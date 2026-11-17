"""Whole-consumer contract: the Meta agent runs the human-approved material.

Each test drives the REAL ``AtomMetaAgent._execute_tool_with_governance`` /
``_execute_parallel_tools`` entry, the REAL
``AgentGovernanceService.request_approval`` durable writer and the REAL
``InterventionService.approve_intervention``/``reject_intervention``
decision writer against a scratch SQLite store. The only test doubles are the
synthetic MCP leaf, the governance ask-for-review verdict and the safety-judge
verdict — no model, network, provider or external side effect is involved.

Locked defect (root counter ``atom-meta-approved-material-counter-20261117``):
Meta filed a HITL row with no actor/execution/scope binding, ignored
edit-before-approve material and dispatched the model's ORIGINAL args. The
durable approved read was ``corrected-filter`` while the handler still got
``original-filter``. A status boolean is not authority; the approval must bind
the runtime agent (``atom_main``), the current actor, execution, scope,
reviewer and the exact reviewed/effective payload.

Run with an absolute scratch DB (never the live dev DB):

    TESTING=1 PYTEST_CURRENT_TEST=meta_approved_material_ci \
    PYTHON_DOTENV_DISABLED=1 \
    DATABASE_URL=sqlite:////absolute/path/meta-approved-material.db \
    /private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python -m pytest \
      tests/test_meta_approved_material_contract.py -q
"""
from __future__ import annotations

import contextlib
import copy
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agent_governance_service import AgentGovernanceService
from core.atom_meta_agent import AtomMetaAgent
from core.intervention_service import InterventionService, describe_parameter_history
from core.models import (
    Base,
    HITLAction,
    HITLActionStatus,
    Tenant,
    User,
    Workspace,
)
from core.oracle.request_expectations import approved_payload_sha256
from core.react_models import ToolCall


# ---------------------------------------------------------------------------
# Canonical scratch store + real service wiring
# ---------------------------------------------------------------------------

class Env:
    def __init__(self, engine, Session, service_session, audit):
        self.engine = engine
        self.Session = Session
        self.service_session = service_session
        self.audit = audit


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'meta-approved-material.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    seed = Session()
    seed.add_all([
        Tenant(id="default", name="Personal", subdomain="personal"),
        Workspace(id="ws-test", name="Test", tenant_id="default"),
        Workspace(id="ws-other", name="Other", tenant_id="default"),
    ])
    seed.add_all([
        User(
            id="lead-1", tenant_id="default", workspace_id="ws-test",
            email="lead@example.com", first_name="Lead", last_name="One",
            role="team_lead", status="active", is_active=True),
        User(
            id="member-1", tenant_id="default", workspace_id="ws-test",
            email="member@example.com", first_name="Member", last_name="One",
            role="member", status="active", is_active=True),
        User(
            id="lead-other", tenant_id="default", workspace_id="ws-other",
            email="other@example.com", first_name="Other", last_name="Lead",
            role="team_lead", status="active", is_active=True),
        User(
            id="inactive-lead", tenant_id="default", workspace_id="ws-test",
            email="inactive@example.com", first_name="Inactive",
            last_name="Lead", role="team_lead", status="inactive",
            is_active=False),
    ])
    seed.commit()
    seed.close()

    @contextlib.contextmanager
    def service_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    # Every production writer/reader in this path uses the SAME scratch store:
    # the meta consumer's SessionLocal, the intervention decision writer and
    # the audit ledger.
    monkeypatch.setattr("core.atom_meta_agent.SessionLocal", Session)
    monkeypatch.setattr(
        "core.intervention_service.get_db_session", service_session)

    audit = []
    monkeypatch.setattr(
        "core.agent_action_audit.log_agent_action",
        lambda **kwargs: audit.append(kwargs) or "audit-row")

    yield Env(engine=engine, Session=Session,
              service_session=service_session, audit=audit)
    engine.dispose()


# ---------------------------------------------------------------------------
# Synthetic leaves / verdict doubles (policy verdict only, never authority)
# ---------------------------------------------------------------------------

class Leaf:
    """Synthetic MCP surface: records exactly what the consumer dispatched."""

    def __init__(self, result=None):
        self.calls = []
        self._result = result if result is not None else {"success": True}

    async def call_tool(self, tool_name, args, **kwargs):
        self.calls.append({
            "tool": tool_name,
            "args": copy.deepcopy(args),
            "context": dict(kwargs.get("context") or {}),
        })
        return copy.deepcopy(self._result)


def _user(user_id: str = "lead-1") -> SimpleNamespace:
    return SimpleNamespace(id=user_id)


def _agent(
    leaf: Leaf, *, user: str = "lead-1", workspace: str = "ws-test",
    tenant: str = "default",
) -> AtomMetaAgent:
    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.workspace_id = workspace
    agent.tenant_id = tenant
    agent.user = _user(user)
    agent.mcp = leaf
    agent.llm = SimpleNamespace()
    agent.session_tools = []
    agent._custom_actions = {}
    agent.graduation_service = SimpleNamespace(
        get_maturity=lambda *_a, **_k: "autonomous",
        record_usage=lambda *_a, **_k: None,
    )
    return agent


def _context(
    execution: str = "exec-meta", *, user: str = "lead-1",
    workspace: str = "ws-test", tenant: str = "default", **extra,
) -> dict:
    context = {
        "user_id": user,
        "workspace_id": workspace,
        "tenant_id": tenant,
        "execution_id": execution,
    }
    context.update(extra)
    return context


def _review_verdict(**extra) -> dict:
    verdict = {
        "allowed": False,
        "requires_human_approval": True,
        "reason": "synthetic policy requires review",
        "agent_status": "supervised",
        "action_complexity": 3,
        "required_status": "supervised",
        "confidence": 0.5,
    }
    verdict.update(extra)
    return verdict


def _allow_verdict(**extra) -> dict:
    verdict = {
        "allowed": True,
        "requires_human_approval": False,
        "reason": "Maturity check passed.",
        "agent_status": "autonomous",
        "action_complexity": 1,
        "required_status": "student",
        "confidence": 0.9,
    }
    verdict.update(extra)
    return verdict


def _governance(monkeypatch, verdicts) -> list:
    """Patch only the policy verdict; returns the recorded (agent, tool) calls."""
    calls = []
    if not isinstance(verdicts, list):
        verdicts = [verdicts]

    async def _check(self, agent_id, action_type, **_kwargs):
        calls.append({"agent_id": agent_id, "action": action_type})
        index = min(len(calls) - 1, len(verdicts) - 1)
        return copy.deepcopy(verdicts[index])

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", _check)
    return calls


async def _approve_async(
    action_id: str, reviewer: str = "lead-1", modified=None,
) -> dict:
    result = await InterventionService().approve_intervention(
        action_id, reviewer, modified_params=modified)
    assert result.get("success") is True, result
    return result


async def _reject_async(action_id: str, reviewer: str = "lead-1") -> dict:
    result = await InterventionService().reject_intervention(
        action_id, reviewer, "synthetic rejection")
    assert result.get("success") is True, result
    return result


def _rows(env: Env) -> list:
    with env.Session() as db:
        return db.query(HITLAction).order_by(HITLAction.created_at).all()


def _row(env: Env, action_id: str) -> HITLAction:
    with env.Session() as db:
        return db.query(HITLAction).filter(HITLAction.id == action_id).one()


def _file_approval(env: Env, agent: AtomMetaAgent, context: dict, *,
                   action: str = "read_data", params: dict = None) -> str:
    """File a HITL row through the consumer's own producer binding."""
    with env.Session() as db:
        gov = AgentGovernanceService(
            db,
            workspace_id=agent.workspace_id,
            tenant_id=agent._approval_tenant_arg(
                agent._approval_binding(context)),
        )
        return agent._request_meta_approval(
            gov,
            tool_name=action,
            params=copy.deepcopy(params if params is not None else {}),
            reason="synthetic policy requires review",
            context=context,
        )


# ---------------------------------------------------------------------------
# Positive sequential consumers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meta_consumes_the_actual_human_approved_read_parameters(
    env, monkeypatch,
):
    """Root counter: the durable approved query must reach the handler."""
    leaf = Leaf(result={"rows": [], "success": True})
    agent = _agent(leaf)
    _governance(monkeypatch, _review_verdict(agent_status="autonomous"))

    decisions = []

    async def approve_then_observe(action_id):
        await _approve_async(
            action_id, modified={"query": "corrected-filter"})
        row = _row(env, action_id)
        decisions.append({
            "params": dict(row.params),
            "agent_id": row.agent_id,
            "user_id": row.user_id,
            "workspace_id": row.workspace_id,
            "tenant_id": row.tenant_id,
            "execution_id": (row.context_snapshot or {}).get("execution_id"),
            "history": describe_parameter_history(row, redact=False),
        })
        return True

    agent._wait_for_approval = approve_then_observe
    original = {"query": "original-filter"}
    result = await agent._execute_tool_with_governance(
        "read_data", original, _context(execution="meta-read-counter"), None)

    assert decisions[0]["params"] == {"query": "corrected-filter"}
    # The durable row is bound to the runtime agent, the real actor, the
    # execution and the authenticated scope — not to status alone.
    assert decisions[0]["agent_id"] == "atom_main"
    assert decisions[0]["user_id"] == "lead-1"
    assert decisions[0]["workspace_id"] == "ws-test"
    # Personal Edition persists the scope as NULL and canonicalises it to
    # "default"; both are the SAME scope on comparison.
    from core.goal_run_decision_service import canonical_scope_id

    assert canonical_scope_id(decisions[0]["tenant_id"]) == "default"
    assert decisions[0]["execution_id"] == "meta-read-counter"

    assert len(leaf.calls) == 1
    assert leaf.calls[0]["args"] == decisions[0]["params"]
    # The caller's reviewed request is preserved, not rewritten.
    assert original == {"query": "original-filter"}
    assert result == str({"rows": [], "success": True})


@pytest.mark.asyncio
async def test_unchanged_read_approval_dispatches_reviewed_request_once(
    env, monkeypatch,
):
    leaf = Leaf(result={"rows": [], "success": True})
    agent = _agent(leaf)
    _governance(monkeypatch, _review_verdict(action_complexity=1,
                                             required_status="student"))

    async def approve(action_id):
        await _approve_async(action_id)
        return True

    agent._wait_for_approval = approve
    reviewed = {"query": "unchanged-filter"}
    await agent._execute_tool_with_governance(
        "read_data", reviewed, _context(execution="meta-unchanged"), None)

    assert len(leaf.calls) == 1
    assert leaf.calls[0]["tool"] == "read_data"
    assert leaf.calls[0]["args"] == reviewed
    assert reviewed == {"query": "unchanged-filter"}


@pytest.mark.asyncio
async def test_edited_declared_mutation_dispatches_exact_effective_material(
    env, monkeypatch,
):
    leaf = Leaf(result={"success": True, "id": "task-9"})
    agent = _agent(leaf)
    _governance(monkeypatch, _review_verdict())

    approved = {"title": "Edited by reviewer", "board_id": "board-2"}

    async def approve(action_id):
        await _approve_async(action_id, modified=approved)
        return True

    agent._wait_for_approval = approve
    original = {"title": "Original title", "board_id": "board-1"}
    result = await agent._execute_tool_with_governance(
        "tasks.create", original, _context(execution="meta-mutation"), None)

    assert result == str({"success": True, "id": "task-9"})
    assert len(leaf.calls) == 1
    assert leaf.calls[0]["args"] == approved

    # Audit keeps the REVIEWED ORIGINAL request plus redacted provenance
    # (identity + payload digests only — no second copy of parameters).
    row = _rows(env)[0]
    tool_audit = [
        entry for entry in env.audit
        if entry.get("action") == "tool:tasks.create"
    ]
    assert len(tool_audit) == 1
    metadata = tool_audit[0]["metadata"]
    assert metadata["params"] == original
    approval_provenance = metadata["approval"]
    assert approval_provenance["action_id"] == row.id
    assert approval_provenance["approved_by"] == "lead-1"
    assert approval_provenance["material_changed"] is True
    assert approval_provenance["dispatched"] is True
    assert approval_provenance["binding"]["agent_id"] == "atom_main"
    assert approval_provenance["binding"]["execution_id"] == "meta-mutation"
    assert approval_provenance["reviewed_sha256"] == approved_payload_sha256(
        original)
    assert approval_provenance["effective_sha256"] == approved_payload_sha256(
        approved)
    assert "effective_params" not in approval_provenance
    assert "original_params" not in approval_provenance
    assert tool_audit[0]["success"] is True


@pytest.mark.asyncio
async def test_second_call_without_a_fresh_human_decision_never_resends(
    env, monkeypatch,
):
    """The approved row is a decision for ONE review, not a standing waiver."""
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    _governance(monkeypatch, _review_verdict())

    async def approve(action_id):
        await _approve_async(action_id, modified={"query": "corrected"})
        return True

    agent._wait_for_approval = approve
    params = {"query": "original"}
    await agent._execute_tool_with_governance(
        "read_data", params, _context(execution="meta-once"), None)
    assert len(leaf.calls) == 1
    first_rows = len(_rows(env))

    # Same execution, same request, but the human does not decide the new ask.
    agent._wait_for_approval = AsyncMock(return_value=False)
    second = await agent._execute_tool_with_governance(
        "read_data", params, _context(execution="meta-once"), None)
    assert len(leaf.calls) == 1  # no automatic second dispatch
    assert "REJECTED or timed out" in second
    assert len(_rows(env)) == first_rows + 1  # a NEW durable ask


# ---------------------------------------------------------------------------
# Parallel batch consumer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_batch_consumes_per_action_approved_material(
    env, monkeypatch,
):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    context = _context(execution="meta-parallel")

    async def check(_self, _agent_id, action_type, **_kwargs):
        if action_type == "read_data":
            return _review_verdict()
        return _allow_verdict()

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", check)
    monkeypatch.setattr(
        "core.hallucination_config.is_parallel_tools_enabled", lambda: True)
    monkeypatch.setattr(
        "core.hallucination_config.get_max_parallel_tools", lambda: 4)

    async def approve_all(action_ids):
        for action_id in action_ids:
            await _approve_async(
                action_id, modified={"query": "parallel-corrected"})
        return True

    agent._wait_for_all_approvals = approve_all
    actions = [
        ToolCall(tool="read_data", params={"query": "parallel-original"}),
        ToolCall(tool="read_other", params={"query": "untouched"}),
    ]
    records = await agent._execute_parallel_tools(actions, context, None)

    assert len(leaf.calls) == 2
    by_tool = {item["tool"]: item["args"] for item in leaf.calls}
    assert by_tool["read_data"] == {"query": "parallel-corrected"}
    assert by_tool["read_other"] == {"query": "untouched"}
    assert len(records) == 2
    approved_record = next(
        record for record in records if record["tool_name"] == "read_data")
    # The model's original request stays on the record.
    assert approved_record["params"] == {"query": "parallel-original"}


@pytest.mark.asyncio
async def test_parallel_batch_refuses_a_tampered_action_but_runs_the_rest(
    env, monkeypatch,
):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    context = _context(execution="meta-parallel-tamper")

    async def check(_self, _agent_id, action_type, **_kwargs):
        if action_type == "read_data":
            return _review_verdict()
        return _allow_verdict()

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", check)
    monkeypatch.setattr(
        "core.hallucination_config.is_parallel_tools_enabled", lambda: True)
    monkeypatch.setattr(
        "core.hallucination_config.get_max_parallel_tools", lambda: 4)

    async def approve_all(action_ids):
        for action_id in action_ids:
            await _approve_async(action_id, modified={"query": "approved"})
            with env.Session() as db:
                row = db.get(HITLAction, action_id)
                row.params = {"query": "tampered-after-approval"}
                db.commit()
        return True

    agent._wait_for_all_approvals = approve_all
    actions = [
        ToolCall(tool="read_data", params={"query": "original"}),
        ToolCall(tool="read_other", params={"query": "untouched"}),
    ]
    records = await agent._execute_parallel_tools(actions, context, None)

    assert [item["tool"] for item in leaf.calls] == ["read_other"]
    refused = next(
        record for record in records if record["tool_name"] == "read_data")
    assert "approval_material_tampered" in str(refused["output"])
    assert "tampered-after-approval" not in str(refused["output"])


@pytest.mark.asyncio
async def test_parallel_batch_rejection_executes_no_tool(env, monkeypatch):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)

    async def check(_self, _agent_id, action_type, **_kwargs):
        return _review_verdict()

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", check)
    monkeypatch.setattr(
        "core.hallucination_config.is_parallel_tools_enabled", lambda: True)
    monkeypatch.setattr(
        "core.hallucination_config.get_max_parallel_tools", lambda: 4)

    async def reject_all(action_ids):
        await _reject_async(action_ids[0])
        return False

    agent._wait_for_all_approvals = reject_all
    records = await agent._execute_parallel_tools(
        [
            ToolCall(tool="read_data", params={"query": "a"}),
            ToolCall(tool="tasks.create", params={"title": "b"}),
        ],
        _context(execution="meta-parallel-reject"), None)

    assert leaf.calls == []
    assert all("REJECTED" in str(record["output"]) for record in records)


# ---------------------------------------------------------------------------
# Runtime agent vs context hint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_agent_hint_never_retargets_the_approval(env, monkeypatch):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    _governance(monkeypatch, _review_verdict(agent_status="autonomous"))
    context = _context(
        execution="meta-hint", agent_id="parent-orchestrator",
        agent="parent-orchestrator")

    async def approve(action_id):
        await _approve_async(action_id, modified={"query": "corrected"})
        return True

    agent._wait_for_approval = approve
    await agent._execute_tool_with_governance(
        "read_data", {"query": "original"}, context, None)

    rows = _rows(env)
    assert len(rows) == 1
    assert rows[0].agent_id == "atom_main"
    assert leaf.calls[0]["args"] == {"query": "corrected"}


@pytest.mark.asyncio
async def test_approval_bound_to_another_agent_is_refused(env, monkeypatch):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    context = _context(execution="meta-foreign-agent")
    _governance(monkeypatch, _review_verdict())

    # A row filed by a different runtime agent (a legitimately foreign
    # decision) must never authorize this consumer.
    with env.Session() as db:
        gov = AgentGovernanceService(
            db, workspace_id="ws-test", tenant_id="default")
        action_id = gov.request_approval(
            agent_id="other-agent",
            action_type="read_data",
            params={"query": "foreign"},
            reason="synthetic foreign decision",
            execution_context=context,
            user_id="lead-1",
        )
    await _approve_async(action_id)

    out = await agent._execute_tool_with_governance(
        "read_data", {"query": "foreign"}, context,
        pre_approved=True, approval_action_id=action_id)
    assert leaf.calls == []
    assert "approval_agent_mismatch" in str(out)


# ---------------------------------------------------------------------------
# Missing / invalid / foreign / revoked / tampered proof
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_or_pending_proof_is_a_non_effect(env, monkeypatch):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    context = _context(execution="meta-missing")
    _governance(monkeypatch, _review_verdict())

    async def approved_but_row_gone(action_id):
        await _approve_async(action_id)
        with env.Session() as db:
            db.query(HITLAction).filter(HITLAction.id == action_id).delete()
            db.commit()
        return True

    agent._wait_for_approval = approved_but_row_gone
    out = await agent._execute_tool_with_governance(
        "read_data", {"query": "gone"}, context, None)
    assert leaf.calls == []
    assert "approval_not_found" in str(out)

    # A pending row with a "True" wait result is still not authority.
    pending_id = _file_approval(
        env, agent, context, params={"query": "pending"})
    agent._wait_for_approval = AsyncMock(return_value=True)
    out = await agent._execute_tool_with_governance(
        "read_data", {"query": "pending"}, context, None)
    assert leaf.calls == []
    assert "approval_not_approved" in str(out)
    assert _row(env, pending_id).status == HITLActionStatus.PENDING.value


@pytest.mark.asyncio
async def test_foreign_actor_and_reviewer_are_refused(env, monkeypatch):
    leaf = Leaf(result={"success": True})
    context = _context(execution="meta-foreign-actor")

    owner_id = _file_approval(
        env, _agent(leaf), context, action="tasks.create",
        params={"title": "Owned task", "board_id": "board-1"})
    await _approve_async(owner_id)

    # Same durable row, different current actor.
    member_agent = _agent(leaf, user="member-1")
    out = await member_agent._execute_tool_with_governance(
        "tasks.create", {"title": "Owned task", "board_id": "board-1"},
        _context(execution="meta-foreign-actor", user="member-1"),
        pre_approved=True, approval_action_id=owner_id)
    assert leaf.calls == []
    assert "approval_actor_mismatch" in str(out)

    # A reviewer outside the approval's scope is not authority.
    foreign_context = _context(execution="meta-foreign-review")
    foreign_id = _file_approval(
        env, _agent(leaf), foreign_context, action="read_data",
        params={"query": "foreign-review"})
    await _approve_async(foreign_id, reviewer="lead-other")
    out = await _agent(leaf)._execute_tool_with_governance(
        "read_data", {"query": "foreign-review"}, foreign_context,
        pre_approved=True, approval_action_id=foreign_id)
    assert leaf.calls == []
    assert "approval_reviewer_scope_denied" in str(out)

    # A reviewer deactivated after the decision is not authority either.
    stale_context = _context(execution="meta-stale-review")
    stale_id = _file_approval(
        env, _agent(leaf), stale_context, action="read_data",
        params={"query": "stale-review"})
    await _approve_async(stale_id, reviewer="lead-1")
    with env.Session() as db:
        reviewer = db.get(User, "lead-1")
        reviewer.status = "inactive"
        reviewer.is_active = False
        db.commit()
    out = await _agent(leaf)._execute_tool_with_governance(
        "read_data", {"query": "stale-review"}, stale_context,
        pre_approved=True, approval_action_id=stale_id)
    assert leaf.calls == []
    assert "approval_reviewer_unavailable" in str(out)


@pytest.mark.asyncio
async def test_tampered_revoked_or_mismatched_approval_is_refused(
    env, monkeypatch,
):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    context = _context(execution="meta-tamper")
    _governance(monkeypatch, _review_verdict())

    # Tampered effective payload after the reviewer decision.
    tamper_id = _file_approval(
        env, agent, context, params={"query": "tamper"})
    await _approve_async(tamper_id, modified={"query": "tamper-approved"})
    with env.Session() as db:
        row = db.get(HITLAction, tamper_id)
        row.params = {"query": "tamper-replaced"}
        db.commit()
    out = await agent._execute_tool_with_governance(
        "read_data", {"query": "tamper"}, context,
        pre_approved=True, approval_action_id=tamper_id)
    assert leaf.calls == []
    assert "approval_material_tampered" in str(out)
    assert "tamper-replaced" not in str(out)
    assert "tamper-approved" not in str(out)

    # Revoked status.
    revoked_id = _file_approval(
        env, agent, context, params={"query": "revoked"})
    await _approve_async(revoked_id)
    with env.Session() as db:
        row = db.get(HITLAction, revoked_id)
        row.status = HITLActionStatus.REJECTED.value
        db.commit()
    out = await agent._execute_tool_with_governance(
        "read_data", {"query": "revoked"}, context,
        pre_approved=True, approval_action_id=revoked_id)
    assert leaf.calls == []
    assert "approval_not_approved" in str(out)

    # Foreign workspace binding.
    scope_id = _file_approval(
        env, agent, context, params={"query": "scope"})
    await _approve_async(scope_id)
    with env.Session() as db:
        row = db.get(HITLAction, scope_id)
        row.workspace_id = "ws-other"
        db.commit()
    out = await agent._execute_tool_with_governance(
        "read_data", {"query": "scope"}, context,
        pre_approved=True, approval_action_id=scope_id)
    assert leaf.calls == []
    assert "approval_scope_mismatch" in str(out)

    # A different reviewed request under the same approval id.
    mismatch_id = _file_approval(
        env, agent, context, params={"query": "reviewed-one"})
    await _approve_async(mismatch_id)
    out = await agent._execute_tool_with_governance(
        "read_data", {"query": "different-one"}, context,
        pre_approved=True, approval_action_id=mismatch_id)
    assert leaf.calls == []
    assert "approval_material_mismatch" in str(out)

    # A required role persisted AFTER the decision is not satisfied.
    role_id = _file_approval(
        env, agent, context, params={"query": "role"})
    await _approve_async(role_id)
    with env.Session() as db:
        row = db.get(HITLAction, role_id)
        row.required_role = "admin"
        db.commit()
    out = await agent._execute_tool_with_governance(
        "read_data", {"query": "role"}, context,
        pre_approved=True, approval_action_id=role_id)
    assert leaf.calls == []
    assert "approval_reviewer_role_denied" in str(out)


# ---------------------------------------------------------------------------
# Staleness during the wait and during later awaited checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_actor_revoked_during_wait_is_a_terminal_non_effect(
    env, monkeypatch,
):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf, user="member-1")
    _governance(monkeypatch, _review_verdict())

    async def approve_then_revoke_actor(action_id):
        await _approve_async(action_id, reviewer="lead-1")
        with env.Session() as db:
            actor = db.get(User, "member-1")
            actor.status = "disabled"
            actor.is_active = False
            db.commit()
        return True

    agent._wait_for_approval = approve_then_revoke_actor
    out = await agent._execute_tool_with_governance(
        "tasks.create", {"title": "Revoked task", "board_id": "board-1"},
        _context(execution="meta-actor-revoked", user="member-1"), None)

    assert leaf.calls == []
    assert isinstance(out, dict)
    assert out["terminal_authority_denial"] is True
    assert out["status"] == "failed_before_effect"
    assert out["action_result"] == "not_applied"
    assert out["business_success"] is False
    assert out["effect_state"] == "none"
    assert out["requires_reconciliation"] is False
    assert out["error_class"] == "approval_actor_inactive"
    assert "Revoked task" not in str(out)


@pytest.mark.asyncio
async def test_actor_revoked_during_the_awaited_gate_is_caught_by_final_fence(
    env, monkeypatch,
):
    """The last awaited gate must not reopen the authority window."""
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf, user="member-1")
    calls = {"n": 0}

    async def check(_self, _agent_id, action_type, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            # Between the first consume and the final fence.
            with env.Session() as db:
                actor = db.get(User, "member-1")
                actor.status = "inactive"
                actor.is_active = False
                db.commit()
        return _review_verdict()

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", check)

    async def approve(action_id):
        await _approve_async(
            action_id, reviewer="lead-1", modified={"query": "corrected"})
        return True

    agent._wait_for_approval = approve
    out = await agent._execute_tool_with_governance(
        "read_data", {"query": "original"},
        _context(execution="meta-gate-revoked", user="member-1"), None)

    assert calls["n"] >= 2
    assert leaf.calls == []
    assert isinstance(out, dict)
    assert out["terminal_authority_denial"] is True
    assert out["error_class"] == "approval_actor_inactive"


@pytest.mark.asyncio
async def test_changed_risk_budget_or_never_policy_refuses_before_dispatch(
    env, monkeypatch,
):
    leaf = Leaf(result={"success": True})
    context = _context(execution="meta-risk")

    reviewed = _review_verdict()
    _governance(monkeypatch, [reviewed, _review_verdict(action_complexity=4)])
    risk_agent = _agent(leaf)

    async def approve(action_id):
        await _approve_async(action_id)
        return True

    risk_agent._wait_for_approval = approve
    out = await risk_agent._execute_tool_with_governance(
        "read_data", {"query": "risk"}, context, None)
    assert leaf.calls == []
    assert "action complexity" in str(out)

    budget_context = _context(execution="meta-budget")
    _governance(monkeypatch, [
        reviewed,
        {
            "allowed": False,
            "requires_human_approval": False,
            "status_code": "BUDGET_EXCEEDED",
            "reason": "Budget exhausted",
        },
    ])
    budget_agent = _agent(leaf)

    async def approve_budget(action_id):
        await _approve_async(action_id)
        return True

    budget_agent._wait_for_approval = approve_budget
    out = await budget_agent._execute_tool_with_governance(
        "read_data", {"query": "budget"}, budget_context, None)
    assert leaf.calls == []
    assert "Budget exhausted" in str(out)

    never_context = _context(execution="meta-never")
    reviewed_never = _review_verdict(never_autonomous={
        "applicable": True,
        "matched": True,
        "outcome": "review",
        "rule_ids": ["rule-finance"],
        "rule_bindings": [{"id": "rule-finance", "revision": 1}],
        "reason": "reviewed finance rule",
    })
    changed_never = _review_verdict(never_autonomous={
        "applicable": True,
        "matched": True,
        "outcome": "review",
        "rule_ids": ["rule-finance"],
        "rule_bindings": [{"id": "rule-finance", "revision": 2}],
        "reason": "edited finance rule",
    })
    _governance(monkeypatch, [reviewed_never, changed_never])
    never_agent = _agent(leaf)

    async def approve_never(action_id):
        await _approve_async(action_id)
        return True

    never_agent._wait_for_approval = approve_never
    out = await never_agent._execute_tool_with_governance(
        "read_data", {"query": "never"}, never_context, None)
    assert leaf.calls == []
    assert "never-autonomous policy changed" in str(out)


# ---------------------------------------------------------------------------
# Safety-judge escalation callsite
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_judge_escalation_consumes_the_edited_decision(env, monkeypatch):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    _governance(monkeypatch, _allow_verdict())
    monkeypatch.setattr(
        "core.sandbox_config.is_sandbox_judge_enabled", lambda: True)

    class _Verdict:
        BLOCK = "block"
        ESCALATE = "escalate"
        ALLOW = "allow"

    class _Judge:
        def __init__(self, **_kwargs):
            pass

        async def evaluate(self, **_kwargs):
            return SimpleNamespace(
                verdict=_Verdict.ESCALATE, rationale="synthetic escalation")

    monkeypatch.setattr("core.llm.action_judge.ActionJudge", _Judge)
    monkeypatch.setattr("core.llm.action_judge.JudgeVerdict", _Verdict)

    async def escalate_then_approve(action_id):
        await _approve_async(action_id, modified={"query": "judge-edited"})
        return True

    agent._wait_for_approval = escalate_then_approve
    await agent._execute_tool_with_governance(
        "read_data", {"query": "judge-original"},
        _context(execution="meta-judge"), None)

    rows = _rows(env)
    assert len(rows) == 1
    assert rows[0].agent_id == "atom_main"
    assert rows[0].user_id == "lead-1"
    assert (rows[0].context_snapshot or {}).get("execution_id") == "meta-judge"
    assert len(leaf.calls) == 1
    assert leaf.calls[0]["args"] == {"query": "judge-edited"}


# ---------------------------------------------------------------------------
# Cold receipt / reviewer readback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cold_receipt_reviewer_and_role_readback(env, monkeypatch):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    _governance(monkeypatch, _review_verdict(agent_status="autonomous"))
    original = {"query": "readback-original"}
    effective = {"query": "readback-approved"}

    async def approve(action_id):
        await _approve_async(action_id, modified=effective)
        return True

    agent._wait_for_approval = approve
    await agent._execute_tool_with_governance(
        "read_data", original, _context(execution="meta-readback"), None)

    # Cold process read: a brand-new session sees the durable receipt.
    with env.Session() as db:
        row = db.query(HITLAction).filter(HITLAction.id == _rows(env)[0].id).one()
        history = describe_parameter_history(row, redact=False)
        reviewer = db.get(User, row.reviewed_by)
        reviewer_role = reviewer.role

    assert history["original_known"] is True
    assert history["original_params"] == original
    assert history["effective_params"] == effective
    assert history["modified"] is True
    assert history["modified_by"] == "lead-1"
    assert history["reviewed_by"] == "lead-1"
    assert history["reviewed_at"]
    assert reviewer_role == "team_lead"

    # Dispatch proof is the audit provenance, not a status boolean.
    approval_provenance = [
        entry["metadata"]["approval"] for entry in env.audit
        if entry.get("action") == "tool:read_data"
    ][0]
    assert approval_provenance["dispatched"] is True
    assert approval_provenance["effective_sha256"] == approved_payload_sha256(
        effective)


# ---------------------------------------------------------------------------
# Guard: refusals never leak original args or fake business success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refusal_is_never_a_business_success_and_leaks_no_args(
    env, monkeypatch,
):
    leaf = Leaf(result={"success": True})
    agent = _agent(leaf)
    context = _context(execution="meta-no-leak")
    _governance(monkeypatch, _review_verdict())

    action_id = _file_approval(
        env, agent, context, action="tasks.create",
        params={"title": "Secret original title", "board_id": "board-1"})
    await _approve_async(
        action_id,
        modified={"title": "Secret approved title", "board_id": "board-2"})
    with env.Session() as db:
        row = db.get(HITLAction, action_id)
        row.params = {"title": "Secret tampered title", "board_id": "board-3"}
        db.commit()

    out = await agent._execute_tool_with_governance(
        "tasks.create",
        {"title": "Secret original title", "board_id": "board-1"},
        context, pre_approved=True, approval_action_id=action_id)

    assert leaf.calls == []
    assert not isinstance(out, dict) or out.get("business_success") is not True
    assert "Secret original title" not in str(out)
    assert "Secret approved title" not in str(out)
    refusal_audit = [
        entry for entry in env.audit
        if entry.get("action") == "tool:tasks.create"
    ]
    assert refusal_audit and refusal_audit[0]["success"] is False
    provenance = refusal_audit[0]["metadata"]["approval"]
    assert provenance["dispatched"] is False
    assert provenance["consumed"] is False
    assert provenance["refusal_code"] == "approval_material_tampered"
    assert "Secret tampered title" not in str(provenance)
