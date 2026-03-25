from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Subject(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[int] = mapped_column(Integer, default=1)  # 1=launch, 2,3,4=later
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    icon: Mapped[str | None] = mapped_column(String(50))  # emoji or icon name

    def __repr__(self) -> str:
        return f"<Subject {self.name}>"
