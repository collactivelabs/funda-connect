from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, model_validator


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    channel: str
    title: str
    body: str
    metadata: dict[str, Any] | None = None
    is_read: bool
    sent_at: datetime
    read_at: datetime | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class NotificationPreferencesResponse(BaseModel):
    in_app_enabled: bool
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool


class UpdateNotificationPreferencesRequest(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    push_enabled: bool | None = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UpdateNotificationPreferencesRequest":
        if all(
            value is None
            for value in (
                self.in_app_enabled,
                self.email_enabled,
                self.sms_enabled,
                self.push_enabled,
            )
        ):
            raise ValueError("At least one preference field must be provided")
        return self
