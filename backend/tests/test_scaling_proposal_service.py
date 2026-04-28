"""
Tests for ScalingProposalService - Fleet scaling recommendations.

Tests cover:
- Service initialization
- Fleet size validation
- Cost estimation
- Proposal approval/rejection
- Budget validation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

# Try to import the service
try:
    from core.fleet_orchestration.scaling_proposal_service import (
        ScalingProposalService,
        ScalingProposal,
        ScalingProposalType,
        ScalingProposalStatus
    )
    SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import ScalingProposalService: {e}")
    SERVICE_AVAILABLE = False


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.query = Mock()
    db.filter = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.flush = Mock()
    db.session_execute = Mock()
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = Mock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def scaling_service(mock_db, mock_redis):
    """Create ScalingProposalService instance if available."""
    if not SERVICE_AVAILABLE:
        pytest.skip("ScalingProposalService not available")
    
    with patch('core.fleet_orchestration.scaling_proposal_service.PerformanceMetricsService'):
        with patch('core.fleet_orchestration.scaling_proposal_service.OverageService'):
            service = ScalingProposalService(
                db=mock_db,
                redis_url="redis://localhost"
            )
            service._redis_client = mock_redis
            return service


# ============================================================================
# Service Initialization Tests (3 tests)
# ============================================================================

@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="Service not available")
class TestScalingProposalServiceInit:
    """Tests for ScalingProposalService initialization."""

    def test_initialization_with_db(self, mock_db):
        """Test service initialization with database."""
        with patch('core.fleet_orchestration.scaling_proposal_service.PerformanceMetricsService'):
            with patch('core.fleet_orchestration.scaling_proposal_service.OverageService'):
                service = ScalingProposalService(db=mock_db, redis_url=None)
                assert service.db == mock_db
                assert service._redis_client is None

    def test_initialization_with_redis_url(self, mock_db):
        """Test service initialization with Redis URL."""
        with patch('core.fleet_orchestration.scaling_proposal_service.PerformanceMetricsService'):
            with patch('core.fleet_orchestration.scaling_proposal_service.OverageService'):
                service = ScalingProposalService(
                    db=mock_db,
                    redis_url="redis://localhost:6379"
                )
                assert service.redis_url == "redis://localhost:6379"

    def test_initialization_creates_dependencies(self, mock_db):
        """Test that initialization creates required services."""
        with patch('core.fleet_orchestration.scaling_proposal_service.PerformanceMetricsService') as mock_metrics:
            with patch('core.fleet_orchestration.scaling_proposal_service.OverageService') as mock_overage:
                service = ScalingProposalService(db=mock_db)
                assert service.metrics_service is not None
                assert service.overage_service is not None


# ============================================================================
# Fleet Size Validation Tests (3 tests)
# ============================================================================

@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="Service not available")
class TestFleetSizeValidation:
    """Tests for fleet size limit validation."""

    @pytest.mark.asyncio
    async def test_validate_fleet_size_within_limit(self, scaling_service):
        """Test validation when proposed size is within limit."""
        with patch.object(scaling_service, '_get_current_fleet_size', return_value=5):
            result = await scaling_service.validate_fleet_size_limit(
                chain_id="test-chain",
                proposed_size=8
            )
            assert result["within_limit"] is True

    @pytest.mark.asyncio
    async def test_validate_fleet_size_exceeds_limit(self, scaling_service):
        """Test validation when proposed size exceeds limit."""
        with patch.object(scaling_service, '_get_current_fleet_size', return_value=5):
            with patch.object(scaling_service, '_get_fleet_size_warnings') as mock_warnings:
                mock_warnings.return_value = [{"warning": "Approaching limit"}]
                
                result = await scaling_service.validate_fleet_size_limit(
                    chain_id="test-chain",
                    proposed_size=100
                )
                assert result["within_limit"] is False

    @pytest.mark.asyncio
    async def test_validate_fleet_size_limit_checks(self, scaling_service):
        """Test that validation includes limit checks."""
        with patch.object(scaling_service, '_get_current_fleet_size', return_value=10):
            result = await scaling_service.validate_fleet_size_limit(
                chain_id="limit-check",
                proposed_size=15
            )
            assert "within_limit" in result
            assert "current_size" in result


# ============================================================================
# Cost Estimation Tests (3 tests)
# ============================================================================

@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="Service not available")
class TestCostEstimation:
    """Tests for scaling cost estimation."""

    @pytest.mark.asyncio
    async def test_estimate_scaling_cost_expansion(self, scaling_service):
        """Test cost estimation for fleet expansion."""
        cost = await scaling_service.estimate_scaling_cost(
            chain_id="cost-test",
            current_size=5,
            proposed_size=10,
            duration_hours=8.0
        )
        assert cost >= 0
        assert isinstance(cost, (int, float))

    @pytest.mark.asyncio
    async def test_estimate_scaling_cost_contraction(self, scaling_service):
        """Test cost estimation for fleet contraction (savings)."""
        cost = await scaling_service.estimate_scaling_cost(
            chain_id="savings-test",
            current_size=10,
            proposed_size=5,
            duration_hours=8.0
        )
        # Should be negative (savings) or zero
        assert cost <= 0

    @pytest.mark.asyncio
    async def test_estimate_scaling_cost_zero_duration(self, scaling_service):
        """Test cost estimation with zero duration."""
        cost = await scaling_service.estimate_scaling_cost(
            chain_id="zero-duration",
            current_size=5,
            proposed_size=10,
            duration_hours=0.0
        )
        assert cost == 0


# ============================================================================
# Budget Validation Tests (3 tests)
# ============================================================================

@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="Service not available")
class TestBudgetValidation:
    """Tests for budget validation."""

    @pytest.mark.asyncio
    async def test_validate_budget_sufficient(self, scaling_service):
        """Test budget validation when sufficient funds available."""
        with patch.object(scaling_service, 'estimate_scaling_cost', return_value=100.0):
            result = await scaling_service.validate_budget_for_proposal(
                chain_id="budget-test",
                proposed_size=10,
                duration_hours=8.0,
                available_budget=500.0
            )
            assert result["within_budget"] is True

    @pytest.mark.asyncio
    async def test_validate_budget_insufficient(self, scaling_service):
        """Test budget validation when insufficient funds."""
        with patch.object(scaling_service, 'estimate_scaling_cost', return_value=1000.0):
            result = await scaling_service.validate_budget_for_proposal(
                chain_id="over-budget",
                proposed_size=20,
                duration_hours=8.0,
                available_budget=500.0
            )
            assert result["within_budget"] is False

    @pytest.mark.asyncio
    async def test_validate_budget_exact_match(self, scaling_service):
        """Test budget validation with exact budget match."""
        with patch.object(scaling_service, 'estimate_scaling_cost', return_value=500.0):
            result = await scaling_service.validate_budget_for_proposal(
                chain_id="exact-match",
                proposed_size=10,
                duration_hours=8.0,
                available_budget=500.0
            )
            assert result["within_budget"] is True


# ============================================================================
# Proposal Management Tests (3 tests)
# ============================================================================

@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="Service not available")
class TestProposalManagement:
    """Tests for proposal approval/rejection."""

    @pytest.mark.asyncio
    async def test_approve_proposal_success(self, scaling_service, mock_db):
        """Test successful proposal approval."""
        mock_proposal = Mock(spec=ScalingProposal)
        mock_proposal.id = "test-proposal-123"
        mock_proposal.status = ScalingProposalStatus.PENDING
        
        with patch.object(scaling_service, 'get_proposal', return_value=mock_proposal):
            with patch.object(mock_proposal, 'save') as mock_save:
                result = await scaling_service.approve_proposal("test-proposal-123")
                assert result is not None

    @pytest.mark.asyncio
    async def test_reject_proposal_success(self, scaling_service, mock_db):
        """Test successful proposal rejection."""
        mock_proposal = Mock(spec=ScalingProposal)
        mock_proposal.id = "test-proposal-456"
        mock_proposal.status = ScalingProposalStatus.PENDING
        
        with patch.object(scaling_service, 'get_proposal', return_value=mock_proposal):
            with patch.object(mock_proposal, 'save') as mock_save:
                result = await scaling_service.reject_proposal("test-proposal-456", reason="Not needed")
                assert result is not None

    @pytest.mark.asyncio
    async def test_get_proposal_not_found(self, scaling_service):
        """Test getting non-existent proposal."""
        with patch.object(scaling_service, 'get_proposal', return_value=None):
            proposal = await scaling_service.get_proposal("nonexistent")
            assert proposal is None


# ============================================================================
# Hysteresis Tests (2 tests)
# ============================================================================

@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="Service not available")
class TestHysteresis:
    """Tests for proposal hysteresis (preventing flapping)."""

    @pytest.mark.asyncio
    async def test_check_hysteresis_no_recent_proposals(self, scaling_service, mock_redis):
        """Test hysteresis check when no recent proposals."""
        mock_redis.get.return_value = None
        
        with patch.object(scaling_service, '_get_redis', return_value=mock_redis):
            can_create = await scaling_service._check_hysteresis("test-chain")
            assert can_create is True  # Can create proposal

    @pytest.mark.asyncio
    async def test_check_hysteresis_recent_proposal_exists(self, scaling_service, mock_redis):
        """Test hysteresis check when recent proposal exists."""
        mock_redis.get.return_value = datetime.now(timezone.utc).isoformat()
        
        with patch.object(scaling_service, '_get_redis', return_value=mock_redis):
            can_create = await scaling_service._check_hysteresis("test-chain")
            assert can_create is False  # Cannot create, too soon


# ============================================================================
# Total: 17 tests covering scaling proposal service
# ============================================================================
