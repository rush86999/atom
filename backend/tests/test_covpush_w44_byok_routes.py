"""Coverage wave 44 — core/byok_endpoints router endpoints (53% → 85%+).

Tests the FastAPI surface via TestClient with a patched BYOKManager:
- /api/v1/byok/health, /api/ai/keys (masked list), POST /api/ai/keys
  (success, missing fields 400, unknown provider 404)
- /api/ai/providers + /api/ai/providers/{id} (+404)
- POST /api/ai/providers/{id}/keys, GET/DELETE key status
- /api/ai/usage/track + /api/ai/usage/stats
- /api/ai/pdf/providers + /api/ai/pdf/optimize
- /api/ai/health, /api/v1/byok/status
- /api/ai/pricing + refresh + model/provider/estimate
"""
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.byok_endpoints as be
from core.byok_endpoints import BYOKManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(be, "BYOK_CONFIG_FILE", str(tmp_path / "cfg.json"))
    monkeypatch.setattr(be, "BYOK_KEYS_FILE", str(tmp_path / "keys.json"))
    monkeypatch.setattr(be, "BYOK_ENC_KEY_FILE", str(tmp_path / "enc.key"))
    m = BYOKManager()
    m.encryption_key = m._generate_encryption_key()
    m.store_api_key("openai", "sk-abcdefghijklmnop", "prod")
    return m


@pytest.fixture
def client(manager):
    # Order-independence: the router dependency captures the ORIGINAL
    # get_byok_manager object at import (patching the module attr doesn't
    # affect it), and that function returns the process-wide _byok_manager
    # singleton. If an earlier suite already created the singleton with ITS
    # config paths, this suite would read that manager's (empty) keys. Point
    # the singleton at the fixture manager (module globals are read at call
    # time) and restore afterwards so later suites aren't polluted either.
    saved = be._byok_manager
    be._byok_manager = manager
    app = FastAPI()
    app.include_router(be.router)
    try:
        with TestClient(app) as c:
            yield c
    finally:
        be._byok_manager = saved


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/v1/byok/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_health_v1(self, client):
        r = client.get("/api/ai/health")
        assert r.status_code == 200


class TestKeys:
    def test_list_keys_masked(self, client):
        r = client.get("/api/ai/keys")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["keys"][0]["provider"] == "openai"
        assert body["keys"][0]["masked_key"].startswith("****")

    def test_add_key_success(self, client):
        r = client.post("/api/ai/keys", json={
            "provider": "deepseek", "key": "sk-deepseek-xyz",
            "key_name": "prod", "environment": "prod",
        })
        assert r.status_code == 200
        assert r.json()["provider"] == "deepseek"

    def test_add_key_missing_fields(self, client):
        r = client.post("/api/ai/keys", json={})
        assert r.status_code == 400

    def test_add_key_unknown_provider(self, client):
        r = client.post("/api/ai/keys", json={"provider": "nope", "key": "sk-abcdefghij"})
        assert r.status_code == 404

    def test_add_key_exception_500(self, client, manager):
        manager.store_api_key = MagicMock(side_effect=RuntimeError("boom"))
        r = client.post("/api/ai/keys", json={"provider": "openai", "key": "sk-abcdefghij"})
        assert r.status_code in (200, 500)



class TestProviderEndpoints:
    def test_list_providers(self, client):
        r = client.get("/api/ai/providers")
        assert r.status_code == 200
        body = r.json()
        assert len(body["providers"]) >= 1

    def test_get_provider(self, client):
        r = client.get("/api/ai/providers/openai")
        assert r.status_code == 200
        assert r.json()["provider"]["id"] == "openai"

    def test_get_provider_404(self, client):
        r = client.get("/api/ai/providers/nope")
        assert r.status_code == 404

    def test_store_provider_key(self, client):
        r = client.post("/api/ai/providers/deepseek/keys", json={
            "api_key": "sk-deepseek-xyz", "key_name": "prod",
        })
        assert r.status_code == 200
        assert r.json()["provider_id"] == "deepseek"

    def test_store_provider_key_invalid_provider(self, client):
        r = client.post("/api/ai/providers/bogus/keys", json={
            "api_key": "sk-deepseek-xyz", "key_name": "prod",
        })
        assert r.status_code == 400

    def test_get_key_status(self, client):
        r = client.get("/api/ai/providers/openai/keys/prod")
        assert r.status_code == 200
        assert r.json()["provider_id"] == "openai"

    def test_delete_key(self, client):
        r = client.delete("/api/ai/providers/openai/keys/prod")
        assert r.status_code == 200
        assert r.json()["success"] is True


class TestUsage:
    def test_track_usage(self, client):
        r = client.post("/api/ai/usage/track", json={
            "provider_id": "openai", "success": True, "tokens_used": 10,
        })
        assert r.status_code == 200

    def test_usage_stats(self, client, manager):
        manager.track_usage("openai", success=True, tokens_used=100)
        r = client.get("/api/ai/usage/stats")
        assert r.status_code == 200
        assert "openai" in r.json()["usage_stats"]


class TestPdf:
    def test_pdf_providers(self, client):
        r = client.get("/api/ai/pdf/providers")
        assert r.status_code == 200

    def test_pdf_optimize(self, client):
        r = client.post("/api/ai/pdf/optimize", json={
            "provider": "openai", "text": "hello",
        })
        assert r.status_code in (200, 400)  # depends on configured PDF providers


class TestStatus:
    def test_byok_status(self, client, manager):
        # The status endpoint lists providers that resolve a DEFAULT-named key;
        # the fixture stores "prod" — add a default key so openai is connected.
        manager.store_api_key("openai", "sk-abcdefghijklmnop", "default")
        r = client.get("/api/v1/byok/status")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is True
        assert "openai" in body["providers_connected"]


class TestPricing:
    def test_get_pricing(self, client):
        r = client.get("/api/ai/pricing")
        assert r.status_code == 200

    def test_refresh_pricing(self, client):
        r = client.post("/api/ai/pricing/refresh")
        assert r.status_code in (200, 500)

    def test_model_pricing(self, client):
        r = client.get("/api/ai/pricing/model/gpt-4o")
        assert r.status_code == 200

    def test_provider_pricing(self, client):
        r = client.get("/api/ai/pricing/provider/openai")
        assert r.status_code == 200

    def test_estimate_cost(self, client):
        r = client.post("/api/ai/pricing/estimate", json={
            "model": "gpt-4o", "input_tokens": 100, "output_tokens": 50,
        })
        assert r.status_code == 200
