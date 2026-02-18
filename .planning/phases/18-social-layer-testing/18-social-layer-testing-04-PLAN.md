---
phase: 18-social-layer-testing
plan: 04
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/test_agent_communication.py
  - backend/core/agent_communication.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "No messages are lost during pub/sub broadcasting (Redis or in-memory)"
    - "Redis pub/sub integration enables horizontal scaling for multi-instance deployments"
  artifacts:
    - path: "backend/tests/test_agent_communication.py"
      provides: "Fixed Redis integration tests with proper mocks"
      min_lines: 750
    - path: "backend/core/agent_communication.py"
      provides: "Redis pub/sub integration (existing, may need tweaks)"
  key_links:
    - from: "test_agent_communication.py"
      to: "agent_communication.py"
      via: "AgentEventBus import and instantiation"
      pattern: "from core.agent_communication import AgentEventBus"
    - from: "test_agent_communication.py"
      to: "redis.asyncio"
      via: "Redis mock configuration"
      pattern: "patch.*redis|Mock.*redis"
---

<objective>
Fix Redis integration test failures caused by incorrect mock configuration.

Purpose: Redis integration exists in agent_communication.py (redis.asyncio import, _ensure_redis(), publish to Redis topics, background listener) but tests fail due to mock configuration issues. 4 Redis tests fail: test_redis_subscribe, test_redis_fallback_to_in_memory, test_redis_graceful_shutdown, test_redis_multiple_topics.
Output: All 4 Redis tests pass, verifying Redis pub/sub works correctly for horizontal scaling
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/18-social-layer-testing/18-social-layer-testing-VERIFICATION.md
@.planning/phases/18-social-layer-testing/18-social-layer-testing-02-SUMMARY.md
@backend/tests/test_agent_communication.py
@backend/core/agent_communication.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix Redis mock configuration for pubsub tests</name>
  <files>backend/tests/test_agent_communication.py</files>
  <action>
    Fix the 4 failing Redis tests by correcting mock configuration.

    Failing tests:
    1. test_redis_subscribe - Redis pubsub mock not configured correctly
    2. test_redis_fallback_to_in_memory - Mock issues with Redis unavailability
    3. test_redis_graceful_shutdown - Redis cleanup mock issues
    4. test_redis_multiple_topics - Multi-topic pub/sub mock problems

    Root cause: Redis pubsub mock missing listen() method or incorrect async configuration.

    Fix approach:
    1. Read the TestRedisPubSub class (around line 350-500)
    2. Create proper AsyncMock for redis.asyncio.Redis connection
    3. Configure pubsub mock with all required methods:
       - subscribe() (async)
       - listen() (async) - returns async iterator
       - unsubscribe() (async)
       - get_message() (async)

    Mock pattern to use:
    ```python
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_pubsub.listen = AsyncMock(return_value=async_iter([]))
    mock_redis.pubsub = Mock(return_value=mock_pubsub)
    mock_redis.publish = AsyncMock()
    mock_redis.subscribe = AsyncMock()
    mock_redis.close = AsyncMock()
    ```

    For async iterator in listen():
    ```python
    async def async_iter(items):
        for item in items:
            yield item

    # In test
    mock_pubsub.listen = AsyncMock(side_effect=lambda: async_iter([]))
    ```

    4. Patch redis.asyncio.from_url to return the mock connection
    5. Verify each test's expectations match the mock behavior
  </action>
  <verify>cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_agent_communication.py::TestRedisPubSub -v</verify>
  <done>All 4 Redis tests (test_redis_subscribe, test_redis_fallback_to_in_memory, test_redis_graceful_shutdown, test_redis_multiple_topics) pass with correct mock configuration</done>
</task>

<task type="auto">
  <name>Task 2: Verify Redis integration code works correctly</name>
  <files>backend/tests/test_agent_communication.py</files>
  <action>
    Add verification test for Redis integration implementation in agent_communication.py.

    After fixing mocks, verify the actual Redis integration code works:
    1. Check that _ensure_redis() creates Redis connection correctly
    2. Verify publish() method sends to Redis when available
    3. Verify fallback to in-memory when Redis unavailable
    4. Verify graceful shutdown closes Redis connection

    Read agent_communication.py around:
    - _ensure_redis() method (lines 50-100)
    - publish() method (lines 150-220)
    - _redis_listener() background task (lines 250-350)
    - shutdown() method (lines 400-450)

    Add one integration-style test that uses the real Redis flow with mocks:
    - Create AgentEventBus with redis_url
    - Mock redis.asyncio.from_url
    - Call publish() and verify mock_redis.publish was called
    - Call shutdown() and verify mock_redis.close was called

    This test confirms the code flow is correct even with mocked Redis.
  </action>
  <verify>cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_agent_communication.py::TestRedisPubSub::test_redis_message_format -v</verify>
  <done>Redis integration test confirms publish format, fallback, and shutdown behavior</done>
</task>

</tasks>

<verification>
After completing all tasks, run the Redis test suite:

```bash
cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_agent_communication.py::TestRedisPubSub -v --tb=short
```

Expected results:
- All 10 Redis tests pass (previously 6/10)
- No mock configuration errors
- pubsub listen() method correctly mocked

Run full agent communication test suite:
```bash
cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_agent_communication.py -v
```

Expected results:
- 35 total tests
- 34-35 tests passing (previously 31)
- 0-1 tests failing (edge cases)
</verification>

<success_criteria>
1. All 4 previously failing Redis tests now pass
2. Redis pub/sub mock has all required methods (subscribe, listen, unsubscribe, get_message)
3. AgentEventBus correctly falls back to in-memory when Redis unavailable
4. Overall pass rate for test_agent_communication.py improves from 89% to 98%+
</success_criteria>

<output>
After completion, create `.planning/phases/18-social-layer-testing/18-social-layer-testing-04-SUMMARY.md`
</output>
