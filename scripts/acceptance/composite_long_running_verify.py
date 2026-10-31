#!/usr/bin/env python3
"""Verify the completed composite run and the revised-scope second run.

The verifier enforces the claims it records. A mismatch raises and exits
nonzero; ``--negative-controls`` proves that wrong font, unchanged revision,
duplicate operation, missing email protocol and contradictory completion are
all rejected by the same validator.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
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


def open_assignment(page, frontend: str, objective: str, run_id: str = ""):
    page.goto(f"{frontend}/assignments", wait_until="domcontentloaded")
    if run_id:
        page.get_by_test_id(f"assignment-summary-{run_id}").click()
    else:
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


def _result_value(state: dict, step_id: str) -> str:
    for step in state["assignment"].get("steps") or []:
        if step.get("step_id") == step_id:
            return str(step.get("result_value") or "")
    return ""


def start_and_resolve(page, *, frontend: str, agent_id: str, source_file: str,
                      objective: str, candidate: str, measure: str = "Price",
                      context: str = "sales",
                      qualification: str = "licensed") -> None:
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
    page.get_by_test_id("assignment-custom-measure-input").fill(measure)
    page.get_by_test_id("assignment-context-input").fill(context)
    page.get_by_test_id("assignment-qualification-input").fill(qualification)
    page.get_by_test_id("assignment-task-scope-input").fill("revised")
    page.get_by_test_id("assignment-start-button").click()
    page.get_by_test_id("mapping-candidates").wait_for(timeout=60000)
    page.get_by_test_id(f"mapping-candidate-{candidate}").click()
    detail = page.get_by_test_id("assignment-detail")
    detail.get_by_text("completed", exact=True).wait_for(timeout=120000)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate(record: dict, expected: dict) -> None:
    """Enforce every property the campaign claims."""
    _assert(record.get("active", {}).get("status") == "completed",
            "active assignment did not complete")
    _assert(record["active"]["teaching_revision"] == expected["active_revision"],
            "active teaching revision changed")
    active_mapping = (record["active"].get("mapping") or [{}])[0]
    _assert(active_mapping.get("concept") == expected["concept"],
            f"active mapping concept is {active_mapping.get('concept')!r}")
    _assert(active_mapping.get("column") == expected["active_column"],
            f"active mapping column is {active_mapping.get('column')!r}")
    _assert(record["active"].get("result_value") == expected["active_result"],
            f"active result is {record['active'].get('result_value')!r}")
    _assert(record["active"]["artifact"]["normal_font"]
            == expected["active_font"], "active font mismatch")
    _assert(float(record["active"]["artifact"]["normal_size"])
            == float(expected["active_size"]), "active font size mismatch")
    _assert(expected["active_sha"] in ("", record["active"]["artifact"]["sha256"]),
            "active artifact hash mismatch")
    _assert("FOB destination" in record["active"]["artifact"]["text"],
            "active artifact lacks the supplied delivery term")
    _assert("Currency unstated" not in record["active"]["artifact"]["text"],
            "active artifact contains the contradictory currency statement")

    _assert(record.get("second", {}).get("status") == "completed",
            "second assignment did not complete")
    _assert(record["second"]["teaching_revision"]
            != record["active"]["teaching_revision"],
            "new work did not adopt a new teaching revision")
    second_mapping = (record["second"].get("mapping") or [{}])[0]
    _assert(second_mapping.get("concept") == expected["concept"],
            f"second mapping concept is {second_mapping.get('concept')!r}")
    _assert(second_mapping.get("column") == expected["second_column"],
            f"second mapping column is {second_mapping.get('column')!r}")
    _assert(record["second"].get("result_value") == expected["second_result"],
            f"second result is {record['second'].get('result_value')!r}")
    _assert(record["second"]["artifact"]["normal_font"]
            == expected["second_font"], "second font mismatch")
    _assert(float(record["second"]["artifact"]["normal_size"])
            == float(expected["second_size"]), "second font size mismatch")
    _assert(expected["second_sha"] in ("", record["second"]["artifact"]["sha256"]),
            "second artifact hash mismatch")

    lines = record.get("outbox") or []
    _assert(len(lines) == 1, f"expected one outbox line, got {len(lines)}")
    operations = [line.get("operation_id") for line in lines]
    _assert(len(operations) == len(set(operations)),
            "duplicate outbox operation")
    subject = str(lines[0].get("subject") or "")
    body = str(lines[0].get("body") or "")
    _assert(subject.startswith(expected["subject_prefix"]),
            f"outbox subject lacks {expected['subject_prefix']!r}")
    _assert(body.lstrip().lower().startswith(expected["greeting"].lower()),
            "outbox body lacks the taught greeting")
    _assert(expected["signature"] in body,
            "outbox body lacks the taught signature")
    _assert("FOB destination" in body,
            "outbox body lacks the supplied delivery term")
    _assert("Currency unstated" not in body,
            "outbox body contains the contradictory currency statement")


def negative_controls(record: dict, expected: dict, out: Path) -> dict:
    """Prove the validator rejects each claimed-property regression."""
    cases = {
        "wrong_font": lambda r: r["active"]["artifact"].__setitem__(
            "normal_font", "Times New Roman"),
        "unchanged_revision": lambda r: r["second"].__setitem__(
            "teaching_revision", r["active"]["teaching_revision"]),
        "duplicate_operation": lambda r: r["outbox"].append(
            dict(r["outbox"][0])),
        "missing_protocol": lambda r: r["outbox"][0].__setitem__(
            "subject", "No protocol prefix"),
        "contradictory_completion": lambda r: r["active"]["artifact"].__setitem__(
            "text", r["active"]["artifact"]["text"]
            + "\nCurrency unstated by source; report the total without a currency."),
    }
    results = {}
    for name, mutate in cases.items():
        candidate = copy.deepcopy(record)
        mutate(candidate)
        try:
            validate(candidate, expected)
        except AssertionError as exc:
            results[name] = {"rejected": True, "reason": str(exc)}
        else:
            results[name] = {"rejected": False, "reason": "validator accepted"}
    passed = all(item["rejected"] for item in results.values())
    payload = {
        "schema": "atom-composite-verifier-negative-controls-1",
        "status": "passed" if passed else "failed",
        "cases": results,
    }
    (out / "negative-controls.json").write_text(json.dumps(payload, indent=2) + "\n")
    if not passed:
        raise AssertionError(f"negative controls failed: {results}")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--part1", required=True)
    ap.add_argument("--objective", required=True)
    ap.add_argument("--second-objective", required=True)
    ap.add_argument("--outbox", required=True)
    ap.add_argument("--expected-active-sha", default="")
    ap.add_argument("--expected-second-sha", default="")
    ap.add_argument("--expected-active-font", default="Arial")
    ap.add_argument("--expected-active-size", default="11")
    ap.add_argument("--expected-second-font", default="Calibri")
    ap.add_argument("--expected-second-size", default="14")
    ap.add_argument("--expected-active-result", default="400.00")
    ap.add_argument("--expected-second-result", default="2225.75")
    ap.add_argument("--measure", default="Price")
    ap.add_argument("--context", default="sales")
    ap.add_argument("--qualification", default="licensed")
    ap.add_argument("--second-source", default="clean_quote.csv")
    ap.add_argument("--second-candidate", default="Net Amount")
    ap.add_argument("--active-column", default="Gross Amount")
    ap.add_argument("--greeting", default="Dear colleague,")
    ap.add_argument("--signature", default="Sales team")
    ap.add_argument("--subject-prefix", default="[Quote]")
    ap.add_argument("--negative-controls", action="store_true")
    args = ap.parse_args()

    out = Path(args.out_dir).resolve()
    part1 = json.loads(Path(args.part1).read_text())
    password = Path(args.password_file).read_text().strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        login(page, args.frontend, password)

        open_assignment(page, args.frontend, args.objective, part1["run_id"])
        active_artifact = download(page, out, "active-reload")
        active_state = api(page, f"/api/assignments/{part1['run_id']}")
        page.reload(wait_until="domcontentloaded")
        page.get_by_test_id("assignment-detail").wait_for(timeout=30000)
        page.screenshot(path=str(out / "active-reloaded.png"), full_page=True)

        start_and_resolve(
            page, frontend=args.frontend, agent_id=part1["agent_id"],
            source_file=args.second_source, objective=args.second_objective,
            candidate=args.second_candidate, measure=args.measure,
            context=args.context, qualification=args.qualification)
        second_artifact = download(page, out, "revised")
        rows = api(page, "/api/assignments?include_terminal=true")
        second_run = next(
            row for row in rows
            if row["assignment"]["objective"] == args.second_objective)
        second_state = api(page, f"/api/assignments/{second_run['run_id']}")
        page.screenshot(path=str(out / "revised-completed.png"), full_page=True)
        browser.close()

    outbox_path = Path(args.outbox)
    outbox_lines = [
        json.loads(line) for line in outbox_path.read_text().splitlines()
        if line.strip()
    ] if outbox_path.is_file() else []
    final_lines = [
        line for line in outbox_lines
        if args.objective in str(line.get("subject") or "")
    ]
    record = {
        "schema": "atom-composite-long-running-verify-2",
        "status": "passed",
        "active": {
            "run_id": part1["run_id"],
            "status": active_state["assignment"]["status"],
            "teaching_revision": active_state["assignment"]["teaching_revision"],
            "mapping": active_state["assignment"]["mappings"],
            "result_value": _result_value(active_state, "source-1"),
            "artifact": active_artifact,
        },
        "second": {
            "run_id": second_run["run_id"],
            "status": second_state["assignment"]["status"],
            "teaching_revision": second_state["assignment"]["teaching_revision"],
            "mapping": second_state["assignment"]["mappings"],
            "result_value": _result_value(second_state, "source-1"),
            "artifact": second_artifact,
        },
        "teaching_revision_changed_for_new_work": (
            second_state["assignment"]["teaching_revision"]
            != active_state["assignment"]["teaching_revision"]),
        "outbox": final_lines,
        "outbox_all_lines": len(outbox_lines),
    }
    expected = {
        "active_revision": part1["teaching_revision"],
        "active_column": args.active_column,
        "concept": args.measure,
        "active_result": args.expected_active_result,
        "active_font": args.expected_active_font,
        "active_size": args.expected_active_size,
        "active_sha": args.expected_active_sha,
        "second_column": args.second_candidate,
        "second_result": args.expected_second_result,
        "second_font": args.expected_second_font,
        "second_size": args.expected_second_size,
        "second_sha": args.expected_second_sha,
        "subject_prefix": args.subject_prefix,
        "greeting": args.greeting,
        "signature": args.signature,
    }
    try:
        validate(record, expected)
    except AssertionError as exc:
        record["status"] = "failed"
        record["failure"] = str(exc)
        (out / "verify.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record, indent=2))
        return 1

    if args.negative_controls:
        negative_controls(record, expected, out)

    (out / "verify.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"VERIFY FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2)
