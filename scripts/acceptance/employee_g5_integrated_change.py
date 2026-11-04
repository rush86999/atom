#!/usr/bin/env python3
"""Integrated employee artifact + real source-version change campaign.

Phase 1 runs the ordinary Assignments UI: the user uploads the price book,
selects it, asks the employee for a customer quote document, and receives a
DOCX derived from the employee's typed quote calculation.

Phase 2 changes a real source value: a revised workbook version is uploaded
through the normal document-ingestion route and authorized on the same run.
The employee's adaptation contract is asked again; the model chooses the
supported quote work, the compiler adds new steps under a new plan revision,
and the affected artifact is re-rendered. The earlier quote/artifact and an
unrelated authorized note keep their operation ids and results.

Usage (app already launched):
  python scripts/acceptance/employee_g5_integrated_change.py \
    --base http://127.0.0.1:3136 --api http://127.0.0.1:8085 \
    --db backend/data/acceptance_worlds/<world>/atom.db \
    --out /private/tmp/g5-integrated-change
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from typing import Any, Dict

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


def _durable(db: str, run_id: str) -> Dict[str, Any]:
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
    lifecycle = json.loads(row[0] or "{}").get("task_lifecycle") or {}
    return lifecycle.get("assignment") or {}


def _write_revised_workbook(path: Path) -> None:
    """The supplier's revised price list (A 100 -> 120, B 50 -> 55)."""
    import openpyxl

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Prices"
    sheet.append(["Item", "Qty", "Price", "Currency"])
    sheet.append(["A", 2, 120, "USD"])
    sheet.append(["B", 3, 55, "USD"])
    book.save(path)


def _wait(api: str, token: str, run_id: str,
          initial: Dict[str, Any], timeout: float = 600.0) -> Dict[str, Any]:
    deadline = time.time() + timeout
    body = dict(initial or {})
    while time.time() < deadline:
        try:
            body = _assignment(api, token, run_id)
        except Exception:  # noqa: BLE001 — keep the scoped response
            break
        status = str(_record(body).get("status") or "")
        if status in ("completed", "failed", "cancelled", "blocked",
                      "waiting"):
            break
        time.sleep(2)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3136")
    parser.add_argument("--api", default="http://127.0.0.1:8085")
    parser.add_argument("--password", default="G5Browser-2026!")
    parser.add_argument(
        "--fixtures", default="/private/tmp/atom-g5-fixtures")
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fixtures = Path(args.fixtures)
    token = _api_token(args.api, args.password)
    headers = {"Authorization": f"Bearer {token}"}
    revised = out / "price-book-v2.xlsx"
    _write_revised_workbook(revised)
    capture: Dict[str, Any] = {
        "objective": OBJECTIVE,
        "taught_terms": TEACHING_TERMS,
        "line_items_supplied": False,
        "phase1": {},
        "phase2": {},
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        page.add_init_script(
            "sessionStorage.setItem('atom.onboarding.dismissed','1')")
        page.goto(args.base + "/login", wait_until="networkidle", timeout=90000)
        if "/login" in page.url:
            page.fill(
                '[data-testid="login-email-input"]', "admin@example.com")
            page.fill(
                '[data-testid="login-password-input"]', args.password)
            page.locator('[data-testid="login-submit-button"]').click()
            page.wait_for_timeout(6000)
        page.goto(
            args.base + "/assignments", wait_until="networkidle",
            timeout=90000)
        page.get_by_test_id("assignment-start").wait_for(timeout=60000)
        page.get_by_test_id("assignment-source-upload").set_input_files(
            str(fixtures / "price-book.xlsx"))
        page.wait_for_timeout(4000)
        page.get_by_test_id(
            "assignment-employee-decides-checkbox").check()
        page.wait_for_timeout(800)
        page.get_by_test_id("assignment-objective-input").fill(OBJECTIVE)
        checklist = page.get_by_test_id("assignment-source-checklist")
        for label in checklist.locator("label").all():
            checkbox = label.locator("input")
            if "price-book" in label.inner_text():
                if not checkbox.is_checked():
                    checkbox.check()
            elif checkbox.is_checked():
                checkbox.uncheck()
        page.get_by_test_id("assignment-teaching-terms-input").fill(
            json.dumps(TEACHING_TERMS))
        page.get_by_test_id("assignment-deliverable-kind").select_option(
            "document")
        page.screenshot(path=str(out / "start-form.png"), full_page=True)

        with page.expect_response(
                lambda response: (
                    "/api/assignments/from-objective" in response.url
                    and response.request.method == "POST"),
                timeout=300000) as response_info:
            page.get_by_test_id("assignment-start-button").click()
        response = response_info.value
        request_body = json.loads(response.request.post_data or "{}")
        response_body = response.json()
        run_id = str(response_body.get("run_id") or "")
        capture["phase1"].update({
            "request_status": response.status,
            "request": request_body,
            "run_id": run_id,
            "response": response_body,
        })
        (out / "capture.json").write_text(
            json.dumps(capture, indent=1, default=str) + "\n")
        if response.status != 200 or not run_id:
            browser.close()
            return 2

        summary = page.get_by_test_id(f"assignment-summary-{run_id}")
        summary.wait_for(timeout=60000)
        summary.click()
        page.get_by_test_id("assignment-detail").wait_for(timeout=60000)

        first = _wait(args.api, token, run_id, response_body)
        first_assignment = _record(first)
        page.wait_for_timeout(1200)
        (out / "detail-phase1.txt").write_text(page.locator("body").inner_text())
        page.screenshot(
            path=str(out / "exact-run-phase1.png"), full_page=True)
        first_durable = _durable(args.db, run_id)
        first_steps = {
            str(step.get("step_id")): step
            for step in first_durable.get("steps") or []
        }
        first_calc = next(
            step for step in first_steps.values()
            if step.get("adapter") == "quote.calculate")
        first_deliverable = (first_durable.get("deliverables") or [{}])[0]
        first_quote = str((first_calc.get("result") or {}).get("value") or "")
        first_operation = first_calc.get("operation_id")
        first_artifact_path = Path(
            str(first_deliverable.get("artifact_path") or ""))
        first_sha = hashlib.sha256(
            first_artifact_path.read_bytes()).hexdigest() if (
                first_artifact_path.is_file()) else None
        first_text = _docx_text(first_artifact_path.read_bytes()) if (
            first_artifact_path.is_file()) else ""
        capture["phase1"].update({
            "status": first_assignment.get("status"),
            "quote_total": first_quote,
            "quote_operation": first_operation,
            "plan_revision": first_durable.get("plan_revision"),
            "artifact_sha256": first_sha,
            "artifact_text": first_text,
            "steps": [{
                "step_id": step.get("step_id"),
                "adapter": step.get("adapter"),
                "status": step.get("status"),
                "operation_id": step.get("operation_id"),
                "result_value": (step.get("result") or {}).get("value"),
            } for step in first_steps.values()],
        })

        # An unrelated authorized note must keep its operation/result across
        # the later change.
        note = out / "delivery-note.txt"
        note.write_text(
            "Carrier delivery note DN-77: leave this branch intact.\n")
        with note.open("rb") as handle:
            upload = requests.post(
                args.api + "/api/documents/upload",
                headers=headers,
                files={"file": ("delivery-note.txt", handle, "text/plain")},
                timeout=120)
        upload.raise_for_status()
        note_upload = upload.json()
        note_data = (
            note_upload.get("data")
            if isinstance(note_upload.get("data"), dict) else note_upload)
        note_metadata = note_upload.get("metadata") or {}
        note_document_id = str(
            note_upload.get("id") or note_data.get("document_id") or "")
        note_added = requests.post(
            args.api + f"/api/assignments/{run_id}/sources",
            headers=headers,
            json={
                "source": {
                    "kind": "document",
                    "document_id": note_document_id,
                },
                "reason": "unrelated delivery note authorized for this job",
            },
            timeout=300)
        note_added.raise_for_status()
        note_body = _wait(
            args.api, token, run_id, _assignment(args.api, token, run_id))
        note_durable = _durable(args.db, run_id)
        note_step = next(
            (step for step in note_durable.get("steps") or []
             if step.get("step_id") == "source-2"), {})
        note_operation = note_step.get("operation_id")
        note_result = dict(note_step.get("result") or {})
        assert note_operation, note_step

        # The real change: upload and authorize the revised workbook version.
        with revised.open("rb") as handle:
            revised_upload = requests.post(
                args.api + "/api/documents/upload",
                headers=headers,
                files={
                    "file": (
                        "price-book.xlsx", handle,
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet")},
                timeout=120)
        revised_upload.raise_for_status()
        revised_body = revised_upload.json()
        sources_response = requests.get(
            args.api + "/api/assignments/sources",
            headers=headers,
            params={"query": "price-book.xlsx"},
            timeout=60)
        sources_response.raise_for_status()
        revised_source = next(
            item for item in sources_response.json()
            if str(item.get("dataset_name") or "")
            == "upload_price_book__prices")
        change = requests.post(
            args.api + f"/api/assignments/{run_id}/sources",
            headers=headers,
            json={
                "source": {
                    "kind": "workbook",
                    "dataset_name": revised_source.get("dataset_name"),
                    "sheet": revised_source.get("sheet"),
                    "source_version": revised_source.get("source_version"),
                },
                "reason": "supplier published a revised price version",
            },
            timeout=600)
        change.raise_for_status()
        change_body = change.json()
        second = _wait(
            args.api, token, run_id, _assignment(args.api, token, run_id))
        second_assignment = _record(second)
        second_durable = _durable(args.db, run_id)
        page.wait_for_timeout(1200)
        (out / "detail-phase2.txt").write_text(page.locator("body").inner_text())
        page.screenshot(
            path=str(out / "exact-run-phase2.png"), full_page=True)
        steps = {
            str(step.get("step_id")): step
            for step in second_durable.get("steps") or []
        }
        calcs = [
            step for step in steps.values()
            if step.get("adapter") == "quote.calculate"]
        second_calc = next(
            (step for step in calcs
             if step.get("step_id") != first_calc.get("step_id")), {})
        first_after = steps.get(str(first_calc.get("step_id")), {})
        second_quote = str((second_calc.get("result") or {}).get("value") or "")
        deliverable = (second_durable.get("deliverables") or [{}])[0]
        artifact_path = Path(str(deliverable.get("artifact_path") or ""))
        artifact_sha = hashlib.sha256(
            artifact_path.read_bytes()).hexdigest() if (
                artifact_path.is_file()) else None
        artifact_text = _docx_text(artifact_path.read_bytes()) if (
            artifact_path.is_file()) else ""
        (out / "customer-quote-v2.docx").write_bytes(
            artifact_path.read_bytes()) if artifact_path.is_file() else None
        versioned_read = next(
            (step for step in steps.values()
             if step.get("step_id") not in ("source-1", "source-2")
             and str((step.get("result") or {}).get("source_version") or "")
             == str(revised_source.get("source_version") or "")), {})
        note_after = steps.get("source-2", {})
        rounds = change_body.get("reassessment_rounds") or []

        checks = {
            "phase1_completed": first_assignment.get("status") == "completed",
            "phase1_quote_370": first_quote == "370.00",
            "phase1_artifact_has_370": "370.00" in first_text,
            "phase1_no_line_items_supplied": not request_body.get("line_items"),
            "revised_version_authorized": versioned_read.get("status")
            == "applied",
            "revised_version_identity_persisted": str(
                ((versioned_read.get("inputs") or {}).get(
                    "resource_binding") or {}).get("source_version")
                or "") == str(revised_source.get("source_version") or ""),
            "model_chose_next_work": bool(rounds)
            and rounds[0].get("source") == "model"
            and rounds[0].get("technical_fallback") is False,
            "model_chose_quote_work": str(
                rounds[0].get("work_request_operation") or "")
            == "quote_calculation",
            "phase2_completed": second_assignment.get("status")
            == "completed",
            "affected_quote_changed": second_quote == "425.00",
            "prior_quote_result_retained": str(
                (first_after.get("result") or {}).get("value") or "")
            == "370.00",
            "prior_quote_operation_retained": first_after.get(
                "operation_id") == first_operation,
            "unrelated_note_operation_retained": note_after.get(
                "operation_id") == note_operation,
            "unrelated_note_result_retained": dict(
                note_after.get("result") or {}) == note_result,
            "artifact_revision_changed": artifact_sha != first_sha,
            "artifact_has_new_total": "425.00" in artifact_text,
            "artifact_excludes_superseded_total": "370.00"
            not in artifact_text,
            "artifact_criterion_still_met": (
                ((second.get("employee_job") or {}).get(
                    "business_outcome") or {}).get("state") == "satisfied"
                and any(
                    item.get("kind") == "artifact_verified"
                    and item.get("required")
                    for item in ((second.get("employee_job") or {}).get(
                        "criteria") or []))),
        }
        capture["phase2"].update({
            "note": {
                "document_id": note_data.get("document_id"),
                "operation_id": note_operation,
                "result_sha256": hashlib.sha256(
                    json.dumps(note_result, sort_keys=True,
                               default=str).encode()).hexdigest(),
            },
            "revised_source": {
                "dataset_name": revised_source.get("dataset_name"),
                "sheet": revised_source.get("sheet"),
                "source_version": revised_source.get("source_version"),
                "file_sha256": hashlib.sha256(
                    revised.read_bytes()).hexdigest(),
                "add_request_status": change.status_code,
                "add_response": {
                    "status": change_body.get("status"),
                    "step_id": change_body.get("step_id"),
                    "reassessment_rounds": rounds,
                },
            },
            "status": second_assignment.get("status"),
            "plan_revision": second_durable.get("plan_revision"),
            "quote_total": second_quote,
            "steps": [{
                "step_id": step.get("step_id"),
                "adapter": step.get("adapter"),
                "status": step.get("status"),
                "operation_id": step.get("operation_id"),
                "plan_revision": step.get("updated_at"),
                "result_value": (step.get("result") or {}).get("value"),
                "prior_results": [
                    {"status": item.get("status"),
                     "value": ((item.get("result") or {}).get("value"))}
                    for item in step.get("prior_results") or []],
            } for step in steps.values()],
            "artifact": deliverable,
            "artifact_sha256": artifact_sha,
            "artifact_text": artifact_text,
            "checks": checks,
            "all_checks_passed": all(checks.values()),
        })
        (out / "capture.json").write_text(
            json.dumps(capture, indent=1, default=str) + "\n")
        browser.close()

    print(json.dumps(capture["phase2"]["checks"], indent=1))
    return 0 if capture["phase2"]["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
