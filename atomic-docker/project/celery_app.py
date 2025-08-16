from celery import Celery

app = Celery(
    'tasks',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
    include=['project.tasks']
)

from celery.schedules import crontab

app.conf.beat_schedule = {
    'check-budgets-daily': {
        'task': 'project.tasks.check_budget_alerts',
        'schedule': crontab(hour=0, minute=0),
    },
}

if __name__ == '__main__':
    app.start()
