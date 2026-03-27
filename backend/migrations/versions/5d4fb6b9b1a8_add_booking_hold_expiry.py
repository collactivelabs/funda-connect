"""add booking hold expiry

Revision ID: 5d4fb6b9b1a8
Revises: b7d6a9c2e41d
Create Date: 2026-03-27 16:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5d4fb6b9b1a8"
down_revision: Union[str, None] = "b7d6a9c2e41d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_bookings_hold_expires_at"), "bookings", ["hold_expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bookings_hold_expires_at"), table_name="bookings")
    op.drop_column("bookings", "hold_expires_at")
