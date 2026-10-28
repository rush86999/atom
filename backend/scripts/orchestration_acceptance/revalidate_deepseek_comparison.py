#!/usr/bin/env python3
"""Re-validate SAVED DeepSeek responses without calling the model.

The one-shot harness originally bound the full-context validator to only
IN-7301, so the correct three-subject response was reported as
``unrequested_subject``. This script rebuilds the frozen request contract from
SPEC.json and re-runs the product validator against the same saved raw
responses. It makes no external call and does not change a decision.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE))

from compare_deepseek_judgment import _build_requests  # noqa: E402
from core.review_result import build_review_result  # noqa: E402


def _content(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return str(payload.get("content") or "")
    return str((choices[0].get("message") or {}).get("content") or "")


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: revalidate_deepseek_comparison.py <comparison-dir>",
            file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    spec = json.loads((root / "SPEC.json").read_text(encoding="utf-8"))
    results = json.loads((root / "results.json").read_text(encoding="utf-8"))
    source = json.loads(
        (Path(__file__).resolve().parents[3]
         / spec["source"]["preserved_request"]).read_text(encoding="utf-8"))
    prepared = {
        case["case_id"]: case for case in _build_requests(spec, source)
    }
    cases = []
    for case in results["cases"]:
        frozen = prepared[case["case_id"]]
        response = json.loads(
            (root / case["response_file"]).read_text(encoding="utf-8"))
        review = build_review_result(
            execution_id=frozen["execution_id"],
            requested_records=frozen["requested_records"],
            answer=_content(response),
            allowed_decisions=frozen["allowed_decisions"],
            evidence_index=frozen["evidence_index"],
            policy_index=frozen["policy_index"],
        )
        review_file = f"cases/{case['case_id']}_revalidated_review.json"
        (root / review_file).write_text(
            json.dumps(review, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")
        cases.append({
            **case,
            "requested_records": frozen["requested_records"],
            "certified": bool(review.get("ok")),
            "errors": review.get("errors") or [],
            "decisions": [
                {
                    "subject_id": assessment.get("subject_id"),
                    "decision": assessment.get("decision"),
                }
                for assessment in review.get("assessments") or []
            ],
            "revalidated_review_file": review_file,
        })
    revalidated = {
        **results,
        "schema": "deepseek-judgment-comparison-revalidated-1",
        "validation_note": (
            "Offline re-validation of saved raw responses with the accepted "
            "subject set. No model call, no decision rewrite."),
        "cases": cases,
        "summary": {
            "raw_judgment_matches": sum(
                1 for case in cases if case["substantive_match"]),
            "certified": sum(1 for case in cases if case["certified"]),
            "total_cases": len(cases),
            "expected_total_cases": 7,
            "raw_and_certified": sum(
                1 for case in cases
                if case["substantive_match"] and case["certified"]),
        },
    }
    (root / "revalidated_results.json").write_text(
        json.dumps(revalidated, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps(revalidated["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
