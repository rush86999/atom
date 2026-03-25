"""
Entity Skill Service

Manages skill bindings to entity types.
Provides CRUD operations for attaching/detaching skills to entity types.
"""
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import EntityTypeDefinition, Skill, SkillInstallation
from core.database import get_db_session

logger = logging.getLogger(__name__)


class EntitySkillService:
    """Service for managing skill bindings to entity types.

    Features:
    - Attach/detach skills to entity types
    - List attached skills for an entity type
    - Permission checks before skill execution
    - Tenant isolation enforcement
    """

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize entity skill service.

        Args:
            db: Database session (creates SessionLocal if not provided)
        """
        self.db = db # Note: In upstream we handle session management via context manager or provided db

    def attach_skill(
        self,
        tenant_id: str,
        entity_type_id: str,
        skill_id: str
    ) -> EntityTypeDefinition:
        """
        Attach a skill to an entity type.
        """
        with get_db_session() as session:
            # Load entity type with tenant ownership check
            entity_type = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.id == entity_type_id,
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            ).first()

            if not entity_type:
                raise ValueError(
                    f"Entity type '{entity_type_id}' not found for tenant '{tenant_id}'"
                )

            # Check if skill exists and tenant has access
            skill_accessible = session.query(Skill).filter(
                Skill.id == skill_id
            ).first()

            if not skill_accessible:
                # Check if skill installation exists
                skill_installation = session.query(SkillInstallation).filter(
                    SkillInstallation.tenant_id == tenant_id,
                    SkillInstallation.skill_id == skill_id,
                    SkillInstallation.is_active == True
                ).first()

                if not skill_installation:
                    raise ValueError(
                        f"Skill '{skill_id}' not found or not accessible by tenant '{tenant_id}'"
                    )

            # Check for duplicate
            current_skills = entity_type.available_skills or []
            if skill_id in current_skills:
                return entity_type

            # Append skill
            entity_type.available_skills = current_skills + [skill_id]

            try:
                session.commit()
                session.refresh(entity_type)
                logger.info(f"Attached skill '{skill_id}' to entity type '{entity_type.slug}'")
                return entity_type
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to attach skill: {e}")
                raise

    def detach_skill(
        self,
        tenant_id: str,
        entity_type_id: str,
        skill_id: str
    ) -> EntityTypeDefinition:
        """Detach a skill from an entity type."""
        with get_db_session() as session:
            entity_type = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.id == entity_type_id,
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            ).first()

            if not entity_type:
                raise ValueError(f"Entity type '{entity_type_id}' not found")

            current_skills = entity_type.available_skills or []
            if skill_id not in current_skills:
                return entity_type

            entity_type.available_skills = [s for s in current_skills if s != skill_id]

            try:
                session.commit()
                session.refresh(entity_type)
                return entity_type
            except Exception as e:
                session.rollback()
                raise

    def get_entity_skills(
        self,
        tenant_id: str,
        entity_type_id: str
    ) -> List[Dict[str, any]]:
        """List all skills attached to an entity type."""
        with get_db_session() as session:
            entity_type = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.id == entity_type_id,
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            ).first()

            if not entity_type:
                raise ValueError(f"Entity type '{entity_type_id}' not found")

            skill_ids = entity_type.available_skills or []
            if not skill_ids:
                return []

            skills = session.query(Skill).filter(Skill.id.in_(skill_ids)).all()
            return [{"id": s.id, "name": s.name, "description": s.description, "type": s.type} for s in skills]

    def check_skill_permission(
        self,
        tenant_id: str,
        entity_type_slug: str,
        skill_id: str
    ) -> Dict[str, any]:
        """Check if a skill is allowed to operate on an entity type."""
        with get_db_session() as session:
            entity_type = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.slug == entity_type_slug,
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            ).first()

            if not entity_type:
                return {"allowed": False, "reason": "Entity type not found"}

            available_skills = entity_type.available_skills or []
            if skill_id in available_skills:
                return {"allowed": True, "reason": "Skill allowed"}
            return {"allowed": False, "reason": "Skill not attached"}


# Global service instance
_default_service: Optional[EntitySkillService] = None

def get_entity_skill_service(db: Optional[Session] = None) -> EntitySkillService:
    if db: return EntitySkillService(db=db)
    global _default_service
    if _default_service is None:
        _default_service = EntitySkillService()
    return _default_service
