from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LearnerResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    grade: str
    curriculum: str
    notes: str | None = None
    age: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateLearnerRequest(BaseModel):
    first_name: str
    last_name: str
    grade: str  # "Grade R", "Grade 1" ... "Grade 12"
    curriculum: str  # CAPS | Cambridge | IEB
    notes: str | None = None
    age: int | None = Field(None, ge=3, le=25)


class UpdateLearnerRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    grade: str | None = None
    curriculum: str | None = None
    notes: str | None = None
    age: int | None = Field(None, ge=3, le=25)


class ParentPaymentHistoryItemResponse(BaseModel):
    id: UUID
    booking_id: UUID
    gateway: str
    gateway_payment_id: str | None = None
    amount_cents: int
    status: str
    paid_at: datetime | None = None
    created_at: datetime
    booking_status: str
    scheduled_at: datetime
    teacher_name: str
    learner_name: str
    subject_name: str
    refund_amount_cents: int = 0
    refund_status: str | None = None
    refund_requested_at: datetime | None = None
    refund_processed_at: datetime | None = None
    is_series: bool = False
    series_lessons: int = 1


class ParentPaymentHistoryResponse(BaseModel):
    completed_payments_cents: int
    pending_payments_cents: int
    refunded_payments_cents: int
    refund_pending_cents: int
    payments: list[ParentPaymentHistoryItemResponse]


class ParentPaymentReceiptResponse(BaseModel):
    payment_id: UUID
    booking_id: UUID
    receipt_reference: str
    issued_at: datetime
    payment_status: str
    payment_gateway: str
    payment_gateway_reference: str | None = None
    amount_cents: int
    refund_amount_cents: int
    net_paid_cents: int
    parent_name: str
    parent_email: str
    teacher_name: str
    learner_name: str
    subject_name: str
    scheduled_at: datetime
    duration_minutes: int
    is_trial: bool
    is_series: bool = False
    series_lessons: int = 1
