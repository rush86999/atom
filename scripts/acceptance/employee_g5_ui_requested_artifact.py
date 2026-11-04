#!/usr/bin/env python3
"""Employee-decided quote-document journey through the normal UI.

The user uploads the authorized price book, selects it, asks the employee to
prepare the customer quote document, and requests DOCX output through the
ordinary Assignments form. The harness supplies no line items, executable
steps, formulas, final rows or plans: it records the actual /from-objective
request, binds every assertion to the returned run, waits for the employee's
own evidence reads and typed work request, and verifies the artifact bytes
against the durable calculation receipt.

Usage (app already launched on the given base/api):
  python scripts/acceptance/employee_g5_ui_requested_artifact.py \
    --base http://127.0.0.1:3136 --api http://127.0.0.1:8085 \
    --out /private/tmp/g5-ui-requested-artifact
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from playwright.sync_api import sync_playwright

OBJECTIVE = (
    "Prepare the customer quote document from the authorized price list, "
    "using the taught commercial terms")
TEACHING_TERMS = {
    "currency": "USD",
    "freight": "20.00",
    "tax_basis": "none",
}
# Independent arithmetic over the uploaded rows, not a supplied total.
EXPECTED_LINE_NETS = {"A": "200.00", "B": "150.00"}
EXPECTED_TOTAL = "370.00"


def _api_token(api: str, password: str) -> str:
    response = requests.post(
        api + "/api/auth/login",
        json={"username": "admin@example.com", "password": password},
        timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def _assignment(api: str, token: str, run_id: str) -> Dict[str, Any]:
    response = requests.get(
        api + f"/api/assignments/{run_id}",
        headers={"Authorization": f"Bearer {token}"}, timeout=30)
    response.raise_for_status()
    return response.json()


def _record(body: Dict[str, Any]) -> Dict[str, Any]:
    container = body.get("assignment")
    if not isinstance(container, dict):
        return {}
    nested = container.get("assignment")
    return nested if isinstance(nested, dict) else container


def _docx_text(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    return text


def _durable_assignment(db: str, run_id: str) -> Dict[str, Any]:
    """Read the authoritative task record without modifying the world."""
    import sqlite3

    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "select parameters from goal_runs where id = ?",
            (run_id,)).fetchone()
    finally:
        connection.close()
    if not row:
        return {}
    parameters = json.loads(row[0] or "{}")
    lifecycle = parameters.get("task_lifecycle") or {}
    return lifecycle.get("assignment") or {}


def _artifact_step(assignment: Dict[str, Any]) -> Dict[str, Any]:
    for step in assignment.get("steps") or []:
        if step.get("adapter") in (
                "artifact.document", "artifact.presentation"):
            return step
    return {}


def _calculation_step(assignment: Dict[str, Any],
                      adapter: str) -> Dict[str, Any]:
    for step in assignment.get("steps") or []:
        if step.get("adapter") == adapter:
            return step
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3136")
    parser.add_argument("--api", default="http://127.0.0.1:8085")
    parser.add_argument("--password", default="G5Browser-2026!")
    parser.add_argument(
        "--fixtures", default="/private/tmp/atom-g5-fixtures")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--db", default="",
        help="world atom.db used to read the authoritative task record")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fixtures = Path(args.fixtures)
    token = _api_token(args.api, args.password)
    health = requests.get(args.api + "/health", timeout=30)
    health.raise_for_status()
    capture: Dict[str, Any] = {
        "objective": OBJECTIVE,
        "taught_terms": TEACHING_TERMS,
        "line_items_supplied": False,
        "serving_identity": health.json(),
        "request": None,
        "response_status": None,
        "run_id": None,
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        page.add_init_script(
            "sessionStorage.setItem('atom.onboarding.dismissed','1')")

        def sign_in() -> None:
            page.goto(
                args.base + "/login", wait_until="networkidle", timeout=90000)
            if "/login" in page.url:
                page.fill(
                    '[data-testid="login-email-input"]', "admin@example.com")
                page.fill(
                    '[data-testid="login-password-input"]', args.password)
                page.locator(
                    '[data-testid="login-submit-button"]').click()
                page.wait_for_timeout(6000)
            page.goto(
                args.base + "/assignments", wait_until="networkidle",
                timeout=90000)
            page.get_by_test_id("assignment-start").wait_for(timeout=60000)

        sign_in()
        page.get_by_test_id("assignment-source-upload").set_input_files(
            str(fixtures / "price-book.xlsx"))
        page.wait_for_timeout(4000)
        page.get_by_test_id(
            "assignment-employee-decides-checkbox").check()
        page.wait_for_timeout(800)
        page.get_by_test_id("assignment-objective-input").fill(OBJECTIVE)
        checklist = page.get_by_test_id("assignment-source-checklist")
        selected = 0
        for label in checklist.locator("label").all():
            checkbox = label.locator("input")
            checked = checkbox.is_checked()
            if "price-book" in label.inner_text():
                if not checked:
                    checkbox.check()
                selected += 1
            elif checked:
                checkbox.uncheck()
        page.get_by_test_id("assignment-teaching-terms-input").fill(
            json.dumps(TEACHING_TERMS))
        page.get_by_test_id("assignment-deliverable-kind").select_option(
            "document")
        page.wait_for_timeout(400)
        page.screenshot(path=str(out / "start-form.png"), full_page=True)
        capture["selected_source_count"] = selected

        try:
            with page.expect_response(
                    lambda response: (
                        "/api/assignments/from-objective" in response.url
                        and response.request.method == "POST"),
                    timeout=300000) as response_info:
                page.get_by_test_id("assignment-start-button").click()
            response = response_info.value
        except Exception as exc:  # noqa: BLE001 — capture transport failure
            capture["transport_error"] = f"{type(exc).__name__}: {exc}"
            (out / "capture.json").write_text(
                json.dumps(capture, indent=1, default=str) + "\n")
            page.screenshot(
                path=str(out / "start-failure.png"), full_page=True)
            browser.close()
            return 2

        capture["response_status"] = response.status
        try:
            request_body = json.loads(response.request.post_data or "{}")
        except (TypeError, ValueError):
            request_body = {}
        try:
            response_body = response.json()
        except Exception:  # noqa: BLE001
            response_body = {}
        capture["request"] = request_body
        capture["response"] = response_body
        run_id = str(response_body.get("run_id") or "")
        capture["run_id"] = run_id
        (out / "capture.json").write_text(
            json.dumps(capture, indent=1, default=str) + "\n")
        if response.status != 200 or not run_id:
            page.screenshot(
                path=str(out / "start-failure.png"), full_page=True)
            browser.close()
            return 2

        summary = page.get_by_test_id(f"assignment-summary-{run_id}")
        summary.wait_for(timeout=60000)
        summary.click()
        page.get_by_test_id("assignment-detail").wait_for(timeout=60000)

        deadline = time.time() + 600
        body: Dict[str, Any] = dict(response_body or {})
        while time.time() < deadline:
            try:
                body = _assignment(args.api, token, run_id)
            except Exception as exc:  # noqa: BLE001 — keep scoped response
                capture["poll_error"] = f"{type(exc).__name__}: {exc}"
                break
            assignment = _record(body)
            if str(assignment.get("status") or "") in (
                    "completed", "failed", "cancelled", "blocked"):
                break
            page.wait_for_timeout(2000)

        assignment = _record(body)
        page.wait_for_timeout(1500)
        detail_text = page.locator("body").inner_text()
        (out / "detail.txt").write_text(detail_text)
        page.screenshot(
            path=str(out / "exact-run-final.png"), full_page=True)

        job = body.get("employee_job") or {}
        criteria = job.get("criteria") or []
        outcome = job.get("business_outcome") or {}
        deliverable = (assignment.get("deliverables") or [{}])[0]
        artifact_step = _artifact_step(assignment)
        quote_step = _calculation_step(assignment, "quote.calculate")
        lines_step = _calculation_step(assignment, "quote.lines_from_rows")

        # Download through the normal UI control, then read the same bytes
        # over the API to compare identities.
        ui_bytes = b""
        ui_status: Optional[int] = None
        deliverable_id = str(deliverable.get("deliverable_id") or "")
        if deliverable_id:
            download_button = page.get_by_test_id(
                "assignment-download-"
                + "".join(
                    character if character.isalnum() else "-"
                    for character in deliverable_id.lower()
                ).strip("-"))
            try:
                with page.expect_download(timeout=120000) as download_info:
                    download_button.click()
                download = download_info.value
                ui_bytes = Path(download.path()).read_bytes()
                ui_status = 200
            except Exception as exc:  # noqa: BLE001
                capture["ui_download_error"] = (
                    f"{type(exc).__name__}: {exc}")
        api_bytes = b""
        api_status: Optional[int] = None
        if deliverable_id:
            download = requests.get(
                args.api + (
                    f"/api/assignments/{run_id}/deliverables/"
                    f"{deliverable_id}/download"),
                headers={"Authorization": f"Bearer {token}"}, timeout=60)
            api_status = download.status_code
            if download.status_code == 200:
                api_bytes = download.content

        chosen = ui_bytes or api_bytes
        if chosen:
            (out / "customer-quote.docx").write_bytes(chosen)
        artifact_sha = (
            hashlib.sha256(chosen).hexdigest() if chosen else None)
        artifact_text = _docx_text(chosen) if chosen else ""

        durable = _durable_assignment(args.db, run_id) if args.db else {}
        durable_steps = {
            str(step.get("step_id")): step
            for step in durable.get("steps") or []
        }
        durable_quote = durable_steps.get(
            str(quote_step.get("step_id") or "")) or {}
        durable_artifact = durable_steps.get(
            str(artifact_step.get("step_id") or "")) or {}
        quote_result = durable_quote.get("result") or {}
        receipt = quote_result.get("calculation_receipt") or {}
        receipt_rows = quote_result.get("rows") or []
        row_nets = {
            str(row.get("item_id")): str(row.get("net"))
            for row in receipt_rows if isinstance(row, dict)
        }
        # Independent arithmetic over the uploaded source rows.
        independent_total = (
            2 * 100.00  # item A: quantity 2 x price 100
            + 3 * 50.00  # item B: quantity 3 x price 50
            + 20.00  # taught freight
        )

        checks = {
            "captured_exact_run": bool(run_id)
            and body.get("run_id") == run_id,
            "request_has_no_line_items": (
                not (request_body.get("line_items")
                     or request_body.get("deliverables"))),
            "request_requests_document": str(
                request_body.get("requested_output") or "") == "document",
            "assignment_completed": assignment.get("status") == "completed",
            "artifact_after_verified_quote": bool(artifact_step)
            and artifact_step.get("depends_on") == [
                str(quote_step.get("step_id") or "")]
            and all(
                item.get("status") == "applied"
                for item in (lines_step, quote_step) if item),
            "artifact_from_results": bool(
                (durable_artifact.get("inputs") or {}).get(
                    "compose_from_results")),
            "artifact_applied": deliverable.get("status") == "applied",
            "artifact_criterion_met": any(
                item.get("kind") == "artifact_verified"
                and item.get("required") for item in criteria)
            and outcome.get("state") == "satisfied",
            "ui_download_ok": ui_status == 200,
            "api_download_ok": api_status == 200,
            "download_identity_matches": bool(ui_bytes) and ui_bytes
            == api_bytes,
            "artifact_sha_matches": bool(artifact_sha)
            and artifact_sha == deliverable.get("sha256"),
            "receipt_total_matches_independent_arithmetic": str(
                receipt.get("total")) == f"{independent_total:.2f}",
            "receipt_line_nets_match": row_nets == EXPECTED_LINE_NETS,
            "artifact_has_exact_total": EXPECTED_TOTAL in artifact_text,
            "artifact_uses_receipt_expression": str(
                quote_result.get("expression") or "") != ""
            and str(quote_result.get("expression") or "") in artifact_text,
            "artifact_has_both_lines": all(
                item in artifact_text for item in ("A", "B")),
            "artifact_has_source": "price-book.xlsx" in artifact_text,
            "artifact_has_human_labels": (
                "Unit price" in artifact_text
                and "item_id" not in artifact_text),
            "artifact_has_audit_section": "Audit" in artifact_text,
            "ui_shows_exact_run": OBJECTIVE in detail_text
            and "completed" in detail_text.lower(),
        }
        capture.update({
            "serving_identity_after": requests.get(
                args.api + "/health", timeout=30).json(),
            "final_run_id": body.get("run_id"),
            "assignment_status": assignment.get("status"),
            "artifact": deliverable,
            "artifact_sha256": artifact_sha,
            "artifact_text": artifact_text,
            "artifact_ui_sha256": (
                hashlib.sha256(ui_bytes).hexdigest() if ui_bytes else None),
            "artifact_api_sha256": (
                hashlib.sha256(api_bytes).hexdigest() if api_bytes else None),
            "receipt": receipt,
            "receipt_rows": receipt_rows,
            "durable_lineage": {
                "assignment_id": durable.get("assignment_id"),
                "plan_revision": durable.get("plan_revision"),
                "task_version": durable.get("task_version"),
                "provenance": durable.get("provenance") or {},
                "deliverable": (durable.get("deliverables") or [{}])[0],
                "steps": [{
                    "step_id": step.get("step_id"),
                    "adapter": step.get("adapter"),
                    "status": step.get("status"),
                    "operation_id": step.get("operation_id"),
                    "depends_on": step.get("depends_on"),
                    "result_summary": (step.get("result") or {}).get(
                        "summary"),
                    "result_value": (step.get("result") or {}).get("value"),
                } for step in durable.get("steps") or []],
            },
            "independent_total": f"{independent_total:.2f}",
            "steps": [{
                "step_id": step.get("step_id"),
                "adapter": step.get("adapter"),
                "status": step.get("status"),
                "depends_on": step.get("depends_on"),
                "result_value": (step.get("result") or {}).get("value"),
            } for step in assignment.get("steps") or []],
            "adaptive_rounds": (body.get("employee_job") or {}).get(
                "adaptive_rounds") or response_body.get(
                    "adaptive_rounds") or [],
            "criteria": criteria,
            "business_outcome": outcome,
            "checks": checks,
            "all_checks_passed": all(checks.values()),
        })
        (out / "final.json").write_text(
            json.dumps(capture, indent=1, default=str) + "\n")
        print(json.dumps(checks, indent=1))
        browser.close()
    return 0 if capture["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
