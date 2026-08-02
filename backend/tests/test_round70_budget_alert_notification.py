"""
Round 70 — B2: personal_budget_service.send_budget_alert now delivers an
in-app notification via NotificationService (3-arg signature) in addition to
logging, so budget warnings actually reach the user instead of vanishing into
the console.

The 3-arg contract is pinned here exactly like the B1 regression: call
``NotificationService.send_notification(user_id, "budget_alert", {...})`` with
the metadata dict — never 7 kwargs.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from core.personal_budget_service import PersonalBudgetService


def _make_service(spend=85.0, limit=100.0):
    service = PersonalBudgetService()
    service.get_current_spend_usd = MagicMock(return_value=spend)
    service._get_budget_limit = MagicMock(return_value=limit)
    return service


def test_send_budget_alert_notifies_when_crossed():
    service = _make_service(spend=85.0, limit=100.0)
    service._get_alert_recipient_id = MagicMock(return_value="u-admin")

    notifier = MagicMock()
    notifier.send_notification = AsyncMock(
        return_value={"success": True, "notification_id": "n-1", "emailed": False}
    )

    with patch("core.personal_budget_service.NotificationService", return_value=notifier):
        result = service.send_budget_alert(threshold_percent=80.0)

    assert result is True
    notifier.send_notification.assert_awaited_once()
    args, kwargs = (
        notifier.send_notification.await_args.args,
        notifier.send_notification.await_args.kwargs,
    )
    assert kwargs == {}  # no 7-kwarg style regression
    assert args[0] == "u-admin"
    assert args[1] == "budget_alert"
    assert isinstance(args[2], dict)
    assert args[2]["metadata"]["alert_type"] == "budget_alert"
    assert args[2]["metadata"]["usage_percent"] == 85.0
    assert args[2]["metadata"]["threshold_percent"] == 80.0


def test_send_budget_alert_no_notification_below_threshold():
    service = _make_service(spend=70.0, limit=100.0)

    notifier = MagicMock()
    notifier.send_notification = AsyncMock()

    with patch("core.personal_budget_service.NotificationService", return_value=notifier):
        result = service.send_budget_alert(threshold_percent=80.0)

    assert result is False
    notifier.send_notification.assert_not_awaited()


def test_budget_alert_still_logs_warning_when_crossed():
    """The existing console-warning behavior must be preserved."""
    service = _make_service(spend=90.0, limit=100.0)
    service._get_alert_recipient_id = MagicMock(return_value="u-admin")

    notifier = MagicMock()
    notifier.send_notification = AsyncMock()
    with patch("core.personal_budget_service.NotificationService", return_value=notifier), \
         patch("core.personal_budget_service.logger") as mock_logger:
        result = service.send_budget_alert(threshold_percent=80.0)

    assert result is True
    mock_logger.warning.assert_called_once()
    assert "BUDGET ALERT" in str(mock_logger.warning.call_args)


def test_budget_alert_notification_never_raises():
    """Notification glitches must not break the alert return value."""
    service = _make_service(spend=95.0, limit=100.0)
    service._get_alert_recipient_id = MagicMock(return_value="u-admin")

    notifier = MagicMock()
    notifier.send_notification = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("core.personal_budget_service.NotificationService", return_value=notifier):
        result = service.send_budget_alert(threshold_percent=80.0)

    assert result is True
