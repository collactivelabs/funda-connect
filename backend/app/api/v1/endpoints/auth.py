from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_payload, get_db
from app.core.security import (
    create_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.parent import ParentProfile
from app.models.teacher import TeacherProfile
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    EmailRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth_tokens import (
    consume_email_verification_token,
    consume_password_reset_token,
    issue_email_verification_token,
    issue_password_reset_token,
    issue_refresh_session,
    list_refresh_sessions,
    revoke_all_refresh_sessions,
    revoke_other_refresh_sessions,
    revoke_refresh_session,
    revoke_session_by_id,
    rotate_refresh_session,
)
from app.tasks.notifications import (
    send_email_verification_message,
    send_password_reset_message,
)
from app.services.consent import record_registration_consents
from app.services.rate_limits import (
    AUTH_FORGOT_PASSWORD_RATE_LIMIT,
    AUTH_LOGIN_RATE_LIMIT,
    AUTH_REFRESH_RATE_LIMIT,
    AUTH_REGISTER_RATE_LIMIT,
    AUTH_RESET_PASSWORD_RATE_LIMIT,
    AUTH_VERIFY_EMAIL_RATE_LIMIT,
    AUTH_VERIFY_EMAIL_REQUEST_RATE_LIMIT,
    build_rate_limit_identifier,
    enforce_rate_limit,
)

router = APIRouter()

_REFRESH_COOKIE = "refresh_token"


def _cookie_options() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.is_production,
        "path": "/",
    }


def _frontend_url(path: str) -> str:
    return f"{settings.APP_BASE_URL.rstrip('/')}{path}"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(key=_REFRESH_COOKIE, value=token, **_cookie_options())


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def _client_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _user_id_from_refresh_token(refresh_token: str) -> UUID:
    payload = decode_refresh_token(refresh_token)
    return UUID(payload["sub"])


def _session_id_from_refresh_token(refresh_token: str | None) -> str | None:
    if not refresh_token:
        return None
    try:
        payload = decode_refresh_token(refresh_token)
    except ValueError:
        return None

    session_id = payload.get("sid")
    return session_id if isinstance(session_id, str) and session_id else None


async def _build_auth_response(user: User, request: Request) -> dict:
    return {
        "access_token": create_access_token(
            user.id,
            user.email,
            user.role,
            user.email_verified,
        ),
        "refresh_token": await issue_refresh_session(
            user.id,
            user_agent=_client_user_agent(request),
            ip_address=_client_ip(request),
        ),
        "user": user,
    }


async def _enforce_auth_rate_limit(
    request: Request,
    *,
    rate_limit,
    identifier_parts: tuple[object, ...],
    detail: str,
) -> None:
    await enforce_rate_limit(
        request,
        rate_limit=rate_limit,
        identifier=build_rate_limit_identifier(request, *identifier_parts),
        detail=detail,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user (parent or teacher)."""
    await _enforce_auth_rate_limit(
        request,
        rate_limit=AUTH_REGISTER_RATE_LIMIT,
        identifier_parts=(body.email,),
        detail="Too many registration attempts. Please try again later.",
    )
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
        phone=body.phone,
    )
    db.add(user)
    await db.flush()

    if body.role == "teacher":
        db.add(TeacherProfile(user_id=user.id))
    else:
        db.add(ParentProfile(user_id=user.id))

    await record_registration_consents(
        db,
        user_id=user.id,
        request=request,
        marketing_email=body.marketing_email,
        marketing_sms=body.marketing_sms,
    )

    await db.commit()
    await db.refresh(user)

    verification_token = await issue_email_verification_token(user.id)
    send_email_verification_message.apply_async(
        args=[
            user.email,
            user.first_name,
            _frontend_url(f"/verify-email?token={verification_token}"),
        ],
        countdown=2,
    )

    tokens = await _build_auth_response(user, request)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AuthResponse(
        access_token=tokens["access_token"],
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Login with email and password. Returns access token + sets refresh token cookie."""
    await _enforce_auth_rate_limit(
        request,
        rate_limit=AUTH_LOGIN_RATE_LIMIT,
        identifier_parts=(body.email,),
        detail="Too many login attempts. Please wait a moment and try again.",
    )
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    tokens = await _build_auth_response(user, request)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AuthResponse(
        access_token=tokens["access_token"],
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    """Exchange refresh token cookie for a new access token."""
    await _enforce_auth_rate_limit(
        request,
        rate_limit=AUTH_REFRESH_RATE_LIMIT,
        identifier_parts=(refresh_token_cookie,),
        detail="Too many token refresh attempts. Please try again shortly.",
    )
    if not refresh_token_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    try:
        new_refresh_token = await rotate_refresh_session(
            refresh_token_cookie,
            user_agent=_client_user_agent(request),
            ip_address=_client_ip(request),
        )
    except ValueError as exc:
        response.delete_cookie(_REFRESH_COOKIE, path="/")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    user_id = _user_id_from_refresh_token(refresh_token_cookie)
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token = create_access_token(
        user.id,
        user.email,
        user.role,
        user.email_verified,
    )
    _set_refresh_cookie(response, new_refresh_token)
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    """Invalidate refresh token and clear cookie."""
    if refresh_token_cookie:
        await revoke_refresh_session(refresh_token_cookie)
    response.delete_cookie(_REFRESH_COOKIE, path="/")
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def get_me(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """Return current authenticated user's profile."""
    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    payload: dict = Depends(get_current_user_payload),
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    """List active refresh sessions for the current user."""
    user_id = UUID(payload["sub"])
    current_session_id = _session_id_from_refresh_token(refresh_token_cookie)
    sessions = await list_refresh_sessions(user_id, current_session_id)
    return [SessionResponse.model_validate(session) for session in sessions]


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: str,
    response: Response,
    payload: dict = Depends(get_current_user_payload),
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    """Revoke a specific session for the current user."""
    user_id = UUID(payload["sub"])
    revoked = await revoke_session_by_id(user_id, session_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if session_id == _session_id_from_refresh_token(refresh_token_cookie):
        response.delete_cookie(_REFRESH_COOKIE, path="/")

    return MessageResponse(message="Session revoked")


@router.post("/sessions/revoke-others", response_model=MessageResponse)
async def revoke_other_sessions(
    payload: dict = Depends(get_current_user_payload),
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    """Revoke all other active sessions for the current user."""
    user_id = UUID(payload["sub"])
    current_session_id = _session_id_from_refresh_token(refresh_token_cookie)
    revoked = await revoke_other_refresh_sessions(user_id, current_session_id)
    return MessageResponse(message=f"Revoked {revoked} other session(s).")


@router.post("/verify-email/request", response_model=MessageResponse)
async def request_email_verification(
    body: EmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Send or resend an email verification link."""
    await _enforce_auth_rate_limit(
        request,
        rate_limit=AUTH_VERIFY_EMAIL_REQUEST_RATE_LIMIT,
        identifier_parts=(body.email,),
        detail="Too many verification email requests. Please try again later.",
    )
    user = await db.scalar(select(User).where(User.email == body.email))
    if user and user.is_active and not user.email_verified:
        verification_token = await issue_email_verification_token(user.id)
        send_email_verification_message.apply_async(
            args=[
                user.email,
                user.first_name,
                _frontend_url(f"/verify-email?token={verification_token}"),
            ],
            countdown=2,
        )

    return MessageResponse(
        message="If an account exists for that email, a verification link has been sent.",
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Mark a user's email address as verified using a one-time token."""
    await _enforce_auth_rate_limit(
        request,
        rate_limit=AUTH_VERIFY_EMAIL_RATE_LIMIT,
        identifier_parts=(body.token,),
        detail="Too many verification attempts. Please request a new link if needed.",
    )
    user_id = await consume_email_verification_token(body.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link is invalid or has expired",
        )

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.email_verified = True
    await db.commit()
    return MessageResponse(message="Email verified successfully.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: EmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset link if the account exists."""
    await _enforce_auth_rate_limit(
        request,
        rate_limit=AUTH_FORGOT_PASSWORD_RATE_LIMIT,
        identifier_parts=(body.email,),
        detail="Too many password reset requests. Please try again later.",
    )
    user = await db.scalar(select(User).where(User.email == body.email))
    if user and user.is_active:
        reset_token = await issue_password_reset_token(user.id)
        send_password_reset_message.apply_async(
            args=[
                user.email,
                user.first_name,
                _frontend_url(f"/reset-password?token={reset_token}"),
            ],
            countdown=2,
        )

    return MessageResponse(
        message="If an account exists for that email, a password reset link has been sent.",
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password using a one-time token."""
    await _enforce_auth_rate_limit(
        request,
        rate_limit=AUTH_RESET_PASSWORD_RATE_LIMIT,
        identifier_parts=(body.token,),
        detail="Too many password reset attempts. Please request a new link if needed.",
    )
    user_id = await consume_password_reset_token(body.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset link is invalid or has expired",
        )

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(body.new_password)
    await db.commit()
    await revoke_all_refresh_sessions(user.id)
    return MessageResponse(message="Password reset successfully. Please sign in again.")
