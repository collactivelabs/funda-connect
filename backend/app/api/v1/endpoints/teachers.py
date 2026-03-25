from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_teacher

router = APIRouter()


@router.get("")
async def list_teachers(
    subject: str | None = None,
    curriculum: str | None = None,
    grade: str | None = None,
    min_rate: int | None = None,
    max_rate: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Search and filter verified teachers."""
    # TODO: implement search via Meilisearch
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.get("/{teacher_id}")
async def get_teacher(teacher_id: str, db: AsyncSession = Depends(get_db)):
    """Get a teacher's public profile."""
    # TODO: implement
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.patch("/me/profile")
async def update_my_profile(
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Teacher updates their own profile."""
    # TODO: implement
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.get("/me/availability")
async def get_my_availability(payload: dict = Depends(require_teacher)):
    """Get teacher's weekly availability slots."""
    # TODO: implement
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.put("/me/availability")
async def set_my_availability(
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Set teacher's weekly availability slots."""
    # TODO: implement
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/me/documents")
async def upload_verification_document(
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Upload a verification document (ID, qualification, SACE cert, etc.)."""
    # TODO: implement S3 upload + document record
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")
