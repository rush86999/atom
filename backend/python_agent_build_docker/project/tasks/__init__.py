# Tasks module for Celery
# This module contains all Celery tasks for the Python agent service

from . import (
    ai_tasks,
    asana_tasks,
    calendar_tasks,
    data_processing_tasks,
    email_tasks,
    notion_tasks,
    reminder_tasks,
    slack_tasks,
    trello_tasks,
    utility_tasks,
)

# Import tasks to ensure they're registered
__all__ = [
    'notion_tasks',
    'ai_tasks',
    'data_processing_tasks',
    'email_tasks',
    'calendar_tasks',
    'slack_tasks',
    'asana_tasks',
    'trello_tasks',
    'reminder_tasks',
    'utility_tasks'
]
