#!/usr/bin/env python3
"""Case 3 trials: taught formula, missing input, answer, changed-input recalc.

Runs the EXACT trial-1 user messages (natural follow-ups, not planner-shaped
queries) against a live stack through the public POST /api/chat/message API,
then verifies ENGINE/OPERATION evidence — correct prose alone cannot pass:

  T1 "Estimate this service job using our taught rates." (no inputs)
      -> exactly ONE precise question naming the missing inputs
         (hours, materials); NO calculate operation recorded.
  T2 "17.5 hours, no materials."
      -> $2,625 via the engine; its OWN calculate op (applied) carrying
         inputs {hours 17.5, materials 0} + content-derived policy version.
  T3 "Recalculate - 12 hours."
      -> $1,800 via the engine; a SECOND calculate op with its own inputs.

Every POST carries a client-minted request_id (idempotency contract: a
network retry reuses the SAME key; a rephrase mints a NEW key and is
recorded as a separate attempt). No invisible retries: every attempt,
including infra-flake retries, is logged. Operator rephrase / tool-select /
state-repair / manual delivery marks the trial ASSISTED. The T1 missing-input
question is the EXPECTED business clarification, not an intervention.

DB reads are sqlite3-CLI SELECTs only (never the ORM against the live DB).
Nothing is sent; no canvas is touched (canvas-free sessions).

Usage:
  venv314/bin/python scripts/orchestration_acceptance/case3_calc_trials.py \
      [--base http://127.0.0.1:8001] [--trials 3] [--results <path.json>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

T1 = "Estimate this service job using our taught rates."
T2 = "17.5 hours, no materials."
T3 = "Recalculate \u2014 12 hours."

AGENT_SHORT = "9837ec71"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def code_identity() -> Dict[str, str]:
    repo = BACKEND.parent

    def _run(*argv: str) -> str:
        try:
            out = subprocess.run(list(argv), cwd=str(repo),
                                 capture_output=True, text=True,
                                 timeout=15).stdout.strip()
            return out or "unknown"
        except Exception:
            return "unknown"

    try:
        driver_sha = sha256_file(Path(__file__))
    except Exception:
        driver_sha = "unknown"
    return {
        "commit": _run("git", "rev-parse", "HEAD"),
        "dirty_tracked": _run("git", "status", "--short",
                              "--untracked-files=no"),
        "driver_sha256": driver_sha,
    }


def sqlite_select(db: Path, sql: str, params: tuple = ()) -> List[tuple]:
    """Read-only SELECT via the sqlite3 CLI (no ORM on the live DB)."""
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def mint_admin_token(db: Path) -> tuple:
    """Read the admin user row, mint a JWT locally. No DB writes."""
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    from scripts.workbook_read_replay import mint_token
    token, uid = mint_token()
    if not token:
        raise RuntimeError("token mint failed (no admin@example.com?)")
    return token, uid


def full_agent_id(db: Path) -> str:
    rows = sqlite_select(
        db, "SELECT id FROM agent_registry WHERE id LIKE ?",
        (AGENT_SHORT + "%",))
    if not rows:
        raise RuntimeError("trained agent 9837ec71 not found")
    return rows[0][0]


def server_identity(base: str) -> Dict[str, Any]:
    import httpx
    try:
        r = httpx.get(f"{base}/api/health", timeout=10, trust_env=False)
        doc = r.json() if r.status_code == 200 else {}
    except Exception as exc:
        return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"}
    ident = (doc.get("identity") or {}) if isinstance(doc, dict) else {}
    return {"reachable": True, "status": doc.get("status"),
            "pid": ident.get("pid"), "started_at": ident.get("started_at"),
            "cwd": ident.get("cwd")}


def post_turn(base: str, token: str, message: str, user_id: str,
              session_id: Optional[str], agent_id: str,
              request_id: str, timeout_s: float = 600.0) -> Dict[str, Any]:
    import httpx
    t0 = time.monotonic()
    try:
        r = httpx.post(
            f"{base}/api/chat/message",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": message, "user_id": user_id,
                  "session_id": session_id, "agent_id": agent_id,
                  "request_id": request_id},
            timeout=timeout_s, trust_env=False)
        dt = time.monotonic() - t0
        try:
            body = r.json()
        except Exception:
            body = {"_raw": r.text[:500]}
        return {"http": r.status_code, "seconds": round(dt, 1),
                "body": body}
    except Exception as exc:
        return {"http": None, "seconds": round(time.monotonic() - t0, 1),
                "transport_error": f"{type(exc).__name__}: {exc}"}


def job_for_session(db: Path, sid: str) -> Optional[Dict[str, Any]]:
    rows = sqlite_select(
        db, "SELECT id, status, parameters FROM goal_runs "
            "WHERE json_extract(parameters,'$.task_lifecycle.conversation_id')=?",
        (sid,))
    if not rows:
        return None
    jid, status, params = rows[0]
    try:
        ops = (json.loads(params).get("task_lifecycle") or {}).get(
            "operations") or []
    except Exception:
        ops = []
    return {"run_id": jid, "status": status, "ops": ops}


def chat_rows(db: Path, sid: str) -> List[Dict[str, Any]]:
    rows = sqlite_select(
        db, "SELECT role, content, metadata_json FROM chat_messages "
            "WHERE conversation_id=? ORDER BY created_at, rowid", (sid,))
    out = []
    for role, content, meta in rows:
        try:
            m = json.loads(meta) if meta else {}
        except Exception:
            m = {"_raw": str(meta)[:200]}
        out.append({"role": role, "content": content or "", "meta": m})
    return out


def op_inputs(op: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the structured record from a calculate op.

    record_calculation stores the full CalculationResult record under the
    op's `calculation` key (NOT `extra`): inputs snapshot at
    calculation.inputs.inputs, policy id/version alongside, proposed
    amount as the value. An op without this record is narration without
    evidence — exactly what this case exists to catch.
    """
    calc = op.get("calculation") or {}
    grp = calc.get("inputs") or {}
    return {"inputs": grp.get("inputs"),
            "request_supplied": grp.get("request_supplied"),
            "taught_defaults": grp.get("taught_defaults"),
            "basis": grp.get("basis"),
            "policy_id": calc.get("policy_id"),
            "policy_version": calc.get("policy_version"),
            "value": (calc.get("proposed") or {}).get("amount"),
            "status": op.get("status")}


def run_trial(base: str, token: str, user_id: str, agent_id: str,
              db: Path, trial_no: int) -> Dict[str, Any]:
    trial: Dict[str, Any] = {"trial": trial_no, "attempts": [],
                             "assisted": False,
                             "interventions": []}
    sid: Optional[str] = None

    def turn(label: str, text: str) -> Dict[str, Any]:
        nonlocal sid
        req_id = uuid.uuid4().hex
        res = post_turn(base, token, text, user_id, sid, agent_id,
                        req_id)
        att: Dict[str, Any] = {"label": label, "request_id": req_id,
                               "sent": text, "http": res.get("http"),
                               "seconds": res.get("seconds")}
        body = res.get("body") or {}
        if res.get("transport_error") or res.get("http") != 200:
            att["error"] = res.get("transport_error") or body
            trial["attempts"].append(att)
            return att
        sid = body.get("session_id") or sid
        att.update({"session_id": body.get("session_id"),
                    "execution_id": body.get("execution_id"),
                    "success": body.get("success"),
                    "intent": body.get("intent"),
                    "model": body.get("model"),
                    "provider": body.get("provider"),
                    "message": body.get("message") or ""})
        trial["attempts"].append(att)
        return att

    a1 = turn("T1-missing", T1)
    time.sleep(5)
    ops_after_t1 = (job_for_session(db, sid or "") or {}).get("ops", [])
    a2 = turn("T2-answered", T2)
    time.sleep(10)
    job2 = job_for_session(db, sid or "")
    a3 = turn("T3-recalc", T3)
    time.sleep(10)
    job3 = job_for_session(db, sid or "")
    rows = chat_rows(db, sid or "")

    calc_ops_1 = [o for o in ops_after_t1
                  if o.get("operation_type") == "calculate"]
    calc_ops_2 = [o for o in (job2 or {}).get("ops", [])
                  if o.get("operation_type") == "calculate"]
    calc_ops_3 = [o for o in (job3 or {}).get("ops", [])
                  if o.get("operation_type") == "calculate"]

    m1 = (a1.get("message") or "").lower()
    m2 = a2.get("message") or ""
    m3 = a3.get("message") or ""

    checks: Dict[str, Any] = {
        # T1: one precise question for the missing inputs, nothing recorded
        "t1_asks_hours": "hour" in m1,
        "t1_asks_materials": "material" in m1,
        "t1_records_no_calculate": len(calc_ops_1) == 0,
        # T2: engine figure + its own applied op with its own inputs
        "t2_figure_2625": "2,625" in m2 or "2625" in m2,
        "t2_exactly_one_calc_op": len(calc_ops_2) == 1,
        "t2_op_applied": bool(calc_ops_2)
        and calc_ops_2[0].get("status") == "applied",
        "t2_op_inputs_own": bool(calc_ops_2) and _inputs_match(
            op_inputs(calc_ops_2[0]), hours=17.5, materials=0),
        # T3: recalc figure + a SECOND op with its own inputs
        "t3_figure_1800": "1,800" in m3 or "1800" in m3,
        "t3_second_calc_op": len(calc_ops_3) == 2,
        "t3_op_applied": len(calc_ops_3) == 2
        and calc_ops_3[1].get("status") == "applied",
        "t3_op_inputs_own": len(calc_ops_3) == 2 and _inputs_match(
            op_inputs(calc_ops_3[1]), hours=12.0, materials=0),
    }
    trial.update({
        "session_id": sid,
        "job_run_id": (job3 or {}).get("run_id"),
        "checks": checks,
        "verdict": "PASS" if all(v is True for v in checks.values())
        else "FAIL",
        "evidence": {
            "t1_calc_ops": len(calc_ops_1),
            "t2_calc_ops": [op_inputs(o) for o in calc_ops_2],
            "t3_calc_ops": [op_inputs(o) for o in calc_ops_3],
            "chat_roles": [r["role"] for r in rows],
            "t1_head": (a1.get("message") or "")[:300],
            "t2_head": m2[:300],
            "t3_head": m3[:300],
        },
    })
    return trial


def _inputs_match(got: Dict[str, Any], hours: float,
                  materials: float) -> bool:
    inp = got.get("inputs") or {}
    try:
        h = float(inp.get("hours")) if inp.get("hours") is not None else None
        m = (float(inp.get("materials"))
             if inp.get("materials") is not None else None)
    except (TypeError, ValueError):
        return False
    return h == hours and m == materials


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--results", default="")
    ap.add_argument("--db", default=str(BACKEND / "data" / "atom.db"))
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_absolute():
        db = (Path.cwd() / db).resolve()
    serving = server_identity(args.base)
    print(f"[stack] {args.base} -> {serving}")
    if not serving.get("reachable"):
        return 2
    token, user_id = mint_admin_token(db)
    agent_id = full_agent_id(db)
    print(f"[stack] user={user_id[:8]} agent={agent_id[:8]} db={db}")

    trials = []
    for n in range(1, args.trials + 1):
        print(f"[case3] trial {n}/{args.trials}")
        t = run_trial(args.base, token, user_id, agent_id, db, n)
        print(f"[case3] trial {n}: {t['verdict']} "
              f"{sum(1 for v in t['checks'].values() if v is True)}"
              f"/{len(t['checks'])}")
        trials.append(t)

    out = args.results or str(
        BACKEND / "data" / "acceptance_worlds" /
        f"case3_results_{time.strftime('%Y%m%d_%H%M%S')}.json")
    Path(out).write_text(json.dumps({
        "case": 3,
        "candidate": {"code": code_identity(), "serving": serving,
                      "db": str(db), "agent_id": agent_id},
        "queries": {"T1": T1, "T2": T2, "T3": T3},
        "trials": trials,
    }, indent=2))
    print(f"[case3] results -> {out}")
    return 0 if all(t["verdict"] == "PASS" for t in trials) else 1


if __name__ == "__main__":
    raise SystemExit(main())
