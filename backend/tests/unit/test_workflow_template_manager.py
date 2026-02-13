"""
Unit tests for Workflow Template Manager

Tests cover:
- Template CRUD operations
- Template instantiation
- Template validation
- Category filtering
- Error handling
"""
import pytest
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import tempfile
import shutil

from core.workflow_template_system import WorkflowTemplateManager, TemplateCategory, TemplateComplexity


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_templates_dir():
    """Create a temporary directory for templates."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def template_manager(temp_templates_dir):
    """Template manager instance with temporary directory."""
    return WorkflowTemplateManager(template_dir=temp_templates_dir)


@pytest.fixture
def sample_template_data():
    """Sample template data."""
    return {
        "template_id": "test_template_123",
        "name": "Test Template",
        "description": "Test description",
        "category": TemplateCategory.AUTOMATION,
        "complexity": TemplateComplexity.INTERMEDIATE,
        "tags": ["test", "automation"],
        "inputs": [],
        "steps": [
            {
                "id": "step_1",
                "name": "First Step",
                "description": "Initialize",
                "step_type": "agent_execution",
                "parameters": [],
                "depends_on": []
            }
        ],
        "output_schema": {},
        "estimated_total_duration": 60,
        "prerequisites": [],
        "dependencies": [],
        "permissions": [],
        "is_public": True,
        "is_featured": False
    }


@pytest.fixture
def sample_template_id():
    """Sample template ID."""
    return "test_template_123"


# =============================================================================
# Template Creation Tests
# =============================================================================

class TestTemplateCreation:
    """Tests for template creation."""

    def test_create_template_basic(self, template_manager, sample_template_data):
        """Test creating basic template."""
        result = template_manager.create_template(sample_template_data)

        assert result is not None
        assert result.template_id == "test_template_123"
        assert result.name == "Test Template"

    def test_create_template_with_steps(self, template_manager, temp_templates_dir):
        """Test creating template with steps."""
        data = {
            "template_id": "template_with_steps",
            "name": "Template with Steps",
            "description": "Template with multiple steps",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "steps": [
                {
                    "id": "s1",
                    "name": "Step 1",
                    "description": "First step",
                    "step_type": "agent_execution",
                    "parameters": [],
                    "depends_on": []
                },
                {
                    "id": "s2",
                    "name": "Step 2",
                    "description": "Second step",
                    "step_type": "data_processing",
                    "parameters": [],
                    "depends_on": []
                }
            ]
        }

        result = template_manager.create_template(data)

        assert result is not None
        assert len(result.steps) == 2

    def test_create_template_generates_id(self, template_manager):
        """Test template creation generates unique ID."""
        data1 = {
            "name": "Template 1",
            "description": "First template",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": []
        }
        data2 = {
            "name": "Template 2",
            "description": "Second template",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": []
        }

        result1 = template_manager.create_template(data1)
        result2 = template_manager.create_template(data2)

        assert result1.template_id != result2.template_id

    def test_create_template_sets_timestamps(self, template_manager):
        """Test template creation sets timestamps."""
        data = {
            "name": "Timestamp Test",
            "description": "Test timestamps",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": []
        }

        result = template_manager.create_template(data)

        assert result.created_at is not None
        assert result.updated_at is not None

    def test_create_template_duplicate_id(self, template_manager, sample_template_data):
        """Test creating template with duplicate ID fails."""
        template_manager.create_template(sample_template_data)

        with pytest.raises(Exception):
            template_manager.create_template(sample_template_data)


# =============================================================================
# Template Retrieval Tests
# =============================================================================

class TestTemplateRetrieval:
    """Tests for template retrieval."""

    def test_get_template_by_id(self, template_manager, sample_template_data, sample_template_id):
        """Test getting template by ID."""
        template_manager.create_template(sample_template_data)

        result = template_manager.get_template(sample_template_id)

        assert result is not None
        assert result.template_id == sample_template_id

    def test_get_template_not_found(self, template_manager):
        """Test getting non-existent template."""
        result = template_manager.get_template("nonexistent_template")

        assert result is None

    def test_list_templates_all(self, template_manager):
        """Test listing all templates."""
        data1 = {
            "name": "Template 1",
            "description": "First",
            "template_id": "tpl_1",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": []
        }
        data2 = {
            "name": "Template 2",
            "description": "Second",
            "template_id": "tpl_2",
            "category": TemplateCategory.DATA_PROCESSING,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "steps": []
        }

        template_manager.create_template(data1)
        template_manager.create_template(data2)

        result = template_manager.list_templates()

        assert len(result) == 2

    def test_list_templates_by_category(self, template_manager):
        """Test listing templates by category."""
        data1 = {
            "name": "Automation Template",
            "description": "Automation",
            "template_id": "tpl_automation",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": []
        }
        data2 = {
            "name": "Data Template",
            "description": "Data",
            "template_id": "tpl_data",
            "category": TemplateCategory.DATA_PROCESSING,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "steps": []
        }

        template_manager.create_template(data1)
        template_manager.create_template(data2)

        result = template_manager.list_templates(category=TemplateCategory.AUTOMATION)

        assert len(result) == 1
        assert result[0].template_id == "tpl_automation"

    def test_list_templates_by_complexity(self, template_manager):
        """Test listing templates by complexity."""
        data1 = {
            "name": "Beginner Template",
            "description": "Beginner",
            "template_id": "tpl_beginner",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": []
        }
        data2 = {
            "name": "Advanced Template",
            "description": "Advanced",
            "template_id": "tpl_advanced",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.ADVANCED,
            "steps": []
        }

        template_manager.create_template(data1)
        template_manager.create_template(data2)

        result = template_manager.list_templates(complexity=TemplateComplexity.BEGINNER)

        assert len(result) == 1
        assert result[0].template_id == "tpl_beginner"

    def test_list_templates_by_tags(self, template_manager):
        """Test listing templates by tags."""
        data1 = {
            "name": "Automation Template",
            "description": "Automation",
            "template_id": "tpl_automation",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "tags": ["automation", "productivity"],
            "steps": []
        }
        data2 = {
            "name": "Data Template",
            "description": "Data",
            "template_id": "tpl_data",
            "category": TemplateCategory.DATA_PROCESSING,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "tags": ["data", "etl"],
            "steps": []
        }

        template_manager.create_template(data1)
        template_manager.create_template(data2)

        result = template_manager.list_templates(tags=["automation"])

        assert len(result) == 1
        assert result[0].template_id == "tpl_automation"

    def test_list_templates_with_limit(self, template_manager):
        """Test listing templates with limit."""
        for i in range(10):
            template_manager.create_template({
                "template_id": f"tpl_{i}",
                "name": f"Template {i}",
                "description": f"Template number {i}",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "steps": []
            })

        result = template_manager.list_templates(limit=5)

        assert len(result) == 5


# =============================================================================
# Template Update Tests
# =============================================================================

class TestTemplateUpdate:
    """Tests for template updates."""

    def test_update_template_name(self, template_manager, sample_template_data, sample_template_id):
        """Test updating template name."""
        template_manager.create_template(sample_template_data)

        result = template_manager.update_template(sample_template_id, {"name": "Updated Name"})

        assert result is not None
        assert result.name == "Updated Name"

    def test_update_template_description(self, template_manager, sample_template_data, sample_template_id):
        """Test updating template description."""
        template_manager.create_template(sample_template_data)

        result = template_manager.update_template(
            sample_template_id,
            {"description": "Updated description"}
        )

        assert result is not None
        assert result.description == "Updated description"

    def test_update_template_tags(self, template_manager, sample_template_data, sample_template_id):
        """Test updating template tags."""
        template_manager.create_template(sample_template_data)

        result = template_manager.update_template(
            sample_template_id,
            {"tags": ["updated", "tags"]}
        )

        assert result is not None
        assert "updated" in result.tags

    def test_update_template_not_found(self, template_manager, sample_template_id):
        """Test updating non-existent template."""
        with pytest.raises(ValueError):
            template_manager.update_template(sample_template_id, {"name": "New Name"})


# =============================================================================
# Template Deletion Tests
# =============================================================================

class TestTemplateDeletion:
    """Tests for template deletion."""

    def test_delete_template_success(self, template_manager, sample_template_data, sample_template_id):
        """Test deleting existing template."""
        template_manager.create_template(sample_template_data)

        result = template_manager.delete_template(sample_template_id)

        assert result is True

        # Verify it's deleted
        assert template_manager.get_template(sample_template_id) is None

    def test_delete_template_not_found(self, template_manager, sample_template_id):
        """Test deleting non-existent template."""
        result = template_manager.delete_template(sample_template_id)

        assert result is False


# =============================================================================
# Template Instantiation Tests
# =============================================================================

class TestTemplateInstantiation:
    """Tests for template instantiation."""

    def test_create_workflow_from_template_basic(self, template_manager, sample_template_data, sample_template_id):
        """Test instantiating template with defaults."""
        template_manager.create_template(sample_template_data)

        result = template_manager.create_workflow_from_template(
            template_id=sample_template_id,
            workflow_name="My Workflow",
            template_parameters={}
        )

        assert result is not None
        assert "workflow_id" in result
        assert result["template_used"] == sample_template_id

    def test_create_workflow_from_template_with_parameters(self, template_manager, sample_template_data, sample_template_id):
        """Test instantiating template with parameters."""
        sample_template_data["inputs"] = [
            {
                "name": "api_key",
                "type": "string",
                "required": True,
                "default_value": "default_key"
            }
        ]
        template_manager.create_template(sample_template_data)

        result = template_manager.create_workflow_from_template(
            template_id=sample_template_id,
            workflow_name="Parameterized Workflow",
            template_parameters={"api_key": "custom_key"}
        )

        assert result is not None
        assert "workflow_id" in result

    def test_create_workflow_from_template_with_customizations(self, template_manager, sample_template_data, sample_template_id):
        """Test instantiating template with customizations."""
        template_manager.create_template(sample_template_data)

        result = template_manager.create_workflow_from_template(
            template_id=sample_template_id,
            workflow_name="Customized Workflow",
            template_parameters={},
            customizations={"skip_validation": True}
        )

        assert result is not None
        assert result["workflow_definition"]["customizations"] == {"skip_validation": True}

    def test_create_workflow_from_template_not_found(self, template_manager, sample_template_id):
        """Test instantiating non-existent template."""
        with pytest.raises(ValueError):
            template_manager.create_workflow_from_template(
                template_id=sample_template_id,
                workflow_name="Test Workflow",
                template_parameters={}
            )


# =============================================================================
# Template Search Tests
# =============================================================================

class TestTemplateSearch:
    """Tests for template search."""

    def test_search_templates_basic(self, template_manager):
        """Test basic template search."""
        data = {
            "template_id": "automation_template",
            "name": "Automation Workflow",
            "description": "Automates repetitive tasks",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "tags": ["automation", "workflow"],
            "steps": []
        }

        template_manager.create_template(data)

        result = template_manager.search_templates("automation")

        assert len(result) >= 1
        assert any(t.template_id == "automation_template" for t in result)

    def test_search_templates_empty_results(self, template_manager):
        """Test search with no results."""
        result = template_manager.search_templates("nonexistent_term_xyz")

        assert result == []

    def test_search_templates_with_limit(self, template_manager):
        """Test search with limit."""
        for i in range(10):
            template_manager.create_template({
                "template_id": f"search_tpl_{i}",
                "name": f"Search Template {i}",
                "description": f"Search template {i}",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "tags": ["test"],
                "steps": []
            })

        result = template_manager.search_templates("Search Template", limit=5)

        assert len(result) == 5


# =============================================================================
# Template Rating Tests
# =============================================================================

class TestTemplateRating:
    """Tests for template rating."""

    def test_rate_template(self, template_manager, sample_template_data, sample_template_id):
        """Test rating a template."""
        template_manager.create_template(sample_template_data)

        result = template_manager.rate_template(sample_template_id, 4.5)

        assert result is True

        template = template_manager.get_template(sample_template_id)
        assert template.rating == 4.5
        assert template.review_count == 1

    def test_rate_template_multiple_ratings(self, template_manager, sample_template_data, sample_template_id):
        """Test rating a template multiple times."""
        template_manager.create_template(sample_template_data)

        template_manager.rate_template(sample_template_id, 4.0)
        template_manager.rate_template(sample_template_id, 5.0)

        template = template_manager.get_template(sample_template_id)
        assert template.rating == 4.5  # Average of 4.0 and 5.0
        assert template.review_count == 2

    def test_rate_template_not_found(self, template_manager, sample_template_id):
        """Test rating non-existent template."""
        result = template_manager.rate_template(sample_template_id, 4.5)

        assert result is False

    def test_rate_template_invalid_rating(self, template_manager, sample_template_data, sample_template_id):
        """Test rating with invalid value."""
        template_manager.create_template(sample_template_data)

        with pytest.raises(ValueError):
            template_manager.rate_template(sample_template_id, 6.0)  # Above 5.0


# =============================================================================
# Template Export/Import Tests
# =============================================================================

class TestTemplateExportImport:
    """Tests for template export/import."""

    def test_export_template(self, template_manager, sample_template_data, sample_template_id):
        """Test exporting template."""
        template_manager.create_template(sample_template_data)

        result = template_manager.export_template(sample_template_id)

        assert result is not None
        assert result["template_id"] == sample_template_id

    def test_export_template_not_found(self, template_manager, sample_template_id):
        """Test exporting non-existent template."""
        with pytest.raises(ValueError):
            template_manager.export_template(sample_template_id)

    def test_import_template_new(self, template_manager):
        """Test importing new template."""
        template_data = {
            "template_id": "imported_template",
            "name": "Imported Template",
            "description": "Imported from elsewhere",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": []
        }

        result = template_manager.import_template(template_data)

        assert result is not None
        assert result.template_id == "imported_template"

    def test_import_template_existing_no_overwrite(self, template_manager, sample_template_data):
        """Test importing existing template without overwrite fails."""
        template_manager.create_template(sample_template_data)

        with pytest.raises(ValueError):
            template_manager.import_template(sample_template_data, overwrite=False)

    def test_import_template_existing_with_overwrite(self, template_manager, sample_template_data):
        """Test importing existing template with overwrite."""
        template_manager.create_template(sample_template_data)

        result = template_manager.import_template(sample_template_data, overwrite=True)

        assert result is not None
        # Should have a new ID
        assert result.template_id != "test_template_123"


# =============================================================================
# Template Statistics Tests
# =============================================================================

class TestTemplateStatistics:
    """Tests for template statistics."""

    def test_get_template_statistics(self, template_manager):
        """Test getting template usage statistics."""
        # Create some templates
        for i in range(3):
            template_manager.create_template({
                "template_id": f"stats_tpl_{i}",
                "name": f"Stats Template {i}",
                "description": f"Stats template {i}",
                "category": TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.BEGINNER,
                "tags": ["test"],
                "steps": []
            })

        stats = template_manager.get_template_statistics()

        assert stats is not None
        assert "total_templates" in stats
        assert stats["total_templates"] == 3


# =============================================================================
# Template Step Validation Tests
# =============================================================================

class TestStepValidation:
    """Tests for step dependency validation."""

    def test_validate_step_dependencies_valid(self, template_manager):
        """Test template with valid step dependencies."""
        data = {
            "template_id": "valid_deps",
            "name": "Valid Dependencies",
            "description": "Valid step dependencies",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": [
                {
                    "id": "step_1",
                    "name": "Step 1",
                    "description": "First step",
                    "step_type": "agent_execution",
                    "parameters": [],
                    "depends_on": []
                },
                {
                    "id": "step_2",
                    "name": "Step 2",
                    "description": "Second step",
                    "step_type": "data_processing",
                    "parameters": [],
                    "depends_on": ["step_1"]
                }
            ]
        }

        result = template_manager.create_template(data)

        assert result is not None

    def test_validate_step_dependencies_invalid(self, template_manager):
        """Test template with invalid step dependencies fails."""
        data = {
            "template_id": "invalid_deps",
            "name": "Invalid Dependencies",
            "description": "Invalid dependencies",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "steps": [
                {
                    "id": "step_1",
                    "name": "Step 1",
                    "description": "First step",
                    "step_type": "agent_execution",
                    "parameters": [],
                    "depends_on": ["nonexistent_step"]
                }
            ]
        }

        with pytest.raises(ValueError):
            template_manager.create_template(data)
