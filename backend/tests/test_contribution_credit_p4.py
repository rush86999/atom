"""P4 — Marginal-contribution credit (AGENT_ORG_POLITICS_PLAN.md Phase 4).

R10 (bucket-brigade backward value flow): on fleet completion, each
specialist's graduation credit reflects its marginal contribution along the
delegation chain, not uniform presence. Deterministic — outcome deltas from
ChainLink statuses (verified-gated), no LLM judging.

Model:
- step value v ∈ {1.0 completed, 0.5 pending/unknown, 0.0 failed}
- raw score r_i = v_i * γ^(n-1-i)  (γ=0.7; downstream steps weigh more)
- realized chain outcome V_eff = v_last floored at 0.25 (a late failure
  dampens but does not zero upstream positive contributions)
- weights normalized so Σw = V_eff → "weights sum ≈ outcome delta"

Mapping to graduation (one-shot supplement; per-tool records stay
authoritative and failures are never double-counted):
  w ≥ 0.5        → record_usage(success=True,  verified="verified")
  0 < w < 0.5    → record_usage(success=True,  verified="unverified")
  w == 0         → skipped

Flag: ATOM_CONTRIBUTION_CREDIT_ENABLED (default OFF).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


# ============================================================================
# Pure math
# ============================================================================


class TestComputeChainCredit:
    def test_all_success_sums_to_outcome_last_gets_most(self):
        from core.contribution_credit import compute_chain_credit

        steps = [
            {"agent_id": "s1", "status": "completed"},
            {"agent_id": "s2", "status": "completed"},
            {"agent_id": "s3", "status": "completed"},
        ]
        w = compute_chain_credit(steps)
        assert pytest.approx(sum(w.values()), abs=1e-6) == 1.0
        assert w["s3"] > w["s2"] > w["s1"] > 0

    def test_failed_step_gets_zero_upstream_survives(self):
        from core.contribution_credit import compute_chain_credit

        steps = [
            {"agent_id": "s1", "status": "completed"},
            {"agent_id": "s2", "status": "failed"},
            {"agent_id": "s3", "status": "completed"},
        ]
        w = compute_chain_credit(steps)
        assert w["s2"] == 0.0
        assert w["s1"] > 0 and w["s3"] > 0
        assert pytest.approx(sum(w.values()), abs=1e-6) == 1.0

    def test_late_failure_dampens_but_does_not_zero(self):
        from core.contribution_credit import DAMPENED_OUTCOME, compute_chain_credit

        steps = [
            {"agent_id": "s1", "status": "completed"},
            {"agent_id": "s2", "status": "completed"},
            {"agent_id": "s3", "status": "failed"},
        ]
        w = compute_chain_credit(steps)
        assert pytest.approx(sum(w.values()), abs=1e-6) == DAMPENED_OUTCOME
        assert all(v >= 0 for v in w.values())

    def test_unknown_status_counts_half(self):
        from core.contribution_credit import compute_chain_credit

        steps = [
            {"agent_id": "s1", "status": "pending"},
            {"agent_id": "s2", "status": "completed"},
        ]
        w = compute_chain_credit(steps)
        assert w["s1"] > 0  # unknown ≠ failure
        assert w["s2"] > w["s1"]

    def test_empty_and_single(self):
        from core.contribution_credit import compute_chain_credit

        assert compute_chain_credit([]) == {}
        single = compute_chain_credit([{"agent_id": "x", "status": "completed"}])
        assert single == {"x": 1.0}

    def test_duplicate_agents_aggregate(self):
        from core.contribution_credit import compute_chain_credit

        steps = [
            {"agent_id": "s1", "status": "completed"},
            {"agent_id": "s1", "status": "completed"},
        ]
        w = compute_chain_credit(steps)
        assert set(w) == {"s1"}
        assert pytest.approx(w["s1"], abs=1e-6) == 1.0


# ============================================================================
# Graduation mapping
# ============================================================================


class TestApplyCredit:
    @pytest.fixture
    def grad_db(self):
        from core.models import AgentRegistry

        engine = sa.create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=sa.pool.StaticPool,
        )
        AgentRegistry.__table__.create(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(
            AgentRegistry(
                id="ag-a",
                name="A",
                category="Ops",
                role="agent",
                type="personal",
                module_path="m",
                class_name="C",
            )
        )
        session.commit()
        yield session
        session.close()

    def test_strong_credit_records_verified_success(self, grad_db):
        from core.contribution_credit import apply_credit
        from core.models import AgentRegistry

        applied = apply_credit(
            grad_db,
            [{"agent_id": "ag-a", "weight": 0.8, "domain": "finance"}],
        )
        assert applied == 1
        row = grad_db.query(AgentRegistry).filter_by(id="ag-a").first()
        stats = row.configuration["capability_stats"]["finance"]
        assert stats["verified_success"] == 1

    def test_moderate_credit_records_unverified_only(self, grad_db):
        from core.contribution_credit import apply_credit
        from core.models import AgentRegistry

        apply_credit(
            grad_db,
            [{"agent_id": "ag-a", "weight": 0.3, "domain": "finance"}],
        )
        row = grad_db.query(AgentRegistry).filter_by(id="ag-a").first()
        stats = row.configuration["capability_stats"]["finance"]
        assert stats["success"] == 1
        assert stats["verified_success"] == 0  # cannot inflate graduation

    def test_zero_weight_skipped_no_poison(self, grad_db):
        from core.contribution_credit import apply_credit
        from core.models import AgentRegistry

        applied = apply_credit(
            grad_db,
            [{"agent_id": "ag-a", "weight": 0.0, "domain": "finance"}],
        )
        assert applied == 0
        row = grad_db.query(AgentRegistry).filter_by(id="ag-a").first()
        assert "capability_stats" not in (row.configuration or {})


# ============================================================================
# Orchestration: execution_id → chain links → credits
# ============================================================================


@pytest.fixture
def chain_db():
    from core.models import (
        AgentRegistry,
        ChainLink,
        DelegationChain,
        FleetRoutingAudit,
    )

    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    for m in (AgentRegistry, DelegationChain, ChainLink, FleetRoutingAudit):
        m.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed_fleet(db, *, link_statuses):
    from core.models import (
        AgentRegistry,
        ChainLink,
        DelegationChain,
        FleetRoutingAudit,
    )

    db.add(
        DelegationChain(
            id="chain-1",
            root_task="goal",
            tenant_id="t1",
            root_agent_id="atom_main",
        )
    )
    for i, aid in enumerate(["ag-x", "ag-y", "ag-z"]):
        db.add(
            AgentRegistry(
                id=aid,
                name=aid,
                category="Ops",
                role="agent",
                type="personal",
                module_path="m",
                class_name="C",
            )
        )
    for i, status in enumerate(link_statuses):
        db.add(
            ChainLink(
                chain_id="chain-1",
                parent_agent_id="atom_main",
                child_agent_id=["ag-x", "ag-y", "ag-z"][i],
                task_description=f"t{i}",
                context_json={"domain": "finance"},
                status=status,
                link_order=i,
            )
        )
    db.add(
        FleetRoutingAudit(
            workload_key="wk",
            execution_id="exec-9",
            chain_id="chain-1",
            specialists_count=len(link_statuses),
            roster_json=[
                {"agent_id": a}
                for a in ["ag-x", "ag-y", "ag-z"]
            ],
        )
    )
    db.commit()


class TestRecordChainCredit:
    def test_flag_off_noop(self, chain_db, monkeypatch):
        monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "false")
        _seed_fleet(chain_db, link_statuses=["completed"] * 3)
        from core.contribution_credit import record_chain_credit

        assert record_chain_credit("exec-9", db=chain_db) is False

    def test_happy_path_applies_credits(self, chain_db, monkeypatch):
        monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
        _seed_fleet(chain_db, link_statuses=["completed", "completed", "completed"])
        from core.contribution_credit import record_chain_credit
        from core.models import AgentRegistry

        assert record_chain_credit("exec-9", db=chain_db) is True
        for aid in ("ag-x", "ag-y", "ag-z"):
            row = chain_db.query(AgentRegistry).filter_by(id=aid).first()
            assert "finance" in (row.configuration or {}).get("capability_stats", {})

    def test_missing_execution_is_noop_never_raises(self, chain_db, monkeypatch):
        monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
        from core.contribution_credit import record_chain_credit

        assert record_chain_credit("no-such-exec", db=chain_db) is False


class TestFinalizeWireIn:
    def test_record_fleet_execution_outcome_calls_credit(self, monkeypatch):
        import inspect

        from core.fleet_orchestration import fleet_routing_stats

        src = inspect.getsource(fleet_routing_stats.record_fleet_execution_outcome)
        assert "record_chain_credit" in src
