---
phase: 13-openclaw-integration
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/models.py
  - backend/core/agent_social_layer.py
  - backend/core/agent_communication.py
  - backend/api/social_routes.py
  - backend/tests/test_agent_social_layer.py
autonomous: true

must_haves:
  truths:
    - Agents can post natural language status updates to feed
    - Agents can read activity feed from all agents
    - Posts are typed (status, insight, question, alert)
    - INTERN+ agents can post, STUDENT agents are read-only
    - Posts trigger WebSocket broadcasts to subscribers
    - Question and alert posts notify relevant agents
    - Activity feed is paginated and ordered by recency
    - Posts include agent context (maturity, category, name)
  artifacts:
    - path: backend/core/models.py
      provides: AgentPost database model for social feed
      contains: "class AgentPost"
    - path: backend/core/agent_social_layer.py
      provides: Social feed service for agent-to-agent communication
      min_lines: 250
      exports: ["AgentSocialLayer", "post_status_update", "get_activity_feed"]
    - path: backend/core/agent_communication.py
      provides: Event-driven agent communication event bus
      min_lines: 150
      exports: ["AgentEventBus", "publish", "subscribe"]
    - path: backend/api/social_routes.py
      provides: REST API endpoints for social layer
      exports: ["POST /api/social/post", "GET /api/social/feed"]
  key_links:
    - from: backend/core/agent_social_layer.py
      to: backend/core/governance_cache.py
      via: Governance check before posting
      pattern: "can_perform_action.*social_post"
    - from: backend/core/agent_social_layer.py
      to: backend/core/agent_communication.py
      via: Event bus for broadcasting posts
      pattern: "AgentEventBus\(\)"
    - from: backend/api/social_routes.py
      to: backend/core/agent_social_layer.py
      via: Service instantiation
      pattern: "AgentSocialLayer\(db\)"
    - from: backend/core/agent_social_layer.py
      to: backend/api/websocket_routes.py
      via: WebSocket broadcast for real-time updates
      pattern: "websocket_manager.broadcast"
---

<objective>
Implement Agent Social Layer (Agent Feed/Watercooler)

Create an event-driven social feed for agent-to-agent communication with natural language status updates, typed posts (status/insight/question/alert), and real-time WebSocket broadcasting.

Purpose: Enable agents to share insights, ask questions, broadcast alerts, and collaborate through a Twitter-like activity feed while maintaining governance controls (INTERN+ required to post).

Output: AgentSocialLayer service, AgentEventBus for event-driven communication, social API endpoints, AgentPost model, and comprehensive test coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/13-openclaw-integration/13-RESEARCH.md

# Event-Driven Architecture Patterns
@backend/core/agent_governance_service.py  # Service pattern reference
@backend/api/agent_governance_routes.py    # API pattern reference
@backend/api/websocket_routes.py           # WebSocket manager for broadcasting
@backend/core/base_routes.py               # BaseAPIRouter pattern
@backend/core/models.py                    # Database model patterns
@backend/core/feedback_service.py          # Social-like service pattern reference
</context>

<tasks>

<task type="auto">
  <name>Create AgentPost database model for social feed</name>
  <files>backend/core/models.py</files>
  <action>
    Add AgentPost model to backend/core/models.py:

    1. Create new model after AgentFeedback (around line 650):
       class AgentPost(Base):
           __tablename__ = "agent_posts"

           # Primary fields
           id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
           agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
           content = Column(Text, nullable=False)  # Natural language post

           # Post metadata
           post_type = Column(String, nullable=False)  # status, insight, question, alert
           context = Column(JSON, nullable=True)  # Additional structured data

           # Engagement
           reactions = Column(JSON, default={})  # {"like": 3, "helpful": 5, "question": 1}
           replies = Column(JSON, default=list)  # List of reply post IDs

           # Targeting (for questions/alerts)
           target_agent_categories = Column(JSON, default=list)  # ["finance", "sales"]
           target_agent_ids = Column(JSON, default=list)  # Specific agent IDs

           # Timestamps
           created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
           updated_at = Column(DateTime(timezone=True), onupdate=func.now())

           # Soft delete
           deleted_at = Column(DateTime(timezone=True), nullable=True)

    2. Add relationship to AgentRegistry:
       - posts = relationship("AgentPost", backref="agent")

    3. Add indexes on:
       - agent_id
       - post_type
       - created_at (for timeline ordering)

    4. Include __repr__ method:
       def __repr__(self):
           return f"<AgentPost(id={self.id}, agent_id={self.agent_id}, type={self.post_type})>"

    DO NOT modify existing models or migrations
  </action>
  <verify>grep -n "class AgentPost" backend/core/models.py returns the model definition</verify>
  <done>AgentPost model exists with content, post_type, engagement fields, and proper indexes</done>
</task>

<task type="auto">
  <name>Implement AgentEventBus for event-driven communication</name>
  <files>backend/core/agent_communication.py</files>
  <action>
    Create backend/core/agent_communication.py with:

    1. AgentEventBus class:
       - Singleton pattern with _instance class variable
       - __init__ creates _subscribers: Dict[str, List[Callable]]

    2. async publish(event_type: str, data: Dict[str, Any]) -> None:
       - Get subscribers for event_type
       - Create tasks for each subscriber callback
       - Execute with asyncio.gather() for parallel execution
       - Log event publication

    3. subscribe(event_type: str, callback: Callable) -> None:
       - Add callback to event_type subscribers list
       - Create list if doesn't exist
       - Return callback ID for unsubscribing

    4. unsubscribe(event_type: str, callback_id: str) -> None:
       - Remove callback from subscribers

    5. get_event_types() -> List[str]:
       - Return all registered event types

    6. Event type constants:
       - AGENT_POST_CREATED = "agent.post.created"
       - AGENT_POST_REACTED = "agent.post.reacted"
       - AGENT_QUESTION_ASKED = "agent.question.asked"
       - AGENT_ALERT_BROADCAST = "agent.alert.broadcast"
       - AGENT_STATUS_CHANGED = "agent.status.changed"

    7. Instance getter:
       def get_agent_event_bus() -> AgentEventBus:
           if AgentEventBus._instance is None:
               AgentEventBus._instance = AgentEventBus()
           return AgentEventBus._instance

    Import:
    - from typing import Dict, List, Callable, Any, Optional
    - import asyncio, logging, uuid
  </action>
  <verify>grep -n "class AgentEventBus\|async publish\|def subscribe" backend/core/agent_communication.py returns method definitions</verify>
  <done>AgentEventBus provides publish/subscribe for agent communication events</done>
</task>

<task type="auto">
  <name>Implement AgentSocialLayer service for feed management</name>
  <files>backend/core/agent_social_layer.py</files>
  <action>
    Create backend/core/agent_social_layer.py with:

    1. AgentSocialLayer class:
       - __init__(self, db: Session)
       - Import AgentPost, AgentRegistry from models
       - Use get_logger(__name__)
       - Type hints throughout

    2. async post_status_update(
           self, agent_id: str, content: str,
           post_type: str = "status",
           context: Optional[Dict] = None,
           target_categories: Optional[List[str]] = None,
           target_agent_ids: Optional[List[str]] = None
       ) -> AgentPost:
       - Governance check: can_perform_action(agent_id, "social_post")
       - INTERN+ maturity required (STUDENT blocked)
       - Validate post_type against allowed types
       - Validate content length (1-5000 chars)
       - Create AgentPost record
       - Add to database and commit
       - Broadcast via AgentEventBus (AGENT_POST_CREATED)
       - For question/alert types, trigger notification of relevant agents
       - Log post creation
       - Return created post

    3. get_activity_feed(
           self, agent_id: Optional[str] = None,
           post_type: Optional[str] = None,
           limit: int = 50,
           offset: int = 0,
           include_deleted: bool = False
       ) -> List[Dict[str, Any]]:
       - Query AgentPost with eager loading of agent relationship
       - Filter by agent_id if provided
       - Filter by post_type if provided
       - Filter out deleted unless include_deleted=True
       - Order by created_at DESC
       - Apply pagination (limit, offset)
       - Convert to dict format with agent context (name, category, maturity)
       - Return list

    4. async react_to_post(
           self, post_id: str, agent_id: str,
           reaction: str  # "like", "helpful", "question"
       ) -> AgentPost:
       - Get post by ID
       - Update reactions dict (increment counter)
       - Save to database
       - Broadcast AGENT_POST_REACTED event
       - Return updated post

    5. add_reply(self, post_id: str, reply_post_id: str) -> AgentPost:
       - Get parent post
       - Add reply_post_id to replies list
       - Save and return

    6. delete_post(self, post_id: str, agent_id: str) -> bool:
       - Get post and verify agent_id matches
       - Set deleted_at timestamp (soft delete)
       - Return True

    7. get_trending_topics(self, limit: int = 10) -> List[Dict[str, str]]:
       - Analyze recent posts (last 24h)
       - Extract hashtags/keywords from content
       - Count frequency
       - Return top trending topics

    Import patterns:
    - from core.models import AgentPost, AgentRegistry
    - from core.governance_cache import get_governance_cache
    - from core.agent_communication import get_agent_event_bus
    - from sqlalchemy.orm import Session, joinedload
    - from datetime import datetime, timedelta
  </action>
  <verify>grep -n "class AgentSocialLayer\|post_status_update\|get_activity_feed" backend/core/agent_social_layer.py returns method definitions</verify>
  <done>AgentSocialLayer manages posts, feed, reactions, and trends with governance enforcement</done>
</task>

<task type="auto">
  <name>Create social layer API routes</name>
  <files>backend/api/social_routes.py</files>
  <action>
    Create backend/api/social_routes.py with:

    1. Imports following existing patterns:
       - from core.base_routes import BaseAPIRouter
       - from core.database import get_db
       - from core.agent_social_layer import AgentSocialLayer
       - from pydantic import BaseModel

    2. Request models:
       - CreatePostRequest(content: str, post_type: str, context: Optional[Dict])
       - ReactRequest(reaction: str)
       - FeedQueryParams(agent_id: Optional[str], post_type: Optional[str], limit: int, offset: int)

    3. Response models:
       - PostResponse(id, agent_id, content, post_type, created_at, agent_context)
       - FeedResponse(posts: List[PostResponse], total: int, has_more: bool)

    4. router = BaseAPIRouter(prefix="/api/social", tags=["Social"])

    5. POST /api/social/post:
       - Accept CreatePostRequest with agent_id
       - Call post_status_update()
       - Return router.success_response(data=post_dict)

    6. GET /api/social/feed:
       - Query params: agent_id, post_type, limit, offset
       - Call get_activity_feed()
       - Return router.success_list_response(data=posts, total=count, has_more=has_more)

    7. POST /api/social/post/{post_id}/react:
       - Accept ReactRequest
       - Call react_to_post()
       - Return updated post

    8. GET /api/social/trending:
       - Call get_trending_topics()
       - Return trending topics list

    9. DELETE /api/social/post/{post_id}:
       - Verify agent ownership
       - Call delete_post()
       - Return success response

    Follow error handling from agent_governance_routes.py
    Use router.permission_denied_error() for governance failures
  </action>
  <verify>grep -n "router = BaseAPIRouter\|POST\|GET" backend/api/social_routes.py returns route definitions</verify>
  <done>Social API endpoints exist for posts, feed, reactions, and trending topics</done>
</task>

<task type="auto">
  <name>Write comprehensive tests for AgentSocialLayer</name>
  <files>backend/tests/test_agent_social_layer.py</files>
  <action>
    Create backend/tests/test_agent_social_layer.py with:

    1. Test class structure:
       import pytest
       from unittest.mock import Mock, AsyncMock, patch
       from sqlalchemy.orm import Session
       from core.agent_social_layer import AgentSocialLayer
       from core.models import AgentPost, AgentRegistry

    2. Test fixtures:
       - db_session (in-memory SQLite)
       - mock_agent_autonomous (maturity="autonomous")
       - mock_agent_intern (maturity="intern")
       - mock_agent_student (maturity="student")
       - social_layer (AgentSocialLayer instance)

    3. Test post creation:
       - test_autonomous_agent_can_post_status()
       - test_intern_agent_can_post_insight()
       - test_student_agent_cannot_post_raises_error()
       - test_post_validation_content_length()
       - test_post_type_validation()
       - test_post_saves_to_database()
       - test_post_broadcasts_event()

    4. Test feed retrieval:
       - test_get_feed_returns_posts_ordered_by_recency()
       - test_feed_filter_by_agent_id()
       - test_feed_filter_by_post_type()
       - test_feed_pagination_limit_offset()
       - test_feed_excludes_deleted_posts_by_default()
       - test_feed_includes_agent_context()

    5. Test reactions:
       - test_add_reaction_increments_counter()
       - test_multiple_reactions_count_correctly()
       - test_reaction_broadcasts_event()

    6. Test replies:
       - test_add_reply_to_post()
       - test_replies_list_accumulates()

    7. Test deletion:
       - test_soft_delete_sets_deleted_at()
       - test_only_author_can_delete_post()

    8. Test trending:
       - test_trending_extracts_hashtags()
       - test_trending_orders_by_frequency()

    Use AsyncMock for async operations
    Use pytest.mark.asyncio for async tests
    Mock governance_cache for permission checks
  </action>
  <verify>pytest backend/tests/test_agent_social_layer.py -v returns passing tests</verify>
  <done>Comprehensive tests cover posting, feed retrieval, reactions, replies, deletion, and trending</done>
</task>

</tasks>

<verification>
1. Governance Integration:
   - INTERN+ agents can post status updates
   - STUDENT agents are read-only (cannot post)
   - Governance check uses existing can_perform_action pattern

2. Post Types:
   - status: General status updates
   - insight: Sharing learnings/discoveries
   - question: Asking for help (triggers notifications)
   - alert: Broadcasting important information

3. Event-Driven Architecture:
   - AgentEventBus provides pub/sub for agent communication
   - Post creation broadcasts AGENT_POST_CREATED event
   - Reactions broadcast AGENT_POST_REACTED event
   - Questions trigger AGENT_QUESTION_ASKED event

4. Feed Functionality:
   - Paginated feed ordered by recency
   - Filter by agent_id, post_type
   - Include agent context (name, category, maturity)
   - Soft delete support (deleted_at)

5. Engagement:
   - Reactions: like, helpful, question
   - Reply threading via reply post IDs
   - Trending topics from hashtag/keyword extraction

6. API Contract:
   - POST /api/social/post creates post
   - GET /api/social/feed retrieves paginated feed
   - POST /api/social/post/{id}/react adds reaction
   - DELETE /api/social/post/{id} soft deletes
   - GET /api/social/trending returns trending topics

7. Test Coverage:
   - Governance tests (INTERN+ can post, STUDENT cannot)
   - Post validation tests (content length, type)
   - Feed retrieval tests (filters, pagination, ordering)
   - Engagement tests (reactions, replies)
   - Trending analysis tests
</verification>

<success_criteria>
1. Agents can post natural language updates to social feed
2. INTERN+ maturity required to post, STUDENT read-only
3. Four post types work (status, insight, question, alert)
4. Activity feed is paginated and filterable
5. Questions and alerts trigger relevant agent notifications
6. AgentEventBus provides pub/sub for real-time updates
7. Reactions and replies enable engagement
8. Trending topics extracted from recent posts
9. Comprehensive tests validate all functionality
</success_criteria>

<output>
After completion, create `.planning/phases/13-openclaw-integration/13-openclaw-integration-02-SUMMARY.md` with:
- Implemented AgentPost model with social feed fields
- AgentSocialLayer service with governance-enforced posting
- AgentEventBus for event-driven communication
- Social API routes with BaseAPIRouter patterns
- Comprehensive test coverage for social functionality

Include code snippets for:
- Post creation with governance check
- Event bus pub/sub pattern
- Feed retrieval with eager loading
- API endpoint examples
</output>
