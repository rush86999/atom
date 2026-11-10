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
import logging
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
from core.models import (
    AgentRegistry,
    Tenant,
    TenantSetting,
    TokenUsage,
    User,
    Workspace,
)
from core.spend_aggregation_service import (
    BudgetReservationRefused,
    SpendAggregationService,
    begin_llm_usage,
    record_llm_usage,
)

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


def _structured_handler(monkeypatch):
    """Real structured consumer with a doubled sync provider response.

    Returns the handler and a mutable call counter. The provider is never
    contacted; costs are controlled. The real settlement/durable-intent path
    is exercised.
    """
    from contextlib import contextmanager
    from core.llm import byok_handler

    calls = {"count": 0}

    class _FakeResult:
        def __init__(self):
            self._raw_response = {
                "choices": [{
                    "message": {"content": '{"ok": true}'},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 100, "completion_tokens": 0},
            }

    class _FakeCompletions:
        def create(self, **kwargs):
            calls["count"] += 1
            return _FakeResult()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeInstructor:
        chat = _FakeChat()

    class _Pricing:
        def estimate_cost(self, model_name, input_tokens, output_tokens):
            return 7.0

    @contextmanager
    def _fake_db():
        class _Query:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return None

        class _DB:
            def query(self, *args, **kwargs):
                return _Query()

        yield _DB()

    monkeypatch.setattr(byok_handler, "get_db_session", _fake_db)
    monkeypatch.setattr(
        byok_handler.instructor, "from_openai",
        lambda *a, **k: _FakeInstructor())
    monkeypatch.setattr(
        byok_handler, "get_pricing_fetcher", lambda: _Pricing())

    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT
    handler.clients = {"openai": object()}
    handler.env_key_providers = {"openai"}
    handler._local_routes = set()
    handler.refresh_credentials_if_changed = lambda: None
    handler._is_trial_restricted = lambda: False
    handler.analyze_query_complexity = (
        lambda *a, **k: byok_handler.QueryComplexity.MODERATE)

    async def _optimal(*a, **k):
        return ("openai", "gpt-4o-mini")

    async def _ranked(*a, **k):
        return [("openai", "gpt-4o-mini")]

    async def _feedback(*a, **k):
        return None

    handler.get_optimal_provider = _optimal
    handler.get_ranked_providers = _ranked
    handler._record_outcome_feedback = _feedback
    handler._record_provider_usage = (
        BYOKHandler._record_provider_usage.__get__(handler, BYOKHandler))
    handler._track_rate_usage = lambda *a, **k: None
    handler._track_llm_call = lambda *a, **k: None
    handler._provider_cooldown_active = lambda *a, **k: False
    handler._model_cooldown_active = lambda *a, **k: False
    handler._dispatch_catalog_admits = lambda *a, **k: True
    handler._structured_route_trace_enabled = lambda: False
    handler._trace_structured_route = lambda *a, **k: None
    handler._bench_model = lambda *a, **k: None
    handler._clear_model_cooldown = lambda *a, **k: None
    handler._claim_model_attempt = lambda *a, **k: "token"
    handler._release_model_attempt = lambda *a, **k: None
    handler._stamp_sample_logprob = lambda *a, **k: None
    handler.get_context_window = lambda *a, **k: 100000
    handler._pinned_model_fits = lambda *a, **k: True
    handler._moa_eligible = lambda *a, **k: False
    handler.byok_manager = None
    return handler, calls


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
    _settle(monkeypatch, attempt_id="a2", cost=7.0)
    assert _ledger(host) == pytest.approx(104.0)
    # New engine/session from the same scratch file = process-restart read.
    # Actual cost must reach both SpendAggregation and the next production
    # admission after restart, not just the original session.
    engine = create_engine(str(host.engine.url))
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        assert SpendAggregationService(db).update_tenant_spend(
            TENANT, persist=False)["current_spend_usd"] == pytest.approx(104.0)
        refused = asyncio.run(AgentGovernanceService(
            db, workspace_id=WORKSPACE, tenant_id=TENANT,
        ).can_perform_action_async(AGENT, "llm_react_step"))
        assert refused["allowed"] is False
        assert refused.get("status_code") == "BUDGET_EXCEEDED"
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


def test_known_free_contract_is_authoritative_zero_without_usage(
        host, monkeypatch):
    """A trusted free contract gives 0 even when the response has no usage.

    No model-name/brand assumption is made: the caller must supply the
    contract explicitly via known_free.
    """
    _seed(host, spend=90.0)
    monkeypatch.setattr(BYOKHandler, "_track_rate_usage", lambda *a, **k: None)
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT
    _in, _out, cost = handler._record_provider_usage(
        "controlled", "controlled-model", {},
        agent_id=AGENT, request_id="free-no-usage",
        attempt_id="free-no-usage", known_free=True)
    assert cost == 0.0
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "free-no-usage").one()
        assert row.cost_usd == 0.0
        assert row.pricing_status == "free"
    assert _ledger(host) == pytest.approx(90.0)
    assert _unpriced(host) == 0
    assert _admit(host)["allowed"] is True


def test_hard_stop_unpriced_read_failure_refuses(host, monkeypatch):
    _seed(host, spend=90.0)
    monkeypatch.setattr(
        SpendAggregationService, "get_unpriced_usage",
        lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("unpriced read unavailable")))
    with host.Session() as db:
        refused = BudgetEnforcementService(db).check_budget_before_action_sync(
            TENANT, AGENT, "llm_react_step")
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_STATUS_UNAVAILABLE"


def test_upgrade_failure_keeps_hard_stop_closed(host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    from core import sqlite_schema_repair as repair

    monkeypatch.setattr(repair, "_TOKEN_USAGE_UPGRADE_FAILURE", None)
    repair._REPAIRED.clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-fail.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE token_usage ("
            " id VARCHAR NOT NULL PRIMARY KEY,"
            " agent_id VARCHAR NOT NULL,"
            " tenant_id VARCHAR NOT NULL,"
            " model_name VARCHAR NOT NULL,"
            " cost_usd FLOAT)"
        )

    def _begin_fails():
        raise RuntimeError("ddl unavailable")

    monkeypatch.setattr(engine, "begin", _begin_fails)
    repair.ensure_token_usage_upgrade(engine)
    assert repair.token_usage_upgrade_failure_reason()
    refused = _admit(host)
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_STATUS_UNAVAILABLE"
    engine.dispose()


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


def test_missing_usage_is_unknown_not_omitted(host, monkeypatch):
    _seed(host, spend=90.0)
    monkeypatch.setattr(BYOKHandler, "_track_rate_usage", lambda *a, **k: None)
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT
    _in, _out, cost = handler._record_provider_usage(
        "controlled", "controlled-model", {},
        agent_id=AGENT, request_id="no-usage", attempt_id="no-usage")
    assert cost is None
    assert _unpriced(host) == 1
    refused = _admit(host)
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_UNPRICED_USAGE"


def test_unresolved_scope_unknown_is_visible_to_hardstop(host):
    _seed(host, spend=90.0)
    record_llm_usage(
        provider_id="controlled", model_name="controlled-model",
        prompt_tokens=0, completion_tokens=0, cost_usd=None,
        agent_id=None, workspace_id=None, tenant_id=None,
        attempt_id="unscoped-unknown")
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "unscoped-unknown").one()
        assert row.tenant_id is None
        assert row.pricing_status == "unknown"
    refused = _admit(host)
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_UNATTRIBUTED_USAGE"


def test_trusted_handler_scope_carrier(host, monkeypatch):
    _seed(host, spend=0.0)
    from core.llm import byok_handler

    class _Pricing:
        def estimate_cost(self, model_name, input_tokens, output_tokens):
            return 0.01

    monkeypatch.setattr(byok_handler, "get_pricing_fetcher", lambda: _Pricing())
    monkeypatch.setattr(BYOKHandler, "_track_rate_usage", lambda *a, **k: None)
    handler = BYOKHandler(workspace_id=WORKSPACE, tenant_id=TENANT)
    _in, _out, cost = handler._record_provider_usage(
        "controlled", "controlled-model",
        {"usage": {"prompt_tokens": 10, "completion_tokens": 1}},
        agent_id=AGENT, request_id="scope-carrier",
        attempt_id="scope-carrier")
    assert cost == pytest.approx(0.01)
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "scope-carrier").one()
        assert row.tenant_id == TENANT
        assert row.workspace_id == WORKSPACE
        assert row.agent_id == AGENT
    assert _ledger(host) == pytest.approx(0.01)


def test_llm_service_scope_carrier_and_unresolved_refusal(host):
    """LLMService selects the trusted handler scope or refuses; it never
    substitutes a default/guessed tenant or workspace."""
    from core.llm_service import LLMService

    _seed(host, spend=0.0)
    with host.Session() as db:
        svc = LLMService(db=db, workspace_id=WORKSPACE, tenant_id=TENANT)
        handler = svc._get_handler(workspace_id=WORKSPACE, tenant_id=TENANT)
        assert handler is not None
        assert handler.workspace_id == WORKSPACE
        assert handler.tenant_id == TENANT
        # A named tenant with no unique workspace binding is unresolved:
        # no handler is returned, so no provider dispatch/settlement occurs.
        assert svc._get_handler(tenant_id="tenant-without-workspace") is None


def test_settlement_persistence_failure_does_not_fake_success(
        host, monkeypatch):
    _seed(host, spend=90.0)
    from core import spend_aggregation_service as spend_service_module

    monkeypatch.setattr(
        spend_service_module, "_SETTLEMENT_FAILURE_REASON", None)
    caller = host.Session()
    try:
        user = caller.get(User, USER)
        old_name = user.first_name
        user.first_name = "caller-pending"
        caller.flush()

        from core.llm import byok_handler

        class _Pricing:
            def estimate_cost(self, model_name, input_tokens, output_tokens):
                return 7.0

        monkeypatch.setattr(byok_handler, "get_pricing_fetcher", lambda: _Pricing())
        monkeypatch.setattr(BYOKHandler, "_track_rate_usage", lambda *a, **k: None)

        def _db_down():
            raise RuntimeError("settlement ledger unavailable")

        # Settlement opens a dedicated SessionLocal; this failure must be
        # logged/surfaced, not converted into a fake settled budget.
        from core import database as database_module

        real_session_local = database_module.SessionLocal
        monkeypatch.setattr("core.database.SessionLocal", _db_down)
        handler = object.__new__(BYOKHandler)
        handler.workspace_id = WORKSPACE
        handler.tenant_id = TENANT
        _in, _out, cost = handler._record_provider_usage(
            "controlled", "controlled-model",
            {"usage": {"prompt_tokens": 100, "completion_tokens": 0}},
            agent_id=AGENT, request_id="persist-fail",
            attempt_id="persist-fail")
        assert cost == 7.0
        assert _ledger(host) == pytest.approx(90.0)
        with host.Session() as observer:
            assert observer.get(User, USER).first_name == old_name
        # The lost write is not a successful budget: hard_stop refuses until
        # restart/reconciliation rather than allowing on the undercount.
        refused = _admit(host)
        assert refused["allowed"] is False
        assert refused.get("status_code") == "BUDGET_STATUS_UNAVAILABLE"

        # The ledger recovers, but the paid call's settlement was lost. The
        # next admission must NOT become normal on the undercount; the
        # degraded marker keeps it refused until explicit reconciliation.
        monkeypatch.setattr("core.database.SessionLocal", real_session_local)
        with host.Session() as observer:
            assert SpendAggregationService(observer).update_tenant_spend(
                TENANT, persist=False)["current_spend_usd"] == pytest.approx(90.0)
        still_refused = _admit(host)
        assert still_refused["allowed"] is False
        assert still_refused.get("status_code") == "BUDGET_STATUS_UNAVAILABLE"
    finally:
        caller.rollback()
        caller.close()


def test_structured_no_trace_calls_get_distinct_server_identities(
        host, monkeypatch):
    """Two independent no-trace structured calls with identical material are
    distinct paid generations, not a duplicate. A genuine replay of one
    settlement stays idempotent."""
    _seed(host, spend=0.0)
    handler, _calls = _structured_handler(monkeypatch)

    for _ in range(2):
        asyncio.run(handler.generate_structured_response(
            prompt="same prompt",
            system_instruction="Return JSON",
            response_model=dict,
            task_type="analysis",
            allow_moa=False,
            route_trace_id=None,
        ))

    with host.Session() as db:
        rows = db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT).order_by(
            TokenUsage.attempt_id).all()
        assert len(rows) == 2, [r.attempt_id for r in rows]
        assert len({r.attempt_id for r in rows}) == 2
        assert len({r.request_id for r in rows}) == 2
        assert all(r.cost_usd == pytest.approx(7.0) for r in rows)
        first = rows[0]

    # Genuine replay of the first settlement is idempotent, not a third row.
    replay_id = record_llm_usage(
        provider_id=first.provider_id,
        model_name=first.model_name,
        prompt_tokens=first.prompt_tokens,
        completion_tokens=first.completion_tokens,
        cost_usd=first.cost_usd,
        agent_id=first.agent_id,
        workspace_id=first.workspace_id,
        tenant_id=first.tenant_id,
        request_id=first.request_id,
        attempt_id=first.attempt_id,
    )
    assert replay_id == first.id
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT).count() == 2


def test_durable_intent_survives_restart_when_settlement_write_fails(
        host, monkeypatch):
    """Provider succeeded, settlement write failed, process restarts: the
    unresolved attempt must still block the next admission."""
    _seed(host, spend=90.0)
    handler, calls = _structured_handler(monkeypatch)
    from core import spend_aggregation_service as spend_module
    from core import sqlite_schema_repair as repair

    def _settlement_down(*args, **kwargs):
        raise RuntimeError("settlement write failed")

    monkeypatch.setattr(
        spend_module, "record_llm_usage", _settlement_down)
    result = asyncio.run(handler.generate_structured_response(
        prompt="same prompt",
        system_instruction="Return JSON",
        response_model=dict,
        task_type="analysis",
        allow_moa=False,
        route_trace_id=None,
    ))
    assert result is not None
    assert calls["count"] == 1

    with host.Session() as db:
        pending = db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT,
            TokenUsage.attempt_id.isnot(None),
        ).one()
        assert pending.billed is False
        assert pending.pricing_status == "unknown"
        assert pending.cost_usd is None
        assert pending.reservation_status == "active"
        assert pending.reserved_cost_usd and pending.reserved_cost_usd > 0
        assert pending.attempt_id
        attempt_id = pending.attempt_id
        reserved_bound = float(pending.reserved_cost_usd)

    with host.Session() as db:
        committed = SpendAggregationService(db).update_tenant_spend(
            TENANT, persist=False, include_liabilities=True)
    assert committed["committed_spend_usd"] == pytest.approx(
        90.0 + reserved_bound, abs=1e-6)

    # The active reservation is a real liability: a new 7-ish dispatch must
    # refuse before provider dispatch even though the simple spend read is
    # still below the cap.
    with pytest.raises(BudgetReservationRefused):
        begin_llm_usage(
            provider_id="openai", model_name="gpt-4o-mini",
            agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
            request_id="restart-new", attempt_id="restart-new",
            reserved_cost_usd=reserved_bound, enforce_budget=True)

    # Simulate a process restart: clear process-local markers and read the
    # SAME scratch DB through a fresh engine/session. The durable active
    # reservation must still be present and still refuse a new reservation.
    spend_module.clear_settlement_failure()
    repair._clear_token_usage_upgrade_failure()
    engine = create_engine(str(host.engine.url))
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        pending = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == attempt_id).one()
        assert pending.billed is False
        assert pending.pricing_status == "unknown"
        assert pending.cost_usd is None
        assert pending.reservation_status == "active"
        assert float(pending.reserved_cost_usd) == pytest.approx(
            reserved_bound)
        assert db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "restart-new").count() == 0
    with pytest.raises(BudgetReservationRefused):
        begin_llm_usage(
            provider_id="openai", model_name="gpt-4o-mini",
            agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
            request_id="restart-new-2", attempt_id="restart-new-2",
            reserved_cost_usd=reserved_bound, enforce_budget=True)
    engine.dispose()


def test_no_provider_dispatch_when_durable_intent_cannot_persist(
        host, monkeypatch, caplog):
    _seed(host, spend=90.0)
    handler, calls = _structured_handler(monkeypatch)
    from core import spend_aggregation_service as spend_module

    def _intent_down(*args, **kwargs):
        raise RuntimeError("intent store unavailable")

    monkeypatch.setattr(spend_module, "begin_llm_usage", _intent_down)
    caplog.set_level(logging.ERROR)
    result = asyncio.run(asyncio.wait_for(
        handler.generate_structured_response(
            prompt="same prompt",
            system_instruction="Return JSON",
            response_model=dict,
            task_type="analysis",
            allow_moa=False,
            route_trace_id=None,
        ),
        timeout=10.0,
    ))
    assert result is None
    assert calls["count"] == 0
    refusals = [
        r for r in caplog.records
        if "refusing structured dispatch" in r.getMessage()
    ]
    assert 1 <= len(refusals) <= 2
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT,
            TokenUsage.attempt_id.isnot(None),
        ).count() == 0


def test_settle_exact_intent_once(host, monkeypatch):
    _seed(host, spend=0.0)
    from core import spend_aggregation_service as spend_module

    monkeypatch.setattr(
        spend_module, "_SETTLEMENT_FAILURE_REASON", None)
    begin_id = begin_llm_usage(
        provider_id="openai", model_name="gpt-4o-mini",
        agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
        request_id="intent-request", attempt_id="intent-1")
    settled_id = record_llm_usage(
        provider_id="openai", model_name="gpt-4o-mini",
        prompt_tokens=100, completion_tokens=0, cost_usd=7.0,
        agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
        request_id="intent-request", attempt_id="intent-1")
    assert settled_id == begin_id
    replay_id = record_llm_usage(
        provider_id="openai", model_name="gpt-4o-mini",
        prompt_tokens=100, completion_tokens=0, cost_usd=7.0,
        agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
        request_id="intent-request", attempt_id="intent-1")
    assert replay_id == begin_id
    with host.Session() as db:
        rows = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "intent-1").all()
        assert len(rows) == 1
        assert rows[0].billed is True
        assert rows[0].cost_usd == pytest.approx(7.0)
        assert rows[0].pricing_status == "priced"
    with pytest.raises(ValueError):
        record_llm_usage(
            provider_id="openai", model_name="gpt-4o-mini",
            prompt_tokens=1, completion_tokens=0, cost_usd=9.0,
            agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
            request_id="intent-request", attempt_id="intent-1")
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "intent-1").count() == 1


def test_pending_cas_two_sessions_actual_survives_stale_writers(
        host, monkeypatch):
    """Two sessions read the same pending intent; the first actual settlement
    wins and later stale actual/unknown writers cannot overwrite it."""
    _seed(host, spend=0.0)
    from core import spend_aggregation_service as spend_module

    monkeypatch.setattr(
        spend_module, "_SETTLEMENT_FAILURE_REASON", None)
    begin_llm_usage(
        provider_id="openai", model_name="gpt-4o-mini",
        agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
        request_id="cas-req", attempt_id="cas-1")
    SessionA = host.Session()
    SessionB = host.Session()
    SessionC = host.Session()
    try:
        a = SessionA.query(TokenUsage).filter(
            TokenUsage.attempt_id == "cas-1").one()
        b = SessionB.query(TokenUsage).filter(
            TokenUsage.attempt_id == "cas-1").one()
        c = SessionC.query(TokenUsage).filter(
            TokenUsage.attempt_id == "cas-1").one()

        common = dict(
            provider_id="openai", model_name="gpt-4o-mini",
            prompt_tokens=100, completion_tokens=0,
            agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
            execution_id=None, chain_id=None, request_id="cas-req")

        settled = spend_module._settle_pending_intent(
            SessionA, existing=a, cost_usd=7.0, **common)
        assert settled == a.id

        with pytest.raises(ValueError):
            spend_module._settle_pending_intent(
                SessionB, existing=b, cost_usd=9.0, **common)
        with host.Session() as db:
            row = db.query(TokenUsage).filter(
                TokenUsage.attempt_id == "cas-1").one()
            assert row.cost_usd == pytest.approx(7.0)
            assert row.pricing_status == "priced"

        # Exact duplicate replay of the winning material is idempotent.
        assert spend_module._settle_pending_intent(
            SessionB, existing=b, cost_usd=7.0, **common) == a.id

        # A stale unknown writer must not downgrade the actual settlement.
        with pytest.raises(ValueError):
            spend_module._settle_pending_intent(
                SessionB, existing=b, cost_usd=None, **common)
        with host.Session() as db:
            row = db.query(TokenUsage).filter(
                TokenUsage.attempt_id == "cas-1").one()
            assert row.cost_usd == pytest.approx(7.0)
            assert row.pricing_status == "priced"

        # A scope contradiction is refused and leaves the row unchanged.
        with pytest.raises(ValueError):
            spend_module._settle_pending_intent(
                SessionC, existing=c, cost_usd=7.0,
                **{**common, "tenant_id": "other-tenant"})
        with host.Session() as db:
            row = db.query(TokenUsage).filter(
                TokenUsage.attempt_id == "cas-1").one()
            assert row.tenant_id == TENANT
            assert row.cost_usd == pytest.approx(7.0)
    finally:
        SessionA.close()
        SessionB.close()
        SessionC.close()


def test_null_cost_nonunknown_status_is_liability_not_free(host):
    _seed(host, spend=90.0)
    with host.Session() as db:
        db.add(TokenUsage(
            agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
            model_name="controlled", cost_usd=None,
            pricing_status="priced", attempt_id="null-priced"))
        db.commit()
    assert _unpriced(host) == 1
    refused = _admit(host)
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_UNPRICED_USAGE"


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
