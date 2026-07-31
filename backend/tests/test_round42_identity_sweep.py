"""
Round 42 — Client-supplied identity sweep: user_id/approver_id from query/body
instead of the authenticated token (Red-Green-Refactor).

Prior rounds fixed this class case-by-case (deeplinks R38, zoho-workdrive R38,
episode_routes R39, ai_accounting R39, agent_governance R39). This round sweeps
the remaining mounted routers:

  A. api/user_templates_endpoints.py — CRITICAL: create_user_template sets
     author_id from a client query param (create templates AS any user);
     list_user_templates with no user_id returns ALL templates (incl. private);
     update/delete ownership checks run against the client-supplied user_id
     (modify/delete ANY user's template); stats read any user.
  B. api/dashboard_data_routes.py — 5 endpoints filter dashboard data
     (calendar/tasks/messages/stats) by a client-supplied user_id
     (cross-user dashboard reads).
  C. api/supervised_queue_routes.py — get_queue_stats filters by client user_id.
  D. api/messaging_routes.py — approve/reject proactive messages attribute the
     action to a client-supplied approver_user_id/rejecter_user_id.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db


def make_client(router, current_user=None, db=None):
    """TestClient with auth + db dependency overrides (authenticated)."""
    app = FastAPI()
    app.include_router(router)

    def _override_user():
        return current_user if current_user is not None else MagicMock(id="u-42")

    def _override_db():
        return db if db is not None else MagicMock()

    app.dependency_overrides[auth_get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# A. User templates — IDOR + attribution spoofing
# ============================================================================

class TestUserTemplatesIdentity:
    def test_create_uses_current_user_id(self):
        """author_id must come from the token, not the user_id query param."""
        from api.user_templates_endpoints import router

        captured = []

        class FakeTemplate:
            """Stand-in for WorkflowTemplate — records constructor kwargs."""
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                # Defaults the real model provides via Column defaults
                for attr in ("is_approved", "usage_count", "rating",
                             "rating_count", "created_at", "updated_at"):
                    if attr not in self.__dict__:
                        setattr(self, attr, 0 if attr != "is_approved" else False)
                self.is_approved = self.is_approved or False
                captured.append(self)

        db = MagicMock()
        with patch(
            "api.user_templates_endpoints.WorkflowTemplate", FakeTemplate
        ), patch(
            "api.user_templates_endpoints.TemplateVersion",
            lambda **kw: captured.append(type("V", (), kw)()),
        ):
            resp = make_client(router, db=db).post(
                "/api/user/templates?user_id=attacker",
                json={
                    "name": "t",
                    "description": "d",
                    "category": "general",
                    "complexity": "low",
                    "tags": [],
                    "is_public": False,
                    "template_json": {},
                    "inputs_schema": [],
                    "steps_schema": [],
                },
            )
        assert resp.status_code == 201
        template = next(obj for obj in captured if hasattr(obj, "author_id"))
        assert template.author_id == "u-42"

    def test_create_version_uses_current_user_id(self):
        from api.user_templates_endpoints import router

        captured = []

        class FakeTemplate:
            """Stand-in for WorkflowTemplate — records constructor kwargs."""
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                for attr in ("is_approved", "usage_count", "rating",
                             "rating_count", "created_at", "updated_at"):
                    if attr not in self.__dict__:
                        setattr(self, attr, 0 if attr != "is_approved" else False)
                captured.append(self)

        db = MagicMock()
        with patch(
            "api.user_templates_endpoints.WorkflowTemplate", FakeTemplate
        ), patch(
            "api.user_templates_endpoints.TemplateVersion",
            lambda **kw: captured.append(type("V", (), kw)()),
        ):
            make_client(router, db=db).post(
                "/api/user/templates?user_id=attacker",
                json={
                    "name": "t",
                    "description": "d",
                    "category": "general",
                    "complexity": "low",
                    "tags": [],
                    "is_public": False,
                    "template_json": {},
                    "inputs_schema": [],
                    "steps_schema": [],
                },
            )
        version = next(obj for obj in captured if hasattr(obj, "created_by"))
        assert version.created_by == "u-42"

    def test_list_always_scopes_to_current_user(self):
        """Without a user_id param, only own + public templates are returned."""
        from api.user_templates_endpoints import router

        db = MagicMock()
        db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
        make_client(router, db=db).get("/api/user/templates")

        filter_calls = db.query.return_value.filter.call_args_list
        assert filter_calls, "list_templates must apply at least one filter"
        first = filter_calls[0].args[0]
        # Ownership filter: author_id == current_user.id (possibly OR is_public)
        assert "author_id" in str(first)
        params = first.compile().params
        assert "u-42" in params.values()

    def test_stats_use_current_user_id(self):
        from api.user_templates_endpoints import router

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        make_client(router, db=db).get(
            "/api/user/templates/stats?user_id=attacker"
        )

        filter_call = db.query.return_value.filter.call_args.args[0]
        assert filter_call.left.name == "author_id"
        assert filter_call.right.value == "u-42"

    def test_update_ownership_uses_current_user_id(self):
        """Passing the victim's id as user_id must not bypass ownership."""
        from api.user_templates_endpoints import router

        db = MagicMock()
        template = MagicMock()
        template.author_id = "victim"  # owned by someone else
        template.template_id = "t-1"
        template.version = "1.0.0"
        template.template_json = {}
        db.query.return_value.filter.return_value.first.return_value = template

        resp = make_client(router, db=db).put(
            "/api/user/templates/t-1?user_id=victim",
            json={"name": "hijacked"},
        )
        assert resp.status_code == 403

    def test_delete_ownership_uses_current_user_id(self):
        from api.user_templates_endpoints import router

        db = MagicMock()
        template = MagicMock()
        template.author_id = "victim"
        template.template_id = "t-1"
        db.query.return_value.filter.return_value.first.return_value = template

        resp = make_client(router, db=db).delete(
            "/api/user/templates/t-1?user_id=victim"
        )
        assert resp.status_code == 403


# ============================================================================
# B. Dashboard data — cross-user reads via user_id filter
# ============================================================================

class TestDashboardIdentity:
    STATS = {
        "upcoming_events": 0,
        "overdue_tasks": 0,
        "unread_messages": 0,
        "completed_tasks": 0,
        "active_workflows": 0,
        "total_agents": 0,
    }

    def _client(self):
        from api.dashboard_data_routes import router
        return make_client(router)

    def test_dashboard_data_uses_current_user_id(self):
        with patch(
            "api.dashboard_data_routes.get_user_upcoming_events",
            return_value=[],
        ) as events, patch(
            "api.dashboard_data_routes.get_user_tasks",
            return_value=[],
        ) as tasks, patch(
            "api.dashboard_data_routes.get_user_messages",
            return_value=[],
        ) as messages, patch(
            "api.dashboard_data_routes.calculate_dashboard_stats",
            return_value=dict(self.STATS),
        ) as stats:
            resp = self._client().get("/api/dashboard/data?user_id=attacker")
        assert resp.status_code == 200
        events.assert_called_once()
        assert events.call_args.args[1] == "u-42"
        tasks.assert_called_once()
        assert tasks.call_args.args[1] == "u-42"
        messages.assert_called_once()
        assert messages.call_args.args[1] == "u-42"
        stats.assert_called_once()
        assert stats.call_args.args[1] == "u-42"

    def test_dashboard_stats_uses_current_user_id(self):
        with patch(
            "api.dashboard_data_routes.calculate_dashboard_stats",
            return_value=dict(self.STATS),
        ) as stats:
            resp = self._client().get("/api/dashboard/stats?user_id=attacker")
        assert resp.status_code == 200
        assert stats.call_args.args[1] == "u-42"

    def test_calendar_events_use_current_user_id(self):
        with patch(
            "api.dashboard_data_routes.get_user_upcoming_events",
            return_value=[],
        ) as events:
            resp = self._client().get("/api/dashboard/events?user_id=attacker")
        assert resp.status_code == 200
        assert events.call_args.args[1] == "u-42"

    def test_tasks_use_current_user_id(self):
        with patch(
            "api.dashboard_data_routes.get_user_tasks",
            return_value=[],
        ) as tasks:
            resp = self._client().get("/api/dashboard/tasks?user_id=attacker")
        assert resp.status_code == 200
        assert tasks.call_args.args[1] == "u-42"

    def test_messages_use_current_user_id(self):
        with patch(
            "api.dashboard_data_routes.get_user_messages",
            return_value=[],
        ) as messages:
            resp = self._client().get("/api/dashboard/messages?user_id=attacker")
        assert resp.status_code == 200
        assert messages.call_args.args[1] == "u-42"


# ============================================================================
# C. Supervised queue — stats filter
# ============================================================================

class TestSupervisedQueueIdentity:
    def test_stats_use_current_user_id(self):
        from api.supervised_queue_routes import router

        service = MagicMock()
        service.get_queue_stats = AsyncMock(return_value={
            "pending": 0, "executing": 0, "completed": 0,
            "failed": 0, "cancelled": 0, "total": 0,
        })
        with patch(
            "api.supervised_queue_routes.SupervisedQueueService",
            return_value=service,
        ):
            resp = make_client(router).get(
                "/api/supervised-queue/stats?user_id=attacker"
            )
        assert resp.status_code == 200
        assert service.get_queue_stats.call_args.args[0] == "u-42"


# ============================================================================
# D. Messaging — approve/reject attribution
# ============================================================================

class TestMessagingIdentity:
    def _anon(self):
        from api.messaging_routes import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False)

    def test_reject_requires_auth(self):
        resp = self._anon().post(
            "/api/v1/messaging/proactive/reject/m-1",
            json={"rejecter_user_id": "attacker", "rejection_reason": "spam"},
        )
        assert resp.status_code == 401

    def test_cancel_requires_auth(self):
        assert self._anon().delete(
            "/api/v1/messaging/proactive/cancel/m-1"
        ).status_code == 401

    def _message_dict(self):
        from datetime import datetime, timezone
        return {
            "id": "m-1",
            "agent_id": "a-1",
            "agent_name": "Agent",
            "agent_maturity_level": "SUPERVISED",
            "platform": "slack",
            "recipient_id": "r-1",
            "content": "hi",
            "scheduled_for": None,
            "send_now": True,
            "status": "APPROVED",
            "approved_by": None,
            "approved_at": None,
            "rejection_reason": None,
            "sent_at": None,
            "error_message": None,
            "platform_message_id": None,
            "created_at": datetime(2026, 7, 31, tzinfo=timezone.utc),
            "updated_at": None,
        }

    def test_approve_uses_current_user_id(self):
        from api.messaging_routes import router

        service = MagicMock()
        service.approve_message = MagicMock(return_value=self._message_dict())
        with patch("api.messaging_routes.ProactiveMessagingService", return_value=service):
            resp = make_client(router).post(
                "/api/v1/messaging/proactive/approve/m-1",
                json={"approver_user_id": "attacker"},
            )
        assert resp.status_code == 200
        assert service.approve_message.call_args.kwargs["approver_user_id"] == "u-42"

    def test_reject_uses_current_user_id(self):
        from api.messaging_routes import router

        service = MagicMock()
        service.reject_message = MagicMock(return_value=self._message_dict())
        with patch("api.messaging_routes.ProactiveMessagingService", return_value=service):
            resp = make_client(router).post(
                "/api/v1/messaging/proactive/reject/m-1",
                json={"rejecter_user_id": "attacker", "rejection_reason": "spam"},
            )
        assert resp.status_code == 200
        assert service.reject_message.call_args.kwargs["rejecter_user_id"] == "u-42"
