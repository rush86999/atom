#!/usr/bin/env python3
"""Independent procurement evidence selection batch.

The user authorizes a broad pool of procurement documents, including wrong-PO,
obsolete, wrong-receiving and irrelevant candidates. The objective names the
business invoice/PO, never the answer files or role mapping. The employee must
read/select the correct invoice, matching PO and receiving record and complete
the reconciliation. The missing-source twin omits the valid invoice; the same
job must ask for that specific record and recover after an authorized addition.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

import requests

API = "http://127.0.0.1:8085"
PASSWORD = "G5Browser-2026!"
FIXTURES = Path("/private/tmp/atom-g5-source-selection")
OBJECTIVE = (
    "Reconcile supplier invoice INV-SEL-77 for purchase order PO-SEL-520 "
    "against the matching purchase order and the warehouse receiving record. "
    "Use only the authorized procurement workspace; do not use superseded or "
    "unrelated records.")
EXPECTED_RECONCILIATION = Decimal("121.00")
POOL = (
    "warehouse-memo.txt",
    "ap-inbox-0411.json",
    "dock-receipt-07.json",
    "ap-inbox-0402.json",
    "po-archive-88.json",
    "ap-inbox-0412.json",
    "dock-receipt-19.json",
)
MISSING_POOL = tuple(
    name for name in POOL if name != "ap-inbox-0412.json")


def token() -> str:
    response = requests.post(
        API + "/api/auth/login",
        json={"username": "admin@example.com", "password": PASSWORD},
        timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def headers(token_value: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token_value}"}


def upload(token_value: str, path: Path) -> Dict[str, Any]:
    with path.open("rb") as handle:
        response = requests.post(
            API + "/api/documents/upload",
            headers=headers(token_value),
            files={"file": (path.name, handle, "application/octet-stream")},
            timeout=120)
    response.raise_for_status()
    return response.json()


def record(body: Dict[str, Any]) -> Dict[str, Any]:
    container = body.get("assignment")
    if not isinstance(container, dict):
        return {}
    nested = container.get("assignment")
    return nested if isinstance(nested, dict) else container


def detail(token_value: str, run_id: str) -> Dict[str, Any]:
    response = requests.get(
        API + f"/api/assignments/{run_id}",
        headers=headers(token_value), timeout=60)
    response.raise_for_status()
    return response.json()


def step(assignment: Dict[str, Any], adapter: str) -> Dict[str, Any]:
    return next((
        item for item in assignment.get("steps") or []
        if item.get("adapter") == adapter), {})


def wait_for(token_value: str, run_id: str, states, timeout=900):
    deadline = time.time() + timeout
    body = {}
    while time.time() < deadline:
        body = detail(token_value, run_id)
        status = str(record(body).get("status") or "")
        if status in states:
            return body
        time.sleep(2)
    return body


def _evidence_steps(assignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "step_id": item.get("step_id"),
        "adapter": item.get("adapter"),
        "status": item.get("status"),
        "operation_id": item.get("operation_id"),
        "file_name": (
            (item.get("inputs") or {}).get("resource_binding") or {}
        ).get("original_file_name") or (
            (item.get("inputs") or {}).get("resource_binding") or {}
        ).get("file_name"),
        "resource_id": (
            (item.get("inputs") or {}).get("resource_binding") or {}
        ).get("resource_id"),
        "source_version": (
            (item.get("inputs") or {}).get("resource_binding") or {}
        ).get("source_version"),
    } for item in assignment.get("steps") or []
        if str(item.get("adapter") or "").startswith(
            ("document.", "dataset."))]


def _questions(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    job = body.get("employee_job") or {}
    return list(job.get("open_obligations") or [])


def _reconciliation(assignment: Dict[str, Any]) -> Dict[str, Any]:
    return step(assignment, "invoice.reconcile")


def _capture(token_value: str, run_id: str, state: Dict[str, Any]) -> None:
    body = detail(token_value, run_id)
    assignment = record(body)
    state["final_detail"] = body
    state["final"] = {
        "status": assignment.get("status"),
        "plan_revision": assignment.get("plan_revision"),
        "steps": _evidence_steps(assignment) + [{
            "step_id": item.get("step_id"),
            "adapter": item.get("adapter"),
            "status": item.get("status"),
            "operation_id": item.get("operation_id"),
            "result_value": item.get("result_value"),
            "depends_on": list(item.get("depends_on") or []),
            "inputs": dict(item.get("inputs") or {}),
        } for item in assignment.get("steps") or []
            if str(item.get("adapter") or "") in (
                "invoice.reconcile", "artifact.document")],
        "open_questions": _questions(body),
        "business_requirements": (
            body.get("employee_job") or {}).get(
                "business_requirements") or [],
        "business_outcome": (
            body.get("employee_job") or {}).get("business_outcome") or {},
    }


def _advance(token_value: str, run_id: str, state: Dict[str, Any],
             rounds: int = 2) -> None:
    for index in range(max(0, rounds)):
        advanced = requests.post(
            API + f"/api/assignments/{run_id}/advance",
            headers=headers(token_value),
            json={"use_model": True, "max_adaptations": 2,
                  "deadline_seconds": 600}, timeout=900)
        state.setdefault("advance_rounds", []).append({
            "status": advanced.status_code,
            "rounds": advanced.json().get("rounds")
            if advanced.headers.get("content-type", "").startswith(
                "application/json") else None,
        })
        advanced.raise_for_status()
        body = wait_for(
            token_value, run_id,
            {"completed", "failed", "blocked", "cancelled", "waiting"})
        if str(record(body).get("status")) in (
                "completed", "failed", "cancelled"):
            break


def _model_selected_correct(state: Dict[str, Any]) -> bool:
    upload_names = {
        value: name for name, value in (state.get("uploads") or {}).items()
        if isinstance(value, str)
    }
    selected = set()
    initial = state.get("initial_proposal") or {}
    if state.get("initial_proposal_source") == "model":
        for read in initial.get("evidence_reads") or []:
            name = upload_names.get(str(read.get("source_id") or ""))
            if name:
                selected.add(name)
    for item in state.get("initial_adaptive_rounds") or []:
        if isinstance(item, dict):
            if item.get("source") == "model":
                selected.update(
                    str(source) for source in
                    item.get("proposal_sources") or [])
            if item.get("repair_source") == "model":
                selected.update(
                    str(source) for source in
                    item.get("repair_sources") or [])
    for item in state.get("advance_rounds") or []:
        for round_item in item.get("rounds") or []:
            if not isinstance(round_item, dict):
                continue
            if round_item.get("source") == "model":
                selected.update(
                    str(source) for source in
                    round_item.get("proposal_sources") or [])
            if round_item.get("repair_source") == "model":
                selected.update(
                    str(source) for source in
                    round_item.get("repair_sources") or [])
    selected_names = {
        upload_names.get(source, source) for source in selected
    }
    return {
        "ap-inbox-0412.json", "po-archive-88.json",
        "dock-receipt-19.json",
    } <= selected_names


def _checks(state: Dict[str, Any]) -> Dict[str, bool]:
    final = state.get("final") or {}
    reconcile = next((
        item for item in final.get("steps") or []
        if item.get("adapter") == "invoice.reconcile"), {})
    reads = {
        item.get("file_name") for item in final.get("steps") or []
        if item.get("file_name")
    }
    by_step = {
        item.get("step_id"): item.get("file_name")
        for item in final.get("steps") or []
        if item.get("step_id") and item.get("file_name")
    }
    selected_files = {
        by_step[step_id] for step_id in (reconcile.get("depends_on") or [])
        if step_id in by_step
    }
    return {
        "completed": final.get("status") == "completed",
        "reconciliation_121": (
            str(reconcile.get("result_value")) == "121.00"),
        "correct_role_files_selected": selected_files == {
            "ap-inbox-0412.json", "po-archive-88.json",
            "dock-receipt-19.json"},
        "wrong_or_obsolete_not_selected": selected_files.isdisjoint({
            "ap-inbox-0411.json", "ap-inbox-0402.json",
            "dock-receipt-07.json", "warehouse-memo.txt"}),
        "correct_invoice_read": "ap-inbox-0412.json" in reads,
        "correct_po_read": "po-archive-88.json" in reads,
        "correct_receiving_read": "dock-receipt-19.json" in reads,
        "outcome_satisfied": (
            (final.get("business_outcome") or {}).get("state")
            == "satisfied"),
        "model_selected_correct_evidence": _model_selected_correct(state),
    }


def _missing_checks(state: Dict[str, Any]) -> Dict[str, bool]:
    final = state.get("final") or {}
    questions = " ".join(
        str(item.get("question") or item.get("next_action") or "")
        for item in final.get("open_questions") or [])
    reconcile = next((
        item for item in final.get("steps") or []
        if item.get("adapter") == "invoice.reconcile"), {})
    return {
        "not_completed": final.get("status") != "completed",
        "targeted_invoice_question": (
            "invoice" in questions.lower()
            and ("INV-SEL-77" in questions or "PO-SEL-520" in questions)),
        "no_fabricated_reconciliation": not reconcile,
    }


def start(state_path: Path, pool=MISSING_POOL) -> int:
    token_value = token()
    uploads = {
        name: upload(token_value, FIXTURES / name) for name in pool
    }
    sources = [{
        "kind": "document", "document_id": uploads[name]["id"],
    } for name in pool]
    payload = {
        "objective": OBJECTIVE,
        "sources": sources,
        "authorized_actions": ["retrieve", "calculate"],
        "teaching_terms": {"currency": "USD"},
        "budget": {"max_steps": 20, "max_wall_seconds": 3600},
        "use_model": True,
    }
    started = requests.post(
        API + "/api/assignments/from-objective",
        headers=headers(token_value), json=payload, timeout=1200)
    print("START", started.status_code, started.text[:500])
    started.raise_for_status()
    body = started.json()
    run_id = body["run_id"]
    started_body = body
    state = {
        "phase": "start", "run_id": run_id, "request": payload,
        "uploads": {name: value.get("id") for name, value in uploads.items()},
        "expected_reconciliation": str(EXPECTED_RECONCILIATION),
        "initial_proposal": started_body.get("proposal"),
        "initial_proposal_source": started_body.get("proposal_source"),
        "initial_technical_fallback": started_body.get(
            "technical_fallback"),
        "initial_adaptive_rounds": started_body.get("adaptive_rounds") or [],
        "initial_employee_routing": started_body.get("employee_routing"),
    }
    wait_for(
        token_value, run_id,
        {"completed", "failed", "blocked", "cancelled", "waiting"},
        timeout=900)
    _advance(token_value, run_id, state, rounds=2)
    _capture(token_value, run_id, state)
    state["checks"] = _checks(state)
    if pool == MISSING_POOL:
        state["before_add_final"] = json.loads(json.dumps(state["final"]))
        state["before_add_questions"] = state["final"].get(
            "open_questions") or []
        state["missing_checks"] = _missing_checks(state)
    state_path.write_text(json.dumps(state, indent=1, default=str) + "\n")
    print(json.dumps(state["final"], indent=1)[:6000])
    print(json.dumps(state["checks"], indent=1))
    if pool == MISSING_POOL:
        print(json.dumps(state["missing_checks"], indent=1))
    return 0


def _recovery_checks(state: Dict[str, Any]) -> Dict[str, bool]:
    checks = {
        key: value for key, value in _checks(state).items()
        if key != "model_selected_correct_evidence"
    }
    checks["model_backed_recovery"] = any(
        isinstance(round_item, dict)
        and round_item.get("source") in (
            "model", "model_compact", "model_repaired")
        for item in state.get("advance_rounds") or []
        if isinstance(item, dict)
        for round_item in item.get("rounds") or [])
    return checks


def add_missing_invoice(state_path: Path) -> int:
    state = json.loads(state_path.read_text())
    run_id = state["run_id"]
    token_value = token()
    uploaded = upload(token_value, FIXTURES / "ap-inbox-0412.json")
    added = requests.post(
        API + f"/api/assignments/{run_id}/sources",
        headers=headers(token_value),
        json={"source": {"kind": "document",
                         "document_id": uploaded["id"]},
              "reason": "authorized correct invoice added for the missing "
                        "record"},
        timeout=300)
    added.raise_for_status()
    state["missing_invoice_add"] = {
        "upload": uploaded.get("id"),
        "status": added.json().get("status"),
        "body": added.json(),
    }
    _advance(token_value, run_id, state, rounds=2)
    _capture(token_value, run_id, state)
    state["checks"] = _recovery_checks(state)
    state_path.write_text(json.dumps(state, indent=1, default=str) + "\n")
    print(json.dumps(state["final"], indent=1)[:6000])
    print(json.dumps(state["checks"], indent=1))
    return 0 if all(state["checks"].values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("positive", "missing", "add"),
                        required=True)
    parser.add_argument("--state", required=True)
    args = parser.parse_args()
    state_path = Path(args.state)
    if args.phase == "positive":
        raise SystemExit(start(state_path, POOL))
    if args.phase == "missing":
        raise SystemExit(start(state_path, MISSING_POOL))
    raise SystemExit(add_missing_invoice(state_path))
