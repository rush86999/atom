
import logging
from typing import Any, Dict, List, Optional

from integrations.bridge.node_bridge_service import node_bridge

logger = logging.getLogger(__name__)

class ExternalIntegrationService:
    """
    High-level service for managing and interacting with External (Node.js) Integrations.
    This replaces the old 'Catalog' system.
    """
    
    async def get_all_integrations(self) -> List[Dict[str, Any]]:
        """
        Returns a list of all available external integrations (pieces).
        Unifies the format for the frontend.
        """
        try:
            return await node_bridge.get_catalog()
        except Exception as e:
            logger.error(f"Failed to get external integrations: {e}")
            return []

    async def get_piece_details(self, piece_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetches detailed metadata for a specific piece.
        """
        try:
            return await node_bridge.get_piece_details(piece_name)
        except Exception as e:
            logger.error(f"Failed to get details for piece {piece_name}: {e}")
            return None

    async def execute_integration_action(self, 
                                       integration_id: str, 
                                       action_id: str, 
                                       params: Dict[str, Any], 
                                       credentials: Optional[Dict[str, Any]] = None) -> Any:
        """
        Executes an action on a remote integration.
        """
        # integration_id is typically the package name, e.g., "@activepieces/piece-slack"
        # action_id is the action key, e.g., "send_message"
        
        try:
            return await node_bridge.execute_action(
                piece_name=integration_id,
                action_name=action_id,
                props=params,
                auth=credentials
            )
        except Exception as e:
            logger.error(f"External Action Execution Failed: {e}")
            raise

# Singleton
external_integration_service = ExternalIntegrationService()
