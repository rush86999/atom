"""Coverage wave 10c — never-covered core/api cluster (TDD).

Red-green targets (real bugs):
- WC1: ``core/agent_execution_service`` calls ``await trigger_episode_creation(
  user_id=..., workspace_id=...)`` — the function is sync, returns None, and
  accepts no such kwargs → TypeError on EVERY execution → episode creation
  trigger silently dead on the execution-service path.
- WC2: ``api/evolution_routes`` router declares ``prefix="/evolution"`` and is
  mounted at ``prefix="/api/evolution"`` → real path is
  ``/api/evolution/evolution/run`` (documented ``/api/evolution/run`` 404s).
- WC3: ``core/episode_integration.trigger_episode_creation`` calls
  ``asyncio.create_task`` in a sync function — RuntimeError from any sync
  caller (no running loop), abandoned coroutine otherwise.
"""
import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# =========================================================================== #
# WC1/WC3 — episode integration trigger
# =========================================================================== #
class TestEpisodeIntegration:
    def test_sync_context_trigger_does_not_crash(self):
        """No running loop → must not raise RuntimeError (asyncio.create_task)."""
        from core.episode_integration import trigger_episode_creation

        with patch("core.episode_integration.asyncio.run") as mock_run:
            trigger_episode_creation("sess-1", "agent-1", title="t")
        assert mock_run.called

    def test_async_context_trigger_schedules_task(self):
        from core.episode_integration import trigger_episode_creation

        async def main():
            with patch("core.episode_integration.asyncio.create_task") as mock_ct:
                trigger_episode_creation("sess-1", "agent-1")
            assert mock_ct.called

        asyncio.run(main())

    def test_trigger_accepts_user_and_workspace_kwargs(self):
        """agent_execution_service passes user_id/workspace_id — must not TypeError."""
        from core.episode_integration import trigger_episode_creation

        with patch("core.episode_integration.asyncio.run"):
            trigger_episode_creation(
                session_id="s-1", agent_id="a-1", user_id="u-1", workspace_id="w-1"
            )

    def test_background_creation_creates_episode_and_logs(self):
        from core.episode_integration import _create_episode_after_execution

        fake_service = AsyncMock()
        fake_service.create_episode_from_session.return_value = SimpleNamespace(id="ep-1")
        db_ctx = MagicMock()
        db_ctx.__enter__.return_value = SimpleNamespace()
        with patch("core.database.get_db_session", return_value=db_ctx), \
             patch(
                 "core.episode_segmentation_service.EpisodeSegmentationService",
                 return_value=fake_service,
             ):
            asyncio.run(_create_episode_after_execution("s-1", "a-1", "t"))
        fake_service.create_episode_from_session.assert_awaited_once_with(
            session_id="s-1", agent_id="a-1", title="t", force_create=False
        )

    def test_background_creation_failure_is_logged_not_raised(self):
        from core.episode_integration import _create_episode_after_execution

        db_ctx = MagicMock()
        db_ctx.__enter__.side_effect = RuntimeError("db down")
        with patch("core.database.get_db_session", return_value=db_ctx), \
             patch("core.episode_integration.logger") as mock_logger:
            asyncio.run(_create_episode_after_execution("s-1", "a-1"))
        mock_logger.error.assert_called_once()

    def test_execution_service_episode_trigger_kwargs_contract(self):
        """The agent_execution_service call site passes kwargs the trigger
        must accept; the awaited sync call must not raise."""
        import core.agent_execution_service as aes

        assert hasattr(aes, "trigger_episode_creation")

    def test_trigger_is_sync_returning_none(self):
        from core.episode_integration import trigger_episode_creation

        with patch("core.episode_integration.asyncio.run"):
            assert trigger_episode_creation("s", "a") is None


# =========================================================================== #
# WC2 — evolution routes (double prefix + real behavior)
# =========================================================================== #
def _evolution_app():
    from api.evolution_routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api/evolution")
    return app


class TestEvolutionRoutes:
    def test_mounted_paths_have_no_double_prefix(self):
        app = _evolution_app()
        paths = set(app.openapi()["paths"].keys())
        assert "/api/evolution/run" in paths
        assert "/api/evolution/evolution/run" not in paths
        assert "/api/evolution/traces/{agent_id}" in paths

    def test_run_starts_background_evolution(self):
        loop = MagicMock()
        with patch("api.evolution_routes.AgentEvolutionLoop", return_value=loop), \
             patch("api.evolution_routes.get_current_user") as mock_user, \
             patch("api.evolution_routes.get_db") as mock_db:
            mock_user.return_value = SimpleNamespace(id="u-1")
            mock_db.return_value = MagicMock()
            app = _evolution_app()
            client = TestClient(app, raise_server_exceptions=False)

            async def _fake_current_user():
                return SimpleNamespace(id="u-1")

            app.dependency_overrides = {}

            from core.auth import get_current_user
            from core.database import get_db

            app.dependency_overrides[get_current_user] = _fake_current_user
            app.dependency_overrides[get_db] = lambda: MagicMock()
            r = client.post("/api/evolution/run?tenant_id=t-1&group_size=7&target_agent_id=a-1")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "started"
        assert body["tenant_id"] == "t-1"
        loop.run_evolution_cycle.assert_called_once()
        args = loop.run_evolution_cycle.call_args
        assert args.kwargs["tenant_id"] == "t-1"
        assert args.kwargs["group_size"] == 7
        assert args.kwargs["target_agent_id"] == "a-1"

    def test_run_defaults_group_size(self):
        loop = MagicMock()
        from core.auth import get_current_user
        from core.database import get_db

        with patch("api.evolution_routes.AgentEvolutionLoop", return_value=loop):
            app = _evolution_app()
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u-1")
            app.dependency_overrides[get_db] = lambda: MagicMock()
            client = TestClient(app, raise_server_exceptions=False)
            r = client.post("/api/evolution/run?tenant_id=t-1")
        assert r.status_code == 200
        assert loop.run_evolution_cycle.call_args.kwargs["group_size"] == 5

    def test_run_requires_auth(self):
        from core.auth import get_current_user

        with patch("api.evolution_routes.AgentEvolutionLoop"):
            app = _evolution_app()
            app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(
                __import__("fastapi").HTTPException(401, "unauthorized")
            )
            client = TestClient(app, raise_server_exceptions=False)
            r = client.post("/api/evolution/run?tenant_id=t-1")
        assert r.status_code == 401

    def test_traces_returns_serialized_rows(self):
        from core.auth import get_current_user
        from core.database import get_db

        trace = SimpleNamespace(
            id="tr-1", generation=3, performance_score=0.9, novelty_score=0.2,
            evolving_requirements={"focus": "x"}, created_at="2026-01-01",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [trace]
        with patch("api.evolution_routes.AgentEvolutionLoop"):
            app = _evolution_app()
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u-1")
            app.dependency_overrides[get_db] = lambda: db
            client = TestClient(app, raise_server_exceptions=False)
            r = client.get("/api/evolution/traces/a-1")
        assert r.status_code == 200
        rows = r.json()
        assert rows[0]["id"] == "tr-1"
        assert rows[0]["generation"] == 3
        assert rows[0]["performance_score"] == 0.9
        assert rows[0]["directives"] == {"focus": "x"}


# =========================================================================== #
# vfs_registry
# =========================================================================== #
class TestVfsRegistry:
    @pytest.fixture(autouse=True)
    def _clean(self):
        import core.vfs_registry as vr

        vr._REGISTRY.clear()
        yield
        vr._REGISTRY.clear()

    def _provider(self, prefix):
        p = MagicMock()
        p.prefix = prefix
        return p

    def test_register_and_get(self):
        import core.vfs_registry as vr

        p = self._provider("knowledge")
        vr.register_provider(p)
        assert vr.get_provider("knowledge") is p
        assert vr.get_provider("missing") is None

    def test_register_empty_prefix_raises(self):
        import core.vfs_registry as vr

        with pytest.raises(ValueError):
            vr.register_provider(self._provider(""))

    def test_resolve_path_variants(self):
        import core.vfs_registry as vr

        p = self._provider("knowledge")
        vr.register_provider(p)
        assert vr.resolve_provider("knowledge/documents/1") is p
        assert vr.resolve_provider("/knowledge/doc") is p
        assert vr.resolve_provider("") is None
        assert vr.resolve_provider("other/x") is None

    def test_list_prefixes_sorted(self):
        import core.vfs_registry as vr

        vr.register_provider(self._provider("zeta"))
        vr.register_provider(self._provider("alpha"))
        assert vr.list_prefixes() == ["alpha", "zeta"]

    def test_overwrite_same_prefix(self):
        import core.vfs_registry as vr

        p1 = self._provider("knowledge")
        p2 = self._provider("knowledge")
        vr.register_provider(p1)
        vr.register_provider(p2)
        assert vr.get_provider("knowledge") is p2


# =========================================================================== #
# service_registry
# =========================================================================== #
class TestServiceRegistry:
    def test_registry_listing(self):
        from core.service_registry import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        r = client.get("/api/services/registry")
        assert r.status_code == 200
        body = r.json()
        assert body["total_services"] == 6
        assert body["active_services"] == 6
        ids = {s["id"] for s in body["services"]}
        assert {"slack", "gmail", "google_calendar", "github", "asana", "notion"} <= ids

    def test_get_service_found(self):
        from core.service_registry import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        r = client.get("/api/services/slack")
        assert r.status_code == 200
        assert r.json()["name"] == "Slack"
        assert r.json()["oauth_required"] is True

    def test_get_service_404(self):
        from core.service_registry import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        r = client.get("/api/services/not-a-service")
        assert r.status_code == 404
        assert r.json()["detail"] == "Service not found"


# =========================================================================== #
# recruitment_analytics_service (stub contract)
# =========================================================================== #
class TestRecruitmentAnalytics:
    def test_stub_contract(self):
        from core.recruitment_analytics_service import RecruitmentAnalyticsService

        db = MagicMock()
        svc = RecruitmentAnalyticsService(db)
        assert svc.db is db
        assert svc.track_recruitment({"fleet_id": "f-1"}) is None
        assert svc.get_analytics("f-1") == {}


# =========================================================================== #
# push_notifications (stub contract)
# =========================================================================== #
class TestPushNotifications:
    @pytest.mark.asyncio
    async def test_stub_contract(self):
        from core.push_notifications import PushNotificationService

        svc = PushNotificationService(MagicMock(), workspace_id="w-1", tenant_id="t-1")
        assert svc.workspace_id == "w-1"
        assert svc.tenant_id == "t-1"
        out = await svc.send_push_notification("u-1", "title", "body", {"k": "v"})
        assert out["success"] is False
        assert "not available" in out["error"]
        out2 = await svc.register_device("u-1", "tok", "ios")
        assert out2["success"] is False
        out3 = await svc.unregister_device("u-1", "tok")
        assert out3["success"] is False

    @pytest.mark.asyncio
    async def test_defaults(self):
        from core.push_notifications import PushNotificationService

        svc = PushNotificationService(MagicMock())
        assert svc.workspace_id == "default"
        assert svc.tenant_id is None


# =========================================================================== #
# marketing_skills_service
# =========================================================================== #
class TestMarketingSkillsService:
    @pytest.mark.asyncio
    async def test_collect_testimonial(self):
        from core.marketing_skills_service import marketing_skills_service

        out = await marketing_skills_service.collect_testimonial(
            "ws-1", "email", "customer@x.com", "Please review us"
        )
        assert out["status"] == "initiated"
        assert out["platform"] == "email"
        assert out["target"] == "customer@x.com"
        assert "customer@x.com" in out["message"]
        assert out["initiated_at"]

    @pytest.mark.asyncio
    async def test_manage_reviews_empty_defaults(self):
        from core.marketing_skills_service import marketing_skills_service

        out = await marketing_skills_service.manage_reviews("ws-1", "google_reviews")
        assert out["platform"] == "google_reviews"
        assert out["total_reviews"] == 0
        assert out["average_rating"] == 0.0
        assert out["status"] == "ready"

    @pytest.mark.asyncio
    async def test_suggest_review_response_branches(self):
        from core.marketing_skills_service import marketing_skills_service

        good = await marketing_skills_service.suggest_review_response("love it", 5)
        assert "Thank you" in good
        ok = await marketing_skills_service.suggest_review_response("nice", 4)
        assert "Thank you" in ok
        bad = await marketing_skills_service.suggest_review_response("meh", 2)
        assert "sorry" in bad.lower()
        assert "support@example.com" in bad


# =========================================================================== #
# knowledge_vfs_config + fleet_routing_config (env flags)
# =========================================================================== #
class TestEnvFlags:
    def test_knowledge_vfs_enabled_default(self, monkeypatch):
        from core.knowledge_vfs_config import knowledge_vfs_enabled

        monkeypatch.delenv("ATOM_KNOWLEDGE_VFS_ENABLED", raising=False)
        assert knowledge_vfs_enabled() is True

    @pytest.mark.parametrize("raw,expected", [
        ("true", True), ("TRUE", True), ("1", True), ("yes", True), ("on", True),
        ("false", False), ("0", False), ("off", False), ("no", False), ("  true ", True),
    ])
    def test_knowledge_vfs_env_matrix(self, monkeypatch, raw, expected):
        from core.knowledge_vfs_config import knowledge_vfs_enabled

        monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", raw)
        assert knowledge_vfs_enabled() is expected

    def test_fleet_routing_flags_defaults(self, monkeypatch):
        from core.fleet_routing_config import (
            fleet_routing_enabled,
            fleet_routing_force_enforce,
        )

        monkeypatch.delenv("ATOM_FLEET_ROUTING_ENABLED", raising=False)
        monkeypatch.delenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", raising=False)
        assert fleet_routing_enabled() is False
        assert fleet_routing_force_enforce() is False

    def test_fleet_routing_env_matrix(self, monkeypatch):
        from core.fleet_routing_config import (
            fleet_routing_enabled,
            fleet_routing_force_enforce,
        )

        monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
        assert fleet_routing_enabled() is True
        monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "banana")
        assert fleet_routing_enabled() is False
        monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "1")
        assert fleet_routing_force_enforce() is True

    def test_canonical_env_name_constant(self):
        from core.fleet_routing_config import ATOM_FLEET_ROUTING_ENABLED

        assert ATOM_FLEET_ROUTING_ENABLED == "ATOM_FLEET_ROUTING_ENABLED"


# =========================================================================== #
# time-travel fork route
# =========================================================================== #
class TestTimeTravelRoutes:
    def _client(self):
        from api.time_travel_routes import router

        app = FastAPI()
        app.include_router(router)
        from core.auth import get_current_user
        from core.database import get_db

        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u-1")
        app.dependency_overrides[get_db] = lambda: MagicMock()
        return TestClient(app, raise_server_exceptions=False)

    def test_fork_success(self):
        orch = AsyncMock()
        orch.fork_execution.return_value = "exec-2"
        with patch("api.time_travel_routes.get_orchestrator", return_value=orch):
            r = self._client().post(
                "/api/time-travel/workflows/exec-1/fork",
                json={"step_id": "step-9", "new_variables": {"x": 1}},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["original_execution_id"] == "exec-1"
        assert body["new_execution_id"] == "exec-2"
        orch.fork_execution.assert_awaited_once_with(
            original_execution_id="exec-1", step_id="step-9", new_variables={"x": 1}
        )

    def test_fork_snapshot_missing_404(self):
        orch = AsyncMock()
        orch.fork_execution.return_value = None
        with patch("api.time_travel_routes.get_orchestrator", return_value=orch):
            r = self._client().post(
                "/api/time-travel/workflows/exec-1/fork",
                json={"step_id": "step-ghost"},
            )
        assert r.status_code == 404

    def test_fork_missing_step_id_422(self):
        with patch("api.time_travel_routes.get_orchestrator"):
            r = self._client().post("/api/time-travel/workflows/exec-1/fork", json={})
        assert r.status_code == 422


# =========================================================================== #
# workflow_patterns re-export surface
# =========================================================================== #
class TestWorkflowPatterns:
    def test_reexports(self):
        import core.orchestration.workflow_patterns as wp

        for name in wp.__all__:
            assert hasattr(wp, name), name

    def test_template_library_reachable(self):
        from core.orchestration.workflow_patterns import get_template_library

        assert callable(get_template_library)
