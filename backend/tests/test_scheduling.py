from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.core.config import settings
from app.models.booking import AvailabilitySlot
from app.services.scheduling import (
    booking_blocks_time,
    booking_hold_expires_at,
    booking_occurrence_starts,
    is_within_weekly_availability,
    slot_conflicts_with_bookings,
    slot_lock_keys,
)


def test_booking_hold_expires_at_uses_configured_hold_window():
    now = datetime(2026, 3, 28, 10, 0, tzinfo=UTC)

    hold_until = booking_hold_expires_at(now)

    assert hold_until == now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES)


def test_booking_occurrence_starts_generates_weekly_recurring_dates():
    start_at = datetime(2026, 3, 30, 7, 0, tzinfo=UTC)

    occurrences = booking_occurrence_starts(start_at, recurring_weeks=3)

    assert occurrences == [
        datetime(2026, 3, 30, 7, 0, tzinfo=UTC),
        datetime(2026, 4, 6, 7, 0, tzinfo=UTC),
        datetime(2026, 4, 13, 7, 0, tzinfo=UTC),
    ]


def test_slot_lock_keys_split_duration_into_30_minute_segments():
    teacher_id = uuid4()
    occurrence_start = datetime(2026, 3, 30, 7, 0, tzinfo=UTC)

    keys = slot_lock_keys(teacher_id, [occurrence_start], duration_minutes=90)

    assert keys == [
        f"slot_hold:{teacher_id}:2026-03-30T07:00:00+00:00",
        f"slot_hold:{teacher_id}:2026-03-30T07:30:00+00:00",
        f"slot_hold:{teacher_id}:2026-03-30T08:00:00+00:00",
    ]


def test_is_within_weekly_availability_accepts_matching_aligned_slot():
    slot = AvailabilitySlot(
        teacher_id=uuid4(),
        day_of_week=0,
        start_time="09:00",
        end_time="12:00",
        is_active=True,
    )

    assert is_within_weekly_availability(
        [slot],
        datetime(2026, 3, 30, 7, 0, tzinfo=UTC),
        duration_minutes=60,
    )


def test_is_within_weekly_availability_rejects_misaligned_or_out_of_range_slots():
    slot = AvailabilitySlot(
        teacher_id=uuid4(),
        day_of_week=0,
        start_time="09:00",
        end_time="12:00",
        is_active=True,
    )

    assert not is_within_weekly_availability(
        [slot],
        datetime(2026, 3, 30, 7, 15, tzinfo=UTC),
        duration_minutes=60,
    )
    assert not is_within_weekly_availability(
        [slot],
        datetime(2026, 3, 30, 10, 0, tzinfo=UTC),
        duration_minutes=60,
    )


def test_booking_blocks_time_only_while_pending_hold_is_active():
    hold_expires_at = datetime(2026, 3, 30, 8, 0, tzinfo=UTC)
    pending_booking = SimpleNamespace(status="pending_payment", hold_expires_at=hold_expires_at)
    confirmed_booking = SimpleNamespace(status="confirmed", hold_expires_at=None)

    assert booking_blocks_time(pending_booking, datetime(2026, 3, 30, 7, 45, tzinfo=UTC))
    assert not booking_blocks_time(pending_booking, datetime(2026, 3, 30, 8, 1, tzinfo=UTC))
    assert booking_blocks_time(confirmed_booking, datetime(2026, 3, 30, 8, 1, tzinfo=UTC))


def test_slot_conflicts_with_bookings_ignores_expired_pending_holds():
    occurrence_start = datetime(2026, 3, 30, 7, 0, tzinfo=UTC)
    now = datetime(2026, 3, 30, 8, 30, tzinfo=UTC)
    expired_pending = SimpleNamespace(
        id=uuid4(),
        status="pending_payment",
        hold_expires_at=datetime(2026, 3, 30, 8, 0, tzinfo=UTC),
        scheduled_at=occurrence_start,
        duration_minutes=60,
    )
    confirmed = SimpleNamespace(
        id=uuid4(),
        status="confirmed",
        hold_expires_at=None,
        scheduled_at=occurrence_start,
        duration_minutes=60,
    )

    assert not slot_conflicts_with_bookings([expired_pending], [occurrence_start], 60, now_utc=now)
    assert slot_conflicts_with_bookings([confirmed], [occurrence_start], 60, now_utc=now)
