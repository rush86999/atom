"""Presence-only Microsoft OAuth configuration preflight controls."""
from __future__ import annotations

import json

from core.oauth_config_preflight import (
    microsoft_client_config_state,
    run_oauth_config_preflight,
)


def test_missing_configuration_is_reported_without_values(monkeypatch):
    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    monkeypatch.delenv("MICROSOFT_CLIENT_SECRET", raising=False)
    state = microsoft_client_config_state()
    assert state["configured"] is False
    assert state["missing"] == [
        "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
    ]
    assert state["placeholders"] == []


def test_present_configuration_is_configured(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client-id-value")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "client-secret-value")
    state = microsoft_client_config_state()
    assert state["configured"] is True
    assert state["missing"] == []
    assert state["placeholders"] == []
    assert "client-secret-value" not in json.dumps(state)


def test_placeholder_configuration_is_not_configured(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "your-client-id")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "<redacted>")
    state = microsoft_client_config_state()
    assert state["configured"] is False
    assert state["placeholders"] == [
        "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
    ]


def test_preflight_logs_repair_not_revocation(monkeypatch):
    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    monkeypatch.delenv("MICROSOFT_CLIENT_SECRET", raising=False)
    messages = []

    class Capture:
        def info(self, message, *args):
            messages.append(("info", message % args if args else message))

        def warning(self, message, *args):
            messages.append(("warning", message % args if args else message))

    run_oauth_config_preflight(Capture())
    assert messages and messages[0][0] == "warning"
    assert "Administrator configuration repair" in messages[0][1]
    assert "not a revoked user grant" in messages[0][1]
