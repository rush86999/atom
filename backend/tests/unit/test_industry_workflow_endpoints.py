"""
Unit tests for Industry Workflow Endpoints

Tests core/industry_workflow_endpoints.py (181 lines, zero coverage)
Covers industry-specific workflow templates, ROI calculations, and recommendations
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.industry_workflow_endpoints import router
from core.industry_workflow_templates import (
    Industry,
    IndustryWorkflowTemplate,
    IndustryWorkflowEngine,
)


# Create test app
app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_template():
    """Create mock industry template"""
    template = MagicMock(spec=IndustryWorkflowTemplate)
    template.id = "test_template_1"
    template.name = "Invoice Processing Automation"
    template.description = "Automate invoice processing workflows"
    template.industry = Industry.HEALTHCARE
    template.sub_category = "Billing"
    template.complexity = "Intermediate"
    template.estimated_time_savings = "10+ hours/week"
    template.required_integrations = ["quickbooks", "gmail"]
    template.optional_integrations = ["slack"]
    template.benefits = [
        "Reduce manual data entry",
        "Improve accuracy",
        "Faster processing"
    ]
    template.use_cases = ["Accounts payable", "Expense tracking"]
    template.compliance_notes = None
    template.setup_instructions = ["Step 1", "Step 2"]
    template.workflow_data = {}
    template.created_at = datetime.now(timezone.utc)
    return template


@pytest.fixture
def mock_engine():
    """Create mock industry workflow engine"""
    engine = MagicMock(spec=IndustryWorkflowEngine)
    return engine


# ==================== Industry Endpoints Tests ====================

class TestIndustryEndpoints:
    """Tests for industry listing and template retrieval"""

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_supported_industries_success(self, mock_get_engine, client, mock_engine, mock_template):
        """Test getting list of supported industries"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_all_industries.return_value = [Industry.HEALTHCARE, Industry.FINANCE]
        mock_engine.get_templates_by_industry.return_value = [mock_template]

        response = client.get("/api/v1/industries")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "industries" in data
        assert "total_industries" in data

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_industry_templates_success(self, mock_get_engine, client, mock_engine, mock_template):
        """Test getting templates for a specific industry"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_templates_by_industry.return_value = [mock_template]

        response = client.get("/api/v1/industries/healthcare/templates")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "templates" in data
        assert data["industry"] == "healthcare"

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_industry_templates_with_complexity_filter(self, mock_get_engine, client, mock_engine, mock_template):
        """Test filtering templates by complexity"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_templates_by_industry.return_value = [mock_template]

        response = client.get(
            "/api/v1/industries/healthcare/templates",
            params={"complexity": "Intermediate"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "templates" in data

    def test_get_industry_templates_not_found(self, client):
        """Test requesting templates for non-existent industry"""
        response = client.get("/api/v1/industries/nonexistent/templates")

        assert response.status_code == 404

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_industry_template_details_success(self, mock_get_engine, client, mock_engine, mock_template):
        """Test getting detailed template information"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_template_by_id.return_value = mock_template

        response = client.get("/api/v1/templates/industry/test_template_1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "template" in data
        assert data["template"]["id"] == "test_template_1"

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_template_details_not_found(self, mock_get_engine, client, mock_engine):
        """Test getting details for non-existent template"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_template_by_id.return_value = None

        response = client.get("/api/v1/templates/industry/nonexistent")

        assert response.status_code == 404


# ==================== Template Search Tests ====================

class TestTemplateSearch:
    """Tests for template search functionality"""

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_search_industry_templates_success(self, mock_get_engine, client, mock_engine, mock_template):
        """Test searching templates with filters"""
        mock_get_engine.return_value = mock_engine
        mock_engine.search_templates.return_value = [mock_template]

        response = client.post(
            "/api/v1/templates/search",
            json={
                "industry": "healthcare",
                "complexity": "Intermediate",
                "keywords": ["automation", "billing"]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "results" in data
        assert "search_criteria" in data

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_search_templates_no_results(self, mock_get_engine, client, mock_engine):
        """Test search with no matching results"""
        mock_get_engine.return_value = mock_engine
        mock_engine.search_templates.return_value = []

        response = client.post(
            "/api/v1/templates/search",
            json={"industry": "manufacturing"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result_count"] == 0


# ==================== ROI Calculation Tests ====================

class TestROICalculation:
    """Tests for ROI calculation endpoints"""

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_calculate_template_roi_success(self, mock_get_engine, client, mock_engine, mock_template):
        """Test calculating ROI for a template"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_template_by_id.return_value = mock_template
        mock_engine.calculate_roi.return_value = {
            "time_savings_hours_per_week": 10,
            "cost_savings_per_month": 2000,
            "payback_period_weeks": 2
        }

        response = client.post(
            "/api/v1/templates/test_template_1/roi",
            json={"hourly_rate": 50.0}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "roi_analysis" in data
        assert data["hourly_rate_used"] == 50.0

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_calculate_roi_template_not_found(self, mock_get_engine, client, mock_engine):
        """Test calculating ROI for non-existent template"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_template_by_id.return_value = None
        mock_engine.calculate_roi.return_value = {
            "error": "Template not found"
        }

        response = client.post(
            "/api/v1/templates/nonexistent/roi",
            json={"hourly_rate": 50.0}
        )

        assert response.status_code == 400


# ==================== Recommendation Tests ====================

class TestRecommendations:
    """Tests for template recommendation endpoints"""

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_template_recommendations_success(self, mock_get_engine, client, mock_engine, mock_template):
        """Test getting personalized template recommendations"""
        mock_get_engine.return_value = mock_engine
        mock_engine.templates = {"test_template_1": mock_template}

        response = client.get(
            "/api/v1/templates/recommendations",
            params={
                "industry": "healthcare",
                "company_size": "medium",
                "current_integrations": "gmail,slack"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "recommendations" in data
        assert "criteria" in data

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_recommendations_no_filters(self, mock_get_engine, client, mock_engine):
        """Test getting recommendations without filters"""
        mock_get_engine.return_value = mock_engine
        mock_engine.templates = {}

        response = client.get("/api/v1/templates/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ==================== Analytics Tests ====================

class TestIndustryAnalytics:
    """Tests for industry analytics endpoints"""

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_industry_analytics_success(self, mock_get_engine, client, mock_engine, mock_template):
        """Test getting industry template analytics"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_all_industries.return_value = [Industry.HEALTHCARE, Industry.FINANCE]
        mock_engine.get_templates_by_industry.return_value = [mock_template]

        response = client.get("/api/v1/templates/industry-analytics")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "analytics" in data
        assert "industry_distribution" in data["analytics"]


# ==================== Implementation Guide Tests ====================

class TestImplementationGuide:
    """Tests for implementation guide endpoints"""

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_implementation_guide_success(self, mock_get_engine, client, mock_engine, mock_template):
        """Test getting implementation guide for a template"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_template_by_id.return_value = mock_template

        response = client.get("/api/v1/templates/implementation-guide/test_template_1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "implementation_guide" in data
        assert "template_info" in data["implementation_guide"]
        assert "prerequisites" in data["implementation_guide"]

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_get_implementation_guide_not_found(self, mock_get_engine, client, mock_engine):
        """Test getting implementation guide for non-existent template"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_template_by_id.return_value = None

        response = client.get("/api/v1/templates/implementation-guide/nonexistent")

        assert response.status_code == 404


# ==================== Error Handling Tests ====================

class TestErrorHandling:
    """Tests for error handling"""

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_search_with_invalid_industry(self, mock_get_engine, client, mock_engine):
        """Test search with invalid industry (raises ValueError)"""
        mock_get_engine.return_value = mock_engine
        mock_engine.search_templates.side_effect = ValueError("Invalid industry")

        response = client.post(
            "/api/v1/templates/search",
            json={"industry": "invalid_industry_value"}
        )

        # Should return 400 for bad request
        assert response.status_code == 400

    @patch('core.industry_workflow_endpoints.get_industry_workflow_engine')
    def test_endpoint_exception_handling(self, mock_get_engine, client, mock_engine):
        """Test general exception handling in endpoints"""
        mock_get_engine.return_value = mock_engine
        mock_engine.get_all_industries.side_effect = Exception("Unexpected error")

        response = client.get("/api/v1/industries")

        # Should return 500 for server error
        assert response.status_code == 500


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
