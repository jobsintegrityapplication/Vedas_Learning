from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()

settings = get_settings()
celery = Celery("veda", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(task_track_started=True, task_serializer="json", accept_content=["json"], result_serializer="json")
celery.autodiscover_tasks(["app.workers"])
from app.workers import tasks as _tasks  # noqa: E402,F401
