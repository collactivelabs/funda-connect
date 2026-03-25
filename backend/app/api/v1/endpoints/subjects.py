from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db

router = APIRouter()


@router.get("")
async def list_subjects(db: AsyncSession = Depends(get_db)):
    """List all active subjects (public endpoint)."""
    # TODO: implement with Redis cache
    return {"subjects": []}
