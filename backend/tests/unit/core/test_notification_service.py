"""
P2.1 regression tests — notification service unstub + graduation hook.

Verifies:
- send_notification persists a Notification row with default workspace/tenant.
- Signature unchanged: async send_notification(user_id, type, data).
- Email is OPT-IN: not sent by default, sent when user opts in.
- send_notification never raises (soft-fail on db missing).
- _user_email_enabled reads from notification_preferences["email_enabled"].

Run: PYTHONPATH=backend pytest backend/tests/unit/core/test_notification_service.py -v
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_db():
    """In-memory-ish DB that records added rows in self.added."""
    db = MagicMock()
    db.added = []

    def _add(obj):
        db.added.append(obj)
        # Simulate refresh assigning an id.
        obj.id = f"notif-{len(db.added)}"

    db.add.side_effect = _add
    return db


def _make_user(*, email_enabled=False, email="user@example.com"):
    """Build a lightweight user stand-in with a dict-style preferences field."""
    prefs = {"email_enabled": True} if email_enabled else {}
    return SimpleNamespace(
        id="u-1",
        email=email,
        notification_preferences=prefs,
    )


# =============================================================================
# Persistence + signature
# =============================================================================

def test_send_notification_persists_with_default_workspace(fake_db):
    """A row must be written with workspace_id='default' when caller omits it."""
    from core.notification_service import NotificationService

    svc = NotificationService(fake_db)
    result = asyncio.run(svc.send_notification(
        user_id="u-1",
        notification_type="agent_graduated",
        data={"title": "T", "message": "M"},
    ))

    assert result["success"] is True
    assert result["notification_id"] == "notif-1"
    assert len(fake_db.added) == 1
    row = fake_db.added[0]
    assert row.workspace_id == "default"
    assert row.tenant_id == "default"
    assert row.read is False
    assert row.user_id == "u-1"


def test_send_notification_signature_unchanged(fake_db):
    """Constructor + send_notification(user_id, type, data) shape must match stub."""
    from core.notification_service import NotificationService

    svc = NotificationService(fake_db)
    # Must be awaitable with the exact 3 positional args.
    result = asyncio.run(svc.send_notification("u-1", "info", {"title": "x"}))
    assert isinstance(result, dict)


def test_send_notification_classifies_graduation_as_success(fake_db):
    """agent_graduated should classify as type='success' (drives UI styling)."""
    from core.notification_service import NotificationService

    svc = NotificationService(fake_db)
    asyncio.run(svc.send_notification(
        user_id="u-1",
        notification_type="agent_graduated",
        data={"title": "x", "message": "y"},
    ))
    assert fake_db.added[0].type == "success"


# =============================================================================
# Email opt-in semantics
# =============================================================================

def test_email_not_sent_when_user_has_not_opted_in(fake_db):
    """Default user must NOT receive email even for high-priority notifications."""
    from core.notification_service import NotificationService

    fake_db.query.return_value.filter.return_value.first.return_value = _make_user(email_enabled=False)

    svc = NotificationService(fake_db)
    with patch("core.email_utils.send_smtp_email") as mock_smtp:
        asyncio.run(svc.send_notification(
            user_id="u-1",
            notification_type="agent_graduated",
            data={"title": "T", "message": "M"},
        ))
        mock_smtp.assert_not_called()


def test_email_sent_when_user_opts_in(fake_db):
    """Opted-in user + high-priority type must trigger send_smtp_email."""
    from core.notification_service import NotificationService

    fake_db.query.return_value.filter.return_value.first.return_value = _make_user(email_enabled=True)

    svc = NotificationService(fake_db)
    with patch("core.email_utils.send_smtp_email", return_value=True) as mock_smtp:
        result = asyncio.run(svc.send_notification(
            user_id="u-1",
            notification_type="agent_graduated",
            data={"title": "T", "message": "M"},
        ))
        mock_smtp.assert_called_once()
        assert result["emailed"] is True


def test_email_not_sent_for_low_priority_type_even_when_opted_in(fake_db):
    """Regular 'info' notifications must not email even if opted in."""
    from core.notification_service import NotificationService

    fake_db.query.return_value.filter.return_value.first.return_value = _make_user(email_enabled=True)

    svc = NotificationService(fake_db)
    with patch("core.email_utils.send_smtp_email") as mock_smtp:
        asyncio.run(svc.send_notification(
            user_id="u-1",
            notification_type="info",
            data={"title": "T", "message": "M"},
        ))
        mock_smtp.assert_not_called()


# =============================================================================
# Soft-fail invariant
# =============================================================================

def test_send_notification_soft_fails_without_session():
    """No db session → returns success=False, NEVER raises."""
    from core.notification_service import NotificationService

    svc = NotificationService(None)
    result = asyncio.run(svc.send_notification(
        user_id="u-1",
        notification_type="agent_graduated",
        data={"title": "T", "message": "M"},
    ))
    assert result["success"] is False
    assert result["notification_id"] is None


def test_send_notification_swallows_internal_exception():
    """An internal exception must be caught, not raised."""
    from core.notification_service import NotificationService

    db = MagicMock()
    db.add.side_effect = RuntimeError("simulated DB failure")

    svc = NotificationService(db)
    # Should not raise — returns a soft-fail dict.
    result = asyncio.run(svc.send_notification(
        user_id="u-1",
        notification_type="agent_graduated",
        data={"title": "T", "message": "M"},
    ))
    assert result["success"] is False


# =============================================================================
# Helper coverage
# =============================================================================

def test_user_email_enabled_reads_preferences_dict():
    from core.notification_service import _user_email_enabled

    enabled = SimpleNamespace(notification_preferences={"email_enabled": True})
    disabled = SimpleNamespace(notification_preferences={})
    empty = SimpleNamespace(notification_preferences=None)

    assert _user_email_enabled(enabled) is True
    assert _user_email_enabled(disabled) is False
    assert _user_email_enabled(empty) is False


def test_classify_buckets():
    from core.notification_service import _classify

    assert _classify("agent_graduated") == "success"
    assert _classify("approval_needed") == "warning"
    assert _classify("security_alert") == "error"
    assert _classify("info") == "info"
