"""
Unit tests for Integration Dashboard API Routes

Tests cover:
- Integration metrics retrieval
- Integration health status
- Alerts management
- Configuration updates
- Metrics reset
- Overall status
- Performance metrics
- Data quality metrics
- Integration listing and details
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from unittest.mock import MagicMock, Mock, patch
from fastapi.testclient import TestClient

from api.integration_dashboard_routes import router


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_integration_dashboard():
    """Mock integration dashboard."""
    dashboard = MagicMock()
    dashboard.get_metrics = MagicMock(return_value={})
    dashboard.get_health = MagicMock(return_value={})
    dashboard.get_alerts = MagicMock(return_value=[])
    dashboard.update_configuration = MagicMock(return_value=True)
    dashboard.reset_metrics = MagicMock(return_value=True)
    dashboard.get_overall_status = MagicMock(return_value={})
    dashboard.get_configuration = MagicMock(return_value={})
    dashboard.update_health = MagicMock(return_value=True)
    dashboard.get_statistics_summary = MagicMock(return_value={})
    return dashboard


@pytest.fixture
def client(mock_integration_dashboard):
    """Test client with mocked dependencies."""
    with patch('api.integration_dashboard_routes.get_integration_dashboard', return_value=mock_integration_dashboard):
        yield TestClient(router)


@pytest.fixture
def sample_integration_id():
    """Sample integration ID for testing."""
    return "slack_integration"


# =============================================================================
# Integration Metrics Tests
# =============================================================================

class TestIntegrationMetrics:
    """Tests for integration metrics endpoints."""

    def test_get_metrics_all(self, client, mock_integration_dashboard):
        """Test getting metrics for all integrations."""
        mock_integration_dashboard.get_metrics.return_value = {
            "slack": {
                "messages_fetched": 100,
                "messages_processed": 95,
                "messages_failed": 5,
                "success_rate": 0.95
            },
            "teams": {
                "messages_fetched": 50,
                "messages_processed": 48,
                "messages_failed": 2,
                "success_rate": 0.96
            }
        }

        response = client.get("/api/integrations/dashboard/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_integration_dashboard.get_metrics.assert_called_once()

    def test_get_metrics_specific_integration(self, client, mock_integration_dashboard, sample_integration_id):
        """Test getting metrics for specific integration."""
        mock_integration_dashboard.get_metrics.return_value = {
            "messages_fetched": 100,
            "messages_processed": 95,
            "messages_failed": 5
        }

        response = client.get(f"/api/integrations/dashboard/metrics?integration={sample_integration_id}")

        assert response.status_code == 200
        mock_integration_dashboard.get_metrics.assert_called_with(sample_integration_id)

    def test_get_metrics_empty(self, client, mock_integration_dashboard):
        """Test getting metrics when no data exists."""
        mock_integration_dashboard.get_metrics.return_value = {}

        response = client.get("/api/integrations/dashboard/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# =============================================================================
# Integration Health Tests
# =============================================================================

class TestIntegrationHealth:
    """Tests for integration health endpoints."""

    def test_get_health_healthy(self, client, mock_integration_dashboard):
        """Test getting health status for healthy integration."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "healthy",
            "last_check": datetime.now().isoformat(),
            "uptime_seconds": 3600
        }

        response = client.get("/api/integrations/dashboard/health")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_health_degraded(self, client, mock_integration_dashboard):
        """Test getting health status for degraded integration."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "degraded",
            "last_check": datetime.now().isoformat(),
            "error_rate": 0.15
        }

        response = client.get("/api/integrations/dashboard/health")

        assert response.status_code == 200

    def test_get_health_error(self, client, mock_integration_dashboard):
        """Test getting health status for errored integration."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "error",
            "last_check": datetime.now().isoformat(),
            "error": "Connection refused"
        }

        response = client.get("/api/integrations/dashboard/health")

        assert response.status_code == 200

    def test_get_health_disabled(self, client, mock_integration_dashboard):
        """Test getting health status for disabled integration."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "disabled",
            "enabled": False
        }

        response = client.get("/api/integrations/dashboard/health")

        assert response.status_code == 200


# =============================================================================
# Overall Status Tests
# =============================================================================

class TestOverallStatus:
    """Tests for overall status endpoint."""

    def test_get_overall_status_healthy(self, client, mock_integration_dashboard):
        """Test getting overall healthy status."""
        mock_integration_dashboard.get_overall_status.return_value = {
            "overall_status": "healthy",
            "total_integrations": 5,
            "healthy_count": 4,
            "degraded_count": 1,
            "error_count": 0,
            "disabled_count": 0,
            "total_messages_fetched": 1000,
            "total_messages_processed": 975,
            "total_messages_failed": 25,
            "overall_success_rate": 0.975
        }

        response = client.get("/api/integrations/dashboard/status/overall")

        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert data["overall_status"] == "healthy"

    def test_get_overall_status_with_errors(self, client, mock_integration_dashboard):
        """Test getting overall status with errors."""
        mock_integration_dashboard.get_overall_status.return_value = {
            "overall_status": "degraded",
            "total_integrations": 5,
            "healthy_count": 3,
            "degraded_count": 1,
            "error_count": 1,
            "disabled_count": 0
        }

        response = client.get("/api/integrations/dashboard/status/overall")

        assert response.status_code == 200

    def test_get_overall_status_all_disabled(self, client, mock_integration_dashboard):
        """Test getting overall status when all disabled."""
        mock_integration_dashboard.get_overall_status.return_value = {
            "overall_status": "disabled",
            "total_integrations": 5,
            "disabled_count": 5
        }

        response = client.get("/api/integrations/dashboard/status/overall")

        assert response.status_code == 200


# =============================================================================
# Alerts Management Tests
# =============================================================================

class TestAlertsManagement:
    """Tests for alerts endpoints."""

    def test_get_alerts_empty(self, client, mock_integration_dashboard):
        """Test getting alerts when none exist."""
        mock_integration_dashboard.get_alerts.return_value = []

        response = client.get("/api/integrations/dashboard/alerts")

        assert response.status_code == 200
        alerts = response.json()
        assert alerts == [] or isinstance(alerts, list)

    def test_get_alerts_with_data(self, client, mock_integration_dashboard):
        """Test getting alerts with data."""
        mock_integration_dashboard.get_alerts.return_value = [
            {
                "integration": "slack",
                "severity": "warning",
                "type": "high_error_rate",
                "message": "Error rate exceeded threshold",
                "value": 0.15,
                "threshold": 0.10,
                "timestamp": datetime.now().isoformat()
            },
            {
                "integration": "teams",
                "severity": "critical",
                "type": "connection_failure",
                "message": "Unable to connect",
                "timestamp": datetime.now().isoformat()
            }
        ]

        response = client.get("/api/integrations/dashboard/alerts")

        assert response.status_code == 200
        alerts = response.json()
        assert len(alerts) == 2

    def test_get_alerts_filtered_by_severity(self, client, mock_integration_dashboard):
        """Test getting alerts filtered by severity."""
        mock_integration_dashboard.get_alerts.return_value = [
            {"severity": "critical", "type": "test"},
            {"severity": "warning", "type": "test2"}
        ]

        response = client.get("/api/integrations/dashboard/alerts?severity=critical")

        assert response.status_code == 200

    def test_get_alerts_count(self, client, mock_integration_dashboard):
        """Test getting alert counts."""
        mock_integration_dashboard.get_alerts.return_value = [
            {"severity": "critical", "type": "test1"},
            {"severity": "critical", "type": "test2"},
            {"severity": "warning", "type": "test3"}
        ]

        response = client.get("/api/integrations/dashboard/alerts/count")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 3
        assert data["data"]["critical"] == 2
        assert data["data"]["warning"] == 1


# =============================================================================
# Configuration Management Tests
# =============================================================================

class TestConfigurationManagement:
    """Tests for configuration endpoints."""

    def test_get_configuration_all(self, client, mock_integration_dashboard):
        """Test getting configuration for all integrations."""
        mock_integration_dashboard.get_configuration.return_value = {
            "slack": {"enabled": True, "auto_sync": True},
            "teams": {"enabled": False, "auto_sync": False}
        }

        response = client.get("/api/integrations/dashboard/configuration")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_configuration_specific(self, client, mock_integration_dashboard, sample_integration_id):
        """Test getting configuration for specific integration."""
        mock_integration_dashboard.get_configuration.return_value = {
            "enabled": True,
            "auto_sync_new_files": True,
            "file_types": ["pdf", "docx"]
        }

        response = client.get(f"/api/integrations/dashboard/configuration?integration={sample_integration_id}")

        assert response.status_code == 200

    def test_update_configuration_enable(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating configuration to enable integration."""
        request = {
            "enabled": True
        }

        response = client.post(f"/api/integrations/dashboard/configuration/{sample_integration_id}", json=request)

        assert response.status_code == 200
        mock_integration_dashboard.update_health.assert_called_once()

    def test_update_configuration_disable(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating configuration to disable integration."""
        request = {
            "enabled": False
        }

        response = client.post(f"/api/integrations/dashboard/configuration/{sample_integration_id}", json=request)

        assert response.status_code == 200

    def test_update_configuration_with_config(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating configuration with config dict."""
        request = {
            "config": {
                "file_types": ["pdf", "docx", "txt"],
                "sync_folders": ["/Documents", "/Downloads"]
            }
        }

        response = client.post(f"/api/integrations/dashboard/configuration/{sample_integration_id}", json=request)

        assert response.status_code == 200
        mock_integration_dashboard.update_configuration.assert_called_once()

    def test_update_configuration_multiple_fields(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating multiple configuration fields."""
        request = {
            "enabled": True,
            "configured": True,
            "has_valid_token": True,
            "has_required_permissions": True,
            "config": {"max_file_size_mb": 25}
        }

        response = client.post(f"/api/integrations/dashboard/configuration/{sample_integration_id}", json=request)

        assert response.status_code == 200


# =============================================================================
# Metrics Reset Tests
# =============================================================================

class TestMetricsReset:
    """Tests for metrics reset endpoints."""

    def test_reset_metrics_all(self, client, mock_integration_dashboard):
        """Test resetting metrics for all integrations."""
        mock_integration_dashboard.reset_metrics.return_value = True

        response = client.post("/api/integrations/dashboard/metrics/reset", json={})

        assert response.status_code == 200
        mock_integration_dashboard.reset_metrics.assert_called_with(None)

    def test_reset_metrics_specific_integration(self, client, mock_integration_dashboard, sample_integration_id):
        """Test resetting metrics for specific integration."""
        request = {
            "integration": sample_integration_id
        }
        mock_integration_dashboard.reset_metrics.return_value = True

        response = client.post("/api/integrations/dashboard/metrics/reset", json=request)

        assert response.status_code == 200
        mock_integration_dashboard.reset_metrics.assert_called_with(sample_integration_id)


# =============================================================================
# Statistics Summary Tests
# =============================================================================

class TestStatisticsSummary:
    """Tests for statistics summary endpoint."""

    def test_get_statistics_summary(self, client, mock_integration_dashboard):
        """Test getting statistics summary."""
        mock_integration_dashboard.get_statistics_summary.return_value = {
            "total_integrations": 5,
            "active_integrations": 4,
            "total_messages_processed": 10000,
            "avg_success_rate": 0.95,
            "recent_activity": {
                "last_hour": 100,
                "last_day": 2000,
                "last_week": 12000
            }
        }

        response = client.get("/api/integrations/dashboard/statistics/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# =============================================================================
# Integration Listing Tests
# =============================================================================

class TestIntegrationListing:
    """Tests for integration listing endpoints."""

    def test_list_integrations(self, client, mock_integration_dashboard):
        """Test listing all integrations."""
        mock_integration_dashboard.get_health.return_value = {
            "slack": {"status": "healthy", "enabled": True, "configured": True},
            "teams": {"status": "disabled", "enabled": False, "configured": False}
        }
        mock_integration_dashboard.get_metrics.return_value = {
            "slack": {"messages_fetched": 100, "last_fetch_time": "2024-01-01T12:00:00Z"},
            "teams": {"messages_fetched": 0, "last_fetch_time": None}
        }

        response = client.get("/api/integrations/dashboard/integrations")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "integrations" in data["data"]
        assert len(data["data"]["integrations"]) == 2

    def test_get_integration_details(self, client, mock_integration_dashboard, sample_integration_id):
        """Test getting detailed integration information."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "healthy",
            "enabled": True,
            "configured": True
        }
        mock_integration_dashboard.get_metrics.return_value = {
            "messages_fetched": 100,
            "messages_processed": 95,
            "success_rate": 0.95
        }
        mock_integration_dashboard.get_configuration.return_value = {
            "auto_sync": True,
            "file_types": ["pdf"]
        }

        response = client.get(f"/api/integrations/dashboard/integrations/{sample_integration_id}/details")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "integration" in data["data"]
        assert "health" in data["data"]
        assert "metrics" in data["data"]
        assert "configuration" in data["data"]

    def test_get_integration_details_not_found(self, client, mock_integration_dashboard, sample_integration_id):
        """Test getting details for non-existent integration."""
        mock_integration_dashboard.get_health.return_value = None

        response = client.get(f"/api/integrations/dashboard/integrations/nonexistent/details")

        assert response.status_code == 404


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_check_integration_health(self, client, mock_integration_dashboard, sample_integration_id):
        """Test triggering health check for integration."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "healthy",
            "last_check": datetime.now().isoformat()
        }

        response = client.post(f"/api/integrations/dashboard/health/{sample_integration_id}/check")

        assert response.status_code == 200
        mock_integration_dashboard.update_health.assert_called_once()


# =============================================================================
# Performance Metrics Tests
# =============================================================================

class TestPerformanceMetrics:
    """Tests for performance metrics endpoint."""

    def test_get_performance_metrics(self, client, mock_integration_dashboard):
        """Test getting performance metrics."""
        mock_integration_dashboard.get_metrics.return_value = {
            "slack": {
                "avg_fetch_time_ms": 150,
                "p99_fetch_time_ms": 500,
                "avg_process_time_ms": 50,
                "p99_process_time_ms": 200,
                "fetch_size_bytes": 1024000,
                "attachment_count": 5
            },
            "teams": {
                "avg_fetch_time_ms": 200,
                "p99_fetch_time_ms": 600,
                "fetch_size_bytes": 512000,
                "attachment_count": 2
            }
        }

        response = client.get("/api/integrations/dashboard/performance")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "slack" in data["data"]
        assert "teams" in data["data"]


# =============================================================================
# Data Quality Metrics Tests
# =============================================================================

class TestDataQualityMetrics:
    """Tests for data quality metrics endpoint."""

    def test_get_data_quality_metrics(self, client, mock_integration_dashboard):
        """Test getting data quality metrics."""
        mock_integration_dashboard.get_metrics.return_value = {
            "slack": {
                "messages_fetched": 1000,
                "messages_processed": 975,
                "messages_failed": 15,
                "messages_duplicate": 10,
                "success_rate": 97.5,
                "duplicate_rate": 1.0
            },
            "teams": {
                "messages_fetched": 500,
                "messages_processed": 490,
                "messages_failed": 10,
                "messages_duplicate": 5,
                "success_rate": 98.0,
                "duplicate_rate": 1.0
            }
        }

        response = client.get("/api/integrations/dashboard/data-quality")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "slack" in data["data"]
        assert "teams" in data["data"]


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_get_metrics_exception(self, client, mock_integration_dashboard):
        """Test handling exception when getting metrics."""
        mock_integration_dashboard.get_metrics.side_effect = Exception("Database error")

        response = client.get("/api/integrations/dashboard/metrics")

        assert response.status_code == 500

    def test_update_configuration_exception(self, client, mock_integration_dashboard, sample_integration_id):
        """Test handling exception when updating configuration."""
        mock_integration_dashboard.update_configuration.side_effect = Exception("Update failed")

        response = client.post(f"/api/integrations/dashboard/configuration/{sample_integration_id}", json={"config": {}})

        assert response.status_code == 500

    def test_reset_metrics_exception(self, client, mock_integration_dashboard):
        """Test handling exception when resetting metrics."""
        mock_integration_dashboard.reset_metrics.side_effect = Exception("Reset failed")

        response = client.post("/api/integrations/dashboard/metrics/reset", json={})

        assert response.status_code == 500
