"""
EXTENSION coverage tests for core/budget_enforcement_service.py.

The existing tests/core/test_budget_enforcement_coverage.py already covers the
core enforcement modes and helpers but MOCKS _send_enforcement_notification and
skips many error/edge branches. This file covers the gaps:
- _send_enforcement_notification (full implementation: admin users, workspace,
  notification dispatch, fallbacks, exception swallow)
- check_budget_before_action: fail-open spend-error path, fleet aggregate edge,
  unknown enforcement mode default-fail-open
- enforce_budget: approval-mode override-active short-circuit, ALERT_ONLY path,
  generic exception path
- _get_enforcement_mode / _get_budget_override: JSONDecodeError branches
- _is_override_valid: invalid datetime, falsy override, None expiry
- _set_budget_override: existing-setting update path, rollback on error
- _has_active_episodes / _cancel_active_episodes: exception paths
- clear_enforcement_state: no override / exception paths
- close() / __exit__ behavior
"""
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from core.budget_enforcement_service import (
    BudgetEnforcementMode,
    BudgetEnforcementService,
    BudgetError,
    BudgetNotFoundError,
    ConcurrentModificationError,
    InsufficientBudgetError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def service(mock_db):
    return BudgetEnforcementService(db=mock_db)


def _make_tenant(tid="tenant_123"):
    t = Mock()
    t.id = tid
    return t


def _make_user(uid="user-1", role="admin"):
    u = Mock()
    u.id = uid
    u.role = role
    return u


def _make_setting(value_dict):
    s = Mock()
    s.setting_value = json.dumps(value_dict)
    s.tenant_id = "tenant_123"
    s.setting_key = "billing"
    return s


# ---------------------------------------------------------------------------
# _send_enforcement_notification (full implementation)
# ---------------------------------------------------------------------------
class TestSendEnforcementNotification:
    @pytest.mark.asyncio
    async def test_sends_to_admin_users(self, service, mock_db):
        admin = _make_user("u1", "admin")
        workspace = Mock()
        workspace.id = "ws-1"

        mock_db.query.return_value.filter.return_value.all.return_value = [admin]
        # second query (workspace) returns the workspace
        mock_db.query.return_value.filter.return_value.first.return_value = workspace

        service.notification_service.send_notification = AsyncMock()

        result = await service._send_enforcement_notification(
            tenant_id="tenant_123",
            mode=BudgetEnforcementMode.SOFT_STOP,
            current_spend=120.0,
            budget_limit=100.0,
            utilization_percent=120.0,
            details="blocked",
        )
        assert result is True
        service.notification_service.send_notification.assert_awaited_once()
        # verify payload shape
        args = service.notification_service.send_notification.await_args
        assert args.args[0] == "u1"
        assert args.args[1] == "budget_enforcement"
        assert args.args[2]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_falls_back_to_any_tenant_user_when_no_admins(self, service, mock_db):
        regular = _make_user("u2", "member")
        workspace = Mock()
        workspace.id = "ws-1"

        # First .all() (admin query) -> [] ; Second .all() (fallback) -> [regular]
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [regular]
        mock_db.query.return_value.filter.return_value.first.return_value = workspace

        service.notification_service.send_notification = AsyncMock()
        result = await service._send_enforcement_notification(
            "tenant_123", BudgetEnforcementMode.HARD_STOP, 100, 100, 100, "x"
        )
        assert result is True
        service.notification_service.send_notification.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_no_users(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
        result = await service._send_enforcement_notification(
            "tenant_123", BudgetEnforcementMode.HARD_STOP, 100, 100, 100, "x"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_workspace(self, service, mock_db):
        admin = _make_user()
        mock_db.query.return_value.filter.return_value.all.return_value = [admin]
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = await service._send_enforcement_notification(
            "tenant_123", BudgetEnforcementMode.HARD_STOP, 100, 100, 100, "x"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self, service, mock_db):
        mock_db.query.side_effect = RuntimeError("db down")
        result = await service._send_enforcement_notification(
            "tenant_123", BudgetEnforcementMode.HARD_STOP, 100, 100, 100, "x"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_admin_query_exception_falls_back(self, service, mock_db):
        """The inner try/except around admin user query yields [] -> fallback."""
        workspace = Mock()
        workspace.id = "ws-1"
        regular = _make_user("u-fb", "member")

        # Configure the chained calls so the FIRST all() raises, then fallback all() works
        chain = mock_db.query.return_value.filter.return_value
        chain.all.side_effect = [RuntimeError("admin query boom"), [regular]]
        chain.limit.return_value.all.return_value = [regular]
        chain.first.return_value = workspace

        service.notification_service.send_notification = AsyncMock()
        result = await service._send_enforcement_notification(
            "tenant_123", BudgetEnforcementMode.HARD_STOP, 100, 100, 100, "x"
        )
        assert result is True


# ---------------------------------------------------------------------------
# enforce_budget edge cases
# ---------------------------------------------------------------------------
class TestEnforceBudgetEdges:
    @pytest.mark.asyncio
    async def test_approval_mode_override_active_short_circuits(self, service, mock_db):
        tenant = _make_tenant()
        mock_db.query.return_value.filter.return_value.first.return_value = tenant
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.APPROVAL)
        service._get_budget_override = Mock(return_value={"expires_at": "2099-01-01T00:00:00+00:00"})
        service._is_override_valid = Mock(return_value=True)

        result = await service.enforce_budget("tenant_123", 100, 100, 100)
        assert result["success"] is True
        assert result["override_active"] is True

    @pytest.mark.asyncio
    async def test_approval_mode_no_override_sends_notification(self, service, mock_db):
        tenant = _make_tenant()
        mock_db.query.return_value.filter.return_value.first.return_value = tenant
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.APPROVAL)
        service._get_budget_override = Mock(return_value=None)
        service._send_enforcement_notification = AsyncMock(return_value=True)

        result = await service.enforce_budget("tenant_123", 100, 100, 100)
        assert result["success"] is True
        assert result["approval_required"] is True
        service._send_enforcement_notification.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_alert_only_mode(self, service, mock_db):
        tenant = _make_tenant()
        mock_db.query.return_value.filter.return_value.first.return_value = tenant
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.ALERT_ONLY)

        result = await service.enforce_budget("tenant_123", 100, 100, 100)
        assert result["success"] is True
        assert result["enforcement_action"] == "none"

    @pytest.mark.asyncio
    async def test_hard_stop_cancels_and_notifies(self, service, mock_db):
        tenant = _make_tenant()
        mock_db.query.return_value.filter.return_value.first.return_value = tenant
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.HARD_STOP)
        service._cancel_active_episodes = Mock(return_value=3)
        service._send_enforcement_notification = AsyncMock(return_value=True)

        result = await service.enforce_budget("tenant_123", 100, 100, 100)
        assert result["success"] is True
        assert result["episodes_cancelled"] == 3
        assert result["notification_sent"] is True

    @pytest.mark.asyncio
    async def test_soft_stop_notifies(self, service, mock_db):
        tenant = _make_tenant()
        mock_db.query.return_value.filter.return_value.first.return_value = tenant
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)
        service._send_enforcement_notification = AsyncMock(return_value=True)

        result = await service.enforce_budget("tenant_123", 100, 100, 100)
        assert result["success"] is True
        assert result["notification_sent"] is True

    @pytest.mark.asyncio
    async def test_enforce_budget_generic_exception_returns_error(self, service, mock_db):
        service._get_enforcement_mode = Mock(side_effect=RuntimeError("unexpected"))
        result = await service.enforce_budget("tenant_123", 100, 100, 100)
        assert result["success"] is False
        assert "unexpected" in result["error"]


# ---------------------------------------------------------------------------
# check_budget_before_action edge cases
# ---------------------------------------------------------------------------
class TestCheckBudgetEdges:
    @pytest.mark.asyncio
    async def test_spend_error_in_result_fail_open(self, service, mock_db):
        service.spend_service.update_tenant_spend = Mock(
            return_value={"error": "spend service unavailable"}
        )
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is True
        assert result["reason"] == "Unable to verify spend"
        assert result["enforcement_mode"] == "unknown"

    @pytest.mark.asyncio
    async def test_unknown_enforcement_mode_defaults_fail_open(self, service, mock_db):
        """check_budget_before_action's final return (default fail-open) when
        enforcement mode is somehow not one of the known modes AND budget
        is exceeded."""
        service.spend_service.update_tenant_spend = Mock(
            return_value={"current_spend_usd": 200.0, "budget_limit_usd": 100.0,
                          "utilization_percent": 200.0}
        )
        service._get_enforcement_mode = Mock(return_value="bogus_mode")
        result = await service.check_budget_before_action("t1", "a1", "act")
        # falls through to default fail-open
        assert result["allowed"] is True
        assert result["enforcement_mode"] == "bogus_mode"

    @pytest.mark.asyncio
    async def test_fleet_aggregate_within_limit(self, service, mock_db):
        """chain_id present, fleet limit set but spend below limit -> allowed."""
        service.spend_service.update_tenant_spend = Mock(
            return_value={"current_spend_usd": 50.0, "budget_limit_usd": 100.0,
                          "utilization_percent": 50.0}
        )
        service._get_enforcement_mode = Mock(return_value=BudgetEnforcementMode.SOFT_STOP)

        chain = Mock()
        chain.total_spend_usd = 100.0
        # query(Tenant) ... but we patch DelegationChain query
        with patch("core.models.DelegationChain") as DC:
            mock_db.query.return_value.filter.return_value.first.return_value = chain
            service.spend_service.get_fleet_spend = Mock(return_value=10.0)
            result = await service.check_budget_before_action(
                "t1", "a1", "act", chain_id="chain-1"
            )
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_generic_exception_fail_open(self, service, mock_db):
        service.spend_service.update_tenant_spend = Mock(side_effect=RuntimeError("boom"))
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is True
        assert result["enforcement_mode"] == "unknown"


# ---------------------------------------------------------------------------
# _get_enforcement_mode / _get_budget_override error branches
# ---------------------------------------------------------------------------
class TestModeAndOverrideErrors:
    def test_get_enforcement_mode_invalid_json(self, service, mock_db):
        bad = Mock()
        bad.setting_value = "not valid json{"
        mock_db.query.return_value.filter.return_value.first.return_value = bad
        # JSONDecodeError -> default soft_stop
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.SOFT_STOP

    def test_get_enforcement_mode_no_setting(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.SOFT_STOP

    def test_get_enforcement_mode_valid_setting(self, service, mock_db):
        s = _make_setting({"enforcement": {"mode": BudgetEnforcementMode.HARD_STOP}})
        mock_db.query.return_value.filter.return_value.first.return_value = s
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.HARD_STOP

    def test_get_enforcement_mode_setting_with_no_enforcement_key(self, service, mock_db):
        s = _make_setting({"other": "value"})
        mock_db.query.return_value.filter.return_value.first.return_value = s
        assert service._get_enforcement_mode("t1") == BudgetEnforcementMode.SOFT_STOP

    def test_get_budget_override_invalid_json(self, service, mock_db):
        bad = Mock()
        bad.setting_value = "not valid json{"
        mock_db.query.return_value.filter.return_value.first.return_value = bad
        assert service._get_budget_override("t1") is None

    def test_get_budget_override_present(self, service, mock_db):
        s = _make_setting({"enforcement": {"override": {"expires_at": "x"}}})
        mock_db.query.return_value.filter.return_value.first.return_value = s
        result = service._get_budget_override("t1")
        assert result == {"expires_at": "x"}

    def test_get_budget_override_no_setting(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert service._get_budget_override("t1") is None


# ---------------------------------------------------------------------------
# _is_override_valid
# ---------------------------------------------------------------------------
class TestIsOverrideValid:
    def test_falsy_override(self, service):
        assert service._is_override_valid(None) is False
        assert service._is_override_valid({}) is False

    def test_missing_expires_at(self, service):
        assert service._is_override_valid({"user_id": "u"}) is False

    def test_future_expiry_valid(self, service):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        assert service._is_override_valid({"expires_at": future}) is True

    def test_past_expiry_invalid(self, service):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert service._is_override_valid({"expires_at": past}) is False

    def test_invalid_datetime_string(self, service):
        assert service._is_override_valid({"expires_at": "not-a-date"}) is False

    def test_naive_datetime_string_treated_invalid(self, service):
        """Naive ISO string has no tz; comparison with tz-aware raises
        TypeError which is caught -> returns False."""
        naive = datetime.utcnow().isoformat()
        assert service._is_override_valid({"expires_at": naive}) is False


# ---------------------------------------------------------------------------
# _set_budget_override
# ---------------------------------------------------------------------------
class TestSetBudgetOverride:
    def test_creates_new_setting(self, service, mock_db):
        tenant = _make_tenant()
        # First .first() -> tenant (Tenant lookup), Second .first() -> None (no existing setting)
        mock_db.query.return_value.filter.return_value.first.side_effect = [tenant, None]
        result = service._set_budget_override("tenant_123", "user-1")
        assert result["success"] is True
        assert "expires_at" in result
        mock_db.flush.assert_called()
        mock_db.add.assert_called()

    def test_updates_existing_setting(self, service, mock_db):
        tenant = _make_tenant()
        existing_setting = _make_setting({"enforcement": {"mode": "soft_stop"}})
        # First call (Tenant lookup) -> tenant; Second call (TenantSetting) -> existing
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            tenant, existing_setting
        ]
        result = service._set_budget_override("tenant_123", "user-1")
        assert result["success"] is True
        mock_db.flush.assert_called()
        # existing_setting.setting_value was overwritten
        parsed = json.loads(existing_setting.setting_value)
        assert "override" in parsed["enforcement"]

    def test_tenant_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = service._set_budget_override("ghost", "user-1")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_existing_setting_invalid_json_resets_to_empty(self, service, mock_db):
        tenant = _make_tenant()
        bad_setting = Mock()
        bad_setting.setting_value = "not json{"
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            tenant, bad_setting
        ]
        result = service._set_budget_override("tenant_123", "user-1")
        assert result["success"] is True
        parsed = json.loads(bad_setting.setting_value)
        assert "override" in parsed["enforcement"]

    def test_exception_rolls_back(self, service, mock_db):
        mock_db.flush.side_effect = RuntimeError("flush failed")
        tenant = _make_tenant()
        mock_db.query.return_value.filter.return_value.first.side_effect = [tenant, None]
        result = service._set_budget_override("tenant_123", "user-1")
        assert result["success"] is False
        mock_db.rollback.assert_called()


# ---------------------------------------------------------------------------
# _has_active_episodes / _cancel_active_episodes
# ---------------------------------------------------------------------------
class TestEpisodeHelpers:
    def test_has_active_episodes_true(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.scalar.return_value = 2
        assert service._has_active_episodes("t1", "a1") is True

    def test_has_active_episodes_false(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        assert service._has_active_episodes("t1", "a1") is False

    def test_has_active_episodes_exception_returns_false(self, service, mock_db):
        mock_db.query.side_effect = RuntimeError("db down")
        assert service._has_active_episodes("t1", "a1") is False

    def test_cancel_active_episodes(self, service, mock_db):
        e1, e2 = Mock(), Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = [e1, e2]
        count = service._cancel_active_episodes("t1")
        assert count == 2
        assert e1.status == "cancelled"
        assert e2.status == "cancelled"
        mock_db.flush.assert_called()

    def test_cancel_active_episodes_no_episodes(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        count = service._cancel_active_episodes("t1")
        assert count == 0

    def test_cancel_active_episodes_exception_returns_zero(self, service, mock_db):
        mock_db.query.side_effect = RuntimeError("db down")
        assert service._cancel_active_episodes("t1") == 0
        mock_db.rollback.assert_called()


# ---------------------------------------------------------------------------
# clear_enforcement_state
# ---------------------------------------------------------------------------
class TestClearEnforcementState:
    def test_clears_override(self, service, mock_db):
        s = _make_setting({"enforcement": {"mode": "soft_stop", "override": {"x": 1}}})
        mock_db.query.return_value.filter.return_value.first.return_value = s
        service.clear_enforcement_state("t1")
        parsed = json.loads(s.setting_value)
        assert "override" not in parsed["enforcement"]
        mock_db.flush.assert_called()

    def test_no_setting_noop(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        service.clear_enforcement_state("t1")  # no error

    def test_setting_without_override_noop(self, service, mock_db):
        s = _make_setting({"enforcement": {"mode": "soft_stop"}})
        mock_db.query.return_value.filter.return_value.first.return_value = s
        service.clear_enforcement_state("t1")
        # value unchanged
        parsed = json.loads(s.setting_value)
        assert "override" not in parsed["enforcement"]

    def test_exception_rolls_back(self, service, mock_db):
        mock_db.query.side_effect = RuntimeError("db down")
        service.clear_enforcement_state("t1")  # must not raise
        mock_db.rollback.assert_called()


# ---------------------------------------------------------------------------
# close() / __exit__
# ---------------------------------------------------------------------------
class TestCloseAndContextManager:
    def test_close_closes_db(self, service, mock_db):
        service.close()
        mock_db.close.assert_called_once()

    def test_close_without_db_attr(self, mock_db):
        """close() guards with hasattr(self, 'db')."""
        service = BudgetEnforcementService(db=mock_db)
        del service.db  # remove attr
        service.close()  # must not raise

    def test_exit_closes_db_and_returns_false(self, service, mock_db):
        result = service.__exit__(None, None, None)
        assert result is False
        mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------
class TestExceptionHierarchy:
    def test_all_subclass_budget_error(self):
        assert issubclass(InsufficientBudgetError, BudgetError)
        assert issubclass(BudgetNotFoundError, BudgetError)
        assert issubclass(ConcurrentModificationError, BudgetError)

    def test_all_modes_constant(self):
        assert BudgetEnforcementMode.ALL == [
            BudgetEnforcementMode.ALERT_ONLY,
            BudgetEnforcementMode.SOFT_STOP,
            BudgetEnforcementMode.HARD_STOP,
            BudgetEnforcementMode.APPROVAL,
        ]
