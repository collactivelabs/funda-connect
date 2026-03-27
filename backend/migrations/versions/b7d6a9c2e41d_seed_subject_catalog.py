"""seed subject catalog

Revision ID: b7d6a9c2e41d
Revises: 574066609d47
Create Date: 2026-03-27 13:50:00.000000

"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7d6a9c2e41d"
down_revision: Union[str, None] = "574066609d47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SUBJECTS = [
    {"name": "Mathematics", "slug": "mathematics", "icon": "📐", "tier": 1},
    {"name": "Mathematical Literacy", "slug": "mathematical-literacy", "icon": "🔢", "tier": 1},
    {"name": "Physical Sciences", "slug": "physical-sciences", "icon": "⚗️", "tier": 1},
    {"name": "Life Sciences", "slug": "life-sciences", "icon": "🧬", "tier": 1},
    {"name": "English Home Language", "slug": "english-home-language", "icon": "📚", "tier": 1},
    {"name": "English First Additional Language", "slug": "english-fal", "icon": "📖", "tier": 1},
    {"name": "Afrikaans Home Language", "slug": "afrikaans-home-language", "icon": "📚", "tier": 1},
    {"name": "History", "slug": "history", "icon": "🏛️", "tier": 1},
    {"name": "Geography", "slug": "geography", "icon": "🌍", "tier": 1},
    {"name": "Accounting", "slug": "accounting", "icon": "💼", "tier": 1},
    {"name": "Business Studies", "slug": "business-studies", "icon": "📊", "tier": 1},
    {"name": "Economics", "slug": "economics", "icon": "📈", "tier": 1},
    {"name": "Computer Applications Technology", "slug": "cat", "icon": "💻", "tier": 2},
    {"name": "Information Technology", "slug": "information-technology", "icon": "🖥️", "tier": 2},
    {"name": "Life Orientation", "slug": "life-orientation", "icon": "🌱", "tier": 2},
    {"name": "Visual Arts", "slug": "visual-arts", "icon": "🎨", "tier": 2},
    {"name": "Music", "slug": "music", "icon": "🎵", "tier": 2},
    {"name": "Drama", "slug": "drama", "icon": "🎭", "tier": 2},
    {"name": "Tourism", "slug": "tourism", "icon": "✈️", "tier": 2},
    {"name": "Consumer Studies", "slug": "consumer-studies", "icon": "🍳", "tier": 2},
    {"name": "Agricultural Sciences", "slug": "agricultural-sciences", "icon": "🌾", "tier": 2},
    {"name": "Engineering Graphics & Design", "slug": "egd", "icon": "📏", "tier": 2},
    {"name": "Foundation Phase (Gr R–3)", "slug": "foundation-phase", "icon": "🎒", "tier": 3},
    {"name": "Intermediate Phase (Gr 4–6)", "slug": "intermediate-phase", "icon": "📝", "tier": 3},
    {"name": "Cambridge A-Level Mathematics", "slug": "cambridge-a-math", "icon": "📐", "tier": 4},
    {"name": "Cambridge IGCSE Science", "slug": "cambridge-igcse-science", "icon": "🔬", "tier": 4},
]


subjects_table = sa.table(
    "subjects",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.String(length=100)),
    sa.column("slug", sa.String(length=120)),
    sa.column("description", sa.Text()),
    sa.column("tier", sa.Integer()),
    sa.column("is_active", sa.Boolean()),
    sa.column("icon", sa.String(length=50)),
)


def _subject_id(slug: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"fundaconnect:subject:{slug}")


def upgrade() -> None:
    rows = [
        {
            "id": _subject_id(subject["slug"]),
            "name": subject["name"],
            "slug": subject["slug"],
            "description": None,
            "tier": subject["tier"],
            "is_active": True,
            "icon": subject["icon"],
        }
        for subject in SUBJECTS
    ]
    insert_stmt = postgresql.insert(subjects_table).values(rows)
    op.execute(insert_stmt.on_conflict_do_nothing(index_elements=["slug"]))


def downgrade() -> None:
    op.execute(
        subjects_table.delete().where(
            subjects_table.c.slug.in_([subject["slug"] for subject in SUBJECTS])
        )
    )
