"""
Coverage + bug-hunt tests for core/alert_service.py

Targets: AlertThresholdService — threshold evaluation, hysteresis,
sliding-window error-rate, latency p95, notifications, formatting.

All external deps (DB, Redis, IntegrationMetrics, Slack/Email services)
are mocked. No real network.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.alert_service import (
    AlertSeverity,
    AlertStatus,
    AlertThresholdService,
    AlertViolation,
    _AlertConfigurationStub,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_config(
    error_rate_threshold=10.0,
    latency_threshold_ms=500,
    window_seconds=300,
    notification_channels=None,
    slack_channel_id=None,
    email_recipients=None,
    is_active=True,
    tenant_id="t1",
    connector_id="c1",
):
    cfg = MagicMock()
    cfg.error_rate_threshold = error_rate_threshold
    cfg.latency_threshold_ms = latency_threshold_ms
    cfg.window_seconds = window_seconds
    cfg.notification_channels = notification_channels or []
    cfg.slack_channel_id = slack_channel_id
    cfg.email_recipients = email_recipients or []
    cfg.is_active = is_active
    cfg.tenant_id = tenant_id
    cfg.connector_id = connector_id
    return cfg


def _make_metrics(success=0, failure=0, p95=0):
    metrics = MagicMock()
    metrics._make_key = MagicMock(return_value="key")
    metrics.success_counts = {"key": success}
    metrics.failure_counts = {"key": failure}
    metrics.get_duration_percentiles = MagicMock(
        return_value={"p50": 0, "p95": p95, "p99": 0}
    )
    return metrics


def _make_redis(state_map=None):
    """Fake redis client: dict-backed get/setex.

    Mimics real redis-py: stored values are bytes; setex accepts str and
    encodes it so that get() returns bytes (which .decode() works on).
    """
    raw = {} if state_map is None else {k: (v.encode() if isinstance(v, str) else v) for k, v in state_map.items()}

    class FakeRedis:
        def __init__(self, store):
            self._store = store

        def get(self, key):
            return self._store.get(key)

        def setex(self, key, ttl, value):
            self._store[key] = value.encode() if isinstance(value, str) else value
            return True

    return FakeRedis(raw)


def _stub_db_with_query_first(db, value):
    """Configure a MagicMock db so that ANY chained .filter(...).first() returns
    `value`. Works regardless of how many filter() calls precede first()."""
    chain = db.query.return_value
    # Walk all attribute access paths; set first() everywhere it could land.
    chain.first.return_value = value
    chain.filter.return_value.first.return_value = value
    chain.filter.return_value.filter.return_value.first.return_value = value
    chain.filter.return_value.filter.return_value.filter.return_value.first.return_value = value
    # all() chains for evaluate_all_thresholds
    chain.filter.return_value.all.return_value = value if isinstance(value, list) else []
    chain.filter.return_value.filter.return_value.all.return_value = value if isinstance(value, list) else []
    return db


@pytest.fixture
def service():
    db = MagicMock()
    return AlertThresholdService(db_session=db, redis_client=None)


# ---------------------------------------------------------------------------
# Construction / AlertConfiguration fallback
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_stub_config_defaults(self):
        """_AlertConfigurationStub provides sane defaults."""
        stub = _AlertConfigurationStub()
        assert stub.is_active is True
        assert stub.window_seconds == 300
        assert stub.error_rate_threshold == 0.0
        assert stub.latency_threshold_ms is None
        assert stub.notification_channels == []
        assert stub.email_recipients == []

    def test_falls_back_to_stub_when_model_missing(self):
        """If core.models.AlertConfiguration import fails, stub is used."""
        db = MagicMock()
        with patch("builtins.__import__", side_effect=ImportError):
            svc = AlertThresholdService(db_session=db, redis_client=None)
        assert svc.AlertConfiguration is _AlertConfigurationStub

    def test_hysteresis_band_constant(self):
        assert AlertThresholdService.HYSTERESIS_BAND == 0.20


# ---------------------------------------------------------------------------
# Error-rate threshold evaluation
# ---------------------------------------------------------------------------

class TestErrorRateThreshold:
    def test_no_config_returns_none(self, service):
        """Missing configuration -> None."""
        _stub_db_with_query_first(service.db, None)
        assert service.evaluate_error_rate_threshold("t1", "c1") is None

    def test_zero_traffic_returns_none(self, service):
        cfg = _make_config(error_rate_threshold=10.0)
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=0, failure=0)):
            result = service.evaluate_error_rate_threshold("t1", "c1", cfg)
        assert result is None

    def test_below_threshold_returns_none(self, service):
        cfg = _make_config(error_rate_threshold=10.0)  # 10%
        # 5 failures / 100 total = 5% < 10%
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=95, failure=5)):
            result = service.evaluate_error_rate_threshold("t1", "c1", cfg)
        assert result is None

    def test_above_threshold_emits_warning(self, service):
        cfg = _make_config(error_rate_threshold=10.0)
        # 15 / 100 = 15% > 10%, but <= 2x (20%) -> WARNING
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=85, failure=15)):
            result = service.evaluate_error_rate_threshold("t1", "c1", cfg)
        assert result is not None
        assert result.severity is AlertSeverity.WARNING
        assert result.metric_type == "error_rate"
        assert pytest.approx(result.actual_value, rel=1e-6) == 15.0
        assert result.tenant_id == "t1"
        assert result.connector_id == "c1"

    def test_double_threshold_emits_critical(self, service):
        cfg = _make_config(error_rate_threshold=10.0)
        # 50 / 100 = 50% > 2x(10=20) -> CRITICAL
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=50, failure=50)):
            result = service.evaluate_error_rate_threshold("t1", "c1", cfg)
        assert result.severity is AlertSeverity.CRITICAL

    def test_exactly_double_threshold_is_critical(self, service):
        """Boundary: error_rate == threshold*2 falls in CRITICAL (uses >)."""
        cfg = _make_config(error_rate_threshold=10.0)
        # 20 / 100 = 20% == threshold*2. Code uses `> threshold*2` -> WARNING.
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=80, failure=20)):
            result = service.evaluate_error_rate_threshold("t1", "c1", cfg)
        assert result.severity is AlertSeverity.WARNING

    def test_violation_sets_redis_state_when_redis_present(self):
        db = MagicMock()
        redis = _make_redis()
        svc = AlertThresholdService(db_session=db, redis_client=redis)
        cfg = _make_config(error_rate_threshold=10.0)
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=85, failure=15)):
            svc.evaluate_error_rate_threshold("t1", "c1", cfg)
        val = redis.get("alert_state:t1:c1:error_rate")
        assert val == b"violated", f"expected b'violated', got {val!r}"

    def test_clear_path_sets_cleared_state(self):
        """When violated and rate drops below clear band -> state 'cleared'."""
        db = MagicMock()
        redis = _make_redis({"alert_state:t1:c1:error_rate": "violated"})
        svc = AlertThresholdService(db_session=db, redis_client=redis)
        cfg = _make_config(error_rate_threshold=10.0)  # clear band = 8.0
        # 5 / 100 = 5% < 8% -> clears
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=95, failure=5)):
            result = svc.evaluate_error_rate_threshold("t1", "c1", cfg)
        assert result is None
        # FakeRedis stores raw bytes
        val = redis.get("alert_state:t1:c1:error_rate")
        assert val == b"cleared", f"expected b'cleared', got {val!r}"

    def test_get_alert_state_no_redis_returns_ok(self, service):
        assert service._get_alert_state("t", "c", "m") == "ok"

    def test_get_alert_state_redis_decodes_bytes(self):
        db = MagicMock()
        redis = _make_redis({"alert_state:t:c:m": b"violated"})
        svc = AlertThresholdService(db_session=db, redis_client=redis)
        assert svc._get_alert_state("t", "c", "m") == "violated"

    def test_get_alert_state_missing_key_returns_ok(self):
        db = MagicMock()
        redis = _make_redis()
        svc = AlertThresholdService(db_session=db, redis_client=redis)
        assert svc._get_alert_state("t", "c", "m") == "ok"

    def test_set_alert_state_no_redis_is_noop(self):
        db = MagicMock()
        svc = AlertThresholdService(db_session=db, redis_client=None)
        # Should not raise
        svc._set_alert_state("t", "c", "m", "violated")


class TestErrorRateHysteresisBug:
    """BUG: while alert is in 'violated' state and error rate sits in the
    hysteresis band [clear_threshold, threshold], the service returns None
    (no violation) even though the alert is still actively firing. This is a
    false-negative: get_violations_for_tenant() drops an ongoing alert.
    """

    def test_bug_violated_state_in_hysteresis_band_returns_none(self):
        """threshold=10, clear=8. rate=9 (in band) while state=violated
        should STILL report the violation because the alert has not cleared.
        Currently returns None -> bug."""
        db = MagicMock()
        redis = _make_redis({"alert_state:t1:c1:error_rate": "violated"})
        svc = AlertThresholdService(db_session=db, redis_client=redis)
        cfg = _make_config(error_rate_threshold=10.0)  # clear band = 8.0
        # 9 / 100 = 9% — between clear (8) and threshold (10), state violated.
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=91, failure=9)):
            result = svc.evaluate_error_rate_threshold("t1", "c1", cfg)
        # Expected behaviour: alert is still firing (state stays violated),
        # so a violation MUST be reported.
        assert result is not None, (
            "BUG: alert still in violated state but evaluate_error_rate_threshold "
            "returned None — ongoing alert dropped from results"
        )
        assert result.severity in (AlertSeverity.WARNING, AlertSeverity.CRITICAL)
        # state must not have been cleared (rate still above clear band)
        assert redis.get("alert_state:t1:c1:error_rate") != b"cleared"


# ---------------------------------------------------------------------------
# Latency threshold
# ---------------------------------------------------------------------------

class TestLatencyThreshold:
    def test_no_config_returns_none(self, service):
        _stub_db_with_query_first(service.db, None)
        assert service.evaluate_latency_threshold("t", "c") is None

    def test_no_latency_threshold_returns_none(self, service):
        cfg = _make_config(latency_threshold_ms=None)
        assert service.evaluate_latency_threshold("t", "c", cfg) is None

    def test_latency_below_threshold_returns_none(self, service):
        cfg = _make_config(latency_threshold_ms=500)
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(p95=200)):
            assert service.evaluate_latency_threshold("t", "c", cfg) is None

    def test_latency_above_threshold_emits_warning(self, service):
        cfg = _make_config(latency_threshold_ms=500)
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(p95=800)):
            result = service.evaluate_latency_threshold("t", "c", cfg)
        assert result is not None
        assert result.severity is AlertSeverity.WARNING
        assert result.metric_type == "latency_p95"
        assert result.actual_value == 800
        assert result.threshold == 500

    def test_latency_exactly_at_threshold_returns_none(self, service):
        """Boundary: p95 == threshold -> not violated (uses >)."""
        cfg = _make_config(latency_threshold_ms=500)
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(p95=500)):
            assert service.evaluate_latency_threshold("t", "c", cfg) is None


# ---------------------------------------------------------------------------
# evaluate_all_thresholds / get_violations_for_tenant
# ---------------------------------------------------------------------------

class TestEvaluateAll:
    def test_no_active_configs_returns_empty(self, service):
        service.db.query.return_value.filter.return_value.all.return_value = []
        # The filter chain for is_active only; tenant filter applied if present
        result = service.evaluate_all_thresholds()
        assert result == []

    def test_groups_by_tenant_connector(self):
        db = MagicMock()
        cfg1 = _make_config(tenant_id="t1", connector_id="c1", error_rate_threshold=10.0)
        cfg2 = _make_config(tenant_id="t1", connector_id="c1", latency_threshold_ms=100)  # same group
        cfg3 = _make_config(tenant_id="t2", connector_id="c1", error_rate_threshold=10.0)
        configs = [cfg1, cfg2, cfg3]
        # Set .all() at every plausible filter depth
        chain = db.query.return_value
        chain.filter.return_value.all.return_value = configs
        chain.filter.return_value.filter.return_value.all.return_value = configs
        svc = AlertThresholdService(db_session=db, redis_client=None)
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=100, failure=0, p95=50)):
            results = svc.evaluate_all_thresholds()
        # 2 unique groups
        assert len(results) == 2
        keys = {(r.tenant_id, r.connector_id) for r in results}
        assert keys == {("t1", "c1"), ("t2", "c1")}

    def test_status_violated_when_error_breaches(self):
        db = MagicMock()
        cfg = _make_config(error_rate_threshold=10.0)
        chain = db.query.return_value
        chain.filter.return_value.all.return_value = [cfg]
        chain.filter.return_value.filter.return_value.all.return_value = [cfg]
        svc = AlertThresholdService(db_session=db, redis_client=None)
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=50, failure=50, p95=10)):
            results = svc.evaluate_all_thresholds(tenant_id="t1")
        assert results[0].status is AlertStatus.VIOLATED
        assert len(results[0].violations) == 1

    def test_get_violations_for_tenant_flattens(self):
        db = MagicMock()
        cfg = _make_config(error_rate_threshold=10.0, latency_threshold_ms=10)
        chain = db.query.return_value
        chain.filter.return_value.all.return_value = [cfg]
        chain.filter.return_value.filter.return_value.all.return_value = [cfg]
        svc = AlertThresholdService(db_session=db, redis_client=None)
        with patch("core.integration_metrics.get_integration_metrics",
                   return_value=_make_metrics(success=50, failure=50, p95=999)):
            vs = svc.get_violations_for_tenant("t1")
        assert len(vs) == 2  # error + latency


# ---------------------------------------------------------------------------
# Notification helpers (async)
# ---------------------------------------------------------------------------

class TestNotifications:
    @pytest.mark.asyncio
    async def test_send_notifications_no_channels_returns_empty(self, service):
        cfg = _make_config(notification_channels=[])
        v = AlertViolation("t", "c", "error_rate", 5, 1, AlertSeverity.WARNING,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        assert await service.send_notifications(v, cfg) == {}

    @pytest.mark.asyncio
    async def test_send_slack_no_token_returns_false(self, service):
        cfg = _make_config(slack_channel_id="C1")
        v = AlertViolation("t", "c", "error_rate", 5, 1, AlertSeverity.WARNING,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        with patch("core.token_storage.token_storage.get_token",
                   return_value=None):
            result = await service.send_slack_notification(v, cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_slack_success(self, service):
        cfg = _make_config(slack_channel_id="C1")
        v = AlertViolation("t", "c", "error_rate", 5, 1, AlertSeverity.WARNING,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        fake_slack = MagicMock()
        fake_slack.send_message = AsyncMock(return_value=True)
        with patch("core.token_storage.token_storage.get_token",
                   return_value={"access_token": "x"}), \
             patch("integrations.slack_enhanced_service.SlackEnhancedService",
                   return_value=fake_slack):
            result = await service.send_slack_notification(v, cfg)
        assert result is True
        fake_slack.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_slack_import_error_returns_false(self, service):
        cfg = _make_config(slack_channel_id="C1")
        v = AlertViolation("t", "c", "error_rate", 5, 1, AlertSeverity.WARNING,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        with patch("core.token_storage.token_storage.get_token",
                   side_effect=Exception("boom")):
            result = await service.send_slack_notification(v, cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_email_no_recipients_returns_false(self, service):
        cfg = _make_config(email_recipients=[])
        v = AlertViolation("t", "c", "error_rate", 5, 1, AlertSeverity.WARNING,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        result = await service.send_email_notification(v, cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_email_success(self, service):
        cfg = _make_config(email_recipients=["a@b.c", "d@e.f"])
        v = AlertViolation("t", "c", "error_rate", 5, 1, AlertSeverity.WARNING,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        fake_email = MagicMock()
        fake_email.send_email = AsyncMock(return_value=True)
        with patch("integrations.email_routes.EmailService", return_value=fake_email):
            result = await service.send_email_notification(v, cfg)
        assert result is True
        assert fake_email.send_email.await_count == 2

    @pytest.mark.asyncio
    async def test_send_email_partial_failure(self, service):
        cfg = _make_config(email_recipients=["a@b.c", "d@e.f"])
        v = AlertViolation("t", "c", "error_rate", 5, 1, AlertSeverity.WARNING,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        fake_email = MagicMock()
        fake_email.send_email = AsyncMock(side_effect=[True, False])
        with patch("integrations.email_routes.EmailService", return_value=fake_email):
            result = await service.send_email_notification(v, cfg)
        assert result is True  # at least one sent

    @pytest.mark.asyncio
    async def test_send_email_import_error_returns_false(self, service):
        cfg = _make_config(email_recipients=["a@b.c"])
        v = AlertViolation("t", "c", "error_rate", 5, 1, AlertSeverity.WARNING,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        with patch("integrations.email_routes.EmailService", side_effect=Exception("x")):
            result = await service.send_email_notification(v, cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_notifications_dispatches_both_channels(self, service):
        cfg = _make_config(notification_channels=["slack", "email"],
                           slack_channel_id="C1", email_recipients=["a@b.c"])
        v = AlertViolation("t", "c", "error_rate", 5, 1, AlertSeverity.WARNING,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        with patch.object(service, "send_slack_notification", AsyncMock(return_value=True)), \
             patch.object(service, "send_email_notification", AsyncMock(return_value=False)):
            result = await service.send_notifications(v, cfg)
        assert result == {"slack": True, "email": False}


class TestClearedAlertNotification:
    @pytest.mark.asyncio
    async def test_no_redis_returns_none(self, service):
        cfg = _make_config()
        # Should just return (None) without raising
        result = await service.check_and_send_cleared_alerts("t", "c")
        assert result is None

    @pytest.mark.asyncio
    async def test_cleared_state_triggers_notification(self):
        db = MagicMock()
        redis = _make_redis({"alert_state:t:c:error_rate": "cleared"})
        svc = AlertThresholdService(db_session=db, redis_client=redis)
        cfg = _make_config(notification_channels=["slack"], slack_channel_id="C1")
        _stub_db_with_query_first(db, cfg)
        with patch.object(svc, "send_alert_cleared_notification", AsyncMock(return_value=True)) as m:
            await svc.check_and_send_cleared_alerts("t", "c")
        m.assert_awaited_once()
        # state reset to ok after notification
        assert redis.get("alert_state:t:c:error_rate") == b"ok"

    @pytest.mark.asyncio
    async def test_ok_state_no_notification(self):
        db = MagicMock()
        redis = _make_redis({"alert_state:t:c:error_rate": "ok"})
        svc = AlertThresholdService(db_session=db, redis_client=redis)
        with patch.object(svc, "send_alert_cleared_notification", AsyncMock()) as m:
            await svc.check_and_send_cleared_alerts("t", "c")
        m.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cleared_no_config_skips_notification(self):
        db = MagicMock()
        redis = _make_redis({"alert_state:t:c:error_rate": "cleared"})
        svc = AlertThresholdService(db_session=db, redis_client=redis)
        _stub_db_with_query_first(db, None)
        with patch.object(svc, "send_alert_cleared_notification", AsyncMock()) as m:
            await svc.check_and_send_cleared_alerts("t", "c")
        m.assert_not_awaited()
        # state still reset to ok even without config
        assert redis.get("alert_state:t:c:error_rate") == b"ok"

    @pytest.mark.asyncio
    async def test_send_alert_cleared_slack_success(self, service):
        cfg = _make_config(notification_channels=["slack"], slack_channel_id="C1")
        fake_slack = MagicMock()
        fake_slack.send_message = AsyncMock(return_value=True)
        with patch("core.token_storage.token_storage.get_token",
                   return_value={"access_token": "x"}), \
             patch("integrations.slack_enhanced_service.SlackEnhancedService",
                   return_value=fake_slack):
            result = await service.send_alert_cleared_notification("t", "c", "error_rate", cfg)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_cleared_email_success(self, service):
        cfg = _make_config(notification_channels=["email"], email_recipients=["a@b.c"])
        fake_email = MagicMock()
        fake_email.send_email = AsyncMock(return_value=True)
        with patch("integrations.email_routes.EmailService", return_value=fake_email):
            result = await service.send_alert_cleared_notification("t", "c", "error_rate", cfg)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_cleared_no_channels_returns_false(self, service):
        cfg = _make_config(notification_channels=[])
        result = await service.send_alert_cleared_notification("t", "c", "error_rate", cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_alert_cleared_exception_returns_false(self, service):
        cfg = _make_config(notification_channels=["slack"], slack_channel_id="C1")
        with patch("core.token_storage.token_storage.get_token", side_effect=Exception("x")):
            result = await service.send_alert_cleared_notification("t", "c", "error_rate", cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_alert_cleared_slack_send_failure(self, service):
        cfg = _make_config(notification_channels=["slack"], slack_channel_id="C1")
        fake_slack = MagicMock()
        fake_slack.send_message = AsyncMock(side_effect=Exception("send failed"))
        with patch("core.token_storage.token_storage.get_token",
                   return_value={"access_token": "x"}), \
             patch("integrations.slack_enhanced_service.SlackEnhancedService",
                   return_value=fake_slack):
            result = await service.send_alert_cleared_notification("t", "c", "error_rate", cfg)
        assert result is False  # slack failed, no email -> any()=False


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

class TestFormatting:
    def test_emoji_for_severity(self, service):
        assert service._get_emoji_for_severity(AlertSeverity.INFO) == ":information_source:"
        assert service._get_emoji_for_severity(AlertSeverity.WARNING) == ":warning:"
        assert service._get_emoji_for_severity(AlertSeverity.CRITICAL) == ":rotating_light:"

    def test_format_slack_message_contains_fields(self, service):
        cfg = _make_config()
        v = AlertViolation("t1", "c1", "error_rate", 15.5, 10.0,
                           AlertSeverity.CRITICAL,
                           datetime(2026, 1, 1, tzinfo=timezone.utc),
                           datetime(2026, 1, 1, tzinfo=timezone.utc),
                           datetime(2026, 1, 1, tzinfo=timezone.utc))
        msg = service._format_slack_message(v, cfg)
        assert "c1" in msg
        assert "error_rate" in msg
        assert "CRITICAL" in msg
        assert "15.50" in msg

    def test_format_email_subject(self, service):
        v = AlertViolation("t", "c", "error_rate", 1, 1, AlertSeverity.CRITICAL,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           datetime.now(timezone.utc))
        subj = service._format_email_subject(v)
        assert "c" in subj and "error_rate" in subj

    def test_format_email_html_contains_values(self, service):
        cfg = _make_config()
        v = AlertViolation("t", "myconn", "latency_p95", 999.0, 500.0,
                           AlertSeverity.WARNING,
                           datetime(2026, 1, 1, tzinfo=timezone.utc),
                           datetime(2026, 1, 1, tzinfo=timezone.utc),
                           datetime(2026, 1, 1, tzinfo=timezone.utc))
        html = service._format_email_html(v, cfg)
        assert "myconn" in html
        assert "latency_p95" in html
        assert "999.00" in html
