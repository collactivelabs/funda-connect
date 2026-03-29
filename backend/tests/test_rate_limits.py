import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.services import rate_limits
from app.services.rate_limits import RateLimit, build_rate_limit_identifier, enforce_rate_limit


class FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        value = self.counts.get(key, 0) + 1
        self.counts[key] = value
        return value

    async def expire(self, key: str, seconds: int) -> None:
        self.ttls[key] = seconds

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -1)


def build_request(*, client_ip: str = "127.0.0.1") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": [],
        "client": (client_ip, 12345),
    }
    return Request(scope)


def test_build_rate_limit_identifier_hashes_request_fingerprint():
    request = build_request(client_ip="203.0.113.9")

    identifier = build_rate_limit_identifier(request, "test@example.com")

    assert identifier != "test@example.com"
    assert len(identifier) == 64


@pytest.mark.asyncio
async def test_enforce_rate_limit_raises_after_limit(monkeypatch):
    fake_redis = FakeRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(rate_limits, "get_redis", fake_get_redis)
    request = build_request()
    limit = RateLimit("test.scope", limit=2, window_seconds=60)
    identifier = build_rate_limit_identifier(request, "teacher-123")

    await enforce_rate_limit(request, rate_limit=limit, identifier=identifier)
    await enforce_rate_limit(request, rate_limit=limit, identifier=identifier)

    with pytest.raises(HTTPException) as exc_info:
        await enforce_rate_limit(request, rate_limit=limit, identifier=identifier)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}
