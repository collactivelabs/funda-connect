from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SubjectResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    icon: str | None = None
    tier: int

    model_config = ConfigDict(from_attributes=True)


class TeacherSubjectResponse(BaseModel):
    id: UUID
    subject_id: UUID
    subject_name: str
    grade_levels: list[str]
    curriculum: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_subject(cls, ts) -> "TeacherSubjectResponse":
        return cls(
            id=ts.id,
            subject_id=ts.subject_id,
            subject_name=ts.subject.name,
            grade_levels=ts.grade_levels,
            curriculum=ts.curriculum,
        )


class TeacherUserSnippet(BaseModel):
    first_name: str
    last_name: str
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TeacherProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    bio: str | None = None
    headline: str | None = None
    years_experience: int | None = None
    hourly_rate_cents: int | None = None
    curricula: list[str]
    verification_status: str
    is_listed: bool
    average_rating: float | None = None
    total_reviews: int
    total_lessons: int
    is_premium: bool
    province: str | None = None
    subjects: list[TeacherSubjectResponse] = []
    user: TeacherUserSnippet

    model_config = ConfigDict(from_attributes=True)


class UpdateProfileRequest(BaseModel):
    bio: str | None = None
    headline: str | None = None
    years_experience: int | None = Field(None, ge=0, le=50)
    hourly_rate_cents: int | None = Field(None, ge=5000, le=500000)  # R50–R5000
    curricula: list[str] | None = None
    province: str | None = None


class AddSubjectRequest(BaseModel):
    subject_id: UUID
    grade_levels: list[str] = Field(..., min_length=1)
    curriculum: str  # CAPS | Cambridge | IEB


class VerificationDocumentResponse(BaseModel):
    id: UUID
    document_type: str
    file_url: str
    file_name: str
    status: str

    model_config = ConfigDict(from_attributes=True)
