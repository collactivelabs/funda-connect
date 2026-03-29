from app.core.config import settings
from app.services.push import web_push_configured, web_push_public_key, web_push_supported_response


def test_web_push_supported_response_reflects_configuration(monkeypatch):
    monkeypatch.setattr(settings, "WEB_PUSH_PUBLIC_KEY", "public-key")
    monkeypatch.setattr(settings, "WEB_PUSH_PRIVATE_KEY", "private-key")
    monkeypatch.setattr(settings, "WEB_PUSH_SUBJECT", "mailto:test@example.com")

    assert web_push_configured() is True
    assert web_push_public_key() == "public-key"
    assert web_push_supported_response() == {
        "configured": True,
        "public_key": "public-key",
    }


def test_web_push_supported_response_handles_missing_configuration(monkeypatch):
    monkeypatch.setattr(settings, "WEB_PUSH_PUBLIC_KEY", "")
    monkeypatch.setattr(settings, "WEB_PUSH_PRIVATE_KEY", "")
    monkeypatch.setattr(settings, "WEB_PUSH_SUBJECT", "")

    assert web_push_configured() is False
    assert web_push_public_key() is None
    assert web_push_supported_response() == {
        "configured": False,
        "public_key": None,
    }
