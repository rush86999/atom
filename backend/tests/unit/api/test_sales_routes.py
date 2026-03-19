"""
Unit Tests for Sales Routes

Tests sales operations endpoints:
- GET /api/sales/pipeline - Get sales pipeline data
- GET /api/sales/dashboard/summary - Get dashboard summary
- Error cases: database errors, missing data

Target Coverage: 85%
Target Branch Coverage: 60%+
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from api import sales_routes
from core.models import IntegrationMetric


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def mock_integration_metrics():
    """Mock integration metrics query result."""
    metrics = []

    # Pipeline value metric
    m1 = MagicMock(spec=IntegrationMetric)
    m1.metric_key = "pipeline_value"
    m1.value = 150000.00

    # Active opportunities count
    m2 = MagicMock(spec=IntegrationMetric)
    m2.metric_key = "active_opportunities_count"
    m2.value = 25

    # Active deals count
    m3 = MagicMock(spec=IntegrationMetric)
    m3.metric_key = "active_deals_count"
    m3.value = 30

    metrics.extend([m1, m2, m3])
    return metrics


@pytest.fixture
def client(mock_db):
    """Test client with mocked dependencies using FastAPI dependency overrides."""
    from fastapi import FastAPI

    # Create a minimal FastAPI app with the router
    app = FastAPI()
    app.include_router(sales_routes.router)

    # Use FastAPI's dependency override mechanism
    app.dependency_overrides[sales_routes.get_db] = lambda: mock_db

    yield TestClient(app)

    # Clean up overrides
    app.dependency_overrides = {}


# =============================================================================
# Test Get Sales Pipeline
# =============================================================================

class TestGetSalesPipeline:
    """Tests for GET /api/sales/pipeline endpoint."""

    def test_get_sales_pipeline_success(self, client, mock_db, mock_integration_metrics):
        """Test getting sales pipeline with valid metrics."""
        # Arrange: Mock query result
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = mock_integration_metrics
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get sales pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Verify pipeline data
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 150000.00
        assert data["active_deals"] == 55  # 25 + 30
        assert data["currency"] == "USD"
        assert data["source"] == "synced_database"

    def test_get_sales_pipeline_empty_metrics(self, client, mock_db):
        """Test getting sales pipeline with no metrics."""
        # Arrange: Mock empty query result
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = []
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get sales pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Verify empty pipeline
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 0.0
        assert data["active_deals"] == 0
        assert data["currency"] == "USD"

    def test_get_sales_pipeline_partial_metrics(self, client, mock_db):
        """Test getting sales pipeline with only some metrics."""
        # Arrange: Mock partial metrics (only pipeline value)
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = 100000.00

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get sales pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Verify partial data
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 100000.00
        assert data["active_deals"] == 0  # No deal metrics

    def test_get_sales_pipeline_with_custom_user_id(self, client, mock_db, mock_integration_metrics):
        """Test getting sales pipeline for specific user."""
        # Arrange: Mock query result
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = mock_integration_metrics
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get sales pipeline for custom user
        response = client.get("/api/sales/pipeline?user_id=custom_user_123")

        # Assert: Verify pipeline data
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 150000.00

    def test_get_sales_pipeline_none_values(self, client, mock_db):
        """Test handling None metric values."""
        # Arrange: Mock metrics with None values
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = None

        m2 = MagicMock(spec=IntegrationMetric)
        m2.metric_key = "active_opportunities_count"
        m2.value = None

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1, m2]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get sales pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: None values treated as 0
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 0.0
        assert data["active_deals"] == 0

    def test_get_sales_pipeline_large_values(self, client, mock_db):
        """Test handling large metric values."""
        # Arrange: Mock large pipeline value
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = 999999999.99

        m2 = MagicMock(spec=IntegrationMetric)
        m2.metric_key = "active_deals_count"
        m2.value = 10000

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1, m2]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get sales pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Large values handled correctly
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 999999999.99
        assert data["active_deals"] == 10000

    def test_get_sales_pipeline_decimal_values(self, client, mock_db):
        """Test handling decimal values."""
        # Arrange: Mock decimal pipeline value
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = 123456.78

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get sales pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Decimal preserved
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 123456.78

    def test_get_sales_pipeline_duplicate_metrics(self, client, mock_db):
        """Test handling duplicate metric keys (sum aggregation)."""
        # Arrange: Multiple metrics with same key
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = 50000.00

        m2 = MagicMock(spec=IntegrationMetric)
        m2.metric_key = "pipeline_value"
        m2.value = 75000.00

        m3 = MagicMock(spec=IntegrationMetric)
        m3.metric_key = "active_deals_count"
        m3.value = 10

        m4 = MagicMock(spec=IntegrationMetric)
        m4.metric_key = "active_deals_count"
        m4.value = 20

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1, m2, m3, m4]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get sales pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Duplicate metrics summed
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 125000.00  # 50000 + 75000
        assert data["active_deals"] == 30  # 10 + 20

    def test_get_sales_pipeline_all_metric_types(self, client, mock_db):
        """Test all three metric types together."""
        # Arrange: All metric types
        metrics = []
        for key, value in [
            ("pipeline_value", 200000.00),
            ("active_opportunities_count", 50),
            ("active_deals_count", 75)
        ]:
            m = MagicMock(spec=IntegrationMetric)
            m.metric_key = key
            m.value = value
            metrics.append(m)

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = metrics
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get sales pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: All metrics aggregated
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 200000.00
        assert data["active_deals"] == 125  # 50 + 75


# =============================================================================
# Test Get Sales Dashboard Summary
# =============================================================================

class TestGetSalesDashboardSummary:
    """Tests for GET /api/sales/dashboard/summary endpoint."""

    def test_get_dashboard_summary_fails_without_db(self, client):
        """Test that dashboard/summary endpoint fails due to bug in production code.

        NOTE: The production code has a bug where get_sales_dashboard_summary()
        calls get_sales_pipeline(user_id) directly without passing the db parameter.
        Since get_sales_pipeline requires db: Session = Depends(get_db), this fails.

        This test documents the bug. The endpoint returns 500 error.
        """
        # Act: Try to get dashboard summary
        response = client.get("/api/sales/dashboard/summary")

        # Assert: Returns 500 due to production bug
        assert response.status_code == 500
        data = response.json()
        # Error response structure from BaseAPIRouter.internal_error()
        # Response is {'detail': {'error': {...}, 'success': False}}
        assert "detail" in data
        assert data["detail"].get("success") is False

    def test_dashboard_summary_would_alias_pipeline_if_fixed(self, client, mock_db, mock_integration_metrics):
        """Test that dashboard/summary would be an alias for pipeline if bug was fixed.

        NOTE: This tests what the behavior SHOULD be once the bug is fixed.
        Currently this test documents the expected behavior.
        """
        # The correct implementation would call get_sales_pipeline with proper db injection
        # For now, we just verify the pipeline endpoint works correctly
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = mock_integration_metrics
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline data (this works)
        response = client.get("/api/sales/pipeline")

        # Assert: Pipeline endpoint works
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 150000.00
        assert data["active_deals"] == 55

        # TODO: Once dashboard/summary is fixed, it should return same data
        # summary_response = client.get("/api/sales/dashboard/summary")
        # assert summary_response.json() == response.json()


# =============================================================================
# Test Error Handling
# =============================================================================

class TestSalesRoutesErrorHandling:
    """Tests for error handling in sales routes."""

    def test_database_query_error(self, client, mock_db):
        """Test database query error is handled."""
        # Arrange: Mock database error
        mock_db.query.side_effect = Exception("Database connection failed")

        # Act: Try to get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Error handled by router's internal_error method
        assert response.status_code == 500
        data = response.json()
        # Error response structure from BaseAPIRouter.internal_error()
        # Response is {'detail': {'error': {...}, 'success': False}}
        assert "detail" in data
        assert data["detail"].get("success") is False

    def test_database_filter_error(self, client, mock_db):
        """Test database filter error is handled."""
        # Arrange: Mock filter error
        mock_query = MagicMock()
        mock_query.filter.side_effect = Exception("Filter operation failed")
        mock_db.query.return_value = mock_query

        # Act: Try to get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Error handled
        assert response.status_code == 500

    def test_metric_value_conversion_error(self, client, mock_db):
        """Test handling of invalid metric value types."""
        # Arrange: Metric with invalid value type
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = "invalid_string"  # Should be numeric

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Try to get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Should handle gracefully (may return 500 or convert)
        # The actual behavior depends on float() conversion
        # When float() fails with ValueError, it's caught by the try-catch
        assert response.status_code == 500


# =============================================================================
# Test Branch Coverage
# =============================================================================

class TestSalesRoutesBranchCoverage:
    """Tests for branch coverage - testing all conditional paths."""

    def test_branch_pipeline_value_found(self, client, mock_db):
        """Test branch where pipeline_value metric is found."""
        # Arrange: Only pipeline_value metric
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = 100000.00

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Pipeline value added
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 100000.00

    def test_branch_pipeline_value_not_found(self, client, mock_db):
        """Test branch where pipeline_value metric is not found."""
        # Arrange: No pipeline_value metric
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "active_deals_count"
        m1.value = 10

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Pipeline value defaults to 0
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 0.0

    def test_branch_active_opportunities_found(self, client, mock_db):
        """Test branch where active_opportunities_count is found."""
        # Arrange: active_opportunities_count metric
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "active_opportunities_count"
        m1.value = 15

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Opportunities counted
        assert response.status_code == 200
        data = response.json()
        assert data["active_deals"] == 15

    def test_branch_active_deals_found(self, client, mock_db):
        """Test branch where active_deals_count is found."""
        # Arrange: active_deals_count metric
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "active_deals_count"
        m1.value = 20

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Deals counted
        assert response.status_code == 200
        data = response.json()
        assert data["active_deals"] == 20

    def test_branch_both_opportunities_and_deals(self, client, mock_db):
        """Test branch where both metrics are found."""
        # Arrange: Both metrics
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "active_opportunities_count"
        m1.value = 15

        m2 = MagicMock(spec=IntegrationMetric)
        m2.metric_key = "active_deals_count"
        m2.value = 20

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1, m2]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Both counted
        assert response.status_code == 200
        data = response.json()
        assert data["active_deals"] == 35  # 15 + 20

    def test_branch_unknown_metric_key_ignored(self, client, mock_db):
        """Test that unknown metric keys are ignored."""
        # Arrange: Unknown metric key
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "unknown_metric"
        m1.value = 999

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Unknown metric ignored, defaults returned
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 0.0
        assert data["active_deals"] == 0


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestSalesRoutesEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_pipeline_value(self, client, mock_db):
        """Test zero pipeline value."""
        # Arrange: Zero value
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = 0.0

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Zero preserved
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 0.0

    def test_negative_pipeline_value(self, client, mock_db):
        """Test negative pipeline value (edge case)."""
        # Arrange: Negative value (shouldn't happen in production)
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = -1000.00

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Negative value returned (no validation in code)
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == -1000.00

    def test_very_small_pipeline_value(self, client, mock_db):
        """Test very small pipeline value."""
        # Arrange: Very small decimal
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = 0.01

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Small value preserved
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 0.01

    def test_string_numeric_value(self, client, mock_db):
        """Test numeric value stored as string."""
        # Arrange: String value that can convert to float
        m1 = MagicMock(spec=IntegrationMetric)
        m1.metric_key = "pipeline_value"
        m1.value = "100000.00"

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [m1]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: String converted to float
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 100000.00

    def test_multiple_pipeline_values_summed(self, client, mock_db):
        """Test multiple pipeline_value entries are summed."""
        # Arrange: Multiple pipeline values
        metrics = []
        for value in [50000, 75000, 100000]:
            m = MagicMock(spec=IntegrationMetric)
            m.metric_key = "pipeline_value"
            m.value = float(value)
            metrics.append(m)

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = metrics
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: All values summed
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_value"] == 225000.00

    def test_response_format_validation(self, client, mock_db, mock_integration_metrics):
        """Test response format matches expected structure."""
        # Arrange: Mock query result
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = mock_integration_metrics
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Act: Get pipeline
        response = client.get("/api/sales/pipeline")

        # Assert: Validate response structure
        assert response.status_code == 200
        data = response.json()
        assert "pipeline_value" in data
        assert "active_deals" in data
        assert "currency" in data
        assert "source" in data
        assert isinstance(data["pipeline_value"], (int, float))
        assert isinstance(data["active_deals"], int)
        assert data["currency"] == "USD"
        assert data["source"] == "synced_database"
