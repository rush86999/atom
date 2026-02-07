"""
Failure Prediction Module for AI Debug System

Analyzes historical patterns to predict:
- Failure probability for operations
- Resource exhaustion forecasting
- Component failure risk assessment
- Proactive alerts before failures occur

Example:
    predictor = FailurePredictor(db_session)

    # Predict failure probability for an operation
    probability = await predictor.predict_operation_failure(
        component_type="agent",
        component_id="agent-123",
        operation_type="data_processing"
    )
    # Returns: {"probability": 0.75, "confidence": 0.80, "factors": [...]}
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case

from core.models import (
    DebugEvent,
    DebugMetric,
    DebugInsight,
    DebugEventType,
)
from core.structured_logger import StructuredLogger


class FailurePredictor:
    """
    Predicts failures based on historical patterns.

    Analyzes historical debug data to identify patterns that
    precede failures and uses them to predict future issues.
    """

    def __init__(
        self,
        db_session: Session,
        lookback_days: int = 30,
        min_samples: int = 100,
    ):
        """
        Initialize failure predictor.

        Args:
            db_session: SQLAlchemy database session
            lookback_days: Days of historical data to analyze
            min_samples: Minimum samples for reliable predictions
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session
        self.lookback_days = lookback_days
        self.min_samples = min_samples

    async def predict_operation_failure(
        self,
        component_type: str,
        component_id: str,
        operation_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Predict failure probability for an operation.

        Args:
            component_type: Component type
            component_id: Component ID
            operation_type: Type of operation (optional)

        Returns:
            Prediction with probability and factors
        """
        try:
            time_filter = datetime.utcnow() - timedelta(days=self.lookback_days)

            # Get historical operations for this component
            operations = (
                self.db.query(
                    DebugEvent.correlation_id,
                    func.min(DebugEvent.timestamp).label("start_time"),
                    func.max(DebugEvent.timestamp).label("end_time"),
                    func.count(DebugEvent.id).label("event_count"),
                    func.sum(
                        case(
                            (DebugEvent.level.in_(["ERROR", "CRITICAL"]), 1),
                            else_=0
                        )
                    ).label("error_count"),
                )
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .group_by(DebugEvent.correlation_id)
                .all()
            )

            if not operations:
                return {
                    "probability": 0.5,  # Unknown
                    "confidence": 0.0,
                    "factors": ["insufficient_historical_data"],
                }

            # Analyze patterns
            successful_ops = [op for op in operations if op.error_count == 0]
            failed_ops = [op for op in operations if op.error_count > 0]

            total_ops = len(operations)
            success_rate = len(successful_ops) / total_ops if total_ops > 0 else 0

            # Calculate base failure probability
            failure_prob = 1.0 - success_rate

            # Analyze contributing factors
            factors = []
            confidence = 0.5

            # Factor 1: Recent error rate (last 10 operations)
            recent_ops = operations[-10:] if len(operations) >= 10 else operations
            recent_error_rate = sum(op.error_count for op in recent_ops) / sum(op.event_count for op in recent_ops)

            if recent_error_rate > 0.3:  # 30% recent error rate
                factors.append({
                    "factor": "high_recent_error_rate",
                    "value": recent_error_rate,
                    "weight": 0.3,
                })
                confidence += 0.2

            # Factor 2: Trend (improving or degrading)
            if len(operations) >= 20:
                first_half = operations[:len(operations)//2]
                second_half = operations[len(operations)//2:]

                first_half_error_rate = sum(op.error_count for op in first_half) / sum(op.event_count for op in first_half)
                second_half_error_rate = sum(op.error_count for op in second_half) / sum(op.event_count for op in second_half)

                if second_half_error_rate > first_half_error_rate * 1.2:
                    factors.append({
                        "factor": "degrading_trend",
                        "value": second_half_error_rate / first_half_error_rate,
                        "weight": 0.2,
                    })
                    confidence += 0.15

            # Factor 3: Event volume (overload indicator)
            avg_event_count = sum(op.event_count for op in operations) / len(operations)
            if avg_event_count > 100:
                factors.append({
                    "factor": "high_event_volume",
                    "value": avg_event_count,
                    "weight": 0.1,
                })
                confidence += 0.1

            # Calculate weighted probability
            weighted_prob = failure_prob
            if factors:
                weight_sum = sum(f["weight"] for f in factors)
                adjustment = sum(f.get("value", 0) * f["weight"] for f in factors) / weight_sum
                weighted_prob = min(0.95, failure_prob + adjustment)

            # Normalize confidence based on sample size
            sample_size_confidence = min(1.0, len(operations) / self.min_samples)
            confidence = min(1.0, confidence * sample_size_confidence)

            return {
                "probability": weighted_prob,
                "confidence": confidence,
                "factors": factors,
                "historical_operations": total_ops,
                "success_rate": success_rate,
                "component_type": component_type,
                "component_id": component_id,
            }

        except Exception as e:
            self.logger.error(
                "Failed to predict operation failure",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return {
                "probability": 0.5,
                "confidence": 0.0,
                "factors": ["prediction_error"],
            }

    async def predict_resource_exhaustion(
        self,
        component_type: str,
        resource_type: str = "memory",  # memory, cpu, disk
    ) -> Optional[Dict[str, Any]]:
        """
        Predict resource exhaustion based on usage trends.

        Args:
            component_type: Component type to analyze
            resource_type: Type of resource (memory, cpu, disk)

        Returns:
            Prediction with time to exhaustion
        """
        try:
            time_filter = datetime.utcnow() - timedelta(days=7)  # Look at last 7 days

            # Get resource metrics
            metrics = (
                self.db.query(DebugMetric)
                .filter(
                    and_(
                        DebugMetric.metric_name == f"{resource_type}_usage",
                        DebugMetric.component_type == component_type,
                        DebugMetric.timestamp >= time_filter,
                    )
                )
                .order_by(DebugMetric.timestamp)
                .all()
            )

            if len(metrics) < 100:  # Need sufficient data
                return None

            # Extract values and timestamps
            values = [(m.timestamp, m.value) for m in metrics]

            # Calculate trend (linear regression)
            trend = self._calculate_trend(values)

            if trend > 0.01:  # Positive trend (increasing usage)
                # Extrapolate when usage will hit 100%
                current_usage = values[-1][1]
                time_to_exhaustion_hours = (100 - current_usage) / trend * 24  # Assuming trend is per day

                if time_to_exhaustion_hours < 168:  # Less than 1 week
                    return {
                        "resource_type": resource_type,
                        "component_type": component_type,
                        "current_usage_percent": current_usage,
                        "trend_slope_per_day": trend * 100,
                        "predicted_exhaustion_hours": time_to_exhaustion_hours,
                        "predicted_exhaustion_date": datetime.utcnow() + timedelta(hours=time_to_exhaustion_hours),
                        "urgency": "critical" if time_to_exhaustion_hours < 24 else "warning",
                        "confidence": 0.75,
                    }

            return None

        except Exception as e:
            self.logger.error(
                "Failed to predict resource exhaustion",
                component_type=component_type,
                resource_type=resource_type,
                error=str(e),
            )
            return None

    async def assess_component_risk(
        self,
        component_type: str,
        component_id: str,
        time_range: str = "last_24h",
    ) -> Dict[str, Any]:
        """
        Assess overall failure risk for a component.

        Args:
            component_type: Component type
            component_id: Component ID
            time_range: Time range for analysis

        Returns:
            Risk assessment with score and recommendations
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Get error metrics
            total_events = (
                self.db.query(func.count(DebugEvent.id))
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .scalar()
            )

            error_events = (
                self.db.query(func.count(DebugEvent.id))
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter,
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                    )
                )
                .scalar()
            )

            # Calculate base risk score
            error_rate = (error_events / total_events) if total_events and total_events > 0 else 0
            risk_score = min(100, error_rate * 100)

            # Get critical error ratio
            critical_errors = (
                self.db.query(func.count(DebugEvent.id))
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter,
                        DebugEvent.level == "CRITICAL",
                    )
                )
                .scalar()
            )

            # Adjust risk based on critical errors
            if error_events > 0:
                critical_ratio = critical_errors / error_events
                risk_score += critical_ratio * 20

            # Get recent performance metrics if available
            time_filter_hr = datetime.utcnow() - timedelta(hours=1)

            recent_events = (
                self.db.query(DebugEvent)
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter_hr,
                    )
                )
                .all()
            )

            # Check for recent slow operations
            slow_ops = 0
            for event in recent_events:
                if event.data and "duration_ms" in event.data:
                    if event.data["duration_ms"] > 5000:  # 5 second threshold
                        slow_ops += 1

            slow_op_rate = slow_ops / len(recent_events) if recent_events else 0
            risk_score += slow_op_rate * 30

            # Cap at 100
            risk_score = min(100, risk_score)

            # Determine risk level and generate recommendations
            if risk_score >= 70:
                risk_level = "high"
                urgency = "immediate"
            elif risk_score >= 40:
                risk_level = "medium"
                urgency = "soon"
            else:
                risk_level = "low"
                urgency = "monitor"

            recommendations = []
            if error_rate > 0.5:
                recommendations.append("High error rate requires investigation")
            if slow_op_rate > 0.2:
                recommendations.append("Many slow operations detected - review performance")
            if critical_ratio > 0.3:
                recommendations.append(f"Critical errors are {critical_ratio*100:.0f}% of errors")

            return {
                "component_type": component_type,
                "component_id": component_id,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "urgency": urgency,
                "error_rate": error_rate,
                "critical_error_ratio": critical_ratio / error_events if error_events > 0 else 0,
                "slow_operation_rate": slow_op_rate,
                "total_events": total_events or 0,
                "error_events": error_events or 0,
                "recommendations": recommendations,
                "analyzed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(
                "Failed to assess component risk",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return {
                "risk_score": 50,
                "risk_level": "unknown",
                "urgency": "unknown",
                "error": str(e),
            }

    async def get_predictive_alerts(
        self,
        threshold_probability: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Get components with high predicted failure probability.

        Args:
            threshold_probability: Probability threshold for alerts

        Returns:
            List of at-risk components
        """
        try:
            alerts = []

            # Get all components with recent activity
            time_filter = datetime.utcnow() - timedelta(hours=1)

            components = (
                self.db.query(
                    DebugEvent.component_type,
                    DebugEvent.component_id,
                )
                .filter(DebugEvent.timestamp >= time_filter)
                .distinct()
                .all()
            )

            for comp_type, comp_id in components:
                prediction = await self.predict_operation_failure(
                    component_type=comp_type,
                    component_id=comp_id,
                )

                if prediction["probability"] >= threshold_probability:
                    alerts.append({
                        "component_type": comp_type,
                        "component_id": comp_id,
                        "failure_probability": prediction["probability"],
                        "confidence": prediction["confidence"],
                        "factors": prediction["factors"],
                        "recommendation": self._get_recommendation(prediction),
                    })

            # Sort by probability (descending)
            alerts.sort(key=lambda x: x["failure_probability"], reverse=True)

            return alerts

        except Exception as e:
            self.logger.error("Failed to get predictive alerts", error=str(e))
            return []

    def _calculate_trend(self, values: List[Tuple[datetime, float]]) -> float:
        """
        Calculate linear trend slope from time series data.

        Args:
            values: List of (timestamp, value) tuples

        Returns:
            Trend slope (value change per day)
        """
        if len(values) < 2:
            return 0

        # Convert timestamps to numeric (days since first)
        start_time = values[0][0]
        numeric_values = [( (ts - start_time).total_seconds() / 86400, val) for ts, val in values]

        # Simple linear regression
        n = len(numeric_values)
        sum_x = sum(t for t, _ in numeric_values)
        sum_y = sum(v for _, v in numeric_values)
        sum_xx = sum(t * t for t, _ in numeric_values)
        sum_xy = sum(t * v for t, v in numeric_values)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)

        return slope

    def _get_recommendation(self, prediction: Dict[str, Any]) -> str:
        """Generate recommendation based on prediction factors."""
        if prediction["probability"] > 0.8:
            return "Immediate action required - high failure probability"
        elif prediction["probability"] > 0.6:
            return "Monitor closely - elevated failure risk"
        elif prediction["probability"] > 0.4:
            return "Increased monitoring recommended"
        else:
            return "Normal operation"

    def _parse_time_range(self, time_range: str) -> datetime:
        """Parse time range string to datetime."""
        now = datetime.utcnow()

        if time_range == "last_1h":
            return now - timedelta(hours=1)
        elif time_range == "last_24h":
            return now - timedelta(hours=24)
        elif time_range == "last_7d":
            return now - timedelta(days=7)
        else:
            return now - timedelta(hours=1)
