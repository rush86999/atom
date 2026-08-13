"""Coverage wave W64 — integrations/trello_routes.py (TDD, 0% baseline).

Endpoints (router prefix /api/trello):
- GET  /auth/url, /callback, /health, /status, /info
- POST /boards, /boards/{board_id}, /lists, /cards, /cards/create,
  /cards/{card_id} (PUT/DELETE), /members, /user/profile, /search, /activities

Covers per endpoint: success + service-exception (500) + 503 on health.
Auth via get_current_user dependency override (repo standard pattern).

Bugs found + fixed in module (regression tests below):
1. create_card crashed on the real TrelloService (no `card_types` attribute,
   line 346) -> AttributeError -> every create-card call 500'd. Now uses
   getattr(..., {}) — test_create_card_real_service_without_card_types.
2. POST /cards/create was shadowed by POST /cards/{card_id} (registered
   earlier, card_id="create") — create endpoint unreachable via HTTP. Route
   moved above /cards/{card_id} — test_create_card_via_http.
"""
import importlib
import sys
import types
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
    u.id = f"tr-{uuid.uuid4().hex[:8]}"
    u.email = "trello@x.com"
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
def svc():
    """Patched module-level trello_service with async service methods."""
    s = MagicMock()
    s.card_types = {"task": "Task", "bug": "Bug", "feature": "Feature"}
    s.get_service_info = AsyncMock(return_value={"status": "ok", "version": "1"})
    s.get_boards = AsyncMock(return_value=[{"id": "b1", "name": "Board 1"}])
    s.get_board = AsyncMock(return_value={"id": "b1", "name": "Board 1"})
    s.get_lists = AsyncMock(return_value=[{"id": "l1", "name": "List 1"}])
    s.get_cards = AsyncMock(return_value=[{"id": "c1", "name": "Card 1"}])
    s.get_card = AsyncMock(return_value={"id": "c1", "name": "Card 1"})
    s.create_card = AsyncMock(return_value={"id": "c-new", "name": "New"})
    s.update_card = AsyncMock(return_value={"id": "c1", "name": "Updated"})
    s.delete_card = AsyncMock(return_value={"success": True})
    s.get_members = AsyncMock(return_value=[{"id": "m1", "fullName": "M1"}])
    s.search_cards = AsyncMock(return_value=[{"id": "c1"}])
    s.get_board_activities = AsyncMock(return_value=[{"id": "act1"}])
    with patch.object(tr, "trello_service", s):
        yield s


def _assert_ok_payload(response):
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    return body


class TestAuthAndHealth:
    def test_get_auth_url(self, client):
        response = client.get("/api/trello/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert "url" in body
        assert "timestamp" in body

    def test_oauth_callback(self, client):
        body = _assert_ok_payload(client.get("/api/trello/callback", params={"token": "tok-123"}))
        assert body["token"] == "tok-123"
        assert body["status"] == "success"

    def test_health_success(self, client, svc):
        response = client.get("/api/trello/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service_available"] is True
        assert body["service_info"] == {"status": "ok", "version": "1"}
        assert body["api_key_configured"] in (True, False)
        svc.get_service_info.assert_awaited_once()

    def test_health_exception_503(self, client, svc):
        svc.get_service_info.side_effect = RuntimeError("boom")
        response = client.get("/api/trello/health")
        assert response.status_code == 503
        body = response.json()
        assert body["detail"]["status"] == "unhealthy"
        assert body["detail"]["service"] == "trello"

    def test_status_alias(self, client, svc):
        response = client.get("/api/trello/status")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestBoards:
    def test_get_boards_success(self, client, svc):
        body = _assert_ok_payload(
            client.post("/api/trello/boards", json={
                "user_id": "u1", "include_closed": True, "limit": 5,
                "fields": ["name", "id"]}))
        assert body["data"]["total_count"] == 1
        assert body["data"]["user_id"] == "u1"
        svc.get_boards.assert_awaited_once()
        assert svc.get_boards.call_args.kwargs["include_closed"] is True
        assert svc.get_boards.call_args.kwargs["limit"] == 5
        assert svc.get_boards.call_args.kwargs["fields"] == ["name", "id"]

    def test_get_boards_defaults(self, client, svc):
        _assert_ok_payload(client.post("/api/trello/boards", json={"user_id": "u1"}))
        assert svc.get_boards.call_args.kwargs["include_closed"] is False
        assert svc.get_boards.call_args.kwargs["limit"] == 50

    def test_get_boards_exception_500(self, client, svc):
        svc.get_boards.side_effect = RuntimeError("down")
        response = client.post("/api/trello/boards", json={"user_id": "u1"})
        assert response.status_code == 500
        assert response.json()["detail"]["ok"] is False

    def test_get_board_success(self, client, svc):
        body = _assert_ok_payload(
            client.post("/api/trello/boards/b1", json={
                "user_id": "u1", "fields": ["name", "id"]}))
        assert body["data"]["board"]["id"] == "b1"
        svc.get_board.assert_awaited_once_with(board_id="b1", user_id="u1", fields=["name", "id"])

    def test_get_board_exception_500(self, client, svc):
        svc.get_board.side_effect = RuntimeError("down")
        response = client.post("/api/trello/boards/b1", json={"user_id": "u1"})
        assert response.status_code == 500
        assert "board_id" in response.json()["detail"]


class TestLists:
    def test_get_lists_success(self, client, svc):
        body = _assert_ok_payload(
            client.post("/api/trello/lists", json={
                "user_id": "u1", "board_id": "b1", "include_closed": True,
                "limit": 10, "fields": ["name", "id"]}))
        assert body["data"]["total_count"] == 1
        assert body["data"]["board_id"] == "b1"
        assert svc.get_lists.call_args.kwargs["board_id"] == "b1"

    def test_get_lists_exception_500(self, client, svc):
        svc.get_lists.side_effect = RuntimeError("down")
        response = client.post("/api/trello/lists", json={"user_id": "u1", "board_id": "b1"})
        assert response.status_code == 500


class TestCards:
    def test_get_cards_success(self, client, svc):
        body = _assert_ok_payload(
            client.post("/api/trello/cards", json={
                "user_id": "u1", "board_id": "b1", "list_id": "l1",
                "include_archived": True, "limit": 20, "fields": ["name", "id"]}))
        assert body["data"]["total_count"] == 1
        assert svc.get_cards.call_args.kwargs["include_archived"] is True

    def test_get_cards_exception_500(self, client, svc):
        svc.get_cards.side_effect = RuntimeError("down")
        response = client.post("/api/trello/cards", json={"user_id": "u1"})
        assert response.status_code == 500

    def test_get_card_success(self, client, svc):
        body = _assert_ok_payload(
            client.post("/api/trello/cards/c1", json={"user_id": "u1"}))
        assert body["data"]["card"]["id"] == "c1"
        svc.get_card.assert_awaited_once()

    def test_get_card_exception_500(self, client, svc):
        svc.get_card.side_effect = RuntimeError("down")
        response = client.post("/api/trello/cards/c1", json={"user_id": "u1"})
        assert response.status_code == 500

    # Regression: POST /cards/create must route to create_card, not get_card
    # (previously shadowed by POST /cards/{card_id} -> card_id="create").
    def test_create_card_via_http(self, client, svc):
        body = _assert_ok_payload(
            client.post("/api/trello/cards/create", json={
                "user_id": "u1", "name": "My Card", "id_list": "l1",
                "desc": "d", "due": None, "labels": ["lab1"],
                "card_type": "task"}))
        assert body["data"]["card"]["id"] == "c-new"
        svc.create_card.assert_awaited_once()
        kwargs = svc.create_card.call_args.kwargs
        assert kwargs["card_data"]["name"] == "[TASK] My Card"
        assert kwargs["card_data"]["idList"] == "l1"
        assert kwargs["card_data"]["idLabels"] == ["lab1"]
        assert svc.get_card.await_count == 0

    def test_create_card_unknown_card_type(self, client, svc):
        _assert_ok_payload(
            client.post("/api/trello/cards/create", json={
                "user_id": "u1", "name": "Plain", "id_list": "l1",
                "card_type": "mystery"}))
        assert svc.create_card.call_args.kwargs["card_data"]["name"] == "Plain"

    def test_create_card_exception_500(self, client, svc):
        svc.create_card.side_effect = RuntimeError("down")
        response = client.post("/api/trello/cards/create", json={
            "user_id": "u1", "name": "X", "id_list": "l1"})
        assert response.status_code == 500

    # Regression: real TrelloService has NO card_types attribute; create_card
    # must not crash (AttributeError) and must send the plain name.
    def test_create_card_real_service_without_card_types(self, client):
        real = tr.TrelloService()
        real.create_card = AsyncMock(return_value={"id": "c-real"})
        with patch.object(tr, "trello_service", real):
            body = _assert_ok_payload(
                client.post("/api/trello/cards/create", json={
                    "user_id": "u1", "name": "Real", "id_list": "l1",
                    "card_type": "bug"}))
        assert body["data"]["card"]["id"] == "c-real"
        assert real.create_card.call_args.kwargs["card_data"]["name"] == "Real"

    def test_update_card_all_fields(self, client, svc):
        body = _assert_ok_payload(
            client.put("/api/trello/cards/c1", json={
                "user_id": "u1", "name": "n", "desc": "d", "due": "2026-09-01",
                "id_list": "l2", "labels": ["l1", "l2"]}))
        assert body["data"]["message"] == "Card c1 updated successfully"
        update_data = svc.update_card.call_args.kwargs["update_data"]
        assert update_data == {"name": "n", "desc": "d", "due": "2026-09-01",
                               "idList": "l2", "idLabels": ["l1", "l2"]}

    def test_update_card_partial_fields(self, client, svc):
        _assert_ok_payload(client.put("/api/trello/cards/c1", json={
            "user_id": "u1", "name": "only-name"}))
        assert svc.update_card.call_args.kwargs["update_data"] == {"name": "only-name"}

    def test_update_card_no_fields_empty_payload(self, client, svc):
        _assert_ok_payload(client.put("/api/trello/cards/c1", json={"user_id": "u1"}))
        assert svc.update_card.call_args.kwargs["update_data"] == {}

    def test_update_card_exception_500(self, client, svc):
        svc.update_card.side_effect = RuntimeError("down")
        response = client.put("/api/trello/cards/c1", json={"user_id": "u1"})
        assert response.status_code == 500

    def test_delete_card_success(self, client, svc):
        body = _assert_ok_payload(
            client.request("DELETE", "/api/trello/cards/c1", json={"user_id": "u1"}))
        assert body["data"]["message"] == "Card c1 deleted successfully"
        svc.delete_card.assert_awaited_once_with(card_id="c1", user_id="u1")

    def test_delete_card_exception_500(self, client, svc):
        svc.delete_card.side_effect = RuntimeError("down")
        response = client.request("DELETE", "/api/trello/cards/c1", json={"user_id": "u1"})
        assert response.status_code == 500


class TestMembers:
    def test_get_members_success(self, client, svc):
        body = _assert_ok_payload(
            client.post("/api/trello/members", json={
                "user_id": "u1", "board_id": "b1", "include_guests": True,
                "limit": 5, "fields": ["fullName", "id"]}))
        assert body["data"]["total_count"] == 1
        assert svc.get_members.call_args.kwargs["include_guests"] is True

    def test_get_members_exception_500(self, client, svc):
        svc.get_members.side_effect = RuntimeError("down")
        response = client.post("/api/trello/members", json={"user_id": "u1", "board_id": "b1"})
        assert response.status_code == 500


class TestUserProfile:
    def test_get_user_profile(self, client):
        body = _assert_ok_payload(client.post("/api/trello/user/profile", json={"user_id": "u1"}))
        assert body["data"]["user"]["id"] == "u1"
        assert body["data"]["enterprise"]["enterpriseName"] == "ATOM Platform"


class TestSearch:
    def test_search_success(self, client, svc):
        body = _assert_ok_payload(
            client.post("/api/trello/search", json={
                "user_id": "u1", "query": "alpha", "type": "board",
                "limit": 5, "board_id": "b1"}))
        assert body["data"]["total_count"] == 1
        assert svc.search_cards.call_args.kwargs["search_type"] == "board"

    def test_search_exception_500(self, client, svc):
        svc.search_cards.side_effect = RuntimeError("down")
        response = client.post("/api/trello/search", json={"user_id": "u1", "query": "q"})
        assert response.status_code == 500


class TestActivities:
    def test_get_board_activities_success(self, client, svc):
        body = _assert_ok_payload(
            client.post("/api/trello/activities", json={
                "user_id": "u1", "board_id": "b1", "limit": 5, "since": "2026-08-01"}))
        assert body["data"]["total_count"] == 1
        assert svc.get_board_activities.call_args.kwargs["since"] == "2026-08-01"

    def test_get_board_activities_exception_500(self, client, svc):
        svc.get_board_activities.side_effect = RuntimeError("down")
        response = client.post("/api/trello/activities", json={"user_id": "u1", "board_id": "b1"})
        assert response.status_code == 500


class TestServiceInfo:
    def test_get_service_info_success(self, client, svc):
        body = _assert_ok_payload(client.get("/api/trello/info"))
        assert body["data"]["service"] == "trello"
        assert body["data"]["version"] == "1.0.0"
        assert body["data"]["info"] == {"status": "ok", "version": "1"}

    def test_get_service_info_exception_500(self, client, svc):
        svc.get_service_info.side_effect = RuntimeError("down")
        response = client.get("/api/trello/info")
        assert response.status_code == 500


class TestOptionalEnhancedServiceImport:
    """Cover the try/except import guard (trello_enhanced_service optional)."""

    def test_enhanced_service_import_branch(self):
        fake_mod = types.ModuleType("trello_enhanced_service")

        class TrelloEnhancedService:
            pass

        fake_mod.TrelloEnhancedService = TrelloEnhancedService
        saved = sys.modules.get("trello_enhanced_service")
        sys.modules["trello_enhanced_service"] = fake_mod
        try:
            reloaded = importlib.reload(tr)
            assert reloaded.TrelloEnhancedService is TrelloEnhancedService
            assert isinstance(reloaded.trello_service, TrelloEnhancedService)
        finally:
            if saved is not None:
                sys.modules["trello_enhanced_service"] = saved
            else:
                sys.modules.pop("trello_enhanced_service", None)
            importlib.reload(tr)
            assert tr.TrelloEnhancedService is None
