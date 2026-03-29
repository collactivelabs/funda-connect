"""add booking attendance fields

Revision ID: f8a1c4d7b2e9
Revises: e3b7c2d9f6a1
Create Date: 2026-03-29 20:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8a1c4d7b2e9"
down_revision: Union[str, None] = "e3b7c2d9f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("no_show_reported_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("no_show_reported_by_role", sa.String(length=20), nullable=True))
    op.add_column("bookings", sa.Column("no_show_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "no_show_reason")
    op.drop_column("bookings", "no_show_reported_by_role")
    op.drop_column("bookings", "no_show_reported_at")
    op.drop_column("bookings", "completed_at")
    op.drop_column("bookings", "started_at")
