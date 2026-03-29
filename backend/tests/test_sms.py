import pytest

from app.services import sms


def test_normalize_phone_number_supports_local_sa_numbers():
    assert sms.normalize_phone_number("082 123 4567") == "+27821234567"
    assert sms.normalize_phone_number("+27 82 123 4567") == "+27821234567"
    assert sms.normalize_phone_number("27821234567") == "+27821234567"


def test_configured_sms_provider_prefers_bulksms(monkeypatch):
    monkeypatch.setattr(sms.settings, "BULKSMS_USERNAME", "bulksms-user")
    monkeypatch.setattr(sms.settings, "BULKSMS_PASSWORD", "bulksms-pass")
    monkeypatch.setattr(sms.settings, "AT_API_KEY", "at-key")
    monkeypatch.setattr(sms.settings, "AT_USERNAME", "sandbox")

    assert sms.configured_sms_provider() == "bulksms"


@pytest.mark.asyncio
async def test_send_sms_message_requires_configured_provider(monkeypatch):
    monkeypatch.setattr(sms.settings, "BULKSMS_USERNAME", "")
    monkeypatch.setattr(sms.settings, "BULKSMS_PASSWORD", "")
    monkeypatch.setattr(sms.settings, "AT_API_KEY", "")
    monkeypatch.setattr(sms.settings, "AT_USERNAME", "")

    with pytest.raises(sms.SMSConfigurationError):
        await sms.send_sms_message(to="0821234567", message="Hello")


@pytest.mark.asyncio
async def test_send_sms_message_posts_to_bulksms(monkeypatch):
    monkeypatch.setattr(sms.settings, "BULKSMS_USERNAME", "bulksms-user")
    monkeypatch.setattr(sms.settings, "BULKSMS_PASSWORD", "bulksms-pass")
    monkeypatch.setattr(sms.settings, "AT_API_KEY", "")
    monkeypatch.setattr(sms.settings, "AT_USERNAME", "")
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 201
        text = "accepted"

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, timeout: float):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

    monkeypatch.setattr(sms.httpx, "AsyncClient", FakeAsyncClient)

    result = await sms.send_sms_message(to="082 123 4567", message="Lesson confirmed")

    assert result == {"provider": "bulksms", "recipient": "+27821234567"}
    assert captured["url"] == "https://api.bulksms.com/v1/messages"
    assert captured["kwargs"] == {
        "auth": ("bulksms-user", "bulksms-pass"),
        "json": {"to": "+27821234567", "body": "Lesson confirmed"},
        "headers": {"Accept": "application/json"},
    }
