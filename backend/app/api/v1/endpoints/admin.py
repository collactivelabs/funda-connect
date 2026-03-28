from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_admin
from app.models.booking import Booking
from app.models.payment import Payout, VerificationDocument
from app.models.teacher import TeacherProfile, TeacherSubject
from app.schemas.teacher import DocumentAccessResponse, VerificationDocumentResponse
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
            for document in sorted(teacher.documents, key=lambda document: document.created_at, reverse=True)
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
    from app.models.parent import ParentProfile

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

    return StatsResponse(
        total_teachers=total_teachers,
        pending_verification=pending_verification,
        verified_teachers=verified_teachers,
        total_parents=total_parents,
        total_bookings=total_bookings,
        confirmed_bookings=confirmed_bookings,
        total_revenue_cents=total_revenue,
        pending_payouts_cents=pending_payouts,
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
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    teacher = await _get_teacher_with_documents(teacher_id, db)
    document = next((doc for doc in teacher.documents if doc.id == document_id), None)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return _document_access_response(document)


@router.patch(
    "/teachers/{teacher_id}/documents/{document_id}",
    response_model=VerificationDocumentResponse,
)
async def review_teacher_document(
    teacher_id: UUID,
    document_id: UUID,
    body: ReviewDocumentRequest,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    teacher = await _get_teacher_with_documents(teacher_id, db)
    document = next((doc for doc in teacher.documents if doc.id == document_id), None)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    document.status = body.status
    document.reviewer_notes = body.reviewer_notes
    document.reviewed_at = datetime.now(UTC)
    _sync_teacher_verification_state(teacher)
    await db.flush()
    return VerificationDocumentResponse.model_validate(document)


@router.patch("/teachers/{teacher_id}/verify")
async def verify_teacher(
    teacher_id: UUID,
    body: VerifyTeacherRequest,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    teacher = await _get_teacher_with_documents(teacher_id, db)

    if body.action == "verify":
        if not has_approved_all_required_documents(teacher.documents):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="All required verification documents must be approved before verifying this teacher",
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

    await db.flush()
    return {"status": teacher.verification_status, "is_listed": teacher.is_listed}


@router.patch("/teachers/{teacher_id}/premium")
async def toggle_premium(
    teacher_id: UUID,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    teacher = await db.get(TeacherProfile, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    teacher.is_premium = not teacher.is_premium
    return {"is_premium": teacher.is_premium}


@router.get("/payouts", response_model=list[PayoutListItem])
async def list_payouts(
    payout_status: str | None = None,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Payout)
        .options(selectinload(Payout.payment))
        .order_by(Payout.created_at.desc())
    )
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
                f"{teacher_map[payout.teacher_id].user.first_name} {teacher_map[payout.teacher_id].user.last_name}"
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
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    payout = await db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout not found")

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
        from app.tasks.notifications import send_payout_notification

        send_payout_notification.apply_async(args=[str(payout_id)], countdown=3)

    return {"id": payout.id, "status": payout.status}
