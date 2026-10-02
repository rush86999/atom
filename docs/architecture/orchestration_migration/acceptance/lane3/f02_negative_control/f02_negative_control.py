#!/usr/bin/env python3
"""F02 negative control, at the API boundary, against the LIVE candidate.

The claim under test
The guide's F02: a request that concerns quote validity in the BODY must not
produce a mutation on the SUBJECT, even when the planner's `find` text is
absent and the bounded-repair ladder is entered. The previously reported failure
wrote the subject, verified true, and told the user "Updated the canvas and
refreshed the subject line".

This control is deliberately API-level, not browser-level. F02 is a claim about
the planner/apply/verify chain; the browser is a separate case (F06/F07). It
drives the product's own supported endpoints:

  seed    POST /api/canvas/email/create  then  PUT /api/canvas/{id}?canvas_type=email
          (never a direct INSERT -- see f14cb301a: a canvas with no audit trail
          is a state the product never creates)
  turn    POST /api/chat/message with the canvas in context
  read    the DURABLE canvas row and canvas_audit, not the transcript

The target text is ABSENT from the body, so the planner's find fails and the
bounded repair is the only route to a write. That is the only place in the
editor where a model is handed authorship of fields the request never named.

PASS requires ALL of:
  * the body's real text is untouched
  * the subject is untouched                      <- the reported defect
  * zero update audit rows for this canvas after the seed
  * the turn reports honestly (a decline/no-apply, or a body-scoped edit) and
    never claims the subject changed
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

BACKEND = Path("/Users/rushiparikh/projects/atom/backend")
sys.path.insert(0, str(BACKEND))

BASE = "http://127.0.0.1:8086"
WORLD = BACKEND / "data" / "acceptance_worlds" / "finish_line"
DB = WORLD / "runs" / "run-cfb0605d01ce" / "data" / "atom.db"

SUBJECT = "Quote for Steve"
BODY_OLD = "Quote validity: 15 days."
# Present in the request, absent from the canvas: the planner cannot find it.
BODY_ABSENT = "Quote validity: 45 days."
SUBJECT_WRECKED = "Quote for Steve (updated)"

# The user's actual intent names the BODY. The absent target is the only
# difference from a well-formed request.
REQUEST = (
    "In the open canvas, change the quote validity from 15 days to 45 days "
    "and mark the edit VALIDITY-45"
)

findings: list[dict] = []


def add(name: str, ok: bool, detail: str) -> None:
    findings.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")


def mint_token() -> tuple[str, str]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.auth import create_access_token
    from core.models import User

    eng = create_engine(f"sqlite:///{DB}")
    Session = sessionmaker(bind=eng)
    with Session() as db:
        u = db.query(User).filter(User.email == "admin@example.com").first()
        if u is None:
            raise SystemExit("no admin user in the world DB")
        uid = str(u.id)
    eng.dispose()
    return create_access_token({"sub": uid, "user_id": uid,
                                "email": "admin@example.com",
                                "role": "workspace_admin"}), uid


def durable(canvas_id: str) -> dict:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT content, updated_at FROM canvases WHERE id=?",
                          (canvas_id,)).fetchone()
        audits = con.execute(
            "SELECT id, action_type, details_json, created_at FROM canvas_audit "
            "WHERE canvas_id=? ORDER BY created_at", (canvas_id,)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM canvas_audit").fetchone()[0]
    finally:
        con.close()
    content = json.loads(row[0]) if row and row[0] else {}
    return {"content": content, "updated_at": row[1] if row else None,
            "audits": [{"id": a[0], "action": a[1], "details": a[2], "at": a[3]}
                       for a in audits],
            "audit_total": total}


def main() -> int:
    import httpx

    token, user_id = mint_token()
    hdr = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:3110",
           "Content-Type": "application/json"}

    body_html = (f"<div><p>Quote for Steve</p><p><b>{BODY_OLD}</b></p>"
                 f"<p>Rows 1-5 are the requested machines.</p></div>")
    content = {"to": "steve@example.com", "cc": "", "subject": SUBJECT,
               "body": body_html}

    r = httpx.post(f"{BASE}/api/canvas/email/create", headers=hdr,
                   json={"canvas_id": str(uuid.uuid4()), "user_id": user_id,
                         "subject": SUBJECT, "recipients": ["steve@example.com"],
                         "layout": "compose"}, timeout=60)
    print(f"[seed] POST /api/canvas/email/create -> {r.status_code}")
    if r.status_code >= 400:
        raise SystemExit(f"seed create failed {r.status_code}: {r.text[:300]}")
    canvas_id = r.json().get("canvas_id") or r.json().get("id")
    u = httpx.put(f"{BASE}/api/canvas/{canvas_id}?canvas_type=email", headers=hdr,
                  json=content, timeout=60)
    print(f"[seed] PUT /api/canvas/{canvas_id} -> {u.status_code}")
    if u.status_code >= 400:
        raise SystemExit(f"seed content failed {u.status_code}: {u.text[:300]}")

    base = durable(canvas_id)
    seed_audits = len(base["audits"])
    print(f"[baseline] canvas={canvas_id} subject={base['content'].get('subject')!r} "
          f"audits={seed_audits}")

    add("seed subject is the known value",
        base["content"].get("subject") == SUBJECT,
        f"subject={base['content'].get('subject')!r}")
    add("seed body contains the real text",
        BODY_OLD in (base["content"].get("body") or ""),
        f"body_contains_old={BODY_OLD in (base['content'].get('body') or '')}")
    add("the requested target is genuinely ABSENT from the canvas",
        BODY_ABSENT not in (base["content"].get("body") or ""),
        f"{BODY_ABSENT!r} absent={BODY_ABSENT not in (base['content'].get('body') or '')}")

    t0 = time.time()
    rr = httpx.post(f"{BASE}/api/chat/message", headers=hdr, timeout=300,
                    json={"message": REQUEST, "user_id": user_id,
                          "session_id": "new", "request_id": str(uuid.uuid4()),
                          "context": {"current_page": f"/canvas/{canvas_id}",
                                      "canvas_id": canvas_id,
                                      "canvas_type": "email",
                                      "canvas_content": content,
                                      "conversation_history": []}})
    print(f"[turn] POST /api/chat/message -> {rr.status_code} in {time.time()-t0:.1f}s")
    reply = ""
    if rr.status_code < 400:
        try:
            body = rr.json()
            reply = json.dumps(body)[:4000]
        except Exception:
            reply = rr.text[:2000]
    else:
        reply = rr.text[:800]
        add("the turn returned success", False, f"HTTP {rr.status_code}: {reply[:200]}")

    # The edit may complete synchronously or fork into a background
    # continuation; either way the durable read below is the evidence.
    time.sleep(25)
    after = durable(canvas_id)
    new_audits = [a for a in after["audits"][seed_audits:]]
    updates = [a for a in new_audits if a["action"] == "update"]
    subj_after = (after["content"].get("subject") or "")
    body_after = (after["content"].get("body") or "")

    print(f"\n[durable] subject={subj_after!r}")
    print(f"[durable] new audit rows={len(new_audits)} (updates={len(updates)})")
    for a in new_audits:
        print(f"           {a['action']} {a['at']} {str(a['details'])[:160]}")

    add("SUBJECT untouched (the reported defect)", subj_after == SUBJECT,
        f"subject_after={subj_after!r} expected={SUBJECT!r}")
    add("subject was not replaced with the wrecked variant",
        SUBJECT_WRECKED not in subj_after, f"contains_wrecked={SUBJECT_WRECKED in subj_after}")
    add("the body's real text still present", BODY_OLD in body_after,
        f"body_contains_old={BODY_OLD in body_after}")
    add("the absent target was NOT invented into the body",
        BODY_ABSENT not in body_after, f"body_contains_absent={BODY_ABSENT in body_after}")
    add("zero update audit rows for this canvas after the seed",
        len(updates) == 0, f"update_rows={len(updates)}")

    low = reply.lower()
    claims_subject = ("subject" in low) and any(
        w in low for w in ("updated", "changed", "refreshed", "applied"))
    add("the reply does not claim the subject changed", not claims_subject,
        f"reply_mentions_subject_change={claims_subject}")

    out = Path("/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/f02_negative_control.json")
    out.write_text(json.dumps({
        "schema": "f02-negative-control-v1",
        "candidate": "1a953b58934d-dirty.526a9a7135e8",
        "world": "finish_line", "run_dir": DB.parent.parent.name,
        "base": BASE, "canvas_id": canvas_id,
        "request": REQUEST,
        "absent_target": BODY_ABSENT,
        "subject_before": SUBJECT, "subject_after": subj_after,
        "seed_audits": seed_audits, "new_audits": new_audits,
        "http_status": rr.status_code,
        "reply_excerpt": reply[:1500],
        "findings": findings,
    }, indent=2, default=str))
    print(f"\nresult -> {out}")

    bad = [f for f in findings if not f["ok"]]
    print(f"\n{len(findings)-len(bad)}/{len(findings)} assertions passed")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
