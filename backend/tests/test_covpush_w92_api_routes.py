# -*- coding: utf-8 -*-
"""Coverage wave 92 — api/byok_routes.py, api/enterprise_auth_endpoints.py,
api/workflow_debugging.py, api/mini_app_routes.py.

No network / no LLM / no real DB: every external boundary (auth services,
workflow debugger, mini-app services, storage, pricing fetchers, LLM call
tracker) is mocked. Plain pytest + unittest.mock with FastAPI TestClient and
dependency_overrides for get_current_user / get_db / get_current_tenant /
get_byok_manager / oauth2_scheme.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

import api.byok_routes as byok
import api.enterprise_auth_endpoints as ea
import api.mini_app_routes as ma
import api.workflow_debugging as wd
from core.auth import get_current_user
from core.database import get_db

USER = SimpleNamespace(id="u1", email="u1@example.com", tenant_id="t1",
                       workspace_id="w1", is_admin=False, is_staff=False)
TENANT = SimpleNamespace(id="t1", name="Tenant One", ai_mode="auto")


@dataclass
class LlmCallRec:
    provider: str
    model: str
    success: bool


def make_client(module, db=None, extra_overrides=None):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
    for dep, fn in (extra_overrides or {}).items():
        app.dependency_overrides[dep] = fn
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# BYOK helpers
# ---------------------------------------------------------------------------
def real_byok_manager(tmp_path, monkeypatch):
    """Build a real BYOKManager against tmp files (covers persistence code)."""
    monkeypatch.setattr(byok, "BYOK_CONFIG_FILE", str(tmp_path / "byok_config.json"))
    monkeypatch.setattr(byok, "BYOK_KEYS_FILE", str(tmp_path / "byok_keys.json"))
    monkeypatch.setattr(byok, "BYOK_ENC_KEY_FILE", str(tmp_path / "byok_enc_key"))
    monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
    return byok.BYOKManager()


def byok_client(manager, db=None):
    return make_client(byok, db=db, extra_overrides={
        byok.get_byok_manager: lambda: manager,
        byok.get_current_tenant: lambda: TENANT,
    })


def tenant_setting_db(setting=None, count=0):
    db = MagicMock()
    chain = MagicMock()
    chain.filter.return_value.first.return_value = setting
    chain.filter.return_value.count.return_value = count
    db.query.return_value = chain
    return db


def keyed_tenant_setting_db(manager, setting_keys):
    """TenantSetting db whose .first() returns a row only for the given
    setting keys (e.g. {"OPENAI_API_KEY"}), determined by inspecting the
    filter() call args."""
    db = MagicMock()
    chain = MagicMock()

    def first():
        call = chain.filter.call_args
        literals = []
        if call:
            for expr in call.args:
                try:
                    v = expr.right.value
                    if isinstance(v, str):
                        literals.append(v)
                except Exception:
                    pass
        if any(k in literals for k in setting_keys):
            return SimpleNamespace(setting_value=manager.encrypt_api_key("sk-tenant-key"))
        return None

    chain.filter.return_value.first.side_effect = first
    chain.filter.return_value.count.return_value = len(setting_keys)
    db.query.return_value = chain
    return db


# ============================================================================
# BYOK — manager internals (config load/save, encryption, key lifecycle)
# ============================================================================
class TestByokManagerInternals:
    def test_init_creates_and_persists_encryption_key(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        assert m.encryption_key
        assert (tmp_path / "byok_enc_key").exists()

    def test_load_or_create_reuses_persisted_key(self, tmp_path, monkeypatch):
        (tmp_path / "byok_enc_key").write_text("persisted-key\n")
        m = real_byok_manager(tmp_path, monkeypatch)
        assert m.encryption_key == "persisted-key"

    def test_load_or_create_empty_file_regenerates(self, tmp_path, monkeypatch):
        (tmp_path / "byok_enc_key").write_text("   ")
        m = real_byok_manager(tmp_path, monkeypatch)
        assert m.encryption_key

    def test_load_or_create_read_error(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        (tmp_path / "byok_enc_key").unlink()
        with patch.object(byok.os.path, "exists", Mock(side_effect=RuntimeError("io"))):
            key = byok.BYOKManager._load_or_create_encryption_key(m)
        assert key

    def test_load_or_create_persist_error(self, tmp_path, monkeypatch):
        (tmp_path / "byok_enc_key").write_text("")  # force regenerate path
        with patch("builtins.open", Mock(side_effect=OSError("no disk"))):
            m = byok.BYOKManager.__new__(byok.BYOKManager)
            key = byok.BYOKManager._load_or_create_encryption_key(m)
        assert key

    def test_env_key_wins(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)  # deletes env first
        monkeypatch.setenv("BYOK_ENCRYPTION_KEY", "env-key")
        m2 = byok.BYOKManager()
        assert m2.encryption_key == "env-key"

    def test_get_fernet_invalid_key_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BYOK_ENCRYPTION_KEY", "not-a-fernet-key")
        m = byok.BYOKManager.__new__(byok.BYOKManager)
        m.encryption_key = "bogus"
        with pytest.raises(Exception):
            byok.BYOKManager._get_fernet(m)

    def test_get_fernet_empty_key_raises(self):
        m = byok.BYOKManager.__new__(byok.BYOKManager)
        m.encryption_key = ""
        with pytest.raises(ValueError):
            byok.BYOKManager._get_fernet(m)

    def test_encrypt_decrypt_roundtrip(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        enc = m.encrypt_api_key("sk-secret-value")
        assert m.decrypt_api_key(enc) == "sk-secret-value"

    def test_load_configuration_reads_files(self, tmp_path, monkeypatch):
        real_byok_manager(tmp_path, monkeypatch)  # create defaults + key file
        # Rewrite config with an unknown field (forward compat) + ISO dates.
        cfg = {"providers": [{
            "id": "openai", "name": "OpenAI", "description": "d",
            "api_key_env_var": "OPENAI_API_KEY", "supported_tasks": ["chat"],
            "future_field": 1,
        }]}
        (tmp_path / "byok_config.json").write_text(json.dumps(cfg))
        now = datetime.now().isoformat()
        keys = {"keys": {
            "openai_default_production": {
                "provider_id": "openai", "key_name": "default",
                "encrypted_key": "x", "key_hash": "h",
                "created_at": now, "last_used": now, "unknown_k": 2,
            }}}
        (tmp_path / "byok_keys.json").write_text(json.dumps(keys))
        m = real_byok_manager(tmp_path, monkeypatch)
        assert "openai" in m.providers
        k = m.api_keys["openai_default_production"]
        assert isinstance(k.created_at, datetime)
        assert isinstance(k.last_used, datetime)

    def test_load_configuration_bad_json_logged(self, tmp_path, monkeypatch):
        real_byok_manager(tmp_path, monkeypatch)
        (tmp_path / "byok_config.json").write_text("{not json")
        (tmp_path / "byok_keys.json").write_text("{not json")
        m = real_byok_manager(tmp_path, monkeypatch)
        assert m.providers  # defaults still initialized

    def test_save_configuration_write_errors_logged(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        with patch("builtins.open", Mock(side_effect=OSError("ro fs"))):
            m._save_configuration()  # both error branches hit

    def test_store_and_get_api_key(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        key_id = m.store_api_key("openai", "sk-abcdefgh1234")
        assert key_id == "openai_default_production"
        assert m.get_api_key("openai") == "sk-abcdefgh1234"
        obj = m.api_keys[key_id]
        assert obj.usage_count == 1 and obj.last_used is not None

    def test_store_api_key_unknown_provider(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        with pytest.raises(ValueError):
            m.store_api_key("nope", "sk-x")

    def test_get_api_key_missing_and_corrupt(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        assert m.get_api_key("openai") is None
        m.store_api_key("openai", "sk-abcdefgh1234")
        m.api_keys["openai_default_production"].encrypted_key = "garbage"
        assert m.get_api_key("openai") is None

    def test_is_configured(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        assert m.is_configured("t1", "openai") is False
        m.store_api_key("openai", "sk-abcdefgh1234")
        assert m.is_configured("t1", "openai") is True
        m.api_keys["tenant_t1_openai_default_production"] = m.api_keys["openai_default_production"]
        m.api_keys.pop("openai_default_production")
        assert m.is_configured("t1", "openai") is True

    def test_track_usage_and_tenant_usage(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        m.track_usage("", "openai", success=True, tokens_used=100)
        m.track_usage("t1", "openai", success=True, tokens_used=100)
        m.track_usage("t1", "openai", success=False)
        u = m.usage_stats["t1"]["openai"]
        assert u.total_requests == 2 and u.successful_requests == 1
        assert u.failed_requests == 1 and u.cost_accumulated > 0
        assert m.get_tenant_usage("nope") == {}

    def test_get_optimal_provider_variants(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        assert m.get_optimal_provider("chat") is None  # no keys
        m.store_api_key("openai", "sk-abcdefgh1234")
        m.store_api_key("anthropic", "sk-anthropickey")
        assert m.get_optimal_provider("chat") == "anthropic"  # cheaper
        assert m.get_optimal_provider("chat", budget_constraint=0.00002) == "anthropic"
        assert m.get_optimal_provider("chat", budget_constraint=0.000001) is None
        assert m.get_optimal_provider("chat", min_reasoning_level=9) is None
        m.providers["anthropic"].is_active = False
        assert m.get_optimal_provider("chat") == "openai"

    def test_get_tenant_optimal_provider(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        # No keys anywhere -> None
        empty = tenant_setting_db()
        assert m.get_tenant_optimal_provider("t1", "chat", db=empty) is None
        assert m.get_tenant_optimal_provider("t1", "chat") is None
        # Only OPENAI has a tenant key in the DB -> tenant path picks openai
        db = keyed_tenant_setting_db(m, {"OPENAI_API_KEY"})
        assert m.get_tenant_optimal_provider("t1", "chat", db=db) == "openai"
        assert m.get_tenant_optimal_provider("t1", "chat", budget_constraint=0.0000001, db=db) is None
        # Global key + no tenant keys -> fallback to global provider selection
        m.store_api_key("openai", "sk-abcdefgh1234")
        assert m.get_tenant_optimal_provider("t1", "chat", db=empty) == "openai"

    def test_get_provider_status(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        m.store_api_key("openai", "sk-abcdefgh1234")
        st = m.get_provider_status("openai")
        assert st["status"] == "active" and st["has_api_keys"] is True
        with pytest.raises(ValueError):
            m.get_provider_status("missing")

    def test_has_tenant_keys(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        assert m.has_tenant_keys("t1") is False
        assert m.has_tenant_keys("t1", db=tenant_setting_db(count=3)) is True
        m.store_tenant_api_key("t1", "openai", "sk-tenantabcdefgh")
        assert m.has_tenant_keys("t1") is True

    def test_get_tenant_provider_status(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        st = m.get_tenant_provider_status("t1", "openai", db=tenant_setting_db())
        assert st["has_tenant_key"] is False and st["status"] == "inactive"
        enc = m.encrypt_api_key("sk-tenantabcdefgh")
        st2 = m.get_tenant_provider_status(
            "t1", "openai", db=tenant_setting_db(setting=SimpleNamespace(setting_value=enc)))
        assert st2["has_tenant_key"] is True
        with pytest.raises(ValueError):
            m.get_tenant_provider_status("t1", "missing")

    def test_store_tenant_api_key_syncs_db(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        db = tenant_setting_db()  # no existing setting -> db.add branch
        key_id = m.store_tenant_api_key("t1", "openai", "sk-tenantabcdefgh", db=db)
        assert key_id.startswith("tenant_t1_openai")
        existing = SimpleNamespace(setting_value="old", updated_at=None)
        m.store_tenant_api_key("t1", "openai", "sk-tenantabcdefgh2",
                               db=tenant_setting_db(setting=existing))
        assert existing.updated_at is not None
        with pytest.raises(ValueError):
            m.store_tenant_api_key("t1", "nope", "sk-x", db=MagicMock())

    def test_get_tenant_api_key(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        enc = m.encrypt_api_key("sk-tenantabcdefgh")
        db = tenant_setting_db(setting=SimpleNamespace(setting_value=enc))
        assert m.get_tenant_api_key("t1", "openai", db=db) == "sk-tenantabcdefgh"
        # Legacy plaintext row falls back to raw value
        db_plain = tenant_setting_db(setting=SimpleNamespace(setting_value="legacy-plain"))
        assert m.get_tenant_api_key("t1", "openai", db=db_plain) == "legacy-plain"
        assert m.get_tenant_api_key("t1", "openai") is None
        m.store_tenant_api_key("t1", "openai", "sk-tenantabcdefgh")
        assert m.get_tenant_api_key("t1", "openai") == "sk-tenantabcdefgh"
        m.api_keys["tenant_t1_openai_default_production"].encrypted_key = "junk"
        assert m.get_tenant_api_key("t1", "openai") is None


# ============================================================================
# BYOK — routes
# ============================================================================
class TestByokRoutes:
    def test_health(self, tmp_path, monkeypatch):
        r = byok_client(real_byok_manager(tmp_path, monkeypatch)).get("/api/v1/byok/health")
        assert r.status_code == 200 and r.json()["success"] is True

    def test_list_keys_masked_and_corrupt(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        m.store_api_key("openai", "sk-abcdefgh1234")
        m.store_api_key("anthropic", "sk-anthropic123")
        m.api_keys["anthropic_default_production"].encrypted_key = "junk"
        r = byok_client(m).get("/api/ai/keys")
        keys = r.json()["data"]["keys"]
        assert len(keys) == 2
        masked = {k["key_id"]: k["masked_key"] for k in keys}
        assert masked["openai_default_production"].startswith("sk-a")
        assert masked["anthropic_default_production"].startswith("junk"[:0] + "junk"[:4]) is False  # from hash

    def test_add_api_key_routes(self, tmp_path, monkeypatch):
        c = byok_client(real_byok_manager(tmp_path, monkeypatch))
        assert c.post("/api/ai/keys", json={}).status_code == 400
        assert c.post("/api/ai/keys", json={"provider": "x", "key": "y"}).status_code == 400
        r = c.post("/api/ai/keys", json={"provider": "openai", "key": "sk-abcdefgh1234"})
        assert r.status_code == 200 and r.json()["data"]["key_id"]

    def test_providers_listing_with_one_failure(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        real = m.get_tenant_provider_status
        calls = {"n": 0}

        def flaky(tenant_id, provider_id, db=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValueError("boom")
            return real(tenant_id, provider_id, db=db)

        m.get_tenant_provider_status = flaky
        r = byok_client(m, db=MagicMock()).get("/api/ai/providers")
        data = r.json()["data"]
        assert data["total_providers"] == len(m.providers) - 1
        assert "ai_mode" in data

    def test_provider_detail_and_404(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        c = byok_client(m, db=MagicMock())
        assert c.get("/api/ai/providers/openai").status_code == 200
        assert c.get("/api/ai/providers/nope").status_code == 404

    def test_store_provider_key_routes(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        db = tenant_setting_db()
        c = byok_client(m, db=db)
        assert c.post("/api/ai/providers/openai/keys?api_key=short").status_code == 422
        assert c.post("/api/ai/providers/nope/keys?api_key=sk-abcdefgh1234").status_code == 404
        with patch.object(m, "store_tenant_api_key", Mock(side_effect=RuntimeError("db down"))):
            assert c.post("/api/ai/providers/openai/keys?api_key=sk-abcdefgh1234").status_code == 500
        r = c.post("/api/ai/providers/openai/keys?api_key=sk-abcdefgh1234")
        assert r.status_code == 200 and r.json()["data"]["key_id"]

    def test_key_status_and_delete(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        c = byok_client(m)
        assert c.get("/api/ai/providers/openai/keys/default").status_code == 404
        assert c.delete("/api/ai/providers/openai/keys/default").status_code == 404
        m.store_api_key("openai", "sk-abcdefgh1234")
        r = c.get("/api/ai/providers/openai/keys/default")
        assert r.json()["data"]["has_key"] is True
        assert c.delete("/api/ai/providers/openai/keys/default").status_code == 200

    def test_optimize_cost(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        m.store_api_key("openai", "sk-abcdefgh1234")
        m.store_api_key("anthropic", "sk-anthropickey")
        c = byok_client(m)
        r = c.post("/api/ai/optimize-cost", json={"task_type": "chat", "estimated_tokens": 500})
        data = r.json()["data"]
        assert data["recommended_provider"] == "anthropic"
        assert data["alternatives"]
        assert c.post("/api/ai/optimize-cost", json={"task_type": "nosuch"}).status_code == 400
        with patch.object(m, "get_optimal_provider", Mock(side_effect=ValueError("v"))):
            assert c.post("/api/ai/optimize-cost", json={}).status_code == 400
        with patch.object(m, "get_optimal_provider", Mock(side_effect=RuntimeError("x"))):
            assert c.post("/api/ai/optimize-cost", json={}).status_code == 500

    def test_track_usage_route(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        c = byok_client(m)
        assert c.post("/api/ai/usage/track", json={}).status_code == 400
        r = c.post("/api/ai/usage/track", json={"provider_id": "openai", "tokens_used": 5})
        assert r.status_code == 200

    def test_usage_stats_route(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        m.track_usage("t1", "openai", tokens_used=10)
        c = byok_client(m)
        assert c.get("/api/ai/usage/stats?tenant_id=nope").json()["data"]["total_providers"] == 0
        r = c.get("/api/ai/usage/stats?tenant_id=t1&provider_id=openai")
        assert r.json()["data"]["usage"]["total_requests"] == 1
        assert c.get("/api/ai/usage/stats?tenant_id=t1&provider_id=missing").status_code == 404
        allr = c.get("/api/ai/usage/stats").json()["data"]
        assert allr["total_tenants"] == 1
        with patch.object(byok, "asdict", Mock(side_effect=RuntimeError("x"))):
            assert c.get("/api/ai/usage/stats").status_code == 500

    def test_usage_calls_route(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        c = byok_client(m)
        tracker = MagicMock()
        call = LlmCallRec(provider="openai", model="gpt", success=True)
        tracker.get_recent_calls.return_value = [call]
        tracker.get_summary.return_value = {"total": 1}
        import core.llm_call_tracker as lct
        with patch.object(lct, "get_llm_call_tracker", lambda: tracker):
            r = c.get("/api/ai/usage/calls?provider=openai&limit=5")
        assert r.json()["data"]["summary"] == {"total": 1}
        with patch.object(lct, "get_llm_call_tracker", Mock(side_effect=RuntimeError("x"))):
            assert c.get("/api/ai/usage/calls").status_code == 500

    def test_pdf_providers_route(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        m.store_api_key("openai", "sk-abcdefgh1234")
        r = byok_client(m).get("/api/ai/pdf/providers")
        ids = [p["provider"]["id"] for p in r.json()["data"]["pdf_providers"]]
        assert "openai" in ids

    def test_pdf_optimize_route(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        db = keyed_tenant_setting_db(m, {"OPENAI_API_KEY"})
        c = byok_client(m, db=db)
        r = c.post("/api/ai/pdf/optimize", json={"needs_ocr": True, "estimated_pages": 4})
        assert r.status_code == 200
        assert r.json()["data"]["recommended_provider"]["provider_id"] == "openai"
        assert byok_client(m, db=tenant_setting_db()).post(
            "/api/ai/pdf/optimize", json={"needs_ocr": True}).status_code == 400
        with patch.object(m, "get_tenant_optimal_provider", Mock(side_effect=ValueError("v"))):
            assert c.post("/api/ai/pdf/optimize", json={}).status_code == 400
        with patch.object(m, "get_tenant_optimal_provider", Mock(side_effect=RuntimeError("x"))):
            assert c.post("/api/ai/pdf/optimize", json={}).status_code == 500

    def test_ai_health_route(self, tmp_path, monkeypatch):
        m = real_byok_manager(tmp_path, monkeypatch)
        r = byok_client(m).get("/api/ai/health")
        data = r.json()["data"]
        assert data["providers"]["total"] == len(m.providers)
        with patch.object(m, "get_provider_status", Mock(side_effect=RuntimeError("x"))):
            assert byok_client(m).get("/api/ai/health").status_code == 503

    def _fetcher(self, **kw):
        f = MagicMock()
        f.pricing_cache = {"m1": {}, "m2": {}}
        f.last_fetch = datetime(2026, 1, 1)
        f._is_cache_valid.return_value = True
        f.get_cheapest_models.return_value = kw.get("cheapest", [])
        f.compare_providers.return_value = kw.get("compare", {})
        f.get_model_price.return_value = kw.get("price")
        f.get_provider_models.return_value = kw.get("models", [])
        f.estimate_cost.return_value = kw.get("estimate")
        return f

    def test_pricing_routes(self, tmp_path, monkeypatch):
        import core.dynamic_pricing_fetcher as dpf
        c = byok_client(real_byok_manager(tmp_path, monkeypatch))
        f = self._fetcher()
        with patch.object(dpf, "get_pricing_fetcher", lambda: f):
            r = c.get("/api/ai/pricing")
            assert r.json()["data"]["model_count"] == 2
            assert c.get("/api/ai/pricing/model/gpt-4o").json()["data"]["model"] == "gpt-4o"
            f.get_model_price.return_value = None
            assert c.get("/api/ai/pricing/model/gpt-4o").json()["success"] is False
            assert c.get("/api/ai/pricing/provider/openai").json()["data"]["model_count"] == 0
            f.estimate_cost.return_value = 0.5
            body = c.post("/api/ai/pricing/estimate",
                          json={"model": "m1", "input_tokens": 10, "output_tokens": 5}).json()["data"]
            assert body["estimated_cost_usd"] == 0.5
            f.estimate_cost.return_value = None
            f.get_model_price.return_value = {"input_cost_per_token": 1, "output_cost_per_token": 2}
            body = c.post("/api/ai/pricing/estimate",
                          json={"model": "m1", "prompt": "x" * 40,
                                "output_tokens": 5}).json()["data"]
            assert body["input_tokens"] == 10 and body["estimated_cost_usd"] == 20
            f.get_model_price.return_value = None
            assert c.post("/api/ai/pricing/estimate", json={"model": "m1"}).json()["success"] is False
        with patch.object(dpf, "get_pricing_fetcher", Mock(side_effect=RuntimeError("x"))):
            assert c.get("/api/ai/pricing").json()["success"] is False
            assert c.get("/api/ai/pricing/model/m").json()["success"] is False
            assert c.get("/api/ai/pricing/provider/p").json()["success"] is False
            assert c.post("/api/ai/pricing/estimate", json={}).json()["success"] is False

    def test_pricing_refresh(self, tmp_path, monkeypatch):
        import core.dynamic_pricing_fetcher as dpf
        c = byok_client(real_byok_manager(tmp_path, monkeypatch))
        with patch.object(dpf, "refresh_pricing_cache", AsyncMock(return_value={"m": {}})):
            r = c.post("/api/ai/pricing/refresh?force=true")
            assert r.json()["data"]["models_fetched"] == 1
        with patch.object(dpf, "refresh_pricing_cache", AsyncMock(side_effect=RuntimeError("x"))):
            assert c.post("/api/ai/pricing/refresh").json()["success"] is False


# ============================================================================
# Enterprise auth endpoints
# ============================================================================
def ea_auth_service(**kw):
    svc = MagicMock()
    svc.hash_password.return_value = kw.get("hash", "hashed")
    svc.create_access_token.return_value = "access"
    svc.create_refresh_token.return_value = "refresh"
    svc.access_token_expiry = SimpleNamespace(total_seconds=lambda: 3600)
    svc.verify_token.return_value = kw.get("claims")
    svc.verify_password.return_value = kw.get("verify_password", True)
    svc.verify_credentials.return_value = kw.get("creds")
    return svc


def ea_db(first_by_model=None):
    """db.query(Model).filter(...).first() resolved per model."""
    first_by_model = first_by_model or {}
    db = MagicMock()

    def query(model, *a, **k):
        chain = MagicMock()
        chain.filter.return_value.first.return_value = first_by_model.get(model)
        return chain

    db.query.side_effect = query
    return db


class EaUser(SimpleNamespace):
    pass


def ea_user(**kw):
    base = dict(id="uid-1", email="u@example.com", first_name="A", last_name="B",
                role="member", status="active", workspace_id="w", tenant_id="t",
                created_at=None, last_login=None, hashed_password="hashed",
                updated_at=None)
    base.update(kw)
    return EaUser(**base)


def ea_client(db):
    return make_client(ea, db=db, extra_overrides={ea.oauth2_scheme: lambda: "tok"})


class TestEnterpriseAuth:
    def test_register_success_and_tenant_fallback(self):
        import core.models as models
        svc = ea_auth_service()
        db = ea_db({models.User: None})
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc):
            r = ea_client(db).post("/api/auth/register", json={
                "email": "new@x.com", "password": "password123",
                "first_name": "A", "last_name": "B"})
        assert r.status_code == 201

    def test_register_existing_conflict(self):
        import core.models as models
        db = ea_db({models.User: ea_user()})
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: ea_auth_service()):
            r = ea_client(db).post("/api/auth/register", json={
                "email": "u@example.com", "password": "password123",
                "first_name": "A", "last_name": "B"})
        assert r.status_code == 409

    def test_register_integrity_error_conflict(self):
        import core.models as models
        db = ea_db({models.User: None})
        db.commit.side_effect = IntegrityError("s", "p", Exception())
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: ea_auth_service()):
            r = ea_client(db).post("/api/auth/register", json={
                "email": "n@x.com", "password": "password123",
                "first_name": "A", "last_name": "B"})
        assert r.status_code == 409

    def test_register_generic_error(self):
        import core.models as models
        svc = ea_auth_service()
        svc.hash_password.side_effect = RuntimeError("boom")
        db = ea_db({models.User: None})
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc), \
             patch("core.security.auth_rate_limit._register_limiter") as rlim:
            rlim.check.return_value = (True, 2)  # avoid 429 from earlier tests
            rlim._client_ip.return_value = "127.0.0.1"
            r = ea_client(db).post("/api/auth/register", json={
                "email": "n@x.com", "password": "password123",
                "first_name": "A", "last_name": "B"})
        assert r.status_code == 500

    CREDS = {"user_id": "uid-1", "username": "u", "email": "u@example.com",
             "roles": ["member"], "security_level": "standard", "permissions": []}

    def test_login_success(self):
        import core.models as models
        db = ea_db({models.User: ea_user()})
        with patch("core.enterprise_auth_service.EnterpriseAuthService",
                   lambda: ea_auth_service()), \
             patch.object(ea, "_verify_enterprise_credentials",
                          AsyncMock(return_value=dict(self.CREDS))), \
             patch("core.security.auth_rate_limit._login_limiter") as lim:
            lim.check.return_value = (True, 5)
            lim._client_ip.return_value = "127.0.0.1"
            r = ea_client(db).post("/api/auth/login", json={
                "username": "u@example.com", "password": "password123"})
        assert r.status_code == 200 and r.json()["access_token"] == "access"
        lim.reset_ip.assert_called_once()

    def test_login_invalid_credentials(self):
        with patch("core.enterprise_auth_service.EnterpriseAuthService",
                   lambda: ea_auth_service()), \
             patch.object(ea, "_verify_enterprise_credentials",
                          AsyncMock(return_value=None)):
            r = ea_client(ea_db()).post("/api/auth/login", json={
                "username": "u@example.com", "password": "wrong"})
        assert r.status_code == 401

    def test_login_generic_error(self):
        with patch("core.enterprise_auth_service.EnterpriseAuthService",
                   lambda: ea_auth_service()), \
             patch.object(ea, "_verify_enterprise_credentials",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            r = ea_client(ea_db()).post("/api/auth/login", json={
                "username": "u@example.com", "password": "x"})
        assert r.status_code == 500

    def test_refresh_success_with_and_without_creds(self):
        import core.models as models
        creds = SimpleNamespace(user_id="uid-1", username="u", email="u@example.com",
                                roles=["member"], security_level="standard",
                                permissions=["read"])
        for ret in (creds, None):
            db = ea_db({models.User: ea_user()})
            svc = ea_auth_service(claims={"type": "refresh", "user_id": "uid-1"},
                                  creds=ret)
            with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc):
                r = ea_client(db).post("/api/auth/refresh", json={"refresh_token": "rt"})
            assert r.status_code == 200

    def test_refresh_invalid_token(self):
        for claims in (None, {"type": "access", "user_id": "x"}):
            svc = ea_auth_service(claims=claims)
            with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc):
                r = ea_client(ea_db()).post("/api/auth/refresh", json={"refresh_token": "rt"})
            assert r.status_code == 401

    def test_refresh_user_not_found(self):
        import core.models as models
        svc = ea_auth_service(claims={"type": "refresh", "user_id": "gone"})
        db = ea_db({models.User: None})
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc):
            r = ea_client(db).post("/api/auth/refresh", json={"refresh_token": "rt"})
        assert r.status_code == 401

    def test_refresh_generic_error(self):
        svc = ea_auth_service(claims={"type": "refresh", "user_id": "uid-1"})
        svc.create_access_token.side_effect = RuntimeError("x")
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc):
            r = ea_client(ea_db({SimpleNamespace: ea_user()})).post(
                "/api/auth/refresh", json={"refresh_token": "rt"})
        assert r.status_code == 401

    def test_me_success_and_errors(self):
        import core.models as models
        svc = ea_auth_service(claims={"user_id": "uid-1"})
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc):
            r = ea_client(ea_db({models.User: ea_user()})).get("/api/auth/me")
            assert r.status_code == 200
            svc2 = ea_auth_service(claims={"user_id": "nope"})
            with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc2):
                rr = ea_client(ea_db({models.User: None})).get("/api/auth/me")
            assert rr.status_code == 404
        svc3 = ea_auth_service(claims=None)
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc3):
            assert ea_client(ea_db()).get("/api/auth/me").status_code == 401
        svc4 = ea_auth_service(claims={"user_id": "x"})
        svc4.verify_token.side_effect = RuntimeError("boom")
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc4):
            assert ea_client(ea_db()).get("/api/auth/me").status_code == 500

    def test_change_password_paths(self):
        import core.models as models
        body = {"old_password": "oldpassword", "new_password": "newpassword1"}
        ok = ea_auth_service(claims={"user_id": "uid-1"})
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: ok):
            c = ea_client(ea_db({models.User: ea_user()}))
            assert c.post("/api/auth/change-password", json=body).status_code == 200
        locked = ea_auth_service(claims={"user_id": "uid-1"})
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: locked):
            c = ea_client(ea_db({models.User: ea_user(status="locked")}))
            assert c.post("/api/auth/change-password", json=body).status_code == 401
        wrong = ea_auth_service(claims={"user_id": "uid-1"}, verify_password=False)
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: wrong):
            c = ea_client(ea_db({models.User: ea_user()}))
            assert c.post("/api/auth/change-password", json=body).status_code == 401
        notfound = ea_auth_service(claims={"user_id": "x"})
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: notfound):
            assert ea_client(ea_db({models.User: None})).post(
                "/api/auth/change-password", json=body).status_code == 404
        badtok = ea_auth_service(claims=None)
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: badtok):
            assert ea_client(ea_db()).post(
                "/api/auth/change-password", json=body).status_code == 401
        boom = ea_auth_service(claims={"user_id": "uid-1"})
        boom.verify_password.side_effect = RuntimeError("x")
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: boom):
            assert ea_client(ea_db({models.User: ea_user()})).post(
                "/api/auth/change-password", json=body).status_code == 500

    def test_test_auth_endpoint(self):
        svc = ea_auth_service(claims={"user_id": "uid-1", "roles": ["member"]})
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc):
            r = ea_client(ea_db()).get("/api/auth/test-auth")
        assert r.status_code == 200 and r.json()["user"]["user_id"] == "uid-1"

    def test_require_role_and_permission(self):
        async def handler(user):
            return {"ok": True, "user": user}

        role_ok = ea.require_role(["admin"])(handler)
        assert asyncio.run(role_ok({"roles": ["admin"]}))["ok"] is True
        with pytest.raises(Exception):
            asyncio.run(role_ok({"roles": ["member"]}))

        perm_ok = ea.require_permission("read")(handler)
        assert asyncio.run(perm_ok({"permissions": ["read"]}))["ok"] is True
        assert asyncio.run(perm_ok({"permissions": ["all"]}))["ok"] is True
        with pytest.raises(Exception):
            asyncio.run(perm_ok({"permissions": ["write"]}))

    def test_verify_enterprise_credentials_new(self):
        svc = MagicMock()
        creds = SimpleNamespace(user_id="u", username="n", email="e", roles=["r"],
                                security_level="s", permissions=["p"])
        svc.verify_credentials.return_value = creds
        db = MagicMock()

        def gen():
            yield db

        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc), \
             patch("core.database.get_db", gen):
            out = asyncio.run(ea._verify_enterprise_credentials_new("u", "p"))
        assert out["user_id"] == "u" and db.close.called

        svc2 = MagicMock()
        svc2.verify_credentials.return_value = None
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc2), \
             patch("core.database.get_db", gen):
            assert asyncio.run(ea._verify_enterprise_credentials("u", "p")) is None

        svc3 = MagicMock()
        svc3.verify_credentials.side_effect = RuntimeError("boom")
        with patch("core.enterprise_auth_service.EnterpriseAuthService", lambda: svc3), \
             patch("core.database.get_db", gen):
            assert asyncio.run(ea._verify_enterprise_credentials_new("u", "p")) is None


# ============================================================================
# Workflow debugging routes
# ============================================================================
def wd_session(**kw):
    base = dict(id="s1", workflow_id="wf1", execution_id="e1", user_id="u1",
                session_name="n", status="paused", current_step=1,
                current_node_id="n1", created_at=datetime(2026, 1, 1),
                updated_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


def wd_breakpoint(**kw):
    base = dict(id="b1", node_id="n1", edge_id=None, breakpoint_type="node",
                is_active=True, is_disabled=False, condition=None, hit_limit=None,
                hit_count=0, log_message=None, created_at=datetime(2026, 1, 1),
                workflow_id="wf1", debug_session_id=None, created_by="u1")
    base.update(kw)
    return SimpleNamespace(**base)


def wd_trace(**kw):
    base = dict(id="tr1", workflow_id="wf1", execution_id="e1", debug_session_id=None,
                step_number=1, node_id="n1", node_type="python", status="running",
                input_data={}, output_data={}, error_message=None,
                variable_changes={}, started_at=datetime(2026, 1, 1),
                completed_at=None, duration_ms=None)
    base.update(kw)
    return SimpleNamespace(**base)


def wd_variable(**kw):
    base = dict(id="v1", trace_id="tr1", variable_name="x", variable_path="x",
                variable_type="int", value=1, value_preview="1", is_mutable=True,
                scope="local", is_changed=False, previous_value=None,
                is_watch=False, watch_expression=None)
    base.update(kw)
    return SimpleNamespace(**base)


class TestWorkflowDebuggingRoutes:
    def test_create_session(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.create_debug_session.return_value = wd_session()
            r = make_client(wd).post("/api/workflows/wf1/debug/sessions", json={"workflow_id": "wf1"})
        assert r.status_code == 200 and r.json()["session_id"] == "s1"

    def test_create_session_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.create_debug_session.side_effect = RuntimeError("x")
            r = make_client(wd).post("/api/workflows/wf1/debug/sessions", json={"workflow_id": "wf1"})
        assert r.status_code == 500

    def test_get_sessions(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.get_active_debug_sessions.return_value = [
                wd_session(), wd_session(updated_at=datetime(2026, 1, 2))]
            r = make_client(wd).get("/api/workflows/wf1/debug/sessions")
        assert r.status_code == 200 and len(r.json()) == 2

    def test_get_sessions_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.get_active_debug_sessions.side_effect = RuntimeError("x")
            r = make_client(wd).get("/api/workflows/wf1/debug/sessions")
        assert r.status_code == 500

    @pytest.mark.parametrize("action,ok,path", [
        ("pause", True, "pause_debug_session"),
        ("pause", False, "pause_debug_session"),
        ("resume", True, "resume_debug_session"),
        ("resume", False, "resume_debug_session"),
        ("complete", True, "complete_debug_session"),
        ("complete", False, "complete_debug_session"),
    ])
    def test_session_lifecycle(self, action, ok, path):
        with patch.object(wd, "WorkflowDebugger") as cls:
            getattr(cls.return_value, path).return_value = ok
            r = make_client(wd).post(f"/api/workflows/debug/sessions/s1/{action}")
        assert r.status_code == (200 if ok else 404)

    def test_session_lifecycle_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.pause_debug_session.side_effect = RuntimeError("x")
            r = make_client(wd).post("/api/workflows/debug/sessions/s1/pause")
        assert r.status_code == 500

    def test_add_breakpoint(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.add_breakpoint.return_value = wd_breakpoint()
            r = make_client(wd).post("/api/workflows/wf1/debug/breakpoints",
                                     json={"workflow_id": "wf1", "node_id": "n1"})
        assert r.status_code == 200 and r.json()["breakpoint_id"] == "b1"

    def test_add_breakpoint_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.add_breakpoint.side_effect = RuntimeError("x")
            r = make_client(wd).post("/api/workflows/wf1/debug/breakpoints",
                                     json={"workflow_id": "wf1", "node_id": "n1"})
        assert r.status_code == 500

    def test_get_breakpoints(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.get_breakpoints.return_value = [wd_breakpoint()]
            r = make_client(wd).get("/api/workflows/wf1/debug/breakpoints?active_only=false")
        assert r.status_code == 200 and r.json()[0]["node_id"] == "n1"

    def test_get_breakpoints_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.get_breakpoints.side_effect = RuntimeError("x")
            r = make_client(wd).get("/api/workflows/wf1/debug/breakpoints")
        assert r.status_code == 500

    def test_remove_and_toggle_breakpoint(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.remove_breakpoint.return_value = True
            cls.return_value.toggle_breakpoint.return_value = False
            c = make_client(wd)
            assert c.delete("/api/workflows/debug/breakpoints/b1").status_code == 200
            r = c.put("/api/workflows/debug/breakpoints/b1/toggle")
            assert r.status_code == 200 and r.json()["is_disabled"] is True

    def test_remove_and_toggle_breakpoint_missing_and_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.remove_breakpoint.return_value = False
            cls.return_value.toggle_breakpoint.return_value = None
            c = make_client(wd)
            assert c.delete("/api/workflows/debug/breakpoints/b1").status_code == 404
            assert c.put("/api/workflows/debug/breakpoints/b1/toggle").status_code == 404
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.remove_breakpoint.side_effect = RuntimeError("x")
            cls.return_value.toggle_breakpoint.side_effect = RuntimeError("x")
            c = make_client(wd)
            assert c.delete("/api/workflows/debug/breakpoints/b1").status_code == 500
            assert c.put("/api/workflows/debug/breakpoints/b1/toggle").status_code == 500

    @pytest.mark.parametrize("action,method", [
        ("step_over", "step_over"), ("step_into", "step_into"),
        ("step_out", "step_out"), ("continue", "continue_execution"),
        ("pause", "pause_execution"),
    ])
    def test_step_execution_actions(self, action, method):
        with patch.object(wd, "WorkflowDebugger") as cls:
            getattr(cls.return_value, method).return_value = {"stepped": True}
            r = make_client(wd).post("/api/workflows/debug/step",
                                     json={"session_id": "s1", "action": action})
        assert r.status_code == 200 and r.json() == {"stepped": True}

    def test_step_execution_invalid_notfound_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            c = make_client(wd)
            r = c.post("/api/workflows/debug/step",
                       json={"session_id": "s1", "action": "bogus"})
            assert r.status_code == 422
            cls.return_value.step_over.return_value = None
            assert c.post("/api/workflows/debug/step",
                          json={"session_id": "s1", "action": "step_over"}).status_code == 404
            cls.return_value.step_over.side_effect = RuntimeError("x")
            assert c.post("/api/workflows/debug/step",
                          json={"session_id": "s1", "action": "step_over"}).status_code == 500

    def test_create_trace(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.create_trace.return_value = wd_trace()
            r = make_client(wd).post("/api/workflows/debug/traces", json={
                "workflow_id": "wf1", "execution_id": "e1", "step_number": 1,
                "node_id": "n1", "node_type": "python"})
        assert r.status_code == 200 and r.json()["trace_id"] == "tr1"

    def test_create_trace_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.create_trace.side_effect = RuntimeError("x")
            r = make_client(wd).post("/api/workflows/debug/traces", json={
                "workflow_id": "wf1", "execution_id": "e1", "step_number": 1,
                "node_id": "n1", "node_type": "python"})
        assert r.status_code == 500

    def test_complete_trace(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.complete_trace.return_value = True
            r = make_client(wd).put("/api/workflows/debug/traces/tr1/complete", json={})
        assert r.status_code == 200

    def test_complete_trace_missing_and_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.complete_trace.return_value = False
            assert make_client(wd).put(
                "/api/workflows/debug/traces/tr1/complete", json={}).status_code == 404
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.complete_trace.side_effect = RuntimeError("x")
            assert make_client(wd).put(
                "/api/workflows/debug/traces/tr1/complete", json={}).status_code == 500

    def test_get_execution_traces(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.get_execution_traces.return_value = [
                wd_trace(), wd_trace(completed_at=datetime(2026, 1, 2), duration_ms=5)]
            r = make_client(wd).get("/api/workflows/executions/e1/traces?limit=2")
        assert r.status_code == 200 and len(r.json()) == 2

    def test_get_execution_traces_error(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.get_execution_traces.side_effect = RuntimeError("x")
            r = make_client(wd).get("/api/workflows/executions/e1/traces")
        assert r.status_code == 500

    def test_get_variables(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.get_watch_variables.return_value = [wd_variable()]
            cls.return_value.get_variables_for_trace.return_value = [wd_variable()]
            c = make_client(wd)
            assert c.get("/api/workflows/debug/sessions/s1/variables").status_code == 200
            assert c.get("/api/workflows/debug/traces/tr1/variables").status_code == 200

    def test_get_variables_errors(self):
        with patch.object(wd, "WorkflowDebugger") as cls:
            cls.return_value.get_watch_variables.side_effect = RuntimeError("x")
            cls.return_value.get_variables_for_trace.side_effect = RuntimeError("x")
            c = make_client(wd)
            assert c.get("/api/workflows/debug/sessions/s1/variables").status_code == 500
            assert c.get("/api/workflows/debug/traces/tr1/variables").status_code == 500


# ============================================================================
# Mini-app routes
# ============================================================================
def ma_app(**kw):
    base = dict(id=f"app-{uuid.uuid4().hex[:8]}", tenant_id="t1", workspace_id="w1",
                created_by="u1", name="calc", description="d", version="1.0.0",
                manifest={"dependencies": [], "declared_scopes": []},
                blueprint_canvas_id="c1", status="draft", is_public=False,
                is_approved=False, share_token=None, runtime_image="img",
                runtime_version=1, created_at=datetime(2026, 1, 1))
    base.update(kw)
    return SimpleNamespace(**base)


def ma_canvas(**kw):
    base = dict(id="c1", tenant_id="t1", created_by="u1", mini_app_id=None)
    base.update(kw)
    return SimpleNamespace(**base)


def ma_db(firsts=None, alls=None):
    """Per-model mock db: query(Model).filter(...).first()/.all()."""
    firsts = firsts or {}
    alls = alls or {}
    db = MagicMock()

    def query(model, *a, **k):
        chain = MagicMock()
        filt = chain.filter.return_value
        filt.first.return_value = firsts.get(model)
        filt.all.return_value = alls.get(model, [])
        filt.count.return_value = 0
        filt.filter.return_value = filt
        filt.order_by.return_value.limit.return_value.all.return_value = alls.get(model, [])
        return chain

    db.query.side_effect = query
    return db


def ma_client(db):
    return make_client(ma, db=db)


class TestMiniAppCrud:
    def test_create_mini_app(self):
        import core.models as models
        import core.mini_app_service as svc
        db = ma_db()
        with patch.object(svc, "validate_manifest", MagicMock()):
            r = ma_client(db).post("/api/mini-apps", json={
                "name": "app", "manifest": {"x": 1}, "source_canvas_id": "c1"})
        assert r.status_code == 200 and db.add.called

    def test_create_mini_app_invalid_manifest(self):
        import core.mini_app_service as svc
        with patch.object(svc, "validate_manifest",
                          MagicMock(side_effect=ValueError("bad manifest"))):
            r = ma_client(ma_db()).post("/api/mini-apps", json={
                "name": "app", "manifest": {}})
        assert r.status_code == 400

    def test_scaffold_mini_app(self):
        import core.mini_app_service as svc
        app = ma_app()
        with patch.object(svc, "scaffold",
                          MagicMock(return_value=(app, "canvas-9"))):
            r = ma_client(ma_db()).post("/api/mini-apps/scaffold", json={"name": "n"})
        assert r.status_code == 200 and r.json()["canvas_id"] == "canvas-9"

    def test_save_logic(self):
        import core.models as models
        import core.mini_app_service as svc
        import core.canvas_logic_service as cls_
        db = ma_db({models.MiniApp: ma_app()})
        with patch.object(svc, "syntax_check", MagicMock()), \
             patch.object(cls_, "CanvasLogicService") as clc:
            clc.return_value.save_logic.return_value = None
            r = ma_client(db).post("/api/mini-apps/app-1/logic", json={"source": "x = 1"})
        assert r.status_code == 200 and clc.return_value.save_logic.called

    def test_save_logic_errors(self):
        import core.models as models
        import core.mini_app_service as svc
        db = ma_db({models.MiniApp: ma_app()})
        c = ma_client(db)
        # syntax error
        with patch.object(svc, "syntax_check",
                          MagicMock(side_effect=SyntaxError("bad token"))):
            assert c.post("/api/mini-apps/app-1/logic",
                          json={"source": "x"}).status_code == 400
        # no blueprint canvas
        app = ma_app(blueprint_canvas_id=None)
        db2 = ma_db({models.MiniApp: app})
        c2 = ma_client(db2)
        with patch.object(svc, "syntax_check", MagicMock()):
            assert c2.post("/api/mini-apps/app-1/logic",
                           json={"source": "x"}).status_code == 400
        # not owner
        db3 = ma_db({models.MiniApp: ma_app(created_by="other")})
        assert ma_client(db3).post(
            "/api/mini-apps/app-1/logic", json={"source": "x"}).status_code == 403
        # missing app
        assert ma_client(ma_db({models.MiniApp: None})).post(
            "/api/mini-apps/nope/logic", json={"source": "x"}).status_code == 404

    def test_dev_run(self):
        import core.models as models
        import core.mini_app_service as svc
        db = ma_db({models.MiniApp: ma_app()})
        with patch.object(svc, "prepare_runtime", MagicMock()), \
             patch.object(svc, "run_stateful",
                          AsyncMock(return_value={"success": True, "state": {"n": 1},
                                                  "proposed_ops": []})):
            r = ma_client(db).post("/api/mini-apps/app-1/dev-run", json={"inputs": {}})
        assert r.status_code == 200 and r.json()["state"] == {"n": 1}

    def test_dev_run_failure_and_guards(self):
        import core.models as models
        import core.mini_app_service as svc
        db = ma_db({models.MiniApp: ma_app()})
        with patch.object(svc, "prepare_runtime", MagicMock()), \
             patch.object(svc, "run_stateful",
                          AsyncMock(return_value={"success": False, "error": "boom"})):
            r = ma_client(db).post("/api/mini-apps/app-1/dev-run", json={})
        assert r.status_code == 500
        # no blueprint
        with patch.object(svc, "prepare_runtime", MagicMock()):
            r2 = ma_client(ma_db({models.MiniApp: ma_app(blueprint_canvas_id=None)})).post(
                "/api/mini-apps/app-1/dev-run", json={})
        assert r2.status_code == 400
        # not owner
        r3 = ma_client(ma_db({models.MiniApp: ma_app(created_by="other")})).post(
            "/api/mini-apps/app-1/dev-run", json={})
        assert r3.status_code == 403

    def test_list_mini_apps_with_query(self):
        import core.models as models
        db = ma_db(alls={models.MiniApp: [ma_app()]})
        r = ma_client(db).get("/api/mini-apps?q=calc")
        assert r.status_code == 200 and r.json()["apps"][0]["name"] == "calc"

    def test_get_mini_app(self):
        import core.models as models
        app = ma_app(id="app-1")
        r = ma_client(ma_db({models.MiniApp: app})).get("/api/mini-apps/app-1")
        assert r.status_code == 200 and r.json()["app"]["id"] == "app-1"
        assert ma_client(ma_db({models.MiniApp: None})).get(
            "/api/mini-apps/nope").status_code == 404

    def test_update_mini_app(self):
        import core.models as models
        import core.mini_app_service as svc
        app = ma_app(manifest={"dependencies": ["requests"]})
        db = ma_db({models.MiniApp: app})
        with patch.object(svc, "validate_manifest", MagicMock()):
            r = ma_client(db).put("/api/mini-apps/app-1", json={
                "name": "n2", "description": "d2", "version": "2.0.0",
                "manifest": {"dependencies": ["flask"]}})
        assert r.status_code == 200
        assert app.name == "n2" and app.runtime_image is None  # deps changed
        app2 = ma_app(manifest={"dependencies": ["requests"]})
        with patch.object(svc, "validate_manifest", MagicMock()):
            ma_client(ma_db({models.MiniApp: app2})).put(
                "/api/mini-apps/app-1", json={"manifest": {"dependencies": ["requests"]}})
        assert app2.runtime_image == "img"  # deps unchanged

    def test_update_mini_app_invalid_manifest(self):
        import core.models as models
        import core.mini_app_service as svc
        with patch.object(svc, "validate_manifest",
                          MagicMock(side_effect=ValueError("bad"))):
            r = ma_client(ma_db({models.MiniApp: ma_app()})).put(
                "/api/mini-apps/app-1", json={"manifest": {}})
        assert r.status_code == 400

    def test_publish_mini_app(self):
        import core.models as models
        import core.mini_app_service as svc
        db = ma_db({models.MiniApp: ma_app()})
        with patch.object(svc, "publish",
                          MagicMock(return_value={"success": True})):
            assert ma_client(db).post("/api/mini-apps/app-1/publish").status_code == 200
        with patch.object(svc, "publish",
                          MagicMock(side_effect=RuntimeError("rt"))):
            assert ma_client(db).post("/api/mini-apps/app-1/publish").status_code == 500
        with patch.object(svc, "publish",
                          MagicMock(side_effect=ValueError("ve"))):
            assert ma_client(db).post("/api/mini-apps/app-1/publish").status_code == 400

    def test_share_toggle(self):
        import core.models as models
        db = ma_db({models.MiniApp: ma_app()})
        c = ma_client(db)
        r = c.post("/api/mini-apps/app-1/share?public=true")
        assert r.status_code == 200 and r.json()["share_token"]
        r2 = c.post("/api/mini-apps/app-1/share?public=false")
        assert r2.json()["share_token"] is None

    def test_approve_requires_admin(self):
        import core.models as models
        db = ma_db({models.MiniApp: ma_app()})
        assert ma_client(db).post("/api/mini-apps/app-1/approve").status_code == 403
        admin = SimpleNamespace(id="u1", email="a@x.com", is_admin=True, is_staff=False)
        client = make_client(ma, db=ma_db({models.MiniApp: ma_app()}))
        client.app.dependency_overrides[get_current_user] = lambda: admin
        assert client.post("/api/mini-apps/app-1/approve").status_code == 200

    def test_install_by_share_token(self):
        import core.models as models
        import core.mini_app_service as svc
        good = ma_app(is_public=True, is_approved=True, share_token="tok123")
        db = ma_db({models.MiniApp: good})
        with patch.object(svc, "install", MagicMock(return_value="c-inst")):
            r = ma_client(db).post("/api/mini-apps/by-token/tok123/install")
        assert r.status_code == 200 and r.json()["canvas_id"] == "c-inst"
        with patch.object(svc, "install",
                          MagicMock(side_effect=ValueError("bad"))):
            assert ma_client(db).post(
                "/api/mini-apps/by-token/tok123/install").status_code == 400
        assert ma_client(ma_db({models.MiniApp: None})).post(
            "/api/mini-apps/by-token/none/install").status_code == 404
        notpub = ma_app(is_public=False, share_token="tok123")
        assert ma_client(ma_db({models.MiniApp: notpub})).post(
            "/api/mini-apps/by-token/tok123/install").status_code == 404
        pending = ma_app(is_public=True, is_approved=False, share_token="tok123")
        assert ma_client(ma_db({models.MiniApp: pending})).post(
            "/api/mini-apps/by-token/tok123/install").status_code == 403

    def test_install_mini_app(self):
        import core.models as models
        import core.mini_app_service as svc
        with patch.object(svc, "install", MagicMock(return_value="c-inst")):
            c = ma_client(ma_db({models.MiniApp: ma_app()}))
            assert c.post("/api/mini-apps/app-1/install").status_code == 200  # owner
        pending = ma_app(is_public=True, is_approved=False, created_by="other")
        assert ma_client(ma_db({models.MiniApp: pending})).post(
            "/api/mini-apps/app-1/install").status_code == 403
        private = ma_app(created_by="other")
        assert ma_client(ma_db({models.MiniApp: private})).post(
            "/api/mini-apps/app-1/install").status_code == 403
        with patch.object(svc, "install",
                          MagicMock(side_effect=ValueError("bad"))):
            assert ma_client(ma_db({models.MiniApp: ma_app()})).post(
                "/api/mini-apps/app-1/install").status_code == 400

    def test_update_check(self):
        import core.models as models
        canvas = ma_canvas(mini_app_id="app-1")
        inst = SimpleNamespace(canvas_id="c1", app_id="app-1",
                               installed_version="1.0.0", installed_runtime_version=1)
        db = ma_db({models.Canvas: canvas, models.MiniAppInstallation: inst,
                    models.MiniApp: ma_app(version="2.0.0")})
        r = ma_client(db).get("/api/mini-apps/instances/c1/update-check")
        assert r.json()["update_available"] is True
        db2 = ma_db({models.Canvas: canvas, models.MiniAppInstallation: None})
        assert ma_client(db2).get(
            "/api/mini-apps/instances/c1/update-check").json()["reason"] == "no_installation_record"
        db3 = ma_db({models.Canvas: canvas, models.MiniAppInstallation: inst,
                     models.MiniApp: None})
        assert ma_client(db3).get(
            "/api/mini-apps/instances/c1/update-check").json()["reason"] == "app_deleted"


class TestMiniAppAssets:
    def _db(self, asset=None):
        import core.models as models
        return ma_db({models.Canvas: ma_canvas(mini_app_id="app-1"),
                      models.MiniApp: ma_app(), models.MiniAppAsset: asset})

    def test_upload_asset(self):
        storage = MagicMock()
        storage.store.return_value = "file:///tmp/x"
        with patch.object(ma, "get_mini_app_storage", lambda *a: storage):
            r = ma_client(self._db()).post(
                "/api/mini-apps/instances/c1/assets",
                data={"key": "logo.png"}, files={"file": ("l.png", b"data", "image/png")})
        assert r.status_code == 200 and r.json()["uri"].startswith("file://")

    def test_upload_asset_overwrites_row(self):
        import core.models as models
        row = SimpleNamespace(uri="old", content_type=None, size=0)
        storage = MagicMock()
        storage.store.return_value = "file:///new"
        db = self._db(asset=row)
        with patch.object(ma, "get_mini_app_storage", lambda *a: storage):
            r = ma_client(db).post(
                "/api/mini-apps/instances/c1/assets",
                data={"key": "logo.png"}, files={"file": ("l.png", b"data2", "image/png")})
        assert r.status_code == 200 and row.uri == "file:///new"

    def test_upload_asset_guards(self):
        import core.models as models
        c = ma_client(self._db())
        with patch.object(ma, "get_max_object_bytes", lambda: 2):
            r = c.post("/api/mini-apps/instances/c1/assets",
                       data={"key": "k"}, files={"file": ("f", b"toolarge", "text/plain")})
        assert r.status_code == 413
        import core.mini_app_storage as mstorage
        with patch.object(mstorage, "validate_key",
                          MagicMock(side_effect=ValueError("bad key"))):
            r = c.post("/api/mini-apps/instances/c1/assets",
                       data={"key": "k"}, files={"file": ("f", b"ok", "text/plain")})
        assert r.status_code == 400
        # non-owner of a public app instance cannot write
        stranger = SimpleNamespace(id="stranger", email="s@x.com")
        client = make_client(ma, db=self._db())
        client.app.dependency_overrides[get_current_user] = lambda: stranger
        r = client.post("/api/mini-apps/instances/c1/assets",
                        data={"key": "k"}, files={"file": ("f", b"ok", "text/plain")})
        assert r.status_code == 403

    def test_list_and_download_assets(self):
        import core.models as models
        row = SimpleNamespace(key="k", uri="file:///u", content_type="text/plain",
                              size=3, created_at=datetime(2026, 1, 1))
        storage = MagicMock()
        storage.retrieve.return_value = b"abc"
        db = ma_db({models.Canvas: ma_canvas(mini_app_id="app-1"),
                    models.MiniApp: ma_app(), models.MiniAppAsset: row},
                   alls={models.MiniAppAsset: [row]})
        with patch.object(ma, "get_mini_app_storage", lambda *a: storage):
            c = ma_client(db)
            assert c.get("/api/mini-apps/instances/c1/assets").json()["assets"][0]["key"] == "k"
            r = c.get("/api/mini-apps/instances/c1/assets/k")
            assert r.status_code == 200 and r.content == b"abc"
        storage.retrieve.return_value = None
        with patch.object(ma, "get_mini_app_storage", lambda *a: storage):
            assert ma_client(db).get(
                "/api/mini-apps/instances/c1/assets/k").status_code == 404

    def test_delete_asset(self):
        row = SimpleNamespace(key="k")
        storage = MagicMock()
        storage.delete.return_value = True
        db = self._db(asset=row)
        with patch.object(ma, "get_mini_app_storage", lambda *a: storage):
            assert ma_client(db).delete("/api/mini-apps/instances/c1/assets/k").status_code == 200
        # non-owner denied
        stranger = SimpleNamespace(id="stranger", email="s@x.com")
        client = make_client(ma, db=db)
        client.app.dependency_overrides[get_current_user] = lambda: stranger
        with patch.object(ma, "get_mini_app_storage", lambda *a: storage):
            assert client.delete("/api/mini-apps/instances/c1/assets/k").status_code == 403


class TestMiniAppRecords:
    def _db(self, app=None, inst=None):
        import core.models as models
        return ma_db({models.Canvas: ma_canvas(mini_app_id="app-1"),
                      models.MiniApp: app or ma_app(),
                      models.MiniAppInstallation: inst,
                      models.MiniAppAsset: None})

    def test_series_list_query_count(self):
        import core.mini_app_db_service as dbs
        db = self._db()
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "list_series", MagicMock(return_value=["s1"])), \
             patch.object(dbs, "query_records", MagicMock(return_value=[{"id": "r1"}])), \
             patch.object(dbs, "count_records", MagicMock(return_value=7)):
            c = ma_client(db)
            assert c.get("/api/mini-apps/instances/c1/records/series").json()["series"] == ["s1"]
            r = c.get("/api/mini-apps/instances/c1/records?series=s1&order=asc")
            assert r.json()["count"] == 1
            assert c.get("/api/mini-apps/instances/c1/records?series=s1&order=bad").status_code == 400
            assert c.get("/api/mini-apps/instances/c1/records?series=BAD").status_code == 400
            r2 = c.post("/api/mini-apps/instances/c1/records/count", json={"series": "s1"})
            assert r2.json()["count"] == 7
            r3 = c.post("/api/mini-apps/instances/c1/records/count",
                        json={"filter": {"a": 1}})
            assert r3.json()["count"] == 7
            assert c.post("/api/mini-apps/instances/c1/records/count",
                          json={"filter": {"a": [1]}}).status_code == 400
            assert c.post("/api/mini-apps/instances/c1/records/query",
                          json={"series": "s1", "order": "bad"}).status_code == 400
            assert c.post("/api/mini-apps/instances/c1/records/query",
                          json={"series": "s1", "filter": {"a": [1]}}).status_code == 400
            assert c.post("/api/mini-apps/instances/c1/records/query",
                          json={"series": "s1"}).status_code == 200

    def test_get_record(self):
        import core.mini_app_db_service as dbs
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "get_record", MagicMock(return_value={"id": "r1"})):
            assert ma_client(self._db()).get(
                "/api/mini-apps/instances/c1/records/r1?series=s1").status_code == 200
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "get_record", MagicMock(return_value=None)):
            assert ma_client(self._db()).get(
                "/api/mini-apps/instances/c1/records/r1?series=s1").status_code == 404

    def test_append_record(self):
        import core.mini_app_db_service as dbs
        row = {"id": "r1", "data": {"n": 1}}
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "validate_record_data", lambda d, m: True), \
             patch.object(dbs, "append_record", MagicMock(return_value=row)):
            r = ma_client(self._db()).post("/api/mini-apps/instances/c1/records",
                                           json={"series": "s1", "data": {"n": 1}})
        assert r.status_code == 200 and r.json()["record"] == row
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "validate_record_data", lambda d, m: True), \
             patch.object(dbs, "append_record", MagicMock(side_effect=ValueError("cap"))):
            assert ma_client(self._db()).post(
                "/api/mini-apps/instances/c1/records",
                json={"series": "s1", "data": {}}).status_code == 400
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "validate_record_data", lambda d, m: False):
            assert ma_client(self._db()).post(
                "/api/mini-apps/instances/c1/records",
                json={"series": "s1", "data": {}}).status_code == 400
        # manifest disables db
        app = ma_app(manifest={"dependencies": [], "db": {"enabled": False}})
        with patch.object(ma, "db_store_enabled", lambda: True):
            assert ma_client(self._db(app=app)).post(
                "/api/mini-apps/instances/c1/records",
                json={"series": "s1", "data": {}}).status_code == 503

    def test_update_record(self):
        import core.mini_app_db_service as dbs
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "validate_record_data", lambda d, m: True), \
             patch.object(dbs, "update_record", MagicMock(return_value={"id": "r1"})):
            r = ma_client(self._db()).put(
                "/api/mini-apps/instances/c1/records/r1",
                json={"series": "s1", "data": {"n": 2}})
        assert r.status_code == 200
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "validate_record_data", lambda d, m: True), \
             patch.object(dbs, "update_record", MagicMock(return_value=None)):
            assert ma_client(self._db()).put(
                "/api/mini-apps/instances/c1/records/r1",
                json={"series": "s1", "data": {}}).status_code == 404
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "validate_record_data", lambda d, m: True), \
             patch.object(dbs, "update_record", MagicMock(side_effect=ValueError("size"))):
            assert ma_client(self._db()).put(
                "/api/mini-apps/instances/c1/records/r1",
                json={"series": "s1", "data": {}}).status_code == 400

    def test_delete_record_and_series(self):
        import core.mini_app_db_service as dbs
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "delete_record", MagicMock(return_value=True)), \
             patch.object(dbs, "delete_series", MagicMock(return_value=3)):
            c = ma_client(self._db())
            assert c.delete("/api/mini-apps/instances/c1/records/r1?series=s1").status_code == 200
            r = c.delete("/api/mini-apps/instances/c1/records?series=s1")
            assert r.json()["deleted"] == 3
        with patch.object(ma, "db_store_enabled", lambda: True), \
             patch.object(dbs, "delete_record", MagicMock(return_value=False)):
            assert ma_client(self._db()).delete(
                "/api/mini-apps/instances/c1/records/r1?series=s1").status_code == 404

    def test_db_disabled_kill_switch(self):
        import core.mini_app_db_service as dbs
        with patch.object(ma, "db_store_enabled", lambda: False):
            c = ma_client(self._db())
            assert c.get("/api/mini-apps/instances/c1/records/series").status_code == 503
            assert c.get("/api/mini-apps/instances/c1/records?series=s1").status_code == 503
            assert c.post("/api/mini-apps/instances/c1/records",
                          json={"series": "s1", "data": {}}).status_code == 503

    def test_instance_canvas_guards(self):
        import core.models as models
        # canvas missing
        assert ma_client(ma_db({models.Canvas: None})).get(
            "/api/mini-apps/instances/c9/records/series").status_code == 404
        # canvas without mini_app_id
        assert ma_client(ma_db({models.Canvas: ma_canvas(mini_app_id=None)})).get(
            "/api/mini-apps/instances/c1/records/series").status_code == 404
        # stranger on a private instance
        stranger = SimpleNamespace(id="stranger", email="s@x.com")
        client = make_client(ma, db=ma_db({models.Canvas: ma_canvas(mini_app_id="app-1"),
                                           models.MiniApp: ma_app(is_public=False)}))
        client.app.dependency_overrides[get_current_user] = lambda: stranger
        import core.mini_app_db_service as dbs
        with patch.object(ma, "db_store_enabled", lambda: True):
            assert client.get("/api/mini-apps/instances/c1/records/series").status_code == 403
        # non-owner mutation on a public instance
        pub_client = make_client(ma, db=ma_db({models.Canvas: ma_canvas(mini_app_id="app-1"),
                                               models.MiniApp: ma_app(is_public=True)}))
        pub_client.app.dependency_overrides[get_current_user] = lambda: stranger
        with patch.object(ma, "db_store_enabled", lambda: True):
            assert pub_client.post("/api/mini-apps/instances/c1/records",
                                   json={"series": "s1", "data": {}}).status_code == 403
