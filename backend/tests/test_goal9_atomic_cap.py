"""Goal 9 atomic hard-stop admission/reservation controls.

Scratch SQLite + real ledger/transaction only. The reservation is a
``TokenUsage`` row written before provider dispatch; the INSERT/flush is the
SQLite serialization point (Postgres uses ``Tenant ... FOR UPDATE``). Actual
settlement reconciles that exact row once. No second budget store/router.
"""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from types import SimpleNamespace

from tests.test_oracle_mini_app_host_mutations import USER, host
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, Tenant, TenantSetting, TokenUsage, User, Workspace
from core.spend_aggregation_service import (
    BudgetReservationRefused,
    SpendAggregationService,
    begin_llm_usage,
    clear_settlement_failure,
    record_llm_usage,
)

TENANT = "tenant-goal9-atomic"
WORKSPACE = "ws-goal9-atomic"
AGENT = "agent-goal9-atomic"
TENANT_B = "tenant-goal9-atomic-b"
WORKSPACE_B = "ws-goal9-atomic-b"
AGENT_B = "agent-goal9-atomic-b"


@pytest.fixture(autouse=True)
def _clear_process_markers():
    from core import sqlite_schema_repair as repair
    clear_settlement_failure()
    repair._clear_token_usage_upgrade_failure()
    yield
    clear_settlement_failure()
    repair._clear_token_usage_upgrade_failure()


def _seed_scope(host, tenant, workspace, agent, *, spend=0.0, limit=100.0,
                mode="hard_stop"):
    with host.Session() as db:
        if db.query(Tenant).filter(Tenant.id == tenant).first() is None:
            db.add(Tenant(id=tenant, name=tenant, subdomain=tenant))
            db.add(Workspace(id=workspace, name=workspace, tenant_id=tenant))
            db.add(AgentRegistry(
                id=agent, name=agent, category="Operations",
                module_path="core.generic_agent", class_name="GenericAgent",
                user_id=USER, workspace_id=workspace, tenant_id=tenant,
                status="autonomous", confidence_score=0.99))
            db.add(TenantSetting(
                tenant_id=tenant, setting_key="billing",
                setting_value=json.dumps({
                    "budget_limit_usd": limit,
                    "enforcement": {"mode": mode},
                })))
        if spend:
            db.add(TokenUsage(
                agent_id=agent, workspace_id=workspace, tenant_id=tenant,
                model_name="controlled-no-provider", cost_usd=spend,
                pricing_status="priced", reservation_status="none",
                timestamp=datetime.now()))
        db.commit()


def _seed(host, *, spend=90.0, limit=100.0, mode="hard_stop"):
    _seed_scope(host, TENANT, WORKSPACE, AGENT,
                spend=spend, limit=limit, mode=mode)
    _seed_scope(host, TENANT_B, WORKSPACE_B, AGENT_B,
                spend=0.0, limit=limit, mode=mode)


def _set_billing(host, value, *, tenant=TENANT):
    with host.Session() as db:
        row = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant).first()
        raw = value if isinstance(value, str) else json.dumps(value)
        if row is None:
            db.add(TenantSetting(
                tenant_id=tenant, setting_key="billing",
                setting_value=raw))
        else:
            row.setting_value = raw
        db.commit()


def _reserve(attempt_id, bound, *, tenant=TENANT, workspace=WORKSPACE,
             agent=AGENT, provider="openai", model="gpt-4o-mini"):
    return begin_llm_usage(
        provider_id=provider, model_name=model,
        agent_id=agent, workspace_id=workspace, tenant_id=tenant,
        request_id=attempt_id, attempt_id=attempt_id,
        reserved_cost_usd=bound, enforce_budget=True)


def _settle(attempt_id, cost, *, tenant=TENANT, workspace=WORKSPACE,
            agent=AGENT, provider="openai", model="gpt-4o-mini",
            prompt_tokens=100, completion_tokens=0):
    return record_llm_usage(
        provider_id=provider, model_name=model,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        cost_usd=cost, agent_id=agent, workspace_id=workspace,
        tenant_id=tenant, request_id=attempt_id, attempt_id=attempt_id)


def _spend(host, tenant=TENANT):
    with host.Session() as db:
        return SpendAggregationService(db).update_tenant_spend(
            tenant, persist=False, include_liabilities=True)


def _admit(host, tenant=TENANT, workspace=WORKSPACE, agent=AGENT):
    with host.Session() as db:
        return asyncio.run(AgentGovernanceService(
            db, workspace_id=workspace, tenant_id=tenant,
        ).can_perform_action_async(agent, "llm_react_step"))


def test_concurrent_two_seven_reservations_one_refuses(host):
    _seed(host, spend=90.0)
    barrier = threading.Barrier(2)
    results = []

    def _run(attempt_id):
        barrier.wait(timeout=10)
        try:
            _reserve(attempt_id, 7.0)
            results.append(("ok", attempt_id))
        except BudgetReservationRefused as exc:
            results.append(("refused", exc.status_code))
        except Exception as exc:  # pragma: no cover - diagnostic
            results.append(("error", type(exc).__name__, str(exc)))

    threads = [threading.Thread(target=_run, args=(f"concurrent-{i}",))
               for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert [t.is_alive() for t in threads] == [False, False]

    oks = [r for r in results if r[0] == "ok"]
    refused = [r for r in results if r[0] == "refused"]
    assert len(oks) == 1, results
    assert len(refused) == 1, results
    assert refused[0][1] == "BUDGET_EXCEEDED"
    spend = _spend(host)
    assert spend["current_spend_usd"] == pytest.approx(90.0)
    assert spend["reserved_spend_usd"] == pytest.approx(7.0)
    assert spend["committed_spend_usd"] == pytest.approx(97.0)
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT,
            TokenUsage.reservation_status == "active").count() == 1


def test_single_reservation_settles_actual_7_to_97(host):
    _seed(host, spend=90.0)
    _reserve("single-1", 7.0)
    _settle("single-1", 7.0)
    spend = _spend(host)
    assert spend["current_spend_usd"] == pytest.approx(97.0)
    assert spend["reserved_spend_usd"] == pytest.approx(0.0)
    assert spend["committed_spend_usd"] == pytest.approx(97.0)
    assert _admit(host)["allowed"] is True


def test_second_reservation_after_97_refuses(host):
    _seed(host, spend=90.0)
    _reserve("second-1", 7.0)
    _settle("second-1", 7.0)
    with pytest.raises(BudgetReservationRefused) as exc:
        _reserve("second-2", 7.0)
    assert exc.value.status_code == "BUDGET_EXCEEDED"
    assert _spend(host)["committed_spend_usd"] == pytest.approx(97.0)


def test_actual_less_than_reservation_releases_difference(host):
    _seed(host, spend=90.0)
    _reserve("release-1", 7.0)
    _settle("release-1", 3.0)
    assert _spend(host)["committed_spend_usd"] == pytest.approx(93.0)
    _reserve("release-2", 7.0)
    assert _spend(host)["committed_spend_usd"] == pytest.approx(100.0)
    with pytest.raises(BudgetReservationRefused):
        _reserve("release-3", 0.01)


def test_scope_isolation_between_tenants(host):
    _seed(host, spend=90.0)
    _reserve("scope-a", 7.0)
    assert _spend(host, TENANT)["committed_spend_usd"] == pytest.approx(97.0)
    assert _spend(host, TENANT_B)["committed_spend_usd"] == pytest.approx(0.0)
    _reserve("scope-b", 7.0, tenant=TENANT_B,
             workspace=WORKSPACE_B, agent=AGENT_B)
    assert _spend(host, TENANT_B)["committed_spend_usd"] == pytest.approx(7.0)
    assert _spend(host, TENANT)["committed_spend_usd"] == pytest.approx(97.0)


def test_duplicate_reservation_idempotent_and_binding_conflict(host):
    _seed(host, spend=90.0)
    first = _reserve("dup-reserve", 7.0)
    second = _reserve("dup-reserve", 7.0)
    assert first == second
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "dup-reserve").count() == 1
    with pytest.raises(Exception):
        _reserve("dup-reserve", 7.0, tenant=TENANT_B,
                 workspace=WORKSPACE_B, agent=AGENT_B)
    with pytest.raises(Exception):
        begin_llm_usage(
            provider_id="openai", model_name="gpt-4o-mini",
            agent_id=AGENT, workspace_id=WORKSPACE, tenant_id=TENANT,
            execution_id="different-execution", request_id="dup-reserve",
            attempt_id="dup-reserve", reserved_cost_usd=7.0,
            enforce_budget=True)


def test_restart_active_reservation_blocks_new_reservation(host):
    _seed(host, spend=90.0)
    _reserve("restart-atomic", 7.0)
    engine = create_engine(str(host.engine.url))
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "restart-atomic").one()
        assert row.reservation_status == "active"
        assert float(row.reserved_cost_usd) == pytest.approx(7.0)
    engine.dispose()
    with pytest.raises(BudgetReservationRefused):
        _reserve("restart-atomic-2", 7.0)


def test_reservation_write_failure_refuses_provider_dispatch(host, monkeypatch):
    _seed(host, spend=90.0)
    from tests.test_goal9_durable_settlement import _structured_handler

    handler, calls = _structured_handler(monkeypatch)
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT

    def _db_down():
        raise RuntimeError("reservation store unavailable")

    monkeypatch.setattr("core.database.SessionLocal", _db_down)
    result = asyncio.run(handler.generate_structured_response(
        prompt="same prompt",
        system_instruction="Return JSON",
        response_model=dict,
        task_type="analysis",
        allow_moa=False,
        route_trace_id=None,
    ))
    assert result is None
    assert calls["count"] == 0
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT,
            TokenUsage.attempt_id.isnot(None)).count() == 0


def test_known_free_zero_reservation_allowed(host):
    _seed(host, spend=90.0)
    _reserve("free-atomic", 0.0)
    _settle("free-atomic", 0.0)
    spend = _spend(host)
    assert spend["committed_spend_usd"] == pytest.approx(90.0)
    assert spend["unpriced_usage_rows"] == 0
    assert _admit(host)["allowed"] is True


def test_unknown_pricing_hard_stop_refuses_soft_stop_allows(host):
    _seed(host, spend=90.0)
    with pytest.raises(BudgetReservationRefused) as exc:
        _reserve("unknown-price", None)
    assert exc.value.status_code == "BUDGET_UNPRICED_USAGE"
    with host.Session() as db:
        setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == TENANT).one()
        setting.setting_value = json.dumps({
            "budget_limit_usd": 100.0,
            "enforcement": {"mode": "alert_only"},
        })
        db.commit()
    _reserve("unknown-price-soft", None)
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "unknown-price-soft").one()
        assert row.reservation_status == "active"
        assert row.reserved_cost_usd is None


def test_timeout_uncertain_reservation_is_retained(host):
    _seed(host, spend=90.0)
    _reserve("timeout-1", 7.0)
    # No settlement / no release: the reservation is the retained liability.
    assert _spend(host)["committed_spend_usd"] == pytest.approx(97.0)
    with pytest.raises(BudgetReservationRefused):
        _reserve("timeout-2", 7.0)
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "timeout-1").one()
        assert row.reservation_status == "active"
        assert float(row.reserved_cost_usd) == pytest.approx(7.0)
        assert row.cost_usd is None


def test_exact_attempt_settles_once_and_conflict_refused(host, monkeypatch):
    _seed(host, spend=90.0)
    from core import spend_aggregation_service as spend_module

    monkeypatch.setattr(spend_module, "_SETTLEMENT_FAILURE_REASON", None)
    intent_id = _reserve("exact-1", 7.0)
    settled_id = _settle("exact-1", 7.0)
    assert settled_id == intent_id
    assert _settle("exact-1", 7.0) == intent_id
    with pytest.raises(ValueError):
        _settle("exact-1", 9.0)
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "exact-1").count() == 1
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "exact-1").one()
        assert row.cost_usd == pytest.approx(7.0)
        assert row.reservation_status == "settled"
        assert row.reserved_cost_usd == pytest.approx(0.0)


def test_concurrent_structured_only_one_provider_call(host, monkeypatch):
    """Two real structured consumers race; only the reservation winner
    reaches the doubled provider. The loser is refused before dispatch."""
    _seed(host, spend=90.0)
    from tests.test_goal9_durable_settlement import _structured_handler

    monkeypatch.setenv("ATOM_LLM_RESERVATION_MARGIN", "1.0")
    handler, calls = _structured_handler(monkeypatch)
    # The shared durable-test helper defaults to its own scope; bind this
    # production consumer to the atomic scratch tenant that has the cap.
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT
    barrier = threading.Barrier(2)
    results = []

    def _run():
        barrier.wait(timeout=10)
        try:
            result = asyncio.run(handler.generate_structured_response(
                prompt="same prompt",
                system_instruction="Return JSON",
                response_model=dict,
                task_type="analysis",
                allow_moa=False,
                route_trace_id=None,
            ))
            results.append(("returned", result is not None))
        except Exception as exc:  # pragma: no cover - diagnostic
            results.append(("raised", type(exc).__name__))

    threads = [threading.Thread(target=_run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=25)
    assert [t.is_alive() for t in threads] == [False, False]
    assert calls["count"] == 1, results
    assert sum(1 for r in results if r[0] == "returned" and r[1]) == 1
    spend = _spend(host)
    assert spend["current_spend_usd"] == pytest.approx(97.0)
    assert spend["committed_spend_usd"] <= 100.0 + 1e-6


def test_invalid_or_unreadable_policy_fails_closed(host):
    _seed(host, spend=90.0)
    cases = [
        "{not-json",
        {"budget_limit_usd": -1, "enforcement": {"mode": "hard_stop"}},
        {"budget_limit_usd": float("nan"),
         "enforcement": {"mode": "hard_stop"}},
        {"budget_limit_usd": float("inf"),
         "enforcement": {"mode": "hard_stop"}},
        {"budget_limit_usd": 100, "enforcement": {"mode": "not-a-mode"}},
        {"budget_limit_usd": "not-a-number",
         "enforcement": {"mode": "hard_stop"}},
    ]
    for index, value in enumerate(cases):
        _set_billing(host, value)
        with pytest.raises(BudgetReservationRefused) as exc:
            _reserve(f"bad-policy-{index}", 7.0)
        assert exc.value.status_code == "BUDGET_STATUS_UNAVAILABLE", value
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT,
            TokenUsage.reservation_status == "active").count() == 0


def test_database_read_failure_fails_closed(host, monkeypatch):
    _seed(host, spend=90.0)

    def _broken_spend(*args, **kwargs):
        return {"error": "spend read failed"}

    monkeypatch.setattr(
        SpendAggregationService, "get_total_spend", _broken_spend)
    with pytest.raises(BudgetReservationRefused) as exc:
        _reserve("db-read-fail", 7.0)
    assert exc.value.status_code == "BUDGET_STATUS_UNAVAILABLE"
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.tenant_id == TENANT,
            TokenUsage.reservation_status == "active").count() == 0


def test_unresolved_scope_reservation_remains_unattributed_liability(host):
    _seed(host, spend=90.0)
    begin_llm_usage(
        provider_id="openai", model_name="gpt-4o-mini",
        agent_id=None, workspace_id=None, tenant_id=None,
        request_id="tenantless-reserve", attempt_id="tenantless-reserve",
        reserved_cost_usd=7.0, enforce_budget=True)
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "tenantless-reserve").one()
        assert row.tenant_id is None
        assert row.reservation_status == "active"
        assert float(row.reserved_cost_usd) == pytest.approx(7.0)
    refused = _admit(host)
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_UNATTRIBUTED_USAGE"


def test_no_limit_or_observe_policy_is_not_blanket_denied(host):
    _seed(host, spend=0.0)
    # Remove the configured policy entirely: intended no-limit default.
    with host.Session() as db:
        row = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == TENANT_B).one()
        db.delete(row)
        db.commit()
    _reserve("no-limit", 7.0, tenant=TENANT_B,
             workspace=WORKSPACE_B, agent=AGENT_B)
    # Explicit observe mode with a valid cap still reserves without a hard
    # stop refusal.
    _set_billing(host, {
        "budget_limit_usd": 100,
        "enforcement": {"mode": "alert_only"},
    }, tenant=TENANT_B)
    _reserve("observe", 7.0, tenant=TENANT_B,
             workspace=WORKSPACE_B, agent=AGENT_B)
    assert _spend(host, TENANT_B)["reserved_spend_usd"] == pytest.approx(14.0)


def test_budget_revision_after_reservation_keeps_liability(host):
    _seed(host, spend=90.0)
    _reserve("revision-1", 7.0)
    _set_billing(host, {
        "budget_limit_usd": 50,
        "enforcement": {"mode": "hard_stop"},
    })
    assert _spend(host)["committed_spend_usd"] == pytest.approx(97.0)
    with pytest.raises(BudgetReservationRefused):
        _reserve("revision-2", 7.0)
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "revision-1").one().reservation_status == (
                "active")


@pytest.mark.parametrize("estimated", [False, True])
def test_reservation_bound_covers_unicode_schema_and_output(
        host, monkeypatch, estimated):
    from core.llm import byok_handler, prompt_budget

    recorded = {}

    class _Pricing:
        def estimate_cost(self, model, input_tokens, output_tokens):
            recorded["model"] = model
            recorded["input_tokens"] = input_tokens
            recorded["output_tokens"] = output_tokens
            return 1.0

    monkeypatch.setattr(
        byok_handler, "get_pricing_fetcher", lambda: _Pricing())
    # count_tokens returns (count, estimated). Both the real-tokenizer and
    # heuristic flags must retain the model-independent UTF-8 text bound.
    monkeypatch.setattr(
        prompt_budget, "count_tokens",
        lambda text: (max(1, len(str(text or "")) // 4), estimated))
    handler = object.__new__(byok_handler.BYOKHandler)
    bound = handler._estimate_reservation_bound(
        "openai", "gpt-4o-mini",
        ["é" * 10, "hello"], 100,
        schema_text='{"type":"object"}')
    assert bound == pytest.approx(1.25)
    expected_min = (
        len(("é" * 10).encode("utf-8"))
        + len("hello".encode("utf-8"))
        + len('{"type":"object"}'.encode("utf-8"))
        + 256 + 16)
    assert recorded["input_tokens"] >= expected_min
    assert recorded["output_tokens"] == 100


def test_route_binding_conflict_refused(host):
    _seed(host, spend=90.0)
    _reserve("route-1", 7.0, provider="openai", model="gpt-4o-mini")
    with pytest.raises(Exception):
        _settle("route-1", 7.0, provider="other", model="other-model")
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "route-1").one()
        assert row.reservation_status == "active"
        assert row.provider_id == "openai"
        assert row.model_name == "gpt-4o-mini"


def test_reservation_does_not_commit_caller_work(host):
    _seed(host, spend=90.0)
    caller = host.Session()
    try:
        user = caller.get(User, USER)
        old_name = user.first_name
        user.first_name = "caller-pending"
        # Pending edit in the caller's identity map only: no SQLite write
        # lock is held, so the separate reservation session can proceed.
        _reserve("caller-tx", 7.0)
        with host.Session() as observer:
            assert observer.get(User, USER).first_name == old_name
    finally:
        caller.rollback()
        caller.close()


def test_default_scope_without_tenant_is_intentional_no_limit(host):
    _seed(host, spend=0.0)
    begin_llm_usage(
        provider_id="openai", model_name="gpt-4o-mini",
        agent_id=None, workspace_id="default", tenant_id="default",
        request_id="default-scope", attempt_id="default-scope",
        reserved_cost_usd=7.0, enforce_budget=True)
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "default-scope").one()
        assert row.tenant_id == "default"
        assert row.reservation_status == "active"
        assert float(row.reserved_cost_usd) == pytest.approx(7.0)


def test_supported_upgrade_adds_reservation_columns_preserving_old_rows(
        tmp_path, monkeypatch):
    from tests.test_goal9_token_usage_upgrade import (
        _old_schema, _run_supported_startup_upgrade,
    )
    from core import sqlite_schema_repair as repair

    engine = create_engine(f"sqlite:///{tmp_path / 'atomic-upgrade.db'}")
    _old_schema(engine)
    _run_supported_startup_upgrade(engine, monkeypatch)
    cols = {c["name"]: c for c in inspect(engine).get_columns("token_usage")}
    assert "reserved_cost_usd" in cols
    assert "reservation_status" in cols
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, reservation_status, reserved_cost_usd "
            "FROM token_usage ORDER BY id")).fetchall()
        assert rows == [
            ("old-1", "none", 0.0),
            ("old-2", "none", 0.0),
        ]
        fks = {r[2] for r in conn.exec_driver_sql(
            "PRAGMA foreign_key_list('token_usage')").fetchall()}
        assert {"agent_registry", "workspaces", "agent_executions",
                "delegation_chains"}.issubset(fks)
    repair._REPAIRED.clear()
    repair.repair_known_drift()
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT COUNT(*) FROM token_usage")).scalar() == 2
    engine.dispose()


@pytest.mark.parametrize("price", [-1.0, float("nan"), float("inf"), False, True])
def test_invalid_pricing_is_unknown_not_free(monkeypatch, price):
    from core.llm import byok_handler

    monkeypatch.setattr(
        byok_handler, "get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=lambda *a, **k: price))
    handler = object.__new__(byok_handler.BYOKHandler)
    assert handler._estimate_reservation_bound(
        "controlled-paid", "controlled-model", ["A"], 10) is None


@pytest.mark.parametrize("bound", [-1.0, float("nan"), float("inf"), False, True])
def test_begin_rejects_invalid_reservation_bound(host, bound):
    _seed(host, spend=90.0)
    with pytest.raises(BudgetReservationRefused) as exc:
        _reserve("invalid-bound", bound)
    assert exc.value.status_code == "BUDGET_UNPRICED_USAGE"
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "invalid-bound").count() == 0


@pytest.mark.parametrize("cost", [-1.0, float("nan"), float("inf"), False, True])
def test_invalid_settlement_cost_remains_unknown(host, cost):
    _seed(host, spend=0.0)
    _reserve("invalid-cost", 7.0)
    _settle("invalid-cost", cost)
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == "invalid-cost").one()
        assert row.billed is True
        assert row.cost_usd is None
        assert row.pricing_status == "unknown"
        assert row.reservation_status == "uncertain"
        assert float(row.reserved_cost_usd) == pytest.approx(7.0)


@pytest.mark.parametrize("price,expected", [
    (0, 0.0), (0.0, 0.0), (0.25, 0.3125),
])
def test_numeric_zero_and_positive_prices_remain_valid(
        monkeypatch, price, expected):
    from core.llm import byok_handler

    monkeypatch.setattr(
        byok_handler, "get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=lambda *a, **k: price))
    monkeypatch.setenv("ATOM_LLM_RESERVATION_MARGIN", "1.25")
    handler = object.__new__(byok_handler.BYOKHandler)
    assert handler._estimate_reservation_bound(
        "controlled-paid", "controlled-model", ["A"], 10
    ) == pytest.approx(expected)


def test_numeric_zero_direct_bounds_remain_valid(host):
    _seed(host, spend=90.0)
    for bound, attempt in ((0, "numeric-zero-int"),
                           (0.0, "numeric-zero-float")):
        _reserve(attempt, bound)
    with host.Session() as db:
        rows = db.query(TokenUsage).filter(
            TokenUsage.attempt_id.in_(
                ["numeric-zero-int", "numeric-zero-float"])).all()
        assert len(rows) == 2
        assert all(r.reservation_status == "active" for r in rows)
        assert all(float(r.reserved_cost_usd or 0.0) == 0.0 for r in rows)
