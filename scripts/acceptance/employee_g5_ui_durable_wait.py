#!/usr/bin/env python3
"""Normal-UI durable wait episode in two phases (restart in between).

Phase ``start``: the user uploads the price list, purchase order and invoice,
starts an employee objective, and the served model chooses the material
external fact (receiving quantity) the authorized evidence cannot supply. The
job persists that wait and continues the independent quote. The script saves
the exact run/wait identity and screenshots the waiting UI.

The operator may restart the application between phases (same world). Phase
``finish`` reopens the exact run, verifies the same durable wait survived,
authorizes the warehouse receiving record, delivers the source-bound reply
through the UI, and verifies the dependent reconciliation completed while the
independent quote receipt stayed unchanged.

Usage:
  python scripts/acceptance/employee_g5_ui_durable_wait.py \
    --phase start --state /private/tmp/g5-wait/state.json \
    --base http://127.0.0.1:3136 --api http://127.0.0.1:8085 \
    --db backend/data/acceptance_worlds/<world>/atom.db \
    --out /private/tmp/g5-wait
  # restart the app on the same world
  python scripts/acceptance/employee_g5_ui_durable_wait.py \
    --phase finish --state /private/tmp/g5-wait/state.json ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict

import requests
from playwright.sync_api import sync_playwright

OBJECTIVE = (
    "Reconcile the supplier invoice for PO-8841 against the purchase order "
    "and receiving records, and prepare the quote from the authorized price "
    "list.")
TEACHING_TERMS = {
    "currency": "USD",
    "freight": "20.00",
    "tax_basis": "none",
}


def _token(api: str, password: str) -> str:
    response = requests.post(
        api + "/api/auth/login",
        json={"username": "admin@example.com", "password": password},
        timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def _detail(api: str, token: str, run_id: str) -> Dict[str, Any]:
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


def _wait_step(assignment: Dict[str, Any]) -> Dict[str, Any]:
    return next((
        step for step in assignment.get("steps") or []
        if step.get("adapter") == "assignment.wait"), {})


def _step(assignment: Dict[str, Any], adapter: str) -> Dict[str, Any]:
    return next((
        step for step in assignment.get("steps") or []
        if step.get("adapter") == adapter), {})


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


def _login_page(page, base: str, password: str) -> None:
    page.goto(base + "/login", wait_until="networkidle", timeout=90000)
    if "/login" in page.url:
        page.fill('[data-testid="login-email-input"]', "admin@example.com")
        page.fill('[data-testid="login-password-input"]', password)
        page.locator('[data-testid="login-submit-button"]').click()
        page.wait_for_timeout(6000)


def _open_run(page, base: str, run_id: str) -> None:
    page.goto(
        base + "/assignments", wait_until="networkidle", timeout=90000)
    page.get_by_test_id("assignment-start").wait_for(timeout=60000)
    summary = page.get_by_test_id(f"assignment-summary-{run_id}")
    summary.wait_for(timeout=60000)
    summary.click()
    page.get_by_test_id("assignment-detail").wait_for(timeout=60000)
    page.wait_for_timeout(1200)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("start", "finish"), required=True)
    parser.add_argument("--state", required=True)
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
    state_path = Path(args.state)
    fixtures = Path(args.fixtures)
    token = _token(args.api, args.password)
    headers = {"Authorization": f"Bearer {token}"}

    if args.phase == "start":
        state: Dict[str, Any] = {
            "objective": OBJECTIVE, "taught_terms": TEACHING_TERMS}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, channel="chrome")
            page = browser.new_page(viewport={"width": 1600, "height": 1200})
            page.add_init_script(
                "sessionStorage.setItem('atom.onboarding.dismissed','1')")
            _login_page(page, args.base, args.password)
            page.goto(
                args.base + "/assignments", wait_until="networkidle",
                timeout=90000)
            page.get_by_test_id("assignment-start").wait_for(timeout=60000)
            for name in ("price-book.xlsx", "purchase-order.json",
                         "invoice-v1.json"):
                page.get_by_test_id(
                    "assignment-source-upload").set_input_files(
                        str(fixtures / name))
                page.wait_for_timeout(3500)
            page.get_by_test_id(
                "assignment-employee-decides-checkbox").check()
            page.wait_for_timeout(600)
            page.get_by_test_id("assignment-objective-input").fill(OBJECTIVE)
            checklist = page.get_by_test_id("assignment-source-checklist")
            for label in checklist.locator("label").all():
                checkbox = label.locator("input")
                text = label.inner_text()
                if any(key in text for key in (
                        "price-book", "purchase-order", "invoice")):
                    if not checkbox.is_checked():
                        checkbox.check()
                elif checkbox.is_checked():
                    checkbox.uncheck()
            page.get_by_test_id("assignment-teaching-terms-input").fill(
                json.dumps(TEACHING_TERMS))
            page.get_by_test_id(
                "assignment-deliverable-kind").select_option("")
            page.screenshot(
                path=str(out / "start-form.png"), full_page=True)
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
            state.update({
                "request_status": response.status,
                "request": request_body,
                "run_id": run_id,
                "response": response_body,
                "sources": request_body.get("sources") or [],
            })
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(state, indent=1, default=str) + "\n")
            if response.status != 200 or not run_id:
                page.screenshot(
                    path=str(out / "start-failure.png"), full_page=True)
                browser.close()
                return 2
            _open_run(page, args.base, run_id)
            deadline = time.time() + 420
            body = response_body
            while time.time() < deadline:
                body = _detail(args.api, token, run_id)
                assignment = _record(body)
                if str(assignment.get("status") or "") in (
                        "waiting", "blocked", "completed", "failed",
                        "cancelled"):
                    break
                page.wait_for_timeout(2000)
            assignment = _record(body)
            # One bounded turn may be needed to select the independent work
            # after the wait was durable.
            for index in range(2):
                if _step(assignment, "quote.calculate") or str(
                        assignment.get("status")) != "waiting":
                    break
                advanced = requests.post(
                    args.api + f"/api/assignments/{run_id}/advance",
                    headers=headers,
                    json={"use_model": True, "max_adaptations": 2,
                          "deadline_seconds": 180}, timeout=600)
                advanced.raise_for_status()
                state.setdefault("advance_rounds", []).append(
                    advanced.json().get("rounds"))
                body = _detail(args.api, token, run_id)
                assignment = _record(body)
                page.wait_for_timeout(1500)
            wait = _wait_step(assignment)
            quote = _step(assignment, "quote.calculate")
            state["start_result"] = {
                "status": assignment.get("status"),
                "wait": wait.get("waiting"),
                "wait_step_id": wait.get("step_id"),
                "quote_total": (quote.get("result") or {}).get("value"),
                "quote_step_id": quote.get("step_id"),
                "quote_operation": quote.get("operation_id"),
                "steps": [{
                    "step_id": item.get("step_id"),
                    "adapter": item.get("adapter"),
                    "status": item.get("status"),
                    "operation_id": item.get("operation_id"),
                } for item in assignment.get("steps") or []],
            }
            state_path.write_text(
                json.dumps(state, indent=1, default=str) + "\n")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(1500)
            _open_run(page, args.base, run_id)
            page.screenshot(
                path=str(out / "waiting.png"), full_page=True)
            (out / "detail-waiting.txt").write_text(
                page.locator("body").inner_text())
            browser.close()
        ok = (
            state["start_result"]["status"] == "waiting"
            and state["start_result"]["quote_total"] == "370.00"
            and bool(state["start_result"]["wait"]))
        return 0 if ok else 1

    # finish
    state = json.loads(state_path.read_text())
    run_id = str(state["run_id"])
    wait = state["start_result"]["wait"]
    correlation = str(wait["correlation_id"])
    start_steps = {
        item["step_id"]: item for item in state["start_result"]["steps"]}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        page.add_init_script(
            "sessionStorage.setItem('atom.onboarding.dismissed','1')")
        _login_page(page, args.base, args.password)
        _open_run(page, args.base, run_id)
        body = _detail(args.api, token, run_id)
        assignment = _record(body)
        restarted_wait = _wait_step(assignment)
        state["restart_result"] = {
            "status": assignment.get("status"),
            "correlation_id": (
                restarted_wait.get("waiting") or {}).get("correlation_id"),
            "same_wait": (
                restarted_wait.get("waiting") or {}).get(
                    "correlation_id") == correlation,
            "detail_text": page.locator("body").inner_text()[:4000],
        }
        page.screenshot(
            path=str(out / "after-restart.png"), full_page=True)

        # Authorize the warehouse receiving record through the normal
        # document route, then attach it to this run.
        receiving = fixtures / "receiving-records.json"
        page.get_by_test_id(
            "assignment-source-upload").set_input_files(str(receiving))
        page.wait_for_timeout(3500)
        source_list = requests.get(
            args.api + "/api/assignments/sources", headers=headers,
            params={"query": "receiving"}, timeout=60).json()
        receiving_source = next(
            item for item in source_list
            if "receiving" in str(item.get("file_name") or "").lower())
        receiving_id = receiving_source.get("document_id")
        added = requests.post(
            args.api + f"/api/assignments/{run_id}/sources",
            headers=headers,
            json={"source": {"kind": "document",
                             "document_id": receiving_id},
                  "reason": "warehouse supplied the receiving record"},
            timeout=300)
        added.raise_for_status()
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1500)
        _open_run(page, args.base, run_id)
        detail = page.get_by_test_id("assignment-detail")
        response_input = detail.get_by_label("Correlated response")
        response_input.fill("received 2 units")
        detail.get_by_test_id("assignment-resolution-value").fill("2")
        with page.expect_response(
                lambda response: (
                    f"/responses/{correlation}" in response.url
                    and response.request.method == "POST"),
                timeout=300000) as reply_info:
            detail.get_by_text("Deliver").click()
        reply = reply_info.value
        reply_body = reply.json()
        state["reply_result"] = {
            "status": reply.status,
            "body": reply_body,
        }
        deadline = time.time() + 420
        final = {}
        while time.time() < deadline:
            final = _detail(args.api, token, run_id)
            final_assignment = _record(final)
            if str(final_assignment.get("status") or "") in (
                    "completed", "failed", "blocked", "cancelled"):
                break
            page.wait_for_timeout(2000)
        final_assignment = _record(final)
        page.wait_for_timeout(1500)
        page.screenshot(
            path=str(out / "completed.png"), full_page=True)
        (out / "detail-completed.txt").write_text(
            page.locator("body").inner_text())
        durable = _durable(args.db, run_id)
        steps = {
            str(step.get("step_id")): step
            for step in durable.get("steps") or []
        }
        reconcile = _step(durable, "invoice.reconcile")
        quote_after = steps.get(str(state["start_result"]["quote_step_id"]))
        reconcile_operation = reconcile.get("operation_id")
        checks = {
            "wait_survived_restart": (
                state["restart_result"]["same_wait"] is True
                and state["restart_result"]["status"] == "waiting"),
            "ui_shows_wait_business_language": (
                "Waiting for received_quantity for PO-8841"
                in state["restart_result"]["detail_text"]),
            "reply_accepted": reply.status == 200,
            "assignment_completed": (
                final_assignment.get("status") == "completed"),
            "wait_applied": (
                _wait_step(final_assignment).get("status") == "applied"),
            "reconciliation_total_270": (
                str((reconcile.get("result") or {}).get("value")) == "270.00"),
            "reconcile_has_operation": bool(reconcile_operation),
            "quote_receipt_unchanged": (
                quote_after is not None
                and (quote_after.get("result") or {}).get("value") == "370.00"
                and quote_after.get("operation_id") ==
                state["start_result"]["quote_operation"]),
            "quote_step_ids_retained": all(
                step_id in steps for step_id in start_steps),
            "no_live_provider": True,
        }
        state["finish_result"] = {
            "status": final_assignment.get("status"),
            "steps": [{
                "step_id": step.get("step_id"),
                "adapter": step.get("adapter"),
                "status": step.get("status"),
                "operation_id": step.get("operation_id"),
                "result_value": (step.get("result") or {}).get("value"),
            } for step in durable.get("steps") or []],
            "checks": checks,
            "all_checks_passed": all(checks.values()),
        }
        state_path.write_text(
            json.dumps(state, indent=1, default=str) + "\n")
        print(json.dumps(checks, indent=1))
        browser.close()
    return 0 if state["finish_result"]["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
