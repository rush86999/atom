#!/usr/bin/env python3
"""Frozen single-request trace (review round 24).

ONE frozen ask, ONE run, five observation points — harness-only
instrumentation (no production changes):
  1. canvas identity + authorization (the app's own canvas endpoints)
  2. dispatch flags (from the response payload shape + server log slice)
  3. provider function names + VALIDATED served arguments (shim capture)
  4. selected branch + orchestrator return (full API payload + the
     execution row the orchestrator persisted — its own record of what
     it did)
  5. audit/readback state after the turn

Output: one trace artifact; classification fixture/shim/production is
made from the recorded evidence, not inferred.
"""
import argparse
import asyncio
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="old_path_01")
    ap.add_argument("--port", type=int, default=8021)
    args = ap.parse_args()

    from scripts.orchestration_acceptance import run_isolated as R
    BACKEND = R.BACKEND
    ACC = R.ACC
    FIXTURES = R.FIXTURES
    world = BACKEND / "data" / "acceptance_worlds" / args.name
    R.preflight(world)
    R.refresh_working_db(world)
    R.seed_unbound_canvas_copy(world)

    import httpx
    capture = world / "shim_requests.jsonl"
    if capture.exists():
        capture.unlink()
    shim = R.launch_shim(FIXTURES / "provider_shim" / "mutation_overlap.json", capture=capture)
    proc = R.launch_server(args.port, world, provider_shim=True)
    base = f"http://127.0.0.1:{args.port}"
    trace: dict = {"frozen_request": None, "points": {}}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "wrr", BACKEND / "scripts" / "workbook_read_replay.py")
        wrr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wrr)
        import os
        os.environ["DATABASE_URL"] = f"sqlite:///{world / 'data' / 'atom.db'}"
        token, user_id = wrr.mint_token()
        headers = {"Authorization": f"Bearer {token}"}

        # ---- FROZEN REQUEST (do not vary between probes) ----
        frozen_ask = ("in the open canvas, change the quote validity from 15 days "
                      "to 30 days and mark the edit OVLAP-A [ovlapref-a]")
        snapshot = Path("/tmp/canvas_snapshot.json").read_text()
        ctx = {"canvas": {"id": R.UNBOUND_CANVAS_ID},
               "canvas_content": snapshot, "canvas_type": "email",
               "canvas_title": "Quote copy (acceptance rig)"}
        trace["frozen_request"] = {"ask": frozen_ask, "context_keys": sorted(ctx),
                                   "canvas_id": R.UNBOUND_CANVAS_ID, "user_id": user_id}

        # POINT 1: canvas identity + authorization via the app's own endpoints
        p1 = {}
        for path in (f"/api/canvases/{R.UNBOUND_CANVAS_ID}", f"/api/canvas/{R.UNBOUND_CANVAS_ID}"):
            try:
                r = httpx.get(f"{base}{path}", headers=headers, timeout=15, trust_env=False)
                p1[path] = {"status": r.status_code,
                            "body_head": r.text[:200] if r.status_code != 200 else "(200 ok)"}
                if r.status_code == 200:
                    p1["canonical_read_ok"] = True
                    p1["resolved_content_len"] = len(r.text)
                    break
            except Exception as exc:
                p1[path] = {"error": str(exc)[:120]}
        # canonical reader equivalence (audit-first) on the copy pre-turn:
        con = sqlite3.connect(f"file:{world / 'data' / 'atom.db'}?mode=ro", uri=True)
        n_audit_pre = con.execute("SELECT count(*) FROM canvas_audit WHERE canvas_id=?",
                                  (R.UNBOUND_CANVAS_ID,)).fetchone()[0]
        con.close()
        p1["audit_rows_pre_turn"] = n_audit_pre
        trace["points"]["1_canvas_identity_authorization"] = p1

        # POINT 3/4: run the frozen turn; capture the FULL response payload
        session = f"acc-frozen-{int(time.time())}"
        t0 = time.time()
        r = httpx.post(f"{base}/api/chat/message", headers=headers, timeout=300,
                       trust_env=False,
                       json={"message": frozen_ask, "session_id": session,
                             "user_id": user_id, "context": ctx})
        payload = r.json()
        trace["points"]["4_branch_and_return"] = {
            "http_status": r.status_code,
            "full_payload": {k: (v if not isinstance(v, str) or len(v) < 4000 else v[:4000])
                             for k, v in payload.items()},
            "data_keys": sorted((payload.get("data") or {}).keys()),
            "intent": payload.get("intent"), "model": payload.get("model"),
            "execution_id": payload.get("execution_id"),
        }
        exec_id = payload.get("execution_id")

        # the orchestrator's own persisted record of this execution
        time.sleep(1)
        con = sqlite3.connect(f"file:{world / 'data' / 'atom.db'}?mode=ro", uri=True)
        row = con.execute("SELECT status, result_summary, metadata_json, completed_at "
                          "FROM agent_executions WHERE id=? OR (triggered_by='chat' AND "
                          "metadata_json LIKE ?) ORDER BY started_at DESC LIMIT 2",
                          (exec_id or "", f"%{session}%")).fetchall()
        steps = con.execute("SELECT step_type, substr(thought,1,120), substr(action,1,120), "
                            "substr(observation,1,160) FROM agent_reasoning_steps "
                            "WHERE execution_id=? ORDER BY step_number",
                            (exec_id or "",)).fetchall() if exec_id else []
        con.close()
        trace["points"]["4_execution_record"] = {
            "rows": [{"status": r0, "result_summary": str(r1)[:300],
                      "metadata_keys": sorted((json.loads(r2) if r2 and r2 != "{}" else {}).keys()),
                      "task_outcome": ((json.loads(r2) or {}).get("task_outcome") or {}) if r2 else None,
                      "completed_at": r3} for r0, r1, r2, r3 in row],
            "reasoning_steps": [list(s) for s in steps],
        }

        # POINT 5: audit/readback after the turn (poll briefly for async work)
        p5 = {}
        for _ in range(15):
            con = sqlite3.connect(f"file:{world / 'data' / 'atom.db'}?mode=ro", uri=True)
            audits = con.execute("SELECT action_type, details_json FROM canvas_audit "
                                 "WHERE canvas_id=? ORDER BY created_at DESC LIMIT 5",
                                 (R.UNBOUND_CANVAS_ID,)).fetchall()
            con.close()
            if audits and n_audit_pre == 0:
                break
            time.sleep(2)
        p5["audit_rows_post"] = [{"action_type": a, "details_head": str(d)[:200]}
                                 for a, d in audits]
        p5["marker_in_audit"] = any("OVLAP-A" in str(d) for _, d in audits)
        trace["points"]["5_audit_readback"] = p5

        # POINT 3: shim capture — function names + served arguments
        caps = []
        if capture.exists():
            caps = [json.loads(l) for l in capture.read_text().splitlines() if l.strip()]
        trace["points"]["3_provider_calls"] = {
            "count": len(caps),
            "calls": [{"model": c.get("model"), "tool_names": c.get("tool_names"),
                       "matched_key": c.get("matched_key"),
                       "system_head": (c.get("system_head") or "")[:90]} for c in caps],
        }

        # POINT 2: dispatch evidence — the server-log slice for this window
        log = (world / "server.log").read_text(errors="replace").splitlines()
        slice_lines = [l for l in log[-400:] if any(
            k in l for k in ("CHATCTX", "canvas", "timeline", "stage-timing", "planner",
                             "edit", "intent"))][-40:]
        trace["points"]["2_dispatch_log_slice"] = slice_lines

        out = ACC / "results" / f"frozen_trace__{int(time.time())}.json"
        out.write_text(json.dumps(trace, indent=1))
        print(f"[frozen-trace] written: {out.name}")
        print("P1:", json.dumps(p1)[:220])
        print("P4 keys:", trace["points"]["4_branch_and_return"]["data_keys"],
              "| exec:", str(exec_id)[:12], "| msg head:", str(payload.get("message"))[:100])
        print("P5 marker_in_audit:", p5["marker_in_audit"], "| audit rows:", len(p5["audit_rows_post"]))
        print("P3 calls:", trace["points"]["3_provider_calls"]["count"])
    finally:
        R.stop_server(proc)
        shim.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
