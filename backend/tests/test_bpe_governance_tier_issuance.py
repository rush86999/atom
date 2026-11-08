"""Admitted governance tier + current actor field-class controls.

Author-only controls (root executes). They pin the finite repair for the two
confirmed defects:

* an admitted run froze the transient ``AgentRegistry.status == "running"``
  as ``tier_at_issuance`` (sandbox then correctly refused ``workspace.note``);
* a server-bound admitted actor was not re-read from current User/Workspace
  state at the BPE leaf, so a disabled/moved actor could not be refused.

Business assertions from the root admitted probe are preserved unchanged; the
only fixture correction is seeding the same autonomous agent the root probe
uses. No gate, approval verdict, policy whitelist or actor row is faked.
"""
from __future__ import annotations

import importlib
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generic_agent as generic
import core.intervention_service as interventions
from core.models import (
    AgentExecution,
    AgentJob,
    AgentRegistry,
    AuditLog,
    HITLAction,
    Tenant,
    User,
    Workspace,
)
from core.models_registration import Base
from core.react_models import ReActStep, ToolCall
from tests.test_agent_generic_information_wait import _install_model, _seed_board
from tests.test_agent_run_outcome_join_contract import _run, real_env


# ---------------------------------------------------------------------------
# Tier propagation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tier", ["student", "intern", "supervised", "autonomous"])
def test_admission_persists_and_dispatch_uses_the_canonical_tier(
    real_env, monkeypatch, tier, tmp_path,
):
    from core.bpe import workspace as bpe_workspace

    monkeypatch.setenv("ATOM_BPE_WORKSPACE_ENABLED", "true")
    bpe_workspace.reset_registry()
    with real_env.SessionLocal() as db:
        agent = db.get(AgentRegistry, "a1")
        agent.status = tier
        db.commit()

    operation_id = f"tier-canonical-{tier}"
    response = _run(
        real_env,
        operation_id=operation_id,
        parameters={"sync": True, "task_input": "record a fact"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    job_id = data["job_id"]

    with real_env.SessionLocal() as db:
        job = db.get(AgentJob, job_id)
        payload = json.loads(job.result_summary or "{}")
        audit = db.get(AuditLog, f"agent:run:{operation_id}")
        metadata = json.loads(audit.metadata_json or "{}")
        restored = db.get(AgentRegistry, "a1")
        assert restored.status == tier

    assert payload["governance_tier"] == tier
    assert payload["governance_tier_source"] == "admission"
    assert payload["prior_status"] == tier
    assert metadata["extra"]["governance_tier"] == tier
    assert metadata["extra"]["governance_tier_source"] == "admission"
    assert metadata["extra"]["prior_status"] == tier


@pytest.mark.parametrize("runtime_status", ["idle", "success", "unknown"])
def test_legacy_runtime_state_gets_a_restricted_student_ceiling(
    real_env, monkeypatch, runtime_status, tmp_path,
):
    """Non-tier legacy labels stay usable, never become autonomous."""
    import core.bpe.persistence as bpe_persistence
    from core.bpe import workspace as bpe_workspace

    monkeypatch.setenv("ATOM_BPE_WORKSPACE_ENABLED", "true")
    monkeypatch.setattr(bpe_persistence, "DATA_DIR", tmp_path / "bpe")
    bpe_workspace.reset_registry()
    with real_env.SessionLocal() as db:
        agent = db.get(AgentRegistry, "a1")
        agent.status = runtime_status
        db.commit()

    captured = []

    def _final_step(*_args, **_kwargs):
        captured.append(True)
        return ReActStep(thought="done", final_answer="done")

    _install_model(monkeypatch, [_final_step])
    response = _run(
        real_env,
        operation_id=f"tier-runtime-{runtime_status}",
        parameters={"sync": True, "task_input": "legacy run"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    with real_env.SessionLocal() as db:
        job = db.get(AgentJob, data["job_id"])
        payload = json.loads(job.result_summary or "{}")
        execution = db.get(AgentExecution, data["execution_id"])
        execution_metadata = dict(execution.metadata_json or {})
        restored = db.get(AgentRegistry, "a1")
        assert restored.status == runtime_status

    assert captured
    assert payload["governance_tier"] is None
    assert payload["governance_tier_source"] == "legacy_unverified"
    assert payload["prior_status"] == runtime_status
    assert execution_metadata["governance_tier"] == "student"
    assert execution_metadata["governance_tier_source"] in {
        "unverified", "current_unverified"}
    assert execution_metadata["governance_tier_restricted"] is True
    assert execution_metadata["governance_tier_next_action"] == (
        "review_agent_maturity")


def test_running_is_execution_state_and_never_a_frozen_tier(real_env):
    with real_env.SessionLocal() as db:
        agent = db.get(AgentRegistry, "a1")
        agent.status = "running"
        db.commit()

    response = _run(
        real_env,
        operation_id="tier-running-negative",
        parameters={"sync": True, "task_input": "must not be admitted"},
    )
    assert response.status_code == 409, response.text
    detail = response.json()
    assert detail["detail"]["error"]["code"] == "ALREADY_RUNNING"


def test_forged_body_tier_and_provenance_are_rebuilt_from_admission(
    real_env, monkeypatch, tmp_path,
):
    import core.bpe.persistence as bpe_persistence
    from core.bpe import workspace as bpe_workspace

    monkeypatch.setenv("ATOM_BPE_WORKSPACE_ENABLED", "true")
    monkeypatch.setattr(bpe_persistence, "DATA_DIR", tmp_path / "bpe")
    bpe_workspace.reset_registry()
    with real_env.SessionLocal() as db:
        agent = db.get(AgentRegistry, "a1")
        agent.status = "student"
        db.commit()

    calls = _install_model(monkeypatch, [
        lambda *_a: ReActStep(thought="done", final_answer="done")])
    response = _run(
        real_env,
        operation_id="tier-forged-body",
        parameters={
            "sync": True,
            "task_input": "forged authority must not apply",
            "tier": "autonomous",
            "tier_at_issuance": "autonomous",
            "governance_tier": "autonomous",
            "provenance": {"source": "forged"},
            "canvas_provenance": {"source": "forged"},
            "_bpe_principal_scope": {
                "workspace_id": "peer-ws",
                "agent_id": "peer-agent",
                "scope_key": "peer-scope",
                "user_id": "peer-user",
            },
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    context = calls[0]["context"]

    assert context["tier_at_issuance"] == "student"
    assert context["governance_tier"] == "student"
    assert context["provenance"] is None
    assert context["canvas_provenance"] is None
    scope = context["_bpe_principal_scope"]
    assert scope["workspace_id"] == "ws1"
    assert scope["agent_id"] == "a1"
    assert scope["scope_key"] == data["job_id"]
    assert scope["user_id"] == "member-1"

    with real_env.SessionLocal() as db:
        job = db.get(AgentJob, data["job_id"])
        payload = json.loads(job.result_summary or "{}")
    assert payload["governance_tier"] == "student"
    assert payload["prior_status"] == "student"


def test_initial_and_resumed_trusted_contexts_share_the_job_tier(real_env):
    from api.agent_routes import _begin_job, _trusted_execution_context
    from core.agent_decision_write_service import admit_agent_run

    with real_env.SessionLocal() as db:
        agent = db.get(AgentRegistry, "a1")
        agent.status = "autonomous"
        db.commit()
        actor = db.get(User, "member-1")
        admitted = admit_agent_run(
            db,
            actor=actor,
            agent_id="a1",
            parameters={"task_input": "tier resume"},
            operation_id="tier-resume-1",
        )
        assert admitted["status"] in {"already_applied", "verified"}, admitted
        job_id = admitted["data"]["job_id"]
        bind = db.get_bind()

    assert _begin_job(
        job_id, bind, agent_id="a1", execution_id="exec-initial",
        parameters={"task_input": "tier resume"},
    )
    initial = _trusted_execution_context(
        bind, agent_id="a1", job_id=job_id,
        actor_id="member-1", execution_id="exec-initial",
    )
    resumed = _trusted_execution_context(
        bind, agent_id="a1", job_id=job_id,
        actor_id="member-1", execution_id="exec-resumed",
    )
    assert initial and resumed
    assert initial["_trusted_governance_tier"] == "autonomous"
    assert resumed["_trusted_governance_tier"] == "autonomous"
    assert initial["governance_tier"] == resumed["governance_tier"]
    assert initial["governance_tier_source"] == "admission"
    assert initial["job_id"] == resumed["job_id"] == job_id


def test_effective_tier_only_narrows_and_never_promotes():
    from core.governance_tier import effective_governance_tier

    assert effective_governance_tier("autonomous", "running") == (
        "autonomous", "admission")
    assert effective_governance_tier("autonomous", "supervised") == (
        "supervised", "demoted")
    assert effective_governance_tier("autonomous", "student") == (
        "student", "demoted")
    assert effective_governance_tier("student", "autonomous") == (
        "student", "admission")
    assert effective_governance_tier(
        "autonomous", "autonomous", current_enabled=False) == (
            "student", "revoked")
    assert effective_governance_tier("autonomous", "idle") == (
        "student", "current_unverified")
    assert effective_governance_tier(None, "supervised") == (
        "supervised", "current")
    assert effective_governance_tier(None, "running") == (
        "student", "unverified")


def test_stable_run_scope_key_prefers_durable_job_identity():
    from core.bpe.actions import stable_run_scope_key

    assert stable_run_scope_key(
        job_id="job-1", chat_session_id="chat-1") == "job-1"
    assert stable_run_scope_key(chat_session_id="chat-1") == "chat-1"
    first = stable_run_scope_key()
    second = stable_run_scope_key()
    assert first and second
    assert first != second


# ---------------------------------------------------------------------------
# Current actor at the BPE leaf
# ---------------------------------------------------------------------------


@pytest.fixture
def actor_env(tmp_path, monkeypatch):
    import core.database as core_database
    import core.models  # noqa: F401 - table registration
    from core.bpe import actions as bpe_actions
    from core.bpe import persistence, workspace

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path / "bpe")
    importlib.reload(bpe_actions)
    workspace.reset_registry()

    engine = create_engine(
        f"sqlite:///{tmp_path / 'actor.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as db:
        db.add(Tenant(id="t-actor", name="actor scratch",
                      subdomain="actor-scratch"))
        db.commit()
        db.add(Workspace(id="ws-a", name="A", tenant_id="t-actor"))
        db.add(Workspace(id="ws-b", name="B", tenant_id="t-actor"))
        db.commit()
        db.add(User(
            id="user-a", email="a@actor.example.invalid",
            first_name="A", last_name="Actor", role="member",
            status="active", is_active=True, tenant_id="t-actor",
            workspace_id="ws-a",
        ))
        db.commit()

    @contextmanager
    def _db_session():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(core_database, "get_db_session", _db_session)
    yield SimpleNamespace(Session=Session, engine=engine)
    workspace.reset_registry()
    engine.dispose()


def _server_bound_context(job_id="job-actor-1"):
    from core.bpe.actions import PRINCIPAL_SCOPE_CONTEXT_KEY

    return {
        PRINCIPAL_SCOPE_CONTEXT_KEY: {
            "workspace_id": "ws-a",
            "agent_id": "a1",
            "scope_key": job_id,
            "user_id": "user-a",
        },
    }


@pytest.mark.asyncio
async def test_admitted_actor_is_verified_with_bounded_sessions(actor_env):
    """Active actor lands; disabled/moved actor is refused with zero note."""
    from core.action_registry import action_registry
    from core.bpe import workspace

    result = await action_registry.execute_action(
        "workspace.note", {"content": "active actor note"},
        _server_bound_context(),
    )
    assert result["success"] is True, result
    scope_key = "user:user-a:job-actor-1"
    snap = workspace.get_workspace_snapshot("ws-a", "a1", scope_key)
    assert snap["pending_notes"] == ["active actor note"]

    with actor_env.Session() as db:
        user = db.get(User, "user-a")
        user.status = "disabled"
        user.is_active = False
        db.commit()

    denied = await action_registry.execute_action(
        "workspace.note", {"content": "must not land"},
        _server_bound_context(),
    )
    assert denied["success"] is False, denied
    assert denied["error"] == "scope_principal_inactive", denied
    assert denied["action_result"] == "not_applied"
    assert workspace.get_workspace_snapshot(
        "ws-a", "a1", scope_key)["pending_notes"] == ["active actor note"]

    with actor_env.Session() as db:
        user = db.get(User, "user-a")
        user.status = "active"
        user.is_active = True
        user.workspace_id = "ws-b"
        db.commit()

    moved = await action_registry.execute_action(
        "workspace.note", {"content": "moved actor must not land"},
        _server_bound_context(),
    )
    assert moved["success"] is False, moved
    assert moved["error"] == "scope_authority_changed", moved
    assert moved["action_result"] == "not_applied"
    assert workspace.get_workspace_snapshot(
        "ws-a", "a1", scope_key)["pending_notes"] == ["active actor note"]
    assert workspace.get_workspace_snapshot(
        "ws-b", "a1", "user:user-a:job-actor-1") is None


# ---------------------------------------------------------------------------
# Root public valid/refused actor twins (real review, unchanged assertions)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("revoke", [False, True])
def test_public_note_respects_actor_revocation_after_real_review(
    real_env, monkeypatch, tmp_path, revoke,
):
    import core.bpe.actions as actions
    import core.bpe.persistence as persistence
    from core.bpe.workspace import reset_registry

    importlib.reload(actions)
    root = tmp_path / "public_bpe"
    monkeypatch.setenv("ATOM_BPE_WORKSPACE_ENABLED", "true")
    monkeypatch.setattr(persistence, "DATA_DIR", root)
    reset_registry()
    _seed_board(real_env)

    with real_env.SessionLocal() as db:
        db.add(User(
            id="root-reviewer", email="root-reviewer@example.invalid",
            first_name="Root", last_name="Reviewer", role="team_lead",
            status="active", is_active=True, tenant_id="t1",
            workspace_id="ws1",
        ))
        db.commit()
    monkeypatch.setattr(
        interventions, "get_db_session", real_env.db_session)
    original_wait = generic.GenericAgent._wait_for_approval

    async def reviewed_then_real_wait(self, action_id):
        result = await interventions.InterventionService(
        ).approve_intervention(action_id, "root-reviewer")
        assert result.get("success") is True, result
        with real_env.SessionLocal() as db:
            row = db.get(HITLAction, action_id)
            assert row.status == "approved"
            assert row.reviewed_by == "root-reviewer"
        return await original_wait(self, action_id)

    monkeypatch.setattr(
        generic.GenericAgent, "_wait_for_approval", reviewed_then_real_wait)
    trace = []
    original_call = generic.mcp_service.call_tool

    async def observed_call(*args, **kwargs):
        result = await original_call(*args, **kwargs)
        trace.append({
            "type": type(result).__name__,
            "result": str(result)[:1200],
            "tier_at_issuance": (
                kwargs.get("context") or {}).get("tier_at_issuance"),
        })
        return result

    monkeypatch.setattr(generic.mcp_service, "call_tool", observed_call)
    marker = "root-public-note-authority-marker"

    def first(task_input, history, context):
        if revoke:
            with real_env.SessionLocal() as db:
                user = db.get(User, "member-1")
                user.status = "disabled"
                user.is_active = False
                db.commit()
        return ReActStep(
            thought="Record the admitted task fact",
            action=ToolCall(
                tool="workspace.note", params={"content": marker}),
        )

    _install_model(monkeypatch, [first])
    response = _run(
        real_env,
        operation_id="root-public-note-" + str(revoke),
        parameters={"sync": True, "task_input": "Record a task fact"},
    )
    records = [
        json.loads(p.read_text())
        for p in root.glob("*.json")
    ]
    wrote = marker in json.dumps(records)
    capture = {
        "revoked": revoke,
        "http": response.status_code,
        "persisted_marker": wrote,
        "transport_trace": trace,
    }
    try:
        assert wrote is (not revoke), capture
        if not revoke:
            assert trace, capture
            assert any(
                entry.get("tier_at_issuance") == "autonomous"
                for entry in trace), capture
    finally:
        reset_registry()
