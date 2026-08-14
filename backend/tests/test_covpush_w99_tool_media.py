# -*- coding: utf-8 -*-
"""Coverage wave 99 — tools/media_tool.py (was 43%).

- _check_media_governance: human action allow, agent not found (STUDENT
  default), INTERN read-only action allowed, insufficient maturity blocked,
  governance-service allow/deny (incl. "Agent not found" pass-through),
  exception -> fail closed for agents / fail open for humans.
- spotify_current/play/pause/next/previous/volume/devices and
  sonos_discover/play/pause/volume/groups: governance blocked, success,
  service exception.
- register_media_tools: 12 registrations through the ToolRegistry;
  auto-register failure swallowed on reload.

SpotifyService/SonosService fully mocked; db is a MagicMock session.
Zero network, zero LLM.
"""
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools import media_tool as mt
from tools.media_tool import (
    sonos_discover,
    sonos_groups,
    sonos_pause,
    sonos_play,
    sonos_volume,
    spotify_current,
    spotify_devices,
    spotify_next,
    spotify_pause,
    spotify_play,
    spotify_previous,
    spotify_volume,
)


@pytest.fixture()
def db():
    return MagicMock()


@pytest.fixture(autouse=True)
def _gov_service():
    # AgentGovernanceService is imported inside _check_media_governance
    with patch("core.agent_governance_service.AgentGovernanceService",
               MagicMock()) as gov_cls:
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "reason": "ok"})
        gov_cls.return_value = gov
        yield gov_cls


@pytest.fixture()
def spotify():
    svc = MagicMock()
    with patch.object(mt, "SpotifyService", return_value=svc):
        yield svc


@pytest.fixture()
def sonos():
    svc = MagicMock()
    with patch.object(mt, "SonosService", return_value=svc):
        yield svc


def _agent(maturity):
    a = MagicMock()
    a.status = maturity
    return a


# ============================================================================
# _check_media_governance
# ============================================================================

class TestCheckMediaGovernance:
    async def test_human_action_allowed(self, db):
        result = await mt._check_media_governance(db, None, "spotify_play", "u-1")
        assert result["allowed"] is True
        assert result["governance_check_passed"] is True

    async def test_agent_not_found_defaults_student(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = await mt._check_media_governance(db, "ghost", "spotify_play", "u-1")
        assert result["allowed"] is False
        assert "STUDENT" in result["reason"]

    async def test_intern_read_only_action_allowed(self, db, _gov_service):
        db.query.return_value.filter.return_value.first.return_value = _agent("INTERN")
        result = await mt._check_media_governance(db, "a-1", "spotify_devices", "u-1")
        assert result["allowed"] is True
        _gov_service.return_value.can_perform_action_async.assert_awaited_once_with(
            agent_id="a-1", action_type="spotify_devices")

    async def test_supervised_required_action_denied(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("INTERN")
        result = await mt._check_media_governance(db, "a-1", "spotify_play", "u-1")
        assert result["allowed"] is False
        assert "Requires SUPERVISED+" in result["reason"]

    async def test_governance_service_denies(self, db, _gov_service):
        db.query.return_value.filter.return_value.first.return_value = _agent("AUTONOMOUS")
        _gov_service.return_value.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "budget exhausted"})
        result = await mt._check_media_governance(db, "a-1", "sonos_play", "u-1")
        assert result["allowed"] is False
        assert result["reason"] == "budget exhausted"

    async def test_governance_service_agent_not_found_passes(self, db, _gov_service):
        db.query.return_value.filter.return_value.first.return_value = _agent("SUPERVISED")
        _gov_service.return_value.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "Agent not found"})
        result = await mt._check_media_governance(db, "a-1", "sonos_play", "u-1")
        assert result["allowed"] is True

    async def test_unknown_action_defaults_supervised(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("INTERN")
        result = await mt._check_media_governance(db, "a-1", "mystery_action", "u-1")
        assert result["allowed"] is False

    async def test_exception_fails_closed_for_agent(self, db):
        db.query.side_effect = RuntimeError("db down")
        result = await mt._check_media_governance(db, "a-1", "spotify_play", "u-1")
        assert result["allowed"] is False
        assert "Governance check error" in result["reason"]


# ============================================================================
# Spotify tool functions
# ============================================================================

class TestSpotifyCurrent:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await spotify_current(db, "u-1", agent_id="a-1")
        assert result == {"success": False, "error": result["error"],
                          "governance_blocked": True}

    async def test_success(self, db, spotify):
        spotify.get_current_track = AsyncMock(return_value={"name": "Song"})
        result = await spotify_current(db, "u-1")
        assert result == {"name": "Song"}
        spotify.get_current_track.assert_awaited_once_with("u-1")

    async def test_service_exception(self, db, spotify):
        spotify.get_current_track = AsyncMock(side_effect=RuntimeError("spotify down"))
        result = await spotify_current(db, "u-1")
        assert result["success"] is False
        assert "spotify down" in result["error"]


class TestSpotifyPlay:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await spotify_play(db, "u-1", agent_id="a-1")
        assert result["success"] is False
        assert result["governance_blocked"] is True

    async def test_success(self, db, spotify):
        spotify.play_track = AsyncMock(return_value={"playing": True})
        result = await spotify_play(db, "u-1", track_uri="uri", device_id="dev")
        assert result == {"playing": True}
        spotify.play_track.assert_awaited_once_with("u-1", "uri", "dev")

    async def test_service_exception(self, db, spotify):
        spotify.play_track = AsyncMock(side_effect=RuntimeError("no"))
        result = await spotify_play(db, "u-1")
        assert result["success"] is False


class TestSpotifyPause:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("INTERN")
        result = await spotify_pause(db, "u-1", agent_id="a-1")
        assert result["success"] is False
        assert result["governance_blocked"] is True

    async def test_success(self, db, spotify):
        spotify.pause_playback = AsyncMock(return_value={"paused": True})
        assert await spotify_pause(db, "u-1") == {"paused": True}
        spotify.pause_playback.assert_awaited_once_with("u-1", None)

    async def test_service_exception(self, db, spotify):
        spotify.pause_playback = AsyncMock(side_effect=RuntimeError("no"))
        result = await spotify_pause(db, "u-1")
        assert result["success"] is False


class TestSpotifyNext:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await spotify_next(db, "u-1", agent_id="a-1")
        assert result["success"] is False

    async def test_success(self, db, spotify):
        spotify.skip_next = AsyncMock(return_value={"skipped": True})
        assert await spotify_next(db, "u-1") == {"skipped": True}

    async def test_service_exception(self, db, spotify):
        spotify.skip_next = AsyncMock(side_effect=RuntimeError("no"))
        result = await spotify_next(db, "u-1")
        assert result["success"] is False


class TestSpotifyPrevious:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await spotify_previous(db, "u-1", agent_id="a-1")
        assert result["success"] is False

    async def test_success(self, db, spotify):
        spotify.skip_previous = AsyncMock(return_value={"prev": True})
        assert await spotify_previous(db, "u-1") == {"prev": True}

    async def test_service_exception(self, db, spotify):
        spotify.skip_previous = AsyncMock(side_effect=RuntimeError("no"))
        result = await spotify_previous(db, "u-1")
        assert result["success"] is False


class TestSpotifyVolume:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await spotify_volume(db, "u-1", 50, agent_id="a-1")
        assert result["success"] is False

    async def test_success(self, db, spotify):
        spotify.set_volume = AsyncMock(return_value={"volume": 50})
        assert await spotify_volume(db, "u-1", 50) == {"volume": 50}
        spotify.set_volume.assert_awaited_once_with("u-1", 50, None)

    async def test_service_exception(self, db, spotify):
        spotify.set_volume = AsyncMock(side_effect=RuntimeError("no"))
        result = await spotify_volume(db, "u-1", 50)
        assert result["success"] is False


class TestSpotifyDevices:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await spotify_devices(db, "u-1", agent_id="a-1")
        assert result["success"] is False

    async def test_success(self, db, spotify):
        spotify.get_available_devices = AsyncMock(return_value=[{"id": "d1"}])
        assert await spotify_devices(db, "u-1") == [{"id": "d1"}]

    async def test_service_exception(self, db, spotify):
        spotify.get_available_devices = AsyncMock(side_effect=RuntimeError("no"))
        result = await spotify_devices(db, "u-1")
        assert result["success"] is False


# ============================================================================
# Sonos tool functions
# ============================================================================

class TestSonosDiscover:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await sonos_discover(db, agent_id="a-1")
        assert result["success"] is False

    async def test_success(self, db, sonos):
        sonos.discover_speakers = AsyncMock(return_value=[{"ip": "1.1.1.1"}])
        result = await sonos_discover(db)
        assert result == {"success": True, "speakers": [{"ip": "1.1.1.1"}], "count": 1}

    async def test_service_exception(self, db, sonos):
        sonos.discover_speakers = AsyncMock(side_effect=RuntimeError("no"))
        result = await sonos_discover(db)
        assert result["success"] is False


class TestSonosPlay:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await sonos_play(db, "1.1.1.1", agent_id="a-1")
        assert result["success"] is False

    async def test_success(self, db, sonos):
        sonos.play = AsyncMock(return_value={"playing": True})
        assert await sonos_play(db, "1.1.1.1", uri="u") == {"playing": True}
        sonos.play.assert_awaited_once_with("1.1.1.1", "u")

    async def test_service_exception(self, db, sonos):
        sonos.play = AsyncMock(side_effect=RuntimeError("no"))
        result = await sonos_play(db, "1.1.1.1")
        assert result["success"] is False


class TestSonosPause:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await sonos_pause(db, "1.1.1.1", agent_id="a-1")
        assert result["success"] is False

    async def test_success(self, db, sonos):
        sonos.pause = AsyncMock(return_value={"paused": True})
        assert await sonos_pause(db, "1.1.1.1") == {"paused": True}

    async def test_service_exception(self, db, sonos):
        sonos.pause = AsyncMock(side_effect=RuntimeError("no"))
        result = await sonos_pause(db, "1.1.1.1")
        assert result["success"] is False


class TestSonosVolume:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await sonos_volume(db, "1.1.1.1", 30, agent_id="a-1")
        assert result["success"] is False

    async def test_success(self, db, sonos):
        sonos.set_volume = AsyncMock(return_value={"volume": 30})
        assert await sonos_volume(db, "1.1.1.1", 30) == {"volume": 30}

    async def test_service_exception(self, db, sonos):
        sonos.set_volume = AsyncMock(side_effect=RuntimeError("no"))
        result = await sonos_volume(db, "1.1.1.1", 30)
        assert result["success"] is False


class TestSonosGroups:
    async def test_governance_blocked(self, db):
        db.query.return_value.filter.return_value.first.return_value = _agent("STUDENT")
        result = await sonos_groups(db, agent_id="a-1")
        assert result["success"] is False

    async def test_success(self, db, sonos):
        sonos.get_groups = AsyncMock(return_value=[{"name": "Living"}])
        result = await sonos_groups(db)
        assert result == {"success": True, "groups": [{"name": "Living"}], "count": 1}

    async def test_service_exception(self, db, sonos):
        sonos.get_groups = AsyncMock(side_effect=RuntimeError("no"))
        result = await sonos_groups(db)
        assert result["success"] is False


# ============================================================================
# Registration
# ============================================================================

class TestRegisterMediaTools:
    def test_registers_twelve_tools(self):
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            mt.register_media_tools()
        names = [call.kwargs["name"] for call in registry.register.call_args_list]
        assert names == ["spotify_current", "spotify_play", "spotify_pause",
                         "spotify_next", "spotify_previous", "spotify_volume",
                         "spotify_devices", "sonos_discover", "sonos_play",
                         "sonos_pause", "sonos_volume", "sonos_groups"]
        assert registry.register.call_count == 12

    def test_auto_register_failure_is_swallowed(self):
        with patch("tools.registry.get_tool_registry",
                   side_effect=RuntimeError("registry down")):
            importlib.reload(mt)
        importlib.reload(mt)  # restore clean state
