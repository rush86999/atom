"""Durable task consumers: chat intents, public task API and current authority."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import core.models  # noqa: F401
from api.nav_stub_routes import router as nav_router
from core.atom_agent_endpoints import ChatRequest, handle_task_intent
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import Tenant, User, UserTask, Workspace
from core.user_task_service import (
    TaskAuthorityError,
    TaskValidationError,
    create_user_task,
    update_user_task,
)
from integrations.chat_orchestrator import ChatOrchestrator
from service_delivery.models import Project

_DUE = datetime(2031, 5, 6, 7, 8, 9, tzinfo=timezone.utc)


@pytest.fixture()
def env(tmp_path):
    db_path = tmp_path / "chat_task_durability.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    tenant = Tenant(
        id="default", name="Personal", subdomain="personal",
        edition="personal", is_active=True)
    workspace = Workspace(
        id="default", name="Default", tenant_id="default",
        status="active")
    other_workspace = Workspace(
        id="other-workspace", name="Other", tenant_id="default",
        status="active")
    user = User(
        id="task-user", email="task@example.com", hashed_password="h",
        first_name="Task", last_name="User", role="member",
        status="active", is_active=True, tenant_id="default",
        workspace_id="default")
    other_user = User(
        id="other-user", email="other@example.com", hashed_password="h",
        first_name="Other", last_name="User", role="member",
        status="active", is_active=True, tenant_id="default",
        workspace_id="default")
    project = Project(
        id="project-1", workspace_id="default", name="Project One")
    project_two = Project(
        id="project-2", workspace_id="default", name="Project Two")
    foreign_project = Project(
        id="foreign-project", workspace_id="other-workspace",
        name="Foreign")
    db.add_all([
        tenant, workspace, other_workspace, user, other_user,
        project, project_two, foreign_project,
    ])
    db.commit()
    try:
        yield {
            "engine": engine,
            "Session": Session,
            "db": db,
            "path": str(db_path),
            "user": user,
            "other_user": other_user,
            "project": project,
            "project_two": project_two,
            "foreign_project": foreign_project,
        }
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def auth_headers(env):
    token = create_access_token(
        data={"sub": env["user"].id}, user=env["user"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def public_client(env):
    app = FastAPI()
    app.include_router(nav_router)

    def _get_db():
        session = env["Session"]()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    return TestClient(app, base_url="http://testserver")


def _public_tasks(client, headers):
    response = client.get("/api/v1/tasks", headers=headers)
    assert response.status_code == 200
    return response.json()["tasks"]


def _chat_stub(env, session_id, user_id):
    return SimpleNamespace(
        ai_engines={},
        conversation_sessions={
            session_id: {"id": session_id, "user_id": user_id}
        },
        session_manager=None,
    )


def _patch_chat_db(monkeypatch, Session):
    @contextmanager
    def _factory():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(
        "core.database.get_db_session", _factory)


def test_atom_create_is_publicly_listed_same_current_user(
        env, auth_headers, public_client):
    result = __import__("asyncio").run(handle_task_intent(
        "CREATE_TASK",
        {"title": "Atom durable task", "project": env["project"].id},
        ChatRequest(message="Create atom durable task", user_id=env["user"].id),
        current_user=env["user"],
        db=env["db"],
    ))
    assert result["success"] is True
    task_data = result["response"]["data"]["task"]
    task_id = task_data["id"]
    assert task_data["title"] == "Atom durable task"

    fresh = env["Session"]()
    try:
        row = fresh.query(UserTask).filter(UserTask.id == task_id).one()
        assert row.user_id == env["user"].id
        assert row.title == "Atom durable task"
        assert row.project_id == env["project"].id
    finally:
        fresh.close()

    tasks = _public_tasks(public_client, auth_headers)
    assert any(
        task["id"] == task_id
        and task["title"] == "Atom durable task"
        and task["project"] == env["project"].id
        for task in tasks
    )


def test_chat_orchestrator_create_is_publicly_listed_same_current_user(
        env, auth_headers, public_client, monkeypatch):
    _patch_chat_db(monkeypatch, env["Session"])
    session_id = "session-chat-task"
    stub = _chat_stub(env, session_id, env["user"].id)
    result = __import__("asyncio").run(
        ChatOrchestrator._handle_task_request(
            stub,
            "Create a durable chat task",
            {},
            {"id": session_id, "user_id": env["user"].id},
            {"request_id": "chat-request-1"},
        )
    )
    assert result["success"] is True
    task_id = result["data"]["task_id"]
    assert task_id
    assert result["data"]["task"]["title"]

    tasks = _public_tasks(public_client, auth_headers)
    assert any(task["id"] == task_id for task in tasks)


def test_missing_or_foreign_chat_authority_writes_nothing(
        env, monkeypatch):
    _patch_chat_db(monkeypatch, env["Session"])
    session_id = "session-no-authority"

    missing = _chat_stub(env, session_id, "system")
    result = __import__("asyncio").run(
        ChatOrchestrator._handle_task_request(
            missing, "Create an orphan task", {}, {"id": session_id}, {})
    )
    assert result["success"] is False

    unbound = SimpleNamespace(
        ai_engines={}, conversation_sessions={}, session_manager=None)
    result = __import__("asyncio").run(
        ChatOrchestrator._handle_task_request(
            unbound, "Create an unbound task", {},
            {"id": session_id, "user_id": env["user"].id}, {})
    )
    assert result["success"] is False

    fresh = env["Session"]()
    try:
        assert fresh.query(UserTask).count() == 0
    finally:
        fresh.close()


def test_disabled_user_refuses_before_write(env):
    env["user"].status = "suspended"
    env["user"].is_active = False
    env["db"].commit()

    result = __import__("asyncio").run(handle_task_intent(
        "CREATE_TASK",
        {"title": "Disabled task"},
        ChatRequest(message="Create disabled task", user_id=env["user"].id),
        current_user=env["user"],
        db=env["db"],
    ))
    assert result["success"] is False
    fresh = env["Session"]()
    try:
        assert fresh.query(UserTask).count() == 0
    finally:
        fresh.close()


def test_foreign_project_refuses_before_write(env):
    result = __import__("asyncio").run(handle_task_intent(
        "CREATE_TASK",
        {"title": "Foreign project task", "project": env["foreign_project"].id},
        ChatRequest(message="Create foreign task", user_id=env["user"].id),
        current_user=env["user"],
        db=env["db"],
    ))
    assert result["success"] is False
    fresh = env["Session"]()
    try:
        assert fresh.query(UserTask).count() == 0
    finally:
        fresh.close()


def test_idempotent_create_same_material_replays_one_row(env):
    payload = {
        "title": "Stable idempotent task",
        "dueDate": _DUE,
        "status": "todo",
        "priority": "medium",
        "estimatedHours": 1,
        "tags": ["one"],
        "metadata": {"source": "test"},
        "idempotencyKey": "stable-request-1",
    }
    first = create_user_task(env["db"], env["user"], payload)
    second = create_user_task(env["db"], env["user"], payload)
    assert first.id == second.id
    fresh = env["Session"]()
    try:
        assert fresh.query(UserTask).count() == 1
    finally:
        fresh.close()


@pytest.mark.parametrize("changes", [
    {"status": "in_progress"},
    {"description": "changed description"},
    {"dueDate": _DUE + timedelta(days=2)},
    {"estimatedHours": 9},
    {"tags": ["two"]},
    {"metadata": {"source": "changed"}},
    {"project": "project-2"},
], ids=[
    "status", "description", "due", "hours", "tags", "metadata", "project",
])
def test_same_key_same_title_changed_material_is_typed_conflict(env, changes):
    payload = {
        "title": "Same title",
        "dueDate": _DUE,
        "status": "todo",
        "priority": "medium",
        "estimatedHours": 1,
        "tags": ["one"],
        "metadata": {"source": "test"},
        "idempotencyKey": "material-request-1",
    }
    original = create_user_task(env["db"], env["user"], payload)
    changed = dict(payload)
    changed.update(changes)

    with pytest.raises(TaskValidationError):
        create_user_task(env["db"], env["user"], changed)

    fresh = env["Session"]()
    try:
        assert fresh.query(UserTask).count() == 1
        row = fresh.query(UserTask).filter(UserTask.id == original.id).one()
        assert row.status == "todo"
        assert row.title == "Same title"
    finally:
        fresh.close()


def test_idempotent_retry_refuses_after_current_material_changes(env):
    payload = {
        "title": "Current material task",
        "dueDate": _DUE,
        "status": "todo",
        "idempotencyKey": "current-material-1",
    }
    task = create_user_task(env["db"], env["user"], payload)
    update_user_task(
        env["db"], env["user"], task.id, {"status": "in_progress"})

    with pytest.raises(TaskValidationError):
        create_user_task(env["db"], env["user"], payload)


@pytest.mark.parametrize("field,value", [
    ("status", "suspended"),
    ("is_active", False),
    ("role", "admin"),
    ("workspace_id", "peer-workspace"),
    ("hashed_password", "peer-credential"),
])
def test_peer_authority_change_before_claim_zero_effect(env, field, value):
    fired = {"done": False}

    def _peer(conn, cursor, statement, parameters, context, executemany):
        lowered = statement.lower()
        if fired["done"] or not lowered.lstrip().startswith("update users"):
            return
        fired["done"] = True
        peer = env["Session"]()
        try:
            row = peer.query(User).filter(User.id == env["user"].id).one()
            setattr(row, field, value)
            peer.commit()
        finally:
            peer.close()

    event.listen(env["engine"], "before_cursor_execute", _peer)
    try:
        with pytest.raises(TaskAuthorityError):
            create_user_task(
                env["db"], env["user"],
                {"title": "Peer raced task", "dueDate": _DUE},
            )
    finally:
        event.remove(env["engine"], "before_cursor_execute", _peer)

    assert fired["done"] is True
    fresh = env["Session"]()
    try:
        assert fresh.query(UserTask).count() == 0
        row = fresh.query(User).filter(User.id == env["user"].id).one()
        assert getattr(row, field) == value
    finally:
        fresh.close()


def test_public_create_still_uses_same_durable_store(
        env, auth_headers, public_client):
    created = public_client.post(
        "/api/v1/tasks",
        json={"title": "Public API task", "project": env["project"].id},
        headers=auth_headers,
    )
    assert created.status_code == 200
    task_id = created.json()["task"]["id"]
    tasks = _public_tasks(public_client, auth_headers)
    assert any(
        task["id"] == task_id and task["title"] == "Public API task"
        for task in tasks
    )
    fresh = env["Session"]()
    try:
        assert fresh.query(UserTask).filter(
            UserTask.id == task_id, UserTask.user_id == env["user"].id
        ).count() == 1
    finally:
        fresh.close()


_CHILD_LIST_SCRIPT = '''\
import json
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.nav_stub_routes import router
from core.database import get_db

payload = json.load(open(sys.argv[1], encoding="utf-8"))
engine = create_engine(
    f"sqlite:///{payload['db_path']}",
    connect_args={"check_same_thread": False},
)
Session = sessionmaker(bind=engine)
app = FastAPI()
app.include_router(router)

def _get_db():
    session = Session()
    try:
        yield session
    finally:
        session.close()

app.dependency_overrides[get_db] = _get_db
client = TestClient(app, base_url="http://testserver")
response = client.get(
    "/api/v1/tasks",
    headers={"Authorization": f"Bearer {payload['token']}"},
)
tasks = response.json().get("tasks", []) if response.status_code == 200 else []
print(json.dumps({
    "status": response.status_code,
    "ids": [task.get("id") for task in tasks],
    "titles": [task.get("title") for task in tasks],
}))
'''


def test_public_list_after_fresh_process_restart(
        env, auth_headers, public_client, tmp_path):
    result = __import__("asyncio").run(handle_task_intent(
        "CREATE_TASK",
        {"title": "Restart durable task"},
        ChatRequest(message="Create restart task", user_id=env["user"].id),
        current_user=env["user"],
        db=env["db"],
    ))
    task_id = result["response"]["data"]["task"]["id"]
    token = auth_headers["Authorization"].split(" ", 1)[1]

    input_path = tmp_path / "child_task_list_input.json"
    input_path.write_text(json.dumps({
        "db_path": env["path"],
        "token": token,
    }), encoding="utf-8")
    os.chmod(input_path, 0o600)
    script_path = tmp_path / "child_task_list.py"
    script_path.write_text(_CHILD_LIST_SCRIPT, encoding="utf-8")
    os.chmod(script_path, 0o600)
    backend_dir = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, str(script_path), str(input_path)],
        cwd=str(backend_dir),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    log_path = tmp_path / "child_task_list.private.log"
    log_path.write_text(
        (completed.stdout or "") + "\n--- stderr ---\n" + (completed.stderr or ""),
        encoding="utf-8",
    )
    os.chmod(log_path, 0o600)
    assert completed.returncode == 0, {"child_exit": completed.returncode}
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    summary = json.loads(lines[-1])
    assert summary["status"] == 200
    assert task_id in summary["ids"]
    assert "Restart durable task" in summary["titles"]


def test_atom_consumer_replay_same_request_id_omitted_date(env):
    request = ChatRequest(
        message="Create a replayed atom task",
        user_id=env["user"].id,
        context={"request_id": "atom-replay-1"},
    )
    first = __import__("asyncio").run(handle_task_intent(
        "CREATE_TASK", {"title": "Replayed atom task"}, request,
        current_user=env["user"], db=env["db"]))
    second = __import__("asyncio").run(handle_task_intent(
        "CREATE_TASK", {"title": "Replayed atom task"}, request,
        current_user=env["user"], db=env["db"]))
    assert first["success"] is True
    assert second["success"] is True
    assert (
        first["response"]["data"]["task"]["id"]
        == second["response"]["data"]["task"]["id"]
    )
    fresh = env["Session"]()
    try:
        rows = fresh.query(UserTask).filter(
            UserTask.title == "Replayed atom task").all()
        assert len(rows) == 1
        assert rows[0].due_date is None
    finally:
        fresh.close()


def test_chat_consumer_replay_same_request_id_omitted_date(
        env, monkeypatch):
    _patch_chat_db(monkeypatch, env["Session"])
    session_id = "session-chat-replay"
    stub = _chat_stub(env, session_id, env["user"].id)
    session = {"id": session_id, "user_id": env["user"].id}
    context = {"request_id": "chat-replay-1"}

    first = __import__("asyncio").run(
        ChatOrchestrator._handle_task_request(
            stub, "Create a replayed chat task", {}, session, context))
    second = __import__("asyncio").run(
        ChatOrchestrator._handle_task_request(
            stub, "Create a replayed chat task", {}, session, context))

    assert first["success"] is True
    assert second["success"] is True
    assert first["data"]["task_id"] == second["data"]["task_id"]
    fresh = env["Session"]()
    try:
        rows = fresh.query(UserTask).all()
        assert len(rows) == 1
        assert rows[0].due_date is None
    finally:
        fresh.close()


def test_core_profile_does_not_offer_deferred_tasks_link(
        env, monkeypatch):
    monkeypatch.setenv("ATOM_PRODUCT_PROFILE", "core")
    _patch_chat_db(monkeypatch, env["Session"])
    session_id = "session-core-profile"
    stub = _chat_stub(env, session_id, env["user"].id)
    result = __import__("asyncio").run(
        ChatOrchestrator._handle_task_request(
            stub, "Create a core profile task", {},
            {"id": session_id, "user_id": env["user"].id},
            {"request_id": "core-profile-1"},
        )
    )
    assert result["success"] is True
    assert result["data"]["task"]["title"]
    assert all(
        action.get("url") != "/tasks"
        for action in result.get("suggested_actions", [])
    )


def test_full_profile_keeps_tasks_link(env, monkeypatch):
    monkeypatch.setenv("ATOM_PRODUCT_PROFILE", "full")
    _patch_chat_db(monkeypatch, env["Session"])
    session_id = "session-full-profile"
    stub = _chat_stub(env, session_id, env["user"].id)
    result = __import__("asyncio").run(
        ChatOrchestrator._handle_task_request(
            stub, "Create a full profile task", {},
            {"id": session_id, "user_id": env["user"].id},
            {"request_id": "full-profile-1"},
        )
    )
    assert result["success"] is True
    assert any(
        action.get("url") == "/tasks"
        for action in result.get("suggested_actions", [])
    )


def test_atom_title_naming_provider_without_platform_is_local(env):
    result = __import__("asyncio").run(handle_task_intent(
        "CREATE_TASK",
        {"title": "Prepare Asana training notes"},
        ChatRequest(message="Create local task", user_id=env["user"].id),
        current_user=env["user"],
        db=env["db"],
    ))
    assert result["success"] is True
    fresh = env["Session"]()
    try:
        row = fresh.query(UserTask).one()
        assert row.title == "Prepare Asana training notes"
    finally:
        fresh.close()


def test_atom_explicit_local_platform_with_provider_word_title_is_local(env):
    result = __import__("asyncio").run(handle_task_intent(
        "CREATE_TASK",
        {"title": "Asana training notes", "platform": "local"},
        ChatRequest(message="Create local task", user_id=env["user"].id),
        current_user=env["user"],
        db=env["db"],
    ))
    assert result["success"] is True
    fresh = env["Session"]()
    try:
        assert fresh.query(UserTask).one().title == "Asana training notes"
    finally:
        fresh.close()


def test_atom_explicit_external_platform_refuses_without_local_fallback(env):
    result = __import__("asyncio").run(handle_task_intent(
        "CREATE_TASK",
        {"title": "Provider task", "platform": "asana"},
        ChatRequest(message="Create Asana task", user_id=env["user"].id),
        current_user=env["user"],
        db=env["db"],
    ))
    assert result["success"] is False
    fresh = env["Session"]()
    try:
        assert fresh.query(UserTask).count() == 0
    finally:
        fresh.close()
