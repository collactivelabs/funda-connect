import asyncio
import uuid as uuid_lib
from datetime import UTC, datetime, time, timedelta
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pydantic import BaseModel, ConfigDict

from app.core.config import settings
from app.core.deps import get_db, require_teacher
from app.core.redis import get_redis
from app.models.booking import AvailabilitySlot, Booking
from app.models.curriculum import Subject
from app.models.payment import Payout, VerificationDocument
from app.models.teacher import TeacherProfile, TeacherSubject
from app.schemas.booking import (
    AvailabilitySlotResponse,
    BookableSlotResponse,
    SetAvailabilityRequest,
)
from app.services.scheduling import (
    SAST,
    are_slot_keys_available,
    booking_lead_cutoff,
    booking_occurrence_starts,
    format_date_label,
    format_time_label,
    get_teacher_booking_conflicts,
    is_duration_supported,
    local_datetime,
    normalize_utc,
    slot_conflicts_with_bookings,
    slot_lock_keys,
)
from app.schemas.teacher import (
    AddSubjectRequest,
    DocumentAccessResponse,
    TeacherProfileResponse,
    TeacherSubjectResponse,
    UpdateProfileRequest,
    VerificationDocumentResponse,
)
from app.services.notifications import create_in_app_notifications, list_admin_user_ids
from app.services.verification_documents import (
    build_document_access_url,
    derive_teacher_verification_status,
    has_uploaded_all_required_documents,
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


# ── Teacher-only (must be registered BEFORE /{teacher_id} to avoid UUID parsing) ──

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


# ── Documents ─────────────────────────────────────────────────

_ALLOWED_DOC_TYPES = {
    "id_document", "qualification", "sace_certificate", "nrso_clearance", "reference_letter"
}
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
_DOCUMENT_ACCESS_TTL_SECONDS = 900


def _upload_to_s3(key: str, data: bytes, content_type: str) -> str:
    """Synchronous S3 upload — run via asyncio.to_thread."""
    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )
    s3.put_object(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"


def _sync_profile_verification_state(profile: TeacherProfile) -> None:
    profile.verification_status = derive_teacher_verification_status(
        profile.verification_status,
        profile.documents,
    )
    if profile.verification_status != "verified":
        profile.is_listed = False


def _document_access_response(document: VerificationDocument) -> DocumentAccessResponse:
    return DocumentAccessResponse(
        url=build_document_access_url(document.file_url, expires_in=_DOCUMENT_ACCESS_TTL_SECONDS),
        expires_in_seconds=_DOCUMENT_ACCESS_TTL_SECONDS,
    )


@router.get("/me/documents", response_model=list[VerificationDocumentResponse])
async def list_my_documents(
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """List the authenticated teacher's uploaded verification documents."""
    profile = await _get_my_profile(payload, db)
    result = await db.scalars(
        select(VerificationDocument)
        .where(VerificationDocument.teacher_id == profile.id)
        .order_by(VerificationDocument.created_at.desc())
    )
    return result.all()


@router.get("/me/documents/{document_id}/access", response_model=DocumentAccessResponse)
async def get_my_document_access(
    document_id: UUID,
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_my_profile(payload, db)
    document = await db.get(VerificationDocument, document_id)
    if not document or document.teacher_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return _document_access_response(document)


@router.post(
    "/me/documents",
    response_model=VerificationDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    document_type: str,
    file: UploadFile = File(...),
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Upload a verification document (ID, qualification, etc.) to S3."""
    if document_type not in _ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"document_type must be one of: {', '.join(sorted(_ALLOWED_DOC_TYPES))}",
        )

    data = await file.read()
    if len(data) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10 MB limit",
        )

    profile = await _get_my_profile(payload, db)

    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
    key = f"documents/{profile.id}/{document_type}/{uuid_lib.uuid4()}.{ext}"
    content_type = file.content_type or "application/octet-stream"

    try:
        file_url = await asyncio.to_thread(_upload_to_s3, key, data, content_type)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage upload failed: {exc}",
        ) from exc

    doc = VerificationDocument(
        teacher_id=profile.id,
        document_type=document_type,
        file_url=file_url,
        file_name=file.filename or key.split("/")[-1],
    )
    db.add(doc)
    await db.flush()
    documents_result = await db.scalars(
        select(VerificationDocument)
        .where(VerificationDocument.teacher_id == profile.id)
        .order_by(VerificationDocument.created_at.desc())
    )
    profile.documents = documents_result.all()
    _sync_profile_verification_state(profile)

    from app.tasks.notifications import notify_admin_verification_submitted
    if has_uploaded_all_required_documents(profile.documents):
        admin_user_ids = await list_admin_user_ids(db)
        await create_in_app_notifications(
            db,
            user_ids=admin_user_ids,
            notification_type="teacher_verification_submitted",
            title="Teacher verification ready",
            body=(
                f"{profile.user.first_name} {profile.user.last_name} uploaded all required verification documents."
            ),
            metadata={"teacher_id": str(profile.id)},
        )
        notify_admin_verification_submitted.apply_async(args=[str(profile.id)], countdown=5)

    return doc


# ── Earnings ──────────────────────────────────────────────────


class PayoutResponse(BaseModel):
    id: UUID
    amount_cents: int
    status: str
    bank_reference: str | None = None
    processed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EarningsSummary(BaseModel):
    total_earned_cents: int
    pending_payout_cents: int
    paid_out_cents: int
    payouts: list[PayoutResponse]


@router.get("/me/earnings", response_model=EarningsSummary)
async def get_my_earnings(
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Return the teacher's earnings summary and payout history."""
    profile = await _get_my_profile(payload, db)

    payouts_result = await db.scalars(
        select(Payout)
        .where(Payout.teacher_id == profile.id)
        .order_by(Payout.created_at.desc())
    )
    payouts = payouts_result.all()

    total = sum(p.amount_cents for p in payouts)
    pending = sum(p.amount_cents for p in payouts if p.status in ("pending", "processing"))
    paid = sum(p.amount_cents for p in payouts if p.status == "paid")

    return EarningsSummary(
        total_earned_cents=total,
        pending_payout_cents=pending,
        paid_out_cents=paid,
        payouts=payouts,
    )


# ── Public (parameterised — must come AFTER /me routes) ───────

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


@router.get("/{teacher_id}/bookable-slots", response_model=list[BookableSlotResponse])
async def get_teacher_bookable_slots(
    teacher_id: UUID,
    duration_minutes: int = Query(60, ge=30, le=180),
    days: int = Query(settings.BOOKABLE_SLOT_DAYS, ge=1, le=42),
    recurring_weeks: int = Query(1, ge=1, le=12),
    ignore_booking_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return concrete upcoming bookable slots for a teacher."""
    if not is_duration_supported(duration_minutes):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="duration_minutes must be in 30-minute increments",
        )

    teacher = await db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.availability_slots))
    )
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.verification_status != "verified" or not teacher.is_listed:
        return []

    availability_slots = [slot for slot in teacher.availability_slots if slot.is_active]
    if not availability_slots:
        return []

    ignored_booking_start: datetime | None = None
    if ignore_booking_id is not None:
        ignored_booking = await db.get(Booking, ignore_booking_id)
        if ignored_booking and ignored_booking.teacher_id == teacher_id:
            ignored_booking_start = normalize_utc(ignored_booking.scheduled_at)

    now_utc = datetime.now(UTC)
    lead_cutoff_local = booking_lead_cutoff(now_utc).astimezone(SAST)
    start_date = lead_cutoff_local.date()
    query_range_end_local = datetime.combine(
        start_date + timedelta(days=days + ((recurring_weeks - 1) * 7)),
        time.max,
        tzinfo=SAST,
    )

    conflicts = await get_teacher_booking_conflicts(
        db,
        teacher_id,
        range_start=lead_cutoff_local.astimezone(UTC),
        range_end=query_range_end_local.astimezone(UTC),
        now_utc=now_utc,
    )
    redis = await get_redis()

    slots: list[BookableSlotResponse] = []
    seen_start_times: set[datetime] = set()
    step = timedelta(minutes=30)
    duration_delta = timedelta(minutes=duration_minutes)

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        current_day_slots = sorted(
            (
                slot
                for slot in availability_slots
                if slot.day_of_week == current_date.weekday()
            ),
            key=lambda slot: (slot.start_time, slot.end_time),
        )

        for availability_slot in current_day_slots:
            candidate_start_local = local_datetime(current_date, availability_slot.start_time)
            availability_end_local = local_datetime(current_date, availability_slot.end_time)

            while candidate_start_local + duration_delta <= availability_end_local:
                if candidate_start_local < lead_cutoff_local:
                    candidate_start_local += step
                    continue

                candidate_start_utc = normalize_utc(candidate_start_local.astimezone(UTC))
                if ignored_booking_start is not None and candidate_start_utc == ignored_booking_start:
                    candidate_start_local += step
                    continue
                if candidate_start_utc in seen_start_times:
                    candidate_start_local += step
                    continue

                occurrence_starts = booking_occurrence_starts(candidate_start_utc, recurring_weeks)

                if slot_conflicts_with_bookings(
                    conflicts,
                    occurrence_starts,
                    duration_minutes,
                    now_utc,
                    ignore_booking_id=ignore_booking_id,
                ):
                    candidate_start_local += step
                    continue

                lock_keys = slot_lock_keys(teacher.id, occurrence_starts, duration_minutes)
                if not await are_slot_keys_available(redis, lock_keys):
                    candidate_start_local += step
                    continue

                candidate_end_utc = candidate_start_utc + duration_delta
                slots.append(
                    BookableSlotResponse(
                        start_at=candidate_start_utc,
                        end_at=candidate_end_utc,
                        date=current_date,
                        date_label=format_date_label(current_date),
                        time_label=format_time_label(candidate_start_utc, candidate_end_utc),
                    )
                )
                seen_start_times.add(candidate_start_utc)
                candidate_start_local += step

    return slots
