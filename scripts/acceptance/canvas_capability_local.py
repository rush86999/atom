#!/usr/bin/env python3
"""User-created canvas capability journey on an isolated local world.

Creates a blank canvas through the normal UI, attaches an existing employee,
installs a table capability manifest, binds a local CSV, calculates, edits with
readback, exports XLSX, reloads, and verifies the durable revision. The
assessment operation is deliberately not run here: it requires a pinned review
model (ATOM_REVIEW_MODEL), which this local candidate does not configure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def login(page, frontend: str, password: str) -> None:
    page.goto(f"{frontend}/login", wait_until="domcontentloaded")
    page.get_by_test_id("login-email-input").fill("admin@example.com")
    page.get_by_test_id("login-password-input").fill(password)
    page.get_by_test_id("login-submit-button").click()
    page.wait_for_url("**/dashboard", timeout=45000)
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed', '1')")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(1200)


def new_canvas(page, frontend: str, agent_id: str) -> str:
    page.goto(f"{frontend}/canvas", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.get_by_test_id("new-blank-canvas-button").click()
    page.wait_for_timeout(2500)
    page.locator(
        '[data-testid="add-agent-button"], '
        '[data-testid="banner-add-agent-button"]').first.click()
    page.wait_for_timeout(800)
    page.get_by_test_id(f"attach-agent-option-{agent_id}").click()
    page.get_by_test_id("canvas-capability-panel").wait_for(
        state="attached", timeout=60000)
    return page.url


def open_panel(page) -> None:
    panel = page.get_by_test_id("canvas-capability-panel")
    panel.wait_for(state="attached", timeout=60000)
    panel.get_by_role("button", name="Data operations").click()
    page.wait_for_timeout(400)


def configure(page, manifest: dict) -> str:
    open_panel(page)
    panel = page.get_by_test_id("canvas-capability-panel")
    if panel.get_by_test_id("capability-enable").count():
        panel.get_by_test_id("capability-enable").click()
        page.wait_for_timeout(1000)
    panel.get_by_test_id("capability-manifest").fill(
        json.dumps(manifest, indent=2))
    panel.get_by_test_id("capability-save-manifest").click()
    page.wait_for_timeout(1500)
    return panel.get_by_test_id("capability-effective").inner_text()


def bind(page, csv_path: Path) -> dict:
    panel = page.get_by_test_id("canvas-capability-panel")
    with page.expect_response(
            lambda r: "/capability/bind" in r.url
            and r.request.method == "POST", timeout=120000) as info:
        panel.locator('input[type="file"]').set_input_files(str(csv_path))
    response = info.value
    body = response.json()
    page.wait_for_timeout(1200)
    return {"status": response.status, "body": body}


def run_op(page, operation: str, ask: str) -> dict:
    panel = page.get_by_test_id("canvas-capability-panel")
    panel.get_by_test_id("capability-ask").fill(ask)
    with page.expect_response(
            lambda r: f"/capability/{operation}" in r.url
            and r.request.method == "POST", timeout=120000) as info:
        panel.get_by_test_id(f"capability-{operation}").click()
    response = info.value
    body = response.json()
    page.wait_for_timeout(500)
    text = panel.get_by_test_id("capability-result").inner_text()
    return {"status": response.status, "body": body, "text": text}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    password = Path(args.password_file).read_text().strip()
    csv_path = Path(args.csv).resolve()

    manifest = {
        "schema_version": 1,
        "base_component": "table",
        "operations": ["read", "select", "calculate", "edit", "export", "bind"],
        "data_binding": {
            "subject_field": "Ref",
            "measure_field": "Amount",
            "status_field": "Status",
        },
        "editable_fields": ["Amount", "Status"],
        "teaching_binding": {
            "agent_id": args.agent_id,
            "scope_id": "canvas-local-acceptance",
        },
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "task_policy": (
            "Approve Amount >= 100 when Status is Open; review lower amounts."),
        "outputs": ["xlsx"],
        "required_approvals": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)[:300]))
        login(page, args.frontend, password)
        url = new_canvas(page, args.frontend, args.agent_id)
        effective = configure(page, manifest)
        bound = bind(page, csv_path)
        before = run_op(page, "calculate", "sum Amount for all rows")
        before_total = (
            (before["body"].get("total_values") or {}).get("(unstated)")
            or before["body"].get("total")
            or "")

        panel = page.get_by_test_id("canvas-capability-panel")
        panel.get_by_test_id("capability-edit-row").fill("2")
        panel.get_by_test_id("capability-edit-column").fill("Amount")
        panel.get_by_test_id("capability-edit-value").fill("110")
        with page.expect_response(
                lambda r: "/capability/edit" in r.url
                and r.request.method == "POST", timeout=60000) as info:
            panel.get_by_test_id("capability-edit").click()
        edit_body = info.value.json()
        page.wait_for_timeout(600)
        after = run_op(page, "calculate", "sum Amount for all rows")
        after_total = (
            (after["body"].get("total_values") or {}).get("(unstated)")
            or after["body"].get("total")
            or "")

        with page.expect_download(timeout=90000) as download_info:
            panel.get_by_test_id("capability-export").click()
        download = download_info.value
        export_path = out / "canvas-export.xlsx"
        download.save_as(str(export_path))
        page.screenshot(path=str(out / "canvas-completed.png"), full_page=True)

        page.reload(wait_until="domcontentloaded")
        page.get_by_test_id("canvas-capability-panel").wait_for(
            state="attached", timeout=60000)
        revision_text = page.get_by_test_id(
            "capability-revision").inner_text()
        browser.close()

    import openpyxl

    workbook = openpyxl.load_workbook(export_path, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    record = {
        "schema": "atom-canvas-capability-local-1",
        "status": "passed",
        "canvas_url": url,
        "manifest": manifest,
        "effective": effective,
        "bind": bound,
        "before": {"total": before_total, "text": before["text"][:600]},
        "edit": {
            "status": info.value.status,
            "success": edit_body.get("success"),
            "edits": edit_body.get("edits"),
        },
        "after": {"total": after_total, "text": after["text"][:600]},
        "export": {
            "path": str(export_path),
            "bytes": export_path.stat().st_size,
            "sha256": hashlib.sha256(export_path.read_bytes()).hexdigest(),
            "rows": [list(row) for row in rows[:10]],
        },
        "reload_revision": revision_text,
        "page_errors": errors,
    }
    passed = (
        bound["status"] < 300
        and before_total == "290.00"
        and edit_body.get("success") is True
        and str((edit_body.get("edits") or [{}])[0].get("readback")) == "110"
        and after_total == "325.00"
        and export_path.stat().st_size > 1000
        and "4 rows" in revision_text
        and not errors
    )
    record["status"] = "passed" if passed else "failed"
    (out / "canvas.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
