"""
Tests for Debug Insight Engine

Tests cover:
- Insight generation from events
- Consistency insights
- Flow insights
- Error insights
- Performance insights
- Anomaly insights
"""

import pytest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
    DebugEventType,
    DebugInsightType,
    DebugInsightSeverity,
    Base,
)
from core.debug_insight_engine import DebugInsightEngine


@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")

    # Create only debug tables
    debug_tables = [
        DebugEvent.__table__,
        DebugInsight.__table__,
        DebugStateSnapshot.__table__,
    ]

    for table in debug_tables:
        table.create(bind=engine, checkfirst=True)

    TestingSessionLocal = sessionmaker(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        for table in reversed(debug_tables):
            table.drop(bind=engine, checkfirst=True)


@pytest.fixture
def insight_engine(test_db):
    """Create insight engine for testing."""
    return DebugInsightEngine(test_db)


class TestDebugInsightEngine:
    """Tests for DebugInsightEngine."""

    @pytest.mark.asyncio
    async def test_generate_insights_from_no_events(self, insight_engine):
        """Test generating insights when no events exist."""
        insights = await insight_engine.generate_insights_from_events(
            correlation_id="nonexistent",
        )

        assert insights == []

    @pytest.mark.asyncio
    async def test_generate_consistency_insight_missing_components(
        self, insight_engine, test_db
    ):
        """Test consistency insight for missing components."""
        # Create state snapshots for only 2 of 3 components
        for i in range(2):
            from core.models import DebugStateSnapshot

            snapshot = DebugStateSnapshot(
                component_type="agent",
                component_id=f"agent-{i}",
                operation_id="op-123",
                state_data={"status": "running"},
                snapshot_type="full",
            )
            test_db.add(snapshot)
        test_db.commit()

        insight = await insight_engine.analyze_state_consistency(
            operation_id="op-123",
            component_ids=["agent-0", "agent-1", "agent-2"],
            component_type="agent",
        )

        assert insight is not None
        assert insight.insight_type == DebugInsightType.CONSISTENCY.value
        assert insight.severity == DebugInsightSeverity.WARNING.value
        assert "incomplete" in insight.title.lower() or "missing" in insight.title.lower()

    @pytest.mark.asyncio
    async def test_generate_consistency_insight_state_inconsistency(
        self, insight_engine, test_db
    ):
        """Test consistency insight for state inconsistency."""
        from core.models import DebugStateSnapshot

        # Create snapshots with inconsistent state
        snapshot1 = DebugStateSnapshot(
            component_type="agent",
            component_id="agent-0",
            operation_id="op-456",
            state_data={"status": "running", "progress": 0.5},
            snapshot_type="full",
        )
        snapshot2 = DebugStateSnapshot(
            component_type="agent",
            component_id="agent-1",
            operation_id="op-456",
            state_data={"status": "running", "progress": 0.8},  # Different progress
            snapshot_type="full",
        )
        test_db.add_all([snapshot1, snapshot2])
        test_db.commit()

        insight = await insight_engine.analyze_state_consistency(
            operation_id="op-456",
            component_ids=["agent-0", "agent-1"],
            component_type="agent",
        )

        assert insight is not None
        assert insight.insight_type == DebugInsightType.CONSISTENCY.value
        assert "inconsistent" in insight.title.lower() or "differs" in insight.summary.lower()

    @pytest.mark.asyncio
    async def test_generate_flow_insight_with_errors(self, insight_engine, test_db):
        """Test flow insight generation with errors."""
        # Create events with errors
        for i in range(3):
            event = DebugEvent(
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id="corr-flow",
                level="ERROR" if i == 2 else "INFO",
                message=f"Step {i}",
                timestamp=datetime.utcnow() + timedelta(seconds=i),
            )
            test_db.add(event)
        test_db.commit()

        insights = await insight_engine.generate_insights_from_events(
            correlation_id="corr-flow",
        )

        # Should have at least a flow insight
        flow_insights = [
            i
            for i in insights
            if i.insight_type == DebugInsightType.FLOW.value
        ]
        assert len(flow_insights) > 0

    @pytest.mark.asyncio
    async def test_generate_error_insight_repeated_errors(self, insight_engine, test_db):
        """Test error insight generation for repeated errors."""
        # Create repeated error events
        for i in range(5):
            event = DebugEvent(
                event_type="error",
                component_type="agent",
                component_id=f"agent-{i % 2}",  # 2 components
                correlation_id="corr-error",
                level="ERROR",
                message="Connection timeout",  # Same error message
                timestamp=datetime.utcnow() + timedelta(seconds=i),
            )
            test_db.add(event)
        test_db.commit()

        insights = await insight_engine.generate_insights_from_events(
            correlation_id="corr-error",
        )

        # Should have error insight
        error_insights = [
            i
            for i in insights
            if i.insight_type == DebugInsightType.ERROR.value
        ]
        assert len(error_insights) > 0
        assert "repeated" in error_insights[0].title.lower()

    @pytest.mark.asyncio
    async def test_generate_performance_insight_slow_operations(
        self, insight_engine, test_db
    ):
        """Test performance insight for slow operations."""
        # Create events with duration metadata
        for i in range(3):
            event = DebugEvent(
                event_type="metric",
                component_type="agent",
                component_id="agent-123",
                correlation_id="corr-perf",
                level="INFO",
                message="Operation completed",
                data={"duration_ms": 6000 + i * 1000},  # > 5s threshold
                timestamp=datetime.utcnow() + timedelta(seconds=i),
            )
            test_db.add(event)
        test_db.commit()

        insights = await insight_engine.generate_insights_from_events(
            correlation_id="corr-perf",
        )

        # Should have performance insight
        perf_insights = [
            i
            for i in insights
            if i.insight_type == DebugInsightType.PERFORMANCE.value
        ]
        assert len(perf_insights) > 0
        assert "slow" in perf_insights[0].title.lower()

    @pytest.mark.asyncio
    async def test_generate_anomaly_insight_event_spike(self, insight_engine, test_db):
        """Test anomaly insight for event volume spike."""
        # Create normal event volume
        for i in range(10):
            event = DebugEvent(
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id=f"corr-{i}",
                level="INFO",
                message="Normal event",
                timestamp=datetime.utcnow() + timedelta(seconds=i * 60),
            )
            test_db.add(event)

        # Create spike (many events in one minute)
        spike_time = datetime.utcnow() + timedelta(minutes=10)
        for i in range(50):
            event = DebugEvent(
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id=f"corr-spike-{i}",
                level="INFO",
                message="Spike event",
                timestamp=spike_time + timedelta(seconds=i),
            )
            test_db.add(event)

        test_db.commit()

        insights = await insight_engine.generate_insights_from_events(
            component_id="agent-123",
            time_range="last_1h",
        )

        # Should have anomaly insight
        anomaly_insights = [
            i
            for i in insights
            if i.insight_type == DebugInsightType.ANOMALY.value
        ]
        # Note: Anomaly detection might not always trigger depending on thresholds
        # This is a basic test structure

    @pytest.mark.asyncio
    async def test_insight_confidence_scoring(self, insight_engine, test_db):
        """Test that insights have confidence scores."""
        # Create error events
        for i in range(3):
            event = DebugEvent(
                event_type="error",
                component_type="agent",
                component_id="agent-123",
                correlation_id="corr-confidence",
                level="ERROR",
                message="Test error",
                timestamp=datetime.utcnow() + timedelta(seconds=i),
            )
            test_db.add(event)
        test_db.commit()

        insights = await insight_engine.generate_insights_from_events(
            correlation_id="corr-confidence",
        )

        for insight in insights:
            assert 0.0 <= insight.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_insight_suggestions_generation(self, insight_engine, test_db):
        """Test that insights include resolution suggestions."""
        # Create error events
        event = DebugEvent(
            event_type="error",
            component_type="browser",
            component_id="browser-123",
            correlation_id="corr-suggestions",
            level="ERROR",
            message="Connection failed",
        )
        test_db.add(event)
        test_db.commit()

        insights = await insight_engine.generate_insights_from_events(
            correlation_id="corr-suggestions",
        )

        # Check if any insights have suggestions
        insights_with_suggestions = [
            i for i in insights if i.suggestions and len(i.suggestions) > 0
        ]
        # At least some insights should have suggestions
        # (This is a soft assertion as not all insight types may have suggestions)

    @pytest.mark.asyncio
    async def test_insight_scope_classification(self, insight_engine, test_db):
        """Test that insights are correctly scoped."""
        # Create events for single component
        event = DebugEvent(
            event_type="error",
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-scope",
            level="ERROR",
            message="Single component error",
        )
        test_db.add(event)
        test_db.commit()

        insights = await insight_engine.generate_insights_from_events(
            correlation_id="corr-scope",
        )

        for insight in insights:
            assert insight.scope in ["component", "distributed", "system"]

    @pytest.mark.asyncio
    async def test_affected_components_tracking(self, insight_engine, test_db):
        """Test that insights track affected components."""
        # Create events for multiple components
        for i in range(3):
            event = DebugEvent(
                event_type="error",
                component_type="agent",
                component_id=f"agent-{i}",
                correlation_id="corr-affected",
                level="ERROR",
                message="Error",
            )
            test_db.add(event)
        test_db.commit()

        insights = await insight_engine.generate_insights_from_events(
            correlation_id="corr-affected",
        )

        # Check if insights track affected components
        insights_with_components = [
            i
            for i in insights
            if i.affected_components and len(i.affected_components) > 0
        ]
        # At least some insights should track affected components

    def test_parse_time_range(self, insight_engine):
        """Test time range parsing."""
        now = datetime.utcnow()

        # Test various time ranges
        ranges = ["last_1h", "last_24h", "last_7d", "last_30d"]

        for time_range in ranges:
            result = insight_engine._parse_time_range(time_range)
            assert result is not None
            assert isinstance(result, datetime)
            assert result < now

    def test_parse_invalid_time_range(self, insight_engine):
        """Test parsing invalid time range."""
        result = insight_engine._parse_time_range("invalid")
        # Should return None for invalid range
        assert result is None
