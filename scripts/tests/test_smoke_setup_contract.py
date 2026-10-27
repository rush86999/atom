"""No-network setup-contract battery for the deployment smoke.

Every test loads the development and packaged helper copies and drives the real
helper functions. HTTP is the only mocked seam; no live records, network or
model calls are used.
"""
from __future__ import annotations

import ast
import importlib.util
import os
import uuid
from pathlib import Path

import pytest

DEV_SMOKE = Path(__file__).resolve().parents[1] / "smoke_release_candidate_ae0c2fda3.py"
PACKAGED_SMOKE = Path(os.environ.get(
    "ATOM_RELEASE_SMOKE_PATH",
    "/Users/rushiparikh/projects/atom-releases/68ec00b85/scripts/"
    "smoke_release_candidate_ae0c2fda3.py",
))
CANDIDATE_BACKEND = Path(os.environ.get(
    "ATOM_CANDIDATE_BACKEND",
    "/Users/rushiparikh/projects/atom-releases/68ec00b85/backend",
))
SMOKE_PATHS = (DEV_SMOKE, PACKAGED_SMOKE)
SMOKE_IDS = ("development", "packaged")


def load_smoke(path: Path):
    if not path.is_file():
        pytest.skip(f"smoke script not present: {path}")
    spec = importlib.util.spec_from_file_location(
        f"setup_smoke_{uuid.uuid4().hex}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code: int, payload=None, malformed=False,
                 text=""):
        self.status_code = status_code
        self.payload = payload
        self.malformed = malformed
        self.text = text

    def json(self):
        if self.malformed:
            raise ValueError("not json")
        return self.payload


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected {method} {url}")
        response = self.responses.pop(0)
        if not isinstance(response, FakeResponse):
            response = FakeResponse(*response)
        return response

    def post(self, url, **kwargs):
        return self._next("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self._next("GET", url, **kwargs)


def install_http(monkeypatch, responses):
    import httpx

    fake = FakeHTTP(responses)
    monkeypatch.setattr(httpx, "post", fake.post)
    monkeypatch.setattr(httpx, "get", fake.get)
    return fake


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_login_contract_accepts_valid_token_and_user(smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    fake = install_http(monkeypatch, [
        (200, {"access_token": "token-1"}),
        (200, {"data": {"id": "user-1", "workspace_id": "default"}}),
    ])

    token, user = module.login("http://candidate", "admin@example.com", "pw")

    assert token == "token-1"
    assert user["id"] == "user-1"
    assert [call["url"].split("http://candidate")[-1] for call in fake.calls] == [
        "/api/auth/login", "/api/auth/me"]


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_login_rejects_missing_token(smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    install_http(monkeypatch, [(200, {"access_token": ""})])
    with pytest.raises(RuntimeError, match="access_token"):
        module.login("http://candidate", "admin@example.com", "pw")


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_guided_agent_201_valid_id(smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    fake = install_http(monkeypatch, [
        (201, {"success": True, "data": {"agent_id": "agent-1"}}),
    ])

    assert module.create_agent(
        "http://candidate", "token", "smoke-1") == "agent-1"
    assert fake.calls[0]["url"].endswith("/api/agents/guided")


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_guided_agent_rejects_202_pending_approval(smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    install_http(monkeypatch, [
        (202, {"success": True, "data": {
            "status": "pending_approval", "hitl_action_id": "hitl-1"}}),
    ])
    with pytest.raises(RuntimeError, match="pending approval"):
        module.create_agent("http://candidate", "token", "smoke-1")


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
@pytest.mark.parametrize("payload_kind", (
    "missing_id", "blank_id", "non_string_id", "missing_data",
    "non_dict_data", "failure_payload", "malformed_json", "http_200",
))
def test_guided_agent_rejects_invalid_contract(smoke_path, monkeypatch,
                                               payload_kind):
    module = load_smoke(smoke_path)
    if payload_kind == "missing_id":
        response = (201, {"success": True, "data": {}})
    elif payload_kind == "blank_id":
        response = (201, {"success": True, "data": {"agent_id": "  "}})
    elif payload_kind == "non_string_id":
        response = (201, {"success": True, "data": {"agent_id": 123}})
    elif payload_kind == "missing_data":
        response = (201, {"success": True})
    elif payload_kind == "non_dict_data":
        response = (201, {"success": True, "data": ["agent-1"]})
    elif payload_kind == "failure_payload":
        response = (201, {"success": False, "data": {"agent_id": "agent-1"}})
    elif payload_kind == "malformed_json":
        response = FakeResponse(201, malformed=True)
    else:
        response = (200, {"success": True, "data": {"agent_id": "agent-1"}})
    install_http(monkeypatch, [response])
    with pytest.raises(RuntimeError):
        module.create_agent("http://candidate", "token", "smoke-1")


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_canvas_create_and_attach_contract(smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    install_http(monkeypatch, [
        (200, {"success": True, "canvas_id": "canvas-1"}),
        (200, {"success": True, "canvas_id": "canvas-1",
               "agent_id": "agent-1"}),
    ])
    assert module.create_canvas(
        "http://candidate", "token", "smoke-1", "agent-1") == "canvas-1"


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_canvas_attach_rejects_mismatched_agent(smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    install_http(monkeypatch, [
        (200, {"success": True, "canvas_id": "canvas-1"}),
        (200, {"success": True, "canvas_id": "canvas-1",
               "agent_id": "other-agent"}),
    ])
    with pytest.raises(RuntimeError, match="agent id"):
        module.create_canvas("http://candidate", "token", "smoke-1", "agent-1")


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_upload_workbook_contract(smoke_path, monkeypatch, tmp_path):
    module = load_smoke(smoke_path)
    workbook = tmp_path / "orders.xlsx"
    workbook.write_bytes(b"xlsx")
    install_http(monkeypatch, [
        (200, {
            "success": True,
            "canvas_id": "canvas-1",
            "agent_id": "agent-1",
            "file_name": "orders.xlsx",
            "ingestion": {"status": "ingested"},
        }),
    ])
    result = module.upload_workbook(
        "http://candidate", "token", "canvas-1", workbook)
    assert result["body"]["ingestion"]["status"] == "ingested"


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_upload_workbook_rejects_non_ingested(smoke_path, monkeypatch,
                                              tmp_path):
    module = load_smoke(smoke_path)
    workbook = tmp_path / "orders.xlsx"
    workbook.write_bytes(b"xlsx")
    install_http(monkeypatch, [
        (200, {
            "success": True,
            "canvas_id": "canvas-1",
            "agent_id": "agent-1",
            "file_name": "orders.xlsx",
            "ingestion": {"status": "failed"},
        }),
    ])
    with pytest.raises(RuntimeError, match="ingest"):
        module.upload_workbook(
            "http://candidate", "token", "canvas-1", workbook)


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_teach_contract(smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    install_http(monkeypatch, [
        (200, {"success": True, "data": {"status": "ok"}}),
    ])
    result = module.teach(
        "http://candidate", "token", "agent-1", "lesson", "topic")
    assert result["body"]["data"]["status"] == "ok"


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
@pytest.mark.parametrize("status", ("skipped", "failed"))
def test_teach_rejects_non_landed_lesson(smoke_path, monkeypatch, status):
    module = load_smoke(smoke_path)
    install_http(monkeypatch, [
        (200, {"success": True, "data": {"status": status}}),
    ])
    with pytest.raises(RuntimeError, match="teaching did not land"):
        module.teach(
            "http://candidate", "token", "agent-1", "lesson", "topic")


@pytest.mark.parametrize("smoke_path", SMOKE_PATHS, ids=SMOKE_IDS)
def test_full_setup_sequence_with_mocked_http(smoke_path, monkeypatch,
                                              tmp_path):
    module = load_smoke(smoke_path)
    workbook = tmp_path / "orders.xlsx"
    workbook.write_bytes(b"xlsx")
    fake = install_http(monkeypatch, [
        (200, {"access_token": "token-1"}),
        (200, {"data": {"id": "user-1"}}),
        (201, {"success": True, "data": {"agent_id": "agent-1"}}),
        (200, {"success": True, "canvas_id": "canvas-1"}),
        (200, {"success": True, "canvas_id": "canvas-1",
               "agent_id": "agent-1"}),
        (200, {
            "success": True,
            "canvas_id": "canvas-1",
            "agent_id": "agent-1",
            "file_name": "orders.xlsx",
            "ingestion": {"status": "ingested"},
        }),
        (200, {"success": True, "data": {"status": "ok"}}),
    ])

    token, user = module.login(
        "http://candidate", "admin@example.com", "pw")
    agent_id = module.create_agent(
        "http://candidate", token, "smoke-1")
    canvas_id = module.create_canvas(
        "http://candidate", token, "smoke-1", agent_id)
    module.upload_workbook(
        "http://candidate", token, canvas_id, workbook)
    module.teach(
        "http://candidate", token, agent_id, "lesson", "topic")

    assert (token, user["id"], agent_id, canvas_id) == (
        "token-1", "user-1", "agent-1", "canvas-1")
    paths = [call["url"].split("http://candidate")[-1] for call in fake.calls]
    assert paths == [
        "/api/auth/login",
        "/api/auth/me",
        "/api/agents/guided",
        "/api/canvas",
        "/api/canvas/canvas-1/agents",
        "/api/canvas/canvas-1/data/upload",
        "/api/agents/agent-1/teach",
    ]


def test_candidate_route_status_declarations():
    """Static contract audit of the frozen candidate's route declarations."""
    if not CANDIDATE_BACKEND.is_dir():
        pytest.fail(f"candidate backend not present: {CANDIDATE_BACKEND}")

    def status_for(path: Path, route: str):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                if decorator.func.attr != "post" or not decorator.args:
                    continue
                if not isinstance(decorator.args[0], ast.Constant):
                    continue
                if decorator.args[0].value != route:
                    continue
                for keyword in decorator.keywords:
                    if (keyword.arg == "status_code"
                            and isinstance(keyword.value, ast.Constant)):
                        return keyword.value.value
                return 200
        raise AssertionError(f"route not found: {route} in {path}")

    assert status_for(
        CANDIDATE_BACKEND / "api" / "agent_onboarding_routes.py",
        "/guided") == 201
    assert status_for(
        CANDIDATE_BACKEND / "api" / "canvas_routes.py",
        "/{canvas_id}/agents") == 200
    assert status_for(
        CANDIDATE_BACKEND / "api" / "canvas_routes.py",
        "/{canvas_id}/data/upload") == 200
    assert status_for(
        CANDIDATE_BACKEND / "api" / "agent_onboarding_routes.py",
        "/{agent_id}/teach") == 200


def test_candidate_guided_route_integration_201(monkeypatch):
    """Exercise the frozen candidate route with the generation seam mocked."""
    if not CANDIDATE_BACKEND.is_dir():
        pytest.fail(f"candidate backend not present: {CANDIDATE_BACKEND}")
    import sys
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    sys.path.insert(0, str(CANDIDATE_BACKEND))
    try:
        import api.agent_onboarding_routes as routes
    except Exception as exc:  # noqa: BLE001 — report the actual import failure
        pytest.fail(f"could not import candidate guided route: {exc}")
    finally:
        try:
            sys.path.remove(str(CANDIDATE_BACKEND))
        except ValueError:
            pass

    class FakeDB:
        def __init__(self):
            self.added = []

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            return None

        def refresh(self, obj):
            obj.id = "agent-route-1"

    class FakeFactory:
        async def design_agent(self, goal, context):
            return {
                "name": "Scratch Contract Agent",
                "description": "A scratch agent for route-contract testing.",
                "category": "operations",
                "configuration": {},
                "capabilities": [],
                "template": "custom",
            }

    db = FakeDB()
    user = SimpleNamespace(
        id="user-route", workspace_id=None, tenant_id=None)
    monkeypatch.setattr(
        routes, "get_guided_agent_factory", lambda: FakeFactory())
    app = FastAPI()
    app.post("/api/agents/guided", status_code=201)(routes.create_guided_agent)
    app.dependency_overrides[routes.get_current_user] = lambda: user
    app.dependency_overrides[routes.get_db] = lambda: db
    client = TestClient(app)

    response = client.post(
        "/api/agents/guided",
        json={"goal": "Review order records from the workbook.",
              "context": "Scratch contract test."},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body.get("success") is True, body
    assert isinstance(body.get("data"), dict), body
    assert body["data"].get("agent_id") == "agent-route-1", body
    assert db.added and db.added[0].id == "agent-route-1"
