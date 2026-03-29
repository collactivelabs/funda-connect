import hashlib
import urllib.parse
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo
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
from app.models.payment import Dispute, Payment, Payout, Refund
from app.models.teacher import TeacherProfile
from app.services.prepaid_series import (
    build_child_series_metadata,
    build_root_series_metadata,
    checkout_amount_cents,
    recurring_weeks_from_metadata,
    series_total_amount_cents,
)
from app.services.notifications import create_in_app_notification
from app.services.audit import create_audit_log
from app.services.rate_limits import (
    BOOKING_MUTATION_RATE_LIMIT,
    build_rate_limit_identifier,
    enforce_rate_limit,
)
from app.services.reference_data import list_topics
from app.services.refunds import (
    calculate_booking_cancellation_outcome,
    calculate_no_show_outcome,
)
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
    CompleteBookingRequest,
    CreateBookingRequest,
    PayFastRedirectResponse,
    RaiseDisputeRequest,
    ReportNoShowRequest,
    RescheduleBookingRequest,
)

router = APIRouter()

PAYFAST_SANDBOX_URL = "https://sandbox.payfast.co.za/eng/process"
PAYFAST_LIVE_URL = "https://www.payfast.co.za/eng/process"
SAST = ZoneInfo("Africa/Johannesburg")


def _requested_recurring_weeks(body: CreateBookingRequest) -> int:
    return body.recurring_weeks if body.is_recurring and body.recurring_weeks else 1


def _lesson_time_label(value: datetime) -> str:
    return normalize_utc(value).astimezone(SAST).strftime("%a, %-d %b %Y at %H:%M SAST")


async def _booking_participant_user_ids(
    booking: Booking,
    db: AsyncSession,
) -> tuple[UUID | None, UUID | None]:
    parent_user_id = await db.scalar(
        select(ParentProfile.user_id).where(ParentProfile.id == booking.parent_id)
    )
    teacher_user_id = await db.scalar(
        select(TeacherProfile.user_id).where(TeacherProfile.id == booking.teacher_id)
    )
    return parent_user_id, teacher_user_id


async def _notify_booking_participants(
    booking: Booking,
    db: AsyncSession,
    *,
    parent_title: str,
    parent_body: str,
    teacher_title: str,
    teacher_body: str,
    notification_type: str,
    metadata: dict | None = None,
) -> None:
    parent_user_id, teacher_user_id = await _booking_participant_user_ids(booking, db)
    if parent_user_id:
        await create_in_app_notification(
            db,
            user_id=parent_user_id,
            notification_type=notification_type,
            title=parent_title,
            body=parent_body,
            metadata=metadata,
        )
    if teacher_user_id:
        await create_in_app_notification(
            db,
            user_id=teacher_user_id,
            notification_type=notification_type,
            title=teacher_title,
            body=teacher_body,
            metadata=metadata,
        )


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


def _payfast_form_data(booking: Booking, payment: Payment, user_email: str) -> dict[str, str]:
    amount = checkout_amount_cents(payment.amount_cents, payment.gateway_metadata) / 100
    recurring_weeks = recurring_weeks_from_metadata(payment.gateway_metadata)
    data = {
        "merchant_id": settings.PAYFAST_MERCHANT_ID or "10000100",
        "merchant_key": settings.PAYFAST_MERCHANT_KEY or "46f0cd694581a",
        "return_url": _payfast_parent_url(settings.PAYFAST_RETURN_URL, booking, "success"),
        "cancel_url": _payfast_parent_url(settings.PAYFAST_CANCEL_URL, booking, "cancelled"),
        "notify_url": _payfast_notify_url(),
        "email_address": user_email,
        "m_payment_id": str(booking.id),
        "amount": f"{amount:.2f}",
        "item_name": (
            f"FundaConnect {recurring_weeks}-Lesson Series - Booking {str(booking.id)[:8]}"
            if recurring_weeks > 1
            else f"FundaConnect Lesson - Booking {str(booking.id)[:8]}"
        ),
    }
    data["signature"] = _payfast_signature(data, settings.PAYFAST_PASSPHRASE)
    return data


def _upsert_refund(
    payment: Payment,
    *,
    db: AsyncSession,
    amount_cents: int,
    status_value: str,
    reason: str | None,
    requested_by_role: str,
    policy_code: str,
    notes: str,
) -> None:
    refund = payment.refund
    if refund is None:
        db.add(
            Refund(
                payment_id=payment.id,
                amount_cents=amount_cents,
                status=status_value,
                reason=reason,
                requested_by_role=requested_by_role,
                policy_code=policy_code,
                notes=notes,
            )
        )
        return

    refund.amount_cents = amount_cents
    refund.status = status_value
    refund.reason = reason
    refund.requested_by_role = requested_by_role
    refund.policy_code = policy_code
    refund.notes = notes


def _apply_confirmed_booking_cancellation(
    booking: Booking,
    *,
    reason: str | None,
    actor_role: str,
    now_utc: datetime,
    db: AsyncSession,
) -> None:
    if actor_role not in {"parent", "teacher"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only parents or teachers can cancel confirmed lessons",
        )

    payment = booking.payment
    if payment is None or payment.status != "complete":
        return

    outcome = calculate_booking_cancellation_outcome(booking, actor_role, now_utc)
    booking.teacher_payout_cents = outcome.teacher_payout_cents
    booking.commission_cents = outcome.commission_cents

    metadata = dict(payment.gateway_metadata or {})
    metadata["cancellation"] = {
        "policy_code": outcome.policy_code,
        "refund_amount_cents": outcome.refund_amount_cents,
        "teacher_payout_cents": outcome.teacher_payout_cents,
        "commission_cents": outcome.commission_cents,
        "cancelled_at": now_utc.isoformat(),
        "cancelled_by_role": actor_role,
    }
    payment.gateway_metadata = metadata

    if outcome.refund_amount_cents > 0:
        _upsert_refund(
            payment,
            db=db,
            amount_cents=outcome.refund_amount_cents,
            status_value="pending",
            reason=reason,
            requested_by_role=actor_role,
            policy_code=outcome.policy_code,
            notes="Process this refund manually in PayFast and then mark it refunded here.",
        )

    if outcome.teacher_payout_cents > 0 and payment.payout is None:
        db.add(
            Payout(
                teacher_id=booking.teacher_id,
                payment_id=payment.id,
                amount_cents=outcome.teacher_payout_cents,
                status="pending",
                notes=f"Created from cancellation policy: {outcome.policy_code}",
            )
        )


def _apply_booking_no_show(
    booking: Booking,
    *,
    reason: str | None,
    actor_role: str,
    now_utc: datetime,
    db: AsyncSession,
) -> None:
    if actor_role not in {"parent", "teacher"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only parents or teachers can report a no-show",
        )

    payment = booking.payment
    if payment is None or payment.status != "complete":
        return

    outcome = calculate_no_show_outcome(
        reported_by_role=actor_role,
        amount_cents=booking.amount_cents,
        original_teacher_payout_cents=booking.teacher_payout_cents,
        original_commission_cents=booking.commission_cents,
    )
    booking.teacher_payout_cents = outcome.teacher_payout_cents
    booking.commission_cents = outcome.commission_cents

    metadata = dict(payment.gateway_metadata or {})
    metadata["no_show"] = {
        "policy_code": outcome.policy_code,
        "refund_amount_cents": outcome.refund_amount_cents,
        "teacher_payout_cents": outcome.teacher_payout_cents,
        "commission_cents": outcome.commission_cents,
        "reported_at": now_utc.isoformat(),
        "reported_by_role": actor_role,
    }
    payment.gateway_metadata = metadata

    if outcome.refund_amount_cents > 0:
        _upsert_refund(
            payment,
            db=db,
            amount_cents=outcome.refund_amount_cents,
            status_value="pending",
            reason=reason,
            requested_by_role=actor_role,
            policy_code=outcome.policy_code,
            notes="Process this no-show refund manually in PayFast and then mark it refunded here.",
        )
        if payment.payout and payment.payout.status in {"pending", "processing"}:
            payment.payout.status = "failed"
            payment.payout.notes = f"Payout paused because the lesson was marked as {booking.status}."
    elif payment.payout is None:
        db.add(
            Payout(
                teacher_id=booking.teacher_id,
                payment_id=payment.id,
                amount_cents=outcome.teacher_payout_cents,
                status="pending",
                notes=f"Created from no-show policy: {outcome.policy_code}",
            )
        )


async def _refresh_booking_room(booking: Booking) -> None:
    from app.services.video import create_room, delete_room

    if booking.video_room_url:
        room_name = booking.video_room_url.rstrip("/").split("/")[-1]
        await delete_room(room_name)

    room_url = await create_room(
        booking_id=str(booking.id),
        scheduled_at=booking.scheduled_at,
        duration_minutes=booking.duration_minutes,
    )
    booking.video_room_url = room_url


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PayFastRedirectResponse)
async def create_booking(
    body: CreateBookingRequest,
    request: Request,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Parent creates a booking. Returns PayFast payment URL."""
    await enforce_rate_limit(
        request,
        rate_limit=BOOKING_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many booking requests. Please try again shortly.",
    )
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

        payment_metadata = None
        if recurring_weeks > 1:
            payment_metadata = build_root_series_metadata(booking.id, recurring_weeks)
            payment_metadata["series_total_amount_cents"] = series_total_amount_cents(
                amount_cents,
                recurring_weeks,
            )

        payment = Payment(
            booking_id=booking.id,
            gateway="payfast",
            amount_cents=amount_cents,
            status="pending",
            gateway_metadata=payment_metadata,
        )
        db.add(payment)
        await create_audit_log(
            db,
            action="booking.create",
            resource_type="booking",
            resource_id=booking.id,
            actor_user_id=UUID(payload["sub"]),
            actor_role=payload.get("role"),
            request=request,
            metadata={
                "teacher_id": booking.teacher_id,
                "learner_id": booking.learner_id,
                "subject_id": booking.subject_id,
                "scheduled_at": booking.scheduled_at,
                "duration_minutes": booking.duration_minutes,
                "is_trial": booking.is_trial,
                "is_recurring": booking.is_recurring,
                "recurring_weeks": recurring_weeks,
                "amount_cents": checkout_amount_cents(payment.amount_cents, payment.gateway_metadata),
            },
        )
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
    form_data = _payfast_form_data(booking, payment, payload["email"])
    return PayFastRedirectResponse(
        booking_id=booking.id,
        payment_url=payment_url,
        form_data=form_data,
        amount_cents=checkout_amount_cents(payment.amount_cents, payment.gateway_metadata),
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


@router.post("/{booking_id}/reschedule", response_model=BookingResponse)
async def reschedule_booking(
    booking_id: UUID,
    body: RescheduleBookingRequest,
    request: Request,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Move a future confirmed booking to another valid slot for the same teacher."""
    await enforce_rate_limit(
        request,
        rate_limit=BOOKING_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many booking changes. Please wait a moment and try again.",
    )
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(selectinload(Booking.payment))
    )
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    await _assert_booking_access(booking, payload, db)

    if payload.get("role") not in {"parent", "teacher"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only parents or teachers can reschedule lessons",
        )

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot reschedule a booking with status '{booking.status}'",
        )

    now_utc = datetime.now(UTC)
    current_start = normalize_utc(booking.scheduled_at)
    if now_utc >= current_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only future confirmed lessons can be rescheduled",
        )

    next_start = normalize_utc(body.scheduled_at)
    if next_start == current_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please choose a different time for this lesson",
        )

    if not is_slot_aligned(next_start):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bookings must start on 30-minute boundaries",
        )

    if next_start < booking_lead_cutoff(now_utc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Bookings must be made at least {settings.BOOKING_MIN_LEAD_MINUTES} minutes in advance",
        )

    teacher = await db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == booking.teacher_id)
        .options(selectinload(TeacherProfile.availability_slots))
    )
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    if not is_within_weekly_availability(
        teacher.availability_slots,
        next_start,
        booking.duration_minutes,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected time falls outside the teacher's availability",
        )

    conflicts = await get_teacher_booking_conflicts(
        db,
        teacher.id,
        range_start=next_start,
        range_end=next_start,
        now_utc=now_utc,
    )
    if slot_conflicts_with_bookings(
        conflicts,
        [next_start],
        booking.duration_minutes,
        now_utc,
        ignore_booking_id=booking.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That slot is no longer available. Please choose another time.",
        )

    redis = await get_redis()
    hold_keys = await acquire_slot_hold(
        redis,
        teacher.id,
        [next_start],
        booking.duration_minutes,
        booking_hold_expires_at(now_utc),
    )
    if hold_keys is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That slot is currently on hold. Please choose another time.",
        )

    try:
        original_start = booking.scheduled_at
        booking.scheduled_at = next_start
        await _refresh_booking_room(booking)
        await create_audit_log(
            db,
            action="booking.reschedule",
            resource_type="booking",
            resource_id=booking.id,
            actor_user_id=UUID(payload["sub"]),
            actor_role=payload.get("role"),
            request=request,
            metadata={
                "previous_scheduled_at": original_start,
                "new_scheduled_at": next_start,
                "teacher_id": booking.teacher_id,
            },
        )
        await db.commit()
    except Exception:
        await db.rollback()
        await release_slot_hold(redis, hold_keys)
        raise

    await release_slot_hold(redis, hold_keys)
    refreshed_booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking.id)
        .options(
            selectinload(Booking.learner),
            selectinload(Booking.subject),
        )
    )
    if refreshed_booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    await _notify_booking_participants(
        refreshed_booking,
        db,
        parent_title="Lesson rescheduled",
        parent_body=f"Your lesson has been moved to {_lesson_time_label(refreshed_booking.scheduled_at)}.",
        teacher_title="Lesson rescheduled",
        teacher_body=f"This lesson has been moved to {_lesson_time_label(refreshed_booking.scheduled_at)}.",
        notification_type="booking_rescheduled",
        metadata={"booking_id": str(refreshed_booking.id)},
    )
    return refreshed_booking


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
    body: CancelBookingRequest,
    request: Request,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a booking. Only pending_payment or confirmed bookings can be cancelled."""
    await enforce_rate_limit(
        request,
        rate_limit=BOOKING_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many booking changes. Please wait a moment and try again.",
    )
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.payment).selectinload(Payment.payout),
            selectinload(Booking.payment).selectinload(Payment.refund),
        )
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
    now_utc = datetime.now(UTC)
    actor_role = payload.get("role", "")

    booking.status = "cancelled"
    booking.cancellation_reason = body.reason
    booking.cancelled_at = now_utc
    booking.cancelled_by_role = actor_role
    booking.video_room_url = None
    booking.hold_expires_at = None

    if previous_status == "pending_payment" and booking.payment:
        booking.payment.status = "cancelled"
    elif previous_status == "confirmed":
        _apply_confirmed_booking_cancellation(
            booking,
            reason=body.reason,
            actor_role=actor_role,
            now_utc=now_utc,
            db=db,
        )

    recurring_weeks = 1
    if booking.payment:
        recurring_weeks = recurring_weeks_from_metadata(booking.payment.gateway_metadata)

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

    await _notify_booking_participants(
        booking,
        db,
        parent_title="Lesson cancelled",
        parent_body=f"This lesson scheduled for {_lesson_time_label(booking.scheduled_at)} has been cancelled.",
        teacher_title="Lesson cancelled",
        teacher_body=f"This lesson scheduled for {_lesson_time_label(booking.scheduled_at)} has been cancelled.",
        notification_type="booking_cancelled",
        metadata={"booking_id": str(booking.id), "cancelled_by_role": actor_role},
    )
    await create_audit_log(
        db,
        action="booking.cancel",
        resource_type="booking",
        resource_id=booking.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "previous_status": previous_status,
            "new_status": booking.status,
            "cancelled_by_role": actor_role,
            "scheduled_at": booking.scheduled_at,
            "has_reason": bool(body.reason),
        },
    )

    return booking


@router.post("/{booking_id}/complete", response_model=BookingResponse)
async def complete_booking(
    booking_id: UUID,
    body: CompleteBookingRequest,
    request: Request,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Teacher marks an in-progress lesson as completed."""
    await enforce_rate_limit(
        request,
        rate_limit=BOOKING_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many booking changes. Please wait a moment and try again.",
    )
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.learner),
            selectinload(Booking.subject),
            selectinload(Booking.teacher).selectinload(TeacherProfile.user),
        )
    )
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    # Only the assigned teacher can mark complete
    user_id = UUID(payload["sub"])
    profile = await db.scalar(
        select(TeacherProfile).where(TeacherProfile.user_id == user_id)
    )
    if not profile or booking.teacher_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if booking.status not in {"confirmed", "in_progress"}:
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

    if booking.started_at is None:
        booking.started_at = lesson_start

    if booking.learner is None or booking.subject is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Booking is missing learner or subject context",
        )

    allowed_topic_ids = {
        topic.id
        for topic in list_topics(
            subject=booking.subject.slug,
            grade=booking.learner.grade,
            curriculum=booking.learner.curriculum,
        )
    }
    invalid_topic_ids = [
        topic_id for topic_id in body.topics_covered if topic_id not in allowed_topic_ids
    ]
    if invalid_topic_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more selected topics are invalid for this lesson",
        )

    booking.lesson_notes = body.lesson_notes
    booking.topics_covered = body.topics_covered
    booking.status = "completed"
    booking.completed_at = now_utc
    await _notify_booking_participants(
        booking,
        db,
        parent_title="Lesson marked complete",
        parent_body=f"Your lesson from {_lesson_time_label(booking.scheduled_at)} has been marked complete.",
        teacher_title="Lesson marked complete",
        teacher_body=f"You marked the lesson from {_lesson_time_label(booking.scheduled_at)} as complete.",
        notification_type="booking_completed",
        metadata={"booking_id": str(booking.id)},
    )
    await create_audit_log(
        db,
        action="booking.complete",
        resource_type="booking",
        resource_id=booking.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "scheduled_at": booking.scheduled_at,
            "teacher_id": booking.teacher_id,
            "has_lesson_notes": bool(booking.lesson_notes),
            "topics_count": len(booking.topics_covered or []),
        },
    )
    await db.commit()
    refreshed_booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking.id)
        .options(
            selectinload(Booking.learner),
            selectinload(Booking.subject),
        )
    )
    if refreshed_booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return refreshed_booking


@router.post("/{booking_id}/report-no-show", response_model=BookingResponse)
async def report_booking_no_show(
    booking_id: UUID,
    body: ReportNoShowRequest,
    request: Request,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Parent or teacher reports that the other party missed the lesson."""
    await enforce_rate_limit(
        request,
        rate_limit=BOOKING_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many booking changes. Please wait a moment and try again.",
    )
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.payment).selectinload(Payment.payout),
            selectinload(Booking.payment).selectinload(Payment.refund),
            selectinload(Booking.learner),
            selectinload(Booking.subject),
        )
    )
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    await _assert_booking_access(booking, payload, db)

    actor_role = payload.get("role", "")
    if actor_role not in {"parent", "teacher"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only parents or teachers can report a no-show",
        )

    if booking.status not in {"confirmed", "in_progress"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot report a no-show for a booking with status '{booking.status}'",
        )

    now_utc = datetime.now(UTC)
    lesson_start = normalize_utc(booking.scheduled_at)
    grace_threshold = lesson_start + timedelta(minutes=settings.BOOKING_NO_SHOW_GRACE_MINUTES)
    if now_utc < grace_threshold:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"You can only report a no-show {settings.BOOKING_NO_SHOW_GRACE_MINUTES} "
                "minutes after the lesson start time"
            ),
        )

    room_url = booking.video_room_url
    booking.started_at = booking.started_at or lesson_start
    booking.completed_at = None
    booking.no_show_reported_at = now_utc
    booking.no_show_reported_by_role = actor_role
    booking.no_show_reason = body.reason
    booking.video_room_url = None
    booking.status = "no_show_teacher" if actor_role == "parent" else "no_show_parent"

    _apply_booking_no_show(
        booking,
        reason=body.reason,
        actor_role=actor_role,
        now_utc=now_utc,
        db=db,
    )

    await _notify_booking_participants(
        booking,
        db,
        parent_title="Lesson marked as no-show",
        parent_body=(
            "You reported the teacher as absent for this lesson."
            if actor_role == "parent"
            else "The teacher reported that the learner did not attend this lesson."
        ),
        teacher_title="Lesson marked as no-show",
        teacher_body=(
            "The parent reported that you did not attend this lesson."
            if actor_role == "parent"
            else "You reported that the learner did not attend this lesson."
        ),
        notification_type="booking_no_show",
        metadata={
            "booking_id": str(booking.id),
            "reported_by_role": actor_role,
            "status": booking.status,
        },
    )
    await create_audit_log(
        db,
        action="booking.no_show.report",
        resource_type="booking",
        resource_id=booking.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=actor_role,
        request=request,
        metadata={
            "reported_by_role": actor_role,
            "resulting_status": booking.status,
            "scheduled_at": booking.scheduled_at,
            "has_reason": bool(body.reason),
        },
    )
    await db.commit()

    if room_url:
        import asyncio
        from app.services.video import delete_room

        room_name = room_url.rstrip("/").split("/")[-1]
        asyncio.create_task(delete_room(room_name))

    refreshed_booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking.id)
        .options(
            selectinload(Booking.learner),
            selectinload(Booking.subject),
        )
    )
    if refreshed_booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return refreshed_booking


@router.post("/{booking_id}/dispute", response_model=BookingResponse)
async def raise_booking_dispute(
    booking_id: UUID,
    body: RaiseDisputeRequest,
    request: Request,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Raise a dispute on a booking after the lesson has started and before payout is paid."""
    await enforce_rate_limit(
        request,
        rate_limit=BOOKING_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many dispute attempts. Please wait a moment and try again.",
    )
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.payment).selectinload(Payment.payout),
            selectinload(Booking.dispute),
        )
    )
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    await _assert_booking_access(booking, payload, db)

    if booking.status in {"pending_payment", "cancelled", "expired", "disputed"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot dispute a booking with status '{booking.status}'",
        )
    if booking.dispute:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A dispute has already been raised for this booking",
        )

    now_utc = datetime.now(UTC)
    lesson_start = normalize_utc(booking.scheduled_at)
    if now_utc < lesson_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A dispute can only be raised after the lesson has started",
        )

    payout = booking.payment.payout if booking.payment else None
    if payout and payout.status == "paid":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This booking can no longer be disputed because the payout has already been processed",
        )

    if payout and payout.status in {"pending", "processing"}:
        payout.status = "failed"
        payout.notes = "Payout paused because the booking was marked as disputed."

    db.add(
        Dispute(
            booking_id=booking.id,
            raised_by_role=payload.get("role", "unknown"),
            reason=body.reason.strip(),
            status="open",
            original_booking_status=booking.status,
        )
    )
    booking.status = "disputed"
    await _notify_booking_participants(
        booking,
        db,
        parent_title="Dispute opened",
        parent_body="A dispute has been opened for this lesson. An admin will review it.",
        teacher_title="Dispute opened",
        teacher_body="A dispute has been opened for this lesson. An admin will review it.",
        notification_type="booking_disputed",
        metadata={"booking_id": str(booking.id), "raised_by_role": payload.get("role", "unknown")},
    )
    await create_audit_log(
        db,
        action="booking.dispute.raise",
        resource_type="booking",
        resource_id=booking.id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "raised_by_role": payload.get("role", "unknown"),
            "scheduled_at": booking.scheduled_at,
            "has_reason": bool(body.reason.strip()),
        },
    )
    return booking


@router.post("/{booking_id}/cancel-series", response_model=list[BookingResponse])
async def cancel_booking_series(
    booking_id: UUID,
    body: CancelBookingRequest,
    request: Request,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel all future confirmed bookings in a recurring series."""
    await enforce_rate_limit(
        request,
        rate_limit=BOOKING_MUTATION_RATE_LIMIT,
        identifier=build_rate_limit_identifier(request, payload["sub"]),
        detail="Too many booking changes. Please wait a moment and try again.",
    )
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.payment).selectinload(Payment.payout),
            selectinload(Booking.payment).selectinload(Payment.refund),
        )
    )
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if not booking.is_recurring:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Booking is not recurring"
        )

    # The root booking id is either this booking (if it is root) or its parent
    root_id = booking.recurring_booking_id or booking.id

    await _assert_booking_access(booking, payload, db)

    now = datetime.now(UTC)
    siblings = (
        await db.scalars(
            select(Booking)
            .where(
                Booking.status == "confirmed",
                Booking.scheduled_at > now,
                (Booking.id == root_id)
                | (Booking.recurring_booking_id == root_id),
            )
            .options(
                selectinload(Booking.payment).selectinload(Payment.payout),
                selectinload(Booking.payment).selectinload(Payment.refund),
            )
        )
    ).all()

    cancelled = []
    for sib in siblings:
        sib.status = "cancelled"
        sib.cancellation_reason = body.reason
        sib.cancelled_at = now
        sib.cancelled_by_role = payload.get("role", "")
        sib.hold_expires_at = None
        if sib.video_room_url:
            sib.video_room_url = None
        _apply_confirmed_booking_cancellation(
            sib,
            reason=body.reason,
            actor_role=payload.get("role", ""),
            now_utc=now,
            db=db,
        )
        cancelled.append(sib)

    await create_audit_log(
        db,
        action="booking.series.cancel",
        resource_type="booking_series",
        resource_id=root_id,
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "cancelled_count": len(cancelled),
            "has_reason": bool(body.reason),
            "booking_ids": [booking.id for booking in cancelled],
        },
    )
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

    recurring_weeks = recurring_weeks_from_metadata(booking.payment.gateway_metadata)
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
            await create_audit_log(
                db,
                action="payment.itn.expired",
                resource_type="booking",
                resource_id=booking.id,
                actor_role="system",
                request=request,
                metadata={"payment_status": payment_status, "pf_payment_id": pf_payment_id},
            )
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

        root_payment = booking.payment

        # Spawn recurring child bookings and allocate the prepaid series amount per lesson.
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
                await db.flush()

                db.add(
                    Payment(
                        booking_id=child.id,
                        gateway=root_payment.gateway,
                        gateway_payment_id=pf_payment_id,
                        amount_cents=booking.amount_cents,
                        status="complete",
                        paid_at=now_utc,
                        gateway_metadata=build_child_series_metadata(
                            root_booking_id=booking.id,
                            root_payment_id=root_payment.id,
                            recurring_weeks=recurring_weeks,
                            occurrence_index=week + 1,
                        ),
                    )
                )

        await create_audit_log(
            db,
            action="payment.itn.complete",
            resource_type="booking",
            resource_id=booking.id,
            actor_role="system",
            request=request,
            metadata={"payment_status": payment_status, "pf_payment_id": pf_payment_id},
        )
        await db.commit()
        await release_slot_hold(redis, hold_keys)

        await _notify_booking_participants(
            booking,
            db,
            parent_title="Booking confirmed",
            parent_body=f"Your lesson for {_lesson_time_label(booking.scheduled_at)} is confirmed.",
            teacher_title="New lesson confirmed",
            teacher_body=f"A lesson for {_lesson_time_label(booking.scheduled_at)} has been confirmed.",
            notification_type="booking_confirmed",
            metadata={"booking_id": str(booking.id)},
        )

        # Fire confirmation emails (after DB commit via Celery)
        from app.tasks.notifications import send_booking_confirmation

        send_booking_confirmation.apply_async(args=[str(booking.id)], countdown=5)
    elif payment_status in ("FAILED", "CANCELLED"):
        if booking.status != "pending_payment":
            return {"status": "ignored"}

        booking.payment.status = payment_status.lower()
        booking.status = "expired"
        booking.hold_expires_at = None
        await create_audit_log(
            db,
            action="payment.itn.failed",
            resource_type="booking",
            resource_id=booking.id,
            actor_role="system",
            request=request,
            metadata={"payment_status": payment_status, "pf_payment_id": pf_payment_id},
        )
        await db.commit()
        await release_slot_hold(redis, hold_keys)

    return {"status": "ok"}
