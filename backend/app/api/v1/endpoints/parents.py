from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_parent
from app.models.parent import Learner, ParentProfile
from app.schemas.parent import CreateLearnerRequest, LearnerResponse, UpdateLearnerRequest

router = APIRouter()


async def _get_parent_profile(payload: dict, db: AsyncSession) -> ParentProfile:
    profile = await db.scalar(
        select(ParentProfile).where(ParentProfile.user_id == UUID(payload["sub"]))
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found")
    return profile


@router.get("/me/learners", response_model=list[LearnerResponse])
async def list_learners(
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """List all learner profiles for the authenticated parent."""
    profile = await _get_parent_profile(payload, db)
    result = await db.scalars(
        select(Learner)
        .where(Learner.parent_id == profile.id, Learner.is_active == True)  # noqa: E712
        .order_by(Learner.created_at)
    )
    return result.all()


@router.post("/me/learners", response_model=LearnerResponse, status_code=status.HTTP_201_CREATED)
async def create_learner(
    body: CreateLearnerRequest,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Add a new learner profile under the parent account."""
    profile = await _get_parent_profile(payload, db)
    learner = Learner(parent_id=profile.id, **body.model_dump())
    db.add(learner)
    await db.flush()
    return learner


@router.patch("/me/learners/{learner_id}", response_model=LearnerResponse)
async def update_learner(
    learner_id: UUID,
    body: UpdateLearnerRequest,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Update a learner profile."""
    profile = await _get_parent_profile(payload, db)
    learner = await db.get(Learner, learner_id)
    if not learner or learner.parent_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(learner, field, value)

    return learner


@router.delete("/me/learners/{learner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_learner(
    learner_id: UUID,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a learner profile."""
    profile = await _get_parent_profile(payload, db)
    learner = await db.get(Learner, learner_id)
    if not learner or learner.parent_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")
    learner.is_active = False
