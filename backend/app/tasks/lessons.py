"""
Celery tasks for automatic lesson lifecycle management.
"""
import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task
def auto_complete_lessons() -> None:
    """
    Mark confirmed bookings as 'completed' once their scheduled time + duration
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

                # Confirmed bookings whose end time has passed
                result = await db.execute(
                    select(Booking, Payment)
                    .join(Payment, Payment.booking_id == Booking.id)
                    .outerjoin(Payout, Payout.payment_id == Payment.id)
                    .where(
                        Booking.status == "confirmed",
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

                    booking.status = "completed"
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
