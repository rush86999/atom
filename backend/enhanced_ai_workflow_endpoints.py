#!/usr/bin/env python3
"""
Enhanced AI Workflow Endpoints with Real AI Processing (Instructor + Pydantic)
Optimized for 2025 Architecture: DeepSeek V3, Structured Outputs, and Robustness.
Implements ReAct Loop (Reason + Act) for Agentic Behavior.
"""

import os
import json
import logging
import asyncio
import time
import datetime
from typing import Dict, Any, List, Optional, Union, Literal
from dataclasses import dataclass, field
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import openai
import anthropic
import instructor
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["ai_workflows"])

# --- Pydantic Models for Tools & ReAct State (Robustness) ---

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

# --- Existing Models (kept for backward compat) ---

class WorkflowStep(BaseModel):
    step_id: str
    title: str
    description: str
    complexity: int
    service: str
    action: str
    parameters: Dict[str, Any]

class WorkflowGraph(BaseModel):
    nodes: List[WorkflowStep]
    category: str
    is_template: bool = False

class TaskBreakdown(BaseModel):
    intent: str
    entities: List[str]
    tasks: List[str]
    workflow_suggestion: Optional[WorkflowGraph] = None
    confidence: float

class WorkflowExecutionResponse(BaseModel):
    workflow_id: str
    status: str
    ai_provider_used: str
    natural_language_input: str
    tasks_created: int
    execution_time_ms: float
    ai_generated_tasks: List[str]
    confidence_score: float
    steps_executed: Optional[List[ReActStepResult]] = None
    orchestration_type: str = "react_loop"

class NLUProcessingResponse(BaseModel):
    request_id: str
    input_text: str
    intent_confidence: float
    entities: Union[Dict[str, Any], List[str]]
    tasks_generated: List[str]
    processing_time_ms: float
    ai_provider_used: str
    workflow_suggestion: Optional[Dict[str, Any]] = None

# --- ReAct Agent Implementation ---

class ReActAgent:
    """
    Implements the Reason -> Act -> Observe loop.
    Uses DeepSeek V3 (via Instructor) for cost-effective reasoning.
    """
    def __init__(self, client, model_name: str):
        self.client = client
        self.model_name = model_name
        self.max_loops = 10
        self.history: List[Dict[str, str]] = []

    def _get_available_tools(self) -> str:
        """Define available tools for the LLM context"""
        # In a real system, this would dynamically list tools from MCP/UniversalService
        return """
Available Tools:
1. get_order(client_id: str) -> dict: Fetch order details (items, qty).
2. check_inventory(item_id: str) -> dict: Check current stock levels.
3. send_email(to: str, subject: str, body: str) -> str: Send an email.
4. search_knowledge_base(query: str) -> str: Search internal docs.
"""

    async def _execute_tool(self, tool_call: ToolCall) -> str:
        """
        Execute the tool.
        In production, this calls UniversalIntegrationService.
        For this simplified architecture validation, we implement the 'Coffee/SDR' example logic.
        """
        name = tool_call.tool_name
        params = tool_call.parameters

        logger.info(f"Executing Tool: {name} with {params}")

        # --- Mock Implementation for Validation ---
        if name == "get_order":
            client = params.get("client_id", "").lower()
            if "client a" in client:
                return json.dumps({"order_id": "123", "items": [{"item": "Arabica Beans", "qty": 50, "unit": "kg"}]})
            return json.dumps({"error": "Order not found"})

        elif name == "check_inventory":
            item = params.get("item_id", "").lower()
            if "arabica" in item:
                return json.dumps({"item": "Arabica Beans", "current_stock": 20, "unit": "kg"}) # Shortage scenario
            return json.dumps({"current_stock": 100, "unit": "kg"})

        elif name == "send_email":
            return f"Email sent to {params.get('to')}"

        elif name == "search_knowledge_base":
            return "Policy: We do not partial ship coffee beans."

        return f"Error: Tool '{name}' not found."

    async def run_loop(self, user_input: str) -> WorkflowExecutionResponse:
        """Execute the ReAct loop"""
        start_time = time.time()
        self.history = [
            {"role": "system", "content": f"You are an autonomous agent. Use the ReAct pattern (Reason, Act, Observe). {self._get_available_tools()}"},
            {"role": "user", "content": user_input}
        ]

        steps_record = []
        final_answer = None

        for i in range(self.max_loops):
            # 1. REASON (Call LLM)
            try:
                step_decision = await self.client.chat.completions.create(
                    model=self.model_name,
                    response_model=AgentStep, # Instructor validates this structure
                    messages=self.history,
                    max_retries=2
                )
            except Exception as e:
                logger.error(f"LLM Reasoning Failed: {e}")
                final_answer = f"Error during reasoning: {str(e)}"
                break

            action = step_decision.action

            # 2. ACT / FINALIZE
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
                # Record the thought
                steps_record.append(ReActStepResult(
                    step_number=i+1,
                    thought=action.reasoning,
                    tool_call=f"{action.tool_name}({action.parameters})",
                    tool_output=None, # Pending
                    timestamp=time.time()
                ))

                # Update history with assistant's thought/call
                self.history.append({
                    "role": "assistant",
                    "content": f"Thought: {action.reasoning}\nCall: {action.tool_name}({json.dumps(action.parameters)})"
                })

                # 3. OBSERVE (Execute Tool)
                tool_result = await self._execute_tool(action)

                # Record result
                steps_record[-1].tool_output = tool_result

                # Feed back to LLM
                self.history.append({
                    "role": "user",
                    "content": f"Tool Output: {tool_result}"
                })

        if not final_answer:
            final_answer = "Max loops reached without final answer."

        total_time = (time.time() - start_time) * 1000

        return WorkflowExecutionResponse(
            workflow_id=f"react_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            status="completed",
            ai_provider_used=self.model_name,
            natural_language_input=user_input,
            tasks_created=len(steps_record),
            execution_time_ms=total_time,
            ai_generated_tasks=[s.tool_call for s in steps_record],
            confidence_score=1.0, # Assumed high if completed
            steps_executed=steps_record,
            orchestration_type="react_loop_deepseek"
        )


# --- Real Service Implementation ---

class RealAIWorkflowService:
    """Real AI workflow service using Instructor for structured outputs"""

    def __init__(self):
        # Force reload .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        load_dotenv(env_path, override=True)

        from core.byok_endpoints import get_byok_manager
        self._byok = get_byok_manager()
        self.clients = {}
        logger.info("RealAIWorkflowService (Instructor-enabled) Initialized.")

    def get_client(self, provider_id: str):
        """Get or create an instructor-patched client"""
        if provider_id in self.clients:
            return self.clients[provider_id]

        api_key = self._byok.get_api_key(provider_id)
        if not api_key:
            return None

        provider_config = self._byok.providers.get(provider_id)
        base_url = provider_config.base_url
        
        client = None
        
        if provider_id == "anthropic":
            # Native Anthropic Support via Instructor
            try:
                base_client = anthropic.AsyncAnthropic(api_key=api_key)
                patched_client = instructor.from_anthropic(base_client)
                self.clients[provider_id] = patched_client
                return patched_client
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")
                return None

        # OpenAI Compatible Providers
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
        elif provider_id == "google":
             client = openai.AsyncOpenAI(api_key=api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
             mode = instructor.Mode.JSON
        else:
             client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

        if client:
            patched_client = instructor.from_openai(client, mode=mode)
            self.clients[provider_id] = patched_client
            return patched_client
        return None

    async def run_react_agent(self, text: str, provider: str = None) -> WorkflowExecutionResponse:
        """Run the ReAct agent loop"""
        if not provider:
            # ReAct requires high reasoning -> DeepSeek V3
            provider = self._byok.get_optimal_provider(task_type="reasoning", min_reasoning_level=4) or "openai"

        client = self.get_client(provider)
        if not client:
             # Fallback check
             keys = await self.get_active_provider_keys()
             if keys:
                 provider = keys[0]
                 client = self.get_client(provider)

        if not client:
            raise HTTPException(status_code=500, detail="No active AI provider found.")

        model_name = self._byok.providers[provider].model or "gpt-4o"

        agent = ReActAgent(client, model_name)
        return await agent.run_loop(text)

    async def get_active_provider_keys(self) -> List[str]:
        active = []
        for pid in self._byok.providers.keys():
            if self._byok.get_api_key(pid):
                active.append(pid)
        return active

    # Keep legacy/single-turn method for backward compat or simple NLU
    async def process_with_nlu_structured(self, text: str, provider: str = None) -> TaskBreakdown:
        if not provider:
            provider = "openai" # Default for simple tasks
        client = self.get_client(provider)
        if not client: return TaskBreakdown(intent="Error", entities=[], tasks=[], confidence=0.0)

        model_name = self._byok.providers[provider].model or "gpt-4o"
        try:
            return await client.chat.completions.create(
                model=model_name,
                response_model=TaskBreakdown,
                messages=[{"role": "user", "content": text}],
                max_retries=1
            )
        except Exception as e:
            return TaskBreakdown(intent="Error", entities=[], tasks=[str(e)], confidence=0.0)


# Global Service
ai_service = RealAIWorkflowService()

@router.post("/execute", response_model=WorkflowExecutionResponse)
async def execute_ai_workflow(request: Dict[str, Any]):
    """Execute AI workflow using ReAct Agent"""
    input_text = request.get("input", "")
    requested_provider = request.get("provider")

    try:
        # Use ReAct Agent for Execution
        return await ai_service.run_react_agent(input_text, requested_provider)
    except Exception as e:
        logger.error(f"Execution Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/nlu", response_model=NLUProcessingResponse)
async def process_natural_language(request: Dict[str, Any]):
    """Process natural language input (Single Turn NLU)"""
    start_time = time.time()
    input_text = request.get("text", "")
    requested_provider = request.get("provider")

    try:
        breakdown = await ai_service.process_with_nlu_structured(input_text, requested_provider)

        processing_time = (time.time() - start_time) * 1000
        workflow_data = None
        if breakdown.workflow_suggestion:
            workflow_data = breakdown.workflow_suggestion if isinstance(breakdown.workflow_suggestion, dict) else breakdown.workflow_suggestion.model_dump()

        return NLUProcessingResponse(
            request_id=f"nlu_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            input_text=input_text,
            intent_confidence=breakdown.confidence,
            entities=breakdown.entities,
            tasks_generated=breakdown.tasks,
            processing_time_ms=processing_time,
            ai_provider_used=requested_provider or "auto",
            workflow_suggestion=workflow_data
        )
    except Exception as e:
        logger.error(f"NLU Endpoint Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=Dict[str, Any])
async def get_ai_status():
    """Get system status"""
    from core.byok_endpoints import get_byok_manager
    bm = get_byok_manager()
    providers = [p.name for pid, p in bm.providers.items() if bm.get_api_key(pid)]
    return {
        "status": "operational",
        "active_providers": providers,
        "mode": "react_agent_loop",
        "primary_reasoning_engine": "DeepSeek V3"
    }

@router.get("/providers", response_model=Dict[str, Any])
async def get_providers():
    from core.byok_endpoints import get_byok_manager
    bm = get_byok_manager()
    providers = []
    for pid, p in bm.providers.items():
        status = "active" if bm.get_api_key(pid) else "configured"
        providers.append({
            "provider_name": pid,
            "enabled": status == "active",
            "model": p.model,
            "capabilities": p.supported_tasks,
            "status": status
        })
    return {"providers": providers, "total": len(providers), "active": len([p for p in providers if p["enabled"]])}

@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_content(request: Dict[str, Any]):
    text = request.get("text", "")
    provider = request.get("provider")
    try:
        breakdown = await ai_service.process_with_nlu_structured(text, provider)
        return {"status": "success", "analysis": breakdown.model_dump(), "provider": provider or "auto"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
