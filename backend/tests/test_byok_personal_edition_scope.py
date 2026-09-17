"""Personal Edition BYOK: the "default" tenant sentinel must not hide saved keys.

Keys saved in Settings are written as ``tenant_<uuid>_<provider>_<name>_<env>``
(api/byok_routes ``store_tenant_api_key``), but the chat / probe handlers are
constructed with the sentinel ``tenant_id="default"`` — a scope nobody stores
under. Declaring it made ``BYOKManager.get_api_key`` miss the saved key AND
skip ``_find_stored_key``'s single-scope resolution (the designed
personal-edition path), so every chat reply was "All LLM providers failed"
and Settings → AI "Test Connection" always reported provider_not_configured.

The fix maps the sentinel to scope None at the lookup; the store keeps its
own safety rules: the global entry first, a single-scope store resolves to
that one scope, and 2+ scopes with no global entry are ambiguous → None
(never another tenant's key).
"""
import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from cryptography.fernet import Fernet

from core.llm.byok_handler import BYOKHandler

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"


def _setup_store(monkeypatch, tmp_path):
    """Point the runtime BYOKManager at a scratch store with a shared key."""
    import core.byok_endpoints as core_mod

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(
        core_mod, "BYOK_CONFIG_FILE", str(tmp_path / "byok_config.json"))
    monkeypatch.setattr(
        core_mod, "BYOK_KEYS_FILE", str(tmp_path / "byok_keys.json"))
    monkeypatch.setattr(
        core_mod, "BYOK_ENC_KEY_FILE", str(tmp_path / "byok_encryption_key"))
    return core_mod


def _write_tenant_key(core_mod, keys_path, tenant_id, provider_id, plaintext):
    """Write a key in the exact id/entry shape the save route produces."""
    manager = core_mod.BYOKManager()
    entry = {
        "provider_id": provider_id,
        "key_name": "default",
        "environment": "production",
        "encrypted_key": manager.encrypt_api_key(plaintext),
        "key_hash": "deadbeef",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used": None,
        "is_active": True,
        "usage_count": 0,
        "tenant_id": tenant_id,
    }
    keys = {}
    if keys_path.exists():
        keys = json.loads(keys_path.read_text()).get("keys", {})
    keys[f"tenant_{tenant_id}_{provider_id}_default_production"] = entry
    keys_path.write_text(json.dumps({"keys": keys}))


def _write_global_key(core_mod, keys_path, provider_id, plaintext):
    manager = core_mod.BYOKManager()
    entry = {
        "provider_id": provider_id,
        "key_name": "default",
        "environment": "production",
        "encrypted_key": manager.encrypt_api_key(plaintext),
        "key_hash": "deadbeef",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used": None,
        "is_active": True,
        "usage_count": 0,
    }
    keys = {}
    if keys_path.exists():
        keys = json.loads(keys_path.read_text()).get("keys", {})
    keys[f"{provider_id}_default_production"] = entry
    keys_path.write_text(json.dumps({"keys": keys}))


def _build_handler(monkeypatch, core_mod, tenant_id):
    """Construct a real BYOKHandler against the scratch store, with the
    OpenAI/AsyncOpenAI client constructors mocked so the api_key passed for
    each resolved provider can be asserted on."""
    import core.llm.byok_handler as bh

    monkeypatch.setattr(
        bh, "get_byok_manager", lambda: core_mod.BYOKManager())
    monkeypatch.setattr(bh, "get_db_session", lambda: Mock())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with patch.object(bh, "OpenAI") as mock_openai, \
         patch.object(bh, "AsyncOpenAI", create=True):
        handler = BYOKHandler(tenant_id=tenant_id)
    resolved = [c.kwargs.get("api_key") for c in mock_openai.call_args_list]
    return handler, resolved


class TestPersonalEditionScope:
    def test_default_sentinel_resolves_single_tenant_scoped_key(
            self, monkeypatch, tmp_path):
        """THE bug: handler carries tenant_id="default" (module-scoped
        orchestrator / Settings probe), the store holds one tenant-prefixed
        key — the key must resolve and the provider get a client."""
        core_mod = _setup_store(monkeypatch, tmp_path)
        _write_tenant_key(core_mod, tmp_path / "byok_keys.json",
                          TENANT_A, "openai", "sk-personal-live-key")

        handler, resolved = _build_handler(monkeypatch, core_mod, "default")

        assert "openai" in handler.clients
        assert "sk-personal-live-key" in resolved

    def test_default_sentinel_refuses_ambiguous_multi_scope_store(
            self, monkeypatch, tmp_path):
        """Two tenants' keys and no global entry is ambiguous: the sentinel
        caller must get NOTHING, not the first match."""
        core_mod = _setup_store(monkeypatch, tmp_path)
        _write_tenant_key(core_mod, tmp_path / "byok_keys.json",
                          TENANT_A, "openai", "sk-key-of-aaa")
        _write_tenant_key(core_mod, tmp_path / "byok_keys.json",
                          TENANT_B, "openai", "sk-key-of-bbb")

        handler, resolved = _build_handler(monkeypatch, core_mod, "default")

        assert "openai" not in handler.clients
        assert "sk-key-of-aaa" not in resolved
        assert "sk-key-of-bbb" not in resolved

    def test_real_tenant_resolves_own_key_never_another_tenants(
            self, monkeypatch, tmp_path):
        core_mod = _setup_store(monkeypatch, tmp_path)
        _write_tenant_key(core_mod, tmp_path / "byok_keys.json",
                          TENANT_A, "openai", "sk-key-of-aaa")
        _write_tenant_key(core_mod, tmp_path / "byok_keys.json",
                          TENANT_B, "openai", "sk-key-of-bbb")

        handler, resolved = _build_handler(monkeypatch, core_mod, TENANT_A)

        assert "openai" in handler.clients
        assert "sk-key-of-aaa" in resolved
        assert "sk-key-of-bbb" not in resolved

    def test_global_entry_served_to_scopeless_caller(self, monkeypatch, tmp_path):
        """Scopeless callers get the operator's global entry when one exists
        (the store's precedence: global first, single-scope fallback only
        when there is no global entry)."""
        core_mod = _setup_store(monkeypatch, tmp_path)
        _write_global_key(core_mod, tmp_path / "byok_keys.json",
                          "openai", "sk-operator-global")
        _write_tenant_key(core_mod, tmp_path / "byok_keys.json",
                          TENANT_A, "openai", "sk-key-of-aaa")

        handler, resolved = _build_handler(monkeypatch, core_mod, "default")

        assert "openai" in handler.clients
        assert "sk-operator-global" in resolved
        assert "sk-key-of-aaa" not in resolved

    def test_tenant_with_own_key_does_not_get_the_global_entry(
            self, monkeypatch, tmp_path):
        """A declaring tenant gets its OWN scoped entry, else the global one —
        never the global one in preference to its own."""
        core_mod = _setup_store(monkeypatch, tmp_path)
        _write_global_key(core_mod, tmp_path / "byok_keys.json",
                          "openai", "sk-operator-global")
        _write_tenant_key(core_mod, tmp_path / "byok_keys.json",
                          TENANT_A, "openai", "sk-key-of-aaa")

        handler, resolved = _build_handler(monkeypatch, core_mod, TENANT_A)

        assert "openai" in handler.clients
        assert "sk-key-of-aaa" in resolved
        assert "sk-operator-global" not in resolved


class TestSentinelMapping:
    def test_sentinel_and_blank_map_to_none(self):
        handler = object.__new__(BYOKHandler)
        for sentinel in (None, "", "default"):
            handler.tenant_id = sentinel
            assert handler._credential_scope_tenant() is None

    def test_real_tenant_id_passes_through(self):
        handler = object.__new__(BYOKHandler)
        handler.tenant_id = TENANT_A
        assert handler._credential_scope_tenant() == TENANT_A
