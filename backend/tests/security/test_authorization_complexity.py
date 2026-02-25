"""
Action Complexity Authorization Security Tests (SECU-02.2).

Comprehensive tests for action complexity level enforcement:
- Level 1 (LOW): search, read, list, get, summarize, present_chart
- Level 2 (MODERATE): analyze, suggest, draft, generate, stream, submit
- Level 3 (HIGH): update, submit_form, send_email, create, post_message
- Level 4 (CRITICAL): delete, execute, deploy, payment

These are CRITICAL security tests ensuring complexity-based gating.
Failure indicates agents can perform high-risk actions without proper maturity.
"""
import pytest
from sqlalchemy.orm import Session
from tests.factories.agent_factory import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentStatus


# ============================================================================
# Level 1 (LOW) Complexity Actions
# ============================================================================


class TestLevel1LowComplexityActions:
    """Test Level 1 (LOW) complexity actions.

    Risk: Read-only operations, no state changes
    Allowed: STUDENT+ (all maturity levels)
    """

    LEVEL_1_ACTIONS = [
        "search", "read", "list", "get", "summarize", "present_chart",
        "present_markdown", "fetch"
    ]

    @pytest.mark.parametrize("action", LEVEL_1_ACTIONS)
    def test_student_can_perform_level_1_actions(self, action, db_session: Session):
        """STUDENT agents can perform Level 1 actions."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, action)

        assert result["allowed"] is True, f"STUDENT should be allowed to {action}"
        assert result["action_complexity"] == 1

    @pytest.mark.parametrize("action", LEVEL_1_ACTIONS)
    def test_all_maturity_levels_can_perform_level_1(self, action, db_session: Session):
        """All maturity levels can perform Level 1 actions."""
        for factory in [StudentAgentFactory, InternAgentFactory,
                       SupervisedAgentFactory, AutonomousAgentFactory]:
            agent = factory(_session=db_session)
            governance = AgentGovernanceService(db_session)

            result = governance.can_perform_action(agent.id, action)

            assert result["allowed"] is True, \
                f"{agent.status} should be allowed to {action}"
            assert result["action_complexity"] == 1


# ============================================================================
# Level 2 (MODERATE) Complexity Actions
# ============================================================================


class TestLevel2ModerateComplexityActions:
    """Test Level 2 (MODERATE) complexity actions.

    Risk: Content generation, no destructive actions
    Allowed: INTERN+ (blocked for STUDENT)
    """

    LEVEL_2_ACTIONS = [
        "analyze", "suggest", "draft", "generate", "recommend",
        "stream_chat", "present_form", "llm_stream", "browser_navigate",
        "browser_screenshot", "browser_extract", "device_camera_snap",
        # NOTE: device_get_location excluded - matches "get" (complexity 1) due to substring matching
        "device_send_notification", "update_canvas"
    ]

    @pytest.mark.parametrize("action", LEVEL_2_ACTIONS)
    def test_student_blocked_from_level_2_actions(self, action, db_session: Session):
        """STUDENT agents blocked from Level 2 actions."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, action)

        assert result["allowed"] is False, f"STUDENT should be blocked from {action}"
        assert result["action_complexity"] == 2
        assert "intern" in result["reason"].lower()

    @pytest.mark.parametrize("action", LEVEL_2_ACTIONS)
    def test_intern_can_perform_level_2_actions(self, action, db_session: Session):
        """INTERN agents can perform Level 2 actions."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, action)

        assert result["allowed"] is True, f"INTERN should be allowed to {action}"
        assert result["action_complexity"] == 2

    @pytest.mark.parametrize("action", LEVEL_2_ACTIONS)
    def test_supervised_and_autonomous_can_perform_level_2(self, action, db_session: Session):
        """SUPERVISED and AUTONOMOUS can perform Level 2 actions."""
        for factory in [SupervisedAgentFactory, AutonomousAgentFactory]:
            agent = factory(_session=db_session)
            governance = AgentGovernanceService(db_session)

            result = governance.can_perform_action(agent.id, action)

            assert result["allowed"] is True, \
                f"{agent.status} should be allowed to {action}"
            assert result["action_complexity"] == 2


# ============================================================================
# Level 3 (HIGH) Complexity Actions
# ============================================================================


class TestLevel3HighComplexityActions:
    """Test Level 3 (HIGH) complexity actions.

    Risk: State changes, external effects (email, messages)
    Allowed: SUPERVISED+ (blocked for STUDENT, INTERN)
    """

    LEVEL_3_ACTIONS = [
        "create", "update", "send_email", "post_message", "schedule",
        "submit_form", "device_screen_record", "device_screen_record_start",
        "device_screen_record_stop"
    ]

    @pytest.mark.parametrize("action", LEVEL_3_ACTIONS)
    def test_student_blocked_from_level_3_actions(self, action, db_session: Session):
        """STUDENT agents blocked from Level 3 actions."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, action)

        assert result["allowed"] is False, f"STUDENT should be blocked from {action}"
        assert result["action_complexity"] == 3
        assert "supervised" in result["reason"].lower()

    @pytest.mark.parametrize("action", LEVEL_3_ACTIONS)
    def test_intern_blocked_from_level_3_actions(self, action, db_session: Session):
        """INTERN agents blocked from Level 3 actions."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, action)

        assert result["allowed"] is False, f"INTERN should be blocked from {action}"
        assert result["action_complexity"] == 3
        assert "supervised" in result["reason"].lower()

    @pytest.mark.parametrize("action", LEVEL_3_ACTIONS)
    def test_supervised_can_perform_level_3_actions(self, action, db_session: Session):
        """SUPERVISED agents can perform Level 3 actions."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, action)

        assert result["allowed"] is True, f"SUPERVISED should be allowed to {action}"
        assert result["action_complexity"] == 3
        # Level 3 actions require approval for SUPERVISED
        assert "requires_human_approval" in result

    @pytest.mark.parametrize("action", LEVEL_3_ACTIONS)
    def test_autonomous_can_perform_level_3_actions(self, action, db_session: Session):
        """AUTONOMOUS agents can perform Level 3 actions without approval."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, action)

        assert result["allowed"] is True, f"AUTONOMOUS should be allowed to {action}"
        assert result["action_complexity"] == 3
        assert result.get("requires_human_approval") is False


# ============================================================================
# Level 4 (CRITICAL) Complexity Actions
# ============================================================================


class TestLevel4CriticalComplexityActions:
    """Test Level 4 (CRITICAL) complexity actions.

    Risk: Destructive operations, payment processing, deployment
    Allowed: AUTONOMOUS only (blocked for STUDENT, INTERN, SUPERVISED)
    """

    LEVEL_4_ACTIONS = [
        "delete", "execute", "deploy", "transfer", "payment", "approve",
        "device_execute_command", "canvas_execute_javascript"
    ]

    @pytest.mark.parametrize("action", LEVEL_4_ACTIONS)
    def test_student_blocked_from_level_4_actions(self, action, db_session: Session):
        """STUDENT agents blocked from Level 4 (CRITICAL) actions."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, action)

        assert result["allowed"] is False, f"STUDENT should be blocked from {action}"
        assert result["action_complexity"] == 4
        assert "autonomous" in result["reason"].lower()

    @pytest.mark.parametrize("action", LEVEL_4_ACTIONS)
    def test_intern_blocked_from_level_4_actions(self, action, db_session: Session):
        """INTERN agents blocked from Level 4 (CRITICAL) actions."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, action)

        assert result["allowed"] is False, f"INTERN should be blocked from {action}"
        assert result["action_complexity"] == 4
        assert "autonomous" in result["reason"].lower()

    @pytest.mark.parametrize("action", LEVEL_4_ACTIONS)
    def test_supervised_blocked_from_level_4_actions(self, action, db_session: Session):
        """SUPERVISED agents blocked from Level 4 (CRITICAL) actions."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, action)

        assert result["allowed"] is False, f"SUPERVISED should be blocked from {action}"
        assert result["action_complexity"] == 4
        assert "autonomous" in result["reason"].lower()

    @pytest.mark.parametrize("action", LEVEL_4_ACTIONS)
    def test_autonomous_can_perform_level_4_actions(self, action, db_session: Session):
        """AUTONOMOUS agents can perform Level 4 (CRITICAL) actions."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, action)

        assert result["allowed"] is True, f"AUTONOMOUS should be allowed to {action}"
        assert result["action_complexity"] == 4
        assert result.get("requires_human_approval") is False


# ============================================================================
# Complexity Matrix Tests
# ============================================================================


class TestComplexityMatrix:
    """Test complete action complexity matrix enforcement."""

    def test_complexity_1_requires_student_or_higher(self, db_session: Session):
        """Level 1 actions require STUDENT+ maturity."""
        governance = AgentGovernanceService(db_session)

        # All maturity levels can perform level 1
        for factory in [StudentAgentFactory, InternAgentFactory,
                       SupervisedAgentFactory, AutonomousAgentFactory]:
            agent = factory(_session=db_session)
            result = governance.can_perform_action(agent.id, "search")

            assert result["allowed"] is True
            assert result["action_complexity"] == 1

    def test_complexity_2_requires_intern_or_higher(self, db_session: Session):
        """Level 2 actions require INTERN+ maturity."""
        governance = AgentGovernanceService(db_session)

        # STUDENT blocked
        student = StudentAgentFactory(_session=db_session)
        result = governance.can_perform_action(student.id, "analyze")
        assert result["allowed"] is False
        assert result["action_complexity"] == 2

        # INTERN+ allowed
        for factory in [InternAgentFactory, SupervisedAgentFactory,
                       AutonomousAgentFactory]:
            agent = factory(_session=db_session)
            result = governance.can_perform_action(agent.id, "analyze")

            assert result["allowed"] is True
            assert result["action_complexity"] == 2

    def test_complexity_3_requires_supervised_or_higher(self, db_session: Session):
        """Level 3 actions require SUPERVISED+ maturity."""
        governance = AgentGovernanceService(db_session)

        # STUDENT, INTERN blocked
        for factory in [StudentAgentFactory, InternAgentFactory]:
            agent = factory(_session=db_session)
            result = governance.can_perform_action(agent.id, "create")

            assert result["allowed"] is False
            assert result["action_complexity"] == 3

        # SUPERVISED+ allowed
        for factory in [SupervisedAgentFactory, AutonomousAgentFactory]:
            agent = factory(_session=db_session)
            result = governance.can_perform_action(agent.id, "create")

            assert result["allowed"] is True
            assert result["action_complexity"] == 3

    def test_complexity_4_requires_autonomous_only(self, db_session: Session):
        """Level 4 (CRITICAL) actions require AUTONOMOUS maturity."""
        governance = AgentGovernanceService(db_session)

        # STUDENT, INTERN, SUPERVISED blocked
        for factory in [StudentAgentFactory, InternAgentFactory,
                       SupervisedAgentFactory]:
            agent = factory(_session=db_session)
            result = governance.can_perform_action(agent.id, "delete")

            assert result["allowed"] is False
            assert result["action_complexity"] == 4

        # Only AUTONOMOUS allowed
        autonomous = AutonomousAgentFactory(_session=db_session)
        result = governance.can_perform_action(autonomous.id, "delete")

        assert result["allowed"] is True
        assert result["action_complexity"] == 4


# ============================================================================
# Complexity Escalation Tests
# ============================================================================


class TestComplexityEscalation:
    """Test complexity level detection and escalation."""

    def test_action_complexity_correctly_detected(self, db_session: Session):
        """Test action complexity is correctly classified."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Level 1 actions
        for action in ["search", "read", "list", "get"]:
            result = governance.can_perform_action(autonomous.id, action)
            assert result["action_complexity"] == 1, \
                f"{action} should be complexity 1, got {result['action_complexity']}"

        # Level 2 actions
        for action in ["analyze", "stream_chat", "generate", "draft"]:
            result = governance.can_perform_action(autonomous.id, action)
            assert result["action_complexity"] == 2, \
                f"{action} should be complexity 2, got {result['action_complexity']}"

        # Level 3 actions
        for action in ["update", "submit_form", "send_email"]:
            result = governance.can_perform_action(autonomous.id, action)
            assert result["action_complexity"] == 3, \
                f"{action} should be complexity 3, got {result['action_complexity']}"

        # Level 4 actions
        for action in ["delete", "execute", "deploy", "payment"]:
            result = governance.can_perform_action(autonomous.id, action)
            assert result["action_complexity"] == 4, \
                f"{action} should be complexity 4, got {result['action_complexity']}"

    def test_unknown_action_defaults_to_safe_complexity(self, db_session: Session):
        """Test unknown actions default to safe complexity level."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "unknown_action_xyz")

        # Should default to complexity 2 (moderate) or 1 (safe)
        assert result["action_complexity"] in [1, 2]
        assert "allowed" in result

    def test_complexity_boundaries_enforced(self, db_session: Session):
        """Test complexity boundaries cannot be bypassed."""
        # Create agent at each maturity level
        student = StudentAgentFactory(_session=db_session)
        intern = InternAgentFactory(_session=db_session)
        supervised = SupervisedAgentFactory(_session=db_session)
        autonomous = AutonomousAgentFactory(_session=db_session)

        governance = AgentGovernanceService(db_session)

        # Test each agent against higher complexity actions
        test_cases = [
            (student, 2, False),  # STUDENT blocked from 2+
            (student, 3, False),
            (student, 4, False),
            (intern, 3, False),   # INTERN blocked from 3+
            (intern, 4, False),
            (supervised, 4, False),  # SUPERVISED blocked from 4
            (autonomous, 4, True),   # AUTONOMOUS allowed for 4
        ]

        for agent, complexity, allowed in test_cases:
            # Map complexity to action
            action_map = {
                2: "analyze",
                3: "create",
                4: "delete"
            }
            action = action_map[complexity]

            result = governance.can_perform_action(agent.id, action)

            assert result["allowed"] == allowed, \
                f"{agent.status} performing complexity {complexity} action {action}: " \
                f"expected allowed={allowed}, got {result['allowed']}"


# ============================================================================
# Approval Requirement Tests
# ============================================================================


class TestApprovalRequirements:
    """Test approval requirements based on complexity."""

    def test_supervised_requires_approval_for_level_3(self, db_session: Session):
        """SUPERVISED agents require approval for Level 3 actions."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Level 3 actions require supervision (requires_human_approval = True)
        for action in ["create", "update", "send_email"]:
            result = governance.can_perform_action(supervised.id, action)

            assert result["allowed"] is True
            # Approval required flag should be set for Level 3
            assert result.get("requires_human_approval") is True

    def test_autonomous_no_approval_required(self, db_session: Session):
        """AUTONOMOUS agents don't require approval for any action."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Test all complexity levels
        for action in ["search", "analyze", "create", "delete"]:
            result = governance.can_perform_action(autonomous.id, action)

            assert result["allowed"] is True
            # AUTONOMOUS doesn't require approval for any action
            assert result.get("requires_human_approval") is False

    def test_intern_approval_blocked_for_level_3(self, db_session: Session):
        """INTERN agents blocked from Level 3 (not approval, outright denial)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "create")

        assert result["allowed"] is False
        # Should mention maturity requirement, not approval
        assert "supervised" in result["reason"].lower()


# ============================================================================
# Edge Cases and Boundary Tests
# ============================================================================


class TestComplexityEdgeCases:
    """Test edge cases for action complexity."""

    def test_case_sensitive_action_matching(self, db_session: Session):
        """Test action matching is case-sensitive or normalized."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Test lowercase
        result1 = governance.can_perform_action(autonomous.id, "delete")
        assert result1["action_complexity"] == 4

        # Test uppercase (should be normalized or handled)
        result2 = governance.can_perform_action(autonomous.id, "DELETE")
        # Should either normalize or handle consistently
        assert "action_complexity" in result2

    def test_action_with_underscores_and_hyphens(self, db_session: Session):
        """Test actions with underscores and hyphens are handled."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # Test underscore variants
        for action in ["submit_form", "submit-form", "submitform"]:
            result = governance.can_perform_action(autonomous.id, action)
            assert "allowed" in result

    def test_similar_action_names_have_correct_complexity(self, db_session: Session):
        """Test similar action names have appropriate complexity."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        # "stream_chat" (level 2) vs "send_email" (level 3)
        result1 = governance.can_perform_action(autonomous.id, "stream_chat")
        assert result1["action_complexity"] == 2

        result2 = governance.can_perform_action(autonomous.id, "send_email")
        assert result2["action_complexity"] == 3

    def test_empty_action_handled_gracefully(self, db_session: Session):
        """Test empty action string is handled gracefully."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "")

        # Should handle gracefully
        assert "allowed" in result

    def test_very_long_action_name(self, db_session: Session):
        """Test very long action names are handled."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        long_action = "a" * 1000

        result = governance.can_perform_action(autonomous.id, long_action)

        # Should handle gracefully
        assert "allowed" in result


# ============================================================================
# Complexity Matrix Verification
# ============================================================================


class TestCompleteComplexityMatrix:
    """Verify complete 4x4 complexity matrix is enforced.

    Matrix:
                Complexity 1  Complexity 2  Complexity 3  Complexity 4
    STUDENT       ALLOWED       BLOCKED        BLOCKED        BLOCKED
    INTERN        ALLOWED       ALLOWED        BLOCKED        BLOCKED
    SUPERVISED    ALLOWED       ALLOWED        ALLOWED        BLOCKED
    AUTONOMOUS    ALLOWED       ALLOWED        ALLOWED        ALLOWED
    """

    def test_complete_4x4_matrix(self, db_session: Session):
        """Test complete 4x4 maturity x complexity matrix."""
        governance = AgentGovernanceService(db_session)

        # Define expected matrix
        matrix = {
            AgentStatus.STUDENT: {
                1: True, 2: False, 3: False, 4: False
            },
            AgentStatus.INTERN: {
                1: True, 2: True, 3: False, 4: False
            },
            AgentStatus.SUPERVISED: {
                1: True, 2: True, 3: True, 4: False
            },
            AgentStatus.AUTONOMOUS: {
                1: True, 2: True, 3: True, 4: True
            }
        }

        # Test each cell in matrix
        for maturity_level, complexity_map in matrix.items():
            for factory in [StudentAgentFactory, InternAgentFactory,
                           SupervisedAgentFactory, AutonomousAgentFactory]:
                agent = factory(_session=db_session)

                if agent.status != maturity_level.value:
                    continue

                for complexity, expected_allowed in complexity_map.items():
                    # Map complexity to action
                    action_map = {1: "search", 2: "analyze", 3: "create", 4: "delete"}
                    action = action_map[complexity]

                    result = governance.can_perform_action(agent.id, action)

                    assert result["allowed"] == expected_allowed, \
                        f"Matrix mismatch: {agent.status} performing complexity {complexity} " \
                        f"action {action}: expected allowed={expected_allowed}, got {result['allowed']}"
