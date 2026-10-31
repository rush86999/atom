#!/usr/bin/env python3
"""Composite long-running journey, part 1: teach, conflict, start, wait.

Browser actions establish a multi-lesson policy, expose an equally applicable
conflict, remove the conflicting lesson, upload a source, start a multi-step
assignment, confirm the mapping, and stop at the durable external-fact wait.
The caller then closes the browser and restarts the backend process before
running part 2.
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


def agent_rows(page) -> list[dict]:
    rows = api(page, "/api/agents/")
    return rows if isinstance(rows, list) else rows.get("data", [])


def fresh_page(browser, frontend: str, password: str):
    page = browser.new_page(viewport={"width": 1440, "height": 1200})
    login(page, frontend, password)
    return page


def create_agent(page, frontend: str, goal: str,
                 context_text: str = (
                     "Use sales quote methods, cite sources, and ask for "
                     "missing context.")) -> str:
    page.goto(f"{frontend}/agents", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    before = {row["id"] for row in agent_rows(page)}
    page.get_by_test_id("describe-job-button").click()
    page.get_by_test_id("guided-goal-input").fill(goal)
    page.get_by_test_id("guided-context-input").fill(context_text)
    page.get_by_test_id("guided-create-button").click()
    try:
        page.get_by_test_id("guided-success").wait_for(timeout=60000)
        page.get_by_test_id("guided-done-button").click()
    except Exception:
        # The onboarding host may cover the result dialog; the API diff below
        # is the durable signal that creation completed.
        page.keyboard.press("Escape")
    deadline = time.time() + 45
    new_rows = []
    while time.time() < deadline and not new_rows:
        new_rows = [row for row in agent_rows(page) if row["id"] not in before]
        if not new_rows:
            page.wait_for_timeout(1000)
    if not new_rows:
        raise SystemExit("REFUSED: guided creation did not produce an agent")
    return str(new_rows[-1]["id"])


def open_teaching(page, frontend: str, agent_id: str) -> str:
    page.goto(f"{frontend}/agents", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    button = page.get_by_test_id(f"agent-teach-button-{agent_id}")
    button.wait_for(timeout=30000)
    button.click()
    page.wait_for_url("**/canvas/**", timeout=30000)
    page.get_by_test_id("training-panel").wait_for(timeout=30000)
    return page.url


def teach(page, *, lesson: str, topic: str, applies: str | None = None,
          font: str = "", size: str = "", headings: str = "",
          columns: str = "", context: str = "", qualification: str = "",
          task_scope: str = "", effective_from: str = "",
          effective_to: str = "", greeting: str = "", signature: str = "",
          subject_prefix: str = "") -> None:
    page.get_by_test_id("teach-lesson-input").wait_for(
        state="visible", timeout=30000)
    page.wait_for_function(
        """() => {
            const el = document.querySelector(
                '[data-testid="teach-lesson-input"]');
            return !!el && !el.disabled && el.offsetParent !== null;
        }""", timeout=30000)
    page.get_by_test_id("teach-lesson-input").fill(lesson)
    page.get_by_test_id("teach-topic-input").fill(topic)
    page.get_by_test_id("teach-structured-fields").evaluate("el => el.open = true")
    for box in page.locator('[data-testid^="teach-applies-"]').all():
        if box.is_checked():
            box.uncheck()
    if applies:
        page.get_by_test_id(f"teach-applies-{applies}").check()
    page.get_by_test_id("teach-format-font").fill(font)
    page.get_by_test_id("teach-format-size").fill(size)
    page.get_by_test_id("teach-format-headings").fill(headings)
    page.get_by_test_id("teach-format-columns").fill(columns)
    page.get_by_test_id("teach-context").fill(context)
    page.get_by_test_id("teach-qualification").fill(qualification)
    page.get_by_test_id("teach-task-scope").fill(task_scope)
    page.get_by_test_id("teach-effective-from").fill(effective_from)
    page.get_by_test_id("teach-effective-to").fill(effective_to)
    page.get_by_test_id("teach-format-greeting").fill(greeting)
    page.get_by_test_id("teach-format-signature").fill(signature)
    page.get_by_test_id("teach-format-subject-prefix").fill(subject_prefix)
    page.get_by_test_id("teach-submit").click()
    page.get_by_text("Lesson recorded", exact=False).wait_for(timeout=30000)


def fill_start(page, *, frontend: str, agent_id: str, source_file: str,
               objective: str, qualification: str, task_scope: str,
               correlation: str, recipient: str, measure: str = "Price",
               context: str = "sales",
               missing_fact: str = "delivery_term") -> str:
    # A blank navigation then a fresh assignments URL guarantees a full
    # document reload and resets the panel after a refused attempt; a
    # same-route goto can preserve React form state in Next.js.
    page.goto("about:blank")
    page.goto(f"{frontend}/assignments?attempt={time.time_ns()}",
              wait_until="domcontentloaded")
    page.get_by_test_id("assignment-source-select").wait_for(timeout=30000)
    page.get_by_text("Refresh data", exact=False).click()
    page.wait_for_timeout(2000)

    agent_select = page.get_by_test_id("assignment-agent-select")
    agent_select.select_option(value=agent_id)

    source_select = page.get_by_test_id("assignment-source-select")
    deadline = time.time() + 60
    source_label = ""
    while time.time() < deadline and not source_label:
        source_label = next(
            (option for option in source_select.locator("option").all_inner_texts()
             if source_file in option), "")
        if not source_label:
            page.get_by_text("Refresh data", exact=False).click()
            page.wait_for_timeout(1500)
    if not source_label:
        raise SystemExit(f"REFUSED: {source_file} is not in the source picker")
    source_select.select_option(label=source_label)

    page.get_by_test_id("assignment-objective-input").fill(objective)
    page.get_by_test_id("assignment-measure-select").select_option(
        label="Other business concept…")
    page.get_by_test_id("assignment-custom-measure-input").fill(measure)
    page.get_by_test_id("assignment-context-input").fill(context)
    page.get_by_test_id("assignment-qualification-input").fill(qualification)
    page.get_by_test_id("assignment-task-scope-input").fill(task_scope)
    page.get_by_text("Advanced (optional)", exact=False).click()
    page.get_by_test_id("assignment-recipient-input").fill(recipient)
    page.get_by_test_id("assignment-correlation-input").fill(correlation)
    page.get_by_test_id("assignment-missing-fact-input").fill(missing_fact)
    button = page.get_by_test_id("assignment-start-button")
    print("start.disabled", button.is_disabled(), flush=True)
    button.click()
    page.wait_for_timeout(3000)
    return page.get_by_test_id("assignment-panel").inner_text()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--agent-name", default="Quote Specialist")
    ap.add_argument("--objective", default="Sum Price for the integrated quote sheet")
    ap.add_argument("--correlation", default="quote-missing-currency-1")
    ap.add_argument("--measure", default="Price")
    ap.add_argument("--context", default="sales")
    ap.add_argument("--qualification", default="licensed")
    ap.add_argument("--mapping-candidate", default="Gross Amount")
    ap.add_argument("--domain-label", default="sales quote")
    ap.add_argument("--greeting", default="Dear colleague,")
    ap.add_argument("--signature", default="Sales team")
    ap.add_argument("--subject-prefix", default="[Quote]")
    ap.add_argument("--agent-goal", default=(
        "Prepare sales quote documents from uploaded price sheets, "
        "calculate totals, and explain missing context."))
    args = ap.parse_args()

    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    password = Path(args.password_file).read_text().strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = fresh_page(browser, args.frontend, password)
        agent_id = create_agent(
            page, args.frontend, args.agent_goal,
            f"Use {args.domain_label} methods, cite sources, and ask for "
            "missing context.")

        canvas_url = open_teaching(page, args.frontend, agent_id)
        teach(
            page,
            lesson=(f"Method: for {args.domain_label} work, use the selected "
                    "authorized sheet, sum the business measure named in the "
                    "task, and cite the source sheet and row count. "
                    f"Context: {args.context}. If a required fact is missing, "
                    "ask for it instead of guessing."),
            topic=f"{args.domain_label} method",
        )
        teach(
            page,
            lesson=("Document protocol: use the approved quote layout with "
                    "Summary, Findings and Sources, and a two-column Item/Value table."),
            topic="sales document format",
            applies="document", font="Arial", size="11",
            headings="Summary, Findings, Sources", columns="Item, Value",
            context=args.context, qualification=args.qualification,
            effective_from="2026-01-01", effective_to="2027-12-31",
        )
        teach(
            page,
            lesson=("Expedited quote exception: use a compact document with "
                    "Summary and Sources only."),
            topic="expedited document exception",
            applies="document", font="Arial", size="10",
            headings="Summary, Sources", columns="Item, Value",
            context=args.context, qualification=args.qualification, task_scope="expedited",
            effective_from="2026-01-01", effective_to="2027-12-31",
        )
        teach(
            page,
            lesson=(f"Email protocol: greet the recipient, identify the "
                    f"{args.signature}, and prefix the subject with "
                    f"{args.subject_prefix}."),
            topic=f"{args.domain_label} email protocol",
            applies="email", greeting=args.greeting,
            signature=args.signature, subject_prefix=args.subject_prefix,
        )
        teach(
            page,
            lesson=("Expired instruction: use Courier New 13 for quote documents. "
                    "This instruction is outside its effective period."),
            topic="expired document format",
            applies="document", font="Courier New", size="13",
            headings="Summary, Findings, Sources", columns="Item, Value",
            context=args.context, qualification=args.qualification,
            effective_from="2019-01-01", effective_to="2020-01-01",
        )
        teach(
            page,
            lesson=("Conflicting instruction: use Times New Roman 12 for sales "
                    "quote documents."),
            topic="conflicting document format",
            applies="document", font="Times New Roman", size="12",
            headings="Summary, Findings, Sources", columns="Item, Value",
            context=args.context, qualification=args.qualification,
            effective_from="2026-01-01", effective_to="2027-12-31",
        )

        page.goto(f"{args.frontend}/documents", wait_until="domcontentloaded")
        page.set_input_files("#file-upload", args.csv)
        page.get_by_text("Successfully uploaded", exact=False).wait_for(timeout=90000)
        page.close()

        # First attempt in a fresh browser context: the two equally applicable
        # document-format lessons conflict. The error must name the conflicting
        # key, not choose one.
        page = fresh_page(browser, args.frontend, password)
        first_error = fill_start(
            page, frontend=args.frontend, agent_id=agent_id,
            source_file=Path(args.csv).name, objective=args.objective,
            qualification=args.qualification, task_scope="standard",
            correlation=args.correlation,
            recipient="acceptance@example.invalid",
            measure=args.measure, context=args.context)
        if "Teaching cannot govern" not in first_error or "font_name" not in first_error:
            raise SystemExit(
                "REFUSED: expected a font_name teaching conflict, got: "
                + first_error[:1200])
        (out / "first-conflict.txt").write_text(first_error)
        page.screenshot(path=str(out / "first-conflict.png"), full_page=True)
        page.close()

        # Remove the conflicting lesson through the normal teaching surface.
        page = fresh_page(browser, args.frontend, password)
        page.goto(canvas_url, wait_until="domcontentloaded")
        page.get_by_test_id("training-panel").wait_for(timeout=30000)
        point = page.locator('[data-testid="teaching-point"]').filter(
            has_text="Times New Roman").first
        page.on("dialog", lambda dialog: dialog.accept())
        point.locator('[data-testid="teaching-point-delete"]').click(
            timeout=30000, force=True)
        page.get_by_text("Teaching point removed", exact=False).wait_for(
            timeout=30000)
        page.close()

        # Second attempt in another fresh context: the required qualification
        # is absent. The resolver must ask for it, not silently drop the
        # licensed instruction.
        page = fresh_page(browser, args.frontend, password)
        missing_error = fill_start(
            page, frontend=args.frontend, agent_id=agent_id,
            source_file=Path(args.csv).name, objective=args.objective,
            qualification="", task_scope="standard",
            correlation=args.correlation,
            recipient="acceptance@example.invalid",
            measure=args.measure, context=args.context)
        if "Teaching cannot govern" not in missing_error:
            raise SystemExit(
                "REFUSED: expected a missing-qualification clarification, got: "
                + missing_error[:1200])
        (out / "missing-qualification.txt").write_text(missing_error)
        page.screenshot(path=str(out / "missing-qualification.png"),
                        full_page=True)
        page.close()

        # Final attempt in a clean context with the matching qualification.
        page = fresh_page(browser, args.frontend, password)
        second_error = fill_start(
            page, frontend=args.frontend, agent_id=agent_id,
            source_file=Path(args.csv).name, objective=args.objective,
            qualification=args.qualification, task_scope="standard",
            correlation=args.correlation,
            recipient="acceptance@example.invalid",
            measure=args.measure, context=args.context)
        page.get_by_test_id("assignment-detail-objective").wait_for(timeout=60000)
        if page.get_by_test_id("assignment-detail-objective").inner_text() != args.objective:
            raise SystemExit(
                "REFUSED: licensed start did not select the new run: "
                + second_error[:1500])

        page.get_by_test_id("mapping-candidates").wait_for(timeout=60000)
        page.get_by_test_id(
            f"mapping-candidate-{args.mapping_candidate}").click()
        page.get_by_text("Correlated response", exact=False).wait_for(
            timeout=60000)
        page.wait_for_timeout(1500)

        rows = api(page, "/api/assignments?include_terminal=true")
        run = next(row for row in rows if row["assignment"]["objective"] == args.objective)
        detail = api(page, f"/api/assignments/{run['run_id']}")
        record = {
            "schema": "atom-composite-long-running-part1-1",
            "status": "waiting",
            "agent_name": args.agent_name,
            "agent_id": agent_id,
            "canvas_url": canvas_url,
            "objective": args.objective,
            "correlation_id": args.correlation,
            "run_id": run["run_id"],
            "assignment_id": detail["assignment"]["assignment_id"],
            "teaching_revision": detail["assignment"]["teaching_revision"],
            "mapping": detail["assignment"]["mappings"],
            "steps": [
                {"step_id": step["step_id"], "status": step["status"],
                 "result_value": step.get("result_value"),
                 "waiting": step.get("waiting")}
                for step in detail["assignment"]["steps"]
            ],
            "open_gaps": detail["open_gaps"],
            "first_error": first_error,
            "teaching_points_visible": page.locator(
                '[data-testid="teaching-point"]').count(),
        }
        (out / "part1.json").write_text(json.dumps(record, indent=2) + "\n")
        page.screenshot(path=str(out / "waiting-before-restart.png"),
                        full_page=True)
        browser.close()
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
