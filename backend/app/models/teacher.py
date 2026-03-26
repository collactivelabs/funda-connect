import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class TeacherProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "teacher_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    bio: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(String(200))
    years_experience: Mapped[int | None] = mapped_column(Integer)
    hourly_rate_cents: Mapped[int | None] = mapped_column(Integer)  # ZAR in cents
    curricula: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)  # CAPS, Cambridge, IEB
    verification_status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending | under_review | verified | rejected | suspended
    is_listed: Mapped[bool] = mapped_column(Boolean, default=False)
    average_rating: Mapped[float | None] = mapped_column(Float)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_lessons: Mapped[int] = mapped_column(Integer, default=0)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    province: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="teacher_profile")  # noqa: F821
    subjects: Mapped[list["TeacherSubject"]] = relationship(
        "TeacherSubject", back_populates="teacher", cascade="all, delete-orphan"
    )
    documents: Mapped[list["VerificationDocument"]] = relationship(  # noqa: F821
        "VerificationDocument", back_populates="teacher", cascade="all, delete-orphan"
    )
    availability_slots: Mapped[list["AvailabilitySlot"]] = relationship(  # noqa: F821
        "AvailabilitySlot", back_populates="teacher", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="teacher")  # noqa: F821

    def __repr__(self) -> str:
        return f"<TeacherProfile user_id={self.user_id} status={self.verification_status}>"


class TeacherSubject(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "teacher_subjects"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teacher_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    grade_levels: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)  # ["Grade 10", "Grade 11"]
    curriculum: Mapped[str] = mapped_column(String(30))  # CAPS | Cambridge | IEB

    # Relationships
    teacher: Mapped["TeacherProfile"] = relationship("TeacherProfile", back_populates="subjects")
    subject: Mapped["Subject"] = relationship("Subject")  # noqa: F821
