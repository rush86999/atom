import asyncio
import datetime
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union, Callable

from core.llm_service import LLMService
from core.react_models import ReActStep, ToolCall, ReActObservation
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class AgentExecutionResponse(BaseModel):
    """Result of an agent orchestration run."""
    status: str = "completed"
    final_answer: Optional[str] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    total_loops: int = 0
    error: Optional[str] = None

class AgentOrchestrator:
    """
    Core orchestrator for autonomous agent loops.
    Implements a standardized ReAct pattern usable by workflows and endpoints.
    """
    def __init__(
        self, 
        llm_service: LLMService, 
        model: str = "quality",
        max_loops: int = 10,
        system_instruction: Optional[str] = None
    ):
        self.llm_service = llm_service
        self.model = model
        self.max_loops = max_loops
        self.system_instruction = system_instruction or "You are an autonomous AI agent. Use tools to solve the task."
        self.history: List[Dict[str, str]] = []

    async def run(
        self, 
        task: str, 
        toolbox: Dict[str, Callable],
        context: Optional[Dict[str, Any]] = None
    ) -> AgentExecutionResponse:
        """
        Execute the ReAct loop for a specific task using a provided toolbox.
        
        Args:
            task: The natural language task description.
            toolbox: Dictionary mapping tool names to async functions.
            context: Optional execution context (history, memory, etc.)
        """
        start_time = time.time()
        self.history = [{"role": "user", "content": task}]
        if context:
            self.history.insert(0, {"role": "system", "content": f"Context: {json.dumps(context)}"})
        
        steps_record = []
        final_answer = None
        tool_descriptions = self._generate_tool_descriptions(toolbox)
        
        full_system_instruction = f"{self.system_instruction}\n\nAvailable Tools:\n{tool_descriptions}"
        
        for i in range(self.max_loops):
            # 1. REASON
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in self.history])
            
            try:
                # Use structured output for the decision
                step_decision = await self.llm_service.generate_structured(
                    prompt=prompt,
                    response_model=ReActStep,
                    system_instruction=full_system_instruction,
                    model=self.model
                )
            except Exception as e:
                logger.error(f"Agent reasoning failed at loop {i}: {e}")
                return AgentExecutionResponse(
                    status="failed",
                    error=f"Reasoning error: {str(e)}",
                    steps=steps_record,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    total_loops=i
                )

            if not step_decision:
                break
            
            thought = step_decision.thought
            action = step_decision.action
            
            # Record the step
            step_data = {
                "loop": i + 1,
                "thought": thought,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            
            # 2. ACT / FINALIZE
            if step_decision.final_answer:
                final_answer = step_decision.final_answer
                step_data["action"] = "final_answer"
                step_data["result"] = final_answer
                steps_record.append(step_data)
                break
            
            if action:
                tool_name = action.tool
                tool_params = action.params
                step_data["action"] = f"{tool_name}({json.dumps(tool_params)})"
                
                self.history.append({
                    "role": "assistant",
                    "content": f"Thought: {thought}\nAction: {tool_name}({json.dumps(tool_params)})"
                })
                
                # 3. OBSERVE (Execute tool)
                if tool_name in toolbox:
                    try:
                        tool_func = toolbox[tool_name]
                        # Check if tool_func is a coroutine or just a regular function
                        if asyncio.iscoroutinefunction(tool_func):
                            observation = await tool_func(**tool_params)
                        else:
                            observation = tool_func(**tool_params)
                        
                        observation_str = str(observation)
                        step_data["result"] = observation_str
                    except Exception as tool_error:
                        logger.warning(f"Tool {tool_name} execution failed: {tool_error}")
                        observation_str = f"Error executing tool {tool_name}: {str(tool_error)}"
                        step_data["result"] = observation_str
                        step_data["error"] = str(tool_error)
                else:
                    observation_str = f"Error: Tool '{tool_name}' not found in toolbox."
                    step_data["result"] = observation_str
                
                steps_record.append(step_data)
                self.history.append({
                    "role": "user",
                    "content": f"Observation: {observation_str}"
                })
            else:
                # No action and no final answer? 
                logger.warning(f"Agent loop {i} produced no action or result.")
                step_data["action"] = "none"
                steps_record.append(step_data)
                break

        execution_time = (time.time() - start_time) * 1000
        
        return AgentExecutionResponse(
            status="completed" if final_answer else "exhausted",
            final_answer=final_answer or "Maximum reasoning loops reached without a final answer.",
            steps=steps_record,
            execution_time_ms=execution_time,
            total_loops=len(steps_record)
        )

    def _generate_tool_descriptions(self, toolbox: Dict[str, Callable]) -> str:
        """Simple extraction of tool metadata (In production, use docstring parsing)."""
        descriptions = []
        for name, func in toolbox.items():
            doc = getattr(func, "__doc__", "No description available.") or "No description available."
            # Clean up docstring
            doc = doc.strip().split("\n")[0]
            descriptions.append(f"- {name}: {doc}")
        return "\n".join(descriptions)
