"""OpenCode Zen gateway session-id header (MissingSessionID gate).

Live verification 2026-09-07: a header-less call to the zen gateway
(https://opencode.ai/zen/v1) with a "-free" model returns
``400 MissingSessionID — "OpenCode's free tier can only be used in OpenCode"``;
the same call with ``X-Session-Id`` succeeds. The gateway treats both
"opencode-go" (env key) and "opencode" (UI-stored key) provider ids as the
same gateway, so both clients must send the header.
"""
import os
import re
from unittest.mock import MagicMock

from core.llm.byok_handler import (
    BYOKHandler,
    _OPENCODE_GATEWAY_PROVIDERS,
    _OPENCODE_SESSION_ID,
    _opencode_gateway_headers,
)


class TestGatewayHeaders:
    def test_headers_carry_browser_signature_and_session_id(self):
        headers = _opencode_gateway_headers()
        assert headers["X-Session-Id"] == _OPENCODE_SESSION_ID
        assert headers["Origin"] == "https://opencode.ai"
        assert headers["Referer"] == "https://opencode.ai/"
        assert "Mozilla/5.0" in headers["User-Agent"]

    def test_session_id_is_stable_per_process(self):
        # One id per process satisfies the gate; two reads must agree and the
        # generated default must look like a 128-bit hex id.
        assert _opencode_gateway_headers()["X-Session-Id"] == _OPENCODE_SESSION_ID
        assert re.fullmatch(r"[0-9a-f]{32}", _OPENCODE_SESSION_ID)

    def test_env_override_is_honored(self, monkeypatch):
        monkeypatch.setattr(
            "core.llm.byok_handler._OPENCODE_SESSION_ID", "my-fixed-session"
        )
        assert _opencode_gateway_headers()["X-Session-Id"] == "my-fixed-session"

    def test_gateway_provider_set_covers_both_zen_ids(self):
        # "opencode" (UI-stored key) and "opencode-go" (env key) hit the same
        # base_url — a future change to one side without the other regresses
        # the free tier for that credential path.
        assert _OPENCODE_GATEWAY_PROVIDERS == {"opencode-go", "opencode"}


class TestClientConstruction:
    def test_both_gateway_clients_send_session_header(self, monkeypatch):
        built = []

        class _Recorder:
            def __init__(self, **kwargs):
                built.append(kwargs)

        monkeypatch.setattr("core.llm.byok_handler.OpenAI", _Recorder)
        monkeypatch.setattr("core.llm.byok_handler.AsyncOpenAI", _Recorder)
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-zen-test-key-1234567890")
        monkeypatch.setenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1")
        # Clear other provider keys so ONLY the zen gateway clients get built.
        for key in list(os.environ):
            if key.endswith("_API_KEY") and key != "OPENCODE_API_KEY":
                monkeypatch.delenv(key, raising=False)

        handler = BYOKHandler.__new__(BYOKHandler)
        handler.workspace_id = "default"
        handler.clients = {}
        handler.async_clients = {}
        handler.env_key_providers = set()
        handler.credential_service = None
        handler.byok_manager = MagicMock()
        handler.byok_manager.is_configured.return_value = False
        monkeypatch.setattr(handler, "_load_local_providers", lambda: None)

        handler._initialize_clients()

        zen_clients = [
            kw for kw in built
            if str(kw.get("base_url", "")).rstrip("/").endswith("opencode.ai/zen/v1")
        ]
        # 2 provider ids × (sync OpenAI + async AsyncOpenAI) clients.
        assert len(zen_clients) == 4, built
        for kw in zen_clients:
            headers = kw.get("default_headers", {})
            assert headers.get("X-Session-Id") == _OPENCODE_SESSION_ID
            assert "Mozilla/5.0" in headers.get("User-Agent", "")
