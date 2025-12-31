"""
ReAct Agent Engine (Core)
Implements the Reason -> Act -> Observe loop pattern for all agents.
Uses Instructor for type-safe reasoning and DeepSeek V3 for cost efficiency.
"""

import os
import json
import logging
import asyncio
import time
import datetime
from typing import Dict, Any, List, Optional, Union, Literal
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
import instructor
from dotenv import load_dotenv

from core.llm.byok_handler import BYOKHandler, QueryComplexity

# Configure logging
logger = logging.getLogger(__name__)

# --- Pydantic Models for ReAct ---

class ToolCall(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to execute")
    parameters: Dict[str, Any] = Field(..., description="Parameters for the tool")
    reasoning: str = Field(..., description="Thought process justifying this tool call")

class FinalAnswer(BaseModel):
    answer: str = Field(..., description="The final response to the user")
    reasoning: str = Field(..., description="Summary of how the answer was derived")

class AgentStep(BaseModel):
    """Represents a single step decision by the agent"""
    action: Union[ToolCall, FinalAnswer] = Field(..., description="Either a tool call or a final answer")

class ReActStepResult(BaseModel):
    """Records the outcome of a step for history"""
    step_number: int
    thought: str
    tool_call: Optional[str] = None
    tool_output: Optional[str] = None
    timestamp: float

class AgentExecutionResult(BaseModel):
    task_id: str
    status: str
    input: str
    output: str
    steps: List[ReActStepResult]
    execution_time_ms: float
    provider: str
    model: str

# --- Core Engine ---

class ReActAgentEngine:
    """
    Reusable engine for ReAct loops.
    Can be composed into any specific agent (Generic, Marketing, etc.).
    """
    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        # Use BYOKHandler for dynamic pricing and optimization
        self.byok = BYOKHandler(workspace_id=workspace_id)

    def _get_client_and_model(self, complexity: QueryComplexity, estimated_tokens: int, preferred_provider: str = None):
        """Get instructor-patched client and optimal model"""

        # 1. Determine optimal provider/model via BYOKHandler
        if preferred_provider:
            self.byok.default_provider_id = preferred_provider

        provider_id, model_name = self.byok.get_optimal_provider(
            complexity=complexity,
            task_type="react_loop", # Hint to prioritize reasoning capability
            estimated_tokens=estimated_tokens
        )

        # 2. Get raw client
        raw_client = self.byok.get_client(provider_id, async_client=True)
        if not raw_client:
            raise Exception(f"Failed to initialize client for provider: {provider_id}")

        # 3. Wrap with Instructor
        mode = instructor.Mode.JSON
        if provider_id == "openai":
            mode = instructor.Mode.TOOLS

        if provider_id == "anthropic":
             client = instructor.from_anthropic(raw_client)
        else:
             client = instructor.from_openai(raw_client, mode=mode)

        return client, provider_id, model_name

    def _estimate_tokens(self, text: str) -> int:
        """Rough estimate of tokens (chars / 4)"""
        return len(text) // 4

    async def run_loop(self,
                       user_input: str,
                       tools_definition: str,
                       tool_executor: callable,
                       system_prompt: str = "You are a helpful agent.",
                       max_loops: int = 10,
                       preferred_provider: str = None) -> AgentExecutionResult:
        """
        Execute the ReAct loop.
        """
        start_time = time.time()

        # Determine Complexity
        complexity = self.byok.analyze_query_complexity(user_input, task_type="react_loop")

        # Initial Context Estimate
        current_context_length = self._estimate_tokens(system_prompt + tools_definition + user_input)

        # Get Client & Model (Dynamically Selected)
        try:
            client, provider, model = self._get_client_and_model(complexity, current_context_length, preferred_provider)
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return AgentExecutionResult(
                task_id="failed", status="error", input=user_input, output=str(e), steps=[], execution_time_ms=0, provider="none", model="none"
            )

        # History Setup
        history = [
            {"role": "system", "content": f"{system_prompt}\n\nUse the ReAct pattern (Reason, Act, Observe). {tools_definition}"},
            {"role": "user", "content": user_input}
        ]

        steps_record = []
        final_answer = None
        status = "success"

        for i in range(max_loops):
            # Recalculate context size and switch model if needed?
            # For simplicity, we stick to the initial large-context selection if valid,
            # but ideally we might check if we are approaching limits.

            try:
                step_decision = await client.chat.completions.create(
                    model=model,
                    response_model=AgentStep,
                    messages=history,
                    max_retries=2
                )
            except Exception as e:
                logger.error(f"Reasoning error with {model}: {e}")
                final_answer = f"Error during reasoning: {e}"
                status = "error"
                break

            action = step_decision.action

            if isinstance(action, FinalAnswer):
                final_answer = action.answer
                steps_record.append(ReActStepResult(
                    step_number=i+1,
                    thought=action.reasoning,
                    tool_call="FinalAnswer",
                    tool_output=action.answer,
                    timestamp=time.time()
                ))
                break

            elif isinstance(action, ToolCall):
                # Record Thought
                steps_record.append(ReActStepResult(
                    step_number=i+1,
                    thought=action.reasoning,
                    tool_call=f"{action.tool_name}({action.parameters})",
                    timestamp=time.time()
                ))

                history.append({
                    "role": "assistant",
                    "content": f"Thought: {action.reasoning}\nCall: {action.tool_name}({json.dumps(action.parameters)})"
                })

                # Act
                try:
                    tool_output = await tool_executor(action.tool_name, action.parameters)
                except Exception as tool_err:
                    tool_output = f"Error executing tool: {tool_err}"

                steps_record[-1].tool_output = str(tool_output)

                history.append({
                    "role": "user",
                    "content": f"Tool Output: {tool_output}"
                })

                # Update Token Estimate
                current_context_length += self._estimate_tokens(str(tool_output))

        if not final_answer:
            final_answer = "Max loops reached."
            status = "timeout"

        return AgentExecutionResult(
            task_id=f"task_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
            status=status,
            input=user_input,
            output=final_answer,
            steps=steps_record,
            execution_time_ms=(time.time() - start_time) * 1000,
            provider=provider,
            model=model
        )
