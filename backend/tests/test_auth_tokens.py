from uuid import uuid4

import pytest

from app.core.security import decode_refresh_token
from app.services.auth_tokens import (
    consume_email_verification_token,
    consume_password_reset_token,
    issue_email_verification_token,
    issue_password_reset_token,
    issue_refresh_session,
    list_refresh_sessions,
    revoke_other_refresh_sessions,
    revoke_session_by_id,
    rotate_refresh_session,
)


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, *keys):
        count = 0
        for key in keys:
            if key in self.values:
                del self.values[key]
                count += 1
            if key in self.sets:
                del self.sets[key]
                count += 1
        return count

    async def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    async def srem(self, key, *values):
        if key in self.sets:
            for value in values:
                self.sets[key].discard(value)

    async def smembers(self, key):
        return set(self.sets.get(key, set()))

    async def expire(self, key, seconds):
        return True


@pytest.mark.asyncio
async def test_email_verification_tokens_are_one_time_use():
    redis = FakeRedis()
    user_id = uuid4()

    token = await issue_email_verification_token(user_id, redis)

    assert await consume_email_verification_token(token, redis) == user_id
    assert await consume_email_verification_token(token, redis) is None


@pytest.mark.asyncio
async def test_password_reset_tokens_invalidate_previous_token():
    redis = FakeRedis()
    user_id = uuid4()

    old_token = await issue_password_reset_token(user_id, redis)
    new_token = await issue_password_reset_token(user_id, redis)

    assert await consume_password_reset_token(old_token, redis) is None
    assert await consume_password_reset_token(new_token, redis) == user_id


@pytest.mark.asyncio
async def test_refresh_rotation_invalidates_old_token_and_issues_new_one():
    redis = FakeRedis()
    user_id = uuid4()

    refresh_token = await issue_refresh_session(
        user_id,
        redis,
        user_agent="Safari",
        ip_address="127.0.0.1",
    )
    rotated_token = await rotate_refresh_session(
        refresh_token,
        redis,
        user_agent="Safari",
        ip_address="127.0.0.1",
    )

    old_payload = decode_refresh_token(refresh_token)
    new_payload = decode_refresh_token(rotated_token)

    assert old_payload["jti"] != new_payload["jti"]
    assert old_payload["sub"] == new_payload["sub"] == str(user_id)
    assert old_payload["sid"] == new_payload["sid"]

    sessions = await list_refresh_sessions(user_id, old_payload["sid"], redis)
    assert len(sessions) == 1
    assert sessions[0]["current"] is True
    assert sessions[0]["user_agent"] == "Safari"
    assert sessions[0]["ip_address"] == "127.0.0.1"


@pytest.mark.asyncio
async def test_refresh_reuse_detection_revokes_rotated_session_family():
    redis = FakeRedis()
    user_id = uuid4()

    refresh_token = await issue_refresh_session(user_id, redis)
    rotated_token = await rotate_refresh_session(refresh_token, redis)

    with pytest.raises(ValueError, match="reuse detected"):
        await rotate_refresh_session(refresh_token, redis)

    with pytest.raises(ValueError, match="Invalid refresh token"):
        await rotate_refresh_session(rotated_token, redis)


@pytest.mark.asyncio
async def test_revoke_specific_session_only_removes_target_session():
    redis = FakeRedis()
    user_id = uuid4()

    current_token = await issue_refresh_session(user_id, redis, user_agent="Chrome")
    other_token = await issue_refresh_session(user_id, redis, user_agent="Firefox")

    current_session_id = decode_refresh_token(current_token)["sid"]
    other_session_id = decode_refresh_token(other_token)["sid"]

    revoked = await revoke_session_by_id(user_id, other_session_id, redis)

    assert revoked is True
    sessions = await list_refresh_sessions(user_id, current_session_id, redis)
    assert len(sessions) == 1
    assert sessions[0]["id"] == current_session_id
    assert sessions[0]["current"] is True


@pytest.mark.asyncio
async def test_revoke_other_sessions_preserves_current_session():
    redis = FakeRedis()
    user_id = uuid4()

    current_token = await issue_refresh_session(user_id, redis, user_agent="Chrome")
    await issue_refresh_session(user_id, redis, user_agent="Firefox")
    await issue_refresh_session(user_id, redis, user_agent="Edge")

    current_session_id = decode_refresh_token(current_token)["sid"]

    revoked = await revoke_other_refresh_sessions(user_id, current_session_id, redis)

    assert revoked == 2
    sessions = await list_refresh_sessions(user_id, current_session_id, redis)
    assert len(sessions) == 1
    assert sessions[0]["id"] == current_session_id
