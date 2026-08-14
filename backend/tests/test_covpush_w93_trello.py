"""Coverage wave 93 — integrations/trello_routes.py (re-audit).

W64 covered this module to 98%; this wave closes the last gap (the
get_user_profile exception branch, lines 535-537) and re-verifies the full
surface: every endpoint's success + error path, health 503, auth-401 on all
gated endpoints, and the public (health/info/auth-url/callback) surface.

trello_service is fully mocked (AsyncMock); no network, no LLM spend.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations import trello_routes as tr
from core.models import User


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = f"tr93-{uuid.uuid4().hex[:8]}"
    u.email = "trello93@x.com"
    u.tenant_id = "t-1"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(tr.router)
    from core.auth import get_current_user
    from core.database import get_db

    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(tr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def svc():
    s = MagicMock()
    s.card_types = {"task": "Task", "bug": "Bug", "feature": "Feature"}
    s.get_service_info = AsyncMock(return_value={"status": "ok"})
    s.get_boards = AsyncMock(return_value=[{"id": "b1"}])
    s.get_board = AsyncMock(return_value={"id": "b1"})
    s.get_lists = AsyncMock(return_value=[{"id": "l1"}])
    s.get_cards = AsyncMock(return_value=[{"id": "c1"}])
    s.get_card = AsyncMock(return_value={"id": "c1"})
    s.create_card = AsyncMock(return_value={"id": "c-new"})
    s.update_card = AsyncMock(return_value={"id": "c1"})
    s.delete_card = AsyncMock(return_value={"success": True})
    s.get_members = AsyncMock(return_value=[{"id": "m1"}])
    s.search_cards = AsyncMock(return_value=[{"id": "c1"}])
    s.get_board_activities = AsyncMock(return_value=[{"id": "a1"}])
    with patch.object(tr, "trello_service", s):
        yield s


BODY = {"user_id": "u1"}
AUTHED_POST = [
    ("/api/trello/boards", {**BODY}),
    ("/api/trello/boards/b1", {**BODY}),
    ("/api/trello/lists", {**BODY, "board_id": "b1"}),
    ("/api/trello/cards", {**BODY}),
    ("/api/trello/cards/create", {**BODY, "name": "n", "id_list": "l1"}),
    ("/api/trello/cards/c1", {**BODY}),
    ("/api/trello/members", {**BODY, "board_id": "b1"}),
    ("/api/trello/user/profile", {**BODY}),
    ("/api/trello/search", {**BODY, "query": "q"}),
    ("/api/trello/activities", {**BODY, "board_id": "b1"}),
]


class TestAuth:
    @pytest.mark.parametrize("path,body", AUTHED_POST)
    def test_authed_post_anonymous_401(self, anon_client, path, body):
        response = anon_client.post(path, json=body)
        assert response.status_code == 401

    def test_put_card_anonymous_401(self, anon_client):
        assert anon_client.put("/api/trello/cards/c1",
                               json={**BODY}).status_code == 401

    def test_delete_card_anonymous_401(self, anon_client):
        assert anon_client.request(
            "DELETE", "/api/trello/cards/c1",
            json={**BODY}).status_code == 401


class TestPublicEndpoints:
    def test_auth_url(self, client):
        response = client.get("/api/trello/auth/url")
        assert response.status_code == 200
        assert "INSERT_API_KEY" in response.json()["url"]

    def test_callback(self, client):
        response = client.get("/api/trello/callback?token=tok-1")
        assert response.status_code == 200
        assert response.json()["token"] == "tok-1"

    def test_health_ok(self, client, svc):
        with patch.dict("os.environ", {"TRELLO_API_KEY": "k",
                                       "TRELLO_OAUTH_TOKEN": "t"},
                        clear=False):
            response = client.get("/api/trello/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["api_key_configured"] is True
        assert body["oauth_token_configured"] is True

    def test_health_missing_keys(self, client, svc, monkeypatch):
        monkeypatch.delenv("TRELLO_API_KEY", raising=False)
        monkeypatch.delenv("TRELLO_OAUTH_TOKEN", raising=False)
        response = client.get("/api/trello/health")
        assert response.status_code == 200
        assert response.json()["api_key_configured"] is False

    def test_health_service_error_503(self, client):
        with patch.object(tr.trello_service, "get_service_info",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            response = client.get("/api/trello/health")
        assert response.status_code == 503
        assert response.json()["detail"]["status"] == "unhealthy"

    def test_status_alias(self, client, svc):
        response = client.get("/api/trello/status")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_info(self, client, svc):
        response = client.get("/api/trello/info")
        assert response.status_code == 200
        assert response.json()["data"]["service"] == "trello"

    def test_info_error_500(self, client):
        with patch.object(tr.trello_service, "get_service_info",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            response = client.get("/api/trello/info")
        assert response.status_code == 500


class TestBoards:
    def test_get_boards_success(self, client, svc):
        response = client.post("/api/trello/boards", json={
            "user_id": "u1", "include_closed": True, "limit": 10})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["total_count"] == 1
        svc.get_boards.assert_awaited_once_with(
            user_id="u1", include_closed=True, limit=10,
            fields=["name", "id", "desc", "url", "closed", "starred"])

    def test_get_boards_error_500(self, client, svc):
        svc.get_boards.side_effect = RuntimeError("boom")
        response = client.post("/api/trello/boards", json={"user_id": "u1"})
        assert response.status_code == 500
        assert response.json()["detail"]["ok"] is False

    def test_get_board_success(self, client, svc):
        response = client.post("/api/trello/boards/b42", json={"user_id": "u1"})
        assert response.status_code == 200
        assert response.json()["data"]["board"]["id"] == "b1"
        svc.get_board.assert_awaited_once_with(
            board_id="b42", user_id="u1",
            fields=["name", "id", "desc", "url", "closed", "starred", "prefs"])

    def test_get_board_error_500(self, client, svc):
        svc.get_board.side_effect = RuntimeError("boom")
        response = client.post("/api/trello/boards/b42", json={"user_id": "u1"})
        assert response.status_code == 500


class TestLists:
    def test_get_lists_success(self, client, svc):
        response = client.post("/api/trello/lists", json={
            "user_id": "u1", "board_id": "b1", "include_closed": True})
        assert response.status_code == 200
        assert response.json()["data"]["total_count"] == 1
        svc.get_lists.assert_awaited_once_with(
            user_id="u1", board_id="b1", include_closed=True, limit=100,
            fields=["name", "id", "closed", "pos"])

    def test_get_lists_error_500(self, client, svc):
        svc.get_lists.side_effect = RuntimeError("boom")
        response = client.post("/api/trello/lists", json={
            "user_id": "u1", "board_id": "b1"})
        assert response.status_code == 500


class TestCards:
    def test_get_cards_success(self, client, svc):
        response = client.post("/api/trello/cards", json={
            "user_id": "u1", "board_id": "b1", "include_archived": True})
        assert response.status_code == 200
        assert response.json()["data"]["total_count"] == 1
        svc.get_cards.assert_awaited_once_with(
            user_id="u1", board_id="b1", list_id=None,
            include_archived=True, limit=100,
            fields=["name", "id", "desc", "due", "labels", "idList",
                    "idBoard"])

    def test_get_cards_error_500(self, client, svc):
        svc.get_cards.side_effect = RuntimeError("boom")
        response = client.post("/api/trello/cards", json={"user_id": "u1"})
        assert response.status_code == 500

    def test_create_card_with_type_formatting(self, client, svc):
        response = client.post("/api/trello/cards/create", json={
            "user_id": "u1", "name": "Fix bug", "id_list": "l1",
            "desc": "d", "labels": ["x"], "card_type": "bug"})
        assert response.status_code == 200
        card_data = svc.create_card.call_args[1]["card_data"]
        assert card_data["name"] == "[BUG] Fix bug"

    def test_create_card_unknown_type_no_formatting(self, client, svc):
        response = client.post("/api/trello/cards/create", json={
            "user_id": "u1", "name": "plain", "id_list": "l1",
            "card_type": "mystery"})
        assert response.status_code == 200
        assert svc.create_card.call_args[1]["card_data"]["name"] == "plain"

    def test_create_card_error_500(self, client, svc):
        svc.create_card.side_effect = RuntimeError("boom")
        response = client.post("/api/trello/cards/create", json={
            "user_id": "u1", "name": "n", "id_list": "l1"})
        assert response.status_code == 500

    def test_get_card_success(self, client, svc):
        response = client.post("/api/trello/cards/c7", json={"user_id": "u1"})
        assert response.status_code == 200
        assert response.json()["data"]["card"]["id"] == "c1"
        svc.get_card.assert_awaited_once_with(
            card_id="c7", user_id="u1",
            fields=["name", "id", "desc", "due", "labels", "idList",
                    "idBoard", "url"])

    def test_get_card_error_500(self, client, svc):
        svc.get_card.side_effect = RuntimeError("boom")
        response = client.post("/api/trello/cards/c7", json={"user_id": "u1"})
        assert response.status_code == 500

    def test_update_card_all_fields(self, client, svc):
        response = client.put("/api/trello/cards/c7", json={
            "user_id": "u1", "name": "n", "desc": "d", "due": "2026-09-01",
            "id_list": "l2", "labels": ["L1"]})
        assert response.status_code == 200
        svc.update_card.assert_awaited_once_with(
            card_id="c7", user_id="u1",
            update_data={"name": "n", "desc": "d", "due": "2026-09-01",
                         "idList": "l2", "idLabels": ["L1"]})

    def test_update_card_partial(self, client, svc):
        response = client.put("/api/trello/cards/c7",
                              json={"user_id": "u1", "name": "only-name"})
        assert response.status_code == 200
        assert svc.update_card.call_args[1]["update_data"] == {"name":
                                                               "only-name"}

    def test_update_card_error_500(self, client, svc):
        svc.update_card.side_effect = RuntimeError("boom")
        response = client.put("/api/trello/cards/c7", json={"user_id": "u1"})
        assert response.status_code == 500

    def test_delete_card_success(self, client, svc):
        response = client.request("DELETE", "/api/trello/cards/c7",
                                  json={"user_id": "u1"})
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["data"]["message"]
        svc.delete_card.assert_awaited_once_with(card_id="c7", user_id="u1")

    def test_delete_card_error_500(self, client, svc):
        svc.delete_card.side_effect = RuntimeError("boom")
        response = client.request("DELETE", "/api/trello/cards/c7",
                                  json={"user_id": "u1"})
        assert response.status_code == 500


class TestMembersSearchActivities:
    def test_get_members_success(self, client, svc):
        response = client.post("/api/trello/members", json={
            "user_id": "u1", "board_id": "b1", "include_guests": True})
        assert response.status_code == 200
        assert response.json()["data"]["total_count"] == 1
        svc.get_members.assert_awaited_once_with(
            user_id="u1", board_id="b1", include_guests=True, limit=50,
            fields=["fullName", "username", "id", "avatarUrl", "memberType"])

    def test_get_members_error_500(self, client, svc):
        svc.get_members.side_effect = RuntimeError("boom")
        response = client.post("/api/trello/members", json={
            "user_id": "u1", "board_id": "b1"})
        assert response.status_code == 500

    def test_get_user_profile_success(self, client):
        response = client.post("/api/trello/user/profile",
                               json={"user_id": "u42"})
        assert response.status_code == 200
        profile = response.json()["data"]["user"]
        assert profile["id"] == "u42"
        assert profile["email"] == "user_u42@example.com"

    def test_get_user_profile_error_500(self, client):
        """Wave-93 gap: get_user_profile exception branch (logger failure)."""
        with patch.object(tr.logger, "info",
                          side_effect=RuntimeError("log broken")):
            response = client.post("/api/trello/user/profile",
                                   json={"user_id": "u42"})
        assert response.status_code == 500

    def test_search_success(self, client, svc):
        response = client.post("/api/trello/search", json={
            "user_id": "u1", "query": "alpha", "type": "global",
            "limit": 10, "board_id": "b1"})
        assert response.status_code == 200
        assert response.json()["data"]["total_count"] == 1
        svc.search_cards.assert_awaited_once_with(
            user_id="u1", query="alpha", search_type="global",
            limit=10, board_id="b1")

    def test_search_error_500(self, client, svc):
        svc.search_cards.side_effect = RuntimeError("boom")
        response = client.post("/api/trello/search", json={
            "user_id": "u1", "query": "q"})
        assert response.status_code == 500

    def test_activities_success(self, client, svc):
        response = client.post("/api/trello/activities", json={
            "user_id": "u1", "board_id": "b1", "limit": 20,
            "since": "2026-08-01"})
        assert response.status_code == 200
        assert response.json()["data"]["total_count"] == 1
        svc.get_board_activities.assert_awaited_once_with(
            user_id="u1", board_id="b1", limit=20, since="2026-08-01")

    def test_activities_error_500(self, client, svc):
        svc.get_board_activities.side_effect = RuntimeError("boom")
        response = client.post("/api/trello/activities", json={
            "user_id": "u1", "board_id": "b1"})
        assert response.status_code == 500
