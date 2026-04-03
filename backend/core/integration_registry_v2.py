"""
Lightweight Registry for Upstream Integration Adapters.
Dynamically loads and instantiates integration services for node execution.
"""
import importlib
import logging
from typing import Dict, Any, Optional, Type, List

from core.integration_base import IntegrationService, OperationResult, IntegrationErrorCode
from integrations.bridge.node_bridge_service import node_bridge

logger = logging.getLogger(__name__)

# Registry maps connector_id -> module_path:class_name
UPSTREAM_SERVICE_REGISTRY = {
    "asana": "integrations.adapters.asana_adapter:AsanaAdapter",
    "notion": "integrations.adapters.notion_adapter:NotionAdapter",
    "slack": "integrations.adapters.slack_adapter:SlackAdapter",
    "hubspot": "integrations.adapters.hubspot_adapter:HubSpotAdapter",
}

class IntegrationRegistryv2:
    """
    Registry for managing integration service instances in Upstream.
    
    Features:
    - Dynamic loading of adapter classes
    - Unified execution entry point for orchestrator
    - Simplified per-workspace isolation
    """
    
    def __init__(self, workspace_id: Optional[str] = None):
        self.workspace_id = workspace_id or "default"
        self._service_cache: Dict[str, IntegrationService] = {}

    def get_service(self, connector_id: str, config: Optional[Dict[str, Any]] = None) -> Optional[IntegrationService]:
        """Get or create singleton service instance for this registry."""
        if connector_id in self._service_cache:
            return self._service_cache[connector_id]
        
        service_path = UPSTREAM_SERVICE_REGISTRY.get(connector_id)
        if not service_path:
            return None
        
        try:
            module_path, class_name = service_path.split(":")
            module = importlib.import_module(module_path)
            service_class = getattr(module, class_name)
            
            # Instantiate service
            service = service_class(workspace_id=self.workspace_id, config=config)
            self._service_cache[connector_id] = service
            
            return service
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load integration {connector_id} from {service_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading integration {connector_id}: {e}")
            return None

    def _map_to_piece_auth(self, connector_id: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Maps Atom configuration/secrets to ActivePieces piece auth structure."""
        access_token = config.get("access_token")
        api_key = config.get("api_key")
        
        if access_token:
            return {
                "type": "OAUTH2",
                "data": {
                    "access_token": access_token,
                    "refresh_token": config.get("refresh_token"),
                    "client_id": config.get("client_id"),
                    "client_secret": config.get("client_secret")
                }
            }
        elif api_key:
            return {
                "type": "SECRET_TEXT",
                "secret": api_key
            }
        
        return config if config else None

    async def execute_operation(
        self, 
        connector_id: str, 
        operation: str, 
        parameters: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> OperationResult:
        """
        Main execution entry point for the orchestrator.
        Tries native adapters first, then falls back to Pieces (ActivePieces).
        """
        # 1. Try Native Adapter
        service = self.get_service(connector_id, config=config)
        if service:
            try:
                return await service.execute_operation(operation, parameters, context)
            except Exception as e:
                logger.error(f"Native integration execution failed ({connector_id}:{operation}): {e}")
                return OperationResult(
                    success=False, 
                    error=IntegrationErrorCode.EXECUTION_EXCEPTION, 
                    message=str(e)
                )

        # 2. Fallback to Pieces (ActivePieces)
        logger.info(f"Native adapter not found for {connector_id}, falling back to Pieces engine...")
        
        try:
            piece_details = await node_bridge.get_piece_details(connector_id)
            if not piece_details:
                 return OperationResult(
                    success=False, 
                    error=IntegrationErrorCode.NOT_FOUND, 
                    message=f"Integration {connector_id} not found in native or Pieces catalog"
                )
            
            # 3. Execution via Bridge
            piece_auth = self._map_to_piece_auth(connector_id, config or {})
            
            result_data = await node_bridge.execute_action(
                piece_name=connector_id,
                action_name=operation,
                props=parameters,
                auth=piece_auth
            )
            
            return OperationResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"Pieces engine execution failed ({connector_id}:{operation}): {e}")
            return OperationResult(
                success=False, 
                error=IntegrationErrorCode.EXECUTION_EXCEPTION, 
                message=str(e)
            )

# Singleton global registry for easy access
registry = IntegrationRegistryv2()
