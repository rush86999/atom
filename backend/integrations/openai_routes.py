from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from integrations.openai_service import openai_service

router = APIRouter(prefix="/api/openai", tags=["OpenAI Integration"])

class CompletionRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.7
    system_prompt: Optional[str] = None

class EmbeddingRequest(BaseModel):
    text: str
    model: str = "text-embedding-3-small"

@router.post("/chat")
async def openai_chat_completion(request: CompletionRequest):
    """Generate a chat completion using OpenAI"""
    return await openai_service.generate_completion(
        prompt=request.prompt,
        model=request.model,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        system_prompt=request.system_prompt
    )

@router.post("/embeddings")
async def openai_embeddings(request: EmbeddingRequest):
    """Generate embeddings using OpenAI"""
    return await openai_service.generate_embeddings(
        text=request.text,
        model=request.model
    )

@router.get("/health")
async def openai_health():
    """Check health and authentication status of OpenAI integration"""
    return await openai_service.check_health()
