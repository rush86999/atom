"""Product regression: an authenticated spreadsheet cell save is durable.

Ordinary happy path only: create a sheet, PUT one cell with a value and a
formula, read it back through a fresh authenticated GET, then re-read the
scratch SQLite file through a separate engine. The new durable ``CanvasAudit``
row must match the saved cell exactly.

No live services, no security probing: the router/auth stack and service are
the real product path, and the database is the repo's existing scratch
``test_database`` fixture.
"""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("TESTING", "1")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

from api.canvas_sheets_routes import router as sheets_router
from core.auth import create_access_token
from core.database import get_db
from core.models import CanvasAudit, Tenant, User, UserStatus, Workspace


def _seed_actor(SessionLocal):
    """Create the normal Personal-Edition scope rows and a real bearer token."""
    suffix = uuid.uuid4().hex[:8]
    tenant_id = "default"
    workspace_id = "default"
    user_id = f"sheets-user-{suffix}"

    with SessionLocal() as db:
        if db.query(Tenant).filter(Tenant.id == tenant_id).first() is None:
            db.add(Tenant(
                id=tenant_id,
                name="Default",
                subdomain=f"sheets-{suffix}",
                edition="personal",
                is_active=True,
            ))
        if db.query(Workspace).filter(Workspace.id == workspace_id).first() is None:
            db.add(Workspace(
                id=workspace_id,
                name="Default",
                tenant_id=tenant_id,
            ))
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            email=f"{user_id}@example.invalid",
            hashed_password="x",
            first_name="Sheet",
            last_name="User",
            role="member",
            status=UserStatus.ACTIVE.value,
            is_active=True,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user_id}, user=user)

    return user_id, token


def _authenticated_client(SessionLocal, token):
    """Real sheets router with one fresh DB session per request."""
    app = FastAPI()
    app.include_router(sheets_router)

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def test_authenticated_cell_save_is_durable_and_audited(test_database):
    engine, SessionLocal = test_database
    user_id, token = _seed_actor(SessionLocal)

    client = _authenticated_client(SessionLocal, token)
    created = client.post(
        "/api/canvas/sheets/create",
        json={
            "user_id": "ignored-request-body-id",
            "title": "Q3 Budget",
            "data": {"A1": 10, "A2": 20},
        },
    )
    assert created.status_code == 200, created.text
    created_body = created.json()
    assert created_body["success"] is True
    canvas_id = created_body["canvas_id"]

    with SessionLocal() as db:
        before_ids = {
            audit.id
            for audit in db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id).all()
        }
    assert len(before_ids) == 1

    saved = client.put(
        f"/api/canvas/sheets/{canvas_id}/cell",
        json={
            "user_id": "ignored-request-body-id",
            "cell_ref": "C7",
            "value": 1234.5,
            "cell_type": "number",
            "formula": "=SUM(A1:A5)",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == {
        "success": True,
        "cell_ref": "C7",
        "value": 1234.5,
    }

    # Fresh HTTP GET: a new TestClient and a new DB session per request.
    readback = _authenticated_client(SessionLocal, token).get(
        f"/api/canvas/sheets/{canvas_id}")
    assert readback.status_code == 200, readback.text
    persisted = readback.json()
    assert persisted["title"] == "Q3 Budget"
    assert persisted["cells"]["C7"] == {
        "cell_ref": "C7",
        "value": 1234.5,
        "cell_type": "number",
        "formula": "=SUM(A1:A5)",
    }

    # Fresh durable readback: separate engine against the same scratch file.
    fresh_engine = create_engine(
        f"sqlite:///{engine.url.database}",
        connect_args={"check_same_thread": False},
    )
    try:
        FreshSession = sessionmaker(bind=fresh_engine)
        with FreshSession() as db:
            rows = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id
            ).order_by(
                desc(CanvasAudit.created_at), desc(CanvasAudit.id)
            ).all()
    finally:
        fresh_engine.dispose()

    assert len(rows) == len(before_ids) + 1
    updates = [row for row in rows if row.action_type == "update_cell"]
    assert len(updates) == 1
    record = updates[0]
    assert record.id not in before_ids
    assert record.canvas_id == canvas_id
    assert record.user_id == user_id
    assert record.tenant_id == "default"
    assert record.canvas_type == "sheets"
    assert record.details_json["component_type"] == "data_grid"
    assert record.details_json["title"] == "Q3 Budget"
    assert record.details_json["cells"]["C7"] == persisted["cells"]["C7"]
    assert record.details_json["cells"]["C7"] == {
        "cell_ref": "C7",
        "value": 1234.5,
        "cell_type": "number",
        "formula": "=SUM(A1:A5)",
    }
