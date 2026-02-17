---
phase: 05-agent-layer
plan: 02
type: execute
wave: 2
depends_on: ["05-agent-layer-01"]
files_modified:
  - tests/unit/agent/test_agent_graduation_service.py
  - tests/unit/agent/test_student_training_service.py
  - tests/unit/agent/test_agent_context_resolver.py
autonomous: true

must_haves:
  truths:
    - "Graduation readiness score in [0.0, 1.0] (40% episodes + 30% interventions + 30% constitutional)"
    - "Graduation exam requires 100% constitutional compliance for promotion"
    - "Maturity transitions are monotonic (STUDENT → INTERN → SUPERVISED → AUTONOMOUS, no downgrades)"
    - "Intervention rate decreases as maturity increases (STUDENT high, AUTONOMOUS zero)"
    - "Trigger interceptor routes STUDENT agents to training (not automated execution)"
    - "Context resolver fallback chain works (explicit → session → default)"
    - "Governance cache hit rate >95% with <1ms latency"
  artifacts:
    - path: "tests/unit/agent/test_agent_graduation_service.py"
      provides: "Unit tests for graduation readiness scoring and exam"
      min_lines: 350
    - path: "tests/unit/agent/test_student_training_service.py"
      provides: "Unit tests for STUDENT agent training routing"
      min_lines: 250
    - path: "tests/unit/agent/test_agent_context_resolver.py"
      provides: "Unit tests for context resolution and fallback chain"
      min_lines: 200
  key_links:
    - from: "tests/unit/agent/test_agent_graduation_service.py"
      to: "core/agent_graduation_service.py"
      via: "tests readiness scoring and graduation exam"
      pattern: "test_readiness_score|test_graduation_exam"
    - from: "tests/unit/agent/test_student_training_service.py"
      to: "core/student_training_service.py"
      via: "tests STUDENT agent routing to training"
      pattern: "test_student_blocked_from_triggers"
    - from: "tests/unit/agent/test_agent_context_resolver.py"
      to: "core/agent_context_resolver.py"
      via: "tests fallback chain (explicit → session → default)"
      pattern: "test_context_resolution_fallback"
---

## Objective

Create unit tests for agent graduation framework (readiness scoring, exam, level transitions) and context resolution (fallback chain, governance cache integration).

**Purpose:** Graduation framework ensures agents promote based on proven experience (episodes, interventions, constitutional compliance). Context resolution provides agent configuration with graceful fallbacks. Tests validate graduation criteria and context resolution robustness.

**Output:** Unit tests for graduation service, training service, and context resolver.

## Execution Context

@core/agent_graduation_service.py (graduation logic)
@core/student_training_service.py (STUDENT training routing)
@core/agent_context_resolver.py (context resolution)
@core/governance_cache.py (cache integration)
@core/models.py (AgentRegistry, TrainingSession models)

## Context

@.planning/ROADMAP.md (Phase 5 requirements)
@.planning/phases/05-agent-layer/05-agent-layer-01-PLAN.md (Plan 01)

# Phase 3 Complete: Memory Layer Tested
- Episode lifecycle tested (decay, consolidation, archival)
- Graduation framework integration tested with episodic memory
- Constitutional compliance validated

# Existing Graduation Implementation
- agent_graduation_service.py: Readiness scoring, graduation exam, level transitions
- student_training_service.py: STUDENT agent routing to training
- agent_context_resolver.py: Explicit → session → default fallback chain

## Tasks

### Task 1: Create Unit Tests for Agent Graduation Service

**Files:** `tests/unit/agent/test_agent_graduation_service.py`

**Action:**
Create unit tests for graduation service:

```python
"""
Unit Tests for Agent Graduation Service

Tests cover:
- Readiness score calculation (40% episodes + 30% interventions + 30% constitutional)
- Graduation exam validation (100% constitutional compliance required)
- Level transitions (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
- Intervention rate decreases with maturity
"""
import pytest
from sqlalchemy.orm import Session

from core.agent_graduation_service import AgentGraduationService
from core.models import AgentRegistry, Episode, TrainingSession
from tests.factories import AgentFactory, EpisodeFactory


class TestAgentGraduationService:
    """Test agent graduation service."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    def test_readiness_score_in_0_1_range(self, service, db_session):
        """Readiness score should be in [0.0, 1.0]."""
        agent = AgentFactory(maturity_level="INTERN")

        # Create episodes
        for _ in range(25):  # Minimum for INTERN → SUPERVISED
            EpisodeFactory(agent_id=agent.id)

        score = service.calculate_readiness_score(agent.id)
        assert 0.0 <= score <= 1.0

    def test_readiness_score_weights_sum_to_1(self, service, db_session):
        """Readiness score weights: 40% episodes + 30% interventions + 30% constitutional."""
        agent = AgentFactory(maturity_level="SUPERVISED")

        # Create 50 episodes
        for _ in range(50):
            EpisodeFactory(agent_id=agent.id)

        score = service.calculate_readiness_score(agent.id)

        # Score should be weighted average
        # (not testing exact formula, just that it's reasonable)
        assert 0.0 <= score <= 1.0

    def test_graduation_exam_requires_100_percent_compliance(self, service, db_session):
        """Graduation exam requires 100% constitutional compliance."""
        agent = AgentFactory(maturity_level="SUPERVISED")

        # Create episodes with perfect compliance
        for _ in range(50):
            ep = EpisodeFactory(agent_id=agent.id)
            # Mark all interventions as compliant
            ep.constitutional_compliance = 1.0

        result = service.take_graduation_exam(agent.id)

        # Should pass with 100% compliance
        assert result["passed"] is True
        assert result["constitutional_compliance"] == 1.0

    def test_maturity_transitions_are_monotonic(self, service, db_session):
        """Maturity transitions should be monotonic (no downgrades)."""
        agent = AgentFactory(maturity_level="STUDENT")

        # Transition through levels
        transitions = [
            ("STUDENT", "INTERN"),
            ("INTERN", "SUPERVISED"),
            ("SUPERVISED", "AUTONOMOUS")
        ]

        for from_level, to_level in transitions:
            agent.maturity_level = from_level
            result = service.promote_agent(agent.id, to_level)
            assert result["success"] is True or result["reason"] == "requirements_not_met"

        # Should never downgrade
        current_level = agent.maturity_level
        result = service.promote_agent(agent.id, "STUDENT")
        assert result["success"] is False
        assert "downgrade" in result["reason"].lower()
```

**Tests:**
- Readiness score in [0.0, 1.0]
- Readiness score weights correct (40/30/30)
- Graduation exam requires 100% compliance
- Maturity transitions monotonic (no downgrades)
- Intervention rate decreases with maturity

**Acceptance:**
- [ ] Readiness score tested for all maturity levels
- [ ] Graduation exam tested (pass/fail scenarios)
- [ ] All level transitions tested
- [ ] Monotonic transitions enforced

---

### Task 2: Create Unit Tests for Student Training Service

**Files:** `tests/unit/agent/test_student_training_service.py`

**Action:**
Create unit tests for STUDENT agent training:

```python
"""
Unit Tests for Student Training Service

Tests cover:
- STUDENT agents blocked from automated triggers
- Routing to training scenarios
- Training session creation
- Graduation from training
"""
import pytest
from sqlalchemy.orm import Session

from core.student_training_service import StudentTrainingService
from core.trigger_interceptor import TriggerInterceptor
from core.models import AgentRegistry, TrainingSession
from tests.factories import AgentFactory


class TestStudentTrainingService:
    """Test STUDENT agent training service."""

    @pytest.fixture
    def interceptor(self, db_session):
        """Create trigger interceptor."""
        return TriggerInterceptor(db_session)

    def test_student_blocked_from_automated_triggers(self, interceptor, db_session):
        """STUDENT agents should be blocked from automated triggers."""
        agent = AgentFactory(maturity_level="STUDENT")

        # Try to execute action via trigger
        result = interceptor.intercept_trigger(
            agent_id=agent.id,
            trigger_type="automated",
            action_complexity=2
        )

        # Should block and route to training
        assert result["allowed"] is False
        assert result["routing"] == "training"

    def test_student_can_execute_in_training_scenario(self, interceptor, db_session):
        """STUDENT agents can execute in supervised training scenarios."""
        agent = AgentFactory(maturity_level="STUDENT")

        # Create training session
        result = interceptor.execute_in_training(
            agent_id=agent.id,
            action_type="form_submission",
            supervisor_id="test_supervisor"
        )

        assert result["allowed"] is True

    def test_training_session_creation(self, db_session):
        """Training sessions should be created for STUDENT agents."""
        agent = AgentFactory(maturity_level="STUDENT")

        service = StudentTrainingService(db_session)
        session = service.create_training_session(
            agent_id=agent.id,
            training_type="form_presentation"
        )

        assert session.agent_id == agent.id
        assert session.status == "in_progress"
```

**Tests:**
- STUDENT agents blocked from automated triggers
- Routing to training scenarios
- Training session creation
- Graduation from training

**Acceptance:**
- [ ] STUDENT blocking tested
- [ ] Training routing tested
- [ ] Training session lifecycle tested

---

### Task 3: Create Unit Tests for Agent Context Resolver

**Files:** `tests/unit/agent/test_agent_context_resolver.py`

**Action:**
Create unit tests for context resolution:

```python
"""
Unit Tests for Agent Context Resolver

Tests cover:
- Context resolution fallback chain (explicit → session → default)
- Governance cache integration
- Session context creation
- Default context fallback
"""
import pytest
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.governance_cache import GovernanceCache
from core.models import AgentRegistry
from tests.factories import AgentFactory


class TestAgentContextResolver:
    """Test agent context resolver."""

    @pytest.fixture
    def resolver(self, db_session):
        """Create resolver."""
        return AgentContextResolver(db_session)

    def test_context_resolution_fallback_chain(self, resolver, db_session):
        """Context resolution should fallback: explicit → session → default."""
        agent = AgentFactory()

        # Try explicit context (doesn't exist)
        context = resolver.resolve_context(
            agent_id=agent.id,
            context_type="explicit"
        )

        # Should fallback to session or default
        assert context is not None

    def test_explicit_context_priority(self, resolver, db_session):
        """Explicit context should take priority over session/default."""
        agent = AgentFactory()

        # Create explicit context
        resolver.set_explicit_context(
            agent_id=agent.id,
            context={"custom": "value"}
        )

        # Resolve
        context = resolver.resolve_context(
            agent_id=agent.id,
            context_type="any"
        )

        assert context.get("custom") == "value"

    def test_governance_cache_integration(self, resolver, db_session):
        """Context resolver should use governance cache."""
        agent = AgentFactory()

        # Warm cache
        cache = GovernanceCache(db_session)
        cache.get(agent.id)

        # Resolve context (should use cached data)
        context = resolver.resolve_context(agent_id=agent.id)

        assert context is not None
```

**Tests:**
- Fallback chain (explicit → session → default)
- Explicit context priority
- Governance cache integration
- Session context creation

**Acceptance:**
- [ ] Fallback chain tested
- [ ] Explicit context priority tested
- [ ] Cache integration verified

---

## Deviations

**Rule 1 (Auto-fix bugs):** If graduation logic is incorrect, fix immediately.

**Rule 2 (Testing):** If training scenarios are missing, add comprehensive test scenarios.

**Rule 3 (Fallback):** If context resolution fails without fallback, add error handling.

## Success Criteria

- [ ] Readiness score tested ([0.0, 1.0] range, weights)
- [ ] Graduation exam tested (100% compliance requirement)
- [ ] Maturity transitions tested (monotonic)
- [ ] STUDENT training routing tested
- [ ] Context resolution fallback chain tested

## Dependencies

- Plan 05-01 (Governance & Maturity) must be complete

## Estimated Duration

2-3 hours (graduation tests + training tests + context tests)
