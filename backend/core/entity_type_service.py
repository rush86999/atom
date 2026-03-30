"""
Entity Type Service

CRUD operations for dynamic entity type definitions.
Integrates schema validation and model cache management.
"""
import logging
import uuid
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from core.models import EntityTypeDefinition, EntityTypeVersionHistory, GraphNode
from core.schema_validator import SchemaValidator, get_schema_validator
from core.model_factory import ModelFactory, get_model_factory
from core.database import SessionLocal

logger = logging.getLogger(__name__)


class EntityTypeService:
    """CRUD operations for entity type definitions.

    Features:
    - Schema validation before storage
    - Duplicate slug detection per tenant
    - Cache invalidation on schema updates
    - Soft delete support
    - Pagination and filtering
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        schema_validator: Optional[SchemaValidator] = None,
        model_factory: Optional[ModelFactory] = None
    ):
        """
        Initialize entity type service.

        Args:
            db: Database session (creates SessionLocal if not provided)
            schema_validator: Schema validator instance
            model_factory: Model factory for cache invalidation
        """
        self.db = db or SessionLocal()
        self.validator = schema_validator or get_schema_validator()
        self.model_factory = model_factory or get_model_factory()

    def merge_entity_types(
        self,
        tenant_id: str,
        source_id: str,
        target_slug: str,
        workspace_id: Optional[str] = None
    ) -> bool:
        """
        Merge a discovered entity type (source) into an existing active type (target).
        Migrates all associated GraphNodes to the target type.
        
        Args:
            tenant_id: Tenant UUID
            source_id: ID of the draft entity type to merge from
            target_slug: Slug of the active entity type to merge into
            workspace_id: Optional workspace filtering for migration
            
        Returns:
            True if merge successful
        """
        from core.models import GraphNode
        
        source_type = self.get_entity_type(tenant_id, entity_type_id=source_id, include_inactive=True)
        if not source_type:
            raise ValueError(f"Source entity type '{source_id}' not found")
            
        target_type = self.get_entity_type(tenant_id, slug=target_slug)
        if not target_type:
            raise ValueError(f"Target entity type '{target_slug}' not found")
            
        # 1. Update all GraphNodes from source to target slug
        query = self.db.query(GraphNode).filter(
            GraphNode.tenant_id == tenant_id,
            GraphNode.type == source_type.slug
        )
        if workspace_id:
            query = query.filter(GraphNode.workspace_id == workspace_id)
            
        nodes_updated = query.update({GraphNode.type: target_slug}, synchronize_session=False)
        logger.info(f"Merged {nodes_updated} GraphNodes from {source_type.slug} to {target_slug}")
        
        # 2. Add source metadata to target's discovery history if applicable
        if target_type.metadata_json is None:
            target_type.metadata_json = {"merges": []}
        
        merges = target_type.metadata_json.get("merges", [])
        merges.append({
            "source_slug": source_type.slug,
            "source_reasoning": source_type.metadata_json.get("discovery_reasoning") if source_type.metadata_json else None,
            "date": datetime.utcnow().isoformat(),
            "nodes_count": nodes_updated
        })
        target_type.metadata_json["merges"] = merges
        
        # 3. Mark source as deleted/deactive
        source_type.is_active = False
        source_type.description = f"Merged into {target_slug} on {datetime.utcnow().isoformat()}"
        
        try:
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Merge failed: {e}")
            raise
    
    def resolve_or_create_draft(
        self,
        tenant_id: str,
        slug: str,
        display_name: str,
        json_schema: Dict[str, Any],
        description: Optional[str] = None,
        is_active: bool = False
    ) -> EntityTypeDefinition:
        """
        Idempotent resolver for automated discovery.
        If slug exists: updates schema (evolving version) if changed.
        If slug is new: creates a new draft entity type.
        
        Args:
            tenant_id: Tenant UUID
            slug: Entity type slug
            display_name: Suggested display name
            json_schema: Inferred JSON schema
            description: Optional description
            is_active: Whether the entity type is active (default False for drafts)
            
        Returns:
            Resolved/updated EntityTypeDefinition
        """
        existing = self.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == tenant_id,
            EntityTypeDefinition.slug == slug
        ).first()
        
        if existing:
            # Check if schema changed
            if existing.json_schema != json_schema:
                logger.info(f"Evolving schema for {slug} (v{existing.version} -> v{existing.version+1})")
                return self.update_entity_type(
                    tenant_id=tenant_id,
                    entity_type_id=str(existing.id),
                    json_schema=json_schema,
                    change_summary="Automated schema evolution detected during sync.",
                    changed_by="system:auto-discovery"
                )
            return existing
            
        # Create as new draft
        return self.create_entity_type(
            tenant_id=tenant_id,
            slug=slug,
            display_name=display_name,
            json_schema=json_schema,
            description=description,
            is_system=False,
            is_active=is_active
        )

    def create_entity_type(
        self,
        tenant_id: str,
        slug: str,
        display_name: str,
        json_schema: Dict[str, Any],
        description: Optional[str] = None,
        available_skills: Optional[List[str]] = None,
        is_system: bool = False,
        is_active: bool = True
    ) -> EntityTypeDefinition:
        """
        Create new entity type with schema validation.

        Args:
            tenant_id: Tenant UUID
            slug: URL-safe identifier (e.g., "invoice")
            display_name: Human-readable name
            json_schema: JSON Schema Draft 2020-12 definition
            description: Optional description
            available_skills: List of skill IDs that can operate on this entity type
            is_system: True for canonical entities (should not be modified)
            is_active: Whether the entity type is active or a draft

        Returns:
            Created EntityTypeDefinition

        Raises:
            ValueError: If validation fails or slug already exists
        """
        # Validate slug format (alphanumeric, hyphens, underscores only)
        if not self._is_valid_slug(slug):
            raise ValueError(
                f"Invalid slug '{slug}'. Must contain only alphanumeric characters, "
                "hyphens, and underscores."
            )

        # Validate JSON Schema against Draft 2020-12 meta-schema
        is_valid, error = self.validator.validate_schema(json_schema)
        if not is_valid:
            raise ValueError(f"Invalid JSON Schema: {error}")

        existing = self.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == tenant_id,
            EntityTypeDefinition.slug == slug
        ).first()

        if existing:
            raise ValueError(
                f"Entity type '{slug}' already exists for tenant. "
                f"Use update_entity_type() to modify the existing type."
            )

        # Create entity type definition
        entity_type = EntityTypeDefinition(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            slug=slug,
            display_name=display_name,
            description=description,
            json_schema=json_schema,
            available_skills=available_skills or [],
            is_system=is_system,
            is_active=is_active,
            version=1
        )

        try:
            self.db.add(entity_type)
            self.db.commit()
            self.db.refresh(entity_type)
            logger.info(f"Created entity type: {tenant_id}/{slug}")
            return entity_type
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create entity type {slug}: {e}")
            raise

    def get_entity_type(
        self,
        tenant_id: str,
        entity_type_id: Optional[str] = None,
        slug: Optional[str] = None,
        include_inactive: bool = False
    ) -> Optional[EntityTypeDefinition]:
        """
        Get entity type by ID or slug.

        Args:
            tenant_id: Tenant UUID
            entity_type_id: Entity type UUID (alternative to slug)
            slug: Entity type slug (alternative to entity_type_id)
            include_inactive: If True, returns even if is_active is False

        Returns:
            EntityTypeDefinition or None if not found
        """
        if not entity_type_id and not slug:
            raise ValueError("Must provide either entity_type_id or slug")

        query = self.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == tenant_id
        )

        if not include_inactive:
            query = query.filter(EntityTypeDefinition.is_active == True)

        if entity_type_id:
            query = query.filter(EntityTypeDefinition.id == entity_type_id)
        else:
            query = query.filter(EntityTypeDefinition.slug == slug)

        entity_type = query.first()

        if not entity_type:
            logger.debug(f"Entity type not found: {tenant_id}/{entity_type_id or slug}")
            return None

        return entity_type

    def list_entity_types(
        self,
        tenant_id: str,
        include_system: bool = False,
        is_active: Optional[bool] = True, # None for all, True for active, False for drafts
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[EntityTypeDefinition]:
        """
        List entity types for a tenant.

        Args:
            tenant_id: Tenant UUID
            include_system: Include system (canonical) entity types
            is_active: Filter by active status (True=Active, False=Drafts, None=All)
            search: Filter by display name or slug (case-insensitive partial match)
            limit: Maximum results to return
            offset: Number of results to skip

        Returns:
            List of EntityTypeDefinition
        """
        query = self.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == tenant_id
        )

        if is_active is not None:
            query = query.filter(EntityTypeDefinition.is_active == is_active)

        if not include_system:
            query = query.filter(EntityTypeDefinition.is_system == False)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    EntityTypeDefinition.display_name.ilike(search_pattern),
                    EntityTypeDefinition.slug.ilike(search_pattern)
                )
            )

        return query.order_by(
            EntityTypeDefinition.created_at.desc()
        ).limit(limit).offset(offset).all()

    def _create_version_snapshot(
        self,
        entity_type: EntityTypeDefinition,
        changed_by: Optional[str] = None,
        change_summary: Optional[str] = None
    ) -> EntityTypeVersionHistory:
        """
        Create a snapshot of current entity type state before modification.

        Args:
            entity_type: Entity type to snapshot
            changed_by: Optional user identifier who made the change
            change_summary: Optional description of what changed

        Returns:
            Created EntityTypeVersionHistory record
        """
        # Calculate schema hash for integrity
        schema_json = json.dumps(entity_type.json_schema, sort_keys=True)
        schema_hash = hashlib.sha256(schema_json.encode()).hexdigest()

        snapshot = EntityTypeVersionHistory(
            id=uuid.uuid4(),
            tenant_id=entity_type.tenant_id,
            entity_type_id=entity_type.id,
            version=entity_type.version,
            json_schema=entity_type.json_schema.copy() if entity_type.json_schema else {},
            display_name=entity_type.display_name,
            description=entity_type.description,
            available_skills=entity_type.available_skills.copy() if entity_type.available_skills else [],
            change_summary=change_summary or f"Version {entity_type.version} snapshot",
            changed_by=changed_by,
            schema_hash=schema_hash
        )

        self.db.add(snapshot)
        self.db.flush()  # Get ID without committing transaction
        logger.info(
            f"Created version snapshot for {entity_type.slug}: "
            f"v{entity_type.version} (hash: {schema_hash[:8]}...)"
        )
        return snapshot

    def update_entity_type(
        self,
        tenant_id: str,
        entity_type_id: str,
        display_name: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        available_skills: Optional[List[str]] = None,
        changed_by: Optional[str] = None,
        change_summary: Optional[str] = None
    ) -> EntityTypeDefinition:
        """
        Update entity type schema with cache invalidation.

        Args:
            tenant_id: Tenant UUID
            entity_type_id: Entity type UUID
            display_name: New display name
            json_schema: New JSON Schema definition
            description: New description
            available_skills: New available skills list
            changed_by: Optional user identifier who made the change
            change_summary: Optional description of what changed

        Returns:
            Updated EntityTypeDefinition

        Raises:
            ValueError: If entity type not found or validation fails
        """
        entity_type = self.get_entity_type(tenant_id, entity_type_id=entity_type_id)

        if not entity_type:
            raise ValueError(f"Entity type '{entity_type_id}' not found")

        # Prevent modification of system types
        if entity_type.is_system:
            raise ValueError(
                f"Cannot modify system entity type '{entity_type.slug}'. "
                "System types are read-only."
            )

        # Create version snapshot BEFORE applying changes
        if json_schema or display_name or description or available_skills is not None:
            self._create_version_snapshot(
                entity_type=entity_type,
                changed_by=changed_by,
                change_summary=change_summary
            )

        # Validate new schema if provided
        if json_schema:
            is_valid, error = self.validator.validate_schema(json_schema)
            if not is_valid:
                raise ValueError(f"Invalid JSON Schema: {error}")

            # Invalidate cached models BEFORE updating database
            # This prevents stale models from being used after update
            invalidated = self.model_factory.invalidate_cache(tenant_id, entity_type.slug)
            logger.info(f"Invalidated {invalidated} cached models for {tenant_id}/{entity_type.slug}")

            # Update schema and version
            entity_type.json_schema = json_schema
            entity_type.version += 1

        # Update other fields
        if display_name is not None:
            entity_type.display_name = display_name
        if description is not None:
            entity_type.description = description
        if available_skills is not None:
            entity_type.available_skills = available_skills

        try:
            self.db.commit()
            self.db.refresh(entity_type)
            logger.info(f"Updated entity type: {tenant_id}/{entity_type.slug} (v{entity_type.version})")
            return entity_type
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update entity type {entity_type_id}: {e}")
            raise

    def delete_entity_type(
        self,
        tenant_id: str,
        entity_type_id: str,
        hard_delete: bool = False
    ) -> bool:
        """
        Delete or deprecate entity type.

        Args:
            tenant_id: Tenant UUID
            entity_type_id: Entity type UUID
            hard_delete: If True, permanently delete; if False, soft delete (is_active=False)

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If trying to delete a system type
        """
        entity_type = self.get_entity_type(tenant_id, entity_type_id=entity_type_id)

        if not entity_type:
            return False

        # Prevent deletion of system types
        if entity_type.is_system:
            raise ValueError(
                f"Cannot delete system entity type '{entity_type.slug}'. "
                "System types are read-only."
            )

        if hard_delete:
            # Permanently delete
            try:
                # Invalidate cache before deletion
                self.model_factory.invalidate_cache(tenant_id, entity_type.slug)
                self.db.delete(entity_type)
                self.db.commit()
                logger.info(f"Hard deleted entity type: {tenant_id}/{entity_type.slug}")
                return True
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to delete entity type {entity_type_id}: {e}")
                raise
        else:
            # Soft delete (deprecate)
            try:
                # Invalidate cache before deactivation
                self.model_factory.invalidate_cache(tenant_id, entity_type.slug)
                entity_type.is_active = False
                self.db.commit()
                logger.info(f"Soft deleted entity type: {tenant_id}/{entity_type.slug}")
                return True
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to deactivate entity type {entity_type_id}: {e}")
                raise

    def count_entity_types(
        self,
        tenant_id: str,
        include_system: bool = False
    ) -> int:
        """
        Count entity types for a tenant.

        Args:
            tenant_id: Tenant UUID
            include_system: Include system (canonical) entity types

        Returns:
            Count of active entity types
        """
        query = self.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == tenant_id,
            EntityTypeDefinition.is_active == True
        )

        if not include_system:
            query = query.filter(EntityTypeDefinition.is_system == False)

        return query.count()

    def compare_schema_versions(
        self,
        tenant_id: str,
        entity_type_id: str,
        from_version: int,
        to_version: int
    ) -> Tuple[Dict[str, Any], Dict[str, Any], list]:
        """
        Compare two schema versions and generate JSON Patch diff.

        Args:
            tenant_id: Tenant UUID
            entity_type_id: Entity type UUID
            from_version: Source version number
            to_version: Target version number

        Returns:
            Tuple of (from_schema, to_schema, json_patch_operations)

        Raises:
            ValueError: If versions not found
        """
        # Get version snapshots
        from_snapshot = self.db.query(EntityTypeVersionHistory).filter(
            EntityTypeVersionHistory.entity_type_id == entity_type_id,
            EntityTypeVersionHistory.tenant_id == tenant_id,
            EntityTypeVersionHistory.version == from_version
        ).first()

        to_snapshot = self.db.query(EntityTypeVersionHistory).filter(
            EntityTypeVersionHistory.entity_type_id == entity_type_id,
            EntityTypeVersionHistory.tenant_id == tenant_id,
            EntityTypeVersionHistory.version == to_version
        ).first()

        if not from_snapshot or not to_snapshot:
            raise ValueError(
                f"Version not found: from={from_version}, to={to_version}"
            )

        # Generate JSON Patch (RFC 6902)
        # For now, use simple diff. In production, use jsonpatch library
        from_schema = from_snapshot.json_schema
        to_schema = to_snapshot.json_schema

        patch_operations = self._generate_json_patch(from_schema, to_schema)

        return from_schema, to_schema, patch_operations

    def _generate_json_patch(
        self,
        from_schema: Dict[str, Any],
        to_schema: Dict[str, Any]
    ) -> list:
        """
        Generate JSON Patch (RFC 6902) operations between two schemas.

        Simple implementation detecting property additions, removals, and modifications.
        For production, consider using 'jsonpatch' library for comprehensive diff.

        Args:
            from_schema: Source schema
            to_schema: Target schema

        Returns:
            List of JSON Patch operation objects
        """
        operations = []
        from_props = from_schema.get("properties", {})
        to_props = to_schema.get("properties", {})
        from_required = set(from_schema.get("required", []))
        to_required = set(to_schema.get("required", []))

        # Detect property additions
        for prop_name in to_props:
            if prop_name not in from_props:
                operations.append({
                    "op": "add",
                    "path": f"/properties/{prop_name}",
                    "value": to_props[prop_name]
                })
                if prop_name in to_required and prop_name not in from_required:
                    operations.append({
                        "op": "add",
                        "path": f"/required/{prop_name}",
                        "value": True
                    })

        # Detect property removals
        for prop_name in from_props:
            if prop_name not in to_props:
                operations.append({
                    "op": "remove",
                    "path": f"/properties/{prop_name}",
                    "value": from_props[prop_name]
                })

        # Detect property modifications
        for prop_name in from_props:
            if prop_name in to_props:
                from_prop = from_props[prop_name]
                to_prop = to_props[prop_name]
                if from_prop != to_prop:
                    operations.append({
                        "op": "replace",
                        "path": f"/properties/{prop_name}",
                        "value": to_prop,
                        "from": from_prop
                    })

        # Detect required field changes
        added_required = to_required - from_required
        removed_required = from_required - to_required
        for prop in added_required:
            if prop not in added_required or prop in from_props:
                operations.append({
                    "op": "add",
                    "path": "/required/-",
                    "value": prop
                })
        for prop in removed_required:
            operations.append({
                "op": "remove",
                "path": f"/required/{prop}",
                "value": prop
            })

        return operations

    def rollback_to_version(
        self,
        tenant_id: str,
        entity_type_id: str,
        target_version: int,
        changed_by: Optional[str] = None
    ) -> EntityTypeDefinition:
        """
        Rollback entity type schema to a previous version.

        Creates a snapshot of current state before rollback.
        Increments version number after rollback.

        Args:
            tenant_id: Tenant UUID
            entity_type_id: Entity type UUID
            target_version: Version number to rollback to
            changed_by: Optional user identifier

        Returns:
            Updated entity type with restored schema

        Raises:
            ValueError: If entity type not found or target version invalid
        """
        # Get current entity type
        entity_type = self.get_entity_type(
            tenant_id=tenant_id,
            entity_type_id=entity_type_id
        )
        if not entity_type:
            raise ValueError(f"Entity type '{entity_type_id}' not found")

        # Prevent modification of system types
        if entity_type.is_system:
            raise ValueError(
                f"Cannot rollback system entity type '{entity_type.slug}'. "
                "System types are read-only."
            )

        # Verify target version exists
        target_snapshot = self.db.query(EntityTypeVersionHistory).filter(
            EntityTypeVersionHistory.entity_type_id == entity_type_id,
            EntityTypeVersionHistory.tenant_id == tenant_id,
            EntityTypeVersionHistory.version == target_version
        ).first()

        if not target_snapshot:
            available_versions = [
                version.version
                for version in self.db.query(EntityTypeVersionHistory).filter(
                    EntityTypeVersionHistory.entity_type_id == entity_type_id
                ).all()
            ]
            raise ValueError(
                f"Version {target_version} not found in history. "
                f"Available versions: {[v.version for v in self.db.query(EntityTypeVersionHistory).filter(EntityTypeVersionHistory.entity_type_id == entity_type_id).all()]}"
            )

        # Verify target version is not current version
        if target_version >= entity_type.version:
            raise ValueError(
                f"Cannot rollback to version {target_version} or higher. "
                f"Current version is {entity_type.version}."
            )

        # Create snapshot of current state BEFORE rollback
        self._create_version_snapshot(
            entity_type=entity_type,
            changed_by=changed_by,
            change_summary=f"Pre-rollback snapshot before restoring v{target_version}"
        )

        # Invalidate cache for current schema
        invalidated = self.model_factory.invalidate_cache(tenant_id, entity_type.slug)
        logger.info(f"Invalidated {invalidated} cached models before rollback")

        # Restore schema from target version
        entity_type.json_schema = target_snapshot.json_schema.copy()
        entity_type.display_name = target_snapshot.display_name
        entity_type.description = target_snapshot.description
        entity_type.available_skills = target_snapshot.available_skills.copy() if target_snapshot.available_skills else []

        # Increment version (rollback is a new version)
        entity_type.version += 1

        try:
            self.db.commit()
            self.db.refresh(entity_type)
            logger.info(
                f"Rolled back {tenant_id}/{entity_type.slug}: "
                f"v{entity_type.version - 1} → v{target_version} → v{entity_type.version}"
            )
            return entity_type
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to rollback entity type {entity_type_id}: {e}")
            raise

    def detect_breaking_changes(
        self,
        tenant_id: str,
        entity_type_id: str,
        new_json_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect breaking changes between current and new schema.

        Args:
            tenant_id: Tenant UUID
            entity_type_id: Entity type UUID
            new_json_schema: Proposed new schema

        Returns:
            Dictionary with breaking change report

        Raises:
            ValueError: If entity type not found
        """
        entity_type = self.get_entity_type(
            tenant_id=tenant_id,
            entity_type_id=entity_type_id
        )
        if not entity_type:
            raise ValueError(f"Entity type '{entity_type_id}' not found")

        current_schema = entity_type.json_schema
        changes = []
        critical_count = 0
        warning_count = 0
        info_count = 0

        current_props = current_schema.get("properties", {})
        new_props = new_json_schema.get("properties", {})
        current_required = set(current_schema.get("required", []))
        new_required = set(new_json_schema.get("required", []))

        # Detect property removals
        for prop_name in current_props:
            if prop_name not in new_props:
                was_required = prop_name in current_required
                severity = "critical" if was_required else "info"
                changes.append({
                    "type": "property_removed",
                    "severity": severity,
                    "property": prop_name,
                    "message": (
                        f"Removed required property '{prop_name}' - data loss risk"
                        if was_required else
                        f"Removed optional property '{prop_name}'"
                    ),
                    "details": {"from": current_props[prop_name]}
                })
                if severity == "critical":
                    critical_count += 1
                else:
                    info_count += 1

        # Detect type changes
        for prop_name in current_props:
            if prop_name in new_props:
                current_type = self._normalize_type(current_props[prop_name])
                new_type = self._normalize_type(new_props[prop_name])
                if current_type != new_type:
                    changes.append({
                        "type": "property_type_changed",
                        "severity": "warning",
                        "property": prop_name,
                        "message": f"Type changed for '{prop_name}': {current_type} → {new_type}",
                        "details": {"from": current_type, "to": new_type}
                    })
                    warning_count += 1

        # Detect required field additions
        for prop in new_required:
            if prop not in current_required:
                changes.append({
                    "type": "required_added",
                    "severity": "warning",
                    "property": prop,
                    "message": f"Added required field '{prop}' - existing data may fail validation",
                    "details": {"to": new_props.get(prop, {})}
                })
                warning_count += 1

        return {
            "has_breaking_changes": critical_count > 0 or warning_count > 0,
            "changes": changes,
            "summary": {
                "critical": critical_count,
                "warning": warning_count,
                "info": info_count
            }
        }

    def _normalize_type(self, prop_schema: Dict[str, Any]) -> str:
        """Normalize property type for comparison."""
        if "type" in prop_schema:
            prop_type = prop_schema["type"]
            if isinstance(prop_type, list):
                return " | ".join(prop_type)
            return prop_type
        if "$ref" in prop_schema:
            return prop_schema["$ref"]
        if "enum" in prop_schema:
            return f"enum: [{', '.join(str(e) for e in prop_schema['enum'])}]"
        return "unknown"

    def generate_migration_suggestions(
        self,
        tenant_id: str,
        entity_type_id: str,
        new_json_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate migration suggestions for schema changes.

        Analyzes differences between current and new schema to suggest
        data migration strategies.

        Args:
            tenant_id: Tenant UUID
            entity_type_id: Entity type UUID
            new_json_schema: Proposed new schema

        Returns:
            Dictionary with migration suggestions and scripts

        Raises:
            ValueError: If entity type not found
        """
        entity_type = self.get_entity_type(
            tenant_id=tenant_id,
            entity_type_id=entity_type_id
        )
        if not entity_type:
            raise ValueError(f"Entity type '{entity_type_id}' not found")

        current_schema = entity_type.json_schema
        suggestions = []

        # Get JSON Patch operations by comparing current vs new
        patch_operations = self._generate_json_patch(current_schema, new_json_schema)

        current_props = current_schema.get("properties", {})
        new_props = new_json_schema.get("properties", {})

        # Generate suggestions for each operation
        for op in patch_operations:
            path = op.get("path", "")
            if "/properties/" not in path:
                continue

            prop_name = path.split("/")[-1]

            if op.get("op") == "remove":
                # Suggest backup for removed fields
                was_required = prop_name in current_schema.get("required", [])
                suggestions.append({
                    "type": "field_removal",
                    "property": prop_name,
                    "description": f"Field '{prop_name}' will be removed",
                    "priority": "high" if was_required else "low",
                    "script": {
                        "javascript": (
                            f"// Backup removed field '{prop_name}'\\n"
                            f"const backup = items.map(item => ({{\\n"
                            f"  id: item.id,\\n"
                            f"  {prop_name}: item.{prop_name}\\n"
                            f"}}));"
                        ),
                        "sql": (
                            f"-- Backup removed field\\n"
                            f"CREATE TABLE backup_{prop_name} AS\\n"
                            f"SELECT id, {prop_name} FROM your_table;"
                        )
                    }
                })

            elif op.get("op") == "replace":
                # Type conversion suggestions
                from_prop = op.get("from", {})
                to_prop = op.get("value", {})
                if from_prop.get("type") != to_prop.get("type"):
                    suggestions.append({
                        "type": "type_change",
                        "property": prop_name,
                        "from_type": from_prop.get("type"),
                        "to_type": to_prop.get("type"),
                        "description": (
                            f"Convert '{prop_name}' from "
                            f"{from_prop.get('type')} to {to_prop.get('type')}"
                        ),
                        "priority": "medium",
                        "script": self._generate_type_conversion_script(
                            prop_name,
                            from_prop.get("type"),
                            to_prop.get("type")
                        )
                    })

        return {
            "entity_type_slug": entity_type.slug,
            "current_version": entity_type.version,
            "suggestions": suggestions,
            "summary": {
                "high": len([s for s in suggestions if s.get("priority") == "high"]),
                "medium": len([s for s in suggestions if s.get("priority") == "medium"]),
                "low": len([s for s in suggestions if s.get("priority") == "low"])
            }
        }

    def _generate_type_conversion_script(
        self,
        field: str,
        from_type: str,
        to_type: str
    ) -> Dict[str, str]:
        """Generate conversion script for type changes."""
        # Simplified converter generation
        converters = {
            ("string", "number"): "Number(value) || 0",
            ("string", "integer"): "Math.floor(Number(value)) || 0",
            ("number", "string"): "String(value)",
            ("boolean", "string"): "value ? 'true' : 'false'",
        }

        converter = converters.get((from_type, to_type), "String(value)")

        return {
            "javascript": (
                f"// Convert {field} from {from_type} to {to_type}\\n"
                f"items.forEach(item => {{\\n"
                f"  if (item.{field} !== undefined) {{\\n"
                f"    item.{field} = {converter};\\n"
                f"  }}\\n"
                f"}});"
            ),
            "sql": (
                f"-- SQL type conversion for {field}\\n"
                f"UPDATE your_table\\n"
                f"SET {field} = CAST({field} AS {to_type.upper()});"
            )
        }

    def _is_valid_slug(self, slug: str) -> bool:
        """
        Validate slug format (alphanumeric, hyphens, underscores only).

        Args:
            slug: Slug to validate

        Returns:
            True if valid, False otherwise
        """
        import re
        pattern = r'^[a-zA-Z0-9_-]+$'
        return bool(re.match(pattern, slug)) and len(slug) <= 100

    def close(self):
        """Close database session if created by this service."""
        # Only close if we created the session
        if self.db is not None:
            self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global service instances per tenant (for dependency injection)
_services: Dict[str, EntityTypeService] = {}


def get_entity_type_service(
    tenant_id: Optional[str] = None,
    db: Optional[Session] = None
) -> EntityTypeService:
    """
    Get entity type service instance.

    Args:
        tenant_id: Optional tenant ID for service scoping
        db: Optional database session

    Returns:
        EntityTypeService instance
    """
    # If DB session provided, create new service instance
    if db:
        return EntityTypeService(db=db)

    # Return global singleton otherwise
    global _services
    if "default" not in _services:
        _services["default"] = EntityTypeService()
        logger.info("Initialized default entity type service")
    return _services["default"]
