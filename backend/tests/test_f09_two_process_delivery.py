"""F09: two REAL processes racing the terminal delivery, on one scratch database.

Why a separate file, and why real processes
The in-process test cannot exercise this. `asyncio.gather` on two coroutines
cannot interleave between the claim's SELECT and its UPDATE, because there is
no `await` in between -- that is exactly what the failed negative control in
`test_f09_supersede_terminal_delivery.py` demonstrated. A race needs an
independent OS process, which is also the real topology: two servers on one
acceptance world database.

Each worker is a real `subprocess` running a real Python interpreter, pointed
at a real file-backed SQLite database by `DATABASE_URL` (so it builds its own
engine at import, like any other server). The two runs differ only in whether
arbitration is enabled:

  * arbitration DISABLED -> both workers must produce a duplicate. If they do
    not, the test is not exercising the race and proves nothing.
  * arbitration ENABLED  -> exactly one delivery.

Neither mode is allowed to be a no-op: a test that cannot fail in the negative
mode cannot certify the positive one.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

WORKER = r'''
import asyncio, json, os, sys
sys.path.insert(0, %(backend)r)
os.environ["TESTING"] = "1"
import core.async_turn_continuation as atc
from core.database import get_db_session
from core.models import AgentExecution, ChatMessage as ChatMessageModel

CID, SID = %(cid)r, %(sid)r
DISABLE = %(disable)s

# Pre-create the durable row the claim arbitrates against. BOTH workers race
# to do this, so losing the insert is expected and is not the race under test.
with get_db_session() as db:
    have = db.query(AgentExecution).filter(AgentExecution.id == CID).first()
    if have is None:
        try:
            db.add(AgentExecution(id=CID, status="completed", metadata_json={}))
            db.commit()
        except Exception:
            db.rollback()

if DISABLE:
    # NEGATIVE MODE: neutralise arbitration. Check-and-insert only -- which is
    # what the code did before the atomic claim existed.
    atc._claim_terminal_delivery = lambda cont: (True, "claim disabled", "")

cont = atc.AsyncTurnContinuation(
    continuation_id=CID, user_id="u-proc", session_id=SID,
    message="m", canvas={"canvas_id": "cv", "canvas_type": "email",
                         "content": {"body": "b"}},
    execution_id="e-proc", agent_id=None, history_snapshot=[])

# Yield so the two processes genuinely overlap rather than running serially.
asyncio.run(asyncio.sleep(0.25))
try:
    claimed, reason, _tok = atc._claim_terminal_delivery(cont)
except BaseException as exc:  # report, do not die: the parent asserts on counts
    import traceback
    print(json.dumps({"claimed": False, "reason": "WORKER RAISED",
                      "error": f"{type(exc).__name__}: {exc}",
                      "tb": traceback.format_exc()[-900:]}))
    raise SystemExit(0)
# A real yield AFTER the claim and BEFORE the write: the window two processes
# collide in.
asyncio.run(asyncio.sleep(0.25))
if claimed:
    with get_db_session() as db:
        db.add(ChatMessageModel(
            conversation_id=SID, tenant_id="default", role="assistant",
            content="terminal",
            metadata_json=json.dumps({"continuation": {
                "id": CID, "outcome": "cancelled"}})))
print(json.dumps({"claimed": bool(claimed), "reason": reason}))
'''


def _make_scratch(tmp: Path) -> Path:
    db = tmp / "race.db"
    url = f"sqlite:///{db}"
    code = (
        "import sys;sys.path.insert(0, %r);import os;os.environ['TESTING']='1';"
        "os.environ['DATABASE_URL']=%r;"
        "from core.database import engine;"
        "from core.models_registration import Base;Base.metadata.create_all(engine);"
        "print('ok')" % (str(BACKEND), url)
    )
    env = dict(os.environ, TESTING="1", DATABASE_URL=url)
    out = subprocess.run([sys.executable, "-c", code], cwd=str(BACKEND),
                         capture_output=True, text=True, env=env, timeout=300)
    if "ok" not in (out.stdout or ""):
        raise SystemExit(f"scratch schema failed: {out.stdout} {out.stderr}")
    return db


def _run_pair(db: Path, cid: str, sid: str, disable: bool, tag: str) -> None:
    env = dict(os.environ, TESTING="1", DATABASE_URL=f"sqlite:///{db}")
    script = WORKER % {"backend": str(BACKEND), "cid": cid, "sid": sid,
                       "disable": disable}
    procs = [subprocess.Popen([sys.executable, "-c", script],
                              cwd=str(BACKEND), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) for _ in range(2)]
    for p in procs:
        out, err = p.communicate(timeout=300)
        if p.returncode != 0:
            raise SystemExit(f"worker ({tag}) failed rc={p.returncode}: "
                             f"{(err or '')[-2500:]}")
        # A worker that RAISED reports claimed=False, which on the enabled path
        # would make `enabled == 1` pass for entirely the wrong reason. The
        # parent refuses to certify a run in which any worker blew up.
        for line in (out or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if payload.get("reason") == "WORKER RAISED":
                raise AssertionError(
                    f"a {tag} worker raised instead of arbitrating, so the "
                    f"count below would be meaningless: "
                    f"{payload.get('error')} | {payload.get('tb')}")


def _count(db: Path, sid: str, cid: str) -> int:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT metadata_json FROM chat_messages WHERE conversation_id=?",
            (sid,)).fetchall()
    finally:
        con.close()
    return sum(1 for r in rows if cid in (r[0] or ""))


def test_two_processes_duplicate_without_arbitration_and_do_not_with_it():
    """The negative mode must actually duplicate, or this certifies nothing."""
    results = {}
    for disable in (True, False):
        tag = "arbitration-disabled" if disable else "arbitration-enabled"
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            db = _make_scratch(tmp)
            cid, sid = f"c-proc-{tag}", f"s-proc-{tag}"
            _run_pair(db, cid, sid, disable, tag)
            results[tag] = _count(db, sid, cid)

    disabled = results["arbitration-disabled"]
    enabled = results["arbitration-enabled"]

    assert disabled > 1, (
        f"NEGATIVE MODE BROKEN: with arbitration disabled two processes wrote "
        f"{disabled} terminal messages, expected more than 1. The pair is not "
        f"actually racing, so the enabled result below would be meaningless.")
    assert enabled == 1, (
        f"ARBITRATION FAILED: with the atomic claim enabled two processes "
        f"still wrote {enabled} terminal messages, expected exactly 1.")

    print(f"\n  arbitration disabled -> {disabled} terminal messages")
    print(f"  arbitration enabled  -> {enabled} terminal message")


def test_the_guarantee_is_not_exactly_once_across_processes_and_surfaces():
    """Stated as a limit, because a single flag cannot deliver it.

    The claim arbitrates the DURABLE row. It cannot make the WebSocket delivery
    and the notification service exactly-once: those are separate systems with
    their own failure modes, and a process that dies between the claim and the
    broadcast leaves the bubble missing while the row exists. So the guarantee
    is: the durable terminal message is written once, and the fail-open path
    still permits a duplicate when the claim cannot be taken. This test pins
    that wording so it cannot be quietly upgraded into a stronger claim later.
    """
    from core import async_turn_continuation as atc

    doc = atc._claim_terminal_delivery.__doc__ or ""
    assert "CLAIM IS NOT PROOF OF DELIVERY" in doc, (
        "the claim function no longer documents that a claim is not proof of "
        "delivery")
    assert "fail" in doc.lower() or "FAIL-OPEN" in doc or "arbitration" in doc.lower(), (
        "the claim function no longer records what happens when it cannot be "
        "arbitrated")
    # The fail-open path is explicit in the caller, at WARNING, not a silent
    # continue.
    src = Path(atc.__file__).read_text()
    # NOTE: the marker is split across two source literals ("NOT " "ARBITRATED"),
    # so assert on a fragment that is contiguous in the file.
    assert "ARBITRATED" in src and "duplicate terminal message" in src, (
        "the fail-open path is no longer observable in the log")
    assert "is POSSIBLE" in src, (
        "the fail-open path no longer states that duplicates remain possible")
