"""
Industry Workflow Endpoints Coverage Tests

Comprehensive TestClient-based tests for industry workflow API endpoints to achieve 60%+ coverage.

Coverage Target:
- core/industry_workflow_endpoints.py - 60%+ coverage (109+ lines)

Test Classes:
- TestIndustryWorkflowEndpoints (10 tests): Industry templates, vertical workflows
- TestIndustryTemplates (12 tests): Healthcare, finance, manufacturing, retail templates
- TestIndustryWorkflows (8 tests): Vertical-specific execution, compliance checks
- TestIndustryErrors (5 tests): Invalid vertical, missing templates, compliance failures

Baseline: 0% coverage (industry_workflow_endpoints.py not tested)
Target: 60%+ coverage (109+ lines)
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


# Import industry workflow router
from core.industry_workflow_endpoints import router as industry_router
from core.industry_workflow_templates import Industry, IndustryWorkflowEngine


# Create minimal FastAPI app for testing industry workflow routes
app = FastAPI()
app.include_router(industry_router, tags=["industry"])


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def industry_test_client():
    """Create TestClient for industry workflow routes testing."""
    return TestClient(app)


@pytest.fixture(scope="function")
def mock_workflow_engine():
    """Create mock industry workflow engine."""
    engine = MagicMock(spec=IndustryWorkflowEngine)

    # Mock get_all_industries
    engine.get_all_industries.return_value = [
        Industry.HEALTHCARE,
        Industry.FINANCE,
        Industry.RETAIL,
        Industry.MANUFACTURING
    ]

    # Mock get_templates_by_industry
    def mock_get_templates(industry):
        templates = []
        if industry == Industry.HEALTHCARE:
            templates = [
                MagicMock(
                    id="hc-patient-reminder",
                    name="Patient Appointment Reminder",
                    description="Automated appointment reminders",
                    industry=Industry.HEALTHCARE,
                    sub_category="Patient Management",
                    complexity="Beginner",
                    estimated_time_savings="5+ hours/week",
                    required_integrations=["gmail"],
                    optional_integrations=["slack"],
                    benefits=["Reduces no-shows", "Saves staff time", "Improves patient satisfaction"],
                    use_cases=["Clinics", "Hospitals", "Dental offices"],
                    compliance_notes="HIPAA compliant",
                    created_at=datetime.now(timezone.utc)
                )
            ]
        elif industry == Industry.FINANCE:
            templates = [
                MagicMock(
                    id="fin-invoice-automation",
                    name="Invoice Processing Automation",
                    description="Automated invoice processing",
                    industry=Industry.FINANCE,
                    sub_category="Accounts Payable",
                    complexity="Intermediate",
                    estimated_time_savings="10+ hours/week",
                    required_integrations=["quickbooks", "gmail"],
                    optional_integrations=["slack"],
                    benefits=["Faster processing", "Fewer errors", "Cost savings"],
                    use_cases=["Small business", "Accounting firms"],
                    compliance_notes=None,
                    created_at=datetime.now(timezone.utc)
                )
            ]
        return templates

    engine.get_templates_by_industry.side_effect = mock_get_templates

    # Mock get_template_by_id
    engine.get_template_by_id.return_value = MagicMock(
        id="hc-patient-reminder",
        name="Patient Appointment Reminder",
        description="Automated appointment reminders",
        industry=Industry.HEALTHCARE,
        sub_category="Patient Management",
        complexity="Beginner",
        estimated_time_savings="5+ hours/week",
        required_integrations=["gmail"],
        optional_integrations=["slack"],
        benefits=["Reduces no-shows", "Saves staff time", "Improves patient satisfaction"],
        use_cases=["Clinics", "Hospitals"],
        compliance_notes="HIPAA compliant",
        setup_instructions=["Step 1", "Step 2", "Step 3"],
        created_at=datetime.now(timezone.utc)
    )

    # Mock search_templates
    engine.search_templates.return_value = []

    # Mock calculate_roi
    engine.calculate_roi.return_value = {
        "time_savings_hours": 5.0,
        "weekly_savings": 250.0,
        "monthly_savings": 1000.0,
        "annual_savings": 12000.0
    }

    return engine


# ============================================================================
# Test Class: TestIndustryWorkflowEndpoints
# ============================================================================

class TestIndustryWorkflowEndpoints:
    """Tests for industry workflow endpoints."""

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_supported_industries(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting list of supported industries."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/industries")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "industries" in data
        assert data["total_industries"] == 4

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_industry_templates_healthcare(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting healthcare industry templates."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/industries/healthcare/templates")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["industry"] == "healthcare"
        assert len(data["templates"]) > 0

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_industry_templates_with_complexity_filter(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting industry templates with complexity filter."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get(
            "/api/v1/industries/healthcare/templates",
            params={"complexity": "Beginner"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_industry_templates_invalid_industry(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting templates for invalid industry."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/industries/invalid/templates")

        assert response.status_code == 404

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_industry_template_details(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting detailed template information."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/industry/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["template"]["id"] == "hc-patient-reminder"

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_template_details_not_found(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting details of non-existent template."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.get_template_by_id.return_value = None

        response = industry_test_client.get("/api/v1/templates/industry/nonexistent")

        assert response.status_code == 404

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_search_industry_templates_no_filters(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test searching templates without filters."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.search_templates.return_value = []

        response = industry_test_client.post(
            "/api/v1/templates/search",
            json={}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_search_industry_templates_with_industry_filter(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test searching templates with industry filter."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.search_templates.return_value = []

        response = industry_test_client.post(
            "/api/v1/templates/search",
            json={"industry": "healthcare"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["search_criteria"]["industry"] == "healthcare"

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_search_industry_templates_with_keywords(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test searching templates with keywords."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.search_templates.return_value = []

        response = industry_test_client.post(
            "/api/v1/templates/search",
            json={"keywords": ["appointment", "reminder"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["search_criteria"]["keywords"] == ["appointment", "reminder"]

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_calculate_template_roi(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test calculating template ROI."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.post(
            "/api/v1/templates/hc-patient-reminder/roi",
            json={"hourly_rate": 50.0}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "roi_analysis" in data


# ============================================================================
# Test Class: TestIndustryTemplates
# ============================================================================

class TestIndustryTemplates:
    """Tests for industry-specific templates."""

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_healthcare_template_benefits(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test healthcare template benefits."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/industry/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        template = data["template"]
        assert "benefits" in template
        assert len(template["benefits"]) > 0

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_healthcare_template_compliance(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test healthcare template compliance notes."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/industry/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        template = data["template"]
        assert template["compliance_notes"] == "HIPAA compliant"

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_finance_template_complexity(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test finance template complexity level."""
        mock_get_engine.return_value = mock_workflow_engine

        # Return finance template
        finance_template = MagicMock(
            id="fin-invoice-automation",
            name="Invoice Processing Automation",
            description="Automated invoice processing",
            industry=Industry.FINANCE,
            sub_category="Accounts Payable",
            complexity="Intermediate",
            estimated_time_savings="10+ hours/week",
            required_integrations=["quickbooks", "gmail"],
            optional_integrations=["slack"],
            benefits=["Faster processing", "Fewer errors", "Cost savings"],
            use_cases=["Small business", "Accounting firms"],
            compliance_notes=None,
            created_at=datetime.now(timezone.utc)
        )
        mock_workflow_engine.get_template_by_id.return_value = finance_template

        response = industry_test_client.get("/api/v1/templates/industry/fin-invoice-automation")

        assert response.status_code == 200
        data = response.json()
        assert data["template"]["complexity"] == "Intermediate"

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_finance_template_integrations(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test finance template required integrations."""
        mock_get_engine.return_value = mock_workflow_engine

        finance_template = MagicMock(
            id="fin-invoice-automation",
            required_integrations=["quickbooks", "gmail"],
            optional_integrations=["slack"],
            industry=Industry.FINANCE,
            complexity="Intermediate",
            estimated_time_savings="10+ hours/week",
            created_at=datetime.now(timezone.utc)
        )
        mock_workflow_engine.get_template_by_id.return_value = finance_template

        response = industry_test_client.get("/api/v1/templates/industry/fin-invoice-automation")

        assert response.status_code == 200
        data = response.json()
        assert "quickbooks" in data["template"]["required_integrations"]
        assert "gmail" in data["template"]["required_integrations"]

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_retail_template_time_savings(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test retail template time savings estimate."""
        mock_get_engine.return_value = mock_workflow_engine

        retail_template = MagicMock(
            id="ret-inventory-sync",
            name="Inventory Synchronization",
            industry=Industry.RETAIL,
            estimated_time_savings="10+ hours/week",
            created_at=datetime.now(timezone.utc)
        )
        mock_workflow_engine.get_template_by_id.return_value = retail_template

        response = industry_test_client.get("/api/v1/templates/industry/ret-inventory-sync")

        assert response.status_code == 200
        data = response.json()
        assert "10+ hours/week" in data["template"]["estimated_time_savings"]

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_manufacturing_template_use_cases(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test manufacturing template use cases."""
        mock_get_engine.return_value = mock_workflow_engine

        mfg_template = MagicMock(
            id="mfg-production-tracking",
            name="Production Tracking",
            industry=Industry.MANUFACTURING,
            use_cases=["Assembly lines", "Quality control", "Inventory management"],
            created_at=datetime.now(timezone.utc)
        )
        mock_workflow_engine.get_template_by_id.return_value = mfg_template

        response = industry_test_client.get("/api/v1/templates/industry/mfg-production-tracking")

        assert response.status_code == 200
        data = response.json()
        assert len(data["template"]["use_cases"]) == 3

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_template_sub_category(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test template sub-category field."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/industry/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        assert data["template"]["sub_category"] == "Patient Management"

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_beginner_complexity_template(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test beginner complexity template."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/industry/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        assert data["template"]["complexity"] == "Beginner"

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_intermediate_complexity_template(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test intermediate complexity template."""
        mock_get_engine.return_value = mock_workflow_engine

        finance_template = MagicMock(
            id="fin-invoice-automation",
            complexity="Intermediate",
            industry=Industry.FINANCE,
            created_at=datetime.now(timezone.utc)
        )
        mock_workflow_engine.get_template_by_id.return_value = finance_template

        response = industry_test_client.get("/api/v1/templates/industry/fin-invoice-automation")

        assert response.status_code == 200
        data = response.json()
        assert data["template"]["complexity"] == "Intermediate"

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_advanced_complexity_template(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test advanced complexity template."""
        mock_get_engine.return_value = mock_workflow_engine

        adv_template = MagicMock(
            id="adv-workflow",
            complexity="Advanced",
            industry=Industry.MANUFACTURING,
            created_at=datetime.now(timezone.utc)
        )
        mock_workflow_engine.get_template_by_id.return_value = adv_template

        response = industry_test_client.get("/api/v1/templates/industry/adv-workflow")

        assert response.status_code == 200
        data = response.json()
        assert data["template"]["complexity"] == "Advanced"

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_required_integrations_validation(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test required integrations are present."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/industry/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        assert len(data["template"]["required_integrations"]) > 0


# ============================================================================
# Test Class: TestIndustryWorkflows
# ============================================================================

class TestIndustryWorkflows:
    """Tests for industry-specific workflow execution."""

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_template_recommendations_small_business(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting recommendations for small business."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.templates = {}

        response = industry_test_client.get(
            "/api/v1/templates/recommendations",
            params={"company_size": "small"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "recommendations" in data

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_template_recommendations_with_integrations(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting recommendations with current integrations."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.templates = {}

        response = industry_test_client.get(
            "/api/v1/templates/recommendations",
            params={"current_integrations": "gmail,slack"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "criteria" in data
        assert "gmail" in data["criteria"]["current_integrations"]

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_industry_analytics(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting industry analytics."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.templates = {}

        response = industry_test_client.get("/api/v1/templates/industry-analytics")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "analytics" in data

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_industry_analytics_complexity_distribution(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test industry analytics complexity distribution."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.templates = {}

        response = industry_test_client.get("/api/v1/templates/industry-analytics")

        assert response.status_code == 200
        data = response.json()
        analytics = data["analytics"]
        assert "complexity_distribution" in analytics
        assert "Beginner" in analytics["complexity_distribution"]

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_implementation_guide(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting implementation guide."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/implementation-guide/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "implementation_guide" in data

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_implementation_guide_prerequisites(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test implementation guide prerequisites section."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/implementation-guide/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        guide = data["implementation_guide"]
        assert "prerequisites" in guide
        assert "required_integrations" in guide["prerequisites"]

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_implementation_guide_setup_steps(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test implementation guide setup steps."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/implementation-guide/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        guide = data["implementation_guide"]
        assert "step_by_step_setup" in guide

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_implementation_guide_compliance_requirements(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test implementation guide includes compliance."""
        mock_get_engine.return_value = mock_workflow_engine

        response = industry_test_client.get("/api/v1/templates/implementation-guide/hc-patient-reminder")

        assert response.status_code == 200
        data = response.json()
        guide = data["implementation_guide"]
        # Healthcare templates should have compliance section
        assert "compliance_requirements" in guide


# ============================================================================
# Test Class: TestIndustryErrors
# ============================================================================

class TestIndustryErrors:
    """Tests for industry workflow error handling."""

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_search_templates_invalid_industry(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test searching with invalid industry."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.search_templates.side_effect = ValueError("Invalid industry")

        response = industry_test_client.post(
            "/api/v1/templates/search",
            json={"industry": "invalid"}
        )

        assert response.status_code == 400

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_calculate_roi_template_not_found(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test calculating ROI for non-existent template."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.calculate_roi.return_value = {"error": "Template not found"}
        mock_workflow_engine.get_template_by_id.return_value = None

        response = industry_test_client.post(
            "/api/v1/templates/nonexistent/roi",
            json={"hourly_rate": 50.0}
        )

        assert response.status_code == 400

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_implementation_guide_template_not_found(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test getting implementation guide for non-existent template."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_workflow_engine.get_template_by_id.return_value = None

        response = industry_test_client.get("/api/v1/templates/implementation-guide/nonexistent")

        assert response.status_code == 404

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_industry_analytics_exception(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test industry analytics exception handling."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_get_engine.side_effect = Exception("Analytics engine error")

        response = industry_test_client.get("/api/v1/templates/industry-analytics")

        assert response.status_code == 500

    @patch("core.industry_workflow_endpoints.get_industry_workflow_engine")
    def test_get_recommendations_exception(
        self, mock_get_engine, industry_test_client, mock_workflow_engine
    ):
        """Test recommendations endpoint exception handling."""
        mock_get_engine.return_value = mock_workflow_engine
        mock_get_engine.side_effect = Exception("Recommendation engine error")

        response = industry_test_client.get("/api/v1/templates/recommendations")

        assert response.status_code == 500
