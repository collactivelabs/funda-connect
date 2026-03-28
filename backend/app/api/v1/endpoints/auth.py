from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_payload, get_db
from app.core.security import create_access_token, hash_password, verify_password
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
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth_tokens import (
    consume_email_verification_token,
    consume_password_reset_token,
    issue_email_verification_token,
    issue_password_reset_token,
    issue_refresh_session,
    revoke_all_refresh_sessions,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.tasks.notifications import (
    send_email_verification_message,
    send_password_reset_message,
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


async def _build_auth_response(user: User) -> dict:
    return {
        "access_token": create_access_token(
            user.id,
            user.email,
            user.role,
            user.email_verified,
        ),
        "refresh_token": await issue_refresh_session(user.id),
        "user": user,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user (parent or teacher)."""
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

    tokens = await _build_auth_response(user)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AuthResponse(
        access_token=tokens["access_token"],
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Login with email and password. Returns access token + sets refresh token cookie."""
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    tokens = await _build_auth_response(user)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AuthResponse(
        access_token=tokens["access_token"],
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    """Exchange refresh token cookie for a new access token."""
    if not refresh_token_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    try:
        new_refresh_token = await rotate_refresh_session(refresh_token_cookie)
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


def _user_id_from_refresh_token(refresh_token: str):
    from app.core.security import decode_refresh_token

    payload = decode_refresh_token(refresh_token)
    return UUID(payload["sub"])


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


@router.post("/verify-email/request", response_model=MessageResponse)
async def request_email_verification(
    body: EmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send or resend an email verification link."""
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
    db: AsyncSession = Depends(get_db),
):
    """Mark a user's email address as verified using a one-time token."""
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
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset link if the account exists."""
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
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password using a one-time token."""
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
