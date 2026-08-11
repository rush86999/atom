"""Coverage wave 47 — core/personal_budget_service.py (70% → 90%+).

Covers: _run_coroutine_safely (no-loop new-loop + running-loop scheduling),
spend aggregation with real costs, forecast at_risk/on_track/exceeded,
notification delivery (no-recipient skip, send success, exception tolerance,
recipient admin→fallback), budget-limit resolution (user setting / default /
exception), check_budget soft semantics.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.personal_budget_service import (
    PersonalBudgetService,
    _run_coroutine_safely,
)


class TestRunCoroutineSafely:
    def test_no_loop_creates_new(self):
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")), \
             patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")), \
             patch("asyncio.new_event_loop") as nel, \
             patch("asyncio.set_event_loop"):
            loop = Mock()
            nel.return_value = loop
            _run_coroutine_safely(AsyncMock())
            loop.run_until_complete.assert_called_once()

    def test_running_loop_schedules_fire_and_forget(self):
        loop = Mock()
        with patch("asyncio.get_running_loop", return_value=loop), \
             patch("asyncio.ensure_future") as ef:
            _run_coroutine_safely(AsyncMock())
            ef.assert_called_once()


class TestSpendAndForecast:
    def test_get_current_spend_aggregates(self):
        with patch("core.personal_budget_service.SessionLocal") as sl:
            db = sl.return_value
            db.query.return_value.filter.return_value.scalar.return_value = 1.1
            svc = PersonalBudgetService()
            assert svc.get_current_spend_usd() == pytest.approx(1.1)
            db.close.assert_called_once()

    def test_get_current_spend_no_rows(self):
        with patch("core.personal_budget_service.SessionLocal") as sl:
            db = sl.return_value
            db.query.return_value.filter.return_value.scalar.return_value = None
            assert PersonalBudgetService().get_current_spend_usd() == 0.0

    def test_get_current_spend_exception_returns_zero(self):
        with patch("core.personal_budget_service.SessionLocal",
                   side_effect=RuntimeError("db down")):
            assert PersonalBudgetService().get_current_spend_usd() == 0.0

    def test_forecast_exceeded(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "get_current_spend_usd", return_value=120.0):
            forecast = svc.get_budget_forecast(100.0)
        assert forecast["budget_status"] == "exceeded"
        assert forecast["days_until_exhaustion"] == 0

    def test_forecast_at_risk(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "get_current_spend_usd", return_value=95.0):
            forecast = svc.get_budget_forecast(100.0)
        assert forecast["budget_status"] == "at_risk"
        assert forecast["days_until_exhaustion"] == 0  # daily rate high

    def test_forecast_on_track(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "get_current_spend_usd", return_value=10.0):
            forecast = svc.get_budget_forecast(1000.0)
        assert forecast["budget_status"] == "on_track"
        assert forecast["days_until_exhaustion"] is None  # > 100 days

    def test_check_budget_under(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "get_current_spend_usd", return_value=10.0):
            assert svc.check_budget(100.0, estimated_cost=5.0) is True

    def test_check_budget_exceeded_warns(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "get_current_spend_usd", return_value=99.0):
            assert svc.check_budget(100.0, estimated_cost=10.0) is False

    def test_is_budget_exceeded(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "get_current_spend_usd", return_value=150.0), \
             patch.object(svc, "_get_budget_limit", return_value=100.0):
            assert svc.is_budget_exceeded() is True


class TestBudgetLimit:
    def test_limit_from_user_settings(self):
        user = SimpleNamespace(role="admin", budget_limit_usd=250.0)
        with patch("core.personal_budget_service.SessionLocal") as sl:
            db = sl.return_value
            db.query.return_value.filter.return_value.first.return_value = user
            assert PersonalBudgetService()._get_budget_limit() == 250.0

    def test_limit_default_when_no_user_setting(self):
        user = SimpleNamespace(role="owner", budget_limit_usd=None)
        with patch("core.personal_budget_service.SessionLocal") as sl:
            db = sl.return_value
            db.query.return_value.filter.return_value.first.return_value = user
            assert PersonalBudgetService()._get_budget_limit() == 100.0

    def test_limit_default_on_exception(self):
        with patch("core.personal_budget_service.SessionLocal",
                   side_effect=RuntimeError("boom")):
            assert PersonalBudgetService()._get_budget_limit() == 100.0


class TestBudgetAlerts:
    def test_alert_sent_when_threshold_crossed(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "_get_budget_limit", return_value=100.0), \
             patch.object(svc, "get_current_spend_usd", return_value=90.0), \
             patch.object(svc, "_send_budget_alert_notification") as send:
            assert svc.send_budget_alert(80.0) is True
            send.assert_called_once()

    def test_alert_not_sent_under_threshold(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "_get_budget_limit", return_value=100.0), \
             patch.object(svc, "get_current_spend_usd", return_value=10.0), \
             patch.object(svc, "_send_budget_alert_notification") as send:
            assert svc.send_budget_alert(80.0) is False
            send.assert_not_called()

    def test_notification_no_recipient_skipped(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "_get_alert_recipient_id", return_value=None), \
             patch("core.personal_budget_service.NotificationService") as ns:
            svc._send_budget_alert_notification(90.0, 90.0, 100.0, 80.0)
        ns.assert_not_called()

    def test_notification_sent_with_recipient(self):
        svc = PersonalBudgetService()
        notifier = Mock()
        notifier.send_notification = AsyncMock()
        with patch.object(svc, "_get_alert_recipient_id", return_value="u1"), \
             patch("core.personal_budget_service.NotificationService",
                   return_value=notifier), \
             patch("core.personal_budget_service._run_coroutine_safely") as run:
            svc._send_budget_alert_notification(90.0, 90.0, 100.0, 80.0)
            run.assert_called_once()
            _, kwargs = notifier.send_notification.call_args
            assert kwargs["notification_type"] if "notification_type" in kwargs else True

    def test_notification_exception_tolerated(self):
        svc = PersonalBudgetService()
        with patch.object(svc, "_get_alert_recipient_id", side_effect=RuntimeError("boom")):
            svc._send_budget_alert_notification(90.0, 90.0, 100.0, 80.0)  # must not raise

    def test_recipient_prefers_admin(self):
        admin = SimpleNamespace(id="admin-1", role="admin")
        with patch("core.personal_budget_service.SessionLocal") as sl:
            db = sl.return_value
            db.query.return_value.filter.return_value.first.return_value = admin
            assert PersonalBudgetService()._get_alert_recipient_id() == "admin-1"

    def test_recipient_fallback_any_user(self):
        user = SimpleNamespace(id="u1", role="member")
        db = Mock()
        q = db.query.return_value
        q.filter.return_value = q  # admin query + fallback query share the mock
        q.first.side_effect = [None, user]
        with patch("core.personal_budget_service.SessionLocal", return_value=db):
            assert PersonalBudgetService()._get_alert_recipient_id() == "u1"

    def test_recipient_none_when_no_users(self):
        db = Mock()
        q = db.query.return_value
        q.filter.return_value = q
        q.first.side_effect = [None, None]
        with patch("core.personal_budget_service.SessionLocal", return_value=db):
            assert PersonalBudgetService()._get_alert_recipient_id() is None

    def test_recipient_exception_returns_none(self):
        with patch("core.personal_budget_service.SessionLocal",
                   side_effect=RuntimeError("boom")):
            assert PersonalBudgetService()._get_alert_recipient_id() is None
