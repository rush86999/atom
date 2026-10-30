#!/usr/bin/env python3
"""Positive twins for wait-fact resolution.

Create mode:
- blank Currency column + reply "USD" -> accepted, completed;
- established Currency=USD + reply "USD" -> confirmation, completed.
Verify mode (after a real backend restart):
- the blank-currency assignment is still completed, artifact hash matches,
  and exactly one wait operation was applied.
"""
from __future__ import annotations

import argparse
import hashlib
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


def download(page, out: Path, stem: str) -> dict:
    button = page.locator('[data-testid^="assignment-download-"]').first
    button.wait_for(timeout=30000)
    with page.expect_download(timeout=30000) as info:
        button.click()
    download = info.value
    target = out / f"{stem}-{download.suggested_filename}"
    download.save_as(str(target))
    return {
        "path": str(target),
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }


def start_wait(page, *, frontend: str, agent_id: str, source_file: str,
               objective: str, measure: str, correlation: str) -> None:
    page.goto(f"{frontend}/assignments?attempt={time.time_ns()}",
              wait_until="domcontentloaded")
    page.get_by_test_id("assignment-source-select").wait_for(timeout=30000)
    page.get_by_text("Refresh data", exact=False).click()
    page.wait_for_timeout(2000)
    page.get_by_test_id("assignment-agent-select").select_option(value=agent_id)
    source = page.get_by_test_id("assignment-source-select")
    label = next(option for option in source.locator("option").all_inner_texts()
                 if source_file in option)
    source.select_option(label=label)
    page.get_by_test_id("assignment-objective-input").fill(objective)
    page.get_by_test_id("assignment-measure-select").select_option(
        label=f"Sum {measure}")
    page.get_by_test_id("assignment-context-input").fill("sales")
    page.get_by_test_id("assignment-qualification-input").fill("licensed")
    page.get_by_test_id("assignment-task-scope-input").fill("standard")
    page.get_by_text("Advanced (optional)", exact=False).click()
    page.get_by_test_id("assignment-correlation-input").fill(correlation)
    page.get_by_test_id("assignment-missing-fact-input").fill("currency")
    page.get_by_test_id("assignment-start-button").click()
    page.get_by_text("Correlated response", exact=False).wait_for(timeout=60000)


def resolve_and_complete(page, response: str) -> None:
    detail = page.get_by_test_id("assignment-detail")
    detail.get_by_label("Correlated response").fill(response)
    detail.get_by_role("button", name="Deliver").click()
    detail.get_by_text("completed", exact=True).wait_for(timeout=120000)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--part1", required=True)
    ap.add_argument("--blank-csv", required=True)
    ap.add_argument("--mode", choices=("create", "verify"), required=True)
    ap.add_argument("--state", default="")
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()

    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    part1 = json.loads(Path(args.part1).read_text())
    password = Path(args.password_file).read_text().strip()
    state_path = Path(args.state) if args.state else out / "positive-twins.json"
    state = json.loads(state_path.read_text()) if state_path.is_file() else {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        login(page, args.frontend, password)

        if args.mode == "create":
            page.goto(f"{args.frontend}/documents", wait_until="domcontentloaded")
            page.set_input_files("#file-upload", args.blank_csv)
            page.get_by_text("Successfully uploaded", exact=False).wait_for(
                timeout=90000)
            page.wait_for_timeout(1500)

            blank_objective = f"Blank currency recovery{args.suffix}"
            start_wait(
                page, frontend=args.frontend, agent_id=part1["agent_id"],
                source_file=Path(args.blank_csv).name,
                objective=blank_objective, measure="Net Amount",
                correlation="blank-currency")
            resolve_and_complete(page, "USD")
            blank_artifact = download(page, out, "blank-currency")
            blank_rows = api(page, "/api/assignments?include_terminal=true")
            blank_run = next(
                row for row in blank_rows
                if row["assignment"]["objective"] == blank_objective)
            blank_state = api(page, f"/api/assignments/{blank_run['run_id']}")
            blank_wait = next(
                step for step in blank_state["assignment"]["steps"]
                if step["step_id"] == "wait")
            state["blank"] = {
                "objective": blank_objective,
                "run_id": blank_run["run_id"],
                "status": blank_state["assignment"]["status"],
                "artifact": blank_artifact,
                "fact_resolution": blank_wait["external_response"].get(
                    "fact_resolution"),
                "fact_confirmation": blank_wait["external_response"].get(
                    "fact_confirmation"),
            }

            agree_objective = f"Agreeing currency confirmation{args.suffix}"
            start_wait(
                page, frontend=args.frontend, agent_id=part1["agent_id"],
                source_file="integrated_quote.csv",
                objective=agree_objective, measure="Gross Amount",
                correlation="agree-currency")
            resolve_and_complete(page, "USD")
            agree_rows = api(page, "/api/assignments?include_terminal=true")
            agree_run = next(
                row for row in agree_rows
                if row["assignment"]["objective"] == agree_objective)
            agree_state = api(page, f"/api/assignments/{agree_run['run_id']}")
            agree_wait = next(
                step for step in agree_state["assignment"]["steps"]
                if step["step_id"] == "wait")
            state["agreeing"] = {
                "objective": agree_objective,
                "run_id": agree_run["run_id"],
                "status": agree_state["assignment"]["status"],
                "fact_resolution": agree_wait["external_response"].get(
                    "fact_resolution"),
                "fact_confirmation": agree_wait["external_response"].get(
                    "fact_confirmation"),
            }
            state_path.write_text(json.dumps(state, indent=2) + "\n")
            browser.close()
            print(json.dumps(state, indent=2))
            return 0

        # verify after restart
        blank = state.get("blank") or {}
        page.goto(f"{args.frontend}/assignments", wait_until="domcontentloaded")
        page.get_by_test_id(f"assignment-summary-{blank['run_id']}").click()
        detail = page.get_by_test_id("assignment-detail")
        detail.wait_for(timeout=30000)
        detail.get_by_text("completed", exact=True).wait_for(timeout=30000)
        artifact = download(page, out, "blank-currency-after-restart")
        rows = api(page, "/api/assignments?include_terminal=true")
        run = next(row for row in rows
                   if row["assignment"]["objective"] == blank["objective"])
        current = api(page, f"/api/assignments/{run['run_id']}")
        wait_ops = [
            op for op in current.get("operations") or []
            if op.get("step_id") == "wait" and op.get("status") == "applied"
        ]
        result = {
            "schema": "atom-wait-positive-twins-verify-1",
            "status": "passed",
            "blank": {
                "run_id": run["run_id"],
                "assignment_status": current["assignment"]["status"],
                "artifact_sha256": artifact["sha256"],
                "artifact_hash_matches": (
                    artifact["sha256"] == blank["artifact"]["sha256"]),
                "applied_wait_operations": len(wait_ops),
            },
            "agreeing": state.get("agreeing"),
        }
        (out / "positive-twins-verify.json").write_text(
            json.dumps(result, indent=2) + "\n")
        browser.close()

    if result["blank"]["assignment_status"] != "completed":
        raise SystemExit("REFUSED: blank-currency assignment did not survive")
    if not result["blank"]["artifact_hash_matches"]:
        raise SystemExit("REFUSED: blank-currency artifact hash changed")
    if result["blank"]["applied_wait_operations"] != 1:
        raise SystemExit("REFUSED: wait operation was duplicated")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
