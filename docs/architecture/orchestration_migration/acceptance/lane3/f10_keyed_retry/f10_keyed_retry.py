#!/usr/bin/env python3
"""F10 — keyed retry, payload conflict, and pin survival. API-level, candidate A.

F10 is a claim about the REQUEST KEY, not about the planner: replaying a key
must not create a second execution, a second effect, or a different answer, and
a changed payload under a live key must conflict rather than run again.

Why this can be asserted cheaply
`replay_pin: {"status": "pinned", "durable": true}` appeared in the F02b turn's
own response, so the pin is recorded in the product's answer. The keyed
behaviour is therefore observable from the API alone -- no browser, no WS, no
planner cooperation. The planner's willingness to edit is irrelevant here: a
declined turn is still a turn with an execution, and "no second execution" is
the assertion that matters.

Cases
  F10a  same key + SAME payload   -> identical answer, SAME execution_id,
                                    zero new AgentExecution rows, zero new
                                    canvas_audit rows
  F10b  same key + CHANGED payload -> an explicit conflict, NOT a second run
                                    and NOT a silent overwrite

The live dev DB is never opened.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

BACKEND = Path("/Users/rushiparikh/projects/atom/backend")
sys.path.insert(0, str(BACKEND))

BASE = "http://127.0.0.1:8086"
WORLD = BACKEND / "data" / "acceptance_worlds" / "finish_line"
DB = WORLD / "runs" / "run-cfb0605d01ce" / "data" / "atom.db"

findings: list[dict] = []


def add(name: str, ok: bool, detail: str) -> None:
    findings.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")


def counts() -> dict:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        ex = con.execute("SELECT COUNT(*) FROM agent_executions").fetchone()[0]
        au = con.execute("SELECT COUNT(*) FROM canvas_audit").fetchone()[0]
    finally:
        con.close()
    return {"agent_executions": ex, "canvas_audit": au}


def mint_token() -> tuple[str, str]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.auth import create_access_token
    from core.models import User

    eng = create_engine(f"sqlite:///{DB}")
    with sessionmaker(bind=eng)() as db:
        u = db.query(User).filter(User.email == "admin@example.com").first()
        uid = str(u.id)
    eng.dispose()
    return create_access_token({"sub": uid, "user_id": uid,
                                "email": "admin@example.com",
                                "role": "workspace_admin"}), uid


def send(hdr, user_id, key, message, session_id):
    import httpx
    r = httpx.post(f"{BASE}/api/chat/message", headers=hdr, timeout=300,
                   json={"message": message, "user_id": user_id,
                         "session_id": session_id, "request_id": key,
                         "context": {"current_page": "/chat",
                                     "conversation_history": []}})
    body = {}
    if r.status_code < 400:
        try:
            body = r.json()
        except Exception:
            body = {"_raw": r.text[:500]}
    return r.status_code, body


def main() -> int:
    import httpx

    token, user_id = mint_token()
    hdr = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:3110",
           "Content-Type": "application/json"}

    # A plain question, no canvas: keeps the assertion purely about the key.
    question = "In one sentence, what is a confirmation bias?"
    key = str(uuid.uuid4())
    session_id = "new"

    print(f"[F10a] first send, key={key}")
    before = counts()
    s1, b1 = send(hdr, user_id, key, question, session_id)
    time.sleep(3)
    after1 = counts()
    eid1 = b1.get("execution_id")
    msg1 = (b1.get("message") or "")[:300]
    print(f"   -> {s1} execution_id={eid1} execs {before['agent_executions']}"
          f"->{after1['agent_executions']}")

    add("first send succeeded", s1 < 400, f"HTTP {s1}")
    add("first send produced an execution id", bool(eid1), f"execution_id={eid1}")
    add("first send created exactly one execution",
        after1["agent_executions"] - before["agent_executions"] == 1,
        f"delta={after1['agent_executions'] - before['agent_executions']}")
    # CONTRACT: the pin is reported at ``metadata.replay_pin``, NOT at the top
    # level. The earlier version of this script asserted on ``response["replay_pin"]``,
    # which does not exist, and so reported a product failure that was never
    # real. ``_mark_replay_pin`` writes into the response's ``metadata`` dict
    # (chat_routes.py:1609-1626) precisely because ``model_dump()`` returns a
    # fresh dict that would not carry the marker to the caller.
    pin = ((b1.get("metadata") or {}).get("replay_pin") or {})
    add("first send reports a durable replay pin at metadata.replay_pin",
        pin.get("status") == "pinned" and pin.get("durable") is True,
        f"metadata.replay_pin={json.dumps(pin)[:120]}")
    add("there is no top-level replay_pin field (the contract is metadata-nested)",
        "replay_pin" not in b1,
        f"top_level_keys_has_replay_pin={'replay_pin' in b1}")

    print("\n[F10a] replay: same key, SAME payload")
    s2, b2 = send(hdr, user_id, key, question, session_id)
    time.sleep(3)
    after2 = counts()
    eid2 = b2.get("execution_id")
    msg2 = (b2.get("message") or "")[:300]
    print(f"   -> {s2} execution_id={eid2} execs {after1['agent_executions']}"
          f"->{after2['agent_executions']}")

    add("replay did NOT create a second execution",
        after2["agent_executions"] == after1["agent_executions"],
        f"execs {after1['agent_executions']} -> {after2['agent_executions']}")
    add("replay did NOT create a second effect",
        after2["canvas_audit"] == after1["canvas_audit"],
        f"canvas_audit {after1['canvas_audit']} -> {after2['canvas_audit']}")
    add("replay returned the SAME execution id (original semantics)",
        eid2 == eid1 and bool(eid1), f"first={eid1} replay={eid2}")
    add("replay returned the same answer text", msg2 == msg1,
        f"identical={msg2 == msg1}")
    add("replay is not an error", s2 < 400, f"HTTP {s2}")
    add("replay reports the same session", b2.get("session_id") == b1.get("session_id"),
        f"first={b1.get('session_id')} replay={b2.get('session_id')}")

    print("\n[F10b] same key, CHANGED payload")
    changed = "In one sentence, what is the sunk cost fallacy?"
    s3, b3 = send(hdr, user_id, key, changed, session_id)
    time.sleep(3)
    after3 = counts()
    eid3 = b3.get("execution_id")
    print(f"   -> {s3} execution_id={eid3} execs {after2['agent_executions']}"
          f"->{after3['agent_executions']}")

    add("changed payload under a live key did NOT create a new execution",
        after3["agent_executions"] == after2["agent_executions"],
        f"execs {after2['agent_executions']} -> {after3['agent_executions']}")
    add("changed payload did not silently overwrite the pinned answer",
        eid3 in (eid1, None),
        f"returned execution_id={eid3} (pinned={eid1})")
    add("changed payload was refused or reported as the pinned turn, not a new one",
        s3 >= 400 or eid3 == eid1
        or (b3.get("message") or "") == (b1.get("message") or ""),
        f"HTTP {s3}; replayed_original_text="
        f"{(b3.get('message') or '') == (b1.get('message') or '')}")
    add("changed payload created no extra effect",
        after3["canvas_audit"] == after2["canvas_audit"],
        f"canvas_audit {after2['canvas_audit']} -> {after3['canvas_audit']}")

    out = Path("/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/f10_keyed_retry.json")
    out.write_text(json.dumps({
        "schema": "f10-keyed-retry-v1",
        "candidate": "1a953b58934d-dirty.526a9a7135e8",
        "code_snapshot": "f7bb91218dee27532551c366c5d13d57dda5a46e89088568e0eafb7e8c909ec2",
        "world": "finish_line", "run_dir": "run-cfb0605d01ce", "db": str(DB),
        "configuration": "api-only; lifecycle+M1+M2 on; barrier disarmed; planner unpinned",
        "request_key": key,
        "counts": {"before": before, "after_first": after1,
                   "after_replay": after2, "after_changed": after3},
        "first": {"status": s1, "execution_id": eid1, "message": msg1,
                  "replay_pin": b1.get("replay_pin")},
        "replay": {"status": s2, "execution_id": eid2, "message": msg2},
        "changed": {"status": s3, "execution_id": eid3,
                    "message": (b3.get("message") or "")[:300]},
        "findings": findings,
    }, indent=2, default=str))
    print(f"\nresult -> {out}")
    bad = [f for f in findings if not f["ok"]]
    print(f"\n{len(findings)-len(bad)}/{len(findings)} assertions passed")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
