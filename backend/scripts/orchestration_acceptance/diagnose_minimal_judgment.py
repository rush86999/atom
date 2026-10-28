#!/usr/bin/env python3
"""One-shot judgment diagnosis: minimal complete input vs the preserved context.

The preserved failing case is IN-7301 (Invoice Amount 3200) under the single
current corrected policy. This script sends:

* the exact preserved full-context request (14 messages, captured by the
  product's review-diagnosis seam at execution 605af591...); and
* a minimal request containing only that row, that policy, the task-owned
  decision vocabulary and the same review output contract.

It then runs a fixed boundary set through the SAME minimal shape. Labels are
derived from the policy text, never from an ordering such as
HOLD > DECLINE. Every response is written once; the script refuses to
overwrite an existing result file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from core.review_result import (  # noqa: E402
    build_review_result,
    parse_review_payload,
    review_output_instruction,
)


DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _money(value: str) -> Decimal:
    return Decimal(value.replace(",", "").strip())


def expected_from_policy(amount: Decimal, lesson: str) -> str:
    """Read the label from the lesson's own thresholds.

    No label is preferred over another: the only rule applied is the text the
    task taught. An amount outside the written ranges is an error, not a
    default safety choice.
    """
    text = " ".join(str(lesson or "").split())
    below = re.search(
        r"below\s+([\d,]+(?:\.\d+)?)\s+is\s+([A-Za-z]+)", text, re.I)
    band = re.search(
        r"([\d,]+(?:\.\d+)?)\s+to\s+([\d,]+(?:\.\d+)?)\s+is\s+([A-Za-z]+)",
        text, re.I)
    above = re.search(
        r"at\s+or\s+above\s+([\d,]+(?:\.\d+)?)\s+is\s+([A-Za-z]+)",
        text, re.I)
    if below and amount < _money(below.group(1)):
        return below.group(2).upper()
    if band and _money(band.group(1)) <= amount <= _money(band.group(2)):
        return band.group(3).upper()
    if above and amount >= _money(above.group(1)):
        return above.group(2).upper()
    raise ValueError(f"amount {amount} is outside the taught ranges")


def _diagnostic(entry: dict) -> dict:
    return {
        "evidence_id": entry["evidence_id"],
        "subject_id": entry["subject_id"],
        "source_identity": dict(entry["source_identity"]),
        "retrieval_operation": entry["retrieval_operation"],
        "retrieval_execution_id": entry["retrieval_execution_id"],
        "row_ref": entry.get("row_ref"),
        "target_status": entry.get("target_status"),
        "values": list(entry.get("values") or []),
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")


def _post_ollama(
    client: httpx.Client,
    base_url: str,
    model: str,
    messages: list[dict],
    *,
    temperature: float,
    max_tokens: int,
) -> dict:
    response = client.post(
        base_url.rstrip("/") + "/v1/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        },
        timeout=300.0,
    )
    response.raise_for_status()
    return response.json()


def _decision_for(review: dict, subject: str) -> str | None:
    for assessment in review.get("assessments") or []:
        if str(assessment.get("subject_id") or "") == subject:
            return str(assessment.get("decision") or "")
    for assessment in review.get("candidate_assessments") or []:
        if str(assessment.get("subject_id") or "") == subject:
            return str(assessment.get("decision") or "")
    return None


def _minimal_request(
    subject: str,
    amount: float,
    evidence_entry: dict,
    policy_entry: dict,
    allowed: list[str],
) -> tuple[list[dict], dict, list[dict], list[dict]]:
    contract = {
        "subjects": [subject],
        "allowed_decisions": list(allowed),
        "required_actions": [],
    }
    evidence_index = [_diagnostic(evidence_entry)]
    policy_index = [dict(policy_entry)]
    instruction = review_output_instruction(
        contract, evidence_index, policy_index)
    values = "; ".join(
        f"{item.get('field')}={item.get('value')}"
        for item in (evidence_entry.get("values") or [])
        if isinstance(item, dict)
    )
    source = evidence_entry.get("source_identity") or {}
    row_message = (
        "AUTHORITATIVE BOUND ROW (the only row in this request):\n"
        f"- source: {source.get('file_name')} | version: "
        f"{source.get('content_hash')}\n"
        f"- row: {evidence_entry.get('row_ref')} | subject: {subject}\n"
        f"- values: {values}\n"
        "Apply the policy below to these values."
    )
    messages = [
        {"role": "system", "content": instruction},
        {"role": "system", "content": row_message},
        {
            "role": "user",
            "content": (
                f"Assess {subject} under the taught threshold rule. "
                "Give the decision."
            ),
        },
    ]
    return messages, contract, evidence_index, policy_index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-request", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument(
        "--full-response",
        help=(
            "Preserve the already-captured full-context response instead of "
            "re-sending the full prompt. The minimal cases still run once."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source_path = Path(args.source_request).resolve()
    out_dir = Path(args.out_dir).resolve()
    results_path = out_dir / "results.json"
    if results_path.exists():
        print(
            f"REFUSING TO OVERWRITE preserved results: {results_path}",
            file=sys.stderr,
        )
        return 2

    source = json.loads(source_path.read_text(encoding="utf-8"))
    full_messages = list(source["messages"])
    evidence_index = list(source["evidence_index"])
    policy_index = list(source["policy_index"])
    allowed = list(source["allowed_decisions"])
    subjects = list(source["subjects"])
    preserved = next(
        entry for entry in evidence_index if entry.get("subject_id") == "IN-7301")
    policy = policy_index[0]
    amount = Decimal("3200")

    # Fixed boundary set. The preserved 3200 row is authoritative; the others
    # are deliberately unfamiliar values around the policy's own boundaries.
    cases = [
        {
            "case_id": "preserved_3200",
            "subject": "IN-7301",
            "amount": "3200",
            "row_ref": preserved.get("row_ref"),
            "preserved_row": True,
        },
        {
            "case_id": "unfamiliar_4321_25",
            "subject": "IN-8801",
            "amount": "4321.25",
            "row_ref": "minimal_judgment!R2",
            "preserved_row": False,
        },
        {
            "case_id": "boundary_4999_99",
            "subject": "IN-8802",
            "amount": "4999.99",
            "row_ref": "minimal_judgment!R3",
            "preserved_row": False,
        },
        {
            "case_id": "boundary_5000",
            "subject": "IN-8803",
            "amount": "5000",
            "row_ref": "minimal_judgment!R4",
            "preserved_row": False,
        },
        {
            "case_id": "boundary_9999",
            "subject": "IN-8804",
            "amount": "9999",
            "row_ref": "minimal_judgment!R5",
            "preserved_row": False,
        },
        {
            "case_id": "boundary_10000",
            "subject": "IN-8805",
            "amount": "10000",
            "row_ref": "minimal_judgment!R6",
            "preserved_row": False,
        },
    ]
    for case in cases:
        case["expected"] = expected_from_policy(
            _money(case["amount"]), str(policy.get("lesson") or ""))

    if args.dry_run:
        print(json.dumps({
            "source_request": str(source_path),
            "source_sha256": sha256(source_path),
            "model": args.model,
            "cases": cases,
            "full_context_messages": len(full_messages),
        }, indent=1))
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(trust_env=False)

    # Full-context result. Reuse the captured failing UI response when
    # supplied; otherwise send the exact preserved messages once.
    if args.full_response:
        full_response_path = Path(args.full_response).resolve()
        full_response = json.loads(
            full_response_path.read_text(encoding="utf-8"))
        full_content = str(full_response.get("content") or "")
        full_request_file = "preserved_full_request.json"
        full_response_file = "preserved_full_response.json"
        _write_json(out_dir / "full_review.json", {})
    else:
        full_response = _post_ollama(
            client, args.base_url, args.model, full_messages,
            temperature=args.temperature, max_tokens=args.max_tokens)
        full_content = str(
            ((full_response.get("choices") or [{}])[0].get("message") or {})
            .get("content") or "")
        full_response_path = None
        full_request_file = "full_request.json"
        full_response_file = "full_response.json"
        _write_json(out_dir / "full_request.json", source)
        _write_json(out_dir / "full_response.json", full_response)
    execution_id = str(source.get("execution_id") or "preserved-full")
    full_review = build_review_result(
        execution_id=execution_id,
        requested_records=subjects,
        answer=full_content,
        allowed_decisions=allowed,
        evidence_index=evidence_index,
        policy_index=policy_index,
    )
    full_decision = _decision_for(full_review, "IN-7301")
    _write_json(out_dir / "full_review.json", full_review)
    full_case = {
        "case_id": "preserved_full_context",
        "subject": "IN-7301",
        "amount": "3200",
        "expected": expected_from_policy(amount, str(policy.get("lesson") or "")),
        "decision": full_decision,
        "matches_policy": full_decision == expected_from_policy(
            amount, str(policy.get("lesson") or "")),
        "certified": bool(full_review.get("ok")),
        "errors": full_review.get("errors") or [],
        "request_file": full_request_file,
        "response_file": full_response_file,
        "review_file": "full_review.json",
        "response_source": (
            str(full_response_path) if full_response_path else "live_replay"),
    }

    minimal_cases = []
    case_dir = out_dir / "cases"
    for case in cases:
        if case["preserved_row"]:
            evidence_entry = dict(preserved)
        else:
            evidence_entry = {
                "evidence_id": (
                    f"ev:{case['subject']}:minimal_judgment!R"
                    f"{case['row_ref'].rsplit('R', 1)[-1]}"),
                "subject_id": case["subject"],
                "source_identity": {
                    "file_name": "minimal_judgment_eval.csv",
                    "resource_id": "eval:minimal_judgment",
                    "content_hash": "eval:minimal_judgment",
                },
                "retrieval_operation": f"eval:{case['case_id']}",
                "retrieval_execution_id": f"eval-{case['case_id']}",
                "row_ref": case["row_ref"],
                "target_status": "matched",
                "values": [
                    {"field": "Invoice Amount", "value": float(case["amount"])},
                    {"field": "State", "value": "Open"},
                ],
            }
        messages, contract, case_evidence, case_policy = _minimal_request(
            case["subject"], float(case["amount"]), evidence_entry,
            policy, allowed)
        response = _post_ollama(
            client, args.base_url, args.model, messages,
            temperature=args.temperature, max_tokens=args.max_tokens)
        content = str(
            ((response.get("choices") or [{}])[0].get("message") or {})
            .get("content") or "")
        review = build_review_result(
            execution_id=f"minimal-{case['case_id']}",
            requested_records=[case["subject"]],
            answer=content,
            allowed_decisions=allowed,
            evidence_index=case_evidence,
            policy_index=case_policy,
            accepted_contract=None,
        )
        decision = _decision_for(review, case["subject"])
        request_file = f"cases/{case['case_id']}_request.json"
        response_file = f"cases/{case['case_id']}_response.json"
        review_file = f"cases/{case['case_id']}_review.json"
        _write_json(out_dir / request_file, {
            "messages": messages,
            "contract": contract,
            "evidence_index": case_evidence,
            "policy_index": case_policy,
        })
        _write_json(out_dir / response_file, response)
        _write_json(out_dir / review_file, review)
        minimal_cases.append({
            **case,
            "decision": decision,
            "matches_policy": decision == case["expected"],
            "certified": bool(review.get("ok")),
            "errors": review.get("errors") or [],
            "request_file": request_file,
            "response_file": response_file,
            "review_file": review_file,
        })

    summary = {
        "full_context_matches": bool(full_case["matches_policy"]),
        "full_context_certified": bool(full_case["certified"]),
        "minimal_matches": sum(
            1 for case in minimal_cases if case["matches_policy"]),
        "minimal_total": len(minimal_cases),
        "minimal_certified": sum(
            1 for case in minimal_cases if case["certified"]),
        "all_minimal_match": all(
            case["matches_policy"] for case in minimal_cases),
    }
    result = {
        "schema": "minimal-judgment-diagnosis-1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_request": str(source_path),
        "source_request_sha256": sha256(source_path),
        "settings": {
            "provider": "ollama",
            "base_url": args.base_url,
            "model": args.model,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "stream": False,
            "review_structured": "0",
            "local_only": "true",
        },
        "policy": {
            "policy_id": policy.get("policy_id"),
            "topic": policy.get("topic"),
            "lesson": policy.get("lesson"),
            "allowed_decisions": allowed,
        },
        "full_context": full_case,
        "minimal_cases": minimal_cases,
        "summary": summary,
        "interpretation_rule": (
            "A label is correct only when the applicable teaching's own "
            "threshold text yields it. No decision label has an inherent "
            "safety rank."
        ),
    }
    _write_json(results_path, result)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
