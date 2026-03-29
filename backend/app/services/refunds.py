from dataclasses import dataclass
from datetime import datetime

from app.models.booking import Booking


FULL_REFUND_THRESHOLD_HOURS = 24
NO_REFUND_THRESHOLD_HOURS = 2


@dataclass(frozen=True)
class CancellationOutcome:
    refund_amount_cents: int
    teacher_payout_cents: int
    commission_cents: int
    policy_code: str


def payment_status_after_refund(payment_amount_cents: int, refund_amount_cents: int) -> str:
    if refund_amount_cents <= 0:
        return "complete"
    if refund_amount_cents >= payment_amount_cents:
        return "refunded"
    return "partially_refunded"


def calculate_cancellation_outcome(
    *,
    actor_role: str,
    amount_cents: int,
    original_teacher_payout_cents: int,
    original_commission_cents: int,
    scheduled_at: datetime,
    cancelled_at: datetime,
) -> CancellationOutcome:
    if actor_role == "teacher":
        return CancellationOutcome(
            refund_amount_cents=amount_cents,
            teacher_payout_cents=0,
            commission_cents=0,
            policy_code="teacher_cancel_full_refund",
        )

    if actor_role != "parent":
        raise ValueError("actor_role must be parent or teacher")

    hours_before_start = (scheduled_at - cancelled_at).total_seconds() / 3600

    if hours_before_start > FULL_REFUND_THRESHOLD_HOURS:
        return CancellationOutcome(
            refund_amount_cents=amount_cents,
            teacher_payout_cents=0,
            commission_cents=0,
            policy_code="parent_cancel_full_refund",
        )

    if hours_before_start > NO_REFUND_THRESHOLD_HOURS:
        refund_amount = amount_cents // 2
        return CancellationOutcome(
            refund_amount_cents=refund_amount,
            teacher_payout_cents=amount_cents - refund_amount,
            commission_cents=0,
            policy_code="parent_cancel_partial_refund",
        )

    return CancellationOutcome(
        refund_amount_cents=0,
        teacher_payout_cents=original_teacher_payout_cents,
        commission_cents=original_commission_cents,
        policy_code="parent_cancel_no_refund",
    )


def calculate_booking_cancellation_outcome(
    booking: Booking,
    actor_role: str,
    cancelled_at: datetime,
) -> CancellationOutcome:
    return calculate_cancellation_outcome(
        actor_role=actor_role,
        amount_cents=booking.amount_cents,
        original_teacher_payout_cents=booking.teacher_payout_cents,
        original_commission_cents=booking.commission_cents,
        scheduled_at=booking.scheduled_at,
        cancelled_at=cancelled_at,
    )


def calculate_no_show_outcome(
    *,
    reported_by_role: str,
    amount_cents: int,
    original_teacher_payout_cents: int,
    original_commission_cents: int,
) -> CancellationOutcome:
    if reported_by_role == "teacher":
        return CancellationOutcome(
            refund_amount_cents=0,
            teacher_payout_cents=original_teacher_payout_cents,
            commission_cents=original_commission_cents,
            policy_code="parent_no_show_no_refund",
        )

    if reported_by_role == "parent":
        return CancellationOutcome(
            refund_amount_cents=amount_cents,
            teacher_payout_cents=0,
            commission_cents=0,
            policy_code="teacher_no_show_full_refund",
        )

    raise ValueError("reported_by_role must be parent or teacher")
