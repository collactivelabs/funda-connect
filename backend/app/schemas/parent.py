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
