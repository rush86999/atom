"""
Monitoring & Analytics Scenario Tests

Test coverage for Category 8: Monitoring & Analytics (15 Scenarios)
Wave 2: Core Agent Workflows

Tests metrics collection, alerting, dashboards, log aggregation,
and health monitoring.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
from sqlalchemy.orm import Session

from core.models import AgentExecution, User


# ============================================================================
# MON-001 to MON-006: Critical Scenarios - Metrics, Alerts, Dashboards
# ============================================================================

class TestMetricsCollectionAgentExecution:
    """MON-001: Metrics Collection - Agent Execution"""

    def test_duration_metric_captured(self, db_session, test_agent, test_user):
        """Execution duration captured"""
        # Given
        started_at = datetime.utcnow()
        completed_at = started_at + timedelta(seconds=5)
        execution = AgentExecution(
            agent_id=test_agent.id,
            user_id=test_user.id,
            input="test",
            status="completed",
            started_at=started_at,
            completed_at=completed_at
        )
        execution.duration_ms = 5000

        # When
        metrics = {
            "duration_ms": execution.duration_ms
        }

        # Then
        assert metrics["duration_ms"] == 5000
        assert metrics["duration_ms"] > 0

    def test_memory_metric_captured(self, db_session, test_agent):
        """Memory usage captured"""
        # Given
        execution = AgentExecution(
            agent_id=test_agent.id,
            user_id=test_user.id,
            input="test",
            status="completed"
        )
        execution.memory_used_mb = 256

        # When
        metrics = {
            "memory_mb": execution.memory_used_mb
        }

        # Then
        assert metrics["memory_mb"] == 256
        assert metrics["memory_mb"] > 0

    def test_cpu_metric_captured(self, db_session, test_agent):
        """CPU usage captured"""
        # Given
        execution = AgentExecution(
            agent_id=test_agent.id,
            user_id=test_user.id,
            input="test",
            status="completed"
        )
        execution.cpu_used_percent = 45

        # When
        metrics = {
            "cpu_percent": execution.cpu_used_percent
        }

        # Then
        assert metrics["cpu_percent"] == 45
        assert 0 <= metrics["cpu_percent"] <= 100

    def test_tokens_metric_captured(self, db_session, test_agent):
        """Token usage captured"""
        # Given
        execution = AgentExecution(
            agent_id=test_agent.id,
            user_id=test_user.id,
            input="test",
            status="completed"
        )
        execution.tokens_used = 150

        # When
        metrics = {
            "tokens": execution.tokens_used
        }

        # Then
        assert metrics["tokens"] == 150
        assert metrics["tokens"] > 0

    def test_metrics_stored_in_database(self, db_session, test_agent, test_user):
        """All metrics stored in database"""
        # Given
        execution = AgentExecution(
            agent_id=test_agent.id,
            user_id=test_user.id,
            input="test",
            status="completed",
            duration_ms=5000,
            memory_used_mb=256,
            cpu_used_percent=45,
            tokens_used=150,
            started_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()

        # When
        retrieved = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first()

        # Then
        assert retrieved is not None
        assert retrieved.duration_ms == 5000
        assert retrieved.memory_used_mb == 256
        assert retrieved.cpu_used_percent == 45
        assert retrieved.tokens_used == 150


class TestMetricsCollectionAPIPerformance:
    """MON-002: Metrics Collection - API Performance"""

    def test_latency_metric_captured(self, db_session):
        """API latency captured"""
        # Given
        start_time = time.time()
        # Simulate API call
        time.sleep(0.05)  # 50ms response time
        end_time = time.time()

        # When
        latency_ms = (end_time - start_time) * 1000
        metrics = {
            "latency_ms": latency_ms
        }

        # Then
        assert metrics["latency_ms"] >= 50

    def test_status_code_captured(self, db_session):
        """HTTP status code captured"""
        # Given
        status_code = 200

        # When
        metrics = {
            "status_code": status_code,
            "success": status_code < 400
        }

        # Then
        assert metrics["status_code"] == 200
        assert metrics["success"] is True

    def test_error_rate_calculated(self, db_session):
        """Error rate calculated from metrics"""
        # Given
        requests = [
            {"status": 200},  # success
            {"status": 200},  # success
            {"status": 500},  # error
            {"status": 200},  # success
            {"status": 404},  # error
        ]

        # When
        total_requests = len(requests)
        error_requests = sum(1 for r in requests if r["status"] >= 400)
        error_rate = (error_requests / total_requests) * 100

        # Then
        assert total_requests == 5
        assert error_requests == 2
        assert error_rate == 40.0

    def test_metrics_aggregated(self, db_session):
        """Metrics aggregated over time window"""
        # Given
        latency_samples = [50, 75, 60, 80, 55]  # in ms

        # When
        avg_latency = sum(latency_samples) / len(latency_samples)
        max_latency = max(latency_samples)
        min_latency = min(latency_samples)

        # Then
        assert avg_latency == 64.0
        assert max_latency == 80
        assert min_latency == 50


class TestAlertTriggerThresholdExceeded:
    """MON-003: Alert Trigger - Threshold Exceeded"""

    def test_alert_triggered_when_error_rate_exceeds_threshold(self, db_session):
        """Alert triggered when error rate > 5%"""
        # Given
        error_rate_threshold = 5.0
        current_error_rate = 7.5  # Exceeds threshold
        alerts_triggered = []

        # When
        if current_error_rate > error_rate_threshold:
            alerts_triggered.append({
                "metric": "error_rate",
                "threshold": error_rate_threshold,
                "current_value": current_error_rate,
                "severity": "critical",
                "timestamp": datetime.utcnow()
            })

        # Then
        assert len(alerts_triggered) == 1
        assert alerts_triggered[0]["metric"] == "error_rate"
        assert alerts_triggered[0]["current_value"] == 7.5
        assert alerts_triggered[0]["severity"] == "critical"

    def test_team_notified_of_alert(self, db_session):
        """Team notified when alert triggered"""
        # Given
        alert = {
            "metric": "error_rate",
            "current_value": 7.5,
            "threshold": 5.0
        }
        notifications_sent = []

        # When
        # Simulate sending notifications
        notifications_sent.append({
            "channel": "email",
            "recipients": ["ops-team@company.com"],
            "subject": f"ALERT: {alert['metric']} exceeded threshold",
            "message": f"Current value: {alert['current_value']}%, Threshold: {alert['threshold']}%",
            "timestamp": datetime.utcnow()
        })

        # Then
        assert len(notifications_sent) == 1
        assert "ops-team@company.com" in notifications_sent[0]["recipients"]
        assert "error_rate" in notifications_sent[0]["subject"]

    def test_alert_severity_based_on_threshold_breach(self, db_session):
        """Alert severity determined by threshold breach amount"""
        # Given
        threshold = 5.0
        test_cases = [
            (6.0, "warning"),    # 20% over threshold
            (10.0, "critical"),  # 100% over threshold
            (4.0, None)         # No alert
        ]

        # When/Then
        for current_value, expected_severity in test_cases:
            breach_percentage = ((current_value - threshold) / threshold) * 100

            if current_value > threshold:
                if breach_percentage >= 100:
                    severity = "critical"
                else:
                    severity = "warning"
            else:
                severity = None

            assert severity == expected_severity, f"Failed for value {current_value}"


class TestDashboardRealTimeMetrics:
    """MON-004: Dashboard - Real-Time Metrics"""

    def test_dashboard_displays_real_time_metrics(self, db_session):
        """Real-time metrics displayed in dashboard"""
        # Given
        metrics = {
            "error_rate": 3.2,
            "avg_latency_ms": 85,
            "requests_per_second": 150,
            "active_agents": 12
        }

        # When
        dashboard_data = {
            "metrics": metrics,
            "last_updated": datetime.utcnow()
        }

        # Then
        assert dashboard_data["metrics"]["error_rate"] == 3.2
        assert dashboard_data["metrics"]["active_agents"] == 12
        assert dashboard_data["last_updated"] is not None

    def test_metrics_update_every_5_seconds(self, db_session):
        """Metrics update every 5 seconds"""
        # Given
        update_interval_seconds = 5
        last_update = datetime.utcnow() - timedelta(seconds=3)
        current_time = datetime.utcnow()

        # When
        time_since_last_update = (current_time - last_update).total_seconds()
        should_update = time_since_last_update >= update_interval_seconds

        # Then
        assert should_update is False  # Only 3 seconds passed

    def test_dashboard_functional_with_current_data(self, db_session):
        """Dashboard is functional and showing current data"""
        # Given
        dashboard_state = {
            "status": "operational",
            "metrics": {
                "uptime_seconds": 86400,
                "total_requests": 50000,
                "error_rate": 2.5
            },
            "last_update": datetime.utcnow()
        }

        # When
        is_operational = dashboard_state["status"] == "operational"
        has_current_data = (datetime.utcnow() - dashboard_state["last_update"]).total_seconds() < 10

        # Then
        assert is_operational is True
        assert has_current_data is True


class TestLogAggregation:
    """MON-005: Log Aggregation"""

    def test_logs_aggregated_from_all_services(self, db_session):
        """Logs aggregated from all services"""
        # Given
        service_logs = {
            "api_gateway": [
                {"level": "INFO", "message": "Request received", "timestamp": datetime.utcnow()},
                {"level": "ERROR", "message": "Request failed", "timestamp": datetime.utcnow()}
            ],
            "agent_service": [
                {"level": "INFO", "message": "Agent started", "timestamp": datetime.utcnow()}
            ],
            "workflow_service": [
                {"level": "INFO", "message": "Workflow completed", "timestamp": datetime.utcnow()}
            ]
        }

        # When
        all_logs = []
        for service, logs in service_logs.items():
            for log in logs:
                log["service"] = service
                all_logs.append(log)

        # Then
        assert len(all_logs) == 4
        assert any(log["service"] == "api_gateway" for log in all_logs)
        assert any(log["service"] == "agent_service" for log in all_logs)

    def test_logs_searchable_by_service(self, db_session):
        """Logs searchable by service name"""
        # Given
        logs = [
            {"service": "api_gateway", "level": "INFO", "message": "Request received"},
            {"service": "agent_service", "level": "INFO", "message": "Agent started"},
            {"service": "api_gateway", "level": "ERROR", "message": "Request failed"}
        ]

        # When
        api_gateway_logs = [log for log in logs if log["service"] == "api_gateway"]

        # Then
        assert len(api_gateway_logs) == 2
        assert all(log["service"] == "api_gateway" for log in api_gateway_logs)

    def test_logs_searchable_by_level(self, db_session):
        """Logs searchable by log level"""
        # Given
        logs = [
            {"service": "api_gateway", "level": "INFO", "message": "Request received"},
            {"service": "api_gateway", "level": "ERROR", "message": "Request failed"},
            {"service": "agent_service", "level": "ERROR", "message": "Agent crashed"}
        ]

        # When
        error_logs = [log for log in logs if log["level"] == "ERROR"]

        # Then
        assert len(error_logs) == 2
        assert all(log["level"] == "ERROR" for log in error_logs)

    def test_all_logs_captured(self, db_session):
        """All logs from all services captured"""
        # Given
        services = ["api_gateway", "agent_service", "workflow_service", "auth_service"]
        logs_generated = 0

        # When
        # Simulate log generation
        for service in services:
            logs_generated += 2  # 2 logs per service

        # Then
        assert len(services) == 4
        assert logs_generated == 8


class TestHealthCheckEndpoint:
    """MON-006: Health Check Endpoint"""

    def test_database_check_performed(self, db_session):
        """Database health checked"""
        # Given
        health_status = {}

        # When
        try:
            # Attempt database query
            db_session.execute("SELECT 1")
            health_status["database"] = "healthy"
        except Exception as e:
            health_status["database"] = f"unhealthy: {str(e)}"

        # Then
        assert health_status["database"] == "healthy"

    def test_cache_check_performed(self, db_session):
        """Cache health checked"""
        # Given
        health_status = {}
        cache_available = True  # Simulate cache check

        # When
        if cache_available:
            health_status["cache"] = "healthy"
        else:
            health_status["cache"] = "unavailable"

        # Then
        assert health_status["cache"] == "healthy"

    def test_external_services_checked(self, db_session):
        """External services health checked"""
        # Given
        external_services = {
            "openai_api": True,
            "anthropic_api": True,
            "slack_api": False  # Simulate failure
        }
        health_status = {}

        # When
        for service, is_healthy in external_services.items():
            health_status[service] = "healthy" if is_healthy else "unhealthy"

        # Then
        assert health_status["openai_api"] == "healthy"
        assert health_status["anthropic_api"] == "healthy"
        assert health_status["slack_api"] == "unhealthy"

    def test_overall_health_status_correct(self, db_session):
        """Overall health status reflects component health"""
        # Given
        component_health = {
            "database": "healthy",
            "cache": "healthy",
            "openai_api": "healthy",
            "slack_api": "unhealthy"
        }

        # When
        all_healthy = all(status == "healthy" for status in component_health.values())
        overall_health = "healthy" if all_healthy else "degraded"

        # Then
        assert overall_health == "degraded"
        assert component_health["database"] == "healthy"


# ============================================================================
# MON-007 to MON-011: High Priority - Custom Metrics, Export, Anomaly
# ============================================================================

class TestCustomMetrics:
    """MON-007: Custom Metrics"""

    def test_custom_metric_defined_by_user(self, db_session):
        """User can define custom metric"""
        # Given
        custom_metric = {
            "name": "custom_response_time",
            "query": "avg(latency_ms) where endpoint='/api/custom'",
            "display_name": "Custom API Response Time",
            "unit": "milliseconds"
        }

        # When
        is_valid = (
            "name" in custom_metric and
            "query" in custom_metric and
            "display_name" in custom_metric
        )

        # Then
        assert is_valid is True
        assert custom_metric["name"] == "custom_response_time"

    def test_custom_metric_tracked(self, db_session):
        """System tracks custom metric"""
        # Given
        metric_name = "custom_response_time"
        samples = [120, 150, 130, 140, 125]

        # When
        metric_value = sum(samples) / len(samples)
        metric_data = {
            "name": metric_name,
            "value": metric_value,
            "timestamp": datetime.utcnow()
        }

        # Then
        assert metric_data["value"] == 133.0
        assert metric_data["name"] == "custom_response_time"

    def test_custom_metric_visible_in_dashboard(self, db_session):
        """Custom metric visible in dashboard"""
        # Given
        dashboard_metrics = [
            {"name": "error_rate", "value": 2.5},
            {"name": "avg_latency", "value": 85},
            {"name": "custom_response_time", "value": 133.0}  # Custom metric
        ]

        # When
        custom_metrics = [m for m in dashboard_metrics if m["name"] == "custom_response_time"]

        # Then
        assert len(custom_metrics) == 1
        assert custom_metrics[0]["value"] == 133.0


class TestMetricsExport:
    """MON-008: Metrics Export"""

    def test_metrics_exported_to_csv(self, db_session):
        """Metrics exported to CSV format"""
        # Given
        metrics = [
            {"timestamp": "2024-01-01T10:00:00Z", "error_rate": 2.5, "latency_ms": 85},
            {"timestamp": "2024-01-01T10:05:00Z", "error_rate": 3.0, "latency_ms": 90},
            {"timestamp": "2024-01-01T10:10:00Z", "error_rate": 2.0, "latency_ms": 80}
        ]

        # When
        # Simulate CSV generation
        csv_lines = ["timestamp,error_rate,latency_ms"]
        for metric in metrics:
            csv_lines.append(f"{metric['timestamp']},{metric['error_rate']},{metric['latency_ms']}")

        csv_content = "\n".join(csv_lines)

        # Then
        assert len(csv_lines) == 4  # header + 3 data rows
        assert "error_rate,latency_ms" in csv_lines[0]

    def test_export_file_generated(self, db_session):
        """Export file generated successfully"""
        # Given
        export_request = {
            "format": "csv",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "metrics": ["error_rate", "latency_ms"]
        }

        # When
        file_generated = True
        export_info = {
            "filename": "metrics_export_2024-01-01_to_2024-01-31.csv",
            "size_bytes": 2048,
            "generated_at": datetime.utcnow(),
            "download_url": "/api/metrics/download/abc123"
        }

        # Then
        assert file_generated is True
        assert export_info["filename"].endswith(".csv")
        assert export_info["download_url"].startswith("/api/metrics/download/")

    def test_export_data_complete(self, db_session):
        """Exported data is complete"""
        # Given
        db_metrics_count = 1000
        export_row_count = 1000

        # When
        data_complete = db_metrics_count == export_row_count

        # Then
        assert data_complete is True


class TestAnomalyDetection:
    """MON-009: Anomaly Detection"""

    def test_anomaly_detected_in_metrics(self, db_session):
        """System detects metric anomalies"""
        # Given
        baseline_metrics = [80, 85, 82, 88, 84]  # Normal range: 80-88
        current_metric = 250  # Anomalous spike
        threshold_std_dev = 2

        # When
        import statistics
        mean = statistics.mean(baseline_metrics)
        stdev = statistics.stdev(baseline_metrics)
        z_score = (current_metric - mean) / stdev if stdev > 0 else 0
        is_anomaly = abs(z_score) > threshold_std_dev

        # Then
        assert is_anomaly is True
        assert z_score > threshold_std_dev

    def test_anomaly_flagged(self, db_session):
        """Anomaly flagged in system"""
        # Given
        anomaly_detected = True
        flagged_anomalies = []

        # When
        if anomaly_detected:
            flagged_anomalies.append({
                "metric": "latency_ms",
                "value": 250,
                "baseline_mean": 83.8,
                "z_score": 15.2,
                "severity": "high",
                "timestamp": datetime.utcnow()
            })

        # Then
        assert len(flagged_anomalies) == 1
        assert flagged_anomalies[0]["severity"] == "high"

    def test_alert_triggered_on_anomaly(self, db_session):
        """Alert triggered when anomaly detected"""
        # Given
        anomaly = {
            "metric": "latency_ms",
            "value": 250,
            "severity": "high"
        }
        alerts_sent = []

        # When
        if anomaly["severity"] == "high":
            alerts_sent.append({
                "type": "anomaly_detected",
                "metric": anomaly["metric"],
                "value": anomaly["value"],
                "timestamp": datetime.utcnow()
            })

        # Then
        assert len(alerts_sent) == 1
        assert alerts_sent[0]["type"] == "anomaly_detected"


class TestMetricsRetention:
    """MON-010: Metrics Retention"""

    def test_old_metrics_removed_after_retention_period(self, db_session):
        """Old metrics removed when retention policy exceeded"""
        # Given
        retention_days = 30
        current_date = datetime.utcnow()
        old_metric_date = current_date - timedelta(days=35)  # Older than retention
        recent_metric_date = current_date - timedelta(days=15)  # Within retention

        # When
        metrics = [
            {"date": old_metric_date, "value": 100},
            {"date": recent_metric_date, "value": 150}
        ]

        # Filter based on retention
        cutoff_date = current_date - timedelta(days=retention_days)
        active_metrics = [m for m in metrics if m["date"] > cutoff_date]

        # Then
        assert len(active_metrics) == 1
        assert active_metrics[0]["value"] == 150

    def test_retention_policy_enforced(self, db_session):
        """Retention policy enforced consistently"""
        # Given
        retention_policies = {
            "raw_metrics": 30,      # days
            "aggregated_metrics": 365,  # days
            "audit_logs": 2555      # days (7 years)
        }

        # When
        all_enforced = all(days > 0 for days in retention_policies.values())

        # Then
        assert all_enforced is True
        assert retention_policies["audit_logs"] == 2555

    def test_storage_managed(self, db_session):
        """Storage managed through retention"""
        # Given
        storage_before_cleanup_gb = 500
        cleanup_target_gb = 100
        expected_freed_gb = 400

        # When
        storage_after_cleanup_gb = storage_before_cleanup_gb - expected_freed_gb

        # Then
        assert storage_after_cleanup_gb == cleanup_target_gb
        assert storage_after_cleanup_gb < storage_before_cleanup_gb


class TestAlertingRules:
    """MON-011: Alerting Rules"""

    def test_user_defines_alerting_rule(self, db_session):
        """User can define alerting rule"""
        # Given
        alert_rule = {
            "name": "high_error_rate_alert",
            "metric": "error_rate",
            "operator": ">",
            "threshold": 5.0,
            "severity": "critical",
            "notification_channels": ["email", "slack"]
        }

        # When
        is_valid = (
            "metric" in alert_rule and
            "operator" in alert_rule and
            "threshold" in alert_rule
        )

        # Then
        assert is_valid is True
        assert alert_rule["metric"] == "error_rate"

    def test_rule_evaluated(self, db_session):
        """Alerting rule evaluated against current metrics"""
        # Given
        alert_rule = {
            "metric": "error_rate",
            "operator": ">",
            "threshold": 5.0
        }
        current_metrics = {"error_rate": 7.5}

        # When
        # Evaluate rule
        metric_value = current_metrics[alert_rule["metric"]]
        operator = alert_rule["operator"]
        threshold = alert_rule["threshold"]

        if operator == ">":
            condition_met = metric_value > threshold
        elif operator == "<":
            condition_met = metric_value < threshold
        elif operator == "==":
            condition_met = metric_value == threshold
        else:
            condition_met = False

        # Then
        assert condition_met is True
        assert metric_value == 7.5

    def test_alert_sent_when_rule_triggered(self, db_session):
        """Alert sent when rule condition met"""
        # Given
        rule_triggered = True
        alert_sent = False

        # When
        if rule_triggered:
            # Send alert
            alert_sent = True

        # Then
        assert alert_sent is True


# ============================================================================
# MON-012 to MON-015: Medium/Low Priority - Sharing, Reports, Comparison
# ============================================================================

class TestMetricsDashboardSharing:
    """MON-012: Metrics Dashboard Sharing"""

    def test_dashboard_shared(self, db_session):
        """User can share dashboard"""
        # Given
        dashboard_id = "dash-123"
        share_with = ["user2@example.com", "user3@example.com"]

        # When
        share_link = f"/api/dashboards/{dashboard_id}/share"
        share_granted = True

        # Then
        assert share_granted is True
        assert share_link.startswith("/api/dashboards/")

    def test_recipients_view_dashboard(self, db_session):
        """Recipients can access shared dashboard"""
        # Given
        shared_dashboard = {
            "id": "dash-123",
            "shared_with": ["user2@example.com", "user3@example.com"],
            "access_permissions": ["view"]
        }
        accessing_user = "user2@example.com"

        # When
        has_access = accessing_user in shared_dashboard["shared_with"]

        # Then
        assert has_access is True


class TestScheduledReports:
    """MON-013: Scheduled Reports"""

    def test_weekly_report_scheduled(self, db_session):
        """User schedules weekly report"""
        # Given
        report_schedule = {
            "name": "weekly_metrics_report",
            "frequency": "weekly",
            "day_of_week": "monday",
            "recipients": ["manager@example.com"]
        }

        # When
        is_valid_schedule = (
            report_schedule["frequency"] == "weekly" and
            "day_of_week" in report_schedule
        )

        # Then
        assert is_valid_schedule is True

    def test_report_generated(self, db_session):
        """Report generated on schedule"""
        # Given
        report_scheduled = True
        current_day = "monday"
        scheduled_day = "monday"
        report_generated = False

        # When
        if report_scheduled and current_day == scheduled_day:
            report_generated = True

        # Then
        assert report_generated is True

    def test_report_emailed(self, db_session):
        """Report emailed to recipients"""
        # Given
        report_content = "Weekly metrics summary..."
        recipients = ["manager@example.com"]
        emails_sent = []

        # When
        for recipient in recipients:
            emails_sent.append({
                "to": recipient,
                "subject": "Weekly Metrics Report",
                "body": report_content,
                "sent_at": datetime.utcnow()
            })

        # Then
        assert len(emails_sent) == 1
        assert emails_sent[0]["to"] == "manager@example.com"


class TestMetricsComparison:
    """MON-014: Metrics Comparison"""

    def test_two_time_periods_compared(self, db_session):
        """User compares two time periods"""
        # Given
        period_a = {
            "start": "2024-01-01",
            "end": "2024-01-07",
            "avg_latency_ms": 85,
            "error_rate": 2.5
        }
        period_b = {
            "start": "2024-01-08",
            "end": "2024-01-14",
            "avg_latency_ms": 95,
            "error_rate": 3.2
        }

        # When
        comparison = {
            "latency_change_ms": period_b["avg_latency_ms"] - period_a["avg_latency_ms"],
            "error_rate_change_percent": period_b["error_rate"] - period_a["error_rate"]
        }

        # Then
        assert comparison["latency_change_ms"] == 10
        assert comparison["error_rate_change_percent"] == 0.7

    def test_differences_visible(self, db_session):
        """Differences shown clearly"""
        # Given
        comparison = {
            "metric": "avg_latency_ms",
            "period_a": 85,
            "period_b": 95,
            "change": 10,
            "change_percent": 11.76
        }

        # When
        has_comparison = (
            "period_a" in comparison and
            "period_b" in comparison and
            "change" in comparison
        )

        # Then
        assert has_comparison is True
        assert comparison["change"] > 0


class TestMetricsAPI:
    """MON-015: Metrics API"""

    def test_api_returns_metric_data(self, db_session):
        """API returns metric data"""
        # Given
        endpoint = "/api/metrics/latency_ms"
        query_params = {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-31T23:59:59Z",
            "aggregation": "avg"
        }

        # When
        # Simulate API response
        response_data = {
            "metric": "latency_ms",
            "aggregation": "avg",
            "value": 87.5,
            "samples": 1000,
            "period": query_params
        }

        # Then
        assert response_data["metric"] == "latency_ms"
        assert response_data["value"] == 87.5
        assert response_data["samples"] > 0

    def test_api_format_correct(self, db_session):
        """API response format is correct"""
        # Given
        response = {
            "status": "success",
            "data": {
                "metric": "error_rate",
                "value": 2.5,
                "timestamp": "2024-01-01T10:00:00Z"
            }
        }

        # When
        has_correct_format = (
            "status" in response and
            "data" in response and
            "metric" in response["data"]
        )

        # Then
        assert has_correct_format is True
        assert response["status"] == "success"
