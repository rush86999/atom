#!/usr/bin/env python3
"""Planner/apply probe: F02 wrong-field, F03 sync edit, F05 background failure.

Injects ONE thing — the planner's model response — through the harness's own
provider shim. Authentication, authorization, the lifecycle reservation, the
execution claim, the store call, the audit append, the independent read-back,
verification and finalization all run for real. That makes every result
EFFECT-LAYER evidence and never evidence that the production planner accepts
canvas edits (it does not; see the ledger's F06).

The shim scripts are AUTHORED MODEL COMPLETIONS. No outcome is manufactured: a
case's verdict comes from the durable canvas content, the canvas_audit rows and
the served HTTP response, never from the script.

Reuses the C16 rig's mechanics (shim registration in the world DB, API canvas
creation, read-only state readers) rather than re-deriving them.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
LANE3 = HERE.parent
REPO = LANE3.parents[4]
BACKEND = REPO / "backend"
WORLDS = BACKEND / "data" / "acceptance_worlds"
STACK = BACKEND / "scripts" / "orchestration_acceptance" / "preview_stack.py"
PY = str(BACKEND / "venv314" / "bin" / "python")

sys.path.insert(0, str(LANE3))
sys.path.insert(0, str(BACKEND))
import controlled_planner_c16 as RIG  # noqa: E402

LOGIN_EMAIL = "admin@example.com"
LOGIN_PASSWORD = os.environ.get("LANE3_PREVIEW_PASSWORD") or "preview-only-local-2026"

#: The email canvas body. `Quote validity: 15 days.` is the text the correct
#: edit targets; the SUBJECT is deliberately a different, observable string so
#: any write to it is unambiguous.
BODY_OLD = "Quote validity: 15 days."
BODY_NEW = "Quote validity: 30 days."
SUBJECT = "Quote for Steve - bandsaw WG-350DSAV"
SUBJECT_WRECKED = "Quote for Steve - bandsaw WG-350DSAV (updated)"
#: The historical scripted `find` from the reported incident: absent from the
#: body. It is preserved VERBATIM — aligning the fixture to it would erase the
#: negative case (guide §5).
ABSENT_FIND = "Quote validity: 99 days."


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def plan_tool_call(args: Dict[str, Any], tool: str = "CanvasEditPlan") -> Dict[str, Any]:
    return {"tool_call": {"name": tool, "arguments": args}}


def patch_plan(*, find: str, replace: str, field: str = "body",
               reply: str = "Updated the quote validity to 30 days.",
               wants_edit: bool = True, edit_mode: str = "patch") -> Dict[str, Any]:
    return {
        "wants_edit": wants_edit,
        "edit_mode": edit_mode,
        "ops": ([{"field": field, "find": find, "replace": replace}]
                if wants_edit else []),
        "restore_audit_id": None,
        "updated_content_json": None,
        "title": None,
        "reply": reply,
    }


def replace_plan(*, updated: Dict[str, Any],
                 reply: str = "Rewrote the canvas.",
                 ops: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "wants_edit": True,
        "edit_mode": "replace",
        "ops": ops or [],
        "restore_audit_id": None,
        "updated_content_json": json.dumps(updated),
        "title": None,
        "reply": reply,
    }


#: The re-ask suffix the product appends when the patch ops did not match. The
#: shim matches on the PROMPT BLOB, so this string is the reliable way to serve
#: the recovery leg a different completion from the first leg. Matched BEFORE
#: the generic tool name, because the shim serves the first matching entry.
REASK_MARK = "your ops did not match the current content exactly"
#: The contract-repair suffix, used the same way.
CONTRACT_REPAIR_MARK = "your previous answer was self-contradictory"


def build_script(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"responses": entries}


# --------------------------------------------------------------------------
# durable readers (read-only, world DB only — never the live dev DB)
# --------------------------------------------------------------------------
def canvas_state(db: str, canvas_id: str) -> Dict[str, Any]:
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT content FROM canvases WHERE id=?",
                          (canvas_id,)).fetchone()
        audits = con.execute(
            "SELECT id, action_type, user_id, details_json, created_at "
            "FROM canvas_audit WHERE canvas_id=? ORDER BY created_at, id",
            (canvas_id,)).fetchall()
        ops = con.execute(
            "SELECT id, "
            "  json_extract(parameters,'$.task_lifecycle.operations[0].status'),"
            "  json_extract(parameters,'$.task_lifecycle.operations[0].operation_id')"
            " FROM goal_runs WHERE json_extract(parameters,'$.task_lifecycle.operations')"
            " IS NOT NULL ORDER BY created_at DESC LIMIT 8").fetchall()
    finally:
        con.close()
    raw = (row[0] if row else "") or ""
    try:
        content = json.loads(raw)
    except Exception:
        content = {"__unparsed__": raw[:200]}
    if not isinstance(content, dict):
        content = {"__scalar__": str(content)[:200]}
    body = str(content.get("body") or "")
    subject = str(content.get("subject") or "")
    return {
        "canvas_id": canvas_id,
        "subject": subject,
        "subject_is_original": subject == SUBJECT,
        "subject_changed": subject != SUBJECT,
        "body_has_old": BODY_OLD in body,
        "body_has_new": BODY_NEW in body,
        "body_len": len(body),
        "content_keys": sorted(k for k in content if not k.startswith("__")),
        "audit_count": len(audits),
        "audit_rows": [{"action": a[1], "id": a[0], "user": a[2],
                        "details_head": str(a[3] or "")[:120]} for a in audits],
        "operations": [{"run_id": o[0], "status": o[1], "operation_id": o[2]}
                       for o in ops],
    }


def all_canvas_audits(db: str, canvas_id: str, after: str) -> List[Dict[str, Any]]:
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, action_type, created_at FROM canvas_audit "
            "WHERE canvas_id=? AND created_at > ? ORDER BY created_at, id",
            (canvas_id, after)).fetchall()
    finally:
        con.close()
    return [{"id": r[0], "action": r[1], "created_at": r[2]} for r in rows]


def mutation_audits(db: str, canvas_id: str, after: str) -> List[Dict[str, Any]]:
    """Every audit row on the canvas after the post-seed baseline, regardless
    of action type or operation id. `create` is the seed's own row and is
    excluded only because the baseline timestamp is taken after it."""
    return [r for r in all_canvas_audits(db, canvas_id, after)
            if r["action"] in ("update", "delete", "restore", "send")]


def agent_executions(db: str, session_id: str) -> List[Dict[str, Any]]:
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, status, triggered_by, started_at, completed_at, "
            "substr(coalesce(metadata_json,''),1,900) "
            "FROM agent_executions WHERE triggered_by != 'continuation' "
            "ORDER BY started_at").fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        try:
            meta = json.loads(r[5] or "{}")
        except Exception:
            meta = {"_unparsed": (r[5] or "")[:200]}
        if session_id and meta.get("session_id") not in (None, session_id):
            continue
        out.append({"id": r[0], "status": r[1], "triggered_by": r[2],
                    "started_at": r[3], "completed_at": r[4], "metadata": meta})
    return out


def continuations(db: str, session_id: str = "") -> List[Dict[str, Any]]:
    """Durable continuation records (AgentExecution rows tagged
    triggered_by='continuation'), optionally narrowed to one session."""
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        q = ("SELECT id, status, triggered_by, result_summary, "
             "error_message, started_at, completed_at, "
             "substr(coalesce(metadata_json,''),1,2000) "
             "FROM agent_executions WHERE triggered_by='continuation'")
        rows = con.execute(q).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        try:
            meta = json.loads(r[7] or "{}")
        except Exception:
            meta = {"_unparsed": (r[7] or "")[:200]}
        cont = meta.get("continuation") or {}
        if session_id and cont.get("session_id") != session_id:
            continue
        out.append({"id": r[0], "status": r[1], "triggered_by": r[2],
                    "result_summary": r[3], "error_message": r[4],
                    "started_at": r[5], "completed_at": r[6],
                    "continuation": cont,
                    "originating_execution_id": meta.get("originating_execution_id"),
                    "origin_operation_id": meta.get("origin_operation_id")})
    return out


def chat_messages(db: str, conversation_id: str) -> List[Dict[str, Any]]:
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT role, content, substr(coalesce(metadata_json,''),1,700) "
            "FROM chat_messages WHERE conversation_id=? ORDER BY rowid",
            (conversation_id,)).fetchall()
    finally:
        con.close()
    return [{"role": r[0], "content": str(r[1] or "")[:600],
             "metadata_head": str(r[2] or "")[:400]} for r in rows]


# --------------------------------------------------------------------------
# world lifecycle
# --------------------------------------------------------------------------
def stack(*args: str, env: Optional[Dict[str, str]] = None,
          timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(STACK), *args], capture_output=True,
                          text=True, timeout=timeout,
                          env={**os.environ, **(env or {})}, cwd=str(REPO))


def bootstrap(world: str, port: int, script: Dict[str, Any], out: Path,
              pin_env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Shim first, then a fresh run dir, then register the shim, then restart.

    Order is load-bearing and failing it is SILENT:
      1. providers are discovered at server STARTUP, so the shim must be
         listening before the server first starts, or the pin falls back to the
         normal route and the control quietly does nothing;
      2. `up` seeds a NEW run dir from the repo config, so the shim row and
         the admin password must be written into THAT run dir, not an older
         one — and `core.database` resolves DATABASE_URL at import, so the
         environment has to be set BEFORE the first import of it, exactly like
         the harness's own R2/R3 repair;
      3. the server then restarts against the same run dir to see them.
    """
    out.mkdir(parents=True, exist_ok=True)
    script_path = out / "planner_script.json"
    script_path.write_text(json.dumps(script, indent=2))
    shim_port = free_port()
    proc = RIG.start_shim(script_path, shim_port,
                          capture=out / "shim_requests.jsonl")

    r = stack("--world", world, "down")
    print(f"[down] rc={r.returncode}")

    harness: Dict[str, Any] = {"pin_env": dict(pin_env or {})}

    def up(reuse: str = "") -> None:
        cmd_env = dict(harness["pin_env"])
        cmd = ["--world", world, "up", "--backend-port", str(port), "--api-only"]
        if reuse:
            cmd += ["--reuse-run", reuse]
        # `up` refuses while a stack is up, so every launch is down-then-up.
        stack("--world", world, "down")
        rr = stack(*cmd, env=cmd_env)
        if rr.returncode != 0:
            raise SystemExit("preview_stack up failed:\n"
                             + (rr.stdout or "")[-2000:] + (rr.stderr or "")[-2000:])
        for line in (rr.stdout or "").splitlines():
            if any(k in line for k in ("backend :", "world ", "run ")):
                print("   ", line.strip())

    print("  [1/3] fresh run dir, shim already listening")
    up()
    wiring = RIG.point_world_at_shim(world, shim_port)
    print(f"  [2/3] shim registered in the run-dir DB as {wiring['provider_key']}"
          f"  (pin {wiring['pin']})")
    # The EDIT-PLAN structured call is routed by BPC unless pinned. Left
    # unpinned it ranks the workspace's real BYOK providers, which answer from
    # the network — the injection then never happens and the case measures a
    # model the script never served. The pin is the harness's documented knob
    # (ATOM_ASYNC_EDIT_PLAN_MODEL, forwarded through SERVER_ENV_WHITELIST).
    harness["pin_env"]["ATOM_ASYNC_EDIT_PLAN_MODEL"] = wiring["pin"]
    print("  [3/3] restart on the same run dir so discovery sees it")
    up(reuse=wiring["run_dir"])

    state = json.loads((WORLDS / world / "preview_stack.json").read_text())
    db = str(Path(state["db_path"]).resolve())
    if "acceptance_worlds" not in db:
        raise SystemExit(f"refusing to touch a database outside a world: {db}")
    # A fresh run dir re-seeds the world admin from the repo config, so login
    # would 401. The value is never printed or written to evidence. The engine
    # is already bound to this run dir by point_world_at_shim, which set
    # DATABASE_URL before the first import of core.database.
    from core.database import engine as _engine
    from sqlalchemy import text as _text
    with _engine.begin() as conn:
        who = conn.execute(_text(
            "SELECT id FROM users WHERE email=:e"), {"e": LOGIN_EMAIL}).scalar()
    if not who:
        raise SystemExit(f"{LOGIN_EMAIL} not present in this world")
    from core.auth import get_password_hash
    from core.database import get_db_session
    from core.models import User
    with get_db_session() as s:
        u = s.query(User).filter(User.email == LOGIN_EMAIL).first()
        u.hashed_password = get_password_hash(LOGIN_PASSWORD)
        s.commit()
    return {"shim_port": shim_port, "shim_proc": proc, "wiring": wiring,
            "db": db, "state": state, "port": port, "script": str(script_path),
            "pin_env": harness["pin_env"]}


def login(base: str, port: int) -> Dict[str, Any]:
    import httpx
    r = httpx.post(f"{base}/api/auth/login", trust_env=False, timeout=60,
                   headers={"Origin": f"http://localhost:{port}"},
                   json={"username": LOGIN_EMAIL, "password": LOGIN_PASSWORD})
    payload = r.json() if r.status_code == 200 else {}
    tok = payload.get("access_token")
    if not tok:
        raise SystemExit(f"login failed: {r.status_code} {r.text[:200]}")
    uid = (payload.get("user") or {}).get("id")
    if not uid:
        uid = httpx.get(f"{base}/api/auth/me", trust_env=False, timeout=60,
                        headers={"Authorization": f"Bearer {tok}"}).json().get("id")
    if not uid:
        raise SystemExit("could not resolve the authenticated user id")
    return {"token": tok, "user_id": uid}


def seed(base: str, port: int, tok: str, uid: str, marker: str) -> Dict[str, Any]:
    """Create the probe canvas through the SUPPORTED APIs only."""
    import uuid
    import httpx
    canvas_id = str(uuid.uuid4())
    hdr = {"Authorization": f"Bearer {tok}",
           "Origin": f"http://localhost:{port}"}
    r = httpx.post(f"{base}/api/canvas/email/create", headers=hdr,
                   trust_env=False, timeout=120,
                   json={"subject": SUBJECT, "recipients": ["steve@example.com"],
                         "canvas_id": canvas_id, "user_id": uid})
    if r.status_code != 200:
        raise SystemExit(f"canvas create failed: {r.status_code} {r.text[:300]}")
    made = (r.json() or {}).get("canvas_id") or canvas_id
    body_html = (f"<div><p>Quote for Steve</p><p><b>{BODY_OLD}</b></p>"
                 f"<p>Rows 1-5 are the requested machines.</p>"
                 f"<!-- {marker} --></div>")
    content = {"to": "steve@example.com", "cc": "",
               "subject": SUBJECT, "body": body_html}
    u = httpx.put(f"{base}/api/canvas/{made}", headers=hdr, trust_env=False,
                  timeout=120, params={"canvas_type": "email"}, json=content)
    if u.status_code != 200:
        raise SystemExit(f"canvas content PUT failed: {u.status_code} {u.text[:300]}")
    return {"canvas_id": made, "content": content, "seeded_via": "api"}


def baseline(db: str, canvas_id: str) -> Dict[str, Any]:
    """Post-seed baseline. The timestamp is the boundary every later count is
    measured against, taken AFTER the seed's own create/update rows."""
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        last = con.execute(
            "SELECT max(created_at) FROM canvas_audit WHERE canvas_id=?",
            (canvas_id,)).fetchone()[0]
    finally:
        con.close()
    state = canvas_state(db, canvas_id)
    return {"after": last or "1970-01-01", "audit_count": state["audit_count"],
            "subject": state["subject"], "content_keys": state["content_keys"],
            "body_has_old": state["body_has_old"]}


def post_turn(base: str, port: int, tok: str, uid: str, message: str,
              session: str, canvas: Dict[str, Any]) -> Dict[str, Any]:
    import httpx
    hdr = {"Authorization": f"Bearer {tok}", "Origin": f"http://localhost:{port}"}
    body = {"message": message, "session_id": session, "user_id": uid,
            "context": {"canvas": {"id": canvas["canvas_id"]},
                        "canvas_content": canvas["content"],
                        "canvas_type": "email",
                        "canvas_title": "planner/apply probe"}}
    r = httpx.post(f"{base}/api/chat/message", headers=hdr, trust_env=False,
                   timeout=1200, json=body)
    try:
        payload = r.json()
    except Exception:
        payload = {"_raw": r.text[:400]}
    ce: Dict[str, Any] = {}
    for cand in (payload.get("canvas_edit"),
                 (payload.get("metadata") or {}).get("canvas_edit"),
                 (payload.get("data") or {}).get("canvas_edit")):
        if isinstance(cand, dict) and cand:
            ce = cand
            break
    return {"status_code": r.status_code, "execution_id": payload.get("execution_id"),
            "session_id": payload.get("session_id"),
            "message": str(payload.get("message") or "")[:900],
            "canvas_edit": ce,
            "intent": payload.get("intent"),
            "response_keys": sorted(payload.keys()) if isinstance(payload, dict) else []}


def log_slice(world: str, offset: int) -> List[str]:
    log = WORLDS / world / "preview_backend.log"
    if not log.exists():
        return []
    return log.read_text(errors="replace")[offset:].splitlines()


def boundary_lines(world: str, offset: int) -> List[str]:
    """Product boundary lines only, with the volatile prefixes stripped."""
    keys = (
        "canvas edit: plan DECLINED", "canvas edit: plan AUTHORIZED",
        "canvas edit: SCHEMA-BOUNDARY", "canvas edit: repair exchange",
        "patch op(s) failed to match", "falling back to a replace-mode re-ask",
        "replace plan recovered via raw-JSON fallback", "consistency repair",
        "canvas edit apply failed", "canvas edit rejected", "canvas edit CONFLICT",
        "canvas edit blocked", "read-back did NOT verify",
        "retrying unpinned", "structured_cascade_exhausted",
        "canvas-edit plan", "canvas edit apply",
    )
    out = []
    for line in log_slice(world, offset):
        if any(k in line for k in keys):
            out.append(line.strip()[:400])
    return out[-90:]


def shim_report(port: int) -> Dict[str, Any]:
    import httpx
    for _ in range(40):
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/log", timeout=10,
                          trust_env=False)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(0.5)
    return {}


def sanity(harness: Dict[str, Any], world: str) -> Dict[str, Any]:
    return {
        "schema": "lane3-planner-apply-probe-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": world,
        "run_dir": harness["state"].get("run_dir"),
        "db_path": harness["db"],
        "port": harness["port"],
        "shim": {"port": harness["shim_port"],
                 "pin": harness["wiring"].get("pin"),
                 "provider_key": harness["wiring"].get("provider_key"),
                 "script": harness["script"]},
        "identity": harness["state"].get("backend_health_identity", {}).get("source_id"),
        "scope": ("ONLY the planner's model response is injected. Auth, "
                  "authorization, reservation, execution claim, store, audit, "
                  "read-back, verification and finalization are real. This is "
                  "EFFECT-LAYER evidence, not evidence that the production "
                  "planner accepts canvas edits."),
    }
