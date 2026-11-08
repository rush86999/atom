"""Scope and non-empty-result contract; controlled transport, not model qualification."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import core.agent_graduation_service as graduation
import core.incident_eval_runner as incident_evals
import core.sandbox_executor as sandbox
from core.models import AgentEpisode
from tests.test_graduation_readiness_tenant_scoping import (
    db_session, make_agent, make_client, make_user,
)


@pytest.fixture
def controlled_exam(monkeypatch):
    monkeypatch.setattr(graduation, "get_lancedb_handler", lambda: None)
    monkeypatch.setattr(graduation, "POMDP_AVAILABLE", False)
    executor = SimpleNamespace(execute_in_sandbox=AsyncMock(return_value=SimpleNamespace(
        passed=True, interventions=0, safety_violations=[], replayed_actions=1)))
    evaluations = AsyncMock(return_value={"ran": 0, "passed": 0, "failed": 0, "skipped": 0})
    monkeypatch.setattr(sandbox, "get_sandbox_executor", lambda db: executor)
    monkeypatch.setattr(incident_evals, "run_evals", evaluations)
    return executor.execute_in_sandbox, evaluations


def _case(db, owner, name, workspace):
    db.add(AgentEpisode(
        id=name, agent_id=owner.id, tenant_id=owner.tenant_id, workspace_id=workspace,
        task_description=name, status="completed", outcome="success", success=True,
        human_intervention_count=0, maturity_at_time="intern", constitutional_score=1.0,
        started_at=datetime.now(timezone.utc), metadata_json={}))
    db.commit()


@pytest.mark.parametrize("scenario", [
    "foreign_target", "foreign_tenant", "foreign_episode", "missing_episode",
    "mixed_scope", "unknown_agent", "empty", "valid",
])
def test_public_exam_preflights_scope_and_cannot_pass_no_results(db_session, controlled_exam, scenario):
    executor, evaluations = controlled_exam
    user = make_user(db_session, "reviewer", "company", "ws-a")
    target = make_agent(db_session, "other" if scenario == "foreign_tenant" else "company",
                        workspace_id="ws-b" if scenario == "foreign_target" else "ws-a")
    own_owner = make_agent(db_session, "company", workspace_id="ws-a")
    foreign_owner = make_agent(db_session, "company", workspace_id="ws-b")
    _case(db_session, own_owner, "authorized-case", "ws-a")
    _case(db_session, foreign_owner, "peer-case", "ws-b")
    ids = ["authorized-case"]
    if scenario == "foreign_episode": ids = ["peer-case"]
    if scenario == "missing_episode": ids = ["absent-case"]
    if scenario == "mixed_scope": ids = ["authorized-case", "peer-case"]
    if scenario == "empty": ids = []
    target_id = "absent-agent" if scenario == "unknown_agent" else target.id
    response = make_client(db_session, user).post(
        "/api/episodes/graduation/exam", params={"agent_id": target_id}, json=ids)
    observed = {"status": response.status_code, "body": response.json(),
                "executor_calls": executor.await_count, "eval_calls": evaluations.await_count}
    if scenario not in {"empty", "valid"}:
        assert response.status_code == 404, observed
        assert executor.await_count == evaluations.await_count == 0, observed
    elif scenario == "empty":
        assert response.status_code == 200, observed
        assert response.json()["passed"] is False, observed
        assert executor.await_count == 0
    else:
        assert response.status_code == 200, observed
        assert response.json()["passed"] is True, observed
        executor.assert_awaited_once_with(episode_id="authorized-case", strict_mode=True)
        assert evaluations.await_args.kwargs["tenant_id"] == "company"


@pytest.mark.parametrize("moved", ["episode", "target"])
def test_exam_rechecks_scope_after_an_awaited_case(db_session, controlled_exam, moved):
    from sqlalchemy import update
    from core.models import AgentRegistry
    executor, evaluations = controlled_exam
    user = make_user(db_session, "reviewer", "company", "ws-a")
    agent = make_agent(db_session, "company", workspace_id="ws-a")
    _case(db_session, agent, "first-case", "ws-a")
    _case(db_session, agent, "later-case", "ws-a")

    async def move_after_first(**kwargs):
        if kwargs["episode_id"] == "first-case":
            model = AgentEpisode if moved == "episode" else AgentRegistry
            record_id = "later-case" if moved == "episode" else agent.id
            db_session.execute(update(model).where(model.id == record_id).values(workspace_id="ws-b")
                               .execution_options(synchronize_session=False))
            db_session.commit()
        return SimpleNamespace(passed=True, interventions=0, safety_violations=[], replayed_actions=1)

    executor.side_effect = move_after_first
    response = make_client(db_session, user).post(
        "/api/episodes/graduation/exam", params={"agent_id": agent.id},
        json=["first-case", "later-case"])
    assert response.status_code == 404, response.json()
    assert executor.await_count == 1
    assert evaluations.await_count == 0
    model = AgentEpisode if moved == "episode" else AgentRegistry
    record_id = "later-case" if moved == "episode" else agent.id
    db_session.expire_all()
    assert db_session.get(model, record_id).workspace_id == "ws-b"


def test_exam_allows_real_installation_only_review_without_claiming_candidate_quality(db_session, controlled_exam):
    executor, evaluations = controlled_exam
    user = make_user(db_session, "reviewer", "company", "ws-a")
    agent = make_agent(db_session, "company", workspace_id="ws-a")
    evaluations.return_value = {"ran": 2, "passed": 2, "failed": 0, "skipped": 0}
    response = make_client(db_session, user).post(
        "/api/episodes/graduation/exam", params={"agent_id": agent.id}, json=[])
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert data["total_cases"] == len(data["results"]) == 1
    assert data["assessment_scope"] == "historical_trace_safety_review"
    assert data["candidate_capability_qualified"] is False
    assert executor.await_count == 0
    evaluations.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_refusal_never_passes_even_after_one_successful_review(db_session, controlled_exam):
    from sqlalchemy import update
    executor, evaluations = controlled_exam
    agent = make_agent(db_session, "company", workspace_id="ws-a")
    _case(db_session, agent, "review-first", "ws-a")
    _case(db_session, agent, "moved-later", "ws-a")

    async def move_later(**kwargs):
        db_session.execute(AgentEpisode.__table__.update().where(AgentEpisode.id == "moved-later")
                           .values(workspace_id="ws-b"))
        db_session.commit()
        return SimpleNamespace(passed=True, interventions=0, safety_violations=[], replayed_actions=1)

    executor.side_effect = move_later
    result = await graduation.AgentGraduationService(db_session).run_graduation_exam(
        agent.id, ["review-first", "moved-later"], tenant_id="company", workspace_id="ws-a")
    assert result.get("error"), result
    assert result["passed"] is False, result
    assert len(result["results"]) == 1
    assert executor.await_count == 1
    assert evaluations.await_count == 0
