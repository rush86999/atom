---
phase: 13-openclaw-integration
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/models.py
  - backend/core/agent_communication.py
  - backend/core/agent_social_layer.py
  - backend/api/social_routes.py
  - backend/api/channel_routes.py
  - backend/tests/test_agent_social_layer.py
  - backend/tests/test_channels.py
autonomous: true

must_haves:
  truths:
    - Agents can post natural language status updates to feed
    - Humans can send directed messages to agents
    - Humans can post public announcements to feed
    - Agents can respond to human messages
    - Posts support public feed, directed messaging, and channels/rooms
    - Posts are typed (status, insight, question, alert, command, response)
    - INTERN+ agents can post, STUDENT agents are read-only
    - Humans can post with no maturity restriction
    - Posts trigger WebSocket broadcasts to subscribers
    - Question and alert posts notify relevant agents
    - Activity feed is paginated and ordered by recency
    - Posts include sender context (agent or human, maturity, category, name)
    - Channels allow context-specific conversations (project, support, engineering)
  artifacts:
    - path: backend/core/models.py
      provides: Channel and AgentPost database models for full communication matrix
      contains: "class Channel", "class AgentPost"
    - path: backend/core/agent_communication.py
      provides: Event bus for real-time communication
      contains: "AgentEventBus"
    - path: backend/core/agent_social_layer.py
      provides: Social layer service for human↔agent and agent↔agent communication
      min_lines: 400
      exports: ["AgentSocialLayer", "create_post", "send_direct_message", "get_feed", "subscribe_to_feed"]
    - path: backend/api/social_routes.py
      provides: REST API and WebSocket for social feed and messaging
      contains: "POST /api/social/posts", "WebSocket /api/social/ws/feed"
    - path: backend/api/channel_routes.py
      provides: Channel management API
      contains: "POST /api/channels", "GET /api/channels"
  key_links:
    - from: "backend/core/agent_social_layer.py"
      to: "backend/core/agent_governance_service.py"
      via: "Governance maturity check before posting"
      pattern: "maturity_level.*INTERN"
    - from: "backend/api/social_routes.py"
      to: "backend/core/agent_communication.py"
      via: "WebSocket connection for real-time feed updates"
      pattern: "websocket.*broadcast"
---

<objective>
Implement Full Communication Matrix with Agent Social Layer (Moltbook-style).

OpenClaw's viral feature: Agents and humans talking through multiple communication channels. Atom's twist:
- Human → Agent: Direct messages, public posts, commands
- Agent → Human: Responses, status updates, requests
- Agent ↔ Agent: Social feed (INTERN+ gate, STUDENT read-only)
- Public feed: Global visibility for all posts
- Directed messaging: 1:1 human-to-agent and agent-to-human
- Channels/rooms: Context-specific conversations (project, support, engineering)

Communication types: status, insight, question, alert, command (human→agent), response (agent→human)

Purpose: Gamify agent observation + enable human-agent collaboration
Output: AgentSocialLayer with event bus, WebSocket broadcasts, typed posts, directed messages, channels, pagination
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
@/Users/rushiparikh/.claude/get-shit-done/references/checkpoints.md
@/Users/rushiparikh/.claude/get-shit-done/references/tdd.md
</execution_context>

<context>
@.planning/phases/13-openclaw-integration/13-RESEARCH.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Existing implementations
@backend/core/agent_governance_service.py
@backend/core/episode_retrieval_service.py
@backend/core/models.py
</context>

<tasks>

<task type="auto">
  <name>Create AgentPost database model</name>
  <files>backend/core/models.py</files>
  <action>
Add AgentPost model after Episode (around line 4500):

```python
class AgentPost(Base):
    """
    Full communication matrix - human ↔ agent, agent ↔ agent, public feed, directed messages, channels.

    OpenClaw Integration (Moltbook-style social layer with expansion):
    - Human → Agent: Direct messages, commands, public announcements
    - Agent → Human: Responses, status updates, requests for approval
    - Agent ↔ Agent: Social feed (INTERN+ gate, STUDENT read-only)
    - Public feed: Global visibility for all participants
    - Directed messaging: 1:1 communication
    - Channels/rooms: Context-specific conversations (project, support, engineering)
    - WebSocket broadcasts for real-time updates

    Communication types:
    - status: Agent status update
    - insight: Agent discovery/learning
    - question: Agent asks for help
    - alert: Important notification
    - command: Human → Agent directive
    - response: Agent → Human reply
    - announcement: Human public post

    Purpose:
    - Gamify agent observation (watch agents "talk")
    - Enable human-agent collaboration
    - Provide transparency into agent operations
    - Support directed messaging and channels
    """
    __tablename__ = "agent_posts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Who sent it
    sender_type = Column(String, nullable=False)  # "agent" or "human"
    sender_id = Column(String, nullable=False)  # agent_id or user_id
    sender_name = Column(String, nullable=False)  # Denormalized for queries
    sender_maturity = Column(String, nullable=True)  # For agents: STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    sender_category = Column(String, nullable=True)  # For agents: engineering, sales, support, etc.

    # Who receives it (for directed messages)
    recipient_type = Column(String, nullable=True)  # "agent", "human", or null (public)
    recipient_id = Column(String, nullable=True)  # agent_id or user_id (null if public)
    is_public = Column(Boolean, default=True)  # True = public feed, False = directed message

    # Channel/room (optional, for contextual conversations)
    channel_id = Column(String, ForeignKey("channels.id"), nullable=True)  # project, support, engineering
    channel_name = Column(String, nullable=True)  # Denormalized for queries

    # What
    post_type = Column(String, nullable=False)  # status, insight, question, alert, command, response, announcement
    content = Column(Text, nullable=False)  # Natural language post

    # Context (optional mentions, references)
    mentioned_agent_ids = Column(JSON, default=list)  # ["agent-123", "agent-456"]
    mentioned_user_ids = Column(JSON, default=list)  # ["user-789"]
    mentioned_episode_ids = Column(JSON, default=list)  # ["episode-101"]
    mentioned_task_ids = Column(JSON, default=list)  # ["task-202"]

    # Engagement
    reactions = Column(JSON, default=dict)  # {"👍": 3, "🤔": 1}
    reply_count = Column(Integer, default=0)
    read_at = Column(DateTime(timezone=True), nullable=True)  # For directed messages

    # When
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    agent = relationship("AgentRegistry", foreign_keys=[sender_id], backref="social_posts")
    user = relationship("User", foreign_keys=[sender_id], backref="social_posts")
    channel = relationship("Channel", backref="posts")

    __table_args__ = (
        Index('idx_agent_posts_created_at', 'created_at'),
        Index('idx_agent_posts_sender_id', 'sender_id'),
        Index('idx_agent_posts_recipient_id', 'recipient_id'),
        Index('idx_agent_posts_channel_id', 'channel_id'),
        Index('idx_agent_posts_is_public', 'is_public'),
    )
```
  </action>
  <verify>
```bash
# Verify AgentPost model exists
grep -n "class AgentPost" backend/core/models.py
grep -n "__tablename__ = \"agent_posts\"" backend/core/models.py
grep -n "INTERN.*can post" backend/core/models.py
```
  </verify>
  <done>
AgentPost model added to models.py:
- Table name: agent_posts
- Fields: sender_type, sender_id, recipient_id, is_public, channel_id, post_type, content
- Indexes: created_at, sender_id, recipient_id, channel_id, is_public
- Post types: status, insight, question, alert, command, response, announcement
- STUDENT read-only, INTERN+ can post
- Humans can post with no maturity restriction
- Support for public feed, directed messages, and channels
  </done>
</task>

<task type="auto">
  <name>Create Channel database model</name>
  <files>backend/core/models.py</files>
  <action>
Add Channel model before AgentPost (around line 4480):

```python
class Channel(Base):
    """
    Communication channels/rooms for contextual conversations.

    Channels allow organizing conversations by context:
    - project: Project-specific discussions
    - support: Customer support coordination
    - engineering: Technical discussions
    - general: Default public channel

    Governance:
    - Humans can create channels
    - INTERN+ agents can post to channels
    - STUDENT agents are read-only
    """
    __tablename__ = "channels"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Channel metadata
    name = Column(String, nullable=False, unique=True)  # project-xyz, support, engineering
    display_name = Column(String, nullable=False)  # "Project XYZ", "Support", "Engineering"
    description = Column(Text, nullable=True)
    channel_type = Column(String, nullable=False)  # project, support, engineering, general

    # Access control
    is_public = Column(Boolean, default=True)  # False = private channel
    created_by = Column(String, ForeignKey("users.id"), nullable=False)

    # Members
    agent_members = Column(JSON, default=list)  # ["agent-123", "agent-456"]
    user_members = Column(JSON, default=list)  # ["user-789"]

    # When
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    creator = relationship("User", backref="channels_created")

    __table_args__ = (
        Index('idx_channels_name', 'name'),
        Index('idx_channels_type', 'channel_type'),
    )
```
  </action>
  <verify>
```bash
# Verify Channel model exists
grep -n "class Channel" backend/core/models.py
grep -n "__tablename__ = \"channels\"" backend/core/models.py
```
  </verify>
  <done>
Channel model added to models.py:
- Table name: channels
- Fields: name, display_name, channel_type, is_public, members
- Channel types: project, support, engineering, general
- Public and private channel support
- Member management (agents and users)
  </done>
</task>

<task type="auto">
  <name>Create AgentEventBus for pub/sub</name>
  <files>backend/core/agent_communication.py</files>
  <action>
Create backend/core/agent_communication.py (200-250 lines):

```python
"""
Agent Event Bus - Pub/sub for agent-to-agent communication.

OpenClaw Integration: Event-driven architecture for real-time agent feed.
Uses WebSocket for broadcasts (MVP <100 agents) or Redis Pub/Sub (enterprise).
"""

import asyncio
import json
import logging
from typing import Dict, Set, Any, List, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentEventBus:
    """
    Event bus for agent communication.

    Patterns:
    - Publish-subscribe for WebSocket broadcasts
    - Topic-based filtering (agent_id, post_type)
    - Fan-out to multiple subscribers

    MVP: In-memory WebSocket connections (<100 agents)
    Enterprise: Redis Pub/Sub for horizontal scaling
    """

    def __init__(self):
        # agent_id -> set of WebSocket connections
        self._subscribers: Dict[str, Set[asyncio.WebSocket]] = {}

        # Topic subscriptions (agent_id, post_type, global)
        self._topics: Dict[str, Set[str]] = {
            "global": set(),  # All agents receive global broadcasts
        }

    async def subscribe(self, agent_id: str, websocket: asyncio.WebSocket, topics: List[str] = None):
        """
        Subscribe agent to event bus.

        Args:
            agent_id: Agent subscribing
            websocket: WebSocket connection for broadcasts
            topics: Topics to subscribe (default: ["global"])
        """
        if agent_id not in self._subscribers:
            self._subscribers[agent_id] = set()

        self._subscribers[agent_id].add(websocket)

        # Subscribe to topics
        if topics:
            for topic in topics:
                if topic not in self._topics:
                    self._topics[topic] = set()
                self._topics[topic].add(agent_id)

        logger.info(f"Agent {agent_id} subscribed to event bus (topics: {topics})")

    async def unsubscribe(self, agent_id: str, websocket: asyncio.WebSocket):
        """Unsubscribe agent's WebSocket connection."""
        if agent_id in self._subscribers:
            self._subscribers[agent_id].discard(websocket)

            # Clean up if no more connections
            if not self._subscribers[agent_id]:
                del self._subscribers[agent_id]

                # Remove from all topics
                for topic_subscribers in self._topics.values():
                    topic_subscribers.discard(agent_id)

        logger.info(f"Agent {agent_id} unsubscribed from event bus")

    async def publish(self, event: Dict[str, Any], topics: List[str] = None):
        """
        Publish event to subscribers.

        Args:
            event: Event data (agent_post, status_update, etc.)
            topics: Topics to broadcast to (default: ["global"])
        """
        topics = topics or ["global"]

        # Collect unique subscribers across all topics
        subscriber_ids = set()
        for topic in topics:
            if topic in self._topics:
                subscriber_ids.update(self._topics[topic])

        # Broadcast to all subscriber WebSockets
        for agent_id in subscriber_ids:
            if agent_id in self._subscribers:
                for websocket in self._subscribers[agent_id]:
                    try:
                        await websocket.send_json(event)
                    except Exception as e:
                        logger.warning(f"Failed to send to agent {agent_id}: {e}")
                        # Remove dead connection
                        await self.unsubscribe(agent_id, websocket)

        logger.info(f"Event published to {len(subscriber_ids)} subscribers (topics: {topics})")

    async def broadcast_post(self, post_data: Dict[str, Any]):
        """
        Broadcast new agent post to all subscribers.

        Shortcut for publish() with post-specific topics.
        """
        topics = ["global", f"agent:{post_data['agent_id']}"]

        # Alert posts go to all agents
        # Question posts go to agents in same category
        if post_data.get("post_type") == "alert":
            topics.append("alerts")
        elif post_data.get("post_type") == "question":
            if post_data.get("agent_category"):
                topics.append(f"category:{post_data['agent_category']}")

        await self.publish({"type": "agent_post", "data": post_data}, topics)


# Global event bus instance
agent_event_bus = AgentEventBus()
```

Follow Atom patterns:
- Async/await for WebSocket communication
- Type hints and docstrings
- Error handling for disconnected clients
- Topic-based filtering for scalability
  </action>
  <verify>
```bash
# Verify event bus created
test -f backend/core/agent_communication.py
grep -n "class AgentEventBus" backend/core/agent_communication.py
grep -n "async def subscribe" backend/core/agent_communication.py
grep -n "async def broadcast_post" backend/core/agent_communication.py
```
  </verify>
  <done>
AgentEventBus created with:
- Pub/sub pattern for agent communication
- WebSocket subscriber management
- Topic-based filtering (global, agent:, category:, alerts)
- broadcast_post() for agent posts
- Error handling for disconnected clients
- Global singleton instance
  </done>
</task>

<task type="auto">
  <name>Create AgentSocialLayer service</name>
  <files>backend/core/agent_social_layer.py</files>
  <action>
Create backend/core/agent_social_layer.py (300-350 lines):

```python
"""
Agent Social Layer - Moltbook-style agent feed service.

OpenClaw Integration: Natural language agent-to-agent communication.
INTERN+ agents can post, STUDENT read-only. Typed posts (status/insight/question/alert).
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.models import AgentPost, AgentRegistry
from core.agent_governance_service import agent_governance_service
from core.agent_communication import agent_event_bus
from core.governance_cache import get_governance_cache

logger = logging.getLogger(__name__)


class AgentSocialLayer:
    """
    Social feed service for agent-to-agent communication.

    Governance:
    - INTERN+ maturity required to post
    - STUDENT agents are read-only
    - All agents can read feed

    Post Types:
    - status: "I'm working on X"
    - insight: "Just discovered Y"
    - question: "How do I Z?"
    - alert: "Important: W happened"
    """

    def __init__(self):
        self.logger = logger

    async def create_post(
        self,
        agent_id: str,
        post_type: str,
        content: str,
        mentioned_agent_ids: List[str] = None,
        mentioned_episode_ids: List[str] = None,
        mentioned_task_ids: List[str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Create new agent post and broadcast to feed.

        Governance Check:
        - Agent must be INTERN+ maturity to post
        - STUDENT agents are rejected with PermissionError

        Args:
            agent_id: Agent creating post
            post_type: Type (status, insight, question, alert)
            content: Natural language content
            mentioned_agent_ids: Optional agent mentions
            mentioned_episode_ids: Optional episode references
            mentioned_task_ids: Optional task references
            db: Database session

        Returns:
            Created post data

        Raises:
            PermissionError: If agent is STUDENT maturity
            ValueError: If post_type is invalid
        """
        # Step 1: Check maturity using cache for speed
        cache = await get_governance_cache()
        agent_key = f"agent:{agent_id}"
        agent_data = await cache.get(agent_key)

        if not agent_data:
            raise PermissionError(f"Agent {agent_id} not found")

        maturity_level = agent_data.get("maturity_level", "STUDENT")

        # Step 2: Governance gate - INTERN+ can post, STUDENT read-only
        if maturity_level == "STUDENT":
            raise PermissionError(
                f"STUDENT agents cannot post to social feed. "
                f"Agent {agent_id} is {maturity_level}, requires INTERN+ maturity"
            )

        # Step 3: Validate post_type
        valid_types = ["status", "insight", "question", "alert"]
        if post_type not in valid_types:
            raise ValueError(
                f"Invalid post_type '{post_type}'. Must be one of: {', '.join(valid_types)}"
            )

        # Step 4: Create post
        post = AgentPost(
            agent_id=agent_id,
            agent_name=agent_data.get("name", agent_id),
            agent_maturity=maturity_level,
            agent_category=agent_data.get("category"),
            post_type=post_type,
            content=content,
            mentioned_agent_ids=mentioned_agent_ids or [],
            mentioned_episode_ids=mentioned_episode_ids or [],
            mentioned_task_ids=mentioned_task_ids or [],
            created_at=datetime.utcnow()
        )

        if db:
            db.add(post)
            db.commit()
            db.refresh(post)

        # Step 5: Broadcast to event bus
        post_data = {
            "id": post.id,
            "agent_id": post.agent_id,
            "agent_name": post.agent_name,
            "agent_maturity": post.agent_maturity,
            "agent_category": post.agent_category,
            "post_type": post.post_type,
            "content": post.content,
            "mentioned_agent_ids": post.mentioned_agent_ids,
            "mentioned_episode_ids": post.mentioned_episode_ids,
            "mentioned_task_ids": post.mentioned_task_ids,
            "reactions": post.reactions,
            "reply_count": post.reply_count,
            "created_at": post.created_at.isoformat()
        }

        await agent_event_bus.broadcast_post(post_data)

        self.logger.info(
            f"Agent {agent_id} posted {post_type}: {content[:50]}... "
            f"(broadcast to feed)"
        )

        return post_data

    async def get_feed(
        self,
        agent_id: str,
        limit: int = 50,
        offset: int = 0,
        post_type: Optional[str] = None,
        agent_filter: Optional[str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get activity feed for agent.

        All agents can read feed (no maturity check).

        Args:
            agent_id: Agent requesting feed (for logging)
            limit: Max posts to return
            offset: Pagination offset
            post_type: Filter by post_type (optional)
            agent_filter: Filter by specific agent (optional)
            db: Database session

        Returns:
            Feed data with posts
        """
        if not db:
            return {"posts": [], "total": 0}

        # Build query
        query = db.query(AgentPost)

        # Apply filters
        if post_type:
            query = query.filter(AgentPost.post_type == post_type)

        if agent_filter:
            query = query.filter(AgentPost.agent_id == agent_filter)

        # Count total
        total = query.count()

        # Apply pagination and ordering
        posts = query.order_by(desc(AgentPost.created_at)).offset(offset).limit(limit).all()

        return {
            "posts": [
                {
                    "id": p.id,
                    "agent_id": p.agent_id,
                    "agent_name": p.agent_name,
                    "agent_maturity": p.agent_maturity,
                    "agent_category": p.agent_category,
                    "post_type": p.post_type,
                    "content": p.content,
                    "mentioned_agent_ids": p.mentioned_agent_ids,
                    "mentioned_episode_ids": p.mentioned_episode_ids,
                    "mentioned_task_ids": p.mentioned_task_ids,
                    "reactions": p.reactions,
                    "reply_count": p.reply_count,
                    "created_at": p.created_at.isoformat()
                }
                for p in posts
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }

    async def add_reaction(
        self,
        post_id: str,
        agent_id: str,
        emoji: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Add emoji reaction to post.

        Args:
            post_id: Post to react to
            agent_id: Agent reacting
            emoji: Emoji reaction
            db: Database session

        Returns:
            Updated reactions dict
        """
        if not db:
            raise ValueError("Database session required")

        post = db.query(AgentPost).filter(AgentPost.id == post_id).first()

        if not post:
            raise ValueError(f"Post {post_id} not found")

        # Add reaction (increment count)
        if not post.reactions:
            post.reactions = {}

        post.reactions[emoji] = post.reactions.get(emoji, 0) + 1

        db.commit()
        db.refresh(post)

        # Broadcast update
        await agent_event_bus.publish({
            "type": "reaction_added",
            "post_id": post_id,
            "agent_id": agent_id,
            "emoji": emoji,
            "reactions": post.reactions
        }, [f"post:{post_id}", "global"])

        return post.reactions

    async def get_trending_topics(self, hours: int = 24, db: Session = None) -> List[Dict[str, Any]]:
        """
        Get trending topics from recent posts.

        Args:
            hours: Lookback period
            db: Database session

        Returns:
            List of trending topics
        """
        if not db:
            return []

        since = datetime.utcnow() - timedelta(hours=hours)

        # Get recent posts
        posts = db.query(AgentPost).filter(
            AgentPost.created_at >= since
        ).all()

        # Count mentions
        topic_counts = {}

        for post in posts:
            # Count agent mentions
            for mentioned_id in post.mentioned_agent_ids:
                topic_counts[f"agent:{mentioned_id}"] = topic_counts.get(f"agent:{mentioned_id}", 0) + 1

            # Count episode mentions
            for episode_id in post.mentioned_episode_ids:
                topic_counts[f"episode:{episode_id}"] = topic_counts.get(f"episode:{episode_id}", 0) + 1

            # Count task mentions
            for task_id in post.mentioned_task_ids:
                topic_counts[f"task:{task_id}"] = topic_counts.get(f"task:{task_id}", 0) + 1

        # Sort by count
        trending = sorted(
            [{"topic": k, "mentions": v} for k, v in topic_counts.items()],
            key=lambda x: x["mentions"],
            reverse=True
        )

        return trending[:10]  # Top 10


# Global service instance
agent_social_layer = AgentSocialLayer()
```

Follow Atom patterns:
- Service pattern with Session injection
- GovernanceCache for <1ms maturity checks
- Async/await for event bus communication
- Type hints and docstrings
- Natural language post content (not functional logs)
  </action>
  <verify>
```bash
# Verify service created
test -f backend/core/agent_social_layer.py
grep -n "class AgentSocialLayer" backend/core/agent_social_layer.py
grep -n "INTERN.*maturity" backend/core/agent_social_layer.py
grep -n "async def create_post" backend/core/agent_social_layer.py
```
  </verify>
  <done>
AgentSocialLayer created with:
- INTERN+ maturity gate for posting (STUDENT read-only)
- create_post() with validation and WebSocket broadcast
- get_feed() with pagination and filtering
- add_reaction() for emoji reactions
- get_trending_topics() for popular mentions
- Integration with AgentEventBus for real-time updates
  </done>
</task>

<task type="auto">
  <name>Create social API routes</name>
  <files>backend/api/social_routes.py</files>
  <action>
Create backend/api/social_routes.py (200-250 lines):

```python
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
```

Follow Atom API patterns:
- BaseAPIRouter for standardized responses
- Pydantic models for type safety
- WebSocket support for real-time updates
- Error handling with HTTPException
- Query parameters for filtering/pagination
  </action>
  <verify>
```bash
# Verify routes created
test -f backend/api/social_routes.py
grep -n "POST /api/social/posts" backend/api/social_routes.py
grep -n "GET /api/social/feed" backend/api/social_routes.py
grep -n "websocket.*feed" backend/api/social_routes.py
```
  </verify>
  <done>
Social routes created with:
- POST /api/social/posts - Create post with INTERN+ gate
- GET /api/social/feed - Read feed (all agents)
- POST /api/social/posts/{id}/reactions - Add emoji reaction
- GET /api/social/trending - Trending topics
- WebSocket /api/social/ws/feed - Real-time feed updates
- Pydantic models for type safety
  </done>
</task>

<task type="auto">
  <name>Create tests for AgentSocialLayer</name>
  <files>backend/tests/test_agent_social_layer.py</files>
  <action>
Create backend/tests/test_agent_social_layer.py (300-350 lines):

```python
"""
Tests for AgentSocialLayer - agent-to-agent communication.

OpenClaw Integration Tests:
- INTERN+ maturity gate for posting
- STUDENT agents are read-only
- Post type validation
- WebSocket broadcasting
- Feed pagination and filtering
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.agent_social_layer import agent_social_layer
from core.agent_communication import agent_event_bus
from core.models import AgentPost


class TestMaturityGate:
    """Test INTERN+ maturity requirement for posting."""

    @pytest.mark.asyncio
    async def test_intern_agent_can_post(self):
        """INTERN agents can create posts."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "INTERN",
                "name": "TestAgent"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()

            post = await agent_social_layer.create_post(
                agent_id="test-agent",
                post_type="status",
                content="Working on feature X",
                db=mock_db
            )

            assert post["agent_maturity"] == "INTERN"
            assert post["content"] == "Working on feature X"

    @pytest.mark.asyncio
    async def test_student_agent_cannot_post(self):
        """STUDENT agents cannot create posts."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "STUDENT",
                "name": "TestAgent"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()

            with pytest.raises(PermissionError) as exc_info:
                await agent_social_layer.create_post(
                    agent_id="test-agent",
                    post_type="status",
                    content="I'm a student",
                    db=mock_db
                )

            assert "STUDENT agents cannot post" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_supervised_agent_can_post(self):
        """SUPERVISED agents can create posts."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "SUPERVISED",
                "name": "TestAgent"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()

            post = await agent_social_layer.create_post(
                agent_id="test-agent",
                post_type="insight",
                content="Discovered a bug",
                db=mock_db
            )

            assert post["post_type"] == "insight"


class TestPostTypes:
    """Test post type validation."""

    @pytest.mark.asyncio
    async def test_valid_post_types(self):
        """Valid post types: status, insight, question, alert."""
        valid_types = ["status", "insight", "question", "alert"]

        for post_type in valid_types:
            with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
                mock_cache_instance = AsyncMock()
                mock_cache_instance.get = AsyncMock(return_value={
                    "agent_id": "test-agent",
                    "maturity_level": "INTERN"
                })
                mock_cache.return_value = mock_cache_instance

                mock_db = Mock()
                mock_db.add = Mock()
                mock_db.commit = Mock()
                mock_db.refresh = Mock()

                post = await agent_social_layer.create_post(
                    agent_id="test-agent",
                    post_type=post_type,
                    content="Test content",
                    db=mock_db
                )

                assert post["post_type"] == post_type

    @pytest.mark.asyncio
    async def test_invalid_post_type_rejected(self):
        """Invalid post types are rejected."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "INTERN"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()

            with pytest.raises(ValueError) as exc_info:
                await agent_social_layer.create_post(
                    agent_id="test-agent",
                    post_type="invalid_type",
                    content="Test",
                    db=mock_db
                )

            assert "Invalid post_type" in str(exc_info.value)


class TestFeedPagination:
    """Test feed pagination and filtering."""

    @pytest.mark.asyncio
    async def test_feed_pagination(self):
        """Feed supports pagination with limit and offset."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.count = Mock(return_value=100)
        mock_query.order_by = Mock(return_value=mock_query)
        mock_query.offset = Mock(return_value=mock_query)
        mock_query.limit = Mock(return_value=[])

        mock_db.query = Mock(return_value=mock_query)

        feed = await agent_social_layer.get_feed(
            agent_id="test-agent",
            limit=50,
            offset=0,
            db=mock_db
        )

        assert feed["total"] == 100
        assert feed["limit"] == 50
        assert feed["offset"] == 0

    @pytest.mark.asyncio
    async def test_feed_filtering_by_post_type(self):
        """Feed can be filtered by post type."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.count = Mock(return_value=10)
        mock_query.order_by = Mock(return_value=mock_query)
        mock_query.offset = Mock(return_value=mock_query)
        mock_query.limit = Mock(return_value=[])

        mock_db.query = Mock(return_value=mock_query)

        feed = await agent_social_layer.get_feed(
            agent_id="test-agent",
            post_type="question",
            db=mock_db
        )

        assert feed["total"] == 10


class TestEventBusIntegration:
    """Test WebSocket broadcasting through event bus."""

    @pytest.mark.asyncio
    async def test_post_broadcasts_to_event_bus(self):
        """New posts are broadcast to event bus subscribers."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "INTERN",
                "name": "TestAgent"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()

            # Mock event bus broadcast
            with patch.object(agent_event_bus, 'broadcast_post', new=AsyncMock()) as mock_broadcast:
                await agent_social_layer.create_post(
                    agent_id="test-agent",
                    post_type="status",
                    content="Test post",
                    db=mock_db
                )

                # Verify broadcast was called
                assert mock_broadcast.called
                call_args = mock_broadcast.call_args[0][0]
                assert call_args["agent_id"] == "test-agent"
                assert call_args["content"] == "Test post"


class TestReactions:
    """Test emoji reactions on posts."""

    @pytest.mark.asyncio
    async def test_add_reaction(self):
        """Agents can add emoji reactions to posts."""
        mock_post = Mock()
        mock_post.reactions = {}

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(first=Mock(return_value=mock_post)))
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        reactions = await agent_social_layer.add_reaction(
            post_id="post-123",
            agent_id="agent-456",
            emoji="👍",
            db=mock_db
        )

        assert reactions["👍"] == 1

    @pytest.mark.asyncio
    async def test_multiple_reactions(self):
        """Multiple reactions of same emoji increment count."""
        mock_post = Mock()
        mock_post.reactions = {"👍": 2}

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(first=Mock(return_value=mock_post)))
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        reactions = await agent_social_layer.add_reaction(
            post_id="post-123",
            agent_id="agent-789",
            emoji="👍",
            db=mock_db
        )

        assert reactions["👍"] == 3


class TestTrendingTopics:
    """Test trending topics calculation."""

    @pytest.mark.asyncio
    async def test_trending_topics(self):
        """Trending topics are calculated from recent posts."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)

        # Mock posts with mentions
        mock_post1 = Mock()
        mock_post1.mentioned_agent_ids = ["agent-1", "agent-2"]
        mock_post1.mentioned_episode_ids = ["episode-1"]
        mock_post1.mentioned_task_ids = []

        mock_post2 = Mock()
        mock_post2.mentioned_agent_ids = ["agent-1"]
        mock_post2.mentioned_episode_ids = []
        mock_post2.mentioned_task_ids = ["task-1"]

        mock_query.all = Mock(return_value=[mock_post1, mock_post2])

        from datetime import timedelta
        from unittest.mock import patch
        with patch('core.agent_social_layer.timedelta') as mock_timedelta:
            mock_timedelta.return_value = timedelta(hours=24)

            mock_db.query = Mock(return_value=mock_query)

            trending = await agent_social_layer.get_trending_topics(
                hours=24,
                db=mock_db
            )

            # agent-1 mentioned twice (should be top)
            assert any(t["topic"] == "agent:agent-1" and t["mentions"] == 2 for t in trending)
```

Coverage targets:
- Maturity gates (INTERN can post, STUDENT blocked)
- Post type validation
- Feed pagination and filtering
- EventBus broadcasting
- Emoji reactions
- Trending topics calculation
  </action>
  <verify>
```bash
# Run tests
cd backend && pytest tests/test_agent_social_layer.py -v
# Should show 15+ tests passing
```
  </verify>
  <done>
Tests created for AgentSocialLayer:
- 3 tests for maturity gate (INTERN, STUDENT, SUPERVISED)
- 2 tests for post type validation
- 2 tests for feed pagination and filtering
- 2 tests for event bus integration
- 3 tests for reactions (add reaction, multiple reactions)
- 2 tests for trending topics
- Total: 14+ tests with comprehensive coverage
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. AgentPost model exists with post_type field (status/insight/question/alert)
2. AgentEventBus implements pub/sub with WebSocket support
3. AgentSocialLayer enforces INTERN+ gate for posting
4. Social API routes exposed (POST /posts, GET /feed, WebSocket)
5. Tests cover maturity gates, validation, broadcasting, reactions
6. WebSocket endpoint for real-time feed updates
7. Trending topics calculation works correctly
</verification>

<success_criteria>
- INTERN+ agents can post to social feed
- STUDENT agents are read-only (403 when trying to post)
- All agents can read feed (no maturity gate)
- Posts broadcast via WebSocket in real-time
- Feed supports pagination and filtering
- Emoji reactions work correctly
- Trending topics calculated from mentions
- Test coverage >80% for AgentSocialLayer
</success_criteria>

<output>
After completion, create `.planning/phases/13-openclaw-integration/13-openclaw-integration-02-SUMMARY.md` with:
- Files created/modified
- INTERN+ maturity gate implementation
- Post types (status, insight, question, alert)
- WebSocket broadcasting details
- Feed pagination and filtering
- Test coverage results
</output>
