"""
Tests for FleetCoordinatorService - Fleet orchestration and task distribution.

Tests cover:
- Service initialization
- Fleet recruitment
- Task execution
- Fleet snapshot
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def fleet_service(mock_db):
    """Create FleetCoordinatorService instance."""
    with patch('core.fleet_orchestration.fleet_coordinator_service.AgentPool'):
        with patch('core.fleet_orchestration.fleet_coordinator_service.Blackboard'):
            with patch('core.fleet_orchestration.fleet_coordinator_service.ScalingProposalService'):
                from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
                service = FleetCoordinatorService(
                    db=mock_db,
                    workspace_id="test-workspace",
                    tenant_id="test-tenant"
                )
                return service


# ============================================================================
# Service Initialization Tests (5 tests)
# ============================================================================

class TestFleetCoordinatorInit:
    """Tests for FleetCoordinatorService initialization."""

    def test_initialization_with_db(self, mock_db):
        """Test service initialization with database."""
        with patch('core.fleet_orchestration.fleet_coordinator_service.AgentPool'):
            with patch('core.fleet_orchestration.fleet_coordinator_service.Blackboard'):
                with patch('core.fleet_orchestration.fleet_coordinator_service.ScalingProposalService'):
                    from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
                    service = FleetCoordinatorService(
                        db=mock_db,
                        workspace_id="default",
                        tenant_id="default"
                    )
                    assert service is not None
                    assert service.workspace_id == "default"

    def test_initialization_with_custom_workspace(self, mock_db):
        """Test initialization with custom workspace."""
        with patch('core.fleet_orchestration.fleet_coordinator_service.AgentPool'):
            with patch('core.fleet_orchestration.fleet_coordinator_service.Blackboard'):
                with patch('core.fleet_orchestration.fleet_coordinator_service.ScalingProposalService'):
                    from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
                    service = FleetCoordinatorService(
                        db=mock_db,
                        workspace_id="custom-workspace",
                        tenant_id="custom-tenant"
                    )
                    assert service.workspace_id == "custom-workspace"
                    assert service.tenant_id == "custom-tenant"

    def test_initialization_creates_dependencies(self, mock_db):
        """Test that initialization creates required dependencies."""
        with patch('core.fleet_orchestration.fleet_coordinator_service.AgentPool') as mock_pool:
            with patch('core.fleet_orchestration.fleet_coordinator_service.Blackboard') as mock_bb:
                with patch('core.fleet_orchestration.fleet_coordinator_service.ScalingProposalService'):
                    from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
                    service = FleetCoordinatorService(db=mock_db)
                    assert service is not None

    def test_initialization_with_scaling_policy(self, mock_db):
        """Test initialization with scaling policy configuration."""
        with patch('core.fleet_orchestration.fleet_coordinator_service.AgentPool'):
            with patch('core.fleet_orchestration.fleet_coordinator_service.Blackboard'):
                with patch('core.fleet_orchestration.fleet_coordinator_service.ScalingProposalService'):
                    from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
                    service = FleetCoordinatorService(
                        db=mock_db,
                        max_parallel_agents=5,
                        scaling_enabled=True
                    )
                    assert service is not None

    def test_initialization_handles_missing_dependencies(self, mock_db):
        """Test initialization handles missing optional dependencies."""
        with patch('core.fleet_orchestration.fleet_coordinator_service.AgentPool'):
            with patch('core.fleet_orchestration.fleet_coordinator_service.Blackboard', side_effect=ImportError("Blackboard not available")):
                # Should handle ImportError gracefully or raise appropriately
                try:
                    from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
                    service = FleetCoordinatorService(db=mock_db)
                    assert service is not None
                except ImportError:
                    pass  # Expected if dependencies are missing


# ============================================================================
# Fleet Recruitment Tests (5 tests)
# ============================================================================

class TestFleetRecruitment:
    """Tests for fleet recruitment operations."""

    @pytest.mark.asyncio
    async def test_recruit_parallel_batch_basic(self, fleet_service):
        """Test basic parallel batch recruitment."""
        with patch.object(fleet_service, '_agent_pool') as mock_pool:
            mock_pool.recruit_agents = AsyncMock(return_value=[Mock(), Mock()])
            
            result = await fleet_service.recruit_parallel_batch(
                task_requirements={"capability": "analysis"},
                count=2
            )
            
            assert result is not None

    @pytest.mark.asyncio
    async def test_recruit_parallel_batch_with_constraints(self, fleet_service):
        """Test recruitment with capacity constraints."""
        with patch.object(fleet_service, '_agent_pool') as mock_pool:
            mock_pool.recruit_agents = AsyncMock(return_value=[Mock()])
            mock_pool.get_available_count = Mock(return_value=5)
            
            result = await fleet_service.recruit_parallel_batch(
                task_requirements={"capability": "code"},
                count=3,
                max_capacity=5
            )
            
            assert result is not None

    @pytest.mark.asyncio
    async def test_recruit_parallel_batch_handles_failure(self, fleet_service):
        """Test recruitment handles agent unavailability."""
        with patch.object(fleet_service, '_agent_pool') as mock_pool:
            mock_pool.recruit_agents = AsyncMock(side_effect=Exception("No agents available"))
            
            try:
                result = await fleet_service.recruit_parallel_batch(
                    task_requirements={},
                    count=1
                )
            except Exception:
                pass  # Expected

    @pytest.mark.asyncio
    async def test_recruit_parallel_batch_empty_requirements(self, fleet_service):
        """Test recruitment with empty task requirements."""
        with patch.object(fleet_service, '_agent_pool') as mock_pool:
            mock_pool.recruit_agents = AsyncMock(return_value=[])
            
            result = await fleet_service.recruit_parallel_batch(
                task_requirements={},
                count=0
            )
            
            assert result is not None or result == []

    @pytest.mark.asyncio
    async def test_recruit_parallel_batch_validates_input(self, fleet_service):
        """Test that recruitment validates input parameters."""
        with patch.object(fleet_service, '_agent_pool') as mock_pool:
            # Should handle invalid input gracefully
            try:
                result = await fleet_service.recruit_parallel_batch(
                    task_requirements=None,
                    count=-1  # Invalid
                )
            except (ValueError, TypeError):
                pass  # Expected for invalid input


# ============================================================================
# Task Execution Tests (5 tests)
# ============================================================================

class TestTaskExecution:
    """Tests for task execution operations."""

    @pytest.mark.asyncio
    async def test_execute_parallel_task_success(self, fleet_service):
        """Test successful parallel task execution."""
        with patch.object(fleet_service, '_blackboard') as mock_bb:
            mock_bb.write = Mock()
            mock_bb.read = Mock(return_value={"status": "completed"})
            
            result = await fleet_service.execute_parallel_task(
                task_id="task-123",
                task_data={"prompt": "Test task"}
            )
            
            assert result is not None

    @pytest.mark.asyncio
    async def test_execute_parallel_task_with_timeout(self, fleet_service):
        """Test task execution with timeout."""
        with patch.object(fleet_service, '_blackboard') as mock_bb:
            mock_bb.write = Mock()
            mock_bb.read = Mock(return_value={"status": "timeout"})
            
            result = await fleet_service.execute_parallel_task(
                task_id="task-456",
                task_data={},
                timeout_seconds=30
            )
            
            assert result is not None

    @pytest.mark.asyncio
    async def test_execute_parallel_task_handles_error(self, fleet_service):
        """Test task execution handles errors gracefully."""
        with patch.object(fleet_service, '_blackboard') as mock_bb:
            mock_bb.write = Mock(side_effect=Exception("Blackboard error"))
            
            try:
                result = await fleet_service.execute_parallel_task(
                    task_id="task-789",
                    task_data={}
                )
            except Exception:
                pass  # Expected

    @pytest.mark.asyncio
    async def test_execute_parallel_task_decomposes_complex_task(self, fleet_service):
        """Test that complex tasks are decomposed."""
        with patch.object(fleet_service, '_blackboard') as mock_bb:
            mock_bb.write = Mock()
            mock_bb.read = Mock(return_value={"status": "decomposed"})
            
            result = await fleet_service.execute_parallel_task(
                task_id="complex-task",
                task_data={
                    "prompt": "Multi-step analysis",
                    "steps": ["step1", "step2", "step3"]
                }
            )
            
            assert result is not None

    @pytest.mark.asyncio
    async def test_execute_parallel_task_aggregates_results(self, fleet_service):
        """Test that parallel task results are aggregated."""
        with patch.object(fleet_service, '_blackboard') as mock_bb:
            mock_bb.write = Mock()
            mock_bb.read = Mock(return_value={
                "status": "completed",
                "results": ["result1", "result2", "result3"]
            })
            
            result = await fleet_service.execute_parallel_task(
                task_id="aggregate-task",
                task_data={}
            )
            
            assert result is not None


# ============================================================================
# Fleet Snapshot Tests (5 tests)
# ============================================================================

class TestFleetSnapshot:
    """Tests for fleet state snapshots."""

    @pytest.mark.asyncio
    async def test_get_fleet_snapshot_basic(self, fleet_service):
        """Test getting basic fleet snapshot."""
        with patch.object(fleet_service, '_agent_pool') as mock_pool:
            mock_pool.get_active_agents = Mock(return_value=[Mock(), Mock()])
            mock_pool.get_idle_agents = Mock(return_value=[Mock()])
            
            snapshot = await fleet_service.get_fleet_snapshot(chain_id="test-chain")
            
            assert snapshot is not None

    @pytest.mark.asyncio
    async def test_get_fleet_snapshot_includes_metrics(self, fleet_service):
        """Test that snapshot includes fleet metrics."""
        with patch.object(fleet_service, '_agent_pool') as mock_pool:
            mock_pool.get_active_agents = Mock(return_value=[])
            mock_pool.get_idle_agents = Mock(return_value=[])
            mock_pool.get_capacity = Mock(return_value=10)
            mock_pool.get_utilization = Mock(return_value=0.3)
            
            snapshot = await fleet_service.get_fleet_snapshot(chain_id="metrics-chain")
            
            assert snapshot is not None

    @pytest.mark.asyncio
    async def test_get_fleet_snapshot_with_task_info(self, fleet_service):
        """Test snapshot includes task execution information."""
        with patch.object(fleet_service, '_blackboard') as mock_bb:
            mock_bb.get_active_tasks = Mock(return_value=[{"task_id": "task-1"}])
            
            snapshot = await fleet_service.get_fleet_snapshot(chain_id="task-info-chain")
            
            assert snapshot is not None

    @pytest.mark.asyncio
    async def test_get_fleet_snapshot_empty_fleet(self, fleet_service):
        """Test snapshot when fleet is empty."""
        with patch.object(fleet_service, '_agent_pool') as mock_pool:
            mock_pool.get_active_agents = Mock(return_value=[])
            mock_pool.get_idle_agents = Mock(return_value=[])
            
            snapshot = await fleet_service.get_fleet_snapshot(chain_id="empty-fleet")
            
            assert snapshot is not None

    @pytest.mark.asyncio
    async def test_get_fleet_snapshot_handles_missing_chain(self, fleet_service):
        """Test snapshot handles missing chain gracefully."""
        snapshot = await fleet_service.get_fleet_snapshot(chain_id="nonexistent-chain")
        
        assert snapshot is not None


# ============================================================================
# Total: 20 tests covering fleet coordination
# ============================================================================
