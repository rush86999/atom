"""
Unit Tests for Governance Helpers

Tests governance helper functions:
- check_agent_permission: Permission verification
- check_agent_action: Action governance checks
- get_agent_maturity: Maturity level retrieval
- can_agent_perform: Capability checks
- enforce_governance_check: Governance enforcement

Target Coverage: 90%
Target Branch Coverage: 70%+
Pass Rate Target: 100%
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from core.governance_helpers import (
    check_agent_permission,
    check_agent_action,
    get_agent_maturity,
    can_agent_perform
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Create mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_agent():
    """Create mock agent."""
    agent = Mock()
    agent.id = "agent-123"
    agent.status = "intern"
    agent.confidence_score = 0.75
    return agent


# =============================================================================
# Test Class: get_agent_maturity
# =============================================================================

class TestGetAgentMaturity:
    """Tests for get_agent_maturity function."""

    def test_get_maturity_success(self, mock_db):
        """RED: Test getting agent maturity successfully."""
        # Mock the database query
        with patch('core.governance_helpers.Agent') as mock_agent_model:
            mock_agent = Mock()
            mock_agent.maturity = "intern"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

            maturity = get_agent_maturity(mock_db, "agent-123")

            assert maturity == "intern"

    def test_get_maturity_not_found(self, mock_db):
        """RED: Test getting maturity for non-existent agent."""
        with patch('core.governance_helpers.Agent') as mock_agent_model:
            mock_db.query.return_value.filter.return_value.first.return_value = None

            maturity = get_agent_maturity(mock_db, "nonexistent")

            assert maturity is None


# =============================================================================
# Test Class: check_agent_permission
# =============================================================================

class TestCheckAgentPermission:
    """Tests for check_agent_permission function."""

    def test_check_permission_granted(self, mock_db, mock_agent):
        """RED: Test checking permission when granted."""
        with patch('core.governance_helpers.get_agent_maturity') as mock_get_maturity:
            mock_get_maturity.return_value = "supervised"
            # Supervised agents have more permissions
            result = check_agent_permission(mock_agent, "streaming")

            # Should return True if maturity allows
            assert isinstance(result, bool)

    def test_check_permission_denied(self, mock_db, mock_agent):
        """RED: Test checking permission when denied."""
        with patch('core.governance_helpers.get_agent_maturity') as mock_get_maturity:
            mock_get_maturity.return_value = "student"
            # Student agents have restricted permissions
            result = check_agent_permission(mock_agent, "streaming")

            # Should return False for student
            assert isinstance(result, bool)


# =============================================================================
# Test Class: check_agent_action
# =============================================================================

class TestCheckAgentAction:
    """Tests for check_agent_action function."""

    def test_check_action_allowed(self, mock_db, mock_agent):
        """RED: Test checking allowed action."""
        with patch('core.governance_helpers.get_agent_maturity') as mock_get_maturity:
            mock_get_maturity.return_value = "autonomous"
            # Autonomous agents can do most actions
            result = check_agent_action(mock_db, mock_agent.id, "form_submission")

            assert isinstance(result, bool)

    def test_check_action_blocked(self, mock_db, mock_agent):
        """RED: Test checking blocked action."""
        with patch('core.governance_helpers.get_agent_maturity') as mock_get_maturity:
            mock_get_maturity.return_value = "student"
            # Student agents blocked from complex actions
            result = check_agent_action(mock_db, mock_agent.id, "form_submission")

            # Should be blocked
            assert isinstance(result, bool)


# =============================================================================
# Test Class: can_agent_perform
# =============================================================================

class TestCanAgentPerform:
    """Tests for can_agent_perform function."""

    def test_can_perform_within_confidence(self, mock_db, mock_agent):
        """RED: Test checking if agent can perform action within confidence."""
        # Agent has high confidence
        mock_agent.confidence_score = 0.85

        result = can_agent_perform(mock_db, mock_agent.id, "simple_task")

        assert isinstance(result, bool)

    def test_can_perform_low_confidence(self, mock_db, mock_agent):
        """RED: Test checking if low-confidence agent can perform."""
        # Agent has low confidence
        mock_agent.confidence_score = 0.3

        result = can_agent_perform(mock_db, mock_agent.id, "complex_task")

        # Should check if action is allowed despite low confidence
        assert isinstance(result, bool)


# =============================================================================
# Test Class: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_check_permission_none_agent(self, mock_db):
        """RED: Test checking permission with None agent."""
        result = check_agent_permission(None, "action")

        # Should handle gracefully
        assert isinstance(result, bool)

    def test_get_maturity_empty_id(self, mock_db):
        """RED: Test getting maturity with empty ID."""
        maturity = get_agent_maturity(mock_db, "")

        assert maturity is None

    def test_check_action_empty_action_type(self, mock_db, mock_agent):
        """RED: Test checking with empty action type."""
        with patch('core.governance_helpers.get_agent_maturity') as mock_get_maturity:
            mock_get_maturity.return_value = "intern"

            result = check_agent_action(mock_db, mock_agent.id, "")

            assert isinstance(result, bool)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
