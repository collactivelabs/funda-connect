"""Seed initial subjects. Run once: python -m app.seeds.subjects"""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.curriculum import Subject

SUBJECTS = [
    # Tier 1 — launch subjects
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
    # Tier 2 — phase 2
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
    # Tier 3 — primary school
    {"name": "Foundation Phase (Gr R–3)", "slug": "foundation-phase", "icon": "🎒", "tier": 3},
    {"name": "Intermediate Phase (Gr 4–6)", "slug": "intermediate-phase", "icon": "📝", "tier": 3},
    # Tier 4 — Cambridge / IEB specific
    {"name": "Cambridge A-Level Mathematics", "slug": "cambridge-a-math", "icon": "📐", "tier": 4},
    {"name": "Cambridge IGCSE Science", "slug": "cambridge-igcse-science", "icon": "🔬", "tier": 4},
]


async def seed():
    async with AsyncSessionLocal() as session:
        existing = await session.scalars(select(Subject.slug))
        existing_slugs = set(existing.all())

        added = 0
        for s in SUBJECTS:
            if s["slug"] not in existing_slugs:
                session.add(Subject(**s))
                added += 1

        await session.commit()
        print(f"Seeded {added} subjects ({len(existing_slugs)} already existed).")


if __name__ == "__main__":
    asyncio.run(seed())
