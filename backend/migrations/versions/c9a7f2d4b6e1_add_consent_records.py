"""add consent records

Revision ID: c9a7f2d4b6e1
Revises: e6c4b9d1a7f2
Create Date: 2026-03-29 12:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9a7f2d4b6e1"
down_revision: Union[str, None] = "e6c4b9d1a7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consent_records",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("consent_type", sa.String(length=50), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consent_records_consent_type"), "consent_records", ["consent_type"], unique=False)
    op.create_index(op.f("ix_consent_records_granted_at"), "consent_records", ["granted_at"], unique=False)
    op.create_index(op.f("ix_consent_records_revoked_at"), "consent_records", ["revoked_at"], unique=False)
    op.create_index(op.f("ix_consent_records_user_id"), "consent_records", ["user_id"], unique=False)
    op.create_index(
        "ix_consent_records_user_type_active",
        "consent_records",
        ["user_id", "consent_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_consent_records_user_type_active", table_name="consent_records")
    op.drop_index(op.f("ix_consent_records_user_id"), table_name="consent_records")
    op.drop_index(op.f("ix_consent_records_revoked_at"), table_name="consent_records")
    op.drop_index(op.f("ix_consent_records_granted_at"), table_name="consent_records")
    op.drop_index(op.f("ix_consent_records_consent_type"), table_name="consent_records")
    op.drop_table("consent_records")
