from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import create_refresh_token, decode_refresh_token

_REFRESH_PREFIX = "auth:refresh"
_REFRESH_USED_PREFIX = "auth:refresh-used"
_REFRESH_USER_PREFIX = "auth:refresh-user"
_SESSION_PREFIX = "auth:session"
_SESSION_USER_PREFIX = "auth:session-user"
_VERIFY_EMAIL_PREFIX = "auth:verify-email"
_VERIFY_EMAIL_USER_PREFIX = "auth:verify-email-user"
_PASSWORD_RESET_PREFIX = "auth:password-reset"
_PASSWORD_RESET_USER_PREFIX = "auth:password-reset-user"


def _key(prefix: str, suffix: str) -> str:
    return f"{prefix}:{suffix}"


def _now() -> datetime:
    return datetime.now(UTC)


def _refresh_ttl_seconds() -> int:
    return settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _email_verification_ttl_seconds() -> int:
    return settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS * 60 * 60


def _password_reset_ttl_seconds() -> int:
    return settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES * 60


async def _redis_client(redis: aioredis.Redis | None = None) -> aioredis.Redis:
    return redis if redis is not None else await get_redis()


def _json_dumps(payload: dict[str, str]) -> str:
    return json.dumps(payload)


def _json_loads(value: str | None) -> dict[str, str] | None:
    if not value:
        return None

    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    return {
        str(key): "" if raw_value is None else str(raw_value) for key, raw_value in data.items()
    }


def _refresh_expires_at(now: datetime | None = None) -> datetime:
    timestamp = now or _now()
    return timestamp + timedelta(seconds=_refresh_ttl_seconds())


def _build_session_record(
    user_id: UUID,
    session_id: str,
    jti: str,
    *,
    user_agent: str | None,
    ip_address: str | None,
    created_at: datetime | None = None,
) -> dict[str, str]:
    now = _now()
    return {
        "id": session_id,
        "user_id": str(user_id),
        "current_jti": jti,
        "created_at": (created_at or now).isoformat(),
        "last_seen_at": now.isoformat(),
        "expires_at": _refresh_expires_at(now).isoformat(),
        "user_agent": (user_agent or "").strip(),
        "ip_address": (ip_address or "").strip(),
    }


def _deserialize_session_record(value: str | None) -> dict[str, object] | None:
    data = _json_loads(value)
    if not data:
        return None

    try:
        return {
            "id": data["id"],
            "user_id": UUID(data["user_id"]),
            "current_jti": data["current_jti"],
            "created_at": datetime.fromisoformat(data["created_at"]),
            "last_seen_at": datetime.fromisoformat(data["last_seen_at"]),
            "expires_at": datetime.fromisoformat(data["expires_at"]),
            "user_agent": data.get("user_agent") or None,
            "ip_address": data.get("ip_address") or None,
        }
    except (KeyError, ValueError):
        return None


async def _session_record(
    session_id: str,
    redis: aioredis.Redis,
) -> dict[str, object] | None:
    return _deserialize_session_record(await redis.get(_key(_SESSION_PREFIX, session_id)))


async def _revoke_legacy_refresh_sessions(
    user_id: UUID,
    redis: aioredis.Redis,
) -> int:
    user_key = _key(_REFRESH_USER_PREFIX, str(user_id))
    legacy_jtis = await redis.smembers(user_key)
    refresh_keys = [_key(_REFRESH_PREFIX, jti) for jti in legacy_jtis]

    revoked = len(legacy_jtis)
    if refresh_keys:
        await redis.delete(*refresh_keys)
    await redis.delete(user_key)
    return revoked


async def issue_refresh_session(
    user_id: UUID,
    redis: aioredis.Redis | None = None,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
    session_id: str | None = None,
    created_at: datetime | None = None,
) -> str:
    redis_client = await _redis_client(redis)
    jti = secrets.token_urlsafe(32)
    stable_session_id = session_id or secrets.token_urlsafe(18)
    token = create_refresh_token(user_id, jti, stable_session_id)
    ttl = _refresh_ttl_seconds()

    await redis_client.set(
        _key(_REFRESH_PREFIX, jti),
        _json_dumps(
            {
                "user_id": str(user_id),
                "session_id": stable_session_id,
            }
        ),
        ex=ttl,
    )
    await redis_client.set(
        _key(_SESSION_PREFIX, stable_session_id),
        _json_dumps(
            _build_session_record(
                user_id,
                stable_session_id,
                jti,
                user_agent=user_agent,
                ip_address=ip_address,
                created_at=created_at,
            )
        ),
        ex=ttl,
    )

    user_key = _key(_SESSION_USER_PREFIX, str(user_id))
    await redis_client.sadd(user_key, stable_session_id)
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
    user_id_raw = payload.get("sub")
    session_id = payload.get("sid")
    if not isinstance(jti, str) or not isinstance(user_id_raw, str):
        return

    refresh_key = _key(_REFRESH_PREFIX, jti)
    refresh_value = await redis_client.get(refresh_key)
    refresh_data = _json_loads(refresh_value)
    resolved_session_id = session_id
    if refresh_data:
        resolved_session_id = refresh_data.get("session_id") or resolved_session_id

    await redis_client.delete(refresh_key)

    if resolved_session_id:
        await redis_client.delete(_key(_SESSION_PREFIX, resolved_session_id))
        await redis_client.srem(_key(_SESSION_USER_PREFIX, user_id_raw), resolved_session_id)
        return

    await redis_client.srem(_key(_REFRESH_USER_PREFIX, user_id_raw), jti)


async def revoke_session_by_id(
    user_id: UUID,
    session_id: str,
    redis: aioredis.Redis | None = None,
) -> bool:
    redis_client = await _redis_client(redis)
    session = await _session_record(session_id, redis_client)
    if not session or session["user_id"] != user_id:
        return False

    await redis_client.delete(
        _key(_SESSION_PREFIX, session_id),
        _key(_REFRESH_PREFIX, str(session["current_jti"])),
    )
    await redis_client.srem(_key(_SESSION_USER_PREFIX, str(user_id)), session_id)
    return True


async def revoke_other_refresh_sessions(
    user_id: UUID,
    current_session_id: str | None,
    redis: aioredis.Redis | None = None,
) -> int:
    redis_client = await _redis_client(redis)
    session_ids = await redis_client.smembers(_key(_SESSION_USER_PREFIX, str(user_id)))

    revoked = 0
    for session_id in session_ids:
        if current_session_id and session_id == current_session_id:
            continue
        revoked += int(await revoke_session_by_id(user_id, session_id, redis_client))

    revoked += await _revoke_legacy_refresh_sessions(user_id, redis_client)
    return revoked


async def revoke_all_refresh_sessions(
    user_id: UUID,
    redis: aioredis.Redis | None = None,
) -> None:
    await revoke_other_refresh_sessions(user_id, current_session_id=None, redis=redis)


async def list_refresh_sessions(
    user_id: UUID,
    current_session_id: str | None = None,
    redis: aioredis.Redis | None = None,
) -> list[dict[str, object]]:
    redis_client = await _redis_client(redis)
    session_ids = await redis_client.smembers(_key(_SESSION_USER_PREFIX, str(user_id)))
    sessions: list[dict[str, object]] = []

    for session_id in session_ids:
        session = await _session_record(session_id, redis_client)
        if not session:
            await redis_client.srem(_key(_SESSION_USER_PREFIX, str(user_id)), session_id)
            continue
        if session["user_id"] != user_id:
            continue

        sessions.append(
            {
                "id": session["id"],
                "current": session["id"] == current_session_id,
                "created_at": session["created_at"],
                "last_seen_at": session["last_seen_at"],
                "expires_at": session["expires_at"],
                "user_agent": session["user_agent"],
                "ip_address": session["ip_address"],
            }
        )

    sessions.sort(
        key=lambda session: (
            not bool(session["current"]),
            -cast(datetime, session["last_seen_at"]).timestamp(),
        )
    )
    return sessions


async def rotate_refresh_session(
    refresh_token: str,
    redis: aioredis.Redis | None = None,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    redis_client = await _redis_client(redis)
    payload = decode_refresh_token(refresh_token)

    jti = payload.get("jti")
    if not isinstance(jti, str):
        raise ValueError("Invalid refresh token")

    refresh_key = _key(_REFRESH_PREFIX, jti)
    used_key = _key(_REFRESH_USED_PREFIX, jti)
    refresh_value = await redis_client.get(refresh_key)

    if refresh_value:
        refresh_data = _json_loads(refresh_value)
        if refresh_data:
            try:
                user_id = UUID(refresh_data["user_id"])
            except (KeyError, ValueError) as exc:
                raise ValueError("Invalid refresh token") from exc

            session_id = refresh_data.get("session_id")
            created_at: datetime | None = None
            session_user_agent = user_agent
            session_ip_address = ip_address

            if session_id:
                existing_session = await _session_record(session_id, redis_client)
                if existing_session:
                    created_at = cast(datetime, existing_session["created_at"])
                    session_user_agent = session_user_agent or cast(
                        str | None,
                        existing_session["user_agent"],
                    )
                    session_ip_address = session_ip_address or cast(
                        str | None,
                        existing_session["ip_address"],
                    )

            await redis_client.delete(refresh_key)
            await redis_client.set(
                used_key,
                _json_dumps(
                    {
                        "user_id": str(user_id),
                        "session_id": session_id or "",
                    }
                ),
                ex=_refresh_ttl_seconds(),
            )
            return await issue_refresh_session(
                user_id,
                redis_client,
                user_agent=session_user_agent,
                ip_address=session_ip_address,
                session_id=session_id,
                created_at=created_at,
            )

        try:
            user_id = UUID(refresh_value)
        except ValueError as exc:
            raise ValueError("Invalid refresh token") from exc

        await redis_client.delete(refresh_key)
        await redis_client.srem(_key(_REFRESH_USER_PREFIX, str(user_id)), jti)
        await redis_client.set(
            used_key,
            _json_dumps({"user_id": str(user_id), "session_id": ""}),
            ex=_refresh_ttl_seconds(),
        )
        return await issue_refresh_session(
            user_id,
            redis_client,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    used_value = await redis_client.get(used_key)
    used_data = _json_loads(used_value)
    if used_data and used_data.get("user_id"):
        await revoke_all_refresh_sessions(UUID(used_data["user_id"]), redis_client)
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
