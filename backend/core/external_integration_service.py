
import logging
from typing import Dict, Any, List, Optional
from backend.integrations.bridge.node_bridge_service import node_bridge

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
            pieces = await node_bridge.get_catalog()
            
            # Transform to match Atom's Integration Interface if needed
            # For now, pass through the Node engine's metadata
            return pieces
        except Exception as e:
            logger.error(f"Failed to get external integrations: {e}")
            return []

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
