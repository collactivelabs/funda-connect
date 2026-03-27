import hashlib
import urllib.parse
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import get_db, require_any_user, require_parent
from app.core.redis import get_redis
from app.models.booking import Booking
from app.models.parent import Learner, ParentProfile
from app.models.payment import Payment
from app.models.teacher import TeacherProfile
from app.services.scheduling import (
    acquire_slot_hold,
    booking_lead_cutoff,
    booking_hold_expires_at,
    booking_occurrence_starts,
    normalize_utc,
    get_teacher_booking_conflicts,
    is_duration_supported,
    is_slot_aligned,
    is_within_weekly_availability,
    release_slot_hold,
    slot_conflicts_with_bookings,
    slot_lock_keys,
)
from app.schemas.booking import (
    BookingResponse,
    CancelBookingRequest,
    CreateBookingRequest,
    PayFastRedirectResponse,
)

router = APIRouter()

PAYFAST_SANDBOX_URL = "https://sandbox.payfast.co.za/eng/process"
PAYFAST_LIVE_URL = "https://www.payfast.co.za/eng/process"


def _requested_recurring_weeks(body: CreateBookingRequest) -> int:
    return body.recurring_weeks if body.is_recurring and body.recurring_weeks else 1


async def _assert_booking_access(booking: Booking, payload: dict, db: AsyncSession) -> None:
    user_id = UUID(payload["sub"])
    role = payload.get("role")

    if role == "admin":
        return

    if role == "parent":
        profile_id = await db.scalar(
            select(ParentProfile.id).where(ParentProfile.user_id == user_id)
        )
        if profile_id and booking.parent_id == profile_id:
            return
    elif role == "teacher":
        profile_id = await db.scalar(
            select(TeacherProfile.id).where(TeacherProfile.user_id == user_id)
        )
        if profile_id and booking.teacher_id == profile_id:
            return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _payfast_url(booking: Booking, user_email: str) -> str:
    return PAYFAST_SANDBOX_URL if settings.PAYFAST_SANDBOX else PAYFAST_LIVE_URL


def _payfast_parent_url(
    configured_url: str | None,
    booking: Booking,
    status_value: str,
) -> str:
    base_url = configured_url.strip() if configured_url else ""
    if not base_url:
        base_url = f"{settings.ALLOWED_ORIGINS[0]}/parent"

    parsed = urllib.parse.urlsplit(base_url)
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query_pairs.extend([
        ("booking", str(booking.id)),
        ("status", status_value),
    ])
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query_pairs)))


def _payfast_notify_url() -> str:
    configured_url = settings.PAYFAST_NOTIFY_URL.strip() if settings.PAYFAST_NOTIFY_URL else ""
    if configured_url:
        return configured_url
    return "http://localhost:8000/api/v1/bookings/payfast/itn"


def _payfast_signature(data: dict[str, str], passphrase: str | None = None) -> str:
    pairs: list[str] = []
    for key, value in data.items():
        if value is None:
            continue

        normalized = str(value).strip()
        if not normalized:
            continue

        encoded = urllib.parse.quote_plus(normalized)
        pairs.append(f"{key}={encoded}")

    if passphrase and passphrase.strip():
        pairs.append(f"passphrase={urllib.parse.quote_plus(passphrase.strip())}")

    payload = "&".join(pairs)
    return hashlib.md5(payload.encode()).hexdigest()  # noqa: S324


def _payfast_form_data(booking: Booking, user_email: str) -> dict[str, str]:
    amount = booking.amount_cents / 100
    data = {
        "merchant_id": settings.PAYFAST_MERCHANT_ID or "10000100",
        "merchant_key": settings.PAYFAST_MERCHANT_KEY or "46f0cd694581a",
        "return_url": _payfast_parent_url(settings.PAYFAST_RETURN_URL, booking, "success"),
        "cancel_url": _payfast_parent_url(settings.PAYFAST_CANCEL_URL, booking, "cancelled"),
        "notify_url": _payfast_notify_url(),
        "email_address": user_email,
        "m_payment_id": str(booking.id),
        "amount": f"{amount:.2f}",
        "item_name": f"FundaConnect Lesson - Booking {str(booking.id)[:8]}",
    }
    data["signature"] = _payfast_signature(data, settings.PAYFAST_PASSPHRASE)
    return data


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PayFastRedirectResponse)
async def create_booking(
    body: CreateBookingRequest,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Parent creates a booking. Returns PayFast payment URL."""
    parent_profile = await db.scalar(
        select(ParentProfile).where(ParentProfile.user_id == UUID(payload["sub"]))
    )
    if not parent_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found")

    # Ownership: learner must belong to this parent
    learner = await db.get(Learner, body.learner_id)
    if not learner or learner.parent_id != parent_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")

    # Teacher must be verified and listed
    teacher = await db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == body.teacher_id)
        .options(
            selectinload(TeacherProfile.availability_slots),
            selectinload(TeacherProfile.subjects),
        )
    )
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.verification_status != "verified":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Teacher is not verified")
    if not teacher.is_listed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Teacher is not accepting bookings")
    if not teacher.hourly_rate_cents:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Teacher has not set a rate")
    matching_subjects = [subject for subject in teacher.subjects if subject.subject_id == body.subject_id]
    if not matching_subjects:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Teacher does not teach this subject")
    if not any(
        subject.curriculum == learner.curriculum
        and (not subject.grade_levels or learner.grade in subject.grade_levels)
        for subject in matching_subjects
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Teacher does not teach this subject for the learner's grade and curriculum",
        )
    if not is_duration_supported(body.duration_minutes):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported lesson duration")
    if not is_slot_aligned(body.scheduled_at):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bookings must start on 30-minute boundaries",
        )

    now_utc = datetime.now(UTC)
    lead_cutoff = booking_lead_cutoff(now_utc)
    hold_expires_at = booking_hold_expires_at(now_utc)
    recurring_weeks = _requested_recurring_weeks(body)
    occurrence_starts = booking_occurrence_starts(body.scheduled_at, recurring_weeks)

    if occurrence_starts[0] < lead_cutoff:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Bookings must be made at least {settings.BOOKING_MIN_LEAD_MINUTES} minutes in advance",
        )

    if not all(
        is_within_weekly_availability(
            teacher.availability_slots,
            occurrence_start,
            body.duration_minutes,
        )
        for occurrence_start in occurrence_starts
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected time falls outside the teacher's availability",
        )

    range_start = occurrence_starts[0]
    range_end = occurrence_starts[-1]
    conflicts = await get_teacher_booking_conflicts(
        db,
        teacher.id,
        range_start=range_start,
        range_end=range_end,
        now_utc=now_utc,
    )
    if slot_conflicts_with_bookings(conflicts, occurrence_starts, body.duration_minutes, now_utc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That slot is no longer available. Please choose another time.",
        )

    redis = await get_redis()
    hold_keys = await acquire_slot_hold(
        redis,
        teacher.id,
        occurrence_starts,
        body.duration_minutes,
        hold_expires_at,
    )
    if hold_keys is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That slot is currently on hold. Please choose another time.",
        )

    # Price calculation
    amount_cents = int(teacher.hourly_rate_cents * body.duration_minutes / 60)
    commission_cents = int(amount_cents * settings.PLATFORM_COMMISSION_RATE)
    payout_cents = amount_cents - commission_cents

    try:
        booking = Booking(
            parent_id=parent_profile.id,
            teacher_id=body.teacher_id,
            learner_id=body.learner_id,
            subject_id=body.subject_id,
            scheduled_at=body.scheduled_at,
            duration_minutes=body.duration_minutes,
            hold_expires_at=hold_expires_at,
            is_trial=body.is_trial,
            is_recurring=body.is_recurring and bool(body.recurring_weeks),
            parent_notes=body.parent_notes,
            amount_cents=amount_cents,
            commission_cents=commission_cents,
            teacher_payout_cents=payout_cents,
            status="pending_payment",
        )
        db.add(booking)
        await db.flush()

        payment = Payment(
            booking_id=booking.id,
            gateway="payfast",
            amount_cents=amount_cents,
            status="pending",
            gateway_metadata={"recurring_weeks": recurring_weeks} if recurring_weeks > 1 else None,
        )
        db.add(payment)
        await db.commit()
    except Exception:
        await db.rollback()
        await release_slot_hold(redis, hold_keys)
        raise

    from app.tasks.lessons import expire_pending_booking_hold

    expire_pending_booking_hold.apply_async(
        args=[str(booking.id)],
        countdown=settings.BOOKING_HOLD_MINUTES * 60,
    )

    payment_url = _payfast_url(booking, payload["email"])
    form_data = _payfast_form_data(booking, payload["email"])
    return PayFastRedirectResponse(
        booking_id=booking.id,
        payment_url=payment_url,
        form_data=form_data,
        amount_cents=amount_cents,
    )


@router.get("/my", response_model=list[BookingResponse])
async def list_my_bookings(
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """List bookings for the authenticated user (parent or teacher)."""
    role = payload.get("role")
    user_id = UUID(payload["sub"])

    base_query = (
        select(Booking)
        .options(
            selectinload(Booking.learner),
            selectinload(Booking.subject),
        )
        .order_by(Booking.scheduled_at.desc())
    )

    if role == "parent":
        profile = await db.scalar(
            select(ParentProfile).where(ParentProfile.user_id == user_id)
        )
        if not profile:
            return []
        result = await db.scalars(base_query.where(Booking.parent_id == profile.id))
    else:
        profile = await db.scalar(
            select(TeacherProfile).where(TeacherProfile.user_id == user_id)
        )
        if not profile:
            return []
        result = await db.scalars(base_query.where(Booking.teacher_id == profile.id))

    return result.all()


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: UUID,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Get booking details (ownership enforced)."""
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    await _assert_booking_access(booking, payload, db)
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
    body: CancelBookingRequest,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a booking. Only pending_payment or confirmed bookings can be cancelled."""
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(selectinload(Booking.payment))
    )
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    await _assert_booking_access(booking, payload, db)

    if booking.status not in ("pending_payment", "confirmed"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot cancel a booking with status '{booking.status}'",
        )

    previous_status = booking.status
    room_url = booking.video_room_url
    booking.status = "cancelled"
    booking.cancellation_reason = body.reason
    booking.video_room_url = None
    booking.hold_expires_at = None

    if previous_status == "pending_payment" and booking.payment:
        booking.payment.status = "cancelled"

    recurring_weeks = 1
    if booking.payment and isinstance(booking.payment.gateway_metadata, dict):
        recurring_weeks = int(booking.payment.gateway_metadata.get("recurring_weeks") or 1)

    redis = await get_redis()
    await release_slot_hold(
        redis,
        slot_lock_keys(
            booking.teacher_id,
            booking_occurrence_starts(booking.scheduled_at, recurring_weeks),
            booking.duration_minutes,
        ),
    )

    # Best-effort room cleanup (fire-and-forget, don't block the response)
    if room_url:
        import asyncio
        from app.services.video import delete_room
        room_name = room_url.rstrip("/").split("/")[-1]
        asyncio.create_task(delete_room(room_name))

    return booking


@router.post("/{booking_id}/complete", response_model=BookingResponse)
async def complete_booking(
    booking_id: UUID,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Teacher marks a confirmed lesson as completed."""
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    # Only the assigned teacher can mark complete
    user_id = UUID(payload["sub"])
    profile = await db.scalar(
        select(TeacherProfile).where(TeacherProfile.user_id == user_id)
    )
    if not profile or booking.teacher_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot complete a booking with status '{booking.status}'",
        )

    now_utc = datetime.now(UTC)
    lesson_start = normalize_utc(booking.scheduled_at)
    if now_utc < lesson_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You can only mark a lesson complete after it has started",
        )

    booking.status = "completed"
    return booking


@router.post("/{booking_id}/cancel-series", response_model=list[BookingResponse])
async def cancel_booking_series(
    booking_id: UUID,
    body: CancelBookingRequest,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel all future confirmed bookings in a recurring series."""
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if not booking.is_recurring:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Booking is not recurring"
        )

    # The root booking id is either this booking (if it is root) or its parent
    root_id = booking.recurring_booking_id or booking.id

    await _assert_booking_access(booking, payload, db)

    # Find all future confirmed bookings in this series
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    siblings = (
        await db.scalars(
            select(Booking).where(
                Booking.status == "confirmed",
                Booking.scheduled_at > now,
                (Booking.id == root_id)
                | (Booking.recurring_booking_id == root_id),
            )
        )
    ).all()

    cancelled = []
    for sib in siblings:
        sib.status = "cancelled"
        sib.cancellation_reason = body.reason
        if sib.video_room_url:
            sib.video_room_url = None
        cancelled.append(sib)

    return cancelled


def _verify_payfast_signature(data: dict) -> bool:
    """Verify the PayFast ITN signature against the posted data."""
    received_sig = data.get("signature", "")
    fields = {
        key: str(value)
        for key, value in data.items()
        if key != "signature"
    }
    expected = _payfast_signature(fields, settings.PAYFAST_PASSPHRASE)
    return expected == received_sig


# PayFast valid source IPs (sandbox + production)
_PAYFAST_VALID_IPS = {
    "197.97.145.144", "197.97.145.145", "197.97.145.146", "197.97.145.147",
    "204.93.204.23", "204.93.204.24", "204.93.204.25", "204.93.204.26",
    # Allow localhost for sandbox testing
    "127.0.0.1", "::1",
}


@router.post("/payfast/itn")
async def payfast_itn(request: Request, db: AsyncSession = Depends(get_db)):
    """PayFast Instant Transaction Notification webhook."""
    form = await request.form()
    data = dict(form)

    # Signature verification (skip in sandbox mode to ease local testing)
    if not settings.PAYFAST_SANDBOX:
        client_ip = request.client.host if request.client else ""
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        source_ip = forwarded or client_ip
        if source_ip not in _PAYFAST_VALID_IPS:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown source IP")
        if not _verify_payfast_signature(data):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    booking_id = data.get("m_payment_id")
    pf_payment_id = data.get("pf_payment_id")
    payment_status = data.get("payment_status")

    if not booking_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing m_payment_id")

    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == UUID(booking_id))
        .options(selectinload(Booking.payment))
    )
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if not booking.payment:
        return {"status": "ok"}

    booking.payment.gateway_payment_id = pf_payment_id
    booking.payment.gateway_metadata = {
        **(booking.payment.gateway_metadata or {}),
        **data,
    }

    recurring_weeks = int((booking.payment.gateway_metadata or {}).get("recurring_weeks") or 1)
    hold_keys = slot_lock_keys(
        booking.teacher_id,
        booking_occurrence_starts(booking.scheduled_at, recurring_weeks),
        booking.duration_minutes,
    )
    redis = await get_redis()
    now_utc = datetime.now(UTC)

    if payment_status == "COMPLETE":
        if booking.payment.status == "complete" and booking.status == "confirmed":
            return {"status": "ok"}

        if booking.status != "pending_payment":
            return {"status": "ignored"}

        if booking.hold_expires_at is not None and booking.hold_expires_at <= now_utc:
            booking.status = "expired"
            booking.hold_expires_at = None
            booking.payment.status = "cancelled"
            await db.commit()
            await release_slot_hold(redis, hold_keys)
            return {"status": "expired"}

        booking.payment.status = "complete"
        booking.payment.paid_at = now_utc
        booking.status = "confirmed"
        booking.hold_expires_at = None

        # Create video room
        from app.services.video import create_room

        room_url = await create_room(
            booking_id=str(booking.id),
            scheduled_at=booking.scheduled_at,
            duration_minutes=booking.duration_minutes,
        )
        if room_url:
            booking.video_room_url = room_url

        # Spawn recurring child bookings (pre-confirmed, no extra payment)
        if booking.is_recurring and recurring_weeks > 1:
            from datetime import timedelta

            for week in range(1, recurring_weeks):
                child = Booking(
                    parent_id=booking.parent_id,
                    teacher_id=booking.teacher_id,
                    learner_id=booking.learner_id,
                    subject_id=booking.subject_id,
                    scheduled_at=booking.scheduled_at + timedelta(weeks=week),
                    duration_minutes=booking.duration_minutes,
                    hold_expires_at=None,
                    is_trial=False,
                    is_recurring=True,
                    recurring_booking_id=booking.id,
                    parent_notes=booking.parent_notes,
                    amount_cents=booking.amount_cents,
                    commission_cents=booking.commission_cents,
                    teacher_payout_cents=booking.teacher_payout_cents,
                    status="confirmed",
                )
                db.add(child)

        await db.commit()
        await release_slot_hold(redis, hold_keys)

        # Fire confirmation emails (after DB commit via Celery)
        from app.tasks.notifications import send_booking_confirmation

        send_booking_confirmation.apply_async(args=[str(booking.id)], countdown=5)
    elif payment_status in ("FAILED", "CANCELLED"):
        if booking.status != "pending_payment":
            return {"status": "ignored"}

        booking.payment.status = payment_status.lower()
        booking.status = "expired"
        booking.hold_expires_at = None
        await db.commit()
        await release_slot_hold(redis, hold_keys)

    return {"status": "ok"}
