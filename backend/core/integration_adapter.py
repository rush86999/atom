"""
Base Integration Adapter
Abstract interface for all integrations
"""
from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, Optional
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
