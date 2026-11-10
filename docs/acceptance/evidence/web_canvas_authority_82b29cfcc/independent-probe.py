"""Private read-only reproduction probe for canvas sheets/coding authority.

Scope: frozen f5a2413ce checkout. Real FastAPI routes, real auth dependency,
real SQLAlchemy User/Canvas/CanvasAudit rows, real services. The only harness
seam is binding the app's get_db dependency to the explicit scratch SQLite
engine; authority, query, service and write code are not mocked.

No live DB, server, provider, model, install, download or source edit.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPORT_PATH = Path(os.environ["ROOT_CANVAS_REPORT"])
PROBE_PATH = Path(__file__).resolve()
SOURCE_REF = os.environ["ROOT_CANVAS_CANDIDATE"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_scratch_environment() -> Dict[str, str]:
    env = {
        "TESTING": os.environ.get("TESTING", ""),
        "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
        "ATOM_DATA_DIR": os.environ.get("ATOM_DATA_DIR", ""),
    }
    assert env["TESTING"] == "1", f"TESTING must be 1, got {env['TESTING']!r}"
    assert env["DATABASE_URL"].startswith("sqlite:////private/tmp/"), env["DATABASE_URL"]
    assert env["ATOM_DATA_DIR"].startswith("/private/tmp/"), env["ATOM_DATA_DIR"]
    return env


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _snapshot(session, canvas_id: str, canvas_type: str) -> Dict[str, Any]:
    from core.models import CanvasAudit

    rows = (
        session.query(CanvasAudit)
        .filter(
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.canvas_type == canvas_type,
        )
        .order_by(CanvasAudit.created_at.asc(), CanvasAudit.id.asc())
        .all()
    )
    payloads = []
    for row in rows:
        details = row.details_json if isinstance(row.details_json, dict) else {}
        payloads.append(
            {
                "id": row.id,
                "user_id": row.user_id,
                "action_type": row.action_type,
                "canvas_type": row.canvas_type,
                "title": details.get("title"),
                "repo": details.get("repo"),
                "digest": _digest(details),
            }
        )
    latest = payloads[-1] if payloads else None
    return {
        "audit_count": len(payloads),
        "latest": latest,
        "rows": payloads,
    }


def _body_summary(response) -> Dict[str, Any]:
    try:
        body = response.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}
    if "data" in body and isinstance(body["data"], dict):
        body = body["data"]
    summary = {}
    for key in ("title", "repo", "branch", "canvas_id", "success", "message", "cells", "files", "diffs", "charts"):
        if key in body:
            value = body[key]
            if key in ("cells", "files", "diffs", "charts") and isinstance(value, (dict, list)):
                summary[key] = f"<{type(value).__name__} len={len(value)}>"
            else:
                summary[key] = value
    return summary


def _scenario(
    name: str,
    route: str,
    actor: str,
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
    status_code: int,
    body: Dict[str, Any],
    reproduced: bool,
    effect: str,
    assertion: str,
) -> Dict[str, Any]:
    return {
        "name": name,
        "route": route,
        "actor": actor,
        "evidence": "runtime",
        "http_status": status_code,
        "body_summary": body,
        "before": before,
        "after": after,
        "reproduced": reproduced,
        "effect": effect,
        "assertion": assertion,
    }


def _run_original_cases() -> None:
    env = _assert_scratch_environment()

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool

    import core.models  # noqa: F401 - register all model tables
    from api.canvas_coding_routes import router as coding_router
    from api.canvas_sheets_routes import router as sheets_router
    from core.auth import create_access_token
    from core.database import Base, get_db
    from core.models import Canvas, CanvasAudit, Tenant, User, UserStatus, Workspace

    url = env["DATABASE_URL"]
    engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    def _new_app() -> FastAPI:
        app = FastAPI()

        def _get_db():
            db = Session()
            try:
                yield db
            finally:
                db.close()

        app.include_router(sheets_router)
        app.include_router(coding_router)
        app.dependency_overrides[get_db] = _get_db
        return app

    def _client(app: FastAPI) -> TestClient:
        return TestClient(app, base_url="http://testserver")

    def _headers(token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    # ---- genuine scratch rows -------------------------------------------------
    tenant = Tenant(id="default", name="Canvas Repro", subdomain="canvas-repro", edition="personal", is_active=True)
    workspace = Workspace(id="default", name="Default", tenant_id="default", status="active")
    owner = User(
        id="canvas-owner",
        email="canvas-owner@example.invalid",
        hashed_password="scratch-owner-hash",
        first_name="Canvas",
        last_name="Owner",
        role="member",
        status=UserStatus.ACTIVE.value,
        is_active=True,
        tenant_id="default",
        workspace_id="default",
    )
    peer = User(
        id="canvas-peer",
        email="canvas-peer@example.invalid",
        hashed_password="scratch-peer-hash",
        first_name="Canvas",
        last_name="Peer",
        role="member",
        status=UserStatus.ACTIVE.value,
        is_active=True,
        tenant_id="default",
        workspace_id="default",
    )
    inactive = User(
        id="canvas-inactive",
        email="canvas-inactive@example.invalid",
        hashed_password="scratch-inactive-hash",
        first_name="Canvas",
        last_name="Inactive",
        role="member",
        status=UserStatus.ACTIVE.value,
        is_active=True,
        tenant_id="default",
        workspace_id="default",
    )
    session.add_all([tenant, workspace, owner, peer, inactive])
    session.commit()

    sheet_canvas = Canvas(
        id="sheet-A",
        tenant_id="default",
        workspace_id="default",
        created_by=owner.id,
        name="Owner Sheet",
        canvas_type="spreadsheet",
    )
    code_canvas = Canvas(
        id="code-A",
        tenant_id="default",
        workspace_id="default",
        created_by=owner.id,
        name="Owner Code",
        canvas_type="code",
    )
    sheet_details = {
        "canvas_type": "sheets",
        "component_type": "data_grid",
        "title": "Owner Sheet",
        "layout": "sheet",
        "cells": {"A1": {"cell_ref": "A1", "value": "owner", "cell_type": "text"}},
        "formulas": [],
        "charts": [],
        "pivot_tables": [],
    }
    code_details = {
        "canvas_type": "coding",
        "component_type": "repo_browser",
        "repo": "owner/repo",
        "branch": "main",
        "layout": "repo_view",
        "files": [],
        "diffs": [],
        "pull_requests": [],
        "comments": [],
    }
    session.add_all([sheet_canvas, code_canvas])
    session.add_all(
        [
            CanvasAudit(
                id="audit-sheet-A",
                canvas_id="sheet-A",
                tenant_id="default",
                user_id=owner.id,
                action_type="create",
                canvas_type="sheets",
                details_json=sheet_details,
            ),
            CanvasAudit(
                id="audit-code-A",
                canvas_id="code-A",
                tenant_id="default",
                user_id=owner.id,
                action_type="create",
                canvas_type="coding",
                details_json=code_details,
            ),
        ]
    )
    session.commit()

    owner_token = create_access_token(data={"sub": owner.id}, user=owner)
    peer_token = create_access_token(data={"sub": peer.id}, user=peer)
    inactive_token = create_access_token(data={"sub": inactive.id}, user=inactive)

    # Deactivate after token issuance: the token is otherwise valid, so any
    # refusal is current authority, not a malformed token.
    inactive.status = UserStatus.SUSPENDED.value
    inactive.is_active = False
    session.commit()

    app = _new_app()
    client = _client(app)
    scenarios: List[Dict[str, Any]] = []

    # ---- owner positive: sheets read -----------------------------------------
    before = _snapshot(session, "sheet-A", "sheets")
    resp = client.get("/api/canvas/sheets/sheet-A", headers=_headers(owner_token))
    after = _snapshot(session, "sheet-A", "sheets")
    body = _body_summary(resp)
    assert resp.status_code == 200, resp.text
    assert body.get("title") == "Owner Sheet", body
    assert after["audit_count"] == before["audit_count"]
    scenarios.append(_scenario(
        "owner_get_sheet", "GET /api/canvas/sheets/sheet-A", "owner",
        before, after, resp.status_code, body, True, "owner_read_ok",
        "Owner read succeeds and adds no audit row.",
    ))

    # ---- owner positive: coding read -----------------------------------------
    before = _snapshot(session, "code-A", "coding")
    resp = client.get("/api/canvas/coding/code-A", headers=_headers(owner_token))
    after = _snapshot(session, "code-A", "coding")
    body = _body_summary(resp)
    assert resp.status_code == 200, resp.text
    assert body.get("repo") == "owner/repo", body
    assert after["audit_count"] == before["audit_count"]
    scenarios.append(_scenario(
        "owner_get_coding", "GET /api/canvas/coding/code-A", "owner",
        before, after, resp.status_code, body, True, "owner_read_ok",
        "Owner read succeeds and adds no audit row.",
    ))

    # ---- peer read: sheets ----------------------------------------------------
    before = _snapshot(session, "sheet-A", "sheets")
    resp = client.get("/api/canvas/sheets/sheet-A", headers=_headers(peer_token))
    after = _snapshot(session, "sheet-A", "sheets")
    body = _body_summary(resp)
    leaked = resp.status_code == 200 and body.get("title") == "Owner Sheet"
    if resp.status_code == 200:
        assert leaked, body
        effect = "foreign_sheet_read_leak"
    else:
        assert resp.status_code in (403, 404), resp.status_code
        assert not leaked
        effect = "none"
    assert after["audit_count"] == before["audit_count"]
    scenarios.append(_scenario(
        "peer_get_sheet", "GET /api/canvas/sheets/sheet-A", "peer_active_same_tenant",
        before, after, resp.status_code, body, leaked, effect,
        "Peer read either leaks owner content (reproduced) or is refused with no row effect.",
    ))

    # ---- peer read: coding ----------------------------------------------------
    before = _snapshot(session, "code-A", "coding")
    resp = client.get("/api/canvas/coding/code-A", headers=_headers(peer_token))
    after = _snapshot(session, "code-A", "coding")
    body = _body_summary(resp)
    leaked = resp.status_code == 200 and body.get("repo") == "owner/repo"
    if resp.status_code == 200:
        assert leaked, body
        effect = "foreign_coding_read_leak"
    else:
        assert resp.status_code in (403, 404), resp.status_code
        assert not leaked
        effect = "none"
    assert after["audit_count"] == before["audit_count"]
    scenarios.append(_scenario(
        "peer_get_coding", "GET /api/canvas/coding/code-A", "peer_active_same_tenant",
        before, after, resp.status_code, body, leaked, effect,
        "Peer read either leaks owner content (reproduced) or is refused with no row effect.",
    ))

    # ---- peer mutation: sheet cell -------------------------------------------
    before = _snapshot(session, "sheet-A", "sheets")
    resp = client.put(
        "/api/canvas/sheets/sheet-A/cell",
        json={"user_id": peer.id, "cell_ref": "B2", "value": "peer-write", "cell_type": "text"},
        headers=_headers(peer_token),
    )
    after = _snapshot(session, "sheet-A", "sheets")
    body = _body_summary(resp)
    if resp.status_code == 200:
        assert after["audit_count"] == before["audit_count"] + 1, (before, after)
        assert after["latest"]["user_id"] == peer.id, after["latest"]
        assert after["latest"]["action_type"] == "update_cell", after["latest"]
        effect = "foreign_cell_mutation"
        reproduced = True
    else:
        assert resp.status_code in (403, 404), resp.status_code
        assert after["audit_count"] == before["audit_count"], (before, after)
        effect = "none"
        reproduced = False
    scenarios.append(_scenario(
        "peer_put_sheet_cell", "PUT /api/canvas/sheets/sheet-A/cell", "peer_active_same_tenant",
        before, after, resp.status_code, body, reproduced, effect,
        "Peer mutation either appends one peer-authored update_cell row (reproduced) or is refused with zero effect.",
    ))

    # ---- peer mutation: sheet chart ------------------------------------------
    before = _snapshot(session, "sheet-A", "sheets")
    resp = client.post(
        "/api/canvas/sheets/sheet-A/chart",
        json={"user_id": peer.id, "chart_type": "bar", "data_range": "A1:B2", "title": "Peer Chart"},
        headers=_headers(peer_token),
    )
    after = _snapshot(session, "sheet-A", "sheets")
    body = _body_summary(resp)
    if resp.status_code == 200:
        assert after["audit_count"] == before["audit_count"] + 1, (before, after)
        assert after["latest"]["user_id"] == peer.id, after["latest"]
        assert after["latest"]["action_type"] == "add_chart", after["latest"]
        effect = "foreign_chart_mutation"
        reproduced = True
    else:
        assert resp.status_code in (403, 404), resp.status_code
        assert after["audit_count"] == before["audit_count"], (before, after)
        effect = "none"
        reproduced = False
    scenarios.append(_scenario(
        "peer_post_sheet_chart", "POST /api/canvas/sheets/sheet-A/chart", "peer_active_same_tenant",
        before, after, resp.status_code, body, reproduced, effect,
        "Peer chart mutation either appends one peer-authored add_chart row (reproduced) or is refused with zero effect.",
    ))

    # ---- peer mutation: coding file -------------------------------------------
    before = _snapshot(session, "code-A", "coding")
    resp = client.post(
        "/api/canvas/coding/code-A/file",
        json={"user_id": peer.id, "path": "peer.py", "content": "print('peer')", "language": "python"},
        headers=_headers(peer_token),
    )
    after = _snapshot(session, "code-A", "coding")
    body = _body_summary(resp)
    if resp.status_code == 200:
        assert after["audit_count"] == before["audit_count"] + 1, (before, after)
        assert after["latest"]["user_id"] == peer.id, after["latest"]
        effect = "foreign_coding_file_mutation"
        reproduced = True
    else:
        assert resp.status_code in (403, 404), resp.status_code
        assert after["audit_count"] == before["audit_count"], (before, after)
        effect = "none"
        reproduced = False
    scenarios.append(_scenario(
        "peer_post_coding_file", "POST /api/canvas/coding/code-A/file", "peer_active_same_tenant",
        before, after, resp.status_code, body, reproduced, effect,
        "Peer coding-file mutation either appends one peer-authored row (reproduced) or is refused with zero effect.",
    ))

    # ---- peer mutation: coding diff -------------------------------------------
    before = _snapshot(session, "code-A", "coding")
    resp = client.post(
        "/api/canvas/coding/code-A/diff",
        json={
            "user_id": peer.id,
            "file_path": "peer.py",
            "old_content": "print('old')",
            "new_content": "print('peer')",
        },
        headers=_headers(peer_token),
    )
    after = _snapshot(session, "code-A", "coding")
    body = _body_summary(resp)
    if resp.status_code == 200:
        assert after["audit_count"] == before["audit_count"] + 1, (before, after)
        assert after["latest"]["user_id"] == peer.id, after["latest"]
        effect = "foreign_coding_diff_mutation"
        reproduced = True
    else:
        assert resp.status_code in (403, 404), resp.status_code
        assert after["audit_count"] == before["audit_count"], (before, after)
        effect = "none"
        reproduced = False
    scenarios.append(_scenario(
        "peer_post_coding_diff", "POST /api/canvas/coding/code-A/diff", "peer_active_same_tenant",
        before, after, resp.status_code, body, reproduced, effect,
        "Peer coding-diff mutation either appends one peer-authored row (reproduced) or is refused with zero effect.",
    ))

    # ---- create collision: supplied canvas_id (sheets) ------------------------
    before = _snapshot(session, "sheet-A", "sheets")
    resp = client.post(
        "/api/canvas/sheets/create",
        json={"user_id": peer.id, "title": "Peer Hijack", "data": {"A1": "hijack"}, "canvas_id": "sheet-A"},
        headers=_headers(peer_token),
    )
    after = _snapshot(session, "sheet-A", "sheets")
    body = _body_summary(resp)
    if resp.status_code == 200:
        assert after["audit_count"] == before["audit_count"] + 1, (before, after)
        assert after["latest"]["user_id"] == peer.id, after["latest"]
        assert after["latest"]["title"] == "Peer Hijack", after["latest"]
        effect = "foreign_create_canvas_id_collision"
        reproduced = True
    else:
        assert resp.status_code in (403, 404, 409), resp.status_code
        assert after["audit_count"] == before["audit_count"], (before, after)
        effect = "none"
        reproduced = False
    scenarios.append(_scenario(
        "peer_create_sheet_canvas_id_collision",
        "POST /api/canvas/sheets/create (canvas_id=sheet-A)", "peer_active_same_tenant",
        before, after, resp.status_code, body, reproduced, effect,
        "Peer create either appends a same-canvas_id row authored by the peer (reproduced) or is refused with zero effect.",
    ))

    # ---- owner read after collision ------------------------------------------
    resp = client.get("/api/canvas/sheets/sheet-A", headers=_headers(owner_token))
    body = _body_summary(resp)
    after_collision_title = body.get("title")
    scenarios.append({
        "name": "owner_get_sheet_after_collision",
        "route": "GET /api/canvas/sheets/sheet-A",
        "actor": "owner",
        "evidence": "runtime",
        "http_status": resp.status_code,
        "body_summary": body,
        "before": None,
        "after": _snapshot(session, "sheet-A", "sheets"),
        "reproduced": after_collision_title == "Peer Hijack",
        "effect": "owner_read_returns_peer_row" if after_collision_title == "Peer Hijack" else "owner_read_ok",
        "assertion": "Owner read after a successful peer collision returns the peer-authored latest state.",
    })

    # ---- create collision: supplied canvas_id (coding) -----------------------
    before = _snapshot(session, "code-A", "coding")
    resp = client.post(
        "/api/canvas/coding/create",
        json={"user_id": peer.id, "repo": "peer/repo", "branch": "main", "canvas_id": "code-A"},
        headers=_headers(peer_token),
    )
    after = _snapshot(session, "code-A", "coding")
    body = _body_summary(resp)
    if resp.status_code == 200:
        assert after["audit_count"] == before["audit_count"] + 1, (before, after)
        assert after["latest"]["user_id"] == peer.id, after["latest"]
        assert after["latest"]["repo"] == "peer/repo", after["latest"]
        effect = "foreign_create_canvas_id_collision"
        reproduced = True
    else:
        assert resp.status_code in (403, 404, 409), resp.status_code
        assert after["audit_count"] == before["audit_count"], (before, after)
        effect = "none"
        reproduced = False
    scenarios.append(_scenario(
        "peer_create_coding_canvas_id_collision",
        "POST /api/canvas/coding/create (canvas_id=code-A)", "peer_active_same_tenant",
        before, after, resp.status_code, body, reproduced, effect,
        "Peer create either appends a same-canvas_id row authored by the peer (reproduced) or is refused with zero effect.",
    ))

    # ---- body user_id spoof control ------------------------------------------
    before = _snapshot(session, "sheet-A", "sheets")
    resp = client.put(
        "/api/canvas/sheets/sheet-A/cell",
        json={"user_id": peer.id, "cell_ref": "C3", "value": "owner-body-spoof", "cell_type": "text"},
        headers=_headers(owner_token),
    )
    after = _snapshot(session, "sheet-A", "sheets")
    body = _body_summary(resp)
    if resp.status_code == 200:
        assert after["latest"]["user_id"] == owner.id, after["latest"]
        body_user_id_ignored = True
    else:
        assert resp.status_code in (403, 404), resp.status_code
        body_user_id_ignored = False
    scenarios.append(_scenario(
        "owner_body_user_id_spoof_control",
        "PUT /api/canvas/sheets/sheet-A/cell (body user_id=peer)", "owner",
        before, after, resp.status_code, body, body_user_id_ignored, "body_user_id_not_authority",
        "Body user_id is not authority; the row is authored by the authenticated owner when allowed.",
    ))

    # ---- inactive actor zero effect ------------------------------------------
    inactive_cases = []
    before_sheet = _snapshot(session, "sheet-A", "sheets")
    resp = client.get("/api/canvas/sheets/sheet-A", headers=_headers(inactive_token))
    after_sheet = _snapshot(session, "sheet-A", "sheets")
    assert resp.status_code in (401, 403), resp.status_code
    assert after_sheet["audit_count"] == before_sheet["audit_count"]
    inactive_cases.append(_scenario(
        "inactive_get_sheet", "GET /api/canvas/sheets/sheet-A", "inactive",
        before_sheet, after_sheet, resp.status_code, _body_summary(resp), False, "none",
        "Inactive actor is refused by current auth with zero row effect.",
    ))

    before_sheet = _snapshot(session, "sheet-A", "sheets")
    resp = client.put(
        "/api/canvas/sheets/sheet-A/cell",
        json={"user_id": inactive.id, "cell_ref": "Z9", "value": "inactive", "cell_type": "text"},
        headers=_headers(inactive_token),
    )
    after_sheet = _snapshot(session, "sheet-A", "sheets")
    assert resp.status_code in (401, 403), resp.status_code
    assert after_sheet["audit_count"] == before_sheet["audit_count"]
    inactive_cases.append(_scenario(
        "inactive_put_sheet_cell", "PUT /api/canvas/sheets/sheet-A/cell", "inactive",
        before_sheet, after_sheet, resp.status_code, _body_summary(resp), False, "none",
        "Inactive actor is refused by current auth with zero row effect.",
    ))

    before_code = _snapshot(session, "code-A", "coding")
    resp = client.post(
        "/api/canvas/coding/code-A/file",
        json={"user_id": inactive.id, "path": "inactive.py", "content": "print('x')", "language": "python"},
        headers=_headers(inactive_token),
    )
    after_code = _snapshot(session, "code-A", "coding")
    assert resp.status_code in (401, 403), resp.status_code
    assert after_code["audit_count"] == before_code["audit_count"]
    inactive_cases.append(_scenario(
        "inactive_post_coding_file", "POST /api/canvas/coding/code-A/file", "inactive",
        before_code, after_code, resp.status_code, _body_summary(resp), False, "none",
        "Inactive actor is refused by current auth with zero row effect.",
    ))
    scenarios.extend(inactive_cases)

    # ---- fresh engine/session readback (not OS process restart) --------------
    final_sheet = _snapshot(session, "sheet-A", "sheets")
    final_code = _snapshot(session, "code-A", "coding")
    client.close()
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()

    engine2 = create_engine(url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    Session2 = sessionmaker(bind=engine2)
    session2 = Session2()

    app2 = FastAPI()

    def _get_db2():
        db = Session2()
        try:
            yield db
        finally:
            db.close()

    app2.include_router(sheets_router)
    app2.include_router(coding_router)
    app2.dependency_overrides[get_db] = _get_db2
    client2 = TestClient(app2, base_url="http://testserver")

    resp_sheet = client2.get("/api/canvas/sheets/sheet-A", headers=_headers(owner_token))
    resp_code = client2.get("/api/canvas/coding/code-A", headers=_headers(owner_token))
    readback_sheet = _snapshot(session2, "sheet-A", "sheets")
    readback_code = _snapshot(session2, "code-A", "coding")
    assert resp_sheet.status_code == 200
    assert resp_code.status_code == 200
    assert readback_sheet["audit_count"] == final_sheet["audit_count"]
    assert readback_code["audit_count"] == final_code["audit_count"]
    scenarios.append({
        "name": "fresh_engine_readback",
        "route": "GET sheets/coding after engine dispose/recreate",
        "actor": "owner",
        "evidence": "runtime",
        "http_status": {"sheet": resp_sheet.status_code, "coding": resp_code.status_code},
        "body_summary": {"sheet_title": _body_summary(resp_sheet).get("title"), "coding_repo": _body_summary(resp_code).get("repo")},
        "before": {"sheet": final_sheet, "coding": final_code},
        "after": {"sheet": readback_sheet, "coding": readback_code},
        "reproduced": False,
        "effect": "persisted_readback",
        "assertion": "Rows persist across a fresh engine/session; this is not an OS process restart.",
    })
    client2.close()
    session2.close()
    engine2.dispose()

    runtime_reproduced = any(
        item.get("reproduced") is True
        and item.get("name") in {
            "peer_get_sheet", "peer_get_coding",
            "peer_put_sheet_cell", "peer_post_sheet_chart",
            "peer_post_coding_file", "peer_post_coding_diff",
            "peer_create_sheet_canvas_id_collision",
            "peer_create_coding_canvas_id_collision",
            "owner_get_sheet_after_collision",
        }
        for item in scenarios
    )

    report = {
        "schema_version": 1,
        "kind": "canvas_authority_reproduction",
        "generated_at": _now(),
        "source_ref": SOURCE_REF,
        "source_state": "Frozen repaired candidate; real scratch ASGI re-execution of original independent failure cases.",
        "environment": env,
        "scope": "Real public ASGI routes for /api/canvas/sheets and /api/canvas/coding, real get_current_user JWT validation, real SQLAlchemy User/Canvas/CanvasAudit rows, real services. Only the app get_db dependency is bound to the explicit scratch SQLite engine.",
        "runtime_reproduced": runtime_reproduced,
        "summary": {
            "owner_positive_passed": all(
                item["http_status"] == 200 for item in scenarios
                if item["name"] in {"owner_get_sheet", "owner_get_coding"}
            ),
            "inactive_refused": all(
                item["http_status"] in (401, 403)
                for item in scenarios
                if item["name"].startswith("inactive_")
            ),
            "foreign_sheet_read_reproduced": next(
                item["reproduced"] for item in scenarios if item["name"] == "peer_get_sheet"
            ),
            "foreign_coding_read_reproduced": next(
                item["reproduced"] for item in scenarios if item["name"] == "peer_get_coding"
            ),
            "foreign_sheet_mutation_reproduced": any(
                item["reproduced"] for item in scenarios
                if item["name"] in {"peer_put_sheet_cell", "peer_post_sheet_chart"}
            ),
            "foreign_coding_mutation_reproduced": any(
                item["reproduced"] for item in scenarios
                if item["name"] in {"peer_post_coding_file", "peer_post_coding_diff"}
            ),
            "supplied_canvas_id_collision_reproduced": any(
                item["reproduced"] for item in scenarios
                if item["name"] in {"peer_create_sheet_canvas_id_collision", "peer_create_coding_canvas_id_collision"}
            ),
            "body_user_id_is_not_authority": any(
                item["name"] == "owner_body_user_id_spoof_control"
                and item["effect"] == "body_user_id_not_authority"
                for item in scenarios
            ),
        },
        "scenarios": scenarios,
        "source_only_cases": [
            "docs/email R66 ownership helpers and PDF _require_owner are source-inspected, not executed in this probe.",
            "The policy conclusion that single-tenant does not remove per-user canvas authority comes from CanvasAudit.user_id plus the R66/owner-gate pattern, not a separate runtime test.",
            "The exact refusal status a future repair should return (403 vs 404) is not runtime-observed because the frozen source is unfixed.",
            "No runtime test of a coeditor/former-coeditor role transition was performed; only owner, a different active same-tenant user, and an inactive user were exercised.",
        ],
        "limits": [
            "No live DB, server, provider, model, install, download, merge or deploy.",
            "The probe uses an explicit scratch SQLite DB and a dependency override only for get_db; authority, routes, services and writes are real.",
            "Fresh engine/session readback is not an OS process restart.",
            "The probe reports current-source behavior; it does not accept, repair or claim a fixed product state.",
        ],
        "probe_source_path": str(PROBE_PATH),
        "probe_source_sha256": hashlib.sha256(PROBE_PATH.read_bytes()).hexdigest(),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "report": str(REPORT_PATH),
        "runtime_reproduced": runtime_reproduced,
        "scenario_count": len(scenarios),
    }, sort_keys=True))


def test_original_independent_failures_now_refuse_with_owner_preserved():
    _run_original_cases()
    report = json.loads(REPORT_PATH.read_text())
    assert report['runtime_reproduced'] is False, 'Original cross-user defect remains'
    cases = {item['name']: item for item in report['scenarios']}
    peers = [item for item in report['scenarios'] if item.get('actor') == 'peer_active_same_tenant']
    assert len(peers) == 8
    for item in peers:
        assert item['http_status'] in (403, 404, 409), item['name']
        assert item['effect'] == 'none', item['name']
        assert item['before'] == item['after'], item['name']
    assert cases['owner_get_sheet_after_collision']['http_status'] == 200
    assert cases['owner_get_sheet_after_collision']['body_summary']['title'] == 'Owner Sheet'
    assert report['summary']['owner_positive_passed'] is True
    assert report['summary']['inactive_refused'] is True
    assert report['summary']['body_user_id_is_not_authority'] is True
    report['independent_repair_assertions_passed'] = True
    report['original_failure_cases_refused'] = len(peers)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + '\n')
