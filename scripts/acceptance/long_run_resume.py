#!/usr/bin/env python3
"""Long-running part 2: resume the same assignment after a real restart.

The part-1 run is already durably waiting on a correlated external fact. This
script reopens that same run in a new browser context, changes teaching while
it waits (the active snapshot must not move), delivers the correlated reply,
approves the exact outbound payload, downloads the artifact, and proves a
duplicate resume/response adds no second effect.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
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


def api(page, path: str, method: str = "GET", payload=None):
    token = page.evaluate(
        "localStorage.getItem('auth_token') || localStorage.getItem('token')")
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"http://127.0.0.1:8071{path}", data=data,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode() or "{}")
        except Exception:
            body = {}
        return exc.code, body


def teach(page, *, lesson: str, topic: str, font: str, size: str,
          headings: str, columns: str, task_scope: str,
          context: str = "sales", qualification: str = "licensed") -> None:
    page.get_by_test_id("teach-lesson-input").fill(
        lesson, timeout=60000, force=True)
    page.get_by_test_id("teach-topic-input").fill(topic)
    page.get_by_test_id("teach-structured-fields").evaluate("el => el.open = true")
    for box in page.locator('[data-testid^="teach-applies-"]').all():
        if box.is_checked():
            box.uncheck()
    page.get_by_test_id("teach-applies-document").check()
    page.get_by_test_id("teach-format-font").fill(font)
    page.get_by_test_id("teach-format-size").fill(size)
    page.get_by_test_id("teach-format-headings").fill(headings)
    page.get_by_test_id("teach-format-columns").fill(columns)
    page.get_by_test_id("teach-context").fill(context)
    page.get_by_test_id("teach-qualification").fill(qualification)
    page.get_by_test_id("teach-task-scope").fill(task_scope)
    page.get_by_test_id("teach-effective-from").fill("2026-01-01")
    page.get_by_test_id("teach-effective-to").fill("2027-12-31")
    page.get_by_test_id("teach-format-greeting").fill("")
    page.get_by_test_id("teach-format-signature").fill("")
    page.get_by_test_id("teach-format-subject-prefix").fill("")
    page.get_by_test_id("teach-submit").click()
    page.get_by_text("Lesson recorded", exact=False).wait_for(timeout=30000)


def open_assignment(page, frontend: str, objective: str, run_id: str) -> None:
    page.goto(f"{frontend}/assignments", wait_until="domcontentloaded")
    page.get_by_test_id(f"assignment-summary-{run_id}").click()
    page.get_by_test_id("assignment-detail").wait_for(timeout=30000)
    page.wait_for_function(
        """expected => {
            const el = document.querySelector(
                '[data-testid="assignment-detail-objective"]');
            return el && el.textContent.trim() === expected;
        }""", arg=objective, timeout=30000)


def download(page, out: Path) -> dict:
    button = page.locator('[data-testid^="assignment-download-"]').first
    button.wait_for(timeout=60000)
    with page.expect_download(timeout=60000) as info:
        button.click()
    handle = info.value
    target = out / f"longrun-{handle.suggested_filename}"
    handle.save_as(str(target))
    document = docx.Document(str(target))
    normal = document.styles["Normal"].font
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "normal_font": normal.name,
        "normal_size": normal.size.pt if normal.size else None,
        "text": "\n".join(p.text for p in document.paragraphs)[:3000],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default="http://127.0.0.1:3130")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--part1", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument(
        "--response",
        default="Delivery term: net 30 days from the invoice date.")
    ap.add_argument("--skip-teaching", action="store_true")
    args = ap.parse_args()

    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    part1 = json.loads(Path(args.part1).read_text())
    password = Path(args.password_file).read_text().strip()
    run_id = part1["run_id"]
    old_revision = part1["teaching_revision"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        login(page, args.frontend, password)

        status, before = api(page, f"/api/assignments/{run_id}")
        assert status == 200, (status, before)
        assignment = before["assignment"]
        assert assignment["status"] == "waiting", assignment["status"]
        assert assignment["teaching_revision"] == old_revision, (
            "restart changed the accepted teaching snapshot")
        assert assignment["steps"][0]["result_value"] == "550.00", (
            assignment["steps"][0])
        open_assignment(page, args.frontend, assignment["objective"], run_id)
        page.screenshot(path=str(out / "reopened-waiting.png"),
                        full_page=True)

        if not args.skip_teaching:
            page.goto(part1["canvas_url"], wait_until="domcontentloaded")
            page.get_by_test_id("training-panel").wait_for(timeout=30000)
            teach(
                page,
                lesson=("Revised long-run format: use Calibri 14 with "
                        "Summary, Findings and Sources and an Item/Value "
                        "table for revised-scope work."),
                topic="revised long-run document format",
                font="Calibri", size="14",
                headings="Summary, Findings, Sources", columns="Item, Value",
                task_scope="revised", context="sales",
                qualification="licensed",
            )
            status, after_teach = api(page, f"/api/assignments/{run_id}")
            assert after_teach["assignment"]["teaching_revision"] == (
                old_revision), "active run adopted revised teaching without review"
            assert after_teach["assignment"]["status"] == "waiting"
        else:
            after_teach = before

        open_assignment(page, args.frontend, assignment["objective"], run_id)
        detail = page.get_by_test_id("assignment-detail")
        detail.get_by_label("Correlated response").fill(args.response)
        detail.get_by_role("button", name="Deliver").click()
        page.wait_for_timeout(2500)
        approval_text = ""
        if detail.get_by_text("Approval required", exact=False).count():
            approval_text = detail.inner_text()
            (out / "approval-panel.txt").write_text(approval_text)
            detail.get_by_role("button", name="Approve this payload").click()
        detail.get_by_text("completed", exact=True).wait_for(timeout=180000)
        page.screenshot(path=str(out / "completed.png"), full_page=True)
        artifact = download(page, out)

        status, done = api(page, f"/api/assignments/{run_id}")
        assert done["assignment"]["status"] == "completed", done["assignment"]
        steps = {s["step_id"]: s for s in done["assignment"]["steps"]}
        assert steps["source-1"]["result_value"] == "550.00"
        assert steps["wait"]["status"] == "applied"
        assert steps["deliverable-1"]["status"] == "applied"
        assert steps["send"]["status"] == "applied"
        response_state = steps["wait"].get("external_response") or {}

        outbox = Path(part1.get("outbox") or
                      "/Users/rushiparikh/projects/atom/backend/data/"
                      "acceptance_worlds/long_run_2h_20261101/"
                      "controlled-outbox.jsonl")
        lines_before = len(outbox.read_text().splitlines()) if outbox.exists() else 0
        # A duplicate resume must not recreate the completed work.
        dup_status, dup = api(page, f"/api/assignments/{run_id}/resume",
                              method="POST")
        lines_after_resume = (
            len(outbox.read_text().splitlines()) if outbox.exists() else 0)
        # A late duplicate reply must not be treated as a new effect.
        late_status, late = api(
            page, f"/api/assignments/{run_id}/responses/"
                  f"{part1['correlation_id']}",
            method="POST", payload={"response": args.response})
        lines_after_late = (
            len(outbox.read_text().splitlines()) if outbox.exists() else 0)

        page.reload(wait_until="domcontentloaded")
        page.get_by_test_id("assignment-detail").wait_for(timeout=30000)
        reloaded_text = page.get_by_test_id("assignment-detail").inner_text()
        page.screenshot(path=str(out / "reloaded-completed.png"),
                        full_page=True)
        browser.close()

    record = {
        "schema": "atom-long-run-resume-1",
        "status": "passed" if (
            done["assignment"]["status"] == "completed"
            and steps["send"]["status"] == "applied"
            and lines_before == lines_after_resume == lines_after_late
            and "completed" in reloaded_text.lower()) else "failed",
        "run_id": run_id,
        "assignment_id": done["assignment"]["assignment_id"],
        "objective": done["assignment"]["objective"],
        "teaching_revision_before": old_revision,
        "teaching_revision_after_teach": (
            after_teach["assignment"]["teaching_revision"]),
        "status_before": before["assignment"]["status"],
        "status_after": done["assignment"]["status"],
        "source_result": steps["source-1"]["result_value"],
        "external_response": response_state,
        "artifact": artifact,
        "outbox": str(outbox),
        "outbox_lines_before_duplicates": lines_before,
        "outbox_lines_after_resume": lines_after_resume,
        "outbox_lines_after_late_response": lines_after_late,
        "duplicate_resume": {"status": dup_status, "body": dup},
        "late_response": {"status": late_status, "body": late},
        "reload_shows_completed": "completed" in reloaded_text.lower(),
        "approval_panel_present": bool(approval_text),
    }
    (out / "resume.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
