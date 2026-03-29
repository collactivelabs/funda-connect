import hashlib
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.core.redis import get_redis


@dataclass(frozen=True)
class RateLimit:
    scope: str
    limit: int
    window_seconds: int


AUTH_REGISTER_RATE_LIMIT = RateLimit("auth.register", limit=5, window_seconds=3600)
AUTH_LOGIN_RATE_LIMIT = RateLimit("auth.login", limit=10, window_seconds=300)
AUTH_REFRESH_RATE_LIMIT = RateLimit("auth.refresh", limit=30, window_seconds=300)
AUTH_VERIFY_EMAIL_REQUEST_RATE_LIMIT = RateLimit("auth.verify_email_request", limit=5, window_seconds=3600)
AUTH_VERIFY_EMAIL_RATE_LIMIT = RateLimit("auth.verify_email", limit=10, window_seconds=3600)
AUTH_FORGOT_PASSWORD_RATE_LIMIT = RateLimit("auth.forgot_password", limit=5, window_seconds=3600)
AUTH_RESET_PASSWORD_RATE_LIMIT = RateLimit("auth.reset_password", limit=10, window_seconds=3600)
BOOKING_MUTATION_RATE_LIMIT = RateLimit("booking.mutation", limit=20, window_seconds=300)
TEACHER_UPLOAD_RATE_LIMIT = RateLimit("teacher.document_upload", limit=10, window_seconds=3600)
ADMIN_MUTATION_RATE_LIMIT = RateLimit("admin.mutation", limit=60, window_seconds=300)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        forwarded_ip = forwarded_for.split(",")[0].strip()
        if forwarded_ip:
            return forwarded_ip
    return request.client.host if request.client else "unknown"


def build_rate_limit_identifier(request: Request, *parts: object) -> str:
    raw_parts = [_client_ip(request)]
    raw_parts.extend(str(part).strip().lower() for part in parts if part not in {None, ""})
    raw = "|".join(raw_parts)
    return hashlib.sha256(raw.encode()).hexdigest()


async def enforce_rate_limit(
    request: Request,
    *,
    rate_limit: RateLimit,
    identifier: str,
    detail: str | None = None,
) -> None:
    redis = await get_redis()
    key = f"rate-limit:{rate_limit.scope}:{identifier}"

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, rate_limit.window_seconds)

    ttl = await redis.ttl(key)
    retry_after = max(ttl, 1)
    if current > rate_limit.limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail or "Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
