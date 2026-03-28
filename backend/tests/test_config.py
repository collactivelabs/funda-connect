import pytest

from app.core.config import Settings


def test_parse_allowed_origins_supports_comma_separated_values():
    parsed = Settings.parse_allowed_origins("http://localhost:3001, http://localhost:8000")

    assert parsed == ["http://localhost:3001", "http://localhost:8000"]


def test_parse_allowed_origins_supports_json_arrays():
    parsed = Settings.parse_allowed_origins('["http://localhost:3001", "https://example.com"]')

    assert parsed == ["http://localhost:3001", "https://example.com"]


def test_parse_allowed_origins_rejects_invalid_input_types():
    with pytest.raises(TypeError, match="must be a list or comma-separated string"):
        Settings.parse_allowed_origins(123)
