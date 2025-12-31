#!/usr/bin/env python3
"""
Enhanced AI Workflow Endpoints with Real AI Processing (Instructor + Pydantic)
Optimized for 2025 Architecture: DeepSeek V3, Structured Outputs, and Robustness.
"""

import os
import json
import logging
import asyncio
import time
import datetime
from typing import Dict, Any, List, Optional, Union, Literal
from dataclasses import dataclass
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import openai
import instructor
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["ai_workflows"])

# --- Pydantic Models for Structured Output (Robustness) ---

class WorkflowStep(BaseModel):
    step_id: str = Field(..., description="Unique identifier for the step (e.g., 'step_1')")
    title: str = Field(..., description="Short title of the step")
    description: str = Field(..., description="Detailed description of what this step does")
    complexity: int = Field(..., description="Complexity level (1-5)")
    service: str = Field(..., description="The service/tool involved (e.g., 'gmail', 'slack', 'excel')")
    action: str = Field(..., description="The specific action (e.g., 'send_email', 'create_row')")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the action")

class WorkflowGraph(BaseModel):
    nodes: List[WorkflowStep] = Field(..., description="List of steps in the workflow")
    category: str = Field(..., description="Category of the workflow (e.g., 'HR', 'Finance')")
    is_template: bool = Field(False, description="Whether this should be saved as a reusable template")

class TaskBreakdown(BaseModel):
    intent: str = Field(..., description="Summary of the user's intent")
    entities: List[str] = Field(default_factory=list, description="Key entities extracted")
    tasks: List[str] = Field(..., description="List of high-level tasks generated")
    workflow_suggestion: Optional[WorkflowGraph] = Field(None, description="Structured workflow definition if applicable")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")

class AIProviderStatus(BaseModel):
    provider_name: str
    enabled: bool
    model: str
    capabilities: List[str]
    status: str

class WorkflowExecutionResponse(BaseModel):
    workflow_id: str
    status: str
    ai_provider_used: str
    natural_language_input: str
    tasks_created: int
    execution_time_ms: float
    ai_generated_tasks: List[str]
    confidence_score: float
    steps_executed: Optional[List[Dict[str, Any]]] = None
    orchestration_type: str = "simple"

class NLUProcessingResponse(BaseModel):
    request_id: str
    input_text: str
    intent_confidence: float
    entities: Union[Dict[str, Any], List[str]]
    tasks_generated: List[str]
    processing_time_ms: float
    ai_provider_used: str
    workflow_suggestion: Optional[Dict[str, Any]] = None

# --- Service Implementation ---

class RealAIWorkflowService:
    """Real AI workflow service using Instructor for structured outputs"""

    def __init__(self):
        # Force reload .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        load_dotenv(env_path, override=True)
        
        from core.byok_endpoints import get_byok_manager
        self._byok = get_byok_manager()
        
        # Initialize Instructor clients lazily
        self.clients = {}
        
        logger.info("RealAIWorkflowService (Instructor-enabled) Initialized.")

    def get_client(self, provider_id: str):
        """Get or create an instructor-patched client for the provider"""
        if provider_id in self.clients:
            return self.clients[provider_id]
            
        api_key = self._byok.get_api_key(provider_id)
        if not api_key:
            return None

        provider_config = self._byok.providers.get(provider_id)
        # Default base URLs if not set
        base_url = provider_config.base_url
        
        # Configure client based on provider
        client = None
        mode = instructor.Mode.JSON
        
        if provider_id == "openai":
            client = openai.AsyncOpenAI(api_key=api_key)
            mode = instructor.Mode.TOOLS # OpenAI supports tools best
        elif provider_id == "deepseek":
            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=base_url or "https://api.deepseek.com/v1"
            )
            mode = instructor.Mode.JSON # DeepSeek V3 supports JSON mode
        elif provider_id == "groq":
             client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=base_url or "https://api.groq.com/openai/v1"
            )
             mode = instructor.Mode.JSON
        elif provider_id == "google":
             # Google OpenAI Compat
             client = openai.AsyncOpenAI(
                 api_key=api_key,
                 base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
             )
             mode = instructor.Mode.JSON
        else:
             # Fallback/Generic OpenAI compatible
             client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

        # Patch with Instructor using v1.0.0+ syntax
        if client:
            # use_server_response_model=False is safer for some proxies
            patched_client = instructor.from_openai(client, mode=mode)
            self.clients[provider_id] = patched_client
            return patched_client

        return None

    async def process_with_nlu_structured(self, text: str, provider: str = None) -> TaskBreakdown:
        """
        Process text using Instructor to get guaranteed structured output.
        Automatically selects optimal provider if none specified.
        """
        # Intelligent Provider Selection (2025 Architecture)
        # Default to DeepSeek V3 for complex reasoning if not specified
        if not provider:
            # High reasoning level required for breakdown
            provider = self._byok.get_optimal_provider(task_type="analysis", min_reasoning_level=3) or "openai"
        
        client = self.get_client(provider)
        if not client:
             # Fallback to OpenAI if preferred failed or keys missing
             if provider != "openai":
                 logger.warning(f"Preferred provider {provider} not available. Falling back to OpenAI.")
                 provider = "openai"
                 client = self.get_client("openai")

        if not client:
            # Final Check: Any active provider?
            keys = await self.get_active_provider_keys()
            if keys:
                provider = keys[0]
                client = self.get_client(provider)

        if not client:
            raise Exception(f"No active AI provider found (attempted {provider} and fallback)")

        model_name = self._byok.providers[provider].model or "gpt-4o"

        logger.info(f"Processing NLU with {provider} (Model: {model_name})")

        try:
            # Execute with retries built-in to Instructor (if validation fails)
            resp = await client.chat.completions.create(
                model=model_name,
                response_model=TaskBreakdown,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert autonomous agent architect. Analyze the user request and break it down into structured intents, entities, and a workflow graph."
                    },
                    {"role": "user", "content": text}
                ],
                max_retries=2,
            )
            return resp
            
        except Exception as e:
            logger.error(f"Instructor NLU failed with {provider}: {e}")
            # Simple fallback if everything fails
            return TaskBreakdown(
                intent="Error processing request",
                entities=[],
                tasks=["Error: " + str(e)],
                confidence=0.0
            )

    async def get_active_provider_keys(self) -> List[str]:
        """Get list of providers with active keys"""
        active = []
        for pid in self._byok.providers.keys():
            if self._byok.get_api_key(pid):
                active.append(pid)
        return active

# Global Service
ai_service = RealAIWorkflowService()

@router.post("/nlu", response_model=NLUProcessingResponse)
async def process_natural_language(request: Dict[str, Any]):
    """Process natural language input using robust Instructor-based pipeline"""
    start_time = time.time()
    input_text = request.get("text", "")
    requested_provider = request.get("provider") # Optional

    # 1. Use Instructor to get structured data
    try:
        breakdown = await ai_service.process_with_nlu_structured(input_text, requested_provider)

        # 2. Convert Pydantic model to response format
        processing_time = (time.time() - start_time) * 1000

        workflow_data = None
        if breakdown.workflow_suggestion:
            # Convert WorkflowGraph Pydantic model to dict
            workflow_data = breakdown.workflow_suggestion.model_dump()

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


@router.post("/execute", response_model=WorkflowExecutionResponse)
async def execute_ai_workflow(request: Dict[str, Any]):
    """Execute AI workflow"""
    start_time = time.time()
    input_text = request.get("input", "")
    requested_provider = request.get("provider")

    try:
        # Reuse the structured NLU to get tasks
        breakdown = await ai_service.process_with_nlu_structured(input_text, requested_provider)

        execution_time = (time.time() - start_time) * 1000

        return WorkflowExecutionResponse(
            workflow_id=f"wf_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            status="completed",
            ai_provider_used=requested_provider or "auto",
            natural_language_input=input_text,
            tasks_created=len(breakdown.tasks),
            execution_time_ms=execution_time,
            ai_generated_tasks=breakdown.tasks,
            confidence_score=breakdown.confidence,
            orchestration_type="instructor_robust"
        )
    except Exception as e:
        logger.error(f"Execution Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=Dict[str, Any])
async def get_ai_status():
    """Get system status"""
    from core.byok_endpoints import get_byok_manager
    bm = get_byok_manager()

    providers = []
    for pid, p in bm.providers.items():
        if bm.get_api_key(pid):
            providers.append(p.name)
            
    return {
        "status": "operational",
        "active_providers": providers,
        "mode": "instructor_robust_structured_outputs",
        "primary_reasoning_engine": "DeepSeek V3 (Preferred)" if "DeepSeek V3" in str(providers) else "OpenAI/Other"
    }

# --- RESTORED ENDPOINTS ---

@router.get("/providers", response_model=Dict[str, Any])
async def get_providers():
    """Get available AI providers (Restored)"""
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
        
    return {
        "providers": providers,
        "total": len(providers),
        "active": len([p for p in providers if p["enabled"]])
    }

@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_content(request: Dict[str, Any]):
    """Analyze content endpoint (Restored)"""
    text = request.get("text", "")
    provider = request.get("provider")
    
    try:
        breakdown = await ai_service.process_with_nlu_structured(text, provider)
        return {
            "status": "success",
            "analysis": breakdown.model_dump(),
            "provider": provider or "auto"
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
