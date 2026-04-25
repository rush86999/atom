"""
Tests for WorkflowTemplateSystem - Workflow template management and marketplace.

Coverage Goals (25-30% on 1,363 lines):
- Template models (WorkflowTemplate, TemplateStep, TemplateParameter)
- Template CRUD (create, read, update, delete)
- Template validation (schema, required parameters, step validation)
- Template instantiation (create workflow from template)
- Error handling (invalid template, validation errors, duplicates)

Reference: Phase 304 Plan 03 - workflow_template_system.py Coverage
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import ValidationError

from core.workflow_template_system import (
    WorkflowTemplate,
    WorkflowTemplateManager,
    TemplateCategory,
    TemplateComplexity,
    TemplateParameter,
    TemplateStep,
    TemplateMarketplace,
)


class TestTemplateModels:
    """Test WorkflowTemplate Pydantic models."""

    def test_template_category_enum(self):
        """Test TemplateCategory enum values."""
        assert TemplateCategory.DATA_PROCESSING == "data_processing"
        assert TemplateCategory.AUTOMATION == "automation"
        assert TemplateCategory.INTEGRATION == "integration"
        assert TemplateCategory.ANALYTICS == "analytics"

    def test_template_complexity_enum(self):
        """Test TemplateComplexity enum values."""
        assert TemplateComplexity.BASIC == "basic"
        assert TemplateComplexity.INTERMEDIATE == "intermediate"
        assert TemplateComplexity.ADVANCED == "advanced"

    def test_template_parameter_required(self):
        """Test required parameter validation."""
        param = TemplateParameter(
            name="api_key",
            type="string",
            required=True,
            description="API key for external service"
        )

        assert param.required is True
        assert param.default_value is None
        assert param.name == "api_key"

    def test_template_parameter_optional_with_default(self):
        """Test optional parameter with default value."""
        param = TemplateParameter(
            name="batch_size",
            type="integer",
            required=False,
            default_value=100,
            description="Batch size for processing"
        )

        assert param.required is False
        assert param.default_value == 100

    def test_template_step_creation(self):
        """Test creating a TemplateStep."""
        step = TemplateStep(
            step_id="step-001",
            name="Transform Data",
            action="transform",
            parameters={"method": "normalize"},
            dependencies=["step-001"]
        )

        assert step.step_id == "step-001"
        assert step.action == "transform"
        assert step.dependencies == ["step-001"]

    def test_workflow_template_creation(self):
        """Test creating a valid WorkflowTemplate."""
        template = WorkflowTemplate(
            template_id="tpl-001",
            name="Data Processing Pipeline",
            description="Process data from S3 to database",
            category=TemplateCategory.DATA_PROCESSING,
            complexity=TemplateComplexity.INTERMEDIATE,
            version="1.0.0",
            author="System",
            steps=[
                TemplateStep(
                    step_id="step-001",
                    name="Extract Data",
                    action="extract",
                    parameters={"source": "s3://bucket/data"}
                )
            ],
            parameters=[
                TemplateParameter(
                    name="source",
                    type="string",
                    required=True,
                    description="Data source location"
                )
            ]
        )

        assert template.template_id == "tpl-001"
        assert template.name == "Data Processing Pipeline"
        assert template.category == TemplateCategory.DATA_PROCESSING
        assert len(template.steps) == 1
        assert len(template.parameters) == 1

    def test_workflow_template_validation_error(self):
        """Test WorkflowTemplate validation with missing required fields."""
        with pytest.raises(ValidationError):
            WorkflowTemplate(
                # Missing template_id, name, category
                description="Invalid template"
            )

    def test_template_calculate_estimated_duration(self):
        """Test calculating estimated template duration."""
        template = WorkflowTemplate(
            template_id="tpl-001",
            name="Test Template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[
                TemplateStep(
                    step_id="step-001",
                    name="Step 1",
                    action="test_action",
                    parameters={},
                    estimated_duration_seconds=60
                ),
                TemplateStep(
                    step_id="step-002",
                    name="Step 2",
                    action="test_action",
                    parameters={},
                    estimated_duration_seconds=120
                )
            ],
            parameters=[]
        )

        duration = template.calculate_estimated_duration()
        assert duration == 180

    def test_template_add_usage(self):
        """Test tracking template usage."""
        template = WorkflowTemplate(
            template_id="tpl-001",
            name="Test Template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[],
            parameters=[],
            usage_count=10
        )

        template.add_usage()
        assert template.usage_count == 11

    def test_template_update_rating(self):
        """Test updating template rating."""
        template = WorkflowTemplate(
            template_id="tpl-001",
            name="Test Template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[],
            parameters=[],
            average_rating=4.0,
            rating_count=10
        )

        template.update_rating(5.0)
        # New average: (4.0 * 10 + 5.0) / 11 = 45/11 = 4.09
        assert template.rating_count == 11
        assert template.average_rating > 4.0


class TestWorkflowTemplateManager:
    """Test WorkflowTemplateManager class."""

    @pytest.fixture
    def template_dir(self, tmp_path):
        """Create temporary template directory."""
        return str(tmp_path / "templates")

    @pytest.fixture
    def manager(self, template_dir):
        """Create WorkflowTemplateManager instance."""
        return WorkflowTemplateManager(template_dir=template_dir)

    # Tests 10-13: Template CRUD
    def test_create_template(self, manager):
        """Test creating a new template."""
        template_data = {
            "template_id": "tpl-001",
            "name": "Test Template",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BASIC,
            "version": "1.0.0",
            "author": "System",
            "steps": [],
            "parameters": []
        }

        template = manager.create_template(template_data)

        assert template.template_id == "tpl-001"
        assert template.name == "Test Template"

    def test_get_template(self, manager):
        """Test retrieving a template by ID."""
        template_id = "tpl-001"
        template = WorkflowTemplate(
            template_id=template_id,
            name="Test Template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[],
            parameters=[]
        )

        # Save template first
        manager._save_template(template)

        retrieved = manager.get_template(template_id)

        assert retrieved is not None
        assert retrieved.template_id == template_id

    def test_update_template(self, manager):
        """Test updating an existing template."""
        template_id = "tpl-001"
        template = WorkflowTemplate(
            template_id=template_id,
            name="Original Name",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[],
            parameters=[]
        )

        manager._save_template(template)

        updates = {"name": "Updated Name"}
        updated = manager.update_template(template_id, updates)

        assert updated.name == "Updated Name"

    def test_delete_template(self, manager):
        """Test deleting a template."""
        template_id = "tpl-001"
        template = WorkflowTemplate(
            template_id=template_id,
            name="Test Template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[],
            parameters=[]
        )

        manager._save_template(template)

        result = manager.delete_template(template_id)

        assert result is True
        assert manager.get_template(template_id) is None

    # Tests 14-16: Template Operations
    def test_list_templates(self, manager):
        """Test listing all templates."""
        # Create multiple templates
        for i in range(3):
            template = WorkflowTemplate(
                template_id=f"tpl-{i}",
                name=f"Template {i}",
                category=TemplateCategory.AUTOMATION,
                complexity=TemplateComplexity.BASIC,
                version="1.0.0",
                author="System",
                steps=[],
                parameters=[]
            )
            manager._save_template(template)

        templates = manager.list_templates()

        assert len(templates) == 3

    def test_search_templates(self, manager):
        """Test searching templates by query."""
        template1 = WorkflowTemplate(
            template_id="tpl-001",
            name="Data Processing Template",
            category=TemplateCategory.DATA_PROCESSING,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[],
            parameters=[]
        )

        template2 = WorkflowTemplate(
            template_id="tpl-002",
            name="Automation Template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[],
            parameters=[]
        )

        manager._save_template(template1)
        manager._save_template(template2)

        results = manager.search_templates("data")

        assert len(results) >= 1
        if results:
            assert "data" in results[0].name.lower()

    def test_export_template(self, manager):
        """Test exporting template to dict."""
        template_id = "tpl-001"
        template = WorkflowTemplate(
            template_id=template_id,
            name="Test Template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[],
            parameters=[]
        )

        manager._save_template(template)

        exported = manager.export_template(template_id)

        assert isinstance(exported, dict)
        assert exported["template_id"] == template_id

    # Tests 17-18: Error Handling
    def test_get_template_not_found(self, manager):
        """Test getting a template that doesn't exist."""
        template = manager.get_template("tpl-999")
        assert template is None

    def test_update_template_not_found(self, manager):
        """Test updating a template that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            manager.update_template("tpl-999", {"name": "Updated"})

    # Tests 19-20: Integration Scenarios
    def test_template_lifecycle(self, manager):
        """Test complete template lifecycle (create → read → update → delete)."""
        # Create
        template_data = {
            "template_id": "tpl-lifecycle",
            "name": "Lifecycle Test Template",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BASIC,
            "version": "1.0.0",
            "author": "System",
            "steps": [],
            "parameters": []
        }

        template = manager.create_template(template_data)
        assert template.template_id == "tpl-lifecycle"

        # Read
        retrieved = manager.get_template("tpl-lifecycle")
        assert retrieved is not None

        # Update
        updated = manager.update_template("tpl-lifecycle", {"name": "Updated Name"})
        assert updated.name == "Updated Name"

        # Delete
        result = manager.delete_template("tpl-lifecycle")
        assert result is True

    def test_import_export_template(self, manager):
        """Test importing and exporting templates."""
        template = WorkflowTemplate(
            template_id="tpl-import-export",
            name="Import Export Test",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BASIC,
            version="1.0.0",
            author="System",
            steps=[
                TemplateStep(
                    step_id="step-001",
                    name="Test Step",
                    action="test",
                    parameters={}
                )
            ],
            parameters=[]
        )

        manager._save_template(template)

        # Export
        exported = manager.export_template("tpl-import-export")
        assert isinstance(exported, dict)

        # Import
        imported = manager.import_template(exported, overwrite=False)
        assert imported.template_id == template.template_id
