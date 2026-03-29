from pydantic import BaseModel


class CurriculumOptionResponse(BaseModel):
    code: str
    label: str
    description: str


class GradeLevelOptionResponse(BaseModel):
    value: str
    label: str
    order: int


class GradeLevelGroupResponse(BaseModel):
    phase: str
    items: list[GradeLevelOptionResponse]


class TopicOptionResponse(BaseModel):
    id: str
    subject: str
    subject_name: str
    grade: str
    curriculum: str
    term: int | None = None
    name: str
    reference_code: str | None = None
