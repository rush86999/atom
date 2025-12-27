"""
AI Workflows Routes - Alias routes for /api/ai-workflows/* paths
Provides compatibility with various API path conventions
"""
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai-workflows", tags=["AI Workflows"])

# Pydantic Models
class NLUParseRequest(BaseModel):
    text: str = Field(..., description="Text to parse")
    provider: str = Field("deepseek", description="AI provider to use")
    intent_only: bool = Field(False, description="Only extract intent")

class NLUParseResponse(BaseModel):
    request_id: str
    text: str
    intent: str
    entities: List[Dict[str, Any]]
    tasks: List[str]
    confidence: float
    provider_used: str
    processing_time_ms: float

class CompletionRequest(BaseModel):
    prompt: str = Field(..., description="Prompt for completion")
    provider: str = Field("deepseek", description="AI provider to use")
    max_tokens: int = Field(500, description="Maximum tokens in response")
    temperature: float = Field(0.7, description="Temperature for sampling")

class CompletionResponse(BaseModel):
    completion: str
    provider_used: str
    tokens_used: int
    processing_time_ms: float

@router.post("/nlu/parse", response_model=NLUParseResponse)
async def parse_nlu(request: NLUParseRequest):
    """
    Parse natural language to extract intent, entities, and tasks.
    This is the main NLU endpoint for the agent runtime.
    """
    import time
    start_time = time.time()
    
    try:
        # Try to use the real AI service
        from enhanced_ai_workflow_endpoints import ai_service
        
        nlu_result = await ai_service.process_with_nlu(
            request.text, 
            request.provider
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return NLUParseResponse(
            request_id=f"nlu_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            text=request.text,
            intent=nlu_result.get('intent', 'unknown'),
            entities=nlu_result.get('entities', []) if isinstance(nlu_result.get('entities'), list) else [],
            tasks=nlu_result.get('tasks', []),
            confidence=nlu_result.get('confidence', 0.85),
            provider_used=nlu_result.get('ai_provider_used', request.provider),
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.warning(f"Real NLU failed, using fallback: {e}")
        
        # Fallback NLU with simple pattern matching
        processing_time = (time.time() - start_time) * 1000
        text_lower = request.text.lower()
        
        # Simple intent classification
        intent = "general"
        if "schedule" in text_lower or "meeting" in text_lower:
            intent = "scheduling"
        elif "send" in text_lower or "email" in text_lower:
            intent = "communication"
        elif "create" in text_lower or "add" in text_lower:
            intent = "creation"
        elif "search" in text_lower or "find" in text_lower:
            intent = "search"
        elif "workflow" in text_lower or "automate" in text_lower:
            intent = "workflow_creation"
        
        # Simple entity extraction
        entities = []
        words = request.text.split()
        for i, word in enumerate(words):
            if "@" in word:
                entities.append({"type": "email", "value": word})
            if word.isdigit():
                entities.append({"type": "number", "value": word})
        
        return NLUParseResponse(
            request_id=f"nlu_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            text=request.text,
            intent=intent,
            entities=entities,
            tasks=[f"Process: {request.text[:100]}"],
            confidence=0.7,
            provider_used="fallback",
            processing_time_ms=processing_time
        )

@router.get("/providers")
async def get_providers():
    """Get available AI providers"""
    try:
        from enhanced_ai_workflow_endpoints import ai_service
        
        providers = []
        if ai_service.openai_api_key:
            providers.append({"id": "openai", "name": "OpenAI GPT-4", "enabled": True})
        if ai_service.anthropic_api_key:
            providers.append({"id": "anthropic", "name": "Anthropic Claude", "enabled": True})
        if ai_service.deepseek_api_key:
            providers.append({"id": "deepseek", "name": "DeepSeek Chat", "enabled": True})
        if ai_service.google_api_key:
            providers.append({"id": "google", "name": "Google Gemini", "enabled": True})
        
        return {
            "providers": providers,
            "default": "deepseek" if ai_service.deepseek_api_key else "openai",
            "count": len(providers)
        }
    except:
        return {
            "providers": [
                {"id": "openai", "name": "OpenAI GPT-4", "enabled": False},
                {"id": "anthropic", "name": "Anthropic Claude", "enabled": False},
                {"id": "deepseek", "name": "DeepSeek Chat", "enabled": False},
            ],
            "default": "openai",
            "count": 0
        }

@router.post("/complete", response_model=CompletionResponse)
async def complete_text(request: CompletionRequest):
    """
    Generate text completion using configured AI provider.
    """
    import time
    start_time = time.time()
    
    try:
        from enhanced_ai_workflow_endpoints import ai_service
        
        result = await ai_service.analyze_text(
            request.prompt,
            complexity=2,
            system_prompt="You are a helpful AI assistant."
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return CompletionResponse(
            completion=result,
            provider_used=request.provider,
            tokens_used=len(result.split()) * 2,  # Rough estimate
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"Completion failed: {e}")
        processing_time = (time.time() - start_time) * 1000
        
        return CompletionResponse(
            completion=f"[Completion unavailable: {str(e)[:100]}]",
            provider_used="error",
            tokens_used=0,
            processing_time_ms=processing_time
        )
