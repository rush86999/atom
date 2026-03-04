"""
Canvas-Skill Integration Service

Manages the pairing between canvas components and agent skills.
Enables agents to create complete capability packages:
- Canvas Component = UI Layer (presentation, forms, charts)
- Agent Skill = Execution Layer (API calls, data processing, business logic)

Key Features:
- Component-skill pairing during creation
- Auto-skill installation on component install
- User permission for marketplace listing
- Skill versioning and dependency management
- Usage tracking for both components and skills
"""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, update
from datetime import datetime

from core.models import (
    CanvasComponent,
    ComponentInstallation,
    Skill,
    SkillVersion,
    User,
    Tenant
)
from core.skill_builder_service import SkillBuilderService
from core.skill_versioning_service import SkillVersioningService

logger = logging.getLogger(__name__)


class CanvasSkillIntegrationService:
    """
    Service for managing canvas-skill pairings.

    Workflow:
    1. Agent creates skill (Python code for API integration)
    2. Agent creates canvas component (React component that uses skill)
    3. Component references skill_id
    4. User installs component → skill auto-created in tenant's registry
    5. Component uses tenant's API keys for skill execution
    """

    def __init__(self, db: Session):
        self.db = db
        self.skill_builder = SkillBuilderService()
        self.skill_versioning = SkillVersioningService(db)

    async def create_component_with_skill(
        self,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        component_data: Dict[str, Any],
        skill_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Agent creates component + skill together.
        """
        try:
            # 1. Create skill first
            logger.info(f"Creating skill {skill_data.get('name')} for component")

            skill = Skill(
                tenant_id=tenant_id,
                author_tenant_id=tenant_id,
                name=skill_data["name"],
                description=skill_data.get("description"),
                long_description=skill_data.get("long_description"),
                version=skill_data.get("version", "1.0.0"),
                type=skill_data["type"],
                input_schema=skill_data.get("input_schema", {}),
                output_schema=skill_data.get("output_schema"),
                config=skill_data.get("config", {}),
                category=skill_data.get("category"),
                tags=skill_data.get("tags"),
                code=skill_data.get("code"),
                is_public=False,  # Start private
                is_approved=False
            )

            self.db.add(skill)
            self.db.flush()  # Get skill.id

            # 2. Create initial version
            version = SkillVersion(
                skill_id=skill.id,
                tenant_id=tenant_id,
                version=skill.version,
                changelog="Initial version",
                name=skill.name,
                description=skill.description,
                type=skill.type,
                input_schema=skill.input_schema,
                output_schema=skill.output_schema,
                config=skill.config,
                code=skill.code
            )

            self.db.add(version)

            # 3. Create component with skill reference
            logger.info(f"Creating component {component_data['name']} with skill {skill.id}")

            component = CanvasComponent(
                tenant_id=tenant_id,
                author_id=user_id,
                name=component_data["name"],
                description=component_data.get("description"),
                category=component_data["category"],
                component_type=component_data["component_type"],
                code=component_data["code"],
                config_schema=component_data.get("config_schema"),
                tags=component_data.get("tags"),
                dependencies=component_data.get("dependencies"),
                version=component_data.get("version", "1.0.0"),
                is_public=False,  # Start private
                is_approved=False,
                required_skill_id=skill.id,
                skill_version=skill.version,
                auto_install_skill=component_data.get("auto_install_skill", True)
            )

            self.db.add(component)
            self.db.commit()
            self.db.refresh(component)
            self.db.refresh(skill)

            return {
                "component_id": component.id,
                "skill_id": skill.id,
                "component_name": component.name,
                "skill_name": skill.name,
                "status": "created"
            }

        except Exception as e:
            logger.error(f"Error creating component with skill: {e}")
            self.db.rollback()
            raise

    async def install_component_to_tenant(
        self,
        tenant_id: str,
        user_id: str,
        component_id: str,
        canvas_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        End user installs component + auto-creates skill.
        """
        try:
            # 1. Get component
            source_component = self.db.query(CanvasComponent).filter(
                and_(
                    CanvasComponent.id == component_id,
                    or_(
                        and_(
                            CanvasComponent.is_public == True,
                            CanvasComponent.is_approved == True
                        ),
                        CanvasComponent.tenant_id == tenant_id
                    )
                )
            ).first()

            if not source_component:
                raise ValueError(f"Component {component_id} not found or not available")

            # 2. Check if component has required skill
            required_skill_id = source_component.required_skill_id
            installed_skill_id = None

            # 3. Check auto_install_skill flag
            if required_skill_id and source_component.auto_install_skill:
                # 4. Get the skill
                source_skill = self.db.query(Skill).filter(
                    Skill.id == required_skill_id
                ).first()

                if not source_skill:
                    raise ValueError(f"Component requires skill {required_skill_id} but skill not found.")

                # 5. Check if skill already installed
                existing_skill = self.db.query(Skill).filter(
                    and_(
                        Skill.tenant_id == tenant_id,
                        Skill.name == source_skill.name
                    )
                ).first()

                if existing_skill:
                    installed_skill_id = existing_skill.id
                else:
                    # Install skill
                    installed_skill = Skill(
                        tenant_id=tenant_id,
                        author_tenant_id=source_skill.author_tenant_id,
                        name=source_skill.name,
                        description=source_skill.description,
                        long_description=source_skill.long_description,
                        version=source_skill.version,
                        type=source_skill.type,
                        input_schema=source_skill.input_schema,
                        output_schema=source_skill.output_schema,
                        config=source_skill.config,
                        category=source_skill.category,
                        tags=source_skill.tags,
                        code=source_skill.code,
                        is_public=False,
                        is_approved=False
                    )

                    self.db.add(installed_skill)
                    self.db.flush()

                    # Create version
                    skill_version = SkillVersion(
                        skill_id=installed_skill.id,
                        tenant_id=tenant_id,
                        version=installed_skill.version,
                        changelog=f"Installed from component {source_component.name}",
                        name=installed_skill.name,
                        description=installed_skill.description,
                        type=installed_skill.type,
                        input_schema=installed_skill.input_schema,
                        output_schema=installed_skill.output_schema,
                        config=installed_skill.config,
                        code=installed_skill.code
                    )

                    self.db.add(skill_version)
                    installed_skill_id = installed_skill.id

            # 6. Create component copy for tenant
            new_component = CanvasComponent(
                tenant_id=tenant_id,
                author_id=source_component.author_id,
                name=source_component.name,
                description=source_component.description,
                category=source_component.category,
                component_type=source_component.component_type,
                code=source_component.code,
                config_schema=source_component.config_schema,
                tags=source_component.tags,
                dependencies=source_component.dependencies,
                version=source_component.version,
                is_public=False,
                is_approved=False,
                required_skill_id=installed_skill_id,
                skill_version=source_component.skill_version,
                auto_install_skill=source_component.auto_install_skill
            )

            self.db.add(new_component)
            self.db.flush()

            # 7. Install on canvas if provided
            if canvas_id:
                installation = ComponentInstallation(
                    tenant_id=tenant_id,
                    canvas_id=canvas_id,
                    component_id=new_component.id,
                    config=config or {}
                )
                self.db.add(installation)

            self.db.commit()
            self.db.refresh(new_component)

            return {
                "component_id": new_component.id,
                "skill_id": installed_skill_id,
                "component_name": new_component.name,
                "status": "installed"
            }

        except Exception as e:
            logger.error(f"Error installing component: {e}")
            self.db.rollback()
            raise
