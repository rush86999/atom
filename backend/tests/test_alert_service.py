"""
Test suite for Alert Service

Tests alert threshold evaluation service including:
- Error rate threshold evaluation
- Latency threshold evaluation
- Sliding window evaluation
- Hysteresis to prevent alert flapping
- Alert notification dispatch (Slack, email)
- Alert violation tracking
- Alert cleared notifications
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timedelta

from core.alert_service import (
    AlertSeverity,
    AlertStatus,
    AlertViolation,
    AlertEvaluationResult,
    AlertThresholdService
)


class TestAlertSeverity:
    """Test AlertSeverity enum"""

    def test_alert_severity_values(self):
        """AlertSeverity has correct enum values."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestAlertStatus:
    """Test AlertStatus enum"""

    def test_alert_status_values(self):
        """AlertStatus has correct enum values."""
        assert AlertStatus.OK.value == "ok"
        assert AlertStatus.VIOLATED.value == "violated"
        assert AlertStatus.CLEARED.value == "cleared"


class TestAlertViolation:
    """Test AlertViolation dataclass"""

    def test_alert_violation_creation(self):
        """AlertViolation can be created with valid parameters."""
        violation = AlertViolation(
            tenant_id="tenant-001",
            connector_id="slack",
            metric_type="error_rate",
            actual_value=15.5,
            threshold=10.0,
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.utcnow(),
            window_start=datetime.utcnow() - timedelta(seconds=300),
            window_end=datetime.utcnow()
        )
        assert violation.tenant_id == "tenant-001"
        assert violation.connector_id == "slack"
        assert violation.actual_value == 15.5
        assert violation.threshold == 10.0
        assert violation.severity == AlertSeverity.CRITICAL

    def test_alert_violation_fields(self):
        """AlertViolation has all required fields."""
        window_start = datetime.utcnow() - timedelta(seconds=300)
        violation = AlertViolation(
            tenant_id="tenant-001",
            connector_id="jira",
            metric_type="latency_p95",
            actual_value=550.0,
            threshold=500.0,
            severity=AlertSeverity.WARNING,
            timestamp=datetime.utcnow(),
            window_start=window_start,
            window_end=datetime.utcnow()
        )
        assert violation.metric_type == "latency_p95"
        assert violation.window_start == window_start


class TestAlertEvaluationResult:
    """Test AlertEvaluationResult dataclass"""

    def test_evaluation_result_creation(self):
        """AlertEvaluationResult can be created with valid parameters."""
        result = AlertEvaluationResult(
            tenant_id="tenant-001",
            connector_id="slack",
            status=AlertStatus.VIOLATED,
            violations=[],
            evaluated_at=datetime.utcnow()
        )
        assert result.tenant_id == "tenant-001"
        assert result.status == AlertStatus.VIOLATED
        assert len(result.violations) == 0

    def test_evaluation_result_with_violations(self):
        """AlertEvaluationResult can contain multiple violations."""
        violation1 = AlertViolation(
            tenant_id="tenant-001",
            connector_id="slack",
            metric_type="error_rate",
            actual_value=15.0,
            threshold=10.0,
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.utcnow(),
            window_start=datetime.utcnow(),
            window_end=datetime.utcnow()
        )
        violation2 = AlertViolation(
            tenant_id="tenant-001",
            connector_id="slack",
            metric_type="latency_p95",
            actual_value=600.0,
            threshold=500.0,
            severity=AlertSeverity.WARNING,
            timestamp=datetime.utcnow(),
            window_start=datetime.utcnow(),
            window_end=datetime.utcnow()
        )

        result = AlertEvaluationResult(
            tenant_id="tenant-001",
            connector_id="slack",
            status=AlertStatus.VIOLATED,
            violations=[violation1, violation2],
            evaluated_at=datetime.utcnow()
        )
        assert len(result.violations) == 2


class TestAlertThresholdServiceInit:
    """Test AlertThresholdService initialization"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    def test_service_initialization(self, mock_db):
        """AlertThresholdService initializes with database session."""
        service = AlertThresholdService(mock_db, redis_client=None)
        assert service.db == mock_db
        assert service.redis is None
        assert service.HYSTERESIS_BAND == 0.20

    def test_service_initialization_with_redis(self, mock_db):
        """AlertThresholdService initializes with Redis client."""
        mock_redis = Mock()
        service = AlertThresholdService(mock_db, redis_client=mock_redis)
        assert service.redis == mock_redis


class TestErrorRateEvaluation:
    """Test error rate threshold evaluation"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def mock_config(self):
        """Mock alert configuration."""
        config = Mock()
        config.tenant_id = "tenant-001"
        config.connector_id = "slack"
        config.window_seconds = 300
        config.error_rate_threshold = 10.0
        config.latency_threshold_ms = 500
        config.notification_channels = ["slack"]
        config.slack_channel_id = "C001"
        config.email_recipients = None
        return config

    @pytest.fixture
    def service(self, mock_db):
        """Create alert service instance."""
        return AlertThresholdService(mock_db, redis_client=None)

    def test_error_rate_threshold_violation(self, service, mock_config):
        """Error rate violation detected when threshold exceeded."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance.success_counts = {"slack:tenant-001:agent": 85}
            metrics_instance.failure_counts = {"slack:tenant-001:agent": 15}
            mock_metrics.return_value = metrics_instance

            with patch.object(service, '_get_alert_state', return_value="ok"):
                with patch.object(service, '_set_alert_state'):
                    violation = service.evaluate_error_rate_threshold(
                        tenant_id="tenant-001",
                        connector_id="slack",
                        configuration=mock_config
                    )

                    assert violation is not None
                    assert violation.metric_type == "error_rate"
                    assert violation.actual_value == 15.0  # 15 failures out of 100 total
                    assert violation.threshold == 10.0

    def test_error_rate_within_threshold(self, service, mock_config):
        """No violation when error rate within threshold."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance.success_counts = {"slack:tenant-001:agent": 95}
            metrics_instance.failure_counts = {"slack:tenant-001:agent": 5}
            mock_metrics.return_value = metrics_instance

            with patch.object(service, '_get_alert_state', return_value="ok"):
                violation = service.evaluate_error_rate_threshold(
                    tenant_id="tenant-001",
                    connector_id="slack",
                    configuration=mock_config
                )

                assert violation is None

    def test_error_rate_hysteresis(self, service, mock_config):
        """Alert clears only when below clear threshold (hysteresis)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance.success_counts = {"slack:tenant-001:agent": 90}
            metrics_instance.failure_counts = {"slack:tenant-001:agent": 10}
            mock_metrics.return_value = metrics_instance

            with patch.object(service, '_get_alert_state', return_value="violated"):
                with patch.object(service, '_set_alert_state') as mock_set_state:
                    # Error rate = 10%, threshold = 10%, clear at 8%
                    # Should clear because 10% is not > 10% (no new violation)
                    # But current state is violated, so check if < 8%
                    # 10% is NOT < 8%, so should NOT clear
                    violation = service.evaluate_error_rate_threshold(
                        tenant_id="tenant-001",
                        connector_id="slack",
                        configuration=mock_config
                    )

                    # Should not clear (10% is still above 8% clear threshold)
                    mock_set_state.assert_not_called()


class TestLatencyEvaluation:
    """Test latency threshold evaluation"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def mock_config(self):
        """Mock alert configuration."""
        config = Mock()
        config.tenant_id = "tenant-001"
        config.connector_id="jira"
        config.latency_threshold_ms = 500
        return config

    @pytest.fixture
    def service(self, mock_db):
        """Create alert service instance."""
        return AlertThresholdService(mock_db, redis_client=None)

    def test_latency_threshold_violation(self, service, mock_config):
        """Latency violation detected when p95 exceeds threshold."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance.get_duration_percentiles.return_value = {
                "p50": 200.0,
                "p95": 600.0,
                "p99": 800.0
            }
            mock_metrics.return_value = metrics_instance

            violation = service.evaluate_latency_threshold(
                tenant_id="tenant-001",
                connector_id="jira",
                configuration=mock_config
            )

            assert violation is not None
            assert violation.metric_type == "latency_p95"
            assert violation.actual_value == 600.0
            assert violation.threshold == 500.0
            assert violation.severity == AlertSeverity.WARNING

    def test_latency_within_threshold(self, service, mock_config):
        """No violation when p95 latency within threshold."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance.get_duration_percentiles.return_value = {
                "p50": 150.0,
                "p95": 400.0,
                "p99": 450.0
            }
            mock_metrics.return_value = metrics_instance

            violation = service.evaluate_latency_threshold(
                tenant_id="tenant-001",
                connector_id="jira",
                configuration=mock_config
            )

            assert violation is None

    def test_latency_threshold_not_configured(self, service, mock_config):
        """No violation when latency threshold not configured."""
        mock_config.latency_threshold_ms = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        violation = service.evaluate_latency_threshold(
            tenant_id="tenant-001",
            connector_id="jira",
            configuration=mock_config
        )

        assert violation is None


class TestEvaluateAllThresholds:
    """Test evaluation of all thresholds"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def service(self, mock_db):
        """Create alert service instance."""
        return AlertThresholdService(mock_db, redis_client=None)

    @pytest.fixture
    def mock_configs(self):
        """Mock multiple alert configurations."""
        config1 = Mock()
        config1.tenant_id = "tenant-001"
        config1.connector_id = "slack"
        config1.window_seconds = 300
        config1.error_rate_threshold = 10.0
        config1.latency_threshold_ms = 500
        config1.notification_channels = []
        config1.slack_channel_id = None
        config1.email_recipients = None

        config2 = Mock()
        config2.tenant_id = "tenant-001"
        config2.connector_id = "jira"
        config2.window_seconds = 300
        config2.error_rate_threshold = 5.0
        config2.latency_threshold_ms = 1000
        config2.notification_channels = []
        config2.slack_channel_id = None
        config2.email_recipients = None

        return [config1, config2]

    def test_evaluate_all_thresholds_success(self, service, mock_db, mock_configs):
        """All thresholds evaluated successfully."""
        mock_db.query.return_value.filter.return_value.all.return_value = mock_configs

        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance.success_counts = {
                "slack:tenant-001:agent": 90,
                "jira:tenant-001:agent": 95
            }
            metrics_instance.failure_counts = {
                "slack:tenant-001:agent": 10,
                "jira:tenant-001:agent": 5
            }
            metrics_instance.get_duration_percentiles.return_value = {"p95": 400.0}
            mock_metrics.return_value = metrics_instance

            with patch.object(service, '_get_alert_state', return_value="ok"):
                results = service.evaluate_all_thresholds(tenant_id="tenant-001")

                assert len(results) == 2
                assert all(isinstance(r, AlertEvaluationResult) for r in results)

    def test_evaluate_all_returns_violations(self, service, mock_db, mock_configs):
        """evaluate_all_thresholds returns violations when thresholds exceeded."""
        mock_db.query.return_value.filter.return_value.all.return_value = mock_configs

        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance.success_counts = {"slack:tenant-001:agent": 85}
            metrics_instance.failure_counts = {"slack:tenant-001:agent": 15}
            metrics_instance.get_duration_percentiles.return_value = {"p95": 400.0}
            mock_metrics.return_value = metrics_instance

            with patch.object(service, '_get_alert_state', return_value="ok"):
                with patch.object(service, '_set_alert_state'):
                    results = service.evaluate_all_thresholds(tenant_id="tenant-001")

                    # At least one violation should be detected (error rate = 15% > 10%)
                    violated_results = [r for r in results if r.status == AlertStatus.VIOLATED]
                    assert len(violated_results) > 0


class TestNotificationDispatch:
    """Test notification dispatch for alerts"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def service(self, mock_db):
        """Create alert service instance."""
        return AlertThresholdService(mock_db, redis_client=None)

    @pytest.fixture
    def mock_violation(self):
        """Mock alert violation."""
        return AlertViolation(
            tenant_id="tenant-001",
            connector_id="slack",
            metric_type="error_rate",
            actual_value=15.0,
            threshold=10.0,
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.utcnow(),
            window_start=datetime.utcnow() - timedelta(seconds=300),
            window_end=datetime.utcnow()
        )

    @pytest.fixture
    def mock_config(self):
        """Mock alert configuration with notifications."""
        config = Mock()
        config.notification_channels = ["slack", "email"]
        config.slack_channel_id = "C001"
        config.email_recipients = ["admin@example.com"]
        return config

    @pytest.mark.asyncio
    async def test_send_notifications_both_channels(self, service, mock_violation, mock_config):
        """Notifications sent to both Slack and email."""
        with patch.object(service, 'send_slack_notification', new_callable=AsyncMock) as mock_slack:
            mock_slack.return_value = True

            with patch.object(service, 'send_email_notification', new_callable=AsyncMock) as mock_email:
                mock_email.return_value = True

                results = await service.send_notifications(mock_violation, mock_config)

                assert results["slack"] is True
                assert results["email"] is True
                mock_slack.assert_called_once_with(mock_violation, mock_config)
                mock_email.assert_called_once_with(mock_violation, mock_config)

    @pytest.mark.asyncio
    async def test_send_notifications_slack_only(self, service, mock_violation, mock_config):
        """Notifications sent to Slack only when email not configured."""
        mock_config.notification_channels = ["slack"]
        mock_config.email_recipients = None

        with patch.object(service, 'send_slack_notification', new_callable=AsyncMock) as mock_slack:
            mock_slack.return_value = True

            results = await service.send_notifications(mock_violation, mock_config)

            assert "slack" in results
            assert "email" not in results

    @pytest.mark.asyncio
    async def test_send_slack_notification_success(self, service, mock_violation, mock_config):
        """Slack notification sent successfully."""
        with patch('core.alert_service.SlackEnhancedService') as mock_slack_class:
            mock_slack_instance = Mock()
            mock_slack_class.return_value = mock_slack_instance

            with patch('core.alert_service.token_storage') as mock_token_storage:
                mock_token_data = {"access_token": "xoxb-test-token"}
                mock_token_storage.get_token.return_value = mock_token_data

                with patch.object(mock_slack_instance, 'send_message', new_callable=AsyncMock):
                    result = await service.send_slack_notification(mock_violation, mock_config)
                    assert result is True

    @pytest.mark.asyncio
    async def test_send_slack_notification_no_token(self, service, mock_violation, mock_config):
        """Slack notification fails when token not found."""
        with patch('core.alert_service.token_storage') as mock_token_storage:
            mock_token_storage.get_token.return_value = None

            result = await service.send_slack_notification(mock_violation, mock_config)
            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_notification_success(self, service, mock_violation, mock_config):
        """Email notification sent successfully."""
        with patch('core.alert_service.EmailService') as mock_email_class:
            mock_email_instance = Mock()
            mock_email_class.return_value = mock_email_instance

            with patch.object(mock_email_instance, 'send_email', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                result = await service.send_email_notification(mock_violation, mock_config)
                assert result is True

    @pytest.mark.asyncio
    async def test_send_email_notification_no_recipients(self, service, mock_violation, mock_config):
        """Email notification fails when no recipients configured."""
        mock_config.email_recipients = None

        result = await service.send_email_notification(mock_violation, mock_config)
        assert result is False


class TestAlertClearedNotification:
    """Test alert cleared notifications"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def service(self, mock_db):
        """Create alert service instance."""
        return AlertThresholdService(mock_db, redis_client=None)

    @pytest.fixture
    def mock_config(self):
        """Mock alert configuration."""
        config = Mock()
        config.notification_channels = ["slack"]
        config.slack_channel_id = "C001"
        config.email_recipients = ["admin@example.com"]
        return config

    @pytest.mark.asyncio
    async def test_send_alert_cleared_notification_slack(self, service, mock_config):
        """Alert cleared notification sent via Slack."""
        with patch('core.alert_service.SlackEnhancedService') as mock_slack_class:
            mock_slack_instance = Mock()
            mock_slack_class.return_value = mock_slack_instance

            with patch('core.alert_service.token_storage') as mock_token_storage:
                mock_token_data = {"access_token": "xoxb-test-token"}
                mock_token_storage.get_token.return_value = mock_token_data

                with patch.object(mock_slack_instance, 'send_message', new_callable=AsyncMock):
                    result = await service.send_alert_cleared_notification(
                        tenant_id="tenant-001",
                        connector_id="slack",
                        metric_type="error_rate",
                        configuration=mock_config
                    )
                    assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_cleared_notification_email(self, service, mock_config):
        """Alert cleared notification sent via email."""
        mock_config.notification_channels = ["email"]
        mock_config.slack_channel_id = None

        with patch('core.alert_service.EmailService') as mock_email_class:
            mock_email_instance = Mock()
            mock_email_class.return_value = mock_email_instance

            with patch.object(mock_email_instance, 'send_email', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                result = await service.send_alert_cleared_notification(
                    tenant_id="tenant-001",
                    connector_id="slack",
                    metric_type="error_rate",
                    configuration=mock_config
                )
                assert result is True


class TestGetViolationsForTenant:
    """Test retrieving violations for tenant"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def service(self, mock_db):
        """Create alert service instance."""
        return AlertThresholdService(mock_db, redis_client=None)

    def test_get_violations_for_tenant(self, service):
        """Violations retrieved for tenant."""
        mock_config = Mock()
        mock_config.tenant_id = "tenant-001"
        mock_config.connector_id = "slack"
        mock_config.window_seconds = 300
        mock_config.error_rate_threshold = 10.0
        mock_config.latency_threshold_ms = None
        mock_config.notification_channels = []
        mock_config.slack_channel_id = None
        mock_config.email_recipients = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance.success_counts = {"slack:tenant-001:agent": 85}
            metrics_instance.failure_counts = {"slack:tenant-001:agent": 15}
            mock_metrics.return_value = metrics_instance

            with patch.object(service, '_get_alert_state', return_value="ok"):
                with patch.object(service, '_set_alert_state'):
                    violations = service.get_violations_for_tenant(tenant_id="tenant-001")

                    assert len(violations) > 0
                    assert all(isinstance(v, AlertViolation) for v in violations)


class TestHelperMethods:
    """Test helper methods"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def service(self, mock_db):
        """Create alert service instance."""
        return AlertThresholdService(mock_db, redis_client=None)

    def test_calculate_error_rate_in_window(self, service):
        """Error rate calculated correctly within window."""
        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance._make_key.return_value = "slack:tenant-001:agent"
            metrics_instance.success_counts = {"slack:tenant-001:agent": 90}
            metrics_instance.failure_counts = {"slack:tenant-001:agent": 10}
            mock_metrics.return_value = metrics_instance

            error_rate = service._calculate_error_rate_in_window(
                metrics=metrics_instance,
                tenant_id="tenant-001",
                connector_id="slack",
                window_start=datetime.utcnow() - timedelta(seconds=300)
            )

            assert error_rate == 10.0  # 10 failures out of 100 total = 10%

    def test_calculate_error_rate_zero_total(self, service):
        """Error rate returns 0 when no requests."""
        with patch('core.alert_service.get_integration_metrics') as mock_metrics:
            metrics_instance = Mock()
            metrics_instance._make_key.return_value = "slack:tenant-001:agent"
            metrics_instance.success_counts = {}
            metrics_instance.failure_counts = {}
            mock_metrics.return_value = metrics_instance

            error_rate = service._calculate_error_rate_in_window(
                metrics=metrics_instance,
                tenant_id="tenant-001",
                connector_id="slack",
                window_start=datetime.utcnow() - timedelta(seconds=300)
            )

            assert error_rate == 0.0

    def test_format_slack_message(self, service):
        """Slack message formatted correctly."""
        violation = AlertViolation(
            tenant_id="tenant-001",
            connector_id="slack",
            metric_type="error_rate",
            actual_value=15.0,
            threshold=10.0,
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.utcnow(),
            window_start=datetime.utcnow(),
            window_end=datetime.utcnow()
        )

        message = service._format_slack_message(violation, Mock())

        assert "Alert Violation Detected" in message
        assert "slack" in message
        assert "error_rate" in message
        assert "15.00" in message
        assert "CRITICAL" in message

    def test_format_email_subject(self, service):
        """Email subject formatted correctly."""
        violation = AlertViolation(
            tenant_id="tenant-001",
            connector_id="jira",
            metric_type="latency_p95",
            actual_value=600.0,
            threshold=500.0,
            severity=AlertSeverity.WARNING,
            timestamp=datetime.utcnow(),
            window_start=datetime.utcnow(),
            window_end=datetime.utcnow()
        )

        subject = service._format_email_subject(violation)

        assert "Alert:" in subject
        assert "jira" in subject
        assert "latency_p95" in subject

    def test_format_email_html(self, service):
        """Email HTML formatted correctly."""
        violation = AlertViolation(
            tenant_id="tenant-001",
            connector_id="slack",
            metric_type="error_rate",
            actual_value=15.0,
            threshold=10.0,
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.utcnow(),
            window_start=datetime.utcnow(),
            window_end=datetime.utcnow()
        )

        html = service._format_email_html(violation, Mock())

        assert "<!DOCTYPE html>" in html
        assert "Alert Violation Detected" in html
        assert "slack" in html
        assert "error_rate" in html
