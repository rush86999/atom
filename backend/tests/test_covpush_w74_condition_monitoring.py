# -*- coding: utf-8 -*-
"""Coverage wave 74 — core/condition_monitoring_service.py (standalone, zero
LLM spend, no network, in-memory SQLite).

TDD target (RED first, fixed in source):
- ``get_metrics`` filtered on ``ConditionMonitor.status`` — the stub model has
  NO ``status`` column (only ``is_active``), so the metrics endpoint raised
  AttributeError (500) instead of returning counts.

Coverage targets: create_monitor validation (missing agent, missing
threshold_config, composite logic/conditions required, invalid logic),
update_monitor (not-found + every field branch), pause/resume/delete
(not-found + success), get_monitors filters (agent_id/condition_type/status),
get_monitor, get_alerts filters + plain-attr hydration, check_and_alert_monitors
(throttle skip, naive-timestamp normalize, triggered→sent, send-failure,
checker exception swallowed, counts), _generate_alert_message (template,
default with/without metric_name), _send_alert (invalid platform, gateway
success/failure/exception), test_condition, get_metrics.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (  # noqa: F401 (register models)
    AgentRegistry,
    ConditionAlert,
    ConditionMonitor,
    Tenant,
    User,
    Workspace,
)
from core.condition_checkers import (
    CONDITION_TYPE_API_METRICS,
    CONDITION_TYPE_COMPOSITE,
    CONDITION_TYPE_INBOX_VOLUME,
)
from core.condition_monitoring_service import ConditionMonitoringService


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1", tenant_id="t1", user_id="user-1"):
    Tenant(id=tenant_id, name="Test", subdomain=f"sub-{tenant_id}")
    db.add(Tenant(id=tenant_id, name="Test", subdomain=f"sub-{tenant_id}"))
    db.add(Workspace(id="ws-1", name="WS", tenant_id=tenant_id))
    db.add(User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="admin",
        status="active",
        tenant_id=tenant_id,
    ))
    db.add(AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id="ws-1",
        tenant_id=tenant_id,
        user_id=user_id,
        category="Test",
        module_path="test",
        class_name="Test",
    ))
    db.commit()
    return agent_id


def _base_config(threshold_config=None, platforms=None):
    return {
        "threshold_config": threshold_config or {},
        "platforms": platforms or [],
        "check_interval_seconds": 300,
        "alert_template": None,
        "composite_logic": None,
        "composite_conditions": [],
        "governance_metadata": {},
    }


def _create_monitor(db, agent_id="agent-1", condition_type=CONDITION_TYPE_INBOX_VOLUME,
                    threshold_config=None, **kwargs):
    if threshold_config is None:
        threshold_config = {"metric": "unread_count", "operator": ">", "value": 100}
    service = ConditionMonitoringService(db)
    monitor = service.create_monitor(
        agent_id=agent_id,
        name=kwargs.pop("name", "Test monitor"),
        condition_type=condition_type,
        threshold_config=threshold_config,
        platforms=kwargs.pop("platforms", []),
        check_interval_seconds=kwargs.pop("check_interval_seconds", 300),
        alert_template=kwargs.pop("alert_template", None),
        composite_logic=kwargs.pop("composite_logic", None),
        composite_conditions=kwargs.pop("composite_conditions", None),
        governance_metadata=kwargs.pop("governance_metadata", None),
    )
    return monitor


# ============================================================================
# TDD RED — get_metrics used nonexistent ConditionMonitor.status column
# ============================================================================

class TestGetMetricsRealBug:
    def test_get_metrics_does_not_crash_on_status_filter(self, db):
        _make_agent(db)
        _create_monitor(db)
        result = ConditionMonitoringService(db).get_metrics()
        assert result["total_monitors"] == 1
        assert result["active_monitors"] == 1
        assert result["total_alerts"] == 0
        assert result["pending_alerts"] == 0
        assert result["alerts_last_24h"] == 0
        assert result["timestamp"].endswith("+00:00") or "T" in result["timestamp"]

    def test_get_metrics_paused_monitor_not_active(self, db):
        _make_agent(db)
        monitor = _create_monitor(db)
        ConditionMonitoringService(db).pause_monitor(monitor.id)
        result = ConditionMonitoringService(db).get_metrics()
        assert result["total_monitors"] == 1
        assert result["active_monitors"] == 0


# ============================================================================
# create_monitor validation
# ============================================================================

class TestCreateMonitor:
    def test_agent_not_found(self, db):
        with pytest.raises(HTTPException) as exc:
            ConditionMonitoringService(db).create_monitor(
                agent_id="nope", name="m", condition_type="inbox_volume",
                threshold_config={"metric": "unread_count", "operator": ">", "value": 1},
                platforms=[],
            )
        assert exc.value.status_code == 404

    def test_missing_threshold_config(self, db):
        _make_agent(db)
        with pytest.raises(HTTPException) as exc:
            ConditionMonitoringService(db).create_monitor(
                agent_id="agent-1", name="m", condition_type="inbox_volume",
                threshold_config={}, platforms=[],
            )
        assert exc.value.status_code == 400
        assert "threshold_config is required" in exc.value.detail

    def test_composite_requires_logic_and_conditions(self, db):
        _make_agent(db)
        service = ConditionMonitoringService(db)
        with pytest.raises(HTTPException) as exc:
            service.create_monitor(
                agent_id="agent-1", name="m", condition_type=CONDITION_TYPE_COMPOSITE,
                threshold_config={}, platforms=[],
            )
        assert exc.value.status_code == 400
        assert "composite_logic and composite_conditions" in exc.value.detail

    def test_composite_invalid_logic(self, db):
        _make_agent(db)
        with pytest.raises(HTTPException) as exc:
            ConditionMonitoringService(db).create_monitor(
                agent_id="agent-1", name="m", condition_type=CONDITION_TYPE_COMPOSITE,
                threshold_config={}, platforms=[],
                composite_logic="XOR",
                composite_conditions=[{"condition_type": "inbox_volume"}],
            )
        assert exc.value.status_code == 400
        assert "must be 'AND' or 'OR'" in exc.value.detail

    def test_composite_created_with_empty_threshold_config(self, db):
        _make_agent(db)
        monitor = _create_monitor(
            db,
            condition_type=CONDITION_TYPE_COMPOSITE,
            composite_logic="AND",
            composite_conditions=[
                {"condition_type": "inbox_volume",
                 "threshold_config": {"metric": "unread_count", "operator": ">", "value": 10}},
            ],
        )
        assert monitor.condition_type == CONDITION_TYPE_COMPOSITE
        assert monitor.composite_logic == "AND"
        assert monitor.status == "active"
        assert monitor.is_active is True
        assert monitor.composite_conditions[0]["condition_type"] == "inbox_volume"

    def test_created_monitor_mirrors_plain_attributes(self, db):
        _make_agent(db)
        monitor = _create_monitor(
            db,
            threshold_config={"metric": "unread_count", "operator": ">", "value": 5},
            platforms=[{"platform": "slack", "recipient_id": "chan-1"}],
            check_interval_seconds=60,
            alert_template="Custom {{value}}",
        )
        assert monitor.threshold_config["value"] == 5
        assert monitor.platforms[0]["platform"] == "slack"
        assert monitor.check_interval_seconds == 60
        assert monitor.alert_template == "Custom {{value}}"
        assert monitor.user_id == "user-1"
        assert monitor.agent_name == "agent-1"


# ============================================================================
# update / pause / resume / delete
# ============================================================================

class TestUpdatePauseResumeDelete:
    def test_update_not_found(self, db):
        with pytest.raises(HTTPException) as exc:
            ConditionMonitoringService(db).update_monitor("nope", name="x")
        assert exc.value.status_code == 404

    def test_update_all_fields(self, db):
        _make_agent(db)
        monitor = _create_monitor(db)
        service = ConditionMonitoringService(db)
        updated = service.update_monitor(
            monitor.id,
            name="Renamed",
            check_interval_seconds=42,
            alert_template="New {{value}}",
            platforms=[{"platform": "discord", "recipient_id": "dc-1"}],
            threshold_config={"metric": "unread_count", "operator": "<", "value": 3},
        )
        assert updated.name == "Renamed"
        assert updated.check_interval_seconds == 42
        assert updated.alert_template == "New {{value}}"
        assert updated.platforms[0]["platform"] == "discord"
        assert updated.threshold_config["operator"] == "<"
        # persisted config was rewritten
        assert updated.condition_config["check_interval_seconds"] == 42
        assert updated.condition_config["platforms"][0]["platform"] == "discord"
        assert updated.condition_config["threshold_config"]["operator"] == "<"

    def test_update_partial_only_name(self, db):
        _make_agent(db)
        monitor = _create_monitor(
            db, threshold_config={"metric": "unread_count", "operator": ">", "value": 5},
        )
        updated = ConditionMonitoringService(db).update_monitor(monitor.id, name="Only name")
        assert updated.name == "Only name"
        assert updated.threshold_config["value"] == 5

    def test_pause_not_found(self, db):
        with pytest.raises(HTTPException) as exc:
            ConditionMonitoringService(db).pause_monitor("nope")
        assert exc.value.status_code == 404

    def test_pause(self, db):
        _make_agent(db)
        monitor = _create_monitor(db)
        paused = ConditionMonitoringService(db).pause_monitor(monitor.id)
        assert paused.is_active is False
        assert paused.status == "paused"

    def test_resume_not_found(self, db):
        with pytest.raises(HTTPException) as exc:
            ConditionMonitoringService(db).resume_monitor("nope")
        assert exc.value.status_code == 404

    def test_resume(self, db):
        _make_agent(db)
        monitor = _create_monitor(db)
        service = ConditionMonitoringService(db)
        service.pause_monitor(monitor.id)
        resumed = service.resume_monitor(monitor.id)
        assert resumed.is_active is True
        assert resumed.status == "active"

    def test_delete_not_found(self, db):
        with pytest.raises(HTTPException) as exc:
            ConditionMonitoringService(db).delete_monitor("nope")
        assert exc.value.status_code == 404

    def test_delete(self, db):
        _make_agent(db)
        monitor = _create_monitor(db)
        deleted = ConditionMonitoringService(db).delete_monitor(monitor.id)
        assert deleted.id == monitor.id
        assert ConditionMonitoringService(db).get_monitor(monitor.id) is None


# ============================================================================
# get_monitors / get_monitor / get_alerts
# ============================================================================

class TestGets:
    def test_get_monitors_filters(self, db):
        _make_agent(db)
        _create_monitor(db, name="inbox", condition_type=CONDITION_TYPE_INBOX_VOLUME,
                        threshold_config={"metric": "unread_count", "operator": ">", "value": 1})
        api_mon = _create_monitor(db, name="api", condition_type=CONDITION_TYPE_API_METRICS,
                                  threshold_config={"metric": "error_rate", "operator": ">", "value": 0.05})
        ConditionMonitoringService(db).pause_monitor(api_mon.id)
        service = ConditionMonitoringService(db)

        all_mons = service.get_monitors()
        assert len(all_mons) == 2

        inbox = service.get_monitors(agent_id="user-1", condition_type=CONDITION_TYPE_INBOX_VOLUME)
        assert len(inbox) == 1
        assert inbox[0].name == "inbox"

        active = service.get_monitors(status="active")
        assert len(active) == 1
        assert active[0].name == "inbox"
        paused = service.get_monitors(status="paused")
        assert len(paused) == 1
        assert paused[0].name == "api"

        empty = service.get_monitors(agent_id="other-agent")
        assert empty == []

    def test_get_monitors_limit(self, db):
        _make_agent(db)
        for i in range(3):
            _create_monitor(db, name=f"m{i}",
                            threshold_config={"metric": "unread_count", "operator": ">", "value": 1})
        assert len(ConditionMonitoringService(db).get_monitors(limit=2)) == 2

    def test_get_monitor_found_and_hydrated(self, db):
        _make_agent(db)
        monitor = _create_monitor(db, threshold_config={"metric": "unread_count", "operator": ">", "value": 7})
        found = ConditionMonitoringService(db).get_monitor(monitor.id)
        assert found is not None
        assert found.threshold_config["value"] == 7
        assert found.status == "active"

    def test_get_monitor_not_found(self, db):
        assert ConditionMonitoringService(db).get_monitor("nope") is None

    def test_get_alerts_filters_and_hydration(self, db):
        _make_agent(db)
        monitor = _create_monitor(db)
        service = ConditionMonitoringService(db)
        alert = ConditionAlert(monitor_id=monitor.id, alert_type="warning",
                               message="boom", is_resolved=False)
        db.add(alert)
        db.commit()

        alerts = service.get_alerts(monitor_id=monitor.id, status="unresolved")
        assert len(alerts) == 1
        assert alerts[0].condition_value == {}
        assert alerts[0].alert_message == "boom"
        assert alerts[0].platforms_sent == []
        assert alerts[0].status == "sent"
        assert alerts[0].sent_at is None
        assert alerts[0].error_message is None

        assert service.get_alerts(status="resolved") == []
        assert len(service.get_alerts()) == 1
        assert len(service.get_alerts(monitor_id="other-mon")) == 0

    def test_get_alerts_limit(self, db):
        _make_agent(db)
        monitor = _create_monitor(db)
        for i in range(3):
            db.add(ConditionAlert(monitor_id=monitor.id, alert_type="warning",
                                  message=f"a{i}", is_resolved=False))
        db.commit()
        assert len(ConditionMonitoringService(db).get_alerts(limit=2)) == 2


# ============================================================================
# check_and_alert_monitors
# ============================================================================

class _FakeCheckers:
    """Configurable stand-in for ConditionCheckers."""

    def __init__(self, result):
        self._result = result

    def check_condition(self, monitor):
        if callable(self._result):
            return self._result(monitor)
        return dict(self._result)


def _patch_checkers(result):
    return patch("core.condition_checkers.ConditionCheckers", return_value=_FakeCheckers(result))


def _make_gateway(status="success", message_id="m-1", error=None, side_effect=None):
    gateway = MagicMock()
    execute = AsyncMock(return_value={"status": status, "message_id": message_id, "error": error})
    if side_effect is not None:
        execute = AsyncMock(side_effect=side_effect)
    gateway.execute_action = execute
    return gateway


class TestCheckAndAlert:
    def test_no_monitors(self, db):
        _make_agent(db)
        result = asyncio.run(ConditionMonitoringService(db).check_and_alert_monitors())
        assert result == {"checked": 0, "triggered": 0, "alerts_sent": 0}

    def test_throttled_skip(self, db):
        _make_agent(db)
        monitor = _create_monitor(db, platforms=[{"platform": "slack", "recipient_id": "c1"}])
        monitor.last_alert_sent_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        with _patch_checkers({"triggered": True, "value": 99, "metric_name": "Unread messages"}):
            result = asyncio.run(ConditionMonitoringService(db).check_and_alert_monitors())
        # 10s < 30min throttle → skipped, no alert row created
        assert result == {"checked": 1, "triggered": 0, "alerts_sent": 0}
        assert db.query(ConditionAlert).count() == 0

    def test_naive_last_alert_timestamp_normalized(self, db):
        _make_agent(db)
        monitor = _create_monitor(db, platforms=[{"platform": "slack", "recipient_id": "c1"}])
        monitor.last_alert_sent_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)
        with _patch_checkers({"triggered": True, "value": 99, "metric_name": "Unread messages"}):
            result = asyncio.run(ConditionMonitoringService(db).check_and_alert_monitors())
        assert result == {"checked": 1, "triggered": 0, "alerts_sent": 0}

    def test_triggered_alert_sent(self, db):
        _make_agent(db)
        monitor = _create_monitor(
            db,
            threshold_config={"metric": "unread_count", "operator": ">", "value": 10},
            platforms=[{"platform": "slack", "recipient_id": "c1"},
                       {"platform": "discord", "recipient_id": "c2"}],
        )
        with _patch_checkers({"triggered": True, "value": 15, "metric_name": "Unread messages"}):
            with patch("core.condition_monitoring_service.agent_integration_gateway",
                       _make_gateway()):
                result = asyncio.run(ConditionMonitoringService(db).check_and_alert_monitors())

        assert result == {"checked": 1, "triggered": 1, "alerts_sent": 2}
        alert = ConditionMonitoringService(db).get_alerts(monitor_id=monitor.id)[0]
        assert alert is not None
        assert alert.status == "sent"
        assert alert.condition_value == 15
        assert alert.platforms_sent[0]["platform"] == "slack"
        assert alert.sent_at is not None
        assert monitor.last_alert_sent_at is not None

    def test_triggered_alert_send_failed(self, db):
        _make_agent(db)
        monitor = _create_monitor(db, platforms=[{"platform": "slack", "recipient_id": "c1"}])
        with _patch_checkers({"triggered": True, "value": 15, "metric_name": "Unread messages"}):
            with patch("core.condition_monitoring_service.agent_integration_gateway",
                       _make_gateway(status="failed", error="channel closed")):
                result = asyncio.run(ConditionMonitoringService(db).check_and_alert_monitors())

        assert result == {"checked": 1, "triggered": 1, "alerts_sent": 0}
        alert = ConditionMonitoringService(db).get_alerts(monitor_id=monitor.id)[0]
        assert alert.status == "failed"
        assert alert.error_message == "Failed to send to any platform"

    def test_not_triggered_no_alert(self, db):
        _make_agent(db)
        _create_monitor(db, platforms=[{"platform": "slack", "recipient_id": "c1"}])
        with _patch_checkers({"triggered": False, "value": 1, "metric_name": "Unread messages"}):
            result = asyncio.run(ConditionMonitoringService(db).check_and_alert_monitors())
        assert result == {"checked": 1, "triggered": 0, "alerts_sent": 0}
        assert db.query(ConditionAlert).count() == 0

    def test_throttle_persists_across_runs_via_column(self, db):
        _make_agent(db)
        monitor = _create_monitor(db, platforms=[{"platform": "slack", "recipient_id": "c1"}])
        with _patch_checkers({"triggered": True, "value": 15, "metric_name": "Unread messages"}):
            with patch("core.condition_monitoring_service.agent_integration_gateway",
                       _make_gateway()):
                first = asyncio.run(ConditionMonitoringService(db).check_and_alert_monitors())
        assert first["alerts_sent"] == 1
        assert db.query(ConditionAlert).count() == 1
        # second run: last_alert_sent_at is now a real column → throttled
        with _patch_checkers({"triggered": True, "value": 15, "metric_name": "Unread messages"}):
            with patch("core.condition_monitoring_service.agent_integration_gateway",
                       _make_gateway()):
                second = asyncio.run(ConditionMonitoringService(db).check_and_alert_monitors())
        assert second == {"checked": 1, "triggered": 0, "alerts_sent": 0}
        assert db.query(ConditionAlert).count() == 1

    def test_checker_exception_swallowed(self, db):
        _make_agent(db)
        _create_monitor(db, platforms=[{"platform": "slack", "recipient_id": "c1"}])

        def boom(monitor):
            raise RuntimeError("checker exploded")

        with _patch_checkers(boom):
            result = asyncio.run(ConditionMonitoringService(db).check_and_alert_monitors())
        assert result == {"checked": 1, "triggered": 0, "alerts_sent": 0}


# ============================================================================
# _generate_alert_message / _send_alert
# ============================================================================

class TestGenerateAlertMessage:
    def _alert(self):
        return ConditionAlert(monitor_id="m", alert_type="warning", message="x", is_resolved=False)

    def test_template_substitution(self, db):
        monitor = MagicMock()
        monitor.alert_template = "Value {{value}} vs threshold {{threshold}}"
        monitor.threshold_config = {"metric": "m", "operator": ">", "value": 5}
        msg = ConditionMonitoringService(db)._generate_alert_message(
            monitor, {"value": 12, "metric_name": "X"})
        assert "Value 12 vs threshold {'metric': 'm', 'operator': '>', 'value': 5}" == msg

    def test_default_with_metric_name(self, db):
        monitor = MagicMock()
        monitor.alert_template = None
        monitor.threshold_config = {"metric": "m", "operator": ">", "value": 5}
        monitor.name = "Mon"
        msg = ConditionMonitoringService(db)._generate_alert_message(
            monitor, {"value": 12, "metric_name": "Unread messages"})
        assert "Unread messages is 12 (threshold: > 5)" in msg

    def test_default_without_metric_name(self, db):
        monitor = MagicMock()
        monitor.alert_template = None
        monitor.threshold_config = {"metric": "m", "operator": ">", "value": 5}
        monitor.name = "My Monitor"
        msg = ConditionMonitoringService(db)._generate_alert_message(
            monitor, {"value": 12, "metric_name": ""})
        assert "Condition 'My Monitor' triggered (value: 12, threshold: > 5)" in msg


class TestSendAlert:
    def _alert(self, message="hi"):
        return ConditionAlert(monitor_id="m", alert_type="warning", message=message,
                              is_resolved=False)

    async def _run(self, db, monitor, alert, result=None, side_effect=None, status="success"):
        gateway = MagicMock()
        execute = AsyncMock(
            return_value={"status": status, "message_id": "mid", "error": "e"}) \
            if result is None else AsyncMock(return_value=result)
        if side_effect is not None:
            execute = AsyncMock(side_effect=side_effect)
        gateway.execute_action = execute
        with patch("core.condition_monitoring_service.agent_integration_gateway", gateway):
            sent = await ConditionMonitoringService(db)._send_alert(monitor, alert, {})
        return sent, execute

    def test_invalid_platform_config_skipped(self, db):
        monitor = MagicMock()
        monitor.platforms = [{"platform": "slack"}, {"recipient_id": "only"}]
        alert = self._alert()
        sent, execute = asyncio.run(self._run(db, monitor, alert))
        assert sent == 0
        assert execute.await_count == 0
        assert alert.platforms_sent == []

    def test_success_and_failure_mixed(self, db):
        monitor = MagicMock()
        monitor.platforms = [{"platform": "slack", "recipient_id": "c1"},
                             {"platform": "teams", "recipient_id": "c2"}]

        async def fake_execute(action_type, platform, params):
            if platform == "teams":
                return {"status": "failed", "error": "rate limited"}
            return {"status": "success", "message_id": "m-1"}

        gateway = MagicMock()
        gateway.execute_action = fake_execute
        alert = self._alert("content")
        with patch("core.condition_monitoring_service.agent_integration_gateway", gateway):
            sent = asyncio.run(ConditionMonitoringService(db)._send_alert(monitor, alert, {}))

        assert sent == 1
        assert alert.platforms_sent[0]["status"] == "sent"
        assert alert.platforms_sent[1]["status"] == "failed"

    def test_gateway_exception(self, db):
        monitor = MagicMock()
        monitor.platforms = [{"platform": "slack", "recipient_id": "c1"}]
        alert = self._alert()
        sent, _ = asyncio.run(self._run(db, monitor, alert, side_effect=RuntimeError("down")))
        assert sent == 0
        assert alert.platforms_sent[0]["status"] == "error"
        assert "down" in alert.platforms_sent[0]["error"]


# ============================================================================
# test_condition / presets
# ============================================================================

class TestMisc:
    def test_test_condition_not_found(self, db):
        with pytest.raises(HTTPException) as exc:
            ConditionMonitoringService(db).test_condition("nope")
        assert exc.value.status_code == 404

    def test_test_condition_result(self, db):
        _make_agent(db)
        monitor = _create_monitor(db, threshold_config={"metric": "unread_count", "operator": ">", "value": 0})
        with _patch_checkers({"triggered": False, "value": 0, "metric_name": "Unread messages"}):
            result = ConditionMonitoringService(db).test_condition(monitor.id)
        assert result["monitor_id"] == monitor.id
        assert result["condition_type"] == CONDITION_TYPE_INBOX_VOLUME
        assert result["triggered"] is False
        assert result["current_value"] == 0
        assert result["threshold"]["value"] == 0

    def test_get_presets(self, db):
        presets = ConditionMonitoringService(db).get_presets()
        assert len(presets) == 4
        names = {p["name"] for p in presets}
        assert names == {
            "High Inbox Volume", "Task Backlog", "High API Error Rate",
            "Database Connection Pool",
        }
        assert presets[0]["threshold_config"]["operator"] == ">"
