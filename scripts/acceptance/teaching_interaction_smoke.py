#!/usr/bin/env python3
"""Unforced teaching-form smoke through the normal application.

This is deliberately small: it does not run an assignment or touch the
capability panel. It proves an ordinary user can open Agents -> Teach, expand
the optional fields with a click, fill the form without ``force=True``, submit,
and read the lesson back after a reload.

No ``page.evaluate``, ``dispatch_event``, ``force=True``, coordinate click or
sessionStorage shortcut is used. The welcome wizard is completed with its
visible Next / Start Automating buttons.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def api_login(api_base: str, password: str) -> str:
    body = json.dumps({"username": "admin@example.com", "password": password}).encode()
    request = urllib.request.Request(
        f"{api_base}/api/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())["access_token"]


def api_get(api_base: str, path: str, token: str):
    request = urllib.request.Request(
        f"{api_base}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode() or "{}")


def finish_welcome(page) -> bool:
    """Complete the visible welcome wizard with normal clicks. Idempotent."""
    for _ in range(8):
        modal = page.locator('div[class*="z-50"]').filter(has_text="Welcome to Atom").last
        if modal.count() == 0 or not modal.is_visible():
            return True
        nxt = modal.get_by_role("button", name="Next", exact=True)
        if nxt.count() and nxt.first.is_visible():
            nxt.first.click()
            page.wait_for_timeout(650)
            continue
        start = modal.get_by_role("button", name="Start Automating", exact=True)
        if start.count() and start.first.is_visible():
            start.first.click()
            page.wait_for_timeout(800)
            continue
        return False
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default="http://127.0.0.1:3130")
    ap.add_argument("--api-base", default="http://127.0.0.1:8071")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    password = Path(args.password_file).read_text().strip()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    marker = f"unforced-teach-{int(time.time())}"
    checks: list[dict] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name, detail or "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1500, "height": 1200})
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)[:250]))

        page.goto(f"{args.frontend}/login", wait_until="domcontentloaded")
        page.get_by_test_id("login-email-input").fill("admin@example.com")
        page.get_by_test_id("login-password-input").fill(password)
        page.get_by_test_id("login-submit-button").click()
        page.wait_for_url("**/dashboard", timeout=45000)
        record("welcome wizard completed by visible clicks", finish_welcome(page))

        page.goto(f"{args.frontend}/agents", wait_until="domcontentloaded")
        guide = page.get_by_test_id("agent-guide-dismiss")
        if guide.count() and guide.is_visible():
            guide.click()
            page.wait_for_timeout(400)

        teach = page.locator('[data-testid^="agent-teach-button-"]').first
        teach.wait_for(state="visible", timeout=60000)
        agent_id = (teach.get_attribute("data-testid") or "").replace(
            "agent-teach-button-", "")
        record("an employee with a Teach action is visible", bool(agent_id), agent_id)
        teach.click()
        page.wait_for_url("**/canvas/**", timeout=30000)
        page.wait_for_timeout(1500)
        canvas_id = page.url.split("/canvas/")[-1].split("?")[0]
        record("Teach opens the employee canvas", bool(canvas_id), page.url)

        panel = page.get_by_test_id("training-panel")
        panel.wait_for(state="attached", timeout=30000)
        lesson_input = page.get_by_test_id("teach-lesson-input")
        if not lesson_input.is_visible():
            tab = page.get_by_test_id("canvas-side-tab-training")
            if tab.count():
                tab.click()
                page.wait_for_timeout(800)
        lesson_input.wait_for(state="visible", timeout=30000)
        record("training form is visible", lesson_input.is_visible())

        page.get_by_test_id("teach-structured-fields").locator("summary").click()
        page.wait_for_timeout(300)
        font = page.get_by_test_id("teach-format-font")
        record("optional fields open with an ordinary click", font.is_visible())

        lesson = (
            f"{marker}: for quote summaries use Arial 11 with a bold header "
            "and cite the source workbook."
        )
        lesson_input.fill(lesson)
        page.get_by_test_id("teach-topic-input").fill("Unforced summary formatting")
        font.fill("Arial")
        page.get_by_test_id("teach-format-size").fill("11")
        page.get_by_test_id("teach-format-headings").fill("Summary, Findings, Sources")
        page.get_by_test_id("teach-applies-document").check()
        record("form filled without force", True)

        page.get_by_test_id("teach-submit").click()
        page.get_by_text("Lesson recorded", exact=False).wait_for(timeout=30000)
        record("lesson submitted", True)
        page.screenshot(path=str(out / "teaching-recorded.png"), full_page=True)

        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        token = api_login(args.api_base, password)
        context = api_get(
            args.api_base,
            f"/api/maturity/training/context?canvas_id={canvas_id}",
            token,
        )
        points = context.get("teaching_points") or []
        saved = any(
            marker in str(point.get("lesson") or point.get("content") or point)
            for point in points
        )
        record("lesson survives reload", saved, {"canvas_id": canvas_id, "points": len(points)})
        record("no page errors", not page_errors, page_errors)

        try:
            health = json.loads(urllib.request.urlopen(
                f"{args.api_base}/health", timeout=10).read().decode())
            identity = health.get("identity") or {}
        except Exception as exc:  # noqa: BLE001
            identity = {"error": str(exc)[:200]}
        browser.close()

    result = {
        "schema": "atom-teaching-interaction-smoke-1",
        "marker": marker,
        "agent_id": agent_id,
        "canvas_id": canvas_id,
        "checks": checks,
        "passed": all(item["ok"] for item in checks),
        "serving_identity": identity,
        "unforced": True,
        "interactions": {
            "force_fill": False,
            "dom_mutation": False,
            "dispatch_event": False,
            "session_storage_shortcut": False,
            "welcome_wizard": "visible Next / Start Automating clicks",
        },
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "checks": len(checks)}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
