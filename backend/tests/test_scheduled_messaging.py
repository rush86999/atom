"""
Tests for Scheduled Messaging Service

Tests scheduled and recurring messages with cron expression support.
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

from core.database import Base
from core.models import AgentRegistry, AgentStatus, User, UserRole, ScheduledMessageStatus
from core.scheduled_messaging_service import ScheduledMessagingService
from core.cron_parser import natural_language_to_cron, CronParser


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_scheduled_messaging.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create a fresh database for each test."""
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


class TestScheduledMessageCreation:
    """Tests for creating scheduled messages."""

    def test_create_one_time_scheduled_message(self, db, autonomous_agent):
        """Test creating a one-time scheduled message."""
        service = ScheduledMessagingService(db)

        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=2)
        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Scheduled message",
            schedule_type="one_time",
            scheduled_for=scheduled_time,
        )

        assert message.schedule_type == "one_time"
        assert message.next_run == scheduled_time
        assert message.status == ScheduledMessageStatus.ACTIVE.value
        assert message.cron_expression is None

    def test_create_recurring_message_with_cron(self, db, autonomous_agent):
        """Test creating a recurring message with cron expression."""
        service = ScheduledMessagingService(db)

        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Daily report",
            schedule_type="recurring",
            cron_expression="0 9 * * *",  # Daily at 9am
        )

        assert message.schedule_type == "recurring"
        assert message.cron_expression == "0 9 * * *"
        assert message.status == ScheduledMessageStatus.ACTIVE.value
        assert message.next_run is not None

    def test_create_recurring_message_with_natural_language(self, db, autonomous_agent):
        """Test creating a recurring message with natural language."""
        service = ScheduledMessagingService(db)

        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Daily report",
            schedule_type="recurring",
            natural_language_schedule="every day at 9am",
        )

        assert message.schedule_type == "recurring"
        assert message.cron_expression == "0 9 * * *"
        assert message.natural_language_schedule == "every day at 9am"
        assert message.status == ScheduledMessageStatus.ACTIVE.value

    def test_create_message_with_template_variables(self, db, autonomous_agent):
        """Test creating a message with template variables."""
        service = ScheduledMessagingService(db)

        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Hello {{name}}, your appointment is at {{time}}",
            schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
            template_variables={"name": "John", "time": "2:00 PM"},
        )

        assert message.template_variables == {"name": "John", "time": "2:00 PM"}

    def test_create_message_with_limits(self, db, autonomous_agent):
        """Test creating a message with max_runs and end_date."""
        service = ScheduledMessagingService(db)

        end_date = datetime.now(timezone.utc) + timedelta(days=30)
        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Limited recurring message",
            schedule_type="recurring",
            cron_expression="0 9 * * *",
            max_runs=10,
            end_date=end_date,
        )

        assert message.max_runs == 10
        assert message.end_date == end_date


class TestScheduledMessageManagement:
    """Tests for managing scheduled messages."""

    def test_pause_scheduled_message(self, db, autonomous_agent):
        """Test pausing a scheduled message."""
        service = ScheduledMessagingService(db)

        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Test message",
            schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        paused_message = service.pause_scheduled_message(message.id)

        assert paused_message.status == ScheduledMessageStatus.PAUSED.value

    def test_resume_scheduled_message(self, db, autonomous_agent):
        """Test resuming a paused scheduled message."""
        service = ScheduledMessagingService(db)

        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Test message",
            schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Pause first
        service.pause_scheduled_message(message.id)

        # Resume
        resumed_message = service.resume_scheduled_message(message.id)

        assert resumed_message.status == ScheduledMessageStatus.ACTIVE.value

    def test_cancel_scheduled_message(self, db, autonomous_agent):
        """Test cancelling a scheduled message."""
        service = ScheduledMessagingService(db)

        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Test message",
            schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        cancelled_message = service.cancel_scheduled_message(message.id)

        assert cancelled_message.status == ScheduledMessageStatus.CANCELLED.value

    def test_update_scheduled_message(self, db, autonomous_agent):
        """Test updating a scheduled message."""
        service = ScheduledMessagingService(db)

        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Original template",
            schedule_type="recurring",
            cron_expression="0 9 * * *",
        )

        # Update template and max_runs
        updated_message = service.update_scheduled_message(
            message_id=message.id,
            template="Updated template",
            max_runs=20,
        )

        assert updated_message.template == "Updated template"
        assert updated_message.max_runs == 20


class TestTemplateVariableSubstitution:
    """Tests for template variable substitution."""

    def test_substitute_user_variables(self, db, autonomous_agent):
        """Test substituting user-defined variables."""
        service = ScheduledMessagingService(db)

        template = "Hello {{name}}, your balance is ${{amount}}"
        variables = {"name": "Alice", "amount": "100"}

        result = service._substitute_template_variables(template, variables)

        assert result == "Hello Alice, your balance is $100"

    def test_substitute_builtin_variables(self, db, autonomous_agent):
        """Test substituting built-in variables (date, time, etc.)."""
        service = ScheduledMessagingService(db)

        template = "Report for {{date}} at {{time}}"
        variables = {}

        result = service._substitute_template_variables(template, variables)

        # Should contain actual date and time
        assert "{{date}}" not in result
        assert "{{time}}" not in result
        assert "Report for" in result

    def test_user_variables_override_builtins(self, db, autonomous_agent):
        """Test that user variables override built-in variables."""
        service = ScheduledMessagingService(db)

        template = "Date: {{date}}"
        variables = {"date": "CUSTOM_DATE"}

        result = service._substitute_template_variables(template, variables)

        assert result == "Date: CUSTOM_DATE"


class TestCronParser:
    """Tests for cron expression parsing."""

    def test_parse_every_day_at_9am(self):
        """Test parsing 'every day at 9am'."""
        result = natural_language_to_cron("every day at 9am")
        assert result == "0 9 * * *"

    def test_parse_every_monday_at_2pm(self):
        """Test parsing 'every monday at 2:00pm'."""
        result = natural_language_to_cron("every monday at 2:00pm")
        assert result == "0 14 * * 1"

    def test_parse_hourly(self):
        """Test parsing 'hourly'."""
        result = natural_language_to_cron("hourly")
        assert result == "0 * * * *"

    def test_parse_daily(self):
        """Test parsing 'daily'."""
        result = natural_language_to_cron("daily")
        assert result == "0 9 * * *"

    def test_parse_weekly(self):
        """Test parsing 'weekly'."""
        result = natural_language_to_cron("weekly")
        assert result == "0 9 * * 1"

    def test_parse_monthly(self):
        """Test parsing 'monthly'."""
        result = natural_language_to_cron("monthly")
        assert result == "0 9 1 * *"

    def test_parse_yearly(self):
        """Test parsing 'yearly'."""
        result = natural_language_to_cron("yearly")
        assert result == "0 9 1 1 *"

    def test_parse_invalid_input(self):
        """Test parsing invalid input raises error."""
        with pytest.raises(ValueError):
            natural_language_to_cron("gibberish input")

    def test_calculate_next_run_daily(self):
        """Test calculating next run for daily schedule."""
        parser = CronParser()
        cron = "0 9 * * *"  # Daily at 9am

        now = datetime(2026, 2, 4, 8, 0, 0, tzinfo=timezone.utc)
        next_run = parser.get_next_run(cron, after=now)

        # Should be 9am on the same day
        assert next_run.hour == 9
        assert next_run.day == 4

    def test_calculate_next_run_hourly(self):
        """Test calculating next run for hourly schedule."""
        parser = CronParser()
        cron = "0 * * * *"  # Every hour

        now = datetime(2026, 2, 4, 8, 30, 0, tzinfo=timezone.utc)
        next_run = parser.get_next_run(cron, after=now)

        # Should be 9am on the same day
        assert next_run.hour == 9
        assert next_run.minute == 0


class TestScheduledMessageQueries:
    """Tests for querying scheduled messages."""

    def test_get_scheduled_messages_by_agent(self, db, autonomous_agent):
        """Test filtering scheduled messages by agent."""
        service = ScheduledMessagingService(db)

        # Create messages
        service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Message 1",
            schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="discord",
            recipient_id="G67890",
            template="Message 2",
            schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=2),
        )

        # Get messages for this agent
        messages = service.get_scheduled_messages(agent_id=autonomous_agent.id)

        assert len(messages) == 2
        assert all(msg.agent_id == autonomous_agent.id for msg in messages)

    def test_get_scheduled_messages_by_status(self, db, autonomous_agent):
        """Test filtering scheduled messages by status."""
        service = ScheduledMessagingService(db)

        # Create active message
        message1 = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="Active message",
            schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Pause it
        service.pause_scheduled_message(message1.id)

        # Get active messages only
        active_messages = service.get_scheduled_messages(status="active")
        paused_messages = service.get_scheduled_messages(status="paused")

        assert len(active_messages) == 0
        assert len(paused_messages) == 1

    def test_get_execution_history(self, db, autonomous_agent):
        """Test getting execution history."""
        service = ScheduledMessagingService(db)

        # Create message
        message = service.create_scheduled_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            template="History test",
            schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Get history
        history = service.get_execution_history(agent_id=autonomous_agent.id)

        # Should include the message even though it hasn't run yet
        assert len(history) >= 1
        assert any(h["id"] == message.id for h in history)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
