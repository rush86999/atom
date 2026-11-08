"""Exact Oracle controls for the registered ``radio.create_thread`` write.

The controls join the REAL registered action, REAL GenericAgent mutation
claim/Oracle consumer, REAL ``radio_service`` persistence and the REAL shared
postcondition verifier against scratch SQLite.  They also exercise the
single-tenant AgentRegistry scope contract (NULL / ``default`` personal scope,
concrete workspace/tenant equality) and the existing maturity floor.

No provider/model/network/account/sandbox is touched.
"""
from __future__ import annotations

import asyncio
import contextlib
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generic_agent as ga
import core.models  # noqa: F401 - register every model on the base
from core.action_registry import action_registry
from core.agent_radio import radio_actions  # noqa: F401 - registers actions
from core.agent_radio import radio_server
from core.generic_agent import GenericAgent
from core.models import AgentRegistry, AgentThread, Tenant, Workspace
from core.models_registration import Base


@contextlib.contextmanager
def _session_factory(path):
    engine = create_engine(f"sqlite:///{path}")
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _reset_radio_server():
    radio_server.reset_radio_server()
    yield
    radio_server.reset_radio_server()


@pytest.fixture(autouse=True)
def _oracle_on(monkeypatch):
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    monkeypatch.setenv("ATOM_RADIO_ENABLED", "true")


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / "radio_thread.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _session():
        return _session_factory(path)

    monkeypatch.setattr(ga, "get_db_session", _session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.get_db_session", _session)

    with Session() as db:
        db.add_all([
            Tenant(id="tenant-1", name="Tenant One", subdomain="tenant-one"),
            Workspace(id="ws-1", name="Workspace One", tenant_id="tenant-1"),
        ])
        db.flush()
        db.add_all([
            AgentRegistry(
                id="agent-a", name="Agent A", category="operations",
                module_path="x.a", class_name="A", status="autonomous",
                enabled=True, tenant_id="tenant-1", workspace_id="ws-1"),
            AgentRegistry(
                id="agent-b", name="Agent B", category="operations",
                module_path="x.b", class_name="B", status="intern",
                enabled=True, tenant_id="tenant-1", workspace_id="ws-1"),
            AgentRegistry(
                id="agent-c", name="Agent C", category="operations",
                module_path="x.c", class_name="C", status="student",
                enabled=True, tenant_id="tenant-1", workspace_id="ws-1"),
            AgentRegistry(
                id="agent-disabled", name="Disabled Agent", category="operations",
                module_path="x.d", class_name="D", status="autonomous",
                enabled=False, tenant_id="tenant-1", workspace_id="ws-1"),
            AgentRegistry(
                id="agent-paused", name="Paused Agent", category="operations",
                module_path="x.p", class_name="P", status="paused",
                enabled=True, tenant_id="tenant-1", workspace_id="ws-1"),
            AgentRegistry(
                id="agent-other-ws", name="Other Workspace", category="operations",
                module_path="x.w", class_name="W", status="autonomous",
                enabled=True, tenant_id="tenant-1", workspace_id="ws-2"),
            AgentRegistry(
                id="agent-other-tenant", name="Other Tenant", category="operations",
                module_path="x.t", class_name="T", status="autonomous",
                enabled=True, tenant_id="tenant-2", workspace_id="ws-1"),
            AgentRegistry(
                id="personal-a", name="Personal A", category="operations",
                module_path="x.pa", class_name="PA", status="autonomous",
                enabled=True, tenant_id=None, workspace_id=None),
            AgentRegistry(
                id="personal-b", name="Personal B", category="operations",
                module_path="x.pb", class_name="PB", status="intern",
                enabled=True, tenant_id=None, workspace_id=None),
        ])
        db.commit()
    return {"path": str(path), "Session": Session}


def _agent(agent_id="agent-a", *, tenant_id="tenant-1", workspace_id="ws-1"):
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = agent_id
    agent.workspace_id = workspace_id
    agent.tenant_id = tenant_id
    agent._custom_actions = {}

    async def registry_leaf(tool_name, arguments, context=None):
        return await action_registry.execute_action(
            tool_name, arguments, context or {})

    agent.mcp = SimpleNamespace(call_tool=registry_leaf)
    return agent


def _context(
    operation_id,
    *,
    agent_id="agent-a",
    tenant_id="tenant-1",
    workspace_id="ws-1",
    tier="autonomous",
):
    return {
        "operation_id": operation_id,
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "execution_id": "exec-radio-thread",
        "user_id": "user-radio",
        "agent_id": agent_id,
        "tier": tier,
    }


def _args(operation_id, **overrides):
    args = {
        "name": "alpha",
        "member_agent_ids": ["agent-b"],
        "scope_hint": "task",
        "operation_id": operation_id,
    }
    args.update(overrides)
    return args


def _call(agent, arguments, context):
    return asyncio.run(agent._step_act_unaudited(
        "radio.create_thread", arguments, context=context,
        pre_approved=True))


def _threads(env):
    with env["Session"]() as db:
        return db.query(AgentThread).all()


def _one_thread(env):
    rows = _threads(env)
    assert len(rows) == 1, rows
    return rows[0]


def _verify(env, result, args, operation_id, *, include_result=True):
    from core.oracle import validate
    from core.oracle.request_expectations import (
        approved_payload_sha256,
        build_request_expectations,
    )

    expected = build_request_expectations(
        "radio.create_thread",
        args,
        operation_id=operation_id,
        tenant_id="tenant-1",
        workspace_id="ws-1",
        actor_id="user-radio",
        agent_id="agent-a",
        request_sha256=approved_payload_sha256(args),
    )
    session = env["Session"]()
    try:
        ctx = {**args, **expected, "db": session}
        if include_result:
            ctx.update(result)
        return asyncio.run(validate("radio.create_thread", ctx))
    finally:
        session.close()


def _set_creator_state(env, agent_id, **values):
    with env["Session"]() as db:
        row = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).one()
        for key, value in values.items():
            setattr(row, key, value)
        db.commit()


# ---------------------------------------------------------------------------
# Exact positive / replay / conflict
# ---------------------------------------------------------------------------


def test_exact_create_is_independently_verified(env):
    operation_id = f"op-thread-exact-{uuid.uuid4().hex}"
    result = _call(_agent(), _args(operation_id), _context(operation_id))

    assert result["success"] is True, result
    assert result["action_result"] == "applied", result
    assert result["oracle_verified"] is True, result
    assert result["remote_id"], result
    assert result["provider_receipt"]["operation_id"] == operation_id, result
    assert result["read_receipt"]["resource_id"] == result["remote_id"], result
    fields = result["read_receipt"]["fields"]
    assert fields["name"] == "alpha", fields
    assert fields["created_by_agent_id"] == "agent-a", fields
    assert fields["member_agent_ids"] == ["agent-a", "agent-b"], fields
    assert fields["scope_hint"] == "task", fields
    assert fields["tenant_id"] == "tenant-1", fields

    thread = _one_thread(env)
    assert thread.id == result["remote_id"]
    assert thread.name == "alpha"
    assert thread.created_by_agent_id == "agent-a"
    assert thread.member_agent_ids == ["agent-a", "agent-b"]
    assert thread.tenant_id == "tenant-1"
    assert thread.metadata_json["scope"] == "task"
    assert thread.metadata_json["operation_id"] == operation_id


def test_model_supplied_identity_args_cannot_override_server_scope(env):
    operation_id = f"op-thread-identity-{uuid.uuid4().hex}"
    poisoned = _args(
        operation_id,
        agent_id="agent-other-tenant",
        tenant_id="tenant-2",
        workspace_id="ws-2",
    )
    result = _call(_agent(), poisoned, _context(operation_id))

    assert result["success"] is True, result
    assert result["oracle_verified"] is True, result
    thread = _one_thread(env)
    assert thread.created_by_agent_id == "agent-a"
    assert thread.tenant_id == "tenant-1"
    assert thread.member_agent_ids == ["agent-a", "agent-b"]


def test_same_operation_replay_does_not_duplicate(env):
    operation_id = f"op-thread-replay-{uuid.uuid4().hex}"
    args = _args(operation_id)
    context = _context(operation_id)

    first = _call(_agent(), args, context)
    second = _call(_agent(), args, context)

    assert first["success"] is True and first["oracle_verified"] is True, first
    assert second["success"] is True, second
    assert second.get("already_applied") is True or second.get(
        "action_result") == "already_applied", second
    assert second["oracle_verified"] is True, second
    assert len(_threads(env)) == 1


def test_changed_material_same_operation_conflicts(env):
    operation_id = f"op-thread-conflict-{uuid.uuid4().hex}"
    first = _call(_agent(), _args(operation_id), _context(operation_id))
    changed = _call(
        _agent(),
        _args(operation_id, name="beta", member_agent_ids=["agent-c"]),
        _context(operation_id),
    )

    assert first["success"] is True, first
    assert changed["success"] is False, changed
    assert changed["status"] == "conflict", changed
    assert changed["action_result"] == "not_applied", changed
    thread = _one_thread(env)
    assert thread.name == "alpha"
    assert thread.member_agent_ids == ["agent-a", "agent-b"]


# ---------------------------------------------------------------------------
# Independent verifier negatives
# ---------------------------------------------------------------------------


def test_changed_roster_is_refuted(env):
    operation_id = f"op-thread-roster-{uuid.uuid4().hex}"
    args = _args(operation_id)
    result = _call(_agent(), args, _context(operation_id))
    assert result["oracle_verified"] is True, result

    with env["Session"]() as db:
        row = db.query(AgentThread).filter(
            AgentThread.id == result["remote_id"]).one()
        row.member_agent_ids = ["agent-a", "agent-b", "agent-c"]
        db.commit()

    verdict = _verify(env, result, args, operation_id)
    assert verdict is not None and verdict.verified is False, verdict
    assert "member_agent_ids" in verdict.evidence, verdict


def test_changed_name_case_is_refuted(env):
    operation_id = f"op-thread-name-{uuid.uuid4().hex}"
    args = _args(operation_id)
    result = _call(_agent(), args, _context(operation_id))
    assert result["oracle_verified"] is True, result

    with env["Session"]() as db:
        row = db.query(AgentThread).filter(
            AgentThread.id == result["remote_id"]).one()
        row.name = "Alpha"
        db.commit()

    verdict = _verify(env, result, args, operation_id)
    assert verdict is not None and verdict.verified is False, verdict
    assert "name" in verdict.evidence, verdict


def test_missing_row_is_refuted(env):
    operation_id = f"op-thread-missing-{uuid.uuid4().hex}"
    args = _args(operation_id)
    result = _call(_agent(), args, _context(operation_id))
    assert result["oracle_verified"] is True, result

    with env["Session"]() as db:
        db.query(AgentThread).filter(
            AgentThread.id == result["remote_id"]).delete()
        db.commit()

    verdict = _verify(env, result, args, operation_id)
    assert verdict is not None and verdict.verified is False, verdict
    assert "absent" in verdict.evidence, verdict


def test_duplicate_operation_rows_are_refuted(env):
    operation_id = f"op-thread-duplicate-{uuid.uuid4().hex}"
    args = _args(operation_id)
    result = _call(_agent(), args, _context(operation_id))
    assert result["oracle_verified"] is True, result

    with env["Session"]() as db:
        original = db.query(AgentThread).filter(
            AgentThread.id == result["remote_id"]).one()
        db.add(AgentThread(
            id=f"duplicate-{uuid.uuid4().hex}",
            name=original.name,
            created_by_agent_id=original.created_by_agent_id,
            member_agent_ids=list(original.member_agent_ids or []),
            tenant_id=original.tenant_id,
            status="open",
            metadata_json=dict(original.metadata_json or {}),
        ))
        db.commit()

    verdict = _verify(env, result, args, operation_id)
    assert verdict is not None and verdict.verified is False, verdict
    assert "multiple threads" in verdict.evidence, verdict


def test_stale_member_authority_refutes_replay(env):
    operation_id = f"op-thread-stale-{uuid.uuid4().hex}"
    args = _args(operation_id)
    context = _context(operation_id)
    first = _call(_agent(), args, context)
    assert first["oracle_verified"] is True, first

    _set_creator_state(env, "agent-b", enabled=False)
    replay = _call(_agent(), args, context)

    assert replay["success"] is False, replay
    assert replay["status"] == "committed_unverified", replay
    assert replay["oracle_verified"] is False, replay
    assert "authority" in replay["oracle_evidence"].lower(), replay
    assert len(_threads(env)) == 1


def test_moved_member_workspace_refutes(env):
    operation_id = f"op-thread-moved-{uuid.uuid4().hex}"
    args = _args(operation_id)
    result = _call(_agent(), args, _context(operation_id))
    assert result["oracle_verified"] is True, result

    _set_creator_state(env, "agent-b", workspace_id="ws-2")
    verdict = _verify(env, result, args, operation_id)
    assert verdict is not None and verdict.verified is False, verdict
    assert "workspace" in verdict.evidence, verdict


def test_legacy_replay_without_result_identity_uses_operation_binding(env):
    operation_id = f"op-thread-legacy-{uuid.uuid4().hex}"
    args = _args(operation_id)
    result = _call(_agent(), args, _context(operation_id))
    assert result["oracle_verified"] is True, result

    verdict = _verify(env, result, args, operation_id, include_result=False)
    assert verdict is not None and verdict.verified is True, verdict
    assert operation_id in (result["provider_receipt"]["operation_id"],)


# ---------------------------------------------------------------------------
# Producer readback / rollback twins
# ---------------------------------------------------------------------------


def test_readback_unavailable_is_uncertain_with_known_id(env, monkeypatch):
    import core.agent_radio.radio_thread_mutations as mutations

    operation_id = f"op-thread-readback-{uuid.uuid4().hex}"

    def boom(db, thread_id):
        raise RuntimeError("readback unavailable")

    monkeypatch.setattr(mutations, "read_thread", boom)
    result = _call(_agent(), _args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["status"] == "uncertain", result
    assert result["error_kind"] == "readback_unavailable", result
    assert result["remote_id"], result
    assert len(_threads(env)) == 1


def test_readback_mismatch_is_uncertain_with_known_id(env, monkeypatch):
    import core.agent_radio.radio_thread_mutations as mutations

    operation_id = f"op-thread-mismatch-{uuid.uuid4().hex}"

    def wrong_row(db, thread_id):
        return SimpleNamespace(
            id=thread_id, name="wrong", created_by_agent_id="agent-x",
            member_agent_ids=["agent-x"], tenant_id="tenant-1",
            metadata_json={"scope": "fleet", "operation_id": operation_id})

    monkeypatch.setattr(mutations, "read_thread", wrong_row)
    result = _call(_agent(), _args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["status"] == "uncertain", result
    assert result["error_kind"] == "readback_mismatch", result
    assert "name" in result["verification"]["mismatches"], result
    assert len(_threads(env)) == 1


def test_commit_failure_is_uncertain_without_row(env, monkeypatch):
    from core.agent_radio import radio_service

    operation_id = f"op-thread-rollback-{uuid.uuid4().hex}"

    def boom(db, **kwargs):
        # Add the row in this transaction, then fail before commit.  The
        # session context must roll it back; the producer must not report
        # success from an uncommitted object.
        db.add(AgentThread(
            name=kwargs.get("name"),
            created_by_agent_id=kwargs.get("created_by_agent_id"),
            member_agent_ids=kwargs.get("member_agent_ids"),
            tenant_id=kwargs.get("tenant_id"),
            metadata_json=kwargs.get("metadata_json"),
        ))
        raise RuntimeError("commit failed")

    monkeypatch.setattr(radio_service, "create_thread", boom)
    result = _call(_agent(), _args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["status"] == "uncertain", result
    assert result["error_kind"] == "provider_error", result
    assert len(_threads(env)) == 0


# ---------------------------------------------------------------------------
# Pre-effect authority / validation negatives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent_id", "members", "tenant_id", "workspace_id", "tier", "needle"),
    [
        ("ghost", ["agent-b"], "tenant-1", "ws-1", "autonomous",
         "creator agent is not registered"),
        ("agent-disabled", ["agent-b"], "tenant-1", "ws-1", "autonomous",
         "creator agent is disabled"),
        ("agent-paused", ["agent-b"], "tenant-1", "ws-1", "autonomous",
         "creator agent is paused"),
        ("agent-c", ["agent-b"], "tenant-1", "ws-1", "autonomous",
         "below INTERN maturity"),
        ("agent-a", ["ghost-member"], "tenant-1", "ws-1", "autonomous",
         "member 'ghost-member' agent is not registered"),
        ("agent-a", ["agent-disabled"], "tenant-1", "ws-1", "autonomous",
         "member 'agent-disabled' agent is disabled"),
        ("agent-a", ["agent-other-ws"], "tenant-1", "ws-1", "autonomous",
         "another workspace"),
        ("agent-a", ["agent-other-tenant"], "tenant-1", "ws-1", "autonomous",
         "another tenant"),
    ],
)
def test_authority_negatives_refuse_before_effect(
    env, agent_id, members, tenant_id, workspace_id, tier, needle,
):
    operation_id = f"op-thread-negative-{uuid.uuid4().hex}"
    result = _call(
        _agent(agent_id),
        _args(operation_id, member_agent_ids=members),
        _context(
            operation_id, agent_id=agent_id, tenant_id=tenant_id,
            workspace_id=workspace_id, tier=tier),
    )

    assert result["success"] is False, result
    assert result["status"] == "failed_before_effect", result
    assert result["action_result"] == "proven_not_applied", result
    assert result["effect_possible"] is False, result
    assert needle in result["message"], result
    assert len(_threads(env)) == 0


@pytest.mark.parametrize(
    ("overrides", "needle"),
    [
        ({"name": "   "}, "name is required"),
        ({"member_agent_ids": []},
         "member_agent_ids must list at least one other agent"),
        ({"member_agent_ids": ["agent-a"]},
         "member_agent_ids must list at least one other agent"),
        ({"scope_hint": "broadcast"},
         "scope_hint must be one of fleet, task, manual"),
        ({"name": "x" * 256}, "name exceeds 255 characters"),
    ],
)
def test_invalid_material_refuses_before_effect(env, overrides, needle):
    operation_id = f"op-thread-invalid-{uuid.uuid4().hex}"
    result = _call(
        _agent(), _args(operation_id, **overrides), _context(operation_id))
    assert result["success"] is False, result
    assert result["status"] == "failed_before_effect", result
    assert result["action_result"] == "proven_not_applied", result
    assert needle in result["message"], result
    assert len(_threads(env)) == 0


def test_personal_null_scope_is_valid(env):
    operation_id = f"op-thread-personal-{uuid.uuid4().hex}"
    result = _call(
        _agent("personal-a", tenant_id=None, workspace_id="default"),
        _args(operation_id, member_agent_ids=["personal-b"]),
        _context(
            operation_id, agent_id="personal-a",
            tenant_id=None, workspace_id="default"),
    )

    assert result["success"] is True, result
    assert result["oracle_verified"] is True, result
    thread = _one_thread(env)
    assert thread.tenant_id is None
    assert thread.member_agent_ids == ["personal-a", "personal-b"]


def test_default_scope_is_valid(env):
    with env["Session"]() as db:
        db.add(AgentRegistry(
            id="default-a", name="Default A", category="operations",
            module_path="x.da", class_name="DA", status="autonomous",
            enabled=True, tenant_id="default", workspace_id="default"))
        db.add(AgentRegistry(
            id="default-b", name="Default B", category="operations",
            module_path="x.db", class_name="DB", status="intern",
            enabled=True, tenant_id="default", workspace_id="default"))
        db.commit()

    operation_id = f"op-thread-default-{uuid.uuid4().hex}"
    result = _call(
        _agent("default-a", tenant_id="default", workspace_id="default"),
        _args(operation_id, member_agent_ids=["default-b"]),
        _context(
            operation_id, agent_id="default-a",
            tenant_id="default", workspace_id="default"),
    )

    assert result["success"] is True, result
    assert result["oracle_verified"] is True, result
    thread = _one_thread(env)
    assert thread.tenant_id == "default"
