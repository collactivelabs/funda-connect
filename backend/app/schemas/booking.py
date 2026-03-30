from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Availability ──────────────────────────────────────────────


class AvailabilitySlotResponse(BaseModel):
    id: UUID
    day_of_week: int  # 0=Mon … 6=Sun
    start_time: str   # "09:00"
    end_time: str     # "10:00"
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BlockedDateResponse(BaseModel):
    id: UUID
    date: date
    reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SetAvailabilityRequest(BaseModel):
    """Replaces all slots for the teacher."""
    slots: list["SlotInput"]


class SetBlockedDatesRequest(BaseModel):
    """Replaces all blocked dates for the teacher."""
    dates: list["BlockedDateInput"]


class SlotInput(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str  # "HH:MM"
    end_time: str    # "HH:MM"


class BlockedDateInput(BaseModel):
    date: date
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


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
    curriculum: str

    model_config = ConfigDict(from_attributes=True)


class SubjectSnippet(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class BookingTeacherSnippet(BaseModel):
    id: UUID
    first_name: str
    last_name: str

    @classmethod
    def from_teacher_profile(cls, tp) -> "BookingTeacherSnippet":
        return cls(id=tp.id, first_name=tp.user.first_name, last_name=tp.user.last_name)

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
    recurring_booking_id: UUID | None = None
    parent_notes: str | None = None
    lesson_notes: str | None = None
    topics_covered: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    no_show_reported_at: datetime | None = None
    no_show_reported_by_role: str | None = None
    no_show_reason: str | None = None
    video_room_url: str | None = None
    teacher_id: UUID
    learner_id: UUID
    subject_id: UUID
    # Optional nested snippets (populated when eager-loaded)
    learner: LearnerSnippet | None = None
    subject: SubjectSnippet | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateBookingRequest(BaseModel):
    teacher_id: UUID
    learner_id: UUID
    subject_id: UUID
    scheduled_at: datetime
    duration_minutes: int = Field(60, ge=30, le=180)
    is_trial: bool = False
    is_recurring: bool = False
    recurring_weeks: int | None = Field(None, ge=2, le=12)  # total lessons in a prepaid weekly series
    parent_notes: str | None = None

    @field_validator("duration_minutes")
    @classmethod
    def duration_must_be_30_min_steps(cls, value: int) -> int:
        if value % 30 != 0:
            raise ValueError("duration_minutes must be in 30-minute increments")
        return value


class CancelBookingRequest(BaseModel):
    reason: str | None = None


class RescheduleBookingRequest(BaseModel):
    scheduled_at: datetime


class RaiseDisputeRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=2000)


class ReportNoShowRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CompleteBookingRequest(BaseModel):
    lesson_notes: str | None = Field(default=None, max_length=5000)
    topics_covered: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("lesson_notes")
    @classmethod
    def normalize_lesson_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("topics_covered")
    @classmethod
    def dedupe_topics(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for item in value:
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                deduped.append(cleaned)
                seen.add(cleaned)
        return deduped


class PayFastRedirectResponse(BaseModel):
    booking_id: UUID
    payment_url: str
    form_data: dict[str, str]
    amount_cents: int


class BookableSlotResponse(BaseModel):
    start_at: datetime
    end_at: datetime
    date: date
    date_label: str
    time_label: str
