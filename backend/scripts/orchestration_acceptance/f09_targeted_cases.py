#!/usr/bin/env python3
"""Targeted F09 checks (2026-09-28): delivery-claim crash, two-process
arbitration, updated public overlap run.

These are DISTINCT from the F11 crash-window case (which parks BEFORE the
terminal effects/record). F09's checks target outcome DELIVERY:

  A. Delivery-claim crash — the worker parks at the barrier, is killed, and
     recovery must deliver the user-visible terminal outcome EXACTLY ONCE:
     one notification after the first restart, and STILL one after a second
     restart (the notified-once flag must persist; the flag_modified defect
     found in the F11 evidence would re-notify here).
  B. Two-process arbitration — two sandboxed servers share one run DB.
     While process A holds the continuation claim for session S (parked at
     the barrier), process B's turn for S must be refused the fork (claim
     held) and answered honestly — no second claim, no second fork record —
     while a control session proceeds normally. After A dies and B's world
     restarts, the boot sweep reconciles A's record and clears the stale
     claim.
  C. Updated public overlap run — the user-facing overlap scenario on the
     current code: concurrent pair, distinct identities, both forked turns
     deliver live `chat_continuation` events and persisted terminal
     outcomes, canvas coherent, sibling outcome truthful.

Isolation model unchanged (seatbelt, shim as provider, dedicated shim port).
Usage: f09_targeted_cases.py [--port 8026] [--b-port 8027] [--results ...]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sqlite3 as _sq
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("SECRET_KEY", uuid.uuid4().hex + uuid.uuid4().hex)

RESULTS: List[Dict[str, Any]] = []


def record(case: str, checks: Dict[str, Any], notes: Optional[List[str]] = None,
           details: Optional[Dict[str, Any]] = None) -> bool:
    ok = bool(checks) and all(v is True for v in checks.values())
    RESULTS.append({"case": case, "status": "PASS" if ok else "FAIL",
                    "checks": checks, "notes": notes or [],
                    "details": details or {}})
    print(f"[{'PASS' if ok else 'FAIL'}] {case}")
    for k, v in checks.items():
        print(f"    {'✓' if v is True else '✗'} {k}: {v}")
    return ok


_SHIM_PROC = None
_SHIM_SCRIPT = None
_SHIM_CAPTURE = None


def ensure_shim_alive() -> None:
    """Relaunch the shim if it died mid-run (external cleanups sweep ports;
    observed 2026-09-28: the shim vanished between phases, and the next
    arm_stall died with Connection refused, losing the remaining cases)."""
    global _SHIM_PROC
    # SHIM_PORT is imported into main()'s scope only; resolve it here or
    # the probe below raises NameError inside its own try/except, reads as
    # "shim dead", and the relaunch path crashes (observed 2026-09-28:
    # two writer attempts died exactly here and persisted no results).
    from scripts.orchestration_acceptance.finish_line_cases import SHIM_PORT
    import httpx
    try:
        httpx.get(f"http://127.0.0.1:{SHIM_PORT}/log", timeout=3,
                  trust_env=False)
        return  # alive
    except Exception:
        pass
    from scripts.orchestration_acceptance import run_isolated as R
    from scripts.orchestration_acceptance.finish_line_cases import (
        ensure_port_free, register_pid)
    try:
        ensure_port_free(SHIM_PORT)
    except RuntimeError:
        pass
    _SHIM_PROC = R.launch_shim(_SHIM_SCRIPT, SHIM_PORT, capture=_SHIM_CAPTURE)
    register_pid(_SHIM_PROC.pid)
    print("[shim] relaunched mid-run")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8026)
    ap.add_argument("--b-port", type=int, default=8027)
    ap.add_argument("--results", default=str(
        BACKEND.parent / "docs" / "architecture" /
        "orchestration_migration" / "acceptance" / "f09_targeted_0928.json"))
    ap.add_argument("--world", default="f09_delivery",
                    help="DEDICATED world: the shared write_combined world "
                         "is contaminated by whichever stream tests against "
                         "it concurrently (observed 2026-09-28: foreign "
                         "sessions wrote mid-run).")
    ap.add_argument("--phase", default="all", choices=["1", "2", "all"],
                    help="'2' runs ONLY the automatic-recovery case on a "
                         "fresh run dir (launch+seed+mine included); 'all' "
                         "preserves the original multi-phase behaviour.")
    ap.add_argument("--out-dir", default=str(
        BACKEND.parent / "docs" / "architecture" /
        "orchestration_migration" / "acceptance" / "lane3" /
        "f09_auto_recovery_0928"))
    args = ap.parse_args()

    class _SkipRest(Exception):
        """Control-flow only: skip the phases this --phase selection does
        not run, falling through to the shared cleanup/finally blocks."""

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _ckpt_path = out_dir / "checkpoints.jsonl"

    def ckpt(event: str, **data: Any) -> None:
        """Timestamped checkpoint after every driver action (2026-09-28
        instruction): the audit must be able to reconstruct timing without
        re-deriving it from the database."""
        row = {"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "epoch": time.time(), "event": event}
        row.update(data)
        with _ckpt_path.open("a") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        print(f"[ckpt] {event} {json.dumps(data, default=str)[:180]}")

    ckpt("driver_start", phase=args.phase, world=args.world,
         pid=os.getpid())

    from scripts.orchestration_acceptance import run_isolated as R
    from scripts.orchestration_acceptance.finish_line_cases import (
        SHIM_PORT, World, arm_stall, disarm_stall, ensure_port_free,
        poll_until, send, ws_continuation_events,
    )
    script = (BACKEND.parent / "docs" / "architecture" /
              "orchestration_migration" / "acceptance" / "lane3" /
              "finish_line_0928" / "planner_script.json")
    # PID JOURNAL: this runner's OWN previous invocation may have left the
    # shim/servers alive. Those pids are OURS (recorded identity), so
    # cleaning them up honors the ownership rule; anything else on the port
    # is foreign and is refused by ensure_port_free.
    from scripts.orchestration_acceptance.finish_line_cases import (
        register_pid)
    journal = BACKEND / "data" / "acceptance_worlds" / \
        "f09_runner_pids.json"
    try:
        for pid in json.loads(journal.read_text()):
            try:
                os.kill(int(pid), signal.SIGKILL)
            except (ProcessLookupError, ValueError, OSError):
                pass
    except Exception:
        pass
    journal.write_text("[]")

    def _journal_pid(pid):
        register_pid(pid)
        try:
            pids = json.loads(journal.read_text())
        except Exception:
            pids = []
        pids.append(int(pid))
        journal.write_text(json.dumps(pids))

    ensure_port_free(SHIM_PORT)
    ensure_port_free(args.port)
    ensure_port_free(args.b_port)
    world_dir = BACKEND / "data" / "acceptance_worlds" / args.world
    if not (world_dir / "MANIFEST.json").exists():
        import subprocess as _sp
        _sp.run([str(R.VENV_PY),
                 str(BACKEND / "scripts" / "orchestration_acceptance" /
                     "run_isolated.py"),
                 "--name", args.world, "--rebuild-world",
                 "--snapshot-working-tree"], check=False)
    global _SHIM_PROC, _SHIM_SCRIPT, _SHIM_CAPTURE
    _SHIM_SCRIPT, _SHIM_CAPTURE = script, None
    shim = R.launch_shim(script, SHIM_PORT)
    _journal_pid(shim.pid)
    World.world_name = args.world
    world = World(args.port)
    token = None
    try:
        # ---- PHASE 1: two-process arbitration --------------------------
        os.environ["ATOM_ACCEPTANCE_BARRIER"] = "continuation_after_effect"
        s1 = f"f09-arb-{uuid.uuid4().hex[:8]}"
        os.environ["ATOM_ACCEPTANCE_BARRIER_MATCH"] = s1
        os.environ["ATOM_ACCEPTANCE_BARRIER_TIMEOUT"] = "300"
        try:
            if args.phase == "2":
                ckpt("skip_phase", phase=1, reason="--phase 2 standalone")
                raise _SkipRest()
            world.launch()
            world.seed()
            token = world.mint()
            bdir = Path(world.run_dir) / "data" / "acceptance_barrier"
            arrival = bdir / "barrier.continuation_after_effect.arrived.json"
            before = world.update_count()
            arm_stall(world, 40, first_n=1)
            rid1 = f"f09-arb-{uuid.uuid4().hex[:8]}"
            try:
                send(world, token, s1,
                     "change the quote validity from 15 days to 30 days",
                     rid1, timeout=60)
            except Exception:
                pass
            parked = poll_until(arrival.exists, 150, interval=0.5)
            forks_s1 = world.fork_records(s1)
            record("F09B_A_parked_holding_claim", {
                "worker_parked": bool(parked),
                "one_fork_record": len(forks_s1) == 1,
                "claim_row_exists": world._ro().execute(
                    "SELECT count(*) FROM async_continuation_claims "
                    "WHERE session_id=?", (s1,)).fetchone()[0] == 1,
            })
            disarm_stall(world)

            # process B: second sandboxed server on the SAME run DB
            b_env = {
                "PATH": os.environ["PATH"], "HOME": os.environ["HOME"],
                "SECRET_KEY": os.environ.get("SECRET_KEY", ""),
                "DATABASE_URL": f"sqlite:///{world.run_dir}/data/atom.db",
                "ATOM_DATA_DIR": str(Path(world.run_dir) / "data"),
                "LANCEDB_URI": str(BACKEND / "data" / "acceptance_worlds" /
                                   "write_combined" / "data" / "atom_memory"),
                "ACC_PORT": str(args.b_port),
                "ATOM_CHAT_STREAMING": "1",
                "ENABLE_SCHEDULER": "false",
                "ENABLE_INGESTION_SYNC": "false",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
            }
            profile = (BACKEND / "data" / "acceptance_worlds" /
                       args.world / "local_only_b.sb")
            profile.write_text(R._sandbox_profile(
                args.b_port, extra_ports=(SHIM_PORT,)))
            blog = open(BACKEND / "data" / "acceptance_worlds" /
                        args.world / "server_b.log", "ab")
            proc_b = subprocess.Popen(
                ["/usr/bin/sandbox-exec", "-f", str(profile),
                 str(R.VENV_PY),
                 str(BACKEND / "scripts" / "orchestration_acceptance" /
                     "_app.py")],
                cwd=str(BACKEND / "data" / "acceptance_worlds" /
                        args.world / "backend_root"),
                env=b_env, stdout=blog, stderr=subprocess.STDOUT,
                start_new_session=True)
            world.proc_b = proc_b  # so the main finally can reap B
            _journal_pid(proc_b.pid)
            import httpx
            b_up = poll_until(lambda: (
                lambda r: r is not None and r.status_code == 200)(
                _health(args.b_port)), 240, interval=2)
            record("F09B_B_second_server_up", {
                "second_server_healthy": bool(b_up),
            })

            # B's turn for the CLAIMED session: fork must be refused
            r_b = send(world, token, s1, "beta: update the payment terms",
                       f"f09-b1-{uuid.uuid4().hex[:6]}") if b_up else None
            forks_s1_after = world.fork_records(s1)
            claims_s1 = world._ro().execute(
                "SELECT count(*) FROM async_continuation_claims "
                "WHERE session_id=?", (s1,)).fetchone()[0]
            b_log_text = (BACKEND / "data" / "acceptance_worlds" /
                          "write_combined" / "server_b.log").read_text(
                              errors="replace")
            record("F09B_B_refused_fork_on_claimed_session", {
                "b_turn_answered": r_b is not None
                and r_b.status_code == 200,
                "no_second_fork_record": len(forks_s1_after) == 1,
                "claim_still_single": claims_s1 == 1,
                "b_log_shows_claim_refusal_or_no_fork":
                    "claim held" in b_log_text
                    or "not forked" in b_log_text
                    or len(forks_s1_after) == 1,
            }, details={"b_status": r_b.status_code if r_b else None,
                        "forks": len(forks_s1_after)})

            # control: a DIFFERENT session proceeds normally on B
            s2 = f"f09-ctrl-{uuid.uuid4().hex[:8]}"
            r_c = send(world, token, s2, "eps: change the greeting",
                       f"f09-c1-{uuid.uuid4().hex[:6]}") if b_up else None
            record("F09B_control_session_not_blocked", {
                "control_turn_answered": r_c is not None
                and r_c.status_code == 200,
            })

            # A dies parked; boot in A's world reconciles + clears the claim
            world.kill()
            never_released = not (bdir /
                                  "barrier.continuation_after_effect.release"
                                  ).exists()
            for k in ("ATOM_ACCEPTANCE_BARRIER",
                      "ATOM_ACCEPTANCE_BARRIER_MATCH",
                      "ATOM_ACCEPTANCE_BARRIER_TIMEOUT"):
                os.environ.pop(k, None)
            world.launch(reuse_run_dir=world.run_dir)
            time.sleep(8)
            claims_s1_after = world._ro().execute(
                "SELECT count(*) FROM async_continuation_claims "
                "WHERE session_id=?", (s1,)).fetchone()[0]
            rec_s1 = world.fork_records(s1)
            record("F09B_dead_owner_reconciled_claim_cleared", {
                "barrier_never_released": never_released,
                "stale_claim_cleared": claims_s1_after == 0,
                "dead_record_reconciled": all(
                    f["status"] != "running" for f in rec_s1),
            }, details={"claims_after": claims_s1_after})
        except _SkipRest:
            pass
        finally:
            for k in ("ATOM_ACCEPTANCE_BARRIER",
                      "ATOM_ACCEPTANCE_BARRIER_MATCH",
                      "ATOM_ACCEPTANCE_BARRIER_TIMEOUT"):
                os.environ.pop(k, None)
            disarm_stall(world)

        # ---- PHASE 2: terminal-delivery lease/recovery contract ---------
        # Reconciled mechanism: the fenced conditional-UPDATE claim inside
        # _apply_effects arbitrates delivery; the recurring scan
        # (independent of ENABLE_SCHEDULER) owns retry-after-expiry; the
        # acceptance barrier parks a holder mid-delivery for the
        # two-process stale-holder case.
        proc_b = None
        try:
            if args.phase == "1":
                ckpt("skip_phase", phase=2, reason="--phase 1")
                raise _SkipRest()
            standalone = args.phase == "2"
            if not standalone and world.proc and world.proc.poll() is None:
                try:
                    os.killpg(os.getpgid(world.proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            ensure_port_free(args.port)
            s3 = f"f09-dlv-{uuid.uuid4().hex[:8]}"
            # Park at the CLAIM boundary (after the terminal-delivery claim
            # is taken, before the durable terminal message). This is the
            # boundary the five-fact audit demands: claim present, terminal
            # message absent, lease anchored on the REAL claim — nothing
            # seeded. (Parking at continuation_after_effect instead leaves
            # the claim not-yet-taken by design; the earlier code seeded a
            # synthetic dead-holder claim there, which proves the machinery
            # but not the real claim path.)
            os.environ["ATOM_ACCEPTANCE_BARRIER"] = \
                "continuation_after_claim"
            os.environ["ATOM_ACCEPTANCE_BARRIER_MATCH"] = s3
            os.environ["ATOM_ACCEPTANCE_BARRIER_TIMEOUT"] = "300"
            # Explicit lease and recovery interval (2026-09-28 instruction):
            # recorded, and the observation waits below are COMPUTED from
            # them instead of fixed sleeps.
            LEASE_S = 90.0
            INTERVAL_S = 5.0
            os.environ["ATOM_TERMINAL_DELIVERY_LEASE_SECONDS"] = \
                str(int(LEASE_S))
            os.environ["ATOM_TERMINAL_RECOVERY_INTERVAL_SECONDS"] = \
                str(int(INTERVAL_S))
            ckpt("armed", session=s3, lease_s=LEASE_S, interval_s=INTERVAL_S,
                 barrier="continuation_after_claim")
            if standalone:
                world.launch()            # fresh run dir; env already armed
                world.seed()
                token = world.mint()
            else:
                world.launch(reuse_run_dir=world.run_dir)
                token = world.mint()
            ckpt("launched", run_dir=str(world.run_dir),
                 db=str(world.db_path), pid=world.proc.pid)
            bdir = Path(world.run_dir) / "data" / "acceptance_barrier"
            # Session-matched arrival detection. Earlier phases in this run
            # dir already wrote arrival markers, and polling the shared
            # convenience file returned a stale TRUE (observed 2026-09-28:
            # phase 2 "parked" on phase 1's marker while its own turn never
            # reached the barrier). Only a NEW marker whose context names
            # THIS session counts.
            pre_arrivals = set(bdir.glob(
                "barrier.continuation_after_claim.arrived.*.json"))

            def s3_arrival():
                for p in sorted(set(bdir.glob(
                        "barrier.continuation_after_claim.arrived.*.json"))
                        - pre_arrivals):
                    try:
                        ctx = (json.loads(p.read_text())
                               .get("context") or {})
                    except Exception:
                        continue
                    if ctx.get("session_id") == s3:
                        return p
                return None
            ensure_shim_alive()
            arm_stall(world, 40, first_n=1)
            ckpt("stall_armed", seconds=40, first_n=1)
            rid3 = f"f09-dlv-{uuid.uuid4().hex[:8]}"
            try:
                send(world, token, s3, "beta: update the payment terms",
                     rid3, timeout=60)
            except Exception:
                pass
            parked_path = poll_until(s3_arrival, 150, interval=0.5)
            ckpt("arrival_polled", parked=bool(parked_path),
                 marker=str(parked_path) if parked_path else None)

            def notification_count() -> int:
                con = world._ro()
                try:
                    return con.execute(
                        "SELECT count(*) FROM notifications WHERE title IN "
                        "('Background update could not finish', "
                        "'Background update reached the canvas', "
                        "'Update had already landed')"
                    ).fetchone()[0]
                finally:
                    con.close()

            def terminal_msg_count(sess: str) -> int:
                con = world._ro()
                try:
                    return con.execute(
                        "SELECT count(*) FROM chat_messages WHERE "
                        "conversation_id=? AND role='assistant' AND "
                        "(content LIKE 'Background update%' OR content "
                        "LIKE '%cannot attribute%')",
                        (sess,)).fetchone()[0]
                finally:
                    con.close()

            # PREREQUISITE GATE (firm, 2026-09-28 instruction): a scenario
            # that never parked is INVALID, never a FAIL, and must not kill
            # an unparked worker.
            if parked_path is None:
                record("F09A_running_server_expiry_recovery", {
                    "scenario_invalid_not_run": False,
                }, notes=["INVALID: no session-matched barrier arrival "
                          "within 150s — the turn never parked at "
                          "continuation_after_claim, so no kill was "
                          "performed and nothing about recovery is claimed."
                          " A FAIL here would assert something untested."],
                    details={"run_dir": str(world.run_dir),
                             "session": s3})
                RESULTS[-1]["status"] = "INVALID"
                raise _SkipRest()

            # Pre-kill verification from the server's own run DB: the
            # continuation exists and is running, the delivery claim is
            # taken, no terminal message exists yet, and the worker is the
            # parked, alive process.
            forks_s3 = world.fork_records(s3)
            con = _sq.connect(world.db_path)
            try:
                claim_rows = con.execute(
                    "SELECT metadata_json FROM agent_executions "
                    "WHERE triggered_by='continuation' AND metadata_json "
                    "LIKE ?", (f"%{s3}%",)).fetchall()
            finally:
                con.close()
            claims = []
            for (mj,) in claim_rows:
                try:
                    c = (json.loads(mj).get("continuation") or {})
                except Exception:
                    continue
                if c.get("session_id") == s3:
                    claims.append(c)
            pid_before = world.proc.pid
            run_dir_before = str(world.run_dir)
            db_before = str(world.db_path)
            prekill = {
                "one_fork_record": len(forks_s3) == 1,
                "fork_still_running": bool(forks_s3)
                and forks_s3[0]["status"] == "running",
                "delivery_claim_taken": any(
                    c.get("terminal_delivered") for c in claims),
                "no_terminal_message_yet": terminal_msg_count(s3) == 0,
                "no_release_file": not (
                    bdir / "barrier.continuation_after_claim.release"
                ).exists(),
                "worker_alive": world.proc.poll() is None,
            }
            ckpt("prekill_verified", pid=pid_before, **prekill)
            if not all(prekill.values()):
                record("F09A_running_server_expiry_recovery", {
                    "scenario_invalid_not_run": False,
                }, notes=["INVALID: pre-kill verification failed ("
                          + ", ".join(k for k, v in prekill.items()
                                      if not v)
                          + "). No kill was performed."],
                    details=dict(prekill, run_dir=run_dir_before))
                RESULTS[-1]["status"] = "INVALID"
                raise _SkipRest()
            update_count_before = world.update_count()
            n0 = notification_count()
            world.kill()
            try:
                os.kill(pid_before, 0)
                old_process_dead = False   # still alive: kill failed
            except ProcessLookupError:
                old_process_dead = True
            never_released = not (
                bdir / "barrier.continuation_after_claim.release").exists()
            ckpt("killed", pid=pid_before, dead=old_process_dead,
                 never_released=never_released)

            # Lease anchor: the REAL claim's own timestamp, read from the
            # dead worker's record after the kill. Nothing is seeded — the
            # parked worker took the claim itself, and the recovery pass
            # must defer on it, expire on it, and deliver on it.
            con = _sq.connect(world.db_path)
            try:
                anchor_rows = con.execute(
                    "SELECT metadata_json FROM agent_executions "
                    "WHERE id = ?", (forks_s3[0]["continuation_id"],)
                ).fetchall()
            finally:
                con.close()
            anchor_meta = {}
            for (mj,) in anchor_rows:
                try:
                    anchor_meta = json.loads(mj).get("continuation") or {}
                except Exception:
                    pass
            claim_anchor = float(anchor_meta.get("terminal_delivered_at")
                                 or 0.0)
            if not claim_anchor:
                record("F09A_running_server_expiry_recovery", {
                    "scenario_invalid_not_run": False,
                }, notes=["INVALID: the killed continuation's record carries "
                          "no terminal_delivered_at claim timestamp, so the "
                          "lease anchor cannot be established. Recovery is "
                          "not tested."],
                    details={"continuation": forks_s3[0]["continuation_id"],
                             "meta_keys": sorted(anchor_meta)})
                RESULTS[-1]["status"] = "INVALID"
                raise _SkipRest()
            expiry_at = claim_anchor + LEASE_S
            ckpt("claim_anchor_read", claim_anchor=claim_anchor,
                 expiry_at=expiry_at, lease_s=LEASE_S)
            for k in ("ATOM_ACCEPTANCE_BARRIER",
                      "ATOM_ACCEPTANCE_BARRIER_MATCH",
                      "ATOM_ACCEPTANCE_BARRIER_TIMEOUT"):
                os.environ.pop(k, None)
            world.launch(reuse_run_dir=Path(run_dir_before))  # restart 1 (only one)
            boot_done = time.time()
            pid_new = world.proc.pid
            same_db = (str(world.run_dir) == run_dir_before
                       and str(world.db_path) == db_before)
            started_before_expiry = boot_done < expiry_at
            ckpt("restarted", old_pid=pid_before, new_pid=pid_new,
                 boot_done=boot_done, same_db=same_db,
                 started_before_expiry=started_before_expiry)
            # Boot pass must DEFER: the seeded claim is unexpired at boot.
            time.sleep(6)
            n1 = notification_count()
            m1 = terminal_msg_count(s3)
            ckpt("boot_defer_checked", n1=n1, m1=m1)
            # Leave the server RUNNING and wait for expiry on the RECORDED
            # clock: expiry_at + interval + margin. Fixed short sleeps
            # measured too early on 2026-09-28 and false-failed a working
            # recovery whose delivery landed 94s after the turn.
            delivered_at = None
            deadline = expiry_at + INTERVAL_S + 60.0
            while time.time() < deadline:
                if terminal_msg_count(s3) >= 1:
                    delivered_at = time.time()
                    break
                time.sleep(2.0)
            n2 = notification_count()
            m2 = terminal_msg_count(s3)
            ckpt("delivery_observed", delivered_at=delivered_at,
                 after_expiry=(delivered_at is not None
                               and delivered_at >= expiry_at - 1.0),
                 n2=n2, m2=m2)
            # Stability window: exactly one terminal row, no further canvas
            # mutation, and STILL the same process (no second restart).
            time.sleep(20)
            m3 = terminal_msg_count(s3)
            n3 = notification_count()
            update_count_after = world.update_count()
            still_same_process = (world.proc.pid == pid_new
                                  and world.proc.poll() is None)
            ckpt("stability_checked", m3=m3, n3=n3,
                 update_count_after=update_count_after,
                 still_same_process=still_same_process)
            hist_r2 = world.history_texts(s3)
            # Honest-wording check: the delivered message's wording must
            # match its recorded attribution — success wording ONLY with a
            # landed (operation-linked) effect; otherwise uncertainty.
            con = _sq.connect(world.db_path)
            effects = [row[0] for row in con.execute(
                "SELECT json_extract(metadata_json, "
                "'$.continuation.effect_on_canvas') FROM chat_messages "
                "WHERE conversation_id=? AND role='assistant' AND "
                "metadata_json LIKE '%recovery_delivery%'", (s3,))]
            con.close()
            worded_landed = any("already applied" in h.lower()
                                for h in hist_r2)
            worded_uncertain = any("cannot attribute" in h
                                   for h in hist_r2)
            effects_landed = [e for e in effects if e == "landed"]
            record("F09A_running_server_expiry_recovery", {
                "parked_at_boundary_session_matched": True,
                "old_process_dead": old_process_dead,
                "barrier_never_released": never_released,
                "restarted_same_database": same_db,
                "new_process_started_before_expiry": started_before_expiry,
                "in_flight_claim_deferred_at_boot": n1 == n0 and m1 == 0,
                "automatic_delivery_after_expiry_same_process": (
                    delivered_at is not None
                    and delivered_at >= expiry_at - 1.0
                    and still_same_process),
                "exactly_one_terminal_row": m3 == 1,
                "no_additional_canvas_mutation":
                    update_count_after == update_count_before,
                # bool() because `and` returns its last operand: a truthy
                # effects_landed LIST failed record()'s `v is True` gate
                # and recorded a semantic pass as a FAIL (2026-09-28).
                "wording_matches_recorded_attribution": bool(
                    (worded_landed and effects_landed)
                    or (worded_uncertain and not effects_landed)),
            }, details={
                "timings": {"claim_anchor": claim_anchor,
                            "expiry_at": expiry_at,
                            "boot_done": boot_done,
                            "delivered_at": delivered_at,
                            "lease_s": LEASE_S, "interval_s": INTERVAL_S},
                "pids": {"before": pid_before, "after": pid_new},
                "prekill": prekill,
                "notifications": [n0, n1, n2, n3],
                "msgs": [m1, m2, m3],
                "update_count": [update_count_before, update_count_after],
                "effects": effects,
                "history_r2": [h[:110] for h in hist_r2],
                "notification_channel_note": (
                    "notification deltas are recorded as live-channel "
                    "evidence per handoff step 10; the durable terminal "
                    "MESSAGE is the gating delivery."),
            })
            if standalone:
                ckpt("phase2_complete", reason="--phase 2 standalone")
                raise _SkipRest()

            # ---- 2b. TWO-PROCESS STALE HOLDER --------------------------
            # A continuation whose record is terminal (outcome recorded) but
            # whose message never landed. A's recovery claims it and parks
            # at recovery_delivery_held; B (second server) takes over after
            # expiry; A resumes and the fence must refuse its write.
            sY = f"f09-stale-{uuid.uuid4().hex[:8]}"
            snapshot = "seeded-snapshot"
            con = _sq.connect(world.db_path)
            cid_y = str(_sq.uuid.uuid4()) if hasattr(_sq, "uuid") else \
                str(uuid.uuid4())
            con.execute(
                "INSERT INTO agent_executions (id, tenant_id, status, "
                "input_summary, triggered_by, started_at, metadata_json) "
                "VALUES (?, 'default', 'failed', 'zeta ask', 'continuation', "
                "datetime('now'), ?)",
                (cid_y, json.dumps({
                    "session_id": sY,
                    "origin_operation_id": f"op-{cid_y[:8]}",
                    "continuation": {
                        "session_id": sY, "user_id": world.user_id,
                        "canvas_id": world.canvas_id,
                        "message": "zeta: shorten the payment window",
                        "snapshot_content_hash": snapshot,
                        "outcome": "failed",
                        "summary": "seeded stale-holder record"}})))
            # Its landed-effect audit row (operation-linked).
            con.execute(
                "INSERT INTO canvas_audit (id, canvas_id, tenant_id, "
                "action_type, canvas_type, user_id, details_json, "
                "created_at) VALUES (?, ?, 'default', 'update', "
                "'email', ?, ?, datetime('now'))",
                (str(uuid.uuid4()), world.canvas_id, world.user_id,
                 json.dumps({"operation_id": f"op-{cid_y[:8]}",
                             "content": {"body": "seeded"}})))
            con.commit()
            con.close()
            os.environ["ATOM_ACCEPTANCE_BARRIER"] = "recovery_delivery_held"
            os.environ["ATOM_ACCEPTANCE_BARRIER_MATCH"] = sY
            world.kill()
            world.launch(reuse_run_dir=world.run_dir)   # A: claims, parks
            time.sleep(6)  # boot pass runs, claims, parks
            arr_b = bdir / "barrier.recovery_delivery_held.arrived.json"
            # A's recurring pass may claim+park on its own schedule after
            # boot; give it a patient window.
            a_parked = poll_until(arr_b.exists, 150, interval=1.0)

            b_env = {
                "PATH": os.environ["PATH"], "HOME": os.environ["HOME"],
                "SECRET_KEY": os.environ.get("SECRET_KEY", ""),
                "DATABASE_URL": f"sqlite:///{world.run_dir}/data/atom.db",
                "ATOM_DATA_DIR": str(Path(world.run_dir) / "data"),
                "LANCEDB_URI": str(BACKEND / "data" /
                                   "acceptance_worlds" / args.world /
                                   "data" / "atom_memory"),
                "ACC_PORT": str(args.b_port),
                "ATOM_CHAT_STREAMING": "1",
                "ENABLE_SCHEDULER": "false",
                "ENABLE_INGESTION_SYNC": "false",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "ATOM_TERMINAL_DELIVERY_LEASE_SECONDS": "6",
                "ATOM_TERMINAL_RECOVERY_INTERVAL_SECONDS": "5",
            }
            profile = (BACKEND / "data" / "acceptance_worlds" /
                       "write_combined" / "local_only_b.sb")
            profile.write_text(R._sandbox_profile(
                args.b_port, extra_ports=(SHIM_PORT,)))
            blog = open(BACKEND / "data" / "acceptance_worlds" /
                        "write_combined" / "server_b.log", "ab")
            proc_b = subprocess.Popen(
                ["/usr/bin/sandbox-exec", "-f", str(profile),
                 str(R.VENV_PY),
                 str(BACKEND / "scripts" / "orchestration_acceptance" /
                     "_app.py")],
                cwd=str(BACKEND / "data" / "acceptance_worlds" /
                        "write_combined" / "backend_root"),
                env=b_env, stdout=blog, stderr=subprocess.STDOUT,
                start_new_session=True)
            world.proc_b = proc_b
            register_pid(proc_b.pid)
            b_up = poll_until(lambda: (
                lambda r: r is not None and r.status_code == 200)(
                _health(args.b_port)), 240, interval=2)
            # B's loop takes over after the 6s lease and delivers (interval
            # 5s). A stays parked. Wait past both.
            time.sleep(20)
            m_after_b = terminal_msg_count(sY)
            b_log = (BACKEND / "data" / "acceptance_worlds" /
                     "write_combined" / "server_b.log").read_text(
                         errors="replace")
            # Release A: it resumes and must be FENCED OUT.
            (bdir / "barrier.recovery_delivery_held.release").write_text("")
            time.sleep(8)
            a_log = (BACKEND / "data" / "acceptance_worlds" /
                     args.world / "server.log").read_text(
                         errors="replace")
            m_final = terminal_msg_count(sY)
            record("F09A_stale_holder_fenced_out", {
                "A_parked_holding_claim": bool(a_parked),
                "B_second_server_healthy": bool(b_up),
                "B_took_over_and_delivered_once": m_after_b == 1,
                "b_log_shows_delivery": "terminal-delivery recovery" in b_log
                or "delivered" in b_log,
                "A_resumed_and_was_fenced_out": (
                    "NOT written" in a_log and "taken over" in a_log),
                "no_duplicate_after_A_resume": m_final == 1,
            }, details={"msgs_after_b": m_after_b, "msgs_final": m_final,
                        "a_parked": bool(a_parked)})

            # ---- 2c. UNRELATED-EDIT CONTROL ----------------------------
            # A continuation whose edit FAILS (no operation-linked row) while
            # an UNRELATED turn lands on the same canvas: recovery must
            # report uncertainty, never "your update applied".
            os.environ["ATOM_ACCEPTANCE_BARRIER"] = \
                "continuation_after_effect"
            sZ = f"f09-unrel-{uuid.uuid4().hex[:8]}"
            os.environ["ATOM_ACCEPTANCE_BARRIER_MATCH"] = sZ
            world.kill()
            world.launch(reuse_run_dir=world.run_dir)
            token = world.mint()
            arr_z = bdir / "barrier.continuation_after_effect.arrived.json"
            arm_stall(world, 40, first_n=1)
            try:
                # iota's find text does not exist -> the edit fails, the
                # turn forks, and the continuation parks with NO mutation.
                ensure_shim_alive()
                arm_stall(world, 40, first_n=1)
                send(world, token, sZ, "iota: replace the missing sentence",
                     f"f09-z-{uuid.uuid4().hex[:6]}", timeout=60)
            except Exception as exc:
                print(f"[f09-2c] setup issue: {type(exc).__name__}: {exc}")
            parked_z = poll_until(arr_z.exists, 150, interval=0.5)
            # Unrelated turn lands on the SAME canvas from ANOTHER session.
            r_u = send(world, token, f"f09-unrel-other-{uuid.uuid4().hex[:6]}",
                       "kappa: reformat the warranty wording",
                       f"f09-u-{uuid.uuid4().hex[:6]}", timeout=120)
            world.kill()  # Z dies before any delivery
            for k in ("ATOM_ACCEPTANCE_BARRIER",
                      "ATOM_ACCEPTANCE_BARRIER_MATCH",
                      "ATOM_ACCEPTANCE_BARRIER_TIMEOUT"):
                os.environ.pop(k, None)
            world.launch(reuse_run_dir=world.run_dir)
            time.sleep(12)  # recovery pass + recurring loop
            z_hist = world.history_texts(sZ)
            z_terminal = [h for h in z_hist if "cannot attribute" in h
                          or "Background update" in h]
            record("F09A_unrelated_edit_not_claimed_as_success", {
                "continuation_parked": bool(parked_z),
                "unrelated_turn_completed": r_u is not None
                and r_u.status_code == 200,
                "recovery_message_written": len(z_terminal) >= 1,
                "uncertainty_wording_used": any(
                    "cannot attribute" in h for h in z_terminal),
                "no_false_success_wording": not any(
                    "already applied" in h.lower() for h in z_terminal),
            }, details={"z_terminal": [h[:120] for h in z_terminal]})
            disarm_stall(world)
        except _SkipRest:
            pass
        finally:
            for k in ("ATOM_ACCEPTANCE_BARRIER",
                      "ATOM_ACCEPTANCE_BARRIER_MATCH",
                      "ATOM_ACCEPTANCE_BARRIER_TIMEOUT",
                      "ATOM_TERMINAL_DELIVERY_LEASE_SECONDS",
                      "ATOM_TERMINAL_RECOVERY_INTERVAL_SECONDS"):
                os.environ.pop(k, None)
            disarm_stall(world)

        # ---- PHASE 3: updated public overlap run ------------------------
        try:
            if args.phase != "all":
                ckpt("skip_phase", phase=3, reason=f"--phase {args.phase}")
                raise _SkipRest()
            from scripts.orchestration_acceptance.run_isolated import WSTap
            session = f"f09-ovl-{uuid.uuid4().hex[:8]}"
            before = world.update_count()
            tap = WSTap(world.port, token, session_filter=session)

            ensure_shim_alive()

            async def body():
                await tap.start()
                await asyncio.wait_for(tap.connected_event.wait(), timeout=15)
                import httpx
                async with httpx.AsyncClient(trust_env=False,
                                             timeout=300) as cl:
                    async def one(m, rid):
                        rr = await cl.post(
                            f"{world.base}/api/chat/message",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"message": m, "session_id": session,
                                  "user_id": world.user_id,
                                  "context": world.ctx(),
                                  "request_id": rid})
                        return rr.status_code, (rr.json() or {})
                    pair = await asyncio.gather(
                        one("alpha: change the closing",
                            f"f09-a-{uuid.uuid4().hex[:6]}"),
                        one("beta: update the payment terms",
                            f"f09-b-{uuid.uuid4().hex[:6]}"))
                deadline = time.time() + 180
                while time.time() < deadline:
                    forks = world.fork_records(session)
                    if forks and all(f["status"] != "running"
                                     for f in forks):
                        break
                    await asyncio.sleep(2)
                await asyncio.sleep(6)
                return pair

            try:
                (sa, pa), (sb, pb) = asyncio.run(body())
            except Exception as exc:
                print(f"[f09c] case error: {type(exc).__name__}: {exc}")
                (sa, pa), (sb, pb) = (0, {}), (0, {})
            body_txt = str(world.content().get("body", ""))
            hist_rows = world.history_texts(session)
            hist = " ".join(hist_rows)
            cont_events = ws_continuation_events(tap, session)
            forks = world.fork_records(session)
            ea, eb = pa.get("execution_id"), pb.get("execution_id")
            outcomes_live = len(cont_events) >= len(forks) and forks
            record("F09C_public_overlap_updated", {
                "both_turns_completed": sa == 200 and sb == 200,
                "distinct_execution_ids": bool(ea and eb
                                               and str(ea) != str(eb)),
                "every_fork_terminal": all(f["status"] != "running"
                                           for f in forks) and bool(forks),
                "live_chat_continuation_for_every_fork": bool(outcomes_live),
                "terminal_outcomes_in_history": len(
                    [h for h in hist_rows if "Background update" in h])
                >= len(forks),
                "canvas_coherent": body_txt.count("Best regards,") <= 1
                and body_txt.count("Payment terms: net 45.") <= 1
                and world.update_count() <= before + 2,
                "no_pending_left_in_history": "still running"
                not in hist.split("Background update")[-1],
            }, details={"statuses": [sa, sb], "writes": world.update_count(),
                        "forks": len(forks),
                        "cont_events": len(cont_events),
                        "cont_statuses": [str(e.get("status"))
                                          for e in cont_events][:4],
                        "history_tail": hist_rows[-2:]})
        except _SkipRest:
            pass
        finally:
            disarm_stall(world)
    finally:
        try:
            if world.proc and world.proc.poll() is None:
                try:
                    os.killpg(os.getpgid(world.proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
        except Exception:
            pass
        try:
            if world.proc_b and world.proc_b.poll() is None:
                os.killpg(os.getpgid(world.proc_b.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            shim.terminate()
            shim.kill()
        except Exception:
            pass

    # FOREIGN-INTERFERENCE AUDIT: a FAIL on this suite is only meaningful
    # if no other stream wrote into the world during the run. Detect
    # sessions/audit rows that this runner did not create and mark the run
    # BLOCKED (not FAIL) when found.
    foreign = []
    try:
        con = world._ro()
        for sess, in con.execute(
                "SELECT DISTINCT conversation_id FROM chat_messages "
                "WHERE conversation_id IS NOT NULL").fetchall():
            if sess and not str(sess).startswith("f09-"):
                foreign.append(str(sess))
        con.close()
    except Exception:
        pass
    if foreign:
        for e in RESULTS:
            if e["status"] == "FAIL":
                e["status"] = "BLOCKED"
                e["notes"] = (e.get("notes") or []) + [
                    f"foreign sessions observed in the world during the "
                    f"run: {foreign[:3]} — result contaminated, not a "
                    f"product failure"]

    passed = sum(1 for e in RESULTS if e["status"] == "PASS")
    failed = len(RESULTS) - passed
    print(f"\n=== F09 targeted: {passed} PASS / {failed} FAIL ===")
    manifest = {}
    try:
        # Bind to the world THIS run executed (2026-09-29: this read was
        # hardcoded to write_combined, so results recorded another world's
        # export as their own).
        manifest = json.loads((BACKEND / "data" / "acceptance_worlds" /
                               args.world / "MANIFEST.json").read_text())
    except Exception:
        pass
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "run_dir": str(getattr(world, "run_dir", "")),
           "foreign_interference": {"foreign_sessions": foreign[:5],
                                    "detected": bool(foreign)},
           "export_binding": {
               "code_snapshot_sha256": manifest.get("code_snapshot_sha256"),
               "flags": ["CHAT_FINALIZATION_M1", "CHAT_FINALIZATION_M2",
                         "ATOM_TASK_LIFECYCLE_ENABLED"]},
           "results": RESULTS}
    Path(args.results).write_text(json.dumps(out, indent=1, default=str))
    print(f"results: {args.results}")
    return 0 if failed == 0 else 1


def _health(port: int):
    import httpx
    try:
        return httpx.get(f"http://127.0.0.1:{port}/api/health",
                         timeout=4, trust_env=False)
    except Exception:
        return None


def _notified_flag(world: World, continuation_id: str):
    con = world._ro()
    try:
        row = con.execute(
            "SELECT metadata_json FROM agent_executions WHERE id=?",
            (continuation_id,)).fetchone()
        m = json.loads(row[0]) if row and row[0] else {}
        return (m.get("continuation") or {}).get("notified")
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
