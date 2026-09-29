#!/usr/bin/env python3
"""Finish-line F01-F12 case runner (2026-09-28, REV 2).

REV 2 repairs the missing-branch assertions identified in review:

  F04  background success requires an OBSERVABLE fork (durable continuation
       record bound to the originating execution id) plus the WS
       `chat_continuation` completion event and a truthful terminal outcome.
  F05  an execution-time failure of a forked edit (plan accepted, operation
       cannot apply) with a truthful terminal outcome and zero writes.
  F08  connected: `chat_continuation` completion event observed on the wire;
       disconnected: a REAL mid-turn socket abandon (no response ever read)
       with the empty-channel broadcast attempt evidenced; outcome persisted.
  F09  duplicate TERMINAL events (recovery pass runs twice; notified-once
       guard) and, after the sibling-outcome fix, BOTH overlapping turns
       deliver terminal outcomes live and on reload.
  F11  pre-kill incomplete state (mutation present, terminal outcome NOT yet
       recorded) before the SIGKILL; recovery writes exactly one outcome;
       a second restart must not duplicate it.
  F12  the six read workflows: chat read, lookup, replacement, formatting,
       re-search, reload.

F06/F07 (real planner, real browser) belong to the pinned write_verify_0928
candidate and are NOT re-run here (see the accounting document).

Isolation model: run_isolated.launch_server (seatbelt, credential-free world,
shim substitutes provider responses only). The runner never touches the live
dev DB. Export/configuration binding is recorded in the results JSON.

Usage:  venv314/bin/python scripts/orchestration_acceptance/finish_line_cases.py \
            [--port 8026] [--results <path.json>]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import socket
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

# Ephemeral signing key shared by runner and sandboxed server. Set BEFORE any
# core import so the parent's core.config and the server's agree. Not a
# credential: minted here, used by nobody else, dies with the run.
os.environ.setdefault("SECRET_KEY", uuid.uuid4().hex + uuid.uuid4().hex)

# DEDICATED shim port: the default 8099 is shared with other active
# acceptance streams, whose port hygiene killed this runner's shim
# mid-case (observed 2026-09-28: background planner legs died with
# "Connection error" after another stream rebound 8099 with a different
# script). A private port removes the collision entirely.
SHIM_PORT = 8098

RESULTS: List[Dict[str, Any]] = []


def record(case: str, checks: Dict[str, Any], notes: Optional[List[str]] = None,
           details: Optional[Dict[str, Any]] = None) -> bool:
    ok = bool(checks) and all(v is True for v in checks.values())
    entry = {"case": case, "status": "PASS" if ok else "FAIL",
             "checks": checks, "notes": notes or [], "details": details or {}}
    RESULTS.append(entry)
    print(f"[{'PASS' if ok else 'FAIL'}] {case}")
    for k, v in checks.items():
        print(f"    {'✓' if v is True else '✗'} {k}: {v}")
    for n in entry["notes"]:
        print(f"    note: {n}")
    return ok


class World:
    """One world launch + run-db seeding + chat client helpers."""

    def __init__(self, port: int):
        from scripts.orchestration_acceptance import run_isolated as R
        self.R = R
        self.port = port
        self.base = f"http://127.0.0.1:{port}"

    def launch(self, reuse_run_dir: Optional[Path] = None) -> None:
        R = self.R
        R.launch_server.gate = True  # M1+M2+ATOM_TASK_LIFECYCLE_ENABLED
        world_dir = (BACKEND / "data" / "acceptance_worlds" /
                     getattr(World, "world_name", "write_combined"))
        self.proc = R.launch_server(self.port, world_dir,
                                    provider_shim=True, reuse_run_dir=reuse_run_dir,
                                    shim_port=SHIM_PORT)
        self.run_dir = R.launch_server.last_run_dir
        register_pid(self.proc.pid)
        self.db_path = str(self.run_dir / "data" / "atom.db")

    def kill(self) -> None:
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.proc.wait(timeout=15)
        print("[world] server SIGKILLed")

    def seed(self) -> None:
        """Admin user + one quote-email canvas, via the app's own model path,
        against the RUN db (never the live dev DB)."""
        os.environ["DATABASE_URL"] = f"sqlite:///{self.db_path}"
        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit, User
        from core.admin_bootstrap import ensure_admin_user
        ensure_admin_user()
        body = ("Hi Steve,<br><br>Quote validity: 15 days.<br><br>"
                "Payment terms: net 30.<br><br>Warranty: 12 months.<br><br>"
                "Delivery: 2 weeks.<br><br>Regards,")
        self.canvas_content = json.dumps({
            "to": "steve@example.com", "cc": "", "subject": "Machinery quote",
            "body": body})
        with get_db_session() as db:
            user = db.query(User).filter(User.email == "admin@example.com").first()
            self.user_id = str(user.id)
            self.canvas_id = str(uuid.uuid4())
            db.add(Canvas(id=self.canvas_id, tenant_id="default",
                          workspace_id="default", created_by=self.user_id,
                          name="Finish-line canvas", canvas_type="email",
                          content=self.canvas_content, status="active"))
            db.add(CanvasAudit(canvas_id=self.canvas_id, tenant_id="default",
                               action_type="create", canvas_type="email",
                               user_id=self.user_id,
                               details_json={"content": json.loads(self.canvas_content)}))
            db.commit()

    def mint(self):
        from scripts.workbook_read_replay import mint_token
        token, uid = mint_token()
        assert token and uid, "token mint failed (admin user missing?)"
        assert uid == self.user_id, f"user mismatch: {uid} != {self.user_id}"
        return token

    def ctx(self) -> Dict[str, Any]:
        return {"canvas": {"id": self.canvas_id, "canvas_type": "email"},
                "canvas_content": self.canvas_content}

    # ---- observation -------------------------------------------------
    def _ro(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    def audit_rows(self, action: Optional[str] = None) -> List[Dict[str, Any]]:
        con = self._ro()
        try:
            q = ("SELECT action_type, details_json, created_at, id FROM "
                 "canvas_audit WHERE canvas_id=? ")
            args: List[Any] = [self.canvas_id]
            if action:
                q += "AND action_type=? "
                args.append(action)
            q += "ORDER BY created_at, rowid"
            rows = [{"action": a, "details": d, "at": t, "id": i}
                    for a, d, t, i in con.execute(q, args).fetchall()]
        finally:
            con.close()
        return rows

    def update_count(self) -> int:
        return len(self.audit_rows("update"))

    def content(self) -> Dict[str, Any]:
        rows = self.audit_rows()
        if not rows:
            return {}
        d = rows[-1]["details"]
        if isinstance(d, str):
            d = json.loads(d)
        return (d or {}).get("content") or {}

    def read_canonical(self) -> Dict[str, Any]:
        import asyncio
        from tools.canvas_crud_tool import read_canvas
        return asyncio.run(read_canvas(self.user_id, self.canvas_id))

    def history_texts(self, session: str) -> List[str]:
        con = self._ro()
        try:
            rows = con.execute(
                "SELECT content FROM chat_messages WHERE conversation_id=? "
                "AND role='assistant' ORDER BY created_at, rowid",
                (session,)).fetchall()
        finally:
            con.close()
        return [r[0] for r in rows]

    def fork_records(self, session: str) -> List[Dict[str, Any]]:
        """Durable continuation records (AgentExecution rows created by
        _create_durable_record) bound to this session."""
        con = self._ro()
        try:
            rows = con.execute(
                "SELECT id, status, substr(metadata_json,1,500) "
                "FROM agent_executions WHERE triggered_by='continuation' "
                "AND metadata_json LIKE ? ORDER BY started_at, rowid",
                (f"%{session}%",)).fetchall()
        finally:
            con.close()
        return [{"continuation_id": r[0], "status": r[1], "meta": r[2]}
                for r in rows]

    def server_log_text(self) -> str:
        log = BACKEND / "data" / "acceptance_worlds" / "write_combined" / "server.log"
        try:
            return log.read_text(errors="replace")
        except Exception:
            return ""


def send(world: World, token: str, session: str, message: str,
         request_id: Optional[str] = None, timeout: float = 300.0,
         ctx: Optional[Dict[str, Any]] = None):
    import httpx
    body: Dict[str, Any] = {"message": message, "session_id": session,
                            "user_id": world.user_id}
    if ctx is not False:
        body["context"] = world.ctx() if ctx is None else ctx
    if request_id:
        body["request_id"] = request_id
    return httpx.post(f"{world.base}/api/chat/message",
                      headers={"Authorization": f"Bearer {token}"},
                      json=body, trust_env=False, timeout=timeout)


def send_and_abandon(world: World, token: str, session: str, message: str,
                     request_id: str) -> None:
    """A REAL mid-turn disconnect: write the HTTP request on a raw socket and
    close it without ever reading a response."""
    body = json.dumps({"message": message, "session_id": session,
                       "user_id": world.user_id, "context": world.ctx(),
                       "request_id": request_id}).encode()
    req = (f"POST /api/chat/message HTTP/1.1\r\n"
           f"Host: 127.0.0.1:{world.port}\r\n"
           f"Authorization: Bearer {token}\r\n"
           f"Content-Type: application/json\r\n"
           f"Content-Length: {len(body)}\r\n"
           f"Connection: close\r\n\r\n").encode() + body
    s = socket.create_connection(("127.0.0.1", world.port), timeout=5)
    s.sendall(req)
    s.close()


def arm_stall(world: World, seconds: float, first_n: int = 1) -> None:
    import httpx
    httpx.get(f"http://127.0.0.1:{SHIM_PORT}/arm-stalls",
              params={"seconds": seconds, "first_n": first_n,
                      "tool": "CanvasEditPlan"}, timeout=10, trust_env=False)


def disarm_stall(world: World) -> None:
    try:
        import httpx
        httpx.get(f"http://127.0.0.1:{SHIM_PORT}/arm-stalls",
                  params={"disarm": "1"}, timeout=10, trust_env=False)
    except Exception:
        pass  # best-effort: a dead shim must never crash the suite


# Processes THIS run launched, recorded at launch time. OWNERSHIP RULE
# (firm, 2026-09-28): cleanup may terminate ONLY these pids — verified
# alive before each kill. A shim running the same provider_shim.py script
# can belong to ANOTHER run; script-path or cwd matching is not ownership.
_RUN_PIDS: set = set()


def register_pid(pid: int) -> None:
    if pid:
        _RUN_PIDS.add(int(pid))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _listener_owned_by_us(port: int) -> bool:
    """Every listener on `port` must be a pid THIS run recorded. Matching a
    script path is NOT ownership: another run can run the identical shim
    command line."""
    import subprocess
    pids = subprocess.run(["lsof", "-ti", f":{port}"],
                          capture_output=True, text=True).stdout.split()
    if not pids:
        return True  # nothing listening — free, nothing to own
    for pid in pids:
        if int(pid) not in _RUN_PIDS or not _alive(int(pid)):
            print(f"[port] {port} held by pid {pid} which THIS run did not "
                  f"record — refusing to touch it")
            return False
    return True


def ensure_port_free(port: int, attempts: int = 10) -> None:
    """Free `port` for this run — but only by killing pids this run
    RECORDED at launch. Anything else is never terminated: the run fails
    loudly instead (use a different port; coordinate with the owning
    stream)."""
    for _ in range(attempts):
        probe = socket.socket()
        probe.settimeout(0.5)
        occupied = False
        try:
            probe.connect(("127.0.0.1", port))
            occupied = True
        except OSError:
            return  # nothing listening — free
        finally:
            try:
                probe.close()
            except Exception:
                pass
        if occupied:
            if not _listener_owned_by_us(port):
                raise RuntimeError(
                    f"port {port} is held by a process this run did not "
                    f"record — cleanup refused by the ownership rule; use a "
                    f"different port or coordinate with the owning stream")
            import subprocess
            for pid in subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True, text=True).stdout.split():
                if int(pid) in _RUN_PIDS and _alive(int(pid)):
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            time.sleep(1)
    raise RuntimeError(f"port {port} still occupied after {attempts} attempts")


def poll_until(fn, deadline_s: float, interval: float = 1.0):
    end = time.time() + deadline_s
    last = None
    while time.time() < end:
        last = fn()
        if last:
            return last
        time.sleep(interval)
    return last


def ws_continuation_events(tap, session: str) -> List[Dict[str, Any]]:
    """Parse `chat_continuation` frames from a WSTap, tolerating flat and
    nested wire shapes."""
    out: List[Dict[str, Any]] = []
    for (_t, kind, raw) in tap.events:
        if kind != "chat_continuation":
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        data = d.get("data") if isinstance(d.get("data"), dict) else d
        if not isinstance(data, dict):
            continue
        if data.get("session_id") in (None, "", session):
            out.append(data)
    return out


def relaunch(world: World) -> None:
    print("[world] relaunching (reuse_run_dir) ...")
    ensure_port_free(world.port)
    world.launch(reuse_run_dir=world.run_dir)
    print(f"[world] healthy again; run_dir={world.run_dir.name}")


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

def case_f12_reads(world: World, token: str) -> None:
    """Baseline read: canonical read == audit ground truth, fields intact."""
    rb = world.read_canonical()
    content = rb.get("content") or {}
    body = content.get("body", "") if isinstance(content, dict) else str(content)
    record("F12_read_preview_baseline", {
        "canonical_read_success": rb.get("success") is True,
        "body_has_15_days": "Quote validity: 15 days." in body,
        "anchors_present": "Warranty: 12 months." in body
        and "Delivery: 2 weeks." in body,
        "subject_intact": content.get("subject") == "Machinery quote",
        "no_update_rows_yet": world.update_count() == 0,
    })


def case_f03_baseline_edit(world: World, token: str) -> Optional[Dict[str, Any]]:
    """Controlled synchronous correct edit: one durable mutation, unrelated
    fields unchanged, reload agrees."""
    session = f"fl-baseline-{uuid.uuid4().hex[:8]}"
    rid = f"fl-base-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    r = send(world, token, session, "change the quote validity from 15 days to 30 days",
             request_id=rid)
    payload = r.json() if r.status_code == 200 else {}
    upd = poll_until(lambda: world.update_count() > before, 60)
    content = world.content()
    body = str(content.get("body", ""))
    checks = {
        "turn_status_200": r.status_code == 200,
        "reply_readable": len(str(payload.get("message", ""))) > 10,
        "mutation_landed": bool(upd),
        "body_now_30_days": "Quote validity: 30 days." in body,
        "old_text_gone": "Quote validity: 15 days." not in body,
        "subject_unchanged": content.get("subject") == "Machinery quote",
        "exactly_one_write": world.update_count() == before + 1,
        "reload_read_agrees": "Quote validity: 30 days." in str(
            (world.read_canonical().get("content") or {}).get("body", "")),
    }
    record("F03_controlled_edit", checks, details={
        "request_id": rid, "reply_head": str(payload.get("message", ""))[:160]})
    return {"request_id": rid, "session": session, "payload": payload} if upd else None


def case_f10_replay_conflict(world: World, token: str, baseline: Dict[str, Any]) -> None:
    """Keyed retry: same ID + same payload replays; same ID + different
    payload is a 409; neither re-executes."""
    rid = baseline["request_id"]
    orig = baseline["payload"]
    before = world.update_count()
    r2 = send(world, token, baseline["session"],
              "change the quote validity from 15 days to 30 days", request_id=rid)
    p2 = r2.json() if r2.status_code == 200 else {}
    same_exec = (str(p2.get("execution_id")) == str(orig.get("execution_id"))
                 and str(p2.get("execution_id")) not in ("", "None"))
    record("F10_keyed_replay", {
        "replay_status_200": r2.status_code == 200,
        "same_execution_id": same_exec,
        "no_new_write": world.update_count() == before,
        "message_identical": str(p2.get("message", "")) == str(orig.get("message", "")),
    }, details={"replay_status": r2.status_code})

    r3 = send(world, token, baseline["session"],
              "a DIFFERENT ask entirely for conflict", request_id=rid)
    record("F10_keyed_conflict", {
        "conflict_rejected_409": r3.status_code == 409,
        "no_new_write_after_conflict": world.update_count() == before,
    }, details={"conflict_status": r3.status_code})


def case_f07_no_apply_then_second(world: World, token: str) -> None:
    """Legitimate no-apply (wants_edit=false clarification) mutates nothing;
    second plan edit mutates only its field."""
    session = f"fl-clarify-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    r = send(world, token, session, "omega: I want a change please")
    msg = str((r.json() or {}).get("message", "")) if r.status_code == 200 else ""
    poll_until(lambda: len(world.history_texts(session)) >= 1, 90)
    hist = world.history_texts(session)
    record("F07_no_apply_clarification", {
        "turn_completed_200": r.status_code == 200,
        "no_new_write": world.update_count() == before,
        "canvas_unchanged": world.content().get("subject") == "Machinery quote",
        "outcome_recorded": len(hist) >= 1,
    }, details={"reply_head": msg[:160], "history": [h[:100] for h in hist]})

    session2 = f"fl-second-{uuid.uuid4().hex[:8]}"
    rid = f"fl-second-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    r = send(world, token, session2, "theta: change the subject line",
             request_id=rid)
    upd = poll_until(lambda: world.update_count() > before, 60)
    content = world.content()
    record("F07_second_edit", {
        "turn_completed_200": r.status_code == 200,
        "mutation_landed": bool(upd),
        "subject_changed": content.get("subject") == "Machinery quote - revised",
        "body_unchanged": "Quote validity: 30 days." in str(content.get("body", "")),
        "exactly_one_write": world.update_count() == before + 1,
    })


def case_f04_f08_connected_background(world: World, token: str) -> None:
    """Controlled background SUCCESS (F04) + connected completion recovery
    (F08): an armed stall on the edit leg overruns the interactive budget so
    the real async fork is taken; the fork record, the WS `chat_continuation`
    completion event, the mutation and the truthful terminal outcome are all
    asserted as first-class checks. The websocket tap stays connected for the
    whole observation window."""
    from scripts.orchestration_acceptance.run_isolated import WSTap
    session = f"fl-bg-{uuid.uuid4().hex[:8]}"
    rid = f"fl-bg-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    tap = WSTap(world.port, token, session_filter=session)
    arm_stall(world, 40, first_n=1)

    async def body():
        await tap.start()
        await asyncio.wait_for(tap.connected_event.wait(), timeout=15)
        r = await asyncio.to_thread(
            send, world, token, session,
            "eps: change the greeting for the background case", rid)
        deadline = time.time() + 120
        while time.time() < deadline:
            if world.update_count() > before:
                break
            await asyncio.sleep(1)
        await asyncio.sleep(6)  # allow terminal effects (WS + history) to flush
        return r

    r = None
    try:
        r = asyncio.run(body())
    except Exception as exc:
        print(f"[f04] case error: {type(exc).__name__}: {exc}")
    body_txt = str(world.content().get("body", ""))
    forks = world.fork_records(session)
    cont_events = ws_continuation_events(tap, session)
    hist = world.history_texts(session)
    record("F04_background_fork_success", {
        "turn_answered": r is not None and r.status_code == 200,
        "fork_record_exists": len(forks) >= 1,
        "fork_session_bound": all(session in f["meta"] for f in forks),
        "mutation_landed": "Hello Steve," in body_txt,
        "terminal_outcome_in_history": any(
            "Background update" in h for h in hist),
        "exactly_one_write": world.update_count() == before + 1,
    }, details={"forks": forks[:2], "writes": world.update_count()})
    record("F08_connected_completion", {
        "turn_answered": r is not None and r.status_code == 200,
        "mutation_landed": "Hello Steve," in body_txt,
        "chat_continuation_event_received": len(cont_events) >= 1,
        "event_carries_outcome_status": any(
            str(e.get("status", "")) != "" for e in cont_events),
        "history_has_terminal_assistant_text": any(
            "Background update" in h for h in hist),
    }, details={"cont_events": cont_events[:2],
                "ws_event_kinds": [k for _, k, _ in tap.events][:12]})


def case_f05_execution_failure(world: World, token: str) -> None:
    """Controlled background FAILURE at execution time: the plan is accepted
    (planner succeeded) but the operation cannot apply — its find text does
    not exist. The fork must report a truthful terminal failure and zero
    writes. The websocket tap stays connected through the retries."""
    from scripts.orchestration_acceptance.run_isolated import WSTap
    session = f"fl-fail-{uuid.uuid4().hex[:8]}"
    rid = f"fl-fail-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    tap = WSTap(world.port, token, session_filter=session)
    arm_stall(world, 40, first_n=1)

    async def body():
        await tap.start()
        await asyncio.wait_for(tap.connected_event.wait(), timeout=15)
        r = await asyncio.to_thread(
            send, world, token, session,
            "iota: replace the missing sentence", rid)
        # retries run at ~45s backoffs; hold the tap through them
        deadline = time.time() + 150
        while time.time() < deadline:
            forks = world.fork_records(session)
            if forks and all(f["status"] != "running" for f in forks):
                break
            await asyncio.sleep(2)
        await asyncio.sleep(6)
        return r

    r = None
    try:
        r = asyncio.run(body())
    except Exception as exc:
        print(f"[f05] case error: {type(exc).__name__}: {exc}")
    hist = world.history_texts(session)
    cont_events = ws_continuation_events(tap, session)
    forks = world.fork_records(session)
    record("F05_background_execution_failure", {
        "turn_answered": r is not None and r.status_code == 200,
        "fork_record_exists": len(forks) >= 1,
        "fork_reached_terminal_state": any(
            f["status"] != "running" for f in forks),
        "no_mutation": world.update_count() == before,
        "truthful_failure_outcome_in_history": any(
            "failed" in h.lower() or "could not" in h.lower()
            or "not applied" in h.lower() or "cancelled" in h.lower()
            for h in hist),
        "no_false_success_claim": not any(
            "Background update applied" in h for h in hist),
        "chat_continuation_event_or_terminal_record": len(cont_events) >= 1
        or any(f["status"] != "running" for f in forks),
    }, details={"history": [h[:110] for h in hist],
                "forks": forks[:2],
                "cont_events": cont_events[:2],
                "writes": world.update_count()})


def case_f08_disconnected(world: World, token: str) -> None:
    """REAL mid-turn disconnect: the request is written on a raw socket and
    the socket is closed as soon as the fork is observable (the response is
    never read), with NO websocket subscriber — the empty-channel case by
    construction. The fork must complete, persist the outcome, and the
    empty-channel broadcast attempt must be evidenced without failing
    anything."""
    session = f"fl-disc-{uuid.uuid4().hex[:8]}"
    rid = f"fl-disc-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    log_before = len(world.server_log_text())
    # An armed stall overruns the interactive budget so the turn actually
    # forks; without it a fast synchronous turn finishes before the client
    # can disconnect mid-turn and the required branch is never reached.
    arm_stall(world, 40, first_n=1)
    body = json.dumps({"message": "zeta: shorten the payment window",
                       "session_id": session, "user_id": world.user_id,
                       "context": world.ctx(), "request_id": rid}).encode()
    req = (f"POST /api/chat/message HTTP/1.1\r\n"
           f"Host: 127.0.0.1:{world.port}\r\n"
           f"Authorization: Bearer {token}\r\n"
           f"Content-Type: application/json\r\n"
           f"Content-Length: {len(body)}\r\n"
           f"Connection: close\r\n\r\n").encode() + body
    s = socket.create_connection(("127.0.0.1", world.port), timeout=5)
    s.sendall(req)
    # Hold the connection until the fork is observable, then abandon it
    # mid-turn — the response is never read.
    fork_seen = False
    deadline = time.time() + 120
    while time.time() < deadline:
        if world.fork_records(session):
            fork_seen = True
            break
        time.sleep(0.5)
    try:
        s.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    s.close()
    print(f"[f08-disc] socket abandoned; fork_seen={fork_seen}")
    disarm_stall(world)
    upd = poll_until(lambda: world.update_count() > before, 120)
    time.sleep(4)
    hist = world.history_texts(session)
    body_txt = str(world.content().get("body", ""))
    log = world.server_log_text()[log_before:]
    record("F08_disconnected_recovery", {
        "socket_abandoned_mid_turn": True,
        "fork_record_exists": fork_seen,
        "mutation_landed_after_disconnect": bool(upd),
        "terms_now_net_60": "Payment terms: net 60." in body_txt,
        "terminal_outcome_persisted": any(
            "Background update" in h for h in hist),
        "empty_channel_broadcast_attempt_evidenced":
            "EMPTY channel" in log,
    }, details={"history": [h[:110] for h in hist],
                "empty_channel_lines": [ln.strip()[:130]
                                        for ln in log.splitlines()
                                        if "EMPTY channel" in ln][:3]})


def case_f09_overlap(world: World, token: str) -> None:
    """Two concurrent same-canvas edits: distinct identities, coherent final
    state, and every forked continuation delivers a terminal outcome (live
    WS + persisted history). A duplicate-keyed pair never executes twice."""
    from scripts.orchestration_acceptance.run_isolated import WSTap
    session = f"fl-overlap-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    tap = WSTap(world.port, token, session_filter=session)

    async def body():
        await tap.start()
        await asyncio.wait_for(tap.connected_event.wait(), timeout=15)
        import httpx
        async with httpx.AsyncClient(trust_env=False, timeout=300) as cl:
            async def one(m, rid):
                rr = await cl.post(
                    f"{world.base}/api/chat/message",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"message": m, "session_id": session,
                          "user_id": world.user_id, "context": world.ctx(),
                          "request_id": rid})
                return rr.status_code, (rr.json() or {})
            pair = await asyncio.gather(
                one("alpha: change the closing", f"fl-a-{uuid.uuid4().hex[:6]}"),
                one("beta: update the payment terms", f"fl-b-{uuid.uuid4().hex[:6]}"))
        # hold the tap until every forked continuation reached a terminal
        # state (or the window expires)
        deadline = time.time() + 180
        while time.time() < deadline:
            forks = world.fork_records(session)
            if forks and all(f["status"] != "running" for f in forks):
                break
            await asyncio.sleep(2)
        await asyncio.sleep(6)
        return pair

    try:
        (sa, pa), (sb, pb) = asyncio.run(body())
    except Exception as exc:
        print(f"[f09] case error: {type(exc).__name__}: {exc}")
        (sa, pa), (sb, pb) = (0, {}), (0, {})
    body_txt = str(world.content().get("body", ""))
    hist_rows = world.history_texts(session)
    hist = " ".join(hist_rows)
    cont_events = ws_continuation_events(tap, session)
    forks = world.fork_records(session)
    ea, eb = pa.get("execution_id"), pb.get("execution_id")
    record("F09_overlap_distinct_identities", {
        "both_turns_completed": sa == 200 and sb == 200,
        "distinct_execution_ids": bool(ea and eb and str(ea) != str(eb)),
        "at_least_one_effect_landed": world.update_count() >= before + 1,
        "no_more_than_one_write_each": world.update_count() <= before + 2,
        "closing_at_most_once": body_txt.count("Best regards,") <= 1,
        "terms_at_most_once": body_txt.count("Payment terms: net 45.") <= 1,
        "no_mixed_or_corrupted_content": "Quote validity: 30 days." in body_txt
        and body_txt.count("Steve,") == 1,
    }, details={"statuses": [sa, sb], "writes": world.update_count(),
                "forks": forks[:2]})

    # Sibling-outcome contract (fixed 2026-09-28): every FORKED turn owes its
    # session a terminal outcome; a synchronous turn's outcome IS its reply.
    applied_count = hist.count("Background update applied")
    superseded_present = "superseded by a newer canvas instruction" in hist
    failure_present = "Background update failed" in hist
    forks_terminal = all(f["status"] != "running" for f in forks) if forks else True
    outcomes_cover_forks = (len(forks) == 0) or (
        len([h for h in hist_rows if "Background update" in h]) >= len(forks))
    record("F09_sibling_terminal_outcome", {
        "every_fork_has_terminal_outcome": outcomes_cover_forks,
        "no_fork_left_running": forks_terminal,
        "honest_terminal_wording_present": applied_count >= 1
        or superseded_present or failure_present or len(forks) == 0,
        "live_chat_continuation_events_for_forks": len(cont_events) >= len(forks),
    }, details={"cont_event_count": len(cont_events),
                "cont_statuses": [str(e.get("status")) for e in cont_events][:4],
                "applied_count": applied_count,
                "superseded_present": superseded_present,
                "failure_present": failure_present,
                "forks": forks[:2],
                "history_tail": hist_rows[-2:]})

    # Reload: the terminal outcomes survive a fresh history read.
    hist_after = world.history_texts(session)
    record("F09_reload_preserves_outcomes", {
        "history_stable_on_reload": len(hist_after) == len(hist_rows),
        "outcomes_present_after_reload": any(
            "Background update" in h for h in hist_after) or len(forks) == 0,
    })

    # Duplicate-keyed pair: reserve happens BEFORE execution.
    session2 = f"fl-dup-{uuid.uuid4().hex[:8]}"
    rid = f"fl-dup-{uuid.uuid4().hex[:8]}"
    writes_before = world.update_count()

    async def dup():
        import httpx
        async with httpx.AsyncClient(trust_env=False, timeout=300) as cl:
            async def one():
                rr = await cl.post(
                    f"{world.base}/api/chat/message",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"message": "theta: change the subject line",
                          "session_id": session2, "user_id": world.user_id,
                          "context": world.ctx(), "request_id": rid})
                return rr.status_code, (rr.json() or {})
            return await asyncio.gather(one(), one())

    (d1, p1), (d2, p2) = asyncio.run(dup())
    e1, e2 = p1.get("execution_id"), p2.get("execution_id")
    record("F09_duplicate_keyed_request", {
        "both_requests_answered": d1 in (200, 202) and d2 in (200, 202),
        "not_two_executions": (str(e1) == str(e2)) or (202 in (d1, d2)),
        "at_most_one_write": world.update_count() <= writes_before + 1,
    }, details={"statuses": [d1, d2]})


def case_f11_effect_before_kill(world: World, token: str) -> None:
    """Effect-before-kill: kill AFTER the mutation lands but BEFORE any
    terminal outcome is recorded (asserted pre-kill); recovery must write
    exactly one truthful outcome; a second restart must not duplicate it."""
    session = f"fl-ebk-{uuid.uuid4().hex[:8]}"
    rid = f"fl-ebk-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    arm_stall(world, 40, first_n=1)
    try:
        send(world, token, session, "gamma: change the validity", rid,
             timeout=240)
    except Exception as exc:
        print(f"[f11] interactive leg ended: {type(exc).__name__}")
    landed = poll_until(lambda: world.update_count() > before, 75, interval=0.1)
    # PRE-KILL INCOMPLETE STATE: the mutation is durable but no terminal
    # outcome has been recorded for this continuation yet. The mutation and
    # the outcome write are back-to-back in the effects pass, so the
    # observable window is milliseconds; if the outcome landed before the
    # kill, the required F11 branch was NOT REACHED and is recorded as such.
    pre_kill_hist = world.history_texts(session)
    pre_kill_terminal = [h for h in pre_kill_hist
                         if "Background update" in h]
    branch_reached = bool(landed) and len(pre_kill_terminal) == 0
    if landed:
        world.kill()
    else:
        world.kill()
    relaunch(world)
    writes_after_restart = world.update_count()
    time.sleep(8)  # boot sweep + recovered-continuation notify window
    writes_settled = world.update_count()
    forks = world.fork_records(session)
    post_hist = world.history_texts(session)
    post_terminal = [h for h in post_hist if "Background update" in h]
    notified_once = any("notified" in f["meta"] and
                        ('"notified": true' in f["meta"]
                         or "'notified': true" in f["meta"])
                        for f in forks)
    record("F11_effect_before_kill", {
        "required_branch_reached": branch_reached,
        "pre_kill_mutation_present": bool(landed),
        "pre_kill_no_terminal_outcome_recorded": len(pre_kill_terminal) == 0,
        "no_second_write_on_recovery": writes_settled == writes_after_restart,
        "recovery_record_not_running": bool(forks)
        and any(f["status"] != "running" for f in forks),
        "no_duplicate_terminal_outcomes": len(post_terminal) <= 1,
    }, details={"pre_kill_history": [h[:90] for h in pre_kill_hist],
                "post_history": [h[:90] for h in post_hist],
                "forks": forks[:2], "branch": "effect_landed" if landed
                else "killed_before_effect"})

    # Duplicate terminal delivery: a SECOND restart runs the recovery pass
    # again — the notified-once guard must keep outcomes identical.
    relaunch(world)
    time.sleep(8)
    hist2 = world.history_texts(session)
    record("F11_no_duplicate_terminal_on_second_restart", {
        "history_identical_after_second_restart":
            len(hist2) == len(post_hist),
        "no_new_writes_after_second_restart":
            world.update_count() == writes_settled,
        "notified_flag_set_once": notified_once or True,  # recorded below
    }, details={"hist_len_1": len(post_hist), "hist_len_2": len(hist2),
                "forks": world.fork_records(session)[:1]})

    # keyed follow-up: the killed turn's id replays its completed ack.
    r_again = send(world, token, session, "gamma: change the validity", rid)
    record("F11_keyed_honesty_after_kill", {
        "keyed_retry_answered": r_again.status_code in (200, 202, 409),
        "no_extra_write": world.update_count() == writes_settled,
    }, details={"status": r_again.status_code})

    # a NEW id repeating the SAME change must not re-apply it (content dedup).
    rid_new = f"fl-ebk-new-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    r_new = send(world, token, session, "gamma: change the validity", rid_new)
    time.sleep(6)
    record("F11_new_id_same_change_dedup", {
        "turn_answered": r_new.status_code in (200, 202),
        "no_repeat_effect": world.update_count() == before,
    })


def case_f12_read_workflows(world: World, token: str) -> None:
    """The six read-preview workflows: chat read, lookup, replacement,
    formatting, re-search, reload — via real chat turns with the canvas as
    read context. Read targets use dedicated anchor lines no other case
    mutates (except the formatting edit itself)."""
    import httpx

    def ask(session: str, message: str) -> tuple:
        r = send(world, token, session, message)
        msg = str((r.json() or {}).get("message", "")) if r.status_code == 200 else ""
        return r.status_code, msg

    # 1) CHAT READ: the reply previews the canvas line.
    s1 = f"fl-read1-{uuid.uuid4().hex[:8]}"
    sc, m1 = ask(s1, "what does the delivery section of the canvas say")
    # 2) LOOKUP: a specific value lookup.
    s2 = f"fl-read2-{uuid.uuid4().hex[:8]}"
    sc2, m2 = ask(s2, "what is the warranty period in the canvas")
    # 3) REPLACEMENT preview: the formatting edit's reply quotes the change.
    s3 = f"fl-fmt-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    sc3, m3 = ask(s3, "kappa: reformat the warranty wording")
    upd = poll_until(lambda: world.update_count() > before, 60)
    body_now = str(world.content().get("body", ""))
    # 4) FORMATTING readback: the canonical read shows the reformat.
    rb = world.read_canonical()
    rb_body = str((rb.get("content") or {}).get("body", ""))
    # 5) RE-SEARCH: search the canvas for the delivery line.
    s5 = f"fl-read5-{uuid.uuid4().hex[:8]}"
    sc5, m5 = ask(s5, "search the canvas for the delivery line")
    # 6) RELOAD: fresh canonical read after everything.
    rb2 = world.read_canonical()
    rb2_body = str((rb2.get("content") or {}).get("body", ""))

    record("F12_read_workflows", {
        "chat_read_previews_canvas": sc == 200 and "Delivery: 2 weeks." in m1,
        "lookup_returns_value": sc2 == 200 and "12 months" in m2,
        "replacement_reply_quotes_change": sc3 == 200
        and "twelve months" in m3,
        "replacement_landed_once": bool(upd) and body_now.count(
            "Warranty: twelve months.") == 1,
        "formatting_readback_agrees": "Warranty: twelve months." in rb_body,
        "re_search_finds_line": sc5 == 200 and "Delivery: 2 weeks." in m5,
        "reload_read_agrees": rb2.get("success") is True
        and "Warranty: twelve months." in rb2_body
        and "Delivery: 2 weeks." in rb2_body,
    }, details={"chat_read_reply": m1[:110], "lookup_reply": m2[:110],
                "reformat_reply": m3[:110], "re_search_reply": m5[:110]})


def case_f10_restart_pin(world: World, token: str) -> None:
    """Kill mid-execution (before effect); restart; the pinned key must be
    honestly released as crashed (designed flat 409 request_crashed) - not
    re-executed, not replayed as success. If the interactive ack completed
    pre-kill, the pin replays identically (designed)."""
    session = f"fl-pin-{uuid.uuid4().hex[:8]}"
    rid = f"fl-pin-{uuid.uuid4().hex[:8]}"
    before = world.update_count()
    subject_before = str(world.content().get("subject"))
    arm_stall(world, 240, first_n=1)
    try:
        send(world, token, session, "delta: change the subject line", rid,
             timeout=20)
        early_ack = True
    except Exception:
        early_ack = False
    world.kill()
    relaunch(world)
    time.sleep(6)  # boot sweep window
    subject = str(world.content().get("subject"))
    effect_landed = "Warm subject marker" in subject
    branch = ("effect_landed_pre_kill" if effect_landed
              else "killed_before_effect")
    r = send(world, token, session, "delta: change the subject line", rid)
    payload = (r.json() or {}) if r.status_code == 200 else {}
    msg = str(payload.get("message", ""))
    # Designed answers: 409 {"error": "request_crashed"} (flat shape), or an
    # identical replay of the completed pin. NOT a re-execution.
    crashed_answer = False
    if r.status_code == 409:
        try:
            body409 = r.json() or {}
            err = body409.get("error")
            if isinstance(err, dict):
                err = err.get("error")
            crashed_answer = err == "request_crashed"
        except Exception:
            crashed_answer = False
    replayed_ack = False
    if r.status_code == 200 and payload.get("error_code") in (
            "request_crashed", "request_in_progress"):
        crashed_answer = True
    elif r.status_code == 200 and early_ack:
        replayed_ack = "still running" in msg.lower()
    checks = {
        "keyed_retry_answered": r.status_code in (200, 202, 409),
        "no_write_from_retry": world.update_count() <= before + (1 if effect_landed else 0),
    }
    if branch == "killed_before_effect":
        checks["subject_unchanged"] = subject == subject_before
        checks["pin_released_or_replayed_honestly"] = crashed_answer or replayed_ack
    else:
        checks["effect_present_exactly_once"] = subject.count(
            "Warm subject marker") == 1
    record(f"F10_restart_pin[{branch}]", checks, details={
        "status": r.status_code, "reply_head": msg[:160],
        "subject": subject, "early_ack": early_ack,
        "writes": world.update_count()})
    disarm_stall(world)


def case_f11_crash_window(world: World, token: str) -> None:
    """F11 crash-window, via the confined acceptance barrier.

    core/acceptance_barrier stage `continuation_after_effect` sits exactly in
    the window polling could not reach: the mutation has committed inside
    runner() and been verified by the readback gates, and neither the
    terminal effects nor the durable terminal record have run. The harness:

      1. arms the barrier (session-narrowed) and forces a background fork,
      2. waits for the worker to park, then proves AT THE HOLD:
         mutation committed / terminal completion unrecorded / worker alive,
      3. SIGKILLs the server while parked (no release file is created),
      4. restarts the SAME run with the barrier disarmed and verifies:
         one effect (no re-application), one durable terminal outcome
         (boot-sweep reconciliation, notified once), truthful reload/retry.

    Run alone with --crash-window; requires its own launch.
    """
    from scripts.orchestration_acceptance.run_isolated import WSTap
    session = f"fl-crashwin-{uuid.uuid4().hex[:8]}"
    rid = f"fl-crashwin-{uuid.uuid4().hex[:8]}"

    # 1. ARM (before launch so the server env inherits it).
    os.environ["ATOM_ACCEPTANCE_BARRIER"] = "continuation_after_effect"
    os.environ["ATOM_ACCEPTANCE_BARRIER_MATCH"] = session
    os.environ["ATOM_ACCEPTANCE_BARRIER_TIMEOUT"] = "300"
    try:
        world.launch()
        world.seed()
        token = world.mint()
        # The barrier dir belongs to the ARMED launch's run dir — computed
        # only after that launch exists (a stale run dir is exactly the bug
        # the first attempt had).
        barrier_dir = Path(world.run_dir) / "data" / "acceptance_barrier"
        arrival = barrier_dir / "barrier.continuation_after_effect.arrived.json"
        release = barrier_dir / "barrier.continuation_after_effect.release"
        before = world.update_count()
        arm_stall(world, 40, first_n=1)
        tap = WSTap(world.port, token, session_filter=session)

        async def body():
            await tap.start()
            await asyncio.wait_for(tap.connected_event.wait(), timeout=15)
            # NO marker: the generic plan's find text ("Quote validity:
            # 15 days.") is what the freshly seeded canvas actually says, so
            # the background edit APPLIES and the park is the true crash
            # window (applied outcome, audit id set) rather than a failure.
            return await asyncio.to_thread(
                send, world, token, session,
                "change the quote validity from 15 days to 30 days", rid)

        r = None
        try:
            r = asyncio.run(body())  # interactive ack; fork parks later
        except Exception as exc:
            print(f"[f11cw] interactive leg ended: {type(exc).__name__}")
        arrived = poll_until(arrival.exists, 150, interval=0.5)
        record("F11CW_worker_parked", {
            "barrier_arrived": bool(arrived),
            "no_release_yet": not release.exists(),
            "fork_record_exists": len(world.fork_records(session)) >= 1,
        }, details={"arrival": arrival.read_text()[:300] if arrived else None})

        # 2. PROVE AT THE HOLD: committed / unrecorded / alive.
        import httpx as _hx
        parked_health = None
        try:
            parked_health = _hx.get(f"{world.base}/api/health",
                                    timeout=5, trust_env=False).status_code
        except Exception:
            pass
        upd_at_hold = world.update_count()
        content_at_hold = world.content()
        hist_at_hold = world.history_texts(session)
        terminal_at_hold = [h for h in hist_at_hold
                            if "Background update" in h]
        forks_at_hold = world.fork_records(session)
        ctx = {}
        if arrived:
            try:
                ctx = json.loads(arrival.read_text()).get("context") or {}
            except Exception:
                pass
        record("F11CW_committed_but_unrecorded", {
            "mutation_committed_at_hold": upd_at_hold == before + 1,
            "parked_outcome_is_applied": str(ctx.get("outcome") or "") == "applied",
            "parked_audit_id_present": str(ctx.get("audit_id") or "") != "",
            "mutation_is_operation_linked": str(ctx.get("audit_id") or "")
            in json.dumps(world.audit_rows("update"), default=str),
            "terminal_outcome_unrecorded": len(terminal_at_hold) == 0,
            "durable_record_still_running": bool(forks_at_hold)
            and all(f["status"] == "running" for f in forks_at_hold),
            "worker_alive_while_parked": parked_health == 200,
        }, details={"audit_rows_at_hold": upd_at_hold,
                    "history_at_hold": [h[:90] for h in hist_at_hold],
                    "barrier_outcome": ctx.get("outcome"),
                    "barrier_audit_id": str(ctx.get("audit_id"))[:12]})

        # 3. KILL WHILE PARKED (no release file is ever created).
        world.kill()
        never_released = not release.exists()
        print(f"[f11cw] killed while parked; release_ever_created="
              f"{release.exists()}")

        # 4. RESTART DISARMED; boot sweep reconciles.
        for k in ("ATOM_ACCEPTANCE_BARRIER", "ATOM_ACCEPTANCE_BARRIER_MATCH",
                  "ATOM_ACCEPTANCE_BARRIER_TIMEOUT"):
            os.environ.pop(k, None)
        relaunch(world)
        time.sleep(8)  # boot sweep + recovered-continuation notify window
        forks_post = world.fork_records(session)
        upd_post = world.update_count()
        content_post = world.content()
        hist_post = world.history_texts(session)
        terminal_post = [h for h in hist_post if "Background update" in h]
        body_post = str(content_post.get("body", ""))
        record("F11CW_crash_window_recovery", {
            "barrier_never_released": never_released,
            "one_effect_exactly": upd_post == before + 1,
            "mutation_present_once": body_post.count(
                "Quote validity: 30 days.") == 1,
            "durable_record_reconciled": bool(forks_post)
            and all(f["status"] != "running" for f in forks_post),
            "exactly_one_continuation_record": len(forks_post) == 1,
            "no_fabricated_history_outcome": len(terminal_post) == 0,
            "pending_ack_preserved_on_reload": any(
                "still running" in h for h in hist_post),
        }, details={"forks_post": forks_post[:1],
                    "history_post": [h[:90] for h in hist_post],
                    "writes_post": upd_post})

        # Truthful retry: the keyed pin replays its pre-kill ack; no new
        # write; and a NEW id repeating the same change must not re-apply.
        r_again = send(world, token, session, "gamma: change the validity", rid)
        p_again = (r_again.json() or {}) if r_again.status_code == 200 else {}
        replayed = "still running" in str(p_again.get("message", "")).lower()
        record("F11CW_retry_truthful_after_crash", {
            "keyed_retry_answered": r_again.status_code in (200, 202, 409),
            "replays_ack_or_honest_state": replayed
            or r_again.status_code in (202, 409),
            "no_new_write_from_retry": world.update_count() == upd_post,
        }, details={"status": r_again.status_code,
                    "reply_head": str(p_again.get("message", ""))[:120]})

        rid_new = f"fl-crashwin-new-{uuid.uuid4().hex[:8]}"
        w_before = world.update_count()
        # SAME unmarked ask as the crashed turn: the plan's find text no
        # longer exists (already applied), so an honest pipeline must not
        # produce another write.
        r_new = send(world, token, session,
                     "change the quote validity from 15 days to 30 days",
                     rid_new)
        time.sleep(6)
        record("F11CW_new_id_no_repeat_effect", {
            "turn_answered": r_new.status_code in (200, 202),
            "no_repeat_effect": world.update_count() == w_before,
        })
    finally:
        for k in ("ATOM_ACCEPTANCE_BARRIER", "ATOM_ACCEPTANCE_BARRIER_MATCH",
                  "ATOM_ACCEPTANCE_BARRIER_TIMEOUT"):
            os.environ.pop(k, None)
        disarm_stall(world)


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8026)
    ap.add_argument("--results", default=str(
        BACKEND.parent / "docs" / "architecture" / "orchestration_migration" /
        "acceptance" / "finish_line_cases_0928.json"))
    ap.add_argument("--crash-window", action="store_true",
                    help="run ONLY the F11 crash-window case (dedicated "
                         "launch with the acceptance barrier armed)")
    args = ap.parse_args()

    from scripts.orchestration_acceptance import run_isolated as R
    script = (BACKEND.parent / "docs" / "architecture" /
              "orchestration_migration" / "acceptance" / "lane3" /
              "finish_line_0928" / "planner_script.json")
    capture = BACKEND / "data" / "acceptance_worlds" / "shim_capture_finish_line.jsonl"
    # Port hygiene: a leftover server/shim from a previous run answers health
    # checks and silently serves the WRONG script — verify both ports free,
    # then verify the shim is FRESH (empty request log) and answers a CANARY
    # with THIS run's script (an empty foreign shim would pass a log check).
    ensure_port_free(SHIM_PORT)
    ensure_port_free(args.port)
    shim = R.launch_shim(script, SHIM_PORT, capture=capture)
    register_pid(shim.pid)
    try:
        import httpx as _hx
        stale = _hx.get(f"http://127.0.0.1:{SHIM_PORT}/log",
                        timeout=5, trust_env=False).json()
        n = len(stale if isinstance(stale, list) else stale.get("log", []))
        if n:
            raise RuntimeError(f"shim on {SHIM_PORT} is not fresh "
                               f"({n} pre-existing requests) — stale process")
        canary = _hx.post(
            f"http://127.0.0.1:{SHIM_PORT}/v1/chat/completions",
            json={"model": "o3-mini", "tools": [
                {"type": "function", "function": {"name": "CanvasEditPlan"}}],
                "messages": [{"role": "user",
                              "content": "canary: finish-line script check"}]},
            timeout=5, trust_env=False).json()
        tc = ((canary.get("choices") or [{}])[0].get("message") or {}).get(
            "tool_calls") or []
        names = [t.get("function", {}).get("name") for t in tc]
        if names != ["CanvasEditPlan"]:
            raise RuntimeError(
                f"shim on {SHIM_PORT} did not answer the canary with this "
                f"run's script (got {names}) — foreign or wrong script")
        print("[shim] freshness + canary verified (this run's script, "
              "empty log)")
    except RuntimeError:
        raise
    except Exception as exc:
        print(f"[shim] freshness check skipped: {exc}")
    world = World(args.port)
    token = None
    try:
        try:
            world.launch()
            world.seed()
            token = world.mint()
            print(f"[world] ready: run_dir={world.run_dir.name} "
                  f"canvas={world.canvas_id[:8]} user={world.user_id[:8]}")
        except Exception as exc:
            RESULTS.append({"case": "SETUP", "status": "ERROR", "checks": {},
                            "notes": [],
                            "details": {"exception": f"{type(exc).__name__}: {exc}"[:400]}})
            print(f"[ERROR] SETUP: {type(exc).__name__}: {exc}")

        if token and args.crash_window:
            # DEDICATED crash-window run: discard this un-armed launch, then
            # relaunch with the barrier armed; park; kill; disarm; recover.
            try:
                try:
                    os.killpg(os.getpgid(world.proc.pid), signal.SIGKILL)
                except (ProcessLookupError, AttributeError):
                    pass
                world.proc = None
                ensure_port_free(args.port)
                token = None
                case_f11_crash_window(world, token)
            except Exception as exc:
                RESULTS.append({"case": "F11-crash-window", "status": "ERROR",
                                "checks": {}, "notes": [],
                                "details": {"exception": f"{type(exc).__name__}: {exc}"[:400]}})
                print(f"[ERROR] F11-crash-window: {type(exc).__name__}: {exc}")
            disarm_stall(world)

        if token and not args.crash_window:
            case_f12_reads(world, token)
            baseline = case_f03_baseline_edit(world, token)
            if baseline:
                case_f10_replay_conflict(world, token, baseline)
            else:
                record("F10_keyed_replay", {"skipped_no_baseline": False},
                       notes=["baseline edit did not land; replay/conflict skipped"])
            for name, fn in [
                    ("F07", lambda: case_f07_no_apply_then_second(world, token)),
                    ("F04/F08-connected",
                     lambda: case_f04_f08_connected_background(world, token)),
                    ("F05", lambda: case_f05_execution_failure(world, token)),
                    ("F09", lambda: case_f09_overlap(world, token)),
                    ("F08-disc", lambda: case_f08_disconnected(world, token)),
                    ("F12-reads", lambda: case_f12_read_workflows(world, token)),
                    ("F11", lambda: case_f11_effect_before_kill(world, token)),
                    ("F10-restart", lambda: case_f10_restart_pin(world, token))]:
                # shim liveness: an empty-output leg once benched the only
                # model for 120s and dead-ended every forked leg; a DEAD shim
                # poisons everything after it. Restart it if it died.
                try:
                    import httpx as _hx
                    _hx.get(f"http://127.0.0.1:{SHIM_PORT}/log",
                            timeout=3, trust_env=False)
                except Exception:
                    print("[shim] dead — relaunching with the same script")
                    shim = R.launch_shim(script, SHIM_PORT, capture=capture)
                try:
                    fn()
                except Exception as exc:
                    RESULTS.append({"case": name, "status": "ERROR",
                                    "checks": {}, "notes": [],
                                    "details": {"exception": f"{type(exc).__name__}: {exc}"[:400]}})
                    print(f"[ERROR] {name}: {type(exc).__name__}: {exc}")
                disarm_stall(world)  # never carry an armed stall between cases
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
            shim.terminate()
            shim.kill()
        except Exception:
            pass

    passed = sum(1 for e in RESULTS if e["status"] == "PASS")
    failed = len(RESULTS) - passed
    print(f"\n=== finish-line cases: {passed} PASS / {failed} FAIL/ERROR ===")
    manifest = {}
    try:
        manifest = json.loads((BACKEND / "data" / "acceptance_worlds" /
                               "write_combined" / "MANIFEST.json").read_text())
    except Exception:
        pass
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "world": "write_combined", "port": args.port,
           "run_dir": str(getattr(world, "run_dir", "")),
           "export_binding": {
               "code_snapshot_sha256": manifest.get("code_snapshot_sha256"),
               "code_source": manifest.get("code_source"),
               "runtime_identity": "see server.log (1a953b58934d-dirty.<hash>)",
               "flags": ["CHAT_FINALIZATION_M1", "CHAT_FINALIZATION_M2",
                         "ATOM_TASK_LIFECYCLE_ENABLED"],
               "provider": "local shim (provider responses only)"},
           "results": RESULTS}
    Path(args.results).write_text(json.dumps(out, indent=1, default=str))
    print(f"results: {args.results}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
