from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "tutor_hub",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.alerts"],
)

celery_app.conf.beat_schedule = {
    "daily-overdue-payment-alerts": {
        "task": "app.tasks.alerts.send_overdue_alerts",
        "schedule": crontab(hour=7, minute=0),
    }
}
celery_app.conf.timezone = "UTC"
