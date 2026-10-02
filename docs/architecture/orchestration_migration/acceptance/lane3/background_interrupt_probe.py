#!/usr/bin/env python3
"""Kill the serving worker during an in-flight BACKGROUND continuation.

WHY THIS CASE EXISTS SEPARATELY FROM THE CHAT-TURN CRASH
The chat-turn crash probe proves the boot sweep reconciles a dead process's
running execution. That is not the same claim. A background continuation has
extra obligations this case exists to measure:

  * its durable row is a `triggered_by='continuation'` AgentExecution, so the
    ownership rules apply to it exactly as they do to any other;
  * it may have ALREADY APPLIED its effect before the kill, and the recovery
    must reconcile that without applying it a second time -- a resumed-looking
    retry here would be a duplicated mutation on a user's canvas, which is the
    one thing the whole write path exists to avoid;
  * and the user-visible outcome must stay truthful afterwards.

A stall in a LIVE process is deliberately NOT this case: the owner is alive, so
the sweep declines to touch the row, and treating that as a recovery failure
would be measuring the wrong thing. The kill has to be a real SIGKILL of the
pid the launcher recorded, which is why the serving worker's identity is read
from the launch descriptor rather than assumed.

REUSED, NOT REBUILT
The accepting-planner shim, the budget arithmetic, the canvas seeding and the
durable readers all come from the C16 lane's harness
(`controlled_planner_c16.py`), imported as a library. The only injected thing is
still the planner's model response.

WHY A BARRIER MODE EXISTS (2026-09-28)
The `--kill-after-effect` mode polls for the operation-linked audit row and then
kills. Measured, that window is ~20 ms (audit row committed 10:12:53.334944,
continuation `completed_at` 10:12:53.354743), and seizing SQLite's write lock
after the effect is *visible* is too late: a reader can only see the audit row
once that commit landed, by which time the terminal record has already been
written. So that mode reports `the terminal record had NOT been written` = FAIL
and then measures the ordinary completed case instead of the interrupted one.

`--barrier-after-effect` makes the window deterministic instead of racing for
it. The world is launched with the product's own test-only barrier armed
(`core/acceptance_barrier`, stage `continuation_after_effect`, confined to an
isolated acceptance world and inert otherwise). The worker signals arrival at
the barrier and parks there: the mutation has committed, the readback/D0 gates
have run, and the durable terminal record has NOT been written. This probe
waits for the ARRIVAL FILE (not for a database row), asserts the state from
inside that window, and only then SIGKILLs. Nothing about the product's
behaviour is changed by the barrier -- it only pauses between two steps that
both really happen.

    background_interrupt_probe.py --world <w> --port <p> --out <dir>
    background_interrupt_probe.py --world <w> --port <p> --out <dir> \
        --barrier-after-effect
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
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
sys.path.insert(0, str(HERE))

import controlled_planner_c16 as c16  # noqa: E402  (the C16 lane's harness)

# The product's own barrier, imported for its STAGE NAMES and its path
# arithmetic so the harness and the call site cannot drift on a string. It is
# stdlib-only and does no I/O at import, and this probe never sets
# ATOM_ACCEPTANCE_BARRIER in its own process, so importing it is inert here.
from core import acceptance_barrier as AB  # noqa: E402

INTERACTIVE_BUDGET = 60.0
STALL_SECONDS = 40.0
BARRIER_STAGE = AB.STAGE_CONTINUATION_AFTER_EFFECT
#: How long the worker may sit at the barrier before this probe gives up. The
#: barrier's own timeout is longer; the probe gives up first so the failure is
#: reported rather than absorbed by the barrier's bounded hold.
BARRIER_WAIT_SECONDS = 300.0


def barrier_dir(db: str) -> Path:
    """Where the worker will write this world's barrier files. Same rule the
    barrier applies internally: beside the world's own database, i.e. inside
    that world's run directory."""
    return Path(db).parent / "acceptance_barrier"


def wait_for_barrier_arrival(db: str, expect_pid: int,
                             timeout: float = BARRIER_WAIT_SECONDS,
                             ) -> Optional[Dict[str, Any]]:
    """Block until the serving worker parks at the barrier.

    Deliberately NOT a database poll: the whole point of the mode is that the
    window cannot be observed by watching rows. The arrival file is the
    worker's own statement that it is between the two steps, and it carries the
    pid, so a marker written by any other process is detectable.
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


def release_barrier(db: str) -> Path:
    path = AB.release_path(barrier_dir(db), BARRIER_STAGE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"released by probe at {time.time()}")
    return path


def stack_cmd(*args: str, env_extra: Optional[Dict[str, str]] = None,
              timeout: int = 1800) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "TESTING"}
    env.update(env_extra or {})
    return subprocess.run([PYTHON, str(STACK), *args], cwd=str(REPO), env=env,
                          capture_output=True, text=True, timeout=timeout)


def launch_with_shim(world: str, port: int, shim_port: int,
                     budget: float,
                     barrier: Optional[Dict[str, str]] = None
                     ) -> Dict[str, Any]:
    """The C16 launch order, verbatim in spirit: shim first, then the world.

    Order is load-bearing and getting it wrong is silent -- provider discovery
    runs at server startup, so a world launched before the shim listens never
    registers the provider and the pin quietly falls back to the real route.
    """
    def launch(reuse: str = "", pin: str = "") -> bool:
        stack_cmd("--world", world, "down")
        time.sleep(3)
        cmd = ["up", "--backend-port", str(port), "--api-only"]
        if reuse:
            cmd += ["--reuse-run", reuse]
        extra = dict(barrier or {})
        if pin:
            extra["ATOM_ASYNC_EDIT_PLAN_MODEL"] = pin
        if budget:
            extra["ATOM_CHAT_REQUEST_DEADLINE_SECONDS"] = str(budget)
        r = stack_cmd("--world", world, *cmd, env_extra=extra)
        if r.returncode != 0:
            print(r.stdout[-1500:], r.stderr[-1500:])
        return r.returncode == 0

    if not launch():
        raise SystemExit("fresh launch failed")
    wiring = c16.point_world_at_shim(world, shim_port)
    if not launch(reuse=wiring["run_dir"], pin=wiring["pin"]):
        raise SystemExit("relaunch on the shim run dir failed")
    return wiring


def set_world_password(db_path: str, password: str) -> None:
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
    with get_db_session() as s:
        user = s.query(User).filter(User.email == c16.LOGIN_EMAIL).first()
        if user is None:
            raise SystemExit(f"{c16.LOGIN_EMAIL} not present in this world")
        user.hashed_password = get_password_hash(password)
        s.commit()


def continuation_rows(db: str, session: str) -> List[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, status, error_message, metadata_json, started_at, "
            "completed_at FROM agent_executions WHERE triggered_by='continuation' "
            "AND json_extract(metadata_json,'$.session_id')=? ORDER BY started_at",
            (session,)).fetchall()
    except sqlite3.OperationalError as exc:
        return [{"error": f"agent_executions unreadable: {exc}"}]
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
                    "metadata": meta, "started_at": r[4], "completed_at": r[5]})
    return out


def update_audits(db: str, canvas_id: str) -> List[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, action_type, created_at, details_json FROM canvas_audit "
            "WHERE canvas_id=? ORDER BY created_at, id", (canvas_id,)).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        details: Any = None
        if r[3]:
            try:
                details = json.loads(r[3]) if isinstance(r[3], str) else r[3]
            except (ValueError, TypeError):
                details = None
        out.append({"id": r[0], "action": r[1], "at": r[2],
                    "operation_id": (details or {}).get("operation_id"),
                    "review_status": (details or {}).get("review_status")})
    return out


def session_execution(db: str, session: str) -> List[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, status, error_message FROM agent_executions "
            "WHERE json_extract(metadata_json,'$.session_id')=? ORDER BY started_at",
            (session,)).fetchall()
        return [{"id": r[0], "status": r[1], "error": r[2]} for r in rows]
    finally:
        con.close()


def recovery_notifications(db: str, canvas_id: str) -> List[Dict[str, Any]]:
    """The notifications this canvas's interrupted background work produced.

    Truthfulness is graded on what the USER was told, not on the row's status:
    a recovery that marks the row failed while telling the user the update
    "applied" has still lied.
    """
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        try:
            rows = con.execute(
                "SELECT type, title, message, metadata_json, created_at "
                "FROM notifications WHERE json_extract(metadata_json,"
                "'$.canvas_id')=? ORDER BY created_at", (canvas_id,)).fetchall()
        except sqlite3.OperationalError as exc:
            return [{"error": f"notifications unreadable: {exc}"}]
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
        out.append({"type": r[0], "title": r[1], "message": r[2],
                    "metadata": meta, "at": r[4]})
    return out


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
    ap.add_argument("--port", type=int, default=8079)
    ap.add_argument("--out", required=True)
    ap.add_argument("--kill-after-effect", action="store_true",
                    help="wait until the operation-LINKED audit row for this "
                         "continuation exists, then kill the worker BEFORE the "
                         "terminal record is written. The previous mode killed as "
                         "soon as the continuation was running, which in practice "
                         "caught it before the write landed, so the "
                         "'already applied, must not repeat' branch had nothing "
                         "to repeat. This mode is the one that tests it.")
    ap.add_argument("--barrier-after-effect", action="store_true",
                    help="the DETERMINISTIC version of --kill-after-effect. The "
                         "world is launched with the product's own test-only "
                         "barrier armed for this session "
                         "(core/acceptance_barrier, stage "
                         "continuation_after_effect, refused outside an isolated "
                         "acceptance world). The worker parks between the "
                         "committed mutation and the terminal record and says so "
                         "in a file; this probe waits for THAT file -- not for a "
                         "database row -- asserts the window's state, then "
                         "SIGKILLs. Needed because the window is ~20 ms wide, "
                         "which no poll can land in (see the module docstring).")
    args = ap.parse_args(argv)
    if args.barrier_after_effect and args.kill_after_effect:
        raise SystemExit("--barrier-after-effect already implies killing after "
                         "the effect; pass one or the other")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    world_dir = WORLDS / args.world
    base = f"http://127.0.0.1:{args.port}"
    origin = f"http://localhost:{args.port}"
    rep = Report()
    timeline: List[Dict[str, Any]] = []
    #: Recorded-but-not-graded findings, so an artifact carries what was
    #: measured instead of only what was asserted.
    observations: List[Dict[str, Any]] = []

    def mark(event: str, **kw: Any) -> None:
        timeline.append({"at": time.strftime("%H:%M:%S"), "event": event, **kw})
        print(f"  [{time.strftime('%H:%M:%S')}] {event} "
              f"{json.dumps(kw, default=str)[:220]}", flush=True)

    # The only injection: one consistent ACCEPTING plan, with the stall armed so
    # the real async fork is taken and the continuation outlives the request.
    script = out_dir / "planner_script.json"
    c16.write_script(script, [{"match": "CanvasEditPlan", "response": {
        "response": {"tool_call": {"name": c16.PLANNER_TOOL_NAME,
                                   "arguments": json.loads(c16.plan_json(
                                       wants_edit=True, ops=c16.PATCH_OPS))}},
        "stall_seconds": STALL_SECONDS, "stall_first_n": 1}}])
    shim_port = c16.free_port()
    shim = c16.start_shim(script, shim_port, capture=out_dir / "shim_requests.jsonl")
    mark("shim listening", port=shim_port)

    # The session id is generated BEFORE the launch because the barrier's
    # session narrowing is a launch-time environment variable: the harness has
    # to know the id it is about to use in order to arm the barrier for it.
    marker = f"BGINT-{int(time.time())}-{uuid.uuid4().hex[:4]}"
    session = f"bgint-{marker}"
    barrier_env: Dict[str, str] = {}
    if args.barrier_after_effect:
        barrier_env = {
            AB.ENV_STAGE: BARRIER_STAGE,
            AB.ENV_MATCH: session,
            # Long enough that the probe's own wait is what gives up, never the
            # barrier's bounded hold silently continuing the work.
            AB.ENV_TIMEOUT: "600",
        }

    try:
        wiring = launch_with_shim(args.world, args.port, shim_port,
                                  INTERACTIVE_BUDGET, barrier=barrier_env)
        state = json.loads((world_dir / "preview_stack.json").read_text())
        db, run_dir = state["db_path"], str(Path(state["run_dir"]))
        descriptor = json.loads((world_dir / "launch_descriptor.json").read_text())
        serving_pid = int(descriptor["pid"])
        mark("world launched", pid=serving_pid, run_dir=Path(run_dir).name,
             pin=wiring.get("pin"),
             barrier=descriptor.get("effective_flags", {}).get(
                 "ATOM_ACCEPTANCE_BARRIER"))

        import httpx
        set_world_password(db, c16.LOGIN_PASSWORD)
        tok = httpx.post(f"{base}/api/auth/login", trust_env=False, timeout=60,
                         headers={"Origin": origin},
                         json={"username": c16.LOGIN_EMAIL,
                               "password": c16.LOGIN_PASSWORD}).json()["access_token"]
        headers = {"Authorization": f"Bearer {tok}"}
        uid = str(httpx.get(f"{base}/api/auth/me", headers=headers,
                            trust_env=False, timeout=60).json()["id"])

        canvas = c16.seed_canvas(db, marker, uid)
        before = c16.read_state(db, canvas["canvas_id"])
        mark("canvas seeded", canvas_id=canvas["canvas_id"],
             audit_count=before["audit_count"])

        # ------------------------------------------------------------ the kill
        reply: Dict[str, Any] = {}

        def fire() -> None:
            try:
                r = httpx.post(f"{base}/api/chat/message", headers=headers,
                               trust_env=False, timeout=1800,
                               json={"message": ("in the open canvas, change the "
                                                 "quote validity from 15 days to "
                                                 f"30 days and mark the edit {marker}"),
                                     "session_id": session, "user_id": uid,
                                     "context": {"canvas": {"id": canvas["canvas_id"]},
                                                 "canvas_content": canvas["content"],
                                                 "canvas_type": "email",
                                                 "canvas_title": "BG interrupt"}})
                reply["status"] = r.status_code
            except Exception as exc:      # the worker is killed mid-flight on purpose
                reply["error"] = f"{type(exc).__name__}: {exc}"[:200]

        th = threading.Thread(target=fire, daemon=True)
        th.start()

        victim: Optional[Dict[str, Any]] = None
        deadline = time.time() + 240
        # In barrier mode the interactive request is expected to return long
        # before the continuation finishes, so thread liveness must not end the
        # search: the worker parks at the barrier afterwards and that is what
        # this probe is waiting for.
        while time.time() < deadline and (args.barrier_after_effect
                                          or th.is_alive()):
            for row in continuation_rows(db, session):
                if str(row.get("status", "")).lower() == "running":
                    victim = row
                    break
            if victim:
                break
            time.sleep(0.5)
        rep.check("a BACKGROUND continuation was running when the kill was timed",
                  victim is not None,
                  {"continuations": continuation_rows(db, session),
                   "thread_alive": th.is_alive()})
        if victim is None:
            raise SystemExit("no continuation to interrupt; the fork never happened")
        victim_id = victim["id"]
        mark("continuation running", execution_id=victim_id)

        # ------------------------------------------------- kill AFTER the effect
        # The window that matters: the mutation has landed, and the terminal
        # record has NOT been written. Killing earlier proves recovery; killing
        # here proves recovery does not REPEAT an effect that already happened.
        # The row is located by the operation identity the write stamps, not by
        # recency -- an audit row is only this mutation's if its operation_id is
        # one this continuation legitimately owns.
        held_lock: Optional[sqlite3.Connection] = None
        if args.kill_after_effect or args.barrier_after_effect:
            attributed = {victim_id}
            origin = ((victim.get("metadata") or {}).get("origin_operation_id")
                      or (victim.get("metadata") or {}).get("continuation", {}).get(
                          "origin_operation_id"))
            if origin:
                attributed.add(str(origin))

            if args.barrier_after_effect:
                # DETERMINISTIC. The worker parks itself between the committed
                # mutation and the terminal record, so the window is not raced
                # for -- it is announced. Waiting on the arrival FILE is also
                # the only honest way to know the worker is between the two
                # steps: a database read can only ever prove the state, and
                # the state before and after the window is identical.
                arrival = wait_for_barrier_arrival(db, serving_pid)
                rep.check("the serving worker parked at the acceptance barrier",
                          arrival is not None,
                          {"stage": BARRIER_STAGE,
                           "waited_for": str(barrier_dir(db)),
                           "expected_pid": serving_pid,
                           "barrier_armed": descriptor.get(
                               "effective_flags", {}).get(
                                   "ATOM_ACCEPTANCE_BARRIER"),
                           "continuations": continuation_rows(db, session),
                           "thread_alive": th.is_alive()})
                if arrival is None:
                    # No arrival marker is a harness-timing outcome, not a
                    # product result, so it is recorded as one rather than as a
                    # crash-recovery verdict.
                    (out_dir / "NO_BARRIER.json").write_text(json.dumps(
                        {"schema": "lane3-background-no-barrier-v1",
                         "reason": f"the worker never parked at barrier "
                                   f"{BARRIER_STAGE!r} within "
                                   f"{BARRIER_WAIT_SECONDS:.0f}s",
                         "world": args.world, "backend": base,
                         "session": session,
                         "continuations": continuation_rows(db, session),
                         "thread_alive": th.is_alive()},
                        indent=1, default=str))
                    raise SystemExit("no barrier arrival; cannot place the kill "
                                     "inside the after-the-effect window")
                mark("barrier arrival", pid=arrival.get("pid"),
                     stage=arrival.get("stage"),
                     context=arrival.get("context"))
                rep.check("the barrier was armed for THIS session and the "
                          "parking process is the recorded serving worker",
                          str((arrival.get("context") or {}).get("session_id")
                              or "") == session
                          and int(arrival.get("pid") or 0) == serving_pid,
                          {"arrival": arrival, "session": session,
                           "serving_pid": serving_pid,
                           "why": "a marker from another pid, or for another "
                                  "session, would mean the kill is not landing "
                                  "in the window this probe opened"})
                # INSIDE the window: read the durable state that a poll could
                # never catch, with the worker provably parked.
                landed = next((a for a in update_audits(db, canvas["canvas_id"])
                               if a["operation_id"] and
                               a["operation_id"] in attributed), None)
                terminal_early = False
            else:
                # NOT gated on the request thread: once the product forks, the
                # interactive request returns a PENDING response and the thread
                # is done while the continuation is still working. Waiting on
                # the thread would end this loop seconds after the fork and
                # report "the effect never landed" for a run that was merely
                # still in progress. The window closes on the durable state,
                # not on the caller.
                landed = None
                terminal_early = False
                eff_deadline = time.time() + 300
                while time.time() < eff_deadline:
                    for a in update_audits(db, canvas["canvas_id"]):
                        if a["operation_id"] and a["operation_id"] in attributed:
                            landed = a
                            break
                    if landed:
                        break
                    row_now = next((r for r in continuation_rows(db, session)
                                    if r["id"] == victim_id), None)
                    if row_now and str(row_now.get("status", "")).lower() != "running":
                        terminal_early = True
                        break
                    time.sleep(0.02)
                if terminal_early and not landed:
                    mark("continuation reached a terminal state before the effect "
                         "was observed; the interrupted-after-effect window closed")

            rep.check("the operation-LINKED audit row exists before the kill",
                      landed is not None,
                      {"attributed_operation_ids": sorted(attributed),
                       "audits": update_audits(db, canvas["canvas_id"]),
                       "thread_alive": th.is_alive(),
                       "how": "barrier arrival" if args.barrier_after_effect
                              else "db poll (raced)"})
            if landed is None:
                raise SystemExit("the effect never landed; cannot test the "
                                 "after-the-effect interruption")
            mark("effect landed", audit_id=landed["id"],
                 operation_id=landed["operation_id"])

            if not args.barrier_after_effect:
                # Polling cannot hold this window. Measured: the audit row's
                # commit and the terminal record land back to back, and a 20 ms
                # poll loop only ever saw them together -- so "kill after the
                # effect, before completion" was unreachable by waiting. The
                # write lock is held here as a HARNESS technique only; it is
                # already too late for the effect-to-completion window (a reader
                # can see the audit row only after that commit), which is
                # exactly what --barrier-after-effect replaces.
                held_lock = sqlite3.connect(db, isolation_level=None, timeout=1)
                held_lock.execute("PRAGMA busy_timeout=1500")
                lock_held = False
                try:
                    held_lock.execute("BEGIN IMMEDIATE")
                    lock_held = True
                except sqlite3.OperationalError as exc:
                    mark("could not seize the write lock", error=str(exc)[:160])
                mark("write lock held" if lock_held else "write lock NOT held",
                     journal_mode=sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                     .execute("PRAGMA journal_mode").fetchone()[0])

            still = next((r for r in continuation_rows(db, session)
                          if r["id"] == victim_id), None)
            rep.check("the terminal record had NOT been written when the kill fired",
                      still is not None
                      and str(still.get("status", "")).lower() == "running"
                      and not still.get("completed_at"),
                      {"status": (still or {}).get("status"),
                       "completed_at": (still or {}).get("completed_at"),
                       "how": "the worker was parked at the barrier, so this is "
                              "a real observation of the window, not a race",
                       "why": "if completion had already been recorded this is the "
                              "ordinary completed case, not the interrupted one"})

        if held_lock is not None:
            try:
                held_lock.close()      # the kill is done; the world is going down
            except Exception:
                pass
        os.kill(serving_pid, signal.SIGKILL)
        gone = False
        for _ in range(100):
            try:
                os.kill(serving_pid, 0)
                time.sleep(0.1)
            except OSError:
                gone = True
                break
        rep.check("the recorded serving worker is gone (SIGKILL, not a stall)",
                  gone, {"pid": serving_pid,
                         "why_not_a_stall": "a stall keeps a live owner, and the "
                                            "boot sweep correctly refuses to touch "
                                            "live work -- that is a different case "
                                            "and would not measure recovery"})
        mark("worker killed", pid=serving_pid)

        ghost = continuation_rows(db, session)
        ghost_row = next((r for r in ghost if r["id"] == victim_id), None)
        rep.check("BEFORE any restart the continuation is still 'running' (a ghost)",
                  ghost_row is not None
                  and str(ghost_row["status"]).lower() == "running",
                  {"status": ghost_row["status"] if ghost_row else None})
        audits_at_kill = update_audits(db, canvas["canvas_id"])
        updates_at_kill = [a for a in audits_at_kill if a["action"] == "update"]
        content_at_kill = c16.read_state(db, canvas["canvas_id"])
        mark("state at kill", audit_count=len(audits_at_kill),
             updates=len(updates_at_kill),
             effect_landed=content_at_kill.get("has_new_text"))

        # ------------------------------------------------------------- recovery
        stack_cmd("--world", args.world, "down")
        back = stack_cmd("--world", args.world, "up", "--api-only",
                         "--backend-port", str(args.port), "--reuse-run", run_dir)
        if back.returncode != 0:
            print(back.stdout[-2000:], back.stderr[-2000:])
            raise SystemExit("restart failed")
        d2 = json.loads((world_dir / "launch_descriptor.json").read_text())
        mark("restarted", pid=d2["pid"], source_id=d2.get("health_identity", {}).get("source_id"))

        after = continuation_rows(db, session)
        row = next((r for r in after if r["id"] == victim_id), None)
        rep.check("the same run dir and database served the restart",
                  json.loads((world_dir / "launch_descriptor.json").read_text())["db_path"] == db,
                  {"db": db, "run_dir": run_dir})
        rep.check("the interrupted continuation is no longer 'running'",
                  row is not None and str(row["status"]).lower() != "running",
                  {"status": row["status"] if row else None})
        recovery = ((row or {}).get("metadata") or {}).get("recovery")
        rep.check("it is reconciled as CRASH-recovered from a VERIFIED dead owner",
                  bool(recovery and recovery.get("crashed"))
                  and recovery.get("owner_state") in ("dead", "self"),
                  {"recovery": recovery,
                     "owner_state_meaning": "dead = no such pid, or a confirmed "
                                            "pid reuse; anything else would be "
                                            "'unknown' and must NOT be reconciled"})
        rep.check("recovery did not invent a second continuation row",
                  len([r for r in after if r["id"] == victim_id]) == 1,
                  {"rows": len(after)})

        audits_after = update_audits(db, canvas["canvas_id"])
        updates_after = [a for a in audits_after if a["action"] == "update"]
        content_after = c16.read_state(db, canvas["canvas_id"])
        rep.check("the already-landed effect was NOT applied a second time",
                  len(updates_after) == len(updates_at_kill),
                  {"update_audits_at_kill": len(updates_at_kill),
                   "after_recovery": len(updates_after),
                   "audits": [a["action"] for a in audits_after],
                   "why": "a repeated mutation on a user's canvas is the one "
                          "failure this whole path exists to prevent"})
        # The absolute form of the same claim, in the mode that is supposed to
        # be deterministic: the canvas carries exactly ONE update row, total,
        # and it is the one the operation identity attributes to this request.
        rep.check("the canvas carries EXACTLY ONE update audit row, and it is "
                  "this request's",
                  len(updates_after) == 1
                  and any(a["operation_id"] in attributed for a in updates_after),
                  {"total_update_rows": len(updates_after),
                   "attributed_operation_ids": sorted(attributed),
                   "update_rows": updates_after,
                   "canvas_content": content_after})
        rep.check("no new audit row appeared during recovery itself",
                  len(audits_after) == len(audits_at_kill),
                  {"at_kill": len(audits_at_kill), "after": len(audits_after)})
        rep.check("the restart ran with the barrier DISARMED",
                  json.loads(
                      (world_dir / "launch_descriptor.json").read_text()
                  ).get("effective_flags", {}).get("ATOM_ACCEPTANCE_BARRIER")
                  in ("(disarmed)", "", None),
                  {"effective_flags": json.loads(
                      (world_dir / "launch_descriptor.json").read_text()
                  ).get("effective_flags", {}),
                   "why": "a barrier still armed during recovery would let the "
                          "probe's own seam, not the product, decide when "
                          "recovery finished"})

        # A follow-up turn must not re-apply the edit either.
        if content_at_kill.get("has_new_text"):
            follow = httpx.post(f"{base}/api/chat/message", headers=headers,
                                trust_env=False, timeout=900,
                                json={"message": "what did you just change?",
                                      "session_id": session, "user_id": uid,
                                      "context": {"current_page": "/chat",
                                                  "conversation_history": []}})
            mark("follow-up turn", status=follow.status_code)
            audits_final = update_audits(db, canvas["canvas_id"])
            updates_final = [a for a in audits_final if a["action"] == "update"]
            rep.check("a follow-up turn did not re-apply the same edit",
                      len(updates_final) == len(updates_at_kill),
                      {"updates_at_kill": len(updates_at_kill),
                       "after_followup": len(updates_final)})
        else:
            rep.check("a follow-up turn did not re-apply the same edit",
                      True, {"note": "the effect had not landed before the kill, so "
                                     "there was nothing to repeat"})

        hist = httpx.get(f"{base}/api/chat/history/{session}", headers=headers,
                         trust_env=False, timeout=60)
        blob = json.dumps(hist.json()) if hist.status_code == 200 else ""
        rep.check("after recovery the session still reports the turn honestly",
                  hist.status_code == 200 and session in blob,
                  {"status": hist.status_code, "bytes": len(blob),
                   "raw_bracket_diagnostic": "[background continuation" in blob,
                   "note": "the bracketed text is the known D5 UX gap, recorded "
                           "not fixed here"})
        # TRUTHFULNESS OF THE OUTCOME, read from what the user is actually
        # shown. In barrier mode the continuation never got to write its own
        # outcome ChatMessage (it was parked before _apply_effects), so the
        # only user-visible statement about that work is the recovery
        # notification. A "the background update applied" claim anywhere would
        # be a lie about work that was interrupted after the write.
        notes = recovery_notifications(db, canvas["canvas_id"])
        applied_claims = [n for n in notes
                          if "applied" in str(n.get("message", "")).lower()
                          or "applied" in str(n.get("title", "")).lower()]
        rep.check("nothing the user is shown claims the interrupted background "
                  "update applied",
                  not applied_claims,
                  {"notifications": notes,
                   "applied_claims": applied_claims,
                   "why": "the write DID land, but the background attempt that "
                          "landed it was killed before it could say so; a claim "
                          "of 'applied' attributed to the interrupted attempt "
                          "would be asserting a completion nobody recorded"})
        if args.barrier_after_effect:
            rep.check("the user WAS told the background update was interrupted",
                      any("interrupt" in str(n.get("message", "")).lower()
                          or "restart" in str(n.get("message", "")).lower()
                          for n in notes),
                      {"notifications": notes,
                       "why": "silence is not truthful reporting either: the "
                              "turn the user asked for ended in a state they "
                              "were never shown"})
        execs = session_execution(db, session)
        rep.check("no duplicate execution was created for the interrupted turn",
                  len([e for e in execs if e["id"] == victim_id]) == 1,
                  {"executions": execs})
        rep.check("recovery wrote no new continuation row for the session",
                  len(after) == len(ghost),
                  {"before": len(ghost), "after": len(after),
                   "why": "a reconcile that re-forked the work would be a "
                          "second attempt at a mutation that already landed"})

        # RECORDED, NOT GRADED. Two things this run measured about the recovery
        # notification that are not this probe's claim to make and not its
        # failure to own:
        #   * the world's frozen fixture already carried crashed continuation
        #     rows from 2026-09-23, so the boot pass had 3 rows to notify, not 1;
        #   * every one of the 3 notification rows carries THIS run's canvas_id
        #     and session_id, including the two that belong to a different
        #     canvas/session -- `notify_recovered_continuations` dispatches the
        #     send as a task that closes over the loop variable, so by the time
        #     it runs it reads the LAST row's metadata; and
        #   * `continuation.notified` is still unset on all three afterwards,
        #     so a later boot would notify them again.
        # Truthfulness is graded above; this is recorded so the next reader does
        # not have to re-derive it.
        # (appended to the payload's observations list)
        if len(notes) > 1:
            observations.append({
                "what": f"{len(notes)} recovery notifications for one restart",
                "canvas_ids": sorted({str((n.get('metadata') or {}).get(
                    'canvas_id')) for n in notes}),
                "sessions": sorted({str((n.get('metadata') or {}).get(
                    'session_id')) for n in notes}),
                "note": "the fixture carries older crashed rows, and every "
                        "notification carries this run's identity -- deferred "
                        "closure over the loop variable in "
                        "notify_recovered_continuations",
            })
        victim_notified = (((row or {}).get("metadata") or {}).get(
            "continuation") or {}).get("notified")
        if not victim_notified:
            observations.append({
                "what": "continuation.notified is still unset on the recovered "
                        "row",
                "execution_id": victim_id,
                "note": "the pass sets the flag after dispatching, so a later "
                        "boot would notify the same crashed row again",
            })
    finally:
        try:
            shim.terminate()
        except Exception:
            pass
        stack_cmd("--world", args.world, "down")

    verdict = "PASS" if all(rep.checks.values()) else "FAIL"
    payload = {
        "schema": "lane3-background-interrupt-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": args.world, "backend": base,
        "mode": ("barrier-after-effect" if args.barrier_after_effect
                 else "kill-after-effect" if args.kill_after_effect
                 else "kill-while-running"),
        "barrier": {"stage": BARRIER_STAGE, "armed": bool(barrier_env),
                    "env": barrier_env,
                    "confined_to": "acceptance_worlds (refused elsewhere)"},
        "verdict": verdict,
        "checks_passed": rep.passed, "checks_total": rep.total,
        "checks": rep.checks, "details": rep.details, "timeline": timeline,
        "scope_note": "the only injection is the planner's model response; the "
                      "fork, the continuation, the reservation, the store, the "
                      "audit rows and the recovery are all the product's. The "
                      "barrier is a PAUSE between two steps that both really "
                      "happen: it writes no row, decides nothing, and cannot "
                      "make a failed outcome read as applied.",
        "observations_not_graded": observations,
    }
    (out_dir / "background_interrupt.json").write_text(
        json.dumps(payload, indent=1, default=str))
    print(f"\n{rep.passed}/{rep.total} checks -> {out_dir / 'background_interrupt.json'}")
    for name, ok in rep.checks.items():
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
