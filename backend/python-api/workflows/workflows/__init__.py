
# Workflows tasks package
# This package contains Celery tasks for workflow automation

from . import tasks

# Import tasks to ensure they're registered with Celery
__all__ = ['tasks']
