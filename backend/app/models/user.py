from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # parent | teacher | admin
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deletion_scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # Relationships
    teacher_profile: Mapped["TeacherProfile | None"] = relationship(  # noqa: F821
        "TeacherProfile", back_populates="user", uselist=False
    )
    parent_profile: Mapped["ParentProfile | None"] = relationship(  # noqa: F821
        "ParentProfile", back_populates="user", uselist=False
    )
    notifications: Mapped[list["Notification"]] = relationship(  # noqa: F821
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    notification_preferences: Mapped["NotificationPreference | None"] = relationship(  # noqa: F821
        "NotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role}]>"
