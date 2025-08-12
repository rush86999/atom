from celery import Celery
import os

celery_app = Celery(
    "workflows",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    include=["workflows.tasks"],
)

if __name__ == "__main__":
    celery_app.start()
