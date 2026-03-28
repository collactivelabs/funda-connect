"""add booking disputes

Revision ID: 9f4a2d1c6b7e
Revises: 8c1f9d7a2b3e
Create Date: 2026-03-29 00:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f4a2d1c6b7e"
down_revision: Union[str, None] = "8c1f9d7a2b3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "disputes",
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("raised_by_role", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolution", sa.String(length=20), nullable=True),
        sa.Column("original_booking_status", sa.String(length=30), nullable=False),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
    )
    op.create_index(op.f("ix_disputes_booking_id"), "disputes", ["booking_id"], unique=True)
    op.create_index(op.f("ix_disputes_status"), "disputes", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_disputes_status"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_booking_id"), table_name="disputes")
    op.drop_table("disputes")
