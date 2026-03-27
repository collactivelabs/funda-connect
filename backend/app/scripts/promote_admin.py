import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.parent import ParentProfile
from app.models.teacher import TeacherProfile
from app.models.user import User


async def promote_admin(email: str) -> int:
    normalized_email = email.strip().lower()
    if not normalized_email:
        print("Email is required.", file=sys.stderr)
        return 1

    async with AsyncSessionLocal() as session:
        user = await session.scalar(
            select(User)
            .where(User.email.ilike(normalized_email))
            .options(selectinload(User.teacher_profile), selectinload(User.parent_profile))
        )

        if not user:
            print(f"No user found for {normalized_email}.", file=sys.stderr)
            return 1

        previous_role = user.role
        if user.role == "admin":
            print(f"{user.email} is already an admin.")
            return 0

        user.role = "admin"
        await session.commit()

        print(f"Promoted {user.email} from {previous_role} to admin.")

        has_teacher_profile = isinstance(user.teacher_profile, TeacherProfile)
        has_parent_profile = isinstance(user.parent_profile, ParentProfile)
        if has_teacher_profile or has_parent_profile:
            print(
                "Note: this project uses a single active role per user. "
                "The user keeps any existing teacher/parent profile records, "
                "but new logins will authenticate as admin."
            )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote an existing FundaConnect user to admin by email."
    )
    parser.add_argument("--email", required=True, help="Email address of the user to promote")
    args = parser.parse_args()
    return asyncio.run(promote_admin(args.email))


if __name__ == "__main__":
    raise SystemExit(main())
