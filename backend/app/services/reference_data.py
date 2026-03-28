from app.schemas.reference_data import (
    CurriculumOptionResponse,
    GradeLevelGroupResponse,
    GradeLevelOptionResponse,
)

CURRICULA = [
    CurriculumOptionResponse(
        code="CAPS",
        label="CAPS",
        description="South African Curriculum and Assessment Policy Statement.",
    ),
    CurriculumOptionResponse(
        code="Cambridge",
        label="Cambridge",
        description="Cambridge homeschool and international programme support.",
    ),
    CurriculumOptionResponse(
        code="IEB",
        label="IEB",
        description="Independent Examinations Board aligned tutoring support.",
    ),
]

GRADE_LEVEL_GROUPS = [
    GradeLevelGroupResponse(
        phase="Foundation Phase",
        items=[
            GradeLevelOptionResponse(value="Grade R", label="Grade R", order=0),
            GradeLevelOptionResponse(value="Grade 1", label="Grade 1", order=1),
            GradeLevelOptionResponse(value="Grade 2", label="Grade 2", order=2),
            GradeLevelOptionResponse(value="Grade 3", label="Grade 3", order=3),
        ],
    ),
    GradeLevelGroupResponse(
        phase="Intermediate Phase",
        items=[
            GradeLevelOptionResponse(value="Grade 4", label="Grade 4", order=4),
            GradeLevelOptionResponse(value="Grade 5", label="Grade 5", order=5),
            GradeLevelOptionResponse(value="Grade 6", label="Grade 6", order=6),
        ],
    ),
    GradeLevelGroupResponse(
        phase="Senior Phase",
        items=[
            GradeLevelOptionResponse(value="Grade 7", label="Grade 7", order=7),
            GradeLevelOptionResponse(value="Grade 8", label="Grade 8", order=8),
            GradeLevelOptionResponse(value="Grade 9", label="Grade 9", order=9),
        ],
    ),
    GradeLevelGroupResponse(
        phase="FET Phase",
        items=[
            GradeLevelOptionResponse(value="Grade 10", label="Grade 10", order=10),
            GradeLevelOptionResponse(value="Grade 11", label="Grade 11", order=11),
            GradeLevelOptionResponse(value="Grade 12", label="Grade 12", order=12),
        ],
    ),
]


def list_curricula() -> list[CurriculumOptionResponse]:
    return CURRICULA


def list_grade_level_groups() -> list[GradeLevelGroupResponse]:
    return GRADE_LEVEL_GROUPS
