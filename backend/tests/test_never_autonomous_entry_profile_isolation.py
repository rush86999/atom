"""REAL-ENTRY task-profile isolation regressions.

A nested autonomous entry must own its task-profile boundary. Before the
fix, ``GenericAgent.execute`` / ``WorkflowEngine._run_execution`` skipped the
bind when BOTH the classifier and the canonical unknown-profile fallback
failed, so task admission read the ANCESTOR's still-bound profile:

* parent ``marketing`` + child ``finance`` under an enabled finance rule was
  admitted with zero human reviews, and
* a cross-owner ancestor profile selected the wrong rule owner (the profile's
  owner instead of the actor the child actually runs for).

The fix masks the ancestor profile/clearance for the whole entry, binds only
a profile this entry built (or the canonical unknown profile), and restores
the caller's ContextVar tokens + dispatch-dict entries on success, exception
and cancellation. Tool checks inside the SAME task still inherit that task's
profile; only a NEW entry boundary is isolated.

These are production-entry regressions (``execute`` / ``_run_execution``),
not helper tests: real SQLite, real rule matching and real durable HITL rows.
No review is fabricated — unapproved cases assert a pending row and zero
model/step calls. Approved-path evidence stays in the existing five files,
which use the real ``authorize_task_admission_decision`` /
``claim_task_admission_decision`` seam.

Run with an isolated scratch DB (never the live dev DB):

    TESTING=1 PYTEST_VERSION=ci PYTHON_DOTENV_DISABLED=1 \
    DATABASE_URL=sqlite:////tmp/atom_never_profile_isolation.db \
    /private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python -m pytest \
      tests/test_never_autonomous_entry_profile_isolation.py -q
"""
from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.generic_agent as real_generic
from core import autonomy_policy as ap
from core.agent_governance_service import AgentGovernanceService
from core.models import (
    AgentRegistry,
    Base,
    HITLAction,
    HITLActionStatus,
    User,
)
from core.task_classification import (
    TASK_PROFILE_CONTEXT_KEY,
    bind_task_profile,
    build_task_profile,
    current_task_profile,
    reset_task_profile,
)

FINANCE_JAN = (
    "Analyse the January finance invoice expense and accounting records "
    "and summarize the reconciled totals for the finance team"
)
FINANCE_FEB = (
    "Analyse the February finance invoice expense and accounting records "
    "and summarize the reconciled totals for the finance team"
)
MARKETING_TEXT = (
    "Write a short marketing blog article and summarize the campaign notes"
)


@pytest.fixture()
def store(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'atom_never_profile_isolation.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    try:
        yield engine, Session, db
    finally:
        db.close()
        engine.dispose()


@contextlib.contextmanager
def _session_for(db):
    yield db


@pytest.fixture()
def use_db(store, monkeypatch):
    """Route services/agents at the scratch session (never the live DB)."""
    _engine, _Session, db = store
    for target in (
        "core.generic_agent.get_db_session",
        "core.database.get_db_session",
        "core.workflow_engine.get_db_session",
        "core.intervention_service.get_db_session",
    ):
        monkeypatch.setattr(target, lambda db=db: _session_for(db))
    return db


def _agent(db, agent_id="hire-1", user_id="u1", status="autonomous"):
    db.add(AgentRegistry(
        id=agent_id,
        name=agent_id,
        category="Operations",
        role="agent",
        type="personal",
        capabilities=[],
        module_path="operations.test",
        class_name="TestAgent",
        user_id=user_id,
        status=status,
        confidence_score=0.95,
        configuration={},
        tenant_id=None,
        workspace_id="default",
    ))
    db.add(User(
        id=user_id,
        email=f"{user_id}@example.test",
        hashed_password="x",
        first_name="Test",
        last_name="Owner",
        role="team_lead",
        status="active",
        is_active=True,
        workspace_id=None,
        tenant_id=None,
    ))
    db.commit()


def _generic_agent(db):
    row = db.query(AgentRegistry).filter(
        AgentRegistry.id == "hire-1").first()
    with patch("core.generic_agent.WorldModelService"), \
         patch("core.generic_agent.ReflectionService"), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service"), \
         patch("core.generic_agent.LLMService"):
        agent = real_generic.GenericAgent(row, workspace_id="default")
    agent.world_model = MagicMock()
    agent.world_model.recall_experiences = AsyncMock(
        return_value={"experiences": []})
    agent.world_model.record_experience = AsyncMock(return_value=None)
    agent.reflection_service = MagicMock()
    agent.reflection_service.add_critique = AsyncMock()
    return agent


def _finance_rule(db, user_id="u1"):
    return ap.create_never_rule(
        db, user_id, name="Always review finance",
        match={"domain": ["finance"]})


def _hitl_rows(db):
    return db.query(HITLAction).filter(
        HITLAction.action_type == ap.NEVER_TASK_ADMISSION_ACTION).all()


def _double_builder_failure(monkeypatch, workflow=False):
    target = ("core.task_classification.build_workflow_task_profile"
              if workflow else "core.task_classification.build_task_profile")
    monkeypatch.setattr(
        target, MagicMock(side_effect=RuntimeError("synthetic builder failure")))
    monkeypatch.setattr(
        "core.task_classification.build_unknown_task_profile",
        MagicMock(side_effect=RuntimeError("synthetic fallback failure")))


def _marketing_profile(user_id="u1"):
    profile = build_task_profile(MARKETING_TEXT, user_id=user_id)
    assert profile.domain != "finance"
    return profile


def _finance_profile(text=FINANCE_JAN, user_id="u1"):
    profile = build_task_profile(text, user_id=user_id)
    assert profile.domain == "finance"
    return profile


@pytest.fixture()
def workflow_engine(monkeypatch):
    from core.workflow_engine import WorkflowEngine

    engine = WorkflowEngine()
    state_manager = MagicMock()
    state_manager.update_execution_status = AsyncMock()
    state_manager.get_execution_state = AsyncMock(
        return_value={"steps": {}, "outputs": {}})
    state_manager.update_step_status = AsyncMock()
    engine.state_manager = state_manager
    ws = MagicMock()
    ws.notify_workflow_status = AsyncMock()
    monkeypatch.setattr(
        "core.workflow_engine.get_connection_manager", lambda: ws)
    monkeypatch.setattr(engine, "_notify_workflow_paused", MagicMock())
    monkeypatch.setattr(engine, "_publish_orchestration_event", MagicMock())
    monkeypatch.setattr(
        "core.workflow_engine.ServiceFactory.get_governance_service",
        staticmethod(lambda db, workspace_id=None, tenant_id=None:
                     AgentGovernanceService(
                         db, workspace_id=workspace_id,
                         tenant_id=tenant_id)))
    return engine


def _workflow(workflow_id: str, text: str, created_by="u1", steps=None):
    return {
        "id": workflow_id,
        "name": text,
        "description": text,
        "agent_id": "hire-1",
        "created_by": created_by,
        "steps": steps if steps is not None else [],
    }


# ---------------------------------------------------------------------------
# GenericAgent.execute — the real agent entry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generic_nested_double_builder_failure_blocks_without_ancestor(
    store, use_db, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)
    model_calls = []

    async def _model_leaf(*args, **kwargs):
        model_calls.append(kwargs)
        raise AssertionError("model leaf must not run during a policy outage")

    monkeypatch.setattr(
        real_generic.GenericAgent, "_react_step", _model_leaf)
    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))
    _double_builder_failure(monkeypatch)

    # Nested call: the SAME dispatch dict is reused by the parent task.
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-generic-double"}
    parent = _marketing_profile()
    parent_token = bind_task_profile(context, parent)
    try:
        result = await agent.execute(FINANCE_JAN, context)

        # The ancestor's marketing profile did NOT satisfy the finance rule
        # (and, before the fix, was consumed as a valid finance match).
        assert result["status"] == "blocked"
        assert result["requires_human_approval"] is True
        assert "could not be bound" in result["output"]
        assert model_calls == []
        assert agent.world_model.recall_experiences.await_count == 0

        rows = _hitl_rows(db)
        assert len(rows) == 1
        assert rows[0].status == HITLActionStatus.PENDING.value
        assert rows[0].params["task_profile"] is None
        assert rows[0].params["owner_user_id"] == "u1"

        # Parent task context is intact for the next nested tool call.
        assert current_task_profile() is parent
        assert context[TASK_PROFILE_CONTEXT_KEY] is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_generic_cross_owner_double_failure_uses_acting_actor(
    store, use_db, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db, user_id="u1")
    _finance_rule(db, user_id="u1")
    agent = _generic_agent(db)
    model_calls = []

    async def _model_leaf(*args, **kwargs):
        model_calls.append(kwargs)
        raise AssertionError("model leaf must not run during a policy outage")

    monkeypatch.setattr(
        real_generic.GenericAgent, "_react_step", _model_leaf)
    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))
    _double_builder_failure(monkeypatch)

    # Ancestor profile belongs to u2; the current admitted actor is u1.
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-generic-cross-owner"}
    parent = build_task_profile(MARKETING_TEXT, user_id="u2")
    assert parent.owner_user_id == "u2"
    parent_token = bind_task_profile(context, parent)
    try:
        result = await agent.execute(FINANCE_JAN, context)

        assert result["status"] == "blocked"
        assert model_calls == []
        rows = _hitl_rows(db)
        assert len(rows) == 1
        # u1 owns the enabled finance rule. The stale u2 profile must not
        # select the owner (old code returned "unaffected" and ran).
        assert rows[0].params["owner_user_id"] == "u1"
        assert rows[0].params["rule_ids"]
        assert current_task_profile() is parent
        assert context[TASK_PROFILE_CONTEXT_KEY] is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_generic_nested_valid_child_still_requires_review(
    store, use_db, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)
    rule = _finance_rule(db)
    agent = _generic_agent(db)
    model_calls = []

    async def _model_leaf(*args, **kwargs):
        model_calls.append(kwargs)
        raise AssertionError("model leaf must not run before review")

    monkeypatch.setattr(
        real_generic.GenericAgent, "_react_step", _model_leaf)
    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))

    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-generic-valid-child"}
    parent = _marketing_profile()
    parent_token = bind_task_profile(context, parent)
    try:
        result = await agent.execute(FINANCE_JAN, context)

        assert result["status"] == "awaiting_approval"
        assert model_calls == []
        rows = _hitl_rows(db)
        assert len(rows) == 1
        assert rows[0].params["rule_bindings"] == [
            {"id": rule["id"], "revision": 1}]
        # The FRESH child profile (not the ancestor marketing one) binds the
        # review and the policy owner.
        assert rows[0].params["task_profile"]["domain"] == "finance"
        assert rows[0].params["owner_user_id"] == "u1"
        assert current_task_profile() is parent
        assert context[TASK_PROFILE_CONTEXT_KEY] is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_generic_nested_nonmatch_proceeds_with_fresh_profile(
    store, use_db, monkeypatch,
):
    """A fresh classified child that is a true nonmatch must not be blocked."""
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)
    captured = {}

    async def _impl(task_input, context, step_callback=None):
        captured["profile"] = current_task_profile()
        captured["input"] = task_input
        return {"output": "ok", "status": "success", "steps": []}

    agent._execute_impl = _impl

    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-generic-nonmatch"}
    parent = _finance_profile()
    parent_token = bind_task_profile(context, parent)
    try:
        result = await agent.execute(MARKETING_TEXT, context)

        assert result["status"] == "success"
        assert _hitl_rows(db) == []
        # If the finance ancestor had leaked through, admission would have
        # paused before _execute_impl and this capture would be absent.
        assert captured["input"] == MARKETING_TEXT
        assert captured["profile"] is not parent
        assert captured["profile"].domain != "finance"
        assert current_task_profile() is parent
        assert context[TASK_PROFILE_CONTEXT_KEY] is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_generic_unknown_fallback_reviews_without_inheriting_parent(
    store, use_db, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)

    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))
    monkeypatch.setattr(
        "core.task_classification.build_task_profile",
        MagicMock(side_effect=RuntimeError("synthetic builder failure")))

    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-generic-unknown"}
    parent = _marketing_profile()
    parent_token = bind_task_profile(context, parent)
    try:
        result = await agent.execute(FINANCE_JAN, context)

        assert result["status"] == "awaiting_approval"
        rows = _hitl_rows(db)
        assert len(rows) == 1
        assert rows[0].params["task_profile"]["domain"] is None
        assert rows[0].params["task_profile"]["signals"][
            "classification_source"] == "unavailable"
        assert current_task_profile() is parent
        assert context[TASK_PROFILE_CONTEXT_KEY] is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_generic_entry_restores_parent_on_error(store, use_db):
    _engine, _Session, db = store
    _agent(db)
    agent = _generic_agent(db)

    async def _boom(task_input, context, step_callback=None):
        raise RuntimeError("synthetic execution failure")

    agent._execute_impl = _boom

    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-generic-error"}
    parent = _marketing_profile()
    parent_token = bind_task_profile(context, parent)
    try:
        with pytest.raises(RuntimeError, match="synthetic execution failure"):
            await agent.execute(MARKETING_TEXT, context)

        assert current_task_profile() is parent
        assert context[TASK_PROFILE_CONTEXT_KEY] is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_generic_entry_restores_parent_on_cancellation(store, use_db):
    _engine, _Session, db = store
    _agent(db)
    agent = _generic_agent(db)
    started = asyncio.Event()

    async def _blocking(task_input, context, step_callback=None):
        started.set()
        await asyncio.Event().wait()

    agent._execute_impl = _blocking

    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-generic-cancel"}
    parent = _marketing_profile()
    parent_token = bind_task_profile(context, parent)
    captured = {}

    async def _runner():
        try:
            await agent.execute(MARKETING_TEXT, context)
        except asyncio.CancelledError:
            captured["profile"] = current_task_profile()
            captured["context_key"] = context.get(TASK_PROFILE_CONTEXT_KEY)
            raise

    try:
        task = asyncio.create_task(_runner())
        await asyncio.wait_for(started.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # The entry's own context was restored before cancellation unwound.
        assert captured["profile"] is parent
        assert captured["context_key"] is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_generic_sequential_entries_do_not_share_profile_or_review(
    store, use_db, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)

    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))

    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-generic-sequential"}
    parent = _marketing_profile()
    parent_token = bind_task_profile(context, parent)
    try:
        jan = await agent.execute(FINANCE_JAN, context)
        assert jan["status"] == "awaiting_approval"
        assert current_task_profile() is parent
        assert context[TASK_PROFILE_CONTEXT_KEY] is parent

        feb = await agent.execute(FINANCE_FEB, context)
        assert feb["status"] == "awaiting_approval"
        assert current_task_profile() is parent
        assert context[TASK_PROFILE_CONTEXT_KEY] is parent

        rows = _hitl_rows(db)
        assert len(rows) == 2
        assert len({row.params["task_fingerprint"] for row in rows}) == 2
        assert all(
            row.params["task_profile"]["domain"] == "finance"
            for row in rows)
        assert all(
            row.params["owner_user_id"] == "u1" for row in rows)
        assert all(row.status == HITLActionStatus.PENDING.value
                   for row in rows)
    finally:
        reset_task_profile(parent_token)


# ---------------------------------------------------------------------------
# AtomMetaAgent.execute_unaudited — dict-scoped sibling entry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meta_double_builder_failure_drops_stale_dict_profile(
    store, use_db, monkeypatch,
):
    _engine, Session, db = store
    _agent(db)
    _finance_rule(db)
    from core.atom_meta_agent import AtomMetaAgent

    meta = object.__new__(AtomMetaAgent)
    meta.workspace_id = "default"
    meta.tenant_id = "default"
    meta.user = None
    model_calls = []

    async def _model_leaf(*args, **kwargs):
        model_calls.append(kwargs)
        raise AssertionError("model leaf must not run before task admission")

    monkeypatch.setattr(AtomMetaAgent, "_react_step", _model_leaf)
    monkeypatch.setattr(
        meta, "_wait_for_approval", AsyncMock(return_value=False))
    monkeypatch.setattr("core.atom_meta_agent.SessionLocal", Session)
    _double_builder_failure(monkeypatch)

    # A reused caller context still carries the parent task's dict profile.
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-meta-double"}
    parent = _marketing_profile()
    parent_token = bind_task_profile(context, parent)
    try:
        result = await meta.execute_unaudited(FINANCE_JAN, context)

        assert result["status"] == "awaiting_approval"
        assert model_calls == []
        rows = _hitl_rows(db)
        assert len(rows) == 1
        assert rows[0].params["task_profile"] is None
        assert rows[0].params["owner_user_id"] == "u1"
        # The shared MCP guard reads the dict; it must not still see the
        # parent's profile while this entry is running.
        assert TASK_PROFILE_CONTEXT_KEY not in context
    finally:
        reset_task_profile(parent_token)


# ---------------------------------------------------------------------------
# WorkflowEngine._run_execution — the real workflow entry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_nested_double_builder_failure_pauses_without_ancestor(
    store, use_db, workflow_engine, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    _double_builder_failure(monkeypatch, workflow=True)

    parent = _marketing_profile()
    parent_token = bind_task_profile(None, parent)
    try:
        workflow = _workflow(
            "wf-finance", "January finance invoice reconciliation")
        await workflow_engine._run_execution("exec-wf-double", workflow)

        rows = _hitl_rows(db)
        assert len(rows) == 1
        assert rows[0].status == HITLActionStatus.PENDING.value
        assert rows[0].params["task_profile"] is None
        assert rows[0].params["owner_user_id"] == "u1"
        workflow_engine.state_manager.update_execution_status.assert_awaited_with(
            "exec-wf-double", "PAUSED", error=ANY)
        assert current_task_profile() is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_workflow_cross_owner_double_failure_uses_workflow_creator(
    store, use_db, workflow_engine, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db, user_id="u1")
    _finance_rule(db, user_id="u1")
    _double_builder_failure(monkeypatch, workflow=True)

    parent = build_task_profile(MARKETING_TEXT, user_id="u2")
    assert parent.owner_user_id == "u2"
    parent_token = bind_task_profile(None, parent)
    try:
        workflow = _workflow(
            "wf-finance", "January finance invoice reconciliation",
            created_by="u1")
        await workflow_engine._run_execution("exec-wf-cross", workflow)

        rows = _hitl_rows(db)
        assert len(rows) == 1
        assert rows[0].params["owner_user_id"] == "u1"
        assert rows[0].params["rule_ids"]
        assert current_task_profile() is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_workflow_nested_valid_child_still_pauses_before_first_step(
    store, use_db, workflow_engine,
):
    _engine, _Session, db = store
    _agent(db)
    rule = _finance_rule(db)

    parent = _marketing_profile()
    parent_token = bind_task_profile(None, parent)
    try:
        workflow = _workflow(
            "wf-finance", "January finance invoice reconciliation",
            steps=[{"id": "s1", "service": "ai", "action": "analyze"}])
        await workflow_engine._run_execution("exec-wf-valid", workflow)

        rows = _hitl_rows(db)
        assert len(rows) == 1
        assert rows[0].params["rule_bindings"] == [
            {"id": rule["id"], "revision": 1}]
        assert rows[0].params["task_profile"]["domain"] == "finance"
        assert rows[0].params["owner_user_id"] == "u1"
        # No step executed: admission runs before the first step.
        workflow_engine.state_manager.update_step_status.assert_not_awaited()
        assert current_task_profile() is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_workflow_nested_nonmatch_proceeds_with_fresh_profile(
    store, use_db, workflow_engine, monkeypatch,
):
    """A fresh classified workflow nonmatch still executes (not always block)."""
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    monkeypatch.setattr(
        "core.workflow_engine.notifier",
        SimpleNamespace(
            notify_completion=AsyncMock(), notify_failure=AsyncMock()))
    monkeypatch.setattr(
        "core.student_learning_service.auto_observe", AsyncMock())
    monkeypatch.setattr(
        "core.analytics_engine.get_analytics_engine", lambda: MagicMock())

    parent = _finance_profile()
    parent_token = bind_task_profile(None, parent)
    try:
        workflow = _workflow("wf-marketing", MARKETING_TEXT)
        await workflow_engine._run_execution("exec-wf-nonmatch", workflow)

        assert _hitl_rows(db) == []
        workflow_engine.state_manager.update_execution_status.assert_awaited_with(
            "exec-wf-nonmatch", "COMPLETED")
        assert current_task_profile() is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_workflow_unknown_fallback_pauses_before_first_step(
    store, use_db, workflow_engine, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    monkeypatch.setattr(
        "core.task_classification.build_workflow_task_profile",
        MagicMock(side_effect=RuntimeError("synthetic builder failure")))

    parent = _marketing_profile()
    parent_token = bind_task_profile(None, parent)
    try:
        workflow = _workflow(
            "wf-finance", "January finance invoice reconciliation",
            steps=[{"id": "s1", "service": "ai", "action": "analyze"}])
        await workflow_engine._run_execution("exec-wf-unknown", workflow)

        rows = _hitl_rows(db)
        assert len(rows) == 1
        assert rows[0].params["task_profile"]["domain"] is None
        assert rows[0].params["task_profile"]["signals"][
            "classification_source"] == "unavailable"
        workflow_engine.state_manager.update_step_status.assert_not_awaited()
        assert current_task_profile() is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_workflow_entry_restores_parent_on_error(
    store, use_db, workflow_engine, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)

    async def _boom(execution_id, workflow):
        raise RuntimeError("synthetic workflow failure")

    monkeypatch.setattr(workflow_engine, "_run_execution_body", _boom)

    parent = _marketing_profile()
    parent_token = bind_task_profile(None, parent)
    try:
        with pytest.raises(RuntimeError, match="synthetic workflow failure"):
            await workflow_engine._run_execution(
                "exec-wf-error", _workflow("wf", MARKETING_TEXT))
        assert current_task_profile() is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_workflow_entry_restores_parent_on_cancellation(
    store, use_db, workflow_engine, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)
    started = asyncio.Event()

    async def _blocking(execution_id, workflow):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(workflow_engine, "_run_execution_body", _blocking)

    parent = _marketing_profile()
    parent_token = bind_task_profile(None, parent)
    captured = {}

    async def _runner():
        try:
            await workflow_engine._run_execution(
                "exec-wf-cancel", _workflow("wf", MARKETING_TEXT))
        except asyncio.CancelledError:
            captured["profile"] = current_task_profile()
            raise

    try:
        task = asyncio.create_task(_runner())
        await asyncio.wait_for(started.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert captured["profile"] is parent
    finally:
        reset_task_profile(parent_token)


@pytest.mark.asyncio
async def test_workflow_sequential_entries_do_not_share_review_or_profile(
    store, use_db, workflow_engine,
):
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)

    parent = _marketing_profile()
    parent_token = bind_task_profile(None, parent)
    try:
        await workflow_engine._run_execution(
            "exec-wf-jan",
            _workflow("wf-jan", "January finance invoice reconciliation"))
        assert current_task_profile() is parent

        await workflow_engine._run_execution(
            "exec-wf-feb",
            _workflow("wf-feb", "February finance invoice reconciliation"))
        assert current_task_profile() is parent

        rows = _hitl_rows(db)
        assert len(rows) == 2
        assert len({row.params["task_fingerprint"] for row in rows}) == 2
        assert all(
            row.params["task_profile"]["domain"] == "finance"
            for row in rows)
        assert all(
            row.params["owner_user_id"] == "u1" for row in rows)
        assert all(row.status == HITLActionStatus.PENDING.value
                   for row in rows)
    finally:
        reset_task_profile(parent_token)
