"""
TDD regression: BYOK LLM clients must be constructed with a bounded request
timeout so a wedged provider (dead key, retry storm) cannot hold the request
loop for the SDK default 600s — E2E boot verify 2026-08-06 reproduced the
whole server freezing on POST /api/v1/ai/nlu for minutes.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

from core.llm import byok_handler


class _FakeClientFactory:
    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        _FakeClientFactory.instances.append(kwargs)


def _build_handler():
    handler = byok_handler.BYOKHandler.__new__(byok_handler.BYOKHandler)
    handler.byok_manager = MagicMock()
    handler.byok_manager.is_configured.return_value = False
    handler.credential_service = MagicMock()
    handler.credential_service.get_credential.return_value = (None, None)
    handler.clients = {}
    handler.async_clients = {}
    handler.workspace_id = "ws_test"
    return handler


def _reset_factory():
    _FakeClientFactory.instances = []


def test_clients_constructed_with_env_timeout(monkeypatch):
    _reset_factory()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ATOM_LLM_REQUEST_TIMEOUT", "45")

    handler = _build_handler()
    with patch.object(byok_handler, "OpenAI", _FakeClientFactory), patch.object(
        byok_handler, "AsyncOpenAI", _FakeClientFactory
    ):
        handler._initialize_clients()

    assert _FakeClientFactory.instances, "no clients constructed"
    for kwargs in _FakeClientFactory.instances:
        assert kwargs.get("timeout") == 45, f"missing env timeout in {kwargs}"


def test_clients_constructed_with_default_timeout(monkeypatch):
    _reset_factory()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.delenv("ATOM_LLM_REQUEST_TIMEOUT", raising=False)

    handler = _build_handler()
    with patch.object(byok_handler, "OpenAI", _FakeClientFactory), patch.object(
        byok_handler, "AsyncOpenAI", _FakeClientFactory
    ):
        handler._initialize_clients()

    assert _FakeClientFactory.instances
    for kwargs in _FakeClientFactory.instances:
        assert kwargs.get("timeout") == 120, f"missing default timeout in {kwargs}"


def test_invalid_env_timeout_falls_back_to_default(monkeypatch):
    _reset_factory()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("ATOM_LLM_REQUEST_TIMEOUT", "not-a-number")

    handler = _build_handler()
    with patch.object(byok_handler, "OpenAI", _FakeClientFactory), patch.object(
        byok_handler, "AsyncOpenAI", _FakeClientFactory
    ):
        handler._initialize_clients()

    for kwargs in _FakeClientFactory.instances:
        assert kwargs.get("timeout") == 120
