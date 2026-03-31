from uuid import uuid4

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import settings
from app.models.teacher import TeacherProfile
from app.models.user import User
from app.schemas.auth import GoogleOAuthStartRequest
from app.services import google_oauth
from app.services.google_oauth import (
    GoogleOAuthFlowError,
    GoogleOAuthProfile,
    GoogleOAuthState,
    build_google_authorization_url,
    consume_google_oauth_state,
    issue_google_oauth_state,
    normalize_avatar_url,
    resolve_google_oauth_user,
)


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.values:
                del self.values[key]
                deleted += 1
        return deleted


class FakeSession:
    def __init__(self, existing_users: list[User] | None = None):
        self.users_by_email = {user.email: user for user in (existing_users or [])}
        self.added: list[object] = []
        self.consent_calls: list[dict[str, object]] = []

    def add(self, instance):
        self.added.append(instance)
        if isinstance(instance, User):
            self.users_by_email[instance.email] = instance

    async def flush(self):
        for instance in self.added:
            if getattr(instance, "id", None) is None:
                instance.id = uuid4()


async def fake_record_registration_consents(
    db: FakeSession,
    *,
    user_id,
    request,
    marketing_email: bool,
    marketing_sms: bool,
):
    db.consent_calls.append(
        {
            "user_id": user_id,
            "marketing_email": marketing_email,
            "marketing_sms": marketing_sms,
            "request_path": request.url.path,
        }
    )


async def fake_find_user_by_email(db: FakeSession, email: str) -> User | None:
    return db.users_by_email.get(email)


def build_request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/auth/google/callback",
        "headers": [(b"user-agent", b"pytest-agent")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_google_oauth_start_request_requires_role_and_consents_for_register():
    with pytest.raises(ValidationError):
        GoogleOAuthStartRequest(flow="register")


@pytest.mark.asyncio
async def test_google_oauth_state_is_one_time_use(monkeypatch):
    fake_redis = FakeRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(google_oauth, "get_redis", fake_get_redis)

    token = await issue_google_oauth_state(GoogleOAuthState(flow="login", redirect_path="/teacher"))

    first = await consume_google_oauth_state(token)
    second = await consume_google_oauth_state(token)

    assert first is not None
    assert first.redirect_path == "/teacher"
    assert second is None


def test_build_google_authorization_url_uses_configured_callback(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setattr(settings, "API_BASE_URL", "http://localhost:8000")

    url = build_google_authorization_url("state-token")

    assert "client_id=google-client-id" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fauth%2Fgoogle%2Fcallback" in url
    assert "scope=openid+email+profile" in url
    assert "state=state-token" in url


def test_normalize_avatar_url_rejects_overly_long_values():
    assert (
        normalize_avatar_url(" https://example.com/avatar.png ") == "https://example.com/avatar.png"
    )
    assert normalize_avatar_url("x" * 2049) is None


@pytest.mark.asyncio
async def test_resolve_google_oauth_user_registers_new_teacher_and_records_consents(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(google_oauth, "_find_user_by_email", fake_find_user_by_email)
    monkeypatch.setattr(
        google_oauth, "record_registration_consents", fake_record_registration_consents
    )

    profile = GoogleOAuthProfile(
        subject="google-subject-1",
        email="google-teacher@example.com",
        email_verified=True,
        given_name="Anele",
        family_name="Mokoena",
        picture="https://example.com/avatar.png",
    )

    user = await resolve_google_oauth_user(
        session,
        request=build_request(),
        oauth_state=GoogleOAuthState(
            flow="register",
            role="teacher",
            marketing_email=True,
            marketing_sms=False,
        ),
        profile=profile,
    )

    assert user.email == "google-teacher@example.com"
    assert user.role == "teacher"
    assert user.email_verified is True
    assert any(isinstance(instance, TeacherProfile) for instance in session.added)
    assert len(session.consent_calls) == 1
    assert session.consent_calls[0]["marketing_email"] is True
    assert session.consent_calls[0]["marketing_sms"] is False


@pytest.mark.asyncio
async def test_resolve_google_oauth_user_logs_in_existing_user_and_marks_verified(monkeypatch):
    user = User(
        id=uuid4(),
        email="existing-google@example.com",
        password_hash="hashed",
        first_name="Existing",
        last_name="User",
        role="parent",
        email_verified=False,
        avatar_url=None,
        is_active=True,
    )
    session = FakeSession(existing_users=[user])
    monkeypatch.setattr(google_oauth, "_find_user_by_email", fake_find_user_by_email)

    resolved = await resolve_google_oauth_user(
        session,
        request=build_request(),
        oauth_state=GoogleOAuthState(flow="login"),
        profile=GoogleOAuthProfile(
            subject="google-subject-2",
            email="existing-google@example.com",
            email_verified=True,
            given_name="Existing",
            family_name="User",
            picture="https://example.com/google.png",
        ),
    )

    assert resolved.id == user.id
    assert resolved.email_verified is True
    assert resolved.avatar_url == "https://example.com/google.png"


@pytest.mark.asyncio
async def test_resolve_google_oauth_user_rejects_register_for_existing_email(monkeypatch):
    session = FakeSession(
        existing_users=[
            User(
                email="existing@example.com",
                password_hash="hashed",
                first_name="Existing",
                last_name="User",
                role="parent",
                email_verified=True,
                is_active=True,
            )
        ]
    )
    monkeypatch.setattr(google_oauth, "_find_user_by_email", fake_find_user_by_email)

    with pytest.raises(GoogleOAuthFlowError, match="already_registered"):
        await resolve_google_oauth_user(
            session,
            request=build_request(),
            oauth_state=GoogleOAuthState(flow="register", role="parent"),
            profile=GoogleOAuthProfile(
                subject="google-subject-3",
                email="existing@example.com",
                email_verified=True,
                name="Existing User",
            ),
        )
