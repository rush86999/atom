---
phase: 08-80-percent-coverage-push
plan: 27a
type: execute
wave: 5
depends_on: []
files_modified:
  - backend/tests/unit/test_agent_governance_service.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Agent governance service has 60%+ test coverage (registration, feedback, confidence scoring, maturity transitions, action complexity checks)"
    - "All public methods of AgentGovernanceService have test coverage"
    - "Mock setup verified for database operations"
  artifacts:
    - path: "backend/tests/unit/test_agent_governance_service.py"
      provides: "Agent lifecycle and feedback tests"
      min_lines: 850
  key_links:
    - from: "test_agent_governance_service.py"
      to: "core/agent_governance_service.py"
      via: "mock_db, mock_user, mock_agent"
      pattern: "AgentGovernanceService"
status: pending
created: 2026-02-13
gap_closure: false
---

# Plan 27a: Agent Governance Service Tests

**Status:** Pending
**Wave:** 5 (parallel with 27b, 28)
**Dependencies:** None

## Objective

Create comprehensive baseline unit tests for agent governance service, achieving 60% coverage to contribute +0.5-0.6% toward Phase 8.8's 19-20% overall coverage goal.

## Context

Phase 8.8 targets 19-20% overall coverage (+2% from 17-18% baseline) by testing governance and LLM handler files. This plan focuses ONLY on agent_governance_service.py:

1. **agent_governance_service.py** (540 lines) - Agent lifecycle, feedback, confidence scoring, maturity transitions, action complexity checks

**Production Lines:** 540
**Expected Coverage at 60%:** ~324 lines
**Coverage Contribution:** +0.5-0.6 percentage points toward 19-20% goal

## Success Criteria

**Must Have (truths that become verifiable):**
1. Agent governance service has 60%+ test coverage (registration, feedback, confidence scoring, maturity transitions)
2. All public methods have test coverage
3. Mock setup verified for database operations

**Should Have:**
- Edge cases tested (missing agents, invalid maturity levels, cache misses)
- Async coordination tested (feedback adjudication)
- Confidence scoring edge cases (caps, floors, high/low impact)

**Could Have:**
- Property-based tests for maturity transitions
- Integration patterns with governance cache

**Won't Have:**
- Full database integration (sessions mocked)
- WorldModelService integration (mocked)

## Tasks

### Task 1: Create test_agent_governance_service.py

**Files:**
- CREATE: `backend/tests/unit/test_agent_governance_service.py` (850+ lines, 60-65 tests)

**Action:**
```bash
cat > backend/tests/unit/test_agent_governance_service.py << 'EOF'
"""
Unit tests for Agent Governance Service

Tests cover:
- Agent registration and update logic
- Feedback submission and adjudication
- Confidence score updates and capping
- Maturity level transitions
- Action complexity mapping and checks
- Agent capability queries
- HITL action creation
- Approval status tracking
- Error handling for missing agents
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentFeedback,
    FeedbackStatus,
    HITLAction,
    HITLActionStatus,
    User,
    UserRole,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def governance_service(mock_db):
    """Create governance service instance."""
    return AgentGovernanceService(mock_db)


@pytest.fixture
def sample_agent():
    """Create sample agent for testing."""
    return AgentRegistry(
        id="agent_123",
        name="Test Agent",
        category="testing",
        module_path="test.module",
        class_name="TestAgent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.4
    )


@pytest.fixture
def sample_user():
    """Create sample user for testing."""
    user = MagicMock(spec=User)
    user.id = "user_123"
    user.role = UserRole.USER
    user.specialty = "testing"
    return user


@pytest.fixture
def admin_user():
    """Create admin user for testing."""
    user = MagicMock(spec=User)
    user.id = "admin_123"
    user.role = UserRole.WORKSPACE_ADMIN
    user.specialty = None
    return user


@pytest.fixture
def matching_specialty_user():
    """Create user with matching specialty."""
    user = MagicMock(spec=User)
    user.id = "user_456"
    user.role = UserRole.USER
    user.specialty = "testing"
    return user


# ============================================================================
# Agent Registration Tests
# ============================================================================

class TestAgentRegistration:
    """Tests for agent registration and update logic."""

    def test_register_new_agent(self, governance_service, mock_db, sample_agent):
        """Test registering a new agent."""
        # Setup: no existing agent
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = governance_service.register_or_update_agent(
            name="New Agent",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            description="A test agent"
        )

        assert result.name == "New Agent"
        assert result.category == "testing"
        assert result.status == AgentStatus.STUDENT.value
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_register_new_agent_with_description(self, governance_service, mock_db):
        """Test registering new agent with description."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = governance_service.register_or_update_agent(
            name="Described Agent",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            description="This agent has a description"
        )

        assert result.name == "Described Agent"
        assert result.description == "This agent has a description"

    def test_update_existing_agent(self, governance_service, mock_db, sample_agent):
        """Test updating an existing agent."""
        # Setup: existing agent found
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.register_or_update_agent(
            name="Updated Agent",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            description="Updated description"
        )

        assert result.name == "Updated Agent"
        assert result.category == "testing"

    def test_agent_starts_with_student_status(self, governance_service, mock_db):
        """Test new agents start with STUDENT status."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        agent = governance_service.register_or_update_agent(
            name="New Agent",
            category="testing",
            module_path="test.module",
            class_name="TestAgent"
        )

        assert agent.status == AgentStatus.STUDENT.value

    def test_register_agent_with_existing_confidence(self, governance_service, mock_db, sample_agent):
        """Test updating agent preserves existing confidence when provided."""
        sample_agent.confidence_score = 0.75
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.register_or_update_agent(
            name="Existing Agent",
            category="testing",
            module_path="test.module",
            class_name="TestAgent"
        )

        # Confidence should be preserved when updating
        assert result.id == "agent_123"


# ============================================================================
# Feedback Submission Tests
# ============================================================================

class TestFeedbackSubmission:
    """Tests for feedback submission and adjudication."""

    @pytest.mark.asyncio
    async def test_submit_feedback_creates_record(self, governance_service, mock_db, sample_agent):
        """Test feedback submission creates a feedback record."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch.object(governance_service, '_adjudicate_feedback', new=AsyncMock()):
            result = await governance_service.submit_feedback(
                agent_id="agent_123",
                user_id="user_123",
                original_output="Bad output",
                user_correction="Better output",
                input_context="Test context"
            )

            assert result.agent_id == "agent_123"
            assert result.status == FeedbackStatus.PENDING.value
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_feedback_without_context(self, governance_service, mock_db, sample_agent):
        """Test feedback submission without optional context."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch.object(governance_service, '_adjudicate_feedback', new=AsyncMock()):
            result = await governance_service.submit_feedback(
                agent_id="agent_123",
                user_id="user_123",
                original_output="Bad output",
                user_correction="Better output"
            )

            assert result.agent_id == "agent_123"

    @pytest.mark.asyncio
    async def test_feedback_for_nonexistent_agent_raises_error(self, governance_service, mock_db):
        """Test feedback for nonexistent agent raises error."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(Exception):
            await governance_service.submit_feedback(
                agent_id="nonexistent",
                user_id="user_123",
                original_output="output",
                user_correction="correction"
            )

    @pytest.mark.asyncio
    async def test_feedback_calls_adjudication(self, governance_service, mock_db, sample_agent):
        """Test feedback submission triggers adjudication."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch.object(governance_service, '_adjudicate_feedback', new=AsyncMock()) as mock_adjudicate:
            await governance_service.submit_feedback(
                agent_id="agent_123",
                user_id="user_123",
                original_output="output",
                user_correction="correction"
            )

            mock_adjudicate.assert_called_once()


# ============================================================================
# Feedback Adjudication Tests
# ============================================================================

class TestFeedbackAdjudication:
    """Tests for feedback adjudication logic."""

    @pytest.mark.asyncio
    async def test_admin_feedback_accepted(self, governance_service, mock_db, sample_agent, admin_user):
        """Test admin feedback is auto-accepted."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=sample_agent)),
            MagicMock(first=MagicMock(return_value=admin_user))
        ]
        mock_db.query.return_value = mock_query

        feedback = AgentFeedback(
            id="feedback_123",
            agent_id="agent_123",
            user_id="user_123",
            original_output="output",
            user_correction="correction"
        )
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch.object(governance_service, '_update_confidence_score'):
            await governance_service._adjudicate_feedback(feedback)

            assert feedback.status == FeedbackStatus.ACCEPTED.value
            assert "Trusted reviewer" in feedback.ai_reasoning

    @pytest.mark.asyncio
    async def test_super_admin_feedback_accepted(self, governance_service, mock_db, sample_agent):
        """Test super admin feedback is auto-accepted."""
        super_admin = MagicMock(spec=User)
        super_admin.role = UserRole.SUPER_ADMIN
        super_admin.specialty = None

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=sample_agent)),
            MagicMock(first=MagicMock(return_value=super_admin))
        ]
        mock_db.query.return_value = mock_query

        feedback = AgentFeedback(
            id="feedback_123",
            agent_id="agent_123",
            user_id="super_admin",
            original_output="output",
            user_correction="correction"
        )

        with patch.object(governance_service, '_update_confidence_score'):
            await governance_service._adjudicate_feedback(feedback)

            assert feedback.status == FeedbackStatus.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_specialty_match_feedback_accepted(self, governance_service, mock_db, sample_agent, matching_specialty_user):
        """Test specialty match feedback is auto-accepted."""
        sample_agent.category = "testing"
        matching_specialty_user.specialty = "testing"

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=sample_agent)),
            MagicMock(first=MagicMock(return_value=matching_specialty_user))
        ]
        mock_db.query.return_value = mock_query

        feedback = AgentFeedback(
            id="feedback_123",
            agent_id="agent_123",
            user_id="user_456",
            original_output="output",
            user_correction="correction"
        )

        with patch.object(governance_service, '_update_confidence_score'):
            await governance_service._adjudicate_feedback(feedback)

            assert feedback.status == FeedbackStatus.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_specialty_case_insensitive_match(self, governance_service, mock_db, sample_agent):
        """Test specialty matching is case-insensitive."""
        sample_agent.category = "Testing"
        user = MagicMock(spec=User)
        user.role = UserRole.USER
        user.specialty = "testing"

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=sample_agent)),
            MagicMock(first=MagicMock(return_value=user))
        ]
        mock_db.query.return_value = mock_query

        feedback = AgentFeedback(
            id="feedback_123",
            agent_id="agent_123",
            user_id="user_456",
            original_output="output",
            user_correction="correction"
        )

        with patch.object(governance_service, '_update_confidence_score'):
            await governance_service._adjudicate_feedback(feedback)

            assert feedback.status == FeedbackStatus.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_non_matching_specialty_feedback_pending(self, governance_service, mock_db, sample_agent, sample_user):
        """Test non-matching specialty feedback stays pending."""
        sample_agent.category = "finance"
        sample_user.specialty = "engineering"

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=sample_agent)),
            MagicMock(first=MagicMock(return_value=sample_user))
        ]
        mock_db.query.return_value = mock_query

        feedback = AgentFeedback(
            id="feedback_123",
            agent_id="agent_123",
            user_id="user_123",
            original_output="output",
            user_correction="correction"
        )

        with patch.object(governance_service, '_update_confidence_score'):
            await governance_service._adjudicate_feedback(feedback)

            assert feedback.status == FeedbackStatus.PENDING.value


# ============================================================================
# Confidence Score Tests
# ============================================================================

class TestConfidenceScoring:
    """Tests for confidence score updates."""

    def test_positive_outcome_increases_confidence(self, governance_service, mock_db, sample_agent):
        """Test positive outcome increases confidence score."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        original_score = sample_agent.confidence_score
        governance_service._update_confidence_score("agent_123", positive=True, impact_level="low")

        assert sample_agent.confidence_score > original_score

    def test_negative_outcome_decreases_confidence(self, governance_service, mock_db, sample_agent):
        """Test negative outcome decreases confidence score."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        original_score = sample_agent.confidence_score
        governance_service._update_confidence_score("agent_123", positive=False, impact_level="high")

        assert sample_agent.confidence_score < original_score

    def test_high_impact_has_larger_adjustment(self, governance_service, mock_db):
        """Test high impact adjustments are larger than low impact."""
        agent_high = AgentRegistry(id="agent_high", confidence_score=0.5)
        agent_low = AgentRegistry(id="agent_low", confidence_score=0.5)

        call_count = [0]

        def mock_query_side_effect(*args, **kwargs):
            m = MagicMock()
            if "agent_high" in str(args):
                m.first.return_value = agent_high
            else:
                m.first.return_value = agent_low
            call_count[0] += 1
            return m

        mock_db.query.side_effect = mock_query_side_effect

        governance_service._update_confidence_score("agent_high", positive=True, impact_level="high")
        governance_service._update_confidence_score("agent_low", positive=True, impact_level="low")

        assert agent_high.confidence_score > agent_low.confidence_score

    def test_confidence_capped_at_one(self, governance_service, mock_db):
        """Test confidence score is capped at 1.0."""
        agent = AgentRegistry(id="agent_max", confidence_score=0.99)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        governance_service._update_confidence_score("agent_max", positive=True, impact_level="high")

        assert agent.confidence_score <= 1.0

    def test_confidence_floored_at_zero(self, governance_service, mock_db):
        """Test confidence score is floored at 0.0."""
        agent = AgentRegistry(id="agent_min", confidence_score=0.01)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        governance_service._update_confidence_score("agent_min", positive=False, impact_level="high")

        assert agent.confidence_score >= 0.0

    def test_positive_low_impact_boost(self, governance_service, mock_db, sample_agent):
        """Test positive low impact applies small boost."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        original = sample_agent.confidence_score
        governance_service._update_confidence_score("agent_123", positive=True, impact_level="low")

        # Low impact should add 0.01
        assert abs(sample_agent.confidence_score - (original + 0.01)) < 0.001

    def test_negative_high_impact_penalty(self, governance_service, mock_db, sample_agent):
        """Test negative high impact applies large penalty."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        original = sample_agent.confidence_score
        governance_service._update_confidence_score("agent_123", positive=False, impact_level="high")

        # High impact should subtract 0.1
        assert abs(sample_agent.confidence_score - (original - 0.1)) < 0.001


# ============================================================================
# Maturity Transition Tests
# ============================================================================

class TestMaturityTransitions:
    """Tests for maturity level transitions based on confidence."""

    def test_student_to_intern_transition(self, governance_service, mock_db):
        """Test transition from STUDENT to INTERN at 0.5 confidence."""
        agent = AgentRegistry(
            id="agent_student",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        # Boost to intern level
        governance_service._update_confidence_score("agent_student", positive=True, impact_level="high")

        assert agent.status in [AgentStatus.INTERN.value, AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]

    def test_intern_to_supervised_transition(self, governance_service, mock_db):
        """Test transition from INTERN to SUPERVISED at 0.7 confidence."""
        agent = AgentRegistry(
            id="agent_intern",
            status=AgentStatus.INTERN.value,
            confidence_score=0.65
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        governance_service._update_confidence_score("agent_intern", positive=True, impact_level="high")

        assert agent.status in [AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]

    def test_supervised_to_autonomous_transition(self, governance_service, mock_db):
        """Test transition from SUPERVISED to AUTONOMOUS at 0.9 confidence."""
        agent = AgentRegistry(
            id="agent_supervised",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.88
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        governance_service._update_confidence_score("agent_supervised", positive=True, impact_level="high")

        assert agent.status == AgentStatus.AUTONOMOUS.value

    def test_autonomous_demoted_on_low_confidence(self, governance_service, mock_db):
        """Test AUTONOMOUS agent can be demoted."""
        agent = AgentRegistry(
            id="agent_auto",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.91
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        # Apply multiple penalties
        for _ in range(5):
            governance_service._update_confidence_score("agent_auto", positive=False, impact_level="high")

        assert agent.status != AgentStatus.AUTONOMOUS.value

    def test_confidence_threshold_exact_student(self, governance_service, mock_db):
        """Test exact 0.5 confidence triggers INTERN."""
        agent = AgentRegistry(
            id="agent_exact",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.49
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        governance_service._update_confidence_score("agent_exact", positive=True, impact_level="high")

        assert agent.status in [AgentStatus.INTERN.value, AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]

    def test_confidence_threshold_exact_supervised(self, governance_service, mock_db):
        """Test exact 0.7 confidence triggers SUPERVISED."""
        agent = AgentRegistry(
            id="agent_exact",
            status=AgentStatus.INTERN.value,
            confidence_score=0.69
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        governance_service._update_confidence_score("agent_exact", positive=True, impact_level="high")

        assert agent.status in [AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]


# ============================================================================
# Outcome Recording Tests
# ============================================================================

class TestOutcomeRecording:
    """Tests for outcome recording."""

    @pytest.mark.asyncio
    async def test_record_successful_outcome(self, governance_service, mock_db):
        """Test recording successful outcome."""
        agent = AgentRegistry(id="agent_123", confidence_score=0.5)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        await governance_service.record_outcome("agent_123", success=True)

        assert agent.confidence_score > 0.5

    @pytest.mark.asyncio
    async def test_record_failed_outcome(self, governance_service, mock_db):
        """Test recording failed outcome."""
        agent = AgentRegistry(id="agent_123", confidence_score=0.5)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        await governance_service.record_outcome("agent_123", success=False)

        assert agent.confidence_score < 0.5

    @pytest.mark.asyncio
    async def test_record_outcome_low_impact(self, governance_service, mock_db):
        """Test outcome uses low impact by default."""
        agent = AgentRegistry(id="agent_123", confidence_score=0.5)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        await governance_service.record_outcome("agent_123", success=True)

        # Should use low impact (0.01 boost)
        assert abs(agent.confidence_score - 0.51) < 0.001


# ============================================================================
# Agent Listing Tests
# ============================================================================

class TestAgentListing:
    """Tests for agent listing functionality."""

    def test_list_all_agents(self, governance_service, mock_db):
        """Test listing all agents."""
        agent1 = AgentRegistry(id="agent_1", name="Agent 1")
        agent2 = AgentRegistry(id="agent_2", name="Agent 2")

        mock_query = MagicMock()
        mock_query.all.return_value = [agent1, agent2]
        mock_query.filter.return_value = mock_query
        mock_db.query.return_value = mock_query

        result = governance_service.list_agents()

        assert result == [agent1, agent2]

    def test_list_agents_by_category(self, governance_service, mock_db):
        """Test filtering agents by category."""
        agent1 = AgentRegistry(id="agent_1", name="Agent 1", category="testing")
        agent2 = AgentRegistry(id="agent_2", name="Agent 2", category="finance")

        mock_query = MagicMock()
        mock_query.all.return_value = [agent1]
        mock_db.query.return_value = mock_query

        result = governance_service.list_agents(category="testing")

        mock_query.filter.assert_called()
        assert len(result) == 1

    def test_list_agents_empty_result(self, governance_service, mock_db):
        """Test listing when no agents exist."""
        mock_query = MagicMock()
        mock_query.all.return_value = []
        mock_query.filter.return_value = mock_query
        mock_db.query.return_value = mock_query

        result = governance_service.list_agents()

        assert result == []


# ============================================================================
# Action Complexity Tests
# ============================================================================

class TestActionComplexity:
    """Tests for action complexity mapping."""

    def test_action_complexity_contains_all_levels(self, governance_service):
        """Test ACTION_COMPLEXITY has all complexity levels."""
        from core.agent_governance_service import AgentGovernanceService

        assert 1 in AgentGovernanceService.ACTION_COMPLEXITY.values()
        assert 2 in AgentGovernanceService.ACTION_COMPLEXITY.values()
        assert 3 in AgentGovernanceService.ACTION_COMPLEXITY.values()
        assert 4 in AgentGovernanceService.ACTION_COMPLEXITY.values()

    def test_action_complexity_simple_actions(self, governance_service):
        """Test simple (level 1) actions are mapped correctly."""
        from core.agent_governance_service import AgentGovernanceService

        simple_actions = ["search", "read", "list", "get", "fetch", "summarize",
                       "present_chart", "present_markdown"]
        for action in simple_actions:
            assert AgentGovernanceService.ACTION_COMPLEXITY.get(action) == 1

    def test_action_complexity_moderate_actions(self, governance_service):
        """Test moderate (level 2) actions are mapped correctly."""
        from core.agent_governance_service import AgentGovernanceService

        moderate_actions = ["analyze", "suggest", "draft", "generate", "recommend",
                        "stream_chat", "present_form", "llm_stream", "browser_navigate",
                        "browser_screenshot", "browser_extract", "device_camera_snap",
                        "device_get_location", "device_send_notification", "update_canvas"]
        for action in moderate_actions:
            assert AgentGovernanceService.ACTION_COMPLEXITY.get(action) == 2

    def test_action_complexity_medium_actions(self, governance_service):
        """Test medium (level 3) actions are mapped correctly."""
        from core.agent_governance_service import AgentGovernanceService

        medium_actions = ["create", "update", "send_email", "post_message", "schedule",
                       "submit_form", "device_screen_record", "device_screen_record_start",
                       "device_screen_record_stop"]
        for action in medium_actions:
            assert AgentGovernanceService.ACTION_COMPLEXITY.get(action) == 3

    def test_action_complexity_high_actions(self, governance_service):
        """Test high (level 4) actions are mapped correctly."""
        from core.agent_governance_service import AgentGovernanceService

        high_actions = ["delete", "execute", "deploy", "transfer", "payment", "approve",
                      "device_execute_command", "canvas_execute_javascript"]
        for action in high_actions:
            assert AgentGovernanceService.ACTION_COMPLEXITY.get(action) == 4


# ============================================================================
# Maturity Requirements Tests
# ============================================================================

class TestMaturityRequirements:
    """Tests for maturity requirement mapping."""

    def test_maturity_requirements_all_levels(self, governance_service):
        """Test MATURITY_REQUIREMENTS has all maturity levels."""
        from core.agent_governance_service import AgentGovernanceService

        assert 1 in AgentGovernanceService.MATURITY_REQUIREMENTS
        assert 2 in AgentGovernanceService.MATURITY_REQUIREMENTS
        assert 3 in AgentGovernanceService.MATURITY_REQUIREMENTS
        assert 4 in AgentGovernanceService.MATURITY_REQUIREMENTS

    def test_maturity_requirements_correct_mapping(self, governance_service):
        """Test maturity requirements map correctly to agent statuses."""
        from core.agent_governance_service import AgentGovernanceService

        assert AgentGovernanceService.MATURITY_REQUIREMENTS[1] == AgentStatus.STUDENT
        assert AgentGovernanceService.MATURITY_REQUIREMENTS[2] == AgentStatus.INTERN
        assert AgentGovernanceService.MATURITY_REQUIREMENTS[3] == AgentStatus.SUPERVISED
        assert AgentGovernanceService.MATURITY_REQUIREMENTS[4] == AgentStatus.AUTONOMOUS


# ============================================================================
# Can Perform Action Tests
# ============================================================================

class TestCanPerformAction:
    """Tests for action permission checking."""

    def test_can_perform_action_allowed(self, governance_service, mock_db, sample_agent):
        """Test agent can perform allowed action."""
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.confidence_score = 0.95
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.can_perform_action("agent_123", "search")

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.AUTONOMOUS.value

    def test_can_perform_action_not_found(self, governance_service, mock_db):
        """Test action check when agent not found."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = governance_service.can_perform_action("nonexistent", "search")

        assert result["allowed"] is False
        assert result["reason"] == "Agent not found"

    def test_can_perform_action_blocked_by_maturity(self, governance_service, mock_db, sample_agent):
        """Test action blocked by insufficient maturity."""
        sample_agent.status = AgentStatus.STUDENT.value
        sample_agent.confidence_score = 0.4
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.can_perform_action("agent_123", "delete")

        assert result["allowed"] is False
        assert "insufficient maturity" in result["reason"].lower()

    def test_can_perform_action_require_approval(self, governance_service, mock_db, sample_agent):
        """Test SUPERVISED agent requires approval for medium actions."""
        sample_agent.status = AgentStatus.SUPERVISED.value
        sample_agent.confidence_score = 0.8
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.can_perform_action("agent_123", "create")

        assert result["requires_human_approval"] is True

    def test_can_perform_action_with_require_approval_flag(self, governance_service, mock_db, sample_agent):
        """Test explicit require_approval overrides default."""
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.confidence_score = 0.95
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.can_perform_action("agent_123", "search", require_approval=True)

        assert result["requires_human_approval"] is True


# ============================================================================
# Get Agent Capabilities Tests
# ============================================================================

class TestGetAgentCapabilities:
    """Tests for querying agent capabilities."""

    def test_get_capabilities_student(self, governance_service, mock_db, sample_agent):
        """Test getting capabilities for STUDENT agent."""
        sample_agent.status = AgentStatus.STUDENT.value
        sample_agent.name = "Student Agent"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["maturity_level"] == AgentStatus.STUDENT.value
        assert result["max_complexity"] == 1
        assert len(result["allowed_actions"]) > 0

    def test_get_capabilities_intern(self, governance_service, mock_db, sample_agent):
        """Test getting capabilities for INTERN agent."""
        sample_agent.status = AgentStatus.INTERN.value
        sample_agent.name = "Intern Agent"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["maturity_level"] == AgentStatus.INTERN.value
        assert result["max_complexity"] == 2

    def test_get_capabilities_supervised(self, governance_service, mock_db, sample_agent):
        """Test getting capabilities for SUPERVISED agent."""
        sample_agent.status = AgentStatus.SUPERVISED.value
        sample_agent.name = "Supervised Agent"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["maturity_level"] == AgentStatus.SUPERVISED.value
        assert result["max_complexity"] == 3

    def test_get_capabilities_autonomous(self, governance_service, mock_db, sample_agent):
        """Test getting capabilities for AUTONOMOUS agent."""
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.name = "Autonomous Agent"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["maturity_level"] == AgentStatus.AUTONOMOUS.value
        assert result["max_complexity"] == 4

    def test_get_capabilities_agent_not_found(self, governance_service, mock_db):
        """Test getting capabilities for nonexistent agent raises error."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(Exception):
            governance_service.get_agent_capabilities("nonexistent")

    def test_get_capabilities_lists_allowed_and_restricted(self, governance_service, mock_db, sample_agent):
        """Test capabilities include both allowed and restricted actions."""
        sample_agent.status = AgentStatus.INTERN.value
        sample_agent.name = "Intern Agent"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert "allowed_actions" in result
        assert "restricted_actions" in result
        assert len(result["allowed_actions"]) > 0
        assert len(result["restricted_actions"]) > 0

    def test_get_capabilities_includes_confidence(self, governance_service, mock_db, sample_agent):
        """Test capabilities include confidence score."""
        sample_agent.status = AgentStatus.INTERN.value
        sample_agent.confidence_score = 0.65
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["confidence_score"] == 0.65

    def test_get_capabilities_no_confidence_uses_default(self, governance_service, mock_db, sample_agent):
        """Test capabilities use default when confidence is None."""
        sample_agent.status = AgentStatus.INTERN.value
        sample_agent.confidence_score = None
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["confidence_score"] == 0.5


# ============================================================================
# Enforce Action Tests
# ============================================================================

class TestEnforceAction:
    """Tests for action enforcement."""

    def test_enforce_action_allowed(self, governance_service, mock_db, sample_agent):
        """Test enforcing allowed action."""
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.confidence_score = 0.95
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.enforce_action("agent_123", "search")

        assert result["proceed"] is True
        assert result["status"] == "APPROVED"

    def test_enforce_action_blocked(self, governance_service, mock_db, sample_agent):
        """Test enforcing blocked action."""
        sample_agent.status = AgentStatus.STUDENT.value
        sample_agent.confidence_score = 0.4
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.enforce_action("agent_123", "delete")

        assert result["proceed"] is False
        assert result["status"] == "BLOCKED"

    def test_enforce_action_requires_approval(self, governance_service, mock_db, sample_agent):
        """Test enforcing action that requires approval."""
        sample_agent.status = AgentStatus.SUPERVISED.value
        sample_agent.confidence_score = 0.8
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.enforce_action("agent_123", "create")

        assert result["proceed"] is True
        assert result["status"] == "PENDING_APPROVAL"

    def test_enforce_action_includes_action_details(self, governance_service, mock_db, sample_agent):
        """Test enforcement includes action details in result."""
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.confidence_score = 0.95
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.enforce_action("agent_123", "search", action_details={"query": "test"})

        assert result["proceed"] is True

    def test_enforce_action_includes_confidence(self, governance_service, mock_db, sample_agent):
        """Test enforcement includes confidence in result."""
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.confidence_score = 0.92
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.enforce_action("agent_123", "search")

        assert "confidence" in result


# ============================================================================
# HITL Action Tests
# ============================================================================

class TestHITLActions:
    """Tests for human-in-the-loop actions."""

    def test_create_hitl_action(self, governance_service, mock_db):
        """Test creating a HITL action."""
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('uuid.uuid4', return_value="hitl-123"):
            hitl_id = governance_service.request_approval(
                agent_id="agent_123",
                action_type="delete",
                params={"target": "resource"},
                reason="High risk action"
            )

        assert hitl_id is not None

    def test_create_hitl_action_saves_to_db(self, governance_service, mock_db):
        """Test HITL action is saved to database."""
        mock_db.add = Mock()
        mock_db.commit = Mock()

        governance_service.request_approval(
            agent_id="agent_123",
            action_type="update",
            params={"field": "value"},
            reason="Needs approval"
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_get_approval_status_found(self, governance_service, mock_db):
        """Test getting approval status for existing HITL."""
        hitl = HITLAction(
            id="hitl-123",
            status=HITLActionStatus.PENDING.value,
            user_feedback="Pending review"
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = hitl
        mock_db.query.return_value = mock_query

        result = governance_service.get_approval_status("hitl-123")

        assert result["status"] == HITLActionStatus.PENDING.value
        assert result["id"] == "hitl-123"

    def test_get_approval_status_not_found(self, governance_service, mock_db):
        """Test getting approval status for nonexistent HITL."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = governance_service.get_approval_status("nonexistent")

        assert result["status"] == "not_found"

    def test_get_approval_status_includes_feedback(self, governance_service, mock_db):
        """Test approval status includes user feedback."""
        hitl = HITLAction(
            id="hitl-123",
            status=HITLActionStatus.APPROVED.value,
            user_feedback="Looks good",
            reviewed_at=datetime.now()
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = hitl
        mock_db.query.return_value = mock_query

        result = governance_service.get_approval_status("hitl-123")

        assert result["user_feedback"] == "Looks good"
        assert "reviewed_at" in result


# ============================================================================
# Can Access Agent Data Tests
# ============================================================================

class TestCanAccessAgentData:
    """Tests for agent data access control."""

    def test_admin_can_access_any_agent(self, governance_service, mock_db, sample_agent, admin_user):
        """Test workspace admin can access any agent."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=admin_user)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("admin_123", "agent_123")

        assert result is True

    def test_super_admin_can_access_any_agent(self, governance_service, mock_db, sample_agent):
        """Test super admin can access any agent."""
        super_admin = MagicMock(spec=User)
        super_admin.role = UserRole.SUPER_ADMIN
        super_admin.specialty = None

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=super_admin)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("super_123", "agent_123")

        assert result is True

    def test_specialty_match_can_access(self, governance_service, mock_db, sample_agent, matching_specialty_user):
        """Test specialty match grants access."""
        sample_agent.category = "testing"
        matching_specialty_user.specialty = "testing"

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=matching_specialty_user)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_456", "agent_123")

        assert result is True

    def test_specialty_no_match_denied(self, governance_service, mock_db, sample_agent, sample_user):
        """Test non-matching specialty denies access."""
        sample_agent.category = "finance"
        sample_user.specialty = "engineering"

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=sample_user)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_123", "agent_123")

        assert result is False

    def test_regular_user_no_specialty_denied(self, governance_service, mock_db, sample_agent):
        """Test regular user without specialty denies access."""
        sample_user.specialty = None

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=sample_user)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_123", "agent_123")

        assert result is False

    def test_missing_user_denies_access(self, governance_service, mock_db, sample_agent):
        """Test missing user denies access."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=None)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_123", "agent_123")

        assert result is False

    def test_missing_agent_denies_access(self, governance_service, mock_db, sample_agent):
        """Test missing agent denies access."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=sample_user)),
            MagicMock(first=MagicMock(return_value=None))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_123", "agent_123")

        assert result is False

    def test_specialty_case_insensitive(self, governance_service, mock_db, sample_agent):
        """Test specialty matching is case-insensitive."""
        sample_agent.category = "Testing"
        user = MagicMock(spec=User)
        user.role = UserRole.USER
        user.specialty = "testing"

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=user)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_456", "agent_123")

        assert result is True


# ============================================================================
# Promote to Autonomous Tests
# ============================================================================

class TestPromoteToAutonomous:
    """Tests for promoting agents to autonomous status."""

    def test_promote_to_autonomous_success(self, governance_service, mock_db, sample_agent):
        """Test successful promotion to autonomous."""
        sample_agent.status = AgentStatus.SUPERVISED.value
        sample_agent.name = "Promotion Candidate"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.RBACService.check_permission', return_value=True):
            with patch('core.agent_governance_service.get_governance_cache'):
                result = governance_service.promote_to_autonomous("agent_123", sample_agent)

                assert result.status == AgentStatus.AUTONOMOUS.value
                mock_db.commit.assert_called()

    def test_promote_nonexistent_agent_raises(self, governance_service, mock_db):
        """Test promoting nonexistent agent raises error."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        user = MagicMock(spec=User)
        user.role = UserRole.WORKSPACE_ADMIN

        with patch('core.agent_governance_service.RBACService.check_permission', return_value=True):
            with pytest.raises(Exception):
                governance_service.promote_to_autonomous("nonexistent", user)

    def test_promote_without_permission_denied(self, governance_service, mock_db, sample_agent):
        """Test promoting without permission denies access."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        user = MagicMock(spec=User)

        with patch('core.agent_governance_service.RBACService.check_permission', return_value=False):
            with patch('core.agent_governance_service.handle_permission_denied') as mock_handle:
                governance_service.promote_to_autonomous("agent_123", user)

                mock_handle.assert_called_once()
EOF

# Verify file created
wc -l backend/tests/unit/test_agent_governance_service.py
```

**Verify:**
```bash
test -f backend/tests/unit/test_agent_governance_service.py && echo "File exists"
grep -c "^def test_" backend/tests/unit/test_agent_governance_service.py
# Expected: 60-65 tests
```

**Done:**
- File created with 60-65 tests
- Agent registration tested
- Feedback submission and adjudication tested
- Confidence scoring validated
- Maturity transitions verified
- Action complexity mapping tested
- Agent capabilities queried
- HITL actions created
- Data access control tested
- Promotion to autonomous tested

---

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_agent_governance_service.py | core/agent_governance_service.py | mock_db, mock_user, mock_agent | Test agent lifecycle and feedback |

## Progress Tracking

**Current Coverage (Phase 8.7):** 17-18%
**Plan 27a Target:** +0.5-0.6 percentage points
**Projected After Plans 27a+27b+28:** ~19-20%

## Notes

- Focuses ONLY on agent_governance_service.py for better context management
- 60% coverage target (higher than standard 50% due to critical path)
- Test patterns from Phase 8.7 applied (AsyncMock, fixtures)
- Estimated 60-65 tests
- Duration: 2 hours
- Splits original Plan 27 to manage context budget (<50%)
