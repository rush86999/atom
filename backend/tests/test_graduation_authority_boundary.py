"""Awaited graduation must not spend stale authority or overwrite peer state.

Readiness/strategic decisions are controlled only to place a deterministic
interleaving. These controls do not qualify evidence quality or general autonomy.
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.agent_graduation_service as graduation
import core.governance as governance
import core.governance_cache as cache
import core.maturity_broadcast as broadcast
import core.notification_service as notifications
from core.database import Base
from core.models import AgentRegistry, Tenant, User, Workspace


@pytest.fixture
def graduation_world(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'graduation-boundary.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        db.add(Tenant(id="company", name="Company", subdomain="graduation-test"))
        db.add_all([
            Workspace(id="ws-a", name="A", tenant_id="company"),
            Workspace(id="ws-b", name="B", tenant_id="company"),
        ])
        db.add(User(
            id="supervisor", email="supervisor@example.test", first_name="Test",
            last_name="Supervisor", role="team_lead", status="active",
            is_active=True, tenant_id="company", workspace_id="ws-a"))
        db.add(AgentRegistry(
            id="graduate", name="Graduate", category="operations",
            module_path="test.agent", class_name="TestAgent", user_id="supervisor",
            tenant_id="company", workspace_id="ws-a", status="supervised",
            configuration={"accepted": "original"}, confidence_score=0.99))
        db.commit()
    monkeypatch.setattr(graduation, "get_lancedb_handler", lambda: None)
    monkeypatch.setattr(graduation, "POMDP_AVAILABLE", False)
    monkeypatch.setattr(governance.DynamicGovernanceManager, "decide",
                        lambda *a, **k: SimpleNamespace(allowed=True, reasons=[]))
    monkeypatch.setattr(cache, "get_governance_cache",
                        lambda: SimpleNamespace(invalidate_agent=lambda *a: None))
    monkeypatch.setattr(broadcast, "schedule_maturity_broadcast", lambda **k: None)
    monkeypatch.setattr(notifications, "NotificationService",
                        lambda db: SimpleNamespace(send_notification=lambda **k: None))
    monkeypatch.setattr(graduation, "get_event_loop",
                        lambda: SimpleNamespace(run_until_complete=lambda value: None))
    yield sessions
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("peer_change", [
    "target_scope", "target_status", "target_configuration", "actor_disabled",
    "actor_demoted", "actor_scope", "unchanged",
])
async def test_graduation_revalidates_after_awaited_readiness(graduation_world, peer_change):
    sessions = graduation_world
    with sessions() as caller:
        service = graduation.AgentGraduationService(caller)

        async def ready(**kwargs):
            # The service already loaded/checks its original target. A distinct
            # session now commits the peer winner during its actual await.
            with sessions() as peer:
                if peer_change == "target_scope":
                    peer.execute(update(AgentRegistry).where(AgentRegistry.id == "graduate")
                                 .values(workspace_id="ws-b"))
                elif peer_change == "target_status":
                    peer.execute(update(AgentRegistry).where(AgentRegistry.id == "graduate")
                                 .values(status="student"))
                elif peer_change == "target_configuration":
                    peer.execute(update(AgentRegistry).where(AgentRegistry.id == "graduate")
                                 .values(configuration={"accepted": "peer"}))
                elif peer_change == "actor_demoted":
                    peer.execute(update(User).where(User.id == "supervisor")
                                 .values(role="member"))
                elif peer_change == "actor_scope":
                    peer.execute(update(User).where(User.id == "supervisor")
                                 .values(workspace_id="ws-b"))
                elif peer_change == "actor_disabled":
                    peer.execute(update(User).where(User.id == "supervisor")
                                 .values(is_active=False))
                peer.commit()
            return {
                "ready": True, "gaps": [], "episodes_analyzed": 60,
                "readiness_score": 1.0, "success_rate": 1.0,
                "avg_constitutional_score": 1.0, "intervention_rate": 0.0,
                "avg_confidence_score": 0.99,
            }

        service.calculate_readiness_score = ready
        promoted = await service.promote_agent(
            "graduate", "AUTONOMOUS", "supervisor",
            tenant_id="company", workspace_id="ws-a")
    with sessions() as fresh:
        agent = fresh.get(AgentRegistry, "graduate")
        actor = fresh.get(User, "supervisor")
        assert promoted is (peer_change == "unchanged"), (
            peer_change, promoted, agent.status, agent.workspace_id, actor.is_active)
        assert agent.workspace_id == ("ws-b" if peer_change == "target_scope" else "ws-a")
        assert actor.is_active is (peer_change != "actor_disabled")
        assert agent.status == (
            "autonomous" if peer_change == "unchanged"
            else "student" if peer_change == "target_status" else "supervised")
        if peer_change != "unchanged":
            assert agent.configuration == {"accepted": (
                "peer" if peer_change == "target_configuration" else "original")}
        assert actor.role == ("member" if peer_change == "actor_demoted" else "team_lead")
        assert actor.workspace_id == ("ws-b" if peer_change == "actor_scope" else "ws-a")
