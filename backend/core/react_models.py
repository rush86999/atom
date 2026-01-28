from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class ToolCall(BaseModel):
    tool: str
    params: Dict[str, Any]

class ReActStep(BaseModel):
    thought: str = Field(description="Reasoning about the current state")
    action: Optional[ToolCall] = Field(None, description="Tool to execute, if any")
    final_answer: Optional[str] = Field(None, description="Final response to the user, if task is complete")

class ReActObservation(BaseModel):
    """Container for tool output"""
    content: str
    tool_name: str
    status: str = "success"
    error: Optional[str] = None
