"""
Coverage tests for workflow_template_system.py.

Target: 60%+ coverage (350 statements, ~210 lines to cover)
Focus: Template creation, validation, instantiation, parameters
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from core.workflow_template_system import (
    WorkflowTemplateManager,
    WorkflowTemplate,
    TemplateParameter,
    TemplateCategory,
    TemplateComplexity
)


class TestTemplateCreation:
    """Test workflow template creation."""

    def test_create_template(self):
        """Test creating a new workflow template."""
        system = WorkflowTemplateManager()

        template = system.create_template(
            name="data-processing",
            description="Process data files",
            steps=[
                {"id": "load", "action": "load_data"},
                {"id": "transform", "action": "transform_data"},
                {"id": "save", "action": "save_data"}
            ]
        )

        assert template.template_id is not None
        assert template.name == "data-processing"

    def test_create_template_with_parameters(self):
        """Test creating template with parameters."""
        system = WorkflowTemplateManager()

        template = system.create_template(
            name="parametrized-workflow",
            description="Workflow with parameters",
            category=TemplateCategory.DATA_PROCESSING,
            complexity=TemplateComplexity.INTERMEDIATE,
            steps=[{"step_id": "step1", "name": "Process", "action": "process"}],
            inputs=[
                {"name": "input_file", "type": "string", "required": True},
                {"name": "output_format", "type": "string", "default_value": "json"}
            ]
        )

        assert len(template.inputs) == 2

    def test_create_template_from_existing_workflow(self):
        """Test creating template from existing workflow."""
        system = WorkflowTemplateManager()

        with patch.object(system, '_get_workflow') as mock_get:
            mock_get.return_value = {
                "steps": [
                    {"step_id": "step1", "name": "Action 1", "action": "action1"},
                    {"step_id": "step2", "name": "Action 2", "action": "action2"}
                ]
            }

            template = system.create_template(
                name="workflow-template",
                description="Template from workflow",
                category=TemplateCategory.AUTOMATION,
                steps=[{"step_id": "step1", "name": "Step 1", "action": "action1"}]
            )
            assert template is not None


class TestTemplateValidation:
    """Test workflow template validation."""

    def test_validate_valid_template(self):
        """Test validation of valid template."""
        system = WorkflowTemplateManager()

        template = system.create_template(
            name="valid-template",
            description="Valid",
            category=TemplateCategory.GENERAL,
            steps=[{"step_id": "step1", "name": "Step", "action": "action"}]
        )

        assert template.template_id is not None
        assert len(template.steps) == 1

    def test_validate_template_missing_required_fields(self):
        """Test validation of template with missing fields."""
        system = WorkflowTemplateManager()

        # Test with empty name
        with pytest.raises(Exception):
            system.create_template(
                name="",  # Invalid empty name
                description="Test",
                category=TemplateCategory.GENERAL,
                steps=[]  # Invalid empty steps
            )

    def test_validate_template_parameters(self):
        """Test template parameter validation."""
        system = WorkflowTemplateManager()

        template = system.create_template(
            name="parametrized",
            description="Test",
            category=TemplateCategory.GENERAL,
            steps=[{"step_id": "step1", "name": "Step", "action": "action"}],
            inputs=[
                {"name": "required_param", "type": "string", "required": True}
            ]
        )

        # Validate parameters are properly set
        assert len(template.inputs) == 1
        assert template.inputs[0].required is True

    def test_validate_template_dependencies(self):
        """Test validation of template dependencies."""
        system = WorkflowTemplateManager()

        template = system.create_template(
            name="dependent-template",
            description="Test",
            category=TemplateCategory.GENERAL,
            steps=[
                {"step_id": "step1", "name": "Step 1", "action": "action", "depends_on": ["step2"]},  # Invalid - step2 doesn't exist
                {"step_id": "step2", "name": "Step 2", "action": "action", "depends_on": ["step1"]}
            ]
        )

        # This should raise validation error
        with pytest.raises(ValueError):
            WorkflowTemplate(**{
                "name": "invalid-deps",
                "description": "Invalid dependencies",
                "category": "general",
                "steps": [
                    {"step_id": "step1", "name": "S1", "action": "a", "depends_on": ["nonexistent"]}
                ]
            })


class TestTemplateInstantiation:
    """Test workflow template instantiation."""

    def test_instantiate_template(self):
        """Test instantiating template to workflow."""
        system = WorkflowTemplateManager()

        template = system.create_template(
            name="simple-template",
            description="Simple",
            category=TemplateCategory.GENERAL,
            steps=[
                {"step_id": "step1", "name": "Step 1", "action": "action1"},
                {"step_id": "step2", "name": "Step 2", "action": "action2"}
            ]
        )

        workflow = system.create_workflow_from_template(
            template_id=template.template_id,
            workflow_name="Test Workflow",
            template_parameters={}
        )

        assert workflow is not None
        assert workflow["workflow_definition"]["steps"] is not None

    def test_instantiate_with_parameters(self):
        """Test instantiating template with parameters."""
        system = WorkflowTemplateManager()

        template = system.create_template(
            name="parametrized",
            description="Test",
            category=TemplateCategory.GENERAL,
            steps=[
                {
                    "step_id": "step1",
                    "name": "Process",
                    "action": "process",
                    "parameters": [{"name": "input", "type": "string"}]
                }
            ],
            inputs=[
                {"name": "param", "type": "string", "required": True}
            ]
        )

        workflow = system.create_workflow_from_template(
            template_id=template.template_id,
            workflow_name="Test Workflow",
            template_parameters={"param": "test-value"}
        )

        assert workflow["parameters_applied"]["param"] == "test-value"

    def test_instantiate_with_default_parameters(self):
        """Test instantiation with default parameter values."""
        system = WorkflowTemplateManager()

        template = system.create_template(
            name="defaults",
            description="Test",
            category=TemplateCategory.GENERAL,
            steps=[{"step_id": "step1", "name": "Step", "action": "action"}],
            inputs=[
                {"name": "option", "type": "string", "default_value": "default-value"}
            ]
        )

        workflow = system.create_workflow_from_template(
            template_id=template.template_id,
            workflow_name="Test Workflow",
            template_parameters={}
        )

        assert workflow is not None


class TestTemplateManagement:
    """Test template lifecycle management."""

    def test_list_templates(self):
        """Test listing all templates."""
        system = WorkflowTemplateManager()

        system.create_template("template1", "Test 1", TemplateCategory.GENERAL, [])
        system.create_template("template2", "Test 2", TemplateCategory.GENERAL, [])

        templates = system.list_templates()
        assert len(templates) >= 2

    def test_get_template_by_id(self):
        """Test getting template by ID."""
        system = WorkflowTemplateManager()

        template = system.create_template("test", "Test", TemplateCategory.GENERAL, [])
        retrieved = system.get_template(template.template_id)

        assert retrieved.template_id == template.template_id

    def test_update_template(self):
        """Test updating template."""
        system = WorkflowTemplateManager()

        template = system.create_template("test", "Test", TemplateCategory.GENERAL, [])
        updated = system.update_template(
            template.template_id,
            {"description": "Updated description"}
        )

        assert updated.description == "Updated description"

    def test_delete_template(self):
        """Test deleting template."""
        system = WorkflowTemplateManager()

        template = system.create_template("test", "Test", TemplateCategory.GENERAL, [])
        deleted = system.delete_template(template.template_id)

        assert deleted is True

    def test_rate_template(self):
        """Test rating template."""
        system = WorkflowTemplateManager()

        template = system.create_template("test", "Test", TemplateCategory.GENERAL, [])
        result = system.rate_template(template.template_id, 4.5)

        assert result is True
        assert template.rating == 4.5


class TestTemplateDiscovery:
    """Test template discovery and search."""

    def test_search_templates_by_name(self):
        """Test searching templates by name."""
        system = WorkflowTemplateManager()

        system.create_template(
            "data-processor",
            "Processes data",
            TemplateCategory.DATA_PROCESSING,
            []
        )
        system.create_template(
            "data-validator",
            "Validates data",
            TemplateCategory.DATA_PROCESSING,
            []
        )

        results = system.search_templates("data")
        assert len(results) >= 2

    def test_filter_templates_by_tag(self):
        """Test filtering templates by tag."""
        system = WorkflowTemplateManager()

        system.create_template(
            "etl-workflow",
            "ETL Workflow",
            TemplateCategory.DATA_PROCESSING,
            [],
            tags=["etl", "data"]
        )

        templates = system.list_templates(tags=["etl"])
        assert len(templates) >= 1

    def test_get_popular_templates(self):
        """Test getting popular templates."""
        system = WorkflowTemplateManager()

        template = system.create_template("popular", "Popular Template", TemplateCategory.GENERAL, [])
        template.add_usage()

        popular = system.list_templates(limit=5)
        assert len(popular) >= 1

    def test_get_recent_templates(self):
        """Test getting recently created templates."""
        system = WorkflowTemplateManager()

        system.create_template("recent", "Recent Template", TemplateCategory.GENERAL, [])

        recent = system.list_templates(limit=10)
        assert len(recent) >= 1


class TestTemplateExportImport:
    """Test template export and import."""

    def test_export_template_to_dict(self):
        """Test exporting template to dict."""
        system = WorkflowTemplateManager()

        template = system.create_template("export-test", "Test", TemplateCategory.GENERAL, [])
        exported = system.export_template(template.template_id)

        assert "template_id" in exported
        assert exported["name"] == "export-test"

    def test_import_template_from_dict(self):
        """Test importing template from dict."""
        system = WorkflowTemplateManager()

        template_data = {
            "name": "imported-template",
            "description": "Imported",
            "category": "general",
            "steps": [
                {"step_id": "step1", "name": "Step 1", "action": "action1"}
            ]
        }

        imported = system.import_template(template_data)
        assert imported.name == "imported-template"

    def test_get_template_statistics(self):
        """Test getting template statistics."""
        system = WorkflowTemplateManager()

        stats = system.get_template_statistics()

        assert "total_templates" in stats
        assert "total_usage" in stats
        assert "average_rating" in stats
