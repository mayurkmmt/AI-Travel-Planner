from celery import Celery
from app.config import settings

celery_app = Celery(
    "ai_travel_planner",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    # Fail quickly when Redis is not running locally; the chat flow has a
    # background fallback for this case.
    broker_connection_timeout=3,
    broker_connection_retry=False,
    broker_transport_options={
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
        "retry_on_timeout": False,
    },
)
