# -*- coding: utf-8 -*-
"""Coverage wave 73 — core/governance_config remaining branches.

Closes the last uncovered lines of GovernanceConfig: governance-disabled
decisions, no-rule fallback for non-AUTONOMOUS agents, denied-decision
logging with context, validate_config STUDENT+CRITICAL warning, convenience
`check_governance` with default logging, env-driven feature-flag loading and
singleton behavior. Existing suite (test_governance_config.py) covers the
core paths; this file adds the branch/edge complement. Zero LLM spend, no
network, no real DB.
"""
import logging
from unittest.mock import patch

import pytest

import core.governance_config as gc
from core.governance_config import (
    ActionComplexity,
    FeatureType,
    GovernanceConfig,
    GovernanceDecision,
    MaturityLevel,
    check_governance,
    get_governance_config,
    is_governance_enabled,
    validate_maturity_for_action,
)


@pytest.fixture(autouse=True)
def reset_global():
    """Isolate the module-level singleton between tests."""
    saved = gc._governance_config
    gc._governance_config = None
    yield
    gc._governance_config = saved


@pytest.fixture()
def config():
    return GovernanceConfig()


# ============================================================================
# Feature-flag loading from env
# ============================================================================

class TestFeatureFlagLoading:
    def test_env_override_disables_feature(self, monkeypatch, reset_global):
        monkeypatch.setenv("GOVERNANCE_CANVAS_PRESENTATION_ENABLED", "false")
        cfg = GovernanceConfig()
        assert cfg.is_governance_enabled("canvas_presentation") is False
        assert cfg.is_governance_enabled("browser_automation") is True

    def test_global_switch_env(self, monkeypatch, reset_global):
        monkeypatch.setenv("GOVERNANCE_ENABLED", "false")
        cfg = GovernanceConfig()
        assert cfg.is_governance_enabled("browser_automation") is False
        assert cfg._feature_flags["_global"] is False

    def test_unknown_feature_defaults_true(self, config):
        assert config.is_governance_enabled("no_such_feature") is True

    def test_emergency_bypass_disables_everything(self, monkeypatch, reset_global):
        monkeypatch.setenv("EMERGENCY_GOVERNANCE_BYPASS", "true")
        cfg = GovernanceConfig()
        assert cfg.is_governance_enabled("browser_automation") is False
        assert cfg._emergency_bypass is True


# ============================================================================
# check_governance branch completion
# ============================================================================

class TestCheckGovernanceBranches:
    def test_governance_disabled_for_feature_allows(self, config):
        config._feature_flags["canvas_presentation"] = False
        decision = config.check_governance(
            feature="canvas_presentation", agent_id="a1", action="present"
        )
        assert decision.allowed is True
        assert "disabled" in decision.reason

    def test_no_rule_non_autonomous_denied(self, config, caplog):
        del config._rules[FeatureType.AGENT_MANAGEMENT]
        with caplog.at_level(logging.WARNING, logger="core.governance_config"):
            decision = config.check_governance(
                feature="agent_management",
                agent_id="a1",
                action="manage",
                maturity_level="INTERN",
            )
        assert decision.allowed is False
        assert decision.required_maturity == MaturityLevel.AUTONOMOUS
        assert "No governance rule" in caplog.text

    def test_no_rule_autonomous_allowed(self, config):
        del config._rules[FeatureType.AGENT_MANAGEMENT]
        decision = config.check_governance(
            feature="agent_management",
            agent_id="a1",
            action="manage",
            maturity_level="AUTONOMOUS",
        )
        assert decision.allowed is True

    def test_invalid_feature_autonomous_bypasses(self, config):
        decision = config.check_governance(
            feature="not-a-feature", agent_id="a1", action="x", maturity_level="AUTONOMOUS"
        )
        assert decision.allowed is True
        assert "bypasses validation" in decision.reason

    def test_invalid_feature_and_invalid_maturity_rejected(self, config):
        decision = config.check_governance(
            feature="not-a-feature", agent_id="a1", action="x", maturity_level="BOGUS"
        )
        assert decision.allowed is False
        assert "Invalid governance parameters" in decision.reason

    def test_valid_feature_invalid_maturity_rejected(self, config):
        decision = config.check_governance(
            feature="canvas_presentation", agent_id="a1", action="x", maturity_level="bogus"
        )
        assert decision.allowed is False
        assert decision.agent_maturity == MaturityLevel.STUDENT

    def test_invalid_complexity_rejected(self, config):
        decision = config.check_governance(
            feature="canvas_presentation", agent_id="a1", action="x",
            action_complexity=99, maturity_level="INTERN",
        )
        assert decision.allowed is False

    def test_invalid_complexity_autonomous_bypasses(self, config):
        """AUTONOMOUS agents bypass parameter validation by design."""
        decision = config.check_governance(
            feature="canvas_presentation", agent_id="a1", action="x",
            action_complexity=99, maturity_level="AUTONOMOUS",
        )
        assert decision.allowed is True

    def test_maturity_insufficient_reports_required(self, config):
        decision = config.check_governance(
            feature="device_command_execution", agent_id="a1", action="exec",
            action_complexity=4, maturity_level="INTERN",
        )
        assert decision.allowed is False
        assert decision.required_maturity == MaturityLevel.AUTONOMOUS
        assert decision.action_complexity == ActionComplexity.CRITICAL

    def test_complexity_insufficient_reports_required(self, config):
        decision = config.check_governance(
            feature="canvas_presentation", agent_id="a1", action="exec",
            action_complexity=4, maturity_level="STUDENT",
        )
        assert decision.allowed is False
        assert decision.required_maturity == MaturityLevel.AUTONOMOUS

    def test_full_pass(self, config):
        decision = config.check_governance(
            feature="browser_automation", agent_id="a1", action="navigate",
            action_complexity=2, maturity_level="INTERN",
        )
        assert decision.allowed is True
        assert decision.required_maturity == MaturityLevel.INTERN

    def test_emergency_bypass_returns_decision(self, monkeypatch, reset_global):
        monkeypatch.setenv("EMERGENCY_GOVERNANCE_BYPASS", "true")
        cfg = GovernanceConfig()
        decision = cfg.check_governance(
            feature="canvas_presentation", agent_id="a1", action="present"
        )
        assert decision.allowed is True
        assert decision.reason == "Emergency bypass active"


# ============================================================================
# Decision logging (denied branch + context merge)
# ============================================================================

class TestDecisionLoggingBranches:
    def test_denied_decision_logs_warning_with_context(self, config, caplog):
        with caplog.at_level(logging.WARNING, logger="core.governance_config"):
            config.log_governance_decision(
                feature="browser_automation", agent_id="a1", action="navigate",
                allowed=False, reason="denied", additional_context={"agent_maturity": "STUDENT"},
            )
        assert any("Blocked navigate" in r.message for r in caplog.records)
        assert any(r.agent_maturity == "STUDENT" for r in caplog.records)

    def test_allowed_decision_logs_info(self, config, caplog):
        with caplog.at_level(logging.INFO, logger="core.governance_config"):
            config.log_governance_decision(
                feature="canvas", agent_id="a1", action="present",
                allowed=True, reason="ok",
            )
        assert any("Allowed present" in r.message for r in caplog.records)

    def test_no_context_leaves_basic_fields(self, config, caplog):
        with caplog.at_level(logging.INFO, logger="core.governance_config"):
            config.log_governance_decision(
                feature="canvas", agent_id="a1", action="present", allowed=True, reason="ok"
            )
        record = [r for r in caplog.records if "Allowed present" in r.message][0]
        assert record.feature == "canvas"
        assert record.agent_id == "a1"


# ============================================================================
# validate_config warning path + validate_maturity_for_action
# ============================================================================

class TestValidateConfigWarnings:
    def test_student_critical_rule_warns(self, config):
        config._rules[FeatureType.CANVAS_PRESENTATION] = gc.GovernanceRule(
            feature=FeatureType.CANVAS_PRESENTATION,
            min_maturity=MaturityLevel.STUDENT,
            action_complexity=ActionComplexity.CRITICAL,
            description="bad",
        )
        result = config.validate_config()
        assert result["valid"] is True
        assert any(w["issue"] == "canvas_presentation allows CRITICAL actions with STUDENT maturity"
                   for w in result["warnings"])

    def test_valid_config_default(self, config):
        result = config.validate_config()
        assert result["valid"] is True
        assert result["rules_count"] == len(config.DEFAULT_RULES)
        assert result["features_governed"] == len(FeatureType)

    def test_emergency_bypass_issue(self, monkeypatch, reset_global):
        monkeypatch.setenv("EMERGENCY_GOVERNANCE_BYPASS", "true")
        cfg = GovernanceConfig()
        result = cfg.validate_config()
        assert result["valid"] is False
        assert result["issues"][0]["severity"] == "CRITICAL"

    def test_global_disabled_issue(self, monkeypatch, reset_global):
        monkeypatch.setenv("GOVERNANCE_ENABLED", "false")
        cfg = GovernanceConfig()
        result = cfg.validate_config()
        assert result["valid"] is False
        assert result["issues"][0]["severity"] == "HIGH"


class TestValidateMaturityForActionBranches:
    def test_all_complexity_levels(self, config):
        assert config.validate_maturity_for_action("STUDENT", 1) is True
        assert config.validate_maturity_for_action("INTERN", 2) is True
        assert config.validate_maturity_for_action("SUPERVISED", 3) is True
        assert config.validate_maturity_for_action("AUTONOMOUS", 4) is True

    def test_insufficient_combinations(self, config):
        assert config.validate_maturity_for_action("STUDENT", 2) is False
        assert config.validate_maturity_for_action("INTERN", 3) is False
        assert config.validate_maturity_for_action("SUPERVISED", 4) is False

    def test_invalid_maturity_string(self, config, caplog):
        with caplog.at_level(logging.ERROR, logger="core.governance_config"):
            assert config.validate_maturity_for_action("BOGUS", 2) is False
        assert "Invalid maturity/complexity" in caplog.text

    def test_invalid_complexity_value(self, config):
        assert config.validate_maturity_for_action("AUTONOMOUS", 9) is False
        assert config.validate_maturity_for_action("AUTONOMOUS", 0) is False

    def test_lowercase_maturity_rejected(self, config):
        assert config.validate_maturity_for_action("intern", 2) is False


# ============================================================================
# Convenience functions + singleton
# ============================================================================

class TestConvenienceFunctions:
    def test_get_governance_config_caches_singleton(self, reset_global):
        first = get_governance_config()
        second = get_governance_config()
        assert first is second

    def test_check_governance_logs_by_default(self, reset_global, caplog):
        with caplog.at_level(logging.INFO, logger="core.governance_config"):
            allowed, reason = check_governance(
                feature="canvas_presentation", agent_id="a1", action="present"
            )
        assert allowed is True
        assert any("Allowed present" in r.message for r in caplog.records)

    def test_check_governance_skip_logging(self, reset_global, caplog):
        with caplog.at_level(logging.INFO, logger="core.governance_config"):
            allowed, reason = check_governance(
                feature="canvas_presentation", agent_id="a1", action="present",
                log_decision=False,
            )
        assert allowed is True
        assert not any("Allowed present" in r.message for r in caplog.records)

    def test_check_governance_denied_tuple(self, reset_global):
        allowed, reason = check_governance(
            feature="device_command_execution", agent_id="a1", action="exec",
            action_complexity=4, maturity_level="STUDENT",
        )
        assert allowed is False
        assert "insufficient" in reason

    def test_is_governance_enabled_convenience(self, reset_global, monkeypatch):
        monkeypatch.setenv("GOVERNANCE_CANVAS_PRESENTATION_ENABLED", "false")
        assert is_governance_enabled("browser_automation") is True
        assert is_governance_enabled("canvas_presentation") is False

    def test_validate_maturity_convenience(self, reset_global):
        assert validate_maturity_for_action("AUTONOMOUS", 4) is True
        assert validate_maturity_for_action("STUDENT", 4) is False


# ============================================================================
# Dataclass + rule defaults sanity
# ============================================================================

class TestDataClasses:
    def test_governance_decision_defaults(self):
        d = GovernanceDecision(
            allowed=False, reason="r", feature=FeatureType.CANVAS_PRESENTATION,
            agent_maturity=MaturityLevel.STUDENT,
        )
        assert d.required_maturity is None
        assert d.action_complexity is None

    def test_required_maturity_unknown_feature_falls_back_autonomous(self, config):
        assert config.get_required_maturity(FeatureType.CANVAS_PRESENTATION) == MaturityLevel.STUDENT
        unknown = FeatureType("device_command_execution")
        config._rules.pop(unknown, None)
        assert config.get_required_maturity(unknown) == MaturityLevel.AUTONOMOUS
