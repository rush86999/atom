#!/usr/bin/env python3
"""Two independent processes submit the same intended mutation. Exactly one wins.

WHAT THIS MEASURES, AND WHERE THE LINE IS
=========================================
The repository already has the cross-process arbiter for this and this probe
exists to hold it to its contract rather than to build a second mechanism:
`core.task_lifecycle._claim_operation_key` inserts a `TaskOperationRecord` under a
UNIQUE (workspace, run, idempotency_key) and lets the DATABASE decide the winner,
because the task's own JSON cannot arbitrate two workers that both read "absent"
before either writes. The key is bound to a canonical payload hash, so the same
key with a different payload is a conflict rather than a silent replay.

Three phases, each with two REAL operating-system processes -- not two threads,
not two coroutines, because a same-process race is decided by a lock the product
does not have:

  A  same key, same payload      -> exactly one winner, one row, one operation
  B  same key, DIFFERENT payload -> still one row; the loser sees a conflict and
                                    mints nothing
  C  the same race over the real HTTP boundary: two clients, one request_id ->
                                    one execution, one delivered answer, and the
                                    loser either waits (202) or replays (200)
                                    with identical bytes

WHERE THE LINE IS, STATED PLAINLY
Phases A and B are measured at the layer that GATES a mutation: the durable
operation claim and the operation materialised in the task JSON. What is NOT
measured here is the canvas-audit row itself -- driving a real canvas edit needs
an accepting planner, which is the provider shim the C16 lane already owns
(`controlled_planner_c16.py` + `provider_shim.py`). Claiming "one audit
attribution" from this probe would be asserting a fact it did not measure, so it
does not: the final integration run folds the shim-driven canvas case in.

    concurrent_claim_probe.py --world <w> --port <p> --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
WORLDS = BACKEND / "data" / "acceptance_worlds"
STACK = BACKEND / "scripts" / "orchestration_acceptance" / "preview_stack.py"
PYTHON = str(BACKEND / "venv314" / "bin" / "python")
sys.path.insert(0, str(BACKEND))

LOGIN_EMAIL = "admin@example.com"
LOGIN_PASSWORD = os.environ.get("LANE3_PREVIEW_PASSWORD") or "preview-only-local-2026"

# The worker script. It imports the WORLD's code with the WORLD's database, so
# the arbiter under test is the one the server runs, not the checkout's.
WORKER = r'''
import hashlib, json, os, sys, uuid
sys.path.insert(0, os.getcwd())
os.environ["DATABASE_URL"] = f"sqlite:///{sys.argv[2]}"

role, db, run_id, key, payload = sys.argv[1:6]

from core.database import get_db_session
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.task_lifecycle import TaskLifecycle

digest = hashlib.sha256(payload.encode()).hexdigest()
tl = TaskLifecycle(
    GoalRunService(workspace_id="default", tenant_id="default",
                   session_factory=get_db_session),
    GoalService(workspace_id="default", tenant_id="default",
                session_factory=get_db_session),
)
mine = str(uuid.uuid4())
out = tl._claim_operation_key(run_id=run_id, idempotency_key=key,
                              payload_sha256=digest, operation_id=mine,
                              operation_type="canvas_edit")
result = {"role": role, "won": out is None, "claim": out,
          "operation_id": mine, "asked_payload_sha256": digest}
if out is None:
    # The winner materialises exactly ONE operation for the key it just claimed.
    try:
        tl._adopt_claimed_operation(
            run_id=run_id,
            claim={"operation_id": mine, "idempotency_key": key},
            op_type="canvas_edit", requested_change=payload,
            parent_operation_id=None)
        result["materialised"] = True
    except Exception as exc:
        result["materialise_error"] = f"{type(exc).__name__}: {exc}"[:200]
print("WORKER_JSON " + json.dumps(result, default=str))
'''


def run_worker(world_dir: Path, db: str, role: str, run_id: str, key: str,
               payload: str, timeout: int = 300) -> Dict[str, Any]:
    env = {k: v for k, v in os.environ.items() if k != "TESTING"}
    env["DATABASE_URL"] = f"sqlite:///{db}"
    proc = subprocess.run(
        [PYTHON, "-c", WORKER, role, db, run_id, key, payload],
        cwd=str(world_dir / "backend_root"), env=env,
        capture_output=True, text=True, timeout=timeout)
    for line in proc.stdout.splitlines():
        if line.startswith("WORKER_JSON "):
            return json.loads(line[len("WORKER_JSON "):])
    return {"role": role, "error": "no worker output", "stdout": proc.stdout[-400:],
            "stderr": proc.stderr[-600:]}


def stack(*args: str, timeout: int = 1800) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "TESTING"}
    return subprocess.run([PYTHON, str(STACK), *args], cwd=str(REPO), env=env,
                          capture_output=True, text=True, timeout=timeout)


def descriptor(world: str) -> Dict[str, Any]:
    return json.loads((WORLDS / world / "launch_descriptor.json").read_text())


def records_for_key(db: str, run_id: str, key: str) -> List[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        try:
            rows = con.execute(
                "SELECT operation_id, idempotency_key, payload_sha256, status, "
                "operation_type FROM task_operation_records "
                "WHERE run_id=? AND idempotency_key=? ORDER BY created_at",
                (run_id, key)).fetchall()
        except sqlite3.OperationalError as exc:
            return [{"error": f"task_operation_records unreadable: {exc}"}]
        return [{"operation_id": r[0], "idempotency_key": r[1],
                 "payload_sha256": r[2], "status": r[3], "operation_type": r[4]}
                for r in rows]
    finally:
        con.close()


def operations_in_task(db: str, run_id: str) -> List[Dict[str, Any]]:
    """The operations materialised in the task's own JSON, by key."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        try:
            rows = con.execute(
                "SELECT parameters FROM goal_runs WHERE id=?", (run_id,)).fetchall()
        except sqlite3.OperationalError:
            return []
        out: List[Dict[str, Any]] = []
        for (blob,) in rows:
            try:
                params = json.loads(blob) if isinstance(blob, str) else (blob or {})
            except (ValueError, TypeError):
                continue
            life = ((params or {}).get("task_lifecycle") or {})
            for op in life.get("operations", []) or []:
                out.append({"operation_id": op.get("operation_id"),
                            "idempotency_key": op.get("idempotency_key"),
                            "status": op.get("status")})
        return out
    finally:
        con.close()


def set_world_password(db_path: str, password: str) -> None:
    """Make the world's admin loggable. One scoped write, value never printed.

    Necessary because `preview_stack up` without `--reuse-run` seeds a NEW run dir
    from the fixture, so the password set in a previous run is not there --
    without this the probe just gets a 401 and reports a race it never ran.
    """
    db = str(Path(db_path).resolve())
    if "acceptance_worlds" not in db:
        raise SystemExit(f"refusing to write outside an acceptance world: {db}")
    os.environ.pop("TESTING", None)
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    os.environ["ATOM_DATA_DIR"] = str(Path(db).parent)
    os.environ["ENVIRONMENT"] = "development"
    from core.auth import get_password_hash
    from core.database import get_db_session
    from core.models import User
    with get_db_session() as session:
        user = session.query(User).filter(User.email == LOGIN_EMAIL).first()
        if user is None:
            raise SystemExit(f"{LOGIN_EMAIL} not present in this world")
        user.hashed_password = get_password_hash(password)
        session.commit()


def http_login(base: str) -> Dict[str, str]:
    import httpx
    r = httpx.post(f"{base}/api/auth/login", trust_env=False, timeout=60,
                   headers={"Origin": base},
                   json={"username": LOGIN_EMAIL, "password": LOGIN_PASSWORD})
    r.raise_for_status()
    token = (r.json() or {}).get("access_token")
    me = httpx.get(f"{base}/api/auth/me", trust_env=False, timeout=60,
                   headers={"Authorization": f"Bearer {token}"})
    me.raise_for_status()
    return {"token": token, "user_id": str((me.json() or {}).get("id"))}


def ask(base: str, token: str, user_id: str, session: str, message: str,
        request_id: str, timeout: int = 420) -> Dict[str, Any]:
    import httpx
    r = httpx.post(f"{base}/api/chat/message", timeout=timeout, trust_env=False,
                   headers={"Authorization": f"Bearer {token}"},
                   json={"message": message, "session_id": session,
                         "user_id": user_id, "request_id": request_id,
                         "context": {"current_page": "/chat",
                                     "conversation_history": []}})
    try:
        return {"status": r.status_code, **r.json()}
    except Exception:
        return {"status": r.status_code, "raw": r.text[:300]}


def executions_for(db: str, session: str) -> List[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, status, input_summary FROM agent_executions "
            "WHERE json_extract(metadata_json, '$.session_id')=? "
            "ORDER BY started_at", (session,)).fetchall()
        return [{"id": r[0], "status": r[1], "input": (r[2] or "")[:60]} for r in rows]
    finally:
        con.close()


def assistant_rows(db: str, session: str) -> List[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, length(content) FROM chat_messages "
            "WHERE conversation_id=? AND role='assistant' ORDER BY created_at",
            (session,)).fetchall()
        return [{"id": r[0], "chars": r[1]} for r in rows]
    finally:
        con.close()


class Report:
    def __init__(self) -> None:
        self.checks: Dict[str, bool] = {}
        self.details: Dict[str, Any] = {}

    def check(self, name: str, ok: Any, detail: Any = None) -> bool:
        ok = bool(ok)
        self.checks[name] = ok
        if detail is not None:
            self.details[name] = detail
        return ok

    @property
    def passed(self) -> int:
        return sum(1 for v in self.checks.values() if v)

    @property
    def total(self) -> int:
        return len(self.checks)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--world", required=True)
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    world_dir = WORLDS / args.world
    base = f"http://127.0.0.1:{args.port}"
    rep = Report()
    timeline: List[Dict[str, Any]] = []

    def mark(event: str, **kw: Any) -> None:
        timeline.append({"at": time.strftime("%H:%M:%S"), "event": event, **kw})
        print(f"  [{time.strftime('%H:%M:%S')}] {event} "
              f"{json.dumps(kw, default=str)[:200]}", flush=True)

    up = stack("--world", args.world, "up", "--api-only", "--backend-port", str(args.port))
    (out_dir / "launch.log").write_text(up.stdout + "\n" + up.stderr)
    if up.returncode != 0:
        print(up.stdout[-2500:], up.stderr[-2500:])
        raise SystemExit("launch failed")
    d = descriptor(args.world)
    db, run_dir = d["db_path"], str(world_dir / "runs" / d["run_id"])
    mark("launched", pid=d["pid"], run_id=d["run_id"])
    set_world_password(db, LOGIN_PASSWORD)

    try:
        # ---------------------------------------------------------- phase A
        # Same key, same payload, two processes. Started together so the race is
        # real: both are in flight before either can answer.
        run_a = f"claim-a-{uuid.uuid4().hex[:8]}"
        key_a = f"idem-{uuid.uuid4().hex[:12]}"
        payload_a = "set the quote validity to 30 days"
        import threading
        results_a: Dict[str, Any] = {}

        def racer(tag: str) -> None:
            results_a[tag] = run_worker(world_dir, db, tag, run_a, key_a, payload_a)

        threads = [threading.Thread(target=racer, args=(t,)) for t in ("p1", "p2")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        rows_a = records_for_key(db, run_a, key_a)
        winners = [k for k, v in results_a.items() if v.get("won")]
        losers = [k for k, v in results_a.items() if not v.get("won")]
        mark("phase A", winners=winners, rows=len(rows_a))
        rep.check("A: exactly one process won the claim", len(winners) == 1,
                  {"results": results_a})
        rep.check("A: the durable record holds exactly ONE row for the key",
                  len(rows_a) == 1, {"rows": rows_a})
        loser_claim_a = results_a[losers[0]].get("claim") if losers else None
        rep.check("A: the loser was handed the WINNER's operation id (so it replays, "
                  "never mints a second effect)",
                  bool(losers) and loser_claim_a is not None and rows_a
                  and loser_claim_a.get("operation_id") == rows_a[0]["operation_id"],
                  {"loser_claim": loser_claim_a, "row": rows_a[0] if rows_a else None,
                   "winner_operation_id": results_a[winners[0]].get("operation_id")
                   if winners else None})

        # ---------------------------------------------------------- phase B
        # Same key, DIFFERENT payload. The key is bound to a payload hash, so the
        # second process must be told it is a conflict -- not handed a replay of
        # an effect it did not ask for.
        run_b = f"claim-b-{uuid.uuid4().hex[:8]}"
        key_b = f"idem-{uuid.uuid4().hex[:12]}"
        results_b: Dict[str, Any] = {}

        def racer_b(tag: str, payload: str) -> None:
            results_b[tag] = run_worker(world_dir, db, tag, run_b, key_b, payload)

        t1 = threading.Thread(target=racer_b, args=("p1", "set validity to 30 days"))
        t2 = threading.Thread(target=racer_b, args=("p2", "set validity to 45 days"))
        t1.start(); t2.start(); t1.join(); t2.join()
        rows_b = records_for_key(db, run_b, key_b)
        claimed_hashes = {r["payload_sha256"] for r in rows_b}
        loser_b = [k for k, v in results_b.items() if not v.get("won")]
        mark("phase B", rows=len(rows_b), hashes=len(claimed_hashes))
        rep.check("B: still exactly ONE row for the key", len(rows_b) == 1,
                  {"rows": rows_b, "results": results_b})
        loser_claim = results_b[loser_b[0]].get("claim") if loser_b else None
        loser_asked = results_b[loser_b[0]].get("asked_payload_sha256") if loser_b else None
        rep.check("B: the loser was handed a DIFFERENT payload hash -- a conflict, not a replay",
                  bool(loser_b) and loser_claim is not None
                  and loser_claim.get("payload_sha256") != loser_asked,
                  {"loser": loser_b, "loser_claim": loser_claim,
                   "asked_hashes": {k: v.get("asked_payload_sha256")
                                    for k, v in results_b.items()},
                   "why": "the key is bound to a canonical payload hash, so a "
                          "different payload under the same key must be reported "
                          "as a conflict rather than served as a replay of an "
                          "effect the loser never asked for"})
        ops_b = operations_in_task(db, run_b)
        rep.check("B: no second operation was materialised for the contested key",
                  len([o for o in ops_b if o.get("idempotency_key") == key_b]) <= 1,
                  {"operations": ops_b, "key": key_b})

        # ---------------------------------------------------------- phase C
        # The same race over the real HTTP boundary.
        auth = http_login(base)
        session = f"claim-http-{uuid.uuid4().hex[:8]}"
        request_id = f"claim-req-{uuid.uuid4().hex[:12]}"
        message = "In one sentence, what is a price list used for?"
        http_results: Dict[str, Any] = {}

        def http_racer(tag: str, msg: str, rid: str) -> None:
            http_results[tag] = ask(base, auth["token"], auth["user_id"], session,
                                    msg, rid)

        h1 = threading.Thread(target=http_racer, args=("p1", message, request_id))
        h2 = threading.Thread(target=http_racer, args=("p2", message, request_id))
        h1.start(); h2.start(); h1.join(); h2.join()
        execs = executions_for(db, session)
        answers = assistant_rows(db, session)
        statuses = sorted(http_results[t].get("status") for t in http_results)
        mark("phase C", statuses=statuses, executions=len(execs), answers=len(answers))
        rep.check("C: exactly ONE execution for the contested request",
                  len(execs) == 1, {"executions": execs, "responses": statuses})
        rep.check("C: exactly ONE delivered answer (no duplicate effect)",
                  len(answers) == 1, {"answers": answers, "responses": statuses})
        rep.check("C: the loser waited or replayed, never re-executed",
                  all(s in (200, 202) for s in statuses) and 200 in statuses,
                  {"statuses": statuses,
                   "bodies": {t: str(http_results[t].get("message") or
                                     http_results[t].get("content") or "")[:120]
                              for t in http_results}})

        # Conflicting payload on the same request id.
        conflict = ask(base, auth["token"], auth["user_id"], session,
                       "In one sentence, what is a bandsaw used for?", request_id)
        execs_after = executions_for(db, session)
        answers_after = assistant_rows(db, session)
        mark("phase C conflict", status=conflict.get("status"),
            executions=len(execs_after), answers=len(answers_after))
        rep.check("C: a different payload under the same request id is refused",
                  conflict.get("status") == 409
                  or conflict.get("error") == "request_id_conflict",
                  {"status": conflict.get("status"),
                   "error": conflict.get("error"),
                   "detail": str(conflict.get("detail"))[:200]})
        rep.check("C: the conflicting payload created NO second execution or answer",
                  len(execs_after) == len(execs) and len(answers_after) == len(answers),
                  {"executions_before": len(execs), "after": len(execs_after),
                   "answers_before": len(answers), "after": len(answers_after)})
    finally:
        if not args.keep:
            stack("--world", args.world, "down")

    verdict = "PASS" if all(rep.checks.values()) else "FAIL"
    payload = {
        "schema": "lane3-concurrent-claim-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": args.world, "backend": base, "run_dir": run_dir, "db": db,
        "launch_identity": {"source_id": None, "pid": d["pid"]},
        "verdict": verdict,
        "checks_passed": rep.passed, "checks_total": rep.total,
        "checks": rep.checks, "details": rep.details, "timeline": timeline,
        "scope_note": "phases A and B measure the durable operation claim, which is "
                      "the layer that gates a mutation. The canvas-audit row itself "
                      "needs an accepting planner (the C16 lane's provider shim) and "
                      "is NOT measured here.",
    }
    (out_dir / "concurrent_claim.json").write_text(json.dumps(payload, indent=1, default=str))
    print(f"\n{rep.passed}/{rep.total} checks -> {out_dir / 'concurrent_claim.json'}")
    for name, ok in rep.checks.items():
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
