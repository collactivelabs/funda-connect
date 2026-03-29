from app.schemas.reference_data import (
    CurriculumOptionResponse,
    GradeLevelGroupResponse,
    GradeLevelOptionResponse,
    TopicOptionResponse,
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

TOPICS = [
    TopicOptionResponse(
        id="caps-mathematics-grade-10-algebraic-expressions",
        subject="mathematics",
        subject_name="Mathematics",
        grade="Grade 10",
        curriculum="CAPS",
        term=1,
        name="Algebraic expressions and factorisation",
        reference_code="CAPS-MATH-G10-T1-ALG",
    ),
    TopicOptionResponse(
        id="caps-mathematics-grade-10-functions",
        subject="mathematics",
        subject_name="Mathematics",
        grade="Grade 10",
        curriculum="CAPS",
        term=2,
        name="Functions and graphs",
        reference_code="CAPS-MATH-G10-T2-FUNC",
    ),
    TopicOptionResponse(
        id="caps-mathematics-grade-11-quadratic-functions",
        subject="mathematics",
        subject_name="Mathematics",
        grade="Grade 11",
        curriculum="CAPS",
        term=1,
        name="Quadratic functions and inequalities",
        reference_code="CAPS-MATH-G11-T1-QUAD",
    ),
    TopicOptionResponse(
        id="caps-mathematics-grade-12-calculus",
        subject="mathematics",
        subject_name="Mathematics",
        grade="Grade 12",
        curriculum="CAPS",
        term=3,
        name="Differential calculus",
        reference_code="CAPS-MATH-G12-T3-CALC",
    ),
    TopicOptionResponse(
        id="caps-physical-sciences-grade-10-matter-materials",
        subject="physical-sciences",
        subject_name="Physical Sciences",
        grade="Grade 10",
        curriculum="CAPS",
        term=1,
        name="Matter and materials",
        reference_code="CAPS-PS-G10-T1-MAT",
    ),
    TopicOptionResponse(
        id="caps-physical-sciences-grade-11-newtons-laws",
        subject="physical-sciences",
        subject_name="Physical Sciences",
        grade="Grade 11",
        curriculum="CAPS",
        term=2,
        name="Newton's laws and momentum",
        reference_code="CAPS-PS-G11-T2-NEW",
    ),
    TopicOptionResponse(
        id="caps-physical-sciences-grade-12-organic-chemistry",
        subject="physical-sciences",
        subject_name="Physical Sciences",
        grade="Grade 12",
        curriculum="CAPS",
        term=3,
        name="Organic chemistry and reactions",
        reference_code="CAPS-PS-G12-T3-ORG",
    ),
    TopicOptionResponse(
        id="caps-english-home-language-grade-8-comprehension",
        subject="english-home-language",
        subject_name="English Home Language",
        grade="Grade 8",
        curriculum="CAPS",
        term=1,
        name="Reading comprehension and language structures",
        reference_code="CAPS-EHL-G8-T1-COMP",
    ),
    TopicOptionResponse(
        id="caps-english-home-language-grade-10-essay-writing",
        subject="english-home-language",
        subject_name="English Home Language",
        grade="Grade 10",
        curriculum="CAPS",
        term=2,
        name="Essay writing and transactional texts",
        reference_code="CAPS-EHL-G10-T2-ESSAY",
    ),
    TopicOptionResponse(
        id="caps-life-sciences-grade-12-genetics",
        subject="life-sciences",
        subject_name="Life Sciences",
        grade="Grade 12",
        curriculum="CAPS",
        term=2,
        name="Genetics and inheritance",
        reference_code="CAPS-LS-G12-T2-GEN",
    ),
    TopicOptionResponse(
        id="cambridge-a-math-a-level-pure-1-functions",
        subject="cambridge-a-math",
        subject_name="Cambridge A-Level Mathematics",
        grade="Grade 12",
        curriculum="Cambridge",
        term=None,
        name="Pure Mathematics 1: functions and transformations",
        reference_code="CAMB-A-MATH-P1-FUNC",
    ),
    TopicOptionResponse(
        id="cambridge-igcse-science-grade-10-chemical-reactions",
        subject="cambridge-igcse-science",
        subject_name="Cambridge IGCSE Science",
        grade="Grade 10",
        curriculum="Cambridge",
        term=None,
        name="Chemical reactions and energy changes",
        reference_code="CAMB-IGCSE-SCI-CHEM",
    ),
    TopicOptionResponse(
        id="ieb-accounting-grade-11-ledgers",
        subject="accounting",
        subject_name="Accounting",
        grade="Grade 11",
        curriculum="IEB",
        term=1,
        name="General ledger and trial balance",
        reference_code="IEB-ACC-G11-T1-LEDGER",
    ),
    TopicOptionResponse(
        id="ieb-geography-grade-12-climate-geomorphology",
        subject="geography",
        subject_name="Geography",
        grade="Grade 12",
        curriculum="IEB",
        term=3,
        name="Climate and geomorphology revision",
        reference_code="IEB-GEO-G12-T3-CLIM",
    ),
]


def list_curricula() -> list[CurriculumOptionResponse]:
    return CURRICULA


def list_grade_level_groups() -> list[GradeLevelGroupResponse]:
    return GRADE_LEVEL_GROUPS


def list_topics(
    *,
    subject: str | None = None,
    grade: str | None = None,
    curriculum: str | None = None,
    term: int | None = None,
    q: str | None = None,
) -> list[TopicOptionResponse]:
    normalized_subject = subject.strip().lower() if subject else None
    normalized_grade = grade.strip().lower() if grade else None
    normalized_curriculum = curriculum.strip().lower() if curriculum else None
    normalized_query = q.strip().lower() if q else None

    results = TOPICS
    if normalized_subject:
        results = [item for item in results if item.subject.lower() == normalized_subject]
    if normalized_grade:
        results = [item for item in results if item.grade.lower() == normalized_grade]
    if normalized_curriculum:
        results = [item for item in results if item.curriculum.lower() == normalized_curriculum]
    if term is not None:
        results = [item for item in results if item.term == term]
    if normalized_query:
        results = [
            item
            for item in results
            if normalized_query in item.name.lower()
            or normalized_query in item.subject_name.lower()
            or (item.reference_code or "").lower().find(normalized_query) >= 0
        ]

    return results


def get_topics_by_ids(topic_ids: list[str]) -> list[TopicOptionResponse]:
    if not topic_ids:
        return []

    topic_map = {topic.id: topic for topic in TOPICS}
    return [topic_map[topic_id] for topic_id in topic_ids if topic_id in topic_map]
