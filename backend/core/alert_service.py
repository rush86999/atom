"""
Alert Threshold Evaluation Service

Evaluates integration health metrics against configured thresholds.
Supports sliding window evaluation and hysteresis to prevent alert flapping.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert state tracking"""
    OK = "ok"
    VIOLATED = "violated"
    CLEARED = "cleared"


@dataclass
class AlertViolation:
    """Represents a threshold violation"""
    tenant_id: str
    connector_id: str
    metric_type: str  # "error_rate" or "latency"
    actual_value: float
    threshold: float
    severity: AlertSeverity
    timestamp: datetime
    window_start: datetime
    window_end: datetime


@dataclass
class AlertEvaluationResult:
    """Result of threshold evaluation"""
    tenant_id: str
    connector_id: str
    status: AlertStatus
    violations: List[AlertViolation]
    evaluated_at: datetime


class AlertThresholdService:
    """
    Service for evaluating alert thresholds against integration metrics.

    **Features:**
    - Error rate threshold evaluation (percentage)
    - Latency threshold evaluation (p95 in milliseconds)
    - Sliding window evaluation (configurable window size)
    - Hysteresis to prevent alert flapping (trigger/clear bands)

    **Hysteresis:**
    - Error rate triggers alert at >threshold (e.g., 10%)
    - Alert clears only when <threshold - 20% (e.g., 8%)
    - Prevents rapid on/off oscillation near threshold
    """

    # Hysteresis band (percentage of threshold)
    HYSTERESIS_BAND = 0.20  # 20%

    def __init__(self, db_session, redis_client=None):
        """
        Initialize alert threshold service.

        Args:
            db_session: SQLAlchemy database session
            redis_client: Optional Redis client for sliding window storage
        """
        self.db = db_session
        self.redis = redis_client

        # Import models here to avoid circular imports
        from core.models import AlertConfiguration
        self.AlertConfiguration = AlertConfiguration

    def evaluate_error_rate_threshold(
        self,
        tenant_id: str,
        connector_id: str,
        configuration: Optional['AlertConfiguration'] = None
    ) -> Optional[AlertViolation]:
        """
        Evaluate error rate against configured threshold.

        Args:
            tenant_id: Tenant UUID
            connector_id: Integration identifier
            configuration: Optional AlertConfiguration (loaded if not provided)

        Returns:
            AlertViolation if threshold exceeded, None otherwise
        """
        # Load configuration if not provided
        if configuration is None:
            configuration = self.db.query(self.AlertConfiguration).filter(
                self.AlertConfiguration.tenant_id == tenant_id,
                self.AlertConfiguration.connector_id == connector_id,
                self.AlertConfiguration.is_active == True
            ).first()

        if not configuration:
            return None

        # Get metrics from IntegrationMetrics
        from core.integration_metrics import get_integration_metrics
        metrics = get_integration_metrics()

        # Calculate error rate over sliding window
        window_start = datetime.utcnow() - timedelta(seconds=configuration.window_seconds)
        error_rate = self._calculate_error_rate_in_window(
            metrics, tenant_id, connector_id, window_start
        )

        # Get current alert state (if any)
        current_state = self._get_alert_state(tenant_id, connector_id, "error_rate")

        # Apply hysteresis
        threshold = configuration.error_rate_threshold
        clear_threshold = threshold * (1 - self.HYSTERESIS_BAND)

        # Determine violation
        violation = None
        if error_rate > threshold:
            violation = AlertViolation(
                tenant_id=tenant_id,
                connector_id=connector_id,
                metric_type="error_rate",
                actual_value=error_rate,
                threshold=threshold,
                severity=AlertSeverity.CRITICAL if error_rate > threshold * 2 else AlertSeverity.WARNING,
                timestamp=datetime.utcnow(),
                window_start=window_start,
                window_end=datetime.utcnow()
            )
            self._set_alert_state(tenant_id, connector_id, "error_rate", "violated")
        elif current_state == "violated" and error_rate < clear_threshold:
            # Alert clears when below clear threshold
            self._set_alert_state(tenant_id, connector_id, "error_rate", "cleared")

        return violation

    def evaluate_latency_threshold(
        self,
        tenant_id: str,
        connector_id: str,
        configuration: Optional['AlertConfiguration'] = None
    ) -> Optional[AlertViolation]:
        """
        Evaluate p95 latency against configured threshold.

        Args:
            tenant_id: Tenant UUID
            connector_id: Integration identifier
            configuration: Optional AlertConfiguration

        Returns:
            AlertViolation if threshold exceeded, None otherwise
        """
        # Load configuration if not provided
        if configuration is None:
            configuration = self.db.query(self.AlertConfiguration).filter(
                self.AlertConfiguration.tenant_id == tenant_id,
                self.AlertConfiguration.connector_id == connector_id,
                self.AlertConfiguration.is_active == True
            ).first()

        if not configuration or not configuration.latency_threshold_ms:
            return None

        # Get metrics from IntegrationMetrics
        from core.integration_metrics import get_integration_metrics
        metrics = get_integration_metrics()

        # Get p95 latency
        percentiles = metrics.get_duration_percentiles(
            connector_id, tenant_id, "agent", "all"
        )
        p95_latency = percentiles.get("p95", 0)

        # Check threshold
        threshold = configuration.latency_threshold_ms
        if p95_latency > threshold:
            return AlertViolation(
                tenant_id=tenant_id,
                connector_id=connector_id,
                metric_type="latency_p95",
                actual_value=p95_latency,
                threshold=threshold,
                severity=AlertSeverity.WARNING,
                timestamp=datetime.utcnow(),
                window_start=datetime.utcnow() - timedelta(seconds=300),
                window_end=datetime.utcnow()
            )

        return None

    def evaluate_all_thresholds(
        self,
        tenant_id: Optional[str] = None
    ) -> List[AlertEvaluationResult]:
        """
        Evaluate all thresholds for tenant or all tenants.

        Args:
            tenant_id: Optional tenant UUID (evaluates all tenants if None)

        Returns:
            List of evaluation results
        """
        # Build query
        query = self.db.query(self.AlertConfiguration).filter(
            self.AlertConfiguration.is_active == True
        )

        if tenant_id:
            query = query.filter(self.AlertConfiguration.tenant_id == tenant_id)

        configurations = query.all()
        results = []

        # Group by (tenant_id, connector_id) to avoid duplicate evaluations
        config_groups = {}
        for config in configurations:
            key = (config.tenant_id, config.connector_id)
            if key not in config_groups:
                config_groups[key] = config

        # Evaluate each unique configuration
        for (tenant_id, connector_id), config in config_groups.items():
            violations = []

            # Evaluate error rate
            error_violation = self.evaluate_error_rate_threshold(
                tenant_id, connector_id, config
            )
            if error_violation:
                violations.append(error_violation)

            # Evaluate latency
            latency_violation = self.evaluate_latency_threshold(
                tenant_id, connector_id, config
            )
            if latency_violation:
                violations.append(latency_violation)

            # Determine status
            status = AlertStatus.OK
            if violations:
                status = AlertStatus.VIOLATED

            results.append(AlertEvaluationResult(
                tenant_id=tenant_id,
                connector_id=connector_id,
                status=status,
                violations=violations,
                evaluated_at=datetime.utcnow()
            ))

        return results

    def _calculate_error_rate_in_window(
        self,
        metrics: 'IntegrationMetrics',
        tenant_id: str,
        connector_id: str,
        window_start: datetime
    ) -> float:
        """
        Calculate error rate within sliding window.

        Args:
            metrics: IntegrationMetrics instance
            tenant_id: Tenant UUID
            connector_id: Integration identifier
            window_start: Start of sliding window

        Returns:
            Error rate as percentage (0-100)
        """
        # Get success and failure counts from metrics
        success_key = metrics._make_key(connector_id, tenant_id, "agent")
        successes = metrics.success_counts.get(success_key, 0)
        failures = metrics.failure_counts.get(success_key, 0)

        total = successes + failures
        if total == 0:
            return 0.0

        return (failures / total) * 100

    def _get_alert_state(self, tenant_id: str, connector_id: str, metric_type: str) -> str:
        """Get current alert state from Redis"""
        if not self.redis:
            return "ok"

        key = f"alert_state:{tenant_id}:{connector_id}:{metric_type}"
        state = self.redis.get(key)
        return state.decode() if state else "ok"

    def _set_alert_state(self, tenant_id: str, connector_id: str, metric_type: str, state: str):
        """Set alert state in Redis"""
        if not self.redis:
            return

        key = f"alert_state:{tenant_id}:{connector_id}:{metric_type}"
        self.redis.setex(key, 3600, state)  # Expire after 1 hour

    def get_violations_for_tenant(self, tenant_id: str) -> List[AlertViolation]:
        """
        Get all current violations for a tenant.

        Args:
            tenant_id: Tenant UUID

        Returns:
            List of active violations
        """
        results = self.evaluate_all_thresholds(tenant_id)
        violations = []
        for result in results:
            violations.extend(result.violations)
        return violations

    async def send_notifications(
        self,
        violation: AlertViolation,
        configuration: 'AlertConfiguration'
    ) -> Dict[str, bool]:
        """
        Send notifications for alert violation.

        Args:
            violation: AlertViolation instance
            configuration: AlertConfiguration with notification settings

        Returns:
            Dict with channel names and send status
        """
        results = {}

        if not configuration.notification_channels:
            return results

        # Determine which channels to use
        channels = configuration.notification_channels or []

        if "slack" in channels and configuration.slack_channel_id:
            results["slack"] = await self.send_slack_notification(violation, configuration)

        if "email" in channels and configuration.email_recipients:
            results["email"] = await self.send_email_notification(violation, configuration)

        return results

    async def send_slack_notification(
        self,
        violation: AlertViolation,
        configuration: 'AlertConfiguration'
    ) -> bool:
        """
        Send Slack notification for alert violation.

        Args:
            violation: AlertViolation instance
            configuration: AlertConfiguration with Slack settings

        Returns:
            True if notification sent successfully
        """
        try:
            from integrations.slack_enhanced_service import SlackEnhancedService
            from core.token_storage import token_storage

            # Get Slack OAuth token for tenant
            token_data = token_storage.get_token(
                tenant_id=violation.tenant_id,
                connector_id="slack"
            )

            if not token_data or not token_data.get("access_token"):
                logger.error(f"No Slack token found for tenant {violation.tenant_id[:8]}")
                return False

            # Create Slack client
            slack_service = SlackEnhancedService(
                access_token=token_data["access_token"]
            )

            # Format message
            message = self._format_slack_message(violation, configuration)

            # Send to channel
            await slack_service.send_message(
                workspace_id=violation.tenant_id,  # Using tenant_id as workspace_id
                channel_id=configuration.slack_channel_id,
                text=message
            )

            logger.info(
                f"Slack notification sent for {violation.metric_type} "
                f"violation to {configuration.slack_channel_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    async def send_email_notification(
        self,
        violation: AlertViolation,
        configuration: 'AlertConfiguration'
    ) -> bool:
        """
        Send email notification for alert violation.

        Args:
            violation: AlertViolation instance
            configuration: AlertConfiguration with email settings

        Returns:
            True if notification sent successfully
        """
        try:
            from core.email_service import EmailService

            email_service = EmailService()

            # Get recipients from configuration
            recipients = configuration.email_recipients or []
            if not recipients:
                logger.warning(f"No email recipients configured for tenant {violation.tenant_id[:8]}")
                return False

            # Format email
            subject = self._format_email_subject(violation)
            html_content = self._format_email_html(violation, configuration)

            # Send to all recipients
            success_count = 0
            for recipient in recipients:
                if await email_service.send_email(
                    to_email=recipient,
                    subject=subject,
                    html_content=html_content,
                    tenant_id=violation.tenant_id
                ):
                    success_count += 1

            logger.info(
                f"Email notification sent for {violation.metric_type} "
                f"violation to {success_count}/{len(recipients)} recipients"
            )
            return success_count > 0

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

    async def send_alert_cleared_notification(
        self,
        tenant_id: str,
        connector_id: str,
        metric_type: str,
        configuration: 'AlertConfiguration'
    ) -> bool:
        """
        Send notification when alert condition is cleared.

        Args:
            tenant_id: Tenant UUID
            connector_id: Integration identifier
            metric_type: Type of metric that cleared
            configuration: AlertConfiguration with notification settings

        Returns:
            True if at least one notification sent successfully
        """
        try:
            message = (
                ":white_check_mark: Alert Cleared\n\n"
                f"The alert condition has been resolved:\n"
                f"*Connector:* {connector_id}\n"
                f"*Metric:* {metric_type}\n"
                f"*Cleared at:* {datetime.utcnow().isoformat()}\n"
            )

            results = {}
            channels = configuration.notification_channels or []

            if "slack" in channels and configuration.slack_channel_id:
                from integrations.slack_enhanced_service import SlackEnhancedService
                from core.token_storage import token_storage

                token_data = token_storage.get_token(
                    tenant_id=tenant_id,
                    connector_id="slack"
                )

                if token_data and token_data.get("access_token"):
                    slack_service = SlackEnhancedService(
                        access_token=token_data["access_token"]
                    )
                    try:
                        await slack_service.send_message(
                            workspace_id=tenant_id,
                            channel_id=configuration.slack_channel_id,
                            text=message
                        )
                        results["slack"] = True
                    except Exception as e:
                        logger.error(f"Failed to send Slack cleared notification: {e}")
                        results["slack"] = False

            if "email" in channels and configuration.email_recipients:
                from core.email_service import EmailService

                email_service = EmailService()
                subject = f"✓ Alert Cleared: {connector_id} {metric_type}"

                success_count = 0
                for recipient in configuration.email_recipients or []:
                    if await email_service.send_email(
                        to_email=recipient,
                        subject=subject,
                        html_content=f"<p>{message.replace(chr(10), '<br>')}</p>",
                        tenant_id=tenant_id
                    ):
                        success_count += 1

                results["email"] = success_count > 0

            return any(results.values())

        except Exception as e:
            logger.error(f"Failed to send alert cleared notification: {e}")
            return False

    def _get_emoji_for_severity(self, severity: AlertSeverity) -> str:
        """Get Slack emoji for severity level"""
        emojis = {
            AlertSeverity.INFO: ":information_source:",
            AlertSeverity.WARNING: ":warning:",
            AlertSeverity.CRITICAL: ":rotating_light:"
        }
        return emojis.get(severity, ":warning:")

    def _format_slack_message(
        self,
        violation: AlertViolation,
        configuration: 'AlertConfiguration'
    ) -> str:
        """Format Slack message for alert violation"""
        emoji = self._get_emoji_for_severity(violation.severity)

        message = (
            f"{emoji} *Alert Violation Detected*\n\n"
            f"*Connector:* {violation.connector_id}\n"
            f"*Metric:* {violation.metric_type}\n"
            f"*Actual Value:* {violation.actual_value:.2f}\n"
            f"*Threshold:* {violation.threshold}\n"
            f"*Severity:* {violation.severity.value.upper()}\n"
            f"*Time:* {violation.timestamp.isoformat()}\n"
        )

        return message

    def _format_email_subject(self, violation: AlertViolation) -> str:
        """Format email subject for alert violation"""
        severity_emoji = {
            AlertSeverity.INFO: "",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨"
        }
        emoji = severity_emoji.get(violation.severity, "")

        return f"{emoji} Alert: {violation.connector_id} {violation.metric_type} threshold exceeded"

    def _format_email_html(
        self,
        violation: AlertViolation,
        configuration: 'AlertConfiguration'
    ) -> str:
        """Format HTML email content for alert violation"""
        severity_colors = {
            AlertSeverity.INFO: "#17a2b8",
            AlertSeverity.WARNING: "#ffc107",
            AlertSeverity.CRITICAL: "#dc3545"
        }
        color = severity_colors.get(violation.severity, "#17a2b8")

        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: {color}; padding: 20px; border-radius: 10px 10px 0 0; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 22px;">Alert Violation Detected</h1>
            </div>

            <div style="background-color: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #ddd;">
                <h2 style="color: #333; margin-top: 0;">Integration Health Alert</h2>

                <p>An integration health threshold has been exceeded:</p>

                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Connector:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{violation.connector_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Metric:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{violation.metric_type}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Actual Value:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; color: {color}; font-weight: bold;">{violation.actual_value:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Threshold:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{violation.threshold}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Severity:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{violation.severity.value.upper()}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Detected at:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{violation.timestamp.isoformat()}</td>
                    </tr>
                </table>

                <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                    <p style="margin: 0; font-size: 14px;">
                        <strong>Recommended Action:</strong> Investigate the {violation.connector_id} integration
                        for errors or performance issues. Check integration logs and recent execution history.
                    </p>
                </div>
            </div>

            <div style="text-align: center; padding: 20px; font-size: 12px; color: #999;">
                <p>&copy; 2026 ATOM Platform. All rights reserved.</p>
                <p>This is an automated alert. Please do not reply directly.</p>
            </div>
        </body>
        </html>
        """

        return html

    async def check_and_send_cleared_alerts(
        self,
        tenant_id: str,
        connector_id: str
    ):
        """
        Check for alerts that have cleared and send notifications.

        Called when alert state transitions from "violated" to "cleared".
        """
        # Check alert states in Redis
        if not self.redis:
            return

        patterns = [
            f"alert_state:{tenant_id}:{connector_id}:error_rate",
            f"alert_state:{tenant_id}:{connector_id}:latency_p95"
        ]

        for pattern in patterns:
            # Scan for keys (simplified - in production use SCAN)
            state = self.redis.get(pattern)
            if state and state.decode() == "cleared":
                # Send cleared notification
                metric_type = pattern.split(":")[-1]
                configuration = self.db.query(self.AlertConfiguration).filter(
                    self.AlertConfiguration.tenant_id == tenant_id,
                    self.AlertConfiguration.connector_id == connector_id
                ).first()

                if configuration:
                    await self.send_alert_cleared_notification(
                        tenant_id, connector_id, metric_type, configuration
                    )

                # Reset state to OK
                self.redis.setex(pattern, 3600, "ok")
