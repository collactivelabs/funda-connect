"""add lesson notes and topics

Revision ID: e3b7c2d9f6a1
Revises: a1c3d5e7f9b2
Create Date: 2026-03-29 14:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e3b7c2d9f6a1"
down_revision: Union[str, None] = "a1c3d5e7f9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("lesson_notes", sa.Text(), nullable=True))
    op.add_column(
        "bookings",
        sa.Column(
            "topics_covered",
            postgresql.ARRAY(sa.String(length=255)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column("bookings", "topics_covered", server_default=None)


def downgrade() -> None:
    op.drop_column("bookings", "topics_covered")
    op.drop_column("bookings", "lesson_notes")
