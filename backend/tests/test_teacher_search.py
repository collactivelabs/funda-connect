from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.services.teacher_search import (
    build_teacher_search_filter_expression,
    build_teacher_search_sort,
    serialize_teacher_search_document,
)


def test_serialize_teacher_search_document_flattens_subjects_and_grades() -> None:
    profile = SimpleNamespace(
        id=uuid4(),
        verification_status="verified",
        is_listed=True,
        headline="Mathematics tutor",
        bio="Strong on functions and algebra",
        province="Gauteng",
        curricula=["CAPS", "IEB"],
        hourly_rate_cents=35_000,
        average_rating=4.8,
        total_lessons=42,
        is_premium=True,
        created_at=datetime(2026, 3, 29, 10, 0, tzinfo=UTC),
        user=SimpleNamespace(first_name="Nomvula", last_name="Mokoena"),
        subjects=[
            SimpleNamespace(
                subject=SimpleNamespace(name="Mathematics", slug="mathematics"),
                grade_levels=["Grade 10", "Grade 11"],
            ),
            SimpleNamespace(
                subject=SimpleNamespace(name="Physical Sciences", slug="physical-sciences"),
                grade_levels=["Grade 11", "Grade 12"],
            ),
        ],
    )

    document = serialize_teacher_search_document(profile)

    assert document is not None
    assert document["full_name"] == "Nomvula Mokoena"
    assert document["subject_slugs"] == ["mathematics", "physical-sciences"]
    assert document["grade_levels"] == ["Grade 10", "Grade 11", "Grade 12"]
    assert document["rating_average"] == 4.8
    assert document["is_premium"] is True


def test_serialize_teacher_search_document_skips_non_public_profiles() -> None:
    profile = SimpleNamespace(
        id=uuid4(),
        verification_status="pending",
        is_listed=False,
        user=SimpleNamespace(first_name="Nomvula", last_name="Mokoena"),
        subjects=[],
    )

    assert serialize_teacher_search_document(profile) is None


def test_build_teacher_search_filter_expression_combines_all_supported_filters() -> None:
    expression = build_teacher_search_filter_expression(
        subject="mathematics",
        curriculum="CAPS",
        grade="Grade 11",
        min_rate=20_000,
        max_rate=40_000,
        min_rating=4.5,
        province="Gauteng",
    )

    assert expression == (
        "subject_slugs = 'mathematics' AND curricula = 'CAPS' AND grade_levels = 'Grade 11' "
        "AND province = 'Gauteng' AND hourly_rate_cents >= 20000 AND hourly_rate_cents <= 40000 "
        "AND rating_average >= 4.5"
    )


def test_build_teacher_search_sort_defaults_to_premium_then_rating() -> None:
    assert build_teacher_search_sort() == [
        "is_premium:desc",
        "rating_average:desc",
        "created_at:desc",
    ]


def test_build_teacher_search_sort_honours_supported_override() -> None:
    assert build_teacher_search_sort("hourly_rate_cents", "asc") == [
        "is_premium:desc",
        "hourly_rate_cents:asc",
        "created_at:desc",
    ]
