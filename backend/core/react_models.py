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

class InformationWaitRequest(BaseModel):
    """A model-selected request for one missing fact.

    This is NOT an approval: it pauses the current admitted run so an
    authorized person/source can supply the named fact.  The server owns the
    job/execution/wait/correlation/subject binding; the model may only say
    what fact is missing and why it is needed.
    """
    question: str = Field(
        ..., min_length=1, max_length=400,
        description="The specific question an authorized person/source must answer.")
    missing_fact: Optional[str] = Field(
        None, max_length=200,
        description="The single fact/record the work cannot continue without.")
    subject: Optional[str] = Field(
        None, max_length=200,
        description="Optional business subject the fact belongs to (display only; "
                    "the server binds the authoritative subject).")


class ReActStep(BaseModel):
    """
    Validated output for a single step in the ReAct loop.
    The LLM must output one of:
    1. A Thought + Action (single tool call)
    2. A Thought + Actions (multiple independent tool calls, executed in parallel)
    3. A Thought + FinalAnswer (end of loop)
    4. A Thought + InformationWaitRequest (durably pause the same run)
    """
    thought: str = Field(..., description="The agent's reasoning about what to do next")
    action: Optional[ToolCall] = Field(None, description="A tool to execute, if the agent decides to act")
    actions: Optional[List[ToolCall]] = Field(None, description="Multiple INDEPENDENT tools to execute in parallel in this step (Workstream G). Tools that depend on each other's output must NOT be batched here.")
    final_answer: Optional[str] = Field(None, description="The final response to the user, if the agent is done")
    information_wait: Optional[InformationWaitRequest] = Field(
        None,
        description="Pause this admitted run for one missing fact. Not for "
                    "action approval; use the normal approval path for that.")
    confidence: float = Field(default=0.9, description="Confidence level in this thought/action (0.0 to 1.0)", ge=0.0, le=1.0)

class ReActObservation(BaseModel):
    """Structured observation from a tool execution."""
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
