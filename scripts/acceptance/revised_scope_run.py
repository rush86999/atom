#!/usr/bin/env python3
"""A NEW assignment at revised scope adopts the correction taught while the
long-running assignment was waiting. The active run keeps its snapshot (its
completion is verified separately).

Ordinary UI only: upload on /documents, fill the Assignments form, answer the
mapping card, download the artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

import docx
from playwright.sync_api import sync_playwright

BACKEND = "http://127.0.0.1:8071"


def login(page, frontend: str, password: str) -> None:
    page.goto(f"{frontend}/login", wait_until="domcontentloaded")
    page.get_by_test_id("login-email-input").fill("admin@example.com")
    page.get_by_test_id("login-password-input").fill(password)
    page.get_by_test_id("login-submit-button").click()
    page.wait_for_url("**/dashboard", timeout=60000)
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed', '1')")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(800)


def api(page, path: str):
    token = page.evaluate(
        "() => localStorage.getItem('auth_token') || localStorage.getItem('token')")
    request = urllib.request.Request(
        f"{BACKEND}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def start_and_complete(page, *, frontend: str, agent_id: str, source_file: str,
                       objective: str, measure: str, candidate: str,
                       context: str, qualification: str,
                       task_scope: str = "revised") -> None:
    page.goto(f"{frontend}/assignments?attempt={time.time_ns()}",
              wait_until="domcontentloaded")
    page.get_by_test_id("assignment-source-select").wait_for(timeout=30000)
    page.get_by_text("Refresh data", exact=False).click()
    page.wait_for_timeout(2500)
    page.get_by_test_id("assignment-agent-select").select_option(value=agent_id)
    source_select = page.get_by_test_id("assignment-source-select")
    deadline = time.time() + 60
    label = ""
    while time.time() < deadline and not label:
        label = next(
            (option for option in source_select.locator("option").all_inner_texts()
             if source_file in option), "")
        if not label:
            page.get_by_text("Refresh data", exact=False).click()
            page.wait_for_timeout(1500)
    if not label:
        raise SystemExit(f"source {source_file} missing from the picker")
    source_select.select_option(label=label)
    page.get_by_test_id("assignment-objective-input").fill(objective)
    page.get_by_test_id("assignment-measure-select").select_option(
        label="Other business concept…")
    page.get_by_test_id("assignment-custom-measure-input").fill(measure)
    page.get_by_test_id("assignment-context-input").fill(context)
    page.get_by_test_id("assignment-qualification-input").fill(qualification)
    page.get_by_test_id("assignment-task-scope-input").fill(task_scope)
    page.get_by_test_id("assignment-start-button").click()
    page.get_by_test_id("mapping-candidates").wait_for(timeout=90000)
    page.get_by_test_id(f"mapping-candidate-{candidate}").click()
    page.get_by_test_id("assignment-detail").get_by_text(
        "completed", exact=True).wait_for(timeout=180000)
    page.wait_for_timeout(1500)


def download_artifact(page, out: Path, stem: str) -> dict:
    button = page.locator('[data-testid^="assignment-download-"]').first
    button.wait_for(timeout=30000)
    with page.expect_download(timeout=30000) as info:
        button.click()
    target = out / f"{stem}-{info.value.suggested_filename}"
    info.value.save_as(str(target))
    document = docx.Document(str(target))
    normal = document.styles["Normal"].font
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "normal_font": normal.name,
        "normal_size": normal.size.pt if normal.size else None,
        "text": "\n".join(paragraph.text for paragraph in document.paragraphs)[:2000],
    }


def main() -> int:
    global BACKEND
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--backend", default="http://127.0.0.1:8071")
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--source-file", required=True)
    ap.add_argument("--objective", required=True)
    ap.add_argument("--measure", default="Price")
    ap.add_argument("--candidate", default="Net Amount")
    ap.add_argument("--context", default="sales")
    ap.add_argument("--qualification", default="licensed")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--task-scope", default="revised")
    args = ap.parse_args()
    BACKEND = args.backend.rstrip("/")

    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    password = Path(args.password_file).read_text().strip()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        login(page, args.frontend, password)
        page.goto(f"{args.frontend}/documents", wait_until="domcontentloaded")
        page.set_input_files("#file-upload", args.csv)
        page.get_by_text("Successfully uploaded", exact=False).wait_for(
            timeout=90000)
        start_and_complete(
            page, frontend=args.frontend, agent_id=args.agent_id,
            source_file=args.source_file, objective=args.objective,
            measure=args.measure, candidate=args.candidate,
            context=args.context, qualification=args.qualification,
            task_scope=args.task_scope)
        artifact = download_artifact(page, out, f"{args.label}")
        rows = api(page, "/api/assignments?include_terminal=true")
        run = next(row for row in rows
                   if row["assignment"]["objective"] == args.objective)
        detail = api(page, f"/api/assignments/{run['run_id']}")
        page.screenshot(path=str(out / f"{args.label}-completed.png"),
                        full_page=True)
        browser.close()

    record = {
        "schema": "atom-revised-scope-run-1",
        "label": args.label,
        "objective": args.objective,
        "run_id": run["run_id"],
        "assignment_id": detail["assignment"]["assignment_id"],
        "assignment_status": detail["assignment"]["status"],
        "teaching_revision": detail["assignment"]["teaching_revision"],
        "effective_lesson_ids": detail["assignment"].get("effective_lesson_ids"),
        "step_values": {step["step_id"]: step.get("result_value")
                        for step in detail.get("steps") or []},
        "artifact": artifact,
        "source_file": args.source_file,
        "mapping_candidate": args.candidate,
        "task_scope": args.task_scope,
    }
    (out / f"{args.label}.json").write_text(
        json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
