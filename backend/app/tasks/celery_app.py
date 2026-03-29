from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "fundaconnect",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.account_lifecycle",
        "app.tasks.lessons",
        "app.tasks.notifications",
        "app.tasks.payouts",
        "app.tasks.verification",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Johannesburg",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    beat_schedule={
        # Release expired payment holds so slots become bookable again
        "expire-pending-booking-holds": {
            "task": "app.tasks.lessons.expire_pending_booking_holds",
            "schedule": 60,
        },
        # Move due lessons into an in-progress state so attendance actions are available.
        "start-due-lessons": {
            "task": "app.tasks.lessons.start_due_lessons",
            "schedule": 60,
        },
        # Mark completed lessons and create payout records every 15 minutes
        "auto-complete-lessons": {
            "task": "app.tasks.lessons.auto_complete_lessons",
            "schedule": 60 * 15,
        },
        # Weekly payout batch every Monday at 02:00 SAST
        "process-weekly-payouts": {
            "task": "app.tasks.payouts.process_weekly_payouts",
            "schedule": 60 * 60 * 24 * 7,
        },
        # Daily sweep to anonymize accounts whose deletion grace period has elapsed
        "anonymize-due-accounts": {
            "task": "app.tasks.account_lifecycle.anonymize_due_accounts",
            "schedule": 60 * 60 * 24,
        },
    },
)
