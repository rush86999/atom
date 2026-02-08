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
from core.database import get_db_session
from core.episode_integration import trigger_episode_creation
from core.lancedb_handler import get_chat_history_manager
from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.models import AgentExecution
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

    try:
        # ============================================
        # GOVERNANCE: Agent Resolution & Validation
        # ============================================
        if governance_enabled and not emergency_bypass:
            db_session = get_db_session()
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
                    action_complexity=1  # Chat is low complexity
                )

                if not governance_check.get("proceed", False):
                    reason = governance_check.get("reason", "Governance policy denied this action")
                    logger.warning(f"Governance blocked agent chat: {reason}")
                    return {
                        "success": False,
                        "error": f"Action blocked by governance: {reason}",
                        "agent_id": agent_id,
                        "execution_id": None
                    }

        # ============================================
        # EXECUTION: Create AgentExecution Record
        # ============================================
        execution_id = str(uuid.uuid4())

        if agent and governance_enabled:
            try:
                agent_execution = AgentExecution(
                    id=execution_id,
                    agent_id=agent.id,
                    agent_name=agent.name,
                    agent_category=agent.category,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    session_id=session_id,
                    action_type="chat",
                    action_complexity=1,
                    status="running",
                    input_data={"message": message},
                    metadata={
                        "source": "menubar",
                        "governance_check": governance_check,
                        "resolution_context": resolution_context
                    }
                )

                if db_session:
                    db_session.add(agent_execution)
                    db_session.commit()
                    db_session.refresh(agent_execution)

            except Exception as exec_error:
                logger.error(f"Failed to create AgentExecution record: {exec_error}")
                # Continue anyway - don't block execution on audit failure

        # ============================================
        # LLM: Initialize BYOK Handler
        # ============================================
        byok_handler = BYOKHandler(workspace_id=workspace_id, provider_id="auto")

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
        complexity = byok_handler.analyze_query_complexity(message, task_type="chat")
        provider_id, model = byok_handler.get_optimal_provider(
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
                "model": model,
                "provider": provider_id,
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
            "model": model,
            "provider_id": provider_id,
            "temperature": 0.7,
            "max_tokens": 2000
        }

        # Add agent context for governance tracking
        if agent and governance_enabled:
            stream_kwargs["agent_id"] = agent.id

        # Stream response
        async for token in byok_handler.stream_completion(**stream_kwargs):
            accumulated_content += token
            tokens_count += 1

            # Broadcast token via WebSocket if streaming enabled
            if stream:
                user_channel = f"user:{user_id}"
                await ws_manager.broadcast(user_channel, {
                    "type": ws_manager.STREAMING_UPDATE,
                    "id": message_id,
                    "delta": token,
                    "complete": False,
                    "metadata": {
                        "model": model,
                        "tokens_so_far": len(accumulated_content),
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
        if agent_execution and governance_enabled:
            try:
                end_time = datetime.now()
                duration_ms = (end_time - start_time).total_seconds() * 1000

                agent_execution.status = "completed"
                agent_execution.output_data = {
                    "response": accumulated_content,
                    "tokens": tokens_count,
                    "provider": provider_id,
                    "model": model
                }
                agent_execution.duration_ms = duration_ms
                agent_execution.end_time = end_time

                if db_session:
                    db_session.commit()

            except Exception as update_error:
                logger.error(f"Failed to update AgentExecution record: {update_error}")

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
            "provider": provider_id,
            "model": model
        }

    except Exception as e:
        logger.error(f"Agent chat execution failed: {e}", exc_info=True)

        # Update execution record as failed
        if agent_execution and governance_enabled and db_session:
            try:
                agent_execution.status = "failed"
                agent_execution.error_message = str(e)
                agent_execution.end_time = datetime.now()
                db_session.commit()
            except Exception as update_error:
                logger.error(f"Failed to update failed execution record: {update_error}")

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
