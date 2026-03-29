from uuid import uuid4

import pytest

from app.models.notification import Notification, NotificationDelivery, NotificationPreference
from app.models.user import User
from app.services.notifications import (
    create_in_app_notification,
    get_notification_preferences_snapshot,
    get_or_create_notification_preferences,
    validate_notification_preference_channels,
)
from app.core.security import hash_password


class FakeSession:
    def __init__(self, preference: NotificationPreference | None = None):
        self.preference = preference
        self.notifications: list[Notification] = []
        self.deliveries: list[NotificationDelivery] = []

    async def scalar(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is NotificationPreference:
            return self.preference
        return None

    def add(self, instance):
        if isinstance(instance, NotificationPreference):
            self.preference = instance
        elif isinstance(instance, Notification):
            self.notifications.append(instance)
        elif isinstance(instance, NotificationDelivery):
            self.deliveries.append(instance)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_notification_preferences_default_to_enabled_channels():
    session = FakeSession()
    user_id = uuid4()

    snapshot = await get_notification_preferences_snapshot(session, user_id)
    preferences = await get_or_create_notification_preferences(session, user_id)

    assert snapshot.in_app_enabled is True
    assert snapshot.email_enabled is True
    assert snapshot.sms_enabled is False
    assert snapshot.push_enabled is False
    assert preferences.user_id == user_id


@pytest.mark.asyncio
async def test_in_app_notifications_respect_disabled_preference():
    user_id = uuid4()
    session = FakeSession(
        NotificationPreference(
            user_id=user_id,
            in_app_enabled=False,
            email_enabled=True,
            sms_enabled=False,
            push_enabled=False,
        )
    )

    notification = await create_in_app_notification(
        session,
        user_id=user_id,
        notification_type="booking_confirmed",
        title="Booking confirmed",
        body="Your lesson is confirmed.",
    )

    assert notification is None
    assert session.notifications == []
    assert session.deliveries[0].status == "skipped"
    assert session.deliveries[0].channel == "in_app"


@pytest.mark.asyncio
async def test_in_app_notifications_record_delivered_delivery():
    user_id = uuid4()
    session = FakeSession(
        NotificationPreference(
            user_id=user_id,
            in_app_enabled=True,
            email_enabled=True,
            sms_enabled=False,
            push_enabled=False,
        )
    )

    notification = await create_in_app_notification(
        session,
        user_id=user_id,
        notification_type="booking_confirmed",
        title="Booking confirmed",
        body="Your lesson is confirmed.",
    )

    assert notification is not None
    assert session.notifications[0].title == "Booking confirmed"
    assert session.deliveries[0].status == "delivered"
    assert session.deliveries[0].notification_id == notification.id


def _build_user(*, phone: str | None = None) -> User:
    return User(
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("password123"),
        first_name="Test",
        last_name="User",
        role="parent",
        phone=phone,
        email_verified=True,
    )


def test_validate_notification_preferences_rejects_sms_without_phone(monkeypatch):
    user = _build_user(phone=None)
    monkeypatch.setattr("app.services.notifications.sms_provider_configured", lambda: True)

    with pytest.raises(ValueError, match="Add a phone number to your account"):
        validate_notification_preference_channels(user=user, sms_enabled=True)


def test_validate_notification_preferences_rejects_sms_without_provider(monkeypatch):
    user = _build_user(phone="+27821234567")
    monkeypatch.setattr("app.services.notifications.sms_provider_configured", lambda: False)

    with pytest.raises(ValueError, match="SMS delivery is not configured"):
        validate_notification_preference_channels(user=user, sms_enabled=True)


def test_validate_notification_preferences_allows_sms_when_phone_and_provider_available(monkeypatch):
    user = _build_user(phone="+27821234567")
    monkeypatch.setattr("app.services.notifications.sms_provider_configured", lambda: True)

    validate_notification_preference_channels(user=user, sms_enabled=True)


def test_validate_notification_preferences_rejects_push_without_configuration(monkeypatch):
    user = _build_user(phone="+27821234567")
    monkeypatch.setattr("app.services.notifications.web_push_configured", lambda: False)

    with pytest.raises(ValueError, match="Push notifications are not configured"):
        validate_notification_preference_channels(user=user, push_enabled=True)


def test_validate_notification_preferences_allows_push_when_configured(monkeypatch):
    user = _build_user(phone="+27821234567")
    monkeypatch.setattr("app.services.notifications.web_push_configured", lambda: True)

    validate_notification_preference_channels(user=user, push_enabled=True)
