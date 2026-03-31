from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import redis.asyncio as aioredis
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.booking import AvailabilitySlot, Booking

SAST = ZoneInfo("Africa/Johannesburg")
SLOT_STEP_MINUTES = 30
MAX_BOOKING_DURATION_MINUTES = 180
ACTIVE_BOOKING_STATUSES = {"confirmed", "in_progress", "completed", "reviewed"}


def normalize_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def booking_hold_expires_at(from_time: datetime | None = None) -> datetime:
    base = normalize_utc(from_time or datetime.now(UTC))
    return base + timedelta(minutes=settings.BOOKING_HOLD_MINUTES)


def booking_lead_cutoff(from_time: datetime | None = None) -> datetime:
    base = normalize_utc(from_time or datetime.now(UTC))
    return base + timedelta(minutes=settings.BOOKING_MIN_LEAD_MINUTES)


def booking_occurrence_starts(start_at: datetime, recurring_weeks: int = 1) -> list[datetime]:
    base = normalize_utc(start_at)
    total_weeks = max(recurring_weeks, 1)
    return [base + timedelta(weeks=week) for week in range(total_weeks)]


def occurrences_touch_blocked_dates(
    occurrence_starts: list[datetime],
    blocked_dates: set[date],
) -> bool:
    return any(
        normalize_utc(start).astimezone(SAST).date() in blocked_dates for start in occurrence_starts
    )


def slot_lock_keys(
    teacher_id: UUID,
    occurrence_starts: list[datetime],
    duration_minutes: int,
) -> list[str]:
    keys: set[str] = set()
    segment_count = duration_minutes // SLOT_STEP_MINUTES
    for occurrence_start in occurrence_starts:
        normalized_start = normalize_utc(occurrence_start)
        for segment in range(segment_count):
            segment_start = normalized_start + timedelta(minutes=SLOT_STEP_MINUTES * segment)
            keys.add(f"slot_hold:{teacher_id}:{segment_start.isoformat()}")
    return sorted(keys)


async def acquire_slot_hold(
    redis: aioredis.Redis,
    teacher_id: UUID,
    occurrence_starts: list[datetime],
    duration_minutes: int,
    hold_until: datetime,
) -> list[str] | None:
    keys = slot_lock_keys(teacher_id, occurrence_starts, duration_minutes)
    if not keys:
        return []

    ttl_seconds = max(int((normalize_utc(hold_until) - datetime.now(UTC)).total_seconds()), 1)
    acquired: list[str] = []

    for key in keys:
        if await redis.set(key, hold_until.isoformat(), nx=True, ex=ttl_seconds):
            acquired.append(key)
            continue

        if acquired:
            await redis.delete(*acquired)
        return None

    return keys


async def release_slot_hold(redis: aioredis.Redis, keys: list[str]) -> None:
    if keys:
        await redis.delete(*keys)


async def are_slot_keys_available(redis: aioredis.Redis, keys: list[str]) -> bool:
    if not keys:
        return True
    return all(value is None for value in await redis.mget(keys))


def is_duration_supported(duration_minutes: int) -> bool:
    return (
        30 <= duration_minutes <= MAX_BOOKING_DURATION_MINUTES
        and duration_minutes % SLOT_STEP_MINUTES == 0
    )


def is_slot_aligned(start_at: datetime) -> bool:
    local_start = normalize_utc(start_at).astimezone(SAST)
    return (
        local_start.minute in (0, 30) and local_start.second == 0 and local_start.microsecond == 0
    )


def is_within_weekly_availability(
    availability_slots: list[AvailabilitySlot],
    start_at: datetime,
    duration_minutes: int,
) -> bool:
    if not is_duration_supported(duration_minutes) or not is_slot_aligned(start_at):
        return False

    local_start = normalize_utc(start_at).astimezone(SAST)
    local_end = local_start + timedelta(minutes=duration_minutes)
    if local_start.date() != local_end.date():
        return False

    weekday = local_start.weekday()
    start_time = local_start.strftime("%H:%M")
    end_time = local_end.strftime("%H:%M")

    return any(
        slot.is_active
        and slot.day_of_week == weekday
        and slot.start_time <= start_time
        and end_time <= slot.end_time
        for slot in availability_slots
    )


def bookings_overlap(
    first_start: datetime,
    first_duration_minutes: int,
    second_start: datetime,
    second_duration_minutes: int,
) -> bool:
    first_start_utc = normalize_utc(first_start)
    first_end_utc = first_start_utc + timedelta(minutes=first_duration_minutes)
    second_start_utc = normalize_utc(second_start)
    second_end_utc = second_start_utc + timedelta(minutes=second_duration_minutes)
    return first_start_utc < second_end_utc and second_start_utc < first_end_utc


def booking_blocks_time(booking: Booking, now_utc: datetime) -> bool:
    if booking.status in ACTIVE_BOOKING_STATUSES:
        return True
    return (
        booking.status == "pending_payment"
        and booking.hold_expires_at is not None
        and normalize_utc(booking.hold_expires_at) > now_utc
    )


async def get_teacher_booking_conflicts(
    db: AsyncSession,
    teacher_id: UUID,
    range_start: datetime,
    range_end: datetime,
    now_utc: datetime | None = None,
) -> list[Booking]:
    now_utc = normalize_utc(now_utc or datetime.now(UTC))
    query_start = normalize_utc(range_start) - timedelta(minutes=MAX_BOOKING_DURATION_MINUTES)
    query_end = normalize_utc(range_end) + timedelta(minutes=MAX_BOOKING_DURATION_MINUTES)

    result = await db.scalars(
        select(Booking).where(
            Booking.teacher_id == teacher_id,
            Booking.scheduled_at < query_end,
            Booking.scheduled_at >= query_start,
            or_(
                Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                and_(
                    Booking.status == "pending_payment",
                    Booking.hold_expires_at.is_not(None),
                    Booking.hold_expires_at > now_utc,
                ),
            ),
        )
    )
    return result.all()


def slot_conflicts_with_bookings(
    conflicts: list[Booking],
    occurrence_starts: list[datetime],
    duration_minutes: int,
    now_utc: datetime | None = None,
    ignore_booking_id: UUID | None = None,
) -> bool:
    now_utc = normalize_utc(now_utc or datetime.now(UTC))

    for conflict in conflicts:
        if ignore_booking_id and conflict.id == ignore_booking_id:
            continue
        if not booking_blocks_time(conflict, now_utc):
            continue
        for occurrence_start in occurrence_starts:
            if bookings_overlap(
                occurrence_start,
                duration_minutes,
                conflict.scheduled_at,
                conflict.duration_minutes,
            ):
                return True
    return False


def local_datetime(date_value: date, hhmm: str) -> datetime:
    parsed_time = time.fromisoformat(hhmm)
    return datetime.combine(date_value, parsed_time, tzinfo=SAST)


def format_date_label(date_value: date) -> str:
    return date_value.strftime("%a, %d %b")


def format_time_label(start_at: datetime, end_at: datetime) -> str:
    local_start = normalize_utc(start_at).astimezone(SAST)
    local_end = normalize_utc(end_at).astimezone(SAST)
    return f"{local_start.strftime('%H:%M')} - {local_end.strftime('%H:%M')}"
