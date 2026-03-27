import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class AvailabilitySlot(UUIDMixin, TimestampMixin, Base):
    """Teacher's recurring weekly availability."""

    __tablename__ = "availability_slots"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teacher_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "09:00" (SAST)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)    # "10:00" (SAST)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    teacher: Mapped["TeacherProfile"] = relationship(  # noqa: F821
        "TeacherProfile", back_populates="availability_slots"
    )


class Booking(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bookings"

    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_profiles.id"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teacher_profiles.id"), nullable=False, index=True
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False
    )

    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # State machine: pending_payment → confirmed → in_progress → completed → reviewed
    # pending_payment can also lapse into expired if the payment hold times out.
    status: Mapped[str] = mapped_column(String(30), default="pending_payment", index=True)

    # Pricing (ZAR in cents)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    teacher_payout_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    # Lesson delivery
    video_room_url: Mapped[str | None] = mapped_column(String(500))
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring_booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Notes
    parent_notes: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    # Relationships
    parent: Mapped["ParentProfile"] = relationship("ParentProfile", back_populates="bookings")  # noqa: F821
    teacher: Mapped["TeacherProfile"] = relationship("TeacherProfile", back_populates="bookings")  # noqa: F821
    learner: Mapped["Learner"] = relationship("Learner", back_populates="bookings")  # noqa: F821
    subject: Mapped["Subject"] = relationship("Subject")  # noqa: F821
    payment: Mapped["Payment | None"] = relationship(  # noqa: F821
        "Payment", back_populates="booking", uselist=False
    )
    review: Mapped["Review | None"] = relationship(  # noqa: F821
        "Review", back_populates="booking", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Booking {self.id} [{self.status}] @ {self.scheduled_at}>"
