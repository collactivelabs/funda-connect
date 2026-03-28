from fastapi import APIRouter

from app.schemas.reference_data import CurriculumOptionResponse, GradeLevelGroupResponse
from app.services.reference_data import list_curricula, list_grade_level_groups

router = APIRouter()


@router.get("/curricula", response_model=list[CurriculumOptionResponse])
async def get_curricula():
    """List supported curricula for public forms and filters."""
    return list_curricula()


@router.get("/grade-levels", response_model=list[GradeLevelGroupResponse])
async def get_grade_levels():
    """List supported grade levels grouped by learning phase."""
    return list_grade_level_groups()
