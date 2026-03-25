import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task
def process_weekly_payouts() -> None:
    """Process all pending teacher payouts for completed lessons."""
    logger.info("process_weekly_payouts.start")
    # TODO: query confirmed+completed payments with pending payouts, batch transfer
    logger.info("process_weekly_payouts.done")
