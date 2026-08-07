"""
Comprehensive tests for AgentScheduler

Target: 60%+ coverage for core/scheduler.py (320 lines)
Focus: Job scheduling, execution, persistence, sync operations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import uuid

from core.scheduler import AgentScheduler
from core.models import AgentJob, AgentJobStatus, AgentRegistry, AgentStatus


# ========================================================================
# Fixtures
# ========================================================================


@pytest.fixture
def mock_agent(db_session):
    """Create a mock agent for testing."""
    agent = AgentRegistry(
        id="test-agent-123",
        tenant_id="test-tenant",
        name="Test Agent",
        category="Finance",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.9,
        schedule_config={
            "active": True,
            "cron_expression": "0 9 * * *"
        }
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def scheduler_instance():
    """Get AgentScheduler instance.

    add_job is patched so tests don't hit the real SQLAlchemyJobStore:
    the jobstore persists callables by textual reference + pickled args,
    so MagicMock callables raise at add_job time. The scheduler object
    itself (get_job/remove_job/running) stays real.
    """
    instance = AgentScheduler()
    with patch.object(instance.scheduler, 'add_job') as mock_add_job:
        mock_add_job.return_value = None
        yield instance


# ========================================================================
# TestScheduler: Scheduler Initialization and Configuration
# ========================================================================


class TestScheduler:
    """Test scheduler initialization and basic operations."""

    def test_singleton_pattern(self, scheduler_instance):
        """Test scheduler follows singleton pattern."""
        instance1 = AgentScheduler.get_instance()
        instance2 = AgentScheduler.get_instance()
        assert instance1 is instance2

    def test_scheduler_initialization(self, scheduler_instance):
        """Test scheduler initializes with BackgroundScheduler."""
        assert scheduler_instance.scheduler is not None
        assert scheduler_instance.scheduler is not None

    def test_get_instance_creates_singleton(self):
        """Test get_instance creates singleton on first call."""
        # Clear any existing instance
        AgentScheduler._instance = None

        instance = AgentScheduler.get_instance()
        assert instance is not None
        assert AgentScheduler._instance is not None

    def test_scheduler_started(self, scheduler_instance):
        """Test scheduler is started on initialization."""
        # APScheduler BackgroundScheduler should be running
        assert scheduler_instance.scheduler.running


# ========================================================================
# TestJobExecution: Job Scheduling and Execution
# ========================================================================


class TestJobExecution:
    """Test job scheduling, execution, and lifecycle."""

    def test_schedule_job_with_dict_cron(self, scheduler_instance):
        """Test scheduling job with dict cron expression."""
        mock_func = MagicMock()
        job_id = scheduler_instance.schedule_job(
            agent_id="agent-123",
            cron_expression={"minute": "*/5", "hour": "*"},
            func=mock_func
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    def test_schedule_job_with_string_cron(self, scheduler_instance):
        """Test scheduling job with string cron expression."""
        mock_func = MagicMock()
        job_id = scheduler_instance.schedule_job(
            agent_id="agent-123",
            cron_expression="*/5 * * * *",
            func=mock_func
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    def test_schedule_job_with_args(self, scheduler_instance):
        """Test scheduling job with function arguments."""
        mock_func = MagicMock()
        args = ("arg1", "arg2")
        job_id = scheduler_instance.schedule_job(
            agent_id="agent-123",
            cron_expression="0 9 * * *",
            func=mock_func,
            args=args
        )

        assert job_id is not None

    def test_execute_and_log_success(self, scheduler_instance):
        """Test successful job execution with logging."""
        async def mock_async_func():
            return {"result": "success"}

        with patch('core.scheduler.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            captured = {}

            def _add(record):
                captured['job'] = record

            mock_db.add.side_effect = _add
            mock_db.commit = MagicMock()
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            # Execute
            scheduler_instance._execute_and_log("agent-123", mock_async_func)

            # Verify the created job record was updated to success
            assert captured['job'].status == AgentJobStatus.SUCCESS.value

    def test_execute_and_log_failure(self, scheduler_instance):
        """Test job execution failure handling."""
        async def failing_func():
            raise Exception("Task failed")

        with patch('core.scheduler.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            captured = {}

            def _add(record):
                captured['job'] = record

            mock_db.add.side_effect = _add
            mock_db.commit = MagicMock()
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            # Execute
            scheduler_instance._execute_and_log("agent-123", failing_func)

            # Verify the created job record was updated to failed
            assert captured['job'].status == AgentJobStatus.FAILED.value
            assert captured['job'].logs is not None

    def test_execute_and_log_records_timing(self, scheduler_instance):
        """Test execution logs timing information."""
        async def mock_func():
            return {"result": "done"}

        with patch('core.scheduler.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            captured = {}

            def _add(record):
                captured['job'] = record

            mock_db.add.side_effect = _add
            mock_db.commit = MagicMock()
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            scheduler_instance._execute_and_log("agent-123", mock_func)

            # Verify end_time was set
            assert captured['job'].end_time is not None


# ========================================================================
# TestScheduleManagement: Agent Scheduling and Persistence
# ========================================================================


class TestScheduleManagement:
    """Test agent scheduling, persistence, and management."""

    def test_schedule_agent_with_config(self, scheduler_instance, mock_agent):
        """Test scheduling an agent with config."""
        schedule_config = {
            "active": True,
            "cron_expression": "0 9 * * *"
        }

        with patch('core.scheduler.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            job_id = scheduler_instance.schedule_agent(
                agent_id=mock_agent.id,
                schedule_config=schedule_config
            )

            assert job_id is not None

    def test_schedule_agent_no_cron_expression(self, scheduler_instance, mock_agent):
        """Test scheduling agent without cron expression returns None."""
        schedule_config = {
            "active": True
            # Missing cron_expression
        }

        result = scheduler_instance.schedule_agent(
            agent_id=mock_agent.id,
            schedule_config=schedule_config
        )

        assert result is None

    def test_load_scheduled_agents(self, scheduler_instance):
        """Test loading all scheduled agents from database."""
        mock_agents = [
            MagicMock(id="agent-1", schedule_config={"active": True, "cron_expression": "0 9 * * *"}),
            MagicMock(id="agent-2", schedule_config={"active": True, "cron_expression": "0 17 * * *"}),
            MagicMock(id="agent-3", schedule_config={"active": False}),  # Inactive
        ]

        with patch('core.scheduler.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = mock_agents
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            with patch.object(scheduler_instance, 'schedule_agent') as mock_schedule:
                scheduler_instance.load_scheduled_agents()

                # Should schedule 2 active agents
                assert mock_schedule.call_count == 2

    def test_load_scheduled_agents_empty_database(self, scheduler_instance):
        """Test loading scheduled agents from empty database."""
        with patch('core.scheduler.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = []
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            # Should not raise exception
            scheduler_instance.load_scheduled_agents()


# ========================================================================
# TestSyncOperations: Rating and Skill Sync Scheduling
# ========================================================================


class TestSyncOperations:
    """Test rating sync and skill sync scheduling."""

    def test_schedule_rating_sync(self, scheduler_instance):
        """Test scheduling rating sync job."""
        mock_sync_service = MagicMock()

        job_id = scheduler_instance.schedule_rating_sync(
            sync_service=mock_sync_service,
            interval_minutes=30
        )

        assert job_id == "rating-sync-atom-saas"

    def test_schedule_rating_sync_default_interval(self, scheduler_instance):
        """Test scheduling rating sync with default interval."""
        mock_sync_service = MagicMock()

        job_id = scheduler_instance.schedule_rating_sync(
            sync_service=mock_sync_service
        )

        assert job_id is not None

    def test_schedule_rating_sync_removes_existing(self, scheduler_instance):
        """Test that existing rating sync job is removed before adding new one."""
        mock_sync_service = MagicMock()

        with patch.object(scheduler_instance.scheduler, 'get_job') as mock_get_job:
            mock_get_job.return_value = MagicMock()  # Job exists

            with patch.object(scheduler_instance.scheduler, 'remove_job') as mock_remove:
                scheduler_instance.schedule_rating_sync(
                    sync_service=mock_sync_service,
                    interval_minutes=30
                )

                # Verify existing job was removed
                mock_remove.assert_called_once_with("rating-sync-atom-saas")

    def test_schedule_skill_sync(self, scheduler_instance):
        """Test scheduling skill sync job."""
        mock_sync_service = MagicMock()

        job_id = scheduler_instance.schedule_skill_sync(
            sync_service=mock_sync_service,
            interval_minutes=15
        )

        assert job_id == "skill-sync-atom-saas"

    def test_schedule_skill_sync_default_interval(self, scheduler_instance):
        """Test scheduling skill sync with default interval."""
        mock_sync_service = MagicMock()

        job_id = scheduler_instance.schedule_skill_sync(
            sync_service=mock_sync_service
        )

        assert job_id is not None

    def test_schedule_skill_sync_removes_existing(self, scheduler_instance):
        """Test that existing skill sync job is removed before adding new one."""
        mock_sync_service = MagicMock()

        with patch.object(scheduler_instance.scheduler, 'get_job') as mock_get_job:
            mock_get_job.return_value = MagicMock()

            with patch.object(scheduler_instance.scheduler, 'remove_job') as mock_remove:
                scheduler_instance.schedule_skill_sync(
                    sync_service=mock_sync_service,
                    interval_minutes=15
                )

                mock_remove.assert_called_once_with("skill-sync-atom-saas")


# ========================================================================
# TestSyncInitialization: Environment-Based Sync Initialization
# ========================================================================


class TestSyncInitialization:
    """Test sync initialization from environment variables."""

    @patch.dict('os.environ', {'ATOM_SAAS_SYNC_INTERVAL_MINUTES': '20'})
    def test_initialize_skill_sync_from_env(self, scheduler_instance):
        """Test initializing skill sync from environment variable."""
        with patch('core.sync_service.SyncService') as mock_sync_service_class:
            with patch('core.atom_saas_client.AtomSaaSClient') as mock_client_class:
                with patch('core.atom_saas_websocket.AtomSaaSWebSocketClient') as mock_ws_class:
                    with patch('core.scheduler.get_db_session') as mock_get_db:
                        mock_db = MagicMock()
                        mock_db.__enter__ = MagicMock(return_value=mock_db)
                        mock_db.__exit__ = MagicMock(return_value=False)
                        mock_get_db.return_value = mock_db

                        with patch.object(scheduler_instance, 'schedule_skill_sync') as mock_schedule:
                            scheduler_instance.initialize_skill_sync()

                            # Verify scheduled with interval from env
                            mock_schedule.assert_called_once()

    @patch.dict('os.environ', {}, clear=True)
    def test_initialize_skill_sync_default_interval(self, scheduler_instance):
        """Test initializing skill sync with default interval when env not set."""
        with patch('core.sync_service.SyncService') as mock_sync_service_class:
            with patch('core.atom_saas_client.AtomSaaSClient') as mock_client_class:
                with patch('core.atom_saas_websocket.AtomSaaSWebSocketClient') as mock_ws_class:
                    with patch('core.scheduler.get_db_session') as mock_get_db:
                        mock_db = MagicMock()
                        mock_db.__enter__ = MagicMock(return_value=mock_db)
                        mock_db.__exit__ = MagicMock(return_value=False)
                        mock_get_db.return_value = mock_db

                        with patch.object(scheduler_instance, 'schedule_skill_sync') as mock_schedule:
                            scheduler_instance.initialize_skill_sync()

                            # Verify scheduled with default 15 minute interval
                            mock_schedule.assert_called_once()

    @patch.dict('os.environ', {'ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES': '45'})
    def test_initialize_rating_sync_from_env(self, scheduler_instance):
        """Test initializing rating sync from environment variable."""
        with patch('core.rating_sync_service.RatingSyncService') as mock_rating_class:
            with patch('core.atom_saas_client.AtomSaaSClient') as mock_client_class:
                with patch('core.scheduler.get_db_session') as mock_get_db:
                    mock_db = MagicMock()
                    mock_db.__enter__ = MagicMock(return_value=mock_db)
                    mock_db.__exit__ = MagicMock(return_value=False)
                    mock_get_db.return_value = mock_db

                    with patch.object(scheduler_instance, 'schedule_rating_sync') as mock_schedule:
                        scheduler_instance.initialize_rating_sync()

                        # Verify scheduled with interval from env
                        mock_schedule.assert_called_once()

    @patch.dict('os.environ', {}, clear=True)
    def test_initialize_rating_sync_default_interval(self, scheduler_instance):
        """Test initializing rating sync with default interval when env not set."""
        with patch('core.rating_sync_service.RatingSyncService') as mock_rating_class:
            with patch('core.atom_saas_client.AtomSaaSClient') as mock_client_class:
                with patch('core.scheduler.get_db_session') as mock_get_db:
                    mock_db = MagicMock()
                    mock_db.__enter__ = MagicMock(return_value=mock_db)
                    mock_db.__exit__ = MagicMock(return_value=False)
                    mock_get_db.return_value = mock_db

                    with patch.object(scheduler_instance, 'schedule_rating_sync') as mock_schedule:
                        scheduler_instance.initialize_rating_sync()

                        # Verify scheduled with default 30 minute interval
                        mock_schedule.assert_called_once()


# ========================================================================
# TestSchedulerErrors: Error Handling and Edge Cases
# ========================================================================


class TestSchedulerErrors:
    """Test error handling and edge cases in scheduler."""

    def test_schedule_job_invalid_cron_format(self, scheduler_instance):
        """An invalid cron expression MUST be rejected, not silently scheduled.

        Previously an invalid cron (not 5 fields) left trigger_args={} and
        APScheduler created a job with an empty CronTrigger that defaults all
        fields to '*' — firing every second forever (runaway execution storm).
        """
        mock_func = MagicMock()

        # Invalid cron must NOT create a job — it should return None or raise.
        job_id = scheduler_instance.schedule_job(
            agent_id="agent-123",
            cron_expression="invalid",  # Invalid format
            func=mock_func
        )

        # The job must NOT have been scheduled (no runaway every-second trigger).
        assert job_id is None, (
            "Invalid cron expression was scheduled instead of rejected — this "
            "creates an empty CronTrigger that fires every second forever."
        )

    def test_schedule_job_too_few_cron_fields_rejected(self, scheduler_instance):
        """A cron with != 5 fields must be rejected (e.g. 4 fields)."""
        mock_func = MagicMock()
        job_id = scheduler_instance.schedule_job(
            agent_id="agent-456",
            cron_expression="0 9 * *",  # only 4 fields
            func=mock_func
        )
        assert job_id is None

    def test_execute_and_log_database_error(self, scheduler_instance):
        """Test handling database errors during job logging."""
        async def mock_func():
            return {"result": "success"}

        with patch('core.scheduler.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_db.add.side_effect = Exception("Database error")
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            # Should not raise exception
            try:
                scheduler_instance._execute_and_log("agent-123", mock_func)
            except Exception as e:
                # Expected to raise due to db.commit() in finally
                pass

    def test_schedule_agent_not_found_in_database(self, scheduler_instance):
        """Test scheduling an agent that doesn't exist in the database.

        Current behavior: schedule_agent does NOT look up the agent at
        schedule time — the lookup happens at fire time inside
        _run_scheduled_agent. Scheduling proceeds regardless.
        """
        schedule_config = {
            "active": True,
            "cron_expression": "0 9 * * *"
        }

        with patch('core.scheduler.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_get_db.return_value = mock_db

            job_id = scheduler_instance.schedule_agent(
                agent_id="nonexistent-agent",
                schedule_config=schedule_config
            )

            # Job is scheduled; the agent lookup is deferred to fire time
            assert job_id is not None

    def test_sync_wrapper_exception_handling(self, scheduler_instance):
        """Test sync wrapper handles exceptions gracefully."""
        mock_sync_service = MagicMock()
        mock_sync_service.sync_ratings = AsyncMock(side_effect=Exception("Sync failed"))

        # Schedule should not raise exception
        job_id = scheduler_instance.schedule_rating_sync(
            sync_service=mock_sync_service,
            interval_minutes=30
        )

        assert job_id is not None

    def test_cron_string_parser_edge_cases(self, scheduler_instance):
        """Test cron string parser with various formats."""
        mock_func = MagicMock()

        # Valid 5-part cron
        job_id1 = scheduler_instance.schedule_job(
            agent_id="agent-1",
            cron_expression="*/5 * * * *",
            func=mock_func
        )
        assert job_id1 is not None

        # Dict format
        job_id2 = scheduler_instance.schedule_job(
            agent_id="agent-2",
            cron_expression={"minute": "0", "hour": "9"},
            func=mock_func
        )
        assert job_id2 is not None
