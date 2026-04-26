"""
Base Integration Adapter
Abstract interface for all integrations
"""
from abc import ABC, abstractmethod
import ipaddress
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import httpx

logger = logging.getLogger(__name__)


class IntegrationAdapter(ABC):
    """
    Base class for all integration adapters
    Provides standardized interface and HTTP client utilities
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
    
    @abstractmethod
    async def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an integration action
        
        Args:
            action: Action to perform (e.g., "send_message", "create_task")
            payload: Action parameters
            
        Returns:
            Result dictionary
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if integration is healthy and accessible
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Default implementation - try a simple execute
            await self.execute("health", {})
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with timeout"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=True
            )
        return self._client
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class HTTPIntegrationAdapter(IntegrationAdapter):
    """
    HTTP-based integration adapter
    Preferred for most integrations - no heavy SDKs
    """

    def _validate_url(self, url: str) -> None:
        """Validate URL to prevent SSRF attacks.

        Args:
            url: URL to validate

        Raises:
            ValueError: If URL is invalid or points to internal/private address
        """
        try:
            parsed = urlparse(url)

            # Block internal hostnames
            blocked_hostnames = ['localhost', '127.0.0.1', '0.0.0.0', '::1']
            if parsed.hostname in blocked_hostnames:
                raise ValueError(f"Internal URLs not allowed: {parsed.hostname}")

            # Block private IP addresses
            if parsed.hostname:
                try:
                    ip = ipaddress.ip_address(parsed.hostname)
                    if ip.is_private:
                        raise ValueError(f"Private IP addresses not allowed: {parsed.hostname}")
                except ValueError:
                    # Not an IP address, hostname is fine
                    pass

        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.warning(f"URL validation failed for {url}: {e}")

    async def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute HTTP request to integration API

        Args:
            action: API endpoint/action
            payload: Request payload

        Returns:
            Response JSON
        """
        client = await self.get_client()

        url = f"{self.base_url}/{action}" if self.base_url else action

        # Validate URL to prevent SSRF attacks
        self._validate_url(url)

        headers = {}
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {action}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error executing {action}: {e}")
            raise
