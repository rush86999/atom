#!/usr/bin/env python3
"""Separate substance from format in the preserved minimal-judgment run.

This is diagnostic only. It does NOT certify anything and it never changes a
decision. It reads the already-saved responses, extracts the decision the
model actually wrote (including from a malformed fence), and compares it to
the label the policy text yields. Certification remains the product
validator's ``build_review_result`` result.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _content(payload: dict) -> str:
    if isinstance(payload.get("content"), str):
        return payload["content"]
    choices = payload.get("choices") or []
    if choices and isinstance(choices[0], dict):
        return str((choices[0].get("message") or {}).get("content") or "")
    return ""


def _all_json_objects(text: str):
    for match in re.finditer(
            r"```[a-zA-Z0-9_:-]*\s*(\{.*?\})\s*```", text, re.DOTALL):
        try:
            yield json.loads(match.group(1))
        except Exception:  # noqa: BLE001
            continue
    for match in re.finditer(r"(\{.*\})", text, re.DOTALL):
        try:
            value = json.loads(match.group(1))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(value, dict):
            yield value


def _raw_decision(text: str, subject: str) -> str | None:
    for payload in _all_json_objects(text):
        assessments = payload.get("assessments")
        if not isinstance(assessments, list):
            continue
        for assessment in assessments:
            if not isinstance(assessment, dict):
                continue
            if str(assessment.get("subject_id") or "") == subject:
                return str(assessment.get("decision") or "")
    return None


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: analyze_minimal_judgment.py <evidence-dir>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    results_path = root / "results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))

    def analyze(record: dict, subject: str) -> dict:
        content = _content(json.loads(
            (root / record["response_file"]).read_text(encoding="utf-8")))
        raw = _raw_decision(content, subject)
        return {
            "subject": subject,
            "expected": record["expected"],
            "raw_decision": raw,
            "substantive_match": raw == record["expected"],
            "certified": bool(record.get("certified")),
            "certification_errors": [
                error.get("code") for error in (record.get("errors") or [])
                if isinstance(error, dict)
            ],
            "format_parseable": raw is not None,
        }

    full = analyze(results["full_context"], "IN-7301")
    cases = [
        {"case_id": record["case_id"], **analyze(record, record["subject"])}
        for record in results["minimal_cases"]
    ]
    analysis = {
        "schema": "minimal-judgment-analysis-1",
        "results_sha256": _sha256(results_path),
        "note": (
            "Substance is the decision written in the response JSON. "
            "Certification is the product validator's separate reference/shape "
            "result. No decision was rewritten, and no label is ranked."
        ),
        "full_context": full,
        "minimal_cases": cases,
        "summary": {
            "full_context_substantive_match": full["substantive_match"],
            "full_context_certified": full["certified"],
            "minimal_substantive_matches": sum(
                1 for case in cases if case["substantive_match"]),
            "minimal_total": len(cases),
            "minimal_certified": sum(1 for case in cases if case["certified"]),
            "minimal_format_parseable": sum(
                1 for case in cases if case["format_parseable"]),
            "substantively_wrong": [
                case["case_id"] for case in cases
                if not case["substantive_match"]
            ],
        },
    }
    out_path = root / "analysis.json"
    out_path.write_text(
        json.dumps(analysis, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps(analysis["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
