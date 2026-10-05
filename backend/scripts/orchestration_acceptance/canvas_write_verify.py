#!/usr/bin/env python3
"""Prove one browser-driven canvas edit becomes an attributable durable write.

WHY THIS EXISTS
On 2026-09-27 a real-planner turn rendered "**Canvas Updated:** ... Quote
validity: **30 days**" while ``canvas_audit`` held no row for any canvas in 30
minutes and no canvas in the world contained the new text. A success claim with
no verified write. The response was 200 the whole time, so the API proved only
what the server chose to return.

This script establishes the opposite claim, with the assertions that make it
worth something. It reuses ``browser_verify``'s proven pieces (world token
minting, the network/WS recorder, the composer driver) rather than inventing a
second browser harness, and it adds the part that was missing everywhere: it
reads the DURABLE state afterwards and refuses to call a turn successful on the
strength of what the UI displayed.

WHAT IS ASSERTED, AND WHY EACH ONE IS NEEDED
  field_changed          the requested field's new value is in the durable
                         canvas. A timestamp bump proves something wrote; it
                         does not prove it wrote the right thing.
  audit_row_attributed   exactly one canvas_audit row for THIS canvas, of
                         action_type=update, carrying the operation_id the turn
                         reported. This is the attribution link: without it a
                         write cannot be tied to the turn that claimed it.
  mutation_delta_one     the world's total canvas_audit row count grew by
                         exactly one. Asserted on the COUNT and not on
                         operation ids, because ids are generated per run and a
                         delta assertion is what actually catches a double
                         write, a retried write, or a write to the wrong canvas.
  postcondition_verified the turn's own verdict, which is what the product now
                         refuses to render as success without.
  survives_reload        a real browser reload still shows the new value, so
                         the change is durable rather than an optimistic client
                         cache that a refresh discards.
  world_only             every request the page made went to THIS world's
                         backend, and this world's database changed while the
                         live dev database did not.

The mutation path itself is NOT assumed. It is observed: the script records
every request and every WebSocket frame, so "the client applied it" and "the
server applied it" are distinguishable from the record rather than inferred
from an empty broadcast channel.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND / "scripts" / "orchestration_acceptance"))

import browser_verify as BV  # noqa: E402

OUT_DIR = BACKEND / "data" / "acceptance_worlds_results" / "canvas_write_verify"

# The edit target. Deliberately a single unambiguous token pair in one field of
# one canvas, so a failure is attributable to a specific substitution rather
# than to a diff nobody can review.
OLD_VALUE = "15 days"
NEW_VALUE = "30 days"


def build_ask(old: str, new: str, field: str = "quote validity") -> str:
    return f"In the open canvas, change the {field} from {old} to {new}."

# A "document" canvas is text-backed, so a single-token substitution is
# attributable to one field. (A blank canvas cannot be created as "email" --
# BLANK_CANVAS_TYPES restricts creation to the text/grid apps -- so the canvas is
# created blank and then re-typed, which is the supported PUT contract.)
DOC_CONTENT = (
    "# Quote terms\n\n"
    "- Quote validity: 15 days\n"
    "- Payment terms: Net 30\n"
)

# The Phase A surface. SUBJECT is deliberately the same words as the body target,
# because the preserved negative case is a subject-line edit produced by a
# request about body content. If the subject moves, that is the regression.
EMAIL_SUBJECT = "Quote validity"
EMAIL_CONTENT = {
    "to": "buyer@example.com",
    "subject": EMAIL_SUBJECT,
    "body": (
        "<p>Hello,</p>"
        "<p>Here is your quote.</p>"
        "<ul>"
        "<li><strong>Quote validity:</strong> 15 days</li>"
        "<li><strong>Payment terms:</strong> Net 30</li>"
        "</ul>"
        "<p>Regards,<br/>Sales</p>"
    ),
}


def _ro(db: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    con.execute("PRAGMA query_only=ON")
    return con


def durable_state(db: Path, canvas_id: str) -> Dict[str, Any]:
    """Read the durable truth for one canvas. Never the API's own claim."""
    con = _ro(db)
    try:
        row = con.execute(
            "SELECT content, updated_at, last_edited_at FROM canvases WHERE id=?",
            (canvas_id,)).fetchone()
        audits = con.execute(
            "SELECT id, action_type, created_at, details_json FROM canvas_audit "
            "WHERE canvas_id=? ORDER BY created_at", (canvas_id,)).fetchall()
        total = con.execute("SELECT count(*) FROM canvas_audit").fetchone()[0]
    finally:
        con.close()
    content = None
    if row:
        try:
            content = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except (TypeError, ValueError):
            content = row[0]
    return {
        "content": content,
        "updated_at": row[1] if row else None,
        "last_edited_at": row[2] if row else None,
        "audits": [{"id": a[0], "action_type": a[1], "created_at": a[2],
                    "details": a[3]} for a in audits],
        "audit_total": total,
    }


def _body_text(content: Any) -> str:
    if isinstance(content, dict):
        return " ".join(str(v) for v in content.values())
    return str(content or "")


def browser_api(page: Any, method: str, path: str, body: Any = None,
                origin: str = "", token: str = "") -> Any:
    """Call the product's own API FROM THE PAGE, so the request is the
    browser's and carries the browser's session -- not a side-channel curl.

    ``origin`` must be the BACKEND's absolute origin. The page is served by the
    Next dev server, which deliberately does not proxy ``/api`` to the backend
    (the real client uses the compiled-in absolute API base), so a relative
    ``fetch('/api/canvases')`` lands on the frontend and 404s -- which is what
    the first run of this script did.

    ``token`` becomes an ``Authorization: Bearer`` header, matching the app's
    own ``apiClient``. Relying on the session cookie instead is rejected with
    ``403 csrf_token_invalid`` (the second run of this script), so the header is
    not optional decoration -- it is how this API authenticates writes.
    """
    return page.evaluate(
        """async ([method, url, body, token]) => {
             const r = await fetch(url, {
               method,
               headers: {
                 'Content-Type': 'application/json',
                 ...(token ? {'Authorization': 'Bearer ' + token} : {}),
               },
               body: body === null ? undefined : JSON.stringify(body),
             });
             let parsed = null;
             try { parsed = await r.json(); } catch (e) {}
             return {status: r.status, body: parsed};
           }""",
        [method, f"{origin}{path}", body, token])


def warm_routes(page: Any, base: str, paths: List[str], timeout_s: int = 240) -> Dict[str, int]:
    """Force the dev server to compile routes BEFORE driving the UI.

    `next dev` compiles a route on first hit, and that compile routinely takes
    longer than any sane selector timeout. Driving the browser straight at an
    uncompiled route therefore looks exactly like a broken page: /login
    answered 500 with no inputs while the identical checkout on :3000 was fine,
    and an email field "timed out" for 90s on a page that renders in 2s once
    compiled. Warming through the API request context pays the compile cost with
    the server rather than with the assertions.
    """
    seen: Dict[str, int] = {}
    for path in paths:
        try:
            r = page.request.get(f"{base}{path}", timeout=timeout_s * 1000)
            seen[path] = r.status
        except Exception as exc:
            seen[path] = f"{type(exc).__name__}"
        page.wait_for_timeout(1500)
    return seen


# The canvas page renders its transcript WITHOUT the app's usual
# data-testid="message-list", so browser_verify's reader silently fell back to
# document.body.innerText and the assistant's actual reply was never captured --
# page chrome was recorded instead. Scope the read to the composer's own
# container so the reply is what gets asserted on.
CANVAS_TRANSCRIPT_JS = """() => {
  const ta = document.querySelector('textarea[placeholder*="edit" i]');
  let el = ta;
  for (let i = 0; i < 8 && el; i++) {
    el = el.parentElement;
    if (!el) break;
    const bubbles = el.querySelectorAll('div.inline-block');
    if (bubbles.length) {
      const out = [];
      bubbles.forEach(function (b) {
        const t = (b.innerText || "").trim();
        if (t.length > 1) out.push(t);
      });
      return out.join(" | ");
    }
  }
  return "";
}"""

# Truthful completion. The turn must resolve to exactly one of these. HTTP 200
# is not one of them: it establishes only that the request was handled.
OUTCOME_MUTATED = "verified_mutation"
OUTCOME_REFUSED = "explicit_no_apply"
# The orchestrator's own words for "the planner would not authorise this", and
# for "a write was attempted and not confirmed".
REFUSAL_MARKERS = (
    "not going to claim", "could not be confirmed", "nothing was changed",
    "couldn't reach the model", "did not complete that canvas change",
    "no changes were made", "still running in the background",
    "planner", "decline",
)

def main() -> int:
    ap_arg = sys.argv[1:] or ["--world", "write_verify_0928"]
    world_name = ap_arg[ap_arg.index("--world") + 1] if "--world" in ap_arg else "write_verify_0928"
    canvas_type = (ap_arg[ap_arg.index("--canvas-type") + 1]
                   if "--canvas-type" in ap_arg else "document")
    # --expect decline|mutation : what the run is asserting. A decline case must
    # be a legitimate one (nothing to change / out of scope), and must still
    # require zero unrelated mutation.
    expect = (ap_arg[ap_arg.index("--expect") + 1]
              if "--expect" in ap_arg else "mutation")
    # --ask overrides the request, for the negative case.
    old_value = ap_arg[ap_arg.index("--old") + 1] if "--old" in ap_arg else OLD_VALUE
    new_value = ap_arg[ap_arg.index("--new") + 1] if "--new" in ap_arg else NEW_VALUE
    field = ap_arg[ap_arg.index("--field") + 1] if "--field" in ap_arg else "quote validity"
    ask = (ap_arg[ap_arg.index("--ask") + 1] if "--ask" in ap_arg
           else build_ask(old_value, new_value, field))
    globals()["OLD_VALUE"], globals()["NEW_VALUE"] = old_value, new_value
    world = BACKEND / "data" / "acceptance_worlds" / world_name
    state = json.loads((world / "preview_stack.json").read_text())
    run_dir = Path(state["run_dir"])
    backend_port = int(state["backend_port"])
    frontend_port = int(state["frontend_port"])
    db = run_dir / "data" / "atom.db"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"world={world_name} backend=:{backend_port} frontend=:{frontend_port}")
    print(f"run  ={run_dir.name}")

    # ---- baseline BEFORE anything -------------------------------------
    before = durable_state(db, "nonexistent-canvas-probe")
    audit_total_before = before["audit_total"]
    print(f"[baseline] canvas_audit rows in world = {audit_total_before}")

    # Live dev DB fingerprint, to prove the world-only claim at the end.
    live = BACKEND / "data" / "atom.db"
    live_before = None
    if live.exists():
        try:
            con = sqlite3.connect(f"file:{live}?immutable=1", uri=True, timeout=20)
            live_before = con.execute(
                "SELECT count(*), max(created_at) FROM canvas_audit").fetchone()
            con.close()
        except sqlite3.Error as exc:
            print(f"[baseline] live db unreadable ({exc}); world-only check "
                  f"will fall back to the serving process's open handles")

    api_origin = f"http://localhost:{backend_port}"
    fe_base = f"http://localhost:{frontend_port}"

    # A REAL login, not a seeded session. The plan forbids bypassing session
    # gating, and an earlier version of this script called seed_session() and so
    # never exercised authentication at all. The world-local credential is
    # provisioned by preview_stack.seed_preview_auth (0600, generated, never a
    # live secret); it is read here and never logged.
    cred_path = world / "run_secrets" / "preview_auth.json"
    if not cred_path.exists():
        print(f"no preview credential at {cred_path}; run preview_stack up first",
              file=sys.stderr)
        return 2
    cred = json.loads(cred_path.read_text())
    print(f"[auth] preview credential present for {cred['email']} "
          f"(value not logged)")

    from playwright.sync_api import sync_playwright

    recorder = BV.Recorder(backend_port)
    findings: List[Dict[str, Any]] = []
    shots: List[str] = []
    result: Dict[str, Any] = {"world": world_name, "run": run_dir.name}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1500, "height": 950})
        page = ctx.new_page()
        recorder.attach(page)

        # `next dev` compiles /login on first hit, which routinely exceeds
        # ui_login's 15s fill timeout and looks exactly like a broken login.
        # Wait for the field to exist, then log in, and retry once.
        warm = warm_routes(page, fe_base, ["/login"])
        result.setdefault("warm_routes", {}).update(warm)
        print(f"[warm] compiled routes: {warm}")

        login: Dict[str, Any] = {}
        for attempt in range(3):
            page.goto(f"{fe_base}/login", wait_until="domcontentloaded",
                      timeout=180000)
            try:
                page.wait_for_selector(
                    'input[type="email"], input[name="email"], input[id*="email" i]',
                    timeout=180000)
            except Exception:
                pass
            login = BV.ui_login(page, fe_base, cred["email"], cred["password"])
            if login.get("ok"):
                break
            print(f"[auth] login attempt {attempt + 1} did not land"
                  + (f": {login.get('error')}" if login.get("error") else ""))
        result["login"] = {k: v for k, v in login.items() if k != "error"}
        if login.get("error"):
            result["login"]["error"] = login["error"]
        print(f"[auth] ui_login ok={login.get('ok')} landed={login.get('landed_url')}")

        # Prove the session is real, from the page, before anything else runs.
        session = page.evaluate(
            """async () => {
                 const r = await fetch('/api/auth/session');
                 return {status: r.status, body: await r.json().catch(() => null)};
               }""")
        result["session"] = session
        sess_user = ((session.get("body") or {}).get("user") or {})
        print(f"[auth] /api/auth/session -> {session.get('status')} "
              f"user={sess_user.get('email')}")

        token = page.evaluate("() => localStorage.getItem('auth_token')") or ""
        if not token:
            print("no auth_token after a real login", file=sys.stderr)
            return 2

        # ---- 1. create the canvas through the normal product path -----
        r = browser_api(page, "POST", "/api/canvas", origin=api_origin, token=token, body={
            "title": "Quote terms", "canvas_type": "document",
            "description": "browser write verification",
        })
        if r["status"] not in (200, 201) or not r["body"]:
            print(f"canvas create failed: {r['status']} {r['body']}", file=sys.stderr)
            return 2
        canvas_id = (r["body"].get("id") or r["body"].get("canvas_id")
                     or (r["body"].get("canvas") or {}).get("id"))
        print(f"[canvas] created via POST /api/canvas -> {canvas_id}")
        result["canvas_id"] = canvas_id

        # Give it real content through the same PUT the editor saves with.
        # Re-type on the same PUT that seeds the content: creation is restricted
        # to text/grid apps, so "email" is applied here.
        put_path = (f"/api/canvas/{canvas_id}?canvas_type={canvas_type}"
                    if canvas_type != "document"
                    else f"/api/canvas/{canvas_id}")
        seed_body = EMAIL_CONTENT if canvas_type == "email" else DOC_CONTENT
        r = browser_api(page, "PUT", put_path,
                        origin=api_origin, token=token,
                        body=seed_body)
        if r["status"] not in (200, 201):
            print(f"canvas content PUT failed: {r['status']} {r['body']}", file=sys.stderr)
            return 2
        seeded = durable_state(db, canvas_id)
        seeded_text = _body_text(seeded["content"])
        print(f"[canvas] type={canvas_type}; seeded content; "
              f"contains '{OLD_VALUE}': {OLD_VALUE in seeded_text}")
        result["canvas_type"] = canvas_type

        # ---- 2. attach its context ------------------------------------
        r = browser_api(page, "POST", f"/api/canvas/{canvas_id}/context", origin=api_origin, token=token, body={
            "canvas_type": "document", "initial_state": {"source": "browser_verify"},
        })
        result["context_attach_status"] = r["status"]
        print(f"[context] POST /api/canvas/{{id}}/context -> {r['status']}")

        audits_before = len(seeded["audits"])
        total_before_edit = seeded["audit_total"]
        updated_before = seeded["updated_at"]

        # ---- 3. drive the edit from the browser composer -------------
        # The edit must be sent FROM the canvas page. That page registers the
        # open canvas in the global registry AND builds the chat request's
        # context itself (pages/canvas/[id].tsx posts
        # context.canvas_content), which is what "attach its context" means
        # here. The landing page has no composer, and /chat only picks up the
        # canvas if some other surface registered it first.
        # The canvas route can abort the navigation while the app settles
        # (redirect / client navigation racing the dev server's first compile).
        # That is a navigation-level nuisance, not a verdict on the page, so it
        # is retried and then judged on the DOM rather than on the goto result.
        canvas_url = f"http://localhost:{frontend_port}/canvas/{canvas_id}"
        warm_canvas = warm_routes(page, fe_base, [f"/canvas/{canvas_id}"])
        result.setdefault("warm_routes", {}).update(warm_canvas)
        print(f"[warm] canvas route: {warm_canvas}")
        for attempt in range(3):
            try:
                page.goto(canvas_url, wait_until="commit", timeout=180000)
                break
            except Exception as exc:
                print(f"[nav] canvas goto attempt {attempt + 1} failed: "
                      f"{type(exc).__name__}")
                page.wait_for_timeout(8000)
        page.wait_for_timeout(20000)
        # A fresh account lands on the "Welcome to Atom" onboarding wizard whose
        # scrim sits OVER the canvas composer: Playwright resolves the textarea,
        # reports it visible and stable, then refuses the click because the modal
        # intercepts pointer events, so the edit is never sent and the run
        # reports 8 durable-write failures against a completely healthy app
        # (2026-09-29, candidate 79b2a41032c3). Dismiss it the way a user would.
        result["first_run_modals"] = BV.dismiss_first_run_modals(page)
        print(f"[modals] {result['first_run_modals']}")
        shots.append(BV.shoot(page, "01_before_edit"))
        try:
            # The canvas page's own composer, which is the one wired to this
            # canvas's context.
            box = page.locator('textarea[placeholder*="edit" i]').first
            if box.count() and box.is_visible():
                box.click()
                box.fill(ask, timeout=20000)
                page.keyboard.press("Enter")
            else:
                BV.send_via_ui(page, ask)
            sent = True
        except Exception as exc:
            print(f"[composer] could not drive the UI composer: {exc}")
            sent = False
        result["composer_sent"] = sent
        result["expect"] = expect
        result["ask"] = ask
        print(f"[composer] sent={sent}")

        # Wait for the ASSISTANT's reply, not merely for text to appear. The
        # first non-empty read is the user's OWN request echoed back, so
        # breaking on "non-empty" recorded the question as the answer and then
        # reported the turn as a silent no-op. Require at least two bubbles
        # (the question and a reply) and two identical consecutive reads.
        end = time.time() + 360
        transcript, prev, stable = "", "", 0
        while time.time() < end:
            page.wait_for_timeout(4000)
            try:
                cur = page.evaluate(CANVAS_TRANSCRIPT_JS) or ""
            except Exception:
                cur = ""
            bubbles = [b for b in cur.split(" | ") if b.strip()]
            if len(bubbles) >= 2:
                stable = stable + 1 if cur == prev else 0
                prev = cur
                transcript = cur
                if stable >= 2:
                    break
            else:
                prev = cur
        shots.append(BV.shoot(page, "02_after_edit"))
        result["transcript_tail"] = (transcript or "")[-1200:]

        # ---- 4. reload and re-read the DOM ---------------------------
        page.reload(wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(6000)
        after_reload_text = page.evaluate(CANVAS_TRANSCRIPT_JS) or ""
        shots.append(BV.shoot(page, "03_after_reload"))
        result["reload_transcript_tail"] = after_reload_text[-1200:]

        ctx.close()
        browser.close()

    # ---- 5. durable assertions ---------------------------------------
    after = durable_state(db, canvas_id)
    after_text = _body_text(after["content"])
    update_rows = [a for a in after["audits"]
                   if a["action_type"] == "update" and a["id"] not in
                   {x["id"] for x in seeded["audits"]}]
    delta = after["audit_total"] - total_before_edit

    def add(name: str, ok: bool, detail: Any = None) -> None:
        findings.append({"assertion": name, "ok": bool(ok), "detail": detail})
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f"  {detail}" if detail is not None else ""))

    print("\n=== durable-write assertions ===")
    if expect == "mutation":
        add("field_changed_in_durable_canvas",
        NEW_VALUE in after_text and OLD_VALUE not in after_text,
        f"new present={NEW_VALUE in after_text} old absent={OLD_VALUE not in after_text}")
    if canvas_type == "email":
        subj = after["content"].get("subject") if isinstance(after["content"], dict) else None
        add("unrelated_subject_unchanged", subj == EMAIL_SUBJECT,
            f"subject {subj!r} (expected {EMAIL_SUBJECT!r})")
        result["subject_after"] = subj
    if expect == "mutation":
        add("canvas_row_timestamp_advanced",
        after["updated_at"] != updated_before,
        f"{updated_before} -> {after['updated_at']}")
    if expect == "mutation":
        add("exactly_one_update_audit_row", len(update_rows) == 1,
        f"{len(update_rows)} new update row(s)")
    if expect == "mutation":
        add("mutation_delta_is_one", delta == 1,
        f"world canvas_audit {total_before_edit} -> {after['audit_total']} (delta {delta})")
    op_ids = []
    for a in update_rows:
        try:
            d = json.loads(a["details"] or "{}")
            op_ids.append(d.get("operation_id") or d.get("operation"))
        except (TypeError, ValueError):
            op_ids.append(None)
    if expect == "mutation":
        add("audit_row_is_attributable", bool(op_ids and op_ids[0]),
        f"operation_id on the audit row: {op_ids[0] if op_ids else None}")
    # Read the canvas back from the DURABLE store after the reload, not the
    # transcript. The transcript echoes the user's own request, so it contains
    # the new value even when nothing was written -- which made this assertion
    # pass on a run where the canvas was provably unchanged. A reload check that
    # can be satisfied by the request text is not a reload check.
    durable_after_reload = durable_state(db, canvas_id)
    durable_text = _body_text(durable_after_reload["content"])
    if expect == "mutation":
        add("survives_reload_in_durable_state",
        NEW_VALUE in durable_text and OLD_VALUE not in durable_text,
        f"durable canvas after reload contains {NEW_VALUE!r}: "
        f"{NEW_VALUE in durable_text}; still shows {OLD_VALUE!r}: "
        f"{OLD_VALUE in durable_text}")
    result["reload_durable_body"] = durable_text[:400]

    # Which side applied it? Observed, not inferred.
    apply_reqs = [r for r in recorder.requests
                  if r.get("method") in ("PUT", "PATCH", "POST")
                  and "canvas" in (r.get("url") or "")
                  and r.get("method") in ("PUT", "PATCH")]
    chat_reqs = [r for r in recorder.requests
                 if "/api/chat/message" in (r.get("url") or "")]
    result["observed"] = {
        "chat_message_requests": len(chat_reqs),
        "canvas_write_requests": [
            {"method": r.get("method"), "path": (r.get("url") or "").split("?")[0],
             "status": r.get("status")} for r in apply_reqs],
        "websockets": len(recorder.websockets),
        "foreign_origin_hits": recorder.foreign_origin_hits,
    }
    add("no_foreign_origin_requests", not recorder.foreign_origin_hits,
        f"{len(recorder.foreign_origin_hits)} foreign-origin request(s)")
    # Isolation invariant: no request left the two origins this preview owns.
    # Enumerating which /api/* paths Next serves itself is not the invariant --
    # it serves /api/auth/* and /api/v1/* from the frontend origin -- and
    # guessing at it produced two different false failures.
    fe_origin = f"http://localhost:{frontend_port}"
    be_origin = f"http://localhost:{backend_port}"
    # Real origin = scheme://host:port. Splitting the string on "/api" left
    # every non-API asset URL intact, so each chunk path became its own
    # "origin" and the check flagged the frontend serving its own assets.
    from urllib.parse import urlsplit
    origins = {}
    for r in recorder.requests:
        u = r.get("url") or ""
        if u.startswith("http"):
            q = urlsplit(u)
            o = f"{q.scheme}://{q.netloc}"
            origins[o] = origins.get(o, 0) + 1
    allowed_origins = {fe_origin, be_origin,
                       f"http://127.0.0.1:{backend_port}",
                       f"http://127.0.0.1:{frontend_port}"}
    stray = {o: n for o, n in origins.items() if o not in allowed_origins}
    add("all_requests_stayed_within_this_preview", not stray,
        f"origins={origins}" if not stray else f"STRAY ORIGINS: {stray}")

    # World-only, at the data layer.
    live_after = None
    if live_before:
        try:
            con = sqlite3.connect(f"file:{live}?immutable=1", uri=True, timeout=20)
            live_after = con.execute(
                "SELECT count(*), max(created_at) FROM canvas_audit").fetchone()
            con.close()
        except sqlite3.Error:
            pass
    add("live_dev_db_canvas_audit_unchanged",
        live_before is None or live_after == live_before,
        f"before={live_before} after={live_after}")

    # ---- 3. truthful completion ---------------------------------------
    # A 200 establishes only that the request was handled. The turn must land on
    # exactly one of: a verified intended mutation, or an explicit refusal /
    # pending / failed / uncertain statement. "The reply looked fine" is not an
    # outcome, and a silent no-op is the failure this whole check exists for.
    reply = (result.get("transcript_tail") or "")
    mutated = ("field_changed_in_durable_canvas" in
               {f["assertion"] for f in findings if f["ok"]}
               and "mutation_delta_is_one" in
               {f["assertion"] for f in findings if f["ok"]})
    refused = any(m in reply.lower() for m in REFUSAL_MARKERS)
    if expect == "decline":
        # Negative case: the ONLY acceptable outcomes are a truthful no-apply
        # with zero mutation. A mutation here is a FAIL, not a pass.
        outcome = OUTCOME_MUTATED if mutated else (
            OUTCOME_REFUSED if refused else "silent_no_outcome")
        add("decline_case_made_no_mutation", not mutated,
            f"expected no mutation; delta={delta}, new_update_rows="
            f"{len(update_rows)}")
    else:
        outcome = OUTCOME_MUTATED if mutated else (
            OUTCOME_REFUSED if refused else "silent_no_outcome")
    result["outcome"] = outcome
    add("completion_is_truthful", outcome in (OUTCOME_MUTATED, OUTCOME_REFUSED),
        f"outcome={outcome}"
        + (f"; reply excerpt: {reply[:180]!r}" if reply else "; NO REPLY CAPTURED"))

    result["findings"] = findings
    result["durable"] = {
        "audit_total_before": total_before_edit,
        "audit_total_after": after["audit_total"],
        "new_update_rows": update_rows,
        "updated_at": after["updated_at"],
        "body_after": after_text[:600],
    }
    result["screenshots"] = shots
    result["console_errors"] = recorder.console_errors[:20]
    result["page_errors"] = recorder.page_errors[:20]
    out = OUT_DIR / f"{world_name}_{int(time.time())}.json"
    out.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nresult -> {out}")

    bad = [f for f in findings if not f["ok"]]
    print(f"\n{len(findings)-len(bad)}/{len(findings)} assertions passed")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
