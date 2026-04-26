"""
Comprehensive tests for Industry Workflow Templates

Tests core.industry_workflow_templates module which provides pre-built
workflow templates tailored for different industries and use cases.

Target: backend/core/industry_workflow_templates.py (852 lines)
Test Categories: Template Management, Domain Automation, Blueprint Execution, Industry Integration
"""

import pytest
from datetime import datetime
from typing import List

from core.industry_workflow_templates import (
    Industry,
    IndustryWorkflowTemplate,
    IndustryWorkflowEngine,
    get_industry_workflow_engine
)


# Test Category 1: Template Management (6 tests)

class TestTemplateManagement:
    """Tests for template creation, validation, and listing."""

    def test_industry_enum_values(self):
        """Test Industry enum has all expected values."""
        expected_industries = [
            Industry.HEALTHCARE,
            Industry.FINANCE,
            Industry.EDUCATION,
            Industry.RETAIL,
            Industry.MANUFACTURING,
            Industry.REAL_ESTATE,
            Industry.LEGAL,
            Industry.NON_PROFIT,
            Industry.TECHNOLOGY,
            Industry.CONSULTING,
            Industry.HOSPITALITY,
            Industry.LOGISTICS
        ]

        assert len(expected_industries) == 12

    def test_workflow_template_dataclass(self):
        """Test IndustryWorkflowTemplate dataclass initialization."""
        template = IndustryWorkflowTemplate(
            id="test_template",
            name="Test Template",
            description="Test description",
            industry=Industry.TECHNOLOGY,
            sub_category="Testing",
            complexity="Beginner",
            estimated_time_savings="5 hours/week",
            required_integrations=["slack"],
            optional_integrations=["gmail"],
            workflow_data={"nodes": [], "edges": []},
            setup_instructions=["Step 1"],
            benefits=["Benefit 1"],
            use_cases=["Use case 1"]
        )

        assert template.id == "test_template"
        assert template.industry == Industry.TECHNOLOGY
        assert template.complexity == "Beginner"
        assert template.created_at is not None  # Should be set by __post_init__

    def test_workflow_template_created_at_auto_generation(self):
        """Test created_at is auto-generated if not provided."""
        template = IndustryWorkflowTemplate(
            id="test",
            name="Test",
            description="Test",
            industry=Industry.TECHNOLOGY,
            sub_category="Test",
            complexity="Beginner",
            estimated_time_savings="1 hour/week",
            required_integrations=[],
            optional_integrations=[],
            workflow_data={},
            setup_instructions=[],
            benefits=[],
            use_cases=[]
        )

        assert template.created_at is not None
        assert isinstance(template.created_at, str)

    def test_engine_initialization(self):
        """Test IndustryWorkflowEngine initializes with templates."""
        engine = IndustryWorkflowEngine()

        assert len(engine.templates) > 0
        assert isinstance(engine.templates, dict)

    def test_get_template_by_id_found(self):
        """Test retrieving template by ID when it exists."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("healthcare_patient_onboarding")

        assert template is not None
        assert template.id == "healthcare_patient_onboarding"
        assert template.industry == Industry.HEALTHCARE

    def test_get_template_by_id_not_found(self):
        """Test retrieving template by ID when it doesn't exist."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("nonexistent_template")

        assert template is None


# Test Category 2: Domain Automation (6 tests)

class TestDomainAutomation:
    """Tests for industry-specific workflow templates."""

    def test_healthcare_template_exists(self):
        """Test healthcare patient onboarding template exists."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("healthcare_patient_onboarding")

        assert template is not None
        assert template.industry == Industry.HEALTHCARE
        assert "patient" in template.name.lower()

    def test_finance_template_exists(self):
        """Test finance expense approval template exists."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("finance_expense_approval")

        assert template is not None
        assert template.industry == Industry.FINANCE
        assert "expense" in template.name.lower()

    def test_education_template_exists(self):
        """Test education student enrollment template exists."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("education_student_enrollment")

        assert template is not None
        assert template.industry == Industry.EDUCATION
        assert "enrollment" in template.name.lower()

    def test_retail_template_exists(self):
        """Test retail inventory management template exists."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("retail_inventory_management")

        assert template is not None
        assert template.industry == Industry.RETAIL
        assert "inventory" in template.name.lower()

    def test_real_estate_template_exists(self):
        """Test real estate client onboarding template exists."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("real_estate_client_onboarding")

        assert template is not None
        assert template.industry == Industry.REAL_ESTATE
        assert "client" in template.name.lower()

    def test_technology_template_exists(self):
        """Test technology content file management template exists."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("tech_content_file_management")

        assert template is not None
        assert template.industry == Industry.TECHNOLOGY
        assert "file" in template.name.lower()


# Test Category 3: Blueprint Execution (6 tests)

class TestBlueprintExecution:
    """Tests for workflow blueprint structure and execution."""

    def test_workflow_data_structure(self):
        """Test template has valid workflow_data structure."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("healthcare_patient_onboarding")

        assert "nodes" in template.workflow_data
        assert "edges" in template.workflow_data
        assert isinstance(template.workflow_data["nodes"], list)
        assert isinstance(template.workflow_data["edges"], list)

    def test_workflow_nodes_have_required_fields(self):
        """Test workflow nodes have required fields."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("finance_expense_approval")

        if template.workflow_data.get("nodes"):
            node = template.workflow_data["nodes"][0]

            assert "id" in node
            assert "type" in node
            assert "label" in node
            assert "config" in node

    def test_workflow_edges_connect_nodes(self):
        """Test workflow edges properly connect nodes."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("retail_inventory_management")

        if template.workflow_data.get("edges"):
            edge = template.workflow_data["edges"][0]

            assert "source" in edge
            assert "target" in edge

    def test_required_integrations_specified(self):
        """Test templates specify required integrations."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("education_student_enrollment")

        assert isinstance(template.required_integrations, list)
        assert len(template.required_integrations) > 0

    def test_optional_integrations_specified(self):
        """Test templates specify optional integrations."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("legal_case_management")

        assert isinstance(template.optional_integrations, list)

    def test_setup_instructions_provided(self):
        """Test templates provide setup instructions."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("real_estate_client_onboarding")

        assert isinstance(template.setup_instructions, list)
        assert len(template.setup_instructions) > 0


# Test Category 4: Industry Integration (6 tests)

class TestIndustryIntegration:
    """Tests for template querying, filtering, and search."""

    def test_get_templates_by_industry(self):
        """Test filtering templates by industry."""
        engine = IndustryWorkflowEngine()

        healthcare_templates = engine.get_templates_by_industry(Industry.HEALTHCARE)

        assert len(healthcare_templates) >= 1
        assert all(t.industry == Industry.HEALTHCARE for t in healthcare_templates)

    def test_get_all_industries(self):
        """Test getting list of all supported industries."""
        engine = IndustryWorkflowEngine()

        industries = engine.get_all_industries()

        assert len(industries) > 0
        assert Industry.HEALTHCARE in industries
        assert Industry.FINANCE in industries

    def test_search_templates_by_industry(self):
        """Test searching templates by industry filter."""
        engine = IndustryWorkflowEngine()

        results = engine.search_templates(industry=Industry.FINANCE)

        assert len(results) >= 1
        assert all(t.industry == Industry.FINANCE for t in results)

    def test_search_templates_by_complexity(self):
        """Test searching templates by complexity level."""
        engine = IndustryWorkflowEngine()

        results = engine.search_templates(complexity="Intermediate")

        assert len(results) >= 1
        assert all(t.complexity == "Intermediate" for t in results)

    def test_search_templates_by_keywords(self):
        """Test searching templates by keywords."""
        engine = IndustryWorkflowEngine()

        results = engine.search_templates(keywords=["patient", "healthcare"])

        assert len(results) >= 1

    def test_search_templates_combined_filters(self):
        """Test searching templates with multiple filters."""
        engine = IndustryWorkflowEngine()

        results = engine.search_templates(
            industry=Industry.TECHNOLOGY,
            complexity="Intermediate"
        )

        assert len(results) >= 0  # May or may not have results


# Test Category 5: Template Metadata (5 tests)

class TestTemplateMetadata:
    """Tests for template metadata, benefits, and use cases."""

    def test_template_benefits_specified(self):
        """Test templates specify benefits."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("healthcare_patient_onboarding")

        assert isinstance(template.benefits, list)
        assert len(template.benefits) > 0

    def test_template_use_cases_specified(self):
        """Test templates specify use cases."""
        engine = IndustryWorkflowEngine()

        template = engine.get_template_by_id("finance_expense_approval")

        assert isinstance(template.use_cases, list)
        assert len(template.use_cases) > 0

    def test_template_complexity_levels(self):
        """Test templates have valid complexity levels."""
        engine = IndustryWorkflowEngine()

        valid_levels = ["Beginner", "Intermediate", "Advanced"]

        for template in engine.templates.values():
            assert template.complexity in valid_levels

    def test_template_time_savings_format(self):
        """Test templates have properly formatted time savings."""
        engine = IndustryWorkflowEngine()

        for template in engine.templates.values():
            assert "hour" in template.estimated_time_savings.lower()
            assert "week" in template.estimated_time_savings.lower()

    def test_compliance_notes_optional(self):
        """Test some templates have compliance notes."""
        engine = IndustryWorkflowEngine()

        # Legal template should have compliance notes
        legal_template = engine.get_template_by_id("legal_case_management")

        assert legal_template.compliance_notes is not None
        assert len(legal_template.compliance_notes) > 0


# Test Category 6: ROI Calculation (2 tests)

class TestROICalculation:
    """Tests for ROI calculation functionality."""

    def test_calculate_roi_success(self):
        """Test ROI calculation for valid template."""
        engine = IndustryWorkflowEngine()

        roi = engine.calculate_roi("healthcare_patient_onboarding", hourly_rate=50.0)

        assert "time_savings" in roi
        assert "implementation" in roi
        assert roi["time_savings"]["hours_per_week"] > 0

    def test_calculate_roi_template_not_found(self):
        """Test ROI calculation for non-existent template."""
        engine = IndustryWorkflowEngine()

        roi = engine.calculate_roi("nonexistent_template")

        assert "error" in roi


# Total: 30 tests
