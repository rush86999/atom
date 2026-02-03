import logging
import asyncio
from typing import Dict, Any, List, Optional
from core.knowledge_extractor import KnowledgeExtractor
from core.automation_settings import get_automation_settings
from core.database import get_db_session
from core.models import User
from ecommerce.models import EcommerceCustomer
from sales.models import Deal, Lead
from core.negotiation_engine import NegotiationStateMachine
from core.business_intelligence import BusinessEventIntelligence
from core.business_intelligence import BusinessEventIntelligence
from core.lifecycle_comm_generator import LifecycleCommGenerator
import json

logger = logging.getLogger(__name__)

class CommunicationIntelligenceService:
    def __init__(self, ai_service: Any = None, db_session: Any = None):
        self.extractor = KnowledgeExtractor(ai_service)
        self.settings = get_automation_settings()
        self.ai_service = ai_service
        self.db_session = db_session
        self.negotiation_engine = NegotiationStateMachine(db_session)
        self.business_intel = BusinessEventIntelligence(db_session)
        self.lifecycle_comm = LifecycleCommGenerator(ai_service)

    async def analyze_and_route(self, comm_data: Dict[str, Any], user_id: str):
        """
        Orchestrates knowledge extraction and automated responses.
        """
        content = comm_data.get("content", "")
        metadata = comm_data.get("metadata", {})
        
        # 1. Extract Knowledge (Intent, Entities, Rels)
        knowledge = await self.extractor.extract_knowledge(content, source="communication")
        signals = [rel.get("to") for rel in knowledge.get("relationships", []) if rel.get("type") == "INTENT"]
        
        # 2. Update Negotiation State if a deal is found
        deal_id = metadata.get("deal_id")
        strategy_prompt = ""
        if deal_id:
            self.negotiation_engine.update_deal_state(deal_id, signals)
            strategy_prompt = self.negotiation_engine.get_strategy_prompt(deal_id)

        # 3. Process Business Lifecycle Events (POs, Shipping, etc.)
        workspace_id = metadata.get("workspace_id")
        if workspace_id:
            await self.business_intel.process_extracted_events(knowledge, workspace_id)

        # 4. Cross-System Enrichment (Simulated)
        enriched_context = self._get_cross_system_context(knowledge, user_id)
        
        # 4. Determine Response Mode
        mode = self.settings.get_settings().get("response_control_mode", "suggest")
        
        # 5. Generate & Execute Response
        if mode in ["suggest", "draft", "auto_send"]:
            # Check for specialized lifecycle intents
            lifecycle_intents = {"request_quote", "offer_quote", "confirm_shipping", "po_confirmation"}
            detected_lifecycle = list(set(signals) & lifecycle_intents)
            
            if detected_lifecycle:
                # Use specialized generator
                intent = detected_lifecycle[0]
                # Gather context from knowledge
                context = enriched_context.copy()
                context.update({
                    "entities": knowledge.get("entities", []),
                    "original_content": content
                })
                # Flatten some entities for easier prompt usage
                for e in knowledge.get("entities", []):
                    if e["type"] in ["Quote", "Shipment", "PurchaseOrder"]:
                        context.update(e["properties"])
                
                suggestion = await self.lifecycle_comm.generate_draft(intent, context)
            else:
                # Use default fallback generator
                suggestion = await self._generate_response_suggestion(content, enriched_context, user_id, strategy_prompt)
            
            await self._execute_response_mode(user_id, suggestion, mode, comm_data)

        return {
            "knowledge": knowledge,
            "response_mode": mode,
            "enriched_context": enriched_context,
            "suggestion": suggestion if mode in ["suggest", "draft", "auto_send"] else None
        }

    def _get_cross_system_context(self, knowledge: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Pulls data from other systems (CRM, eCommerce) based on extracted entities.
        """
        db = self.db_session or get_db_session()
        context = {}
        try:
            for entity in knowledge.get("entities", []):
                e_type = entity.get("type")
                props = entity.get("properties", {})
                
                if e_type == "Deal" and props.get("external_id"):
                    deal = db.query(Deal).filter(Deal.external_id == props["external_id"]).first()
                    if deal:
                        context[f"deal_{deal.id}"] = {"name": deal.name, "value": deal.value, "stage": deal.stage}
                
                if e_type == "Person" and props.get("email"):
                    cust = db.query(EcommerceCustomer).filter(EcommerceCustomer.email == props["email"]).first()
                    if cust:
                        context[f"customer_{cust.id}"] = {"risk_score": cust.risk_score, "mrr": getattr(cust, 'mrr', 0)}
        finally:
            if not self.db_session:
                db.close()
            
        return context

    async def _generate_response_suggestion(self, original_content: str, context: Dict[str, Any], user_id: str, strategy_prompt: str = "") -> str:
        """
        Uses AI to generate a context-aware response draft.
        """
        prompt = f"""
        Draft a response to the following communication:
        "{original_content}"
        
        Strategic Goal:
        {strategy_prompt}
        
        Cross-System Context:
        {json.dumps(context)}
        
        Instructions: 
        - Be professional.
        - Mention relevant system data (Deals, Risk, etc.) if it helps the business outcome.
        - If an invoice is mentioned in the context as overdue, bring it up politely.
        """
        if self.ai_service and hasattr(self.ai_service, 'analyze_text'):
            res = await self.ai_service.analyze_text(prompt)
            return res.get("response", "I'll look into this for you.")
        return "Thank you for your message. We are processing your request."

    async def _execute_response_mode(self, user_id: str, suggestion: str, mode: str, comm_data: Dict[str, Any]):
        """
        Handles the actual suggest/draft/send execution logic.
        """
        if mode == "suggest":
            logger.info(f"Response Suggestion for User {user_id}: {suggestion}")
            # In a real app, this would send a Slack/Team notification
            pass
        elif mode == "draft":
            logger.info(f"Creating Draft for User {user_id} in {comm_data.get('app_type')}")
            # Logic to create draft via integration API
            pass
        elif mode == "auto_send":
            logger.warning(f"AUTO-SENDING response for User {user_id}: {suggestion}")
            # Logic to send via integration API
            pass
