"""Coverage-push + bug-hunt tests for backend/tools (part 3).

Covers: media_tool, smarthome_tool, productivity_tool (Notion), calendar_tool,
device_tool gap coverage.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@contextmanager
def _db_ctx(db):
    yield db


def _patch_db(db):
    return patch("core.database.get_db_session", side_effect=lambda: _db_ctx(db))


def _patch_tool_db(module, db):
    return patch(f"tools.{module}.get_db_session", side_effect=lambda: _db_ctx(db))


# ============================================================================
# media_tool
# ============================================================================

class TestMediaTool:
    @pytest.fixture(autouse=True)
    def _media_patch(self):
        self.spotify = MagicMock()
        self.spotify.get_current_track = AsyncMock(return_value={"success": True})
        self.spotify.play_track = AsyncMock(return_value={"success": True})
        self.spotify.pause_playback = AsyncMock(return_value={"success": True})
        self.spotify.skip_next = AsyncMock(return_value={"success": True})
        self.spotify.skip_previous = AsyncMock(return_value={"success": True})
        self.spotify.set_volume = AsyncMock(return_value={"success": True})
        self.spotify.get_available_devices = AsyncMock(return_value={"success": True})
        self.sonos = MagicMock()
        self.sonos.discover_speakers = AsyncMock(return_value=[{"ip": "1.2.3.4"}])
        self.sonos.play = AsyncMock(return_value={"success": True})
        self.sonos.pause = AsyncMock(return_value={"success": True})
        self.sonos.set_volume = AsyncMock(return_value={"success": True})
        self.sonos.get_groups = AsyncMock(return_value=[{"id": "g1"}])
        with patch("tools.media_tool.SpotifyService", return_value=self.spotify), \
             patch("tools.media_tool.SonosService", return_value=self.sonos):
            yield

    async def test_check_media_governance_no_agent(self):
        from tools.media_tool import _check_media_governance
        res = await _check_media_governance(Mock(), None, "spotify_play", "u-1")
        assert res["allowed"] is True

    async def test_check_media_governance_insufficient_maturity(self):
        resolver = MagicMock()
        resolver.resolve_agent_context = AsyncMock(return_value={"maturity_level": "STUDENT"})
        with patch("core.agent_context_resolver.AgentContextResolver", return_value=resolver):
            from tools.media_tool import _check_media_governance
            res = await _check_media_governance(Mock(), "a-1", "spotify_play", "u-1")
        assert res["allowed"] is False
        assert "insufficient" in res["reason"]

    async def test_check_media_governance_allowed(self):
        resolver = MagicMock()
        resolver.resolve_agent_context = AsyncMock(return_value={"maturity_level": "AUTONOMOUS"})
        gc = MagicMock()
        gc.check_permission = AsyncMock(return_value=True)
        with patch("core.agent_context_resolver.AgentContextResolver", return_value=resolver), \
             patch("tools.media_tool.AsyncGovernanceCache", return_value=gc):
            from tools.media_tool import _check_media_governance
            res = await _check_media_governance(Mock(), "a-1", "spotify_devices", "u-1")
        assert res["allowed"] is True

    async def test_check_media_governance_cache_denied(self):
        resolver = MagicMock()
        resolver.resolve_agent_context = AsyncMock(return_value={"maturity_level": "AUTONOMOUS"})
        gc = MagicMock()
        gc.check_permission = AsyncMock(return_value=False)
        with patch("core.agent_context_resolver.AgentContextResolver", return_value=resolver), \
             patch("tools.media_tool.AsyncGovernanceCache", return_value=gc):
            from tools.media_tool import _check_media_governance
            res = await _check_media_governance(Mock(), "a-1", "spotify_play", "u-1")
        assert res["allowed"] is False
        assert "Governance check failed" in res["reason"]

    async def test_check_media_governance_exception(self):
        resolver = MagicMock()
        resolver.resolve_agent_context = AsyncMock(side_effect=RuntimeError("x"))
        with patch("core.agent_context_resolver.AgentContextResolver", return_value=resolver):
            from tools.media_tool import _check_media_governance
            res = await _check_media_governance(Mock(), "a-1", "spotify_play", "u-1")
        assert res["allowed"] is False

    async def test_spotify_functions_success(self):
        from tools.media_tool import (
            spotify_current, spotify_devices, spotify_next, spotify_pause,
            spotify_play, spotify_previous, spotify_volume,
        )
        db = Mock()
        assert (await spotify_current(db, "u-1"))["success"] is True
        assert (await spotify_play(db, "u-1", track_uri="x", device_id="d"))["success"] is True
        assert (await spotify_pause(db, "u-1", device_id="d"))["success"] is True
        assert (await spotify_next(db, "u-1"))["success"] is True
        assert (await spotify_previous(db, "u-1"))["success"] is True
        assert (await spotify_volume(db, "u-1", 50))["success"] is True
        assert (await spotify_devices(db, "u-1"))["success"] is True

    async def test_spotify_blocked(self):
        with patch("tools.media_tool._check_media_governance",
                   AsyncMock(return_value={"allowed": False, "reason": "no"})):
            from tools.media_tool import spotify_current
            res = await spotify_current(Mock(), "u-1", agent_id="a-1")
        assert res["success"] is False and res["governance_blocked"] is True

    @pytest.mark.parametrize("fn_name,args,kwargs", [
        ("spotify_play", ("u-1",), {}),
        ("spotify_pause", ("u-1",), {}),
        ("spotify_next", ("u-1",), {}),
        ("spotify_previous", ("u-1",), {}),
        ("spotify_volume", ("u-1",), {"volume_percent": 50}),
        ("spotify_devices", ("u-1",), {}),
        ("sonos_play", (), {"speaker_ip": "1.2.3.4"}),
        ("sonos_pause", (), {"speaker_ip": "1.2.3.4"}),
        ("sonos_volume", (), {"speaker_ip": "1.2.3.4", "volume": 30}),
        ("sonos_groups", (), {}),
    ])
    async def test_functions_blocked_paths(self, fn_name, args, kwargs):
        import tools.media_tool as mt
        with patch("tools.media_tool._check_media_governance",
                   AsyncMock(return_value={"allowed": False, "reason": "no"})):
            res = await getattr(mt, fn_name)(Mock(), *args, agent_id="a-1", **kwargs)
        assert res["success"] is False and res["governance_blocked"] is True

    async def test_spotify_error(self):
        self.spotify.get_current_track.side_effect = RuntimeError("api down")
        from tools.media_tool import spotify_current
        res = await spotify_current(Mock(), "u-1")
        assert res["success"] is False

    @pytest.mark.parametrize("fn_name,svc_name,attr,args,kwargs", [
        ("spotify_play", "spotify", "play_track", ("u-1",), {}),
        ("spotify_pause", "spotify", "pause_playback", ("u-1",), {}),
        ("spotify_next", "spotify", "skip_next", ("u-1",), {}),
        ("spotify_previous", "spotify", "skip_previous", ("u-1",), {}),
        ("spotify_volume", "spotify", "set_volume", ("u-1",), {"volume_percent": 50}),
        ("spotify_devices", "spotify", "get_available_devices", ("u-1",), {}),
        ("sonos_play", "sonos", "play", (), {"speaker_ip": "1.2.3.4"}),
        ("sonos_pause", "sonos", "pause", (), {"speaker_ip": "1.2.3.4"}),
        ("sonos_volume", "sonos", "set_volume", (), {"speaker_ip": "1.2.3.4", "volume": 30}),
        ("sonos_groups", "sonos", "get_groups", (), {}),
    ])
    async def test_functions_error_paths(self, fn_name, svc_name, attr, args, kwargs):
        import tools.media_tool as mt
        svc = self.spotify if svc_name == "spotify" else self.sonos
        getattr(svc, attr).side_effect = RuntimeError("boom")
        res = await getattr(mt, fn_name)(Mock(), *args, **kwargs)
        assert res["success"] is False

    async def test_sonos_functions_success(self):
        from tools.media_tool import (
            sonos_discover, sonos_groups, sonos_pause, sonos_play, sonos_volume,
        )
        db = Mock()
        res = await sonos_discover(db)
        assert res["success"] is True and res["count"] == 1
        assert (await sonos_play(db, "1.2.3.4", uri="u"))["success"] is True
        assert (await sonos_pause(db, "1.2.3.4"))["success"] is True
        assert (await sonos_volume(db, "1.2.3.4", 30))["success"] is True
        res = await sonos_groups(db)
        assert res["success"] is True and res["count"] == 1

    async def test_sonos_blocked_and_error(self):
        from tools.media_tool import sonos_discover
        with patch("tools.media_tool._check_media_governance",
                   AsyncMock(return_value={"allowed": False, "reason": "no"})):
            res = await sonos_discover(Mock(), agent_id="a-1")
        assert res["governance_blocked"] is True
        self.sonos.discover_speakers.side_effect = RuntimeError("net")
        res2 = await sonos_discover(Mock())
        assert res2["success"] is False

    def test_register_media_tools(self):
        from tools.media_tool import register_media_tools
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            register_media_tools()
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert "spotify_play" in names and "sonos_groups" in names
        assert len(names) == 12


# ============================================================================
# smarthome_tool
# ============================================================================

class TestSmarthomeTool:
    @pytest.fixture(autouse=True)
    def _sh_patch(self):
        self.hue = MagicMock()
        self.hue.discover_bridges = AsyncMock(return_value=["192.168.1.2"])
        self.hue.get_all_lights = AsyncMock(return_value=[{"id": 1}])
        self.hue.set_light_state = AsyncMock(return_value={"on": True})
        self.ha = MagicMock()
        self.ha.get_states = AsyncMock(return_value=[{"entity_id": "light.x"}])
        self.ha.call_service = AsyncMock(return_value={"ok": True})
        self.ha.get_lights = AsyncMock(return_value=[{"entity_id": "light.y"}])
        self.ha.close = AsyncMock()
        with patch("tools.smarthome_tool.HueService", return_value=self.hue), \
             patch("tools.smarthome_tool.HomeAssistantService", return_value=self.ha), \
             patch("tools.smarthome_tool.FeatureFlags",
                   SimpleNamespace(SMART_HOME_CONTROL_ENABLED=True)):
            yield

    async def test_check_hue_permission(self):
        from tools.smarthome_tool import _check_hue_permission
        with patch("tools.smarthome_tool.FeatureFlags",
                   SimpleNamespace(SMART_HOME_CONTROL_ENABLED=False)):
            res = await _check_hue_permission("a-1", "u-1")
        assert res[0] is False and "disabled" in res[1]
        res = await _check_hue_permission(None, "u-1")
        assert res == (True, None)
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = {"allowed": True, "reason": None}
            res = await _check_hue_permission("a-1", "u-1")
        assert res[0] is True
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = None
            cache.set = Mock()
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                maturity_level="STUDENT")
            with _patch_tool_db("smarthome_tool", q):
                res = await _check_hue_permission("a-1", "u-1")
        assert res[0] is False and "SUPERVISED" in res[1]
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = None
            cache.set = Mock()
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                maturity_level="AUTONOMOUS")
            with _patch_tool_db("smarthome_tool", q):
                res = await _check_hue_permission("a-1", "u-1")
        assert res[0] is True

    async def test_check_hue_permission_not_found_and_error(self):
        from tools.smarthome_tool import _check_hue_permission
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = None
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = None
            with _patch_tool_db("smarthome_tool", q):
                res = await _check_hue_permission("a-1", "u-1")
        assert res[0] is False and "not found" in res[1]
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = None
            q = MagicMock()
            q.query.side_effect = RuntimeError("x")
            with _patch_tool_db("smarthome_tool", q):
                res = await _check_hue_permission("a-1", "u-1")
        assert res[0] is False

    async def test_hue_discover_bridges(self):
        from tools.smarthome_tool import hue_discover_bridges
        res = await hue_discover_bridges()
        assert res["success"] is True and res["count"] == 1
        with patch("tools.smarthome_tool._check_hue_permission",
                   AsyncMock(return_value=(False, "no"))):
            with pytest.raises(PermissionError):
                await hue_discover_bridges(agent_id="a-1")
        self.hue.discover_bridges.side_effect = RuntimeError("mdns down")
        res2 = await hue_discover_bridges()
        assert res2["success"] is False

    async def test_hue_get_lights(self):
        from tools.smarthome_tool import hue_get_lights
        res = await hue_get_lights(bridge_ip="1.2.3.4", api_key="k")
        assert res["success"] is True and res["count"] == 1
        with pytest.raises(ValueError):
            await hue_get_lights(bridge_ip=None, api_key="k")
        self.hue.get_all_lights.side_effect = RuntimeError("x")
        res2 = await hue_get_lights(bridge_ip="1.2.3.4", api_key="k")
        assert res2["success"] is False

    async def test_hue_set_light_state(self):
        from tools.smarthome_tool import hue_set_light_state
        res = await hue_set_light_state(bridge_ip="1.2.3.4", api_key="k", light_id="1",
                                        on=True, brightness=50, color_xy=(0.1, 0.2))
        assert res["success"] is True
        with pytest.raises(ValueError):
            await hue_set_light_state(bridge_ip="1.2.3.4", api_key="k")
        self.hue.set_light_state.side_effect = RuntimeError("x")
        res2 = await hue_set_light_state(bridge_ip="1.2.3.4", api_key="k", light_id="1")
        assert res2["success"] is False

    async def test_home_assistant_get_states(self):
        from tools.smarthome_tool import home_assistant_get_states
        res = await home_assistant_get_states(ha_url="http://ha", ha_token="tok")
        assert res["success"] is True and res["count"] == 1
        with pytest.raises(ValueError):
            await home_assistant_get_states(ha_url=None, ha_token="tok")
        self.ha.get_states.side_effect = RuntimeError("x")
        res2 = await home_assistant_get_states(ha_url="http://ha", ha_token="tok")
        assert res2["success"] is False

    async def test_home_assistant_call_service(self):
        from tools.smarthome_tool import home_assistant_call_service
        res = await home_assistant_call_service(ha_url="http://ha", ha_token="tok",
                                                domain="light", service="turn_on",
                                                entity_id="light.x", data={"x": 1})
        assert res["success"] is True
        with pytest.raises(ValueError):
            await home_assistant_call_service(ha_url="http://ha", ha_token="tok", domain="light")
        self.ha.call_service.side_effect = RuntimeError("x")
        res2 = await home_assistant_call_service(ha_url="http://ha", ha_token="tok",
                                                 domain="light", service="turn_on")
        assert res2["success"] is False

    async def test_home_assistant_get_lights(self):
        from tools.smarthome_tool import home_assistant_get_lights
        res = await home_assistant_get_lights(ha_url="http://ha", ha_token="tok")
        assert res["success"] is True and res["count"] == 1
        with pytest.raises(ValueError):
            await home_assistant_get_lights(ha_url=None, ha_token="tok")
        self.ha.get_lights.side_effect = RuntimeError("x")
        res2 = await home_assistant_get_lights(ha_url="http://ha", ha_token="tok")
        assert res2["success"] is False

    async def test_blocked_raises_permission_error(self):
        from tools.smarthome_tool import home_assistant_get_states
        with patch("tools.smarthome_tool._check_home_assistant_permission",
                   AsyncMock(return_value=(False, "no"))):
            with pytest.raises(PermissionError):
                await home_assistant_get_states(agent_id="a-1", ha_url="http://ha", ha_token="t")

    async def test_check_home_assistant_permission(self):
        from tools.smarthome_tool import _check_home_assistant_permission
        res = await _check_home_assistant_permission(None, "u-1")
        assert res == (True, None)
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = {"allowed": True, "reason": None}
            res = await _check_home_assistant_permission("a-1", "u-1")
        assert res[0] is True
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = None
            cache.set = Mock()
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                maturity_level="STUDENT")
            with _patch_tool_db("smarthome_tool", q):
                res = await _check_home_assistant_permission("a-1", "u-1")
        assert res[0] is False
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = None
            cache.set = Mock()
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                maturity_level="AUTONOMOUS")
            with _patch_tool_db("smarthome_tool", q):
                res = await _check_home_assistant_permission("a-1", "u-1")
        assert res[0] is True

    def test_register_smarthome_tools(self):
        from tools.smarthome_tool import register_smarthome_tools
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            register_smarthome_tools()
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert "hue_discover_bridges" in names and "home_assistant_get_lights" in names
        assert len(names) == 6

    async def test_flag_missing_from_feature_flags_defaults_to_enabled(self):
        from tools.smarthome_tool import _check_hue_permission
        with patch("tools.smarthome_tool.FeatureFlags", SimpleNamespace()):
            res = await _check_hue_permission(None, "u-1")
        assert res == (True, None)


# ============================================================================
# productivity_tool (Notion)
# ============================================================================

class TestProductivityTool:
    @pytest.fixture(autouse=True)
    def _notion_patch(self):
        self.service = MagicMock()
        self.service.search_workspace = AsyncMock(return_value=[{"id": 1}])
        self.service.list_databases = AsyncMock(return_value=[{"id": "db1"}])
        self.service.query_database = AsyncMock(return_value=[{"id": "p1"}])
        self.service.get_database_schema = AsyncMock(return_value={"cols": []})
        self.service.get_page = AsyncMock(return_value={"id": "p1"})
        self.service.get_page_blocks = AsyncMock(return_value=[{"id": "b1"}])
        self.service.create_page = AsyncMock(return_value={"id": "p2"})
        self.service.update_page = AsyncMock(return_value={"id": "p1"})
        self.service.append_page_blocks = AsyncMock(return_value={"ok": True})
        with patch("tools.productivity_tool.NotionService", return_value=self.service), \
             patch("tools.productivity_tool.LocalOnlyGuard") as self.guard_cls:
            self.guard_cls.return_value.allow_external_request = Mock()
            yield

    def _tool(self):
        from tools.productivity_tool import NotionTool
        return NotionTool()

    async def test_run_unknown_action(self):
        tool = self._tool()
        res = await tool.run("bogus")
        assert res["success"] is False

    async def test_run_human_no_permission_check(self):
        tool = self._tool()
        res = await tool.run("search", user_id="u-1", query="q")
        assert res["success"] is True and res["count"] == 1

    async def test_run_agent_permission_error(self):
        with patch.object(self._tool().__class__, "_check_notion_permission",
                           new=AsyncMock(return_value=(False, "denied"))):
            tool = self._tool()
            with pytest.raises(PermissionError):
                await tool.run("search", agent_id="a-1", user_id="u-1")

    async def test_run_agent_allowed_with_local_only_guard(self):
        with patch.object(self._tool().__class__, "_check_notion_permission",
                          new=AsyncMock(return_value=(True, None))):
            tool = self._tool()
            res = await tool.run("list_databases", agent_id="a-1", user_id="u-1")
        assert res["success"] is True and res["count"] == 1

    async def test_local_only_guard_blocked_real_check(self):
        from tools.productivity_tool import NotionTool
        tool = self._tool()
        guard = MagicMock()
        guard.allow_external_request.side_effect = RuntimeError("local-only mode")
        with patch("tools.productivity_tool._governance_cache") as cache, \
             patch("tools.productivity_tool.LocalOnlyGuard", return_value=guard), \
             _patch_tool_db("productivity_tool", MagicMock()):
            cache.get.return_value = None
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                maturity_level="AUTONOMOUS")
            with _patch_tool_db("productivity_tool", q):
                with pytest.raises(PermissionError):
                    await tool.run("list_databases", agent_id="a-1", user_id="u-1")

    async def test_run_execution_error(self):
        self.service.search_workspace.side_effect = RuntimeError("api down")
        tool = self._tool()
        res = await tool.run("search", user_id="u-1", query="q")
        assert res["success"] is False
        assert res["action"] == "search"

    async def test_check_notion_permission(self):
        from tools.productivity_tool import NotionTool
        check = NotionTool._check_notion_permission
        res = await check(None, None, "u-1", "search", "INTERN")
        assert res == (True, None)
        with patch("tools.productivity_tool._governance_cache") as cache:
            cache.get.return_value = {"allowed": True, "reason": None}
            res = await check(None, "a-1", "u-1", "search", "INTERN")
        assert res[0] is True
        with patch("tools.productivity_tool._governance_cache") as cache:
            cache.get.return_value = None
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = None
            with _patch_tool_db("productivity_tool", q):
                res = await check(None, "a-1", "u-1", "search", "INTERN")
        assert res[0] is False and "not found" in res[1]
        with patch("tools.productivity_tool._governance_cache") as cache:
            cache.get.return_value = None
            cache.set = Mock()
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                maturity_level="STUDENT")
            with _patch_tool_db("productivity_tool", q):
                res = await check(None, "a-1", "u-1", "search", "INTERN")
        assert res[0] is False and "requires" in res[1]
        with patch("tools.productivity_tool._governance_cache") as cache:
            cache.get.return_value = None
            cache.set = Mock()
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                maturity_level="INTERN")
            with _patch_tool_db("productivity_tool", q):
                res = await check(None, "a-1", "u-1", "search", "INTERN")
        assert res[0] is True
        with patch("tools.productivity_tool._governance_cache") as cache:
            cache.get.return_value = None
            q = MagicMock()
            q.query.side_effect = RuntimeError("x")
            with _patch_tool_db("productivity_tool", q):
                res = await check(None, "a-1", "u-1", "search", "INTERN")
        assert res[0] is False

    async def test_check_notion_permission_local_only_blocked(self):
        from tools.productivity_tool import NotionTool
        check = NotionTool._check_notion_permission
        with patch("tools.productivity_tool._governance_cache") as cache:
            cache.get.return_value = None
            q = MagicMock()
            q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                maturity_level="AUTONOMOUS")
            guard = MagicMock()
            guard.allow_external_request.side_effect = RuntimeError("local-only mode")
            with patch("tools.productivity_tool.LocalOnlyGuard", return_value=guard), \
                 _patch_tool_db("productivity_tool", q):
                res = await check(None, "a-1", "u-1", "search", "INTERN")
        assert res[0] is False

    async def test_execute_action_reads(self):
        tool = self._tool()
        res = await tool.run("search", user_id="u-1")
        assert res["success"] is False and "Query parameter required" in res["error"]
        res = await tool.run("search", user_id="u-1", query="x")
        assert res["success"] is True
        res = await tool.run("list_databases", user_id="u-1")
        assert res["success"] is True and res["count"] == 1
        res = await tool.run("query_database", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("query_database", user_id="u-1", database_id="db1",
                             filter='{"property": "x"}')
        assert res["success"] is True and res["count"] == 1
        res = await tool.run("query_database", user_id="u-1", database_id="db1",
                             filter="not json{")
        assert res["success"] is False and "Invalid filter JSON" in res["error"]
        res = await tool.run("query_database", user_id="u-1", database_id="db1",
                             filter={"p": 1})
        assert res["success"] is True
        res = await tool.run("get_schema", user_id="u-1", database_id="db1")
        assert res["success"] is True
        res = await tool.run("get_schema", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("get_page", user_id="u-1", page_id="p1")
        assert res["success"] is True
        res = await tool.run("get_page", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("get_blocks", user_id="u-1", page_id="p1")
        assert res["success"] is True and res["count"] == 1
        res = await tool.run("get_blocks", user_id="u-1")
        assert res["success"] is False

    async def test_execute_action_writes(self):
        tool = self._tool()
        res = await tool.run("create_page", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("create_page", user_id="u-1", database_id="db1")
        assert res["success"] is False
        res = await tool.run("create_page", user_id="u-1", database_id="db1",
                             properties='{"Name": {"title": [{"text": {"content": "x"}}]}}')
        assert res["success"] is True
        res = await tool.run("create_page", user_id="u-1", database_id="db1",
                             properties="bad json{")
        assert res["success"] is False
        res = await tool.run("update_page", user_id="u-1", page_id="p1", properties={"x": 1})
        assert res["success"] is True
        res = await tool.run("update_page", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("update_page", user_id="u-1", page_id="p1", properties="bad{")
        assert res["success"] is False
        res = await tool.run("append_blocks", user_id="u-1", page_id="p1",
                             blocks='[{"type": "paragraph"}]')
        assert res["success"] is True
        res = await tool.run("append_blocks", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("append_blocks", user_id="u-1", page_id="p1", blocks="bad{")
        assert res["success"] is False

    def test_register_notion_tool(self):
        registry = MagicMock()
        from tools.productivity_tool import register_notion_tool
        with patch("tools.productivity_tool.NotionTool"):
            register_notion_tool(registry)
        assert registry.register.call_args.kwargs["name"] == "notion_tool"


# ============================================================================
# calendar_tool
# ============================================================================

class TestCalendarTool:
    @pytest.fixture(autouse=True)
    def _cal_patch(self):
        self.service = MagicMock()
        self.service.authenticate = Mock(return_value=True)
        self.service.get_events = AsyncMock(return_value=[{"id": "e1"}])
        self.service.check_conflicts = AsyncMock(return_value={"conflicts": []})
        self.service.create_event = AsyncMock(return_value={"id": "e2"})
        self.service.update_event = AsyncMock(return_value={"id": "e1"})
        self.service.delete_event = AsyncMock(return_value=True)
        with patch("tools.calendar_tool.google_calendar_service", self.service), \
             patch("tools.calendar_tool._governance_cache") as self.cache:
            self.cache.get.return_value = None
            self.cache.set = Mock()
            yield

    def _tool(self):
        from tools.calendar_tool import CalendarTool
        return CalendarTool()

    def test_init_auth_failure(self):
        with patch("tools.calendar_tool.google_calendar_service") as svc:
            svc.authenticate.side_effect = RuntimeError("no creds")
            from tools.calendar_tool import CalendarTool
            CalendarTool()

    async def test_run_unknown_action(self):
        tool = self._tool()
        res = await tool.run("bogus")
        assert res["success"] is False and "available_actions" in res

    async def test_run_human_success(self):
        tool = self._tool()
        res = await tool.run("get_events", user_id="u-1")
        assert res["success"] is True and res["count"] == 1
        res = await tool.run("check_conflicts", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("check_conflicts", user_id="u-1",
                             start_time="2026-01-01T10:00:00", end_time="2026-01-01T11:00:00")
        assert res["action"] == "check_conflicts"
        res = await tool.run("create_event", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("create_event", user_id="u-1", title="T",
                             start_time="2026-01-01T10:00:00", end_time="2026-01-01T11:00:00",
                             description="d", location="l", attendees=["a@b"])
        assert res["success"] is True
        self.service.create_event.return_value = None
        res = await tool.run("create_event", user_id="u-1", title="T",
                             start_time="2026-01-01T10:00:00", end_time="2026-01-01T11:00:00")
        assert res["success"] is False
        self.service.create_event.return_value = {"id": "e2"}
        res = await tool.run("update_event", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("update_event", user_id="u-1", event_id="e1", updates={"title": "X"})
        assert res["success"] is True
        self.service.update_event.return_value = None
        res = await tool.run("update_event", user_id="u-1", event_id="e1", updates={"title": "X"})
        assert res["success"] is False
        self.service.update_event.return_value = {"id": "e1"}
        res = await tool.run("delete_event", user_id="u-1")
        assert res["success"] is False
        res = await tool.run("delete_event", user_id="u-1", event_id="e1")
        assert res["success"] is True
        self.service.authenticate.return_value = False
        res = await tool.run("get_events", user_id="u-1")
        assert res["success"] is False and "not authenticated" in res["error"]

    async def test_run_agent_permission_denied(self):
        from tools.calendar_tool import CalendarTool
        with patch.object(CalendarTool, "_check_calendar_permission",
                          new=AsyncMock(return_value=(False, "denied"))):
            from tools.calendar_tool import CalendarTool
            tool = CalendarTool()
            with pytest.raises(PermissionError):
                await tool.run("get_events", agent_id="a-1", user_id="u-1")

    async def test_run_execution_error(self):
        self.service.get_events.side_effect = RuntimeError("api")
        tool = self._tool()
        res = await tool.run("get_events", user_id="u-1")
        assert res["success"] is False and res["action"] == "get_events"

    async def test_check_calendar_permission(self):
        from tools.calendar_tool import CalendarTool
        check = CalendarTool._check_calendar_permission
        res = await check(None, None, "u-1", "get_events", "INTERN")
        assert res == (True, None)
        self.cache.get.return_value = {"allowed": True, "reason": None}
        res = await check(None, "a-1", "u-1", "get_events", "INTERN")
        assert res[0] is True
        self.cache.get.return_value = None
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = None
        with _patch_tool_db("calendar_tool", q):
            res = await check(None, "a-1", "u-1", "get_events", "INTERN")
        assert res[0] is False and "not found" in res[1]
        q2 = MagicMock()
        q2.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="STUDENT")
        with _patch_tool_db("calendar_tool", q2):
            res = await check(None, "a-1", "u-1", "create_event", "SUPERVISED")
        assert res[0] is False and "requires" in res[1]
        q3 = MagicMock()
        q3.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="AUTONOMOUS")
        with _patch_tool_db("calendar_tool", q3):
            res = await check(None, "a-1", "u-1", "create_event", "SUPERVISED")
        assert res[0] is True
        q4 = MagicMock()
        q4.query.side_effect = RuntimeError("x")
        with _patch_tool_db("calendar_tool", q4):
            res = await check(None, "a-1", "u-1", "get_events", "INTERN")
        assert res[0] is False

    async def test_get_events_parses_time_bounds(self):
        tool = self._tool()
        res = await tool.run("get_events", user_id="u-1", time_min="2026-01-01T00:00:00",
                             time_max="2026-01-08T00:00:00", max_results=50)
        assert res["success"] is True
        self.service.get_events.assert_awaited_once()

    def test_register_calendar_tool(self):
        registry = MagicMock()
        from tools.calendar_tool import register_calendar_tool
        with patch("tools.calendar_tool.CalendarTool"):
            register_calendar_tool(registry)
        assert registry.register.call_args.kwargs["name"] == "calendar_tool"


# ============================================================================
# device_tool (gap coverage)
# ============================================================================

class TestDeviceToolGaps:
    @pytest.fixture(autouse=True)
    def _device_patch(self):
        with patch("tools.device_tool.is_device_online", return_value=True), \
             patch("tools.device_tool.send_device_command",
                   AsyncMock(return_value={"success": True, "data": {}})) as send:
            self.send = send
            yield

    async def test_execute_device_command_unknown(self):
        from tools.device_tool import execute_device_command
        res = await execute_device_command(Mock(), "u-1", None, "d-1", "bogus", {})
        assert res["success"] is False and "Unknown command type" in res["error"]

    async def test_execute_device_command_camera_typeerror(self):
        from tools.device_tool import execute_device_command
        res = await execute_device_command(Mock(), "u-1", None, "d-1", "camera", {})
        assert res["success"] is False

    async def test_execute_device_command_location_typeerror(self):
        from tools.device_tool import execute_device_command
        res = await execute_device_command(Mock(), "u-1", None, "d-1", "location", {})
        assert res["success"] is False

    async def test_execute_device_command_notification_typeerror(self):
        from tools.device_tool import execute_device_command
        res = await execute_device_command(Mock(), "u-1", None, "d-1", "notification", {})
        assert res["success"] is False

    async def test_execute_device_command_command_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        from tools.device_tool import execute_device_command
        res = await execute_device_command(db, "u-1", None, "d-1", "command",
                                           {"command": "ls", "timeout": 5})
        assert res["success"] is False and "not found" in res["error"]

    async def test_execute_device_command_command_success(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            device_id="d-1")
        self.send.return_value = {"success": True, "data": {"exit_code": 0, "stdout": "ok"}}
        from tools.device_tool import execute_device_command
        res = await execute_device_command(db, "u-1", None, "d-1", "command",
                                           {"command": "ls", "timeout": 5})
        assert res["success"] is True and res["exit_code"] == 0

    async def test_get_device_info(self):
        from tools.device_tool import get_device_info
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        assert await get_device_info(db, "d-1") is None
        device = SimpleNamespace(id="1", device_id="d-1", name="Phone", node_type="mobile",
                                 status="online", platform="ios", platform_version="18",
                                 architecture="arm64", capabilities=["camera"],
                                 capabilities_detailed={}, hardware_info={},
                                 last_seen=datetime(2026, 1, 1))
        db.query.return_value.filter.return_value.first.return_value = device
        info = await get_device_info(db, "d-1")
        assert info["device_id"] == "d-1" and info["last_seen"] == "2026-01-01T00:00:00"

    async def test_list_devices(self):
        from tools.device_tool import list_devices
        db = MagicMock()
        q = MagicMock()
        q.all.return_value = []
        q.filter.return_value = q
        db.query.return_value.filter.return_value = q
        res = await list_devices(db, "u-1")
        assert res == []
        device = SimpleNamespace(id="1", device_id="d-1", name="Phone", node_type="mobile",
                                 status="online", platform="ios", capabilities=[],
                                 last_seen=None)
        q.all.return_value = [device]
        res = await list_devices(db, "u-1", status="online")
        assert res[0]["last_seen"] is None

    async def test_check_device_governance_disabled_and_allowed(self):
        from tools.device_tool import _check_device_governance
        with patch("tools.device_tool.FeatureFlags.should_enforce_governance",
                   return_value=False):
            res = await _check_device_governance(Mock(), "a-1", "device_camera_snap", "u-1")
        assert res["allowed"] is True
        with patch("tools.device_tool.FeatureFlags.should_enforce_governance",
                   return_value=True), \
             patch("tools.device_tool.ServiceFactory") as sf:
            gov = MagicMock()
            gov.can_perform_action.return_value = {"allowed": True, "reason": None}
            sf.get_governance_service.return_value = gov
            res = await _check_device_governance(Mock(), "a-1", "device_camera_snap", "u-1")
        assert res["allowed"] is True and res["governance_check_passed"] is True

    async def test_check_device_governance_error(self):
        from tools.device_tool import _check_device_governance
        with patch("tools.device_tool.FeatureFlags.should_enforce_governance",
                   return_value=True), \
             patch("tools.device_tool.ServiceFactory") as sf:
            sf.get_governance_service.side_effect = RuntimeError("x")
            res = await _check_device_governance(Mock(), "a-1", "device_camera_snap", "u-1")
        assert res["allowed"] is True
        assert res["governance_check_passed"] is False

    async def test_session_manager(self):
        from tools.device_tool import DeviceSessionManager
        mgr = DeviceSessionManager(session_timeout_minutes=0)
        session = mgr.create_session("u-1", "d-1", "screen_record", agent_id="a-1",
                                     configuration={"res": "1080p"})
        assert session["status"] == "active"
        assert mgr.get_session(session["session_id"]) is session
        assert mgr.get_session("nope") is None
        mgr.close_session("nope") is False
        assert mgr.close_session(session["session_id"]) is True
        assert mgr.get_session(session["session_id"]) is None
        fresh = mgr.create_session("u-1", "d-1", "screen_record")
        fresh["last_used"] = datetime(2020, 1, 1)
        assert mgr.cleanup_expired_sessions() == 1
        assert mgr.get_session(fresh["session_id"]) is None

    def test_get_device_session_manager_singleton(self):
        import tools.device_tool as dt
        dt._device_session_manager = None
        m1 = dt.get_device_session_manager()
        m2 = dt.get_device_session_manager()
        assert m1 is m2
