import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_confirmation_email(self, booking_id: str, recipient_email: str) -> None:
    try:
        logger.info("send_booking_confirmation_email", booking_id=booking_id)
        # TODO: implement email sending via SES/Postmark
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_reminder_sms(self, booking_id: str, phone: str) -> None:
    try:
        logger.info("send_booking_reminder_sms", booking_id=booking_id)
        # TODO: implement SMS via BulkSMS / Africa's Talking
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_lesson_starting_soon(self, booking_id: str) -> None:
    try:
        logger.info("send_lesson_starting_soon", booking_id=booking_id)
        # TODO: send 15-minute reminder to both parent and teacher
    except Exception as exc:
        raise self.retry(exc=exc)
