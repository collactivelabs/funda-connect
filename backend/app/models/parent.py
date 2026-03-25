import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ParentProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "parent_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    province: Mapped[str | None] = mapped_column(String(50))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="parent_profile")  # noqa: F821
    learners: Mapped[list["Learner"]] = relationship(
        "Learner", back_populates="parent", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="parent")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ParentProfile user_id={self.user_id}>"


class Learner(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "learners"

    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    grade: Mapped[str] = mapped_column(String(20))  # "Grade 10", "Grade R"
    curriculum: Mapped[str] = mapped_column(String(30))  # CAPS | Cambridge | IEB
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    age: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    parent: Mapped["ParentProfile"] = relationship("ParentProfile", back_populates="learners")
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="learner")  # noqa: F821

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
