"""Mounted graduation evidence routes must preserve current workspace scope."""
from datetime import datetime, timezone

import pytest

import core.agent_graduation_service as graduation
from core.models import AgentEpisode
from tests.test_graduation_readiness_tenant_scoping import (
    db_session, make_agent, make_client, make_user,
)


@pytest.fixture(autouse=True)
def no_model_initialization(monkeypatch):
    monkeypatch.setattr(graduation, "get_lancedb_handler", lambda: None)
    monkeypatch.setattr(graduation, "POMDP_AVAILABLE", False)


@pytest.mark.parametrize("foreign", ["workspace", "tenant", None])
def test_audit_route_checks_target_workspace(db_session, foreign):
    user = make_user(db_session, "reviewer", "company", "ws-a")
    agent = make_agent(db_session, "other" if foreign == "tenant" else "company",
                       workspace_id="ws-b" if foreign == "workspace" else "ws-a")
    response = make_client(db_session, user).get(f"/api/episodes/graduation/audit/{agent.id}")
    assert response.status_code == (404 if foreign else 200), response.json()
    if not foreign:
        assert response.json()["agent_id"] == agent.id


def test_audit_route_does_not_include_peer_workspace_episode(db_session):
    user = make_user(db_session, "reviewer", "company", "ws-a")
    agent = make_agent(db_session, "company", workspace_id="ws-a")
    db_session.add(AgentEpisode(
        id="foreign-evidence", agent_id=agent.id, tenant_id="company", workspace_id="ws-b",
        task_description="Peer workspace evidence", status="completed", outcome="success",
        success=True, human_intervention_count=0, maturity_at_time="intern",
        constitutional_score=1.0, started_at=datetime.now(timezone.utc), metadata_json={}))
    db_session.commit()
    response = make_client(db_session, user).get(f"/api/episodes/graduation/audit/{agent.id}")
    assert response.status_code == 200
    assert response.json()["total_episodes"] == 0, response.json()
    assert "Peer workspace evidence" not in response.text


@pytest.mark.parametrize("legacy_scope", [None, "", "default"])
def test_personal_audit_preserves_existing_default_aliases(db_session, legacy_scope):
    user = make_user(db_session, "reviewer", legacy_scope, legacy_scope)
    agent = make_agent(db_session, legacy_scope, workspace_id=legacy_scope)
    db_session.add(AgentEpisode(
        id="personal-evidence", agent_id=agent.id, tenant_id="default", workspace_id="default",
        task_description="Authorized personal evidence", status="completed", outcome="success",
        success=True, human_intervention_count=0, maturity_at_time="intern",
        constitutional_score=1.0, started_at=datetime.now(timezone.utc), metadata_json={}))
    db_session.commit()
    response = make_client(db_session, user).get(f"/api/episodes/graduation/audit/{agent.id}")
    assert response.status_code == 200, response.json()
    assert response.json()["total_episodes"] == 1
    assert "Authorized personal evidence" in response.text
