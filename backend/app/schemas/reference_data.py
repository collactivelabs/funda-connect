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
