from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_parent, require_teacher

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_review(payload: dict = Depends(require_parent), db: AsyncSession = Depends(get_db)):
    """Parent submits a review after a completed lesson."""
    # TODO: validate booking is completed and unreviewed
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/{review_id}/reply")
async def reply_to_review(
    review_id: str,
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Teacher replies to a review on one of their lessons."""
    # TODO: validate teacher owns the lesson being reviewed
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")
