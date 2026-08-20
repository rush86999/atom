"""
Tests for the A2A (Agent2Agent) protocol bridge — api/a2a_routes.py.

Mirrors the conventions of the ACP bridge tests (tests/test_berd_gap_closures.py):
auth is mocked by patching api.a2a_routes.get_current_user_ws + SessionLocal,
and the agent execution service (ChatOrchestrator) is monkeypatched.
"""

import os
os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def client():
    from api.a2a_routes import router as a2a_router

    app = FastAPI(title="Atom A2A Test")
    app.include_router(a2a_router)
    yield TestClient(app)


@pytest.fixture(scope="function")
def fake_user():
    user = MagicMock()
    user.id = "u1"
    return user


@pytest.fixture(scope="function")
def auth(client, fake_user):
    """Patch auth so every request with a token is user u1."""
    with patch("api.a2a_routes.get_current_user_ws", AsyncMock(return_value=fake_user)), \
         patch("api.a2a_routes.SessionLocal", return_value=MagicMock()):
        yield client


def _send_payload(text="hello atom"):
    return {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": "m-1",
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                "contextId": "ctx-1",
            },
            "metadata": {},
        },
    }


# --------------------------------------------------------------------------- #
# Agent Card
# --------------------------------------------------------------------------- #

def test_agent_card_shape(client):
    for path in ("/.well-known/agent-card.json", "/api/a2a/agent-card"):
        resp = client.get(path)
        assert resp.status_code == 200
        card = resp.json()
        assert card["name"] == "Atom"
        assert card["description"]
        assert card["url"].endswith("/api/a2a")
        assert card["version"]
        assert card["capabilities"] == {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        }
        assert card["defaultInputModes"] == ["text"]
        assert card["defaultOutputModes"] == ["text"]
        assert isinstance(card["skills"], list) and card["skills"]
        for skill in card["skills"]:
            assert "id" in skill and "description" in skill


# --------------------------------------------------------------------------- #
# message/send
# --------------------------------------------------------------------------- #

def test_message_send_happy_path(auth):
    fake_orch = MagicMock()
    fake_orch.process_chat_message = AsyncMock(
        return_value={"message": "hi from atom"}
    )
    with patch("integrations.chat_orchestrator.ChatOrchestrator", return_value=fake_orch):
        resp = auth.post("/api/a2a", json=_send_payload(), headers={"Authorization": "Bearer t"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 7
    result = body["result"]
    assert result["kind"] == "message"
    assert result["role"] == "agent"
    assert result["parts"] == [{"kind": "text", "text": "hi from atom"}]
    assert result["messageId"]
    # The agent was invoked with the extracted text.
    args = fake_orch.process_chat_message.await_args.kwargs
    assert args["message"] == "hello atom"
    assert args["user_id"] == "u1"


def test_message_send_token_via_query_param(auth):
    fake_orch = MagicMock()
    fake_orch.process_chat_message = AsyncMock(return_value={"message": "ok"})
    with patch("integrations.chat_orchestrator.ChatOrchestrator", return_value=fake_orch):
        resp = auth.post("/api/a2a?token=t", json=_send_payload())
    assert resp.status_code == 200
    assert resp.json()["result"]["parts"][0]["text"] == "ok"


def test_method_not_found(auth):
    resp = auth.post(
        "/api/a2a",
        json={"jsonrpc": "2.0", "id": 3, "method": "tasks/get", "params": {}},
        headers={"Authorization": "Bearer t"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == -32601
    assert body["error"]["message"] == "Method not found"
    assert body["id"] == 3


def test_malformed_json(auth):
    resp = auth.post(
        "/api/a2a",
        content="{not json",
        headers={"Authorization": "Bearer t", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == -32700
    assert body["error"]["message"] == "Parse error"
    assert body["id"] is None


def test_invalid_params_no_text(auth):
    payload = _send_payload()
    payload["params"]["message"]["parts"] = [{"kind": "file", "uri": "x"}]
    resp = auth.post("/api/a2a", json=payload, headers={"Authorization": "Bearer t"})
    body = resp.json()
    assert body["error"]["code"] == -32602


def test_unauthenticated(client):
    resp = client.post("/api/a2a", json=_send_payload())
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == -32001

    # Invalid token goes through the auth helper and fails too.
    with patch("api.a2a_routes.get_current_user_ws", AsyncMock(return_value=None)), \
         patch("api.a2a_routes.SessionLocal", return_value=MagicMock()):
        resp = client.post(
            "/api/a2a", json=_send_payload(), headers={"Authorization": "Bearer bad"}
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == -32001


def test_rate_limit(auth):
    fake_orch = MagicMock()
    fake_orch.process_chat_message = AsyncMock(return_value={"message": "x"})
    from api import a2a_routes

    with patch("integrations.chat_orchestrator.ChatOrchestrator", return_value=fake_orch), \
         patch.object(a2a_routes, "_RATE_LIMIT_MAX", 2), \
         patch.object(a2a_routes, "_rate_buckets", {}):
        for _ in range(2):
            r = auth.post("/api/a2a", json=_send_payload(), headers={"Authorization": "Bearer t"})
            assert r.status_code == 200
        r = auth.post("/api/a2a", json=_send_payload(), headers={"Authorization": "Bearer t"})
        assert r.status_code == 429
        assert r.json()["error"]["code"] == -32002
