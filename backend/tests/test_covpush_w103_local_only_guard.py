# -*- coding: utf-8 -*-
"""Coverage wave 103 — core/privsec/local_only_guard.py gaps to 100%.

Existing suite covers sync decorator + blocking basics; this file closes the
gaps: async decorator (blocked + allowed), is_service_local_allowed (both
branches, case-insensitivity), LocalOnlyModeError message assembly with
reason + alternatives, singleton identity, allow_external_request error
paths (blocked w/ reason, alternatives injection), _get_local_alternatives,
and reset_cache behavior. Fully mocked — no network.
"""
import asyncio

import pytest

from core.privsec import local_only_guard as log_mod
from core.privsec.local_only_guard import (
    LocalOnlyGuard,
    LocalOnlyModeError,
    get_local_only_guard,
    require_local_allowed,
)


def _reset():
    log_mod._local_only_guard_instance = None
    LocalOnlyGuard.reset_cache()


@pytest.fixture(autouse=True)
def _isolated():
    _reset()
    yield
    _reset()


@pytest.fixture()
def local_only(monkeypatch):
    monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")
    _reset()
    yield
    monkeypatch.delenv("ATOM_LOCAL_ONLY", raising=False)
    _reset()


class TestLocalOnlyModeError:
    def test_message_plain(self):
        err = LocalOnlyModeError("spotify")
        assert err.status_code == 403
        assert "Service 'spotify' is blocked in local-only mode" in err.detail
        assert "Disable local-only mode" in err.detail

    def test_message_with_reason(self):
        err = LocalOnlyModeError("spotify", reason="OAuth requires cloud")
        assert "OAuth requires cloud" in err.detail

    def test_message_with_alternatives(self):
        err = LocalOnlyModeError("spotify", suggested_alternatives=["sonos", "airplay"])
        assert "Local alternatives: sonos, airplay" in err.detail

    def test_message_with_reason_and_alternatives(self):
        err = LocalOnlyModeError("notion", reason="no local mode", suggested_alternatives=["local markdown files"])
        assert "no local mode" in err.detail
        assert "local markdown files" in err.detail

    def test_no_alternatives_yields_empty(self):
        err = LocalOnlyModeError("slack")
        assert err.suggested_alternatives == []

    def test_alternatives_none_coerced(self):
        err = LocalOnlyModeError("slack", suggested_alternatives=None)
        assert err.suggested_alternatives == []


class TestSingleton:
    def test_singleton_identity(self):
        assert LocalOnlyGuard() is LocalOnlyGuard()
        assert get_local_only_guard() is LocalOnlyGuard()

    def test_init_runs_once(self):
        g1 = LocalOnlyGuard()
        assert g1._enabled is not None
        g2 = LocalOnlyGuard()  # __init__ no-op
        assert g2._enabled == g1._enabled


class TestAllowExternalRequest:
    def test_disabled_allows_everything(self, monkeypatch):
        monkeypatch.delenv("ATOM_LOCAL_ONLY", raising=False)
        _reset()
        guard = get_local_only_guard()
        assert guard.allow_external_request("spotify") is True

    def test_blocked_service_raises_with_reason(self, local_only):
        guard = get_local_only_guard()
        with pytest.raises(LocalOnlyModeError) as exc:
            guard.allow_external_request("spotify", reason="manual test")
        assert exc.value.service == "spotify"
        assert "manual test" in exc.value.detail

    def test_blocked_service_raises_with_alternatives(self, local_only):
        guard = get_local_only_guard()
        with pytest.raises(LocalOnlyModeError) as exc:
            guard.allow_external_request("openai")
        assert exc.value.suggested_alternatives == ["local LLM (Ollama)"]

    def test_uppercase_blocked_service_still_blocked(self, local_only):
        guard = get_local_only_guard()
        with pytest.raises(LocalOnlyModeError):
            guard.allow_external_request("Spotify")

    def test_local_allowed_service_passes(self, local_only):
        guard = get_local_only_guard()
        assert guard.allow_external_request("sonos") is True

    def test_unknown_service_passes_fail_open(self, local_only):
        guard = get_local_only_guard()
        assert guard.allow_external_request("some_future_local_thing") is True


class TestServiceQueries:
    def test_is_service_blocked_case_insensitive(self, local_only):
        guard = get_local_only_guard()
        assert guard.is_service_blocked("NOTION") is True
        assert guard.is_service_blocked("slack") is True
        assert guard.is_service_blocked("sonos") is False

    def test_is_service_local_allowed_true(self, local_only):
        guard = get_local_only_guard()
        assert guard.is_service_local_allowed("sonos") is True
        assert guard.is_service_local_allowed("hue") is True

    def test_is_service_local_allowed_false(self, local_only):
        guard = get_local_only_guard()
        assert guard.is_service_local_allowed("spotify") is False

    def test_is_service_local_allowed_case_insensitive(self, local_only):
        guard = get_local_only_guard()
        assert guard.is_service_local_allowed("HOME_ASSISTANT") is True
        assert guard.is_service_local_allowed("FFMPEG") is True

    def test_blocked_and_local_lists_are_disjoint_sorted(self):
        guard = get_local_only_guard()
        blocked = guard.get_blocked_services()
        allowed = guard.get_local_allowed_services()
        assert blocked == sorted(blocked)
        assert allowed == sorted(allowed)
        assert not (set(blocked) & set(allowed))

    def test_local_alternatives_known(self):
        guard = get_local_only_guard()
        assert guard._get_local_alternatives("spotify") == ["sonos", "airplay"]
        assert guard._get_local_alternatives("notion") == ["local markdown files"]
        assert guard._get_local_alternatives("tavily") == ["local search"]
        assert guard._get_local_alternatives("SONOS") == []

    def test_unknown_alternatives_empty(self):
        guard = get_local_only_guard()
        assert guard._get_local_alternatives("mystery_service") == []


class TestDecoratorAsync:
    def test_async_blocked_service_raises(self, local_only):
        @require_local_allowed("spotify")
        async def fetch_track():
            return "track"

        with pytest.raises(LocalOnlyModeError):
            asyncio.run(fetch_track())

    def test_async_local_service_allowed(self, local_only):
        @require_local_allowed("sonos")
        async def play_speaker():
            return "playing"

        assert asyncio.run(play_speaker()) == "playing"

    def test_async_disabled_mode_passes(self, monkeypatch):
        monkeypatch.delenv("ATOM_LOCAL_ONLY", raising=False)
        _reset()

        @require_local_allowed("spotify")
        async def fetch_track():
            return "track"

        assert asyncio.run(fetch_track()) == "track"

    def test_async_kwargs_passed_through(self, local_only):
        @require_local_allowed("hue")
        async def set_light(color, brightness=100):
            return f"{color}-{brightness}"

        assert asyncio.run(set_light("red", brightness=50)) == "red-50"


class TestDecoratorSync:
    def test_sync_blocked_raises(self, local_only):
        @require_local_allowed("gmail")
        def send_email():
            return "sent"

        with pytest.raises(LocalOnlyModeError):
            send_email()

    def test_sync_allowed_passes(self, local_only):
        @require_local_allowed("ffmpeg")
        def transcode():
            return "ok"

        assert transcode() == "ok"

    def test_wraps_preserves_metadata(self):
        @require_local_allowed("sonos")
        def documented_fn():
            """Docstring preserved."""
            return 1

        assert documented_fn.__name__ == "documented_fn"
        assert "Docstring preserved" in documented_fn.__doc__


class TestResetCache:
    def test_reset_cache_forces_reenable(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "false")
        _reset()
        assert get_local_only_guard().is_local_only_enabled() is False

        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")
        _reset()
        assert get_local_only_guard().is_local_only_enabled() is True
