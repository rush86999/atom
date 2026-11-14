# -*- coding: utf-8 -*-
"""
Agent Execution Service

Provides centralized agent chat execution with:
- Full governance integration
- WebSocket streaming support
- AgentExecution audit trail
- Episode creation for memory
"""

from core.asyncio_compat import get_event_loop, iscoroutinefunction
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.chat_context_manager import get_chat_context_manager
from core.chat_session_manager import get_chat_session_manager
from core.database import get_db_session, SessionLocal
from core.episode_integration import trigger_episode_creation
from core.lancedb_handler import get_chat_history_manager
from core.llm_service import LLMService
from core.models import AgentExecution, AgentInstallation
from core.marketplace_usage_tracker import MarketplaceUsageTracker
from core.personal_budget_service import personal_budget_service
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


#: The streaming provider ladder reports a terminal failure on the token
#: stream as one final text frame: ``stream_completion`` yields this error
#: envelope instead of raising once every provider/route has failed
#: (core/llm/byok_handler.py — "All LLM providers failed" and the budget
#: authorization refusal). The OpenAI gateway already treats the same lead-in
#: as a 502 rather than assistant text (api/openai_gateway_routes.py). There
#: is no richer structured channel on the token stream, so this envelope IS
#: the terminal result: it must never be accumulated as a reply, persisted as
#: assistant content, or reported as ``success``.
_PROVIDER_TERMINAL_ERROR_PREFIX = "\n\n[Error:"


def _is_provider_terminal_error_frame(frame: str) -> bool:
    """True when ``frame`` is the provider ladder's terminal failure envelope.

    Deliberately narrow — only the exact lead-in the producer documents. A
    broad "mentions providers / API keys" heuristic would reject genuine
    answers that quote logs or configuration advice.
    """
    return bool(frame) and frame.startswith(_PROVIDER_TERMINAL_ERROR_PREFIX)


async def _notify_stream_failure(
    *,
    user_id: str,
    message_id: str,
    execution_id: Optional[str],
    partial_content: str,
    tokens_count: int,
) -> None:
    """Emit the structured terminal failure to streaming clients.

    ``streaming:error`` is the existing structured failure status (the frame
    ``core/atom_agent_endpoints.py`` already sends). ``streaming:complete``
    follows because legacy panels — including the web app's ``useTurnStream``
    hook — clear their in-flight bubble on completion only. Its content is the
    PARTIAL answer that was really delivered (empty when the provider failed
    before producing any), never the error envelope.
    """
    channel = f"user:{user_id}"

    async def _send(frame: Dict[str, Any]) -> None:
        try:
            await ws_manager.broadcast(channel, frame)
        except Exception as notify_error:  # noqa: BLE001 — never mask the failure
            logger.warning(f"Failed to notify stream failure: {notify_error}")

    await _send({
        "type": ws_manager.STREAMING_ERROR,
        "id": message_id,
        "error": "Agent chat execution failed",
        "execution_id": execution_id,
        "partial": bool(partial_content),
    })
    await _send({
        "type": ws_manager.STREAMING_COMPLETE,
        "id": message_id,
        "content": partial_content or "",
        "complete": True,
        "metadata": {
            "execution_id": execution_id,
            "tokens_total": tokens_count,
            "error": True,
        },
    })


def _record_failed_execution(
    *,
    db_session: Optional[Session],
    agent_execution: Optional[AgentExecution],
    execution_id: Optional[str],
    agent: Any,
    governance_enabled: bool,
    start_time: Optional[datetime],
) -> None:
    """Finalize an AgentExecution row (and marketplace usage) as failed.

    Uses the still-open governance session when one exists; otherwise opens a
    short-lived session and re-fetches the row by id — the pre-stream session
    is intentionally closed before streaming starts, so both windows occur.
    The persisted error message is GENERIC: raw exception/sentinel text never
    reaches the audit trail.
    """
    if not (execution_id and governance_enabled):
        return

    session = db_session
    owned_session = False
    if session is None:
        try:
            session = SessionLocal()
            owned_session = True
        except Exception:
            session = None
    if session is None:
        return

    try:
        execution = agent_execution
        if execution is None:
            execution = session.query(AgentExecution).filter(
                AgentExecution.id == execution_id
            ).first()
        if execution:
            execution.status = "failed"
            execution.error_message = "Agent chat execution failed"
            execution.completed_at = datetime.now()
            session.commit()

        # Marketplace Tracking (Failure)
        if agent is not None and getattr(agent, "type", None) == "marketplace":
            try:
                installation = session.query(AgentInstallation).filter(
                    AgentInstallation.instantiated_agent_id == agent.id
                ).first()
                if installation:
                    _start = start_time or datetime.now()
                    duration_ms = (
                        datetime.now() - _start
                    ).total_seconds() * 1000
                    MarketplaceUsageTracker.track_usage(
                        item_type="agent",
                        item_id=installation.template_id,
                        success=False,
                        duration_ms=duration_ms,
                    )
            except Exception as mt_error:
                logger.error(f"Marketplace failure tracking failed: {mt_error}")

    except Exception as update_error:
        logger.error(f"Failed to update failed execution record: {update_error}")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        if owned_session:
            try:
                session.close()
            except Exception:
                pass


class ChatMessage:
    """Simple chat message model"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


async def execute_agent_chat(
    agent_id: str,
    message: str,
    user_id: str,
    session_id: Optional[str] = None,
    workspace_id: str = "default",
    tenant_id: Optional[str] = None,
    conversation_history: List[Dict[str, str]] = None,
    stream: bool = False
) -> Dict[str, Any]:
    """
    Execute agent chat with full governance and streaming support.

    This is the centralized service for executing agent chat requests,
    used by menubar, mobile, and web platforms.

    Args:
        agent_id: The ID of the agent to execute
        message: User's message to the agent
        user_id: User ID making the request
        session_id: Optional session ID for conversation continuity
        workspace_id: Workspace ID (default for single-tenant)
        tenant_id: Authenticated tenant ID. Kept separate from workspace_id:
            a tenant id is never used as a workspace id when the LLM handler
            resolves provider scope.
        conversation_history: Optional conversation history for context
        stream: Whether to stream response via WebSocket

    Returns:
        Dictionary containing:
        - success: bool
        - execution_id: str
        - response: str (full response if not streaming)
        - agent_id: str
        - agent_name: str
        - message_id: str (for WebSocket tracking)
        - error: str (if failed)

        A terminal provider failure delivered on the token stream is a
        failure: ``success`` is False, ``response`` is None, and the error
        envelope is never persisted as assistant content (genuine partial
        output that arrived before the terminal frame is still delivered).

    Example:
        result = await execute_agent_chat(
            agent_id="agent_123",
            message="Hello, how can you help me?",
            user_id="user_456"
        )
        print(result["response"])
    """
    # Feature flags
    governance_enabled = os.getenv("STREAMING_GOVERNANCE_ENABLED", "true").lower() == "true"
    emergency_bypass = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

    agent = None
    agent_execution = None
    resolution_context = None
    governance_check = None
    db_session = None
    # Carries the execution id forward after the governance session is closed
    # pre-stream, so the post-stream/failure finalizers can re-fetch the row.
    _execution_id_for_finalize = None
    # Initialized before the try so the failure handler and streamed-terminal
    # branch can always report/notify on the same turn identity.
    message_id: Optional[str] = None
    accumulated_content = ""
    tokens_count = 0
    start_time: Optional[datetime] = None

    try:
        # ============================================
        # GOVERNANCE: Agent Resolution & Validation
        # ============================================
        if governance_enabled and not emergency_bypass:
            db_session = SessionLocal()
            resolver = AgentContextResolver(db_session)
            # Authenticated scope, not the shared default: a real workspace's
            # agent must pass ITS OWN governance check. The default-scoped
            # service reported "Agent not found" for every non-default
            # workspace after the route had already authorized the agent.
            governance = AgentGovernanceService(
                db_session, workspace_id=workspace_id, tenant_id=tenant_id)

            # Resolve agent for this request
            agent, resolution_context = await resolver.resolve_agent_for_request(
                user_id=user_id,
                session_id=session_id,
                requested_agent_id=agent_id,
                action_type="chat"
            )

            if not agent:
                logger.warning(f"Agent resolution failed for agent_id={agent_id}, using system default")
                # Fall through to system default behavior

            # Perform governance check
            if agent:
                governance_check = governance.can_perform_action(
                    agent_id=agent.id,
                    action_type="chat",
                    require_approval=False
                )

                if not governance_check.get("allowed", False):
                    reason = governance_check.get("reason", "Governance policy denied this action")
                    logger.warning(f"Governance blocked agent chat: {reason}")
                    return {
                        "success": False,
                        "error": f"Action blocked by governance: {reason}",
                        "agent_id": agent_id,
                        "execution_id": None
                    }

        # ============================================
        # BUDGET: Check Budget (Warning Only, No Blocking)
        # ============================================
        # Check budget before execution (warning only, does NOT block)
        # Personal use = user's responsibility, so we only log warnings
        try:
            if personal_budget_service.is_budget_exceeded():
                logger.warning(
                    f"Budget exceeded for agent execution (agent_id={agent_id}). "
                    f"Continuing anyway (personal use = user responsibility)."
                )
                # Send alert at 100% threshold
                personal_budget_service.send_budget_alert(100.0)
            else:
                # Send alerts at 80% and 90% thresholds
                personal_budget_service.send_budget_alert(80.0)
                personal_budget_service.send_budget_alert(90.0)
        except Exception as budget_error:
            logger.error(f"Budget check failed (continuing anyway): {budget_error}")
            # Don't block execution on budget check failures

        # ============================================
        # EXECUTION: Create AgentExecution Record
        # ============================================
        execution_id = str(uuid.uuid4())

        if agent and governance_enabled:
            try:
                # Map to ACTUAL AgentExecution columns. Several fields used here
                # previously (agent_name, agent_category, user_id, session_id,
                # action_type, action_complexity, input_data, metadata) are NOT
                # columns on the model — SQLAlchemy silently dropped them, so the
                # audit trail lost agent/user/action/duration/output. Fold them
                # into input_summary + metadata_json (the extensible JSON column).
                agent_execution = AgentExecution(
                    id=execution_id,
                    agent_id=agent.id,
                    workspace_id=workspace_id,
                    status="running",
                    triggered_by="websocket",
                    input_summary=(message or "")[:500],
                    metadata_json={
                        "source": "menubar",
                        "agent_name": agent.name,
                        "agent_category": agent.category,
                        "user_id": user_id,
                        "session_id": session_id,
                        "action_type": "chat",
                        "action_complexity": 1,
                        "governance_check": governance_check,
                        "resolution_context": resolution_context,
                    },
                )

                if db_session:
                    db_session.add(agent_execution)
                    db_session.commit()
                    db_session.refresh(agent_execution)

            except Exception as exec_error:
                logger.error(f"Failed to create AgentExecution record: {exec_error}")
                # Continue anyway - don't block execution on audit failure

        # ============================================
        # LLM: Initialize LLM Service
        # ============================================
        # Pass db=None so LLMService/BYOKHandler do NOT share the governance
        # session. Holding one DB connection across the full streaming call
        # (which can run for many seconds) pins a pool slot per concurrent chat
        # and exhausts the pool (~20 connections) under modest load. The handler
        # opens its own sessions as needed. The governance session is closed
        # below before streaming begins.
        #
        # Scope is the AUTHENTICATED pair, passed as two identifiers. The
        # previous tenant_id=workspace_id collapsed them: a real workspace id
        # was treated as a tenant and could not resolve its own workspace, so
        # the provider scope was refused (or silently defaulted).
        llm_service = LLMService(
            workspace_id=workspace_id, tenant_id=tenant_id, db=None)

        # Prepare messages for LLM
        messages = []

        # Add system message
        agent_name = agent.name if agent else "ATOM"
        agent_desc = agent.description if agent else "AI Assistant"

        messages.append({
            "role": "system",
            "content": f"""You are {agent_name}, an intelligent AI assistant.

{agent_desc}

Provide helpful, concise responses. Be direct and practical."""
        })

        # Add conversation history
        if conversation_history:
            for hist_msg in conversation_history:
                messages.append({
                    "role": hist_msg.get("role", "user"),
                    "content": hist_msg.get("content", "")
                })

        # Add current message
        messages.append({
            "role": "user",
            "content": message
        })

        # Get optimal provider for this request
        complexity = llm_service.analyze_query_complexity(message, task_type="chat")
        provider_id, model = llm_service.get_optimal_provider(
            complexity,
            task_type="chat",
            prefer_cost=True,
            tenant_plan="free",
            is_managed_service=False,
            requires_tools=False
        )

        logger.info(f"Executing agent chat with {provider_id}/{model}" +
                   (f" (agent: {agent.name})" if agent else ""))

        # Create unique message ID for WebSocket tracking
        message_id = str(uuid.uuid4())

        # If streaming is requested, send initial WebSocket message
        if stream:
            user_channel = f"user:{user_id}"
            await ws_manager.broadcast(user_channel, {
                "type": "streaming:start",
                "id": message_id,
                "model": "auto",
                "agent_id": agent.id if agent else None,
                "agent_name": agent.name if agent else None,
                "execution_id": execution_id
            })

        # Execute chat (streaming or non-streaming)
        accumulated_content = ""
        tokens_count = 0
        start_time = datetime.now()

        stream_kwargs = {
            "messages": messages,
            "model": "auto",
            "temperature": 0.7,
            "max_tokens": 2000,
            "agent_id": agent.id if agent else None,
            # Exact turn attribution: the durable usage ledger row for every
            # physical provider attempt carries this AgentExecution id. Only
            # pass it when a row was actually created (governance+agent), never
            # a dangling id when the audit insert was skipped.
            "execution_id": agent_execution.id if agent_execution else None,
            # Authenticated scope, kept as two identifiers. The handler uses
            # these to select the caller's own provider/key configuration.
            "workspace_id": workspace_id,
            "tenant_id": tenant_id,
        }

        # Close the governance DB session BEFORE streaming. The session was
        # opened for agent resolution + the execution-record insert (all done
        # by now); holding it across the streaming call pinned a pool slot for
        # the whole stream wall-clock. The post-stream block re-opens a fresh
        # short-lived session to finalize the execution row (re-fetched by id).
        _execution_id_for_finalize = agent_execution.id if agent_execution else None
        if db_session is not None:
            try:
                db_session.close()
            except Exception:
                pass
            db_session = None
            # Detach so the post-stream block knows to re-fetch; keep the id.
            agent_execution = None

        async def _emit_visible(part: str) -> None:
            """Accumulate + stream one VISIBLE answer fragment."""
            nonlocal accumulated_content, tokens_count
            accumulated_content += part
            # Count TOKENS, not stream chunks. stream_completion yields
            # arbitrary text fragments (often whole words/sentences), so the old
            # `tokens_count += 1` undercounted real tokens by ~3-10x and
            # corrupted the spend recorded against the personal budget. Use the
            # codebase's standard ~4-chars/token estimate.
            tokens_count += max(1, len(part) // 4)

            # Broadcast token via WebSocket if streaming enabled
            if stream:
                user_channel = f"user:{user_id}"
                await ws_manager.broadcast(user_channel, {
                    "type": ws_manager.STREAMING_UPDATE,
                    "id": message_id,
                    "delta": part,
                    "complete": False,
                    "metadata": {
                        # Report the token ESTIMATE (tokens_count), not the raw
                        # char count — the key is named tokens_so_far.
                        "tokens_so_far": tokens_count,
                        "execution_id": execution_id
                    }
                })

        # The provider ladder signals a terminal failure by YIELDING its error
        # envelope as the last frame (it never raises once routing is done).
        # Hold the first frame(s) only while they are still a prefix of that
        # envelope: a real answer streams immediately, an exhausted-provider
        # turn never becomes visible/persisted content, and a real answer that
        # merely QUOTES the envelope later in the turn is left untouched.
        pending_frame = ""
        envelope_candidate = True
        provider_terminal_failure = False

        async for token in llm_service.stream_completion(**stream_kwargs):
            if envelope_candidate:
                candidate = pending_frame + token
                if _is_provider_terminal_error_frame(candidate):
                    provider_terminal_failure = True
                    break
                if _PROVIDER_TERMINAL_ERROR_PREFIX.startswith(candidate):
                    # Still a possible envelope lead-in ("\n", "\n\n[E"...):
                    # hold it rather than stream error text as a reply.
                    pending_frame = candidate
                    continue
                # Diverged from the envelope: real output. Flush it and stop
                # buffering for the rest of the turn.
                token = candidate
                pending_frame = ""
                envelope_candidate = False

            await _emit_visible(token)

        if pending_frame and not provider_terminal_failure:
            # The stream ended on an incomplete envelope lead-in (e.g. the
            # answer really was "\n"): deliver it instead of dropping it.
            await _emit_visible(pending_frame)
            pending_frame = ""

        if provider_terminal_failure:
            # A streamed terminal provider error is a FAILED turn. It must not
            # be accumulated, persisted to chat history, or reported as a
            # successful reply — the error text is not assistant output.
            logger.error(
                "Provider stream reported a terminal failure for "
                "agent_id=%s (execution_id=%s); not persisting it as "
                "assistant content", agent_id, execution_id)
            if stream:
                await _notify_stream_failure(
                    user_id=user_id,
                    message_id=message_id,
                    execution_id=_execution_id_for_finalize or execution_id,
                    partial_content=accumulated_content,
                    tokens_count=tokens_count,
                )
            _record_failed_execution(
                db_session=db_session,
                agent_execution=agent_execution,
                execution_id=_execution_id_for_finalize,
                agent=agent,
                governance_enabled=governance_enabled,
                start_time=start_time,
            )
            return {
                "success": False,
                "error": "Agent chat execution failed",
                "response": None,
                "agent_id": agent.id if agent else agent_id,
                "execution_id": execution_id,
                "message_id": message_id,
                "session_id": session_id,
            }

        # Send completion message if streaming
        if stream:
            user_channel = f"user:{user_id}"
            await ws_manager.broadcast(user_channel, {
                "type": ws_manager.STREAMING_COMPLETE,
                "id": message_id,
                "content": accumulated_content,
                "complete": True,
                "metadata": {
                    "execution_id": execution_id,
                    "tokens_total": tokens_count
                }
            })

        # ============================================
        # PERSISTENCE: Save to Chat History
        # ============================================
        try:
            chat_history = get_chat_history_manager(workspace_id)
            session_manager = get_chat_session_manager(workspace_id)

            # Create or use session
            if not session_id:
                session_id = session_manager.create_session(user_id)

            # Save messages
            chat_history.add_message(session_id, "user", message)
            chat_history.add_message(session_id, "assistant", accumulated_content)

        except Exception as persist_error:
            logger.error(f"Failed to save chat history: {persist_error}")
            # Don't fail the request on persistence errors

        # ============================================
        # GOVERNANCE: Update Execution Record
        # ============================================
        # The governance session was closed before streaming (to avoid pinning a
        # pool slot across the stream), so open a FRESH short-lived session here
        # and re-fetch the execution row by id. agent_execution is detached/None
        # at this point; _execution_id_for_finalize carries the id forward.
        if _execution_id_for_finalize and governance_enabled:
            end_time = datetime.now()
            duration_seconds = (end_time - start_time).total_seconds()
            _fin_session = SessionLocal()
            try:
                execution = _fin_session.query(AgentExecution).filter(
                    AgentExecution.id == _execution_id_for_finalize
                ).first()
                if execution:
                    execution.status = "completed"
                    # Use REAL columns (result_summary, duration_seconds,
                    # completed_at). The old output_data/duration_ms/end_time
                    # writes were no-ops (not model columns).
                    execution.result_summary = (accumulated_content or "")[:500]
                    execution.duration_seconds = duration_seconds
                    execution.completed_at = end_time
                    # Merge output details into the extensible metadata_json.
                    _meta = execution.metadata_json or {}
                    if not isinstance(_meta, dict):
                        _meta = {}
                    _meta["output"] = {
                        "response": (accumulated_content or "")[:500],
                        "tokens": tokens_count,
                        "model": "auto",
                    }
                    execution.metadata_json = _meta
                    _fin_session.commit()

                # Marketplace Tracking
                if agent and agent.type == "marketplace":
                    try:
                        installation = _fin_session.query(AgentInstallation).filter(
                            AgentInstallation.instantiated_agent_id == agent.id
                        ).first()
                        if installation:
                            MarketplaceUsageTracker.track_usage(
                                item_type="agent",
                                item_id=installation.template_id,
                                success=True,
                                duration_ms=duration_seconds * 1000
                            )
                    except Exception as mt_error:
                        logger.error(f"Marketplace tracking failed: {mt_error}")

            except Exception as update_error:
                logger.error(f"Failed to update AgentExecution record: {update_error}")
                try:
                    _fin_session.rollback()
                except Exception:
                    pass
            finally:
                try:
                    _fin_session.close()
                except Exception:
                    pass

        # Trigger episode creation for memory (sync fire-and-forget: the
        # trigger schedules on the running loop or falls back to asyncio.run)
        try:
            trigger_episode_creation(
                user_id=user_id,
                agent_id=agent.id if agent else None,
                session_id=session_id,
                workspace_id=workspace_id
            )
        except Exception as episode_error:
            logger.warning(f"Failed to trigger episode creation: {episode_error}")

        # ============================================
        # BUDGET: Track Spend After Execution
        # ============================================
        # Record spend for budget forecasting and tracking
        try:
            # Estimate cost based on tokens (rough estimation)
            # ACU cost: ~$0.0001 per token, API cost varies by provider
            estimated_cost = (tokens_count * 0.0001) + 0.001  # Base API call cost
            personal_budget_service.record_spend(estimated_cost, execution_id)
        except Exception as budget_error:
            logger.error(f"Failed to record spend (non-critical): {budget_error}")
            # Don't fail execution on budget tracking errors

        # Return success
        return {
            "success": True,
            "execution_id": execution_id,
            "response": accumulated_content,
            "agent_id": agent.id if agent else agent_id,
            "agent_name": agent.name if agent else "System",
            "message_id": message_id,
            "session_id": session_id,
            "tokens": tokens_count,
            "model": "auto"
        }

    except Exception as e:
        logger.error(f"Agent chat execution failed: {e}", exc_info=True)

        # Update execution record as failed. Two windows: before the pre-stream
        # session close (db_session + agent_execution still valid) and after
        # (both None — re-fetch by id in a fresh session).
        _record_failed_execution(
            db_session=db_session,
            agent_execution=agent_execution,
            execution_id=_execution_id_for_finalize,
            agent=agent,
            governance_enabled=governance_enabled,
            start_time=start_time,
        )

        # A streamed turn must terminate its client-side view too — otherwise
        # the browser keeps a spinner forever and only sees a dropped socket.
        if stream and message_id:
            await _notify_stream_failure(
                user_id=user_id,
                message_id=message_id,
                execution_id=_execution_id_for_finalize,
                partial_content=accumulated_content,
                tokens_count=tokens_count,
            )

        return {
            "success": False,
            # GENERIC error message — the raw exception (str(e)) may carry
            # internal paths/SQL/token details and must stay server-side
            # (it is logged above with exc_info=True).
            "error": "Agent chat execution failed",
            "agent_id": agent_id,
            "execution_id": execution_id if agent_execution else None
        }

    finally:
        # Clean up database session
        if db_session:
            try:
                db_session.close()
            except Exception:
                pass


def execute_agent_chat_sync(
    agent_id: str,
    message: str,
    user_id: str,
    session_id: Optional[str] = None,
    workspace_id: str = "default",
    tenant_id: Optional[str] = None,
    conversation_history: List[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for execute_agent_chat.

    Use this in non-async contexts. This runs the async function in an event loop.
    Note: WebSocket streaming is disabled in sync mode.

    Args:
        Same as execute_agent_chat

    Returns:
        Same as execute_agent_chat (but without streaming support)
    """
    import asyncio

    try:
        loop = get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        execute_agent_chat(
            agent_id=agent_id,
            message=message,
            user_id=user_id,
            session_id=session_id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            conversation_history=conversation_history,
            stream=False  # Disable streaming in sync mode
        )
    )
