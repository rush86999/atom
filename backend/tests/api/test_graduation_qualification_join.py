"""Executable counterexamples for the scoped qualification join.

Real scratch SQLite + real FastAPI routes + real JWT. No model/provider/
browser/live DB. These are policy-path controls, not capability proof.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

import core.agent_graduation_service as grad
from core.agent_governance_service import AgentGovernanceService
from core.agent_graduation_service import (
    evaluate_qualification_gate,
    find_qualification_receipt,
)
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import (
    AgentEpisode,
    AgentExecution,
    Artifact,
    EpisodeSegment,
    AgentProposal,
    AgentRegistry,
    AuditLog,
    GraduationExam,
    HITLAction,
    HITLActionStatus,
    PromotionHistory,
    RuntimeSetting,
    SupervisionSession,
    Tenant,
    TrainingSession,
    User,
    Workspace,
)
from core.promotion_policy_service import (
    ASSESSMENT_POLICY_KEY,
    AssessmentPolicyError,
    get_assessment_policy,
)
from core.student_training_service import StudentTrainingService, TrainingOutcome
from core.graduation_exam import GraduationExamService
from core.supervision_service import (
    SupervisionDirtyCallerWorkError,
    SupervisionService,
)
from core.agent_context_resolver import AgentContextResolver
from api.agent_onboarding_routes import router as onboarding_router
from api.agent_routes import router as agent_router
from api.episode_routes import router as episode_router

grad.get_lancedb_handler = lambda: None
grad.POMDP_AVAILABLE = False

COMPANY, WS_A, OTHER, WS_B = "company", "ws-a", "other", "ws-b"
SUPERVISOR, MEMBER, ADMIN, AGENT = "supervisor", "member", "admin", "student-agent"


class World:
    def __init__(self, tmp_path: Path, episodes: int = 10, sessions: int = 1):
        self.db_path = tmp_path / "qualification.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        started = datetime.now(timezone.utc) - timedelta(days=2)
        with self.Session() as db:
            db.add_all([
                Tenant(id=COMPANY, name="Company", subdomain=f"q-{uuid.uuid4().hex[:6]}",
                       edition="personal", is_active=True),
                Tenant(id=OTHER, name="Other", subdomain=f"o-{uuid.uuid4().hex[:6]}",
                       edition="personal", is_active=True),
            ])
            db.add_all([
                Workspace(id=WS_A, name="A", tenant_id=COMPANY),
                Workspace(id=WS_B, name="B", tenant_id=OTHER),
            ])
            db.add_all([
                User(id=SUPERVISOR, tenant_id=COMPANY, workspace_id=WS_A,
                     email="sup@example.test", first_name="S", last_name="V",
                     role="team_lead", status="active", is_active=True),
                User(id=MEMBER, tenant_id=COMPANY, workspace_id=WS_A,
                     email="mem@example.test", first_name="M", last_name="V",
                     role="member", status="active", is_active=True),
                User(id=ADMIN, tenant_id=COMPANY, workspace_id=WS_A,
                     email="adm@example.test", first_name="A", last_name="V",
                     role="admin", status="active", is_active=True),
                User(id="foreign-sup", tenant_id=OTHER, workspace_id=WS_B,
                     email="foreign@example.test", first_name="F", last_name="V",
                     role="team_lead", status="active", is_active=True),
            ])
            db.add(AgentRegistry(
                id=AGENT, name="Scratch Student", category="operations",
                role="agent", type="personal", capabilities=[],
                module_path="core.generic_agent", class_name="GenericAgent",
                user_id=SUPERVISOR, workspace_id=WS_A, tenant_id=COMPANY,
                status="student", enabled=True, confidence_score=0.62,
                configuration={"learning": {"role": "operations", "log": []}},
            ))
            for i in range(episodes):
                db.add(AgentExecution(
                    id=f"exec-{i:02d}", agent_id=AGENT, tenant_id=COMPANY,
                    workspace_id=WS_A, status="completed",
                    input_summary=f"held-out task {i}",
                    result_summary=f"actual durable output {i}",
                    completed_at=started + timedelta(minutes=i + 5),
                ))
                db.add(AgentEpisode(
                    id=f"ep-{i:02d}", agent_id=AGENT, tenant_id=COMPANY,
                    workspace_id=WS_A, execution_id=f"exec-{i:02d}",
                    task_description=f"held-out work {i}",
                    maturity_at_time="student", constitutional_score=0.9,
                    human_intervention_count=0, confidence_score=0.62,
                    outcome="success", success=True, status="completed",
                    started_at=started + timedelta(minutes=i),
                    completed_at=started + timedelta(minutes=i + 5),
                ))
            db.add(Artifact(
                id="artifact-1", tenant_id=COMPANY, workspace_id=WS_A,
                agent_id=AGENT, name="Held-out output", type="markdown",
                content="actual artifact output for held-out work",
                version=1,
            ))
            db.add(EpisodeSegment(
                id="seg-1", episode_id="ep-00", segment_type="execution",
                sequence_order=1, content="actual segment output",
            ))
            db.add(AgentEpisode(
                id="ep-history", agent_id=AGENT, tenant_id=COMPANY,
                workspace_id=WS_A, task_description="history-only episode",
                maturity_at_time="student", constitutional_score=0.9,
                human_intervention_count=0, confidence_score=0.62,
                outcome="success", success=True, status="completed",
                started_at=started - timedelta(minutes=10),
                completed_at=started - timedelta(minutes=5),
            ))
            for i in range(sessions):
                db.add(AgentProposal(
                    id=f"proposal-{i}", tenant_id=COMPANY, user_id=SUPERVISOR,
                    agent_id=AGENT, agent_name="Scratch Student",
                    title=f"training {i}", proposal_type="action",
                    proposal_data={}, status="executed",
                ))
                db.add(TrainingSession(
                    id=f"session-{i}", tenant_id=COMPANY,
                    proposal_id=f"proposal-{i}", agent_id=AGENT,
                    agent_name="Scratch Student", status="completed",
                    started_at=started, completed_at=started + timedelta(hours=1),
                    supervisor_id=SUPERVISOR, tasks_completed=10, total_tasks=10,
                    performance_score=1.0, confidence_boost=0.12,
                    promoted_to_intern=False,
                ))
            db.commit()

    def client(self) -> TestClient:
        app = FastAPI()
        app.include_router(episode_router)
        app.include_router(onboarding_router)
        app.include_router(agent_router)

        def override():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override
        return TestClient(app, base_url="http://testserver")

    def token(self, user_id: str) -> str:
        with self.Session() as db:
            user = db.get(User, user_id)
            return create_access_token({"sub": user.id}, user=user)

    def receipt(self):
        with self.Session() as db:
            agent = db.get(AgentRegistry, AGENT)
            return db.query(GraduationExam).filter(
                GraduationExam.id == (agent.last_exam_id or "")).first()


def call(client, method, path, token_value, **kwargs):
    r = client.request(method, path,
                       headers={"Authorization": f"Bearer {token_value}"},
                       **kwargs)
    try:
        body = r.json()
    except Exception:
        body = None
    return {"status": r.status_code, "json": body}


def request_review(client, token_value, evidence=None, target="INTERN"):
    return call(
        client, "POST", "/api/episodes/graduation/qualification/request",
        token_value,
        json={
            "agent_id": AGENT,
            "target_maturity": target,
            "evidence_refs": evidence or [
                {"kind": "agent_episode", "id": "ep-00"},
                {"kind": "agent_execution", "id": "exec-00"},
            ],
            "rubric_version": "heldout-v1",
        },
    )


def approve(client, admin_token, action_id):
    return call(
        client, "POST", f"/api/agents/approvals/{action_id}", admin_token,
        json={"decision": "approved", "feedback": "held-out work reviewed"},
    )


def promote(client, token_value, operation_id=None, target="INTERN"):
    suffix = f"&operation_id={operation_id}" if operation_id else ""
    return call(
        client, "POST",
        f"/api/episodes/graduation/promote?agent_id={AGENT}"
        f"&new_maturity={target}{suffix}",
        token_value,
    )


def qualify(world: World, target="INTERN"):
    client = world.client()
    sup, admin = world.token(SUPERVISOR), world.token(ADMIN)
    requested = request_review(client, sup, target=target)
    assert requested["status"] == 200, requested
    action_id = requested["json"]["data"]["action_id"]
    approved = approve(client, admin, action_id)
    assert approved["status"] == 200, approved
    return action_id


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_missing_receipt_blocks_then_review_unlocks_promotion(world):
    client = world.client()
    sup, admin = world.token(SUPERVISOR), world.token(ADMIN)

    readiness = call(client, "GET",
                     f"/api/episodes/graduation/readiness/{AGENT}?target_maturity=INTERN",
                     sup)
    assert readiness["status"] == 200
    assert readiness["json"]["assessment"]["state"] == "unresolved_missing"

    blocked = promote(client, sup)
    assert blocked["status"] == 409
    assert blocked["json"]["detail"]["status"] == "unresolved"

    requested = request_review(client, sup)
    assert requested["status"] == 200, requested
    action_id = requested["json"]["data"]["action_id"]
    assert approve(client, admin, action_id)["status"] == 200

    promoted = promote(client, sup)
    assert promoted["status"] == 200, promoted
    assert promoted["json"]["data"]["promoted"] is True
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        history = db.query(PromotionHistory).filter(
            PromotionHistory.agent_id == AGENT).one()
        assert agent.status == "intern"
        assert agent.last_exam_id == history.exam_id
        assert history.exam_id
        assert db.query(func.count(GraduationExam.id)).scalar() == 1
        assert db.query(func.count(AuditLog.id)).scalar() == 1


def test_exact_replay_after_fresh_session_and_changed_material(world):
    client = world.client()
    sup = world.token(SUPERVISOR)
    qualify(world)
    first = promote(client, sup)
    assert first["status"] == 200, first
    operation_id = first["json"]["data"]["operation_id"]

    # Fresh engine/session, same operation id: replay the original receipt.
    world.engine.dispose()
    fresh = create_engine(
        f"sqlite:///{world.db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    world.engine = fresh
    world.Session = sessionmaker(bind=fresh, expire_on_commit=False)
    replay_client = world.client()
    replay_token = world.token(SUPERVISOR)
    replay = promote(replay_client, replay_token, operation_id=operation_id)
    assert replay["status"] == 200, replay
    assert replay["json"]["data"]["promoted"] is True
    with world.Session() as db:
        assert db.query(func.count(PromotionHistory.id)).scalar() == 1
        assert db.query(func.count(GraduationExam.id)).scalar() == 1

    # Changed target with the same operation id: no replay, no second effect.
    changed_target = promote(
        replay_client, replay_token, operation_id=operation_id,
        target="SUPERVISED")
    assert changed_target["status"] == 409, changed_target
    with world.Session() as db:
        assert db.query(func.count(PromotionHistory.id)).scalar() == 1

    # Changed receipt material with the same operation id: refuse.
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        legacy = GraduationExam(
            id="legacy-exam-1", agent_id=AGENT, tenant_id=COMPANY,
            target_level="INTERN", current_level="student",
            readiness_score=0.9, zero_intervention_ratio=1.0,
            avg_constitutional_score=0.9, avg_confidence_score=0.6,
            success_rate=1.0, episodes_analyzed=10,
            passed=True, promoted=False,
            metadata_json={"receipt_kind": "legacy_history_statistics"},
        )
        db.add(legacy)
        agent.last_exam_id = "legacy-exam-1"
        db.commit()
    changed_material = promote(
        replay_client, replay_token, operation_id=operation_id)
    assert changed_material["status"] == 409, changed_material
    with world.Session() as db:
        assert db.query(func.count(PromotionHistory.id)).scalar() == 1


def test_required_receipt_fields_and_review_authority(world):
    qualify(world)

    def check(mutator, expected_state=None):
        with world.Session() as db:
            agent = db.get(AgentRegistry, AGENT)
            receipt = db.query(GraduationExam).filter(
                GraduationExam.id == agent.last_exam_id).one()
            review_id = receipt.metadata_json["review_action_id"]
            review = db.get(HITLAction, review_id)
            original = {
                "metadata": dict(receipt.metadata_json),
                "passed": receipt.passed,
                "target": receipt.target_level,
                "current": receipt.current_level,
                "review_status": review.status,
                "review_params": dict(review.params or {}),
                "reviewed_by": review.reviewed_by,
                "role": db.get(User, ADMIN).role,
            }
            mutator(db, receipt, review)
            flag_modified(receipt, "metadata_json")
            flag_modified(review, "params")
            db.commit()
            result = find_qualification_receipt(
                db, agent, "INTERN", get_assessment_policy(db))
            assert not result.get("ok"), result
            if expected_state:
                assert result["state"] == expected_state, result
            # Restore the exact durable material for the next independent case.
            receipt = db.get(GraduationExam, receipt.id)
            review = db.get(HITLAction, review_id)
            receipt.metadata_json = original["metadata"]
            receipt.passed = original["passed"]
            receipt.target_level = original["target"]
            receipt.current_level = original["current"]
            review.status = original["review_status"]
            review.params = original["review_params"]
            review.reviewed_by = original["reviewed_by"]
            db.get(User, ADMIN).role = original["role"]
            db.commit()

    check(lambda d, r, v: r.metadata_json.pop("workspace_id"),
          "unresolved_scope")
    check(lambda d, r, v: r.metadata_json.__setitem__("workspace_id", 123),
          "unresolved_scope")
    check(lambda d, r, v: r.metadata_json.pop("policy_digest"),
          "unresolved_stale")
    check(lambda d, r, v: r.metadata_json.pop("policy_revision"),
          "unresolved_stale")
    check(lambda d, r, v: r.metadata_json.pop("rubric_version"),
          "unresolved_stale")
    check(lambda d, r, v: r.metadata_json.pop("source_revision"),
          "unresolved_stale")
    check(lambda d, r, v: r.metadata_json.__setitem__("evidence_refs", []),
          "unresolved_missing")
    check(lambda d, r, v: r.metadata_json.pop("review_action_id"),
          "unresolved_failed")
    check(lambda d, r, v: r.metadata_json.pop("reviewed_by"),
          "unresolved_scope")
    check(lambda d, r, v: r.metadata_json.__setitem__(
        "candidate_capability_qualified", "true"), "unresolved_failed")
    check(lambda d, r, v: setattr(r, "passed", False), "unresolved_failed")
    check(lambda d, r, v: setattr(v, "status", "rejected"),
          "unresolved_failed")
    check(lambda d, r, v: v.params.__setitem__("source_revision", "wrong"),
          "unresolved_stale")
    check(lambda d, r, v: setattr(d.get(User, ADMIN), "role", "team_lead"),
          "unresolved_scope")

def test_governance_hook_preserves_caller_work(world):
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        agent.confidence_score = 0.49
        db.commit()

    for kind in ("dirty", "new", "deleted"):
        with world.Session() as db:
            agent = db.get(AgentRegistry, AGENT)
            agent.confidence_score = 0.49
            if kind == "dirty":
                other = db.get(User, MEMBER)
                other.first_name = "caller-dirty"
                pending = other
            elif kind == "new":
                pending = AgentRegistry(
                    id=f"caller-new-{uuid.uuid4().hex[:6]}",
                    name="Caller New", category="test", role="agent",
                    type="personal", capabilities=[], module_path="test",
                    class_name="Test", tenant_id=COMPANY, workspace_id=WS_A,
                    status="student", enabled=True,
                )
                db.add(pending)
            else:
                pending = db.get(User, MEMBER)
                db.delete(pending)
            pending_id = getattr(pending, "id", None)
            db.flush()
            AgentGovernanceService(
                db, workspace_id=WS_A, tenant_id=COMPANY
            )._update_confidence_score(AGENT, positive=True, impact_level="high")
            # The caller's uncommitted work is not visible to a peer session:
            # nothing was committed by the governance hook.
            with world.Session() as peer:
                if kind == "dirty":
                    assert peer.get(User, MEMBER).first_name != "caller-dirty"
                elif kind == "new":
                    assert peer.get(AgentRegistry, pending_id) is None
                else:
                    assert peer.get(User, MEMBER) is not None
                assert peer.get(AgentRegistry, AGENT).status == "student"
            db.rollback()


def test_policy_null_row_is_invalid_and_fresh_read_defeats_cache(world):
    with world.Session() as db:
        db.add(RuntimeSetting(
            key=ASSESSMENT_POLICY_KEY, value_json=None,
            updated_by="test"))
        db.commit()
        with pytest.raises(AssessmentPolicyError) as exc:
            get_assessment_policy(db)
        assert exc.value.state == "configuration_required"

    # Fresh read defeats a retained ORM RuntimeSetting.
    with world.Session() as db:
        row = db.get(RuntimeSetting, ASSESSMENT_POLICY_KEY)
        row.value_json = {
            "schema_version": "atom-graduation-assessment-policy-1",
            "revision": "1",
            "default_required": True,
            "tiers": {"intern": True, "supervised": True, "autonomous": True},
            "exceptions": {
                "legacy": {"allowed": True, "agent_ids": [AGENT],
                           "domains": [], "state": "legacy_unassessed"},
                "manual": {"allowed": False, "agent_ids": [], "domains": [],
                           "state": "manual_override"},
                "system": {"allowed": False, "agent_ids": [], "domains": [],
                           "state": "system_exempt"},
            },
            "evaluator": "human_review",
            "rubric_version": "heldout-v1",
            "source_revision": "agent-evidence-v1",
        }
        db.commit()
        # Cache the row in this identity map.
        cached = db.get(RuntimeSetting, ASSESSMENT_POLICY_KEY)
        assert cached is not None
        with world.Session() as peer:
            row = peer.get(RuntimeSetting, ASSESSMENT_POLICY_KEY)
            row.value_json = {
                "schema_version": "atom-graduation-assessment-policy-1",
                "revision": "1",
                "default_required": True,
                "tiers": {"intern": True, "supervised": True,
                          "autonomous": True},
                "exceptions": {
                    "legacy": {"allowed": False, "agent_ids": [], "domains": [],
                               "state": "legacy_unassessed"},
                    "manual": {"allowed": False, "agent_ids": [], "domains": [],
                               "state": "manual_override"},
                    "system": {"allowed": False, "agent_ids": [], "domains": [],
                               "state": "system_exempt"},
                },
                "evaluator": "human_review",
                "rubric_version": "heldout-v1",
                "source_revision": "agent-evidence-v1",
            }
            peer.commit()
        fresh = get_assessment_policy(db)
        assert fresh["policy"].exceptions.legacy.allowed is False


def test_peer_policy_change_before_target_dml_refuses(world, monkeypatch):
    qualify(world)
    from core import agent_decision_write_service as writes

    original = writes.commit_graduation

    def wrapper(*args, **kwargs):
        with world.Session() as peer:
            row = peer.get(RuntimeSetting, ASSESSMENT_POLICY_KEY)
            if row is None:
                row = RuntimeSetting(key=ASSESSMENT_POLICY_KEY)
                peer.add(row)
            row.value_json = {
                "schema_version": "atom-graduation-assessment-policy-1",
                "revision": "peer-change",
                "default_required": True,
                "tiers": {"intern": True, "supervised": True,
                          "autonomous": True},
                "exceptions": {
                    "legacy": {"allowed": False, "agent_ids": [], "domains": [],
                               "state": "legacy_unassessed"},
                    "manual": {"allowed": False, "agent_ids": [], "domains": [],
                               "state": "manual_override"},
                    "system": {"allowed": False, "agent_ids": [], "domains": [],
                               "state": "system_exempt"},
                },
                "evaluator": "human_review",
                "rubric_version": "heldout-v1",
                "source_revision": "agent-evidence-v1",
            }
            peer.commit()
        return original(*args, **kwargs)

    monkeypatch.setattr(writes, "commit_graduation", wrapper)
    result = promote(world.client(), world.token(SUPERVISOR))
    assert result["status"] == 409, result
    with world.Session() as db:
        assert db.get(AgentRegistry, AGENT).status == "student"


def test_peer_receipt_and_evidence_change_before_target_dml_refuses(world, monkeypatch):
    qualify(world)
    from core import agent_decision_write_service as writes

    for change in ("receipt", "evidence"):
        original = writes.commit_graduation

        def wrapper(*args, **kwargs):
            with world.Session() as peer:
                agent = peer.get(AgentRegistry, AGENT)
                if change == "receipt":
                    receipt = peer.get(GraduationExam, agent.last_exam_id)
                    receipt.passed = False
                else:
                    episode = peer.get(AgentEpisode, "ep-00")
                    episode.task_description = "peer changed evidence"
                peer.commit()
            return original(*args, **kwargs)

        monkeypatch.setattr(writes, "commit_graduation", wrapper)
        result = promote(world.client(), world.token(SUPERVISOR))
        assert result["status"] == 409, (change, result)
        with world.Session() as db:
            assert db.get(AgentRegistry, AGENT).status == "student"
        # Restore for the next case.
        with world.Session() as db:
            agent = db.get(AgentRegistry, AGENT)
            receipt = db.get(GraduationExam, agent.last_exam_id)
            if receipt is not None:
                receipt.passed = True
            episode = db.get(AgentEpisode, "ep-00")
            episode.task_description = "held-out work 0"
            db.commit()
        monkeypatch.setattr(writes, "commit_graduation", original)


def test_member_foreign_and_deactivated_controls(world):
    client = world.client()
    member = world.token(MEMBER)
    foreign = world.token("foreign-sup")
    sup = world.token(SUPERVISOR)
    assert promote(client, member)["status"] == 403
    assert promote(client, foreign)["status"] == 404
    assert call(client, "GET",
                f"/api/episodes/graduation/readiness/{AGENT}?target_maturity=INTERN",
                foreign)["status"] == 404
    token_before = world.token(SUPERVISOR)
    with world.Session() as db:
        user = db.get(User, SUPERVISOR)
        user.is_active = False
        user.status = "inactive"
        db.commit()
    assert call(client, "GET",
                f"/api/episodes/graduation/readiness/{AGENT}?target_maturity=INTERN",
                token_before)["status"] == 401


def test_legacy_exception_is_explicit_and_unassessed(world, monkeypatch):
    policy = {
        "schema_version": "atom-graduation-assessment-policy-1",
        "revision": "legacy-explicit-1",
        "default_required": True,
        "tiers": {"intern": True, "supervised": True, "autonomous": True},
        "exceptions": {
            "legacy": {"allowed": True, "agent_ids": [AGENT], "domains": [],
                       "reason": "Owner-approved legacy continuity for this exact agent.",
                       "state": "legacy_unassessed"},
            "manual": {"allowed": False, "agent_ids": [], "domains": [],
                       "state": "manual_override"},
            "system": {"allowed": False, "agent_ids": [], "domains": [],
                       "state": "system_exempt"},
        },
        "evaluator": "human_review",
        "rubric_version": "heldout-v1",
        "source_revision": "agent-evidence-v1",
    }
    monkeypatch.setenv(ASSESSMENT_POLICY_KEY, json.dumps(policy))
    result = promote(world.client(), world.token(SUPERVISOR))
    assert result["status"] == 200, result
    assert result["json"]["data"]["promoted"] is True
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        history = db.query(PromotionHistory).filter(
            PromotionHistory.agent_id == AGENT).one()
        assert agent.status == "intern"
        assert history.exam_id is None
        assert result["json"]["data"]["assessment"]["state"] == "legacy_unassessed"
        assert result["json"]["data"]["assessment"]["exception"]["reason"] == (
            "Owner-approved legacy continuity for this exact agent.")
        assert result["json"]["data"]["assessment"][
            "candidate_capability_qualified"] is False


def test_manual_promotion_requires_explicit_exception(world, monkeypatch):
    client = world.client()
    admin = world.token(ADMIN)
    blocked = call(client, "POST", f"/api/agents/{AGENT}/promote", admin)
    assert blocked["status"] == 409, blocked
    assert blocked["json"]["detail"]["error"]["code"] == "QUALIFICATION_REQUIRED"
    policy = {
        "schema_version": "atom-graduation-assessment-policy-1",
        "revision": "manual-explicit-1",
        "default_required": True,
        "tiers": {"intern": True, "supervised": True, "autonomous": True},
        "exceptions": {
            "legacy": {"allowed": False, "agent_ids": [], "domains": [],
                       "state": "legacy_unassessed"},
            "manual": {"allowed": True, "agent_ids": [AGENT], "domains": [],
                       "reason": "Owner-approved manual continuity for this exact agent.",
                       "state": "manual_override"},
            "system": {"allowed": False, "agent_ids": [], "domains": [],
                       "state": "system_exempt"},
        },
        "evaluator": "human_review",
        "rubric_version": "heldout-v1",
        "source_revision": "agent-evidence-v1",
    }
    monkeypatch.setenv(ASSESSMENT_POLICY_KEY, json.dumps(policy))
    allowed = call(client, "POST", f"/api/agents/{AGENT}/promote", admin)
    assert allowed["status"] == 200, allowed
    assert allowed["json"]["data"]["agent_status"] == "autonomous"
    assert allowed["json"]["data"]["assessment"]["state"] == "manual_override"
    assert allowed["json"]["data"]["assessment"][
        "candidate_capability_qualified"] is False


def test_restart_readback_from_fresh_os_process(world):
    qualify(world)
    assert promote(world.client(), world.token(SUPERVISOR))["status"] == 200
    world.engine.dispose()
    script = (
        "import json,sqlite3,sys;"
        "db=sqlite3.connect(sys.argv[1]);"
        "a=db.execute(\"select status,last_exam_id,promotion_count from agent_registry where id='student-agent'\").fetchone();"
        "h=db.execute(\"select count(*),max(exam_id) from promotion_history where agent_id='student-agent'\").fetchone();"
        "print(json.dumps({'agent':a,'history':h}))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script, str(world.db_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["agent"][0] == "intern"
    assert payload["agent"][1]
    assert payload["agent"][2] == 1
    assert payload["history"][0] == 1
    assert payload["history"][1] == payload["agent"][1]


def test_training_completion_requires_receipt(tmp_path):
    world = World(tmp_path, sessions=3)
    # Three completed sessions + 10 episodes make the training evidence gate
    # ready; the qualification gate still decides the tier.
    with world.Session() as db:
        for i in (3, 4):
            db.add(AgentProposal(
                id=f"proposal-{i}", tenant_id=COMPANY, user_id=SUPERVISOR,
                agent_id=AGENT, agent_name="Scratch Student",
                title=f"training {i}", proposal_type="action",
                proposal_data={}, status="approved",
            ))
            db.add(TrainingSession(
                id=f"session-{i}", tenant_id=COMPANY,
                proposal_id=f"proposal-{i}", agent_id=AGENT,
                agent_name="Scratch Student", status="in_progress",
                started_at=datetime.now(timezone.utc) - timedelta(days=3),
                completed_at=None, supervisor_id=SUPERVISOR,
                tasks_completed=0, total_tasks=10,
            ))
        db.commit()

    outcome = TrainingOutcome(
        performance_score=1.0, supervisor_feedback="held-out work reviewed",
        errors_count=0, tasks_completed=10, total_tasks=10,
        capabilities_developed=[], capability_gaps_remaining=[],
    )
    with world.Session() as db:
        blocked = asyncio.run(
            StudentTrainingService(db).complete_training_session(
                "session-3", outcome, actor_id=SUPERVISOR))
    assert blocked["promoted_to_intern"] is False
    assert blocked["new_status"] == "student"
    assert blocked["promotion"]["assessment"]["state"] == "unresolved_missing"

    qualify(world)
    with world.Session() as db:
        allowed = asyncio.run(
            StudentTrainingService(db).complete_training_session(
                "session-4", outcome, actor_id=SUPERVISOR))
    assert allowed["promoted_to_intern"] is True
    assert allowed["new_status"] == "intern"
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        assert agent.status == "intern"
        assert agent.last_exam_id
        assert db.query(func.count(PromotionHistory.id)).scalar() == 1


def test_legacy_exam_does_not_overwrite_qualification_pointer(world):
    qualify(world)
    assert promote(world.client(), world.token(SUPERVISOR))["status"] == 200
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        receipt_id = agent.last_exam_id
        assert receipt_id
        service = GraduationExamService(db)
        service.execute_graduation_exam(
            agent_id=AGENT, tenant_id=COMPANY,
            target_level="supervised", promoted_by=SUPERVISOR)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        assert agent.status == "intern"
        assert agent.last_exam_id == receipt_id
        legacy = db.query(GraduationExam).filter(
            GraduationExam.metadata_json.isnot(None)).all()
        assert any(
            (row.metadata_json or {}).get("receipt_kind")
            == "legacy_history_statistics" for row in legacy)



def _set_db_policy(world, policy):
    with world.Session() as db:
        row = db.get(RuntimeSetting, ASSESSMENT_POLICY_KEY)
        if row is None:
            row = RuntimeSetting(key=ASSESSMENT_POLICY_KEY)
            db.add(row)
        row.value_json = policy
        db.commit()


def _legacy_policy(allowed=True):
    return {
        "schema_version": "atom-graduation-assessment-policy-1",
        "revision": "db-exception-1",
        "default_required": True,
        "tiers": {"intern": True, "supervised": True, "autonomous": True},
        "exceptions": {
            "legacy": {"allowed": allowed, "agent_ids": [AGENT], "domains": [],
                       **({"reason": "Owner-approved legacy continuity for this exact agent."}
                          if allowed else {}),
                       "state": "legacy_unassessed"},
            "manual": {"allowed": False, "agent_ids": [], "domains": [],
                       "state": "manual_override"},
            "system": {"allowed": False, "agent_ids": [], "domains": [],
                       "state": "system_exempt"},
        },
        "evaluator": "human_review",
        "rubric_version": "heldout-v1",
        "rubric_criteria": [
            {"id": "task_context", "label": "Task/context is inspectable"},
            {"id": "actual_output", "label": "Actual output is present"},
        ],
        "source_revision": "agent-evidence-v1",
    }


def test_peer_exception_revocation_before_dml_refuses(world, monkeypatch):
    _set_db_policy(world, _legacy_policy(True))
    from core import agent_decision_write_service as writes

    original = writes.commit_graduation

    def wrapper(*args, **kwargs):
        _set_db_policy(world, _legacy_policy(False))
        return original(*args, **kwargs)

    monkeypatch.setattr(writes, "commit_graduation", wrapper)
    result = promote(world.client(), world.token(SUPERVISOR))
    assert result["status"] == 409, result
    with world.Session() as db:
        assert db.get(AgentRegistry, AGENT).status == "student"


def test_peer_policy_value_change_without_timestamp_refuses(world, monkeypatch):
    from sqlalchemy import text

    _set_db_policy(world, _legacy_policy(True))
    from core import agent_decision_write_service as writes

    original = writes.commit_graduation

    def wrapper(*args, **kwargs):
        # Direct SQL changes value_json without touching updated_at.
        with world.Session() as peer:
            peer.execute(
                text("UPDATE runtime_settings SET value_json=:v WHERE key=:k"),
                {"v": json.dumps(_legacy_policy(False)),
                 "k": ASSESSMENT_POLICY_KEY},
            )
            peer.commit()
        return original(*args, **kwargs)

    monkeypatch.setattr(writes, "commit_graduation", wrapper)
    result = promote(world.client(), world.token(SUPERVISOR))
    assert result["status"] == 409, result
    with world.Session() as db:
        assert db.get(AgentRegistry, AGENT).status == "student"


def test_same_passed_receipt_and_review_changes_before_dml_refuse(world, monkeypatch):
    qualify(world)
    from core import agent_decision_write_service as writes
    from sqlalchemy.orm.attributes import flag_modified

    for change in ("workspace", "reviewer", "source", "review_params"):
        original = writes.commit_graduation

        def wrapper(*args, **kwargs):
            with world.Session() as peer:
                agent = peer.get(AgentRegistry, AGENT)
                receipt = peer.get(GraduationExam, agent.last_exam_id)
                review = peer.get(
                    HITLAction, receipt.metadata_json["review_action_id"])
                if change == "workspace":
                    receipt.metadata_json["workspace_id"] = WS_B
                elif change == "reviewer":
                    receipt.metadata_json["reviewed_by"] = MEMBER
                elif change == "source":
                    receipt.metadata_json["source_revision"] = "peer-source"
                else:
                    review.params["source_revision"] = "peer-source"
                    flag_modified(review, "params")
                flag_modified(receipt, "metadata_json")
                peer.commit()
            return original(*args, **kwargs)

        monkeypatch.setattr(writes, "commit_graduation", wrapper)
        result = promote(world.client(), world.token(SUPERVISOR))
        assert result["status"] == 409, (change, result)
        with world.Session() as db:
            assert db.get(AgentRegistry, AGENT).status == "student"
        monkeypatch.setattr(writes, "commit_graduation", original)


def test_inactive_status_active_requester_is_refused(world):
    client = world.client()
    token_value = world.token(SUPERVISOR)  # issued before deactivation
    with world.Session() as db:
        user = db.get(User, SUPERVISOR)
        user.is_active = False
        # status deliberately remains "active": the is_active-only negative.
        db.commit()
        before = db.query(func.count(HITLAction.id)).scalar()
    refused = request_review(client, token_value)
    assert refused["status"] == 403, refused
    with world.Session() as db:
        assert db.query(func.count(HITLAction.id)).scalar() == before

    with world.Session() as db:
        user = db.get(User, SUPERVISOR)
        user.is_active = True
        db.commit()
    allowed = request_review(client, token_value)
    assert allowed["status"] == 200, allowed
    with world.Session() as db:
        assert db.query(func.count(HITLAction.id)).scalar() == before + 1


def test_history_only_episode_is_not_qualification(world):
    client = world.client()
    sup = world.token(SUPERVISOR)
    # Ten successful historical episodes, no inspectable output: the old
    # baseline must remain a negative, not be relabelled as held-out proof.
    requested = request_review(
        client, sup, evidence=[{"kind": "agent_episode", "id": "ep-01"}])
    assert requested["status"] == 409, requested
    assert requested["json"]["detail"]["state"] == "unresolved_missing"
    with world.Session() as db:
        assert db.query(func.count(HITLAction.id)).scalar() == 0
    assert promote(client, sup)["status"] == 409


def test_artifact_output_is_qualification(world):
    client = world.client()
    sup, admin = world.token(SUPERVISOR), world.token(ADMIN)
    requested = request_review(
        client, sup,
        evidence=[
            {"kind": "agent_episode", "id": "ep-00"},
            {"kind": "artifact", "id": "artifact-1"},
        ],
    )
    assert requested["status"] == 200, requested
    assert approve(
        client, admin, requested["json"]["data"]["action_id"])["status"] == 200
    promoted = promote(client, sup)
    assert promoted["status"] == 200, promoted
    assert promoted["json"]["data"]["promoted"] is True


def test_evidence_endpoint_excludes_history_only(world):
    client = world.client()
    sup = world.token(SUPERVISOR)
    response = call(
        client, "GET",
        f"/api/episodes/graduation/qualification/evidence/{AGENT}?target_maturity=INTERN",
        sup,
    )
    assert response["status"] == 200, response
    data = response["json"]["data"]
    assert data["rubric_criteria"]
    assert data["items"]
    for item in data["items"]:
        assert item["task_preview"]
        assert item["output_preview"]
        assert item["evidence_refs"]
    assert all(item["episode_id"] != "ep-history" for item in data["items"])
    readiness = call(
        client, "GET",
        f"/api/episodes/graduation/readiness/{AGENT}?target_maturity=INTERN",
        sup,
    )
    assert readiness["status"] == 200
    assert readiness["json"]["assessment_evidence"]
    assert all(
        item["episode_id"] != "ep-history"
        for item in readiness["json"]["assessment_evidence"]
    )


def test_peer_evidence_scope_move_before_dml_refuses(tmp_path, monkeypatch):
    from core import agent_decision_write_service as writes

    cases = {
        "agent_episode": (
            [{"kind": "agent_episode", "id": "ep-00"},
             {"kind": "agent_execution", "id": "exec-00"}],
            "episode",
        ),
        "agent_execution": (
            [{"kind": "agent_episode", "id": "ep-00"},
             {"kind": "agent_execution", "id": "exec-00"}],
            "execution",
        ),
        "artifact": (
            [{"kind": "agent_episode", "id": "ep-00"},
             {"kind": "artifact", "id": "artifact-1"}],
            "artifact",
        ),
        "segment_parent_reassign": (
            [{"kind": "agent_episode", "id": "ep-00"},
             {"kind": "episode_segment", "id": "seg-1"}],
            "segment_reassign",
        ),
        "segment_parent_scope": (
            [{"kind": "agent_episode", "id": "ep-00"},
             {"kind": "episode_segment", "id": "seg-1"}],
            "episode",
        ),
    }
    for name, (evidence, move) in cases.items():
        case_dir = tmp_path / name
        case_dir.mkdir(parents=True, exist_ok=True)
        world = World(case_dir)
        client = world.client()
        sup, admin = world.token(SUPERVISOR), world.token(ADMIN)
        requested = request_review(client, sup, evidence=evidence)
        assert requested["status"] == 200, (name, requested)
        assert approve(
            client, admin, requested["json"]["data"]["action_id"])["status"] == 200
        original = writes.commit_graduation

        def wrapper(*args, **kwargs):
            with world.Session() as peer:
                if move == "episode":
                    episode = peer.get(AgentEpisode, "ep-00")
                    episode.tenant_id = OTHER
                    episode.workspace_id = WS_B
                elif move == "execution":
                    execution = peer.get(AgentExecution, "exec-00")
                    execution.tenant_id = OTHER
                    execution.workspace_id = WS_B
                elif move == "artifact":
                    artifact = peer.get(Artifact, "artifact-1")
                    artifact.tenant_id = OTHER
                    artifact.workspace_id = WS_B
                else:
                    segment = peer.get(EpisodeSegment, "seg-1")
                    segment.episode_id = "ep-history"
                peer.commit()
            return original(*args, **kwargs)

        monkeypatch.setattr(writes, "commit_graduation", wrapper)
        result = promote(client, sup)
        assert result["status"] == 409, (name, result)
        with world.Session() as db:
            assert db.get(AgentRegistry, AGENT).status == "student"
            if move == "episode":
                assert str(db.get(AgentEpisode, "ep-00").tenant_id) == OTHER
            elif move == "execution":
                assert str(db.get(AgentExecution, "exec-00").tenant_id) == OTHER
            elif move == "artifact":
                assert str(db.get(Artifact, "artifact-1").tenant_id) == OTHER
            else:
                assert db.get(EpisodeSegment, "seg-1").episode_id == "ep-history"
        monkeypatch.setattr(writes, "commit_graduation", original)


def _supervision_session(db, session_id):
    db.add(SupervisionSession(
        id=session_id, tenant_id=COMPANY, workspace_id=WS_A,
        agent_id=AGENT, agent_name="Scratch Student",
        supervisor_id=SUPERVISOR, trigger_context={}, status="running",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        intervention_count=0,
    ))


def test_supervision_completion_requires_qualification(tmp_path, monkeypatch):
    async def no_secondary_feedback(*args, **kwargs):
        return None

    monkeypatch.setattr(
        SupervisionService, "_process_supervision_feedback",
        no_secondary_feedback)
    world = World(tmp_path)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        agent.status = "supervised"
        agent.confidence_score = 0.95
        _supervision_session(db, "sup-1")
        db.commit()
    with world.Session() as db:
        blocked = asyncio.run(
            SupervisionService(db).complete_supervision(
                "sup-1", 5, "reviewed", actor_id=SUPERVISOR))
    assert blocked.promoted is False
    assert blocked.promotion["assessment"]["state"] == "unresolved_missing"
    with world.Session() as db:
        assert db.get(AgentRegistry, AGENT).status == "supervised"
        assert db.query(func.count(GraduationExam.id)).scalar() == 0

    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        agent.status = "supervised"
        agent.confidence_score = 0.95
        _supervision_session(db, "sup-2")
        db.commit()
    qualify(world, target="AUTONOMOUS")
    with world.Session() as db:
        allowed = asyncio.run(
            SupervisionService(db).complete_supervision(
                "sup-2", 5, "reviewed", actor_id=SUPERVISOR))
    assert allowed.promoted is True
    with world.Session() as db:
        assert db.get(AgentRegistry, AGENT).status == "autonomous"


def test_existing_system_student_is_not_healed_even_with_flag(world):
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        agent.name = "Chat Assistant"
        agent.category = "system"
        agent.status = "student"
        agent.is_system_agent = False
        db.commit()
        AgentContextResolver(db)._get_or_create_system_default()
        assert db.get(AgentRegistry, AGENT).status == "student"

    # The dedicated server flag is provenance, not an exemption: a flagged
    # existing STUDENT row (including a revoked/legacy one) stays STUDENT.
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        agent.is_system_agent = True
        db.commit()
        AgentContextResolver(db)._get_or_create_system_default()
        assert db.get(AgentRegistry, AGENT).status == "student"

    # A genuinely new trusted initial system agent is born INTERN; it does
    # not heal an existing row.
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        agent.name = "Not The Default"
        db.commit()
        created = AgentContextResolver(db)._get_or_create_system_default()
        assert created is not None
        assert created.name == "Chat Assistant"
        assert created.status == "intern"
        assert created.is_system_agent is True
        # A later revocation of the new system agent is not silently waived.
        created.status = "student"
        db.commit()
        AgentContextResolver(db)._get_or_create_system_default()
        assert db.get(AgentRegistry, created.id).status == "student"


def test_supervision_entry_preserves_caller_work(tmp_path, monkeypatch):
    async def no_secondary_feedback(*args, **kwargs):
        return None

    monkeypatch.setattr(
        SupervisionService, "_process_supervision_feedback",
        no_secondary_feedback)
    for kind in ("dirty", "new", "deleted", "flushed"):
        case_dir = tmp_path / kind
        case_dir.mkdir(parents=True, exist_ok=True)
        world = World(case_dir)
        with world.Session() as db:
            agent = db.get(AgentRegistry, AGENT)
            agent.status = "supervised"
            agent.confidence_score = 0.95
            _supervision_session(db, f"sup-{kind}")
            db.commit()
        with world.Session() as db:
            if kind == "dirty":
                pending = db.get(User, MEMBER)
                pending.first_name = "caller-dirty"
            elif kind == "new":
                pending = AgentRegistry(
                    id=f"caller-new-{uuid.uuid4().hex[:6]}",
                    name="Caller New", category="test", role="agent",
                    type="personal", capabilities=[], module_path="test",
                    class_name="Test", tenant_id=COMPANY, workspace_id=WS_A,
                    status="student", enabled=True,
                )
                db.add(pending)
            else:
                pending = db.get(User, MEMBER)
                if kind == "deleted":
                    db.delete(pending)
                else:
                    pending.first_name = "caller-flushed"
            if kind == "flushed":
                # Model already-flushed caller work: Session.dirty is empty,
                # but the transaction still holds the caller's write.
                db.flush()
            with pytest.raises(SupervisionDirtyCallerWorkError):
                asyncio.run(
                    SupervisionService(db).complete_supervision(
                        f"sup-{kind}", 5, "reviewed", actor_id=SUPERVISOR))
            with world.Session() as peer:
                if kind in ("dirty", "flushed"):
                    assert peer.get(User, MEMBER).first_name != "caller-dirty"
                    assert peer.get(User, MEMBER).first_name != "caller-flushed"
                elif kind == "new":
                    assert peer.get(AgentRegistry, pending.id) is None
                else:
                    assert peer.get(User, MEMBER) is not None
                assert peer.get(AgentRegistry, AGENT).status == "supervised"
            db.rollback()



def test_enabled_exception_requires_nonblank_owner_reason(world, monkeypatch):
    policy = _legacy_policy(True)
    policy["exceptions"]["legacy"].pop("reason", None)
    monkeypatch.setenv(ASSESSMENT_POLICY_KEY, json.dumps(policy))
    with world.Session() as db:
        with pytest.raises(AssessmentPolicyError) as exc:
            get_assessment_policy(db)
        assert exc.value.state == "configuration_required"
    assert promote(world.client(), world.token(SUPERVISOR))["status"] == 409

    policy = _legacy_policy(True)
    policy["exceptions"]["legacy"]["reason"] = "   "
    monkeypatch.setenv(ASSESSMENT_POLICY_KEY, json.dumps(policy))
    with world.Session() as db:
        with pytest.raises(AssessmentPolicyError):
            get_assessment_policy(db)


def test_blank_policy_identity_and_rubric_are_invalid(world, monkeypatch):
    for mutate in (
        lambda p: p.__setitem__("revision", "   "),
        lambda p: p.__setitem__("rubric_version", "   "),
        lambda p: p.__setitem__("source_revision", "   "),
        lambda p: p["rubric_criteria"][0].__setitem__("id", "   "),
        lambda p: p["rubric_criteria"][0].__setitem__("label", "   "),
    ):
        policy = _legacy_policy(False)
        mutate(policy)
        monkeypatch.setenv(ASSESSMENT_POLICY_KEY, json.dumps(policy))
        with world.Session() as db:
            with pytest.raises(AssessmentPolicyError) as exc:
                get_assessment_policy(db)
            assert exc.value.state == "configuration_required"
