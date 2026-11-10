"""Read-only public-boundary audit for ordinary email draft save/open/reload.

Scratch SQLite only; real JWT/get_current_user and development-audience guard.
No provider, send, model, browser or live DB.
"""
from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

from api.canvas_email_routes import router as email_router
from api.canvas_routes import router as canvas_router
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import Canvas, CanvasAudit, Tenant, User, Workspace

DB_PATH = sys.argv[1]
ENGINE = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Base.metadata.create_all(ENGINE)
Session = sessionmaker(bind=ENGINE, expire_on_commit=False)
SUFFIX = uuid.uuid4().hex[:8]
TENANT = f"tenant-{SUFFIX}"
FOREIGN_TENANT = f"tenant-f-{SUFFIX}"
WS = f"ws-{SUFFIX}"
FOREIGN_WS = f"ws-f-{SUFFIX}"
OWNER = f"owner-{SUFFIX}"
PEER = f"peer-{SUFFIX}"

with Session() as db:
    db.add(Tenant(id=TENANT, name="T", subdomain=f"t-{SUFFIX}",
                  edition="personal", is_active=True))
    db.add(Tenant(id=FOREIGN_TENANT, name="F", subdomain=f"f-{SUFFIX}",
                  edition="personal", is_active=True))
    db.add(Workspace(id=WS, name="W", tenant_id=TENANT))
    db.add(Workspace(id=FOREIGN_WS, name="FW", tenant_id=FOREIGN_TENANT))
    for uid, tenant, ws in ((OWNER, TENANT, WS), (PEER, TENANT, WS)):
        db.add(User(id=uid, tenant_id=tenant, workspace_id=ws,
                    email=f"{uid}@example.invalid", hashed_password="x",
                    first_name="U", last_name="Ser", role="member",
                    status="active", is_active=True))
    db.commit()


def token(uid: str) -> str:
    with Session() as db:
        user = db.query(User).filter(User.id == uid).one()
        return create_access_token({"sub": user.id}, user=user)


def make_canvas(owner: str = OWNER, tenant: str = TENANT, ws: str = WS):
    cid = f"canvas-{uuid.uuid4().hex[:10]}"
    aid = f"audit-{uuid.uuid4().hex[:10]}"
    with Session() as db:
        db.add(Canvas(
            id=cid, tenant_id=tenant, workspace_id=ws, created_by=owner,
            name="Draft", canvas_type="email",
            content={"to": "", "cc": "", "subject": "Draft", "body": ""},
            status="active"))
        db.add(CanvasAudit(
            id=aid, canvas_id=cid, tenant_id=tenant, user_id=owner,
            canvas_type="email", action_type="create",
            details_json={
                "canvas_type": "email", "component_type": "compose_form",
                "subject": "Draft", "layout": "conversation",
                "thread_id": str(uuid.uuid4()),
                "draft": {"draft_id": str(uuid.uuid4()), "to_emails": [],
                          "cc_emails": [], "subject": "Draft", "body": "",
                          "attachments": []},
                "messages": [], "attachments": [],
            }))
        db.commit()
    return cid


def client(uid: str | None = None):
    app = FastAPI()
    app.include_router(email_router)
    app.include_router(canvas_router)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    c = TestClient(app)
    if uid:
        c.headers["Authorization"] = f"Bearer {token(uid)}"
    return c


def save(c, cid, body, subject="Draft", to=None):
    response = c.post(
        f"/api/canvas/email/{cid}/draft",
        json={"user_id": "ignored", "to_emails": to or ["a@example.invalid"],
              "cc_emails": ["c@example.invalid"], "subject": subject,
              "body": body})
    return response


def latest_audit(cid):
    with Session() as db:
        row = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == cid,
            CanvasAudit.canvas_type == "email",
        ).order_by(desc(CanvasAudit.created_at)).first()
        row2 = db.query(Canvas).filter(Canvas.id == cid).first()
        return {
            "audit_tenant": row.tenant_id if row else None,
            "audit_action": row.action_type if row else None,
            "audit_user": row.user_id if row else None,
            "audit_draft": ((row.details_json or {}).get("draft")
                            if row else None),
            "canvas_tenant": row2.tenant_id if row2 else None,
            "canvas_workspace": row2.workspace_id if row2 else None,
            "canvas_content": dict(row2.content or {}) if row2 else None,
        }


results = {}

# A. positive save + email read + general read + fresh SQL receipt
cid = make_canvas()
c = client(OWNER)
r = save(c, cid, "positive body", subject="Positive Subject")
get_email = c.get(f"/api/canvas/email/{cid}")
get_general = c.get(f"/api/canvas/{cid}")
results["positive"] = {
    "save_status": r.status_code,
    "email_read_status": get_email.status_code,
    "email_read_body": (
        ((get_email.json() or {}).get("draft") or {}).get("body")
        if get_email.status_code == 200 else None),
    "general_read_status": get_general.status_code,
    "general_read_body": (
        (get_general.json() or {}).get("content", {}).get("body")
        if get_general.status_code == 200 and isinstance(
            get_general.json(), dict) else None),
    "fresh": latest_audit(cid),
}

# B. foreign user
foreign = client(PEER)
rb = save(foreign, cid, "foreign body")
results["foreign_user"] = {"status": rb.status_code}

# C. inactive actor (is_active False; status remains active)
inactive_cid = make_canvas()
inactive_token = token(OWNER)
with Session() as db:
    db.query(User).filter(User.id == OWNER).update(
        {"is_active": False}, synchronize_session=False)
    db.commit()
ic = client(None)
ic.headers["Authorization"] = f"Bearer {inactive_token}"
rc = save(ic, inactive_cid, "inactive body")
results["inactive_actor"] = {
    "status": rc.status_code,
    "fresh": latest_audit(inactive_cid),
}
with Session() as db:
    db.query(User).filter(User.id == OWNER).update(
        {"is_active": True}, synchronize_session=False)
    db.commit()

# D. moved actor (owner moved to a foreign tenant/workspace after token issued)
moved_actor_cid = make_canvas()
moved_actor_token = token(OWNER)
with Session() as db:
    db.query(User).filter(User.id == OWNER).update(
        {"tenant_id": FOREIGN_TENANT, "workspace_id": FOREIGN_WS},
        synchronize_session=False)
    db.commit()
mc = client(None)
mc.headers["Authorization"] = f"Bearer {moved_actor_token}"
rd = save(mc, moved_actor_cid, "moved actor body")
results["moved_actor"] = {
    "status": rd.status_code,
    "fresh": latest_audit(moved_actor_cid),
}
with Session() as db:
    db.query(User).filter(User.id == OWNER).update(
        {"tenant_id": TENANT, "workspace_id": WS},
        synchronize_session=False)
    db.commit()

# E. moved target (canvas moved to foreign tenant/workspace)
moved_target_cid = make_canvas()
c2 = client(OWNER)
with Session() as db:
    db.query(Canvas).filter(Canvas.id == moved_target_cid).update(
        {"tenant_id": FOREIGN_TENANT, "workspace_id": FOREIGN_WS},
        synchronize_session=False)
    db.commit()
re = save(c2, moved_target_cid, "moved target body")
results["moved_target"] = {
    "status": re.status_code,
    "fresh": latest_audit(moved_target_cid),
}

# F. stale peer overwrite: two independently authenticated editors save
# without any source/prior revision in the request.
race_cid = make_canvas()
editor_a = client(OWNER)
editor_b = client(OWNER)
ra1 = save(editor_a, race_cid, "accepted peer body", subject="Peer Subject")
rb1 = save(editor_b, race_cid, "stale editor body", subject="Stale Subject")
ra2 = save(editor_a, race_cid, "accepted peer body v2",
           subject="Peer Subject v2")
results["stale_overwrite"] = {
    "statuses": [ra1.status_code, rb1.status_code, ra2.status_code],
    "final": latest_audit(race_cid),
}

# G. shared generic canvas PUT path used by the ordinary frontend and prior
# accepted connected-core evidence: authority + expected-prior CAS.
def latest_audit_id(canvas_id):
    with Session() as db:
        row = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.canvas_type == "email",
        ).order_by(desc(CanvasAudit.created_at)).first()
        return row.id if row else None


shared_cid = make_canvas()
shared_client = client(OWNER)
prior = latest_audit_id(shared_cid)
shared_body = {"to": "shared@example.invalid", "cc": "scc@example.invalid",
               "subject": "Shared Subject", "body": "shared body"}
shared_put = shared_client.put(
    f"/api/canvas/{shared_cid}?canvas_type=email",
    params={"expected_prior_audit_id": prior},
    json=shared_body)
shared_get = shared_client.get(f"/api/canvas/email/{shared_cid}")
shared_general = shared_client.get(f"/api/canvas/{shared_cid}")
stale_put = shared_client.put(
    f"/api/canvas/{shared_cid}?canvas_type=email",
    params={"expected_prior_audit_id": prior},
    json={**shared_body, "body": "stale shared body"})
results["shared_put_positive"] = {
    "put_status": shared_put.status_code,
    "put_verification": (shared_put.json() or {}).get("verification")
    if shared_put.status_code == 200 else None,
    "email_read_status": shared_get.status_code,
    "email_read_body": (
        ((shared_get.json() or {}).get("draft") or {}).get("body")
        if shared_get.status_code == 200 else None),
    "general_read_status": shared_general.status_code,
    "general_read_body": (
        (shared_general.json() or {}).get("content", {}).get("body")
        if shared_general.status_code == 200 else None),
    "stale_status": stale_put.status_code,
    "fresh": latest_audit(shared_cid),
}

# H. moved target on the shared path must refuse before effect.
shared_moved_cid = make_canvas()
with Session() as db:
    db.query(Canvas).filter(Canvas.id == shared_moved_cid).update(
        {"tenant_id": FOREIGN_TENANT, "workspace_id": FOREIGN_WS},
        synchronize_session=False)
    db.commit()
shared_moved = client(OWNER).put(
    f"/api/canvas/{shared_moved_cid}?canvas_type=email",
    json={"to": "x@example.invalid", "cc": "", "subject": "X",
          "body": "moved shared target"})
results["shared_moved_target"] = {
    "status": shared_moved.status_code,
    "fresh": latest_audit(shared_moved_cid),
}

# K. public email canvas creation under a non-default current actor scope.
create_client = client(OWNER)
create_resp = create_client.post(
    "/api/canvas/email/create",
    json={"user_id": "ignored", "subject": "Scoped Create",
          "recipients": ["a@example.invalid"], "layout": "conversation"})
created_id = ((create_resp.json() or {}).get("canvas_id")
              if create_resp.status_code == 200 else None)
created_general = (create_client.get(f"/api/canvas/{created_id}")
                   if created_id else None)
created_email = (create_client.get(f"/api/canvas/email/{created_id}")
                 if created_id else None)
with Session() as db:
    created_row = (db.query(Canvas).filter(Canvas.id == created_id).first()
                   if created_id else None)
    created_audit = (db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == created_id,
        CanvasAudit.canvas_type == "email",
    ).order_by(desc(CanvasAudit.created_at)).first()
        if created_id else None)
results["scoped_create"] = {
    "create_status": create_resp.status_code,
    "canvas_id_present": bool(created_id),
    "created_canvas_tenant": created_row.tenant_id if created_row else None,
    "created_canvas_workspace": (
        created_row.workspace_id if created_row else None),
    "created_audit_tenant": (
        created_audit.tenant_id if created_audit else None),
    "general_read_status": (
        created_general.status_code if created_general is not None else None),
    "email_read_status": (
        created_email.status_code if created_email is not None else None),
}

# I. inactive actor on the shared path.
shared_inactive_cid = make_canvas()
shared_inactive_token = token(OWNER)
with Session() as db:
    db.query(User).filter(User.id == OWNER).update(
        {"is_active": False}, synchronize_session=False)
    db.commit()
shared_inactive = client(None)
shared_inactive.headers["Authorization"] = f"Bearer {shared_inactive_token}"
shared_inactive_resp = shared_inactive.put(
    f"/api/canvas/{shared_inactive_cid}?canvas_type=email",
    json={"to": "x@example.invalid", "cc": "", "subject": "X",
          "body": "inactive shared actor"})
results["shared_inactive_actor"] = {
    "status": shared_inactive_resp.status_code,
    "fresh": latest_audit(shared_inactive_cid),
}
with Session() as db:
    db.query(User).filter(User.id == OWNER).update(
        {"is_active": True}, synchronize_session=False)
    db.commit()

# J. fresh OS process read of the positive saved draft
child = Path(__file__).with_name("atom-goal11-email-draft-audit-20261110-child.py")
child_env = {**__import__("os").environ,
             "TESTING": "0", "DATABASE_URL": f"sqlite:///{DB_PATH}",
             "PYTHONPATH": str(Path.cwd()) + __import__("os").pathsep
             + "<root-plugin-path>"}
completed = subprocess.run(
    [sys.executable, str(child), str(DB_PATH), cid, OWNER],
    capture_output=True, text=True, timeout=120, env=child_env)
payload = None
if completed.returncode == 0:
    payload = json.loads(completed.stdout.splitlines()[-1].split(
        "RESULT_JSON:", 1)[1])
results["fresh_process"] = {
    "returncode": completed.returncode,
    "payload": payload,
    "stderr": completed.stderr[-1000:] if completed.returncode else "",
}
print("RESULT_JSON:" + json.dumps(results, sort_keys=True, default=str))
