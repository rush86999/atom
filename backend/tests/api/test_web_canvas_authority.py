"""Failure-first authority controls for the sheets and coding canvas families.

Real SQLAlchemy User/CanvasAudit rows, real public ASGI routes and real
services. No authority/query/service/write mocks in the decisive paths.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

import core.canvas_authority as canvas_authority

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import core.models  # noqa: F401 - register tables
from api.canvas_coding_routes import router as coding_router
from api.canvas_sheets_routes import router as sheets_router
from core.auth import create_access_token
from core.canvas_coding_service import CodingCanvasService
from core.canvas_sheets_service import SpreadsheetCanvasService
from core.database import Base, get_db
from core.models import Canvas, CanvasAudit, Tenant, User, UserStatus, Workspace


def _user(db, user_id: str, *, tenant_id="default", workspace_id="default", status=UserStatus.ACTIVE.value, active=True):
    row = User(
        id=user_id,
        email=f"{user_id}@example.invalid",
        hashed_password=f"scratch-{user_id}",
        first_name="Canvas",
        last_name=user_id,
        role="member",
        status=status,
        is_active=active,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    db.add(row)
    return row


def _tenant(db, tenant_id: str):
    row = Tenant(
        id=tenant_id,
        name=tenant_id,
        subdomain=tenant_id,
        edition="personal",
        is_active=True,
    )
    db.add(row)
    return row


def _workspace(db, workspace_id: str, tenant_id: str):
    row = Workspace(
        id=workspace_id,
        name=workspace_id,
        tenant_id=tenant_id,
        status="active",
    )
    db.add(row)
    return row


def _audit(db, canvas_id: str, user_id: str, canvas_type: str, details, action="create", tenant_id="default"):
    row = CanvasAudit(
        id=f"audit-{canvas_id}-{user_id}-{action}-{datetime.now(timezone.utc).timestamp()}",
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        user_id=user_id,
        action_type=action,
        canvas_type=canvas_type,
        details_json=details,
    )
    db.add(row)
    return row


def _snapshot(db, canvas_id: str, canvas_type: str):
    rows = (
        db.query(CanvasAudit)
        .filter(
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.canvas_type == canvas_type,
        )
        .order_by(CanvasAudit.created_at.asc(), CanvasAudit.id.asc())
        .all()
    )
    return {
        "count": len(rows),
        "latest_user": rows[-1].user_id if rows else None,
        "latest_action": rows[-1].action_type if rows else None,
        "latest_tenant": rows[-1].tenant_id if rows else None,
        "latest_details": (rows[-1].details_json or {}) if rows else {},
    }


@pytest.fixture()
def env(tmp_path):
    assert os.environ.get("TESTING") == "1"
    db_path = tmp_path / "canvas_authority.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    _tenant(db, "default")
    _tenant(db, "tenant-other")
    _workspace(db, "default", "default")
    _workspace(db, "ws-other", "tenant-other")
    owner = _user(db, "owner")
    peer = _user(db, "peer")
    coeditor = _user(db, "coeditor")
    inactive = _user(db, "inactive")
    foreign = _user(db, "foreign", tenant_id="tenant-other", workspace_id="ws-other")
    no_tenant = _user(db, "no-tenant", tenant_id=None, workspace_id="default")
    db.commit()

    tokens = {
        "owner": create_access_token(data={"sub": owner.id}, user=owner),
        "peer": create_access_token(data={"sub": peer.id}, user=peer),
        "coeditor": create_access_token(data={"sub": coeditor.id}, user=coeditor),
        "inactive": create_access_token(data={"sub": inactive.id}, user=inactive),
        "foreign": create_access_token(data={"sub": foreign.id}, user=foreign),
        "no_tenant": create_access_token(data={"sub": no_tenant.id}, user=no_tenant),
    }
    inactive.status = UserStatus.SUSPENDED.value
    inactive.is_active = False
    db.commit()

    app = FastAPI()

    def _get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.include_router(sheets_router)
    app.include_router(coding_router)
    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app, base_url="http://testserver")

    def headers(name: str):
        return {"Authorization": f"Bearer {tokens[name]}"}

    yield SimpleNamespace(
        db=db,
        Session=Session,
        engine=engine,
        app=app,
        client=client,
        headers=headers,
        users={"owner": owner, "peer": peer, "coeditor": coeditor, "inactive": inactive, "foreign": foreign, "no_tenant": no_tenant},
        db_path=str(db_path),
    )

    client.close()
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _create_sheet(client, headers, *, canvas_id=None, title="Owner Sheet", user_id=None):
    body = {"user_id": user_id or "ignored", "title": title, "data": {"A1": "owner"}}
    if canvas_id is not None:
        body["canvas_id"] = canvas_id
    return client.post("/api/canvas/sheets/create", json=body, headers=headers)


def _create_coding(client, headers, *, canvas_id=None, repo="owner/repo", user_id=None):
    body = {"user_id": user_id or "ignored", "repo": repo, "branch": "main"}
    if canvas_id is not None:
        body["canvas_id"] = canvas_id
    return client.post("/api/canvas/coding/create", json=body, headers=headers)


def _sheet_id(response):
    assert response.status_code == 200, response.text
    return response.json()["canvas_id"]


def _coding_id(response):
    assert response.status_code == 200, response.text
    body = response.json()
    return body.get("canvas_id") or body.get("data", {}).get("canvas_id")


def test_owner_sheets_and_coding_positive_twins(env):
    client = env.client
    owner = env.headers("owner")

    sheet = _create_sheet(client, owner, title="Owner Sheet")
    sheet_id = _sheet_id(sheet)
    assert sheet.json()["success"] is True
    assert client.get(f"/api/canvas/sheets/{sheet_id}", headers=owner).status_code == 200
    cell = client.put(
        f"/api/canvas/sheets/{sheet_id}/cell",
        json={"user_id": "ignored", "cell_ref": "B2", "value": "owner-write", "cell_type": "text"},
        headers=owner,
    )
    assert cell.status_code == 200, cell.text
    chart = client.post(
        f"/api/canvas/sheets/{sheet_id}/chart",
        json={"user_id": "ignored", "chart_type": "bar", "data_range": "A1:B2", "title": "Owner Chart"},
        headers=owner,
    )
    assert chart.status_code == 200, chart.text
    snap = _snapshot(env.db, sheet_id, "sheets")
    assert snap["count"] == 3
    assert snap["latest_user"] == env.users["owner"].id
    assert snap["latest_tenant"] == "default"

    coding = _create_coding(client, owner, repo="owner/repo")
    code_id = _coding_id(coding)
    assert client.get(f"/api/canvas/coding/{code_id}", headers=owner).status_code == 200
    file_resp = client.post(
        f"/api/canvas/coding/{code_id}/file",
        json={"user_id": "ignored", "path": "main.py", "content": "print('owner')", "language": "python"},
        headers=owner,
    )
    assert file_resp.status_code == 200, file_resp.text
    diff_resp = client.post(
        f"/api/canvas/coding/{code_id}/diff",
        json={"user_id": "ignored", "file_path": "main.py", "old_content": "old", "new_content": "new"},
        headers=owner,
    )
    assert diff_resp.status_code == 200, diff_resp.text
    code_snap = _snapshot(env.db, code_id, "coding")
    assert code_snap["count"] == 3
    assert code_snap["latest_user"] == env.users["owner"].id


def test_same_tenant_peer_sheets_refused_zero_effect(env):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    before = _snapshot(env.db, sheet_id, "sheets")
    peer = env.headers("peer")

    read = env.client.get(f"/api/canvas/sheets/{sheet_id}", headers=peer)
    assert read.status_code in (403, 404), read.text
    cell = env.client.put(
        f"/api/canvas/sheets/{sheet_id}/cell",
        json={"user_id": env.users["peer"].id, "cell_ref": "Z9", "value": "peer", "cell_type": "text"},
        headers=peer,
    )
    assert cell.status_code in (403, 404), cell.text
    chart = env.client.post(
        f"/api/canvas/sheets/{sheet_id}/chart",
        json={"user_id": env.users["peer"].id, "chart_type": "bar", "data_range": "A1:B2"},
        headers=peer,
    )
    assert chart.status_code in (403, 404), chart.text
    after = _snapshot(env.db, sheet_id, "sheets")
    assert after == before, after


def test_same_tenant_peer_coding_refused_zero_effect(env):
    code_id = _coding_id(_create_coding(env.client, env.headers("owner")))
    before = _snapshot(env.db, code_id, "coding")
    peer = env.headers("peer")

    read = env.client.get(f"/api/canvas/coding/{code_id}", headers=peer)
    assert read.status_code in (403, 404), read.text
    file_resp = env.client.post(
        f"/api/canvas/coding/{code_id}/file",
        json={"user_id": env.users["peer"].id, "path": "peer.py", "content": "print('peer')", "language": "python"},
        headers=peer,
    )
    assert file_resp.status_code in (403, 404), file_resp.text
    diff_resp = env.client.post(
        f"/api/canvas/coding/{code_id}/diff",
        json={"user_id": env.users["peer"].id, "file_path": "peer.py", "old_content": "old", "new_content": "new"},
        headers=peer,
    )
    assert diff_resp.status_code in (403, 404), diff_resp.text
    after = _snapshot(env.db, code_id, "coding")
    assert after == before, after


def test_inactive_actor_refused_zero_effect(env):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    code_id = _coding_id(_create_coding(env.client, env.headers("owner")))
    before_sheet = _snapshot(env.db, sheet_id, "sheets")
    before_code = _snapshot(env.db, code_id, "coding")
    inactive = env.headers("inactive")

    assert env.client.get(f"/api/canvas/sheets/{sheet_id}", headers=inactive).status_code in (401, 403)
    assert env.client.put(
        f"/api/canvas/sheets/{sheet_id}/cell",
        json={"user_id": env.users["inactive"].id, "cell_ref": "Z9", "value": "x"},
        headers=inactive,
    ).status_code in (401, 403)
    assert env.client.post(
        f"/api/canvas/coding/{code_id}/file",
        json={"user_id": env.users["inactive"].id, "path": "x.py", "content": "x"},
        headers=inactive,
    ).status_code in (401, 403)
    assert _snapshot(env.db, sheet_id, "sheets") == before_sheet
    assert _snapshot(env.db, code_id, "coding") == before_code


def test_same_scope_coeditor_still_allowed(env):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    _audit(
        env.db, sheet_id, env.users["coeditor"].id, "sheets",
        {"canvas_type": "sheets", "component_type": "data_grid", "title": "Owner Sheet", "cells": {}, "charts": []},
        action="update",
    )
    env.db.commit()
    coeditor = env.headers("coeditor")
    assert env.client.get(f"/api/canvas/sheets/{sheet_id}", headers=coeditor).status_code == 200
    updated = env.client.put(
        f"/api/canvas/sheets/{sheet_id}/cell",
        json={"user_id": "ignored", "cell_ref": "C3", "value": "coeditor"},
        headers=coeditor,
    )
    assert updated.status_code == 200, updated.text
    snap = _snapshot(env.db, sheet_id, "sheets")
    assert snap["latest_user"] == env.users["coeditor"].id

    code_id = _coding_id(_create_coding(env.client, env.headers("owner")))
    _audit(
        env.db, code_id, env.users["coeditor"].id, "coding",
        {"canvas_type": "coding", "component_type": "repo_browser", "repo": "owner/repo", "files": [], "diffs": []},
        action="update",
    )
    env.db.commit()
    assert env.client.get(f"/api/canvas/coding/{code_id}", headers=coeditor).status_code == 200
    added = env.client.post(
        f"/api/canvas/coding/{code_id}/file",
        json={"user_id": "ignored", "path": "coeditor.py", "content": "coeditor"},
        headers=coeditor,
    )
    assert added.status_code == 200, added.text


def test_foreign_scope_coeditor_refused_zero_effect(env):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    _audit(
        env.db, sheet_id, env.users["foreign"].id, "sheets",
        {"canvas_type": "sheets", "component_type": "data_grid", "title": "Owner Sheet", "cells": {}, "charts": []},
        action="update",
        tenant_id="default",
    )
    env.db.commit()
    before = _snapshot(env.db, sheet_id, "sheets")
    foreign = env.headers("foreign")
    assert env.client.get(f"/api/canvas/sheets/{sheet_id}", headers=foreign).status_code in (403, 404)
    response = env.client.put(
        f"/api/canvas/sheets/{sheet_id}/cell",
        json={"user_id": env.users["foreign"].id, "cell_ref": "Z9", "value": "foreign"},
        headers=foreign,
    )
    assert response.status_code in (403, 404), response.text
    assert _snapshot(env.db, sheet_id, "sheets") == before


def test_create_collision_same_family_cross_family_and_same_owner(env):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    owner = env.headers("owner")
    peer = env.headers("peer")

    before = _snapshot(env.db, sheet_id, "sheets")
    for headers in (peer, owner):
        response = _create_sheet(env.client, headers, canvas_id=sheet_id, title="Hijack")
        assert response.status_code == 409, response.text
    cross = _create_coding(env.client, owner, canvas_id=sheet_id, repo="cross/repo")
    assert cross.status_code == 409, cross.text
    assert _snapshot(env.db, sheet_id, "sheets") == before

    code_id = _coding_id(_create_coding(env.client, env.headers("owner")))
    before_code = _snapshot(env.db, code_id, "coding")
    assert _create_coding(env.client, peer, canvas_id=code_id).status_code == 409
    assert _create_sheet(env.client, owner, canvas_id=code_id).status_code == 409
    assert _snapshot(env.db, code_id, "coding") == before_code

    fresh = _create_sheet(env.client, owner, canvas_id="fresh-explicit-id", title="Fresh")
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["canvas_id"] == "fresh-explicit-id"
    assert _create_sheet(env.client, owner, canvas_id="fresh-explicit-id", title="Again").status_code == 409


def test_body_user_id_is_not_authority(env):
    created = _create_sheet(
        env.client,
        env.headers("owner"),
        title="Body Spoof",
        user_id=env.users["peer"].id,
    )
    sheet_id = _sheet_id(created)
    snap = _snapshot(env.db, sheet_id, "sheets")
    assert snap["latest_user"] == env.users["owner"].id

    updated = env.client.put(
        f"/api/canvas/sheets/{sheet_id}/cell",
        json={"user_id": env.users["peer"].id, "cell_ref": "D4", "value": "owner-write"},
        headers=env.headers("owner"),
    )
    assert updated.status_code == 200, updated.text
    assert _snapshot(env.db, sheet_id, "sheets")["latest_user"] == env.users["owner"].id


def test_direct_service_calls_cannot_bypass_route_authority(env):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    code_id = _coding_id(_create_coding(env.client, env.headers("owner")))
    before_sheet = _snapshot(env.db, sheet_id, "sheets")
    before_code = _snapshot(env.db, code_id, "coding")

    sheets = SpreadsheetCanvasService(env.db)
    cell = sheets.update_cell(sheet_id, env.users["peer"].id, "Z9", "peer")
    assert cell.get("success") is False
    assert cell.get("http_status") in (403, 404)
    chart = sheets.add_chart(sheet_id, env.users["peer"].id, "bar", "A1:B2")
    assert chart.get("success") is False
    assert chart.get("http_status") in (403, 404)

    coding = CodingCanvasService(env.db)
    file_res = coding.add_file(code_id, env.users["peer"].id, "peer.py", "print('peer')")
    assert file_res.get("success") is False
    assert file_res.get("http_status") in (403, 404)
    diff_res = coding.add_diff(code_id, env.users["peer"].id, "peer.py", "old", "new")
    assert diff_res.get("success") is False
    assert diff_res.get("http_status") in (403, 404)

    assert _snapshot(env.db, sheet_id, "sheets") == before_sheet
    assert _snapshot(env.db, code_id, "coding") == before_code


def test_missing_actor_refused_but_null_default_is_valid_personal(env):
    before = _snapshot(env.db, "missing-canvas", "sheets")
    sheets = SpreadsheetCanvasService(env.db)
    missing = sheets.create_spreadsheet_canvas("does-not-exist", "Missing", {})
    assert missing.get("success") is False
    assert missing.get("http_status") == 403
    # Bootstrap NULL tenant is the documented Personal fallback; the default
    # Tenant row exists, so this is a valid actor, not "no authority".
    no_tenant = sheets.create_spreadsheet_canvas(
        env.users["no_tenant"].id, "No Tenant", {})
    assert no_tenant.get("success") is True
    route = _create_sheet(env.client, env.headers("no_tenant"), title="No Tenant")
    assert route.status_code == 200, route.text
    snap = _snapshot(env.db, no_tenant["canvas_id"], "sheets")
    assert snap["latest_tenant"] == "default"
    assert _snapshot(env.db, "missing-canvas", "sheets") == before


def test_stale_actor_deactivation_before_claim_zero_effect(env):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    before = _snapshot(env.db, sheet_id, "sheets")
    fired = {"done": False}

    def _deactivate(conn, cursor, statement, parameters, context, executemany):
        lowered = statement.lower().lstrip()
        if fired["done"] or not lowered.startswith("update users"):
            return
        fired["done"] = True
        peer = env.Session()
        try:
            row = peer.query(User).filter(User.id == env.users["owner"].id).one()
            row.status = UserStatus.SUSPENDED.value
            row.is_active = False
            peer.commit()
        finally:
            peer.close()

    event.listen(env.engine, "before_cursor_execute", _deactivate)
    try:
        response = env.client.put(
            f"/api/canvas/sheets/{sheet_id}/cell",
            json={"user_id": env.users["owner"].id, "cell_ref": "Z9", "value": "stale"},
            headers=env.headers("owner"),
        )
    finally:
        event.remove(env.engine, "before_cursor_execute", _deactivate)

    assert fired["done"] is True
    assert response.status_code == 409, response.text
    assert _snapshot(env.db, sheet_id, "sheets") == before
    env.db.expire_all()
    row = env.db.query(User).filter(User.id == env.users["owner"].id).one()
    assert row.status == UserStatus.SUSPENDED.value
    assert row.is_active is False


def test_target_canvas_scope_move_refused_zero_effect(env):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    canvas = env.db.query(Canvas).filter(Canvas.id == sheet_id).one()
    canvas.tenant_id = "tenant-other"
    env.db.commit()
    before = _snapshot(env.db, sheet_id, "sheets")
    response = env.client.put(
        f"/api/canvas/sheets/{sheet_id}/cell",
        json={"user_id": env.users["owner"].id, "cell_ref": "Z9", "value": "moved"},
        headers=env.headers("owner"),
    )
    assert response.status_code in (403, 404), response.text
    assert _snapshot(env.db, sheet_id, "sheets") == before


def test_legacy_audit_only_target_scope_move_refused_zero_effect(env):
    details = {
        "canvas_type": "sheets",
        "component_type": "data_grid",
        "title": "Legacy",
        "cells": {},
        "charts": [],
    }
    _audit(env.db, "legacy-audit-only", env.users["owner"].id, "sheets", details, action="create", tenant_id="default")
    _audit(env.db, "legacy-audit-only", env.users["owner"].id, "sheets", details, action="update", tenant_id="tenant-other")
    env.db.commit()
    before = _snapshot(env.db, "legacy-audit-only", "sheets")
    response = env.client.put(
        "/api/canvas/sheets/legacy-audit-only/cell",
        json={"user_id": env.users["owner"].id, "cell_ref": "Z9", "value": "moved"},
        headers=env.headers("owner"),
    )
    assert response.status_code in (403, 404), response.text
    assert _snapshot(env.db, "legacy-audit-only", "sheets") == before


def test_canvas_scope_move_between_check_and_cas_refused_zero_effect(env, monkeypatch):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    before = _snapshot(env.db, sheet_id, "sheets")
    real_scope_check = canvas_authority.canvas_lifecycle_scope_error

    def _move_after_check(db, canvas_id, user_id, tenant_id, workspace_id, lock=False):
        result = real_scope_check(db, canvas_id, user_id, tenant_id, workspace_id, lock=lock)
        peer = env.Session()
        try:
            row = peer.query(Canvas).filter(Canvas.id == sheet_id).one()
            row.tenant_id = "tenant-other"
            peer.commit()
        finally:
            peer.close()
        return result

    monkeypatch.setattr(canvas_authority, "canvas_lifecycle_scope_error", _move_after_check)
    response = env.client.put(
        f"/api/canvas/sheets/{sheet_id}/cell",
        json={"user_id": env.users["owner"].id, "cell_ref": "Z9", "value": "moved"},
        headers=env.headers("owner"),
    )
    assert response.status_code == 409, response.text
    assert _snapshot(env.db, sheet_id, "sheets") == before


def test_audit_only_append_between_check_and_cas_refused_zero_effect(env, monkeypatch):
    details = {
        "canvas_type": "sheets",
        "component_type": "data_grid",
        "title": "Legacy",
        "cells": {},
        "charts": [],
    }
    _audit(env.db, "legacy-race", env.users["owner"].id, "sheets", details, action="create", tenant_id="default")
    env.db.commit()
    before = _snapshot(env.db, "legacy-race", "sheets")
    real_scope_check = canvas_authority.canvas_lifecycle_scope_error

    def _append_after_check(db, canvas_id, user_id, tenant_id, workspace_id, lock=False):
        result = real_scope_check(db, canvas_id, user_id, tenant_id, workspace_id, lock=lock)
        peer = env.Session()
        try:
            _audit(peer, "legacy-race", env.users["coeditor"].id, "sheets", details, action="update", tenant_id="default")
            peer.commit()
        finally:
            peer.close()
        return result

    monkeypatch.setattr(canvas_authority, "canvas_lifecycle_scope_error", _append_after_check)
    response = env.client.put(
        "/api/canvas/sheets/legacy-race/cell",
        json={"user_id": env.users["owner"].id, "cell_ref": "Z9", "value": "race"},
        headers=env.headers("owner"),
    )
    assert response.status_code == 409, response.text
    after = _snapshot(env.db, "legacy-race", "sheets")
    assert after["count"] == before["count"] + 1  # only the injected peer append
    assert after["latest_user"] == env.users["coeditor"].id


def test_concurrent_same_id_create_has_one_winner(env):
    results = []
    owner_id = str(env.users["owner"].id)

    def _create():
        engine = create_engine(
            f"sqlite:///{env.db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=NullPool,
        )
        session = sessionmaker(bind=engine)()
        try:
            service = SpreadsheetCanvasService(session)
            result = service.create_spreadsheet_canvas(
                owner_id,
                "Race Sheet",
                {"A1": "race"},
                canvas_id="race-same-id",
            )
            return result
        finally:
            session.close()
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_create) for _ in range(2)]
        results = [future.result() for future in futures]

    successes = [r for r in results if r.get("success") is True]
    conflicts = [r for r in results if r.get("http_status") == 409]
    assert len(successes) == 1, results
    assert len(conflicts) == 1, results
    assert env.db.query(Canvas).filter(Canvas.id == "race-same-id").count() == 1
    assert _snapshot(env.db, "race-same-id", "sheets")["count"] == 1


_CHILD_READBACK = """
import json, sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
count = conn.execute(
    "select count(*) from canvas_audit where canvas_id = ?", (sys.argv[2],)
).fetchone()[0]
latest = conn.execute(
    "select user_id, action_type from canvas_audit where canvas_id = ? "
    "order by created_at desc, id desc limit 1", (sys.argv[2],)
).fetchone()
print(json.dumps({"count": count, "latest_user": latest[0], "latest_action": latest[1]}))
"""


def test_fresh_session_and_child_process_readback(env):
    sheet_id = _sheet_id(_create_sheet(env.client, env.headers("owner")))
    env.client.put(
        f"/api/canvas/sheets/{sheet_id}/cell",
        json={"user_id": env.users["owner"].id, "cell_ref": "B2", "value": "persisted"},
        headers=env.headers("owner"),
    )
    final = _snapshot(env.db, sheet_id, "sheets")
    env.client.close()
    env.app.dependency_overrides.clear()
    env.db.close()
    env.engine.dispose()

    engine2 = create_engine(
        f"sqlite:///{env.db_path}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Session2 = sessionmaker(bind=engine2)
    session2 = Session2()
    app2 = FastAPI()

    def _get_db2():
        session = Session2()
        try:
            yield session
        finally:
            session.close()

    app2.include_router(sheets_router)
    app2.dependency_overrides[get_db] = _get_db2
    client2 = TestClient(app2, base_url="http://testserver")
    readback = client2.get(f"/api/canvas/sheets/{sheet_id}", headers=env.headers("owner"))
    assert readback.status_code == 200, readback.text
    assert _snapshot(session2, sheet_id, "sheets")["count"] == final["count"]
    client2.close()
    session2.close()
    engine2.dispose()

    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_READBACK, env.db_path, sheet_id],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout.strip().splitlines()[-1])
    assert summary["count"] == final["count"]
    assert summary["latest_user"] == env.users["owner"].id
    assert summary["latest_action"] == "update_cell"
