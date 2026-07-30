# -*- coding: utf-8 -*-
"""
Agent Execution Service

Provides centralized agent chat execution with:
- Full governance integration
- WebSocket streaming support
- AgentExecution audit trail
- Episode creation for memory
"""

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

    try:
        # ============================================
        # GOVERNANCE: Agent Resolution & Validation
        # ============================================
        if governance_enabled and not emergency_bypass:
            db_session = SessionLocal()
            resolver = AgentContextResolver(db_session)
            governance = AgentGovernanceService(db_session)

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
        llm_service = LLMService(tenant_id=workspace_id, db=None)

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
            "agent_id": agent.id if agent else None
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

        # Stream response
        # Stream response via LLMService
        async for token in llm_service.stream_completion(**stream_kwargs):
            accumulated_content += token
            # Count TOKENS, not stream chunks. stream_completion yields
            # arbitrary text fragments (often whole words/sentences), so the old
            # `tokens_count += 1` undercounted real tokens by ~3-10x and
            # corrupted the spend recorded against the personal budget. Use the
            # codebase's standard ~4-chars/token estimate.
            tokens_count += max(1, len(token) // 4)

            # Broadcast token via WebSocket if streaming enabled
            if stream:
                user_channel = f"user:{user_id}"
                await ws_manager.broadcast(user_channel, {
                    "type": ws_manager.STREAMING_UPDATE,
                    "id": message_id,
                    "delta": token,
                    "complete": False,
                    "metadata": {
                        # Report the token ESTIMATE (tokens_count), not the raw
                        # char count — the key is named tokens_so_far.
                        "tokens_so_far": tokens_count,
                        "execution_id": execution_id
                    }
                })

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

        # Trigger episode creation for memory
        try:
            await trigger_episode_creation(
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
        _fail_session = db_session  # reuse if still open
        _fail_session_owned = False
        if _fail_session is None and _execution_id_for_finalize and governance_enabled:
            try:
                _fail_session = SessionLocal()
                _fail_session_owned = True
            except Exception:
                _fail_session = None
        if _execution_id_for_finalize and governance_enabled and _fail_session is not None:
            try:
                # Re-fetch if the original object is detached/None.
                execution = agent_execution
                if execution is None:
                    execution = _fail_session.query(AgentExecution).filter(
                        AgentExecution.id == _execution_id_for_finalize
                    ).first()
                if execution:
                    execution.status = "failed"
                    execution.error_message = str(e)[:500]
                    execution.completed_at = datetime.now()
                    _fail_session.commit()

                # Marketplace Tracking (Failure)
                if agent and agent.type == "marketplace":
                    try:
                        installation = _fail_session.query(AgentInstallation).filter(
                            AgentInstallation.instantiated_agent_id == agent.id
                        ).first()
                        if installation:
                            _start = start_time if "start_time" in locals() else datetime.now()
                            duration_ms = (datetime.now() - _start).total_seconds() * 1000
                            MarketplaceUsageTracker.track_usage(
                                item_type="agent",
                                item_id=installation.template_id,
                                success=False,
                                duration_ms=duration_ms
                            )
                    except Exception as mt_error:
                        logger.error(f"Marketplace failure tracking failed: {mt_error}")

            except Exception as update_error:
                logger.error(f"Failed to update failed execution record: {update_error}")
                try:
                    _fail_session.rollback()
                except Exception:
                    pass
            finally:
                if _fail_session_owned:
                    try:
                        _fail_session.close()
                    except Exception:
                        pass

        return {
            "success": False,
            "error": str(e),
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
        loop = asyncio.get_event_loop()
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
            conversation_history=conversation_history,
            stream=False  # Disable streaming in sync mode
        )
    )
