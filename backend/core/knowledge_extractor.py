import asyncio
from datetime import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from core.database import get_db_session
from core.models import EntityTypeDefinition
from core.llm_service import LLMService

logger = logging.getLogger(__name__)

# Background extraction (communication/document ingestion) runs at machine
# volume — 800+ calls in 6h with no user in the loop (observed 2026-09-05) —
# so it pins a flash-class model instead of trusting BPC's value ranking,
# which routed bulk extraction to frontier models (qwen3-max / mimo-v2.5-pro,
# ~26-30x flash per-token pricing) for ~400-char supplier emails. Same pin +
# unpinned-retry convention as chat_tool_planner / chat_canvas_editor.
KG_EXTRACTION_MODEL = os.getenv("ATOM_KG_EXTRACTION_MODEL", "qwen/qwen3.7-flash")


class ExtractionResult(BaseModel):
    """Schema-free extraction contract: property bags stay open so the
    ontology-driven prompt (and custom entity types) flow through unchanged."""

    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)

class KnowledgeExtractor:
    """
    Extracts structured entities and relationships from text using LLMs.
    Targets canonical entities and user-defined custom entity types.
    SECURITY: Redacts secrets before processing to prevent leakage.
    """
    
    def __init__(self, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None):
        self.workspace_id = workspace_id or "default"
        self.tenant_id = tenant_id or "default"
        
        self.llm_service = LLMService(workspace_id=self.workspace_id, tenant_id=self.tenant_id)
        # Initialize secrets redactor
        try:
            from core.secrets_redactor import get_secrets_redactor
            self.redactor = get_secrets_redactor()
        except ImportError:
            self.redactor = None
            logger.warning("Secrets redactor not available in KnowledgeExtractor")

    async def _get_custom_entity_types(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch active custom entity types for the workspace."""
        wid = workspace_id or self.workspace_id
        if not wid:
            return []
            
        with get_db_session() as session:
            try:
                custom_types = session.query(EntityTypeDefinition).filter(
                    EntityTypeDefinition.tenant_id == self.tenant_id,
                    EntityTypeDefinition.is_active == True,
                    EntityTypeDefinition.is_system == False
                ).all()
                return [
                    {
                        "slug": t.slug,
                        "display_name": t.display_name,
                        "description": t.description,
                        "schema": t.json_schema
                    }
                    for t in custom_types
                ]
            except Exception as e:
                logger.error(f"Failed to fetch custom entity types: {e}")
                return []

    async def _build_extraction_prompt(self, workspace_id: Optional[str] = None) -> Optional[str]:
        """Build the schema-constrained extraction prompt from the ontology
        tables (entity types with hierarchy + allowed relation triples).

        Returns None when the ontology layer is unavailable — callers then
        fall back to the legacy hardcoded prompt so extraction never breaks.
        """
        try:
            from core.ontology import get_ontology_service
            schema = get_ontology_service(self.tenant_id).get_schema()
        except Exception as exc:
            logger.debug(f"ontology prompt generation unavailable: {exc}")
            return None

        types = [t for t in schema["entity_types"] if not t.get("abstract")]
        if not types or not schema["relations"]:
            return None

        # Include custom (non-system) types always; for system types show
        # name + parent + field hints.
        lines = []
        for t in types:
            desc = t.get("fields") or t.get("description") or ""
            parent = f" (subtype of {t['parent_type']})" if t.get("parent_type") else ""
            line = f"{t['slug']}{parent}"
            if t.get("aliases"):
                line += f" [also: {', '.join(t['aliases'][:4])}]"
            if desc:
                line += f" ({desc})"
            lines.append(line)
        # Custom types carry JSON Schema property hints.
        for t in types:
            if t.get("json_schema") and isinstance(t["json_schema"], dict) \
                    and "properties" in t["json_schema"] and not t.get("fields"):
                props = ", ".join(t["json_schema"]["properties"].keys())
                lines.append(f"{t['slug']} - Fields: [{props}]")

        rel_lines = []
        for r in schema["relations"]:
            domain = "/".join(r["domain"]) if r["domain"] != ["*"] else "Any"
            rng = "/".join(r["range"]) if r["range"] != ["*"] else "Any"
            rel_lines.append(f"- {r['name']} ({domain} -> {rng})"
                             + (f": {r['description']}" if r.get("description") else ""))

        return f"""
        You are a Knowledge Graph Extraction Agent. Your goal is to analyze the provided text and extract a structured set of Entities and Relationships.

        **Target Entities (constrained schema — use ONLY these types):**
        {chr(10).join('        - ' + l for l in lines)}

        **Target Relationships (only these source-type -> relation -> target-type triples are legal):**
        {chr(10).join('        ' + l for l in rel_lines)}

        **Output Format (JSON strictly):**
        {{
          "entities": [
            {{"id": "unique_id", "type": "Person", "properties": {{"name": "...", "role": "...", "is_stakeholder": true/false}}}}
          ],
          "relationships": [
            {{"from": "id1", "to": "id2", "type": "OWNS", "properties": {{}}}},
            {{"from": "msg_id", "to": "intent_type", "type": "INTENT", "properties": {{"confidence": 0.9}}}}
          ]
        }}

        **Important:** Deduplicate entities. If "John" and "John Doe" refer to the same person, use a single ID. Prefer the most specific entity type from the schema (e.g. Invoice over Transaction). Do NOT invent relationship types outside the list above.
        """

    def _extraction_llm_kwargs(self) -> Dict[str, Any]:
        """Pin (provider, model) exactly like the planner: generate_structured_
        response forwards provider_model into the handler, collapsing the
        option list to one reachable (provider, model). Unpinned "auto"
        routing sends bulk extraction to frontier models by value score."""
        kwargs: Dict[str, Any] = {}
        try:
            if "openrouter" in self.llm_service._get_handler().clients:
                kwargs["provider_model"] = ("openrouter", KG_EXTRACTION_MODEL)
        except Exception:
            pass
        return kwargs

    async def _extract_via_llm(self, system_prompt: str, text: str, workspace_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Pinned extraction call with one UNPINNED retry (planner pattern).

        The pin is a single attempt with no provider fallback; if it returns
        None (key can't serve the pinned model — out of credits, gated,
        revoked), the unpinned retry re-ranks across the workspace's own
        configured providers so extraction still lands. Both failing returns
        None so the caller keeps its empty-knowledge contract."""
        llm_kwargs = self._extraction_llm_kwargs()
        call = dict(
            prompt=f"Text to analyze:\n{text[:10000]}",
            response_model=ExtractionResult,
            system_instruction=system_prompt,
            temperature=0.1,
            disable_reasoning=True,
        )
        result = await self.llm_service.generate_structured_response(
            workspace_id=workspace_id, **call, **llm_kwargs
        )
        if result is None and "provider_model" in llm_kwargs:
            logger.info("pinned extraction call returned None — retrying unpinned")
            result = await self.llm_service.generate_structured_response(
                workspace_id=workspace_id, **call
            )
        if result is None:
            return None
        return result.model_dump()

    async def extract_knowledge(self, text: str, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None, source: str = "unknown") -> Dict[str, Any]:
        """
        Processes text to extract a structured knowledge graph.
        Schema-constrained: the prompt is generated from the ontology tables
        (entity types with hierarchy + declared relation triples), falling
        back to the legacy hardcoded lists when the ontology is unavailable.
        """
        wid = workspace_id or self.workspace_id
        tid = tenant_id or self.tenant_id
        
        # Schema-constrained prompt from the ontology tables; legacy hardcoded
        # lists remain the fallback (ontology layer must never break extraction).
        system_prompt = await self._build_extraction_prompt(wid)
        if system_prompt is None:
            # Base entities (legacy fallback)
            base_entities = [
                "Person (name, role, organization, is_stakeholder: bool)",
                "Project (name, status)",
                "Task (description, status, owner)",
                "File (filename, type)",
                "Decision (summary, context, date, impact_level)",
                "Organization (name)",
                "Transaction (amount, currency, merchant, date, category)",
                "Invoice (invoice_number, amount, recipient, status, due_date)",
                "Lead (name, company, email, score, external_id)",
                "Deal (name, value, stage, health_score, external_id)",
                "Quote (id, amount, items, terms, status: [requested, offered])",
                "PurchaseOrder (id, items, total_amount, vendor, shipping_address)",
                "SalesOrder (id, order_number, total_amount, items)",
                "Shipment (tracking_number, carrier, status, estimated_delivery)",
                "BusinessRule (description, type, value, applies_to)"
            ]

            # Fetch and append custom entities
            custom_types = await self._get_custom_entity_types(wid)
            for ct in custom_types:
                type_desc = f"{ct['display_name']} ({ct['description'] or 'Custom entity type'})"
                # Add schema hints if possible
                if ct['schema'] and 'properties' in ct['schema']:
                    props = ", ".join(ct['schema']['properties'].keys())
                    type_desc += f" - Fields: [{props}]"
                base_entities.append(type_desc)

            entities_prompt = "\n        - ".join(base_entities)

            system_prompt = f"""
        You are a Knowledge Graph Extraction Agent. Your goal is to analyze the provided text and extract a structured set of Entities and Relationships.

        **Target Entities:**
        - {entities_prompt}

        **Target Relationships & Intents:**
        - PARTICIPATED_IN (Person -> Meeting/Decision)
        - REFERENCE_TO (Text -> File/Project/ExternalLink)
        - OWNS (Person/Org -> Project/Task/File/Asset)
        - STAKEHOLDER_OF (Person -> Project/Organization)
        - INTENT (Message -> intent_type): values=[payment_commitment, churn_threat, upsell_inquiry, meeting_request, approval, request_quote, offer_quote, confirm_shipping, dispute_invoice]
        - UPDATES_STATUS (Shipment/Quote -> EcommerceOrder/Deal/Contract)
        - LINKS_TO_EXTERNAL (Entity -> external_system_id): Map to CRM/ERP IDs if mentioned.

        **Output Format (JSON strictly):**
        {{
          "entities": [
            {{"id": "unique_id", "type": "Person", "properties": {{"name": "...", "role": "...", "is_stakeholder": true/false}}}}
          ],
          "relationships": [
            {{"from": "id1", "to": "id2", "type": "OWNS", "properties": {{}}}},
            {{"from": "msg_id", "to": "intent_type", "type": "INTENT", "properties": {{"confidence": 0.9}}}}
          ]
        }}

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

            extracted_data = await self._extract_via_llm(system_prompt, safe_text, wid)
            if extracted_data is None:
                return {"entities": [], "relationships": []}
            return extracted_data

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
        response = await self.llm_service.generate_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript[:10000]}
            ],
            temperature=0.1
        )
        if response and response.get("content"):
            content = response.get("content", "{}")
            try:
                # Clean up markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                return json.loads(content)
            except json.JSONDecodeError:
                return {"entities": [], "relationships": []}
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
