#!/usr/bin/env python3
"""Shared trial library for the Brennan six-case release suite (Agent C).

Conventions (fixed for the release):
- Every chat turn goes through public POST /api/chat/message with a
  client-minted request_id. Same key is reused ONLY for network retries
  of the same turn; any rephrase mints a new key and is logged as a
  separate attempt. No invisible retries: every attempt is recorded.
- Operator rephrase / answer-seeding / tool-select / state-repair /
  manual delivery marks the trial ASSISTED with the reason. Genuine
  business clarifications (answering the assistant's questions,
  authorizing the draft when the case requires it) are expected case
  input, counted separately, never assistance.
- DB reads are sqlite3-CLI SELECTs only (mode=ro URI). Never the ORM
  against the live DB. Nothing here writes except the product itself
  responding to the posted turns (chat rows, jobs, episodes) and the
  results JSON.
- --dry-run performs fixture/contract checks with ZERO posted turns.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def code_identity(driver_file: Path) -> Dict[str, str]:
    repo = BACKEND.parent

    def _run(*argv: str) -> str:
        try:
            out = subprocess.run(list(argv), cwd=str(repo),
                                 capture_output=True, text=True,
                                 timeout=15).stdout.strip()
            return out or "unknown"
        except Exception:
            return "unknown"

    try:
        driver_sha = sha256_file(driver_file)
    except Exception:
        driver_sha = "unknown"
    return {
        "commit": _run("git", "rev-parse", "HEAD"),
        "dirty_tracked": _run("git", "status", "--short",
                              "--untracked-files=no"),
        "driver_sha256": driver_sha,
    }


def sqlite_select(db: Path, sql: str,
                  params: tuple = ()) -> List[tuple]:
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def mint_admin_token(db: Path) -> Tuple[str, str]:
    """Read the admin user row, mint a JWT locally. No DB writes.

    DEPRECATED for live trials (owner directive 2026-10-08): a restarted
    server generates a fresh SECRET_KEY, so locally minted JWTs decode
    as 401 and invalidate the trial. Use real_admin_login."""
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    from scripts.workbook_read_replay import mint_token
    token, uid = mint_token()
    if not token or not uid:
        raise RuntimeError("token mint failed (no admin@example.com?)")
    return token, uid


def real_admin_login(base: str, db: Path) -> Tuple[str, str]:
    """POST /api/auth/login as the seeded admin — the REAL endpoint, the
    same token a browser session gets. The password comes from the
    bootstrap file the app seeded (0600, gitignored); no credentials are
    ever written into results files or logs."""
    import httpx

    rows = sqlite_select(
        db, "SELECT email FROM users WHERE email LIKE 'admin%' "
            "ORDER BY created_at LIMIT 1")
    email = rows[0][0] if rows else "admin@example.com"
    # The seeded bootstrap password goes stale once the owner rotates it;
    # the acceptance password file (0600, gitignored alongside logs/)
    # holds the current one. Neither is ever written into results.
    candidates = [
        db.parents[1] / "logs" / "acceptance_admin_password.txt",
        db.parents[1] / "logs" / "bootstrap_admin_password.txt",
    ]
    password = next(
        (p.read_text().strip() for p in candidates
         if p.exists() and p.read_text().strip()), "")
    if not password:
        raise RuntimeError(
            "no admin password file under backend/logs/ "
            "(acceptance_admin_password.txt or bootstrap_admin_password.txt)")
    r = httpx.post(
        f"{base}/api/auth/login",
        json={"email": email, "username": email, "password": password},
        timeout=30, trust_env=False)
    doc = r.json() if r.status_code == 200 else {}
    token = doc.get("access_token") or doc.get("token")
    user_id = None
    if token:
        uid_rows = sqlite_select(
            db, "SELECT id FROM users WHERE email = ?", (email,))
        user_id = uid_rows[0][0] if uid_rows else None
    if not token or not user_id:
        raise RuntimeError(
            f"real login failed (http {r.status_code})")
    return token, user_id


def full_agent_id(db: Path, short: str = "9837ec71") -> str:
    rows = sqlite_select(
        db, "SELECT id FROM agent_registry WHERE id LIKE ?",
        (short + "%",))
    if not rows:
        raise RuntimeError(f"trained agent {short} not found")
    return rows[0][0]


def server_identity(base: str) -> Dict[str, Any]:
    import httpx
    try:
        r = httpx.get(f"{base}/api/health", timeout=10, trust_env=False)
        doc = r.json() if r.status_code == 200 else {}
    except Exception as exc:
        return {"reachable": False,
                "error": f"{type(exc).__name__}: {exc}"}
    ident = (doc.get("identity") or {}) if isinstance(doc, dict) else {}
    return {"reachable": True, "status": doc.get("status"),
            "pid": ident.get("pid"),
            "started_at": ident.get("started_at"),
            "git_commit": ident.get("git_commit"),
            "cwd": ident.get("cwd")}


def post_turn(base: str, token: str, message: str, user_id: str,
              session_id: Optional[str], agent_id: str,
              request_id: str,
              context: Optional[Dict[str, Any]] = None,
              timeout_s: float = 600.0) -> Dict[str, Any]:
    import httpx
    payload: Dict[str, Any] = {
        "message": message, "user_id": user_id,
        "session_id": session_id, "agent_id": agent_id,
        "request_id": request_id,
    }
    if context:
        payload["context"] = context
    t0 = time.monotonic()
    try:
        r = httpx.post(f"{base}/api/chat/message",
                       headers={"Authorization": f"Bearer {token}"},
                       json=payload, timeout=timeout_s, trust_env=False)
        dt = time.monotonic() - t0
        try:
            body = r.json()
        except Exception:
            body = {"_raw": r.text[:500]}
        return {"http": r.status_code, "seconds": round(dt, 1),
                "body": body}
    except Exception as exc:
        return {"http": None, "seconds": round(time.monotonic() - t0, 1),
                "transport_error": f"{type(exc).__name__}: {exc}"}


def job_for_session(db: Path, sid: str) -> Optional[Dict[str, Any]]:
    rows = sqlite_select(
        db, "SELECT id, status, parameters FROM goal_runs "
            "WHERE json_extract(parameters,"
            "'$.task_lifecycle.conversation_id')=?", (sid,))
    if not rows:
        return None
    jid, status, params = rows[0]
    try:
        ops = (json.loads(params).get("task_lifecycle") or {}).get(
            "operations") or []
    except Exception:
        ops = []
    return {"run_id": jid, "status": status, "ops": ops}


def chat_rows(db: Path, sid: str) -> List[Dict[str, Any]]:
    rows = sqlite_select(
        db, "SELECT role, content, metadata_json FROM chat_messages "
            "WHERE conversation_id=? ORDER BY created_at, rowid", (sid,))
    out = []
    for role, content, meta in rows:
        try:
            m = json.loads(meta) if meta else {}
        except Exception:
            m = {"_raw": str(meta)[:200]}
        out.append({"role": role, "content": content or "", "meta": m})
    return out


def canvas_audit_updates(db: Path, canvas_id: str,
                         since: Optional[str] = None) -> List[tuple]:
    if since:
        return sqlite_select(
            db, "SELECT action_type, created_at FROM canvas_audit "
                "WHERE canvas_id=? AND action_type='update' "
                "AND created_at>? ORDER BY created_at",
            (canvas_id, since))
    return sqlite_select(
        db, "SELECT action_type, created_at FROM canvas_audit "
            "WHERE canvas_id=? AND action_type='update' "
            "ORDER BY created_at", (canvas_id,))


def history_texts(base: str, token: str, sid: str) -> List[str]:
    """Assistant texts via the public history API (reload/delivery proof:
    what a fresh client receives must equal what the turns delivered)."""
    import httpx
    r = httpx.get(f"{base}/api/chat/history/{sid}",
                  headers={"Authorization": f"Bearer {token}"},
                  timeout=30, trust_env=False)
    doc = r.json()
    out = []
    for m in (doc.get("messages") or []):
        if m.get("role") == "assistant":
            out.append(str((m.get("response") or {}).get("message")
                           or m.get("content") or ""))
    return out


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())


# ---------------------------------------------------------------------------
# Authoritative canvas projection
# ---------------------------------------------------------------------------
# `canvases.content` is NOT the state a user sees. It is the ACCEPTED
# snapshot: update_canvas_content deliberately does not mirror a
# pending_review row into it (docstring: "Pending content remains readable
# from the audit trail but is not mirrored into the accepted
# `canvases.content` snapshot"). The audit trail IS the source of truth —
# tools.canvas_crud_tool.read_canvas says so and builds the public
# GET /api/canvas/{id} response from it.
#
# A preservation assertion computed from `canvases.content` therefore proves
# nothing about what the operator sees: on a canvas whose newest write is
# still under review the snapshot holds the pre-edit body and reports the
# edit as "not preserved", while the browser renders the edit correctly.
# Observed live on fork 2233f463 (2026-10-08): the accepted snapshot still
# read $8,880.00 with an empty header while the API served $8,984.00 with
# subject + cc filled.
#
# Everything below reads sqlite in mode=ro only. No ORM, no writes.

CANVAS_EVENT_ACTIONS = ("email_send", "email_send_attempt")


def canvas_projection(db: Path, canvas_id: str) -> Dict[str, Any]:
    """The authoritative canvas state: the same projection the public canvas
    API serves (``tools.canvas_crud_tool.read_canvas``), reimplemented as
    read-only sqlite SELECTs.

    Projection order, mirroring read_canvas exactly:

      1. newest ``canvas_audit`` row (``created_at DESC, id DESC``)
      2. if that row carries no ``content``/``data`` key it is an EVENT
         stamp (send attempt, attach, …): scan back over the 10 rows
         beneath it for the newest one that does carry a body
      3. only if NO content-bearing row exists fall back to the
         ``canvases.content`` column (legacy canvases predating the trail)
      4. email draft-state read: a served dict whose ``body`` is blank while
         ``details["draft"]["body"]`` is not means the draft IS the body
      5. ``coerce_email_canvas`` unless the type is user-pinned

    Also carries the review-state: ``review_status`` from the row that
    supplied the body, so a caller can tell "the accepted snapshot moved"
    from "a proposal is readable but not yet accepted".
    """
    import json as _json

    from core.chat_draft_classifier import coerce_email_canvas

    rows = sqlite_select(
        db, "SELECT id, action_type, canvas_type, details_json, created_at "
            "FROM canvas_audit WHERE canvas_id=? "
            "ORDER BY created_at DESC, id DESC LIMIT 11", (canvas_id,))
    if not rows:
        return {"success": False, "error": f"Canvas {canvas_id} not found",
                "canvas_id": canvas_id}

    def _details(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            return _json.loads(raw)
        except Exception:  # noqa: BLE001 — a malformed row must not kill a read
            return {}

    newest_id, newest_action, newest_type, newest_raw, newest_at = rows[0]
    if newest_action == "delete":
        return {"success": False, "deleted": True,
                "error": "Canvas has been deleted", "canvas_id": canvas_id}

    details = _details(newest_raw)
    audit_canvas_type = newest_type
    content_audit_id, content_at = newest_id, newest_at

    def _body_of(d: Dict[str, Any]) -> tuple:
        if "content" in d:
            return d.get("content"), True
        if "data" in d:
            return d.get("data"), True
        return None, False

    raw_content, has_key = _body_of(details)
    if raw_content is None and not has_key:
        # EVENT stamp — walk back to the newest row that carries a body.
        for rid, ract, rtype, rraw, rat in rows[1:11]:
            rd = _details(rraw)
            cand, cand_has = _body_of(rd)
            if not cand_has:
                continue
            if details.get("type_pinned"):
                rd = {**rd, "type_pinned": details["type_pinned"]}
            details = rd
            raw_content = cand
            audit_canvas_type = rtype
            content_audit_id, content_at = rid, rat
            break

    source = "audit"
    if raw_content is None and not has_key:
        # LEGACY: no content-bearing row anywhere in the recent trail.
        snap = sqlite_select(
            db, "SELECT content FROM canvases WHERE id=?", (canvas_id,))
        if snap and snap[0][0] is not None:
            raw = snap[0][0]
            try:
                raw_content = _json.loads(raw) if isinstance(raw, str) else raw
            except Exception:  # noqa: BLE001
                raw_content = raw
            source = "snapshot"
        content_audit_id, content_at = None, None

    content = raw_content if raw_content is not None else details

    # EMAIL DRAFT-STATE READ (mirrors read_canvas): a blank served body with
    # a non-empty details["draft"]["body"] means the draft IS the content.
    try:
        draft = details.get("draft")
        if (
            isinstance(content, dict)
            and isinstance(draft, dict)
            and isinstance(content.get("body"), str)
            and not content.get("body").strip()
            and str(draft.get("body") or "").strip()
        ):
            content = {
                **content,
                "body": draft.get("body"),
                "subject": content.get("subject") or draft.get("subject") or "",
                "to": content.get("to") or ", ".join(draft.get("to_emails") or []),
            }
            source = "audit+draft"
    except Exception:  # noqa: BLE001 — read normalization only
        pass

    pinned = bool(details.get("type_pinned"))
    if pinned:
        canvas_type = audit_canvas_type
    else:
        canvas_type, content = coerce_email_canvas(audit_canvas_type, content)

    body = content.get("body") if isinstance(content, dict) else str(content or "")
    text = content if isinstance(content, str) else _json.dumps(content)

    snap_row = sqlite_select(
        db, "SELECT content FROM canvases WHERE id=?", (canvas_id,))
    snapshot_raw = snap_row[0][0] if snap_row else ""
    try:
        snapshot_obj = (_json.loads(snapshot_raw)
                        if isinstance(snapshot_raw, str) and snapshot_raw
                        else snapshot_raw)
    except Exception:  # noqa: BLE001
        snapshot_obj = snapshot_raw
    snapshot_text = (snapshot_raw if isinstance(snapshot_raw, str)
                     else _json.dumps(snapshot_obj))

    return {
        "success": True,
        "canvas_id": canvas_id,
        "content": content,
        "text": text,
        "body": body or "",
        "to": (content.get("to") if isinstance(content, dict) else "") or "",
        "cc": (content.get("cc") if isinstance(content, dict) else "") or "",
        "subject": (content.get("subject") if isinstance(content, dict) else "") or "",
        "canvas_type": canvas_type,
        "title": details.get("title"),
        "action_type": newest_action,
        "audit_id": content_audit_id,
        "operation_id": details.get("operation_id"),
        "review_status": details.get("review_status", "unknown"),
        "created_at": content_at,
        "source": source,
        "type_pinned": pinned,
        "snapshot_text": snapshot_text,
        "diverges_from_snapshot": snapshot_text != text,
    }
