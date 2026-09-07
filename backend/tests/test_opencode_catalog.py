"""OpenCode / OpenCode Go must be first-class API Keys page providers.

The BYOK handler has routed provider id "opencode-go" (env OPENCODE_API_KEY,
Zen gateway) with quota accounting and model maps since the OpenCode Go
integration — but neither provider catalog listed it, so the API Keys page
had no card for it and store_tenant_api_key raised ValueError for those
ids. These tests pin catalog presence in BOTH catalogs (the UI's
/api/ai/providers iterates api.byok_routes' manager; core.byok_endpoints
serves other surfaces), the storable-key path, and the handler client
base_url for the "opencode" alias (same gateway — without it a UI-stored
key would build a client against the OpenAI default URL).
"""
import os
os.environ.setdefault("TESTING", "1")

import pytest


def test_byok_routes_catalog_lists_opencode():
    from api.byok_routes import BYOKManager

    mgr = BYOKManager()
    for pid in ("opencode", "opencode-go"):
        assert pid in mgr.providers, f"{pid} missing from api.byok_routes catalog"
        cfg = mgr.providers[pid]
        assert cfg.api_key_env_var == "OPENCODE_API_KEY"
        assert (cfg.base_url or "").startswith("https://opencode.ai/zen/")


def test_byok_endpoints_catalog_lists_opencode():
    from core.byok_endpoints import BYOKManager as EndpointBYOKManager

    mgr = EndpointBYOKManager()
    for pid in ("opencode", "opencode-go"):
        assert pid in mgr.providers, f"{pid} missing from core.byok_endpoints catalog"


def test_status_and_store_accept_opencode_ids():
    """The API Keys page flow: status must not 404 and a stored key must
    register (the old catalog raised ValueError in store_tenant_api_key)."""
    from api.byok_routes import BYOKManager

    mgr = BYOKManager()
    for pid in ("opencode", "opencode-go"):
        status = mgr.get_tenant_provider_status("tenant_test", pid, db=None)
        assert status["has_api_keys"] is False  # nothing stored in test env

        key_id = mgr.store_tenant_api_key("tenant_test", pid, "sk-test-opencode-12345678")
        assert key_id
        assert mgr.get_tenant_api_key("tenant_test", pid, db=None) == "sk-test-opencode-12345678"

        status = mgr.get_tenant_provider_status("tenant_test", pid, db=None)
        assert status["has_api_keys"] is True
        assert status["status"] == "active"


def test_handler_builds_opencode_alias_client_with_zen_base_url(monkeypatch):
    """A key stored under provider id "opencode" must produce a client
    pointed at the Zen gateway, not the OpenAI default."""
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-test-opencode-12345678")
    from core.llm.byok_handler import BYOKHandler

    handler = BYOKHandler()
    client = handler.clients.get("opencode")
    assert client is not None, "opencode client should build from the env key"
    base = str(getattr(client, "base_url", ""))
    assert "opencode.ai/zen" in base
    assert "opencode-go" in handler.env_key_providers
    assert "opencode" in handler.env_key_providers
