"""
Entity Linking Service

Link DiscoveredEntity instances to GraphNodes via type matching.
Matches _discovered_type to EntityTypeDefinition.slug.

Phase 323-02: Schema Discovery & Entity Linking
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from core.models import DiscoveredEntity, GraphNode, EntityTypeDefinition
from core.schema_discovery_service import SchemaDiscoveryService

logger = logging.getLogger(__name__)


class EntityLinkingService:
    """
    Link discovered entities to graph nodes.

    Process:
    1. Match DiscoveredEntity._discovered_type to EntityTypeDefinition.slug
    2. Create GraphNode with proper type
    3. Update DiscoveredEntity.status to 'linked'
    4. Handle novel types (create draft EntityTypeDefinition)

    Features:
    - Automatic type matching (PascalCase → slug_case)
    - Novel type creation with schema inference
    - Batch linking for performance
    - Confidence-based filtering
    """

    def __init__(
        self,
        db: Session,
        schema_discovery_service: SchemaDiscoveryService
    ):
        """
        Initialize Entity Linking Service.

        Args:
            db: Database session
            schema_discovery_service: Schema discovery service instance
        """
        self.db = db
        self.schema_discovery = schema_discovery_service

    async def link_entities_to_graph(
        self,
        tenant_id: str,
        workspace_id: str,
        auto_create_types: bool = True,
        min_confidence: float = 0.0
    ) -> List[GraphNode]:
        """
        Link all pending DiscoveredEntity instances to GraphNodes.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Workspace UUID
            auto_create_types: Create EntityTypeDefinition for novel types
            min_confidence: Minimum confidence score to link (0.0-1.0)

        Returns:
            List of created GraphNode instances
        """
        # Fetch all pending discovered entities
        discovered_entities = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.workspace_id == workspace_id,
            DiscoveredEntity.status == "pending",
            DiscoveredEntity.confidence_score >= min_confidence
        ).all()

        if not discovered_entities:
            logger.info(f"No pending discovered entities to link for tenant {tenant_id}")
            return []

        logger.info(f"Linking {len(discovered_entities)} discovered entities to graph")

        # Get all active entity types
        entity_types = self.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == tenant_id,
            EntityTypeDefinition.is_active == True
        ).all()

        # Create type lookup by slug
        type_by_slug = {et.slug: et for et in entity_types}

        linked_nodes = []
        novel_types = set()

        for entity in discovered_entities:
            # Convert _discovered_type to slug
            target_slug = self._discovered_type_to_slug(entity._discovered_type)

            # Check if entity type exists
            if target_slug in type_by_slug:
                # Create GraphNode
                graph_node = entity.to_graph_node(target_slug)
                self.db.add(graph_node)
                self.db.flush()  # Get graph_node.id

                # Update DiscoveredEntity
                entity.mark_linked(graph_node.id)

                linked_nodes.append(graph_node)
                logger.info(f"✓ Linked {entity.id} ({entity._discovered_type} → {target_slug})")

            elif auto_create_types:
                # Novel type - add to set for batch creation
                novel_types.add(entity._discovered_type)

        # Handle novel types
        if novel_types and auto_create_types:
            logger.info(f"Creating {len(novel_types)} novel entity types")
            for discovered_type in novel_types:
                # Group entities by novel type
                entities_of_type = [e for e in discovered_entities if e._discovered_type == discovered_type]

                if entities_of_type:
                    # Use schema discovery to create entity type
                    entity_types = await self.schema_discovery.discover_schemas_from_entities(
                        tenant_id,
                        workspace_id,
                        min_sample_count=1  # Allow single-sample types
                    )

                    # Link entities to newly created type
                    for entity_type in entity_types:
                        if entity_type.slug == self._discovered_type_to_slug(discovered_type):
                            # Now link the entities
                            for entity in entities_of_type:
                                if entity.status == "pending":  # Not yet linked
                                    graph_node = entity.to_graph_node(entity_type.slug)
                                    self.db.add(graph_node)
                                    self.db.flush()

                                    entity.mark_linked(graph_node.id)
                                    linked_nodes.append(graph_node)
                                    logger.info(f"✓ Created novel type {entity_type.slug} and linked {entity.id}")

        self.db.commit()
        logger.info(f"Successfully linked {len(linked_nodes)} entities to graph")
        return linked_nodes

    def _discovered_type_to_slug(self, discovered_type: str) -> str:
        """
        Convert PascalCase _discovered_type to slug.

        Args:
            discovered_type: PascalCase string (e.g., "PurchaseOrder")

        Returns:
            slug_case string (e.g., "purchase_order")
        """
        import re
        slug = re.sub('([A-Z])', r'_\1', discovered_type).lower().lstrip('_')
        return slug

    async def link_single_entity(
        self,
        entity_id: str,
        entity_type_slug: str,
        create_type_if_missing: bool = True
    ) -> Optional[GraphNode]:
        """
        Link a single discovered entity to the graph.

        Args:
            entity_id: DiscoveredEntity UUID
            entity_type_slug: Target entity type slug
            create_type_if_missing: Create EntityTypeDefinition if it doesn't exist

        Returns:
            Created GraphNode or None if entity not found
        """
        # Fetch entity
        entity = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.id == entity_id
        ).first()

        if not entity:
            logger.error(f"DiscoveredEntity {entity_id} not found")
            return None

        # Check if entity type exists
        entity_type = self.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == entity.tenant_id,
            EntityTypeDefinition.slug == entity_type_slug,
            EntityTypeDefinition.is_active == True
        ).first()

        if not entity_type and create_type_if_missing:
            # Create entity type from entity
            slug = entity_type_slug
            discovered_type = entity._discovered_type

            entity_type = EntityTypeDefinition(
                tenant_id=entity.tenant_id,
                slug=slug,
                display_name=discovered_type,
                json_schema=self._infer_schema_from_single_entity(entity),
                source="llm_discovery",
                description=f"Auto-created from single {discovered_type} entity",
                is_active=True,
                metadata_json={
                    "discovered_type": discovered_type,
                    "sample_count": 1,
                    "auto_created": True
                }
            )
            self.db.add(entity_type)
            self.db.flush()
            logger.info(f"✓ Created EntityTypeDefinition: {slug} from single entity")

        if entity_type:
            # Create GraphNode
            graph_node = entity.to_graph_node(entity_type.slug)
            self.db.add(graph_node)
            self.db.flush()

            # Update DiscoveredEntity
            entity.mark_linked(graph_node.id)
            self.db.commit()

            logger.info(f"✓ Linked {entity_id} to {entity_type_slug}")
            return graph_node
        else:
            logger.error(f"EntityTypeDefinition {entity_type_slug} not found and auto_create_if_missing=False")
            return None

    def _infer_schema_from_single_entity(self, entity: DiscoveredEntity) -> Dict[str, Any]:
        """
        Infer JSON Schema from single entity.

        Args:
            entity: DiscoveredEntity instance

        Returns:
            JSON Schema dictionary
        """
        properties = {}
        required_fields = []

        for prop_name, prop_value in entity.properties.items():
            if prop_value is not None:
                required_fields.append(prop_name)

            properties[prop_name] = self._infer_schema_from_value(prop_value)

        return {
            "type": "object",
            "properties": properties,
            "required": required_fields,
            "additionalProperties": False
        }

    def _infer_schema_from_value(self, value: Any) -> Dict[str, Any]:
        """
        Infer JSON Schema from single value.

        Args:
            value: Python value

        Returns:
            JSON Schema property definition
        """
        if value is None:
            return {"type": "null"}
        elif isinstance(value, bool):
            return {"type": "boolean"}
        elif isinstance(value, int):
            return {"type": "integer"}
        elif isinstance(value, float):
            return {"type": "number"}
        elif isinstance(value, str):
            return {"type": "string"}
        elif isinstance(value, list):
            return {"type": "array", "items": {"type": "string"}}
        elif isinstance(value, dict):
            return {"type": "object"}
        else:
            return {"type": "string"}
