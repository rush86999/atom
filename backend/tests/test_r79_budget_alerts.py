"""Round 79 — gateway budget-alert day-reset + recipient-resolution tests.

TDD targets:
- The admin fallback in ``_resolve_recipient_id`` used ``User.is_admin``, an
  attribute that does not exist on the model — the AttributeError was swallowed
  and the fallback silently returned None, so alerts without a preferred user
  never fired.
- Day rollover must reset both the daily-spend accumulator and the fire-once
  state (thresholds refire on the new day).
- An arbitrary non-admin user must never become the recipient.
"""
import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.gateway import budget_alerts as ba


@pytest.fixture(autouse=True)
def _reset():
    ba.reset_budget_alerts()
    ba.GATEWAY_BUDGET_ALERTS_ENABLED = True
    ba.resolve_budget_limit = lambda ws: 100.0
    yield
    ba.reset_budget_alerts()


class _FakeDate:
    current = "2026-08-01"

    @classmethod
    def today(cls):
        return datetime.date.fromisoformat(cls.current)


@pytest.fixture
def fake_date(monkeypatch):
    monkeypatch.setattr(ba, "date", _FakeDate)
    return _FakeDate


def _notifier():
    n = MagicMock()
    n.send_notification = AsyncMock(return_value={"success": True})
    return n


class TestDayRollover:
    def test_day_rollover_resets_spend_and_fire_state(self, fake_date):
        """A threshold that fired yesterday must refire when the calendar day
        changes (fresh spend accumulator + fresh fire-once state)."""
        n = _notifier()
        with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n), \
             patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u1"):
            c1 = asyncio.run(ba.record_gateway_spend("ws-1", 50.0))   # day 1: fires 50
            fake_date.current = "2026-08-02"
            c2 = asyncio.run(ba.record_gateway_spend("ws-1", 10.0))   # day 2: fresh, nothing yet
            c3 = asyncio.run(ba.record_gateway_spend("ws-1", 40.0))   # day 2: hits 50 again
        assert c1 == [50]
        assert c2 == []
        assert c3 == [50]
        assert n.send_notification.await_count == 2

    def test_exact_100_percent_fires_all_thresholds(self):
        n = _notifier()
        with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n), \
             patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u1"):
            crossed = asyncio.run(ba.record_gateway_spend("ws-1", 100.0))
        assert crossed == [50, 80, 90, 100]
        assert n.send_notification.await_count == 4

    def test_multi_threshold_crossing_in_one_call(self):
        n = _notifier()
        with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n), \
             patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u1"):
            crossed = asyncio.run(ba.record_gateway_spend("ws-1", 85.0))
        assert set(crossed) == {50, 80}

    def test_spend_below_first_threshold_fires_nothing(self):
        n = _notifier()
        with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n), \
             patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u1"):
            crossed = asyncio.run(ba.record_gateway_spend("ws-1", 49.99))
        assert crossed == []
        n.send_notification.assert_not_awaited()

    def test_per_workspace_accumulation_is_independent(self):
        n = _notifier()
        with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n), \
             patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u1"):
            c_a = asyncio.run(ba.record_gateway_spend("ws-a", 50.0))
            c_b = asyncio.run(ba.record_gateway_spend("ws-b", 50.0))
        assert c_a == [50]
        assert c_b == [50]
        assert n.send_notification.await_count == 2


class TestRecipientResolution:
    """_resolve_recipient_id must resolve the spending user, else an admin —
    never an arbitrary user."""

    @pytest.fixture
    def db(self, worker_database):
        from core.models import User

        session = worker_database()
        session.query(User).delete()
        session.commit()
        yield session
        session.close()

    @staticmethod
    def _user(db, uid, is_admin=False):
        import uuid

        from core.models import User

        unique = uid or f"user-{uuid.uuid4().hex[:10]}"
        user = User(
            id=unique,
            email=f"{unique}@test.com",
            first_name="A",
            last_name="B",
            role="admin" if is_admin else "user",
            status="active",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id  # capture before the resolver closes the session
        db.expunge(user)
        return user_id

    def _resolve(self, db, prefer_user_id=None):
        with patch("core.database.SessionLocal", lambda: db):
            return ba._resolve_recipient_id(prefer_user_id=prefer_user_id)

    def test_prefers_the_spending_user_over_an_admin(self, db):
        caller_id = self._user(db, "spend-user-1")
        admin_id = self._user(db, "admin-user-1", is_admin=True)
        assert self._resolve(db, prefer_user_id=caller_id) == caller_id

    def test_falls_back_to_admin_when_preferred_user_unknown(self, db):
        admin_id = self._user(db, "admin-user-2", is_admin=True)
        assert self._resolve(db, prefer_user_id="ghost-user") == admin_id

    def test_never_returns_an_arbitrary_user_when_no_admin_exists(self, db):
        """With only a plain non-admin user present, the recipient must be
        None — never the first arbitrary row (the old `User.is_admin` lookup
        crashed and silently skipped the alert)."""
        self._user(db, "only-user-1", is_admin=False)
        assert self._resolve(db, prefer_user_id="ghost-user") is None
        assert self._resolve(db, prefer_user_id=None) is None

    def test_admin_fallback_works_when_no_preferred_user(self, db):
        admin_id = self._user(db, "admin-user-3", is_admin=True)
        self._user(db, "member-user-1", is_admin=False)
        assert self._resolve(db, prefer_user_id=None) == admin_id

    def test_preferred_user_who_is_not_admin_still_wins(self, db):
        caller_id = self._user(db, "spend-user-2", is_admin=False)
        self._user(db, "admin-user-4", is_admin=True)
        assert self._resolve(db, prefer_user_id=caller_id) == caller_id

    def test_alert_end_to_end_delivers_to_spending_user(self, db):
        """record_gateway_spend passes the spending user through to the
        notification recipient (fire-once + recipient wiring)."""
        caller_id = self._user(db, "spend-user-3", is_admin=False)
        n = _notifier()
        with patch("core.llm.gateway.budget_alerts.NotificationService", return_value=n), \
             patch("core.database.SessionLocal", lambda: db):
            crossed = asyncio.run(ba.record_gateway_spend("ws-1", 50.0, user_id=caller_id))
        assert crossed == [50]
        assert n.send_notification.await_count == 1
        recipient = n.send_notification.await_args.args[0]
        assert recipient == caller_id
