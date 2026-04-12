"""
Test AutoDevCapabilityService maturity gates.

Tests cover:
- Maturity gate checks
- Tenant opt-in verification
- Capability-specific checks
- Error handling
- Integration with governance
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from core.auto_dev.capability_gate import (
    AutoDevCapabilityService,
    AUTONOMOUS,
    INTERN,
    STUDENT,
    SUPERVISED,
    is_at_least,
)


class TestCapabilityGateMaturityGates:
    """Test can_use_auto_dev() checks agent maturity."""

    def test_student_maturity_blocked(self, auto_dev_db_session):
        """Test STUDENT maturity blocked."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        # Mock graduation service to return STUDENT
        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=STUDENT)
        service._graduation_service = mock_graduation

        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.memento_skills",
            workspace_settings={"auto_dev": {"enabled": True}},
        )

        assert result is False

    def test_intern_maturity_blocked_for_evolver(self, auto_dev_db_session):
        """Test INTERN maturity blocked for alpha_evolver."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=INTERN)
        service._graduation_service = mock_graduation

        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.alpha_evolver",
            workspace_settings={"auto_dev": {"enabled": True}},
        )

        assert result is False

    def test_supervised_maturity_allowed(self, auto_dev_db_session):
        """Test SUPERVISED maturity allowed for memento_skills."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=SUPERVISED)
        service._graduation_service = mock_graduation

        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.memento_skills",
            workspace_settings={"auto_dev": {"enabled": True}},
        )

        assert result is True

    def test_autonomous_maturity_allowed(self, auto_dev_db_session):
        """Test AUTONOMOUS maturity allowed."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=AUTONOMOUS)
        service._graduation_service = mock_graduation

        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.background_evolution",
            workspace_settings={"auto_dev": {"enabled": True}},
        )

        assert result is True


class TestCapabilityGateTenantOptIn:
    """Test tenant opt-in verification."""

    def test_checks_auto_dev_enabled(self, auto_dev_db_session):
        """Test checks tenant_settings.auto_dev_enabled."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=AUTONOMOUS)
        service._graduation_service = mock_graduation

        # Auto-dev disabled
        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.memento_skills",
            workspace_settings={"auto_dev": {"enabled": False}},
        )

        assert result is False

    def test_returns_false_if_opt_in_disabled(self, auto_dev_db_session):
        """Test returns False if opt-in disabled."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=AUTONOMOUS)
        service._graduation_service = mock_graduation

        # No auto_dev settings at all
        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.memento_skills",
            workspace_settings={},
        )

        assert result is False

    def test_handles_missing_tenant_settings(self, auto_dev_db_session):
        """Test handles missing tenant_settings."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=AUTONOMOUS)
        service._graduation_service = mock_graduation

        # None settings
        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.memento_skills",
            workspace_settings=None,
        )

        assert result is False


class TestCapabilityGateCapabilityCheck:
    """Test capability check for specific operations."""

    def test_can_use_skill_generation(self, auto_dev_db_session):
        """Test can_use_skill_generation()."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=INTERN)
        service._graduation_service = mock_graduation

        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.memento_skills",
            workspace_settings={"auto_dev": {"enabled": True, "memento_skills": True}},
        )

        assert result is True

    def test_can_use_evolution(self, auto_dev_db_session):
        """Test can_use_evolution()."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=SUPERVISED)
        service._graduation_service = mock_graduation

        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.alpha_evolver",
            workspace_settings={"auto_dev": {"enabled": True, "alpha_evolver": True}},
        )

        assert result is True

    def test_different_maturity_requirements(self, auto_dev_db_session):
        """Test different maturity requirements."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(return_value=INTERN)
        service._graduation_service = mock_graduation

        # INTERN can use memento_skills but not alpha_evolver
        memento_result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.memento_skills",
            workspace_settings={"auto_dev": {"enabled": True}},
        )

        evolver_result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.alpha_evolver",
            workspace_settings={"auto_dev": {"enabled": True}},
        )

        assert memento_result is True
        assert evolver_result is False


class TestCapabilityGateErrorHandling:
    """Test handles missing agent and tenant."""

    def test_handles_missing_agent(self, auto_dev_db_session):
        """Test handles missing agent."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        mock_graduation = MagicMock()
        mock_graduation.get_maturity = MagicMock(side_effect=Exception("Agent not found"))
        service._graduation_service = mock_graduation

        result = service.can_use(
            agent_id="nonexistent-agent",
            capability="auto_dev.memento_skills",
            workspace_settings={"auto_dev": {"enabled": True}},
        )

        # Should return False on error
        assert result is False

    def test_returns_false_on_errors(self, auto_dev_db_session):
        """Test returns False on errors."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        service.graduation = None  # No graduation service

        result = service.can_use(
            agent_id="agent-001",
            capability="auto_dev.memento_skills",
            workspace_settings={"auto_dev": {"enabled": True}},
        )

        assert result is False


class TestCapabilityGateDailyLimits:
    """Test check_daily_limits()."""

    def test_max_mutations_per_day(self, auto_dev_db_session, sample_tenant_id):
        """Test max_mutations_per_day limit."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        # Create some mutations
        from core.auto_dev.models import ToolMutation

        for i in range(5):
            mutation = ToolMutation(
                tenant_id=sample_tenant_id,
                tool_name=f"tool_{i}",
                mutated_code="def test(): pass",
                sandbox_status="passed",
            )
            auto_dev_db_session.add(mutation)

        auto_dev_db_session.commit()

        result = service.check_daily_limits(
            agent_id="agent-001",
            capability="auto_dev.alpha_evolver",
            workspace_settings={"auto_dev": {"max_mutations_per_day": 10}},
        )

        # Should allow (5 < 10)
        assert result is True

    def test_max_skill_candidates_per_day(self, auto_dev_db_session, sample_tenant_id, sample_agent_id):
        """Test max_skill_candidates_per_day limit."""
        service = AutoDevCapabilityService(auto_dev_db_session)

        # Create skill candidates
        from core.auto_dev.models import SkillCandidate

        for i in range(3):
            candidate = SkillCandidate(
                tenant_id=sample_tenant_id,
                agent_id=sample_agent_id,
                skill_name=f"skill_{i}",
                generated_code="def test(): pass",
                validation_status="pending",
            )
            auto_dev_db_session.add(candidate)

        auto_dev_db_session.commit()

        result = service.check_daily_limits(
            agent_id=sample_agent_id,
            capability="auto_dev.memento_skills",
            workspace_settings={"auto_dev": {"max_skill_candidates_per_day": 5}},
        )

        # Should allow (3 < 5)
        assert result is True


class TestCapabilityGateMaturityHelpers:
    """Test maturity helper functions."""

    def test_is_at_least_function(self):
        """Test is_at_least() function."""
        assert is_at_least(STUDENT, STUDENT) is True
        assert is_at_least(INTERN, STUDENT) is True
        assert is_at_least(SUPERVISED, INTERN) is True
        assert is_at_least(AUTONOMOUS, SUPERVISED) is True

        assert is_at_least(STUDENT, INTERN) is False
        assert is_at_least(INTERN, SUPERVISED) is False
        assert is_at_least(SUPERVISED, AUTONOMOUS) is False

    def test_maturity_order(self):
        """Test MATURITY_ORDER is correct."""
        from core.auto_dev.capability_gate import MATURITY_ORDER

        assert MATURITY_ORDER == [STUDENT, INTERN, SUPERVISED, AUTONOMOUS]
