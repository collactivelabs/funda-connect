"""add teacher blocked dates

Revision ID: c4d9e2a7f1b3
Revises: f8a1c4d7b2e9
Create Date: 2026-03-29 21:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c4d9e2a7f1b3"
down_revision: Union[str, None] = "f8a1c4d7b2e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blocked_dates",
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", "date", name="uq_blocked_dates_teacher_date"),
    )
    op.create_index(op.f("ix_blocked_dates_date"), "blocked_dates", ["date"], unique=False)
    op.create_index(op.f("ix_blocked_dates_teacher_id"), "blocked_dates", ["teacher_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_blocked_dates_teacher_id"), table_name="blocked_dates")
    op.drop_index(op.f("ix_blocked_dates_date"), table_name="blocked_dates")
    op.drop_table("blocked_dates")
