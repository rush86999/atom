from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any

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
