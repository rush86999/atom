#!/usr/bin/env python3
"""Canvas EDITING through a real browser, against the PRODUCTION planner.

THE GAP THIS CLOSES (and only part of it)
`WRITE_PATH_HANDOFF.md`'s "NOT supported" list has two separate items, and they
are two separate holes:

  1. Canvas editing has never been exercised through a browser at all. Every
     green mutation in this lane was driven at the API boundary.
  2. Editing with the production planner is measured to DECLINE
     (`wants_edit=False`).

This driver runs BOTH halves against one world, and reports them separately
because they can have different answers.

WHAT IS INJECTED: NOTHING.
The production planner runs on the real request. There is no provider shim, no
monkeypatched planner, no accepting plan handed to the turn. The only thing the
driver writes before the turn is the probe canvas, and it writes it through the
product's own supported endpoints (POST /api/canvas/email/create, then
PUT /api/canvas/{id}) so the fixture carries the same evidence trail a real
user's canvas does -- the reason `f14cb301a` moved off the direct INSERT.
`ATOM_ASYNC_EDIT_PLAN_MODEL` MAY be set by the operator: model selection is a
routing decision and carries no authority over whether a canvas may change.
The driver's launch descriptor and report both record whether it was pinned.

THE STEPS, AND WHAT EACH ONE MUST PROVE
  V0  login through the real form      -> the auth path works at all, and this
                                          browser talks to THIS world only
  V1  the canvas is created over HTTP  -> the fixture is one the product made;
                                          the two calls are recorded verbatim
  V2  the REAL canvas page renders it  -> the page a user opens really shows
                                          this canvas's title, type and body
  V3  the composer's OUTGOING request  -> captured off the browser's own network
                                          traffic (`page.on("request")`), never
                                          re-sent and never reconstructed. The
                                          bug class is a composer that posts to a
                                          generic chat session with the canvas
                                          dropped, or with the wrong canvas, so
                                          the assertions are on the BYTES:
                                          canvas_id, canvas_type, the canvas
                                          content, current_page, session_id.
  V4  the edit runs on the real planner-> the reply, the machine-readable
                                          outcome, the durable mutation and the
                                          audit trail, all read back from THIS
                                          run
  V5  what the user is shown            -> the assistant bubble's text out of the
                                          DOM, judged against the durable store
                                          rather than against the reply's own
                                          self-assessment
  V6  a browser RELOAD                  -> the same turn, the same outcome,
                                          recovered from durable state alone

A DECLINE IS A RESULT, NOT A FAILURE TO HIDE
If the production planner declines, the canvas must be untouched, the visible
answer must say so, and the report carries the planner's own log line -- the
`plan_contract_violation` shape and, where it applies, the repair exchange
committed in 6e34725c7. There is no fallback accepting plan anywhere in this
file, by construction.

NOT APPLICABLE IS PRINTED, NEVER FOLDED IN
Checks that only mean something when a mutation landed (the exactly-one
attribution, the current-revision check) are published as NOT APPLICABLE with
the check that makes them so, and are excluded from the ratio -- the same
discipline as `publish_case.py`.

    browser_canvas_edit.py --world d5_browser_edit --out <dir> [--headed]
                            [--edit-request "..."] [--label unpinned]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
# HERE is .../orchestration_migration/acceptance/lane3, so the repo root is
# HERE.parents[4] (lane3 -> acceptance -> orchestration_migration ->
# architecture -> docs -> REPO).
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
WORLDS = BACKEND / "data" / "acceptance_worlds"
sys.path.insert(0, str(BACKEND))

LOGIN_EMAIL = "admin@example.com"
#: The marker makes this canvas findable in the audit trail even after several
#: turns have appended rows to it.
MARKER = "d5-browser-canvas-edit"

#: The canvas body the probe seeds, and the single change this case asks for.
#: One verbatim find->replace, so "did the canvas change" is decidable from the
#: durable bytes alone with no interpretation.
BODY_OLD = "Quote validity: 15 days."
BODY_NEW = "Quote validity: 30 days."
DEFAULT_EDIT_REQUEST = (
    "In the open canvas, change the quote validity from 15 days to 30 days "
    "and mark the edit VALIDITY-30"
)

#: Phrases that mean the visible answer is telling the user a change WAS made.
#: Both lists are printed with the run so the classification is auditable: a
#: keyword list is a judgement, and a judgement nobody can check is a claim.
MUTATION_CLAIM_PHRASES = (
    "updated", "i changed", "i've changed", "changed the", "changed it",
    "applied", "edited", "revised", "rewrote", "is now", "now shows",
)
NO_CHANGE_PHRASES = (
    "nothing was changed", "nothing changed", "was not changed", "not changed",
    "i did not", "i didn't", "couldn't", "could not", "was not applied",
    "no change", "already reflects", "not going to claim", "did not complete",
    "could not be confirmed",
)


# --------------------------------------------------------------------- helpers
def set_world_password(db_path: str, password: str) -> None:
    """Make the world's admin loggable through the real form.

    Scoped exactly like the existing browser drivers: refuse any path that is
    not inside an acceptance world, and never leave TESTING set
    (core/database.py treats TESTING=1 as "force the scratch DB", which would
    silently write to backend/test_integration.db instead of the world).

    This is a credential set-up step, not part of what is measured. The
    password is never printed, logged, or written to the report.
    """
    db = str(Path(db_path).resolve())
    if "acceptance_worlds" not in db:
        raise SystemExit(f"refusing to write outside an acceptance world: {db}")
    os.environ.pop("TESTING", None)
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    os.environ["ATOM_DATA_DIR"] = str(Path(db).parent)
    os.environ["ENVIRONMENT"] = "development"
    from core.auth import get_password_hash
    from core.database import get_db_session
    from core.models import User
    with get_db_session() as session:
        user = session.query(User).filter(User.email == LOGIN_EMAIL).first()
        if user is None:
            raise SystemExit(f"{LOGIN_EMAIL} not present in this world")
        user.hashed_password = get_password_hash(password)
        session.commit()
    print(f"[world] admin password set in {Path(db).parent.parent.name} "
          f"(value never printed)")


def frontend_source_digest(farm: Path) -> Dict[str, Any]:
    """A content digest of the frontend sources this run was actually served.

    The backend can be frozen (a world's immutable code export), but the farm is
    a symlink tree over the LIVE working tree, so "which frontend was this?" is
    not answered by a commit. It is answered by hashing what the browser ran --
    and that hash has to be in the report, because a frontend edited mid-test
    otherwise makes the result unattributable.

    The tracked set is this case's own decision points: the canvas page (which
    builds the composer request), the canvas panel (what the user is shown),
    the canvas sync bridge, and the resolved config.
    """
    import hashlib
    tracked = [
        "pages/canvas/[id].tsx",
        "components/canvas/CanvasPanel.tsx",
        "components/canvas/ChatMarkdown.tsx",
        "lib/canvasSync.ts",
        "lib/api-client.ts",
        "pages/login.tsx",
        "next.config.js",
    ]
    per_file: Dict[str, Optional[str]] = {}
    h = hashlib.sha256()
    for rel in tracked:
        try:
            real = (farm / rel).resolve()
            digest = hashlib.sha256(real.read_bytes()).hexdigest()
        except OSError:
            digest = ""
        per_file[rel] = digest or None
        h.update(rel.encode())
        h.update(digest.encode())
    return {"farm": str(farm), "tree_sha256": h.hexdigest(), "files": per_file,
            "note": "symlink farm over the live working tree; the backend is "
                    "frozen by the world's code export but the frontend is not, "
                    "so this digest is what makes the browser result attributable"}


def _world_db(db: str) -> sqlite3.Connection:
    """A connection to a WORLD database, with the same refusal as everything else."""
    resolved = str(Path(db).resolve())
    if "acceptance_worlds" not in resolved:
        raise SystemExit(f"refusing to read outside an acceptance world: {resolved}")
    con = sqlite3.connect(resolved, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def read_canvas_row(db: str, canvas_id: str) -> Dict[str, Any]:
    con = _world_db(db)
    try:
        # The column set is read from the schema rather than assumed: a frozen
        # fixture and a live product migration can differ, and a driver that
        # hardcodes a column reports a crash where the honest answer is "read
        # what is there".
        cols = {r[1] for r in con.execute("PRAGMA table_info(canvases)")}
        wanted = [c for c in ("id", "name", "title", "canvas_type", "content",
                              "status", "created_by", "last_edited_by",
                              "last_edited_at", "updated_at") if c in cols]
        row = con.execute(
            f"SELECT {', '.join(wanted)} FROM canvases WHERE id=?",
            (canvas_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        return {"found": False}
    out = dict(row)
    parsed: Any = out.get("content")
    try:
        parsed = json.loads(parsed) if isinstance(parsed, str) else parsed
    except Exception:
        pass
    out["content"] = parsed
    out["found"] = True
    out["body_html"] = (parsed or {}).get("body") if isinstance(parsed, dict) else None
    out["body_contains_old"] = bool(out["body_html"] and BODY_OLD in out["body_html"])
    out["body_contains_new"] = bool(out["body_html"] and BODY_NEW in out["body_html"])
    return out


def read_audit_rows(db: str, canvas_id: str) -> List[Dict[str, Any]]:
    """Every audit row for this canvas, in the store's own order.

    `created_at` is microsecond-precision server-side, so the ordering below is
    the append order, and the ids make each row individually citable.
    """
    con = _world_db(db)
    try:
        rows = con.execute(
            "SELECT id, canvas_id, action_type, user_id, agent_id, canvas_type, "
            "details_json, created_at FROM canvas_audit WHERE canvas_id=? "
            "ORDER BY created_at, id", (canvas_id,)).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        details: Any = r["details_json"]
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                pass
        content = (details or {}).get("content") if isinstance(details, dict) else None
        body = content.get("body") if isinstance(content, dict) else (
            content if isinstance(content, str) else None)
        out.append({
            "id": r["id"],
            "action_type": r["action_type"],
            "user_id": r["user_id"],
            "agent_id": r["agent_id"],
            "canvas_type": r["canvas_type"],
            "created_at": r["created_at"],
            "operation_id": (details or {}).get("operation_id")
            if isinstance(details, dict) else None,
            "review_status": (details or {}).get("review_status")
            if isinstance(details, dict) else None,
            "body_contains_old": bool(body and BODY_OLD in body),
            "body_contains_new": bool(body and BODY_NEW in body),
            "details_keys": sorted((details or {}).keys())
            if isinstance(details, dict) else None,
        })
    return out


def log_slice(world: Path, offset: int) -> str:
    log = world / "preview_backend.log"
    if not log.exists():
        return ""
    with log.open("rb") as fh:
        fh.seek(offset)
        return fh.read().decode("utf-8", errors="replace")


def log_offset(world: Path) -> int:
    log = world / "preview_backend.log"
    return log.stat().st_size if log.exists() else 0


def api_login(base: str, email: str, password: str) -> Tuple[str, Dict[str, Any]]:
    """POST /api/auth/login -- the same call the login FORM makes.

    Used only to seed the probe canvas. The browser logs in through the form
    on its own, in V0, so no result here depends on this token.
    """
    import httpx
    r = httpx.post(f"{base}/api/auth/login", trust_env=False, timeout=60,
                   json={"username": email, "password": password})
    if r.status_code != 200:
        raise SystemExit(f"login for canvas seeding failed: {r.status_code} "
                         f"{r.text[:200]}")
    data = r.json() or {}
    token = data.get("access_token")
    if not token:
        raise SystemExit("login returned no access_token")
    return token, {"status": r.status_code, "keys": sorted(data.keys())}


def jwt_subject(token: str) -> Optional[str]:
    import base64
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return str(json.loads(base64.urlsafe_b64decode(payload).decode())["sub"])
    except Exception:
        return None


# ------------------------------------------------------------------ the driver
class BrowserCanvasEdit:
    def __init__(self, world: str, out: Path, *, headed: bool = False,
                 edit_request: str = DEFAULT_EDIT_REQUEST,
                 label: str = "unpinned") -> None:
        state_path = WORLDS / world / "preview_stack.json"
        if not state_path.exists():
            raise SystemExit(
                f"world {world!r} has no preview stack. Launch one with:\n"
                f"  python scripts/orchestration_acceptance/preview_stack.py "
                f"--world {world} up --backend-port <p> --frontend-port <p>")
        self.state = json.loads(state_path.read_text())
        if not self.state.get("frontend_port"):
            raise SystemExit(
                f"world {world!r} has no frontend (frontend_port="
                f"{self.state.get('frontend_port')!r}, intent="
                f"{self.state.get('frontend_intent')!r}). Editing is a UI "
                f"capability; attach one with `preview_stack.py --world "
                f"{world} frontend-up`.")
        self.world = world
        self.world_path = WORLDS / world
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.shots = self.out / "screenshots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.frontend = f"http://localhost:{self.state['frontend_port']}"
        self.backend_port = int(self.state["backend_port"])
        self.base = f"http://127.0.0.1:{self.backend_port}"
        self.db = self.state["db_path"]
        self.farm = Path(self.state.get("frontend_farm") or (self.world_path / "frontend_farm"))
        self.headed = headed
        self.label = label
        self.edit_request = edit_request
        self.steps: List[Dict[str, Any]] = []
        self.origins: set = set()
        self.console: List[str] = []
        self.net: List[Dict[str, Any]] = []
        # Stable by default, and the SAME value the published quickstart tells
        # the user to type. Override with LANE3_PREVIEW_PASSWORD if needed.
        self.password = os.environ.get("LANE3_PREVIEW_PASSWORD") or \
            "preview-only-local-2026"

    # -- reporting ---------------------------------------------------------
    def check(self, name: str, ok: bool, detail: Any = None, *,
              na_if: Optional[Tuple[str, bool, str]] = None) -> bool:
        """Publish one assertion as PASS / FAIL / NOT APPLICABLE.

        `na_if` is (guard_assertion_name, guard_value, reason). When the guard
        holds, this assertion cannot mean anything, so it is published as NOT
        APPLICABLE and EXCLUDED from the ratio -- never folded in as a pass and
        never quietly dropped.
        """
        row: Dict[str, Any] = {"assertion": name}
        if na_if is not None and na_if[1]:
            row.update({"verdict": "NOT APPLICABLE", "reason": na_if[2],
                        "established_by": f"{na_if[0]} = True"})
            self.steps.append(row)
            print(f"  n/a   {name}\n         {na_if[2]} ({na_if[0]} = True)")
            return False
        row.update({"verdict": "PASS" if ok else "FAIL",
                    "recorded_value": bool(ok), "detail": detail})
        self.steps.append(row)
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f"   {str(detail)[:170]}" if detail is not None else ""))
        return bool(ok)

    def shot(self, page: Any, name: str) -> None:
        try:
            page.screenshot(path=str(self.shots / f"{name}.png"), full_page=True)
        except Exception as exc:  # a screenshot must never fail a case
            self.console.append(f"screenshot {name} failed: {exc}")

    # -- network capture ---------------------------------------------------
    def _on_request(self, r: Any) -> None:
        """Record the browser's OWN outgoing request. No reconstruction.

        `post_data` is the serialised body the page actually put on the wire --
        this is the thing under test, so it is read from the request object and
        never re-sent, re-built from the page's state, or fetched again.
        """
        self.net.append({"type": "request", "url": r.url, "method": r.method,
                         "post_data": r.post_data
                         if "/api/chat/message" in r.url else None})

    def _on_response(self, r: Any) -> None:
        self.net.append({"type": "response", "url": r.url, "status": r.status})

    # -- seeding (V1) ------------------------------------------------------
    def seed_canvas(self, token: str, user_id: str) -> Dict[str, Any]:
        """Create the probe canvas through the product's own endpoints.

        Deliberately NOT a direct INSERT (see f14cb301a): a row written straight
        into `canvases` with no CanvasAudit trail is a state the product never
        creates, and readers treat the audit trail as the source of truth. Both
        calls are recorded -- method, URL, request body, status, returned id --
        so the fixture is auditable rather than asserted.
        """
        import httpx
        canvas_id = str(uuid.uuid4())
        body_html = (f"<div><p>Quote for Steve</p>"
                     f"<p><b>{BODY_OLD}</b></p>"
                     f"<p>Rows 1-5 are the requested machines.</p>"
                     f"<!-- {MARKER} --></div>")
        content = {"to": "steve@example.com", "cc": "",
                   "subject": "Quote for Steve", "body": body_html}
        hdr = {"Authorization": f"Bearer {token}",
               "Origin": f"http://localhost:{self.state['frontend_port']}"}
        calls: List[Dict[str, Any]] = []

        r = httpx.post(f"{self.base}/api/canvas/email/create", headers=hdr,
                       trust_env=False, timeout=60,
                       json={"subject": "Quote for Steve",
                             "recipients": ["steve@example.com"],
                             "canvas_id": canvas_id, "user_id": user_id})
        calls.append({"step": "create", "method": "POST",
                      "url": f"{self.base}/api/canvas/email/create",
                      "request": {"subject": "Quote for Steve",
                                  "recipients": ["steve@example.com"],
                                  "canvas_id": canvas_id, "user_id": user_id},
                      "status": r.status_code,
                      "response_keys": sorted((r.json() or {}).keys())
                      if r.status_code == 200 else r.text[:300]})
        if r.status_code != 200:
            raise SystemExit(f"canvas creation API failed: {r.status_code} "
                             f"{r.text[:300]}")
        made = (r.json() or {}).get("canvas_id") or canvas_id

        u = httpx.put(f"{self.base}/api/canvas/{made}", headers=hdr,
                      trust_env=False, timeout=60,
                      params={"canvas_type": "email"}, json=content)
        calls.append({"step": "seed_content", "method": "PUT",
                      "url": f"{self.base}/api/canvas/{made}"
                             f"?canvas_type=email",
                      "request": content, "status": u.status_code,
                      "response": (u.json() or {}) if u.status_code == 200
                      else u.text[:300]})
        if u.status_code != 200:
            raise SystemExit(f"canvas content API failed: {u.status_code} "
                             f"{u.text[:300]}")
        return {"canvas_id": made, "content": content, "seeded_via": "api",
                "http_calls": calls}

    # -- DOM reading -------------------------------------------------------
    READ_MESSAGES_JS = """
    () => {
      const panel = document.querySelector('[data-testid="canvas-side-panel"]');
      if (!panel) return null;
      const list = panel.querySelector('div.overflow-y-auto');
      if (!list) return null;
      const out = [];
      for (const el of Array.from(list.children)) {
        const wrapperCls = (el.className || '');
        const bubble = el.firstElementChild;
        const bubbleCls = bubble ? (bubble.className || '') : '';
        let kind = 'other';
        if (wrapperCls.indexOf('text-right') !== -1
            || bubbleCls.indexOf('bg-primary') !== -1) kind = 'user';
        else if (bubbleCls.indexOf('bg-amber-100') !== -1
                 || bubbleCls.indexOf('dark:bg-amber-900') !== -1) kind = 'system';
        else if (bubbleCls.indexOf('bg-background') !== -1) kind = 'assistant';
        out.push({kind: kind, wrapper_class: wrapperCls,
                  bubble_class: bubbleCls,
                  text: (el.innerText || '').trim()});
      }
      return out;
    }
    """
    READ_CANVAS_TEXT_JS = """
    () => {
      const c = document.querySelector('[data-testid="canvas-container"]');
      return c ? (c.innerText || '').trim() : null;
    }
    """

    def read_messages(self, page: Any) -> Optional[List[Dict[str, Any]]]:
        return page.evaluate(self.READ_MESSAGES_JS)

    def read_canvas_text(self, page: Any) -> Optional[str]:
        return page.evaluate(self.READ_CANVAS_TEXT_JS)

    def classify_claim(self, text: str) -> Dict[str, Any]:
        low = (text or "").lower()
        claims = [p for p in MUTATION_CLAIM_PHRASES if p in low]
        denies = [p for p in NO_CHANGE_PHRASES if p in low]
        return {"asserts_mutation": bool(claims) and not denies,
                "denies_mutation": bool(denies),
                "claim_phrases_matched": claims,
                "no_change_phrases_matched": denies}

    # -- the run -----------------------------------------------------------
    def run(self) -> int:
        from playwright.sync_api import sync_playwright

        set_world_password(self.db, self.password)
        fe_digest = frontend_source_digest(self.farm)
        token, login_meta = api_login(self.base, LOGIN_EMAIL, self.password)
        user_id = jwt_subject(token)
        if not user_id:
            raise SystemExit("could not read the subject out of the login token")
        print(f"[seed] user_id={user_id}")

        seed = self.seed_canvas(token, user_id)
        canvas_id = seed["canvas_id"]
        print(f"[seed] canvas_id={canvas_id} (POST /api/canvas/email/create + "
              f"PUT /api/canvas/{canvas_id})")

        before = read_canvas_row(self.db, canvas_id)
        audit_before = read_audit_rows(self.db, canvas_id)
        self.check("V1_canvas_exists_after_api_creation", before.get("found"),
                   {"canvas_id": canvas_id, "canvas_type": before.get("canvas_type"),
                    "audit_rows": len(audit_before)})
        self.check("V1_canvas_seeded_with_the_old_text",
                   bool(before.get("body_contains_old"))
                   and not before.get("body_contains_new"),
                   {"body_contains_old": before.get("body_contains_old"),
                    "body_contains_new": before.get("body_contains_new")})
        self.check("V1_api_creation_left_an_audit_trail",
                   any(r["action_type"] == "create" for r in audit_before),
                   {"actions": [r["action_type"] for r in audit_before]})

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not self.headed)
            ctx = browser.new_context(viewport={"width": 1600, "height": 1100})
            page = ctx.new_page()
            page.on("request", self._on_request)
            page.on("response", self._on_response)
            page.on("requestfailed", lambda r: self.net.append(
                {"type": "requestfailed", "url": r.url, "method": r.method}))
            page.on("console", lambda m: self.console.append(
                f"{m.type}: {m.text[:200]}"))

            # --------------------------------------------------------- V0 login
            page.goto(f"{self.frontend}/login", wait_until="domcontentloaded",
                      timeout=180_000)
            page.locator('[data-testid="login-email-input"]').wait_for(
                state="visible", timeout=180_000)
            page.locator('[data-testid="login-email-input"]').fill(LOGIN_EMAIL)
            page.locator('[data-testid="login-password-input"]').fill(self.password)
            page.locator('[data-testid="login-submit-button"]').click()
            try:
                page.wait_for_url(lambda u: "/login" not in u, timeout=180_000)
            except Exception:
                pass
            self.shot(page, "V0_login")
            self.check("V0_login_through_the_real_form", "/login" not in page.url,
                       page.url)
            self.check("V0_the_composer_will_post_as_this_user",
                       page.evaluate("() => localStorage.getItem('user_email')")
                       == LOGIN_EMAIL,
                       page.evaluate(
                           "() => ({email: localStorage.getItem('user_email'),"
                           " has_token: !!localStorage.getItem('auth_token')})"))

            # ------------------------------------------------- V2 the real page
            page.goto(f"{self.frontend}/canvas/{canvas_id}",
                      wait_until="domcontentloaded", timeout=180_000)
            page.locator('[data-testid="canvas-side-panel"]').wait_for(
                state="visible", timeout=180_000)
            # The COMPOSER is the thing under test, so this is the element the
            # page must really be showing. The canvas panel itself is asserted
            # separately below, because it is a different subject with its own
            # measured behaviour.
            box = page.locator('textarea[placeholder^="Ask the agent to edit"]').first
            box.wait_for(state="visible", timeout=180_000)
            page.wait_for_timeout(8000)
            self.shot(page, "V2_canvas_page")
            # The header BAR, not just the h1: the canvas type is a badge
            # rendered beside the title, and reading only the h1 makes a
            # correctly-shown type look absent.
            header = page.locator("h1").first.inner_text()
            header_bar = page.locator("h1").first.locator("xpath=..").inner_text()
            panel_present = page.locator('[data-testid="canvas-container"]').count() > 0
            canvas_text = self.read_canvas_text(page) or ""
            self.check("V2_the_page_renders_the_co_editor_composer", True,
                       {"composer_textareas":
                        page.locator('textarea[placeholder^="Ask the agent to edit"]').count(),
                        "send_buttons":
                        page.locator('button[aria-label="Send message"]').count(),
                        "url": page.url})
            self.check("V2_the_page_identifies_this_canvas",
                       canvas_id in page.url and (canvas_id in header
                                                  or "Quote for Steve" in header),
                       {"url": page.url, "header": header})
            self.check("V2_the_page_shows_the_canvas_type",
                       "email" in (header_bar + canvas_text).lower(),
                       (header_bar + " | " + canvas_text[:80]))
            # The canvas PANEL is a separate assertion because its behaviour is
            # not what a user would predict: CanvasPanel consumes its
            # `lastMessage` prop ONLY when the parent does not also hand it a
            # socket listener, and /canvas/[id] passes both -- so the panel
            # never applies the page's own present frame and renders nothing
            # until a canvas broadcast arrives. A user who opens a canvas by URL
            # sees an empty canvas area.
            self.check("V2_the_canvas_area_rendered_its_content_on_load",
                       panel_present and BODY_OLD in canvas_text,
                       {"canvas_container_present": panel_present,
                        "canvas_text_chars": len(canvas_text),
                        "rte_surface": page.locator(".rte-surface").count(),
                        "note": "the page DID load this canvas (the header "
                                "carries its type); the panel host did not "
                                "render. CanvasPanel applies its `lastMessage` "
                                "prop only when the parent passes no socket "
                                "listener, and /canvas/[id] passes both."})

            # Which origins did this browser actually talk to? Recorded before
            # the turn, so a claim about isolation is measured, not assumed.
            for r in self.net:
                if r["type"] == "request":
                    for m in re.findall(r"https?://(?:localhost|127\.0\.0\.1):\d+",
                                        r["url"]):
                        self.origins.add(m.rstrip("/"))
            foreign = sorted(o for o in self.origins
                             if f":{self.backend_port}" not in o
                             and str(self.state["frontend_port"]) not in o)
            self.check("V0_this_browser_only_talks_to_this_candidate", not foreign,
                       {"origins": sorted(self.origins), "foreign": foreign})

            # ------------------------------------ V3 the composer's real request
            send = page.locator('button[aria-label="Send message"]').first
            send.wait_for(state="visible", timeout=60_000)
            before_msgs = self.read_messages(page) or []
            n_user_before = sum(1 for m in before_msgs if m["kind"] == "user")

            off = log_offset(self.world_path)
            t_sent = time.time()
            box.fill(self.edit_request)
            self.shot(page, "V3_typed")
            chat_response: Dict[str, Any] = {}
            try:
                with page.expect_response(
                        lambda r: "/api/chat/message" in r.url,
                        timeout=300_000) as info:
                    send.click()
                resp = info.value
                chat_response = {"status": resp.status,
                                 "url": resp.url,
                                 "body": resp.json() if resp.ok else resp.text()[:4000]}
            except Exception as exc:
                chat_response = {"error": str(exc)[:400]}
            t_resp = time.time()
            page.wait_for_timeout(2000)

            posted = [r for r in self.net
                      if r["type"] == "request" and "/api/chat/message" in r["url"]]
            self.check("V3_the_composer_actually_sent_one_chat_request",
                       len(posted) == 1,
                       {"count": len(posted),
                        "url": posted[0]["url"] if posted else None})
            if not posted:
                return self._finish(page, browser, seed, fe_digest, login_meta,
                                    user_id, before, audit_before, off,
                                    t_sent, t_resp, chat_response, {}, None,
                                    None, None)
            raw = posted[0]["post_data"]
            try:
                payload = json.loads(raw)
            except Exception as exc:
                self.check("V3_the_captured_payload_is_json", False,
                           f"unparseable: {exc}; first 300 bytes: {raw[:300]}")
                payload = {}

            # -- the assertions that matter: the BYTES the browser sent.
            ctx_sent = payload.get("context") or {}
            self.check("V3_payload_names_this_canvas",
                       ctx_sent.get("canvas_id") == canvas_id,
                       {"sent_canvas_id": ctx_sent.get("canvas_id"),
                        "expected": canvas_id})
            self.check("V3_payload_names_the_canvas_type",
                       (ctx_sent.get("canvas_type") or "") == "email",
                       {"sent_canvas_type": ctx_sent.get("canvas_type")})
            self.check("V3_payload_names_the_current_page",
                       ctx_sent.get("current_page") == f"/canvas/{canvas_id}",
                       {"sent_current_page": ctx_sent.get("current_page")})
            sent_content = ctx_sent.get("canvas_content")
            self.check("V3_payload_carries_the_canvas_content",
                       isinstance(sent_content, dict)
                       and BODY_OLD in (sent_content.get("body") or ""),
                       {"is_dict": isinstance(sent_content, dict),
                        "keys": sorted(sent_content.keys())
                        if isinstance(sent_content, dict) else None,
                        "body_contains_old": BODY_OLD in (
                            (sent_content or {}).get("body") or "")
                        if isinstance(sent_content, dict) else None,
                        "body_chars": len((sent_content or {}).get("body") or "")
                        if isinstance(sent_content, dict) else None})
            self.check("V3_payload_content_matches_the_durable_canvas",
                       isinstance(sent_content, dict)
                       and sent_content.get("to") == (before.get("content") or {}).get("to")
                       and sent_content.get("subject") == (before.get("content") or {}).get("subject"),
                       {"sent_subject": (sent_content or {}).get("subject")
                        if isinstance(sent_content, dict) else None,
                        "durable_subject": (before.get("content") or {}).get("subject")})
            self.check("V3_payload_carries_the_edit_request_verbatim",
                       payload.get("message") == self.edit_request,
                       payload.get("message"))
            self.check("V3_payload_posts_to_this_world_s_backend",
                       f":{self.backend_port}" in posted[0]["url"],
                       posted[0]["url"])
            self.check("V3_payload_carries_a_session_identity",
                       bool(payload.get("session_id")),
                       {"session_id": payload.get("session_id"),
                        "user_id": payload.get("user_id"),
                        "request_id": payload.get("request_id"),
                        "agent_id": payload.get("agent_id")})
            self.check("V3_payload_carries_the_conversation_so_far",
                       isinstance(ctx_sent.get("conversation_history"), list),
                       {"history_len": len(ctx_sent.get("conversation_history") or [])})

            # ----------------------------------------- V4 the turn, read back
            session_id = chat_response.get("body", {}).get("session_id") \
                if isinstance(chat_response.get("body"), dict) else None
            outcome: Dict[str, Any] = {}
            try:
                msgs = page.wait_for_function(
                    """(n) => {
                        const panel = document.querySelector('[data-testid="canvas-side-panel"]');
                        if (!panel) return false;
                        const list = panel.querySelector('div.overflow-y-auto');
                        if (!list) return false;
                        const kids = Array.from(list.children);
                        const users = kids.filter(el => (el.className||'').indexOf('text-right') !== -1);
                        if (users.length <= n) return false;
                        // an answer AFTER this turn's question, with text
                        for (let i = users.length - 1; i >= 0; i--) {
                            for (let j = i + 1; j < kids.length; j++) {
                                const b = kids[j].firstElementChild;
                                const bc = b ? (b.className||'') : '';
                                if (bc.indexOf('bg-background') !== -1
                                    && (kids[j].innerText||'').trim()) return true;
                            }
                        }
                        return false;
                    }""", arg=n_user_before, timeout=300_000)
                del msgs
            except Exception as exc:
                self.console.append(f"assistant bubble wait: {exc}")
            page.wait_for_timeout(4000)
            self.shot(page, "V4_reply")

            live = self.read_messages(page) or []
            assistant = [m for m in live if m["kind"] == "assistant"]
            reply_text = assistant[-1]["text"] if assistant else ""
            n_user_after = sum(1 for m in live if m["kind"] == "user")
            self.check("V4_the_turn_produced_exactly_one_user_message",
                       n_user_after == n_user_before + 1,
                       {"before": n_user_before, "after": n_user_after})
            self.check("V4_the_turn_produced_an_assistant_answer", bool(reply_text),
                       {"assistant_bubbles": len(assistant),
                        "chars": len(reply_text),
                        "head": reply_text[:160]})

            # The machine-readable outcome the product itself returned. The DOM
            # is the user's view; this is the product's own verdict on the turn.
            body = chat_response.get("body")
            if isinstance(body, dict):
                meta = body.get("metadata") or {}
                outcome = {"http_status": chat_response.get("status"),
                           "success": body.get("success"),
                           "error_code": body.get("error_code"),
                           "intent": body.get("intent"),
                           "execution_id": body.get("execution_id"),
                           "session_id": body.get("session_id"),
                           "canvas_edit": meta.get("canvas_edit"),
                           "reply_message": body.get("message")}
            else:
                outcome = {"http_status": chat_response.get("status"),
                           "error": chat_response.get("error")}
            ce = outcome.get("canvas_edit") or {}
            self.check("V4_the_product_reported_a_machine_readable_outcome",
                       isinstance(ce, dict) and ce.get("canvas_id") == canvas_id
                       and "updated" in ce,
                       outcome)

            after = read_canvas_row(self.db, canvas_id)
            audit_after = read_audit_rows(self.db, canvas_id)
            new_rows = [r for r in audit_after
                        if r["id"] not in {x["id"] for x in audit_before}]
            updates = [r for r in new_rows if r["action_type"] == "update"]
            store_changed = bool(after.get("body_contains_new")
                                 and not after.get("body_contains_old"))
            self.check("V4_the_durable_canvas_content_actually_changed",
                       store_changed,
                       {"body_contains_old": after.get("body_contains_old"),
                        "body_contains_new": after.get("body_contains_new"),
                        "reported_updated": ce.get("updated")})
            # The mutation is attributed by an operation id, not by a timestamp
            # inference (update_canvas_content stamps details_json.operation_id).
            self.check("V4_exactly_one_update_audit_row_for_this_turn",
                       len(updates) == 1,
                       {"new_audit_rows": len(new_rows),
                        "update_rows": [r["id"] for r in updates],
                        "actions": [r["action_type"] for r in new_rows]},
                       # Inapplicable only when NOTHING landed. A first version
                       # of this file passed `store_changed` as the guard, which
                       # is INVERTED: it published the check as NOT APPLICABLE
                       # precisely when a mutation DID land -- the one case where
                       # the check is the whole point.
                       na_if=("V4_the_durable_canvas_content_actually_changed",
                              not store_changed,
                              "no mutation landed, so there is no update row to "
                              "count; the correct expectation for a declined "
                              "turn is zero update rows, asserted separately "
                              "below"))
            if updates:
                u = updates[0]
                self.check("V4_the_update_row_is_attributed_to_an_operation",
                           bool(u["operation_id"]),
                           {"operation_id": u["operation_id"],
                            "review_status": u["review_status"],
                            "user_id": u["user_id"]})
                self.check("V4_the_update_row_is_accepted_not_pending_review",
                           u["review_status"] == "accepted",
                           {"review_status": u["review_status"]})
                self.check("V4_the_update_row_belongs_to_this_user",
                           u["user_id"] == user_id,
                           {"row_user": u["user_id"], "request_user": user_id})
                self.check("V4_the_update_row_is_the_current_revision",
                           audit_after[-1]["id"] == u["id"],
                           {"latest": audit_after[-1]["id"], "update_row": u["id"]})
            else:
                self.check("V4_no_update_audit_row_was_written",
                           len(updates) == 0,
                           {"update_rows": [r["id"] for r in updates]})
            # A decline is only honest if it is COMPLETE: nothing may have been
            # written, not even under a different operation id.
            self.check("V4_the_turn_added_no_unrelated_audit_rows",
                       all(r["action_type"] in ("update",) for r in new_rows),
                       {"actions": [r["action_type"] for r in new_rows]})

            # ------------------------------------- V5 what the user is shown
            claim = self.classify_claim(reply_text)
            self.check("V5_the_visible_answer_matches_the_durable_store",
                       claim["asserts_mutation"] == store_changed,
                       {"store_changed": store_changed, **claim,
                        "reply": reply_text[:400]})
            if store_changed:
                self.check("V5_the_visible_answer_does_not_deny_the_change",
                           not claim["denies_mutation"], claim)
            self.check("V5_the_visible_canvas_shows_the_new_content",
                       (BODY_NEW in canvas_text_after(page)) == store_changed,
                       {"body_contains_new_in_dom":
                        BODY_NEW in canvas_text_after(page),
                        "canvas_container_present":
                        page.locator('[data-testid="canvas-container"]').count() > 0,
                        "store_changed": store_changed})

            # ------------------------------------------- V6 a browser RELOAD
            pre_reload_msgs = [m["text"] for m in live if m["kind"] in
                               ("user", "assistant", "system")]
            pre_reload_canvas = canvas_text_after(page)
            page.reload(wait_until="domcontentloaded", timeout=180_000)
            page.locator('[data-testid="canvas-side-panel"]').wait_for(
                state="visible", timeout=180_000)
            page.locator('textarea[placeholder^="Ask the agent to edit"]').first \
                .wait_for(state="visible", timeout=180_000)
            page.wait_for_timeout(12000)
            self.shot(page, "V6_reload")
            reloaded = self.read_messages(page) or []
            reload_msgs = [m["text"] for m in reloaded if m["kind"] in
                           ("user", "assistant", "system")]
            reload_canvas = canvas_text_after(page)
            reload_panel = page.locator('[data-testid="canvas-container"]').count()
            self.check("V6_reload_recovers_the_same_conversation",
                       reload_msgs == pre_reload_msgs,
                       {"before": len(pre_reload_msgs),
                        "after": len(reload_msgs),
                        "first_diff": next((i for i, (a, b) in enumerate(
                            zip(reload_msgs, pre_reload_msgs)) if a != b), None)})
            self.check("V6_reload_shows_the_same_canvas_state",
                       reload_canvas == pre_reload_canvas,
                       {"body_contains_new_before": BODY_NEW in pre_reload_canvas,
                        "body_contains_new_after": BODY_NEW in reload_canvas,
                        "canvas_container_after_reload": reload_panel,
                        "chars_before": len(pre_reload_canvas),
                        "chars_after": len(reload_canvas)})
            audit_reload = read_audit_rows(self.db, canvas_id)
            self.check("V6_reload_writes_nothing_new",
                       len(audit_reload) == len(audit_after),
                       {"audit_rows_before_reload": len(audit_after),
                        "audit_rows_after_reload": len(audit_reload)})
            after_reload = read_canvas_row(self.db, canvas_id)
            self.check("V6_reload_reads_back_the_same_durable_content",
                       (after_reload.get("body_contains_new")
                        and not after_reload.get("body_contains_old")) == store_changed,
                       {"body_contains_old": after_reload.get("body_contains_old"),
                        "body_contains_new": after_reload.get("body_contains_new")})

            return self._finish(page, browser, seed, fe_digest, login_meta,
                                user_id, before, audit_before, off, t_sent,
                                t_resp, chat_response, outcome, raw,
                                {"reply_text": reply_text,
                                 "claim": claim,
                                 "live_messages": live,
                                 "after_reload_messages": reloaded,
                                 "canvas_text_live": canvas_text_after(page),
                                 "canvas_text_before_reload": pre_reload_canvas,
                                 "canvas_text_after_reload": reload_canvas,
                                 "header": header, "header_bar": header_bar},
                                {"canvas_row_before": before,
                                 "canvas_row_after": after,
                                 "canvas_row_after_reload": after_reload,
                                 "audit_before": audit_before,
                                 "audit_after": audit_after,
                                 "audit_after_reload": audit_reload,
                                 "new_audit_rows": new_rows,
                                 "update_rows": updates,
                                 "store_changed": store_changed})

    # -- report ------------------------------------------------------------
    def _finish(self, page: Any, browser: Any, seed: Dict[str, Any],
                fe_digest: Dict[str, Any], login_meta: Dict[str, Any],
                user_id: str, before: Dict[str, Any],
                audit_before: List[Dict[str, Any]], off: int, t_sent: float,
                t_resp: float, chat_response: Dict[str, Any],
                outcome: Dict[str, Any], raw: Optional[str],
                dom: Optional[Dict[str, Any]], store: Optional[Dict[str, Any]]
                ) -> int:
        log = log_slice(self.world_path, off)
        # The planner's own trace, kept whole. A decline is only diagnosable if
        # the run carries evidence that the planner was REACHED and ANSWERED,
        # and whether the schema-boundary contract check fired -- the product
        # logs the plan shape only on a violation or a repair, so a clean
        # decline is silent unless the trace is captured.
        interesting = ("canvas", "plan", "structured-trace", "instructor",
                       "no_apply", "refused", "decline")
        planner_lines = [ln for ln in log.splitlines()
                         if not ln.startswith("INFO:main_api_app")
                         and any(k in ln.lower() for k in interesting)]
        ce = (outcome.get("canvas_edit") or {})
        declared_updated = bool(ce.get("updated"))
        store_changed = bool((store or {}).get("store_changed"))
        log_applied = "canvas co-editor edit applied" in log
        planner_answered = any("result_type=CanvasEditPlan" in ln
                               for ln in planner_lines)
        contract_violation = [ln for ln in planner_lines
                              if "SCHEMA-BOUNDARY" in ln or "consistency repair" in ln
                              or "repair exchange" in ln]
        # The turn's execution id threads the whole log slice, so the evidence
        # for THIS turn is separable from the world's other traffic.
        exec_id = str(outcome.get("execution_id") or "")
        turn_lines = [ln for ln in planner_lines if exec_id and exec_id[:8] in ln]

        # The VERDICT, stated separately from the harness' own health: the case
        # can be mechanically green (a decline handled honestly end to end) and
        # still not promote the capability. Both numbers are printed.
        self.check("V7_the_product_decided_an_outcome_on_this_turn",
                   isinstance(ce, dict) and (
                       "updated" in ce or "no_apply" in ce or "unverified" in ce
                       or ce.get("plan_unavailable") is True),
                   {"canvas_edit": ce})
        declined = bool(ce.get("no_apply")) or (ce.get("updated") is False
                                                and not ce.get("unverified"))
        # "The planner was reached and answered" is the control that separates
        # "the model declined" from "the model was never asked" -- the two look
        # identical from the user's side and only this distinguishes them.
        self.check("V7_the_production_planner_was_reached_and_answered",
                   planner_answered,
                   {"structured_trace_lines": [
                       ln[:220] for ln in planner_lines
                       if "structured-trace" in ln][-4:],
                    "schema_boundary_violation_logged": contract_violation,
                    "note": "the product logs a plan's shape only when the "
                            "contract check fires, so an EMPTY violation list "
                            "with a CanvasEditPlan trace means the plan was "
                            "internally CONSISTENT -- a real decline, not a "
                            "malformed answer"})
        self.check("V7_the_declared_outcome_agrees_with_the_durable_store",
                   declared_updated == store_changed,
                   {"declared_updated": declared_updated,
                    "store_changed": store_changed,
                    "log_says_applied": log_applied})
        if store_changed:
            self.check("V7_the_backend_log_records_the_applied_edit", log_applied,
                       [ln[:200] for ln in planner_lines
                        if "applied" in ln][:4])
        else:
            self.check("V7_the_backend_log_records_the_refusal",
                       "planner_declined" in json.dumps(ce)
                       or "canvas edit" in log or "not-an-edit" in log,
                       [ln[:200] for ln in planner_lines][-6:])

        n_pass = sum(1 for s in self.steps if s["verdict"] == "PASS")
        n_fail = sum(1 for s in self.steps if s["verdict"] == "FAIL")
        n_na = sum(1 for s in self.steps if s["verdict"] == "NOT APPLICABLE")
        applicable = n_pass + n_fail
        product_outcome = ("EDIT APPLIED" if store_changed
                           else "DECLINED / NOT APPLIED")
        report = {
            "schema": "lane3-browser-canvas-edit-v1",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "label": self.label,
            "world": self.world,
            "world_path": str(self.world_path),
            "run_dir": self.state.get("run_dir"),
            "db": self.db,
            "ports": {"backend": self.backend_port,
                      "frontend": self.state.get("frontend_port")},
            "frontend": self.frontend,
            "backend": self.base,
            "backend_health_identity": self.state.get("backend_health_identity", {}),
            "source_id": (self.state.get("backend_health_identity", {})
                          or {}).get("source_id"),
            "effective_flags": self.state.get("effective_flags", {}),
            "planner_pin": (self.state.get("effective_flags", {}) or {}).get(
                "ATOM_ASYNC_EDIT_PLAN_MODEL"),
            "injection": "none: the production planner ran on the real request; "
                         "no provider shim, no stubbed planner, no injected plan",
            "frontend_source": fe_digest,
            "login": {"email": LOGIN_EMAIL, "user_id": user_id,
                      "api_login_status": login_meta.get("status"),
                      "form_login_attempted": True,
                      "note": "the password is set in the world for this run and "
                              "is never recorded here"},
            "seed": seed,
            "edit_request": self.edit_request,
            "captured_request": {
                "url": next((r["url"] for r in self.net
                             if r["type"] == "request"
                             and "/api/chat/message" in r["url"]), None),
                "method": "POST",
                "post_data_bytes": len(raw or ""),
                "post_data": raw,
            },
            "chat_response": chat_response,
            "product_outcome": outcome,
            "durable_store": store,
            "canvas_before": before,
            "canvas_after": (store or {}).get("canvas_row_after"),
            "audit_before": audit_before,
            "audit_after": (store or {}).get("audit_after"),
            "audit_after_reload": (store or {}).get("audit_after_reload"),
            "dom": dom,
            "planner_evidence": {
                "answered": planner_answered,
                "structured_traces": [ln[:400] for ln in planner_lines
                                      if "structured-trace" in ln][-6:],
                "schema_boundary_violations": contract_violation,
                "repair_exchange": [ln[:400] for ln in planner_lines
                                    if "repair exchange" in ln],
                "plan_declined": declined,
                "execution_id": exec_id,
                "turn_log_lines": [ln[:300] for ln in turn_lines][-40:],
                "note": "the raw plan body is not logged for a CONSISTENT "
                        "decline -- only its shape, and only when the contract "
                        "check fires (6e34725c7). A decline is therefore "
                        "attributable to the model and the prompt, not to a "
                        "quotable plan object.",
            },
            "planner_log_lines": planner_lines[-120:],
            "log_window_bytes": len(log),
            "network_origins": sorted(self.origins),
            "console": self.console[-40:],
            "steps": self.steps,
            "counts": {"published": len(self.steps), "pass": n_pass,
                       "fail": n_fail, "not_applicable": n_na,
                       "applicable": applicable,
                       "note": f"{n_pass}/{applicable} of the APPLICABLE "
                               f"assertions passed; {n_na} published as NOT "
                               f"APPLICABLE and not counted in the ratio"},
            "verdict": "PASS" if n_fail == 0 else "FAIL",
            "capability_outcome": product_outcome,
            "capability_note": (
                "The harness verdict above is the HARNESS's health: it can be "
                "green because a decline was refused and reported honestly. "
                "The capability is the PRODUCT OUTCOME line: editing is only "
                "supported if the canvas actually changed."),
            "timing": {"sent_at": t_sent, "response_at": t_resp,
                       "response_s": round(t_resp - t_sent, 2)},
        }
        (self.out / f"browser_canvas_edit_{self.label}.json").write_text(
            json.dumps(report, indent=2, default=str))
        browser.close()

        ce = outcome.get("canvas_edit") or {}
        print(f"\ncapability outcome : {product_outcome}")
        print(f"  canvas_edit      : {json.dumps(ce, default=str)[:400]}")
        print(f"  store_changed    : {store_changed}")
        print(f"  visible reply    : {((dom or {}).get('reply_text') or '')[:300]!r}")
        print(f"\n{report['counts']['note']}")
        print(f"harness verdict : {report['verdict']}")
        print(f"-> {self.out}/browser_canvas_edit_{self.label}.json")
        print(f"screenshots  -> {self.shots}")
        return 0 if report["verdict"] == "PASS" else 1


def canvas_text_after(page: Any) -> str:
    """The canvas area's rendered text -- re-read, never cached across a reload."""
    try:
        return page.evaluate(BrowserCanvasEdit.READ_CANVAS_TEXT_JS) or ""
    except Exception:
        return ""


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--world", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--edit-request", default=DEFAULT_EDIT_REQUEST)
    ap.add_argument("--label", default="unpinned",
                    help="name this configuration in the artifact, e.g. the "
                         "value of ATOM_ASYNC_EDIT_PLAN_MODEL or 'unpinned'")
    args = ap.parse_args(argv)
    return BrowserCanvasEdit(args.world, Path(args.out), headed=args.headed,
                             edit_request=args.edit_request,
                             label=args.label).run()


if __name__ == "__main__":
    raise SystemExit(main())
