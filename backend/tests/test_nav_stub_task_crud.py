"""Tasks sidebar CRUD must persist (2026-10-27 whole-app pass).

The Tasks page POSTed/PUT/DELETEd /api/v1/tasks against a GET-only nav stub:
create returned 405 while the UI optimistically showed "Task created", and
the row disappeared on reload. These tests lock the durable UserTask CRUD.
"""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auth import get_current_user as auth_get_current_user
from core.database import Base, get_db
from core.models import Tenant, User


@pytest.fixture()
def task_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(Tenant(id="default", name="Default Tenant", subdomain="default",
                  plan_type="free", edition="personal"))
    db.add(User(
        id="member-1", email="member@example.com", hashed_password="x",
        first_name="M", last_name="User", role="member", status="active",
        is_active=True, tenant_id="default",
    ))
    db.commit()
    user = db.query(User).filter(User.id == "member-1").first()

    from api.nav_stub_routes import router as nav_router

    app = FastAPI()
    app.include_router(nav_router)
    app.dependency_overrides[auth_get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app, raise_server_exceptions=False)
    yield client, db
    db.close()


def test_task_crud_round_trip(task_client):
    client, db = task_client

    created = client.post("/api/v1/tasks", json={
        "title": "Whole-app durable task",
        "description": "created by the browser contract",
        "dueDate": "2026-11-01T00:00:00",
        "priority": "high",
        "status": "todo",
        "tags": ["whole-app"],
        "estimatedHours": 2,
    })
    assert created.status_code == 200, created.text
    task = created.json()["task"]
    assert task["title"] == "Whole-app durable task"
    assert task["dueDate"].startswith("2026-11-01")

    listed = client.get("/api/v1/tasks")
    assert listed.status_code == 200, listed.text
    assert [t["id"] for t in listed.json()["tasks"]] == [task["id"]]

    updated = client.put(f"/api/v1/tasks/{task['id']}", json={
        "status": "completed", "priority": "low",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["task"]["status"] == "completed"
    assert updated.json()["task"]["priority"] == "low"

    # A new request/session sees the same row — the durability claim.
    db.expire_all()
    again = client.get("/api/v1/tasks").json()["tasks"]
    assert again[0]["status"] == "completed"

    deleted = client.delete(f"/api/v1/tasks/{task['id']}")
    assert deleted.status_code == 200, deleted.text
    assert client.get("/api/v1/tasks").json()["tasks"] == []


def test_task_create_requires_title(task_client):
    client, _ = task_client
    resp = client.post("/api/v1/tasks", json={"description": "no title"})
    assert resp.status_code == 422, resp.text


def test_cannot_touch_another_users_task(task_client):
    client, db = task_client
    db.add(User(
        id="other-1", email="other@example.com", hashed_password="x",
        first_name="O", last_name="User", role="member", status="active",
        is_active=True, tenant_id="default",
    ))
    db.commit()
    created = client.post("/api/v1/tasks", json={
        "title": "mine", "dueDate": datetime.utcnow().isoformat(),
    }).json()["task"]
    # The override still resolves member-1; another user's id must 404, not
    # leak the row. Simulate by filtering on ownership in the helper.
    from api.nav_stub_routes import _owned_task
    assert _owned_task(db, created["id"], "other-1") is None
