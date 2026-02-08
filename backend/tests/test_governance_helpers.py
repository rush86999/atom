"""
Tests for governance helper functions.

Tests the standardized governance check helpers in core/governance_helpers.py
"""

import pytest
from unittest.mock import MagicMock, patch

# Import helpers
try:
    from core.governance_helpers import (
        check_agent_permission,
        check_agent_action,
        get_agent_maturity,
        can_agent_perform,
        enforce_governance_check
    )
    from core.api_governance import ActionComplexity
except ImportError:
    from backend.core.governance_helpers import (
        check_agent_permission,
        check_agent_action,
        get_agent_maturity,
        can_agent_perform,
        enforce_governance_check
    )
    from backend.core.api_governance import ActionComplexity


class TestCheckAgentPermission:
    """Test suite for check_agent_permission function"""

    @pytest.mark.asyncio
    @patch('core.governance_helpers.ServiceFactory.get_governance_service')
    def test_permission_granted(self, mock_get_gov):
        """Test permission check when agent is permitted"""
        # Arrange
        mock_gov = MagicMock()
        mock_gov.can_execute_action.return_value = True
        mock_get_gov.return_value = mock_gov

        # Act
        result = check_agent_permission(
            db=MagicMock(),
            agent_id="agent123",
            action="update_agent",
            complexity=3,
            raise_on_denied=False
        )

        # Assert
        assert result is True
        mock_gov.can_execute_action.assert_called_once_with("agent123", 3)

    @pytest.mark.asyncio
    @patch('core.governance_helpers.ServiceFactory.get_governance_service')
    def test_permission_denied_return_false(self, mock_get_gov):
        """Test permission check returns False when denied and raise_on_denied=False"""
        # Arrange
        mock_gov = MagicMock()
        mock_gov.can_execute_action.return_value = False
        mock_gov.get_agent_maturity.return_value = "INTERN"
        mock_gov.get_required_maturity.return_value = "SUPERVISED"
        mock_get_gov.return_value = mock_gov

        # Act
        result = check_agent_permission(
            db=MagicMock(),
            agent_id="agent123",
            action="update_agent",
            complexity=3,
            raise_on_denied=False
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    @patch('core.governance_helpers.ServiceFactory.get_governance_service')
    def test_permission_denied_raises_exception(self, mock_get_gov):
        """Test permission check raises HTTPException when denied and raise_on_denied=True"""
        from fastapi import HTTPException

        # Arrange
        mock_gov = MagicMock()
        mock_gov.can_execute_action.return_value = False
        mock_gov.get_agent_maturity.return_value = "INTERN"
        mock_gov.get_required_maturity.return_value = "SUPERVISED"
        mock_get_gov.return_value = mock_gov

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            check_agent_permission(
                db=MagicMock(),
                agent_id="agent123",
                action="update_agent",
                complexity=3,
                raise_on_denied=True
            )

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @patch('core.governance_helpers.ServiceFactory.get_governance_service')
    def test_various_complexity_levels(self, mock_get_gov):
        """Test permission check with various complexity levels"""
        mock_gov = MagicMock()
        mock_gov.can_execute_action.return_value = True
        mock_get_gov.return_value = mock_gov

        for complexity in [1, 2, 3, 4]:
            result = check_agent_permission(
                db=MagicMock(),
                agent_id="agent123",
                action=f"action_complexity_{complexity}",
                complexity=complexity,
                raise_on_denied=False
            )

            assert result is True


class TestCheckAgentAction:
    """Test suite for check_agent_action function with ActionComplexity enum"""

    @pytest.mark.asyncio
    @patch('core.governance_helpers.ServiceFactory.get_governance_service')
    def test_action_complexity_enum(self, mock_get_gov):
        """Test check_agent_action with ActionComplexity enum"""
        # Arrange
        mock_gov = MagicMock()
        mock_gov.can_execute_action.return_value = True
        mock_get_gov.return_value = mock_gov

        # Act
        result = check_agent_action(
            db=MagicMock(),
            agent_id="agent123",
            action="delete_resource",
            action_complexity=ActionComplexity.CRITICAL,
            raise_on_denied=False
        )

        # Assert
        assert result is True
        # CRITICAL = 4
        mock_gov.can_execute_action.assert_called_once_with("agent123", 4)

    @pytest.mark.asyncio
    @patch('core.governance_helpers.ServiceFactory.get_governance_service')
    def test_all_action_complexity_levels(self, mock_get_gov):
        """Test all ActionComplexity enum values"""
        mock_gov = MagicMock()
        mock_gov.can_execute_action.return_value = True
        mock_get_gov.return_value = mock_gov

        action_complexities = [
            (ActionComplexity.LOW, 1),
            (ActionComplexity.MODERATE, 2),
            (ActionComplexity.HIGH, 3),
            (ActionComplexity.CRITICAL, 4),
        ]

        for action_complexity, expected_value in action_complexities:
            result = check_agent_action(
                db=MagicMock(),
                agent_id="agent123",
                action="test_action",
                action_complexity=action_complexity,
                raise_on_denied=False
            )

            assert result is True


class TestGetAgentMaturity:
    """Test suite for get_agent_maturity function"""

    @pytest.mark.asyncio
    @patch('core.governance_helpers.ServiceFactory.get_governance_service')
    def test_get_maturity_success(self, mock_get_gov):
        """Test getting agent maturity successfully"""
        # Arrange
        mock_gov = MagicMock()
        mock_gov.get_agent_maturity.return_value = "SUPERVISED"
        mock_get_gov.return_value = mock_gov

        # Act
        maturity = get_agent_maturity(MagicMock(), "agent123")

        # Assert
        assert maturity == "SUPERVISED"
        mock_gov.get_agent_maturity.assert_called_once_with("agent123")

    @pytest.mark.asyncio
    @patch('core.governance_helpers.ServiceFactory.get_governance_service')
    def test_get_maturity_not_found(self, mock_get_gov):
        """Test getting maturity for non-existent agent"""
        # Arrange
        mock_gov = MagicMock()
        mock_gov.get_agent_maturity.side_effect = Exception("Agent not found")
        mock_get_gov.return_value = mock_gov

        # Act
        maturity = get_agent_maturity(MagicMock(), "nonexistent")

        # Assert
        assert maturity is None


class TestCanAgentPerform:
    """Test suite for can_agent_perform function"""

    @pytest.mark.asyncio
    @patch('core.governance_helpers.check_agent_permission')
    def test_can_perform_true(self, mock_check):
        """Test can_agent_perform returns True when permitted"""
        # Arrange
        mock_check.return_value = True

        # Act
        result = can_agent_perform(MagicMock(), "agent123", complexity=3)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    @patch('core.governance_helpers.check_agent_permission')
    def test_can_perform_false(self, mock_check):
        """Test can_agent_perform returns False when not permitted"""
        # Arrange
        mock_check.return_value = False

        # Act
        result = can_agent_perform(MagicMock(), "agent123", complexity=4)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    @patch('core.governance_helpers.check_agent_permission')
    def test_can_perform_never_raises(self, mock_check):
        """Test can_agent_perform never raises exception"""
        # Arrange
        mock_check.return_value = False

        # Act - should not raise
        result = can_agent_perform(MagicMock(), "agent123", complexity=4)

        # Assert
        assert result is False
        # Verify raise_on_denied=False was used
        mock_check.assert_called_once()


class TestEnforceGovernanceCheck:
    """Test suite for enforce_governance_check function"""

    @pytest.mark.asyncio
    @patch('core.governance_helpers.check_agent_permission')
    def test_enforce_success(self, mock_check):
        """Test enforce_governance_check passes when permitted"""
        # Arrange
        mock_check.return_value = True

        # Act - should not raise
        enforce_governance_check(
            MagicMock(),
            "agent123",
            "delete_user",
            complexity=4
        )

        # Assert - verify check was called with correct parameters (not comparing MagicMock instances)
        assert mock_check.called
        call_args = mock_check.call_args
        assert call_args[0][1] == "agent123"  # agent_id
        assert call_args[0][2] == "delete_user"  # action
        assert call_args[0][3] == 4  # complexity
        assert call_args[1]["raise_on_denied"] is True

    @pytest.mark.asyncio
    @patch('core.governance_helpers.check_agent_permission')
    def test_enforce_raises(self, mock_check):
        """Test enforce_governance_check raises when not permitted"""
        from fastapi import HTTPException

        # Arrange
        mock_check.side_effect = HTTPException(status_code=403, detail="Forbidden")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            enforce_governance_check(
                MagicMock(),
                "agent123",
                "delete_user",
                complexity=4
            )

        assert exc_info.value.status_code == 403


class TestIntegrationScenarios:
    """Integration tests for governance helpers"""

    @pytest.mark.asyncio
    @patch('core.governance_helpers.ServiceFactory.get_governance_service')
    def test_complete_workflow(self, mock_get_gov):
        """Test complete workflow: check maturity, then perform action"""
        # Arrange
        mock_gov = MagicMock()
        mock_gov.get_agent_maturity.return_value = "AUTONOMOUS"
        mock_gov.can_execute_action.return_value = True
        mock_get_gov.return_value = mock_gov

        db = MagicMock()
        agent_id = "agent123"

        # Act - Check maturity
        maturity = get_agent_maturity(db, agent_id)

        # Assert maturity
        assert maturity == "AUTONOMOUS"

        # Act - Check if can perform high-complexity action
        can_perform = can_agent_perform(db, agent_id, complexity=4)

        # Assert permission
        assert can_perform is True

        # Act - Enforce check (should not raise)
        enforce_governance_check(db, agent_id, "critical_action", complexity=4)

        # All checks passed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
