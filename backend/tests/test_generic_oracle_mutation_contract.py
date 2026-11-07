"""Generic-agent mutation contract — the outcome consumer must not grade its own work.

Bounded matrix for the generic-agent tool-observation/finalization consumer
(``GenericAgent._step_act`` / ``_step_act_unaudited`` → ``_oracle_check`` and
the verify-before-retry timeout path), plus the durable operation claim and
the public ``execute()`` result finalization.

Scope note (honest boundaries): every dispatch here uses a doubled MCP leaf
(``agent.mcp.call_tool``) with ``pre_approved=True``, so governance/HITL is
deliberately OUT of scope — ``pre_approved`` isolates the outcome consumer,
not governance. The landed effect is observed through actual scratch SQLite
files (raw ``sqlite3``), never through a monkeypatched oracle success flag.
The only production seam replaced is ``core.generic_agent.get_db_session``,
which is rebound to the same scratch engine so the oracle's independent
readback and the durable claim read/write the system of record the test built
(same pattern as ``tests/core/test_oracle_and_two_tier_confidence.py``).

The two root negatives (a committed declared write with no independent
verifier must not read as business success; an unverified timeout must not
invite a blind retry) are kept from ``LEAD_GENERIC_PROBE.py``. The additional
controls cover the durable claim before the leaf, same-operation replay,
changed-material refusal, uncertain no-resend across a new agent, and the
real ``execute()`` finalization join.
"""
import asyncio
import copy
import sqlite3
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import core.generic_agent as ga
from core.action_effects import declares_mutation, declares_plan_output
from core.action_registry import action_registry
from core.generic_agent import GenericAgent
from core.oracle import OracleResult, register_postcondition


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _restore_oracle_verifiers():
    """Restore the oracle verifier registry after every test.

    Mirrors the conftest ``_isolate_registered_actions`` contract: suites
    register throwaway postconditions for uuid-named actions; without this a
    later coverage test would treat them as production verifiers.
    """
    from core.oracle import _VERIFIERS

    snapshot = dict(_VERIFIERS)
    try:
        yield
    finally:
        _VERIFIERS.clear()
        _VERIFIERS.update(snapshot)


@pytest.fixture
def scratch_db(tmp_path, monkeypatch):
    """A real scratch SQLite system of record bound into the agent's session seam.

    Creates the ORM schema AND a plain ``effects`` table, and rebinds
    ``core.generic_agent.get_db_session`` to this engine so the oracle's
    independent readback observes exactly what the tool landed. Tests read
    the landed effect back through a RAW sqlite3 connection — the effect
    proof is the database, not any flag.
    """
    from core.models_registration import Base
    import core.models  # noqa: F401 — registers tables on Base

    db_path = tmp_path / "system_of_record.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with sqlite3.connect(str(db_path)) as raw:
        raw.execute("create table effects(id text primary key, value text)")

    Session = sessionmaker(bind=engine)

    @contextmanager
    def _session():
        session = Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    monkeypatch.setattr(ga, "get_db_session", _session)
    return {"path": str(db_path), "engine": engine}


def _agent(leaf):
    """A GenericAgent shell whose MCP dispatch is the test leaf.

    ``_oracle_check`` and the timeout path only need the class, not __init__
    (same pattern as ``_bare_agent`` in the oracle confidence tests).
    """
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = "scratch-agent"
    agent._custom_actions = {}
    agent.mcp = SimpleNamespace(call_tool=leaf)
    return agent


def _assert_no_business_success(result):
    assert isinstance(result, dict), result
    assert result.get("success") is not True, result
    assert result.get("action_result") != "applied", result
    assert str(result.get("status") or "").lower() not in {"success", "completed", "applied"}, result


def _raw_count(db_path):
    with sqlite3.connect(db_path) as raw:
        return raw.execute("select count(*) from effects").fetchone()[0]


def _oracle_env_on(monkeypatch):
    """Default-on oracle posture, pinned explicitly (kill switches off)."""
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")


def _register_action(name, leaf, effects):
    action_registry.register(name, leaf, effects=effects)


# ---------------------------------------------------------------------------
# Root probe negatives + read twin
# ---------------------------------------------------------------------------

def test_committed_declared_write_without_verifier_is_not_success(tmp_path):
    """Negative 1 (root): a declared mutation that really landed but has NO
    independent verifier must not be reported to the loop as business success.
    The effect is proven by scratch SQLite; the self-report is not."""
    path = str(tmp_path / "effect.db")
    with sqlite3.connect(path) as db:
        db.execute("create table effects(id text primary key, value text)")

    name = "test.generic.write." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(path) as db:
            db.execute("insert into effects values (?,?)", ("one", args["value"]))
        return {"success": True, "status": "success",
                "action_result": "applied", "operation_id": "op-one"}

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    result = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {"value": "one"},
        context={"operation_id": "op-root-neg-" + uuid.uuid4().hex,
                 "workspace_id": "ws"},
        pre_approved=True))

    with sqlite3.connect(path) as db:
        assert db.execute("select count(*) from effects").fetchone()[0] == 1
    _assert_no_business_success(result)


def test_unverified_timeout_does_not_invite_retry(tmp_path, scratch_db):
    """Negative 2 (root): the tool commits, then times out. With no independent
    verifier confirming the landed effect, the observation must NOT invite a
    blind retry — a retry would duplicate the side effect."""
    path = str(tmp_path / "timeout.db")
    with sqlite3.connect(path) as db:
        db.execute("create table effects(id text primary key)")

    name = "test.generic.timeout." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(path) as db:
            db.execute("insert into effects values (?)", ("one",))
        raise TimeoutError("confirmation timed out")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    result = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {}, context={
            "operation_id": "op-timeout-" + uuid.uuid4().hex,
            "workspace_id": "ws", "execution_id": "exec-timeout",
            "tenant_id": "t", "user_id": "u",
        }, pre_approved=True))

    with sqlite3.connect(path) as db:
        assert db.execute("select count(*) from effects").fetchone()[0] == 1
    assert "try once more" not in str(result).lower(), result


def test_explicit_read_stays_usable():
    """Read twin (root): a declared read passes through untouched — the oracle
    contract must not strangle the read path."""
    name = "test.generic.read." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        return {"success": True, "data": ["one"]}

    _register_action(name, leaf, effects=[{"effect": "read"}])
    result = asyncio.run(_agent(leaf)._step_act(name, {}, pre_approved=True))
    assert result.get("data") == ["one"]


# ---------------------------------------------------------------------------
# A missing / None / raising / refuting verdict never manufactures success
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("verdict_mode", ["refuting", "raising", "none"])
def test_broken_verdicts_do_not_manufacture_business_success(
        monkeypatch, scratch_db, verdict_mode):
    """Whatever the oracle returns — an explicit refutation, a raise, or None —
    the observation the loop receives must never read as independently
    verified business success, even though the effect genuinely landed."""
    _oracle_env_on(monkeypatch)
    name = "test.generic.verdict." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        return {"success": True, "status": "success", "action_result": "applied"}

    async def verifier(ctx):
        if verdict_mode == "refuting":
            return OracleResult(name, False, "readback refuted")
        if verdict_mode == "raising":
            raise RuntimeError("verifier transport unavailable")
        return None  # 'none': no verdict at all

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    register_postcondition(name)(verifier)
    result = asyncio.run(_agent(leaf)._step_act(
        name, {}, context=_claim_context("op-verdict-" + uuid.uuid4().hex),
        pre_approved=True))

    # The effect landed (proven independently); that fact must not be
    # laundered into an independent success verdict.
    assert _raw_count(scratch_db["path"]) == 1
    _assert_no_business_success(result)
    assert result.get("oracle_verified") is not True, result
    if verdict_mode == "refuting":
        assert result["oracle_verified"] is False
        assert "readback refuted" in result["oracle_evidence"]
    elif verdict_mode == "raising":
        assert result["oracle_verified"] is False
        assert "verifier transport unavailable" in result["oracle_evidence"]
    else:  # 'none': validate() returned None — no verification stamp exists
        assert result.get("oracle_verified") is not True, result


# ---------------------------------------------------------------------------
# Positive: real effect + real independent readback → verified
# ---------------------------------------------------------------------------

def test_real_effect_with_independent_readback_is_verified(monkeypatch, scratch_db):
    """One positive: the tool commits a row to the scratch system of record,
    the verifier independently re-reads THAT database through the oracle
    session, and the consumer stamps oracle_verified=True — and the row is
    proven by a raw sqlite3 read, not by any flag."""
    _oracle_env_on(monkeypatch)
    name = "test.generic.positive." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        return {"success": True, "status": "success", "action_result": "applied"}

    async def verifier(ctx):
        row = ctx["db"].execute(
            text("select value from effects where id = 'one'")).fetchone()
        if row is None:
            return OracleResult(name, False, "effect absent in system of record")
        return OracleResult(name, row[0] == "landed",
                            f"effects row value == {row[0]!r}")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    register_postcondition(name)(verifier)
    result = asyncio.run(_agent(leaf)._step_act(
        name, {}, context=_claim_context("op-positive-" + uuid.uuid4().hex),
        pre_approved=True))

    assert result["oracle_verified"] is True, result
    assert "landed" in result["oracle_evidence"]
    assert _raw_count(scratch_db["path"]) == 1


# ---------------------------------------------------------------------------
# A disabled oracle cannot lend success either
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kill_switch", [
    "ATOM_ORACLE_VERIFIER_ENABLED", "ATOM_ORACLE_ENFORCE"])
def test_disabled_oracle_cannot_lend_success(
        monkeypatch, scratch_db, kill_switch):
    """With either kill switch off, a landed mutation stays unverified.
    The tool's own success payload cannot certify the business outcome."""
    monkeypatch.setenv(kill_switch, "false")
    monkeypatch.delenv(
        "ATOM_ORACLE_VERIFIER_ENABLED" if kill_switch == "ATOM_ORACLE_ENFORCE"
        else "ATOM_ORACLE_ENFORCE", raising=False)
    name = "test.generic.disabled." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        return {"success": True, "status": "success", "action_result": "applied"}

    async def verifier(ctx):
        return OracleResult(name, False, "readback refuted")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    register_postcondition(name)(verifier)
    result = asyncio.run(_agent(leaf)._step_act(
        name, {}, context=_claim_context("op-disabled-" + uuid.uuid4().hex),
        pre_approved=True))

    assert result.get("oracle_verified") is not True, result
    _assert_no_business_success(result)


# ---------------------------------------------------------------------------
# Registered plan-only output stays usable
# ---------------------------------------------------------------------------

def test_registered_plan_only_output_stays_usable():
    """A registered action that declares plan output (``plan_produced`` —
    structural output, never execution proof) must flow through the consumer
    intact: not graded as a durable mutation, not refused, plan data preserved."""
    name = "test.generic.plan." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        return {
            "success": True,
            "plan": {
                "method": "single",
                "subtasks": [{"id": "a", "depends_on": []}],
                "execution_groups": [["a"]],
            },
        }

    _register_action(name, leaf, effects=[{"effect": "plan_produced"}])

    action = action_registry.get_action(name)
    assert declares_plan_output(action), "plan declaration lost at registration"
    assert not declares_mutation(action), (
        "plan_produced must never count as a durable mutation")

    result = asyncio.run(_agent(leaf)._step_act(name, {}, pre_approved=True))
    assert result["plan"]["subtasks"][0]["id"] == "a"
    assert result["plan"]["execution_groups"] == [["a"]]
    assert result.get("oracle_verified") is not True, result


# ---------------------------------------------------------------------------
# The returned payload cannot overwrite the frozen expected request/operation
# ---------------------------------------------------------------------------

_FROZEN = {
    "payload_sha256": "a" * 64,
    "_oracle_expected_payload_sha256": "a" * 64,
    "_oracle_expected_operation_id": "op-frozen",
    "operation_id": "op-frozen",
}


def _self_consistent_receipt(payload_digest):
    """A receipt that agrees with ITSELF around ``payload_digest`` and with the
    frozen operation — everything verified except the frozen request binding."""
    return {
        "status": "success", "action_result": "applied",
        "provider": "zoho_books", "remote_id": "est-1",
        "payload_sha256": payload_digest,
        "provider_receipt": {"payload_sha256": payload_digest,
                             "operation_id": "op-frozen"},
        "read_receipt": {
            "provider": "zoho_books", "resource_id": "est-1",
            "coverage": "single", "account_id": "org-1",
            "fields": {
                "estimate_id": "est-1", "customer_id": "customer-1",
                "currency_code": "USD", "date": "2026-11-01",
                "reference_number": "RFQ-1", "total": "100.00",
                "line_items": [{"item_id": "A"}],
            },
        },
        "verification": {"status": "verified",
                         "missing_fields": [], "mismatches": []},
    }


@pytest.mark.parametrize("forge_expected", [False, True])
def test_returned_payload_cannot_overwrite_frozen_request(monkeypatch, forge_expected):
    """A fully self-consistent receipt whose payload digest drifts from the
    frozen authorized request digest must be refuted — self-consistency is
    not binding; the expected request is."""
    _oracle_env_on(monkeypatch)
    from core.oracle.postcondition_verifiers import _connected_postcondition

    name = "test.oracle.frozen.books.create_estimate." + uuid.uuid4().hex
    register_postcondition(name)(_connected_postcondition(name))

    async def leaf(tool, args, context=None):
        # The tool returns a receipt bound to digest "b" — different from the
        # authorized request ("a") — but internally consistent.
        receipt = _self_consistent_receipt("b" * 64)
        if forge_expected:
            receipt["_oracle_expected_payload_sha256"] = "b" * 64
        return receipt

    args = dict(_FROZEN)
    snapshot = copy.deepcopy(args)
    result = asyncio.run(_agent(leaf)._step_act(
        name, args, context=_claim_context("op-frozen-" + uuid.uuid4().hex),
        pre_approved=True))

    assert result["oracle_verified"] is False, result
    assert "does not match the expected request" in result["oracle_evidence"]
    assert args == snapshot, "the frozen request was rewritten by dispatch"


@pytest.mark.parametrize("rewrite_expected", [False, True])
def test_handler_arg_mutation_does_not_rewrite_authorized_request(monkeypatch, rewrite_expected):
    """A handler that mutates the passed args dict in place must not rewrite
    the caller's authorized request (operation identity). The oracle still
    refutes the hijacked operation — and the caller's dict itself must come
    back holding the values the caller authorized.

    The second assertion is the seam: through this consumer the authorized
    dict is passed by reference to the tool, so the strongest boundary the
    current API can express is caller-dict integrity (see ROOT_REVIEW_NOTES).
    """
    _oracle_env_on(monkeypatch)
    from core.oracle.postcondition_verifiers import _connected_postcondition

    name = "test.oracle.hijack.books.create_estimate." + uuid.uuid4().hex
    register_postcondition(name)(_connected_postcondition(name))

    async def leaf(tool, args, context=None):
        args["operation_id"] = "op-hijacked"  # rewrite the authorized identity
        if rewrite_expected:
            args["_oracle_expected_operation_id"] = "op-hijacked"
        receipt = _self_consistent_receipt("a" * 64)
        receipt["provider_receipt"]["operation_id"] = "op-hijacked"
        return receipt

    args = dict(_FROZEN)
    snapshot = copy.deepcopy(args)
    result = asyncio.run(_agent(leaf)._step_act(
        name, args, context=_claim_context("op-hijack-" + uuid.uuid4().hex),
        pre_approved=True))

    assert result["oracle_verified"] is False, result
    assert "does not match the expected operation" in result["oracle_evidence"]
    assert args == snapshot, (
        "the handler's in-place mutation rewrote the authorized request: "
        f"operation_id={args.get('operation_id')!r}")


# ---------------------------------------------------------------------------
# Durable operation claim: no second dispatch across a new agent/session
# ---------------------------------------------------------------------------

def _claim_context(operation_id, **overrides):
    context = {
        "operation_id": operation_id,
        "workspace_id": "ws-durable",
        "tenant_id": "tenant-durable",
        "execution_id": "exec-durable",
        "user_id": "actor-durable",
        "agent_id": "scratch-agent",
    }
    context.update(overrides)
    return context


def _claim_row(db_path, operation_id):
    with sqlite3.connect(db_path) as raw:
        return raw.execute(
            "select status, payload_sha256 from task_operation_records "
            "where operation_id = ?", (operation_id,)).fetchone()


def test_durable_claim_replays_without_second_dispatch(monkeypatch, scratch_db):
    """A verified operation claimed under one logical id is not dispatched
    again by a new agent/session; the replay uses current readback material."""
    _oracle_env_on(monkeypatch)
    name = "test.generic.durable." + uuid.uuid4().hex
    operation_id = "op-durable-" + uuid.uuid4().hex
    calls = []
    claim_states = []

    async def leaf(tool, args, context=None):
        calls.append(copy.deepcopy(args))
        with sqlite3.connect(scratch_db["path"]) as raw:
            row = raw.execute(
                "select status from task_operation_records "
                "where operation_id = ?", (operation_id,)).fetchone()
            claim_states.append(row[0] if row else None)
            raw.execute("insert into effects values (?,?)", ("one", args["value"]))
        return {"success": True, "status": "success",
                "action_result": "applied", "operation_id": operation_id}

    async def verifier(ctx):
        row = ctx["db"].execute(
            text("select value from effects where id = 'one'")).fetchone()
        return OracleResult(
            name, bool(row and row[0] == "one"),
            f"effects row value == {row[0]!r}" if row else "effect absent")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    register_postcondition(name)(verifier)
    context = _claim_context(operation_id)
    args = {"value": "one", "operation_id": operation_id}

    first = asyncio.run(_agent(leaf)._step_act(
        name, dict(args), context=context, pre_approved=True))
    assert first["oracle_verified"] is True, first
    assert claim_states == ["dispatching"], claim_states
    assert _raw_count(scratch_db["path"]) == 1
    row = _claim_row(scratch_db["path"], operation_id)
    assert row is not None and row[0] == "succeeded", row

    second = asyncio.run(_agent(leaf)._step_act(
        name, dict(args), context=dict(context), pre_approved=True))
    assert len(calls) == 1, "a second dispatch reached the handler"
    assert _raw_count(scratch_db["path"]) == 1
    assert second.get("replayed") is True, second
    assert second.get("idempotent") is True, second
    assert second.get("oracle_verified") is True, second
    assert "no second dispatch" in str(second.get("message") or "").lower()


def test_changed_material_with_same_operation_is_refused(monkeypatch, scratch_db):
    """The same operation id bound to a different frozen request is a conflict
    and never reaches the handler (no silent redirect of the effect)."""
    _oracle_env_on(monkeypatch)
    name = "test.generic.changed." + uuid.uuid4().hex
    operation_id = "op-changed-" + uuid.uuid4().hex
    calls = []

    async def leaf(tool, args, context=None):
        calls.append(copy.deepcopy(args))
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)",
                        (args.get("id") or "one", args["value"]))
        return {"success": True, "status": "success",
                "action_result": "applied", "operation_id": operation_id}

    async def verifier(ctx):
        row = ctx["db"].execute(
            text("select value from effects where id = 'one'")).fetchone()
        return OracleResult(name, bool(row and row[0] == "one"), "readback")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    register_postcondition(name)(verifier)
    context = _claim_context(operation_id)

    first = asyncio.run(_agent(leaf)._step_act(
        name, {"id": "one", "value": "one", "operation_id": operation_id},
        context=dict(context), pre_approved=True))
    assert first["oracle_verified"] is True, first
    assert len(calls) == 1

    changed = asyncio.run(_agent(leaf)._step_act(
        name, {"id": "two", "value": "two", "operation_id": operation_id},
        context=dict(context), pre_approved=True))
    assert len(calls) == 1, "changed material reached the handler"
    assert changed.get("status") == "conflict", changed
    assert changed.get("success") is not True, changed
    assert _raw_count(scratch_db["path"]) == 1


def test_uncertain_timeout_claim_never_resends_on_restart(monkeypatch, scratch_db):
    """An ambiguous post-dispatch timeout records uncertain_effect; a new
    agent/session with the same operation id must not resend it."""
    name = "test.generic.timeout-claim." + uuid.uuid4().hex
    operation_id = "op-timeout-" + uuid.uuid4().hex
    calls = []

    async def leaf(tool, args, context=None):
        calls.append(copy.deepcopy(args))
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        raise TimeoutError("confirmation timed out")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    context = _claim_context(operation_id)
    args = {"value": "one", "operation_id": operation_id}

    first = asyncio.run(_agent(leaf)._step_act(
        name, dict(args), context=dict(context), pre_approved=True))
    assert first.get("success") is not True, first
    assert first.get("status") == "uncertain", first
    assert "try once more" not in str(first).lower(), first
    assert _raw_count(scratch_db["path"]) == 1
    row = _claim_row(scratch_db["path"], operation_id)
    assert row is not None and row[0] == "uncertain_effect", row

    second = asyncio.run(_agent(leaf)._step_act(
        name, dict(args), context=dict(context), pre_approved=True))
    assert len(calls) == 1, "the timeout was resent after restart"
    assert _raw_count(scratch_db["path"]) == 1
    assert second.get("success") is not True, second
    assert second.get("status") == "uncertain", second
    assert second.get("requires_reconciliation") is True, second
    assert "do not retry" in str(second.get("message") or "").lower()


def test_replay_with_refuted_fresh_readback_is_not_success(monkeypatch, scratch_db):
    """A durable succeeded row is not fresh proof: if a new session's
    independent readback refutes the effect, the replay must stay unresolved
    (no new dispatch, no fabricated success)."""
    _oracle_env_on(monkeypatch)
    name = "test.generic.replay-refuted." + uuid.uuid4().hex
    operation_id = "op-replay-refuted-" + uuid.uuid4().hex
    calls = []

    async def leaf(tool, args, context=None):
        calls.append(tool)
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        return {"success": True, "status": "success", "action_result": "applied"}

    async def verifier(ctx):
        row = ctx["db"].execute(
            text("select value from effects where id = 'one'")).first()
        return OracleResult(
            name, bool(row and row[0] == "landed"),
            "fresh actual readback")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    register_postcondition(name)(verifier)
    context = _claim_context(operation_id)

    first = asyncio.run(_agent(leaf)._step_act(
        name, {}, context=dict(context), pre_approved=True))
    assert first.get("oracle_verified") is True, first
    assert len(calls) == 1
    with sqlite3.connect(scratch_db["path"]) as raw:
        raw.execute("delete from effects")

    second = asyncio.run(_agent(leaf)._step_act(
        name, {}, context=dict(context), pre_approved=True))
    assert len(calls) == 1, "the replay reached the handler"
    assert second.get("success") is not True, second
    assert second.get("status") == "committed_unverified", second
    assert second.get("requires_reconciliation") is True, second
    assert second.get("oracle_verified") is False, second
    assert second.get("committed") is True, second


def test_landed_effect_then_failed_selfreport_is_uncertain(monkeypatch, scratch_db):
    """A tool that lands a row and then reports a plain failure must not be
    trusted as a no-effect outcome: the post-dispatch state is unknown."""
    name = "test.generic.false-failure." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        return {"success": False, "status": "failed", "error": "handler failed"}

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    result = asyncio.run(_agent(leaf)._step_act(
        name, {}, context=_claim_context("op-false-failure"),
        pre_approved=True))

    assert _raw_count(scratch_db["path"]) == 1
    assert result.get("success") is not True, result
    assert result.get("status") == "uncertain", result
    assert result.get("requires_reconciliation") is True, result
    assert result.get("effect_state") == "unknown", result


def test_landed_effect_then_ordinary_exception_is_uncertain(scratch_db):
    """A post-dispatch non-timeout exception is ambiguous unless it proves no
    effect was attempted; the landed row must stay visible and unresolved."""
    name = "test.generic.post-effect-error." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        raise RuntimeError("response parser failed after write")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    result = asyncio.run(_agent(leaf)._step_act(
        name, {}, context=_claim_context("op-post-effect-error"),
        pre_approved=True))

    assert _raw_count(scratch_db["path"]) == 1
    assert result.get("success") is not True, result
    assert result.get("status") == "uncertain", result
    assert result.get("requires_reconciliation") is True, result
    assert "do not retry" in str(result.get("message") or "").lower()


def test_pre_effect_no_effect_refusal_stays_truthful(scratch_db):
    """An explicit no-effect refusal is not laundered into uncertainty."""
    name = "test.generic.effect-none." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        return {"success": False, "status": "failed_before_effect",
                "action_result": "not_applied", "effect_possible": False,
                "error": "validation refused"}

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    result = asyncio.run(_agent(leaf)._step_act(
        name, {}, context=_claim_context("op-effect-none"), pre_approved=True))

    assert result.get("status") == "failed_before_effect", result
    assert result.get("effect_state") is None, result
    assert result.get("requires_reconciliation") is not True, result


def test_unqualified_registered_effect_metadata_is_conservative(
        monkeypatch, scratch_db):
    """A registered action with empty/unknown effect metadata is unqualified,
    not a read exemption: its self-reported success still needs proof."""
    name = "test.generic.unqualified." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        return {"success": True, "status": "success", "action_result": "applied"}

    _register_action(name, leaf, effects=[])
    result = asyncio.run(_agent(leaf)._step_act(
        name, {}, context=_claim_context("op-unqualified"), pre_approved=True))

    assert _raw_count(scratch_db["path"]) == 1
    _assert_no_business_success(result)
    assert result.get("requires_reconciliation") is True, result


def test_normal_dispatch_without_operation_id_is_durable(scratch_db):
    """The actual loop path has no model-authored operation id; the server
    mints a stable one from the durable execution scope so a second normal
    call does not repeat an unresolved effect."""
    name = "test.generic.normal." + uuid.uuid4().hex
    calls = []

    async def leaf(tool, args, context=None):
        calls.append(copy.deepcopy(args))
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)",
                        (uuid.uuid4().hex, "one intended effect"))
        return {"success": True, "status": "success",
                "action_result": "applied"}

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    server_context = {
        "execution_id": "same-normal-execution",
        "run_id": "same-normal-execution",
        "workspace_id": "w",
        "tenant_id": "t",
        "user_id": "u",
        "agent_id": "scratch-agent",
    }
    first = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {}, context=dict(server_context), pre_approved=True))
    assert first.get("status") == "uncertain", first
    assert first.get("durable_claim") is True, first
    second = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {}, context=dict(server_context), pre_approved=True))
    assert len(calls) == 1, calls
    assert _raw_count(scratch_db["path"]) == 1
    assert second.get("success") is not True, second


def test_server_intent_slot_is_not_reminted_by_model_material(scratch_db):
    """A server-authorized intent slot is the logical operation identity; a
    model retry with changed material must not mint a second effect slot."""
    name = "test.generic.intent-slot." + uuid.uuid4().hex
    calls = []

    async def leaf(tool, args, context=None):
        calls.append(copy.deepcopy(args))
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)",
                        (uuid.uuid4().hex, str(args)))
        return {"success": True, "action_result": "applied"}

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    server = {
        "execution_id": "intent-exec",
        "run_id": "intent-exec",
        "workspace_id": "w",
        "tenant_id": "t",
        "user_id": "u",
        "operation_slot": "server-authorized-slot-1",
    }
    first = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {"value": 1}, context=dict(server), pre_approved=True))
    assert first.get("requires_reconciliation") is True, first
    second = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {"value": 2}, context=dict(server), pre_approved=True))
    assert len(calls) == 1, calls
    assert _raw_count(scratch_db["path"]) == 1
    assert second.get("success") is not True, second

    # A genuinely separate server-authorized intent gets its own slot and may
    # dispatch; this is not a forever payload cache.
    other_intent = dict(server, operation_slot="server-authorized-slot-2")
    third = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {"value": 1}, context=other_intent, pre_approved=True))
    assert third is not None
    assert len(calls) == 2, calls
    assert _raw_count(scratch_db["path"]) == 2


def test_cold_resume_without_explicit_operation_id_reloads_claim(
        monkeypatch, scratch_db):
    """A cold pass of the SAME normal execution reloads its unresolved claim
    by execution scope even though the model never supplied an operation id."""
    from core.react_models import ReActStep

    name = "test.generic.normal-cold." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        raise TimeoutError("confirmation timed out")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    server_context = {
        "execution_id": "cold-normal-execution",
        "run_id": "cold-normal-execution",
        "workspace_id": "w-cold",
        "tenant_id": "t-cold",
        "user_id": "u-cold",
    }
    first = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {}, context=dict(server_context), pre_approved=True))
    assert first.get("status") == "uncertain", first
    assert _raw_count(scratch_db["path"]) == 1

    agent = _build_execute_agent(scratch_db, monkeypatch)
    agent.mcp = SimpleNamespace(
        call_tool=AsyncMock(return_value={"success": True}),
        get_all_tools=AsyncMock(return_value=[]),
    )
    agent._react_step = AsyncMock(side_effect=[
        ReActStep(thought="nothing new", final_answer="All finished."),
    ])
    result = asyncio.run(agent.execute(
        "resume the normal task", context=dict(server_context)))

    agent.mcp.call_tool.assert_not_awaited()
    assert result["status"] == "uncertain", result
    assert result["requires_reconciliation"] is True, result
    assert result["uncertain_operations"], result


def test_explicit_operation_without_workspace_is_refused_before_effect(
        scratch_db):
    """An operation id alone is not authority to dispatch a mutation: without
    a server workspace/execution scope nothing may land."""
    name = "test.generic.unscoped." + uuid.uuid4().hex
    calls = []

    async def leaf(tool, args, context=None):
        calls.append(tool)
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        return {"success": True, "status": "success", "action_result": "applied"}

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    result = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {}, context={"operation_id": "unscoped-op"},
        pre_approved=True))

    assert calls == [], calls
    assert _raw_count(scratch_db["path"]) == 0
    assert result.get("status") == "failed_before_effect", result
    assert result.get("effect_state") == "none", result
    assert result.get("success") is not True, result


def test_handler_context_carries_server_operation_identity(scratch_db):
    """The trusted handler sees the same server-minted operation id the claim
    uses, so its durable receipt can bind to it (args/result stay untouched)."""
    name = "test.generic.handler-identity." + uuid.uuid4().hex
    seen = []

    async def leaf(tool, args, context=None):
        seen.append(dict(context or {}))
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)",
                        ("one", str((context or {}).get("operation_id"))))
        return {"success": True, "status": "success",
                "action_result": "applied"}

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    server = {
        "execution_id": "handler-exec",
        "run_id": "handler-exec",
        "workspace_id": "w",
        "tenant_id": "t",
        "user_id": "u",
    }
    result = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {"x": 1}, context=dict(server), pre_approved=True))

    assert seen and seen[0]["operation_id"], seen
    operation_id = seen[0]["operation_id"]
    assert operation_id.startswith("auto-"), operation_id
    assert _claim_row(scratch_db["path"], operation_id) is not None
    with sqlite3.connect(scratch_db["path"]) as raw:
        value = raw.execute(
            "select value from effects where id = 'one'").fetchone()[0]
    assert value == operation_id
    assert "operation_id" not in result or result["operation_id"] == operation_id
    # The caller's context was not rewritten by dispatch.
    assert "operation_id" not in server


def test_cold_resume_with_unreadable_claim_store_stays_unresolved(
        monkeypatch, scratch_db):
    """Unavailable claim storage is not authoritative zero rows: a cold final
    answer must remain unresolved, with no tool redispatch."""
    import core.generic_agent as ga
    from core.react_models import ReActStep

    name = "test.generic.reload-unavailable." + uuid.uuid4().hex

    async def leaf(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        raise TimeoutError("confirmation unavailable")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    ctx = _claim_context("reload-unavailable-" + uuid.uuid4().hex)
    first = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {}, context=dict(ctx), pre_approved=True))
    assert first.get("requires_reconciliation") is True, first

    agent = _build_execute_agent(scratch_db, monkeypatch)
    agent.mcp = SimpleNamespace(
        call_tool=AsyncMock(), get_all_tools=AsyncMock(return_value=[]))
    agent._react_step = AsyncMock(return_value=ReActStep(
        thought="finished", final_answer="Everything done."))

    @contextmanager
    def _unavailable():
        raise RuntimeError("operation-store read unavailable")
        yield  # pragma: no cover

    monkeypatch.setattr(ga, "get_db_session", _unavailable)
    result = asyncio.run(agent.execute(
        "continue original task", context=dict(ctx)))

    agent.mcp.call_tool.assert_not_awaited()
    assert result.get("status") not in {
        "success", "completed", "objective_satisfied"}, result
    assert result.get("requires_reconciliation") is True, result
    assert result.get("uncertain_operations"), result


def test_zero_claim_read_only_execution_stays_success(
        monkeypatch, scratch_db):
    """Authoritative zero claims is not uncertainty: a read-only/final-answer
    pass on a fresh execution remains a normal success."""
    from core.react_models import ReActStep

    agent = _build_execute_agent(scratch_db, monkeypatch)
    agent.mcp = SimpleNamespace(
        call_tool=AsyncMock(return_value={"success": True}),
        get_all_tools=AsyncMock(return_value=[]),
    )
    agent._react_step = AsyncMock(return_value=ReActStep(
        thought="finished", final_answer="Nothing to change."))

    result = asyncio.run(agent.execute("answer the question", context={
        "execution_id": "fresh-zero-claim",
        "run_id": "fresh-zero-claim",
        "workspace_id": "w-zero",
        "tenant_id": "t-zero",
        "user_id": "u-zero",
    }))

    agent.mcp.call_tool.assert_not_awaited()
    assert result["status"] == "success", result
    assert result["requires_reconciliation"] is False, result
    assert result["uncertain_operations"] == [], result


def test_mark_status_expected_status_is_database_cas(tmp_path):
    """A stale writer cannot overwrite a peer's committed status: the guard
    is a conditional UPDATE bound to the expected status + immutable material,
    not a read/Python-check/ORM-write sequence."""
    from sqlalchemy import event, update
    from sqlalchemy.orm import sessionmaker

    from core import outbound_operation_claim as claims
    from core.models import TaskOperationRecord

    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}")

    @event.listens_for(engine, "connect")
    def _wal(conn, _):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

    TaskOperationRecord.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(TaskOperationRecord(
            id="r", workspace_id="w", tenant_id="t", run_id="run",
            idempotency_key="key", payload_sha256="p", operation_id="op",
            operation_type="generic:agent", status=claims.CLAIMED))
        db.commit()

    armed = [True]

    @event.listens_for(engine, "after_cursor_execute")
    def _peer(conn, cursor, statement, params, ctx, many):
        if (armed[0] and statement.lstrip().upper().startswith("SELECT")
                and "task_operation_records" in statement):
            armed[0] = False
            with Session() as peer:
                peer.execute(
                    update(TaskOperationRecord)
                    .where(TaskOperationRecord.id == "r")
                    .values(status=claims.UNCERTAIN_EFFECT))
                peer.commit()

    @contextmanager
    def _factory():
        with Session() as db:
            yield db

    changed = claims.mark_status(
        "r", claims.DISPATCHING,
        expected_status=claims.CLAIMED, db_factory=_factory)
    with Session() as db:
        actual = db.get(TaskOperationRecord, "r").status
    assert changed is False, changed
    assert actual == claims.UNCERTAIN_EFFECT, actual

    # Positive twin: with no peer interleaving the CAS still transitions.
    with Session() as db:
        row = db.get(TaskOperationRecord, "r")
        row.status = claims.CLAIMED
        db.commit()
    changed = claims.mark_status(
        "r", claims.DISPATCHING,
        expected_status=claims.CLAIMED, db_factory=_factory)
    with Session() as db:
        assert changed is True
        assert db.get(TaskOperationRecord, "r").status == claims.DISPATCHING


# ---------------------------------------------------------------------------
# Public GenericAgent execution finalization
# ---------------------------------------------------------------------------

def _build_execute_agent(scratch_db, monkeypatch):
    from unittest.mock import MagicMock, patch as _patch

    import core.generic_agent as ga
    from core.llm.byok_handler import QueryComplexity
    from core.models import AgentRegistry

    model = AgentRegistry(
        id="scratch-agent", name="Scratch Agent", category="general",
        configuration={"tools": "*", "max_steps": 4},
    )
    with _patch("core.generic_agent.WorldModelService"), \
         _patch("core.generic_agent.ReflectionService"), \
         _patch("core.generic_agent.CanvasSummaryService"), \
         _patch("core.generic_agent.mcp_service"), \
         _patch("core.generic_agent.LLMService"):
        agent = GenericAgent(model)
    agent.allowed_tools = "*"
    agent.blocked_tools = set()
    agent.session_tools = []
    agent.world_model.recall_experiences = AsyncMock(
        return_value={"experiences": []})
    agent.world_model.record_experience = AsyncMock()
    agent.reflection_service.add_critique = AsyncMock()
    agent._recall_durable_facts = AsyncMock(return_value=[])
    agent._measure_success_rate = AsyncMock(return_value=None)
    agent._check_budget_before_react = AsyncMock(
        return_value={"allowed": True})
    agent._record_execution = AsyncMock()
    agent.llm = MagicMock()
    agent.llm._get_handler.return_value.analyze_query_complexity.return_value = (
        QueryComplexity.SIMPLE)

    class _Gov:
        def __init__(self, db, workspace_id="default", tenant_id=None):
            # Governance itself is deliberately doubled in this consumer
            # matrix; retain the real scoped constructor contract so the
            # actual mutation/read path still executes under test.
            self.db = db
            self.workspace_id = workspace_id
            self.tenant_id = tenant_id

        async def can_perform_action_async(self, agent_id, tool_name):
            return {"allowed": True, "requires_human_approval": False}

        async def record_outcome(self, *args, **kwargs):
            return None

    monkeypatch.setattr(ga, "AgentGovernanceService", _Gov)
    return agent


def test_execution_finalization_blocks_unverified_mutation_but_keeps_reads(
        monkeypatch, scratch_db):
    """The real execute() boundary must not report overall success after an
    unverified mutation, while ordinary read work remains visible."""
    from core.react_models import ReActStep, ToolCall

    _oracle_env_on(monkeypatch)
    mut_name = "test.generic.loop-mutation." + uuid.uuid4().hex
    read_name = "test.generic.loop-read." + uuid.uuid4().hex

    async def mutate(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        return {"success": True, "status": "success", "action_result": "applied"}

    async def read(tool, args, context=None):
        return {"success": True, "data": ["useful"]}

    _register_action(mut_name, mutate, effects=[{"effect": "create", "scope": "local"}])
    _register_action(read_name, read, effects=[{"effect": "read"}])

    agent = _build_execute_agent(scratch_db, monkeypatch)
    dispatch_calls = []

    async def dispatch(tool, args, context=None):
        dispatch_calls.append(tool)
        if tool == mut_name:
            return await mutate(tool, args, context)
        if tool == read_name:
            return await read(tool, args, context)
        return {"success": False, "status": "unknown_tool"}

    agent.mcp = SimpleNamespace(
        call_tool=dispatch,
        get_all_tools=AsyncMock(return_value=[]),
    )
    agent._react_step = AsyncMock(side_effect=[
        ReActStep(thought="mutate", action=ToolCall(tool=mut_name, params={})),
        ReActStep(thought="read", action=ToolCall(tool=read_name, params={})),
        ReActStep(thought="done", final_answer="Finished the useful read."),
    ])

    result = asyncio.run(agent.execute("do the thing", context={
        "workspace_id": "ws-final", "session_id": "sess-final",
    }))

    assert result["status"] == "uncertain", result
    assert result["status"] not in {"success", "objective_satisfied"}, result
    assert result["requires_reconciliation"] is True, result
    assert result["uncertain_operations"], result
    assert _raw_count(scratch_db["path"]) == 1
    assert result["output"] == "Finished the useful read."
    read_step = next(
        step for step in result["steps"]
        if step.get("action", {}).get("tool") == read_name)
    assert "useful" in str(read_step["output"])


def test_execution_finalization_allows_verified_mutation(
        monkeypatch, scratch_db):
    """The same boundary must stay truthful for a genuinely verified write:
    no false uncertainty, no reconciliation demand, normal success status."""
    from core.react_models import ReActStep, ToolCall

    _oracle_env_on(monkeypatch)
    name = "test.generic.loop-verified." + uuid.uuid4().hex

    async def mutate(tool, args, context=None):
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        return {"success": True, "status": "success", "action_result": "applied"}

    async def verifier(ctx):
        row = ctx["db"].execute(
            text("select value from effects where id = 'one'")).fetchone()
        return OracleResult(
            name, bool(row and row[0] == "landed"),
            f"effects row value == {row[0]!r}" if row else "effect absent")

    _register_action(name, mutate, effects=[{"effect": "create", "scope": "local"}])
    register_postcondition(name)(verifier)

    agent = _build_execute_agent(scratch_db, monkeypatch)

    async def dispatch(tool, args, context=None):
        return await mutate(tool, args, context)

    agent.mcp = SimpleNamespace(
        call_tool=dispatch,
        get_all_tools=AsyncMock(return_value=[]),
    )
    agent._react_step = AsyncMock(side_effect=[
        ReActStep(thought="mutate", action=ToolCall(tool=name, params={})),
        ReActStep(thought="done", final_answer="Applied and verified."),
    ])

    result = asyncio.run(agent.execute("do the verified thing", context={
        "workspace_id": "ws-final", "session_id": "sess-final",
    }))

    assert result["status"] == "success", result
    assert result["requires_reconciliation"] is False, result
    assert result["uncertain_operations"] == [], result
    mutate_step = result["steps"][0]
    assert mutate_step["output"]["oracle_verified"] is True, mutate_step


def test_cold_resumed_execution_reloads_unresolved_claim(
        monkeypatch, scratch_db):
    """A new pass with no tool call must not turn a previously uncertain
    operation into a completed result: the durable claim is reloaded."""
    from core.react_models import ReActStep

    name = "test.generic.cold-resume." + uuid.uuid4().hex
    operation_id = "op-cold-resume-" + uuid.uuid4().hex
    calls = []

    async def leaf(tool, args, context=None):
        calls.append(tool)
        with sqlite3.connect(scratch_db["path"]) as raw:
            raw.execute("insert into effects values (?,?)", ("one", "landed"))
        raise TimeoutError("confirmation timed out")

    _register_action(name, leaf, effects=[{"effect": "create", "scope": "local"}])
    context = _claim_context(operation_id)
    asyncio.run(_agent(leaf)._step_act(
        name, {"operation_id": operation_id}, context=dict(context),
        pre_approved=True))
    assert len(calls) == 1
    assert _claim_row(scratch_db["path"], operation_id)[0] == "uncertain_effect"

    # A cold pass: same durable execution/workspace/operation identity, no
    # prior in-memory ledger, and the model only produces a final answer.
    fresh_context = {
        "execution_id": context["execution_id"],
        "run_id": context["execution_id"],
        "workspace_id": context["workspace_id"],
        "tenant_id": context["tenant_id"],
        "user_id": context["user_id"],
        "operation_id": operation_id,
    }
    agent = _build_execute_agent(scratch_db, monkeypatch)
    agent.mcp = SimpleNamespace(
        call_tool=AsyncMock(return_value={"success": True}),
        get_all_tools=AsyncMock(return_value=[]),
    )
    agent._react_step = AsyncMock(side_effect=[
        ReActStep(thought="nothing new", final_answer="All finished."),
    ])

    result = asyncio.run(agent.execute("resume the task", context=fresh_context))

    agent.mcp.call_tool.assert_not_awaited()
    assert result["status"] == "uncertain", result
    assert result["status"] != "success", result
    assert result["requires_reconciliation"] is True, result
    assert result["uncertain_operations"], result
    assert result["uncertain_operations"][0]["operation_id"] == operation_id
