# -*- coding: utf-8 -*-
"""Cross-source follow-up scenario driver (2026-09-29 fix verification).

Drives the ORIGINAL incident sequence through the preview stack's PUBLIC
chat API and captures exact IDs for the result package:

  turn 1  the verbatim eight-machine price ask (the stored objective);
  turn 2  "That filename is correct" only if the ask asked for one;
  turn 3  the EXACT failed instruction — check Chandrakant's email and
          the workbook descriptions to find the correct sheet/row.

Verdicts recorded per turn (assertion-free capture where judgment is
needed; hard asserts only where the fix's contract is objective):

  - turn 1 must deliver the workbook prices (positive control: the fix
    must not break the deterministic read lane);
  - turn 3 must NOT be answered by re-running/re-delivering the stored
    price read: no deterministic_delivery, model is not "deterministic",
    and the answer text is not the turn-1 price table again;
  - the run-DB rows (read-only, world-local SQLite) bind every turn to
    its execution id and record what actually ran.

Run against an isolated acceptance world ONLY (the preview stack's run
database — never the live dev DB).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[6] / "backend"

INCIDENT_MSG = (
    "check Chandrakant's email and or description in workbook to find "
    "correct sheet and row from workbook for confirmation")
STORED_ASK = (
    "find the prices of these 8 machines in Consolidated Price List "
    "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
    "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
CONFIRMATION = "That filename is correct"
EIGHT = [
    "No. 381", "U-22", "No. 622", "TK Manual Flanger", "SLE24-16",
    "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]


def _ro_rows(db_path: Path, sql: str, args=()):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        cur = con.execute(sql, args)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


async def main() -> int:
    import asyncio

    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="crosssrc_fix_0929")
    ap.add_argument("--backend-port", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    world = BACKEND / "data" / "acceptance_worlds" / args.world
    stack = json.loads((world / "preview_stack.json").read_text())
    db_path = Path(stack["db_path"])
    cred = json.loads((world / "run_secrets" / "preview_auth.json").read_text())

    base = f"http://127.0.0.1:{args.backend_port}"
    client = httpx.AsyncClient(trust_env=False, timeout=420)

    login = (await client.post(f"{base}/api/auth/login", json={
        "username": cred["email"], "password": cred["password"]})).json()
    token = login.get("access_token") or (login.get("data") or {}).get(
        "access_token")
    if not token:
        print(f"login failed: {json.dumps(login)[:400]}", file=sys.stderr)
        return 2
    headers = {"Authorization": f"Bearer {token}"}
    me = (await client.get(f"{base}/api/auth/me", headers=headers)).json()
    user_id = str(me.get("id") or (me.get("data") or {}).get("id") or "")

    session = f"crosssrc-{int(time.time())}"
    request_ids = {k: f"req-{uuid.uuid4().hex[:12]}" for k in
                   ("ask", "confirm", "incident")}

    async def send(msg: str, key: str):
        t0 = time.time()
        r = (await client.post(
            f"{base}/api/chat/message", headers=headers,
            json={"message": msg, "session_id": session,
                  "user_id": user_id, "request_id": request_ids[key]},
        )).json()
        r["_latency_s"] = round(time.time() - t0, 2)
        return r

    result = {
        "world": args.world,
        "base": base,
        "session_id": session,
        "user_id": user_id,
        "request_ids": request_ids,
        "db_path": str(db_path),
        "turns": [],
    }

    r1 = await send(STORED_ASK, "ask")
    result["turns"].append({"n": 1, "key": "ask", "message": STORED_ASK,
                            "response": r1})
    final1 = r1
    if (r1.get("data") or {}).get("requires_confirmation") or (
            "correct" in str(r1.get("message") or "").lower()
            and "?" in str(r1.get("message") or "")):
        r2 = await send(CONFIRMATION, "confirm")
        result["turns"].append({"n": 2, "key": "confirm",
                                "message": CONFIRMATION, "response": r2})
        final1 = r2

    answer1 = str(final1.get("message") or "")
    found1 = [t for t in EIGHT if t.lower() in answer1.lower()]
    result["control_turn1"] = {
        "execution_id": final1.get("execution_id"),
        "model": final1.get("model"),
        "provider": final1.get("provider"),
        "deterministic_delivery": (final1.get("data") or {}).get(
            "deterministic_delivery"),
        "items_found_in_answer": found1,
        "eight_delivered": len(found1) >= 6,
        "answer_chars": len(answer1),
    }

    r3 = await send(INCIDENT_MSG, "incident")
    answer3 = str(r3.get("message") or "")
    data3 = r3.get("data") or {}
    result["turns"].append({"n": 3, "key": "incident",
                            "message": INCIDENT_MSG, "response": r3})
    # Non-substitution contract (objective): the stored price read must
    # not be the answer to the cross-source request.
    price_table_repeat = (
        "8880" in answer3 and "SLE24-16" in answer3
        and "| " in answer3 and len(
            [t for t in EIGHT if t.lower() in answer3.lower()]) >= 6)
    result["incident_turn"] = {
        "execution_id": r3.get("execution_id"),
        "model": r3.get("model"),
        "provider": r3.get("provider"),
        "deterministic_delivery": data3.get("deterministic_delivery"),
        "intent": r3.get("intent"),
        "answer_chars": len(answer3),
        "price_table_repeat": price_table_repeat,
        "substitution_blocked": (
            not data3.get("deterministic_delivery")
            and r3.get("model") != "deterministic"
            and not price_table_repeat),
        "answer_text": answer3[:6000],
    }

    # Reload persistence + durable binding (read-only, world-local DB).
    await asyncio.sleep(2)
    try:
        msgs = _ro_rows(
            db_path,
            "SELECT id, role, conversation_id, created_at, "
            "length(content) as content_len, metadata_json "
            "FROM chat_messages WHERE conversation_id=? "
            "ORDER BY created_at",
            (session,))
    except Exception as e:  # noqa: BLE001 — capture must not lose the turns
        msgs = [{"query_error": str(e)}]
    try:
        execs = _ro_rows(
            db_path,
            "SELECT id, agent_id, status, created_at, updated_at, "
            "result_summary FROM agent_executions "
            "WHERE id IN (%s)" % ",".join(
                "?" for t in result["turns"]
                if t["response"].get("execution_id")),
            tuple(t["response"]["execution_id"]
                  for t in result["turns"]
                  if t["response"].get("execution_id")) or ("none",))
    except Exception as e:  # noqa: BLE001
        execs = [{"query_error": str(e)}]
    result["durable"] = {
        "chat_message_rows": [
            {k: m[k] for k in ("id", "role", "created_at", "content_len")}
            for m in msgs],
        "agent_execution_rows": execs,
        "incident_message_row_present": any(
            m["role"] == "user" for m in msgs),
    }

    await client.aclose()
    Path(args.out).write_text(json.dumps(result, indent=2, default=str))
    ok = (result["control_turn1"]["eight_delivered"]
          and result["incident_turn"]["substitution_blocked"])
    print(json.dumps({
        "control_eight_delivered": result["control_turn1"]["eight_delivered"],
        "substitution_blocked": result["incident_turn"]["substitution_blocked"],
        "incident_model": result["incident_turn"]["model"],
        "out": args.out}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
