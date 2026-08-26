"""
Chat Routes - API endpoints for the ATOM chat interface
"""
import logging
import os
from datetime import datetime, timezone

# Add parent directory to path to import from backend
import sys
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from integrations.chat_orchestrator import ChatOrchestrator, FeatureType
from fastapi import Depends
from core.auth import get_current_user
from core.llm.routing_overrides import parse_routing_overrides
from core.models import User
from core.personal_scope import PERSONAL_TENANT_ID as CHAT_ROUTING_TENANT_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Initialize chat orchestrator
chat_orchestrator = ChatOrchestrator()

LEGACY_PLACEHOLDER_USER_IDS = frozenset({
    "", "default", "default_user", "anonymous", "anonymous_sales_user", "guest",
    "user", "test_user", "test_user_context", "test_user_agent", "test_user_e2e",
    "test_user_001", "test-user", "test-user-id", "unit_test_user",
    # Greptile PR #583 follow-up: sessions persisted with the all-zero (nil)
    # UUID owner are ownerless ghosts — no real user id can ever equal it, so
    # without this entry they load at startup and stay permanently unclaimable.
    "00000000-0000-0000-0000-000000000000",
})


def _is_legacy_placeholder_owner(owner: Optional[str]) -> bool:
    return (
        owner is None
        or not str(owner).strip()
        or str(owner) in LEGACY_PLACEHOLDER_USER_IDS
    )


def _persist_session_rebind(session_id: str, user_id: str) -> bool:
    """Durably re-point a reclaimed legacy session at its new owner.

    Delegates to the session manager so BOTH persistence stores are updated:
    the DB row (if present) and the startup JSON file (the store the
    orchestrator reloads at boot). A rebind that only touches memory would
    revert to placeholder ownership after a restart and expose the session to
    re-claiming (Greptile PR #582 finding). Returns True if the rebind was
    durably recorded in at least one store.
    """
    try:
        manager = chat_orchestrator.session_manager
        if manager is not None:
            return bool(manager.rebind_session_owner(session_id, user_id))
    except Exception as e:
        logger.warning(f"Could not persist session rebind: {e}")
    return False


def _ensure_session_access(session: Dict[str, Any], current_user: User) -> bool:
    """Return whether ``current_user`` may access ``session``.

    Legacy placeholder-owned sessions are reclaimed (rebound in the shared
    in-memory store and durably persisted) for the caller; a session owned by
    a different *real* user is refused. Reclamation fails closed: if the
    rebind cannot be recorded durably, access is refused and the in-memory
    rebind is rolled back, so the session can never revert to a claimable
    placeholder after a restart.
    """
    if current_user is None:
        # Greptile P1 (PR #591): an unresolvable user must never pass the
        # ownership check — previously the None case skipped this guard.
        return False
    owner = session.get("user_id")
    if owner is not None and str(owner) != str(current_user.id):
        if _is_legacy_placeholder_owner(owner):
            session["user_id"] = str(current_user.id)
            session_id = session.get("id") or session.get("session_id")
            if session_id and not _persist_session_rebind(str(session_id), str(current_user.id)):
                # Roll back the in-memory rebind and refuse access: without a
                # durable transfer the session reverts to placeholder ownership
                # after a restart and could be claimed by a different caller.
                session["user_id"] = owner
                logger.warning(
                    f"Refused to reclaim legacy chat session {session_id} "
                    f"(was owner={owner!r}) for user {current_user.id}: "
                    f"rebind could not be persisted durably"
                )
                return False
            logger.info(
                f"Reclaimed legacy chat session {session_id} (was owner={owner!r}) "
                f"for user {current_user.id}"
            )
            return True
        return False
    return True

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
    memory_context: Optional[str] = Field(None, description="Auto-retrieved memory context injected before this answer (memory transparency)")
    model: Optional[str] = Field(None, description="Which model produced the response")
    provider: Optional[str] = Field(None, description="Which provider served the response")
    error_code: Optional[str] = Field(None, description="Structured error code (e.g. no_llm_provider, budget_exceeded)")
    recovery_url: Optional[str] = Field(None, description="Recovery URL for structured errors")


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


@router.get("/harness-evolution")
async def get_harness_evolution_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retrieve weakness mining patterns and active harness patches for the agent registry."""
    from sqlalchemy.orm import Session
    from core.database import get_db
    from core.harness_evolution_service import HarnessEvolutionService
    from core.models import AgentRegistry

    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        tenant_id = current_user.tenant_id or "default"
        service = HarnessEvolutionService(db)

        try:
            patterns = await service.mine_weaknesses(tenant_id=tenant_id, lookback_hours=48)
        except Exception as e:
            logger.warning(f"Failed to mine weaknesses in API: {e}")
            patterns = []

        active_patches = []
        try:
            agents = db.query(AgentRegistry).filter(AgentRegistry.tenant_id == tenant_id).all()
            for a in agents:
                if a.configuration and "harness_patches" in a.configuration:
                    for patch in a.configuration["harness_patches"]:
                        active_patches.append({
                            "agent_id": a.id,
                            "agent_name": a.name,
                            "patch_id": patch.get("patch_id"),
                            "target_component": patch.get("target_component"),
                            "mutation_payload": patch.get("mutation_payload"),
                            "model_scope": patch.get("model_scope"),
                        })
        except Exception as e:
            logger.warning(f"Failed to retrieve active patches in API: {e}")

        return {
            "success": True,
            "mined_weaknesses": patterns,
            "active_patches": active_patches,
        }
    finally:
        db.close()


@router.get("/memory/{session_id}")
async def get_chat_memory(
    session_id: str,
    user_id: Optional[str] = "demo-user",
    current_user: User = Depends(get_current_user),
) -> ChatMemoryResponse:
    """
    Get memory/context for a specific chat session (authenticated).

    **Security**: requires authentication and verifies the caller owns the
    session (or reclaims a legacy placeholder-owner session durably).
    """
    try:
        logger.info(f"Retrieving memory for session {session_id} and user {current_user.id}")

        if session_id not in chat_orchestrator.conversation_sessions:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        session = chat_orchestrator.conversation_sessions[session_id]
        if not _ensure_session_access(session, current_user):
            logger.warning(
                f"Chat memory access denied: session {session_id} user mismatch "
                f"(expected: {current_user.id}, got: {session.get('user_id')})"
            )
            raise HTTPException(status_code=403, detail="Access denied")

        return ChatMemoryResponse(
            session_id=session_id,
            memory_context=session.get("context", {}),
            timestamp=session.get("last_updated", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve chat memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat memory")


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    user_id: Optional[str] = "demo-user",
    current_user: User = Depends(get_current_user),
) -> ChatHistoryResponse:
    """
    Get chat history for a specific session (authenticated).

    **Security**: requires authentication and verifies the caller owns the
    session; an ownerless legacy session is reclaimed durably for the caller.
    """
    try:
        logger.info(f"Retrieving history for session {session_id} and user {current_user.id}")

        if session_id not in chat_orchestrator.conversation_sessions:
            logger.info(
                f"Session {session_id} not found, lazy-initializing for user {current_user.id}"
            )
            session = chat_orchestrator._get_or_create_session(str(current_user.id), session_id)
        else:
            session = chat_orchestrator.conversation_sessions[session_id]

        if not _ensure_session_access(session, current_user):
            logger.warning(
                f"Chat history access denied: session {session_id} user mismatch "
                f"(expected: {current_user.id}, got: {session.get('user_id')})"
            )
            raise HTTPException(status_code=403, detail="Access denied")

        history = session.get("history", [])
        if not history:
            try:
                from core.database import get_db_session
                from core.models import ChatMessage as ChatMessageModel
                with get_db_session() as db:
                    rows = db.query(ChatMessageModel).filter(
                        ChatMessageModel.conversation_id == session_id
                    ).order_by(ChatMessageModel.created_at).all()
                    history = [
                        {
                            "message": row.content if row.role == "user" else None,
                            "response": {"message": row.content} if row.role == "assistant" else None,
                            "timestamp": row.created_at.isoformat() if row.created_at else None,
                        }
                        for row in rows
                    ]
                    if history:
                        logger.info(
                            f"Loaded {len(history)} messages from DB for session {session_id}"
                        )
            except Exception as db_err:
                logger.warning(f"Could not load history from DB: {db_err}")

        return ChatHistoryResponse(
            session_id=session_id,
            messages=history,
            timestamp=session.get("last_updated", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history")


@router.get("/sessions")
async def get_user_sessions(
    user_id: Optional[str] = "demo-user",
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get all chat sessions for the authenticated user.
    """
    try:
        logger.info(f"Retrieving sessions for user {user_id}")

        user_sessions = chat_orchestrator.get_user_sessions(str(current_user.id))
        return {
            "user_id": str(current_user.id),
            "sessions": user_sessions or {},
            "total_sessions": len(user_sessions) if user_sessions else 0,
        }

    except Exception as e:
        logger.error(f"Failed to retrieve user sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user sessions")


@router.get("/health")
async def chat_health_check():
    """
    Health check for the chat system
    """
    try:
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
                "ai_engines": f"available ({len(chat_orchestrator.ai_engines)})",
            },
            "metrics": {
                "total_sessions": len(chat_orchestrator.conversation_sessions),
                "active_features": len(chat_orchestrator.feature_handlers),
                "connected_platforms": len(chat_orchestrator.platform_connectors),
            },
        }

    except Exception as e:
        logger.error(f"Chat health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "atom_chat_system",
            "error": str(e),
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
                "/chat/": "This endpoint",
            },
        },
    }


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


class ChatFeedbackRequest(BaseModel):
    """User feedback on a chat response (the previously-dead feedback loop)."""
    message_id: str = Field(..., description="The message the feedback is about")
    feedback: str = Field(..., description='"thumbs_up" or "thumbs_down"')
    comment: Optional[str] = Field(None, description="Optional free-text feedback")
    memory_context: Optional[str] = Field(None, description="Auto-retrieved memory context injected before this answer (memory transparency)")
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
    Rename a chat session (authenticated with dev fallback)
    """
    try:
        active_user_id = str(current_user.id) if current_user else (request.user_id or "demo-user")
        request.user_id = active_user_id

        # Check permissions first
        session = chat_orchestrator.conversation_sessions.get(session_id)
        if not session:
            managed_session = chat_orchestrator.session_manager.get_session(session_id)
            if managed_session:
                session = managed_session

        if not session:
             raise HTTPException(status_code=404, detail="Session not found")

        if current_user and not _ensure_session_access(session, current_user):
             logger.warning(f"Rename denied: Owner {session.get('user_id')} != Requestor {current_user.id}")
             raise HTTPException(status_code=403, detail="Access denied")

        # The rename logic lives on the session manager (DB + file sync) — the
        # orchestrator has no rename_session method. Update the in-memory
        # session cache AND the durable store.
        session["title"] = request.title
        success = True
        if chat_orchestrator.session_manager is not None:
            success = bool(
                chat_orchestrator.session_manager.rename_session(session_id, request.title)
            )

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
    user_id: Optional[str] = "demo-user",
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get details for a specific session (authenticated).
    """
    try:
        session = chat_orchestrator.conversation_sessions.get(session_id)

        if not session:
             managed_session = chat_orchestrator.session_manager.get_session(session_id)
             if managed_session:
                 session = managed_session

        if not session:
             raise HTTPException(status_code=404, detail="Session not found")

        if not _ensure_session_access(session, current_user):
             logger.warning(
                 f"Session details denied: Owner {session.get('user_id')} != Requestor {current_user.id}"
             )
             raise HTTPException(status_code=403, detail="Access denied")

        return {
            "success": True,
            "session_id": session.get("id") or session.get("session_id") or session_id,
            "title": session.get("title") or "New Chat",
            "created_at": session.get("created_at") or datetime.now().isoformat(),
            "user_id": session.get("user_id") or str(current_user.id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session details: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session details")



# API Routes
@router.post("/message")
async def send_chat_message(
    request: ChatMessageRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user)
) -> ChatMessageResponse:
    """
    Send a chat message to the ATOM chat orchestrator (authenticated with optional dev fallback)
    """
    try:
        # Resolve active user ID
        active_user_id = str(current_user.id) if current_user else (request.user_id or "demo-user")
        request.user_id = active_user_id

        logger.info(f"Processing chat message from user {active_user_id}: {request.message}")

        # Handle "new" session ID from frontend - treat as fresh session
        session_id = request.session_id
        if session_id == "new":
            session_id = None

        # Parse optional x-atom-* routing override headers.
        try:
            routing_overrides = parse_routing_overrides(http_request.headers)
        except Exception:
            logger.debug("Failed to parse routing override headers", exc_info=True)
            routing_overrides = {}

        # Process the message through the chat orchestrator
        response = await chat_orchestrator.process_chat_message(
            user_id=active_user_id,
            message=request.message,
            session_id=session_id,
            context=request.context,
            routing_overrides=routing_overrides or None,
        )

        # Detect the "no LLM provider configured" sentinel and surface it as a
        # structured error so the frontend shows the recovery banner (linking
        # to /settings/ai) instead of a junk assistant message. The orchestrator
        # returns these sentinels as the message string when no provider key is
        # configured.
        response_msg = response.get("message", "") or ""
        _NO_PROVIDER_MARKERS = (
            "llm client not initialized",
            "no api keys configured",
            "no eligible llm providers",
        )
        if any(m in response_msg.lower() for m in _NO_PROVIDER_MARKERS):
            return ChatMessageResponse(
                success=False,
                message="You need an AI provider to use chat. Add an API key in Settings to get started.",
                session_id=response.get("session_id") or request.session_id or "unknown",
                intent="unknown",
                confidence=0.5,
                suggested_actions=[],
                requires_confirmation=False,
                next_steps=[],
                timestamp=datetime.utcnow().isoformat(),
                error_code="no_llm_provider",
                recovery_url="/settings/ai",
            )

        # Budget-exceeded short-circuit: surface the structured signal so the
        # frontend can render a distinct budget-halted UI (mirrors the
        # no_llm_provider convention above). The orchestrator sets error_code
        # when the agent's budget gate halted the run.
        if response.get("error_code") == "budget_exceeded":
            return ChatMessageResponse(
                success=False,
                message=response.get("message", "Budget limit reached — execution halted."),
                session_id=response.get("session_id") or request.session_id or "unknown",
                intent="unknown",
                confidence=0.5,
                suggested_actions=[],
                requires_confirmation=False,
                next_steps=[],
                timestamp=datetime.utcnow().isoformat(),
                error_code="budget_exceeded",
                recovery_url=response.get("recovery_url", "/settings/billing"),
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
            memory_context=response.get("memory_context"),
            model=response.get("model"),
            provider=response.get("provider"),
        )

    except Exception as e:
        logger.error(f"Chat message processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Chat processing failed")


@router.post("/cancel/{session_id}")
async def cancel_chat(
    session_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Cancel an in-flight chat message for a session.

    Marks the session as cancelled so the orchestrator returns early between
    processing steps. Best-effort: if the LLM call is already in-flight, the
    cancel takes effect after it returns. The frontend's AbortController drops
    the connection immediately; this endpoint prevents the backend from
    continuing unnecessary work (e.g. tool execution, follow-up steps).
    """
    chat_orchestrator.request_cancellation(session_id)
    return {"cancelled": True, "session_id": session_id}


def _learning_router_enabled() -> bool:
    """Whether the learning router is enabled (flag-gated)."""
    from core.llm.learning_router_registry import learning_router_enabled
    return learning_router_enabled()


def _ema_router_enabled() -> bool:
    """Whether the EMA (online telemetry) scoring path is enabled.

    Mirrors the centralized parse in the registry (accepts 1/true/yes/on) so the
    dashboard agrees with the scoring branch — previously this endpoint used a
    "true"-only check that disagreed with what the router actually honored.
    """
    from core.llm.learning_router_registry import ema_router_enabled
    return ema_router_enabled()


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

        model_id = request.model or "unknown"

        # Recover the REAL task_type and routing_result_id for this message by
        # correlating with the most recent outcome feedback the BYOK hook
        # recorded for this (tenant, model). Previously this was hardcoded to
        # task_type="question_answering" and keyed by the chat message_id (which
        # never matched the outcome hook's uuid), so explicit feedback landed in
        # the wrong task bucket and never recovered prompt features (Bug 5).
        resolved_task, resolved_id = learning_router.resolve_feedback_context(
            CHAT_ROUTING_TENANT_KEY, model_id
        )
        task_type = resolved_task or "question_answering"
        # Prefer the routing_result_id the outcome hook used (so feedback recovers
        # the real prompt features); fall back to the chat message_id, then a
        # fresh id. Note the id only matters for feature recovery — record_feedback
        # degrades gracefully to task defaults when it's not found.
        import uuid as _uuid
        decision_id = resolved_id or request.message_id or str(_uuid.uuid4())

        fb = LearningBasedRouter.build_feedback(
            routing_result_id=decision_id,
            tenant_id=CHAT_ROUTING_TENANT_KEY,
            model_id=model_id,
            task_type=task_type,
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
    ema_enabled = _ema_router_enabled()
    
    if not enabled and not ema_enabled:
        return {"enabled": False, "ema_enabled": False, "stats": {"feedback_samples": 0, "model_success_rates": {}, "ema_scores": {}}}

    learning_router = _get_learning_router()
    if learning_router is None:
        return {"enabled": enabled, "ema_enabled": ema_enabled, "stats": {"feedback_samples": 0, "model_success_rates": {}, "ema_scores": {}}}

    try:
        stats = await learning_router.get_routing_statistics(CHAT_ROUTING_TENANT_KEY)
        return {"enabled": enabled, "ema_enabled": ema_enabled, "stats": stats}
    except Exception as e:
        logger.warning(f"Failed to get routing stats: {e}")
        return {"enabled": enabled, "ema_enabled": ema_enabled, "stats": {"error": str(e)}}
