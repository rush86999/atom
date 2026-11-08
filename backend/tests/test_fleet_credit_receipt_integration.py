"""End-to-end fleet credit receipt integration (producer -> receipt -> credit).

This is the controlled positive the consumer diagnostics were missing:

* a real ``GenericAgent`` mutation runs a registered action,
* the action writes to a scratch SQLite system of record,
* a real oracle postcondition independently re-reads that database,
* ``GenericAgent`` stores the succeeded durable receipt in the existing
  ``TaskOperationRecord`` claim,
* ``FleetAdmiral``'s link carries the exact server-bound child execution id,
* ``record_chain_credit`` reads that receipt and updates the capability counter
  once, in the same transaction as its unique credit receipt.

Nothing here monkeypatches an oracle success flag, trusts a raw runner
``success``/``verified`` field, or seeds a synthetic "verified" receipt. The
legacy status-only facts remain visible, but earn zero verified success.
"""
from __future__ import annotations

import asyncio
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import core.generic_agent as ga
from core.action_registry import action_registry
from core.contribution_credit import CREDIT_RECEIPT_TYPE, record_chain_credit
from core.generic_agent import GenericAgent
from core.models import (
    AgentExecution,
    AgentRegistry,
    ChainLink,
    DelegationChain,
    FleetRoutingAudit,
    TaskOperationRecord,
    Tenant,
    Workspace,
)
from core.models_registration import Base
from core.oracle import OracleResult, register_postcondition

TENANT = "tenant-fleet"
WORKSPACE = "workspace-fleet"
ACTOR = "actor-fleet"


@pytest.fixture(autouse=True)
def _restore_oracle_verifiers():
    from core.oracle import _VERIFIERS

    snapshot = dict(_VERIFIERS)
    try:
        yield
    finally:
        _VERIFIERS.clear()
        _VERIFIERS.update(snapshot)


@pytest.fixture()
def fleet_world(tmp_path, monkeypatch):
    db_path = tmp_path / "fleet_system_of_record.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with sqlite3.connect(str(db_path)) as raw:
        raw.execute("create table effects(id text primary key, value text)")

    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session():
        session = Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    # GenericAgent's tool claim/oracle consumer must write the SAME database
    # the test's raw sqlite3 readback observes.
    monkeypatch.setattr(ga, "get_db_session", _session)

    world = SimpleNamespace(
        path=str(db_path), engine=engine, Session=Session,
        session=_session,
    )
    yield world
    engine.dispose()


def _bare_agent(leaf):
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = "ag-fleet"
    agent._custom_actions = {}
    agent.mcp = SimpleNamespace(call_tool=leaf)
    return agent


def _produce_verified_operation(world, *, child_execution_id, action_name,
                                operation_id):
    """Run the real producer consumer and leave a real succeeded claim."""
    effect_id = "effect-" + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(world.path) as raw:
            raw.execute(
                "insert into effects values (?,?)",
                (effect_id, args["value"]))
        return {
            "success": True,
            "status": "success",
            "action_result": "applied",
            "operation_id": operation_id,
        }

    async def verifier(ctx):
        row = ctx["db"].execute(
            text("select value from effects where id = :id"),
            {"id": effect_id}).fetchone()
        if row is None:
            return OracleResult(action_name, False, "effect absent")
        return OracleResult(
            action_name, row[0] == "landed",
            f"effects[{effect_id}] == {row[0]!r}")

    action_registry.register(
        action_name, leaf,
        effects=[{"effect": "create", "scope": "local"}])
    register_postcondition(action_name)(verifier)

    result = asyncio.run(_bare_agent(leaf)._step_act_unaudited(
        action_name,
        {"value": "landed"},
        context={
            "operation_id": operation_id,
            "workspace_id": WORKSPACE,
            "tenant_id": TENANT,
            "execution_id": child_execution_id,
            "user_id": ACTOR,
            "agent_id": "ag-fleet",
        },
        pre_approved=True,
    ))
    assert result.get("oracle_verified") is True, result
    assert result.get("success") is True, result
    return effect_id


def _seed_fleet(world, *, child_executions):
    """Seed the fleet/audit/child execution scope around real receipts.

    ``child_executions`` is a list of ``(child_execution_id, action_name)``.
    Each link points at exactly that child execution. The operation receipts
    themselves are produced by ``_produce_verified_operation`` above.
    """
    with world.Session() as db:
        db.add_all([
            Tenant(id=TENANT, name="Fleet Tenant", subdomain="fleet-tenant"),
            Workspace(id=WORKSPACE, name="Fleet Workspace", tenant_id=TENANT),
        ])
        db.add_all([
            AgentRegistry(
                id="atom-fleet", name="Fleet Root", category="Ops",
                role="agent", type="personal", module_path="m",
                class_name="C", tenant_id=TENANT, workspace_id=WORKSPACE),
            AgentRegistry(
                id="ag-fleet", name="Fleet Specialist", category="Finance",
                role="agent", type="personal", module_path="m",
                class_name="C", tenant_id=TENANT, workspace_id=WORKSPACE,
                capabilities=["finance"], specialty="finance"),
        ])
        db.add(DelegationChain(
            id="chain-credit", tenant_id=TENANT, root_agent_id="atom-fleet",
            root_task="fleet goal", status="completed",
            metadata_json={"workspace_id": WORKSPACE}))
        db.add(AgentExecution(
            id="parent-exec", agent_id="atom-fleet", tenant_id=TENANT,
            workspace_id=WORKSPACE, status="completed"))
        for index, (child_execution_id, _action) in enumerate(child_executions):
            db.add(AgentExecution(
                id=child_execution_id, agent_id="ag-fleet",
                tenant_id=TENANT, workspace_id=WORKSPACE,
                status="completed"))
            db.add(ChainLink(
                id=f"link-credit-{index}",
                chain_id="chain-credit",
                parent_agent_id="atom-fleet",
                child_agent_id="ag-fleet",
                task_description="finance specialist work",
                context_json={"domain": "finance"},
                result_json={
                    "execution_id": child_execution_id,
                    "agent_id": "ag-fleet",
                    "domain": "finance",
                    "status": "completed",
                    "task_digest": "digest-credit",
                },
                status="completed",
                link_order=index,
            ))
        db.add(FleetRoutingAudit(
            id="audit-credit",
            execution_id="parent-exec",
            tenant_id=TENANT,
            workspace_id=WORKSPACE,
            agent_id="atom-fleet",
            workload_key="wk-credit",
            chain_id="chain-credit",
            specialists_count=len(child_executions),
            roster_json=[
                {"agent_id": "ag-fleet", "domain": "finance"}
                for _ in child_executions
            ],
            recruitment_succeeded=True,
            enforced=True,
            decision_source="fleet_eligible",
            success=True,
        ))
        db.commit()


def _stats(db, capability):
    db.expire_all()
    agent = db.query(AgentRegistry).filter_by(id="ag-fleet").one()
    return dict(
        (agent.configuration or {}).get("capability_stats", {}).get(
            capability, {}))


def _credit(db, **overrides):
    kwargs = {
        "audit_id": "audit-credit",
        "tenant_id": TENANT,
        "workspace_id": WORKSPACE,
        "agent_id": "atom-fleet",
    }
    kwargs.update(overrides)
    return record_chain_credit("parent-exec", db=db, **kwargs)


def _receipt_count(db):
    db.expire_all()
    return db.query(TaskOperationRecord).filter(
        TaskOperationRecord.operation_type == CREDIT_RECEIPT_TYPE).count()


def test_real_oracle_receipt_positive_and_replay_are_idempotent(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.invoice.post." + uuid.uuid4().hex
    child = "child-positive"
    _produce_verified_operation(
        fleet_world, child_execution_id=child, action_name=action,
        operation_id="op-positive")
    _seed_fleet(fleet_world, child_executions=[(child, action)])

    with fleet_world.session() as db:
        assert _credit(db) is True
        stats = _stats(db, action)
        assert stats.get("verified_success") == 1
        assert stats.get("success") == 1
        assert _receipt_count(db) == 1

    # Replay from a fresh Session must not add usage or a second receipt.
    with fleet_world.session() as fresh:
        assert _credit(fresh) is False
        replay_stats = _stats(fresh, action)
        assert replay_stats.get("verified_success") == 1
        assert replay_stats.get("total") == 1
        assert _receipt_count(fresh) == 1


def test_completed_status_and_forged_verified_flag_earn_zero(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    child = "child-forged"
    _seed_fleet(fleet_world, child_executions=[(child, "unused")])
    with fleet_world.session() as db:
        link = db.query(ChainLink).filter_by(id="link-credit-0").one()
        # A raw model/runner claim is not verification authority.
        link.result_json = {
            "execution_id": child,
            "agent_id": "ag-fleet",
            "domain": "finance",
            "status": "completed",
            "verified": True,
            "oracle_verified": True,
        }
        db.commit()

        assert _credit(db) is True
        # Visible as unverified work under the link's domain, never verified.
        stats = _stats(db, "finance")
        assert stats.get("success") == 1
        assert stats.get("verified_success") == 0
        assert _receipt_count(db) == 1


def test_foreign_child_binding_is_refused_not_downgraded(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    _seed_fleet(fleet_world, child_executions=[("child-real", "unused")])
    with fleet_world.session() as db:
        link = db.query(ChainLink).filter_by(id="link-credit-0").one()
        link.result_json = {
            "execution_id": "child-foreign",
            "agent_id": "ag-fleet",
            "domain": "finance",
            "status": "completed",
        }
        db.commit()

        assert _credit(db) is False
        assert _stats(db, "finance") == {}
        # No child execution was created for "child-foreign": contradictory
        # material is refused, not converted into an unverified finance win.
        assert _receipt_count(db) == 0


def test_distinct_real_child_outcomes_each_learn_once(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.ledger.reconcile." + uuid.uuid4().hex
    children = ["child-distinct-1", "child-distinct-2"]
    for index, child in enumerate(children):
        _produce_verified_operation(
            fleet_world, child_execution_id=child, action_name=action,
            operation_id=f"op-distinct-{index}")
    _seed_fleet(
        fleet_world,
        child_executions=[(child, action) for child in children])

    with fleet_world.session() as db:
        assert _credit(db) is True
        stats = _stats(db, action)
        assert stats.get("verified_success") == 2
        assert stats.get("total") == 2
        assert _receipt_count(db) == 2

        # Same outcome again is a replay, not two more credits.
        assert _credit(db) is False
        assert _stats(db, action).get("verified_success") == 2
        assert _receipt_count(db) == 2


def test_missing_scope_ambiguous_audit_and_shadow_are_refused(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.approval.post." + uuid.uuid4().hex
    child = "child-scope"
    _produce_verified_operation(
        fleet_world, child_execution_id=child, action_name=action,
        operation_id="op-scope")
    _seed_fleet(fleet_world, child_executions=[(child, action)])

    with fleet_world.session() as db:
        assert _credit(db, tenant_id="foreign-tenant") is False
        assert _stats(db, action) == {}

        # A second audit row for the same execution is ambiguous: no .first().
        db.add(FleetRoutingAudit(
            execution_id="parent-exec", tenant_id=TENANT,
            workspace_id=WORKSPACE, agent_id="atom-fleet",
            workload_key="wk-other", chain_id="chain-credit",
            enforced=True, decision_source="fleet_eligible", success=True))
        db.commit()
        assert record_chain_credit(
            "parent-exec", db=db, tenant_id=TENANT,
            workspace_id=WORKSPACE, agent_id="atom-fleet") is False
        assert _stats(db, action) == {}

    # A shadow audit measures the incumbent, not fleet work.
    with fleet_world.session() as fresh:
        fresh.query(FleetRoutingAudit).filter_by(
            id="audit-credit").one().enforced = False
        fresh.commit()
        assert _credit(fresh) is False
        assert _stats(fresh, action) == {}


def test_missing_credit_recovery_and_duplicate_contender(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.payment.release." + uuid.uuid4().hex
    child = "child-recovery"
    _produce_verified_operation(
        fleet_world, child_execution_id=child, action_name=action,
        operation_id="op-recovery")
    _seed_fleet(fleet_world, child_executions=[(child, action)])

    # Outcome committed, worker lost BEFORE credit: no receipt exists yet.
    with fleet_world.session() as db:
        assert _receipt_count(db) == 0

    # Recovery pass applies the missing credit, exactly once.
    with fleet_world.session() as db:
        assert _credit(db) is True
        assert _stats(db, action).get("verified_success") == 1
        assert _receipt_count(db) == 1

    # A second contender arriving after the winner sees the same receipt.
    with fleet_world.session() as contender:
        assert _credit(contender) is False
        assert _stats(contender, action).get("verified_success") == 1
        assert _receipt_count(contender) == 1


def test_pre_revocation_work_cannot_become_new_success(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.risk.review." + uuid.uuid4().hex
    child = "child-pre-revocation"
    _produce_verified_operation(
        fleet_world, child_execution_id=child, action_name=action,
        operation_id="op-pre-revocation")
    _seed_fleet(fleet_world, child_executions=[(child, action)])

    with fleet_world.session() as db:
        agent = db.query(AgentRegistry).filter_by(id="ag-fleet").one()
        # Revocation at a future instant means the already-produced receipt is
        # pre-revocation work when the credit worker finally runs.
        agent.configuration = {
            "autonomy_revocations": {
                action: {
                    "at": (
                        datetime.now(timezone.utc) + timedelta(hours=1)
                    ).isoformat(),
                    "reason": "verified_regression",
                    "epoch": 1,
                }
            }
        }
        db.query(AgentRegistry).filter_by(id="ag-fleet").update(
            {"configuration": agent.configuration},
            synchronize_session=False)
        db.commit()

        assert _credit(db) is True
        stats = _stats(db, action)
        # The outcome is still visible, but cannot increment verified success.
        assert stats.get("success") == 1
        assert stats.get("verified_success") == 0
