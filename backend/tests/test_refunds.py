from datetime import UTC, datetime, timedelta

from app.services.refunds import (
    calculate_cancellation_outcome,
    calculate_no_show_outcome,
    payment_status_after_refund,
)


def test_teacher_cancellation_always_gets_full_refund() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=UTC)
    outcome = calculate_cancellation_outcome(
        actor_role="teacher",
        amount_cents=35_000,
        original_teacher_payout_cents=28_000,
        original_commission_cents=7_000,
        scheduled_at=now + timedelta(hours=1),
        cancelled_at=now,
    )

    assert outcome.refund_amount_cents == 35_000
    assert outcome.teacher_payout_cents == 0
    assert outcome.commission_cents == 0
    assert outcome.policy_code == "teacher_cancel_full_refund"


def test_parent_cancellation_over_24_hours_gets_full_refund() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=UTC)
    outcome = calculate_cancellation_outcome(
        actor_role="parent",
        amount_cents=35_000,
        original_teacher_payout_cents=28_000,
        original_commission_cents=7_000,
        scheduled_at=now + timedelta(hours=30),
        cancelled_at=now,
    )

    assert outcome.refund_amount_cents == 35_000
    assert outcome.teacher_payout_cents == 0
    assert outcome.commission_cents == 0
    assert outcome.policy_code == "parent_cancel_full_refund"


def test_parent_cancellation_between_2_and_24_hours_gets_half_refund() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=UTC)
    outcome = calculate_cancellation_outcome(
        actor_role="parent",
        amount_cents=35_000,
        original_teacher_payout_cents=28_000,
        original_commission_cents=7_000,
        scheduled_at=now + timedelta(hours=8),
        cancelled_at=now,
    )

    assert outcome.refund_amount_cents == 17_500
    assert outcome.teacher_payout_cents == 17_500
    assert outcome.commission_cents == 0
    assert outcome.policy_code == "parent_cancel_partial_refund"


def test_parent_cancellation_inside_2_hours_gets_no_refund() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=UTC)
    outcome = calculate_cancellation_outcome(
        actor_role="parent",
        amount_cents=35_000,
        original_teacher_payout_cents=28_000,
        original_commission_cents=7_000,
        scheduled_at=now + timedelta(minutes=90),
        cancelled_at=now,
    )

    assert outcome.refund_amount_cents == 0
    assert outcome.teacher_payout_cents == 28_000
    assert outcome.commission_cents == 7_000
    assert outcome.policy_code == "parent_cancel_no_refund"


def test_payment_status_after_refund_handles_partial_and_full() -> None:
    assert payment_status_after_refund(35_000, 0) == "complete"
    assert payment_status_after_refund(35_000, 17_500) == "partially_refunded"
    assert payment_status_after_refund(35_000, 35_000) == "refunded"


def test_teacher_reporting_parent_no_show_keeps_full_payout() -> None:
    outcome = calculate_no_show_outcome(
        reported_by_role="teacher",
        amount_cents=35_000,
        original_teacher_payout_cents=28_000,
        original_commission_cents=7_000,
    )

    assert outcome.refund_amount_cents == 0
    assert outcome.teacher_payout_cents == 28_000
    assert outcome.commission_cents == 7_000
    assert outcome.policy_code == "parent_no_show_no_refund"


def test_parent_reporting_teacher_no_show_gets_full_refund() -> None:
    outcome = calculate_no_show_outcome(
        reported_by_role="parent",
        amount_cents=35_000,
        original_teacher_payout_cents=28_000,
        original_commission_cents=7_000,
    )

    assert outcome.refund_amount_cents == 35_000
    assert outcome.teacher_payout_cents == 0
    assert outcome.commission_cents == 0
    assert outcome.policy_code == "teacher_no_show_full_refund"
