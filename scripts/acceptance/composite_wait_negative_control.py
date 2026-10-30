#!/usr/bin/env python3
"""Negative control: a reply denying a fact the source already exposes.

The assignment must stay waiting, retain the reply as a durable conflict, and
must not complete or produce an artifact from the contradictory statement.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
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
    page.wait_for_timeout(1000)


def api(page, path: str):
    token = page.evaluate(
        "localStorage.getItem('auth_token') || localStorage.getItem('token')")
    request = urllib.request.Request(
        f"http://127.0.0.1:8071{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode() or "{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--part1", required=True)
    ap.add_argument("--objective", default="Negative control: currency contradiction")
    ap.add_argument("--response",
                    default="Currency unstated by source; report the total without a currency.")
    args = ap.parse_args()

    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    part1 = json.loads(Path(args.part1).read_text())
    password = Path(args.password_file).read_text().strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        login(page, args.frontend, password)
        page.goto(f"{args.frontend}/assignments?attempt={time.time_ns()}",
                  wait_until="domcontentloaded")
        page.get_by_test_id("assignment-source-select").wait_for(timeout=30000)
        page.get_by_text("Refresh data", exact=False).click()
        page.wait_for_timeout(2000)
        page.get_by_test_id("assignment-agent-select").select_option(
            value=part1["agent_id"])
        source = page.get_by_test_id("assignment-source-select")
        label = next(option for option in source.locator("option").all_inner_texts()
                     if "integrated_quote.csv" in option)
        source.select_option(label=label)
        page.get_by_test_id("assignment-objective-input").fill(args.objective)
        page.get_by_test_id("assignment-measure-select").select_option(
            label="Other business concept…")
        page.get_by_test_id("assignment-custom-measure-input").fill("Price")
        page.get_by_test_id("assignment-context-input").fill("sales")
        page.get_by_test_id("assignment-qualification-input").fill("licensed")
        page.get_by_test_id("assignment-task-scope-input").fill("standard")
        page.get_by_text("Advanced (optional)", exact=False).click()
        page.get_by_test_id("assignment-recipient-input").fill("")
        page.get_by_test_id("assignment-correlation-input").fill("negative-currency")
        page.get_by_test_id("assignment-missing-fact-input").fill("currency")
        page.get_by_test_id("assignment-start-button").click()
        page.get_by_test_id("mapping-candidates").wait_for(timeout=60000)
        page.get_by_test_id("mapping-candidate-Gross Amount").click()
        page.get_by_text("Correlated response", exact=False).wait_for(timeout=60000)
        detail = page.get_by_test_id("assignment-detail")
        detail.get_by_label("Correlated response").fill(args.response)
        detail.get_by_role("button", name="Deliver").click()
        page.get_by_text("already establishes", exact=False).wait_for(
            timeout=30000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(out / "negative-control.png"), full_page=True)

        rows = api(page, "/api/assignments?include_terminal=true")
        run = next(row for row in rows
                   if row["assignment"]["objective"] == args.objective)
        state = api(page, f"/api/assignments/{run['run_id']}")
        wait_step = next(step for step in state["assignment"]["steps"]
                         if step["step_id"] == "wait")
        conflicts = (wait_step.get("waiting") or {}).get("conflicts") or []
        record = {
            "schema": "atom-composite-wait-negative-control-1",
            "status": "passed",
            "objective": args.objective,
            "run_id": run["run_id"],
            "assignment_status": state["assignment"]["status"],
            "wait_step_status": wait_step["status"],
            "conflicts": conflicts,
            "response_retained": any(
                args.response in str(item.get("response") or "")
                for item in conflicts),
            "artifact_created": any(
                item.get("status") == "applied"
                for item in state["assignment"].get("deliverables") or []),
        }
        (out / "negative-control.json").write_text(
            json.dumps(record, indent=2) + "\n")
        browser.close()

    if record["assignment_status"] != "waiting":
        raise SystemExit("REFUSED: contradictory reply completed the assignment")
    if record["wait_step_status"] != "waiting":
        raise SystemExit("REFUSED: contradictory reply closed the wait step")
    if not record["response_retained"]:
        raise SystemExit("REFUSED: contradictory reply was not retained")
    if record["artifact_created"]:
        raise SystemExit("REFUSED: contradictory reply produced an artifact")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
