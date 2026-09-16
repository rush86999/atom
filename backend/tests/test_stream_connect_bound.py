# -*- coding: utf-8 -*-
"""The stream CONNECT must be bounded, not just the silence after it.

The idle watchdog (`_stream_with_idle_watchdog`) starts only once a stream
object exists. A provider that accepts the request and never sends response
headers blocks the initial `create()` await for the SDK's read timeout (120 s
by default) — longer than the turn budget. The orchestrator then sees neither a
chunk nor an error: measured 2026-09-16, `Attempting stream with provider:
openrouter …` followed 115 s later by `reply generation: 115.0s` with no
zero-chunk warning and no first-visible abort, because neither bound could fire.
"""
import os

import pytest

import core.llm.byok_handler as bh


class TestStreamConnectBound:
    def test_default_is_inside_the_turn_budget(self):
        assert bh._stream_connect_timeout_seconds() == 30.0

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("ATOM_STREAM_CONNECT_TIMEOUT_SECONDS", "12.5")
        assert bh._stream_connect_timeout_seconds() == 12.5

    def test_invalid_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("ATOM_STREAM_CONNECT_TIMEOUT_SECONDS", "soon")
        assert bh._stream_connect_timeout_seconds() == 30.0

    def test_zero_disables_the_bound(self, monkeypatch):
        monkeypatch.setenv("ATOM_STREAM_CONNECT_TIMEOUT_SECONDS", "0")
        assert bh._stream_connect_timeout_seconds() == 0.0

    def test_the_connect_await_is_wrapped(self):
        import inspect

        src = inspect.getsource(bh.BYOKHandler.stream_completion)
        assert "_stream_connect_timeout_seconds()" in src
        assert "asyncio.wait_for(" in src
        # The bounded form wraps the create call; the unwrapped await survives
        # only in the `else` branch used when the bound is disabled.
        assert "asyncio.wait_for(\n                        client.chat.completions.create" in src
        assert src.count("await client.chat.completions.create(**create_kwargs)") == 1
