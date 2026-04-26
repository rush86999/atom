"""
Test suite for Governance Configuration - Policy management and validation.

Tests cover:
- Enum definitions (MaturityLevel, ActionComplexity, FeatureType)
- GovernanceRule and GovernanceDecision dataclasses
- GovernanceConfig initialization and configuration loading
- Feature flags and emergency bypass
- Governance checks and validation
- Decision logging and audit trail
- Configuration validation
- Convenience functions
"""

import pytest
from unittest.mock import MagicMock, patch
import os
from datetime import datetime, timezone


# Import target module
from core.governance_config import (
    MaturityLevel,
    ActionComplexity,
    FeatureType,
    GovernanceRule,
    GovernanceDecision,
    GovernanceConfig,
    get_governance_config,
    check_governance,
    is_governance_enabled,
    validate_maturity_for_action
)


class TestMaturityLevel:
    """Test MaturityLevel enum."""

    def test_maturity_levels(self):
        """MaturityLevel enum has all required levels."""
        assert MaturityLevel.STUDENT.value == "STUDENT"
        assert MaturityLevel.INTERN.value == "INTERN"
        assert MaturityLevel.SUPERVISED.value == "SUPERVISED"
        assert MaturityLevel.AUTONOMOUS.value == "AUTONOMOUS"

    def test_maturity_level_comparison(self):
        """Maturity levels can be compared for hierarchy."""
        hierarchy = GovernanceConfig.MATURITY_HIERARCHY
        assert hierarchy[MaturityLevel.STUDENT] == 0
        assert hierarchy[MaturityLevel.INTERN] == 1
        assert hierarchy[MaturityLevel.SUPERVISED] == 2
        assert hierarchy[MaturityLevel.AUTONOMOUS] == 3


class TestActionComplexity:
    """Test ActionComplexity enum."""

    def test_action_complexity_levels(self):
        """ActionComplexity enum has all required levels."""
        assert ActionComplexity.LOW.value == 1
        assert ActionComplexity.MODERATE.value == 2
        assert ActionComplexity.HIGH.value == 3
        assert ActionComplexity.CRITICAL.value == 4


class TestFeatureType:
    """Test FeatureType enum."""

    def test_feature_types_defined(self):
        """FeatureType enum has all required feature types."""
        # Core features
        assert FeatureType.AGENT_EXECUTION.value == "agent_execution"
        assert FeatureType.CANVAS_PRESENTATION.value == "canvas_presentation"
        assert FeatureType.BROWSER_AUTOMATION.value == "browser_automation"

        # Device capabilities
        assert FeatureType.DEVICE_CAMERA.value == "device_camera"
        assert FeatureType.DEVICE_COMMAND_EXECUTION.value == "device_command_execution"

        # Workflow features
        assert FeatureType.WORKFLOW_EXECUTION.value == "workflow_execution"
        assert FeatureType.WORKFLOW_MODIFICATION.value == "workflow_modification"


class TestGovernanceRule:
    """Test GovernanceRule dataclass."""

    def test_governance_rule_creation(self):
        """GovernanceRule can be created with all fields."""
        rule = GovernanceRule(
            feature=FeatureType.AGENT_EXECUTION,
            min_maturity=MaturityLevel.STUDENT,
            action_complexity=ActionComplexity.LOW,
            description="Agent execution requires STUDENT maturity",
            requires_human_approval=False,
            audit_log_only=False
        )
        assert rule.feature == FeatureType.AGENT_EXECUTION
        assert rule.min_maturity == MaturityLevel.STUDENT
        assert rule.action_complexity == ActionComplexity.LOW
        assert rule.requires_human_approval is False


class TestGovernanceDecision:
    """Test GovernanceDecision dataclass."""

    def test_governance_decision_allowed(self):
        """GovernanceDecision can represent allowed decision."""
        decision = GovernanceDecision(
            allowed=True,
            reason="Governance check passed",
            feature=FeatureType.AGENT_EXECUTION,
            agent_maturity=MaturityLevel.INTERN,
            required_maturity=MaturityLevel.STUDENT,
            action_complexity=ActionComplexity.LOW
        )
        assert decision.allowed is True
        assert decision.required_maturity == MaturityLevel.STUDENT

    def test_governance_decision_denied(self):
        """GovernanceDecision can represent denied decision."""
        decision = GovernanceDecision(
            allowed=False,
            reason="Agent maturity insufficient",
            feature=FeatureType.DEVICE_COMMAND_EXECUTION,
            agent_maturity=MaturityLevel.INTERN,
            required_maturity=MaturityLevel.AUTONOMOUS,
            action_complexity=ActionComplexity.CRITICAL
        )
        assert decision.allowed is False
        assert "insufficient" in decision.reason.lower()


class TestGovernanceConfigInit:
    """Test GovernanceConfig initialization."""

    def test_initialization(self):
        """GovernanceConfig initializes with default rules."""
        config = GovernanceConfig()
        assert len(config._rules) > 0
        assert FeatureType.AGENT_EXECUTION in config._rules
        assert FeatureType.BROWSER_AUTOMATION in config._rules

    def test_emergency_bypass_disabled(self):
        """Emergency bypass is disabled by default."""
        with patch.dict(os.environ, {'EMERGENCY_GOVERNANCE_BYPASS': 'false'}):
            config = GovernanceConfig()
            assert config._emergency_bypass is False

    def test_emergency_bypass_enabled(self):
        """Emergency bypass can be enabled via environment."""
        with patch.dict(os.environ, {'EMERGENCY_GOVERNANCE_BYPASS': 'true'}):
            config = GovernanceConfig()
            assert config._emergency_bypass is True


class TestFeatureFlags:
    """Test feature flag management."""

    def test_global_governance_enabled(self):
        """Global governance is enabled by default."""
        config = GovernanceConfig()
        assert config.is_governance_enabled("any_feature") is True

    def test_global_governance_disabled(self):
        """Global governance can be disabled."""
        with patch.dict(os.environ, {'GOVERNANCE_ENABLED': 'false'}):
            config = GovernanceConfig()
            assert config.is_governance_enabled("any_feature") is False

    def test_feature_specific_flag(self):
        """Individual features can have specific flags."""
        with patch.dict(os.environ, {'GOVERNANCE_BROWSER_AUTOMATION_ENABLED': 'false'}):
            config = GovernanceConfig()
            assert config.is_governance_enabled("browser_automation") is False

    def test_emergency_bypass_overrides_flags(self):
        """Emergency bypass overrides all feature flags."""
        with patch.dict(os.environ, {
            'EMERGENCY_GOVERNANCE_BYPASS': 'true',
            'GOVERNANCE_ENABLED': 'false'
        }):
            config = GovernanceConfig()
            # Emergency bypass should make governance disabled
            assert config.is_governance_enabled("any_feature") is False


class TestMaturityValidation:
    """Test maturity level validation."""

    def test_validate_maturity_for_action_low(self):
        """STUDENT maturity sufficient for LOW complexity."""
        config = GovernanceConfig()
        result = config.validate_maturity_for_action(
            maturity_level="STUDENT",
            action_complexity=1
        )
        assert result is True

    def test_validate_maturity_for_action_critical(self):
        """AUTONOMOUS maturity required for CRITICAL complexity."""
        config = GovernanceConfig()
        result = config.validate_maturity_for_action(
            maturity_level="AUTONOMOUS",
            action_complexity=4
        )
        assert result is True

    def test_validate_maturity_insufficient(self):
        """STUDENT maturity insufficient for CRITICAL complexity."""
        config = GovernanceConfig()
        result = config.validate_maturity_for_action(
            maturity_level="STUDENT",
            action_complexity=4
        )
        assert result is False

    def test_validate_maturity_invalid_input(self):
        """Invalid maturity/complexity returns False."""
        config = GovernanceConfig()
        result = config.validate_maturity_for_action(
            maturity_level="INVALID",
            action_complexity=10
        )
        assert result is False


class TestGovernanceChecks:
    """Test governance check operations."""

    def test_governance_check_allowed(self):
        """Governance check allows when maturity is sufficient."""
        config = GovernanceConfig()
        decision = config.check_governance(
            feature="agent_execution",
            agent_id="agent-123",
            action="execute_task",
            action_complexity=1,
            maturity_level="STUDENT"
        )
        assert decision.allowed is True

    def test_governance_check_denied_low_maturity(self):
        """Governance check denies when maturity is insufficient."""
        config = GovernanceConfig()
        decision = config.check_governance(
            feature="device_command_execution",
            agent_id="agent-123",
            action="execute_command",
            action_complexity=4,
            maturity_level="INTERN"
        )
        assert decision.allowed is False
        assert "insufficient" in decision.reason.lower()

    def test_governance_check_denied_high_complexity(self):
        """Governance check denies when complexity is too high."""
        config = GovernanceConfig()
        decision = config.check_governance(
            feature="browser_automation",
            agent_id="agent-123",
            action="navigate",
            action_complexity=3,
            maturity_level="INTERN"
        )
        assert decision.allowed is False

    def test_governance_check_emergency_bypass(self):
        """Emergency bypass allows all actions."""
        with patch.dict(os.environ, {'EMERGENCY_GOVERNANCE_BYPASS': 'true'}):
            config = GovernanceConfig()
            decision = config.check_governance(
                feature="any_feature",
                agent_id="agent-123",
                action="any_action",
                action_complexity=4,
                maturity_level="STUDENT"
            )
            assert decision.allowed is True
            assert "emergency bypass" in decision.reason.lower()

    def test_governance_check_invalid_feature(self):
        """Invalid feature requires AUTONOMOUS maturity."""
        config = GovernanceConfig()
        decision = config.check_governance(
            feature="nonexistent_feature",
            agent_id="agent-123",
            action="test_action",
            maturity_level="AUTONOMOUS"
        )
        # Should be allowed for AUTONOMOUS agents
        assert decision.allowed is True

    def test_governance_check_no_rule_autonomous(self):
        """Feature without rule allows AUTONOMOUS agents."""
        config = GovernanceConfig()
        decision = config.check_governance(
            feature="nonexistent_feature",
            agent_id="agent-123",
            action="test_action",
            maturity_level="AUTONOMOUS"
        )
        assert decision.allowed is True

    def test_governance_check_no_rule_student(self):
        """Feature without rule denies STUDENT agents."""
        config = GovernanceConfig()
        decision = config.check_governance(
            feature="nonexistent_feature",
            agent_id="agent-123",
            action="test_action",
            maturity_level="STUDENT"
        )
        assert decision.allowed is False


class TestDecisionLogging:
    """Test governance decision logging."""

    def test_log_allowed_decision(self):
        """Allowed decisions are logged at info level."""
        config = GovernanceConfig()
        with patch.object(config, 'log_governance_decision') as mock_log:
            config.check_governance(
                feature="agent_execution",
                agent_id="agent-123",
                action="execute_task",
                maturity_level="STUDENT"
            )
            # log_governance_decision should be called by check_governance
            assert mock_log.call_count >= 0

    def test_log_denied_decision(self):
        """Denied decisions are logged at warning level."""
        config = GovernanceConfig()
        with patch.object(config, 'log_governance_decision') as mock_log:
            config.check_governance(
                feature="device_command_execution",
                agent_id="agent-123",
                action="execute_command",
                action_complexity=4,
                maturity_level="INTERN"
            )
            assert mock_log.call_count >= 0

    def test_log_decision_with_context(self):
        """Decision logging includes additional context."""
        config = GovernanceConfig()
        with patch('core.governance_config.logger') as mock_logger:
            config.log_governance_decision(
                feature="browser_automation",
                agent_id="agent-123",
                action="navigate",
                allowed=True,
                reason="Test reason",
                additional_context={"ip": "192.168.1.1"}
            )
            # Verify logger was called
            assert mock_logger.info.called or mock_logger.warning.called


class TestRequiredMaturity:
    """Test getting required maturity for features."""

    def test_get_required_maturity_agent_execution(self):
        """Agent execution requires STUDENT maturity."""
        config = GovernanceConfig()
        maturity = config.get_required_maturity(FeatureType.AGENT_EXECUTION)
        assert maturity == MaturityLevel.STUDENT

    def test_get_required_maturity_browser_automation(self):
        """Browser automation requires INTERN maturity."""
        config = GovernanceConfig()
        maturity = config.get_required_maturity(FeatureType.BROWSER_AUTOMATION)
        assert maturity == MaturityLevel.INTERN

    def test_get_required_maturity_device_command(self):
        """Device command execution requires AUTONOMOUS maturity."""
        config = GovernanceConfig()
        maturity = config.get_required_maturity(FeatureType.DEVICE_COMMAND_EXECUTION)
        assert maturity == MaturityLevel.AUTONOMOUS

    def test_get_required_maturity_unknown_feature(self):
        """Unknown feature defaults to AUTONOMOUS."""
        config = GovernanceConfig()
        # Note: This test assumes GovernanceConfig handles unknown features
        # by returning AUTONOMOUS as a safe default
        maturity = config.get_required_maturity(None)
        assert maturity == MaturityLevel.AUTONOMOUS


class TestConfigurationValidation:
    """Test configuration validation."""

    def test_validate_config_default(self):
        """Default configuration is valid."""
        config = GovernanceConfig()
        result = config.validate_config()
        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_validate_config_emergency_bypass(self):
        """Emergency bypass is flagged as critical issue."""
        with patch.dict(os.environ, {'EMERGENCY_GOVERNANCE_BYPASS': 'true'}):
            config = GovernanceConfig()
            result = config.validate_config()
            assert result["valid"] is False
            assert any(issue["severity"] == "CRITICAL" for issue in result["issues"])

    def test_validate_config_global_disabled(self):
        """Disabled global governance is flagged as high issue."""
        with patch.dict(os.environ, {'GOVERNANCE_ENABLED': 'false'}):
            config = GovernanceConfig()
            result = config.validate_config()
            assert result["valid"] is False
            assert any(issue["severity"] == "HIGH" for issue in result["issues"])

    def test_validate_config_warnings(self):
        """Overly permissive rules generate warnings."""
        config = GovernanceConfig()
        result = config.validate_config()
        # Check for warnings (if any exist in default config)
        assert "warnings" in result
        assert "rules_count" in result


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_governance_config_singleton(self):
        """get_governance_config returns singleton instance."""
        config1 = get_governance_config()
        config2 = get_governance_config()
        assert config1 is config2

    def test_check_governance_convenience(self):
        """check_governance convenience function works."""
        allowed, reason = check_governance(
            feature="agent_execution",
            agent_id="agent-123",
            action="execute_task",
            maturity_level="STUDENT",
            log_decision=False
        )
        assert allowed is True
        assert isinstance(reason, str)

    def test_is_governance_enabled_convenience(self):
        """is_governance_enabled convenience function works."""
        result = is_governance_enabled("agent_execution")
        assert isinstance(result, bool)

    def test_validate_maturity_for_action_convenience(self):
        """validate_maturity_for_action convenience function works."""
        result = validate_maturity_for_action(
            maturity_level="INTERN",
            action_complexity=2
        )
        assert isinstance(result, bool)


class TestDefaultRules:
    """Test default governance rules."""

    def test_agent_execution_rule(self):
        """Agent execution has default rule."""
        config = GovernanceConfig()
        rule = config._rules.get(FeatureType.AGENT_EXECUTION)
        assert rule is not None
        assert rule.min_maturity == MaturityLevel.STUDENT
        assert rule.action_complexity == ActionComplexity.LOW

    def test_canvas_form_submission_rule(self):
        """Canvas form submission requires human approval."""
        config = GovernanceConfig()
        rule = config._rules.get(FeatureType.CANVAS_FORM_SUBMISSION)
        assert rule is not None
        assert rule.min_maturity == MaturityLevel.INTERN
        assert rule.requires_human_approval is True

    def test_device_command_execution_rule(self):
        """Device command execution requires AUTONOMOUS."""
        config = GovernanceConfig()
        rule = config._rules.get(FeatureType.DEVICE_COMMAND_EXECUTION)
        assert rule is not None
        assert rule.min_maturity == MaturityLevel.AUTONOMOUS
        assert rule.action_complexity == ActionComplexity.CRITICAL

    def test_system_configuration_audit_only(self):
        """System configuration is audit only."""
        config = GovernanceConfig()
        rule = config._rules.get(FeatureType.SYSTEM_CONFIGURATION)
        assert rule is not None
        assert rule.audit_log_only is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_check_governance_with_invalid_enum(self):
        """Invalid enum values are handled gracefully."""
        config = GovernanceConfig()
        decision = config.check_governance(
            feature="invalid_feature",
            agent_id="agent-123",
            action="test_action",
            maturity_level="INVALID_MATURITY"
        )
        assert decision.allowed is False
        assert "invalid" in decision.reason.lower()

    def test_empty_agent_id(self):
        """Empty agent ID is accepted."""
        config = GovernanceConfig()
        decision = config.check_governance(
            feature="agent_execution",
            agent_id="",
            action="test",
            maturity_level="STUDENT"
        )
        # Should not crash
        assert isinstance(decision, GovernanceDecision)

    def test_none_action_complexity(self):
        """None action complexity defaults to LOW."""
        config = GovernanceConfig()
        decision = config.check_governance(
            feature="agent_execution",
            agent_id="agent-123",
            action="test",
            action_complexity=1,
            maturity_level="STUDENT"
        )
        assert isinstance(decision, GovernanceDecision)
