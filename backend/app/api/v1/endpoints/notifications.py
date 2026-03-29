from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_any_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationResponse,
    UpdateNotificationPreferencesRequest,
)
from app.services.notifications import (
    get_notification_preferences_snapshot,
    get_or_create_notification_preferences,
    notification_to_response,
    validate_notification_preference_channels,
)

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=50),
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = UUID(payload["sub"])
    notifications_result = await db.scalars(
        select(Notification)
        .where(Notification.user_id == user_id, Notification.channel == "in_app")
        .order_by(Notification.sent_at.desc(), Notification.created_at.desc())
        .limit(limit)
    )
    unread_count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.channel == "in_app",
            Notification.is_read == False,  # noqa: E712
        )
    )
    return NotificationListResponse(
        items=[notification_to_response(notification) for notification in notifications_result.all()],
        unread_count=unread_count or 0,
    )


@router.put("/read-all", response_model=MessageResponse)
async def mark_all_notifications_read(
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = UUID(payload["sub"])
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.channel == "in_app",
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    return MessageResponse(message=f"Marked {result.rowcount or 0} notification(s) as read.")


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    body: UpdateNotificationPreferencesRequest,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = UUID(payload["sub"])
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        validate_notification_preference_channels(
            user=user,
            sms_enabled=body.sms_enabled,
            push_enabled=body.push_enabled,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if detail in {
                "SMS delivery is not configured for this environment yet.",
                "Push notifications are not configured yet.",
            }
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc

    preferences = await get_or_create_notification_preferences(db, user_id)

    for field_name in ("in_app_enabled", "email_enabled", "sms_enabled", "push_enabled"):
        value = getattr(body, field_name)
        if value is not None:
            setattr(preferences, field_name, value)

    await db.flush()
    return NotificationPreferencesResponse(
        in_app_enabled=preferences.in_app_enabled,
        email_enabled=preferences.email_enabled,
        sms_enabled=preferences.sms_enabled,
        push_enabled=preferences.push_enabled,
    )


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_notification_preferences_snapshot(db, UUID(payload["sub"]))


@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    notification = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == UUID(payload["sub"]),
            Notification.channel == "in_app",
        )
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(UTC)
        await db.flush()

    return notification_to_response(notification)
