from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class AccountDataExportResponse(BaseModel):
    exported_at: datetime
    data: dict[str, Any]


class AccountDeletionStatusResponse(BaseModel):
    status: Literal["active", "pending_deletion", "anonymized"]
    is_active: bool
    deletion_requested_at: datetime | None = None
    deletion_scheduled_for: datetime | None = None
    anonymized_at: datetime | None = None
    cancelled_future_bookings: int = 0
    grace_period_days: int


class ConsentStateResponse(BaseModel):
    granted: bool
    version: str
    granted_at: datetime | None = None
    revoked_at: datetime | None = None


class AccountConsentResponse(BaseModel):
    terms_of_service: ConsentStateResponse
    privacy_policy: ConsentStateResponse
    marketing_email: ConsentStateResponse
    marketing_sms: ConsentStateResponse


class UpdateMarketingConsentRequest(BaseModel):
    marketing_email: bool
    marketing_sms: bool
