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
import openai
import anthropic
import instructor
from dotenv import load_dotenv

from core.byok_endpoints import get_byok_manager

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

# --- Core Engine ---

class ReActAgentEngine:
    """
    Reusable engine for ReAct loops.
    Can be composed into any specific agent (Generic, Marketing, etc.).
    """
    def __init__(self, workspace_id: str = "default", model_override: str = None):
        self.workspace_id = workspace_id
        self.byok = get_byok_manager()
        self.model_override = model_override
        self.clients = {}

    def _get_client(self, provider_id: str):
        """Get instructor-patched client"""
        if provider_id in self.clients:
            return self.clients[provider_id]

        api_key = self.byok.get_api_key(provider_id)
        if not api_key:
            return None

        config = self.byok.providers.get(provider_id)
        base_url = config.base_url

        client = None
        mode = instructor.Mode.JSON

        if provider_id == "openai":
            client = openai.AsyncOpenAI(api_key=api_key)
            mode = instructor.Mode.TOOLS
        elif provider_id == "deepseek":
            client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url or "https://api.deepseek.com/v1")
            mode = instructor.Mode.JSON
        elif provider_id == "groq":
             client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url or "https://api.groq.com/openai/v1")
             mode = instructor.Mode.JSON
        elif provider_id == "anthropic":
            try:
                base_client = anthropic.AsyncAnthropic(api_key=api_key)
                client = instructor.from_anthropic(base_client)
                self.clients[provider_id] = client
                return client
            except: return None
        else:
             client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

        if client:
            patched = instructor.from_openai(client, mode=mode)
            self.clients[provider_id] = patched
            return patched
        return None

    async def run_loop(self,
                       user_input: str,
                       tools_definition: str,
                       tool_executor: callable,
                       system_prompt: str = "You are a helpful agent.",
                       max_loops: int = 10) -> AgentExecutionResult:
        """
        Execute the ReAct loop.

        Args:
            user_input: The task description
            tools_definition: String describing available tools (for LLM context)
            tool_executor: Async function(name, params) -> str result
            system_prompt: Base persona
            max_loops: Safety limit
        """
        start_time = time.time()

        # Select Provider (DeepSeek Preference)
        provider = self.byok.get_optimal_provider("reasoning", min_reasoning_level=4) or "openai"
        client = self._get_client(provider)

        # Fallback
        if not client and provider != "openai":
            provider = "openai"
            client = self._get_client("openai")

        if not client:
             # Last ditch: check any active key
             for pid in self.byok.providers.keys():
                 if self.byok.get_api_key(pid):
                     provider = pid
                     client = self._get_client(pid)
                     break

        if not client:
            raise Exception("No active AI provider found.")

        model_name = self.model_override or self.byok.providers[provider].model or "gpt-4o"

        # History Setup
        history = [
            {"role": "system", "content": f"{system_prompt}\n\nUse the ReAct pattern (Reason, Act, Observe). {tools_definition}"},
            {"role": "user", "content": user_input}
        ]

        steps_record = []
        final_answer = None
        status = "success"

        for i in range(max_loops):
            try:
                step_decision = await client.chat.completions.create(
                    model=model_name,
                    response_model=AgentStep,
                    messages=history,
                    max_retries=2
                )
            except Exception as e:
                logger.error(f"Reasoning error: {e}")
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
            provider=provider
        )
