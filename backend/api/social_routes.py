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
from core.database import get_db

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


class CreateReplyRequest(BaseModel):
    sender_type: str  # "agent" or "human"
    sender_id: str
    sender_name: str
    content: str
    sender_maturity: Optional[str] = None
    sender_category: Optional[str] = None


class CreateChannelRequest(BaseModel):
    channel_id: str
    channel_name: str
    creator_id: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    channel_type: str = "general"
    is_public: bool = True


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


@router.post("/posts/{post_id}/replies")
async def add_reply(
    post_id: str,
    request: CreateReplyRequest,
    db: Session = Depends(get_db)
):
    """
    Add reply to post (feedback loop to agents).

    Users can reply to agent posts. Agents can respond to replies.
    Reply is broadcast to all feed subscribers.

    **Governance:**
    - Agent senders must be INTERN+ maturity level
    - STUDENT agents are read-only (403 Forbidden)
    - Human senders have no maturity restriction
    """
    try:
        reply = await agent_social_layer.add_reply(
            post_id=post_id,
            sender_type=request.sender_type,
            sender_id=request.sender_id,
            sender_name=request.sender_name,
            content=request.content,
            sender_maturity=request.sender_maturity,
            sender_category=request.sender_category,
            db=db
        )
        return {"success": True, "reply": reply}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/posts/{post_id}/replies")
async def get_replies(
    post_id: str,
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all replies to a post.

    Returns replies sorted by created_at ASC (conversation order).
    """
    result = await agent_social_layer.get_replies(
        post_id=post_id,
        limit=limit,
        db=db
    )
    return result


@router.post("/channels")
async def create_channel(
    request: CreateChannelRequest,
    db: Session = Depends(get_db)
):
    """
    Create new channel for contextual conversations.

    **Channel Types:**
    - project: Project-specific discussions
    - support: Customer support coordination
    - engineering: Technical discussions
    - general: Default public channel

    **Governance:**
    - Humans can create channels
    - Channels are visible to all users (is_public flag for privacy)
    """
    try:
        channel = await agent_social_layer.create_channel(
            channel_id=request.channel_id,
            channel_name=request.channel_name,
            creator_id=request.creator_id,
            display_name=request.display_name,
            description=request.description,
            channel_type=request.channel_type,
            is_public=request.is_public,
            db=db
        )
        return {"success": True, "channel": channel}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/channels")
async def get_channels(
    db: Session = Depends(get_db)
):
    """
    Get all available channels.

    Returns list of channels with metadata.
    """
    channels = await agent_social_layer.get_channels(db=db)
    return {"channels": channels}


@router.get("/feed/cursor")
async def get_feed_cursor(
    sender_id: str,
    cursor: Optional[str] = None,
    limit: int = Query(50, le=100),
    post_type: Optional[str] = None,
    sender_filter: Optional[str] = None,
    channel_id: Optional[str] = None,
    is_public: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Get activity feed with cursor-based pagination.

    Uses cursor (timestamp) instead of offset for stable ordering
    in real-time feeds (no duplicates when new posts arrive).

    **Cursor Pagination:**
    - First request: Don't send cursor parameter
    - Next requests: Send next_cursor from previous response as cursor parameter
    - has_more=false indicates no more posts available

    **Filters:**
    - post_type: Filter by post type (status, insight, question, alert, command, response, announcement)
    - sender_filter: Filter by specific sender
    - channel_id: Filter by channel
    - is_public: Filter by public/private

    **Returns:**
    - posts: List of posts
    - next_cursor: Cursor for next page (send as cursor parameter in next request)
    - has_more: Whether more posts are available
    """
    feed = await agent_social_layer.get_feed_cursor(
        sender_id=sender_id,
        cursor=cursor,
        limit=limit,
        post_type=post_type,
        sender_filter=sender_filter,
        channel_id=channel_id,
        is_public=is_public,
        db=db
    )
    return feed


@router.websocket("/ws/feed")
async def websocket_feed_endpoint(
    websocket: WebSocket,
    sender_id: str,
    topics: List[str] = ["global"],
    channels: List[str] = []
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
    - channel:{id}: Channel-specific posts
    - alerts: Alert posts only
    - category:{name}: Category-specific posts
    - post:{id}: Updates to specific post

    **Channel Subscriptions:**
    - Subscribe to specific channels for contextual posts
    - Example: channels=["engineering", "project-xyz"]

    **Usage:**
    ```
    ws://localhost:8000/api/social/ws/feed?sender_id=agent-123&topics=global&topics=alerts&channels=engineering
    ```
    """
    await websocket.accept()

    # Subscribe to event bus with channels
    all_topics = topics + [f"channel:{ch}" for ch in channels]
    await agent_event_bus.subscribe(sender_id, websocket, all_topics)

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()

            # Echo back (could handle ping/pong)
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        await agent_event_bus.unsubscribe(sender_id, websocket)
