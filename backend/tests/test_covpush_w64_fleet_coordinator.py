"""
Coverage-push tests for core.fleet_orchestration.fleet_coordinator_service.

Target: >=95% statement coverage STANDALONE (this file alone).

Covers: batch recruitment, grouped parallel execution (success/failure/retry/
timeout), fault-tolerance retry, snapshots, pub/sub notifications, tracing
(graceful-degradation paths), decomposition pipeline (incl. lazy init),
metadata persistence, task-group conversion, and the factory function.

Lines 127 and 227 (`self.tracing_service = FleetTracingService(...)` bodies
under `if self.tracing_service is None:` nested inside `if self.tracing_service:`)
are unreachable dead code — documented, not testable.
"""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.fleet.fleet_task_types import FleetTaskType
from core.fleet_orchestration.task_decomposition_service import (
    SubTask,
    TaskDecomposition,
)


@pytest.fixture()
def db_session():
    """Per-test isolated SQLite engine (temp file)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.models_registration import Base

    _fd, _db_path = tempfile.mkstemp(suffix=".db")
    os.close(_fd)
    engine = create_engine(f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})
    _seen_idx = set()
    for _table in list(Base.metadata.tables.values()):
        for _idx in list(_table.indexes):
            if _idx.name in _seen_idx:
                _table.indexes.remove(_idx)
            else:
                _seen_idx.add(_idx.name)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.unlink(_db_path)
        except OSError:
            pass


def _subtask(sid, depends_on=None):
    return SubTask(
        id=sid,
        description=f"task {sid}",
        required_domain="analyst",
        estimated_tokens=1000,
        depends_on=depends_on or [],
        can_parallelize=False,
    )


def _decomposition(n=2):
    return TaskDecomposition(
        subtasks=[_subtask(f"task-{i}") for i in range(1, n + 1)],
        complexity_score=0.5,
        estimated_duration_seconds=60,
        suggested_fleet_size=3,
        decomposition_rationale="test",
    )


class FakeCoordinatorServices:
    def __init__(self):
        self.decomposition = Mock()
        self.dependency = Mock()
        self.complexity = Mock()
        self.tracing = Mock()
        self.blackboard = AsyncMock()


class TestFleetCoordinatorInit:
    def _make(self, db, services=None):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        if services is None:
            services = FakeCoordinatorServices()
        return FleetCoordinatorService(
            db=db,
            blackboard_service=services.blackboard,
            decomposition_service=services.decomposition,
            dependency_service=services.dependency,
            complexity_estimator=services.complexity,
            tracing_service=services.tracing,
        ), services

    def test_init_defaults(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        assert svc.db is db_session
        assert svc.blackboard_service is None
        assert svc.decomposition_service is None
        assert svc.dependency_service is None
        assert svc.complexity_estimator is None
        assert svc.tracing_service is None
        assert svc.fleet_service is not None
        assert svc.fault_tolerance is not None
        assert isinstance(svc._init_lock, asyncio.Lock)

    def test_init_with_all_services(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc, services = self._make(db_session)
        assert svc.blackboard_service is services.blackboard
        assert svc.decomposition_service is services.decomposition
        assert svc.dependency_service is services.dependency
        assert svc.complexity_estimator is services.complexity
        assert svc.tracing_service is services.tracing

    def test_factory(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            get_fleet_coordinator,
        )
        svc = get_fleet_coordinator(db_session)
        assert svc is not None
        assert svc.db is db_session

    def test_factory_with_services(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            get_fleet_coordinator,
        )
        services = FakeCoordinatorServices()
        svc = get_fleet_coordinator(
            db_session,
            blackboard_service=services.blackboard,
            decomposition_service=services.decomposition,
            dependency_service=services.dependency,
            complexity_estimator=services.complexity,
        )
        assert svc.blackboard_service is services.blackboard
        assert svc.complexity_estimator is services.complexity


class TestRecruitParallelBatch:
    @pytest.mark.asyncio
    async def test_recruit_parallel_batch_happy_path(self, db_session):
        from core.agent_fleet_service import AgentFleetService
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import ChainLink
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock())
        with patch.object(AgentFleetService, "recruit_member") as recruit:
            recruit.side_effect = [
                ChainLink(id="l1", chain_id="chain-1"),
                ChainLink(id="l2", chain_id="chain-1"),
            ]
            links = await svc.recruit_parallel_batch(
                "chain-1", "parent-1",
                [{"child_agent_id": "a", "task_description": "t1"},
                 {"child_agent_id": "b", "task_description": "t2",
                  "context_json": {"k": "v"}, "link_order": 5,
                  "optimization_metadata": {"cheap": True}}])
        assert len(links) == 2
        assert recruit.call_count == 2
        assert recruit.call_args_list[1].kwargs["link_order"] == 5
        assert recruit.call_args_list[1].kwargs["context_json"] == {"k": "v"}
        assert recruit.call_args_list[1].kwargs["optimization_metadata"] == {"cheap": True}
        assert recruit.call_args_list[0].kwargs["optimization_metadata"] is None
        assert recruit.call_args_list[0].kwargs["link_order"] == 0
        svc.blackboard_service.publish_update.assert_awaited_once()
        call_data = svc.blackboard_service.publish_update.await_args.args[1]
        assert call_data["type"] == "fleet_expanded"
        assert call_data["data"]["new_members"] == 2

    @pytest.mark.asyncio
    async def test_recruit_empty_list(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session, blackboard_service=AsyncMock())
        links = await svc.recruit_parallel_batch("chain-1", "parent-1", [])
        assert links == []

    @pytest.mark.asyncio
    async def test_recruit_tracing_span_lifecycle(self, db_session):
        from core.agent_fleet_service import AgentFleetService
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import ChainLink
        tracing = Mock()
        tracing.start_agent_span = Mock(return_value=Mock())
        tracing.finish_span = Mock()
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(),
            tracing_service=tracing)
        with patch.object(AgentFleetService, "recruit_member") as recruit:
            recruit.return_value = ChainLink(id="l1", chain_id="chain-1")
            links = await svc.recruit_parallel_batch(
                "chain-1", "parent-1", [{"child_agent_id": "a",
                                         "task_description": "t1"}])
        assert len(links) == 1
        tracing.start_agent_span.assert_called_once()
        tracing.finish_span.assert_called_once()
        finish_kwargs = tracing.finish_span.call_args.kwargs
        assert finish_kwargs["status"] == "completed"
        assert "Recruited 1" in finish_kwargs["result_summary"]

    @pytest.mark.asyncio
    async def test_recruit_tracing_start_error_swallowed(self, db_session):
        from core.agent_fleet_service import AgentFleetService
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import ChainLink
        tracing = Mock()
        tracing.start_agent_span = Mock(side_effect=RuntimeError("trace down"))
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(),
            tracing_service=tracing)
        with patch.object(AgentFleetService, "recruit_member") as recruit:
            recruit.return_value = ChainLink(id="l1", chain_id="chain-1")
            links = await svc.recruit_parallel_batch(
                "chain-1", "parent-1", [{"child_agent_id": "a",
                                         "task_description": "t1"}])
        assert len(links) == 1
        tracing.finish_span.assert_not_called()

    @pytest.mark.asyncio
    async def test_recruit_tracing_finish_error_swallowed(self, db_session):
        from core.agent_fleet_service import AgentFleetService
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import ChainLink
        tracing = Mock()
        tracing.start_agent_span = Mock(return_value=Mock())
        tracing.finish_span = Mock(side_effect=RuntimeError("finish down"))
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(),
            tracing_service=tracing)
        with patch.object(AgentFleetService, "recruit_member") as recruit:
            recruit.return_value = ChainLink(id="l1", chain_id="chain-1")
            links = await svc.recruit_parallel_batch(
                "chain-1", "parent-1", [{"child_agent_id": "a",
                                         "task_description": "t1"}])
        assert len(links) == 1


class TestExecuteParallelTask:
    @pytest.mark.asyncio
    async def test_execute_success(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session, blackboard_service=AsyncMock())
        result = await svc.execute_parallel_task(
            "chain-1",
            [[{"agent_id": "a1", "task": "t1"}, {"agent_id": "a2", "task": "t2"}]],
        )
        assert result.total_tasks == 2
        assert result.completed_count == 2
        assert result.failed_count == 0
        assert result.retried_count == 0
        assert result.group_count == 1
        assert result.success_rate == 100.0
        assert result.metadata["enable_fault_tolerance"] is True
        assert result.metadata["has_retries"] is False
        assert result.tasks[0].status.value == "completed"
        assert result.tasks[0].result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_task_types_slicing(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session, blackboard_service=AsyncMock())
        svc._execute_single_task = AsyncMock(return_value={"ok": True})
        result = await svc.execute_parallel_task(
            "chain-1",
            [[{"agent_id": "a1", "task": "t1"},
              {"agent_id": "a2", "task": "t2"},
              {"agent_id": "a3", "task": "t3"}]],
            task_types=[FleetTaskType.RESEARCH],
        )
        assert result.total_tasks == 3
        assert result.completed_count == 3

    @pytest.mark.asyncio
    async def test_execute_failure_with_retry(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import ChainLink
        svc = FleetCoordinatorService(db=db_session, blackboard_service=AsyncMock())
        svc._execute_single_task = AsyncMock(side_effect=RuntimeError("agent boom"))
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a1",
            task_description="t1", status="failed", link_order=0))
        db_session.commit()
        retry_link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="alt",
            task_description="t", status="pending", link_order=0)
        retry_link.id = "retry-1"
        svc.fault_tolerance = Mock()
        svc.fault_tolerance.retry_with_alternative_specialist = AsyncMock(
            return_value=retry_link)
        result = await svc.execute_parallel_task(
            "chain-1",
            [[{"agent_id": "a1", "task_description": "t1"}]],
            task_types=[FleetTaskType.RESEARCH],
        )
        assert result.failed_count == 1
        assert result.retried_count == 1
        assert result.metadata["has_retries"] is True
        assert result.tasks[0].error == "agent boom"
        assert result.tasks[0].retry_attempt.retry_link_id == "retry-1"
        assert result.tasks[0].retry_attempt.alternative_agent_id == "alt"
        assert result.tasks[0].retry_attempt.original_agent_id == "a1"
        assert "Fault tolerance retry" in result.tasks[0].retry_attempt.reason

    @pytest.mark.asyncio
    async def test_execute_failure_no_retry_attempt(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session, blackboard_service=AsyncMock())
        svc._execute_single_task = AsyncMock(side_effect=ValueError("boom"))
        svc.fault_tolerance = Mock()
        svc.fault_tolerance.retry_with_alternative_specialist = AsyncMock(
            return_value=None)
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.failed_count == 1
        assert result.retried_count == 0
        assert result.tasks[0].retry_attempt is None

    @pytest.mark.asyncio
    async def test_execute_failure_fault_tolerance_disabled(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session, blackboard_service=AsyncMock())
        svc._execute_single_task = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]],
            enable_fault_tolerance=False)
        assert result.failed_count == 1
        assert result.retried_count == 0
        assert result.tasks[0].retry_attempt is None
        assert result.metadata["enable_fault_tolerance"] is False

    @pytest.mark.asyncio
    async def test_execute_timeout_marks_group_failed(self, db_session):
        from core.fleet_orchestration import fleet_coordinator_service as fcs
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session, blackboard_service=AsyncMock())

        async def _slow(*a, **k):
            await asyncio.sleep(10)

        svc._execute_single_task = Mock(side_effect=_slow)
        with patch.object(fcs, "DEFAULT_TASK_TIMEOUT_SECONDS", 0.05):
            result = await svc.execute_parallel_task(
                "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.failed_count == 1
        assert result.completed_count == 0
        assert "Task group timeout" in result.tasks[0].error

    @pytest.mark.asyncio
    async def test_execute_tracing_full_lifecycle(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        services = FakeCoordinatorServices()
        services.tracing.start_fleet_trace = Mock(return_value=Mock())
        services.tracing.start_agent_span = Mock(return_value=Mock())
        services.tracing.finish_span = Mock()
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(),
            tracing_service=services.tracing)
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.completed_count == 1
        services.tracing.start_fleet_trace.assert_called_once()
        services.tracing.start_agent_span.assert_called_once()
        assert services.tracing.finish_span.call_count >= 2
        span_statuses = [c.kwargs.get("status") for c in services.tracing.finish_span.call_args_list]
        assert "completed" in span_statuses
        assert result.metadata["trace_context"] is not None

    @pytest.mark.asyncio
    async def test_execute_tracing_start_fleet_trace_error(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        tracing = Mock()
        tracing.start_fleet_trace = Mock(side_effect=RuntimeError("trace down"))
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(), tracing_service=tracing)
        svc._execute_single_task = AsyncMock(return_value={"ok": True})
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.completed_count == 1
        assert result.metadata["trace_context"] is None
        tracing.start_agent_span.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_tracing_agent_span_error(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        tracing = Mock()
        tracing.start_fleet_trace = Mock(return_value=Mock())
        tracing.start_agent_span = Mock(side_effect=RuntimeError("span down"))
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(), tracing_service=tracing)
        svc._execute_single_task = AsyncMock(return_value={"ok": True})
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.completed_count == 1

    @pytest.mark.asyncio
    async def test_execute_failure_finishes_span_and_deletes(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        tracing = Mock()
        tracing.start_fleet_trace = Mock(return_value=Mock())
        tracing.start_agent_span = Mock(return_value=Mock())
        tracing.finish_span = Mock()
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(), tracing_service=tracing)
        svc._execute_single_task = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.failed_count == 1
        fail_calls = [c for c in tracing.finish_span.call_args_list
                      if c.kwargs.get("status") == "failed"]
        assert len(fail_calls) == 1
        assert fail_calls[0].kwargs["error"] == "boom"

    @pytest.mark.asyncio
    async def test_execute_span_finish_error_on_failure(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        tracing = Mock()
        tracing.start_fleet_trace = Mock(return_value=Mock())
        tracing.start_agent_span = Mock(return_value=Mock())
        tracing.finish_span = Mock(side_effect=RuntimeError("finish down"))
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(), tracing_service=tracing)
        svc._execute_single_task = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.failed_count == 1
        assert result.tasks[0].error == "boom"

    @pytest.mark.asyncio
    async def test_execute_span_finish_error_on_success(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        tracing = Mock()
        tracing.start_fleet_trace = Mock(return_value=Mock())
        tracing.start_agent_span = Mock(return_value=Mock())
        tracing.finish_span = Mock(side_effect=RuntimeError("finish down"))
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(), tracing_service=tracing)
        svc._execute_single_task = AsyncMock(return_value={"ok": True})
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.completed_count == 1

    @pytest.mark.asyncio
    async def test_execute_empty_result_is_falsy(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session, blackboard_service=AsyncMock())
        svc._execute_single_task = AsyncMock(return_value={})
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.completed_count == 1

    @pytest.mark.asyncio
    async def test_execute_fleet_trace_finish_error(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )

        tracing = Mock()
        tracing.start_fleet_trace = Mock(return_value=Mock())
        tracing.start_agent_span = Mock(return_value=Mock())
        tracing.finish_span = Mock(side_effect=RuntimeError("finish down"))
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(), tracing_service=tracing)
        svc._execute_single_task = AsyncMock(return_value={"ok": True})
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.completed_count == 1

    @pytest.mark.asyncio
    async def test_execute_publishes_completion_event(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        blackboard = AsyncMock()
        svc = FleetCoordinatorService(db=db_session, blackboard_service=blackboard)
        svc._execute_single_task = AsyncMock(return_value={"ok": True})
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        events = [c.args[1] for c in blackboard.publish_update.await_args_list]
        types = [e["type"] for e in events]
        assert "group_progress" in types
        assert "execution_complete" in types
        complete = [e for e in events if e["type"] == "execution_complete"][0]
        assert complete["data"]["total_tasks"] == 1
        assert complete["data"]["success_rate"] == result.success_rate

    @pytest.mark.asyncio
    async def test_execute_no_blackboard(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        svc._execute_single_task = AsyncMock(return_value={"ok": True})
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.completed_count == 1


class TestExecuteSingleTask:
    @pytest.mark.asyncio
    async def test_execute_single_task_task_description_key(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        result = await svc._execute_single_task(
            "chain-1", {"agent_id": "a1", "task_description": "do the thing"})
        assert result["agent_id"] == "a1"
        assert result["task"] == "do the thing"
        assert result["status"] == "completed"
        assert result["result"] == "Executed: do the thing"

    @pytest.mark.asyncio
    async def test_execute_single_task_task_key_fallback(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        result = await svc._execute_single_task(
            "chain-1", {"agent_id": "a1", "task": "short"})
        assert result["task"] == "short"


class TestPublishGroupProgress:
    @pytest.mark.asyncio
    async def test_no_blackboard_returns_early(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        await svc._publish_group_progress("chain-1", 0, 1, 1, 0)

    @pytest.mark.asyncio
    async def test_publishes_update(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        blackboard = AsyncMock()
        svc = FleetCoordinatorService(db=db_session, blackboard_service=blackboard)
        await svc._publish_group_progress("chain-1", 0, 2, 1, 1)
        blackboard.publish_update.assert_awaited_once()
        update = blackboard.publish_update.await_args.args[1]
        assert update["type"] == "group_progress"
        assert update["group_index"] == 0
        assert update["total_groups"] == 2
        assert update["completed_count"] == 1
        assert update["failed_count"] == 1

    @pytest.mark.asyncio
    async def test_publish_error_swallowed(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        blackboard = AsyncMock()
        blackboard.publish_update = AsyncMock(side_effect=RuntimeError("down"))
        svc = FleetCoordinatorService(db=db_session, blackboard_service=blackboard)
        await svc._publish_group_progress("chain-1", 0, 1, 1, 0)


class TestGetFleetSnapshot:
    @pytest.mark.asyncio
    async def test_chain_missing(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        snapshot = await svc.get_fleet_snapshot("missing")
        assert snapshot.active_agents == []
        assert snapshot.pending_tasks == []
        assert snapshot.metadata["error"] == "Chain not found"

    @pytest.mark.asyncio
    async def test_chain_with_links_and_metadata(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import ChainLink, DelegationChain
        chain = DelegationChain(
            id="chain-1", tenant_id="default", root_agent_id="r",
            root_task="root task", status="active", total_links=3,
            metadata_json={"_version": 7})
        db_session.add(chain)
        db_session.add_all([
            ChainLink(id="l1", chain_id="chain-1", parent_agent_id="r",
                      child_agent_id="a1", task_description="pending task",
                      status="pending", link_order=0),
            ChainLink(id="l2", chain_id="chain-1", parent_agent_id="r",
                      child_agent_id="a2", task_description="processing task",
                      status="processing", link_order=1),
            ChainLink(id="l3", chain_id="chain-1", parent_agent_id="r",
                      child_agent_id="a3", task_description="done task",
                      status="completed", link_order=2),
            ChainLink(id="l4", chain_id="chain-1", parent_agent_id="r",
                      child_agent_id="a4", task_description="failed task",
                      status="failed", link_order=3),
        ])
        db_session.commit()
        svc = FleetCoordinatorService(db=db_session)
        snapshot = await svc.get_fleet_snapshot("chain-1")
        assert snapshot.active_agents == ["a1", "a2"]
        assert snapshot.blackboard_version == 7
        assert snapshot.pending_tasks == ["pending task", "processing task"]
        assert snapshot.completed_tasks == ["done task"]
        assert snapshot.failed_tasks == ["failed task"]
        assert snapshot.metadata["chain_status"] == "active"
        assert snapshot.metadata["root_agent_id"] == "r"
        assert snapshot.metadata["root_task"] == "root task"

    @pytest.mark.asyncio
    async def test_chain_without_metadata_json(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import DelegationChain
        db_session.add(DelegationChain(
            id="chain-2", tenant_id="default", root_agent_id="r",
            root_task="root task", status="active"))
        db_session.commit()
        svc = FleetCoordinatorService(db=db_session)
        snapshot = await svc.get_fleet_snapshot("chain-2")
        assert snapshot.blackboard_version == 0
        assert snapshot.active_agents == []


class TestNotifyFleetStateChange:
    @pytest.mark.asyncio
    async def test_no_blackboard(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        await svc.notify_fleet_state_change("chain-1", "fleet_expanded", {})

    @pytest.mark.asyncio
    async def test_invalid_event_type(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        blackboard = AsyncMock()
        svc = FleetCoordinatorService(db=db_session, blackboard_service=blackboard)
        await svc.notify_fleet_state_change("chain-1", "bogus_event", {})
        blackboard.publish_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_event_published(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        blackboard = AsyncMock()
        svc = FleetCoordinatorService(db=db_session, blackboard_service=blackboard)
        for event_type in ("agent_joined", "agent_completed", "agent_failed",
                           "fleet_expanded", "group_progress",
                           "execution_complete", "decomposition_complete"):
            await svc.notify_fleet_state_change("chain-1", event_type, {"k": "v"})
        assert blackboard.publish_update.await_count == 7
        event = blackboard.publish_update.await_args.args[1]
        assert event["chain_id"] == "chain-1"
        assert event["data"] == {"k": "v"}
        assert event["type"] == "decomposition_complete"

    @pytest.mark.asyncio
    async def test_publish_error_swallowed(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        blackboard = AsyncMock()
        blackboard.publish_update = AsyncMock(side_effect=RuntimeError("redis down"))
        svc = FleetCoordinatorService(db=db_session, blackboard_service=blackboard)
        await svc.notify_fleet_state_change("chain-1", "fleet_expanded", {})


class TestAttemptFaultToleranceRetry:
    @pytest.mark.asyncio
    async def test_missing_agent_id(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        assert await svc._attempt_fault_tolerance_retry(
            "chain-1", {}, FleetTaskType.RESEARCH, RuntimeError("x")) is None

    @pytest.mark.asyncio
    async def test_no_failed_link(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        assert await svc._attempt_fault_tolerance_retry(
            "chain-1", {"agent_id": "a", "task": "t"}, FleetTaskType.RESEARCH,
            RuntimeError("x")) is None

    @pytest.mark.asyncio
    async def test_retry_creates_link(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import ChainLink
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a",
            task_description="t", status="failed", link_order=0))
        db_session.commit()
        svc = FleetCoordinatorService(db=db_session)
        retry = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="alt",
            task_description="t", status="pending", link_order=0)
        svc.fault_tolerance = Mock()
        svc.fault_tolerance.retry_with_alternative_specialist = AsyncMock(
            return_value=retry)
        result = await svc._attempt_fault_tolerance_retry(
            "chain-1", {"agent_id": "a", "task_description": "t"},
            FleetTaskType.RESEARCH, RuntimeError("x"))
        assert result is retry
        svc.fault_tolerance.retry_with_alternative_specialist.assert_awaited_once()
        assert svc.fault_tolerance.retry_with_alternative_specialist.await_args.kwargs[
            "task_type"] is FleetTaskType.RESEARCH

    @pytest.mark.asyncio
    async def test_task_key_fallback_lookup(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import ChainLink
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a",
            task_description="via-task-key", status="failed", link_order=0))
        db_session.commit()
        svc = FleetCoordinatorService(db=db_session)
        svc.fault_tolerance = Mock()
        svc.fault_tolerance.retry_with_alternative_specialist = AsyncMock(
            return_value=None)
        assert await svc._attempt_fault_tolerance_retry(
            "chain-1", {"agent_id": "a", "task": "via-task-key"},
            None, RuntimeError("x")) is None


class TestDecomposeAndExecute:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_services(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import DelegationChain
        services = FakeCoordinatorServices()
        decomposition = _decomposition(2)
        services.decomposition.decompose_task = AsyncMock(return_value=decomposition)
        services.dependency.build_graph = Mock(return_value="graph")
        services.dependency.validate_cycles = Mock(return_value=[])
        services.dependency.detect_critical_path = Mock(return_value=(["task-1", "task-2"], 2000))
        services.dependency.get_execution_groups = Mock(return_value=[["task-1"], ["task-2"]])
        services.complexity.estimate_fleet_size = Mock(return_value=2)
        svc = FleetCoordinatorService(
            db=db_session,
            blackboard_service=AsyncMock(),
            decomposition_service=services.decomposition,
            dependency_service=services.dependency,
            complexity_estimator=services.complexity,
        )
        db_session.add(DelegationChain(
            id="chain-1", tenant_id="default", root_agent_id="r",
            root_task="complex task", status="active"))
        db_session.commit()
        result = await svc.decompose_and_execute(
            "chain-1", "complex task", tenant_plan="solo", context={"c": 1},
            max_subtasks=5)
        assert result["decomposition"] is decomposition
        assert result["critical_path"] == ["task-1", "task-2"]
        assert result["execution_groups"] == [["task-1"], ["task-2"]]
        assert result["execution_result"].total_tasks == 2
        assert result["metadata"]["critical_tokens"] == 2000
        services.decomposition.decompose_task.assert_awaited_once_with(
            task_description="complex task", context={"c": 1}, max_subtasks=5)
        chain = db_session.query(DelegationChain).filter(
            DelegationChain.id == "chain-1").first()
        dec = chain.metadata_json["decomposition"]
        assert dec["critical_tokens"] == 2000
        assert dec["estimated_fleet_size"] == 2
        assert dec["execution_groups"] == [["task-1"], ["task-2"]]
        assert "decomposed_at" in dec

    @pytest.mark.asyncio
    async def test_full_pipeline_lazy_init(self, db_session):
        from core.fleet_orchestration import fleet_coordinator_service as fcs
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import DelegationChain
        decomposition = _decomposition(1)
        fake_decomposition_svc = Mock()
        fake_decomposition_svc.decompose_task = AsyncMock(return_value=decomposition)
        fake_dependency_svc = Mock()
        fake_dependency_svc.build_graph = Mock(return_value="graph")
        fake_dependency_svc.validate_cycles = Mock(return_value=[])
        fake_dependency_svc.detect_critical_path = Mock(return_value=(["task-1"], 1000))
        fake_dependency_svc.get_execution_groups = Mock(return_value=[["task-1"]])
        fake_complexity_svc = Mock()
        fake_complexity_svc.estimate_fleet_size = Mock(return_value=1)

        db_session.add(DelegationChain(
            id="chain-lazy", tenant_id="default", root_agent_id="r",
            root_task="task", status="active"))
        db_session.commit()
        svc = FleetCoordinatorService(db=db_session, blackboard_service=AsyncMock())
        with patch("core.llm.byok_handler.BYOKHandler") as mock_byok, \
                patch.object(fcs, "TaskDecompositionService",
                             return_value=fake_decomposition_svc), \
                patch.object(fcs, "DependencyGraphService",
                             return_value=fake_dependency_svc), \
                patch.object(fcs, "ComplexityEstimator",
                             return_value=fake_complexity_svc):
            result = await svc.decompose_and_execute(
                "chain-lazy", "task", tenant_plan="team", context=None)
        mock_byok.assert_called_once()
        assert mock_byok.call_args.kwargs["db_session"] is db_session
        assert svc.decomposition_service is fake_decomposition_svc
        assert svc.dependency_service is fake_dependency_svc
        assert svc.complexity_estimator is fake_complexity_svc
        assert result["execution_result"].total_tasks == 1

    @pytest.mark.asyncio
    async def test_decomposition_timeout(self, db_session):
        from core.fleet_orchestration import fleet_coordinator_service as fcs
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        services = FakeCoordinatorServices()

        async def _slow(*a, **k):
            await asyncio.sleep(10)

        services.decomposition.decompose_task = Mock(side_effect=_slow)
        svc = FleetCoordinatorService(
            db=db_session,
            decomposition_service=services.decomposition,
            dependency_service=services.dependency,
            complexity_estimator=services.complexity,
        )
        with patch.object(fcs, "DEFAULT_DECOMPOSITION_TIMEOUT_SECONDS", 0.05):
            with pytest.raises(TimeoutError, match="Task decomposition timeout"):
                await svc.decompose_and_execute("chain-1", "task", context={})

    @pytest.mark.asyncio
    async def test_circular_dependencies(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        services = FakeCoordinatorServices()
        services.decomposition.decompose_task = AsyncMock(return_value=_decomposition(2))
        services.dependency.build_graph = Mock(return_value="graph")
        services.dependency.validate_cycles = Mock(side_effect=ValueError("cycle!"))
        svc = FleetCoordinatorService(
            db=db_session,
            decomposition_service=services.decomposition,
            dependency_service=services.dependency,
            complexity_estimator=services.complexity,
        )
        with pytest.raises(ValueError, match="cycle!"):
            await svc.decompose_and_execute("chain-1", "task", context={})

    @pytest.mark.asyncio
    async def test_chain_missing_metadata_warned(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        services = FakeCoordinatorServices()
        services.decomposition.decompose_task = AsyncMock(return_value=_decomposition(1))
        services.dependency.build_graph = Mock(return_value="graph")
        services.dependency.validate_cycles = Mock(return_value=[])
        services.dependency.detect_critical_path = Mock(return_value=(["task-1"], 1000))
        services.dependency.get_execution_groups = Mock(return_value=[["task-1"]])
        services.complexity.estimate_fleet_size = Mock(return_value=1)
        svc = FleetCoordinatorService(
            db=db_session,
            blackboard_service=AsyncMock(),
            decomposition_service=services.decomposition,
            dependency_service=services.dependency,
            complexity_estimator=services.complexity,
        )
        result = await svc.decompose_and_execute("chain-ghost", "task", context={})
        assert result["execution_result"].total_tasks == 1


class TestExecuteDecomposedTask:
    @pytest.mark.asyncio
    async def test_full_path(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        services = FakeCoordinatorServices()
        services.dependency.build_graph = Mock(return_value="graph")
        services.dependency.validate_cycles = Mock(return_value=[])
        services.dependency.get_execution_groups = Mock(return_value=[["task-1"], ["task-2"]])
        services.dependency.detect_critical_path = Mock(return_value=(["task-1", "task-2"], 2000))
        svc = FleetCoordinatorService(
            db=db_session,
            blackboard_service=AsyncMock(),
            dependency_service=services.dependency,
        )
        result = await svc.execute_decomposed_task("chain-1", _decomposition(2))
        assert result["execution_result"].total_tasks == 2
        assert result["critical_path"] == ["task-1", "task-2"]
        assert result["execution_groups"] == [["task-1"], ["task-2"]]

    @pytest.mark.asyncio
    async def test_circular_dependencies(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        services = FakeCoordinatorServices()
        services.dependency.build_graph = Mock(return_value="graph")
        services.dependency.validate_cycles = Mock(side_effect=ValueError("cycle!"))
        svc = FleetCoordinatorService(
            db=db_session, dependency_service=services.dependency)
        with pytest.raises(ValueError, match="cycle!"):
            await svc.execute_decomposed_task("chain-1", _decomposition(2))

    @pytest.mark.asyncio
    async def test_lazy_dependency_init(self, db_session):
        from core.fleet_orchestration import fleet_coordinator_service as fcs
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        fake_dependency_svc = Mock()
        fake_dependency_svc.build_graph = Mock(return_value="graph")
        fake_dependency_svc.validate_cycles = Mock(return_value=[])
        fake_dependency_svc.get_execution_groups = Mock(return_value=[["task-1"]])
        fake_dependency_svc.detect_critical_path = Mock(return_value=(["task-1"], 1000))
        svc = FleetCoordinatorService(
            db=db_session, blackboard_service=AsyncMock(),
            dependency_service=None)
        with patch.object(fcs, "DependencyGraphService",
                          return_value=fake_dependency_svc):
            result = await svc.execute_decomposed_task("chain-1", _decomposition(1))
        assert svc.dependency_service is fake_dependency_svc
        assert result["execution_result"].total_tasks == 1


class TestStoreDecompositionMetadata:
    @pytest.mark.asyncio
    async def test_chain_missing(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        await svc._store_decomposition_metadata(
            "missing", _decomposition(2), [["task-1"]], ["task-1"], 100, 2)

    @pytest.mark.asyncio
    async def test_stores_and_merges_metadata(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        from core.models import DelegationChain
        db_session.add(DelegationChain(
            id="chain-1", tenant_id="default", root_agent_id="r",
            root_task="root task", status="active",
            metadata_json={"pre_existing": "keep"}))
        db_session.commit()
        svc = FleetCoordinatorService(db=db_session)
        await svc._store_decomposition_metadata(
            "chain-1", _decomposition(2), [["task-1"], ["task-2"]],
            ["task-1", "task-2"], 2000, 3)
        chain = db_session.query(DelegationChain).filter(
            DelegationChain.id == "chain-1").first()
        assert chain.metadata_json["pre_existing"] == "keep"
        dec = chain.metadata_json["decomposition"]
        assert dec["subtask_count"] == 2
        assert dec["complexity_score"] == 0.5
        assert dec["suggested_fleet_size"] == 3
        assert dec["estimated_fleet_size"] == 3
        assert dec["execution_groups"] == [["task-1"], ["task-2"]]
        assert dec["critical_tokens"] == 2000
        assert dec["decomposition_rationale"] == "test"


class TestConvertToTaskGroups:
    def test_convert_happy_path(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        groups = svc._convert_to_task_groups(
            [_subtask("t1"), _subtask("t2")],
            [["t1"], ["t2"]])
        assert groups == [
            [{"agent_id": "t1", "task_description": "task t1"}],
            [{"agent_id": "t2", "task_description": "task t2"}],
        ]

    def test_convert_skips_missing_subtask(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import (
            FleetCoordinatorService,
        )
        svc = FleetCoordinatorService(db=db_session)
        groups = svc._convert_to_task_groups(
            [_subtask("t1")], [["t1"], ["ghost"]])
        assert groups == [
            [{"agent_id": "t1", "task_description": "task t1"}],
            [],
        ]
