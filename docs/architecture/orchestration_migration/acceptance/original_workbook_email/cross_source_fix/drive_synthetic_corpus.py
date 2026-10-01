# -*- coding: utf-8 -*-
"""Synthetic conversations over REAL ingested data, driven through the
LIVE app (2026-09-30 full-activation directive).

Purpose: accumulate real shadow turn-decisions on real turns (the
incremental plan's live-traffic evidence) without waiting for organic
use — conversations are synthetic, the DATA is the real workspace
catalog (Consolidated Price List 2019.xlsx, its 46 indexed sheets,
the real machine codes), and every turn is labeled with its intended
actions by construction.

What it measures, per the directive:
- correct requested actions  (decision kinds == labels)
- served-lane agreement      (deterministic read served research, etc.)
- unintended mutations       (canvas audit delta on non-edit turns)
- omissions                  (research-labeled turn served narration)

Run: cd backend && python3 ../docs/.../drive_synthetic_corpus.py
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

# (message, expected kinds, attach_canvas)
CONVERSATIONS = [
    [  # C1 — the incident arc, condensed
        (ASK8, ["research"], False),
        ("That filename is correct", ["research"], False),
        ("check Chandrakant's email and or description in workbook to "
         "find correct sheet and row from workbook for confirmation",
         ["research"], True),
        ("repeat the search and learn to include tennsmith sheet for "
         "roper whitney searches", ["research", "learning"], True),
        ("make it cleaner", ["presentation"], True),
        ("find this in the tracker", [], True),
    ],
    [  # C2 — odd-wording research that legacy resolution may miss
        (ASK4, ["research"], False),
        ("run the lookup again on that price sheet please",
         ["research"], False),
        ("check what the workbook says about No. 622",
         ["research"], False),
        ("search again", ["research"], False),
    ],
    [  # C3 — edit-shaped with canvas
        (ASK4, ["research"], True),
        ("update the No. 381 price in this draft to $3,254.00",
         ["canvas_edit"], True),
        ("search the file again", ["research"], True),
    ],
    [  # C4 — pure conversation + ambiguity
        ("what can you help me automate?", [], False),
        ("find this in the tracker", [], False),
        (ASK4, ["research"], False),
    ],
]


async def register(c, stamp):
    for _ in range(4):
        reg = (await c.post(f"{BASE}/api/auth/register", json={
            "username": f"sync-{stamp}@example.com",
            "email": f"sync-{stamp}@example.com",
            "password": f"pw-{stamp}",
            "first_name": "Syn", "last_name": "Corpus"})).json()
        if reg.get("access_token"):
            return reg["access_token"], f"sync-{stamp}@example.com"
        await asyncio.sleep(40)
    return None, None


def ro_con():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    return con


def canvas_fingerprint(cid):
    con = ro_con()
    row = con.execute(
        "SELECT content FROM canvases WHERE id=?", (cid,)).fetchone()
    audit = con.execute(
        "SELECT count(*) FROM canvas_audit WHERE canvas_id=? AND "
        "action_type != 'create'", (cid,)).fetchone()[0]
    con.close()
    return (hashlib.sha256((row[0] if row else "").encode())
            .hexdigest()[:12], audit)


async def main():
    out_rows = []
    metrics = {"turns": 0, "decision_correct": 0, "lane_agree": 0,
               "omitted_research": 0, "unintended_edit": 0,
               "unintended_mutation": 0}
    async with httpx.AsyncClient(trust_env=False, timeout=420) as c:
        for ci, convo in enumerate(CONVERSATIONS):
            stamp = f"{uuid.uuid4().hex[:8]}"
            token, email = await register(c, stamp)
            if not token:
                print(f"C{ci+1}: registration rate-limited; skipping")
                continue
            headers = {"Authorization": f"Bearer {token}"}
            me = (await c.get(f"{BASE}/api/auth/me",
                              headers=headers)).json()
            uid = str(me.get("id") or "")
            session = f"sync-{stamp}"
            cid = None
            for msg, want, attach in convo:
                if attach and cid is None:
                    cv = (await c.post(f"{BASE}/api/canvas", headers=headers,
                                       json={"title": f"Synthetic C{ci+1}",
                                             "canvas_type": "document"})).json()
                    cid = cv.get("canvas_id")
                    await c.put(f"{BASE}/api/canvas/{cid}", headers=headers,
                                json={"body": "<p>synthetic draft</p>"},
                                params={"canvas_type": "document"})
                fp_before = canvas_fingerprint(cid) if cid else None
                ctx = {"canvas_id": cid} if (cid and attach) else {}
                r = (await c.post(f"{BASE}/api/chat/message",
                                  headers=headers, json={
                    "message": msg, "session_id": session, "user_id": uid,
                    "request_id": f"req-{uuid.uuid4().hex[:8]}",
                    **({"context": ctx} if ctx else {}),
                })).json()
                await asyncio.sleep(2)
                con = ro_con()
                row = con.execute(
                    """SELECT metadata_json FROM chat_messages
                       WHERE conversation_id=? AND role='assistant'
                       ORDER BY created_at DESC LIMIT 1""",
                    (session,)).fetchone()
                con.close()
                meta = json.loads((row[0] if row else None) or "{}")
                td = meta.get("turn_decision") or {}
                kinds = [a["kind"] for a in
                         td.get("requested_actions") or []]
                meta_ce = (r.get("metadata") or {}).get(
                    "canvas_edit") or {}
                wr = (r.get("metadata") or {}).get("workbook_result")
                model = r.get("model")
                if model == "deterministic" and (wr or meta.get(
                        "pending_file_result")):
                    served = "read"
                elif model == "deterministic":
                    served = "deterministic"
                else:
                    served = "planning"
                if meta_ce.get("updated"):
                    served = "edit_applied"
                metrics["turns"] += 1
                dec_ok = (kinds == want) or (
                    not want and "conversation" in kinds)
                if dec_ok:
                    metrics["decision_correct"] += 1
                lane_ok = (
                    ("research" in want and served == "read")
                    or (want == ["presentation"]
                        and served in ("deterministic", "read"))
                    or (want == ["canvas_edit"] and served in (
                        "edit_applied", "planning", "deterministic"))
                    or (not want and served != "edit_applied"))
                if lane_ok:
                    metrics["lane_agree"] += 1
                if "research" in want and served not in ("read",):
                    metrics["omitted_research"] += 1
                if "canvas_edit" not in want and (
                        meta_ce.get("updated") or served == "edit_applied"):
                    metrics["unintended_edit"] += 1
                if cid and fp_before:
                    fp_after = canvas_fingerprint(cid)
                    if (fp_before[0] != fp_after[0]
                            and "canvas_edit" not in want):
                        metrics["unintended_mutation"] += 1
                out_rows.append({
                    "conv": ci + 1, "msg": msg[:60], "expected": want,
                    "decision": kinds, "served": served,
                    "model": model, "dec_ok": dec_ok, "lane_ok": lane_ok})
                print(f"C{ci+1} {msg[:38]!r:42s} dec={kinds} "
                      f"served={served} ok={dec_ok and lane_ok}")
            # cleanup
            if cid:
                await c.request("DELETE", f"{BASE}/api/canvas/{cid}",
                                headers=headers)
            con = sqlite3.connect(str(DB))
            con.execute("BEGIN")
            con.execute("DELETE FROM chat_messages WHERE conversation_id=?",
                        (session,))
            con.execute("DELETE FROM chat_sessions WHERE id=?", (session,))
            con.execute("DELETE FROM users WHERE email=?", (email,))
            con.commit()
            con.close()
    art = Path(__file__).parent / "synthetic_corpus_live_results.json"
    art.write_text(json.dumps(
        {"metrics": metrics, "rows": out_rows}, indent=2, default=str))
    print(json.dumps(metrics))
    print("wrote", art)
    ok = (metrics["omitted_research"] == 0
          and metrics["unintended_edit"] == 0
          and metrics["unintended_mutation"] == 0
          and metrics["decision_correct"] == metrics["turns"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
