import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import observability


def test_init_sentry_is_noop_without_dsn(monkeypatch):
    monkeypatch.setattr(observability, "_sentry_initialized", False)
    monkeypatch.setattr(observability.settings, "SENTRY_DSN", "")

    assert observability.init_sentry(component="api") is False


def test_init_sentry_returns_false_when_sdk_is_unavailable(monkeypatch):
    monkeypatch.setattr(observability, "_sentry_initialized", False)
    monkeypatch.setattr(
        observability.settings,
        "SENTRY_DSN",
        "https://public@example.ingest.sentry.io/123",
    )

    def fake_import_module(name: str):
        raise ImportError(f"missing dependency for {name}")

    monkeypatch.setattr(observability.importlib, "import_module", fake_import_module)

    assert observability.init_sentry(component="api") is False


@pytest.mark.asyncio
async def test_build_readiness_report_is_ok_when_all_checks_pass(monkeypatch):
    async def ok() -> None:
        return None

    monkeypatch.setattr(observability, "check_database_health", ok)
    monkeypatch.setattr(observability, "check_redis_health", ok)
    monkeypatch.setattr(observability, "check_meilisearch_health", ok)
    monkeypatch.setattr(
        observability.settings,
        "SENTRY_DSN",
        "https://public@example.ingest.sentry.io/123",
    )

    report = await observability.build_readiness_report()

    assert report["status"] == "ok"
    assert report["services"]["database"]["status"] == "ok"
    assert report["services"]["redis"]["status"] == "ok"
    assert report["services"]["meilisearch"]["status"] == "ok"
    assert report["observability"]["sentry_enabled"] is True


@pytest.mark.asyncio
async def test_build_readiness_report_is_degraded_when_a_dependency_fails(monkeypatch):
    async def ok() -> None:
        return None

    async def fail() -> None:
        raise RuntimeError("Redis unavailable")

    monkeypatch.setattr(observability, "check_database_health", ok)
    monkeypatch.setattr(observability, "check_redis_health", fail)
    monkeypatch.setattr(observability, "check_meilisearch_health", ok)
    monkeypatch.setattr(observability.settings, "SENTRY_DSN", "")

    report = await observability.build_readiness_report()

    assert report["status"] == "degraded"
    assert report["services"]["redis"]["status"] == "error"
    assert "Redis unavailable" in report["services"]["redis"]["detail"]
    assert report["observability"]["sentry_enabled"] is False


def test_readiness_endpoint_returns_503_and_security_headers(monkeypatch):
    async def fake_build_readiness_report():
        return {
            "status": "degraded",
            "environment": "test",
            "services": {
                "database": {"status": "ok", "latency_ms": 1.0},
                "redis": {"status": "error", "latency_ms": 1.0, "detail": "down"},
                "meilisearch": {"status": "ok", "latency_ms": 1.0},
            },
            "observability": {"sentry_enabled": False, "release": None},
        }

    monkeypatch.setattr(main, "build_readiness_report", fake_build_readiness_report)
    client = TestClient(main.app)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.headers["x-content-type-options"] == "nosniff"
