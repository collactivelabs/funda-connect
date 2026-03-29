from __future__ import annotations

import importlib
from time import perf_counter
from typing import Any

import structlog
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis

logger = structlog.get_logger()

_sentry_initialized = False


def sentry_enabled() -> bool:
    return bool(settings.SENTRY_DSN.strip())


def init_sentry(*, component: str) -> bool:
    global _sentry_initialized

    if _sentry_initialized:
        return True
    if not sentry_enabled():
        return False

    try:
        sentry_sdk = importlib.import_module("sentry_sdk")
        redis_integration = importlib.import_module("sentry_sdk.integrations.redis")
        sqlalchemy_integration = importlib.import_module("sentry_sdk.integrations.sqlalchemy")
        integrations: list[Any] = [
            redis_integration.RedisIntegration(),
            sqlalchemy_integration.SqlalchemyIntegration(),
        ]

        if component == "api":
            fastapi_integration = importlib.import_module("sentry_sdk.integrations.fastapi")
            integrations.append(fastapi_integration.FastApiIntegration())
        elif component.startswith("celery"):
            celery_integration = importlib.import_module("sentry_sdk.integrations.celery")
            integrations.append(celery_integration.CeleryIntegration())
    except ImportError as exc:
        logger.warning("observability.sentry.unavailable", component=component, error=str(exc))
        return False

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN.strip(),
        environment=settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
        release=settings.SENTRY_RELEASE or None,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        send_default_pii=settings.SENTRY_SEND_DEFAULT_PII,
        integrations=integrations,
        enable_tracing=settings.SENTRY_TRACES_SAMPLE_RATE > 0,
    )

    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("service.component", component)
        scope.set_tag("service.name", "fundaconnect")

    _sentry_initialized = True
    logger.info(
        "observability.sentry.initialized",
        component=component,
        environment=settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
        release=settings.SENTRY_RELEASE or None,
    )
    return True


async def check_database_health() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))


async def check_redis_health() -> None:
    redis = await get_redis()
    pong = await redis.ping()
    if not pong:
        raise RuntimeError("Redis ping failed")


async def check_meilisearch_health() -> None:
    try:
        meilisearch = importlib.import_module("meilisearch")
    except ImportError as exc:
        raise RuntimeError("Meilisearch client is unavailable") from exc

    client = meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY)
    result = client.health()
    if isinstance(result, dict):
        status = result.get("status", "available")
    else:
        status = "available"
    if status != "available":
        raise RuntimeError(f"Meilisearch health check returned {status!r}")


async def _run_check(name: str, checker: Any) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        await checker()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            "detail": str(exc),
        }

    return {
        "status": "ok",
        "latency_ms": round((perf_counter() - started_at) * 1000, 2),
    }


async def build_readiness_report() -> dict[str, Any]:
    services = {
        "database": await _run_check("database", check_database_health),
        "redis": await _run_check("redis", check_redis_health),
        "meilisearch": await _run_check("meilisearch", check_meilisearch_health),
    }
    status = "ok" if all(service["status"] == "ok" for service in services.values()) else "degraded"

    return {
        "status": status,
        "environment": settings.ENVIRONMENT,
        "services": services,
        "observability": {
            "sentry_enabled": sentry_enabled(),
            "release": settings.SENTRY_RELEASE or None,
        },
    }
