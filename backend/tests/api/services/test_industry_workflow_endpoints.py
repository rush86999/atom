"""
Tests for Industry Workflow Endpoints

Tests for industry workflow API endpoints including:
- Getting supported industries
- Getting industry templates
- Template search
- ROI calculation
- Template recommendations
- Analytics
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def mock_app():
    """Create mock FastAPI app."""
    from fastapi import FastAPI
    app = FastAPI()

    # Mock router
    from core.industry_workflow_endpoints import router
    app.include_router(router)

    return app


@pytest.fixture
def client(mock_app):
    """Create test client."""
    return TestClient(mock_app)


@pytest.fixture
def mock_workflow_engine():
    """Mock industry workflow engine."""
    with patch('core.industry_workflow_endpoints.get_industry_workflow_engine') as mock:
        engine = MagicMock()
        mock.return_value = engine

        # Setup default returns
        engine.get_all_industries.return_value = []
        engine.get_templates_by_industry.return_value = []
        engine.get_template_by_id.return_value = None
        engine.search_templates.return_value = []
        engine.calculate_roi.return_value = {"monthly_savings": 100}

        yield engine


class TestGetSupportedIndustries:
    """Tests for GET /api/v1/industries endpoint."""

    def test_get_supported_industries_empty(self, client, mock_workflow_engine):
        """Test getting industries with no templates."""
        mock_workflow_engine.get_all_industries.return_value = []

        response = client.get("/api/v1/industries")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_industries"] == 0

    def test_get_supported_industries_with_templates(self, client, mock_workflow_engine):
        """Test getting industries with templates."""
        from core.industry_workflow_templates import Industry

        mock_template = MagicMock()
        mock_template.complexity = "Beginner"
        mock_template.estimated_time_savings = "5+ hours/week"

        mock_workflow_engine.get_all_industries.return_value = [Industry.HEALTHCARE]
        mock_workflow_engine.get_templates_by_industry.return_value = [mock_template]

        response = client.get("/api/v1/industries")

        assert response.status_code == 200
        data = response.json()
        assert "industries" in data
        assert data["total_industries"] == 1


class TestGetIndustryTemplates:
    """Tests for GET /api/v1/industries/{industry}/templates endpoint."""

    def test_get_industry_templates_basic(self, client, mock_workflow_engine):
        """Test getting templates for an industry."""
        mock_template = MagicMock()
        mock_template.id = "template-1"
        mock_template.name = "Test Template"
        mock_template.description = "Test description"
        mock_template.sub_category = "Testing"
        mock_template.complexity = "Beginner"
        mock_template.estimated_time_savings = "5+ hours/week"
        mock_template.required_integrations = ["slack"]
        mock_template.optional_integrations = []
        mock_template.benefits = ["Benefit 1", "Benefit 2"]
        mock_template.created_at = "2024-01-01"

        mock_workflow_engine.get_templates_by_industry.return_value = [mock_template]

        response = client.get("/api/v1/industries/healthcare/templates")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["templates"]) == 1
        assert data["templates"][0]["id"] == "template-1"

    def test_get_industry_templates_with_complexity_filter(self, client, mock_workflow_engine):
        """Test filtering templates by complexity."""
        beginner_template = MagicMock()
        beginner_template.complexity = "Beginner"
        beginner_template.id = "beginner-1"
        beginner_template.name = "Beginner Template"
        beginner_template.description = "Description"
        beginner_template.sub_category = "Test"
        beginner_template.estimated_time_savings = "5+ hours/week"
        beginner_template.required_integrations = []
        beginner_template.optional_integrations = []
        beginner_template.benefits = []
        beginner_template.created_at = "2024-01-01"

        advanced_template = MagicMock()
        advanced_template.complexity = "Advanced"
        advanced_template.id = "advanced-1"
        advanced_template.name = "Advanced Template"
        advanced_template.description = "Description"
        advanced_template.sub_category = "Test"
        advanced_template.estimated_time_savings = "10+ hours/week"
        advanced_template.required_integrations = []
        advanced_template.optional_integrations = []
        advanced_template.benefits = []
        advanced_template.created_at = "2024-01-01"

        mock_workflow_engine.get_templates_by_industry.return_value = [
            beginner_template,
            advanced_template
        ]

        response = client.get("/api/v1/industries/healthcare/templates?complexity=Beginner")

        assert response.status_code == 200
        data = response.json()
        assert len(data["templates"]) == 1
        assert data["templates"][0]["complexity"] == "Beginner"

    def test_get_industry_templates_invalid_industry(self, client, mock_workflow_engine):
        """Test getting templates for invalid industry."""
        response = client.get("/api/v1/industries/invalid_industry/templates")

        assert response.status_code == 404


class TestGetTemplateDetails:
    """Tests for GET /api/v1/templates/industry/{template_id} endpoint."""

    def test_get_template_details_found(self, client, mock_workflow_engine):
        """Test getting details for existing template."""
        mock_template = MagicMock()
        mock_template.id = "template-123"
        mock_template.name = "Test Template"
        mock_template.description = "Description"
        mock_template.industry.value = "healthcare"
        mock_template.sub_category = "Testing"
        mock_template.complexity = "Intermediate"
        mock_template.estimated_time_savings = "10+ hours/week"
        mock_template.required_integrations = ["slack", "gmail"]
        mock_template.optional_integrations = ["zoom"]
        mock_template.setup_instructions = ["Step 1", "Step 2"]
        mock_template.benefits = ["Benefit 1", "Benefit 2"]
        mock_template.use_cases = ["Use case 1"]
        mock_template.compliance_notes = "HIPAA compliant"
        mock_template.workflow_data = {"key": "value"}
        mock_template.created_at = "2024-01-01"

        mock_workflow_engine.get_template_by_id.return_value = mock_template

        response = client.get("/api/v1/templates/industry/template-123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["template"]["id"] == "template-123"
        assert data["template"]["compliance_notes"] == "HIPAA compliant"

    def test_get_template_details_not_found(self, client, mock_workflow_engine):
        """Test getting details for non-existent template."""
        mock_workflow_engine.get_template_by_id.return_value = None

        response = client.get("/api/v1/templates/industry/non-existent")

        assert response.status_code == 404


class TestSearchTemplates:
    """Tests for POST /api/v1/templates/search endpoint."""

    def test_search_templates_basic(self, client, mock_workflow_engine):
        """Test basic template search."""
        mock_template = MagicMock()
        mock_template.id = "search-result-1"
        mock_template.name = "Search Result"
        mock_template.description = "Found template"
        mock_template.industry.value = "healthcare"
        mock_template.sub_category = "Search"
        mock_template.complexity = "Beginner"
        mock_template.estimated_time_savings = "5+ hours/week"
        mock_template.required_integrations = []
        mock_template.benefits = ["Benefit 1", "Benefit 2", "Benefit 3"]
        mock_template.created_at = "2024-01-01"

        mock_workflow_engine.search_templates.return_value = [mock_template]

        request_body = {
            "industry": "healthcare",
            "complexity": "Beginner",
            "keywords": ["automation"]
        }

        response = client.post("/api/v1/templates/search", json=request_body)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["results"]) == 1
        assert data["search_criteria"]["industry"] == "healthcare"

    def test_search_templates_no_filters(self, client, mock_workflow_engine):
        """Test searching without filters."""
        mock_workflow_engine.search_templates.return_value = []

        request_body = {}

        response = client.post("/api/v1/templates/search", json=request_body)

        assert response.status_code == 200
        data = response.json()
        assert data["result_count"] == 0


class TestCalculateROI:
    """Tests for POST /api/v1/templates/{template_id}/roi endpoint."""

    def test_calculate_roi_basic(self, client, mock_workflow_engine):
        """Test basic ROI calculation."""
        mock_template = MagicMock()
        mock_template.id = "roi-template-1"
        mock_template.complexity = "Beginner"
        mock_template.benefits = ["Save time", "Reduce errors", "Improve accuracy"]
        mock_template.required_integrations = ["slack"]
        mock_template.optional_integrations = []

        mock_workflow_engine.get_template_by_id.return_value = mock_template
        mock_workflow_engine.calculate_roi.return_value = {
            "monthly_savings_hours": 10,
            "monthly_savings_currency": 500,
            "annual_savings_currency": 6000
        }

        request_body = {
            "template_id": "roi-template-1",
            "hourly_rate": 50.0
        }

        response = client.post("/api/v1/templates/roi-template-1/roi", json=request_body)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "roi_analysis" in data
        assert "insights" in data
        assert data["hourly_rate_used"] == 50.0

    def test_calculate_roi_template_not_found(self, client, mock_workflow_engine):
        """Test ROI calculation for non-existent template."""
        mock_workflow_engine.get_template_by_id.return_value = None

        request_body = {
            "template_id": "non-existent",
            "hourly_rate": 50.0
        }

        response = client.post("/api/v1/templates/non-existent/roi", json=request_body)

        assert response.status_code == 404


class TestGetRecommendations:
    """Tests for GET /api/v1/templates/recommendations endpoint."""

    def test_get_recommendations_basic(self, client, mock_workflow_engine):
        """Test getting template recommendations."""
        mock_template = MagicMock()
        mock_template.id = "rec-1"
        mock_template.name = "Recommended Template"
        mock_template.description = "Highly recommended"
        mock_template.industry.value = "healthcare"
        mock_template.complexity = "Beginner"
        mock_template.estimated_time_savings = "10+ hours/week"
        mock_template.required_integrations = ["slack"]
        mock_template.benefits = ["Benefit 1", "Benefit 2", "Benefit 3"]

        mock_workflow_engine.templates.values.return_value = [mock_template]

        response = client.get("/api/v1/templates/recommendations?industry=healthcare&company_size=small")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "recommendations" in data
        assert "criteria" in data

    def test_get_recommendations_with_integrations(self, client, mock_workflow_engine):
        """Test recommendations with current integrations."""
        mock_template = MagicMock()
        mock_template.id = "rec-2"
        mock_template.name = "Integration Match"
        mock_template.description = "Matches your integrations"
        mock_template.industry.value = "technology"
        mock_template.complexity = "Intermediate"
        mock_template.estimated_time_savings = "5+ hours/week"
        mock_template.required_integrations = ["slack", "gmail"]
        mock_template.benefits = ["Benefit 1", "Benefit 2"]

        mock_workflow_engine.templates.values.return_value = [mock_template]

        response = client.get("/api/v1/templates/recommendations?current_integrations=slack,gmail")

        assert response.status_code == 200
        data = response.json()
        assert len(data["criteria"]["current_integrations"]) == 2


class TestGetIndustryAnalytics:
    """Tests for GET /api/v1/templates/industry-analytics endpoint."""

    def test_get_industry_analytics(self, client, mock_workflow_engine):
        """Test getting industry analytics."""
        from core.industry_workflow_templates import Industry

        mock_template = MagicMock()
        mock_template.complexity = "Beginner"
        mock_template.sub_category = "Automation"
        mock_template.required_integrations = ["slack", "gmail"]
        mock_template.estimated_time_savings = "10 hours/week"

        mock_workflow_engine.get_all_industries.return_value = [Industry.HEALTHCARE, Industry.TECHNOLOGY]
        mock_workflow_engine.get_templates_by_industry.return_value = [mock_template]

        response = client.get("/api/v1/templates/industry-analytics")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "analytics" in data
        assert "industry_distribution" in data["analytics"]
        assert "complexity_distribution" in data["analytics"]
        assert "top_integrations" in data["analytics"]


class TestGetImplementationGuide:
    """Tests for GET /api/v1/templates/implementation-guide/{template_id} endpoint."""

    def test_get_implementation_guide(self, client, mock_workflow_engine):
        """Test getting implementation guide."""
        mock_template = MagicMock()
        mock_template.id = "impl-guide-1"
        mock_template.name = "Template with Guide"
        mock_template.industry.value = "healthcare"
        mock_template.complexity = "Intermediate"
        mock_template.required_integrations = ["slack"]
        mock_template.optional_integrations = ["zoom"]
        mock_template.setup_instructions = ["Step 1: Configure", "Step 2: Test"]
        mock_template.compliance_notes = "HIPAA compliant"

        mock_workflow_engine.get_template_by_id.return_value = mock_template

        response = client.get("/api/v1/templates/implementation-guide/impl-guide-1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "implementation_guide" in data
        assert "prerequisites" in data["implementation_guide"]
        assert "step_by_step_setup" in data["implementation_guide"]
        assert "post_implementation" in data["implementation_guide"]

    def test_get_implementation_guide_not_found(self, client, mock_workflow_engine):
        """Test getting guide for non-existent template."""
        mock_workflow_engine.get_template_by_id.return_value = None

        response = client.get("/api/v1/templates/implementation-guide/non-existent")

        assert response.status_code == 404


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_extract_hours_from_savings(self):
        """Test extracting hours from savings text."""
        from core.industry_workflow_endpoints import _extract_hours_from_savings

        result = _extract_hours_from_savings("10 hours/week")
        assert result == 10.0

        result = _extract_hours_from_savings("5+ hours weekly")
        assert result == 5.0

        result = _extract_hours_from_savings("No savings")
        assert result is None

    def test_calculate_avg_savings(self, mock_workflow_engine):
        """Test calculating average time savings."""
        from core.industry_workflow_endpoints import _calculate_avg_savings

        template1 = MagicMock()
        template1.estimated_time_savings = "10 hours/week"

        template2 = MagicMock()
        template2.estimated_time_savings = "5 hours/week"

        result = _calculate_avg_savings([template1, template2])

        assert "7.5" in result

    def test_get_integration_setup_details(self):
        """Test getting integration setup details."""
        from core.industry_workflow_endpoints import _get_integration_setup_details

        result = _get_integration_setup_details(["slack", "custom"])

        assert "slack" in result
        assert "custom" in result
        assert len(result["slack"]) > 0
        assert len(result["custom"]) > 0
