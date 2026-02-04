"""
Chat Routes - API endpoints for the ATOM chat interface
"""
import logging
import os

# Add parent directory to path to import from backend
import sys
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from integrations.chat_orchestrator import ChatOrchestrator, FeatureType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Initialize chat orchestrator
chat_orchestrator = ChatOrchestrator()


# Pydantic Models
class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="Chat message from user")
    user_id: str = Field(..., description="User ID for context")
    session_id: Optional[str] = Field(None, description="Conversation session ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context data")


class ChatMessageResponse(BaseModel):
    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Response message")
    session_id: str = Field(..., description="Conversation session ID")
    intent: str = Field(..., description="Detected intent")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    suggested_actions: list = Field(..., description="Suggested next actions")
    requires_confirmation: bool = Field(..., description="Whether confirmation is needed")
    next_steps: list = Field(..., description="Suggested next steps")
    timestamp: str = Field(..., description="Response timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata and structured actions")


class ChatHistoryRequest(BaseModel):
    session_id: str = Field(..., description="Conversation session ID")
    user_id: str = Field(..., description="User ID")


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list
    timestamp: str


class ChatMemoryRequest(BaseModel):
    session_id: str = Field(..., description="Conversation session ID")
    user_id: str = Field(..., description="User ID")


class ChatMemoryResponse(BaseModel):
    session_id: str
    memory_context: dict
    timestamp: str

class RenameSessionRequest(BaseModel):
    title: str = Field(..., description="New title for the session")
    user_id: str = Field(..., description="ID of the user performing the rename")


@router.patch("/sessions/{session_id}")
async def rename_session(session_id: str, request: RenameSessionRequest) -> Dict[str, Any]:
    """
    Rename a chat session
    """
    try:
        # Check permissions first
        session = chat_orchestrator.conversation_sessions.get(session_id)
        if not session:
            # Try lazy load check via manager
            managed_session = chat_orchestrator.session_manager.get_session(session_id)
            if managed_session:
                session = managed_session
        
        if not session:
             raise HTTPException(status_code=404, detail="Session not found")
             
        if session.get("user_id") != request.user_id:
             logger.warning(f"Rename denied: Owner {session.get('user_id')} != Requestor {request.user_id}")
             raise HTTPException(status_code=403, detail="Access denied")

        success = chat_orchestrator.rename_session(session_id, request.title)
        
        if not success:
             raise HTTPException(status_code=404, detail="Session not found or upgrade failed")
             
        return {
            "success": True, 
            "message": "Session renamed successfully",
            "session_id": session_id,
            "title": request.title
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rename session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to rename session: {str(e)}")

@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str, user_id: str) -> Dict[str, Any]:
    """
    Get details for a specific session
    """
    try:
        # We can use orchestrator's memory or fetch from session manager
        # Since orchestrator has get_user_sessions, let's use a direct get_session
        session = chat_orchestrator.conversation_sessions.get(session_id)
        
        if not session:
             # Let's peek into manager
             managed_session = chat_orchestrator.session_manager.get_session(session_id)
             if managed_session:
                 session = managed_session
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        if session.get("user_id") != user_id:
             raise HTTPException(status_code=403, detail="Access denied")

        return {
            "success": True,
            "session_id": session.get("id") or session.get("session_id"),
            "title": session.get("title"),
            "created_at": session.get("created_at"),
            "user_id": session.get("user_id")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get session details: {str(e)}")



# API Routes
@router.post("/message")
async def send_chat_message(request: ChatMessageRequest) -> ChatMessageResponse:
    """
    Send a chat message to the ATOM chat orchestrator
    """
    try:
        logger.info(f"Processing chat message from user {request.user_id}: {request.message}")

        # Handle "new" session ID from frontend - treat as fresh session
        session_id = request.session_id
        if session_id == "new":
            session_id = None

        # Process the message through the chat orchestrator
        response = await chat_orchestrator.process_chat_message(
            user_id=request.user_id,
            message=request.message,
            session_id=session_id,
            context=request.context
        )

        return ChatMessageResponse(
            success=response.get("success", True),
            message=response.get("message", "Message processed successfully"),
            session_id=response.get("session_id", request.session_id or "unknown"),
            intent=response.get("intent", "unknown"),
            confidence=response.get("confidence", 0.5),
            suggested_actions=response.get("suggested_actions", []),
            requires_confirmation=response.get("requires_confirmation", False),
            next_steps=response.get("next_steps", []),
            timestamp=response.get("timestamp", ""),
            metadata=response.get("data", {}) # Map 'data' to 'metadata' for frontend
        )

    except Exception as e:
        logger.error(f"Chat message processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.get("/memory/{session_id}")
async def get_chat_memory(session_id: str, user_id: str) -> ChatMemoryResponse:
    """
    Get memory/context for a specific chat session
    """
    try:
        logger.info(f"Retrieving memory for session {session_id} and user {user_id}")

        # Check if session exists
        if session_id not in chat_orchestrator.conversation_sessions:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        session = chat_orchestrator.conversation_sessions[session_id]
        if session.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return ChatMemoryResponse(
            session_id=session_id,
            memory_context=session.get("context", {}),
            timestamp=session.get("last_updated", "")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve chat memory: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat memory: {str(e)}")


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str, user_id: str) -> ChatHistoryResponse:
    """
    Get chat history for a specific session
    """
    try:
        logger.info(f"Retrieving history for session {session_id} and user {user_id}")

        # Lazy-load session if it doesn't exist (e.g. new chat from frontend)
        if session_id not in chat_orchestrator.conversation_sessions:
            logger.info(f"Session {session_id} not found, lazy-initializing for user {user_id}")
            session = chat_orchestrator._get_or_create_session(user_id, session_id)
        else:
            session = chat_orchestrator.conversation_sessions[session_id]

        # Verify user access (if we didn't just create it)
        # RELAXED CHECK: Allow 'default_user' to access everything in dev mode
        if session.get("user_id") != user_id and user_id != "default_user":
            logger.warning(f"Access denied: Session owner {session.get('user_id')} != Request user {user_id}")
            raise HTTPException(status_code=403, detail="Access denied")

        return ChatHistoryResponse(
            session_id=session_id,
            messages=session.get("history", []),
            timestamp=session.get("last_updated", "")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat history: {str(e)}")


@router.get("/sessions")
async def get_user_sessions(user_id: str) -> Dict[str, Any]:
    """
    Get all chat sessions for a user
    """
    try:
        logger.info(f"Retrieving sessions for user {user_id}")

        # Use orchestrator to get sessions (handles DB/File persistence)
        # Note: This returns a Dict[session_id, session_data]
        user_sessions = chat_orchestrator.get_user_sessions(user_id)

        return {
            "user_id": user_id,
            "sessions": user_sessions,
            "total_sessions": len(user_sessions)
        }

    except Exception as e:
        logger.error(f"Failed to retrieve user sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user sessions: {str(e)}")







@router.get("/health")
async def chat_health_check():
    """
    Health check for the chat system
    """
    try:
        # Test basic functionality
        test_session_id = "health_test"
        
        # Verify orchestrator is initialized
        is_initialized = chat_orchestrator is not None
        has_feature_handlers = len(chat_orchestrator.feature_handlers) > 0
        
        status = "healthy" if is_initialized and has_feature_handlers else "degraded"

        return {
            "status": status,
            "service": "atom_chat_system",
            "version": "1.0.0",
            "components": {
                "orchestrator": "initialized" if is_initialized else "not_initialized",
                "feature_handlers": "available" if has_feature_handlers else "unavailable",
                "platform_connectors": f"available ({len(chat_orchestrator.platform_connectors)})",
                "ai_engines": f"available ({len(chat_orchestrator.ai_engines)})"
            },
            "metrics": {
                "total_sessions": len(chat_orchestrator.conversation_sessions),
                "active_features": len(chat_orchestrator.feature_handlers),
                "connected_platforms": len(chat_orchestrator.platform_connectors)
            }
        }

    except Exception as e:
        logger.error(f"Chat health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "atom_chat_system",
            "error": str(e)
        }


@router.get("/")
async def chat_root():
    """
    Chat integration root endpoint
    """
    return {
        "service": "chat_integration",
        "status": "active",
        "version": "1.0.0",
        "description": "ATOM Chat Interface - Conversational Automation System",
        "endpoints": {
            "chat": {
                "/chat/message": "Send a chat message",
                "/chat/memory/{session_id}": "Get chat memory/context",
                "/chat/history/{session_id}": "Get chat history",
                "/chat/sessions": "Get user sessions",
            },
            "system": {
                "/chat/health": "Health check",
                "/chat/": "This endpoint"
            }
        }
    }