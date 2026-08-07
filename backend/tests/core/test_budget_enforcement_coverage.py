"""
Comprehensive test coverage for Budget Enforcement Service.

Target: 60%+ line coverage (320+ lines covered out of 534)
Tests: 30+ tests across 4 test classes
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from core.budget_enforcement_service import (
    BudgetEnforcementService,
    BudgetEnforcementMode,
    BudgetError,
    InsufficientBudgetError,
    BudgetNotFoundError,
    ConcurrentModificationError,
)


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = Mock(spec=Session)
    return session


@pytest.fixture
def budget_service(mock_db_session):
    """Create budget enforcement service with mocked database."""
    return BudgetEnforcementService(db=mock_db_session)


@pytest.fixture
def mock_tenant():
    """Mock tenant with budget."""
    tenant = Mock()
    tenant.id = "tenant_123"
    return tenant


@pytest.fixture
def default_spend_result():
    """Default spend aggregation result within budget."""
    return {
        "current_spend_usd": 50.0,
        "budget_limit_usd": 100.0,
        "utilization_percent": 50.0
    }


class TestBudgetEnforcement:
    """Test budget enforcement core functionality."""

    def test_init(self, mock_db_session):
        """Test service initialization."""
        service = BudgetEnforcementService(db=mock_db_session)
        assert service.db == mock_db_session

    @patch('core.budget_enforcement_service.SessionLocal')
    def test_init_without_db_session(self, mock_session_local, mock_db_session):
        """Test service initialization with default database session."""
        mock_session_local.return_value = mock_db_session

        service = BudgetEnforcementService()

        assert service.db is mock_db_session

    def test_context_manager_closes_db(self, mock_db_session):
        """Test context manager closes the database session."""
        service = BudgetEnforcementService(db=mock_db_session)

        with service:
            pass

        mock_db_session.close.assert_called_once()

    def test_close_closes_db(self, mock_db_session):
        """Test close() closes the database session."""
        service = BudgetEnforcementService(db=mock_db_session)

        service.close()

        mock_db_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_budget_within_limit(self, budget_service, default_spend_result):
        """Test checking budget when spend is within limit."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value=default_spend_result)
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant_123",
            agent_id="agent_123",
            action="run_episode"
        )

        assert result["allowed"] is True
        assert result["current_spend_usd"] == 50.0
        assert result["budget_limit_usd"] == 100.0
        assert result["utilization_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_check_budget_soft_stop_blocks_new_episodes(self, budget_service):
        """Test soft_stop blocks new episodes when budget exceeded."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)
        budget_service._has_active_episodes = Mock(return_value=False)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant_123",
            agent_id="agent_123",
            action="run_episode"
        )

        assert result["allowed"] is False
        assert "blocked" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_soft_stop_allows_active_episodes(self, budget_service):
        """Test soft_stop allows active episodes to complete."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)
        budget_service._has_active_episodes = Mock(return_value=True)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant_123",
            agent_id="agent_123",
            action="run_episode"
        )

        assert result["allowed"] is True
        assert "active episode" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_hard_stop_blocks_all(self, budget_service):
        """Test hard_stop blocks all operations when budget exceeded."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.HARD_STOP)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant_123",
            agent_id="agent_123",
            action="run_episode"
        )

        assert result["allowed"] is False
        assert "halted" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_alert_only_allows(self, budget_service):
        """Test alert_only allows operations even when budget exceeded."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.ALERT_ONLY)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant_123",
            agent_id="agent_123",
            action="run_episode"
        )

        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_check_budget_approval_mode_with_override(self, budget_service):
        """Test approval mode allows operations with a valid override."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.APPROVAL)
        budget_service._get_budget_override = Mock(return_value={"user_id": "admin-1"})
        budget_service._is_override_valid = Mock(return_value=True)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant_123",
            agent_id="agent_123",
            action="run_episode"
        )

        assert result["allowed"] is True
        assert "override" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_approval_mode_without_override(self, budget_service):
        """Test approval mode blocks operations without a valid override."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.APPROVAL)
        budget_service._get_budget_override = Mock(return_value=None)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant_123",
            agent_id="agent_123",
            action="run_episode"
        )

        assert result["allowed"] is False
        assert "approval" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_fail_open_on_spend_error(self, budget_service):
        """Test fail-open when spend cannot be verified."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "error": "Spend aggregation unavailable"
        })

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant_123",
            agent_id="agent_123",
            action="run_episode"
        )

        assert result["allowed"] is True
        assert "unable to verify" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_fleet_aggregate_limit(self, budget_service, default_spend_result):
        """Test fleet aggregate budget limit blocks recruitment."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value=default_spend_result)
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)
        budget_service.spend_service.get_fleet_spend = Mock(return_value=150.0)

        mock_chain = Mock()
        mock_chain.id = "chain_123"
        mock_chain.total_spend_usd = 100.0
        budget_service.db.query.return_value.filter.return_value.first.return_value = mock_chain

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant_123",
            agent_id="agent_123",
            action="recruit",
            chain_id="chain_123"
        )

        assert result["allowed"] is False
        assert "fleet aggregate" in result["reason"].lower()


class TestBudgetValidation:
    """Test budget validation and status calculations."""

    @pytest.mark.asyncio
    async def test_enforce_budget_alert_only(self, budget_service, mock_tenant):
        """Test alert-only mode takes no enforcement action."""
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.ALERT_ONLY)
        budget_service.db.query.return_value.filter.return_value.first.return_value = mock_tenant

        result = await budget_service.enforce_budget(
            tenant_id="tenant_123",
            current_spend=100.0,
            budget_limit=100.0,
            utilization_percent=100.0
        )

        assert result["success"] is True
        assert result["enforcement_mode"] == BudgetEnforcementMode.ALERT_ONLY

    @pytest.mark.asyncio
    async def test_enforce_budget_soft_stop(self, budget_service, mock_tenant):
        """Test soft-stop sends a notification without cancelling episodes."""
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)
        budget_service._send_enforcement_notification = AsyncMock(return_value=True)
        budget_service.db.query.return_value.filter.return_value.first.return_value = mock_tenant

        result = await budget_service.enforce_budget(
            tenant_id="tenant_123",
            current_spend=100.0,
            budget_limit=100.0,
            utilization_percent=100.0
        )

        assert result["success"] is True
        assert result["enforcement_mode"] == BudgetEnforcementMode.SOFT_STOP
        assert "episodes_cancelled" not in result

    @pytest.mark.asyncio
    async def test_enforce_budget_hard_stop_cancels_episodes(self, budget_service, mock_tenant):
        """Test hard-stop cancels active episodes and sends notification."""
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.HARD_STOP)
        budget_service._cancel_active_episodes = Mock(return_value=3)
        budget_service._send_enforcement_notification = AsyncMock(return_value=True)
        budget_service.db.query.return_value.filter.return_value.first.return_value = mock_tenant

        result = await budget_service.enforce_budget(
            tenant_id="tenant_123",
            current_spend=100.0,
            budget_limit=100.0,
            utilization_percent=100.0
        )

        assert result["success"] is True
        assert result["episodes_cancelled"] == 3
        assert result["notification_sent"] is True

    @pytest.mark.asyncio
    async def test_enforce_budget_approval_requests_approval(self, budget_service, mock_tenant):
        """Test approval mode requests admin approval."""
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.APPROVAL)
        budget_service._get_budget_override = Mock(return_value=None)
        budget_service._send_enforcement_notification = AsyncMock(return_value=True)
        budget_service.db.query.return_value.filter.return_value.first.return_value = mock_tenant

        result = await budget_service.enforce_budget(
            tenant_id="tenant_123",
            current_spend=100.0,
            budget_limit=100.0,
            utilization_percent=100.0
        )

        assert result["success"] is True
        assert result["approval_required"] is True

    @pytest.mark.asyncio
    async def test_enforce_budget_tenant_not_found(self, budget_service):
        """Test enforce_budget with nonexistent tenant."""
        budget_service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)
        budget_service.db.query.return_value.filter.return_value.first.return_value = None

        result = await budget_service.enforce_budget(
            tenant_id="nonexistent",
            current_spend=100.0,
            budget_limit=100.0,
            utilization_percent=100.0
        )

        assert result["success"] is False
        assert "not found" in result["error"]


class TestBudgetLimits:
    """Test budget limits and constraints."""

    def test_get_enforcement_mode_from_settings(self, budget_service):
        """Test retrieving enforcement mode from tenant settings."""
        mock_setting = Mock()
        mock_setting.setting_value = json.dumps({
            'enforcement': {'mode': 'hard_stop'}
        })
        budget_service.db.query.return_value.filter.return_value.first.return_value = mock_setting

        mode = budget_service._get_enforcement_mode("tenant_123")

        assert mode == BudgetEnforcementMode.HARD_STOP

    def test_get_enforcement_mode_defaults_to_soft_stop(self, budget_service):
        """Test default enforcement mode is soft_stop when unset."""
        budget_service.db.query.return_value.filter.return_value.first.return_value = None

        mode = budget_service._get_enforcement_mode("tenant_123")

        assert mode == BudgetEnforcementMode.SOFT_STOP

    def test_get_enforcement_mode_invalid_defaults_to_soft_stop(self, budget_service):
        """Test invalid enforcement mode defaults to soft_stop."""
        mock_setting = Mock()
        mock_setting.setting_value = json.dumps({
            'enforcement': {'mode': 'invalid_mode'}
        })
        budget_service.db.query.return_value.filter.return_value.first.return_value = mock_setting

        mode = budget_service._get_enforcement_mode("tenant_123")

        assert mode == BudgetEnforcementMode.SOFT_STOP

    def test_get_budget_override_from_settings(self, budget_service):
        """Test retrieving budget override from tenant settings."""
        override = {
            'user_id': 'admin-001',
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
        mock_setting = Mock()
        mock_setting.setting_value = json.dumps({
            'enforcement': {'override': override}
        })
        budget_service.db.query.return_value.filter.return_value.first.return_value = mock_setting

        result = budget_service._get_budget_override("tenant_123")

        assert result is not None
        assert result['user_id'] == 'admin-001'

    def test_get_budget_override_returns_none(self, budget_service):
        """Test retrieving budget override when none exists."""
        budget_service.db.query.return_value.filter.return_value.first.return_value = None

        result = budget_service._get_budget_override("tenant_123")

        assert result is None

    def test_is_override_valid_with_future_expiry(self, budget_service):
        """Test override is valid when not expired."""
        override = {
            'user_id': 'admin-001',
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }

        assert budget_service._is_override_valid(override) is True

    def test_is_override_valid_with_past_expiry(self, budget_service):
        """Test override is invalid when expired."""
        override = {
            'user_id': 'admin-001',
            'expires_at': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        }

        assert budget_service._is_override_valid(override) is False

    def test_is_override_valid_with_missing_expiry(self, budget_service):
        """Test override is invalid when expiry is missing."""
        override = {'user_id': 'admin-001'}

        assert budget_service._is_override_valid(override) is False

    def test_set_budget_override_creates_new_setting(self, budget_service, mock_tenant):
        """Test setting a budget override creates a TenantSetting row."""
        budget_service.db.query.return_value.filter.return_value.first.side_effect = [mock_tenant, None]
        budget_service.db.flush.return_value = None

        result = budget_service._set_budget_override("tenant_123", "user-001")

        assert result["success"] is True
        assert "expires_at" in result
        budget_service.db.add.assert_called_once()

    def test_set_budget_override_tenant_not_found(self, budget_service):
        """Test setting a budget override for a nonexistent tenant fails."""
        budget_service.db.query.return_value.filter.return_value.first.return_value = None

        result = budget_service._set_budget_override("nonexistent", "user-001")

        assert result["success"] is False
        assert "not found" in result["error"]


class TestBudgetErrors:
    """Test budget error handling and edge cases."""

    def test_error_hierarchy(self):
        """Test budget error class hierarchy."""
        assert issubclass(BudgetError, Exception)
        assert issubclass(InsufficientBudgetError, BudgetError)
        assert issubclass(BudgetNotFoundError, BudgetError)
        assert issubclass(ConcurrentModificationError, BudgetError)

    def test_enforcement_mode_constants(self):
        """Test enforcement mode constants."""
        assert BudgetEnforcementMode.ALERT_ONLY == "alert_only"
        assert BudgetEnforcementMode.SOFT_STOP == "soft_stop"
        assert BudgetEnforcementMode.HARD_STOP == "hard_stop"
        assert BudgetEnforcementMode.APPROVAL == "approval"

    def test_has_active_episodes_true(self, budget_service):
        """Test detecting active episodes for agent."""
        mock_filter = Mock()
        mock_filter.scalar.return_value = 5
        budget_service.db.query.return_value.filter.return_value = mock_filter

        assert budget_service._has_active_episodes("tenant_123", "agent_123") is True

    def test_has_active_episodes_false(self, budget_service):
        """Test detecting no active episodes for agent."""
        mock_filter = Mock()
        mock_filter.scalar.return_value = 0
        budget_service.db.query.return_value.filter.return_value = mock_filter

        assert budget_service._has_active_episodes("tenant_123", "agent_123") is False

    def test_cancel_active_episodes(self, budget_service):
        """Test cancelling all active episodes for tenant."""
        mock_episode1 = Mock()
        mock_episode1.status = "running"
        mock_episode2 = Mock()
        mock_episode2.status = "running"

        mock_filter = Mock()
        mock_filter.all.return_value = [mock_episode1, mock_episode2]
        budget_service.db.query.return_value.filter.return_value = mock_filter

        cancelled_count = budget_service._cancel_active_episodes("tenant_123")

        assert cancelled_count == 2
        assert mock_episode1.status == "cancelled"
        assert mock_episode2.status == "cancelled"

    def test_clear_enforcement_state_removes_override(self, budget_service):
        """Test clearing the enforcement override on billing cycle reset."""
        mock_setting = Mock()
        mock_setting.setting_value = json.dumps({
            'enforcement': {
                'mode': 'hard_stop',
                'override': {'user_id': 'admin-001'}
            }
        })
        budget_service.db.query.return_value.filter.return_value.first.return_value = mock_setting

        budget_service.clear_enforcement_state("tenant_123")

        updated_dict = json.loads(mock_setting.setting_value)
        assert 'override' not in updated_dict.get('enforcement', {})

    def test_clear_enforcement_state_no_setting(self, budget_service):
        """Test clearing enforcement state without an existing setting."""
        budget_service.db.query.return_value.filter.return_value.first.return_value = None

        budget_service.clear_enforcement_state("tenant_123")
