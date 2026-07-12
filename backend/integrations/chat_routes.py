"""
Chat Routes - API endpoints for the ATOM chat interface
"""
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.models import User
from core.security_dependencies import get_current_user
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
    model: Optional[str] = Field(None, description="Which model produced the response")
    provider: Optional[str] = Field(None, description="Which provider served the response")


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


class ChatFeedbackRequest(BaseModel):
    """User feedback on a chat response (the previously-dead feedback loop)."""
    message_id: str = Field(..., description="The message the feedback is about")
    feedback: str = Field(..., description='"thumbs_up" or "thumbs_down"')
    comment: Optional[str] = Field(None, description="Optional free-text feedback")
    model: Optional[str] = Field(None, description="Which model produced the response")
    provider: Optional[str] = Field(None, description="Which provider served the response")
    session_id: Optional[str] = Field(None, description="Conversation session ID")


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    request: RenameSessionRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Rename a chat session (authenticated)

    **Security**: Requires authentication and verifies user owns the session
    """
    try:
        # Override body-supplied user_id with the authenticated user's ID.
        # The frontend historically sends "default_user" here; the token is
        # the authoritative source.
        request.user_id = str(current_user.id)

        # Check permissions first
        session = chat_orchestrator.conversation_sessions.get(session_id)
        if not session:
            # Try lazy load check via manager
            managed_session = chat_orchestrator.session_manager.get_session(session_id)
            if managed_session:
                session = managed_session

        if not session:
             raise HTTPException(status_code=404, detail="Session not found")

        if session.get("user_id") != current_user.id:
             logger.warning(f"Rename denied: Owner {session.get('user_id')} != Requestor {current_user.id}")
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
        raise HTTPException(status_code=500, detail="Failed to rename session")

@router.get("/sessions/{session_id}")
async def get_session_details(
    session_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get details for a specific session (authenticated)

    **Security**: Requires authentication and verifies user owns the session
    """
    try:
        # Override query-param user_id with the authenticated user's ID.
        user_id = str(current_user.id)

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

        # Additional verification: ensure session belongs to the authenticated user
        if session.get("user_id") != current_user.id:
            logger.warning(
                f"Chat access denied: session {session_id} user mismatch "
                f"(expected: {current_user.id}, got: {session.get('user_id')})"
            )
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
        raise HTTPException(status_code=500, detail="Failed to get session details")



# API Routes
@router.post("/message")
async def send_chat_message(
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user)
) -> ChatMessageResponse:
    """
    Send a chat message to the ATOM chat orchestrator (authenticated)

    **Security**: Requires authentication and verifies user matches request.user_id
    """
    try:
        # Override body-supplied user_id with the authenticated user's ID.
        request.user_id = str(current_user.id)

        logger.info(f"Processing chat message from user {current_user.id}: {request.message}")

        # Handle "new" session ID from frontend - treat as fresh session
        session_id = request.session_id
        if session_id == "new":
            session_id = None

        # Process the message through the chat orchestrator
        # Use authenticated user_id instead of request.user_id
        response = await chat_orchestrator.process_chat_message(
            user_id=current_user.id,
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
            metadata=response.get("data", {}), # Map 'data' to 'metadata' for frontend
            model=response.get("model"),
            provider=response.get("provider"),
        )

    except Exception as e:
        logger.error(f"Chat message processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Chat processing failed")


def _learning_router_enabled() -> bool:
    """Whether the learning router is enabled (flag-gated)."""
    from core.llm.learning_router_registry import learning_router_enabled
    return learning_router_enabled()


def _get_learning_router():
    """Return the process-wide learning router singleton (or None).

    Uses the singleton registry so predictors accumulate across requests
    instead of being trained into throwaway instances.
    """
    from core.llm.learning_router_registry import get_learning_router_instance
    return get_learning_router_instance()


@router.post("/feedback")
async def submit_chat_feedback(
    request: ChatFeedbackRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Submit feedback on a chat response.

    This is the live feedback endpoint (replacing the dead /api/atom-agent/feedback
    path). When the learning router is enabled, feedback is recorded as a
    RoutingFeedback with the user's thumbs-up/down mapped to a satisfaction
    signal, and persists to DB for predictor training. When disabled, it
    returns 200 without recording (so the UI never errors).
    """
    feedback_val = request.feedback.lower().strip()
    if feedback_val not in ("thumbs_up", "thumbs_down"):
        raise HTTPException(status_code=422, detail="feedback must be 'thumbs_up' or 'thumbs_down'")

    learning_router = _get_learning_router()
    if learning_router is None:
        # Disabled — acknowledge but don't record.
        return {"success": True, "recorded": False, "reason": "learning_router_disabled"}

    try:
        from core.learning_llm_router import LearningBasedRouter
        from core.llm.response_quality import ResponseQuality
        import uuid

        # Map explicit user feedback to a quality assessment. Thumbs-down with
        # a comment is a stronger negative signal than a bare thumbs-down.
        if feedback_val == "thumbs_up":
            quality = ResponseQuality(
                success=True, quality_satisfied=True,
                quality_score=0.95, issues=[],
            )
        else:
            score = 0.15 if request.comment else 0.3
            quality = ResponseQuality(
                success=True, quality_satisfied=False,
                quality_score=score, issues=["user_thumbs_down"],
            )

        fb = LearningBasedRouter.build_feedback(
            routing_result_id=request.message_id,
            tenant_id=_resolve_tenant_id(current_user.id),
            model_id=request.model or "unknown",
            task_type="question_answering",  # chat path default
            quality=quality,
        )
        await learning_router.record_feedback(fb)
        return {"success": True, "recorded": True}
    except Exception as e:
        logger.warning(f"Failed to record chat feedback (non-fatal): {e}")
        return {"success": True, "recorded": False, "reason": str(e)}


@router.get("/routing-stats")
async def get_routing_stats(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Routing-learning statistics for the dashboard.

    Returns per-model success rates, total feedback samples, and whether the
    learning router is enabled. When disabled, returns the stats that exist
    (possibly empty) with enabled=false so the dashboard can show an honest
    'Learning Router is off' banner.
    """
    enabled = _learning_router_enabled()
    if not enabled:
        return {"enabled": False, "stats": {"feedback_samples": 0, "model_success_rates": {}}}

    learning_router = _get_learning_router()
    if learning_router is None:
        return {"enabled": False, "stats": {"feedback_samples": 0, "model_success_rates": {}}}

    try:
        stats = await learning_router.get_routing_statistics(_resolve_tenant_id(current_user.id))
        return {"enabled": True, "stats": stats}
    except Exception as e:
        logger.warning(f"Failed to get routing stats: {e}")
        return {"enabled": True, "stats": {"error": str(e)}}


def _resolve_tenant_id(user_id) -> str:
    """Resolve the tenant id for a user, matching the BYOKHandler's tenant key.

    The outcome-observation path records feedback under the BYOKHandler's
    ``self.tenant_id`` (workspace-scoped). To keep explicit user feedback in
    the same namespace (so the dashboard aggregates correctly), resolve the
    user → workspace → tenant here. Falls back to the string user id when the
    lookup fails (single-user/dev setups).
    """
    try:
        from core.database import get_db_session
        from core.models import Workspace, Tenant
        with get_db_session() as db:
            ws = db.query(Workspace).filter(Workspace.owner_id == user_id).first()
            if ws and ws.tenant_id:
                return ws.tenant_id
            # Fall back: any workspace the user belongs to.
            ws = db.query(Workspace).first()
            if ws and ws.tenant_id:
                return ws.tenant_id
    except Exception:
        pass
    return str(user_id)



async def get_chat_memory(
    session_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user)
) -> ChatMemoryResponse:
    """
    Get memory/context for a specific chat session (authenticated)

    **Security**: Requires authentication and verifies user owns the session
    """
    try:
        # Override query-param user_id with the authenticated user's ID.
        user_id = str(current_user.id)

        logger.info(f"Retrieving memory for session {session_id} and user {current_user.id}")

        # Check if session exists
        if session_id not in chat_orchestrator.conversation_sessions:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        session = chat_orchestrator.conversation_sessions[session_id]
        # Verify session belongs to authenticated user
        if session.get("user_id") != current_user.id:
            logger.warning(
                f"Chat memory access denied: session {session_id} user mismatch "
                f"(expected: {current_user.id}, got: {session.get('user_id')})"
            )
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
        raise HTTPException(status_code=500, detail="Failed to retrieve chat memory")


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user)
) -> ChatHistoryResponse:
    """
    Get chat history for a specific session (authenticated)

    **Security**: Requires authentication and verifies user owns the session
    """
    try:
        # Override query-param user_id with the authenticated user's ID.
        user_id = str(current_user.id)

        logger.info(f"Retrieving history for session {session_id} and user {current_user.id}")

        # Lazy-load session if it doesn't exist (e.g. new chat from frontend)
        if session_id not in chat_orchestrator.conversation_sessions:
            logger.info(f"Session {session_id} not found, lazy-initializing for user {current_user.id}")
            session = chat_orchestrator._get_or_create_session(current_user.id, session_id)
        else:
            session = chat_orchestrator.conversation_sessions[session_id]

        # Verify session belongs to authenticated user (prevents IDOR)
        if session.get("user_id") != current_user.id:
            logger.warning(
                f"Chat history access denied: session {session_id} user mismatch "
                f"(expected: {current_user.id}, got: {session.get('user_id')})"
            )
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
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history")


@router.get("/sessions")
async def get_user_sessions(
    user_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get all chat sessions for a user (authenticated)

    **Security**: Requires authentication and verifies user matches requested user_id
    """
    try:
        # Override query-param user_id with the authenticated user's ID.
        user_id = str(current_user.id)

        logger.info(f"Retrieving sessions for user {current_user.id}")

        # Use orchestrator to get sessions (handles DB/File persistence)
        # Note: This returns a Dict[session_id, session_data]
        user_sessions = chat_orchestrator.get_user_sessions(current_user.id)

        return {
            "user_id": current_user.id,
            "sessions": user_sessions,
            "total_sessions": len(user_sessions)
        }

    except Exception as e:
        logger.error(f"Failed to retrieve user sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user sessions")







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