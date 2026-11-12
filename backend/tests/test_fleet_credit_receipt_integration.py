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
from sqlalchemy import create_engine, event, text
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
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"timeout": 0.2})
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

        # Same-run replay in the SAME unit of work is also consumed once.
        assert _credit(db) is False
        assert _stats(db, action).get("verified_success") == 1
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


def test_finalizer_does_not_credit_a_nonunique_execution_join(
        fleet_world, monkeypatch):
    """The finalizer must pass one exact audit id. If the execution joins more
    than one candidate audit row, credit is refused rather than choosing a
    first row arbitrarily."""
    from core.fleet_orchestration import fleet_routing_stats as frs

    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.audit.join." + uuid.uuid4().hex
    child = "child-ambiguous-finalizer"
    _seed_real_credit(
        fleet_world, child=child, action=action, operation_id="op-ambiguous")

    with fleet_world.Session() as db:
        first = db.query(FleetRoutingAudit).filter_by(id="audit-credit").one()
        first.success = None
        db.add(FleetRoutingAudit(
            id="audit-credit-2", execution_id="parent-exec",
            tenant_id=TENANT, workspace_id=WORKSPACE, agent_id="atom-fleet",
            workload_key="wk-credit-2", chain_id="chain-credit",
            enforced=True, decision_source="fleet_eligible", success=None))
        db.commit()

    monkeypatch.setattr("core.database.get_db_session", fleet_world.session)
    result = frs.record_fleet_execution_outcome(
        "parent-exec", True, tenant_id=TENANT, workspace_id=WORKSPACE,
        agent_id="atom-fleet")
    assert result["status"] == "conflict", result
    assert result["applied"] == [], result

    with fleet_world.Session() as fresh:
        assert _receipt_count(fresh) == 0
        assert _stats(fresh, action) == {}


def test_finalizer_replay_credits_once_from_fresh_sessions(
        fleet_world, monkeypatch):
    """The documented finalizer replay: the first join applies the pending
    audit and credits that exact outcome, the second is an already-applied
    replay that adds neither a receipt nor another verified success."""
    from core.fleet_orchestration import fleet_routing_stats as frs

    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.invoice.verify." + uuid.uuid4().hex
    child = "child-finalizer-replay"
    _seed_real_credit(
        fleet_world, child=child, action=action,
        operation_id="op-finalizer-replay")

    # The execution finalized before its audit join: the outcome is pending
    # exactly once, which is the state the real finalizer consumes.
    with fleet_world.Session() as db:
        db.query(FleetRoutingAudit).filter_by(
            id="audit-credit").one().success = None
        db.commit()

    monkeypatch.setattr("core.database.get_db_session", fleet_world.session)
    first = frs.record_fleet_execution_outcome(
        "parent-exec", True, audit_id="audit-credit", tenant_id=TENANT,
        workspace_id=WORKSPACE, agent_id="atom-fleet")
    assert first["status"] == "applied", first
    assert first["applied"] == ["audit-credit"], first
    assert first["already_applied"] == [], first

    with fleet_world.Session() as fresh:
        assert _receipt_count(fresh) == 1
        stats = _stats(fresh, action)
        assert stats.get("verified_success") == 1
        assert stats.get("success") == 1

    replay = frs.record_fleet_execution_outcome(
        "parent-exec", True, audit_id="audit-credit", tenant_id=TENANT,
        workspace_id=WORKSPACE, agent_id="atom-fleet")
    assert replay["status"] == "already_applied", replay
    assert replay["already_applied"] == ["audit-credit"], replay
    assert replay["applied"] == [], replay

    with fleet_world.Session() as fresh:
        assert _receipt_count(fresh) == 1
        stats = _stats(fresh, action)
        assert stats.get("verified_success") == 1
        assert stats.get("total") == 1


def test_finalizer_flag_off_applies_outcome_without_credit(
        fleet_world, monkeypatch):
    """Negative twin: with the credit flag OFF the finalizer still joins the
    exact outcome, but never writes a receipt or verified success."""
    from core.fleet_orchestration import fleet_routing_stats as frs

    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "false")
    action = "finance.invoice.verify." + uuid.uuid4().hex
    child = "child-finalizer-flag-off"
    _seed_real_credit(
        fleet_world, child=child, action=action,
        operation_id="op-finalizer-flag-off")

    with fleet_world.Session() as db:
        db.query(FleetRoutingAudit).filter_by(
            id="audit-credit").one().success = None
        db.commit()

    monkeypatch.setattr("core.database.get_db_session", fleet_world.session)
    first = frs.record_fleet_execution_outcome(
        "parent-exec", True, audit_id="audit-credit", tenant_id=TENANT,
        workspace_id=WORKSPACE, agent_id="atom-fleet")
    assert first["status"] == "applied", first
    assert first["applied"] == ["audit-credit"], first

    replay = frs.record_fleet_execution_outcome(
        "parent-exec", True, audit_id="audit-credit", tenant_id=TENANT,
        workspace_id=WORKSPACE, agent_id="atom-fleet")
    assert replay["status"] == "already_applied", replay

    with fleet_world.Session() as fresh:
        assert fresh.query(FleetRoutingAudit).filter_by(
            id="audit-credit").one().success is True
        assert _receipt_count(fresh) == 0
        assert _stats(fresh, action) == {}


def test_meta_agent_finalizer_derives_scope_and_credits_once(
        fleet_world, monkeypatch):
    """The real ``AtomMetaAgent._finalize_agent_execution`` is the production
    finalizer. Given a persisted parent execution, a pending audit row and no
    caller-supplied scope, it derives tenant/workspace/agent from that
    execution, joins the exact audit, and credits the child's durable receipt
    exactly once across a replay."""
    from core import atom_meta_agent as ama
    from core.models import AgentTriggerMode

    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.invoice.reconcile." + uuid.uuid4().hex
    child = "child-meta-finalizer"
    _seed_real_credit(
        fleet_world, child=child, action=action,
        operation_id="op-meta-finalizer")

    # The execution is still running and its audit join is pending: exactly
    # the state the real finalizer consumes.
    with fleet_world.Session() as db:
        parent = db.get(AgentExecution, "parent-exec")
        parent.status = "running"
        parent.result_summary = None
        db.query(FleetRoutingAudit).filter_by(
            id="audit-credit").one().success = None
        db.commit()

    with fleet_world.Session() as fresh:
        assert _receipt_count(fresh) == 0
        assert _stats(fresh, action) == {}

    monkeypatch.setattr(ama, "SessionLocal", fleet_world.Session)
    monkeypatch.setattr("core.database.get_db_session", fleet_world.session)

    async def _noop_record_execution(*args, **kwargs):
        return None

    agent = ama.AtomMetaAgent.__new__(ama.AtomMetaAgent)
    agent._record_execution = _noop_record_execution

    async def _finalize():
        await ama.AtomMetaAgent._finalize_agent_execution(
            agent,
            execution_id="parent-exec",
            request="fleet goal",
            result_payload={"status": "success"},
            durable_status="success",
            final_answer="done",
            start_time=datetime.now(timezone.utc),
            trigger_mode=AgentTriggerMode.MANUAL,
            tenant_id=None,
            context={},
            fleet_audit_id="audit-credit",
            fleet_success=True,
            fleet_error=None,
            fleet_model="model-x",
            fleet_provider="provider-x",
        )

    asyncio.run(_finalize())

    with fleet_world.Session() as fresh:
        parent = fresh.get(AgentExecution, "parent-exec")
        assert parent.status == "completed"
        assert parent.result_summary == "done"
        assert parent.duration_seconds is not None
        assert fresh.get(FleetRoutingAudit, "audit-credit").success is True
        assert _receipt_count(fresh) == 1
        stats = _stats(fresh, action)
        assert stats.get("verified_success") == 1
        assert stats.get("success") == 1
        assert stats.get("total") == 1

    # Replay through the same finalizer: same outcome material, no new
    # receipt, no second verified success.
    asyncio.run(_finalize())

    with fleet_world.Session() as fresh:
        assert _receipt_count(fresh) == 1
        stats = _stats(fresh, action)
        assert stats.get("verified_success") == 1
        assert stats.get("success") == 1
        assert stats.get("total") == 1


def test_meta_agent_finalizer_failed_outcome_earns_zero_credit(
        fleet_world, monkeypatch):
    """Failed-outcome twin (GLM audit 92248): the real
    ``AtomMetaAgent._finalize_agent_execution`` joins a FAILED parent outcome
    onto the exact pending audit while the child's real oracle-verified
    receipt is still durable. From a fresh session the audit records the
    failure and neither a credit receipt nor capability credit exists — a
    verified child contribution must not mint credit for a failed chain
    outcome."""
    from core import atom_meta_agent as ama
    from core.models import AgentTriggerMode

    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.invoice.reconcile." + uuid.uuid4().hex
    child = "child-meta-finalizer-failed"
    _seed_real_credit(
        fleet_world, child=child, action=action,
        operation_id="op-meta-finalizer-failed")

    # Pending audit join + running parent: exactly the state the real
    # finalizer consumes, with the child's real receipt already durable.
    with fleet_world.Session() as db:
        parent = db.get(AgentExecution, "parent-exec")
        parent.status = "running"
        parent.result_summary = None
        db.query(FleetRoutingAudit).filter_by(
            id="audit-credit").one().success = None
        db.commit()

    with fleet_world.Session() as fresh:
        assert _receipt_count(fresh) == 0
        assert _stats(fresh, action) == {}
        # The reused fixture is a REAL receipt: a succeeded generic-agent
        # operation whose durable result was written after an independent
        # oracle readback — not a status-only or forged claim.
        receipt_row = fresh.query(TaskOperationRecord).filter(
            TaskOperationRecord.operation_type
            == f"generic:agent:{action}").one()
        receipt = receipt_row.result_json
        assert receipt.get("success") is True
        assert receipt.get("oracle_verified") is True
        assert receipt.get("status") == "success"
        assert receipt.get("operation_id") == receipt_row.operation_id

    fleet_error = "fleet run failed: ledger reconciliation mismatch"

    monkeypatch.setattr(ama, "SessionLocal", fleet_world.Session)
    monkeypatch.setattr("core.database.get_db_session", fleet_world.session)

    async def _noop_record_execution(*args, **kwargs):
        return None

    agent = ama.AtomMetaAgent.__new__(ama.AtomMetaAgent)
    agent._record_execution = _noop_record_execution

    async def _finalize():
        await ama.AtomMetaAgent._finalize_agent_execution(
            agent,
            execution_id="parent-exec",
            request="fleet goal",
            result_payload={"status": "failed"},
            durable_status="failed",
            final_answer="fleet run failed",
            start_time=datetime.now(timezone.utc),
            trigger_mode=AgentTriggerMode.MANUAL,
            tenant_id=None,
            context={},
            fleet_audit_id="audit-credit",
            fleet_success=False,
            fleet_error=fleet_error,
            fleet_model="model-x",
            fleet_provider="provider-x",
        )

    asyncio.run(_finalize())

    with fleet_world.Session() as fresh:
        # Durable failed outcome on both the execution and the audit row.
        parent = fresh.get(AgentExecution, "parent-exec")
        assert parent.status == "failed"
        assert fleet_error in (parent.error_message or "")
        assert parent.duration_seconds is not None
        assert fresh.get(FleetRoutingAudit, "audit-credit").success is False

        # The real child receipt survives untouched, yet earns nothing:
        # zero credit receipts and zero capability credit.
        assert _receipt_count(fresh) == 0
        assert _stats(fresh, action) == {}

    # Replay through the same finalizer with identical failure material:
    # the failure stays recorded exactly once and credit is still refused.
    asyncio.run(_finalize())

    with fleet_world.Session() as fresh:
        assert fresh.get(FleetRoutingAudit, "audit-credit").success is False
        assert _receipt_count(fresh) == 0
        assert _stats(fresh, action) == {}


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


# ---------------------------------------------------------------------------
# Stale writer / CAS discipline
# ---------------------------------------------------------------------------


def test_forced_sqlite_stale_writer_cannot_erase_peer_revocation(tmp_path):
    """A stale success writer must reload after losing the conditional UPDATE.

    The peer commits a verified-regression revocation between our observed
    configuration read and our UPDATE. The database CAS matches zero rows; a
    bounded reload then applies the success on top of the peer's revocation,
    never replacing it with the stale pre-revocation blob.
    """
    from core.capability_graduation_service import CapabilityGraduationService
    from core.models import AgentRegistry

    # Commit the peer immediately before the weak UPDATE reaches SQLite.
    # An after-SELECT hook leaves its cursor open and prevents the peer commit;
    # that tests an artificial cursor lock instead of the stale-writer race.
    engine = create_engine(f"sqlite:///{tmp_path / 'cas_race.db'}")
    AgentRegistry.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    capability = "finance.invoice.post"
    with Session() as db:
        db.add(AgentRegistry(
            id="ag-race", name="Race", category="Ops", role="agent",
            type="personal", module_path="m", class_name="C",
            configuration={
                "capability_stats": {
                    capability: {
                        "success": 5, "total": 5, "verified_success": 5}},
                "capability_maturities": {capability: "intern"},
            }))
        db.commit()

    armed = [True]

    @event.listens_for(engine, "before_cursor_execute")
    def _peer_commits_revocation(conn, cursor, statement, params, ctx, many):
        if not armed[0]:
            return
        if not statement.lstrip().upper().startswith("UPDATE AGENT_REGISTRY"):
            return
        if "agent_registry" not in statement or "CAST" not in statement.upper():
            return
        armed[0] = False
        with Session() as peer:
            assert CapabilityGraduationService(peer).record_usage(
                "ag-race", capability, False, "failed_verification") is True

    with Session() as db:
        service = CapabilityGraduationService(db)
        assert service.record_usage(
            "ag-race", capability, success=True,
            verified="verified") is True

    with Session() as db:
        config = dict(db.get(AgentRegistry, "ag-race").configuration or {})
        revocation = config["autonomy_revocations"][capability]
        stats = config["capability_stats"][capability]
        assert int(revocation["epoch"]) == 1
        assert int(revocation["baseline_verified_success"]) == 5
        assert int(revocation["reentry_successes"]) == 1
        assert int(stats["verified_success"]) == 6
        assert config["capability_maturities"][capability] == "student"


# ---------------------------------------------------------------------------
# Borrowed caller sessions: dirty / flushed / new / deleted are untouchable
# ---------------------------------------------------------------------------


def _seed_real_credit(world, *, child, action, operation_id):
    _produce_verified_operation(
        world, child_execution_id=child, action_name=action,
        operation_id=operation_id)
    _seed_fleet(world, child_executions=[(child, action)])


def test_dirty_new_and_deleted_caller_state_is_never_committed(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.ledger.post." + uuid.uuid4().hex
    child = "child-dirty-caller"
    _seed_real_credit(
        fleet_world, child=child, action=action, operation_id="op-dirty")

    Session = sessionmaker(
        bind=fleet_world.engine, expire_on_commit=False)
    with Session() as caller:
        agent = caller.get(AgentRegistry, "ag-fleet")
        deleted_agent = caller.get(AgentRegistry, "atom-fleet")
        caller.commit()  # end the read transaction; keep dirty objects only

        # Keep this the unflushed twin. ORM delete cascades can otherwise
        # autoflush the earlier name edit during fixture construction, turning
        # it into the separate already-flushed/SQLite-lock refusal case.
        with caller.no_autoflush:
            agent.name = "dirty-caller-name"
            caller.delete(deleted_agent)
            caller.add(AgentRegistry(
                id="ag-pending-new", name="Pending", category="Ops",
                role="agent", type="personal", module_path="m", class_name="C",
                tenant_id=TENANT, workspace_id=WORKSPACE))
            assert caller.new or caller.dirty or caller.deleted

            # An independent owned writer applies the credit; the caller's unit of
            # work is neither committed nor rolled back.
            assert _credit(caller) is True
            assert agent.name == "dirty-caller-name"
            assert agent in caller.dirty
            assert deleted_agent in caller.deleted
            assert any(row.id == "ag-pending-new" for row in caller.new)

    with fleet_world.Session() as fresh:
        assert fresh.get(AgentRegistry, "ag-fleet").name == "Fleet Specialist"
        assert fresh.get(AgentRegistry, "atom-fleet") is not None
        assert fresh.get(AgentRegistry, "ag-pending-new") is None
        assert _stats(fresh, action).get("verified_success") == 1


def test_already_flushed_caller_edit_blocks_independent_write_and_is_refused(
        fleet_world, monkeypatch):
    """A flushed (but uncommitted) caller edit holds the SQLite write lock.

    The supplement must refuse explicitly instead of committing, rolling back,
    expiring, or borrowing that transaction.
    """
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    action = "finance.payment.post." + uuid.uuid4().hex
    child = "child-flushed-caller"
    _seed_real_credit(
        fleet_world, child=child, action=action, operation_id="op-flushed")

    Session = sessionmaker(bind=fleet_world.engine, expire_on_commit=False)
    caller = Session()
    try:
        agent = caller.get(AgentRegistry, "ag-fleet")
        caller.commit()  # end the read transaction
        agent.name = "flushed-caller-name"
        caller.flush()     # already-flushed edit, still uncommitted
        assert caller.in_transaction()
        assert _credit(caller) is False
        assert caller.in_transaction()
        assert caller.get(AgentRegistry, "ag-fleet").name == "flushed-caller-name"
    finally:
        caller.rollback()
        caller.close()

    with fleet_world.Session() as fresh:
        assert fresh.get(AgentRegistry, "ag-fleet").name == "Fleet Specialist"
        # Refusal wrote nothing at all.
        assert _receipt_count(fresh) == 0
        assert _stats(fresh, action) == {}


# ---------------------------------------------------------------------------
# Stable child dispatch recovery from the durable server result
# ---------------------------------------------------------------------------


def test_lost_cache_recovers_full_child_output_without_redispatch(
        tmp_path, monkeypatch):
    """A resumed child whose chain cache/link result was lost recovers the
    actual full specialist output from the succeeded durable dispatch claim and
    never constructs a second GenericAgent."""
    from core.fleet_admiral import FleetAdmiral

    engine = create_engine(f"sqlite:///{tmp_path / 'fleet_recovery.db'}")
    for model in (AgentRegistry, DelegationChain, ChainLink,
                  TaskOperationRecord):
        model.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    tenant, workspace = "tenant-recovery", "workspace-recovery"
    task = "reconcile the ledger"
    roster = [{"agent_id": "ag-recover", "agent_name": "Recover",
               "domain": "finance", "capability_score": 1.0}]
    full_output = (
        "Full specialist contribution: reconciled 17 ledger rows against the "
        "bank statement and listed every unmatched entry with its exact id.")

    with Session() as db:
        db.add(AgentRegistry(
            id="ag-recover", name="Recover", category="Finance",
            role="agent", type="personal", module_path="m", class_name="C",
            tenant_id=tenant, workspace_id=workspace,
            capabilities=["finance"], specialty="finance"))
        db.add(DelegationChain(
            id="chain-recovery", tenant_id=tenant, root_agent_id="atom-main",
            root_task=task, status="in_progress",
            metadata_json={"workspace_id": workspace}))
        db.commit()

        admiral = FleetAdmiral.__new__(FleetAdmiral)
        admiral.db = db
        admiral.llm = None
        digest = admiral._specialist_task_digest(
            task, "chain-recovery", roster, tenant, workspace, {})
        link, binding = admiral._bind_specialist_link(
            chain=db.get(DelegationChain, "chain-recovery"),
            chain_id="chain-recovery", item=roster[0], link_order=0,
            task_digest=digest, tenant_id=tenant, workspace_id=workspace,
            actor_id="user-recovery")
        claim = admiral._claim_child_dispatch(
            binding=binding, chain_id="chain-recovery", tenant_id=tenant,
            workspace_id=workspace, agent_id="ag-recover",
            actor_id="user-recovery")
        assert claim.get("won") is True, claim
        assert admiral._finish_child_claim(
            claim, binding=binding, status="completed", success=True,
            output_length=len(full_output), task_digest=digest,
            output=full_output) is True

        # Crash/loss after the outcome: cache and link result are gone.
        chain = db.get(DelegationChain, "chain-recovery")
        chain.metadata_json = {"workspace_id": workspace}
        link = db.get(ChainLink, link.id)
        link.status = "in_progress"
        link.result_json = None
        db.commit()

        class _NoDispatch:
            def __init__(self, *args, **kwargs):
                raise AssertionError("specialist was dispatched a second time")

        monkeypatch.setattr("core.generic_agent.GenericAgent", _NoDispatch)

        result = asyncio.run(admiral.execute_recruited_specialists(
            task=task, user_id="user-recovery", chain_id="chain-recovery",
            roster=roster, tenant_id=tenant, workspace_id=workspace,
            context={}))

        assert result["success"] is True, result
        assert full_output in result["final_output"]
        assert result["specialist_results"][0]["output"] == full_output
        assert result["specialist_results"][0]["recovered"] is True
        assert full_output in (
            db.get(DelegationChain, "chain-recovery").metadata_json[
                "specialist_execution"]["result"]["final_output"])
        assert db.get(ChainLink, link.id).status == "completed"

        # The recovery pass re-cached the exact result; a later resume is a
        # cache hit, still with no dispatch.
        resumed = asyncio.run(admiral.execute_recruited_specialists(
            task=task, user_id="user-recovery", chain_id="chain-recovery",
            roster=roster, tenant_id=tenant, workspace_id=workspace,
            context={}))
        assert resumed.get("cached") is True, resumed
        assert full_output in resumed["final_output"]
