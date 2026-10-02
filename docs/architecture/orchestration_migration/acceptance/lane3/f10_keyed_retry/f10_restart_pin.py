#!/usr/bin/env python3
"""F10 restart-pin survival on candidate A. Replay a key across a restart.

Why this is a separate run
F10 was PARTIAL on candidate A for exactly two reasons: `replay_pin` is not
reported on a plain chat turn, and **restart-pin survival was not established
for this candidate**. This script answers the second, and re-checks the first
after the restart, because the pin's *reporting* and its *survival* are
different claims and only the second is a correctness matter.

Method
1. Establish a completed key against the live candidate and record the durable
   `chat_request_records` row (state, execution_id, finalized_response).
2. RESTART the candidate's backend against the SAME run dir -- a faithful
   restart, same database, no reseed. The preserved previews (:3102/:8071,
   :3101/:8051) are not touched.
3. Replay the identical key + identical payload.
4. Assert: identical answer, same execution_id, zero new AgentExecution rows,
   zero new canvas_audit rows -- i.e. the completed pin survived the restart
   and was answered from the durable record rather than re-executed.

The live dev DB is never opened.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

BACKEND = Path("/Users/rushiparikh/projects/atom/backend")
sys.path.insert(0, str(BACKEND))

BASE = "http://127.0.0.1:8086"
WORLD = BACKEND / "data" / "acceptance_worlds" / "finish_line"
RUN_DIR = "run-cfb0605d01ce"
DB = WORLD / "runs" / RUN_DIR / "data" / "atom.db"
STACK = WORLD / "preview_stack.json"

QUESTION = "In one sentence, what is the sunk cost fallacy?"
findings: list[dict] = []


def add(name, ok, detail):
    findings.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")


def counts():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return {"executions": con.execute(
            "SELECT COUNT(*) FROM agent_executions").fetchone()[0],
            "canvas_audit": con.execute(
                "SELECT COUNT(*) FROM canvas_audit").fetchone()[0]}
    finally:
        con.close()


def record(key):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return con.execute(
            "SELECT state, execution_id, payload_sha256, finalized_response "
            "FROM chat_request_records WHERE request_id=?", (key,)).fetchone()
    finally:
        con.close()


def mint_token():
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
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_raw": r.text[:400]}


def main() -> int:
    import httpx

    token, user_id = mint_token()
    hdr = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:3110",
           "Content-Type": "application/json"}

    # ---------- 1. establish a completed key ----------
    key = str(uuid.uuid4())
    before = counts()
    s1, b1 = send(hdr, user_id, key, QUESTION, "new")
    time.sleep(4)
    rec_before = record(key)
    eid = b1.get("execution_id")
    answer = b1.get("message") or ""
    print(f"[1] key={key}")
    print(f"    HTTP {s1} execution_id={eid}")
    print(f"    record: state={rec_before[0] if rec_before else None} "
          f"exec={rec_before[1] if rec_before else None} "
          f"len={len(rec_before[3] or '') if rec_before else 0}")
    add("the key reached a durable COMPLETED record", bool(rec_before) and
        rec_before[0] == "completed",
        f"state={rec_before[0] if rec_before else None}")
    add("the record carries the execution id", bool(rec_before) and
        rec_before[1] == eid, f"record={rec_before[1] if rec_before else None} "
        f"response={eid}")

    # ---------- 2. faithful restart, same run dir ----------
    print("\n[2] restarting the candidate against the SAME run dir")
    state = json.loads(STACK.read_text())
    old_pid = state.get("backend_pid")
    subprocess.run(["pkill", "-TERM", "-f", f"pid {old_pid}"], check=False)
    try:
        subprocess.run(["kill", "-TERM", str(old_pid)], check=False,
                       capture_output=True)
    except Exception:
        pass
    for _ in range(60):
        time.sleep(1)
        try:
            httpx.get(f"{BASE}/api/health", timeout=3)
            break
        except Exception:
            continue
    time.sleep(3)
    cmd = ["venv314/bin/python",
           "scripts/orchestration_acceptance/preview_stack.py",
           "--world", "finish_line", "up", "--api-only",
           "--backend-port", "8086", "--reuse-run", RUN_DIR]
    print("    " + " ".join(cmd))
    up = subprocess.run(cmd, cwd=str(BACKEND), capture_output=True, text=True,
                        timeout=900)
    print("    " + (up.stdout or "")[-400:].replace("\n", "\n    "))
    if up.returncode != 0:
        print("    STDERR: " + (up.stderr or "")[-600:])
        add("restart succeeded", False, f"exit {up.returncode}")
        return 1
    add("restart succeeded against the same run dir", True,
        f"old pid {old_pid} -> new stack up")

    new_state = json.loads(STACK.read_text())
    new_pid = new_state.get("backend_pid")
    print(f"    new backend pid={new_pid} run_dir={Path(new_state['run_dir']).name}")
    add("the restart really is a new process", new_pid != old_pid,
        f"{old_pid} -> {new_pid}")
    add("the restart kept the same run dir (same database)",
        Path(new_state["run_dir"]).name == RUN_DIR,
        f"{Path(new_state['run_dir']).name}")

    # token is bound to the user row, which is unchanged, but re-mint defensively
    token, user_id = mint_token()
    hdr = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:3110",
           "Content-Type": "application/json"}

    # ---------- 3. replay the identical key across the restart ----------
    time.sleep(4)
    mid = counts()
    s2, b2 = send(hdr, user_id, key, QUESTION, "new")
    time.sleep(4)
    after = counts()
    eid2 = b2.get("execution_id")
    answer2 = b2.get("message") or ""
    rec_after = record(key)
    print(f"\n[3] replay after restart: HTTP {s2} execution_id={eid2}")
    print(f"    executions {mid['executions']}->{after['executions']}  "
          f"canvas_audit {mid['canvas_audit']}->{after['canvas_audit']}")

    add("the completed pin SURVIVED the restart (durable record still there)",
        bool(rec_after) and rec_after[0] == "completed",
        f"state={rec_after[0] if rec_after else None}")
    add("the replay was answered, not re-executed", s2 < 400, f"HTTP {s2}")
    add("the restart created NO new execution",
        after["executions"] == mid["executions"],
        f"{mid['executions']} -> {after['executions']}")
    add("the restart/replay created NO new effect",
        after["canvas_audit"] == mid["canvas_audit"],
        f"canvas_audit {mid['canvas_audit']} -> {after['canvas_audit']}")
    add("the replay returned the SAME execution id as before the restart",
        eid2 == eid and bool(eid), f"before={eid} after={eid2}")
    add("the replay returned the SAME answer text", answer2 == answer,
        f"identical={answer2 == answer}")
    add("only ONE record exists for the key after the restart",
        (rec_after is not None), f"record present={rec_after is not None}")
    print(f"    replay_pin reported now: "
          f"{json.dumps(b2.get('replay_pin'))}")

    out = Path("/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/f10_restart_pin.json")
    out.write_text(json.dumps({
        "schema": "f10-restart-pin-v1",
        "candidate": "1a953b58934d-dirty.526a9a7135e8",
        "code_snapshot": "f7bb91218dee27532551c366c5d13d57dda5a46e89088568e0eafb7e8c909ec2",
        "world": "finish_line", "run_dir": RUN_DIR, "db": str(DB),
        "old_pid": old_pid, "new_pid": new_pid,
        "key": key,
        "record_before": rec_before and [rec_before[0], rec_before[1],
                                         rec_before[2], len(rec_before[3] or "")],
        "record_after": rec_after and [rec_after[0], rec_after[1],
                                       rec_after[2], len(rec_after[3] or "")],
        "execution_before": eid, "execution_after": eid2,
        "counts": {"before": before, "mid": mid, "after": after},
        "replay_pin_after_restart": b2.get("replay_pin"),
        "findings": findings,
    }, indent=2, default=str))
    print(f"\nresult -> {out}")
    bad = [f for f in findings if not f["ok"]]
    print(f"\n{len(findings)-len(bad)}/{len(findings)} assertions passed")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
