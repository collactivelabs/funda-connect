from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationDelivery, NotificationPreference
from app.models.user import User
from app.schemas.notification import (
    NotificationDeliveryResponse,
    NotificationPreferencesResponse,
    NotificationResponse,
)
from app.services.push import web_push_configured
from app.services.sms import normalize_phone_number, sms_provider_configured

_DEFAULT_PREFERENCES = {
    "in_app_enabled": True,
    "email_enabled": True,
    "sms_enabled": False,
    "push_enabled": False,
}


def notification_to_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        channel=notification.channel,
        title=notification.title,
        body=notification.body,
        metadata=notification.metadata_json,
        is_read=notification.is_read,
        sent_at=notification.sent_at,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


def notification_delivery_to_response(
    delivery: NotificationDelivery,
) -> NotificationDeliveryResponse:
    return NotificationDeliveryResponse(
        id=delivery.id,
        notification_id=delivery.notification_id,
        type=delivery.type,
        channel=delivery.channel,
        status=delivery.status,
        title=delivery.title,
        body=delivery.body,
        recipient=delivery.recipient,
        provider=delivery.provider,
        metadata=delivery.metadata_json,
        error_message=delivery.error_message,
        attempted_at=delivery.attempted_at,
        created_at=delivery.created_at,
    )


async def get_or_create_notification_preferences(
    db: AsyncSession, user_id: UUID
) -> NotificationPreference:
    preferences = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if preferences:
        return preferences

    preferences = NotificationPreference(user_id=user_id, **_DEFAULT_PREFERENCES)
    db.add(preferences)
    await db.flush()
    return preferences


async def get_notification_preferences_snapshot(
    db: AsyncSession, user_id: UUID
) -> NotificationPreferencesResponse:
    preferences = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if not preferences:
        return NotificationPreferencesResponse(**_DEFAULT_PREFERENCES)
    return NotificationPreferencesResponse(
        in_app_enabled=preferences.in_app_enabled,
        email_enabled=preferences.email_enabled,
        sms_enabled=preferences.sms_enabled,
        push_enabled=preferences.push_enabled,
    )


async def notifications_enabled_for_channel(
    db: AsyncSession,
    user_id: UUID,
    *,
    channel: str,
) -> bool:
    preferences = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if not preferences:
        return _DEFAULT_PREFERENCES.get(f"{channel}_enabled", False)

    if channel == "in_app":
        return preferences.in_app_enabled
    if channel == "email":
        return preferences.email_enabled
    if channel == "sms":
        return preferences.sms_enabled
    if channel == "push":
        return preferences.push_enabled
    return False


async def create_in_app_notification(
    db: AsyncSession,
    *,
    user_id: UUID,
    notification_type: str,
    title: str,
    body: str,
    metadata: dict | None = None,
) -> Notification | None:
    if not await notifications_enabled_for_channel(db, user_id, channel="in_app"):
        await record_notification_delivery(
            db,
            user_id=user_id,
            notification_type=notification_type,
            channel="in_app",
            status="skipped",
            title=title,
            body=body,
            metadata=metadata,
            error_message="Channel disabled by user preferences.",
        )
        return None

    notification = Notification(
        user_id=user_id,
        type=notification_type,
        channel="in_app",
        title=title,
        body=body,
        metadata_json=metadata,
        is_read=False,
        sent_at=datetime.now(UTC),
    )
    db.add(notification)
    await db.flush()
    await record_notification_delivery(
        db,
        user_id=user_id,
        notification_type=notification_type,
        channel="in_app",
        status="delivered",
        title=title,
        body=body,
        metadata=metadata,
        notification_id=notification.id,
        attempted_at=notification.sent_at,
    )
    return notification


async def create_in_app_notifications(
    db: AsyncSession,
    *,
    user_ids: list[UUID],
    notification_type: str,
    title: str,
    body: str,
    metadata: dict | None = None,
) -> None:
    for user_id in list(dict.fromkeys(user_ids)):
        await create_in_app_notification(
            db,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            metadata=metadata,
        )


async def list_admin_user_ids(db: AsyncSession) -> list[UUID]:
    result = await db.scalars(
        select(User.id).where(User.role == "admin", User.is_active == True)  # noqa: E712
    )
    return list(result.all())


async def list_notification_deliveries_for_user(
    db: AsyncSession,
    user_id: UUID,
    *,
    limit: int = 20,
) -> list[NotificationDelivery]:
    result = await db.scalars(
        select(NotificationDelivery)
        .where(NotificationDelivery.user_id == user_id)
        .order_by(NotificationDelivery.attempted_at.desc(), NotificationDelivery.created_at.desc())
        .limit(limit)
    )
    return result.all()


async def record_notification_delivery(
    db: AsyncSession,
    *,
    user_id: UUID,
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
    attempted_at: datetime | None = None,
) -> NotificationDelivery:
    delivery = NotificationDelivery(
        user_id=user_id,
        notification_id=notification_id,
        type=notification_type,
        channel=channel,
        status=status,
        title=title,
        body=body,
        recipient=recipient,
        provider=provider,
        metadata_json=metadata,
        error_message=error_message,
        attempted_at=attempted_at or datetime.now(UTC),
    )
    db.add(delivery)
    await db.flush()
    return delivery


def validate_notification_preference_channels(
    *,
    user: User,
    sms_enabled: bool | None = None,
    push_enabled: bool | None = None,
) -> None:
    if sms_enabled is True:
        if not sms_provider_configured():
            raise ValueError("SMS delivery is not configured for this environment yet.")
        if not user.phone:
            raise ValueError(
                "Add a phone number to your account before enabling SMS notifications."
            )
        try:
            normalize_phone_number(user.phone)
        except ValueError as exc:
            raise ValueError("Your saved phone number is invalid for SMS delivery.") from exc

    if push_enabled is True:
        if not web_push_configured():
            raise ValueError("Push notifications are not configured for this environment yet.")
