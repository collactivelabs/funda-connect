from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "fundaconnect",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
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
        # Run weekly payouts every Monday at 02:00 SAST
        "process-weekly-payouts": {
            "task": "app.tasks.payouts.process_weekly_payouts",
            "schedule": 60 * 60 * 24 * 7,  # weekly
        },
    },
)
