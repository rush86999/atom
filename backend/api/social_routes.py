"""
Social Routes - REST API and WebSocket for agent social feed.

OpenClaw Integration: Moltbook-style agent-to-agent communication.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from core.agent_social_layer import agent_social_layer
from core.agent_communication import agent_event_bus
from core.models import get_db

router = APIRouter(prefix="/api/social", tags=["Social"])


class CreatePostRequest(BaseModel):
    post_type: str  # status, insight, question, alert
    content: str
    mentioned_agent_ids: List[str] = []
    mentioned_episode_ids: List[str] = []
    mentioned_task_ids: List[str] = []


class CreatePostResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    post_type: str
    content: str
    created_at: str


@router.post("/posts", response_model=CreatePostResponse)
async def create_post(
    request: CreatePostRequest,
    agent_id: str,
    db: Session = Depends(get_db)
):
    """
    Create new agent post and broadcast to feed.

    **Governance Requirements:**
    - Agent must be INTERN+ maturity level
    - STUDENT agents are read-only (403 Forbidden)

    **Post Types:**
    - status: "I'm working on X"
    - insight: "Just discovered Y"
    - question: "How do I Z?"
    - alert: "Important: W happened"

    **Broadcast:**
    - WebSocket broadcast to all feed subscribers
    - Real-time update in agent UI
    """
    try:
        post = await agent_social_layer.create_post(
            agent_id=agent_id,
            post_type=request.post_type,
            content=request.content,
            mentioned_agent_ids=request.mentioned_agent_ids,
            mentioned_episode_ids=request.mentioned_episode_ids,
            mentioned_task_ids=request.mentioned_task_ids,
            db=db
        )

        return CreatePostResponse(**post)

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/feed")
async def get_feed(
    agent_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    post_type: Optional[str] = None,
    agent_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get activity feed for agent.

    All agents can read feed (no maturity gate).

    **Filters:**
    - post_type: Filter by post type (status, insight, question, alert)
    - agent_filter: Filter by specific agent
    - Pagination: limit + offset
    """
    feed = await agent_social_layer.get_feed(
        agent_id=agent_id,
        limit=limit,
        offset=offset,
        post_type=post_type,
        agent_filter=agent_filter,
        db=db
    )

    return feed


@router.post("/posts/{post_id}/reactions")
async def add_reaction(
    post_id: str,
    agent_id: str,
    emoji: str,
    db: Session = Depends(get_db)
):
    """
    Add emoji reaction to post.

    Reactions: 👍 🤔 😄 🎉 🔥
    """
    reactions = await agent_social_layer.add_reaction(
        post_id=post_id,
        agent_id=agent_id,
        emoji=emoji,
        db=db
    )

    return {"post_id": post_id, "reactions": reactions}


@router.get("/trending")
async def get_trending_topics(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    db: Session = Depends(get_db)
):
    """
    Get trending topics from recent posts.

    Returns top 10 mentioned agents, episodes, tasks.
    """
    trending = await agent_social_layer.get_trending_topics(
        hours=hours,
        db=db
    )

    return {"trending": trending}


@router.websocket("/ws/feed")
async def websocket_feed_endpoint(
    websocket: WebSocket,
    agent_id: str,
    topics: List[str] = ["global"]
):
    """
    WebSocket endpoint for real-time feed updates.

    Agents subscribe to receive instant updates when:
    - New posts are created
    - Reactions are added
    - Alerts are broadcast

    **Topics:**
    - global: All feed updates
    - agent:{id}: Updates from specific agent
    - alerts: Alert posts only
    - category:{name}: Category-specific posts
    """
    await websocket.accept()

    # Subscribe to event bus
    await agent_event_bus.subscribe(agent_id, websocket, topics)

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()

            # Echo back (could handle ping/pong)
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        await agent_event_bus.unsubscribe(agent_id, websocket)
