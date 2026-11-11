"""Retained negative: check-only admission + zero-cost pending intent.

Two real budget admissions at 90/100 both pass because no reservation is
written. Two real provider settlements of 7 then produce 104, proving the
current path is not an atomic cap reservation. This is a scratch negative,
not a product test; it is preserved with its original failing output.
"""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime

import pytest

from tests.test_oracle_mini_app_host_mutations import USER, host
from core.agent_governance_service import AgentGovernanceService
from core.budget_enforcement_service import BudgetEnforcementService
from core.llm.byok_handler import BYOKHandler
from core.models import AgentRegistry, Tenant, TenantSetting, TokenUsage, Workspace
from core.spend_aggregation_service import SpendAggregationService

TENANT = "tenant-goal9-atomic-gap"
WORKSPACE = "ws-goal9-atomic-gap"
AGENT = "agent-goal9-atomic-gap"


def _seed(host):
    with host.Session() as db:
        db.add(Tenant(id=TENANT, name="Goal9 atomic gap", subdomain="goal9-atomic-gap"))
        db.add(Workspace(id=WORKSPACE, name="Goal9 atomic gap", tenant_id=TENANT))
        db.add(AgentRegistry(
            id=AGENT, name="Budget consumer", category="Operations",
            module_path="core.generic_agent", class_name="GenericAgent",
            user_id=USER, workspace_id=WORKSPACE, tenant_id=TENANT,
            status="autonomous", confidence_score=0.99))
        db.add(TenantSetting(
            tenant_id=TENANT, setting_key="billing",
            setting_value=json.dumps({
                "budget_limit_usd": 100.0,
                "enforcement": {"mode": "hard_stop"},
            })))
        db.add(TokenUsage(
            agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
            model_name="controlled-no-provider", cost_usd=90.0,
            timestamp=datetime.now()))
        db.commit()


def _settle(monkeypatch, attempt_id: str, cost: float = 7.0) -> None:
    from core.llm import byok_handler

    class _Pricing:
        def estimate_cost(self, model_name, input_tokens, output_tokens):
            return cost

    monkeypatch.setattr(byok_handler, "get_pricing_fetcher", lambda: _Pricing())
    monkeypatch.setattr(BYOKHandler, "_track_rate_usage", lambda *a, **k: None)
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT
    handler._record_provider_usage(
        "controlled", "controlled-model",
        {"usage": {"prompt_tokens": 100, "completion_tokens": 0}},
        agent_id=AGENT, request_id=attempt_id, attempt_id=attempt_id)


def _ledger(host) -> float:
    with host.Session() as db:
        return float(SpendAggregationService(db).update_tenant_spend(
            TENANT, persist=False)["current_spend_usd"])


def test_two_admissions_at_90_both_pass_then_104(host, monkeypatch):
    _seed(host)
    barrier = threading.Barrier(2)
    results = []

    def _admit():
        with host.Session() as db:
            barrier.wait(timeout=10)
            results.append(BudgetEnforcementService(db)
                           .check_budget_before_action_sync(
                               TENANT, AGENT, "llm_react_step"))

    threads = [threading.Thread(target=_admit) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert len(results) == 2
    assert all(r["allowed"] is True for r in results), results
    assert all(r["current_spend_usd"] == pytest.approx(90.0) for r in results)

    # Both paid attempts are real settlements; no reservation existed.
    _settle(monkeypatch, "gap-a1", 7.0)
    _settle(monkeypatch, "gap-a2", 7.0)
    assert _ledger(host) == pytest.approx(104.0)

    print("GOAL9_ATOMIC_GAP " + json.dumps({
        "admissions_allowed": [r["allowed"] for r in results],
        "admission_spend": [r["current_spend_usd"] for r in results],
        "ledger_after_two_settlements": _ledger(host),
    }, sort_keys=True))

    with host.Session() as db:
        refused = asyncio.run(AgentGovernanceService(
            db, workspace_id=WORKSPACE, tenant_id=TENANT,
        ).can_perform_action_async(AGENT, "llm_react_step"))
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_EXCEEDED"
