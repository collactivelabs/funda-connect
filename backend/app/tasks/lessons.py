"""
Celery tasks for automatic lesson lifecycle management.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task
def expire_pending_booking_hold(booking_id: str) -> None:
    """Expire a single pending-payment booking hold if it is still outstanding."""

    async def _run() -> str | None:
        from uuid import UUID

        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import selectinload

        from app.core.config import settings
        from app.core.redis import get_redis
        from app.models.booking import Booking
        from app.services.scheduling import (
            booking_occurrence_starts,
            release_slot_hold,
            slot_lock_keys,
        )

        engine = create_async_engine(settings.DATABASE_URL, echo=False)

        try:
            async with AsyncSession(engine) as db:
                booking = await db.scalar(
                    select(Booking)
                    .where(Booking.id == UUID(booking_id))
                    .options(selectinload(Booking.payment))
                )
                if not booking or booking.status != "pending_payment":
                    return None

                now = datetime.now(UTC)
                if booking.hold_expires_at is None or booking.hold_expires_at > now:
                    return None

                recurring_weeks = 1
                if booking.payment and isinstance(booking.payment.gateway_metadata, dict):
                    recurring_weeks = int(
                        booking.payment.gateway_metadata.get("recurring_weeks") or 1
                    )

                booking.status = "expired"
                booking.hold_expires_at = None
                if booking.payment and booking.payment.status == "pending":
                    booking.payment.status = "cancelled"

                await db.commit()

                redis = await get_redis()
                await release_slot_hold(
                    redis,
                    slot_lock_keys(
                        booking.teacher_id,
                        booking_occurrence_starts(booking.scheduled_at, recurring_weeks),
                        booking.duration_minutes,
                    ),
                )
                return str(booking.id)
        finally:
            await engine.dispose()

    expired_booking_id = asyncio.run(_run())
    if expired_booking_id:
        logger.info("expire_pending_booking_hold.done", booking_id=expired_booking_id)


@celery_app.task
def expire_pending_booking_holds() -> None:
    """Sweep and expire any pending-payment booking holds past their expiry."""

    async def _run() -> list[str]:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.models.booking import Booking

        engine = create_async_engine(settings.DATABASE_URL, echo=False)

        try:
            async with AsyncSession(engine) as db:
                now = datetime.now(UTC)
                result = await db.scalars(
                    select(Booking.id).where(
                        Booking.status == "pending_payment",
                        Booking.hold_expires_at.is_not(None),
                        Booking.hold_expires_at <= now,
                    )
                )
                return [str(booking_id) for booking_id in result.all()]
        finally:
            await engine.dispose()

    expired_ids = asyncio.run(_run())
    for booking_id in expired_ids:
        expire_pending_booking_hold.delay(booking_id)

    if expired_ids:
        logger.info(
            "expire_pending_booking_holds.done", count=len(expired_ids), booking_ids=expired_ids
        )


@celery_app.task
def start_due_lessons() -> None:
    """Move confirmed lessons into in-progress once their start time has arrived."""

    async def _run() -> list[str]:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.models.booking import Booking
        from app.models.payment import Payment

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        started_ids: list[str] = []

        try:
            async with AsyncSession(engine) as db:
                now = datetime.now(UTC)

                rows = (
                    await db.execute(
                        select(Booking, Payment)
                        .join(Payment, Payment.booking_id == Booking.id)
                        .where(
                            Booking.status == "confirmed",
                            Payment.status == "complete",
                            Booking.scheduled_at <= now,
                        )
                    )
                ).all()

                for booking, _payment in rows:
                    lesson_end = booking.scheduled_at + timedelta(minutes=booking.duration_minutes)
                    if lesson_end.replace(tzinfo=UTC) <= now:
                        continue

                    booking.status = "in_progress"
                    booking.started_at = booking.started_at or now
                    started_ids.append(str(booking.id))

                await db.commit()
        finally:
            await engine.dispose()

        return started_ids

    started = asyncio.run(_run())
    if started:
        logger.info("start_due_lessons.done", count=len(started), booking_ids=started)


@celery_app.task
def auto_complete_lessons() -> None:
    """
    Mark elapsed live bookings as 'completed' once their scheduled time + duration
    has elapsed, then create pending Payout records for each.
    Runs every 15 minutes via Celery Beat.
    """

    async def _run():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.models.booking import Booking
        from app.models.payment import Payment, Payout

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        completed_ids = []

        try:
            async with AsyncSession(engine) as db:
                now = datetime.now(UTC)

                # Live bookings whose end time has passed
                result = await db.execute(
                    select(Booking, Payment)
                    .join(Payment, Payment.booking_id == Booking.id)
                    .outerjoin(Payout, Payout.payment_id == Payment.id)
                    .where(
                        Booking.status.in_(["confirmed", "in_progress"]),
                        Payment.status == "complete",
                        Payout.id.is_(None),
                    )
                )
                rows = result.all()

                for booking, payment in rows:
                    # Ensure the lesson end time is in the past
                    lesson_end = booking.scheduled_at + timedelta(minutes=booking.duration_minutes)
                    if lesson_end.replace(tzinfo=UTC) > now:
                        continue

                    booking.started_at = booking.started_at or booking.scheduled_at
                    booking.status = "completed"
                    booking.completed_at = booking.completed_at or now
                    payout = Payout(
                        teacher_id=booking.teacher_id,
                        payment_id=payment.id,
                        amount_cents=booking.teacher_payout_cents,
                        status="pending",
                    )
                    db.add(payout)
                    completed_ids.append(str(booking.id))

                await db.commit()
        finally:
            await engine.dispose()

        return completed_ids

    completed = asyncio.run(_run())
    if completed:
        logger.info("auto_complete_lessons.done", count=len(completed), booking_ids=completed)
