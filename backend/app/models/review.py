import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Review(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reviews"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teacher_profiles.id"), nullable=False, index=True
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_profiles.id"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–5
    comment: Mapped[str | None] = mapped_column(Text)
    teacher_reply: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="published")
    # published | flagged | hidden

    booking: Mapped["Booking"] = relationship("Booking", back_populates="review")  # noqa: F821
