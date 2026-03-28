from uuid import uuid4

import pytest

from app.models.notification import Notification, NotificationPreference
from app.services.notifications import (
    create_in_app_notification,
    get_notification_preferences_snapshot,
    get_or_create_notification_preferences,
)


class FakeSession:
    def __init__(self, preference: NotificationPreference | None = None):
        self.preference = preference
        self.notifications: list[Notification] = []

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
