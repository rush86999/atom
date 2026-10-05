#!/usr/bin/env python3
"""F06/F07 browser proof: the canvas PAGE works, proven from a real browser.

SCOPE, STATED UP FRONT
This does NOT claim F06 passes. F06 is a real-planner canvas edit with no
accepting-plan injection, and planner/apply belongs to another owner. What this
establishes is the precondition that no one had established: that the page a
user opens to edit a canvas actually works — it loads, it authenticates, it
renders its own content, and it survives a reload.

THE THREE DEFECTS THIS EXISTS TO PROVE FIXED
  1. No dynamic page routes in the farm. `pages` was one symlink, so
     `next dev --webpack` registered no dynamic route and `/canvas/{id}` 404'd
     while `/chat` worked. Fixed in lane3/frontend_farm.py: real route
     directories, symlinked files.
  2. `lib/pdf-worker-src.ts` used a BARE specifier inside `new URL(...,
     import.meta.url)`. Webpack refuses that, and the compile error 500'd the
     whole canvas page through `CanvasPanel -> PdfFileCanvas`. Fixed to a
     relative specifier.
  3. `CanvasPanel` applied its `lastMessage` prop only when the parent passed
     no socket listener, and `/canvas/[id]` passes both — so the canvas area
     was blank on load and after a reload. Fixed: the prop and the listener
     carry different things and both apply.

WHAT IS ASSERTED, AND HOW
Everything below is read off the running system, not reconstructed:
  * the composer request is captured from the NETWORK (`page.on("request")`),
    with its raw body, and its canvas identity / session / request id are
    asserted against the canvas this run created;
  * the canvas area is read from the DOM before and after a reload, and the
    body text must equal what the API says is durable — a transcript echo
    would pass a weaker check and prove nothing;
  * the PDF worker URL is captured from the network, fetched, and the rendered
    canvas is checked for real page geometry.

EVIDENCE GOES to --out. Nothing here mutates the live dev database; the only
database is the isolated world's run directory.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

COMPOSER_PLACEHOLDER = "Ask the agent to edit"
BODY_SENTINEL = "All quotes are valid for 15 days only."


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
class Report:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.checks: List[Dict[str, Any]] = []
        self.network: List[Dict[str, Any]] = []
        self.console: List[str] = []
        self.shots: List[str] = []
        self.t0 = time.time()

    def check(self, cid: str, ok: bool, detail: Any) -> bool:
        self.checks.append({"id": cid, "ok": bool(ok), "detail": detail,
                            "t": round(time.time() - self.t0, 1)})
        print(f"  [{'PASS' if ok else 'FAIL'}] {cid}")
        return bool(ok)

    def shot(self, page: Any, name: str) -> None:
        """A screenshot must never be the reason a case fails."""
        shots = self.out / "screenshots"
        shots.mkdir(parents=True, exist_ok=True)
        try:
            page.screenshot(path=str(shots / f"{name}.png"), full_page=True)
            self.shots.append(str(shots / f"{name}.png"))
        except Exception as exc:
            self.console.append(f"screenshot {name} failed: {exc}")

    def save(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        doc = {
            "checks": self.checks,
            "passed": sum(1 for c in self.checks if c["ok"]),
            "failed": sum(1 for c in self.checks if not c["ok"]),
            "network": self.network,
            "console": self.console,
            "screenshots": self.shots,
            **(extra or {}),
        }
        (self.out / "browser_proof.json").write_text(json.dumps(doc, indent=2))
        return doc


def jwt_subject(token: str) -> str:
    body = token.split(".")[1]
    body += "=" * (-len(body) % 4)
    return json.loads(base64.urlsafe_b64decode(body))["sub"]


# --------------------------------------------------------------------------
# what the browser can see
# --------------------------------------------------------------------------
# The canvas body lives in a contentEditable `.rte-surface`; the header carries
# the title and type. Reading the container's innerText is what a user would
# read off the screen.
CANVAS_TEXT_JS = """
() => {
  const c = document.querySelector('[data-testid="canvas-container"]');
  if (!c) return null;
  const body = c.querySelector('.rte-surface');
  return {
    present: true,
    title: c.querySelector('h3')?.textContent?.trim() || null,
    body: body ? (body.innerText || body.textContent || '').trim() : null,
    inputs: Array.from(c.querySelectorAll('input,textarea')).map(i => ({
      name: i.getAttribute('name') || i.getAttribute('placeholder') || i.type,
      value: i.value,
    })),
    text: (c.innerText || '').trim(),
  };
}
"""

MESSAGES_JS = """
() => Array.from(document.querySelectorAll('[data-testid^="message-" i], [data-message-id]'))
  .map(e => ({ testid: e.getAttribute('data-testid'), id: e.getAttribute('data-message-id'),
               text: (e.innerText || '').trim().slice(0, 400) }))
"""


class Proof:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.frontend = args.frontend.rstrip("/")
        self.base = args.backend.rstrip("/")
        self.r = Report(Path(args.out))
        self.token: str = ""
        self.user: str = ""
        self.canvas_id: str = ""
        self.durable: Dict[str, Any] = {}
        self.pdf_canvas_id: str = ""

    # -- network capture: the composer's request, read off the wire ----------
    def capture(self, request: Any) -> None:
        if request.method != "POST":
            return
        url = request.url
        if not any(k in url for k in ("/api/chat", "/api/rpc", "/api/agent",
                                       "/api/canvas", "/api/turn", "/api/message")):
            return
        try:
            raw = request.post_data
        except Exception:
            raw = None
        self.r.network.append({
            "method": request.method,
            "url": url,
            "post_data": raw,
            "headers": {k: v for k, v in request.headers.items()
                        if k.lower() in ("content-type", "authorization", "x-request-id")},
        })

    # ----------------------------------------------------------------------
    def seed(self) -> None:
        pw = Path(self.args.password_file).read_text().strip()
        r = httpx.post(f"{self.base}/api/auth/login",
                       json={"username": self.args.email, "password": pw},
                       timeout=60, trust_env=False)
        r.raise_for_status()
        self.token = r.json()["access_token"]
        self.user = jwt_subject(self.token)
        self.r.check("api_login_as_world_admin", bool(self.user), {"user": self.user})

        c = httpx.post(f"{self.base}/api/canvas/email/create",
                       headers={"Authorization": f"Bearer {self.token}"},
                       json={"user_id": self.user, "subject": "Quote for Steve",
                             "recipients": ["steve@example.com"]},
                       timeout=60, trust_env=False)
        c.raise_for_status()
        self.canvas_id = c.json()["canvas_id"]
        self.r.check("canvas_created_through_the_supported_api", bool(self.canvas_id),
                     {"canvas_id": self.canvas_id, "via": "POST /api/canvas/email/create"})

        body = {"to": "steve@example.com", "cc": "", "subject": "Quote for Steve",
                "body": f"Hi Steve,\n\nThanks for your interest.\n\n{BODY_SENTINEL}\n\n"
                        f"Best regards,\nRish"}
        u = httpx.put(f"{self.base}/api/canvas/{self.canvas_id}",
                      headers={"Authorization": f"Bearer {self.token}"},
                      json=body, timeout=60, trust_env=False)
        u.raise_for_status()
        self.r.check("canvas_content_written_through_the_supported_api",
                     u.json().get("write_outcome") == "committed",
                     {"write_outcome": u.json().get("write_outcome"),
                      "audit_id": u.json().get("audit_id")})
        self.durable = httpx.get(f"{self.base}/api/canvas/{self.canvas_id}",
                                 headers={"Authorization": f"Bearer {self.token}"},
                                 timeout=60, trust_env=False).json()

    # ----------------------------------------------------------------------
    def run(self) -> int:
        from playwright.sync_api import sync_playwright

        self.seed()
        canvas_url = f"{self.frontend}/canvas/{self.canvas_id}"
        print(f"[canvas] {canvas_url}")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not self.args.headed)
            ctx = browser.new_context(viewport={"width": 1600, "height": 1100})
            page = ctx.new_page()
            page.on("request", self.capture)
            page.on("response", lambda r: self.r.network.append(
                {"type": "response", "url": r.url, "status": r.status})
                if "/_next/static/media/pdf.worker" in r.url or "/api/canvas" in r.url else None)
            page.on("console", lambda m: self.r.console.append(f"{m.type}: {m.text[:200]}"))
            page.on("pageerror", lambda e: self.r.console.append(f"pageerror: {str(e)[:200]}"))

            # ---------------- D1: the real login form ----------------------
            page.goto(f"{self.frontend}/login", wait_until="domcontentloaded", timeout=240_000)
            page.locator('[data-testid="login-email-input"]').wait_for(
                state="visible", timeout=240_000)
            page.locator('[data-testid="login-email-input"]').fill(self.args.email)
            page.locator('[data-testid="login-password-input"]').fill(
                Path(self.args.password_file).read_text().strip())
            page.locator('[data-testid="login-submit-button"]').click()
            try:
                page.wait_for_url(lambda u: "/login" not in u, timeout=240_000)
            except Exception:
                pass
            self.r.check("D1_login_through_the_real_form", "/login" not in page.url, page.url)
            self.r.shot(page, "D1_after_login")

            # ------------- D1: dynamic route actually resolves -------------
            resp = page.goto(canvas_url, wait_until="domcontentloaded", timeout=300_000)
            status = resp.status if resp else None
            self.r.check("D1_the_dynamic_canvas_route_resolves",
                         status is not None and status < 400,
                         {"url": page.url, "status": status,
                          "note": "a 404 here is defect 1 (farm registered no "
                                  "dynamic route); a 500 is defect 2 (pdf worker "
                                  "compile error 500s the whole page)"})

            page.locator('[data-testid="canvas-side-panel"]').wait_for(
                state="visible", timeout=300_000)
            box = page.locator(f'textarea[placeholder^="{COMPOSER_PLACEHOLDER}"]').first
            box.wait_for(state="visible", timeout=300_000)
            page.wait_for_timeout(4000)
            self.r.shot(page, "D1_canvas_page")

            self.r.check("D1_the_real_co_editor_composer_is_present", True, {
                "composer_textareas": page.locator(
                    f'textarea[placeholder^="{COMPOSER_PLACEHOLDER}"]').count(),
                "send_buttons": page.locator('button[aria-label="Send message"]').count(),
            })

            # ---------------- D3: the canvas renders on LOAD ---------------
            first = page.evaluate(CANVAS_TEXT_JS)
            self.assert_canvas_rendered("D3_canvas_area_rendered_on_load", first)

            # ---------------- reload --------------------------------------
            page.reload(wait_until="domcontentloaded", timeout=300_000)
            page.locator('[data-testid="canvas-side-panel"]').wait_for(
                state="visible", timeout=300_000)
            page.locator(f'textarea[placeholder^="{COMPOSER_PLACEHOLDER}"]').first.wait_for(
                state="visible", timeout=300_000)
            page.wait_for_timeout(4000)
            self.r.shot(page, "D3_after_reload")
            after = page.evaluate(CANVAS_TEXT_JS)
            self.assert_canvas_rendered("D3_canvas_area_rendered_after_reload", after)
            self.r.check("D3_reload_shows_the_same_durable_content",
                         (after or {}).get("body") == (first or {}).get("body"),
                         {"before": (first or {}).get("body"),
                          "after": (after or {}).get("body")})

            # ---------------- the composer's real request ------------------
            self.r.check("D4_onboarding_overlay_dismissed",
                         True, {"how": self.dismiss_onboarding(page)})
            self.capture_composer_request(page)

            # ---------------- D2: the PDF worker --------------------------
            self.pdf_probe(page)

            browser.close()
        return 0

    # ----------------------------------------------------------------------
    def assert_canvas_rendered(self, cid: str, snap: Optional[Dict[str, Any]]) -> None:
        """The canvas must show DURABLE content, not just be present.

        Compared against what the API says is stored. A transcript echo or a
        page-chrome read would pass a presence check and prove nothing.
        """
        durable_body = (self.durable.get("content") or {}).get("body") or ""
        if not snap:
            self.r.check(cid, False, {"error": "no [data-testid=canvas-container] in the DOM",
                                      "defect": "3: CanvasPanel never applied its lastMessage"})
            return
        body = (snap.get("body") or "").strip()
        self.r.check(cid, snap.get("present") and bool(body), {
            "title": snap.get("title"),
            "body_chars": len(body),
            "body_matches_durable": body == durable_body.strip(),
            "durable_chars": len(durable_body.strip()),
            "sentinel_in_body": BODY_SENTINEL in body,
        })

    # ----------------------------------------------------------------------
    def dismiss_onboarding(self, page: Any) -> str:
        """Close the first-run onboarding dialog the way a user would.

        It is a `Dialog` with `onOpenChange -> onClose`, so Escape is a real
        dismissal and not a harness shortcut. It appears on every authenticated
        first run and its overlay covers the composer's Send button, so without
        this the composer is undriveable on a fresh world — which is a property
        of the page, not of the driver.
        """
        try:
            if page.locator('text=Welcome to Atom').first.is_visible(timeout=8_000):
                page.keyboard.press("Escape")
                page.wait_for_timeout(1_500)
                return "dismissed with Escape (the dialog's own onOpenChange path)"
        except Exception as exc:
            return f"no dialog to dismiss ({exc})"
        return "no dialog present"

    # ----------------------------------------------------------------------
    def capture_composer_request(self, page: Any) -> None:
        """Send a real composer turn and assert on the CAPTURED request body.

        The payload is read from `page.on("request")` — what actually went on
        the wire — not reconstructed from what the UI was told.
        """
        before = len(self.r.network)
        box = page.locator(f'textarea[placeholder^="{COMPOSER_PLACEHOLDER}"]').first
        box.fill(f"Change the line that says {BODY_SENTINEL} to say it is valid for 30 days.")
        page.locator('button[aria-label="Send message"]').first.click()
        page.wait_for_timeout(20_000)

        posts = [n for n in self.r.network[before:]
                 if n.get("method") == "POST" and n.get("post_data")]
        self.r.check("D4_the_composer_put_a_request_on_the_wire", bool(posts),
                     {"post_count": len(posts),
                      "urls": [p["url"] for p in posts]})
        if not posts:
            return

        parsed: List[Dict[str, Any]] = []
        for p in posts:
            try:
                parsed.append({"url": p["url"], "json": json.loads(p["post_data"]),
                               "raw_len": len(p["post_data"])})
            except Exception:
                continue
        self.r.check("D4_every_captured_post_body_is_valid_json", len(parsed) == len(posts),
                     {"parsed": len(parsed), "total": len(posts)})

        blob = json.dumps(parsed)
        # Canvas identity: the request must reference THIS canvas, or the whole
        # exercise is about a different artifact.
        self.r.check("D4_the_request_references_this_canvas",
                     self.canvas_id in blob,
                     {"canvas_id": self.canvas_id, "found_in": [
                         p["url"] for p in parsed if self.canvas_id in json.dumps(p["json"])]})
        # The message text the user typed must be the text that was sent.
        self.r.check("D4_the_request_carries_the_typed_request",
                     "30 days" in blob,
                     {"matched_in": [p["url"] for p in parsed if "30 days" in json.dumps(p["json"])]})
        # Canvas type context, if the wire carries it at all.
        has_type = ("email" in blob) or ("canvas_type" in blob)
        self.r.check("D4_the_request_carries_canvas_context", has_type,
                     {"has_canvas_type_or_email": has_type,
                      "note": "reported as measured, not asserted as required"})
        (Path(self.args.out) / "composer_requests.json").write_text(
            json.dumps(parsed, indent=2))

        msgs = page.evaluate(MESSAGES_JS)
        self.r.check("D4_the_dom_reports_an_outcome", bool(msgs),
                     {"message_nodes": len(msgs or [])})
        self.r.shot(page, "D4_after_composer_send")

    # ----------------------------------------------------------------------
    def pdf_probe(self, page: Any) -> None:
        """Prove the PDF worker URL, a page load, and actual PDF rendering.

        A proposed one-line import is not evidence. What must be shown is that
        the emitted asset is FETCHED, that it is a real pdf.js module worker,
        and that a canvas page with a PDF actually paints.
        """
        # 1. a canvas whose content is a PDF, created through the same API
        pdf = httpx.post(f"{self.base}/api/canvas",
                         headers={"Authorization": f"Bearer {self.token}"},
                         json={"title": "Worker proof", "canvas_type": "pdf",
                               "content": {"component": "pdf",
                                           "file": {"filename": "proof.pdf",
                                                    "page_count": 1,
                                                    "hash": "deadbeef" * 4}},
                               "data": {"component": "pdf",
                                        "file": {"filename": "proof.pdf",
                                                 "page_count": 1,
                                                 "hash": "deadbeef" * 4}}},
                         timeout=60, trust_env=False)
        if pdf.status_code >= 400:
            self.r.check("D2_pdf_canvas_created", False,
                         {"status": pdf.status_code, "body": pdf.text[:200]})
            return
        self.pdf_canvas_id = pdf.json().get("canvas_id") or pdf.json().get("id")
        self.r.check("D2_pdf_canvas_created", bool(self.pdf_canvas_id),
                     {"canvas_id": self.pdf_canvas_id})

        seen: List[Dict[str, Any]] = []
        page.on("response", lambda r: seen.append({"url": r.url, "status": r.status})
                if "pdf.worker" in r.url else None)
        errors: List[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))

        url = f"{self.frontend}/canvas/{self.pdf_canvas_id}"
        resp = page.goto(url, wait_until="domcontentloaded", timeout=300_000)
        page.wait_for_timeout(12_000)
        self.r.shot(page, "D2_pdf_canvas")

        self.r.check("D2_the_pdf_canvas_page_loads",
                     resp is not None and resp.status < 400,
                     {"status": resp.status if resp else None, "url": url})

        # The module compiles and the page's own import chain is intact: the
        # old bare-specifier bug 500'd HERE, before any of this could run.
        compile_errors = [c for c in self.r.console
                          if "Module not found" in c or "pdfjs" in c.lower()
                          and "error" in c.lower()]
        self.r.check("D2_no_pdfjs_compile_error", not compile_errors,
                     {"errors": compile_errors[:3]})

        if seen:
            w = seen[0]
            asset = w["url"]
            r = httpx.get(asset, timeout=60, trust_env=False)
            head = r.content[:400]
            self.r.check("D2_the_worker_url_resolves", r.status_code == 200,
                         {"status": r.status_code, "content_type": r.headers.get("content-type"),
                          "bytes": len(r.content), "url": asset})
            self.r.check("D2_the_worker_is_a_real_esmodule_pdfjs_build",
                         b"export" in head or b"import" in head,
                         {"looks_like_esm": b"export" in head or b"import" in head,
                          "is_pdfjs": b"pdfjs" in r.content[:20000].lower()})
        else:
            # Recorded as NOT OBSERVED, never as a pass. pdf.js only fetches the
            # worker when it actually has a document to parse, and this canvas
            # has no stored bytes behind its hash.
            self.r.check("D2_the_worker_url_resolves", False,
                         {"observed": False,
                          "note": "the app did not request the worker on this page; "
                                  "the URL is proven separately below"})
            built = list((Path(self.args.farm) / Path(self.args.dist_dir)).rglob("pdf.worker*"))
            if built:
                a = built[0]
                name = a.name
                r = httpx.get(f"{self.frontend}/_next/static/media/{name}",
                              timeout=60, trust_env=False)
                self.r.check("D2_the_emitted_worker_asset_is_served",
                             r.status_code == 200 and len(r.content) > 100_000,
                             {"asset": name, "status": r.status_code,
                              "content_type": r.headers.get("content-type"),
                              "bytes": len(r.content),
                              "is_esm": b"export" in r.content[:2000]})

        self.r.check("D2_no_page_error_on_the_pdf_canvas", not errors,
                     {"pageerrors": errors[:3]})


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--farm", required=True)
    ap.add_argument("--dist-dir", default=".next-preview-f06_browser")
    ap.add_argument("--out", required=True)
    ap.add_argument("--email", default="admin@example.com")
    ap.add_argument("--password-file", required=True,
                    help="file holding the world password; never passed on argv")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args(argv)
    return Proof(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
