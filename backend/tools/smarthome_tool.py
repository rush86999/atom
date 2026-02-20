# -*- coding: utf-8 -*-
"""
Smart Home Control Tool

**✅ REAL IMPLEMENTATION**

Provides Philips Hue and Home Assistant control for AI agents with governance integration.
- Local-only execution (no cloud relay)
- Hue light control: on/off, brightness, color, scenes
- Home Assistant entity control: states, services, automations
- SUPERVISED+ maturity level required
- Full audit trail for all device control actions

Architecture:
- Agent -> SmartHomeTool -> HueService/HomeAssistantService -> Local Devices
- Governance check via GovernanceCache before all operations
- Encrypted credential storage via database models
- Audit trail via HueBridge/HomeAssistantConnection models

Governance:
- STUDENT and INTERN agents BLOCKED from smart home control
- SUPERVISED and AUTONOMOUS agents can control devices
- All actions logged with entity identification for accountability
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.governance_cache import GovernanceCache
from core.models import AgentRegistry, User
from core.smarthome.hue_service import HueService
from core.smarthome.home_assistant_service import HomeAssistantService
from core.feature_flags import FeatureFlags
from core.structured_logger import get_logger

logger = get_logger(__name__)

# Initialize governance cache
_governance_cache = GovernanceCache()


# ============================================================================
# Hue Control Functions
# ============================================================================

async def _check_hue_permission(
    agent_id: Optional[str],
    user_id: str
) -> Tuple[bool, Optional[str]]:
    """
    Check if agent has permission for Hue control.

    Args:
        agent_id: Agent ID (None if human-triggered)
        user_id: User ID

    Returns:
        (allowed, reason) tuple
    """
    if not FeatureFlags.SMART_HOME_CONTROL_ENABLED:
        return False, "Smart home control is disabled via feature flag"

    # If no agent_id, it's a human-triggered action (allow)
    if not agent_id:
        return True, None

    # Check governance cache
    cached = _governance_cache.get(agent_id, "hue_control")
    if cached:
        return cached.get("allowed", False), cached.get("reason")

    # Check agent maturity level from database
    try:
        with get_db_session() as db:
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                return False, f"Agent '{agent_id}' not found"

            # Map maturity to allowed
            maturity = agent.maturity_level
            allowed = maturity in ["SUPERVISED", "AUTONOMOUS"]

            reason = None
            if not allowed:
                reason = f"Hue control requires SUPERVISED+ maturity (agent is {maturity})"

            # Cache decision
            _governance_cache.set(agent_id, "hue_control", {
                "allowed": allowed,
                "reason": reason,
                "maturity": maturity
            })

            return allowed, reason

    except Exception as e:
        logger.error("Failed to check Hue permission", agent_id=agent_id, error=str(e))
        return False, f"Permission check failed: {e}"


async def hue_discover_bridges(
    agent_id: Optional[str] = None,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Discover Philips Hue bridges on local network.

    Args:
        agent_id: Agent ID (if agent-triggered)
        user_id: User ID

    Returns:
        Discovery result with bridge IPs

    Raises:
        PermissionError: If agent lacks SUPERVISED maturity
    """
    user_id = user_id or "default"

    # Check governance
    allowed, reason = await _check_hue_permission(agent_id, user_id)
    if not allowed:
        logger.warning("Hue bridge discovery blocked", agent_id=agent_id, reason=reason)
        raise PermissionError(reason)

    try:
        service = HueService()
        bridge_ips = await service.discover_bridges()

        logger.info("Hue bridge discovery successful", agent_id=agent_id, bridge_count=len(bridge_ips))

        return {
            "success": True,
            "bridges": bridge_ips,
            "count": len(bridge_ips),
            "message": f"Found {len(bridge_ips)} Hue bridge(s)"
        }

    except Exception as e:
        logger.error("Hue bridge discovery failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to discover Hue bridges"
        }


async def hue_get_lights(
    agent_id: Optional[str] = None,
    user_id: str = None,
    bridge_ip: str = None,
    api_key: str = None
) -> Dict[str, Any]:
    """
    Get all lights from Hue bridge.

    Args:
        agent_id: Agent ID (if agent-triggered)
        user_id: User ID
        bridge_ip: Hue bridge IP address
        api_key: Hue API v2 key

    Returns:
        List of lights with id, name, on, brightness, color

    Raises:
        PermissionError: If agent lacks SUPERVISED maturity
        ValueError: If bridge_ip or api_key missing
    """
    user_id = user_id or "default"

    # Check governance
    allowed, reason = await _check_hue_permission(agent_id, user_id)
    if not allowed:
        logger.warning("Hue get_lights blocked", agent_id=agent_id, reason=reason)
        raise PermissionError(reason)

    if not bridge_ip or not api_key:
        raise ValueError("bridge_ip and api_key are required")

    try:
        service = HueService()
        lights = await service.get_all_lights(bridge_ip, api_key)

        logger.info("Hue get_lights successful", agent_id=agent_id, light_count=len(lights))

        return {
            "success": True,
            "lights": lights,
            "count": len(lights),
            "message": f"Retrieved {len(lights)} light(s)"
        }

    except Exception as e:
        logger.error("Hue get_lights failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get Hue lights"
        }


async def hue_set_light_state(
    agent_id: Optional[str] = None,
    user_id: str = None,
    bridge_ip: str = None,
    api_key: str = None,
    light_id: str = None,
    on: Optional[bool] = None,
    brightness: Optional[float] = None,
    color_xy: Optional[Tuple[float, float]] = None
) -> Dict[str, Any]:
    """
    Set state of a Hue light.

    Args:
        agent_id: Agent ID (if agent-triggered)
        user_id: User ID
        bridge_ip: Hue bridge IP address
        api_key: Hue API v2 key
        light_id: Light ID (e.g., "1", "2", "3")
        on: Turn on/off (None = no change)
        brightness: Brightness 0-100 (None = no change)
        color_xy: Color XY coordinates (None = no change)

    Returns:
        Updated light state

    Raises:
        PermissionError: If agent lacks SUPERVISED maturity
        ValueError: If required parameters missing
    """
    user_id = user_id or "default"

    # Check governance
    allowed, reason = await _check_hue_permission(agent_id, user_id)
    if not allowed:
        logger.warning("Hue set_light_state blocked", agent_id=agent_id, reason=reason)
        raise PermissionError(reason)

    if not bridge_ip or not api_key or not light_id:
        raise ValueError("bridge_ip, api_key, and light_id are required")

    try:
        service = HueService()
        light_state = await service.set_light_state(
            bridge_ip, api_key, light_id, on, brightness, color_xy
        )

        logger.info("Hue set_light_state successful", agent_id=agent_id, light_id=light_id)

        return {
            "success": True,
            "light": light_state,
            "message": f"Light '{light_id}' state updated"
        }

    except Exception as e:
        logger.error("Hue set_light_state failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to set light '{light_id}' state"
        }


# ============================================================================
# Home Assistant Control Functions
# ============================================================================

async def _check_home_assistant_permission(
    agent_id: Optional[str],
    user_id: str
) -> Tuple[bool, Optional[str]]:
    """
    Check if agent has permission for Home Assistant control.

    Args:
        agent_id: Agent ID (None if human-triggered)
        user_id: User ID

    Returns:
        (allowed, reason) tuple
    """
    if not FeatureFlags.SMART_HOME_CONTROL_ENABLED:
        return False, "Smart home control is disabled via feature flag"

    # If no agent_id, it's a human-triggered action (allow)
    if not agent_id:
        return True, None

    # Check governance cache
    cached = _governance_cache.get(agent_id, "home_assistant_control")
    if cached:
        return cached.get("allowed", False), cached.get("reason")

    # Check agent maturity level from database
    try:
        with get_db_session() as db:
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                return False, f"Agent '{agent_id}' not found"

            # Map maturity to allowed
            maturity = agent.maturity_level
            allowed = maturity in ["SUPERVISED", "AUTONOMOUS"]

            reason = None
            if not allowed:
                reason = f"Home Assistant control requires SUPERVISED+ maturity (agent is {maturity})"

            # Cache decision
            _governance_cache.set(agent_id, "home_assistant_control", {
                "allowed": allowed,
                "reason": reason,
                "maturity": maturity
            })

            return allowed, reason

    except Exception as e:
        logger.error("Failed to check Home Assistant permission", agent_id=agent_id, error=str(e))
        return False, f"Permission check failed: {e}"


async def home_assistant_get_states(
    agent_id: Optional[str] = None,
    user_id: str = None,
    ha_url: str = None,
    ha_token: str = None
) -> Dict[str, Any]:
    """
    Get all entity states from Home Assistant.

    Args:
        agent_id: Agent ID (if agent-triggered)
        user_id: User ID
        ha_url: Home Assistant URL
        ha_token: Long-lived access token

    Returns:
        List of entity states

    Raises:
        PermissionError: If agent lacks SUPERVISED maturity
    """
    user_id = user_id or "default"

    # Check governance
    allowed, reason = await _check_home_assistant_permission(agent_id, user_id)
    if not allowed:
        logger.warning("Home Assistant get_states blocked", agent_id=agent_id, reason=reason)
        raise PermissionError(reason)

    if not ha_url or not ha_token:
        raise ValueError("ha_url and ha_token are required")

    try:
        service = HomeAssistantService(ha_url, ha_token)
        states = await service.get_states()
        await service.close()

        logger.info("Home Assistant get_states successful", agent_id=agent_id, entity_count=len(states))

        return {
            "success": True,
            "states": states,
            "count": len(states),
            "message": f"Retrieved {len(states)} entity states"
        }

    except Exception as e:
        logger.error("Home Assistant get_states failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get entity states"
        }


async def home_assistant_call_service(
    agent_id: Optional[str] = None,
    user_id: str = None,
    ha_url: str = None,
    ha_token: str = None,
    domain: str = None,
    service: str = None,
    entity_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Call a Home Assistant service.

    Args:
        agent_id: Agent ID (if agent-triggered)
        user_id: User ID
        ha_url: Home Assistant URL
        ha_token: Long-lived access token
        domain: Domain (e.g., "light", "switch")
        service: Service name (e.g., "turn_on", "turn_off")
        entity_id: Entity ID (optional)
        data: Service data (optional)

    Returns:
        Service call result

    Raises:
        PermissionError: If agent lacks SUPERVISED maturity
    """
    user_id = user_id or "default"

    # Check governance
    allowed, reason = await _check_home_assistant_permission(agent_id, user_id)
    if not allowed:
        logger.warning("Home Assistant call_service blocked", agent_id=agent_id, reason=reason)
        raise PermissionError(reason)

    if not ha_url or not ha_token or not domain or not service:
        raise ValueError("ha_url, ha_token, domain, and service are required")

    try:
        service = HomeAssistantService(ha_url, ha_token)
        result = await service.call_service(domain, service, entity_id, data)
        await service.close()

        logger.info("Home Assistant call_service successful", agent_id=agent_id, domain=domain, service=service)

        return {
            "success": True,
            "result": result,
            "message": f"Service '{domain}.{service}' called successfully"
        }

    except Exception as e:
        logger.error("Home Assistant call_service failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to call service '{domain}.{service}'"
        }


async def home_assistant_get_lights(
    agent_id: Optional[str] = None,
    user_id: str = None,
    ha_url: str = None,
    ha_token: str = None
) -> Dict[str, Any]:
    """
    Get all light entities from Home Assistant.

    Args:
        agent_id: Agent ID (if agent-triggered)
        user_id: User ID
        ha_url: Home Assistant URL
        ha_token: Long-lived access token

    Returns:
        List of light entity states
    """
    user_id = user_id or "default"

    # Check governance
    allowed, reason = await _check_home_assistant_permission(agent_id, user_id)
    if not allowed:
        logger.warning("Home Assistant get_lights blocked", agent_id=agent_id, reason=reason)
        raise PermissionError(reason)

    if not ha_url or not ha_token:
        raise ValueError("ha_url and ha_token are required")

    try:
        service = HomeAssistantService(ha_url, ha_token)
        lights = await service.get_lights()
        await service.close()

        logger.info("Home Assistant get_lights successful", agent_id=agent_id, light_count=len(lights))

        return {
            "success": True,
            "lights": lights,
            "count": len(lights),
            "message": f"Retrieved {len(lights)} light(s)"
        }

    except Exception as e:
        logger.error("Home Assistant get_lights failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get lights"
        }


# ============================================================================
# Tool Registration
# ============================================================================

def register_smarthome_tools():
    """
    Register smart home tools with ToolRegistry.

    This function should be called during application startup to register
    all smart home control functions with the tool registry for agent use.
    """
    from tools.registry import tool_registry

    # Register Hue tools
    tool_registry.register(
        name="hue_discover_bridges",
        function=hue_discover_bridges,
        version="1.0.0",
        description="Discover Philips Hue bridges on local network via mDNS. Requires SUPERVISED+ maturity.",
        category="smarthome",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["hue", "philips-hue", "discovery", "smarthome", "home"]
    )

    tool_registry.register(
        name="hue_get_lights",
        function=hue_get_lights,
        version="1.0.0",
        description="Get all Philips Hue lights with state (on/off, brightness, color). Requires SUPERVISED+ maturity.",
        category="smarthome",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["hue", "philips-hue", "lights", "smarthome", "home"]
    )

    tool_registry.register(
        name="hue_set_light_state",
        function=hue_set_light_state,
        version="1.0.0",
        description="Set Philips Hue light state (on/off, brightness 0-100, color XY coordinates). Requires SUPERVISED+ maturity.",
        category="smarthome",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["hue", "philips-hue", "lights", "control", "smarthome", "home"]
    )

    # Register Home Assistant tools
    tool_registry.register(
        name="home_assistant_get_states",
        function=home_assistant_get_states,
        version="1.0.0",
        description="Get all entity states from Home Assistant. Requires SUPERVISED+ maturity.",
        category="smarthome",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["home-assistant", "states", "smarthome", "home", "automation"]
    )

    tool_registry.register(
        name="home_assistant_call_service",
        function=home_assistant_call_service,
        version="1.0.0",
        description="Call Home Assistant service (e.g., light.turn_on, switch.turn_off, automation.trigger). Requires SUPERVISED+ maturity.",
        category="smarthome",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["home-assistant", "services", "control", "smarthome", "home", "automation"]
    )

    tool_registry.register(
        name="home_assistant_get_lights",
        function=home_assistant_get_lights,
        version="1.0.0",
        description="Get all light entities from Home Assistant. Requires SUPERVISED+ maturity.",
        category="smarthome",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["home-assistant", "lights", "smarthome", "home"]
    )

    logger.info("Smart home tools registered with ToolRegistry")


# Auto-register on import
try:
    register_smarthome_tools()
except Exception as e:
    logger.warning(f"Failed to auto-register smart home tools: {e}")
