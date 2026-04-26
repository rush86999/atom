"""
Tests for ScalingProposalService

Test coverage for fleet scaling proposal service including:
- Scaling analysis and proposal generation
- Proposal management (create, approve, reject)
- Auto-scaling logic with hysteresis
- Fleet integration with metrics and overage services
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from core.fleet_orchestration.scaling_proposal_service import (
    ScalingProposalService,
    ScalingProposal,
    ScalingProposalType,
    ScalingProposalStatus,
    get_scaling_proposal_service,
)


# ============================================================================
# Test: Scaling Analysis
# ============================================================================

class TestScalingAnalysis:
    """Test scaling requirement analysis and proposal generation."""

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_with_critical_success_rate(self):
        """Scaling proposal created when success rate is critical."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-001"
        mock_metrics = Mock()
        mock_metrics.success_rate = 65.0  # Below critical threshold (70%)
        mock_metrics.avg_latency_ms = 10000
        mock_metrics.throughput_per_minute = 5.0
        mock_metrics.execution_count = 5

        with patch.object(service, 'metrics_service') as mock_metrics_svc:
            mock_metrics_svc.get_metrics = AsyncMock(return_value=mock_metrics)
            with patch.object(service, '_check_expansion_need') as mock_check:
                mock_check.return_value = ScalingProposal(
                    chain_id=mock_chain_id,
                    proposal_type=ScalingProposalType.EXPANSION,
                    current_fleet_size=5,
                    proposed_fleet_size=8,
                    reason="Critical success rate (65.0% < 70.0%)",
                    metrics={"success_rate": 65.0},
                    cost_estimate=0.72,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
                )
                with patch.object(service, '_check_hysteresis', return_value=True):

                    # Act
                    result = await service.analyze_scaling_need(mock_chain_id)

                    # Assert
                    assert result is not None
                    assert result.proposal_type == ScalingProposalType.EXPANSION
                    assert result.proposed_fleet_size == 8
                    assert "Critical success rate" in result.reason

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_with_warning_latency(self):
        """Scaling proposal created with warning urgency for high latency."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-002"
        mock_metrics = Mock()
        mock_metrics.success_rate = 90.0
        mock_metrics.avg_latency_ms = 25000  # Above warning threshold (20000ms)
        mock_metrics.throughput_per_minute = 3.0
        mock_metrics.execution_count = 4

        with patch.object(service, 'metrics_service') as mock_metrics_svc:
            mock_metrics_svc.get_metrics = AsyncMock(return_value=mock_metrics)
            with patch.object(service, '_check_expansion_need') as mock_check:
                mock_check.return_value = ScalingProposal(
                    chain_id=mock_chain_id,
                    proposal_type=ScalingProposalType.EXPANSION,
                    current_fleet_size=4,
                    proposed_fleet_size=6,
                    reason="High latency (25000ms > 20000ms)",
                    metrics={"avg_latency_ms": 25000},
                    cost_estimate=0.48,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
                )
                with patch.object(service, '_check_hysteresis', return_value=True):

                    # Act
                    result = await service.analyze_scaling_need(mock_chain_id)

                    # Assert
                    assert result is not None
                    assert "High latency" in result.reason

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_no_scaling_required(self):
        """No scaling proposal created when metrics are healthy."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-003"
        mock_metrics = Mock()
        mock_metrics.success_rate = 92.0
        mock_metrics.avg_latency_ms = 5000
        mock_metrics.throughput_per_minute = 4.0
        mock_metrics.execution_count = 5

        with patch.object(service, 'metrics_service') as mock_metrics_svc:
            mock_metrics_svc.get_metrics = AsyncMock(return_value=mock_metrics)
            with patch.object(service, '_check_expansion_need', return_value=None):
                with patch.object(service, '_check_contraction_need', return_value=None):

                    # Act
                    result = await service.analyze_scaling_need(mock_chain_id)

                    # Assert
                    assert result is None

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_with_contraction(self):
        """Contraction proposal created for underutilized fleet."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-004"
        mock_metrics = Mock()
        mock_metrics.success_rate = 96.0  # Excellent
        mock_metrics.avg_latency_ms = 3000
        mock_metrics.throughput_per_minute = 1.0  # Low throughput
        mock_metrics.execution_count = 8

        with patch.object(service, 'metrics_service') as mock_metrics_svc:
            mock_metrics_svc.get_metrics = AsyncMock(return_value=mock_metrics)
            with patch.object(service, '_check_contraction_need') as mock_check:
                mock_check.return_value = ScalingProposal(
                    chain_id=mock_chain_id,
                    proposal_type=ScalingProposalType.CONTRACTION,
                    current_fleet_size=8,
                    proposed_fleet_size=5,
                    reason="Underutilized fleet (success rate 96.0%, throughput 1.0 tasks/min)",
                    metrics={"success_rate": 96.0},
                    cost_estimate=-0.84,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=7)
                )
                with patch.object(service, '_check_hysteresis', return_value=True):

                    # Act
                    result = await service.analyze_scaling_need(mock_chain_id)

                    # Assert
                    assert result is not None
                    assert result.proposal_type == ScalingProposalType.CONTRACTION
                    assert result.proposed_fleet_size == 5
                    assert result.cost_estimate < 0  # Negative = savings

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_suppressed_by_hysteresis(self):
        """Scaling proposal suppressed by hysteresis check."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-005"
        mock_metrics = Mock()
        mock_metrics.success_rate = 60.0
        mock_metrics.avg_latency_ms = 50000
        mock_metrics.throughput_per_minute = 2.0
        mock_metrics.execution_count = 3

        with patch.object(service, 'metrics_service') as mock_metrics_svc:
            mock_metrics_svc.get_metrics = AsyncMock(return_value=mock_metrics)
            with patch.object(service, '_check_expansion_need') as mock_check:
                mock_check.return_value = ScalingProposal(
                    chain_id=mock_chain_id,
                    proposal_type=ScalingProposalType.EXPANSION,
                    current_fleet_size=3,
                    proposed_fleet_size=5,
                    reason="Critical success rate",
                    metrics={},
                    cost_estimate=0.48,
                    expires_at=datetime.now(timezone.utc)
                )
                with patch.object(service, '_check_hysteresis', return_value=False):

                    # Act
                    result = await service.analyze_scaling_need(mock_chain_id)

                    # Assert
                    assert result is None  # Suppressed by hysteresis

    @pytest.mark.asyncio
    async def test_analyze_scaling_need_handles_exception_gracefully(self):
        """Service returns None on exception during analysis."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-006"

        with patch.object(service, 'metrics_service') as mock_metrics_svc:
            mock_metrics_svc.get_metrics = AsyncMock(side_effect=Exception("Database error"))

            # Act
            result = await service.analyze_scaling_need(mock_chain_id)

            # Assert
            assert result is None  # Graceful degradation

    @pytest.mark.asyncio
    async def test_scaling_proposal_enum_types(self):
        """Scaling proposal enums have correct values."""
        # Assert
        assert ScalingProposalType.EXPANSION == "expansion"
        assert ScalingProposalType.CONTRACTION == "contraction"
        assert ScalingProposalStatus.PENDING == "pending"
        assert ScalingProposalStatus.APPROVED == "approved"
        assert ScalingProposalStatus.REJECTED == "rejected"
        assert ScalingProposalStatus.EXPIRED == "expired"
        assert ScalingProposalStatus.EXECUTED == "executed"


# ============================================================================
# Test: Proposal Management
# ============================================================================

class TestProposalManagement:
    """Test proposal creation, approval, rejection, and lifecycle."""

    def test_create_expansion_proposal_success(self):
        """Manual expansion proposal created successfully."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-101"
        mock_current_size = 5
        mock_proposed_size = 8
        mock_reason = "Manual expansion request"

        with patch.object(service, 'validate_fleet_size_limit') as mock_validate:
            mock_validate.return_value = {
                "allowed": True,
                "reason": "Within fleet size limits",
                "current_limit": 100,
                "current_size": 5,
                "usage_percent": 5.0,
                "warnings": []
            }
            with patch.object(service, '_persist_proposal', new_callable=AsyncMock):
                with patch.object(service, '_set_hysteresis_timestamp', new_callable=AsyncMock):

                    # Act
                    import asyncio
                    result = asyncio.run(service.create_expansion_proposal(
                        mock_chain_id,
                        mock_current_size,
                        mock_proposed_size,
                        mock_reason
                    ))

                    # Assert
                    assert result.proposal_type == ScalingProposalType.EXPANSION
                    assert result.current_fleet_size == mock_current_size
                    assert result.proposed_fleet_size == mock_proposed_size
                    assert result.reason == mock_reason
                    assert result.cost_estimate > 0  # Expansion costs money

    def test_create_expansion_proposal_exceeds_limit_with_overage(self):
        """Expansion proposal exceeding limit requires overage."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-102"
        mock_current_size = 95
        mock_proposed_size = 105  # Exceeds default limit of 100

        with patch.object(service, 'validate_fleet_size_limit') as mock_validate:
            mock_validate.return_value = {
                "allowed": False,
                "reason": "Proposed fleet size 105 exceeds limit 100",
                "current_limit": 100,
                "current_size": 95,
                "usage_percent": 95.0,
                "warnings": [{"severity": "critical", "message": "At 95% of limit"}]
            }
            with patch('core.fleet_orchestration.scaling_proposal_service.os.getenv', return_value="100"):

                # Act & Assert
                import asyncio
                with pytest.raises(ValueError, match="Cannot create expansion proposal"):
                    asyncio.run(service.create_expansion_proposal(
                        mock_chain_id,
                        mock_current_size,
                        mock_proposed_size,
                        "Test expansion"
                    ))

    def test_create_contraction_proposal_success(self):
        """Manual contraction proposal created successfully."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-103"
        mock_current_size = 10
        mock_proposed_size = 7
        mock_reason = "Cost optimization"

        with patch.object(service, '_persist_proposal', new_callable=AsyncMock):
            with patch.object(service, '_set_hysteresis_timestamp', new_callable=AsyncMock):

                # Act
                import asyncio
                result = asyncio.run(service.create_contraction_proposal(
                    mock_chain_id,
                    mock_current_size,
                    mock_proposed_size,
                    mock_reason
                ))

                # Assert
                assert result.proposal_type == ScalingProposalType.CONTRACTION
                assert result.current_fleet_size == mock_current_size
                assert result.proposed_fleet_size == mock_proposed_size
                assert result.cost_estimate < 0  # Contraction saves money

    def test_approve_proposal_success(self):
        """Proposal approved successfully."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_proposal_id = "prop-001"
        mock_approved_by = "user-123"

        mock_model = Mock()
        mock_model.id = mock_proposal_id
        mock_model.status = 'pending'
        mock_model.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_db.query.return_value.filter.return_value.first.return_value = mock_model
        mock_db.commit = Mock()

        with patch.object(service, 'get_proposal') as mock_get:
            mock_get.return_value = ScalingProposal(
                id=mock_proposal_id,
                chain_id="chain-001",
                proposal_type=ScalingProposalType.EXPANSION,
                current_fleet_size=5,
                proposed_fleet_size=8,
                reason="Test",
                metrics={},
                cost_estimate=0.72,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
            )

            # Act
            import asyncio
            result = asyncio.run(service.approve_proposal(mock_proposal_id, mock_approved_by))

            # Assert
            assert result.status == ScalingProposalStatus.APPROVED
            mock_model.status = 'approved'
            mock_model.approved_by = mock_approved_by
            mock_db.commit.assert_called_once()

    def test_approve_proposal_not_found(self):
        """Approving non-existent proposal raises ValueError."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_proposal_id = "prop-999"
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act & Assert
        import asyncio
        with pytest.raises(ValueError, match="Proposal .* not found"):
            asyncio.run(service.approve_proposal(mock_proposal_id, "user-123"))

    def test_approve_proposal_already_approved(self):
        """Approving already-approved proposal raises ValueError."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_proposal_id = "prop-002"
        mock_model = Mock()
        mock_model.id = mock_proposal_id
        mock_model.status = 'approved'  # Already approved
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        # Act & Assert
        import asyncio
        with pytest.raises(ValueError, match="is not pending"):
            asyncio.run(service.approve_proposal(mock_proposal_id, "user-123"))

    def test_approve_proposal_expired(self):
        """Approving expired proposal raises ValueError."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_proposal_id = "prop-003"
        mock_model = Mock()
        mock_model.id = mock_proposal_id
        mock_model.status = 'pending'
        mock_model.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # Expired
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model
        mock_db.commit = Mock()

        # Act & Assert
        import asyncio
        with pytest.raises(ValueError, match="has expired"):
            asyncio.run(service.approve_proposal(mock_proposal_id, "user-123"))

    def test_reject_proposal_success(self):
        """Proposal rejected successfully with hysteresis suppression."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_proposal_id = "prop-004"
        mock_rejected_by = "user-456"
        mock_rejection_reason = "Budget constraints"

        mock_model = Mock()
        mock_model.id = mock_proposal_id
        mock_model.chain_id = "chain-001"
        mock_model.status = 'pending'
        mock_model.proposal_type = 'expansion'
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model
        mock_db.commit = Mock()

        with patch.object(service, 'get_proposal') as mock_get:
            mock_get.return_value = ScalingProposal(
                id=mock_proposal_id,
                chain_id="chain-001",
                proposal_type=ScalingProposalType.EXPANSION,
                current_fleet_size=5,
                proposed_fleet_size=8,
                reason="Test",
                metrics={},
                cost_estimate=0.72,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
            )
            with patch.object(service, '_set_rejection_suppression', new_callable=AsyncMock):

                # Act
                import asyncio
                result = asyncio.run(service.reject_proposal(
                    mock_proposal_id,
                    mock_rejected_by,
                    mock_rejection_reason
                ))

                # Assert
                assert result.status == ScalingProposalStatus.REJECTED
                mock_model.status = 'rejected'
                mock_model.rejection_reason = mock_rejection_reason
                mock_db.commit.assert_called_once()


# ============================================================================
# Test: Auto-Scaling Logic
# ============================================================================

class TestAutoScalingLogic:
    """Test auto-scaling triggers, thresholds, and hysteresis."""

    def test_hysteresis_allows_first_proposal(self):
        """Hysteresis allows first proposal (no previous timestamp)."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-201"

        with patch.object(service, '_get_redis', return_value=None):

            # Act
            import asyncio
            result = asyncio.run(service._check_hysteresis(mock_chain_id, "expansion"))

            # Assert
            assert result is True  # No Redis = allow

    def test_hysteresis_suppresses_rapid_proposals(self):
        """Hysteresis suppresses proposals within cooldown period."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-202"
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=(datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat())

        with patch.object(service, '_get_redis', return_value=mock_redis):

            # Act
            import asyncio
            result = asyncio.run(service._check_hysteresis(mock_chain_id, "expansion"))

            # Assert
            assert result is False  # Suppressed (within 1 hour cooldown)

    def test_hysteresis_allows_after_cooldown(self):
        """Hysteresis allows proposal after cooldown period."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-203"
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())

        with patch.object(service, '_get_redis', return_value=mock_redis):

            # Act
            import asyncio
            result = asyncio.run(service._check_hysteresis(mock_chain_id, "expansion"))

            # Assert
            assert result is True  # Allowed (after 1 hour cooldown)

    def test_default_thresholds_configured(self):
        """Default scaling thresholds are properly configured."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        # Assert
        assert "expansion" in service.DEFAULT_THRESHOLDS
        assert "contraction" in service.DEFAULT_THRESHOLDS
        assert service.DEFAULT_THRESHOLDS["expansion"]["success_rate_critical"] == 70.0
        assert service.DEFAULT_THRESHOLDS["expansion"]["latency_critical_ms"] == 45000
        assert service.DEFAULT_THRESHOLDS["contraction"]["utilization_low"] == 30.0

    def test_hysteresis_configuration(self):
        """Hysteresis configuration values are set."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        # Assert
        assert "min_time_between_proposals_hours" in service.HYSTERESIS_CONFIG
        assert "rejection_suppression_hours" in service.HYSTERESIS_CONFIG
        assert service.HYSTERESIS_CONFIG["min_time_between_proposals_hours"] == 1
        assert service.HYSTERESIS_CONFIG["rejection_suppression_hours"] == 4


# ============================================================================
# Test: Fleet Integration
# ============================================================================

class TestFleetIntegration:
    """Test integration with fleet coordinator, metrics, and overage services."""

    @pytest.mark.asyncio
    async def test_validate_fleet_size_limit_within_limit(self):
        """Fleet size validation passes when within limit."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-301"
        mock_proposed_size = 50

        with patch.object(service, 'overage_service') as mock_overage:
            mock_overage.get_effective_limit.return_value = 100
            with patch.object(service, '_get_current_fleet_size', new_callable=AsyncMock, return_value=40):

                # Act
                result = await service.validate_fleet_size_limit(mock_chain_id, mock_proposed_size)

                # Assert
                assert result["allowed"] is True
                assert result["current_limit"] == 100
                assert result["current_size"] == 40
                assert len(result["warnings"]) == 0

    @pytest.mark.asyncio
    async def test_validate_fleet_size_limit_exceeds(self):
        """Fleet size validation fails when exceeding limit."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-302"
        mock_proposed_size = 120

        with patch.object(service, 'overage_service') as mock_overage:
            mock_overage.get_effective_limit.return_value = 100
            with patch.object(service, '_get_current_fleet_size', new_callable=AsyncMock, return_value=95):

                # Act
                result = await service.validate_fleet_size_limit(mock_chain_id, mock_proposed_size)

                # Assert
                assert result["allowed"] is False
                assert "exceeds limit" in result["reason"]
                assert result["current_limit"] == 100

    @pytest.mark.asyncio
    async def test_validate_fleet_size_warning_at_80_percent(self):
        """Warning generated when fleet size at 80% of limit."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-303"
        mock_proposed_size = 85

        with patch.object(service, 'overage_service') as mock_overage:
            mock_overage.get_effective_limit.return_value = 100
            with patch.object(service, '_get_current_fleet_size', new_callable=AsyncMock, return_value=80):

                # Act
                result = await service.validate_fleet_size_limit(mock_chain_id, mock_proposed_size)

                # Assert
                assert result["allowed"] is True
                assert len(result["warnings"]) == 1
                assert result["warnings"][0]["severity"] == "warning"
                assert "80%" in result["warnings"][0]["message"]

    @pytest.mark.asyncio
    async def test_validate_fleet_size_critical_warning_at_90_percent(self):
        """Critical warning generated when fleet size at 90% of limit."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-304"
        mock_proposed_size = 92

        with patch.object(service, 'overage_service') as mock_overage:
            mock_overage.get_effective_limit.return_value = 100
            with patch.object(service, '_get_current_fleet_size', new_callable=AsyncMock, return_value=90):

                # Act
                result = await service.validate_fleet_size_limit(mock_chain_id, mock_proposed_size)

                # Assert
                assert result["allowed"] is True
                assert len(result["warnings"]) == 1
                assert result["warnings"][0]["severity"] == "critical"
                assert "90%" in result["warnings"][0]["message"]

    @pytest.mark.asyncio
    async def test_get_current_fleet_size_queries_database(self):
        """Current fleet size retrieved from database."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_chain_id = "chain-305"

        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 7
        mock_db.query.return_value = mock_query

        # Act
        result = await service._get_current_fleet_size(mock_chain_id)

        # Assert
        assert result == 7
        mock_db.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_estimate_scaling_cost_calculation(self):
        """Scaling cost estimated correctly."""
        # Arrange
        mock_db = Mock(spec=Session)
        service = ScalingProposalService(mock_db)

        mock_current_size = 10
        mock_proposed_size = 15
        mock_duration_hours = 24.0

        # Act
        result = await service.estimate_scaling_cost(
            mock_current_size,
            mock_proposed_size,
            mock_duration_hours
        )

        # Assert
        assert result == 1.2  # 5 agents * $0.01/hour * 24 hours = $1.20


# ============================================================================
# Test: Scaling Proposal Model
# ============================================================================

class TestScalingProposalModel:
    """Test ScalingProposal Pydantic model validation."""

    def test_scaling_proposal_model_creation(self):
        """ScalingProposal model created with valid fields."""
        # Arrange & Act
        proposal = ScalingProposal(
            id="prop-001",
            chain_id="chain-001",
            proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=5,
            proposed_fleet_size=8,
            reason="Test expansion",
            metrics={"success_rate": 65.0},
            cost_estimate=0.72,
            duration_hours=24.0,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )

        # Assert
        assert proposal.id == "prop-001"
        assert proposal.chain_id == "chain-001"
        assert proposal.proposal_type == ScalingProposalType.EXPANSION
        assert proposal.current_fleet_size == 5
        assert proposal.proposed_fleet_size == 8
        assert proposal.status == ScalingProposalStatus.PENDING  # Default

    def test_scaling_proposal_model_with_defaults(self):
        """ScalingProposal model uses default values correctly."""
        # Arrange & Act
        proposal = ScalingProposal(
            chain_id="chain-002",
            proposal_type=ScalingProposalType.CONTRACTION,
            current_fleet_size=10,
            proposed_fleet_size=7,
            reason="Test contraction",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )

        # Assert
        assert proposal.id is not None  # Auto-generated UUID
        assert proposal.status == ScalingProposalStatus.PENDING
        assert proposal.cost_estimate >= 0  # Default validation
        assert proposal.duration_hours >= 0  # Default validation
        assert proposal.metrics == {}  # Default empty dict
        assert proposal.metadata == {}  # Default empty dict


# ============================================================================
# Test: Singleton Pattern
# ============================================================================

class TestSingletonPattern:
    """Test singleton service instance management."""

    def test_get_scaling_proposal_service_returns_singleton(self):
        """get_scaling_proposal_service returns singleton instance."""
        # Arrange
        mock_db = Mock(spec=Session)

        # Act
        service1 = get_scaling_proposal_service(mock_db)
        service2 = get_scaling_proposal_service(mock_db)

        # Assert
        assert service1 is service2  # Same instance

    def test_get_scaling_proposal_service_initializes_once(self):
        """Singleton service initialized only once."""
        # Arrange
        mock_db = Mock(spec=Session)

        # Act
        service = get_scaling_proposal_service(mock_db)

        # Assert
        assert isinstance(service, ScalingProposalService)
        assert service.db is mock_db
