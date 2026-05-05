from __future__ import annotations

"""
Open IE Schema Discovery Service

AI-powered entity type discovery using Open Information Extraction.
Extracts entity types from integration data without pre-defined schemas.
Uses LLM with core entity hardcoding for intelligent classification.
"""
import json
import logging
from typing import Any, Union

from sqlalchemy.orm import Session

from core.byok_endpoints import get_byok_manager
from core.database import SessionLocal
from core.entity_type_service import EntityTypeService

logger = logging.getLogger(__name__)

# Core entity schemas with few-shot examples for LLM guidance
# These are hardcoded to ensure consistent mapping to canonical types
CORE_ENTITY_SCHEMAS = {
    "Person": {
        "canonical_type": "user",
        "description": "A human person with name, email, title",
        "properties": ["name", "email", "title", "phone"],
        "examples": [
            {"name": "John Doe", "email": "john@example.com", "title": "CEO"},
            {"name": "Jane Smith", "email": "jane@company.co", "title": "Sales Manager"},
        ],
    },
    "Organization": {
        "canonical_type": "organization",
        "description": "A company, organization, or business entity",
        "properties": ["name", "domain", "industry", "size"],
        "examples": [
            {"name": "Acme Corp", "domain": "acme.com", "industry": "Technology"},
            {"name": "Global Industries", "industry": "Manufacturing"},
        ],
    },
    "Contact": {
        "canonical_type": "contact",
        "description": "A business contact or lead",
        "properties": ["name", "email", "company", "status"],
        "examples": [
            {"name": "Dr. Sarah Johnson", "email": "sarah@clinic.com", "company": "City Clinic"},
            {"name": "Mike Ross", "email": "mike@firm.com", "status": "lead"},
        ],
    },
    "Project": {
        "canonical_type": "project",
        "description": "A project or initiative with goals and timeline",
        "properties": ["name", "description", "status", "deadline"],
        "examples": [
            {"name": "Website Redesign", "status": "in_progress", "deadline": "2025-06-01"},
            {"name": "Q4 Sales Push", "description": "End of year sales campaign"},
        ],
    },
    "Task": {
        "canonical_type": "task",
        "description": "An actionable task or todo item",
        "properties": ["title", "description", "status", "assignee", "due_date"],
        "examples": [
            {"title": "Review proposal", "status": "pending", "assignee": "John"},
            {"title": "Send invoice", "due_date": "2025-04-01"},
        ],
    },
}


class OpenIESchemaDiscovery:
    """
    Open Information Extraction schema discovery service.

    Uses LLM to automatically discover entity types from integration data.
    Hardcodes core entities (Person, Organization, Contact, Project, Task)
    for consistent mapping to canonical types.
    Creates draft entity types for unknown entities.

    Features:
    - Core entity hardcoding with few-shot prompting
    - Fuzzy matching for similar entity types (Customer → Contact)
    - Draft entity type creation with discovery reasoning
    - Confidence scoring for discovered types
    - BYOK support for tenant-specific OpenAI keys
    """

    def __init__(
        self, tenant_id: str = "default", db: Union[Session, None] = None, workspace_id: Union[str, None] = None
    ):
        """
        Initialize OpenIE discovery service.

        Args:
            tenant_id: Tenant UUID for isolation
            db: Optional database session (creates SessionLocal if not provided)
            workspace_id: Optional Workspace UUID for multi-workspace support
        """
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id
        self.db = db or SessionLocal()
        self.entity_type_service = EntityTypeService(db=self.db)

    def _get_llm_client(self):
        """
        Get LLM client with BYOK support.

        Returns:
            OpenAI client or None if no key available
        """
        try:
            from openai import OpenAI

            byok = get_byok_manager()
            # 1. Try Tenant-specific Key
            api_key = byok.get_tenant_api_key(self.tenant_id, "openai")

            # 2. Fallback to Platform Key
            if not api_key:
                api_key = byok.get_api_key("openai")

            if api_key:
                return OpenAI(api_key=api_key)
            return None
        except ImportError:
            logger.warning("OpenAI or BYOK Manager not available")
            return None
        except Exception as e:
            logger.error(f"Failed to get LLM client: {e}")
            return None

    def _build_extraction_prompt(self, sample_data: list[dict[str, Any]]) -> str:
        """
        Build LLM prompt with core entity definitions as few-shot examples.

        Args:
            sample_data: Sample integration records to analyze

        Returns:
            Prompt string with core entity schemas and instructions
        """
        core_entities_section = json.dumps(CORE_ENTITY_SCHEMAS, indent=2)

        sample_data_section = json.dumps(sample_data[:5], indent=2)

        prompt = f"""Analyze the following integration data and extract entity types.

Core Entity Types (prefer these when matching):
{core_entities_section}

Instructions:
1. Check if entities match Core Entity Types above - use canonical_type if match found
2. For non-matching entities, create appropriate custom types
3. Provide discovery reasoning for each entity type
4. Respond with valid JSON only.

Sample Integration Data:
{sample_data_section}

JSON Schema:
{{
  "entities": [
    {{
      "name": "string",
      "type": "string",
      "canonical_type": "string (optional: user, organization, contact, project, task)",
      "description": "string",
      "properties": {{}}
    }}
  ],
  "relationships": [
    {{
      "from": "string",
      "to": "string",
      "type": "string",
      "description": "string"
    }}
  ],
  "discovery_reasoning": "Explanation of why these entity types were identified"
}}
"""
        return prompt

    def extract_entities_with_core_hardcoding(
        self, text: str, source: str = "unknown"
    ) -> dict[str, Any]:
        """
        Extract entities with core entity hardcoding using LLM.

        Args:
            text: Integration data text to analyze
            source: Data source identifier

        Returns:
            Dict with entities, relationships, and classification counts
        """
        client = self._get_llm_client()
        if not client:
            logger.warning("LLM client not available, skipping extraction")
            return {
                "entities": [],
                "relationships": [],
                "core_entity_count": 0,
                "custom_entity_count": 0,
                "error": "LLM client not available",
            }

        try:
            prompt = self._build_extraction_prompt_from_text(text)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a knowledge graph extractor. Output valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            entities = []
            relationships = []
            core_count = 0
            custom_count = 0

            # Process entities with core entity classification
            for e in data.get("entities", []):
                classification = self._classify_entity_type(
                    e.get("name", ""), e.get("properties", {})
                )

                properties = {
                    "source": source,
                    "llm_extracted": True,
                    "is_core": classification["is_core"],
                    "is_custom": not classification["is_core"],
                }

                if classification["is_core"]:
                    properties["canonical_type"] = classification["canonical_type"]
                    core_count += 1
                else:
                    custom_count += 1

                entities.append(
                    {
                        "name": e["name"],
                        "type": e.get("type", "unknown"),
                        "description": e.get("description", ""),
                        "properties": properties,
                    }
                )

            # Process relationships
            for r in data.get("relationships", []):
                relationships.append(
                    {
                        "from": r["from"],
                        "to": r["to"],
                        "type": r["type"],
                        "description": r.get("description", ""),
                        "properties": {"llm_extracted": True},
                    }
                )

            return {
                "entities": entities,
                "relationships": relationships,
                "core_entity_count": core_count,
                "custom_entity_count": custom_count,
                "discovery_reasoning": data.get("discovery_reasoning", ""),
            }

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {
                "entities": [],
                "relationships": [],
                "core_entity_count": 0,
                "custom_entity_count": 0,
                "error": str(e),
            }

    def _build_extraction_prompt_from_text(self, text: str) -> str:
        """
        Build extraction prompt from raw text.

        Args:
            text: Text to analyze

        Returns:
            Prompt string
        """
        core_entities_section = json.dumps(CORE_ENTITY_SCHEMAS, indent=2)

        prompt = f"""Analyze the following text and extract knowledge graph elements.

Core Entity Types (prefer these when matching):
{core_entities_section}

Instructions:
1. Check if entities match Core Entity Types above - use canonical_type if match found
2. For non-matching entities, create appropriate custom types
3. Respond with valid JSON only.

Text:
\"\"\"
{text[:6000]}
\"\"\"

JSON Schema:
{{
  "entities": [
    {{
      "name": "string",
      "type": "string",
      "canonical_type": "string (optional: user, organization, contact, project, task)",
      "description": "string",
      "properties": {{}}
    }}
  ],
  "relationships": [
    {{
      "from": "string",
      "to": "string",
      "type": "string",
      "description": "string"
    }}
  ],
  "discovery_reasoning": "Explanation of entity type discovery"
}}
"""
        return prompt

    def _classify_entity_type(self, entity_name: str, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Classify entity type against core entities using fuzzy matching.

        Args:
            entity_name: Name of entity to classify
            properties: Entity properties for matching

        Returns:
            Dict with is_core, canonical_type, confidence
        """
        entity_name_lower = entity_name.lower()

        # Direct name match
        for core_type, schema in CORE_ENTITY_SCHEMAS.items():
            if entity_name_lower == core_type.lower():
                return {
                    "is_core": True,
                    "canonical_type": schema["canonical_type"],
                    "confidence": 1.0,
                }

        # Fuzzy matching for similar names
        fuzzy_matches = {
            "customer": "contact",
            "client": "contact",
            "lead": "contact",
            "company": "organization",
            "employer": "organization",
            "business": "organization",
            "employee": "user",
            "worker": "user",
            "staff": "user",
            "todo": "task",
            "todoitem": "task",
            "action": "task",
            "initiative": "project",
            "program": "project",
        }

        if entity_name_lower in fuzzy_matches:
            canonical_type = fuzzy_matches[entity_name_lower]
            return {"is_core": True, "canonical_type": canonical_type, "confidence": 0.8}

        # Property-based matching
        prop_keys = set(k.lower() for k in properties)

        for core_type, schema in CORE_ENTITY_SCHEMAS.items():
            core_props = set(p.lower() for p in schema["properties"])
            overlap = len(prop_keys & core_props)

            # If 60% of properties match core entity
            if overlap >= len(core_props) * 0.6:
                return {
                    "is_core": True,
                    "canonical_type": schema["canonical_type"],
                    "confidence": 0.7,
                }

        # No match - custom entity
        return {"is_core": False, "canonical_type": None, "confidence": 0.0}

    @staticmethod
    def _normalize_slug(slug: str) -> str:
        """
        Normalize an entity type slug for deduplication.

        Handles LLM-generated near-identical variants (e.g., "email", "email_subject",
        "emailsubject" → "email") by applying canonicalization rules.

        Args:
            slug: Raw slug (may already be lowercased with underscores)

        Returns:
            Normalized canonical slug
        """
        # --- Alias map for known synonyms ---
        ALIAS_MAP: dict[str, str] = {
            "emailsubject": "email",
            "email_subject": "email",
            "mail": "email",
            "contact_email": "email",
            "person_name": "person",
            "people": "person",
            "organization_name": "organization",
            "company_name": "organization",
            "phone_number": "phone",
            "telephone": "phone",
            "url_link": "url",
            "hyperlink": "url",
            "date_time": "datetime",
            "timestamp": "datetime",
        }

        # --- Step 1: Lowercase and replace spaces/hyphens with underscores ---
        normalized = slug.lower().strip()
        normalized = normalized.replace(" ", "_").replace("-", "_")

        # Collapse multiple underscores
        while "__" in normalized:
            normalized = normalized.replace("__", "_")

        # --- Step 2: Check alias map first (exact match after normalization) ---
        if normalized in ALIAS_MAP:
            return ALIAS_MAP[normalized]

        # --- Step 3: Strip common redundant suffixes ---
        REDUNDANT_SUFFIXES = [
            "_subject",
            "_content",
            "_body",
            "_header",
            "_detail",
            "_info",
            "_data",
            "_record",
            "_item",
            "_entry",
        ]
        for suffix in REDUNDANT_SUFFIXES:
            if normalized.endswith(suffix):
                stripped = normalized[: -len(suffix)]
                if stripped:  # Ensure we don't strip everything
                    normalized = stripped
                    break  # Only strip one suffix

        # --- Step 4: Singularize common plurals ---
        PLURAL_TO_SINGULAR: dict[str, str] = {
            "emails": "email",
            "contacts": "contact",
            "organizations": "organization",
            "companies": "company",
            "people": "person",
            "persons": "person",
            "tasks": "task",
            "projects": "project",
            "users": "user",
            "phones": "phone",
            "urls": "url",
            "addresses": "address",
            "notes": "note",
            "messages": "message",
            "documents": "document",
            "files": "file",
            "events": "event",
            "orders": "order",
            "products": "product",
            "items": "item",
            "records": "record",
            "entries": "entry",
            "dates": "date",
            "times": "time",
            "numbers": "number",
            "names": "name",
        }
        if normalized in PLURAL_TO_SINGULAR:
            normalized = PLURAL_TO_SINGULAR[normalized]
        # Generic -s plural: strip trailing 's' if word is long enough
        elif normalized.endswith("s") and len(normalized) > 4 and not normalized.endswith("ss"):
            # Only strip if it looks like a plural (not words like "status", "address")
            if not normalized.endswith("us") and not normalized.endswith("is"):
                root = normalized[:-1]
                # Basic heuristic: if the root is at least 3 chars, it's likely a valid singular
                if len(root) >= 3:
                    normalized = root

        # --- Step 5: Re-check alias map after transformations ---
        if normalized in ALIAS_MAP:
            return ALIAS_MAP[normalized]

        return normalized

    def create_draft_entity_type(
        self,
        slug: str,
        display_name: str,
        properties: dict[str, Any],
        discovery_reasoning: str,
        confidence: float = 0.7,
        workspace_id: Union[str, None] = None,
        integration_id: Union[str, None] = None,
        original_type: Union[str, None] = None,
    ):
        """
        Create draft entity type from discovered schema.
        Idempotent: Returns existing entity type if it already exists.

        Args:
            slug: Entity type slug
            display_name: Human-readable name
            properties: Discovered properties
            discovery_reasoning: LLM explanation of discovery
            confidence: Confidence score (0-1)
            workspace_id: Optional Workspace UUID override (pass None for tenant-wide)

        Returns:
            Created EntityTypeDefinition or None
        """
        try:
            # --- Normalize slug for deduplication ---
            slug = self._normalize_slug(slug)

            # Use provided workspace_id or fallback to service default
            target_workspace_id = workspace_id if workspace_id is not None else self.workspace_id

            # For "org" scope, workspace_id should be None to make it tenant-wide
            if target_workspace_id == self.tenant_id:
                target_workspace_id = None

            # Check if entity type already exists
            existing = self.entity_type_service.get_entity_type(
                tenant_id=self.tenant_id,
                slug=slug,
                include_inactive=True,
            )

            if existing:
                logger.debug(
                    f"Entity type '{slug}' already exists for tenant {self.tenant_id}. "
                    f"Skipping creation (id: {existing.id}, is_active: {existing.is_active})"
                )
                return existing

            # Generate JSON Schema from properties
            json_schema = self._generate_json_schema_from_properties(properties)

            # Create draft entity type (is_active=False)
            entity_type = self.entity_type_service.create_entity_type(
                tenant_id=self.tenant_id,
                slug=slug,
                display_name=display_name,
                json_schema=json_schema,
                description=f"Auto-discovered: {discovery_reasoning}",
                is_system=False,
                is_active=False,
            )
            self.db.commit()

            logger.info(
                f"Created draft entity type: {slug} "
                f"(confidence: {confidence}, reasoning: {discovery_reasoning[:50]}...)"
            )

            return entity_type

        except Exception as e:
            logger.error(f"Failed to create draft entity type {slug}: {e}")
            self.db.rollback()
            return None

    def _generate_json_schema_from_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Generate JSON Schema from discovered properties.

        Args:
            properties: Sample properties with values

        Returns:
            JSON Schema Draft 2020-12
        """
        schema_properties = {}
        required = []

        for prop_name, prop_value in properties.items():
            # Infer type from value
            if prop_value is None:
                prop_type = "string"
            elif isinstance(prop_value, bool):
                prop_type = "boolean"
                required.append(prop_name)
            elif isinstance(prop_value, int):
                prop_type = "integer"
                required.append(prop_name)
            elif isinstance(prop_value, float):
                prop_type = "number"
                required.append(prop_name)
            elif isinstance(prop_value, list):
                prop_type = "array"
            else:
                prop_type = "string"

            schema_properties[prop_name] = {"type": prop_type}

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": schema_properties,
            "required": required,
        }

    def close(self):
        """Close database session if created by this service."""
        if self.db is not None:
            self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
