from celery import Celery
import os

# Create Celery application for workflows
celery_app = Celery(
    "workflows",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    include=["workflows.tasks"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="workflows",
    task_routes={
        "workflows.tasks.*": {"queue": "workflows"},
    },
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

# Beat schedule configuration
celery_app.conf.beat_schedule = {
    # Workflow-related periodic tasks
    "check-scheduled-workflows": {
        "task": "workflows.tasks.check_scheduled_workflows",
        "schedule": 60.0,  # Every minute
    },
    "cleanup-completed-workflows": {
        "task": "workflows.tasks.cleanup_completed_workflows",
        "schedule": 3600.0,  # Every hour
    },
}

if __name__ == "__main__":
    celery_app.start()
