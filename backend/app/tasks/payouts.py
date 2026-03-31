import asyncio

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task
def process_weekly_payouts() -> None:
    """
    Create Payout records for all completed bookings that haven't been paid out yet.
    Runs weekly via Celery Beat.
    """

    async def _run():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.models.booking import Booking
        from app.models.payment import Payment, Payout

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        created = 0
        try:
            async with AsyncSession(engine) as db:
                rows = (
                    await db.execute(
                        select(Booking, Payment)
                        .join(Payment, Payment.booking_id == Booking.id)
                        .outerjoin(Payout, Payout.payment_id == Payment.id)
                        .where(
                            Booking.status.in_(["completed", "reviewed"]),
                            Payment.status == "complete",
                            Payout.id.is_(None),
                        )
                    )
                ).all()

                for booking, payment in rows:
                    payout = Payout(
                        teacher_id=booking.teacher_id,
                        payment_id=payment.id,
                        amount_cents=booking.teacher_payout_cents,
                        status="pending",
                    )
                    db.add(payout)
                    created += 1

                await db.commit()
        finally:
            await engine.dispose()
        return created

    logger.info("process_weekly_payouts.start")
    created = asyncio.run(_run())
    logger.info("process_weekly_payouts.done", payouts_created=created)
