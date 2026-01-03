from pydantic import BaseModel, Field, validator
from typing import Dict, Any, List, Optional, Literal
import datetime
import uuid

class TaskRequest(BaseModel):
    """Schema for a task request sent to an agent"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    intent: str
    input_data: Dict[str, Any]
    priority: Literal['low', 'medium', 'high', 'critical'] = 'medium'
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    @validator('user_id')
    def user_id_must_be_present(cls, v):
        if not v or not v.strip():
            raise ValueError('user_id must not be empty')
        return v

class TaskResult(BaseModel):
    """Schema for a task result returned by an agent"""
    task_id: str
    status: Literal['success', 'failure', 'retry']
    output_data: Dict[str, Any]
    error_message: Optional[str] = None
    execution_time_ms: float
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class AgentMessage(BaseModel):
    """Schema for inter-agent communication messages"""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str
    target_agent: str
    message_type: str
    payload: Dict[str, Any]
    
    # "Context Protection" - ensure context is passed
    context_id: str
