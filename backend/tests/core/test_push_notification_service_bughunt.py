"""
Bug-hunt tests for core/push_notification_service.py.

Run:
  cd backend && venv/bin/python -m pytest \
      tests/core/test_push_notification_service_bughunt.py -v
"""
import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_device(platform="android", device_token="token-xyz", device_id="dev-1"):
    return SimpleNamespace(
        id=device_id,
        user_id="u-1",
        tenant_id=None,
        platform=platform,
        device_token=device_token,
        status="active",
    )


def _service_with_one_device(db, device):
    """Patch the device query inside send_notification to return exactly `device`."""
    db.query.return_value.filter.return_value.all.return_value = [device]
    # If tenant_id branch adds a second filter, make it a no-op passthrough.
    db.query.return_value.filter.return_value.filter.return_value.all.return_value = [device]


@pytest.fixture(autouse=True)
def _enable_push(monkeypatch):
    monkeypatch.setenv("PUSH_NOTIFICATIONS_ENABLED", "true")


# =============================================================================
# BUG: critical/warning severity alerts never get high-priority FCM/APNs routing
# =============================================================================
@pytest.mark.asyncio
async def test_bug_critical_error_alert_gets_high_priority_fcm():
    """BUG: send_error_alert(severity='critical') passes priority='critical'
    to _send_fcm_notification, which only treats priority=='high' as urgent.
    Critical alerts therefore lose high-priority Android routing.

    Fix: map severity into the FCM priority ('high' for critical/warning/error,
    else 'normal') so urgent alerts are delivered promptly.
    """
    from core.push_notification_service import PushNotificationService

    db = MagicMock()
    svc = PushNotificationService(db)
    device = _make_device(platform="android")

    # Force send_notification to actually reach the FCM path with this one device.
    db.query.return_value.filter.return_value.all.return_value = [device]
    db.query.return_value.filter.return_value.filter.return_value.all.return_value = [device]

    captured = {}

    async def fake_fcm(dev, title, body, data, priority):
        captured["priority"] = priority
        return True

    with patch.object(svc, "_send_fcm_notification", side_effect=fake_fcm):
        await svc.send_error_alert(
            user_id="u-1",
            error_type="DB_DOWN",
            error_message="Primary DB unreachable",
            severity="critical",
        )

    assert captured.get("priority") == "high", (
        "critical severity alerts must be routed as FCM high priority, got "
        f"{captured.get('priority')!r}"
    )


@pytest.mark.asyncio
async def test_bug_warning_system_alert_gets_high_priority_fcm():
    """BUG: send_system_alert(severity='warning') passes priority='warning'
    to _send_fcm_notification, which only honors priority=='high'. Warning-level
    system alerts (CPU threshold, queue depth, integration health) therefore
    lose high-priority delivery.

    Fix: warning (and critical) system alerts should be routed as FCM 'high'.
    """
    from core.push_notification_service import PushNotificationService

    db = MagicMock()
    svc = PushNotificationService(db)
    device = _make_device(platform="android")

    db.query.return_value.filter.return_value.all.return_value = [device]
    db.query.return_value.filter.return_value.filter.return_value.all.return_value = [device]

    captured = {}

    async def fake_fcm(dev, title, body, data, priority):
        captured["priority"] = priority
        return True

    with patch.object(svc, "_send_fcm_notification", side_effect=fake_fcm):
        await svc.send_system_alert(
            user_id="u-1",
            alert_type="high_cpu",
            message="CPU at 92%",
            severity="warning",
        )

    assert captured.get("priority") == "high", (
        "warning system alerts must be routed as FCM high priority, got "
        f"{captured.get('priority')!r}"
    )
