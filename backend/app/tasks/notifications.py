import asyncio

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_verification_message(
    self,
    to: str,
    first_name: str,
    verify_url: str,
) -> None:
    try:
        from app.services.email import email_verification_link

        email_verification_link(to=to, first_name=first_name, verify_url=verify_url)
        logger.info("send_email_verification_message.done", to=to)
    except Exception as exc:
        logger.error("send_email_verification_message.error", to=to, error=str(exc))
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_message(
    self,
    to: str,
    first_name: str,
    reset_url: str,
) -> None:
    try:
        from app.services.email import password_reset_link

        password_reset_link(to=to, first_name=first_name, reset_url=reset_url)
        logger.info("send_password_reset_message.done", to=to)
    except Exception as exc:
        logger.error("send_password_reset_message.error", to=to, error=str(exc))
        raise self.retry(exc=exc) from exc


async def _get_db():
    """Yield a throwaway async session for use inside Celery workers."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


async def _load_booking_data(booking_id: str):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from app.core.config import settings
    from app.models.booking import Booking
    from app.models.curriculum import Subject
    from app.models.parent import ParentProfile
    from app.models.teacher import TeacherProfile
    from app.models.user import User

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with AsyncSession(engine) as db:
            booking = await db.get(Booking, booking_id)
            if not booking:
                return None
            parent_profile = await db.get(ParentProfile, booking.parent_id)
            teacher_profile = await db.get(TeacherProfile, booking.teacher_id)
            subject = await db.get(Subject, booking.subject_id)
            if not parent_profile or not teacher_profile:
                return None
            parent_user = await db.get(User, parent_profile.user_id)
            teacher_user = await db.get(User, teacher_profile.user_id)
            if not parent_user or not teacher_user:
                return None
            return {
                "booking": booking,
                "parent_user": parent_user,
                "teacher_user": teacher_user,
                "subject_name": subject.name if subject else "Lesson",
            }
    finally:
        await engine.dispose()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_confirmation(self, booking_id: str) -> None:
    """Send confirmation emails to both parent and teacher after payment."""
    try:
        from app.services.email import booking_confirmation_parent, booking_confirmation_teacher

        data = asyncio.run(_load_booking_data(booking_id))
        if not data:
            logger.warning("send_booking_confirmation.not_found", booking_id=booking_id)
            return

        booking = data["booking"]
        parent_user = data["parent_user"]
        teacher_user = data["teacher_user"]
        subject_name = data["subject_name"]
        scheduled = booking.scheduled_at.strftime("%A, %-d %B %Y at %H:%M SAST")

        booking_confirmation_parent(
            to=parent_user.email,
            parent_name=parent_user.first_name,
            teacher_name=f"{teacher_user.first_name} {teacher_user.last_name}",
            subject_name=subject_name,
            scheduled_at=scheduled,
            duration_minutes=booking.duration_minutes,
            amount_cents=booking.amount_cents,
            booking_id=str(booking.id),
        )
        booking_confirmation_teacher(
            to=teacher_user.email,
            teacher_name=teacher_user.first_name,
            parent_name=f"{parent_user.first_name} {parent_user.last_name}",
            subject_name=subject_name,
            scheduled_at=scheduled,
            duration_minutes=booking.duration_minutes,
            payout_cents=booking.teacher_payout_cents,
        )

        logger.info("send_booking_confirmation.done", booking_id=booking_id)
    except Exception as exc:
        logger.error("send_booking_confirmation.error", booking_id=booking_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def notify_teacher_verification_result(self, teacher_id: str, new_status: str, notes: str | None = None) -> None:
    """Notify teacher of verification approval or rejection."""
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from app.core.config import settings
        from app.models.teacher import TeacherProfile
        from app.models.user import User
        from app.services.email import verification_approved, verification_rejected

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                teacher = await db.get(TeacherProfile, teacher_id)
                if not teacher:
                    return
                user = await db.get(User, teacher.user_id)
                if not user:
                    return
                if new_status == "verified":
                    verification_approved(to=user.email, teacher_name=user.first_name)
                elif new_status in ("rejected", "suspended"):
                    verification_rejected(to=user.email, teacher_name=user.first_name, notes=notes)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info("notify_teacher_verification_result.done", teacher_id=teacher_id, status=new_status)
    except Exception as exc:
        logger.error("notify_teacher_verification_result.error", teacher_id=teacher_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def notify_admin_verification_submitted(self, teacher_id: str) -> None:
    """Alert admin team when a teacher uploads documents."""
    async def _run():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from app.core.config import settings
        from app.models.payment import VerificationDocument
        from app.models.teacher import TeacherProfile
        from app.models.user import User
        from app.services.email import verification_submitted_admin

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                teacher = await db.get(TeacherProfile, teacher_id)
                if not teacher:
                    return
                user = await db.get(User, teacher.user_id)
                if not user:
                    return
                result = await db.scalars(
                    select(VerificationDocument).where(VerificationDocument.teacher_id == teacher.id)
                )
                doc_count = len(result.all())
                verification_submitted_admin(
                    teacher_name=f"{user.first_name} {user.last_name}",
                    teacher_id=str(teacher.id),
                    document_count=doc_count,
                )
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info("notify_admin_verification_submitted.done", teacher_id=teacher_id)
    except Exception as exc:
        logger.error("notify_admin_verification_submitted.error", teacher_id=teacher_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_payout_notification(self, payout_id: str) -> None:
    """Notify teacher when their payout has been marked as paid."""
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from app.core.config import settings
        from app.models.payment import Payout
        from app.models.teacher import TeacherProfile
        from app.models.user import User
        from app.services.email import payout_processed

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                payout = await db.get(Payout, payout_id)
                if not payout:
                    return
                teacher = await db.get(TeacherProfile, payout.teacher_id)
                if not teacher:
                    return
                user = await db.get(User, teacher.user_id)
                if not user:
                    return
                payout_processed(
                    to=user.email,
                    teacher_name=user.first_name,
                    amount_cents=payout.amount_cents,
                    bank_reference=payout.bank_reference,
                )
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info("send_payout_notification.done", payout_id=payout_id)
    except Exception as exc:
        logger.error("send_payout_notification.error", payout_id=payout_id, error=str(exc))
        raise self.retry(exc=exc)
