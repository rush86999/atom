"""
Tests for FleetScalerService

Test coverage for fleet scaling orchestration including:
- Scaling operations (expand, contract, execute)
- Resource management and allocation
- Capacity planning and forecasting
- Fleet integration with proposal and metrics services
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.fleet_orchestration.fleet_scaler_service import (
    FleetScalerService,
    ScalingOperation,
    ScalingOperationStatus,
)
from core.fleet_orchestration.scaling_proposal_service import (
    ScalingProposal,
    ScalingProposalType,
    ScalingProposalStatus,
)


# ============================================================================
# Test: Scaling Operations
# ============================================================================

class TestScalingOperations:
    """Test scaling operation execution and management."""

    @pytest.mark.asyncio
    async def test_monitor_and_scale_creates_proposal(self):
        """Monitor and scale creates proposal when metrics indicate need."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_chain_id = "chain-001"
        mock_metrics = Mock()
        mock_metrics.success_rate = 60.0  # Critical
        mock_metrics.avg_latency_ms = 50000
        mock_metrics.throughput_per_minute = 2.0
        mock_metrics.execution_count = 5

        mock_proposal = ScalingProposal(
            id="prop-001",
            chain_id=mock_chain_id,
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=5,
            proposed_fleet_size=8,
            reason="Critical success rate",
            metrics={"success_rate": 60.0},
            cost_estimate=0.72,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )

        with patch.object(service, 'metrics_service') as mock_metrics_svc:
            mock_metrics_svc.get_metrics = AsyncMock(return_value=mock_metrics)
            with patch.object(service, 'proposal_service') as mock_proposal_svc:
                mock_proposal_svc.analyze_scaling_need = AsyncMock(return_value=mock_proposal)
                mock_proposal_svc._persist_proposal = AsyncMock()

                # Act
                result = await service.monitor_and_scale(mock_chain_id)

                # Assert
                assert result is not None
                assert result.id == "prop-001"
                assert result.proposal_type == ScalingProposalType.EXPANSION
                mock_proposal_svc._persist_proposal.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_and_scale_no_scaling_needed(self):
        """Monitor and scale returns None when metrics are healthy."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_chain_id = "chain-002"
        mock_metrics = Mock()
        mock_metrics.success_rate = 95.0
        mock_metrics.avg_latency_ms = 5000
        mock_metrics.throughput_per_minute = 3.0

        with patch.object(service, 'metrics_service') as mock_metrics_svc:
            mock_metrics_svc.get_metrics = AsyncMock(return_value=mock_metrics)
            with patch.object(service, 'proposal_service') as mock_proposal_svc:
                mock_proposal_svc.analyze_scaling_need = AsyncMock(return_value=None)

                # Act
                result = await service.monitor_and_scale(mock_chain_id)

                # Assert
                assert result is None

    @pytest.mark.asyncio
    async def test_execute_scaling_expansion_success(self):
        """Execute scaling operation for fleet expansion."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal_id = "prop-003"
        mock_proposal = ScalingProposal(
            id=mock_proposal_id,
            chain_id="chain-003",
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=5,
            proposed_fleet_size=8,
            reason="Test expansion",
            metrics={},
            cost_estimate=0.72,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            status=ScalingProposalStatus.APPROVED
        )

        with patch.object(service, 'proposal_service') as mock_proposal_svc:
            mock_proposal_svc.get_proposal = AsyncMock(return_value=mock_proposal)
            mock_proposal_svc._update_proposal_status = AsyncMock()
            with patch.object(service, '_execute_expansion') as mock_expand:
                mock_expand.return_value = {"recruited_agents": ["agent-001", "agent-002", "agent-003"]}
                with patch.object(service, '_persist_operation', new_callable=AsyncMock):

                    # Act
                    result = await service.execute_scaling(mock_proposal_id)

                    # Assert
                    assert result.status == ScalingOperationStatus.COMPLETED
                    assert result.from_size == 5
                    assert result.to_size == 8
                    assert len(result.agents_added) == 3

    @pytest.mark.asyncio
    async def test_execute_scaling_contraction_success(self):
        """Execute scaling operation for fleet contraction."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal_id = "prop-004"
        mock_proposal = ScalingProposal(
            id=mock_proposal_id,
            chain_id="chain-004",
            proposal_type=ScalingProposalType.CONTRACTION,
            current_fleet_size=10,
            proposed_fleet_size=7,
            reason="Test contraction",
            metrics={},
            cost_estimate=-0.84,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            status=ScalingProposalStatus.APPROVED
        )

        with patch.object(service, 'proposal_service') as mock_proposal_svc:
            mock_proposal_svc.get_proposal = AsyncMock(return_value=mock_proposal)
            mock_proposal_svc._update_proposal_status = AsyncMock()
            with patch.object(service, '_execute_contraction') as mock_contract:
                mock_contract.return_value = {"removed_agents": ["agent-008", "agent-009", "agent-010"]}
                with patch.object(service, '_persist_operation', new_callable=AsyncMock):

                    # Act
                    result = await service.execute_scaling(mock_proposal_id)

                    # Assert
                    assert result.status == ScalingOperationStatus.COMPLETED
                    assert result.from_size == 10
                    assert result.to_size == 7
                    assert len(result.agents_removed) == 3

    @pytest.mark.asyncio
    async def test_execute_scaling_proposal_not_found(self):
        """Execute scaling raises ValueError for missing proposal."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal_id = "prop-999"

        with patch.object(service, 'proposal_service') as mock_proposal_svc:
            mock_proposal_svc.get_proposal = AsyncMock(return_value=None)

            # Act & Assert
            with pytest.raises(ValueError, match="Proposal .* not found"):
                await service.execute_scaling(mock_proposal_id)

    @pytest.mark.asyncio
    async def test_execute_scaling_proposal_not_approved(self):
        """Execute scaling raises ValueError for non-approved proposal."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal_id = "prop-005"
        mock_proposal = ScalingProposal(
            id=mock_proposal_id,
            chain_id="chain-005",
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=5,
            proposed_fleet_size=8,
            reason="Test",
            metrics={},
            cost_estimate=0.72,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            status=ScalingProposalStatus.PENDING  # Not approved
        )

        with patch.object(service, 'proposal_service') as mock_proposal_svc:
            mock_proposal_svc.get_proposal = AsyncMock(return_value=mock_proposal)

            # Act & Assert
            with pytest.raises(ValueError, match="is not approved"):
                await service.execute_scaling(mock_proposal_id)

    @pytest.mark.asyncio
    async def test_execute_scaling_proposal_expired(self):
        """Execute scaling raises ValueError for expired proposal."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal_id = "prop-006"
        mock_proposal = ScalingProposal(
            id=mock_proposal_id,
            chain_id="chain-006",
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=5,
            proposed_fleet_size=8,
            reason="Test",
            metrics={},
            cost_estimate=0.72,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            status=ScalingProposalStatus.APPROVED
        )

        with patch.object(service, 'proposal_service') as mock_proposal_svc:
            mock_proposal_svc.get_proposal = AsyncMock(return_value=mock_proposal)

            # Act & Assert
            with pytest.raises(ValueError, match="has expired"):
                await service.execute_scaling(mock_proposal_id)


# ============================================================================
# Test: Resource Management
# ============================================================================

class TestResourceManagement:
    """Test resource allocation, deallocation, and monitoring."""

    @pytest.mark.asyncio
    async def test_execute_expansion_recruits_agents(self):
        """Execute expansion recruits new agents to fleet."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal = ScalingProposal(
            id="prop-007",
            chain_id="chain-007",
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=5,
            proposed_fleet_size=8,
            reason="Test expansion",
            metrics={},
            cost_estimate=0.72,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        mock_operation = ScalingOperation(
            id="op-001",
            chain_id="chain-007",
            proposal_id="prop-007",
            operation_type="expand",
            from_size=5,
            to_size=8,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )

        mock_query = Mock()
        mock_query.all.return_value = [("agent-001",)]  # Existing agent
        mock_db.query.return_value.filter.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('core.fleet_orchestration.fleet_scaler_service.get_distributed_blackboard') as mock_bb:
            mock_bb.return_value.notify_state_update = AsyncMock()

            # Act
            result = await service._execute_expansion(mock_proposal, mock_operation)

            # Assert
            assert "recruited_agents" in result
            assert len(result["recruited_agents"]) == 3  # 8 - 5 = 3 agents
            assert len(mock_operation.agents_added) == 3

    @pytest.mark.asyncio
    async def test_execute_contraction_removes_agents(self):
        """Execute contraction removes idle agents from fleet."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal = ScalingProposal(
            id="prop-008",
            chain_id="chain-008",
            proposal_type=ScalingProposalType.CONTRACTION,
            current_fleet_size=10,
            proposed_fleet_size=7,
            reason="Test contraction",
            metrics={},
            cost_estimate=-0.84,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        mock_operation = ScalingOperation(
            id="op-002",
            chain_id="chain-008",
            proposal_id="prop-008",
            operation_type="contract",
            from_size=10,
            to_size=7,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )

        mock_link_1 = Mock()
        mock_link_1.child_agent_id = "agent-008"
        mock_link_1.status = "active"
        mock_link_2 = Mock()
        mock_link_2.child_agent_id = "agent-009"
        mock_link_2.status = "active"
        mock_link_3 = Mock()
        mock_link_3.child_agent_id = "agent-010"
        mock_link_3.status = "active"

        mock_query = Mock()
        mock_query.order_by.return_value.limit.return_value.all.return_value = [
            mock_link_1, mock_link_2, mock_link_3
        ]
        mock_db.query.return_value.filter.return_value = mock_query
        mock_db.commit = Mock()

        with patch('core.fleet_orchestration.fleet_scaler_service.get_distributed_blackboard') as mock_bb:
            mock_bb.return_value.notify_state_update = AsyncMock()

            # Act
            result = await service._execute_contraction(mock_proposal, mock_operation)

            # Assert
            assert "removed_agents" in result
            assert len(result["removed_agents"]) == 3  # 10 - 7 = 3 agents
            assert len(mock_operation.agents_removed) == 3
            assert mock_link_1.status == "completed"

    @pytest.mark.asyncio
    async def test_scaling_operation_validation(self):
        """Scaling operation model validates correctly."""
        # Arrange & Act
        operation = ScalingOperation(
            id="op-003",
            chain_id="chain-009",
            proposal_id="prop-009",
            operation_type="expand",
            from_size=5,
            to_size=8,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )

        # Assert
        assert operation.id == "op-003"
        assert operation.chain_id == "chain-009"
        assert operation.from_size == 5
        assert operation.to_size == 8
        assert operation.status == ScalingOperationStatus.IN_PROGRESS
        assert len(operation.agents_added) == 0
        assert len(operation.agents_removed) == 0

    @pytest.mark.asyncio
    async def test_execute_scaling_handles_exception(self):
        """Execute scaling handles exceptions and marks operation as failed."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal_id = "prop-010"
        mock_proposal = ScalingProposal(
            id=mock_proposal_id,
            chain_id="chain-010",
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=5,
            proposed_fleet_size=8,
            reason="Test",
            metrics={},
            cost_estimate=0.72,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            status=ScalingProposalStatus.APPROVED
        )

        with patch.object(service, 'proposal_service') as mock_proposal_svc:
            mock_proposal_svc.get_proposal = AsyncMock(return_value=mock_proposal)
            mock_proposal_svc._update_proposal_status = AsyncMock()
            with patch.object(service, '_execute_expansion', side_effect=Exception("Database error")):
                with patch.object(service, '_persist_operation', new_callable=AsyncMock):

                    # Act
                    result = await service.execute_scaling(mock_proposal_id)

                    # Assert
                    assert result.status == ScalingOperationStatus.FAILED
                    assert result.error_message == "Database error"
                    assert result.completed_at is not None


# ============================================================================
# Test: Capacity Planning
# ============================================================================

class TestCapacityPlanning:
    """Test capacity forecasting, reservation, and utilization tracking."""

    @pytest.mark.asyncio
    async def test_check_scaling_constraints_within_limit(self):
        """Check scaling constraints passes when within limit."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_chain_id = "chain-101"
        mock_proposed_size = 50

        with patch.object(service, 'overage_service') as mock_overage:
            mock_overage.get_effective_limit.return_value = 100
            with patch.object(service, '_get_current_fleet_size', new_callable=AsyncMock, return_value=40):
                with patch.object(service, 'overage_service.check_overage_expiry', new_callable=AsyncMock, return_value=False):

                    # Act
                    result = await service.check_scaling_constraints(mock_chain_id, mock_proposed_size)

                    # Assert
                    assert result["allowed"] is True
                    assert result["constraints"]["fleet_size_limit"]["within_limit"] is True

    @pytest.mark.asyncio
    async def test_check_scaling_constraints_exceeds_limit(self):
        """Check scaling constraints fails when exceeding limit."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_chain_id = "chain-102"
        mock_proposed_size = 150

        with patch.object(service, 'overage_service') as mock_overage:
            mock_overage.get_effective_limit.return_value = 100
            with patch.object(service, '_get_current_fleet_size', new_callable=AsyncMock, return_value=95):

                # Act
                result = await service.check_scaling_constraints(mock_chain_id, mock_proposed_size)

                # Assert
                assert result["allowed"] is False
                assert "exceeds effective limit" in result["constraints"]["fleet_size_limit"]["reason"]

    @pytest.mark.asyncio
    async def test_get_scaling_status_comprehensive(self):
        """Get scaling status returns comprehensive fleet information."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_chain_id = "chain-103"

        mock_query = Mock()
        mock_query.scalar.return_value = 7
        mock_db.query.return_value.filter.return_value = mock_query

        with patch.object(service, 'proposal_service') as mock_proposal_svc:
            mock_proposal_svc._model_to_proposal.side_effect = lambda m: ScalingProposal(
                id=m.id,
                chain_id=m.chain_id,
                proposal_type=m.proposal_type,
                current_fleet_size=m.current_fleet_size,
                proposed_fleet_size=m.proposed_fleet_size,
                reason=m.reason,
                metrics=m.metrics_json,
                cost_estimate=m.cost_estimate,
                expires_at=m.expires_at
            )
            with patch.object(service, '_get_recent_operations', new_callable=AsyncMock, return_value=[]):

                # Mock pending proposals query
                mock_proposal_query = Mock()
                mock_proposal_query.all.return_value = []
                mock_db.query.return_value.filter.return_value.filter.return_value = mock_proposal_query

                # Act
                result = await service.get_scaling_status(mock_chain_id)

                # Assert
                assert result["chain_id"] == mock_chain_id
                assert result["current_fleet_size"] == 7
                assert "pending_proposals" in result
                assert "recent_operations" in result
                assert "last_monitored" in result

    @pytest.mark.asyncio
    async def test_get_current_fleet_size_queries_database(self):
        """Get current fleet size from database."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_chain_id = "chain-104"

        mock_query = Mock()
        mock_query.scalar.return_value = 12
        mock_db.query.return_value.filter.return_value = mock_query

        # Act
        result = await service._get_current_fleet_size(mock_chain_id)

        # Assert
        assert result == 12


# ============================================================================
# Test: Fleet Integration
# ============================================================================

class TestFleetIntegration:
    """Test integration with fleet coordinator and metrics services."""

    def test_fleet_scaler_initialization(self):
        """FleetScalerService initializes with required dependencies."""
        # Arrange
        mock_db = Mock(spec=Session)

        # Act
        service = FleetScalerService(mock_db)

        # Assert
        assert service.db is mock_db
        assert service.overage_service is not None
        assert service.proposal_service is not None
        assert service.metrics_service is not None
        assert service.running is False

    def test_scaling_operation_status_enum(self):
        """ScalingOperationStatus enum has correct values."""
        # Assert
        assert ScalingOperationStatus.PENDING == "pending"
        assert ScalingOperationStatus.IN_PROGRESS == "in_progress"
        assert ScalingOperationStatus.COMPLETED == "completed"
        assert ScalingOperationStatus.FAILED == "failed"
        assert ScalingOperationStatus.ROLLED_BACK == "rolled_back"

    @pytest.mark.asyncio
    async def test_blackboard_notification_on_expansion(self):
        """Blackboard notified when agents added during expansion."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal = ScalingProposal(
            id="prop-011",
            chain_id="chain-105",
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=5,
            proposed_fleet_size=7,
            reason="Test",
            metrics={},
            cost_estimate=0.48,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        mock_operation = ScalingOperation(
            id="op-004",
            chain_id="chain-105",
            proposal_id="prop-011",
            operation_type="expand",
            from_size=5,
            to_size=7,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )

        mock_query = Mock()
        mock_query.all.return_value = [("agent-001",)]
        mock_db.query.return_value.filter.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('core.fleet_orchestration.fleet_scaler_service.get_distributed_blackboard') as mock_bb:
            mock_blackboard = AsyncMock()
            mock_blackboard.notify_state_update = AsyncMock()
            mock_bb.return_value = mock_blackboard

            # Act
            await service._execute_expansion(mock_proposal, mock_operation)

            # Assert
            mock_blackboard.notify_state_update.assert_called_once_with(
                chain_id="chain-105",
                update_type="agents_added",
                data={"agent_ids": mock_operation.agents_added}
            )

    @pytest.mark.asyncio
    async def test_blackboard_notification_on_contraction(self):
        """Blackboard notified when agents removed during contraction."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_proposal = ScalingProposal(
            id="prop-012",
            chain_id="chain-106",
            proposal_type=ScalingProposalType.CONTRACTION,
            current_fleet_size=8,
            proposed_fleet_size=6,
            reason="Test",
            metrics={},
            cost_estimate=-0.56,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        mock_operation = ScalingOperation(
            id="op-005",
            chain_id="chain-106",
            proposal_id="prop-012",
            operation_type="contract",
            from_size=8,
            to_size=6,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )

        mock_link = Mock()
        mock_link.child_agent_id = "agent-007"
        mock_link.status = "active"

        mock_query = Mock()
        mock_query.order_by.return_value.limit.return_value.all.return_value = [
            mock_link, Mock(child_agent_id="agent-008", status="active")
        ]
        mock_db.query.return_value.filter.return_value = mock_query
        mock_db.commit = Mock()

        with patch('core.fleet_orchestration.fleet_scaler_service.get_distributed_blackboard') as mock_bb:
            mock_blackboard = AsyncMock()
            mock_blackboard.notify_state_update = AsyncMock()
            mock_bb.return_value = mock_blackboard

            # Act
            await service._execute_contraction(mock_proposal, mock_operation)

            # Assert
            mock_blackboard.notify_state_update.assert_called_once_with(
                chain_id="chain-106",
                update_type="agents_removed",
                data={"agent_ids": mock_operation.agents_removed}
            )

    @pytest.mark.asyncio
    async def test_get_recent_operations(self):
        """Get recent scaling operations for fleet."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = FleetScalerService(mock_db)

        mock_chain_id = "chain-107"

        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        # Act
        result = await service._get_recent_operations(mock_chain_id, limit=5)

        # Assert
        assert isinstance(result, list)
        mock_db.query.assert_called_once()
