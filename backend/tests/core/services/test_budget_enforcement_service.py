"""
Tests for BudgetEnforcementService

The service was rewritten from a project-level spend-approval API
(check_budget/approve_spend/record_spend/get_budget_status on
service_delivery Projects) into a tenant-level enforcement wrapper:
- check_budget_before_action(tenant_id, agent_id, action, chain_id)
    gate called before each agent action; consults
    SpendAggregationService and the tenant's configured enforcement mode.
- enforce_budget(tenant_id, ...) — actions taken once utilization >= 100%
    (cancel episodes on hard_stop, notify, request approval).
- Admin approval flow via billing settings override
    (_set_budget_override / _is_override_valid / clear_enforcement_state).

These tests port the intent of the original suite (budget gating, approval,
enforcement actions, locking/override lifecycle, error types, edge cases)
onto that current API.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from core.budget_enforcement_service import (
    BudgetEnforcementService,
    BudgetEnforcementMode,
    BudgetError,
    BudgetNotFoundError,
    ConcurrentModificationError,
    InsufficientBudgetError,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def budget_service(mock_db):
    """Create budget enforcement service instance."""
    return BudgetEnforcementService(db=mock_db)


class TestBudgetEnforcementServiceInit:
    """Tests for BudgetEnforcementService initialization."""

    def test_init_with_db(self, budget_service, mock_db):
        """Test initialization with database session."""
        assert budget_service.db == mock_db

    def test_context_manager_closes_db(self, budget_service, mock_db):
        """Test the context-manager protocol closes the session on exit."""
        with budget_service as svc:
            assert svc is budget_service
        mock_db.close.assert_called_once()

    def test_close_closes_db(self, budget_service, mock_db):
        """Test explicit close() releases the session."""
        budget_service.close()
        mock_db.close.assert_called_once()


class TestCheckBudget:
    """Tests for check_budget_before_action (the budget gate)."""

    def _spend(self, current=50.0, limit=100.0, utilization=50.0):
        return {
            "current_spend_usd": current,
            "budget_limit_usd": limit,
            "utilization_percent": utilization,
        }

    @pytest.mark.asyncio
    async def test_check_budget_within_limit(self, budget_service):
        """Test checking budget that is within limit."""
        budget_service.spend_service.update_tenant_spend = Mock(
            return_value=self._spend()
        )
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is True
        assert result["reason"] is None
        assert result["current_spend_usd"] == 50.0
        assert result["budget_limit_usd"] == 100.0
        assert result["utilization_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_check_budget_exceeds_limit(self, budget_service):
        """Test checking budget that exceeds limit (soft stop default)."""
        budget_service.spend_service.update_tenant_spend = Mock(
            return_value=self._spend(current=120.0, utilization=120.0)
        )
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )
        budget_service._has_active_episodes = Mock(return_value=False)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is False
        assert "Budget exceeded" in result["reason"]
        assert result["enforcement_mode"] == BudgetEnforcementMode.SOFT_STOP

    @pytest.mark.asyncio
    async def test_check_budget_fractional_amounts_propagate(self, budget_service):
        """Spend figures pass through unrounded (was: Decimal amounts)."""
        budget_service.spend_service.update_tenant_spend = Mock(
            return_value=self._spend(current=50.25, limit=100.50, utilization=49.9)
        )
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.ALERT_ONLY
        )

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="tool_call"
        )

        assert result["allowed"] is True
        assert result["current_spend_usd"] == 50.25
        assert result["budget_limit_usd"] == 100.50

    @pytest.mark.asyncio
    async def test_check_budget_fleet_aggregate_limit(self, budget_service):
        """Fleet (delegation-chain) aggregate cap blocks the action
        (was: string-amount handling — numeric accounting beyond tenant spend)."""
        budget_service.spend_service.update_tenant_spend = Mock(
            return_value=self._spend()
        )
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )
        chain = Mock()
        chain.total_spend_usd = 50.0
        budget_service.db.query.return_value.filter.return_value.first.return_value = chain
        budget_service.spend_service.get_fleet_spend = Mock(return_value=60.0)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1",
            agent_id="agent-1",
            action="spawn_agent",
            chain_id="chain-1",
        )

        assert result["allowed"] is False
        assert "Fleet aggregate budget limit" in result["reason"]
        assert result["budget_limit_usd"] == 50.0

    @pytest.mark.asyncio
    async def test_check_budget_fail_open_on_spend_error(self, budget_service):
        """Spend aggregation erroring fails open (was: negative amount guard)."""
        budget_service.spend_service.update_tenant_spend = Mock(
            return_value={"error": "aggregation unavailable"}
        )

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is True
        assert result["reason"] == "Unable to verify spend"
        assert result["enforcement_mode"] == "unknown"

    @pytest.mark.asyncio
    async def test_check_budget_unexpected_exception_fails_open(self, budget_service):
        """Unexpected internal errors fail open rather than blocking (was:
        budget-not-found raising BudgetNotFoundError)."""
        budget_service.spend_service.update_tenant_spend = Mock(
            side_effect=RuntimeError("db exploded")
        )

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is True
        assert result["reason"] == "Unable to verify spend"

    @pytest.mark.asyncio
    async def test_check_budget_utilization_boundary(self, budget_service):
        """Utilization of exactly 100% counts as exceeded."""
        budget_service.spend_service.update_tenant_spend = Mock(
            return_value=self._spend(current=100.0, utilization=100.0)
        )
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.HARD_STOP
        )

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is False
        assert result["utilization_percent"] == 100.0


class TestApproveSpend:
    """Admin approval flow (approval mode + override) — was approve_spend."""

    def _exceeded_spend(self):
        return {
            "current_spend_usd": 150.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 150.0,
        }

    @pytest.mark.asyncio
    async def test_approval_mode_with_valid_override_allows(self, budget_service):
        """Valid admin override approves continued spend."""
        budget_service.spend_service.update_tenant_spend = Mock(
            return_value=self._exceeded_spend()
        )
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.APPROVAL
        )
        budget_service._get_budget_override = Mock(return_value={
            "user_id": "admin-1",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        })

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is True
        assert result["reason"] == "Admin override approved"

    @pytest.mark.asyncio
    async def test_approval_mode_without_override_blocks(self, budget_service):
        """No override in approval mode blocks the spend (was: insufficient)."""
        budget_service.spend_service.update_tenant_spend = Mock(
            return_value=self._exceeded_spend()
        )
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.APPROVAL
        )
        budget_service._get_budget_override = Mock(return_value=None)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is False
        assert "approval required" in result["reason"].lower()

    def test_set_budget_override_tenant_not_found(self, budget_service):
        """Override for a missing tenant fails cleanly (was: not-found raise)."""
        budget_service.db.query.return_value.filter.return_value.first.return_value = None

        result = budget_service._set_budget_override("ghost-tenant", "admin-1")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_set_budget_override_persists_setting(self, budget_service):
        """Override is persisted into the billing setting with 1h expiry
        (was: approve_spend updating remaining budget)."""
        tenant = Mock()
        tenant.id = "tenant-1"
        existing_setting = Mock()
        existing_setting.setting_value = json.dumps({"enforcement": {"mode": "approval"}})
        budget_service.db.query.return_value.filter.return_value.first.side_effect = [
            tenant,
            existing_setting,
        ]

        result = budget_service._set_budget_override("tenant-1", "admin-1")

        assert result["success"] is True
        expires_at = datetime.fromisoformat(result["expires_at"])
        assert expires_at > datetime.now(timezone.utc)
        assert expires_at - datetime.now(timezone.utc) <= timedelta(hours=1)
        stored = json.loads(existing_setting.setting_value)
        assert stored["enforcement"]["override"]["user_id"] == "admin-1"
        budget_service.db.flush.assert_called()

    def test_set_budget_override_rollback_on_error(self, budget_service):
        """DB failure during override write rolls back (was: rollback test)."""
        tenant = Mock()
        tenant.id = "tenant-1"
        budget_service.db.query.return_value.filter.return_value.first.return_value = tenant
        with patch.object(
            budget_service.db, "flush", side_effect=Exception("DB error")
        ):
            result = budget_service._set_budget_override("tenant-1", "admin-1")

        assert result["success"] is False
        assert "DB error" in result["error"]
        budget_service.db.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_approval_mode_expired_override_blocks(self, budget_service):
        """An expired override no longer approves spend (was: negative amount)."""
        budget_service.spend_service.update_tenant_spend = Mock(
            return_value=self._exceeded_spend()
        )
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.APPROVAL
        )
        budget_service._get_budget_override = Mock(return_value={
            "user_id": "admin-1",
            "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        })

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is False
        assert "approval required" in result["reason"].lower()


class TestRecordSpend:
    """Enforcement actions once the budget is exceeded — was record_spend."""

    @pytest.mark.asyncio
    async def test_enforce_budget_soft_stop_notifies(self, budget_service):
        """Soft stop sends an enforcement notification (was: success record)."""
        tenant = Mock()
        budget_service.db.query.return_value.filter.return_value.first.return_value = tenant
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )
        budget_service._send_enforcement_notification = AsyncMock(return_value=True)

        result = await budget_service.enforce_budget("tenant-1", 150.0, 100.0, 150.0)

        assert result["success"] is True
        assert result["notification_sent"] is True
        budget_service._send_enforcement_notification.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enforce_budget_hard_stop_cancels_episodes(self, budget_service):
        """Hard stop cancels active episodes and reports the count
        (was: record_spend creating a transaction)."""
        tenant = Mock()
        budget_service.db.query.return_value.filter.return_value.first.return_value = tenant
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.HARD_STOP
        )
        budget_service._cancel_active_episodes = Mock(return_value=3)
        budget_service._send_enforcement_notification = AsyncMock(return_value=True)

        result = await budget_service.enforce_budget("tenant-1", 150.0, 100.0, 150.0)

        assert result["success"] is True
        assert result["episodes_cancelled"] == 3
        budget_service._cancel_active_episodes.assert_called_once_with("tenant-1")

    @pytest.mark.asyncio
    async def test_enforce_budget_alert_only_takes_no_action(self, budget_service):
        """Alert-only mode enforces nothing (was: insufficient-budget raise)."""
        tenant = Mock()
        budget_service.db.query.return_value.filter.return_value.first.return_value = tenant
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.ALERT_ONLY
        )
        budget_service._send_enforcement_notification = AsyncMock(return_value=True)

        result = await budget_service.enforce_budget("tenant-1", 150.0, 100.0, 150.0)

        assert result["success"] is True
        assert result["enforcement_action"] == "none"
        budget_service._send_enforcement_notification.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enforce_budget_tenant_not_found(self, budget_service):
        """Enforcement for an unknown tenant reports failure."""
        budget_service.db.query.return_value.filter.return_value.first.return_value = None

        result = await budget_service.enforce_budget("ghost", 150.0, 100.0, 150.0)

        assert result["success"] is False
        assert "not found" in result["error"]


class TestGetBudgetStatus:
    """Enforcement-mode retrieval from tenant settings — was get_budget_status."""

    def test_get_enforcement_mode_reads_setting(self, budget_service):
        """Mode is read from the billing tenant setting."""
        setting = Mock()
        setting.setting_value = json.dumps(
            {"enforcement": {"mode": BudgetEnforcementMode.HARD_STOP}}
        )
        budget_service.db.query.return_value.filter.return_value.first.return_value = setting

        mode = budget_service._get_enforcement_mode("tenant-1")

        assert mode == BudgetEnforcementMode.HARD_STOP

    def test_get_enforcement_mode_defaults_to_soft_stop(self, budget_service):
        """Unset (or invalid) settings default to soft_stop."""
        budget_service.db.query.return_value.filter.return_value.first.return_value = None
        assert budget_service._get_enforcement_mode("tenant-1") == BudgetEnforcementMode.SOFT_STOP

        setting = Mock()
        setting.setting_value = json.dumps({"enforcement": {"mode": "bogus"}})
        budget_service.db.query.return_value.filter.return_value.first.return_value = setting
        assert budget_service._get_enforcement_mode("tenant-1") == BudgetEnforcementMode.SOFT_STOP

    def test_get_enforcement_mode_malformed_json_defaults(self, budget_service):
        """Malformed setting JSON falls back to the safe default."""
        setting = Mock()
        setting.setting_value = "{not json"
        budget_service.db.query.return_value.filter.return_value.first.return_value = setting

        assert budget_service._get_enforcement_mode("tenant-1") == BudgetEnforcementMode.SOFT_STOP


class TestApproveSpendLocked:
    """Active-episode gating under soft stop — was pessimistic locking."""

    @pytest.mark.asyncio
    async def test_active_episode_allowed_to_complete(self, budget_service):
        """Soft stop lets an agent with a running episode finish it."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 150.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 150.0,
        })
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )
        budget_service._has_active_episodes = Mock(return_value=True)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is True
        assert result["reason"] == "Active episode allowed to complete"

    @pytest.mark.asyncio
    async def test_no_active_episode_blocked(self, budget_service):
        """Soft stop blocks new episodes once the budget is exceeded."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 150.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 150.0,
        })
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )
        budget_service._has_active_episodes = Mock(return_value=False)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )

        assert result["allowed"] is False

    def test_has_active_episodes_db_error_fails_closed_to_no_active(self, budget_service):
        """A DB error while counting episodes is reported as 'no active'
        (conservative for new-episode gating) — was: lock-error rollback."""
        budget_service.db.query.return_value.filter.return_value.scalar.side_effect = (
            Exception("lock timeout")
        )

        assert budget_service._has_active_episodes("tenant-1", "agent-1") is False

    def test_has_active_episodes_counts_running(self, budget_service):
        """Count of running episodes drives the answer."""
        budget_service.db.query.return_value.filter.return_value.scalar.return_value = 2
        assert budget_service._has_active_episodes("tenant-1", "agent-1") is True

        budget_service.db.query.return_value.filter.return_value.scalar.return_value = 0
        assert budget_service._has_active_episodes("tenant-1", "agent-1") is False


class TestApproveSpendWithRetry:
    """Override validity lifecycle — was optimistic locking retries."""

    def test_override_with_future_expiry_valid(self, budget_service):
        """A future expiry keeps the override valid (was: retry success)."""
        override = {
            "user_id": "admin-1",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }
        assert budget_service._is_override_valid(override) is True

    def test_override_with_past_expiry_invalid(self, budget_service):
        """An expired override is rejected (was: insufficient)."""
        override = {
            "user_id": "admin-1",
            "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        assert budget_service._is_override_valid(override) is False

    def test_override_missing_or_malformed_expiry_invalid(self, budget_service):
        """Overrides without a parseable expiry never approve (was: StaleDataError
        concurrent-modification retry)."""
        assert budget_service._is_override_valid({}) is False
        assert budget_service._is_override_valid({"expires_at": "not-a-date"}) is False
        assert budget_service._is_override_valid(None) is False

    def test_clear_enforcement_state_removes_override(self, budget_service):
        """Billing-cycle reset clears the override (was: max-retries exceeded)."""
        setting = Mock()
        setting.setting_value = json.dumps({
            "enforcement": {
                "mode": "approval",
                "override": {"user_id": "admin-1"},
            }
        })
        budget_service.db.query.return_value.filter.return_value.first.return_value = setting

        budget_service.clear_enforcement_state("tenant-1")

        stored = json.loads(setting.setting_value)
        assert "override" not in stored["enforcement"]
        assert stored["enforcement"]["mode"] == "approval"  # rest preserved
        budget_service.db.flush.assert_called()

    def test_clear_enforcement_state_without_override_noop(self, budget_service):
        """Nothing to clear when no override exists."""
        setting = Mock()
        setting.setting_value = json.dumps({"enforcement": {"mode": "approval"}})
        budget_service.db.query.return_value.filter.return_value.first.return_value = setting

        budget_service.clear_enforcement_state("tenant-1")

        budget_service.db.flush.assert_not_called()


class TestBudgetErrors:
    """Tests for budget exception classes."""

    def test_insufficient_budget_error(self):
        """InsufficientBudgetError is a raisable BudgetError."""
        error = InsufficientBudgetError("Requested 100.0 but only 50.0 remaining")
        assert isinstance(error, BudgetError)
        assert "100" in str(error)
        assert "50" in str(error)

    def test_budget_not_found_error(self):
        """BudgetNotFoundError is a raisable BudgetError."""
        error = BudgetNotFoundError("Tenant budget not found")
        assert isinstance(error, BudgetError)
        assert "not found" in str(error)

    def test_concurrent_modification_error(self):
        """ConcurrentModificationError is a raisable BudgetError."""
        error = ConcurrentModificationError("Concurrent update detected")
        assert isinstance(error, BudgetError)
        assert "Concurrent update" in str(error)


class TestBudgetStatusTransitions:
    """Behavior per enforcement mode once exceeded — was status transitions."""

    def _exceeded(self, budget_service):
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 150.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 150.0,
        })

    @pytest.mark.asyncio
    async def test_alert_only_still_allows(self, budget_service):
        """Alert-only never blocks (was: stay ON_TRACK)."""
        self._exceeded(budget_service)
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.ALERT_ONLY
        )

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_hard_stop_blocks_everything(self, budget_service):
        """Hard stop halts all operations (was: transition to OVER_BUDGET)."""
        self._exceeded(budget_service)
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.HARD_STOP
        )

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )
        assert result["allowed"] is False
        assert "halted" in result["reason"]

    @pytest.mark.asyncio
    async def test_soft_stop_blocks_new_episodes(self, budget_service):
        """Soft stop blocks new episodes with a clear reason (was: AT_RISK)."""
        self._exceeded(budget_service)
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )
        budget_service._has_active_episodes = Mock(return_value=False)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )
        assert result["allowed"] is False
        assert "New episodes blocked" in result["reason"]


class TestEdgeCases:
    """Tests for edge cases around the exceed boundary."""

    @pytest.mark.asyncio
    async def test_zero_budget_means_unconfigured_allows(self, budget_service):
        """Zero limit = 'no budget configured' = unlimited (deliberate): the
        old contract read 0.0 as a real limit and blocked every new agent
        episode on fresh installs the moment any spend existed."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 0.0,
            "budget_limit_usd": 0.0,
            "utilization_percent": 0.0,
        })
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )
        budget_service._has_active_episodes = Mock(return_value=False)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_zero_remaining_blocks(self, budget_service):
        """Spend at exactly the limit is exceeded (>= comparison)."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 99.9,
        })
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )
        budget_service._has_active_episodes = Mock(return_value=False)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_just_under_limit_allowed(self, budget_service):
        """Spend just below the limit is allowed (was: exact-match boundary)."""
        budget_service.spend_service.update_tenant_spend = Mock(return_value={
            "current_spend_usd": 99.99,
            "budget_limit_usd": 100.0,
            "utilization_percent": 99.99,
        })
        budget_service._get_enforcement_mode = Mock(
            return_value=BudgetEnforcementMode.SOFT_STOP
        )
        budget_service._has_active_episodes = Mock(return_value=False)

        result = await budget_service.check_budget_before_action(
            tenant_id="tenant-1", agent_id="agent-1", action="llm_call"
        )
        assert result["allowed"] is True
