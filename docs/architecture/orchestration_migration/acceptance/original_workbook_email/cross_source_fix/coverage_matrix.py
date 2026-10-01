# -*- coding: utf-8 -*-
"""END-TO-END COVERAGE MATRIX over real data (2026-09-30 final
activation directive): every gate class in the consolidated pipeline,
driven through the LIVE app with one registered user across multiple
sessions (registration rate limits bind per-user creation, not
sessions), mutation-intent labels so canvas writes on EDIT turns are
expected while any write on a non-edit turn is a failure, and
per-turn latency.

Gate classes covered:
  research: direct ask / filename confirmation / bare retry / bare
  approval / rerun inheritance (odd wording) / cross-source (sources
  explicit) / row-assertion binding / compound research+learning /
  compound research+presentation
  presentation: formatting-only (reply and canvas variants)
  edit: explicit instruction (mutation EXPECTED) / nomination without
  grant (no mutation) / research-after-edit (no mutation)
  learning: opening cue / always-cue / learn-to with destination
  ambiguity: unknown reference / question form
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[6] / "backend"
sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402

BASE = "http://127.0.0.1:8001"
DB = BACKEND / "data" / "atom.db"
ASK8 = ("find the prices of these 8 machines in Consolidated Price List "
        "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
        "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
ASK4 = ("find the prices for No. 381, U-22, SLE24-16 and GSL48-16 in "
        "Consolidated Price List 2019.xlsx")
ROW338 = ("roper whitney and tennsmith are 2 brands under 1 ownership and "
          "they sometimes mix the names. no. 381 is on Tennsmith sheet of "
          "the workbook under row 338. here's the data: 381 167072381 Roll "
          "Bending Machine, $3,254.00 . find this in the workbook")

# (message, expected_kinds, mutation_expected, canvas)
SESSIONS = [
    ("research_arc", [
        (ASK8, ["research"], False, False),
        ("That filename is correct", ["research"], False, False),
        ("search again", ["research"], False, False),
        ("check Chandrakant's email and or description in workbook to "
         "find correct sheet and row from workbook for confirmation",
         ["research"], False, True),
        (ROW338, ["research"], False, True),
        ("repeat the search and learn to include tennsmith sheet for "
         "roper whitney searches", ["research", "learning"], False, True),
        ("make it cleaner", ["presentation"], False, True),
        ("find this in the tracker", [], False, True),
    ]),
    ("edit_arc", [
        (ASK4, ["research"], False, True),
        ("update the No. 381 price in this draft to $3,254.00",
         ["canvas_edit"], True, True),
        ("search the file again", ["research"], False, True),
        ("the draft should mention the tennsmith sheet", [], False, True),
        ("make it cleaner", ["presentation"], True, True),
    ]),
    ("learning_arc", [
        ("remember that roper whitney ships from tulare",
         ["learning"], False, False),
        ("always include the Tennsmith sheet for roper whitney searches",
         ["learning"], False, False),
        (ASK4, ["research"], False, False),
        ("run the lookup again on that price sheet please",
         ["research"], False, False),
        ("what are the prices for No. 622 in the workbook?",
         ["research"], False, False),
    ]),
]


def ro_con():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    return con


def canvas_fp(cid):
    con = ro_con()
    row = con.execute(
        "SELECT content FROM canvases WHERE id=?", (cid,)).fetchone()
    audits = con.execute(
        "SELECT count(*) FROM canvas_audit WHERE canvas_id=? AND "
        "action_type != 'create'", (cid,)).fetchone()[0]
    con.close()
    return (hashlib.sha256((row[0] if row else "").encode())
            .hexdigest()[:12], audits)


async def register(c):
    stamp = uuid.uuid4().hex[:8]
    email = f"cov-{stamp}@example.com"
    for _ in range(5):
        reg = (await c.post(f"{BASE}/api/auth/register", json={
            "username": email, "email": email, "password": f"pw-{stamp}",
            "first_name": "Cov", "last_name": "Matrix"})).json()
        if reg.get("access_token"):
            return reg["access_token"], email
        await asyncio.sleep(45)
    return None, None


async def main():
    rows_out = []
    m = {"turns": 0, "decision_correct": 0, "lane_agree": 0,
         "omitted_research": 0, "unintended_mutation": 0,
         "missing_writes": 0, "teaching_attached": 0,
         "teaching_expected": 0, "bindings_captured": 0,
         "latency_ms": []}
    async with httpx.AsyncClient(trust_env=False, timeout=420) as c:
        token, email = await register(c)
        if not token:
            print("SKIP: registration rate-limited"); return 1
        headers = {"Authorization": f"Bearer {token}"}
        me = (await c.get(f"{BASE}/api/auth/me", headers=headers)).json()
        uid = str(me.get("id") or "")
        for sname, turns in SESSIONS:
            session = f"cov-{uuid.uuid4().hex[:8]}"
            cid = None
            for msg, want, mutate, attach in turns:
                if attach and cid is None:
                    cv = (await c.post(f"{BASE}/api/canvas",
                                        headers=headers, json={
                        "title": f"Cov {sname}",
                        "canvas_type": "document"})).json()
                    cid = cv.get("canvas_id")
                    await c.put(f"{BASE}/api/canvas/{cid}",
                                headers=headers,
                                json={"body": "<p>cov draft</p>"},
                                params={"canvas_type": "document"})
                fp0 = canvas_fp(cid) if cid else None
                t0 = time.time()
                r = (await c.post(f"{BASE}/api/chat/message",
                                  headers=headers, json={
                    "message": msg, "session_id": session,
                    "user_id": uid,
                    "request_id": f"req-{uuid.uuid4().hex[:8]}",
                    **({"context": {"canvas_id": cid}}
                       if (cid and attach) else {}),
                })).json()
                dt_ms = int((time.time() - t0) * 1000)
                m["latency_ms"].append(dt_ms)
                await asyncio.sleep(2)
                con = ro_con()
                row = con.execute(
                    """SELECT metadata_json FROM chat_messages
                       WHERE conversation_id=? AND role='assistant'
                       ORDER BY created_at DESC LIMIT 1""",
                    (session,)).fetchone()
                task = (json.loads(row[0]).get("pending_file_task")
                        if row else None) or {}
                con.close()
                meta = json.loads((row[0] if row else None) or "{}")
                td = meta.get("turn_decision") or {}
                kinds = [a["kind"] for a in
                         td.get("requested_actions") or []]
                rmeta = r.get("metadata") or {}
                ce = rmeta.get("canvas_edit") or {}
                wr = rmeta.get("workbook_result")
                model = r.get("model")
                if ce.get("updated"):
                    served = "edit_applied"
                elif model == "deterministic" and (
                        wr or meta.get("pending_file_result")):
                    served = "read"
                elif model == "deterministic":
                    served = "deterministic"
                else:
                    served = "planning"
                fp1 = canvas_fp(cid) if cid else None
                wrote = bool(fp0 and fp1 and (
                    fp0[0] != fp1[0] or fp1[1] > fp0[1]))
                m["turns"] += 1
                dec_ok = (kinds == want) or (
                    not want and "conversation" in kinds)
                if dec_ok:
                    m["decision_correct"] += 1
                lane_ok = (
                    ("research" in want
                     and served in ("read", "planning"))
                    or (want == ["presentation"] and served in (
                        "deterministic", "read", "edit_applied"))
                    or (want == ["canvas_edit"]
                        and served != "read")
                    or (want == ["learning"]
                        and served in ("planning", "deterministic"))
                    or (not want and served != "edit_applied"))
                if lane_ok:
                    m["lane_agree"] += 1
                if "research" in want and served not in (
                        "read", "planning"):
                    m["omitted_research"] += 1
                if wrote and not mutate:
                    m["unintended_mutation"] += 1
                if mutate and not wrote and served == "edit_applied":
                    m["missing_writes"] += 1
                if "learning" in want:
                    m["teaching_expected"] += 1
                    if rmeta.get("teaching"):
                        m["teaching_attached"] += 1
                if ROW338.startswith(msg[:30]):
                    b = ((task.get("disambiguation") or {}).get(
                        "resolved_bindings") or [])
                    if b:
                        m["bindings_captured"] += 1
                rows_out.append({
                    "session": sname, "msg": msg[:56], "expected": want,
                    "decision": kinds, "served": served, "model": model,
                    "latency_ms": dt_ms, "wrote": wrote,
                    "mutate_expected": mutate, "dec_ok": dec_ok,
                    "lane_ok": lane_ok,
                    "teaching": bool(rmeta.get("teaching"))})
                print(f"{sname[:6]} {msg[:36]!r:40s} dec={kinds} "
                      f"served={served} {dt_ms}ms wrote={wrote} "
                      f"ok={dec_ok and lane_ok}")
            if cid:
                await c.request("DELETE", f"{BASE}/api/canvas/{cid}",
                                headers=headers)
            con = sqlite3.connect(str(DB))
            con.execute("BEGIN")
            con.execute("DELETE FROM chat_messages WHERE "
                        "conversation_id=?", (session,))
            con.execute("DELETE FROM chat_sessions WHERE id=?",
                        (session,))
            con.commit(); con.close()
        con = sqlite3.connect(str(DB))
        con.execute("BEGIN")
        con.execute("DELETE FROM users WHERE email=?", (email,))
        con.commit(); con.close()
    lat = sorted(m["latency_ms"])
    m["latency_p50_ms"] = lat[len(lat)//2] if lat else None
    m["latency_max_ms"] = lat[-1] if lat else None
    art = Path(__file__).parent / "coverage_matrix_results.json"
    art.write_text(json.dumps({"metrics": m, "rows": rows_out},
                              indent=2, default=str))
    print(json.dumps(m))
    print("wrote", art)
    ok = (m["omitted_research"] == 0 and m["unintended_mutation"] == 0
          and m["missing_writes"] == 0
          and m["decision_correct"] == m["turns"]
          and m["teaching_attached"] == m["teaching_expected"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
