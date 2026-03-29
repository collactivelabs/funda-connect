import json
import secrets
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import hash_password
from app.models.parent import ParentProfile
from app.models.teacher import TeacherProfile
from app.models.user import User
from app.services.consent import record_registration_consents

_GOOGLE_OAUTH_STATE_PREFIX = "google_oauth_state"
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthFlowError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class GoogleOAuthState(BaseModel):
    flow: Literal["login", "register"]
    role: Literal["parent", "teacher"] | None = None
    redirect_path: str | None = None
    marketing_email: bool = False
    marketing_sms: bool = False


class GoogleOAuthProfile(BaseModel):
    subject: str
    email: EmailStr
    email_verified: bool
    given_name: str | None = None
    family_name: str | None = None
    name: str | None = None
    picture: str | None = None


def google_callback_url() -> str:
    return f"{settings.API_BASE_URL.rstrip('/')}/api/v1/auth/google/callback"


async def issue_google_oauth_state(state: GoogleOAuthState) -> str:
    redis = await get_redis()
    token = secrets.token_urlsafe(32)
    ttl_seconds = settings.GOOGLE_OAUTH_STATE_EXPIRE_MINUTES * 60
    await redis.set(
        f"{_GOOGLE_OAUTH_STATE_PREFIX}:{token}",
        state.model_dump_json(),
        ex=ttl_seconds,
    )
    return token


async def consume_google_oauth_state(token: str) -> GoogleOAuthState | None:
    redis = await get_redis()
    key = f"{_GOOGLE_OAUTH_STATE_PREFIX}:{token}"
    payload = await redis.get(key)
    if payload is None:
        return None
    await redis.delete(key)
    return GoogleOAuthState.model_validate(json.loads(payload))


def build_google_authorization_url(state_token: str) -> str:
    query = urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": google_callback_url(),
            "response_type": "code",
            "scope": "openid email profile",
            "prompt": "select_account",
            "state": state_token,
        }
    )
    return f"{_GOOGLE_AUTH_URL}?{query}"


async def exchange_google_code_for_profile(code: str) -> GoogleOAuthProfile:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": google_callback_url(),
                },
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
            access_token = token_payload.get("access_token")
            if not access_token:
                raise ValueError("Google did not return an access token")

            userinfo_response = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            profile_payload = userinfo_response.json()
    except httpx.HTTPError as exc:
        raise ValueError("Google OAuth request failed") from exc

    email = profile_payload.get("email")
    subject = profile_payload.get("sub")
    if not email or not subject:
        raise ValueError("Google profile response is missing required fields")

    return GoogleOAuthProfile(
        subject=str(subject),
        email=str(email),
        email_verified=bool(profile_payload.get("email_verified")),
        given_name=profile_payload.get("given_name"),
        family_name=profile_payload.get("family_name"),
        name=profile_payload.get("name"),
        picture=profile_payload.get("picture"),
    )


def _fallback_name_from_email(email: str) -> tuple[str, str]:
    local_part = email.split("@", 1)[0]
    tokens = [
        token.capitalize()
        for token in local_part.replace(".", " ").replace("_", " ").replace("-", " ").split()
        if token
    ]
    if not tokens:
        return ("Google", "User")
    if len(tokens) == 1:
        return (tokens[0], "User")
    return (tokens[0], " ".join(tokens[1:]))


def google_profile_name_parts(profile: GoogleOAuthProfile) -> tuple[str, str]:
    first_name = (profile.given_name or "").strip()
    last_name = (profile.family_name or "").strip()
    if first_name:
        return (first_name, last_name or "User")

    if profile.name:
        parts = [part for part in profile.name.strip().split() if part]
        if parts:
            if len(parts) == 1:
                return (parts[0], "User")
            return (parts[0], " ".join(parts[1:]))

    return _fallback_name_from_email(profile.email)


async def _find_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email))


async def resolve_google_oauth_user(
    db: AsyncSession,
    *,
    request: Request,
    oauth_state: GoogleOAuthState,
    profile: GoogleOAuthProfile,
) -> User:
    if not profile.email_verified:
        raise GoogleOAuthFlowError("email_unverified")

    user = await _find_user_by_email(db, str(profile.email))
    if user is not None:
        if not user.is_active:
            raise GoogleOAuthFlowError("account_disabled")
        if oauth_state.flow == "register":
            raise GoogleOAuthFlowError("already_registered")
        if not user.email_verified:
            user.email_verified = True
        if not user.avatar_url and profile.picture:
            user.avatar_url = profile.picture
        await db.flush()
        return user

    if oauth_state.flow == "login":
        raise GoogleOAuthFlowError("account_not_found")
    if oauth_state.role is None:
        raise GoogleOAuthFlowError("role_required")

    first_name, last_name = google_profile_name_parts(profile)
    user = User(
        email=profile.email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        first_name=first_name,
        last_name=last_name,
        role=oauth_state.role,
        avatar_url=profile.picture,
        email_verified=True,
    )
    db.add(user)
    await db.flush()

    if oauth_state.role == "teacher":
        db.add(TeacherProfile(user_id=user.id))
    else:
        db.add(ParentProfile(user_id=user.id))

    await record_registration_consents(
        db,
        user_id=user.id,
        request=request,
        marketing_email=oauth_state.marketing_email,
        marketing_sms=oauth_state.marketing_sms,
    )
    await db.flush()
    return user
