#!/usr/bin/env python3
"""C16 effect-layer coverage with a CONTROLLED planner, and real-planner trials.

SCOPE, STATED PLAINLY
This injects ONE thing: the planner's model response. Everything else is real --
authentication, authorization, the lifecycle reservation, the execution claim, the
canvas mutation, the audit row, the independent read-back, D0's verification and
D4's repair. That is what makes it effect-layer coverage, and it is NOT evidence
that the production planner accepts edits. It measurably does not. The two are
reported in separate sections and never merged.

WHY THE PROVIDER SHIM AND NOT A CODE BYPASS
`provider_shim.py` exists for exactly this: "Substitutes PROVIDER RESPONSES ONLY:
the production execution, routing, persistence, verification, and delivery paths
run for real." A monkeypatched planner inside the server would also stub the
reservation and the store, and would prove nothing about them. So the world is
pointed at the shim through its own provider config, and the injection is
asserted to have been CONSUMED by reading the shim's request log -- a control that
did not fire would otherwise be indistinguishable from a control that worked.

THE DISTINCTION THE INSTRUCTION ASKS FOR
A clean planner decline is respected at execution time -- it must never become an
edit. But it is NOT successful completion of an authorized, supported edit
request. So a decline is graded as an INTERPRETATION FAILURE against the
advertised workflow, separately from whether execution correctly did nothing.

    controlled_planner_c16.py --world <w> --out <dir> [--cases all]
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
WORLDS = BACKEND / "data" / "acceptance_worlds"
SHIM = BACKEND / "scripts" / "orchestration_acceptance" / "provider_shim.py"
sys.path.insert(0, str(BACKEND))

USER_ID = "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"
LOGIN_EMAIL = "admin@example.com"
LOGIN_PASSWORD = os.environ.get("LANE3_PREVIEW_PASSWORD") or \
    "preview-only-local-2026"
SHIM_MODEL = "shim-1"
# Captured from the structured request (see tool_names in the capture
# file), not assumed: instructor derives the tool name from the response
# model's class name.
PLANNER_TOOL_NAME = "CanvasEditPlan"
WORKSPACE_ID = os.environ.get("LANE3_WORKSPACE_ID", "default")
TENANT_ID = os.environ.get("LANE3_TENANT_ID", "default")

# The canvas the probe seeds. The scripted op must match THIS text, or the
# planner's plan is discarded before any write -- which would look like a
# shim failure when it is really a fixture mismatch.
BODY_OLD = "Quote validity: 15 days."
BODY_NEW = "Quote validity: 30 days."


_SECRET_HINTS = ("sk-", "bearer ", "api_key", "authorization", "password",
                 "token")


def redact(obj: Any) -> Any:
    """Strip anything credential-shaped before it reaches an evidence file."""
    if isinstance(obj, str):
        out = obj
        for hint in _SECRET_HINTS:
            low = out.lower()
            i = low.find(hint)
            while i != -1:
                tail = out[i + len(hint):]
                cut = len(tail)
                for stop in (",", "}", "]", "\n", '"'):
                    j = tail.find(stop)
                    if j != -1:
                        cut = min(cut, j)
                out = out[:i + len(hint)] + "<REDACTED>" + tail[cut:]
                low = out.lower()
                nxt = low.find(hint, i + len(hint) + 10)
                i = nxt
        return out
    if isinstance(obj, dict):
        return {k: ("<REDACTED>" if any(h in k.lower() for h in _SECRET_HINTS)
                    else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def plan_json(*, wants_edit: bool, ops: Optional[List[Dict]] = None,
              reply: str = "Updated the quote validity to 30 days.") -> str:
    """A CanvasEditPlan exactly as the structured call expects to receive it."""
    return json.dumps({
        "wants_edit": wants_edit,
        "edit_mode": "patch" if ops else "none",
        "ops": ops or [],
        "restore_audit_id": None,
        "updated_content_json": None,
        "title": None,
        "reply": reply,
    })


PATCH_OPS = [{"field": "body", "find": BODY_OLD, "replace": BODY_NEW}]

#: bg-failure: a plan the parser ACCEPTS (so the turn reserves, claims and
#: reaches execution) that then cannot be applied, because its `find` text is
#: not present in the canvas. The failure is therefore an EXECUTION-time one
#: after acceptance, not another planner decline -- which a decline would be,
#: and a decline proves nothing about truthful failure REPORTING. Submitting
#: the accepting PATCH_OPS here (as this mode used to) contradicted its own
#: assertions: it asked for zero update audits from a plan designed to make one.
UNAPPLIABLE_OPS = [{"field": "body",
                    "find": "Quote validity: 99 days.",
                    "replace": BODY_NEW}]


def write_script(path: Path, responses: List[Dict[str, str]]) -> None:
    path.write_text(json.dumps({"responses": responses}, indent=2))


def start_shim(script: Path, port: int, capture: Optional[Path] = None
               ) -> subprocess.Popen:
    log = (script.parent / "shim.log").open("ab")
    cmd = [str(BACKEND / "venv314" / "bin" / "python"), str(SHIM),
           "--port", str(port), "--script", str(script)]
    if capture is not None:
        cmd += ["--capture", str(capture)]
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)


def shim_log(port: int) -> Dict[str, Any]:
    import httpx
    for _ in range(40):
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/log", timeout=5,
                          trust_env=False)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(0.5)
    return {}


def point_world_at_shim(world: str, port: int) -> Dict[str, Any]:
    """Register the shim as a LOCAL provider in the world's own DB.

    Why the DB and not `byok_config.json`: `preview_stack up` re-seeds
    `BYOK_SEED_FILES` (including byok_config.json) on every launch, so a config
    edit is silently overwritten by the very restart needed to load it. The
    loader's own documented seam for a local OpenAI-compatible endpoint is
    `LocalModelProvider`, read by `_load_local_providers()` into clients keyed
    `local_{id[:8]}`. Inserting the row is world-local, survives restarts, and
    changes no production config or code.

    Returns the provider key to pin, and the workspace it was registered under.
    """
    state = json.loads((WORLDS / world / "preview_stack.json").read_text())
    db = str(Path(state["db_path"]).resolve())
    if "acceptance_worlds" not in db:
        raise SystemExit(f"refusing to write outside a world: {db}")
    import uuid
    os.environ.pop("TESTING", None)
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    os.environ["ATOM_DATA_DIR"] = str(Path(db).parent)
    os.environ["ENVIRONMENT"] = "development"
    from core.database import get_db_session
    from core.models import LocalModelProvider
    provider_id = str(uuid.uuid4())
    with get_db_session() as s:
        s.add(LocalModelProvider(
            id=provider_id,
            workspace_id=WORKSPACE_ID,
            tenant_id=state.get("tenant_id") or TENANT_ID,
            name="C16 controlled planner shim",
            provider_type="openai",
            base_url=f"http://127.0.0.1:{port}/v1",
            api_key="shim-not-a-secret",
            is_active=True,
        ))
        s.commit()
    key = f"local_{provider_id[:8]}"
    return {"db": db, "run_dir": state["run_dir"], "provider_key": key,
            "base_url": f"http://127.0.0.1:{port}/v1", "model": SHIM_MODEL,
            "pin": f"{key}/{SHIM_MODEL}", "workspace_id": WORKSPACE_ID}


def seed_canvas(db: str, marker: str, user_id: str,
                base: str = "", tok: str = "") -> Dict[str, Any]:
    """Create the probe canvas through the SUPPORTED APIs.

    The previous version inserted the row straight into `canvases` with
    sqlite3 and wrote NO CanvasAudit row -- the exact inverse of what the
    product does, and a state the product never creates. Readers treat the
    audit trail as the source of truth, so every result earned on that fixture
    was measured on a canvas the product would never have produced. Creation
    now goes through POST /api/canvas/email/create and the body through
    PUT /api/canvas/{id}, so the fixture carries the same evidence trail a real
    user's canvas does. The direct-insert path is kept only as an explicit
    fallback for offline use and is reported when used.
    """
    import sqlite3
    import uuid
    canvas_id = str(uuid.uuid4())
    body_html = (f"<div><p>Quote for Steve</p>"
                 f"<p><b>{BODY_OLD}</b></p>"
                 f"<p>Rows 1-5 are the requested machines.</p>"
                 f"<!-- {marker} --></div>")
    content = {"to": "steve@example.com", "cc": "",
               "subject": "Quote for Steve", "body": body_html}
    if base and tok:
        import httpx as _h
        hdr = {"Authorization": f"Bearer {tok}",
               "Origin": base.replace("http://", "http://")}
        r = _h.post(f"{base}/api/canvas/email/create", headers=hdr,
                    trust_env=False, timeout=60,
                    json={"subject": "Quote for Steve",
                          "recipients": ["steve@example.com"],
                          "canvas_id": canvas_id, "user_id": user_id})
        if r.status_code != 200:
            raise SystemExit(f"canvas creation API failed: {r.status_code} "
                             f"{r.text[:200]}")
        made = (r.json() or {}).get("canvas_id") or canvas_id
        u = _h.put(f"{base}/api/canvas/{made}", headers=hdr, trust_env=False,
                   timeout=60, params={"canvas_type": "email"},
                   json=content)
        if u.status_code != 200:
            raise SystemExit(f"canvas content API failed: {u.status_code} "
                             f"{u.text[:200]}")
        return {"canvas_id": made, "content": content, "seeded_via": "api"}
    con = sqlite3.connect(db)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(canvases)")}
        row = con.execute("SELECT tenant_id, workspace_id, created_by, status, "
                          "canvas_type FROM canvases WHERE created_by=? AND "
                          "canvas_type='email' LIMIT 1", (user_id,)).fetchone()
        if row is None:
            row = con.execute("SELECT tenant_id, workspace_id, created_by, "
                              "status, canvas_type FROM canvases "
                              "WHERE canvas_type='email' LIMIT 1").fetchone()
        if row is None:
            raise SystemExit("no canvas row to copy tenant/workspace from")
        values = {"id": canvas_id, "name": f"C16 controlled {marker}",
                  "title": f"C16 controlled {marker}",
                  "description": "C16 controlled-planner probe",
                  "content": json.dumps(content), "canvas_type": row[4] or "email",
                  "status": row[3] or "active", "tenant_id": row[0],
                  "created_by": user_id, "workspace_id": row[1]}
        names = [c for c in values if c in cols]
        con.execute(f"INSERT INTO canvases ({','.join(names)}) VALUES "
                    f"({','.join('?' * len(names))})",
                    [values[n] for n in names])
        # The store's update path requires BOTH an owned Canvas row AND an
        # existing audit row: with no latest CanvasAudit it answers
        # "Canvas <id> not found" for a canvas that plainly exists, which reads
        # as a product failure but is really an incomplete fixture. Ownership is
        # also established by an authoring audit row, so seed the create row.
        import uuid as _u
        con.execute(
            "INSERT INTO canvas_audit (id, canvas_id, tenant_id, "
            "action_type, user_id, canvas_type, details_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,datetime('now'))",
            (str(_u.uuid4()), canvas_id, values["tenant_id"], "create",
             user_id, values["canvas_type"],
             json.dumps({"content": content, "data": content,
                         "name": values["name"]})))
        con.commit()
    finally:
        con.close()
    return {"canvas_id": canvas_id, "content": content}


def log_offset(world: str) -> int:
    log = WORLDS / world / "preview_backend.log"
    return log.stat().st_size if log.exists() else 0


def _sha256_of(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _fixture_sha(world: str) -> Optional[str]:
    """The frozen fixture both launches seed from. Identical across the sync and
    background launches is what makes their run dirs EQUIVALENT setups rather
    than merely similar ones."""
    p = WORLDS / world / "fixture" / "atom.db"
    return _sha256_of(p)[:32] if p.exists() else None


def _code_snapshot_sha(world: str) -> Optional[str]:
    """The immutable export both launches execute. Recorded so 'same code' is
    provable rather than assumed."""
    p = WORLDS / world / "code_manifest.json"
    if not p.exists():
        return None
    return _sha256_of(p)[:32]


def injection_proof(shim_port: int, log_off: int) -> Dict[str, Any]:
    """Prove the injection happened, stage by stage.

    'The provider loaded' and 'no fallback marker appeared' are NOT proof that a
    request occurred: the world registers the shim at startup and can decline
    before any planner call is ever made. A case whose injection is not proven
    here is INCONCLUSIVE, whatever the reply said.
    """
    import httpx as _h
    try:
        d = (_h.get(f"http://127.0.0.1:{shim_port}/log", trust_env=False,
                    timeout=20).json() or {})
    except Exception as exc:  # noqa: BLE001
        return {"proven": False, "problem": f"shim log unreachable: {exc}"}
    entries = d.get("log") or []
    completions = [e for e in entries if e.get("served") != "(models list)"]
    served = [e for e in completions if e.get("served") not in (None, "")]
    tool_calls = [e for e in completions if e.get("tool_mode")]
    return {
        "proven": bool(served),
        "problem": None if served else (
            "the shim received no completion request: the edit planner was "
            "never called, so nothing was injected and the case measured no "
            "effect at all"),
        "shim_log_entries": len(entries),
        "completion_requests": len(completions),
        "requests_served": len(served),
        "tool_mode_requests": len(tool_calls),
        "gate_missed": d.get("gate_missed") or [],
        "stall_hits": d.get("stall_hits") or [],
        "armed": d.get("armed") or {},
    }


def server_env_of(world: str) -> Dict[str, str]:
    """The environment the SERVER PROCESS actually received, as recorded by the
    launcher in `<run_dir>/server_env.json`.

    The fork is a claim about two numbers -- the interactive budget and the
    stall -- and the launcher filters the child environment through
    SERVER_ENV_WHITELIST, so a requested knob can be dropped before it ever
    reaches the server. Reading back what the child was given is the only
    positive observation available; the product's own `[deadline]` lines cannot
    be used, because they are emitted only when a budget check FAILS.
    """
    state = json.loads((WORLDS / world / "preview_stack.json").read_text())
    p = Path(state["run_dir"]) / "server_env.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return {}


def fallback_markers(world: str, offset: int = 0) -> List[str]:
    """Lines proving a NON-shim provider supplied the plan instead.

    `pinned_structured_call` documents a fallback: when the pinned call returns
    no result it retries UNPINNED across the workspace's real providers. A wrong
    shim script shape makes every structured attempt fail, that fallback fires,
    and the user sees a decline that looks identical to a planner refusal. So
    "no fallback provider supplied a replacement plan" has to be asserted, not
    assumed from the response.
    """
    log = WORLDS / world / "preview_backend.log"
    if not log.exists():
        return ["(no backend log)"]
    out: List[str] = []
    for line in log.read_text(errors="replace")[offset:].splitlines():
        if "retrying unpinned" in line or "structured_cascade_exhausted" in line:
            out.append(line.strip()[:160])
    return out[-8:]


def read_state(db: str, canvas_id: str) -> Dict[str, Any]:
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        audits = con.execute("SELECT id, action_type, created_at, details_json "
                             "FROM canvas_audit WHERE canvas_id=? ORDER BY "
                             "created_at, id", (canvas_id,)).fetchall()
        content = con.execute("SELECT content FROM canvases WHERE id=?",
                              (canvas_id,)).fetchone()
        ops = con.execute(
            "SELECT json_extract(parameters,'$.task_lifecycle.operations[0].status'),"
            "       json_extract(parameters,'$.task_lifecycle.operations[0].operation_id'),"
            "       id FROM goal_runs WHERE "
            "json_extract(parameters,'$.task_lifecycle.operations') IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 4").fetchall()
    finally:
        con.close()
    body = (content[0] if content else "") or ""
    return {"audit_count": len(audits),
            "audit_actions": [a[1] for a in audits],
            "audit_details": [str(a[3])[:200] for a in audits],
            "content": body,
            "has_new_text": BODY_NEW in body,
            "has_old_text": BODY_OLD in body,
            "operations": [{"status": o[0], "operation_id": o[1], "run_id": o[2]}
                           for o in ops]}



def ws_events(base: str, ws_url: str, token: str, channel: str,
              deadline: float,
              stop: Optional[threading.Event] = None) -> List[Dict[str, Any]]:
    """Subscribe to a channel and collect events until the deadline.

    Bounded by OBSERVED events, not elapsed time: the caller asserts on what
    arrived. An empty result is a real observation (the D5 empty-channel case),
    never an implicit pass.

    ``stop`` lets a caller that is waiting on some OTHER barrier (the durable
    terminal state) end collection the moment that barrier is reached. Without
    it the only correct call site is one where nothing else is being waited on
    -- and subscribing AFTER the fact silently observes nothing, because the
    event was emitted during the wait that preceded the subscription.
    """
    import asyncio
    import websockets
    got: List[Dict[str, Any]] = []

    async def _run() -> None:
        async with websockets.connect(f"{ws_url}?token={token}",
                                      open_timeout=20) as ws:
            await ws.send(json.dumps({"type": "subscribe",
                                      "channel": channel}))
            while time.time() < deadline:
                if stop is not None and stop.is_set():
                    return
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    return
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if isinstance(msg, dict) and msg.get("type") != "ping":
                    got.append(msg)

    try:
        asyncio.new_event_loop().run_until_complete(_run())
    except Exception as e:  # noqa: BLE001
        got.append({"subscribe_error": f"{type(e).__name__}: {e}"})
    return got


def _classify_durable_rows(rows: List[Any]) -> Dict[str, Any]:
    """Classify durable continuation rows. PURE -- no DB, no clock.

    Kept pure so the four conditions that matter can each be exercised
    directly (see durable_lookup_controls) instead of being inferred from
    whatever a live world happened to contain. A lookup that cannot
    distinguish these four is not evidence of anything.
    """
    if not rows:
        return {"found": False, "state": "missing", "duplicate": False}
    if len(rows) > 1:
        return {"found": True, "state": "duplicate", "duplicate": True,
                "count": len(rows)}
    status = (rows[0][1] or "").strip().lower()
    terminal = status in ("success", "completed", "failed", "error", "cancelled")
    return {"found": True, "duplicate": False, "count": 1,
            "state": ("terminal" if terminal else "running"), "status": status,
            "terminal": terminal}


def durable_lookup_controls() -> List[Dict[str, Any]]:
    """Prove the lookup tells missing / duplicate / running / terminal apart.

    Run every time and recorded in the report, so "no continuation" can never
    again be reported for a lookup that merely failed to find, or found more
    than one, or found one still running.
    """
    cases = [
        ("missing", [], "missing", False),
        ("duplicate", [("a", "running", "", "", "", "{}"),
                       ("b", "success", "", "", "", "{}")], "duplicate", True),
        ("running", [("a", "running", "", "", "", "{}")], "running", False),
        ("terminal", [("a", "success", "", "", "", "{}")], "terminal", False),
    ]
    out: List[Dict[str, Any]] = []
    for name, rows, want_state, want_dup in cases:
        got = _classify_durable_rows(rows)
        ok = (got.get("state") == want_state
              and bool(got.get("duplicate")) == want_dup)
        out.append({"control": name, "expected_state": want_state,
                    "observed_state": got.get("state"),
                    "expected_duplicate": want_dup,
                    "observed_duplicate": bool(got.get("duplicate")),
                    "ok": ok})
    return out


def identity_chain(db: str, canvas_id: str, session_id: str,
                   continuation_id: str = "",
                   origin_operation_id: str = "") -> Dict[str, Any]:
    """The four identities a canvas edit carries, and how they relate.

    A landed mutation can be attributed to the INTERACTIVE turn (whose
    lifecycle reservation minted the operation_id stamped on the audit row),
    to the CONTINUATION that re-ran the edit, or to neither. Those ids are not
    equal by construction and must not be assumed equal: the point of this
    reader is to make the relationship explicit and checkable, so the product
    can be judged on whether it RE-CONCILES the write, not on whether it
    happened to reuse an id.
    """
    import sqlite3
    out: Dict[str, Any] = {"canvas_id": canvas_id, "session_id": session_id,
                           "continuation_id": continuation_id or None,
                           "audit_rows": [], "read_ok": False,
                           "read_problem": None}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT id, action_type, session_id, details_json, created_at "
                "FROM canvas_audit WHERE canvas_id=? ORDER BY created_at",
                (canvas_id,)).fetchall()
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001
        out["read_problem"] = f"{type(exc).__name__}: {exc}"
        return out
    for r in rows:
        det: Dict[str, Any] = {}
        try:
            det = json.loads(r[3] or "{}")
        except Exception:  # noqa: BLE001
            pass
        out["audit_rows"].append({
            "audit_id": r[0], "action_type": r[1], "session_id": r[2],
            "created_at": r[4],
            "operation_id": det.get("operation_id"),
            "review_status": det.get("review_status"),
            "previous_audit_id": det.get("previous_audit_id")
                                or det.get("prior_audit_id"),
        })
    out["read_ok"] = True
    updates = [a for a in out["audit_rows"] if a["action_type"] == "update"]
    out["update_count"] = len(updates)
    # ZERO-ADDITIONAL-WRITES REGRESSION. Reconciliation must never write. The
    # proof is that exactly ONE audit row on this canvas carries an operation id
    # attributed to this request -- the continuation's own or the origin turn's.
    # Two such rows would mean the reconciliation path applied a second write.
    ids = [i for i in (continuation_id, origin_operation_id) if i]
    out["identity_operation_ids"] = ids or None
    out["rows_attributed_to_this_request"] = sum(
        1 for a in out["audit_rows"] if a.get("operation_id") in ids) if ids else 0
    if updates:
        last = updates[-1]
        out["landed_operation_id"] = last.get("operation_id")
        out["landed_review_status"] = last.get("review_status")
        out["landed_matches_continuation"] = bool(
            continuation_id) and last.get("operation_id") == continuation_id
        out["landed_by_interactive_attempt"] = bool(
            continuation_id) and last.get("operation_id") != continuation_id
        # Current revision means the LAST audit row on this canvas is the
        # mutation -- not that there is exactly one update. Seeding through the
        # supported APIs legitimately writes an earlier create + body update.
        out["current_revision_is_the_landed_row"] = bool(
            last.get("operation_id")
            and out["audit_rows"]
            and out["audit_rows"][-1].get("audit_id") == last.get("audit_id"))
    return out


def durable_continuation(db: str, session_id: str,
                         run_dir: str = "") -> Dict[str, Any]:
    """The durable background record for ONE continuation, identity-exact.

    Returns a verdict object, never a bare list, because "I found nothing" and
    "I could not look" are different claims and only one of them is a result.

    `lookup_ok` False means INCONCLUSIVE -- the run measured nothing. It must
    never be reported as "no continuation happened".
    """
    import sqlite3
    res: Dict[str, Any] = {
        "lookup_ok": False, "lookup_problem": None,
        "db_path": db, "server_database_url": None, "db_matches_server": None,
        "session_id": session_id, "rows": [], "row_count": 0,
    }
    # CROSS-CHECK: the world writes a NEW run dir on every relaunch, so the DB
    # this harness read can be a different file from the one the server is
    # actually using. That mismatch is silent -- every read succeeds, it just
    # reads the wrong world -- and it is indistinguishable from a product
    # defect at the assertion level. Bind the measured database to the served
    # configuration explicitly, or refuse to conclude.
    if run_dir:
        try:
            env = json.loads((Path(run_dir) / "server_env.json").read_text())
            served = str(env.get("DATABASE_URL") or "")
            res["server_database_url"] = served
            served_db = served.replace("sqlite:///", "").strip()
            res["db_matches_server"] = bool(
                served_db) and Path(served_db).resolve() == Path(db).resolve()
        except Exception as exc:  # noqa: BLE001
            res["lookup_problem"] = (
                f"server_env.json unreadable ({type(exc).__name__}); the "
                "served database could not be identified")
            return res
        if not res["db_matches_server"]:
            res["lookup_problem"] = (
                "harness db is not the server's db "
                f"(harness={db} server={served_db})")
            return res
    if not Path(db).exists():
        res["lookup_problem"] = f"db file does not exist: {db}"
        return res
    sql = ("SELECT id, status, result_summary, output_summary, "
           "error_message, metadata_json FROM agent_executions "
           "WHERE triggered_by='continuation' AND metadata_json LIKE ? "
           "ORDER BY started_at DESC")
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            raw = con.execute(sql, [f"%{session_id}%"]).fetchall()
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001
        res["lookup_problem"] = f"query failed: {type(exc).__name__}: {exc}"
        return res
    parsed: List[Dict[str, Any]] = []
    for r in raw:
        meta: Dict[str, Any] = {}
        try:
            meta = json.loads(r[5] or "{}")
        except Exception:  # noqa: BLE001
            pass
        # EXACT identity: the row must name THIS session, not merely contain
        # it as a substring somewhere in a metadata blob.
        if str(meta.get("session_id") or "") != session_id:
            continue
        parsed.append({
            "continuation_id": r[0], "status": r[1],
            "result_summary": (r[2] or "")[:300],
            "output_summary": (r[3] or "")[:300],
            "error_message": (r[4] or "")[:300],
            "session_id": meta.get("session_id"),
            "canvas_id": meta.get("canvas_id"),
            "originating_execution_id": meta.get("originating_execution_id"),
            "origin_operation_id": (meta.get("origin_operation_id")
                                    or (meta.get("continuation") or {}).get(
                                        "origin_operation_id")),
            "continuation": meta.get("continuation") or {},
        })
    res["rows"] = parsed
    res["row_count"] = len(parsed)
    res.update(_classify_durable_rows(
        [(p["continuation_id"], p["status"], "", "", "", "{}") for p in parsed]))
    if res.get("duplicate"):
        res["lookup_problem"] = (
            f"{len(parsed)} durable rows for one session; identity is ambiguous")
        return res
    res["lookup_ok"] = True
    if res.get("state") == "missing":
        res["lookup_problem"] = (
            "no durable continuation row for this session in the served db")
    return res


def durable_continuations(db: str, session_id: str = "") -> List[Dict[str, Any]]:
    """Backwards-compatible list view. Prefer `durable_continuation`, which
    reports whether the lookup itself was trustworthy."""
    res = durable_continuation(db, session_id)
    return res.get("rows") or []



def history_has_continuation(base: str, headers: Dict[str, str],
                             session_id: str, needle: str) -> Dict[str, Any]:
    """Reload the session from the API -- not from process memory."""
    import httpx
    try:
        r = httpx.get(f"{base}/api/chat/history/{session_id}", headers=headers,
                      trust_env=False, timeout=60)
        if r.status_code != 200:
            return {"reachable": False, "status_code": r.status_code,
                    "has_continuation": False}
        body = r.json()
    except Exception as e:  # noqa: BLE001
        return {"reachable": False, "error": f"{type(e).__name__}: {e}",
                "has_continuation": False}
    blob = json.dumps(body)
    return {"reachable": True, "status_code": r.status_code,
            "has_continuation": needle.lower() in blob.lower(),
            "has_raw_bracket_diagnostic": "[background continuation" in blob,
            "bytes": len(blob)}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--world", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=8074)
    ap.add_argument("--relaunch", action="store_true",
                    help="stop and restart the world AFTER the shim is "
                         "listening. Required: provider discovery runs at server "
                         "startup, so a world launched before the shim exists "
                         "never registers the provider and the pin silently "
                         "falls back to the normal route.")
    ap.add_argument("--keep-shim", action="store_true")
    ap.add_argument("--mode", default="sync",
                    choices=["sync", "bg-success", "bg-failure"])
    ap.add_argument("--interactive-budget", type=float, default=60.0,
                    help="ATOM_CHAT_REQUEST_DEADLINE_SECONDS for the "
                         "background launch. MUST exceed the product's reply-leg "
                         "reserve (ATOM_REPLY_LEG_MIN_SECONDS, default 40) or "
                         "the edit leg is skipped before it can ever start")
    ap.add_argument("--stall-seconds", type=float, default=40.0,
                    help="overrun the edit leg's structured call so the REAL "
                         "async fork is taken; gated on the armed tool so only "
                         "that call stalls and the background retry answers")
    ap.add_argument("--only", choices=["sync", "bg"], default="",
                    help="run exactly ONE case. The two cases need DIFFERENT "
                         "interactive budgets, and the budget is fixed at server "
                         "launch, so they must be separate launches against the "
                         "same immutable export")
    ap.add_argument("--stall-first-n", type=int, default=1,
                    help="how many tool-gated calls may consume the armed stall. "
                         "1 = only the interactive edit leg stalls. Raise it to "
                         "hold the CONTINUATION's first attempt too, which opens "
                         "the window in which the interactive attempt's own "
                         "write can land first -- the only way to exercise the "
                         "origin-operation reconciliation path live, since the "
                         "continuation's-own-write path never touches it")
    ap.add_argument("--empty-notification-channel", action="store_true",
                    help="subscribe to NO websocket channel. Proves the durable "
                         "outcome survives an empty notification channel and "
                         "that the mutation is neither lost nor repeated")
    ap.add_argument("--tool-name", default=PLANNER_TOOL_NAME,
                    help="tool name the structured call requests; captured from "
                         "the request, not assumed")
    args = ap.parse_args(argv)

    import httpx

    # BUDGET FEASIBILITY PRECONDITION (2026-09-27). The product reserves
    # ATOM_REPLY_LEG_MIN_SECONDS (default 40) of the request budget for the
    # answer and refuses to START a pre-reply leg it cannot pay for. A budget at
    # or below that reserve skips the canvas-edit leg entirely: no edit, no fork,
    # and the shim is never called because the edit planner never runs. That is
    # arithmetically incapable of reaching the background path and presents as a
    # product decline. Refuse it up front instead of spending a run on it.
    _reply_reserve = float(
        os.environ.get("ATOM_REPLY_LEG_MIN_SECONDS", "40") or 40)
    if args.only != "sync":
        if args.interactive_budget <= _reply_reserve:
            print(f"refusing to run: --interactive-budget "
                  f"{args.interactive_budget}s cannot reserve "
                  f"{_reply_reserve}s for the reply leg, so the canvas-edit leg "
                  f"would be skipped before it starts. Use a budget above "
                  f"{_reply_reserve}s (60s is the calibrated default).")
            return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state = json.loads((WORLDS / args.world / "preview_stack.json").read_text())
    db = state["db_path"]
    base = f"http://127.0.0.1:{args.port}"
    origin = f"http://localhost:{args.port}"

    shim_port = free_port()
    script = out / "planner_script.json"
    # One consistent, ACCEPTING plan. This is the only injected thing.
    if args.mode == "bg-failure":
        # Accept the plan, then fail AFTER acceptance on a field no op can
        # supply, so the failure is an execution-time one rather than another
        # planner decline. The continuation then has to report a terminal
        # failure with zero effects.
        entry_response: Dict[str, Any] = {
            "tool_call": {"name": args.tool_name,
                          "arguments": json.loads(
                              plan_json(wants_edit=True,
                                        ops=UNAPPLIABLE_OPS,
                                        reply="Updated the quote validity."))}}
    else:
        entry_response = {
            "tool_call": {"name": args.tool_name,
                          "arguments": json.loads(
                              plan_json(wants_edit=True, ops=PATCH_OPS))}}
    scripted: Dict[str, Any] = {"response": entry_response}
    if args.mode in ("bg-success", "bg-failure"):
        # NOTE: the stall is NOT armed here. Case 1 (synchronous) and case 2
        # share one world launch and therefore one interactive budget, so a
        # stall armed at script time was always consumed by CASE 1 -- which then
        # overran the shortened budget and was refused, taking case 1's 15/15
        # with it. The stall is armed explicitly, for the background leg only,
        # immediately before that leg's request.
        scripted["stall_seconds"] = 0
        scripted["stall_first_n"] = 0
    write_script(script, [{"match": "CanvasEditPlan",
                           "response": scripted}])
    capture = out / "shim_requests.jsonl"
    proc = start_shim(script, shim_port, capture=capture)
    print(f"shim on :{shim_port}  model {SHIM_MODEL}")

    if args.relaunch:
        # Order matters and getting it wrong is SILENT, which is the whole reason
        # the harness asserts the shim log was written rather than trusting the
        # response body.
        #   1. providers are discovered at server STARTUP, so the shim must be
        #      listening first, or `c16-shim` is never registered as a client;
        #   2. a fresh `up` seeds a NEW run dir from the repo's config, so the
        #      shim entry has to be written into THAT run dir, not the old one;
        #   3. the server then restarts against the same run dir to see it.
        # Miss any step and `build_provider_model_pin` returns {} "because the
        # pin names a provider this workspace cannot call at all" -- the planner
        # falls back to the real route and the control quietly does nothing.
        stack = BACKEND / "scripts" / "orchestration_acceptance" / "preview_stack.py"
        py = str(BACKEND / "venv314" / "bin" / "python")
        env = dict(os.environ)

        wiring: Dict[str, Any] = {}

        def launch(reuse: str = "", pin: str = "") -> bool:
            subprocess.run([py, str(stack), "--world", args.world, "down"],
                           capture_output=True, text=True, timeout=300, env=env)
            time.sleep(3)
            cmd = [py, str(stack), "--world", args.world, "up",
                   "--backend-port", str(args.port), "--api-only"]
            if reuse:
                cmd += ["--reuse-run", reuse]
            e2 = dict(env)
            if pin:
                e2["ATOM_ASYNC_EDIT_PLAN_MODEL"] = pin
            # THE BUDGET KNOB (2026-09-27). The server filters its environment
            # through SERVER_ENV_WHITELIST, so a requested knob is stripped
            # unless it is passed through explicitly; the default is the
            # product's own CHAT_TURN_BUDGET_DEFAULT_SECONDS. Applied ONLY to
            # the background launch: the synchronous case is earned under the
            # product defaults, and the two cases need different budgets, which
            # is why they are separate launches (--only).
            if args.mode != "sync" and args.only != "sync":
                e2["ATOM_CHAT_REQUEST_DEADLINE_SECONDS"] = str(
                    args.interactive_budget)
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=1800, env=e2, cwd=str(REPO))
            for line in (r.stdout or "").splitlines():
                if any(k in line for k in ("backend :", "world ", "FAILED",
                                           "frontend", "reuse-run")):
                    print("   ", line.strip())
            return r.returncode == 0

        print("  [1/3] fresh run dir with the shim listening")
        if not launch():
            return 2
        wiring = point_world_at_shim(args.world, shim_port)
        print(f"  [2/3] shim registered in the world DB as {wiring['provider_key']}")
        print("  [3/3] restart on the same run dir so the loader sees it")
        if not launch(reuse=wiring["run_dir"], pin=wiring["pin"]):
            return 2
        wiring["relaunched_with_pin"] = wiring["pin"]
    else:
        wiring = point_world_at_shim(args.world, shim_port)
    print(f"  world provider config -> {wiring['base_url']}")

    if args.relaunch:
        state = json.loads((WORLDS / args.world / "preview_stack.json").read_text())
        db = state["db_path"]
        # A relaunch seeds a NEW run dir, so the world's admin password is the
        # developer's again and login would 401. Scoped exactly like
        # preview_login.py: refuse any path outside an acceptance world, and never
        # leave TESTING set (which would redirect the write to the scratch DB).
        import sqlite3 as _s3
        _db = str(Path(db).resolve())
        if "acceptance_worlds" not in _db:
            raise SystemExit(f"refusing to write outside a world: {_db}")
        os.environ.pop("TESTING", None)
        os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
        os.environ["ATOM_DATA_DIR"] = str(Path(_db).parent)
        os.environ["ENVIRONMENT"] = "development"
        from core.auth import get_password_hash
        from core.database import get_db_session
        from core.models import User
        with get_db_session() as _s:
            _u = _s.query(User).filter(User.email == LOGIN_EMAIL).first()
            if _u is None:
                raise SystemExit(f"{LOGIN_EMAIL} not present in this world")
            _u.hashed_password = get_password_hash(LOGIN_PASSWORD)
            _s.commit()
        print("  world admin password set for this run (value never logged)")

    report: Dict[str, Any] = {
        "schema": "lane3-c16-controlled-planner-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": args.world,
        # The launch this result belongs to, tied explicitly so a result can
        # never be read against a different server's configuration.
        "launch": {
            "only": args.only or ("sync" if args.mode == "sync" else "bg"),
            "run_dir": state.get("run_dir"),
            "db_path": db,
            "port": args.port,
            "effective_interactive_budget": server_env_of(args.world).get(
                "ATOM_CHAT_REQUEST_DEADLINE_SECONDS") or "(product default)",
            "interactive_budget_requested": (
                args.interactive_budget
                if (args.mode != "sync" and args.only != "sync") else None),
            "reply_leg_reserve_seconds": _reply_reserve,
            "fixture_sha256": _fixture_sha(args.world),
            "canvas_seeded_via": "api",
            "code_snapshot_sha256": _code_snapshot_sha(args.world),
        },
        "scope": ("ONLY the planner's model response is injected. Auth, "
                  "authorization, reservation, execution claim, mutation, audit, "
                  "read-back, verification and finalization all run for real. "
                  "This is EFFECT-LAYER coverage and is NOT evidence that the "
                  "production planner accepts canvas edits."),
        "shim": {"port": shim_port, "script": str(script),
                 "provider_key": wiring.get("provider_key"), "pin": wiring.get("pin"),
                 "model": SHIM_MODEL, "base_url": wiring.get("base_url"),
                 "scripted_plan": json.loads(
                     plan_json(wants_edit=True, ops=PATCH_OPS))},
    }

    try:
        token = httpx.post(f"{base}/api/auth/login", trust_env=False, timeout=30,
                           headers={"Origin": origin},
                           json={"username": LOGIN_EMAIL,
                                 "password": LOGIN_PASSWORD}).json()
        tok = (token or {}).get("access_token")
        if not tok:
            report["error"] = "login failed against the isolated candidate"
            print(report["error"])
            return 2
        headers = {"Authorization": f"Bearer {tok}"}
        who = (token.get("user") or {}) if isinstance(token, dict) else {}
        uid = who.get("id") or (httpx.get(f"{base}/api/auth/me", headers=headers,
                                          trust_env=False,
                                          timeout=30).json().get("id"))
        if not uid:
            report["error"] = "could not resolve the authenticated user id"
            return 2
        report["authenticated_user_id"] = uid

        # ---------------- case 1: synchronous edit -----------------------
        log_off = log_offset(args.world)
        marker = f"C16SYNC-{int(time.time())}"
        seeded = seed_canvas(db, marker, uid, base=base, tok=tok)
        before = read_state(db, seeded["canvas_id"])
        r = httpx.post(f"{base}/api/chat/message", headers=headers,
                       trust_env=False, timeout=900,
                       json={"message":
                             f"in the open canvas, change the quote validity "
                             f"from 15 days to 30 days and mark the edit {marker}",
                             "session_id": f"c16-sync-{marker}",
                             "user_id": uid,
                             "context": {"canvas": {"id": seeded["canvas_id"]},
                                         "canvas_content": seeded["content"],
                                         "canvas_type": "email",
                                         "canvas_title": "C16 controlled"}})
        payload = r.json() if r.status_code == 200 else {"raw": r.text[:300]}
        deadline = time.time() + 120
        after = read_state(db, seeded["canvas_id"])
        while time.time() < deadline and not after["has_new_text"]:
            time.sleep(3)
            after = read_state(db, seeded["canvas_id"])
        log = shim_log(shim_port)
        served = [e for e in (log.get("log") or [])
                  if "CanvasEditPlan" in str(e.get("served") or "")
                  and "tool_call" in str(e.get("served") or "")]
        reply = str(payload.get("message") or "")
        ce = {}
        for _cand in (payload.get("canvas_edit"),
                      (payload.get("metadata") or {}).get("canvas_edit"),
                      (payload.get("data") or {}).get("canvas_edit"),
                      (payload.get("data") or {}).get("canvasEditor"),
                      payload.get("canvasEditor")):
            if isinstance(_cand, dict) and _cand:
                ce = _cand
                break
        report["response_keys"] = sorted(payload.keys()) if isinstance(
            payload, dict) else []
        report["response_preview"] = redact(
            {k: v for k, v in payload.items()
             if k not in ("message", "content")}) if isinstance(
            payload, dict) else str(payload)[:300]
        case1 = {
            "name": "synchronous edit",
            "status_code": r.status_code,
            "execution_id": payload.get("execution_id"),
            "canvas_edit": ce,
            "reply": reply[:600],
            "before": {"audit_count": before["audit_count"],
                       "has_new_text": before["has_new_text"]},
            "after": {"audit_count": after["audit_count"],
                      "audit_actions": after["audit_actions"],
                      "has_new_text": after["has_new_text"],
                      "has_old_text": after["has_old_text"],
                      "operations": after["operations"]},
            "checks": {
                "injection_was_consumed": bool(served),
                "injection_hits": len(served),
                # Measured as a DELTA from the post-seed state, not an absolute
                # count. Seeding through the supported APIs writes its own
                # audited `update` (create + body), so an absolute count of one
                # is only true for a hand-seeded fixture. What matters is that
                # the REQUEST added exactly one mutation.
                "exactly_one_audit_row": (
                    after["audit_actions"].count("update")
                    - before["audit_actions"].count("update") == 1),
                "durable_content_has_the_intended_change":
                    after["has_new_text"],
                "the_old_text_is_gone": not after["has_old_text"],
                "reported_updated_true": ce.get("updated") is True,
                "reported_verified": ce.get("outcome") == "completed",
                "postcondition_verified": ce.get("postcondition_verified") is True,
                "reported_audit_id_present": bool(ce.get("audit_id")),
                "reported_canvas_is_the_edited_one":
                    ce.get("canvas_id") == seeded["canvas_id"],
                "execution_identity_present": bool(payload.get("execution_id")),
                "operation_identity_present": bool(ce.get("operation_id")),
                "no_stranded_operation": not any(
                    o.get("status") == "pending" for o in after["operations"]),
            },
        }
        fb = fallback_markers(args.world, log_off)
        case1["checks"]["accepted_plan_is_the_injected_plan"] = any(
            BODY_OLD in str(d) and BODY_NEW in str(d)
            for d in after["audit_details"]) or (
                after["has_new_text"] and after["has_old_text"] is False)
        case1["checks"]["no_fallback_provider_supplied_the_plan"] = not fb
        case1["fallback_evidence"] = fb
        case1["boundaries"] = {
            "b1_served": case1["checks"]["injection_was_consumed"],
            "b2_parser_accepted":
                case1["checks"]["accepted_plan_is_the_injected_plan"],
            "b3_no_fallback":
                case1["checks"]["no_fallback_provider_supplied_the_plan"],
            "b4_mutation_audited":
                case1["checks"]["exactly_one_audit_row"],
            "b5_readback_verified":
                case1["checks"]["durable_content_has_the_intended_change"],
        }
        case1["pass"] = all(case1["checks"].values())
        # A case whose injection is not PROVEN did not measure the effect it
        # claims to measure. It is inconclusive, not a failure.
        case1["injection_proof"] = injection_proof(shim_port, log_off)
        if not case1["injection_proof"].get("proven"):
            case1["inconclusive"] = True

        if args.mode != "sync" and args.only != "sync":
            # ---- background: the SAME request, now through the real fork ----
            marker = f"C16BG-{args.mode.upper()}-{int(time.time())}"
            bseed = seed_canvas(db, marker, uid, base=base, tok=tok)
            # Post-seed audit baseline: seeding through the supported APIs
            # writes its own audited create + update, so the request's effect is
            # measured as a delta from here.
            bseed_before = read_state(db, bseed["canvas_id"])
            # Arm the stall for THIS leg only, and re-arm the per-key counters.
            # The counter is global over the shim's life, so without this the
            # budget is already spent and the background planner call answers
            # inside the interactive budget, no fork is taken, and every
            # "background" assertion silently measures the SYNCHRONOUS path.
            rearm = httpx.get(
                f"http://127.0.0.1:{shim_port}/arm-stalls"
                f"?seconds={args.stall_seconds}&first_n={args.stall_first_n}"
                f"&tool={args.tool_name}",
                trust_env=False, timeout=20)
            print(f"  stall armed for the {args.tool_name} call only: "
                  f"{rearm.status_code} {rearm.text[:90]}")
            # SUBSCRIBE BEFORE EXECUTION (2026-09-27). The continuation emits
            # `chat_continuation` from _apply_effects(), which runs BEFORE the
            # durable record goes terminal -- and the whole continuation
            # finishes seconds after the fork, which happens BEFORE the
            # interactive reply is even returned to this process. So the
            # subscription must be live BEFORE the request is issued, and the
            # request must therefore be issued on its own thread. Subscribing
            # after the reply (as this did) can only ever miss the event, and
            # did: the product broadcast, the harness saw nothing.
            ws_base = base.replace("http://", "ws://")
            ws_url = f"{ws_base}/ws/default"
            _stop = threading.Event()
            _collected: List[Dict[str, Any]] = []
            _wait_deadline = time.time() + 420
            _t = threading.Thread(
                target=lambda: _collected.extend(
                    ws_events(base, ws_url, tok, f"user:{uid}",
                              _wait_deadline + 30, stop=_stop)),
                daemon=True)
            if not args.empty_notification_channel:
                _t.start()
            time.sleep(2)  # let the subscription land BEFORE the request

            _breply: Dict[str, Any] = {}

            def _do_request() -> None:
                _breply["resp"] = httpx.post(
                    f"{base}/api/chat/message", headers=headers,
                    trust_env=False, timeout=1800,
                    json={"message": ("in the open canvas, change the quote "
                                      "validity from 15 days to 30 days and "
                                      f"mark the edit {marker}"),
                          "session_id": f"c16-bg-{marker}", "user_id": uid,
                          "context": {"canvas": {"id": bseed["canvas_id"]},
                                      "canvas_content": bseed["content"],
                                      "canvas_type": "email",
                                      "canvas_title": "C16 background"}})

            _rt = threading.Thread(target=_do_request, daemon=True)
            _rt.start()
            _rt.join(timeout=1800)
            breply = _breply.get("resp")
            if breply is None:
                raise SystemExit("background request produced no response")
            bp = breply.json() if breply.status_code == 200 else {"raw": breply.text[:300]}
            expect_success = args.mode == "bg-success"
            meta = (bp.get("metadata") or {})
            ce_bg = meta.get("canvas_edit") or {}
            shared = meta.get("shared_tool_state") or meta.get("shared_tool") or {}
            pending_signal = bool(
                shared.get("async_continuation_forked")
                or shared.get("async_continuation_existing")
                or meta.get("async_continuation_forked")
                or ce_bg.get("outcome") in (None, "pending"))

            # Terminal state comes from the DURABLE record, observed, with a
            # bounded wait -- never from a fixed sleep. The lookup reports
            # whether it was TRUSTWORTHY, so "not found" and "could not look"
            # stay distinguishable for the whole wait.
            bg_sess = f"c16-bg-{marker}"
            run_dir = str(state.get("run_dir") or "")
            dur: Dict[str, Any] = {}
            deadline = _wait_deadline
            while time.time() < deadline:
                dur = durable_continuation(db, bg_sess, run_dir=run_dir)
                if dur.get("lookup_ok") and dur.get("terminal"):
                    break
                # An untrustworthy lookup will not become trustworthy by waiting.
                if not dur.get("lookup_ok"):
                    break
                time.sleep(4)
            # Let any in-flight event arrive, then stop collecting.
            time.sleep(3)
            _stop.set()
            if _t.is_alive() or _t.ident is not None:
                _t.join(timeout=20)
            evs = list(_collected)
            after_bg = read_state(db, bseed["canvas_id"])
            conts = dur.get("rows") or []
            term = (conts or [{}])[0]
            cont_events = [e for e in evs
                           if "continuation" in json.dumps(e).lower()]

            # The needle must be the CONTINUATION's own record, not text the
            # user typed -- "30 days" is in the request itself, so matching it
            # proved nothing about recovery.
            # The needle is the READABLE outcome text. It used to be the literal
            # marker "background continuation", which was welded into the old
            # bracketed rendering; the D5 change moved the binding into the
            # message's metadata and left a sentence in `content`, so a needle
            # on the old marker now reports a MISSING record for a record that
            # is present. Asserting the rendered sentence is also what proves
            # the user-facing form is the readable one.
            hist = history_has_continuation(
                base, headers, f"c16-bg-{marker}", "Background update")

            # Reconnect/reload must not repeat the mutation.
            audits_before = after_bg["audit_count"]
            httpx.post(f"{base}/api/chat/message", headers=headers,
                       trust_env=False, timeout=600,
                       json={"message": "what did you just change?",
                             "session_id": f"c16-bg-{marker}",
                             "user_id": uid,
                             "context": {"canvas": {"id": bseed["canvas_id"]},
                                         "canvas_content": after_bg["content"],
                                         "canvas_type": "email"}})
            after_reload = read_state(db, bseed["canvas_id"])

            # The fork is the PRECONDITION of the whole background case: if the
            # request completed synchronously then every assertion below measured
            # the synchronous path and none of it is evidence about the
            # background path. Assert it from the DURABLE record -- an
            # AgentExecution(triggered_by='continuation') row for this session
            # exists at all only when the product really forked.
            forked = bool(conts) and bool(dur.get("lookup_ok"))
            _cont_id_early = (term or {}).get("continuation_id") or ""
            _origin_early = (term or {}).get("origin_operation_id") or ""
            chain = identity_chain(db, bseed["canvas_id"], f"c16-bg-{marker}",
                                   _cont_id_early, _origin_early)
            # ATTRIBUTION (2026-09-27). The landed mutation must be attributable
            # to THIS request by EXACT id -- either the continuation's own
            # operation, or the interactive turn's lifecycle operation carried
            # across the fork. A row attributable to neither is an unrelated
            # edit and must never be reported as this request's completion.
            landed_op = chain.get("landed_operation_id")
            cont_id = (term or {}).get("continuation_id") or ""
            origin_op = ((term or {}).get("origin_operation_id") or "") or ""
            attribution = ("continuation" if landed_op and landed_op == cont_id
                           else "origin" if landed_op and landed_op == origin_op
                           else "unattributed" if landed_op else "none")
            chain["attribution"] = attribution
            chain["continuation_operation_id"] = cont_id or None
            chain["origin_operation_id"] = origin_op or None
            chain["current_revision_is_the_landed_row"] = bool(
                chain.get("current_revision_is_the_landed_row"))
            # The knob must be OBSERVED, not assumed: read back the budget the
            # server process was actually launched with, and require the stall
            # to exceed it (otherwise there is nothing to overrun and the
            # request was never going to fork).
            child_env = server_env_of(args.world)
            seen_budget = str(
                child_env.get("ATOM_CHAT_REQUEST_DEADLINE_SECONDS") or "")
            knob_ok = bool(seen_budget) and abs(
                float(seen_budget) - args.interactive_budget) < 0.51
            # The stall must overrun the EDIT LEG's slice, not the whole budget.
            # The leg is started only if the request can still reserve
            # ATOM_REPLY_LEG_MIN_SECONDS for the answer, so its slice is roughly
            # budget - reserve; a stall below that fits inside and the edit
            # completes synchronously with no fork.
            edit_leg_slice = max(0.0, args.interactive_budget - _reply_reserve)
            stall_exceeds_budget = args.stall_seconds > edit_leg_slice
            report["launch"]["edit_leg_slice_seconds"] = edit_leg_slice
            report["launch"]["stall_seconds"] = args.stall_seconds
            checks = {
                "injection_was_consumed": bool(served),
                "interactive_budget_knob_reached_the_server": knob_ok,
                "stall_exceeds_interactive_budget": stall_exceeds_budget,
                "durable_lookup_was_trustworthy": bool(dur.get("lookup_ok")),
                "durable_lookup_controls_all_green": all(
                    c["ok"] for c in durable_lookup_controls()),
                "background_path_was_actually_exercised": forked,
                "initial_response_was_pending_not_complete": pending_signal,
                "initial_response_was_pending_not_complete": pending_signal,
                "terminal_state_observed": term.get("status") in
                    ("success", "failed", "completed", "error"),
                "terminal_state_matches_expectation":
                    (term.get("status") in ("success", "completed")
                     if expect_success else
                     term.get("status") in ("failed", "error")),
                "durable_completion_recorded": bool(
                    term.get("result_summary") or term.get("output_summary")
                    or term.get("error_message")),
                "no_duplicate_effect_after_reconnect":
                    after_reload["audit_count"] == audits_before,
                "history_recovery_reachable": hist.get("reachable") is True,
                "no_stranded_operation": not any(
                    o.get("status") == "pending"
                    for o in after_bg["operations"]),
            }
            if expect_success:
                checks.update({
                    "exactly_one_update_audit":
                        after_bg["audit_actions"].count("update")
                        - bseed_before["audit_actions"].count("update") == 1,
                    "total_mutation_delta_is_exactly_one":
                        after_bg["audit_count"]
                        - bseed_before["audit_count"] == 1,
                    "intended_mutation_persisted": after_bg["has_new_text"],
                    "old_text_gone": not after_bg["has_old_text"],
                    "live_notification_received": bool(cont_events),
                    "history_shows_the_completed_edit":
                        hist.get("has_continuation") is True,
                    # D5: a reload must render a sentence, not the old
                    # "[background continuation - ...]" diagnostic line.
                    "history_has_no_raw_bracket_diagnostic": (
                        not hist.get("has_raw_bracket_diagnostic")),
                    "no_false_failure": term.get("status") in
                    ("success", "completed"),
                })
            else:
                checks.update({
                    "no_unsupported_success": not after_bg["has_new_text"],
                    "zero_update_audits":
                        after_bg["audit_actions"].count("update")
                        - bseed_before["audit_actions"].count("update") == 0,
                    "old_text_intact": after_bg["has_old_text"],
                    "no_false_success_in_summary":
                        "30 days" not in (term.get("result_summary") or ""),
                "history_reports_the_failure":
                    hist.get("has_continuation") is True,
            })
                if args.empty_notification_channel:
                    # The channel is empty on purpose. The durable outcome must
                    # still be recorded and the mutation must not be repeated by
                    # the absence of a live listener.
                    checks["empty_channel_lost_no_durable_outcome"] = bool(
                        term.get("result_summary") or term.get("error_message"))
                    checks["empty_channel_repeated_no_mutation"] = (
                        after_reload["audit_count"] == audits_before)
            fb_bg = fallback_markers(args.world, log_off)
            checks["no_fallback_provider_supplied_the_plan"] = not fb_bg
            bg = {"name": f"background {args.mode}", "mode": args.mode,
                  "status_code": breply.status_code,
                  "fork_observed": forked,
                  "durable_lookup": dur,
                  "durable_lookup_controls": durable_lookup_controls(),
                  "identity_chain": chain,
                  "durable_continuation_rows": len(conts),
                  "interactive_budget_requested": args.interactive_budget,
                  "stall_seconds": args.stall_seconds,
                  "interactive_budget_seen_by_server": seen_budget,
                  "pending_signal": pending_signal,
                  "pending_signal_source": {
                      "shared_forked": bool(shared.get("async_continuation_forked")),
                      "metadata_forked": bool(meta.get("async_continuation_forked")),
                      "initial_outcome": ce_bg.get("outcome")},
                  "initial_reply": str(bp.get("message") or "")[:400],
                  "terminal": term, "after": after_bg,
                  "ws_events_seen": len(evs),
                  "continuation_events": cont_events[:4],
                  "history": hist,
                  "audit_count_before_reconnect": audits_before,
                  "audit_count_after_reconnect": after_reload["audit_count"],
                  "fallback_evidence": fb_bg,
                  "checks": checks}
            # INJECTION PROOF (2026-09-27). "The provider loaded" and "no
            # fallback marker" do not prove a request happened. The whole chain
            # must be visible: the edit leg ran, the armed stall was consumed by
            # the tool-gated call, and the shim actually served the plan.
            bg_injection = injection_proof(shim_port, log_off)
            bg["injection_proof"] = bg_injection
            edit_leg_ran = bg_injection.get("tool_mode_requests", 0) > 0
            stall_consumed = bool(bg_injection.get("stall_hits"))
            bg["edit_leg_ran"] = edit_leg_ran
            bg["intended_stall_consumed"] = stall_consumed
            checks["injection_was_proven_at_the_shim"] = (
                bg_injection.get("proven") is True)
            checks["edit_leg_actually_ran"] = edit_leg_ran
            checks["intended_stall_was_consumed"] = stall_consumed
            checks["no_unmatched_request_drew_the_stall"] = not (
                bg_injection.get("gate_missed") or [])
            # The landed mutation must be THIS request's, by exact id, and must
            # still be the canvas's current revision. Only meaningful when a
            # mutation was EXPECTED: the failure case asserts the opposite (no
            # mutation at all), so scoring attribution there would demand a
            # landed edit precisely when the product is right to have none.
            if expect_success:
                # Reconciliation must add no write of its own: exactly one audit
                # row on the canvas may carry an operation id attributed to this
                # request.
                checks["reconciliation_wrote_nothing_additional"] = (
                    chain.get("rows_attributed_to_this_request") == 1)
                # ACCEPTANCE CORRECTION (2026-09-28): a single row with a
                # RECOGNISED operation id does not rule out an extra write under
                # a DIFFERENT id. Count EVERY audit row this request added to
                # this exact canvas, whatever id it carries, with the
                # API-seeding writes already in the baseline excluded.
                checks["total_mutation_delta_is_exactly_one"] = (
                    after_bg["audit_count"] - bseed_before["audit_count"] == 1)
                checks["landed_mutation_attributable_to_this_request"] = (
                    attribution in ("continuation", "origin"))
                checks["landed_mutation_is_the_current_revision"] = bool(
                    chain.get("current_revision_is_the_landed_row"))
            else:
                checks["no_mutation_landed_on_a_failed_turn"] = (
                    not landed_op)
            bg["pass"] = all(checks.values())
            # An unforked run, or a run whose durable lookup could not be
            # trusted, is INCONCLUSIVE -- not a product verdict. Reporting
            # "no continuation" for a lookup that failed is how a harness
            # artifact gets recorded as a product defect.
            bg["inconclusive"] = (
                (not forked) or (not dur.get("lookup_ok"))
                or (not bg_injection.get("proven")))
            if bg["inconclusive"]:
                verdict = ("INCONCLUSIVE (durable lookup untrustworthy: "
                           f"{dur.get('lookup_problem')})"
                           if not dur.get("lookup_ok")
                           else "INCONCLUSIVE (no fork: background path not exercised)")
            else:
                verdict = "PASS" if bg["pass"] else "FAIL"
            report[f"case_{args.mode}"] = bg
            print(f"\ncase {args.mode}: {verdict}")
            for k, v in checks.items():
                print(f"   {'ok  ' if v else 'FAIL'} {k}")
            if not bg["pass"]:
                print(f"   terminal: {json.dumps(term)[:300]}")
                print(f"   ws_events_seen: {len(evs)} "
                      f"cont_events: {len(cont_events)}")
                print(f"   history: {json.dumps(hist)[:220]}")
            overall = bg["pass"]
        elif args.only == "sync":
            overall = case1["pass"]
        else:
            overall = case1["pass"]
        if args.only != "bg":
            report["case_1_synchronous"] = case1
            report["case_1_injection_proof"] = case1.get("injection_proof")
            print(f"\ncase 1 synchronous: {'PASS' if case1['pass'] else 'FAIL'}")
            for k, v in case1["checks"].items():
                print(f"   {'ok  ' if v else 'FAIL'} {k}")
            if not case1["pass"]:
                print(f"   reply: {reply[:300]}")
                print(f"   after : {json.dumps(case1['after'])[:300]}")
                if case1.get("injection_proof", {}).get("problem"):
                    print(f"   INJECTION NOT PROVEN: "
                          f"{case1['injection_proof']['problem']}")
    finally:
        # Read BEFORE terminating: /log is served by the shim process, so
        # terminating first closed the port and made every consumption check
        # read as zero hits regardless of what had actually been served.
        report["shim_log"] = shim_log(shim_port).get("log") or []
        if not args.keep_shim:
            try:
                proc.terminate()
            except Exception:
                pass
        report["shim_log_tail"] = report["shim_log"][-12:]
    (out / f"c16_controlled_{args.mode}.json").write_text(
        json.dumps(redact(report), indent=2))
    print(f"\n-> {out/f'c16_controlled_{args.mode}.json'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
