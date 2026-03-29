"""add account deletion fields

Revision ID: e6c4b9d1a7f2
Revises: f4b8c1e9a2d3
Create Date: 2026-03-29 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6c4b9d1a7f2"
down_revision: Union[str, None] = "f4b8c1e9a2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deletion_scheduled_for", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_users_deletion_requested_at"), "users", ["deletion_requested_at"], unique=False)
    op.create_index(op.f("ix_users_deletion_scheduled_for"), "users", ["deletion_scheduled_for"], unique=False)
    op.create_index(op.f("ix_users_anonymized_at"), "users", ["anonymized_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_anonymized_at"), table_name="users")
    op.drop_index(op.f("ix_users_deletion_scheduled_for"), table_name="users")
    op.drop_index(op.f("ix_users_deletion_requested_at"), table_name="users")
    op.drop_column("users", "anonymized_at")
    op.drop_column("users", "deletion_scheduled_for")
    op.drop_column("users", "deletion_requested_at")
