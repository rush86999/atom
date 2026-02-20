"""
Media Control Tool

Provides LangChain-style tool interface for Spotify and Sonos media control.
Integrates with agent governance system for maturity-based access control.

Features:
- Spotify playback control (play, pause, skip, volume)
- Sonos speaker control (play, pause, volume, groups)
- Governance enforcement (SUPERVISED+ maturity required)
- Audit trail for all media operations

Governance:
- Spotify: SUPERVISED+ maturity level
- Sonos: SUPERVISED+ maturity level
- STUDENT and INTERN agents blocked
"""

import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from core.governance_cache import AsyncGovernanceCache
from core.media.spotify_service import SpotifyService
from core.media.sonos_service import SonosService
from core.structured_logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Governance Check Helper
# ============================================================================

async def _check_media_governance(
    db: Session,
    agent_id: Optional[str],
    action: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Check if agent has permission to perform media control action.

    Args:
        db: Database session
        agent_id: Agent ID (None if human action)
        action: Action being performed (e.g., "spotify_play", "sonos_pause")
        user_id: User requesting action

    Returns:
        Dict with allowed (bool) and reason (str)
    """
    # Human actions (no agent_id) are always allowed
    if not agent_id:
        return {
            "allowed": True,
            "reason": "Human action",
            "governance_check_passed": True
        }

    # Check governance cache
    try:
        # Get agent maturity level
        from core.agent_context_resolver import AgentContextResolver
        resolver = AgentContextResolver(db)
        agent_context = await resolver.resolve_agent_context(agent_id)

        maturity_level = agent_context.get("maturity_level", "STUDENT")

        # Map media actions to maturity requirements
        maturity_requirements = {
            "spotify_current": "SUPERVISED",
            "spotify_play": "SUPERVISED",
            "spotify_pause": "SUPERVISED",
            "spotify_next": "SUPERVISED",
            "spotify_previous": "SUPERVISED",
            "spotify_volume": "SUPERVISED",
            "spotify_devices": "INTERN",  # Read-only, lower barrier
            "sonos_discover": "INTERN",  # Read-only, lower barrier
            "sonos_play": "SUPERVISED",
            "sonos_pause": "SUPERVISED",
            "sonos_volume": "SUPERVISED",
            "sonos_next": "SUPERVISED",
            "sonos_previous": "SUPERVISED",
            "sonos_groups": "INTERN",  # Read-only, lower barrier
            "sonos_join": "SUPERVISED",
            "sonos_leave": "SUPERVISED",
        }

        required_maturity = maturity_requirements.get(action, "SUPERVISED")

        # Check maturity hierarchy
        maturity_order = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
        current_level = maturity_order.index(maturity_level)
        required_level = maturity_order.index(required_maturity)

        if current_level < required_level:
            return {
                "allowed": False,
                "reason": f"Agent maturity {maturity_level} insufficient for {action}. Requires {required_maturity}+.",
                "governance_check_passed": False,
                "current_maturity": maturity_level,
                "required_maturity": required_maturity
            }

        # Check governance cache for tool-specific permission
        gc = AsyncGovernanceCache(db)
        has_permission = await gc.check_permission(
            agent_id=agent_id,
            tool_name=action,
            maturity_level=maturity_level
        )

        if not has_permission:
            return {
                "allowed": False,
                "reason": f"Governance check failed for {action}",
                "governance_check_passed": False,
                "maturity_level": maturity_level
            }

        return {
            "allowed": True,
            "reason": "Governance check passed",
            "governance_check_passed": True,
            "maturity_level": maturity_level
        }

    except Exception as e:
        logger.error(f"Governance check failed for {action}: {e}")
        # Fail open for human operations, fail closed for agents
        if agent_id:
            return {
                "allowed": False,
                "reason": f"Governance check error: {str(e)}",
                "governance_check_passed": False
            }
        return {
            "allowed": True,
            "reason": "Human action (governance check failed)",
            "governance_check_passed": False
        }


# ============================================================================
# Spotify Control Functions
# ============================================================================

async def spotify_current(
    db: Session,
    user_id: str,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get currently playing track from Spotify.

    Action Complexity: 2 (MODERATE)
    Maturity Required: SUPERVISED+

    Args:
        db: Database session
        user_id: User ID for Spotify account
        agent_id: Agent ID (for governance)

    Returns:
        Dict with current track info (artist, name, album, is_playing)
    """
    governance_check = await _check_media_governance(db, agent_id, "spotify_current", user_id)
    if not governance_check["allowed"]:
        return {
            "success": False,
            "error": governance_check["reason"],
            "governance_blocked": True
        }

    try:
        spotify_service = SpotifyService(db)
        result = await spotify_service.get_current_track(user_id)

        logger.info(f"Retrieved current track for user {user_id}")
        return result

    except Exception as e:
        logger.error(f"Failed to get current track for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def spotify_play(
    db: Session,
    user_id: str,
    agent_id: Optional[str] = None,
    track_uri: Optional[str] = None,
    device_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Play track or resume playback on Spotify.

    Action Complexity: 2 (MODERATE)
    Maturity Required: SUPERVISED+

    Args:
        db: Database session
        user_id: User ID for Spotify account
        agent_id: Agent ID (for governance)
        track_uri: Spotify track URI (optional, resumes if None)
        device_id: Target device ID (optional)

    Returns:
        Dict with playback status
    """
    governance_check = await _check_media_governance(db, agent_id, "spotify_play", user_id)
    if not governance_check["allowed"]:
        return {
            "success": False,
            "error": governance_check["reason"],
            "governance_blocked": True
        }

    try:
        spotify_service = SpotifyService(db)
        result = await spotify_service.play_track(user_id, track_uri, device_id)

        logger.info(f"Started Spotify playback for user {user_id} (track={track_uri})")
        return result

    except Exception as e:
        logger.error(f"Failed to play track for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def spotify_pause(
    db: Session,
    user_id: str,
    agent_id: Optional[str] = None,
    device_id: Optional[str] = None
) -> Dict[str, Any]:
    """Pause Spotify playback."""
    governance_check = await _check_media_governance(db, agent_id, "spotify_pause", user_id)
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        spotify_service = SpotifyService(db)
        result = await spotify_service.pause_playback(user_id, device_id)
        logger.info(f"Paused Spotify playback for user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to pause Spotify for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


async def spotify_next(
    db: Session,
    user_id: str,
    agent_id: Optional[str] = None,
    device_id: Optional[str] = None
) -> Dict[str, Any]:
    """Skip to next track on Spotify."""
    governance_check = await _check_media_governance(db, agent_id, "spotify_next", user_id)
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        spotify_service = SpotifyService(db)
        result = await spotify_service.skip_next(user_id, device_id)
        logger.info(f"Skipped to next track for user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to skip next for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


async def spotify_previous(
    db: Session,
    user_id: str,
    agent_id: Optional[str] = None,
    device_id: Optional[str] = None
) -> Dict[str, Any]:
    """Skip to previous track on Spotify."""
    governance_check = await _check_media_governance(db, agent_id, "spotify_previous", user_id)
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        spotify_service = SpotifyService(db)
        result = await spotify_service.skip_previous(user_id, device_id)
        logger.info(f"Skipped to previous track for user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to skip previous for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


async def spotify_volume(
    db: Session,
    user_id: str,
    volume_percent: int,
    agent_id: Optional[str] = None,
    device_id: Optional[str] = None
) -> Dict[str, Any]:
    """Set Spotify volume."""
    governance_check = await _check_media_governance(db, agent_id, "spotify_volume", user_id)
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        spotify_service = SpotifyService(db)
        result = await spotify_service.set_volume(user_id, volume_percent, device_id)
        logger.info(f"Set Spotify volume to {volume_percent}% for user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to set volume for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


async def spotify_devices(
    db: Session,
    user_id: str,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """Get available Spotify devices."""
    governance_check = await _check_media_governance(db, agent_id, "spotify_devices", user_id)
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        spotify_service = SpotifyService(db)
        result = await spotify_service.get_available_devices(user_id)
        logger.info(f"Retrieved Spotify devices for user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to get devices for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# Sonos Control Functions
# ============================================================================

async def sonos_discover(
    db: Session,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """Discover Sonos speakers on local network."""
    governance_check = await _check_media_governance(db, agent_id, "sonos_discover", "system")
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        sonos_service = SonosService()
        speakers = await sonos_service.discover_speakers()
        logger.info(f"Discovered {len(speakers)} Sonos speakers")
        return {"success": True, "speakers": speakers, "count": len(speakers)}
    except Exception as e:
        logger.error(f"Failed to discover Sonos speakers: {e}")
        return {"success": False, "error": str(e)}


async def sonos_play(
    db: Session,
    speaker_ip: str,
    agent_id: Optional[str] = None,
    uri: Optional[str] = None
) -> Dict[str, Any]:
    """Play audio or resume playback on Sonos speaker."""
    governance_check = await _check_media_governance(db, agent_id, "sonos_play", "system")
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        sonos_service = SonosService()
        result = await sonos_service.play(speaker_ip, uri)
        logger.info(f"Started playback on Sonos speaker {speaker_ip}")
        return result
    except Exception as e:
        logger.error(f"Failed to play on Sonos speaker {speaker_ip}: {e}")
        return {"success": False, "error": str(e)}


async def sonos_pause(
    db: Session,
    speaker_ip: str,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """Pause Sonos speaker."""
    governance_check = await _check_media_governance(db, agent_id, "sonos_pause", "system")
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        sonos_service = SonosService()
        result = await sonos_service.pause(speaker_ip)
        logger.info(f"Paused Sonos speaker {speaker_ip}")
        return result
    except Exception as e:
        logger.error(f"Failed to pause Sonos speaker {speaker_ip}: {e}")
        return {"success": False, "error": str(e)}


async def sonos_volume(
    db: Session,
    speaker_ip: str,
    volume: int,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """Set Sonos speaker volume."""
    governance_check = await _check_media_governance(db, agent_id, "sonos_volume", "system")
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        sonos_service = SonosService()
        result = await sonos_service.set_volume(speaker_ip, volume)
        logger.info(f"Set Sonos speaker {speaker_ip} volume to {volume}")
        return result
    except Exception as e:
        logger.error(f"Failed to set volume for Sonos speaker {speaker_ip}: {e}")
        return {"success": False, "error": str(e)}


async def sonos_groups(
    db: Session,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """Get Sonos speaker groups."""
    governance_check = await _check_media_governance(db, agent_id, "sonos_groups", "system")
    if not governance_check["allowed"]:
        return {"success": False, "error": governance_check["reason"], "governance_blocked": True}

    try:
        sonos_service = SonosService()
        groups = await sonos_service.get_groups()
        logger.info(f"Retrieved {len(groups)} Sonos groups")
        return {"success": True, "groups": groups, "count": len(groups)}
    except Exception as e:
        logger.error(f"Failed to get Sonos groups: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# Tool Registration
# ============================================================================

# Auto-register all media control functions with tool registry
# This happens on module import

def register_media_tools():
    """Register all media control tools with the tool registry."""
    from tools.registry import tool_registry

    # Spotify tools
    tool_registry.register(
        name="spotify_current",
        function=spotify_current,
        version="1.0.0",
        description="Get currently playing track from Spotify",
        category="media",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["music", "audio", "spotify", "streaming"]
    )

    tool_registry.register(
        name="spotify_play",
        function=spotify_play,
        version="1.0.0",
        description="Play track or resume playback on Spotify",
        category="media",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["music", "audio", "spotify", "streaming"]
    )

    tool_registry.register(
        name="spotify_pause",
        function=spotify_pause,
        version="1.0.0",
        description="Pause Spotify playback",
        category="media",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["music", "audio", "spotify", "streaming"]
    )

    tool_registry.register(
        name="spotify_next",
        function=spotify_next,
        version="1.0.0",
        description="Skip to next track on Spotify",
        category="media",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["music", "audio", "spotify", "streaming"]
    )

    tool_registry.register(
        name="spotify_previous",
        function=spotify_previous,
        version="1.0.0",
        description="Skip to previous track on Spotify",
        category="media",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["music", "audio", "spotify", "streaming"]
    )

    tool_registry.register(
        name="spotify_volume",
        function=spotify_volume,
        version="1.0.0",
        description="Set Spotify volume (0-100)",
        category="media",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["music", "audio", "spotify", "streaming"]
    )

    tool_registry.register(
        name="spotify_devices",
        function=spotify_devices,
        version="1.0.0",
        description="Get available Spotify devices",
        category="media",
        complexity=1,
        maturity_required="INTERN",  # Read-only
        tags=["music", "audio", "spotify", "streaming"]
    )

    # Sonos tools
    tool_registry.register(
        name="sonos_discover",
        function=sonos_discover,
        version="1.0.0",
        description="Discover Sonos speakers on local network",
        category="media",
        complexity=1,
        maturity_required="INTERN",  # Read-only
        tags=["music", "audio", "sonos", "speakers"]
    )

    tool_registry.register(
        name="sonos_play",
        function=sonos_play,
        version="1.0.0",
        description="Play audio or resume playback on Sonos speaker",
        category="media",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["music", "audio", "sonos", "speakers"]
    )

    tool_registry.register(
        name="sonos_pause",
        function=sonos_pause,
        version="1.0.0",
        description="Pause Sonos speaker",
        category="media",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["music", "audio", "sonos", "speakers"]
    )

    tool_registry.register(
        name="sonos_volume",
        function=sonos_volume,
        version="1.0.0",
        description="Set Sonos speaker volume (0-100)",
        category="media",
        complexity=2,
        maturity_required="SUPERVISED",
        tags=["music", "audio", "sonos", "speakers"]
    )

    tool_registry.register(
        name="sonos_groups",
        function=sonos_groups,
        version="1.0.0",
        description="Get Sonos speaker groups",
        category="media",
        complexity=1,
        maturity_required="INTERN",  # Read-only
        tags=["music", "audio", "sonos", "speakers"]
    )

    logger.info("Media control tools registered with tool registry")


# Auto-register on import
try:
    register_media_tools()
except Exception as e:
    logger.warning(f"Failed to register media tools: {e}")
