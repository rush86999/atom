#!/usr/bin/env python3
"""Verify the completed composite run and the revised-scope second run."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

import docx
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


def open_assignment(page, frontend: str, objective: str):
    page.goto(f"{frontend}/assignments", wait_until="domcontentloaded")
    page.get_by_text(objective, exact=False).first.click()
    detail = page.get_by_test_id("assignment-detail")
    detail.wait_for(timeout=30000)
    detail.get_by_text("completed", exact=True).wait_for(timeout=120000)
    return detail


def download(page, out: Path, stem: str) -> dict:
    button = page.locator('[data-testid^="assignment-download-"]').first
    button.wait_for(timeout=30000)
    with page.expect_download(timeout=30000) as info:
        button.click()
    download = info.value
    target = out / f"{stem}-{download.suggested_filename}"
    download.save_as(str(target))
    document = docx.Document(str(target))
    normal = document.styles["Normal"].font
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "normal_font": normal.name,
        "normal_size": normal.size.pt if normal.size else None,
        "text": "\n".join(p.text for p in document.paragraphs)[:1500],
    }


def start_and_resolve(page, *, frontend: str, agent_id: str, source_file: str,
                      objective: str, candidate: str) -> None:
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
        label="Other business concept…")
    page.get_by_test_id("assignment-custom-measure-input").fill("Price")
    page.get_by_test_id("assignment-context-input").fill("sales")
    page.get_by_test_id("assignment-qualification-input").fill("licensed")
    page.get_by_test_id("assignment-task-scope-input").fill("revised")
    page.get_by_test_id("assignment-start-button").click()
    page.get_by_test_id("mapping-candidates").wait_for(timeout=60000)
    page.get_by_test_id(f"mapping-candidate-{candidate}").click()
    detail = page.get_by_test_id("assignment-detail")
    detail.get_by_text("completed", exact=True).wait_for(timeout=120000)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--part1", required=True)
    ap.add_argument("--objective", required=True)
    ap.add_argument("--second-objective", required=True)
    ap.add_argument("--outbox", required=True)
    args = ap.parse_args()

    out = Path(args.out_dir).resolve()
    part1 = json.loads(Path(args.part1).read_text())
    password = Path(args.password_file).read_text().strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        login(page, args.frontend, password)

        detail = open_assignment(page, args.frontend, args.objective)
        active_artifact = download(page, out, "active-reload")
        active_state = api(page, f"/api/assignments/{part1['run_id']}")
        page.reload(wait_until="domcontentloaded")
        page.get_by_test_id("assignment-detail").wait_for(timeout=30000)
        page.screenshot(path=str(out / "active-reloaded.png"), full_page=True)

        start_and_resolve(
            page, frontend=args.frontend, agent_id=part1["agent_id"],
            source_file="clean_quote.csv", objective=args.second_objective,
            candidate="Net Amount")
        second_artifact = download(page, out, "revised")
        rows = api(page, "/api/assignments?include_terminal=true")
        second_run = next(
            row for row in rows
            if row["assignment"]["objective"] == args.second_objective)
        second_state = api(page, f"/api/assignments/{second_run['run_id']}")
        page.screenshot(path=str(out / "revised-completed.png"), full_page=True)
        browser.close()

    outbox = Path(args.outbox)
    record = {
        "schema": "atom-composite-long-running-verify-1",
        "status": "passed",
        "active": {
            "run_id": part1["run_id"],
            "status": active_state["assignment"]["status"],
            "teaching_revision": active_state["assignment"]["teaching_revision"],
            "mapping": active_state["assignment"]["mappings"],
            "artifact": active_artifact,
        },
        "second": {
            "run_id": second_run["run_id"],
            "status": second_state["assignment"]["status"],
            "teaching_revision": second_state["assignment"]["teaching_revision"],
            "mapping": second_state["assignment"]["mappings"],
            "artifact": second_artifact,
        },
        "teaching_revision_changed_for_new_work": (
            second_state["assignment"]["teaching_revision"]
            != active_state["assignment"]["teaching_revision"]),
        "outbox_lines": (
            len(outbox.read_text().splitlines()) if outbox.is_file() else None),
    }
    (out / "verify.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
