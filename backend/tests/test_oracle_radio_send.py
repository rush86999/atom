"""Exact Oracle controls for the registered ``radio.send_message`` write.

Failure-first
-------------
The predecessor handler committed a ``LateralMessage`` row and returned the
raw success envelope; it never re-read the exact message id or compared the
authorized content/mentions/scope.  The real Generic mutation consumer therefore
reports the unverified send as ``uncertain``.  The exact-send control is written
first.

Scope and seams
---------------
The controls join the REAL registered action, REAL GenericAgent mutation claim,
REAL ``radio_service`` persistence and the REAL shared postcondition verifier.
There is no provider HTTP in this candidate: the scratch SQLite database and
the real models/service are used directly.  No live model, provider, server,
browser, account or credential is touched.

Contract: ``docs/architecture/AGENT_RADIO.md`` §Protocol — mention-first,
thread-scoped, no broadcast; ``agent_threads`` + ``lateral_messages`` rows.
"""
from __future__ import annotations

import asyncio
import copy
import sqlite3
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generic_agent as ga
from core.action_registry import action_registry
from core.agent_radio import radio_actions  # noqa: F401 - registers actions
from core.agent_radio import radio_server
from core.generic_agent import GenericAgent


@contextmanager
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
    from core.models_registration import Base
    import core.models  # noqa: F401 - registers every model on Base

    path = tmp_path / "radio_send.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _session():
        return _session_factory(path)

    monkeypatch.setattr(ga, "get_db_session", _session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.get_db_session", _session)
    return {"path": str(path), "Session": Session, "engine": engine,
            "_session": _session}


def _bind_scratch(monkeypatch, path):
    engine = create_engine(f"sqlite:///{path}")
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _session():
        return _session_factory(path)

    monkeypatch.setattr(ga, "get_db_session", _session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.get_db_session", _session)
    return {"path": str(path), "Session": Session, "engine": engine,
            "_session": _session}


def _seed_thread(
    env, *, thread_id="thread-1", tenant_id="tenant-1",
    members=("agent-a", "agent-b"),
):
    from core.models import AgentThread

    with env["Session"]() as db:
        db.add(AgentThread(
            id=thread_id,
            tenant_id=tenant_id,
            name="Scratch radio thread",
            created_by_agent_id="agent-a",
            status="open",
            member_agent_ids=list(members),
            metadata_json={"used_budget_usd": 0.0},
        ))
        db.commit()


def _message_rows(env):
    from core.models import LateralMessage

    with env["Session"]() as db:
        return db.query(LateralMessage).all()


def _agent():
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = "scratch-radio-agent"
    agent.workspace_id = "ws-radio"
    agent.tenant_id = "tenant-1"
    agent._custom_actions = {}

    async def registry_leaf(tool_name, arguments, context=None):
        return await action_registry.execute_action(
            tool_name, arguments, context or {})

    agent.mcp = SimpleNamespace(call_tool=registry_leaf)
    return agent


def _context(operation_id, *, agent_id="agent-a", tenant_id="tenant-1"):
    return {
        "operation_id": operation_id,
        "workspace_id": "ws-radio",
        "tenant_id": tenant_id,
        "execution_id": "exec-radio",
        "user_id": "user-radio",
        "agent_id": agent_id,
        "tier": "autonomous",
    }


def _call(agent, arguments, context):
    return asyncio.run(agent._step_act_unaudited(
        "radio.send_message", arguments, context=context,
        pre_approved=True))


def _claim_row(env, operation_id):
    with sqlite3.connect(env["path"]) as raw:
        columns = {
            row[1] for row in raw.execute(
                "pragma table_info(task_operation_records)")
        }
        if "result_json" in columns:
            return raw.execute(
                "select status, payload_sha256, result_json "
                "from task_operation_records where operation_id = ?",
                (operation_id,)).fetchone()
        return raw.execute(
            "select status, payload_sha256 from task_operation_records "
            "where operation_id = ?", (operation_id,)).fetchone()


def _send_args(operation_id, **overrides):
    args = {
        "thread_id": "thread-1",
        "content": "please review the checkout flow",
        "mention_agent_ids": ["agent-b"],
        "requires_response": False,
        "operation_id": operation_id,
    }
    args.update(overrides)
    return args


def _send_exact(env, monkeypatch, *, operation_id=None, args=None,
                context=None):
    if operation_id is None:
        operation_id = f"op-radio-{uuid.uuid4().hex}"
    args = args or _send_args(operation_id)
    context = context or _context(operation_id)
    result = _call(_agent(), args, context)
    return operation_id, args, context, result


# ---------------------------------------------------------------------------
# Exact positive / pre-effect negatives
# ---------------------------------------------------------------------------


def test_exact_send_is_independently_verified(env, monkeypatch):
    _seed_thread(env)
    operation_id, _args, _ctx, result = _send_exact(env, monkeypatch)

    assert result["success"] is True, result
    assert result["action_result"] == "applied", result
    assert result["oracle_verified"] is True, result
    assert result["remote_id"], result
    assert result["provider_receipt"]["operation_id"] == operation_id, result
    assert result["read_receipt"]["resource_id"] == result["remote_id"], result
    fields = result["read_receipt"]["fields"]
    assert fields["thread_id"] == "thread-1", fields
    assert fields["from_agent_id"] == "agent-a", fields
    assert fields["to_agent_id"] == "", fields
    assert fields["content"] == "please review the checkout flow", fields
    assert fields["mentions"] == ["agent-b"], fields
    assert fields["requires_response"] is False, fields
    assert fields["tenant_id"] == "tenant-1", fields
    assert len(_message_rows(env)) == 1
    assert _claim_row(env, operation_id)[0] == "succeeded"


def test_to_agent_and_requires_response_are_verified(env, monkeypatch):
    _seed_thread(env, members=("agent-a", "agent-b", "agent-c"))
    operation_id = f"op-radio-target-{uuid.uuid4().hex}"
    args = _send_args(
        operation_id,
        mention_agent_ids=["agent-c"],
        to_agent_id="agent-b",
        requires_response=True,
    )

    _op, _args, _ctx, result = _send_exact(
        env, monkeypatch, operation_id=operation_id, args=args)

    assert result["success"] is True, result
    assert result["oracle_verified"] is True, result
    fields = result["read_receipt"]["fields"]
    assert fields["to_agent_id"] == "agent-b", fields
    assert fields["mentions"] == ["agent-b", "agent-c"], fields
    assert fields["requires_response"] is True, fields


@pytest.mark.parametrize("case", [
    "missing_thread", "no_mentions", "student_tier", "disabled",
])
def test_pre_effect_refusals_do_not_write(env, monkeypatch, case):
    _seed_thread(env)
    if case == "student_tier":
        monkeypatch.setattr(
            "core.agent_radio.radio_config.radio_enabled", lambda: True)
    if case == "disabled":
        monkeypatch.setattr(
            "core.agent_radio.radio_config.radio_enabled", lambda: False)
    operation_id = f"op-radio-pre-{case}-{uuid.uuid4().hex}"
    args = _send_args(operation_id)
    context = _context(operation_id)
    if case == "missing_thread":
        args["thread_id"] = "missing-thread"
    elif case == "no_mentions":
        args["mention_agent_ids"] = []
    elif case == "student_tier":
        context["tier"] = "student"

    result = _call(_agent(), args, context)

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert result["status"] == "failed_before_effect", result
    assert result["effect_possible"] is False, result
    assert _message_rows(env) == []


# ---------------------------------------------------------------------------
# Durable same-operation replay / changed current material
# ---------------------------------------------------------------------------


def test_known_success_replays_exact_message_without_second_send(
        env, monkeypatch):
    _seed_thread(env)
    operation_id, args, context, first = _send_exact(env, monkeypatch)
    assert first["success"] is True, first
    assert len(_message_rows(env)) == 1

    second = _call(_agent(), dict(args), dict(context))

    assert len(_message_rows(env)) == 1, "the replay sent a second message"
    assert second["success"] is True, second
    assert second["action_result"] == "already_applied", second
    assert second.get("replayed") is True, second
    assert second["oracle_verified"] is True, second
    assert second["remote_id"] == first["remote_id"], second
    assert _claim_row(env, operation_id)[0] == "succeeded"


def test_restart_fresh_session_reloads_exact_message(env, monkeypatch):
    _seed_thread(env)
    operation_id, args, context, first = _send_exact(env, monkeypatch)
    message_id = first["remote_id"]

    env["engine"].dispose()
    reborn = _bind_scratch(monkeypatch, env["path"])
    second = _call(_agent(), dict(args), dict(context))

    assert len(_message_rows(reborn)) == 1, "restart replay sent a second message"
    assert second["success"] is True, second
    assert second["action_result"] == "already_applied", second
    assert second["oracle_verified"] is True, second
    assert second["remote_id"] == message_id, second


@pytest.mark.parametrize("change", [
    "content", "mentions", "to_agent_id", "requires_response", "tenant_id",
])
def test_replay_with_changed_current_material_is_committed_unverified(
        env, monkeypatch, change):
    _seed_thread(env)
    operation_id, args, context, first = _send_exact(env, monkeypatch)
    assert first["success"] is True, first
    from core.models import AgentThread, LateralMessage

    with env["Session"]() as db:
        if change == "tenant_id":
            db.query(AgentThread).filter(
                AgentThread.id == "thread-1").one().tenant_id = "tenant-other"
        else:
            message = db.query(LateralMessage).filter(
                LateralMessage.id == first["remote_id"]).one()
            if change == "content":
                message.content = "changed after send"
            elif change == "mentions":
                message.mentions = ["agent-c"]
            elif change == "to_agent_id":
                message.to_agent_id = "agent-c"
            elif change == "requires_response":
                message.metadata_json = {
                    "read_by": [], "is_response": False, "priority": "high"}
        db.commit()

    second = _call(_agent(), dict(args), dict(context))

    assert len(_message_rows(env)) == 1, "changed material was resent"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["action_result"] == "already_applied_unverified", second
    assert second["oracle_verified"] is False, second
    assert second["retryable"] is False, second


def test_replay_with_missing_message_is_committed_unverified(
        env, monkeypatch):
    _seed_thread(env)
    operation_id, args, context, first = _send_exact(env, monkeypatch)
    from core.models import LateralMessage

    with env["Session"]() as db:
        db.query(LateralMessage).filter(
            LateralMessage.id == first["remote_id"]).delete()
        db.commit()

    second = _call(_agent(), dict(args), dict(context))

    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["requires_reconciliation"] is True, second
    assert second["retryable"] is False, second


def test_changed_same_operation_material_refuses_before_send(env, monkeypatch):
    _seed_thread(env)
    operation_id, args, context, first = _send_exact(env, monkeypatch)
    assert first["success"] is True, first

    changed = dict(args)
    changed["content"] = "changed unapproved content"
    second = _call(_agent(), changed, dict(context))

    assert len(_message_rows(env)) == 1, "changed material reached the service"
    assert second["status"] == "conflict", second
    assert second["success"] is not True, second


# ---------------------------------------------------------------------------
# Readback/identity/unknown negatives
# ---------------------------------------------------------------------------


def test_wrong_readback_id_is_unverified(env, monkeypatch):
    _seed_thread(env)
    from core.agent_radio import radio_mutations

    def _wrong(_db, _message_id):
        return SimpleNamespace(
            id="other-message", thread_id="thread-1",
            from_agent_id="agent-a", to_agent_id=None,
            content="please review the checkout flow",
            mentions=["agent-b"], metadata_json={"read_by": []},
        )

    monkeypatch.setattr(radio_mutations, "read_message", _wrong)
    _op, _args, _ctx, result = _send_exact(env, monkeypatch)

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert "remote_id" in result["verification"]["mismatches"], result


def test_missing_readback_is_uncertain_not_success(env, monkeypatch):
    _seed_thread(env)
    from core.agent_radio import radio_mutations

    monkeypatch.setattr(
        radio_mutations, "read_message", lambda _db, _id: None)
    _op, _args, _ctx, result = _send_exact(env, monkeypatch)

    assert result["success"] is not True, result
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False, result
    assert len(_message_rows(env)) == 1


def test_unavailable_readback_is_uncertain_not_success(env, monkeypatch):
    _seed_thread(env)
    from core.agent_radio import radio_mutations

    def _unavailable(_db, _id):
        raise TimeoutError("readback timed out")

    monkeypatch.setattr(
        radio_mutations, "read_message", _unavailable)
    _op, _args, _ctx, result = _send_exact(env, monkeypatch)

    assert result["success"] is not True, result
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False, result
    assert len(_message_rows(env)) == 1


def test_unidentifiable_message_is_never_resent(env, monkeypatch):
    _seed_thread(env)
    from core.agent_radio import radio_service

    real_send = radio_service.send_message
    calls = []

    def _no_id(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(id="")

    monkeypatch.setattr(radio_service, "send_message", _no_id)
    operation_id = f"op-radio-no-id-{uuid.uuid4().hex}"
    args = _send_args(operation_id)
    context = _context(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is not True, first
    assert first["status"] == "uncertain", first
    assert first["remote_id"] == "", first

    second = _call(_agent(), dict(args), dict(context))
    assert second["success"] is not True, second
    assert second["status"] == "uncertain", second
    assert len(calls) == 1, "an unidentifiable send was retried"
    monkeypatch.setattr(radio_service, "send_message", real_send)


def test_lost_confirmation_is_uncertain_and_never_resent(env, monkeypatch):
    _seed_thread(env)
    from core.agent_radio import radio_service

    real_send = radio_service.send_message

    def _commit_then_raise(*args, **kwargs):
        real_send(*args, **kwargs)
        raise TimeoutError("confirmation timed out")

    monkeypatch.setattr(radio_service, "send_message", _commit_then_raise)
    operation_id = f"op-radio-lost-{uuid.uuid4().hex}"
    args = _send_args(operation_id)
    context = _context(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is not True, first
    assert first["status"] == "uncertain", first
    assert len(_message_rows(env)) == 1

    second = _call(_agent(), dict(args), dict(context))
    assert second["success"] is not True, second
    assert second["status"] == "uncertain", second
    assert len(_message_rows(env)) == 1, "a lost confirmation was resent"
    monkeypatch.setattr(radio_service, "send_message", real_send)


def test_failed_identity_receipt_is_not_rolled_back_or_resent(
        env, monkeypatch):
    _seed_thread(env)
    from core import outbound_operation_claim as claims

    real_mark_status = claims.mark_status

    def _fail_success_receipt(record_id, status, **kwargs):
        if status == claims.SUCCEEDED:
            return False
        return real_mark_status(record_id, status, **kwargs)

    monkeypatch.setattr(claims, "mark_status", _fail_success_receipt)
    operation_id, args, context, first = _send_exact(env, monkeypatch)

    assert first["success"] is not True, first
    assert first["status"] == "uncertain", first
    assert first.get("identity_receipt_persisted") is False, first
    assert first.get("retryable") is False, first
    assert "not rolled back" in str(first.get("message") or "").lower()
    assert len(_message_rows(env)) == 1

    monkeypatch.setattr(claims, "mark_status", real_mark_status)
    second = _call(_agent(), dict(args), dict(context))
    assert second["success"] is not True, second
    assert second["status"] == "uncertain", second
    assert len(_message_rows(env)) == 1, "a failed identity receipt was resent"
