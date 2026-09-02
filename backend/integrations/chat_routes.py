"""
Chat Routes - API endpoints for the ATOM chat interface
"""
import logging
import re
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
from core.database import get_db
from sqlalchemy.orm import Session as _Session
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


def _resolve_canvas_agent_id(canvas_id: str, tenant_id: Optional[str]) -> Optional[str]:
    """Which hire works this canvas? Resolution mirrors the training panel's
    provenance order (api/agent_maturity_routes.get_canvas_training_context):
    the per-canvas context binding first, then canvas audit provenance. Only
    returns agents that still exist in the registry. Fault-isolated.
    """
    if not canvas_id:
        return None
    try:
        from core.database import get_db_session
        from core.models import AgentRegistry, CanvasAudit, CanvasContext
        from sqlalchemy import desc

        with get_db_session() as db:
            ctx = (
                db.query(CanvasContext)
                .filter(CanvasContext.canvas_id == canvas_id)
                .first()
            )
            candidates: list = []
            if ctx is not None and ctx.agent_id:
                candidates.append(ctx.agent_id)
            # Several audit rows can share a created_at timestamp (same
            # commit) — collect a handful of distinct agent ids, don't bet
            # the resolution on tie-broken ordering.
            for (audit_agent,) in (
                db.query(CanvasAudit.agent_id)
                .filter(
                    CanvasAudit.canvas_id == canvas_id,
                    CanvasAudit.agent_id.isnot(None),
                )
                .order_by(desc(CanvasAudit.created_at))
                .limit(5)
                .all()
            ):
                if audit_agent and audit_agent not in candidates:
                    candidates.append(audit_agent)
            for agent_id in candidates:
                agent = (
                    db.query(AgentRegistry)
                    .filter(AgentRegistry.id == agent_id)
                    .first()
                )
                if agent is not None:
                    return agent.id
        return None
    except Exception as e:
        logger.debug(f"canvas agent resolution skipped: {e}")
        return None


def _canvas_provenance_context(
    canvas_id: Optional[str],
    current_session_id: Optional[str],
    max_messages: int = 8,
) -> Optional[Dict[str, Any]]:
    """Hydrate the ORIGIN conversation of a canvas: the chat thread this
    canvas was created from, resolved through the create-audit row's
    ``session_id`` (written by chat_draft_to_canvas).

    The canvas panel starts its own session, so a turn on /canvas/{id} had
    ``conversation_history: []`` even minutes after "generate the draft" —
    the co-editor honestly answered "I don't know who wrote this draft" to
    the provenance question that follows it (observed live 2026-09-02,
    canvas da27bb76…: the origin thread aca15165… sat one query away). The
    returned messages ride to the orchestrator as ``context[
    'canvas_provenance']`` and enter the prompts as clearly-labeled,
    non-evidentiary background. Skipped when the canvas was created in the
    SAME session that is chatting now (the live transcript already has it).
    Fault-isolated: any failure returns None and the turn proceeds without
    provenance.
    """
    if not canvas_id:
        return None
    try:
        from sqlalchemy import asc, desc

        from core.database import get_db_session
        from core.models import CanvasAudit, ChatMessage

        with get_db_session() as db:
            create_row = (
                db.query(CanvasAudit.session_id)
                .filter(
                    CanvasAudit.canvas_id == str(canvas_id),
                    CanvasAudit.action_type == "create",
                )
                .order_by(asc(CanvasAudit.created_at))
                .first()
            )
            origin_session = (create_row or (None,))[0] if create_row else None
            if not origin_session or origin_session == current_session_id:
                return None
            rows = (
                db.query(ChatMessage)
                .filter(ChatMessage.conversation_id == origin_session)
                .order_by(desc(ChatMessage.created_at))
                .limit(max_messages)
                .all()
            )
            messages = [
                {"role": row.role, "content": str(row.content or "")}
                for row in reversed(rows)
                if (row.role or "") in ("user", "assistant")
                and str(row.content or "").strip()
            ]
            if not messages:
                return None
            return {"session_id": origin_session, "messages": messages}
    except Exception as e:
        logger.debug(f"canvas provenance hydration skipped: {e}")
        return None


def _bind_canvas_chat_session(
    canvas_id: Optional[str],
    canvas_type: str,
    user_id: str,
    tenant_id: Optional[str],
    agent_id: Optional[str],
    session_id: Optional[str],
) -> bool:
    """Record which chat conversation is serving a canvas's co-editor panel.

    Stored in the canvas's per-user context row (CanvasContext.current_state
    under ``chat_session_id``) so the /canvas/{id} panel can reattach to the
    same thread on ANY device — a localStorage pointer only ever worked in the
    browser that wrote it. Latest turn wins, mirroring the panel's own
    behavior. Fault-isolated: a binding failure never breaks the chat turn.
    """
    if not canvas_id or not session_id or session_id in ("new", "unknown"):
        return False
    try:
        from core.database import get_db_session
        from core.service_factory import ServiceFactory

        with get_db_session() as db:
            service = ServiceFactory.get_canvas_context_service(
                db, tenant_id=tenant_id
            )
            context = service.get_or_create_context(
                canvas_id=str(canvas_id),
                canvas_type=canvas_type or "generic",
                user_id=user_id,
                agent_id=agent_id,
            )
            # get_or_create only sets agent_id at CREATION: a canvas bound
            # before it had a hire keeps None forever. Stamp the resolved
            # agent so training-context resolution and the correction loop
            # (record_user_correction reads context.agent_id) see the hire.
            if agent_id and context.agent_id != agent_id:
                context.agent_id = agent_id
                db.commit()
            return bool(service.update_state(
                canvas_id=str(canvas_id),
                user_id=user_id,
                state_update={"chat_session_id": str(session_id)},
            ))
    except Exception as e:
        # Warning, not debug: a binding that silently never persists looks
        # exactly like "panel history doesn't survive refresh" (e.g. a
        # production install whose migrations lack canvas_contexts).
        logger.warning(f"canvas chat-session binding skipped: {e}")
        return False


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
    agent_id: Optional[str] = Field(None, description="Explicit agent selection — session-linked agent chats record graduation episodes")


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


@router.post("/harness-evolution/mine")
async def remine_harness_weaknesses(
    lookback_hours: int = 48,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Run a real weakness-mining pass over recent execution traces.

    Read-only analysis (mine → report counts); patch proposal, sandbox
    validation and deployment stay in their own governed flow. Mirrors the
    GET's graceful failure: a mining error returns success with an empty
    pattern list rather than a 500.
    """
    from core.harness_evolution_service import HarnessEvolutionService

    db_gen = get_db()
    db: _Session = next(db_gen)
    try:
        tenant_id = current_user.tenant_id or "default"
        lookback = min(max(int(lookback_hours), 1), 24 * 30)
        try:
            service = HarnessEvolutionService(db)
            patterns = await service.mine_weaknesses(
                tenant_id=tenant_id, lookback_hours=lookback
            )
        except Exception as e:
            logger.warning(f"Failed to re-mine weaknesses in API: {e}")
            patterns = []
        return {
            "success": True,
            "mined_weaknesses": patterns,
            "pattern_count": len(patterns),
            "total_failures": sum(
                int(p.get("failure_count") or 0) for p in patterns
            ),
            "lookback_hours": lookback,
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

        # The durable store is authoritative: read SQL rows first (they carry
        # real message ids the fork-from-here journey needs), in the same
        # order hydration uses. In-memory history is a legacy fallback.
        history: list = []
        try:
            from core.database import get_db_session
            from core.models import ChatMessage as ChatMessageModel
            with get_db_session() as db:
                rows = (
                    db.query(ChatMessageModel)
                    .filter(ChatMessageModel.conversation_id == session_id)
                    .order_by(
                        ChatMessageModel.created_at.asc(),
                        ChatMessageModel.role.desc(),
                    )
                    .all()
                )
                history = [
                    {
                        "id": row.id,
                        "role": row.role,
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
        if not history:
            history = session.get("history", [])

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


@router.get("/trace/{session_id}")
async def get_session_agent_trace(
    session_id: str,
    limit: int = 10,
    db: _Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get the agent execution trace (runs + reasoning steps) for a chat session.

    Powers the Agent Workspace panel's history restore: chat-triggered
    meta-agent runs persist AgentReasoningStep rows and are joined back to
    the session via AgentExecution.metadata_json["session_id"]. Ownership is
    enforced the same way as /history/{session_id}; unknown sessions simply
    have no runs and return an empty list.
    """
    from sqlalchemy import func
    from core.models import AgentExecution, AgentReasoningStep

    try:
        known = chat_orchestrator.conversation_sessions.get(session_id)
        if known is not None and not _ensure_session_access(known, current_user):
            raise HTTPException(status_code=403, detail="Access denied")

        limit = max(1, min(limit, 50))
        executions = (
            db.query(AgentExecution)
            .filter(
                func.json_extract(AgentExecution.metadata_json, '$.session_id')
                == session_id
            )
            .order_by(AgentExecution.started_at.desc())
            .limit(limit)
            .all()
        )
        if not executions:
            return {"runs": [], "session_id": session_id}

        execution_ids = [e.id for e in executions]
        steps = (
            db.query(AgentReasoningStep)
            .filter(AgentReasoningStep.execution_id.in_(execution_ids))
            .order_by(AgentReasoningStep.step_number.asc())
            .all()
        )
        steps_by_execution: Dict[str, list] = {}
        for s in steps:
            action_value = s.action
            action_input = ""
            if isinstance(action_value, dict):
                action_input = str(action_value.get("params") or "")
                action_value = str(action_value.get("tool") or action_value)
            steps_by_execution.setdefault(s.execution_id, []).append({
                "step_number": s.step_number,
                "step_type": s.step_type,
                "thought": s.thought,
                "action": action_value if isinstance(action_value, str) else (str(action_value) if action_value else ""),
                "action_input": action_input,
                "observation": s.observation,
                "confidence": s.confidence,
                "verified": s.verified,
                "verification_evidence": s.verification_evidence,
                "duration_ms": s.duration_ms,
                "resolved_model": s.resolved_model,
                "feedback_score": s.feedback_score,
                "feedback_text": s.feedback_text,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            })

        runs = [
            {
                "execution_id": e.id,
                "agent_id": e.agent_id,
                "status": e.status,
                "triggered_by": e.triggered_by,
                "input_summary": e.input_summary,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "duration_seconds": e.duration_seconds,
                "steps": steps_by_execution.get(e.id, []),
            }
            for e in executions
        ]
        return {"runs": runs, "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve agent trace for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agent trace")


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


class ForkSessionRequest(BaseModel):
    """Fork a chat session ("fork from here" when up_to_message_id is set)."""
    up_to_message_id: Optional[str] = Field(
        None,
        description="Copy the conversation up to and including this message id",
    )


@router.post("/sessions/{session_id}/fork")
async def fork_chat_session(
    session_id: str,
    payload: Optional[ForkSessionRequest] = None,
    db: _Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Fork a chat session: create a new session owned by the same user and copy
    the SQL-persisted conversation into it, so the user can branch without
    polluting the original. Optionally pass up_to_message_id to fork from a
    specific point in the conversation ("fork from here"). External
    channel/thread bindings are NOT inherited — a fork is a fresh local
    conversation.
    """
    import uuid as _uuid
    from core.models import ChatMessage as ChatMessageModel
    from core.models import ChatSession as ChatSessionModel

    up_to_message_id = payload.up_to_message_id if payload else None

    # Same ownership gate as /history: unknown sessions lazy-initialize for
    # the caller, known ones must belong to them.
    if session_id not in chat_orchestrator.conversation_sessions:
        session = chat_orchestrator._get_or_create_session(str(current_user.id), session_id)
    else:
        session = chat_orchestrator.conversation_sessions[session_id]
    if not _ensure_session_access(session, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # Chronological order matches history hydration exactly.
        rows = (
            db.query(ChatMessageModel)
            .filter(ChatMessageModel.conversation_id == session_id)
            .order_by(
                ChatMessageModel.created_at.asc(),
                ChatMessageModel.role.desc(),
            )
            .all()
        )
        if not rows:
            return {"success": False, "error": "Session not found"}

        if up_to_message_id:
            idx = next((i for i, r in enumerate(rows) if r.id == up_to_message_id), None)
            if idx is None:
                return {
                    "success": False,
                    "error": f"up_to_message_id {up_to_message_id} not found in session",
                }
            rows = rows[: idx + 1]

        source_row = (
            db.query(ChatSessionModel)
            .filter(ChatSessionModel.id == session_id)
            .first()
        )
        tenant_id = getattr(source_row, "tenant_id", None) or "default"
        source_title = (source_row.title if source_row else None) or session.get("title") or "Chat"

        fork_id = str(_uuid.uuid4())
        forked_at = datetime.now(timezone.utc).isoformat()
        fork_session_row = ChatSessionModel(
            id=fork_id,
            user_id=str(current_user.id),
            title=f"Fork: {source_title}",
            # Lineage on the row; channel/thread bindings deliberately
            # not inherited (external replies keep routing to the original).
            metadata_json={
                "forked_from": session_id,
                "forked_at": forked_at,
            },
            message_count=len(rows),
        )
        db.add(fork_session_row)

        copied = 0
        for row in rows:
            try:
                db.add(ChatMessageModel(
                    id=str(_uuid.uuid4()),
                    conversation_id=fork_id,
                    tenant_id=row.tenant_id or tenant_id,
                    role=row.role,
                    content=row.content,
                    agent_id=row.agent_id,
                    metadata_json=row.metadata_json,
                ))
                copied += 1
            except Exception as row_err:
                logger.warning(
                    f"Failed to copy message {row.id} into fork {fork_id}: {row_err}"
                )
        db.commit()

        # Register the fork in the in-memory store so the sidebar lists it
        # immediately and history loads without a lazy-init round trip.
        chat_orchestrator._get_or_create_session(str(current_user.id), fork_id)

        return {
            "success": True,
            "session_id": fork_id,
            "forked_from": session_id,
            "messages_copied": copied,
            "title": f"Fork: {source_title}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fork chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fork chat session")


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
        # agent_id into context → role-aware memory recall scopes to the
        # hire's domain (Sales-tagged records surface first for the SDR).
        # Bind the chat turn's session/agent for the duration of processing —
        # tool-time audit rows (canvas edits, guidance canvases) attribute to
        # this session so training episodes capture the agent's canvas work.
        from core.chat_session_context import set_chat_context, reset_chat_context

        logger.info(f"[CHATCTX] request.agent_id={getattr(request, 'agent_id', None)!r} context={request.context!r}")

        # Canvas co-editor identity: a canvas SHOULD be worked by an agent
        # (the AI-employee model), not the anonymous platform assistant. When
        # the client didn't name one, resolve the canvas's own hire the same
        # way the training panel does — the per-canvas context binding first,
        # then canvas provenance (audit rows carry the creating/editing
        # agent). Everything downstream (persona, role-scoped memory, tier
        # behavior, audit attribution, learning loop) keys off agent_id.
        _canvas_id_for_agent = (request.context or {}).get("canvas_id")
        if not getattr(request, "agent_id", None) and _canvas_id_for_agent:
            _resolved = _resolve_canvas_agent_id(
                str(_canvas_id_for_agent),
                tenant_id=getattr(current_user, "tenant_id", None),
            )
            if _resolved:
                request.agent_id = _resolved
                logger.info(
                    f"[CHATCTX] canvas {_canvas_id_for_agent} resolved agent "
                    f"{_resolved} — co-editor turn runs as the canvas's hire"
                )

        context_with_agent = {
            **(request.context or {}),
            "agent_id": getattr(request, "agent_id", None)
            or ((request.context or {}).get("agent_id")),
        }
        # Canvas turns: hydrate the ORIGIN conversation (the thread the
        # canvas was created from) so provenance questions ("why was the
        # draft written this way?") are answerable from the panel — the
        # panel's own session history starts empty by design.
        if _canvas_id_for_agent and not context_with_agent.get("canvas_provenance"):
            _prov = _canvas_provenance_context(
                str(_canvas_id_for_agent), session_id
            )
            if _prov:
                context_with_agent["canvas_provenance"] = _prov
                logger.info(
                    f"[CHATCTX] canvas {_canvas_id_for_agent} origin session "
                    f"{_prov['session_id']} hydrated ({len(_prov['messages'])} messages)"
                )
        _ctx_tokens = set_chat_context(session_id, getattr(request, "agent_id", None))
        try:
            response = await chat_orchestrator.process_chat_message(
                user_id=active_user_id,
                message=request.message,
                session_id=session_id,
                context=context_with_agent,
                routing_overrides=routing_overrides or None,
            )
        finally:
            reset_chat_context(_ctx_tokens)

        # Canvas co-editor binding (DB-backed): when the turn ran against an
        # open canvas, remember which conversation served it, in the canvas's
        # per-user context store. The /canvas/{id} panel reads this binding on
        # load (GET /api/canvas/{id}/context) to reattach to the same thread
        # across refreshes AND devices — localStorage only ever worked
        # per-browser. Latest turn wins, which is the panel's own behavior.
        _bind_canvas_chat_session(
            canvas_id=(request.context or {}).get("canvas_id"),
            canvas_type=(request.context or {}).get("canvas_type") or "generic",
            user_id=active_user_id,
            tenant_id=getattr(current_user, "tenant_id", None),
            agent_id=getattr(request, "agent_id", None),
            session_id=response.get("session_id"),
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

        # R81-parity: session-linked agent chats accumulate episodic memory.
        # The atom-agent chat endpoint triggers episode creation, but this —
        # the live chat surface — never did, so agents trained through
        # /api/chat/message never registered graduation episodes.
        #
        # R88-parity: this surface also never recorded OUTCOMES, so turns on
        # the live chat path produced no confidence drips — the agent only
        # matured when chat ran through the streaming endpoint. Record the
        # outcome (success and failure) for every session-linked agent turn.
        if getattr(request, "agent_id", None):
            turn_success = bool(response.get("success", True))
            try:
                from core.database import get_db_session
                from core.agent_governance_service import AgentGovernanceService

                with get_db_session() as outcome_db:
                    await AgentGovernanceService(outcome_db).record_outcome(
                        request.agent_id,
                        success=turn_success,
                        task_summary=request.message[:200],
                    )
            except Exception as outcome_error:  # never block the chat response
                logger.warning(f"Failed to record chat outcome: {outcome_error}")

            if turn_success:
                try:
                    from core.episode_integration import trigger_episode_creation

                    trigger_episode_creation(
                        session_id=response.get("session_id") or session_id or request.session_id,
                        agent_id=request.agent_id,
                        title=request.message[:50],
                        user_id=active_user_id,
                    )
                except Exception as episode_error:  # never block the chat response
                    logger.warning(f"Failed to trigger episode creation: {episode_error}")

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

    # Phase 56 (positive/negative example learning): persist the full
    # (query, response) pair BEFORE the learning-router branch. The router
    # branch below only feeds model routing — and when it is disabled this
    # endpoint used to silently drop the thumbs entirely. Capture is
    # flag-gated (ATOM_EXCHANGE_MEMORY), dedupes, and fans the pair into the
    # teaching circuit (human_correction lessons / mastery exposure).
    capture_summary: Dict[str, Any] = {"captured": False, "reason": "not_attempted"}
    try:
        from core.exchange_example_service import capture_exchange

        capture_summary = await capture_exchange(
            message_id=request.message_id,
            feedback=feedback_val,
            comment=request.comment,
            session_id=request.session_id,
            model=request.model,
            provider=request.provider,
            user_id=str(current_user.id) if current_user else None,
        )
    except Exception as e:
        logger.warning(f"exchange example capture failed (non-fatal): {e}")

    learning_router = _get_learning_router()
    if learning_router is None:
        # Disabled — acknowledge but don't record routing feedback. (Capture
        # above still runs; its outcome is logged, not added to this response
        # — the response shape is pinned by API consumers and route tests.)
        logger.info(f"chat feedback routing disabled; exchange capture: {capture_summary}")
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


async def _office_draft(content: str, kind: str, title: str) -> Optional[tuple]:
    """Materialize an office draft (excel table / slide outline / document)
    as a real file under ATOM_OFFICE_DIR and return the typed canvas
    payload ``(canvas_type, content, title)``; None when the kind has no
    office form or creation fails (caller falls back to markdown doc).
    """
    import os
    import uuid as _uuid

    from core.chat_draft_classifier import extract_slide_outline, markdown_table_rows
    from core.office_service import OfficeService

    ext = {"table": ".xlsx", "slides": ".pptx", "doc": ".docx"}.get(kind)
    if not ext:
        return None

    slug = re.sub(r"[^A-Za-z0-9]+", "-", (title or "draft").strip())[:40].strip("-") or "draft"
    office_dir = os.getenv("ATOM_OFFICE_DIR", os.path.join("data", "office"))
    file_path = os.path.join(office_dir, f"chat-{slug}-{_uuid.uuid4().hex[:8]}{ext}")

    office = OfficeService()
    try:
        if kind == "table":
            rows = markdown_table_rows(content) or []
            res = office.excel.create_spreadsheet(file_path, rows)
        elif kind == "slides":
            res = {"success": True}
            for i, slide in enumerate(extract_slide_outline(content)):
                res = office.pptx.modify_slides(
                    file_path,
                    "add_slide",
                    {"title": slide["title"], "content": slide["content"]},
                )
                if not res.get("success"):
                    break
        else:  # doc
            res = {"success": True}
            for ln in content.splitlines():
                text = ln.strip()
                if not text:
                    continue
                if text.startswith("# "):
                    style = "Title"
                elif text.startswith("## "):
                    style = "Heading 1"
                elif text.startswith("### "):
                    style = "Heading 2"
                else:
                    style = "Normal"
                text = text.lstrip("#").strip()
                res = office.word.modify_document(file_path, "append", text, {"style": style})
                if not res.get("success"):
                    break
        if not res.get("success"):
            logger.warning(f"Office draft creation failed ({kind}): {res.get('error')}")
            return None
    except Exception as e:
        logger.warning(f"Office draft creation failed ({kind}): {e}")
        return None

    from core.office_sync_service import OFFICE_COMPONENT_MAP

    _, canvas_type = OFFICE_COMPONENT_MAP[ext]
    # Minimal binding payload — OfficeFileCanvas self-hydrates the
    # structured snapshot (sheets/text/slides) from the office read API.
    return canvas_type, {"office_file": file_path, "file_path": file_path, "format": ext.lstrip(".")}, title


@router.post("/to-canvas")
async def chat_draft_to_canvas(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: _Session = Depends(get_db),
):
    """Expand a chat draft into a co-editable canvas (training surface).

    Supervisor trains the hire by editing the draft ON the canvas; the
    original agent draft stays in the audit trail so the edit-diff is the
    learning signal.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON")

    content = body.get("content") or ""
    title = (body.get("title") or "Chat draft").strip()[:200]
    session_id = body.get("session_id")
    agent_id = body.get("agent_id")

    if not content.strip():
        raise HTTPException(status_code=400, detail="content is required")

    import uuid as _uuid
    from core.chat_draft_classifier import coerce_email_canvas, select_draft_message, strip_agent_signoff
    from core.models import Canvas, CanvasAudit

    # "Open latest draft" must open the DRAFT, not whatever the agent last
    # said: when the chat's recent assistant messages are supplied
    # newest-first, prefer the most recent one carrying a detectable
    # artifact (email / code / table / titled document).
    selected = select_draft_message(body.get("candidates") or [])
    if selected and selected["content"] != content:
        content = selected["content"]
        # Fallback title from the message head, minus code-fence markers.
        head = re.sub(r"^```[\w+-]*\s*\n?", "", selected["content"].lstrip())
        title = f"Draft — {head[:60]}"

    canvas_id = str(_uuid.uuid4())
    # Email drafts become typed email canvases ({to, subject, body}) so
    # /canvas/{id} renders the composer — To/Subject fields + Send button —
    # instead of a document with the Subject line buried in the body.
    # The owner can override the classifier from the UI: canvas_type forces
    # the app ("auto" keeps the heuristic). Ordered best-match in the UI:
    # document and email lead, specialized apps follow. Email keeps its
    # structured {to, subject, body} mapping; every other app takes the
    # draft as text content (no data lost — worst case it renders as text).
    CHAT_DRAFT_CANVAS_TYPES = {
        "document", "email", "markdown", "code", "sheet", "status_panel",
        "form", "line_chart", "bar_chart", "pie_chart", "terminal",
        "orchestration", "office_word", "office_excel", "office_pptx",
    }
    requested_type = (body.get("canvas_type") or "auto").strip().lower()
    office_fallback_warning: Optional[str] = None
    if requested_type and requested_type != "auto" and requested_type not in CHAT_DRAFT_CANVAS_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported canvas_type: {requested_type}",
        )
    if requested_type == "email":
        from core.chat_draft_classifier import extract_email_draft

        canvas_type = "email"
        canvas_content = extract_email_draft(content) or {
            "to": "",
            "subject": title,
            "body": content,
        }
    elif requested_type in ("office_word", "office_excel", "office_pptx"):
        # Office apps need a REAL generated file. Run the same materializer
        # the auto path uses, with the kind the user picked (word→doc,
        # excel→table, pptx→slides). A draft without the matching shape
        # falls back to a document canvas + a warning instead of a broken
        # office component.
        office_kind = {"office_word": "doc", "office_excel": "table",
                       "office_pptx": "slides"}[requested_type]
        office = await _office_draft(content, office_kind, title)
        if office:
            canvas_type, canvas_content, title = office
        else:
            canvas_type = "document"
            canvas_content = {"content": content}
            office_fallback_warning = (
                f"The draft has no {'table' if office_kind == 'table' else 'slide-outline' if office_kind == 'slides' else 'document'} "
                f"shape for a {requested_type} canvas — opened as a document instead."
            )
    elif requested_type != "auto":
        canvas_type = requested_type
        canvas_content = {"content": content}
    else:
        canvas_type, canvas_content = coerce_email_canvas("document", content)

    # Office drafts become REAL office canvases: excel tables → .xlsx,
    # slide outlines → .pptx, documents → .docx (office_* components bind
    # the file and self-hydrate their structured snapshot). Code drafts
    # open the code editor. Any file-creation failure falls back to the
    # markdown document path — the draft must still open. (Skipped when the
    # owner forced a type — their choice outranks the classifier.)
    if selected and requested_type == "auto" and canvas_type == "document":
        office = await _office_draft(content, selected["kind"], title)
        if office:
            canvas_type, canvas_content, title = office
        elif selected["kind"] == "code":
            canvas_type = "code"
            canvas_content = {"content": content}

    # A selected draft titles by its real artifact: the email's subject, a
    # document's leading heading — not raw markdown fragments.
    if selected:
        if canvas_type == "email":
            title = canvas_content.get("subject") or title
        elif selected["kind"] == "doc" and content.lstrip().startswith(("# ", "## ")):
            title = content.lstrip().splitlines()[0].lstrip("#").strip()[:200] or title
    # Agent-typed sign-offs: replaced by the user's real default when one
    # exists (their Outlook integration's, or a stored override); kept as a
    # starting point when the user has NO default — stripping would leave a
    # bare draft.
    if canvas_type == "email" and isinstance(canvas_content, dict):
        # Signature swap-in is enrichment — a preference-store hiccup must
        # never 500 the draft-open (observed: missing preferences table).
        try:
            from core.canvas_email_service import EmailCanvasService

            default_sig = await EmailCanvasService(db).get_signature(str(current_user.id))
            canvas_content["body"] = strip_agent_signoff(
                canvas_content.get("body") or "", default_sig.get("signature")
            )
        except Exception as sig_err:
            logger.debug(f"default signature resolution skipped: {sig_err}")
    canvas = Canvas(
        id=canvas_id,
        tenant_id=current_user.tenant_id or "default",
        workspace_id=current_user.workspaces[0].id if getattr(current_user, "workspaces", None) else "default",
        created_by=current_user.id,
        name=title,
        canvas_type=canvas_type,
        content=canvas_content,
        status="active",
    )
    db.add(canvas)
    db.commit()

    audit = CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=canvas.tenant_id,
        session_id=session_id,
        agent_id=agent_id,
        canvas_type=canvas_type,
        action_type="create",
        user_id=current_user.id,
        # Convention: canvas readers (tools/canvas_crud_tool.read_canvas) treat
        # the audit trail as the source of truth and extract details.content —
        # writing the body ONLY to the Canvas row made /canvas/{id} render an
        # empty page (details had just source/title).
        details_json={
            "source": "chat_to_canvas",
            "title": title,
            "content": canvas_content,
        },
    )
    db.add(audit)
    db.commit()

    result = {"success": True, "canvas_id": canvas_id, "url": f"/canvas/{canvas_id}"}
    # Which history message actually became the canvas — the UI toasts when
    # selection fell back to an earlier reply instead of the latest one.
    if selected and selected.get("message_id") is not None:
        result["selected_message_id"] = selected["message_id"]
    if office_fallback_warning:
        result["warning"] = office_fallback_warning
    return result
