"""
Tests for Self-Healing Module
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from core.models import Base, DebugInsight, DebugEvent
from core.debug_self_healing import DebugSelfHealer, SelfHealingAction


@pytest.fixture
def db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    # Create only debug tables
    debug_tables = [
        DebugInsight.__table__,
        DebugEvent.__table__,
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
def healer(db):
    """Create self-healer instance."""
    return DebugSelfHealer(
        db_session=db,
        governance_service=None,  # No governance for tests
        require_approval=False
    )


class TestDebugSelfHealer:
    """Test self-healing functionality."""

    def test_determine_action_type_scale(self, healer):
        """Test action type detection for scaling."""
        action = healer._determine_action_type(
            "Scale up resources",
            None
        )
        assert action == SelfHealingAction.SCALE_RESOURCES

        action = healer._determine_action_type(
            "Scale resources up",
            None
        )
        assert action == SelfHealingAction.SCALE_RESOURCES

    def test_determine_action_type_restart(self, healer):
        """Test action type detection for restart."""
        action = healer._determine_action_type(
            "Restart the component",
            None
        )
        assert action == SelfHealingAction.RESTART_COMPONENT

    def test_determine_action_type_cache(self, healer):
        """Test action type detection for cache."""
        action = healer._determine_action_type(
            "Clear the cache",
            None
        )
        assert action == SelfHealingAction.CLEAR_CACHE

    def test_determine_action_type_timeout(self, healer):
        """Test action type detection for timeout."""
        action = healer._determine_action_type(
            "Increase timeout value",
            None
        )
        assert action == SelfHealingAction.ADJUST_TIMEOUT

    def test_determine_action_type_retry(self, healer):
        """Test action type detection for retry."""
        action = healer._determine_action_type(
            "Retry the operation",
            None
        )
        assert action == SelfHealingAction.RETRY_OPERATION

    def test_determine_action_type_isolate(self, healer):
        """Test action type detection for isolate."""
        action = healer._determine_action_type(
            "Isolate the component",
            None
        )
        assert action == SelfHealingAction.ISOLATE_COMPONENT

    def test_determine_action_type_unknown(self, healer):
        """Test action type detection for unknown action."""
        action = healer._determine_action_type(
            "Unknown action",
            None
        )
        assert action is None

    def test_assess_risk(self, healer, db):
        """Test risk assessment for actions."""
        insight = DebugInsight(
            id="insight-1",
            insight_type="error",
            severity="INFO",
            title="Test",
            description="Test",
            summary="Test",
            evidence={},
            confidence_score=0.9,
            suggestions=[],
            scope="component",
            affected_components=[],
            generated_at=datetime.utcnow()
        )

        # High risk actions
        assert healer._assess_risk(SelfHealingAction.RESTART_COMPONENT, insight) == "high"
        assert healer._assess_risk(SelfHealingAction.ISOLATE_COMPONENT, insight) == "high"

        # Medium risk
        assert healer._assess_risk(SelfHealingAction.SCALE_RESOURCES, insight) == "medium"

        # Low risk
        assert healer._assess_risk(SelfHealingAction.CLEAR_CACHE, insight) == "low"

    def test_estimate_duration(self, healer):
        """Test action duration estimation."""
        assert healer._estimate_duration(SelfHealingAction.SCALE_RESOURCES) == 5
        assert healer._estimate_duration(SelfHealingAction.RESTART_COMPONENT) == 2
        assert healer._estimate_duration(SelfHealingAction.CLEAR_CACHE) == 1
        assert healer._estimate_duration(SelfHealingAction.ADJUST_TIMEOUT) == 1
        assert healer._estimate_duration(SelfHealingAction.RETRY_OPERATION) == 2
        assert healer._estimate_duration(SelfHealingAction.ISOLATE_COMPONENT) == 10

    @pytest.mark.asyncio
    async def test_get_auto_heal_suggestions(self, healer, db):
        """Test getting auto-heal suggestions."""
        insight = DebugInsight(
            id="insight-1",
            insight_type="error",
            severity="WARNING",
            title="High Latency",
            description="Component is slow",
            summary="Performance issue detected",
            evidence={"latency_ms": 5000},
            confidence_score=0.9,
            suggestions=[
                "Scale up resources",
                "Clear cache",
                "Check network"
            ],
            scope="component",
            affected_components=[{"type": "agent", "id": "agent-123"}],
            generated_at=datetime.utcnow()
        )
        db.add(insight)
        db.commit()

        suggestions = await healer.get_auto_heal_suggestions("insight-1")

        assert len(suggestions) >= 2  # At least scale and clear cache
        assert any(s["action_type"] == SelfHealingAction.SCALE_RESOURCES for s in suggestions)
        assert any(s["action_type"] == SelfHealingAction.CLEAR_CACHE for s in suggestions)

        # Check suggestions have required fields
        for suggestion in suggestions:
            assert "action_type" in suggestion
            assert "suggestion" in suggestion
            assert "estimated_duration_minutes" in suggestion
            assert "success_probability" in suggestion
            assert "risk_level" in suggestion

    @pytest.mark.asyncio
    async def test_get_auto_heal_suggestions_no_insight(self, healer):
        """Test getting suggestions for non-existent insight."""
        suggestions = await healer.get_auto_heal_suggestions("non-existent")
        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_attempt_auto_heal_not_found(self, healer):
        """Test auto-heal with non-existent insight."""
        result = await healer.attempt_auto_heal(
            insight_id="non-existent",
            suggestion_text="Scale up resources"
        )

        assert result["status"] == "not_found"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_attempt_auto_heal_unsupported_action(self, healer, db):
        """Test auto-heal with unsupported action."""
        insight = DebugInsight(
            id="insight-1",
            insight_type="error",
            severity="INFO",
            title="Test",
            description="Test",
            summary="Test",
            evidence={},
            confidence_score=0.9,
            suggestions=["Do something unsupported"],
            scope="component",
            affected_components=[],
            generated_at=datetime.utcnow()
        )
        db.add(insight)
        db.commit()

        result = await healer.attempt_auto_heal(
            insight_id="insight-1",
            suggestion_text="Do something unsupported"
        )

        assert result["status"] == "unsupported_action"

    @pytest.mark.asyncio
    async def test_attempt_auto_heal_success(self, healer, db):
        """Test successful auto-heal execution."""
        insight = DebugInsight(
            id="insight-1",
            insight_type="error",
            severity="WARNING",
            title="Test",
            description="Test",
            summary="Test",
            evidence={},
            confidence_score=0.9,
            suggestions=["Scale up resources"],
            scope="component",
            affected_components=[],
            generated_at=datetime.utcnow()
        )
        db.add(insight)
        db.commit()

        result = await healer.attempt_auto_heal(
            insight_id="insight-1",
            suggestion_text="Scale up resources"
        )

        assert result["status"] == "success"
        assert "action_type" in result

    @pytest.mark.asyncio
    async def test_execute_healing_action(self, healer):
        """Test executing a healing action."""
        result = await healer.execute_healing_action(
            action_type=SelfHealingAction.CLEAR_CACHE,
            target_component={"type": "agent", "id": "agent-123"},
            parameters={"cache_type": "redis"}
        )

        assert result["status"] in ["success", "failed"]
        assert result["action_type"] == SelfHealingAction.CLEAR_CACHE
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_healing_history(self, healer, db):
        """Test getting healing history."""
        # Create some self-healing events
        for i in range(5):
            event = DebugEvent(
                id=f"event-{i}",
                event_type="system",
                component_type="debug_self_healer",
                component_id="system",
                correlation_id=f"correlation-{i}",
                level="INFO" if i < 4 else "ERROR",
                message=f"Self-healing action {i}",
                data={
                    "action_type": SelfHealingAction.SCALE_RESOURCES,
                    "target_component": {"type": "agent", "id": f"agent-{i}"},
                    "parameters": {}
                },
                timestamp=datetime.utcnow() - timedelta(hours=i)
            )
            db.add(event)

        db.commit()

        history = await healer.get_healing_history(limit=10)

        assert len(history) == 5
        assert all("action_type" in h for h in history)
        assert all("timestamp" in h for h in history)

    @pytest.mark.asyncio
    async def test_check_governance_no_service(self, healer, db):
        """Test governance check with no service."""
        insight = DebugInsight(
            id="insight-1",
            insight_type="error",
            severity="WARNING",
            title="Test",
            description="Test",
            summary="Test",
            evidence={},
            confidence_score=0.9,
            suggestions=[],
            scope="component",
            affected_components=[],
            generated_at=datetime.utcnow()
        )

        result = await healer._check_governance(
            action_type=SelfHealingAction.SCALE_RESOURCES,
            insight=insight,
            context=None
        )

        # Should allow when no governance service
        assert result["allowed"] is True
        assert "No governance service" in result["reason"]

    def test_parse_time_range(self, healer):
        """Test time range parsing."""
        now = datetime.utcnow()

        # Test different ranges
        result = healer._parse_time_range("last_1h")
        assert (now - result).total_seconds() < 3700  # ~1 hour

        result = healer._parse_time_range("last_24h")
        assert (now - result).total_seconds() < 86500  # ~24 hours

        result = healer._parse_time_range("last_7d")
        assert (now - result).total_seconds() < 605000  # ~7 days
