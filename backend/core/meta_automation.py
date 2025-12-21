import logging
from typing import Dict, Any, Optional, Type
from operations.automations.crm_operator import CRMManualOperator
from finance.automations.legacy_portals import BankPortalWorkflow

logger = logging.getLogger(__name__)

class MetaAutomationEngine:
    """
    Handles 'Self-Healing' automation by falling back to UI agents 
    when API integrations fail.
    """
    
    def __init__(self):
        # Map Integration Type -> Browser Agent Class
        self.fallback_registry = {
            "SALESFORCE": CRMManualOperator,
            "HUBSPOT": CRMManualOperator, # Assuming we use same/similar for demo
            "BANKING": BankPortalWorkflow
        }

    def should_fallback(self, error: Exception) -> bool:
        """
        Determines if an error should trigger a UI fallback.
        Triggers on:
        - HTTP 500 (Server Error)
        - HTTP 429 (Rate Limit)
        - HTTP 503 (Service Unavailable)
        - Specific 'API Error' strings
        """
        err_str = str(error).lower()
        
        # Check for status codes
        if "500" in err_str or "503" in err_str or "429" in err_str:
            return True
            
        # Check for keywords
        triggers = ["internal server error", "quota exceeded", "api down", "service unavailable"]
        for trigger in triggers:
            if trigger in err_str:
                return True
                
        return False

    def get_fallback_agent(self, integration_type: str, headless: bool = True) -> Optional[Any]:
        """
        Returns an instance of the appropriate Browser Agent.
        """
        agent_cls = self.fallback_registry.get(integration_type.upper())
        if agent_cls:
            logger.info(f"Meta-Automation: Activating fallback agent {agent_cls.__name__} for {integration_type}")
            return agent_cls(headless=headless)
        
        logger.warning(f"Meta-Automation: No fallback agent found for {integration_type}")
        return None

# Global instance
meta_automation = MetaAutomationEngine()

def get_meta_automation() -> MetaAutomationEngine:
    return meta_automation
