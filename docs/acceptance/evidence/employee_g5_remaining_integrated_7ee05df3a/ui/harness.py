#!/usr/bin/env python3
"""Normal Assignments UI artifact journey with exact run capture.

Starts an explicit quote-document objective through the ordinary page,
captures the actual /api/assignments request/response and returned run_id,
clicks that exact summary, waits for completion, downloads the artifact
through the normal route, and verifies the bytes/content independently.

Usage (app already launched):
  python scripts/acceptance/employee_g5_ui_artifact.py \
    --base http://127.0.0.1:3136 --api http://127.0.0.1:8085 \
    --out /private/tmp/g5-ui-artifact
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

OBJECTIVE = "Prepare the customer quote document"
LINE_ITEMS = {
    "line_items": [
        {"item_id": "A", "category": "A", "quantity": "2", "unit": "each",
         "pack_size": "1", "unit_price": "100.00", "price_basis": "contract",
         "currency": "USD"},
        {"item_id": "B", "category": "B", "quantity": "3", "unit": "each",
         "pack_size": "1", "unit_price": "50.00", "price_basis": "contract",
         "currency": "USD"},
    ],
    "currency": "USD",
    "freight": "20.00",
    "tax": {"basis": "none"},
    "rounding": "half_up",
    "scale": 2,
    "rounding_authority": "customer agreement",
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


def _payload(body: Dict[str, Any]) -> Dict[str, Any]:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3136")
    parser.add_argument("--api", default="http://127.0.0.1:8085")
    parser.add_argument("--password", default="G5Browser-2026!")
    parser.add_argument(
        "--fixtures", default="/private/tmp/atom-g5-fixtures")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    token = _api_token(args.api, args.password)
    health = requests.get(args.api + "/health", timeout=30)
    health.raise_for_status()
    capture: Dict[str, Any] = {
        "objective": OBJECTIVE,
        "line_items": LINE_ITEMS,
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
                args.base + "/login", wait_until="networkidle",
                timeout=90000)
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
            str(Path(args.fixtures) / "price-book.xlsx"))
        page.wait_for_timeout(4000)
        page.get_by_test_id("assignment-objective-input").fill(OBJECTIVE)
        page.get_by_test_id("assignment-deliverable-kind").select_option(
            "document")
        select = page.get_by_test_id("assignment-source-select")
        option = next(
            text for text in select.locator("option").all_inner_texts()
            if "price-book" in text)
        select.select_option(label=option)
        page.locator("details").first.evaluate("element => { element.open = true }")
        page.get_by_test_id("assignment-line-items-input").fill(
            json.dumps(LINE_ITEMS))
        page.screenshot(
            path=str(out / "start-form.png"), full_page=True)

        try:
            with page.expect_response(
                    lambda response: (
                        "/api/assignments" in response.url
                        and response.request.method == "POST"
                        and "/from-objective" not in response.url),
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
            capture["request"] = json.loads(
                response.request.post_data or "{}")
        except (TypeError, ValueError):
            capture["request"] = {}
        try:
            response_body = response.json()
        except Exception:  # noqa: BLE001
            response_body = {}
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

        if "/login" in page.url:
            sign_in()
        summary = page.get_by_test_id(f"assignment-summary-{run_id}")
        summary.wait_for(timeout=60000)
        summary.click()
        page.get_by_test_id("assignment-detail").wait_for(timeout=60000)

        deadline = time.time() + 300
        body: Dict[str, Any] = {}
        while time.time() < deadline:
            body = _assignment(args.api, token, run_id)
            assignment = _payload(body)
            if str(assignment.get("status") or "") in (
                    "completed", "failed", "cancelled", "blocked"):
                break
            page.wait_for_timeout(1500)
        assignment = _payload(body)
        page.wait_for_timeout(1200)
        detail_text = page.locator("body").inner_text()
        (out / "detail.txt").write_text(detail_text)
        page.screenshot(
            path=str(out / "exact-run-final.png"), full_page=True)

        job = body.get("employee_job") or {}
        criteria = job.get("criteria") or []
        outcome = job.get("business_outcome") or {}
        deliverable = (assignment.get("deliverables") or [{}])[0]
        artifact_bytes = b""
        download_status = None
        if deliverable.get("deliverable_id"):
            download = requests.get(
                args.api + (
                    f"/api/assignments/{run_id}/deliverables/"
                    f"{deliverable['deliverable_id']}/download"),
                headers={"Authorization": f"Bearer {token}"}, timeout=60)
            download_status = download.status_code
            if download.status_code == 200:
                artifact_bytes = download.content
        artifact_path = out / "customer-quote.docx"
        if artifact_bytes:
            artifact_path.write_bytes(artifact_bytes)
        artifact_sha = (
            hashlib.sha256(artifact_bytes).hexdigest()
            if artifact_bytes else None)
        artifact_text = (
            _docx_text(artifact_bytes) if artifact_bytes else "")
        expected_total = "370.00"
        checks = {
            "captured_exact_run": bool(run_id)
            and body.get("run_id") == run_id,
            "three_source_scope_not_required": True,
            "assignment_completed": assignment.get("status")
            == "completed",
            "artifact_applied": deliverable.get("status") == "applied",
            "artifact_criterion_met": any(
                item.get("kind") == "artifact_verified"
                and item.get("required") for item in criteria)
            and outcome.get("state") == "satisfied",
            "artifact_download_ok": download_status == 200,
            "artifact_sha_matches": bool(artifact_sha)
            and artifact_sha == deliverable.get("sha256"),
            "artifact_has_exact_total": expected_total in artifact_text,
            "artifact_has_source_and_lines": "price-book.xlsx"
            in artifact_text and "A" in artifact_text and "B"
            in artifact_text,
            "ui_shows_completed_exact_run": OBJECTIVE in detail_text
            and "completed" in detail_text.lower()
            and expected_total in detail_text,
        }
        capture.update({
            "serving_identity_after": requests.get(
                args.api + "/health", timeout=30).json(),
            "final_run_id": body.get("run_id"),
            "assignment_status": assignment.get("status"),
            "artifact": deliverable,
            "artifact_sha256": artifact_sha,
            "artifact_text": artifact_text,
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
