"""
Tests for Condition Monitoring Service

Tests condition monitors that trigger alerts when thresholds are exceeded.
"""

import sys
import os

# Prevent numpy/pandas from loading real DLLs that crash on Py 3.13
sys.modules["numpy"] = None
sys.modules["pandas"] = None
sys.modules["lancedb"] = None
sys.modules["pyarrow"] = None

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, MagicMock

# Mock the imports before importing the service
sys.modules['core.agent_integration_gateway'] = MagicMock()
sys.modules['integrations.atom_discord_integration'] = MagicMock()
sys.modules['integrations.atom_whatsapp_integration'] = MagicMock()
sys.modules['integrations.atom_telegram_integration'] = MagicMock()
sys.modules['integrations.google_chat_enhanced_service'] = MagicMock()
sys.modules['integrations.meta_business_service'] = MagicMock()
sys.modules['integrations.marketing_unified_service'] = MagicMock()
sys.modules['integrations.ecommerce_unified_service'] = MagicMock()
sys.modules['integrations.slack_enhanced_service'] = MagicMock()
sys.modules['integrations.teams_enhanced_service'] = MagicMock()
sys.modules['integrations.document_logic_service'] = MagicMock()
sys.modules['integrations.shopify_service'] = MagicMock()
sys.modules['integrations.openclaw_service'] = MagicMock()

from core.models import AgentRegistry, AgentStatus, ConditionMonitorType
from core.condition_checkers import ConditionCheckers
from core.condition_monitoring_service import ConditionMonitoringService


# Test database setup
import uuid
TEST_DATABASE_URL = f"sqlite:///./test_condition_monitoring_{uuid.uuid4()}.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create a fresh database for each test."""
    # Drop all tables first to ensure clean state
    from core.database import Base
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def autonomous_agent(db):
    """Create an AUTONOMOUS agent for testing."""
    agent = AgentRegistry(
        name="Autonomous Agent",
        category="testing",
        module_path="test.autonomous",
        class_name="AutonomousAgent",
        description="An autonomous agent for testing",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


class TestConditionCheckers:
    """Tests for condition checker implementations."""

    def test_compare_values_greater_than(self, db):
        """Test > comparison."""
        checkers = ConditionCheckers(db)

        assert checkers._compare_values(150, ">", 100) == True
        assert checkers._compare_values(50, ">", 100) == False

    def test_compare_values_less_than(self, db):
        """Test < comparison."""
        checkers = ConditionCheckers(db)

        assert checkers._compare_values(50, "<", 100) == True
        assert checkers._compare_values(150, "<", 100) == False

    def test_compare_values_equal(self, db):
        """Test == comparison."""
        checkers = ConditionCheckers(db)

        assert checkers._compare_values(100, "==", 100) == True
        assert checkers._compare_values(99, "==", 100) == False

    def test_compare_values_greater_or_equal(self, db):
        """Test >= comparison."""
        checkers = ConditionCheckers(db)

        assert checkers._compare_values(100, ">=", 100) == True
        assert checkers._compare_values(150, ">=", 100) == True
        assert checkers._compare_values(50, ">=", 100) == False

    def test_compare_values_less_or_equal(self, db):
        """Test <= comparison."""
        checkers = ConditionCheckers(db)

        assert checkers._compare_values(100, "<=", 100) == True
        assert checkers._compare_values(50, "<=", 100) == True
        assert checkers._compare_values(150, "<=", 100) == False

    def test_compare_values_not_equal(self, db):
        """Test != comparison."""
        checkers = ConditionCheckers(db)

        assert checkers._compare_values(99, "!=", 100) == True
        assert checkers._compare_values(100, "!=", 100) == False


class TestConditionMonitoringService:
    """Tests for the condition monitoring service."""

    def test_create_inbox_volume_monitor(self, db, autonomous_agent):
        """Test creating an inbox volume monitor."""
        service = ConditionMonitoringService(db)

        monitor = service.create_monitor(
            agent_id=autonomous_agent.id,
            name="High Inbox Volume",
            condition_type=ConditionMonitorType.INBOX_VOLUME.value,
            threshold_config={
                "metric": "unread_count",
                "operator": ">",
                "value": 100,
            },
            platforms=[
                {"platform": "slack", "recipient_id": "C12345"}
            ],
            check_interval_seconds=300,
        )

        assert monitor.condition_type == ConditionMonitorType.INBOX_VOLUME.value
        assert monitor.name == "High Inbox Volume"
        assert monitor.status == "active"
        assert monitor.threshold_config["operator"] == ">"

    def test_create_task_backlog_monitor(self, db, autonomous_agent):
        """Test creating a task backlog monitor."""
        service = ConditionMonitoringService(db)

        monitor = service.create_monitor(
            agent_id=autonomous_agent.id,
            name="Task Backlog",
            condition_type=ConditionMonitorType.TASK_BACKLOG.value,
            threshold_config={
                "metric": "pending_count",
                "operator": ">",
                "value": 50,
            },
            platforms=[
                {"platform": "discord", "recipient_id": "G67890"}
            ],
        )

        assert monitor.condition_type == ConditionMonitorType.TASK_BACKLOG.value
        assert monitor.threshold_config["value"] == 50

    def test_create_api_metrics_monitor(self, db, autonomous_agent):
        """Test creating an API metrics monitor."""
        service = ConditionMonitoringService(db)

        monitor = service.create_monitor(
            agent_id=autonomous_agent.id,
            name="High Error Rate",
            condition_type=ConditionMonitorType.API_METRICS.value,
            threshold_config={
                "metric": "error_rate",
                "operator": ">",
                "value": 0.05,
                "window": "5m",
            },
            platforms=[
                {"platform": "slack", "recipient_id": "C12345"}
            ],
        )

        assert monitor.condition_type == ConditionMonitorType.API_METRICS.value
        assert monitor.threshold_config["metric"] == "error_rate"

    def test_create_composite_monitor(self, db, autonomous_agent):
        """Test creating a composite monitor with AND/OR logic."""
        service = ConditionMonitoringService(db)

        monitor = service.create_monitor(
            agent_id=autonomous_agent.id,
            name="Composite Condition",
            condition_type=ConditionMonitorType.COMPOSITE.value,
            threshold_config={},
            composite_logic="AND",
            composite_conditions=[
                {
                    "condition_type": "inbox_volume",
                    "threshold_config": {"metric": "unread_count", "operator": ">", "value": 100}
                },
                {
                    "condition_type": "task_backlog",
                    "threshold_config": {"metric": "pending_count", "operator": ">", "value": 50}
                }
            ],
            platforms=[
                {"platform": "slack", "recipient_id": "C12345"}
            ],
        )

        assert monitor.condition_type == ConditionMonitorType.COMPOSITE.value
        assert monitor.composite_logic == "AND"
        assert len(monitor.composite_conditions) == 2

    def test_pause_monitor(self, db, autonomous_agent):
        """Test pausing a monitor."""
        service = ConditionMonitoringService(db)

        monitor = service.create_monitor(
            agent_id=autonomous_agent.id,
            name="Test Monitor",
            condition_type=ConditionMonitorType.INBOX_VOLUME.value,
            threshold_config={"metric": "unread_count", "operator": ">", "value": 100},
            platforms=[{"platform": "slack", "recipient_id": "C12345"}],
        )

        paused_monitor = service.pause_monitor(monitor.id)

        assert paused_monitor.status == "paused"

    def test_resume_monitor(self, db, autonomous_agent):
        """Test resuming a paused monitor."""
        service = ConditionMonitoringService(db)

        monitor = service.create_monitor(
            agent_id=autonomous_agent.id,
            name="Test Monitor",
            condition_type=ConditionMonitorType.INBOX_VOLUME.value,
            threshold_config={"metric": "unread_count", "operator": ">", "value": 100},
            platforms=[{"platform": "slack", "recipient_id": "C12345"}],
        )

        # Pause first
        service.pause_monitor(monitor.id)

        # Resume
        resumed_monitor = service.resume_monitor(monitor.id)

        assert resumed_monitor.status == "active"

    def test_delete_monitor(self, db, autonomous_agent):
        """Test deleting a monitor."""
        service = ConditionMonitoringService(db)

        monitor = service.create_monitor(
            agent_id=autonomous_agent.id,
            name="Test Monitor",
            condition_type=ConditionMonitorType.INBOX_VOLUME.value,
            threshold_config={"metric": "unread_count", "operator": ">", "value": 100},
            platforms=[{"platform": "slack", "recipient_id": "C12345"}],
        )

        # Delete
        deleted_monitor = service.delete_monitor(monitor.id)

        assert deleted_monitor.id == monitor.id

        # Verify it's deleted
        found = service.get_monitor(monitor_id=monitor.id)
        assert found is None

    def test_update_monitor(self, db, autonomous_agent):
        """Test updating a monitor."""
        service = ConditionMonitoringService(db)

        monitor = service.create_monitor(
            agent_id=autonomous_agent.id,
            name="Original Name",
            condition_type=ConditionMonitorType.INBOX_VOLUME.value,
            threshold_config={"metric": "unread_count", "operator": ">", "value": 100},
            platforms=[{"platform": "slack", "recipient_id": "C12345"}],
        )

        # Update
        updated_monitor = service.update_monitor(
            monitor_id=monitor.id,
            name="Updated Name",
            threshold_config={"metric": "unread_count", "operator": ">", "value": 200},
        )

        assert updated_monitor.name == "Updated Name"
        assert updated_monitor.threshold_config["value"] == 200

    def test_get_monitors_by_agent(self, db, autonomous_agent):
        """Test filtering monitors by agent."""
        service = ConditionMonitoringService(db)

        # Create monitors
        service.create_monitor(
            agent_id=autonomous_agent.id,
            name="Monitor 1",
            condition_type=ConditionMonitorType.INBOX_VOLUME.value,
            threshold_config={"metric": "unread_count", "operator": ">", "value": 100},
            platforms=[{"platform": "slack", "recipient_id": "C12345"}],
        )
        service.create_monitor(
            agent_id=autonomous_agent.id,
            name="Monitor 2",
            condition_type=ConditionMonitorType.TASK_BACKLOG.value,
            threshold_config={"metric": "pending_count", "operator": ">", "value": 50},
            platforms=[{"platform": "discord", "recipient_id": "G67890"}],
        )

        # Get monitors for this agent
        monitors = service.get_monitors(agent_id=autonomous_agent.id)

        assert len(monitors) == 2
        assert all(m.agent_id == autonomous_agent.id for m in monitors)


class TestMonitoringPresets:
    """Tests for monitoring presets."""

    def test_get_presets(self):
        """Test getting monitoring presets."""
        # Create mock DB
        mock_db = MagicMock()
        service = ConditionMonitoringService(mock_db)

        presets = service.get_presets()

        assert len(presets) >= 4  # At least 4 presets
        preset_names = [p["name"] for p in presets]

        assert "High Inbox Volume" in preset_names
        assert "Task Backlog" in preset_names
        assert "High API Error Rate" in preset_names
        assert "Database Connection Pool" in preset_names

    def test_preset_structure(self):
        """Test that presets have required fields."""
        mock_db = MagicMock()
        service = ConditionMonitoringService(mock_db)

        presets = service.get_presets()

        for preset in presets:
            assert "name" in preset
            assert "description" in preset
            assert "condition_type" in preset
            assert "threshold_config" in preset
            assert "check_interval_seconds" in preset
            assert "recommended_platforms" in preset


class TestConditionMonitoringValidation:
    """Tests for validation logic."""

    def test_composite_requires_logic(self, db, autonomous_agent):
        """Test that composite monitors require logic and conditions."""
        service = ConditionMonitoringService(db)

        with pytest.raises(Exception) as exc_info:
            service.create_monitor(
                agent_id=autonomous_agent.id,
                name="Invalid Composite",
                condition_type=ConditionMonitorType.COMPOSITE.value,
                threshold_config={},
                composite_logic=None,  # Missing
                composite_conditions=None,  # Missing
                platforms=[{"platform": "slack", "recipient_id": "C12345"}],
            )

        assert "composite_logic" in str(exc_info.value).lower() or "composite_conditions" in str(exc_info.value).lower()

    def test_invalid_agent_raises_error(self, db):
        """Test that invalid agent ID raises error."""
        service = ConditionMonitoringService(db)

        with pytest.raises(Exception) as exc_info:
            service.create_monitor(
                agent_id="non-existent-id",
                name="Test Monitor",
                condition_type=ConditionMonitorType.INBOX_VOLUME.value,
                threshold_config={"metric": "unread_count", "operator": ">", "value": 100},
                platforms=[{"platform": "slack", "recipient_id": "C12345"}],
            )

        assert "not found" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
