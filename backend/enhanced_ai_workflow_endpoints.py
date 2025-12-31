#!/usr/bin/env python3
"""
Enhanced AI Workflow Endpoints with Real AI Processing (Instructor + Pydantic)
Optimized for 2025 Architecture: DeepSeek V3, Structured Outputs, and Robustness.
Implements ReAct Loop (Reason + Act) via Core Engine.
"""

import os
import json
import logging
import asyncio
import time
import datetime
from typing import Dict, Any, List, Optional, Union, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import Core Engine
from core.react_agent_engine import ReActAgentEngine, ToolCall, FinalAnswer, AgentStep, ReActStepResult, AgentExecutionResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["ai_workflows"])

# --- Models (Compat) ---
class TaskBreakdown(BaseModel):
    intent: str
    entities: List[str]
    tasks: List[str]
    workflow_suggestion: Optional[Dict[str, Any]] = None
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

# --- Service Implementation Wrapper ---

class RealAIWorkflowService:
    """Wrapper around ReActAgentEngine for Endpoints"""

    def __init__(self):
        self.engine = ReActAgentEngine()

    async def run_react_agent(self, text: str, provider: str = None) -> WorkflowExecutionResponse:
        """Run the ReAct agent loop via Engine"""

        # Define Tools (Mock for this endpoint context)
        tools_def = """
Available Tools:
1. get_order(client_id: str) -> dict: Fetch order details (items, qty).
2. check_inventory(item_id: str) -> dict: Check current stock levels.
3. send_email(to: str, subject: str, body: str) -> str: Send an email.
4. search_knowledge_base(query: str) -> str: Search internal docs.
"""

        async def execute_tool(name: str, params: Dict) -> str:
            logger.info(f"Executing Tool: {name} with {params}")
            if name == "get_order":
                client = params.get("client_id", "").lower()
                if "client a" in client:
                    return json.dumps({"order_id": "123", "items": [{"item": "Arabica Beans", "qty": 50, "unit": "kg"}]})
                return json.dumps({"error": "Order not found"})
            elif name == "check_inventory":
                item = params.get("item_id", "").lower()
                if "arabica" in item:
                    return json.dumps({"item": "Arabica Beans", "current_stock": 20, "unit": "kg"})
                return json.dumps({"current_stock": 100, "unit": "kg"})
            elif name == "send_email":
                return f"Email sent to {params.get('to')}"
            elif name == "search_knowledge_base":
                return "Policy: We do not partial ship coffee beans."
            return f"Error: Tool '{name}' not found."

        # Run Loop
        result = await self.engine.run_loop(
            user_input=text,
            tools_definition=tools_def,
            tool_executor=execute_tool,
            system_prompt="You are an autonomous agent."
        )

        return WorkflowExecutionResponse(
            workflow_id=result.task_id,
            status=result.status,
            ai_provider_used=result.provider,
            natural_language_input=result.input,
            tasks_created=len(result.steps),
            execution_time_ms=result.execution_time_ms,
            ai_generated_tasks=[s.tool_call for s in result.steps if s.tool_call],
            confidence_score=1.0 if result.status == "success" else 0.0,
            steps_executed=result.steps,
            orchestration_type="react_loop_deepseek"
        )

    # Legacy NLU support via simple one-shot
    async def process_with_nlu_structured(self, text: str, provider: str = None) -> TaskBreakdown:
        provider = provider or "openai"
        client = self.engine._get_client(provider)
        if not client: return TaskBreakdown(intent="Error", entities=[], tasks=[], confidence=0.0)

        try:
            return await client.chat.completions.create(
                model="gpt-4o", # Fallback default
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
    input_text = request.get("input", "")
    requested_provider = request.get("provider")
    try:
        return await ai_service.run_react_agent(input_text, requested_provider)
    except Exception as e:
        logger.error(f"Execution Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/nlu", response_model=NLUProcessingResponse)
async def process_natural_language(request: Dict[str, Any]):
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
    from core.byok_endpoints import get_byok_manager
    bm = get_byok_manager()
    providers = [p.name for pid, p in bm.providers.items() if bm.get_api_key(pid)]
    return {
        "status": "operational",
        "active_providers": providers,
        "mode": "react_agent_loop_engine",
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
