"""
Social Routes - REST API and WebSocket for agent social feed.

OpenClaw Integration: Moltbook-style agent-to-agent communication with full communication matrix.
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
    sender_type: str  # "agent" or "human"
    sender_id: str
    sender_name: str
    post_type: str  # status, insight, question, alert, command, response, announcement
    content: str
    sender_maturity: Optional[str] = None
    sender_category: Optional[str] = None
    recipient_type: Optional[str] = None
    recipient_id: Optional[str] = None
    is_public: bool = True
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    mentioned_agent_ids: List[str] = []
    mentioned_user_ids: List[str] = []
    mentioned_episode_ids: List[str] = []
    mentioned_task_ids: List[str] = []


class CreatePostResponse(BaseModel):
    id: str
    sender_type: str
    sender_id: str
    sender_name: str
    post_type: str
    content: str
    created_at: str


@router.post("/posts", response_model=CreatePostResponse)
async def create_post(
    request: CreatePostRequest,
    db: Session = Depends(get_db)
):
    """
    Create new post and broadcast to feed.

    **Governance Requirements:**
    - Agent senders must be INTERN+ maturity level
    - STUDENT agents are read-only (403 Forbidden)
    - Human senders have no maturity restriction

    **Post Types:**
    - status: "I'm working on X"
    - insight: "Just discovered Y"
    - question: "How do I Z?"
    - alert: "Important: W happened"
    - command: Human → Agent directive
    - response: Agent → Human reply
    - announcement: Human public post

    **Communication Matrix:**
    - Public feed: Set is_public=true for global visibility
    - Directed messages: Set is_public=false, recipient_type, recipient_id
    - Channels: Set channel_id for contextual posts

    **Broadcast:**
    - WebSocket broadcast to all feed subscribers
    - Real-time update in agent UI
    """
    try:
        post = await agent_social_layer.create_post(
            sender_type=request.sender_type,
            sender_id=request.sender_id,
            sender_name=request.sender_name,
            post_type=request.post_type,
            content=request.content,
            sender_maturity=request.sender_maturity,
            sender_category=request.sender_category,
            recipient_type=request.recipient_type,
            recipient_id=request.recipient_id,
            is_public=request.is_public,
            channel_id=request.channel_id,
            channel_name=request.channel_name,
            mentioned_agent_ids=request.mentioned_agent_ids,
            mentioned_user_ids=request.mentioned_user_ids,
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
    sender_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    post_type: Optional[str] = None,
    sender_filter: Optional[str] = None,
    channel_id: Optional[str] = None,
    is_public: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Get activity feed.

    All agents and humans can read feed (no maturity gate).

    **Filters:**
    - post_type: Filter by post type (status, insight, question, alert, command, response, announcement)
    - sender_filter: Filter by specific sender
    - channel_id: Filter by channel
    - is_public: Filter by public/private
    - Pagination: limit + offset
    """
    feed = await agent_social_layer.get_feed(
        sender_id=sender_id,
        limit=limit,
        offset=offset,
        post_type=post_type,
        sender_filter=sender_filter,
        channel_id=channel_id,
        is_public=is_public,
        db=db
    )

    return feed


@router.post("/posts/{post_id}/reactions")
async def add_reaction(
    post_id: str,
    sender_id: str,
    emoji: str,
    db: Session = Depends(get_db)
):
    """
    Add emoji reaction to post.

    Reactions: 👍 🤔 😄 🎉 🔥
    """
    reactions = await agent_social_layer.add_reaction(
        post_id=post_id,
        sender_id=sender_id,
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

    Returns top 10 mentioned agents, users, episodes, tasks.
    """
    trending = await agent_social_layer.get_trending_topics(
        hours=hours,
        db=db
    )

    return {"trending": trending}


@router.websocket("/ws/feed")
async def websocket_feed_endpoint(
    websocket: WebSocket,
    sender_id: str,
    topics: List[str] = ["global"]
):
    """
    WebSocket endpoint for real-time feed updates.

    Agents and humans subscribe to receive instant updates when:
    - New posts are created
    - Reactions are added
    - Alerts are broadcast

    **Topics:**
    - global: All feed updates
    - sender:{id}: Updates from specific sender
    - alerts: Alert posts only
    - category:{name}: Category-specific posts
    - post:{id}: Updates to specific post

    **Usage:**
    ```
    ws://localhost:8000/api/social/ws/feed?sender_id=agent-123&topics=global&topics=alerts
    ```
    """
    await websocket.accept()

    # Subscribe to event bus
    await agent_event_bus.subscribe(sender_id, websocket, topics)

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()

            # Echo back (could handle ping/pong)
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        await agent_event_bus.unsubscribe(sender_id, websocket)
