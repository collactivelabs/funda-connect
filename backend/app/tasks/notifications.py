import asyncio
from uuid import UUID

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


async def _record_delivery(
    db,
    *,
    user_id: UUID | str,
    notification_type: str,
    channel: str,
    status: str,
    title: str,
    body: str,
    recipient: str | None = None,
    provider: str | None = None,
    metadata: dict | None = None,
    error_message: str | None = None,
    notification_id: UUID | None = None,
):
    from app.services.notifications import record_notification_delivery

    await record_notification_delivery(
        db,
        user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
        notification_type=notification_type,
        channel=channel,
        status=status,
        title=title,
        body=body,
        recipient=recipient,
        provider=provider,
        metadata=metadata,
        error_message=error_message,
        notification_id=notification_id,
    )


def _queue_sms_delivery(
    *,
    user_id: UUID,
    to: str,
    title: str,
    body: str,
    event_type: str,
    metadata: dict | None = None,
) -> None:
    send_transactional_sms.apply_async(
        kwargs={
            "user_id": str(user_id),
            "to": to,
            "title": title,
            "body": body,
            "event_type": event_type,
            "metadata": metadata,
        }
    )


def _queue_push_delivery(
    *,
    user_id: UUID,
    title: str,
    body: str,
    event_type: str,
    metadata: dict | None = None,
) -> None:
    send_transactional_push.apply_async(
        kwargs={
            "user_id": str(user_id),
            "title": title,
            "body": body,
            "event_type": event_type,
            "metadata": metadata,
        }
    )


async def _handle_push_delivery_preference(
    db,
    *,
    user,
    title: str,
    body: str,
    event_type: str,
    metadata: dict | None = None,
) -> None:
    from app.services.notifications import notifications_enabled_for_channel
    from app.services.push import has_active_push_subscription

    if not await notifications_enabled_for_channel(db, user.id, channel="push"):
        await _record_delivery(
            db,
            user_id=user.id,
            notification_type=event_type,
            channel="push",
            status="skipped",
            title=title,
            body=body,
            provider="webpush",
            metadata=metadata,
            error_message="Channel disabled by user preferences.",
        )
        return

    if not await has_active_push_subscription(db, user.id):
        await _record_delivery(
            db,
            user_id=user.id,
            notification_type=event_type,
            channel="push",
            status="skipped",
            title=title,
            body=body,
            provider="webpush",
            metadata=metadata,
            error_message="No active push subscription.",
        )
        return

    _queue_push_delivery(
        user_id=user.id,
        title=title,
        body=body,
        event_type=event_type,
        metadata=metadata,
    )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_verification_message(
    self,
    user_id: str,
    to: str,
    first_name: str,
    verify_url: str,
) -> None:
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.services.email import email_verification_link

        title = "Verify your email"
        body = "Confirm your email address to activate your FundaConnect account."

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                try:
                    email_verification_link(to=to, first_name=first_name, verify_url=verify_url)
                    await _record_delivery(
                        db,
                        user_id=user_id,
                        notification_type="email_verification",
                        channel="email",
                        status="delivered",
                        title=title,
                        body=body,
                        recipient=to,
                        provider="smtp",
                    )
                    await db.commit()
                except Exception as exc:  # noqa: BLE001
                    await _record_delivery(
                        db,
                        user_id=user_id,
                        notification_type="email_verification",
                        channel="email",
                        status="failed",
                        title=title,
                        body=body,
                        recipient=to,
                        provider="smtp",
                        error_message=str(exc),
                    )
                    await db.commit()
                    raise
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info("send_email_verification_message.done", to=to)
    except Exception as exc:
        logger.error("send_email_verification_message.error", to=to, error=str(exc))
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_message(
    self,
    user_id: str,
    to: str,
    first_name: str,
    reset_url: str,
) -> None:
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.services.email import password_reset_link

        title = "Reset your password"
        body = "Use the secure link sent by FundaConnect to reset your password."

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                try:
                    password_reset_link(to=to, first_name=first_name, reset_url=reset_url)
                    await _record_delivery(
                        db,
                        user_id=user_id,
                        notification_type="password_reset",
                        channel="email",
                        status="delivered",
                        title=title,
                        body=body,
                        recipient=to,
                        provider="smtp",
                    )
                    await db.commit()
                except Exception as exc:  # noqa: BLE001
                    await _record_delivery(
                        db,
                        user_id=user_id,
                        notification_type="password_reset",
                        channel="email",
                        status="failed",
                        title=title,
                        body=body,
                        recipient=to,
                        provider="smtp",
                        error_message=str(exc),
                    )
                    await db.commit()
                    raise
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info("send_password_reset_message.done", to=to)
    except Exception as exc:
        logger.error("send_password_reset_message.error", to=to, error=str(exc))
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_transactional_sms(
    self,
    user_id: str,
    to: str,
    title: str,
    body: str,
    event_type: str,
    metadata: dict | None = None,
) -> None:
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.services.sms import SMSConfigurationError, send_sms_message

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                try:
                    result = await send_sms_message(to=to, message=body)
                    await _record_delivery(
                        db,
                        user_id=user_id,
                        notification_type=event_type,
                        channel="sms",
                        status="delivered",
                        title=title,
                        body=body,
                        recipient=result["recipient"],
                        provider=result["provider"],
                        metadata=metadata,
                    )
                    await db.commit()
                    logger.info(
                        "send_transactional_sms.done",
                        to=result["recipient"],
                        provider=result["provider"],
                        event_type=event_type,
                    )
                except SMSConfigurationError as exc:
                    await _record_delivery(
                        db,
                        user_id=user_id,
                        notification_type=event_type,
                        channel="sms",
                        status="skipped",
                        title=title,
                        body=body,
                        recipient=to,
                        metadata=metadata,
                        error_message=str(exc),
                    )
                    await db.commit()
                    logger.warning(
                        "send_transactional_sms.skipped",
                        to=to,
                        event_type=event_type,
                        reason=str(exc),
                    )
                except ValueError as exc:
                    await _record_delivery(
                        db,
                        user_id=user_id,
                        notification_type=event_type,
                        channel="sms",
                        status="skipped",
                        title=title,
                        body=body,
                        recipient=to,
                        metadata=metadata,
                        error_message=str(exc),
                    )
                    await db.commit()
                    logger.warning(
                        "send_transactional_sms.invalid_recipient",
                        to=to,
                        event_type=event_type,
                        reason=str(exc),
                    )
                except Exception as exc:  # noqa: BLE001
                    await _record_delivery(
                        db,
                        user_id=user_id,
                        notification_type=event_type,
                        channel="sms",
                        status="failed",
                        title=title,
                        body=body,
                        recipient=to,
                        metadata=metadata,
                        error_message=str(exc),
                    )
                    await db.commit()
                    logger.error(
                        "send_transactional_sms.error",
                        to=to,
                        event_type=event_type,
                        error=str(exc),
                    )
                    raise
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_transactional_push(
    self,
    user_id: str,
    title: str,
    body: str,
    event_type: str,
    metadata: dict | None = None,
) -> None:
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.services.push import (
            PushConfigurationError,
            PushDeliveryError,
            active_push_subscriptions_for_user,
            deactivate_push_subscription_by_id,
            send_web_push,
        )

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                subscriptions = await active_push_subscriptions_for_user(db, UUID(user_id))
                if not subscriptions:
                    await _record_delivery(
                        db,
                        user_id=user_id,
                        notification_type=event_type,
                        channel="push",
                        status="skipped",
                        title=title,
                        body=body,
                        provider="webpush",
                        metadata=metadata,
                        error_message="No active push subscription.",
                    )
                    await db.commit()
                    return

                for subscription in subscriptions:
                    delivery_metadata = {
                        **(metadata or {}),
                        "subscription_id": str(subscription.id),
                    }
                    recipient = f"subscription:{subscription.id}"

                    try:
                        await send_web_push(
                            subscription,
                            title=title,
                            body=body,
                            data=metadata or {},
                        )
                        await _record_delivery(
                            db,
                            user_id=user_id,
                            notification_type=event_type,
                            channel="push",
                            status="delivered",
                            title=title,
                            body=body,
                            recipient=recipient,
                            provider="webpush",
                            metadata=delivery_metadata,
                        )
                    except PushConfigurationError as exc:
                        await _record_delivery(
                            db,
                            user_id=user_id,
                            notification_type=event_type,
                            channel="push",
                            status="skipped",
                            title=title,
                            body=body,
                            recipient=recipient,
                            provider="webpush",
                            metadata=delivery_metadata,
                            error_message=str(exc),
                        )
                        await db.commit()
                        logger.warning(
                            "send_transactional_push.skipped",
                            user_id=user_id,
                            event_type=event_type,
                            reason=str(exc),
                        )
                        return
                    except PushDeliveryError as exc:
                        if exc.status_code in {404, 410}:
                            await deactivate_push_subscription_by_id(db, subscription.id)
                        await _record_delivery(
                            db,
                            user_id=user_id,
                            notification_type=event_type,
                            channel="push",
                            status="failed",
                            title=title,
                            body=body,
                            recipient=recipient,
                            provider="webpush",
                            metadata=delivery_metadata,
                            error_message=str(exc),
                        )
                        logger.warning(
                            "send_transactional_push.delivery_failed",
                            user_id=user_id,
                            event_type=event_type,
                            subscription_id=str(subscription.id),
                            status_code=exc.status_code,
                            error=str(exc),
                        )
                    except Exception as exc:  # noqa: BLE001
                        await _record_delivery(
                            db,
                            user_id=user_id,
                            notification_type=event_type,
                            channel="push",
                            status="failed",
                            title=title,
                            body=body,
                            recipient=recipient,
                            provider="webpush",
                            metadata=delivery_metadata,
                            error_message=str(exc),
                        )
                        logger.error(
                            "send_transactional_push.error",
                            user_id=user_id,
                            event_type=event_type,
                            subscription_id=str(subscription.id),
                            error=str(exc),
                        )

                await db.commit()
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_confirmation(self, booking_id: str) -> None:
    """Send confirmation emails to both parent and teacher after payment."""

    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.models.booking import Booking
        from app.models.curriculum import Subject
        from app.models.parent import ParentProfile
        from app.models.teacher import TeacherProfile
        from app.models.user import User
        from app.services.email import booking_confirmation_parent, booking_confirmation_teacher
        from app.services.notifications import notifications_enabled_for_channel
        from app.services.sms import (
            build_booking_confirmation_parent_sms,
            build_booking_confirmation_teacher_sms,
        )

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                booking = await db.get(Booking, booking_id)
                if not booking:
                    logger.warning("send_booking_confirmation.not_found", booking_id=booking_id)
                    return

                parent_profile = await db.get(ParentProfile, booking.parent_id)
                teacher_profile = await db.get(TeacherProfile, booking.teacher_id)
                subject = await db.get(Subject, booking.subject_id)
                if not parent_profile or not teacher_profile:
                    logger.warning(
                        "send_booking_confirmation.participants_missing", booking_id=booking_id
                    )
                    return

                parent_user = await db.get(User, parent_profile.user_id)
                teacher_user = await db.get(User, teacher_profile.user_id)
                if not parent_user or not teacher_user:
                    logger.warning("send_booking_confirmation.users_missing", booking_id=booking_id)
                    return

                subject_name = subject.name if subject else "Lesson"
                scheduled = booking.scheduled_at.strftime("%A, %-d %B %Y at %H:%M SAST")
                scheduled_sms = booking.scheduled_at.strftime("%a %d %b %H:%M SAST")
                parent_title = "Lesson booking confirmed"
                parent_body = (
                    f"Your {subject_name} lesson with {teacher_user.first_name} "
                    f"{teacher_user.last_name} is confirmed for {scheduled}."
                )
                teacher_title = "New lesson booked"
                teacher_body = (
                    f"{parent_user.first_name} {parent_user.last_name} booked a {subject_name} "
                    f"lesson for {scheduled}."
                )

                if await notifications_enabled_for_channel(db, parent_user.id, channel="email"):
                    try:
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
                        await _record_delivery(
                            db,
                            user_id=parent_user.id,
                            notification_type="booking_confirmed",
                            channel="email",
                            status="delivered",
                            title=parent_title,
                            body=parent_body,
                            recipient=parent_user.email,
                            provider="smtp",
                        )
                    except Exception as exc:  # noqa: BLE001
                        await _record_delivery(
                            db,
                            user_id=parent_user.id,
                            notification_type="booking_confirmed",
                            channel="email",
                            status="failed",
                            title=parent_title,
                            body=parent_body,
                            recipient=parent_user.email,
                            provider="smtp",
                            error_message=str(exc),
                        )
                        await db.commit()
                        raise
                else:
                    await _record_delivery(
                        db,
                        user_id=parent_user.id,
                        notification_type="booking_confirmed",
                        channel="email",
                        status="skipped",
                        title=parent_title,
                        body=parent_body,
                        recipient=parent_user.email,
                        provider="smtp",
                        error_message="Channel disabled by user preferences.",
                    )

                if parent_user.phone and await notifications_enabled_for_channel(
                    db, parent_user.id, channel="sms"
                ):
                    _queue_sms_delivery(
                        user_id=parent_user.id,
                        to=parent_user.phone,
                        title=parent_title,
                        body=build_booking_confirmation_parent_sms(
                            teacher_name=f"{teacher_user.first_name} {teacher_user.last_name}",
                            subject_name=subject_name,
                            scheduled_at=scheduled_sms,
                            booking_id=str(booking.id),
                        ),
                        event_type="booking_confirmed",
                    )
                else:
                    await _record_delivery(
                        db,
                        user_id=parent_user.id,
                        notification_type="booking_confirmed",
                        channel="sms",
                        status="skipped",
                        title=parent_title,
                        body=build_booking_confirmation_parent_sms(
                            teacher_name=f"{teacher_user.first_name} {teacher_user.last_name}",
                            subject_name=subject_name,
                            scheduled_at=scheduled_sms,
                            booking_id=str(booking.id),
                        ),
                        recipient=parent_user.phone,
                        error_message=(
                            "No phone number on file."
                            if not parent_user.phone
                            else "Channel disabled by user preferences."
                        ),
                    )

                await _handle_push_delivery_preference(
                    db,
                    user=parent_user,
                    title=parent_title,
                    body=parent_body,
                    event_type="booking_confirmed",
                    metadata={
                        "booking_id": str(booking.id),
                        "url": "/parent",
                    },
                )

                if await notifications_enabled_for_channel(db, teacher_user.id, channel="email"):
                    try:
                        booking_confirmation_teacher(
                            to=teacher_user.email,
                            teacher_name=teacher_user.first_name,
                            parent_name=f"{parent_user.first_name} {parent_user.last_name}",
                            subject_name=subject_name,
                            scheduled_at=scheduled,
                            duration_minutes=booking.duration_minutes,
                            payout_cents=booking.teacher_payout_cents,
                        )
                        await _record_delivery(
                            db,
                            user_id=teacher_user.id,
                            notification_type="booking_confirmed",
                            channel="email",
                            status="delivered",
                            title=teacher_title,
                            body=teacher_body,
                            recipient=teacher_user.email,
                            provider="smtp",
                        )
                    except Exception as exc:  # noqa: BLE001
                        await _record_delivery(
                            db,
                            user_id=teacher_user.id,
                            notification_type="booking_confirmed",
                            channel="email",
                            status="failed",
                            title=teacher_title,
                            body=teacher_body,
                            recipient=teacher_user.email,
                            provider="smtp",
                            error_message=str(exc),
                        )
                        await db.commit()
                        raise
                else:
                    await _record_delivery(
                        db,
                        user_id=teacher_user.id,
                        notification_type="booking_confirmed",
                        channel="email",
                        status="skipped",
                        title=teacher_title,
                        body=teacher_body,
                        recipient=teacher_user.email,
                        provider="smtp",
                        error_message="Channel disabled by user preferences.",
                    )

                if teacher_user.phone and await notifications_enabled_for_channel(
                    db, teacher_user.id, channel="sms"
                ):
                    _queue_sms_delivery(
                        user_id=teacher_user.id,
                        to=teacher_user.phone,
                        title=teacher_title,
                        body=build_booking_confirmation_teacher_sms(
                            parent_name=f"{parent_user.first_name} {parent_user.last_name}",
                            subject_name=subject_name,
                            scheduled_at=scheduled_sms,
                        ),
                        event_type="booking_confirmed",
                    )
                else:
                    await _record_delivery(
                        db,
                        user_id=teacher_user.id,
                        notification_type="booking_confirmed",
                        channel="sms",
                        status="skipped",
                        title=teacher_title,
                        body=build_booking_confirmation_teacher_sms(
                            parent_name=f"{parent_user.first_name} {parent_user.last_name}",
                            subject_name=subject_name,
                            scheduled_at=scheduled_sms,
                        ),
                        recipient=teacher_user.phone,
                        error_message=(
                            "No phone number on file."
                            if not teacher_user.phone
                            else "Channel disabled by user preferences."
                        ),
                    )

                await _handle_push_delivery_preference(
                    db,
                    user=teacher_user,
                    title=teacher_title,
                    body=teacher_body,
                    event_type="booking_confirmed",
                    metadata={
                        "booking_id": str(booking.id),
                        "url": "/teacher",
                    },
                )

                await db.commit()
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info("send_booking_confirmation.done", booking_id=booking_id)
    except Exception as exc:
        logger.error("send_booking_confirmation.error", booking_id=booking_id, error=str(exc))
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def notify_teacher_verification_result(
    self, teacher_id: str, new_status: str, notes: str | None = None
) -> None:
    """Notify teacher of verification approval or rejection."""

    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.models.teacher import TeacherProfile
        from app.models.user import User
        from app.services.email import verification_approved, verification_rejected
        from app.services.notifications import notifications_enabled_for_channel
        from app.services.sms import build_verification_result_sms

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                teacher = await db.get(TeacherProfile, teacher_id)
                if not teacher:
                    return
                user = await db.get(User, teacher.user_id)
                if not user:
                    return
                title = "Verification update"
                status_label = {
                    "verified": "verified",
                    "rejected": "rejected",
                    "suspended": "suspended",
                }.get(new_status, new_status.replace("_", " "))
                body = f"Your verification status is now {status_label}."
                email_enabled = await notifications_enabled_for_channel(
                    db, user.id, channel="email"
                )
                if new_status == "verified":
                    if email_enabled:
                        try:
                            verification_approved(to=user.email, teacher_name=user.first_name)
                            await _record_delivery(
                                db,
                                user_id=user.id,
                                notification_type="teacher_verification_result",
                                channel="email",
                                status="delivered",
                                title=title,
                                body=body,
                                recipient=user.email,
                                provider="smtp",
                            )
                        except Exception as exc:  # noqa: BLE001
                            await _record_delivery(
                                db,
                                user_id=user.id,
                                notification_type="teacher_verification_result",
                                channel="email",
                                status="failed",
                                title=title,
                                body=body,
                                recipient=user.email,
                                provider="smtp",
                                error_message=str(exc),
                            )
                            await db.commit()
                            raise
                    else:
                        await _record_delivery(
                            db,
                            user_id=user.id,
                            notification_type="teacher_verification_result",
                            channel="email",
                            status="skipped",
                            title=title,
                            body=body,
                            recipient=user.email,
                            provider="smtp",
                            error_message="Channel disabled by user preferences.",
                        )
                elif new_status in ("rejected", "suspended"):
                    if email_enabled:
                        try:
                            verification_rejected(
                                to=user.email, teacher_name=user.first_name, notes=notes
                            )
                            await _record_delivery(
                                db,
                                user_id=user.id,
                                notification_type="teacher_verification_result",
                                channel="email",
                                status="delivered",
                                title=title,
                                body=body,
                                recipient=user.email,
                                provider="smtp",
                            )
                        except Exception as exc:  # noqa: BLE001
                            await _record_delivery(
                                db,
                                user_id=user.id,
                                notification_type="teacher_verification_result",
                                channel="email",
                                status="failed",
                                title=title,
                                body=body,
                                recipient=user.email,
                                provider="smtp",
                                error_message=str(exc),
                            )
                            await db.commit()
                            raise
                    else:
                        await _record_delivery(
                            db,
                            user_id=user.id,
                            notification_type="teacher_verification_result",
                            channel="email",
                            status="skipped",
                            title=title,
                            body=body,
                            recipient=user.email,
                            provider="smtp",
                            error_message="Channel disabled by user preferences.",
                        )
                if user.phone and await notifications_enabled_for_channel(
                    db, user.id, channel="sms"
                ):
                    _queue_sms_delivery(
                        user_id=user.id,
                        to=user.phone,
                        title=title,
                        body=build_verification_result_sms(status_label=status_label, notes=notes),
                        event_type="teacher_verification_result",
                    )
                else:
                    await _record_delivery(
                        db,
                        user_id=user.id,
                        notification_type="teacher_verification_result",
                        channel="sms",
                        status="skipped",
                        title=title,
                        body=build_verification_result_sms(status_label=status_label, notes=notes),
                        recipient=user.phone,
                        error_message=(
                            "No phone number on file."
                            if not user.phone
                            else "Channel disabled by user preferences."
                        ),
                    )
                await _handle_push_delivery_preference(
                    db,
                    user=user,
                    title=title,
                    body=body,
                    event_type="teacher_verification_result",
                    metadata={
                        "teacher_id": str(teacher.id),
                        "status": new_status,
                        "url": "/teacher",
                    },
                )
                await db.commit()
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info(
            "notify_teacher_verification_result.done", teacher_id=teacher_id, status=new_status
        )
    except Exception as exc:
        logger.error(
            "notify_teacher_verification_result.error", teacher_id=teacher_id, error=str(exc)
        )
        raise self.retry(exc=exc) from exc


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
                    select(VerificationDocument).where(
                        VerificationDocument.teacher_id == teacher.id
                    )
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
        logger.error(
            "notify_admin_verification_submitted.error", teacher_id=teacher_id, error=str(exc)
        )
        raise self.retry(exc=exc) from exc


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
        from app.services.notifications import notifications_enabled_for_channel
        from app.services.sms import build_payout_processed_sms

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
                title = "Payout processed"
                body = f"Your payout of {payout.amount_cents / 100:.2f} has been marked paid."
                if await notifications_enabled_for_channel(db, user.id, channel="email"):
                    try:
                        payout_processed(
                            to=user.email,
                            teacher_name=user.first_name,
                            amount_cents=payout.amount_cents,
                            bank_reference=payout.bank_reference,
                        )
                        await _record_delivery(
                            db,
                            user_id=user.id,
                            notification_type="payout_paid",
                            channel="email",
                            status="delivered",
                            title=title,
                            body=body,
                            recipient=user.email,
                            provider="smtp",
                        )
                    except Exception as exc:  # noqa: BLE001
                        await _record_delivery(
                            db,
                            user_id=user.id,
                            notification_type="payout_paid",
                            channel="email",
                            status="failed",
                            title=title,
                            body=body,
                            recipient=user.email,
                            provider="smtp",
                            error_message=str(exc),
                        )
                        await db.commit()
                        raise
                else:
                    await _record_delivery(
                        db,
                        user_id=user.id,
                        notification_type="payout_paid",
                        channel="email",
                        status="skipped",
                        title=title,
                        body=body,
                        recipient=user.email,
                        provider="smtp",
                        error_message="Channel disabled by user preferences.",
                    )
                if user.phone and await notifications_enabled_for_channel(
                    db, user.id, channel="sms"
                ):
                    _queue_sms_delivery(
                        user_id=user.id,
                        to=user.phone,
                        title=title,
                        body=build_payout_processed_sms(
                            amount_cents=payout.amount_cents,
                            bank_reference=payout.bank_reference,
                        ),
                        event_type="payout_paid",
                    )
                else:
                    await _record_delivery(
                        db,
                        user_id=user.id,
                        notification_type="payout_paid",
                        channel="sms",
                        status="skipped",
                        title=title,
                        body=build_payout_processed_sms(
                            amount_cents=payout.amount_cents,
                            bank_reference=payout.bank_reference,
                        ),
                        recipient=user.phone,
                        error_message=(
                            "No phone number on file."
                            if not user.phone
                            else "Channel disabled by user preferences."
                        ),
                    )
                await _handle_push_delivery_preference(
                    db,
                    user=user,
                    title=title,
                    body=body,
                    event_type="payout_paid",
                    metadata={
                        "payout_id": str(payout.id),
                        "url": "/teacher",
                    },
                )
                await db.commit()
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info("send_payout_notification.done", payout_id=payout_id)
    except Exception as exc:
        logger.error("send_payout_notification.error", payout_id=payout_id, error=str(exc))
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_refund_notification(self, refund_id: str) -> None:
    """Notify parent when a refund has been marked as processed."""

    async def _run():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import selectinload

        from app.core.config import settings
        from app.models.parent import ParentProfile
        from app.models.payment import Payment, Refund
        from app.models.user import User
        from app.services.email import refund_processed
        from app.services.notifications import notifications_enabled_for_channel
        from app.services.sms import build_refund_processed_sms

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine) as db:
                refund = await db.scalar(
                    select(Refund)
                    .where(Refund.id == refund_id)
                    .options(selectinload(Refund.payment).selectinload(Payment.booking))
                )
                if not refund:
                    return
                parent = await db.get(ParentProfile, refund.payment.booking.parent_id)
                if not parent:
                    return
                user = await db.get(User, parent.user_id)
                if not user:
                    return
                lesson_reference = str(refund.payment.booking.id)[:8].upper()
                title = "Refund processed"
                body = f"Your refund for lesson {lesson_reference} has been processed."
                if await notifications_enabled_for_channel(db, user.id, channel="email"):
                    try:
                        refund_processed(
                            to=user.email,
                            parent_name=user.first_name,
                            amount_cents=refund.amount_cents,
                            lesson_reference=lesson_reference,
                        )
                        await _record_delivery(
                            db,
                            user_id=user.id,
                            notification_type="refund_processed",
                            channel="email",
                            status="delivered",
                            title=title,
                            body=body,
                            recipient=user.email,
                            provider="smtp",
                        )
                    except Exception as exc:  # noqa: BLE001
                        await _record_delivery(
                            db,
                            user_id=user.id,
                            notification_type="refund_processed",
                            channel="email",
                            status="failed",
                            title=title,
                            body=body,
                            recipient=user.email,
                            provider="smtp",
                            error_message=str(exc),
                        )
                        await db.commit()
                        raise
                else:
                    await _record_delivery(
                        db,
                        user_id=user.id,
                        notification_type="refund_processed",
                        channel="email",
                        status="skipped",
                        title=title,
                        body=body,
                        recipient=user.email,
                        provider="smtp",
                        error_message="Channel disabled by user preferences.",
                    )
                if user.phone and await notifications_enabled_for_channel(
                    db, user.id, channel="sms"
                ):
                    _queue_sms_delivery(
                        user_id=user.id,
                        to=user.phone,
                        title=title,
                        body=build_refund_processed_sms(
                            amount_cents=refund.amount_cents,
                            lesson_reference=lesson_reference,
                        ),
                        event_type="refund_processed",
                    )
                else:
                    await _record_delivery(
                        db,
                        user_id=user.id,
                        notification_type="refund_processed",
                        channel="sms",
                        status="skipped",
                        title=title,
                        body=build_refund_processed_sms(
                            amount_cents=refund.amount_cents,
                            lesson_reference=lesson_reference,
                        ),
                        recipient=user.phone,
                        error_message=(
                            "No phone number on file."
                            if not user.phone
                            else "Channel disabled by user preferences."
                        ),
                    )
                await _handle_push_delivery_preference(
                    db,
                    user=user,
                    title=title,
                    body=body,
                    event_type="refund_processed",
                    metadata={
                        "refund_id": str(refund.id),
                        "payment_id": str(refund.payment_id),
                        "url": "/parent",
                    },
                )
                await db.commit()
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info("send_refund_notification.done", refund_id=refund_id)
    except Exception as exc:
        logger.error("send_refund_notification.error", refund_id=refund_id, error=str(exc))
        raise self.retry(exc=exc) from exc
