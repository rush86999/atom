"""
Tests for Failure Prediction Module
"""

import pytest
from collections import Counter
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from core.models import Base, DebugEvent, DebugMetric
from core.debug_prediction import FailurePredictor


@pytest.fixture
def db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    # Create only debug tables
    debug_tables = [
        DebugEvent.__table__,
        DebugMetric.__table__,
    ]
    for table in debug_tables:
        table.create(bind=engine, checkfirst=True)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def predictor(db):
    """Create failure predictor instance."""
    return FailurePredictor(db_session=db, lookback_days=30, min_samples=10)


class TestFailurePredictor:
    """Test failure prediction functionality."""

    @pytest.mark.asyncio
    async def test_predict_operation_failure_no_data(self, predictor):
        """Test prediction with no historical data."""
        result = await predictor.predict_operation_failure(
            component_type="agent",
            component_id="new-agent"
        )

        assert result["probability"] == 0.5  # Unknown
        assert result["confidence"] == 0.0
        assert "insufficient_historical_data" in result["factors"]

    @pytest.mark.asyncio
    async def test_predict_operation_failure_with_history(self, db, predictor):
        """Test prediction with historical operations."""
        now = datetime.utcnow()

        # Create historical operations - 70% success rate
        for i in range(100):
            is_error = i < 30  # 30 errors
            event = DebugEvent(
                id=f"event-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id=f"op-{i//10}",  # Group into operations
                level="ERROR" if is_error else "INFO",
                message="Operation failed" if is_error else "Operation success",
                timestamp=now - timedelta(days=i // 10)  # Spread over 10 days
            )
            db.add(event)

        db.commit()

        result = await predictor.predict_operation_failure(
            component_type="agent",
            component_id="agent-123"
        )

        assert abs(result["probability"] - 0.3) < 0.01  # 30% failure rate (allowing for floating point)
        assert result["confidence"] > 0.5
        assert abs(result["success_rate"] - 0.7) < 0.01
        assert result["historical_operations"] > 0

    @pytest.mark.asyncio
    async def test_predict_operation_failure_with_trend(self, db, predictor):
        """Test prediction detects degrading trend."""
        now = datetime.utcnow()

        # First half: 90% success
        for i in range(50):
            event = DebugEvent(
                id=f"event-first-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-456",
                correlation_id=f"op-{i}",
                level="ERROR" if i < 5 else "INFO",  # Only 5 errors
                message="Error" if i < 5 else "Success",
                timestamp=now - timedelta(days=20 + i // 5)
            )
            db.add(event)

        # Second half: 50% success (degrading)
        for i in range(50):
            event = DebugEvent(
                id=f"event-second-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-456",
                correlation_id=f"op-{50+i}",
                level="ERROR" if i < 25 else "INFO",  # 25 errors
                message="Error" if i < 25 else "Success",
                timestamp=now - timedelta(days=10 + i // 5)
            )
            db.add(event)

        db.commit()

        result = await predictor.predict_operation_failure(
            component_type="agent",
            component_id="agent-456"
        )

        # Should detect degrading trend
        assert result["probability"] > 0.3
        factor_names = [f["factor"] for f in result["factors"]]
        assert "degrading_trend" in factor_names or "high_recent_error_rate" in factor_names

    @pytest.mark.asyncio
    async def test_predict_resource_exhaustion_memory(self, db, predictor):
        """Test memory exhaustion prediction."""
        now = datetime.utcnow()

        # Create memory usage metrics showing increasing trend
        for i in range(100):
            metric = DebugMetric(
                id=f"metric-{i}",
                metric_name="memory_usage",
                component_type="agent",
                component_id="agent-123",
                value=50 + i * 0.5,  # Increasing from 50% to 100%
                timestamp=now - timedelta(hours=100-i)
            )
            db.add(metric)

        db.commit()

        result = await predictor.predict_resource_exhaustion(
            component_type="agent",
            resource_type="memory"
        )

        assert result is not None
        assert result["resource_type"] == "memory"
        assert result["current_usage_percent"] > 50
        assert result["trend_slope_per_day"] > 0
        assert result["predicted_exhaustion_hours"] < 168  # Less than a week

    @pytest.mark.asyncio
    async def test_predict_resource_exhaustion_insufficient_data(self, db, predictor):
        """Test resource exhaustion with insufficient data."""
        now = datetime.utcnow()

        # Only 50 data points
        for i in range(50):
            metric = DebugMetric(
                id=f"metric-{i}",
                metric_name="memory_usage",
                component_type="agent",
                component_id="agent-456",
                value=50.0,
                timestamp=now - timedelta(hours=50-i)
            )
            db.add(metric)

        db.commit()

        result = await predictor.predict_resource_exhaustion(
            component_type="agent",
            resource_type="memory"
        )

        assert result is None  # Insufficient data

    @pytest.mark.asyncio
    async def test_assess_component_risk_low(self, db, predictor):
        """Test component risk assessment - low risk."""
        now = datetime.utcnow()

        # Create events with low error rate
        for i in range(100):
            event = DebugEvent(
                id=f"event-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-low-risk",
                correlation_id=f"op-{i}",
                level="ERROR" if i < 5 else "INFO",  # 5% error rate
                message="Error" if i < 5 else "Success",
                timestamp=now - timedelta(hours=24-i)
            )
            db.add(event)

        db.commit()

        result = await predictor.assess_component_risk(
            component_type="agent",
            component_id="agent-low-risk",
            time_range="last_24h"
        )

        assert result["risk_score"] < 30
        assert result["risk_level"] == "low"
        assert result["urgency"] == "monitor"

    @pytest.mark.asyncio
    async def test_assess_component_risk_high(self, db, predictor):
        """Test component risk assessment - high risk."""
        now = datetime.utcnow()

        # Create events with high error rate
        for i in range(100):
            event = DebugEvent(
                id=f"event-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-high-risk",
                correlation_id=f"op-{i}",
                level="ERROR" if i < 60 else "INFO",  # 60% error rate
                message="Error" if i < 60 else "Success",
                timestamp=now - timedelta(hours=24-i)
            )
            db.add(event)

        db.commit()

        result = await predictor.assess_component_risk(
            component_type="agent",
            component_id="agent-high-risk",
            time_range="last_24h"
        )

        assert result["risk_score"] >= 70
        assert result["risk_level"] == "high"
        assert result["urgency"] == "immediate"
        assert len(result["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_get_predictive_alerts(self, db, predictor):
        """Test getting predictive alerts."""
        now = datetime.utcnow()

        # Create high-risk component
        for i in range(50):
            event = DebugEvent(
                id=f"event-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-alert",
                correlation_id=f"op-{i}",
                level="ERROR" if i < 35 else "INFO",  # 70% error rate
                message="Error" if i < 35 else "Success",
                timestamp=now - timedelta(hours=1)
            )
            db.add(event)

        # Create low-risk component
        for i in range(50):
            event = DebugEvent(
                id=f"event-low-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-ok",
                correlation_id=f"op-{i}",
                level="ERROR" if i < 5 else "INFO",  # 10% error rate
                message="Error" if i < 5 else "Success",
                timestamp=now - timedelta(hours=1)
            )
            db.add(event)

        db.commit()

        alerts = await predictor.get_predictive_alerts(threshold_probability=0.6)

        # Should alert on high-risk component
        assert len(alerts) >= 1
        high_risk_alerts = [a for a in alerts if a["component_id"] == "agent-alert"]
        assert len(high_risk_alerts) == 1
        assert high_risk_alerts[0]["failure_probability"] >= 0.6

    def test_calculate_trend(self, predictor):
        """Test trend calculation."""
        now = datetime.utcnow()
        values = [
            (now - timedelta(days=4), 10.0),
            (now - timedelta(days=3), 20.0),
            (now - timedelta(days=2), 30.0),
            (now - timedelta(days=1), 40.0),
            (now, 50.0),
        ]

        trend = predictor._calculate_trend(values)

        # Should be positive (increasing)
        assert trend > 0
        # Approximately 10 units per day
        assert abs(trend - 10.0) < 1.0

    def test_get_recommendation(self, predictor):
        """Test recommendation generation."""
        # High probability
        result = predictor._get_recommendation({"probability": 0.85})
        assert "Immediate action" in result

        # Medium probability
        result = predictor._get_recommendation({"probability": 0.65})
        assert "Monitor closely" in result

        # Medium-low probability (> 0.4)
        result = predictor._get_recommendation({"probability": 0.5})
        assert "Increased monitoring" in result

        # Very low probability
        result = predictor._get_recommendation({"probability": 0.1})
        assert "Normal operation" in result
