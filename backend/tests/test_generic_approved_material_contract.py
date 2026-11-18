"""Durable approved-material consumption by the generic ReAct consumer.

These are whole-consumer regressions, not helper fixtures: each test drives the
real ``GenericAgent._step_act``/``_step_act_unaudited`` entry, the real
``AgentGovernanceService.request_approval`` writer and the real
``InterventionService.approve_intervention``/``reject_intervention`` decision
writer against a scratch SQLite store. The only synthetic leaves are the MCP
handler and a governance verdict that asks for review (no model, network or
provider call is made).

The defect being locked down (root evidence
``atom-root-generic-approved-params-counter-20261117``): the durable approved
query was ``corrected-filter`` while the handler still received the original
``original-filter``. Status alone must never authorize a dispatch, and an
edit-before-approve payload must actually run once with the edited material.

Run with an absolute scratch DB (never the live dev DB):

    TESTING=1 PYTEST_VERSION=local PYTHON_DOTENV_DISABLED=1 \
    DATABASE_URL=sqlite:////absolute/path/atom_approved.db \
    /private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python -m pytest \
      tests/test_generic_approved_material_contract.py -q
"""
from __future__ import annotations

import contextlib
import os

os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import outbound_operation_claim as claims
from core.agent_governance_service import AgentGovernanceService
from core.generic_agent import GenericAgent
from core.intervention_service import InterventionService
from core.models import (
    Base,
    HITLAction,
    HITLActionStatus,
    TaskOperationRecord,
    Tenant,
    User,
    Workspace,
)
from core.react_models import ToolCall


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'approved-material.db'}",
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

    # Every status/service writer in these tests uses the SAME scratch store.
    monkeypatch.setattr(
        "core.generic_agent.get_db_session", service_session)
    monkeypatch.setattr(
        "core.intervention_service.get_db_session", service_session)

    yield SimpleEnv(engine=engine, Session=Session,
                    service_session=service_session)
    engine.dispose()


class SimpleEnv:
    def __init__(self, engine, Session, service_session):
        self.engine = engine
        self.Session = Session
        self.service_session = service_session


def _context(
    execution: str = "exec-approved", *,
    user: str = "lead-1", workspace: str = "ws-test",
    tenant: str = "default", **extra,
) -> dict:
    context = {
        "user_id": user,
        "workspace_id": workspace,
        "tenant_id": tenant,
        "execution_id": execution,
    }
    context.update(extra)
    return context


def _agent(captured: list, result: dict = None) -> GenericAgent:
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = "agent-lead-1"
    agent.workspace_id = "ws-test"
    agent.tenant_id = "default"
    agent._custom_actions = {}

    async def leaf(tool_name, args, **kwargs):
        captured.append({
            "tool": tool_name,
            "args": dict(args),
            "context": dict(kwargs.get("context") or {}),
        })
        return dict(result or {"success": True})

    agent.mcp = SimpleNamespaceCallable(leaf)
    return agent


class SimpleNamespaceCallable:
    """Minimal MCP surface: only the leaf the consumer invokes."""

    def __init__(self, call_tool):
        self.call_tool = call_tool


def _request_approval(
    env, context: dict, *,
    action: str = "read_data", params: dict = None,
    user_id: str = "lead-1",
) -> str:
    with env.Session() as db:
        gov = AgentGovernanceService(
            db,
            workspace_id=context.get("workspace_id") or "ws-test",
            tenant_id=context.get("tenant_id") or "default",
        )
        return gov.request_approval(
            agent_id="agent-lead-1",
            action_type=action,
            params=dict(params if params is not None else {}),
            reason="synthetic policy requires review",
            execution_context=context,
            user_id=user_id,
        )


async def _approve(
    action_id: str, reviewer: str = "lead-1", modified=None,
) -> dict:
    result = await InterventionService().approve_intervention(
        action_id, reviewer, modified_params=modified)
    assert result.get("success") is True, result
    return result


async def _reject(action_id: str, reviewer: str = "lead-1") -> dict:
    result = await InterventionService().reject_intervention(
        action_id, reviewer, "synthetic rejection")
    assert result.get("success") is True, result
    return result


def _row(env, action_id: str) -> HITLAction:
    with env.Session() as db:
        return db.query(HITLAction).filter(
            HITLAction.id == action_id).one()


def _requires_review(reason: str = "synthetic policy requires review", **extra):
    payload = {
        "allowed": False,
        "requires_human_approval": True,
        "reason": reason,
        "agent_status": "supervised",
        "action_complexity": 3,
        "required_status": "supervised",
    }
    payload.update(extra)
    return payload


def _review_verdict(monkeypatch, verdict=None):
    verdict = verdict or _requires_review()

    async def _check(*_args, **_kwargs):
        return dict(verdict)

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", _check)
    return verdict


def _claim_rows(env, execution: str):
    with env.Session() as db:
        return db.query(TaskOperationRecord).filter(
            TaskOperationRecord.run_id == execution,
            TaskOperationRecord.operation_type.like("generic:agent:%"),
        ).all()


# ---------------------------------------------------------------------------
# Positive sequential consumers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_root_generic_consumes_the_actual_human_approved_read_parameters(
    env, monkeypatch,
):
    """Exact root counter: durable approved query must reach the handler."""
    captured = []
    decisions = []
    agent = _agent(captured, result={"rows": [], "success": True})
    _review_verdict(monkeypatch)

    async def approve_then_observe(action_id):
        await _approve(
            action_id, modified={"query": "corrected-filter"})
        decisions.append(dict(_row(env, action_id).params))
        return True

    agent._wait_for_approval = approve_then_observe
    original = {"query": "original-filter"}
    result = await agent._step_act_unaudited(
        "read_data", original,
        context=_context(execution="root-read-counter"))

    assert decisions == [{"query": "corrected-filter"}]
    assert len(captured) == 1
    assert captured[0]["args"] == decisions[0]
    # The caller's reviewed request is preserved for audit, not rewritten.
    assert original == {"query": "original-filter"}
    assert result == {"rows": [], "success": True}


@pytest.mark.asyncio
async def test_unchanged_approval_dispatches_the_reviewed_request_once(
    env, monkeypatch,
):
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)

    async def approve(action_id):
        await _approve(action_id)
        return True

    agent._wait_for_approval = approve
    reviewed = {"query": "unchanged-filter"}
    context = _context(
        execution="exec-unchanged", agent_id="parent-orchestrator")
    await agent._step_act_unaudited(
        "read_data", reviewed, context=context)

    assert len(captured) == 1
    assert captured[0]["tool"] == "read_data"
    assert captured[0]["args"] == reviewed
    assert reviewed == {"query": "unchanged-filter"}


@pytest.mark.asyncio
async def test_edited_declared_mutation_dispatches_effective_material(
    env, monkeypatch,
):
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)

    async def approve(action_id):
        await _approve(
            action_id,
            modified={"title": "Edited by reviewer", "board_id": "board-2"},
        )
        return True

    agent._wait_for_approval = approve
    context = _context(execution="exec-mutation")
    await agent._step_act_unaudited(
        "tasks.create",
        {"title": "Original title", "board_id": "board-1"},
        context=context,
    )

    assert len(captured) == 1
    assert captured[0]["args"] == {
        "title": "Edited by reviewer", "board_id": "board-2"}

    # The durable claim material was recomputed from the ACTUAL edited args,
    # not the model's original request.
    rows = _claim_rows(env, "exec-mutation")
    assert len(rows) == 1
    expected_hash = claims.operation_payload_sha256(
        workspace_id="ws-test",
        tenant_id="default",
        actor_id="lead-1",
        actor_kind="user",
        agent_id="agent-lead-1",
        execution_id="exec-mutation",
        execution_kind="execution",
        action="tasks.create",
        frozen_args={"title": "Edited by reviewer", "board_id": "board-2"},
    )
    assert rows[0].payload_sha256 == expected_hash
    original_hash = claims.operation_payload_sha256(
        workspace_id="ws-test",
        tenant_id="default",
        actor_id="lead-1",
        actor_kind="user",
        agent_id="agent-lead-1",
        execution_id="exec-mutation",
        execution_kind="execution",
        action="tasks.create",
        frozen_args={"title": "Original title", "board_id": "board-1"},
    )
    assert rows[0].payload_sha256 != original_hash


# ---------------------------------------------------------------------------
# Negative bindings: wrong action/material/actor/scope/reviewer/state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_for_another_action_or_request_is_refused(
    env, monkeypatch,
):
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-wrong")

    wrong_action_id = _request_approval(
        env, context, action="tasks.create",
        params={"title": "Some task", "board_id": "board-1"})
    await _approve(wrong_action_id)

    out = await agent._step_act_unaudited(
        "read_data", {"query": "x"}, context=context,
        pre_approved=True, approval_action_id=wrong_action_id)
    assert captured == []
    assert "approval_action_mismatch" in str(out)

    reviewed = {"query": "reviewed-filter"}
    row_id = _request_approval(
        env, context, action="read_data", params=reviewed)
    await _approve(row_id)
    out = await agent._step_act_unaudited(
        "read_data", {"query": "different-filter"}, context=context,
        pre_approved=True, approval_action_id=row_id)
    assert captured == []
    assert "approval_material_mismatch" in str(out)


@pytest.mark.asyncio
async def test_foreign_or_inactive_reviewer_is_refused(env, monkeypatch):
    captured = []
    _review_verdict(monkeypatch)
    context = _context(execution="exec-reviewer")

    # The shared decision writer now fences the reviewer there as well
    # (DECISION_SCOPE_DENIED), so the consumer's own independent fence is
    # pinned through the reachable shape: a reviewer who was in scope when the
    # decision was written and durably moved out of scope before dispatch. The
    # requester is a different, unmoved actor so only the reviewer fence fires.
    member_context = _context(execution="exec-reviewer", user="member-1")
    foreign_id = _request_approval(
        env, member_context, action="read_data", params={"query": "foreign"},
        user_id="member-1")
    foreign_agent = _agent(captured)

    async def foreign_reviewer(action_id):
        await _approve(action_id, reviewer="lead-1")
        with env.Session() as db:
            db.get(User, "lead-1").workspace_id = "ws-other"
            db.commit()
        return True

    foreign_agent._wait_for_approval = foreign_reviewer
    out = await foreign_agent._step_act_unaudited(
        "read_data", {"query": "foreign"}, context=member_context)
    assert captured == []
    assert "approval_reviewer_scope_denied" in str(out)

    # Restore the reviewer's admitted scope for the deactivation case below.
    with env.Session() as db:
        db.get(User, "lead-1").workspace_id = "ws-test"
        db.commit()

    stale_id = _request_approval(
        env, context, action="read_data", params={"query": "stale"})
    stale_agent = _agent(captured)

    async def stale_reviewer(action_id):
        await _approve(action_id, reviewer="lead-1")
        with env.Session() as db:
            reviewer = db.get(User, "lead-1")
            reviewer.status = "inactive"
            reviewer.is_active = False
            db.commit()
        return True

    stale_agent._wait_for_approval = stale_reviewer
    out = await stale_agent._step_act_unaudited(
        "read_data", {"query": "stale"}, context=context)
    assert captured == []
    assert "approval_reviewer_unavailable" in str(out)


@pytest.mark.asyncio
async def test_revoked_admitted_actor_is_a_typed_terminal_non_effect(
    env, monkeypatch,
):
    captured = []
    _review_verdict(monkeypatch)
    context = _context(execution="exec-actor-revoked", user="member-1")
    row_id = _request_approval(
        env, context, action="tasks.create",
        params={"title": "Revoked task", "board_id": "board-1"},
        user_id="member-1")
    agent = _agent(captured)

    # The terminal record is one insert of the FINAL state. A claim followed
    # by a CAS commit is interruptible (a stranded `claimed` row would later
    # read as unresolved), so the refusal path must not use those seams.
    transition_calls = []
    real_claim = claims.claim_generic_operation
    real_mark = claims.mark_status

    def _spy_claim(**kwargs):
        transition_calls.append("claim")
        return real_claim(**kwargs)

    def _spy_mark(*args, **kwargs):
        transition_calls.append("mark")
        return real_mark(*args, **kwargs)

    monkeypatch.setattr(claims, "claim_generic_operation", _spy_claim)
    monkeypatch.setattr(claims, "mark_status", _spy_mark)

    async def approve_then_revoke_actor(action_id):
        await _approve(action_id, reviewer="lead-1")
        with env.Session() as db:
            actor = db.get(User, "member-1")
            actor.status = "disabled"
            actor.is_active = False
            db.commit()
        return True

    agent._wait_for_approval = approve_then_revoke_actor
    out = await agent._step_act_unaudited(
        "tasks.create",
        {"title": "Revoked task", "board_id": "board-1"},
        context=context)
    assert captured == []
    assert transition_calls == []
    assert isinstance(out, dict)
    assert out["terminal_authority_denial"] is True
    assert out["status"] == "failed_before_effect"
    assert out["effect_state"] == "none"
    assert out["requires_reconciliation"] is False
    assert out["error_class"] == "approval_actor_inactive"
    # The terminal refusal is a final no-effect decision for this logical
    # operation, so the existing durable claim arbiter records it. No handler
    # ran and no dispatched/succeeded claim exists.
    rows = _claim_rows(env, "exec-actor-revoked")
    assert len(rows) == 1, rows
    assert rows[0].status == claims.FAILED_BEFORE_EFFECT
    assert rows[0].operation_type == "generic:agent:tasks.create"
    assert rows[0].operation_id.startswith("auto-")
    assert rows[0].idempotency_key == rows[0].operation_id
    first_id = rows[0].id

    # A repeated refusal for the same logical operation is the same terminal
    # decision: it must not duplicate, transition, or overwrite the arbiter.
    repeats = _agent([])
    repeats._record_refused_mutation_claim(
        "tasks.create",
        {"title": "Revoked task", "board_id": "board-1"},
        context)
    repeated = _claim_rows(env, "exec-actor-revoked")
    assert len(repeated) == 1, repeated
    assert repeated[0].id == first_id
    assert repeated[0].status == claims.FAILED_BEFORE_EFFECT


@pytest.mark.asyncio
async def test_tampered_or_revoked_approval_is_refused_before_dispatch(
    env, monkeypatch,
):
    captured = []
    _review_verdict(monkeypatch)
    context = _context(execution="exec-tamper")

    tamper_id = _request_approval(
        env, context, action="read_data", params={"query": "tamper"})
    tamper_agent = _agent(captured)

    async def tamper_then_approve(action_id):
        await _approve(action_id, modified={"query": "tamper-approved"})
        with env.Session() as db:
            row = db.get(HITLAction, action_id)
            row.params = {"query": "tamper-replaced"}
            db.commit()
        return True

    tamper_agent._wait_for_approval = tamper_then_approve
    out = await tamper_agent._step_act_unaudited(
        "read_data", {"query": "tamper"}, context=context)
    assert captured == []
    assert "approval_material_tampered" in str(out)

    revoked_id = _request_approval(
        env, context, action="read_data", params={"query": "revoked"})
    revoked_agent = _agent(captured)

    async def approve_then_revoke(action_id):
        await _approve(action_id)
        with env.Session() as db:
            row = db.get(HITLAction, action_id)
            row.status = HITLActionStatus.REJECTED.value
            db.commit()
        return True

    revoked_agent._wait_for_approval = approve_then_revoke
    out = await revoked_agent._step_act_unaudited(
        "read_data", {"query": "revoked"}, context=context)
    assert captured == []
    assert "approval_not_approved" in str(out)


@pytest.mark.asyncio
async def test_rejected_approval_never_dispatches(env, monkeypatch):
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-cancel")

    async def reject(action_id):
        await _reject(action_id)
        return False

    agent._wait_for_approval = reject
    out = await agent._step_act_unaudited(
        "read_data", {"query": "cancel"}, context=context)
    assert captured == []
    assert "REJECTED" in str(out)


@pytest.mark.asyncio
async def test_actor_scope_and_mutating_refusals_are_non_effects(
    env, monkeypatch,
):
    captured = []
    _review_verdict(monkeypatch)
    owner_context = _context(execution="exec-owner", user="lead-1")
    owner_row = _request_approval(
        env, owner_context, action="tasks.create",
        params={"title": "Owned task", "board_id": "board-1"},
        user_id="lead-1")
    await _approve(owner_row)
    agent = _agent(captured)
    out = await agent._step_act_unaudited(
        "tasks.create",
        {"title": "Owned task", "board_id": "board-1"},
        context=_context(execution="exec-owner", user="member-1"),
        pre_approved=True, approval_action_id=owner_row)
    assert captured == []
    assert isinstance(out, dict)
    assert out["status"] == "failed_before_effect"
    assert out["action_result"] == "not_applied"
    assert out["effect_state"] == "none"
    assert out["requires_reconciliation"] is False
    assert "approval_actor_mismatch" in out["error_class"]


@pytest.mark.asyncio
async def test_changed_risk_or_budget_refuses_before_dispatch(env, monkeypatch):
    captured = []
    context = _context(execution="exec-risk")
    reviewed = _requires_review()
    calls = {"n": 0}

    async def risk_check(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return dict(reviewed)
        return _requires_review(action_complexity=4)

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", risk_check)
    risk_row = _request_approval(
        env, context, action="read_data", params={"query": "risk"})
    risk_agent = _agent(captured)

    async def approve(action_id):
        await _approve(action_id)
        return True

    risk_agent._wait_for_approval = approve
    out = await risk_agent._step_act_unaudited(
        "read_data", {"query": "risk"}, context=context)
    assert captured == []
    assert "action complexity" in str(out)

    budget_calls = {"n": 0}

    async def budget_check(*_args, **_kwargs):
        budget_calls["n"] += 1
        if budget_calls["n"] == 1:
            return dict(reviewed)
        return {
            "allowed": False,
            "requires_human_approval": False,
            "status_code": "BUDGET_EXCEEDED",
            "reason": "Budget exhausted",
        }

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", budget_check)
    budget_context = _context(execution="exec-budget")
    budget_row = _request_approval(
        env, budget_context, action="read_data", params={"query": "budget"})
    budget_agent = _agent(captured)
    budget_agent._wait_for_approval = approve
    out = await budget_agent._step_act_unaudited(
        "read_data", {"query": "budget"}, context=budget_context)
    assert captured == []
    assert "Budget exhausted" in str(out)


# ---------------------------------------------------------------------------
# Operation claims: no resend of a prior uncertain effect, restart replay
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prior_uncertain_operation_is_reconciled_not_resent(
    env, monkeypatch,
):
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-prior", operation_id="op-prior")
    effective = {"title": "Prior task", "board_id": "board-1"}
    with env.Session() as db:
        db.add(TaskOperationRecord(
            id="row-prior",
            workspace_id="ws-test",
            tenant_id="default",
            run_id="exec-prior",
            idempotency_key="op-prior",
            payload_sha256=claims.operation_payload_sha256(
                workspace_id="ws-test",
                tenant_id="default",
                actor_id="lead-1",
                actor_kind="user",
                agent_id="agent-lead-1",
                execution_id="exec-prior",
                execution_kind="execution",
                action="tasks.create",
                frozen_args=effective,
            ),
            operation_id="op-prior",
            operation_type="generic:agent:tasks.create",
            status=claims.UNCERTAIN_EFFECT,
        ))
        db.commit()

    row_id = _request_approval(
        env, context, action="tasks.create", params=effective)
    await _approve(row_id)
    out = await agent._step_act_unaudited(
        "tasks.create", effective, context=context,
        pre_approved=True, approval_action_id=row_id,
        approval_reviewed_check=_requires_review())
    assert captured == []
    assert isinstance(out, dict)
    assert out["requires_reconciliation"] is True, {
        k: out.get(k) for k in (
            "status", "error_class", "message", "operation_id",
            "durable_claim", "effect_state")}
    assert out["retryable"] is False
    assert "reconcile" in str(out.get("message") or "").lower()


@pytest.mark.asyncio
async def test_restart_replays_durable_receipt_without_second_dispatch(
    env, monkeypatch,
):
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-restart")
    original = {"title": "Original task", "board_id": "board-1"}
    effective = {"title": "Approved task", "board_id": "board-2"}
    row_id = _request_approval(
        env, context, action="tasks.create", params=original)
    await _approve(row_id, modified=effective)

    first = await agent._step_act_unaudited(
        "tasks.create", original, context=context,
        pre_approved=True, approval_action_id=row_id,
        approval_reviewed_check=_requires_review())
    assert len(captured) == 1
    assert captured[0]["args"] == effective

    # Same durable approval + same reviewed request after a restart: the
    # effective material is consumed again but no second handler call is made.
    second = await agent._step_act_unaudited(
        "tasks.create", original, context=context,
        pre_approved=True, approval_action_id=row_id,
        approval_reviewed_check=_requires_review())
    assert len(captured) == 1
    assert isinstance(second, dict)
    assert second.get("requires_reconciliation") is True
    assert second.get("retryable") is False
    assert first is not None


# ---------------------------------------------------------------------------
# Parallel consumer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_batch_consumes_per_action_approved_material(
    env, monkeypatch,
):
    captured = []
    agent = _agent(captured)
    context = _context(execution="exec-parallel")

    async def check(_service, _agent_id, action_type, **_kwargs):
        if action_type == "read_data":
            return _requires_review()
        return {"allowed": True, "requires_human_approval": False,
                "reason": "Maturity check passed."}

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", check)
    monkeypatch.setattr(
        "core.hallucination_config.is_parallel_tools_enabled",
        lambda: True)
    monkeypatch.setattr(
        "core.hallucination_config.get_max_parallel_tools", lambda: 4)

    async def approve_all(action_ids):
        for action_id in action_ids:
            await _approve(
                action_id, modified={"query": "parallel-corrected"})
        return True

    agent._wait_for_all_approvals = approve_all
    actions = [
        ToolCall(tool="read_data", params={"query": "parallel-original"}),
        ToolCall(tool="read_other", params={"query": "untouched"}),
    ]
    records = await agent._execute_parallel_tools(actions, context, None)

    assert len(captured) == 2
    by_tool = {item["tool"]: item["args"] for item in captured}
    assert by_tool["read_data"] == {"query": "parallel-corrected"}
    assert by_tool["read_other"] == {"query": "untouched"}

    assert len(records) == 2
    approved_record = next(
        record for record in records if record["tool_name"] == "read_data")
    # The model's original request stays on the record; the exact dispatched
    # effective payload is retained in the dispatch evidence.
    assert approved_record["params"] == {"query": "parallel-original"}
    approval_evidence = approved_record["dispatch_evidence"]["approval"]
    assert approval_evidence["effective_params"] == {
        "query": "parallel-corrected"}
    assert approval_evidence["material_changed"] is True
    assert approved_record["dispatch_evidence"]["dispatched"] is True


# ---------------------------------------------------------------------------
# Root edge regressions: legacy receipt, requester authority, awaited fences
# ---------------------------------------------------------------------------

def _strip_parameter_history(env, action_id: str) -> None:
    """Turn a decided row into a historical row with no recorded original."""
    with env.Session() as db:
        row = db.get(HITLAction, action_id)
        snapshot = dict(row.context_snapshot or {})
        snapshot.pop("parameter_history", None)
        row.context_snapshot = snapshot
        db.commit()


@pytest.mark.asyncio
async def test_legacy_unchanged_receipt_dispatches_after_cold_read(
    env, monkeypatch,
):
    """Root edge 1: unchanged historical approval must still dispatch.

    The row has an approved status but no parameter history (the receipt
    predates it). Only the exact unchanged expected/effective material may
    run, and the unknown original must stay explicit rather than be
    reconstructed from the rewritten payload. The engine is disposed before
    consumption, so this is a cold durable read (process-restart shape), not
    a warm identity-map read.
    """
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-legacy-cold")
    evidence: dict = {}

    async def approve(action_id):
        await _approve(action_id)
        _strip_parameter_history(env, action_id)
        env.engine.dispose()
        return True

    agent._wait_for_approval = approve
    out = await agent._step_act_unaudited(
        "read_data", {"query": "legacy-unchanged"}, context=context,
        dispatch_evidence=evidence)

    assert len(captured) == 1
    assert captured[0]["args"] == {"query": "legacy-unchanged"}
    assert out == {"success": True}
    approval = evidence["approval"]
    assert approval["original_known"] is False
    assert approval["original_params"] is None
    assert approval["material_changed"] is False
    assert approval["reviewed_params"] == {"query": "legacy-unchanged"}


@pytest.mark.asyncio
async def test_legacy_edited_receipt_without_original_proof_is_refused(
    env, monkeypatch,
):
    """Root edge 1 (negative): a legacy edit has no reviewed original proof."""
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-legacy-edited")

    async def approve(action_id):
        await _approve(
            action_id, modified={"query": "edited-after-review"})
        _strip_parameter_history(env, action_id)
        return True

    agent._wait_for_approval = approve
    out = await agent._step_act_unaudited(
        "read_data", {"query": "original-request"}, context=context)

    assert captured == []
    assert "approval_material_unreviewed_change" in str(out)


@pytest.mark.asyncio
async def test_malformed_approval_material_is_refused(env, monkeypatch):
    """Malformed authority records are refusals, never a legacy downgrade."""
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-malformed")

    async def run(row_id, reviewed=None):
        return await agent._step_act_unaudited(
            "read_data", reviewed or {"query": "malformed"}, context=context,
            pre_approved=True, approval_action_id=row_id,
            approval_reviewed_check=_requires_review())

    # (a) The live params column diverged from the reviewed receipt into a
    # non-mapping value: execution material is not the receipt.
    bad_params = _request_approval(
        env, context, action="read_data", params={"query": "bad-params"})
    await _approve(bad_params)
    with env.Session() as db:
        db.get(HITLAction, bad_params).params = ["not", "a", "mapping"]
        db.commit()
    out = await run(bad_params, reviewed={"query": "bad-params"})
    assert captured == []
    assert "approval_material_tampered" in str(out)

    # (b) A corrupt execution-context snapshot must not silently look like
    # an old row that never recorded history.
    bad_snapshot = _request_approval(
        env, context, action="read_data", params={"query": "bad-snapshot"})
    await _approve(bad_snapshot)
    with env.Session() as db:
        db.get(HITLAction, bad_snapshot).context_snapshot = ["corrupt"]
        db.commit()
    out = await run(bad_snapshot, reviewed={"query": "bad-snapshot"})
    assert captured == []
    assert "approval_material_unavailable" in str(out)

    # (c) The receipt exists but its effective payload is unreadable.
    bad_receipt = _request_approval(
        env, context, action="read_data", params={"query": "bad-receipt"})
    await _approve(bad_receipt)
    with env.Session() as db:
        row = db.get(HITLAction, bad_receipt)
        snapshot = dict(row.context_snapshot or {})
        history = [dict(entry) for entry in snapshot["parameter_history"]]
        history[-1]["approved_params"] = "not-a-parameter-mapping"
        snapshot["parameter_history"] = history
        row.context_snapshot = snapshot
        db.commit()
    out = await run(bad_receipt, reviewed={"query": "bad-receipt"})
    assert captured == []
    assert "approval_material_unavailable" in str(out)

    # (d) A legacy row (no receipt) whose live params are unreadable.
    bad_legacy = _request_approval(
        env, context, action="read_data", params={"query": "bad-legacy"})
    await _approve(bad_legacy)
    with env.Session() as db:
        row = db.get(HITLAction, bad_legacy)
        snapshot = dict(row.context_snapshot or {})
        snapshot.pop("parameter_history", None)
        row.context_snapshot = snapshot
        row.params = ["not", "a", "mapping"]
        db.commit()
    out = await run(bad_legacy, reviewed={"query": "bad-legacy"})
    assert captured == []
    assert "approval_material_unavailable" in str(out)


@pytest.mark.asyncio
async def test_requester_tenant_move_refuses_dispatch(env, monkeypatch):
    """Root edge 2: a requester that moved tenant after review is refused.

    Exact root counter shape: member-1 owns the request, lead-1 approves a
    corrected query, then member-1 moves to a REAL other tenant while the
    workspace is unchanged. The current context still names the old tenant,
    so only a fresh durable actor resolution can see the drift.
    """
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-tenant-move", user="member-1")
    row_id = _request_approval(
        env, context, action="read_data", params={"query": "original"},
        user_id="member-1")

    async def approve(action_id):
        await _approve(
            action_id, reviewer="lead-1", modified={"query": "corrected"})
        with env.Session() as db:
            db.add(Tenant(
                id="moved-tenant", name="Moved", subdomain="moved"))
            actor = db.get(User, "member-1")
            actor.tenant_id = "moved-tenant"
            db.commit()
        return True

    agent._wait_for_approval = approve
    out = await agent._step_act_unaudited(
        "read_data", {"query": "original"}, context=context)

    assert captured == []
    assert isinstance(out, dict)
    assert out["terminal_authority_denial"] is True
    assert out["denial_kind"] == "approval_actor_scope_denied"
    assert out["status"] == "failed_before_effect"
    assert out["action_result"] == "not_applied"
    assert out["effect_state"] == "none"


@pytest.mark.asyncio
async def test_requester_null_tenant_matches_default_scope(env, monkeypatch):
    """NULL and the literal ``default`` tenant remain the same scope."""
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-null-tenant", user="member-1")
    row_id = _request_approval(
        env, context, action="read_data", params={"query": "null-tenant"},
        user_id="member-1")

    async def approve(action_id):
        await _approve(action_id)
        with env.Session() as db:
            db.get(User, "member-1").tenant_id = None
            db.commit()
        return True

    agent._wait_for_approval = approve
    await agent._step_act_unaudited(
        "read_data", {"query": "null-tenant"}, context=context)

    assert len(captured) == 1
    assert captured[0]["args"] == {"query": "null-tenant"}


@pytest.mark.asyncio
async def test_missing_or_deleted_requester_is_refused(env, monkeypatch):
    """A named caller that no longer resolves is a terminal non-effect."""
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)

    # (a) The durable owner row never existed.
    missing_context = _context(
        execution="exec-missing-actor", user="ghost-1")
    missing_row = _request_approval(
        env, missing_context, action="read_data", params={"query": "ghost"},
        user_id="ghost-1")
    await _approve(missing_row)
    out = await agent._step_act_unaudited(
        "read_data", {"query": "ghost"}, context=missing_context,
        pre_approved=True, approval_action_id=missing_row,
        approval_reviewed_check=_requires_review())
    assert captured == []
    assert isinstance(out, dict)
    assert out["terminal_authority_denial"] is True
    assert out["denial_kind"] == "approval_actor_unavailable"
    assert out["effect_state"] == "none"

    # (b) The admitted owner row is deleted after the human decision.
    deleted_context = _context(
        execution="exec-deleted-actor", user="member-1")
    deleted_row = _request_approval(
        env, deleted_context, action="read_data", params={"query": "deleted"},
        user_id="member-1")
    await _approve(deleted_row)
    with env.Session() as db:
        db.delete(db.get(User, "member-1"))
        db.commit()
    out = await agent._step_act_unaudited(
        "read_data", {"query": "deleted"}, context=deleted_context,
        pre_approved=True, approval_action_id=deleted_row,
        approval_reviewed_check=_requires_review())
    assert captured == []
    assert isinstance(out, dict)
    assert out["terminal_authority_denial"] is True
    assert out["denial_kind"] == "approval_actor_unavailable"


@pytest.mark.asyncio
async def test_ownerless_internal_approval_keeps_legacy_contract(
    env, monkeypatch,
):
    """Declared background/bridge contract: no named actor, exact material.

    A direct internal caller files an approval without an admitted user. That
    legacy path is preserved (the reviewer and exact material still bind),
    while a named-but-missing caller above is refused.
    """
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = {
        "workspace_id": "ws-test",
        "tenant_id": "default",
        "execution_id": "exec-background",
    }
    row_id = _request_approval(
        env, context, action="read_data", params={"query": "background"},
        user_id=None)

    async def approve(action_id):
        await _approve(action_id)
        return True

    agent._wait_for_approval = approve
    await agent._step_act_unaudited(
        "read_data", {"query": "background"}, context=context)

    assert len(captured) == 1
    assert captured[0]["args"] == {"query": "background"}


@pytest.mark.asyncio
async def test_authority_outage_refuses_without_dispatch(env, monkeypatch):
    """An unreadable authority store is a refusal, never a pass-through."""
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    context = _context(execution="exec-outage")
    row_id = _request_approval(
        env, context, action="read_data", params={"query": "outage"})
    evidence: dict = {}
    state = {"outage": False}
    real_factory = env.service_session

    def flaky_factory(*_args, **_kwargs):
        if state["outage"]:
            raise RuntimeError("authority store unavailable")
        return real_factory()

    monkeypatch.setattr(
        "core.generic_agent.get_db_session", flaky_factory)

    async def approve(action_id):
        await _approve(action_id)
        state["outage"] = True
        return True

    agent._wait_for_approval = approve
    out = await agent._step_act_unaudited(
        "read_data", {"query": "outage"}, context=context,
        dispatch_evidence=evidence)

    assert captured == []
    assert "approval_authority_unavailable" in str(out)
    assert evidence["dispatched"] is False


@pytest.mark.asyncio
async def test_scope_change_during_governance_revalidation_is_refused(
    env, monkeypatch,
):
    """The awaited re-check is a real window; the last-safe-point fence wins.

    A tenant move that happens while the independent governance verdict is
    being awaited (after the first material read) must not reach the handler.
    """
    captured = []
    agent = _agent(captured)
    context = _context(execution="exec-await-tenant", user="member-1")
    row_id = _request_approval(
        env, context, action="read_data", params={"query": "await-original"},
        user_id="member-1")
    calls = {"n": 0}

    async def governance(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            with env.Session() as db:
                db.add(Tenant(
                    id="await-moved-tenant", name="Await Moved",
                    subdomain="await-moved"))
                actor = db.get(User, "member-1")
                actor.tenant_id = "await-moved-tenant"
                db.commit()
        return dict(_requires_review())

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", governance)

    async def approve(action_id):
        await _approve(action_id, modified={"query": "await-corrected"})
        return True

    agent._wait_for_approval = approve
    out = await agent._step_act_unaudited(
        "read_data", {"query": "await-original"}, context=context)

    assert calls["n"] >= 2
    assert captured == []
    assert isinstance(out, dict)
    assert out["terminal_authority_denial"] is True
    assert out["denial_kind"] == "approval_actor_scope_denied"


@pytest.mark.asyncio
async def test_revocation_or_tamper_during_governance_revalidation_is_refused(
    env, monkeypatch,
):
    """A decision/payload change during the awaited re-check is refused."""
    captured = []
    agent = _agent(captured)
    _review_verdict(monkeypatch)
    seen: dict = {}

    async def approve(action_id):
        seen["id"] = action_id
        await _approve(action_id)
        return True

    agent._wait_for_approval = approve

    # (a) revoked while the governance verdict is being awaited.
    revoked_context = _context(execution="exec-await-revoked")
    revoked_calls = {"n": 0}

    async def revoke_governance(*_args, **_kwargs):
        revoked_calls["n"] += 1
        if revoked_calls["n"] >= 2:
            with env.Session() as db:
                db.get(
                    HITLAction, seen["id"]).status = (
                        HITLActionStatus.REJECTED.value)
                db.commit()
        return dict(_requires_review())

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async",
        revoke_governance)

    out = await agent._step_act_unaudited(
        "read_data", {"query": "revoked"}, context=revoked_context)
    assert captured == []
    assert "approval_not_approved" in str(out)

    # (b) payload tampered while the governance verdict is being awaited.
    tamper_context = _context(execution="exec-await-tamper")
    tamper_calls = {"n": 0}

    async def tamper_governance(*_args, **_kwargs):
        tamper_calls["n"] += 1
        if tamper_calls["n"] >= 2:
            with env.Session() as db:
                db.get(HITLAction, seen["id"]).params = {
                    "query": "tampered-after-await"}
                db.commit()
        return dict(_requires_review())

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async",
        tamper_governance)
    out = await agent._step_act_unaudited(
        "read_data", {"query": "tamper"}, context=tamper_context)
    assert captured == []
    assert "approval_material_tampered" in str(out)


@pytest.mark.asyncio
async def test_parallel_batch_fences_scope_change_during_revalidation(
    env, monkeypatch,
):
    """The parallel consumer uses the same post-await safe-point fence."""
    captured = []
    agent = _agent(captured)
    context = _context(execution="exec-parallel-await", user="member-1")
    read_calls = {"n": 0}

    async def check(_service, _agent_id, action_type, **_kwargs):
        if action_type == "read_data":
            read_calls["n"] += 1
            if read_calls["n"] >= 2:
                with env.Session() as db:
                    db.add(Tenant(
                        id="parallel-moved-tenant", name="Parallel Moved",
                        subdomain="parallel-moved"))
                    actor = db.get(User, "member-1")
                    actor.tenant_id = "parallel-moved-tenant"
                    db.commit()
            return dict(_requires_review())
        return {"allowed": True, "requires_human_approval": False,
                "reason": "Maturity check passed."}

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async", check)
    monkeypatch.setattr(
        "core.hallucination_config.is_parallel_tools_enabled", lambda: True)
    monkeypatch.setattr(
        "core.hallucination_config.get_max_parallel_tools", lambda: 4)

    async def approve_all(action_ids):
        for action_id in action_ids:
            await _approve(action_id, modified={"query": "parallel-await"})
        return True

    agent._wait_for_all_approvals = approve_all
    actions = [
        ToolCall(tool="read_data", params={"query": "parallel-original"}),
        ToolCall(tool="read_other", params={"query": "untouched"}),
    ]
    records = await agent._execute_parallel_tools(actions, context, None)

    by_tool = {item["tool"]: item["args"] for item in captured}
    assert "read_data" not in by_tool
    assert by_tool["read_other"] == {"query": "untouched"}

    records_by_tool = {record["tool_name"]: record for record in records}
    refused = records_by_tool["read_data"]
    assert refused["dispatch_evidence"]["dispatched"] is False
    assert refused["output"]["denial_kind"] == "approval_actor_scope_denied"
    assert records_by_tool["read_other"]["dispatch_evidence"][
        "dispatched"] is True
