
import logging
from typing import Dict, Any, List, Optional
from core.database import SessionLocal
from integrations.salesforce_service import SalesforceService
from integrations.hubspot_service import get_hubspot_service

logger = logging.getLogger(__name__)

class UniversalIntegrationService:
    """
    Unified interface for accessing third-party integrations (Salesforce, HubSpot, etc.)
    Provides consistent CRUD and Search capabilities for Agents.
    """
    
    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        # In a real app, we'd load configs for the workspace
        
    async def execute(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute an action against a specific integration service.
        
        Args:
            service: "salesforce", "hubspot", "slack", etc.
            action: "create", "read", "update", "list", "custom"
            params: Action-specific parameters (e.g., {"entity": "contact", "data": {...}})
            context: Execution context (user_id, etc.)
        """
        context = context or {}
        user_id = context.get("user_id")
        
        try:
            if service == "salesforce":
                return await self._execute_salesforce(action, params, user_id)
            elif service == "hubspot":
                return await self._execute_hubspot(action, params)
            else:
                raise ValueError(f"Service '{service}' not supported.")
                
        except Exception as e:
            logger.error(f"Universal Integration Execution Failed ({service}.{action}): {e}")
            return {"status": "error", "error": str(e)}

    async def search(self, service: str, query: str, entity_type: str = None, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search for entities within an integration.
        """
        context = context or {}
        user_id = context.get("user_id")
        
        try:
            if service == "salesforce":
                return await self._search_salesforce(query, entity_type, user_id)
            elif service == "hubspot":
                return await self._search_hubspot(query, entity_type)
            else:
                raise ValueError(f"Service '{service}' not supported for search.")
        except Exception as e:
            logger.error(f"Universal Search Failed ({service}): {e}")
            return []

    # --- Salesforce Implementation ---
    async def _execute_salesforce(self, action: str, params: Dict[str, Any], user_id: str) -> Any:
        sf_service = SalesforceService()
        # We need a DB pool/session to get the client tokens
        # For simplicity in this async method, we assume we might lack a global pool variable if not passed
        # But `SalesforceService.get_client` takes `db_conn_pool`.
        # We will try to get a one-off session or pool proxy. 
        # CAUTION: This depends on how `get_user_salesforce_tokens` works.
        # Assuming we can Mock/Patch or use a unified session helper if real DB needed.
        # For this implementation, we'll try to get the client.
        
        # NOTE: If user_id is missing (e.g. system agent), we might fail or use a system account.
        if not user_id:
            # Fallback to system user or raise error
            user_id = "system" # In a real app, this would be a specific UUID

        # Try to get client via service
        # If get_client is broken (missing db_oauth_salesforce), we catch it or use a fallback
        try:
             client = await sf_service.get_client(user_id, None) # We'll see if it works with None or fails
        except ImportError:
             logger.warning("Salesforce Service is missing db_oauth_salesforce. Falling back to Mock/Manual token if available.")
             # For now, let's just raise a clear error if we can't get it
             raise ValueError("Salesforce integration is currently incomplete (missing dependency: db_oauth_salesforce)")

        if not client:
             return {"status": "error", "message": "Could not authenticate with Salesforce"}

        entity = params.get("entity") # contact, account, opportunity
        
        if action == "list":
            if entity == "contact":
                return await sf_service.list_contacts(client)
            elif entity == "opportunity":
                return await sf_service.list_opportunities(client)
            elif entity == "account":
                return await sf_service.list_accounts(client)
            else:
                raise ValueError(f"Entity '{entity}' not supported for list action.")
                
        elif action == "create":
            data = params.get("data", {})
            if entity == "contact":
                return await sf_service.create_contact(client, **data)
            elif entity == "opportunity":
                # Ensure date string is passed
                return await sf_service.create_opportunity(client, **data)
            elif entity == "account":
                return await sf_service.create_account(client, **data)
                
        elif action == "read":
             # Generic read if ID provided
             obj_id = params.get("id")
             if entity == "opportunity":
                 return await sf_service.get_opportunity(client, obj_id)
        
        elif action == "query":
            soql = params.get("query")
            return await sf_service.execute_query(client, soql)

        return {"status": "error", "message": f"Action {action} not supported for {entity}"}

    async def _search_salesforce(self, query: str, entity_type: str, user_id: str) -> List[Dict]:
        # Use SOQL/SOSL
        sf_service = SalesforceService()
        if not user_id: return []
        
        try:
            client = await sf_service.get_client(user_id, None)
            if not client: return []
        except ImportError:
            return [{"message": "Salesforce search unavailable"}]
        
        # Simple SOSL or SOQL match
        # Using execute_query (SOQL)
        if entity_type == "contact":
            soql = f"SELECT Id, Name, Email FROM Contact WHERE Name LIKE '%{query}%'"
        elif entity_type == "account":
            soql = f"SELECT Id, Name FROM Account WHERE Name LIKE '%{query}%'"
        else:
            # SOSL for global search
            return [{"message": "Only specific entity search implemented via SOQL"}]
            
        res = await sf_service.execute_query(client, soql)
        return res.get("records", [])

    # --- HubSpot Implementation ---
    async def _execute_hubspot(self, action: str, params: Dict[str, Any]) -> Any:
        hs_service = get_hubspot_service()
        
        entity = params.get("entity")
        
        if action == "list":
            if entity == "contact":
                return await hs_service.get_contacts()
            elif entity == "deal":
                return await hs_service.get_deals()
            elif entity == "company":
                return await hs_service.get_companies()
                
        elif action == "create":
            data = params.get("data", {})
            if entity == "contact":
                return await hs_service.create_contact(**data)
            elif entity == "deal":
                return await hs_service.create_deal(**data)
            elif entity == "company":
                return await hs_service.create_company(**data)
        
        return {"status": "error", "message": f"Action {action} not implemented for HubSpot {entity}"}

    async def _search_hubspot(self, query: str, entity_type: str) -> List[Dict]:
        hs_service = get_hubspot_service()
        res = await hs_service.search_content(query, object_type=entity_type or "contact")
        return res.get("results", [])
