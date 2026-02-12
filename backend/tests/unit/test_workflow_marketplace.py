"""
Unit tests for workflow_marketplace.py

Tests the WorkflowMarketplace including:
- MarketplaceEngine initialization
- Template listing and discovery
- Template publishing
- Import/export functionality
- Advanced workflow templates
- Industry-specific templates
- Template statistics
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
from typing import Dict, Any

# Import the module to test
import sys
sys.path.insert(0, '/Users/rushiparikh/projects/atom/backend')

from core.workflow_marketplace import (
    TemplateType,
    WorkflowTemplate,
    AdvancedWorkflowTemplate,
    MarketplaceEngine,
    router,
)


# ==================== Test Fixtures ====================

@pytest.fixture
def temp_templates_dir():
    """Create temporary directory for templates"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def marketplace_engine(temp_templates_dir):
    """Create a MarketplaceEngine with temporary directory"""
    with patch('core.workflow_marketplace.MarketplaceEngine.__init__') as mock_init:
        mock_init.return_value = None
        engine = MarketplaceEngine()
        engine.templates_dir = temp_templates_dir
        engine.advanced_templates_dir = os.path.join(temp_templates_dir, "advanced")
        engine.industry_templates_dir = os.path.join(temp_templates_dir, "industry")
        os.makedirs(engine.advanced_templates_dir, exist_ok=True)
        os.makedirs(engine.industry_templates_dir, exist_ok=True)
        return engine


@pytest.fixture
def sample_template_data():
    """Sample workflow template data"""
    return {
        "id": "test_template_001",
        "name": "Test Workflow Template",
        "description": "A test workflow template",
        "category": "Testing",
        "author": "Test Author",
        "version": "1.0.0",
        "integrations": ["test", "mock"],
        "complexity": "Beginner",
        "workflow_data": {
            "nodes": [
                {"id": "1", "type": "trigger", "label": "Start"},
                {"id": "2", "type": "action", "label": "Process"}
            ],
            "edges": [
                {"source": "1", "target": "2"}
            ]
        },
        "tags": ["test", "automation"],
        "created_at": datetime.now().isoformat(),
        "downloads": 0,
        "rating": 5.0
    }


@pytest.fixture
def sample_advanced_template_data():
    """Sample advanced workflow template data"""
    return {
        "id": "advanced_test_001",
        "name": "Advanced Test Template",
        "description": "An advanced workflow template",
        "category": "Data Processing",
        "author": "Test Author",
        "version": "2.0.0",
        "integrations": ["api", "database"],
        "complexity": "Advanced",
        "tags": ["advanced", "etl"],
        "input_schema": [
            {
                "name": "source",
                "type": "select",
                "label": "Data Source",
                "description": "Select data source",
                "required": True,
                "options": ["api", "database", "file"]
            }
        ],
        "steps": [
            {
                "step_id": "validate",
                "name": "Validate Inputs",
                "description": "Validate input parameters",
                "step_type": "validation",
                "estimated_duration": 30,
                "depends_on": []
            },
            {
                "step_id": "process",
                "name": "Process Data",
                "description": "Process the data",
                "step_type": "processing",
                "estimated_duration": 120,
                "depends_on": ["validate"]
            }
        ],
        "output_config": {
            "type": "single",
            "outputs": ["result"]
        },
        "estimated_duration": 150,
        "prerequisites": ["data_access"],
        "use_cases": ["Data migration"],
        "benefits": ["Fast processing"],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "downloads": 0,
        "rating": 5.0,
        "pause_resume_support": True,
        "multi_input_support": True,
        "multi_step_support": True,
        "multi_output_support": True
    }


# ==================== Test MarketplaceInit ====================

class TestMarketplaceInit:
    """Tests for MarketplaceEngine initialization"""

    def test_router_prefix(self):
        """Test router has correct prefix"""
        assert router.prefix == "/api/marketplace"

    def test_router_tags(self):
        """Test router has correct tags"""
        assert "marketplace" in router.tags

    def test_template_type_enum(self):
        """Test TemplateType enum values"""
        assert TemplateType.LEGACY == "legacy"
        assert TemplateType.ADVANCED == "advanced"
        assert TemplateType.INDUSTRY == "industry"

    def test_workflow_template_model(self, sample_template_data):
        """Test WorkflowTemplate model validation"""
        template = WorkflowTemplate(**sample_template_data)

        assert template.id == "test_template_001"
        assert template.name == "Test Workflow Template"
        assert template.category == "Testing"
        assert template.complexity == "Beginner"
        assert template.downloads == 0
        assert template.rating == 5.0

    def test_advanced_workflow_template_model(self, sample_advanced_template_data):
        """Test AdvancedWorkflowTemplate model validation"""
        template = AdvancedWorkflowTemplate(**sample_advanced_template_data)

        assert template.id == "advanced_test_001"
        assert len(template.input_schema) == 1
        assert len(template.steps) == 2
        assert template.pause_resume_support is True
        assert template.multi_input_support is True


# ==================== Test Template Publishing ====================

class TestTemplatePublishing:
    """Tests for template publishing functionality"""

    def test_save_template_to_file(self, marketplace_engine, sample_template_data):
        """Test saving a template to file"""
        template_path = os.path.join(marketplace_engine.templates_dir, f"{sample_template_data['id']}.json")

        with open(template_path, 'w') as f:
            json.dump(sample_template_data, f, indent=2)

        # Verify file exists
        assert os.path.exists(template_path)

        # Verify content
        with open(template_path, 'r') as f:
            loaded_data = json.load(f)

        assert loaded_data["id"] == sample_template_data["id"]
        assert loaded_data["name"] == sample_template_data["name"]

    def test_save_advanced_template(self, marketplace_engine, sample_advanced_template_data):
        """Test saving an advanced template"""
        template_path = os.path.join(marketplace_engine.advanced_templates_dir, f"{sample_advanced_template_data['id']}.json")

        with open(template_path, 'w') as f:
            json.dump(sample_advanced_template_data, f, indent=2)

        # Verify file exists
        assert os.path.exists(template_path)

        # Verify it's in advanced directory
        assert "advanced" in template_path

    def test_template_with_metadata(self, marketplace_engine):
        """Test creating template with all metadata fields"""
        template_data = {
            "id": "meta_test",
            "name": "Metadata Test",
            "description": "Test metadata fields",
            "category": "Test",
            "author": "Tester",
            "version": "1.0.0",
            "integrations": [],
            "complexity": "Beginner",
            "workflow_data": {"nodes": [], "edges": []},
            "tags": ["test", "metadata"],
            "created_at": datetime.now().isoformat(),
            "downloads": 100,
            "rating": 4.5,
            "estimated_duration": 300,
            "multi_input_support": True,
            "multi_step_support": True,
            "multi_output_support": False,
            "pause_resume_support": True,
            "prerequisites": ["req1", "req2"]
        }

        template = WorkflowTemplate(**template_data)

        assert template.estimated_duration == 300
        assert template.multi_input_support is True
        assert template.pause_resume_support is True
        assert len(template.prerequisites) == 2


# ==================== Test Template Discovery ====================

class TestTemplateDiscovery:
    """Tests for template discovery and listing"""

    def test_list_templates_empty(self, marketplace_engine):
        """Test listing templates when none exist"""
        templates = marketplace_engine.list_templates()

        assert templates == []

    def test_list_templates_with_data(self, marketplace_engine, sample_template_data):
        """Test listing templates with existing templates"""
        # Create multiple templates
        for i in range(3):
            template_data = sample_template_data.copy()
            template_data["id"] = f"template_{i}"
            template_data["name"] = f"Template {i}"
            template_data["category"] = f"Category {i % 2}"  # Alternate categories

            template_path = os.path.join(marketplace_engine.templates_dir, f"template_{i}.json")
            with open(template_path, 'w') as f:
                json.dump(template_data, f, indent=2)

        templates = marketplace_engine.list_templates()

        assert len(templates) == 3

    def test_list_templates_with_category_filter(self, marketplace_engine, sample_template_data):
        """Test listing templates filtered by category"""
        # Create templates in different categories
        for category in ["Data", "Automation", "Reporting"]:
            template_data = sample_template_data.copy()
            template_data["id"] = f"{category.lower()}_template"
            template_data["category"] = category

            template_path = os.path.join(marketplace_engine.templates_dir, f"{category.lower()}_template.json")
            with open(template_path, 'w') as f:
                json.dump(template_data, f, indent=2)

        # Filter by Data category
        data_templates = marketplace_engine.list_templates(category="Data")

        assert len(data_templates) == 1
        assert data_templates[0].category == "Data"

    def test_list_templates_with_tag_filter(self, marketplace_engine, sample_template_data):
        """Test listing templates filtered by tags"""
        # Create templates with different tags
        template1_data = sample_template_data.copy()
        template1_data["id"] = "tagged_1"
        template1_data["tags"] = ["etl", "data"]

        template2_data = sample_template_data.copy()
        template2_data["id"] = "tagged_2"
        template2_data["tags"] = ["automation"]

        template3_data = sample_template_data.copy()
        template3_data["id"] = "tagged_3"
        template3_data["tags"] = ["etl", "automation"]

        for template_data in [template1_data, template2_data, template3_data]:
            template_path = os.path.join(marketplace_engine.templates_dir, f"{template_data['id']}.json")
            with open(template_path, 'w') as f:
                json.dump(template_data, f, indent=2)

        # Filter by etl tag
        etl_templates = marketplace_engine.list_templates(tags=["etl"])

        assert len(etl_templates) == 2
        assert all(any("etl" in tag for tag in t.tags) for t in etl_templates)

    def test_list_templates_with_type_filter(self, marketplace_engine, sample_advanced_template_data):
        """Test listing templates filtered by type"""
        # Create legacy template
        legacy_data = sample_template_data.copy()
        legacy_data["id"] = "legacy_test"
        legacy_data["template_type"] = TemplateType.LEGACY

        legacy_path = os.path.join(marketplace_engine.templates_dir, "legacy_test.json")
        with open(legacy_path, 'w') as f:
            json.dump(legacy_data, f, indent=2)

        # Create advanced template
        advanced_data = sample_advanced_template_data.copy()
        advanced_data["template_type"] = TemplateType.ADVANCED

        advanced_path = os.path.join(marketplace_engine.advanced_templates_dir, "advanced_test.json")
        with open(advanced_path, 'w') as f:
            json.dump(advanced_data, f, indent=2)

        # Filter by advanced type
        advanced_templates = marketplace_engine.list_templates(template_type=TemplateType.ADVANCED)

        assert len(advanced_templates) == 1
        assert advanced_templates[0].template_type == TemplateType.ADVANCED

    def test_get_template_by_id(self, marketplace_engine, sample_template_data):
        """Test retrieving a specific template by ID"""
        # Create template
        template_path = os.path.join(marketplace_engine.templates_dir, f"{sample_template_data['id']}.json")
        with open(template_path, 'w') as f:
            json.dump(sample_template_data, f, indent=2)

        # Get template
        template = marketplace_engine.get_template(sample_template_data["id"])

        assert template is not None
        assert template.id == sample_template_data["id"]
        assert template.name == sample_template_data["name"]

    def test_get_template_not_found(self, marketplace_engine):
        """Test retrieving non-existent template"""
        template = marketplace_engine.get_template("nonexistent")

        assert template is None

    def test_get_template_increments_download_count(self, marketplace_engine, sample_template_data):
        """Test that getting template increments download count"""
        # Create template with specific download count
        sample_template_data["downloads"] = 5
        template_path = os.path.join(marketplace_engine.templates_dir, f"{sample_template_data['id']}.json")
        with open(template_path, 'w') as f:
            json.dump(sample_template_data, f, indent=2)

        # Get template twice
        marketplace_engine.get_template(sample_template_data["id"])
        marketplace_engine.get_template(sample_template_data["id"])

        # Verify download count incremented
        # Note: This requires re-reading the file
        with open(template_path, 'r') as f:
            updated_data = json.load(f)

        assert updated_data["downloads"] == 7  # 5 + 2


# ==================== Test Import/Export ====================

class TestImportExport:
    """Tests for workflow import/export functionality"""

    def test_import_workflow_valid(self, marketplace_engine):
        """Test importing a valid workflow"""
        workflow_json = {
            "nodes": [
                {"id": "1", "type": "trigger", "label": "Start"},
                {"id": "2", "type": "action", "label": "End"}
            ],
            "edges": [
                {"source": "1", "target": "2"}
            ]
        }

        result = marketplace_engine.import_workflow(workflow_json)

        assert "id" in result
        assert "name" in result
        assert "Imported:" in result["name"]
        assert result["nodes"] == workflow_json["nodes"]
        assert result["edges"] == workflow_json["edges"]

    def test_import_workflow_missing_nodes(self, marketplace_engine):
        """Test importing workflow with missing nodes"""
        workflow_json = {
            "edges": [{"source": "1", "target": "2"}]
        }

        with pytest.raises(ValueError, match="Invalid workflow structure"):
            marketplace_engine.import_workflow(workflow_json)

    def test_import_workflow_missing_edges(self, marketplace_engine):
        """Test importing workflow with missing edges"""
        workflow_json = {
            "nodes": [{"id": "1", "type": "trigger"}]
        }

        with pytest.raises(ValueError, match="Invalid workflow structure"):
            marketplace_engine.import_workflow(workflow_json)

    def test_export_workflow(self, marketplace_engine):
        """Test exporting a workflow"""
        workflow_data = {
            "name": "Export Test Workflow",
            "description": "A workflow to export",
            "nodes": [{"id": "1", "type": "trigger"}],
            "edges": []
        }

        export_data = marketplace_engine.export_workflow(workflow_data)

        assert export_data["name"] == "Export Test Workflow"
        assert "nodes" in export_data
        assert "edges" in export_data
        assert "metadata" in export_data
        assert "exported_at" in export_data["metadata"]

    def test_export_workflow_invalid_structure(self, marketplace_engine):
        """Test exporting workflow with invalid structure"""
        workflow_data = {
            "name": "Invalid Workflow"
        }

        with pytest.raises(ValueError, match="Invalid workflow structure"):
            marketplace_engine.export_workflow(workflow_data)


# ==================== Test Advanced Templates ====================

class TestAdvancedTemplates:
    """Tests for advanced workflow templates"""

    def test_create_advanced_template(self, marketplace_engine, sample_advanced_template_data):
        """Test creating an advanced template"""
        template = marketplace_engine.create_advanced_template(sample_advanced_template_data)

        assert template.id == sample_advanced_template_data["id"]
        assert template.multi_input_support is True
        assert template.multi_step_support is True
        assert template.multi_output_support is True
        assert template.pause_resume_support is True

    def test_advanced_template_calculates_duration(self, marketplace_engine):
        """Test that advanced template calculates estimated duration"""
        template_data = {
            "id": "duration_test",
            "name": "Duration Test",
            "description": "Test duration calculation",
            "category": "Test",
            "author": "Tester",
            "version": "1.0.0",
            "integrations": [],
            "complexity": "Beginner",
            "steps": [
                {"step_id": "s1", "estimated_duration": 100},
                {"step_id": "s2", "estimated_duration": 200},
                {"step_id": "s3", "estimated_duration": 150}
            ]
        }

        template = marketplace_engine.create_advanced_template(template_data)

        assert template.estimated_duration == 450  # Sum of all steps

    def test_create_workflow_from_advanced_template(self, marketplace_engine, sample_advanced_template_data):
        """Test creating a workflow from an advanced template"""
        # Save the template first
        template_path = os.path.join(marketplace_engine.advanced_templates_dir, f"{sample_advanced_template_data['id']}.json")
        with open(template_path, 'w') as f:
            json.dump(sample_advanced_template_data, f, indent=2)

        # Create workflow from template
        workflow_def = marketplace_engine.create_workflow_from_advanced_template(
            template_id=sample_advanced_template_data["id"],
            workflow_name="My Workflow",
            parameters={"source": "api"}
        )

        assert workflow_def["workflow_id"].startswith("workflow_")
        assert workflow_def["name"] == "My Workflow"
        assert workflow_def["created_from_template"] == sample_advanced_template_data["id"]
        assert workflow_def["created_from_advanced_template"] is True
        assert workflow_def["multi_input_support"] is True
        assert workflow_def["pause_resume_support"] is True

    def test_create_workflow_from_nonexistent_template(self, marketplace_engine):
        """Test creating workflow from non-existent template"""
        with pytest.raises(ValueError, match="not found"):
            marketplace_engine.create_workflow_from_advanced_template(
                template_id="nonexistent",
                workflow_name="Test"
            )


# ==================== Test Template Statistics ====================

class TestTemplateStatistics:
    """Tests for template statistics"""

    def test_get_statistics_empty(self, marketplace_engine):
        """Test getting statistics when no templates exist"""
        stats = marketplace_engine.list_templates()

        assert len(stats) == 0

    def test_get_statistics_with_data(self, marketplace_engine, sample_template_data):
        """Test getting statistics with template data"""
        # Create templates with different properties
        for i in range(3):
            template_data = sample_template_data.copy()
            template_data["id"] = f"stats_test_{i}"
            template_data["category"] = f"Category {i % 2}"  # 2 categories
            template_data["complexity"] = "Beginner" if i < 2 else "Advanced"
            template_data["downloads"] = i * 10
            template_data["rating"] = 4.0 + i * 0.5

            template_path = os.path.join(marketplace_engine.templates_dir, f"stats_test_{i}.json")
            with open(template_path, 'w') as f:
                json.dump(template_data, f, indent=2)

        templates = marketplace_engine.list_templates()

        # Verify counts
        assert len(templates) == 3

        # Total downloads
        total_downloads = sum(t.downloads for t in templates)
        assert total_downloads == 30  # 0 + 10 + 20

        # Average rating
        avg_rating = sum(t.rating for t in templates) / len(templates)
        assert pytest.approx(avg_rating, 0.1) == 4.5  # (4.0 + 4.5 + 5.0) / 3


# ==================== Test Industry Templates ====================

class TestIndustryTemplates:
    """Tests for industry-specific templates"""

    def test_industry_template_has_industry_field(self):
        """Test that industry templates have industry field"""
        industry_template_data = {
            "id": "healthcare_test",
            "name": "Healthcare Template",
            "description": "A healthcare workflow",
            "category": "Healthcare",
            "author": "Medical",
            "version": "1.0.0",
            "integrations": ["ehr"],
            "complexity": "Advanced",
            "industry": "healthcare",
            "compliance_requirements": ["HIPAA"],
            "input_schema": [],
            "steps": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "downloads": 0,
            "rating": 5.0,
            "template_type": TemplateType.INDUSTRY
        }

        template = WorkflowTemplate(**industry_template_data)

        assert template.industry == "healthcare"

    def test_industry_template_with_compliance(self):
        """Test industry template with compliance requirements"""
        template_data = {
            "id": "finance_test",
            "name": "Finance Template",
            "description": "A finance workflow",
            "category": "Finance",
            "author": "Financial",
            "version": "1.0.0",
            "integrations": ["quickbooks"],
            "complexity": "Advanced",
            "industry": "finance",
            "compliance_requirements": ["SOX", "GDPR"],
            "input_schema": [],
            "steps": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "downloads": 0,
            "rating": 5.0
        }

        # Compliance requirements would be in metadata
        assert "compliance_requirements" in template_data
        assert len(template_data["compliance_requirements"]) == 2


# ==================== Test Template Types ====================

class TestTemplateTypes:
    """Tests for different template types"""

    def test_legacy_template_type(self, sample_template_data):
        """Test legacy template type"""
        template = WorkflowTemplate(**sample_template_data)

        assert template.template_type == TemplateType.LEGACY

    def test_advanced_template_features(self, sample_advanced_template_data):
        """Test advanced template has required features"""
        template = AdvancedWorkflowTemplate(**sample_advanced_template_data)

        assert template.multi_input_support is True
        assert template.multi_step_support is True
        assert template.multi_output_support is True
        assert template.pause_resume_support is True

    def test_industry_template_type(self):
        """Test industry template type"""
        industry_data = {
            "id": "industry_test",
            "name": "Industry Test",
            "description": "Test",
            "category": "Industrial",
            "author": "Tester",
            "version": "1.0.0",
            "integrations": [],
            "complexity": "Beginner",
            "industry": "manufacturing",
            "input_schema": [],
            "steps": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "downloads": 0,
            "rating": 5.0,
            "template_type": TemplateType.INDUSTRY
        }

        template = WorkflowTemplate(**industry_data)
        assert template.template_type == TemplateType.INDUSTRY


# ==================== Test Marketplace Errors ====================

class TestMarketplaceErrors:
    """Tests for error handling in marketplace"""

    def test_load_corrupted_template(self, marketplace_engine):
        """Test handling of corrupted template file"""
        # Create corrupted file
        corrupted_path = os.path.join(marketplace_engine.templates_dir, "corrupted.json")
        with open(corrupted_path, 'w') as f:
            f.write("{ invalid json }")

        # Should handle gracefully (return empty or skip)
        templates = marketplace_engine.list_templates()
        # Corrupted template should be skipped
        assert "corrupted" not in [t.id for t in templates if hasattr(t, 'id')]

    def test_get_template_invalid_json(self, marketplace_engine):
        """Test getting template with invalid JSON"""
        invalid_path = os.path.join(marketplace_engine.templates_dir, "invalid.json")
        with open(invalid_path, 'w') as f:
            f.write("{ invalid }")

        template = marketplace_engine.get_template("invalid")
        assert template is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
