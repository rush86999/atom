---
phase: 18-social-layer-testing
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/test_agent_communication.py
  - backend/tests/test_social_feed_integration.py
autonomous: true

must_haves:
  truths:
    - "Agent-to-agent messaging delivers messages with FIFO ordering guarantee"
    - "No messages are lost during pub/sub broadcasting (Redis or in-memory)"
    - "Feed generation is chronological (newest first) and filterable by post_type, sender, channel"
    - "Cursor pagination never returns duplicate posts even when new posts arrive during pagination"
    - "Redis pub/sub integration enables horizontal scaling for multi-instance deployments"
    - "WebSocket subscriptions receive real-time updates for subscribed topics"
    - "Channel isolation: posts in channels only visible to channel subscribers"
    - "Property tests verify: no duplicates, FIFO ordering, no lost messages, feed stability"
  artifacts:
    - path: "backend/tests/test_agent_communication.py"
      provides: "Agent-to-agent messaging and pub/sub tests with Redis integration"
      min_lines: 400
      exports: ["TestAgentEventBus", "TestWebSocketBroadcast", "TestRedisPubSub", "TestMessageOrdering"]
    - path: "backend/tests/test_social_feed_integration.py"
      provides: "Integration tests for feed generation, pagination, and filtering"
      min_lines: 500
      exports: ["TestFeedGeneration", "TestFeedPagination", "TestChannelIsolation", "TestRealTimeUpdates"]
  key_links:
    - from: "backend/tests/test_agent_communication.py"
      to: "backend/core/agent_communication.py"
      via: "imports AgentEventBus, agent_event_bus"
    - from: "backend/tests/test_social_feed_integration.py"
      to: "backend/core/agent_social_layer.py"
      via: "imports agent_social_layer"
    - from: "backend/core/agent_communication.py"
      to: "backend/core/agent_social_layer.py"
      via: "broadcast_post() for WebSocket updates"
    - from: "backend/core/agent_social_layer.py"
      to: "backend/core/models.py"
      via: "AgentPost, Channel queries for feed generation"
---

<objective>
**Communication & Feed Management Testing** - Verify agent-to-agent messaging reliability, Redis pub/sub horizontal scaling, chronological feed generation, and cursor-based pagination with property-based invariants.

**Purpose:** Ensure the social layer communication infrastructure delivers messages reliably (no lost messages, FIFO ordering) and generates stable, filterable feeds with cursor pagination that never returns duplicates.

**Output:** Comprehensive integration and property-based tests for agent_communication.py and agent_social_layer.py feed generation.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@/Users/rushiparikh/projects/atom/backend/core/agent_communication.py
@/Users/rushiparikh/projects/atom/backend/core/agent_social_layer.py
@/Users/rushiparikh/projects/atom/backend/api/social_routes.py
@/Users/rushiparikh/projects/atom/backend/tests/test_social_feed_service.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Agent Communication and Pub/Sub Tests</name>
  <files>backend/tests/test_agent_communication.py</files>
  <action>
    Create comprehensive test file test_agent_communication.py with tests for:

    1. **Event Bus Unit Tests** (12 tests):
       - test_subscribe_adds_subscriber: Agent added to subscribers
       - test_unsubscribe_removes_subscriber: Agent removed on unsubscribe
       - test_unsubscribe_cleans_up_empty_agent: Agent entry removed when no connections
       - test_topic_subscription: Agent subscribed to specific topics
       - test_publish_to_subscribers: Event delivered to all topic subscribers
       - test_publish_multiple_topics: Event delivered to multiple topics
       - test_broadcast_post_shortcut: broadcast_post() publishes correctly
       - test_websocket_send_json: Events sent as JSON
       - test_dead_websocket_removed: Failed sends trigger unsubscribe
       - test_global_topic_all_subscribers: All agents receive global broadcasts
       - test_alert_topic_subscribers: Alert posts go to alerts topic
       - test_category_topic_subscribers: Category-specific posts routed correctly

    2. **Redis Pub/Sub Integration Tests** (10 tests):
       - test_redis_publish: Events published to Redis channels
       - test_redis_subscribe: Background listener created
       - test_redis_fallback_to_in_memory: Graceful degradation when Redis unavailable
       - test_redis_graceful_shutdown: Connections closed properly
       - test_redis_listener_broadcasts_locally: Redis messages rebroadcast to local WebSockets
       - test_redis_multiple_topics: Subscribed to all agent_events:* topics
       - test_redis_connection_retry: Reconnection on connection failure
       - test_redis_disabled_by_env: REDIS_URL unset = in-memory only
       - test_redis_message_format: JSON format with topics and event
       - test_redis_no_infinite_loop: Redis events not republished back to Redis

    3. **WebSocket Connection Tests** (8 tests):
       - test_websocket_subscribe: Connection added to subscribers
       - test_websocket_unsubscribe: Connection removed on disconnect
       - test_multiple_connections_per_agent: Multiple concurrent connections allowed
       - test_ping_pong_response: Ping messages get pong response
       - test_json_send_format: Events sent as valid JSON
       - test_connection_cleanup: Cleanup on abnormal disconnect
       - test_subscribe_to_multiple_topics: Single connection can subscribe to multiple topics
       - test_channel_subscription: Channel topics (channel:{name}) work correctly

    4. **Property-Based Tests for Message Ordering** (5 tests):
       ```python
       @given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=20))
       def test_messages_delivered_in_fifo_order(messages):
           """Property: Messages delivered in FIFO order per sender"""
           bus = AgentEventBus()
           received = []
           async def capture(msg):
               received.append(msg)
           # Send messages and verify order
           for msg in messages:
               await bus.publish({"data": msg}, ["global"])
           # Verify FIFO order preserved
           assert [m["data"] for m in received] == messages

       @given(st.integers(min_value=1, max_value=100))
       def test_no_messages_lost(count):
           """Property: All published messages delivered to subscribers"""
           bus = AgentEventBus()
           received_count = [0]
           async def increment(msg):
               received_count[0] += 1
           await bus.subscribe("agent1", MockWebSocket(increment))
           for i in range(count):
               await bus.publish({"id": i}, ["global"])
           assert received_count[0] == count

       @given(st.integers(min_value=2, max_value=20))
       def test_multiple_subscribers_all_receive(subscriber_count):
           """Property: All subscribers receive every message"""
           bus = AgentEventBus()
           counts = [0] * subscriber_count
           for i in range(subscriber_count):
               await bus.subscribe(f"agent{i}", MockWebSocket(lambda m: set_count(i, counts)))
           await bus.publish({"test": "data"}, ["global"])
           assert all(c == 1 for c in counts)

       @given(st.lists(st.sampled_from(["global", "alerts", "agent:123"]), min_size=0, max_size=10))
       def test_topic_filtering(topics):
           """Property: Only subscribed topics received"""
           bus = AgentEventBus()
           global_received = []
           alerts_received = []
           await bus.subscribe("agent1", MockWebSocket(lambda m: global_received.append(m), ["global"]))
           await bus.subscribe("agent2", MockWebSocket(lambda m: alerts_received.append(m), ["alerts"]))
           await bus.publish({"test": "data"}, topics)
           # Verify each subscriber only gets their topics
           assert len(global_received) == (1 if "global" in topics else 0)
           assert len(alerts_received) == (1 if "alerts" in topics else 0)

       @given(st.integers(min_value=0, max_size=50))
       def test_event_bus_concurrent_publish(count):
           """Property: Concurrent publishes don't lose messages"""
           bus = AgentEventBus()
           received = []
           async def capture(msg):
               received.append(msg)
           await bus.subscribe("agent1", MockWebSocket(capture))
           # Publish concurrently
           tasks = [bus.publish({"id": i}, ["global"]) for i in range(count)]
           await asyncio.gather(*tasks)
           assert len(received) == count
       ```

    Create 500+ line test file with 35 tests (12 unit, 10 Redis, 8 WebSocket, 5 property-based).
  </action>
  <verify>
    pytest tests/test_agent_communication.py -v --tb=short
    # Expected: 35+ tests passing, property tests run 100+ examples each
  </verify>
  <done>
    - New test file test_agent_communication.py with 35 tests
    - AgentEventBus tested for subscribe, unsubscribe, publish, Redis integration
    - WebSocket connection handling verified
    - Property-based tests verify FIFO ordering, no lost messages
    - Coverage for agent_communication.py >80%
  </done>
</task>

<task type="auto">
  <name>Task 2: Social Feed Integration and Pagination Tests</name>
  <files>backend/tests/test_social_feed_integration.py</files>
  <action>
    Create comprehensive test file test_social_feed_integration.py with tests for:

    1. **Feed Generation Tests** (10 tests):
       - test_feed_chronological_ordering: Posts sorted by created_at DESC
       - test_feed_filter_by_post_type: Only specified post_type returned
       - test_feed_filter_by_sender: Only posts from sender returned
       - test_feed_filter_by_channel: Only posts in channel returned
       - test_feed_filter_public_private: is_public filter works
       - test_feed_pagination_offset_limit: Pagination parameters respected
       - test_feed_total_count_accurate: Total count matches query
       - test_feed_empty_returns_empty: No posts returns empty list
       - test_feed_with_multiple_filters: Combined filters work together
       - test_feed_includes_all_fields: All post fields included in response

    2. **Cursor Pagination Tests** (8 tests):
       - test_cursor_first_page_returns_next_cursor: Initial request has next_cursor
       - test_cursor_second_page_returns_older_posts: Cursor gets posts before cursor
       - test_cursor_no_duplicates_on_new_posts: New posts don't cause duplicates
       - test_cursor_empty_when_no_more_posts: has_more=false at end
       - test_cursor_invalid_format_handled: Bad cursor format logged
       - test_cursor_with_channel_filter: Cursor works with channels
       - test_cursor_with_post_type_filter: Cursor works with filters
       - test_cursor_stable_with_concurrent_posts: Stability under concurrent writes

    3. **Channel Isolation Tests** (7 tests):
       - test_channel_creation: Channel created successfully
       - test_channel_duplicate_returns_existing: Idempotent channel creation
       - test_channel_list_all: All channels returned
       - test_channel_posts_isolated: Channel posts only in channel feed
       - test_channel_public_private: is_public controls visibility
       - test_channel_members: agent_members and user_members tracked
       - test_channel_deletion: Posts cascade on channel delete (if implemented)

    4. **Real-Time Update Tests** (6 tests):
       - test_new_post_broadcasts: New post triggers WebSocket broadcast
       - test_reaction_broadcasts: Reaction triggers broadcast
       - test_reply_broadcasts: Reply triggers broadcast
       - test_channel_post_broadcasts_to_channel: Channel posts broadcast to channel topic
       - test_alert_broadcasts_to_all: Alert posts go to alerts topic
       - test_websocket_subscribe_receives_updates: Subscriber receives real-time updates

    5. **Property-Based Tests for Feed Invariants** (7 tests):
       ```python
       @given(st.integers(min_value=1, max_value=50), st.integers(min_value=5, max_size=20))
       def test_cursor_pagination_never_returns_duplicates(post_count, page_size):
           """Property: Cursor pagination never returns duplicate posts"""
           # Create posts
           posts = create_test_posts(post_count)
           # Paginate through all pages
           seen_ids = set()
           cursor = None
           while True:
               feed = get_feed_cursor(cursor=cursor, limit=page_size)
               page_ids = set(p["id"] for p in feed["posts"])
               # Verify no duplicates
               duplicates = seen_ids & page_ids
               assert not duplicates, f"Duplicates found: {duplicates}"
               seen_ids.update(page_ids)
               if not feed["has_more"]:
                   break
               cursor = feed["next_cursor"]
           # Verify all posts seen
           assert seen_ids == set(p["id"] for p in posts)

       @given(st.integers(min_value=1, max_value=100))
       def test_feed_always_chronological(post_count):
           """Property: Feed always returns posts in chronological order (newest first)"""
           posts = create_test_posts_with_timestamps(post_count)
           feed = get_feed(limit=post_count)
           timestamps = [p["created_at"] for p in feed["posts"]]
           # Verify descending order
           assert timestamps == sorted(timestamps, reverse=True)

       @given(st.lists(st.integers(min_value=0, max_value=50), min_size=0, max_size=20))
       def test_reply_count_monotonically_increases(reply_counts):
           """Property: Reply count never decreases"""
           post = create_test_post(reply_count=0)
           for count in reply_counts:
               add_replies(post.id, count)
               updated = get_post(post.id)
               assert updated["reply_count"] >= post["reply_count"]
               post = updated

       @given(st.integers(min_value=1, max_value=50), st.integers(min_value=1, max_value=10))
       def test_channel_posts_isolated(channel_posts, other_posts):
           """Property: Channel posts only appear in that channel's feed"""
           channel_id = create_test_channel()
           # Create channel posts and non-channel posts
           for _ in range(channel_posts):
               create_post(channel_id=channel_id)
           for _ in range(other_posts):
               create_post(channel_id=None)
           # Get channel feed
           channel_feed = get_feed(channel_id=channel_id)
           # All posts should have channel_id
           assert all(p["channel_id"] == channel_id for p in channel_feed["posts"])

       @given(st.integers(min_value=1, max_value=20))
       def test_feed_filter_by_post_type_complete(post_count):
           """Property: Filter returns only matching post_type"""
           types = ["status", "insight", "question", "alert"]
           posts = [create_post(post_type=random.choice(types)) for _ in range(post_count)]
           for post_type in types:
               filtered = get_feed(post_type=post_type)
               assert all(p["post_type"] == post_type for p in filtered["posts"])

       @given(st.integers(min_value=1, max_value=30))
       def test_total_count_matches_actual(post_count):
           """Property: Total count matches actual post count"""
           create_test_posts(post_count)
           feed = get_feed(limit=100)
           assert feed["total"] == post_count

       @given(st.integers(min_value=1, max_value=20))
       def test_no_lost_posts_in_feed(post_count):
           """Property: All posts appear in feed (no lost posts)"""
           created = create_test_posts(post_count)
           feed = get_feed(limit=100)
           feed_ids = set(p["id"] for p in feed["posts"])
           created_ids = set(p["id"] for p in created)
           # All created posts should be in feed
           assert feed_ids == created_ids
       ```

    Create 600+ line test file with 38 tests (10 feed generation, 8 cursor pagination, 7 channel isolation, 6 real-time updates, 7 property-based).
  </action>
  <verify>
    pytest tests/test_social_feed_integration.py -v --tb=short
    # Expected: 38+ tests passing, property tests run 100+ examples each
  </verify>
  <done>
    - New test file test_social_feed_integration.py with 38 tests
    - Feed generation verified for chronological ordering and filtering
    - Cursor pagination verified for no duplicates invariant
    - Channel isolation verified
    - Real-time WebSocket updates verified
    - Property-based tests verify all AR-12 invariants
    - Coverage for agent_social_layer.py >80%
  </done>
</task>

<task type="auto">
  <name>Task 3: Social Routes API Integration Tests</name>
  <files>backend/tests/api/test_social_routes_integration.py</files>
  <action>
    Create comprehensive API integration test file test_social_routes_integration.py with tests for:

    1. **POST /api/social/posts Tests** (6 tests):
       - test_create_post_as_agent_success: INTERN+ agent can post
       - test_create_post_as_student_forbidden: STUDENT agent blocked
       - test_create_post_as_human_success: Human can post
       - test_create_post_with_pii_redacted: PII auto-redacted
       - test_create_post_broadcasts_websocket: WebSocket broadcast triggered
       - test_create_post_invalid_post_type: 400 for invalid post_type

    2. **GET /api/social/feed Tests** (5 tests):
       - test_get_feed_returns_posts: Feed returns posts
       - test_get_feed_with_filters: Filters applied correctly
       - test_get_feed_pagination: Limit/offset respected
       - test_get_feed_empty: Empty feed handled
       - test_get_feed_no_auth_required: No maturity gate for reading

    3. **Cursor Pagination API Tests** (4 tests):
       - test_get_feed_cursor_first_page: Returns next_cursor
       - test_get_feed_cursor_pagination: Cursor pagination works
       - test_get_feed_cursor_with_filters: Cursor with filters
       - test_get_feed_cursor_no_duplicates: No duplicates across pages

    4. **Reply and Reaction API Tests** (5 tests):
       - test_add_reply_success: Reply created and broadcast
       - test_add_reply_student_blocked: STUDENT blocked from replying
       - test_get_replies_success: Replies returned in ASC order
       - test_add_reaction_success: Reaction added
       - test_get_reactions_success: Reactions returned

    5. **Channel API Tests** (4 tests):
       - test_create_channel_success: Channel created
       - test_get_channels_success: Channels listed
       - test_channel_posts_filtered: Channel filter works
       - test_duplicate_channel_handled: Idempotent channel creation

    6. **WebSocket Feed Tests** (4 tests):
       - test_websocket_connect: Connection accepted
       - test_websocket_receive_updates: Real-time updates received
       - test_websocket_ping_pong: Ping/pong works
       - test_websocket_disconnect: Cleanup on disconnect

    Create 400+ line API integration test file using FastAPI TestClient with 28 tests.
  </action>
  <verify>
    pytest tests/api/test_social_routes_integration.py -v --tb=short
    # Expected: 28+ tests passing, API responses validated
  </verify>
  <done>
    - New API test file test_social_routes_integration.py with 28 tests
    - All social API endpoints tested
    - WebSocket endpoint tested
    - Governance enforcement verified (STUDENT blocked)
    - PII redaction integration verified
  </done>
</task>

</tasks>

<verification>
**Overall Verification:**
1. Run full social layer test suite: `pytest tests/test_agent_communication.py tests/test_social_feed_integration.py tests/api/test_social_routes_integration.py -v`
2. Verify 95%+ test pass rate
3. Verify property-based tests run 100+ examples each with zero failures
4. Run coverage report: `pytest --cov=core/agent_communication --cov=core/agent_social_layer --cov=api/social_routes --cov-report=term-missing`
5. Verify >80% coverage for all modules
6. Test Redis integration with optional dependency (skip tests if Redis not installed)
7. Run 3 times to verify no flaky tests (TQ-04 requirement)
</verification>

<success_criteria>
1. **Agent Communication**: 35+ tests, >80% coverage, Redis integration tested
2. **Social Feed Integration**: 38+ tests, >80% coverage, all filter combinations tested
3. **API Integration**: 28+ tests, all endpoints tested
4. **Property-Based Tests**: 12+ Hypothesis tests verifying AR-12 invariants
5. **Invariants Verified**: No duplicates, FIFO ordering, no lost messages, feed stability
6. **Flaky Tests**: Zero flaky tests across 3 runs (TQ-04)
</success_criteria>

<output>
After completion, create `.planning/phases/18-social-layer-testing/18-social-layer-testing-02-SUMMARY.md` with:
- Test count and pass rate for each module
- Coverage metrics for agent_communication, agent_social_layer, social_routes
- Property-based test results (examples run, shrinks, failures)
- Redis integration test results
- Discovered bugs or edge cases
- Overall Phase 18 summary with recommendations for next phases
</output>
