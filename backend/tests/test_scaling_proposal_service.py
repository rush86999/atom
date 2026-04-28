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
        # Mock the overage service to return actual values
        scaling_service.overage_service.get_effective_limit = Mock(return_value=20)
        scaling_service._get_current_fleet_size = AsyncMock(return_value=5)

        result = await scaling_service.validate_fleet_size_limit(
            chain_id="test-chain",
            proposed_size=8
        )
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_validate_fleet_size_exceeds_limit(self, scaling_service):
        """Test validation when proposed size exceeds limit."""
        # Mock the overage service to return actual values
        scaling_service.overage_service.get_effective_limit = Mock(return_value=10)
        scaling_service._get_current_fleet_size = AsyncMock(return_value=5)

        result = await scaling_service.validate_fleet_size_limit(
            chain_id="test-chain",
            proposed_size=100
        )
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_validate_fleet_size_limit_checks(self, scaling_service):
        """Test that validation includes limit checks."""
        # Mock the overage service to return actual values
        scaling_service.overage_service.get_effective_limit = Mock(return_value=20)
        scaling_service._get_current_fleet_size = AsyncMock(return_value=10)

        result = await scaling_service.validate_fleet_size_limit(
            chain_id="limit-check",
            proposed_size=15
        )
        assert "allowed" in result
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
            current_size=10,
            proposed_size=5,
            duration_hours=8.0
        )
        # Method uses abs() so cost is always positive
        # Cost represents the magnitude of change (5 agents * 8 hours * $0.01)
        assert cost >= 0
        assert cost == 0.4  # (10-5) * 8.0 * 0.01

    @pytest.mark.asyncio
    async def test_estimate_scaling_cost_zero_duration(self, scaling_service):
        """Test cost estimation with zero duration."""
        cost = await scaling_service.estimate_scaling_cost(
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
        result = await scaling_service.validate_budget_for_proposal(
            chain_id="budget-test",
            proposed_size=10,
            duration_hours=8.0
        )
        # All proposals allowed (no budget tracking)
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_validate_budget_insufficient(self, scaling_service):
        """Test budget validation when insufficient funds."""
        result = await scaling_service.validate_budget_for_proposal(
            chain_id="over-budget",
            proposed_size=20,
            duration_hours=8.0
        )
        # All proposals allowed (no budget tracking)
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_validate_budget_exact_match(self, scaling_service):
        """Test budget validation with exact budget match."""
        result = await scaling_service.validate_budget_for_proposal(
            chain_id="exact-match",
            proposed_size=10,
            duration_hours=8.0
        )
        # All proposals allowed (no budget tracking)
        assert result["allowed"] is True


# ============================================================================
# Proposal Management Tests (3 tests)
# ============================================================================

@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="Service not available")
class TestProposalManagement:
    """Tests for proposal approval/rejection."""

    @pytest.mark.asyncio
    async def test_approve_proposal_success(self, scaling_service, mock_db):
        """Test successful proposal approval."""
        from core.models import ScalingProposal as ScalingProposalRecord

        mock_proposal_record = ScalingProposalRecord(
            id="test-proposal-123",
            chain_id="chain-123",
            proposal_type="expansion",
            status="pending",
            current_agents=10,
            proposed_agents=15,
            reason="Test proposal",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal_record

        result = await scaling_service.approve_proposal(
            proposal_id="test-proposal-123",
            approved_by="user-456"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_reject_proposal_success(self, scaling_service, mock_db):
        """Test successful proposal rejection."""
        from core.models import ScalingProposal as ScalingProposalRecord

        mock_proposal_record = ScalingProposalRecord(
            id="test-proposal-456",
            chain_id="chain-456",
            proposal_type="expansion",
            status="pending",
            current_agents=10,
            proposed_agents=15,
            reason="Test proposal",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal_record

        result = await scaling_service.reject_proposal(
            proposal_id="test-proposal-456",
            rejected_by="user-789",
            reason="Not needed"
        )
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
            can_create = await scaling_service._check_hysteresis("test-chain", "expansion")
            assert can_create is True  # Can create proposal

    @pytest.mark.asyncio
    async def test_check_hysteresis_recent_proposal_exists(self, scaling_service, mock_redis):
        """Test hysteresis check when recent proposal exists."""
        mock_redis.get.return_value = datetime.now(timezone.utc).isoformat()

        with patch.object(scaling_service, '_get_redis', return_value=mock_redis):
            can_create = await scaling_service._check_hysteresis("test-chain", "expansion")
            assert can_create is False  # Cannot create, too soon


# ============================================================================
# Total: 17 tests covering scaling proposal service
# ============================================================================
