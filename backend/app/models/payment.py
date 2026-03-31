import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Payment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    gateway: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # payfast | manual (Ozow planned)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(100), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    # pending | complete | failed | refunded | partially_refunded | cancelled
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gateway_metadata: Mapped[dict | None] = mapped_column(JSONB)  # raw ITN payload

    booking: Mapped["Booking"] = relationship("Booking", back_populates="payment")  # noqa: F821
    payout: Mapped["Payout | None"] = relationship(
        "Payout", back_populates="payment", uselist=False
    )
    refund: Mapped["Refund | None"] = relationship(
        "Refund", back_populates="payment", uselist=False
    )


class Payout(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payouts"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teacher_profiles.id"), nullable=False, index=True
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending | processing | paid | failed
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bank_reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    payment: Mapped["Payment"] = relationship("Payment", back_populates="payout")


class Refund(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "refunds"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending | processing | refunded | failed | cancelled
    reason: Mapped[str | None] = mapped_column(Text)
    requested_by_role: Mapped[str | None] = mapped_column(String(20))
    policy_code: Mapped[str | None] = mapped_column(String(50))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gateway_reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    payment: Mapped["Payment"] = relationship("Payment", back_populates="refund")


class Dispute(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "disputes"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    raised_by_role: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    # open | resolved
    resolution: Mapped[str | None] = mapped_column(String(20))
    original_booking_status: Mapped[str] = mapped_column(String(30), nullable=False)
    admin_notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    booking: Mapped["Booking"] = relationship("Booking", back_populates="dispute")  # noqa: F821


class VerificationDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "verification_documents"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # id_document | qualification | sace_certificate | nrso_clearance | reference_letter
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | approved | rejected
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    teacher: Mapped["TeacherProfile"] = relationship(  # noqa: F821
        "TeacherProfile", back_populates="documents"
    )
