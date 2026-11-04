#!/usr/bin/env python3
"""Verify the frozen procurement-selection positive and missing-source twin."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Mapping

CORRECT = {
    "invoice": "ap-inbox-0412.json",
    "purchase_order": "po-archive-88.json",
    "receiving": "dock-receipt-19.json",
}
WRONG = {
    "ap-inbox-0411.json", "ap-inbox-0402.json",
    "dock-receipt-07.json", "warehouse-memo.txt",
}
EXPECTED = "121.00"


def durable(db: str, run_id: str) -> Dict[str, Any]:
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "select parameters from goal_runs where id = ?",
            (run_id,)).fetchone()
    finally:
        connection.close()
    if not row:
        return {}
    lifecycle = json.loads(row[0] or "{}").get("task_lifecycle") or {}
    return lifecycle.get("assignment") or {}


def step_by_id(assignment: Mapping[str, Any], step_id: str) -> Dict[str, Any]:
    return next((
        dict(item) for item in assignment.get("steps") or []
        if str(item.get("step_id") or "") == str(step_id)), {})


def source_name(step: Mapping[str, Any]) -> str:
    binding = ((step.get("inputs") or {}).get("resource_binding")
               if isinstance(step.get("inputs"), dict) else None)
    if not isinstance(binding, Mapping):
        return ""
    return str(
        binding.get("original_file_name") or binding.get("file_name") or "")


def role_bindings(assignment: Mapping[str, Any]) -> Dict[str, Any]:
    reconcile = next((
        dict(item) for item in assignment.get("steps") or []
        if item.get("adapter") == "invoice.reconcile"), {})
    inputs = reconcile.get("inputs") if isinstance(
        reconcile.get("inputs"), dict) else {}
    refs = {}
    for role in ("invoice", "purchase_order", "receiving"):
        match = re.match(r"\$\{([^}]+)\.data\}", str(inputs.get(role) or ""))
        step_id = match.group(1) if match else ""
        step = step_by_id(assignment, step_id)
        refs[role] = {
            "step_id": step_id,
            "file_name": source_name(step),
            "data": (step.get("result") or {}).get("data") or {},
            "value": (step.get("result") or {}).get("value"),
        }
    return {
        "step": reconcile,
        "refs": refs,
        "value": (reconcile.get("result") or {}).get("value"),
        "depends_on": list(reconcile.get("depends_on") or []),
    }


def model_selected_files(state: Mapping[str, Any]) -> List[str]:
    upload_names = {
        value: name for name, value in (state.get("uploads") or {}).items()
        if isinstance(value, str)
    }
    selected: List[str] = []

    def add_sources(values):
        for value in values or []:
            name = upload_names.get(str(value))
            if name:
                selected.append(name)

    initial = state.get("initial_proposal") or {}
    if state.get("initial_proposal_source") == "model":
        add_sources([read.get("source_id")
                     for read in initial.get("evidence_reads") or []])
    for item in state.get("initial_adaptive_rounds") or []:
        if not isinstance(item, Mapping):
            continue
        if item.get("source") == "model":
            add_sources(item.get("proposal_sources"))
        if item.get("repair_source") == "model":
            add_sources(item.get("repair_sources"))
    for item in state.get("advance_rounds") or []:
        for round_item in (item.get("rounds") or []
                           if isinstance(item, Mapping) else []):
            if not isinstance(round_item, Mapping):
                continue
            if round_item.get("source") == "model":
                add_sources(round_item.get("proposal_sources"))
            if round_item.get("repair_source") == "model":
                add_sources(round_item.get("repair_sources"))
    return sorted(set(selected))


def _routing_stage(item: Mapping[str, Any], profile: str) -> str:
    if profile == "employee_evidence_selection":
        return "evidence_selection"
    if profile in (
            "employee_adaptive_planning_compact",
            "employee_adaptive_planning"):
        return "adaptation"
    if profile == "employee_wait_choice":
        return "wait_choice"
    if item.get("decision") in ("replan", "reconcile"):
        return "adaptation"
    if item.get("proposal_kind") in (
            "evidence_read", "evidence_and_clarification", "clarification"):
        return "evidence_selection"
    return "adaptation" if item.get("decision") else "evidence_selection"


def routing_summary(state: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in state.get("initial_adaptive_rounds") or []:
        if not isinstance(item, Mapping):
            continue
        routing = item.get("routing") or {}
        profile = str((routing.get("profile") or {}).get("name") or "")
        stage = _routing_stage(item, profile)
        decision = item.get("decision")
        proposal_kind = item.get("proposal_kind")
        outcome = (
            decision
            or proposal_kind
            or ("selected_sources" if item.get("selected_sources")
                else "no_result"))
        rows.append({
            "stage": stage,
            "source": item.get("source"),
            "repair_source": item.get("repair_source"),
            "profile": profile or None,
            "served_route": routing.get("served_route"),
            "decision": decision,
            "proposal_kind": proposal_kind,
            "outcome": outcome,
        })
    for item in state.get("advance_rounds") or []:
        for round_item in (item.get("rounds") or []
                           if isinstance(item, Mapping) else []):
            if not isinstance(round_item, Mapping):
                continue
            routing = round_item.get("routing") or {}
            profile = str((routing.get("profile") or {}).get("name") or "")
            stage = _routing_stage(round_item, profile)
            rows.append({
                "stage": stage,
                "source": round_item.get("source"),
                "profile": profile or None,
                "served_route": routing.get("served_route"),
                "decision": round_item.get("decision"),
                "proposal_kind": round_item.get("proposal_kind"),
                "outcome": (
                    round_item.get("decision")
                    or round_item.get("proposal_kind")
                    or "no_result"),
            })
    return rows


def attempt_summary(path: Path) -> Dict[str, Any]:
    rows = []
    if path.is_file():
        rows = [json.loads(line) for line in path.read_text().splitlines()
                if line.strip()]
    dispatches = [r for r in rows if r.get("event") == "dispatch"]
    parsed = [r for r in rows if r.get("event") == "parsed"]
    failures = [r for r in rows if r.get("event") in (
        "failure", "no_result")]
    seconds = sum(float(r.get("seconds") or 0) for r in parsed)
    usage = [r.get("usage") or {} for r in parsed]
    return {
        "events": len(rows),
        "dispatches": len(dispatches),
        "parsed": len(parsed),
        "failures_or_no_results": len(failures),
        "parsed_seconds": round(seconds, 3),
        "prompt_tokens": sum(int(u.get("prompt_tokens") or 0)
                             for u in usage),
        "completion_tokens": sum(int(u.get("completion_tokens") or 0)
                                 for u in usage),
        "profiles": sorted({
            str((r.get("routing") or {}).get("profile") or "")
            for r in rows if r.get("routing")} - {""}),
    }


def fixture_hashes(root: Path) -> Dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.iterdir()) if path.is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--positive-state", required=True)
    parser.add_argument("--missing-state", required=True)
    parser.add_argument("--attempts", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    positive = json.loads(Path(args.positive_state).read_text())
    missing = json.loads(Path(args.missing_state).read_text())
    p_run = positive["run_id"]
    m_run = missing["run_id"]
    p_assign = durable(args.db, p_run)
    m_assign = durable(args.db, m_run)
    p_roles = role_bindings(p_assign)
    m_roles = role_bindings(m_assign)
    p_model = set(model_selected_files(positive))
    m_model = set(model_selected_files(missing))
    p_checks = {
        "assignment_completed": p_assign.get("status") == "completed",
        "reconciliation_121": p_roles.get("value") == EXPECTED,
        "correct_invoice_role": (
            p_roles["refs"]["invoice"]["file_name"] == CORRECT["invoice"]),
        "correct_purchase_order_role": (
            p_roles["refs"]["purchase_order"]["file_name"]
            == CORRECT["purchase_order"]),
        "correct_receiving_role": (
            p_roles["refs"]["receiving"]["file_name"]
            == CORRECT["receiving"]),
        "no_wrong_or_obsolete_role": not {
            p_roles["refs"][role]["file_name"]
            for role in ("invoice", "purchase_order", "receiving")
        } & WRONG,
        "correct_files_read": {
            CORRECT["invoice"], CORRECT["purchase_order"],
            CORRECT["receiving"]} <= {
                source_name(item) for item in p_assign.get("steps") or []
                if item.get("adapter") in ("document.text", "document.read")},
        "outcome_satisfied": (
            (positive.get("final") or {}).get("business_outcome") or {}
        ).get("state") == "satisfied",
        "no_injected_total": "999.99" not in json.dumps(
            p_roles["refs"], default=str),
        "model_selected_invoice": CORRECT["invoice"] in p_model,
        "model_selected_purchase_order": CORRECT["purchase_order"] in p_model,
        "model_selected_receiving": CORRECT["receiving"] in p_model,
    }
    before = missing.get("before_add_final") or {}
    questions = " ".join(
        str(item.get("question") or "")
        for item in missing.get("before_add_questions") or [])
    m_checks = {
        "before_add_not_completed": before.get("status") != "completed",
        "targeted_invoice_question": (
            "invoice" in questions.lower()
            and ("INV-SEL-77" in questions or "PO-SEL-520" in questions)),
        "question_is_missing_invoice": "invoice" in questions.lower(),
        "no_reconciliation_before_add": not any(
            item.get("adapter") == "invoice.reconcile"
            and item.get("status") == "applied"
            for item in before.get("steps") or []),
        "no_artifact_before_add": not any(
            item.get("adapter") == "artifact.document"
            and item.get("status") == "applied"
            for item in before.get("steps") or []),
        "same_run_recovered": m_roles.get("step") != {},
        "recovery_completed": m_assign.get("status") == "completed",
        "recovery_121": m_roles.get("value") == EXPECTED,
        "recovery_correct_invoice": (
            m_roles["refs"]["invoice"]["file_name"] == CORRECT["invoice"]),
        "recovery_correct_purchase_order": (
            m_roles["refs"]["purchase_order"]["file_name"]
            == CORRECT["purchase_order"]),
        "recovery_correct_receiving": (
            m_roles["refs"]["receiving"]["file_name"]
            == CORRECT["receiving"]),
        "recovery_outcome_satisfied": (
            (missing.get("final") or {}).get("business_outcome") or {}
        ).get("state") == "satisfied",
        "question_resolved": not (missing.get("final") or {}).get(
            "open_questions"),
        "model_backed_recovery": any(
            isinstance(round_item, Mapping)
            and round_item.get("source") in (
                "model", "model_compact", "model_repaired")
            for item in missing.get("advance_rounds") or []
            if isinstance(item, Mapping)
            for round_item in item.get("rounds") or []),
    }
    verification = {
        "source": "7d4358ea6708f1c568caed78e972ad2f0c79d8f8",
        "positive": {
            "run_id": p_run,
            "value": p_roles.get("value"),
            "roles": {
                role: {
                    "step_id": p_roles["refs"][role]["step_id"],
                    "file_name": p_roles["refs"][role]["file_name"],
                } for role in ("invoice", "purchase_order", "receiving")},
            "model_selected_files": sorted(p_model),
            "checks": p_checks,
            "all_passed": all(p_checks.values()),
            "routing": routing_summary(positive),
        },
        "missing": {
            "run_id": m_run,
            "before_add_question": questions or None,
            "before_add_checks": {
                "not_completed": before.get("status") != "completed",
                "targeted_invoice_question": (
                    "invoice" in questions.lower()
                    and ("INV-SEL-77" in questions
                         or "PO-SEL-520" in questions)),
                "no_reconciliation": not any(
                    item.get("adapter") == "invoice.reconcile"
                    and item.get("status") == "applied"
                    for item in before.get("steps") or []),
            },
            "after_add": {
                "value": m_roles.get("value"),
                "roles": {
                    role: {
                        "step_id": m_roles["refs"][role]["step_id"],
                        "file_name": m_roles["refs"][role]["file_name"],
                    } for role in ("invoice", "purchase_order", "receiving")},
                "model_selected_files": sorted(m_model),
            },
            "checks": m_checks,
            "all_passed": all(m_checks.values()),
            "routing": routing_summary(missing),
        },
        "attempts": attempt_summary(Path(args.attempts)),
        "fixtures": fixture_hashes(Path(args.fixtures)),
    }
    verification["all_passed"] = (
        verification["positive"]["all_passed"]
        and verification["missing"]["all_passed"])
    Path(args.out).write_text(json.dumps(verification, indent=1) + "\n")
    print(json.dumps({
        "positive_checks": p_checks,
        "missing_checks": m_checks,
        "all_passed": verification["all_passed"],
        "positive_value": p_roles.get("value"),
        "missing_value": m_roles.get("value"),
    }, indent=1))
    return 0 if verification["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
