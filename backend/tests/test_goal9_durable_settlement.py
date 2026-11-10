"""Goal 9 durable settlement + hard-stop fail-closed controls.

Scratch SQLite only; doubled LLM response and controlled pricing stub. The
real `BYOKHandler._record_provider_usage` settlement writes the durable
`TokenUsage` ledger that SpendAggregation/admission reads. The real
`AgentGovernanceService` admission path is used.

Retained negative evidence (pre-fix in-memory-only settlement, hard-stop
fail-open) is in the packet's `retained_negative/`; this file asserts the
fixed contract. The conditional harness 104 twin remains explicitly
harness-authored.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.test_oracle_mini_app_host_mutations import USER, host
from core.agent_governance_service import AgentGovernanceService
from core.budget_enforcement_service import BudgetEnforcementService
from core.llm.byok_handler import BYOKHandler
from core.llm_usage_tracker import llm_usage_tracker
from core.models import AgentRegistry, Tenant, TenantSetting, TokenUsage, Workspace
from core.spend_aggregation_service import SpendAggregationService, record_llm_usage

TENANT = "tenant-goal9"
WORKSPACE = "ws-goal9"
AGENT = "agent-goal9"


def _seed(host, *, limit: float = 100.0, mode: str = "hard_stop",
          spend: float = 90.0) -> None:
    with host.Session() as db:
        db.add(Tenant(id=TENANT, name="Goal9 operator", subdomain="goal9-budget"))
        db.add(Workspace(id=WORKSPACE, name="Goal9 workspace", tenant_id=TENANT))
        db.add(AgentRegistry(
            id=AGENT, name="Budget consumer", category="Operations",
            module_path="core.generic_agent", class_name="GenericAgent",
            user_id=USER, workspace_id=WORKSPACE, tenant_id=TENANT,
            status="autonomous", confidence_score=0.99))
        db.add(TenantSetting(
            tenant_id=TENANT, setting_key="billing",
            setting_value=json.dumps({
                "budget_limit_usd": limit,
                "enforcement": {"mode": mode},
            })))
        if spend:
            db.add(TokenUsage(
                agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
                model_name="controlled-no-provider", cost_usd=spend,
                timestamp=datetime.now()))
        db.commit()
    llm_usage_tracker.reset_usage(WORKSPACE)


def _admit(host) -> dict:
    with host.Session() as db:
        return asyncio.run(AgentGovernanceService(
            db, workspace_id=WORKSPACE, tenant_id=TENANT,
        ).can_perform_action_async(AGENT, "llm_react_step"))


def _ledger(host) -> float:
    with host.Session() as db:
        return float(SpendAggregationService(db).update_tenant_spend(
            TENANT, persist=False)["current_spend_usd"])


def _unpriced(host) -> int:
    with host.Session() as db:
        return SpendAggregationService(db).get_unpriced_usage(TENANT)


def _settle(monkeypatch, *, attempt_id: str, cost: float = 7.0,
            request_id: str | None = None, agent_id: str | None = AGENT,
            tenant_id: str | None = TENANT,
            workspace_id: str | None = WORKSPACE,
            provider_id: str = "controlled",
            model: str = "controlled-model") -> float:
    """Real production settlement path; no provider/network."""
    from core.llm import byok_handler

    class _Pricing:
        def estimate_cost(self, model_name, input_tokens, output_tokens):
            return cost

    monkeypatch.setattr(byok_handler, "get_pricing_fetcher", lambda: _Pricing())
    monkeypatch.setattr(BYOKHandler, "_track_rate_usage", lambda *a, **k: None)
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = workspace_id
    handler.tenant_id = tenant_id
    response = {"usage": {"prompt_tokens": 100, "completion_tokens": 0}}
    _in, _out, settled = handler._record_provider_usage(
        provider_id, model, response, agent_id=agent_id,
        request_id=request_id or attempt_id, attempt_id=attempt_id)
    assert settled == cost
    return settled


def _settle_unknown(monkeypatch, *, attempt_id: str) -> None:
    """Real settlement with an unavailable price; cost must remain unknown."""
    from core.llm import byok_handler

    def _bad_fetcher():
        raise RuntimeError("pricing unavailable")

    monkeypatch.setattr(byok_handler, "get_pricing_fetcher", _bad_fetcher)
    monkeypatch.setattr(BYOKHandler, "_track_rate_usage", lambda *a, **k: None)
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT
    _in, _out, cost = handler._record_provider_usage(
        "controlled", "controlled-model",
        {"usage": {"prompt_tokens": 100, "completion_tokens": 0}},
        agent_id=AGENT, request_id=attempt_id, attempt_id=attempt_id)
    assert cost is None


def test_90_97_104_durable_settlement_then_refuses(host, monkeypatch):
    _seed(host, spend=90.0)
    _settle(monkeypatch, attempt_id="a1", cost=7.0)
    assert _ledger(host) == pytest.approx(97.0)
    _settle(monkeypatch, attempt_id="a2", cost=7.0)
    assert _ledger(host) == pytest.approx(104.0)
    refused = _admit(host)
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_EXCEEDED"


def test_duplicate_attempt_id_is_idempotent(host, monkeypatch):
    _seed(host, spend=90.0)
    _settle(monkeypatch, attempt_id="dup", cost=7.0)
    _settle(monkeypatch, attempt_id="dup", cost=7.0)
    assert _ledger(host) == pytest.approx(97.0)
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "dup").count() == 1


def test_multiple_paid_attempts_count_separately(host, monkeypatch):
    _seed(host, spend=90.0)
    _settle(monkeypatch, attempt_id="a1", cost=7.0)
    _settle(monkeypatch, attempt_id="a2", cost=7.0)
    assert _ledger(host) == pytest.approx(104.0)
    assert _unpriced(host) == 0


def test_restart_reads_durable_ledger(host, monkeypatch):
    _seed(host, spend=90.0)
    _settle(monkeypatch, attempt_id="a1", cost=7.0)
    assert _ledger(host) == pytest.approx(97.0)
    # New engine/session from the same scratch file = process-restart read.
    engine = create_engine(str(host.engine.url))
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        assert SpendAggregationService(db).update_tenant_spend(
            TENANT, persist=False)["current_spend_usd"] == pytest.approx(97.0)
    engine.dispose()


def test_scope_is_tenant_bound(host, monkeypatch):
    _seed(host, spend=0.0)
    with host.Session() as db:
        db.add(Tenant(id="other-tenant", name="Other",
                      subdomain="other-goal9"))
        db.commit()
    _settle(monkeypatch, attempt_id="a1", cost=7.0)
    with host.Session() as db:
        assert SpendAggregationService(db).update_tenant_spend(
            "other-tenant", persist=False)["current_spend_usd"] == pytest.approx(0.0)


def test_agent_and_non_agent_settle_without_inventing_identity(
        host, monkeypatch):
    _seed(host, spend=0.0)
    _settle(monkeypatch, attempt_id="agent-1", cost=7.0)
    _settle(monkeypatch, attempt_id="nonagent-1", cost=7.0, agent_id=None)
    with host.Session() as db:
        rows = db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT).order_by(TokenUsage.attempt_id).all()
        assert {r.attempt_id: r.agent_id for r in rows} == {
            "agent-1": AGENT, "nonagent-1": None}
    assert _ledger(host) == pytest.approx(14.0)
    # Unknown tenant is not invented/defaulted; it remains unattributed.
    record_llm_usage(
        provider_id="controlled", model_name="controlled-model",
        prompt_tokens=1, completion_tokens=0, cost_usd=3.0,
        agent_id=None, workspace_id=None, tenant_id=None,
        attempt_id="tenantless-1")
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "tenantless-1").one()
        assert row.tenant_id is None
    assert _ledger(host) == pytest.approx(14.0)


def test_unknown_is_liability_not_zero_and_hard_stop_refuses(
        host, monkeypatch):
    _seed(host, spend=90.0)
    _settle_unknown(monkeypatch, attempt_id="unknown-1")
    assert _ledger(host) == pytest.approx(90.0)  # NULL does not sum as 0
    assert _unpriced(host) == 1
    refused = _admit(host)
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_UNPRICED_USAGE"


def test_known_free_zero_is_allowed(host, monkeypatch):
    _seed(host, spend=90.0)
    _settle(monkeypatch, attempt_id="free-1", cost=0.0)
    assert _ledger(host) == pytest.approx(90.0)
    assert _unpriced(host) == 0
    assert _admit(host)["allowed"] is True


def test_hard_stop_unreadable_refuses_alert_only_observes(
        host, monkeypatch):
    _seed(host, spend=90.0, mode="hard_stop")
    monkeypatch.setattr(
        SpendAggregationService, "update_tenant_spend",
        lambda *a, **k: {"error": "unreadable ledger"})
    with host.Session() as db:
        refused = BudgetEnforcementService(db).check_budget_before_action_sync(
            TENANT, AGENT, "llm_react_step")
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_STATUS_UNAVAILABLE"

    with host.Session() as db:
        setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == TENANT).one()
        setting.setting_value = json.dumps({
            "budget_limit_usd": 100.0,
            "enforcement": {"mode": "alert_only"},
        })
        db.commit()
    with host.Session() as db:
        observed = BudgetEnforcementService(db).check_budget_before_action_sync(
            TENANT, AGENT, "llm_react_step")
    assert observed["allowed"] is True


def test_failed_semantic_attempt_cost_is_recorded(host, monkeypatch):
    """No quality/grounding verdict filters actual paid work."""
    _seed(host, spend=90.0)
    _settle(monkeypatch, attempt_id="failed-semantic-1", cost=7.0)
    assert _ledger(host) == pytest.approx(97.0)


def test_conditional_harness_104_twin_preserved(host):
    """Harness-authored settlement twin, explicitly not production evidence."""
    _seed(host, spend=90.0)
    assert _admit(host)["allowed"] is True
    assert _admit(host)["allowed"] is True
    with host.Session() as db:
        for _ in range(2):
            db.add(TokenUsage(
                agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
                model_name="controlled-no-provider", cost_usd=7.0,
                timestamp=datetime.now()))
        db.commit()
        ledger = SpendAggregationService(db).update_tenant_spend(
            TENANT, persist=False)
    assert ledger["current_spend_usd"] == pytest.approx(104.0)
    refused = _admit(host)
    assert refused["allowed"] is False


def test_normal_budget_valid_twin(host):
    _seed(host, spend=50.0)
    assert _admit(host)["allowed"] is True
    with host.Session() as db:
        db.add(TokenUsage(
            agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
            model_name="controlled-no-provider", cost_usd=50.0,
            timestamp=datetime.now()))
        db.commit()
    refused = _admit(host)
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_EXCEEDED"
