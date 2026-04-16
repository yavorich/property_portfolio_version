import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

celery_app = Celery(
    "config",
    broker=settings.CELERY_BROKER_URL,
    backend="rpc://",
)

celery_app.config_from_object(settings)
celery_app.autodiscover_tasks()
