"""
Round 62 — BYOK admin config load: unknown fields brick the whole store
(Red-Green-Refactor).

api/byok_routes.BYOKManager._load_configuration does `AIProviderConfig(**p_data)`
and `APIKey(**k_data)` with NO field filtering — a single unknown field in the
shared config/keys files (e.g. `tenant_id` written by the runtime manager, or
`supports_vision` from an older version) raises TypeError and the ENTIRE
provider/key store silently fails to load. The sibling manager
(core/byok_endpoints) filters to known dataclass fields; the admin manager
does not.

Fix: mirror the field-filtering pattern.
"""

import json


def _setup(monkeypatch, tmp_path):
    import api.byok_routes as mod

    config = tmp_path / "byok_config.json"
    keys = tmp_path / "byok_keys.json"
    monkeypatch.setattr(mod, "BYOK_CONFIG_FILE", str(config))
    monkeypatch.setattr(mod, "BYOK_KEYS_FILE", str(keys))
    monkeypatch.setattr(mod, "BYOK_ENC_KEY_FILE", str(tmp_path / "byok_encryption_key"))
    monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
    import api.byok_routes as m2

    m2._byok_manager = None
    return config, keys


class TestByokConfigForwardCompat:
    def test_provider_with_extra_fields_still_loads(self, monkeypatch, tmp_path):
        config, keys = _setup(monkeypatch, tmp_path)
        config.write_text(json.dumps({"providers": [{
            "id": "custom-provider-x",
            "name": "CustomX",
            "description": "Custom provider",
            "api_key_env_var": "CUSTOM_X_KEY",
            "base_url": "https://custom.example/v1",
            "model": "custom-model",
            "cost_per_token": 0.001,
            "supported_tasks": ["chat"],
            "max_requests_per_minute": 60,
            "rate_limit_window": 60,
            "is_active": True,
            "requires_encryption": True,
            "reasoning_level": "high",
            "supports_vision": True,  # unknown field from an older version
        }]}))
        keys.write_text(json.dumps({"keys": {}}))

        from api.byok_routes import BYOKManager

        m = BYOKManager()
        assert "custom-provider-x" in m.providers, (
            "a single unknown provider field bricked the whole config load"
        )
        assert m.providers["custom-provider-x"].name == "CustomX"

    def test_keys_with_extra_fields_still_load(self, monkeypatch, tmp_path):
        config, keys = _setup(monkeypatch, tmp_path)
        config.write_text(json.dumps({"providers": []}))
        from datetime import datetime

        keys.write_text(json.dumps({"keys": {
            "openai_default_production": {
                "provider_id": "openai",
                "key_name": "default",
                "encrypted_key": "gAAAAAxyz",
                "key_hash": "deadbeef",
                "created_at": datetime.utcnow().isoformat(),
                "last_used": None,
                "is_active": True,
                "usage_count": 0,
                "environment": "production",
                "tenant_id": "tenant-1",  # written by the runtime manager
                "rotation_count": 3,  # unknown field from a future version
            }
        }}))

        from api.byok_routes import BYOKManager

        m = BYOKManager()
        assert "openai_default_production" in m.api_keys, (
            "a single unknown key field bricked the whole keys load"
        )

    def test_both_managers_load_each_others_keys(self, monkeypatch, tmp_path):
        """The shared keys store must round-trip across both managers."""
        config, keys = _setup(monkeypatch, tmp_path)
        import core.byok_endpoints as core_mod

        monkeypatch.setattr(core_mod, "BYOK_CONFIG_FILE", str(config))
        monkeypatch.setattr(core_mod, "BYOK_KEYS_FILE", str(keys))
        monkeypatch.setattr(core_mod, "BYOK_ENC_KEY_FILE", str(tmp_path / "byok_encryption_key"))

        from api.byok_routes import BYOKManager as AdminManager

        admin = AdminManager()
        key_id = admin.store_api_key("openai", "sk-cross-111", "default", "production")

        # Runtime manager loads the file the admin manager wrote
        from core.byok_endpoints import BYOKManager as RuntimeManager

        runtime = RuntimeManager()
        assert key_id in runtime.api_keys, (
            "runtime manager could not load keys written by the admin manager"
        )
