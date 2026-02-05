"""
Mobile Agent API Routes

Mobile-optimized endpoints for agent interactions:
- Mobile agent list with filtering
- Mobile agent chat with streaming
- Episode context integration
- Canvas presentation support
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.agent_context_resolver import AgentContextResolver
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService, RetrievalMode
from core.llm.byok_handler import BYOKHandler
from core.models import AgentRegistry, AgentFeedback, AgentExecution, User
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/agents/mobile", tags=["Mobile-Agents"])


# ============================================================================
# Request/Response Models
# ============================================================================

class MobileAgentListItem(BaseModel):
    agent_id: str
    name: str
    description: str
    maturity_level: str  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    category: str
    capabilities: List[str]
    status: str  # active, paused, deprecated
    is_available: bool
    last_active: Optional[str] = None


class MobileAgentListResponse(BaseModel):
    agents: List[MobileAgentListItem]
    total: int
    filtered: int


class MobileChatRequest(BaseModel):
    message: str
    include_episode_context: bool = True
    episode_retrieval_mode: str = "contextual"  # temporal, semantic, sequential, contextual
    max_episodes: int = 3


class MobileChatResponse(BaseModel):
    message_id: str
    agent_id: str
    content: str
    is_streaming: bool
    governance: Optional[Dict[str, Any]] = None
    episode_context: Optional[List[Dict[str, Any]]] = None


class EpisodeContextItem(BaseModel):
    episode_id: str
    title: str
    summary: str
    relevance_score: float
    created_at: str


class StreamingChunk(BaseModel):
    chunk_id: str
    content: str
    is_complete: bool = False
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# Mobile Agent Routes
# ============================================================================

@router.get("/list", response_model=MobileAgentListResponse)
async def list_mobile_agents(
    category: Optional[str] = None,
    status: Optional[str] = None,
    capability: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get mobile-optimized list of agents with filtering.

    Args:
        category: Filter by category (e.g., 'automation', 'analytics')
        status: Filter by maturity (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        capability: Filter by capability (e.g., 'web_automation', 'data_analysis')
        search: Search in name/description
        limit: Max items to return
        offset: Pagination offset

    Returns:
        Mobile-optimized agent list with metadata
    """
    try:
        governance_service = AgentGovernanceService(db)

        # Get agents with governance info
        # Filter out paused/deprecated agents
        active_statuses = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']
        agents_query = db.query(AgentRegistry).filter(
            AgentRegistry.status.in_(active_statuses)
        )

        # Apply filters
        if category:
            agents_query = agents_query.filter(AgentRegistry.category == category)

        if status:
            agents_query = agents_query.filter(
                AgentRegistry.status == status
            )

        if search:
            search_pattern = f"%{search}%"
            agents_query = agents_query.filter(
                (AgentRegistry.name.ilike(search_pattern)) |
                (AgentRegistry.description.ilike(search_pattern))
            )

        # Get total count
        total = agents_query.count()

        # Apply pagination
        agents = agents_query.offset(offset).limit(limit).all()

        # Filter by capability and maturity after fetching
        filtered_agents = []
        for agent in agents:
            # Check capability filter
            if capability:
                agent_capabilities = agent.configuration.get('capabilities', [])
                if capability not in agent_capabilities:
                    continue

            # Get governance info
            governance_info = governance_service.get_agent_governance_info(agent.id)

            # Determine availability based on maturity and current state
            is_available = (
                agent.status in ['SUPERVISED', 'AUTONOMOUS'] and
                governance_info.get('can_execute', False)
            )

            filtered_agents.append(MobileAgentListItem(
                agent_id=agent.id,
                name=agent.name,
                description=agent.description or "",
                maturity_level=agent.status,
                category=agent.category,
                capabilities=agent.configuration.get('capabilities', []),
                status=agent.status,
                is_available=is_available,
                last_active=agent.updated_at.isoformat() if agent.updated_at else None
            ))

        return MobileAgentListResponse(
            agents=filtered_agents,
            total=total,
            filtered=len(filtered_agents)
        )

    except Exception as e:
        logger.error(f"Failed to list mobile agents: {e}")
        raise router.internal_error(f"Failed to list agents: {str(e)}")


@router.post("/{agent_id}/chat", response_model=MobileChatResponse)
async def mobile_agent_chat(
    agent_id: str,
    request: MobileChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send message to agent and receive response (mobile-optimized).

    Supports streaming responses and episode context integration.

    Args:
        agent_id: Agent ID
        request: Chat request with message and options

    Returns:
        Agent response with optional episode context
    """
    agent_execution = None
    start_time = datetime.utcnow()

    try:
        # Verify agent exists and is accessible
        active_statuses = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.status.in_(active_statuses)
        ).first()

        if not agent:
            raise router.not_found_error("Agent", agent_id)

        # Check governance
        governance_service = AgentGovernanceService(db)
        governance_info = governance_service.get_agent_governance_info(agent_id)

        if not governance_info.get('can_execute', False):
            raise router.forbidden_error(
                f"Agent maturity level ({governance_info.get('status')}) "
                "does not allow direct execution"
            )

        # Generate message ID
        message_id = str(uuid.uuid4())

        # Create AgentExecution record for audit trail
        agent_execution = AgentExecution(
            agent_id=agent.id,
            workspace_id="default",
            status="running",
            input_summary=f"Mobile chat: {request.message[:200]}...",
            triggered_by="mobile_api"
        )
        db.add(agent_execution)
        db.commit()
        db.refresh(agent_execution)

        # Retrieve episode context if requested
        episode_context = None
        if request.include_episode_context:
            try:
                retrieval_service = EpisodeRetrievalService(db)
                mode = RetrievalMode[request.episode_retrieval_mode.upper()]

                episodes = retrieval_service.retrieve_episodes(
                    query_text=request.message,
                    user_id=str(current_user.id),
                    agent_id=agent_id,
                    mode=mode,
                    limit=request.max_episodes
                )

                episode_context = [
                    EpisodeContextItem(
                        episode_id=ep.episode_id,
                        title=ep.title or f"Episode {ep.episode_id[:8]}",
                        summary=ep.summary[:200] if ep.summary else "",
                        relevance_score=ep.relevance_score,
                        created_at=ep.created_at.isoformat()
                    )
                    for ep in episodes
                ]
            except Exception as e:
                logger.warning(f"Failed to retrieve episode context: {e}")
                # Continue without episode context

        # Prepare governance metadata
        governance_metadata = {
            "maturity_level": agent.status,
            "action_complexity": governance_info.get('action_complexity', 1),
            "requires_approval": governance_info.get('requires_approval', False),
            "supervised": agent.status in ['STUDENT', 'INTERN'],
        }

        # Prepare episode context for system prompt
        episode_context_str = ""
        if episode_context:
            episode_context_str = "\n\n**Relevant Past Episodes:**\n"
            for ep in episode_context:
                episode_context_str += f"- {ep.title}: {ep.summary}\n"

        # Prepare messages for LLM
        messages = []

        # Add system prompt with agent context and episode context
        system_prompt = f"""You are {agent.name}, an AI agent in the Atom platform.

**Agent Description:**
{agent.description or 'No description available.'}

**Capabilities:**
{', '.join(agent.configuration.get('capabilities', ['General assistance']))}

**Maturity Level:** {agent.status}

{episode_context_str}

Provide helpful, concise responses. You are communicating via a mobile interface, so be direct and practical."""

        messages.append({
            "role": "system",
            "content": system_prompt
        })

        # Add current user message
        messages.append({
            "role": "user",
            "content": request.message
        })

        # Initialize BYOK handler for LLM streaming
        byok_handler = BYOKHandler(workspace_id="default", provider_id="auto")

        # Analyze query complexity and get optimal provider
        complexity = byok_handler.analyze_query_complexity(request.message, task_type="chat")
        provider_id, model = byok_handler.get_optimal_provider(
            complexity,
            task_type="chat",
            prefer_cost=True,
            tenant_plan="free",
            is_managed_service=False,
            requires_tools=False
        )

        logger.info(f"Mobile agent chat using {provider_id}/{model} for agent {agent.name}")

        # Send initial message via WebSocket
        user_channel = f"user:{current_user.id}"
        await ws_manager.broadcast(
            user_channel,
            {
                "type": "streaming:start",
                "id": message_id,
                "agent_id": agent_id,
                "agent_name": agent.name,
                "model": model,
                "provider": provider_id
            }
        )

        # Stream tokens via WebSocket
        accumulated_content = ""
        tokens_count = 0

        try:
            async for token in byok_handler.stream_completion(
                messages=messages,
                model=model,
                provider_id=provider_id,
                temperature=0.7,
                max_tokens=2000,
                agent_id=agent_id
            ):
                accumulated_content += token
                tokens_count += 1

                # Broadcast token to frontend
                await ws_manager.broadcast(user_channel, {
                    "type": ws_manager.STREAMING_UPDATE,
                    "id": message_id,
                    "delta": token,
                    "complete": False,
                    "metadata": {
                        "model": model,
                        "tokens_so_far": len(accumulated_content)
                    }
                })

            # Send completion message
            await ws_manager.broadcast(user_channel, {
                "type": ws_manager.STREAMING_COMPLETE,
                "id": message_id,
                "content": accumulated_content,
                "complete": True
            })

            # Update agent execution record
            end_time = datetime.utcnow()
            duration_seconds = (end_time - start_time).total_seconds()

            agent_execution.status = "completed"
            agent_execution.output_summary = f"Generated {tokens_count} tokens, {len(accumulated_content)} chars"
            agent_execution.duration_seconds = duration_seconds
            agent_execution.completed_at = end_time
            db.commit()

            # Record successful outcome for confidence scoring
            await governance_service.record_outcome(agent.id, success=True)

            logger.info(f"Mobile agent execution {agent_execution.id} completed successfully")

            return MobileChatResponse(
                message_id=message_id,
                agent_id=agent_id,
                content=accumulated_content,
                is_streaming=False,  # Streaming completed
                governance=governance_metadata,
                episode_context=[ep.dict() for ep in episode_context] if episode_context else None
            )

        except Exception as stream_error:
            logger.error(f"LLM streaming error: {stream_error}")

            # Mark execution as failed
            agent_execution.status = "failed"
            agent_execution.error_message = str(stream_error)
            agent_execution.completed_at = datetime.utcnow()
            db.commit()

            # Record failure for confidence scoring
            await governance_service.record_outcome(agent.id, success=False)

            # Send error via WebSocket
            await ws_manager.broadcast(user_channel, {
                "type": ws_manager.STREAMING_ERROR,
                "id": message_id,
                "error": str(stream_error)
            })

            raise router.internal_error(f"Agent execution failed: {str(stream_error)}")

    except HTTPException:
        # Re-raise HTTP exceptions
        if agent_execution:
            agent_execution.status = "failed"
            agent_execution.error_message = "HTTP exception raised"
            agent_execution.completed_at = datetime.utcnow()
            db.commit()
        raise
    except Exception as e:
        logger.error(f"Mobile agent chat error: {e}")

        # Update execution record if it exists
        if agent_execution:
            try:
                agent_execution.status = "failed"
                agent_execution.error_message = str(e)
                agent_execution.completed_at = datetime.utcnow()
                db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update execution record: {db_error}")

        raise router.internal_error(f"Chat failed: {str(e)}")


@router.get("/{agent_id}/episodes")
async def get_agent_episodes(
    agent_id: str,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent episodes for an agent (mobile-optimized).

    Args:
        agent_id: Agent ID
        limit: Max episodes to return
        offset: Pagination offset

    Returns:
        List of episodes with agent context
    """
    try:
        # Verify agent exists
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise router.not_found_error("Agent", agent_id)

        # Retrieve episodes
        retrieval_service = EpisodeRetrievalService(db)
        episodes = retrieval_service.retrieve_episodes(
            query_text="",
            user_id=str(current_user.id),
            agent_id=agent_id,
            mode=RetrievalMode.SEQUENTIAL,
            limit=limit
        )

        # Convert to response format
        episodes_data = [
            {
                "episode_id": ep.episode_id,
                "title": ep.title or f"Episode {ep.episode_id[:8]}",
                "summary": ep.summary[:300] if ep.summary else "",
                "created_at": ep.created_at.isoformat(),
                "segment_count": ep.segment_count if hasattr(ep, 'segment_count') else 0,
                "relevance_score": ep.relevance_score,
            }
            for ep in episodes
        ]

        return {
            "episodes": episodes_data,
            "total": len(episodes_data),
            "agent_id": agent_id,
            "agent_name": agent.name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent episodes: {e}")
        raise router.internal_error(f"Failed to retrieve episodes: {str(e)}")


@router.get("/categories")
async def list_agent_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of agent categories for filtering (mobile-optimized).

    Returns:
        List of unique categories with counts
    """
    try:
        from sqlalchemy import func

        categories = db.query(
            AgentRegistry.category,
            func.count(AgentRegistry.id).label('count')
        ).filter(
            AgentRegistry.status == "active"
        ).group_by(
            AgentRegistry.category
        ).all()

        return {
            "categories": [
                {
                    "name": cat.category,
                    "count": cat.count
                }
                for cat in categories
            ]
        }

    except Exception as e:
        logger.error(f"Failed to list categories: {e}")
        raise router.internal_error(f"Failed to list categories: {str(e)}")


@router.get("/capabilities")
async def list_agent_capabilities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of all agent capabilities for filtering (mobile-optimized).

    Returns:
        List of unique capabilities with counts
    """
    try:
        # Get all unique capabilities from agent configs
        agents = db.query(AgentRegistry).filter(
            AgentRegistry.status == "active"
        ).all()

        capability_counts = {}
        for agent in agents:
            capabilities = agent.configuration.get('capabilities', [])
            for cap in capabilities:
                capability_counts[cap] = capability_counts.get(cap, 0) + 1

        return {
            "capabilities": [
                {
                    "name": cap,
                    "count": count
                }
                for cap, count in sorted(capability_counts.items())
            ]
        }

    except Exception as e:
        logger.error(f"Failed to list capabilities: {e}")
        raise router.internal_error(f"Failed to list capabilities: {str(e)}")


@router.post("/{agent_id}/feedback")
async def submit_agent_feedback(
    agent_id: str,
    feedback: str,
    rating: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback for an agent response (mobile-optimized).

    Args:
        agent_id: Agent ID
        feedback: Feedback text
        rating: Optional rating (1-5)

    Returns:
        Confirmation of feedback submission
    """
    try:
        # Verify agent exists
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise router.not_found_error("Agent", agent_id)

        # Create feedback record
        agent_feedback = AgentFeedback(
            agent_id=agent_id,
            user_id=str(current_user.id),
            feedback=feedback,
            rating=rating,
            source="mobile"
        )

        db.add(agent_feedback)
        db.commit()

        logger.info(f"Feedback submitted for agent {agent_id} by user {current_user.id}")

        return router.success_response(
            message="Feedback submitted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        raise router.internal_error(f"Failed to submit feedback: {str(e)}")
