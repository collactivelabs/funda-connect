from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_admin
from app.models.booking import Booking
from app.models.parent import ParentProfile
from app.models.payment import Dispute, Payment, Payout, Refund, VerificationDocument
from app.models.teacher import TeacherProfile, TeacherSubject
from app.schemas.teacher import DocumentAccessResponse, VerificationDocumentResponse
from app.services.audit import create_audit_log
from app.services.notifications import create_in_app_notification
from app.services.rate_limits import (
    ADMIN_MUTATION_RATE_LIMIT,
    build_rate_limit_identifier,
    enforce_rate_limit,
)
from app.services.refunds import payment_status_after_refund
from app.services.teacher_search import sync_teacher_document_by_id
from app.services.verification_documents import (
    build_document_access_url,
    derive_teacher_verification_status,
    get_missing_required_document_types,
    get_rejected_required_document_types,
    has_approved_all_required_documents,
    has_uploaded_all_required_documents,
    verification_document_counts,
)

router = APIRouter()

_DOCUMENT_ACCESS_TTL_SECONDS = 900


class TeacherListItem(BaseModel):
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    email: str
    verification_status: str
    is_listed: bool
    is_premium: bool
    total_lessons: int
    hourly_rate_cents: int | None
    province: str | None
    subject_count: int
    document_count: int
    approved_document_count: int
    pending_document_count: int
    rejected_document_count: int
    all_required_documents_uploaded: bool
    all_required_documents_approved: bool

    model_config = ConfigDict(from_attributes=True)


class VerifyTeacherRequest(BaseModel):
    action: str  # "verify" | "reject" | "suspend"
    notes: str | None = None


class ReviewDocumentRequest(BaseModel):
    status: Literal["approved", "rejected"]
    reviewer_notes: str | None = None

    @model_validator(mode="after")
    def validate_reviewer_notes(self) -> "ReviewDocumentRequest":
        if self.status == "rejected" and not (self.reviewer_notes or "").strip():
            raise ValueError("reviewer_notes are required when rejecting a document")
        if self.reviewer_notes is not None:
            self.reviewer_notes = self.reviewer_notes.strip() or None
        return self


class TeacherVerificationDetail(BaseModel):
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    email: str
    verification_status: str
    is_listed: bool
    is_premium: bool
    total_lessons: int
    hourly_rate_cents: int | None
    province: str | None
    subject_count: int
    subjects: list[str]
    documents: list[VerificationDocumentResponse]
    approved_document_count: int
    pending_document_count: int
    rejected_document_count: int
    all_required_documents_uploaded: bool
    all_required_documents_approved: bool
    missing_required_document_types: list[str]
    rejected_required_document_types: list[str]


class PayoutListItem(BaseModel):
    id: UUID
    teacher_id: UUID
    teacher_name: str
    amount_cents: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdatePayoutRequest(BaseModel):
    status: str  # processing | paid | failed
    bank_reference: str | None = None
    notes: str | None = None


class StatsResponse(BaseModel):
    total_teachers: int
    pending_verification: int
    verified_teachers: int
    total_parents: int
    total_bookings: int
    confirmed_bookings: int
    total_revenue_cents: int
    pending_payouts_cents: int
    pending_refunds_cents: int
    open_disputes: int


class RefundListItem(BaseModel):
    id: UUID
    payment_id: UUID
    booking_id: UUID
    parent_name: str
    teacher_name: str
    amount_cents: int
    status: str
    policy_code: str | None = None
    requested_by_role: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdateRefundRequest(BaseModel):
    status: str  # processing | refunded | failed
    gateway_reference: str | None = None
    notes: str | None = None


class DisputeListItem(BaseModel):
    id: UUID
    booking_id: UUID
    parent_name: str
    teacher_name: str
    subject_name: str
    scheduled_at: datetime
    raised_by_role: str
    reason: str
    status: str
    resolution: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResolveDisputeRequest(BaseModel):
    resolution: Literal["completed", "refunded"]
    notes: str | None = None


def _verification_counts(teacher: TeacherProfile) -> dict[str, int]:
    return verification_document_counts(teacher.documents)


def _teacher_list_item(teacher: TeacherProfile) -> TeacherListItem:
    counts = _verification_counts(teacher)
    return TeacherListItem(
        id=teacher.id,
        user_id=teacher.user_id,
        first_name=teacher.user.first_name,
        last_name=teacher.user.last_name,
        email=teacher.user.email,
        verification_status=teacher.verification_status,
        is_listed=teacher.is_listed,
        is_premium=teacher.is_premium,
        total_lessons=teacher.total_lessons,
        hourly_rate_cents=teacher.hourly_rate_cents,
        province=teacher.province,
        subject_count=len(teacher.subjects),
        document_count=len(teacher.documents),
        approved_document_count=counts["approved"],
        pending_document_count=counts["pending"],
        rejected_document_count=counts["rejected"],
        all_required_documents_uploaded=has_uploaded_all_required_documents(teacher.documents),
        all_required_documents_approved=has_approved_all_required_documents(teacher.documents),
    )


def _teacher_detail_item(teacher: TeacherProfile) -> TeacherVerificationDetail:
    counts = _verification_counts(teacher)
    return TeacherVerificationDetail(
        id=teacher.id,
        user_id=teacher.user_id,
        first_name=teacher.user.first_name,
        last_name=teacher.user.last_name,
        email=teacher.user.email,
        verification_status=teacher.verification_status,
        is_listed=teacher.is_listed,
        is_premium=teacher.is_premium,
        total_lessons=teacher.total_lessons,
        hourly_rate_cents=teacher.hourly_rate_cents,
        province=teacher.province,
        subject_count=len(teacher.subjects),
        subjects=[
            subject.subject.name if subject.subject else "Unknown subject"
            for subject in teacher.subjects
        ],
        documents=[
            VerificationDocumentResponse.model_validate(document)
            for document in sorted(
                teacher.documents, key=lambda document: document.created_at, reverse=True
            )
        ],
        approved_document_count=counts["approved"],
        pending_document_count=counts["pending"],
        rejected_document_count=counts["rejected"],
        all_required_documents_uploaded=has_uploaded_all_required_documents(teacher.documents),
        all_required_documents_approved=has_approved_all_required_documents(teacher.documents),
        missing_required_document_types=get_missing_required_document_types(teacher.documents),
        rejected_required_document_types=get_rejected_required_document_types(teacher.documents),
    )


def _sync_teacher_verification_state(teacher: TeacherProfile) -> None:
    teacher.verification_status = derive_teacher_verification_status(
        teacher.verification_status,
        teacher.documents,
    )
    if teacher.verification_status != "verified":
        teacher.is_listed = False


def _document_access_response(document: VerificationDocument) -> DocumentAccessResponse:
    return DocumentAccessResponse(
        url=build_document_access_url(document.file_url, expires_in=_DOCUMENT_ACCESS_TTL_SECONDS),
        expires_in_seconds=_DOCUMENT_ACCESS_TTL_SECONDS,
    )


async def _get_teacher_with_documents(teacher_id: UUID, db: AsyncSession) -> TeacherProfile:
    teacher = await db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(
            selectinload(TeacherProfile.user),
            selectinload(TeacherProfile.subjects).selectinload(TeacherSubject.subject),
            selectinload(TeacherProfile.documents),
        )
    )
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    return teacher


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_teachers = await db.scalar(select(func.count(TeacherProfile.id))) or 0
    pending_verification = (
        await db.scalar(
            select(func.count(TeacherProfile.id)).where(
                TeacherProfile.verification_status.in_(["pending", "under_review"])
            )
        )
        or 0
    )
    verified_teachers = (
        await db.scalar(
            select(func.count(TeacherProfile.id)).where(
                TeacherProfile.verification_status == "verified"
            )
        )
        or 0
    )
    total_parents = await db.scalar(select(func.count(ParentProfile.id))) or 0
    total_bookings = await db.scalar(select(func.count(Booking.id))) or 0
    confirmed_bookings = (
        await db.scalar(
            select(func.count(Booking.id)).where(
                Booking.status.in_(["confirmed", "in_progress", "completed", "reviewed"])
            )
        )
        or 0
    )
    total_revenue = (
        await db.scalar(
            select(func.coalesce(func.sum(Booking.amount_cents), 0)).where(
                Booking.status.in_(["confirmed", "in_progress", "completed", "reviewed"])
            )
        )
        or 0
    )
    pending_payouts = (
        await db.scalar(
            select(func.coalesce(func.sum(Payout.amount_cents), 0)).where(
                Payout.status == "pending"
            )
        )
        or 0
    )
    pending_refunds = (
        await db.scalar(
            select(func.coalesce(func.sum(Refund.amount_cents), 0)).where(
                Refund.status.in_(["pending", "processing"])
            )
        )
        or 0
    )
    open_disputes = (
        await db.scalar(select(func.count(Dispute.id)).where(Dispute.status == "open")) or 0
    )

    return StatsResponse(
        total_teachers=total_teachers,
        pending_verification=pending_verification,
        verified_teachers=verified_teachers,
        total_parents=total_parents,
        total_bookings=total_bookings,
        confirmed_bookings=confirmed_bookings,
        total_revenue_cents=total_revenue,
        pending_payouts_cents=pending_payouts,
        pending_refunds_cents=pending_refunds,
        open_disputes=open_disputes,
    )


@router.get("/teachers", response_model=list[TeacherListItem])
async def list_teachers_admin(
    verification_status: str | None = None,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(TeacherProfile)
        .options(
            selectinload(TeacherProfile.user),
            selectinload(TeacherProfile.subjects),
            selectinload(TeacherProfile.documents),
        )
        .order_by(TeacherProfile.created_at.desc())
    )
    if verification_status:
        query = query.where(TeacherProfile.verification_status == verification_status)

    result = await db.scalars(query)
    return [_teacher_list_item(teacher) for teacher in result.all()]


@router.get("/teachers/{teacher_id}/verification", response_model=TeacherVerificationDetail)
async def get_teacher_verification_detail(
    teacher_id: UUID,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    teacher = await _get_teacher_with_documents(teacher_id, db)
    return _teacher_detail_item(teacher)


@router.get(
    "/teachers/{teacher_id}/documents/{document_id}/access",
    response_model=DocumentAccessResponse,
)
async def get_teacher_document_access(
    teacher_id: UUID,
    document_id: UUID,
    request: Request,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    teacher = await _get_teacher_with_documents(teacher_id, db)
    document = next((doc for doc in teacher.documents if doc.id == document_id), None)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await create_audit_log(
        db,
        action="verification_document.access",
        resource_type="verification_document",
        resource_id=document.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "teacher_id": teacher.id,
            "document_type": document.document_type,
            "scope": "admin",
        },
    )
    return _document_access_response(document)


@router.patch(
    "/teachers/{teacher_id}/documents/{document_id}",
    response_model=VerificationDocumentResponse,
)
async def review_teacher_document(
    teacher_id: UUID,
    document_id: UUID,
    body: ReviewDocumentRequest,
    request: Request,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        rate_limit=ADMIN_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many admin actions. Please wait a moment and try again.",
    )
    teacher = await _get_teacher_with_documents(teacher_id, db)
    document = next((doc for doc in teacher.documents if doc.id == document_id), None)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    document.status = body.status
    document.reviewer_notes = body.reviewer_notes
    document.reviewed_at = datetime.now(UTC)
    _sync_teacher_verification_state(teacher)
    await db.flush()
    await create_audit_log(
        db,
        action="verification_document.review",
        resource_type="verification_document",
        resource_id=document.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "teacher_id": teacher.id,
            "document_type": document.document_type,
            "status": body.status,
            "has_reviewer_notes": bool(body.reviewer_notes),
        },
    )
    return VerificationDocumentResponse.model_validate(document)


@router.patch("/teachers/{teacher_id}/verify")
async def verify_teacher(
    teacher_id: UUID,
    body: VerifyTeacherRequest,
    request: Request,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        rate_limit=ADMIN_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many admin actions. Please wait a moment and try again.",
    )
    teacher = await _get_teacher_with_documents(teacher_id, db)
    previous_status = teacher.verification_status

    if body.action == "verify":
        if not has_approved_all_required_documents(teacher.documents):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "All required verification documents must be approved before "
                    "verifying this teacher"
                ),
            )
        teacher.verification_status = "verified"
        teacher.is_listed = True
    elif body.action == "reject":
        teacher.verification_status = "rejected"
        teacher.is_listed = False
    elif body.action == "suspend":
        teacher.verification_status = "suspended"
        teacher.is_listed = False
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="action must be verify | reject | suspend",
        )

    from app.tasks.notifications import notify_teacher_verification_result

    notify_teacher_verification_result.apply_async(
        args=[str(teacher_id), teacher.verification_status, body.notes],
        countdown=2,
    )
    await create_in_app_notification(
        db,
        user_id=teacher.user_id,
        notification_type="teacher_verification_result",
        title="Verification status updated",
        body=(
            "Your teacher profile has been verified and is now live."
            if teacher.verification_status == "verified"
            else f"Your teacher verification status is now '{teacher.verification_status}'."
        ),
        metadata={"teacher_id": str(teacher.id), "status": teacher.verification_status},
    )

    await db.flush()
    await sync_teacher_document_by_id(db, teacher.id)
    await create_audit_log(
        db,
        action="teacher.verification_status.update",
        resource_type="teacher_profile",
        resource_id=teacher.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "teacher_id": teacher.id,
            "action": body.action,
            "previous_status": previous_status,
            "new_status": teacher.verification_status,
            "is_listed": teacher.is_listed,
            "has_notes": bool(body.notes),
        },
    )
    return {"status": teacher.verification_status, "is_listed": teacher.is_listed}


@router.patch("/teachers/{teacher_id}/premium")
async def toggle_premium(
    teacher_id: UUID,
    request: Request,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        rate_limit=ADMIN_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many admin actions. Please wait a moment and try again.",
    )
    teacher = await db.get(TeacherProfile, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    teacher.is_premium = not teacher.is_premium
    await db.flush()
    await sync_teacher_document_by_id(db, teacher.id)
    await create_audit_log(
        db,
        action="teacher.premium.toggle",
        resource_type="teacher_profile",
        resource_id=teacher.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={"teacher_id": teacher.id, "is_premium": teacher.is_premium},
    )
    return {"is_premium": teacher.is_premium}


@router.get("/payouts", response_model=list[PayoutListItem])
async def list_payouts(
    payout_status: str | None = None,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Payout).options(selectinload(Payout.payment)).order_by(Payout.created_at.desc())
    if payout_status:
        query = query.where(Payout.status == payout_status)

    result = await db.scalars(query)
    payouts = result.all()

    teacher_ids = list({payout.teacher_id for payout in payouts})
    teachers_result = await db.scalars(
        select(TeacherProfile)
        .where(TeacherProfile.id.in_(teacher_ids))
        .options(selectinload(TeacherProfile.user))
    )
    teacher_map = {teacher.id: teacher for teacher in teachers_result.all()}

    return [
        PayoutListItem(
            id=payout.id,
            teacher_id=payout.teacher_id,
            teacher_name=(
                f"{teacher_map[payout.teacher_id].user.first_name} "
                f"{teacher_map[payout.teacher_id].user.last_name}"
                if payout.teacher_id in teacher_map
                else "Unknown"
            ),
            amount_cents=payout.amount_cents,
            status=payout.status,
            created_at=payout.created_at,
        )
        for payout in payouts
    ]


@router.patch("/payouts/{payout_id}")
async def update_payout(
    payout_id: UUID,
    body: UpdatePayoutRequest,
    request: Request,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        rate_limit=ADMIN_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many admin actions. Please wait a moment and try again.",
    )
    payout = await db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout not found")
    previous_status = payout.status

    allowed = {"processing", "paid", "failed"}
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of: {', '.join(allowed)}",
        )
    payout.status = body.status
    if body.bank_reference:
        payout.bank_reference = body.bank_reference
    if body.notes:
        payout.notes = body.notes
    if body.status == "paid":
        payout.processed_at = datetime.now(UTC)
        teacher_user_id = await db.scalar(
            select(TeacherProfile.user_id).where(TeacherProfile.id == payout.teacher_id)
        )
        if teacher_user_id:
            await create_in_app_notification(
                db,
                user_id=teacher_user_id,
                notification_type="payout_paid",
                title="Payout processed",
                body=f"Your payout of R{payout.amount_cents / 100:.2f} has been marked as paid.",
                metadata={"payout_id": str(payout.id)},
            )
        from app.tasks.notifications import send_payout_notification

        send_payout_notification.apply_async(args=[str(payout_id)], countdown=3)

    await create_audit_log(
        db,
        action="payout.status.update",
        resource_type="payout",
        resource_id=payout.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "teacher_id": payout.teacher_id,
            "payment_id": payout.payment_id,
            "previous_status": previous_status,
            "new_status": payout.status,
            "bank_reference_present": bool(body.bank_reference),
            "has_notes": bool(body.notes),
        },
    )
    return {"id": payout.id, "status": payout.status}


@router.get("/refunds", response_model=list[RefundListItem])
async def list_refunds(
    refund_status: str | None = None,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Refund)
        .options(
            selectinload(Refund.payment)
            .selectinload(Payment.booking)
            .selectinload(Booking.parent)
            .selectinload(ParentProfile.user),
            selectinload(Refund.payment)
            .selectinload(Payment.booking)
            .selectinload(Booking.teacher)
            .selectinload(TeacherProfile.user),
        )
        .order_by(Refund.created_at.desc())
    )
    if refund_status:
        query = query.where(Refund.status == refund_status)

    result = await db.scalars(query)
    refunds = result.all()

    return [
        RefundListItem(
            id=refund.id,
            payment_id=refund.payment_id,
            booking_id=refund.payment.booking_id,
            parent_name=(
                f"{refund.payment.booking.parent.user.first_name} "
                f"{refund.payment.booking.parent.user.last_name}"
            ),
            teacher_name=(
                f"{refund.payment.booking.teacher.user.first_name} "
                f"{refund.payment.booking.teacher.user.last_name}"
            ),
            amount_cents=refund.amount_cents,
            status=refund.status,
            policy_code=refund.policy_code,
            requested_by_role=refund.requested_by_role,
            created_at=refund.created_at,
        )
        for refund in refunds
    ]


@router.patch("/refunds/{refund_id}")
async def update_refund(
    refund_id: UUID,
    body: UpdateRefundRequest,
    request: Request,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        rate_limit=ADMIN_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many admin actions. Please wait a moment and try again.",
    )
    refund = await db.scalar(
        select(Refund)
        .where(Refund.id == refund_id)
        .options(selectinload(Refund.payment).selectinload(Payment.booking))
    )
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found")
    previous_status = refund.status

    allowed = {"processing", "refunded", "failed"}
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of: {', '.join(sorted(allowed))}",
        )

    refund.status = body.status
    if body.gateway_reference:
        refund.gateway_reference = body.gateway_reference
    if body.notes:
        refund.notes = body.notes

    if body.status == "refunded":
        refund.processed_at = datetime.now(UTC)
        refund.payment.status = payment_status_after_refund(
            refund.payment.amount_cents,
            refund.amount_cents,
        )
        parent_user_id = await db.scalar(
            select(ParentProfile.user_id).where(
                ParentProfile.id == refund.payment.booking.parent_id
            )
        )
        if parent_user_id:
            await create_in_app_notification(
                db,
                user_id=parent_user_id,
                notification_type="refund_processed",
                title="Refund processed",
                body=f"Your refund of R{refund.amount_cents / 100:.2f} has been processed.",
                metadata={
                    "refund_id": str(refund.id),
                    "booking_id": str(refund.payment.booking_id),
                },
            )
        from app.tasks.notifications import send_refund_notification

        send_refund_notification.apply_async(args=[str(refund.id)], countdown=3)
    elif body.status == "failed":
        refund.processed_at = None
        refund.payment.status = "complete"

    await create_audit_log(
        db,
        action="refund.status.update",
        resource_type="refund",
        resource_id=refund.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "payment_id": refund.payment_id,
            "booking_id": refund.payment.booking_id,
            "previous_status": previous_status,
            "new_status": refund.status,
            "gateway_reference_present": bool(body.gateway_reference),
            "has_notes": bool(body.notes),
        },
    )
    return {"id": refund.id, "status": refund.status}


@router.get("/disputes", response_model=list[DisputeListItem])
async def list_disputes(
    dispute_status: str | None = None,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Dispute)
        .options(
            selectinload(Dispute.booking)
            .selectinload(Booking.parent)
            .selectinload(ParentProfile.user),
            selectinload(Dispute.booking)
            .selectinload(Booking.teacher)
            .selectinload(TeacherProfile.user),
            selectinload(Dispute.booking).selectinload(Booking.subject),
        )
        .order_by(Dispute.created_at.desc())
    )
    if dispute_status:
        query = query.where(Dispute.status == dispute_status)

    result = await db.scalars(query)
    disputes = result.all()

    return [
        DisputeListItem(
            id=dispute.id,
            booking_id=dispute.booking_id,
            parent_name=(
                f"{dispute.booking.parent.user.first_name} {dispute.booking.parent.user.last_name}"
            ),
            teacher_name=(
                f"{dispute.booking.teacher.user.first_name} "
                f"{dispute.booking.teacher.user.last_name}"
            ),
            subject_name=dispute.booking.subject.name,
            scheduled_at=dispute.booking.scheduled_at,
            raised_by_role=dispute.raised_by_role,
            reason=dispute.reason,
            status=dispute.status,
            resolution=dispute.resolution,
            created_at=dispute.created_at,
        )
        for dispute in disputes
    ]


@router.patch("/disputes/{dispute_id}")
async def resolve_dispute(
    dispute_id: UUID,
    body: ResolveDisputeRequest,
    request: Request,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        rate_limit=ADMIN_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many admin actions. Please wait a moment and try again.",
    )
    dispute = await db.scalar(
        select(Dispute)
        .where(Dispute.id == dispute_id)
        .options(
            selectinload(Dispute.booking)
            .selectinload(Booking.payment)
            .selectinload(Payment.payout),
            selectinload(Dispute.booking)
            .selectinload(Booking.payment)
            .selectinload(Payment.refund),
        )
    )
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    if dispute.status != "open":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dispute is already resolved"
        )

    booking = dispute.booking
    payment = booking.payment
    payout = payment.payout if payment else None

    dispute.status = "resolved"
    dispute.resolution = body.resolution
    dispute.admin_notes = body.notes
    dispute.resolved_at = datetime.now(UTC)

    if body.resolution == "completed":
        booking.status = "completed"
        if payment and payout is None and booking.teacher_payout_cents > 0:
            db.add(
                Payout(
                    teacher_id=booking.teacher_id,
                    payment_id=payment.id,
                    amount_cents=booking.teacher_payout_cents,
                    status="pending",
                    notes="Created after dispute was resolved as completed.",
                )
            )
        elif payout and payout.status == "failed":
            payout.status = "pending"
            payout.notes = "Reopened after dispute was resolved as completed."
    else:
        booking.status = "cancelled"
        booking.teacher_payout_cents = 0
        booking.commission_cents = 0

        if payout and payout.status != "paid":
            payout.status = "failed"
            payout.notes = "Cancelled because the dispute was resolved as refunded."

        if payment:
            refund = payment.refund
            if refund is None:
                refund = Refund(
                    payment_id=payment.id,
                    amount_cents=payment.amount_cents,
                    status="pending",
                    reason=dispute.reason,
                    requested_by_role="admin",
                    policy_code="dispute_refund",
                    notes=(
                        "Created from dispute resolution. Process manually in "
                        "PayFast and then mark refunded."
                    ),
                )
                db.add(refund)
            else:
                refund.amount_cents = payment.amount_cents
                refund.status = "pending"
                refund.reason = dispute.reason
                refund.requested_by_role = "admin"
                refund.policy_code = "dispute_refund"
                refund.notes = (
                    "Created from dispute resolution. Process manually in "
                    "PayFast and then mark refunded."
                )

    parent_user_id = await db.scalar(
        select(ParentProfile.user_id).where(ParentProfile.id == booking.parent_id)
    )
    teacher_user_id = await db.scalar(
        select(TeacherProfile.user_id).where(TeacherProfile.id == booking.teacher_id)
    )
    for user_id in (parent_user_id, teacher_user_id):
        if user_id:
            await create_in_app_notification(
                db,
                user_id=user_id,
                notification_type="dispute_resolved",
                title="Dispute resolved",
                body=(
                    "An admin resolved the dispute and restored the lesson as completed."
                    if body.resolution == "completed"
                    else "An admin resolved the dispute and moved it into the refund flow."
                ),
                metadata={
                    "dispute_id": str(dispute.id),
                    "booking_id": str(booking.id),
                    "resolution": body.resolution,
                },
            )

    await create_audit_log(
        db,
        action="dispute.resolve",
        resource_type="dispute",
        resource_id=dispute.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "booking_id": booking.id,
            "resolution": body.resolution,
            "booking_status": booking.status,
            "has_notes": bool(body.notes),
        },
    )
    return {"id": dispute.id, "status": dispute.status, "resolution": dispute.resolution}
