"""TASK-LEVEL never-autonomous admission + per-task clearance bindings.

Permanent regressions for two independent ROOT findings:

1. Never-autonomous baskets were narrowed to effectful actions: a pure
   analysis/QA/math/extraction task with a matching rule ran autonomously
   (``read_data`` was allowed because governance complexity 1 returned early).
   The boundary is now the TASK — admitted once before the first model call
   or output.
2. A human approval was a module-global token plus rule ids, so approving one
   finance task also waived a DIFFERENT later finance task that reused the
   same context dict, agent and rule. Clearance is now bound to the trusted
   task identity (per-start profile id), reviewed rule revisions, owner/scope
   and execution id.

Run with the isolated scratch DB (never the live dev DB):

    TESTING=1 PYTEST_VERSION=ci PYTHON_DOTENV_DISABLED=1 \
    DATABASE_URL=sqlite:////tmp/atom_never_task_scope.db \
    /private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python -m pytest \
      tests/test_never_autonomous_task_scope.py -q
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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
    reset_task_profile,
)

# A pure finance analysis task: extraction/QA, no writes or tools.
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
        f"sqlite:///{tmp_path / 'atom_never_task_scope.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    try:
        yield Session, db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def use_db(store, monkeypatch):
    """Route the agent/governance DB helpers to the scratch session."""
    _Session, db = store

    @contextlib.contextmanager
    def _session():
        yield db

    for target in (
        "core.generic_agent.get_db_session",
        "core.database.get_db_session",
    ):
        monkeypatch.setattr(target, _session)
    return db


def _active_user(
    db, user_id="u1", role="team_lead", workspace_id="default",
    tenant_id=None, active=True,
):
    """A real, currently-authorised human reviewer row.

    Review authority is resolved from the durable User row, so an approval
    fixture that only flips ``status`` (with no real reviewer) no longer
    models a legitimate decision.
    """
    existing = db.query(User).filter(User.id == user_id).first()
    if existing is not None:
        return existing
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="Reviewer",
        last_name="User",
        role=role,
        status="active" if active else "inactive",
        is_active=bool(active),
        workspace_id=workspace_id,
        tenant_id=tenant_id,
    )
    db.add(user)
    db.commit()
    return user


def _agent(db, agent_id="hire-1", user_id="u1", status="autonomous"):
    _active_user(db, user_id)
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
    db.commit()


def _generic_agent(db, status="autonomous"):
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
    agent.reflection_service = MagicMock()
    agent.reflection_service.add_critique = AsyncMock()
    return agent


def _finance_rule(db, name="Always review finance", user_id="u1"):
    return ap.create_never_rule(
        db, user_id, name=name, match={"domain": ["finance"]})


def _approved_hitl(db, action_id, reviewer_id="u1"):
    _active_user(db, reviewer_id)
    row = db.query(HITLAction).filter(HITLAction.id == action_id).first()
    assert row is not None
    row.status = HITLActionStatus.APPROVED.value
    row.reviewed_by = reviewer_id
    row.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return row


# ---------------------------------------------------------------------------
# TASK admission before the first model/provider call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_matched_pure_analysis_creates_task_hitl_before_model_leaf(
    store, use_db, monkeypatch,
):
    Session, db = store
    _agent(db)
    rule = _finance_rule(db)
    agent = _generic_agent(db)
    model_calls = []

    async def _model_leaf(*args, **kwargs):
        model_calls.append(kwargs)
        raise AssertionError("model leaf must not run before task admission")

    monkeypatch.setattr(
        real_generic.GenericAgent, "_react_step", _model_leaf)
    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))

    result = await agent.execute(
        FINANCE_JAN, {"user_id": "u1", "workspace_id": "default"})

    assert result["status"] == "awaiting_approval"
    assert result["requires_human_approval"] is True
    assert "Never-autonomous" in result["reason"]
    assert model_calls == []
    assert agent.world_model.recall_experiences.await_count == 0

    rows = db.query(HITLAction).filter(
        HITLAction.action_type == ap.NEVER_TASK_ADMISSION_ACTION).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.status == HITLActionStatus.PENDING.value
    assert row.params["rule_bindings"] == [
        {"id": rule["id"], "revision": 1}]
    assert row.params["task_fingerprint"]
    assert row.params["task_profile"]["domain"] == "finance"


def test_nonmatch_and_no_policy_twins_are_not_admitted(store, use_db):
    Session, db = store
    _agent(db)
    agent = _generic_agent(db)

    # No policy at all.
    no_policy = build_task_profile(FINANCE_JAN, user_id="u1")
    bind_task_profile({}, no_policy)
    assert ap.evaluate_task_admission(
        db, no_policy, task_material=FINANCE_JAN,
        agent_id="hire-1", user_id="u1",
        execution_id="exec-none")["outcome"] == ap.NEVER_OUTCOME_UNAFFECTED

    # Enabled rule, but a near-neighbour task is a definite nonmatch.
    _finance_rule(db)
    marketing = build_task_profile(MARKETING_TEXT, user_id="u1")
    assert marketing.domain != "finance"
    bound = {}
    bind_task_profile(bound, marketing)
    decision = ap.evaluate_task_admission(
        db, marketing, task_material=MARKETING_TEXT,
        agent_id="hire-1", user_id="u1",
        execution_id="exec-marketing")
    assert decision["outcome"] == ap.NEVER_OUTCOME_UNAFFECTED
    assert decision["matched"] is False

    # A task with missing classification metadata is potentially applicable
    # (fail closed), not a silent skip.
    empty = build_task_profile("", user_id="u1")
    bind_task_profile(bound, empty)
    missing = ap.evaluate_task_admission(
        db, empty, task_material="",
        agent_id="hire-1", user_id="u1",
        execution_id="exec-empty")
    assert missing["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert missing["potential"] is True


# ---------------------------------------------------------------------------
# Read-only action gate + a specific, approved execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_only_matched_task_requires_review_and_approved_task_runs(
    store, use_db, monkeypatch,
):
    Session, db = store
    _agent(db)
    _finance_rule(db)
    profile = build_task_profile(FINANCE_JAN, user_id="u1")

    gov = AgentGovernanceService(db, workspace_id="default", tenant_id=None)
    monkeypatch.setattr(
        gov, "_check_budget_async", AsyncMock(return_value={"allowed": True}))

    # ROOT's first finding: read_data is a TASK, not "not execution".
    read = await gov.can_perform_action_async(
        "hire-1", "read_data", task_profile=profile)
    assert read["requires_human_approval"] is True
    assert read["never_autonomous"]["matched"] is True
    assert read["never_autonomous"]["applicable"] is True

    agent = _generic_agent(db)
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-approved"}
    bind_task_profile(context, profile)

    async def _approve(action_id):
        _approved_hitl(db, action_id)
        return True

    monkeypatch.setattr(agent, "_wait_for_approval", _approve)
    assert await agent._admit_never_autonomous_task(FINANCE_JAN, context) is None

    # The approval is bound to this exact task execution and clears ONLY the
    # never policy; the independent maturity/budget guards still run.
    cleared = await gov.can_perform_action_async(
        "hire-1", "read_data", task_profile=profile,
        never_clearance=context)
    assert cleared["requires_human_approval"] is False
    assert cleared["never_autonomous"]["cleared"] is True
    assert ap.has_never_autonomous_clearance(
        context,
        decision=ap.evaluate_never_autonomous(db, "u1", profile),
        execution_id="exec-approved",
    ) is True

    # A different execution context of the same owner/agent/rule still asks.
    other = {"user_id": "u1", "workspace_id": "default",
             "execution_id": "exec-other"}
    still_blocked = await gov.can_perform_action_async(
        "hire-1", "read_data", task_profile=profile,
        never_clearance=other)
    assert still_blocked["requires_human_approval"] is True


# ---------------------------------------------------------------------------
# Approval of task A must never waive task B (same dict/agent/rule)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_second_real_task_start_requires_a_fresh_approval(
    store, use_db, monkeypatch,
):
    Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-two-starts"}

    async def _approve(action_id):
        _approved_hitl(db, action_id)
        return True

    jan = build_task_profile(FINANCE_JAN, user_id="u1")
    bind_task_profile(context, jan)

    # Start 1: real task identity + a human approval.
    monkeypatch.setattr(agent, "_wait_for_approval", _approve)
    assert await agent._admit_never_autonomous_task(FINANCE_JAN, context) is None
    assert ap.has_never_autonomous_clearance(
        context,
        decision=ap.evaluate_task_admission(
            db, jan, task_material=FINANCE_JAN,
            agent_id="hire-1", user_id="u1")) is True

    # Start 2: the SAME context/agent/rule, but a different real task. The
    # provider boundary must re-ask; the first approval is not a waiver.
    feb = build_task_profile(FINANCE_FEB, user_id="u1")
    bind_task_profile(context, feb)
    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))
    second = await agent._admit_never_autonomous_task(FINANCE_FEB, context)
    assert second is not None
    assert second["status"] == "awaiting_approval"
    assert ap.NEVER_CLEARANCE_CONTEXT_KEY not in context
    rows = db.query(HITLAction).filter(
        HITLAction.action_type == ap.NEVER_TASK_ADMISSION_ACTION).all()
    assert len(rows) == 2
    assert len({row.params["task_fingerprint"] for row in rows}) == 2


def test_second_task_on_reused_context_never_inherits_clearance(store, use_db):
    Session, db = store
    _agent(db)
    rule = _finance_rule(db)

    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-jan"}
    jan = build_task_profile(FINANCE_JAN, user_id="u1")
    token = bind_task_profile(context, jan)
    jan_decision = ap.evaluate_task_admission(
        db, jan, task_material=FINANCE_JAN,
        agent_id="hire-1", user_id="u1", execution_id="exec-jan")
    assert jan_decision["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert ap.grant_never_autonomous_clearance(
        context, jan_decision) is True
    assert ap.has_never_autonomous_clearance(
        context, decision=jan_decision) is True

    # February is a DIFFERENT task in the same basket/rule. Even if the
    # caller re-binds a new profile WITHOUT clearing and keeps the old
    # clearance object, the new task identity must invalidate it.
    reset_task_profile(token)
    feb = build_task_profile(FINANCE_FEB, user_id="u1")
    context[TASK_PROFILE_CONTEXT_KEY] = feb
    feb_decision = ap.evaluate_task_admission(
        db, feb, task_material=FINANCE_FEB,
        agent_id="hire-1", user_id="u1", execution_id="exec-feb")
    assert feb_decision["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert feb_decision["rule_ids"] == [rule["id"]]
    assert ap.has_never_autonomous_clearance(
        context, decision=feb_decision) is False
    assert ap.has_never_autonomous_clearance(
        context, required_rule_ids=feb_decision["rule_ids"]) is False

    # A real new task start through bind_task_profile also drops the old
    # clearance from the dict (defence in depth, not the only check).
    bind_task_profile(context, feb)
    assert ap.NEVER_CLEARANCE_CONTEXT_KEY not in context


def test_direct_mcp_guard_refuses_second_task_with_stale_clearance(
    store, use_db,
):
    Session, db = store
    _finance_rule(db)
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-jan"}
    jan = build_task_profile(FINANCE_JAN, user_id="u1")
    token = bind_task_profile(context, jan)
    decision = ap.evaluate_task_admission(
        db, jan, task_material=FINANCE_JAN,
        agent_id="hire-1", user_id="u1", execution_id="exec-jan")
    assert ap.grant_never_autonomous_clearance(context, decision) is True
    reset_task_profile(token)

    # Reuse the SAME dict for the February task (stale clearance retained).
    feb = build_task_profile(FINANCE_FEB, user_id="u1")
    context[TASK_PROFILE_CONTEXT_KEY] = feb

    import core.action_registry as registry_module
    from integrations import mcp_service as mcp_module

    with patch.object(
            registry_module.action_registry, "get_action",
            return_value=object()), patch.object(
            registry_module.action_registry, "execute_action",
            new=AsyncMock(return_value={"ok": True})):
        blocked = asyncio.run(mcp_module.mcp_service.call_tool(
            "read_data", {"query": "february finance"}, context))
    assert blocked["blocked_by"] == "never_autonomous"
    assert blocked["requires_human_approval"] is True
    assert blocked["never_autonomous"]["matched"] is True


def test_parallel_actions_share_one_task_clearance_but_not_a_new_task(
    store, use_db, monkeypatch,
):
    Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)
    profile = build_task_profile(FINANCE_JAN, user_id="u1")
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-parallel"}
    token = bind_task_profile(context, profile)
    decision = ap.evaluate_task_admission(
        db, profile, task_material=FINANCE_JAN,
        agent_id="hire-1", user_id="u1", execution_id="exec-parallel")
    assert ap.grant_never_autonomous_clearance(context, decision) is True

    gov = AgentGovernanceService(db, workspace_id="default", tenant_id=None)
    monkeypatch.setattr(
        gov, "_check_budget_async", AsyncMock(return_value={"allowed": True}))

    async def _two_reads():
        return [
            await gov.can_perform_action_async(
                "hire-1", "read_data", task_profile=profile,
                never_clearance=context)
            for _ in range(2)
        ]

    first, second = asyncio.run(_two_reads())
    assert first["requires_human_approval"] is False
    assert second["requires_human_approval"] is False
    assert first["never_autonomous"]["cleared"] is True

    # Same context, new task start: no shared clearance across the boundary.
    reset_task_profile(token)
    feb = build_task_profile(FINANCE_FEB, user_id="u1")
    bind_task_profile(context, feb)
    fresh = asyncio.run(gov.can_perform_action_async(
        "hire-1", "read_data", task_profile=feb,
        never_clearance=context))
    assert fresh["requires_human_approval"] is True


# ---------------------------------------------------------------------------
# Durable resume reuses the exact approved task, never a different one
# ---------------------------------------------------------------------------

def test_durable_task_admission_resumes_only_the_same_task(store, use_db):
    Session, db = store
    _agent(db)
    rule = _finance_rule(db)
    profile = build_task_profile(FINANCE_JAN, user_id="u1")
    decision = ap.evaluate_task_admission(
        db, profile, task_material=FINANCE_JAN,
        agent_id="hire-1", user_id="u1", execution_id="exec-resume")
    db.add(HITLAction(
        id="hitl-task-admission-1",
        workspace_id="default",
        agent_id="hire-1",
        action_type=ap.NEVER_TASK_ADMISSION_ACTION,
        platform="internal",
        params={
            "execution_id": "exec-resume",
            "task_fingerprint": decision["task_fingerprint"],
            "rule_bindings": [{"id": rule["id"], "revision": 1}],
            "owner_user_id": "u1",
            "task_profile": profile.as_dict(),
        },
        status=HITLActionStatus.APPROVED.value,
        reason=decision["reason"],
        user_id="u1",
        reviewed_by="u1",
        reviewed_at=datetime.now(timezone.utc),
    ))
    db.commit()

    # A restarted process rebuilds the profile (new per-task id); the durable
    # HITL row for the same execution/task/rule is reused.
    resumed_profile = build_task_profile(FINANCE_JAN, user_id="u1")
    resumed = ap.evaluate_task_admission(
        db, resumed_profile, task_material=FINANCE_JAN,
        agent_id="hire-1", user_id="u1", execution_id="exec-resume")
    assert resumed["durable_admission"]["hitl_action_id"] == (
        "hitl-task-admission-1")
    assert ap.decision_covers(
        {"outcome": "review",
         "rule_bindings": resumed["durable_admission"]["params"][
             "rule_bindings"]},
        resumed) is True

    # The same execution with DIFFERENT task material is not covered.
    other = ap.evaluate_task_admission(
        db, build_task_profile(FINANCE_FEB, user_id="u1"),
        task_material=FINANCE_FEB,
        agent_id="hire-1", user_id="u1", execution_id="exec-resume")
    assert not other.get("durable_admission")


# ---------------------------------------------------------------------------
# Workflow/system-agent path: durable task admission before the first step
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_task_admission_pauses_and_resume_reuses_hitl(
    store, use_db, monkeypatch,
):
    Session, db = store
    _agent(db)
    _finance_rule(db)
    from core.workflow_engine import WorkflowEngine

    engine = WorkflowEngine()
    state_manager = MagicMock()
    state_manager.update_execution_status = AsyncMock()
    engine.state_manager = state_manager
    ws = MagicMock()
    ws.notify_workflow_status = AsyncMock()
    monkeypatch.setattr(
        "core.workflow_engine.get_connection_manager", lambda: ws)
    monkeypatch.setattr(
        engine, "_notify_workflow_paused", MagicMock())
    monkeypatch.setattr(
        "core.workflow_engine.get_db_session", _session_factory(db))
    monkeypatch.setattr(
        "core.workflow_engine.ServiceFactory.get_governance_service",
        staticmethod(lambda db, workspace_id=None, tenant_id=None:
                     AgentGovernanceService(
                         db, workspace_id=workspace_id,
                         tenant_id=tenant_id)))

    workflow = {
        "id": "wf-finance",
        "name": "January finance reconciliation analysis",
        "description": "Reconcile finance invoice accounting records",
        "agent_id": "hire-1",
        "steps": [{"id": "s1", "service": "ai", "action": "analyze"}],
    }
    token = bind_task_profile(
        None, build_task_profile(FINANCE_JAN, user_id="u1"))
    try:
        paused = await engine._admit_never_autonomous_task(
            "exec-wf", workflow, {"steps": {}}, "u1", "default", "default")
        assert paused == "paused"
        state_manager.update_execution_status.assert_awaited()
        rows = db.query(HITLAction).filter(
            HITLAction.action_type == ap.NEVER_TASK_ADMISSION_ACTION).all()
        assert len(rows) == 1
        assert rows[0].params["execution_id"] == "exec-wf"
        assert rows[0].params["workflow_id"] == "wf-finance"

        # Resume: the durable approved row is the authority; a rebuilt
        # profile (new per-task id) reuses it and does not pause again.
        _approved_hitl(db, rows[0].id)
        reset_task_profile(token)
        token = bind_task_profile(
            None, build_task_profile(FINANCE_JAN, user_id="u1"))
        engine._notify_workflow_paused.reset_mock()
        resumed = await engine._admit_never_autonomous_task(
            "exec-wf", workflow, {"steps": {}}, "u1", "default", "default")
        assert resumed is None
        engine._notify_workflow_paused.assert_not_called()
        gov = AgentGovernanceService(
            db, workspace_id="default", tenant_id="default")
        monkeypatch.setattr(
            gov, "_check_budget_async",
            AsyncMock(return_value={"allowed": True}))
        from core.task_classification import current_task_profile

        decision = await gov.can_perform_action_async(
            "hire-1", "read_data",
            task_profile=current_task_profile())
        assert decision.get("never_autonomous", {}).get("cleared") is True
    finally:
        reset_task_profile(token)


def _session_factory(db):
    @contextlib.contextmanager
    def _session():
        yield db

    return _session


# ---------------------------------------------------------------------------
# Stale rule revision / owner + scope binding
# ---------------------------------------------------------------------------

def test_rule_edit_revision_and_scope_invalidate_clearance(store, use_db):
    Session, db = store
    rule = _finance_rule(db)
    profile = build_task_profile(FINANCE_JAN, user_id="u1")
    context = {"user_id": "u1", "workspace_id": "ws-a", "tenant_id": "t1",
               "execution_id": "exec-scope"}
    bind_task_profile(context, profile)
    decision = ap.evaluate_task_admission(
        db, profile, task_material=FINANCE_JAN,
        agent_id="hire-1", user_id="u1",
        execution_id="exec-scope", tenant_id="t1", workspace_id="ws-a")
    assert ap.grant_never_autonomous_clearance(
        context, decision, tenant_id="t1", workspace_id="ws-a") is True

    # Same rule id, new revision (edited) must not reuse the old review.
    ap.update_never_rule(
        db, "u1", rule["id"], name="Always review finance v2",
        match={"domain": ["finance"], "category": ["extraction"]})
    fresh = ap.evaluate_never_autonomous(db, "u1", profile)
    assert fresh["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert fresh["rule_bindings"] == [
        {"id": rule["id"], "revision": 2}]
    assert ap.has_never_autonomous_clearance(
        context, decision=fresh, tenant_id="t1",
        workspace_id="ws-a") is False

    # Owner and scope are part of the binding too.
    rebuilt = {"user_id": "u1", "workspace_id": "ws-a", "tenant_id": "t1",
               "execution_id": "exec-scope"}
    bind_task_profile(rebuilt, profile)
    assert ap.grant_never_autonomous_clearance(
        rebuilt, fresh, tenant_id="t1", workspace_id="ws-a") is True
    assert ap.has_never_autonomous_clearance(
        rebuilt, decision=fresh, tenant_id="t1",
        workspace_id="ws-a") is True
    assert ap.has_never_autonomous_clearance(
        rebuilt, decision=fresh, tenant_id="t2",
        workspace_id="ws-a") is False
    assert ap.has_never_autonomous_clearance(
        rebuilt, decision=fresh, tenant_id="t1",
        workspace_id="ws-b") is False
    owner_mismatch = dict(fresh)
    owner_mismatch["owner_user_id"] = "u2"
    assert ap.has_never_autonomous_clearance(
        rebuilt, decision=owner_mismatch) is False
