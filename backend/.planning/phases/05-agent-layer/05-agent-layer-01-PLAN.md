---
phase: 05-agent-layer
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/property_tests/agent/test_agent_governance_invariants.py
  - tests/unit/agent/test_agent_governance_service.py
  - tests/unit/agent/test_governance_cache.py
autonomous: true

must_haves:
  truths:
    - "All 4 maturity levels have correct action access (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)"
    - "STUDENT agents blocked from complexity 3-4 actions (forms, state changes, deletions)"
    - "INTERN agents require proposals for complexity 2-4 actions (human approval required)"
    - "SUPERVISED agents execute under real-time monitoring with pause capability"
    - "AUTONOMOUS agents have full access to all actions"
    - "Governance cache achieves >95% hit rate with <1ms lookup latency"
    - "Action complexity matrix enforced (1: presentation, 2: streaming, 3: state change, 4: deletion)"
  artifacts:
    - path: "tests/property_tests/agent/test_agent_governance_invariants.py"
      provides: "Property tests for maturity routing invariants"
      min_lines: 400
    - path: "tests/unit/agent/test_agent_governance_service.py"
      provides: "Unit tests for agent governance service edge cases"
      min_lines: 300
    - path: "tests/unit/agent/test_governance_cache.py"
      provides: "Unit tests for governance cache performance"
      min_lines: 200
  key_links:
    - from: "tests/property_tests/agent/test_agent_governance_invariants.py"
      to: "core/agent_governance_service.py"
      via: "tests maturity routing decisions"
      pattern: "test_maturity_routing|test_action_complexity_matrix"
    - from: "tests/unit/agent/test_governance_cache.py"
      to: "core/governance_cache.py"
      via: "tests cache hit rate and latency"
      pattern: "test_cache_hit_rate|test_cache_latency"
---

## Objective

Create comprehensive tests for agent governance system including maturity routing (4 levels), action complexity matrix (1-4), permission checks, and governance cache performance.

**Purpose:** Agent governance is critical for AI safety - ensures agents only take actions appropriate to their maturity level. Tests validate STUDENT agents can't perform dangerous actions, INTERN agents require human approval, SUPERVISED agents are monitored, and AUTONOMOUS agents have full access.

**Output:** Property tests for governance invariants, unit tests for edge cases, performance tests for cache.

## Execution Context

@core/agent_governance_service.py (existing governance logic)
@core/agent_context_resolver.py (context resolution)
@core/governance_cache.py (performance cache)
@core/models.py (AgentRegistry, AgentExecution models)
@.planning/ROADMAP.md (Phase 5 requirements)

## Context

@.planning/PROJECT.md
@.planning/REQUIREMENTS.md

# Phase 2 Complete: Core Invariants Tested
- Property-based testing established (Hypothesis)
- Governance invariants tested (confidence scores, maturity routing)
- Cache performance tested (<10ms target achieved)

# Phase 3 Complete: Memory Layer Tested
- Episode segmentation and retrieval tested
- Graduation framework integration tested
- Constitutional compliance validated

# Existing Agent Governance Implementation
- agent_governance_service.py: Maturity checks, permission evaluation
- governance_cache.py: <1ms cached lookups, >95% hit rate
- agent_context_resolver.py: Explicit → session → default fallback chain

## Tasks

### Task 1: Create Property Tests for Agent Governance Invariants

**Files:** `tests/property_tests/agent/test_agent_governance_invariants.py`

**Action:**
Create property-based tests for governance invariants using Hypothesis:

```python
"""
Property-Based Tests for Agent Governance Invariants

Tests CRITICAL governance invariants:
- Maturity routing is deterministic (same inputs → same decisions)
- Action complexity matrix enforced (1-4)
- STUDENT agents blocked from complexity 3-4 actions
- INTERN agents require proposals for complexity 2-4
- SUPERVISED agents monitored for complexity 2-4
- AUTONOMOUS agents have full access
- Confidence scores in [0.0, 1.0]
- Governance cache hit rate >95%
"""
import pytest
from hypothesis import strategies as st, given, settings
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache
from core.models import AgentRegistry, AgentExecution
from tests.factories import AgentFactory


class TestMaturityRoutingInvariants:
    """Property tests for maturity routing determinism and correctness."""

    @pytest.fixture
    def service(self, db_session):
        """Create AgentGovernanceService."""
        return AgentGovernanceService(db_session)

    @given(
        maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
        action_complexity=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=100)
    def test_maturity_routing_deterministic(self, service, maturity, action_complexity):
        """
        Maturity routing is deterministic invariant.

        Property: Same (maturity, action_complexity) always produces same allow/deny decision.
        """
        agent = AgentFactory(maturity_level=maturity)

        # Check permission twice
        decision1 = service.check_action_permission(
            agent_id=agent.id,
            action_complexity=action_complexity
        )
        decision2 = service.check_action_permission(
            agent_id=agent.id,
            action_complexity=action_complexity
        )

        # Should be identical
        assert decision1["allowed"] == decision2["allowed"]
        assert decision1["reason"] == decision2["reason"]

    @given(
        complexity=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=50)
    def test_student_blocked_from_high_complexity(self, service, db_session, complexity):
        """
        STUDENT agents blocked from complexity 3-4 invariant.

        Property: STUDENT agents always denied actions with complexity >= 3.
        """
        agent = AgentFactory(maturity_level="STUDENT")

        if complexity >= 3:
            decision = service.check_action_permission(
                agent_id=agent.id,
                action_complexity=complexity
            )
            assert decision["allowed"] is False
            assert "STUDENT" in decision["reason"]


class TestActionComplexityMatrixInvariants:
    """Property tests for action complexity matrix enforcement."""

    @given(
        maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
        complexity=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=200)
    def test_complexity_matrix_enforced(self, service, maturity, complexity):
        """
        Action complexity matrix invariant.

        Property: Each maturity level has specific complexity access.
        """
        agent = AgentFactory(maturity_level=maturity)
        decision = service.check_action_permission(
            agent_id=agent.id,
            action_complexity=complexity
        )

        # Define allowed complexity by maturity
        allowed_by_maturity = {
            "STUDENT": [1],  # Presentations only
            "INTERN": [1, 2],  # Presentations + Streaming
            "SUPERVISED": [1, 2, 3],  # + State changes
            "AUTONOMOUS": [1, 2, 3, 4]  # Full access
        }

        if complexity in allowed_by_maturity[maturity]:
            assert decision["allowed"] is True
        else:
            assert decision["allowed"] is False


class TestGovernanceCachePerformance:
    """Property tests for governance cache performance."""

    @pytest.fixture
    def cache(self, db_session):
        """Create GovernanceCache."""
        return GovernanceCache(db_session)

    @given(
        agent_id=st.uuids(),
        num_queries=st.integers(min_value=10, max_value=1000)
    )
    @settings(max_examples=50)
    def test_cache_hit_rate_gt_95_percent(self, cache, agent_id, num_queries):
        """
        Cache hit rate >95% invariant.

        Property: Repeated queries for same agent_id should hit cache >95% of time.
        """
        # Warm cache
        cache.get(agent_id)

        # Measure hits
        hits = 0
        for _ in range(num_queries):
            result = cache.get(agent_id)
            if result is not None:
                hits += 1

        hit_rate = hits / num_queries
        assert hit_rate > 0.95, f"Cache hit rate should be >95%, got {hit_rate:.1%}"
```

**Tests:**
- Maturity routing determinism (same inputs → same decisions)
- STUDENT blocked from complexity 3-4
- Action complexity matrix enforced (all 4 maturity levels)
- Cache hit rate >95%
- Cache latency <1ms

**Acceptance:**
- [ ] Property tests cover all maturity levels
- [ ] All 16 maturity/complexity combinations tested
- [ ] Cache performance validated (>95% hit rate, <1ms latency)

---

### Task 2: Create Unit Tests for Agent Governance Service

**Files:** `tests/unit/agent/test_agent_governance_service.py`

**Action:**
Create unit tests for edge cases:

```python
"""
Unit Tests for Agent Governance Service

Tests cover:
- Permission checks for all maturity levels
- Proposal workflow for INTERN agents
- Supervision setup for SUPERVISED agents
- Audit logging
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentProposal, SupervisionSession
from tests.factories import AgentFactory


class TestAgentGovernanceService:
    """Test agent governance service."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGovernanceService(db_session)

    def test_student_allowed_presentation_only(self, service, db_session):
        """STUDENT agents allowed complexity 1 (presentations) only."""
        agent = AgentFactory(maturity_level="STUDENT")

        # Complexity 1: Allowed
        decision = service.check_action_permission(
            agent_id=agent.id,
            action_complexity=1
        )
        assert decision["allowed"] is True

        # Complexity 2: Denied
        decision = service.check_action_permission(
            agent_id=agent.id,
            action_complexity=2
        )
        assert decision["allowed"] is False

    def test_intern_requires_proposal_for_complexity_2(self, service, db_session):
        """INTERN agents require proposal for complexity 2+ actions."""
        agent = AgentFactory(maturity_level="INTERN")

        # Complexity 2: Should require proposal
        decision = service.check_action_permission(
            agent_id=agent.id,
            action_complexity=2
        )
        assert "proposal" in decision["reason"].lower()

    def test_supervised_requires_monitoring(self, service, db_session):
        """SUPERVISED agents require monitoring for complexity 2+ actions."""
        agent = AgentFactory(maturity_level="SUPERVISED")

        decision = service.check_action_permission(
            agent_id=agent.id,
            action_complexity=3
        )
        assert decision["allowed"] is True
        assert "supervision" in decision["reason"].lower()

    def test_autonomous_full_access(self, service, db_session):
        """AUTONOMOUS agents have full access to all actions."""
        agent = AgentFactory(maturity_level="AUTONOMOUS")

        for complexity in [1, 2, 3, 4]:
            decision = service.check_action_permission(
                agent_id=agent.id,
                action_complexity=complexity
            )
            assert decision["allowed"] is True
```

**Tests:**
- STUDENT agent permissions (complexity 1 only)
- INTERN agent proposal workflow
- SUPERVISED agent monitoring
- AUTONOMOUS agent full access
- Audit logging

**Acceptance:**
- [ ] All 4 maturity levels tested
- [ ] Edge cases covered (unknown agent, invalid complexity)
- [ ] Audit logging verified

---

### Task 3: Create Performance Tests for Governance Cache

**Files:** `tests/unit/agent/test_governance_cache.py`

**Action:**
Create performance tests for governance cache:

```python
"""
Unit Tests for Governance Cache Performance

Tests cover:
- Cache hit rate (>95% target)
- Cache latency (<1ms target)
- Cache invalidation
- Cache warming
"""
import pytest
import time
from sqlalchemy.orm import Session

from core.governance_cache import GovernanceCache
from core.models import AgentRegistry
from tests.factories import AgentFactory


class TestGovernanceCachePerformance:
    """Test governance cache performance."""

    @pytest.fixture
    def cache(self, db_session):
        """Create cache."""
        return GovernanceCache(db_session)

    def test_cache_hit_rate_gt_95_percent(self, cache, db_session):
        """Cache hit rate should exceed 95%."""
        # Create 100 agents
        agents = [AgentFactory() for _ in range(100)]
        db_session.commit()

        # Warm cache
        for agent in agents:
            cache.get(agent.id)

        # Measure hit rate
        hits = 0
        queries = 1000
        for _ in range(queries):
            agent_id = agents[_ % len(agents)].id
            result = cache.get(agent_id)
            if result is not None:
                hits += 1

        hit_rate = hits / queries
        assert hit_rate > 0.95, f"Hit rate {hit_rate:.1%} should exceed 95%"

    def test_cache_latency_lt_1ms(self, cache, db_session):
        """Cache lookup should be <1ms (P99)."""
        agent = AgentFactory()
        db_session.commit()

        # Warm cache
        cache.get(agent.id)

        # Measure P99 latency
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            cache.get(agent.id)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms

        # Sort and get P99
        latencies.sort()
        p99_latency = latencies[int(0.99 * len(latencies))]

        assert p99_latency < 1.0, f"P99 latency {p99_latency:.3f}ms should be <1ms"
```

**Tests:**
- Cache hit rate >95%
- Cache latency <1ms (P99)
- Cache invalidation on agent updates
- Cache warming strategy

**Acceptance:**
- [ ] Hit rate >95% verified
- [ ] Latency <1ms verified (P99)
- [ ] Invalidation tested

---

## Deviations

**Rule 1 (Auto-fix bugs):** If governance service has incorrect permission logic, fix immediately.

**Rule 2 (Performance):** If cache doesn't meet <1ms target, optimize or increase cache size.

**Rule 3 (Edge cases):** If unknown agents or invalid complexities crash service, add error handling.

## Success Criteria

- [ ] Property tests for maturity routing (determinism, matrix enforcement)
- [ ] Unit tests for all 4 maturity levels
- [ ] Performance tests for cache (>95% hit rate, <1ms latency)
- [ ] All tests passing

## Dependencies

None (Wave 1 - independent plan)

## Estimated Duration

2-3 hours (property tests + unit tests + performance tests)
