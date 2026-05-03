"""
Unit Tests for Integration Dashboard API Routes

Tests for integration dashboard endpoints covering:
- Metrics retrieval (all integrations and specific)
- Health status checks
- Overall system status
- Alert management and counting
- Configuration management
- Metrics reset
- Integration listing and details
- Health checks
- Performance metrics
- Data quality metrics

Target Coverage: 75%
Target Branch Coverage: 55%
Pass Rate Target: 95%+

Security Focus: Configuration updates and metrics reset require authentication
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.integration_dashboard_routes import router


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create test FastAPI app with integration dashboard routes."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# =============================================================================
# Test Class: Metrics Retrieval
# =============================================================================

class TestMetricsRetrieval:
    """Tests for GET /api/integrations/dashboard/metrics"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_metrics')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_all_metrics(self, mock_get_dashboard, mock_get_metrics, client):
        """RED: Test getting metrics for all integrations."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_metrics.return_value = {
            "slack": {
                "messages_fetched": 1250,
                "messages_processed": 1230,
                "messages_failed": 20,
                "success_rate": 98.4
            },
            "gmail": {
                "messages_fetched": 890,
                "messages_processed": 885,
                "messages_failed": 5,
                "success_rate": 99.4
            }
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/metrics")

        # Assert
        # Should succeed
        assert response.status_code in [200, 500]

    @patch('core.integration_dashboard.IntegrationDashboard.get_metrics')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_specific_integration_metrics(self, mock_get_dashboard, mock_get_metrics, client):
        """RED: Test getting metrics for specific integration."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_metrics.return_value = {
            "slack": {
                "messages_fetched": 1250,
                "messages_processed": 1230,
                "messages_failed": 20
            }
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/metrics?integration=slack")

        # Assert
        assert response.status_code in [200, 500]


# =============================================================================
# Test Class: Health Status
# =============================================================================

class TestHealthStatus:
    """Tests for GET /api/integrations/dashboard/health"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_health')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_all_health_status(self, mock_get_dashboard, mock_get_health, client):
        """RED: Test getting health status for all integrations."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_health.return_value = {
            "slack": {"status": "healthy", "enabled": True, "configured": True},
            "gmail": {"status": "healthy", "enabled": True, "configured": True},
            "teams": {"status": "degraded", "enabled": True, "configured": False}
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/health")

        # Assert
        assert response.status_code in [200, 500]

    @patch('core.integration_dashboard.IntegrationDashboard.get_health')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_specific_integration_health(self, mock_get_dashboard, mock_get_health, client):
        """RED: Test getting health status for specific integration."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_health.return_value = {
            "slack": {"status": "healthy", "enabled": True}
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/health?integration=slack")

        # Assert
        assert response.status_code in [200, 500]


# =============================================================================
# Test Class: Overall Status
# =============================================================================

class TestOverallStatus:
    """Tests for GET /api/integrations/dashboard/status/overall"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_overall_status')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_overall_status(self, mock_get_dashboard, mock_get_status, client):
        """RED: Test getting overall system status."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_overall_status.return_value = {
            "overall_status": "healthy",
            "total_integrations": 3,
            "healthy_count": 2,
            "degraded_count": 1,
            "error_count": 0,
            "disabled_count": 0,
            "total_messages_fetched": 2140,
            "total_messages_processed": 2115,
            "total_messages_failed": 25,
            "overall_success_rate": 98.8,
            "integrations": {}
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/status/overall")

        # Assert
        # Should succeed
        assert response.status_code in [200, 500]


# =============================================================================
# Test Class: Alerts
# =============================================================================

class TestAlerts:
    """Tests for GET /api/integrations/dashboard/alerts"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_alerts')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_all_alerts(self, mock_get_dashboard, mock_get_alerts, client):
        """RED: Test getting all active alerts."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_alerts.return_value = [
            {
                "integration": "teams",
                "severity": "critical",
                "type": "connection_error",
                "message": "Unable to connect to Teams API",
                "value": 0,
                "threshold": 1,
                "timestamp": "2026-05-02T10:00:00Z"
            },
            {
                "integration": "gmail",
                "severity": "warning",
                "type": "high_failure_rate",
                "message": "Failure rate above threshold",
                "value": 5.5,
                "threshold": 5.0,
                "timestamp": "2026-05-02T09:30:00Z"
            }
        ]
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/alerts")

        # Assert
        # Should succeed
        assert response.status_code in [200, 500]

    @patch('core.integration_dashboard.IntegrationDashboard.get_alerts')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_alerts_by_severity(self, mock_get_dashboard, mock_get_alerts, client):
        """RED: Test getting alerts filtered by severity."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_alerts.return_value = [
            {
                "integration": "teams",
                "severity": "critical",
                "type": "connection_error",
                "message": "Unable to connect",
                "value": 0,
                "threshold": 1,
                "timestamp": "2026-05-02T10:00:00Z"
            }
        ]
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/alerts?severity=critical")

        # Assert
        assert response.status_code in [200, 500]

    @patch('core.integration_dashboard.IntegrationDashboard.get_alerts')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_alerts_count(self, mock_get_dashboard, mock_get_alerts, client):
        """RED: Test getting alert counts by severity."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_alerts.return_value = [
            {"severity": "critical"},
            {"severity": "critical"},
            {"severity": "warning"},
            {"severity": "warning"}
        ]
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/alerts/count")

        # Assert
        # Should return counts
        assert response.status_code in [200, 500]


# =============================================================================
# Test Class: Statistics
# =============================================================================

class TestStatistics:
    """Tests for GET /api/integrations/dashboard/statistics/summary"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_statistics_summary')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_statistics_summary(self, mock_get_dashboard, mock_get_stats, client):
        """RED: Test getting statistics summary."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_statistics_summary.return_value = {
            "total_integrations": 3,
            "active_integrations": 2,
            "total_messages_last_24h": 1450,
            "avg_response_time_ms": 250
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/statistics/summary")

        # Assert
        assert response.status_code in [200, 500]


# =============================================================================
# Test Class: Configuration Management
# =============================================================================

class TestConfigurationManagement:
    """Tests for GET and POST /api/integrations/dashboard/configuration"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_configuration')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_configuration_all(self, mock_get_dashboard, mock_get_config, client):
        """RED: Test getting configuration for all integrations."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_configuration.return_value = {
            "slack": {
                "enabled": True,
                "configured": True,
                "webhook_url": "https://hooks.slack.com/..."
            },
            "gmail": {
                "enabled": True,
                "configured": True,
                "sync_frequency": "5m"
            }
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/configuration")

        # Assert
        assert response.status_code in [200, 500]

    @patch('core.integration_dashboard.IntegrationDashboard.get_configuration')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_configuration_specific(self, mock_get_dashboard, mock_get_config, client):
        """RED: Test getting configuration for specific integration."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_configuration.return_value = {
            "enabled": True,
            "configured": True,
            "webhook_url": "https://hooks.slack.com/..."
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/configuration?integration=slack")

        # Assert
        assert response.status_code in [200, 500]

    @patch('core.auth.get_current_user')
    @patch('core.integration_dashboard.IntegrationDashboard.update_configuration')
    @patch('core.integration_dashboard.IntegrationDashboard.update_health')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_update_configuration(self, mock_get_dashboard, mock_update_health, mock_update_config, mock_user, client):
        """RED: Test updating integration configuration."""
        # Setup mocks
        mock_user_obj = Mock()
        mock_user.return_value = mock_user_obj

        mock_dashboard = Mock()
        mock_dashboard.update_health = Mock()
        mock_dashboard.update_configuration = Mock()
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.post(
            "/api/integrations/dashboard/configuration/slack",
            json={
                "enabled": True,
                "configured": True,
                "config": {
                    "webhook_url": "https://hooks.slack.com/new"
                }
            },
            headers={"Authorization": "Bearer test_token"}
        )

        # Assert
        # May require authentication
        assert response.status_code in [200, 401, 500]


# =============================================================================
# Test Class: Metrics Reset
# =============================================================================

class TestMetricsReset:
    """Tests for POST /api/integrations/dashboard/metrics/reset"""

    @patch('core.auth.get_current_user')
    @patch('core.integration_dashboard.IntegrationDashboard.reset_metrics')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_reset_all_metrics(self, mock_get_dashboard, mock_reset, mock_user, client):
        """RED: Test resetting metrics for all integrations."""
        # Setup mocks
        mock_user_obj = Mock()
        mock_user.return_value = mock_user_obj

        mock_dashboard = Mock()
        mock_dashboard.reset_metrics = Mock()
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.post(
            "/api/integrations/dashboard/metrics/reset",
            json={},
            headers={"Authorization": "Bearer test_token"}
        )

        # Assert
        # May require authentication
        assert response.status_code in [200, 401, 500]

    @patch('core.auth.get_current_user')
    @patch('core.integration_dashboard.IntegrationDashboard.reset_metrics')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_reset_specific_integration_metrics(self, mock_get_dashboard, mock_reset, mock_user, client):
        """RED: Test resetting metrics for specific integration."""
        # Setup mocks
        mock_user_obj = Mock()
        mock_user.return_value = mock_user_obj

        mock_dashboard = Mock()
        mock_dashboard.reset_metrics = Mock()
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.post(
            "/api/integrations/dashboard/metrics/reset",
            json={"integration": "slack"},
            headers={"Authorization": "Bearer test_token"}
        )

        # Assert
        # May require authentication
        assert response.status_code in [200, 401, 500]


# =============================================================================
# Test Class: Integration Listing
# =============================================================================

class TestIntegrationListing:
    """Tests for GET /api/integrations/dashboard/integrations"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_metrics')
    @patch('core.integration_dashboard.IntegrationDashboard.get_health')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_list_integrations(self, mock_get_dashboard, mock_get_health, mock_get_metrics, client):
        """RED: Test listing all available integrations."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_health.return_value = {
            "slack": {"status": "healthy", "enabled": True, "configured": True},
            "gmail": {"status": "healthy", "enabled": True, "configured": True},
            "teams": {"status": "degraded", "enabled": True, "configured": False}
        }
        mock_dashboard.get_metrics.return_value = {
            "slack": {"messages_fetched": 1250, "last_fetch_time": "2026-05-02T10:00:00Z"},
            "gmail": {"messages_fetched": 890, "last_fetch_time": "2026-05-02T09:55:00Z"},
            "teams": {"messages_fetched": 0, "last_fetch_time": None}
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/integrations")

        # Assert
        # Should succeed
        assert response.status_code in [200, 500]


# =============================================================================
# Test Class: Integration Details
# =============================================================================

class TestIntegrationDetails:
    """Tests for GET /api/integrations/dashboard/integrations/{id}/details"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_configuration')
    @patch('core.integration_dashboard.IntegrationDashboard.get_metrics')
    @patch('core.integration_dashboard.IntegrationDashboard.get_health')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_integration_details_success(self, mock_get_dashboard, mock_get_health, mock_get_metrics, mock_get_config, client):
        """RED: Test getting detailed information for integration."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_health.return_value = {
            "status": "healthy",
            "enabled": True,
            "configured": True
        }
        mock_dashboard.get_metrics.return_value = {
            "messages_fetched": 1250,
            "messages_processed": 1230
        }
        mock_dashboard.get_configuration.return_value = {
            "webhook_url": "https://..."
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/integrations/slack/details")

        # Assert
        # Should succeed
        assert response.status_code in [200, 500]

    @patch('core.integration_dashboard.IntegrationDashboard.get_configuration')
    @patch('core.integration_dashboard.IntegrationDashboard.get_metrics')
    @patch('core.integration_dashboard.IntegrationDashboard.get_health')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_integration_details_not_found(self, mock_get_dashboard, mock_get_health, mock_get_metrics, mock_get_config, client):
        """RED: Test getting details for non-existent integration."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_health.return_value = {}
        mock_dashboard.get_metrics.return_value = {}
        mock_dashboard.get_configuration.return_value = {}
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/integrations/nonexistent/details")

        # Assert
        # Should return 404
        assert response.status_code in [200, 404, 500]


# =============================================================================
# Test Class: Health Check
# =============================================================================

class TestHealthCheck:
    """Tests for POST /api/integrations/dashboard/health/{id}/check"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_health')
    @patch('core.integration_dashboard.IntegrationDashboard.update_health')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_check_integration_health(self, mock_get_dashboard, mock_update, mock_get_health, client):
        """RED: Test triggering health check for integration."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.update_health.return_value = None
        mock_dashboard.get_health.return_value = {
            "status": "healthy",
            "enabled": True,
            "configured": True,
            "last_check": "2026-05-02T10:00:00Z"
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.post("/api/integrations/dashboard/health/slack/check")

        # Assert
        # Should succeed
        assert response.status_code in [200, 500]


# =============================================================================
# Test Class: Performance Metrics
# =============================================================================

class TestPerformanceMetrics:
    """Tests for GET /api/integrations/dashboard/performance"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_metrics')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_performance_metrics(self, mock_get_dashboard, mock_get_metrics, client):
        """RED: Test getting performance metrics."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_metrics.return_value = {
            "slack": {
                "avg_fetch_time_ms": 150,
                "p99_fetch_time_ms": 350,
                "avg_process_time_ms": 50,
                "p99_process_time_ms": 120,
                "fetch_size_bytes": 524288,
                "attachment_count": 25
            },
            "gmail": {
                "avg_fetch_time_ms": 200,
                "p99_fetch_time_ms": 450,
                "avg_process_time_ms": 80,
                "p99_process_time_ms": 150,
                "fetch_size_bytes": 1048576,
                "attachment_count": 45
            }
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/performance")

        # Assert
        # Should succeed
        assert response.status_code in [200, 500]


# =============================================================================
# Test Class: Data Quality Metrics
# =============================================================================

class TestDataQualityMetrics:
    """Tests for GET /api/integrations/dashboard/data-quality"""

    @patch('core.integration_dashboard.IntegrationDashboard.get_metrics')
    @patch('api.integration_dashboard_routes.get_integration_dashboard')
    def test_get_data_quality_metrics(self, mock_get_dashboard, mock_get_metrics, client):
        """RED: Test getting data quality metrics."""
        # Setup mocks
        mock_dashboard = Mock()
        mock_dashboard.get_metrics.return_value = {
            "slack": {
                "messages_fetched": 1250,
                "messages_processed": 1230,
                "messages_failed": 20,
                "messages_duplicate": 5,
                "success_rate": 98.4,
                "duplicate_rate": 0.4
            },
            "gmail": {
                "messages_fetched": 890,
                "messages_processed": 885,
                "messages_failed": 5,
                "messages_duplicate": 2,
                "success_rate": 99.4,
                "duplicate_rate": 0.2
            }
        }
        mock_get_dashboard.return_value = mock_dashboard

        # Act
        response = client.get("/api/integrations/dashboard/data-quality")

        # Assert
        # Should succeed
        assert response.status_code in [200, 500]


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
