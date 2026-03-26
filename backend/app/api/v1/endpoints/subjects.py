from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.curriculum import Subject
from app.schemas.teacher import SubjectResponse

router = APIRouter()


@router.get("", response_model=list[SubjectResponse])
async def list_subjects(db: AsyncSession = Depends(get_db)):
    """List all active subjects (public endpoint)."""
    result = await db.scalars(
        select(Subject).where(Subject.is_active == True).order_by(Subject.tier, Subject.name)  # noqa: E712
    )
    return result.all()
