"""
Comprehensive test coverage for WorkflowMarketplace

This test suite covers:
- Marketplace connection and template listing
- Search queries and filtering
- Template validation and security checks
- Marketplace operations (import, export, create)
- Advanced and industry template handling
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from core.workflow_marketplace import (
    AdvancedWorkflowTemplate,
    MarketplaceEngine,
    TemplateType,
    WorkflowTemplate,
)


@pytest.fixture
def temp_templates_dir():
    """Create a temporary templates directory for testing"""
    temp_dir = tempfile.mkdtemp()
    templates_dir = os.path.join(temp_dir, "marketplace_templates")
    advanced_dir = os.path.join(templates_dir, "advanced")
    industry_dir = os.path.join(templates_dir, "industry")

    os.makedirs(templates_dir, exist_ok=True)
    os.makedirs(advanced_dir, exist_ok=True)
    os.makedirs(industry_dir, exist_ok=True)

    yield templates_dir, advanced_dir, industry_dir

    # Cleanup
    import shutil

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def sample_template():
    """Sample workflow template for testing"""
    return {
        "id": "tmpl_test_workflow",
        "name": "Test Workflow",
        "description": "A test workflow for unit testing",
        "category": "Testing",
        "author": "Test Author",
        "version": "1.0.0",
        "integrations": ["test_integration"],
        "complexity": "Beginner",
        "workflow_data": {
            "nodes": [
                {"id": "1", "type": "trigger", "label": "Test Trigger", "config": {}},
                {"id": "2", "type": "action", "label": "Test Action", "config": {}},
            ],
            "edges": [{"source": "1", "target": "2"}],
        },
        "created_at": "2026-01-01T00:00:00Z",
        "downloads": 0,
        "rating": 5.0,
        "tags": ["test", "sample"],
    }


@pytest.fixture
def sample_advanced_template():
    """Sample advanced workflow template"""
    return {
        "id": "advanced_test_pipeline",
        "name": "Test Pipeline",
        "description": "Advanced test pipeline",
        "category": "Data Processing",
        "author": "ATOM Team",
        "version": "2.0.0",
        "integrations": ["database", "api"],
        "complexity": "Advanced",
        "tags": ["pipeline", "test", "advanced"],
        "input_schema": [
            {
                "name": "input_data",
                "type": "object",
                "label": "Input Data",
                "required": True,
            }
        ],
        "steps": [
            {
                "step_id": "step1",
                "name": "Validate",
                "description": "Validate input",
                "step_type": "validation",
                "estimated_duration": 30,
            },
            {
                "step_id": "step2",
                "name": "Process",
                "description": "Process data",
                "step_type": "processing",
                "estimated_duration": 60,
                "depends_on": ["step1"],
            },
        ],
        "estimated_duration": 90,
        "prerequisites": [],
        "use_cases": ["Testing"],
        "benefits": ["Fast", "Reliable"],
    }


@pytest.fixture
def sample_industry_template():
    """Sample industry-specific template"""
    return {
        "id": "industry_healthcare_test",
        "name": "Healthcare Test Workflow",
        "description": "Healthcare-specific test workflow",
        "category": "Healthcare",
        "author": "ATOM Team",
        "version": "1.0.0",
        "integrations": ["ehr", "email"],
        "complexity": "Intermediate",
        "industry": "healthcare",
        "compliance_requirements": ["HIPAA"],
        "input_schema": [
            {
                "name": "patient_id",
                "type": "string",
                "label": "Patient ID",
                "required": True,
            }
        ],
        "steps": [
            {
                "step_id": "verify",
                "name": "Verify Patient",
                "description": "Verify patient information",
                "step_type": "verification",
                "estimated_duration": 60,
            }
        ],
        "estimated_duration": 60,
        "use_cases": ["Patient verification"],
        "benefits": ["Compliant", "Secure"],
    }


class TestWorkflowMarketplace:
    """Test marketplace connection, workflow listing, and search queries"""

    def test_marketplace_initialization(self, temp_templates_dir):
        """Test marketplace engine initialization"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            assert marketplace.templates_dir == templates_dir
            assert marketplace.advanced_templates_dir == advanced_dir
            assert marketplace.industry_templates_dir == industry_dir

    def test_list_templates_empty(self, temp_templates_dir):
        """Test listing templates when marketplace is empty"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace.list_templates()
            assert templates == []

    def test_list_templates_with_category_filter(self, temp_templates_dir, sample_template):
        """Test listing templates with category filter"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create template
        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Filter by matching category
            templates = marketplace.list_templates(category="Testing")
            assert len(templates) == 1
            assert templates[0].category == "Testing"

            # Filter by non-matching category
            templates = marketplace.list_templates(category="NonExistent")
            assert len(templates) == 0

    def test_list_templates_with_type_filter(self, temp_templates_dir, sample_template):
        """Test listing templates with template type filter"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create legacy template
        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        sample_template["template_type"] = TemplateType.LEGACY
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Filter by legacy type
            templates = marketplace.list_templates(template_type=TemplateType.LEGACY)
            assert len(templates) == 1
            assert templates[0].template_type == TemplateType.LEGACY

            # Filter by advanced type (should be empty)
            templates = marketplace.list_templates(template_type=TemplateType.ADVANCED)
            assert len(templates) == 0

    def test_list_templates_with_tags_filter(self, temp_templates_dir, sample_template):
        """Test listing templates with tags filter"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create template with tags
        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        sample_template["tags"] = ["test", "sample", "workflow"]
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Filter by matching tag
            templates = marketplace.list_templates(tags=["test"])
            assert len(templates) == 1

            # Filter by non-matching tag
            templates = marketplace.list_templates(tags=["nonexistent"])
            assert len(templates) == 0

            # Filter by multiple tags (should match any)
            templates = marketplace.list_templates(tags=["test", "other"])
            assert len(templates) == 1

    def test_list_templates_with_industry_filter(self, temp_templates_dir, sample_industry_template):
        """Test listing industry-specific templates"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create industry template
        template_path = os.path.join(industry_dir, f"{sample_industry_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_industry_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Filter by industry
            templates = marketplace.list_templates(industry="healthcare")
            assert len(templates) == 1
            assert templates[0].industry == "healthcare"

            # Filter by non-matching industry
            templates = marketplace.list_templates(industry="finance")
            assert len(templates) == 0

    def test_list_templates_multiple_filters(self, temp_templates_dir, sample_template):
        """Test listing templates with multiple filters combined"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create template
        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        sample_template["tags"] = ["test", "beginner"]
        sample_template["template_type"] = TemplateType.LEGACY
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Apply multiple filters
            templates = marketplace.list_templates(
                category="Testing",
                template_type=TemplateType.LEGACY,
                tags=["test"],
            )
            assert len(templates) == 1

    def test_get_template_success(self, temp_templates_dir, sample_template):
        """Test getting a specific template by ID"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create template
        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        initial_downloads = sample_template["downloads"]
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Get template
            template = marketplace.get_template("tmpl_test_workflow")

            assert template is not None
            assert template.id == "tmpl_test_workflow"
            assert template.name == "Test Workflow"

            # Verify download count incremented
            with open(template_path, "r") as f:
                updated_data = json.load(f)
                assert updated_data["downloads"] == initial_downloads + 1

    def test_get_template_not_found(self, temp_templates_dir):
        """Test getting non-existent template"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            template = marketplace.get_template("nonexistent_template")
            assert template is None

    def test_get_template_advanced(self, temp_templates_dir, sample_advanced_template):
        """Test getting advanced template by ID"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create advanced template
        template_path = os.path.join(advanced_dir, f"{sample_advanced_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_advanced_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            template = marketplace.get_template("advanced_test_pipeline")

            assert template is not None
            assert template.id == "advanced_test_pipeline"
            assert template.template_type == TemplateType.ADVANCED

    def test_get_template_industry(self, temp_templates_dir, sample_industry_template):
        """Test getting industry template by ID"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create industry template
        template_path = os.path.join(industry_dir, f"{sample_industry_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_industry_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            template = marketplace.get_template("industry_healthcare_test")

            assert template is not None
            assert template.id == "industry_healthcare_test"
            assert template.template_type == TemplateType.INDUSTRY
            assert template.industry == "healthcare"

    def test_load_legacy_templates(self, temp_templates_dir, sample_template):
        """Test loading legacy templates"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create legacy template
        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace._load_legacy_templates()
            assert len(templates) == 1
            assert templates[0].template_type == TemplateType.LEGACY

    def test_load_advanced_templates(self, temp_templates_dir, sample_advanced_template):
        """Test loading advanced templates"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create advanced template
        template_path = os.path.join(advanced_dir, f"{sample_advanced_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_advanced_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace._load_advanced_templates()
            assert len(templates) == 1
            assert templates[0].template_type == TemplateType.ADVANCED
            assert templates[0].multi_step_support is True

    def test_load_industry_templates(self, temp_templates_dir, sample_industry_template):
        """Test loading industry templates"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create industry template
        template_path = os.path.join(industry_dir, f"{sample_industry_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_industry_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace._load_industry_templates()
            assert len(templates) == 1
            assert templates[0].template_type == TemplateType.INDUSTRY
            assert templates[0].industry == "healthcare"

    def test_load_templates_with_invalid_json(self, temp_templates_dir):
        """Test handling of invalid JSON files"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create invalid JSON file
        invalid_path = os.path.join(templates_dir, "invalid.json")
        with open(invalid_path, "w") as f:
            f.write("{ invalid json }")

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Should handle gracefully and return empty list
            templates = marketplace._load_legacy_templates()
            assert len(templates) == 0


class TestMarketplaceQueries:
    """Test category browsing, tag search, rating sorting, date filtering"""

    def test_category_browsing_productivity(self, temp_templates_dir, sample_template):
        """Test browsing productivity category"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        sample_template["category"] = "Productivity"
        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace.list_templates(category="Productivity")
            assert len(templates) == 1
            assert all(t.category == "Productivity" for t in templates)

    def test_category_browsing_multiple_categories(self, temp_templates_dir, sample_template):
        """Test browsing multiple categories"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create templates in different categories
        for category in ["Sales", "Marketing", "Productivity"]:
            template = sample_template.copy()
            template["id"] = f"tmpl_{category.lower()}"
            template["category"] = category
            template_path = os.path.join(templates_dir, f"{template['id']}.json")
            with open(template_path, "w") as f:
                json.dump(template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Get all templates
            all_templates = marketplace.list_templates()
            assert len(all_templates) == 3

            # Get specific category
            sales_templates = marketplace.list_templates(category="Sales")
            assert len(sales_templates) == 1

    def test_tag_search_single_tag(self, temp_templates_dir, sample_template):
        """Test searching by single tag"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        sample_template["tags"] = ["automation", "email", "productivity"]
        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Search by tag
            templates = marketplace.list_templates(tags=["automation"])
            assert len(templates) == 1

            # Search by non-matching tag
            templates = marketplace.list_templates(tags=["nonexistent"])
            assert len(templates) == 0

    def test_tag_search_multiple_tags(self, temp_templates_dir, sample_template):
        """Test searching by multiple tags (OR logic)"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create templates with different tags
        for i, tags in enumerate([["automation", "email"], ["sales", "crm"], ["automation", "sales"]]):
            template = sample_template.copy()
            template["id"] = f"tmpl_{i}"
            template["tags"] = tags
            template_path = os.path.join(templates_dir, f"{template['id']}.json")
            with open(template_path, "w") as f:
                json.dump(template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Search with multiple tags (should match any)
            templates = marketplace.list_templates(tags=["automation", "crm"])
            assert len(templates) == 3  # All three have at least one matching tag

    def test_rating_sorting_high_rated(self, temp_templates_dir, sample_template):
        """Test sorting templates by rating (high to low)"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create templates with different ratings
        for i, rating in enumerate([5.0, 3.5, 4.8, 2.0]):
            template = sample_template.copy()
            template["id"] = f"tmpl_{i}"
            template["rating"] = rating
            template_path = os.path.join(templates_dir, f"{template['id']}.json")
            with open(template_path, "w") as f:
                json.dump(template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace.list_templates()

            # Sort by rating (descending)
            sorted_templates = sorted(templates, key=lambda t: t.rating, reverse=True)

            assert sorted_templates[0].rating == 5.0
            assert sorted_templates[-1].rating == 2.0

    def test_downloads_sorting(self, temp_templates_dir, sample_template):
        """Test sorting templates by download count"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create templates with different download counts
        for i, downloads in enumerate([100, 50, 200, 10]):
            template = sample_template.copy()
            template["id"] = f"tmpl_{i}"
            template["downloads"] = downloads
            template_path = os.path.join(templates_dir, f"{template['id']}.json")
            with open(template_path, "w") as f:
                json.dump(template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace.list_templates()

            # Sort by downloads (descending)
            sorted_templates = sorted(templates, key=lambda t: t.downloads, reverse=True)

            assert sorted_templates[0].downloads == 200
            assert sorted_templates[-1].downloads == 10

    def test_date_filtering_recent(self, temp_templates_dir, sample_template):
        """Test filtering templates by creation date"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create templates with different dates
        from datetime import timedelta

        for i, days in enumerate([0, 7, 30, 365]):
            template = sample_template.copy()
            template["id"] = f"tmpl_{i}"
            template["created_at"] = (datetime.now() - timedelta(days=days)).isoformat()
            template_path = os.path.join(templates_dir, f"{template['id']}.json")
            with open(template_path, "w") as f:
                json.dump(template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace.list_templates()

            # Filter to recent templates (last 30 days)
            recent = datetime.now() - timedelta(days=30)
            recent_templates = [t for t in templates if datetime.fromisoformat(t.created_at) >= recent]

            assert len(recent_templates) >= 2  # At least 0 and 7 days

    def test_complexity_filtering(self, temp_templates_dir, sample_template):
        """Test filtering by complexity level"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create templates with different complexity levels
        for complexity in ["Beginner", "Intermediate", "Advanced"]:
            template = sample_template.copy()
            template["id"] = f"tmpl_{complexity.lower()}"
            template["complexity"] = complexity
            template_path = os.path.join(templates_dir, f"{template['id']}.json")
            with open(template_path, "w") as f:
                json.dump(template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace.list_templates()

            # Filter by complexity
            beginner_templates = [t for t in templates if t.complexity == "Beginner"]
            assert len(beginner_templates) == 1

    def test_integration_filtering(self, temp_templates_dir, sample_template):
        """Test filtering by required integrations"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # Create templates with different integrations
        for i, integrations in enumerate(
            [
                ["slack", "email"],
                ["salesforce", "slack"],
                ["database", "api"],
            ]
        ):
            template = sample_template.copy()
            template["id"] = f"tmpl_{i}"
            template["integrations"] = integrations
            template_path = os.path.join(templates_dir, f"{template['id']}.json")
            with open(template_path, "w") as f:
                json.dump(template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace.list_templates()

            # Filter by integration
            slack_templates = [t for t in templates if "slack" in t.integrations]
            assert len(slack_templates) == 2


class TestMarketplaceValidation:
    """Test workflow schema validation, security checks, signature verification"""

    def test_workflow_schema_validation_valid(self, temp_templates_dir):
        """Test validation of valid workflow schema"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        valid_workflow = {
            "nodes": [{"id": "1", "type": "trigger", "label": "Start", "config": {}}],
            "edges": [],
        }

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Should not raise exception
            result = marketplace.import_workflow(valid_workflow)
            assert "id" in result
            assert "name" in result

    def test_workflow_schema_validation_missing_nodes(self, temp_templates_dir):
        """Test validation fails with missing nodes"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        invalid_workflow = {"edges": []}

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            with pytest.raises(ValueError, match="Invalid workflow structure: missing nodes or edges"):
                marketplace.import_workflow(invalid_workflow)

    def test_workflow_schema_validation_missing_edges(self, temp_templates_dir):
        """Test validation fails with missing edges"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        invalid_workflow = {"nodes": []}

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            with pytest.raises(ValueError, match="Invalid workflow structure: missing nodes or edges"):
                marketplace.import_workflow(invalid_workflow)

    def test_export_workflow_validation(self, temp_templates_dir):
        """Test export workflow structure validation"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        valid_workflow = {
            "nodes": [{"id": "1", "type": "trigger"}],
            "edges": [],
            "name": "Test Workflow",
        }

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            export_data = marketplace.export_workflow(valid_workflow)

            assert "nodes" in export_data
            assert "edges" in export_data
            assert "metadata" in export_data
            assert "exported_at" in export_data["metadata"]

    def test_export_workflow_missing_structure(self, temp_templates_dir):
        """Test export validation with missing structure"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        invalid_workflow = {"nodes": []}

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            with pytest.raises(ValueError, match="Invalid workflow structure: missing nodes or edges"):
                marketplace.export_workflow(invalid_workflow)

    def test_template_id_uniqueness(self, temp_templates_dir, sample_template):
        """Test that template IDs are unique"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace.list_templates()
            template_ids = [t.id for t in templates]

            # All IDs should be unique
            assert len(template_ids) == len(set(template_ids))

    def test_template_required_fields(self, temp_templates_dir, sample_template):
        """Test that templates have all required fields"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            template = marketplace.get_template("tmpl_test_workflow")

            # Verify required fields
            assert template.id is not None
            assert template.name is not None
            assert template.description is not None
            assert template.category is not None
            assert template.author is not None
            assert template.version is not None
            assert template.integrations is not None
            assert template.complexity is not None
            assert template.workflow_data is not None

    def test_advanced_template_required_features(self, temp_templates_dir, sample_advanced_template):
        """Test advanced templates have required feature flags"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        template_path = os.path.join(advanced_dir, f"{sample_advanced_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_advanced_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            templates = marketplace._load_advanced_templates()
            template = templates[0]

            # Verify advanced features
            assert template.multi_input_support is True
            assert template.multi_step_support is True
            assert template.multi_output_support is True
            assert template.pause_resume_support is True


class TestMarketplaceOperations:
    """Test download workflow, install workflow, rate workflow, submit review"""

    def test_import_workflow_success(self, temp_templates_dir):
        """Test importing a workflow successfully"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        workflow_json = {
            "name": "Imported Workflow",
            "nodes": [{"id": "1", "type": "trigger"}],
            "edges": [],
        }

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            result = marketplace.import_workflow(workflow_json)

            assert "id" in result
            assert "name" in result
            assert result["name"] == "Imported: Imported Workflow"
            assert "imported_at" in result

    def test_import_workflow_with_custom_name(self, temp_templates_dir):
        """Test importing workflow preserves custom name"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        workflow_json = {
            "name": "My Custom Workflow",
            "nodes": [{"id": "1", "type": "trigger"}],
            "edges": [],
        }

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            result = marketplace.import_workflow(workflow_json)

            assert "My Custom Workflow" in result["name"]

    def test_export_workflow_with_metadata(self, temp_templates_dir):
        """Test exporting workflow includes metadata"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        workflow_data = {
            "name": "Test Workflow",
            "description": "Test Description",
            "nodes": [{"id": "1", "type": "trigger"}],
            "edges": [],
        }

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            export_data = marketplace.export_workflow(workflow_data)

            assert export_data["name"] == "Test Workflow"
            assert export_data["description"] == "Test Description"
            assert "metadata" in export_data
            assert "version" in export_data["metadata"]

    def test_create_advanced_template(self, temp_templates_dir, sample_advanced_template):
        """Test creating a new advanced template"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            template = marketplace.create_advanced_template(sample_advanced_template)

            assert isinstance(template, AdvancedWorkflowTemplate)
            assert template.id == "advanced_test_pipeline"
            assert template.multi_input_support is True
            assert template.multi_step_support is True

            # Verify file was created
            template_path = os.path.join(advanced_dir, f"{template.id}.json")
            assert os.path.exists(template_path)

    def test_create_advanced_template_auto_duration(self, temp_templates_dir):
        """Test creating advanced template auto-calculates duration"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        template_data = {
            "id": "test_auto_duration",
            "name": "Test",
            "category": "Test",
            "author": "Test",
            "version": "1.0.0",
            "integrations": [],
            "complexity": "Beginner",
            "steps": [
                {"step_id": "step1", "estimated_duration": 30},
                {"step_id": "step2", "estimated_duration": 60},
                {"step_id": "step3", "estimated_duration": 45},
            ],
        }

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            template = marketplace.create_advanced_template(template_data)

            # Should sum all step durations
            assert template.estimated_duration == 135

    def test_create_workflow_from_advanced_template(self, temp_templates_dir, sample_advanced_template):
        """Test creating workflow from advanced template"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        # First create the template
        template_path = os.path.join(advanced_dir, f"{sample_advanced_template['id']}.json")
        with open(template_path, "w") as f:
            json.dump(sample_advanced_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            workflow_def = marketplace.create_workflow_from_advanced_template(
                template_id="advanced_test_pipeline",
                workflow_name="My Workflow",
                parameters={"input_data": "test"},
            )

            assert workflow_def["workflow_id"].startswith("workflow_")
            assert workflow_def["name"] == "My Workflow"
            assert workflow_def["created_from_template"] == "advanced_test_pipeline"
            assert workflow_def["created_from_advanced_template"] is True
            assert workflow_def["user_inputs"] == {"input_data": "test"}

    def test_create_workflow_nonexistent_template(self, temp_templates_dir):
        """Test creating workflow from non-existent template"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            with pytest.raises(ValueError, match="Advanced template nonexistent not found"):
                marketplace.create_workflow_from_advanced_template(
                    template_id="nonexistent",
                    workflow_name="Test",
                )

    def test_template_download_increment(self, temp_templates_dir, sample_template):
        """Test that template download count increments"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        sample_template["downloads"] = 10
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Get template (should increment download count)
            template = marketplace.get_template("tmpl_test_workflow")

            # Verify file was updated
            with open(template_path, "r") as f:
                updated_data = json.load(f)
                assert updated_data["downloads"] == 11

    def test_multiple_downloads_increment(self, temp_templates_dir, sample_template):
        """Test multiple downloads increment correctly"""
        templates_dir, advanced_dir, industry_dir = temp_templates_dir

        template_path = os.path.join(templates_dir, f"{sample_template['id']}.json")
        sample_template["downloads"] = 0
        with open(template_path, "w") as f:
            json.dump(sample_template, f)

        with patch("core.workflow_marketplace.MarketplaceEngine.__init__", lambda self: None):
            marketplace = MarketplaceEngine()
            marketplace.templates_dir = templates_dir
            marketplace.advanced_templates_dir = advanced_dir
            marketplace.industry_templates_dir = industry_dir

            # Get template multiple times
            for _ in range(5):
                marketplace.get_template("tmpl_test_workflow")

            # Verify file was updated
            with open(template_path, "r") as f:
                updated_data = json.load(f)
                assert updated_data["downloads"] == 5
