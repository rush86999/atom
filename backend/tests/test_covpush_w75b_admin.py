"""Coverage wave W75B — admin route modules (standalone >=95% each).

Targets:
1. api/admin/cache_routes.py           (82% before — missing 55, 57, 59, 94-99)
2. api/admin/system_health_routes.py   (28% before — imports only; the real
   endpoint path /api/admin/health/api/admin/health was never exercised)
3. api/admin/business_facts_routes.py  (98% before — missing 35, 268, 289, 411)
4. api/admin/skill_routes.py           (100% before — regression re-run standalone)

Pattern (per W74B/W53 convention): FastAPI TestClient + dependency_overrides,
patches on real module names (no `backend.` prefix), zero DB / network / LLM
spend. 401 tests run the real auth dependency chain (no token -> 401); 403
tests override get_current_user with a member and let the real
get_super_admin/require_role dependency reject.
"""
import asyncio
import io
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.admin.cache_routes import router as cache_router
from api.admin.system_health_routes import router as health_router
from api.admin.business_facts_routes import router as facts_router
from api.admin.business_facts_routes import _sanitize_filename
from api.admin.skill_routes import router as skill_router
from core.auth import get_current_user
from core.admin_endpoints import get_super_admin
from core.database import get_db


# ============================================================================
# Shared user fixtures
# ============================================================================
@pytest.fixture
def admin_user():
    user = MagicMock()
    user.id = "admin-w75b"
    user.email = "admin@test.local"
    user.first_name = "Admin"
    user.last_name = "User"
    user.role = "super_admin"
    user.status = "active"
    user.workspace_id = "default"
    user.tenant_id = "tenant-1"
    return user


@pytest.fixture
def member_user():
    user = MagicMock()
    user.id = "member-w75b"
    user.email = "member@test.local"
    user.role = "member"
    user.status = "active"
    user.workspace_id = "default"
    return user


def _admin_client(router, admin_user):
    app = FastAPI()
    app.include_router(router)

    async def _override_admin():
        return admin_user

    app.dependency_overrides[get_super_admin] = _override_admin
    yield_client = TestClient(app)
    yield_client._app = app
    return yield_client


@pytest.fixture
def cache_client(admin_user):
    return _admin_client(cache_router, admin_user)


@pytest.fixture
def health_client(admin_user):
    app = FastAPI()
    app.include_router(health_router)

    mock_db = Mock()

    async def _override_admin():
        return admin_user

    def _override_get_db():
        try:
            yield mock_db
        finally:
            pass

    app.dependency_overrides[get_super_admin] = _override_admin
    app.dependency_overrides[get_db] = _override_get_db
    yield_client = TestClient(app)
    yield_client._app = app
    return yield_client


@pytest.fixture
def skill_client(admin_user):
    return _admin_client(skill_router, admin_user)


# ============================================================================
# 1. api/admin/cache_routes.py
# ============================================================================
class TestCachePreseed:
    def test_preseed_all(self, cache_client):
        with patch("api.admin.cache_routes.preseed_all_caches", new=AsyncMock(return_value={"success": True})) as m:
            resp = cache_client.post(
                "/api/v1/admin/cache/preseed", json={"cache_type": "all", "workspace_id": "ws-9"}
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        m.assert_awaited_once_with(workspace_id="ws-9", verbose=False)

    def test_preseed_pricing(self, cache_client):
        with patch("api.admin.cache_routes.preseed_pricing_cache", new=AsyncMock(return_value={"models_loaded": 3})) as m:
            resp = cache_client.post("/api/v1/admin/cache/preseed", json={"cache_type": "pricing"})
        assert resp.status_code == 200
        assert resp.json()["pricing"]["models_loaded"] == 3
        m.assert_awaited_once_with(verbose=False)

    def test_preseed_cognitive(self, cache_client):
        with patch("api.admin.cache_routes.preseed_cognitive_models", new=AsyncMock(return_value={"tiers_loaded": 5})) as m:
            resp = cache_client.post("/api/v1/admin/cache/preseed", json={"cache_type": "cognitive"})
        assert resp.status_code == 200
        assert resp.json()["cognitive"]["tiers_loaded"] == 5
        m.assert_awaited_once_with(verbose=False)

    def test_preseed_governance(self, cache_client):
        with patch("api.admin.cache_routes.preseed_governance_cache", new=AsyncMock(return_value={"actions_cached": 60})) as m:
            resp = cache_client.post(
                "/api/v1/admin/cache/preseed", json={"cache_type": "governance", "workspace_id": "ws-9"}
            )
        assert resp.status_code == 200
        assert resp.json()["governance"]["actions_cached"] == 60
        m.assert_awaited_once_with(workspace_id="ws-9", verbose=False)

    def test_preseed_cache_aware(self, cache_client):
        with patch("api.admin.cache_routes.preseed_cache_aware_router", new=AsyncMock(return_value={"prompts_seeded": 10})) as m:
            resp = cache_client.post(
                "/api/v1/admin/cache/preseed", json={"cache_type": "cache_aware", "workspace_id": "ws-9"}
            )
        assert resp.status_code == 200
        assert resp.json()["cache_aware"]["prompts_seeded"] == 10
        m.assert_awaited_once_with(workspace_id="ws-9", verbose=False)

    def test_preseed_invalid_type_400(self, cache_client):
        resp = cache_client.post("/api/v1/admin/cache/preseed", json={"cache_type": "bogus"})
        assert resp.status_code == 400

    def test_preseed_invalid_body_422(self, cache_client):
        resp = cache_client.post("/api/v1/admin/cache/preseed", json={"cache_type": 123})
        assert resp.status_code == 422

    def test_preseed_requires_auth_401(self):
        app = FastAPI()
        app.include_router(cache_router)
        app.dependency_overrides[get_db] = _never_used_db
        resp = TestClient(app).post("/api/v1/admin/cache/preseed", json={"cache_type": "all"})
        assert resp.status_code == 401

    def test_preseed_requires_admin_403(self, member_user):
        app = FastAPI()
        app.include_router(cache_router)

        async def _override_user():
            return member_user

        app.dependency_overrides[get_current_user] = _override_user
        resp = TestClient(app).post("/api/v1/admin/cache/preseed", json={"cache_type": "all"})
        assert resp.status_code == 403

    def test_preseed_unknown_route_404(self, cache_client):
        resp = cache_client.get("/api/v1/admin/cache/nope")
        assert resp.status_code == 404


class TestCacheStats:
    def test_stats_with_last_fetch(self, cache_client):
        gov = Mock()
        gov.get_stats.return_value = {"size": 156, "hit_rate": 94.5}
        pricing = Mock()
        pricing.pricing_cache = {"gpt-4o": {}}
        pricing.last_fetch = __import__("datetime").datetime(2026, 1, 1, 12, 0, 0)
        router_instance = Mock()
        router_instance.cache_hit_history = {"k": [1, 2]}
        with patch("api.admin.cache_routes.get_governance_cache", return_value=gov), \
             patch("api.admin.cache_routes.get_pricing_fetcher", return_value=pricing), \
             patch("api.admin.cache_routes.CacheAwareRouter", return_value=router_instance):
            resp = cache_client.get("/api/v1/admin/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["governance_cache"]["size"] == 156
        assert data["pricing_cache"]["models"] == 1
        assert data["pricing_cache"]["last_fetch"] == "2026-01-01T12:00:00"
        assert data["cache_aware_router"]["cache_history_size"] == 1

    def test_stats_without_last_fetch(self, cache_client):
        gov = Mock()
        gov.get_stats.return_value = {"size": 0}
        pricing = Mock()
        pricing.pricing_cache = {}
        pricing.last_fetch = None
        router_instance = Mock()
        router_instance.cache_hit_history = {}
        with patch("api.admin.cache_routes.get_governance_cache", return_value=gov), \
             patch("api.admin.cache_routes.get_pricing_fetcher", return_value=pricing), \
             patch("api.admin.cache_routes.CacheAwareRouter", return_value=router_instance):
            resp = cache_client.get("/api/v1/admin/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pricing_cache"]["last_fetch"] is None
        assert data["pricing_cache"]["models"] == 0

    def test_stats_requires_admin_403(self, member_user):
        app = FastAPI()
        app.include_router(cache_router)

        async def _override_user():
            return member_user

        app.dependency_overrides[get_current_user] = _override_user
        resp = TestClient(app).get("/api/v1/admin/cache/stats")
        assert resp.status_code == 403


class TestCacheHealth:
    def test_health_ok(self, cache_client):
        gov = Mock()
        gov.get_stats.return_value = {"size": 42, "hit_rate": 88.0}
        with patch("api.admin.cache_routes.get_governance_cache", return_value=gov):
            resp = cache_client.get("/api/v1/admin/cache/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] == "OK"
        assert data["status"] == "OK"
        assert data["governance_cache"]["size"] == 42
        assert data["governance_cache"]["hit_rate"] == 88.0

    def test_health_empty_cache_degraded(self, cache_client):
        gov = Mock()
        gov.get_stats.return_value = {"size": 0, "hit_rate": 0.0}
        with patch("api.admin.cache_routes.get_governance_cache", return_value=gov):
            resp = cache_client.get("/api/v1/admin/cache/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] == "DEGRADED"
        assert data["reason"] == "Governance cache is empty"

    def test_health_exception_degraded(self, cache_client):
        gov = Mock()
        gov.get_stats.side_effect = RuntimeError("boom")
        with patch("api.admin.cache_routes.get_governance_cache", return_value=gov):
            resp = cache_client.get("/api/v1/admin/cache/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] == "DEGRADED"
        assert data["reason"] == "Governance cache check failed"

    def test_health_requires_auth_401(self):
        app = FastAPI()
        app.include_router(cache_router)
        app.dependency_overrides[get_db] = _never_used_db
        resp = TestClient(app).get("/api/v1/admin/cache/health")
        assert resp.status_code == 401


# ============================================================================
# 2. api/admin/system_health_routes.py
# ============================================================================
class TestSystemHealth:
    URL = "/api/admin/health/api/admin/health"

    def _ok_ctx(self, handler=None):
        handler = handler or Mock()
        handler.test_connection.return_value = {"connected": True}
        fake_time = Mock()
        fake_time.time.return_value = 100.0
        return patch("api.admin.system_health_routes.LanceDBHandler", return_value=handler), \
            patch("api.admin.system_health_routes.time", fake_time)

    def test_all_operational(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client.ping.return_value = True
        h, t = self._ok_ctx()
        with h, t, patch("api.admin.system_health_routes.cache", cache_mock):
            resp = health_client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "healthy"
        assert data["data"]["version"] == "2.1.0"
        services = data["data"]["services"]
        assert services["database"] == "operational"
        assert services["redis"] == "operational"
        assert services["vector_store"] == "operational"

    def test_db_error_degraded(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client = None
        cache_mock.config.redis.enabled = False
        handler = Mock()
        handler.test_connection.return_value = {"connected": True}
        with patch("api.admin.system_health_routes.LanceDBHandler", return_value=handler), \
             patch("api.admin.system_health_routes.cache", cache_mock), \
             patch("api.admin.system_health_routes.time", Mock(time=lambda: 100.0)):
            resp = self._request_with_failing_db(health_client)
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "degraded"
        assert resp.json()["data"]["services"]["database"] == "degraded"

    def _request_with_failing_db(self, health_client):
        # execute raises -> db degraded (lines 48-50)
        def _fail_execute(*a, **k):
            raise RuntimeError("db down")

        health_client._app.dependency_overrides[get_db] = lambda: _FailingDB(_fail_execute)
        try:
            return health_client.get(self.URL)
        finally:
            health_client._app.dependency_overrides.pop(get_db, None)

    def test_db_slow_degraded(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client = None
        cache_mock.config.redis.enabled = False
        handler = Mock()
        handler.test_connection.return_value = {"connected": True}
        fake_time = Mock()
        fake_time.time.side_effect = [100.0, 103.0]  # elapsed 3s > 2.0 -> degraded
        with patch("api.admin.system_health_routes.LanceDBHandler", return_value=handler), \
             patch("api.admin.system_health_routes.cache", cache_mock), \
             patch("api.admin.system_health_routes.time", fake_time):
            resp = health_client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["services"]["database"] == "degraded"

    def test_redis_ping_false_degraded(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client.ping.return_value = False
        handler = Mock()
        handler.test_connection.return_value = {"connected": True}
        h, t = self._ok_ctx(handler)
        with h, t, patch("api.admin.system_health_routes.cache", cache_mock):
            resp = health_client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["services"]["redis"] == "degraded"
        assert data["status"] == "degraded"

    def test_redis_no_client_config_enabled_degraded(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client = None
        cache_mock.config.redis.enabled = True
        handler = Mock()
        handler.test_connection.return_value = {"connected": True}
        h, t = self._ok_ctx(handler)
        with h, t, patch("api.admin.system_health_routes.cache", cache_mock):
            resp = health_client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["services"]["redis"] == "degraded"

    def test_redis_no_client_config_disabled_unknown(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client = None
        cache_mock.config.redis.enabled = False
        handler = Mock()
        handler.test_connection.return_value = {"connected": True}
        h, t = self._ok_ctx(handler)
        with h, t, patch("api.admin.system_health_routes.cache", cache_mock):
            resp = health_client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["services"]["redis"] == "unknown"
        assert data["status"] == "healthy"

    def test_redis_exception_degraded(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client.ping.side_effect = RuntimeError("redis boom")
        handler = Mock()
        handler.test_connection.return_value = {"connected": True}
        h, t = self._ok_ctx(handler)
        with h, t, patch("api.admin.system_health_routes.cache", cache_mock):
            resp = health_client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["services"]["redis"] == "degraded"

    def test_vector_not_connected_degraded(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client.ping.return_value = True
        handler = Mock()
        handler.test_connection.return_value = {"connected": False, "message": "lancedb down"}
        fake_time = Mock()
        fake_time.time.return_value = 100.0
        with patch("api.admin.system_health_routes.LanceDBHandler", return_value=handler), \
             patch("api.admin.system_health_routes.time", fake_time), \
             patch("api.admin.system_health_routes.cache", cache_mock):
            resp = health_client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["services"]["vector_store"] == "degraded"
        assert data["status"] == "degraded"

    def test_vector_exception_degraded(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client.ping.return_value = True
        handler = Mock()
        handler.test_connection.side_effect = RuntimeError("vector boom")
        h, t = self._ok_ctx(handler)
        with h, t, patch("api.admin.system_health_routes.cache", cache_mock):
            resp = health_client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["services"]["vector_store"] == "degraded"

    def test_vector_maintenance_when_lancedb_missing(self, health_client):
        cache_mock = MagicMock()
        cache_mock.redis_client.ping.return_value = True
        fake_time = Mock()
        fake_time.time.return_value = 100.0
        with patch("api.admin.system_health_routes.HAS_LANCEDB", False), \
             patch("api.admin.system_health_routes.time", fake_time), \
             patch("api.admin.system_health_routes.cache", cache_mock):
            resp = health_client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["services"]["vector_store"] == "maintenance"

    def test_requires_auth_401(self):
        app = FastAPI()
        app.include_router(health_router)
        app.dependency_overrides[get_db] = _never_used_db
        resp = TestClient(app).get(self.URL)
        assert resp.status_code == 401

    def test_requires_admin_403(self, member_user):
        app = FastAPI()
        app.include_router(health_router)

        async def _override_user():
            return member_user

        app.dependency_overrides[get_current_user] = _override_user
        resp = TestClient(app).get(self.URL)
        assert resp.status_code == 403

    def test_unknown_route_404(self, health_client):
        resp = health_client.get("/api/admin/health/nope")
        assert resp.status_code == 404

    def test_lancedb_import_error_sets_has_lancedb_false(self):
        """Cover the ImportError branch at module import time (lines 20-22)."""
        import importlib

        mod = sys.modules["api.admin.system_health_routes"]
        try:
            with patch.dict(sys.modules, {"core.lancedb_handler": None}):
                reloaded = importlib.reload(mod)
            assert reloaded.HAS_LANCEDB is False
        finally:
            importlib.reload(mod)


class _FailingDB:
    """Minimal session stand-in whose execute() raises."""

    def __init__(self, fail_execute):
        self._fail_execute = fail_execute

    def execute(self, *args, **kwargs):
        return self._fail_execute(*args, **kwargs)


def _never_used_db():
    """get_db override for 401 tests: real auth rejects before touching the DB."""
    mock_db = Mock()

    def _gen():
        try:
            yield mock_db
        finally:
            pass

    return _gen()


# ============================================================================
# 3. api/admin/business_facts_routes.py
# ============================================================================
@pytest.fixture
def facts_client(admin_user):
    app = FastAPI()
    app.include_router(facts_router)

    async def _override_user():
        return admin_user

    app.dependency_overrides[get_current_user] = _override_user
    yield_client = TestClient(app)
    yield_client._app = app
    return yield_client


class TestSanitizeFilename:
    def test_none_filename_defaults_to_upload(self):
        assert _sanitize_filename(None) == "upload"

    def test_path_traversal_stripped(self):
        assert _sanitize_filename("../../etc/passwd") == "passwd"

    def test_dangerous_characters_replaced(self):
        assert _sanitize_filename("a b;c|d") == "a_b_c_d"

    def test_length_capped_at_128(self):
        assert len(_sanitize_filename("x" * 300)) == 128

    def test_all_invalid_chars_replaced(self):
        assert _sanitize_filename("!!!") == "___"

    def test_empty_string_defaults(self):
        assert _sanitize_filename("") == "upload"


class TestFactsList:
    def test_list_empty(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.list_all_facts = AsyncMock(return_value=[])
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.get("/api/admin/governance/facts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_data_and_deleted_filtered(self, facts_client):
        live = self._fact("f-live", "fact-a", {"domain": "accounting"}, "verified")
        deleted = self._fact("f-del", "fact-b", None, "deleted")
        mock_wm = AsyncMock()
        mock_wm.list_all_facts = AsyncMock(return_value=[live, deleted])
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.get("/api/admin/governance/facts")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == "f-live"
        assert body[0]["domain"] == "accounting"

    def test_list_with_filters_passed(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.list_all_facts = AsyncMock(return_value=[])
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.get(
                "/api/admin/governance/facts?status=verified&domain=ops&limit=25"
            )
        assert resp.status_code == 200
        mock_wm.list_all_facts.assert_awaited_once_with(status="verified", domain="ops", limit=25)

    def test_list_requires_admin_403(self, member_user):
        app = FastAPI()
        app.include_router(facts_router)

        async def _override_user():
            return member_user

        app.dependency_overrides[get_current_user] = _override_user
        resp = TestClient(app).get("/api/admin/governance/facts")
        assert resp.status_code == 403

    def test_list_requires_auth_401(self):
        app = FastAPI()
        app.include_router(facts_router)
        app.dependency_overrides[get_db] = _never_used_db
        resp = TestClient(app).get("/api/admin/governance/facts")
        assert resp.status_code == 401

    @staticmethod
    def _fact(fid, text, metadata, vstatus):
        from core.agent_world_model import BusinessFact

        return BusinessFact(
            id=fid,
            fact=text,
            citations=["policy.pdf:p1"],
            reason="r",
            source_agent_id="user:u1",
            created_at=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc),
            last_verified=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc),
            verification_status=vstatus,
            metadata=metadata if metadata is not None else {},
        )


class TestFactsGet:
    def test_get_success_with_metadata(self, facts_client):
        fact = TestFactsList._fact("f1", "Invoices > $500 need VP approval", {"domain": "finance"}, "verified")
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.get("/api/admin/governance/facts/f1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["fact"] == "Invoices > $500 need VP approval"
        assert body["domain"] == "finance"
        assert body["verification_status"] == "verified"

    def test_get_success_without_metadata_defaults_general(self, facts_client):
        fact = TestFactsList._fact("f2", "fact", None, "verified")
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.get("/api/admin/governance/facts/f2")
        assert resp.status_code == 200
        assert resp.json()["domain"] == "general"

    def test_get_not_found_404(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=None)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.get("/api/admin/governance/facts/missing")
        assert resp.status_code == 404


class TestFactsCreate:
    def test_create_success_201(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.record_business_fact = AsyncMock(return_value=True)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.post(
                "/api/admin/governance/facts",
                json={
                    "fact": "Net-30 terms apply",
                    "citations": ["terms.pdf:p2"],
                    "reason": "Policy",
                    "domain": "sales",
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["fact"] == "Net-30 terms apply"
        assert body["domain"] == "sales"
        assert body["verification_status"] == "verified"

    def test_create_with_defaults(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.record_business_fact = AsyncMock(return_value=True)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.post("/api/admin/governance/facts", json={"fact": "bare fact"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["domain"] == "general"
        assert body["citations"] == []

    def test_create_record_failure_500(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.record_business_fact = AsyncMock(return_value=False)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.post("/api/admin/governance/facts", json={"fact": "doomed"})
        assert resp.status_code == 500

    def test_create_missing_fact_422(self, facts_client):
        resp = facts_client.post("/api/admin/governance/facts", json={})
        assert resp.status_code == 422


class TestFactsUpdate:
    def test_update_not_found_404(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=None)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.put("/api/admin/governance/facts/missing", json={"fact": "x"})
        assert resp.status_code == 404

    def test_update_verification_status_only(self, facts_client):
        existing = TestFactsList._fact("f1", "orig", {"domain": "general"}, "verified")
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=existing)
        mock_wm.update_fact_verification = AsyncMock()
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.put(
                "/api/admin/governance/facts/f1", json={"verification_status": "outdated"}
            )
        assert resp.status_code == 200
        mock_wm.update_fact_verification.assert_awaited_once_with("f1", "outdated")
        assert resp.json()["verification_status"] == "outdated"

    def test_update_all_fields(self, facts_client):
        existing = TestFactsList._fact("f1", "orig", {"domain": "general"}, "verified")
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=existing)
        mock_wm.update_fact_verification = AsyncMock()
        mock_wm.record_business_fact = AsyncMock()
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.put(
                "/api/admin/governance/facts/f1",
                json={
                    "fact": "updated",
                    "citations": ["u.pdf:p1"],
                    "reason": "ur",
                    "domain": "ops",
                    "verification_status": "verified",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["fact"] == "updated"
        assert body["domain"] == "ops"
        mock_wm.record_business_fact.assert_awaited_once()


class TestFactsDelete:
    def test_delete_success(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.delete_fact = AsyncMock(return_value=True)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.delete("/api/admin/governance/facts/f1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted", "id": "f1"}

    def test_delete_not_found_404(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.delete_fact = AsyncMock(return_value=False)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.delete("/api/admin/governance/facts/missing")
        assert resp.status_code == 404


class TestFactsUpload:
    URL = "/api/admin/governance/facts/upload"

    def test_upload_success(self, facts_client):
        storage = MagicMock()
        storage.upload_file = Mock(return_value="s3://atom-business-facts/bucket/doc.pdf")
        storage.bucket = "atom-business-facts"

        extracted = Mock(fact="Rule A", citations=[], domain="accounting")
        extractor = AsyncMock()
        extractor.extract_facts_from_document = AsyncMock(
            return_value=Mock(facts=[extracted], extraction_time=1.25)
        )
        mock_wm = AsyncMock()
        mock_wm.bulk_record_facts = AsyncMock(return_value=1)

        with patch("core.storage.get_storage_service", return_value=storage), \
             patch("api.admin.business_facts_routes.get_policy_fact_extractor", return_value=extractor), \
             patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.post(
                self.URL,
                files={"file": ("policy.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
                data={"domain": "accounting"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["facts_extracted"] == 1
        assert body["source_document"] == "policy.pdf"
        assert body["extraction_time"] == 1.25
        assert body["facts"][0]["fact"] == "Rule A"
        extractor.extract_facts_from_document.assert_awaited_once()

    def test_upload_zero_facts(self, facts_client):
        storage = MagicMock()
        storage.upload_file = Mock(return_value="s3://atom-business-facts/b/doc.pdf")
        storage.bucket = "atom-business-facts"
        extractor = AsyncMock()
        extractor.extract_facts_from_document = AsyncMock(
            return_value=Mock(facts=[], extraction_time=0.1)
        )
        mock_wm = AsyncMock()
        mock_wm.bulk_record_facts = AsyncMock(return_value=0)
        with patch("core.storage.get_storage_service", return_value=storage), \
             patch("api.admin.business_facts_routes.get_policy_fact_extractor", return_value=extractor), \
             patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.post(
                self.URL,
                files={"file": ("notes.txt", io.BytesIO(b"txt"), "text/plain")},
                data={"domain": "general"},
            )
        assert resp.status_code == 200
        assert resp.json()["facts_extracted"] == 0
        assert resp.json()["facts"] == []

    @pytest.mark.parametrize("filename", ["evil.exe", "script.sh", "archive.zip"])
    def test_upload_unsupported_extension_422(self, facts_client, filename):
        resp = facts_client.post(
            self.URL,
            files={"file": (filename, io.BytesIO(b"data"), "application/octet-stream")},
            data={"domain": "general"},
        )
        assert resp.status_code == 422

    def test_upload_file_size_cap_422(self, facts_client):
        with patch.dict(os.environ, {"MAX_UPLOAD_BYTES": "5"}):
            resp = facts_client.post(
                self.URL,
                files={"file": ("big.pdf", io.BytesIO(b"x" * 100), "application/pdf")},
                data={"domain": "general"},
            )
        assert resp.status_code == 422
        assert "exceeds maximum size" in resp.json()["detail"]["error"]["message"]

    def test_upload_content_too_large_after_read_422(self):
        """Direct-call branch: file.size is None but read() content exceeds cap."""
        from api.admin.business_facts_routes import upload_and_extract

        mock_file = MagicMock()
        mock_file.filename = "big.pdf"
        mock_file.size = None
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"x" * 1000)
        user = SimpleNamespace(id="u1")
        with patch.dict(os.environ, {"MAX_UPLOAD_BYTES": "10"}):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(
                    upload_and_extract(file=mock_file, domain="general", current_user=user, _=None)
                )
        assert exc.value.status_code == 422
        assert "exceeds maximum size" in exc.value.detail["error"]["message"]

    def test_upload_extraction_failure_500(self, facts_client):
        storage = MagicMock()
        storage.upload_file = Mock(side_effect=RuntimeError("r2 down"))
        with patch("core.storage.get_storage_service", return_value=storage):
            resp = facts_client.post(
                self.URL,
                files={"file": ("policy.pdf", io.BytesIO(b"x"), "application/pdf")},
                data={"domain": "general"},
            )
        assert resp.status_code == 500


class TestFactsVerifyCitation:
    URL = "/api/admin/governance/facts/{}/verify-citation"

    def test_fact_not_found_404(self, facts_client):
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=None)
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm):
            resp = facts_client.post(self.URL.format("missing"))
        assert resp.status_code == 404

    def test_s3_citation_exists_verified(self, facts_client):
        fact = TestFactsList._fact("f1", "fact", {}, "verified")
        fact.citations = ["s3://atom-business-facts/workspace-1/doc.pdf"]
        storage = MagicMock()
        storage.bucket = "atom-business-facts"
        storage.check_exists = Mock(return_value=True)
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact)
        mock_wm.update_fact_verification = AsyncMock()
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm), \
             patch("core.storage.get_storage_service", return_value=storage):
            resp = facts_client.post(self.URL.format("f1"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["new_status"] == "verified"
        assert body["citations"][0]["exists"] is True
        assert body["citations"][0]["source"] == "R2"
        mock_wm.update_fact_verification.assert_awaited_once_with("f1", "verified")

    def test_s3_citation_missing_outdated(self, facts_client):
        fact = TestFactsList._fact("f1", "fact", {}, "verified")
        fact.citations = ["s3://atom-business-facts/workspace-1/doc.pdf"]
        storage = MagicMock()
        storage.bucket = "atom-business-facts"
        storage.check_exists = Mock(return_value=False)
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact)
        mock_wm.update_fact_verification = AsyncMock()
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm), \
             patch("core.storage.get_storage_service", return_value=storage):
            resp = facts_client.post(self.URL.format("f1"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["new_status"] == "outdated"
        mock_wm.update_fact_verification.assert_awaited_once_with("f1", "outdated")

    def test_s3_check_exception_outdated(self, facts_client):
        fact = TestFactsList._fact("f1", "fact", {}, "verified")
        fact.citations = ["s3://atom-business-facts/doc.pdf"]
        storage = MagicMock()
        storage.bucket = "atom-business-facts"
        storage.check_exists = Mock(side_effect=RuntimeError("s3 error"))
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact)
        mock_wm.update_fact_verification = AsyncMock()
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm), \
             patch("core.storage.get_storage_service", return_value=storage):
            resp = facts_client.post(self.URL.format("f1"))
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "outdated"

    def test_s3_cross_bucket_parse_branch(self, facts_client):
        """Citation 's3://bucket/key' (no trailing slash) -> else-branch parse."""
        fact = TestFactsList._fact("f1", "fact", {}, "verified")
        fact.citations = ["s3://atom-business-facts/doc.pdf"]
        storage = MagicMock()
        storage.bucket = "atom-business-facts"
        storage.check_exists = Mock(return_value=True)
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact)
        mock_wm.update_fact_verification = AsyncMock()
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm), \
             patch("core.storage.get_storage_service", return_value=storage):
            resp = facts_client.post(self.URL.format("f1"))
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "verified"
        storage.check_exists.assert_called_once_with("doc.pdf")

    def test_s3_other_bucket_outdated(self, facts_client):
        fact = TestFactsList._fact("f1", "fact", {}, "verified")
        fact.citations = ["s3://other-bucket/doc.pdf"]
        storage = MagicMock()
        storage.bucket = "atom-business-facts"
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact)
        mock_wm.update_fact_verification = AsyncMock()
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm), \
             patch("core.storage.get_storage_service", return_value=storage):
            resp = facts_client.post(self.URL.format("f1"))
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "outdated"

    def test_local_citation_exists(self, facts_client):
        fact = TestFactsList._fact("f1", "fact", {}, "verified")
        fact.citations = ["policy.pdf:p4"]
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact)
        mock_wm.update_fact_verification = AsyncMock()
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm), \
             patch("os.path.exists", return_value=True):
            resp = facts_client.post(self.URL.format("f1"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["new_status"] == "verified"
        assert body["citations"][0]["source"] == "Local"
        assert body["citations"][0]["exists"] is True

    def test_local_citation_missing(self, facts_client):
        fact = TestFactsList._fact("f1", "fact", {}, "verified")
        fact.citations = ["policy.pdf:p4"]
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact)
        mock_wm.update_fact_verification = AsyncMock()
        with patch("api.admin.business_facts_routes.WorldModelService", return_value=mock_wm), \
             patch("os.path.exists", return_value=False):
            resp = facts_client.post(self.URL.format("f1"))
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "outdated"


# ============================================================================
# 4. api/admin/skill_routes.py
# ============================================================================
class TestAdminSkillRoutes:
    URL = "/api/admin/skills/"

    def _payload(self, name="skill-w75b"):
        return {
            "name": name,
            "description": "desc",
            "instructions": "You are helpful",
            "capabilities": ["web_search"],
            "scripts": {"main.py": "def main():\n    pass"},
        }

    def _patch_builder(self, result=None):
        builder = Mock()
        builder.create_skill_package.return_value = result or {
            "success": True,
            "message": "created",
            "skill_path": "/tmp/skills/x",
        }
        return patch("api.admin.skill_routes.skill_builder_service", builder)

    def test_create_success(self, skill_client):
        with patch("api.admin.skill_routes.StaticAnalyzer") as analyzer, \
             self._patch_builder() as builder:
            analyzer.return_value.scan_content.return_value = []
            resp = skill_client.post(self.URL, json=self._payload())
        assert resp.status_code == 200
        assert resp.json()["data"]["success"] is True
        builder.create_skill_package.assert_called_once()

    def test_create_critical_finding_403(self, skill_client):
        finding = Mock()
        finding.severity.value = "HIGH"
        finding.dict.return_value = {"severity": "HIGH", "category": "injection"}
        with patch("api.admin.skill_routes.StaticAnalyzer") as analyzer:
            analyzer.return_value.scan_content.return_value = [finding]
            resp = skill_client.post(self.URL, json=self._payload("evil"))
        assert resp.status_code == 403
        body = resp.json()
        assert body["detail"]["error"]["code"] == "PERMISSION_DENIED"
        assert "security policy violations" in body["detail"]["error"]["details"]["message"]

    def test_create_llm_scan_low_finding_ok(self, skill_client):
        low = Mock()
        low.severity.value = "LOW"
        low.dict.return_value = {"severity": "LOW"}
        llm_analyzer = AsyncMock()
        llm_analyzer.analyze = AsyncMock(return_value=[low])
        with patch("api.admin.skill_routes.StaticAnalyzer") as analyzer, \
             patch("atom_security.analyzers.llm.LLMAnalyzer", return_value=llm_analyzer), \
             self._patch_builder():
            analyzer.return_value.scan_content.return_value = []
            with patch.dict(os.environ, {"ATOM_SECURITY_ENABLE_LLM_SCAN": "true"}):
                resp = skill_client.post(self.URL, json=self._payload("llm"))
        assert resp.status_code == 200
        llm_analyzer.analyze.assert_awaited_once()

    def test_create_llm_scan_failure_ok(self, skill_client):
        llm_analyzer = AsyncMock()
        llm_analyzer.analyze = AsyncMock(side_effect=RuntimeError("llm down"))
        with patch("api.admin.skill_routes.StaticAnalyzer") as analyzer, \
             patch("atom_security.analyzers.llm.LLMAnalyzer", return_value=llm_analyzer), \
             self._patch_builder():
            analyzer.return_value.scan_content.return_value = []
            with patch.dict(os.environ, {"ATOM_SECURITY_ENABLE_LLM_SCAN": "true"}):
                resp = skill_client.post(self.URL, json=self._payload("llmfail"))
        assert resp.status_code == 200

    def test_create_security_scan_exception_ok(self, skill_client):
        with patch("api.admin.skill_routes.StaticAnalyzer") as analyzer, \
             self._patch_builder():
            analyzer.return_value.scan_content.side_effect = RuntimeError("scanner down")
            resp = skill_client.post(self.URL, json=self._payload("scanfail"))
        assert resp.status_code == 200

    def test_create_builder_failure_422(self, skill_client):
        with patch("api.admin.skill_routes.StaticAnalyzer") as analyzer, \
             self._patch_builder({"success": False, "message": "Invalid skill structure"}):
            analyzer.return_value.scan_content.return_value = []
            resp = skill_client.post(self.URL, json=self._payload("bad"))
        assert resp.status_code == 422

    def test_create_unhandled_exception_500(self, skill_client):
        builder = Mock()
        builder.create_skill_package.side_effect = RuntimeError("boom")
        with patch("api.admin.skill_routes.StaticAnalyzer") as analyzer, \
             patch("api.admin.skill_routes.skill_builder_service", builder):
            analyzer.return_value.scan_content.return_value = []
            resp = skill_client.post(self.URL, json=self._payload("crash"))
        assert resp.status_code == 500

    def test_create_default_tenant_when_none(self, admin_user):
        admin_user.tenant_id = None
        app = FastAPI()
        app.include_router(skill_router)

        async def _override_admin():
            return admin_user

        app.dependency_overrides[get_super_admin] = _override_admin
        client = TestClient(app)

        builder = Mock()
        builder.create_skill_package.return_value = {"success": True, "message": "ok"}
        with patch("api.admin.skill_routes.StaticAnalyzer") as analyzer, \
             patch("api.admin.skill_routes.skill_builder_service", builder):
            analyzer.return_value.scan_content.return_value = []
            resp = client.post(self.URL, json=self._payload("tenant"))
        assert resp.status_code == 200
        assert builder.create_skill_package.call_args.kwargs["tenant_id"] == "default"

    def test_create_validation_422(self, skill_client):
        resp = skill_client.post(self.URL, json={"name": "incomplete"})
        assert resp.status_code == 422

    def test_create_requires_auth_401(self):
        app = FastAPI()
        app.include_router(skill_router)
        app.dependency_overrides[get_db] = _never_used_db
        resp = TestClient(app).post(
            self.URL, json=self._payload("unauth")
        )
        assert resp.status_code == 401

    def test_create_requires_admin_403(self, member_user):
        app = FastAPI()
        app.include_router(skill_router)

        async def _override_user():
            return member_user

        app.dependency_overrides[get_current_user] = _override_user
        resp = TestClient(app).post(self.URL, json=self._payload("member"))
        assert resp.status_code == 403
