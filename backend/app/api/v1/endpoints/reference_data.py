from fastapi import APIRouter

from app.schemas.reference_data import (
    CurriculumOptionResponse,
    GradeLevelGroupResponse,
    TopicOptionResponse,
)
from app.services.reference_data import list_curricula, list_grade_level_groups, list_topics

router = APIRouter()


@router.get("/curricula", response_model=list[CurriculumOptionResponse])
async def get_curricula():
    """List supported curricula for public forms and filters."""
    return list_curricula()


@router.get("/grade-levels", response_model=list[GradeLevelGroupResponse])
async def get_grade_levels():
    """List supported grade levels grouped by learning phase."""
    return list_grade_level_groups()


@router.get("/topics", response_model=list[TopicOptionResponse])
async def get_topics(
    subject: str | None = None,
    grade: str | None = None,
    curriculum: str | None = None,
    term: int | None = None,
    q: str | None = None,
):
    """List reference topics filtered by subject, grade, curriculum, term, and free text."""
    return list_topics(
        subject=subject,
        grade=grade,
        curriculum=curriculum,
        term=term,
        q=q,
    )
