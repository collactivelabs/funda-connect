from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateReviewRequest(BaseModel):
    booking_id: UUID
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None


class ReplyReviewRequest(BaseModel):
    reply: str


class ReviewResponse(BaseModel):
    id: UUID
    booking_id: UUID
    teacher_id: UUID
    parent_id: UUID
    rating: int
    comment: str | None = None
    teacher_reply: str | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)
