"""Unit tests for Agent Governance Service

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
    return AgentGovernanceService(mock_db)


@pytest.fixture
def sample_agent():
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
    user = MagicMock(spec=User)
    user.id = "user_123"
    user.role = UserRole.MEMBER
    user.specialty = "testing"
    return user


@pytest.fixture
def admin_user():
    user = MagicMock(spec=User)
    user.id = "admin_123"
    user.role = UserRole.WORKSPACE_ADMIN
    user.specialty = None
    return user


@pytest.fixture
def matching_specialty_user():
    user = MagicMock(spec=User)
    user.id = "user_456"
    user.role = UserRole.MEMBER
    user.specialty = "testing"
    return user


class TestAgentRegistration:
    def test_register_new_agent(self, governance_service, mock_db):
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

        assert result.id == "agent_123"


class TestFeedbackSubmission:
    @pytest.mark.asyncio
    async def test_submit_feedback_creates_record(self, governance_service, mock_db, sample_agent):
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


class TestConfidenceScoring:
    def test_positive_outcome_increases_confidence(self, governance_service, mock_db, sample_agent):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        original_score = sample_agent.confidence_score
        governance_service._update_confidence_score("agent_123", positive=True, impact_level="low")

        assert sample_agent.confidence_score > original_score

    def test_negative_outcome_decreases_confidence(self, governance_service, mock_db, sample_agent):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        original_score = sample_agent.confidence_score
        governance_service._update_confidence_score("agent_123", positive=False, impact_level="high")

        assert sample_agent.confidence_score < original_score

    def test_confidence_capped_at_one(self, governance_service, mock_db):
        agent = AgentRegistry(id="agent_max", confidence_score=0.99)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        governance_service._update_confidence_score("agent_max", positive=True, impact_level="high")

        assert agent.confidence_score <= 1.0

    def test_confidence_floored_at_zero(self, governance_service, mock_db):
        agent = AgentRegistry(id="agent_min", confidence_score=0.01)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        governance_service._update_confidence_score("agent_min", positive=False, impact_level="high")

        assert agent.confidence_score >= 0.0

    def test_positive_low_impact_boost(self, governance_service, mock_db, sample_agent):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        original = sample_agent.confidence_score
        governance_service._update_confidence_score("agent_123", positive=True, impact_level="low")

        assert abs(sample_agent.confidence_score - (original + 0.01)) < 0.001

    def test_negative_high_impact_penalty(self, governance_service, mock_db, sample_agent):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        original = sample_agent.confidence_score
        governance_service._update_confidence_score("agent_123", positive=False, impact_level="high")

        assert abs(sample_agent.confidence_score - (original - 0.1)) < 0.001


class TestMaturityTransitions:
    def test_student_to_intern_transition(self, governance_service, mock_db):
        agent = AgentRegistry(
            id="agent_student",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.45  # Just below intern threshold
        )

        def mock_query_side_effect(*args, **kwargs):
            m = MagicMock()
            m.filter.return_value.first.return_value = agent
            return m

        mock_db.query.side_effect = mock_query_side_effect

        governance_service._update_confidence_score("agent_student", positive=True, impact_level="high")

        assert agent.status in ["intern", "supervised", "autonomous"]

    def test_intern_to_supervised_transition(self, governance_service, mock_db):
        agent = AgentRegistry(
            id="agent_intern",
            status=AgentStatus.INTERN.value,
            confidence_score=0.65
        )

        def mock_query_side_effect(*args, **kwargs):
            m = MagicMock()
            m.filter.return_value.first.return_value = agent
            return m

        mock_db.query.side_effect = mock_query_side_effect

        governance_service._update_confidence_score("agent_intern", positive=True, impact_level="high")

        assert agent.status in ["supervised", "autonomous"]

    def test_supervised_to_autonomous_transition(self, governance_service, mock_db):
        agent = AgentRegistry(
            id="agent_supervised",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.88
        )

        def mock_query_side_effect(*args, **kwargs):
            m = MagicMock()
            m.filter.return_value.first.return_value = agent
            return m

        mock_db.query.side_effect = mock_query_side_effect

        governance_service._update_confidence_score("agent_supervised", positive=True, impact_level="high")

        assert agent.status == "autonomous"

    def test_autonomous_demoted_on_low_confidence(self, governance_service, mock_db):
        agent = AgentRegistry(
            id="agent_auto",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.91
        )

        def mock_query_side_effect(*args, **kwargs):
            m = MagicMock()
            m.filter.return_value.first.return_value = agent
            return m

        mock_db.query.side_effect = mock_query_side_effect

        for _ in range(5):
            governance_service._update_confidence_score("agent_auto", positive=False, impact_level="high")

        assert agent.status != "autonomous"


class TestOutcomeRecording:
    @pytest.mark.asyncio
    async def test_record_successful_outcome(self, governance_service, mock_db):
        agent = AgentRegistry(id="agent_123", confidence_score=0.5)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        await governance_service.record_outcome("agent_123", success=True)

        assert agent.confidence_score > 0.5

    @pytest.mark.asyncio
    async def test_record_failed_outcome(self, governance_service, mock_db):
        agent = AgentRegistry(id="agent_123", confidence_score=0.5)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        await governance_service.record_outcome("agent_123", success=False)

        assert agent.confidence_score < 0.5

    @pytest.mark.asyncio
    async def test_record_outcome_low_impact(self, governance_service, mock_db):
        agent = AgentRegistry(id="agent_123", confidence_score=0.5)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        await governance_service.record_outcome("agent_123", success=True)

        assert abs(agent.confidence_score - 0.51) < 0.001


class TestAgentListing:
    def test_list_all_agents(self, governance_service, mock_db):
        agent1 = AgentRegistry(id="agent_1", name="Agent 1")
        agent2 = AgentRegistry(id="agent_2", name="Agent 2")

        mock_query = MagicMock()
        mock_query.all.return_value = [agent1, agent2]
        mock_query.filter.return_value = mock_query
        mock_db.query.return_value = mock_query

        result = governance_service.list_agents()

        assert result == [agent1, agent2]

    def test_list_agents_by_category(self, governance_service, mock_db):
        agent1 = AgentRegistry(id="agent_1", name="Agent 1", category="testing")
        agent2 = AgentRegistry(id="agent_2", name="Agent 2", category="finance")

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [agent1]
        mock_db.query.return_value = mock_query

        result = governance_service.list_agents(category="testing")

        mock_query.filter.assert_called()
        assert len(result) == 1

    def test_list_agents_empty_result(self, governance_service, mock_db):
        mock_query = MagicMock()
        mock_query.all.return_value = []
        mock_query.filter.return_value = mock_query
        mock_db.query.return_value = mock_query

        result = governance_service.list_agents()

        assert result == []


class TestActionComplexity:
    def test_action_complexity_contains_all_levels(self):
        from core.agent_governance_service import AgentGovernanceService

        assert 1 in AgentGovernanceService.ACTION_COMPLEXITY.values()
        assert 2 in AgentGovernanceService.ACTION_COMPLEXITY.values()
        assert 3 in AgentGovernanceService.ACTION_COMPLEXITY.values()
        assert 4 in AgentGovernanceService.ACTION_COMPLEXITY.values()

    def test_action_complexity_simple_actions(self):
        from core.agent_governance_service import AgentGovernanceService

        simple_actions = ["search", "read", "list", "get", "fetch", "summarize",
                       "present_chart", "present_markdown"]
        for action in simple_actions:
            assert AgentGovernanceService.ACTION_COMPLEXITY.get(action) == 1

    def test_action_complexity_moderate_actions(self):
        from core.agent_governance_service import AgentGovernanceService

        moderate_actions = ["analyze", "suggest", "draft", "generate", "recommend",
                        "stream_chat", "present_form", "llm_stream", "browser_navigate",
                        "browser_screenshot", "browser_extract", "device_camera_snap",
                        "device_get_location", "device_send_notification", "update_canvas"]
        for action in moderate_actions:
            assert AgentGovernanceService.ACTION_COMPLEXITY.get(action) == 2

    def test_action_complexity_medium_actions(self):
        from core.agent_governance_service import AgentGovernanceService

        medium_actions = ["create", "update", "send_email", "post_message", "schedule",
                       "submit_form", "device_screen_record", "device_screen_record_start",
                       "device_screen_record_stop"]
        for action in medium_actions:
            assert AgentGovernanceService.ACTION_COMPLEXITY.get(action) == 3

    def test_action_complexity_high_actions(self):
        from core.agent_governance_service import AgentGovernanceService

        high_actions = ["delete", "execute", "deploy", "transfer", "payment", "approve",
                      "device_execute_command", "canvas_execute_javascript"]
        for action in high_actions:
            assert AgentGovernanceService.ACTION_COMPLEXITY.get(action) == 4


class TestMaturityRequirements:
    def test_maturity_requirements_all_levels(self):
        from core.agent_governance_service import AgentGovernanceService

        assert 1 in AgentGovernanceService.MATURITY_REQUIREMENTS
        assert 2 in AgentGovernanceService.MATURITY_REQUIREMENTS
        assert 3 in AgentGovernanceService.MATURITY_REQUIREMENTS
        assert 4 in AgentGovernanceService.MATURITY_REQUIREMENTS

    def test_maturity_requirements_correct_mapping(self):
        from core.agent_governance_service import AgentGovernanceService

        assert AgentGovernanceService.MATURITY_REQUIREMENTS[1] == AgentStatus.STUDENT
        assert AgentGovernanceService.MATURITY_REQUIREMENTS[2] == AgentStatus.INTERN
        assert AgentGovernanceService.MATURITY_REQUIREMENTS[3] == AgentStatus.SUPERVISED
        assert AgentGovernanceService.MATURITY_REQUIREMENTS[4] == AgentStatus.AUTONOMOUS


class TestCanPerformAction:
    def test_can_perform_action_allowed(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.confidence_score = 0.95
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            result = governance_service.can_perform_action("agent_123", "search")

            assert result["allowed"] is True
            assert result["agent_status"] == AgentStatus.AUTONOMOUS.value

    def test_can_perform_action_not_found(self, governance_service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            result = governance_service.can_perform_action("nonexistent", "search")

            assert result["allowed"] is False
            assert result["reason"] == "Agent not found"

    def test_can_perform_action_blocked_by_maturity(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.STUDENT.value
        sample_agent.confidence_score = 0.4
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            result = governance_service.can_perform_action("agent_123", "delete")

            assert result["allowed"] is False
            assert "insufficient maturity" in result["reason"].lower() or "lacks maturity" in result["reason"].lower()

    def test_can_perform_action_require_approval(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.SUPERVISED.value
        sample_agent.confidence_score = 0.8
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            result = governance_service.can_perform_action("agent_123", "create")

            assert result["requires_human_approval"] is True

    def test_can_perform_action_with_require_approval_flag(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.confidence_score = 0.95
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            result = governance_service.can_perform_action("agent_123", "search", require_approval=True)

            assert result["requires_human_approval"] is True


class TestGetAgentCapabilities:
    def test_get_capabilities_student(self, governance_service, mock_db, sample_agent):
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
        sample_agent.status = AgentStatus.INTERN.value
        sample_agent.name = "Intern Agent"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["maturity_level"] == AgentStatus.INTERN.value
        assert result["max_complexity"] == 2

    def test_get_capabilities_supervised(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.SUPERVISED.value
        sample_agent.name = "Supervised Agent"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["maturity_level"] == AgentStatus.SUPERVISED.value
        assert result["max_complexity"] == 3

    def test_get_capabilities_autonomous(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.name = "Autonomous Agent"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["maturity_level"] == AgentStatus.AUTONOMOUS.value
        assert result["max_complexity"] == 4

    def test_get_capabilities_agent_not_found(self, governance_service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(Exception):
            governance_service.get_agent_capabilities("nonexistent")

    def test_get_capabilities_lists_allowed_and_restricted(self, governance_service, mock_db, sample_agent):
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
        sample_agent.status = AgentStatus.INTERN.value
        sample_agent.confidence_score = 0.65
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["confidence_score"] == 0.65

    def test_get_capabilities_no_confidence_uses_default(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.INTERN.value
        sample_agent.confidence_score = None
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        result = governance_service.get_agent_capabilities("agent_123")

        assert result["confidence_score"] == 0.5


class TestEnforceAction:
    def test_enforce_action_allowed(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.AUTONOMOUS.value
        sample_agent.confidence_score = 0.95
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            result = governance_service.enforce_action("agent_123", "search")

            assert result["proceed"] is True
            assert result["status"] == "APPROVED"

    def test_enforce_action_blocked(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.STUDENT.value
        sample_agent.confidence_score = 0.4
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            result = governance_service.enforce_action("agent_123", "delete")

            assert result["proceed"] is False
            assert result["status"] == "BLOCKED"

    def test_enforce_action_requires_approval(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.SUPERVISED.value
        sample_agent.confidence_score = 0.8
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            result = governance_service.enforce_action("agent_123", "create")

            assert result["proceed"] is True
            assert result["status"] == "PENDING_APPROVAL"


class TestHITLActions:
    def test_create_hitl_action(self, governance_service, mock_db):
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = "hitl-123"
            hitl_id = governance_service.request_approval(
                agent_id="agent_123",
                action_type="delete",
                params={"target": "resource"},
                reason="High risk action"
            )

        assert hitl_id is not None

    def test_create_hitl_action_saves_to_db(self, governance_service, mock_db):
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
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = governance_service.get_approval_status("nonexistent")

        assert result["status"] == "not_found"

    def test_get_approval_status_includes_feedback(self, governance_service, mock_db):
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


class TestCanAccessAgentData:
    def test_admin_can_access_any_agent(self, governance_service, mock_db, sample_agent, admin_user):
        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=admin_user)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("admin_123", "agent_123")

        assert result is True

    def test_super_admin_can_access_any_agent(self, governance_service, mock_db, sample_agent):
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
        sample_agent.category = "testing"
        matching_specialty_user.specialty = "testing"

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=matching_specialty_user)),
            MagicMock(first=Mock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_456", "agent_123")

        assert result is True

    def test_specialty_no_match_denied(self, governance_service, mock_db, sample_agent, sample_user):
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
        user = MagicMock(spec=User)
        user.role = UserRole.MEMBER
        user.specialty = None

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=user)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_123", "agent_123")

        assert result is False

    def test_missing_user_denies_access(self, governance_service, mock_db, sample_agent):
        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=None)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_123", "agent_123")

        assert result is False

    def test_missing_agent_denies_access(self, governance_service, mock_db, sample_user):
        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=sample_user)),
            MagicMock(first=MagicMock(return_value=None))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_123", "agent_123")

        assert result is False

    def test_specialty_case_insensitive(self, governance_service, mock_db, sample_agent):
        sample_agent.category = "Testing"
        user = MagicMock(spec=User)
        user.role = UserRole.MEMBER
        user.specialty = "testing"

        mock_query = MagicMock()
        mock_query.filter.side_effect = [
            MagicMock(first=MagicMock(return_value=user)),
            MagicMock(first=MagicMock(return_value=sample_agent))
        ]
        mock_db.query.return_value = mock_query

        result = governance_service.can_access_agent_data("user_456", "agent_123")

        assert result is True


class TestPromoteToAutonomous:
    def test_promote_to_autonomous_success(self, governance_service, mock_db, sample_agent):
        sample_agent.status = AgentStatus.SUPERVISED.value
        sample_agent.name = "Promotion Candidate"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        user = MagicMock(spec=User)
        user.role = UserRole.WORKSPACE_ADMIN

        with patch('core.rbac_service.RBACService.check_permission', return_value=True):
            with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
                mock_cache_inst = MagicMock()
                mock_cache.return_value = mock_cache_inst
                result = governance_service.promote_to_autonomous("agent_123", user)

                assert result.status == "autonomous"
                mock_db.commit.assert_called()

    def test_promote_nonexistent_agent_raises(self, governance_service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        user = MagicMock(spec=User)
        user.role = UserRole.WORKSPACE_ADMIN

        with patch('core.rbac_service.RBACService.check_permission', return_value=True):
            with pytest.raises(Exception):
                governance_service.promote_to_autonomous("nonexistent", user)

    def test_promote_without_permission_denied(self, governance_service, mock_db, sample_agent):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        user = MagicMock(spec=User)
        user.role = UserRole.MEMBER

        with patch('core.rbac_service.RBACService.check_permission', return_value=False):
            # handle_permission_denied raises HTTPException, so we expect the call to raise
            with patch('core.agent_governance_service.handle_permission_denied') as mock_handle:
                mock_handle.side_effect = Exception("Permission denied")
                with pytest.raises(Exception, match="Permission denied"):
                    governance_service.promote_to_autonomous("agent_123", user)

                mock_handle.assert_called_once_with("promote", "Agent")
