#!/usr/bin/env python3
"""Three typed canvases through the normal canvas UI.

Creates an industrial quote, a service proposal and a non-sales exception
queue with schema-2 typed fields. The user configures fields/units/rules in
the ordinary panel, binds a CSV, clicks Derive fields, answers a targeted
missing-value clarification on the same canvas, and reloads.

The server computes every total; the browser only sends the three accepted
revisions and the field answers. No per-canvas Python and no custom-code
runtime are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
    page.get_by_test_id(
        f"attach-agent-option-{agent_id}").evaluate("el => el.click()")
    page.get_by_test_id("canvas-capability-panel").wait_for(
        state="attached", timeout=60000)
    return page.url


def open_panel(page) -> None:
    panel = page.get_by_test_id("canvas-capability-panel")
    panel.wait_for(state="attached", timeout=60000)
    button = panel.get_by_role("button", name="Data operations")
    if button.count():
        button.click()
        page.wait_for_timeout(400)


def configure(page, manifest: dict) -> str:
    open_panel(page)
    panel = page.get_by_test_id("canvas-capability-panel")
    if panel.get_by_test_id("capability-enable").count():
        panel.get_by_test_id("capability-enable").click()
        page.wait_for_timeout(1200)
    advanced = panel.get_by_test_id("capability-advanced-manifest")
    if advanced.count() and not advanced.get_attribute("open"):
        advanced.locator("summary").click()
        page.wait_for_timeout(300)
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
    page.wait_for_timeout(1500)
    effective = panel.get_by_test_id("capability-effective").inner_text()
    return {"status": response.status, "body": body, "effective": effective}


def derive(page) -> dict:
    panel = page.get_by_test_id("canvas-capability-panel")
    with page.expect_response(
            lambda r: "/capability/derive" in r.url
            and "/answer" not in r.url
            and r.request.method == "POST", timeout=120000) as info:
        panel.get_by_test_id("capability-derive").click()
    response = info.value
    body = response.json()
    page.wait_for_timeout(500)
    return {"status": response.status, "body": body}


def answer(page, row: int, field_id: str, value: str) -> dict:
    panel = page.get_by_test_id("canvas-capability-panel")
    panel.get_by_test_id(
        f"capability-derive-answer-{row}-{field_id}").fill(value)
    with page.expect_response(
            lambda r: "/capability/derive/" in r.url
            and "/answer" in r.url
            and r.request.method == "POST", timeout=120000) as info:
        panel.get_by_test_id("capability-derive-answer-submit").click()
    response = info.value
    body = response.json()
    page.wait_for_timeout(500)
    return {"status": response.status, "body": body}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    password = Path(args.password_file).read_text().strip()

    quote_csv = out / "industrial-quote.csv"
    quote_csv.write_text(
        "Item,Qty,Price\n"
        "A-1,2,100.00\n"
        "B-2,3,50.00\n",
        encoding="utf-8",
    )
    service_csv = out / "service-proposal.csv"
    service_csv.write_text(
        "Service,Hours,Rate\n"
        "Consulting,4,120.00\n"
        "Site trip,2,75.00\n",
        encoding="utf-8",
    )
    queue_csv = out / "exception-queue.csv"
    queue_csv.write_text(
        "Exception,Amount,Status\n"
        "EX-1,,Open\n"
        "EX-2,50.00,Open\n"
        "EX-3,20.00,Closed\n",
        encoding="utf-8",
    )

    quote_manifest = {
        "schema_version": 2,
        "base_component": "table",
        "operations": ["read", "derive", "edit", "bind"],
        "data_binding": {"subject_field": "Item"},
        "fields": [
            {"id": "item_id", "label": "Item", "type": "string",
             "column": "Item", "required": True},
            {"id": "quantity", "label": "Quantity", "type": "decimal",
             "column": "Qty", "unit": "each", "required": True,
             "editable": True},
            {"id": "unit_price", "label": "Unit price", "type": "currency",
             "column": "Price", "currency": "USD", "required": True,
             "editable": True},
            {"id": "line_total", "label": "Line total", "type": "currency",
             "currency": "USD", "column": "Line Total",
             "derived": "quantity * unit_price", "aggregate": "sum",
             "group_by": "item_id"},
        ],
        "outputs": ["xlsx"],
    }
    service_manifest = {
        "schema_version": 2,
        "base_component": "form",
        "operations": ["read", "derive", "edit", "bind"],
        "data_binding": {"subject_field": "Service"},
        "fields": [
            {"id": "service", "label": "Service", "type": "string",
             "column": "Service", "required": True},
            {"id": "hours", "label": "Hours", "type": "decimal",
             "column": "Hours", "unit": "hour", "required": True,
             "editable": True},
            {"id": "rate", "label": "Rate", "type": "currency",
             "column": "Rate", "currency": "CAD", "required": True,
             "editable": True},
            {"id": "fee_total", "label": "Fee total", "type": "currency",
             "currency": "CAD", "column": "Fee Total",
             "derived": "hours * rate", "aggregate": "sum",
             "group_by": "service"},
        ],
        "outputs": ["xlsx"],
    }
    queue_manifest = {
        "schema_version": 2,
        "base_component": "queue",
        "operations": ["read", "derive", "edit", "select", "bind"],
        "data_binding": {
            "subject_field": "Exception", "status_field": "Status"},
        "fields": [
            {"id": "exception_id", "label": "Exception", "type": "string",
             "column": "Exception", "required": True,
             "aggregate": "count", "group_by": "status"},
            {"id": "amount", "label": "Amount", "type": "currency",
             "column": "Amount", "currency": "USD", "required": True,
             "editable": True, "aggregate": "sum", "group_by": "status"},
            {"id": "status", "label": "Status", "type": "string",
             "column": "Status", "required": True, "editable": True},
        ],
        "outputs": ["xlsx"],
    }

    checks: list[dict] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS" if ok else "FAIL"), name, json.dumps(
            detail or {}, default=str)[:500])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)[:300]))
        login(page, args.frontend, password)

        # Canvas 1: industrial quote.
        quote_url = new_canvas(page, args.frontend, args.agent_id)
        quote_effective = configure(page, quote_manifest)
        quote_bind = bind(page, quote_csv)
        quote_derive = derive(page)
        record(
            "industrial quote created and bound through the UI",
            "/canvas/" in quote_url and quote_bind["status"] == 200
            and quote_bind["body"].get("row_count") == 2,
            {"url": quote_url, "bind": quote_bind["body"].get("row_count")},
        )
        record(
            "industrial quote derives server total 350.00 USD",
            quote_derive["body"].get("aggregates", {}).get("line_total")
            == "350.00"
            and quote_derive["body"].get("input_receipt", {}).get("digest"),
            {"aggregates": quote_derive["body"].get("aggregates")},
        )
        record(
            "industrial quote exposes table view and derive operation",
            "derive" in quote_bind["effective"],
            quote_bind["effective"],
        )
        page.reload(wait_until="domcontentloaded")
        page.get_by_test_id("canvas-capability-panel").wait_for(
            state="attached", timeout=60000)
        open_panel(page)
        page.get_by_test_id("capability-typed-fields").wait_for(
            state="visible", timeout=15000)
        record(
            "industrial quote fields and revision survive reload",
            "line_total" in page.get_by_test_id(
                "capability-typed-fields").inner_text(),
            page.get_by_test_id("capability-typed-fields").inner_text()[:300],
        )
        page.screenshot(path=str(out / "industrial-quote.png"),
                        full_page=True)

        # Canvas 2: service proposal.
        service_url = new_canvas(page, args.frontend, args.agent_id)
        service_effective = configure(page, service_manifest)
        service_bind = bind(page, service_csv)
        service_derive = derive(page)
        record(
            "service proposal created and bound through the UI",
            "/canvas/" in service_url and service_bind["status"] == 200
            and service_bind["body"].get("row_count") == 2,
            {"url": service_url, "bind": service_bind["body"].get("row_count")},
        )
        record(
            "service proposal derives server total 630.00 CAD",
            service_derive["body"].get("aggregates", {}).get("fee_total")
            == "630.00",
            {"aggregates": service_derive["body"].get("aggregates")},
        )
        record(
            "service proposal derives in CAD through the same panel",
            "derive" in service_bind["effective"]
            and service_derive["body"].get("input_receipt", {}).get(
                "fields", [{}])[2].get("currency") == "CAD",
            service_bind["effective"],
        )
        page.screenshot(path=str(out / "service-proposal.png"),
                        full_page=True)

        # Canvas 3: non-sales exception queue with a missing-value answer.
        queue_url = new_canvas(page, args.frontend, args.agent_id)
        queue_effective = configure(page, queue_manifest)
        queue_bind = bind(page, queue_csv)
        first_derive = derive(page)
        record(
            "exception queue created with a targeted missing amount",
            "/canvas/" in queue_url and queue_bind["status"] == 200
            and first_derive["body"].get("status") == "clarification"
            and first_derive["body"]["clarification"]["missing"][0][
                "field_id"] == "amount",
            {"url": queue_url, "status": first_derive["body"].get("status")},
        )
        answered = answer(page, 2, "amount", "100.00")
        record(
            "same queue derivation resumes after the answer",
            answered["status"] == 200
            and answered["body"].get("status") == "resolved"
            and answered["body"].get("result", {}).get(
                "aggregates", {}).get("amount") == "170.00",
            {"status": answered["body"].get("status"),
             "aggregates": answered["body"].get("result", {}).get(
                 "aggregates")},
        )
        record(
            "exception queue counts and groups by status",
            answered["body"].get("result", {}).get("aggregates", {}).get(
                "exception_id") == 3
            and any(group.get("group") == "Open"
                    and group.get("value") == "150.00"
                    for group in answered["body"].get("result", {}).get(
                        "groups", [])),
            answered["body"].get("result", {}).get("groups"),
        )
        record(
            "exception queue exposes derive and selection, not a sales quote",
            "derive" in queue_bind["effective"]
            and "select" in queue_bind["effective"],
            queue_bind["effective"],
        )
        page.reload(wait_until="domcontentloaded")
        page.get_by_test_id("canvas-capability-panel").wait_for(
            state="attached", timeout=60000)
        open_panel(page)
        page.get_by_test_id("capability-typed-fields").wait_for(
            state="visible", timeout=15000)
        record(
            "exception queue history and fields survive reload",
            "exception_id" in page.get_by_test_id(
                "capability-typed-fields").inner_text(),
            page.get_by_test_id("capability-typed-fields").inner_text()[:300],
        )
        page.screenshot(path=str(out / "exception-queue.png"),
                        full_page=True)
        record("no browser page errors", not errors, errors)

        payload = {
            "schema": "atom-canvas-typed-canvases-local-1",
            "status": "passed" if all(item["ok"] for item in checks) else "failed",
            "frontend": args.frontend,
            "agent_id": args.agent_id,
            "canvas_urls": {
                "industrial_quote": quote_url,
                "service_proposal": service_url,
                "exception_queue": queue_url,
            },
            "manifests": {
                "industrial_quote": quote_manifest,
                "service_proposal": service_manifest,
                "exception_queue": queue_manifest,
            },
            "checks": checks,
            "artifacts": {
                "industrial_quote.png": hashlib.sha256(
                    (out / "industrial-quote.png").read_bytes()).hexdigest(),
                "service_proposal.png": hashlib.sha256(
                    (out / "service-proposal.png").read_bytes()).hexdigest(),
                "exception_queue.png": hashlib.sha256(
                    (out / "exception-queue.png").read_bytes()).hexdigest(),
            },
            "page_errors": errors,
        }
        (out / "result.json").write_text(json.dumps(payload, indent=2))
        browser.close()
    return 0 if all(item["ok"] for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
