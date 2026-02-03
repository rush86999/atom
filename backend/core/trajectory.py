import datetime
import json
import os
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
import aiofiles
from pydantic import BaseModel, Field


class TraceStepType(str, Enum):
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"

class TraceStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TraceStepType
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    content: str # Human readable description or logic
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ExecutionTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    request: str
    start_time: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    end_time: Optional[datetime.datetime] = None
    steps: List[TraceStep] = Field(default_factory=list)
    final_result: Optional[Dict[str, Any]] = None
    
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0

class TrajectoryRecorder:
    def __init__(self, user_id: str, request: str):
        self.trace = ExecutionTrace(user_id=user_id, request=request)
    
    def add_thought(self, content: str):
        self.trace.steps.append(TraceStep(
            type=TraceStepType.THOUGHT,
            content=content
        ))
        
    def add_tool_call(self, tool_name: str, args: Dict[str, Any]):
        self.trace.steps.append(TraceStep(
            type=TraceStepType.TOOL_CALL,
            content=f"Calling tool: {tool_name}",
            metadata={"tool": tool_name, "args": args}
        ))
        
    def add_tool_result(self, tool_name: str, result: Any, is_error: bool = False):
        self.trace.steps.append(TraceStep(
            type=TraceStepType.ERROR if is_error else TraceStepType.TOOL_RESULT,
            content=f"Result from {tool_name}",
            metadata={"tool": tool_name, "result": str(result)}
        ))

    def set_final_result(self, result: Dict[str, Any]):
        self.trace.final_result = result
        self.trace.steps.append(TraceStep(
            type=TraceStepType.FINAL_ANSWER,
            content="Generated Final Response",
            metadata={"result": result}
        ))
        self.trace.end_time = datetime.datetime.utcnow()

    async def save(self, directory: str = "logs/traces"):
        """Save trace to a JSON file"""
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        filename = f"{directory}/{self.trace.trace_id}.json"
        
        # Convert pydantic model to json
        data = self.trace.dict()
        # Handle datetime serialization
        def json_serial(obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            raise TypeError ("Type not serializable")

        async with aiofiles.open(filename, mode='w') as f:
            await f.write(json.dumps(data, default=json_serial, indent=2))
        
        return filename
