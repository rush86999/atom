"""
TDD regression tests for Round 23 bug hunt - Real-time messaging & WebSocket DoS.

Covers:
- BUG R23-1: messaging_routes — 10 endpoints with NO auth (proactive/scheduled/history)
- BUG R23-2: scheduled_messaging_routes — 10 endpoints with NO auth
- BUG R23-3: notification_settings_routes — 3 endpoints with NO auth
"""

from __future__ import annotations

import inspect


def _route_auth_dependencies(func) -> list[str]:
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty:
            continue
        if hasattr(p.default, "dependency"):
            name = getattr(p.default.dependency, "__name__", "") or p.default.dependency.__class__.__name__
            deps.append(name)
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    return deps


def _has_auth_dependency(func) -> bool:
    deps = _route_auth_dependencies(func)
    markers = ("get_current_user", "verify_token", "require_user", "require_auth",
               "get_current_active_user", "require_admin", "require_permission",
               "require_governance")
    return any(any(m in d for m in markers) for d in deps)


# ---------------------------------------------------------------------------
# BUG R23-1: messaging_routes — no auth
# ---------------------------------------------------------------------------


class TestMessagingRoutesRequireAuth:
    """Proactive/scheduled message endpoints must require auth."""

    def _load(self):
        from api import messaging_routes as mod
        return mod

    def test_send_proactive_message_requires_auth(self):
        assert _has_auth_dependency(self._load().send_proactive_message), (
            "POST send_proactive_message has no auth — unauthenticated message sending"
        )

    def test_approve_proactive_message_requires_auth(self):
        assert _has_auth_dependency(self._load().approve_proactive_message), (
            "POST approve_proactive_message has no auth — anyone can approve messages"
        )

    def test_get_message_history_requires_auth(self):
        assert _has_auth_dependency(self._load().get_message_history), (
            "GET get_message_history has no auth — anyone can read message history"
        )

    def test_get_pending_messages_requires_auth(self):
        assert _has_auth_dependency(self._load().get_pending_messages), (
            "GET get_pending_messages has no auth — pending message enumeration"
        )


# ---------------------------------------------------------------------------
# BUG R23-2: scheduled_messaging_routes — no auth
# ---------------------------------------------------------------------------


class TestScheduledMessagingRoutesRequireAuth:
    def _load(self):
        from api import scheduled_messaging_routes as mod
        return mod

    def test_create_scheduled_message_requires_auth(self):
        assert _has_auth_dependency(self._load().create_scheduled_message), (
            "POST create_scheduled_message has no auth — unauthenticated scheduling"
        )

    def test_list_scheduled_messages_requires_auth(self):
        assert _has_auth_dependency(self._load().list_scheduled_messages), (
            "GET list_scheduled_messages has no auth — schedule enumeration"
        )

    def test_cancel_scheduled_message_requires_auth(self):
        assert _has_auth_dependency(self._load().cancel_scheduled_message), (
            "POST cancel_scheduled_message has no auth — anyone can cancel schedules"
        )

    def test_execute_due_messages_requires_auth(self):
        assert _has_auth_dependency(self._load().execute_due_messages), (
            "POST execute_due_messages has no auth — trigger mass message dispatch"
        )


# ---------------------------------------------------------------------------
# BUG R23-3: notification_settings_routes — no auth
# ---------------------------------------------------------------------------


class TestNotificationSettingsRoutesRequireAuth:
    def _load(self):
        from api import notification_settings_routes as mod
        return mod

    def test_get_notification_settings_requires_auth(self):
        assert _has_auth_dependency(self._load().get_notification_settings), (
            "GET get_notification_settings has no auth — settings enumeration"
        )

    def test_update_notification_settings_requires_auth(self):
        assert _has_auth_dependency(self._load().update_notification_settings), (
            "PUT update_notification_settings has no auth — anyone can change notification settings"
        )
