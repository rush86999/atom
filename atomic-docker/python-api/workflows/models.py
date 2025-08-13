from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from .database import Base

class CrontabSchedule(Base):
    __tablename__ = 'django_celery_beat_crontabschedule'
    id = Column(Integer, primary_key=True, index=True)
    minute = Column(String(64), default='*')
    hour = Column(String(64), default='*')
    day_of_week = Column(String(64), default='*')
    day_of_month = Column(String(64), default='*')
    month_of_year = Column(String(64), default='*')
    timezone = Column(String(64), default='UTC')

class PeriodicTask(Base):
    __tablename__ = 'django_celery_beat_periodictask'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True)
    task = Column(String(200))
    args = Column(Text, default='[]')
    kwargs = Column(Text, default='{}')
    queue = Column(String(200), nullable=True)
    exchange = Column(String(200), nullable=True)
    routing_key = Column(String(200), nullable=True)
    expires = Column(DateTime, nullable=True)
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    total_run_count = Column(Integer, default=0)
    date_changed = Column(DateTime)
    description = Column(Text, default='')
    crontab_id = Column(Integer, ForeignKey('django_celery_beat_crontabschedule.id'), nullable=True)

class WorkflowBase(BaseModel):
    name: str
    definition: Dict[str, Any]
    enabled: bool = False
    schedule: Optional[str] = None

class WorkflowCreate(WorkflowBase):
    pass

class Workflow(WorkflowBase):
    id: UUID
    user_id: UUID
    celery_task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
