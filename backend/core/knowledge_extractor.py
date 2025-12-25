import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.byok_endpoints import get_byok_manager

logger = logging.getLogger(__name__)

class KnowledgeExtractor:
    """
    Extracts structured entities and relationships from text using LLMs.
    Targets Persons, Projects, Tasks, Files, and Decisions.
    SECURITY: Redacts secrets before processing to prevent leakage.
    """
    
    def __init__(self, ai_service: Any = None):
        self.ai_service = ai_service
        self.byok = get_byok_manager()
        # Initialize secrets redactor
        try:
            from core.secrets_redactor import get_secrets_redactor
            self.redactor = get_secrets_redactor()
        except ImportError:
            self.redactor = None
            logger.warning("Secrets redactor not available in KnowledgeExtractor")

    async def extract_knowledge(self, text: str, source: str = "unknown") -> Dict[str, Any]:
        """
        Processes text to extract a structured knowledge graph.
        """
        system_prompt = """
        You are a Knowledge Graph Extraction Agent. Your goal is to analyze the provided text and extract a structured set of Entities and Relationships.
        
        **Target Entities:**
        - Person (name, role, organization, is_stakeholder: bool)
        - Project (name, status)
        - Task (description, status, owner)
        - File (filename, type)
        - Decision (summary, context, date, impact_level)
        - Organization (name)
        - Transaction (amount, currency, merchant, date, category)
        - Invoice (invoice_number, amount, recipient, status, due_date)
        - Lead (name, company, email, score, external_id)
        - Deal (name, value, stage, health_score, external_id)
        - Quote (id, amount, items, terms, status: [requested, offered])
        - PurchaseOrder (id, items, total_amount, vendor, shipping_address)
        - SalesOrder (id, order_number, total_amount, items)
        - Shipment (tracking_number, carrier, status, estimated_delivery)
        - BusinessRule (description, type, value, applies_to)
        
        **Target Relationships & Intents:**
        - PARTICIPATED_IN (Person -> Meeting/Decision)
        - REFERENCE_TO (Text -> File/Project/ExternalLink)
        - OWNS (Person/Org -> Project/Task/File/Asset)
        - STAKEHOLDER_OF (Person -> Project/Organization)
        - INTENT (Message -> intent_type): values=[payment_commitment, churn_threat, upsell_inquiry, meeting_request, approval, request_quote, offer_quote, confirm_shipping, dispute_invoice]
        - UPDATES_STATUS (Shipment/Quote -> EcommerceOrder/Deal/Contract)
        - LINKS_TO_EXTERNAL (Entity -> external_system_id): Map to CRM/ERP IDs if mentioned.
        
        **Output Format (JSON strictly):**
        {
          "entities": [
            {"id": "unique_id", "type": "Person", "properties": {"name": "...", "role": "...", "is_stakeholder": true/false}}
          ],
          "relationships": [
            {"from": "id1", "to": "id2", "type": "OWNS", "properties": {}},
            {"from": "msg_id", "to": "intent_type", "type": "INTENT", "properties": {"confidence": 0.9}}
          ]
        }
        
        **Important:** Deduplicate entities. If "John" and "John Doe" refer to the same person, use a single ID. Correctly identify hierarchy (REPORTS_TO) and those with key roles (STAKEHOLDER_OF).
        """
        
        try:
            # SECURITY: Redact secrets before sending to LLM
            # This prevents API keys, passwords, and PII from being sent to external AI services
            safe_text = text
            if self.redactor:
                redaction_result = self.redactor.redact(text)
                if redaction_result.has_secrets:
                    logger.warning(f"Redacted {len(redaction_result.redactions)} secrets before LLM extraction")
                    safe_text = redaction_result.redacted_text
            
            # Use optimal AI provider
            provider_id = self.byok.get_optimal_provider("chat")
            
            # If our internal ai_service is a wrapper that supports multiple backends
            if self.ai_service and hasattr(self.ai_service, 'analyze_text'):
                result = await self.ai_service.analyze_text(safe_text, system_prompt=system_prompt)
            else:
                # Fallback to a direct call if we have to, but better to use the centralized service
                logger.warning("No robust AI service provided to KnowledgeExtractor, extraction may be limited.")
                return {"entities": [], "relationships": []}

            if result and result.get("success"):
                content = result.get("response", "{}")
                # Attempt to find JSON in the content if the LLM was chatty
                try:
                    # Clean up markdown code blocks if present
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                    
                    extracted_data = json.loads(content)
                    return extracted_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse extracted knowledge JSON: {content}")
                    return {"entities": [], "relationships": []}
            
            return {"entities": [], "relationships": []}
            
        except Exception as e:
            logger.error(f"Knowledge extraction failed: {e}")
            return {"entities": [], "relationships": []}

    async def process_meeting_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Specialized extractor for meeting transcripts, focusing on attendees, 
        action items, and decisions made.
        """
        system_prompt = """
        You are an expert Meeting Analyst. Extract a structured knowledge graph from this meeting transcript.
        
        **Entities to Focus On:**
        - Person (Attendees)
        - Decision (What was agreed upon?)
        - Task (Action items assigned)
        - Project (Discussed projects)
        
        **Relationships to Focus On:**
        - PARTICIPATED_IN (Person -> Meeting)
        - DECIDED_ON (Person -> Decision)
        - ASSIGNED_TO (Task -> Person)
        - PART_OF (Task -> Project)
        
        Output only JSON with "entities" and "relationships" keys.
        """
        result = await self.ai_service.analyze_text(transcript, system_prompt=system_prompt)
        if result and result.get("success"):
            return json.loads(result.get("response", "{}"))
        return {"entities": [], "relationships": []}

    def merge_knowledge(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """
        Utility to merge two knowledge fragments, handling simple deduplication by ID.
        """
        merged_entities = {e["id"]: e for e in existing.get("entities", [])}
        for e in new.get("entities", []):
            merged_entities[e["id"]] = e
            
        merged_rels = existing.get("relationships", [])
        # Simple list extension for relationships, ideally we'd deduplicate these too
        merged_rels.extend(new.get("relationships", []))
        
        return {
            "entities": list(merged_entities.values()),
            "relationships": merged_rels
        }
