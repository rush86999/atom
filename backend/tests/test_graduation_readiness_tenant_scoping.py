"""NULL/empty-tenant agents must still get graduation readiness.

Personal Edition bootstraps some rows with tenant_id=None — the admin user
(admin_bootstrap) and agents hired before tenant scoping — and
core/personal_scope.py declares the resolver fallback to "default"
load-bearing. EpisodeService.get_graduation_readiness re-queried the agent
with a strict tenant_id == :tenant equality filter, so every readiness call
for a NULL-tenant agent raised ValueError("Agent … not found for tenant
default") → HTTP 500 → the canvas Training panel showed "Readiness
unavailable." while the Promote button stayed clickable (promote queries by
ID only) — a supervisor could graduate an agent without ever seeing the
evidence.

Live case (2026-09-22): intern "Sales Agent" (tenant_id NULL, 374 episodes
under tenant "default") 500'd /api/episodes/graduation/readiness on every
Training-panel load.

Scratch-file sqlite via tmp_path — never the live dev DB (AGENTS.md).
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from api.episode_routes import router
from core.agent_graduation_service import AgentGraduationService
from core.auth import get_current_user
from core.database import get_db
from core.episode_service import EpisodeService
from core.models import AgentEpisode, AgentRegistry, AgentStatus, User, UserRole


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/readiness_tenant_test.db",
        connect_args={"check_same_thread": False},
    )
    User.__table__.create(engine)
    AgentRegistry.__table__.create(engine)
    AgentEpisode.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


def make_agent(db, tenant_id, status=AgentStatus.INTERN.value, workspace_id=None):
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name=f"Agent {tenant_id!r}",
        category="Sales",
        module_path="sales.agent",
        class_name="SalesAgent",
        status=status,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    db.add(agent)
    db.commit()
    return agent


def make_episodes(
    db,
    agent,
    tenant_id,
    count=12,
    constitutional_score=None,
    confidence_score=0.6,
):
    base = datetime.now(timezone.utc)
    for i in range(count):
        db.add(AgentEpisode(
            agent_id=agent.id,
            tenant_id=tenant_id,
            task_description=f"Episode {i}",
            maturity_at_time=AgentStatus.INTERN.value,
            outcome="success",
            success=True,
            human_intervention_count=0,
            confidence_score=confidence_score,
            constitutional_score=constitutional_score,
            status="completed",
            metadata_json={},
            started_at=base,
        ))
    db.commit()


def make_user(db, user_id, tenant_id, workspace_id, role=UserRole.TEAM_LEAD.value):
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="Graduation",
        last_name="Supervisor",
        hashed_password="x",
        role=role,
        status="active",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    db.add(user)
    db.commit()
    return user


def make_client(db, user):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture()
def isolated_promotion(monkeypatch):
    notification_service = Mock()
    notification_service.send_notification = Mock(side_effect=RuntimeError("mocked"))
    monkeypatch.setattr(
        "core.agent_graduation_service.get_lancedb_handler",
        lambda: Mock(),
    )
    monkeypatch.setattr("core.agent_graduation_service.POMDP_AVAILABLE", False)
    monkeypatch.setattr(
        "core.governance_cache.get_governance_cache",
        lambda: Mock(),
    )
    monkeypatch.setattr(
        "core.maturity_broadcast.schedule_maturity_broadcast",
        Mock(),
    )
    monkeypatch.setattr(
        "core.notification_service.NotificationService",
        lambda _db: notification_service,
    )


class TestReadinessTenantScoping:
    def test_null_tenant_agent_resolves_for_default_tenant(self, db_session):
        """THE regression: a NULL-tenant intern with episodes under
        'default' must get a readiness response, not ValueError."""
        agent = make_agent(db_session, tenant_id=None)
        make_episodes(db_session, agent, tenant_id="default", count=12)

        readiness = EpisodeService(db_session).get_graduation_readiness(
            agent_id=agent.id,
            tenant_id="default",
            target_level=AgentStatus.SUPERVISED.value,
        )

        assert readiness.episodes_analyzed == 12
        assert readiness.current_level == AgentStatus.INTERN.value
        assert 0.0 <= readiness.readiness_score <= 1.0

    def test_empty_tenant_agent_resolves(self, db_session):
        agent = make_agent(db_session, tenant_id="")
        make_episodes(db_session, agent, tenant_id="default", count=5)

        readiness = EpisodeService(db_session).get_graduation_readiness(
            agent_id=agent.id,
            tenant_id="default",
            target_level=AgentStatus.SUPERVISED.value,
        )

        assert readiness.episodes_analyzed == 5

    def test_tenanted_agent_still_scoped_to_its_tenant(self, db_session):
        """The NULL tolerance must not open a cross-tenant hole: a
        properly-tenanted agent is invisible to another tenant."""
        agent = make_agent(db_session, tenant_id="tenant-1")
        make_episodes(db_session, agent, tenant_id="tenant-1", count=3)

        with pytest.raises(ValueError, match="not found for tenant default"):
            EpisodeService(db_session).get_graduation_readiness(
                agent_id=agent.id,
                tenant_id="default",
                target_level=AgentStatus.SUPERVISED.value,
            )

    def test_calculate_readiness_score_end_to_end_null_tenant(self, db_session):
        """The route path: AgentGraduationService.calculate_readiness_score
        for the NULL-tenant agent returns scored evidence (no "error" key),
        so the Training panel shows the readiness bar instead of falling
        back to the "Readiness unavailable." placeholder."""
        agent = make_agent(db_session, tenant_id=None)
        make_episodes(db_session, agent, tenant_id="default", count=12)

        with patch("core.agent_graduation_service.get_lancedb_handler",
                   return_value=Mock()), \
             patch("core.agent_graduation_service.POMDP_AVAILABLE", False):
            result = asyncio.run(
                AgentGraduationService(db_session).calculate_readiness_score(
                    agent_id=agent.id,
                    target_maturity="SUPERVISED",
                )
            )

        assert "error" not in result
        assert result["episode_count"] == 12
        assert result["current_maturity"] == AgentStatus.INTERN.value
        assert isinstance(result["score"], (int, float))
        # 12 episodes < SUPERVISED floor (25) must surface as an explicit
        # gap, not a silent pass — the supervisor reads these gaps.
        assert any("Insufficient episodes" in g for g in result["gaps"])

    def test_service_readiness_rejects_foreign_tenant_and_workspace(self, db_session):
        agent = make_agent(
            db_session,
            tenant_id="tenant-2",
            workspace_id="workspace-2",
        )

        with patch("core.agent_graduation_service.get_lancedb_handler", return_value=Mock()), \
             patch("core.agent_graduation_service.POMDP_AVAILABLE", False):
            service = AgentGraduationService(db_session)
            foreign_tenant = asyncio.run(service.calculate_readiness_score(
                agent_id=agent.id,
                target_maturity="INTERN",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
            ))
            foreign_workspace = asyncio.run(service.calculate_readiness_score(
                agent_id=agent.id,
                target_maturity="INTERN",
                tenant_id="tenant-2",
                workspace_id="workspace-1",
            ))

        assert foreign_tenant == {"error": "Agent not found"}
        assert foreign_workspace == {"error": "Agent not found"}


class TestGraduationApiTenantScoping:
    def test_same_tenant_readiness_is_available(self, db_session, isolated_promotion):
        user = make_user(db_session, "scope-lead", "tenant-1", "workspace-1")
        agent = make_agent(
            db_session,
            tenant_id="tenant-1",
            status=AgentStatus.STUDENT.value,
            workspace_id="workspace-1",
        )
        make_episodes(
            db_session,
            agent,
            tenant_id="tenant-1",
            count=10,
            constitutional_score=1.0,
            confidence_score=1.0,
        )

        response = make_client(db_session, user).get(
            f"/api/episodes/graduation/readiness/{agent.id}",
            params={"target_maturity": "INTERN"},
        )

        assert response.status_code == 200
        assert response.json()["ready"] is True

    def test_foreign_tenant_readiness_and_promotion_return_404(self, db_session, isolated_promotion):
        user = make_user(db_session, "scope-lead", "tenant-1", "workspace-1")
        agent = make_agent(
            db_session,
            tenant_id="tenant-2",
            status=AgentStatus.STUDENT.value,
            workspace_id="workspace-2",
        )
        client = make_client(db_session, user)

        readiness = client.get(f"/api/episodes/graduation/readiness/{agent.id}")
        promotion = client.post(
            "/api/episodes/graduation/promote",
            params={"agent_id": agent.id, "new_maturity": "INTERN"},
        )

        assert readiness.status_code == 404
        assert promotion.status_code == 404
        db_session.expire_all()
        assert db_session.get(AgentRegistry, agent.id).status == AgentStatus.STUDENT.value

    def test_null_tenant_agent_is_only_visible_to_default_tenant(
        self,
        db_session,
        isolated_promotion,
    ):
        default_user = make_user(db_session, "default-lead", None, None)
        scoped_user = make_user(db_session, "scoped-lead", "tenant-1", "workspace-1")
        agent = make_agent(
            db_session,
            tenant_id=None,
            status=AgentStatus.STUDENT.value,
            workspace_id=None,
        )
        make_episodes(
            db_session,
            agent,
            tenant_id="default",
            count=10,
            constitutional_score=1.0,
            confidence_score=1.0,
        )

        default_response = make_client(db_session, default_user).get(
            f"/api/episodes/graduation/readiness/{agent.id}"
        )
        scoped_response = make_client(db_session, scoped_user).get(
            f"/api/episodes/graduation/readiness/{agent.id}"
        )

        assert default_response.status_code == 200
        assert scoped_response.status_code == 404


class TestPromotionReadinessGate:
    @pytest.mark.parametrize(
        ("source", "target", "episode_count"),
        [
            (AgentStatus.STUDENT.value, "INTERN", 10),
            (AgentStatus.INTERN.value, "SUPERVISED", 25),
            (AgentStatus.SUPERVISED.value, "AUTONOMOUS", 50),
        ],
    )
    def test_promotion_without_evidence_is_rejected(
        self,
        db_session,
        isolated_promotion,
        source,
        target,
        episode_count,
    ):
        user = make_user(db_session, "gate-lead", "tenant-1", "workspace-1")
        agent = make_agent(
            db_session,
            tenant_id="tenant-1",
            status=source,
            workspace_id="workspace-1",
        )
        client = make_client(db_session, user)

        response = client.post(
            "/api/episodes/graduation/promote",
            params={"agent_id": agent.id, "new_maturity": target},
        )

        assert response.status_code == 200
        assert response.json()["data"]["promoted"] is False
        db_session.expire_all()
        assert db_session.get(AgentRegistry, agent.id).status == source

    @pytest.mark.parametrize(
        ("source", "target", "episode_count"),
        [
            (AgentStatus.STUDENT.value, "INTERN", 10),
            (AgentStatus.INTERN.value, "SUPERVISED", 25),
            (AgentStatus.SUPERVISED.value, "AUTONOMOUS", 50),
        ],
    )
    def test_promotion_accepts_sufficient_readiness(
        self,
        db_session,
        isolated_promotion,
        source,
        target,
        episode_count,
    ):
        user = make_user(db_session, "gate-lead", "tenant-1", "workspace-1")
        agent = make_agent(
            db_session,
            tenant_id="tenant-1",
            status=source,
            workspace_id="workspace-1",
        )
        make_episodes(
            db_session,
            agent,
            tenant_id="tenant-1",
            count=episode_count,
            constitutional_score=1.0,
            confidence_score=1.0,
        )
        client = make_client(db_session, user)

        response = client.post(
            "/api/episodes/graduation/promote",
            params={"agent_id": agent.id, "new_maturity": target},
        )

        assert response.status_code == 200
        assert response.json()["data"]["promoted"] is True
        db_session.expire_all()
        assert db_session.get(AgentRegistry, agent.id).status == target.lower()

    def test_per_agent_episode_floor_blocks_and_then_allows(
        self,
        db_session,
        isolated_promotion,
    ):
        user = make_user(db_session, "gate-lead", "tenant-1", "workspace-1")
        agent = make_agent(
            db_session,
            tenant_id="tenant-1",
            status=AgentStatus.STUDENT.value,
            workspace_id="workspace-1",
        )
        agent.promotion_episode_floor = 12
        db_session.commit()
        make_episodes(
            db_session,
            agent,
            tenant_id="tenant-1",
            count=10,
            constitutional_score=1.0,
            confidence_score=1.0,
        )
        client = make_client(db_session, user)
        params = {"agent_id": agent.id, "new_maturity": "INTERN"}

        blocked = client.post("/api/episodes/graduation/promote", params=params)
        make_episodes(
            db_session,
            agent,
            tenant_id="tenant-1",
            count=2,
            constitutional_score=1.0,
            confidence_score=1.0,
        )
        promoted = client.post("/api/episodes/graduation/promote", params=params)

        assert blocked.json()["data"]["promoted"] is False
        assert promoted.json()["data"]["promoted"] is True

    def test_unreadable_evidence_fails_closed(self, db_session, isolated_promotion):
        agent = make_agent(
            db_session,
            tenant_id="tenant-1",
            status=AgentStatus.SUPERVISED.value,
            workspace_id="workspace-1",
        )
        service = AgentGraduationService(db_session)

        with patch.object(
            service,
            "calculate_readiness_score",
            new=AsyncMock(side_effect=RuntimeError("evidence unavailable")),
        ):
            promoted = asyncio.run(service.promote_agent(
                agent_id=agent.id,
                new_maturity="AUTONOMOUS",
                validated_by="gate-lead",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
            ))

        assert promoted is False
        db_session.expire_all()
        assert db_session.get(AgentRegistry, agent.id).status == AgentStatus.SUPERVISED.value
