from __future__ import annotations

import secrets
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import create_refresh_token, decode_refresh_token

_REFRESH_PREFIX = "auth:refresh"
_REFRESH_USED_PREFIX = "auth:refresh-used"
_REFRESH_USER_PREFIX = "auth:refresh-user"
_VERIFY_EMAIL_PREFIX = "auth:verify-email"
_VERIFY_EMAIL_USER_PREFIX = "auth:verify-email-user"
_PASSWORD_RESET_PREFIX = "auth:password-reset"
_PASSWORD_RESET_USER_PREFIX = "auth:password-reset-user"


def _key(prefix: str, suffix: str) -> str:
    return f"{prefix}:{suffix}"


def _refresh_ttl_seconds() -> int:
    return settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _email_verification_ttl_seconds() -> int:
    return settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS * 60 * 60


def _password_reset_ttl_seconds() -> int:
    return settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES * 60


async def _redis_client(redis: aioredis.Redis | None = None) -> aioredis.Redis:
    return redis if redis is not None else await get_redis()


async def issue_refresh_session(
    user_id: UUID,
    redis: aioredis.Redis | None = None,
) -> str:
    redis_client = await _redis_client(redis)
    jti = secrets.token_urlsafe(32)
    token = create_refresh_token(user_id, jti)
    ttl = _refresh_ttl_seconds()
    user_key = _key(_REFRESH_USER_PREFIX, str(user_id))

    await redis_client.set(_key(_REFRESH_PREFIX, jti), str(user_id), ex=ttl)
    await redis_client.sadd(user_key, jti)
    await redis_client.expire(user_key, ttl)
    return token


async def revoke_refresh_session(
    refresh_token: str,
    redis: aioredis.Redis | None = None,
) -> None:
    redis_client = await _redis_client(redis)
    try:
        payload = decode_refresh_token(refresh_token)
    except ValueError:
        return

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not isinstance(jti, str) or not isinstance(user_id, str):
        return

    await redis_client.delete(_key(_REFRESH_PREFIX, jti))
    await redis_client.srem(_key(_REFRESH_USER_PREFIX, user_id), jti)


async def revoke_all_refresh_sessions(
    user_id: UUID,
    redis: aioredis.Redis | None = None,
) -> None:
    redis_client = await _redis_client(redis)
    user_key = _key(_REFRESH_USER_PREFIX, str(user_id))
    jtis = await redis_client.smembers(user_key)
    refresh_keys = [_key(_REFRESH_PREFIX, jti) for jti in jtis]

    if refresh_keys:
        await redis_client.delete(*refresh_keys)
    await redis_client.delete(user_key)


async def rotate_refresh_session(
    refresh_token: str,
    redis: aioredis.Redis | None = None,
) -> str:
    redis_client = await _redis_client(redis)
    payload = decode_refresh_token(refresh_token)

    jti = payload.get("jti")
    user_id_raw = payload.get("sub")
    if not isinstance(jti, str) or not isinstance(user_id_raw, str):
        raise ValueError("Invalid refresh token")

    refresh_key = _key(_REFRESH_PREFIX, jti)
    used_key = _key(_REFRESH_USED_PREFIX, jti)
    user_id = UUID(user_id_raw)

    if await redis_client.get(refresh_key):
        await redis_client.delete(refresh_key)
        await redis_client.srem(_key(_REFRESH_USER_PREFIX, user_id_raw), jti)
        await redis_client.set(used_key, user_id_raw, ex=_refresh_ttl_seconds())
        return await issue_refresh_session(user_id, redis_client)

    if await redis_client.get(used_key):
        await revoke_all_refresh_sessions(user_id, redis_client)
        raise ValueError("Refresh token reuse detected")

    raise ValueError("Invalid refresh token")


async def issue_email_verification_token(
    user_id: UUID,
    redis: aioredis.Redis | None = None,
) -> str:
    redis_client = await _redis_client(redis)
    ttl = _email_verification_ttl_seconds()
    user_key = _key(_VERIFY_EMAIL_USER_PREFIX, str(user_id))
    previous_token = await redis_client.get(user_key)
    if previous_token:
        await redis_client.delete(_key(_VERIFY_EMAIL_PREFIX, previous_token))

    token = secrets.token_urlsafe(32)
    await redis_client.set(_key(_VERIFY_EMAIL_PREFIX, token), str(user_id), ex=ttl)
    await redis_client.set(user_key, token, ex=ttl)
    return token


async def consume_email_verification_token(
    token: str,
    redis: aioredis.Redis | None = None,
) -> UUID | None:
    redis_client = await _redis_client(redis)
    user_id = await redis_client.get(_key(_VERIFY_EMAIL_PREFIX, token))
    if not user_id:
        return None

    await redis_client.delete(
        _key(_VERIFY_EMAIL_PREFIX, token),
        _key(_VERIFY_EMAIL_USER_PREFIX, user_id),
    )
    return UUID(user_id)


async def issue_password_reset_token(
    user_id: UUID,
    redis: aioredis.Redis | None = None,
) -> str:
    redis_client = await _redis_client(redis)
    ttl = _password_reset_ttl_seconds()
    user_key = _key(_PASSWORD_RESET_USER_PREFIX, str(user_id))
    previous_token = await redis_client.get(user_key)
    if previous_token:
        await redis_client.delete(_key(_PASSWORD_RESET_PREFIX, previous_token))

    token = secrets.token_urlsafe(32)
    await redis_client.set(_key(_PASSWORD_RESET_PREFIX, token), str(user_id), ex=ttl)
    await redis_client.set(user_key, token, ex=ttl)
    return token


async def consume_password_reset_token(
    token: str,
    redis: aioredis.Redis | None = None,
) -> UUID | None:
    redis_client = await _redis_client(redis)
    user_id = await redis_client.get(_key(_PASSWORD_RESET_PREFIX, token))
    if not user_id:
        return None

    await redis_client.delete(
        _key(_PASSWORD_RESET_PREFIX, token),
        _key(_PASSWORD_RESET_USER_PREFIX, user_id),
    )
    return UUID(user_id)
