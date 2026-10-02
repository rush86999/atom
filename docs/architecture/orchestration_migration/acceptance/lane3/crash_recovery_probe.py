#!/usr/bin/env python3
"""Crash recovery: kill the server mid-turn, restart it, and grade what survives.

WHY THIS EXISTS
The read-oriented preview advertises nothing about a mid-answer crash, and the
quickstart says so honestly ("Your machine lost power mid-answer" is untested).
The *mechanism* already exists and is wired at boot --
`core/execution_recovery.reconcile_orphaned_executions` (main_api_app.py step 5)
and `core/async_turn_continuation.notify_recovered_continuations` (step 5b) --
but no artifact in this repo has ever driven a real SIGKILL through it. Unit
tests cannot: they call the function. This probe produces the crash.

WHAT IS ACTUALLY CLAIMED
That a turn interrupted by an uncatchable process death is not left behind as a
ghost, is not reported to the user as a completed answer, and does not wedge the
world or duplicate an execution. It is NOT a claim that interrupted work resumes
-- the module is explicit that it is reconcile-only, deliberately, because
re-entering a crashed run can double-fire side effects.

HOW IT CRASHES
`SIGKILL` to the exact pid the real launcher recorded, mid-turn, while that turn's
execution is observably `running` in the server's own database. The pre-crash
ghost state is read from the database BEFORE the restart, so "recovery happened"
cannot be confused with "the row happened to already be terminal".

WHY A BARRIER MODE EXISTS (2026-09-28)
The 8-item lookup got fast: on the latest run it finished in under 3 s, the
probe never saw a running execution, and it recorded `NO_INTERRUPT.json` — a
harness-timing outcome that measures nothing. Timing a real turn is not a
reproducible way to interrupt one. `--barrier-after-claim` makes it
reproducible on demand: the world is launched with the product's own test-only
barrier armed for this probe's victim session only
(`core/acceptance_barrier`, stage `chat_turn_after_claim`, refused outside an
isolated acceptance world, inert otherwise). The turn's execution row is
committed `running` and the worker parks immediately afterwards, announcing
itself in a file, until the release file appears. The probe waits for THAT
file — not for a database row — proves the process is alive and parked
mid-turn, and only then SIGKILLs it. The barrier only pauses between two steps
that both really happen: it does not answer, finalize, or persist anything, and
the turn would have failed in exactly the same way had it never been parked.

    crash_recovery_probe.py --world <w> --port <p> --out <dir> [--keep]
    crash_recovery_probe.py --world <w> --port <p> --out <dir> \
        --barrier-after-claim
"""
from __future__ import annotations

import argparse
import json
import os
import signal
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

# The product's own barrier, imported for its STAGE NAMES and its path
# arithmetic so the harness and the call site cannot drift on a string. It is
# stdlib-only and does no I/O at import, and this probe never sets
# ATOM_ACCEPTANCE_BARRIER in its own process, so importing it is inert here.
from core import acceptance_barrier as AB  # noqa: E402

LOGIN_EMAIL = "admin@example.com"
LOGIN_PASSWORD = os.environ.get("LANE3_PREVIEW_PASSWORD") or "preview-only-local-2026"

BARRIER_STAGE = AB.STAGE_CHAT_TURN_AFTER_CLAIM
#: The probe's own wait is shorter than the barrier's bounded hold, so a
#: missing arrival is REPORTED as a harness outcome instead of being absorbed
#: by the barrier giving up and letting the turn finish normally.
BARRIER_WAIT_SECONDS = 180.0


def barrier_dir(db: str) -> Path:
    """Where the worker will write this world's barrier files: beside the
    world's own database, i.e. inside that world's run directory."""
    return Path(db).parent / "acceptance_barrier"


def wait_for_barrier_arrival(db: str, expect_pid: int,
                             timeout: float = BARRIER_WAIT_SECONDS,
                             ) -> Optional[Dict[str, Any]]:
    """Block until the serving worker parks at the barrier.

    Deliberately NOT a database poll. A row read can only ever prove the
    state, and the state before and after the intended window is identical
    (the execution row is `running` in both cases) — which is precisely why
    the plain mode could not catch a fast turn. The arrival file is the
    worker stating that it is between the two steps, and it carries the pid,
    so a marker left by any other process is detectable.
    """
    directory = barrier_dir(db)
    deadline = time.time() + timeout
    while time.time() < deadline:
        for arrival in AB.arrived_paths(directory, BARRIER_STAGE):
            try:
                payload = json.loads(arrival.read_text())
            except (ValueError, OSError):
                continue
            if int(payload.get("pid") or 0) == int(expect_pid):
                payload["_file"] = str(arrival)
                return payload
        time.sleep(0.02)
    return None


#: The frozen acceptance ask (acceptance/cases.json `1_initial_request`).
#: Eight real items out of the seeded workbook: long enough to be interrupted,
#: deterministic enough that a completed answer is checkable, and read-only.
LOOKUP = ("find the prices of these 8 machines in Consolidated Price List 2019.xlsx: "
          "No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, "
          "TK Multi Wheel Gang Slitter and GSL48-16")
SMALL = "In one sentence, what is a price list used for?"

#: Markers for the two turns. The interrupted one is locatable in the database
#: by its own session, never by recency.
SESSION_BASELINE = "crash-base-" + uuid.uuid4().hex[:8]
SESSION_VICTIM = "crash-victim-" + uuid.uuid4().hex[:8]
SESSION_AFTER = "crash-after-" + uuid.uuid4().hex[:8]


# --------------------------------------------------------------------- plumbing
def stack(*args: str, env_extra: Optional[Dict[str, str]] = None,
         timeout: int = 1800) -> subprocess.CompletedProcess:
    """Invoke the real launcher. Never reimplement its launch path."""
    env = {k: v for k, v in os.environ.items() if k != "TESTING"}
    env.update(env_extra or {})
    return subprocess.run([PYTHON, str(STACK), *args], cwd=str(REPO), env=env,
                          capture_output=True, text=True, timeout=timeout)


def descriptor(world: str) -> Dict[str, Any]:
    return json.loads((WORLDS / world / "launch_descriptor.json").read_text())


def health(base: str) -> Dict[str, Any]:
    import httpx
    r = httpx.get(f"{base}/api/health", timeout=20, trust_env=False)
    r.raise_for_status()
    return r.json()


def open_ro(db: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def login(base: str) -> Dict[str, str]:
    """Real login. Returns the token AND the caller's user id.

    The user id is read from `/api/auth/me` rather than hardcoded: the fixture
    is refrozen per world, so a copied constant is a guess, and a wrong one is
    indistinguishable from a turn that simply produced no execution.
    """
    import httpx
    r = httpx.post(f"{base}/api/auth/login", trust_env=False, timeout=60,
                   headers={"Origin": base},
                   json={"username": LOGIN_EMAIL, "password": LOGIN_PASSWORD})
    r.raise_for_status()
    token = (r.json() or {}).get("access_token")
    if not token:
        raise SystemExit("login returned no access_token")
    me = httpx.get(f"{base}/api/auth/me", trust_env=False, timeout=60,
                   headers={"Authorization": f"Bearer {token}"})
    me.raise_for_status()
    user_id = (me.json() or {}).get("id") or (me.json() or {}).get("user_id")
    if not user_id:
        raise SystemExit("/api/auth/me returned no user id")
    return {"token": token, "user_id": str(user_id)}


def ask(base: str, token: str, session: str, message: str, user_id: str,
        request_id: Optional[str] = None, timeout: int = 420) -> Dict[str, Any]:
    import httpx
    body: Dict[str, Any] = {"message": message, "session_id": session,
                            "user_id": user_id,
                            "context": {"current_page": "/chat",
                                        "conversation_history": []}}
    if request_id:
        body["request_id"] = request_id
    r = httpx.post(f"{base}/api/chat/message", json=body, timeout=timeout,
                   trust_env=False, headers={"Authorization": f"Bearer {token}"})
    try:
        return {"status": r.status_code, **r.json()}
    except Exception:
        return {"status": r.status_code, "raw": r.text[:300]}


def set_world_password(db_path: str, password: str) -> None:
    """One credential write, scoped inside the world. Never logged."""
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


# ------------------------------------------------------------- durable readers
def executions_for(db: str, session: str) -> List[Dict[str, Any]]:
    """Every AgentExecution row this session's turns produced, oldest first.

    `agent_executions` has no `session_id` column; the link is
    `metadata_json.session_id`, so the filter is a JSON extraction and never a
    recency window. Selecting by "the newest row" is how a previous runner ended
    up handing a turn the previous turn's record.
    """
    con = open_ro(db)
    try:
        rows = con.execute(
            "SELECT id, status, error_message, metadata_json, started_at, "
            "completed_at, triggered_by FROM agent_executions "
            "WHERE json_extract(metadata_json, '$.session_id')=? "
            "ORDER BY started_at", (session,)).fetchall()
    except sqlite3.OperationalError as exc:
        raise SystemExit(f"cannot read executions by session: {exc}")
    finally:
        con.close()
    out = []
    for r in rows:
        meta: Any = None
        if r[3]:
            try:
                meta = json.loads(r[3]) if isinstance(r[3], str) else r[3]
            except (ValueError, TypeError):
                meta = None
        out.append({"id": r[0], "status": r[1], "error_message": r[2],
                    "metadata": meta, "started_at": r[4], "completed_at": r[5],
                    "triggered_by": r[6]})
    return out


def running_execution(db: str, session: str) -> Optional[Dict[str, Any]]:
    for row in executions_for(db, session):
        if str(row["status"]).lower() == "running":
            return row
    return None


def assistant_rows(db: str, session: str,
                   execution_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Assistant rows for a session, optionally narrowed to ONE execution.

    Scoped by execution when one is given, because the session is reused: after
    recovery this probe deliberately sends a NEW turn in the same session, and an
    unscoped read then finds that legitimate answer and reports the interrupted
    turn as "finished". Identity, not recency -- the same rule the rest of this
    file follows.
    """
    con = open_ro(db)
    try:
        sql = ("SELECT id, content, metadata_json, created_at FROM chat_messages "
               "WHERE conversation_id=? AND role='assistant'")
        args: List[Any] = [session]
        if execution_id:
            sql += " AND json_extract(metadata_json, '$.execution_id')=?"
            args.append(execution_id)
        sql += " ORDER BY created_at"
        out = []
        for r in con.execute(sql, args):
            out.append({"id": r[0], "chars": len(r[1] or ""),
                        "content_head": (r[1] or "")[:200], "created_at": r[3]})
        return out
    finally:
        con.close()


def second_process_sweep(world_dir: Path, db: str) -> Dict[str, Any]:
    """Run the boot crash-recovery sweep from a genuinely separate process.

    Not a mock and not an in-process call: a new interpreter, with its own PID
    and its own ownership token, importing the SAME world code and opening the
    SAME database file. That is the only way to show the sweep can tell "another
    live worker owns this row" from "this row is a ghost" -- an in-process call
    would be `self`, which is a different branch.
    """
    script = (
        "import json, os, sys\n"
        "sys.path.insert(0, os.getcwd())\n"
        "from core.execution_recovery import reconcile_orphaned_executions\n"
        "out = reconcile_orphaned_executions()\n"
        "out['pid'] = os.getpid()\n"
        "print('SWEEP_JSON ' + json.dumps(out, default=str))\n"
    )
    env = {k: v for k, v in os.environ.items() if k != "TESTING"}
    env["DATABASE_URL"] = f"sqlite:///{db}"
    env["PYTHONPATH"] = str(world_dir / "backend_root")
    proc = subprocess.run([PYTHON, "-c", script], cwd=str(world_dir / "backend_root"),
                          env=env, capture_output=True, text=True, timeout=300)
    for line in proc.stdout.splitlines():
        if line.startswith("SWEEP_JSON "):
            return json.loads(line[len("SWEEP_JSON "):])
    return {"error": "no sweep output", "stdout": proc.stdout[-500:],
            "stderr": proc.stderr[-800:]}


def keyed_state(db: str, request_id: str) -> Dict[str, Any]:
    """The durable keyed-request row, by request id.

    `state` is the transport's own vocabulary: in_progress, completed, crashed.
    Read directly rather than inferred from the HTTP answer, because the whole
    point of these checks is that the answer and the durable state must agree.
    """
    con = open_ro(db)
    try:
        row = con.execute(
            "SELECT state, execution_id, error FROM chat_request_records "
            "WHERE request_id=? ORDER BY created_at DESC LIMIT 1",
            (request_id,)).fetchone()
    except sqlite3.OperationalError as exc:
        return {"error": f"chat_request_records unreadable: {exc}"}
    finally:
        con.close()
    if row is None:
        return {"request_id": request_id, "state": None,
                "note": "no keyed record exists for this request id"}
    return {"request_id": request_id, "state": row[0], "execution_id": row[1],
            "error": row[2]}


def claim_rows(db: str) -> List[Dict[str, Any]]:
    con = open_ro(db)
    try:
        try:
            rows = con.execute("SELECT continuation_id, session_id "
                               "FROM async_continuation_claims").fetchall()
        except sqlite3.OperationalError:
            return []
        return [{"continuation_id": r[0], "session_id": r[1]} for r in rows]
    finally:
        con.close()


# ---------------------------------------------------------------------- grading
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


def history_text(base: str, token: str, session: str) -> str:
    import httpx
    r = httpx.get(f"{base}/api/chat/history/{session}", timeout=60,
                  trust_env=False, headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        return ""
    try:
        return json.dumps(r.json())
    except Exception:
        return r.text


def interrupted_turn_claimed_success(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """An assistant row that reads as a finished answer to the interrupted ask.

    A crash-recovery bug that matters is a *false success*: the user reloads and
    sees a confident answer for a turn that never finished. So this is graded on
    the content, not on the absence of an exception.
    """
    for row in rows:
        head = (row.get("content_head") or "").lower()
        if not head:
            continue
        failure_words = ("failed", "interrupted", "restarted", "crashed",
                         "did not complete", "could not complete", "incomplete",
                         "error", "try again")
        if any(w in head for w in failure_words):
            return None
        if row.get("chars", 0) > 40:
            return row
    return None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--world", required=True)
    ap.add_argument("--port", type=int, default=8076)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep", action="store_true",
                    help="leave the world running after the probe")
    ap.add_argument("--interrupt-timeout", type=int, default=180)
    ap.add_argument("--barrier-after-claim", action="store_true",
                    help="reproducible version of the mid-turn interrupt. The "
                         "world is launched with the product's own test-only "
                         "barrier armed for THIS probe's victim session only "
                         "(core/acceptance_barrier, stage chat_turn_after_claim, "
                         "refused outside an isolated acceptance world, inert "
                         "otherwise). The turn's execution row is committed "
                         "'running' and the worker parks immediately afterwards "
                         "until a release file appears; the probe waits for the "
                         "ARRIVAL FILE, proves the worker is alive and parked "
                         "mid-turn, and then SIGKILLs. Needed because the 8-item "
                         "lookup now finishes in under 3 s, so the plain mode "
                         "records NO_INTERRUPT instead of testing anything.")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rep = Report()
    base = f"http://127.0.0.1:{args.port}"
    world_dir = WORLDS / args.world
    timeline: List[Dict[str, Any]] = []

    def mark(event: str, **kw: Any) -> None:
        timeline.append({"at": time.strftime("%H:%M:%S"), "event": event, **kw})
        print(f"  [{time.strftime('%H:%M:%S')}] {event} "
              f"{json.dumps(kw, default=str)[:160]}", flush=True)

    # The barrier's session narrowing is a launch-time variable, so the world
    # is armed before it starts. SESSION_VICTIM is a module constant, so this
    # is known before the launch; the baseline, after-crash and fresh-turn
    # sessions are NOT matched, which is what keeps the barrier from pausing
    # the very turns the probe needs to complete.
    barrier_env: Dict[str, str] = {}
    if args.barrier_after_claim:
        barrier_env = {
            AB.ENV_STAGE: BARRIER_STAGE,
            AB.ENV_MATCH: SESSION_VICTIM,
            AB.ENV_TIMEOUT: "600",
        }

    # ---------------------------------------------------------------- launch
    print("== launch (real launcher, api-only: no frontend is needed to crash a turn)")
    up = stack("--world", args.world, "up", "--api-only",
               "--backend-port", str(args.port), env_extra=barrier_env)
    (out_dir / "launch_up.log").write_text(up.stdout + "\n" + up.stderr)
    if up.returncode != 0:
        print(up.stdout[-3000:]); print(up.stderr[-3000:])
        raise SystemExit("launch failed")
    d = descriptor(args.world)
    db, pid, run_dir = d["db_path"], d["pid"], str(WORLDS / args.world / "runs" / d["run_id"])
    mark("launched", pid=pid, run_id=d["run_id"], port=args.port,
         barrier=(d.get("effective_flags") or {}).get("ATOM_ACCEPTANCE_BARRIER"))

    ident_before = health(base).get("identity", {})
    ident_after: Optional[Dict[str, Any]] = None
    rep.check("launched identity is this world",
              str(ident_before.get("cwd", "")).endswith(f"{args.world}/backend_root"),
              {"source_id": ident_before.get("source_id"),
               "database": ident_before.get("database")})
    rep.check("identity database is the db this probe reads",
              Path(str(ident_before.get("database", ""))).resolve() == Path(db).resolve(),
              {"identity_db": ident_before.get("database"), "probe_db": db})

    set_world_password(db, LOGIN_PASSWORD)
    auth = login(base)
    token, user_id = auth["token"], auth["user_id"]

    try:
        # ------------------------------------------------- baseline (must survive)
        base_resp = ask(base, token, SESSION_BASELINE, SMALL, user_id)
        base_ok = base_resp.get("status") == 200
        rep.check("a pre-crash turn was delivered", base_ok,
                  {"status": base_resp.get("status")})
        baseline_answer = history_text(base, token, SESSION_BASELINE)

        # ------------------------------------------- interrupt a turn in flight
        victim_request_id = f"crash-req-{uuid.uuid4().hex[:12]}"
        import threading
        outcome: Dict[str, Any] = {}

        def fire() -> None:
            try:
                outcome["resp"] = ask(base, token, SESSION_VICTIM, LOOKUP, user_id,
                                      request_id=victim_request_id, timeout=120)
            except Exception as exc:      # the server is killed mid-flight on purpose
                outcome["error"] = f"{type(exc).__name__}: {exc}"[:200]

        th = threading.Thread(target=fire, daemon=True)
        th.start()

        seen: Optional[Dict[str, Any]] = None
        arrival: Optional[Dict[str, Any]] = None
        if args.barrier_after_claim:
            # DETERMINISTIC. The worker parks itself between the committed
            # `running` execution row and the turn's finalization, and says so
            # in a file. Waiting on that file is also the only way to tell
            # "mid-turn" from "about to start": the durable state is `running`
            # in both cases, which is why the plain mode could not catch a turn
            # that finishes in under three seconds.
            arrival = wait_for_barrier_arrival(db, pid)
            rep.check("the serving worker parked mid-turn at the acceptance "
                      "barrier",
                      arrival is not None,
                      {"stage": BARRIER_STAGE, "expected_pid": pid,
                       "waited_for": str(barrier_dir(db)),
                       "barrier_armed": (d.get("effective_flags") or {}).get(
                           "ATOM_ACCEPTANCE_BARRIER"),
                       "thread_alive": th.is_alive()})
            if arrival is None:
                # No arrival marker is a harness-timing outcome, not a product
                # result, and must be recorded as one.
                (Path(args.out) / "NO_INTERRUPT.json").write_text(json.dumps(
                    {"schema": "lane3-crash-no-interrupt-v1",
                     "reason": f"the worker never parked at barrier "
                               f"{BARRIER_STAGE!r} within "
                               f"{BARRIER_WAIT_SECONDS:.0f}s",
                     "mode": "barrier-after-claim",
                     "baseline_status": base_resp.get("status"),
                     "outcome": {k: str(v)[:600] for k, v in outcome.items()},
                     "world": args.world, "backend": base},
                    indent=1, default=str))
                raise SystemExit("cannot interrupt: no barrier arrival")
            seen = next((r for r in executions_for(db, SESSION_VICTIM)
                         if r["id"] == (arrival.get("context") or {}).get(
                             "execution_id")), None) or \
                running_execution(db, SESSION_VICTIM)
            rep.check("the barrier parked the RECORDED serving worker, on the "
                      "victim turn's own execution row",
                      seen is not None
                      and int(arrival.get("pid") or 0) == int(pid)
                      and str((arrival.get("context") or {}).get("session_id")
                              or "") == SESSION_VICTIM,
                      {"arrival": arrival, "serving_pid": pid,
                       "session": SESSION_VICTIM,
                       "execution_id": (seen or {}).get("id"),
                       "why": "a marker from another pid or another session would "
                              "mean the kill is not landing mid-turn"})
            # The worker is parked, so this is a real observation rather than a
            # race: the process is ALIVE and the turn is unfinished.
            try:
                os.kill(int(pid), 0)
                alive_parked = True
            except OSError:
                alive_parked = False
            rep.check("the worker is ALIVE while parked (a stall in a live "
                      "process is a different case, and the boot sweep "
                      "correctly refuses to touch it)",
                      alive_parked, {"pid": pid})
            mark("barrier arrival", pid=arrival.get("pid"),
                 stage=arrival.get("stage"),
                 context=arrival.get("context"))
        else:
            deadline = time.time() + args.interrupt_timeout
            while time.time() < deadline:
                seen = running_execution(db, SESSION_VICTIM)
                if seen:
                    break
                if not th.is_alive():
                    break
                time.sleep(0.05)
        rep.check("the victim turn was observably RUNNING before the kill",
                  seen is not None,
                  {"execution_id": (seen or {}).get("id"),
                   "thread_alive": th.is_alive(),
                   "outcome": {k: str(v)[:300] for k, v in outcome.items()}})
        if seen is None:
            mark("no running execution observed; the turn never got slow enough",
                 outcome={k: str(v)[:400] for k, v in outcome.items()},
                 baseline_status=base_resp.get("status"))
            # Leave a record of WHY, rather than only a traceback: a turn that
            # completed before it could be interrupted is a harness-timing
            # outcome, and it must not be mistaken for a product result.
            (Path(args.out) / "NO_INTERRUPT.json").write_text(json.dumps(
                {"schema": "lane3-crash-no-interrupt-v1",
                 "reason": "no running execution was observed within "
                           f"{args.interrupt_timeout}s; the turn was never slow "
                           "enough to interrupt",
                 "baseline_status": base_resp.get("status"),
                 "outcome": {k: str(v)[:600] for k, v in outcome.items()},
                 "world": args.world, "backend": base},
                indent=1, default=str))
            raise SystemExit("cannot interrupt: no running execution was observed")
        victim_id = seen["id"]
        mark("victim execution running", execution_id=victim_id)

        # A retry WHILE the turn is genuinely in flight. The expectation is
        # derived from the durable state, not chosen in advance: read whether the
        # execution is still running, then demand the matching answer. A 202 is
        # only correct while the turn is unfinished, and only if the body says
        # so in those words.
        still_running = running_execution(db, SESSION_VICTIM) is not None
        inflight_retry = ask(base, token, SESSION_VICTIM, LOOKUP, user_id,
                             request_id=victim_request_id, timeout=60)
        if still_running:
            rep.check("a retry while the turn is unfinished answers 202 in-progress",
                      inflight_retry.get("status") == 202
                      and inflight_retry.get("error_code") == "request_in_progress"
                      and "in progress" in str(inflight_retry.get("message", "")).lower(),
                      {"status": inflight_retry.get("status"),
                       "error_code": inflight_retry.get("error_code"),
                       "durable_state": "execution running"})
        else:
            rep.check("a retry after the turn finished replays the same answer",
                      inflight_retry.get("status") == 200,
                      {"status": inflight_retry.get("status"),
                       "durable_state": "execution already terminal"})

        # A SECOND PROCESS, mid-turn. The sweep is a pure function of the
        # database, so running it from another process against the same file is
        # exactly what a sibling worker's boot does -- and it is the case that
        # decides whether this slice is safe to ship. A sweep that reconciles by
        # status alone will mark the live turn below it failed, and nothing will
        # report the contradiction: the turn keeps running and then tries to
        # finalize into a row that now says it failed.
        second = second_process_sweep(world_dir, db)
        after_second = executions_for(db, SESSION_VICTIM)
        row_after_second = next((r for r in after_second if r["id"] == victim_id), None)
        rep.check("a second process's boot sweep leaves the live turn running",
                  row_after_second is not None
                  and str(row_after_second["status"]).lower() == "running",
                  {"second_process": second,
                   "status_after": row_after_second["status"] if row_after_second else None})
        rep.check("the second process reported it as owned by a LIVE process",
                  int(second.get("agent_untouched_live") or 0) >= 1
                  and int(second.get("agent_recovered") or 0) == 0
                  and int(second.get("agent_unknown_owner") or 0) == 0,
                  {"agent_untouched_live": second.get("agent_untouched_live"),
                   "agent_recovered": second.get("agent_recovered"),
                   "agent_unknown_owner": second.get("agent_unknown_owner"),
                   "pid": second.get("pid"),
                   "note": "untouched-live, not untouched-unknown: an "
                           "unverifiable owner must not be conflated with a "
                           "verified live one"})
        mark("second-process sweep ran", **{
            k: second.get(k) for k in ("pid", "agent_recovered",
                                       "agent_untouched_live")})

        # ------------------------------------------------------------ the crash
        os.kill(int(pid), signal.SIGKILL)
        for _ in range(100):
            try:
                os.kill(int(pid), 0)
                time.sleep(0.1)
            except OSError:
                break
        alive = True
        try:
            os.kill(int(pid), 0)
        except OSError:
            alive = False
        rep.check("the process is gone (SIGKILL, no graceful shutdown)",
                  not alive, {"pid": pid, "signal": "SIGKILL"})
        mark("killed", pid=pid)

        ghost = executions_for(db, SESSION_VICTIM)
        ghost_row = next((r for r in ghost if r["id"] == victim_id), None)
        rep.check("BEFORE any restart the interrupted execution is still 'running'",
                  ghost_row is not None and str(ghost_row["status"]).lower() == "running",
                  {"status": ghost_row["status"] if ghost_row else None,
                   "note": "this is the ghost-run state; without it, nothing below "
                           "proves anything about recovery"})
        assistant_before = assistant_rows(db, SESSION_VICTIM)
        rep.check("no finished answer exists for the interrupted turn",
                  interrupted_turn_claimed_success(assistant_before) is None,
                  {"assistant_rows": assistant_before})
        mark("ghost state read", executions=len(ghost),
             assistant_rows=len(assistant_before))

        # ------------------------------------------------------------- recovery
        down = stack("--world", args.world, "down")
        (out_dir / "launch_down.log").write_text(down.stdout + "\n" + down.stderr)
        back = stack("--world", args.world, "up", "--api-only", "--backend-port",
                     str(args.port), "--reuse-run", run_dir)
        (out_dir / "launch_restart.log").write_text(back.stdout + "\n" + back.stderr)
        if back.returncode != 0:
            print(back.stdout[-3000:]); print(back.stderr[-3000:])
            raise SystemExit("restart failed")
        d2 = descriptor(args.world)
        ident_after = health(base).get("identity", {})
        rep.check("restarted against the SAME run dir and database",
                  d2["db_path"] == db and d2["run_id"] == d["run_id"],
                  {"before": {"run_id": d["run_id"], "db": db},
                   "after": {"run_id": d2["run_id"], "db": d2["db_path"]}})
        mark("restarted", pid=d2["pid"], source_id=ident_after.get("source_id"))

        after = executions_for(db, SESSION_VICTIM)
        row = next((r for r in after if r["id"] == victim_id), None)
        rep.check("the interrupted execution is no longer 'running'",
                  row is not None and str(row["status"]).lower() != "running",
                  {"status": row["status"] if row else None})
        recovery = ((row or {}).get("metadata") or {}).get("recovery") if row else None
        rep.check("it is marked as CRASH-recovered, not a genuine failure",
                  bool(recovery and recovery.get("crashed")),
                  {"recovery": recovery, "error_message": (row or {}).get("error_message")})
        rep.check("it was reconciled from a VERIFIED dead owner",
                  bool(recovery) and recovery.get("owner_state") in ("dead", "self"),
                  {"owner_state": (recovery or {}).get("owner_state"),
                   "why": "'unknown' means the owner could not be established, "
                          "and reconciling on that is how a live turn gets "
                          "failed; it must be left alone"})
        rep.check("the restart ran with the barrier DISARMED",
                  (d2.get("effective_flags") or {}).get(
                      "ATOM_ACCEPTANCE_BARRIER") in ("(disarmed)", "", None),
                  {"effective_flags": d2.get("effective_flags", {}),
                   "why": "a barrier still armed during recovery would let this "
                          "probe's own seam, not the product, decide when "
                          "recovery finished"})

        # THE KEYED REQUEST, PER DURABLE STATE. Before the fix this probe graded
        # the retry as "any of {200, 202, 409} with a body", which accepts
        # contradictory outcomes: 202 and a completed replay say opposite things
        # about the same turn. The expectation now follows the state:
        #
        #   execution terminal + key crashed -> 409 request_crashed, definitively
        #   202 is now WRONG: the turn is not in progress any more
        #   200 is also WRONG: nothing completed, so there is nothing to replay
        key_state = keyed_state(db, victim_request_id)
        rep.check("the keyed record is terminal 'crashed', not in progress",
                  key_state.get("state") == "crashed", key_state)
        executions_before_retry = len(executions_for(db, SESSION_VICTIM))
        retry = ask(base, token, SESSION_VICTIM, LOOKUP, user_id,
                    request_id=victim_request_id)
        executions_after_retry = len(executions_for(db, SESSION_VICTIM))
        # The 409 body is UNWRAPPED by the API layer: `error` and `request_id`
        # are top-level, not nested under `detail` (measured against the live
        # candidate: `{"error": "request_id_conflict", ...}`). Reading
        # `detail["error"]` is why an earlier revision of this check reported a
        # correct 409 as a failure.
        retry_code = retry.get("error") or (
            (retry.get("detail") or {}).get("error")
            if isinstance(retry.get("detail"), dict) else None)
        rep.check("the keyed retry creates NO new execution",
                  executions_after_retry == executions_before_retry,
                  {"status": retry.get("status"),
                   "executions_before": executions_before_retry,
                   "executions_after": executions_after_retry})
        rep.check("the keyed retry is refused 409 request_crashed (not 202, not a replay)",
                  retry.get("status") == 409 and retry_code == "request_crashed"
                  and "did not complete" in str(retry.get("detail", "")).lower(),
                  {"status": retry.get("status"), "error_code": retry_code,
                   "detail": str(retry.get("detail"))[:220],
                   "raw_keys": sorted(retry.keys()),
                   "why_not_202": "the sweep marked the execution failed, so the "
                                  "turn is not in progress; an indefinite "
                                  "in-progress answer is the absence of a policy",
                   "why_not_200": "nothing completed, so there is no pinned "
                                  "response and replaying one would be a lie"})
        rows_before_retry = assistant_rows(db, SESSION_VICTIM, victim_id)
        rep.check("the crashed key was not re-executed into a new delivery",
                  len(assistant_rows(db, SESSION_VICTIM, victim_id)) == len(rows_before_retry),
                  {"assistant_rows_before": len(rows_before_retry),
                   "after": len(assistant_rows(db, SESSION_VICTIM, victim_id))})

        fresh_id = f"crash-req-{uuid.uuid4().hex[:12]}"
        fresh = ask(base, token, SESSION_VICTIM, LOOKUP, user_id, request_id=fresh_id)
        rep.check("a NEW request id in the same session runs a real turn",
                  fresh.get("status") == 200
                  and str(fresh.get("content") or fresh.get("message") or "").strip() != "",
                  {"status": fresh.get("status"),
                   "head": str(fresh.get("content") or fresh.get("message") or "")[:160]})

        rep.check("recovery did not invent a second execution",
                  len([r for r in after if r["id"] == victim_id]) == 1
                  and len(after) == len(ghost),
                  {"before": len(ghost), "after": len(after)})

        log_text = (world_dir / "preview_backend.log").read_text(errors="replace")
        rep.check("the boot sweep says it ran (independent of the row)",
                  "Crash recovery: reconciled" in log_text,
                  {"matched": "Crash recovery: reconciled" in log_text})

        claims = claim_rows(db)
        rep.check("no stale claim points at the dead execution",
                  all(c.get("continuation_id") != victim_id for c in claims),
                  {"claims": claims})

        # Scoped to the interrupted execution: a LATER legitimate turn in the
        # same session must not be read as this turn's answer.
        assistant_after = assistant_rows(db, SESSION_VICTIM, victim_id)
        rep.check("recovery did not present the interrupted turn as a finished answer",
                  interrupted_turn_claimed_success(assistant_after) is None,
                  {"assistant_rows_for_this_execution": assistant_after,
                   "all_rows_in_session": len(assistant_rows(db, SESSION_VICTIM))})

        # ------------------------------------------- the world is not wedged
        after_resp = ask(base, token, SESSION_AFTER, SMALL, user_id)
        rep.check("a NEW turn works after the crash",
                  after_resp.get("status") == 200,
                  {"status": after_resp.get("status")})

        # ------------------------------- a keyed retry must not double-execute
        executions_before_retry = len(executions_for(db, SESSION_VICTIM))
        retry = ask(base, token, SESSION_VICTIM, LOOKUP, user_id,
                   request_id=victim_request_id)
        executions_after_retry = len(executions_for(db, SESSION_VICTIM))
        # ------------------------------------------ nothing pre-crash was lost
        baseline_after = history_text(base, token, SESSION_BASELINE)
        rep.check("the pre-crash answer is still returned after recovery",
                  bool(baseline_after) and baseline_after == baseline_answer,
                  {"chars": len(baseline_after), "unchanged": baseline_after == baseline_answer})
    finally:
        if not args.keep:
            stack("--world", args.world, "down")

    verdict = "PASS" if all(rep.checks.values()) else "FAIL"
    payload = {
        "schema": "lane3-crash-recovery-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": args.world,
        "backend": base,
        "mode": "barrier-after-claim" if args.barrier_after_claim else "timed",
        "barrier": {"stage": BARRIER_STAGE, "armed": bool(barrier_env),
                    "env": barrier_env,
                    "confined_to": "acceptance_worlds (refused elsewhere)"},
        "identity_before": ident_before,
        "identity_after": ident_after,
        "run_dir": run_dir,
        "db": db,
        "verdict": verdict,
        "checks_passed": rep.passed,
        "checks_total": rep.total,
        "checks": rep.checks,
        "details": rep.details,
        "timeline": timeline,
        "scope_note": "the barrier is a PAUSE between two steps that both "
                      "really happen -- the committed `running` execution row "
                      "and the turn's finalization. It answers nothing, "
                      "finalizes nothing and persists nothing.",
    }
    (out_dir / "crash_recovery.json").write_text(json.dumps(payload, indent=1, default=str))
    print(f"\n{rep.passed}/{rep.total} checks -> {out_dir / 'crash_recovery.json'}")
    for name, ok in rep.checks.items():
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
