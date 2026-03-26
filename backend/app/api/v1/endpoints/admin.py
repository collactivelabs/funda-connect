from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_admin
from app.models.booking import Booking
from app.models.payment import Payout, VerificationDocument
from app.models.teacher import TeacherProfile, TeacherSubject
from app.models.user import User

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────


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

    model_config = ConfigDict(from_attributes=True)


class VerifyTeacherRequest(BaseModel):
    action: str  # "verify" | "reject" | "suspend"
    notes: str | None = None


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


# ── Dashboard stats ───────────────────────────────────────────


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
                TeacherProfile.verification_status == "pending"
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


# ── Teacher verification queue ────────────────────────────────


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
    teachers = result.all()

    return [
        TeacherListItem(
            id=t.id,
            user_id=t.user_id,
            first_name=t.user.first_name,
            last_name=t.user.last_name,
            email=t.user.email,
            verification_status=t.verification_status,
            is_listed=t.is_listed,
            is_premium=t.is_premium,
            total_lessons=t.total_lessons,
            hourly_rate_cents=t.hourly_rate_cents,
            province=t.province,
            subject_count=len(t.subjects),
            document_count=len(t.documents),
        )
        for t in teachers
    ]


@router.patch("/teachers/{teacher_id}/verify")
async def verify_teacher(
    teacher_id: UUID,
    body: VerifyTeacherRequest,
    _payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    teacher = await db.get(TeacherProfile, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    if body.action == "verify":
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


# ── Payouts ───────────────────────────────────────────────────


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

    # Fetch teacher names in bulk
    teacher_ids = list({p.teacher_id for p in payouts})
    teachers_result = await db.scalars(
        select(TeacherProfile)
        .where(TeacherProfile.id.in_(teacher_ids))
        .options(selectinload(TeacherProfile.user))
    )
    teacher_map = {t.id: t for t in teachers_result.all()}

    return [
        PayoutListItem(
            id=p.id,
            teacher_id=p.teacher_id,
            teacher_name=(
                f"{teacher_map[p.teacher_id].user.first_name} {teacher_map[p.teacher_id].user.last_name}"
                if p.teacher_id in teacher_map else "Unknown"
            ),
            amount_cents=p.amount_cents,
            status=p.status,
            created_at=p.created_at,
        )
        for p in payouts
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
