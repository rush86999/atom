#!/usr/bin/env python3
"""
Workflow Template Manager
Manages workflow templates for reusability
"""

from datetime import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


class WorkflowTemplate(BaseModel):
    """Workflow template model"""
    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    category: str = Field(default="general", description="Template category")
    input_schema: List[Dict[str, Any]] = Field(default_factory=list, description="Input parameter definitions")
    steps: List[Dict[str, Any]] = Field(..., description="Workflow steps")
    output_config: Optional[Dict[str, Any]] = Field(default=None, description="Output configuration")
    tags: List[str] = Field(default_factory=list, description="Template tags")
    version: str = Field(default="1.0.0", description="Template version")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: Optional[str] = Field(default=None, description="Creator user ID")
    is_active: bool = Field(default=True, description="Whether template is active")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "email_campaign_workflow",
                "name": "Email Campaign Workflow",
                "description": "Automated email campaign setup and execution",
                "category": "marketing",
                "input_schema": [
                    {
                        "name": "recipient_list",
                        "type": "array",
                        "required": True,
                        "description": "List of email recipients"
                    }
                ],
                "steps": [
                    {
                        "step_id": "validate_recipients",
                        "name": "Validate Recipients",
                        "action": "validate_emails"
                    }
                ],
                "tags": ["marketing", "email", "automation"],
                "version": "1.0.0"
            }
        }
    )

    @field_validator('template_id')
    @classmethod
    def validate_template_id(cls, v):
        if not v or not v.strip():
            raise ValueError("template_id cannot be empty")
        return v


class WorkflowTemplateManager:
    """
    Manages workflow templates with file-based storage
    Templates are stored as JSON files for easy version control and inspection
    """

    def __init__(self, templates_dir: str = None):
        """
        Initialize template manager

        Args:
            templates_dir: Directory to store templates (default: backend/workflow_templates)
        """
        if templates_dir is None:
            # Default to workflow_templates directory in backend
            backend_dir = Path(__file__).parent.parent
            templates_dir = backend_dir / "workflow_templates"

        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Index file for quick lookups
        self.index_file = self.templates_dir / "template_index.json"

        logger.info(f"WorkflowTemplateManager initialized with directory: {self.templates_dir}")

    def _get_template_path(self, template_id: str) -> Path:
        """Get file path for a template"""
        return self.templates_dir / f"{template_id}.json"

    def _load_index(self) -> Dict[str, Any]:
        """Load template index"""
        if not self.index_file.exists():
            return {"templates": {}, "last_updated": None}

        try:
            with open(self.index_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load template index: {e}")
            return {"templates": {}, "last_updated": None}

    def _save_index(self, index: Dict[str, Any]):
        """Save template index"""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save template index: {e}")

    def _update_index(self, template: WorkflowTemplate):
        """Update index with template metadata"""
        index = self._load_index()

        index["templates"][template.template_id] = {
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "tags": template.tags,
            "version": template.version,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
            "is_active": template.is_active,
            "file_path": str(self._get_template_path(template.template_id))
        }
        index["last_updated"] = datetime.utcnow().isoformat()

        self._save_index(index)

    def create_template(self, template_data: Dict[str, Any]) -> WorkflowTemplate:
        """
        Create a new workflow template

        Args:
            template_data: Template definition

        Returns:
            Created WorkflowTemplate

        Raises:
            ValueError: If template validation fails
            IOError: If template file cannot be written
        """
        # Generate template_id if not provided
        if "template_id" not in template_data or not template_data["template_id"]:
            template_data["template_id"] = f"template_{uuid.uuid4().hex[:8]}"

        # Validate and create template
        try:
            template = WorkflowTemplate(**template_data)
        except Exception as e:
            raise ValueError(f"Invalid template data: {e}")

        # Check if template already exists
        template_path = self._get_template_path(template.template_id)
        if template_path.exists():
            raise ValueError(f"Template with ID '{template.template_id}' already exists")

        # Save template to file
        try:
            with open(template_path, 'w') as f:
                json.dump(template.dict(), f, indent=2)

            # Update index
            self._update_index(template)

            logger.info(f"Created workflow template: {template.template_id}")
            return template

        except Exception as e:
            logger.error(f"Failed to save template {template.template_id}: {e}")
            raise IOError(f"Failed to save template: {e}")

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """
        Get a workflow template by ID

        Args:
            template_id: Template identifier

        Returns:
            WorkflowTemplate or None if not found
        """
        template_path = self._get_template_path(template_id)

        if not template_path.exists():
            return None

        try:
            with open(template_path, 'r') as f:
                data = json.load(f)

            return WorkflowTemplate(**data)

        except Exception as e:
            logger.error(f"Failed to load template {template_id}: {e}")
            return None

    def list_templates(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True
    ) -> List[WorkflowTemplate]:
        """
        List all workflow templates with optional filtering

        Args:
            category: Filter by category
            tags: Filter by tags (any match)
            active_only: Only return active templates

        Returns:
            List of WorkflowTemplates
        """
        index = self._load_index()
        templates = []

        for template_id, metadata in index.get("templates", {}).items():
            # Filter by active status
            if active_only and not metadata.get("is_active", True):
                continue

            # Filter by category
            if category and metadata.get("category") != category:
                continue

            # Filter by tags
            if tags:
                template_tags = metadata.get("tags", [])
                if not any(tag in template_tags for tag in tags):
                    continue

            # Load full template
            template = self.get_template(template_id)
            if template:
                templates.append(template)

        return templates

    def update_template(self, template_id: str, updates: Dict[str, Any]) -> Optional[WorkflowTemplate]:
        """
        Update an existing workflow template

        Args:
            template_id: Template identifier
            updates: Fields to update

        Returns:
            Updated WorkflowTemplate or None if not found
        """
        template = self.get_template(template_id)
        if not template:
            return None

        # Update fields
        template_data = template.dict()
        template_data.update(updates)

        # Update timestamp
        template_data["updated_at"] = datetime.utcnow().isoformat()

        # Validate updated template
        try:
            updated_template = WorkflowTemplate(**template_data)
        except Exception as e:
            raise ValueError(f"Invalid updated template data: {e}")

        # Save updated template
        template_path = self._get_template_path(template_id)
        try:
            with open(template_path, 'w') as f:
                json.dump(updated_template.dict(), f, indent=2)

            # Update index
            self._update_index(updated_template)

            logger.info(f"Updated workflow template: {template_id}")
            return updated_template

        except Exception as e:
            logger.error(f"Failed to update template {template_id}: {e}")
            raise IOError(f"Failed to update template: {e}")

    def delete_template(self, template_id: str) -> bool:
        """
        Delete a workflow template

        Args:
            template_id: Template identifier

        Returns:
            True if deleted, False if not found
        """
        template_path = self._get_template_path(template_id)

        if not template_path.exists():
            return False

        try:
            # Remove template file
            template_path.unlink()

            # Update index
            index = self._load_index()
            if template_id in index.get("templates", {}):
                del index["templates"][template_id]
                self._save_index(index)

            logger.info(f"Deleted workflow template: {template_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete template {template_id}: {e}")
            return False

    def create_workflow_from_template(
        self,
        template_id: str,
        workflow_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a workflow from a template

        Args:
            template_id: Template identifier
            workflow_data: Workflow-specific data (name, description, etc.)

        Returns:
            Workflow definition ready for creation

        Raises:
            ValueError: If template not found or invalid
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template '{template_id}' not found")

        if not template.is_active:
            raise ValueError(f"Template '{template_id}' is not active")

        # Merge template with workflow-specific data
        workflow_definition = {
            "workflow_id": f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
            "name": workflow_data.get("name", template.name),
            "description": workflow_data.get("description", template.description),
            "category": template.category,
            "tags": template.tags + workflow_data.get("additional_tags", []),
            "input_schema": template.input_schema,
            "steps": template.steps,
            "output_config": template.output_config,
            "template_id": template_id,
            "template_version": template.version,
            "created_by": workflow_data.get("created_by")
        }

        logger.info(f"Created workflow from template: {template_id}")
        return workflow_definition


# Global instance
workflow_template_manager = WorkflowTemplateManager()


def get_workflow_template_manager() -> WorkflowTemplateManager:
    """Get global workflow template manager instance"""
    return workflow_template_manager
