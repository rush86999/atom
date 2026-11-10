"""Public-boundary controls for the shared email draft writer.

Real canonical routes, real JWT/get_current_user, scratch SQLite only.
No provider/send/model/browser/live DB.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

from api.canvas_email_routes import router as email_router
from api.canvas_routes import router as canvas_router
from core.auth import create_access_token, get_current_user
from core.database import Base, get_db
from core.models import Canvas, CanvasAudit, Tenant, User, Workspace


class World:
    def __init__(self, tmp_path):
        self.engine = create_engine(
            f"sqlite:///{tmp_path}/email-shared.db",
            connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        suffix = uuid.uuid4().hex[:8]
        self.tenant = f"tenant-{suffix}"
        self.ws = f"ws-{suffix}"
        self.foreign_tenant = f"tenant-f-{suffix}"
        self.foreign_ws = f"ws-f-{suffix}"
        self.owner = f"owner-{suffix}"
        self.peer = f"peer-{suffix}"
        with self.Session() as db:
            db.add(Tenant(id=self.tenant, name="T", subdomain=f"t-{suffix}",
                          edition="personal", is_active=True))
            db.add(Tenant(id=self.foreign_tenant, name="F",
                          subdomain=f"f-{suffix}", edition="personal",
                          is_active=True))
            db.add(Workspace(id=self.ws, name="W", tenant_id=self.tenant))
            db.add(Workspace(id=self.foreign_ws, name="FW",
                             tenant_id=self.foreign_tenant))
            for uid in (self.owner, self.peer):
                db.add(User(
                    id=uid, tenant_id=self.tenant, workspace_id=self.ws,
                    email=f"{uid}@example.invalid", hashed_password="x",
                    first_name="U", last_name="Ser", role="member",
                    status="active", is_active=True))
            db.commit()

    def token(self, uid):
        with self.Session() as db:
            user = db.query(User).filter(User.id == uid).one()
            return create_access_token({"sub": user.id}, user=user)

    def create_canvas(self, *, owner=None, tenant=None, workspace=None,
                      content=None, thread_id=None, attachments=None,
                      draft=None):
        cid = f"canvas-{uuid.uuid4().hex[:10]}"
        aid = f"audit-{uuid.uuid4().hex[:10]}"
        owner = owner or self.owner
        tenant = tenant or self.tenant
        workspace = workspace or self.ws
        content = content if content is not None else {
            "to": "", "cc": "", "subject": "Draft", "body": ""}
        details = {
            "canvas_type": "email", "component_type": "compose_form",
            "subject": "Draft", "layout": "conversation",
            "thread_id": thread_id or str(uuid.uuid4()),
            "draft": draft if draft is not None else {
                "draft_id": str(uuid.uuid4()), "to_emails": [],
                "cc_emails": [], "subject": "Draft", "body": "",
                "attachments": list(attachments or []),
            },
            "messages": [], "attachments": list(attachments or []),
        }
        with self.Session() as db:
            db.add(Canvas(
                id=cid, tenant_id=tenant, workspace_id=workspace,
                created_by=owner, name="Draft", canvas_type="email",
                content=dict(content), status="active"))
            db.add(CanvasAudit(
                id=aid, canvas_id=cid, tenant_id=tenant, user_id=owner,
                canvas_type="email", action_type="create",
                details_json=details))
            db.commit()
        return cid, aid

    def latest_audit_id(self, canvas_id):
        with self.Session() as db:
            row = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "email",
            ).order_by(desc(CanvasAudit.created_at)).first()
            return row.id if row else None

    def audit_count(self, canvas_id):
        with self.Session() as db:
            return db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id).count()

    def fresh(self, canvas_id):
        with self.Session() as db:
            canvas = db.query(Canvas).filter(Canvas.id == canvas_id).one()
            audit = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "email",
            ).order_by(desc(CanvasAudit.created_at)).first()
            return {
                "canvas_tenant": canvas.tenant_id,
                "canvas_workspace": canvas.workspace_id,
                "content": dict(canvas.content or {}),
                "audit_tenant": audit.tenant_id if audit else None,
                "audit_action": audit.action_type if audit else None,
                "details": dict(audit.details_json or {}) if audit else {},
            }


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_DEPLOYMENT_AUDIENCE", "development")
    w = World(tmp_path)

    @contextmanager
    def _session_cm():
        db = w.Session()
        try:
            yield db
        finally:
            db.close()

    import core.database as database
    monkeypatch.setattr(database, "get_db_session", _session_cm)
    return w


def _client(world, user_id=None):
    app = FastAPI()
    app.include_router(email_router)
    app.include_router(canvas_router)
    actor = user_id or world.owner

    def override_db():
        db = world.Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {world.token(actor)}"
    return client


def _save(client, canvas_id, *, prior, body="Draft body",
          subject="Draft Subject", to=None, cc=None,
          operation_id=None):
    return client.post(
        f"/api/canvas/email/{canvas_id}/draft",
        json={
            "user_id": "ignored",
            "to_emails": to or ["to@example.invalid"],
            "cc_emails": cc or ["cc@example.invalid"],
            "subject": subject,
            "body": body,
            "expected_prior_audit_id": prior,
            "operation_id": operation_id,
        })


def _email_get(client, canvas_id):
    return client.get(f"/api/canvas/email/{canvas_id}")


def test_requires_prior_and_roundtrips_exact_body(world):
    canvas_id, create_audit = world.create_canvas()
    client = _client(world)
    missing = _save(client, canvas_id, prior="")
    assert missing.status_code == 409, missing.text
    assert missing.json()["detail"]["error"] == (
        "expected_prior_audit_id_required")
    assert missing.json()["detail"]["current_audit_id"] == create_audit
    assert world.audit_count(canvas_id) == 1

    saved = _save(client, canvas_id, prior=create_audit,
                  operation_id="draft-op-1")
    assert saved.status_code == 200, saved.text
    assert saved.json()["verification"]["status"] == "verified"
    assert saved.json()["draft_id"]
    assert world.audit_count(canvas_id) == 2

    email = _email_get(client, canvas_id)
    assert email.status_code == 200, email.text
    draft = email.json()["draft"]
    assert draft["to_emails"] == ["to@example.invalid"]
    assert draft["cc_emails"] == ["cc@example.invalid"]
    assert draft["subject"] == "Draft Subject"
    assert draft["body"] == "Draft body"
    generic = client.get(f"/api/canvas/{canvas_id}")
    assert generic.status_code == 200
    assert generic.json()["content"]["body"] == "Draft body"
    fresh = world.fresh(canvas_id)
    assert fresh["content"]["body"] == "Draft body"
    assert fresh["audit_tenant"] == world.tenant

    # Idempotent replay of the same logical operation/material.
    replay = _save(client, canvas_id, prior=create_audit,
                   operation_id="draft-op-1")
    assert replay.status_code == 200, replay.text
    assert replay.json().get("write_outcome") in (
        "already_applied", "no_change", "committed")
    assert world.audit_count(canvas_id) == 2

    # Same operation id with different material is not a retry.
    conflict = _save(client, canvas_id, prior=create_audit,
                     operation_id="draft-op-1", body="different body")
    assert conflict.status_code == 409, conflict.text
    assert world.audit_count(canvas_id) == 2


def test_stale_prior_refuses_without_overwriting_peer(world):
    canvas_id, create_audit = world.create_canvas()
    client = _client(world)
    first = _save(client, canvas_id, prior=create_audit, body="peer body")
    assert first.status_code == 200
    peer_audit = world.latest_audit_id(canvas_id)
    stale = _save(client, canvas_id, prior=create_audit, body="stale body")
    assert stale.status_code == 409, stale.text
    assert world.latest_audit_id(canvas_id) == peer_audit
    assert world.fresh(canvas_id)["content"]["body"] == "peer body"


def test_inactive_moved_actor_and_moved_target_refuse(world):
    canvas_id, create_audit = world.create_canvas()
    client = _client(world)

    with world.Session() as db:
        db.query(User).filter(User.id == world.owner).update(
            {"is_active": False}, synchronize_session=False)
        db.commit()
    inactive = _save(client, canvas_id, prior=create_audit)
    assert inactive.status_code == 403, inactive.text
    assert world.audit_count(canvas_id) == 1

    with world.Session() as db:
        db.query(User).filter(User.id == world.owner).update(
            {"is_active": True, "tenant_id": world.foreign_tenant,
             "workspace_id": world.foreign_ws},
            synchronize_session=False)
        db.commit()
    moved_actor = _save(client, canvas_id, prior=create_audit)
    assert moved_actor.status_code == 403, moved_actor.text
    assert world.audit_count(canvas_id) == 1

    with world.Session() as db:
        db.query(User).filter(User.id == world.owner).update(
            {"tenant_id": world.tenant, "workspace_id": world.ws},
            synchronize_session=False)
        db.query(Canvas).filter(Canvas.id == canvas_id).update(
            {"tenant_id": world.foreign_tenant,
             "workspace_id": world.foreign_ws},
            synchronize_session=False)
        db.commit()
    moved_target = _save(client, canvas_id, prior=create_audit)
    assert moved_target.status_code in (403, 404), moved_target.text
    assert world.audit_count(canvas_id) == 1
    assert _email_get(client, canvas_id).status_code in (403, 404)


def test_scoped_create_is_ordinary_put_editable(world):
    client = _client(world)
    created = client.post(
        "/api/canvas/email/create",
        json={"user_id": "ignored", "subject": "Scoped Draft",
              "recipients": ["to@example.invalid"],
              "layout": "conversation"})
    assert created.status_code == 200, created.text
    canvas_id = created.json()["canvas_id"]
    fresh = world.fresh(canvas_id)
    assert fresh["canvas_tenant"] == world.tenant
    assert fresh["canvas_workspace"] == world.ws
    assert fresh["audit_tenant"] == world.tenant

    prior = world.latest_audit_id(canvas_id)
    put = client.put(
        f"/api/canvas/{canvas_id}?canvas_type=email",
        params={"expected_prior_audit_id": prior},
        json={"to": "to@example.invalid", "cc": "",
              "subject": "Scoped Draft", "body": "Ordinary PUT body"})
    assert put.status_code == 200, put.text
    assert put.json()["verification"]["status"] == "verified"
    generic = client.get(f"/api/canvas/{canvas_id}")
    assert generic.json()["content"]["body"] == "Ordinary PUT body"
    email = _email_get(client, canvas_id)
    assert email.status_code == 200, email.text
    assert email.json()["draft"]["body"] == "Ordinary PUT body"
    assert email.json()["draft"]["to_emails"] == ["to@example.invalid"]


def test_email_get_projects_native_thread_and_attachments(world):
    attachment = {"attachment_id": "att-1", "filename": "a.pdf",
                  "sendable": False, "origin": "received"}
    canvas_id, create_audit = world.create_canvas(
        thread_id="thread-1", attachments=[attachment])
    client = _client(world)
    put = client.put(
        f"/api/canvas/{canvas_id}?canvas_type=email",
        params={"expected_prior_audit_id": create_audit},
        json={"to": "to@example.invalid", "cc": "cc@example.invalid",
              "subject": "Thread Draft", "body": "Thread body",
              "attachments": [attachment], "thread_id": "thread-1"})
    assert put.status_code == 200, put.text
    email = _email_get(client, canvas_id)
    assert email.status_code == 200, email.text
    view = email.json()
    assert view["draft"]["body"] == "Thread body"
    assert view["draft"]["subject"] == "Thread Draft"
    assert view["thread_id"] == "thread-1"
    assert view["attachments"][0]["attachment_id"] == "att-1"


def test_uncertain_and_refused_writes_are_truthful(
        world, monkeypatch):
    canvas_id, create_audit = world.create_canvas()
    client = _client(world)
    import core.canvas_write_service as write_service

    async def uncertain(**kwargs):
        return {"success": True, "status": "effect_unknown",
                "write_outcome": "unknown",
                "verification": {"status": "unavailable",
                                 "effect": "unknown",
                                 "replay": "do_not_repeat"}}

    monkeypatch.setattr(write_service, "update_canvas_verified", uncertain)
    response = _save(client, canvas_id, prior=create_audit)
    assert response.status_code == 200
    assert response.json()["status"] == "effect_unknown"
    assert response.json()["verification"]["effect"] == "unknown"

    async def refused(**kwargs):
        return {"success": False, "status": "refused", "http_status": 500,
                "error": "database unavailable",
                "verification": {"status": "not_attempted",
                                 "effect": "none"}}

    monkeypatch.setattr(write_service, "update_canvas_verified", refused)
    failed = _save(client, canvas_id, prior=create_audit)
    assert failed.status_code == 500
    assert failed.json()["detail"]["error"] == "email_draft_save_refused"


def test_fresh_process_reads_exact_saved_body(world, tmp_path):
    canvas_id, create_audit = world.create_canvas()
    client = _client(world)
    saved = _save(client, canvas_id, prior=create_audit,
                  body="fresh process body")
    assert saved.status_code == 200, saved.text
    helper = Path(__file__).resolve().parent / "helpers" / (
        "email_draft_readback_child.py")
    env = os.environ.copy()
    db_path = str(world.engine.url.database)
    env.update({
        "TESTING": "0",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "PYTHONPATH": str(Path(__file__).resolve().parents[1])
        + os.pathsep + env.get("PYTHONPATH", ""),
    })
    completed = subprocess.run(
        [sys.executable, str(helper), db_path, canvas_id, world.owner],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        completed.stdout.splitlines()[-1].split("RESULT_JSON:", 1)[1])
    assert payload["status"] == 200
    assert payload["draft"]["body"] == "fresh process body"
    assert payload["draft"]["to_emails"] == ["to@example.invalid"]


def test_generic_put_explicit_empty_does_not_resurrect_native_values(
        world, tmp_path):
    attachment = {"attachment_id": "att-old", "filename": "old.pdf",
                  "sendable": False, "origin": "received"}
    canvas_id, create_audit = world.create_canvas(
        thread_id="thread-clear", attachments=[attachment])
    client = _client(world)
    native = _save(client, canvas_id, prior=create_audit,
                   to=["old@example.invalid"], cc=["oldcc@example.invalid"],
                   subject="Old Subject", body="Old Body")
    assert native.status_code == 200, native.text
    prior = world.latest_audit_id(canvas_id)

    put = client.put(
        f"/api/canvas/{canvas_id}?canvas_type=email",
        params={"expected_prior_audit_id": prior},
        json={"to": "new@example.invalid", "cc": "", "subject": "",
              "body": "", "attachments": [], "thread_id": "thread-clear"})
    assert put.status_code == 200, put.text
    view = _email_get(client, canvas_id).json()
    assert view["draft"]["to_emails"] == ["new@example.invalid"]
    assert view["draft"]["cc_emails"] == []
    assert view["draft"]["subject"] == ""
    assert view["draft"]["body"] == ""
    assert view["draft"]["attachments"] == []
    assert view["attachments"] == []
    fresh = world.fresh(canvas_id)
    assert fresh["content"]["to"] == "new@example.invalid"
    assert fresh["content"]["cc"] == ""
    assert fresh["content"]["subject"] == ""
    assert fresh["content"]["body"] == ""
    assert fresh["content"]["attachments"] == []

    helper = Path(__file__).resolve().parent / "helpers" / (
        "email_draft_readback_child.py")
    db_path = str(world.engine.url.database)
    env = os.environ.copy()
    env.update({
        "TESTING": "0",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "PYTHONPATH": str(Path(__file__).resolve().parents[1])
        + os.pathsep + env.get("PYTHONPATH", ""),
    })
    completed = subprocess.run(
        [sys.executable, str(helper), db_path, canvas_id, world.owner],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        completed.stdout.splitlines()[-1].split("RESULT_JSON:", 1)[1])
    assert payload["draft"]["to_emails"] == ["new@example.invalid"]
    assert payload["draft"]["cc_emails"] == []
    assert payload["draft"]["subject"] == ""
    assert payload["draft"]["body"] == ""
    assert payload["draft"]["attachments"] == []

    # A later native save must not resurrect the cleared attachment from the
    # older receipt; explicit empty remains the visible value.
    cleared_prior = world.latest_audit_id(canvas_id)
    after = _save(client, canvas_id, prior=cleared_prior,
                  to=["new2@example.invalid"], cc=[], subject="",
                  body="after clear")
    assert after.status_code == 200, after.text
    view2 = _email_get(client, canvas_id).json()
    assert view2["draft"]["body"] == "after clear"
    assert view2["draft"]["attachments"] == []


def test_generic_put_with_stale_nested_draft_keeps_top_level_edits(world):
    """The ordinary panel spreads the loaded payload (including a stale
    nested draft) and writes the visible top-level fields. Top-level key
    presence must win, or every edit is silently reverted to the seed."""
    canvas_id, create_audit = world.create_canvas(thread_id="thread-stale")
    client = _client(world)
    native = _save(client, canvas_id, prior=create_audit,
                   to=["old@example.invalid"], cc=["oldcc@example.invalid"],
                   subject="Email Draft OLD", body="Old body OLD-1111")
    assert native.status_code == 200, native.text
    prior = world.latest_audit_id(canvas_id)
    stale_draft = dict(world.fresh(canvas_id)["content"]["draft"])
    assert stale_draft["body"] == "Old body OLD-1111"

    put = client.put(
        f"/api/canvas/{canvas_id}?canvas_type=email",
        params={"expected_prior_audit_id": prior},
        json={"to": "alpha@example.invalid, clear@example.invalid", "cc": "",
              "subject": "Email Draft CURRENT",
              "body": "Current body NEW-EMAIL-7788",
              "attachments": [], "thread_id": "thread-stale",
              "draft": stale_draft})
    assert put.status_code == 200, put.text

    view = _email_get(client, canvas_id).json()
    assert view["draft"]["to_emails"] == [
        "alpha@example.invalid", "clear@example.invalid"]
    assert view["draft"]["cc_emails"] == []
    assert view["draft"]["subject"] == "Email Draft CURRENT"
    assert view["draft"]["body"] == "Current body NEW-EMAIL-7788"

    fresh = world.fresh(canvas_id)
    assert fresh["content"]["to"] == (
        "alpha@example.invalid, clear@example.invalid")
    assert fresh["content"]["cc"] == ""
    assert fresh["content"]["subject"] == "Email Draft CURRENT"
    assert fresh["content"]["body"] == "Current body NEW-EMAIL-7788"
    # The nested view is refreshed, so a later reader cannot resurrect OLD.
    assert fresh["content"]["draft"]["to_emails"] == [
        "alpha@example.invalid", "clear@example.invalid"]
    assert fresh["content"]["draft"]["cc_emails"] == []
    assert fresh["content"]["draft"]["subject"] == "Email Draft CURRENT"
    assert fresh["content"]["draft"]["body"] == "Current body NEW-EMAIL-7788"


def test_readback_explicit_empty_does_not_resurrect_stale_details_draft(world):
    """A present-but-empty canonical field is an explicit value. Stale
    ``details.draft`` metadata from an older writer must not fill it back in
    on read."""
    stale_draft = {
        "draft_id": "draft-stale",
        "to_emails": ["stale@example.invalid"],
        "cc_emails": ["stalecc@example.invalid"],
        "subject": "Stale Subject",
        "body": "Stale Body",
        "attachments": [],
    }
    canvas_id, create_audit = world.create_canvas(
        content={"to": "", "cc": "", "subject": "", "body": ""},
        draft=stale_draft)
    client = _client(world)
    put = client.put(
        f"/api/canvas/{canvas_id}?canvas_type=email",
        params={"expected_prior_audit_id": create_audit},
        json={"to": "", "cc": "", "subject": "", "body": "",
              "attachments": []})
    assert put.status_code == 200, put.text

    view = _email_get(client, canvas_id).json()
    assert view["draft"]["to_emails"] == []
    assert view["draft"]["cc_emails"] == []
    assert view["draft"]["subject"] == ""
    assert view["draft"]["body"] == ""

    fresh = world.fresh(canvas_id)
    assert fresh["content"]["to"] == ""
    assert fresh["content"]["cc"] == ""
    assert fresh["content"]["subject"] == ""
    assert fresh["content"]["body"] == ""


def test_native_attachment_identity_is_preserved_without_duplication(world):
    attachment = {"attachment_id": "att-keep", "filename": "keep.pdf",
                  "sendable": False, "origin": "received"}
    canvas_id, create_audit = world.create_canvas(attachments=[attachment])
    client = _client(world)
    first = _save(client, canvas_id, prior=create_audit, body="one")
    assert first.status_code == 200
    prior = world.latest_audit_id(canvas_id)
    second = _save(client, canvas_id, prior=prior, body="two")
    assert second.status_code == 200
    view = _email_get(client, canvas_id).json()
    assert [item["attachment_id"] for item in view["attachments"]] == [
        "att-keep"]
    assert [item["attachment_id"]
            for item in view["draft"]["attachments"]] == ["att-keep"]


@pytest.mark.parametrize("change", ["deactivate", "move"])
def test_create_authority_race_has_zero_effects(world, monkeypatch, change):
    from core.canvas_email_service import EmailCanvasService

    original = EmailCanvasService._resolve_actor_scope

    def race(self, user_id, tenant_id=None, workspace_id=None):
        resolved = original(self, user_id, tenant_id, workspace_id)
        with world.Session() as peer:
            values = ({"is_active": False} if change == "deactivate"
                      else {"tenant_id": world.foreign_tenant,
                            "workspace_id": world.foreign_ws})
            peer.query(User).filter(User.id == world.owner).update(
                values, synchronize_session=False)
            peer.commit()
        return resolved

    monkeypatch.setattr(EmailCanvasService, "_resolve_actor_scope", race)
    client = _client(world)
    response = client.post(
        "/api/canvas/email/create",
        json={"user_id": "ignored", "subject": "Race Draft",
              "recipients": ["to@example.invalid"]})
    assert response.status_code == 400, response.text
    with world.Session() as db:
        canvases = db.query(Canvas).filter(
            Canvas.created_by == world.owner,
            Canvas.name == "Race Draft").count()
    assert canvases == 0


def test_created_draft_survives_ordinary_restart(world):
    client = _client(world)
    created = client.post(
        "/api/canvas/email/create",
        json={"user_id": "ignored", "subject": "Restart Draft",
              "recipients": ["restart@example.invalid"]})
    assert created.status_code == 200, created.text
    canvas_id = created.json()["canvas_id"]
    prior = world.latest_audit_id(canvas_id)
    saved = _save(client, canvas_id, prior=prior,
                  to=["restart@example.invalid"], body="restart body")
    assert saved.status_code == 200, saved.text
    helper = Path(__file__).resolve().parent / "helpers" / (
        "email_draft_readback_child.py")
    db_path = str(world.engine.url.database)
    env = os.environ.copy()
    env.update({
        "TESTING": "0", "DATABASE_URL": f"sqlite:///{db_path}",
        "PYTHONPATH": str(Path(__file__).resolve().parents[1])
        + os.pathsep + env.get("PYTHONPATH", ""),
    })
    completed = subprocess.run(
        [sys.executable, str(helper), db_path, canvas_id, world.owner],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        completed.stdout.splitlines()[-1].split("RESULT_JSON:", 1)[1])
    assert payload["status"] == 200
    assert payload["draft"]["body"] == "restart body"
    assert payload["draft"]["to_emails"] == ["restart@example.invalid"]


def test_create_rejects_scope_disagreement_and_unknown_user(world):
    from core.canvas_email_service import EmailCanvasService

    with world.Session() as db:
        mismatch = EmailCanvasService(db).create_email_canvas(
            user_id=world.owner, subject="Mismatch",
            recipients=["to@example.invalid"],
            tenant_id=world.foreign_tenant,
            workspace_id=world.foreign_ws)
        unknown = EmailCanvasService(db).create_email_canvas(
            user_id="user-does-not-exist", subject="Unknown",
            recipients=["to@example.invalid"])
    assert mismatch["success"] is False
    assert unknown["success"] is False
    with world.Session() as db:
        assert db.query(Canvas).filter(
            Canvas.name.in_(["Mismatch", "Unknown"])).count() == 0


@pytest.mark.parametrize("moved", ["default", ""])
def test_create_null_raw_scope_move_has_zero_effects(world, monkeypatch, moved):
    from core.canvas_email_service import EmailCanvasService
    from core.models import User

    personal = f"personal-{moved or 'empty'}"
    with world.Session() as db:
        db.add(User(
            id=personal, tenant_id=None, workspace_id=None,
            email=f"{personal}@example.invalid", hashed_password="x",
            first_name="P", last_name="User", role="member",
            status="active", is_active=True))
        db.commit()

    original = EmailCanvasService._resolve_actor_scope

    def race(self, user_id, tenant_id=None, workspace_id=None):
        resolved = original(self, user_id, tenant_id, workspace_id)
        with world.Session() as peer:
            peer.query(User).filter(User.id == personal).update(
                {"tenant_id": moved, "workspace_id": moved},
                synchronize_session=False)
            peer.commit()
        return resolved

    monkeypatch.setattr(EmailCanvasService, "_resolve_actor_scope", race)
    with world.Session() as db:
        result = EmailCanvasService(db).create_email_canvas(
            user_id=personal, subject=f"Raw {moved or 'empty'}",
            recipients=["to@example.invalid"])
    assert result["success"] is False
    with world.Session() as db:
        assert db.query(Canvas).filter(Canvas.created_by == personal).count() == 0


@pytest.mark.parametrize("raw_scope", ["default", None], ids=["explicit-default", "bootstrap-null"])
def test_active_personal_default_create_is_ordinary_put_editable(world, raw_scope):
    from core.models import User

    personal = "personal-default"
    with world.Session() as db:
        if db.get(Tenant, "default") is None:
            db.add(Tenant(id="default", name="Default",
                          subdomain="personal-default",
                          edition="personal", is_active=True))
            db.add(Workspace(id="default", name="Default",
                             tenant_id="default"))
        db.add(User(
            id=personal, tenant_id=raw_scope, workspace_id=raw_scope,
            email=f"{personal}@example.invalid", hashed_password="x",
            first_name="P", last_name="User", role="member",
            status="active", is_active=True))
        db.commit()
    client = _client(world, user_id=personal)
    created = client.post(
        "/api/canvas/email/create",
        json={"user_id": "ignored", "subject": "Personal Draft",
              "recipients": ["to@example.invalid"]})
    assert created.status_code == 200, created.text
    canvas_id = created.json()["canvas_id"]
    fresh = world.fresh(canvas_id)
    assert fresh["canvas_tenant"] == "default"
    assert fresh["canvas_workspace"] == "default"
    assert fresh["audit_tenant"] == "default"
    prior = world.latest_audit_id(canvas_id)
    put = client.put(
        f"/api/canvas/{canvas_id}?canvas_type=email",
        params={"expected_prior_audit_id": prior},
        json={"to": "to@example.invalid", "cc": "",
              "subject": "Personal Draft", "body": "personal body"})
    assert put.status_code == 200, put.text
    assert _email_get(client, canvas_id).json()["draft"]["body"] == (
        "personal body")

    with world.Session() as db:
        actor = db.get(User, personal)
        assert actor.tenant_id == raw_scope
        assert actor.workspace_id == raw_scope
