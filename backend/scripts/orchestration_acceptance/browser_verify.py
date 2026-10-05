#!/usr/bin/env python3
"""Browser-level verification of the isolated preview stack.

WHY THIS EXISTS
The readiness plan requires that the app be verified where the USER touches
it -- the browser -- and it specifically forbids the failure mode this script
exists to catch:

    "A separate frontend port alone does not prove isolation."
    "Inspect actual browser network traffic, server process identity and
     opened database paths."                            (plan section 4)

Nothing in the existing acceptance harness touches a browser: there is no
Playwright, no `next dev`, and no `frontend-nextjs` reference anywhere in
scripts/orchestration_acceptance/. So the isolation claim has never been
tested at the layer where it matters. This script drives a real Chromium
against the preview frontend and records, per step:

  * every network request the page made, with the resolved backend origin, so
    "the browser talked to OUR backend" is an observation and not an inference
  * every WebSocket URL, because the WS client bypasses the Next dev server
    entirely (next.config.js deliberately does not rewrite /ws)
  * console errors and failed requests
  * a screenshot per step

It then drives the manual-test script from the plan (M01..) against the real
UI and reports what was actually visible.

AUTHENTICATION
Drives the REAL login form when a password is supplied (--password, or
ATOM_PREVIEW_PASSWORD in the environment; never taken from a file, never
logged, never written to the result JSON). Without one it seeds the app's own
client-side session (localStorage + the auth_token cookie that
middleware.ts reads) with a token minted by the app's own
scripts/workbook_read_replay.mint_token() -- i.e. the environment-owned test
authentication the plan calls for, using the app's own credential mechanism.
The user row is a byte-identical snapshot of the user's own dev database, so a
password that works in their normal app works here too.

Usage:
    browser_verify.py --step all
    browser_verify.py --step M01 --headed
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

ACC = REPO / "docs" / "architecture" / "orchestration_migration" / "acceptance"
SHOTS = ACC / "preview_browser"
DEFAULT_WORLD = "preview_v1"

# Ports the preview must never touch. The user's own stack lives here; if the
# browser ever reaches one of these, the preview is NOT isolated and every
# observation is void. This is the check the plan asks for by name.
FORBIDDEN_ORIGIN_PORTS = {3000: "user frontend", 8001: "user backend",
                          8000: "atom-saas backend"}


def load_stack(world: str) -> Dict[str, Any]:
    p = BACKEND / "data" / "acceptance_worlds" / world / "preview_stack.json"
    if not p.exists():
        sys.exit(f"no preview stack for world {world!r} (expected {p})")
    return json.loads(p.read_text())


def mint_world_token(run_dir: str) -> tuple[Optional[str], Optional[str]]:
    """Mint a token against THIS world's database, using the app's own code."""
    os.environ["DATABASE_URL"] = f"sqlite:///{run_dir}/data/atom.db"
    os.environ["ATOM_DATA_DIR"] = f"{run_dir}/data"
    os.environ.pop("BYOK_KEYS_FILE", None)
    from scripts.workbook_read_replay import mint_token
    return mint_token()


class Recorder:
    """Captures everything the browser actually did."""

    def __init__(self, expected_backend_port: int) -> None:
        self.expected_port = expected_backend_port
        self.requests: List[Dict[str, Any]] = []
        # request object -> its record, so attaching a status is O(1). The
        # previous linear rescan of self.requests per response is O(n^2) over a
        # long-running chat page and showed up as driver stalls.
        self._by_request: Dict[int, Dict[str, Any]] = {}
        self.websockets: List[Dict[str, Any]] = []
        self.console_errors: List[str] = []
        self.page_errors: List[str] = []
        self.failed: List[str] = []
        self.foreign_origin_hits: List[Dict[str, Any]] = []

    # -- playwright wiring ------------------------------------------------
    def attach(self, page: Any) -> None:
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_failed)
        page.on("console", self._on_console)
        page.on("pageerror", self._on_pageerror)
        page.on("websocket", self._on_ws)

    @staticmethod
    def _origin(url: str) -> str:
        m = re.match(r"^(https?|wss?)://([^/]+)", url or "")
        return m.group(2) if m else ""

    def _on_request(self, req: Any) -> None:
        url = req.url
        origin = self._origin(url)
        rec = {"method": req.method, "url": url[:400], "origin": origin,
               "resource_type": req.resource_type}
        self.requests.append(rec)
        try:
            self._by_request[id(req)] = rec
        except Exception:
            pass
        port = origin.rsplit(":", 1)[-1] if ":" in origin else ""
        if port.isdigit() and int(port) in FORBIDDEN_ORIGIN_PORTS:
            self.foreign_origin_hits.append(
                {"reason": f"browser reached {FORBIDDEN_ORIGIN_PORTS[int(port)]}",
                 **rec})

    def _on_response(self, resp: Any) -> None:
        rec = self._by_request.get(id(resp.request))
        if rec is not None and "status" not in rec:
            rec["status"] = resp.status

    def _on_failed(self, req: Any) -> None:
        self.failed.append(f"{req.method} {req.url[:200]} :: "
                           f"{getattr(req, 'failure', None)}")

    def _on_console(self, msg: Any) -> None:
        if msg.type == "error":
            self.console_errors.append(str(msg.text)[:300])

    def _on_pageerror(self, exc: Any) -> None:
        self.page_errors.append(str(exc)[:300])

    def _on_ws(self, ws: Any) -> None:
        self.websockets.append({"url": ws.url[:300],
                                "origin": self._origin(ws.url)})

    # -- reporting -------------------------------------------------------
    def backend_calls(self) -> List[Dict[str, Any]]:
        return [r for r in self.requests
                if r["origin"].endswith(f":{self.expected_port}")]

    def summary(self) -> Dict[str, Any]:
        ours = {r["origin"] for r in self.backend_calls()}
        return {
            "total_requests": len(self.requests),
            "requests_to_our_backend": len(self.backend_calls()),
            "our_backend_origins": sorted(ours),
            "websockets": self.websockets,
            "websocket_origins": sorted({w["origin"] for w in self.websockets}),
            "foreign_origin_hits": self.foreign_origin_hits,
            "isolated": not self.foreign_origin_hits,
            "console_errors": self.console_errors[:20],
            "page_errors": self.page_errors[:20],
            "failed_requests": self.failed[:20],
        }


def seed_session(page: Any, base: str, token: str, email: str = "admin@example.com") -> None:
    """Install the app's own client-side session before any app script runs.

    Mirrors frontend-nextjs/lib/backendAuth.ts persistBackendToken() exactly:
    localStorage auth_token/token/user_email plus the auth_token and
    next-auth.session-token cookies that middleware.ts reads. Setting the
    cookie is what lets the page render past the middleware redirect.
    """
    page.add_init_script(
        "(() => {"
        f"  const token = {json.dumps(token)};"
        f"  const email = {json.dumps(email)};"
        "  try {"
        "    localStorage.setItem('auth_token', token);"
        "    localStorage.setItem('token', token);"
        "    localStorage.setItem('user_email', email);"
        "    localStorage.removeItem('atom_explicit_logout');"
        "  } catch (e) {}"
        "})();"
    )
    # The cookie must be set on the frontend origin, so navigate there once
    # before injecting it.
    page.goto(f"{base}/login", wait_until="domcontentloaded")
    page.evaluate(
        "([token]) => {"
        "  document.cookie = 'auth_token=' + token + '; path=/; max-age=86400; SameSite=Lax';"
        "  document.cookie = 'next-auth.session-token=' + token + '; path=/; max-age=86400; SameSite=Lax';"
        "}",
        arg=[token],
    )


def ui_login(page: Any, base: str, email: str, password: str) -> Dict[str, Any]:
    """Drive the real login form. Used when a password is supplied."""
    out: Dict[str, Any] = {"attempted": True, "ok": False}
    page.goto(f"{base}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    try:
        page.fill('input[type="email"], input[name="email"], input[id*="email" i]',
                  email, timeout=15000)
        page.fill('input[type="password"]', password, timeout=15000)
        page.click('button[type="submit"]', timeout=15000)
        page.wait_for_timeout(6000)
        out["landed_url"] = page.url
        out["ok"] = "/login" not in page.url
        tok = page.evaluate("() => localStorage.getItem('auth_token')")
        out["token_present_after_login"] = bool(tok)
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:300]
    return out


BUSY_MARKERS = (
    "agent is thinking",
    "executing tool_planner",
    "processing step",
    "agent status: running",
    "agent status: pending",
)

# The transcript, not the whole page. An earlier version compared
# document.body.innerText, which never stabilises: the notification badge, the
# Agent Workspace panel and the artifact sidebar all poll on timers, so the
# "unchanged across N polls" test could never be satisfied and every step ran
# to its full timeout even though the answer had arrived in seconds. The app
# marks the transcript with data-testid="message-list"; only that subtree
# changes when a turn completes.
TRANSCRIPT_JS = """() => {
  const el = document.querySelector('[data-testid="message-list"]');
  return el ? el.innerText : (document.body.innerText || '');
}"""


def wait_for_assistant(page: Any, timeout_s: int = 300,
                       settle_polls: int = 3) -> Optional[str]:
    """Wait for a turn to settle and return the visible transcript text.

    Two things this deliberately does NOT do, both of which made an earlier
    version of this script lie or hang:

      * It does not block the thread with time.sleep(). The Playwright sync
        API multiplexes the browser over a pipe to a node driver; blocking the
        Python thread starves that transport and the driver dies with EPIPE
        mid-turn. Every wait goes through page.wait_for_timeout().

      * It does not match on the word "assistant" or "atom" to decide the turn
        finished. The sidebar renders a literal "ATOM" brand mark, so such a
        regex returns on the first poll -- before the answer exists -- and
        reports an unfinished turn as a pass.

    Completion is: no busy marker inside the transcript, and the transcript
    unchanged across `settle_polls` consecutive polls. That is a property of
    what the user can see, which is what the plan asks us to record.
    """
    end = time.time() + timeout_s
    prev = ""
    stable = 0
    last = ""
    while time.time() < end:
        page.wait_for_timeout(2000)
        try:
            txt = page.evaluate(TRANSCRIPT_JS)
        except Exception:
            txt = ""
        last = txt or ""
        busy = any(m in last.lower() for m in BUSY_MARKERS)
        if last and last == prev and not busy:
            stable += 1
            if stable >= settle_polls:
                return last
        else:
            stable = 0
        prev = last
    return last or None


def shoot(page: Any, name: str) -> str:
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = SHOTS / f"{name}.png"
    page.screenshot(path=str(p), full_page=True)
    return str(p.relative_to(REPO))


# The manual test script from the readiness plan, section 11. These run as ONE
# CONVERSATION, in this order, in a single session -- M03/M04/M07 are
# continuation semantics, and a continuation asserted across separate sessions
# is not a continuation at all.
#
# M02's ask is the frozen acceptance ask VERBATIM (acceptance/cases.json
# inputs.ask_verbatim), not a paraphrase and not the older TARGETS list from
# scripts/workbook_read_replay.py. The eight identities it names are the ones
# the frozen per_target expectations are written against.
SEQUENCE: List[Dict[str, Any]] = [
    {"id": "M01", "prompt": "In one sentence, what is a price list used for?",
     "expect": "relevant answer, no unintended task or action"},
    {"id": "M02",
     "prompt": ("find the prices of these 8 machines in Consolidated Price "
                "List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, "
                "SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16"),
     "expect": "eight ordered entries, honest ambiguity, readable evidence"},
    {"id": "M03", "prompt": "Make this easier to read",
     "expect": "new concise answer; prior answer unchanged"},
    {"id": "M04", "prompt": "Search again and show the same items",
     "expect": "new read; saved/live status truthful"},
    {"id": "M05", "prompt": "Use the factory price instead",
     "expect": "correct labeled values; no silent substitution"},
    {"id": "M06", "prompt": "Replace U-22 with U-38",
     "expect": "updated list without resurrecting old distractors"},
    {"id": "M07", "prompt": "What is the capital of France?",
     "expect": "unrelated question answered without losing the task"},
    {"id": "M08", "prompt": None,
     "expect": "reload: same final answers, artifact and evidence association"},
]

# Kept for --step <ID> single-step runs.
STEPS: Dict[str, Dict[str, Any]] = {s_["id"]: s_ for s_ in SEQUENCE}


def dismiss_first_run_modals(page: Any) -> Dict[str, Any]:
    """Clear anything standing between the user and the composer.

    A brand-new account lands on a "Welcome to Atom" onboarding wizard
    (role=dialog, aria-modal) whose scrim is `fixed inset-0`, so it sits OVER
    the chat composer: Playwright resolves the textarea, reports it visible and
    stable, then refuses the click because the modal intercepts pointer events.
    Every step of the sequence timed out on that click while the app itself was
    healthy (2026-09-29, candidate 79b2a41032c3).

    A real user dismisses it, so the driver does too: prefer a close control,
    otherwise walk the wizard's own Next button to the end. Returns what it did
    so the run records that the page was prepared rather than silently assumed.
    """
    out: Dict[str, Any] = {"attempted": True, "dismissed": [], "left_open": []}
    for _ in range(6):
        dlg = page.locator('[role="dialog"][aria-modal="true"]')
        if not dlg.count():
            break
        text = ""
        try:
            text = (dlg.first.inner_text() or "")[:80].replace("\n", " ")
        except Exception:
            pass
        clicked = False
        for sel in ('[aria-label="Close"]', 'button[data-state="closed"]',
                    'button:has-text("Skip")', 'button:has-text("Get started")',
                    'button:has-text("Finish")'):
            loc = dlg.first.locator(sel)
            if loc.count():
                try:
                    loc.first.click(timeout=4000)
                    out["dismissed"].append(text)
                    clicked = True
                    break
                except Exception:
                    continue
        if not clicked:
            nxt = dlg.first.locator('button:has-text("Next"), button:has-text("Continue")')
            if nxt.count():
                try:
                    nxt.first.click(timeout=4000)
                    clicked = True
                except Exception:
                    pass
        if not clicked:
            # No close and no Next: press Escape, which is what a user does.
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(600)
                if page.locator('[role="dialog"][aria-modal="true"]').count():
                    out["left_open"].append(text)
                    break
                out["dismissed"].append(text + " (via Escape)")
                continue
            except Exception:
                out["left_open"].append(text)
                break
        page.wait_for_timeout(700)
    try:
        page.wait_for_selector('[data-testid="agent-chat-input"]', state="visible",
                               timeout=15000)
    except Exception:
        pass
    out["composer_clickable"] = _composer_clickable(page)
    return out


def _composer_clickable(page: Any) -> bool:
    """Can the composer actually be clicked right now?"""
    loc = page.locator('[data-testid="agent-chat-input"]').first
    try:
        if not loc.count():
            return False
        loc.click(timeout=4000)
        return True
    except Exception:
        return False


def send_via_ui(page: Any, text: str) -> None:
    """Type into the chat composer and submit, the way a user does."""
    box = None
    # The app's own testids first, then generic fallbacks: driving the element
    # the app marks as its composer is more stable than guessing a selector.
    for sel in ('[data-testid="agent-chat-input"]', 'textarea',
                '[contenteditable="true"]',
                'input[placeholder*="message" i]'):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                box = loc
                break
        except Exception:
            continue
    if box is None:
        raise RuntimeError("no chat composer found on the page")
    box.click()
    try:
        box.fill(text, timeout=10000)
    except Exception:
        page.keyboard.type(text, delay=8)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1500)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default=DEFAULT_WORLD)
    ap.add_argument("--step", default="all")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--password", default=os.environ.get("ATOM_PREVIEW_PASSWORD", ""))
    ap.add_argument("--out", default=str(ACC / "preview_browser_results.json"))
    args = ap.parse_args(argv)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright not importable; use backend/venv314/bin/python")

    st = load_stack(args.world)
    fe = f"http://localhost:{st['frontend_port']}"
    be_port = st["backend_port"]
    token, user_id = mint_world_token(st["run_dir"])
    if not token:
        sys.exit("could not mint a token against the preview world")
    print(f"world={args.world} frontend={fe} backend=:{be_port} user={user_id}")

    results: Dict[str, Any] = {"world": args.world, "frontend": fe,
                               "backend_port": be_port, "steps": {}}
    wanted = list(STEPS) if args.step == "all" else [args.step]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        rec = Recorder(be_port)
        rec.attach(page)

        if args.password:
            print("auth: driving the real login form")
            results["login"] = ui_login(page, fe, "admin@example.com", args.password)
        else:
            print("auth: seeding the app's own client session with a "
                  "world-minted token (no password available)")
            results["login"] = {"attempted": False,
                                "method": "seeded session token",
                                "note": "login FORM not exercised; see report"}
            seed_session(page, fe, token)

        # One conversation, in order. The session id is created by the page
        # itself on first send and reused by the app (atom_chat_session_id),
        # so M03..M07 genuinely continue the same task.
        page.goto(f"{fe}/chat", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        results["first_run_modals"] = dismiss_first_run_modals(page)
        print(f"first-run modals: {results['first_run_modals']}")
        for spec in SEQUENCE:
            name = spec["id"]
            if args.step != "all" and name != args.step:
                continue
            step_rec: Dict[str, Any] = {"expect": spec["expect"]}
            print(f"\n=== {name}: {spec['prompt'] or '(reload)'} ===")
            t0 = time.time()
            try:
                if spec["prompt"] is None:
                    # A REAL browser reload, which is what the plan asks M08 to
                    # exercise: not a re-render and not an API refetch.
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_timeout(8000)
                else:
                    send_via_ui(page, spec["prompt"])
                text = wait_for_assistant(page, timeout_s=360)
                step_rec["visible_text"] = text or ""
                step_rec["screenshot"] = shoot(page, f"{args.world}_{name}")
                step_rec["ok"] = bool(text)
            except Exception as exc:
                step_rec["ok"] = False
                step_rec["error"] = f"{type(exc).__name__}: {exc}"[:400]
            step_rec["elapsed_s"] = round(time.time() - t0, 1)
            # A per-step network summary lets a later step be compared with an
            # earlier one (e.g. M03 must issue no new read where M04 must).
            step_rec["network"] = rec.summary()
            results["steps"][name] = step_rec
            print(f"  ok={step_rec.get('ok')} elapsed={step_rec['elapsed_s']}s "
                  f"foreign_origins={len(rec.foreign_origin_hits)} "
                  f"shot={step_rec.get('screenshot')}")

        results["final_network"] = rec.summary()
        Path(args.out).write_text(json.dumps(results, indent=2))
        print(f"\nwrote {args.out}")
        s = results["final_network"]
        print(f"requests={s['total_requests']} to_our_backend="
              f"{s['requests_to_our_backend']} websockets={s['websocket_origins']} "
              f"ISOLATED={s['isolated']}")
        for h in s["foreign_origin_hits"]:
            print("  FOREIGN:", h)
        ctx.close()
        browser.close()
    return 0 if results["final_network"]["isolated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
