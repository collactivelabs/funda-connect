from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer()


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        return decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(*roles: str):
    async def _check(payload: dict = Depends(get_current_user_payload)) -> dict:
        if payload.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return payload
    return _check


# Convenience role guards
require_teacher = require_role("teacher")
require_parent = require_role("parent")
require_admin = require_role("admin")
require_any_user = require_role("teacher", "parent", "admin")

# Re-export for convenience
__all__ = [
    "get_db",
    "get_current_user_payload",
    "require_role",
    "require_teacher",
    "require_parent",
    "require_admin",
    "require_any_user",
]
