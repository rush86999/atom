"""
Enhanced Chat Interface with Phase 3 AI Intelligence
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from ai_conversation_intelligence import conversation_intelligence
    AI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"AI intelligence not available: {e}")
    AI_AVAILABLE = False

class ChatMessage(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None
    enable_ai_analysis: bool = True
    conversation_history: Optional[List[Dict[str, str]]] = None

class AIAnalysisResponse(BaseModel):
    analysis_id: str
    timestamp: str
    sentiment_scores: Dict[str, float]
    entities: List[Dict[str, str]]
    context_relevance: float
    suggested_actions: List[str]

app = FastAPI(title="Atom Chat Interface Phase 3", version="3.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conversation tracking
active_conversations = {}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "ai_conversation_intelligence": AI_AVAILABLE,
            "phase3_enhanced_chat": True
        }
    }

@app.post("/api/v1/ai/analyze")
async def analyze_conversation(message: str, user_id: str):
    if not AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI intelligence not available")

    try:
        analysis = conversation_intelligence.generate_context_aware_response(message, [])

        response = AIAnalysisResponse(
            analysis_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            sentiment_scores=analysis.get("sentiment", {}),
            entities=analysis.get("entities", []),
            context_relevance=analysis.get("context_relevance", 0.0),
            suggested_actions=analysis.get("suggested_actions", [])
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

@app.post("/api/v1/chat/enhanced/message")
async def enhanced_chat_message(request: ChatMessage):
    try:
        conversation_id = request.session_id or str(uuid.uuid4())

        if conversation_id not in active_conversations:
            active_conversations[conversation_id] = {
                "user_id": request.user_id,
                "start_time": datetime.now().isoformat(),
                "messages": []
            }

        # Add user message
        active_conversations[conversation_id]["messages"].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        })

        response_data = {
            "response": f"Enhanced response to: {request.message}",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "ai_analysis_applied": False
        }

        # Apply AI intelligence if enabled
        if request.enable_ai_analysis and AI_AVAILABLE:
            try:
                analysis = conversation_intelligence.generate_context_aware_response(
                    request.message,
                    request.conversation_history or []
                )
                response_data["ai_analysis"] = analysis
                response_data["ai_analysis_applied"] = True

                if analysis.get("suggested_actions"):
                    response_data["enhanced_suggestions"] = analysis["suggested_actions"]
            except Exception as e:
                logging.warning(f"AI analysis failed: {e}")

        # Add assistant response
        active_conversations[conversation_id]["messages"].append({
            "role": "assistant",
            "content": response_data["response"],
            "timestamp": datetime.now().isoformat()
        })

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5061)
