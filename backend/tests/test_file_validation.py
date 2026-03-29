import pytest

from app.services.file_validation import UploadValidationError, validate_upload


def test_validate_upload_accepts_pdf_magic_bytes():
    validated = validate_upload(
        data=b"%PDF-1.7\nbody",
        filename="../Teacher ID.PDF",
        content_type="application/pdf",
        max_file_bytes=1024,
    )

    assert validated.content_type == "application/pdf"
    assert validated.extension == "pdf"
    assert validated.file_name == "Teacher-ID.pdf"


def test_validate_upload_rejects_mismatched_content_type():
    with pytest.raises(UploadValidationError, match="does not match"):
        validate_upload(
            data=b"\x89PNG\r\n\x1a\nrest",
            filename="document.pdf",
            content_type="application/pdf",
            max_file_bytes=1024,
        )


def test_validate_upload_rejects_unknown_binary_content():
    with pytest.raises(UploadValidationError, match="Unsupported file content"):
        validate_upload(
            data=b"not-a-real-document",
            filename="mystery.pdf",
            content_type="application/pdf",
            max_file_bytes=1024,
        )
