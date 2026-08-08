"""
Coverage + bug-hunt tests for ``core/condition_monitoring_service.py``.

The production ``ConditionMonitor`` / ``ConditionAlert`` models are Phase 265
stubs that lack the fields/attributes the service reads/writes
(``ConditionMonitor.status``/``.agent_id`` columns and the
``ConditionAlertStatus.PENDING``/``.SENT``/``.FAILED`` enum members do not
exist on the stubs). So the model classes referenced by the service are
replaced with MagicMock stand-ins for the duration of every test, the DB
``Session`` is mocked, and the condition checker + agent integration gateway
are patched so there is no real DB / network IO.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import core.condition_monitoring_service as cms_module
from core.condition_monitoring_service import ConditionMonitoringService


# A stand-in for the (stubbed) ConditionAlertStatus enum. The real model is a
# plain table missing the PENDING/SENT/FAILED members the service uses.
class _FakeAlertStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


class _Column:
    """A SQL-column-like sentinel that supports arbitrary comparisons so it can
    stand in for any ``Model.attribute`` used inside ``.filter(...)`` clauses."""

    def __eq__(self, other):
        return ("==", other)

    def __ne__(self, other):
        return ("!=", other)

    def __ge__(self, other):
        return (">=", other)

    def __gt__(self, other):
        return (">", other)

    def __le__(self, other):
        return ("<=", other)

    def __lt__(self, other):
        return ("<", other)

    # MagicMock-style desc() for ORDER BY clauses.
    def desc(self):
        return ("desc", self)


class _FakeModelMeta(type):
    """Metaclass that returns a fresh ``_Column`` for any class-attribute access,
    so ``FakeModel.status == 'active'`` and ``FakeModel.created_at.desc()``
    work without a real SQLAlchemy schema."""

    def __getattr__(cls, name):
        # Only intercept column-like accesses; dunders/dunder-methods resolve
        # normally via type.
        return _Column()


class _FakeModel(metaclass=_FakeModelMeta):
    """A stand-in model class. Instantiation captures constructor kwargs as
    attributes so test assertions can read them back."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture(autouse=True)
def _stub_model_classes():
    """Replace the stubbed model classes in the service module with stand-ins
    so attribute access (``ConditionMonitor.status == ...``), ORDER BY
    (``ConditionMonitor.created_at.desc()``), comparisons
    (``ConditionAlert.triggered_at >= ...``) and instantiation all work without
    the real (stub) schema."""
    with patch.object(cms_module, "ConditionMonitor", _FakeModel), \
         patch.object(cms_module, "ConditionAlert", _FakeModel), \
         patch.object(cms_module, "ConditionAlertStatus", _FakeAlertStatus):
        yield


# Re-export so test bodies can compare against the same status values the
# service writes.
ConditionAlertStatus = _FakeAlertStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _svc(db=None):
    return ConditionMonitoringService(db or MagicMock())


def _make_monitor(
    id_="m1", name="Inbox monitor", agent_name="OpsBot",
    condition_type="inbox_volume",
    threshold_config=None, status="active",
    platforms=None, alert_template=None, last_alert_sent_at=None,
    throttle_minutes=5, composite_logic=None, composite_conditions=None,
    agent_id="agent1",
):
    m = MagicMock()
    m.id = id_
    m.name = name
    m.agent_name = agent_name
    m.agent_id = agent_id
    m.condition_type = condition_type
    m.threshold_config = threshold_config if threshold_config is not None else {
        "metric": "unread_count", "operator": ">", "value": 100,
    }
    m.status = status
    m.platforms = platforms if platforms is not None else [
        {"platform": "slack", "recipient_id": "C1"},
    ]
    m.alert_template = alert_template
    m.last_alert_sent_at = last_alert_sent_at
    m.throttle_minutes = throttle_minutes
    m.composite_logic = composite_logic
    m.composite_conditions = composite_conditions
    m.governance_metadata = {}
    m.check_interval_seconds = 300
    return m


# ---------------------------------------------------------------------------
# create_monitor
# ---------------------------------------------------------------------------

class TestCreateMonitor:
    def test_agent_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        s = _svc(db)
        with pytest.raises(HTTPException) as exc:
            s.create_monitor(
                agent_id="ghost", name="n", condition_type="inbox_volume",
                threshold_config={"value": 1}, platforms=[],
            )
        assert exc.value.status_code == 404

    def test_empty_threshold_config_rejected(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock(name="agent")
        s = _svc(db)
        for bad in ({}, None):
            with pytest.raises(HTTPException) as exc:
                s.create_monitor(
                    agent_id="a1", name="n", condition_type="inbox_volume",
                    threshold_config=bad, platforms=[],
                )
            assert exc.value.status_code == 400
            assert "threshold_config" in exc.value.detail

    def test_composite_requires_logic_and_conditions(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        s = _svc(db)
        with pytest.raises(HTTPException) as exc:
            s.create_monitor(
                agent_id="a1", name="n", condition_type="composite",
                threshold_config={"value": 1}, platforms=[],
                composite_logic=None, composite_conditions=None,
            )
        assert exc.value.status_code == 400

    def test_composite_invalid_logic(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        s = _svc(db)
        with pytest.raises(HTTPException) as exc:
            s.create_monitor(
                agent_id="a1", name="n", condition_type="composite",
                threshold_config={"value": 1}, platforms=[],
                composite_logic="XOR", composite_conditions=[{"condition_type": "inbox_volume"}],
            )
        assert exc.value.status_code == 400
        assert "composite_logic" in exc.value.detail

    def test_composite_empty_conditions_rejected(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        s = _svc(db)
        with pytest.raises(HTTPException) as exc:
            s.create_monitor(
                agent_id="a1", name="n", condition_type="composite",
                threshold_config={"value": 1}, platforms=[],
                composite_logic="AND", composite_conditions=[],
            )
        assert exc.value.status_code == 400

    def test_create_success_persists_monitor(self):
        agent = MagicMock()
        agent.name = "OpsBot"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        s = _svc(db)
        monitor = s.create_monitor(
            agent_id="a1", name="My Monitor", condition_type="inbox_volume",
            threshold_config={"metric": "unread_count", "operator": ">", "value": 50},
            platforms=[{"platform": "slack", "recipient_id": "C1"}],
            check_interval_seconds=120, alert_template="hi {{value}}",
            governance_metadata={"team": "ops"},
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()
        # The persisted object should carry through the inputs.
        added = db.add.call_args[0][0]
        assert added.agent_id == "a1"
        assert added.agent_name == "OpsBot"
        assert added.name == "My Monitor"
        assert added.status == "active"
        assert added.check_interval_seconds == 120
        assert added.alert_template == "hi {{value}}"
        assert added.governance_metadata == {"team": "ops"}
        assert monitor is added

    def test_create_composite_success(self):
        agent = MagicMock()
        agent.name = "Bot"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        s = _svc(db)
        s.create_monitor(
            agent_id="a1", name="comp", condition_type="composite",
            threshold_config={"value": 1}, platforms=[],
            composite_logic="OR",
            composite_conditions=[{"condition_type": "inbox_volume"}],
        )
        db.add.assert_called_once()


# ---------------------------------------------------------------------------
# update_monitor / pause / resume / delete / get_monitors / get_monitor
# ---------------------------------------------------------------------------

class TestMonitorMutations:
    def _db_with_monitor(self, monitor):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = monitor
        return db

    def test_update_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            _svc(db).update_monitor("ghost")
        assert exc.value.status_code == 404

    def test_update_applies_provided_fields_only(self):
        m = _make_monitor(name="old", alert_template="t",
                          platforms=[{"platform": "slack"}])
        db = self._db_with_monitor(m)
        _svc(db).update_monitor(
            "m1", name="new", threshold_config={"value": 9},
            check_interval_seconds=60,
        )
        assert m.name == "new"
        assert m.threshold_config == {"value": 9}
        assert m.check_interval_seconds == 60
        # Unprovided fields untouched.
        assert m.alert_template == "t"
        assert m.platforms == [{"platform": "slack"}]
        db.commit.assert_called_once()

    def test_update_all_none_fields_unchanged(self):
        m = _make_monitor(name="keep")
        db = self._db_with_monitor(m)
        _svc(db).update_monitor("m1")  # nothing to update
        assert m.name == "keep"
        db.commit.assert_called_once()

    def test_pause_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException):
            _svc(db).pause_monitor("ghost")

    def test_pause_sets_status(self):
        m = _make_monitor(status="active")
        db = self._db_with_monitor(m)
        out = _svc(db).pause_monitor("m1")
        assert m.status == "paused"
        assert out is m

    def test_resume_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException):
            _svc(db).resume_monitor("ghost")

    def test_resume_sets_status(self):
        m = _make_monitor(status="paused")
        db = self._db_with_monitor(m)
        _svc(db).resume_monitor("m1")
        assert m.status == "active"

    def test_delete_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException):
            _svc(db).delete_monitor("ghost")

    def test_delete_calls_db_delete(self):
        m = _make_monitor()
        db = self._db_with_monitor(m)
        out = _svc(db).delete_monitor("m1")
        db.delete.assert_called_once_with(m)
        db.commit.assert_called_once()
        assert out is m


class TestMonitorQueries:
    def test_get_monitors_with_filters(self):
        q = MagicMock()
        # Service chains: .filter().filter().filter().order_by().limit().all()
        leaf = MagicMock()
        leaf.all.return_value = ["m1", "m2"]
        q.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value = leaf
        db = MagicMock()
        db.query.return_value = q
        s = _svc(db)
        out = s.get_monitors(agent_id="a1", condition_type="inbox_volume", status="active", limit=10)
        assert out == ["m1", "m2"]
        # agent_id + condition_type + status filters all applied (3 .filter calls)
        assert q.filter.call_count == 3

    def test_get_monitors_no_filters(self):
        q = MagicMock()
        q.order_by.return_value.limit.return_value.all.return_value = []
        db = MagicMock()
        db.query.return_value = q
        assert _svc(db).get_monitors() == []
        q.filter.assert_not_called()

    def test_get_monitor(self):
        m = _make_monitor()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = m
        assert _svc(db).get_monitor("m1") is m

    def test_get_monitor_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        assert _svc(db).get_monitor("ghost") is None

    def test_get_alerts_with_filters(self):
        q = MagicMock()
        # Service chains: .filter().filter().order_by().limit().all()
        leaf = MagicMock()
        leaf.all.return_value = ["a1"]
        q.filter.return_value.filter.return_value.order_by.return_value.limit.return_value = leaf
        db = MagicMock()
        db.query.return_value = q
        out = _svc(db).get_alerts(monitor_id="m1", status="pending", limit=5)
        assert out == ["a1"]
        assert q.filter.call_count == 2  # monitor_id + status

    def test_get_alerts_no_filters(self):
        q = MagicMock()
        q.order_by.return_value.limit.return_value.all.return_value = []
        db = MagicMock()
        db.query.return_value = q
        assert _svc(db).get_alerts() == []


# ---------------------------------------------------------------------------
# _generate_alert_message
# ---------------------------------------------------------------------------

class TestGenerateAlertMessage:
    def test_custom_template_substitution(self):
        m = _make_monitor(alert_template="Value {{value}} hit threshold {{threshold}}",
                          threshold_config={"value": 100})
        s = _svc()
        msg = s._generate_alert_message(m, {"value": 42, "metric_name": "X"})
        assert "Value 42" in msg
        assert "threshold {'value': 100}" in msg

    def test_default_message_with_metric_name(self):
        m = _make_monitor(threshold_config={"metric": "unread", "operator": ">=", "value": 50})
        s = _svc()
        msg = s._generate_alert_message(m, {"value": 75, "metric_name": "Unread messages"})
        assert "Unread messages" in msg
        assert "75" in msg
        assert ">= 50" in msg

    def test_default_message_without_metric_name(self):
        m = _make_monitor(name="MyCond", threshold_config={"operator": ">", "value": 10})
        s = _svc()
        msg = s._generate_alert_message(m, {"value": 99, "metric_name": ""})
        assert "MyCond" in msg
        assert "99" in msg

    def test_default_message_threshold_config_without_value_key(self):
        # threshold_config with no 'value' key -> falls back to whole dict.
        m = _make_monitor(threshold_config={"operator": "<"})
        s = _svc()
        msg = s._generate_alert_message(m, {"value": 3, "metric_name": "M"})
        assert "<" in msg
        # fallback prints the whole dict as the threshold
        assert "{'operator': '<'}" in msg

    def test_default_message_threshold_config_defaults(self):
        # Empty-ish dict -> operator defaults to '>', metric to ''.
        m = _make_monitor(threshold_config={})
        s = _svc()
        msg = s._generate_alert_message(m, {"value": 1, "metric_name": "M"})
        assert "> {}" in msg


# ---------------------------------------------------------------------------
# _send_alert
# ---------------------------------------------------------------------------

class TestSendAlert:
    @pytest.mark.asyncio
    async def test_successful_send_increments_count(self):
        m = _make_monitor(platforms=[
            {"platform": "slack", "recipient_id": "C1"},
            {"platform": "teams", "recipient_id": "T1"},
        ])
        alert = MagicMock()
        alert.alert_message = "hello"
        s = _svc()
        with patch("core.condition_monitoring_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(side_effect=[
                {"status": "success", "message_id": "ms1"},
                {"status": "success", "message_id": "ms2"},
            ])
            count = await s._send_alert(m, alert, {"value": 1})
        assert count == 2
        assert len(alert.platforms_sent) == 2
        assert alert.platforms_sent[0]["status"] == "sent"

    @pytest.mark.asyncio
    async def test_failed_platform_recorded_not_counted(self):
        m = _make_monitor(platforms=[
            {"platform": "slack", "recipient_id": "C1"},
            {"platform": "teams", "recipient_id": "T1"},
        ])
        alert = MagicMock()
        alert.alert_message = "hello"
        s = _svc()
        with patch("core.condition_monitoring_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(side_effect=[
                {"status": "error", "error": "rate-limited"},
                Exception("boom"),
            ])
            count = await s._send_alert(m, alert, {"value": 1})
        assert count == 0
        statuses = [p["status"] for p in alert.platforms_sent]
        assert "failed" in statuses
        assert "error" in statuses

    @pytest.mark.asyncio
    async def test_invalid_platform_config_skipped(self):
        m = _make_monitor(platforms=[
            {"platform": "", "recipient_id": ""},   # missing platform
            {"platform": "slack"},                  # missing recipient_id
            {"platform": "slack", "recipient_id": "C1"},  # valid
        ])
        alert = MagicMock()
        alert.alert_message = "hi"
        s = _svc()
        with patch("core.condition_monitoring_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success", "message_id": "x"})
            count = await s._send_alert(m, alert, {"value": 1})
        assert count == 1  # only the valid config sent

    @pytest.mark.asyncio
    async def test_empty_platforms(self):
        m = _make_monitor(platforms=[])
        alert = MagicMock()
        s = _svc()
        with patch("core.condition_monitoring_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            count = await s._send_alert(m, alert, {"value": 1})
        assert count == 0
        assert alert.platforms_sent == []


# ---------------------------------------------------------------------------
# check_and_alert_monitors
# ---------------------------------------------------------------------------

class TestCheckAndAlertMonitors:
    @pytest.mark.asyncio
    async def test_no_active_monitors(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        s = _svc(db)
        result = await s.check_and_alert_monitors()
        assert result == {"checked": 0, "triggered": 0, "alerts_sent": 0}

    @pytest.mark.asyncio
    async def test_triggered_monitor_sends_alert(self):
        m = _make_monitor(last_alert_sent_at=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [m]
        s = _svc(db)
        cond_result = {"triggered": True, "value": 150, "metric_name": "Unread"}
        with patch("core.condition_checkers.ConditionCheckers.check_condition", return_value=cond_result), \
             patch.object(ConditionMonitoringService, "_send_alert", new=AsyncMock(return_value=1)):
            result = await s.check_and_alert_monitors()
        assert result["checked"] == 1
        assert result["triggered"] == 1
        assert result["alerts_sent"] == 1
        # Alert created with PENDING then promoted to SENT.
        added_alert = db.add.call_args[0][0]
        assert added_alert.status == ConditionAlertStatus.SENT.value
        assert added_alert.sent_at is not None
        assert m.last_alert_sent_at is not None

    @pytest.mark.asyncio
    async def test_triggered_but_send_fails_marks_failed(self):
        m = _make_monitor(last_alert_sent_at=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [m]
        s = _svc(db)
        cond_result = {"triggered": True, "value": 150, "metric_name": "Unread"}
        with patch("core.condition_checkers.ConditionCheckers.check_condition", return_value=cond_result), \
             patch.object(ConditionMonitoringService, "_send_alert", new=AsyncMock(return_value=0)):
            result = await s.check_and_alert_monitors()
        assert result["alerts_sent"] == 0
        assert result["triggered"] == 1
        added_alert = db.add.call_args[0][0]
        assert added_alert.status == ConditionAlertStatus.FAILED.value
        assert added_alert.error_message == "Failed to send to any platform"
        # last_alert_sent_at must NOT advance when send failed.
        assert m.last_alert_sent_at is None

    @pytest.mark.asyncio
    async def test_not_triggered_does_not_alert(self):
        m = _make_monitor(last_alert_sent_at=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [m]
        s = _svc(db)
        cond_result = {"triggered": False, "value": 5, "metric_name": "Unread"}
        with patch("core.condition_checkers.ConditionCheckers.check_condition", return_value=cond_result), \
             patch.object(ConditionMonitoringService, "_send_alert", new=AsyncMock(return_value=99)):
            result = await s.check_and_alert_monitors()
        assert result == {"checked": 1, "triggered": 0, "alerts_sent": 0}
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_throttled_monitor_skipped(self):
        # Last alert 1 minute ago, throttle window 5 minutes -> skip.
        now = datetime.now(timezone.utc)
        m = _make_monitor(last_alert_sent_at=now - timedelta(minutes=1),
                          throttle_minutes=5)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [m]
        s = _svc(db)
        with patch("core.condition_checkers.ConditionCheckers.check_condition") as chk, \
             patch.object(ConditionMonitoringService, "_send_alert", new=AsyncMock(return_value=1)):
            result = await s.check_and_alert_monitors()
        # counted as checked but NOT evaluated (condition checker not called).
        assert result["checked"] == 1
        assert result["triggered"] == 0
        chk.assert_not_called()

    @pytest.mark.asyncio
    async def test_throttle_expired_re_checks(self):
        # Last alert 10 minutes ago, throttle window 5 minutes -> re-check.
        now = datetime.now(timezone.utc)
        m = _make_monitor(last_alert_sent_at=now - timedelta(minutes=10),
                          throttle_minutes=5)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [m]
        s = _svc(db)
        cond_result = {"triggered": True, "value": 150, "metric_name": "Unread"}
        with patch("core.condition_checkers.ConditionCheckers.check_condition", return_value=cond_result), \
             patch.object(ConditionMonitoringService, "_send_alert", new=AsyncMock(return_value=1)):
            result = await s.check_and_alert_monitors()
        assert result["triggered"] == 1
        assert result["alerts_sent"] == 1

    @pytest.mark.asyncio
    async def test_zero_throttle_minutes_never_throttles(self):
        now = datetime.now(timezone.utc)
        m = _make_monitor(last_alert_sent_at=now - timedelta(seconds=1),
                          throttle_minutes=0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [m]
        s = _svc(db)
        cond_result = {"triggered": True, "value": 150, "metric_name": "Unread"}
        with patch("core.condition_checkers.ConditionCheckers.check_condition", return_value=cond_result), \
             patch.object(ConditionMonitoringService, "_send_alert", new=AsyncMock(return_value=1)):
            result = await s.check_and_alert_monitors()
        assert result["triggered"] == 1

    @pytest.mark.asyncio
    async def test_bug_naive_last_alert_sent_at_does_not_disable_monitor(self):
        """BUG: ``now`` is timezone-aware (UTC). If ``last_alert_sent_at`` is a
        naive datetime (e.g. returned by SQLite or assigned naively), the
        subtraction ``now - last_alert_sent_at`` raises TypeError, which the
        broad ``except Exception`` in the loop silently swallows — so the
        monitor's condition is NEVER checked and no alert fires. The throttle
        math must normalize a naive timestamp to UTC before subtracting."""
        # naive timestamp from the "past" so the throttle window has elapsed.
        naive_past = (datetime.now(timezone.utc) - timedelta(minutes=30)
                      ).replace(tzinfo=None)
        m = _make_monitor(last_alert_sent_at=naive_past, throttle_minutes=5)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [m]
        s = _svc(db)
        cond_result = {"triggered": True, "value": 150, "metric_name": "Unread"}
        with patch("core.condition_checkers.ConditionCheckers.check_condition", return_value=cond_result) as chk, \
             patch.object(ConditionMonitoringService, "_send_alert", new=AsyncMock(return_value=1)):
            result = await s.check_and_alert_monitors()
        # The condition must be evaluated (not silently skipped by the
        # swallowed TypeError), and the triggered alert must fire.
        chk.assert_called_once()
        assert result["triggered"] == 1
        assert result["alerts_sent"] == 1

    @pytest.mark.asyncio
    async def test_exception_in_one_monitor_does_not_stop_others(self):
        good = _make_monitor(id_="good", last_alert_sent_at=None)
        # A monitor whose condition check raises.
        bad = _make_monitor(id_="bad", last_alert_sent_at=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [bad, good]
        s = _svc(db)

        def fake_check(monitor):
            if monitor.id == "bad":
                raise RuntimeError("checker exploded")
            return {"triggered": True, "value": 150, "metric_name": "Unread"}

        with patch("core.condition_checkers.ConditionCheckers.check_condition", side_effect=fake_check), \
             patch.object(ConditionMonitoringService, "_send_alert", new=AsyncMock(return_value=1)):
            result = await s.check_and_alert_monitors()
        # Both counted as checked; only the good one triggered/alerted.
        assert result["checked"] == 2
        assert result["triggered"] == 1
        assert result["alerts_sent"] == 1


# ---------------------------------------------------------------------------
# test_condition / get_presets / get_metrics
# ---------------------------------------------------------------------------

class TestTestCondition:
    def test_monitor_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            _svc(db).test_condition("ghost")
        assert exc.value.status_code == 404

    def test_returns_check_result_without_alerting(self):
        m = _make_monitor(condition_type="inbox_volume")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = m
        s = _svc(db)
        cond_result = {"triggered": True, "value": 200, "metric_name": "Unread"}
        with patch("core.condition_checkers.ConditionCheckers.check_condition", return_value=cond_result):
            out = s.test_condition("m1")
        assert out["triggered"] is True
        assert out["current_value"] == 200
        assert out["monitor_id"] == "m1"
        assert out["threshold"] == m.threshold_config
        assert "timestamp" in out


class TestPresets:
    def test_presets_returned_with_expected_types(self):
        presets = _svc().get_presets()
        assert len(presets) == 4
        types = {p["condition_type"] for p in presets}
        assert types == {"inbox_volume", "task_backlog", "api_metrics", "database_query"}
        for p in presets:
            assert "threshold_config" in p
            assert "recommended_platforms" in p


class TestGetMetrics:
    def test_metrics_aggregate_counts(self):
        db = MagicMock()
        # The method issues 5 count() scalars in order:
        # total_monitors, active_monitors, total_alerts, pending_alerts, recent_alerts
        db.query.return_value.scalar.side_effect = [10, 4, 25, 3, 2]
        s = _svc(db)
        out = s.get_metrics()
        assert out["total_monitors"] == 10
        assert out["active_monitors"] == 4
        assert out["total_alerts"] == 25
        assert out["pending_alerts"] == 3
        assert out["alerts_last_24h"] == 2
        assert "timestamp" in out
