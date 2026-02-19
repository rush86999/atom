"""
Atom SaaS API Client - WebSocket + HTTP communication with Atom SaaS platform.

Provides centralized interface for:
- Fetching skills from Atom SaaS marketplace
- Submitting skill ratings
- Installing skills with dependency resolution
- Real-time skill updates via WebSocket
- Authentication via API tokens

Environment Variables:
- ATOM_SAAS_URL: WebSocket URL (default: ws://localhost:5058/api/ws/satellite/connect)
- ATOM_SAAS_API_URL: HTTP API URL (default: http://localhost:5058/api)
- ATOM_SAAS_API_TOKEN: Authentication token (required)

Reference: scripts/satellite/atom_satellite.py for WebSocket pattern
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AtomSaaSConfig:
    """Atom SaaS connection configuration."""
    ws_url: str
    api_url: str
    api_token: str
    timeout: int = 30
    cache_ttl_seconds: int = 300  # 5 minutes


class AtomSaaSClient:
    """Client for Atom SaaS API communication."""

    def __init__(self, config: Optional[AtomSaaSConfig] = None):
        self.config = config or self._load_config()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ws_connection = None  # websockets.WebSocketClientProtocol
        self._connected = False

    @staticmethod
    def _load_config() -> AtomSaaSConfig:
        """Load configuration from environment variables."""
        ws_url = os.getenv("ATOM_SAAS_URL", "ws://localhost:5058/api/ws/satellite/connect")
        api_url = os.getenv("ATOM_SAAS_API_URL", "http://localhost:5058/api")
        api_token = os.getenv("ATOM_SAAS_API_TOKEN", "")

        if not api_token:
            logger.warning("ATOM_SAAS_API_TOKEN not set - API calls may fail")

        return AtomSaaSConfig(
            ws_url=ws_url,
            api_url=api_url,
            api_token=api_token
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with authentication headers."""
        if not self._http_client:
            headers = {
                "Authorization": f"Bearer {self.config.api_token}",
                "Content-Type": "application/json"
            }
            self._http_client = httpx.AsyncClient(
                base_url=self.config.api_url,
                headers=headers,
                timeout=self.config.timeout
            )
        return self._http_client

    async def fetch_skills(
        self,
        query: str = "",
        category: Optional[str] = None,
        skill_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Fetch skills from Atom SaaS marketplace.

        Returns paginated results with metadata.
        """
        client = await self._get_http_client()

        params = {
            "query": query,
            "page": page,
            "page_size": page_size
        }

        if category:
            params["category"] = category
        if skill_type:
            params["skill_type"] = skill_type

        try:
            response = await client.get("/marketplace/skills", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch skills from Atom SaaS: {e}")
            return {"skills": [], "total": 0, "page": page, "page_size": page_size}

    async def get_skill_by_id(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed skill information from Atom SaaS."""
        client = await self._get_http_client()

        try:
            response = await client.get(f"/marketplace/skills/{skill_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch skill {skill_id}: {e}")
            return None

    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all skill categories from Atom SaaS."""
        client = await self._get_http_client()

        try:
            response = await client.get("/marketplace/categories")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch categories: {e}")
            return []

    async def rate_skill(
        self,
        skill_id: str,
        user_id: str,
        rating: int,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit skill rating to Atom SaaS.

        Rating must be 1-5 stars.
        """
        if not 1 <= rating <= 5:
            return {
                "success": False,
                "error": "Rating must be between 1 and 5"
            }

        client = await self._get_http_client()

        payload = {
            "skill_id": skill_id,
            "user_id": user_id,
            "rating": rating,
            "comment": comment
        }

        try:
            response = await client.post(f"/marketplace/skills/{skill_id}/rate", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to submit rating for skill {skill_id}: {e}")
            return {"success": False, "error": str(e)}

    async def install_skill(
        self,
        skill_id: str,
        agent_id: str,
        auto_install_deps: bool = True
    ) -> Dict[str, Any]:
        """
        Install skill from Atom SaaS marketplace.

        Creates skill execution record, returns skill_id.
        """
        client = await self._get_http_client()

        payload = {
            "agent_id": agent_id,
            "auto_install_deps": auto_install_deps
        }

        try:
            response = await client.post(f"/marketplace/skills/{skill_id}/install", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to install skill {skill_id}: {e}")
            return {"success": False, "error": str(e)}

    async def search_skills(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Full-text search of Atom SaaS marketplace.

        Supports filtering by category, tags, skill_type.
        """
        return await self.fetch_skills(
            query=query,
            category=filters.get("category") if filters else None,
            skill_type=filters.get("skill_type") if filters else None
        )

    async def connect_websocket(self, message_handler: callable):
        """
        Connect to Atom SaaS WebSocket for real-time updates.

        message_handler: Async callback for incoming messages

        NOTE: This is a placeholder for future Atom SaaS WebSocket integration.
        The actual WebSocket implementation will be added when Atom SaaS API is available.
        """
        # TODO: Implement WebSocket connection when Atom SaaS API is ready
        logger.warning("WebSocket connection not yet implemented - Atom SaaS API integration pending")
        raise NotImplementedError("Atom SaaS WebSocket integration pending")

    async def disconnect_websocket(self):
        """Disconnect from Atom SaaS WebSocket."""
        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None
        self._connected = False
        logger.info("Disconnected from Atom SaaS WebSocket")

    async def close(self):
        """Close all connections."""
        await self.disconnect_websocket()
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # Synchronous wrappers for non-async contexts
    def fetch_skills_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for fetch_skills."""
        return asyncio.run(self.fetch_skills(*args, **kwargs))

    def get_skill_by_id_sync(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Synchronous wrapper for get_skill_by_id."""
        return asyncio.run(self.get_skill_by_id(skill_id))

    def get_categories_sync(self) -> List[Dict[str, Any]]:
        """Synchronous wrapper for get_categories."""
        return asyncio.run(self.get_categories())

    def rate_skill_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for rate_skill."""
        return asyncio.run(self.rate_skill(*args, **kwargs))

    def install_skill_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for install_skill."""
        return asyncio.run(self.install_skill(*args, **kwargs))

    def search_skills_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for search_skills."""
        return asyncio.run(self.search_skills(*args, **kwargs))
