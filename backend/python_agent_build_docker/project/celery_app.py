from celery import Celery
import os

# Create Celery application
app = Celery(
    'project',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
    include=['project.tasks']
)

# Configure Celery
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
)

# Beat schedule configuration
app.conf.beat_schedule = {
    # Add periodic tasks here
    # Example:
    # 'process-scheduled-every-5-minutes': {
    #     'task': 'project.tasks.process_scheduled_tasks',
    #     'schedule': 300.0,  # Every 5 minutes
    # },
}

# Optional: Import and register tasks
try:
    # This will import tasks from project.tasks module
    from project import tasks
    # Tasks are automatically registered when imported
except ImportError as e:
    print(f"Warning: Could not import tasks module: {e}")

if __name__ == '__main__':
    app.start()
