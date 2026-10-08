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
    pw_file = db.parents[1] / "logs" / "bootstrap_admin_password.txt"
    password = pw_file.read_text().strip() if pw_file.exists() else ""
    if not password:
        raise RuntimeError(
            f"bootstrap admin password not found at {pw_file}")
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
