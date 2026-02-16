---
phase: 03-social-layer
plan: 03
type: execute
wave: 2
depends_on: ["03-social-layer-01", "03-social-layer-02"]
files_modified:
  - backend/core/agent_social_layer.py
  - backend/api/social_routes.py
  - backend/core/agent_communication.py
  - backend/tests/test_social_feed_service.py
autonomous: true
user_setup:
  - service: redis
    why: "Optional Redis pub/sub for horizontal scaling (skip for MVP)"
    env_vars:
      - name: REDIS_URL
        source: "Redis server configuration (localhost:6379 or cloud)"

must_haves:
  truths:
    - "Users can reply to agent posts (feedback loop to agents)"
    - "Directed messaging works (Human → Agent, Agent → Human, Agent → Agent)"
    - "Channels/rooms supported for contextual conversations (project, support, engineering)"
    - "Redis pub/sub integration for horizontal scaling (optional for MVP)"
    - "Cursor-based pagination prevents duplicates in real-time feed"
    - "Full communication matrix: Human↔Agent, Agent↔Human, Agent↔Agent"
  artifacts:
    - path: "backend/core/agent_social_layer.py"
      provides: "Enhanced social layer with replies, channels, Redis"
      min_lines: 400
    - path: "backend/api/social_routes.py"
      provides: "New REST endpoints for replies and channels"
      min_lines: 250
    - path: "backend/core/agent_communication.py"
      provides: "Redis pub/sub integration for enterprise scaling"
      min_lines: 200
    - path: "backend/tests/test_social_feed_service.py"
      provides: "Test coverage for replies, channels, Redis, pagination"
      min_lines: 200
  key_links:
    - from: "backend/api/social_routes.py"
      to: "backend/core/agent_social_layer.py"
      via: "add_reply(), create_channel() methods"
      pattern: "add_reply\(|create_channel\("
    - from: "backend/core/agent_communication.py"
      to: "Redis"
      via: "redis.asyncio.pubsub"
      pattern: "redis\.publish\(|pubsub\.subscribe\("
---

<objective>
Implement full communication matrix enhancements for agent social layer (replies, channels, Redis pub/sub, cursor pagination).

**Purpose:** Enable complete Human ↔ Agent, Agent ↔ Human, Agent ↔ Agent communication with replies, channels, and horizontal scaling support via Redis Pub/Sub.

**Output:**
- Enhanced `agent_social_layer.py`: Reply threading, channel management, cursor pagination
- Enhanced `social_routes.py`: New endpoints for replies and channels
- Enhanced `agent_communication.py`: Redis pub/sub for horizontal scaling
- Test suite covering replies, channels, Redis, and pagination
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-social-layer/03-RESEARCH.md
@backend/core/agent_social_layer.py (existing AgentSocialLayer with create_post, get_feed)
@backend/api/social_routes.py (existing REST and WebSocket endpoints)
@backend/core/agent_communication.py (existing AgentEventBus with in-memory pub/sub)
@backend/core/models.py (AgentPost model with reply_count, channel_id fields)

**Existing Infrastructure (60% Complete from Plan 01-02):**
- AgentPost model supports replies (reply_to_id), channels (channel_id), directed messages (recipient_id, is_public)
- AgentSocialLayer with create_post(), get_feed() (offset-based pagination)
- AgentEventBus with in-memory WebSocket pub/sub
- WebSocket feed endpoint (/ws/feed)

**What This Plan Adds:**
- Reply threading (users reply to agent posts, agents respond to replies)
- Channel management (create, list, join/leave channels)
- Cursor-based pagination (prevents duplicates in real-time feed)
- Redis pub/sub integration (horizontal scaling for enterprise)
- Enhanced WebSocket with Redis fallback
- Trending topics by channel

**Key Decision:**
- Redis pub/sub is OPTIONAL for MVP (in-memory works for <100 agents)
- Redis required for enterprise scale (multiple Atom instances behind load balancer)
- Use environment variable `REDIS_URL` to enable/disable

**Reference:** Research docs 03-RESEARCH.md Pattern 4 (Cursor Pagination), Pattern 5 (Redis Pub/Sub)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Enhance AgentSocialLayer with replies, channels, and cursor pagination</name>
  <files>backend/core/agent_social_layer.py</files>
  <action>
Update `backend/core/agent_social_layer.py` to add:

1. **Reply threading** (add to AgentSocialLayer class):
   ```python
   async def add_reply(
       self,
       post_id: str,
       sender_type: str,
       sender_id: str,
       sender_name: str,
       content: str,
       sender_maturity: Optional[str] = None,
       sender_category: Optional[str] = None,
       db: Session = None
   ) -> Dict[str, Any]:
       """
       Add reply to post (feedback loop to agents).

       Users can reply to agent posts. Agents can respond to replies.
       Creates new post with reply_to_id set.

       Returns:
           Created reply post data
       """
       if not db:
           raise ValueError("Database session required")

       parent_post = db.query(AgentPost).filter(AgentPost.id == post_id).first()
       if not parent_post:
           raise ValueError(f"Post {post_id} not found")

       # Create reply post
       reply = await self.create_post(
           sender_type=sender_type,
           sender_id=sender_id,
           sender_name=sender_name,
           post_type="response",
           content=content,
           sender_maturity=sender_maturity,
           sender_category=sender_category,
           db=db
       )

       # Link to parent post
       parent_post.reply_count += 1
       db.commit()

       # Store reply relationship (add to AgentPost model or use junction table)
       # For now, use agent_social_layer.replies tracking

       return reply
   ```

2. **Cursor-based pagination** (replace offset-based in get_feed):
   ```python
   async def get_feed_cursor(
       self,
       sender_id: str,
       cursor: Optional[str] = None,  # ISO timestamp string
       limit: int = 50,
       post_type: Optional[str] = None,
       sender_filter: Optional[str] = None,
       channel_id: Optional[str] = None,
       is_public: Optional[bool] = None,
       db: Session = None
   ) -> Dict[str, Any]:
       """
       Get feed with cursor-based pagination.

       Args:
           cursor: ISO timestamp of last post (get posts before this time)
           limit: Max posts to return

       Returns:
           Feed with next_cursor for pagination
       """
       if not db:
           return {"posts": [], "next_cursor": None, "has_more": False}

       query = db.query(AgentPost)

       # Apply filters (same as before)
       if post_type:
           query = query.filter(AgentPost.post_type == post_type)
       if sender_filter:
           query = query.filter(AgentPost.sender_id == sender_filter)
       if channel_id:
           query = query.filter(AgentPost.channel_id == channel_id)
       if is_public is not None:
           query = query.filter(AgentPost.is_public == is_public)

       # Apply cursor (get posts before this timestamp)
       if cursor:
           try:
               cursor_time = datetime.fromisoformat(cursor)
               query = query.filter(AgentPost.created_at < cursor_time)
           except ValueError:
               logger.warning(f"Invalid cursor format: {cursor}")

       # Order by created_at DESC
       query = query.order_by(desc(AgentPost.created_at))

       # Fetch one extra to check has_more
       posts = query.limit(limit + 1).all()
       has_more = len(posts) > limit
       posts = posts[:limit]

       # Generate next cursor (last post's created_at)
       next_cursor = None
       if posts and has_more:
           next_cursor = posts[-1].created_at.isoformat()

       return {
           "posts": [
               {
                   "id": p.id,
                   # ... same serialization as before ...
                   "created_at": p.created_at.isoformat()
               }
               for p in posts
           ],
           "next_cursor": next_cursor,
           "has_more": has_more
       }
   ```

3. **Channel management**:
   ```python
   async def create_channel(
       self,
       channel_id: str,
       channel_name: str,
       creator_id: str,
       description: Optional[str] = None,
       db: Session = None
   ) -> Dict[str, Any]:
       """
       Create new channel for contextual conversations.

       Channels: project, support, engineering, general
       """
       if not db:
           raise ValueError("Database session required")

       # Check if channel exists
       existing = db.query(Channel).filter(Channel.id == channel_id).first()
       if existing:
           return {"id": existing.id, "name": existing.name, "exists": True}

       channel = Channel(
           id=channel_id,
           name=channel_name,
           description=description,
           created_by=creator_id,
           created_at=datetime.utcnow()
       )
       db.add(channel)
       db.commit()

       await agent_event_bus.publish({
           "type": "channel_created",
           "channel_id": channel_id,
           "channel_name": channel_name
       }, ["global"])

       return {"id": channel.id, "name": channel.name, "created": True}

   async def get_channels(self, db: Session = None) -> List[Dict[str, Any]]:
       """Get all available channels."""
       if not db:
           return []

       channels = db.query(Channel).all()
       return [
           {"id": c.id, "name": c.name, "description": c.description}
           for c in channels
       ]
   ```

4. **Get replies for post**:
   ```python
   async def get_replies(
       self,
       post_id: str,
       limit: int = 50,
       db: Session = None
   ) -> Dict[str, Any]:
       """
       Get all replies to a post.

       Returns posts sorted by created_at ASC (conversation order).
       """
       if not db:
           return {"replies": []}

       # Query posts that reply to this post
       # Note: Need to add reply_to_id column to AgentPost model
       replies = db.query(AgentPost).filter(
           AgentPost.reply_to_id == post_id
       ).order_by(AgentPost.created_at).limit(limit).all()

       return {
           "replies": [
               {
                   "id": r.id,
                   "sender_type": r.sender_type,
                   "sender_id": r.sender_id,
                   "sender_name": r.sender_name,
                   "content": r.content,
                   "created_at": r.created_at.isoformat()
               }
               for r in replies
           ],
           "total": len(replies)
       }
   ```

5. **Database migration** (add reply_to_id to AgentPost):
   ```python
   # Add to AgentPost model in models.py:
   reply_to_id = Column(String, ForeignKey("agent_posts.id"), nullable=True)
   reply_to = relationship("AgentPost", remote_side=[id], backref="replies")
   ```

**DO NOT:**
- Remove existing offset-based pagination (keep for backward compatibility)
- Allow replies to private directed messages (security risk)
- Create channels without creator_id (audit requirement)

**Reference:** Research docs 03-RESEARCH.md Pattern 4 (Cursor-Based Pagination)
  </action>
  <verify>
grep -n "get_feed_cursor\|add_reply\|create_channel" /Users/rushiparikh/projects/atom/backend/core/agent_social_layer.py
  </verify>
  <done>
AgentSocialLayer has get_feed_cursor(), add_reply(), create_channel(), get_replies(), and get_channels() methods.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add REST API endpoints for replies and channels</name>
  <files>backend/api/social_routes.py</files>
  <action>
Update `backend/api/social_routes.py` to add new endpoints:

1. **Reply endpoints**:
   ```python
   class CreateReplyRequest(BaseModel):
       sender_type: str  # "agent" or "human"
       sender_id: str
       sender_name: str
       content: str
       sender_maturity: Optional[str] = None
       sender_category: Optional[str] = None

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
       """Get all replies to a post."""
       result = await agent_social_layer.get_replies(
           post_id=post_id,
           limit=limit,
           db=db
       )
       return result
   ```

2. **Channel endpoints**:
   ```python
   class CreateChannelRequest(BaseModel):
       channel_id: str
       channel_name: str
       creator_id: str
       description: Optional[str] = None

   @router.post("/channels")
   async def create_channel(
       request: CreateChannelRequest,
       db: Session = Depends(get_db)
   ):
       """
       Create new channel for contextual conversations.

       Channels: project, support, engineering, general
       """
       try:
           channel = await agent_social_layer.create_channel(
               channel_id=request.channel_id,
               channel_name=request.channel_name,
               creator_id=request.creator_id,
               description=request.description,
               db=db
           )
           return {"success": True, "channel": channel}
       except ValueError as e:
           raise HTTPException(status_code=400, detail=str(e))

   @router.get("/channels")
   async def get_channels(
       db: Session = Depends(get_db)
   ):
       """Get all available channels."""
       channels = await agent_social_layer.get_channels(db=db)
       return {"channels": channels}
   ```

3. **Cursor-based feed endpoint** (new, alongside existing /feed):
   ```python
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

       Returns:
           Feed with posts, next_cursor, has_more
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
   ```

4. **Update OpenAPI tags**:
   ```python
   router = APIRouter(prefix="/api/social", tags=["Social"])

   # Add new tags for organization
   tags_metadata = [
       {"name": "Social", "description": "Agent social feed and communication"},
       {"name": "Social Replies", "description": "Reply threading for posts"},
       {"name": "Social Channels", "description": "Channel management"}
   ]
   ```

5. **Enhanced WebSocket endpoint** (support channel subscriptions):
   ```python
   @router.websocket("/ws/feed")
   async def websocket_feed_endpoint(
       websocket: WebSocket,
       sender_id: str,
       topics: List[str] = Query(["global"]),
       channels: List[str] = Query([])  # NEW: Channel subscriptions
   ):
       """
       WebSocket endpoint for real-time feed updates.

       NEW: Subscribe to specific channels for contextual posts.

       Topics:
       - global: All feed updates
       - sender:{id}: Updates from specific sender
       - channel:{id}: Channel-specific posts
       - alerts: Alert posts only

       Usage:
       ```
       ws://localhost:8000/api/social/ws/feed?sender_id=agent-123&topics=global&channels=engineering
       ```
       """
       await websocket.accept()

       # Subscribe to event bus with channels
       all_topics = topics + [f"channel:{ch}" for ch in channels]
       await agent_event_bus.subscribe(sender_id, websocket, all_topics)

       try:
           while True:
               data = await websocket.receive_text()
               if data == "ping":
                   await websocket.send_text("pong")
       except WebSocketDisconnect:
           await agent_event_bus.unsubscribe(sender_id, websocket)
   ```

**DO NOT:**
- Remove existing offset-based /feed endpoint (backward compatibility)
- Allow creating channels without authentication (add auth middleware)
- Allow WebSocket connections without sender_id validation

**Reference:** Research docs 03-RESEARCH.md Pattern 4 (Cursor-Based Pagination)
  </action>
  <verify>
grep -n "replies\|channels\|feed/cursor" /Users/rushiparikh/projects/atom/backend/api/social_routes.py
  </verify>
  <done>
New endpoints added: /posts/{id}/replies (POST, GET), /channels (POST, GET), /feed/cursor (GET). WebSocket enhanced with channel subscriptions.
  </done>
</task>

<task type="auto">
  <name>Task 3: Integrate Redis pub/sub for horizontal scaling</name>
  <files>backend/core/agent_communication.py</files>
  <action>
Update `backend/core/agent_communication.py` to add Redis pub/sub:

1. **Redis integration** (optional, enabled via REDIS_URL):
   ```python
   import os
   from typing import Optional
   import asyncio

   try:
       import redis.asyncio as redis
       REDIS_AVAILABLE = True
   except ImportError:
       REDIS_AVAILABLE = False

   class AgentEventBus:
       """
       Event bus for agent communication.

       MVP: In-memory WebSocket connections (<100 agents)
       Enterprise: Redis Pub/Sub for horizontal scaling
       """

       def __init__(self, redis_url: Optional[str] = None):
           # Existing in-memory subscribers
           self._subscribers: Dict[str, Set[Any]] = {}
           self._topics: Dict[str, Set[str]] = {"global": set()}

           # NEW: Redis pub/sub for horizontal scaling
           self._redis_url = redis_url or os.getenv("REDIS_URL")
           self._redis: Optional[redis.Redis] = None
           self._pubsub: Optional = None
           self._redis_enabled = bool(self._redis_url) and REDIS_AVAILABLE

       async def _ensure_redis(self):
           """Initialize Redis connection if not already connected."""
           if self._redis_enabled and not self._redis:
               try:
                   self._redis = await redis.from_url(
                       self._redis_url,
                       encoding="utf-8",
                       decode_responses=True
                   )
                   self._pubsub = self._redis.pubsub()
                   logger.info(f"Redis pub/sub enabled: {self._redis_url}")
               except Exception as e:
                   logger.warning(f"Redis connection failed, using in-memory only: {e}")
                   self._redis_enabled = False
       ```

2. **Redis publish** (enhance publish method):
   ```python
   async def publish(self, event: Dict[str, Any], topics: List[str] = None):
       """
       Publish event to subscribers.

       Enhanced: Also publishes to Redis for horizontal scaling.
       """
       topics = topics or ["global"]

       # NEW: Publish to Redis (if enabled)
       if self._redis_enabled:
           await self._ensure_redis()
           if self._redis:
               try:
                   event_json = json.dumps({"topics": topics, "event": event})
                   for topic in topics:
                       await self._redis.publish(f"agent_events:{topic}", event_json)
                       logger.debug(f"Published to Redis topic: agent_events:{topic}")
               except Exception as e:
                   logger.warning(f"Redis publish failed: {e}")

       # Existing in-memory publish
       subscriber_ids = set()
       for topic in topics:
           if topic in self._topics:
               subscriber_ids.update(self._topics[topic])

       for agent_id in subscriber_ids:
           if agent_id in self._subscribers:
               for websocket in self._subscribers[agent_id]:
                   try:
                       await websocket.send_json(event)
                   except Exception as e:
                       logger.warning(f"Failed to send to agent {agent_id}: {e}")
                       await self.unsubscribe(agent_id, websocket)
   ```

3. **Redis subscribe** (for multi-instance support):
   ```python
   async def subscribe_to_redis(self):
       """
       Subscribe to Redis pub/sub for cross-instance events.

       Call this on startup if REDIS_URL is configured.
       Background task listens for Redis messages and broadcasts locally.
       """
       if not self._redis_enabled:
           return

       await self._ensure_redis()
       if not self._pubsub:
           return

       # Subscribe to all agent event topics
       await self._pubsub.subscribe("agent_events:global")
       await self._pubsub.subscribe("agent_events:alerts")

       async def redis_listener():
           """Background task: Listen for Redis messages and broadcast locally."""
           async for message in self._pubsub.listen():
               if message['type'] == 'message':
                   try:
                       data = json.loads(message['data'])
                       event = data['event']
                       topics = data['topics']

                       # Broadcast to local WebSocket subscribers
                       await self.publish(event, topics)
                   except Exception as e:
                       logger.warning(f"Redis message processing failed: {e}")

       # Start background task
       asyncio.create_task(redis_listener())
       logger.info("Redis pub/sub listener started")
   ```

4. **Environment configuration**:
   ```python
   # Get Redis URL from environment
   REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
   REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
   ```

5. **Startup hook** (call subscribe_to_redis on app startup):
   ```python
   @app.on_event("startup")
   async def startup_event():
       """Initialize Redis pub/sub on startup."""
       if os.getenv("REDIS_ENABLED", "false").lower() == "true":
           await agent_event_bus.subscribe_to_redis()
   ```

6. **Graceful shutdown**:
   ```python
   async def close_redis(self):
       """Close Redis connection."""
       if self._pubsub:
           await self._pubsub.close()
       if self._redis:
           await self._redis.close()
           logger.info("Redis connection closed")

   # Call on app shutdown
   @app.on_event("shutdown")
   async def shutdown_event():
       """Cleanup on shutdown."""
       await agent_event_bus.close_redis()
   ```

**DO NOT:**
- Require Redis for MVP (optional via REDIS_URL)
- Block WebSocket if Redis fails (fallback to in-memory)
- Create Redis connection if not configured (check env var)

**Reference:** Research docs 03-RESEARCH.md Pattern 5 (Redis Pub/Sub for Horizontal Scaling)
  </action>
  <verify>
grep -n "redis\|Redis" /Users/rushiparikh/projects/atom/backend/core/agent_communication.py | head -20
  </verify>
  <done>
AgentEventBus has Redis pub/sub integration (optional), subscribe_to_redis() method, and graceful shutdown.
  </done>
</task>

<task type="auto">
  <name>Task 4: Create comprehensive test suite for replies, channels, and Redis</name>
  <files>backend/tests/test_social_feed_service.py</files>
  <action>
Create `backend/tests/test_social_feed_service.py` with 20+ tests:

1. **Reply threading tests** (6 tests):
   - `test_add_reply_to_post()`: User replies to agent post
   - `test_agent_responds_to_reply()`: Agent responds to user reply
   - `test_reply increments_reply_count()`: Parent post reply_count updated
   - `test_get_replies_for_post()`: Retrieve all replies sorted ASC
   - `test_student_agent_cannot_reply()`: STUDENT maturity blocked
   - `test_reply_broadcast_via_websocket()`: Reply event broadcast

2. **Channel management tests** (5 tests):
   - `test_create_channel()`: New channel created successfully
   - `test_duplicate_channel_returns_existing()`: Idempotent channel creation
   - `test_get_channels()`: List all channels
   - `test_post_to_channel()`: Post with channel_id filtered correctly
   - `test_channel_posts_filtered_in_feed()`: get_feed() filters by channel

3. **Cursor pagination tests** (5 tests):
   - `test_cursor_pagination_first_page()`: Initial request returns next_cursor
   - `test_cursor_pagination_second_page()`: Using cursor returns older posts
   - `test_cursor_no_duplicates_when_new_posts_arrive()': Stability during real-time updates
   - `test_cursor_empty_returns_false()`: No posts returns has_more=false
   - `test_cursor_invalid_format_handled()`: Bad cursor format logged, returns feed

4. **Redis pub/sub tests** (4 tests):
   - `test_redis_publish()`: Event published to Redis channel
   - `test_redis_subscribe_broadcasts_locally()`: Redis message triggers local broadcast
   - `test_redis_fallback_to_in_memory()`: Redis unavailable → in-memory only
   - `test_redis_graceful_shutdown()`: Connection closed on shutdown

5. **Integration tests** (3 tests):
   - `test_full_reply_thread_with_redaction()`: Reply → PII redaction → broadcast
   - `test_channel_conversation_isolated()`: Posts in channel not visible in global feed
   - `test_cursor_pagination_with_channels()`: Cursor works with channel filter

**Test patterns:**
- Use `pytest-asyncio` for async tests
- Mock Redis with `fakeredis` library (if available) or mock `redis.asyncio`
- Use `factory_boy` for test data
- Clean up database in `finally` blocks
- Test both Redis enabled and disabled scenarios

**Dependencies**:
```
fakeredis>=2.0.0  # Redis mocking for tests
```

**Reference:** Research docs 03-RESEARCH.md Code Examples (Redis Pub/Sub, Cursor Pagination)
  </action>
  <verify>
cd /Users/rushiparikh/projects/atom/backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_social_feed_service.py -v --tb=short
  </verify>
  <done>
20+ tests pass, coverage >80% for enhanced agent_social_layer.py and agent_communication.py.
  </done>
</task>

</tasks>

<verification>
**Overall Phase Checks:**
1. Run test suite: `pytest tests/test_social_feed_service.py tests/test_agent_social_layer.py -v`
2. Test reply flow: Create post → add_reply() → verify reply_count incremented
3. Test cursor pagination: Create 100 posts, fetch with cursor=last_post_timestamp, verify no duplicates
4. Test channels: Create channel → post to channel → verify filtered in get_feed(channel_id=...)
5. Test Redis (optional): Set REDIS_URL=localhost:6379, verify pub/sub works across instances

**Quality Metrics:**
- Test coverage >80% for enhanced files
- All 20+ tests pass
- Cursor pagination prevents duplicates (verified with concurrent post creation)
- Redis pub/sub works (if REDIS_URL configured)
</verification>

<success_criteria>
1. **Reply Threading**: Users can reply to agent posts, agents can respond to replies
2. **Reply Count**: Parent post reply_count incremented correctly
3. **Channel Management**: Create/list channels, post to channels, filter feed by channel
4. **Cursor Pagination**: Feed uses cursor-based pagination (no duplicates when new posts arrive)
5. **Redis Pub/Sub**: Optional Redis integration for horizontal scaling (multi-instance deployments)
6. **Backward Compatibility**: Existing offset-based /feed endpoint still works
7. **WebSocket Channels**: WebSocket supports channel subscriptions
8. **Test Coverage**: 20+ tests covering replies, channels, cursor pagination, and Redis
9. **Full Communication Matrix**: Human↔Agent, Agent↔Human, Agent↔Agent all supported
</success_criteria>

<output>
After completion, create `.planning/phases/03-social-layer/03-social-layer-03-SUMMARY.md` with:
- Reply threading flow documentation
- Channel management configuration
- Redis pub/sub setup instructions
- Cursor pagination migration guide
- Test coverage metrics
</output>
