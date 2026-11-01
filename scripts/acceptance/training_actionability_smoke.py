#!/usr/bin/env python3
"""Unforced teaching-form smoke through the normal application.

Unlike the long journey harness, this does NOT use ``fill(force=True)`` or
mutate the DOM to open the optional fields. It dismisses onboarding with a
normal Escape, opens Training and its ``<details>`` with clicks, fills the
form (no force), submits, reloads, and reads the saved lesson back through the
app's own training-context route.

Outputs a JSON check receipt plus the serving identity observed during the run.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def _token(page) -> str:
    return page.evaluate(
        "localStorage.getItem('auth_token') || localStorage.getItem('token')")


def api(page, base: str, path: str):
    request = urllib.request.Request(
        f"{base}{path}", headers={"Authorization": f"Bearer {_token(page)}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode() or "{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default="http://127.0.0.1:3133")
    ap.add_argument("--api-base", default="http://127.0.0.1:8077")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    password = Path(args.password_file).read_text().strip()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    marker = f"actionability-smoke-{int(time.time())}"
    checks = []

    def record(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name, detail or "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(f"{args.frontend}/login", wait_until="domcontentloaded")
        page.get_by_test_id("login-email-input").fill("admin@example.com")
        page.get_by_test_id("login-password-input").fill(password)
        page.get_by_test_id("login-submit-button").click()
        page.wait_for_url("**/dashboard", timeout=45000)

        # Visible dismissal: wait for the onboarding dialog to mount, then
        # Escape (or click the visible backdrop). No sessionStorage shortcut.
        dialog = page.locator('[role="dialog"]')
        appeared = False
        try:
            dialog.first.wait_for(state="visible", timeout=15000)
            appeared = True
        except Exception:  # noqa: BLE001 — no onboarding for this session
            appeared = False
        if appeared:
            page.keyboard.press("Escape")
            try:
                dialog.first.wait_for(state="hidden", timeout=10000)
            except Exception:  # noqa: BLE001
                pass
        overlay_gone = not (dialog.count() and dialog.first.is_visible())
        record(
            "onboarding dismissed visibly",
            overlay_gone,
            {"appeared": appeared})

        agents = api(page, args.api_base, "/api/agents/")
        rows = agents if isinstance(agents, list) else agents.get("data", [])
        if not rows:
            record("an agent exists", False)
            browser.close()
            return 1
        agent_id = rows[-1]["id"]
        record("an agent exists", True, agent_id)

        page.goto(f"{args.frontend}/agents", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        page.get_by_test_id(f"agent-teach-button-{agent_id}").click()
        page.wait_for_url("**/canvas/**", timeout=30000)
        page.get_by_test_id("training-panel").wait_for(
            state="attached", timeout=30000)

        lesson_input = page.get_by_test_id("teach-lesson-input")
        if not lesson_input.is_visible():
            tab = page.locator('[data-testid="canvas-side-tab-training"]')
            if tab.count():
                tab.first.click()
                page.wait_for_timeout(800)
        lesson_input.wait_for(state="visible", timeout=30000)

        # Open the optional fields with a normal click on <summary>.
        details = page.get_by_test_id("teach-structured-fields")
        details.locator("summary").click()
        page.wait_for_timeout(300)
        font = page.get_by_test_id("teach-format-font")
        record("optional fields opened by click", font.is_visible())

        lesson = (
            f"{marker}: for quote summaries use Arial 11 with a bold header "
            "and cite the source workbook.")
        lesson_input.fill(lesson)  # no force
        page.get_by_test_id("teach-topic-input").fill("Summary formatting")
        font.fill("Arial")  # no force
        page.get_by_test_id("teach-format-size").fill("11")  # no force
        record("form filled without force", True)

        page.get_by_test_id("teach-submit").click()
        page.get_by_text("Lesson recorded", exact=False).wait_for(
            timeout=30000)
        record("lesson submitted", True)

        # Reload and read the saved lesson through the app's own route.
        canvas_id = page.url.split("/canvas/")[-1].split("?")[0]
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        context = api(
            page, args.api_base,
            f"/api/maturity/training/context?canvas_id={canvas_id}")
        points = context.get("teaching_points") or []
        saved = any(
            marker in str(point.get("lesson") or point.get("content") or point)
            for point in points)
        record("lesson survives reload", saved, {
            "canvas_id": canvas_id, "points": len(points)})

        try:
            health = json.loads(urllib.request.urlopen(
                f"{args.api_base}/health", timeout=10).read().decode())
            identity = health.get("identity") or {}
        except Exception as exc:  # noqa: BLE001
            identity = {"error": str(exc)[:200]}
        browser.close()

    result = {
        "schema": "atom-training-actionability-smoke-1",
        "marker": marker,
        "checks": checks,
        "passed": all(item["ok"] for item in checks),
        "serving_identity": identity,
        "unforced": True,
    }
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"],
                      "checks": len(checks)}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
