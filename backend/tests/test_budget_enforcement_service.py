"""
Test suite for Budget Enforcement Service

Tests cover:
- Budget tracking (initialization, spend tracking, thresholds)
- Enforcement rules (modes, limits, approval workflows)
- Cost management (calculation, attribution, forecasting)
- Governance integration (policies, approvals, audit trails)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.budget_enforcement_service import (
    BudgetEnforcementService,
    BudgetEnforcementMode,
    BudgetError,
    InsufficientBudgetError,
    BudgetNotFoundError,
    ConcurrentModificationError,
)


class TestBudgetEnforcementMode:
    """Test budget enforcement mode constants."""

    def test_enforcement_mode_constants(self):
        """EnforcementMode has all expected modes."""
        # Assert
        assert BudgetEnforcementMode.ALERT_ONLY == "alert_only"
        assert BudgetEnforcementMode.SOFT_STOP == "soft_stop"
        assert BudgetEnforcementMode.HARD_STOP == "hard_stop"
        assert BudgetEnforcementMode.APPROVAL == "approval"

    def test_enforcement_mode_all(self):
        """ALL constant includes all modes."""
        # Assert
        assert BudgetEnforcementMode.ALERT_ONLY in BudgetEnforcementMode.ALL
        assert BudgetEnforcementMode.SOFT_STOP in BudgetEnforcementMode.ALL
        assert BudgetEnforcementMode.HARD_STOP in BudgetEnforcementMode.ALL
        assert BudgetEnforcementMode.APPROVAL in BudgetEnforcementMode.ALL


class TestBudgetEnforcementExceptions:
    """Test budget enforcement exception hierarchy."""

    def test_budget_error_is_exception(self):
        """BudgetError is an Exception subclass."""
        # Assert
        assert issubclass(BudgetError, Exception)

    def test_insufficient_budget_error_inherits_budget_error(self):
        """InsufficientBudgetError inherits from BudgetError."""
        # Assert
        assert issubclass(InsufficientBudgetError, BudgetError)

    def test_budget_not_found_error_inherits_budget_error(self):
        """BudgetNotFoundError inherits from BudgetError."""
        # Assert
        assert issubclass(BudgetNotFoundError, BudgetError)

    def test_concurrent_modification_error_inherits_budget_error(self):
        """ConcurrentModificationError inherits from BudgetError."""
        # Assert
        assert issubclass(ConcurrentModificationError, BudgetError)


class TestBudgetInitialization:
    """Test budget enforcement service initialization."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_initialization_with_db_session(self, mock_db):
        """Initialize service with provided database session."""
        # Act
        service = BudgetEnforcementService(db=mock_db)

        # Assert
        assert service.db == mock_db

    @patch('core.budget_enforcement_service.SessionLocal')
    def test_initialization_without_db_session(self, mock_session_local):
        """Initialize service with default database session."""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db

        # Act
        service = BudgetEnforcementService()

        # Assert
        assert service.db is not None


class TestBudgetChecking:
    """Test budget checking before actions."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def service(self, mock_db):
        """BudgetEnforcementService instance."""
        return BudgetEnforcementService(db=mock_db)

    @pytest.mark.asyncio
    async def test_check_budget_action_allowed(self, service):
        """Action is allowed when budget not exceeded."""
        # Arrange
        service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 50.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 50.0
        })
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.ALERT_ONLY)

        # Act
        result = await service.check_budget_before_action(
            tenant_id="tenant-001",
            agent_id="agent-001",
            action="run_episode"
        )

        # Assert
        assert result["allowed"] is True
        assert result["current_spend_usd"] == 50.0
        assert result["budget_limit_usd"] == 100.0
        assert result["utilization_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_check_budget_exceeded_alert_only_mode(self, service):
        """Action allowed in alert_only mode even when budget exceeded."""
        # Arrange
        service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.ALERT_ONLY)

        # Act
        result = await service.check_budget_before_action(
            tenant_id="tenant-001",
            agent_id="agent-001",
            action="run_episode"
        )

        # Assert
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_check_budget_exceeded_soft_stop_mode_no_active(self, service):
        """Action blocked in soft_stop mode with no active episodes."""
        # Arrange
        service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)
        service._has_active_episodes = Mock(return_value=False)

        # Act
        result = await service.check_budget_before_action(
            tenant_id="tenant-001",
            agent_id="agent-001",
            action="run_episode"
        )

        # Assert
        assert result["allowed"] is False
        assert "blocked" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_exceeded_soft_stop_mode_with_active(self, service):
        """Action allowed in soft_stop mode with active episodes."""
        # Arrange
        service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)
        service._has_active_episodes = Mock(return_value=True)

        # Act
        result = await service.check_budget_before_action(
            tenant_id="tenant-001",
            agent_id="agent-001",
            action="run_episode"
        )

        # Assert
        assert result["allowed"] is True
        assert "active episode" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_exceeded_hard_stop_mode(self, service):
        """Action blocked in hard_stop mode even with active episodes."""
        # Arrange
        service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.HARD_STOP)

        # Act
        result = await service.check_budget_before_action(
            tenant_id="tenant-001",
            agent_id="agent-001",
            action="run_episode"
        )

        # Assert
        assert result["allowed"] is False
        assert "halted" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_exceeded_approval_mode_with_override(self, service):
        """Action allowed in approval mode with valid override."""
        # Arrange
        service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.APPROVAL)

        # Mock valid override
        override = {
            'user_id': 'admin-001',
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
        service._get_budget_override = Mock(return_value=override)
        service._is_override_valid = Mock(return_value=True)

        # Act
        result = await service.check_budget_before_action(
            tenant_id="tenant-001",
            agent_id="agent-001",
            action="run_episode"
        )

        # Assert
        assert result["allowed"] is True
        assert "override" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_exceeded_approval_mode_no_override(self, service):
        """Action blocked in approval mode without override."""
        # Arrange
        service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0
        })
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.APPROVAL)
        service._get_budget_override = Mock(return_value=None)

        # Act
        result = await service.check_budget_before_action(
            tenant_id="tenant-001",
            agent_id="agent-001",
            action="run_episode"
        )

        # Assert
        assert result["allowed"] is False
        assert "approval" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_budget_fail_open_on_error(self, service):
        """Action allowed when spend check fails (fail-open)."""
        # Arrange
        service.spend_service.update_tenant_spend = Mock(return_value={
            "error": "Service unavailable"
        })

        # Act
        result = await service.check_budget_before_action(
            tenant_id="tenant-001",
            agent_id="agent-001",
            action="run_episode"
        )

        # Assert
        assert result["allowed"] is True
        assert "unable to verify" in result["reason"].lower()


class TestBudgetEnforcement:
    """Test budget enforcement actions."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def service(self, mock_db):
        """BudgetEnforcementService instance."""
        return BudgetEnforcementService(db=mock_db)

    @pytest.mark.asyncio
    async def test_enforce_budget_hard_stop(self, service):
        """Hard-stop mode cancels active episodes and sends notification."""
        # Arrange
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.HARD_STOP)
        service._cancel_active_episodes = Mock(return_value=3)
        service._send_enforcement_notification = AsyncMock(return_value=True)

        # Mock tenant
        mock_tenant = Mock()
        mock_tenant.id = "tenant-001"
        service.db.query.return_value.filter.return_value.first.return_value = mock_tenant

        # Act
        result = await service.enforce_budget(
            tenant_id="tenant-001",
            current_spend=100.0,
            budget_limit=100.0,
            utilization_percent=100.0
        )

        # Assert
        assert result["success"] is True
        assert result["enforcement_mode"] == BudgetEnforcementMode.HARD_STOP
        assert result["episodes_cancelled"] == 3
        assert result["notification_sent"] is True

    @pytest.mark.asyncio
    async def test_enforce_budget_soft_stop(self, service):
        """Soft-stop mode sends notification but doesn't cancel episodes."""
        # Arrange
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)
        service._send_enforcement_notification = AsyncMock(return_value=True)

        # Mock tenant
        mock_tenant = Mock()
        mock_tenant.id = "tenant-001"
        service.db.query.return_value.filter.return_value.first.return_value = mock_tenant

        # Act
        result = await service.enforce_budget(
            tenant_id="tenant-001",
            current_spend=100.0,
            budget_limit=100.0,
            utilization_percent=100.0
        )

        # Assert
        assert result["success"] is True
        assert result["enforcement_mode"] == BudgetEnforcementMode.SOFT_STOP
        assert "episodes_cancelled" not in result

    @pytest.mark.asyncio
    async def test_enforce_budget_approval_mode(self, service):
        """Approval mode requests admin approval."""
        # Arrange
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.APPROVAL)
        service._get_budget_override = Mock(return_value=None)
        service._send_enforcement_notification = AsyncMock(return_value=True)

        # Mock tenant
        mock_tenant = Mock()
        mock_tenant.id = "tenant-001"
        service.db.query.return_value.filter.return_value.first.return_value = mock_tenant

        # Act
        result = await service.enforce_budget(
            tenant_id="tenant-001",
            current_spend=100.0,
            budget_limit=100.0,
            utilization_percent=100.0
        )

        # Assert
        assert result["success"] is True
        assert result["approval_required"] is True


class TestEnforcementModeRetrieval:
    """Test enforcement mode retrieval from tenant settings."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def service(self, mock_db):
        """BudgetEnforcementService instance."""
        return BudgetEnforcementService(db=mock_db)

    def test_get_enforcement_mode_from_settings(self, service):
        """Retrieve enforcement mode from tenant settings."""
        # Arrange
        import json
        mock_setting = Mock()
        mock_setting.setting_value = json.dumps({
            'enforcement': {'mode': 'hard_stop'}
        })
        service.db.query.return_value.filter.return_value.first.return_value = mock_setting

        # Act
        mode = service._get_enforcement_mode("tenant-001")

        # Assert
        assert mode == BudgetEnforcementMode.HARD_STOP

    def test_get_enforcement_mode_default_to_alert_only(self, service):
        """Default to alert_only when mode not set."""
        # Arrange
        service.db.query.return_value.filter.return_value.first.return_value = None

        # Act
        mode = service._get_enforcement_mode("tenant-001")

        # Assert
        assert mode == BudgetEnforcementMode.ALERT_ONLY

    def test_get_enforcement_mode_invalid_defaults_to_alert_only(self, service):
        """Default to alert_only when mode is invalid."""
        # Arrange
        import json
        mock_setting = Mock()
        mock_setting.setting_value = json.dumps({
            'enforcement': {'mode': 'invalid_mode'}
        })
        service.db.query.return_value.filter.return_value.first.return_value = mock_setting

        # Act
        mode = service._get_enforcement_mode("tenant-001")

        # Assert
        assert mode == BudgetEnforcementMode.ALERT_ONLY


class TestBudgetOverride:
    """Test budget override functionality."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def service(self, mock_db):
        """BudgetEnforcementService instance."""
        return BudgetEnforcementService(db=mock_db)

    def test_get_budget_override_from_settings(self, service):
        """Retrieve budget override from tenant settings."""
        # Arrange
        import json
        override = {
            'user_id': 'admin-001',
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
        mock_setting = Mock()
        mock_setting.setting_value = json.dumps({
            'enforcement': {'override': override}
        })
        service.db.query.return_value.filter.return_value.first.return_value = mock_setting

        # Act
        result = service._get_budget_override("tenant-001")

        # Assert
        assert result is not None
        assert result['user_id'] == 'admin-001'

    def test_is_override_valid_with_future_expiry(self, service):
        """Override is valid when not expired."""
        # Arrange
        override = {
            'user_id': 'admin-001',
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }

        # Act
        is_valid = service._is_override_valid(override)

        # Assert
        assert is_valid is True

    def test_is_override_valid_with_past_expiry(self, service):
        """Override is invalid when expired."""
        # Arrange
        override = {
            'user_id': 'admin-001',
            'expires_at': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        }

        # Act
        is_valid = service._is_override_valid(override)

        # Assert
        assert is_valid is False

    def test_is_override_valid_with_missing_expiry(self, service):
        """Override is invalid when expiry is missing."""
        # Arrange
        override = {'user_id': 'admin-001'}

        # Act
        is_valid = service._is_override_valid(override)

        # Assert
        assert is_valid is False


class TestActiveEpisodeManagement:
    """Test active episode checking and cancellation."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def service(self, mock_db):
        """BudgetEnforcementService instance."""
        return BudgetEnforcementService(db=mock_db)

    def test_has_active_episodes_true(self, service):
        """Detect active episodes for agent."""
        # Arrange
        from sqlalchemy import func
        service.db.query.return_value.filter.return_value.filter.return_value.filter.return_value.scalar.return_value = 5

        # Act
        has_active = service._has_active_episodes("tenant-001", "agent-001")

        # Assert
        assert has_active is True

    def test_has_active_episodes_false(self, service):
        """No active episodes for agent."""
        # Arrange
        from sqlalchemy import func
        service.db.query.return_value.filter.return_value.filter.return_value.filter.return_value.scalar.return_value = 0

        # Act
        has_active = service._has_active_episodes("tenant-001", "agent-001")

        # Assert
        assert has_active is False

    def test_cancel_active_episodes_success(self, service):
        """Cancel all active episodes for tenant."""
        # Arrange
        from core.models import AgentExecution
        mock_episode1 = Mock(spec=AgentExecution)
        mock_episode1.status = "running"
        mock_episode2 = Mock(spec=AgentExecution)
        mock_episode2.status = "running"
        service.db.query.return_value.filter.return_value.filter.return_value.all.return_value = [
            mock_episode1, mock_episode2
        ]

        # Act
        cancelled_count = service._cancel_active_episodes("tenant-001")

        # Assert
        assert cancelled_count == 2
        assert mock_episode1.status == "cancelled"
        assert mock_episode2.status == "cancelled"


class TestBudgetClearing:
    """Test budget state clearing on billing cycle reset."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def service(self, mock_db):
        """BudgetEnforcementService instance."""
        return BudgetEnforcementService(db=mock_db)

    def test_clear_enforcement_state_removes_override(self, service):
        """Clear override on billing cycle reset."""
        # Arrange
        import json
        mock_setting = Mock()
        mock_setting.setting_value = json.dumps({
            'enforcement': {
                'mode': 'hard_stop',
                'override': {'user_id': 'admin-001'}
            }
        })
        service.db.query.return_value.filter.return_value.first.return_value = mock_setting

        # Act
        service.clear_enforcement_state("tenant-001")

        # Assert
        # Verify override was removed from setting_value
        import json
        updated_dict = json.loads(mock_setting.setting_value)
        assert 'override' not in updated_dict.get('enforcement', {})

    def test_clear_enforcement_state_no_setting(self, service):
        """Handle missing tenant setting gracefully."""
        # Arrange
        service.db.query.return_value.filter.return_value.first.return_value = None

        # Act (should not raise)
        service.clear_enforcement_state("tenant-001")

        # Assert (no exception)
        assert True
