"""
Coverage-push + bug-hunt tests for core.fleet and core.fleet_orchestration.

TDD: each bug found here has a failing test first, then a minimal fix.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import os

from core.fleet.fleet_task_types import (
    FailurePolicy,
    FleetTaskType,
    DEFAULT_FAILURE_POLICIES,
)
from core.fleet_orchestration.fleet_execution_models import (
    BatchExecutionRequest,
    BlackboardUpdate,
    FleetExecutionConfig,
    FleetExecutionResult,
    FleetStateSnapshot,
    ParallelExecutionRequest,
    RetryAttempt,
    TaskExecutionResult,
    TaskStatus,
)
from core.fleet_orchestration.task_decomposition_service import (
    SubTask,
    TaskDecomposition,
    TaskDecompositionService,
)
from core.fleet_orchestration.dependency_graph_service import (
    DependencyGraphService,
    build_graph,
    validate_cycles,
    get_execution_groups,
    detect_critical_path,
)
from core.fleet_orchestration.complexity_estimator import ComplexityEstimator
from core.fleet_orchestration.fault_tolerance_service import FaultToleranceService
from core.fleet_orchestration.fleet_tracing_service import (
    FleetTracingService,
    TraceContext,
)
from core.fleet_orchestration.distributed_blackboard_service import (
    FleetStateNotifier,
    get_fleet_state_notifier,
)
from core.fleet_orchestration.fleet_progress_service import (
    AgentStatus as FleetAgentStatus,
    FleetProgressService,
)
from core.fleet_orchestration.performance_metrics_service import (
    PerformanceMetricsService,
)
from core.llm.fallback.circuit_breaker import CircuitBreakerState


@pytest.fixture()
def db_session():
    """Per-test isolated SQLite engine (temp file)."""
    import tempfile
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


class TestFleetTaskTypes:
    def test_default_policies(self):
        assert DEFAULT_FAILURE_POLICIES[FleetTaskType.DATA_PROCESSING] == FailurePolicy.CONTINUE_ON_FAILURE
        assert DEFAULT_FAILURE_POLICIES[FleetTaskType.RESEARCH] == FailurePolicy.CONTINUE_ON_FAILURE
        assert DEFAULT_FAILURE_POLICIES[FleetTaskType.TRANSACTIONAL] == FailurePolicy.STOP_ON_FAILURE
        assert DEFAULT_FAILURE_POLICIES[FleetTaskType.CREATIVE] == FailurePolicy.STOP_ON_FAILURE
        assert DEFAULT_FAILURE_POLICIES[FleetTaskType.ANALYSIS] == FailurePolicy.CONTINUE_ON_FAILURE

    def test_enum_values(self):
        assert FleetTaskType("data_processing") is FleetTaskType.DATA_PROCESSING
        assert FailurePolicy("retry_stop") is FailurePolicy.RETRY_THEN_STOP


class TestFleetExecutionModels:
    def test_fleet_config_valid(self):
        cfg = FleetExecutionConfig()
        assert cfg.parallel_mode is True
        assert cfg.max_parallel_agents == 10
        assert cfg.conflict_resolution_strategy == "optimistic_lock"

    def test_fleet_config_invalid_strategy(self):
        with pytest.raises(ValueError):
            FleetExecutionConfig(conflict_resolution_strategy="bogus")

    def test_fleet_config_invalid_parallel_agents(self):
        with pytest.raises(ValueError):
            FleetExecutionConfig(max_parallel_agents=0)

    def test_blackboard_update_valid_and_invalid(self):
        update = BlackboardUpdate(agent_id="a1", update_type="merge", data={}, version=1)
        assert update.version == 1
        with pytest.raises(ValueError):
            BlackboardUpdate(agent_id="a1", update_type="bogus", data={}, version=1)

    def test_snapshot_to_dict(self):
        snap = FleetStateSnapshot(chain_id="c1", active_agents=["a"], completed_tasks=["t"])
        d = snap.to_dict()
        assert d["chain_id"] == "c1"
        assert d["active_agents"] == ["a"]
        assert "timestamp" in d

    def test_parallel_execution_request(self):
        req = ParallelExecutionRequest(chain_id="c", task_groups=[[{"agent_id": "a"}]])
        assert req.config is not None
        with pytest.raises(ValueError):
            ParallelExecutionRequest(chain_id="c", task_groups=[])

    def test_retry_attempt_to_dict(self):
        r = RetryAttempt(retry_link_id="r", alternative_agent_id="b", original_agent_id="a", reason="x")
        d = r.to_dict()
        assert d["retry_link_id"] == "r"
        assert "timestamp" in d

    def test_task_result_to_dict(self):
        t = TaskExecutionResult(agent_id="a", task_description="d", status=TaskStatus.COMPLETED)
        d = t.to_dict()
        assert d["status"] == "completed"
        assert d["retry_attempt"] is None

    def test_execution_result_properties(self):
        res = FleetExecutionResult(
            chain_id="c",
            total_tasks=10,
            completed_count=7,
            failed_count=3,
            retried_count=1,
            tasks=[
                TaskExecutionResult(agent_id="a", task_description="t1", status=TaskStatus.COMPLETED),
                TaskExecutionResult(agent_id="b", task_description="t2", status=TaskStatus.FAILED),
                TaskExecutionResult(
                    agent_id="c", task_description="t3", status=TaskStatus.FAILED,
                    retry_attempt=RetryAttempt(
                        retry_link_id="r1", alternative_agent_id="x",
                        original_agent_id="c", reason="ft"),
                ),
            ],
        )
        assert res.success_rate == 70.0
        assert res.has_failures is True
        assert res.has_retries is True
        assert len(res.get_failed_tasks()) == 2
        assert len(res.get_retried_tasks()) == 1
        assert len(res.get_completed_tasks()) == 1
        d = res.to_dict()
        assert d["success_rate"] == 70.0
        assert d["has_failures"] is True
        assert d["has_retries"] is True
        assert len(d["tasks"]) == 3

    def test_execution_result_zero_tasks(self):
        res = FleetExecutionResult(chain_id="c", total_tasks=0, completed_count=0, failed_count=0, retried_count=0)
        assert res.success_rate == 0.0

    def test_batch_execution_request(self):
        req = BatchExecutionRequest(chain_id="c", task_groups=[[{"agent_id": "a"}]])
        assert req.enable_fault_tolerance is True
        with pytest.raises(ValueError):
            BatchExecutionRequest(chain_id="c", task_groups=[])


def _subtask(sid, domain="analyst", tokens=1000, depends_on=None, parallel=False):
    return SubTask(
        id=sid,
        description=f"task {sid}",
        required_domain=domain,
        estimated_tokens=tokens,
        depends_on=depends_on or [],
        can_parallelize=parallel,
    )


def _decomposition(n=3):
    return TaskDecomposition(
        subtasks=[_subtask(f"task-{i}") for i in range(1, n + 1)],
        complexity_score=0.5,
        estimated_duration_seconds=60,
        suggested_fleet_size=3,
        decomposition_rationale="test",
    )


class FakeLLM:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.last_prompt = None

    async def generate_structured_response(self, prompt, system_instruction=None, response_model=None, temperature=None):
        self.last_prompt = prompt
        if self.exc:
            raise self.exc
        return self.result


class TestTaskDecompositionService:
    def _svc(self, llm):
        return TaskDecompositionService(db=Mock(), llm_service=llm)

    @pytest.mark.asyncio
    async def test_decompose_success(self):
        llm = FakeLLM(result=_decomposition())
        svc = self._svc(llm)
        result = await svc.decompose_task("Do something", context={})
        assert len(result.subtasks) == 3
        assert "AVAILABLE SPECIALIST DOMAINS" in llm.last_prompt

    @pytest.mark.asyncio
    async def test_decompose_limits_subtasks(self):
        llm = FakeLLM(result=_decomposition(5))
        svc = self._svc(llm)
        result = await svc.decompose_task("task", context={}, max_subtasks=3)
        assert len(result.subtasks) == 3

    @pytest.mark.asyncio
    async def test_decompose_unknown_domain_defaults_to_analyst(self):
        llm = FakeLLM(result=_decomposition())
        llm.result.subtasks[0].required_domain = "bogus-domain"
        svc = self._svc(llm)
        result = await svc.decompose_task("task", context={})
        assert result.subtasks[0].required_domain == "analyst"

    @pytest.mark.asyncio
    async def test_decompose_removes_invalid_dependencies(self):
        llm = FakeLLM(result=_decomposition())
        llm.result.subtasks[0].depends_on = ["ghost-task"]
        svc = self._svc(llm)
        result = await svc.decompose_task("task", context={})
        assert result.subtasks[0].depends_on == []

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_llm_failure(self):
        llm = FakeLLM(exc=RuntimeError("llm down"))
        svc = self._svc(llm)
        result = await svc.decompose_task("Analyze the sales data", context={})
        assert result.decomposition_rationale == "Rule-based decomposition (LLM fallback)"
        assert len(result.subtasks) == 3

    @pytest.mark.asyncio
    async def test_fallback_research(self):
        llm = FakeLLM(exc=RuntimeError("down"))
        svc = self._svc(llm)
        result = await svc.decompose_task("Search for competitor pricing", context={})
        assert result.subtasks[0].required_domain == "research"

    @pytest.mark.asyncio
    async def test_fallback_correlation(self):
        llm = FakeLLM(exc=RuntimeError("down"))
        svc = self._svc(llm)
        result = await svc.decompose_task("correlate sales across multiple systems", context={})
        assert len(result.subtasks) == 4
        assert result.subtasks[0].can_parallelize is True

    @pytest.mark.asyncio
    async def test_fallback_generic(self):
        llm = FakeLLM(exc=RuntimeError("down"))
        svc = self._svc(llm)
        result = await svc.decompose_task("Greet the customer politely", context={}, max_subtasks=10)
        assert len(result.subtasks) == 1
        assert result.subtasks[0].required_domain == "executor"

    def test_build_domain_catalog(self):
        svc = self._svc(FakeLLM(result=None))
        catalog = svc._build_domain_catalog()
        assert "Finance: Available" in catalog
        assert len(catalog.splitlines()) == len(svc.AVAILABLE_DOMAINS)


class TestDependencyGraphService:
    def test_build_graph_empty(self):
        g = DependencyGraphService().build_graph([])
        assert g.number_of_nodes() == 0

    def test_build_graph_duplicate_ids(self):
        tasks = [_subtask("task-1"), _subtask("task-1")]
        with pytest.raises(ValueError):
            DependencyGraphService().build_graph(tasks)

    def test_build_graph_with_dependencies(self):
        tasks = [
            _subtask("task-1"),
            _subtask("task-2", depends_on=["task-1"]),
            _subtask("task-3", depends_on=["task-1", "task-2"]),
        ]
        g = DependencyGraphService().build_graph(tasks)
        assert set(g.nodes()) == {"task-1", "task-2", "task-3"}
        assert g.has_edge("task-1", "task-2")
        assert g.has_edge("task-2", "task-3")
        assert g.nodes["task-1"]["description"] == "task task-1"

    def test_build_graph_skips_missing_dependency(self):
        tasks = [_subtask("task-1", depends_on=["ghost"])]
        g = DependencyGraphService().build_graph(tasks)
        assert g.number_of_edges() == 0

    def test_validate_cycles_ok(self):
        tasks = [_subtask("task-1"), _subtask("task-2", depends_on=["task-1"])]
        g = DependencyGraphService().build_graph(tasks)
        assert DependencyGraphService().validate_cycles(g) == []

    def test_validate_cycles_empty(self):
        assert DependencyGraphService().validate_cycles(None) == []

    def test_validate_cycles_detects(self):
        tasks = [
            _subtask("task-1", depends_on=["task-2"]),
            _subtask("task-2", depends_on=["task-1"]),
        ]
        g = DependencyGraphService().build_graph(tasks)
        with pytest.raises(ValueError):
            DependencyGraphService().validate_cycles(g)

    def test_get_execution_groups(self):
        tasks = [
            _subtask("task-1"),
            _subtask("task-2", depends_on=["task-1"]),
            _subtask("task-3"),
            _subtask("task-4", depends_on=["task-2", "task-3"]),
        ]
        g = DependencyGraphService().build_graph(tasks)
        groups = DependencyGraphService().get_execution_groups(g)
        assert groups == [["task-1", "task-3"], ["task-2"], ["task-4"]]

    def test_get_execution_groups_empty(self):
        assert DependencyGraphService().get_execution_groups(None) == []

    def test_get_execution_groups_cyclic_raises(self):
        tasks = [
            _subtask("task-1", depends_on=["task-2"]),
            _subtask("task-2", depends_on=["task-1"]),
        ]
        g = DependencyGraphService().build_graph(tasks)
        with pytest.raises(ValueError):
            DependencyGraphService().get_execution_groups(g)

    def test_detect_critical_path(self):
        tasks = [
            _subtask("task-1", tokens=100),
            _subtask("task-2", tokens=400, depends_on=["task-1"]),
            _subtask("task-3", tokens=1000),
        ]
        g = DependencyGraphService().build_graph(tasks)
        path, tokens = DependencyGraphService().detect_critical_path(g, tasks)
        assert path[0] == "task-1"
        assert path[-1] == "task-2"
        assert tokens == 500

    def test_detect_critical_path_empty(self):
        assert DependencyGraphService().detect_critical_path(None, []) == ([], 0)

    def test_module_level_convenience_functions(self):
        tasks = [_subtask("task-1"), _subtask("task-2", depends_on=["task-1"])]
        g = build_graph(tasks)
        assert validate_cycles(g) == []
        assert get_execution_groups(g) == [["task-1"], ["task-2"]]
        path, tokens = detect_critical_path(g, tasks)
        assert path == ["task-1", "task-2"]


class TestComplexityEstimator:
    def test_estimate_fleet_size_empty(self, db_session):
        est = ComplexityEstimator(db_session)
        assert est.estimate_fleet_size(_decomposition(0), "solo") == 1

    def test_estimate_fleet_size_basic(self, db_session):
        est = ComplexityEstimator(db_session)
        size = est.estimate_fleet_size(_decomposition(4), "solo")
        assert 1 <= size <= 10

    def test_estimate_fleet_size_token_multiplier(self, db_session):
        est = ComplexityEstimator(db_session)
        subtasks = [
            _subtask("t1", tokens=60000),
            _subtask("t2", tokens=60000, parallel=True),
            _subtask("t3", tokens=60000, parallel=True),
        ]
        dec = TaskDecomposition(
            subtasks=subtasks, complexity_score=0.9,
            estimated_duration_seconds=100, suggested_fleet_size=3,
            decomposition_rationale="x")
        big = est.estimate_fleet_size(dec, "solo")
        subtasks[0].estimated_tokens = 2000
        small = est.estimate_fleet_size(dec, "solo")
        assert big >= small

    def test_estimate_fleet_size_caps_unknown_plan(self, db_session):
        est = ComplexityEstimator(db_session)
        size = est.estimate_fleet_size(_decomposition(50), "unknown-plan")
        assert size <= 10

    def test_estimate_fleet_size_historical_multiplier(self, db_session):
        est = ComplexityEstimator(db_session)
        with patch.object(est.analytics, "get_domain_performance_stats",
                          return_value={"success_rate": 0.5}) as mock_stats:
            est.estimate_fleet_size(_decomposition(3), "solo", tenant_id="tenant-1")
            mock_stats.assert_called_once()

    def test_estimate_fleet_size_historical_error(self, db_session):
        est = ComplexityEstimator(db_session)
        with patch.object(est.analytics, "get_domain_performance_stats",
                          side_effect=RuntimeError("analytics down")):
            size = est.estimate_fleet_size(_decomposition(3), "solo", tenant_id="tenant-1")
            assert 1 <= size <= 10

    def test_estimate_duration_empty(self, db_session):
        est = ComplexityEstimator(db_session)
        assert est.estimate_duration(_decomposition(0), 2) == 60

    def test_estimate_duration(self, db_session):
        est = ComplexityEstimator(db_session)
        dur = est.estimate_duration(_decomposition(3), 3)
        assert dur >= 60

    def test_estimate_duration_graph_error_falls_back(self, db_session):
        est = ComplexityEstimator(db_session)
        with patch.object(est.dependency_service, "build_graph", side_effect=RuntimeError("nx down")):
            dur = est.estimate_duration(_decomposition(3), 2)
            assert dur >= 60


class TestFaultToleranceService:
    def test_should_retry_policies(self):
        svc = FaultToleranceService(Mock())
        assert svc.should_retry(FleetTaskType.RESEARCH, FailurePolicy.RETRY_THEN_STOP) is True
        assert svc.should_retry(FleetTaskType.TRANSACTIONAL, FailurePolicy.STOP_ON_FAILURE) is False
        assert svc.should_retry(FleetTaskType.DATA_PROCESSING, None) is False
        assert svc.should_retry(None, None) is False

    @pytest.mark.asyncio
    async def test_find_alternative_original_missing(self, db_session):
        svc = FaultToleranceService(db_session)
        assert await svc.find_alternative_specialist("missing", "chain-1") is None

    @pytest.mark.asyncio
    async def test_find_alternative_no_candidates(self, db_session):
        from core.models import AgentRegistry
        db_session.add(AgentRegistry(
            id="agent-1", name="A", category="Finance", module_path="m", class_name="c"))
        db_session.commit()
        svc = FaultToleranceService(db_session)
        assert await svc.find_alternative_specialist("agent-1", "chain-1") is None

    @pytest.mark.asyncio
    async def test_find_alternative_excludes_original(self, db_session):
        from core.models import AgentRegistry
        db_session.add_all([
            AgentRegistry(id="agent-1", name="A", category="Finance", module_path="m", class_name="c", status="intern"),
            AgentRegistry(id="agent-2", name="B", category="Finance", module_path="m", class_name="c", status="intern"),
            AgentRegistry(id="agent-3", name="C", category="Finance", module_path="m", class_name="c", status="intern"),
        ])
        db_session.commit()
        svc = FaultToleranceService(db_session)
        alt = await svc.find_alternative_specialist("agent-1", "chain-1")
        assert alt is not None and alt.id != "agent-1"

    @pytest.mark.asyncio
    async def test_find_alternative_respects_exclusions(self, db_session):
        from core.models import AgentRegistry
        db_session.add_all([
            AgentRegistry(id="agent-1", name="A", category="Ops", module_path="m", class_name="c", status="supervised"),
            AgentRegistry(id="agent-2", name="B", category="Ops", module_path="m", class_name="c", status="supervised"),
        ])
        db_session.commit()
        svc = FaultToleranceService(db_session)
        assert await svc.find_alternative_specialist(
            "agent-1", "chain-1", exclude_agent_ids={"agent-1", "agent-2"}) is None

    @pytest.mark.asyncio
    async     def test_select_best_alternative_with_breakers(self):
        svc = FaultToleranceService(Mock())
        breaker_closed = Mock()
        breaker_closed.get_state = AsyncMock(return_value=CircuitBreakerState.CLOSED)
        breaker_closed.get_metrics = AsyncMock(return_value={"failure_count": 0})
        svc.circuit_breakers = {"agent-2": breaker_closed}
        agent1 = Mock(id="agent-1", name="A")
        agent2 = Mock(id="agent-2", name="B")
        agent3 = Mock(id="agent-3", name="C")
        best = await svc._select_best_alternative([agent1, agent2, agent3])
        assert best.id == "agent-2"

    @pytest.mark.asyncio
    async def test_retry_with_alternative_policy_blocks(self, db_session):
        from core.models import ChainLink
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a",
            task_description="t", status="failed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc = FaultToleranceService(db_session)
        assert await svc.retry_with_alternative_specialist(
            link, task_type=FleetTaskType.TRANSACTIONAL) is None

    @pytest.mark.asyncio
    async def test_retry_with_alternative_no_candidate(self, db_session):
        from core.models import ChainLink, AgentRegistry
        db_session.add_all([
            AgentRegistry(id="agent-1", name="A", category="Finance", module_path="m", class_name="c"),
        ])
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="agent-1",
            task_description="t", status="failed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc = FaultToleranceService(db_session)
        assert await svc.retry_with_alternative_specialist(
            link, task_type=FleetTaskType.RESEARCH,
            failure_policy_override=FailurePolicy.RETRY_THEN_STOP) is None

    @pytest.mark.asyncio
    async def test_retry_with_alternative_success(self, db_session):
        from core.models import ChainLink, AgentRegistry
        db_session.add_all([
            AgentRegistry(id="agent-1", name="A", category="Finance", module_path="m", class_name="c", status="intern"),
            AgentRegistry(id="agent-2", name="B", category="Finance", module_path="m", class_name="c", status="autonomous"),
        ])
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="agent-1",
            task_description="t", context_json={"note": "x"}, status="failed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc = FaultToleranceService(db_session)
        retry_link = await svc.retry_with_alternative_specialist(
            link, task_type=FleetTaskType.RESEARCH,
            failure_policy_override=FailurePolicy.RETRY_THEN_STOP)
        assert retry_link is not None
        assert retry_link.child_agent_id == "agent-2"
        assert retry_link.context_json["is_fault_tolerance_retry"] is True
        assert link.context_json["retried_with_link_id"] == retry_link.id
        from core.models import FleetHealingEvent
        events = db_session.query(FleetHealingEvent).all()
        assert len(events) == 1
        assert events[0].status == "in_progress"

    def test_get_tried_agent_ids_recursive(self, db_session):
        from core.models import ChainLink
        original = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="agent-1",
            task_description="t", status="failed", link_order=0)
        db_session.add(original)
        db_session.flush()
        retry = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="agent-2",
            task_description="t", context_json={"original_failed_link_id": original.id},
            status="failed", link_order=0)
        db_session.add(retry)
        db_session.commit()
        svc = FaultToleranceService(db_session)
        tried = svc._get_tried_agent_ids(retry)
        assert tried == {"agent-1", "agent-2"}

    def test_get_tried_agent_ids_missing_original(self, db_session):
        from core.models import ChainLink
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="agent-1",
            task_description="t", context_json={"original_failed_link_id": "nope"},
            status="failed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc = FaultToleranceService(db_session)
        assert svc._get_tried_agent_ids(link) == {"agent-1"}

    @pytest.mark.asyncio
    async def test_retry_with_alternative_circuit_breaker_open(self, db_session):
        from core.models import ChainLink, AgentRegistry
        db_session.add_all([
            AgentRegistry(id="agent-1", name="A", category="Finance", module_path="m", class_name="c", status="intern"),
            AgentRegistry(id="agent-2", name="B", category="Finance", module_path="m", class_name="c", status="autonomous"),
        ])
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="agent-1",
            task_description="t", status="failed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc = FaultToleranceService(db_session)
        breaker = Mock()
        breaker.get_state = AsyncMock(return_value=CircuitBreakerState.OPEN)
        svc.circuit_breakers = {"agent-1": breaker}
        retry_link = await svc.retry_with_alternative_specialist(
            link, task_type=FleetTaskType.RESEARCH,
            failure_policy_override=FailurePolicy.RETRY_THEN_STOP)
        assert retry_link is not None
        breaker.get_state.assert_awaited_once()

    def test_get_or_create_circuit_breaker(self):
        svc = FaultToleranceService(Mock())
        breaker = svc.get_or_create_circuit_breaker("agent-9")
        assert svc.get_or_create_circuit_breaker("agent-9") is breaker

    @pytest.mark.asyncio
    async def test_handle_failed_task_no_link(self, db_session):
        svc = FaultToleranceService(db_session)
        result = await svc.handle_failed_task("chain-1", "agent-1", "task")
        assert result == {"retried": False, "reason": "ChainLink not found"}

    @pytest.mark.asyncio
    async def test_handle_failed_task_policy_blocks(self, db_session):
        from core.models import ChainLink
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="agent-1",
            task_description="task", status="failed", link_order=0))
        db_session.commit()
        svc = FaultToleranceService(db_session)
        result = await svc.handle_failed_task(
            "chain-1", "agent-1", "task", task_type=FleetTaskType.TRANSACTIONAL)
        assert result["retried"] is False
        assert "policy" in result["reason"]

    @pytest.mark.asyncio
    async def test_handle_failed_task_retried(self, db_session):
        from core.models import ChainLink, AgentRegistry
        db_session.add_all([
            AgentRegistry(id="agent-1", name="A", category="Finance", module_path="m", class_name="c", status="intern"),
            AgentRegistry(id="agent-2", name="B", category="Finance", module_path="m", class_name="c", status="intern"),
        ])
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="agent-1",
            task_description="task", status="failed", link_order=0))
        db_session.commit()
        svc = FaultToleranceService(db_session)
        with patch.object(svc, "should_retry", return_value=True):
            result = await svc.handle_failed_task(
                "chain-1", "agent-1", "task", task_type=FleetTaskType.RESEARCH,
                error=RuntimeError("boom"))
        assert result["retried"] is True
        assert result["alternative_agent_id"] == "agent-2"

    @pytest.mark.asyncio
    async def test_handle_failed_task_no_alternative(self, db_session):
        from core.models import ChainLink, AgentRegistry
        db_session.add_all([
            AgentRegistry(id="agent-1", name="A", category="Finance", module_path="m", class_name="c"),
        ])
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="agent-1",
            task_description="task", status="failed", link_order=0))
        db_session.commit()
        svc = FaultToleranceService(db_session)
        with patch.object(svc, "should_retry", return_value=True):
            result = await svc.handle_failed_task(
                "chain-1", "agent-1", "task", task_type=FleetTaskType.RESEARCH)
        assert result["retried"] is False
        assert "No alternative" in result["reason"]


class TestFleetTracingService:
    def test_trace_context_tenant_truncation(self):
        ctx = TraceContext(trace_id="t", span_id="s", tenant_id="0123456789abcdef")
        assert len(ctx.tenant_id) == 8

    def test_trace_context_to_dict(self):
        ctx = TraceContext(trace_id="t", span_id="s", parent_span_id="p", chain_id="c", agent_id="a")
        d = ctx.to_dict()
        assert d["trace_id"] == "t"
        assert d["parent_span_id"] == "p"
        assert d["tenant_id"] is None

    def test_trace_context_child_span(self):
        ctx = TraceContext(trace_id="t", span_id="s", chain_id="c")
        child = ctx.create_child_span("agent-x")
        assert child.trace_id == "t"
        assert child.parent_span_id == "s"
        assert child.agent_id == "agent-x"
        assert child.span_id != "s"

    def test_start_fleet_trace(self):
        svc = FleetTracingService(Mock())
        ctx = svc.start_fleet_trace(chain_id="chain-1", root_task="do work")
        assert ctx.trace_id and ctx.span_id
        assert ctx.parent_span_id is None
        assert ctx.chain_id == "chain-1"

    def test_start_agent_span_with_parent(self):
        svc = FleetTracingService(Mock())
        parent = TraceContext(trace_id="t", span_id="s", chain_id="chain-1")
        ctx = svc.start_agent_span("chain-1", "agent-1", "task", parent_context=parent)
        assert ctx.parent_span_id == "s"
        assert ctx.trace_id == "t"
        assert ctx.agent_id == "agent-1"

    def test_start_agent_span_without_parent(self):
        svc = FleetTracingService(Mock())
        ctx = svc.start_agent_span("chain-1", "agent-1", "task")
        assert ctx.trace_id
        assert ctx.chain_id == "chain-1"

    def test_finish_span_completed(self):
        svc = FleetTracingService(Mock())
        ctx = TraceContext(trace_id="t", span_id="s", chain_id="c", agent_id="a")
        svc.finish_span(ctx, status="completed", result_summary="done")

    def test_finish_span_failed_with_error(self):
        svc = FleetTracingService(Mock())
        ctx = TraceContext(trace_id="t", span_id="s", chain_id="c", agent_id="a")
        svc.finish_span(ctx, status="failed", error="boom")

    def test_finish_span_cancelled(self):
        svc = FleetTracingService(Mock())
        ctx = TraceContext(trace_id="t", span_id="s", chain_id="c", agent_id="a")
        svc.finish_span(ctx, status="cancelled")

    def test_get_current_trace_context_none(self):
        from core.logging_context import _trace_id
        token = _trace_id.set(None)
        try:
            svc = FleetTracingService(Mock())
            assert svc.get_current_trace_context() is None
        finally:
            _trace_id.reset(token)

    def test_get_current_trace_context_active(self):
        from core.logging_context import _trace_id, _span_id, _parent_span_id
        t1 = _trace_id.set("trace-1")
        t2 = _span_id.set("span-1")
        t3 = _parent_span_id.set("parent-1")
        try:
            svc = FleetTracingService(Mock())
            ctx = svc.get_current_trace_context()
            assert ctx.trace_id == "trace-1"
            assert ctx.span_id == "span-1"
            assert ctx.parent_span_id == "parent-1"
        finally:
            _trace_id.reset(t1)
            _span_id.reset(t2)
            _parent_span_id.reset(t3)


class FakeRedisPipeline:
    def __init__(self, returns=None):
        self.ops = []
        self.returns = returns

    def __getattr__(self, name):
        def _op(*args, **kwargs):
            self.ops.append((name, args, kwargs))
            return self
        return _op

    async def execute(self):
        self.ops.append(("execute", (), {}))
        if self.returns is not None:
            return [self.returns.get(args[0]) if len(args) else None
                    for name, args, kwargs in self.ops]
        return self.ops


def _noop_msgs():
    async def _gen():
        yield {"type": "subscribe", "data": 1}
    return _gen()


class FakeRedisClient:
    def __init__(self, pipeline_returns=None):
        self.pipeline_returns = pipeline_returns
        self.published = []
        self.hash_data = {}
        self.close = AsyncMock()

    def pipeline(self):
        self.last_pipeline = FakeRedisPipeline(returns=self.pipeline_returns)
        return self.last_pipeline

    async def publish(self, channel, message):
        self.published.append((channel, message))

    async def hgetall(self, key):
        return self.hash_data.get(key, {})

    async def get(self, key):
        return None


class TestDistributedBlackboardService:
    @pytest.mark.asyncio
    async def test_publish_and_listener(self):
        client = FakeRedisClient()
        with patch("redis.asyncio.from_url", return_value=client):
            notifier = FleetStateNotifier("redis://x")
            await notifier.publish_blackboard_update("chain-1", {"a": 1}, "agent-1", 3)
            assert len(client.published) == 1

            async def _iter_msgs():
                yield {"type": "message", "data": '{"chain_id": "chain-1", "type": "blackboard_update"}'}

            pubsub = Mock()
            pubsub.subscribe = AsyncMock()
            pubsub.close = AsyncMock()
            pubsub.listen.return_value = _iter_msgs()
            client.pubsub = Mock(return_value=pubsub)
            seen = []
            listener = await notifier.subscribe_to_fleet("chain-1", lambda e: seen.append(e))
            await listener()
            assert len(seen) == 1
            assert seen[0]["chain_id"] == "chain-1"

    @pytest.mark.asyncio
    async def test_listener_timeout(self):
        client = FakeRedisClient()
        with patch("redis.asyncio.from_url", return_value=client):
            notifier = FleetStateNotifier("redis://x")
            pubsub = Mock()
            pubsub.subscribe = AsyncMock()
            pubsub.close = AsyncMock()
            pubsub.listen.return_value = _noop_msgs()
            client.pubsub = Mock(return_value=pubsub)
            listener = await notifier.subscribe_to_fleet("chain-1", lambda e: None, timeout_seconds=-1)
            await listener()
            pubsub.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_publish_error_swallowed(self):
        client = FakeRedisClient()
        client.publish = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch("redis.asyncio.from_url", return_value=client):
            notifier = FleetStateNotifier("redis://x")
            await notifier.publish_blackboard_update("chain-1", {}, "agent-1", 1)

    @pytest.mark.asyncio
    async def test_close(self):
        client = FakeRedisClient()
        notifier = FleetStateNotifier("redis://x")
        notifier._redis_client = client
        await notifier.close()
        client.close.assert_awaited()

    def test_get_fleet_state_notifier_no_redis(self):
        with patch.dict("os.environ", {}, clear=False):
            with patch("os.getenv", return_value=None):
                assert get_fleet_state_notifier() is None

    def test_get_fleet_state_notifier_with_redis(self):
        with patch("os.getenv", return_value="redis://localhost:6379"), \
             patch("redis.asyncio.from_url", return_value=FakeRedisClient()):
            from core.fleet_orchestration.distributed_blackboard_service import (
                _fleet_state_notifier_instance)
            _fleet_state_notifier_instance = None
            instance = get_fleet_state_notifier()
            assert instance is not None
            assert get_fleet_state_notifier() is instance
            _fleet_state_notifier_instance = None


class TestFleetProgressService:
    def _svc(self, client):
        svc = FleetProgressService(Mock())
        svc._redis_client = client
        return svc

    @pytest.mark.asyncio
    async def test_record_agent_start_no_redis(self):
        svc = FleetProgressService(Mock())
        await svc.record_agent_start("chain-1", "agent-1", "task", "trace-1")

    @pytest.mark.asyncio
    async def test_record_agent_start(self):
        client = FakeRedisClient()
        svc = self._svc(client)
        await svc.record_agent_start("chain-1", "agent-1", "task", "trace-1")
        assert any(name == "execute" for name, _, _ in client.last_pipeline.ops)
        assert len(client.published) == 1

    @pytest.mark.asyncio
    async def test_record_agent_complete(self):
        client = FakeRedisClient()
        svc = self._svc(client)
        await svc.record_agent_complete("chain-1", "agent-1", "summary", 42)
        assert len(client.published) == 1

    @pytest.mark.asyncio
    async def test_record_agent_failed(self):
        client = FakeRedisClient()
        svc = self._svc(client)
        await svc.record_agent_failed("chain-1", "agent-1", "error msg")
        assert len(client.published) == 1

    @pytest.mark.asyncio
    async def test_record_agent_failed_no_redis(self):
        svc = FleetProgressService(Mock())
        await svc.record_agent_failed("chain-1", "agent-1", "error msg")

    @pytest.mark.asyncio
    async def test_get_fleet_progress_no_redis(self):
        svc = FleetProgressService(Mock())
        progress = await svc.get_fleet_progress("chain-1")
        assert progress.chain_id == "chain-1"
        assert progress.active_agents == []

    @pytest.mark.asyncio
    async def test_get_fleet_progress_with_data(self):
        pipeline_returns = {
            "fleet:chain-1:active_agents": {b"agent-1"},
            "fleet:chain-1:counters:processing": b"1",
            "fleet:chain-1:counters:completed": b"2",
            "fleet:chain-1:counters:failed": b"0",
        }
        client = FakeRedisClient(pipeline_returns=pipeline_returns)
        client.hash_data = {
            "fleet:chain-1:agent:agent-1": {
                b"status": b"processing",
                b"task": b"do work",
                b"started_at": b"2026-01-01",
                b"trace_id": b"trace-1",
                b"result": b"",
                b"duration_ms": b"",
                b"error": b"",
            }
        }
        svc = self._svc(client)
        progress = await svc.get_fleet_progress("chain-1")
        assert progress.active_agents == ["agent-1"]
        assert progress.processing_count == 1
        assert progress.completed_count == 2
        assert progress.agent_details[0]["status"] == "processing"

    @pytest.mark.asyncio
    async def test_publish_progress_update(self):
        client = FakeRedisClient()
        svc = self._svc(client)
        await svc.publish_progress_update("chain-1", "agent-1", "completed", {"result": "ok"})
        assert client.published[0][0] == "fleet:progress:chain-1"

    @pytest.mark.asyncio
    async def test_close(self):
        client = FakeRedisClient()
        svc = self._svc(client)
        await svc.close()
        assert svc._redis_client is None


class TestPerformanceMetricsService:
    def _svc(self, client):
        svc = PerformanceMetricsService(Mock())
        svc._redis_client = client
        return svc

    def _result(self, total=5, completed=4, failed=1, ms=100):
        from core.fleet_orchestration.fleet_execution_models import FleetExecutionResult
        return FleetExecutionResult(
            chain_id="chain-1", total_tasks=total,
            completed_count=completed, failed_count=failed,
            retried_count=0, execution_time_ms=ms)

    @pytest.mark.asyncio
    async def test_record_execution_no_redis(self):
        svc = PerformanceMetricsService(Mock())
        await svc.record_execution("chain-1", self._result())

    @pytest.mark.asyncio
    async def test_record_execution_with_failures(self, db_session):
        client = FakeRedisClient()
        svc = self._svc(client)
        svc.db = db_session
        await svc.record_execution("chain-1", self._result(failed=1, completed=4))
        await asyncio.sleep(0.2)
        ops = client.last_pipeline.ops
        assert any(name == "execute" for name, _, _ in ops)
        assert any(name == "incrby" and args[0].endswith(":failure") for name, args, _ in ops)
        assert len(svc._bg_tasks) == 0

    @pytest.mark.asyncio
    async def test_record_execution_success_path(self, db_session):
        client = FakeRedisClient()
        svc = self._svc(client)
        svc.db = db_session
        await svc.record_execution("chain-1", self._result(failed=0, completed=5))
        await asyncio.sleep(0.2)
        ops = client.last_pipeline.ops
        assert any(name == "incrby" and args[0].endswith(":success") for name, args, _ in ops)

    @pytest.mark.asyncio
    async def test_record_execution_redis_error(self):
        client = FakeRedisClient()
        client.pipeline = Mock(side_effect=RuntimeError("pipe broken"))
        svc = self._svc(client)
        await svc.record_execution("chain-1", self._result())

    @pytest.mark.asyncio
    async def test_get_metrics_invalid_window(self):
        svc = PerformanceMetricsService(Mock())
        with pytest.raises(ValueError):
            await svc.get_metrics("chain-1", window="7d")

    @pytest.mark.asyncio
    async def test_get_metrics_no_redis(self):
        svc = PerformanceMetricsService(Mock())
        metrics = await svc.get_metrics("chain-1")
        assert metrics.success_rate == 0.0
        assert metrics.execution_count == 0

    @pytest.mark.asyncio
    async def test_get_metrics_with_data(self):
        pipeline_returns = {
            "fleet:chain-1:metrics:5m:success": b"8",
            "fleet:chain-1:metrics:5m:failure": b"2",
            "fleet:chain-1:metrics:5m:latency": b"1000.0",
            "fleet:chain-1:metrics:5m:count": b"10",
        }
        client = FakeRedisClient(pipeline_returns=pipeline_returns)
        svc = self._svc(client)
        metrics = await svc.get_metrics("chain-1", window="5m")
        assert metrics.success_rate == 80.0
        assert metrics.avg_latency_ms == 100.0
        assert metrics.throughput_per_minute == 2.0
        assert metrics.execution_count == 10

    @pytest.mark.asyncio
    async def test_get_metrics_error_fallback(self):
        client = FakeRedisClient()
        client.pipeline = Mock(side_effect=RuntimeError("boom"))
        svc = self._svc(client)
        metrics = await svc.get_metrics("chain-1", window="5m")
        assert metrics.execution_count == 0

    @pytest.mark.asyncio
    async def test_check_thresholds(self):
        returns = {}
        for window, suffix in [("1m", 60), ("5m", 300), ("1h", 3600)]:
            key = f"fleet:chain-1:metrics:{window}"
            returns[f"{key}:success"] = b"1"
            returns[f"{key}:failure"] = b"9"
            returns[f"{key}:latency"] = b"500000.0"
            returns[f"{key}:count"] = b"10"
        client = FakeRedisClient(pipeline_returns=returns)
        svc = self._svc(client)
        alerts = await svc.check_thresholds("chain-1")
        assert len(alerts) == 8
        assert all(a.alert_type in ("low_success_rate", "high_latency", "low_throughput") for a in alerts)

    @pytest.mark.asyncio
    async def test_check_thresholds_warning_levels(self):
        returns = {}
        for window in ["1m", "5m", "1h"]:
            key = f"fleet:chain-1:metrics:{window}"
            returns[f"{key}:success"] = b"9"
            returns[f"{key}:failure"] = b"1"
            returns[f"{key}:latency"] = b"30000.0"
            returns[f"{key}:count"] = b"10"
        client = FakeRedisClient(pipeline_returns=returns)
        svc = self._svc(client)
        alerts = await svc.check_thresholds("chain-1")
        assert any(a.severity == "warning" for a in alerts)

    @pytest.mark.asyncio
    async def test_close(self):
        client = FakeRedisClient()
        svc = self._svc(client)
        await svc.close()
        assert svc._redis_client is None


class TestSelfHealService:
    @pytest.mark.asyncio
    async def test_process_link_update_missing_link(self, db_session):
        from core.fleet.self_heal_service import SelfHealService
        svc = SelfHealService(db_session)
        await svc.process_link_update("no-such-link")

    @pytest.mark.asyncio
    async def test_process_link_update_failure_triggers_recovery(self, db_session):
        from core.fleet.self_heal_service import SelfHealService
        from core.models import ChainLink, AgentRegistry
        db_session.add_all([
            AgentRegistry(id="agent-p", name="P", category="Ops", module_path="m", class_name="c"),
            AgentRegistry(id="agent-c", name="C", category="Ops", module_path="m", class_name="c"),
        ])
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="agent-p", child_agent_id="agent-c",
            task_description="t", status="failed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc = SelfHealService(db_session)
        with patch.object(svc, "_trigger_recovery", new=AsyncMock()) as recover:
            await svc.process_link_update(link.id)
            recover.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_link_update_retry_succeeded(self, db_session):
        from core.fleet.self_heal_service import SelfHealService
        from core.models import ChainLink, FleetHealingEvent
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="c",
            task_description="t", status="completed", link_order=0,
            context_json={"is_self_heal_retry": True})
        db_session.add(link)
        db_session.flush()
        db_session.add(FleetHealingEvent(
            tenant_id="default", chain_id="chain-1", link_id="other",
            trigger_type="failed_link", recovery_action="retry_with_quality",
            status="in_progress", retry_link_id=link.id))
        db_session.commit()
        svc = SelfHealService(db_session)
        with patch.object(svc.optimization_service, "analyze_bottlenecks", return_value=[]):
            await svc.process_link_update(link.id)
        event = db_session.query(FleetHealingEvent).first()
        assert event.status == "succeeded"

    @pytest.mark.asyncio
    async def test_process_link_update_retry_failed(self, db_session):
        from core.fleet.self_heal_service import SelfHealService
        from core.models import ChainLink, FleetHealingEvent
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="c",
            task_description="t", status="failed", link_order=0,
            context_json={"is_self_heal_retry": True})
        db_session.add(link)
        db_session.flush()
        db_session.add(FleetHealingEvent(
            tenant_id="default", chain_id="chain-1", link_id="other",
            trigger_type="failed_link", recovery_action="retry_with_quality",
            status="in_progress", retry_link_id=link.id))
        db_session.commit()
        svc = SelfHealService(db_session)
        with patch.object(svc.optimization_service, "analyze_bottlenecks", return_value=[]):
            await svc.process_link_update(link.id)
        event = db_session.query(FleetHealingEvent).first()
        assert event.status == "failed"

    @pytest.mark.asyncio
    async def test_process_link_update_bottleneck(self, db_session):
        from core.fleet.self_heal_service import SelfHealService
        from core.models import ChainLink
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="c",
            task_description="t", status="completed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc = SelfHealService(db_session)
        with patch.object(svc.optimization_service, "analyze_bottlenecks",
                          return_value=[{"link_id": link.id, "severity": "critical", "domain": "latency"}]):
            with patch.object(svc, "_trigger_recovery", new=AsyncMock()) as recover:
                await svc.process_link_update(link.id)
                recover.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_link_update_no_bottleneck(self, db_session):
        from core.fleet.self_heal_service import SelfHealService
        from core.models import ChainLink
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="c",
            task_description="t", status="completed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc = SelfHealService(db_session)
        with patch.object(svc.optimization_service, "analyze_bottlenecks", return_value=[]):
            await svc.process_link_update(link.id)

    @pytest.mark.asyncio
    async def test_trigger_recovery_skips_existing_retry(self, db_session):
        from core.fleet.self_heal_service import SelfHealService
        from core.models import ChainLink
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="c",
            task_description="t", status="failed", link_order=0,
            context_json={"is_self_heal_retry": True})
        db_session.add(link)
        db_session.commit()
        svc = SelfHealService(db_session)
        await svc._trigger_recovery(link, reason="Execution Failure")
        assert db_session.query(ChainLink).count() == 1

    @pytest.mark.asyncio
    async def test_trigger_recovery_recruits_and_records_event(self, db_session):
        from core.fleet.self_heal_service import SelfHealService
        from core.models import ChainLink, AgentRegistry, FleetHealingEvent
        db_session.add_all([
            AgentRegistry(id="agent-p", name="P", category="Ops", module_path="m", class_name="c"),
            AgentRegistry(id="agent-c", name="C", category="Ops", module_path="m", class_name="c"),
        ])
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="agent-p", child_agent_id="agent-c",
            task_description="t", status="failed", link_order=0,
            context_json={"note": "orig"})
        db_session.add(link)
        db_session.commit()
        svc = SelfHealService(db_session)
        await svc._trigger_recovery(link, reason="Execution Failure")
        links = db_session.query(ChainLink).order_by(ChainLink.created_at).all()
        assert len(links) == 2
        assert links[1].context_json["is_self_heal_retry"] is True
        assert links[1].context_json["optimization"]["model"] == "quality"
        events = db_session.query(FleetHealingEvent).all()
        assert len(events) == 1
        assert events[0].status == "in_progress"
        assert events[0].trigger_type == "failed_link"

    @pytest.mark.asyncio
    async def test_trigger_recovery_bottleneck_trigger_type(self, db_session):
        from core.fleet.self_heal_service import SelfHealService
        from core.models import ChainLink, AgentRegistry
        db_session.add_all([
            AgentRegistry(id="agent-p", name="P", category="Ops", module_path="m", class_name="c"),
            AgentRegistry(id="agent-c", name="C", category="Ops", module_path="m", class_name="c"),
        ])
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="agent-p", child_agent_id="agent-c",
            task_description="t", status="completed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc = SelfHealService(db_session)
        await svc._trigger_recovery(link, reason="Critical Latency Bottleneck (latency)")
        from core.models import FleetHealingEvent
        event = db_session.query(FleetHealingEvent).first()
        assert event.trigger_type == "critical_bottleneck"


class FakeCoordinatorServices:
    def __init__(self, db):
        self.decomposition = Mock()
        self.dependency = Mock()
        self.complexity = Mock()
        self.tracing = Mock()
        self.blackboard = AsyncMock()


class TestFleetCoordinatorService:
    def _make(self, db, services=None):
        from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
        if services is None:
            services = FakeCoordinatorServices(db)
        return FleetCoordinatorService(
            db=db,
            blackboard_service=services.blackboard,
            decomposition_service=services.decomposition,
            dependency_service=services.dependency,
            complexity_estimator=services.complexity,
            tracing_service=services.tracing,
        ), services

    @pytest.mark.asyncio
    async def test_recruit_parallel_batch(self, db_session):
        from core.models import ChainLink
        from core.agent_fleet_service import AgentFleetService
        svc, services = self._make(db_session)
        with patch.object(AgentFleetService, "recruit_member") as recruit:
            recruit.side_effect = [
                ChainLink(id="l1", chain_id="chain-1"),
                ChainLink(id="l2", chain_id="chain-1"),
            ]
            links = await svc.recruit_parallel_batch(
                "chain-1", "parent-1",
                [{"child_agent_id": "a", "task_description": "t1"},
                 {"child_agent_id": "b", "task_description": "t2"}])
            assert len(links) == 2
            services.blackboard.publish_update.assert_awaited()
            assert recruit.call_count == 2
            assert recruit.call_args.kwargs["optimization_metadata"] is None

    @pytest.mark.asyncio
    async def test_recruit_parallel_batch_with_tracing(self, db_session):
        from core.agent_fleet_service import AgentFleetService
        svc, services = self._make(db_session)
        services.tracing.start_agent_span = Mock(return_value=Mock())
        services.tracing.finish_span = Mock()
        from core.models import ChainLink
        with patch.object(AgentFleetService, "recruit_member") as recruit:
            recruit.side_effect = [ChainLink(id="l1", chain_id="chain-1")]
            await svc.recruit_parallel_batch(
                "chain-1", "parent-1", [{"child_agent_id": "a", "task_description": "t1"}])
        services.tracing.start_agent_span.assert_called_once()
        services.tracing.finish_span.assert_called_once()

    @pytest.mark.asyncio
    async def test_recruit_parallel_batch_tracing_error_swallowed(self, db_session):
        from core.agent_fleet_service import AgentFleetService
        svc, services = self._make(db_session)
        from core.models import ChainLink
        services.tracing.start_agent_span = Mock(side_effect=RuntimeError("trace down"))
        with patch.object(AgentFleetService, "recruit_member") as recruit:
            recruit.side_effect = [ChainLink(id="l1", chain_id="chain-1")]
            links = await svc.recruit_parallel_batch(
                "chain-1", "parent-1", [{"child_agent_id": "a", "task_description": "t1"}])
            assert len(links) == 1

    @pytest.mark.asyncio
    async def test_execute_parallel_task_success(self, db_session):
        svc, services = self._make(db_session)
        result = await svc.execute_parallel_task(
            "chain-1",
            [[{"agent_id": "a1", "task": "t1"}, {"agent_id": "a2", "task": "t2"}]])
        assert result.total_tasks == 2
        assert result.completed_count == 2
        assert result.failed_count == 0
        assert result.group_count == 1
        assert result.success_rate == 100.0

    @pytest.mark.asyncio
    async def test_execute_parallel_task_failure_with_retry(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
        svc, services = self._make(db_session)
        svc._execute_single_task = AsyncMock(side_effect=RuntimeError("agent boom"))
        from core.models import ChainLink
        db_session.add(ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a1",
            task_description="t1", status="failed", link_order=0))
        db_session.commit()
        retry_link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="alt",
            task_description="t", status="pending", link_order=0)
        retry_link.id = "retry-1"
        svc.fault_tolerance = Mock()
        svc.fault_tolerance.retry_with_alternative_specialist = AsyncMock(return_value=retry_link)
        result = await svc.execute_parallel_task(
            "chain-1",
            [[{"agent_id": "a1", "task": "t1"}]],
            task_types=[FleetTaskType.RESEARCH])
        assert result.failed_count == 1
        assert result.retried_count == 1
        assert result.tasks[0].retry_attempt.retry_link_id == "retry-1"
        assert result.tasks[0].retry_attempt.alternative_agent_id == "alt"

    @pytest.mark.asyncio
    async def test_execute_parallel_task_timeout(self, db_session):
        from core.fleet_orchestration import fleet_coordinator_service as fcs
        svc, services = self._make(db_session)
        async def _slow(*a, **k):
            await asyncio.sleep(10)
        svc._execute_single_task = Mock(side_effect=_slow)
        with patch.object(fcs, "DEFAULT_TASK_TIMEOUT_SECONDS", 0.05):
            result = await svc.execute_parallel_task(
                "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.failed_count == 1
        assert result.completed_count == 0

    @pytest.mark.asyncio
    async def test_execute_parallel_task_with_tracing(self, db_session):
        svc, services = self._make(db_session)
        services.tracing.start_fleet_trace = Mock(return_value=Mock())
        services.tracing.start_agent_span = Mock(return_value=Mock())
        services.tracing.finish_span = Mock()
        result = await svc.execute_parallel_task(
            "chain-1", [[{"agent_id": "a1", "task": "t1"}]])
        assert result.completed_count == 1
        assert services.tracing.finish_span.call_count >= 2

    @pytest.mark.asyncio
    async def test_get_fleet_snapshot_chain_missing(self, db_session):
        svc, _ = self._make(db_session)
        snapshot = await svc.get_fleet_snapshot("missing")
        assert snapshot.active_agents == []
        assert snapshot.metadata["error"] == "Chain not found"

    @pytest.mark.asyncio
    async def test_get_fleet_snapshot_with_links(self, db_session):
        from core.models import DelegationChain, ChainLink
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
                      child_agent_id="a2", task_description="done task",
                      status="completed", link_order=1),
            ChainLink(id="l3", chain_id="chain-1", parent_agent_id="r",
                      child_agent_id="a3", task_description="failed task",
                      status="failed", link_order=2),
        ])
        db_session.commit()
        svc, _ = self._make(db_session)
        snapshot = await svc.get_fleet_snapshot("chain-1")
        assert snapshot.active_agents == ["a1"]
        assert snapshot.blackboard_version == 7
        assert snapshot.pending_tasks == ["pending task"]
        assert snapshot.completed_tasks == ["done task"]
        assert snapshot.failed_tasks == ["failed task"]

    @pytest.mark.asyncio
    async def test_notify_fleet_state_change_no_blackboard(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
        svc = FleetCoordinatorService(db=db_session)
        await svc.notify_fleet_state_change("chain-1", "fleet_expanded", {})

    @pytest.mark.asyncio
    async def test_notify_fleet_state_change_invalid_event(self, db_session):
        svc, services = self._make(db_session)
        await svc.notify_fleet_state_change("chain-1", "bogus_event", {})
        services.blackboard.publish_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_fleet_state_change_publish_error(self, db_session):
        svc, services = self._make(db_session)
        services.blackboard.publish_update = AsyncMock(side_effect=RuntimeError("redis down"))
        await svc.notify_fleet_state_change("chain-1", "fleet_expanded", {})

    @pytest.mark.asyncio
    async def test_attempt_fault_tolerance_retry_missing_agent(self, db_session):
        svc, _ = self._make(db_session)
        assert await svc._attempt_fault_tolerance_retry(
            "chain-1", {}, FleetTaskType.RESEARCH, RuntimeError("x")) is None

    @pytest.mark.asyncio
    async def test_attempt_fault_tolerance_retry_no_failed_link(self, db_session):
        svc, _ = self._make(db_session)
        assert await svc._attempt_fault_tolerance_retry(
            "chain-1", {"agent_id": "a", "task": "t"}, FleetTaskType.RESEARCH,
            RuntimeError("x")) is None

    @pytest.mark.asyncio
    async def test_attempt_fault_tolerance_retry_success(self, db_session):
        from core.models import ChainLink
        link = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="a",
            task_description="t", status="failed", link_order=0)
        db_session.add(link)
        db_session.commit()
        svc, _ = self._make(db_session)
        retry = ChainLink(
            chain_id="chain-1", parent_agent_id="p", child_agent_id="alt",
            task_description="t", status="pending", link_order=0)
        svc.fault_tolerance = Mock()
        svc.fault_tolerance.retry_with_alternative_specialist = AsyncMock(return_value=retry)
        result = await svc._attempt_fault_tolerance_retry(
            "chain-1", {"agent_id": "a", "task_description": "t"}, FleetTaskType.RESEARCH,
            RuntimeError("x"))
        assert result is retry

    @pytest.mark.asyncio
    async def test_decompose_and_execute(self, db_session):
        svc, services = self._make(db_session)
        tasks = [_subtask("task-1"), _subtask("task-2", depends_on=["task-1"])]
        decomposition = TaskDecomposition(
            subtasks=tasks, complexity_score=0.5,
            estimated_duration_seconds=60, suggested_fleet_size=2,
            decomposition_rationale="test")
        services.decomposition.decompose_task = AsyncMock(return_value=decomposition)
        services.dependency.build_graph = Mock(return_value="graph")
        services.dependency.validate_cycles = Mock(return_value=[])
        services.dependency.detect_critical_path = Mock(return_value=(["task-1", "task-2"], 2000))
        services.dependency.get_execution_groups = Mock(return_value=[["task-1"], ["task-2"]])
        services.complexity.estimate_fleet_size = Mock(return_value=2)
        from core.models import DelegationChain
        chain = DelegationChain(id="chain-1", tenant_id="default", root_agent_id="r", status="active")
        db_session.add(chain)
        db_session.commit()
        result = await svc.decompose_and_execute(
            "chain-1", "complex task", tenant_plan="solo", context={})
        assert result["critical_path"] == ["task-1", "task-2"]
        assert result["execution_result"].total_tasks == 2
        chain_after = db_session.query(DelegationChain).filter(
            DelegationChain.id == "chain-1").first()
        assert chain_after.metadata_json["decomposition"]["critical_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_decompose_and_execute_timeout(self, db_session):
        svc, services = self._make(db_session)
        from core.fleet_orchestration import fleet_coordinator_service as fcs
        async def _slow(*a, **k):
            await asyncio.sleep(10)
        services.decomposition.decompose_task = Mock(side_effect=_slow)
        with patch.object(fcs, "DEFAULT_DECOMPOSITION_TIMEOUT_SECONDS", 0.05):
            with pytest.raises(TimeoutError):
                await svc.decompose_and_execute("chain-1", "task", context={})

    @pytest.mark.asyncio
    async def test_decompose_and_execute_circular_deps(self, db_session):
        svc, services = self._make(db_session)
        services.decomposition.decompose_task = AsyncMock(return_value=_decomposition(2))
        services.dependency.build_graph = Mock(return_value="graph")
        services.dependency.validate_cycles = Mock(side_effect=ValueError("cycle!"))
        with pytest.raises(ValueError):
            await svc.decompose_and_execute("chain-1", "task", context={})

    @pytest.mark.asyncio
    async def test_execute_decomposed_task(self, db_session):
        svc, services = self._make(db_session)
        tasks = [_subtask("task-1"), _subtask("task-2", depends_on=["task-1"])]
        decomposition = TaskDecomposition(
            subtasks=tasks, complexity_score=0.5,
            estimated_duration_seconds=60, suggested_fleet_size=2,
            decomposition_rationale="test")
        services.dependency.build_graph = Mock(return_value="graph")
        services.dependency.validate_cycles = Mock(return_value=[])
        services.dependency.get_execution_groups = Mock(return_value=[["task-1"], ["task-2"]])
        services.dependency.detect_critical_path = Mock(return_value=(["task-1", "task-2"], 2000))
        result = await svc.execute_decomposed_task("chain-1", decomposition)
        assert result["execution_result"].total_tasks == 2
        assert result["critical_path"] == ["task-1", "task-2"]

    @pytest.mark.asyncio
    async def test_execute_decomposed_task_cycle(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
        svc = FleetCoordinatorService(db=db_session)
        svc.dependency_service = Mock()
        svc.dependency_service.build_graph = Mock(return_value="graph")
        svc.dependency_service.validate_cycles = Mock(side_effect=ValueError("cycle!"))
        with pytest.raises(ValueError):
            await svc.execute_decomposed_task("chain-1", _decomposition(2))

    @pytest.mark.asyncio
    async def test_store_decomposition_metadata_chain_missing(self, db_session):
        svc, _ = self._make(db_session)
        await svc._store_decomposition_metadata(
            "missing", _decomposition(2), [["task-1"]], ["task-1"], 100, 2)

    @pytest.mark.asyncio
    async def test_convert_to_task_groups_skips_missing(self, db_session):
        svc, _ = self._make(db_session)
        groups = svc._convert_to_task_groups(
            [_subtask("task-1")], [["task-1"], ["ghost"]])
        assert groups == [[{"agent_id": "task-1", "task_description": "task task-1"}], []]

    def test_get_fleet_coordinator_factory(self, db_session):
        from core.fleet_orchestration.fleet_coordinator_service import get_fleet_coordinator
        svc = get_fleet_coordinator(db_session)
        assert svc is not None
        assert svc.db is db_session

    @pytest.mark.asyncio
    async def test_publish_group_progress(self, db_session):
        svc, services = self._make(db_session)
        services.blackboard.publish_update = AsyncMock()
        await svc._publish_group_progress("chain-1", 0, 2, 1, 0)
        services.blackboard.publish_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_group_progress_error(self, db_session):
        svc, services = self._make(db_session)
        services.blackboard.publish_update = AsyncMock(side_effect=RuntimeError("down"))
        await svc._publish_group_progress("chain-1", 0, 2, 1, 0)
