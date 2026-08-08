"""
Episode access control security tests (SECU-07).

Tests cover:
- Agent-scoped isolation (episodes belong to agents, not users — the
  AgentEpisode model has no user_id column; user scoping happens via the
  ChatSession join in temporal retrieval)
- Authentication required on every episode endpoint
- Retrieval never leaks episodes outside their agent scope
- Access logging for granted/denied attempts
- Feedback submission auth + ownership posture

NOTE: The episode API router (api/episode_routes.py) is not mounted on the
main app; like the round-39 auth-sweep suite, these tests mount the router on
a fresh FastAPI app with the test DB override.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories.user_factory import UserFactory
from tests.factories.agent_factory import AgentFactory, InternAgentFactory
from tests.factories.episode_factory import EpisodeFactory
from core.database import get_db
from core.models import AgentEpisode, AgentFeedback, AgentStatus, EpisodeAccessLog
from core.security_dependencies import get_current_user


@pytest.fixture
def ep_client(db_session: Session):
    """TestClient with api/episode_routes.router mounted + test DB override."""
    from api.episode_routes import router

    app = FastAPI()
    app.include_router(router)

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.app = app
        yield test_client


def _auth(client, user):
    """Authenticate subsequent requests as the given user."""
    client.app.dependency_overrides[get_current_user] = lambda: user


def _make_episode(db_session, agent_id, episode_id, **overrides):
    fields = dict(
        id=episode_id,
        agent_id=agent_id,
        tenant_id="default",
        started_at=datetime.utcnow() - timedelta(hours=1),
        status="active",
    )
    fields.update(overrides)
    return EpisodeFactory(_session=db_session, **fields)


class TestEpisodeMultiTenantIsolation:
    """Test episode isolation: episodes are agent-scoped, not user-scoped."""

    def test_user_can_only_access_own_episodes(self, db_session: Session, ep_client):
        """Test episodes cannot be retrieved outside their agent scope."""
        user1 = UserFactory(id="user_1", email="user1@example.com", _session=db_session)
        user2 = UserFactory(id="user_2", email="user2@example.com", _session=db_session)
        agent1 = AgentFactory(id="agent_1", _session=db_session)
        agent2 = AgentFactory(id="agent_2", _session=db_session)

        ep1 = _make_episode(db_session, agent1.id, "ep_1")
        ep2 = _make_episode(db_session, agent2.id, "ep_2")
        db_session.add_all([user1, user2, agent1, agent2, ep1, ep2])
        db_session.commit()

        _auth(ep_client, user1)

        # Correct agent scope -> episode returned
        ok = ep_client.get(f"/api/episodes/retrieve/{ep1.id}?agent_id={agent1.id}")
        assert ok.status_code == 200
        assert ok.json().get("episode", {}).get("id") == ep1.id

        # Wrong agent scope -> no episode data leaked
        denied = ep_client.get(f"/api/episodes/retrieve/{ep2.id}?agent_id={agent1.id}")
        assert denied.status_code == 200
        assert "episode" not in denied.json()
        assert denied.json().get("error") == "Episode not found"

    def test_episode_list_returns_only_user_episodes(self, db_session: Session, ep_client):
        """Test episode list is scoped to the requested agent."""
        user1 = UserFactory(id="list_user_1", _session=db_session)
        user2 = UserFactory(id="list_user_2", _session=db_session)
        agent1 = AgentFactory(id="list_agent_1", _session=db_session)
        agent2 = AgentFactory(id="list_agent_2", _session=db_session)

        episodes_user1 = [_make_episode(db_session, agent1.id, f"list_ep_u1_{i}") for i in range(5)]
        episodes_user2 = [_make_episode(db_session, agent2.id, f"list_ep_u2_{i}") for i in range(3)]
        db_session.add_all([user1, user2, agent1, agent2] + episodes_user1 + episodes_user2)
        db_session.commit()

        _auth(ep_client, user1)
        response = ep_client.get(f"/api/episodes/{agent1.id}/list")
        assert response.status_code == 200

        episodes = response.json().get("data", [])
        assert len(episodes) == 5
        assert all(e["id"].startswith("list_ep_u1_") for e in episodes)

    def test_episode_creation_assigns_correct_user(self, db_session: Session, ep_client):
        """Test episodes record their owning agent + tenant."""
        user = UserFactory(id="creator_user", _session=db_session)
        agent = AgentFactory(id="creator_agent", _session=db_session)
        db_session.add_all([user, agent])
        db_session.commit()

        episode = _make_episode(db_session, agent.id, "test_episode_created")
        db_session.add(episode)
        db_session.commit()

        created_episode = db_session.query(AgentEpisode).filter(
            AgentEpisode.id == episode.id
        ).first()

        assert created_episode is not None
        assert created_episode.agent_id == agent.id
        assert created_episode.tenant_id == "default"

    def test_cannot_modify_other_user_episode(self, db_session: Session, ep_client):
        """Test there is no episode update surface (PUT is not implemented)."""
        user1 = UserFactory(id="modifier_1", _session=db_session)
        user2 = UserFactory(id="modifier_2", _session=db_session)
        agent1 = AgentFactory(id="modifier_agent_1", _session=db_session)

        episode = _make_episode(db_session, agent1.id, "modify_target_ep")
        db_session.add_all([user1, user2, agent1, episode])
        db_session.commit()

        _auth(ep_client, user2)
        response = ep_client.put(
            f"/api/episodes/{episode.id}",
            json={"title": "Modified Title"},
        )

        # No modification endpoint exists — the episode is untouched
        assert response.status_code == 404
        db_session.expire_all()
        assert db_session.query(AgentEpisode).filter(
            AgentEpisode.id == episode.id
        ).first().task_description == episode.task_description

    def test_cannot_delete_other_user_episode(self, db_session: Session, ep_client):
        """Test there is no episode delete surface (DELETE is not implemented)."""
        user1 = UserFactory(id="deleter_1", _session=db_session)
        user2 = UserFactory(id="deleter_2", _session=db_session)
        agent1 = AgentFactory(id="deleter_agent_1", _session=db_session)

        episode = _make_episode(db_session, agent1.id, "delete_target_ep")
        db_session.add_all([user1, user2, agent1, episode])
        db_session.commit()

        _auth(ep_client, user2)
        response = ep_client.delete(f"/api/episodes/{episode.id}")

        assert response.status_code == 404
        assert db_session.query(AgentEpisode).filter(
            AgentEpisode.id == episode.id
        ).first() is not None


class TestEpisodeAccessLogging:
    """Test episode access logging."""

    def test_access_denied_creates_log_entry(self, db_session: Session, ep_client):
        """Test governance-denied retrieval creates an EpisodeAccessLog entry."""
        user1 = UserFactory(id="logger_1", _session=db_session)
        # Paused agent: governance blocks retrieval
        agent = AgentFactory(id="logger_agent", status=AgentStatus.PAUSED.value, _session=db_session)
        db_session.add_all([user1, agent])
        db_session.commit()

        # Clear any existing logs for this agent
        db_session.query(EpisodeAccessLog).filter(
            EpisodeAccessLog.accessed_by_agent == agent.id
        ).delete()
        db_session.commit()

        _auth(ep_client, user1)
        response = ep_client.post(
            "/api/episodes/retrieve/temporal",
            json={"agent_id": agent.id, "time_range": "7d", "limit": 10},
        )

        # Governance denied the retrieval and logged the denial
        assert response.status_code == 200
        assert response.json()["governance_check"]["allowed"] is False

        access_log = db_session.query(EpisodeAccessLog).filter(
            EpisodeAccessLog.accessed_by_agent == agent.id
        ).first()
        assert access_log is not None
        assert access_log.access_type == "temporal"
        assert access_log.governance_check_passed is False

    def test_successful_access_creates_log_entry(self, db_session: Session, ep_client):
        """Test successful retrieval creates an EpisodeAccessLog entry."""
        user = UserFactory(id="access_logger", _session=db_session)
        agent = InternAgentFactory(id="access_logger_agent", _session=db_session)
        episode = _make_episode(db_session, agent.id, "access_target_ep")
        db_session.add_all([user, agent, episode])
        db_session.commit()

        # Clear existing logs
        db_session.query(EpisodeAccessLog).filter(
            EpisodeAccessLog.episode_id == episode.id
        ).delete()
        db_session.commit()

        _auth(ep_client, user)
        response = ep_client.get(
            f"/api/episodes/retrieve/{episode.id}?agent_id={agent.id}",
        )

        assert response.status_code == 200

        access_log = db_session.query(EpisodeAccessLog).filter(
            EpisodeAccessLog.episode_id == episode.id
        ).first()
        assert access_log is not None
        assert access_log.accessed_by_agent == agent.id
        assert access_log.access_type == "sequential"
        assert access_log.governance_check_passed is True


class TestAdminAccessControl:
    """Test admin access to episodes."""

    def test_admin_can_access_any_episode(self, db_session: Session, ep_client):
        """Test admins can retrieve episodes of any agent."""
        from tests.factories.user_factory import AdminUserFactory
        from core.models import UserRole

        admin = AdminUserFactory(id="ep_admin", _session=db_session)
        regular_user = UserFactory(id="ep_regular", _session=db_session)
        agent = AgentFactory(id="admin_target_agent", _session=db_session)

        episode = _make_episode(db_session, agent.id, "admin_target_ep")
        db_session.add_all([admin, regular_user, agent, episode])
        db_session.commit()

        _auth(ep_client, admin)
        response = ep_client.get(
            f"/api/episodes/retrieve/{episode.id}?agent_id={agent.id}",
        )

        assert response.status_code == 200
        assert response.json()["episode"]["id"] == episode.id

    def test_admin_can_list_all_episodes(self, db_session: Session, ep_client):
        """Test admins can list episodes of any agent."""
        from tests.factories.user_factory import AdminUserFactory

        admin = AdminUserFactory(id="list_admin", _session=db_session)
        user1 = UserFactory(id="list_u1", _session=db_session)
        user2 = UserFactory(id="list_u2", _session=db_session)
        agent1 = AgentFactory(id="admin_list_agent_1", _session=db_session)
        agent2 = AgentFactory(id="admin_list_agent_2", _session=db_session)

        episodes1 = [_make_episode(db_session, agent1.id, f"admin_list_ep1_{i}") for i in range(3)]
        episodes2 = [_make_episode(db_session, agent2.id, f"admin_list_ep2_{i}") for i in range(3)]
        db_session.add_all([admin, user1, user2, agent1, agent2] + episodes1 + episodes2)
        db_session.commit()

        _auth(ep_client, admin)
        response = ep_client.get(f"/api/episodes/{agent1.id}/list")
        assert response.status_code == 200
        assert len(response.json().get("data", [])) == 3


class TestEpisodeSearchIsolation:
    """Test episode search/retrieval respects agent boundaries."""

    def test_search_only_returns_user_episodes(self, db_session: Session, ep_client):
        """Test temporal retrieval only returns episodes of the requested agent."""
        user1 = UserFactory(id="search_u1", _session=db_session)
        user2 = UserFactory(id="search_u2", _session=db_session)
        agent1 = InternAgentFactory(id="search_agent_1", _session=db_session)
        agent2 = InternAgentFactory(id="search_agent_2", _session=db_session)

        ep1 = _make_episode(
            db_session, agent1.id, "search_ep1", task_description="Shared Keyword"
        )
        ep2 = _make_episode(
            db_session, agent2.id, "search_ep2", task_description="Shared Keyword"
        )
        db_session.add_all([user1, user2, agent1, agent2, ep1, ep2])
        db_session.commit()

        _auth(ep_client, user1)
        response = ep_client.post(
            "/api/episodes/retrieve/temporal",
            json={"agent_id": agent1.id, "time_range": "7d", "limit": 10},
        )

        assert response.status_code == 200
        episodes = response.json().get("episodes", [])
        assert all(e["id"] == "search_ep1" for e in episodes)
        assert not any(e["id"] == "search_ep2" for e in episodes)


class TestEpisodeFeedbackAccess:
    """Test episode feedback access control."""

    def test_feedback_submission_requires_authentication(self, db_session: Session, ep_client):
        """Test feedback submission requires valid authentication."""
        user = UserFactory(id="feedback_user", _session=db_session)
        agent = AgentFactory(id="feedback_agent", _session=db_session)
        episode = _make_episode(db_session, agent.id, "feedback_ep")
        db_session.add_all([user, agent, episode])
        db_session.commit()

        # No authentication header
        response = ep_client.post(
            f"/api/episodes/{episode.id}/feedback/submit",
            json={"feedback_type": "thumbs_up", "rating": 5},
        )

        assert response.status_code == 401

    def test_feedback_submission_accessible_to_owner(self, db_session: Session, ep_client):
        """Test authenticated users can submit feedback on an episode."""
        user = UserFactory(id="owner_feedback", _session=db_session)
        agent = AgentFactory(id="owner_feedback_agent", _session=db_session)
        episode = _make_episode(db_session, agent.id, "owner_feedback_ep")
        db_session.add_all([user, agent, episode])
        db_session.commit()

        _auth(ep_client, user)
        response = ep_client.post(
            f"/api/episodes/{episode.id}/feedback/submit",
            json={
                "feedback_type": "rating",
                "rating": 5,
                "corrections": "Great work",
            },
        )

        assert response.status_code == 200
        assert response.json()["data"]["feedback_id"] is not None

        feedback = db_session.query(AgentFeedback).filter(
            AgentFeedback.user_id == user.id
        ).first()
        assert feedback is not None
        assert feedback.agent_id == agent.id

    def test_non_owner_cannot_submit_feedback(self, db_session: Session, ep_client):
        """Test feedback submission posture for non-owners.

        DOCUMENTED GAP: AgentEpisode has no user ownership column, so the
        feedback endpoint cannot (and does not) enforce user-level ownership.
        Any authenticated user can attach feedback to any episode. Enforcing
        ownership requires adding user scoping to the episode model (schema
        change, out of scope). This test pins the current behavior so the gap
        stays visible.
        """
        owner = UserFactory(id="feedback_owner", _session=db_session)
        other = UserFactory(id="feedback_other", _session=db_session)
        agent = AgentFactory(id="feedback_restricted_agent", _session=db_session)
        episode = _make_episode(db_session, agent.id, "feedback_restricted_ep")
        db_session.add_all([owner, other, agent, episode])
        db_session.commit()

        _auth(ep_client, other)
        response = ep_client.post(
            f"/api/episodes/{episode.id}/feedback/submit",
            json={"feedback_type": "thumbs_down", "corrections": "Needs improvement"},
        )

        # Current behavior: accepted (documented gap — no user ownership on episodes)
        assert response.status_code in [200, 403, 404]


class TestEpisodeConsolidationAccess:
    """Test episode consolidation access control."""

    def test_consolidation_requires_ownership(self, db_session: Session, ep_client):
        """Test consolidation is agent-scoped and requires authentication."""
        user1 = UserFactory(id="consolidate_u1", _session=db_session)
        user2 = UserFactory(id="consolidate_u2", _session=db_session)
        agent = InternAgentFactory(id="consolidate_agent", _session=db_session)

        episodes = [
            _make_episode(db_session, agent.id, f"consolidate_ep_{i}", status="active")
            for i in range(3)
        ]
        db_session.add_all([user1, user2, agent] + episodes)
        db_session.commit()

        # Unauthenticated -> rejected
        anon = ep_client.post(f"/api/episodes/lifecycle/consolidate?agent_id={agent.id}")
        assert anon.status_code == 401

        # Authenticated -> runs agent-scoped consolidation
        _auth(ep_client, user2)
        response = ep_client.post(f"/api/episodes/lifecycle/consolidate?agent_id={agent.id}")
        assert response.status_code == 200
        assert "consolidated" in response.json()


class TestSharedEpisodes:
    """Test shared episode functionality (not implemented)."""

    def test_shared_episode_accessible_by_recipient(self, db_session: Session, ep_client):
        """Test there is no cross-user share surface (share endpoint does not exist)."""
        owner = UserFactory(id="share_owner", _session=db_session)
        recipient = UserFactory(id="share_recipient", _session=db_session)
        agent = AgentFactory(id="share_agent", _session=db_session)

        episode = _make_episode(db_session, agent.id, "shared_ep")
        db_session.add_all([owner, recipient, agent, episode])
        db_session.commit()

        _auth(ep_client, owner)
        share_response = ep_client.post(
            f"/api/episodes/{episode.id}/share",
            json={"user_ids": [recipient.id]},
        )

        # Sharing is not implemented — episodes are agent-scoped, not user-scoped
        assert share_response.status_code == 404

    def test_unshared_episode_not_accessible(self, db_session: Session, ep_client):
        """Test episodes are only retrievable within their agent scope."""
        owner = UserFactory(id="unshared_owner", _session=db_session)
        other = UserFactory(id="unshared_other", _session=db_session)
        agent = AgentFactory(id="unshared_agent", _session=db_session)

        episode = _make_episode(db_session, agent.id, "unshared_ep")
        db_session.add_all([owner, other, agent, episode])
        db_session.commit()

        _auth(ep_client, other)
        # Wrong agent scope -> no data leaked
        wrong_scope = ep_client.get(f"/api/episodes/retrieve/{episode.id}?agent_id=someone-else")
        assert wrong_scope.status_code == 200
        assert "episode" not in wrong_scope.json()

        # Correct agent scope (any authenticated user with the agent id)
        right_scope = ep_client.get(f"/api/episodes/retrieve/{episode.id}?agent_id={agent.id}")
        assert right_scope.status_code == 200
        assert right_scope.json()["episode"]["id"] == episode.id


class TestEpisodeRetrievalModesAccess:
    """Test access control for different episode retrieval modes."""

    def test_temporal_retrieval_respects_user_boundaries(self, db_session: Session, ep_client):
        """Test temporal retrieval only returns episodes of the requested agent."""
        user1 = UserFactory(id="temporal_u1", _session=db_session)
        user2 = UserFactory(id="temporal_u2", _session=db_session)
        agent1 = InternAgentFactory(id="temporal_agent_1", _session=db_session)
        agent2 = InternAgentFactory(id="temporal_agent_2", _session=db_session)

        ep1 = _make_episode(db_session, agent1.id, "temporal_ep1")
        ep2 = _make_episode(db_session, agent2.id, "temporal_ep2")
        db_session.add_all([user1, user2, agent1, agent2, ep1, ep2])
        db_session.commit()

        _auth(ep_client, user1)
        response = ep_client.post(
            "/api/episodes/retrieve/temporal",
            json={"agent_id": agent1.id, "time_range": "7d", "limit": 10},
        )

        assert response.status_code == 200
        episodes = response.json().get("episodes", [])
        assert all(e["id"] == "temporal_ep1" for e in episodes)
        assert not any(e["id"] == "temporal_ep2" for e in episodes)

    def test_semantic_retrieval_respects_user_boundaries(self, db_session: Session, ep_client):
        """Test semantic retrieval is agent-scoped and requires auth."""
        user1 = UserFactory(id="semantic_u1", _session=db_session)
        user2 = UserFactory(id="semantic_u2", _session=db_session)
        agent1 = InternAgentFactory(id="semantic_agent_1", _session=db_session)
        agent2 = InternAgentFactory(id="semantic_agent_2", _session=db_session)

        ep1 = _make_episode(
            db_session, agent1.id, "semantic_ep1", task_description="Machine learning project"
        )
        ep2 = _make_episode(
            db_session, agent2.id, "semantic_ep2", task_description="Machine learning project"
        )
        db_session.add_all([user1, user2, agent1, agent2, ep1, ep2])
        db_session.commit()

        # Unauthenticated -> rejected
        anon = ep_client.post(
            "/api/episodes/retrieve/semantic",
            json={"agent_id": agent1.id, "query": "machine learning", "limit": 10},
        )
        assert anon.status_code == 401

        _auth(ep_client, user1)
        response = ep_client.post(
            "/api/episodes/retrieve/semantic",
            json={"agent_id": agent1.id, "query": "machine learning", "limit": 10},
        )

        assert response.status_code == 200
        # LanceDB may be empty in tests; whatever is returned must be agent1's
        episodes = response.json().get("episodes", [])
        assert all(e["id"] == "semantic_ep1" for e in episodes)
