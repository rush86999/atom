"""Coverage wave 43 — core/byok_endpoints BYOKManager (24% → 90%+).

- AddAPIKeyRequest key_name validation
- AIProviderConfig post_init defaults, ProviderUsage/APIKey dataclasses
- _atomic_write_json (success + failure cleanup)
- _normalize_key_part variants
- encrypt/decrypt roundtrip, _get_fernet failure raises (no silent rotation)
- store_api_key (unknown provider raises, normalize parts, persisted)
- get_api_key (stored, env fallback + auto-store, missing, decrypt failure)
- track_usage (new/known, success cost, failure)
- get_optimal_provider (none, cost-sort, budget filter, reasoning fallback,
  deepseek/openai last-ditch, high-reasoning raise)
- get_provider_status (missing raises, active/inactive)
- is_configured / get_tenant_api_key aliases
"""
import hashlib
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest

import core.byok_endpoints as be


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(be, "BYOK_CONFIG_FILE", str(tmp_path / "cfg.json"))
    monkeypatch.setattr(be, "BYOK_KEYS_FILE", str(tmp_path / "keys.json"))
    monkeypatch.setattr(be, "BYOK_ENC_KEY_FILE", str(tmp_path / "enc.key"))
    m = be.BYOKManager()
    m.encryption_key = be.BYOKManager()._generate_encryption_key()
    return m


class TestModels:
    def test_add_api_key_request_valid(self):
        req = be.AddAPIKeyRequest(api_key="sk-abcdefghij", key_name="prod_key1")
        assert req.key_name == "prod_key1"

    def test_add_api_key_request_invalid_name(self):
        with pytest.raises(Exception):
            be.AddAPIKeyRequest(api_key="sk-abcdefghij", key_name="bad name!")

    def test_provider_config_defaults(self):
        p = be.AIProviderConfig(id="x", name="X", description="d", api_key_env_var="X_KEY")
        assert p.supported_tasks == []
        assert p.requires_encryption is True

    def test_provider_usage_defaults(self):
        u = be.ProviderUsage(provider_id="x")
        assert u.total_requests == 0
        assert u.cost_accumulated == 0.0

    def test_api_key_defaults(self):
        k = be.APIKey(
            provider_id="x", key_name="d", encrypted_key="e", key_hash="h",
            created_at=datetime.now(),
        )
        assert k.is_active is True
        assert k.environment == "production"


class TestFileOps:
    def test_atomic_write_and_cleanup(self, tmp_path):
        target = tmp_path / "f.json"
        be.BYOKManager._atomic_write_json(str(target), {"a": 1})
        assert target.exists()

        with patch("os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError):
                be.BYOKManager._atomic_write_json(str(target), {"b": 2})
        # temp file cleaned up
        leftovers = [p for p in os.listdir(tmp_path) if p.startswith(".tmp_")]
        assert leftovers == []


class TestNormalize:
    @pytest.mark.parametrize("value,expected", [
        (None, "default"),
        ("", "default"),
        ("   ", "default"),
        ("prod", "prod"),
        (42, "42"),
        (True, "True"),
    ])
    def test_variants(self, value, expected):
        assert be.BYOKManager._normalize_key_part(value, "default") == expected

    def test_invalid_type_warns(self):
        assert be.BYOKManager._normalize_key_part([], "default") == "default"


class TestCrypto:
    def test_roundtrip(self, manager):
        encrypted = manager.encrypt_api_key("sk-secret-123")
        assert encrypted != "sk-secret-123"
        assert manager.decrypt_api_key(encrypted) == "sk-secret-123"

    def test_invalid_fernet_raises(self, manager):
        manager.encryption_key = "not-a-valid-key"
        with pytest.raises(Exception):
            manager.encrypt_api_key("x")


class TestStoreAndGet:
    def test_store_unknown_provider_raises(self, manager):
        with pytest.raises(ValueError):
            manager.store_api_key("nope", "sk-abcdefghij")

    def test_store_and_get_roundtrip(self, manager):
        key_id = manager.store_api_key("openai", "sk-abcdefghij", "prod", "prod")
        assert key_id == "openai_prod_prod"
        assert manager.get_api_key("openai", "prod", "prod") == "sk-abcdefghij"
        # usage counter on the key object bumped
        assert manager.api_keys["openai_prod_prod"].usage_count == 1

    def test_get_env_fallback_autostores(self, manager, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key-123")
        key = manager.get_api_key("openai")
        assert key == "sk-env-key-123"
        assert "openai_default_production" in manager.api_keys

    def test_get_missing_returns_none(self, manager, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert manager.get_api_key("openai") is None

    def test_get_decrypt_failure_returns_none(self, manager):
        manager.store_api_key("openai", "sk-abcdefghij")
        manager.api_keys["openai_default_production"].encrypted_key = "garbage"
        assert manager.get_api_key("openai") is None


class TestUsage:
    def test_track_new_and_known(self, manager):
        manager.track_usage("openai", success=True, tokens_used=100)
        manager.track_usage("openai", success=False, tokens_used=50)
        usage = manager.usage_stats["openai"]
        assert usage.total_requests == 2
        assert usage.successful_requests == 1
        assert usage.failed_requests == 1
        assert usage.total_tokens_used == 100
        # cost = tokens * provider cost_per_token (openai default > 0)
        assert usage.cost_accumulated > 0

    def test_track_usage_with_cost(self, manager):
        manager.providers["openai"].cost_per_token = 0.01
        manager.track_usage("openai", success=True, tokens_used=10)
        assert manager.usage_stats["openai"].cost_accumulated == 0.1


class TestOptimalProvider:
    def _configure(self, manager, provider_id, tasks, cost, reasoning=1, active=True, key=True):
        p = be.AIProviderConfig(
            id=provider_id, name=provider_id, description="d",
            api_key_env_var=f"{provider_id.upper()}_KEY",
            supported_tasks=tasks, cost_per_token=cost,
            reasoning_level=reasoning, is_active=active,
        )
        manager.providers[provider_id] = p
        if key:
            manager.store_api_key(provider_id, f"sk-{provider_id}-key")

    def test_no_suitable_returns_none(self, manager):
        assert manager.get_optimal_provider("bogus_task") is None

    def test_cheapest_wins(self, manager):
        self._configure(manager, "deepseek", ["chat"], 0.1)
        self._configure(manager, "openai", ["chat"], 1.0)
        assert manager.get_optimal_provider("chat") == "deepseek"

    def test_reasoning_filter_and_budget(self, manager):
        self._configure(manager, "deepseek", ["chat"], 0.1, reasoning=1)
        self._configure(manager, "openai", ["chat"], 1.0, reasoning=4)
        # min_reasoning 4 → only openai
        assert manager.get_optimal_provider("chat", min_reasoning_level=4) == "openai"
        # budget below deepseek cost → none
        assert manager.get_optimal_provider("chat", budget_constraint=0.05) is None

    def test_high_reasoning_raises(self, manager):
        self._configure(manager, "openai", ["chat"], 1.0, reasoning=2)
        with pytest.raises(ValueError):
            manager.get_optimal_provider("chat", min_reasoning_level=4)

    def test_last_ditch_fallback(self, manager):
        # no provider supports the task, but deepseek has keys
        self._configure(manager, "deepseek", ["other"], 0.1)
        assert manager.get_optimal_provider("chat") == "deepseek"


class TestStatusAndAliases:
    def test_status_missing_raises(self, manager):
        with pytest.raises(ValueError):
            manager.get_provider_status("nope")

    def test_status_active(self, manager):
        manager.store_api_key("openai", "sk-abcdefghij")
        status = manager.get_provider_status("openai")
        assert status["status"] == "active"
        assert status["has_api_keys"] is True

    def test_status_inactive_without_key(self, manager):
        status = manager.get_provider_status("openai")
        assert status["status"] == "inactive"

    def test_aliases(self, manager):
        manager.store_api_key("openai", "sk-abcdefghij", key_name="ws-1")
        assert manager.is_configured("ws-1", "openai") is True
        assert manager.get_tenant_api_key("ws-1", "openai") == "sk-abcdefghij"


class TestConfigPersistence:
    def test_save_and_reload(self, tmp_path, monkeypatch):
        monkeypatch.setattr(be, "BYOK_CONFIG_FILE", str(tmp_path / "cfg.json"))
        monkeypatch.setattr(be, "BYOK_KEYS_FILE", str(tmp_path / "keys.json"))
        monkeypatch.setattr(be, "BYOK_ENC_KEY_FILE", str(tmp_path / "enc.key"))
        m1 = be.BYOKManager()
        m1.encryption_key = be.BYOKManager()._generate_encryption_key()
        m1.store_api_key("openai", "sk-abcdefghij")
        m2 = be.BYOKManager()
        m2.encryption_key = m1.encryption_key
        assert m2.get_api_key("openai") == "sk-abcdefghij"

    def test_corrupt_config_tolerated(self, tmp_path, monkeypatch):
        cfg = tmp_path / "cfg.json"
        cfg.write_text("{not json")
        monkeypatch.setattr(be, "BYOK_CONFIG_FILE", str(cfg))
        monkeypatch.setattr(be, "BYOK_KEYS_FILE", str(tmp_path / "keys.json"))
        monkeypatch.setattr(be, "BYOK_ENC_KEY_FILE", str(tmp_path / "enc.key"))
        m = be.BYOKManager()
        assert isinstance(m.providers, dict)
