---
phase: 17-agent-layer
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/governance/test_agent_governance_maturity_routing.py
  - backend/tests/unit/governance/test_action_complexity_matrix.py
  - backend/tests/unit/governance/test_governance_cache_performance.py
autonomous: true

must_haves:
  truths:
    - "STUDENT agents (<0.5 confidence) are blocked from complexity 2+ actions (analyze, create, delete)"
    - "INTERN agents (0.5-0.7) can perform complexity 2 actions but require approval for complexity 3+"
    - "SUPERVISED agents (0.7-0.9) can perform complexity 1-3 actions but blocked from complexity 4"
    - "AUTONOMOUS agents (>0.9) can perform all actions (complexity 1-4) without restrictions"
    - "Action complexity matrix correctly maps 60+ actions to 4 complexity levels"
    - "Governance cache provides <1ms lookup latency with >90% hit rate"
    - "Permission checks enforce RBAC rules (admin/specialty matching)"
  artifacts:
    - path: "backend/tests/unit/governance/test_agent_governance_maturity_routing.py"
      provides: "Maturity level routing tests (4x4 matrix = 16 test cases)"
      min_lines: 400
    - path: "backend/tests/unit/governance/test_action_complexity_matrix.py"
      provides: "Action complexity matrix validation tests (60+ actions)"
      min_lines: 300
    - path: "backend/tests/unit/governance/test_governance_cache_performance.py"
      provides: "Cache performance tests (hit rate, latency, LRU eviction)"
      min_lines: 350
  key_links:
    - from: "test_agent_governance_maturity_routing.py"
      to: "core/agent_governance_service.py"
      via: "AgentGovernanceService.can_perform_action() method"
      pattern: "governance_service\\.can_perform_action"
    - from: "test_action_complexity_matrix.py"
      to: "core/agent_governance_service.py"
      via: "ACTION_COMPLEXITY dictionary and MATURITY_REQUIREMENTS mapping"
      pattern: "ACTION_COMPLEXITY\\[.*\\]|MATURITY_REQUIREMENTS"
    - from: "test_governance_cache_performance.py"
      to: "core/governance_cache.py"
      via: "GovernanceCache.get/set/invalidate methods"
      pattern: "GovernanceCache\\.(get|set|invalidate)"
---

<objective>
Test agent governance maturity routing and action complexity matrix enforcement.

**Purpose:** Validate that agent maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) correctly enforce permission boundaries and action complexity gates. This is critical for preventing immature agents from performing risky operations.

**Output:** Three comprehensive test files covering:
1. Maturity routing across 4x4 matrix (4 maturity levels × 4 action complexities)
2. Action complexity matrix validation (60+ action mappings)
3. Governance cache performance (<1ms lookups, >90% hit rate, LRU eviction)

**Coverage Target:** 60%+ combined coverage on agent_governance_service.py and governance_cache.py
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md

# Core governance services
@backend/core/agent_governance_service.py
@backend/core/governance_cache.py

# Existing test patterns
@backend/tests/unit/test_agent_governance_service.py
@backend/tests/unit/governance/test_agent_context_resolver.py
@backend/tests/conftest.py (db_session, maturity fixtures)
@backend/tests/factories/__init__.py (AgentFactory, maturity-specific factories)
</context>

<tasks>

<task type="auto">
  <name>Test maturity routing with 4x4 governance matrix</name>
  <files>backend/tests/unit/governance/test_agent_governance_maturity_routing.py</files>
  <action>
    Create test_agent_governance_maturity_routing.py with 4x4 maturity/complexity matrix tests.

    Test structure:
    - TestStudentAgentRouting: 4 tests for complexity 1-4 actions (should allow 1, block 2-4)
    - TestInternAgentRouting: 4 tests for complexity 1-4 actions (should allow 1-2, block 3-4)
    - TestSupervisedAgentRouting: 4 tests for complexity 1-4 actions (should allow 1-3, block 4)
    - TestAutonomousAgentRouting: 4 tests for complexity 1-4 actions (should allow all)
    - TestMaturityTransitions: 4 tests for confidence-based status changes
    - TestApprovalRequirements: 4 tests for require_approval flag behavior
    - TestEdgeCases: 4 tests for boundary conditions (0.5, 0.7, 0.9 thresholds)

    Use maturity-specific fixtures from conftest.py:
    - test_agent_student (0.3 confidence)
    - test_agent_intern (0.6 confidence)
    - test_agent_supervised (0.8 confidence)
    - test_agent_autonomous (0.95 confidence)

    Mock governance cache with patch:
    ```python
    @patch('core.agent_governance_service.get_governance_cache')
    def test_student_allowed_complexity_1(self, mock_cache, test_agent_student, db_session):
        cache_inst = MagicMock()
        cache_inst.get.return_value = None  # Force DB lookup
        mock_cache.return_value = cache_inst

        result = self.governance.can_perform_action(
            agent_id=test_agent_student.id,
            action_type="present_chart"  # Complexity 1
        )
        assert result["allowed"] is True
    ```

    Validate response structure includes:
    - allowed (bool)
    - reason (str)
    - agent_status (str)
    - action_complexity (int)
    - required_status (str)
    - requires_human_approval (bool)
    - confidence_score (float)
  </action>
  <verify>
    Run: pytest backend/tests/unit/governance/test_agent_governance_maturity_routing.py -v

    Expected: 28 tests passing, 0 failures, 70%+ coverage on can_perform_action()
  </verify>
  <done>
    - All 4 maturity levels tested against all 4 complexity levels (16 test cases)
    - Maturity transitions validated at confidence thresholds (0.5, 0.7, 0.9)
    - Approval requirements correctly enforced (SUPERVISED complexity 3+)
    - Response structure validated for all test cases
  </done>
</task>

<task type="auto">
  <name>Test action complexity matrix with 60+ action mappings</name>
  <files>backend/tests/unit/governance/test_action_complexity_matrix.py</files>
  <action>
    Create test_action_complexity_matrix.py with comprehensive action complexity validation.

    Test classes:
    - TestActionComplexityLevels: Validate ACTION_COMPLEXITY dict has all 4 levels
    - TestLowComplexityActions: 10 tests for complexity 1 actions (search, read, list, get, fetch, summarize, present_chart, present_markdown)
    - TestModerateComplexityActions: 10 tests for complexity 2 actions (analyze, suggest, draft, generate, recommend, stream_chat, present_form, llm_stream, browser_navigate, browser_screenshot, browser_extract, device_camera_snap, device_get_location, device_send_notification, update_canvas)
    - TestMediumComplexityActions: 8 tests for complexity 3 actions (create, update, send_email, post_message, schedule, submit_form, device_screen_record*)
    - TestHighComplexityActions: 8 tests for complexity 4 actions (delete, execute, deploy, transfer, payment, approve, device_execute_command, canvas_execute_javascript)
    - TestMaturityRequirementsMapping: Validate MATURITY_REQUIREMENTS maps correctly (1→STUDENT, 2→INTERN, 3→SUPERVISED, 4→AUTONOMOUS)
    - TestUnknownActionsDefaultToMedium: 4 tests for actions not in matrix (default complexity 2)
    - TestActionTypeCaseInsensitivity: 4 tests for case-insensitive action matching

    Use parametrize for efficiency:
    ```python
    @pytest.mark.parametrize("action,expected_level", [
        ("search", 1),
        ("read", 1),
        ("get", 1),
        # ... all 60+ actions
    ])
    def test_action_complexity_level(self, action, expected_level):
        level = AgentGovernanceService.ACTION_COMPLEXITY.get(action)
        assert level == expected_level
    ```

    Property-based test using Hypothesis for invariant validation:
    ```python
    from hypothesis import given, strategies as st
    from hypothesis.stateful import RuleBasedStateMachine

    class ActionComplexityInvariants:
        @given(st.text(min_size=1, max_size=50))
        def test_all_actions_have_valid_complexity(self, action):
            level = AgentGovernanceService.ACTION_COMPLEXITY.get(action.lower(), 2)
            assert level in [1, 2, 3, 4], f"Action {action} has invalid complexity {level}"
    ```
  </action>
  <verify>
    Run: pytest backend/tests/unit/governance/test_action_complexity_matrix.py -v

    Expected: 50+ tests passing, comprehensive coverage of all 60+ action mappings
  </verify>
  <done>
    - All 60+ actions tested for correct complexity level
    - MATURITY_REQUIREMENTS mapping validated (1→STUDENT, 2→INTERN, 3→SUPERVISED, 4→AUTONOMOUS)
    - Unknown actions default to complexity 2 (moderate)
    - Action matching is case-insensitive
    - Property test validates all possible action strings return valid complexity
  </done>
</task>

<task type="auto">
  <name>Test governance cache performance with hit rate and latency validation</name>
  <files>backend/tests/unit/governance/test_governance_cache_performance.py</files>
  <action>
    Create test_governance_cache_performance.py with cache performance tests.

    Test classes:
    - TestCacheBasicOperations: Test get/set/has/invalidate operations
    - TestCacheHitRate: Test >90% hit rate after warmup with 1000 operations
    - TestCacheLatency: Test <1ms P50 latency for cached lookups
    - TestLRUEviction: Test oldest entry eviction at max_size (1000 entries)
    - TestTTLExpiration: Test 60-second TTL for entry expiration
    - TestAgentSpecificInvalidation: Test invalidate(agent_id) removes all agent entries
    - TestDirectoryPermissionCache: Test specialized "dir:" prefix cache for permissions
    - TestThreadSafety: Test concurrent access from multiple threads
    - TestStatisticsReporting: Test get_stats() returns correct metrics
    - TestBackgroundCleanup: Test async cleanup task removes expired entries

    Key tests:
    ```python
    import time

    def test_cache_hit_rate_after_warmup(self):
        cache = GovernanceCache(max_size=1000)
        agent_id = "test_agent"

        # Warmup: cache 100 actions
        for i in range(100):
            cache.set(agent_id, f"action_{i}", {"allowed": True})

        # Measure hit rate
        hits = 0
        total = 1000
        for i in range(total):
            result = cache.get(agent_id, f"action_{i % 100}")
            if result is not None:
                hits += 1

        hit_rate = (hits / total) * 100
        assert hit_rate > 90, f"Hit rate {hit_rate}% below 90% threshold"

    def test_cache_latency_p50_sub_1ms(self):
        cache = GovernanceCache()
        agent_id = "perf_agent"
        cache.set(agent_id, "test_action", {"allowed": True})

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            cache.get(agent_id, "test_action")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms

        p50 = sorted(latencies)[len(latencies) // 2]
        assert p50 < 1.0, f"P50 latency {p50}ms exceeds 1ms threshold"
    ```

    Test LRU eviction order:
    ```python
    def test_lru_eviction_removes_oldest(self):
        cache = GovernanceCache(max_size=3)
        cache.set("agent1", "action1", {"data": "first"})
        cache.set("agent2", "action2", {"data": "second"})
        cache.set("agent3", "action3", {"data": "third"})

        # Access agent1 to make it recently used
        cache.get("agent1", "action1")

        # Add 4th entry - should evict agent2 (oldest, not agent1)
        cache.set("agent4", "action4", {"data": "fourth"})

        assert cache.get("agent1", "action1") is not None  # Still present
        assert cache.get("agent2", "action2") is None  # Evicted
        assert cache.get("agent3", "action3") is not None
        assert cache.get("agent4", "action4") is not None
    ```

    Test directory permission cache:
    ```python
    def test_directory_permission_cache_specialized_key(self):
        cache = GovernanceCache()
        agent_id = "test_agent"
        directory = "/tmp/test"

        # Use specialized methods
        permission_data = {"allowed": True, "reason": "Test directory"}
        cache.cache_directory(agent_id, directory, permission_data)

        result = cache.check_directory(agent_id, directory)
        assert result["allowed"] is True

        # Verify it doesn't collide with action_type cache
        cache.set(agent_id, "test_action", {"allowed": False})
        action_result = cache.get(agent_id, "test_action")
        dir_result = cache.check_directory(agent_id, directory)

        assert action_result["allowed"] is False  # Action blocked
        assert dir_result["allowed"] is True    # Directory allowed
    ```
  </action>
  <verify>
    Run: pytest backend/tests/unit/governance/test_governance_cache_performance.py -v

    Expected: 40+ tests passing, cache hit rate >90%, P50 latency <1ms, LRU eviction working
  </verify>
  <done>
    - Cache hit rate exceeds 90% after warmup
    - P50 latency <1ms for cached lookups
    - LRU eviction removes oldest entries at max_size
    - TTL expiration works correctly (60-second timeout)
    - Agent-specific invalidation removes all agent entries
    - Directory permission cache uses "dir:" prefix without collision
    - Statistics (hits, misses, hit_rate, evictions) are accurate
    - Background cleanup removes expired entries
  </done>
</task>

</tasks>

<verification>
After completing all tasks, run full test suite for governance module:

```bash
pytest backend/tests/unit/governance/test_agent_governance_maturity_routing.py -v --cov=backend/core/agent_governance_service --cov-report=term-missing
pytest backend/tests/unit/governance/test_action_complexity_matrix.py -v --cov=backend/core/agent_governance_service --cov-report=term-missing
pytest backend/tests/unit/governance/test_governance_cache_performance.py -v --cov=backend/core/governance_cache --cov-report=term-missing
```

Success criteria:
- All 118+ tests passing (28+50+40)
- Coverage on agent_governance_service.py >60%
- Coverage on governance_cache.py >60%
- No test collection errors
- All maturity levels tested against all complexity levels (4x4 matrix)
- Cache performance targets met (>90% hit rate, <1ms P50 latency)
</verification>

<success_criteria>
1. Agent maturity routing enforces correct permission gates for all 4x4 combinations
2. Action complexity matrix correctly maps 60+ actions to 4 complexity levels
3. Governance cache performance meets SLA targets (>90% hit rate, <1ms latency)
4. Test files follow established patterns (fixtures, mocks, parametrize)
5. All tests pass with zero failures
6. Code coverage increased on governance services
</success_criteria>

<output>
After completion, create `.planning/phases/05-agent-layer/05-agent-layer-01-SUMMARY.md`
</output>
