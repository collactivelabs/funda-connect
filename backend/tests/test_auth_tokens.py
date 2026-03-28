from uuid import uuid4

import pytest

from app.core.security import decode_refresh_token
from app.services.auth_tokens import (
    consume_email_verification_token,
    consume_password_reset_token,
    issue_email_verification_token,
    issue_password_reset_token,
    issue_refresh_session,
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

    refresh_token = await issue_refresh_session(user_id, redis)
    rotated_token = await rotate_refresh_session(refresh_token, redis)

    old_payload = decode_refresh_token(refresh_token)
    new_payload = decode_refresh_token(rotated_token)

    assert old_payload["jti"] != new_payload["jti"]
    assert old_payload["sub"] == new_payload["sub"] == str(user_id)


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
