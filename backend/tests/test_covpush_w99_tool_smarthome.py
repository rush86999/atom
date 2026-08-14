# -*- coding: utf-8 -*-
"""Coverage wave 99 — tools/smarthome_tool.py (was 19%) + the
SMART_HOME_CONTROL_ENABLED FeatureFlags bug it depends on.

Bug found (RED -> GREEN): core/smarthome/hue_service.py:80 and
core/smarthome/home_assistant_service.py reference
FeatureFlags.SMART_HOME_CONTROL_ENABLED, which was never declared in
core/feature_flags.py — every HueService/HomeAssistantService construction
raised AttributeError (13 pre-existing failing tests in test_smarthome_tool.py).
The failing test below pins the flag's existence; the fix adds the flag with
the standard env-var default of True.

Coverage:
- _check_hue_permission / _check_home_assistant_permission: flag disabled,
  human action, cached allowed/denied, DB maturity allowed/denied, agent not
  found, exception.
- hue_discover_bridges / hue_get_lights / hue_set_light_state: permission
  denied -> PermissionError, missing args -> ValueError, success, service
  exception.
- home_assistant_get_states / home_assistant_call_service /
  home_assistant_get_lights: same matrix.
- register_smarthome_tools: 6 registrations through the ToolRegistry.

Fully mocked services, cache, and DB session. Zero network.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.feature_flags import FeatureFlags

from tools import smarthome_tool as st
from tools.smarthome_tool import (
    home_assistant_call_service,
    home_assistant_get_lights,
    home_assistant_get_states,
    hue_discover_bridges,
    hue_get_lights,
    hue_set_light_state,
)


# ============================================================================
# Bug pin: SMART_HOME_CONTROL_ENABLED must exist on FeatureFlags
# ============================================================================

def test_smart_home_control_feature_flag_exists():
    """RED test for the missing flag — hue_service/home_assistant_service
    reference FeatureFlags.SMART_HOME_CONTROL_ENABLED unconditionally."""
    assert hasattr(FeatureFlags, "SMART_HOME_CONTROL_ENABLED")


@pytest.fixture(autouse=True)
def _gov_cache():
    with patch.object(st, "_governance_cache", MagicMock()) as cache:
        cache.get.return_value = None
        yield cache


@pytest.fixture()
def hue_service():
    svc = MagicMock()
    with patch.object(st, "HueService", return_value=svc) as cls:
        cls.return_value = svc
        yield svc, cls


@pytest.fixture()
def ha_service():
    svc = MagicMock()
    with patch.object(st, "HomeAssistantService", return_value=svc) as cls:
        cls.return_value = svc
        yield svc, cls


class _DbCtx:
    """Context manager that yields a session whose query returns agent."""

    def __init__(self, agent):
        self._agent = agent

    def __enter__(self):
        session = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = self._agent
        session.query.return_value = q
        return session

    def __exit__(self, *a):
        return False


def _agent(maturity):
    a = MagicMock()
    a.maturity_level = maturity
    return a


# ============================================================================
# _check_hue_permission
# ============================================================================

class TestCheckHuePermission:
    async def test_flag_disabled(self, _gov_cache):
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            allowed, reason = await st._check_hue_permission("a-1", "u-1")
        assert allowed is False
        assert "disabled" in reason

    async def test_human_action_allowed(self, _gov_cache):
        allowed, reason = await st._check_hue_permission(None, "u-1")
        assert allowed is True
        assert reason is None

    async def test_cached_decision_used(self, _gov_cache):
        _gov_cache.get.return_value = {"allowed": False, "reason": "cached no"}
        allowed, reason = await st._check_hue_permission("a-1", "u-1")
        assert allowed is False
        assert reason == "cached no"
        _gov_cache.get.assert_called_once_with("a-1", "hue_control")

    async def test_agent_not_found(self, _gov_cache):
        with patch.object(st, "get_db_session", return_value=_DbCtx(None)):
            allowed, reason = await st._check_hue_permission("ghost", "u-1")
        assert allowed is False
        assert "ghost" in reason

    async def test_supervised_allowed(self, _gov_cache):
        with patch.object(st, "get_db_session", return_value=_DbCtx(_agent("SUPERVISED"))):
            allowed, reason = await st._check_hue_permission("a-1", "u-1")
        assert allowed is True
        assert reason is None
        _gov_cache.set.assert_called_once()

    async def test_intern_denied(self, _gov_cache):
        with patch.object(st, "get_db_session", return_value=_DbCtx(_agent("INTERN"))):
            allowed, reason = await st._check_hue_permission("a-1", "u-1")
        assert allowed is False
        assert "requires SUPERVISED+" in reason

    async def test_exception_fails_closed(self, _gov_cache):
        with patch.object(st, "get_db_session",
                          side_effect=RuntimeError("db down")):
            allowed, reason = await st._check_hue_permission("a-1", "u-1")
        assert allowed is False
        assert "Permission check failed" in reason


# ============================================================================
# Hue tool functions
# ============================================================================

class TestHueDiscoverBridges:
    async def test_permission_denied_raises(self, _gov_cache):
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await hue_discover_bridges(agent_id="a-1", user_id="u-1")

    async def test_success(self, _gov_cache, hue_service):
        svc, cls = hue_service
        svc.discover_bridges = AsyncMock(return_value=["192.168.1.50"])
        result = await hue_discover_bridges(agent_id=None, user_id="u-1")
        assert result == {"success": True, "bridges": ["192.168.1.50"], "count": 1,
                          "message": "Found 1 Hue bridge(s)"}

    async def test_service_exception(self, _gov_cache, hue_service):
        svc, cls = hue_service
        svc.discover_bridges = AsyncMock(side_effect=RuntimeError("no mdns"))
        result = await hue_discover_bridges()
        assert result["success"] is False
        assert "no mdns" in result["error"]


class TestHueGetLights:
    async def test_permission_denied_raises(self, _gov_cache):
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await hue_get_lights(agent_id="a-1", user_id="u-1")

    async def test_missing_args(self, _gov_cache):
        with pytest.raises(ValueError):
            await hue_get_lights(agent_id=None, user_id="u-1")

    async def test_success(self, _gov_cache, hue_service):
        svc, cls = hue_service
        svc.get_all_lights = AsyncMock(return_value=[{"id": "1", "name": "LR"}])
        result = await hue_get_lights(bridge_ip="1.2.3.4", api_key="k")
        assert result["success"] is True
        assert result["count"] == 1
        svc.get_all_lights.assert_awaited_once_with("1.2.3.4", "k")

    async def test_service_exception(self, _gov_cache, hue_service):
        svc, cls = hue_service
        svc.get_all_lights = AsyncMock(side_effect=RuntimeError("bridge off"))
        result = await hue_get_lights(bridge_ip="1.2.3.4", api_key="k")
        assert result["success"] is False


class TestHueSetLightState:
    async def test_permission_denied_raises(self, _gov_cache):
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await hue_set_light_state(agent_id="a-1", user_id="u-1")

    async def test_missing_args(self, _gov_cache):
        with pytest.raises(ValueError):
            await hue_set_light_state(bridge_ip="1.2.3.4", api_key="k")

    async def test_success(self, _gov_cache, hue_service):
        svc, cls = hue_service
        svc.set_light_state = AsyncMock(return_value={"on": True})
        result = await hue_set_light_state(bridge_ip="1.2.3.4", api_key="k",
                                           light_id="1", on=True, brightness=50,
                                           color_xy=(0.5, 0.5))
        assert result["success"] is True
        assert result["light"] == {"on": True}
        svc.set_light_state.assert_awaited_once_with("1.2.3.4", "k", "1", True, 50, (0.5, 0.5))

    async def test_service_exception(self, _gov_cache, hue_service):
        svc, cls = hue_service
        svc.set_light_state = AsyncMock(side_effect=RuntimeError("no"))
        result = await hue_set_light_state(bridge_ip="1.2.3.4", api_key="k", light_id="1")
        assert result["success"] is False


# ============================================================================
# _check_home_assistant_permission
# ============================================================================

class TestCheckHomeAssistantPermission:
    async def test_flag_disabled(self, _gov_cache):
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            allowed, reason = await st._check_home_assistant_permission("a-1", "u-1")
        assert allowed is False

    async def test_human_action_allowed(self, _gov_cache):
        allowed, reason = await st._check_home_assistant_permission(None, "u-1")
        assert allowed is True

    async def test_cached_denied(self, _gov_cache):
        _gov_cache.get.return_value = {"allowed": False, "reason": "no"}
        allowed, _ = await st._check_home_assistant_permission("a-1", "u-1")
        assert allowed is False
        _gov_cache.get.assert_called_once_with("a-1", "home_assistant_control")

    async def test_supervised_allowed(self, _gov_cache):
        with patch.object(st, "get_db_session", return_value=_DbCtx(_agent("AUTONOMOUS"))):
            allowed, reason = await st._check_home_assistant_permission("a-1", "u-1")
        assert allowed is True
        assert reason is None

    async def test_intern_denied(self, _gov_cache):
        with patch.object(st, "get_db_session", return_value=_DbCtx(_agent("INTERN"))):
            allowed, reason = await st._check_home_assistant_permission("a-1", "u-1")
        assert allowed is False
        assert "requires SUPERVISED+" in reason

    async def test_agent_not_found(self, _gov_cache):
        with patch.object(st, "get_db_session", return_value=_DbCtx(None)):
            allowed, reason = await st._check_home_assistant_permission("ghost", "u-1")
        assert allowed is False

    async def test_exception_fails_closed(self, _gov_cache):
        with patch.object(st, "get_db_session", side_effect=RuntimeError("down")):
            allowed, reason = await st._check_home_assistant_permission("a-1", "u-1")
        assert allowed is False


# ============================================================================
# Home Assistant tool functions
# ============================================================================

class TestHomeAssistantGetStates:
    async def test_permission_denied_raises(self, _gov_cache):
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await home_assistant_get_states(agent_id="a-1", user_id="u-1")

    async def test_missing_args(self, _gov_cache):
        with pytest.raises(ValueError):
            await home_assistant_get_states()

    async def test_success(self, _gov_cache, ha_service):
        svc, cls = ha_service
        svc.get_states = AsyncMock(return_value=[{"entity_id": "light.x"}])
        svc.close = AsyncMock()
        result = await home_assistant_get_states(ha_url="http://ha", ha_token="t")
        assert result["success"] is True
        assert result["count"] == 1
        svc.close.assert_awaited_once()

    async def test_service_exception(self, _gov_cache, ha_service):
        svc, cls = ha_service
        svc.get_states = AsyncMock(side_effect=RuntimeError("ha down"))
        result = await home_assistant_get_states(ha_url="http://ha", ha_token="t")
        assert result["success"] is False


class TestHomeAssistantCallService:
    async def test_permission_denied_raises(self, _gov_cache):
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await home_assistant_call_service(agent_id="a-1", user_id="u-1")

    async def test_missing_args(self, _gov_cache):
        with pytest.raises(ValueError):
            await home_assistant_call_service(ha_url="http://ha", ha_token="t")

    async def test_success(self, _gov_cache, ha_service):
        svc, cls = ha_service
        svc.call_service = AsyncMock(return_value={"ok": True})
        svc.close = AsyncMock()
        result = await home_assistant_call_service(ha_url="http://ha", ha_token="t",
                                                   domain="light", service="turn_on",
                                                   entity_id="light.x", data={"b": 1})
        assert result["success"] is True
        assert result["result"] == {"ok": True}
        svc.call_service.assert_awaited_once_with("light", "turn_on", "light.x", {"b": 1})

    async def test_service_exception(self, _gov_cache, ha_service):
        svc, cls = ha_service
        svc.call_service = AsyncMock(side_effect=RuntimeError("no"))
        result = await home_assistant_call_service(ha_url="http://ha", ha_token="t",
                                                   domain="light", service="turn_on")
        assert result["success"] is False


class TestHomeAssistantGetLights:
    async def test_permission_denied_raises(self, _gov_cache):
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await home_assistant_get_lights(agent_id="a-1", user_id="u-1")

    async def test_missing_args(self, _gov_cache):
        with pytest.raises(ValueError):
            await home_assistant_get_lights()

    async def test_success(self, _gov_cache, ha_service):
        svc, cls = ha_service
        svc.get_lights = AsyncMock(return_value=[{"entity_id": "light.a"}])
        svc.close = AsyncMock()
        result = await home_assistant_get_lights(ha_url="http://ha", ha_token="t")
        assert result["success"] is True
        assert result["count"] == 1

    async def test_service_exception(self, _gov_cache, ha_service):
        svc, cls = ha_service
        svc.get_lights = AsyncMock(side_effect=RuntimeError("no"))
        result = await home_assistant_get_lights(ha_url="http://ha", ha_token="t")
        assert result["success"] is False


# ============================================================================
# Registration
# ============================================================================

class TestRegisterSmarthomeTools:
    def test_registers_six_tools(self):
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            st.register_smarthome_tools()
        names = [call.kwargs["name"] for call in registry.register.call_args_list]
        assert names == ["hue_discover_bridges", "hue_get_lights", "hue_set_light_state",
                         "home_assistant_get_states", "home_assistant_call_service",
                         "home_assistant_get_lights"]
        assert registry.register.call_count == 6

    def test_auto_register_failure_is_swallowed(self):
        # Re-import executes the module-level try/except; a failing registry
        # must log a warning, not raise.
        import importlib
        with patch("tools.registry.get_tool_registry",
                   side_effect=RuntimeError("registry down")):
            importlib.reload(st)
        importlib.reload(st)  # restore clean state (registry OK again)
