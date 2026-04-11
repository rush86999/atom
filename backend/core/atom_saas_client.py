"""
Atom Agent OS Marketplace API Client - HTTP communication with Atom Agent OS platform.

Provides centralized interface for:
- Fetching skills from Atom Agent OS marketplace
- Submitting skill ratings
- Installing skills with dependency resolution
- Uninstalling skills
- Authentication via API tokens

Environment Variables:
- ATOM_SAAS_URL: WebSocket URL (default: wss://atomagentos.com/api/ws/satellite/connect)
- ATOM_SAAS_API_URL: HTTP API URL (default: https://atomagentos.com/api/v1/marketplace)
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
    instance_id: Optional[str] = None
    timeout: int = 30
    cache_ttl_seconds: int = 300  # 5 minutes


class AtomAgentOSMarketplaceClient:
    """Client for Atom Agent OS Marketplace API communication."""

    def __init__(self, config: Optional[AtomSaaSConfig] = None):
        self.config = config or self._load_config()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ws_connection = None  # websockets.WebSocketClientProtocol
        self._connected = False

    @staticmethod
    def _load_config() -> AtomSaaSConfig:
        """Load configuration from environment variables."""
        # Default to Atom SaaS mothership (atomagentos.com)
        ws_url = os.getenv(
            "ATOM_SAAS_URL",
            "wss://atomagentos.com/api/ws/satellite/connect"
        )
        api_url = os.getenv(
            "ATOM_SAAS_API_URL",
            "https://atomagentos.com/api/v1/marketplace"
        )
        api_token = os.getenv("ATOM_SAAS_API_TOKEN", "")
        instance_id = os.getenv("ATOM_INSTANCE_ID")

        if not instance_id and api_token:
            # Generate a stable instance ID from the token if not provided
            import hashlib
            instance_id = hashlib.sha256(api_token.encode()).hexdigest()[:32]

        if not api_token:
            logger.warning("ATOM_SAAS_API_TOKEN not set - API calls to Atom SaaS may fail")

        return AtomSaaSConfig(
            ws_url=ws_url,
            api_url=api_url,
            api_token=api_token,
            instance_id=instance_id
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with authentication headers."""
        if not self._http_client:
            headers = {
                "X-API-Token": self.config.api_token,
                "X-Federation-Key": self.config.api_token, # Reuse token as federation key context
                "X-Instance-ID": self.config.instance_id or "",
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
            response = await client.get("/skills/marketplace/skills", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch skills from Atom SaaS: {e}")
            return {"skills": [], "total": 0, "page": page, "page_size": page_size}

    async def get_skill_by_id(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed skill information from Atom SaaS."""
        client = await self._get_http_client()

        try:
            response = await client.get(f"/skills/marketplace/skills/{skill_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch skill {skill_id}: {e}")
            return None

    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all skill categories from Atom SaaS."""
        client = await self._get_http_client()

        try:
            response = await client.get("/skills/marketplace/categories")
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
            response = await client.post(f"/skills/marketplace/skills/{skill_id}/rate", json=payload)
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
            response = await client.post(f"/skills/marketplace/skills/{skill_id}/install", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to install skill {skill_id}: {e}")
            return {"success": False, "error": str(e)}

    async def uninstall_skill(
        self,
        skill_id: str,
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Uninstall a skill from Atom SaaS marketplace.

        Removes skill execution record for the specified agent.
        """
        client = await self._get_http_client()

        params = {
            "agent_id": agent_id
        }

        try:
            response = await client.delete(f"/skills/marketplace/skills/{skill_id}/uninstall", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to uninstall skill {skill_id}: {e}")
            return {"success": False, "error": str(e)}

    async def fetch_agents(
        self,
        query: str = "",
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Fetch agents from Atom SaaS marketplace."""
        client = await self._get_http_client()

        params = {
            "query": query,
            "page": page,
            "page_size": page_size
        }

        if category:
            params["category"] = category

        try:
            response = await client.get("/agents/api/agent-marketplace/browse", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch agents: {e}")
            return {"agents": [], "total": 0, "page": page, "page_size": page_size}

    async def get_agent_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get agent template details from Atom SaaS."""
        client = await self._get_http_client()

        try:
            response = await client.get(f"/agents/api/agent-marketplace/details/{template_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch agent template {template_id}: {e}")
            return None

    async def install_agent(self, template_id: str, tenant_id: str) -> Dict[str, Any]:
        """Record agent installation with Atom SaaS."""
        client = await self._get_http_client()

        payload = {
            "tenant_id": tenant_id
        }

        try:
            response = await client.post(f"/agents/api/agent-marketplace/install/{template_id}", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to install agent {template_id}: {e}")
            return {"success": False, "error": str(e)}

    async def fetch_workflows(
        self,
        query: str = "",
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Fetch workflows from Atom SaaS marketplace."""
        client = await self._get_http_client()

        params = {
            "query": query,
            "page": page,
            "page_size": page_size
        }

        if category:
            params["category"] = category

        try:
            response = await client.get("/workflows/marketplace/workflows", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch workflows: {e}")
            return {"workflows": [], "total": 0, "page": page, "page_size": page_size}

    async def get_workflow_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow template details from Atom SaaS."""
        client = await self._get_http_client()

        try:
            response = await client.get("/workflows/marketplace/workflows/{template_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch workflow template {template_id}: {e}")
            return None

    async def fetch_domains(
        self,
        query: str = "",
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Fetch specialist domains from Atom SaaS marketplace."""
        client = await self._get_http_client()

        params = {
            "query": query,
            "page": page,
            "page_size": page_size
        }

        if category:
            params["category"] = category

        try:
            response = await client.get("/domains/api/v1/domains/marketplace/browse", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch domains: {e}")
            return {"domains": [], "total": 0, "page": page, "page_size": page_size}

    async def get_domain_template(self, domain_id: str) -> Optional[Dict[str, Any]]:
        """Get domain template details from Atom SaaS."""
        client = await self._get_http_client()

        try:
            response = await client.get(f"/domains/api/v1/domains/marketplace/details/{domain_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch domain template {domain_id}: {e}")
            return None

    async def install_domain(self, domain_id: str, tenant_id: str) -> Dict[str, Any]:
        """Record domain installation with Atom SaaS."""
        client = await self._get_http_client()

        payload = {
            "tenant_id": tenant_id
        }

        try:
            response = await client.post(f"/domains/api/v1/domains/marketplace/install", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to install domain {domain_id}: {e}")
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

    async def register_instance(
        self,
        instance_name: Optional[str] = None,
        version: str = "1.0.0",
        platform: str = "docker"
    ) -> Dict[str, Any]:
        """
        Register this self-hosted instance with the SaaS marketplace.
        Returns instance_id and analytics configuration.
        """
        client = await self._get_http_client()

        payload = {
            "instance_name": instance_name or os.getenv("INSTANCE_NAME", "unnamed-instance"),
            "version": version,
            "platform": platform
        }

        try:
            # Endpoint matches the SaaS implementation
            response = await client.post("/public/v1/marketplace/analytics/register", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to register marketplace instance: {e}")
            return {"success": False, "error": str(e)}

    async def push_analytics(self, instance_id: str, reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Push aggregated usage reports to the SaaS analytics service.
        """
        if not reports:
            return {"success": True, "count": 0}

        client = await self._get_http_client()

        payload = {
            "instance_id": instance_id,
            "reports": reports
        }

        try:
            response = await client.post("/public/v1/marketplace/analytics/usage", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to push marketplace analytics: {e}")
            return {"success": False, "error": str(e)}

    async def fetch_components(
        self,
        query: str = "",
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Fetch canvas components from Atom SaaS marketplace."""
        client = await self._get_http_client()

        params = {
            "query": query,
            "page": page,
            "limit": page_size,
            "offset": (page - 1) * page_size
        }

        if category:
            params["category"] = category

        try:
            response = await client.get("/components/components", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch components: {e}")
            return {"components": [], "total": 0, "page": page, "page_size": page_size}

    async def get_component_details(self, component_id: str) -> Optional[Dict[str, Any]]:
        """Get canvas component details from Atom SaaS."""
        client = await self._get_http_client()

        try:
            response = await client.get(f"/components/components/{component_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch component {component_id}: {e}")
            return None

    async def install_component(self, component_id: str, canvas_id: Optional[str] = None) -> Dict[str, Any]:
        """Record component installation with Atom SaaS."""
        client = await self._get_http_client()

        payload = {
            "component_id": component_id,
            "canvas_id": canvas_id
        }

        try:
            response = await client.post(f"/components/components/{component_id}/install", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to install component {component_id}: {e}")
            return {"success": False, "error": str(e)}

    async def health_check(self) -> bool:
        """Verify connection to mothership."""
        client = await self._get_http_client()

        try:
            response = await client.get("/health")
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Health check failed: {e}")
            return False

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

    def uninstall_skill_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for uninstall_skill."""
        return asyncio.run(self.uninstall_skill(*args, **kwargs))

    def search_skills_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for search_skills."""
        return asyncio.run(self.search_skills(*args, **kwargs))

    def fetch_agents_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for fetch_agents."""
        return asyncio.run(self.fetch_agents(*args, **kwargs))

    def get_agent_template_sync(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Synchronous wrapper for get_agent_template."""
        return asyncio.run(self.get_agent_template(template_id))

    def install_agent_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for install_agent."""
        return asyncio.run(self.install_agent(*args, **kwargs))

    def fetch_workflows_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for fetch_workflows."""
        return asyncio.run(self.fetch_workflows(*args, **kwargs))

    def get_workflow_template_sync(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Synchronous wrapper for get_workflow_template."""
        return asyncio.run(self.get_workflow_template(template_id))

    def fetch_domains_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for fetch_domains."""
        return asyncio.run(self.fetch_domains(*args, **kwargs))

    def get_domain_template_sync(self, domain_id: str) -> Optional[Dict[str, Any]]:
        """Synchronous wrapper for get_domain_template."""
        return asyncio.run(self.get_domain_template(domain_id))

    def install_domain_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for install_domain."""
        return asyncio.run(self.install_domain(*args, **kwargs))

    def fetch_components_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for fetch_components."""
        return asyncio.run(self.fetch_components(*args, **kwargs))

    def get_component_details_sync(self, component_id: str) -> Optional[Dict[str, Any]]:
        """Synchronous wrapper for get_component_details."""
        return asyncio.run(self.get_component_details(component_id))

    def install_component_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for install_component."""
        return asyncio.run(self.install_component(*args, **kwargs))

    def register_instance_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for register_instance."""
        return asyncio.run(self.register_instance(*args, **kwargs))

    def push_analytics_sync(self, *args, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for push_analytics."""
        return asyncio.run(self.push_analytics(*args, **kwargs))

    def health_check_sync(self) -> bool:
        """Synchronous wrapper for health_check."""
        return asyncio.run(self.health_check())


# Alias for backward compatibility
# Multiple files import AtomSaaSClient but class is named AtomAgentOSMarketplaceClient
AtomSaaSClient = AtomAgentOSMarketplaceClient

