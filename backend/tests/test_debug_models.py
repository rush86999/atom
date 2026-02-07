"""
Tests for AI Debug System models.

Tests cover:
- DebugEvent model creation and relationships
- DebugInsight model creation and fields
- DebugStateSnapshot model with diff detection
- DebugMetric model for time-series data
- DebugSession model for interactive debugging
- Index verification for query performance
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
    DebugMetric,
    DebugSession,
    DebugEventType,
    DebugInsightType,
    DebugInsightSeverity,
)
from core.database import Base


# Test Database Setup
@pytest.fixture(scope="function")
def test_db():
    """Create a test database."""
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create only debug tables (not all tables to avoid conflicts)
    debug_tables = [
        DebugEvent.__table__,
        DebugInsight.__table__,
        DebugStateSnapshot.__table__,
        DebugMetric.__table__,
        DebugSession.__table__,
    ]

    for table in debug_tables:
        table.create(bind=engine, checkfirst=True)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        for table in reversed(debug_tables):
            table.drop(bind=engine, checkfirst=True)


class TestDebugEvent:
    """Tests for DebugEvent model."""

    def test_create_debug_event_log(self, test_db):
        """Test creating a log event."""
        event = DebugEvent(
            event_type=DebugEventType.LOG.value,
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-456",
            level="INFO",
            message="Agent started successfully",
            data={"timestamp": "2026-02-06T10:00:00Z"},
            event_metadata={"source": "system"},
        )
        test_db.add(event)
        test_db.commit()

        retrieved = test_db.query(DebugEvent).filter_by(id=event.id).first()
        assert retrieved is not None
        assert retrieved.event_type == DebugEventType.LOG.value
        assert retrieved.component_type == "agent"
        assert retrieved.component_id == "agent-123"
        assert retrieved.level == "INFO"
        assert retrieved.message == "Agent started successfully"

    def test_create_debug_event_error(self, test_db):
        """Test creating an error event."""
        event = DebugEvent(
            event_type=DebugEventType.ERROR.value,
            component_type="browser",
            component_id="browser-789",
            correlation_id="corr-456",
            parent_event_id="parent-123",
            level="ERROR",
            message="Browser connection failed",
            data={"error": "Connection timeout", "url": "https://example.com"},
        )
        test_db.add(event)
        test_db.commit()

        retrieved = test_db.query(DebugEvent).filter_by(id=event.id).first()
        assert retrieved.event_type == DebugEventType.ERROR.value
        assert retrieved.level == "ERROR"
        assert retrieved.parent_event_id == "parent-123"

    def test_create_debug_event_state_snapshot(self, test_db):
        """Test creating a state snapshot event."""
        event = DebugEvent(
            event_type=DebugEventType.STATE_SNAPSHOT.value,
            component_type="workflow",
            component_id="workflow-456",
            correlation_id="corr-789",
            data={"state": {"step": 3, "status": "running"}},
        )
        test_db.add(event)
        test_db.commit()

        retrieved = test_db.query(DebugEvent).filter_by(id=event.id).first()
        assert retrieved.event_type == DebugEventType.STATE_SNAPSHOT.value
        assert retrieved.data["state"]["step"] == 3

    def test_debug_event_correlation_chain(self, test_db):
        """Test event correlation through parent-child relationships."""
        parent = DebugEvent(
            event_type=DebugEventType.LOG.value,
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-456",
            level="INFO",
            message="Parent event",
        )
        test_db.add(parent)
        test_db.commit()

        child = DebugEvent(
            event_type=DebugEventType.LOG.value,
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-456",
            parent_event_id=parent.id,
            level="INFO",
            message="Child event",
        )
        test_db.add(child)
        test_db.commit()

        # Verify parent-child relationship
        retrieved_child = test_db.query(DebugEvent).filter_by(id=child.id).first()
        assert retrieved_child.parent_event_id == parent.id

        # Query all events in correlation
        correlated_events = (
            test_db.query(DebugEvent)
            .filter_by(correlation_id="corr-456")
            .order_by(DebugEvent.timestamp)
            .all()
        )
        assert len(correlated_events) == 2

    def test_debug_event_index_on_component(self, test_db):
        """Test index on component_type and component_id."""
        event1 = DebugEvent(
            event_type=DebugEventType.LOG.value,
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-1",
            level="INFO",
            message="Event 1",
        )
        event2 = DebugEvent(
            event_type=DebugEventType.LOG.value,
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-2",
            level="INFO",
            message="Event 2",
        )
        test_db.add_all([event1, event2])
        test_db.commit()

        # Query by component
        events = (
            test_db.query(DebugEvent)
            .filter_by(component_type="agent", component_id="agent-123")
            .all()
        )
        assert len(events) == 2


class TestDebugInsight:
    """Tests for DebugInsight model."""

    def test_create_consistency_insight(self, test_db):
        """Test creating a consistency insight."""
        insight = DebugInsight(
            insight_type=DebugInsightType.CONSISTENCY.value,
            severity=DebugInsightSeverity.WARNING.value,
            title="Data inconsistency detected",
            description="Data sent to 5 nodes but only 4 confirmed receipt",
            summary="Data sent to all nodes, node-5 pending confirmation",
            evidence={"event_ids": ["event-1", "event-2"]},
            confidence_score=0.85,
            suggestions=["Retry sending to node-5", "Check network connectivity"],
            scope="distributed",
            affected_components=["node-1", "node-2", "node-3", "node-4", "node-5"],
        )
        test_db.add(insight)
        test_db.commit()

        retrieved = test_db.query(DebugInsight).filter_by(id=insight.id).first()
        assert retrieved is not None
        assert retrieved.insight_type == DebugInsightType.CONSISTENCY.value
        assert retrieved.severity == DebugInsightSeverity.WARNING.value
        assert retrieved.confidence_score == 0.85
        assert retrieved.resolved is False

    def test_create_performance_insight(self, test_db):
        """Test creating a performance insight."""
        insight = DebugInsight(
            insight_type=DebugInsightType.PERFORMANCE.value,
            severity=DebugInsightSeverity.INFO.value,
            title="Agent response time degraded",
            summary="Agent-456 response time increased by 200%",
            description="Average response time increased from 500ms to 1.5s",
            confidence_score=0.92,
            suggestions=["Check resource utilization", "Scale up agent capacity"],
            scope="component",
            affected_components=[{"type": "agent", "id": "agent-456"}],
        )
        test_db.add(insight)
        test_db.commit()

        retrieved = test_db.query(DebugInsight).filter_by(id=insight.id).first()
        assert retrieved.insight_type == DebugInsightType.PERFORMANCE.value
        assert retrieved.severity == DebugInsightSeverity.INFO.value

    def test_debug_insight_resolution(self, test_db):
        """Test marking insight as resolved."""
        insight = DebugInsight(
            insight_type=DebugInsightType.ERROR.value,
            severity=DebugInsightSeverity.CRITICAL.value,
            title="Critical error in workflow",
            summary="Workflow execution failed at step 5",
            confidence_score=0.95,
            scope="component",
            affected_components=[{"type": "workflow", "id": "workflow-789"}],
        )
        test_db.add(insight)
        test_db.commit()

        # Mark as resolved
        insight.resolved = True
        insight.resolution_notes = "Fixed by updating workflow configuration"
        test_db.commit()

        retrieved = test_db.query(DebugInsight).filter_by(id=insight.id).first()
        assert retrieved.resolved is True
        assert retrieved.resolution_notes == "Fixed by updating workflow configuration"

    def test_debug_insight_expiration(self, test_db):
        """Test insight expiration."""
        insight = DebugInsight(
            insight_type=DebugInsightType.ANOMALY.value,
            severity=DebugInsightSeverity.WARNING.value,
            title="Anomalous behavior detected",
            summary="Unusual spike in agent requests",
            confidence_score=0.75,
            scope="system",
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        test_db.add(insight)
        test_db.commit()

        retrieved = test_db.query(DebugInsight).filter_by(id=insight.id).first()
        assert retrieved.expires_at is not None
        assert retrieved.expires_at > datetime.utcnow()

    def test_debug_insight_source_event_link(self, test_db):
        """Test linking insight to source event."""
        event = DebugEvent(
            event_type=DebugEventType.ERROR.value,
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-456",
            level="ERROR",
            message="Agent error",
        )
        test_db.add(event)
        test_db.commit()

        insight = DebugInsight(
            insight_type=DebugInsightType.ERROR.value,
            severity=DebugInsightSeverity.CRITICAL.value,
            title="Agent error detected",
            summary="Agent-123 encountered critical error",
            confidence_score=0.95,
            scope="component",
            source_event_id=event.id,
        )
        test_db.add(insight)
        test_db.commit()

        # Verify relationship
        retrieved = test_db.query(DebugInsight).filter_by(id=insight.id).first()
        assert retrieved.source_event_id == event.id
        assert retrieved.event.id == event.id


class TestDebugStateSnapshot:
    """Tests for DebugStateSnapshot model."""

    def test_create_full_state_snapshot(self, test_db):
        """Test creating a full state snapshot."""
        snapshot = DebugStateSnapshot(
            component_type="agent",
            component_id="agent-123",
            operation_id="op-456",
            checkpoint_name="before_execution",
            state_data={"status": "running", "progress": 0.5, "variables": {"x": 10}},
            snapshot_type="full",
        )
        test_db.add(snapshot)
        test_db.commit()

        retrieved = test_db.query(DebugStateSnapshot).filter_by(id=snapshot.id).first()
        assert retrieved is not None
        assert retrieved.component_type == "agent"
        assert retrieved.snapshot_type == "full"
        assert retrieved.state_data["progress"] == 0.5

    def test_create_incremental_snapshot_with_diff(self, test_db):
        """Test creating incremental snapshot with diff."""
        # First snapshot
        snapshot1 = DebugStateSnapshot(
            component_type="agent",
            component_id="agent-123",
            operation_id="op-456",
            state_data={"status": "running", "progress": 0.5},
            snapshot_type="full",
        )
        test_db.add(snapshot1)
        test_db.commit()

        # Second snapshot with diff
        snapshot2 = DebugStateSnapshot(
            component_type="agent",
            component_id="agent-123",
            operation_id="op-456",
            state_data={"status": "running", "progress": 0.8},
            diff_from_previous={"progress": {"from": 0.5, "to": 0.8}},
            snapshot_type="incremental",
        )
        test_db.add(snapshot2)
        test_db.commit()

        retrieved = test_db.query(DebugStateSnapshot).filter_by(id=snapshot2.id).first()
        assert retrieved.snapshot_type == "incremental"
        assert retrieved.diff_from_previous is not None
        assert retrieved.diff_from_previous["progress"]["from"] == 0.5

    def test_query_snapshots_by_operation(self, test_db):
        """Test querying snapshots by operation_id."""
        snapshot1 = DebugStateSnapshot(
            component_type="workflow",
            component_id="workflow-789",
            operation_id="op-123",
            state_data={"step": 1},
            snapshot_type="full",
        )
        snapshot2 = DebugStateSnapshot(
            component_type="workflow",
            component_id="workflow-789",
            operation_id="op-123",
            state_data={"step": 2},
            snapshot_type="incremental",
        )
        test_db.add_all([snapshot1, snapshot2])
        test_db.commit()

        # Query by operation
        snapshots = (
            test_db.query(DebugStateSnapshot)
            .filter_by(operation_id="op-123")
            .order_by(DebugStateSnapshot.captured_at)
            .all()
        )
        assert len(snapshots) == 2
        assert snapshots[0].state_data["step"] == 1
        assert snapshots[1].state_data["step"] == 2


class TestDebugMetric:
    """Tests for DebugMetric model."""

    def test_create_metric(self, test_db):
        """Test creating a metric."""
        metric = DebugMetric(
            metric_name="agent_response_time",
            component_type="agent",
            component_id="agent-123",
            value=523.5,
            unit="ms",
            dimensions={"operation": "chat", "model": "gpt-4"},
        )
        test_db.add(metric)
        test_db.commit()

        retrieved = test_db.query(DebugMetric).filter_by(id=metric.id).first()
        assert retrieved is not None
        assert retrieved.metric_name == "agent_response_time"
        assert retrieved.value == 523.5
        assert retrieved.unit == "ms"

    def test_query_metrics_by_component(self, test_db):
        """Test querying metrics by component."""
        metric1 = DebugMetric(
            metric_name="response_time",
            component_type="agent",
            component_id="agent-123",
            value=500.0,
            unit="ms",
        )
        metric2 = DebugMetric(
            metric_name="throughput",
            component_type="agent",
            component_id="agent-123",
            value=100.0,
            unit="req/min",
        )
        test_db.add_all([metric1, metric2])
        test_db.commit()

        # Query by component
        metrics = (
            test_db.query(DebugMetric)
            .filter_by(component_type="agent", component_id="agent-123")
            .all()
        )
        assert len(metrics) == 2

    def test_metric_time_series(self, test_db):
        """Test querying metrics as time series."""
        import time

        # Create metrics at different times
        for i in range(5):
            metric = DebugMetric(
                metric_name="cpu_usage",
                component_type="system",
                component_id="server-1",
                value=50.0 + i * 10,
                unit="percentage",
            )
            test_db.add(metric)
            test_db.commit()
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Query time series
        metrics = (
            test_db.query(DebugMetric)
            .filter_by(metric_name="cpu_usage", component_id="server-1")
            .order_by(DebugMetric.timestamp)
            .all()
        )
        assert len(metrics) == 5
        assert metrics[0].value == 50.0
        assert metrics[4].value == 90.0


class TestDebugSession:
    """Tests for DebugSession model."""

    def test_create_debug_session(self, test_db):
        """Test creating a debug session."""
        session = DebugSession(
            session_name="Debug workflow failure",
            description="Investigating workflow-789 execution failure",
            filters={"component_type": "workflow", "component_id": "workflow-789"},
            scope={"time_range": "last_1h"},
        )
        test_db.add(session)
        test_db.commit()

        retrieved = test_db.query(DebugSession).filter_by(id=session.id).first()
        assert retrieved is not None
        assert retrieved.session_name == "Debug workflow failure"
        assert retrieved.active is True
        assert retrieved.resolved is False

    def test_update_session_counters(self, test_db):
        """Test updating session counters."""
        session = DebugSession(
            session_name="Test session",
            filters={},
            scope={},
        )
        test_db.add(session)
        test_db.commit()

        # Update counters
        session.event_count = 150
        session.insight_count = 5
        session.query_count = 20
        test_db.commit()

        retrieved = test_db.query(DebugSession).filter_by(id=session.id).first()
        assert retrieved.event_count == 150
        assert retrieved.insight_count == 5
        assert retrieved.query_count == 20

    def test_close_debug_session(self, test_db):
        """Test closing a debug session."""
        session = DebugSession(
            session_name="Test session",
            filters={},
            scope={},
            active=True,
        )
        test_db.add(session)
        test_db.commit()

        # Close session
        session.active = False
        session.resolved = True
        session.closed_at = datetime.utcnow()
        test_db.commit()

        retrieved = test_db.query(DebugSession).filter_by(id=session.id).first()
        assert retrieved.active is False
        assert retrieved.resolved is True
        assert retrieved.closed_at is not None

    def test_query_active_sessions(self, test_db):
        """Test querying active debug sessions."""
        session1 = DebugSession(
            session_name="Active session 1",
            filters={},
            scope={},
            active=True,
        )
        session2 = DebugSession(
            session_name="Active session 2",
            filters={},
            scope={},
            active=True,
        )
        session3 = DebugSession(
            session_name="Closed session",
            filters={},
            scope={},
            active=False,
        )
        test_db.add_all([session1, session2, session3])
        test_db.commit()

        # Query active sessions
        active_sessions = (
            test_db.query(DebugSession)
            .filter_by(active=True)
            .order_by(DebugSession.created_at)
            .all()
        )
        assert len(active_sessions) == 2


class TestDebugModelIndexes:
    """Tests for debug model indexes."""

    def test_debug_event_indexes(self, test_db):
        """Verify DebugEvent indexes are created."""
        # Create multiple events
        for i in range(10):
            event = DebugEvent(
                event_type=DebugEventType.LOG.value,
                component_type="agent",
                component_id=f"agent-{i % 3}",
                correlation_id=f"corr-{i}",
                level="INFO",
                message=f"Event {i}",
            )
            test_db.add(event)
        test_db.commit()

        # Test index queries
        events_by_component = (
            test_db.query(DebugEvent)
            .filter_by(component_type="agent", component_id="agent-1")
            .all()
        )
        assert len(events_by_component) > 0

        events_by_correlation = (
            test_db.query(DebugEvent).filter_by(correlation_id="corr-5").first()
        )
        assert events_by_correlation is not None

    def test_debug_insight_indexes(self, test_db):
        """Verify DebugInsight indexes are created."""
        # Create insights
        for i in range(10):
            insight = DebugInsight(
                insight_type=DebugInsightType.CONSISTENCY.value,
                severity=DebugInsightSeverity.WARNING.value if i % 2 == 0 else DebugInsightSeverity.CRITICAL.value,
                title=f"Insight {i}",
                summary=f"Summary {i}",
                confidence_score=0.8,
                scope="distributed",
            )
            test_db.add(insight)
        test_db.commit()

        # Test index queries
        critical_insights = (
            test_db.query(DebugInsight)
            .filter_by(severity=DebugInsightSeverity.CRITICAL.value)
            .all()
        )
        assert len(critical_insights) > 0

        unresolved_insights = (
            test_db.query(DebugInsight).filter_by(resolved=False).all()
        )
        assert len(unresolved_insights) == 10

    def test_debug_state_snapshot_indexes(self, test_db):
        """Verify DebugStateSnapshot indexes are created."""
        snapshot = DebugStateSnapshot(
            component_type="agent",
            component_id="agent-123",
            operation_id="op-456",
            checkpoint_name="test",
            state_data={"test": "data"},
            snapshot_type="full",
        )
        test_db.add(snapshot)
        test_db.commit()

        # Test index queries
        by_operation = (
            test_db.query(DebugStateSnapshot)
            .filter_by(operation_id="op-456")
            .first()
        )
        assert by_operation is not None

    def test_debug_metric_indexes(self, test_db):
        """Verify DebugMetric indexes are created."""
        metric = DebugMetric(
            metric_name="test_metric",
            component_type="agent",
            component_id="agent-123",
            value=100.0,
            unit="ms",
        )
        test_db.add(metric)
        test_db.commit()

        # Test index queries
        by_metric_name = (
            test_db.query(DebugMetric).filter_by(metric_name="test_metric").first()
        )
        assert by_metric_name is not None

    def test_debug_session_indexes(self, test_db):
        """Verify DebugSession indexes are created."""
        session = DebugSession(
            session_name="Test session",
            filters={},
            scope={},
            active=True,
            resolved=False,
        )
        test_db.add(session)
        test_db.commit()

        # Test index queries
        active_sessions = (
            test_db.query(DebugSession)
            .filter_by(active=True, resolved=False)
            .all()
        )
        assert len(active_sessions) == 1
