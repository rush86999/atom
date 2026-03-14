"""
Coverage-driven tests for workflow_template_system.py (0% -> 75%+ target)

This test suite provides comprehensive coverage for the WorkflowTemplateSystem,
focusing on template creation, validation, instantiation, and parameter substitution.

Target: 75%+ coverage (265+ of 350 statements)
Strategy: Parametrized tests for template types, validation rules, and edge cases
"""

import json
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import pytest
import uuid
from pathlib import Path

from core.workflow_template_system import (
    WorkflowTemplate,
    WorkflowTemplateManager,
    TemplateParameter,
    TemplateStep,
    TemplateCategory,
    TemplateComplexity,
    TemplateMarketplace
)


class TestWorkflowTemplateModels:
    """Coverage tests for WorkflowTemplate model and related models"""

    @pytest.mark.parametrize("category,expected_value", [
        (TemplateCategory.AUTOMATION, "automation"),
        (TemplateCategory.AI_ML, "ai_ml"),
        (TemplateCategory.BUSINESS, "business"),
        (TemplateCategory.INTEGRATION, "integration"),
    ])
    def test_template_category_enum(self, category, expected_value):
        """Test TemplateCategory enum values"""
        assert category.value == expected_value

    @pytest.mark.parametrize("complexity,expected_value", [
        (TemplateComplexity.BEGINNER, "beginner"),
        (TemplateComplexity.INTERMEDIATE, "intermediate"),
        (TemplateComplexity.ADVANCED, "advanced"),
        (TemplateComplexity.EXPERT, "expert"),
    ])
    def test_template_complexity_enum(self, complexity, expected_value):
        """Test TemplateComplexity enum values"""
        assert complexity.value == expected_value

    @pytest.mark.parametrize("field_name,default_value", [
        ("label", None),
        ("description", None),
    ])
    def test_template_parameter_defaults(self, field_name, default_value):
        """Test TemplateParameter field defaults"""
        param = TemplateParameter(name="test_param")
        assert getattr(param, field_name) == default_value

    @pytest.mark.parametrize("param_data,expected_result", [
        ({"name": "param1", "type": "string", "required": True}, True),
        ({"name": "param2", "type": "number", "required": False, "default_value": 42}, False),
        ({"name": "param3", "type": "boolean", "required": True}, True),
    ])
    def test_template_parameter_creation(self, param_data, expected_result):
        """Test TemplateParameter creation with various configurations"""
        param = TemplateParameter(**param_data)
        assert param.required == expected_result
        assert param.name == param_data["name"]

    def test_template_step_alias_handling(self):
        """Test TemplateStep handles 'id' alias correctly"""
        step_data = {
            "id": "step_1",
            "name": "Test Step",
            "description": "A test step",
            "step_type": "action",
            "parameters": []
        }
        step = TemplateStep(**step_data)
        assert step.step_id == "step_1"

    def test_template_step_dependencies_validation(self):
        """Test TemplateStep dependency validation"""
        step = TemplateStep(
            step_id="step_1",
            name="Test Step",
            depends_on=["step_0", "step_2"]
        )
        assert step.depends_on == ["step_0", "step_2"]


class TestWorkflowTemplateCreation:
    """Coverage tests for WorkflowTemplate creation and validation"""

    @pytest.mark.parametrize("template_type,expected_structure", [
        (
            "sequential",
            {
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "has_steps": True
            }
        ),
        (
            "parallel",
            {
                "category": TemplateCategory.AI_ML,
                "complexity": TemplateComplexity.INTERMEDIATE,
                "has_steps": True
            }
        ),
        (
            "conditional",
            {
                "category": TemplateCategory.BUSINESS,
                "complexity": TemplateComplexity.ADVANCED,
                "has_conditions": True
            }
        ),
    ])
    def test_create_template_with_different_types(self, template_type, expected_structure):
        """Test template creation for different workflow types"""
        template_data = {
            "name": f"test_{template_type}_template",
            "description": f"A {template_type} workflow template",
            "category": expected_structure["category"],
            "complexity": expected_structure["complexity"],
            "steps": [
                {
                    "id": "step_1",
                    "name": "Start",
                    "description": "Start step",
                    "step_type": "action",
                    "parameters": []
                }
            ]
        }

        template = WorkflowTemplate(**template_data)

        assert template.template_id is not None
        assert template.name == f"test_{template_type}_template"
        assert template.category == expected_structure["category"]
        assert template.complexity == expected_structure["complexity"]
        assert len(template.steps) > 0

    @pytest.mark.parametrize("validation_check,should_pass", [
        ("valid_dependencies", True),
        ("invalid_dependency", False),
        ("empty_steps", True),
    ])
    def test_validate_template_step_connections(self, validation_check, should_pass):
        """Test template step connection validation"""
        if validation_check == "valid_dependencies":
            template_data = {
                "name": "valid_template",
                "description": "Template with valid dependencies",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "steps": [
                    {
                        "id": "step_1",
                        "name": "Step 1",
                        "description": "First step",
                        "step_type": "action",
                        "depends_on": [],
                        "parameters": []
                    },
                    {
                        "id": "step_2",
                        "name": "Step 2",
                        "description": "Second step",
                        "step_type": "action",
                        "depends_on": ["step_1"],
                        "parameters": []
                    }
                ]
            }
            # Should pass validation
            template = WorkflowTemplate(**template_data)
            assert len(template.steps) == 2

        elif validation_check == "invalid_dependency":
            template_data = {
                "name": "invalid_template",
                "description": "Template with invalid dependency",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "steps": [
                    {
                        "id": "step_1",
                        "name": "Step 1",
                        "description": "First step",
                        "step_type": "action",
                        "depends_on": ["nonexistent_step"],
                        "parameters": []
                    }
                ]
            }
            # Should fail validation
            with pytest.raises(ValueError, match="depends on non-existent step"):
                WorkflowTemplate(**template_data)

        else:  # empty_steps
            template_data = {
                "name": "empty_template",
                "description": "Template with no steps",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "steps": []
            }
            template = WorkflowTemplate(**template_data)
            assert len(template.steps) == 0

    def test_calculate_estimated_duration(self):
        """Test estimated duration calculation"""
        template_data = {
            "name": "duration_test",
            "description": "Test duration calculation",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": [
                {
                    "id": "step_1",
                    "name": "Step 1",
                    "description": "First step",
                    "step_type": "action",
                    "estimated_duration": 60,
                    "parameters": []
                },
                {
                    "id": "step_2",
                    "name": "Step 2",
                    "description": "Second step",
                    "step_type": "action",
                    "estimated_duration": 120,
                    "parameters": []
                }
            ]
        }

        template = WorkflowTemplate(**template_data)
        duration = template.calculate_estimated_duration()

        assert duration == 180  # 60 + 120
        assert template.estimated_total_duration == 180

    def test_add_usage(self):
        """Test usage tracking"""
        template = WorkflowTemplate(
            name="usage_test",
            description="Test usage tracking",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BEGINNER
        )

        initial_usage = template.usage_count
        template.add_usage()

        assert template.usage_count == initial_usage + 1
        assert isinstance(template.updated_at, datetime)

    def test_update_rating(self):
        """Test rating updates"""
        template = WorkflowTemplate(
            name="rating_test",
            description="Test rating updates",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BEGINNER
        )

        # First rating
        template.update_rating(4.5)
        assert template.rating == 4.5
        assert template.review_count == 1

        # Second rating
        template.update_rating(5.0)
        expected_rating = (4.5 * 1 + 5.0) / 2
        assert abs(template.rating - expected_rating) < 0.01
        assert template.review_count == 2


class TestWorkflowTemplateManager:
    """Coverage tests for WorkflowTemplateManager operations"""

    @pytest.fixture
    def temp_template_dir(self, tmp_path):
        """Create a temporary template directory"""
        template_dir = tmp_path / "templates"
        template_dir.mkdir(exist_ok=True)
        return str(template_dir)

    @pytest.fixture
    def manager(self, temp_template_dir):
        """Create a WorkflowTemplateManager instance"""
        return WorkflowTemplateManager(template_dir=temp_template_dir)

    @pytest.mark.parametrize("template_config", [
        {
            "name": "automation_template",
            "description": "An automation workflow",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "tags": ["automation", "test"],
            "steps": [
                {
                    "id": "step_1",
                    "name": "Start",
                    "description": "Start step",
                    "step_type": "action",
                    "parameters": []
                }
            ]
        },
        {
            "name": "ai_ml_template",
            "description": "An AI/ML workflow",
            "category": TemplateCategory.AI_ML,
            "complexity": TemplateComplexity.EXPERT,
            "tags": ["ai", "ml", "model"],
            "steps": [
                {
                    "id": "step_1",
                    "name": "Load Data",
                    "description": "Load training data",
                    "step_type": "action",
                    "parameters": []
                },
                {
                    "id": "step_2",
                    "name": "Train Model",
                    "description": "Train ML model",
                    "step_type": "action",
                    "depends_on": ["step_1"],
                    "parameters": []
                }
            ]
        }
    ])
    def test_create_template(self, manager, template_config):
        """Test template creation"""
        template = manager.create_template(template_config)

        assert template.template_id is not None
        assert template.name == template_config["name"]
        assert template.category == template_config["category"]
        assert template.complexity == template_config["complexity"]
        assert template.template_id in manager.templates

    def test_create_and_get_template(self, manager):
        """Test creating and retrieving a template"""
        template_data = {
            "name": "test_template",
            "description": "Test template",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER
        }

        created = manager.create_template(template_data)
        retrieved = manager.get_template(created.template_id)

        assert retrieved is not None
        assert retrieved.template_id == created.template_id
        assert retrieved.name == created.name

    def test_get_nonexistent_template(self, manager):
        """Test getting a non-existent template"""
        result = manager.get_template("nonexistent_id")
        assert result is None

    def test_update_template(self, manager):
        """Test updating a template"""
        template_data = {
            "name": "original_name",
            "description": "Original description",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER
        }

        template = manager.create_template(template_data)

        # Update template
        updates = {
            "name": "updated_name",
            "description": "Updated description",
            "tags": ["updated", "tags"]
        }

        updated = manager.update_template(template.template_id, updates)

        assert updated.name == "updated_name"
        assert updated.description == "Updated description"
        assert "updated" in updated.tags

    def test_update_nonexistent_template(self, manager):
        """Test updating a non-existent template"""
        with pytest.raises(ValueError, match="not found"):
            manager.update_template("nonexistent_id", {"name": "new_name"})

    def test_delete_template(self, manager):
        """Test deleting a template"""
        template_data = {
            "name": "delete_test",
            "description": "Template to delete",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER
        }

        template = manager.create_template(template_data)
        template_id = template.template_id

        result = manager.delete_template(template_id)

        assert result is True
        assert manager.get_template(template_id) is None

    def test_delete_nonexistent_template(self, manager):
        """Test deleting a non-existent template"""
        result = manager.delete_template("nonexistent_id")
        assert result is False

    def test_rate_template(self, manager):
        """Test rating a template"""
        template_data = {
            "name": "rate_test",
            "description": "Template to rate",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER
        }

        template = manager.create_template(template_data)
        result = manager.rate_template(template.template_id, 4.5)

        assert result is True
        updated = manager.get_template(template.template_id)
        assert updated.rating == 4.5
        assert updated.review_count == 1

    def test_rate_template_invalid_rating(self, manager):
        """Test rating with invalid values"""
        template_data = {
            "name": "rate_invalid_test",
            "description": "Template for invalid rating",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER
        }

        template = manager.create_template(template_data)

        with pytest.raises(ValueError, match="Rating must be between 1.0 and 5.0"):
            manager.rate_template(template.template_id, 6.0)

    def test_rate_nonexistent_template(self, manager):
        """Test rating a non-existent template"""
        result = manager.rate_template("nonexistent_id", 4.0)
        assert result is False


class TestTemplateFilteringAndSearch:
    """Coverage tests for template filtering and search operations"""

    @pytest.fixture
    def populated_manager(self, tmp_path):
        """Create a manager with multiple templates"""
        # Create isolated temp directory to avoid loading built-in templates
        template_dir = tmp_path / "isolated_templates"
        template_dir.mkdir(exist_ok=True)

        manager = WorkflowTemplateManager(template_dir=str(template_dir))

        templates = [
            {
                "name": "automation_1",
                "description": "First automation template",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "author": "Alice",
                "is_public": True,
                "tags": ["automation", "beginner"]
            },
            {
                "name": "automation_2",
                "description": "Second automation template",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.INTERMEDIATE,
                "author": "Bob",
                "is_public": False,
                "tags": ["automation", "intermediate"]
            },
            {
                "name": "ai_workflow",
                "description": "AI and ML workflow",
                "category": TemplateCategory.AI_ML,
                "complexity": TemplateComplexity.EXPERT,
                "author": "Alice",
                "is_public": True,
                "tags": ["ai", "ml", "expert"]
            }
        ]

        for template_data in templates:
            manager.create_template(template_data)

        return manager

    @pytest.mark.parametrize("filter_field,filter_value,min_expected", [
        ("category", TemplateCategory.AUTOMATION, 2),  # At least our 2 automation templates
        ("complexity", TemplateComplexity.BEGINNER, 1),  # At least our 1 beginner template
        ("author", "Alice", 2),  # At least our 2 Alice templates
        ("is_public", True, 2),  # At least our 2 public templates
        ("is_public", False, 1),  # At least our 1 private template
    ])
    def test_list_templates_with_filters(self, populated_manager, filter_field, filter_value, min_expected):
        """Test listing templates with various filters"""
        kwargs = {filter_field: filter_value}
        results = populated_manager.list_templates(**kwargs)

        # Check that we have at least the expected count (may include built-in templates)
        assert len(results) >= min_expected

        # Verify that our test templates are included
        if filter_field == "author" and filter_value == "Alice":
            template_names = [t.name for t in results]
            assert "automation_1" in template_names
            assert "ai_workflow" in template_names

    def test_list_templates_with_tag_filter(self, populated_manager):
        """Test filtering by tags"""
        results = populated_manager.list_templates(tags=["automation"])
        assert len(results) >= 2  # At least our 2 automation templates

        results = populated_manager.list_templates(tags=["ai"])
        assert len(results) >= 1  # At least our AI workflow

    def test_search_templates(self, populated_manager):
        """Test template search functionality"""
        # Search by name
        results = populated_manager.search_templates("automation")
        assert len(results) >= 2  # At least our 2 automation templates

        # Search by description
        results = populated_manager.search_templates("workflow")
        assert len(results) >= 1

        # Search with no matches
        results = populated_manager.search_templates("nonexistent")
        assert len(results) == 0

    def test_list_templates_limit(self, populated_manager):
        """Test limit parameter in list_templates"""
        results = populated_manager.list_templates(limit=2)
        assert len(results) <= 2


class TestTemplateWorkflowCreation:
    """Coverage tests for creating workflows from templates"""

    @pytest.fixture
    def manager_with_template(self, tmp_path):
        """Create a manager with a parameterized template"""
        # Use isolated temp directory to avoid built-in templates
        template_dir = tmp_path / "param_templates"
        template_dir.mkdir(exist_ok=True)

        manager = WorkflowTemplateManager(template_dir=str(template_dir))

        template_data = {
            "name": "parameterized_template",
            "description": "Template with parameters",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "inputs": [
                {
                    "name": "param1",
                    "type": "string",
                    "required": True,
                    "label": "First Parameter"
                },
                {
                    "name": "param2",
                    "type": "number",
                    "required": False,
                    "default_value": 42
                },
                {
                    "name": "param3",
                    "type": "boolean",
                    "required": False,
                    "default_value": True
                }
            ],
            "steps": [
                {
                    "id": "step_1",
                    "name": "Process",
                    "description": "Process step",
                    "step_type": "action",
                    "parameters": []
                }
            ]
        }

        manager.create_template(template_data)
        return manager

    @pytest.mark.parametrize("param_values", [
        {"param1": "value1", "param2": 100},
        {"param1": "value2"},  # Use default for param2
        {"param1": "value3", "param2": 200, "param3": False},
    ])
    def test_create_workflow_from_template(self, manager_with_template, param_values):
        """Test creating workflow from template with parameters"""
        # Find our parameterized template
        template = None
        for t in manager_with_template.templates.values():
            if t.name == "parameterized_template":
                template = t
                break

        assert template is not None, "parameterized_template not found"

        result = manager_with_template.create_workflow_from_template(
            template_id=template.template_id,
            workflow_name="test_workflow",
            template_parameters=param_values
        )

        assert "workflow_id" in result
        assert "workflow_definition" in result
        assert result["template_used"] == template.template_id
        assert "parameters_applied" in result

    def test_create_workflow_nonexistent_template(self, manager_with_template):
        """Test creating workflow from non-existent template"""
        with pytest.raises(ValueError, match="not found"):
            manager_with_template.create_workflow_from_template(
                template_id="nonexistent_id",
                workflow_name="test_workflow",
                template_parameters={}
            )

    @pytest.mark.parametrize("param_config,should_fail", [
        ({"param2": 100}, True),  # Missing required param1
        ({"param1": "value", "param2": "invalid"}, True),  # Invalid type for param2
        ({"param1": "value", "param2": 100}, False),  # Valid
    ])
    def test_create_workflow_parameter_validation(self, manager_with_template, param_config, should_fail):
        """Test parameter validation in workflow creation"""
        # Find our parameterized template (not built-in ones)
        template = None
        for t in manager_with_template.templates.values():
            if t.name == "parameterized_template":
                template = t
                break

        assert template is not None, "parameterized_template not found"

        if should_fail:
            # Should raise ValueError
            with pytest.raises(ValueError):
                manager_with_template.create_workflow_from_template(
                    template_id=template.template_id,
                    workflow_name="test_workflow",
                    template_parameters=param_config
                )
        else:
            # Should succeed
            result = manager_with_template.create_workflow_from_template(
                template_id=template.template_id,
                workflow_name="test_workflow",
                template_parameters=param_config
            )
            assert "workflow_id" in result


class TestTemplateParameterValidation:
    """Coverage tests for parameter validation logic"""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a manager instance"""
        return WorkflowTemplateManager(template_dir=str(tmp_path / "templates"))

    @pytest.mark.parametrize("param_type,input_value,expected_output", [
        ("string", "test", "test"),
        ("number", "42", 42.0),
        ("number", 3.14, 3.14),
        ("boolean", "true", True),
        ("boolean", "false", False),
        ("boolean", True, True),
        ("array", '["a", "b"]', ["a", "b"]),
        ("object", '{"key": "value"}', {"key": "value"}),
    ])
    def test_parameter_type_conversion(self, manager, param_type, input_value, expected_output):
        """Test parameter type conversion and validation"""
        template = WorkflowTemplate(
            name="test_template",
            description="Test template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BEGINNER,
            inputs=[
                {
                    "name": "test_param",
                    "type": param_type,
                    "required": True
                }
            ]
        )

        result = manager._validate_template_parameters(
            template,
            {"test_param": input_value}
        )

        assert result["test_param"] == expected_output

    def test_parameter_with_default_value(self, manager):
        """Test parameter default value handling"""
        template = WorkflowTemplate(
            name="test_template",
            description="Test template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BEGINNER,
            inputs=[
                {
                    "name": "optional_param",
                    "type": "string",
                    "required": False,
                    "default_value": "default_value"
                }
            ]
        )

        # Don't provide parameter - should use default
        result = manager._validate_template_parameters(template, {})
        assert result["optional_param"] == "default_value"

    def test_required_parameter_missing(self, manager):
        """Test error when required parameter is missing"""
        template = WorkflowTemplate(
            name="test_template",
            description="Test template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BEGINNER,
            inputs=[
                {
                    "name": "required_param",
                    "type": "string",
                    "required": True
                }
            ]
        )

        with pytest.raises(ValueError, match="Required parameter 'required_param' is missing"):
            manager._validate_template_parameters(template, {})


class TestTemplateExportImport:
    """Coverage tests for template export and import"""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a manager instance"""
        return WorkflowTemplateManager(template_dir=str(tmp_path / "templates"))

    def test_export_template(self, manager):
        """Test exporting template to dict"""
        template_data = {
            "name": "export_test",
            "description": "Template to export",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "tags": ["export", "test"]
        }

        template = manager.create_template(template_data)
        exported = manager.export_template(template.template_id)

        assert isinstance(exported, dict)
        assert exported["name"] == "export_test"
        assert exported["template_id"] == template.template_id

    def test_export_nonexistent_template(self, manager):
        """Test exporting non-existent template"""
        with pytest.raises(ValueError, match="not found"):
            manager.export_template("nonexistent_id")

    def test_import_template(self, manager):
        """Test importing template from dict"""
        template_data = {
            "name": "imported_template",
            "description": "Template imported from dict",
            "category": TemplateCategory.AI_ML,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "tags": ["imported"]
        }

        imported = manager.import_template(template_data)

        assert isinstance(imported, WorkflowTemplate)
        assert imported.name == "imported_template"
        assert imported.template_id in manager.templates

    def test_import_template_duplicate_id(self, manager):
        """Test importing template with duplicate ID"""
        # Use isolated temp directory to avoid built-in templates
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            isolated_manager = WorkflowTemplateManager(template_dir=tmpdir)

            # First import - generates ID
            template_data = {
                "name": "duplicate_test",
                "description": "Template with duplicate ID",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER
            }

            first = isolated_manager.import_template(template_data)

            # Second import with same ID - should fail
            template_data_with_id = template_data.copy()
            template_data_with_id["template_id"] = first.template_id

            with pytest.raises(ValueError, match="already exists"):
                isolated_manager.import_template(template_data_with_id, overwrite=False)

    def test_import_template_with_overwrite(self, manager):
        """Test importing template with overwrite enabled"""
        template_data = {
            "name": "overwrite_test",
            "description": "Original description",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER
        }

        # Import first time
        original = manager.import_template(template_data)

        # Import again with overwrite
        template_data["description"] = "Updated description"
        updated = manager.import_template(template_data, overwrite=True)

        # Should create a new template with different ID
        assert updated.template_id != original.template_id
        assert updated.description == "Updated description"


class TestTemplateStatistics:
    """Coverage tests for template statistics"""

    @pytest.fixture
    def manager_with_stats(self, tmp_path):
        """Create a manager with templates for statistics"""
        # Use isolated temp directory
        template_dir = tmp_path / "stats_templates"
        template_dir.mkdir(exist_ok=True)

        manager = WorkflowTemplateManager(template_dir=str(template_dir))

        templates = [
            {
                "name": "template_1",
                "description": "First template",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "usage_count": 10,
                "rating": 4.5,
                "review_count": 2
            },
            {
                "name": "template_2",
                "description": "Second template",
                "category": TemplateCategory.AI_ML,
                "complexity": TemplateComplexity.INTERMEDIATE,
                "usage_count": 20,
                "rating": 4.0,
                "review_count": 5
            },
            {
                "name": "template_3",
                "description": "Third template",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "usage_count": 5,
                "rating": 5.0,
                "review_count": 1
            }
        ]

        for template_data in templates:
            manager.create_template(template_data)

        return manager

    def test_get_template_statistics(self, manager_with_stats):
        """Test getting template statistics"""
        stats = manager_with_stats.get_template_statistics()

        assert "total_templates" in stats
        assert "total_usage" in stats
        assert "average_rating" in stats
        assert "category_breakdown" in stats
        assert "most_used_templates" in stats
        assert "highest_rated_templates" in stats

        assert stats["total_templates"] >= 3  # At least our 3 templates
        assert stats["total_usage"] >= 35  # At least our templates' usage

    def test_category_breakdown_in_statistics(self, manager_with_stats):
        """Test category breakdown in statistics"""
        stats = manager_with_stats.get_template_statistics()

        assert "automation" in stats["category_breakdown"]
        assert "ai_ml" in stats["category_breakdown"]

        auto_stats = stats["category_breakdown"]["automation"]
        assert auto_stats["count"] >= 2  # At least our 2 automation templates
        assert auto_stats["usage"] >= 15  # At least our templates' usage


class TestEdgeCasesAndErrors:
    """Coverage tests for edge cases and error handling"""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a manager instance"""
        template_dir = tmp_path / "edge_templates"
        template_dir.mkdir(exist_ok=True)
        return WorkflowTemplateManager(template_dir=str(template_dir))

    def test_template_with_invalid_json_in_param(self, manager):
        """Test handling of invalid JSON in array/object parameters"""
        template = WorkflowTemplate(
            name="test_template",
            description="Test template",
            category=TemplateCategory.AUTOMATION,
            complexity=TemplateComplexity.BEGINNER,
            inputs=[
                {
                    "name": "array_param",
                    "type": "array",
                    "required": True
                }
            ]
        )

        with pytest.raises(ValueError, match="Invalid value for parameter"):
            manager._validate_template_parameters(
                template,
                {"array_param": "invalid json string"}
            )

    def test_empty_template_search(self, manager):
        """Test search on empty manager"""
        # Clear built-in templates
        manager.templates.clear()
        manager.marketplace.templates.clear()
        results = manager.search_templates("test")
        assert len(results) == 0

    def test_list_all_templates_empty(self, manager):
        """Test listing all templates when manager is empty"""
        # Clear built-in templates
        manager.templates.clear()
        manager.marketplace.templates.clear()
        results = manager.list_templates()
        assert len(results) == 0
