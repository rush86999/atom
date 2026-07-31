"""
Round 61 — Runtime BYOK manager: R59 key-persistence gap + silent key swap
(Red-Green-Refactor).

R59 fixed api/byok_routes.BYOKManager (the admin surface) but the RUNTIME
manager — core/byok_endpoints.BYOKManager, used by byok_handler for actual
LLM provider calls — still:

  A. generates a fresh Fernet key per process (never persisted): stored keys
     brick on every restart.
  B. worse, both managers are singletons in the SAME process with DIFFERENT
     keys — keys stored via the admin API can never be decrypted by the
     runtime (feature broken even without a restart).
  C. _get_fernet silently swaps in a new key on construction failure,
     corrupting the key state mid-process.

Fix: the runtime manager shares the same persisted key file
(BYOK_ENC_KEY_FILE) and no longer rotates keys on Fernet errors.
"""

from unittest.mock import patch

import pytest


def _reset_singletons():
    import api.byok_routes as api_mod
    import core.byok_endpoints as core_mod

    api_mod._byok_manager = None
    core_mod._byok_manager = None


def _tmp_paths(monkeypatch, tmp_path):
    import api.byok_routes as api_mod
    import core.byok_endpoints as core_mod

    for mod in (api_mod, core_mod):
        monkeypatch.setattr(mod, "BYOK_CONFIG_FILE", str(tmp_path / "byok_config.json"))
        monkeypatch.setattr(mod, "BYOK_KEYS_FILE", str(tmp_path / "byok_keys.json"))
        monkeypatch.setattr(mod, "BYOK_ENC_KEY_FILE", str(tmp_path / "byok_encryption_key"))
    monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
    _reset_singletons()


class TestRuntimeManagerKeyPersistence:
    def test_runtime_key_persists_across_instances(self, monkeypatch, tmp_path):
        """Runtime manager (restart) must reuse the persisted key."""
        _tmp_paths(monkeypatch, tmp_path)

        from core.byok_endpoints import BYOKManager

        m1 = BYOKManager()
        key1 = m1.encryption_key
        _reset_singletons()
        m2 = BYOKManager()
        assert key1 == m2.encryption_key, (
            "runtime BYOKManager generated a new encryption key on restart — "
            "stored API keys are undecryptable"
        )

    def test_admin_stored_key_decrypts_in_runtime_manager(self, monkeypatch, tmp_path):
        """Keys stored via the admin API must be decryptable by the runtime
        manager (both singletons in the same process today use different keys
        — the BYOK feature is broken end-to-end)."""
        _tmp_paths(monkeypatch, tmp_path)

        from api.byok_routes import BYOKManager as AdminManager
        from core.byok_endpoints import BYOKManager as RuntimeManager

        admin = AdminManager()
        key_id = admin.store_api_key("openai", "sk-runtime-456", "default", "production")

        _reset_singletons()
        runtime = RuntimeManager()
        decrypted = runtime.decrypt_api_key(runtime.api_keys[key_id].encrypted_key)

        assert decrypted == "sk-runtime-456", (
            f"runtime manager could not decrypt a key stored via the admin "
            f"API (got {decrypted!r})"
        )

    def test_runtime_stored_key_decrypts_after_restart(self, monkeypatch, tmp_path):
        _tmp_paths(monkeypatch, tmp_path)

        from core.byok_endpoints import BYOKManager

        m1 = BYOKManager()
        key_id = m1.store_api_key("openai", "sk-runtime-789", "default", "production")

        _reset_singletons()
        m2 = BYOKManager()
        assert m2.decrypt_api_key(m2.api_keys[key_id].encrypted_key) == "sk-runtime-789"

    def test_get_fernet_does_not_swap_key_on_error(self, monkeypatch, tmp_path):
        """A bad key must NOT silently rotate the manager's key state."""
        _tmp_paths(monkeypatch, tmp_path)

        from core.byok_endpoints import BYOKManager

        m = BYOKManager()
        m.encryption_key = "not-a-valid-fernet-key!!"

        with pytest.raises(Exception):
            m.encrypt_api_key("sk-test")

        assert m.encryption_key == "not-a-valid-fernet-key!!", (
            "_get_fernet swapped in a fresh key on error — silently "
            "invalidating all stored ciphertext"
        )

    def test_admin_get_fernet_does_not_swap_key_on_error(self, monkeypatch, tmp_path):
        """Same guarantee for the admin manager (api/byok_routes)."""
        _tmp_paths(monkeypatch, tmp_path)

        from api.byok_routes import BYOKManager as AdminManager

        m = AdminManager()
        m.encryption_key = "not-a-valid-fernet-key!!"

        with pytest.raises(Exception):
            m.encrypt_api_key("sk-test")

        assert m.encryption_key == "not-a-valid-fernet-key!!", (
            "admin _get_fernet swapped in a fresh key on error"
        )
