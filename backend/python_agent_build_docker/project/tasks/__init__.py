# Tasks module for Celery
# This module contains all Celery tasks for the Python agent service

from . import notion_tasks
from . import ai_tasks
from . import data_processing_tasks
from . import email_tasks
from . import calendar_tasks
from . import slack_tasks
from . import asana_tasks
from . import trello_tasks
from . import reminder_tasks
from . import utility_tasks

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
