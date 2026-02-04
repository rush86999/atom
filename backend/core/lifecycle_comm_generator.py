import json
import logging
from typing import Any, Dict, List, Optional

from core.byok_endpoints import get_byok_manager
from core.database import get_db_session
from core.models import BusinessRule

logger = logging.getLogger(__name__)

class LifecycleCommGenerator:
    """
    Generates professional, context-aware business emails for external stakeholders.
    """

    def __init__(self, ai_service: Any = None):
        self.ai_service = ai_service
        self.byok = get_byok_manager()

    async def generate_draft(self, intent: str, context: Dict[str, Any], workspace_id: Optional[str] = None) -> str:
        """
        Generic entry point for generating lifecycle communications.
        """
        # Fetch relevant business rules if workspace_id is provided
        rules_context = ""
        if workspace_id:
            with get_db_session() as db:
                try:
                    rules = db.query(BusinessRule).filter(BusinessRule.workspace_id == workspace_id, BusinessRule.is_active == True).all()
                    if rules:
                        rules_context = "\nApplicable Business Rules & Calculations:\n"
                        for r in rules:
                            rules_context += f"- {r.description}: {r.formula or r.value} (Applies to: {r.applies_to or 'General'})\n"
                finally:
                    db.close()

        prompt = self._get_prompt_for_intent(intent, context)
        if rules_context:
            prompt += rules_context
        
        if self.ai_service and hasattr(self.ai_service, 'analyze_text'):
            res = await self.ai_service.analyze_text(prompt)
            return res.get("response", "I'll look into this for you.")
            
        return "Thank you for your inquiry. We are processing your request."

    def _get_prompt_for_intent(self, intent: str, context: Dict[str, Any]) -> str:
        """
        Returns specialized prompts based on business lifecycle intent.
        """
        base_instructions = "Draft a professional, concise email for a small business. Ensure a helpful and brand-aligned tone."
        
        if intent == "request_quote":
            return f"""
            {base_instructions}
            Intent: Requesting a Quote from a Vendor.
            Items: {context.get('items', 'General Services')}
            Context: {json.dumps(context)}
            Please ask for pricing, availability, and terms.
            """
        elif intent == "offer_quote":
            return f"""
            {base_instructions}
            Intent: Offering a Quote to a Customer.
            Quote Details: {context.get('quote_details')}
            Customer: {context.get('customer_name')}
            Please present the quote professionally, highlighting key benefits and terms.
            """
        elif intent == "confirm_shipping":
            return f"""
            {base_instructions}
            Intent: Shipment Confirmation.
            Tracking: {context.get('tracking_number')}
            Carrier: {context.get('carrier')}
            Est. Delivery: {context.get('est_delivery')}
            Notify the customer that their order is on the way.
            """
        elif intent == "po_confirmation":
            return f"""
            {base_instructions}
            Intent: Purchase Order Confirmation.
            PO Number: {context.get('po_id')}
            Total: {context.get('total_amount')}
            Confirm receipt of the PO and state that it is being processed.
            """
        
        return f"{base_instructions}\nContext: {json.dumps(context)}"
