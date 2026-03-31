from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.services.learner_progress import build_learner_progress_summary


def _build_booking(
    *,
    status: str,
    scheduled_at: datetime,
    duration_minutes: int,
    subject_id,
    subject_name: str,
    teacher_name: str,
    lesson_notes: str | None = None,
    topics_covered: list[str] | None = None,
):
    first_name, last_name = teacher_name.split(" ", 1)
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        subject_id=subject_id,
        subject=SimpleNamespace(name=subject_name),
        teacher=SimpleNamespace(user=SimpleNamespace(first_name=first_name, last_name=last_name)),
        lesson_notes=lesson_notes,
        topics_covered=topics_covered or [],
    )


def test_build_learner_progress_summary_returns_recent_lessons_subject_rollups_and_topics() -> None:
    learner = SimpleNamespace(
        id=uuid4(),
        full_name="Hope Mongwe",
        grade="Grade 10",
        curriculum="CAPS",
    )
    mathematics_id = uuid4()
    science_id = uuid4()
    now = datetime.now(UTC)

    bookings = [
        _build_booking(
            status="completed",
            scheduled_at=now - timedelta(days=1),
            duration_minutes=60,
            subject_id=mathematics_id,
            subject_name="Mathematics",
            teacher_name="Ada Lovelace",
            lesson_notes="Worked through graphs and intercepts.",
            topics_covered=[
                "caps-mathematics-grade-10-functions",
                "caps-mathematics-grade-10-algebraic-expressions",
            ],
        ),
        _build_booking(
            status="reviewed",
            scheduled_at=now - timedelta(days=7),
            duration_minutes=90,
            subject_id=science_id,
            subject_name="Physical Sciences",
            teacher_name="Grace Hopper",
            lesson_notes="Reinforced matter and materials.",
            topics_covered=["caps-physical-sciences-grade-10-matter-materials"],
        ),
        _build_booking(
            status="confirmed",
            scheduled_at=now + timedelta(days=2),
            duration_minutes=60,
            subject_id=mathematics_id,
            subject_name="Mathematics",
            teacher_name="Ada Lovelace",
        ),
    ]

    summary = build_learner_progress_summary(learner, bookings)

    assert summary.learner_name == "Hope Mongwe"
    assert summary.completed_lessons == 2
    assert summary.upcoming_lessons == 1
    assert summary.total_minutes == 150
    assert summary.subject_count == 2
    assert summary.topic_count == 3
    assert [subject.subject_name for subject in summary.subjects] == [
        "Mathematics",
        "Physical Sciences",
    ]
    assert summary.recent_lessons[0].lesson_notes == "Worked through graphs and intercepts."
    assert [topic.name for topic in summary.topics_covered] == [
        "Functions and graphs",
        "Algebraic expressions and factorisation",
        "Matter and materials",
    ]


def test_build_learner_progress_summary_ignores_cancelled_lessons_in_progress_counts() -> None:
    learner = SimpleNamespace(
        id=uuid4(),
        full_name="Micah Dube",
        grade="Grade 11",
        curriculum="CAPS",
    )
    subject_id = uuid4()
    now = datetime.now(UTC)

    bookings = [
        _build_booking(
            status="cancelled",
            scheduled_at=now - timedelta(days=2),
            duration_minutes=60,
            subject_id=subject_id,
            subject_name="Mathematics",
            teacher_name="Ada Lovelace",
        ),
        _build_booking(
            status="expired",
            scheduled_at=now + timedelta(days=1),
            duration_minutes=60,
            subject_id=subject_id,
            subject_name="Mathematics",
            teacher_name="Ada Lovelace",
        ),
    ]

    summary = build_learner_progress_summary(learner, bookings)

    assert summary.completed_lessons == 0
    assert summary.upcoming_lessons == 0
    assert summary.total_minutes == 0
    assert summary.subjects == []
    assert summary.recent_lessons == []
