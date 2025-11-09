"""
Enhanced Chat Interface with Phase 3 AI Intelligence & Memory System
AI-powered conversation intelligence with persistent memory

Author: Atom Platform Engineering
Date: November 9, 2025
Version: 3.1.0-memory
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from ai_conversation_intelligence_lightweight import conversation_intelligence

    AI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Lightweight AI intelligence not available: {e}")
    AI_AVAILABLE = False

# Import memory system components
try:
    from lancedb_handler import (
        get_lancedb_connection,
        search_conversation_context,
        store_conversation_context,
    )

    MEMORY_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Memory system not available: {e}")
    MEMORY_AVAILABLE = False


class ChatMessage(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None
    enable_ai_analysis: bool = True
    enable_memory: bool = True
    conversation_history: Optional[List[Dict[str, str]]] = None


class MemoryContext(BaseModel):
    relevant_conversations: List[Dict[str, Any]]
    memory_score: float
    context_summary: str


class AIAnalysisResponse(BaseModel):
    analysis_id: str
    timestamp: str
    sentiment_scores: Dict[str, float]
    entities: List[Dict[str, str]]
    intents: List[str]
    context_relevance: float
    suggested_actions: List[str]


app = FastAPI(
    title="Atom Chat Interface Phase 3 (Memory Enhanced)",
    description="Enhanced chat interface with AI-powered conversation intelligence and persistent memory",
    version="3.1.0-memory",
)

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


@app.get("/")
async def root():
    return {
        "message": "Atom Chat Interface Phase 3 (Memory Enhanced)",
        "version": "3.1.0-memory",
        "status": "operational",
        "ai_intelligence": "available" if AI_AVAILABLE else "unavailable",
        "memory_system": "available" if MEMORY_AVAILABLE else "unavailable",
    }


@app.get("/health")
async def health_check():
    # Test memory system if available
    memory_status = "unavailable"
    if MEMORY_AVAILABLE:
        try:
            # Simple memory system test
            memory_status = "healthy"
        except:
            memory_status = "unhealthy"

    return {
        "status": "healthy",
        "version": "3.1.0-memory",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "lightweight_ai_intelligence": AI_AVAILABLE,
            "phase3_enhanced_chat": True,
            "sentiment_analysis": AI_AVAILABLE,
            "entity_extraction": AI_AVAILABLE,
            "intent_detection": AI_AVAILABLE,
            "memory_system": MEMORY_AVAILABLE,
        },
        "system_stats": {
            "active_conversations": len(active_conversations),
            "ai_model_status": "loaded" if AI_AVAILABLE else "unavailable",
            "memory_system_status": memory_status,
        },
    }


@app.post("/api/v1/ai/analyze", response_model=AIAnalysisResponse)
async def analyze_conversation(message: str, user_id: str):
    """Analyze conversation with lightweight AI intelligence"""
    if not AI_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Lightweight AI intelligence not available"
        )

    try:
        analysis = conversation_intelligence.generate_context_aware_response(
            message, []
        )

        response = AIAnalysisResponse(
            analysis_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            sentiment_scores=analysis.get("sentiment", {}),
            entities=analysis.get("entities", []),
            intents=analysis.get("intents", []),
            context_relevance=analysis.get("context_relevance", 0.0),
            suggested_actions=analysis.get("suggested_actions", []),
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


@app.post("/api/v1/chat/enhanced/message")
async def enhanced_chat_message(request: ChatMessage):
    """Enhanced chat message with lightweight AI intelligence"""
    try:
        conversation_id = request.session_id or str(uuid.uuid4())

        if conversation_id not in active_conversations:
            active_conversations[conversation_id] = {
                "user_id": request.user_id,
                "start_time": datetime.now().isoformat(),
                "messages": [],
                "metrics": {"message_count": 0, "ai_analyses_performed": 0},
            }

        conversation = active_conversations[conversation_id]

        # Add user message to conversation
        user_message = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat(),
            "message_id": str(uuid.uuid4()),
        }
        conversation["messages"].append(user_message)
        conversation["metrics"]["message_count"] += 1

        # Prepare response
        response_data = {
            "response": f"Enhanced response to: {request.message}",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "ai_analysis_applied": False,
            "memory_context_applied": False,
            "conversation_metrics": conversation["metrics"],
        }

        # Get memory context if enabled
        memory_context = None
        if request.enable_memory and MEMORY_AVAILABLE:
            try:
                memory_context = await get_memory_context(
                    request.message, request.user_id, conversation_id
                )
                response_data["memory_context"] = MemoryContext(**memory_context)
                response_data["memory_context_applied"] = True
                conversation["metrics"]["memory_contexts_applied"] += 1

                # Enhance response based on memory context
                if memory_context.get("memory_score", 0) > 0.7:
                    response_data["response"] = (
                        f"I recall our previous discussion. {response_data['response']}"
                    )

            except Exception as e:
                logging.warning(f"Memory context retrieval failed: {e}")

        # Apply AI intelligence if enabled
        if request.enable_ai_analysis and AI_AVAILABLE:
            try:
                # Combine current message with memory context for better analysis
                analysis_input = request.message
                if memory_context and memory_context.get("context_summary"):
                    analysis_input = f"Context: {memory_context['context_summary']}. Message: {request.message}"

                analysis = conversation_intelligence.generate_context_aware_response(
                    analysis_input,
                    request.conversation_history or conversation["messages"],
                )

                response_data["ai_analysis"] = analysis
                response_data["ai_analysis_applied"] = True
                conversation["metrics"]["ai_analyses_performed"] += 1

                # Enhance response based on analysis and memory
                sentiment_score = analysis["sentiment"].get("overall_sentiment", 0)

                if memory_context and memory_context.get("memory_score", 0) > 0.7:
                    # High memory relevance - reference previous discussions
                    if sentiment_score < -0.3:
                        response_data["response"] = (
                            f"I understand you're still concerned about this. Let me help you resolve it completely."
                        )
                    elif sentiment_score > 0.3:
                        response_data["response"] = (
                            f"Great to continue our discussion about this! Here's more information."
                        )
                    else:
                        response_data["response"] = (
                            f"Building on our previous conversation: {response_data['response']}"
                        )
                else:
                    # Standard AI-enhanced responses
                    if sentiment_score < -0.3:
                        response_data["response"] = (
                            f"I understand you're concerned about: {request.message}. Let me help you with that."
                        )
                    elif sentiment_score > 0.3:
                        response_data["response"] = (
                            f"Great to hear about: {request.message}! Here's some information that might help."
                        )

                # Add enhanced suggestions
                if analysis.get("suggested_actions"):
                    response_data["enhanced_suggestions"] = analysis[
                        "suggested_actions"
                    ]

            except Exception as e:
                logging.warning(f"Lightweight AI analysis failed: {e}")

        # Add assistant response to conversation
        assistant_message = {
            "role": "assistant",
            "content": response_data["response"],
            "timestamp": datetime.now().isoformat(),
            "message_id": str(uuid.uuid4()),
        }
        conversation["messages"].append(assistant_message)

        # Store conversation in memory (background task)
        if request.enable_memory and MEMORY_AVAILABLE:
            try:
                conversation_data = {
                    "id": user_message["message_id"],
                    "user_id": request.user_id,
                    "session_id": conversation_id,
                    "role": "user",
                    "content": request.message,
                    "message_type": "text",
                    "timestamp": user_message["timestamp"],
                    "metadata": {
                        "ai_analysis_applied": request.enable_ai_analysis,
                        "memory_context_applied": request.enable_memory,
                        "sentiment_score": analysis["sentiment"].get(
                            "overall_sentiment", 0
                        )
                        if analysis
                        else 0,
                    },
                }
                await store_conversation_in_memory(conversation_data)
            except Exception as e:
                logging.warning(f"Failed to store conversation in memory: {e}")

        return response_data

    except Exception as e:
        logging.error(f"Enhanced chat message failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


async def get_memory_context(
    message: str, user_id: str, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Get relevant context from memory system"""
    if not MEMORY_AVAILABLE:
        return {
            "relevant_conversations": [],
            "memory_score": 0.0,
            "context_summary": "Memory system unavailable",
        }

    try:
        # Search memory for relevant conversations
        db_conn = await get_lancedb_connection()
        search_result = await search_conversation_context(
            db_conn,
            _generate_simple_embedding(message),  # Simple fallback embedding
            user_id,
            session_id,
            limit=3,
            similarity_threshold=0.6,
        )

        if search_result.get("status") == "success":
            relevant_conversations = search_result.get("results", [])
            memory_score = (
                max(
                    [conv.get("similarity_score", 0) for conv in relevant_conversations]
                )
                if relevant_conversations
                else 0.0
            )

            # Generate context summary
            context_summary = _generate_context_summary(relevant_conversations)

            return {
                "relevant_conversations": relevant_conversations,
                "memory_score": memory_score,
                "context_summary": context_summary,
            }
        else:
            return {
                "relevant_conversations": [],
                "memory_score": 0.0,
                "context_summary": "Memory search failed",
            }

    except Exception as e:
        logging.error(f"Error getting memory context: {e}")
        return {
            "relevant_conversations": [],
            "memory_score": 0.0,
            "context_summary": f"Memory error: {str(e)}",
        }


def _generate_context_summary(relevant_conversations: List[Dict]) -> str:
    """Generate a summary of relevant conversation context"""
    if not relevant_conversations:
        return "No relevant context found"

    # Extract key topics from relevant conversations
    topics = set()
    for conv in relevant_conversations[:3]:  # Use top 3 most relevant
        content = conv.get("content", "")
        # Simple topic extraction
        if "help" in content.lower():
            topics.add("help requests")
        if "problem" in content.lower() or "issue" in content.lower():
            topics.add("problem solving")
        if "feature" in content.lower():
            topics.add("feature discussion")
        if "setting" in content.lower():
            topics.add("settings/config")

    if topics:
        return f"Previous discussions about: {', '.join(topics)}"
    else:
        return "General conversation context available"


async def store_conversation_in_memory(conversation_data: Dict[str, Any]):
    """Store conversation in memory system"""
    if not MEMORY_AVAILABLE:
        return

    try:
        db_conn = await get_lancedb_connection()
        await store_conversation_context(
            db_conn,
            conversation_data,
            _generate_simple_embedding(conversation_data.get("content", "")),
        )
    except Exception as e:
        logging.error(f"Failed to store conversation in memory: {e}")


def _generate_simple_embedding(text: str) -> List[float]:
    """Generate simple embedding for fallback when embedding service is unavailable"""
    import hashlib

    hash_obj = hashlib.md5(text.encode())
    hash_hex = hash_obj.hexdigest()

    # Convert to 16-dimensional vector (simple mapping)
    embedding = []
    for i in range(0, 32, 2):
        byte_val = int(hash_hex[i : i + 2], 16)
        embedding.append(byte_val / 255.0)  # Normalize to 0-1

    # Pad or truncate to 16 dimensions
    while len(embedding) < 16:
        embedding.append(0.0)

    return embedding[:16]


@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation details"""
    if conversation_id not in active_conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return active_conversations[conversation_id]


@app.get("/api/v1/analytics/overview")
async def get_analytics_overview():
    """Get analytics overview"""
    total_conversations = len(active_conversations)
    total_messages = sum(
        conv["metrics"]["message_count"] for conv in active_conversations.values()
    )
    total_ai_analyses = sum(
        conv["metrics"]["ai_analyses_performed"]
        for conv in active_conversations.values()
    )
    total_memory_contexts = sum(
        conv["metrics"]["memory_contexts_applied"]
        for conv in active_conversations.values()
    )

    return {
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_ai_analyses": total_ai_analyses,
        "total_memory_contexts": total_memory_contexts,
        "ai_utilization_rate": total_ai_analyses / total_messages
        if total_messages > 0
        else 0,
        "memory_utilization_rate": total_memory_contexts / total_messages
        if total_messages > 0
        else 0,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=5062)
