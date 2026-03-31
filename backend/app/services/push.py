from __future__ import annotations

import importlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import PushSubscription


class PushConfigurationError(RuntimeError):
    pass


class PushDeliveryError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def web_push_configured() -> bool:
    return all(
        (
            settings.WEB_PUSH_PUBLIC_KEY.strip(),
            settings.WEB_PUSH_PRIVATE_KEY.strip(),
            settings.WEB_PUSH_SUBJECT.strip(),
        )
    )


def web_push_public_key() -> str | None:
    value = settings.WEB_PUSH_PUBLIC_KEY.strip()
    return value or None


def web_push_supported_response() -> dict[str, Any]:
    return {
        "configured": web_push_configured(),
        "public_key": web_push_public_key(),
    }


async def active_push_subscriptions_for_user(
    db: AsyncSession, user_id: UUID
) -> list[PushSubscription]:
    result = await db.scalars(
        select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.is_active == True,  # noqa: E712
        )
    )
    return result.all()


async def has_active_push_subscription(db: AsyncSession, user_id: UUID) -> bool:
    result = await db.scalar(
        select(PushSubscription.id).where(
            PushSubscription.user_id == user_id,
            PushSubscription.is_active == True,  # noqa: E712
        )
    )
    return result is not None


async def upsert_push_subscription(
    db: AsyncSession,
    *,
    user_id: UUID,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
    expiration_time: datetime | None,
    user_agent: str | None = None,
) -> PushSubscription:
    subscription = await db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    )
    if subscription is None:
        subscription = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
            expiration_time=expiration_time,
            user_agent=user_agent,
            is_active=True,
            last_used_at=datetime.now(UTC),
        )
        db.add(subscription)
    else:
        subscription.user_id = user_id
        subscription.p256dh_key = p256dh_key
        subscription.auth_key = auth_key
        subscription.expiration_time = expiration_time
        subscription.user_agent = user_agent
        subscription.is_active = True
        subscription.last_used_at = datetime.now(UTC)

    await db.flush()
    return subscription


async def deactivate_push_subscription(
    db: AsyncSession,
    *,
    endpoint: str,
    user_id: UUID | None = None,
) -> bool:
    statement = select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    if user_id is not None:
        statement = statement.where(PushSubscription.user_id == user_id)

    subscription = await db.scalar(statement)
    if subscription is None:
        return False

    subscription.is_active = False
    await db.flush()
    return True


async def deactivate_push_subscription_by_id(db: AsyncSession, subscription_id: UUID) -> None:
    subscription = await db.get(PushSubscription, subscription_id)
    if subscription is None:
        return
    subscription.is_active = False
    await db.flush()


async def send_web_push(
    subscription: PushSubscription,
    *,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not web_push_configured():
        raise PushConfigurationError("Push notifications are not configured")

    try:
        pywebpush = importlib.import_module("pywebpush")
    except ImportError as exc:
        raise PushConfigurationError(
            "pywebpush is not installed in the backend environment"
        ) from exc

    payload = {
        "title": title,
        "body": body,
        "url": data.get("url") if data else None,
        "data": data or {},
    }
    sub_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh_key,
            "auth": subscription.auth_key,
        },
    }
    if subscription.expiration_time is not None:
        sub_info["expirationTime"] = int(subscription.expiration_time.timestamp() * 1000)

    try:
        pywebpush.webpush(
            subscription_info=sub_info,
            data=pywebpush.json_encode(payload),
            vapid_private_key=settings.WEB_PUSH_PRIVATE_KEY,
            vapid_claims={"sub": settings.WEB_PUSH_SUBJECT},
        )
    except pywebpush.WebPushException as exc:  # type: ignore[attr-defined]
        status_code = getattr(exc.response, "status_code", None)
        raise PushDeliveryError(str(exc), status_code=status_code) from exc

    return {
        "endpoint": subscription.endpoint,
    }
