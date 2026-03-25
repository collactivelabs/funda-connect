from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_any_user, require_parent

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Parent creates a booking. Returns PayFast payment URL."""
    # TODO: check slot availability, create pending booking, initiate PayFast payment
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.get("/my")
async def list_my_bookings(payload: dict = Depends(require_any_user)):
    """List bookings for the authenticated user (parent or teacher)."""
    # TODO: implement
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.get("/{booking_id}")
async def get_booking(booking_id: str, payload: dict = Depends(require_any_user)):
    """Get booking details."""
    # TODO: implement with ownership check
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: str,
    payload: dict = Depends(require_any_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a booking (subject to cancellation policy)."""
    # TODO: implement cancellation + refund logic
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/payfast/itn")
async def payfast_itn(db: AsyncSession = Depends(get_db)):
    """PayFast Instant Transaction Notification webhook."""
    # TODO: verify signature, update payment + booking status, trigger notifications
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")
