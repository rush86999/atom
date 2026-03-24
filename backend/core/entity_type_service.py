"""
Entity Type Service

CRUD operations for dynamic entity type definitions.
Integrates schema validation and model cache management.
"""
import logging
import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.models import EntityTypeDefinition
from core.schema_validator import SchemaValidator, get_schema_validator
from core.model_factory import ModelFactory, get_model_factory
from core.database import get_db_session

logger = logging.getLogger(__name__)


class EntityTypeService:
    """CRUD operations for entity type definitions.
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        schema_validator: Optional[SchemaValidator] = None,
        model_factory: Optional[ModelFactory] = None
    ):
        self.db = db
        self.validator = schema_validator or get_schema_validator()
        self.model_factory = model_factory or get_model_factory()

    def create_entity_type(
        self,
        tenant_id: str,
        slug: str,
        display_name: str,
        json_schema: Dict[str, Any],
        description: Optional[str] = None,
        available_skills: Optional[List[str]] = None,
        is_system: bool = False
    ) -> EntityTypeDefinition:
        """Create new entity type with schema validation."""
        # Simple validation
        if not slug or not display_name:
            raise ValueError("Slug and Display Name are required")

        # Validate JSON Schema
        is_valid, error = self.validator.validate_schema(json_schema)
        if not is_valid:
            raise ValueError(f"Invalid JSON Schema: {error}")

        with get_db_session() as session:
            # Check for duplicate
            existing = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.slug == slug,
                EntityTypeDefinition.is_active == True
            ).first()

            if existing:
                raise ValueError(f"Entity type '{slug}' already exists for tenant.")

            # Create
            entity_type = EntityTypeDefinition(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                slug=slug,
                display_name=display_name,
                description=description,
                json_schema=json_schema,
                available_skills=available_skills or [],
                is_system=is_system,
                is_active=True,
                version=1
            )

            try:
                session.add(entity_type)
                session.commit()
                session.refresh(entity_type)
                logger.info(f"Created entity type: {tenant_id}/{slug}")
                return entity_type
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to create entity type {slug}: {e}")
                raise

    def get_entity_type(
        self,
        tenant_id: str,
        entity_type_id: Optional[str] = None,
        slug: Optional[str] = None
    ) -> Optional[EntityTypeDefinition]:
        """Get entity type by ID or slug."""
        with get_db_session() as session:
            query = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            )

            if entity_type_id:
                query = query.filter(EntityTypeDefinition.id == entity_type_id)
            else:
                query = query.filter(EntityTypeDefinition.slug == slug)

            return query.first()

    def list_entity_types(
        self,
        tenant_id: str,
        include_system: bool = False,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[EntityTypeDefinition]:
        """List entity types for a tenant."""
        with get_db_session() as session:
            query = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            )

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

            return query.order_by(EntityTypeDefinition.created_at.desc()).limit(limit).offset(offset).all()

    def update_entity_type(
        self,
        tenant_id: str,
        entity_type_id: str,
        display_name: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        available_skills: Optional[List[str]] = None
    ) -> EntityTypeDefinition:
        """Update entity type."""
        with get_db_session() as session:
            entity_type = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.id == entity_type_id,
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            ).first()

            if not entity_type:
                raise ValueError(f"Entity type '{entity_type_id}' not found")

            if entity_type.is_system:
                raise ValueError(f"Cannot modify system entity type '{entity_type.slug}'")

            if json_schema:
                is_valid, error = self.validator.validate_schema(json_schema)
                if not is_valid: raise ValueError(f"Invalid JSON Schema: {error}")
                
                # Invalidate cache
                self.model_factory.invalidate_cache(tenant_id, entity_type.slug)
                entity_type.json_schema = json_schema
                entity_type.version += 1

            if display_name is not None: entity_type.display_name = display_name
            if description is not None: entity_type.description = description
            if available_skills is not None: entity_type.available_skills = available_skills

            try:
                session.commit()
                session.refresh(entity_type)
                return entity_type
            except Exception as e:
                session.rollback()
                raise

    def count_entity_types(self, tenant_id: str, include_system: bool = False) -> int:
        """Count entity types for a tenant."""
        with get_db_session() as session:
            query = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            )
            if not include_system: query = query.filter(EntityTypeDefinition.is_system == False)
            return query.count()


# Global service instance
_default_service: Optional[EntityTypeService] = None

def get_entity_type_service(db: Optional[Session] = None) -> EntityTypeService:
    if db: return EntityTypeService(db=db)
    global _default_service
    if _default_service is None:
        _default_service = EntityTypeService()
    return _default_service
