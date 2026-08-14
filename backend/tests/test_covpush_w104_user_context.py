# -*- coding: utf-8 -*-
"""Coverage wave 104 — core/user_context_manager.py.

Unit coverage of the user context / token manager:
- token_storage lazy-load (success + ImportError branches).
- get_token: user storage hit, storage-miss/missing-key/exception falls
  through to env vars (all three env-name orders), no token -> None.
- get_token_with_context: no token -> {}, source user/bot (incl. storage
  exception and missing access_token), no user_id -> bot.
- store_token: no storage, no user_id, success with additional_data,
  storage exception -> False.
- invalidate_token: no storage, delete_token path, set_token fallback
  path, exception -> False.
- get_available_providers: env providers (BOT_TOKEN/ACCESS_TOKEN),
  storage providers, storage exception, no storage.
- get_user_context_manager singleton + db rebind.

No LLM spend, no network.
"""
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.user_context_manager import (
    UserContextManager,
    get_user_context_manager,
)


@pytest.fixture()
def storage():
    return MagicMock()


@pytest.fixture()
def manager(storage):
    m = UserContextManager(db=MagicMock())
    m._token_storage = storage
    return m


class TestTokenStorageLazyLoad:
    def test_loads_global_storage(self, monkeypatch):
        fake = MagicMock()
        monkeypatch.setattr("core.token_storage.token_storage", fake)
        m = UserContextManager()
        assert m.token_storage is fake
        assert m._token_storage is fake

    def test_loads_only_once(self, monkeypatch):
        fake = MagicMock()
        monkeypatch.setattr("core.token_storage.token_storage", fake)
        m = UserContextManager()
        _ = m.token_storage
        _ = m.token_storage
        assert m.token_storage is fake

    def test_import_error_returns_none(self, monkeypatch):
        import sys
        import types

        fake_module = types.ModuleType("core.token_storage")
        with patch.dict(sys.modules, {"core.token_storage": fake_module}):
            m = UserContextManager()
            assert m.token_storage is None


class TestGetToken:
    def test_user_token_from_storage(self, manager, storage):
        storage.get_token.return_value = {"access_token": "tok-1", "refresh_token": "ref"}
        assert manager.get_token("slack", user_id="u1") == "tok-1"
        storage.get_token.assert_called_once_with("slack", "u1")

    def test_user_token_specific_type(self, manager, storage):
        storage.get_token.return_value = {"access_token": "tok-1", "refresh_token": "ref"}
        assert manager.get_token("slack", user_id="u1", token_type="refresh_token") == "ref"

    def test_missing_token_type_falls_back_to_env(self, manager, storage, monkeypatch):
        storage.get_token.return_value = {"refresh_token": "ref"}
        monkeypatch.setenv("SLACK_BOT_TOKEN", "env-tok")
        assert manager.get_token("slack", user_id="u1") == "env-tok"

    def test_storage_exception_falls_back_to_env(self, manager, storage, monkeypatch):
        storage.get_token.side_effect = RuntimeError("storage down")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "env-tok")
        assert manager.get_token("slack", user_id="u1") == "env-tok"

    def test_env_bot_token(self, manager, monkeypatch):
        monkeypatch.setenv("GMAIL_BOT_TOKEN", "g-bot")
        assert manager.get_token("gmail") == "g-bot"

    def test_env_access_token(self, manager, monkeypatch):
        monkeypatch.setenv("GMAIL_ACCESS_TOKEN", "g-acc")
        assert manager.get_token("gmail") == "g-acc"

    def test_env_plain_token(self, manager, monkeypatch):
        monkeypatch.setenv("GMAIL_TOKEN", "g-plain")
        assert manager.get_token("gmail") == "g-plain"

    def test_env_priority_order(self, manager, monkeypatch):
        monkeypatch.setenv("GMAIL_BOT_TOKEN", "g-bot")
        monkeypatch.setenv("GMAIL_ACCESS_TOKEN", "g-acc")
        assert manager.get_token("gmail") == "g-bot"

    def test_no_token_returns_none(self, manager):
        assert manager.get_token("zoom") is None

    def test_no_storage_no_env(self, monkeypatch):
        m = UserContextManager(db=None)
        m._token_storage = None
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_TOKEN", raising=False)
        assert m.get_token("slack", user_id="u1") is None

    def test_no_user_id_but_storage_present(self, manager, storage, monkeypatch):
        storage.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setenv("ZOOM_ACCESS_TOKEN", "zoom-tok")
        assert manager.get_token("zoom") == "zoom-tok"


class TestGetTokenWithContext:
    def test_no_token_empty_dict(self, manager):
        assert manager.get_token_with_context("zoom") == {}

    def test_source_user(self, manager, storage):
        storage.get_token.return_value = {"access_token": "tok-1"}
        ctx = manager.get_token_with_context("slack", user_id="u1")
        assert ctx == {
            "token": "tok-1",
            "source": "user",
            "user_id": "u1",
            "provider": "slack",
        }

    def test_source_bot_when_storage_lacks_access_token(self, manager, storage, monkeypatch):
        storage.get_token.return_value = {"refresh_token": "ref"}
        monkeypatch.setenv("SLACK_ACCESS_TOKEN", "env-tok")
        ctx = manager.get_token_with_context("slack", user_id="u1")
        assert ctx["source"] == "bot"
        assert ctx["user_id"] is None
        assert ctx["token"] == "env-tok"

    def test_source_bot_when_storage_raises(self, manager, storage, monkeypatch):
        storage.get_token.side_effect = RuntimeError("boom")
        monkeypatch.setenv("SLACK_ACCESS_TOKEN", "env-tok")
        ctx = manager.get_token_with_context("slack", user_id="u1")
        assert ctx["source"] == "bot"

    def test_no_user_id_source_bot(self, manager, storage, monkeypatch):
        storage.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setenv("SLACK_ACCESS_TOKEN", "env-tok")
        ctx = manager.get_token_with_context("slack")
        assert ctx["source"] == "bot"
        assert ctx["user_id"] is None


class TestStoreToken:
    def test_no_storage(self, monkeypatch):
        monkeypatch.setattr("core.token_storage.token_storage", None)
        m = UserContextManager(db=None)
        assert m.store_token("slack", "tok", user_id="u1") is False

    def test_no_user_id(self, manager, storage):
        assert manager.store_token("slack", "tok") is False

    def test_success(self, manager, storage):
        assert manager.store_token("slack", "tok-1", user_id="u1") is True
        storage.set_token.assert_called_once_with("slack", "u1", {"access_token": "tok-1"})

    def test_success_with_additional_data(self, manager, storage):
        assert manager.store_token(
            "slack", "tok-1", user_id="u1", additional_data={"refresh_token": "r"}
        ) is True
        storage.set_token.assert_called_once_with(
            "slack", "u1", {"access_token": "tok-1", "refresh_token": "r"}
        )

    def test_storage_exception(self, manager, storage):
        storage.set_token.side_effect = RuntimeError("no")
        assert manager.store_token("slack", "tok-1", user_id="u1") is False


class TestInvalidateToken:
    def test_no_storage(self, monkeypatch):
        monkeypatch.setattr("core.token_storage.token_storage", None)
        m = UserContextManager(db=None)
        assert m.invalidate_token("slack", "u1") is False

    def test_delete_token_path(self, manager, storage):
        assert manager.invalidate_token("slack", "u1") is True
        storage.delete_token.assert_called_once_with("slack", "u1")
        storage.set_token.assert_not_called()

    def test_set_token_fallback(self, storage):
        storage = MagicMock(spec=["set_token"])
        m = UserContextManager(db=None)
        m._token_storage = storage
        assert m.invalidate_token("slack", "u1") is True
        storage.set_token.assert_called_once_with("slack", "u1", {})

    def test_exception(self, manager, storage):
        storage.delete_token.side_effect = RuntimeError("no")
        assert manager.invalidate_token("slack", "u1") is False


class TestGetAvailableProviders:
    def test_env_bot_token(self, manager, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "x")
        assert "slack" in manager.get_available_providers()

    def test_env_access_token(self, manager, monkeypatch):
        monkeypatch.setenv("OUTLOOK_ACCESS_TOKEN", "x")
        assert "outlook" in manager.get_available_providers()

    def test_storage_providers(self, manager, storage):
        storage.get_all_providers.return_value = ["gmail", "zoho"]
        providers = manager.get_available_providers()
        assert "gmail" in providers and "zoho" in providers

    def test_storage_exception(self, manager, storage, monkeypatch):
        storage.get_all_providers.side_effect = RuntimeError("boom")
        monkeypatch.setenv("GMAIL_BOT_TOKEN", "x")
        assert manager.get_available_providers() == ["gmail"]

    def test_no_storage_no_env(self, monkeypatch):
        for name in ("SLACK", "GMAIL", "OUTLOOK", "MICROSOFT_365", "ZOHO"):
            monkeypatch.delenv(f"{name}_BOT_TOKEN", raising=False)
            monkeypatch.delenv(f"{name}_ACCESS_TOKEN", raising=False)
        m = UserContextManager(db=None)
        m._token_storage = None
        assert m.get_available_providers() == []


class TestGetUserContextManager:
    def test_singleton_first_call(self):
        m1 = get_user_context_manager()
        try:
            assert isinstance(m1, UserContextManager)
            assert get_user_context_manager() is m1
        finally:
            _reset_global()

    def test_rebind_db(self):
        _reset_global()
        m = get_user_context_manager(db=SimpleNamespace())
        m2 = get_user_context_manager(db=SimpleNamespace())
        assert m is m2
        assert m2.db is not None
        _reset_global()

    def test_constructor_db(self):
        db = SimpleNamespace()
        m = UserContextManager(db=db)
        assert m.db is db
        assert m._token_storage is None


def _reset_global():
    import core.user_context_manager as ucm

    ucm._global_context_manager = None
    ucm._global_context_manager_lock = __import__("threading").Lock()


class TestEnvFallbackIntegration:
    def test_os_getenv_respected(self, manager, monkeypatch):
        monkeypatch.setenv("ZOOHOO_BOT_TOKEN", "secret")
        assert manager.get_token("zoohoo") == "secret"
        monkeypatch.delenv("ZOOHOO_BOT_TOKEN", raising=False)
