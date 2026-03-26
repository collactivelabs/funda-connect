import hashlib
import urllib.parse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import get_db, require_any_user, require_parent
from app.models.booking import Booking
from app.models.curriculum import Subject
from app.models.parent import Learner, ParentProfile
from app.models.payment import Payment
from app.models.teacher import TeacherProfile
from app.schemas.booking import (
    BookingResponse,
    CancelBookingRequest,
    CreateBookingRequest,
    PayFastRedirectResponse,
)

router = APIRouter()

PAYFAST_SANDBOX_URL = "https://sandbox.payfast.co.za/eng/process"
PAYFAST_LIVE_URL = "https://www.payfast.co.za/eng/process"


def _payfast_url(booking: Booking, user_email: str) -> str:
    amount = booking.amount_cents / 100
    data = {
        "merchant_id": settings.PAYFAST_MERCHANT_ID or "10000100",
        "merchant_key": settings.PAYFAST_MERCHANT_KEY or "46f0cd694581a",
        "return_url": f"{settings.ALLOWED_ORIGINS[0]}/parent?booking={booking.id}&status=success",
        "cancel_url": f"{settings.ALLOWED_ORIGINS[0]}/parent?booking={booking.id}&status=cancelled",
        "notify_url": f"http://localhost:8000/api/v1/bookings/payfast/itn",
        "amount": f"{amount:.2f}",
        "item_name": f"FundaConnect Lesson - Booking {str(booking.id)[:8]}",
        "email_address": user_email,
        "m_payment_id": str(booking.id),
    }
    if settings.PAYFAST_PASSPHRASE:
        data["passphrase"] = settings.PAYFAST_PASSPHRASE

    param_string = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in data.items())
    data["signature"] = hashlib.md5(param_string.encode()).hexdigest()  # noqa: S324

    base = PAYFAST_SANDBOX_URL if settings.PAYFAST_SANDBOX else PAYFAST_LIVE_URL
    return f"{base}?{urllib.parse.urlencode(data)}"


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
        select(TeacherProfile).where(TeacherProfile.id == body.teacher_id)
    )
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.verification_status != "verified":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Teacher is not verified")
    if not teacher.hourly_rate_cents:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Teacher has not set a rate")

    # Price calculation
    amount_cents = int(teacher.hourly_rate_cents * body.duration_minutes / 60)
    commission_cents = int(amount_cents * settings.PLATFORM_COMMISSION_RATE)
    payout_cents = amount_cents - commission_cents

    booking = Booking(
        parent_id=parent_profile.id,
        teacher_id=body.teacher_id,
        learner_id=body.learner_id,
        subject_id=body.subject_id,
        scheduled_at=body.scheduled_at,
        duration_minutes=body.duration_minutes,
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
        gateway_metadata={"recurring_weeks": body.recurring_weeks} if body.recurring_weeks else None,
    )
    db.add(payment)

    payment_url = _payfast_url(booking, payload["email"])
    return PayFastRedirectResponse(
        booking_id=booking.id,
        payment_url=payment_url,
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

    user_id = UUID(payload["sub"])
    role = payload.get("role")

    if role == "parent":
        profile = await db.scalar(
            select(ParentProfile).where(ParentProfile.user_id == user_id)
        )
        if not profile or booking.parent_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        profile = await db.scalar(
            select(TeacherProfile).where(TeacherProfile.user_id == user_id)
        )
        if not profile or booking.teacher_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return booking


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
    body: CancelBookingRequest,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a booking. Only pending_payment or confirmed bookings can be cancelled."""
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.status not in ("pending_payment", "confirmed"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot cancel a booking with status '{booking.status}'",
        )

    room_url = booking.video_room_url
    booking.status = "cancelled"
    booking.cancellation_reason = body.reason
    booking.video_room_url = None

    # Best-effort room cleanup (fire-and-forget, don't block the response)
    if room_url:
        import asyncio
        from app.services.video import delete_room
        room_name = room_url.rstrip("/").split("/")[-1]
        asyncio.create_task(delete_room(room_name))

    return booking


def _verify_payfast_signature(data: dict) -> bool:
    """Verify the PayFast ITN signature against the posted data."""
    received_sig = data.get("signature", "")
    # Build parameter string from all fields except signature, preserving order
    fields = {k: v for k, v in data.items() if k != "signature"}
    param_string = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in fields.items())
    if settings.PAYFAST_PASSPHRASE:
        param_string += f"&passphrase={urllib.parse.quote_plus(settings.PAYFAST_PASSPHRASE)}"
    expected = hashlib.md5(param_string.encode()).hexdigest()  # noqa: S324
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

    if booking.payment:
        booking.payment.gateway_payment_id = pf_payment_id
        booking.payment.gateway_metadata = data

        if payment_status == "COMPLETE":
            booking.payment.status = "complete"
            booking.payment.gateway_metadata = {
                **(booking.payment.gateway_metadata or {}),
                **data,
            }
            booking.status = "confirmed"

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
            recurring_weeks = (booking.payment.gateway_metadata or {}).get("recurring_weeks")
            if booking.is_recurring and recurring_weeks and recurring_weeks > 1:
                from datetime import timedelta
                for week in range(1, recurring_weeks):
                    child = Booking(
                        parent_id=booking.parent_id,
                        teacher_id=booking.teacher_id,
                        learner_id=booking.learner_id,
                        subject_id=booking.subject_id,
                        scheduled_at=booking.scheduled_at + timedelta(weeks=week),
                        duration_minutes=booking.duration_minutes,
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

            # Fire confirmation emails (after DB commit via Celery)
            from app.tasks.notifications import send_booking_confirmation
            send_booking_confirmation.apply_async(args=[str(booking.id)], countdown=5)
        elif payment_status in ("FAILED", "CANCELLED"):
            booking.payment.status = payment_status.lower()

    return {"status": "ok"}
