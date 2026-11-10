"""Goal 9 production-consumer evidence — durable budget ledger vs actual spend.

Scratch SQLite only. The LLM transport is a doubled response; the only cost
source is a controlled pricing stub. No provider, model, network, credential or
live dollar spend is used.

The admission consumer is the real ``AgentGovernanceService`` path used by
GenericAgent/AtomMetaAgent tool dispatch. The settlement consumer is the real
``BYOKHandler._record_provider_usage`` path called after an LLM response.

The first test records the actual negative: production LLM settlement does not
write the durable ``TokenUsage``/ACU ledger that the configured budget
admission reads, and the separate in-memory tracker's budget is never set.
The second test is an explicitly harness-authored settlement twin; it shows the
latent non-atomic admission only if settlement rows existed. The third is the
normal valid twin for the existing hard-stop behavior.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from tests.test_oracle_mini_app_host_mutations import (
    USER,
    host,
)
from core.agent_governance_service import AgentGovernanceService
from core.budget_enforcement_service import BudgetEnforcementService
from core.llm.byok_handler import BYOKHandler
from core.llm_usage_tracker import llm_usage_tracker
from core.models import AgentRegistry, Tenant, TenantSetting, TokenUsage, Workspace
from core.spend_aggregation_service import SpendAggregationService

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


def _settle(monkeypatch, *, cost: float = 7.0) -> float:
    """Call the real production settlement method; no network/provider."""
    from core.llm import byok_handler

    class _Pricing:
        def estimate_cost(self, model, input_tokens, output_tokens):
            return cost

    monkeypatch.setattr(byok_handler, "get_pricing_fetcher", lambda: _Pricing())
    monkeypatch.setattr(BYOKHandler, "_track_rate_usage", lambda *a, **k: None)
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    response = {"usage": {"prompt_tokens": 100, "completion_tokens": 0}}
    _in, _out, settled = handler._record_provider_usage(
        "controlled", "controlled-model", response, agent_id=AGENT)
    assert settled == cost
    return settled


def _ledger(host) -> float:
    with host.Session() as db:
        return float(SpendAggregationService(db).update_tenant_spend(
            TENANT, persist=False)["current_spend_usd"])


def test_production_llm_settlement_does_not_reach_configured_ledger(
        host, monkeypatch):
    """The actual negative: configured admission reads a ledger production
    settlement does not write, so the 90+7+7 joint spend cannot be observed
    as a durable 104 by the configured budget."""
    _seed(host, spend=90.0)
    assert _admit(host)["allowed"] is True
    assert _admit(host)["allowed"] is True

    # Two real production settlement calls, each server-owned at 7.
    _settle(monkeypatch, cost=7.0)
    _settle(monkeypatch, cost=7.0)

    # The durable configured ledger is unchanged: no production TokenUsage
    # writer; the real spend went to the in-memory tracker.
    assert _ledger(host) == pytest.approx(90.0)
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT).count() == 1

    # The separate in-memory tracker saw 14 today, but its budget is unset;
    # the BYOK hard guard therefore cannot enforce the configured limit.
    assert llm_usage_tracker.get_usage(WORKSPACE) == pytest.approx(14.0)
    assert llm_usage_tracker.get_budget(WORKSPACE) is None
    assert llm_usage_tracker.is_budget_exceeded(WORKSPACE) is False

    # Configured admission still sees 90 and admits another request.
    assert _admit(host)["allowed"] is True


def test_harness_settlement_twin_shows_latent_non_atomic_admission(host):
    """Harness-authored twin, NOT production evidence.

    The production consumer does not write these settlement rows. If the
    intended durable settlement existed, both admissions at 90 would pass and
    the ledger would reach 104; this is the latent preflight race only.
    """
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
    assert refused.get("status_code") == "BUDGET_EXCEEDED"


def test_normal_budget_valid_twin(host):
    """Existing hard-stop semantics remain truthful for the seeded ledger."""
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


def test_configured_hard_stop_unreadable_budget_currently_fails_open(
        host, monkeypatch):
    """Unsafe current behavior, pinned as a negative.

    A configured hard_stop with an unreadable spend ledger currently returns
    allowed=True / enforcement_mode='unknown'. This is not a cap pass; a
    hard-stop admission must refuse or require an explicit override.
    """
    _seed(host, spend=90.0)
    monkeypatch.setattr(
        SpendAggregationService, "update_tenant_spend",
        lambda *a, **k: {"error": "unreadable ledger"})
    with host.Session() as db:
        result = BudgetEnforcementService(db).check_budget_before_action_sync(
            TENANT, AGENT, "llm_react_step")
    assert result["allowed"] is True
    assert result["enforcement_mode"] == "unknown"
    assert result["reason"] == "Unable to verify spend"


def test_configured_hard_stop_failed_admission_exception_currently_allows(
        host, monkeypatch):
    """Unsafe current behavior at the explicit except fail-open (line ~252)."""
    _seed(host, spend=90.0)

    def _raise(*a, **k):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(SpendAggregationService, "update_tenant_spend", _raise)
    with host.Session() as db:
        result = BudgetEnforcementService(db).check_budget_before_action_sync(
            TENANT, AGENT, "llm_react_step")
    assert result["allowed"] is True
    assert result["enforcement_mode"] == "unknown"
    assert result["reason"] == "Unable to verify spend"


def test_production_consumer_hard_stop_failed_admission_currently_allows(
        host, monkeypatch):
    """The real governance consumer inherits the same unsafe fail-open."""
    _seed(host, spend=90.0)

    def _raise(*a, **k):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(SpendAggregationService, "update_tenant_spend", _raise)
    with host.Session() as db:
        result = asyncio.run(AgentGovernanceService(
            db, workspace_id=WORKSPACE, tenant_id=TENANT,
        ).can_perform_action_async(AGENT, "llm_react_step"))
    assert result["allowed"] is True


def test_settlement_pricing_error_records_zero_not_unknown(host, monkeypatch):
    """A pricing/settlement error is swallowed and recorded as cost 0.

    `0` is a real free cost; `unknown` is not. The current path conflates them
    and leaves the configured hard-stop ledger unchanged.
    """
    _seed(host, spend=90.0)
    from core.llm import byok_handler

    def _bad_fetcher():
        raise RuntimeError("pricing unavailable")

    monkeypatch.setattr(byok_handler, "get_pricing_fetcher", _bad_fetcher)
    monkeypatch.setattr(BYOKHandler, "_track_rate_usage", lambda *a, **k: None)
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    _in, _out, cost = handler._record_provider_usage(
        "controlled", "controlled-model",
        {"usage": {"prompt_tokens": 100, "completion_tokens": 0}},
        agent_id=AGENT)
    assert cost is None
    assert llm_usage_tracker.get_usage(WORKSPACE) == pytest.approx(0.0)
    assert _ledger(host) == pytest.approx(90.0)
    assert _admit(host)["allowed"] is True


def test_alert_only_observe_semantics_remain_allowed(host):
    """alert_only is deliberately observe/warn; it is distinct from hard_stop."""
    _seed(host, spend=150.0, mode="alert_only")
    assert _admit(host)["allowed"] is True

