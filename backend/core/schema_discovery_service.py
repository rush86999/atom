"""
Schema Discovery Service

Dynamically creates entity type schemas from LLM-extracted entities.
Groups by _discovered_type, infers JSON Schema, creates EntityTypeDefinition.

Phase 323-02: Schema Discovery & Entity Linking
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import datetime, timezone

from core.models import DiscoveredEntity, EntityTypeDefinition, GraphNode
from core.schema_validator import SchemaValidator
from core.entity_type_service import EntityTypeService

logger = logging.getLogger(__name__)


class SchemaDiscoveryService:
    """
    Discover entity type schemas from LLM-extracted entities.

    Process:
    1. Group DiscoveredEntity by _discovered_type
    2. Infer JSON Schema from property patterns
    3. Create EntityTypeDefinition with discovered schema
    4. Update DiscoveredEntity with new entity type ID

    Features:
    - Automatic schema inference from 5+ entity samples
    - JSON Schema generation (type, format, required fields)
    - Quality thresholds (min_sample_count=5)
    - Confidence tracking
    """

    def __init__(
        self,
        db: Session,
        schema_validator: Optional[SchemaValidator] = None,
        entity_type_service: Optional[EntityTypeService] = None
    ):
        """
        Initialize Schema Discovery Service.

        Args:
            db: Database session
            schema_validator: Schema validator instance
            entity_type_service: Entity type service instance
        """
        self.db = db
        self.validator = schema_validator or SchemaValidator()
        # Note: EntityTypeService may not exist, we'll handle it
        self.entity_type_service = entity_type_service

    async def discover_schemas_from_entities(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        min_sample_count: int = 5
    ) -> List[EntityTypeDefinition]:
        """
        Discover entity type schemas from pending DiscoveredEntity instances.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional Workspace UUID (if provided, limits discovery to this workspace)
            min_sample_count: Minimum entities of a type before creating schema (default: 5)

        Returns:
            List of created EntityTypeDefinition instances
        """
        # Fetch all pending discovered entities
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == "pending"
        )
        
        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)
            
        discovered_entities = query.all()

        if not discovered_entities:
            logger.info(f"No pending discovered entities for tenant {tenant_id}")
            return []

        # Group by _discovered_type
        entities_by_type = defaultdict(list)
        for entity in discovered_entities:
            entities_by_type[entity._discovered_type].append(entity)

        logger.info(f"Found {len(entities_by_type)} unique entity types from {len(discovered_entities)} entities")

        # Discover schemas for types with enough samples
        created_types = []
        for discovered_type, entities in entities_by_type.items():
            if len(entities) >= min_sample_count:
                logger.info(f"Discovering schema for {discovered_type} from {len(entities)} samples")

                entity_type = await self._discover_schema_for_type(
                    discovered_type,
                    entities,
                    tenant_id,
                    workspace_id
                )

                if entity_type:
                    created_types.append(entity_type)
                    logger.info(f"✓ Created EntityTypeDefinition: {entity_type.slug}")
            else:
                logger.info(f"⊗ Skipping {discovered_type} (only {len(entities)} samples, need {min_sample_count})")

        return created_types

    async def _discover_schema_for_type(
        self,
        discovered_type: str,
        entities: List[DiscoveredEntity],
        tenant_id: str,
        workspace_id: Optional[str] = None
    ) -> Optional[EntityTypeDefinition]:
        """
        Infer JSON Schema for a specific discovered type.

        Args:
            discovered_type: PascalCase entity type name (e.g., "PurchaseOrder")
            entities: List of DiscoveredEntity instances with this type
            tenant_id: Tenant UUID
            workspace_id: Optional Workspace UUID

        Returns:
            EntityTypeDefinition instance or None if inference fails
        """
        # Check if type already exists to avoid duplicates (tenant level)
        slug = self._pascal_to_slug(discovered_type)
        existing = self.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == tenant_id,
            EntityTypeDefinition.slug == slug
        ).first()
        
        if existing:
            logger.info(f"Entity type {slug} already exists for tenant {tenant_id}")
            return existing

        # Infer JSON Schema from entity properties
        json_schema = self._infer_json_schema(entities)

        # Validate schema
        # Note: Skip validation if validator doesn't exist or fails
        try:
            if hasattr(self.validator, 'validate_schema'):
                is_valid, errors = self.validator.validate_schema(json_schema)
                if not is_valid:
                    logger.warning(f"Schema validation failed for {discovered_type}: {errors}")
                    # Continue anyway, let the user review
        except Exception as e:
            logger.warning(f"Schema validation error for {discovered_type}: {e}")

        # Calculate average confidence
        avg_confidence = sum(e.confidence_score for e in entities) / len(entities)

        # Create EntityTypeDefinition
        entity_type = EntityTypeDefinition(
            tenant_id=tenant_id,
            slug=slug,
            display_name=discovered_type,
            json_schema=json_schema,
            description=f"Auto-discovered from {len(entities)} {discovered_type} entities via LLM extraction",
            is_active=True,
            metadata_json={
                "discovered_type": discovered_type,
                "sample_count": len(entities),
                "sample_entity_ids": [str(e.id) for e in entities[:5]],
                "confidence_score": round(avg_confidence, 3),
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "auto_created": True
            }
        )

        self.db.add(entity_type)
        self.db.flush()  # Get entity_type.id

        # Update entities to linked status
        for entity in entities:
            entity.entity_type_id = entity_type.id
            entity.status = "linked"
            entity.processed_at = datetime.now(timezone.utc)

        logger.info(f"Created EntityTypeDefinition: {slug} from {discovered_type} and linked {len(entities)} samples")
        return entity_type

    def _infer_json_schema(
        self,
        entities: List[DiscoveredEntity]
    ) -> Dict[str, Any]:
        """
        Infer JSON Schema from entity properties.

        Analyzes property types, formats, required fields across all samples.
        Uses statistical analysis to determine property types.

        Args:
            entities: List of DiscoveredEntity instances

        Returns:
            JSON Schema dictionary
        """
        from collections import Counter

        # Aggregate property types across all entities
        property_types = defaultdict(lambda: defaultdict(int))
        property_examples = defaultdict(list)
        required_counter = Counter()
        all_values = defaultdict(list)

        for entity in entities:
            for prop_name, prop_value in entity.properties.items():
                # Infer type from value
                prop_type = self._infer_type_from_value(prop_value)
                property_types[prop_name][prop_type] += 1
                property_examples[prop_name].append(prop_value)
                all_values[prop_name].append(prop_value)

                # Track required fields (non-null values)
                if prop_value is not None and prop_value != "":
                    required_counter[prop_name] += 1

        # Build JSON Schema
        properties = {}
        required_fields = []

        for prop_name, type_counts in property_types.items():
            # Use most common type
            most_common_type = max(type_counts, key=type_counts.get)

            schema_def = {"type": most_common_type}

            # Add format for strings
            if most_common_type == "string":
                format_info = self._infer_string_format(property_examples[prop_name])
                if format_info:
                    schema_def.update(format_info)

            # Add format for numbers
            if most_common_type == "number":
                format_info = self._infer_number_format(all_values[prop_name])
                if format_info:
                    schema_def.update(format_info)

            # Add array item type if present
            if most_common_type == "array":
                array_types = [self._infer_array_item_type(v) for v in all_values[prop_name] if isinstance(v, list)]
                if array_types:
                    most_common_item_type = max(set(array_types), key=array_types.count)
                    schema_def["items"] = {"type": most_common_item_type}

            properties[prop_name] = schema_def

            # Mark as required if present in 90%+ of entities
            if required_counter[prop_name] / len(entities) >= 0.9:
                required_fields.append(prop_name)

        json_schema = {
            "type": "object",
            "properties": properties,
            "required": required_fields,
            "additionalProperties": False
        }

        return json_schema

    def _infer_type_from_value(self, value: Any) -> str:
        """
        Infer JSON Schema type from Python value.

        Args:
            value: Python value

        Returns:
            JSON Schema type string
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "string"  # Fallback

    def _infer_array_item_type(self, array_value: list) -> str:
        """
        Infer type of array items.

        Args:
            array_value: List value

        Returns:
            Most common item type
        """
        if not array_value:
            return "string"

        item_types = [self._infer_type_from_value(item) for item in array_value if item is not None]
        if not item_types:
            return "string"

        # Return most common type
        from collections import Counter
        type_counts = Counter(item_types)
        return type_counts.most_common(1)[0][0]

    def _infer_string_format(self, examples: List[Any]) -> Dict[str, Any]:
        """
        Infer format for string properties.

        Args:
            examples: List of string values

        Returns:
            Format information dict
        """
        if not examples:
            return {}

        # Check for email format
        email_count = 0
        for example in examples:
            if isinstance(example, str) and "@" in example and "." in example.split("@")[1]:
                email_count += 1

        if email_count / len(examples) >= 0.8:
            return {"format": "email"}

        # Check for date-time format
        date_indicators = ["2026-", "T", "-", ":", "Z"]
        date_count = 0
        for example in examples:
            if isinstance(example, str):
                if any(indicator in example for indicator in date_indicators):
                    date_count += 1

        if date_count / len(examples) >= 0.5:
            return {"format": "date-time"}

        # Check for enum (low cardinality)
        unique_values = [str(e) for e in examples if e is not None]
        if len(set(unique_values)) <= 10 and len(set(unique_values)) / len(unique_values) > 0.3:
            return {"enum": list(set(unique_values))}

        return {}

    def _infer_number_format(self, examples: List[Any]) -> Dict[str, Any]:
        """
        Infer format for number properties.

        Args:
            examples: List of number values

        Returns:
            Format information dict
        """
        if not examples:
            return {}

        # Check for currency (2 decimal places)
        decimal_count = 0
        for value in examples:
            if isinstance(value, float):
                if abs(value - round(value, 2)) < 0.001:
                    decimal_count += 1

        res = {}
        if decimal_count / len(examples) >= 0.8:
            res = {"format": "currency", "multipleOf": 0.01}

        # Check for minimum/maximum
        numeric_values = [v for v in examples if isinstance(v, (int, float))]
        if numeric_values:
            res.update({
                "minimum": min(numeric_values),
                "maximum": max(numeric_values)
            })
        return res

    def _pascal_to_slug(self, pascal_string: str) -> str:
        """
        Convert PascalCase to slug_case.

        Args:
            pascal_string: PascalCase string (e.g., "PurchaseOrder")

        Returns:
            slug_case string (e.g., "purchase_order")
        """
        import re
        # Insert underscore before capital letters, convert to lowercase
        slug = re.sub('([A-Z])', r'_\1', pascal_string).lower().lstrip('_')
        return slug
