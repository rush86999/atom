"""Coverage wave W65f — api/board_comment_routes.py, api/board_decompose_routes.py,
api/meeting_routes.py, api/messenger_routes.py (TDD).

Endpoints covered per module: every route x {success, 404/403/401, service
exception, 422} plus branch coverage of response-shaping logic.

Auth via get_current_user dependency override (repo standard pattern); the
messenger routes carry no auth dependency (webhook surface) and are exercised
as-is. All DB access uses MagicMock sessions; external adapters/services are
patched at their real module attributes (api.<module>.<name>).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db

USER = SimpleNamespace(id="u-1", role="member", email="u@t.com")


def _make_app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def _client(router, db, user=USER):
    app = _make_app(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _anon_client(router, db):
    app = _make_app(router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _comment_dict(**overrides):
    c = {
        "id": "c-1",
        "task_id": "task-1",
        "conversation_id": "conv-1",
        "content": "hello",
        "author": {"user_id": "u-1", "agent_id": None, "display_name": "U"},
        "parent_message_id": None,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    c.update(overrides)
    return c


# =========================================================================== #
# api/board_comment_routes.py
# =========================================================================== #
class TestBoardCommentRoutes:
    def _c(self, db=None, user=USER):
        from api.board_comment_routes import router

        return _client(router, db or MagicMock(), user=user)

    @pytest.fixture
    def svc(self):
        s = MagicMock()
        with patch("api.board_comment_routes.BoardCommentService", return_value=s):
            yield s

    @pytest.fixture
    def emitter(self):
        e = MagicMock()
        e.emit_comment_posted = AsyncMock()
        with patch("api.board_comment_routes._emitter", e):
            yield e

    def test_create_task_comment_with_task(self, svc, emitter):
        svc.create_comment.return_value = SimpleNamespace(id="c-new")
        svc._serialize.return_value = _comment_dict(id="c-new")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="task-1")
        r = self._c(db).post(
            "/api/boards/b-1/tasks/task-1/comments", json={"content": "hi"}
        )
        assert r.status_code == 201
        body = r.json()
        assert body["id"] == "c-new"
        assert body["replies"] == []
        svc.create_comment.assert_called_once()
        emitter.emit_comment_posted.assert_awaited_once()
        assert emitter.emit_comment_posted.call_args.kwargs["comment_id"] == "c-new"

    def test_create_task_comment_task_missing_skips_emit(self, svc, emitter):
        svc.create_comment.return_value = SimpleNamespace(id="c-new")
        svc._serialize.return_value = _comment_dict(id="c-new")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post(
            "/api/boards/b-1/tasks/task-1/comments", json={"content": "hi"}
        )
        assert r.status_code == 201
        emitter.emit_comment_posted.assert_not_awaited()

    def test_list_task_comments(self, svc):
        node = _comment_dict(id="c-1")
        svc.list_comments.return_value = [MagicMock()]
        svc.build_thread_tree.return_value = [node]
        r = self._c().get("/api/boards/b-1/tasks/task-1/comments")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["id"] == "c-1"
        svc.list_comments.assert_called_once()
        assert svc.list_comments.call_args.kwargs["limit"] == 100
        assert svc.list_comments.call_args.kwargs["before_id"] is None

    def test_list_task_comments_pagination_params(self, svc):
        svc.list_comments.return_value = []
        svc.build_thread_tree.return_value = []
        self._c().get(
            "/api/boards/b-1/tasks/task-1/comments",
            params={"limit": 25, "before_id": "c-9"},
        )
        assert svc.list_comments.call_args.kwargs["limit"] == 25
        assert svc.list_comments.call_args.kwargs["before_id"] == "c-9"

    def test_list_task_comments_limit_out_of_range_422(self, svc):
        r = self._c().get(
            "/api/boards/b-1/tasks/task-1/comments", params={"limit": 0}
        )
        assert r.status_code == 422

    def test_patch_comment(self, svc):
        svc.patch_comment.return_value = SimpleNamespace(id="c-1")
        svc._serialize.return_value = _comment_dict(id="c-1")
        r = self._c().patch("/api/comments/c-1", json={"content": "updated"})
        assert r.status_code == 200
        assert r.json()["content"] == "hello"
        assert svc.patch_comment.call_args.kwargs["author_user_id"] == "u-1"

    def test_patch_comment_empty_content_422(self, svc):
        r = self._c().patch("/api/comments/c-1", json={"content": ""})
        assert r.status_code == 422

    def test_delete_comment(self, svc):
        r = self._c().delete("/api/comments/c-1")
        assert r.status_code == 204
        svc.delete_comment.assert_called_once_with(
            comment_id="c-1", author_user_id="u-1"
        )

    def test_list_artifact_comments(self, svc):
        row = {
            "id": "art-1",
            "artifact_id": "a-1",
            "canvas_id": None,
            "content": "note",
            "user_id": "u-1",
            "agent_id": None,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": None,
        }
        svc.list_artifact_comments_for_task.return_value = [row]
        r = self._c().get("/api/boards/b-1/tasks/task-1/artifact-comments")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["artifact_id"] == "a-1"

    def test_requires_auth(self):
        from api.board_comment_routes import router

        c = _anon_client(router, MagicMock())
        assert c.get("/api/boards/b-1/tasks/task-1/comments").status_code == 401
        assert c.patch("/api/comments/c-1", json={"content": "x"}).status_code == 401
        assert c.delete("/api/comments/c-1").status_code == 401


# =========================================================================== #
# api/board_decompose_routes.py
# =========================================================================== #
class TestBoardDecomposeRoutes:
    def _c(self, db=None, user=USER):
        from api.board_decompose_routes import router

        return _client(router, db or MagicMock(), user=user)

    def test_propose_decomposition_task_found(self):
        from api.board_decompose_routes import BoardDecomposer

        result = SimpleNamespace(rationale="split it", subtasks=[])
        db = MagicMock()
        task = SimpleNamespace(id="task-1", parent_task_id=None)
        db.query.return_value.filter.return_value.first.return_value = task
        with patch.object(BoardDecomposer, "propose", AsyncMock(return_value=result)), \
             patch("core.llm.byok_handler.BYOKHandler"):
            r = self._c(db).post(
                "/api/boards/b-1/tasks/task-1/decompose",
                json={"model_hint": "gpt-4o", "spawn_workspaces": True},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["parent_task_id"] == "task-1"
        assert body["rationale"] == "split it"
        assert body["depth"] == 1
        assert body["max_depth"] >= 1

    def test_propose_decomposition_task_missing_depth_default(self):
        from api.board_decompose_routes import BoardDecomposer

        result = SimpleNamespace(rationale="r", subtasks=[])
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(BoardDecomposer, "propose", AsyncMock(return_value=result)), \
             patch("core.llm.byok_handler.BYOKHandler"):
            r = self._c(db).post(
                "/api/boards/b-1/tasks/task-1/decompose",
                json={"model_hint": None},
            )
        assert r.status_code == 200
        assert r.json()["depth"] == 1

    def test_propose_byok_unavailable_503(self):
        db = MagicMock()
        with patch.dict(sys.modules, {"core.llm.byok_handler": None}):
            r = self._c(db).post(
                "/api/boards/b-1/tasks/task-1/decompose",
                json={"model_hint": None},
            )
        assert r.status_code == 503

    def test_commit_decomposition(self):
        from api.board_decompose_routes import BoardDecomposer

        child = SimpleNamespace(id="child-1")
        db = MagicMock()
        emitter = MagicMock()
        emitter.emit_task_created = AsyncMock()
        with patch.object(BoardDecomposer, "commit", Mock(return_value=[child])), \
             patch("api.board_decompose_routes._emitter", emitter):
            r = self._c(db).post(
                "/api/boards/b-1/tasks/task-1/decompose/commit",
                json={"proposals": [{"title": "sub", "description": "d"}],
                      "spawn_workspaces": True},
            )
        assert r.status_code == 201
        body = r.json()
        assert body["parent_task_id"] == "task-1"
        assert body["created_task_ids"] == ["child-1"]
        assert body["spawned_workspaces"] is True
        emitter.emit_task_created.assert_awaited_once_with(child)

    def test_commit_empty_proposals(self):
        from api.board_decompose_routes import BoardDecomposer

        db = MagicMock()
        emitter = MagicMock()
        emitter.emit_task_created = AsyncMock()
        with patch.object(BoardDecomposer, "commit", Mock(return_value=[])), \
             patch("api.board_decompose_routes._emitter", emitter):
            r = self._c(db).post(
                "/api/boards/b-1/tasks/task-1/decompose/commit",
                json={"proposals": [], "spawn_workspaces": False},
            )
        assert r.status_code == 201
        assert r.json()["created_task_ids"] == []

    def test_commit_requires_proposals_422(self):
        r = self._c().post(
            "/api/boards/b-1/tasks/task-1/decompose/commit", json={}
        )
        assert r.status_code == 422

    def test_requires_auth(self):
        from api.board_decompose_routes import router

        c = _anon_client(router, MagicMock())
        assert c.post("/api/boards/b-1/tasks/task-1/decompose",
                      json={"model_hint": None}).status_code == 401
        assert c.post("/api/boards/b-1/tasks/task-1/decompose/commit",
                      json={"proposals": []}).status_code == 401


# =========================================================================== #
# api/meeting_routes.py
# =========================================================================== #
def _attendance(**overrides):
    a = SimpleNamespace(
        task_id="task-1",
        user_id="u-1",
        platform="zoom",
        meeting_identifier="m-123",
        status_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        current_status_message="waiting",
        final_notion_page_url="https://notion.so/p1",
        error_details=None,
    )
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


class TestMeetingRoutes:
    def _c(self, db=None, user=USER):
        from api.meeting_routes import router

        return _client(router, db or MagicMock(), user=user)

    def test_get_attendance_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _attendance()
        r = self._c(db).get("/api/meetings/attendance/task-1")
        assert r.status_code == 200
        body = r.json()
        assert body["task_id"] == "task-1"
        assert body["platform"] == "zoom"
        assert body["error_details"] is None

    def test_get_attendance_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).get("/api/meetings/attendance/task-1")
        assert r.status_code == 404

    def test_list_attendance(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _attendance(), _attendance(task_id="task-2")
        ]
        r = self._c(db).get("/api/meetings/attendance")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        assert rows[1]["task_id"] == "task-2"

    def test_list_attendance_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        r = self._c(db).get("/api/meetings/attendance")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_attendance_success(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [None, _attendance()]
        r = self._c(db).post("/api/meetings/attendance", json={
            "task_id": "task-1",
            "platform": "zoom",
            "meeting_identifier": "m-123",
            "current_status_message": "in progress",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["task_id"] == "task-1"
        assert body["current_status_message"] == "in progress"

    def test_create_attendance_duplicate_409(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _attendance()
        r = self._c(db).post("/api/meetings/attendance", json={"task_id": "task-1"})
        assert r.status_code == 409

    def test_create_attendance_missing_task_id_422(self):
        r = self._c().post("/api/meetings/attendance", json={})
        assert r.status_code == 422

    def test_update_attendance_all_fields(self):
        att = _attendance()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = att
        r = self._c(db).patch("/api/meetings/attendance/task-1", json={
            "platform": "teams",
            "meeting_identifier": "m-999",
            "current_status_message": "done",
            "final_notion_page_url": "https://notion.so/p2",
            "error_details": "minor issue",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["platform"] == "teams"
        assert body["meeting_identifier"] == "m-999"
        assert body["current_status_message"] == "done"
        assert body["final_notion_page_url"] == "https://notion.so/p2"
        assert body["error_details"] == "minor issue"
        assert att.status_timestamp is not None

    def test_update_attendance_partial_fields(self):
        att = _attendance()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = att
        r = self._c(db).patch("/api/meetings/attendance/task-1", json={
            "current_status_message": "started"
        })
        assert r.status_code == 200
        assert r.json()["current_status_message"] == "started"

    def test_update_attendance_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).patch("/api/meetings/attendance/task-1", json={
            "platform": "teams"
        })
        assert r.status_code == 404

    def test_delete_attendance_success(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _attendance()
        r = self._c(db).delete("/api/meetings/attendance/task-1")
        assert r.status_code == 200
        assert r.json()["message"] == "Meeting attendance deleted successfully"

    def test_delete_attendance_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).delete("/api/meetings/attendance/task-1")
        assert r.status_code == 404

    def test_requires_auth(self):
        from api.meeting_routes import router

        c = _anon_client(router, MagicMock())
        assert c.get("/api/meetings/attendance/task-1").status_code == 401
        assert c.get("/api/meetings/attendance").status_code == 401
        assert c.post("/api/meetings/attendance", json={"task_id": "t"}).status_code == 401
        assert c.patch("/api/meetings/attendance/task-1", json={}).status_code == 401
        assert c.delete("/api/meetings/attendance/task-1").status_code == 401


# =========================================================================== #
# api/messenger_routes.py
# =========================================================================== #
class TestMessengerRoutes:
    def _c(self):
        from api.messenger_routes import router

        return _client(router, MagicMock())

    @pytest.fixture
    def adapter(self):
        a = MagicMock()
        a.app_secret = None
        a.verify_webhook = Mock(return_value={"ok": True, "challenge": "ch-123"})
        a.verify_signature = Mock(return_value=True)
        a.handle_webhook_event = AsyncMock(return_value={"received": True})
        a.send_message = AsyncMock(return_value={"ok": True, "message_id": "m-1"})
        a.send_attachment = AsyncMock(return_value={"ok": True, "attachment_id": "a-1"})
        a.get_user_info = AsyncMock(return_value={"ok": True, "first_name": "Bob"})
        a.get_service_status = AsyncMock(return_value={"status": "active"})
        a.get_capabilities = AsyncMock(return_value={"capabilities": ["send", "receive"]})
        with patch("api.messenger_routes.messenger_adapter", a):
            yield a

    # -- webhook verification (GET) --
    def test_verify_webhook_success(self, adapter):
        r = self._c().get("/api/messenger/webhook", params={
            "hub.mode": "subscribe", "hub.verify_token": "tok",
            "hub.challenge": "ch-123",
        })
        assert r.status_code == 200
        assert r.json() == {"hub.challenge": "ch-123"}
        adapter.verify_webhook.assert_called_once_with("subscribe", "tok", "ch-123")

    def test_verify_webhook_failed_403(self, adapter):
        adapter.verify_webhook.return_value = {"ok": False, "error": "bad token"}
        r = self._c().get("/api/messenger/webhook", params={
            "hub.mode": "subscribe", "hub.verify_token": "bad",
            "hub.challenge": "ch",
        })
        assert r.status_code == 403

    def test_verify_webhook_exception_500(self, adapter):
        adapter.verify_webhook.side_effect = RuntimeError("boom")
        r = self._c().get("/api/messenger/webhook", params={
            "hub.mode": "subscribe", "hub.verify_token": "tok",
            "hub.challenge": "ch",
        })
        assert r.status_code == 500

    def test_verify_webhook_missing_params_422(self, adapter):
        r = self._c().get("/api/messenger/webhook")
        assert r.status_code == 422

    # -- webhook event handling (POST) --
    def test_handle_webhook_success(self, adapter):
        r = self._c().post(
            "/api/messenger/webhook",
            json={"object": "page", "entry": []},
            headers={"X-Hub-Signature": "sha1=abc"},
        )
        assert r.status_code == 200
        assert r.json() == {"received": True}
        adapter.handle_webhook_event.assert_awaited_once()

    def test_handle_webhook_signature_skipped_without_secret(self, adapter):
        adapter.app_secret = None
        r = self._c().post("/api/messenger/webhook", json={"object": "page"})
        assert r.status_code == 200
        adapter.verify_signature.assert_not_called()

    def test_handle_webhook_invalid_signature_403(self, adapter):
        adapter.app_secret = "secret"
        adapter.verify_signature.return_value = False
        r = self._c().post(
            "/api/messenger/webhook",
            json={"object": "page"},
            headers={"X-Hub-Signature": "sha1=bad"},
        )
        assert r.status_code == 403

    def test_handle_webhook_valid_signature(self, adapter):
        adapter.app_secret = "secret"
        r = self._c().post(
            "/api/messenger/webhook",
            json={"object": "page"},
            headers={"X-Hub-Signature": "sha1=good"},
        )
        assert r.status_code == 200
        adapter.verify_signature.assert_called_once()

    def test_handle_webhook_invalid_json_500(self, adapter):
        r = self._c().post(
            "/api/messenger/webhook",
            content=b"{not-json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 500

    def test_handle_webhook_event_exception_500(self, adapter):
        adapter.handle_webhook_event.side_effect = RuntimeError("boom")
        r = self._c().post("/api/messenger/webhook", json={"object": "page"})
        assert r.status_code == 500

    # -- send message --
    def test_send_message_success(self, adapter):
        r = self._c().post("/api/messenger/send-message", json={
            "recipient_id": "psid-1", "message": "hello",
        })
        assert r.status_code == 200
        assert r.json()["message_id"] == "m-1"
        kwargs = adapter.send_message.await_args.kwargs
        assert kwargs["recipient_id"] == "psid-1"
        assert kwargs["messaging_type"] == "RESPONSE"

    def test_send_message_with_quick_replies(self, adapter):
        self._c().post("/api/messenger/send-message", json={
            "recipient_id": "psid-1", "message": "hi",
            "messaging_type": "UPDATE",
            "quick_replies": [{"content_type": "text", "title": "Yes", "payload": "y"}],
        })
        kwargs = adapter.send_message.await_args.kwargs
        assert kwargs["messaging_type"] == "UPDATE"
        assert len(kwargs["quick_replies"]) == 1

    def test_send_message_failed_500(self, adapter):
        adapter.send_message.return_value = {"ok": False, "error": "api down"}
        r = self._c().post("/api/messenger/send-message", json={
            "recipient_id": "psid-1", "message": "hi",
        })
        assert r.status_code == 500

    def test_send_message_exception_500(self, adapter):
        adapter.send_message.side_effect = RuntimeError("boom")
        r = self._c().post("/api/messenger/send-message", json={
            "recipient_id": "psid-1", "message": "hi",
        })
        assert r.status_code == 500

    def test_send_message_missing_recipient_422(self, adapter):
        r = self._c().post("/api/messenger/send-message", json={"message": "hi"})
        assert r.status_code == 422

    # -- send attachment --
    def test_send_attachment_success(self, adapter):
        r = self._c().post("/api/messenger/send-attachment", json={
            "recipient_id": "psid-1", "attachment_type": "image",
            "attachment_url": "https://x/img.png",
        })
        assert r.status_code == 200
        assert r.json()["attachment_id"] == "a-1"

    def test_send_attachment_failed_500(self, adapter):
        adapter.send_attachment.return_value = {"ok": False, "error": "nope"}
        r = self._c().post("/api/messenger/send-attachment", json={
            "recipient_id": "psid-1", "attachment_type": "file",
            "attachment_url": "https://x/f.pdf",
        })
        assert r.status_code == 500

    def test_send_attachment_exception_500(self, adapter):
        adapter.send_attachment.side_effect = RuntimeError("boom")
        r = self._c().post("/api/messenger/send-attachment", json={
            "recipient_id": "psid-1", "attachment_type": "audio",
            "attachment_url": "https://x/a.mp3",
        })
        assert r.status_code == 500

    def test_send_attachment_missing_type_422(self, adapter):
        r = self._c().post("/api/messenger/send-attachment", json={
            "recipient_id": "psid-1", "attachment_url": "https://x/a.mp3",
        })
        assert r.status_code == 422

    # -- user info --
    def test_get_user_info_success(self, adapter):
        r = self._c().get("/api/messenger/user/psid-1")
        assert r.status_code == 200
        assert r.json()["first_name"] == "Bob"
        adapter.get_user_info.assert_awaited_once_with("psid-1")

    def test_get_user_info_not_found_404(self, adapter):
        adapter.get_user_info.return_value = {"ok": False, "error": "not found"}
        r = self._c().get("/api/messenger/user/psid-1")
        assert r.status_code == 404

    def test_get_user_info_exception_500(self, adapter):
        adapter.get_user_info.side_effect = RuntimeError("boom")
        r = self._c().get("/api/messenger/user/psid-1")
        assert r.status_code == 500

    # -- health / status / capabilities --
    def test_health_active(self, adapter):
        r = self._c().get("/api/messenger/health")
        assert r.status_code == 200
        assert r.json() == {"status": "healthy", "service": "Facebook Messenger"}

    def test_health_inactive(self, adapter):
        adapter.get_service_status.return_value = {"status": "inactive"}
        r = self._c().get("/api/messenger/health")
        assert r.status_code == 200
        assert r.json()["status"] == "inactive"

    def test_health_exception_500(self, adapter):
        adapter.get_service_status.side_effect = RuntimeError("boom")
        r = self._c().get("/api/messenger/health")
        assert r.status_code == 500

    def test_status_success(self, adapter):
        r = self._c().get("/api/messenger/status")
        assert r.status_code == 200
        assert r.json()["status"] == "active"

    def test_status_exception_500(self, adapter):
        adapter.get_service_status.side_effect = RuntimeError("boom")
        r = self._c().get("/api/messenger/status")
        assert r.status_code == 500

    def test_capabilities(self, adapter):
        r = self._c().get("/api/messenger/capabilities")
        assert r.status_code == 200
        assert r.json()["capabilities"] == ["send", "receive"]
        adapter.get_capabilities.assert_awaited_once()
