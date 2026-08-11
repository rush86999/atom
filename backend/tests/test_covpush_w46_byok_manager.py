"""Coverage wave 46 — core/byok_endpoints.py BYOKManager internals (TDD).

Picks up from 59%. Targets the BYOKManager class methods that the API-level
suites never exercised:
- _load_or_create_encryption_key (file exists/empty/error/generate+persist)
- _get_fernet (valid key, empty key, invalid key fail-loud)
- encrypt/decrypt round-trip
- store_api_key (normalize, provider-missing ValueError, persistence)
- get_api_key (found+decrypt, env fallback, missing → None, decrypt failure)
- track_usage (new provider, success with cost, failure)
- get_optimal_provider (no keys → fallback deepseek/openai/None, reasoning
  raise, budget filter, cheapest sort)
- get_provider_status (active/inactive, missing → ValueError)
- _normalize_key_part (str/int/None/invalid-type)
- _atomic_write_json success + failure
"""
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from core.byok_endpoints import (
    AIProviderConfig,
    APIKey,
    BYOKManager,
)


def _manager(tmpdir, providers=None, keys=None, enc_key=None):
    """BYOKManager with isolated temp files (bypasses __init__ disk access)."""
    with patch("core.byok_endpoints.BYOK_CONFIG_FILE", f"{tmpdir}/config.json"), \
         patch("core.byok_endpoints.BYOK_KEYS_FILE", f"{tmpdir}/keys.json"), \
         patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", f"{tmpdir}/enc.key"), \
         patch("core.byok_endpoints.os.getenv",
               return_value=enc_key if enc_key is not None else None):
        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = providers or {}
        mgr.usage_stats = {}
        mgr.api_keys = keys or {}
        if enc_key:
            mgr.encryption_key = enc_key
        else:
            mgr.encryption_key = mgr._load_or_create_encryption_key()
        return mgr


def _provider(**kw):
    defaults = dict(
        id="p1", name="P1", description="d", api_key_env_var="TEST_KEY_ENV",
        base_url="https://x", model="m", cost_per_token=0.001,
        supported_tasks=["general"], reasoning_level=1, is_active=True,
    )
    defaults.update(kw)
    return AIProviderConfig(**defaults)


class TestEncryptionKey:
    def test_loads_existing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_file = f"{tmp}/enc.key"
            os.makedirs(tmp, exist_ok=True)
            with open(key_file, "w") as f:
                f.write("persisted-key")
            with patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", key_file):
                mgr = BYOKManager.__new__(BYOKManager)
                assert mgr._load_or_create_encryption_key() == "persisted-key"

    def test_empty_key_file_generates(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_file = f"{tmp}/enc.key"
            os.makedirs(tmp, exist_ok=True)
            with open(key_file, "w") as f:
                f.write("   ")
            with patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", key_file), \
                 patch.object(BYOKManager, "_generate_encryption_key",
                              return_value="gen-key"):
                mgr = BYOKManager.__new__(BYOKManager)
                key = mgr._load_or_create_encryption_key()
            assert key == "gen-key"
            assert open(key_file).read().strip() == "gen-key"

    def test_missing_key_generates_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_file = f"{tmp}/enc.key"
            with patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", key_file), \
                 patch.object(BYOKManager, "_generate_encryption_key",
                              return_value="brand-new"):
                mgr = BYOKManager.__new__(BYOKManager)
                key = mgr._load_or_create_encryption_key()
            assert key == "brand-new"
            assert os.path.exists(key_file)
            assert oct(os.stat(key_file).st_mode & 0o777) == "0o600"

    def test_read_error_generates(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_file = f"{tmp}/enc.key"
            os.makedirs(tmp, exist_ok=True)
            with open(key_file, "w") as f:
                f.write("x")
            with patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", key_file), \
                 patch("builtins.open", side_effect=RuntimeError("io error")), \
                 patch.object(BYOKManager, "_generate_encryption_key",
                              return_value="fallback-key"):
                mgr = BYOKManager.__new__(BYOKManager)
                key = mgr._load_or_create_encryption_key()
            assert key == "fallback-key"

    def test_persist_error_returns_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_file = f"{tmp}/enc.key"
            with patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", key_file), \
                 patch.object(BYOKManager, "_generate_encryption_key",
                              return_value="gen"), \
                 patch("os.makedirs", side_effect=RuntimeError("no perm")):
                mgr = BYOKManager.__new__(BYOKManager)
                assert mgr._load_or_create_encryption_key() == "gen"


class TestFernet:
    def test_get_fernet_valid(self):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        mgr = BYOKManager.__new__(BYOKManager)
        mgr.encryption_key = key
        assert mgr._get_fernet() is not None

    def test_get_fernet_empty_raises(self):
        mgr = BYOKManager.__new__(BYOKManager)
        mgr.encryption_key = None
        with pytest.raises(ValueError, match="empty"):
            mgr._get_fernet()

    def test_get_fernet_invalid_raises(self):
        mgr = BYOKManager.__new__(BYOKManager)
        mgr.encryption_key = "not-a-valid-fernet-key"
        with pytest.raises(Exception):
            mgr._get_fernet()

    def test_encrypt_decrypt_roundtrip(self):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        mgr = BYOKManager.__new__(BYOKManager)
        mgr.encryption_key = key
        encrypted = mgr.encrypt_api_key("secret-123")
        assert encrypted != "secret-123"
        assert mgr.decrypt_api_key(encrypted) == "secret-123"


class TestStoreGetApiKey:
    def test_store_and_get_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider()})
            key_id = mgr.store_api_key("p1", "my-secret")
            assert key_id == "p1_default_production"
            assert mgr.get_api_key("p1") == "my-secret"

    def test_store_provider_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={})
            with pytest.raises(ValueError, match="not found"):
                mgr.store_api_key("ghost", "key")

    def test_store_normalizes_key_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider()})
            key_id = mgr.store_api_key("p1", "k", key_name="  ", environment=None)
            assert key_id == "p1_default_production"

    def test_get_api_key_env_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider(api_key_env_var="MY_TEST_VAR")})
            with patch.dict(os.environ, {"MY_TEST_VAR": "env-key"}):
                assert mgr.get_api_key("p1") == "env-key"
            # stored for future use
            assert mgr.get_api_key("p1") == "env-key"

    def test_get_api_key_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider()})
            assert mgr.get_api_key("p1") is None

    def test_get_api_key_decrypt_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_obj = APIKey(
                provider_id="p1", key_name="default",
                encrypted_key="garbage-not-valid", key_hash="h",
                created_at=__import__("datetime").datetime.now(),
                environment="production")
            mgr = _manager(tmp, providers={"p1": _provider()},
                           keys={"p1_default_production": key_obj})
            assert mgr.get_api_key("p1") is None

    def test_get_api_key_updates_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            mgr = _manager(tmp, providers={"p1": _provider()}, enc_key=key)
            mgr.store_api_key("p1", "k")
            mgr.get_api_key("p1")
            assert mgr.api_keys["p1_default_production"].usage_count == 1
            assert mgr.api_keys["p1_default_production"].last_used is not None


class TestTrackUsage:
    def test_track_success_with_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider(cost_per_token=0.5)})
            mgr.track_usage("p1", success=True, tokens_used=10)
            usage = mgr.usage_stats["p1"]
            assert usage.total_requests == 1
            assert usage.successful_requests == 1
            assert usage.total_tokens_used == 10
            assert usage.cost_accumulated == 5.0

    def test_track_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider()})
            mgr.track_usage("p1", success=False)
            usage = mgr.usage_stats["p1"]
            assert usage.failed_requests == 1
            assert usage.total_requests == 1


class TestOptimalProvider:
    def test_returns_cheapest_with_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            mgr = _manager(tmp, providers={
                "cheap": _provider(id="cheap", cost_per_token=0.001,
                                   supported_tasks=["general"]),
                "pricey": _provider(id="pricey", cost_per_token=0.9,
                                    supported_tasks=["general"]),
            }, enc_key=key)
            for p in ("cheap", "pricey"):
                mgr.store_api_key(p, "k")
            assert mgr.get_optimal_provider("general") == "cheap"

    def test_no_suitable_falls_back_deepseek(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={})
            with patch.object(mgr, "get_api_key", side_effect=lambda pid: pid == "deepseek"):
                assert mgr.get_optimal_provider("general") == "deepseek"

    def test_no_suitable_falls_back_openai(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={})
            with patch.object(mgr, "get_api_key", side_effect=lambda pid: pid == "openai"):
                assert mgr.get_optimal_provider("general") == "openai"

    def test_no_suitable_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={})
            with patch.object(mgr, "get_api_key", return_value=None):
                assert mgr.get_optimal_provider("general") is None

    def test_high_reasoning_unavailable_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={})
            with patch.object(mgr, "get_api_key", return_value=None):
                with pytest.raises(ValueError, match="No high-reasoning"):
                    mgr.get_optimal_provider("general", min_reasoning_level=4)

    def test_budget_filter_excludes_expensive(self):
        with tempfile.TemporaryDirectory() as tmp:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            mgr = _manager(tmp, providers={
                "cheap": _provider(id="cheap", cost_per_token=0.001,
                                   supported_tasks=["general"]),
                "pricey": _provider(id="pricey", cost_per_token=0.9,
                                    supported_tasks=["general"]),
            }, enc_key=key)
            for p in ("cheap", "pricey"):
                mgr.store_api_key(p, "k")
            assert mgr.get_optimal_provider("general", budget_constraint=0.01) == "cheap"

    def test_reasoning_level_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            mgr = _manager(tmp, providers={
                "low": _provider(id="low", reasoning_level=1,
                                 supported_tasks=["general"]),
                "high": _provider(id="high", reasoning_level=4,
                                  supported_tasks=["general"]),
            }, enc_key=key)
            for p in ("low", "high"):
                mgr.store_api_key(p, "k")
            assert mgr.get_optimal_provider("general", min_reasoning_level=3) == "high"


class TestProviderStatus:
    def test_status_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            mgr = _manager(tmp, providers={"p1": _provider()}, enc_key=key)
            mgr.store_api_key("p1", "k")
            status = mgr.get_provider_status("p1")
            assert status["status"] == "active"
            assert status["has_api_keys"] is True

    def test_status_inactive_no_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider()})
            status = mgr.get_provider_status("p1")
            assert status["status"] == "inactive"
            assert status["has_api_keys"] is False

    def test_status_missing_provider_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={})
            with pytest.raises(ValueError, match="not found"):
                mgr.get_provider_status("ghost")


class TestNormalizeAndAtomic:
    def test_normalize_key_part(self):
        assert BYOKManager._normalize_key_part(None, "d") == "d"
        assert BYOKManager._normalize_key_part("  x  ", "d") == "x"
        assert BYOKManager._normalize_key_part("", "d") == "d"
        assert BYOKManager._normalize_key_part(5, "d") == "5"
        assert BYOKManager._normalize_key_part(True, "d") == "True"
        assert BYOKManager._normalize_key_part(["bad"], "d") == "d"

    def test_atomic_write_json_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/out.json"
            BYOKManager._atomic_write_json(path, {"a": 1})
            assert json.load(open(path)) == {"a": 1}

    def test_atomic_write_json_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/out.json"
            with patch("tempfile.mkstemp",
                       side_effect=RuntimeError("disk full")):
                with pytest.raises(RuntimeError, match="disk full"):
                    BYOKManager._atomic_write_json(path, {"a": 1})


class TestInitAndDefaults:
    def test_init_initializes_providers(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("core.byok_endpoints.BYOK_CONFIG_FILE", f"{tmp}/c.json"), \
                 patch("core.byok_endpoints.BYOK_KEYS_FILE", f"{tmp}/k.json"), \
                 patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", f"{tmp}/e.key"), \
                 patch("core.byok_endpoints.os.getenv", return_value=None):
                mgr = BYOKManager()
        assert "deepseek" in mgr.providers
        assert "openai" in mgr.providers
        assert mgr.encryption_key

    def test_initialize_default_providers_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp)
            mgr._initialize_default_providers()
            assert mgr.providers
            count = len(mgr.providers)
            mgr._initialize_default_providers()
            assert len(mgr.providers) == count  # no duplicates


class TestLoadConfiguration:
    def test_loads_providers_and_keys_from_disk(self):
        from cryptography.fernet import Fernet
        with tempfile.TemporaryDirectory() as tmp:
            key = Fernet.generate_key().decode()
            cfg = {"providers": [
                {"id": "p1", "name": "P1", "description": "d",
                 "api_key_env_var": "X", "base_url": "https://x",
                 "model": "m", "cost_per_token": 0.1,
                 "supported_tasks": ["general"],
                 "reasoning_level": 1, "is_active": True},
            ]}
            with open(f"{tmp}/config.json", "w") as f:
                json.dump(cfg, f)
            from core.byok_endpoints import APIKey
            keys = {"p1_k_e": {
                "provider_id": "p1", "key_name": "k", "environment": "e",
                "encrypted_key": "enc", "key_hash": "h",
                "created_at": "2026-01-01T00:00:00",
                "last_used": "2026-01-02T00:00:00",
                "usage_count": 3,
            }}
            with open(f"{tmp}/keys.json", "w") as f:
                json.dump({"keys": keys}, f)
            with patch("core.byok_endpoints.BYOK_CONFIG_FILE", f"{tmp}/config.json"), \
                 patch("core.byok_endpoints.BYOK_KEYS_FILE", f"{tmp}/keys.json"), \
                 patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", f"{tmp}/e.key"), \
                 patch("core.byok_endpoints.os.getenv", return_value=None):
                mgr = BYOKManager.__new__(BYOKManager)
                mgr.providers = {}
                mgr.api_keys = {}
                mgr.encryption_key = key
                mgr._load_configuration()
            assert mgr.providers["p1"].cost_per_token == 0.1
            assert "p1_k_e" in mgr.api_keys
            assert mgr.api_keys["p1_k_e"].usage_count == 3

    def test_load_configuration_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("core.byok_endpoints.BYOK_CONFIG_FILE", f"{tmp}/nope.json"), \
                 patch("core.byok_endpoints.BYOK_KEYS_FILE", f"{tmp}/nope2.json"), \
                 patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", f"{tmp}/e.key"), \
                 patch("core.byok_endpoints.os.getenv", return_value=None):
                mgr = BYOKManager.__new__(BYOKManager)
                mgr.providers = {}
                mgr.api_keys = {}
                mgr.encryption_key = "k"
                mgr._load_configuration()
            assert mgr.providers == {}
            assert mgr.api_keys == {}

    def test_load_configuration_corrupt_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(f"{tmp}/config.json", "w") as f:
                f.write("{not valid json")
            with open(f"{tmp}/keys.json", "w") as f:
                f.write("[[[")
            with patch("core.byok_endpoints.BYOK_CONFIG_FILE", f"{tmp}/config.json"), \
                 patch("core.byok_endpoints.BYOK_KEYS_FILE", f"{tmp}/keys.json"), \
                 patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", f"{tmp}/e.key"), \
                 patch("core.byok_endpoints.os.getenv", return_value=None), \
                 patch("core.byok_endpoints.logger") as mock_log:
                mgr = BYOKManager.__new__(BYOKManager)
                mgr.providers = {}
                mgr.api_keys = {}
                mgr.encryption_key = "k"
                mgr._load_configuration()
            assert mgr.providers == {}
            assert mgr.api_keys == {}

    def test_load_configuration_filters_unknown_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"providers": [
                {"id": "p1", "name": "P1", "description": "d",
                 "api_key_env_var": "X", "model": "m",
                 "cost_per_token": 0.1, "supported_tasks": ["general"],
                 "bogus_field": "should-be-dropped"},
            ]}
            with open(f"{tmp}/config.json", "w") as f:
                json.dump(cfg, f)
            with patch("core.byok_endpoints.BYOK_CONFIG_FILE", f"{tmp}/config.json"), \
                 patch("core.byok_endpoints.BYOK_KEYS_FILE", f"{tmp}/k.json"), \
                 patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", f"{tmp}/e.key"), \
                 patch("core.byok_endpoints.os.getenv", return_value=None):
                mgr = BYOKManager.__new__(BYOKManager)
                mgr.providers = {}
                mgr.api_keys = {}
                mgr.encryption_key = "k"
                mgr._load_configuration()
            assert "bogus_field" not in mgr.providers["p1"].__dict__


class TestUpdateProviderCosts:
    def test_updates_costs_from_fetcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider(model="m1")})
            fetcher = MagicMock()
            fetcher.get_model_price = MagicMock(
                return_value={"input_cost_per_token": 0.01,
                              "output_cost_per_token": 0.03})
            with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                       return_value=fetcher):
                mgr.update_provider_costs()
            assert mgr.providers["p1"].cost_per_token == 0.02

    def test_update_costs_no_pricing(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider(model="m1")})
            fetcher = MagicMock()
            fetcher.get_model_price = MagicMock(return_value=None)
            with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                       return_value=fetcher):
                mgr.update_provider_costs()
            assert mgr.providers["p1"].cost_per_token == 0.001  # unchanged

    def test_update_costs_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = _manager(tmp, providers={"p1": _provider(model="m1")})
            with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                       side_effect=RuntimeError("fetcher down")):
                with patch("core.byok_endpoints.logger") as mock_log:
                    mgr.update_provider_costs()
                mock_log.error.assert_called()
