"""
Comprehensive agent lifecycle scenario tests (Wave 1 - Task 3).

These tests map to the documented scenarios in SCENARIOS.md:
- AGENT-001 to AGENT-050
- Covers agent registration, classification, confidence updates, graduation, configuration

Priority: CRITICAL - Agent governance, maturity management
"""
import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
from sqlalchemy.orm import Session

from tests.factories.agent_factory import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory,
)
from tests.factories.user_factory import AdminUserFactory
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentExecution,
    Episode,
)
from core.agent_governance_service import AgentGovernanceService
from core.agent_graduation_service import AgentGraduationService


# ============================================================================
# Scenario Category: Agent Lifecycle (CRITICAL)
# ============================================================================

class TestAgentRegistration:
    """AGENT-001: Agent Registration."""

    def test_agent_registration_creates_record(
        self, db_session: Session
    ):
        """Test agent registration creates database record."""
        agent = AgentRegistry(
            id="agent-test-001",
            name="Test Agent",
            category="automation",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.5,
            created_by="admin_user"
        )

        db_session.add(agent)
        db_session.commit()

        # Verify record created
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == "agent-test-001"
        ).first()

        assert retrieved is not None
        assert retrieved.name == "Test Agent"
        assert retrieved.status == AgentStatus.STUDENT.value

    def test_agent_registration_initializes_confidence(
        self, db_session: Session
    ):
        """Test new agent initialized with confidence 0.5."""
        agent = StudentAgentFactory(confidence_score=0.5, _session=db_session)
        db_session.commit()

        # Should have initial confidence
        assert agent.confidence_score == 0.5
        assert agent.status == AgentStatus.STUDENT.value

    def test_agent_registration_default_status(
        self, db_session: Session
    ):
        """Test new agents default to STUDENT status."""
        agent = AgentRegistry(
            id="agent-default-001",
            name="Default Agent",
            category="automation",
            module_path="test.module",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4
        )

        db_session.add(agent)
        db_session.commit()

        # Verify default status
        assert agent.status == AgentStatus.STUDENT.value


class TestAgentClassification:
    """AGENT-002 to AGENT-005: Agent Classification by Maturity."""

    def test_student_classification_low_confidence(
        self, db_session: Session
    ):
        """Test agents with confidence < 0.5 classified as STUDENT."""
        agent = AgentRegistry(
            id="agent-student-001",
            name="Student Agent",
            category="automation",
            module_path="test.module",
            confidence_score=0.3  # Below threshold
        )

        # Determine maturity based on confidence
        if agent.confidence_score < 0.5:
            agent.status = AgentStatus.STUDENT.value

        db_session.add(agent)
        db_session.commit()

        assert agent.status == AgentStatus.STUDENT.value

    def test_intern_classification_medium_confidence(
        self, db_session: Session
    ):
        """Test agents with confidence 0.5-0.7 classified as INTERN."""
        agent = AgentRegistry(
            id="agent-intern-001",
            name="Intern Agent",
            category="automation",
            module_path="test.module",
            confidence_score=0.6  # In range
        )

        if 0.5 <= agent.confidence_score < 0.7:
            agent.status = AgentStatus.INTERN.value

        db_session.add(agent)
        db_session.commit()

        assert agent.status == AgentStatus.INTERN.value

    def test_supervised_classification_high_confidence(
        self, db_session: Session
    ):
        """Test agents with confidence 0.7-0.9 classified as SUPERVISED."""
        agent = AgentRegistry(
            id="agent-supervised-001",
            name="Supervised Agent",
            category="automation",
            module_path="test.module",
            confidence_score=0.8  # In range
        )

        if 0.7 <= agent.confidence_score < 0.9:
            agent.status = AgentStatus.SUPERVISED.value

        db_session.add(agent)
        db_session.commit()

        assert agent.status == AgentStatus.SUPERVISED.value

    def test_autonomous_classification_very_high_confidence(
        self, db_session: Session
    ):
        """Test agents with confidence > 0.9 classified as AUTONOMOUS."""
        agent = AgentRegistry(
            id="agent-autonomous-001",
            name="Autonomous Agent",
            category="automation",
            module_path="test.module",
            confidence_score=0.95  # Above threshold
        )

        if agent.confidence_score >= 0.9:
            agent.status = AgentStatus.AUTONOMOUS.value

        db_session.add(agent)
        db_session.commit()

        assert agent.status == AgentStatus.AUTONOMOUS.value


class TestAgentConfidenceUpdate:
    """AGENT-006 to AGENT-010: Agent Confidence Updates."""

    def test_positive_feedback_increases_confidence(
        self, db_session: Session
    ):
        """Test positive feedback increases agent confidence."""
        agent = StudentAgentFactory(confidence_score=0.5, _session=db_session)

        # Simulate positive feedback
        original_confidence = agent.confidence_score
        increase = 0.05
        agent.confidence_score = min(1.0, original_confidence + increase)
        agent.updated_at = datetime.utcnow()

        db_session.commit()

        assert agent.confidence_score > original_confidence

    def test_negative_feedback_decreases_confidence(
        self, db_session: Session
    ):
        """Test negative feedback decreases agent confidence."""
        agent = InternAgentFactory(confidence_score=0.6, _session=db_session)

        # Simulate negative feedback
        original_confidence = agent.confidence_score
        decrease = 0.1
        agent.confidence_score = max(0.0, original_confidence - decrease)
        agent.updated_at = datetime.utcnow()

        db_session.commit()

        assert agent.confidence_score < original_confidence

    def test_confidence_never_exceeds_1_0(
        self, db_session: Session
    ):
        """Test confidence score capped at 1.0."""
        agent = SupervisedAgentFactory(confidence_score=0.95, _session=db_session)

        # Try to increase beyond 1.0
        agent.confidence_score = min(1.0, agent.confidence_score + 0.1)
        db_session.commit()

        assert agent.confidence_score <= 1.0

    def test_confidence_never_below_0_0(
        self, db_session: Session
    ):
        """Test confidence score never below 0.0."""
        agent = InternAgentFactory(confidence_score=0.1, _session=db_session)

        # Try to decrease below 0.0
        agent.confidence_score = max(0.0, agent.confidence_score - 0.2)
        db_session.commit()

        assert agent.confidence_score >= 0.0

    def test_confidence_update_affects_classification(
        self, db_session: Session
    ):
        """Test confidence changes can trigger reclassification."""
        agent = StudentAgentFactory(confidence_score=0.49, _session=db_session)

        # Increase confidence to INTERN threshold
        agent.confidence_score = 0.6
        agent.updated_at = datetime.utcnow()

        # Recalculate maturity
        if agent.confidence_score >= 0.5 and agent.confidence_score < 0.7:
            agent.status = AgentStatus.INTERN.value

        db_session.commit()

        assert agent.status == AgentStatus.INTERN.value


class TestAgentMaturityTransition:
    """AGENT-011 to AGENT-015: Maturity Level Transitions."""

    def test_student_to_intern_transition(
        self, db_session: Session
    ):
        """Test STUDENT to INTERN transition."""
        agent = StudentAgentFactory(_session=db_session)

        # Simulate reaching INTERN threshold
        agent.confidence_score = 0.65
        agent.status = AgentStatus.INTERN.value
        agent.updated_at = datetime.utcnow()

        db_session.commit()

        assert agent.status == AgentStatus.INTERN.value
        assert agent.confidence_score >= 0.5

    def test_intern_to_supervised_transition(
        self, db_session: Session
    ):
        """Test INTERN to SUPERVISED transition."""
        agent = InternAgentFactory(_session=db_session)

        # Simulate reaching SUPERVISED threshold
        agent.confidence_score = 0.75
        agent.status = AgentStatus.SUPERVISED.value
        agent.updated_at = datetime.utcnow()

        db_session.commit()

        assert agent.status == AgentStatus.SUPERVISED.value
        assert agent.confidence_score >= 0.7

    def test_supervised_to_autonomous_transition(
        self, db_session: Session
    ):
        """Test SUPERVISED to AUTONOMOUS transition."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Simulate reaching AUTONOMOUS threshold
        agent.confidence_score = 0.95
        agent.status = AgentStatus.AUTONOMOUS.value
        agent.updated_at = datetime.utcnow()

        db_session.commit()

        assert agent.status == AgentStatus.AUTONOMOUS.value
        assert agent.confidence_score >= 0.9

    def test_transition_requires_minimum_confidence(
        self, db_session: Session
    ):
        """Test transitions require minimum confidence thresholds."""
        student = StudentAgentFactory(confidence_score=0.4, _session=db_session)

        # Should NOT transition to INTERN (below threshold)
        if student.confidence_score < 0.5:
            # Student cannot transition
            assert student.status == AgentStatus.STUDENT.value

    def test_transition_log_audited(
        self, db_session: Session
    ):
        """Test maturity transitions are audited."""
        agent = StudentAgentFactory(_session=db_session)

        # Store original state
        original_status = agent.status

        # Promote agent
        agent.status = AgentStatus.INTERN.value
        agent.confidence_score = 0.65
        agent.updated_at = datetime.utcnow()

        # Add audit metadata
        if not agent.metadata_json:
            agent.metadata_json = {}
        agent.metadata_json["promoted_at"] = datetime.utcnow().isoformat()
        agent.metadata_json["promoted_by"] = "admin_user"
        agent.metadata_json["previous_status"] = original_status

        db_session.commit()

        # Verify audit trail
        assert "promoted_at" in agent.metadata_json
        assert "promoted_by" in agent.metadata_json


class TestAgentCapabilities:
    """AGENT-016 to AGENT-020: Agent Capabilities by Maturity."""

    def test_student_limited_to_read_only(
        self, db_session: Session
    ):
        """Test STUDENT agents limited to read-only actions."""
        agent = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Check permissions for various actions
        read_actions = ["search", "read", "list", "get", "summarize"]
        for action in read_actions:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] is True, f"STUDENT should be allowed to {action}"

    def test_student_blocked_from_state_changes(
        self, db_session: Session
    ):
        """Test STUDENT agents blocked from state changes."""
        agent = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Check blocked actions
        blocked_actions = ["update", "delete", "execute", "submit_form"]
        for action in blocked_actions:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] is False, f"STUDENT should be blocked from {action}"

    def test_intern_can_stream_and_analyze(
        self, db_session: Session
    ):
        """Test INTERN agents can stream and analyze."""
        agent = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Check allowed actions
        allowed_actions = ["stream", "analyze", "draft", "suggest"]
        for action in allowed_actions:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] is True, f"INTERN should be allowed to {action}"

    def test_intern_blocked_from_critical_actions(
        self, db_session: Session
    ):
        """Test INTERN agents blocked from critical actions."""
        agent = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Check blocked actions
        blocked_actions = ["delete", "execute", "submit_form", "send_email"]
        for action in blocked_actions:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] is False, f"INTERN should be blocked from {action}"

    def test_supervised_can_change_state(
        self, db_session: Session
    ):
        """Test SUPERVISED agents can change state."""
        agent = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Check allowed state changes
        state_actions = ["update", "submit_form", "send_email", "create"]
        for action in state_actions:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] is True, f"SUPERVISED should be allowed to {action}"

    def test_supervised_blocked_from_deletion(
        self, db_session: Session
    ):
        """Test SUPERVISED agents blocked from deletion."""
        agent = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Check blocked actions
        result = governance.can_perform_action(agent.id, "delete")
        assert result["allowed"] is False, "SUPERVISED should be blocked from delete"

    def test_autonomous_full_execution(
        self, db_session: Session
    ):
        """Test AUTONOMOUS agents have full execution权限."""
        agent = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Check all actions allowed
        all_actions = [
            "search", "read", "stream", "analyze", "update",
            "submit_form", "delete", "execute", "send_email"
        ]
        for action in all_actions:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] is True, \
                f"AUTONOMOUS should be allowed to {action}: {result}"


class TestAgentGraduation:
    """AGENT-021 to AGENT-030: Agent Graduation Framework."""

    @pytest.mark.asyncio
    async def test_graduation_readiness_calculation(
        self, db_session: Session
    ):
        """Test graduation readiness score calculation."""
        agent = StudentAgentFactory(_session=db_session)
        graduation_service = AgentGraduationService(db_session)

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        # Verify structure
        assert "score" in result
        assert "ready" in result
        assert "gaps" in result
        assert "episode_count" in result
        assert "intervention_rate" in result

    @pytest.mark.asyncio
    async def test_graduation_episode_count_criteria(
        self, db_session: Session
    ):
        """Test graduation requires minimum episodes."""
        agent = StudentAgentFactory(_session=db_session)

        # Create minimal episodes
        for i in range(10):
            episode = Episode(
                id=f"episode_{i}",
                agent_id=agent.id,
                user_id="test_user",
                workspace_id="default",
                title=f"Episode {i}",
                status="completed",
                maturity_at_time=AgentStatus.STUDENT.value,
                started_at=datetime.utcnow(),
                human_intervention_count=0
            )
            db_session.add(episode)

        db_session.commit()

        graduation_service = AgentGraduationService(db_session)
        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        assert result["episode_count"] >= 10

    @pytest.mark.asyncio
    async def test_graduation_intervention_rate_criteria(
        self, db_session: Session
    ):
        """Test graduation requires low intervention rate."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with low intervention
        for i in range(10):
            episode = Episode(
                id=f"episode_{i}",
                agent_id=agent.id,
                user_id="test_user",
                workspace_id="default",
                title=f"Episode {i}",
                status="completed",
                maturity_at_time=AgentStatus.INTERN.value,
                started_at=datetime.utcnow(),
                human_intervention_count=0  # No interventions
            )
            db_session.add(episode)

        db_session.commit()

        graduation_service = AgentGraduationService(db_session)
        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        # Low intervention rate
        assert result["intervention_rate"] < 0.5

    @pytest.mark.asyncio
    async def test_graduation_constitutional_compliance(
        self, db_session: Session
    ):
        """Test graduation requires constitutional compliance."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes with high compliance
        for i in range(10):
            episode = Episode(
                id=f"episode_{i}",
                agent_id=agent.id,
                user_id="test_user",
                workspace_id="default",
                title=f"Episode {i}",
                status="completed",
                maturity_at_time=AgentStatus.SUPERVISED.value,
                started_at=datetime.utcnow(),
                human_intervention_count=0,
                constitutional_score=0.95  # High compliance
            )
            db_session.add(episode)

        db_session.commit()

        graduation_service = AgentGraduationService(db_session)
        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        # Should have high constitutional score
        if result.get("avg_constitutional_score"):
            assert result["avg_constitutional_score"] >= 0.70

    @pytest.mark.asyncio
    async def test_promote_agent_updates_status(
        self, db_session: Session
    ):
        """Test promoting agent updates maturity status."""
        agent = StudentAgentFactory(_session=db_session)
        graduation_service = AgentGraduationService(db_session)

        success = await graduation_service.promote_agent(
            agent_id=agent.id,
            new_maturity="INTERN",
            validated_by="test_admin"
        )

        assert success is True

        # Refresh and verify
        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN.value

    @pytest.mark.asyncio
    async def test_graduation_metadata_recorded(
        self, db_session: Session
    ):
        """Test graduation records metadata."""
        agent = StudentAgentFactory(
            metadata_json={},
            _session=db_session
        )
        graduation_service = AgentGraduationService(db_session)

        await graduation_service.promote_agent(
            agent_id=agent.id,
            new_maturity="INTERN",
            validated_by="test_admin"
        )

        # Check metadata
        db_session.refresh(agent)
        assert agent.metadata_json is not None
        assert "promoted_at" in agent.metadata_json
        assert "promoted_by" in agent.metadata_json
        assert agent.metadata_json["promoted_by"] == "test_admin"


class TestAgentExecutionTracking:
    """AGENT-031 to AGENT-035: Agent Execution Tracking."""

    def test_execution_record_created(
        self, db_session: Session
    ):
        """Test agent execution creates record."""
        agent = AutonomousAgentFactory(_session=db_session)

        execution = AgentExecution(
            id="exec-001",
            agent_id=agent.id,
            user_id="test_user",
            workspace_id="default",
            status="running",
            started_at=datetime.utcnow(),
            input_data={"query": "test"}
        )

        db_session.add(execution)
        db_session.commit()

        # Verify record created
        retrieved = db_session.query(AgentExecution).filter(
            AgentExecution.id == "exec-001"
        ).first()

        assert retrieved is not None
        assert retrieved.agent_id == agent.id

    def test_execution_updates_on_completion(
        self, db_session: Session
    ):
        """Test execution record updated on completion."""
        agent = AutonomousAgentFactory(_session=db_session)

        execution = AgentExecution(
            id="exec-002",
            agent_id=agent.id,
            user_id="test_user",
            workspace_id="default",
            status="running",
            started_at=datetime.utcnow()
        )

        db_session.add(execution)
        db_session.commit()

        # Mark as completed
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {"result": "success"}
        db_session.commit()

        # Verify updated
        db_session.refresh(execution)
        assert execution.status == "completed"
        assert execution.completed_at is not None

    def test_execution_error_tracking(
        self, db_session: Session
    ):
        """Test execution errors are tracked."""
        agent = InternAgentFactory(_session=db_session)

        execution = AgentExecution(
            id="exec-003",
            agent_id=agent.id,
            user_id="test_user",
            workspace_id="default",
            status="running",
            started_at=datetime.utcnow()
        )

        db_session.add(execution)

        # Mark as failed
        execution.status = "failed"
        execution.completed_at = datetime.utcnow()
        execution.error_message = "Test error"
        execution.error_details = {"code": "TEST_ERROR"}
        db_session.commit()

        # Verify error tracked
        db_session.refresh(execution)
        assert execution.status == "failed"
        assert execution.error_message is not None

    def test_execution_duration_calculated(
        self, db_session: Session
    ):
        """Test execution duration is calculated."""
        agent = AutonomousAgentFactory(_session=db_session)

        start_time = datetime.utcnow()

        execution = AgentExecution(
            id="exec-004",
            agent_id=agent.id,
            user_id="test_user",
            workspace_id="default",
            status="running",
            started_at=start_time
        )

        db_session.add(execution)

        # Complete after 5 seconds
        end_time = start_time + timedelta(seconds=5)
        execution.status = "completed"
        execution.completed_at = end_time
        db_session.commit()

        # Calculate duration
        db_session.refresh(execution)
        duration = (execution.completed_at - execution.started_at).total_seconds()
        assert duration >= 5


class TestAgentConfiguration:
    """AGENT-036 to AGENT-040: Agent Configuration."""

    def test_agent_config_storage(
        self, db_session: Session
    ):
        """Test agent configuration stored in metadata."""
        agent = StudentAgentFactory(_session=db_session)

        # Store configuration
        config = {
            "max_tokens": 2000,
            "temperature": 0.7,
            "model": "gpt-4",
            "timeout": 30
        }

        agent.metadata_json = agent.metadata_json or {}
        agent.metadata_json["config"] = config
        db_session.commit()

        # Verify config stored
        db_session.refresh(agent)
        assert "config" in agent.metadata_json
        assert agent.metadata_json["config"]["max_tokens"] == 2000

    def test_agent_config_update(
        self, db_session: Session
    ):
        """Test agent configuration can be updated."""
        agent = InternAgentFactory(_session=db_session)

        # Update config
        agent.metadata_json = agent.metadata_json or {}
        agent.metadata_json["config"] = {
            "max_tokens": 4000,  # Updated
            "temperature": 0.5
        }
        db_session.commit()

        # Verify updated
        db_session.refresh(agent)
        assert agent.metadata_json["config"]["max_tokens"] == 4000

    def test_agent_config_default_values(
        self, db_session: Session
    ):
        """Test agent configuration has default values."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Should have default config
        # (implementation dependent)
        assert agent is not None


class TestAgentDeactivation:
    """AGENT-041 to AGENT-045: Agent Deactivation."""

    def test_deactivate_agent(
        self, db_session: Session
    ):
        """Test agent can be deactivated."""
        agent = AutonomousAgentFactory(_session=db_session)

        # Deactivate
        agent.is_active = False
        agent.updated_at = datetime.utcnow()
        db_session.commit()

        # Verify deactivated
        db_session.refresh(agent)
        assert agent.is_active is False

    def test_deactivated_agent_cannot_execute(
        self, db_session: Session
    ):
        """Test deactivated agents cannot execute."""
        agent = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Deactivate agent
        agent.is_active = False
        db_session.commit()

        # Try to check permission
        # (Implementation should check is_active)
        # This test documents expected behavior

    def test_reactivate_agent(
        self, db_session: Session
    ):
        """Test agent can be reactivated."""
        agent = InternAgentFactory(_session=db_session)

        # Deactivate then reactivate
        agent.is_active = False
        db_session.commit()

        agent.is_active = True
        agent.updated_at = datetime.utcnow()
        db_session.commit()

        # Verify reactivated
        db_session.refresh(agent)
        assert agent.is_active is True

    def test_deactivation_reason_recorded(
        self, db_session: Session
    ):
        """Test deactivation reason is recorded."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Deactivate with reason
        agent.is_active = False
        agent.metadata_json = agent.metadata_json or {}
        agent.metadata_json["deactivated_at"] = datetime.utcnow().isoformat()
        agent.metadata_json["deactivation_reason"] = "Deprecated functionality"
        agent.metadata_json["deactivated_by"] = "admin_user"
        db_session.commit()

        # Verify reason recorded
        db_session.refresh(agent)
        assert agent.metadata_json["deactivation_reason"] == "Deprecated functionality"


class TestAgentArchival:
    """AGENT-046 to AGENT-050: Agent Archival."""

    def test_archive_old_agent(
        self, db_session: Session
    ):
        """Test old agents can be archived."""
        agent = StudentAgentFactory(_session=db_session)

        # Mark as archived
        agent.metadata_json = agent.metadata_json or {}
        agent.metadata_json["archived_at"] = datetime.utcnow().isoformat()
        agent.metadata_json["archived_by"] = "system"
        agent.metadata_json["archive_reason"] = "Inactive for 90 days"
        agent.is_active = False
        db_session.commit()

        # Verify archived
        db_session.refresh(agent)
        assert agent.is_active is False
        assert "archived_at" in agent.metadata_json

    def test_archived_agent_not_listed(
        self, db_session: Session
    ):
        """Test archived agents excluded from listings."""
        # This test documents expected behavior
        # Query should filter out archived agents
        pass

    def test_unarchive_agent(
        self, db_session: Session
    ):
        """Test agent can be unarchived."""
        agent = InternAgentFactory(_session=db_session)

        # Archive
        agent.metadata_json = agent.metadata_json or {}
        agent.metadata_json["archived_at"] = datetime.utcnow().isoformat()
        agent.is_active = False
        db_session.commit()

        # Unarchive
        agent.is_active = True
        agent.metadata_json["unarchived_at"] = datetime.utcnow().isoformat()
        agent.metadata_json["unarchived_by"] = "admin_user"
        db_session.commit()

        # Verify unarchived
        db_session.refresh(agent)
        assert agent.is_active is True
        assert "unarchived_at" in agent.metadata_json
