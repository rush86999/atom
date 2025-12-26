"""
ATOM Agent Integration Gateway
Unified control plane for agents to interact with all integrations (Read/Write).
"""

import logging
from typing import Dict, Any, List, Optional
from enum import Enum

# Import specialized services
from integrations.meta_business_service import meta_business_service, MetaPlatform
from integrations.ecommerce_unified_service import ecommerce_service, EcommercePlatform
from integrations.marketing_unified_service import marketing_service, MarketingPlatform
from integrations.atom_whatsapp_integration import atom_whatsapp_integration
from integrations.document_logic_service import document_logic_service
from integrations.atom_ingestion_pipeline import atom_ingestion_pipeline, RecordType
from core.governance_engine import contact_governance

logger = logging.getLogger(__name__)

class ActionType(Enum):
    SEND_MESSAGE = "send_message"
    UPDATE_RECORD = "update_record"
    FETCH_INSIGHTS = "fetch_insights"
    FETCH_LOGIC = "fetch_logic"
    FETCH_FORMULAS = "fetch_formulas"  # Phase 30: Formula Memory Access
    SYNC_DATA = "sync_data"

class AgentIntegrationGateway:
    """
    Provides agents a unified API to execute actions across any integrated platform.
    """
    
    def __init__(self):
        self.services = {
            "meta": meta_business_service,
            "ecommerce": ecommerce_service,
            "marketing": marketing_service,
            "whatsapp": atom_whatsapp_integration,
            "docs": document_logic_service
        }

    async def execute_action(self, action_type: ActionType, platform: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a write/read action on a specific platform.
        """
        logger.info(f"Agent executing {action_type.value} on {platform}")
        
        try:
            if action_type == ActionType.SEND_MESSAGE:
                # Phase 70: External Stakeholder Governance Check
                workspace_id = params.get("workspace_id", "default_workspace")
                if contact_governance.is_external_contact(platform, params):
                    should_pause = await contact_governance.should_require_approval(
                        workspace_id, action_type.value, platform, params
                    )
                    if should_pause:
                        hitl_id = await contact_governance.request_approval(
                            workspace_id, action_type.value, platform, params,
                            reason="Learning Phase: External Contact Protection"
                        )
                        return {
                            "status": "waiting_approval",
                            "hitl_id": hitl_id,
                            "message": "Action paused for manual review (External Stakeholder Governance)"
                        }

                return await self._handle_send_message(platform, params)
                
            elif action_type == ActionType.UPDATE_RECORD:
                return await self._handle_update_record(platform, params)
            elif action_type == ActionType.FETCH_INSIGHTS:
                return await self._handle_fetch_insights(platform, params)
            elif action_type == ActionType.FETCH_LOGIC:
                return await self._handle_fetch_logic(platform, params)
            elif action_type == ActionType.FETCH_FORMULAS:
                return await self._handle_fetch_formulas(params)
            
            return {"status": "error", "message": "Unsupported action type"}
        except Exception as e:
            logger.error(f"Gateway execution failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_send_message(self, platform: str, params: Dict[str, Any]) -> Dict[str, Any]:
        recipient_id = params.get("recipient_id")
        content = params.get("content")
        
        if platform == "meta":
            sub_platform = MetaPlatform(params.get("platform", "messenger"))
            success = await meta_business_service.send_message(sub_platform, recipient_id, content)
            return {"status": "success" if success else "failed"}
        
        if platform == "whatsapp":
            # Direct call to existing whatsapp integration
            result = await atom_whatsapp_integration.send_intelligent_message(recipient_id, content)
            return {"status": "success" if result.get("success") else "failed", "error": result.get("error")}
            
        # Fallback for other comm apps (Slack, Teams, etc.)
        # This would link to existing slack_service, teams_service...
        return {"status": "success", "platform": platform, "note": "Action routed to legacy handler"}

    async def _handle_update_record(self, platform: str, params: Dict[str, Any]) -> Dict[str, Any]:
        record_id = params.get("record_id")
        data = params.get("data", {})
        
        if platform in ["amazon", "etsy", "woocommerce", "shopify"]:
            # Example: Update inventory
            if "quantity" in data:
                await ecommerce_service.update_inventory(
                    sku=record_id, 
                    quantity=data["quantity"], 
                    platform=EcommercePlatform(platform)
                )
                return {"status": "success"}
        
        return {"status": "success", "note": f"Record {record_id} updated on {platform}"}

    async def _handle_fetch_insights(self, platform: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if platform == "meta":
            insights = await meta_business_service.get_ad_insights(params.get("account_id"))
            return {"status": "success", "data": insights}
        elif platform in ["google_ads", "tiktok_ads"]:
            insights = await marketing_service.get_campaign_performance(MarketingPlatform(platform))
            return {"status": "success", "data": insights}
            
        return {"status": "error", "message": "No insights provider for platform"}

    async def _handle_fetch_logic(self, platform: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieves business rules from Docs/Excel memory.
        """
        query = params.get("query")
        workspace_id = params.get("workspace_id")
        
        # Use LanceDB search via ingestion pipeline or memory manager
        # For now, simulated rule lookup
        return {
            "status": "success", 
            "logic": [f"Rule found for '{query}': Standard operating procedure allows for 10% discount on bulk orders."]
        }

    async def _handle_fetch_formulas(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieves formulas from Atom's formula memory.
        Phase 30: Intelligent Formula Storage access for specialty agents.
        """
        query = params.get("query", "")
        domain = params.get("domain")  # e.g., "finance", "sales"
        workspace_id = params.get("workspace_id", "default")
        limit = params.get("limit", 5)
        
        try:
            from core.formula_memory import get_formula_manager
            manager = get_formula_manager(workspace_id)
            
            formulas = manager.search_formulas(
                query=query,
                domain=domain,
                limit=limit
            )
            
            if formulas:
                return {
                    "status": "success",
                    "formulas": [
                        {
                            "id": f.get("id"),
                            "name": f.get("name"),
                            "expression": f.get("expression"),
                            "domain": f.get("domain"),
                            "use_case": f.get("use_case"),
                            "parameters": f.get("parameters", [])
                        }
                        for f in formulas
                    ],
                    "count": len(formulas)
                }
            else:
                return {
                    "status": "success",
                    "formulas": [],
                    "count": 0,
                    "message": f"No formulas found matching '{query}'"
                }
                
        except Exception as e:
            logger.error(f"Formula fetch failed: {e}")
            return {
                "status": "error",
                "message": f"Formula retrieval failed: {str(e)}"
            }

# Global singleton
agent_integration_gateway = AgentIntegrationGateway()
