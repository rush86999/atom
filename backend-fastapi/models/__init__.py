from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class ServiceType(str, Enum):
    GITHUB = "github"
    GOOGLE = "google"
    SLACK = "slack"

class WorkflowStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"

class BaseResponse(BaseModel):
    timestamp: datetime
    status: str
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
