from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_parent

router = APIRouter()


@router.get("/me/learners")
async def list_learners(payload: dict = Depends(require_parent), db: AsyncSession = Depends(get_db)):
    """List all learner profiles for the authenticated parent."""
    # TODO: implement
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/me/learners", status_code=status.HTTP_201_CREATED)
async def create_learner(payload: dict = Depends(require_parent), db: AsyncSession = Depends(get_db)):
    """Add a new learner profile under the parent account."""
    # TODO: implement
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.patch("/me/learners/{learner_id}")
async def update_learner(
    learner_id: str,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Update a learner profile."""
    # TODO: implement with ownership check
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")
