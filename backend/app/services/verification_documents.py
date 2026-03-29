from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import unquote, urlparse

from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.services.storage import build_s3_client

REQUIRED_VERIFICATION_DOCUMENT_TYPES = (
    "id_document",
    "qualification",
    "sace_certificate",
    "nrso_clearance",
    "reference_letter",
)

USABLE_DOCUMENT_STATUSES = {"pending", "approved"}


def _docs_for_type(documents: Iterable, document_type: str) -> list:
    return [
        document
        for document in documents
        if getattr(document, "document_type", None) == document_type
    ]


def _has_status(documents: Iterable, status: str) -> bool:
    return any(getattr(document, "status", None) == status for document in documents)


def has_uploaded_all_required_documents(documents: Iterable) -> bool:
    documents_list = list(documents)
    return all(
        any(
            getattr(document, "status", None) in USABLE_DOCUMENT_STATUSES
            for document in _docs_for_type(documents_list, document_type)
        )
        for document_type in REQUIRED_VERIFICATION_DOCUMENT_TYPES
    )


def has_approved_all_required_documents(documents: Iterable) -> bool:
    documents_list = list(documents)
    return all(
        any(
            getattr(document, "status", None) == "approved"
            for document in _docs_for_type(documents_list, document_type)
        )
        for document_type in REQUIRED_VERIFICATION_DOCUMENT_TYPES
    )


def get_missing_required_document_types(documents: Iterable) -> list[str]:
    documents_list = list(documents)
    return [
        document_type
        for document_type in REQUIRED_VERIFICATION_DOCUMENT_TYPES
        if not any(
            getattr(document, "status", None) in USABLE_DOCUMENT_STATUSES
            for document in _docs_for_type(documents_list, document_type)
        )
    ]


def get_rejected_required_document_types(documents: Iterable) -> list[str]:
    documents_list = list(documents)
    rejected_types: list[str] = []

    for document_type in REQUIRED_VERIFICATION_DOCUMENT_TYPES:
        matching = _docs_for_type(documents_list, document_type)
        if not matching:
            continue
        if any(getattr(document, "status", None) in USABLE_DOCUMENT_STATUSES for document in matching):
            continue
        if _has_status(matching, "rejected"):
            rejected_types.append(document_type)

    return rejected_types


def derive_teacher_verification_status(current_status: str, documents: Iterable) -> str:
    if current_status == "suspended":
        return "suspended"

    documents_list = list(documents)

    if has_approved_all_required_documents(documents_list):
        return "verified" if current_status == "verified" else "under_review"

    if get_rejected_required_document_types(documents_list):
        return "rejected"

    if has_uploaded_all_required_documents(documents_list):
        return "under_review"

    return "pending"


def verification_document_counts(documents: Iterable) -> dict[str, int]:
    counts = {"approved": 0, "pending": 0, "rejected": 0}
    for document in documents:
        status = getattr(document, "status", None)
        if status in counts:
            counts[status] += 1
    return counts


def _document_key_from_url(file_url: str) -> str | None:
    parsed = urlparse(file_url)
    path = unquote(parsed.path.lstrip("/"))
    if not path:
        return None

    bucket = settings.AWS_S3_BUCKET.strip() if settings.AWS_S3_BUCKET else ""
    if bucket and path.startswith(f"{bucket}/"):
        return path.removeprefix(f"{bucket}/")

    return path


def build_document_access_url(file_url: str, *, expires_in: int = 900) -> str:
    if not settings.AWS_S3_BUCKET or not settings.AWS_REGION:
        return file_url

    key = _document_key_from_url(file_url)
    if not key:
        return file_url

    s3 = build_s3_client()

    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.AWS_S3_BUCKET,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, ClientError):
        return file_url
