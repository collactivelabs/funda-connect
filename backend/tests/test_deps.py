from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import deps
from app.models.user import User


class FakeSession:
    def __init__(self, user: User | None):
        self.user = user

    async def get(self, model, primary_key):
        return self.user


@pytest.mark.asyncio
async def test_get_current_user_payload_rejects_inactive_user(monkeypatch):
    user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash="hashed",
        first_name="Test",
        last_name="User",
        role="parent",
        is_active=False,
    )

    monkeypatch.setattr(
        deps,
        "decode_access_token",
        lambda token: {"sub": str(user.id), "role": user.role},
    )

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user_payload(credentials=credentials, db=FakeSession(user))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Account disabled"


@pytest.mark.asyncio
async def test_get_current_user_payload_returns_payload_for_active_user(monkeypatch):
    user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash="hashed",
        first_name="Test",
        last_name="User",
        role="teacher",
        is_active=True,
    )

    expected_payload = {"sub": str(user.id), "role": user.role}
    monkeypatch.setattr(deps, "decode_access_token", lambda token: expected_payload)

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    payload = await deps.get_current_user_payload(credentials=credentials, db=FakeSession(user))

    assert payload == expected_payload
