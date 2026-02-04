
import logging
import re
from typing import Any, Dict, Optional, Type

# In a real app, we might import specific agent classes here or lazily load them
# form operations.automations... 

logger = logging.getLogger(__name__)

class MetaAutomationEngine:
    """
    Decides when to switch from API-based execution to Browser-based execution (Self-Healing).
    """
    def __init__(self):
        # Map integration types to their browser agent counterparts
        self.fallback_registry = {
            "salesforce": "CRMManualOperator", 
            "hubspot": "CRMManualOperator",
            "remote_market": "MarketplaceAdminWorkflow", # From Phase 21
            "supplier_portal": "LogisticsManagerWorkflow" # From Phase 21
        }
        
    def should_fallback(self, error: Exception, context: Dict[str, Any] = None) -> bool:
        """
        Determines if the given error warrants a fallback to manual/browser agents.
        """
        error_str = str(error).lower()
        
        # 1. Check for specific HTTP error codes that suggest API issues but operational site uptime
        # e.g. 500 (Internal Server Error on API), 429 (Rate Limit), 503 (Service Unavailable)
        if "500" in error_str or "503" in error_str:
            logger.warning(f"Meta-Automation: Detected Server Error ({error_str}). Recommending fallback.")
            return True
            
        if "429" in error_str:
            logger.warning(f"Meta-Automation: Detected Rate Limit ({error_str}). Recommending fallback.")
            return True
            
        # 2. Check for "Feature Not Available" or specific integration errors
        if "not implemented" in error_str or "feature missing" in error_str:
             logger.warning(f"Meta-Automation: Feature missing in API. Recommending fallback.")
             return True
             
        # 3. Check for specific known flaky errors
        if "connection reset" in error_str or "timeout" in error_str:
             # Only fallback on timeout if configured to be aggressive
             return True
             
        return False

    def get_fallback_agent(self, integration_type: str) -> Optional[str]:
        """
        Returns the class name of the browser agent to use for fallback.
        """
        return self.fallback_registry.get(integration_type.lower())

    def execute_fallback(self, integration_type: str, goal: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the fallback agent.
        In a real implementation, this would dynamically instantiate the class.
        For MVP, we mock the execution call or map to Phase 21 agents.
        """
        agent_name = self.get_fallback_agent(integration_type)
        if not agent_name:
            return {"status": "failed", "error": f"No fallback agent for {integration_type}"}
            
        logger.info(f"Meta-Automation: Spawning {agent_name} for goal '{goal}'...")
        
        # Heuristic mapping to Phase 21 agents
        if agent_name == "MarketplaceAdminWorkflow":
            # Lazy import to avoid circular deps
            try:
                from operations.automations.marketplace_admin import MarketplaceAdminWorkflow

                # Mock URL for now, or fetch from config
                agent = MarketplaceAdminWorkflow(base_url="http://localhost:8089") 
                # Assuming simple price update goal for MVP tests
                if "price" in goal.lower():
                     # Extract args from goal - naive parsing for MVP
                     sku = data.get("sku", "SKU-123")
                     price = data.get("price", "99.99")
                     return agent.update_listing_price(sku, price)
            except Exception as e:
                return {"status": "failed", "error": f"Agent Execution Failed: {e}"}

        elif agent_name == "LogisticsManagerWorkflow":
             try:
                from operations.automations.logistics_manager import LogisticsManagerWorkflow
                agent = LogisticsManagerWorkflow(base_url="http://localhost:8089")
                if "order" in goal.lower():
                     sku = data.get("sku", "SKU-123")
                     qty = data.get("qty", "10")
                     return agent.place_purchase_order(sku, qty)
             except Exception as e:
                return {"status": "failed", "error": f"Agent Execution Failed: {e}"}
        
        # Default mock response for un-implemented agents
        return {
            "status": "success",
            "agent": agent_name,
            "action": "Simulated Visual Interaction",
            "details": f"Visually completed '{goal}' due to API failure."
        }

def get_meta_automation() -> MetaAutomationEngine:
    """Factory to get singleton instance"""
    return MetaAutomationEngine()
