from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_teacher
from app.models.booking import AvailabilitySlot
from app.models.curriculum import Subject
from app.models.teacher import TeacherProfile, TeacherSubject
from app.schemas.booking import AvailabilitySlotResponse, SetAvailabilityRequest
from app.schemas.teacher import (
    AddSubjectRequest,
    TeacherProfileResponse,
    TeacherSubjectResponse,
    UpdateProfileRequest,
)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────

def _teacher_response(profile: TeacherProfile) -> TeacherProfileResponse:
    subjects = [TeacherSubjectResponse.from_orm_with_subject(ts) for ts in profile.subjects]
    return TeacherProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        bio=profile.bio,
        headline=profile.headline,
        years_experience=profile.years_experience,
        hourly_rate_cents=profile.hourly_rate_cents,
        curricula=profile.curricula or [],
        verification_status=profile.verification_status,
        is_listed=profile.is_listed,
        average_rating=profile.average_rating,
        total_reviews=profile.total_reviews,
        total_lessons=profile.total_lessons,
        is_premium=profile.is_premium,
        province=profile.province,
        subjects=subjects,
        user=profile.user,
    )


async def _get_my_profile(payload: dict, db: AsyncSession) -> TeacherProfile:
    profile = await db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.user_id == UUID(payload["sub"]))
        .options(selectinload(TeacherProfile.subjects).selectinload(TeacherSubject.subject))
        .options(selectinload(TeacherProfile.user))
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher profile not found")
    return profile


# ── Public ────────────────────────────────────────────────────

@router.get("", response_model=list[TeacherProfileResponse])
async def list_teachers(
    subject: str | None = None,
    curriculum: str | None = None,
    grade: str | None = None,
    min_rate: int | None = None,
    max_rate: int | None = None,
    province: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Search and filter verified, listed teachers."""
    query = (
        select(TeacherProfile)
        .where(TeacherProfile.is_listed == True)  # noqa: E712
        .where(TeacherProfile.verification_status == "verified")
        .options(selectinload(TeacherProfile.subjects).selectinload(TeacherSubject.subject))
        .options(selectinload(TeacherProfile.user))
        .order_by(TeacherProfile.is_premium.desc(), TeacherProfile.average_rating.desc())
    )
    if min_rate is not None:
        query = query.where(TeacherProfile.hourly_rate_cents >= min_rate)
    if max_rate is not None:
        query = query.where(TeacherProfile.hourly_rate_cents <= max_rate)
    if province:
        query = query.where(TeacherProfile.province == province)
    if curriculum:
        query = query.where(TeacherProfile.curricula.contains([curriculum]))
    if subject:
        query = query.join(TeacherProfile.subjects).join(TeacherSubject.subject).where(
            Subject.slug == subject
        )
    if grade:
        query = query.join(TeacherProfile.subjects, isouter=not bool(subject)).where(
            TeacherSubject.grade_levels.contains([grade])
        )

    result = await db.scalars(query)
    return [_teacher_response(p) for p in result.unique().all()]


@router.get("/{teacher_id}", response_model=TeacherProfileResponse)
async def get_teacher(teacher_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a teacher's public profile."""
    profile = await db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.subjects).selectinload(TeacherSubject.subject))
        .options(selectinload(TeacherProfile.user))
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    return _teacher_response(profile)


@router.get("/{teacher_id}/availability", response_model=list[AvailabilitySlotResponse])
async def get_teacher_availability(teacher_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a teacher's weekly availability (public, for booking)."""
    result = await db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.teacher_id == teacher_id, AvailabilitySlot.is_active == True)  # noqa: E712
        .order_by(AvailabilitySlot.day_of_week, AvailabilitySlot.start_time)
    )
    return result.all()


# ── Teacher-only ──────────────────────────────────────────────

@router.get("/me", response_model=TeacherProfileResponse)
async def get_my_profile(
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    return _teacher_response(await _get_my_profile(payload, db))


@router.patch("/me/profile", response_model=TeacherProfileResponse)
async def update_my_profile(
    body: UpdateProfileRequest,
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_my_profile(payload, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    return _teacher_response(profile)


@router.post("/me/subjects", response_model=TeacherSubjectResponse, status_code=status.HTTP_201_CREATED)
async def add_subject(
    body: AddSubjectRequest,
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_my_profile(payload, db)
    subject = await db.get(Subject, body.subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    existing = await db.scalar(
        select(TeacherSubject).where(
            TeacherSubject.teacher_id == profile.id,
            TeacherSubject.subject_id == body.subject_id,
            TeacherSubject.curriculum == body.curriculum,
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Subject already added for this curriculum")
    ts = TeacherSubject(
        teacher_id=profile.id,
        subject_id=body.subject_id,
        grade_levels=body.grade_levels,
        curriculum=body.curriculum,
    )
    db.add(ts)
    await db.flush()
    ts.subject = subject
    return TeacherSubjectResponse.from_orm_with_subject(ts)


@router.delete("/me/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_subject(
    subject_id: UUID,
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_my_profile(payload, db)
    ts = await db.get(TeacherSubject, subject_id)
    if not ts or ts.teacher_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    await db.delete(ts)


@router.get("/me/availability", response_model=list[AvailabilitySlotResponse])
async def get_my_availability(
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_my_profile(payload, db)
    result = await db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.teacher_id == profile.id)
        .order_by(AvailabilitySlot.day_of_week, AvailabilitySlot.start_time)
    )
    return result.all()


@router.put("/me/availability", response_model=list[AvailabilitySlotResponse])
async def set_my_availability(
    body: SetAvailabilityRequest,
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Replace all availability slots (full overwrite)."""
    profile = await _get_my_profile(payload, db)
    await db.execute(
        delete(AvailabilitySlot).where(AvailabilitySlot.teacher_id == profile.id)
    )
    slots = [
        AvailabilitySlot(
            teacher_id=profile.id,
            day_of_week=s.day_of_week,
            start_time=s.start_time,
            end_time=s.end_time,
        )
        for s in body.slots
    ]
    db.add_all(slots)
    await db.flush()
    return slots
