import asyncio

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task
def anonymize_due_accounts() -> None:
    async def _run() -> list[str]:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from app.core.config import settings
        from app.services.account_lifecycle import (
            anonymize_due_accounts as anonymize_due_accounts_service,
        )

        engine = create_async_engine(settings.DATABASE_URL, echo=False)

        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                anonymized_ids = await anonymize_due_accounts_service(db)
                return [str(user_id) for user_id in anonymized_ids]
        finally:
            await engine.dispose()

    anonymized = asyncio.run(_run())
    if anonymized:
        logger.info("anonymize_due_accounts.done", count=len(anonymized), user_ids=anonymized)
