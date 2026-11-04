#!/usr/bin/env python3
"""Short normal-UI continuation with exact run capture.

This is the Agent-1 verification harness for the retained-authorized-source
continuation. It uploads three authorized procurement documents through the
ordinary Assignments UI, captures the actual /from-objective request and
response, and binds every subsequent assertion to the returned run_id. It
never treats an already-mounted detail panel or a page-wide total as proof.

Usage (app already launched on the given base/api):
  python scripts/acceptance/employee_g5_ui_continuation.py \
    --base http://127.0.0.1:3136 --api http://127.0.0.1:8085 \
    --out /private/tmp/g5-ui-continuation-exact
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict

import requests
from playwright.sync_api import sync_playwright


def _api_token(api: str, password: str) -> str:
    response = requests.post(
        api + "/api/auth/login",
        json={"username": "admin@example.com", "password": password},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _assignment(api: str, token: str, run_id: str) -> Dict[str, Any]:
    response = requests.get(
        api + f"/api/assignments/{run_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _value(body: Dict[str, Any], adapter: str) -> Any:
    assignment = (body.get("assignment") or {}).get("assignment") or {}
    for step in assignment.get("steps") or []:
        if step.get("adapter") != adapter:
            continue
        if step.get("result_value") is not None:
            return step["result_value"]
        result = step.get("result") or {}
        return result.get("value")
    return None


def _selected_sources(request_body: Dict[str, Any]) -> int:
    return len([
        item for item in request_body.get("sources") or []
        if isinstance(item, dict)
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3136")
    parser.add_argument("--api", default="http://127.0.0.1:8085")
    parser.add_argument("--password", default="G5Browser-2026!")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--fixtures", default="/private/tmp/atom-g5-fixtures")
    parser.add_argument(
        "--objective",
        default=(
            "Reconcile the supplier invoice against the purchase order and "
            "receiving records (exact-run continuation)"),
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fixtures = Path(args.fixtures)
    token = _api_token(args.api, args.password)
    capture: Dict[str, Any] = {
        "objective": args.objective,
        "selected_source_count": 0,
        "request": None,
        "response_status": None,
        "run_id": None,
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.add_init_script(
            "sessionStorage.setItem('atom.onboarding.dismissed','1')")
        page.goto(args.base + "/login", wait_until="networkidle", timeout=90000)
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

        for name in (
                "purchase-order.json", "invoice-v1.json",
                "receiving-records.json"):
            page.get_by_test_id("assignment-source-upload").set_input_files(
                str(fixtures / name))
            page.wait_for_timeout(4000)
        page.get_by_test_id(
            "assignment-employee-decides-checkbox").check()
        page.wait_for_timeout(800)
        page.get_by_test_id("assignment-objective-input").fill(args.objective)
        checklist = page.get_by_test_id("assignment-source-checklist")
        for label in checklist.locator("label").all():
            text = label.inner_text()
            checkbox = label.locator("input")
            wanted = any(
                key in text for key in (
                    "purchase-order", "invoice-v1", "receiving-records"))
            if wanted and not checkbox.is_checked():
                checkbox.check()
            if not wanted and checkbox.is_checked():
                checkbox.uncheck()

        start = page.get_by_test_id("assignment-start-button")
        try:
            with page.expect_response(
                    lambda response: (
                        "/api/assignments/from-objective" in response.url
                        and response.request.method == "POST"),
                    timeout=300000) as response_info:
                start.click()
            response = response_info.value
        except Exception as exc:  # noqa: BLE001 — capture transport failure
            capture["transport_error"] = f"{type(exc).__name__}: {exc}"
            (out / "capture.json").write_text(
                json.dumps(capture, indent=1) + "\n")
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
        capture["selected_source_count"] = _selected_sources(request_body)
        run_id = str(response_body.get("run_id") or "")
        capture["run_id"] = run_id
        (out / "capture.json").write_text(
            json.dumps(capture, indent=1, default=str) + "\n")
        if response.status != 200 or not run_id:
            page.screenshot(
                path=str(out / "start-failure.png"), full_page=True)
            browser.close()
            return 2

        # Bind the UI to the exact returned run. Clicking the summary for the
        # run_id is deliberate: the detail panel may already be mounted on an
        # older assignment.
        summary = page.get_by_test_id(f"assignment-summary-{run_id}")
        summary.wait_for(timeout=60000)
        summary.click()
        detail = page.get_by_test_id("assignment-detail")
        detail.wait_for(timeout=60000)
        page.wait_for_timeout(1200)
        (out / "detail.txt").write_text(page.locator("body").inner_text())
        page.screenshot(
            path=str(out / "exact-run-detail.png"), full_page=True)

        deadline = time.time() + 420
        # The submitted response is already scoped to the exact run; use it as
        # the fallback if a restart/transient transport error interrupts
        # polling. Never substitute an older assignment.
        body: Dict[str, Any] = dict(response_body or {})
        while time.time() < deadline:
            try:
                body = _assignment(args.api, token, run_id)
            except Exception as exc:  # noqa: BLE001 — keep captured response
                capture["poll_error"] = f"{type(exc).__name__}: {exc}"
                break
            assignment = (
                body.get("assignment") or {}).get("assignment") or {}
            status = str(assignment.get("status") or "")
            if status in ("completed", "failed", "cancelled", "blocked"):
                break
            time.sleep(2)
        assignment = (body.get("assignment") or {}).get("assignment") or {}
        capture["final_status"] = assignment.get("status")
        capture["final_value"] = _value(body, "invoice.reconcile")
        capture["steps"] = [
            {
                "step_id": step.get("step_id"),
                "adapter": step.get("adapter"),
                "status": step.get("status"),
                "result_value": step.get("result_value"),
            }
            for step in assignment.get("steps") or []
        ]
        capture["open_obligations"] = (
            (body.get("employee_job") or {}).get("open_obligations") or [])
        capture["authorized_source_count"] = (
            (assignment.get("provenance") or {}).get(
                "authorized_source_count"))
        capture["selected_read_count"] = len([
            step for step in assignment.get("steps") or []
            if step.get("adapter") in ("document.text", "document.read",
                                       "workbook.read", "dataset.read")
        ])
        (out / "final.json").write_text(
            json.dumps(capture, indent=1, default=str) + "\n")
        page.screenshot(
            path=str(out / "exact-run-final.png"), full_page=True)
        browser.close()

    ok = (
        capture.get("final_status") == "completed"
        and str(capture.get("final_value")) == "270.00"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
