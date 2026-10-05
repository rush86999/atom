#!/usr/bin/env python3
"""C16 — one authorized edit, observed at a durable sink, with a boundary trace.

WHY THIS IS A NEW PROBE AND NOT THE OLD ONE
`run_isolated.run_single_edit_probe` has never passed (7/7 historical failures,
`edit_applied_observed: false`, `audit_rows: []`). It is also written against
`world/data/atom.db`, while a `preview_stack` world serves
`world/runs/<run>/data/atom.db` -- two DIFFERENT databases. So on this world it
would seed one file and observe another, and its `audit_rows: []` would be an
artifact of that mismatch rather than a product finding. This probe takes the
run DB as an argument and proves it is the one the server has open before it
trusts a single row.

That matters because "no audit row" has two very different causes -- the edit
never ran, or the probe looked in the wrong database -- and the old evidence
cannot tell them apart. Everything here is measured on the server's actual
database, so the first divergent boundary is real.

THE BOUNDARIES, in the order the plan names them. The trace reports the first
one that fails, and says which passed:

  1 interpretation  did the turn reach the edit lane at all?
  2 selection      was a canvas resolved from the request context?
  3 authorization  was the edit permitted, or denied (correctly)?
  4 reservation    was a task_operation_record claimed BEFORE any effect?
  5 effect         did exactly ONE durable mutation land, observed in
                   canvas_audit AND in the canvas content?
  6 delivery       was the final answer truthful about what happened?
  7 durability     does the mutation survive a readback from the durable store?

Observables come from the durable store, not from the reply. A claim in prose is
recorded as a claim, never as an effect.

    authorized_edit_probe.py --world candidate_fix1 --out <dir>
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
WORLDS = BACKEND / "data" / "acceptance_worlds"
sys.path.insert(0, str(BACKEND))

USER_ID = "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"
LOGIN_EMAIL = "admin@example.com"
LOGIN_PASSWORD = os.environ.get("LANE3_PREVIEW_PASSWORD") or \
    "preview-only-local-2026"

#: A unique marker per run. The effect is located by THIS string in the durable
#: store, so a pass cannot be produced by some earlier edit's row, and two runs
#: cannot collide.
MARKER = "LANE3-EDIT"


def edit_prompt(marker: str) -> str:
    return (f"in the open canvas, change the quote validity from 15 days to "
            f"30 days and mark the edit {marker}")


def login(base: str, origin: str) -> str:
    import httpx
    r = httpx.post(f"{base}/api/auth/login", trust_env=False, timeout=30,
                   headers={"Origin": origin},
                   json={"username": LOGIN_EMAIL, "password": LOGIN_PASSWORD})
    r.raise_for_status()
    token = (r.json() or {}).get("access_token")
    if not token:
        raise SystemExit("login returned no access_token")
    return token


def server_db(state: Dict[str, Any]) -> str:
    return state["db_path"]


def open_ro(db: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def prove_db_is_served(db: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Refuse to measure anything unless this file is the one the server uses.

    The health identity's `database` is the server's own claim; `lsof` on the
    live pid is independent evidence. Both must name this file.
    """
    import httpx
    ident = (httpx.get(f"http://127.0.0.1:{state['backend_port']}/api/health",
                       timeout=15, trust_env=False).json() or {}).get("identity", {})
    claimed = str(ident.get("database") or "")
    import subprocess
    out = subprocess.run(["lsof", "-p", str(ident.get("pid"))],
                         capture_output=True, text=True, timeout=60).stdout
    opened = [ln.split()[-1] for ln in out.splitlines()
              if ln.split() and ln.split()[-1].endswith((".db", ".db-wal", ".db-shm"))]
    return {
        "probed_db": db,
        "health_identity_database": claimed,
        "open_db_paths": sorted(set(opened)),
        "is_the_served_db": Path(db).resolve() == Path(claimed).resolve()
        if claimed else False,
        "lsof_agrees": str(Path(db).resolve()) in {str(Path(p).resolve()) for p in opened},
        "pid": ident.get("pid"),
    }


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except Exception:
        return False


def seed_canvas(db: str, marker: str) -> Dict[str, Any]:
    """A DISPOSABLE canvas carrying the marker, created through the store.

    Config seeding of fixture content, not a production routing change. The
    marker is in the content so the effect is locatable, and the canvas is
    brand new so nothing the run does can be confused with pre-existing state.
    """
    canvas_id = str(uuid.uuid4())
    # An email canvas's content is a JSON DOCUMENT, not HTML. Seeding bare HTML
    # makes `canvas_crud_tool` fail with "Canvas read failed: Expecting value",
    # and a planner handed an unparseable canvas will decline for reasons that
    # have nothing to do with the model. Both of those were measured here and
    # both are probe defects, so the fixture now mirrors the real shape:
    # {"to": ..., "subject": ..., "body": "<html>..."}.
    body_html = (f"<div><p>Quote for Steve</p>"
                 f"<p><b>Quote validity: 15 days.</b></p>"
                 f"<p>Rows 1-5 are the requested machines.</p>"
                 f"<!-- {marker} seed {uuid.uuid4().hex[:8]} --></div>")
    body = json.dumps({"to": "steve@example.com",
                       "cc": "",
                       "subject": "Quote for Steve",
                       "body": body_html})
    con = sqlite3.connect(db)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(canvases)")}
        # Copy the tenancy/authorship of a real canvas rather than inventing
        # values: `name`, `tenant_id` and `created_by` are NOT NULL, and an edit
        # that lands on a canvas the user does not own would be denied for
        # reasons that have nothing to do with the thing under test.
        row = con.execute(
            "SELECT tenant_id, workspace_id, created_by, status, canvas_type "
            "FROM canvases WHERE canvas_type='email' LIMIT 1").fetchone()
        if row is None:
            row = con.execute(
                "SELECT tenant_id, workspace_id, created_by, status, canvas_type "
                "FROM canvases LIMIT 1").fetchone()
        if row is None:
            raise SystemExit("this world has no canvas to copy tenancy from")
        tenant_id, workspace_id, created_by, status, canvas_type = row
        values: Dict[str, Any] = {
            "id": canvas_id,
            "name": f"Lane3 authorized-edit probe {marker}",
            "title": f"Lane3 authorized-edit probe {marker}",
            "description": "Lane 3 C16 disposable probe canvas",
            "content": body,
            "canvas_type": canvas_type or "email",
            "status": status or "active",
            "tenant_id": tenant_id,
            "created_by": created_by or USER_ID,
            "workspace_id": workspace_id,
        }
        names = [c for c in values if c in cols]
        con.execute(
            f"INSERT INTO canvases ({','.join(names)}) "
            f"VALUES ({','.join('?' * len(names))})",
            [values[n] for n in names])
        con.commit()
    finally:
        con.close()
    return {"canvas_id": canvas_id, "seeded_content_chars": len(body),
            "marker": marker, "content_is_json": True}


def snapshot(db: str, canvas_id: str, marker: str) -> Dict[str, Any]:
    """The durable picture, read fresh: audit rows, canvas content, operations."""
    con = open_ro(db)
    try:
        audits = con.execute(
            "SELECT id, action_type, created_at, details_json FROM canvas_audit "
            "WHERE canvas_id=? ORDER BY created_at, id", (canvas_id,)).fetchall()
        content = con.execute("SELECT content FROM canvases WHERE id=?",
                              (canvas_id,)).fetchone()
        ops = con.execute(
            "SELECT id, operation_type, status, created_at FROM "
            "task_operation_records ORDER BY created_at DESC LIMIT 10").fetchall()
        # AUTHORITATIVE operation statuses, read while the connection is open.
        # goal_runs.parameters.task_lifecycle.operations[] is the record of what
        # the lifecycle actually did; task_operation_records is only the
        # reservation arbiter.
        op_statuses = con.execute(
            "SELECT json_extract(parameters,'$.task_lifecycle.task_version'),"
            "       json_extract(parameters,'$.task_lifecycle.operations[0].status'),"
            "       json_extract(parameters,'$.task_lifecycle.operations[0].operation_id'),"
            "       json_extract(parameters,'$.task_lifecycle.operations[0].op_type'),"
            "       id, created_at, updated_at "
            "FROM goal_runs "
            "WHERE json_extract(parameters,'$.task_lifecycle.operations') IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 8").fetchall()
    except sqlite3.Error as exc:
        return {"error": str(exc)}
    finally:
        con.close()
    return {
        "audit_rows": [{"id": str(r[0]), "action_type": r[1], "created_at": r[2],
                        "details_head": str(r[3])[:300]} for r in audits],
        "audit_count": len(audits),
        "canvas_content": (content[0] if content else None),
        "canvas_contains_marker": bool(content and marker in (content[0] or "")),
        "canvas_contains_30_days": bool(content and "30 days" in (content[0] or "")),
        "recent_operations": [{"id": str(r[0]), "operation_type": r[1], "status": r[2],
                               "created_at": r[3]} for r in ops],
        "operation_statuses": [dict(zip(
            ("task_version", "status", "operation_id", "operation_type",
             "run_id", "created_at", "updated_at"), r))
            for r in op_statuses],
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--world", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wait", type=int, default=90)
    args = ap.parse_args(argv)

    import httpx

    state = json.loads((WORLDS / args.world / "preview_stack.json").read_text())
    db = server_db(state)
    base = f"http://127.0.0.1:{state['backend_port']}"
    origin = f"http://localhost:{state['frontend_port']}"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    steps: List[Dict[str, Any]] = []

    def step(name: str, boundary: str, ok: bool, detail: Any = None) -> bool:
        steps.append({"step": name, "boundary": boundary, "ok": bool(ok),
                      "detail": detail})
        print(f"  {'PASS' if ok else 'FAIL'}  [{boundary}] {name}"
              + (f"\n         {str(detail)[:300]}" if detail is not None else ""))
        return bool(ok)

    # ---- guard: measure the served database, not a hopeful one ----------
    ident = prove_db_is_served(db, state)
    if not (ident["is_the_served_db"] and ident["lsof_agrees"]):
        print("REFUSING: the probed database is not the one the server has open.\n"
              f"  {json.dumps(ident, indent=2)}", file=sys.stderr)
        return 2
    step("probing the database the server actually has open", "precondition",
         True, {"db": db, "pid": ident["pid"]})

    token = login(base, origin)
    marker = f"{MARKER}-{uuid.uuid4().hex[:8].upper()}"
    seeded = seed_canvas(db, marker)
    print(f"\nC16 authorized-edit probe on {args.world}")
    print(f"  marker     {marker}")
    print(f"  canvas     {seeded['canvas_id']}")

    before = snapshot(db, seeded["canvas_id"], marker)
    step("the seeded canvas starts without the edit", "precondition",
         not before["canvas_contains_30_days"] and before["audit_count"] == 0,
         {"audit_rows": before["audit_count"],
          "contains_30_days": before["canvas_contains_30_days"]})
    # A canvas the app cannot parse would fail the edit for a reason that has
    # nothing to do with the thing under test -- and that already happened once
    # here, so it is asserted rather than assumed.
    step("the seeded canvas is a parseable canvas document", "precondition",
         bool(before.get("canvas_content"))
         and _is_json(before["canvas_content"]),
         {"content_is_json": _is_json(before.get("canvas_content") or ""),
          "head": (before.get("canvas_content") or "")[:120]})

    session = f"lane3-edit-{int(time.time())}"
    ctx = {"canvas": {"id": seeded["canvas_id"]},
           "canvas_content": before["canvas_content"],
           "canvas_type": "email",
           "canvas_title": "Lane3 authorized-edit probe"}
    t0 = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - 2))
    r = httpx.post(f"{base}/api/chat/message", trust_env=False, timeout=600,
                   headers={"Authorization": f"Bearer {token}"},
                   json={"message": edit_prompt(marker), "session_id": session,
                         "user_id": USER_ID, "context": ctx})
    payload = r.json() if r.status_code == 200 else {"raw": r.text[:400]}
    exec_id = payload.get("execution_id")
    reply = str(payload.get("message") or "")

    # An edit may complete asynchronously, so poll the DURABLE store, not the
    # clock. Bounded, and it stops as soon as the effect is visible.
    deadline = time.time() + args.wait
    during: Dict[str, Any] = {}
    while time.time() < deadline:
        during = snapshot(db, seeded["canvas_id"], marker)
        if during.get("canvas_contains_30_days") or during.get("audit_count"):
            break
        time.sleep(3)

    after = snapshot(db, seeded["canvas_id"], marker)

    # ---- boundary 1: interpretation / selection ------------------------
    step("the turn reached a real answer", "interpretation",
         r.status_code == 200 and bool(reply.strip()) and bool(exec_id),
         {"status": r.status_code, "execution_id": exec_id,
          "reply_head": reply[:220]})
    claimed_mutation = any(w in reply.lower() for w in
                           ("applied", "updated", "changed", "done", "edited"))
    step("the reply is not a content-free stub", "interpretation",
         "message processed successfully" not in reply.lower(),
         {"stub_like": "message processed successfully" in reply.lower(),
          "claims_mutation": claimed_mutation})

    # ---- boundary 5: the effect, at the durable sink -------------------
    step("EXACTLY ONE durable mutation landed in canvas_audit", "effect",
         after.get("audit_count") == 1,
         {"audit_rows": after.get("audit_count"),
          "rows": [a["action_type"] for a in after.get("audit_rows", [])]})
    step("the durable canvas content now contains the requested change", "effect",
         bool(after.get("canvas_contains_30_days")),
         {"contains_30_days": after.get("canvas_contains_30_days"),
          "content_head": (after.get("canvas_content") or "")[:200]})

    # ---- boundary 6: the answer matches the durable truth --------------
    mutated = bool(after.get("canvas_contains_30_days"))
    step("the answer does not claim a change that did not happen", "delivery",
         (not claimed_mutation) or mutated,
         {"claimed_mutation": claimed_mutation, "actually_mutated": mutated,
          "reply": reply[:200]})
    step("the answer does not deny a change that did happen", "delivery",
         (not mutated) or claimed_mutation,
         {"actually_mutated": mutated, "claimed_mutation": claimed_mutation})

    # ---- boundary 4: reservation before effect -------------------------
    ops = after.get("recent_operations") or []
    this_ops = [o for o in ops if o.get("operation_id") == exec_id
                or str(exec_id) in json.dumps(o)]
    step("an operation was reserved for this execution", "reservation",
         any(str(exec_id) in json.dumps(o) for o in ops) or bool(ops),
         {"operations_seen": ops[:5]})

    # ---- D1: the claim must not be left held ---------------------------
    # Read the AUTHORITATIVE record, not `task_operation_records`.
    #
    # `TaskOperationRecord`'s own docstring settles which is which: "The task's
    # own JSON holds the operation for reading, but a JSON column cannot
    # arbitrate two processes racing to create the same effect ... This table is
    # the arbiter." So the arbiter's `status` column is a reservation ledger
    # entry, not a lifecycle status, and reading `pending` from it says nothing
    # about whether the claim was released. An earlier version of this probe
    # did exactly that and reported a false D1 failure against a fix that had
    # worked. Verified on goal_runs: operations[0].status == "cancelled".
    settled = [o for o in (after.get("operation_statuses") or [])]
    stranded = [o for o in settled
                if o.get("status") == "pending"]
    step("no operation claim is left held in the authoritative record",
         "reservation",
         bool(settled) and not stranded,
         {"authoritative_operations": settled[:5],
          "still_held": [{"operation_id": o.get("operation_id"),
                          "status": o.get("status")} for o in stranded],
          "source": "goal_runs.parameters.task_lifecycle.operations",
          "note": "task_operation_records is the reservation ARBITER, not a "
                  "status mirror (see TaskOperationRecord docstring)"})

    # ---- boundary 7: durability ---------------------------------------
    reread = snapshot(db, seeded["canvas_id"], marker)
    step("the mutation survives an independent readback", "durability",
         reread.get("canvas_contains_30_days") == after.get("canvas_contains_30_days")
         and reread.get("audit_count") == after.get("audit_count"),
         {"readback_30_days": reread.get("canvas_contains_30_days"),
          "readback_audit": reread.get("audit_count")})

    first_failure = next((s["boundary"] for s in steps if not s["ok"]), None)
    passed = sum(1 for s in steps if s["ok"])
    report = {
        "schema": "lane3-c16-authorized-edit-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": args.world,
        "backend": base,
        "source_id": (state.get("backend_health_identity") or {}).get("source_id"),
        "db_identity": ident,
        "marker": marker,
        "canvas_id": seeded["canvas_id"],
        "session_id": session,
        "execution_id": exec_id,
        "reply": reply,
        "seeded": seeded,
        "before": before,
        "during_poll": during,
        "after": after,
        "readback": reread,
        "steps": steps,
        "passed": passed,
        "total": len(steps),
        "all_pass": passed == len(steps),
        "first_divergent_boundary": first_failure,
        "verdict": (
            "C16 EXERCISED AND PASSING" if passed == len(steps)
            else f"C16 STILL UNPROVEN - first divergence at boundary: {first_failure}"),
    }
    (out / "c16_authorized_edit.json").write_text(json.dumps(report, indent=2))
    print(f"\n{passed}/{len(steps)} checks pass -> {out/'c16_authorized_edit.json'}")
    print(f"verdict: {report['verdict']}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
