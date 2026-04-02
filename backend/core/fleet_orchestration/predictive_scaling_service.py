"""
Predictive Scaling Service for Adaptive Fleet

Uses historical performance data and trends to predict future scaling needs
before performance degradation occurs. Enables proactive rather than reactive scaling.
"""
import logging
import statistics
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.models import ScalingProposal, DelegationChain, FleetPerformanceMetric
from core.database import SessionLocal
from core.fleet_orchestration.performance_metrics_service import PerformanceMetricsService
from core.fleet_orchestration.scaling_proposal_service import ScalingProposalService

logger = logging.getLogger(__name__)

class PredictiveScalingService:
    """
    Service for predictive fleet scaling based on historical trends.

    Features:
    - Trend analysis for success rate, latency, and throughput
    - Time-to-threshold prediction
    - Proactive scaling recommendations
    - Seasonal pattern detection
    """

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self.metrics_service = PerformanceMetricsService(db=self.db)
        self.proposal_service = ScalingProposalService(db=self.db)

    def analyze_trend(
        self,
        chain_id: str,
        metric_type: str,
        window_hours: int = 24,
        min_data_points: int = 10
    ) -> Dict[str, Any]:
        """
        Analyze trend for a specific metric over time.

        Args:
            chain_id: Chain UUID
            metric_type: Type of metric (success_rate, latency, throughput)
            window_hours: Hours of historical data to analyze
            min_data_points: Minimum required data points

        Returns:
            Dict with trend analysis:
                - direction (str): 'increasing', 'decreasing', 'stable'
                - slope (float): Rate of change per hour
                - r_squared (float): Trend strength (0-1)
                - current_value (float): Latest metric value
                - predicted_value_1h (float): Predicted value in 1 hour
                - predicted_value_4h (float): Predicted value in 4 hours
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        # Get historical metrics
        metrics = self.db.query(FleetPerformanceMetric).filter(
            FleetPerformanceMetric.chain_id == chain_id,
            FleetPerformanceMetric.metric_type == metric_type,
            FleetPerformanceMetric.window_start >= cutoff_time
        ).order_by(FleetPerformanceMetric.window_start).all()

        if len(metrics) < min_data_points:
            return {
                "direction": "unknown",
                "slope": 0.0,
                "r_squared": 0.0,
                "current_value": None,
                "predicted_value_1h": None,
                "predicted_value_4h": None,
                "error": f"Insufficient data points: {len(metrics)} < {min_data_points}"
            }

        # Extract time series data
        timestamps = []
        values = []
        for m in metrics:
            timestamps.append(m.window_start.timestamp())
            values.append(float(m.metric_value))

        # Normalize timestamps to hours from start
        start_time = timestamps[0]
        x_hours = [(t - start_time) / 3600 for t in timestamps]
        y_values = values

        # Calculate linear regression
        slope, intercept, r_squared = self._linear_regression(x_hours, y_values)

        # Determine trend direction
        if slope > 0.5:
            direction = "increasing"
        elif slope < -0.5:
            direction = "decreasing"
        else:
            direction = "stable"

        # Calculate predictions
        current_hour = (timestamps[-1] - start_time) / 3600
        current_value = y_values[-1]
        predicted_1h = slope * (current_hour + 1) + intercept
        predicted_4h = slope * (current_hour + 4) + intercept

        return {
            "direction": direction,
            "slope": round(slope, 4),
            "r_squared": round(r_squared, 4),
            "current_value": round(current_value, 2),
            "predicted_value_1h": round(predicted_1h, 2),
            "predicted_value_4h": round(predicted_4h, 2),
            "data_points": len(metrics),
            "window_hours": window_hours
        }

    def predict_threshold_breach(
        self,
        chain_id: str,
        metric_type: str,
        threshold: float,
        breach_direction: str = 'below'  # 'below' or 'above'
    ) -> Dict[str, Any]:
        """
        Predict when a metric will breach a threshold.

        Args:
            chain_id: Chain UUID
            metric_type: Metric to track
            threshold: Threshold value
            breach_direction: 'below' or 'above'

        Returns:
            Dict with:
                - will_breach (bool): Whether breach is predicted
                - hours_until_breach (float|None): Hours until breach
                - confidence (str): 'high', 'medium', 'low'
                - current_value (float): Current metric value
                - trend_slope (float): Rate of change
        """
        # Analyze trend
        trend = self.analyze_trend(chain_id, metric_type, window_hours=24)

        if trend.get("error"):
            return {
                "will_breach": False,
                "hours_until_breach": None,
                "confidence": "unknown",
                "error": trend["error"]
            }

        slope = trend["slope"]
        current_value = trend["current_value"]
        r_squared = trend["r_squared"]

        # Check if threshold is already breached first, then check trend
        if breach_direction == 'below':
            # Check if already breached
            if current_value <= threshold:
                return {
                    "will_breach": True,
                    "hours_until_breach": 0,
                    "confidence": "high",
                    "current_value": current_value,
                    "trend_slope": slope,
                    "message": "Threshold already breached"
                }
            # Trend is increasing or stable, won't breach below threshold
            if slope >= 0:
                return {
                    "will_breach": False,
                    "hours_until_breach": None,
                    "confidence": "high",
                    "current_value": current_value,
                    "trend_slope": slope,
                    "message": "Metric is stable or increasing, no breach predicted"
                }
        else:  # breach_direction == 'above'
            # Check if already breached
            if current_value >= threshold:
                return {
                    "will_breach": True,
                    "hours_until_breach": 0,
                    "confidence": "high",
                    "current_value": current_value,
                    "trend_slope": slope,
                    "message": "Threshold already breached"
                }
            # Metric is stable or decreasing, no breach predicted
            if slope <= 0:
                return {
                    "will_breach": False,
                    "hours_until_breach": None,
                    "confidence": "high",
                    "current_value": current_value,
                    "trend_slope": slope,
                    "message": "Metric is stable or decreasing, no breach predicted"
                }

        # Calculate time to breach
        if slope != 0:
            hours_until = abs(threshold - current_value) / abs(slope)
        else:
            hours_until = float('inf')

        # Determine confidence based on R²
        if r_squared > 0.7:
            confidence = "high"
        elif r_squared > 0.4:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "will_breach": hours_until < 48,  # Predict if within 48 hours
            "hours_until_breach": round(hours_until, 2) if hours_until != float('inf') else None,
            "confidence": confidence,
            "current_value": current_value,
            "trend_slope": slope,
            "message": f"Breach predicted in {hours_until:.1f} hours" if hours_until < 48 else "No breach predicted within 48 hours"
        }

    def generate_proactive_proposal(
        self,
        chain_id: str) -> Dict[str, Any]:
        """
        Generate a proactive scaling proposal based on predictive analysis.

        Args:
            chain_id: Chain UUID
            tenant_id: Any UUID

        Returns:
            Dict with:
                - proposal_needed (bool): Whether scaling is predicted
                - proposal (ScalingProposal|None): Created proposal
                - prediction (dict): Prediction details
                - reason (str): Explanation
        """
        # Analyze success rate trend
        success_trend = self.analyze_trend(chain_id, 'success_rate', window_hours=24)
        latency_trend = self.analyze_trend(chain_id, 'avg_latency', window_hours=24)

        # Predict threshold breaches
        success_breach = self.predict_threshold_breach(
            chain_id, 'success_rate',
            threshold=85.0,  # Success rate threshold
            breach_direction='below'
        )

        latency_breach = self.predict_threshold_breach(
            chain_id, 'avg_latency',
            threshold=500,  # Latency threshold in ms
            breach_direction='above'
        )

        # Get current fleet size
        chain = self.db.query(DelegationChain).filter(
            DelegationChain.id == chain_id
        ).first()

        if not chain:
            return {
                "proposal_needed": False,
                "proposal": None,
                "prediction": None,
                "reason": f"Chain {chain_id} not found"
            }

        current_fleet_size = self._get_fleet_size(chain_id)

        # Determine if proactive scaling is needed
        reasons = []
        urgency = 0

        if success_breach.get("will_breach"):
            hours = success_breach.get("hours_until_breach", 0)
            if hours is not None and hours < 12:
                reasons.append(f"Success rate predicted to drop below 85% in {hours:.1f}h")
                urgency += 3
            elif hours is not None and hours < 24:
                reasons.append(f"Success rate predicted to drop below 85% in {hours:.1f}h")
                urgency += 2

        if latency_breach.get("will_breach"):
            hours = latency_breach.get("hours_until_breach", 0)
            if hours is not None and hours < 12:
                reasons.append(f"Latency predicted to exceed 500ms in {hours:.1f}h")
                urgency += 3
            elif hours is not None and hours < 24:
                reasons.append(f"Latency predicted to exceed 500ms in {hours:.1f}h")
                urgency += 2

        if not reasons:
            return {
                "proposal_needed": False,
                "proposal": None,
                "prediction": {
                    "success_trend": success_trend,
                    "latency_trend": latency_trend,
                    "success_breach": success_breach,
                    "latency_breach": latency_breach
                },
                "reason": "No performance degradation predicted in next 24 hours"
            }

        # Calculate proposed fleet size based on urgency
        if urgency >= 3:
            # Urgent: 50% increase
            proposed_size = max(current_fleet_size + 1, int(current_fleet_size * 1.5))
        elif urgency >= 2:
            # Moderate: 33% increase
            proposed_size = max(current_fleet_size + 1, int(current_fleet_size * 1.33))
        else:
            # Mild: 25% increase
            proposed_size = max(current_fleet_size + 1, int(current_fleet_size * 1.25))

        # Estimate cost (simplified: $0.10 per agent per hour)
        size_increase = proposed_size - current_fleet_size
        cost_estimate = Decimal(str(size_increase * 0.10 * 24))  # 24-hour duration

        # Create proposal
        proposal = self.proposal_service.create_scaling_proposal(
            chain_id=chain_id,
                        proposal_type='expansion',
            current_fleet_size=current_fleet_size,
            proposed_fleet_size=proposed_size,
            reason="Proactive scaling: " + "; ".join(reasons),
            duration_hours=24,
            cost_estimate=float(cost_estimate),
            is_proactive=True
        )

        logger.info(
            f"[PredictiveScaling] Created proactive proposal {proposal.id} "
            f"for chain {chain_id}: {current_fleet_size} → {proposed_size} agents"
        )

        return {
            "proposal_needed": True,
            "proposal": proposal,
            "prediction": {
                "success_trend": success_trend,
                "latency_trend": latency_trend,
                "success_breach": success_breach,
                "latency_breach": latency_breach
            },
            "reason": "; ".join(reasons),
            "urgency": urgency,
            "hours_until_issue": min(
                success_breach.get("hours_until_breach") or float('inf'),
                latency_breach.get("hours_until_breach") or float('inf')
            )
        }

    def detect_seasonal_pattern(
        self,
        chain_id: str,
        metric_type: str,
        days_to_analyze: int = 7
    ) -> Dict[str, Any]:
        """
        Detect seasonal patterns in metric data.

        Args:
            chain_id: Chain UUID
            metric_type: Metric to analyze
            days_to_analyze: Number of days to analyze

        Returns:
            Dict with:
                - pattern_detected (bool): Whether pattern exists
                - peak_hours (list): Hours with highest values
                - low_hours (list): Hours with lowest values
                - hourly_averages (dict): Average by hour of day
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_analyze)

        metrics = self.db.query(FleetPerformanceMetric).filter(
            FleetPerformanceMetric.chain_id == chain_id,
            FleetPerformanceMetric.metric_type == metric_type,
            FleetPerformanceMetric.window_start >= cutoff_time
        ).all()

        if len(metrics) < 50:
            return {
                "pattern_detected": False,
                "error": "Insufficient data for pattern detection"
            }

        # Group by hour of day
        hourly_values = {h: [] for h in range(24)}
        for m in metrics:
            hour = m.window_start.hour
            hourly_values[hour].append(float(m.metric_value))

        # Calculate hourly averages
        hourly_averages = {}
        for hour, values in hourly_values.items():
            if values:
                hourly_averages[hour] = statistics.mean(values)

        if not hourly_averages:
            return {
                "pattern_detected": False,
                "error": "No valid data"
            }

        # Find peak and low hours
        sorted_hours = sorted(hourly_averages.items(), key=lambda x: x[1])
        low_hours = [h for h, _ in sorted_hours[:3]]
        peak_hours = [h for h, _ in sorted_hours[-3:]]

        # Calculate variance to determine if pattern is significant
        values = list(hourly_averages.values())
        mean_val = statistics.mean(values)
        stdev_val = statistics.stdev(values) if len(values) > 1 else 0
        coefficient_of_variation = (stdev_val / mean_val * 100) if mean_val > 0 else 0

        pattern_detected = coefficient_of_variation > 10  # >10% variation

        return {
            "pattern_detected": pattern_detected,
            "peak_hours": peak_hours,
            "low_hours": low_hours,
            "hourly_averages": {k: round(v, 2) for k, v in hourly_averages.items()},
            "coefficient_of_variation": round(coefficient_of_variation, 2),
            "mean_value": round(mean_val, 2)
        }

    def _linear_regression(
        self,
        x: List[float],
        y: List[float]
    ) -> Tuple[float, float, float]:
        """
        Calculate simple linear regression.

        Returns:
            Tuple of (slope, intercept, r_squared)
        """
        n = len(x)
        if n < 2:
            return 0.0, y[0] if y else 0.0, 0.0

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        sum_y2 = sum(yi ** 2 for yi in y)

        # Calculate slope and intercept
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 0.0, sum_y / n, 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

        # Calculate R²
        y_mean = sum_y / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))  # Clamp to [0, 1]

        return slope, intercept, r_squared

    def _get_fleet_size(self, chain_id: str) -> int:
        """Get current fleet size for a chain."""
        from core.models import ChainLink
        active_agents = self.db.query(ChainLink).filter(
            ChainLink.chain_id == chain_id,
            ChainLink.status == 'active'
        ).count()
        return active_agents

def get_predictive_scaling_service(db: Session = None) -> PredictiveScalingService:
    """
    Factory function to get PredictiveScalingService instance.

    Args:
        db: Optional database session

    Returns:
        PredictiveScalingService instance
    """
    return PredictiveScalingService(db=db)
