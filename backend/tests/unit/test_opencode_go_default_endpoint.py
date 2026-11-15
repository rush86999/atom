"""Provider defaults: Go uses the Go endpoint; Zen keeps the Zen endpoint."""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import patch

from core.llm.byok_handler import BYOKHandler

GO = "https://opencode.ai/inference/go/openai/v1"
ZEN = "https://opencode.ai/zen/v1"


@pytest.fixture()
def handler(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-synthetic-opencode-not-real-0001")
    monkeypatch.setenv(
        "ATOM_LLM_PROVIDER_POLICY",
        '{"mode":"automatic","allowed_providers":[]}')
    monkeypatch.delenv("OPENCODE_BASE_URL", raising=False)
    # No provider-catalog discovery/network in this constructor control.
    monkeypatch.setattr(BYOKHandler, "_refresh_provider_catalog",
                        lambda self: {})
    return BYOKHandler(workspace_id="default", tenant_id="default")


def _base(client):
    return str(client.base_url).rstrip("/") if client is not None else None


def test_opencode_go_defaults_to_go_endpoint_sync_and_async(handler):
    assert _base(handler.clients["opencode-go"]) == GO
    assert _base(handler.async_clients["opencode-go"]) == GO


def test_opencode_zen_default_is_unchanged(handler):
    assert _base(handler.clients["opencode"]) == ZEN
    assert _base(handler.async_clients["opencode"]) == ZEN


def test_explicit_override_applies_to_both_for_loopback(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-synthetic-opencode-not-real-0001")
    monkeypatch.setenv(
        "ATOM_LLM_PROVIDER_POLICY",
        '{"mode":"automatic","allowed_providers":[]}')
    monkeypatch.setenv("OPENCODE_BASE_URL", "http://127.0.0.1:65535/v1")
    monkeypatch.setattr(BYOKHandler, "_refresh_provider_catalog",
                        lambda self: {})
    h = BYOKHandler(workspace_id="default", tenant_id="default")
    assert _base(h.clients["opencode-go"]) == "http://127.0.0.1:65535/v1"
    assert _base(h.clients["opencode"]) == "http://127.0.0.1:65535/v1"


def test_go_client_headers_and_no_retries(handler):
    client = handler.clients["opencode-go"]
    assert client.max_retries == 0
    headers = {k.lower(): v for k, v in dict(client.default_headers).items()}
    assert headers.get("user-agent") == "atom-agent/1.0"
    assert headers.get("x-opencode-session") == "atom-default"
