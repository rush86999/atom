---
phase: 17-agent-layer
plan: 03
type: execute
wave: 2
depends_on: [01]
files_modified:
  - backend/tests/integration/test_agent_execution_orchestration.py
  - backend/tests/unit/agents/test_agent_to_agent_communication.py
  - backend/tests/property_tests/agents/test_agent_coordination_invariants.py
autonomous: true

must_haves:
  truths:
    - "Agent execution orchestration includes governance validation, LLM streaming, episode creation"
    - "WebSocket streaming delivers tokens with proper message tracking and completion signals"
    - "Agent-to-agent communication supports human↔agent, agent↔agent, and directed messaging"
    - "AgentEventBus provides pub/sub with topic filtering (global, agent:, category:, alerts)"
    - "Property tests validate communication invariants (message delivery, topic routing, feed ordering)"
    - "Multi-agent coordination validates parallel execution conflicts and state consistency"
    - "Error handling covers LLM failures, database errors, and WebSocket disconnections"
  artifacts:
    - path: "backend/tests/integration/test_agent_execution_orchestration.py"
      provides: "End-to-end agent execution tests (governance, streaming, persistence)"
      min_lines: 450
    - path: "backend/tests/unit/agents/test_agent_to_agent_communication.py"
      provides: "Agent communication tests (social layer, event bus, directed messaging)"
      min_lines: 400
    - path: "backend/tests/property_tests/agents/test_agent_coordination_invariants.py"
      provides: "Property tests for agent coordination invariants (Hypothesis)"
      min_lines: 350
  key_links:
    - from: "test_agent_execution_orchestration.py"
      to: "core/agent_execution_service.py"
      via: "execute_agent_chat() and execute_agent_chat_sync() functions"
      pattern: "execute_agent_chat"
    - from: "test_agent_to_agent_communication.py"
      to: "core/agent_social_layer.py"
      via: "AgentSocialLayer for communication and AgentEventBus for pub/sub"
      pattern: "AgentSocialLayer|AgentEventBus"
    - from: "test_agent_coordination_invariants.py"
      to: "core/agent_execution_service.py"
      via: "Property tests for orchestration invariants"
      pattern: "invariant.*message_delivery|invariant.*state_consistency"
---

<objective>
Test agent execution orchestration and agent-to-agent communication systems.

**Purpose:** Validate that agent execution orchestrates correctly through the full pipeline (governance validation, LLM streaming, episode creation, WebSocket delivery, audit logging) and that agents can communicate with each other via the social layer and event bus.

**Output:** Three comprehensive test files covering:
1. End-to-end agent execution orchestration with streaming and persistence
2. Agent-to-agent communication (social layer, event bus, directed messaging)
3. Property-based tests for agent coordination invariants (message delivery, state consistency)

**Coverage Target:** 50%+ combined coverage on agent_execution_service.py and agent_social_layer.py
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushipikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md

# Execution and communication services
@backend/core/agent_execution_service.py
@backend/core/agent_social_layer.py
@backend/core/agent_communication.py

# Existing test patterns
@backend/tests/unit/test_agent_governance_service.py
@backend/tests/test_agent_social_layer.py
@backend/tests/property_tests/agents/test_agent_execution_invariants.py
@backend/tests/property_tests/multi_agent/test_agent_coordination_invariants.py
@backend/tests/conftest.py (db_session, mock_llm_response, mock_embedding_vectors)
</context>

<tasks>

<task type="auto">
  <name>Test agent execution orchestration end-to-end</name>
  <files>backend/tests/integration/test_agent_execution_orchestration.py</files>
  <action>
    Create test_agent_execution_orchestration.py with end-to-end execution tests.

    Test classes:
    - TestGovernanceValidation: 4 tests for governance checks before execution (block unauthorized agents)
    - TestLLMStreamingExecution: 4 tests for BYOK handler streaming (token accumulation, provider selection)
    - TestWebSocketStreaming: 4 tests for WebSocket token delivery (streaming:start, update, complete)
    - TestChatHistoryPersistence: 4 tests for chat history saving (session creation, message storage)
    - TestAgentExecutionAuditTrail: 4 tests for AgentExecution records (creation, status updates, error logging)
    - TestEpisodeCreationTriggering: 4 tests for episode creation after execution (trigger_episode_creation)
    - TestErrorHandling: 4 tests for error scenarios (LLM failures, DB errors, governance blocks)
    - TestSyncExecutionWrapper: 4 tests for execute_agent_chat_sync() (event loop handling, streaming disabled)

    Mock dependencies for isolated testing:
    ```python
    @pytest.mark.asyncio
    @patch('core.agent_execution_service.BYOKHandler')
    @patch('core.agent_execution_service.AgentContextResolver')
    @patch('core.agent_execution_service.ws_manager')
    async def test_successful_execution_with_governance_approval(
        self, mock_ws, mock_resolver, mock_byok, db_session
    ):
        # Mock agent resolution
        agent = AutonomousAgentFactory(_session=db_session)
        db_session.commit()

        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(
            return_value=(agent, {"resolution_path": ["explicit_agent_id"]})
        )
        mock_resolver.return_value = resolver

        # Mock governance check
        governance = MagicMock()
        governance.can_perform_action.return_value = {
            "proceed": True,
            "allowed": True
        }
        resolver.governance = governance

        # Mock LLM streaming
        byok_instance = MagicMock()
        byok_instance.analyze_query_complexity.return_value = QueryComplexity.LOW
        byok_instance.get_optimal_provider.return_value = ("openai", "gpt-4")

        async def mock_stream(**kwargs):
            tokens = ["Hello", " ", "world", "!"]
            for token in tokens:
                yield token

        byok_instance.stream_completion = mock_stream
        mock_byok.return_value = byok_instance

        # Mock WebSocket manager
        ws_instance = MagicMock()
        ws_instance.broadcast = AsyncMock()
        mock_ws_manager = MagicMock()
        mock_ws_manager.broadcast = ws_instance.broadcast
        mock_ws.return_value = mock_ws_manager
        mock_ws.STREAMING_UPDATE = "streaming:update"
        mock_ws.STREAMING_COMPLETE = "streaming:complete"

        result = await execute_agent_chat(
            agent_id=agent.id,
            message="Hello world",
            user_id="test_user",
            session_id=None,
            stream=True
        )

        assert result["success"] is True
        assert result["response"] == "Hello world!"
        assert "execution_id" in result
    ```

    Test AgentExecution audit trail:
    ```python
    @pytest.mark.asyncio
    async def test_agent_execution_record_created(self, db_session):
        agent = AutonomousAgentFactory(_session=db_session)
        db_session.commit()

        with patch('core.agent_execution_service.BYOKHandler'):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action.return_value = {
                        "proceed": True, "allowed": True
                    }
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=agent.id,
                        message="test",
                        user_id="user_123",
                        stream=False
                    )

        # Verify AgentExecution record was created
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).first()

        assert execution is not None
        assert execution.status == "completed"
        assert execution.agent_name == agent.name
    ```

    Test error handling:
    ```python
    @pytest.mark.asyncio
    async def test_governance_block_prevents_execution(self, db_session):
        student_agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
            resolver = MagicMock()
            resolver.resolve_agent_for_request = AsyncMock(
                return_value=(student_agent, {})
            )
            resolver.governance = MagicMock()
            resolver.governance.can_perform_action.return_value = {
                "proceed": False,
                "allowed": False,
                "reason": "STUDENT agent blocked from chat"
            }
            mock_resolver.return_value = resolver

            result = await execute_agent_chat(
                agent_id=student_agent.id,
                message="test",
                user_id="user_123"
            )

        assert result["success"] is False
        assert "blocked" in result["error"].lower()
    ```

    Test sync wrapper:
    ```python
    def test_sync_execution_wrapper_creates_event_loop(self):
        result = execute_agent_chat_sync(
            agent_id="test_agent",
            message="test message",
            user_id="user_123",
            stream=False  # Sync mode doesn't support streaming
        )

        assert "success" in result or "error" in result
        assert "execution_id" in result or "error" in result
    ```
  </action>
  <verify>
    Run: pytest backend/tests/integration/test_agent_execution_orchestration.py -v

    Expected: 32 tests passing, end-to-end execution validated
  </verify>
  <done>
    - Governance validation blocks unauthorized agents before execution
    - LLM streaming accumulates tokens correctly
    - WebSocket delivers streaming messages with proper type tags
    - Chat history persists messages to database
    - AgentExecution audit trail captures all executions
    - Episode creation triggers after successful execution
    - Errors are handled gracefully with proper logging
    - Sync wrapper works for non-async contexts
  </done>
</task>

<task type="auto">
  <name>Test agent-to-agent communication via social layer</name>
  <files>backend/tests/unit/agents/test_agent_to_agent_communication.py</files>
  <action>
    Create test_agent_to_agent_communication.py with agent communication tests.

    Test classes:
    - TestSocialLayerMessagePosting: 4 tests for posting to social feed (human↔agent, agent↔agent)
    - TestEventBusPubSub: 4 tests for AgentEventBus (topic filtering, message broadcasting)
    - TestDirectedMessaging: 4 tests for 1:1 agent communication (send, receive, blocking)
    - TestChannelCreation: 4 tests for channel management (create, join, leave, list)
    - TestReactionHandling: 4 tests for emoji reactions (add, remove, list)
    - TestTrendingTopics: 4 tests for trending topic calculation (hashtag extraction, frequency)
    - TestFeedPagination: 4 tests for feed pagination (cursor-based, page-based)
    - TestMaturityGates: 4 tests for maturity restrictions (STUDENT read-only, INTERN+ posting)

    Test agent posting to social feed:
    ```python
    @pytest.mark.asyncio
    async def test_agent_can_post_to_social_feed(self, db_session):
        agent = InternAgentFactory(_session=db_session)
        db_session.commit()

        social_layer = AgentSocialLayer(db_session)

        post = await social_layer.create_post(
            agent_id=agent.id,
            agent_type="agent",
            content="Agent status update: Task completed successfully",
            post_type="status",
            is_public=True
        )

        assert post.id is not None
        assert post.agent_id == agent.id
        assert post.content == "Agent status update: Task completed successfully"
        assert post.is_public is True
    ```

    Test event bus pub/sub:
    ```python
    @pytest.mark.asyncio
    async def test_event_bus_broadcasts_to_subscribers(self):
        event_bus = AgentEventBus()

        # Track received messages
        received = []

        async def handler(message):
            received.append(message)

        # Subscribe to agent topic
        await event_bus.subscribe("agent:test_agent", handler)

        # Broadcast message
        await event_bus.publish("agent:test_agent", {
            "type": "status_update",
            "agent_id": "test_agent",
            "content": "Test message"
        })

        # Give async handler time to process
        await asyncio.sleep(0.1)

        assert len(received) == 1
        assert received[0]["content"] == "Test message"
    ```

    Test directed messaging:
    ```python
    @pytest.mark.asyncio
    async def test_directed_agent_to_agent_communication(self, db_session):
        agent1 = AgentFactory(_session=db_session)
        agent2 = AgentFactory(_session=db_session)
        db_session.commit()

        social_layer = AgentSocialLayer(db_session)

        # Agent1 sends directed message to Agent2
        message = await social_layer.send_direct_message(
            from_agent_id=agent1.id,
            to_agent_id=agent2.id,
            content="Agent2, please help with task",
            message_type="command"
        )

        assert message.id is not None
        assert message.from_agent_id == agent1.id
        assert message.to_agent_id == agent2.id

        # Verify message appears in agent2's inbox
        inbox = await social_layer.get_direct_messages(agent2.id)
        assert any(m.id == message.id for m in inbox)
    ```

    Test maturity gates:
    ```python
    @pytest.mark.asyncio
    async def test_student_agent_read_only_social_access(self, db_session):
        student = StudentAgentFactory(_session=db_session)
        db_session.commit()

        social_layer = AgentSocialLayer(db_session)

        # STUDENT can read public feed
        feed = await social_layer.get_public_feed(limit=10)
        assert isinstance(feed, list)

        # STUDENT blocked from posting
        with pytest.raises(PermissionError):
            await social_layer.create_post(
                agent_id=student.id,
                agent_type="agent",
                content="Should fail",
                post_type="status"
            )
    ```

    Test trending topics:
    ```python
    @pytest.mark.asyncio
    async def test_trending_topics_aggregation(self, db_session):
        agent = AutonomousAgentFactory(__session=db_session)
        db_session.commit()

        social_layer = AgentSocialLayer(db_session)

        # Create posts with hashtags
        await social_layer.create_post(
            agent_id=agent.id,
            agent_type="agent",
            content="Working on #automation and #integration",
            post_type="status",
            is_public=True
        )

        await social_layer.create_post(
            agent_id=agent.id,
            agent_type="agent",
            content="#automation progress update",
            post_type="insight",
            is_public=True
        )

        # Get trending topics
        trending = await social_layer.get_trending_topics(limit=10)

        assert "#automation" in [t["topic"] for t in trending]
        assert "#integration" in [t["topic"] for t in trending]
    ```
  </action>
  <verify>
    Run: pytest backend/tests/unit/agents/test_agent_to_agent_communication.py -v

    Expected: 32 tests passing, agent communication validated
  </verify>
  <done>
    - Agents can post to social feed (INTERN+ only, STUDENT read-only)
    - AgentEventBus provides pub/sub with topic filtering (agent:, category:, alerts)
    - Directed messaging works for agent-to-agent communication
    - Channels support contextual conversations
    - Emoji reactions can be added and removed
    - Trending topics aggregate hashtags from posts
    - Feed pagination works (cursor-based and page-based)
    - Maturity gates enforced (STUDENT blocked from posting)
  </done>
</task>

<task type="auto">
  <name>Test agent coordination with property-based invariants</name>
  <files>backend/tests/property_tests/agents/test_agent_coordination_invariants.py</files>
<action>
    Create test_agent_coordination_invariants.py with Hypothesis property tests.

    Test classes:
    - TestMessageDeliveryInvariant: Given any agent and message, message is delivered to all subscribers
    - TestTopicRoutingInvariant: Given any topic and message, subscribers receive only matching topics
    - TestFeedOrderingInvariant: Given multiple posts, feed maintains chronological order
    - TestStateConsistencyInvariant: Given parallel operations, agent state remains consistent
    - TestPermissionInvariant: Given any agent and action, maturity gates are enforced
    - TestAuditTrailInvariant: Given any execution, audit trail is complete
    - TestErrorRecoveryInvariant: Given any failure, system recovers gracefully

    Example property tests using Hypothesis:
    ```python
    from hypothesis import given, strategies as st
    from hypothesis.stateful import RuleBasedStateMachine

    class TestMessageDeliveryInvariant:
        """Given any agent and message, message is delivered to all subscribers."""

        @pytest.mark.asyncio
        @given(st.text(min_size=1, max_size=100))
        async def test_message_delivered_to_all_subscribers(self, message_content):
            event_bus = AgentEventBus()

            # Create multiple subscribers
            subscriber_count = st.integers(min_value=1, max_value=10).example()
            received_counts = {}

            for i in range(subscriber_count):
                topic = f"test_topic_{i}"
                received_counts[topic] = 0

                async def handler(msg):
                    if msg.get("content") == message_content:
                        received_counts[topic] += 1

                await event_bus.subscribe(topic, handler)

            # Publish to all topics
            for i in range(subscriber_count):
                await event_bus.publish(
                    f"test_topic_{i}",
                    {"content": message_content}
                )

            # Verify each subscriber received exactly once
            for topic, count in received_counts.items():
                assert count == 1, f"Topic {topic} received {count} messages, expected 1"

    class TestStateConsistencyInvariant:
        """Given parallel operations, agent state remains consistent."""

        @pytest.mark.asyncio
        @given(st.lists(st.tuples(st.text(), st.text()), min_size=0, max_size=10))
        async def test_parallel_feed_updates_maintain_consistency(self, updates):
            db = MagicMock()
            social_layer = AgentSocialLayer(db)

            # Create multiple posts in parallel
            tasks = []
            for agent_id, content in updates:
                async def create_post():
                    return await social_layer.create_post(
                        agent_id=agent_id,
                        agent_type="agent",
                        content=content,
                        post_type="status",
                        is_public=True
                    )
                tasks.append(create_post())

            # Execute all posts in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All posts should succeed or fail gracefully
            for result in results:
                if isinstance(result, Exception):
                    # Error is acceptable, but system should not crash
                    assert isinstance(result, (Exception, dict))
                else:
                    assert isinstance(result, dict)
                    assert "id" in result or "error" in result

    class TestPermissionInvariant:
        """Given any agent and action, maturity gates are enforced."""

        @given(
            agent_maturity=st.sampled_from(["student", "intern", "supervised", "autonomous"]),
            action_complexity=st.integers(min_value=1, max_value=4),
            require_approval=st.booleans()
        )
        def test_maturity_gates_enforced(self, agent_maturity, action_complexity, require_approval):
        db = MagicMock()
        governance = AgentGovernanceService(db)

        # Create agent with specified maturity
        agent = MagicMock()
        agent.status = agent_maturity

        # Mock query to return agent
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        db.query.return_value = mock_query

        # Check permission
        result = governance.can_perform_action(
            agent_id="test_agent",
            action_type="test_action",  # Will use default complexity
            require_approval=require_approval
        )

        # Validate maturity gates
        maturity_order = ["student", "intern", "supervised", "autonomous"]
        agent_index = maturity_order.index(agent_maturity)
        required_index = action_complexity - 1

        # Agent must have sufficient maturity level
        if agent_index < required_index:
            assert result["allowed"] is False, \
                f"Agent {agent_maturity} (index {agent_index}) should be blocked from complexity {action_complexity}"
        else:
            assert result["allowed"] is True or result["requires_human_approval"] is True, \
                f"Agent {agent_maturity} (index {agent_index}) should be allowed for complexity {action_complexity}"
    ```

    Test feed ordering:
    ```python
    class TestFeedOrderingInvariant:
        """Given multiple posts, feed maintains chronological order."""

        @pytest.mark.asyncio
        @given(st.lists(st.text(min_size=1, max_size=50), min_size=5, max_size=20))
        async def test_feed_maintains_chronological_order(self, post_contents):
            db = MagicMock()
            social_layer = AgentSocialLayer(db)

            # Create posts with timestamps
            posts = []
            for i, content in enumerate(post_contents):
                post = await social_layer.create_post(
                    agent_id=f"agent_{i}",
                    agent_type="agent",
                    content=content,
                    post_type="status",
                    is_public=True
                )
                posts.append(post)
                await asyncio.sleep(0.01)  # Ensure different timestamps

            # Get feed
            feed = await social_layer.get_public_feed(limit=len(posts))

            # Verify chronological order (newest first)
            for i in range(len(feed) - 1):
                assert feed[i]["created_at"] >= feed[i + 1]["created_at"], \
                    f"Feed not in order at index {i}: {feed[i]['created_at']} < {feed[i+1]['created_at']}"
    ```

    Test audit trail completeness:
    ```python
    class TestAuditTrailInvariant:
        """Given any execution, audit trail is complete."""

        @given(
            action_type=st.sampled_from(["chat", "stream_chat", "create", "update", "delete"]),
            success=st.booleans(),
            error_message=st.none() | st.text(min_size=1, max_size=100)
        )
        @pytest.mark.asyncio
        async def test_audit_trail_complete(self, action_type, success, error_message):
        db_session = MagicMock()
        agent = AutonomousAgentFactory(_session=db_session)
        db_session.commit()

        with patch('core.agent_execution_service.BYOKHandler'):
            with patch('core.agent_execution_service.ws_manager'):
                result = await execute_agent_chat(
                    agent_id=agent.id,
                    message="test",
                    user_id="user_123"
                )

        # Verify audit record created
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).first()

        if result["success"]:
            assert execution is not None, "Audit record missing for successful execution"
            assert execution.status == "completed"
            assert execution.end_time is not None
            assert execution.duration_ms > 0
        else:
            assert execution is not None, "Audit record missing for failed execution"
            assert execution.status == "failed"
            assert execution.error_message is not None
    ```
  </action>
  <verify>
    Run: pytest backend/tests/property_tests/agents/test_agent_coordination_invariants.py -v

    Expected: 20+ tests passing with Hypothesis strategies, invariants validated
  </verify>
  <done>
    - Message delivery invariant: messages reach all subscribers
    - Topic routing invariant: subscribers receive only matching topics
    - Feed ordering invariant: chronological order maintained
    - State consistency invariant: parallel operations don't corrupt state
    - Permission invariant: maturity gates enforced for all actions
    - Audit trail invariant: complete records for all executions
    - Error recovery invariant: system recovers gracefully from failures
  </done>
</task>

</tasks>

<verification>
After completing all tasks, run full test suite for execution and coordination:

```bash
pytest backend/tests/integration/test_agent_execution_orchestration.py -v --cov=backend/core/agent_execution_service --cov-report=term-missing
pytest backend/tests/unit/agents/test_agent_to_agent_communication.py -v --cov=backend/core/agent_social_layer --cov-report=term-missing
pytest backend/tests/property_tests/agents/test_agent_coordination_invariants.py -v --cov=backend/core/agent_execution_service --cov-report=term-missing
```

Success criteria:
- All 80+ tests passing (32+32+20)
- Coverage on agent_execution_service.py >50%
- Coverage on agent_social_layer.py >50%
- All invariants validated with Hypothesis strategies
- End-to-end execution tested with mocked dependencies
</verification>

<success_criteria>
1. Agent execution orchestrates correctly (governance → LLM → streaming → persistence)
2. Agent-to-agent communication works (social layer, event bus, directed messaging)
3. Property tests validate critical coordination invariants
4. WebSocket streaming delivers messages with proper type tags
5. Error handling covers all failure scenarios
6. Audit trail captures all execution attempts
</success_criteria>

<output>
After completion, create `.planning/phases/05-agent-layer/05-agent-layer-03-SUMMARY.md`
</output>
