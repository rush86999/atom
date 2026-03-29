#!/usr/bin/env python3
"""
Enhanced AI Workflow Endpoints with Real AI Processing (Instructor + Pydantic)
Optimized for 2025 Architecture: DeepSeek V3, Structured Outputs, and Robustness.
Implements ReAct Loop (Reason + Act) for Agentic Behavior.
"""

import asyncio
from dataclasses import dataclass, field
import datetime
import json
import logging
import os
import time
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

from core.llm_service import LLMService

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

import base64

from core.voice_service import get_voice_service

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

# --- Chat Models ---

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None
    audio_output: bool = False
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    message: str
    session_id: str
    audio_data: Optional[str] = None # Base64 encoded audio
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str

class AIProvider(BaseModel):
    provider_name: str
    enabled: bool
    model: str
    capabilities: List[str]
    status: str

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
    final_answer: Optional[str] = None
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

# --- ReAct Agent Implementation ---

class ReActAgent:
    """
    Implements the Reason -> Act -> Observe loop.
    Uses unified LLMService for multi-provider reasoning and structured outputs.
    """
    def __init__(self, llm_service: LLMService, model_name: str = "quality"):
        self.llm_service = llm_service
        self.model_name = model_name  # Can be "quality", "fast", or a specific model ID
        self.max_loops = 10
        self.history: List[Dict[str, str]] = []

    def _get_available_tools(self) -> str:
        """Define available tools for the LLM context"""
        return """
Available Tools:
1. get_order(client_id: str) -> dict: Fetch order details (items, qty).
2. check_inventory(item_id: str) -> dict: Check current stock levels.
3. send_email(to: str, subject: str, body: str) -> str: Send an email.
4. search_knowledge_base(query: str) -> str: Search internal docs.
"""

    async def _execute_tool(self, tool_call: ToolCall) -> str:
        """Execute the tool (Mock implementation for validation)"""
        name = tool_call.tool_name
        params = tool_call.parameters

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

    async def run_loop(self, user_input: str) -> WorkflowExecutionResponse:
        """Execute the ReAct loop using unified LLMService.generate_structured"""
        start_time = time.time()
        system_instruction = f"You are an autonomous agent using the ReAct pattern (Reason, Act, Observe). {self._get_available_tools()}"
        
        self.history = [{"role": "user", "content": user_input}]
        steps_record = []
        final_answer = None

        for i in range(self.max_loops):
            # 1. REASON (Call unified LLMService)
            # We map context to a flat prompt for BYOKHandler for now, 
            # but generate_structured is the preferred high-level API.
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in self.history])
            
            try:
                step_decision = await self.llm_service.generate_structured(
                    prompt=prompt,
                    response_model=AgentStep,
                    system_instruction=system_instruction,
                    model=self.model_name
                )
            except Exception as e:
                logger.error(f"LLM Reasoning Failed: {e}")
                final_answer = f"Error during reasoning: {str(e)}"
                break

            if not step_decision:
                final_answer = "Failed to generate structured decision."
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
                steps_record.append(ReActStepResult(
                    step_number=i+1,
                    thought=action.reasoning,
                    tool_call=f"{action.tool_name}({action.parameters})",
                    tool_output=None,
                    timestamp=time.time()
                ))

                self.history.append({
                    "role": "assistant",
                    "content": f"Thought: {action.reasoning}\nCall: {action.tool_name}({json.dumps(action.parameters)})"
                })

                # 3. OBSERVE
                tool_result = await self._execute_tool(action)
                steps_record[-1].tool_output = tool_result

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
            confidence_score=1.0,
            steps_executed=steps_record,
            final_answer=final_answer,
            orchestration_type="react_loop_unified"
        )


# --- Real Service Implementation ---

class RealAIWorkflowService:
    """
    Real AI workflow service modernized to use unified LLMService.
    Eliminates redundant BYOK logic and manual API calls.
    """
    def __init__(self):
        # We use local import to break potential circularity if ServiceFactory imports this
        from core.service_factory import ServiceFactory
        self.llm_service = ServiceFactory.get_llm_service()
        logger.info("RealAIWorkflowService modernized with unified LLMService.")

    async def initialize_sessions(self):
        """No-op: Sessions managed by LLMService/BYOKHandler"""
        pass

    async def cleanup_sessions(self):
        """No-op: Sessions managed by LLMService/BYOKHandler"""
        pass

    def get_client(self, provider_id: str):
        """
        Legacy shim: Returns the underlying instructor-patched client from LLMService.
        """
        # Note: In the new architecture, we prefer calling llm_service directly.
        # This is kept for backward compatibility with external callers.
        handler = self.llm_service.handler
        client = handler.async_clients.get(provider_id) or handler.clients.get(provider_id)
        if client and instructor:
            # Re-patch if needed, though BYOKHandler usually patches already
            return client
        return None

    async def call_glm_api(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> Dict[str, Any]:
        """Modernized GLM call via unified LLMService"""
        content = await self.llm_service.generate(prompt, system_instruction=system_prompt, model="minimax") # Or "glm" if mapped
        return {'content': content, 'confidence': 0.85, 'provider': 'minimax/glm'}

    async def call_openai_api(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Modernized OpenAI call via unified LLMService"""
        res = await self.llm_service.generate_completion(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            model="gpt-4o"
        )
        return {'content': res['content'], 'confidence': 0.85, 'provider': 'openai'}

    async def call_deepseek_api(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Modernized DeepSeek call via unified LLMService"""
        res = await self.llm_service.generate_completion(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            model="deepseek-chat"
        )
        return {'content': res['content'], 'confidence': 0.83, 'provider': 'deepseek'}
            
    async def process_with_nlu(self, text: str, provider: str = "auto", system_prompt: str = None, user_id: str = "default_user") -> Dict[str, Any]:
        """Modernized NLU Processing using ReAct loop by default"""
        from core.trajectory import TrajectoryRecorder
        recorder = TrajectoryRecorder(user_id=user_id, request=text)
        recorder.add_thought(f"Starting Unified NLU: {text}")
        
        try:
             agent_resp = await self.run_react_agent(text, provider=provider)
             return {
                 "intent": "processed_by_react",
                 "workflow_suggestion": {"nodes": []},
                 "tasks_generated": agent_resp.ai_generated_tasks,
                 "confidence": agent_resp.confidence_score,
                 "answer": agent_resp.final_answer
             }
        except Exception as e:
             logger.error(f"NLU ReAct processing failed: {e}")
             # Fallback to simple generation
             content = await self.llm_service.generate(text, system_instruction=system_prompt or "Identify intent and tasks.")
             return {
                 "intent": "fallback_generation",
                 "answer": content,
                 "confidence": 0.5
             }

    async def run_react_agent(self, text: str, provider: str = "quality") -> WorkflowExecutionResponse:
        """Run the ReAct agent loop using unified infrastructure"""
        agent = ReActAgent(self.llm_service, model_name=provider or "quality")
        return await agent.run_loop(text)

    async def get_active_provider_keys(self) -> List[str]:
        """Get active providers from unified LLMService"""
        return self.llm_service.get_available_providers()

    # Keep legacy/single-turn method for backward compat or simple NLU
    async def process_with_nlu_structured(self, text: str, provider: str = "quality") -> TaskBreakdown:
        """Modernized structured NLU via unified LLMService"""
        try:
            return await self.llm_service.generate_structured(
                prompt=text,
                response_model=TaskBreakdown,
                system_instruction="Analyze the user intent and break it down into entities and tasks.",
                model=provider or "quality"
            )
        except Exception as e:
            logger.error(f"Structured NLU failed: {e}")
            return TaskBreakdown(intent="Error", entities=[], tasks=[str(e)], confidence=0.0)

    async def analyze_text(self, prompt: str, complexity: int = 1, system_prompt: str = "", user_id: str = "default_user") -> str:
        """
        Modernized text analysis using unified LLMService.
        Automatically handles provider selection based on complexity.
        """
        # Mapping complexity to pre-defined cognitive tiers in LLMService
        model = "fast"
        if complexity == 3:
            model = "quality"
        elif complexity >= 4:
            model = "reasoning"

        return await self.llm_service.generate(
            prompt, 
            system_instruction=system_prompt,
            model=model
        )


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

@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """
    Enhanced chat endpoint with optional audio output.
    """
    try:
        # Generate text response using AI service
        # Using a system prompt that encourages conversational helpfulness
        system_prompt = "You are ATOM, a helpful and intelligent AI assistant. Keep responses concise and natural."
        
        # If we have context, inject it
        if request.context:
             system_prompt += f"\nContext: {json.dumps(request.context)}"

        response_text = await ai_service.analyze_text(
            request.message, 
            complexity=1,
            system_prompt=system_prompt,
            user_id=request.user_id
        )

        audio_data = None
        if request.audio_output:
            # Generate audio using VoiceService
            # Try efficient provider first
            audio_data = await get_voice_service().text_to_speech(response_text)

        return ChatResponse(
            message=response_text,
            session_id=request.session_id or f"session_{int(time.time())}",
            audio_data=audio_data,
            timestamp=datetime.datetime.now().isoformat(),
            metadata={
                "provider": "atom_enhanced_ai",
                "has_audio": bool(audio_data)
            }
        )
    except Exception as e:
        logger.error(f"Chat failed: {e}")
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
