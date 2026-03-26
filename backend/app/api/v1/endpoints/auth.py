from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_payload, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.parent import ParentProfile
from app.models.teacher import TeacherProfile
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse

router = APIRouter()

_REFRESH_COOKIE = "refresh_token"
_COOKIE_OPTS = dict(httponly=True, samesite="lax", secure=False, path="/")


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(key=_REFRESH_COOKIE, value=token, **_COOKIE_OPTS)


def _build_auth_response(user: User) -> dict:
    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
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
    await db.flush()  # get user.id before creating profile

    if body.role == "teacher":
        db.add(TeacherProfile(user_id=user.id))
    else:
        db.add(ParentProfile(user_id=user.id))

    tokens = _build_auth_response(user)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AuthResponse(access_token=tokens["access_token"], user=UserResponse.model_validate(user))


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

    tokens = _build_auth_response(user)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AuthResponse(access_token=tokens["access_token"], user=UserResponse.model_validate(user))


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
        payload = decode_refresh_token(refresh_token_cookie)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = await db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    tokens = _build_auth_response(user)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AuthResponse(access_token=tokens["access_token"], user=UserResponse.model_validate(user))


@router.post("/logout")
async def logout(response: Response):
    """Invalidate refresh token and clear cookie."""
    response.delete_cookie(_REFRESH_COOKIE, path="/")
    return {"message": "Logged out"}


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
