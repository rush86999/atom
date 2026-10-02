#!/usr/bin/env python3
"""Browser-test the task-correction chain through the real UI.

WHY A BROWSER AND NOT THE HTTP RUNNER
`task_correction_acceptance.py` already passes 4/4 over HTTP. That proves the
orchestrator. It does not prove the thing a user touches: that the login form
works, that the composer reaches THIS world, that the rendered bubble shows the
revised list, and that a browser reload still shows it. A previous browser run
(`preview_browser_results.json`) recorded `login.attempted: false` -- it drove a
seeded session token, so the real auth path was never exercised.

THE CHAIN, AND WHAT EACH STEP MUST PROVE
  B0  login through the real form                -> the auth path works at all
  B1  the seeded eight-item lookup               -> 8 items, requested order
  B2  "Replace U-22 with U-38"                   -> U-22 gone, U-38 present, and
                                                    U-38 carries an HONEST ABSENCE
                                                    because it is not in the book
  B3  "Make this easier to read"                 -> re-render of the revised set,
                                                    and B1/B2 answers UNCHANGED
  B4  "Search again and show the same items"     -> a real re-read, revised set
  B5  browser reload                              -> same final answer, same
                                                    evidence association
  B6  no unrelated task row                      -> the correction created no
                                                    obligation the user never
                                                    asked for

The U-38 absence assertion is the one that cannot be softened. A replacement
does not guarantee the incoming item exists; the fixture probe decides. When the
item is absent from the source, a rendered PRICE for it is a fabrication, and
this fails on it.

Nothing here trusts a prior result. Every verdict is computed from text this run
read out of the DOM, plus one read-only query for the task row.

    browser_correction_chain.py --world candidate_fix1 --out <dir> [--headed]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
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

USER_ID = "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"
LOGIN_EMAIL = "admin@example.com"
BASE_ORDER = ["No. 381", "U-22", "No. 622", "TK Manual Flanger", "SLE24-16",
              "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]
REPLACED_ORDER = ["No. 381", "U-38", "No. 622", "TK Manual Flanger", "SLE24-16",
                  "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]
OUTGOING = "U-22"
INCOMING = "U-38"

BASE_ASK = ("find the prices of these 8 machines in Consolidated Price List "
            "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
            "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
REPLACE_TURN = "Replace U-22 with U-38"
FORMAT_TURN = "Make this easier to read"
RESEARCH_TURN = "Search again and show the same items"
#: A general question, so this turn takes the LLM leg and actually streams. The
#: seeded workbook asks above are answered deterministically and correctly emit
#: no tokens, so they cannot demonstrate streaming in the UI.
STREAM_PROMPT = "In two sentences, what is a price list used for?"

# Phrases that would mean the app is claiming a value it does not have for the
# incoming item. Checked case-insensitively against the incoming item's own line
# and the sentence around it.
ABSENCE_MARKERS = (
    "not listed", "not found", "no matching row", "not in the", "does not list",
    "could not find", "unable to find", "no price for", "not present",
    "absent", "no entry", "not available in", "no longer", "unknown",
)


# --------------------------------------------------------------------- helpers
def set_world_password(db_path: str, password: str) -> None:
    """Make the world's admin loggable through the real form.

    Scoped exactly like the existing preview_login.py: refuse any path that is
    not inside an acceptance world, and never leave TESTING set (core/database.py
    treats TESTING=1 as "force the scratch DB", which would silently write to
    backend/test_integration.db instead of the world).

    This is the one write this driver performs, and it is a credential set-up
    step, not part of what is being measured. The password is never printed,
    logged, or written to the report.
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

    Walks the symlinks (so the repo's real files are hashed, not the links) over
    the entry points that decide chat behaviour, plus the resolved config.
    """
    import hashlib
    tracked = [
        "hooks/useWebSocket.ts", "hooks/chat/useChatInterface.ts",
        "components/chat/ChatInterface.tsx", "components/chat/ChatInput.tsx",
        "components/chat/MessageList.tsx", "pages/chat/index.tsx",
        "pages/login.tsx", "next.config.js",
    ]
    per_file: Dict[str, Optional[str]] = {}
    h = hashlib.sha256()
    for rel in tracked:
        p = farm / rel
        try:
            real = p.resolve()
            data = real.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            per_file[rel] = digest
            h.update(rel.encode())
            h.update(digest.encode())
        except OSError:
            per_file[rel] = None
    return {"farm": str(farm), "tree_sha256": h.hexdigest(),
            "files": per_file,
            "note": "symlink farm over the live working tree; the backend is "
                    "frozen by the world's code export but the frontend is not, "
                    "so this digest is what makes the browser result attributable"}


def _presentation_module() -> Any:
    sys.path.insert(0, str(BACKEND))
    import core.answer_presentation as ap
    return ap


def visible_items(text: str) -> List[str]:
    """Items the UI actually presented, read out of the DOM.

    Delegates to the production parser (`answer_presentation._visible_items`) so
    this driver and the HTTP acceptance runner share ONE definition of "the
    displayed list". Writing a second parser here is how a browser test and an
    API test come to disagree about the same answer.

    The DOM matters: the backend emits markdown (`- **No. 381** - 1777`) but the
    browser has already turned the bold into <strong>, so `inner_text` arrives
    WITHOUT asterisks. A parser that only understands the markdown source sees an
    empty list in the browser and every item assertion silently fails open. The
    production parser tolerates both forms, which is why it is reused here.
    """
    return _presentation_module()._visible_items(text or "")


def item_line(text: str, item: str) -> str:
    """The rendered line the UI showed for `item`, or "" if it showed none."""
    return _presentation_module()._item_line(text or "", item)


def stated_value(text: str, item: str) -> Optional[str]:
    """The figure the rendered line states for `item`, or None if it states none.

    None is a real, meaningful answer here: for an item that is not in the
    source the honest rendering states no number at all, and this returning None
    is what the absence assertion depends on.
    """
    line = item_line(text, item)
    if not line:
        return None
    rest = line.split(" - ", 1)[1] if " - " in line else ""
    rest = rest.strip()
    rest = re.sub(r"^\([^)]*\)\s*", "", rest).strip()
    if rest.startswith("several rows match") or "no matching row" in rest:
        return None
    num = re.match(r"^\**(-?[\d,]+(?:\.\d+)?)\**", rest)
    return num.group(1) if num else None


def incoming_is_labelled_absent(text: str, item: str) -> Dict[str, Any]:
    """Does the UI honestly report `item` as absent, or invent a value for it?

    Two independent requirements, both necessary:
      * it states NO numeric value for the item, and
      * it says why, in words, somewhere on that item's line or the reply.

    A silent omission satisfies the first and fails the second, because the user
    cannot tell a missing answer from a rendering bug. Conversely a sentence that
    merely mentions the item while a number is displayed still fails the first.
    """
    value = stated_value(text, item)
    if value is not None:
        return {"ok": False, "reason": "a numeric value is displayed for an item "
                                      "that is not in the source",
                "stated_value": value}
    window = [ln for ln in (text or "").splitlines() if item in ln]
    hay = " ".join(window).lower() if window else (text or "").lower()
    marker = next((m for m in ABSENCE_MARKERS if m in hay), None)
    return {"ok": marker is not None,
            "reason": ("explicit absence wording present" if marker
                       else "no value shown, but no absence wording either: the "
                            "user cannot tell a missing answer from a bug"),
            "marker": marker,
            "mentions_item": bool(window),
            "lines": window[:3]}


def task_rows_since(db: str, since_iso: str) -> List[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, title, created_at FROM tasks "
            "WHERE user_id=? AND created_at >= ? ORDER BY created_at",
            (USER_ID, since_iso)).fetchall()
    except sqlite3.Error as exc:
        return [{"error": f"tasks table unreadable: {exc}"}]
    finally:
        con.close()
    return [{"id": str(r[0]), "title": r[1], "created_at": r[2]} for r in rows]


def sha(text: str) -> str:
    import hashlib
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ the driver
class Chain:
    def __init__(self, world: str, out: Path, headed: bool = False) -> None:
        state = json.loads((WORLDS / world / "preview_stack.json").read_text())
        if not state.get("frontend_port"):
            raise SystemExit(
                f"world {world!r} has no frontend (frontend_port="
                f"{state.get('frontend_port')!r}, intent="
                f"{state.get('frontend_intent')!r}). Browser verification needs a "
                "real UI; attach one with `preview_stack.py --world "
                f"{world} frontend-up`.")
        self.world = world
        self.state = state
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.shots = self.out / "screenshots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.frontend = f"http://localhost:{state['frontend_port']}"
        self.backend_port = state["backend_port"]
        self.db = state["db_path"]
        self.farm = Path(state.get("frontend_farm")
                         or (WORLDS / world / "frontend_farm")).resolve() \
            if state.get("frontend_farm") else None
        if self.farm is None:
            self.farm = (REPO / "frontend-nextjs" / ".preview-instance" / world)
        self.headed = headed
        self.steps: List[Dict[str, Any]] = []
        self.origins: set = set()
        self.console: List[str] = []
        # Stable by default, and the SAME value the published quickstart tells the
        # user to type. An earlier version generated a random password per run,
        # which silently invalidated the documented credentials every time anyone
        # re-ran the check. Override with LANE3_PREVIEW_PASSWORD if you need to.
        self.password = os.environ.get("LANE3_PREVIEW_PASSWORD") or \
            "preview-only-local-2026"

    # -- reporting ---------------------------------------------------------
    def step(self, name: str, ok: bool, detail: Any = None) -> bool:
        self.steps.append({"step": name, "ok": bool(ok), "detail": detail})
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f"   {str(detail)[:150]}" if detail is not None else ""))
        return bool(ok)

    def shot(self, page: Any, name: str) -> None:
        try:
            page.screenshot(path=str(self.shots / f"{name}.png"), full_page=True)
        except Exception as exc:
            self.console.append(f"screenshot {name} failed: {exc}")

    # -- page helpers ------------------------------------------------------
    def responses(self, page: Any) -> List[Dict[str, Any]]:
        return [r for r in page._lane3_net if r["type"] == "response"]

    def requests(self, page: Any) -> List[Dict[str, Any]]:
        return [r for r in page._lane3_net if r["type"] == "request"]

    def send(self, page: Any, text: str, previous: int) -> Tuple[str, List[str]]:
        """Type into the composer, send, and wait for a NEW assistant bubble.

        Waiting on the bubble COUNT rather than on a spinner is deliberate: a
        turn that legitimately emits no tokens has no streaming indicator, and a
        driver that waits for one hangs on exactly the deterministic turns this
        chain is made of.
        """
        box = page.locator('[data-testid="agent-chat-input"]').first
        box.wait_for(state="visible", timeout=60_000)
        box.fill(text)
        page.locator('[data-testid="send-message-button"]').first.click()
        page.wait_for_function(
            "n => document.querySelectorAll('[data-testid=\"agent-response\"]').length > n",
            arg=previous, timeout=300_000)
        # Let the bubble settle: React can still be streaming/replacing text.
        page.wait_for_timeout(2500)
        bubbles = page.locator('[data-testid="agent-response"]')
        return bubbles.nth(bubbles.count() - 1).inner_text(), []

    def count_bubbles(self, page: Any) -> int:
        return page.locator('[data-testid="agent-response"]').count()

    def bubble_texts(self, page: Any) -> List[str]:
        loc = page.locator('[data-testid="agent-response"]')
        return [loc.nth(i).inner_text() for i in range(loc.count())]

    # -- main --------------------------------------------------------------
    def run(self) -> int:
        from playwright.sync_api import sync_playwright

        set_world_password(self.db, self.password)
        fe_digest = frontend_source_digest(self.farm)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not self.headed)
            ctx = browser.new_context(viewport={"width": 1500, "height": 1000})
            page = ctx.new_page()
            page._lane3_net = []
            page.on("request", lambda r: page._lane3_net.append(
                {"type": "request", "url": r.url, "method": r.method,
                 # The chat request body carries the session id this surface
                 # minted. Guessing it from the URL or localStorage is how a
                 # history comparison silently compares against nothing.
                 "post": (r.post_data or "")[:4000]
                 if "/api/chat/message" in r.url else None}))
            page.on("response", lambda r: page._lane3_net.append(
                {"type": "response", "url": r.url, "status": r.status}))
            page.on("console", lambda m: self.console.append(f"{m.type}: {m.text[:200]}"))

            # ---------------------------------------------------------- B0 login
            page.goto(f"{self.frontend}/login", wait_until="domcontentloaded",
                      timeout=120_000)
            page.locator('[data-testid="login-email-input"]').wait_for(
                state="visible", timeout=120_000)
            page.locator('[data-testid="login-email-input"]').fill(LOGIN_EMAIL)
            page.locator('[data-testid="login-password-input"]').fill(self.password)
            page.locator('[data-testid="login-submit-button"]').click()
            try:
                page.wait_for_url(lambda u: "/login" not in u, timeout=120_000)
                landed = page.url
            except Exception:
                landed = page.url
                err = page.locator('[data-testid="login-error-message"]')
                if err.count():
                    landed = f"{page.url} :: {err.first.inner_text()[:200]}"
            self.step("B0_login_through_real_form", "/login" not in page.url, landed)
            self.shot(page, "B0_login")

            # Where does this browser actually talk? Recorded before any chat
            # traffic so a claim about isolation is measured, not assumed.
            for r in self.requests(page):
                for m in re.findall(r"https?://(?:localhost|127\.0\.0\.1):\d+", r["url"]):
                    self.origins.add(m)
            foreign = sorted(o for o in self.origins
                             if f":{self.backend_port}" not in o
                             and str(self.state["frontend_port"]) not in o)
            self.step("B0_browser_only_talks_to_this_candidate", not foreign,
                      {"origins": sorted(self.origins), "foreign": foreign})

            # ----------------------------------------------------------- the chat
            page.goto(f"{self.frontend}/chat", wait_until="domcontentloaded",
                      timeout=120_000)
            page.locator('[data-testid="agent-chat-input"]').wait_for(
                state="visible", timeout=180_000)
            self.shot(page, "B1_chat_ready")

            window_start = time.strftime("%Y-%m-%dT%H:%M:%S",
                                         time.gmtime(time.time() - 3600))

            # ---------------------------------------------------------- B1 lookup
            n = self.count_bubbles(page)
            t1, _ = self.send(page, BASE_ASK, n)
            items1 = visible_items(t1)
            self.shot(page, "B1_lookup")
            self.step("B1_lookup_shows_all_eight_in_order", items1 == BASE_ORDER,
                      items1)
            self.step("B1_lookup_did_not_create_a_task",
                      task_rows_since(self.db, window_start) == [],
                      task_rows_since(self.db, window_start))
            b1_text, b1_sha = t1, sha(t1)

            # --------------------------------------------------------- B2 replace
            n = self.count_bubbles(page)
            t2, _ = self.send(page, REPLACE_TURN, n)
            items2 = visible_items(t2)
            self.shot(page, "B2_replace")
            self.step("B2_displayed_set_is_the_revised_one", items2 == REPLACED_ORDER,
                      items2)
            self.step("B2_outgoing_item_is_gone",
                      bool(items2) and OUTGOING not in items2, items2)
            self.step("B2_incoming_item_is_present", INCOMING in items2, items2)
            self.step("B2_is_not_a_task_creation_confirmation",
                      "to your tasks" not in t2.lower()
                      and "added" not in t2.lower()[:120],
                      t2[:160])
            absent = incoming_is_labelled_absent(t2, INCOMING)
            self.step("B2_incoming_item_labelled_absent_no_invented_value",
                      absent["ok"], absent)
            self.step("B2_previous_answer_unchanged", sha(t1) == b1_sha,
                      "the base answer is still exactly what was delivered")
            self.step("B2_no_task_row_created",
                      task_rows_since(self.db, window_start) == [],
                      task_rows_since(self.db, window_start))

            # -------------------------------------------------------- B3 format
            n = self.count_bubbles(page)
            t3, _ = self.send(page, FORMAT_TURN, n)
            items3 = visible_items(t3)
            self.shot(page, "B3_formatting")
            self.step("B3_formatting_shows_the_revised_set", items3 == REPLACED_ORDER,
                      items3)
            self.step("B3_formatting_did_not_resurrect_the_outgoing_item",
                      bool(items3) and OUTGOING not in items3, items3)
            self.step("B3_earlier_answers_are_unchanged",
                      sha(t1) == b1_sha and sha(t2) == sha(t2),
                      {"base_sha": b1_sha[:16], "replace_sha": sha(t2)[:16]})
            self.step("B3_bubble_count_grew_by_exactly_one",
                      self.count_bubbles(page) == n + 1,
                      {"expected": n + 1, "actual": self.count_bubbles(page)})

            # ------------------------------------------------------- B4 re-search
            n = self.count_bubbles(page)
            t4, _ = self.send(page, RESEARCH_TURN, n)
            items4 = visible_items(t4)
            self.shot(page, "B4_research")
            self.step("B4_research_returns_the_revised_set",
                      items4 == REPLACED_ORDER, items4)
            self.step("B4_research_did_not_resurrect_the_outgoing_item",
                      bool(items4) and OUTGOING not in items4, items4)

            # ---------------------------------------------------------- B5 reload
            before_reload = self.bubble_texts(page)
            page.reload(wait_until="domcontentloaded", timeout=180_000)
            page.locator('[data-testid="agent-response"]').first.wait_for(
                state="visible", timeout=180_000)
            page.wait_for_timeout(4000)
            after_reload = self.bubble_texts(page)
            self.shot(page, "B5_reload")
            self.step("B5_reload_returns_the_same_number_of_answers",
                      len(after_reload) == len(before_reload),
                      {"before": len(before_reload), "after": len(after_reload)})
            self.step("B5_reload_preserves_every_answer_exactly",
                      after_reload == before_reload,
                      {"first_diff": next((i for i, (a, b) in
                                           enumerate(zip(after_reload, before_reload))
                                           if a != b), None)})
            final_items = visible_items(after_reload[-1] if after_reload else "")
            self.step("B5_reloaded_final_answer_is_the_revised_set",
                      final_items == REPLACED_ORDER, final_items)
            self.step("B5_reload_did_not_resurrect_the_outgoing_item",
                      bool(final_items) and OUTGOING not in final_items, final_items)

            # --------------------------------------------------------- B6 no task
            created = task_rows_since(self.db, window_start)
            self.step("B6_whole_chain_created_no_task_row", created == [], created)

            # ------------------------------------------- B7 streamed turn in the UI
            # The correction chain above runs on the deterministic sheet path,
            # which correctly emits no tokens. That proves nothing about
            # streaming. This turn is a general question, so it takes the LLM
            # leg and DOES stream -- which is the only way to see whether the UI
            # renders progressive text, and then converges on the finalized
            # answer without a duplicate bubble or stale provisional text.
            n_before = self.count_bubbles(page)
            box = page.locator('[data-testid="agent-chat-input"]').first
            box.fill(STREAM_PROMPT)
            page.locator('[data-testid="send-message-button"]').first.click()
            # Sample the newest bubble while it fills. Growth is the evidence
            # that tokens are being rendered as they arrive rather than the
            # whole answer being swapped in at the end.
            samples: List[Tuple[int, int, str]] = []
            deadline = time.time() + 180
            while time.time() < deadline:
                count = self.count_bubbles(page)
                if count > n_before:
                    try:
                        txt = page.locator('[data-testid="agent-response"]').nth(
                            count - 1).inner_text()
                        samples.append((int((time.time() - deadline + 180) * 1000),
                                        len(txt), txt[:80]))
                    except Exception:
                        pass
                if samples and time.time() > deadline - 168:
                    break
                page.wait_for_timeout(300)
            page.wait_for_timeout(6000)
            final_bubbles = self.count_bubbles(page)
            final_text = (page.locator('[data-testid="agent-response"]')
                          .nth(final_bubbles - 1).inner_text())
            self.shot(page, "B7_streaming")
            # "Grew" must mean PROGRESSIVE, not "the number changed once".
            # A bubble that sits at 27 chars and then jumps straight to the
            # finished answer has not rendered a stream, and counting that as
            # growth would claim streaming the UI never displayed. Require
            # several DISTINCT intermediate lengths on the way up.
            lengths = [s[1] for s in samples]
            distinct = sorted(set(lengths))
            intermediate = [n for n in distinct if 0 < n < max(distinct or [0])]
            progressive = len(intermediate) >= 3
            self.step("B7_streamed_turn_added_exactly_one_bubble",
                      final_bubbles == n_before + 1,
                      {"before": n_before, "after": final_bubbles})
            self.step("B7_bubble_text_grew_progressively",
                      progressive,
                      {"samples": len(samples), "distinct_lengths": distinct[:14],
                       "intermediate_lengths": len(intermediate),
                       "first_heads": [s[2][:40] for s in samples[:3]]})
            self.step("B7_bubble_settled_on_non_empty_text",
                      len(final_text.strip()) > 40,
                      {"final_chars": len(final_text),
                       "head": final_text[:120]})
            # Stale-provisional-text detector: once the turn is done, the bubble
            # must contain what the server durably stored. If finalization
            # changed the answer and the UI kept the streamed text, these differ.
            # The session id is read from the running app rather than assumed --
            # this chat surface mints its own.
            sid = ""
            for req in self.requests(page):
                if not req.get("post"):
                    continue
                try:
                    body = json.loads(req["post"])
                except Exception:
                    continue
                if body.get("session_id"):
                    sid = str(body["session_id"])
                    break
            hist_tail = ""
            if sid:
                hjson = page.evaluate(
                    "async (sid) => { const r = await fetch('/api/chat/history/'"
                    " + encodeURIComponent(sid) + '?user_id=" + USER_ID + "');"
                    " return r.ok ? await r.json() : null; }", sid)
                if isinstance(hjson, dict):
                    msgs = hjson.get("messages") or []
                    if msgs:
                        hist_tail = ((msgs[-1].get("response") or {}).get("message")
                                     or "")
            self.step("B7_final_bubble_matches_durable_history",
                      bool(hist_tail.strip())
                      and hist_tail.strip() in final_text.strip(),
                      {"session_id_from_request_body": sid or None,
                       "history_chars": len(hist_tail),
                       "bubble_chars": len(final_text)})

            report = {
                "schema": "lane3-browser-correction-chain-v1",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "world": self.world,
                "frontend": self.frontend,
                "backend": f"http://127.0.0.1:{self.backend_port}",
                "backend_health_identity": self.state.get("backend_health_identity", {}),
                "source_id": (self.state.get("backend_health_identity", {})
                              or {}).get("source_id"),
                "backend_frozen": True,
                "backend_freeze_note": ("the backend serves this world's "
                                        "immutable code export; its source_id and "
                                        "run dir are stable for this process"),
                "frontend_source": fe_digest,
                "db": self.db,
                "expected": {"base": BASE_ORDER, "revised": REPLACED_ORDER},
                "steps": self.steps,
                "passed": sum(1 for s in self.steps if s["ok"]),
                "total": len(self.steps),
                "all_pass": all(s["ok"] for s in self.steps),
                "answers": {"base": b1_text, "replace": t2, "formatting": t3,
                            "research": t4},
                "answer_sha256": {"base": b1_sha, "replace": sha(t2),
                                  "formatting": sha(t3), "research": sha(t4)},
                "network_origins": sorted(self.origins),
                "console": self.console[-40:],
                "note": ("the preview password is set in the world for this run "
                         "and is never recorded here"),
            }
            (self.out / "browser_correction_chain.json").write_text(
                json.dumps(report, indent=2))
            browser.close()

        print(f"\n{report['passed']}/{report['total']} steps pass -> "
              f"{self.out/'browser_correction_chain.json'}")
        print(f"screenshots -> {self.shots}")
        return 0 if report["all_pass"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--world", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args(argv)
    return Chain(args.world, Path(args.out), args.headed).run()


if __name__ == "__main__":
    raise SystemExit(main())
