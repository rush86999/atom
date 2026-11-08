"""Finite BPE note/commit outcome contract — failure-first + valid twins.

The confirmed root negative: a legitimate ``workspace.note`` append lands, but
the normal Generic consumer has no registered postcondition verifier, rewrites
the observation to ``uncertain``, marks the durable claim
``uncertain_effect``, and the episode close-out drains/drops the note. An empty
note is also relabelled ``uncertain`` instead of staying a proven pre-effect
refusal.

These controls exercise the PRODUCTION dispatch/claim/oracle/close-out path:

* real ``core.bpe.actions`` registration + real ``core.action_registry``;
* real ``GenericAgent._step_act_unaudited`` (``pre_approved=True`` isolates the
  outcome consumer — governance/HITL is deliberately out of scope, same
  boundary as ``tests/test_generic_oracle_mutation_contract.py``);
* real scratch SQLite ``task_operation_records`` claim store;
* real ``BPEWorkspace`` + real ``BPEWorkspaceStore`` under a fresh ``tmp_path``
  data root. The oracle re-loads the JSON file independently; no verdict flag
  is monkeypatched.

No model/server/browser/account/provider/credential is invoked. Root owns
execution; this module makes no self-acceptance claim.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generic_agent as ga
from core.action_registry import action_registry
from core.bpe import persistence as bpe_persistence
from core.bpe import workspace as bpe_workspace
from core.bpe.persistence import BPEWorkspaceStore
from core.generic_agent import GenericAgent
from core.oracle import get_postcondition, validate
from core.oracle.request_expectations import build_request_expectations

NOTE = "workspace.note"
COMMIT = "workspace.commit"
WS = "ws-bpe-outcome"
AGENT = "agent-bpe-outcome"
SESSION = "sess-bpe-outcome"
EXECUTION = "exec-bpe-outcome"
TENANT = "tenant-bpe-outcome"
ACTOR = "user-bpe-outcome"


@pytest.fixture(autouse=True)
def _bpe_env(monkeypatch):
    monkeypatch.setenv("ATOM_BPE_WORKSPACE_ENABLED", "true")
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    from core.bpe import actions as bpe_actions

    # The conftest autouse fixture restores the global action registry after
    # each case while this module import is cached; re-run the production
    # decorators so every control starts with workspace.* registered.
    importlib.reload(bpe_actions)
    bpe_workspace.reset_registry()
    try:
        yield
    finally:
        bpe_workspace.reset_registry()


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    """Fresh real SQLite system of record for the claim + oracle seams."""
    from core.models import Tenant, Workspace
    from core.models_registration import Base
    import core.models  # noqa: F401 — registers every table on Base

    db_path = tmp_path / "bpe_outcome_system_of_record.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session():
        session = Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    monkeypatch.setattr(ga, "get_db_session", _session)
    import core.database as core_database
    monkeypatch.setattr(core_database, "get_db_session", _session)

    with Session() as db:
        db.add(Tenant(
            id=TENANT,
            name="BPE outcome tenant",
            subdomain="bpe-outcome-scratch",
            plan_type="free",
            edition="personal",
        ))
        db.commit()
    with Session() as db:
        db.add(Workspace(id=WS, name="BPE outcome workspace", tenant_id=TENANT))
        db.commit()

    return {"path": str(db_path), "engine": engine, "Session": Session}


@pytest.fixture
def bpe_data(tmp_path, monkeypatch):
    data_dir = tmp_path / "bpe_workspaces"
    # DATA_DIR is read by BPEWorkspaceStore.__init__ at call time. Rebinding
    # the module root is isolation, not a fake persistence/readback verdict.
    monkeypatch.setattr(bpe_persistence, "DATA_DIR", data_dir)
    return data_dir


def _agent(leaf=None):
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = AGENT
    agent.workspace_id = WS
    agent.tenant_id = TENANT
    agent._custom_actions = {}

    async def registry_leaf(tool_name, arguments, context=None):
        return await action_registry.execute_action(
            tool_name, arguments, context or {})

    agent.mcp = SimpleNamespace(call_tool=leaf or registry_leaf)
    return agent


def _context(operation_id=None, **overrides):
    ctx = {
        "operation_id": operation_id or f"op-bpe-{uuid.uuid4().hex}",
        "workspace_id": WS,
        "tenant_id": TENANT,
        "execution_id": EXECUTION,
        "session_id": SESSION,
        "user_id": ACTOR,
        "agent_id": AGENT,
    }
    ctx.update(overrides)
    return ctx


def _dispatch(tool, arguments, context, agent=None):
    return asyncio.run((agent or _agent())._step_act_unaudited(
        tool, arguments, context=context, pre_approved=True))


def _snapshot():
    return bpe_workspace.get_workspace_snapshot(WS, AGENT, SESSION)


def _claim_row(db_path, operation_id):
    with sqlite3.connect(db_path) as raw:
        return raw.execute(
            "select status from task_operation_records "
            "where operation_id = ?", (operation_id,)).fetchone()


def _stored():
    return BPEWorkspaceStore().load(WS, AGENT, SESSION)


def _expected(action, arguments, operation_id, *, workspace=WS, agent=AGENT,
              scope_key=SESSION, actor=""):
    return build_request_expectations(
        action,
        arguments,
        operation_id=operation_id,
        tenant_id=TENANT,
        workspace_id=workspace,
        actor_id=ACTOR,
        agent_id=agent,
        bpe_scope={
            "workspace_id": workspace,
            "agent_id": agent,
            "scope_key": scope_key,
            "user_id": actor,
        },
    )


def _validate(action, expected):
    return asyncio.run(validate(action, dict(expected)))


# ---------------------------------------------------------------------------
# Primary failure-first: a landed note is verified and consolidated
# ---------------------------------------------------------------------------


def test_landed_note_is_independently_verified_then_consolidated(
        scratch, bpe_data):
    content = "checkout retry needs an idempotency key"
    operation_id = f"op-note-ok-{uuid.uuid4().hex}"
    context = _context(operation_id)
    result = _dispatch(NOTE, {"content": content}, context)

    # The note really landed in the exact scope.
    snapshot = _snapshot()
    assert snapshot is not None
    assert snapshot["pending_notes"] == [content]

    # The normal consumer must not relabel a landed, verified note.
    assert result.get("success") is True, result
    assert result.get("oracle_verified") is True, result
    assert result.get("requires_reconciliation") is not True, result
    assert str(result.get("status") or "success").lower() != "uncertain", result
    assert not context.get("_uncertain_operations"), context
    assert _claim_row(scratch["path"], operation_id)[0] == "succeeded"

    # The producer persisted a receipt bound to exact operation/scope/material.
    stored = _stored()
    assert stored is not None
    assert stored["pending_notes"] == [content]
    receipt = stored["operation_receipts"][0]
    assert receipt["action"] == NOTE
    assert receipt["operation_id"] == operation_id
    assert receipt["workspace_id"] == WS
    assert receipt["agent_id"] == AGENT
    assert receipt["scope_key"] == SESSION
    assert receipt["material"] == {"content": content}

    # The real close-out branch promotes the just-verified fact.
    from core.bpe.consolidation import consolidate_workspace_notes

    ws = bpe_workspace.get_workspace(WS, AGENT, SESSION)
    report = consolidate_workspace_notes(ws)
    assert report["skills"] == 1, report
    assert ws.experience.to_dict()["skills"][0]["content"] == content
    assert _snapshot()["pending_notes"] == []
    assert BPEWorkspaceStore().save(ws.to_dict()) is True

    restored = _stored()
    assert restored["pending_notes"] == []
    assert restored["experience"]["skills"][0]["content"] == content


# ---------------------------------------------------------------------------
# Empty / invalid material is a proven pre-effect refusal
# ---------------------------------------------------------------------------


def test_empty_note_is_a_pre_effect_refusal(scratch, bpe_data):
    operation_id = f"op-note-empty-{uuid.uuid4().hex}"
    context = _context(operation_id)
    result = _dispatch(NOTE, {"content": "   "}, context)

    snapshot = _snapshot()
    assert snapshot is None or snapshot["pending_notes"] == []
    assert result.get("success") is False, result
    assert result.get("action_result") == "not_applied", result
    assert result.get("effect_possible") is False, result
    assert str(result.get("status") or "").lower() != "uncertain", result
    assert result.get("requires_reconciliation") is not True, result
    assert not context.get("_uncertain_operations"), context
    assert _claim_row(scratch["path"], operation_id)[0] == "failed_before_effect"


def test_commit_without_title_or_with_invalid_status_is_pre_effect(scratch, bpe_data):
    empty_op = f"op-commit-empty-{uuid.uuid4().hex}"
    empty = _dispatch(COMMIT, {"title": "   "}, _context(empty_op))
    assert empty.get("success") is False, empty
    assert empty.get("action_result") == "not_applied", empty
    assert str(empty.get("status") or "").lower() != "uncertain", empty
    assert _claim_row(scratch["path"], empty_op)[0] == "failed_before_effect"

    invalid_op = f"op-commit-invalid-{uuid.uuid4().hex}"
    invalid = _dispatch(
        COMMIT, {"title": "ship it", "status": "finished"},
        _context(invalid_op))
    assert invalid.get("success") is False, invalid
    assert invalid.get("action_result") == "not_applied", invalid
    assert str(invalid.get("status") or "").lower() != "uncertain", invalid
    assert _claim_row(scratch["path"], invalid_op)[0] == "failed_before_effect"
    assert _snapshot() is None or _snapshot()["progress"] == []


# ---------------------------------------------------------------------------
# Registered shape + read twin
# ---------------------------------------------------------------------------


def test_registered_shape_and_read_twin_stay_usable(scratch, bpe_data):
    note = action_registry.get_action(NOTE)
    commit = action_registry.get_action(COMMIT)
    assert note is not None and commit is not None
    assert note.parameters_schema["required"] == ["content"]
    assert commit.parameters_schema["required"] == ["title"]
    assert get_postcondition(NOTE) is not None
    assert get_postcondition(COMMIT) is not None

    from core.bpe.adapter import NullAdapter

    bpe_workspace.get_workspace(WS, AGENT, SESSION).adapter = NullAdapter()
    operation_id = f"op-track-{uuid.uuid4().hex}"
    result = _dispatch(
        "workspace.track", {"topic": "world"}, _context(operation_id))
    assert result["success"] is True, result
    assert result.get("requires_reconciliation") is not True, result
    assert _claim_row(scratch["path"], operation_id) is None


# ---------------------------------------------------------------------------
# Prior / forged / contradictory proof cannot certify the request
# ---------------------------------------------------------------------------


def test_prior_same_content_without_this_operation_receipt_is_not_proof(
        scratch, bpe_data):
    content = "same insight"
    ws = bpe_workspace.BPEWorkspace(WS, AGENT, SESSION)
    ws._pending_notes.append(content)
    assert BPEWorkspaceStore().save(ws.to_dict()) is True

    expected = _expected(
        NOTE, {"content": content}, f"op-new-{uuid.uuid4().hex}")
    verdict = _validate(NOTE, expected)
    assert verdict.verified is False, verdict
    assert "no durable receipt" in verdict.evidence


def test_forged_result_echo_cannot_certify_without_durable_state(
        scratch, bpe_data):
    content = "forged echo"
    operation_id = f"op-forged-{uuid.uuid4().hex}"
    expected = _expected(NOTE, {"content": content}, operation_id)
    forged = dict(expected)
    forged.update({
        "success": True,
        "status": "success",
        "action_result": "applied",
        "oracle_verified": True,
        "operation_id": operation_id,
        "note_id": "fabricated",
        "material": {"content": content},
    })
    verdict = asyncio.run(validate(NOTE, forged))
    assert verdict.verified is False, verdict
    assert "no persisted BPE scope" in verdict.evidence


@pytest.mark.parametrize("field,value", [
    ("operation_id", "op-someone-else"),
    ("workspace_id", "ws-other"),
    ("agent_id", "agent-other"),
    ("scope_key", "sess-other"),
    ("actor_id", "user-other"),
])
def test_wrong_operation_scope_or_principal_receipt_is_refuted(
        scratch, bpe_data, field, value):
    content = "scope-bound insight"
    operation_id = f"op-scope-{uuid.uuid4().hex}"
    ws = bpe_workspace.BPEWorkspace(WS, AGENT, SESSION)
    ws._pending_notes.append(content)
    receipt = {
        "action": NOTE,
        "operation_id": operation_id,
        "workspace_id": WS,
        "agent_id": AGENT,
        "scope_key": SESSION,
        "actor_id": "",
        "material": {"content": content},
        "material_sha256": build_request_expectations(
            NOTE, {"content": content}, operation_id=operation_id,
            bpe_scope={
                "workspace_id": WS, "agent_id": AGENT,
                "scope_key": SESSION, "user_id": "",
            },
        )["_oracle_expected_bpe_material_sha256"],
        "created_at": 1.0,
    }
    receipt[field] = value
    ws.record_operation_receipt(receipt)
    assert BPEWorkspaceStore().save(ws.to_dict()) is True

    expected = _expected(NOTE, {"content": content}, operation_id)
    verdict = _validate(NOTE, expected)
    assert verdict.verified is False, verdict
    # A different operation id simply has no matching receipt; the other
    # fields are present but contradict the frozen binding.
    assert (
        "contradicts the frozen request" in verdict.evidence
        or "no durable receipt" in verdict.evidence
    )


def test_changed_material_for_same_operation_is_refuted(scratch, bpe_data):
    original = "original material"
    changed = "changed material"
    operation_id = f"op-material-{uuid.uuid4().hex}"
    ws = bpe_workspace.BPEWorkspace(WS, AGENT, SESSION)
    ws._pending_notes.append(original)
    expected_original = _expected(NOTE, {"content": original}, operation_id)
    ws.record_operation_receipt({
        "action": NOTE,
        "operation_id": operation_id,
        "workspace_id": WS,
        "agent_id": AGENT,
        "scope_key": SESSION,
        "actor_id": "",
        "material": {"content": original},
        "material_sha256": expected_original[
            "_oracle_expected_bpe_material_sha256"],
        "created_at": 1.0,
    })
    assert BPEWorkspaceStore().save(ws.to_dict()) is True

    changed_expected = _expected(NOTE, {"content": changed}, operation_id)
    verdict = _validate(NOTE, changed_expected)
    assert verdict.verified is False, verdict
    assert "material" in verdict.evidence


def test_partial_receipt_is_refuted(scratch, bpe_data):
    content = "partial proof"
    operation_id = f"op-partial-{uuid.uuid4().hex}"
    ws = bpe_workspace.BPEWorkspace(WS, AGENT, SESSION)
    ws._pending_notes.append(content)
    expected = _expected(NOTE, {"content": content}, operation_id)
    ws.record_operation_receipt({
        "action": NOTE,
        "operation_id": operation_id,
        "workspace_id": WS,
        # agent/scope/material deliberately absent
    })
    assert BPEWorkspaceStore().save(ws.to_dict()) is True
    verdict = _validate(NOTE, expected)
    assert verdict.verified is False, verdict
    assert "contradicts the frozen request" in verdict.evidence


def test_in_memory_only_state_is_not_durable_proof(scratch, bpe_data):
    content = "memory only"
    operation_id = f"op-memory-{uuid.uuid4().hex}"
    ws = bpe_workspace.get_workspace(WS, AGENT, SESSION)
    ws._pending_notes.append(content)
    ws.record_operation_receipt({
        "action": NOTE,
        "operation_id": operation_id,
        "workspace_id": WS,
        "agent_id": AGENT,
        "scope_key": SESSION,
        "actor_id": "",
        "material": {"content": content},
        "material_sha256": _expected(
            NOTE, {"content": content}, operation_id
        )["_oracle_expected_bpe_material_sha256"],
        "created_at": 1.0,
    })
    # Deliberately never persisted.
    expected = _expected(NOTE, {"content": content}, operation_id)
    verdict = _validate(NOTE, expected)
    assert verdict.verified is False, verdict
    assert "no persisted BPE scope" in verdict.evidence


# ---------------------------------------------------------------------------
# Persistence truth + exact replay
# ---------------------------------------------------------------------------


def test_persistence_failure_stays_uncertain_and_preserves_the_note(
        scratch, bpe_data, monkeypatch):
    content = "landed but not durably receipted"
    operation_id = f"op-persist-fail-{uuid.uuid4().hex}"

    def _fail_save(_self, _snapshot):
        return False

    monkeypatch.setattr(BPEWorkspaceStore, "save", _fail_save)
    result = _dispatch(NOTE, {"content": content}, _context(operation_id))

    # The handler appended in-process, but no durable proof exists, so the
    # consumer must not certify success.
    assert _snapshot()["pending_notes"] == [content]
    assert result.get("success") is False, result
    assert result.get("status") == "uncertain", result
    assert result.get("requires_reconciliation") is True, result
    assert result.get("retryable") is False, result
    assert _claim_row(scratch["path"], operation_id)[0] == "uncertain_effect"

    # Close-out must preserve the unresolved fact rather than draining it.
    ws = bpe_workspace.get_workspace(WS, AGENT, SESSION)
    assert ws._pending_notes == [content]
    assert ws.experience.to_dict()["skills"] == []


def test_exact_retry_replays_without_duplicating_the_note(scratch, bpe_data):
    content = "single effect"
    operation_id = f"op-replay-{uuid.uuid4().hex}"
    context = _context(operation_id)
    calls = []

    async def leaf(tool, arguments, inner_context=None):
        calls.append(tool)
        return await action_registry.execute_action(
            tool, arguments, inner_context or {})

    agent = _agent(leaf)
    first = asyncio.run(agent._step_act_unaudited(
        NOTE, {"content": content}, context=dict(context), pre_approved=True))
    second = asyncio.run(agent._step_act_unaudited(
        NOTE, {"content": content}, context=dict(context), pre_approved=True))

    assert first.get("oracle_verified") is True, first
    assert len(calls) == 1, calls
    assert second.get("replayed") is True, second
    assert second.get("oracle_verified") is True, second
    assert "no second dispatch" in str(second.get("message") or "").lower()
    assert _snapshot()["pending_notes"] == [content]
    assert _claim_row(scratch["path"], operation_id)[0] == "succeeded"


# ---------------------------------------------------------------------------
# Commit valid twin (add + status update)
# ---------------------------------------------------------------------------


def test_commit_is_verified_persisted_and_status_update_is_read_back(
        scratch, bpe_data):
    add_op = f"op-commit-add-{uuid.uuid4().hex}"
    add = _dispatch(COMMIT, {"title": "collect evidence"}, _context(add_op))
    assert add.get("success") is True, add
    assert add.get("oracle_verified") is True, add
    assert _claim_row(scratch["path"], add_op)[0] == "succeeded"

    stored = _stored()
    assert stored["progress"][0]["title"] == "collect evidence"
    assert stored["progress"][0]["status"] == "pending"
    assert stored["operation_receipts"][0]["action"] == COMMIT

    update_op = f"op-commit-update-{uuid.uuid4().hex}"
    update = _dispatch(
        COMMIT, {"title": "collect", "status": "done"}, _context(update_op))
    assert update.get("success") is True, update
    assert update.get("oracle_verified") is True, update
    assert _claim_row(scratch["path"], update_op)[0] == "succeeded"
    assert _snapshot()["progress"][0]["status"] == "done"


def test_commit_changed_material_same_operation_is_refuted(scratch, bpe_data):
    operation_id = f"op-commit-material-{uuid.uuid4().hex}"
    ws = bpe_workspace.BPEWorkspace(WS, AGENT, SESSION)
    ws.progress.append(bpe_workspace.Subgoal(title="original step"))
    expected_original = _expected(
        COMMIT, {"title": "original step", "status": None}, operation_id)
    ws.record_operation_receipt({
        "action": COMMIT,
        "operation_id": operation_id,
        "workspace_id": WS,
        "agent_id": AGENT,
        "scope_key": SESSION,
        "actor_id": "",
        "material": {"title": "original step", "status": None},
        "material_sha256": expected_original[
            "_oracle_expected_bpe_material_sha256"],
        "resolved_title": "original step",
        "created_at": 1.0,
    })
    assert BPEWorkspaceStore().save(ws.to_dict()) is True

    changed = _expected(
        COMMIT, {"title": "different step", "status": None}, operation_id)
    verdict = _validate(COMMIT, changed)
    assert verdict.verified is False, verdict
    assert "material" in verdict.evidence


# ---------------------------------------------------------------------------
# Real execute() close-out preserves an unresolved landed note
# ---------------------------------------------------------------------------


def test_execute_closeout_preserves_unresolved_note(
        scratch, bpe_data, monkeypatch):
    from core.llm.byok_handler import QueryComplexity
    from core.models import AgentRegistry
    from core.react_models import ReActStep, ToolCall

    content = "preserve me on an unresolved run"
    calls = {"save": 0}
    original_save = BPEWorkspaceStore.save

    def _stateful_save(_self, snapshot):
        calls["save"] += 1
        if calls["save"] == 1:  # dispatch persistence fails
            return False
        return original_save(_self, snapshot)

    monkeypatch.setattr(BPEWorkspaceStore, "save", _stateful_save)

    model = AgentRegistry(
        id=AGENT, name="BPE outcome agent", category="general",
        configuration={"tools": "*", "max_steps": 4},
    )
    with patch("core.generic_agent.WorldModelService"), \
         patch("core.generic_agent.ReflectionService"), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service"), \
         patch("core.generic_agent.LLMService"):
        agent = GenericAgent(model)
    agent.workspace_id = WS
    agent.tenant_id = TENANT
    agent.allowed_tools = "*"
    agent.blocked_tools = set()
    agent.session_tools = []
    agent.world_model.recall_experiences = AsyncMock(
        return_value={"experiences": []})
    agent.world_model.record_experience = AsyncMock()
    agent.reflection_service.add_critique = AsyncMock()
    agent._recall_durable_facts = AsyncMock(return_value=[])
    agent._measure_success_rate = AsyncMock(return_value=None)
    agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
    agent._record_execution = AsyncMock()
    agent.llm = MagicMock()
    agent.llm._get_handler.return_value.analyze_query_complexity.return_value = (
        QueryComplexity.SIMPLE)

    async def dispatch(tool, arguments, context=None):
        return await action_registry.execute_action(
            tool, arguments, context or {})

    agent.mcp = SimpleNamespace(
        call_tool=dispatch, get_all_tools=AsyncMock(return_value=[]))
    agent._react_step = AsyncMock(side_effect=[
        ReActStep(
            thought="note it",
            action=ToolCall(tool=NOTE, params={"content": content}),
        ),
        ReActStep(thought="done", final_answer="Recorded the note."),
    ])

    class _Gov:
        def __init__(self, db, workspace_id="default", tenant_id=None):
            self.db = db
            self.workspace_id = workspace_id
            self.tenant_id = tenant_id

        async def can_perform_action_async(self, agent_id, tool_name):
            return {"allowed": True, "requires_human_approval": False}

        async def record_outcome(self, *args, **kwargs):
            return None

    monkeypatch.setattr(ga, "AgentGovernanceService", _Gov)

    result = asyncio.run(agent.execute(
        "preserve an unresolved note",
        context={"execution_id": EXECUTION, "run_id": EXECUTION,
                 "session_id": SESSION},
    ))

    assert result["status"] == "uncertain", result
    assert result["requires_reconciliation"] is True, result
    state = result["bpe"]["state"]
    assert state["pending_notes"] == [content], state
    assert state["experience"]["skills"] == [], state
    assert result["bpe"]["consolidated"] == {"preserved_notes": 1}

    # The second (close-out) write is real and leaves the fact recoverable.
    restored = BPEWorkspaceStore().load(
        state["workspace_id"], state["agent_id"], state["scope_key"])
    assert restored["pending_notes"] == [content]
    assert restored["experience"]["skills"] == []


def test_durable_readback_shape_is_plain_json(scratch, bpe_data):
    """The receipt lives in the existing JSON file, not a new store."""
    content = "json readable"
    operation_id = f"op-json-{uuid.uuid4().hex}"
    _dispatch(NOTE, {"content": content}, _context(operation_id))

    path = bpe_data / f"{WS}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    key = f"{AGENT}|{SESSION}"
    assert key in payload, sorted(payload)
    assert payload[key]["pending_notes"] == [content]
    assert payload[key]["operation_receipts"][0]["operation_id"] == operation_id
