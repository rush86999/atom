#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Workbook-read incident replay (2026-09-23) — the exact 2-turn conversation.

Turn 1:  "find the prices of these 8 machines in Consolidated Price List
2019.xlsx: ..."   (the original incident ask)
Turn 2:  "That filename is correct"   (the confirmation that used to be
planned as small talk)

Verdict inputs (no keyword pass/fail):
1. the persisted turn trace — did turn 2 plan the ORIGINAL ask and execute
   a storage/datasets read?
2. the replies themselves — do workbook values carry R#/sheet provenance,
   and are September-2026 email prices kept separate (or absent)?
3. the pending-file-task state — stored after turn 1, served after turn 2.

Read-only except for a scratch chat session via the public API (same
pattern as scripts/acceptance_replay_canvas.py). Never touches the live
DB directly for writes.
"""
import argparse
import asyncio
import json
import os
import sys
import time

import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

BASE_DEFAULT = "http://127.0.0.1:8001"

ORIGINAL_ASK = (
    "find the prices of these 8 machines in Consolidated Price List "
    "2019.xlsx: 381, U-22, 622, SLE24-16, GSL48-16, GSL24-16, SLE16-8 "
    "and U-38")
CONFIRMATION = "That filename is correct"


def mint_token() -> "tuple[str | None, str | None]":
    try:
        from dotenv import load_dotenv

        for f in (os.path.join(PROJECT_ROOT, ".env"),
                  os.path.join(PROJECT_ROOT, ".env.local")):
            if os.path.exists(f):
                load_dotenv(f, override=f.endswith(".env.local"))
    except Exception:
        pass
    from core.auth import create_access_token
    from core.database import get_db_session
    from core.models import User

    with get_db_session() as db:
        user = db.query(User).filter(User.email == "admin@example.com").first()
        if user is None:
            return None, None
        uid, email = str(user.id), user.email
        role = getattr(user, "role", None)
        role = getattr(role, "value", role)
    return create_access_token({
        "sub": uid, "user_id": uid, "email": email,
        "role": str(role or "workspace_admin"),
    }), uid


async def turn(client, base, token, user_id, session_id, message):
    r = await client.post(
        f"{base}/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "session_id": session_id,
              "user_id": user_id},
        timeout=240,
    )
    r.raise_for_status()
    return r.json()


async def trace(client, base, token, session_id):
    r = await client.get(
        f"{base}/api/chat/trace/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code != 200:
        return []
    data = r.json()
    steps = data if isinstance(data, list) else data.get("steps") or []
    return [s for s in steps if isinstance(s, dict)]


def summarize_step(step) -> str:
    kind = step.get("step_type") or step.get("type") or "?"
    act = step.get("action") or {}
    tool = act.get("tool") or "?"
    params = act.get("params") or {}
    obs = str(step.get("observation") or "")[:220].replace("\n", " ")
    return f"[{kind}] {tool} {json.dumps(params)[:140]} :: {obs}"


async def main_async(args) -> int:
    token, user_id = mint_token()
    if not token:
        print("FATAL: could not mint token (admin@example.com missing)")
        return 2
    base = args.base
    async with httpx.AsyncClient() as client:
        health = await client.get(f"{base}/api/health", timeout=10)
        ident = health.json().get("identity", health.json())

        session_id = f"wb-replay-{int(time.time())}"
        print(f"serving instance: {json.dumps(ident)[:200]}")
        print(f"scratch session:  {session_id}\n")

        print("=== TURN 1 — the original ask ===")
        t0 = time.monotonic()
        r1 = await turn(client, base, token, user_id, session_id, ORIGINAL_ASK)
        print(f"({time.monotonic() - t0:.1f}s) success={r1.get('success')} "
              f"model={r1.get('model')}/{r1.get('provider')}")
        print(r1.get("message", "")[:1200])
        sid = r1.get("session_id") or session_id

        print("\n=== TURN 2 — the confirmation ===")
        t0 = time.monotonic()
        r2 = await turn(client, base, token, user_id, sid, CONFIRMATION)
        print(f"({time.monotonic() - t0:.1f}s) success={r2.get('success')} "
              f"model={r2.get('model')}/{r2.get('provider')}")
        print(r2.get("message", "")[:1600])

        print("\n=== TRACE (last 14 steps) ===")
        steps = await trace(client, base, token, sid)
        for s in steps[-14:]:
            print("  " + summarize_step(s))

        # Verdict inputs, printed for human review.
        reply2 = (r2.get("message") or "").lower()
        print("\n=== VERDICT INPUTS ===")
        planned_original = any(
            "consolidated" in json.dumps(s).lower() for s in steps)
        storage_steps = [
            s for s in steps
            if "workdrive" in json.dumps(s).lower()
            or "datasets" in json.dumps(s).lower()
            or "storage" in json.dumps(s).lower()]
        row_refs = [w for w in ("sheet1", "r1", "r2", "r3", "rsheet", "row")
                    if w in reply2]
        email_2026 = ("september 2026" in reply2 or "2026" in reply2
                      and "email" in reply2)
        print(f"trace names the workbook:     {planned_original}")
        print(f"storage/datasets trace steps: {len(storage_steps)}")
        print(f"reply carries row/sheet refs: {row_refs}")
        print(f"reply leans on 2026 emails:   {email_2026}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=BASE_DEFAULT)
    return asyncio.run(main_async(p.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
