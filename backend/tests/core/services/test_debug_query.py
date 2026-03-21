"""
Tests for DebugQuery

Tests for debug query API including:
- Component health queries
- Operation progress tracking
- Error explanation
- Component comparison
- Natural language queries
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch, MagicMock

from core.debug_query import DebugQuery
from core.models import (
    DebugEvent,
    DebugInsight,
    DebugEventType,
    DebugInsightType,
    DebugInsightSeverity,
)


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    from core.models import Base
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def debug_query(db_session):
    """Create debug query instance."""
    return DebugQuery(db_session)


@pytest.fixture
def sample_events(db_session):
    """Create sample debug events."""
    now = datetime.utcnow()

    # Create events
    events = [
        DebugEvent(
            id=f"event-{i}",
            component_type="agent",
            component_id="agent-1",
            level="INFO" if i % 3 != 0 else "ERROR",
            message=f"Event {i}",
            timestamp=now - timedelta(minutes=i),
            correlation_id=f"correlation-1",
            data={"step": i, "status": "completed" if i % 2 == 0 else "in_progress"}
        )
        for i in range(10)
    ]

    for event in events:
        db_session.add(event)
    db_session.commit()

    return events


@pytest.fixture
def sample_insights(db_session):
    """Create sample debug insights."""
    now = datetime.utcnow()

    insights = [
        DebugInsight(
            id=f"insight-{i}",
            insight_type=DebugInsightType.ERROR.value if i % 2 == 0 else DebugInsightType.PERFORMANCE.value,
            severity=DebugInsightSeverity.HIGH.value if i % 3 == 0 else DebugInsightSeverity.MEDIUM.value,
            title=f"Insight {i}",
            summary=f"Summary {i}",
            description=f"Description {i}",
            confidence_score=0.8 + (i * 0.01),
            generated_at=now - timedelta(hours=i),
            scope="component",
            source_event_id=f"event-{i}"
        )
        for i in range(5)
    ]

    for insight in insights:
        db_session.add(insight)
    db_session.commit()

    return insights


class TestDebugQueryInit:
    """Tests for DebugQuery initialization."""

    def test_init_with_db(self, db_session):
        """Test initialization with database session."""
        query = DebugQuery(db_session)
        assert query.db == db_session
        assert query.logger is not None

    def test_init_with_cache_disabled(self, db_session):
        """Test initialization with cache disabled."""
        with patch('core.debug_query.DEBUG_QUERY_CACHE_ENABLED', False):
            query = DebugQuery(db_session)
            assert query.cache is None


class TestGetComponentHealth:
    """Tests for get_component_health method."""

    @pytest.mark.asyncio
    async def test_get_component_health_basic(self, debug_query, sample_events):
        """Test basic component health query."""
        result = await debug_query.get_component_health(
            component_type="agent",
            component_id="agent-1",
            time_range="1h"
        )

        assert result["component_type"] == "agent"
        assert result["component_id"] == "agent-1"
        assert "health_score" in result
        assert "status" in result
        assert result["total_events"] == 10

    @pytest.mark.asyncio
    async def test_get_component_health_no_events(self, debug_query):
        """Test health query for component with no events."""
        result = await debug_query.get_component_health(
            component_type="workflow",
            component_id="non-existent",
            time_range="1h"
        )

        assert result["health_score"] == 100  # No errors
        assert result["total_events"] == 0

    @pytest.mark.asyncio
    async def test_get_component_health_status_calculation(self, debug_query, sample_events):
        """Test health status calculation."""
        result = await debug_query.get_component_health(
            component_type="agent",
            component_id="agent-1",
            time_range="1h"
        )

        if result["total_events"] > 0:
            error_rate = result["error_rate"]
            if error_rate == 0:
                assert result["status"] == "healthy"
            elif error_rate < 0.1:
                assert result["status"] in ["healthy", "degraded"]
            else:
                assert result["status"] in ["degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_get_component_health_with_insights(self, debug_query, sample_events, sample_insights):
        """Test health query includes insights."""
        result = await debug_query.get_component_health(
            component_type="agent",
            component_id="agent-1",
            time_range="24h"
        )

        assert "insights" in result
        assert isinstance(result["insights"], list)


class TestGetOperationProgress:
    """Tests for get_operation_progress method."""

    @pytest.mark.asyncio
    async def test_get_operation_progress_basic(self, debug_query, sample_events):
        """Test basic operation progress query."""
        result = await debug_query.get_operation_progress("correlation-1")

        assert result["operation_id"] == "correlation-1"
        assert "progress" in result
        assert "status" in result
        assert result["total_steps"] == 10

    @pytest.mark.asyncio
    async def test_get_operation_progress_not_found(self, debug_query):
        """Test progress query for non-existent operation."""
        result = await debug_query.get_operation_progress("non-existent")

        assert result["status"] == "not_found"
        assert result["progress"] == 0

    @pytest.mark.asyncio
    async def test_get_operation_progress_completed(self, debug_query, db_session):
        """Test progress for completed operation."""
        now = datetime.utcnow()

        # Create completed events
        for i in range(5):
            event = DebugEvent(
                id=f"completed-event-{i}",
                component_type="workflow",
                component_id="workflow-1",
                level="INFO",
                message=f"Step {i} completed",
                timestamp=now - timedelta(minutes=i),
                correlation_id="completed-op",
                data={"step": i, "status": "completed"}
            )
            db_session.add(event)
        db_session.commit()

        result = await debug_query.get_operation_progress("completed-op")

        assert result["progress"] == 1.0
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_operation_progress_with_errors(self, debug_query, db_session):
        """Test progress with error events."""
        now = datetime.utcnow()

        # Create events with errors
        for i in range(5):
            event = DebugEvent(
                id=f"error-event-{i}",
                component_type="agent",
                component_id="agent-1",
                level="ERROR" if i == 2 else "INFO",
                message=f"Step {i}",
                timestamp=now - timedelta(minutes=i),
                correlation_id="error-op",
                data={"step": i, "status": "completed"}
            )
            db_session.add(event)
        db_session.commit()

        result = await debug_query.get_operation_progress("error-op")

        assert result["error_count"] == 1
        assert result["status"] == "failed"


class TestExplainError:
    """Tests for explain_error method."""

    @pytest.mark.asyncio
    async def test_explain_error_basic(self, debug_query, db_session):
        """Test basic error explanation."""
        # Create error event
        error_event = DebugEvent(
            id="error-to-explain",
            component_type="agent",
            component_id="agent-1",
            level="ERROR",
            message="Connection timeout",
            timestamp=datetime.utcnow(),
            data={"error": "timeout"}
        )
        debug_query.db.add(error_event)
        debug_query.db.commit()

        result = await debug_query.explain_error("error-to-explain")

        assert result["found"] is True
        assert result["message"] == "Connection timeout"
        assert "root_cause" in result
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_explain_error_not_found(self, debug_query):
        """Test explaining non-existent error."""
        result = await debug_query.explain_error("non-existent-error")

        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_explain_error_with_insight(self, debug_query, db_session):
        """Test error explanation with insight."""
        error_event = DebugEvent(
            id="error-with-insight",
            component_type="agent",
            component_id="agent-1",
            level="ERROR",
            message="Error with insight",
            timestamp=datetime.utcnow(),
            data={}
        )
        debug_query.db.add(error_event)

        insight = DebugInsight(
            id="related-insight",
            insight_type=DebugInsightType.ERROR.value,
            severity=DebugInsightSeverity.HIGH.value,
            title="Root Cause",
            summary="Memory leak detected",
            description="Agent has memory leak",
            confidence_score=0.9,
            generated_at=datetime.utcnow(),
            source_event_id="error-with-insight",
            suggestions=["Restart agent", "Increase memory"]
        )
        debug_query.db.add(insight)
        debug_query.db.commit()

        result = await debug_query.explain_error("error-with-insight")

        assert result["found"] is True
        assert result["root_cause"] == "Memory leak detected"
        assert "Restart agent" in result["suggestions"]


class TestCompareComponents:
    """Tests for compare_components method."""

    @pytest.mark.asyncio
    async def test_compare_components_basic(self, debug_query, db_session):
        """Test basic component comparison."""
        # Create events for two agents
        now = datetime.utcnow()

        for agent_id, error_count in [("agent-1", 2), ("agent-2", 5)]:
            for i in range(10):
                event = DebugEvent(
                    id=f"compare-event-{agent_id}-{i}",
                    component_type="agent",
                    component_id=agent_id,
                    level="ERROR" if i < error_count else "INFO",
                    message=f"Event {i}",
                    timestamp=now - timedelta(minutes=i),
                    data={}
                )
                db_session.add(event)
        db_session.commit()

        result = await debug_query.compare_components(
            components=[
                {"type": "agent", "id": "agent-1"},
                {"type": "agent", "id": "agent-2"}
            ],
            time_range="1h"
        )

        assert len(result["components"]) == 2
        assert "insights" in result

    @pytest.mark.asyncio
    async def test_compare_components_single(self, debug_query):
        """Test comparing single component."""
        result = await debug_query.compare_components(
            components=[{"type": "agent", "id": "agent-1"}]
        )

        assert len(result["components"]) == 1
        assert "Need at least 2 components" in result["insights"]


class TestNaturalLanguageQuery:
    """Tests for ask method (natural language queries)."""

    @pytest.mark.asyncio
    async def test_ask_why_failing(self, debug_query, db_session):
        """Test asking why component is failing."""
        # Create error events
        now = datetime.utcnow()
        for i in range(5):
            event = DebugEvent(
                id=f"failing-event-{i}",
                component_type="workflow",
                component_id="workflow-789",
                level="ERROR",
                message="Database connection failed",
                timestamp=now - timedelta(minutes=i),
                data={}
            )
            db_session.add(event)
        db_session.commit()

        result = await debug_query.ask("Why is workflow-789 failing?")

        assert result["confidence"] > 0
        assert "answer" in result

    @pytest.mark.asyncio
    async def test_ask_health_query(self, debug_query, sample_events):
        """Test asking about component health."""
        result = await debug_query.ask("What is the health of agent-1?")

        assert "answer" in result
        assert result["confidence"] >= 0

    @pytest.mark.asyncio
    async def test_ask_unrecognized(self, debug_query):
        """Test asking unrecognized question."""
        result = await debug_query.ask("What is the meaning of life?")

        assert "couldn't understand" in result["answer"].lower()
        assert result["confidence"] == 0.3


class TestHelperMethods:
    """Tests for helper methods."""

    def test_parse_time_range_hours(self, debug_query):
        """Test parsing time range in hours."""
        result = debug_query._parse_time_range("5h")
        # Should be approximately 5 hours ago
        diff = datetime.utcnow() - result
        assert diff.total_seconds() > 4 * 3600
        assert diff.total_seconds() < 6 * 3600

    def test_parse_time_range_days(self, debug_query):
        """Test parsing time range in days."""
        result = debug_query._parse_time_range("2d")
        # Should be approximately 2 days ago
        diff = datetime.utcnow() - result
        assert diff.total_seconds() > 1.5 * 86400
        assert diff.total_seconds() < 2.5 * 86400

    def test_parse_time_range_minutes(self, debug_query):
        """Test parsing time range in minutes."""
        result = debug_query._parse_time_range("30m")
        # Should be approximately 30 minutes ago
        diff = datetime.utcnow() - result
        assert diff.total_seconds() > 25 * 60
        assert diff.total_seconds() < 35 * 60

    def test_parse_time_range_default(self, debug_query):
        """Test default time range parsing."""
        result = debug_query._parse_time_range("invalid")
        # Should default to 1 hour
        diff = datetime.utcnow() - result
        assert diff.total_seconds() > 0.9 * 3600
        assert diff.total_seconds() < 1.1 * 3600

    def test_insight_to_dict(self, debug_query, sample_insights):
        """Test converting insight to dictionary."""
        insight = sample_insights[0]
        result = debug_query._insight_to_dict(insight)

        assert result["id"] == insight.id
        assert result["type"] == insight.insight_type
        assert result["severity"] == insight.severity
        assert result["title"] == insight.title
        assert "confidence_score" in result


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_get_component_health_error(self, debug_query):
        """Test error handling in get_component_health."""
        with patch.object(debug_query.db, 'query', side_effect=Exception("DB error")):
            result = await debug_query.get_component_health("agent", "agent-1")

            assert result["status"] == "error"
            assert "health_score" == 0

    @pytest.mark.asyncio
    async def test_explain_error_handling(self, debug_query):
        """Test error handling in explain_error."""
        with patch.object(debug_query.db, 'query', side_effect=Exception("DB error")):
            result = await debug_query.explain_error("error-1")

            assert result["found"] is False

    @pytest.mark.asyncio
    async def test_compare_components_error(self, debug_query):
        """Test error handling in compare_components."""
        with patch.object(debug_query.db, 'query', side_effect=Exception("DB error")):
            result = await debug_query.compare_components([])

            assert "components" in result
            assert len(result["insights"]) > 0
