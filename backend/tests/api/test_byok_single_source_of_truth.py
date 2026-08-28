"""Single-source-of-truth tests for BYOK key storage.

Atom is single-tenant (CLAUDE.md architecture note): the encrypted file
store is THE source of truth for API keys. The ``tenant_settings`` DB mirror
is SaaS parity only, gated behind ``ATOM_BYOK_DB_SYNC`` (default off).
These tests pin that the DB is never written or read for key truth unless
the parity flag is explicitly on, and that the parity mode still works.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from unittest.mock import MagicMock

from api.byok_routes import BYOKManager, _db_key_sync_enabled

# Tenant key helpers are methods on BYOKManager — invoked unbound so the
# manager instance can be a logic-only stub (no file/DB side effects).
_get_tenant_api_key = BYOKManager.get_tenant_api_key
_get_tenant_provider_status = BYOKManager.get_tenant_provider_status
_has_tenant_keys = BYOKManager.has_tenant_keys
_store_tenant_api_key = BYOKManager.store_tenant_api_key


def _manager() -> BYOKManager:
    """A BYOKManager with file/DB side effects stripped — just the logic."""
    mgr = object.__new__(BYOKManager)
    mgr.providers = {}
    mgr.api_keys = {}
    mgr.usage_stats = {}
    mgr.encryption_key = Fernet.generate_key().decode()
    mgr._save_configuration = lambda: None
    return mgr


def _db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0
    return db


def _provider(provider_id="openai"):
    from api.byok_routes import AIProviderConfig

    return AIProviderConfig(
        id=provider_id, name=provider_id.title(), description="d",
        api_key_env_var=f"{provider_id.upper()}_API_KEY",
    )


@pytest.fixture(autouse=True)
def _parity_off(monkeypatch):
    monkeypatch.delenv("ATOM_BYOK_DB_SYNC", raising=False)


# ---------------------------------------------------------------------------
# Flag itself
# ---------------------------------------------------------------------------


def test_parity_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("ATOM_BYOK_DB_SYNC", raising=False)
    assert _db_key_sync_enabled() is False


def test_parity_flag_on(monkeypatch):
    monkeypatch.setenv("ATOM_BYOK_DB_SYNC", "true")
    assert _db_key_sync_enabled() is True


# ---------------------------------------------------------------------------
# Store: file always written; DB only under parity
# ---------------------------------------------------------------------------


def test_store_writes_file_only_by_default():
    mgr = _manager()
    mgr.providers["openai"] = _provider()
    db = _db()

    _store_tenant_api_key(mgr, "default", "openai", "sk-test-123456", db=db)

    assert any(k.startswith("tenant_default_openai_") for k in mgr.api_keys)
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_store_syncs_db_in_parity_mode(monkeypatch):
    monkeypatch.setenv("ATOM_BYOK_DB_SYNC", "true")
    mgr = _manager()
    mgr.providers["openai"] = _provider()
    db = _db()

    _store_tenant_api_key(mgr, "default", "openai", "sk-test-123456", db=db)

    db.add.assert_called_once()
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Read: file only by default; DB-first only under parity
# ---------------------------------------------------------------------------


def test_get_reads_file_without_touching_db():
    mgr = _manager()
    key_id = mgr.store_api_key if False else None  # noqa: F841 — keep shape clear
    stored = mgr.encrypt_api_key("sk-live-123456")
    mgr.api_keys["tenant_default_openai_default_production"] = SimpleNamespace(
        encrypted_key=stored, usage_count=0, last_used=None
    )
    db = _db()

    key = _get_tenant_api_key(mgr, "default", "openai", db=db)

    assert key == "sk-live-123456"
    db.query.assert_not_called()


def test_get_db_first_in_parity_mode(monkeypatch):
    monkeypatch.setenv("ATOM_BYOK_DB_SYNC", "true")
    mgr = _manager()
    db = _db()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        setting_value=mgr.encrypt_api_key("sk-from-db-12345")
    )

    key = _get_tenant_api_key(mgr, "default", "openai", db=db)

    assert key == "sk-from-db-12345"


# ---------------------------------------------------------------------------
# Status/has-keys: file only by default
# ---------------------------------------------------------------------------


def test_provider_status_ignores_db_by_default():
    mgr = _manager()
    mgr.providers["openai"] = _provider()
    mgr.api_keys["tenant_default_openai_default_production"] = SimpleNamespace(
        encrypted_key=mgr.encrypt_api_key("sk-live-123456"), usage_count=0, last_used=None
    )
    db = _db()

    status = _get_tenant_provider_status(mgr, "default", "openai", db=db)

    db.query.assert_not_called()
    assert status["has_api_keys"] is True
    assert status["has_tenant_key"] is True


def test_has_tenant_keys_ignores_db_by_default():
    mgr = _manager()
    mgr.providers["openai"] = _provider()
    db = _db()  # would report count>0 if consulted — must not be

    assert _has_tenant_keys(mgr, "default", db=db) is False
    db.query.assert_not_called()


def test_asdict_shape_stable_for_frontend():
    """get_tenant_provider_status returns asdict(provider) — the shape the
    Settings/DevStudio/wizard UIs parse (provider.id, provider.name)."""
    mgr = _manager()
    mgr.providers["openai"] = _provider()
    status = _get_tenant_provider_status(mgr, "default", "openai", db=_db())
    assert status["provider"]["id"] == "openai"
    assert asdict(_provider())["id"] == "openai"
