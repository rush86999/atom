"""ENTRY-IDENTITY regressions for never-autonomous task admission.

Two proven gaps on the joined task-scope work:

1. The task admission fingerprint truncated the material to
   ``str(task_material)[:8000]`` while claiming to bind the full task. Two
   finance tasks whose first 8000 characters were identical and whose trailing
   instructions differed (January vs February) produced the SAME fingerprint,
   so the second task could reuse the first task's durable approval.
2. If the server-side profile build raised (classification outage), every
   autonomous entry wrapper saw ``profile is None`` and returned None, skipping
   the task admission entirely: the first model leaf and memory recall ran with
   no task HITL even though an enabled rule was potentially applicable.

The fixes bind COMPLETE canonical task material (no display-limit truncation)
and make every real autonomous entry evaluate configured rules against the
canonical trusted unknown profile when classification is unavailable. Unknown
is never treated as a nonmatch, and it is never treated as proof that no policy
applies. No-policy / disabled / true-nonmatch behavior is preserved.

Run with an isolated scratch DB (never the live dev DB):

    TESTING=1 PYTEST_VERSION=ci PYTHON_DOTENV_DISABLED=1 \
    DATABASE_URL=sqlite:////tmp/atom_never_entry_identity.db \
    /private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python -m pytest \
      tests/test_never_autonomous_entry_identity.py -q
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
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
    build_unknown_task_profile,
    is_trusted_task_profile,
    reset_task_profile,
)

# >11000 chars: the first 8000 are byte-identical; only the trailing
# instruction differs. The old ``[:8000]`` identity could not see the change.
LONG_PREFIX = (
    "Analyze the finance invoice expense and accounting records for the "
    "month end reconciliation and summarize the reconciled totals for the "
    "finance team. "
) * 85
FINANCE_JAN_LONG = LONG_PREFIX + "For January, provide the summary."
FINANCE_FEB_LONG = LONG_PREFIX + "For February, provide the summary."
FINANCE_JAN = (
    "Analyse the January finance invoice expense and accounting records "
    "and summarize the reconciled totals for the finance team"
)
MARKETING_TEXT = (
    "Write a short marketing blog article and summarize the campaign notes"
)


@pytest.fixture()
def store(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'atom_never_entry_identity.db'}",
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


@contextlib.contextmanager
def _session_factory(db):
    yield db


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
    # Async on the production leaf: a plain MagicMock turned an intended
    # ``model_calls == []`` assertion into a TypeError at the experience
    # write, masking the real failure.
    agent.world_model.record_experience = AsyncMock(return_value=None)
    agent.reflection_service = MagicMock()
    agent.reflection_service.add_critique = AsyncMock()
    return agent


def _finance_rule(db, name="Always review finance", user_id="u1"):
    return ap.create_never_rule(
        db, user_id, name=name, match={"domain": ["finance"]})


def _approved_hitl(db, action_id):
    """Approve through the real reviewer-authority + atomic claim seam.

    A status-only flip is not a receipt: ``validate_task_admission_receipt``
    requires the persisted reviewer, reviewed_at and the immutable binding to
    still match. Using the production claim keeps this fixture exactly as
    strict as the mounted approval surfaces instead of bypassing them.
    """
    from core.review_decision_authority import (
        authorize_task_admission_decision,
        claim_task_admission_decision,
    )

    row = db.query(HITLAction).filter(HITLAction.id == action_id).first()
    assert row is not None
    check = authorize_task_admission_decision(db, row, "u1")
    assert check.get("ok") is True, check
    assert claim_task_admission_decision(
        db, row, status=HITLActionStatus.APPROVED.value,
        reviewer_id="u1", reviewed_at=datetime.now(timezone.utc),
    ) is True
    db.commit()
    db.refresh(row)
    return row


def _hitl_rows(db):
    return db.query(HITLAction).filter(
        HITLAction.action_type == ap.NEVER_TASK_ADMISSION_ACTION).all()


def _assert_no_material_leak(decision, secret):
    serialized = json.dumps(decision, default=str)
    assert secret not in serialized


# ---------------------------------------------------------------------------
# Fingerprint: COMPLETE task material, canonical + deterministic
# ---------------------------------------------------------------------------

def test_fingerprint_binds_full_material_past_display_limit():
    assert len(FINANCE_JAN_LONG) > 11000
    assert FINANCE_JAN_LONG[:8000] == FINANCE_FEB_LONG[:8000]

    jan_profile = build_task_profile(FINANCE_JAN_LONG, user_id="u1")
    feb_profile = build_task_profile(FINANCE_FEB_LONG, user_id="u1")
    # Same canonical profile: only the trailing task instruction changed.
    assert (
        jan_profile.difficulty, jan_profile.category, jan_profile.domain,
        jan_profile.owner_user_id,
    ) == (
        feb_profile.difficulty, feb_profile.category, feb_profile.domain,
        feb_profile.owner_user_id,
    )

    jan_fp = ap.task_admission_fingerprint(FINANCE_JAN_LONG, jan_profile)
    feb_fp = ap.task_admission_fingerprint(FINANCE_FEB_LONG, feb_profile)
    assert jan_fp != feb_fp
    assert len(jan_fp) == 64
    assert FINANCE_JAN_LONG[-20:] not in jan_fp

    # Deterministic across a rebuilt profile (restart/cold resume).
    rebuilt = build_task_profile(FINANCE_JAN_LONG, user_id="u1")
    assert ap.task_admission_fingerprint(FINANCE_JAN_LONG, rebuilt) == jan_fp


def test_short_string_identity_stays_cold_resume_compatible():
    """The fix must not invalidate already-reviewed short tasks on upgrade."""
    profile = build_task_profile(FINANCE_JAN, user_id="u1")
    legacy_payload = {
        "task": FINANCE_JAN,
        "profile": {
            "difficulty": profile.difficulty,
            "category": profile.category,
            "domain": profile.domain,
        },
        "owner": profile.owner_user_id,
    }
    legacy = hashlib.sha256(json.dumps(
        legacy_payload, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    assert ap.task_admission_fingerprint(FINANCE_JAN, profile) == legacy


def test_structured_material_canonicalization_is_stable_and_explicit():
    profile = build_task_profile(FINANCE_JAN, user_id="u1")
    first = ap.task_admission_fingerprint(
        {"b": 2, "a": ["x", 1], "s": {"p", "q"}}, profile)
    second = ap.task_admission_fingerprint(
        {"a": ["x", 1], "s": {"q", "p"}, "b": 2}, profile)
    assert first == second

    reordered = ap.task_admission_fingerprint(
        {"a": [1, "x"], "s": {"p", "q"}, "b": 2}, profile)
    assert reordered != first

    assert ap.task_admission_fingerprint("abc", profile) != (
        ap.task_admission_fingerprint(b"abc", profile))


def test_unsupported_material_fails_closed_without_leaking_value():
    class _OpaqueSecret:
        """Deliberately hides a sentinel the fingerprint must never echo."""

        def __repr__(self):
            return "raw-sensitive-material-sentinel"

    profile = build_task_profile(FINANCE_JAN, user_id="u1")
    with pytest.raises(TypeError) as excinfo:
        ap.task_admission_fingerprint(_OpaqueSecret(), profile)
    assert "raw-sensitive-material-sentinel" not in str(excinfo.value)


@pytest.mark.asyncio
async def test_changed_suffix_beyond_8000_cannot_resume_old_approval(
    store, use_db, monkeypatch,
):
    """Real approval of task A must not cover task A' with a changed suffix."""
    _engine, Session, db = store
    _agent(db)
    rule = _finance_rule(db)
    agent = _generic_agent(db)
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-long"}

    jan_profile = build_task_profile(FINANCE_JAN_LONG, user_id="u1")
    bind_task_profile(context, jan_profile)

    async def _approve(action_id):
        _approved_hitl(db, action_id)
        return True

    # Real admission path creates the durable HITL through
    # AgentGovernanceService.request_approval, then a human approves.
    monkeypatch.setattr(agent, "_wait_for_approval", _approve)
    assert await agent._admit_never_autonomous_task(
        FINANCE_JAN_LONG, context) is None
    assert ap.has_never_autonomous_clearance(
        context,
        decision=ap.evaluate_task_admission(
            db, jan_profile, task_material=FINANCE_JAN_LONG,
            agent_id="hire-1", user_id="u1",
            execution_id="exec-long")) is True
    assert len(_hitl_rows(db)) == 1
    approved_fp = _hitl_rows(db)[0].params["task_fingerprint"]

    # Cold resume in a DISTINCT session with the same execution, owner, rule
    # and profile, but the February suffix.
    session2 = Session()
    feb_profile = build_task_profile(FINANCE_FEB_LONG, user_id="u1")
    feb_decision = ap.evaluate_task_admission(
        session2, feb_profile, task_material=FINANCE_FEB_LONG,
        agent_id="hire-1", user_id="u1", execution_id="exec-long")
    assert feb_decision["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert feb_decision["rule_ids"] == [rule["id"]]
    assert feb_decision["task_fingerprint"] != approved_fp
    assert not feb_decision.get("durable_admission")

    # Whole entry path: no granted work and no model call for the changed task.
    model_calls = []

    async def _model_leaf(*args, **kwargs):
        model_calls.append(kwargs)
        raise AssertionError("model leaf must not run on an unapproved task")

    monkeypatch.setattr(
        real_generic.GenericAgent, "_react_step", _model_leaf)
    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))

    @contextlib.contextmanager
    def _session2_ctx():
        yield session2

    monkeypatch.setattr(
        "core.generic_agent.get_db_session", lambda: _session2_ctx())
    monkeypatch.setattr(
        "core.database.get_db_session", lambda: _session2_ctx())
    context2 = {"user_id": "u1", "workspace_id": "default",
                "execution_id": "exec-long"}
    result = await agent.execute(FINANCE_FEB_LONG, context2)

    assert result["status"] == "awaiting_approval"
    assert result["requires_human_approval"] is True
    assert model_calls == []
    assert agent.world_model.recall_experiences.await_count == 0
    assert "Never-autonomous" in result["reason"]
    _assert_no_material_leak(result, FINANCE_FEB_LONG[-30:])
    assert len(_hitl_rows(session2)) == 2
    session2.close()


@pytest.mark.asyncio
async def test_identical_full_task_cold_resume_reuses_approval(
    store, use_db, monkeypatch,
):
    _engine, Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-identical"}
    profile = build_task_profile(FINANCE_JAN_LONG, user_id="u1")
    bind_task_profile(context, profile)

    async def _approve(action_id):
        _approved_hitl(db, action_id)
        return True

    monkeypatch.setattr(agent, "_wait_for_approval", _approve)
    assert await agent._admit_never_autonomous_task(
        FINANCE_JAN_LONG, context) is None
    assert len(_hitl_rows(db)) == 1

    # A restarted process rebuilds the profile (new per-task id) and reads a
    # distinct session. The complete material/profile/owner/execution match
    # reuses the exact durable approval and does not prompt again.
    session2 = Session()

    @contextlib.contextmanager
    def _session2_ctx():
        yield session2

    monkeypatch.setattr(
        "core.generic_agent.get_db_session", lambda: _session2_ctx())
    monkeypatch.setattr(
        "core.database.get_db_session", lambda: _session2_ctx())
    resumed_context = {"user_id": "u1", "workspace_id": "default",
                       "execution_id": "exec-identical"}
    resumed_profile = build_task_profile(FINANCE_JAN_LONG, user_id="u1")
    bind_task_profile(resumed_context, resumed_profile)
    wait = AsyncMock(return_value=False)
    monkeypatch.setattr(agent, "_wait_for_approval", wait)

    assert await agent._admit_never_autonomous_task(
        FINANCE_JAN_LONG, resumed_context) is None
    wait.assert_not_awaited()
    assert len(_hitl_rows(session2)) == 1
    assert ap.has_never_autonomous_clearance(
        resumed_context,
        decision=ap.evaluate_task_admission(
            session2, resumed_profile, task_material=FINANCE_JAN_LONG,
            agent_id="hire-1", user_id="u1",
            execution_id="exec-identical")) is True
    session2.close()


@pytest.mark.asyncio
async def test_mounted_approval_enables_exact_cold_resume(
    store, use_db, monkeypatch,
):
    """request_approval + the mounted reviewer service is the real flow."""
    _engine, Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-mounted"}
    profile = build_task_profile(FINANCE_JAN, user_id="u1")
    bind_task_profile(context, profile)

    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))
    pending = await agent._admit_never_autonomous_task(FINANCE_JAN, context)
    assert pending["status"] == "awaiting_approval"
    action_id = pending["hitl_action_id"]
    assert action_id

    # The mounted approvals surface delegates to this service; the owner is a
    # verified ACTIVE team lead in the scratch DB.
    from core.intervention_service import InterventionService

    verdict = await InterventionService().approve_intervention(
        action_id, "u1")
    assert verdict["success"] is True
    row = db.query(HITLAction).filter(HITLAction.id == action_id).first()
    assert row.status == HITLActionStatus.APPROVED.value
    assert row.reviewed_by == "u1"
    assert row.params["task_fingerprint"]

    # Cold resume in an independent session reuses that exact approval.
    session2 = Session()

    @contextlib.contextmanager
    def _session2_ctx():
        yield session2

    monkeypatch.setattr(
        "core.generic_agent.get_db_session", lambda: _session2_ctx())
    monkeypatch.setattr(
        "core.database.get_db_session", lambda: _session2_ctx())
    resumed_context = {"user_id": "u1", "workspace_id": "default",
                       "execution_id": "exec-mounted"}
    bind_task_profile(
        resumed_context, build_task_profile(FINANCE_JAN, user_id="u1"))
    wait = AsyncMock(return_value=False)
    monkeypatch.setattr(agent, "_wait_for_approval", wait)

    assert await agent._admit_never_autonomous_task(
        FINANCE_JAN, resumed_context) is None
    wait.assert_not_awaited()
    assert len(_hitl_rows(session2)) == 1
    session2.close()


def test_reused_context_new_task_does_not_inherit_clearance(store, use_db):
    _engine, _Session, db = store
    _agent(db)
    rule = _finance_rule(db)
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-reused"}
    jan = build_task_profile(FINANCE_JAN_LONG, user_id="u1")
    token = bind_task_profile(context, jan)
    decision = ap.evaluate_task_admission(
        db, jan, task_material=FINANCE_JAN_LONG,
        agent_id="hire-1", user_id="u1", execution_id="exec-reused")
    assert decision["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert ap.grant_never_autonomous_clearance(context, decision) is True
    assert ap.has_never_autonomous_clearance(
        context, decision=decision) is True

    reset_task_profile(token)
    feb = build_task_profile(FINANCE_FEB_LONG, user_id="u1")
    context[TASK_PROFILE_CONTEXT_KEY] = feb
    feb_decision = ap.evaluate_task_admission(
        db, feb, task_material=FINANCE_FEB_LONG,
        agent_id="hire-1", user_id="u1", execution_id="exec-reused")
    assert feb_decision["rule_ids"] == [rule["id"]]
    assert ap.has_never_autonomous_clearance(
        context, decision=feb_decision) is False


def test_admission_without_profile_still_evaluates_configured_rules(
    store, use_db,
):
    """Unbound profile is not proof that no policy applies."""
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)

    decision = ap.evaluate_task_admission(
        db, None, task_material=FINANCE_JAN,
        agent_id="hire-1", user_id="u1", execution_id="exec-unbound")
    assert decision["outcome"] == ap.NEVER_OUTCOME_REVIEW
    assert decision["potential"] is True
    assert decision["metadata_state"] == "missing"
    assert decision["task_fingerprint"] == (
        ap.task_admission_fingerprint(FINANCE_JAN, None))


# ---------------------------------------------------------------------------
# Classification outage at every real autonomous entry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generic_builder_unavailable_requires_review_before_model_or_memory(
    store, use_db, monkeypatch,
):
    """Fault-injected profile builder must not become a silent bypass."""
    _engine, _Session, db = store
    _agent(db)
    rule = _finance_rule(db)
    agent = _generic_agent(db)
    model_calls = []
    recall = agent.world_model.recall_experiences

    async def _model_leaf(*args, **kwargs):
        model_calls.append(kwargs)
        raise AssertionError("model leaf must not run before task admission")

    monkeypatch.setattr(
        real_generic.GenericAgent, "_react_step", _model_leaf)
    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))
    monkeypatch.setattr(
        "core.task_classification.build_task_profile",
        MagicMock(side_effect=RuntimeError("synthetic builder failure")))

    result = await agent.execute(
        FINANCE_JAN, {"user_id": "u1", "workspace_id": "default",
                      "execution_id": "exec-outage"})

    assert result["status"] == "awaiting_approval"
    assert result["requires_human_approval"] is True
    assert "Never-autonomous" in result["reason"]
    assert model_calls == []
    assert recall.await_count == 0

    rows = _hitl_rows(db)
    assert len(rows) == 1
    assert rows[0].status == HITLActionStatus.PENDING.value
    assert rows[0].params["rule_bindings"] == [
        {"id": rule["id"], "revision": 1}]
    assert rows[0].params["task_profile"]["domain"] is None
    assert rows[0].params["task_profile"]["source"] == "server"
    assert result["never_autonomous"]["potential"] is True
    _assert_no_material_leak(result, FINANCE_JAN[-30:])


@pytest.mark.asyncio
async def test_builder_unavailable_no_policy_and_disabled_twins_proceed(
    store, use_db, monkeypatch,
):
    """An outage alone never blocks: only a configured applicable rule does."""
    _engine, _Session, db = store
    _agent(db)
    agent = _generic_agent(db)

    # No policy at all, classification unavailable.
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-no-policy"}
    assert await agent._admit_never_autonomous_task(
        FINANCE_JAN_LONG, context) is None
    assert context.get(ap.NEVER_CLEARANCE_CONTEXT_KEY) is None

    # Disabled rule twin.
    rule = _finance_rule(db)
    ap.update_never_rule(
        db, "u1", rule["id"], name=rule["name"], match=rule["match"],
        enabled=False)
    disabled_context = {"user_id": "u1", "workspace_id": "default",
                        "execution_id": "exec-disabled"}
    assert await agent._admit_never_autonomous_task(
        FINANCE_JAN_LONG, disabled_context) is None

    # True nonmatch twin: enabled finance rule, marketing task.
    ap.update_never_rule(
        db, "u1", rule["id"], name=rule["name"], match=rule["match"],
        enabled=True)
    marketing = build_task_profile(MARKETING_TEXT, user_id="u1")
    assert marketing.domain != "finance"
    marketing_context = {"user_id": "u1", "workspace_id": "default",
                         "execution_id": "exec-marketing"}
    bind_task_profile(marketing_context, marketing)
    assert await agent._admit_never_autonomous_task(
        MARKETING_TEXT, marketing_context) is None
    assert _hitl_rows(db) == []


@pytest.mark.asyncio
async def test_ungrantable_classification_outage_blocks_without_model(
    store, use_db, monkeypatch,
):
    """If even the unknown-profile fallback is unavailable, block safely."""
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)
    model_calls = []

    async def _model_leaf(*args, **kwargs):
        model_calls.append(kwargs)
        raise AssertionError("model leaf must not run during a policy outage")

    async def _approve(action_id):
        _approved_hitl(db, action_id)
        return True

    monkeypatch.setattr(
        real_generic.GenericAgent, "_react_step", _model_leaf)
    monkeypatch.setattr(agent, "_wait_for_approval", _approve)
    monkeypatch.setattr(
        "core.task_classification.build_task_profile",
        MagicMock(side_effect=RuntimeError("synthetic builder failure")))
    monkeypatch.setattr(
        "core.task_classification.build_unknown_task_profile",
        MagicMock(side_effect=RuntimeError("synthetic fallback failure")))

    result = await agent.execute(
        FINANCE_JAN, {"user_id": "u1", "workspace_id": "default",
                      "execution_id": "exec-ungrantable"})

    assert model_calls == []
    assert agent.world_model.recall_experiences.await_count == 0
    assert result["status"] == "blocked"
    assert result["requires_human_approval"] is True
    assert "could not be bound" in result["output"]
    assert len(_hitl_rows(db)) == 1


@pytest.mark.asyncio
async def test_meta_builder_unavailable_requires_review_before_model(
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
    monkeypatch.setattr(
        "core.task_classification.build_task_profile",
        MagicMock(side_effect=RuntimeError("synthetic builder failure")))

    result = await meta.execute_unaudited(
        FINANCE_JAN,
        {"user_id": "u1", "execution_id": "exec-meta-outage"})

    assert result["status"] == "awaiting_approval"
    assert result["requires_human_approval"] is True
    assert model_calls == []
    rows = _hitl_rows(db)
    assert len(rows) == 1
    assert rows[0].agent_id == "atom_main"
    assert rows[0].params["task_profile"]["domain"] is None


@pytest.mark.asyncio
async def test_workflow_builder_unavailable_binds_unknown_profile(
    store, use_db, monkeypatch,
):
    _engine, _Session, db = store
    from core.task_classification import current_task_profile
    from core.workflow_engine import WorkflowEngine

    engine = WorkflowEngine()
    captured = {}

    async def _body(execution_id, workflow):
        captured["profile"] = current_task_profile()
        captured["execution_id"] = execution_id

    monkeypatch.setattr(engine, "_run_execution_body", _body)
    monkeypatch.setattr(
        "core.task_classification.build_workflow_task_profile",
        MagicMock(side_effect=RuntimeError("synthetic builder failure")))

    await engine._run_execution(
        "exec-wf-bind", {"id": "wf", "created_by": "u1"})

    profile = captured["profile"]
    assert is_trusted_task_profile(profile)
    assert profile.difficulty is None
    assert profile.category is None
    assert profile.domain is None
    assert profile.owner_user_id == "u1"
    assert profile.signals["classification_source"] == "unavailable"


@pytest.mark.asyncio
async def test_workflow_unbound_profile_still_pauses_before_first_step(
    store, use_db, monkeypatch,
):
    _engine, _Session, db = store
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
    monkeypatch.setattr(engine, "_notify_workflow_paused", MagicMock())
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
        "created_by": "u1",
        "steps": [{"id": "s1", "service": "ai", "action": "analyze"}],
    }
    # No profile is bound (classification unavailable/unbound).
    paused = await engine._admit_never_autonomous_task(
        "exec-wf-outage", workflow, {"steps": {}}, "u1", "default", "default")

    assert paused == "paused"
    state_manager.update_execution_status.assert_awaited()
    engine._notify_workflow_paused.assert_called_once()
    rows = _hitl_rows(db)
    assert len(rows) == 1
    assert rows[0].params["execution_id"] == "exec-wf-outage"
    assert rows[0].params["task_profile"]["domain"] is None
    assert any(
        entry.get("id") for entry in rows[0].params["rule_bindings"])


def test_assignment_builder_unavailable_proposes_and_no_policy_twin_passes(
    store, use_db, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)
    rule = _finance_rule(db)
    from core.assignment_executor import AssignmentExecutor

    executor = object.__new__(AssignmentExecutor)
    executor.lifecycle = SimpleNamespace(
        runs=SimpleNamespace(
            _sessions=lambda: (lambda: _session_factory(db))))
    assignment = {
        "assignment_id": "asg-1",
        "employee_id": "u1",
        "provenance": {"user_id": "u1", "agent_id": "hire-1"},
        "tenant_id": None,
        "workspace_id": "default",
        "objective": "Analyze the finance invoice reconciliation",
        "steps": [],
    }
    monkeypatch.setattr(
        "core.task_classification.build_assignment_task_profile",
        MagicMock(side_effect=RuntimeError("synthetic builder failure")))

    gated = executor._never_autonomy_gate(
        assignment, {"step_id": "s1"})
    assert gated["outcome"] == "propose"
    assert gated["source"] == "never_autonomous_task_recheck"
    assert gated["never_autonomous"]["potential"] is True

    # No policy: an outage must not invent a block.
    ap.delete_never_rule(db, "u1", rule["id"])
    assert executor._never_autonomy_gate(
        assignment, {"step_id": "s1"}) is None


def test_assignment_unbound_profile_fail_closed_before_effect(store, use_db):
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    from core.assignment_executor import AssignmentExecutor

    executor = object.__new__(AssignmentExecutor)
    executor.lifecycle = SimpleNamespace(
        runs=SimpleNamespace(
            _sessions=lambda: (lambda: _session_factory(db))))
    assignment = {
        "assignment_id": "asg-2",
        "employee_id": "u1",
        "provenance": {"user_id": "u1", "agent_id": "hire-1"},
        "tenant_id": None,
        "workspace_id": "default",
        "objective": "Analyze the finance invoice reconciliation",
        "steps": [],
    }
    # Non-mapping/empty material yields a trusted unknown-ish profile; the
    # configured rule remains potential, so the effect is proposed.
    gated = executor._never_autonomy_gate(
        assignment, {"step_id": "s1"})
    assert gated["outcome"] == "propose"
    assert gated["never_autonomous"]["outcome"] == ap.NEVER_OUTCOME_REVIEW


# ---------------------------------------------------------------------------
# Recovery: an outage approval never silently carries into recovery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_requires_fresh_review_because_profile_changed(
    store, use_db, monkeypatch,
):
    _engine, _Session, db = store
    _agent(db)
    _finance_rule(db)
    agent = _generic_agent(db)
    context = {"user_id": "u1", "workspace_id": "default",
               "execution_id": "exec-recovery"}
    outage_profile = build_unknown_task_profile(
        user_id="u1", reason="RuntimeError")
    bind_task_profile(context, outage_profile)

    async def _approve(action_id):
        _approved_hitl(db, action_id)
        return True

    monkeypatch.setattr(agent, "_wait_for_approval", _approve)
    assert await agent._admit_never_autonomous_task(
        FINANCE_JAN, context) is None
    assert len(_hitl_rows(db)) == 1
    outage_fp = _hitl_rows(db)[0].params["task_fingerprint"]

    # Classification recovers (new server-built finance profile). The
    # unknown-profile approval bound different identity, so the same
    # execution/task needs a fresh review rather than inheriting it.
    recovered_context = {"user_id": "u1", "workspace_id": "default",
                         "execution_id": "exec-recovery"}
    recovered_profile = build_task_profile(FINANCE_JAN, user_id="u1")
    bind_task_profile(recovered_context, recovered_profile)
    monkeypatch.setattr(
        agent, "_wait_for_approval", AsyncMock(return_value=False))
    result = await agent._admit_never_autonomous_task(
        FINANCE_JAN, recovered_context)

    assert result is not None
    assert result["status"] == "awaiting_approval"
    rows = _hitl_rows(db)
    assert len(rows) == 2
    assert rows[1].params["task_fingerprint"] != outage_fp
    assert rows[1].params["task_profile"]["domain"] == "finance"
