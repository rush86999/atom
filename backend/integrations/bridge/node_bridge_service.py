
from datetime import datetime, timedelta
from functools import lru_cache
import logging
import os
from typing import Any, Dict, List, Optional
import httpx

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
        """
        Fetches the list of available pieces from the Node.js engine.
        Returns metadata for each piece (name, actions, triggers, etc.)
        """
        if not force_refresh and self._catalog_cache and (datetime.now() - self._catalog_last_updated < self._cache_ttl):
            return self._catalog_cache

        try:
            resp = await self.client.get("/pieces")
            resp.raise_for_status()
            pieces = resp.json()
            
            # Update cache
            self._catalog_cache = pieces
            self._catalog_last_updated = datetime.now()
            
            return pieces
        except Exception as e:
            logger.error(f"Failed to fetch catalog from Node engine: {e}")
            return []

    async def get_piece_details(self, piece_name: str) -> Optional[Dict[str, Any]]:
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
            logger.error(f"Error fetching piece {piece_name}: {e}")
            return None

    async def execute_action(self, 
                             piece_name: str, 
                             action_name: str, 
                             props: Dict[str, Any], 
                             auth: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a specific action on a piece via the Node engine.
        """
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
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Execution HTTP error: {e.response.text}")
            raise Exception(f"Node Engine HTTP Error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Execution error for {piece_name}.{action_name}: {e}")
            raise

    async def get_dynamic_options(
        self,
        piece_name: str,
        property_name: str,
        action_name: Optional[str] = None,
        trigger_name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        auth: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetches dynamic options for a property from the Node engine.
        This is used to populate dropdowns with real data (e.g., Slack channels).
        """
        payload = {
            "pieceName": piece_name,
            "propertyName": property_name,
            "config": config or {},
            "auth": auth
        }

        if action_name:
            payload["actionName"] = action_name
        if trigger_name:
            payload["triggerName"] = trigger_name

        try:
            resp = await self.client.post("/dynamic-options", json=payload, timeout=30.0)
            resp.raise_for_status()
            result = resp.json()

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Dynamic options request failed: {error_msg}")
                return {"options": [], "error": error_msg}

            return result.get("data", {"options": []})

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Dynamic options endpoint not found for {piece_name}.{property_name}")
                return {"options": [], "error": "Endpoint not found"}
            logger.error(f"HTTP error fetching dynamic options: {e.response.text}")
            return {"options": [], "error": str(e)}
        except Exception as e:
            logger.error(f"Error fetching dynamic options for {piece_name}.{property_name}: {e}", exc_info=True)
            return {"options": [], "error": str(e)}

    async def close(self):
        await self.client.aclose()

# Singleton instance
node_bridge = NodeBridgeService()
