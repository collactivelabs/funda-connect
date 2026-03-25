from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(db: AsyncSession = Depends(get_db)):
    """Register a new user (parent or teacher)."""
    # TODO: implement registration
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/login")
async def login(db: AsyncSession = Depends(get_db)):
    """Login with email and password. Returns access token + sets refresh token cookie."""
    # TODO: implement login
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/refresh")
async def refresh_token(response: Response):
    """Exchange refresh token cookie for a new access token."""
    # TODO: implement token refresh
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/logout")
async def logout(response: Response):
    """Invalidate refresh token and clear cookie."""
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}


@router.get("/me")
async def get_me():
    """Return current authenticated user's profile."""
    # TODO: implement
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")
