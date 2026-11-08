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
