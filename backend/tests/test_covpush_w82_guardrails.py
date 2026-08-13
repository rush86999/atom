# -*- coding: utf-8 -*-
"""Coverage wave 82 — core/autonomous_guardrails (AutonomousGuardrailService).

In-memory SQLite with the real models (AgentRegistry / TokenUsage /
AgentExecution); no network, no LLM spend.

Coverage targets:
- check_guardrails: agent-not-found (±tenant filter), model capability gate
  (blocked/advanced-model pass/low-complexity pass), danger zone (action name
  match, terminal command substring, non-match), rate limit (hit/miss, custom
  config value), daily cost gate (alert_only / soft_stop ±active episode /
  hard_stop / unknown mode), sensitivity interlock (transfer >$500, batch
  delete >10, critical resource_type, non-sensitive), all-pass.
- _check_model_capability: high-complexity prefix matrix, substring advanced
  model match, unknown model.
- _is_in_danger_zone: category match, terminal command match, miss.
- _get_recent_action_count / _get_daily_spend: ±tenant filter.
- _is_sensitive_action: transfer/payment threshold, mass delete, resource type.
- handle_violation: downgrade+commit, no-agent no-op, non-listed violation
  type, tenant-scoped lookup.
- _cancel_active_episodes: cancel running, none running, exception path.
- Robustness (BUG W82-3): string `amount` must not crash the guardrail;
  non-dict `guardrails` config must not crash; non-dict configuration.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentExecution, AgentRegistry, AgentStatus, TokenUsage  # noqa: F401

from core.autonomous_guardrails import AutonomousGuardrailService


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1", tenant_id="t1", workspace_id="ws-1",
                config=None, status=AgentStatus.AUTONOMOUS.value):
    agent = AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        category="Test",
        module_path="test",
        class_name="Test",
        status=status,
        configuration=config or {},
    )
    db.add(agent)
    db.commit()
    return agent


def _make_usage(db, agent_id="agent-1", tenant_id="t1", workspace_id="ws-1",
                cost=0.0, minutes_ago=10):
    usage = TokenUsage(
        agent_id=agent_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        model_name="gpt-4o",
        cost_usd=cost,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db.add(usage)
    db.commit()
    return usage


def _make_execution(db, agent_id="agent-1", workspace_id="ws-1", status="running"):
    exec_ = AgentExecution(
        agent_id=agent_id,
        workspace_id=workspace_id,
        tenant_id="t1",
        status=status,
        triggered_by="manual",
    )
    db.add(exec_)
    db.commit()
    return exec_


class TestCheckGuardrailsBasics:
    def test_agent_not_found(self, db):
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("ghost", "read_doc", {})
        assert result["proceed"] is False
        assert result["reason"] == "Agent not found"
        assert result["requires_downgrade"] is False

    def test_agent_not_found_tenant_filtered(self, db):
        _make_agent(db, agent_id="a1", tenant_id="t1")
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("a1", "read_doc", {}, tenant_id="t2")
        assert result["proceed"] is False
        assert result["reason"] == "Agent not found"

    def test_agent_not_found_self_tenant(self, db):
        _make_agent(db, agent_id="a1", tenant_id="t1")
        svc = AutonomousGuardrailService(db, workspace_id="ws-1", tenant_id="t2")
        result = svc.check_guardrails("a1", "read_doc", {})
        assert result["proceed"] is False

    def test_all_guardrails_pass(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "read_report", {"model_name": "gpt-4o-mini"}
        )
        assert result["proceed"] is True
        assert result["reason"] == "All guardrails passed."
        assert result["requires_downgrade"] is False


class TestModelCapability:
    def test_high_complexity_weak_model_blocked(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "execute_payment", {"model_name": "gpt-3.5-turbo"}
        )
        assert result["proceed"] is False
        assert result["violation_type"] == "model_mismatch"
        assert "insufficient" in result["reason"]

    def test_high_complexity_advanced_model_passes(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "execute_payment", {"model_name": "gpt-4o"}
        )
        assert result["proceed"] is True

    def test_model_capability_unknown_model_default(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "update_agent_config", {})
        assert result["proceed"] is False
        assert result["violation_type"] == "model_mismatch"

    def test_low_complexity_any_model(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "read_report", {"model_name": "gpt-3.5-turbo"}
        )
        assert result["proceed"] is True

    def test_advanced_model_substring_match(self, db):
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        check = svc._check_model_capability("approve_transfer", "Claude-3-5-Sonnet-20241022")
        assert check["allowed"] is True


class TestDangerZone:
    def test_action_name_match(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "get_ssn", {"model_name": "gpt-4o"})
        assert result["proceed"] is False
        assert result["violation_type"] == "danger_zone"
        assert "Danger Zone" in result["reason"]

    def test_terminal_command_match(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "run_terminal", {"model_name": "gpt-4o", "command": "sudo rm -rf /tmp/x"}
        )
        assert result["proceed"] is False
        assert result["violation_type"] == "danger_zone"

    def test_terminal_clean_command_passes_model_gate(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "run_terminal", {"model_name": "gpt-4o", "command": "ls -la"}
        )
        # terminal commands are not high-complexity prefixes → model gate ok
        assert result["proceed"] is True

    def test_is_in_danger_zone_miss(self, db):
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        assert svc._is_in_danger_zone("send_message", {}) is False
        assert svc._is_in_danger_zone("run_terminal", {"command": "echo hi"}) is False

    def test_mass_comm_danger(self, db):
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        assert svc._is_in_danger_zone("broadcast_slack_all", {}) is True
        assert svc._is_in_danger_zone("send_bulk_email", {}) is True


class TestRateLimit:
    def test_rate_limit_blocked(self, db):
        _make_agent(db, config={"guardrails": {"max_actions_per_hour": 2}})
        _make_usage(db)
        _make_usage(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is False
        assert result["violation_type"] == "rate_limit"
        assert result["requires_downgrade"] is True
        assert "2/2" in result["reason"]

    def test_rate_limit_custom_config(self, db):
        _make_agent(db, config={"guardrails": {"max_actions_per_hour": 1}})
        _make_usage(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is False
        assert result["violation_type"] == "rate_limit"

    def test_rate_limit_under(self, db):
        _make_agent(db, config={"guardrails": {"max_actions_per_hour": 10}})
        _make_usage(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is True

    def test_recent_action_count_tenant_filter(self, db):
        _make_agent(db)
        _make_usage(db)
        _make_usage(db, tenant_id="other")
        svc = AutonomousGuardrailService(db, workspace_id="ws-1", tenant_id="t1")
        assert svc._get_recent_action_count("agent-1", tenant_id="t1", hours=1) == 1


class TestDailyCostGate:
    def test_alert_only_proceeds(self, db):
        _make_agent(db, config={"guardrails": {"enforcement_mode": "alert_only"}})
        _make_usage(db, cost=20.0)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is True
        assert "Alert Only" in result["reason"]

    def test_soft_stop_with_active_episode(self, db):
        _make_agent(db, config={"guardrails": {"enforcement_mode": "soft_stop"}})
        _make_usage(db, cost=20.0)
        _make_execution(db, status="running")
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is True
        assert result["violation_type"] == "cost_gate_soft"

    def test_soft_stop_blocks_new_episodes(self, db):
        _make_agent(db, config={"guardrails": {"enforcement_mode": "soft_stop"}})
        _make_usage(db, cost=20.0)
        _make_execution(db, status="completed")
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is False
        assert result["violation_type"] == "cost_gate"
        assert result["requires_downgrade"] is True

    def test_hard_stop_cancels_episodes(self, db):
        _make_agent(db, config={"guardrails": {"enforcement_mode": "hard_stop"}})
        _make_usage(db, cost=20.0)
        _make_execution(db, status="running")
        _make_execution(db, status="running")
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is False
        assert result["violation_type"] == "cost_gate_hard"
        cancelled = db.query(AgentExecution).filter(AgentExecution.status == "cancelled").count()
        assert cancelled == 2

    def test_unknown_mode_blocks(self, db):
        _make_agent(db, config={"guardrails": {"enforcement_mode": "mystery"}})
        _make_usage(db, cost=20.0)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is False
        assert result["violation_type"] == "cost_gate"

    def test_under_limit_passes(self, db):
        _make_agent(db)
        _make_usage(db, cost=1.0)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is True

    def test_daily_spend_tenant_filter(self, db):
        _make_agent(db)
        _make_usage(db, cost=5.0)
        _make_usage(db, tenant_id="other", cost=100.0)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1", tenant_id="t1")
        assert svc._get_daily_spend("agent-1", tenant_id="t1") == 5.0


class TestSensitivityInterlock:
    def test_transfer_over_500(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "make_transfer", {"model_name": "gpt-4o", "amount": 501}
        )
        assert result["proceed"] is False
        assert result["violation_type"] == "sensitivity_interlock"

    def test_transfer_under_500(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "make_transfer", {"model_name": "gpt-4o", "amount": 400}
        )
        assert result["proceed"] is True

    def test_payment_alert_sensitive(self, db):
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        assert svc._is_sensitive_action("process_payment", {"amount": 999}) is True

    def test_mass_delete_batch(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "delete_records", {"model_name": "gpt-4o", "batch_count": 11}
        )
        assert result["proceed"] is False
        assert result["violation_type"] == "sensitivity_interlock"

    def test_delete_critical_resource(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "delete_thing", {"model_name": "gpt-4o", "resource_type": "database"}
        )
        assert result["proceed"] is False

    def test_small_delete_allowed(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "delete_temp", {"model_name": "gpt-4o", "batch_count": 2}
        )
        assert result["proceed"] is True

    def test_bad_batch_count_no_crash(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "delete_temp", {"model_name": "gpt-4o", "batch_count": "abc"}
        )
        assert result["proceed"] is True

    def test_string_amount_does_not_crash(self, db):
        """BUG W82-3: string `amount` (e.g. '999') previously raised TypeError
        in `_is_sensitive_action`, crashing the guardrail check (fail-open at
        the caller: no BLOCKED_BY_GUARDRAIL is ever returned)."""
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "make_transfer", {"model_name": "gpt-4o", "amount": "999"}
        )
        assert result["proceed"] is False
        assert result["violation_type"] == "sensitivity_interlock"

    def test_non_numeric_amount_no_crash(self, db):
        _make_agent(db)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails(
            "agent-1", "make_transfer", {"model_name": "gpt-4o", "amount": "abc"}
        )
        # Not comparable → not a financial threshold violation; must not crash.
        assert result["proceed"] is True

    def test_non_dict_guardrails_config_no_crash(self, db):
        """BUG W82-3b: `configuration['guardrails']` as a non-dict (e.g. the
        string 'off') crashed config.get('guardrails').get(...)."""
        _make_agent(db, config={"guardrails": "off"})
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        result = svc.check_guardrails("agent-1", "read_report", {"model_name": "gpt-4o"})
        assert result["proceed"] is True


class TestHandleViolation:
    def test_downgrade_to_supervised(self, db):
        _make_agent(db, status=AgentStatus.AUTONOMOUS.value)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        svc.handle_violation("agent-1", "rate_limit", "too many")
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == "agent-1").first()
        assert agent.status == AgentStatus.SUPERVISED.value

    def test_cost_gate_hard_downgrades(self, db):
        _make_agent(db, status=AgentStatus.AUTONOMOUS.value)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        svc.handle_violation("agent-1", "cost_gate_hard", "spent")
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == "agent-1").first()
        assert agent.status == AgentStatus.SUPERVISED.value

    def test_non_downgrade_violation_no_status_change(self, db):
        _make_agent(db, status=AgentStatus.AUTONOMOUS.value)
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        svc.handle_violation("agent-1", "danger_zone", "nope")
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == "agent-1").first()
        assert agent.status == AgentStatus.AUTONOMOUS.value

    def test_agent_not_found_noop(self, db):
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        assert svc.handle_violation("ghost", "rate_limit", "x") is None

    def test_tenant_scoped_lookup(self, db):
        _make_agent(db, agent_id="a1", tenant_id="t1")
        svc = AutonomousGuardrailService(db, workspace_id="ws-1", tenant_id="t2")
        assert svc.handle_violation("a1", "rate_limit", "x") is None


class TestCancelActiveEpisodes:
    def test_cancel_running(self, db):
        _make_agent(db)
        _make_execution(db, status="running")
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        assert svc._cancel_active_episodes("agent-1") == 1

    def test_cancel_none_running(self, db):
        _make_agent(db)
        _make_execution(db, status="completed")
        svc = AutonomousGuardrailService(db, workspace_id="ws-1")
        assert svc._cancel_active_episodes("agent-1") == 0

    def test_cancel_exception_rolls_back(self, db):
        class BoomDB:
            def __init__(self, inner):
                self._inner = inner
                self.rolled = False

            def query(self, model):
                if model is AgentExecution:
                    raise RuntimeError("db down")
                return self._inner.query(model)

            def rollback(self):
                self.rolled = True

        boom = BoomDB(db)
        svc = AutonomousGuardrailService(boom, workspace_id="ws-1")
        assert svc._cancel_active_episodes("agent-1") == 0
        assert boom.rolled is True
