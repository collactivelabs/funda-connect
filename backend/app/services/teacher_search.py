from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.teacher import TeacherProfile, TeacherSubject

logger = structlog.get_logger()

TEACHER_SEARCH_INDEX = "teachers"
_SEARCHABLE_ATTRIBUTES = [
    "full_name",
    "first_name",
    "last_name",
    "headline",
    "bio",
    "subject_names",
    "subject_slugs",
    "grade_levels",
    "curricula",
    "province",
]
_FILTERABLE_ATTRIBUTES = [
    "subject_slugs",
    "curricula",
    "grade_levels",
    "province",
    "hourly_rate_cents",
    "rating_average",
    "total_lessons",
    "is_premium",
]
_SORTABLE_ATTRIBUTES = [
    "is_premium",
    "rating_average",
    "hourly_rate_cents",
    "total_lessons",
    "created_at",
]
_DISPLAYED_ATTRIBUTES = [
    "id",
    "full_name",
    "headline",
    "bio",
    "province",
    "curricula",
    "subject_names",
    "subject_slugs",
    "grade_levels",
    "hourly_rate_cents",
    "rating_average",
    "total_lessons",
    "created_at",
    "is_premium",
]


def _client():
    import meilisearch

    return meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY or None)


def _quote_filter_value(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def build_teacher_search_filter_expression(
    *,
    subject: str | None = None,
    curriculum: str | None = None,
    grade: str | None = None,
    min_rate: int | None = None,
    max_rate: int | None = None,
    min_rating: float | None = None,
    province: str | None = None,
) -> str | None:
    filters: list[str] = []
    if subject:
        filters.append(f"subject_slugs = {_quote_filter_value(subject)}")
    if curriculum:
        filters.append(f"curricula = {_quote_filter_value(curriculum)}")
    if grade:
        filters.append(f"grade_levels = {_quote_filter_value(grade)}")
    if province:
        filters.append(f"province = {_quote_filter_value(province)}")
    if min_rate is not None:
        filters.append(f"hourly_rate_cents >= {min_rate}")
    if max_rate is not None:
        filters.append(f"hourly_rate_cents <= {max_rate}")
    if min_rating is not None:
        filters.append(f"rating_average >= {min_rating}")
    return " AND ".join(filters) if filters else None


def build_teacher_search_sort(
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> list[str]:
    allowed = {
        "rating_average": "rating_average",
        "hourly_rate_cents": "hourly_rate_cents",
        "total_lessons": "total_lessons",
        "created_at": "created_at",
    }
    requested = allowed.get(sort_by or "")
    direction = "asc" if sort_order == "asc" else "desc"
    sort = ["is_premium:desc"]
    if requested:
        sort.append(f"{requested}:{direction}")
        if requested != "created_at":
            sort.append("created_at:desc")
        return sort
    sort.extend(["rating_average:desc", "created_at:desc"])
    return sort


def serialize_teacher_search_document(profile: TeacherProfile) -> dict[str, Any] | None:
    if not profile.user or profile.verification_status != "verified" or not profile.is_listed:
        return None

    subject_names: list[str] = []
    subject_slugs: list[str] = []
    grade_levels: list[str] = []
    seen_names: set[str] = set()
    seen_slugs: set[str] = set()
    seen_grades: set[str] = set()

    for teacher_subject in profile.subjects:
        if teacher_subject.subject:
            if teacher_subject.subject.name not in seen_names:
                subject_names.append(teacher_subject.subject.name)
                seen_names.add(teacher_subject.subject.name)
            if teacher_subject.subject.slug not in seen_slugs:
                subject_slugs.append(teacher_subject.subject.slug)
                seen_slugs.add(teacher_subject.subject.slug)
        for grade_level in teacher_subject.grade_levels or []:
            if grade_level not in seen_grades:
                grade_levels.append(grade_level)
                seen_grades.add(grade_level)

    full_name = f"{profile.user.first_name} {profile.user.last_name}".strip()
    return {
        "id": str(profile.id),
        "first_name": profile.user.first_name,
        "last_name": profile.user.last_name,
        "full_name": full_name,
        "headline": profile.headline or "",
        "bio": profile.bio or "",
        "province": profile.province or "",
        "curricula": profile.curricula or [],
        "subject_names": subject_names,
        "subject_slugs": subject_slugs,
        "grade_levels": grade_levels,
        "hourly_rate_cents": profile.hourly_rate_cents or 0,
        "rating_average": profile.average_rating or 0,
        "total_lessons": profile.total_lessons,
        "created_at": profile.created_at.isoformat(),
        "is_premium": profile.is_premium,
    }


def _wait_for_task(index, task_info) -> None:
    index.wait_for_task(task_info.task_uid, timeout_in_ms=10_000, interval_in_ms=100)


def _ensure_teacher_index_sync() -> None:
    client = _client()
    indexes = client.get_indexes().get("results", [])
    existing_uids = {item["uid"] for item in indexes}
    if TEACHER_SEARCH_INDEX not in existing_uids:
        task = client.create_index(TEACHER_SEARCH_INDEX, {"primaryKey": "id"})
        client.wait_for_task(task.task_uid, timeout_in_ms=10_000, interval_in_ms=100)

    index = client.index(TEACHER_SEARCH_INDEX)
    _wait_for_task(index, index.update_searchable_attributes(_SEARCHABLE_ATTRIBUTES))
    _wait_for_task(index, index.update_filterable_attributes(_FILTERABLE_ATTRIBUTES))
    _wait_for_task(index, index.update_sortable_attributes(_SORTABLE_ATTRIBUTES))
    _wait_for_task(index, index.update_displayed_attributes(_DISPLAYED_ATTRIBUTES))


async def ensure_teacher_search_index() -> None:
    await asyncio.to_thread(_ensure_teacher_index_sync)


def _search_teacher_ids_sync(
    *,
    query: str | None,
    subject: str | None,
    curriculum: str | None,
    grade: str | None,
    min_rate: int | None,
    max_rate: int | None,
    min_rating: float | None,
    province: str | None,
    sort_by: str | None,
    sort_order: str,
) -> list[str]:
    _ensure_teacher_index_sync()
    index = _client().index(TEACHER_SEARCH_INDEX)
    opt_params: dict[str, Any] = {
        "limit": 1000,
        "sort": build_teacher_search_sort(sort_by, sort_order),
    }
    filter_expression = build_teacher_search_filter_expression(
        subject=subject,
        curriculum=curriculum,
        grade=grade,
        min_rate=min_rate,
        max_rate=max_rate,
        min_rating=min_rating,
        province=province,
    )
    if filter_expression:
        opt_params["filter"] = filter_expression

    search_response = index.search((query or "").strip(), opt_params)
    return [str(hit["id"]) for hit in search_response.get("hits", []) if hit.get("id")]


async def search_teacher_ids(
    *,
    query: str | None,
    subject: str | None,
    curriculum: str | None,
    grade: str | None,
    min_rate: int | None,
    max_rate: int | None,
    min_rating: float | None,
    province: str | None,
    sort_by: str | None,
    sort_order: str,
) -> list[str] | None:
    try:
        return await asyncio.to_thread(
            _search_teacher_ids_sync,
            query=query,
            subject=subject,
            curriculum=curriculum,
            grade=grade,
            min_rate=min_rate,
            max_rate=max_rate,
            min_rating=min_rating,
            province=province,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("teacher_search.query_failed", error=str(exc))
        return None


def _replace_teacher_search_documents_sync(documents: list[dict[str, Any]]) -> None:
    _ensure_teacher_index_sync()
    index = _client().index(TEACHER_SEARCH_INDEX)
    _wait_for_task(index, index.delete_all_documents())
    if documents:
        _wait_for_task(index, index.add_documents(documents, primary_key="id"))


async def rebuild_teacher_search_index(db: AsyncSession) -> int:
    result = await db.scalars(
        select(TeacherProfile)
        .options(selectinload(TeacherProfile.user))
        .options(selectinload(TeacherProfile.subjects).selectinload(TeacherSubject.subject))
    )
    documents = [
        document
        for profile in result.unique().all()
        if (document := serialize_teacher_search_document(profile)) is not None
    ]
    try:
        await asyncio.to_thread(_replace_teacher_search_documents_sync, documents)
    except Exception as exc:  # noqa: BLE001
        logger.warning("teacher_search.rebuild_failed", error=str(exc))
        return 0
    return len(documents)


def _upsert_teacher_document_sync(document: dict[str, Any]) -> None:
    _ensure_teacher_index_sync()
    index = _client().index(TEACHER_SEARCH_INDEX)
    _wait_for_task(index, index.update_documents([document], primary_key="id"))


def _delete_teacher_document_sync(teacher_id: UUID) -> None:
    _ensure_teacher_index_sync()
    index = _client().index(TEACHER_SEARCH_INDEX)
    _wait_for_task(index, index.delete_document(str(teacher_id)))


async def sync_teacher_document_by_id(db: AsyncSession, teacher_id: UUID) -> None:
    profile = await db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.id == teacher_id)
        .options(selectinload(TeacherProfile.user))
        .options(selectinload(TeacherProfile.subjects).selectinload(TeacherSubject.subject))
    )
    if not profile:
        try:
            await asyncio.to_thread(_delete_teacher_document_sync, teacher_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("teacher_search.delete_failed", teacher_id=str(teacher_id), error=str(exc))
        return

    document = serialize_teacher_search_document(profile)
    try:
        if document is None:
            await asyncio.to_thread(_delete_teacher_document_sync, teacher_id)
        else:
            await asyncio.to_thread(_upsert_teacher_document_sync, document)
    except Exception as exc:  # noqa: BLE001
        logger.warning("teacher_search.sync_failed", teacher_id=str(teacher_id), error=str(exc))
