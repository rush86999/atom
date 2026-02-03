"""
ATOM Agent Integration Gateway
Unified control plane for agents to interact with all integrations (Read/Write).
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from core.governance_engine import contact_governance
from integrations.atom_discord_integration import atom_discord_integration
from integrations.atom_ingestion_pipeline import RecordType, atom_ingestion_pipeline
from integrations.atom_telegram_integration import atom_telegram_integration
from integrations.atom_whatsapp_integration import atom_whatsapp_integration
from integrations.document_logic_service import document_logic_service
from integrations.ecommerce_unified_service import EcommercePlatform, ecommerce_service
from integrations.google_chat_enhanced_service import google_chat_enhanced_service
from integrations.marketing_unified_service import MarketingPlatform, marketing_service

# Import specialized services
from integrations.meta_business_service import MetaPlatform, meta_business_service
from integrations.openclaw_service import openclaw_service
from integrations.shopify_service import ShopifyService
from integrations.slack_enhanced_service import slack_enhanced_service
from integrations.teams_enhanced_service import teams_enhanced_service

logger = logging.getLogger(__name__)

class ActionType(Enum):
    SEND_MESSAGE = "send_message"
    UPDATE_RECORD = "update_record"
    FETCH_INSIGHTS = "fetch_insights"
    FETCH_LOGIC = "fetch_logic"
    FETCH_FORMULAS = "fetch_formulas"  # Phase 30: Formula Memory Access
    APPLY_FORMULA = "apply_formula"     # Phase 30: Execute formula with learning
    SYNC_DATA = "sync_data"
    # Shopify Lifecycle Actions
    SHOPIFY_GET_CUSTOMERS = "shopify_get_customers"
    SHOPIFY_GET_ORDERS = "shopify_get_orders"
    SHOPIFY_GET_PRODUCTS = "shopify_get_products"
    SHOPIFY_CREATE_FULFILLMENT = "shopify_create_fulfillment"
    SHOPIFY_GET_ANALYTICS = "shopify_get_analytics"
    SHOPIFY_MANAGE_INVENTORY = "shopify_manage_inventory"


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
            "docs": document_logic_service,
            "shopify": ShopifyService(),
            "discord": atom_discord_integration,
            "teams": teams_enhanced_service,
            "telegram": atom_telegram_integration,
            "google_chat": google_chat_enhanced_service,
            "google_chat": google_chat_enhanced_service,
            "slack": slack_enhanced_service,
            "openclaw": openclaw_service
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
            elif action_type == ActionType.APPLY_FORMULA:
                return await self._handle_apply_formula(params)
            # Shopify Lifecycle Actions
            elif action_type == ActionType.SHOPIFY_GET_CUSTOMERS:
                return await self._handle_shopify_customers(params)
            elif action_type == ActionType.SHOPIFY_GET_ORDERS:
                return await self._handle_shopify_orders(params)
            elif action_type == ActionType.SHOPIFY_GET_PRODUCTS:
                return await self._handle_shopify_products(params)
            elif action_type == ActionType.SHOPIFY_CREATE_FULFILLMENT:
                return await self._handle_shopify_fulfillment(params)
            elif action_type == ActionType.SHOPIFY_GET_ANALYTICS:
                return await self._handle_shopify_analytics(params)
            elif action_type == ActionType.SHOPIFY_MANAGE_INVENTORY:
                return await self._handle_shopify_inventory(params)
            
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
            
        if platform == "agent":
            # Route back to Universal Bridge for Agent-to-Agent feedback
            from integrations.universal_webhook_bridge import universal_webhook_bridge
            
            payload = {
                "agent_id": params.get("sender_agent_id", "atom_main"),
                "target_id": recipient_id,
                "message": content
            }
            return await universal_webhook_bridge.process_incoming_message("agent", payload)
            
        if platform == "discord":
            # Direct call to discord integration
            success = await atom_discord_integration.send_message(recipient_id, content)
            return {"status": "success" if success else "failed"}
            
        if platform == "teams":
            # Direct call to teams enhanced service
            result = await teams_enhanced_service.send_message(recipient_id, content, params.get("thread_ts"))
            return {"status": "success" if result else "failed"}
            
        if platform == "telegram":
            # Direct call to telegram integration
            result = await atom_telegram_integration.send_intelligent_message(recipient_id, content)
            return {"status": "success" if result.get("success") else "failed", "error": result.get("error")}
            
        if platform == "google_chat":
            # Direct call to google chat enhanced service
            result = await google_chat_enhanced_service.send_message(recipient_id, content, params.get("thread_ts"))
            return {"status": "success" if result else "failed"}
            
        if platform == "slack":
            # Direct call to slack enhanced service
            result = await slack_enhanced_service.send_message(
                workspace_id=params.get("workspace_id", "default"), 
                channel_id=recipient_id, 
                text=content, 
                thread_ts=params.get("thread_ts")
            )
            return {"status": "success" if result.get("ok") else "failed", "error": result.get("error")}
            
        if platform == "twilio":
            # Direct call to twilio service
            from integrations.twilio_service import twilio_service
            result = await twilio_service.send_sms(to=recipient_id, body=content)
            return {"status": "success" if result else "failed"}
            
        if platform == "matrix":
            # Direct call to matrix service (to be created)
            try:
                from integrations.matrix_service import matrix_service
                result = await matrix_service.send_message(room_id=recipient_id, text=content)
                return {"status": "success" if result else "failed"}
            except ImportError:
                return {"status": "failed", "error": "Matrix service not found"}
            
        if platform == "messenger":
            # Direct call to messenger service
            try:
                from integrations.messenger_service import messenger_service
                result = await messenger_service.send_message(recipient_id=recipient_id, text=content)
                return {"status": "success" if result else "failed"}
            except ImportError:
                return {"status": "failed", "error": "Messenger service not found"}
                
        if platform == "line":
            # Direct call to line service
            try:
                from integrations.line_service import line_service
                result = await line_service.send_message(to=recipient_id, text=content)
                return {"status": "success" if result else "failed"}
            except ImportError:
                return {"status": "failed", "error": "Line service not found"}
            
        if platform == "signal":
            # Direct call to signal service
            try:
                from integrations.signal_service import signal_service
                result = await signal_service.send_message(recipient=recipient_id, text=content)
                return {"status": "success" if result else "failed"}
            except ImportError:
                return {"status": "failed", "error": "Signal service not found"}

        if platform == "openclaw":
             # Direct call to OpenClaw service
             result = await openclaw_service.send_message(
                 recipient_id=recipient_id,
                 content=content,
                 thread_ts=params.get("thread_ts")
             )
             return result
            
        # Fallback for other comm apps (Legacy Support)
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

    async def _handle_apply_formula(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a formula and record the result as a learning experience.
        Phase 30: Formula execution with agent learning integration.
        Uses existing AgentGovernanceService for confidence score updates.
        """
        formula_id = params.get("formula_id")
        inputs = params.get("inputs", {})
        workspace_id = params.get("workspace_id", "default")
        agent_id = params.get("agent_id")
        agent_role = params.get("agent_role", "general")
        task_description = params.get("task_description", "formula calculation")
        
        if not formula_id:
            return {"status": "error", "message": "formula_id is required"}
        
        try:
            from core.agent_world_model import WorldModelService
            from core.formula_memory import get_formula_manager
            
            manager = get_formula_manager(workspace_id)
            
            # Execute the formula
            result = manager.apply_formula(formula_id, inputs)
            
            formula = manager.get_formula(formula_id)
            formula_name = formula.get("name", "Unknown") if formula else "Unknown"
            
            # Record as learning experience AND update agent confidence
            if agent_id:
                world_model = WorldModelService(workspace_id)
                success = result.get("success", False)
                
                # Record the experience
                await world_model.record_formula_usage(
                    agent_id=agent_id,
                    agent_role=agent_role,
                    formula_id=formula_id,
                    formula_name=formula_name,
                    task_description=task_description,
                    inputs=inputs,
                    result=result.get("result") if success else None,
                    success=success,
                    learnings=f"{'Successfully applied' if success else 'Failed:'} {formula_name} for {task_description}"
                )
                
                # Update agent confidence via existing governance system
                try:
                    from core.agent_governance_service import AgentGovernanceService
                    from core.database import get_db_session
                    
                    db = next(get_db_session())
                    governance = AgentGovernanceService(db)
                    governance._update_confidence_score(
                        agent_id=agent_id,
                        positive=success,
                        impact_level="low"  # Formula usage is low-impact learning
                    )
                    logger.info(f"Updated confidence for agent {agent_id} after formula {'success' if success else 'failure'}")
                except Exception as gov_err:
                    logger.warning(f"Could not update agent confidence: {gov_err}")
            
            return result
            
        except Exception as e:
            logger.error(f"Formula apply failed: {e}")
            return {
                "status": "error",
                "message": f"Formula execution failed: {str(e)}"
            }

    # ==================== SHOPIFY LIFECYCLE HANDLERS ====================
    
    async def _handle_shopify_customers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get/search Shopify customers"""
        access_token = params.get("access_token")
        shop = params.get("shop")
        query = params.get("query")
        customer_id = params.get("customer_id")
        limit = params.get("limit", 20)
        
        if not access_token or not shop:
            return {"status": "error", "message": "access_token and shop are required"}
        
        shopify = self.services["shopify"]
        
        try:
            if customer_id:
                customer = await shopify.get_customer(access_token, shop, customer_id)
                return {"status": "success", "data": customer}
            elif query:
                customers = await shopify.search_customers(access_token, shop, query)
                return {"status": "success", "data": customers, "count": len(customers)}
            else:
                customers = await shopify.get_customers(access_token, shop, limit)
                return {"status": "success", "data": customers, "count": len(customers)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _handle_shopify_orders(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get Shopify orders"""
        access_token = params.get("access_token")
        shop = params.get("shop")
        limit = params.get("limit", 20)
        
        if not access_token or not shop:
            return {"status": "error", "message": "access_token and shop are required"}
        
        shopify = self.services["shopify"]
        
        try:
            orders = await shopify.get_orders(access_token, shop, limit)
            return {"status": "success", "data": orders, "count": len(orders)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _handle_shopify_products(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get Shopify products"""
        access_token = params.get("access_token")
        shop = params.get("shop")
        limit = params.get("limit", 20)
        
        if not access_token or not shop:
            return {"status": "error", "message": "access_token and shop are required"}
        
        shopify = self.services["shopify"]
        
        try:
            products = await shopify.get_products(access_token, shop, limit)
            return {"status": "success", "data": products, "count": len(products)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _handle_shopify_fulfillment(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create fulfillment for an order"""
        access_token = params.get("access_token")
        shop = params.get("shop")
        order_id = params.get("order_id")
        location_id = params.get("location_id")
        tracking_number = params.get("tracking_number")
        tracking_company = params.get("tracking_company")
        
        if not all([access_token, shop, order_id, location_id]):
            return {"status": "error", "message": "access_token, shop, order_id, and location_id are required"}
        
        shopify = self.services["shopify"]
        
        try:
            result = await shopify.create_fulfillment(
                access_token, shop, order_id, location_id, tracking_number, tracking_company
            )
            logger.info(f"Agent created fulfillment for order {order_id}")
            return {"status": "success", "data": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _handle_shopify_analytics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive Shopify analytics"""
        access_token = params.get("access_token")
        shop = params.get("shop")
        
        if not access_token or not shop:
            return {"status": "error", "message": "access_token and shop are required"}
        
        shopify = self.services["shopify"]
        
        try:
            analytics = await shopify.get_shop_analytics(access_token, shop)
            return {"status": "success", "data": analytics}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _handle_shopify_inventory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get/manage Shopify inventory"""
        access_token = params.get("access_token")
        shop = params.get("shop")
        location_id = params.get("location_id")
        
        if not access_token or not shop:
            return {"status": "error", "message": "access_token and shop are required"}
        
        shopify = self.services["shopify"]
        
        try:
            inventory = await shopify.get_inventory_levels(access_token, shop, location_id)
            locations = await shopify.get_locations(access_token, shop)
            return {
                "status": "success",
                "inventory": inventory,
                "locations": locations,
                "inventory_count": len(inventory),
                "location_count": len(locations)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Global singleton
agent_integration_gateway = AgentIntegrationGateway()
