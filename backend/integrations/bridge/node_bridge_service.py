import logging
import httpx
import os
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class NodeBridgeService:
    def __init__(self):
        self.node_url = os.getenv("NODE_ENGINE_URL", "http://localhost:3003")
        self.client = httpx.AsyncClient(base_url=self.node_url, timeout=30.0)
        
        # Simple in-memory cache
        self._catalog_cache: List[Dict[str, Any]] = []
        self._catalog_last_updated: datetime = datetime.min
        self._cache_ttl = timedelta(minutes=5)

    async def get_health(self) -> bool:
        try:
            resp = await self.client.get("/health")
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Node engine health check failed: {e}")
            return False

    async def get_catalog(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetches pieces from Node engine."""
        if not force_refresh and self._catalog_cache and (datetime.now(timezone.utc) - self._catalog_last_updated < self._cache_ttl):
            return self._catalog_cache

        try:
            resp = await self.client.get("/pieces")
            resp.raise_for_status()
            pieces = resp.json()

            self._catalog_cache = pieces
            self._catalog_last_updated = datetime.now(timezone.utc)
            return pieces
        except Exception as e:
            logger.error(f"Failed to fetch catalog from Node engine: {e}")
            return []

    async def get_piece_details(self, piece_name: str) -> Optional[Dict[str, Any]]:
        """Get piece details."""
        try:
            resp = await self.client.get(f"/pieces/{piece_name}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Failed to get piece details for {piece_name}: {e}")
            return None
        except Exception as e:
            return None

    async def execute_action(self,
                             piece_name: str,
                             action_name: str,
                             props: Dict[str, Any],
                             auth: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes a piece action."""
        payload = {
            "pieceName": piece_name,
            "actionName": action_name,
            "props": props,
            "auth": auth
        }

        try:
            resp = await self.client.post("/execute/action", json=payload)
            resp.raise_for_status()
            result = resp.json()

            if not result.get("success", False):
                raise Exception(f"Execution failed: {result.get('error', 'Unknown error')}")

            return result.get("output", {})
        except Exception as e:
            logger.error(f"Execution error for {piece_name}.{action_name}: {e}")
            raise

    async def close(self):
        await self.client.aclose()

# Singleton instance
node_bridge = NodeBridgeService()
