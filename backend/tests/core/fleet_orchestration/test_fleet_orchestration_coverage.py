"""
Coverage tests for fleet_orchestration module.

Aligned to the CURRENT service APIs (2026-08-08 refactor; originally written
against Apr-2026 signatures — 41 failures on HEAD, see TESTED_FILES_TRACKER).

Target files:
- fleet_execution_models.py (models)
- fleet_coordinator_service.py (coordination)
- distributed_blackboard_service.py (state sync)
- task_decomposition_service.py (task splitting)
- dependency_graph_service.py (DAG operations)
- fault_tolerance_service.py (error handling)
- complexity_estimator.py (estimation)
- performance_metrics_service.py (metrics)
- scaling_proposal_service.py (scaling)
- fleet_scaler_service.py (scaling execution)
- overage_service.py (overage handling)
- predictive_scaling_service.py (prediction)
- fleet_progress_service.py (progress tracking)
- fleet_tracing_service.py (tracing)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

pytestmark = pytest.mark.usefixtures("db_session")


class TestFleetExecutionModels:
    """Test fleet execution model classes"""

    def test_fleet_execution_config_creation(self):
        """Test FleetExecutionConfig model creation"""
        from core.fleet_orchestration.fleet_execution_models import FleetExecutionConfig

        config = FleetExecutionConfig(
            parallel_mode=True,
            max_parallel_agents=5,
            conflict_resolution_strategy="optimistic_lock",
            sync_channel="fleet:test-123"
        )

        assert config.parallel_mode is True
        assert config.max_parallel_agents == 5
        assert config.conflict_resolution_strategy == "optimistic_lock"

    def test_fleet_execution_config_validation(self):
        """Test FleetExecutionConfig validation"""
        from core.fleet_orchestration.fleet_execution_models import FleetExecutionConfig

        with pytest.raises(ValueError):
            FleetExecutionConfig(conflict_resolution_strategy="invalid")

        with pytest.raises(ValueError):
            FleetExecutionConfig(max_parallel_agents=0)

    def test_blackboard_update_creation(self):
        """Test BlackboardUpdate model creation"""
        from core.fleet_orchestration.fleet_execution_models import BlackboardUpdate

        update = BlackboardUpdate(
            agent_id="agent-123",
            update_type="merge",
            data={"key": "value"},
            version=1
        )

        assert update.agent_id == "agent-123"
        assert update.update_type == "merge"
        assert update.data == {"key": "value"}
        assert update.version == 1

    def test_blackboard_update_validation(self):
        """Test BlackboardUpdate validation"""
        from core.fleet_orchestration.fleet_execution_models import BlackboardUpdate

        with pytest.raises(ValueError):
            BlackboardUpdate(
                agent_id="agent-123",
                update_type="invalid",
                data={},
                version=1
            )

    def test_fleet_state_snapshot_creation(self):
        """Test FleetStateSnapshot model creation"""
        from core.fleet_orchestration.fleet_execution_models import FleetStateSnapshot

        snapshot = FleetStateSnapshot(
            chain_id="chain-123",
            active_agents=["agent-1", "agent-2"],
            blackboard_version=5,
            pending_tasks=["task-1"],
            completed_tasks=["task-2", "task-3"]
        )

        assert snapshot.chain_id == "chain-123"
        assert len(snapshot.active_agents) == 2
        assert snapshot.blackboard_version == 5

    def test_fleet_state_snapshot_to_dict(self):
        """Test FleetStateSnapshot to_dict method"""
        from core.fleet_orchestration.fleet_execution_models import FleetStateSnapshot

        snapshot = FleetStateSnapshot(
            chain_id="chain-123",
            active_agents=["agent-1"]
        )

        result = snapshot.to_dict()
        assert isinstance(result, dict)
        assert "chain_id" in result
        assert result["chain_id"] == "chain-123"


class TestTaskDecompositionService:
    """Test task decomposition service"""

    def test_service_initialization(self, db_session):
        """Test TaskDecompositionService initialization"""
        from core.fleet_orchestration.task_decomposition_service import TaskDecompositionService

        service = TaskDecompositionService(db=db_session, llm_service=Mock())
        assert service is not None
        assert service.db is db_session

    async def test_decompose_task_falls_back_on_llm_error(self, db_session):
        """LLM failure degrades to rule-based fallback, never raises"""
        from core.fleet_orchestration.task_decomposition_service import TaskDecompositionService

        llm = Mock()
        llm.generate_structured_response = AsyncMock(side_effect=RuntimeError("LLM down"))
        service = TaskDecompositionService(db=db_session, llm_service=llm)

        result = await service.decompose_task(
            task_description="Analyze Q3 sales data across regions",
            context={}
        )

        assert result is not None
        assert result.subtasks
        assert 0 <= result.complexity_score <= 1
        assert result.suggested_fleet_size >= 1

    async def test_decompose_task_llm_success(self, db_session):
        """LLM-provided decomposition is returned as-is"""
        from core.fleet_orchestration.task_decomposition_service import (
            TaskDecompositionService, TaskDecomposition,
        )

        expected = TaskDecomposition(
            subtasks=[],
            complexity_score=0.5,
            estimated_duration_seconds=120,
            suggested_fleet_size=3,
            decomposition_rationale="mock"
        )
        llm = Mock()
        llm.generate_structured_response = AsyncMock(return_value=expected)
        service = TaskDecompositionService(db=db_session, llm_service=llm)

        result = await service.decompose_task(
            task_description="Process 100 documents",
            context={}
        )

        assert result is expected


class TestDependencyGraphService:
    """Test dependency graph service"""

    def test_build_graph_basic(self):
        """Test building a basic dependency graph"""
        from core.fleet_orchestration.dependency_graph_service import build_graph
        from core.fleet_orchestration.task_decomposition_service import SubTask
        import networkx as nx

        tasks = [
            SubTask(id="task1", description="a", required_domain="general",
                    estimated_tokens=100, can_parallelize=False),
            SubTask(id="task2", description="b", required_domain="general",
                    estimated_tokens=100, depends_on=["task1"], can_parallelize=False),
            SubTask(id="task3", description="c", required_domain="general",
                    estimated_tokens=100, depends_on=["task2"], can_parallelize=False),
        ]

        graph = build_graph(tasks)
        assert isinstance(graph, nx.DiGraph)
        assert graph.number_of_nodes() == 3

    def test_validate_cycles_no_cycles(self):
        """Test cycle detection with no cycles"""
        from core.fleet_orchestration.dependency_graph_service import validate_cycles
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_edge("task1", "task2")
        graph.add_edge("task2", "task3")

        cycles = validate_cycles(graph)
        assert cycles == []

    def test_validate_cycles_with_cycles(self):
        """Test cycle detection raises ValueError on cycles"""
        from core.fleet_orchestration.dependency_graph_service import validate_cycles
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_edge("task1", "task2")
        graph.add_edge("task2", "task3")
        graph.add_edge("task3", "task1")

        with pytest.raises(ValueError, match="Circular dependencies"):
            validate_cycles(graph)

    def test_get_execution_groups(self):
        """Test getting parallel execution groups"""
        from core.fleet_orchestration.dependency_graph_service import get_execution_groups
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_edge("task1", "task3")
        graph.add_edge("task2", "task3")

        groups = get_execution_groups(graph)
        assert groups is not None
        assert len(groups) > 0
        assert {"task1", "task2"} <= set(groups[0])

    def test_get_execution_groups_rejects_cycles(self):
        """Cycle-laden graphs are rejected before grouping"""
        from core.fleet_orchestration.dependency_graph_service import get_execution_groups
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_edge("task1", "task2")
        graph.add_edge("task2", "task1")

        with pytest.raises(ValueError):
            get_execution_groups(graph)

    def test_detect_critical_path(self):
        """Test critical path detection"""
        from core.fleet_orchestration.dependency_graph_service import detect_critical_path
        from core.fleet_orchestration.task_decomposition_service import SubTask
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_edge("task1", "task2")
        graph.add_edge("task2", "task3")

        tasks = [
            SubTask(id="task1", description="a", required_domain="general",
                    estimated_tokens=100, can_parallelize=False),
            SubTask(id="task2", description="b", required_domain="general",
                    estimated_tokens=200, can_parallelize=False),
            SubTask(id="task3", description="c", required_domain="general",
                    estimated_tokens=300, can_parallelize=False),
        ]

        path, total_tokens = detect_critical_path(graph, tasks)
        assert path is not None
        assert path[0] == "task1"
        assert total_tokens == 600


class TestComplexityEstimator:
    """Test complexity estimator"""

    def test_fleet_size_limits_exists(self):
        """Test FLEET_SIZE_LIMITS constant exists"""
        from core.fleet_orchestration.complexity_estimator import FLEET_SIZE_LIMITS

        assert isinstance(FLEET_SIZE_LIMITS, dict)
        assert len(FLEET_SIZE_LIMITS) > 0

    def test_complexity_estimator_initialization(self, db_session):
        """Test ComplexityEstimator initialization"""
        from core.fleet_orchestration.complexity_estimator import ComplexityEstimator

        estimator = ComplexityEstimator(db=db_session)
        assert estimator is not None
        assert estimator.db is db_session

    def test_estimate_fleet_size_empty(self, db_session):
        """Empty decomposition degrades to minimum fleet size 1"""
        from core.fleet_orchestration.complexity_estimator import ComplexityEstimator
        from core.fleet_orchestration.task_decomposition_service import TaskDecomposition

        estimator = ComplexityEstimator(db=db_session)
        decomposition = TaskDecomposition(
            subtasks=[],
            complexity_score=0.1,
            estimated_duration_seconds=60,
            suggested_fleet_size=1,
            decomposition_rationale="empty"
        )

        assert estimator.estimate_fleet_size(decomposition, "basic") == 1

    def test_estimate_fleet_size_parallelizable(self, db_session):
        """Parallelizable subtasks scale fleet size recommendation"""
        from core.fleet_orchestration.complexity_estimator import (
            ComplexityEstimator, FLEET_SIZE_LIMITS,
        )
        from core.fleet_orchestration.task_decomposition_service import TaskDecomposition, SubTask

        estimator = ComplexityEstimator(db=db_session)
        decomposition = TaskDecomposition(
            subtasks=[
                SubTask(id="t1", description="a", required_domain="finance",
                        estimated_tokens=100, can_parallelize=True),
                SubTask(id="t2", description="b", required_domain="sales",
                        estimated_tokens=100, can_parallelize=True),
                SubTask(id="t3", description="c", required_domain="ops",
                        estimated_tokens=100, can_parallelize=True),
            ],
            complexity_score=0.8,
            estimated_duration_seconds=300,
            suggested_fleet_size=3,
            decomposition_rationale="test"
        )

        size = estimator.estimate_fleet_size(decomposition, "default")
        assert 1 <= size <= FLEET_SIZE_LIMITS["default"]

    def test_estimate_duration(self, db_session):
        """Duration estimation never falls below 60s floor"""
        from core.fleet_orchestration.complexity_estimator import ComplexityEstimator
        from core.fleet_orchestration.task_decomposition_service import TaskDecomposition, SubTask

        estimator = ComplexityEstimator(db=db_session)
        decomposition = TaskDecomposition(
            subtasks=[
                SubTask(id="t1", description="a", required_domain="finance",
                        estimated_tokens=1000, can_parallelize=True),
                SubTask(id="t2", description="b", required_domain="finance",
                        estimated_tokens=1000, depends_on=["t1"], can_parallelize=False),
            ],
            complexity_score=0.5,
            estimated_duration_seconds=300,
            suggested_fleet_size=2,
            decomposition_rationale="test"
        )

        duration = estimator.estimate_duration(decomposition, fleet_size=2)
        assert duration >= 60


class TestScalingProposalService:
    """Test scaling proposal service"""

    def test_scaling_proposal_enum_exists(self):
        """Test scaling proposal enums exist"""
        from core.fleet_orchestration.scaling_proposal_service import ScalingProposalType, ScalingProposalStatus

        assert ScalingProposalType is not None
        assert ScalingProposalStatus is not None

    def test_scaling_proposal_creation(self):
        """Test ScalingProposal creation"""
        from core.fleet_orchestration.scaling_proposal_service import ScalingProposal, ScalingProposalType

        proposal = ScalingProposal(
            chain_id="chain-123",
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=3,
            proposed_fleet_size=10,
            reason="High load detected",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        assert proposal.proposal_type == ScalingProposalType.EXPANSION
        assert proposal.proposed_fleet_size == 10

    def test_service_initialization(self, db_session):
        """Test ScalingProposalService initialization"""
        from core.fleet_orchestration.scaling_proposal_service import ScalingProposalService

        service = ScalingProposalService(db=db_session)
        assert service is not None
        assert service.db is db_session

    def test_get_scaling_proposal_service(self, db_session):
        """Test get_scaling_proposal_service function"""
        from core.fleet_orchestration.scaling_proposal_service import get_scaling_proposal_service

        service = get_scaling_proposal_service(db_session)
        assert service is not None


class TestFleetScalerService:
    """Test fleet scaler service"""

    def test_scaling_operation_status_enum_exists(self):
        """Test ScalingOperationStatus enum exists"""
        from core.fleet_orchestration.fleet_scaler_service import ScalingOperationStatus

        assert ScalingOperationStatus is not None

    def test_scaling_operation_creation(self):
        """Test ScalingOperation creation"""
        from core.fleet_orchestration.fleet_scaler_service import ScalingOperation, ScalingOperationStatus

        operation = ScalingOperation(
            id="op-1",
            chain_id="chain-123",
            proposal_id="prop-1",
            operation_type="expand",
            from_size=3,
            to_size=10,
            status=ScalingOperationStatus.PENDING,
            started_at=datetime.now(timezone.utc)
        )

        assert operation.chain_id == "chain-123"
        assert operation.to_size == 10
        assert operation.status == ScalingOperationStatus.PENDING
        assert "chain_id" in operation.to_dict()

    def test_service_initialization(self, db_session):
        """Test FleetScalerService initialization"""
        from core.fleet_orchestration.fleet_scaler_service import FleetScalerService

        service = FleetScalerService(db=db_session)
        assert service is not None
        assert service.db is db_session

    def test_get_fleet_scaler_service(self, db_session):
        """Test get_fleet_scaler_service function"""
        from core.fleet_orchestration.fleet_scaler_service import get_fleet_scaler_service

        service = get_fleet_scaler_service(db_session)
        assert service is not None


class TestFaultToleranceService:
    """Test fault tolerance service"""

    def test_service_initialization(self, db_session):
        """Test FaultToleranceService initialization"""
        from core.fleet_orchestration.fault_tolerance_service import FaultToleranceService

        service = FaultToleranceService(db=db_session)
        assert service is not None
        assert service.db is db_session

    def test_should_retry_stop_on_failure(self, db_session):
        """STOP_ON_FAILURE policy blocks retries"""
        from core.fleet_orchestration.fault_tolerance_service import FaultToleranceService
        from core.fleet.fleet_task_types import FailurePolicy

        service = FaultToleranceService(db=db_session)

        assert service.should_retry(None, FailurePolicy.STOP_ON_FAILURE) is False

    def test_should_retry_retry_then_stop(self, db_session):
        """RETRY_THEN_STOP policy allows retries"""
        from core.fleet_orchestration.fault_tolerance_service import FaultToleranceService
        from core.fleet.fleet_task_types import FailurePolicy

        service = FaultToleranceService(db=db_session)

        assert service.should_retry(None, FailurePolicy.RETRY_THEN_STOP) is True

    def test_should_retry_continue_on_failure(self, db_session):
        """CONTINUE_ON_FAILURE blocks retries (continue, don't retry)"""
        from core.fleet_orchestration.fault_tolerance_service import FaultToleranceService
        from core.fleet.fleet_task_types import FailurePolicy

        service = FaultToleranceService(db=db_session)

        assert service.should_retry(None, FailurePolicy.CONTINUE_ON_FAILURE) is False


class TestPerformanceMetricsService:
    """Test performance metrics service"""

    def test_performance_metrics_creation(self):
        """Test PerformanceMetrics creation"""
        from core.fleet_orchestration.performance_metrics_service import PerformanceMetrics

        metrics = PerformanceMetrics(
            chain_id="chain-123",
            success_rate=95.0,
            avg_latency_ms=100.5,
            throughput_per_minute=50.0,
            execution_count=10,
            window="5m"
        )

        assert metrics.chain_id == "chain-123"
        assert metrics.success_rate == 95.0

    def test_performance_alert_creation(self):
        """Test PerformanceAlert creation"""
        from core.fleet_orchestration.performance_metrics_service import PerformanceAlert

        alert = PerformanceAlert(
            chain_id="chain-123",
            alert_type="high_latency",
            current_value=500.0,
            threshold_value=250.0,
            severity="warning",
            message="Latency exceeded threshold"
        )

        assert alert.alert_type == "high_latency"
        assert alert.severity == "warning"

    def test_service_initialization(self, db_session):
        """Test PerformanceMetricsService initialization"""
        from core.fleet_orchestration.performance_metrics_service import PerformanceMetricsService

        service = PerformanceMetricsService(db=db_session)
        assert service is not None
        assert service.db is db_session

    def test_get_performance_metrics_service(self, db_session):
        """Test get_performance_metrics_service function"""
        from core.fleet_orchestration.performance_metrics_service import get_performance_metrics_service

        service = get_performance_metrics_service(db_session)
        assert service is not None


class TestOverageService:
    """Test overage service"""

    def test_get_effective_limit(self, db_session):
        """Effective limit falls back to plan base limit without overage"""
        from core.fleet_orchestration.overage_service import OverageService

        service = OverageService(db=db_session)

        limit = service.get_effective_limit("chain-123")
        assert isinstance(limit, int)
        assert limit >= 0

    def test_get_active_overage_none(self, db_session):
        """No overage rows -> None"""
        from core.fleet_orchestration.overage_service import OverageService

        service = OverageService(db=db_session)

        assert service.get_active_overage("chain-123") is None


class TestPredictiveScalingService:
    """Test predictive scaling service"""

    def test_service_initialization(self, db_session):
        """Test PredictiveScalingService initialization"""
        from core.fleet_orchestration.predictive_scaling_service import PredictiveScalingService

        service = PredictiveScalingService(db=db_session)
        assert service is not None

    def test_analyze_trend_insufficient_data(self, db_session):
        """No data -> honest unknown/error dict, never raise"""
        from core.fleet_orchestration.predictive_scaling_service import PredictiveScalingService

        service = PredictiveScalingService(db=db_session)

        result = service.analyze_trend(
            chain_id="chain-123",
            metric_type="success_rate"
        )

        assert isinstance(result, dict)
        assert "direction" in result or "error" in result

    def test_predict_threshold_breach_insufficient_data(self, db_session):
        """No data -> prediction reports no breach without raising"""
        from core.fleet_orchestration.predictive_scaling_service import PredictiveScalingService

        service = PredictiveScalingService(db=db_session)

        result = service.predict_threshold_breach(
            chain_id="chain-123",
            metric_type="success_rate",
            threshold=80.0
        )

        assert isinstance(result, dict)
        assert "will_breach" in result or "error" in result


class TestFleetProgressService:
    """Test fleet progress service"""

    def test_service_initialization(self, db_session):
        """Test FleetProgressService initialization"""
        from core.fleet_orchestration.fleet_progress_service import FleetProgressService

        service = FleetProgressService(db=db_session)
        assert service is not None
        assert service.db is db_session

    async def test_get_fleet_progress_no_redis(self, db_session):
        """Without Redis, progress degrades to an empty FleetProgress"""
        from core.fleet_orchestration.fleet_progress_service import FleetProgressService

        service = FleetProgressService(db=db_session)

        progress = await service.get_fleet_progress("chain-123")

        assert progress.chain_id == "chain-123"
        assert progress.active_count == 0


class TestFleetTracingService:
    """Test fleet tracing service"""

    def test_service_initialization(self, db_session):
        """Test FleetTracingService initialization"""
        from core.fleet_orchestration.fleet_tracing_service import FleetTracingService

        service = FleetTracingService(db=db_session)
        assert service is not None
        assert service.db is db_session

    def test_start_fleet_trace(self, db_session):
        """Trace creation yields a root context with trace/span ids"""
        from core.fleet_orchestration.fleet_tracing_service import FleetTracingService

        service = FleetTracingService(db=db_session)

        ctx = service.start_fleet_trace(
            chain_id="chain-123",
            root_task="Execute fleet operation"
        )

        assert ctx is not None
        assert ctx.trace_id
        assert ctx.span_id
        assert ctx.chain_id == "chain-123"
        assert ctx.parent_span_id is None


class TestFleetCoordinatorService:
    """Test fleet coordinator service"""

    def test_service_initialization(self, db_session):
        """Test FleetCoordinatorService initialization"""
        from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService

        service = FleetCoordinatorService(db=db_session)
        assert service is not None
        assert service.db is db_session

    def test_get_fleet_coordinator(self, db_session):
        """Test get_fleet_coordinator function"""
        from core.fleet_orchestration.fleet_coordinator_service import get_fleet_coordinator

        coordinator = get_fleet_coordinator(db_session)
        assert coordinator is not None

    async def test_get_fleet_snapshot_empty(self, db_session):
        """Empty fleet yields a valid snapshot with zero active agents"""
        from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService

        service = FleetCoordinatorService(db=db_session)

        snapshot = await service.get_fleet_snapshot("chain-123")

        assert snapshot.chain_id == "chain-123"
        assert snapshot.active_agents == []


class TestDistributedBlackboardService:
    """Test distributed blackboard service"""

    def test_fleet_state_notifier_initialization(self):
        """FleetStateNotifier requires a redis_url (ctor contract)"""
        from core.fleet_orchestration.distributed_blackboard_service import FleetStateNotifier

        notifier = FleetStateNotifier(redis_url="redis://localhost:6379/0")
        assert notifier is not None
        assert notifier.redis_url == "redis://localhost:6379/0"

    def test_get_fleet_state_notifier_no_redis(self):
        """Without Redis env, singleton returns None (fail-closed, never raises)"""
        from core.fleet_orchestration.distributed_blackboard_service import get_fleet_state_notifier

        with patch.dict("os.environ", {}, clear=False):
            import os
            for key in ("DRAGONFLY_URL", "UPSTASH_REDIS_URL", "REDIS_URL"):
                os.environ.pop(key, None)
            notifier = get_fleet_state_notifier()

        assert notifier is None

    async def test_publish_blackboard_update_redis_failure(self):
        """Redis publish failure is logged, never raised"""
        from core.fleet_orchestration.distributed_blackboard_service import FleetStateNotifier

        notifier = FleetStateNotifier(redis_url="redis://localhost:6379/0")
        notifier._redis_client = Mock()
        notifier._redis_client.publish = AsyncMock(side_effect=RuntimeError("redis down"))

        # Should not raise
        await notifier.publish_blackboard_update(
            chain_id="chain-123",
            updates={"key": "value"},
            agent_id="agent-1",
            version=1
        )


class TestAutoApprovalService:
    """Test auto approval service"""

    def test_service_initialization(self, db_session):
        """Test AutoApprovalService initialization"""
        from core.fleet_orchestration.auto_approval_service import AutoApprovalService

        service = AutoApprovalService(db=db_session)
        assert service is not None

    def test_create_auto_approval_rule(self, db_session):
        """Rule creation persists a ScalingAutoApproval row"""
        from core.fleet_orchestration.auto_approval_service import AutoApprovalService

        service = AutoApprovalService(db=db_session)

        rule = service.create_auto_approval_rule(
            rule_name="low-risk-expansion",
            created_by="user-1",
            max_agents=10,
            risk_threshold=0.3
        )

        assert rule is not None
        assert rule.max_agents == 10
        assert rule.risk_threshold == 0.3

    def test_get_active_rules_empty(self, db_session):
        """No rules -> empty list"""
        from core.fleet_orchestration.auto_approval_service import AutoApprovalService

        service = AutoApprovalService(db=db_session)

        assert service.get_active_rules() == []

    def test_evaluate_proposal_no_rules(self, db_session):
        """No matching rule -> (False, None, reason)"""
        from core.fleet_orchestration.auto_approval_service import AutoApprovalService
        from core.fleet_orchestration.scaling_proposal_service import ScalingProposal, ScalingProposalType

        service = AutoApprovalService(db=db_session)
        proposal = ScalingProposal(
            chain_id="chain-123",
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=3,
            proposed_fleet_size=8,
            reason="load",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        approved, rule, reason = service.evaluate_proposal(proposal)

        assert approved is False
        assert rule is None
        assert reason
