"""Round 70 — B3: gateway budget threshold alerts (50/80/90/100%, fire-once)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.llm.gateway import budget_alerts as ba


def _reset():
    ba.reset_budget_alerts()
    ba.GATEWAY_BUDGET_ALERTS_ENABLED = True
    ba.resolve_budget_limit = lambda ws: 100.0


def _notifier():
    n = MagicMock()
    n.send_notification = AsyncMock(return_value={"success": True})
    return n


def test_crosses_single_threshold():
    _reset()
    n = _notifier()
    with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n), \
         patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u-admin"):
        crossed = asyncio.run(ba.record_gateway_spend("ws-1", 50.0))
    assert crossed == [50]
    assert n.send_notification.await_count == 1
    args = n.send_notification.await_args
    assert args.args[1] == "gateway_budget_alert"
    assert args.args[2]["metadata"]["threshold_percent"] == 50
    assert args.kwargs == {}


def test_fire_once_per_threshold():
    _reset()
    n = _notifier()
    with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n), \
         patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u-admin"):
        c1 = asyncio.run(ba.record_gateway_spend("ws-1", 95.0))  # crosses 50/80/90
        c2 = asyncio.run(ba.record_gateway_spend("ws-1", 10.0))  # crosses 100 only
    assert set(c1) == {50, 80, 90}
    assert c2 == [100]
    assert n.send_notification.await_count == 4


def test_no_refire_same_day():
    _reset()
    n = _notifier()
    with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n), \
         patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u-admin"):
        asyncio.run(ba.record_gateway_spend("ws-1", 50.0))
        again = asyncio.run(ba.record_gateway_spend("ws-1", 5.0))  # still >=50 but already fired
    assert again == []
    assert n.send_notification.await_count == 1


def test_disabled_by_flag():
    _reset()
    ba.GATEWAY_BUDGET_ALERTS_ENABLED = False
    n = _notifier()
    with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n):
        crossed = asyncio.run(ba.record_gateway_spend("ws-1", 100.0))
    assert crossed == []
    n.send_notification.assert_not_awaited()
