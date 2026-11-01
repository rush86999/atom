#!/usr/bin/env python3
"""Qualify the deterministic taught-rule method on the frozen 24-record set.

This is intentionally NOT a model campaign. It encodes the two frozen policies
as ordered rules, evaluates them with the same rule engine the canvas uses,
and applies the existing safe-abstention judge. The result is a separate
qualification for rule-expressible policies; model-dependent judgment remains
failed and unqualified.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))

from core.assessment_rules import evaluate_row, validate_decision_rules  # noqa: E402
from substantive_assessment_campaign import _judge  # noqa: E402

SET = ROOT / "scripts/acceptance/qualification/assessment_qualification_set_2026-10-31.json"


def _rules_v1() -> List[Dict[str, Any]]:
    return [
        {"decision": "DENY", "when": [
            {"field": "Status", "op": "eq", "value": "Closed"}],
         "basis": "Closed records are denied unconditionally."},
        {"decision": "REVIEW", "when": [
            {"field": "Status", "op": "blank"}],
         "basis": "Status is required to evaluate the policy."},
        {"decision": "REVIEW", "when": [
            {"field": "Amount", "op": "blank"}],
         "basis": "Amount is required to evaluate the policy."},
        {"decision": "REVIEW", "when": [
            {"field": "Risk", "op": "blank"}],
         "basis": "Risk is required by the V1 approval rule."},
        {"decision": "APPROVE", "when": [
            {"field": "Status", "op": "eq", "value": "Open"},
            {"field": "Amount", "op": "gte", "value": 100},
            {"field": "Risk", "op": "eq", "value": "Low"}],
         "basis": "Open, Amount >= 100, Risk Low."},
        {"decision": "REVIEW", "when": [
            {"field": "Status", "op": "eq", "value": "Open"},
            {"field": "Amount", "op": "gte", "value": 100},
            {"field": "Risk", "op": "eq", "value": "High"}],
         "basis": "Open and Amount >= 100 with Risk High."},
        {"decision": "REVIEW", "when": [
            {"field": "Status", "op": "eq", "value": "Open"},
            {"field": "Amount", "op": "gte", "value": 50},
            {"field": "Amount", "op": "lte", "value": 99}],
         "basis": "Open and Amount in the 50-99 band."},
    ]


def _rules_v3() -> List[Dict[str, Any]]:
    return [
        {"decision": "DENY", "when": [
            {"field": "Status", "op": "eq", "value": "Closed"}],
         "basis": "Closed records are denied unconditionally."},
        {"decision": "REVIEW", "when": [
            {"field": "Status", "op": "blank"}],
         "basis": "Status is required to evaluate the policy."},
        {"decision": "REVIEW", "when": [
            {"field": "Amount", "op": "blank"}],
         "basis": "Amount is required to evaluate the policy."},
        {"decision": "REVIEW", "when": [
            {"field": "Risk", "op": "blank"}],
         "basis": "Risk is blank; abstain despite the V3 wording."},
        {"decision": "APPROVE", "when": [
            {"field": "Status", "op": "eq", "value": "Open"},
            {"field": "Amount", "op": "gte", "value": 100}],
         "basis": "Open and Amount >= 100 regardless of Risk."},
        {"decision": "REVIEW", "when": [
            {"field": "Status", "op": "eq", "value": "Open"},
            {"field": "Amount", "op": "gte", "value": 50},
            {"field": "Amount", "op": "lte", "value": 99}],
         "basis": "Open and Amount in the 50-99 band."},
    ]


def _result(dataset: Dict[str, Any], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    columns = dataset["columns"]
    cleaned = validate_decision_rules(
        rules, columns=columns, decisions=["APPROVE", "REVIEW", "DENY"])
    assessments = []
    for row in dataset["rows"]:
        cells = dict(zip(columns, row))
        outcome = evaluate_row(cells, cleaned, fallback="REVIEW")
        assessments.append({
            "subject_id": cells["Ref"],
            "decision": outcome["decision"],
            "basis": outcome["basis"],
            "unresolved_requirements": outcome["unresolved"],
        })
    return {
        "success": True,
        "certified": True,
        "route": {"served_provider": "deterministic",
                  "served_model": "taught_rules"},
        "subjects": list(dataset["subjects"]),
        "policy_revision": "deterministic-frozen",
        "assessments": assessments,
    }


def run_qualification() -> Dict[str, Any]:
    dataset = json.loads(SET.read_text())
    phases = {}
    for label, phase, rules in (
            ("v1", "create", _rules_v1()),
            ("v3", "correct", _rules_v3()),
    ):
        judgment = _judge(_result(dataset, rules), dataset, phase, strict=False)
        phases[label] = {
            "phase": phase,
            "rules": rules,
            "judgment": judgment,
        }
    ok = all(item["judgment"].get("ok") for item in phases.values())
    return {
        "schema": "atom-deterministic-assessment-qualification-1",
        "dataset": dataset["id"],
        "dataset_sha256": dataset.get("sha256"),
        "configuration": {
            "mode": "deterministic",
            "provider": "none",
            "model": "none",
            "engine": "core.assessment_rules",
            "policy_scope": "rule-expressible taught policies only",
        },
        "phases": phases,
        "qualified": ok,
        "verdict": (
            "qualified for rule-expressible policies"
            if ok else "not qualified"),
        "not_claimed": (
            "Model-dependent substantive judgment, arbitrary natural-language "
            "policy interpretation, and live sending remain unqualified."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run_qualification()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({
        "qualified": result["qualified"],
        "verdict": result["verdict"],
        "v1": result["phases"]["v1"]["judgment"].get("judgment"),
        "v3": result["phases"]["v3"]["judgment"].get("judgment"),
    }, indent=2))
    return 0 if result["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
