"""
Round 59 — BYOK encryption key not persisted: stored API keys brick on restart
(Red-Green-Refactor).

BYOKManager.__init__ uses `BYOK_ENCRYPTION_KEY` env var or generates a FRESH
random Fernet key. The generated key is never persisted — on every process
restart (deployments, daemon restarts) the new key cannot decrypt any
previously-stored API key: the BYOK system silently bricks and every
provider key must be re-entered. `_get_fernet` even swaps in a new key on
decrypt failure, corrupting the key state further.

Fix: persist the generated key next to the BYOK config (0600) and reuse it
on subsequent starts; env var still takes precedence.
"""

from unittest.mock import patch

import pytest


def _reset_singleton():
    import api.byok_routes as mod

    mod._byok_manager = None


def _tmp_paths(monkeypatch, tmp_path):
    import api.byok_routes as mod

    monkeypatch.setattr(mod, "BYOK_CONFIG_FILE", str(tmp_path / "byok_config.json"))
    monkeypatch.setattr(mod, "BYOK_KEYS_FILE", str(tmp_path / "byok_keys.json"))
    monkeypatch.setattr(mod, "BYOK_ENC_KEY_FILE", str(tmp_path / "byok_encryption_key"))
    monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
    _reset_singleton()


class TestByokEncryptionKeyPersistence:
    def test_manager_keeps_usage_stats_attribute(self, monkeypatch, tmp_path):
        """Guard: __init__ must keep all pre-existing attributes."""
        _tmp_paths(monkeypatch, tmp_path)

        from api.byok_routes import BYOKManager

        m = BYOKManager()
        assert hasattr(m, "usage_stats"), (
            "BYOKManager.__init__ lost the usage_stats attribute"
        )
        assert hasattr(m, "api_keys")

    def test_key_persists_across_manager_instances(self, monkeypatch, tmp_path):
        """Two manager instances (restart) must share one encryption key."""
        _tmp_paths(monkeypatch, tmp_path)

        from api.byok_routes import BYOKManager

        m1 = BYOKManager()
        key1 = m1.encryption_key

        _reset_singleton()
        m2 = BYOKManager()
        key2 = m2.encryption_key

        assert key1 == key2, (
            "BYOKManager generated a new encryption key on restart — stored "
            "API keys are undecryptable after every process restart"
        )

    def test_stored_key_decrypts_after_restart(self, monkeypatch, tmp_path):
        """An API key stored before a 'restart' must still decrypt after."""
        _tmp_paths(monkeypatch, tmp_path)

        from api.byok_routes import BYOKManager

        m1 = BYOKManager()
        key_id = m1.store_api_key("openai", "sk-secret-123", "default", "production")

        _reset_singleton()
        m2 = BYOKManager()
        decrypted = m2.decrypt_api_key(m2.api_keys[key_id].encrypted_key)

        assert decrypted == "sk-secret-123", (
            f"Stored BYOK key could not be decrypted after restart: {decrypted!r}"
        )

    def test_env_key_takes_precedence(self, monkeypatch, tmp_path):
        _tmp_paths(monkeypatch, tmp_path)
        monkeypatch.setenv("BYOK_ENCRYPTION_KEY", "test-fixed-key-123")

        from api.byok_routes import BYOKManager

        m = BYOKManager()
        assert m.encryption_key == "test-fixed-key-123", (
            "BYOK_ENCRYPTION_KEY env override ignored"
        )

    def test_generated_key_file_permissions(self, monkeypatch, tmp_path):
        _tmp_paths(monkeypatch, tmp_path)

        from api.byok_routes import BYOKManager

        BYOKManager()
        key_file = tmp_path / "byok_encryption_key"
        assert key_file.exists(), "generated encryption key was not persisted"
        mode = key_file.stat().st_mode & 0o777
        assert mode == 0o600, (
            f"persisted encryption key file has permissive mode {oct(mode)}"
        )
