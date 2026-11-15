"""GOAL-6 positive twin: ordinary creation -> synthetic review -> promotion.

Reuses the existing real scratch test harness (FastAPI TestClient + JWT +
real qualification review/approval/receipt routes). The created agent is made
through POST /api/agents/custom; evidence is controlled synthetic scratch
data; no model/network/owner data. The denied twins remain explicit.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from core.models import (
    AgentEpisode, AgentExecution, AgentProposal, AgentRegistry, Artifact,
    EpisodeSegment, GraduationExam, HITLAction, PromotionHistory,
    TrainingSession,
)
from tests.api.test_graduation_qualification_join import (
    ADMIN, COMPANY, SUPERVISOR, WS_A, World, approve, call,
)


def create_agent(client, admin_token):
    body = {
        "name": f"Goal6 ordinary {uuid.uuid4().hex[:8]}",
        "category": "research",
        "description": "Created through the public custom route",
    }
    return call(client, "POST",
                f"/api/agents/custom?operation_id=goal6-create-{uuid.uuid4().hex}",
                admin_token, json=body)


def add_evidence(world, agent_id):
    started = datetime.now(timezone.utc) - timedelta(days=2)
    with world.Session() as db:
        for i in range(10):
            db.add(AgentExecution(
                id=f"goal6-exec-{agent_id[:8]}-{i:02d}", agent_id=agent_id,
                tenant_id=COMPANY, workspace_id=WS_A, status="completed",
                input_summary=f"held-out goal6 task {i}",
                result_summary=f"actual goal6 output {i}",
                completed_at=started + timedelta(minutes=i + 5)))
            db.add(AgentEpisode(
                id=f"goal6-ep-{agent_id[:8]}-{i:02d}", agent_id=agent_id,
                tenant_id=COMPANY, workspace_id=WS_A,
                execution_id=f"goal6-exec-{agent_id[:8]}-{i:02d}",
                task_description=f"held-out goal6 work {i}",
                maturity_at_time="student", constitutional_score=0.9,
                human_intervention_count=0, confidence_score=0.62,
                outcome="success", success=True, status="completed",
                started_at=started + timedelta(minutes=i),
                completed_at=started + timedelta(minutes=i + 5)))
        db.add(Artifact(
            id=f"goal6-art-{agent_id[:8]}", tenant_id=COMPANY,
            workspace_id=WS_A, agent_id=agent_id,
            name="Held-out goal6 output", type="markdown",
            content="actual goal6 artifact output", version=1))
        db.add(EpisodeSegment(
            id=f"goal6-seg-{agent_id[:8]}",
            episode_id=f"goal6-ep-{agent_id[:8]}-00",
            segment_type="execution", sequence_order=1,
            content="actual goal6 segment output"))
        db.add(AgentProposal(
            id=f"goal6-proposal-{agent_id[:8]}", tenant_id=COMPANY,
            user_id=SUPERVISOR, agent_id=agent_id, agent_name="Goal6",
            title="synthetic training", proposal_type="action",
            proposal_data={}, status="executed"))
        db.add(TrainingSession(
            id=f"goal6-session-{agent_id[:8]}", tenant_id=COMPANY,
            proposal_id=f"goal6-proposal-{agent_id[:8]}", agent_id=agent_id,
            agent_name="Goal6", status="completed", started_at=started,
            completed_at=started + timedelta(hours=1),
            supervisor_id=SUPERVISOR, tasks_completed=10, total_tasks=10,
            performance_score=1.0, confidence_boost=0.12,
            promoted_to_intern=False))
        db.commit()


def request_review(client, token_value, agent_id, evidence):
    return call(client, "POST",
                "/api/episodes/graduation/qualification/request", token_value,
                json={"agent_id": agent_id, "target_maturity": "INTERN",
                      "evidence_refs": evidence,
                      "rubric_version": "heldout-v1"})


def promote(client, token_value, agent_id, target="INTERN"):
    return call(client, "POST",
                f"/api/episodes/graduation/promote?agent_id={agent_id}"
                f"&new_maturity={target}&operation_id=goal6-promote-{uuid.uuid4().hex}",
                token_value)


def test_ordinary_creation_positive_qualification_and_promotion(tmp_path):
    world = World(tmp_path, episodes=0)
    client = world.client()
    admin = world.token(ADMIN)
    sup = world.token(SUPERVISOR)

    created = create_agent(client, admin)
    assert created["status"] == 201, created
    agent_id = created["json"]["data"]["agent_id"]
    assert created["json"]["data"]["agent_status"] == "student"
    add_evidence(world, agent_id)

    requested = request_review(client, sup, agent_id, [
        {"kind": "agent_episode", "id": f"goal6-ep-{agent_id[:8]}-00"},
        {"kind": "agent_execution", "id": f"goal6-exec-{agent_id[:8]}-00"},
    ])
    assert requested["status"] == 200, requested
    action_id = requested["json"]["data"]["action_id"]
    assert approve(client, admin, action_id)["status"] == 200

    promoted = promote(client, sup, agent_id)
    assert promoted["status"] == 200, promoted
    assert promoted["json"]["data"]["promoted"] is True

    evidence_ids = {
        f"goal6-ep-{agent_id[:8]}-00", f"goal6-exec-{agent_id[:8]}-00"}
    with world.Session() as db:
        agent = db.get(AgentRegistry, agent_id)
        assert agent.status == "intern"
        history = db.query(PromotionHistory).filter(
            PromotionHistory.agent_id == agent_id).one()
        receipt = db.query(GraduationExam).filter(
            GraduationExam.agent_id == agent_id).one()
        action = db.get(HITLAction, action_id)
        meta = dict(receipt.metadata_json or {})
        refs = meta.get("evidence_refs") or []
        ref_ids = {str(r.get("id")) for r in refs if isinstance(r, dict)}
        assert receipt.id == agent.last_exam_id
        assert receipt.tenant_id == COMPANY
        assert receipt.target_level == "INTERN"
        assert receipt.passed is True
        assert meta.get("state") == "valid"
        assert meta.get("review_action_id") == action_id
        assert meta.get("reviewed_by") == ADMIN
        assert meta.get("tenant_id") == COMPANY
        assert meta.get("workspace_id") == WS_A
        assert ref_ids == evidence_ids
        assert history.exam_id == receipt.id
        assert action.status == "approved"
        assert action.reviewed_by == ADMIN
        assert action.agent_id == agent_id

    # Denied unqualified twin: second ordinary agent has the same synthetic
    # evidence, so the qualification receipt is the only missing gate.
    second = create_agent(client, admin)
    assert second["status"] == 201, second
    second_id = second["json"]["data"]["agent_id"]
    add_evidence(world, second_id)
    denied = promote(client, sup, second_id)
    assert denied["status"] == 409, denied
    assert denied["json"]["detail"]["status"] == "unresolved"
    with world.Session() as db:
        assert db.get(AgentRegistry, second_id).status == "student"
        assert db.query(PromotionHistory).filter(
            PromotionHistory.agent_id == second_id).count() == 0
        assert db.query(GraduationExam).filter(
            GraduationExam.agent_id == second_id).count() == 0

    # Foreign-scope twin: other tenant's supervisor gets exact 404; first agent
    # remains intern.
    foreign = promote(client, world.token("foreign-sup"), agent_id)
    assert foreign["status"] == 404, foreign
    with world.Session() as db:
        assert db.get(AgentRegistry, agent_id).status == "intern"


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="goal6-positive-") as td:
        test_ordinary_creation_positive_qualification_and_promotion(Path(td))
    print("GOAL6_POSITIVE_PASS")
