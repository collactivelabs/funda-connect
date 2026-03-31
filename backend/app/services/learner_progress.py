from collections import defaultdict
from datetime import UTC, datetime

from app.schemas.parent import (
    LearnerLessonProgressResponse,
    LearnerProgressResponse,
    LearnerSubjectProgressResponse,
)
from app.services.reference_data import get_topics_by_ids
from app.services.scheduling import normalize_utc

_COMPLETED_BOOKING_STATUSES = {"completed", "reviewed"}
_UPCOMING_BOOKING_STATUSES = {"confirmed", "in_progress"}


def build_learner_progress_summary(learner, bookings: list) -> LearnerProgressResponse:
    now_utc = datetime.now(UTC)
    completed_bookings = [
        booking for booking in bookings if booking.status in _COMPLETED_BOOKING_STATUSES
    ]
    completed_bookings.sort(key=lambda booking: normalize_utc(booking.scheduled_at), reverse=True)

    upcoming_lessons = sum(
        1
        for booking in bookings
        if booking.status in _UPCOMING_BOOKING_STATUSES
        and normalize_utc(booking.scheduled_at) >= now_utc
    )

    subject_stats: dict[str, dict] = defaultdict(
        lambda: {
            "subject_id": None,
            "subject_name": "",
            "completed_lessons": 0,
            "total_minutes": 0,
            "latest_lesson_at": None,
        }
    )
    ordered_topic_ids: list[str] = []
    seen_topic_ids: set[str] = set()

    for booking in completed_bookings:
        subject_key = str(booking.subject_id)
        stats = subject_stats[subject_key]
        stats["subject_id"] = booking.subject_id
        stats["subject_name"] = booking.subject.name if booking.subject else "Lesson"
        stats["completed_lessons"] += 1
        stats["total_minutes"] += booking.duration_minutes
        latest = stats["latest_lesson_at"]
        if latest is None or normalize_utc(booking.scheduled_at) > normalize_utc(latest):
            stats["latest_lesson_at"] = booking.scheduled_at

        for topic_id in booking.topics_covered or []:
            if topic_id not in seen_topic_ids:
                ordered_topic_ids.append(topic_id)
                seen_topic_ids.add(topic_id)

    topics = get_topics_by_ids(ordered_topic_ids)

    recent_lessons = [
        LearnerLessonProgressResponse(
            booking_id=booking.id,
            scheduled_at=booking.scheduled_at,
            duration_minutes=booking.duration_minutes,
            status=booking.status,
            subject_name=booking.subject.name if booking.subject else "Lesson",
            teacher_name=(
                f"{booking.teacher.user.first_name} {booking.teacher.user.last_name}"
                if booking.teacher and booking.teacher.user
                else "Teacher"
            ),
            lesson_notes=booking.lesson_notes,
            topics_covered=get_topics_by_ids(booking.topics_covered or []),
        )
        for booking in completed_bookings[:5]
    ]

    total_minutes = sum(booking.duration_minutes for booking in completed_bookings)
    last_completed_at = completed_bookings[0].scheduled_at if completed_bookings else None

    return LearnerProgressResponse(
        learner_id=learner.id,
        learner_name=learner.full_name,
        grade=learner.grade,
        curriculum=learner.curriculum,
        completed_lessons=len(completed_bookings),
        upcoming_lessons=upcoming_lessons,
        total_minutes=total_minutes,
        subject_count=len(subject_stats),
        topic_count=len(topics),
        last_completed_at=last_completed_at,
        subjects=[
            LearnerSubjectProgressResponse(
                subject_id=stats["subject_id"],
                subject_name=stats["subject_name"],
                completed_lessons=stats["completed_lessons"],
                total_minutes=stats["total_minutes"],
                latest_lesson_at=stats["latest_lesson_at"],
            )
            for stats in sorted(
                subject_stats.values(),
                key=lambda item: (
                    item["latest_lesson_at"] is None,
                    normalize_utc(item["latest_lesson_at"])
                    if item["latest_lesson_at"]
                    else datetime.min.replace(tzinfo=UTC),
                ),
                reverse=True,
            )
        ],
        topics_covered=topics,
        recent_lessons=recent_lessons,
    )
