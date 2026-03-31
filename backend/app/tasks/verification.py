import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def notify_admin_verification_submitted(self, teacher_id: str) -> None:
    """Alert admin team when a teacher submits documents for review."""
    try:
        logger.info("notify_admin_verification_submitted", teacher_id=teacher_id)
        # TODO: send admin notification email
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def notify_teacher_verification_result(self, teacher_id: str, status: str) -> None:
    """Notify teacher of verification approval or rejection."""
    try:
        logger.info("notify_teacher_verification_result", teacher_id=teacher_id, status=status)
        # TODO: send email with outcome and next steps
    except Exception as exc:
        raise self.retry(exc=exc) from exc
