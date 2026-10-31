"""A cached chat handler must see Settings-saved BYOK changes without restart."""
from __future__ import annotations

import os

import pytest

from core.byok_endpoints import BYOKManager
from core.llm_service import LLMService


@pytest.fixture()
def byok_world(tmp_path, monkeypatch):
    import core.byok_endpoints as endpoints

    keys = tmp_path / "byok_keys.json"
    config = tmp_path / "byok_config.json"
    enc = tmp_path / "byok_encryption_key"
    monkeypatch.setattr(endpoints, "BYOK_KEYS_FILE", str(keys))
    monkeypatch.setattr(endpoints, "BYOK_CONFIG_FILE", str(config))
    monkeypatch.setattr(endpoints, "BYOK_ENC_KEY_FILE", str(enc))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ATOM_LOCAL_ONLY", "false")
    manager = BYOKManager()
    monkeypatch.setattr(endpoints, "_byok_manager", manager)
    return manager


def _openai_key(handler):
    client = handler.clients.get("openai")
    return getattr(client, "api_key", None)


def test_cached_handler_sees_saved_replaced_and_removed_key(byok_world):
    manager = byok_world
    manager.store_api_key("openai", "sk-first-valid-key-123456")
    service = LLMService(workspace_id="default", tenant_id="default")

    first = service._get_handler()
    assert first is not None
    assert _openai_key(first) == "sk-first-valid-key-123456"

    # Settings replaces the key in the shared file. The same LLMService must
    # rebuild its client snapshot on the next request.
    manager.store_api_key("openai", "sk-second-valid-key-654321")
    assert first.credentials_changed() is True
    second = service._get_handler()
    assert second is not first
    assert _openai_key(second) == "sk-second-valid-key-654321"

    # Removal must remove the provider client too — no stale credential.
    manager.api_keys.pop("openai_default_production")
    manager._save_configuration()
    third = service._get_handler()
    assert third is not second
    assert "openai" not in third.clients


def test_credentials_changed_is_false_without_a_store_change(byok_world):
    manager = byok_world
    manager.store_api_key("openai", "sk-stable-valid-key-123456")
    service = LLMService(workspace_id="default", tenant_id="default")
    handler = service._get_handler()
    assert handler.credentials_changed() is False
    assert service._get_handler() is handler


def test_credential_change_clears_discovery_backoff(monkeypatch):
    from core.llm import byok_handler

    monkeypatch.setattr(
        byok_handler, "_DISCOVERY_REFRESH_ATTEMPTED_AT",
        {"openai": 123.0, "anthropic": 456.0}, raising=False)
    byok_handler.BYOKHandler.invalidate_provider_failures("openai")
    assert "openai" not in byok_handler._DISCOVERY_REFRESH_ATTEMPTED_AT
    assert "anthropic" in byok_handler._DISCOVERY_REFRESH_ATTEMPTED_AT

    byok_handler.BYOKHandler.invalidate_provider_failures(None)
    assert byok_handler._DISCOVERY_REFRESH_ATTEMPTED_AT == {}
