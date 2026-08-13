"""Coverage wave 75 — core/scheduled_messaging_service.py (26% → 95%+).

Closes the full service surface: one-time/recurring creation (cron + natural
language), update/pause/resume/cancel lifecycle, query filters, due-message
execution (one-time completion, recurring next-run, end_date/max_runs caps,
send failure, exception fallback), template variable substitution, and
execution history. Fully mocked gateway (zero network), real in-memory SQLite.

This file also pins the wave-75 REAL bug (RED→GREEN): the module crashed on
every create with `AttributeError: type object 'ScheduledMessageStatus' has
no attribute 'ACTIVE'` because core/models.py carried a stub Base model in
place of the enum (plus a ScheduledMessage model whose columns drifted from
alembic 6463674076ea) — the 12 pre-existing failures in test_scheduled_
messaging.py were symptoms of that schema drift.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentRegistry, AgentStatus, ScheduledMessage, ScheduledMessageStatus
from core.scheduled_messaging_service import ScheduledMessagingService

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def agent(db):
    agent = AgentRegistry(
        name="Sched Agent",
        category="testing",
        module_path="test.sched",
        class_name="SchedAgent",
        description="Scheduled messaging test agent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def service(db):
    return ScheduledMessagingService(db)


class TestScheduledMessageStatusEnum:
    """Wave-75 bug regression: ScheduledMessageStatus must be a real enum."""

    def test_status_enum_values(self):
        assert ScheduledMessageStatus.ACTIVE.value == "active"
        assert ScheduledMessageStatus.PAUSED.value == "paused"
        assert ScheduledMessageStatus.COMPLETED.value == "completed"
        assert ScheduledMessageStatus.FAILED.value == "failed"
        assert ScheduledMessageStatus.CANCELLED.value == "cancelled"

    def test_status_is_enum_not_stub_table(self):
        import enum
        assert isinstance(ScheduledMessageStatus, type)
        assert issubclass(ScheduledMessageStatus, enum.Enum)


class TestCreateScheduledMessage:
    def test_create_one_time(self, db, agent, service):
        when = datetime.now(timezone.utc) + timedelta(hours=1)
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C123",
            template="Hello {{name}}", schedule_type="one_time",
            scheduled_for=when, template_variables={"name": "Rushi"},
        )
        assert msg.schedule_type == "one_time"
        assert msg.status == ScheduledMessageStatus.ACTIVE.value
        assert msg.next_run.replace(tzinfo=timezone.utc) == when
        assert msg.agent_name == agent.name
        assert msg.template_variables == {"name": "Rushi"}
        assert msg.run_count == 0
        assert msg.timezone == "UTC"

    def test_create_recurring_with_cron(self, db, agent, service):
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="discord", recipient_id="U9",
            template="Daily ping", schedule_type="recurring",
            cron_expression="0 9 * * *",
        )
        assert msg.schedule_type == "recurring"
        assert msg.cron_expression == "0 9 * * *"
        assert msg.next_run.hour == 9

    def test_create_recurring_natural_language(self, db, agent, service):
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C1",
            template="Hi", schedule_type="recurring",
            natural_language_schedule="every day at 9am",
        )
        assert msg.cron_expression == "0 9 * * *"
        assert msg.natural_language_schedule == "every day at 9am"

    def test_create_with_limits_and_end_date(self, db, agent, service):
        end = datetime.now(timezone.utc) + timedelta(days=30)
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C2",
            template="T", schedule_type="recurring", cron_expression="0 * * * *",
            max_runs=5, end_date=end, timezone_str="America/New_York",
            governance_metadata={"owner": "test"},
        )
        assert msg.max_runs == 5
        assert msg.end_date.replace(tzinfo=timezone.utc) == end
        assert msg.timezone == "America/New_York"
        assert msg.governance_metadata == {"owner": "test"}

    def test_create_agent_not_found(self, db, service):
        with pytest.raises(Exception) as ei:
            service.create_scheduled_message(
                agent_id="missing", platform="slack", recipient_id="C",
                template="T", schedule_type="one_time",
                scheduled_for=datetime.now(timezone.utc),
            )
        assert ei.value.status_code == 404

    def test_create_invalid_schedule_type(self, db, agent, service):
        with pytest.raises(Exception) as ei:
            service.create_scheduled_message(
                agent_id=agent.id, platform="slack", recipient_id="C",
                template="T", schedule_type="weekly",
            )
        assert ei.value.status_code == 400

    def test_create_one_time_missing_scheduled_for(self, db, agent, service):
        with pytest.raises(Exception) as ei:
            service.create_scheduled_message(
                agent_id=agent.id, platform="slack", recipient_id="C",
                template="T", schedule_type="one_time",
            )
        assert ei.value.status_code == 400

    def test_create_recurring_missing_cron(self, db, agent, service):
        with pytest.raises(Exception) as ei:
            service.create_scheduled_message(
                agent_id=agent.id, platform="slack", recipient_id="C",
                template="T", schedule_type="recurring",
            )
        assert ei.value.status_code == 400


class TestUpdateScheduledMessage:
    def test_update_all_fields(self, db, agent, service):
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C",
            template="Old", schedule_type="recurring", cron_expression="0 9 * * *",
        )
        end = datetime.now(timezone.utc) + timedelta(days=10)
        updated = service.update_scheduled_message(
            msg.id, template="New", max_runs=3, end_date=end,
            cron_expression="0 12 * * *",
        )
        assert updated.template == "New"
        assert updated.max_runs == 3
        assert updated.end_date.replace(tzinfo=timezone.utc) == end
        assert updated.cron_expression == "0 12 * * *"
        assert updated.next_run.hour == 12

    def test_update_with_natural_language(self, db, agent, service):
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C",
            template="T", schedule_type="recurring", cron_expression="0 9 * * *",
        )
        updated = service.update_scheduled_message(
            msg.id, natural_language_schedule="hourly"
        )
        assert updated.cron_expression == "0 * * * *"
        assert updated.natural_language_schedule == "hourly"

    def test_update_not_found(self, db, agent, service):
        with pytest.raises(Exception) as ei:
            service.update_scheduled_message("nope", template="X")
        assert ei.value.status_code == 404


class TestLifecycle:
    def test_pause(self, db, agent, service):
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C",
            template="T", schedule_type="recurring", cron_expression="0 9 * * *",
        )
        paused = service.pause_scheduled_message(msg.id)
        assert paused.status == ScheduledMessageStatus.PAUSED.value

    def test_pause_not_found(self, db, agent, service):
        with pytest.raises(Exception) as ei:
            service.pause_scheduled_message("missing")
        assert ei.value.status_code == 404

    def test_resume(self, db, agent, service):
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C",
            template="T", schedule_type="recurring", cron_expression="0 9 * * *",
        )
        service.pause_scheduled_message(msg.id)
        resumed = service.resume_scheduled_message(msg.id)
        assert resumed.status == ScheduledMessageStatus.ACTIVE.value

    def test_resume_not_found(self, db, agent, service):
        with pytest.raises(Exception) as ei:
            service.resume_scheduled_message("missing")
        assert ei.value.status_code == 404

    def test_cancel(self, db, agent, service):
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C",
            template="T", schedule_type="recurring", cron_expression="0 9 * * *",
        )
        cancelled = service.cancel_scheduled_message(msg.id)
        assert cancelled.status == ScheduledMessageStatus.CANCELLED.value

    def test_cancel_not_found(self, db, agent, service):
        with pytest.raises(Exception) as ei:
            service.cancel_scheduled_message("missing")
        assert ei.value.status_code == 404


class TestQueries:
    def test_get_scheduled_messages_filters(self, db, agent, service):
        service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C1",
            template="T1", schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        service.create_scheduled_message(
            agent_id=agent.id, platform="discord", recipient_id="C2",
            template="T2", schedule_type="recurring", cron_expression="0 9 * * *",
        )
        all_msgs = service.get_scheduled_messages()
        assert len(all_msgs) == 2
        by_agent = service.get_scheduled_messages(agent_id=agent.id)
        assert len(by_agent) == 2
        by_status = service.get_scheduled_messages(
            status=ScheduledMessageStatus.ACTIVE.value)
        assert len(by_status) == 2
        by_type = service.get_scheduled_messages(schedule_type="recurring")
        assert len(by_type) == 1
        by_platform = service.get_scheduled_messages(agent_id="other")
        assert len(by_platform) == 0

    def test_get_scheduled_message(self, db, agent, service):
        msg = service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C",
            template="T", schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert service.get_scheduled_message(msg.id).id == msg.id
        assert service.get_scheduled_message("missing") is None


class TestExecuteDueMessages:
    def _due(self, db, agent, service, **kwargs):
        defaults = dict(
            agent_id=agent.id, platform="slack", recipient_id="C",
            template="Due {{name}}", schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=5),
            template_variables={"name": "World"},
        )
        defaults.update(kwargs)
        return service.create_scheduled_message(**defaults)

    def test_one_time_success(self, db, agent, service):
        msg = self._due(db, agent, service)
        with patch("core.scheduled_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={
                "status": "success", "message_id": "m1"})
            counts = asyncio_run(service.execute_due_messages())
        assert counts["sent"] == 1
        assert counts["failed"] == 0
        db.refresh(msg)
        assert msg.status == ScheduledMessageStatus.COMPLETED.value
        assert msg.run_count == 1
        assert msg.last_run is not None

    def test_recurring_updates_next_run(self, db, agent, service):
        msg = self._due(db, agent, service, schedule_type="recurring",
                        cron_expression="* * * * *")
        msg.next_run = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        with patch("core.scheduled_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            counts = asyncio_run(service.execute_due_messages())
        assert counts["sent"] == 1
        db.refresh(msg)
        assert msg.status == ScheduledMessageStatus.ACTIVE.value
        assert msg.run_count == 1
        assert msg.next_run.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) - timedelta(days=1)

    def test_end_date_passed_completes(self, db, agent, service):
        msg = self._due(db, agent, service,
                        end_date=datetime.now(timezone.utc) - timedelta(days=1))
        with patch("core.scheduled_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            counts = asyncio_run(service.execute_due_messages())
        assert counts["completed"] == 1
        db.refresh(msg)
        assert msg.status == ScheduledMessageStatus.COMPLETED.value

    def test_max_runs_reached_completes(self, db, agent, service):
        msg = self._due(db, agent, service, max_runs=2)
        msg.run_count = 2
        db.commit()
        with patch("core.scheduled_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            counts = asyncio_run(service.execute_due_messages())
        assert counts["completed"] == 1
        db.refresh(msg)
        assert msg.status == ScheduledMessageStatus.COMPLETED.value

    def test_recurring_next_run_past_end_date_completes(self, db, agent, service):
        msg = self._due(db, agent, service, schedule_type="recurring",
                        cron_expression="0 9 * * *",
                        end_date=datetime.now(timezone.utc) + timedelta(hours=1))
        msg.next_run = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        with patch("core.scheduled_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            counts = asyncio_run(service.execute_due_messages())
        assert counts["completed"] == 1
        db.refresh(msg)
        assert msg.status == ScheduledMessageStatus.COMPLETED.value

    def test_send_failure_marks_failed(self, db, agent, service):
        msg = self._due(db, agent, service)
        with patch("core.scheduled_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={
                "status": "error", "error": "platform down"})
            counts = asyncio_run(service.execute_due_messages())
        assert counts["failed"] == 1
        db.refresh(msg)
        assert msg.status == ScheduledMessageStatus.FAILED.value

    def test_exception_marks_failed(self, db, agent, service):
        msg = self._due(db, agent, service)
        with patch("core.scheduled_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(side_effect=RuntimeError("boom"))
            counts = asyncio_run(service.execute_due_messages())
        assert counts["failed"] == 1
        db.refresh(msg)
        assert msg.status == ScheduledMessageStatus.FAILED.value

    def test_substitutes_template_variables_in_send(self, db, agent, service):
        msg = self._due(db, agent, service)
        with patch("core.scheduled_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            asyncio_run(service.execute_due_messages())
        args, _ = gw.execute_action.await_args
        assert args[2]["content"] == "Due World"
        assert args[2]["recipient_id"] == "C"


class TestTemplateSubstitution:
    def test_basic(self, service):
        out = service._substitute_template_variables(
            "Hi {{name}}", {"name": "Alice"})
        assert out == "Hi Alice"

    def test_builtins_plus_user_override(self, service):
        out = service._substitute_template_variables(
            "{{date}} {{time}} {{datetime}} {{iso_datetime}} {{name}}",
            {"name": "Bob", "date": "2026-01-01"})
        assert out.startswith("2026-01-01 ")
        assert "{{" not in out
        assert out.endswith(" Bob")


class TestExecutionHistory:
    def test_history_returns_runs_only(self, db, agent, service):
        msg = self._due(db, agent, service)
        with patch("core.scheduled_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            asyncio_run(service.execute_due_messages())
        history = service.get_execution_history(agent_id=agent.id)
        assert len(history) == 1
        assert history[0]["id"] == msg.id
        assert history[0]["run_count"] == 1
        assert history[0]["status"] == ScheduledMessageStatus.COMPLETED.value

    def test_history_skips_never_run(self, db, agent, service):
        service.create_scheduled_message(
            agent_id=agent.id, platform="slack", recipient_id="C",
            template="T", schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=5),
        )
        history = service.get_execution_history(agent_id=agent.id)
        assert history == []

    def _due(self, db, agent, service, **kwargs):
        defaults = dict(
            agent_id=agent.id, platform="slack", recipient_id="C",
            template="Due", schedule_type="one_time",
            scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        defaults.update(kwargs)
        return service.create_scheduled_message(**defaults)


def asyncio_run(coro):
    import asyncio
    try:
        return asyncio.get_event_loop().run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
