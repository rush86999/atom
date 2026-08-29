"""Fresh-install & restart persistence guarantees for the BYOK key store.

Guards the two ways stored credentials were historically lost:

1. CWD-relative store paths — launching uvicorn from the repo root vs
   backend/ pointed at DIFFERENT key files, so a key added in one launch
   mode vanished after a restart in the other. Store paths are now anchored
   to <backend>/data with BYOK_* env-var overrides.

2. Encryption-key sourcing — BYOK_ENCRYPTION_KEY (set by quickstart's
   generated .env) always wins over the persisted key file, but the file was
   never written when the env var was present, so losing .env made the next
   restart mint a fresh key and brick every stored credential. The winning
   env key is now mirrored into the file at manager boot.
"""

import os
import subprocess
import sys

from cryptography.fernet import Fernet

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _reset_singletons():
    import api.byok_routes as api_mod
    import core.byok_endpoints as core_mod

    api_mod._byok_manager = None
    core_mod._byok_manager = None


def _bind_modules_to_tmp(monkeypatch, tmp_path):
    """Point both managers' file constants at a throwaway store."""
    import api.byok_routes as api_mod
    import core.byok_endpoints as core_mod

    for mod in (api_mod, core_mod):
        monkeypatch.setattr(mod, "BYOK_CONFIG_FILE", str(tmp_path / "byok_config.json"))
        monkeypatch.setattr(mod, "BYOK_KEYS_FILE", str(tmp_path / "byok_keys.json"))
        monkeypatch.setattr(mod, "BYOK_ENC_KEY_FILE", str(tmp_path / "byok_encryption_key"))
    _reset_singletons()


class TestStorePathAnchoring:
    def test_default_paths_anchor_to_backend_data_regardless_of_cwd(self, tmp_path):
        """A brand-new install must resolve the same store from any CWD.

        Runs a clean interpreter (no BYOK_* env overrides) from a neutral
        directory and asserts both managers resolve <backend>/data paths.
        """
        code = (
            "import api.byok_routes as a, core.byok_endpoints as c;"
            "print(a.BYOK_CONFIG_FILE);"
            "print(a.BYOK_KEYS_FILE);"
            "print(a.BYOK_ENC_KEY_FILE);"
            "print(c.BYOK_CONFIG_FILE);"
            "print(c.BYOK_KEYS_FILE);"
            "print(c.BYOK_ENC_KEY_FILE)"
        )
        env = {k: v for k, v in os.environ.items() if not k.startswith("BYOK_")}
        env["PYTHONPATH"] = BACKEND_DIR
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120,
        )
        assert result.returncode == 0, result.stderr
        paths = result.stdout.strip().splitlines()
        assert len(paths) == 6
        expected = os.path.join(BACKEND_DIR, "data")
        for p in paths:
            assert os.path.dirname(p) == expected
        # Admin and runtime managers must share ONE store.
        assert paths[0:3] == paths[3:6]


class TestFreshInstallPersistence:
    def test_fresh_install_bootstraps_key_and_survives_restart(self, monkeypatch, tmp_path):
        """No .env, no key file: first boot mints and persists a Fernet key;
        a restarted manager decrypts what the first boot stored."""
        import core.byok_endpoints as core_mod

        _bind_modules_to_tmp(monkeypatch, tmp_path)
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)

        from core.byok_endpoints import BYOKManager

        m1 = BYOKManager()
        assert os.path.exists(core_mod.BYOK_ENC_KEY_FILE), "key file not persisted on first boot"
        m1.store_api_key("openrouter", "sk-or-real-key-1234567890")

        _reset_singletons()
        m2 = BYOKManager()
        assert m2.get_api_key("openrouter") == "sk-or-real-key-1234567890"

    def test_env_key_mirrored_to_file_enables_envless_restart(self, monkeypatch, tmp_path):
        """With BYOK_ENCRYPTION_KEY set (quickstart's default), the file must
        be mirrored so a later env-less restart can still decrypt keys."""
        import core.byok_endpoints as core_mod

        _bind_modules_to_tmp(monkeypatch, tmp_path)
        env_key = Fernet.generate_key().decode()
        monkeypatch.setenv("BYOK_ENCRYPTION_KEY", env_key)

        from core.byok_endpoints import BYOKManager

        m1 = BYOKManager()
        assert m1.encryption_key == env_key
        m1.store_api_key("openrouter", "sk-or-real-key-1234567890")

        with open(core_mod.BYOK_ENC_KEY_FILE) as f:
            assert f.read().strip() == env_key, "env key not mirrored to the key file"

        # Restart WITHOUT the env var: falls back to the mirrored file key.
        _reset_singletons()
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        m2 = BYOKManager()
        assert m2.encryption_key == env_key
        assert m2.get_api_key("openrouter") == "sk-or-real-key-1234567890"

    def test_conflicting_file_key_is_not_clobbered(self, monkeypatch, tmp_path):
        """A differing persisted key is kept (warning only) so credentials
        stored under it stay decryptable for env-less launches."""
        import core.byok_endpoints as core_mod

        _bind_modules_to_tmp(monkeypatch, tmp_path)
        file_key = Fernet.generate_key().decode()
        env_key = Fernet.generate_key().decode()
        with open(core_mod.BYOK_ENC_KEY_FILE, "w") as f:
            f.write(file_key)
        monkeypatch.setenv("BYOK_ENCRYPTION_KEY", env_key)

        from core.byok_endpoints import BYOKManager

        m_env = BYOKManager()
        assert m_env.encryption_key == env_key  # env wins
        with open(core_mod.BYOK_ENC_KEY_FILE) as f:
            assert f.read().strip() == file_key, "differing file key was overwritten"

        # The file key remains fully usable without the env var.
        _reset_singletons()
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        m_file = BYOKManager()
        assert m_file.encryption_key == file_key
        m_file.store_api_key("openrouter", "sk-or-file-key-12345678")
        assert m_file.get_api_key("openrouter") == "sk-or-file-key-12345678"

    def test_admin_manager_mirrors_env_key_too(self, monkeypatch, tmp_path):
        """The admin manager (api/byok_routes) must mirror identically —
        both managers share one store and must share one key story."""
        import api.byok_routes as api_mod

        _bind_modules_to_tmp(monkeypatch, tmp_path)
        env_key = Fernet.generate_key().decode()
        monkeypatch.setenv("BYOK_ENCRYPTION_KEY", env_key)

        from api.byok_routes import BYOKManager

        BYOKManager()
        with open(api_mod.BYOK_ENC_KEY_FILE) as f:
            assert f.read().strip() == env_key


class TestStatusPlaceholderFilter:
    def test_placeholder_key_reports_inactive(self, monkeypatch, tmp_path):
        """A stored dummy (e.g. test-suite leftover "sk-test") must NOT make
        a provider show as active in the UI."""
        import api.byok_routes as api_mod

        _bind_modules_to_tmp(monkeypatch, tmp_path)
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)

        from api.byok_routes import BYOKManager

        m = BYOKManager()
        m.store_api_key("openai", "sk-test")
        status = m.get_provider_status("openai")
        assert status["has_api_keys"] is False
        assert status["status"] == "inactive"

    def test_real_length_key_reports_active(self, monkeypatch, tmp_path):
        import api.byok_routes as api_mod

        _bind_modules_to_tmp(monkeypatch, tmp_path)
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)

        from api.byok_routes import BYOKManager

        m = BYOKManager()
        m.store_api_key("openrouter", "sk-or-v1-real-key-1234567890")
        status = m.get_provider_status("openrouter")
        assert status["has_api_keys"] is True
        assert status["status"] == "active"
