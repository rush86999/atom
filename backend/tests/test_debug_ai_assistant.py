"""
Tests for AI Debug Assistant
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from core.models import Base, DebugEvent, DebugInsight, DebugStateSnapshot
from core.debug_ai_assistant import DebugAIAssistant


@pytest.fixture
def db():
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

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def assistant(db):
    """Create AI assistant instance."""
    return DebugAIAssistant(
        db_session=db,
        enable_prediction=False,  # Disable prediction for tests
        enable_self_healing=False
    )


class TestDebugAIAssistant:
    """Test AI assistant functionality."""

    def test_detect_intent_component_health(self, assistant):
        """Test intent detection for component health queries."""
        intent = assistant._detect_intent("How is agent-123 doing?")
        assert intent == "component_health"

        intent = assistant._detect_intent("What's the status of workflow-456?")
        assert intent == "component_health"

    def test_detect_intent_failure_analysis(self, assistant):
        """Test intent detection for failure queries."""
        intent = assistant._detect_intent("Why is agent-123 failing?")
        assert intent == "failure_analysis"

        intent = assistant._detect_intent("What's causing workflow-456 to break?")
        assert intent == "failure_analysis"

    def test_detect_intent_performance(self, assistant):
        """Test intent detection for performance queries."""
        intent = assistant._detect_intent("Why is agent-123 so slow?")
        assert intent == "performance_analysis"

        intent = assistant._detect_intent("What's the latency for workflow-456?")
        assert intent == "performance_analysis"

    def test_detect_intent_consistency(self, assistant):
        """Test intent detection for consistency queries."""
        intent = assistant._detect_intent("Is the data consistent across nodes?")
        assert intent == "consistency_check"

        intent = assistant._detect_intent("Are all nodes in sync?")
        assert intent == "consistency_check"

    def test_detect_intent_error_patterns(self, assistant):
        """Test intent detection for error pattern queries."""
        intent = assistant._detect_intent("What are the recurring errors?")
        assert intent == "error_patterns"

        intent = assistant._detect_intent("Show me frequent error patterns")
        assert intent == "error_patterns"

    def test_detect_intent_general(self, assistant):
        """Test intent detection for general queries."""
        intent = assistant._detect_intent("What happened yesterday?")
        assert intent == "general_explanation"

        intent = assistant._detect_intent("Explain the debug output")
        assert intent == "general_explanation"

    @pytest.mark.asyncio
    async def test_handle_component_health_question_with_component(self, db, assistant):
        """Test health query with specific component."""
        now = datetime.utcnow()

        # Create events for healthy component
        for i in range(20):
            event = DebugEvent(
                id=f"event-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-healthy",
                correlation_id=f"op-{i}",
                level="INFO",
                message="Operation successful",
                timestamp=now - timedelta(hours=1)
            )
            db.add(event)

        db.commit()

        result = await assistant._handle_component_health_question(
            "How is agent-healthy?",
            context=None
        )

        assert result["confidence"] > 0.8
        assert "healthy" in result["answer"].lower()
        assert "health_score" in result["evidence"]

    @pytest.mark.asyncio
    async def test_handle_component_health_question_without_component(self, assistant):
        """Test health query without specific component."""
        result = await assistant._handle_component_health_question(
            "How is the system?",
            context=None
        )

        # Should ask for clarification
        assert result["confidence"] == 0.5
        assert "clarification_needed" in result

    @pytest.mark.asyncio
    async def test_handle_failure_question_with_errors(self, db, assistant):
        """Test failure query with error data."""
        now = datetime.utcnow()

        # Create error events (more recent than 1 hour ago)
        for i in range(10):
            event = DebugEvent(
                id=f"error-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-failing",
                correlation_id=f"op-{i}",
                level="ERROR",
                message="Connection timeout" if i < 7 else "Other error",
                timestamp=now - timedelta(minutes=30)  # 30 minutes ago, well within 1 hour
            )
            db.add(event)

        db.commit()

        result = await assistant._handle_failure_question(
            "Why is agent-failing failing?",
            context=None
        )

        assert result["confidence"] > 0.7
        assert "error" in result["answer"].lower()
        assert result["evidence"]["error_count"] == 10
        assert "Connection timeout" in str(result["evidence"]["common_errors"])

    @pytest.mark.asyncio
    async def test_handle_failure_question_no_errors(self, db, assistant):
        """Test failure query with no errors."""
        now = datetime.utcnow()

        # Create only success events
        for i in range(10):
            event = DebugEvent(
                id=f"event-{i}",
                event_type="log",
                component_type="agent",
                component_id="agent-ok",
                correlation_id=f"op-{i}",
                level="INFO",
                message="Success",
                timestamp=now - timedelta(hours=1)
            )
            db.add(event)

        db.commit()

        result = await assistant._handle_failure_question(
            "Why is agent-ok failing?",
            context=None
        )

        assert result["confidence"] > 0.7
        assert "no recent errors" in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_handle_error_patterns_question(self, db, assistant):
        """Test error patterns query."""
        now = datetime.utcnow()

        # Create some insights
        for i in range(5):
            insight = DebugInsight(
                id=f"insight-{i}",
                insight_type="error",
                severity="WARNING" if i < 3 else "INFO",
                title=f"Error Pattern {i}",
                description=f"Recurring error pattern {i}",
                summary=f"Error {i} occurs frequently",
                evidence={"occurrence_count": 10 + i},
                confidence_score=0.8,
                suggestions=["Check logs"],
                scope="component",
                affected_components=[{"type": "agent", "id": "agent-123"}],
                generated_at=now - timedelta(hours=i)
            )
            db.add(insight)

        db.commit()

        result = await assistant._handle_error_patterns_question(
            "What are the error patterns?",
            context=None
        )

        assert result["confidence"] > 0.7
        assert "patterns" in result["evidence"]

    @pytest.mark.asyncio
    async def test_handle_general_question(self, db, assistant):
        """Test general question handling."""
        result = await assistant._handle_general_question(
            "What's the system status?",
            context=None
        )

        assert "confidence" in result
        assert "answer" in result

    @pytest.mark.asyncio
    async def test_ask_with_error(self, assistant):
        """Test error handling in ask method."""
        # This should trigger an error (missing component_id in context)
        result = await assistant.ask(
            question="Invalid query",
            context=None
        )

        # Should return error response
        assert result["confidence"] >= 0.0
        assert "answer" in result

    def test_generate_failure_suggestions(self, assistant):
        """Test failure suggestion generation."""
        # Create mock errors
        errors = [
            DebugEvent(
                id="err-1",
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id="op-1",
                level="ERROR",
                message="Connection failed"
            )
        ]

        # Create mock insights
        insights = [
            DebugInsight(
                id="insight-1",
                insight_type="error",
                severity="WARNING",
                title="Connection Error",
                description="Frequent connection errors",
                summary="Connection issues detected",
                evidence={},
                confidence_score=0.8,
                suggestions=["Check network", "Retry connection"],
                scope="component",
                affected_components=[],
                generated_at=datetime.utcnow()
            )
        ]

        suggestions = assistant._generate_failure_suggestions(errors, insights)

        assert len(suggestions) > 0
        assert any("network" in s.lower() for s in suggestions)

    def test_get_system_recommendations(self, assistant):
        """Test system recommendation generation."""
        # Healthy system
        health = {
            "error_rate": 0.05,
            "overall_health_score": 90,
            "active_operations": 50
        }
        recommendations = assistant._get_system_recommendations(health)
        assert "operating normally" in recommendations[0].lower()

        # Unhealthy system
        health = {
            "error_rate": 0.6,
            "overall_health_score": 40,
            "active_operations": 150
        }
        recommendations = assistant._get_system_recommendations(health)
        assert len(recommendations) > 1
        assert any("error rate" in r.lower() for r in recommendations)

    def test_error_response(self, assistant):
        """Test error response generation."""
        result = assistant._error_response("Test error message")

        assert result["confidence"] == 0.0
        assert "error" in result["answer"].lower()
        assert result["evidence"]["error"] == "Test error message"
