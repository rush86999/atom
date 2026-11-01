#!/usr/bin/env python3
"""Guided deterministic-rule authoring through the ordinary canvas UI.

Creates a blank canvas, attaches an employee, binds a CSV, maps the subject /
measure / status fields, builds three decision rules with selects and inputs
(no manifest JSON), saves through the normal capability endpoint, assesses,
approves the exact assessment and reads the decisions.

The optional raw-manifest editor is never touched. The server's existing
manifest validator remains the authority: the script records its error if the
save is refused.
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


def open_capability(page) -> None:
    panel = page.get_by_test_id("canvas-capability-panel")
    toggle = panel.get_by_role("button", name="Data operations")
    try:
        toggle.click(timeout=5000)
    except Exception:  # noqa: BLE001 — the panel state is the source of truth
        pass
    if not panel.get_by_test_id("capability-guided-rules").is_visible():
        box = toggle.bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    panel.get_by_test_id("capability-guided-rules").wait_for(state="visible", timeout=30000)


def add_rule(panel, index: int, decision: str, basis: str, conditions: list[tuple[str, str, str]]) -> None:
    panel.get_by_test_id("capability-rule-add").click()
    panel.get_by_test_id(f"capability-rule-{index}-decision").select_option(decision)
    panel.get_by_test_id(f"capability-rule-{index}-basis").fill(basis)
    for condition_index, (field, op, value) in enumerate(conditions):
        if condition_index:
            panel.get_by_test_id(f"capability-rule-{index}-condition-add").click()
        prefix = f"capability-rule-{index}-condition-{condition_index}"
        panel.get_by_test_id(f"{prefix}-field").select_option(field)
        panel.get_by_test_id(f"{prefix}-op").select_option(op)
        if op not in ("blank", "not_blank"):
            panel.get_by_test_id(f"{prefix}-value").fill(value)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default="http://127.0.0.1:3130")
    ap.add_argument("--api-base", default="http://127.0.0.1:8071")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    password = Path(args.password_file).read_text().strip()
    csv_path = Path(args.csv).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name, detail or "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1700, "height": 1300})
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)[:250]))

        page.goto(f"{args.frontend}/login", wait_until="domcontentloaded")
        page.get_by_test_id("login-email-input").fill("admin@example.com")
        page.get_by_test_id("login-password-input").fill(password)
        page.get_by_test_id("login-submit-button").click()
        page.wait_for_url("**/dashboard", timeout=45000)
        record("welcome wizard completed by visible clicks", finish_welcome(page))

        page.goto(f"{args.frontend}/canvas", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        page.get_by_test_id("new-blank-canvas-button").click()
        page.wait_for_timeout(2200)
        page.locator(
            '[data-testid="add-agent-button"], '
            '[data-testid="banner-add-agent-button"]').first.click()
        page.wait_for_timeout(900)
        attach = page.get_by_test_id(f"attach-agent-option-{args.agent_id}")
        panel = page.get_by_test_id("canvas-capability-panel")
        try:
            attach.click(timeout=6000)
        except Exception:  # noqa: BLE001 — fall back to a normal pointer click
            pass
        try:
            panel.wait_for(state="attached", timeout=6000)
        except Exception:  # noqa: BLE001
            box = attach.bounding_box()
            if box:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        panel.wait_for(state="attached", timeout=60000)
        page.wait_for_timeout(1200)
        canvas_id = page.url.split("/canvas/")[-1].split("?")[0]
        record("blank canvas created through the UI", bool(canvas_id), page.url)

        if panel.get_by_test_id("capability-enable").count():
            panel.get_by_test_id("capability-enable").click()
            page.wait_for_timeout(1200)
        open_capability(page)
        record("capability panel opened", panel.get_by_test_id("capability-guided-rules").is_visible())

        with page.expect_response(
                lambda r: "/capability/bind" in r.url and r.request.method == "POST",
                timeout=120000) as bind_info:
            panel.locator('input[type="file"]').set_input_files(str(csv_path))
        bind_status = bind_info.value.status
        page.wait_for_timeout(1400)
        fields_text = panel.get_by_test_id("capability-guided-fields").inner_text()
        record("CSV bound through the panel", bind_status == 200 and "fields available" in fields_text, fields_text)

        panel.get_by_test_id("capability-guided-subject").select_option("Ref")
        panel.get_by_test_id("capability-guided-measure").select_option("Amount")
        panel.get_by_test_id("capability-guided-status").select_option("Status")
        panel.get_by_test_id("capability-guided-editable-Amount").check()
        panel.get_by_test_id("capability-guided-editable-Status").check()
        record("field mapping set with selects", True)

        add_rule(panel, 0, "DENY", "Closed records are denied.", [
            ("Status", "eq", "Closed"),
        ])
        add_rule(panel, 1, "APPROVE", "Open and Amount at least 100.", [
            ("Status", "eq", "Open"),
            ("Amount", "gte", "100"),
        ])
        add_rule(panel, 2, "REVIEW", "Open and Amount 50-99.", [
            ("Status", "eq", "Open"),
            ("Amount", "gte", "50"),
            ("Amount", "lte", "99"),
        ])
        record("three rules built without manifest JSON", True)

        panel.get_by_test_id("capability-guided-save").click()
        page.wait_for_timeout(1800)
        save_error = panel.get_by_test_id("capability-error").inner_text() if panel.get_by_test_id("capability-error").count() else None
        record("guided save accepted by the existing validator", save_error is None, save_error)
        effective = panel.get_by_test_id("capability-effective").inner_text()
        record("effective operations include assess and edit", "assess" in effective and "edit" in effective, effective)

        token = api_login(args.api_base, password)
        state = api_get(args.api_base, f"/api/canvas/{canvas_id}/capability", token)
        manifest = state.get("manifest") or {}
        record("manifest persisted deterministically",
               manifest.get("assessment_mode") == "deterministic"
               and len(manifest.get("decision_rules") or []) == 3
               and bool(str(manifest.get("task_policy") or "").strip()),
               {"decision_rules": len(manifest.get("decision_rules") or []),
                "task_policy": manifest.get("task_policy")})

        with page.expect_response(
                lambda r: "/capability/assess" in r.url and r.request.method == "POST",
                timeout=120000) as assess_info:
            panel.get_by_test_id("capability-assess").click()
        page.wait_for_timeout(800)
        assess = assess_info.value.json()
        decisions = {row.get("subject_id"): row.get("decision") for row in assess.get("assessments") or []}
        record("deterministic assess served",
               assess_info.value.status == 200
               and (assess.get("route") or {}).get("served_provider") == "deterministic",
               (assess.get("route") or {}).get("served_provider"))
        record("decisions match the guided rules",
               decisions == {"D-1": "APPROVE", "D-2": "REVIEW", "D-3": "DENY"}, decisions)

        panel.get_by_test_id("capability-assess-approve").click()
        page.wait_for_timeout(1000)
        authorized = panel.get_by_test_id("capability-assessment-state").inner_text()
        panel.get_by_test_id("capability-decisions").click()
        page.wait_for_timeout(800)
        decisions_text = panel.get_by_test_id("capability-decisions-result").inner_text()
        record("exact assessment approved and decisions used",
               "Authorized assessment" in authorized
               and "D-1: APPROVE" in decisions_text
               and "D-2: REVIEW" in decisions_text
               and "D-3: DENY" in decisions_text,
               decisions_text.replace("\n", " | "))
        page.screenshot(path=str(out / "guided-rules.png"), full_page=True)
        record("no page errors", not page_errors, page_errors)

        try:
            health = json.loads(urllib.request.urlopen(
                f"{args.api_base}/health", timeout=10).read().decode())
            identity = health.get("identity") or {}
        except Exception as exc:  # noqa: BLE001
            identity = {"error": str(exc)[:200]}
        browser.close()

    result = {
        "schema": "atom-guided-rule-authoring-smoke-1",
        "canvas_id": canvas_id,
        "checks": checks,
        "passed": all(item["ok"] for item in checks),
        "serving_identity": identity,
        "manifest": manifest,
        "assessments": decisions,
        "decisions_text": decisions_text,
        "authorized_text": authorized,
        "unforced": {
            "force_fill": False,
            "dom_mutation": False,
            "dispatch_event": False,
            "raw_manifest_editor_used": False,
        },
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "checks": len(checks)}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
