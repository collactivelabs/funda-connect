from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Availability ──────────────────────────────────────────────


class AvailabilitySlotResponse(BaseModel):
    id: UUID
    day_of_week: int  # 0=Mon … 6=Sun
    start_time: str   # "09:00"
    end_time: str     # "10:00"
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SetAvailabilityRequest(BaseModel):
    """Replaces all slots for the teacher."""
    slots: list["SlotInput"]


class SlotInput(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str  # "HH:MM"
    end_time: str    # "HH:MM"


# ── Bookings ─────────────────────────────────────────────────


class TeacherSnippet(BaseModel):
    id: UUID
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


class LearnerSnippet(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    grade: str

    model_config = ConfigDict(from_attributes=True)


class SubjectSnippet(BaseModel):
    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class BookingResponse(BaseModel):
    id: UUID
    status: str
    scheduled_at: datetime
    duration_minutes: int
    amount_cents: int
    commission_cents: int
    teacher_payout_cents: int
    is_trial: bool
    is_recurring: bool
    parent_notes: str | None = None
    video_room_url: str | None = None
    # nested
    teacher_id: UUID
    learner_id: UUID
    subject_id: UUID

    model_config = ConfigDict(from_attributes=True)


class CreateBookingRequest(BaseModel):
    teacher_id: UUID
    learner_id: UUID
    subject_id: UUID
    scheduled_at: datetime
    duration_minutes: int = Field(60, ge=30, le=180)
    is_trial: bool = False
    parent_notes: str | None = None


class CancelBookingRequest(BaseModel):
    reason: str | None = None


class PayFastRedirectResponse(BaseModel):
    booking_id: UUID
    payment_url: str
    amount_cents: int
