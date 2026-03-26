from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_parent, require_teacher
from app.models.booking import Booking
from app.models.parent import ParentProfile
from app.models.review import Review
from app.models.teacher import TeacherProfile
from app.schemas.review import CreateReviewRequest, ReplyReviewRequest, ReviewResponse

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ReviewResponse)
async def create_review(
    body: CreateReviewRequest,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Parent submits a review after a completed lesson."""
    parent_profile = await db.scalar(
        select(ParentProfile).where(ParentProfile.user_id == UUID(payload["sub"]))
    )
    if not parent_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found")

    booking = await db.get(Booking, body.booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.parent_id != parent_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if booking.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only completed bookings can be reviewed",
        )

    # Check not already reviewed
    existing = await db.scalar(select(Review).where(Review.booking_id == body.booking_id))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking already reviewed")

    review = Review(
        booking_id=body.booking_id,
        teacher_id=booking.teacher_id,
        parent_id=parent_profile.id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(review)
    await db.flush()

    # Update booking status
    booking.status = "reviewed"

    return review


@router.post("/{review_id}/reply", response_model=ReviewResponse)
async def reply_to_review(
    review_id: UUID,
    body: ReplyReviewRequest,
    payload: dict = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Teacher replies to a review on one of their lessons."""
    teacher_profile = await db.scalar(
        select(TeacherProfile).where(TeacherProfile.user_id == UUID(payload["sub"]))
    )
    if not teacher_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher profile not found")

    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if review.teacher_id != teacher_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    review.teacher_reply = body.reply
    return review


@router.get("/teacher/{teacher_id}", response_model=list[ReviewResponse])
async def list_teacher_reviews(
    teacher_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Public: list published reviews for a teacher."""
    result = await db.scalars(
        select(Review)
        .where(Review.teacher_id == teacher_id, Review.status == "published")
        .order_by(Review.created_at.desc())
    )
    return result.all()
