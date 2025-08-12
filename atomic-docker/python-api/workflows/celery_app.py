from celery import Celery

celery_app = Celery(
    "workflows",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
    include=["workflows.tasks"],
)

if __name__ == "__main__":
    celery_app.start()
