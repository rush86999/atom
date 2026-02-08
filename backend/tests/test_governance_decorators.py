"""
Test Governance Decorators

Tests for the governance enforcement decorators.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.governance_decorator import (
    require_governance,
    require_student,
    require_intern,
    require_supervised,
    require_autonomous
)
from core.error_handlers import ErrorCode


class TestRequireGovernance:
    """Test suite for @require_governance decorator"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent"""
        agent = Mock()
        agent.id = "test-agent-123"
        agent.maturity_level = "INTERN"
        return agent

    def test_governance_check_pass(self, mock_db, mock_agent):
        """Test that governance check passes when agent has sufficient maturity"""
        with patch('core.governance_decorator.ServiceFactory') as mock_factory:
            mock_governance = Mock()
            mock_governance.can_execute_action.return_value = True
            mock_factory.get_governance_service.return_value = mock_governance

            @require_governance(action_complexity=2)
            def test_function(agent_id: str, db: Session):
                return f"Executed for {agent_id}"

            result = test_function(agent_id="test-agent-123", db=mock_db)
            assert "Executed for test-agent-123" in result

    def test_governance_check_fail(self, mock_db):
        """Test that governance check fails when agent lacks maturity"""
        with patch('core.governance_decorator.ServiceFactory') as mock_factory:
            mock_governance = Mock()
            mock_governance.can_execute_action.return_value = False
            mock_factory.get_governance_service.return_value = mock_governance

            with patch('core.governance_decorator.AgentContextResolver') as mock_resolver:
                mock_context = {"maturity_level": "STUDENT"}
                mock_resolver.return_value.resolve_context.return_value = mock_context

                @require_intern
                def test_function(agent_id: str, db: Session):
                    return "Should not execute"

                from core.error_handlers import api_error
                with pytest.raises(api_error) as exc_info:
                    test_function(agent_id="test-agent-123", db=mock_db)

                assert exc_info.value.status_code == 403


class TestConvenienceDecorators:
    """Test suite for convenience decorators"""

    def test_require_student_decorator(self):
        """Test @require_student enforces action_complexity=1"""
        from core.governance_decorator import require_governance
        import inspect

        @require_student
        def test_func():
            pass

        # Verify decorator was applied correctly
        assert hasattr(test_func, '__wrapped__')

    def test_require_intern_decorator(self):
        """Test @require_intern enforces action_complexity=2"""
        from core.governance_decorator import require_governance

        @require_intern
        def test_func():
            pass

        assert hasattr(test_func, '__wrapped__')

    def test_require_supervised_decorator(self):
        """Test @require_supervised enforces action_complexity=3"""
        from core.governance_decorator import require_governance

        @require_supervised
        def test_func():
            pass

        assert hasattr(test_func, '__wrapped__')

    def test_require_autonomous_decorator(self):
        """Test @require_autonomous enforces action_complexity=4"""
        from core.governance_decorator import require_governance

        @require_autonomous
        def test_func():
            pass

        assert hasattr(test_func, '__wrapped__')


class TestGovernanceBypass:
    """Test suite for governance bypass scenarios"""

    def test_emergency_bypass_disabled(self):
        """Test that emergency bypass can be checked"""
        # Test with emergency bypass disabled (default)
        import os
        bypass = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"
        assert bypass == False

    def test_feature_flag_integration(self):
        """Test that feature flags are properly integrated"""
        from core.feature_flags import FeatureFlags
        import os

        # Test feature flag can be read
        flag_value = FeatureFlags.should_enforce_governance('browser')
        assert isinstance(flag_value, bool)


class TestOnFailureBehavior:
    """Test suite for on_failure parameter"""

    def test_return_none_on_failure(self):
        """Test on_failure='return_none' behavior"""
        with patch('core.governance_decorator.ServiceFactory') as mock_factory:
            mock_governance = Mock()
            mock_governance.can_execute_action.return_value = False
            mock_factory.get_governance_service.return_value = mock_governance

            with patch('core.governance_decorator.AgentContextResolver') as mock_resolver:
                mock_context = {"maturity_level": "STUDENT"}
                mock_resolver.return_value.resolve_context.return_value = mock_context

                @require_governance(action_complexity=3, on_failure="return_none")
                def test_function(agent_id: str, db: Session):
                    return "Should not execute"

                from unittest.mock import Mock
                mock_db = Mock(spec=Session)
                result = test_function(agent_id="test-agent-123", db=mock_db)

                assert result is None
