"""
Local-Only Mode Guard for Privacy-Focused Operation

This module implements local-only mode enforcement for Personal Edition.
When enabled, blocks all external API calls to cloud services while allowing
local network services (Sonos, Hue, Home Assistant, FFmpeg) to function.

Features:
- Singleton pattern for global state management
- Environment-based configuration (ATOM_LOCAL_ONLY)
- Decorator for function-level enforcement
- Clear error messages with suggestions
- Audit logging for blocked requests

Blocked Services (cloud-based):
- Spotify, Notion, OpenAI, Anthropic, DeepSeek
- Tavily, Brave Search, Slack, Gmail
- Any OAuth-based external service

Allowed Services (local):
- Sonos (local network)
- Philips Hue (local network)
- Home Assistant (local network)
- FFmpeg (local processing)
- mDNS/local network discovery

Usage:
    from core.security import require_local_allowed

    @require_local_allowed("spotify")
    async def get_current_track(user_id: str):
        # Raises LocalOnlyModeError if local-only mode enabled
        pass
"""

import functools
import logging
import os
from typing import Callable, List, Optional, Set
from fastapi import HTTPException, status

from core.structured_logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Exception Classes
# ============================================================================

class LocalOnlyModeError(HTTPException):
    """
    Raised when external service is blocked in local-only mode.

    Provides clear error message with suggestion to disable local-only mode
    or use alternative local services.
    """

    def __init__(
        self,
        service: str,
        reason: Optional[str] = None,
        suggested_alternatives: Optional[List[str]] = None
    ):
        """
        Initialize local-only mode error.

        Args:
            service: Name of blocked service (e.g., "spotify", "notion")
            reason: Optional reason for blocking (e.g., "OAuth requires cloud")
            suggested_alternatives: Optional list of local alternatives
        """
        self.service = service
        self.reason = reason
        self.suggested_alternatives = suggested_alternatives or []

        message = f"Service '{service}' is blocked in local-only mode"
        if reason:
            message += f": {reason}"

        if suggested_alternatives:
            message += f"\n\nLocal alternatives: {', '.join(suggested_alternatives)}"

        message += ".\n\nDisable local-only mode (set ATOM_LOCAL_ONLY=false) or use local services only."

        # Call parent with HTTP 403 Forbidden
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=message
        )


# ============================================================================
# Local-Only Guard Service
# ============================================================================

class LocalOnlyGuard:
    """
    Singleton service for enforcing local-only mode.

    Checks environment variable ATOM_LOCAL_ONLY and caches the value
    to avoid repeated environment lookups. Provides methods to check
    if external requests are allowed and blocks them if not.

    Thread-safe: Uses module-level singleton instance
    """

    _instance: Optional['LocalOnlyGuard'] = None
    _enabled: Optional[bool] = None

    # Cloud-based services blocked in local-only mode
    BLOCKED_SERVICES: Set[str] = {
        # Music/Media (cloud)
        "spotify",
        "apple_music",
        "youtube_music",

        # Productivity (cloud)
        "notion",
        "trello",
        "asana",
        "slack",
        "gmail",
        "google_calendar",

        # AI Providers (cloud)
        "openai",
        "anthropic",
        "deepseek",
        "cohere",
        "gemini",

        # Search (cloud)
        "tavily",
        "brave_search",
        "google_search",

        # Social (cloud)
        "twitter",
        "facebook",
        "linkedin",

        # Generic cloud APIs
        "oauth",
        "rest_api",
        "graphql",
    }

    # Local network services allowed in local-only mode
    LOCAL_ALLOWED_SERVICES: Set[str] = {
        # Media (local network)
        "sonos",           # Sonos speakers on local network
        "chromecast",      # Google Cast on local network
        "airplay",         # Apple AirPlay on local network

        # Smart Home (local network)
        "hue",             # Philips Hue Bridge
        "home_assistant",  # Home Assistant instance
        "homekit",         # Apple HomeKit
        "zigbee",          # Zigbee2MQTT
        "zwave",           # Z-Wave JS

        # File Processing (local)
        "ffmpeg",          # FFmpeg media processing
        "image_magick",    # ImageMagick processing
        "pandoc",          # Document conversion

        # Discovery (local network)
        "mdns",            # mDNS/Bonjour discovery
        "upnp",            # UPnP discovery
        "ssdp",            # Simple Service Discovery

        # Generic local
        "localhost",
        "127.0.0.1",
        "local_network",
        "lan",
    }

    def __new__(cls) -> 'LocalOnlyGuard':
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize guard (only runs once due to singleton)."""
        if self._enabled is None:
            # Read from environment on first access
            self._enabled = os.getenv("ATOM_LOCAL_ONLY", "false").lower() == "true"

            logger.info(
                "LocalOnlyGuard initialized",
                extra={
                    "local_only_enabled": self._enabled,
                    "blocked_services": len(self.BLOCKED_SERVICES),
                    "local_allowed_services": len(self.LOCAL_ALLOWED_SERVICES)
                }
            )

    @classmethod
    def reset_cache(cls):
        """
        Reset cached configuration (mainly for testing).

        Forces re-read of environment variable on next access.
        """
        cls._enabled = None
        logger.debug("LocalOnlyGuard cache reset")

    def is_local_only_enabled(self) -> bool:
        """
        Check if local-only mode is currently enabled.

        Returns:
            True if local-only mode is active, False otherwise
        """
        return self._enabled

    def allow_external_request(
        self,
        service: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Check if external service request is allowed.

        Returns True if local-only mode is disabled.
        Returns False (raises LocalOnlyModeError) if local-only mode is enabled.

        Args:
            service: Name of service being accessed (e.g., "spotify")
            reason: Optional reason for access (for error message)

        Returns:
            True if request is allowed

        Raises:
            LocalOnlyModeError: If service is blocked in local-only mode
        """
        # If local-only mode is disabled, allow everything
        if not self._enabled:
            return True

        # Check if service is explicitly blocked
        service_lower = service.lower()
        if service_lower in self.BLOCKED_SERVICES:
            # Log blocked request for audit
            logger.warning(
                "Local-only mode: blocked external service request",
                extra={
                    "service": service,
                    "reason": reason,
                    "local_only_enabled": True
                }
            )

            # Suggest local alternatives if available
            alternatives = self._get_local_alternatives(service_lower)
            raise LocalOnlyModeError(
                service=service,
                reason=reason,
                suggested_alternatives=alternatives
            )

        # Service is either local-allowed or unknown
        # Unknown services are allowed by default (fail-open for local services)
        return True

    def get_blocked_services(self) -> List[str]:
        """
        Get list of services blocked in local-only mode.

        Returns:
            Sorted list of blocked service names
        """
        return sorted(self.BLOCKED_SERVICES)

    def get_local_allowed_services(self) -> List[str]:
        """
        Get list of services that work locally (no external API).

        Returns:
            Sorted list of local-allowed service names
        """
        return sorted(self.LOCAL_ALLOWED_SERVICES)

    def is_service_blocked(self, service: str) -> bool:
        """
        Check if a specific service is blocked in local-only mode.

        Args:
            service: Service name to check

        Returns:
            True if service would be blocked, False otherwise
        """
        service_lower = service.lower()
        return service_lower in self.BLOCKED_SERVICES

    def is_service_local_allowed(self, service: str) -> bool:
        """
        Check if a service is explicitly allowed in local-only mode.

        Args:
            service: Service name to check

        Returns:
            True if service is explicitly local-allowed, False otherwise
        """
        service_lower = service.lower()
        return service_lower in self.LOCAL_ALLOWED_SERVICES

    def _get_local_alternatives(self, blocked_service: str) -> List[str]:
        """
        Get local alternatives for blocked cloud service.

        Args:
            blocked_service: Name of blocked service

        Returns:
            List of local alternative service names
        """
        alternatives_map = {
            "spotify": ["sonos", "airplay"],
            "apple_music": ["sonos", "airplay"],
            "youtube_music": ["sonos"],
            "notion": ["local markdown files"],
            "trello": ["local kanban boards"],
            "asana": ["local task management"],
            "slack": ["local messaging"],
            "gmail": ["local email client"],
            "google_calendar": ["local calendar"],
            "openai": ["local LLM (Ollama)"],
            "anthropic": ["local LLM (Ollama)"],
            "deepseek": ["local LLM (Ollama)"],
            "tavily": ["local search"],
            "brave_search": ["local search"],
        }

        return alternatives_map.get(blocked_service.lower(), [])


# ============================================================================
# Decorator for Function-Level Enforcement
# ============================================================================

def require_local_allowed(service_name: str):
    """
    Decorator to enforce local-only mode at function level.

    Raises LocalOnlyModeError before function execution if local-only mode
    is enabled and the service is blocked.

    Args:
        service_name: Name of service being accessed (e.g., "spotify")

    Usage:
        @require_local_allowed("spotify")
        async def get_current_track(user_id: str):
            # This will raise LocalOnlyModeError if local-only is enabled
            pass

    Returns:
        Decorated function that checks local-only mode before execution
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            guard = LocalOnlyGuard()
            guard.allow_external_request(
                service=service_name,
                reason=f"Function '{func.__name__}' requires {service_name} access"
            )
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            guard = LocalOnlyGuard()
            guard.allow_external_request(
                service=service_name,
                reason=f"Function '{func.__name__}' requires {service_name} access"
            )
            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Import asyncio for coroutine function detection
import asyncio


# ============================================================================
# Module-Level Singleton Instance
# ============================================================================

# Global instance for convenient access
_local_only_guard_instance: Optional[LocalOnlyGuard] = None


def get_local_only_guard() -> LocalOnlyGuard:
    """
    Get singleton LocalOnlyGuard instance.

    Returns:
        LocalOnlyGuard singleton instance
    """
    global _local_only_guard_instance
    if _local_only_guard_instance is None:
        _local_only_guard_instance = LocalOnlyGuard()
    return _local_only_guard_instance
