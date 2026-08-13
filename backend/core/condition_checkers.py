"""
Condition Checkers Module

Implements the actual condition checking logic for different condition types.
Each checker evaluates a specific business condition and returns the result.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, Optional
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from core.models import AgentExecution, ConditionMonitor, TeamMessage

logger = logging.getLogger(__name__)

# Condition type identifiers. ConditionMonitor.condition_type is persisted as a
# plain string (see condition_monitoring_service), so dispatch compares strings.
CONDITION_TYPE_INBOX_VOLUME = "inbox_volume"
CONDITION_TYPE_TASK_BACKLOG = "task_backlog"
CONDITION_TYPE_API_METRICS = "api_metrics"
CONDITION_TYPE_DATABASE_QUERY = "database_query"
CONDITION_TYPE_COMPOSITE = "composite"


class ConditionCheckers:
    """
    Condition checker implementations for different condition types.

    Supports:
    - inbox_volume: Check unread message counts
    - task_backlog: Check pending task/item counts
    - api_metrics: Check API error rates, response times
    - database_query: Run custom database queries
    - composite: AND/OR logic for multiple conditions
    """

    def __init__(self, db: Session):
        self.db = db

    def check_condition(self, monitor: ConditionMonitor) -> Dict[str, Any]:
        """
        Check a condition monitor and return the result.

        Args:
            monitor: The condition monitor to check

        Returns:
            Dictionary with:
                - triggered: bool - Whether condition is triggered
                - value: Any - Current value of the metric
                - metric_name: str - Human-readable metric name
        """
        condition_type = monitor.condition_type

        if condition_type == CONDITION_TYPE_INBOX_VOLUME:
            return self._check_inbox_volume(monitor)
        elif condition_type == CONDITION_TYPE_TASK_BACKLOG:
            return self._check_task_backlog(monitor)
        elif condition_type == CONDITION_TYPE_API_METRICS:
            return self._check_api_metrics(monitor)
        elif condition_type == CONDITION_TYPE_DATABASE_QUERY:
            return self._check_database_query(monitor)
        elif condition_type == CONDITION_TYPE_COMPOSITE:
            return self._check_composite(monitor)
        else:
            logger.warning(f"Unknown condition type: {condition_type}")
            return {
                "triggered": False,
                "value": None,
                "metric_name": f"Unknown type: {condition_type}",
            }

    def _check_inbox_volume(self, monitor: ConditionMonitor) -> Dict[str, Any]:
        """
        Check inbox volume condition.

        threshold_config: {"metric": "unread_count", "operator": ">", "value": 100}

        Returns:
            Current unread message count and whether threshold is exceeded
        """
        threshold = monitor.threshold_config
        metric = threshold.get("metric", "unread_count")
        operator = threshold.get("operator", ">")
        threshold_value = threshold.get("value", 100)

        # Count unread messages (simplified - count all TeamMessages)
        # In production, you'd filter by recipient, status, etc.
        current_value = self.db.query(func.count(TeamMessage.id)).scalar()

        triggered = self._compare_values(current_value, operator, threshold_value)

        return {
            "triggered": triggered,
            "value": current_value,
            "metric_name": f"Unread messages",
            "details": f"Current: {current_value}, Threshold: {operator} {threshold_value}",
        }

    def _check_task_backlog(self, monitor: ConditionMonitor) -> Dict[str, Any]:
        """
        Check task backlog condition.

        threshold_config: {"metric": "pending_count", "operator": ">", "value": 50}

        Returns:
            Current pending task count and whether threshold is exceeded
        """
        threshold = monitor.threshold_config
        metric = threshold.get("metric", "pending_count")
        operator = threshold.get("operator", ">")
        threshold_value = threshold.get("value", 50)

        # Count agent executions with status="pending" or similar
        # In production, you'd query actual task tables
        current_value = self.db.query(func.count(AgentExecution.id)).filter(
            AgentExecution.status == "pending"
        ).scalar()

        triggered = self._compare_values(current_value, operator, threshold_value)

        return {
            "triggered": triggered,
            "value": current_value,
            "metric_name": f"Pending tasks",
            "details": f"Current: {current_value}, Threshold: {operator} {threshold_value}",
        }

    def _check_api_metrics(self, monitor: ConditionMonitor) -> Dict[str, Any]:
        """
        Check API metrics condition.

        threshold_config: {"metric": "error_rate", "operator": ">", "value": 0.05, "window": "5m"}

        Supported metrics:
        - error_rate: Failed requests / Total requests
        - response_time_p95: 95th percentile response time
        - request_count: Total requests in time window

        Returns:
            Current metric value and whether threshold is exceeded
        """
        threshold = monitor.threshold_config
        metric = threshold.get("metric", "error_rate")
        operator = threshold.get("operator", ">")
        threshold_value = threshold.get("value", 0.05)
        window_minutes = threshold.get("window", "5m")

        # Parse the configured window into minutes. Supports "5m", "15m",
        # "1h", "2h". Previously the configured window was captured into
        # ``window_minutes`` (used only for the display string) while the
        # actual query cutoff was hardcoded to 5 minutes — so an operator
        # setting a 1-hour window got a 5-minute measurement.
        _wm = window_minutes if isinstance(window_minutes, (int, float)) else str(window_minutes)
        if isinstance(_wm, (int, float)):
            window_mins_float = float(_wm)
        elif isinstance(_wm, str):
            _wm_lower = _wm.strip().lower()
            try:
                if _wm_lower.endswith("h"):
                    window_mins_float = float(_wm_lower[:-1]) * 60
                elif _wm_lower.endswith("m"):
                    window_mins_float = float(_wm_lower[:-1])
                else:
                    window_mins_float = float(_wm_lower)
            except ValueError:
                window_mins_float = 5.0
        else:
            window_mins_float = 5.0

        # Calculate time window from the configured value.
        window_start = datetime.now(timezone.utc) - timedelta(minutes=window_mins_float)

        if metric == "error_rate":
            # Count failed vs total executions. NOTE: AgentExecution has no
            # ``created_at`` column — the time anchor is ``started_at`` (the
            # model's server_default-now column). The old code referenced
            # ``AgentExecution.created_at``, which raised AttributeError and
            # made every api_metrics check fail silently.
            total_count = self.db.query(func.count(AgentExecution.id)).filter(
                AgentExecution.started_at >= window_start
            ).scalar()

            failed_count = self.db.query(func.count(AgentExecution.id)).filter(
                AgentExecution.started_at >= window_start,
                AgentExecution.status == "failed",
            ).scalar()

            if total_count > 0:
                current_value = failed_count / total_count
            else:
                current_value = 0.0

            metric_name = f"API error rate (last {window_minutes})"

        elif metric == "response_time_p95":
            # Calculate p95 response time
            # For simplicity, return average response time
            # In production, you'd use actual p95 calculation
            executions = self.db.query(AgentExecution).filter(
                AgentExecution.started_at >= window_start
            ).all()

            if executions:
                durations = []
                for ex in executions:
                    # Calculate duration if has timing info
                    if ex.started_at and ex.completed_at:
                        duration = (ex.completed_at - ex.started_at).total_seconds()
                        durations.append(duration)

                if durations:
                    current_value = sum(durations) / len(durations)
                else:
                    current_value = 0.0
            else:
                current_value = 0.0

            metric_name = f"API response time (last {window_minutes})"

        elif metric == "request_count":
            # Count total executions
            current_value = self.db.query(func.count(AgentExecution.id)).filter(
                AgentExecution.started_at >= window_start
            ).scalar()

            metric_name = f"API request count (last {window_minutes})"

        else:
            logger.warning(f"Unknown API metric: {metric}")
            current_value = 0
            metric_name = f"Unknown metric: {metric}"

        triggered = self._compare_values(current_value, operator, threshold_value)

        return {
            "triggered": triggered,
            "value": current_value,
            "metric_name": metric_name,
            "details": f"Current: {current_value:.4f}, Threshold: {operator} {threshold_value}",
        }

    def _check_database_query(self, monitor: ConditionMonitor) -> Dict[str, Any]:
        """
        Check custom database query condition.

        threshold_config: {"query": "SELECT COUNT(*) FROM table", "operator": ">", "value": 100}

        WARNING: Executes raw SQL queries. Use with caution and validate inputs.

        Returns:
            Query result and whether threshold is exceeded
        """
        threshold = monitor.threshold_config
        query = threshold.get("query", "")
        operator = threshold.get("operator", ">")
        threshold_value = threshold.get("value", 100)

        try:
            # Execute custom query. The query string MUST be wrapped in
            # ``text()`` — SQLAlchemy 2.0 rejects raw strings in
            # ``Session.execute`` with ArgumentError. The old code passed the
            # raw string, so every database_query monitor caught that
            # ArgumentError and silently reported triggered=False.
            result = self.db.execute(text(query)).scalar()

            if result is None:
                current_value = 0
            else:
                current_value = result

            triggered = self._compare_values(current_value, operator, threshold_value)

            return {
                "triggered": triggered,
                "value": current_value,
                "metric_name": "Database query result",
                "details": f"Query result: {current_value}, Threshold: {operator} {threshold_value}",
            }

        except Exception as e:
            logger.error(f"Error executing database query: {e}")
            return {
                "triggered": False,
                "value": None,
                "metric_name": "Database query",
                "details": f"Query error: {str(e)}",
            }

    def _check_composite(self, monitor: ConditionMonitor) -> Dict[str, Any]:
        """
        Check composite condition with AND/OR logic.

        threshold_config: {"composite_logic": "AND", "composite_conditions": [...]}

        Returns:
            Composite condition result and whether triggered
        """
        logic = monitor.composite_logic  # "AND" or "OR"
        conditions = monitor.composite_conditions or []

        if not conditions:
            return {
                "triggered": False,
                "value": {},
                "metric_name": "Composite (empty)",
                "details": "No sub-conditions defined",
            }

        results = []
        all_triggered = True
        any_triggered = False

        for i, condition_config in enumerate(conditions):
            # Create a temporary monitor for the sub-condition. The
            # ConditionMonitor stub has no agent_id/agent_name/threshold_config
            # columns, so those kwargs must NOT be passed to the constructor
            # (TypeError); set them as plain attributes afterwards — mirroring
            # ConditionMonitoringService._hydrate_config.
            temp_monitor = ConditionMonitor(
                user_id=getattr(monitor, "user_id", "default"),
                name=f"{monitor.name}_sub_{i}",
                condition_type=condition_config.get("condition_type", "inbox_volume"),
                condition_config={
                    "threshold_config": condition_config.get("threshold_config", {})
                },
            )
            temp_monitor.agent_id = getattr(monitor, "agent_id", None)
            temp_monitor.agent_name = getattr(monitor, "agent_name", None)
            temp_monitor.threshold_config = condition_config.get("threshold_config", {})

            # Check the sub-condition
            result = self.check_condition(temp_monitor)
            results.append(result)

            if result["triggered"]:
                any_triggered = True
            else:
                all_triggered = False

        # Apply logic
        if logic == "AND":
            triggered = all_triggered
        else:  # OR
            triggered = any_triggered

        return {
            "triggered": triggered,
            "value": {r["metric_name"]: r["value"] for r in results},
            "metric_name": f"Composite ({logic} of {len(results)} conditions)",
            "details": f"Logic: {logic}, All triggered: {all_triggered}, Any triggered: {any_triggered}",
            "sub_conditions": results,
        }

    def _compare_values(
        self,
        current_value: Any,
        operator: str,
        threshold_value: Any
    ) -> bool:
        """
        Compare current value to threshold using operator.

        Operators: >, >=, <, <=, ==, !=
        """
        try:
            if operator == ">":
                return current_value > threshold_value
            elif operator == ">=":
                return current_value >= threshold_value
            elif operator == "<":
                return current_value < threshold_value
            elif operator == "<=":
                return current_value <= threshold_value
            elif operator == "==":
                return current_value == threshold_value
            elif operator == "=":
                return current_value == threshold_value
            elif operator == "!=":
                return current_value != threshold_value
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False

        except Exception as e:
            logger.error(f"Error comparing values: {e}")
            return False


class ConditionCheckerFactory:
    """Factory for creating condition checkers."""

    @staticmethod
    def create_checker(condition_type: str, db: Session):
        """
        Create a condition checker for the given type.

        Args:
            condition_type: The type of condition checker to create
            db: Database session

        Returns:
            Condition checker instance

        Raises:
            ValueError: If condition type is not supported
        """
        # All checkers are implemented in ConditionCheckers class
        return ConditionCheckers(db)
