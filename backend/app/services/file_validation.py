import re
from dataclasses import dataclass
from pathlib import PurePosixPath

_ALLOWED_SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}

_EXTENSIONS = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}


class UploadValidationError(ValueError):
    def __init__(self, detail: str, *, status_code: int):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedUpload:
    file_name: str
    content_type: str
    extension: str


def _detect_mime_type(data: bytes) -> str | None:
    for content_type, signatures in _ALLOWED_SIGNATURES.items():
        if any(data.startswith(signature) for signature in signatures):
            return content_type
    return None


def _normalise_display_name(filename: str | None, extension: str) -> str:
    raw_name = PurePosixPath(filename or "").name.strip()
    if not raw_name:
        return f"document.{extension}"

    stem = raw_name.rsplit(".", 1)[0] if "." in raw_name else raw_name
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("._-") or "document"
    return f"{safe_stem[:120]}.{extension}"


def validate_upload(
    *,
    data: bytes,
    filename: str | None,
    content_type: str | None,
    max_file_bytes: int,
) -> ValidatedUpload:
    if len(data) > max_file_bytes:
        raise UploadValidationError("File exceeds 10 MB limit", status_code=413)

    declared_content_type = (content_type or "").strip().lower()
    if declared_content_type not in _ALLOWED_SIGNATURES:
        raise UploadValidationError(
            "Only PDF, JPG, and PNG files are allowed",
            status_code=422,
        )

    detected_content_type = _detect_mime_type(data)
    if detected_content_type is None:
        raise UploadValidationError(
            "Unsupported file content. Upload a valid PDF, JPG, or PNG document.",
            status_code=422,
        )

    if detected_content_type != declared_content_type:
        raise UploadValidationError(
            "File content does not match the selected file type",
            status_code=422,
        )

    extension = _EXTENSIONS[detected_content_type]
    return ValidatedUpload(
        file_name=_normalise_display_name(filename, extension),
        content_type=detected_content_type,
        extension=extension,
    )
