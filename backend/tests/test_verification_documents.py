from dataclasses import dataclass

from app.services import verification_documents
from app.services.verification_documents import (
    build_document_access_url,
    derive_teacher_verification_status,
    get_missing_required_document_types,
    get_rejected_required_document_types,
    has_approved_all_required_documents,
    has_uploaded_all_required_documents,
    verification_document_counts,
)


@dataclass
class FakeDocument:
    document_type: str
    status: str


def _required_documents(status: str) -> list[FakeDocument]:
    return [
        FakeDocument("id_document", status),
        FakeDocument("qualification", status),
        FakeDocument("sace_certificate", status),
        FakeDocument("nrso_clearance", status),
        FakeDocument("reference_letter", status),
    ]


def test_uploaded_required_documents_treat_pending_as_usable():
    documents = _required_documents("pending")

    assert has_uploaded_all_required_documents(documents) is True
    assert has_approved_all_required_documents(documents) is False
    assert get_missing_required_document_types(documents) == []


def test_missing_required_documents_are_reported():
    documents = [
        FakeDocument("id_document", "approved"),
        FakeDocument("qualification", "approved"),
    ]

    assert has_uploaded_all_required_documents(documents) is False
    assert get_missing_required_document_types(documents) == [
        "sace_certificate",
        "nrso_clearance",
        "reference_letter",
    ]


def test_rejected_required_document_type_requires_replacement():
    documents = [
        FakeDocument("id_document", "approved"),
        FakeDocument("qualification", "approved"),
        FakeDocument("sace_certificate", "rejected"),
        FakeDocument("nrso_clearance", "approved"),
        FakeDocument("reference_letter", "approved"),
    ]

    assert get_rejected_required_document_types(documents) == ["sace_certificate"]
    assert derive_teacher_verification_status("under_review", documents) == "rejected"


def test_rejected_document_with_replacement_moves_back_to_under_review():
    documents = [
        FakeDocument("id_document", "approved"),
        FakeDocument("qualification", "approved"),
        FakeDocument("sace_certificate", "rejected"),
        FakeDocument("sace_certificate", "pending"),
        FakeDocument("nrso_clearance", "approved"),
        FakeDocument("reference_letter", "approved"),
    ]

    assert get_rejected_required_document_types(documents) == []
    assert derive_teacher_verification_status("rejected", documents) == "under_review"


def test_verified_status_requires_all_required_documents_to_stay_verified():
    documents = _required_documents("approved")

    assert has_approved_all_required_documents(documents) is True
    assert derive_teacher_verification_status("verified", documents) == "verified"


def test_document_counts_group_by_review_status():
    documents = [
        FakeDocument("id_document", "approved"),
        FakeDocument("qualification", "approved"),
        FakeDocument("sace_certificate", "pending"),
        FakeDocument("nrso_clearance", "rejected"),
        FakeDocument("reference_letter", "pending"),
    ]

    assert verification_document_counts(documents) == {
        "approved": 2,
        "pending": 2,
        "rejected": 1,
    }


def test_build_document_access_url_uses_regional_s3_endpoint(monkeypatch):
    class FakeS3Client:
        def generate_presigned_url(self, operation_name, *, Params, ExpiresIn):
            assert operation_name == "get_object"
            assert Params["Bucket"] == verification_documents.settings.AWS_S3_BUCKET
            assert Params["Key"] == "documents/teacher/doc.pdf"
            assert ExpiresIn == 900
            return (
                "https://"
                f"{verification_documents.settings.AWS_S3_BUCKET}.s3."
                f"{verification_documents.settings.AWS_REGION}.amazonaws.com/documents/teacher/doc.pdf"
                "?X-Amz-SignedHeaders=host"
            )

    monkeypatch.setattr(verification_documents, "build_s3_client", lambda: FakeS3Client())

    url = build_document_access_url(
        f"https://{verification_documents.settings.AWS_S3_BUCKET}.s3."
        f"{verification_documents.settings.AWS_REGION}.amazonaws.com/documents/teacher/doc.pdf",
        expires_in=900,
    )

    assert ".s3.af-south-1.amazonaws.com/" in url
    assert ".s3.amazonaws.com/" not in url
