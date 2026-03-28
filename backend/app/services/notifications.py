from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationPreference
from app.models.user import User
from app.schemas.notification import NotificationPreferencesResponse, NotificationResponse

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
