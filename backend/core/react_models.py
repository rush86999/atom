"""
Pydantic Models for Robust ReAct Loop Parsing
Based on 2025 Architecture: PydanticAI wraps each step of the loop in a validation layer.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Structured representation of a tool call decided by the agent."""
    tool: str = Field(..., description="The name of the tool/function to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")

class ReActStep(BaseModel):
    """
    Validated output for a single step in the ReAct loop.
    The LLM must output one of:
    1. A Thought + Action (tool call)
    2. A Thought + FinalAnswer (end of loop)
    """
    thought: str = Field(..., description="The agent's reasoning about what to do next")
    action: Optional[ToolCall] = Field(None, description="A tool to execute, if the agent decides to act")
    final_answer: Optional[str] = Field(None, description="The final response to the user, if the agent is done")
    confidence: float = Field(default=0.9, description="Confidence level in this thought/action (0.0 to 1.0)", ge=0.0, le=1.0)
    
    class Config:
        # Ensure at least one of action or final_answer is provided
        # This is validated in the agent loop itself for flexibility
        pass

class ReActObservation(BaseModel):
    """Structured observation from a tool execution."""
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
