"""Coverage wave 92 — integrations/chat_routes.py (29% → 95%+).

Closes the never-wave-tested gaps: session rename/get (manager lazy-load,
legacy placeholder reclaim success + fail-closed rebind rollback, IDOR 403),
send message (routing-override headers, "new" session, no_llm_provider +
budget_exceeded sentinels, 500), cancel, feedback (invalid value, router
disabled, thumbs up/down with/without comment, recording failure), routing
stats (disabled/enabled/error), harness evolution (mining + active patches +
both failure branches), chat memory (dead helper called directly), history
(DB fallback, 403, 404, lazy init), sessions list, health (healthy/degraded/
unhealthy), root.

Security: every endpoint except /health and / asserts 401 anonymous.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security_dependencies import get_current_user
from integrations import chat_routes as cr

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(cr.router)
    return application


@pytest.fixture
def anon_client(app):
    return TestClient(app)


@pytest.fixture
def client(app):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user_1", tenant_id="t1")
    return TestClient(app)


@pytest.fixture
def orch():
    with patch.object(cr, "chat_orchestrator") as m:
        m.session_manager = MagicMock()
        yield m


def make_session(session_id="s1", owner="user_1", title="My chat",
                 history=None, context=None, created_at=None, last_updated=None):
    return {
        "id": session_id,
        "session_id": session_id,
        "user_id": owner,
        "title": title,
        "created_at": created_at or "2026-01-01T00:00:00",
        "last_updated": last_updated or "2026-01-01T00:00:00",
        "history": history or [],
        "context": context or {},
    }


class TestAuth:
    @pytest.mark.parametrize("method,path,kwargs", [
        ("patch", "/api/chat/sessions/s1", {"json": {"title": "x", "user_id": "u"}}),
        ("get", "/api/chat/sessions/s1", {"params": {"user_id": "u"}}),
        ("post", "/api/chat/message", {"json": {"message": "hi", "user_id": "u"}}),
        ("post", "/api/chat/cancel/s1", {}),
        ("post", "/api/chat/feedback", {"json": {"message_id": "m", "feedback": "thumbs_up"}}),
        ("get", "/api/chat/routing-stats", {}),
        ("get", "/api/chat/harness-evolution", {}),
        ("get", "/api/chat/history/s1", {"params": {"user_id": "u"}}),
        ("get", "/api/chat/sessions", {"params": {"user_id": "u"}}),
    ])
    def test_anonymous_rejected(self, anon_client, method, path, kwargs):
        resp = getattr(anon_client, method)(path, **kwargs)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"

    def test_health_and_root_public(self, anon_client):
        assert anon_client.get("/api/chat/health").status_code == 200
        assert anon_client.get("/api/chat/").status_code == 200


class TestRenameSession:
    def test_success(self, client, orch):
        orch.conversation_sessions = {"s1": make_session()}
        orch.session_manager.rename_session.return_value = True
        resp = client.patch("/api/chat/sessions/s1", json={"title": "New", "user_id": "x"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"
        orch.session_manager.rename_session.assert_called_once_with("s1", "New")

    def test_not_found_in_memory(self, client, orch):
        orch.conversation_sessions = {}
        orch.session_manager.get_session.return_value = None
        resp = client.patch("/api/chat/sessions/missing", json={"title": "x", "user_id": "u"})
        assert resp.status_code == 404

    def test_lazy_managed_session(self, client, orch):
        managed = make_session()
        orch.conversation_sessions = {}
        orch.session_manager.get_session.return_value = managed
        orch.session_manager.rename_session.return_value = True
        resp = client.patch("/api/chat/sessions/s1", json={"title": "R", "user_id": "u"})
        assert resp.status_code == 200

    def test_cross_user_denied(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(owner="other_user")}
        resp = client.patch("/api/chat/sessions/s1", json={"title": "x", "user_id": "u"})
        assert resp.status_code == 403
        assert "Access denied" in resp.json()["detail"]

    def test_legacy_placeholder_reclaimed(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(owner="default_user")}
        orch.session_manager.rebind_session_owner.return_value = True
        orch.session_manager.rename_session.return_value = True
        resp = client.patch("/api/chat/sessions/s1", json={"title": "Mine", "user_id": "u"})
        assert resp.status_code == 200
        assert orch.conversation_sessions["s1"]["user_id"] == "user_1"
        orch.session_manager.rebind_session_owner.assert_called_once_with("s1", "user_1")

    def test_legacy_rebind_fail_closed(self, client, orch):
        """Unpersisted rebind must refuse access AND roll back the claim."""
        orch.conversation_sessions = {"s1": make_session(owner="anonymous")}
        orch.session_manager.rebind_session_owner.return_value = None
        resp = client.patch("/api/chat/sessions/s1", json={"title": "x", "user_id": "u"})
        assert resp.status_code == 403
        assert orch.conversation_sessions["s1"]["user_id"] == "anonymous"

    def test_rename_failed_404(self, client, orch):
        orch.conversation_sessions = {"s1": make_session()}
        orch.session_manager.rename_session.return_value = False
        resp = client.patch("/api/chat/sessions/s1", json={"title": "x", "user_id": "u"})
        assert resp.status_code == 404

    def test_internal_error_500(self, client, orch):
        orch.conversation_sessions = {"s1": make_session()}
        orch.session_manager.rename_session.side_effect = RuntimeError("boom")
        resp = client.patch("/api/chat/sessions/s1", json={"title": "x", "user_id": "u"})
        assert resp.status_code == 500

    def test_rebind_exception_logged_and_refused(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(owner="guest")}
        orch.session_manager.rebind_session_owner.side_effect = RuntimeError("db down")
        resp = client.patch("/api/chat/sessions/s1", json={"title": "x", "user_id": "u"})
        assert resp.status_code == 403
        assert orch.conversation_sessions["s1"]["user_id"] == "guest"


class TestGetSessionDetails:
    def test_success(self, client, orch):
        orch.conversation_sessions = {"s1": make_session()}
        resp = client.get("/api/chat/sessions/s1", params={"user_id": "u"})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user_1"

    def test_not_found(self, client, orch):
        orch.conversation_sessions = {}
        orch.session_manager.get_session.return_value = None
        resp = client.get("/api/chat/sessions/missing", params={"user_id": "u"})
        assert resp.status_code == 404

    def test_manager_fallback(self, client, orch):
        managed = make_session()
        orch.conversation_sessions = {}
        orch.session_manager.get_session.return_value = managed
        resp = client.get("/api/chat/sessions/s1", params={"user_id": "u"})
        assert resp.status_code == 200

    def test_cross_user_denied(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(owner="other")}
        resp = client.get("/api/chat/sessions/s1", params={"user_id": "u"})
        assert resp.status_code == 403

    def test_internal_error_500(self, client, orch):
        orch.conversation_sessions = MagicMock()
        orch.conversation_sessions.get.side_effect = RuntimeError("boom")
        resp = client.get("/api/chat/sessions/s1", params={"user_id": "u"})
        assert resp.status_code == 500


class TestSendMessage:
    def test_success(self, client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "success": True, "message": "Hello", "session_id": "s1",
            "intent": "conversation", "confidence": 0.9,
            "suggested_actions": [], "requires_confirmation": False,
            "next_steps": [], "timestamp": "t", "data": {"k": "v"},
            "model": "m1", "provider": "p1"})
        resp = client.post("/api/chat/message", json={"message": "hi", "user_id": "u"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["metadata"] == {"k": "v"}
        assert body["model"] == "m1"
        orch.process_chat_message.assert_awaited_once()

    def test_routing_override_headers(self, client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "success": True, "message": "ok", "session_id": "s1"})
        client.post("/api/chat/message", json={"message": "hi", "user_id": "u"},
                    headers={"x-atom-tier": "standard", "x-atom-model": "gpt-4o",
                             "x-atom-intent": "conversation"})
        kwargs = orch.process_chat_message.await_args[1]
        assert kwargs["routing_overrides"] == {"tier": "standard",
                                               "model": "gpt-4o", "intent": "conversation"}

    def test_invalid_override_header_ignored(self, client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "success": True, "message": "ok", "session_id": "s1"})
        client.post("/api/chat/message", json={"message": "hi", "user_id": "u"},
                    headers={"x-atom-tier": "bogus-tier"})
        kwargs = orch.process_chat_message.await_args[1]
        assert kwargs["routing_overrides"] is None

    def test_parse_override_exception_tolerated(self, client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "success": True, "message": "ok", "session_id": "s1"})
        with patch.object(cr, "parse_routing_overrides",
                          side_effect=RuntimeError("boom")):
            resp = client.post("/api/chat/message", json={"message": "hi", "user_id": "u"},
                               headers={"x-atom-tier": "standard"})
        assert resp.status_code == 200
        assert orch.process_chat_message.await_args[1]["routing_overrides"] is None

    def test_new_session_normalized(self, client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "success": True, "message": "ok", "session_id": "fresh"})
        client.post("/api/chat/message",
                    json={"message": "hi", "user_id": "u", "session_id": "new"})
        assert orch.process_chat_message.await_args[1]["session_id"] is None

    def test_no_llm_provider_sentinel(self, client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "success": False, "message": "LLM client not initialized", "session_id": "s1"})
        resp = client.post("/api/chat/message", json={"message": "hi", "user_id": "u"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error_code"] == "no_llm_provider"
        assert body["recovery_url"] == "/settings/ai"

    def test_budget_exceeded(self, client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "success": False, "message": "halted", "error_code": "budget_exceeded",
            "recovery_url": "/settings/billing"})
        resp = client.post("/api/chat/message", json={"message": "hi", "user_id": "u"})
        body = resp.json()
        assert body["error_code"] == "budget_exceeded"
        assert body["recovery_url"] == "/settings/billing"

    def test_internal_error_500(self, client, orch):
        orch.process_chat_message = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/chat/message", json={"message": "hi", "user_id": "u"})
        assert resp.status_code == 500


class TestCancel:
    def test_cancel(self, client, orch):
        resp = client.post("/api/chat/cancel/s1")
        assert resp.status_code == 200
        assert resp.json() == {"cancelled": True, "session_id": "s1"}
        orch.request_cancellation.assert_called_once_with("s1")


class TestFeedback:
    def test_invalid_feedback_422(self, client):
        resp = client.post("/api/chat/feedback",
                           json={"message_id": "m", "feedback": "sideways"})
        assert resp.status_code == 422

    def test_router_disabled_acknowledged(self, client, orch):
        with patch.object(cr, "_get_learning_router", return_value=None):
            resp = client.post("/api/chat/feedback",
                               json={"message_id": "m", "feedback": "thumbs_up"})
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "recorded": False,
                               "reason": "learning_router_disabled"}

    def test_thumbs_up_recorded(self, client, orch):
        router = MagicMock()
        router.resolve_feedback_context.return_value = ("coding", "rid_9")
        router.record_feedback = AsyncMock()
        with patch.object(cr, "_get_learning_router", return_value=router), \
             patch("core.learning_llm_router.LearningBasedRouter.build_feedback",
                   return_value=MagicMock()) as build:
            resp = client.post("/api/chat/feedback",
                               json={"message_id": "m1", "feedback": "thumbs_up"})
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "recorded": True}
        kwargs = build.call_args[1]
        assert kwargs["routing_result_id"] == "rid_9"
        assert kwargs["task_type"] == "coding"
        assert kwargs["quality"].quality_satisfied is True

    def test_thumbs_down_with_comment(self, client, orch):
        router = MagicMock()
        router.resolve_feedback_context.return_value = (None, None)
        router.record_feedback = AsyncMock()
        with patch.object(cr, "_get_learning_router", return_value=router), \
             patch("core.learning_llm_router.LearningBasedRouter.build_feedback") as build:
            client.post("/api/chat/feedback",
                        json={"message_id": "m1", "feedback": "thumbs_down",
                              "comment": "wrong answer"})
        quality = build.call_args[1]["quality"]
        assert quality.quality_satisfied is False
        assert quality.quality_score == 0.15
        # message_id fallback for decision id
        assert build.call_args[1]["routing_result_id"] == "m1"

    def test_thumbs_down_bare(self, client, orch):
        router = MagicMock()
        router.resolve_feedback_context.return_value = (None, None)
        router.record_feedback = AsyncMock()
        with patch.object(cr, "_get_learning_router", return_value=router), \
             patch("core.learning_llm_router.LearningBasedRouter.build_feedback") as build:
            client.post("/api/chat/feedback",
                        json={"message_id": "m1", "feedback": "thumbs_down"})
        assert build.call_args[1]["quality"].quality_score == 0.3

    def test_record_failure_nonfatal(self, client, orch):
        router = MagicMock()
        router.resolve_feedback_context.return_value = (None, None)
        router.record_feedback = AsyncMock(side_effect=RuntimeError("db down"))
        with patch.object(cr, "_get_learning_router", return_value=router), \
             patch("core.learning_llm_router.LearningBasedRouter.build_feedback",
                   return_value=MagicMock()):
            resp = client.post("/api/chat/feedback",
                               json={"message_id": "m", "feedback": "thumbs_up"})
        assert resp.json() == {"success": True, "recorded": False,
                               "reason": "db down"}


class TestRoutingStats:
    """Exercise the REAL _learning_router_enabled/_ema_router_enabled/
    _get_learning_router wrappers (registry functions patched instead)."""

    def test_disabled(self, client, orch):
        with patch("core.llm.learning_router_registry.learning_router_enabled",
                   return_value=False), \
             patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=False):
            resp = client.get("/api/chat/routing-stats")
        body = resp.json()
        assert body["enabled"] is False
        assert body["stats"]["feedback_samples"] == 0

    def test_enabled_no_router(self, client, orch):
        with patch("core.llm.learning_router_registry.learning_router_enabled",
                   return_value=True), \
             patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=False), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=None):
            resp = client.get("/api/chat/routing-stats")
        assert resp.json()["enabled"] is True

    def test_stats_success(self, client, orch):
        router = MagicMock()
        router.get_routing_statistics = AsyncMock(
            return_value={"feedback_samples": 5, "model_success_rates": {"m": 0.8}})
        with patch("core.llm.learning_router_registry.learning_router_enabled",
                   return_value=True), \
             patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=True), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router):
            resp = client.get("/api/chat/routing-stats")
        assert resp.json()["stats"]["feedback_samples"] == 5

    def test_stats_error(self, client, orch):
        router = MagicMock()
        router.get_routing_statistics = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.llm.learning_router_registry.learning_router_enabled",
                   return_value=True), \
             patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=False), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router):
            resp = client.get("/api/chat/routing-stats")
        assert "error" in resp.json()["stats"]


class TestHarnessEvolution:
    def _db_mock(self, rows):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = rows
        gen = iter([db])

        def fake_get_db():
            return gen

        return db, fake_get_db

    def test_success(self, client, orch):
        row = SimpleNamespace(id="agent_1", name="Agent 1", configuration={"harness_patches": [
            {"patch_id": "p1", "target_component": "agent_loop",
             "mutation_payload": {}, "model_scope": "gpt-4o"}]})
        db, fake_get_db = self._db_mock([row])
        service = MagicMock()
        service.mine_weaknesses = AsyncMock(return_value=[{"weakness": "w1"}])
        with patch("core.database.get_db", fake_get_db), \
             patch("core.harness_evolution_service.HarnessEvolutionService",
                   return_value=service):
            resp = client.get("/api/chat/harness-evolution")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mined_weaknesses"] == [{"weakness": "w1"}]
        assert body["active_patches"][0]["patch_id"] == "p1"
        assert body["active_patches"][0]["agent_id"] == row.id

    def test_mining_failure_returns_empty(self, client, orch):
        db, fake_get_db = self._db_mock([])
        service = MagicMock()
        service.mine_weaknesses = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.database.get_db", fake_get_db), \
             patch("core.harness_evolution_service.HarnessEvolutionService",
                   return_value=service):
            resp = client.get("/api/chat/harness-evolution")
        assert resp.json()["mined_weaknesses"] == []
        assert resp.json()["active_patches"] == []

    def test_patch_query_failure(self, client, orch):
        db, fake_get_db = self._db_mock([MagicMock()])
        db.query.side_effect = RuntimeError("boom")
        service = MagicMock()
        service.mine_weaknesses = AsyncMock(return_value=[])
        with patch("core.database.get_db", fake_get_db), \
             patch("core.harness_evolution_service.HarnessEvolutionService",
                   return_value=service):
            resp = client.get("/api/chat/harness-evolution")
        assert resp.json()["active_patches"] == []


class TestGetChatMemory:
    async def _call(self, orch, session_id="s1", owner="user_1"):
        orch.conversation_sessions = {"s1": make_session(owner=owner, context={"a": 1})}
        user = SimpleNamespace(id="user_1")
        return await cr.get_chat_memory(session_id, "u", user)

    def test_success(self, orch):
        import asyncio
        resp = asyncio.run(self._call(orch))
        assert resp.session_id == "s1"
        assert resp.memory_context == {"a": 1}

    def test_session_not_found(self, orch):
        import asyncio
        import pytest
        orch.conversation_sessions = {}
        with pytest.raises(Exception) as exc:
            asyncio.run(self._call(orch, session_id="missing"))
        assert exc.value.status_code == 404

    def test_cross_user_403(self, orch):
        import asyncio
        import pytest
        with pytest.raises(Exception) as exc:
            asyncio.run(self._call(orch, owner="other"))
        assert exc.value.status_code == 403

    def test_internal_error_500(self, orch):
        import asyncio
        import pytest
        orch.conversation_sessions = MagicMock()
        orch.conversation_sessions.__contains__.side_effect = RuntimeError("boom")
        user = SimpleNamespace(id="user_1")
        with pytest.raises(Exception) as exc:
            asyncio.run(cr.get_chat_memory("s1", "u", user))
        assert exc.value.status_code == 500


class TestGetChatHistory:
    def test_in_memory_history(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(
            history=[{"message": "hi"}])}
        # The durable store is read FIRST now (fork-from-here needs real
        # message ids) — mock an empty DB so the in-memory fallback engages
        # instead of reading ambient rows for session "s1".
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=False)
        with patch("core.database.get_db_session", return_value=cm):
            resp = client.get("/api/chat/history/s1", params={"user_id": "u"})
        assert resp.status_code == 200
        assert resp.json()["messages"] == [{"message": "hi"}]

    def test_lazy_init_new_session(self, client, orch):
        orch.conversation_sessions = {}
        lazy = make_session()
        orch._get_or_create_session.return_value = lazy
        resp = client.get("/api/chat/history/snew", params={"user_id": "u"})
        assert resp.status_code == 200
        orch._get_or_create_session.assert_called_once_with("user_1", "snew")

    def test_cross_user_denied(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(owner="other")}
        resp = client.get("/api/chat/history/s1", params={"user_id": "u"})
        assert resp.status_code == 403

    def test_db_fallback(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(history=[])}
        rows = [
            SimpleNamespace(id="m1", role="user", content="hi", created_at=datetime(2026, 1, 1, 10)),
            SimpleNamespace(id="m2", role="assistant", content="hello", created_at=datetime(2026, 1, 1, 10, 1)),
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=False)
        with patch("core.database.get_db_session", return_value=cm):
            resp = client.get("/api/chat/history/s1", params={"user_id": "u"})
        messages = resp.json()["messages"]
        assert messages[0]["message"] == "hi"
        assert messages[1]["response"] == {"message": "hello"}

    def test_db_fallback_failure_tolerated(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(history=[])}
        cm = MagicMock()
        cm.__enter__.side_effect = RuntimeError("db down")
        with patch("core.database.get_db_session", return_value=cm):
            resp = client.get("/api/chat/history/s1", params={"user_id": "u"})
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    def test_internal_error_500(self, client, orch):
        orch.conversation_sessions = MagicMock()
        orch.conversation_sessions.__contains__.side_effect = RuntimeError("boom")
        resp = client.get("/api/chat/history/s1", params={"user_id": "u"})
        assert resp.status_code == 500


class TestGetUserSessions:
    def test_success(self, client, orch):
        orch.get_user_sessions.return_value = {"s1": make_session()}
        resp = client.get("/api/chat/sessions", params={"user_id": "u"})
        assert resp.status_code == 200
        assert resp.json()["total_sessions"] == 1
        orch.get_user_sessions.assert_called_once_with("user_1")

    def test_internal_error_500(self, client, orch):
        orch.get_user_sessions.side_effect = RuntimeError("boom")
        resp = client.get("/api/chat/sessions", params={"user_id": "u"})
        assert resp.status_code == 500


class TestHealthAndRoot:
    def test_healthy(self, client, orch):
        orch.feature_handlers = {"search": object()}
        orch.platform_connectors = {"slack": object()}
        orch.ai_engines = {"nlp": object()}
        orch.conversation_sessions = {"s1": {}}
        resp = client.get("/api/chat/health")
        assert resp.json()["status"] == "healthy"
        assert resp.json()["metrics"]["total_sessions"] == 1

    def test_degraded_no_handlers(self, client, orch):
        orch.feature_handlers = {}
        resp = client.get("/api/chat/health")
        assert resp.json()["status"] == "degraded"

    def test_unhealthy_on_error(self, client, orch):
        class ExplodingOrchestrator:
            @property
            def feature_handlers(self):
                raise RuntimeError("boom")
        with patch.object(cr, "chat_orchestrator", ExplodingOrchestrator()):
            resp = client.get("/api/chat/health")
        assert resp.json()["status"] == "unhealthy"

    def test_root(self, client):
        resp = client.get("/api/chat/")
        assert resp.json()["service"] == "chat_integration"
