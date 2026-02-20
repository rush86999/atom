# -*- coding: utf-8 -*-
"""
Home Assistant Service

**✅ REAL IMPLEMENTATION**

This module provides Home Assistant integration using REST API.
- Local network communication (no cloud relay)
- Long-lived access token authentication (no OAuth flow)
- Entity state retrieval
- Service calling (light, switch, automation, etc.)
- Automation triggers

Architecture:
- Backend (HomeAssistantService) <--REST API--> Home Assistant (Local Network)
- No cloud relay - all communication stays on local network
- Long-lived access tokens for authentication (Hass UI: Settings -> Profile)

Privacy:
- Local-only execution (no cloud dependencies)
- Encrypted credential storage
- Audit trail for all device control actions

Governance:
- SUPERVISED+ maturity level required
- Full audit trail via HomeAssistantConnection model
- Device identification for accountability
"""

import asyncio
from typing import Any, Dict, List, Optional
import httpx

from core.structured_logger import get_logger
from core.feature_flags import FeatureFlags

logger = get_logger(__name__)

# Default timeout for API calls (10 seconds)
DEFAULT_TIMEOUT = 10.0


# ============================================================================
# Home Assistant Service
# ============================================================================

class HomeAssistantService:
    """
    Home Assistant integration service using REST API.

    Features:
    - State retrieval (all entities or single entity)
    - Service calling (light.turn_on, switch.turn_off, etc.)
    - Automation triggers
    - Entity filtering by domain (light, switch, sensor, etc.)

    Authentication:
    - Long-lived access tokens (not OAuth)
    - Generate in Home Assistant: Settings -> Profile -> Long-Lived Access Tokens
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = DEFAULT_TIMEOUT
    ):
        """
        Initialize Home Assistant service.

        Args:
            base_url: Home Assistant URL (e.g., http://localhost:8123)
            token: Long-lived access token
            timeout: HTTP request timeout in seconds

        Raises:
            ValueError: If base_url or token missing
        """
        if not base_url:
            raise ValueError("Home Assistant base_url is required")
        if not token:
            raise ValueError("Home Assistant access token is required")

        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

        # Create HTTP client with authorization header
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

        logger.info("Home Assistant service initialized", base_url=base_url)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
        logger.debug("Home Assistant HTTP client closed")

    async def get_states(self) -> List[Dict[str, Any]]:
        """
        Get all entity states from Home Assistant.

        Returns:
            List of entity states with entity_id, state, attributes, last_changed

        Raises:
            ConnectionError: If Home Assistant not reachable
            PermissionError: If token invalid (401)
        """
        if not FeatureFlags.SMART_HOME_CONTROL_ENABLED:
            raise PermissionError("Smart home control is disabled")

        try:
            url = f"{self.base_url}/api/states"
            logger.debug("Fetching all states from Home Assistant", url=url)

            response = await self.client.get(url)
            response.raise_for_status()

            states = response.json()
            logger.info(f"Retrieved {len(states)} entity states from Home Assistant")

            return states

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Home Assistant authentication failed - invalid token")
                raise PermissionError("Invalid Home Assistant access token")
            elif e.response.status_code == 404:
                logger.error("Home Assistant endpoint not found - check base_url")
                raise ConnectionError(f"Home Assistant not found at {self.base_url}")
            else:
                logger.error("Failed to get states", status_code=e.response.status_code)
                raise
        except Exception as e:
            logger.error("Failed to connect to Home Assistant", error=str(e))
            raise ConnectionError(f"Home Assistant not responding: {e}")

    async def get_state(self, entity_id: str) -> Dict[str, Any]:
        """
        Get state of a single entity.

        Args:
            entity_id: Entity ID (e.g., "light.living_room", "sensor.temperature")

        Returns:
            Entity state data

        Raises:
            ValueError: If entity not found (404)
            PermissionError: If token invalid (401)
        """
        if not FeatureFlags.SMART_HOME_CONTROL_ENABLED:
            raise PermissionError("Smart home control is disabled")

        try:
            url = f"{self.base_url}/api/states/{entity_id}"
            logger.debug("Fetching entity state", entity_id=entity_id)

            response = await self.client.get(url)
            response.raise_for_status()

            state = response.json()
            logger.info("Retrieved entity state", entity_id=entity_id, state=state.get("state"))

            return state

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Home Assistant authentication failed")
                raise PermissionError("Invalid Home Assistant access token")
            elif e.response.status_code == 404:
                logger.error("Entity not found", entity_id=entity_id)
                raise ValueError(f"Entity '{entity_id}' not found")
            else:
                logger.error("Failed to get state", status_code=e.response.status_code)
                raise
        except Exception as e:
            logger.error("Failed to get entity state", entity_id=entity_id, error=str(e))
            raise

    async def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call a Home Assistant service.

        Args:
            domain: Domain (e.g., "light", "switch", "automation")
            service: Service name (e.g., "turn_on", "turn_off", "trigger")
            entity_id: Entity ID (optional, for domain-specific services)
            data: Service data (e.g., {"brightness_pct": 80, "color_name": "blue"})

        Returns:
            Service call response

        Raises:
            ValueError: If entity not found or service invalid
            PermissionError: If token invalid (401)

        Examples:
            # Turn on light
            await call_service("light", "turn_on", "light.living_room", {"brightness_pct": 80})

            # Turn off switch
            await call_service("switch", "turn_off", "switch.office")

            # Trigger automation
            await call_service("automation", "trigger", "automation.bedtime")
        """
        if not FeatureFlags.SMART_HOME_CONTROL_ENABLED:
            raise PermissionError("Smart home control is disabled")

        try:
            url = f"{self.base_url}/api/services/{domain}/{service}"
            logger.info("Calling Home Assistant service", domain=domain, service=service, entity_id=entity_id)

            # Build request body
            body = {}
            if entity_id:
                body["entity_id"] = entity_id
            if data:
                body.update(data)

            response = await self.client.post(url, json=body)
            response.raise_for_status()

            result = response.json() if response.content else {}
            logger.info("Service call successful", domain=domain, service=service, entity_id=entity_id)

            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Home Assistant authentication failed")
                raise PermissionError("Invalid Home Assistant access token")
            elif e.response.status_code == 404:
                logger.error("Service or entity not found", domain=domain, service=service, entity_id=entity_id)
                raise ValueError(f"Service '{domain}.{service}' or entity '{entity_id}' not found")
            elif e.response.status_code == 400:
                logger.error("Invalid service data", domain=domain, service=service, data=data)
                raise ValueError(f"Invalid service data for '{domain}.{service}'")
            else:
                logger.error("Service call failed", status_code=e.response.status_code)
                raise
        except Exception as e:
            logger.error("Failed to call service", domain=domain, service=service, error=str(e))
            raise

    async def trigger_automation(self, automation_id: str) -> Dict[str, Any]:
        """
        Trigger a Home Assistant automation.

        Args:
            automation_id: Automation entity ID (e.g., "automation.bedtime")

        Returns:
            Automation trigger response

        Raises:
            ValueError: If automation not found
        """
        if not FeatureFlags.SMART_HOME_CONTROL_ENABLED:
            raise PermissionError("Smart home control is disabled")

        try:
            logger.info("Triggering Home Assistant automation", automation_id=automation_id)

            return await self.call_service("automation", "trigger", automation_id)

        except Exception as e:
            logger.error("Failed to trigger automation", automation_id=automation_id, error=str(e))
            raise

    async def get_entities_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """
        Get all entities for a specific domain.

        Args:
            domain: Domain name (e.g., "light", "switch", "sensor")

        Returns:
            List of entity states filtered by domain

        Examples:
            # Get all lights
            lights = await get_entities_by_domain("light")

            # Get all switches
            switches = await get_entities_by_domain("switch")
        """
        if not FeatureFlags.SMART_HOME_CONTROL_ENABLED:
            raise PermissionError("Smart home control is disabled")

        try:
            all_states = await self.get_states()

            # Filter by domain
            filtered = [
                state for state in all_states
                if state.get("entity_id", "").startswith(f"{domain}.")
            ]

            logger.info(f"Retrieved {len(filtered)} {domain} entities", domain=domain)

            return filtered

        except Exception as e:
            logger.error("Failed to get entities by domain", domain=domain, error=str(e))
            raise

    async def get_lights(self) -> List[Dict[str, Any]]:
        """
        Get all light entities.

        Returns:
            List of light entity states

        Convenience method for get_entities_by_domain("light").
        """
        return await self.get_entities_by_domain("light")

    async def get_switches(self) -> List[Dict[str, Any]]:
        """
        Get all switch entities.

        Returns:
            List of switch entity states

        Convenience method for get_entities_by_domain("switch").
        """
        return await self.get_entities_by_domain("switch")

    async def get_groups(self) -> List[Dict[str, Any]]:
        """
        Get all groups (areas).

        Returns:
            List of group entity states

        Groups are logical collections of entities (e.g., "all_lights", "living_room").
        """
        return await self.get_entities_by_domain("group")


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_home_assistant_service(
    base_url: str,
    token: str
) -> HomeAssistantService:
    """Convenience function for creating Home Assistant service."""
    return HomeAssistantService(base_url, token)
