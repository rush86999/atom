#!/usr/bin/env python3
"""Held-out two-domain employee batch on the normal product routes.

New PO/invoice/receiving identifiers, quantities and prices, independent
arithmetic computed here, and a content/order variant of the accepted
episode. The model selects the durable receiving wait and the independent
quote; the application is restarted between phases; the authorized receiving
answer resumes the same job; the model selects the dependent reconciliation;
the requested review document must contain both independently computed totals.

Usage:
  python scripts/acceptance/employee_g5_heldout_two_domain.py \
    --phase start --state /private/tmp/g5-heldout/state.json ...
  # restart the application on the same world/source
  python ... --phase finish --state ... --db ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict

import requests

API = "http://127.0.0.1:8085"
PASSWORD = "G5Browser-2026!"
FIXTURES = Path("/private/tmp/atom-g5-heldout")
OBJECTIVE = (
    "Reconcile the supplier invoice INV-4491 for PO-7302 against the "
    "purchase order and the receiving record the warehouse still owes. While "
    "that record is pending, prepare the quote from the authorized price "
    "list, and deliver a review document when the reconciliation is settled.")
TEACHING = {"currency": "USD", "freight": "7.50", "tax_basis": "none"}
EXPECTED_QUOTE = "96.30"
EXPECTED_RECONCILE = "140.25"


def token() -> str:
    response = requests.post(
        API + "/api/auth/login",
        json={"username": "admin@example.com", "password": PASSWORD},
        timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def detail(headers, run_id):
    response = requests.get(
        API + f"/api/assignments/{run_id}", headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def record(body):
    container = body.get("assignment")
    if not isinstance(container, dict):
        return {}
    nested = container.get("assignment")
    return nested if isinstance(nested, dict) else container


def step(assignment, adapter):
    return next((
        item for item in assignment.get("steps") or []
        if item.get("adapter") == adapter), {})


def durable(db: str, run_id: str) -> Dict[str, Any]:
    import sqlite3

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


def _served_providers(value, found=None):
    """Collect actually served provider identities from captured rounds."""
    if found is None:
        found = set()
    if isinstance(value, dict):
        route = value.get("served_route")
        if isinstance(route, dict) and route.get("provider"):
            found.add(str(route["provider"]))
        for item in value.values():
            _served_providers(item, found)
    elif isinstance(value, list):
        for item in value:
            _served_providers(item, found)
    return found


def artifact_text(deliverable: Dict[str, Any]) -> str:
    import docx

    path = Path(str(deliverable.get("artifact_path") or ""))
    if not path.is_file():
        return ""
    document = docx.Document(str(path))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    return text


def wait_for(headers, run_id, states, timeout=420):
    deadline = time.time() + timeout
    body = {}
    while time.time() < deadline:
        body = detail(headers, run_id)
        status = str(record(body).get("status") or "")
        if status in states:
            return body
        time.sleep(2)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("start", "finish"), required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.state)
    headers = {"Authorization": f"Bearer {token()}"}

    if args.phase == "start":
        uploads = {}
        for name, kind in (
                ("price-book-heldout.xlsx", "workbook"),
                ("purchase-order-heldout.json", "document"),
                ("invoice-heldout.json", "document")):
            with (FIXTURES / name).open("rb") as handle:
                response = requests.post(
                    API + "/api/documents/upload", headers=headers,
                    files={"file": (name, handle, "application/octet-stream")},
                    timeout=120)
            response.raise_for_status()
            uploads[name] = response.json()
        sources = requests.get(
            API + "/api/assignments/sources", headers=headers,
            params={"query": "price-book-heldout"}, timeout=60).json()
        price = next(
            item for item in sources
            if item.get("dataset_name") == "upload_price_book_heldout__prices")
        payload = {
            "objective": OBJECTIVE,
            "sources": [{
                "kind": "workbook",
                "dataset_name": price["dataset_name"],
                "sheet": price["sheet"],
                "source_version": price["source_version"],
            }, {
                "kind": "document",
                "document_id": uploads["purchase-order-heldout.json"]["id"],
            }, {
                "kind": "document",
                "document_id": uploads["invoice-heldout.json"]["id"],
            }],
            "authorized_actions": ["retrieve", "calculate"],
            "teaching_terms": TEACHING,
            "requested_output": "document",
            "budget": {"max_steps": 30},
            "use_model": True,
        }
        started = requests.post(
            API + "/api/assignments/from-objective", headers=headers,
            json=payload, timeout=600)
        started.raise_for_status()
        body = started.json()
        run_id = body["run_id"]
        body = wait_for(
            headers, run_id,
            {"waiting", "blocked", "completed", "failed", "cancelled"})
        assignment = record(body)
        wait = step(assignment, "assignment.wait")
        quote = step(assignment, "quote.calculate")
        state = {
            "phase": "start", "run_id": run_id, "request": payload,
            "response": started.json(),
            "status": assignment.get("status"),
            "wait": wait.get("waiting") or {},
            "start_quote_present": bool(quote),
            "steps": [{
                "step_id": item.get("step_id"),
                "adapter": item.get("adapter"),
                "status": item.get("status"),
                "operation_id": item.get("operation_id"),
            } for item in assignment.get("steps") or []],
        }
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=1, default=str) + "\n")
        print(json.dumps({
            "run_id": run_id, "status": state["status"],
            "wait": state["wait"].get("correlation_id"),
            "quote_at_start": state["start_quote_present"],
        }, indent=1))
        return 0 if (state["status"] == "waiting" and state["wait"]) else 1

    state = json.loads(state_path.read_text())
    run_id = state["run_id"]
    correlation = str(state["wait"]["correlation_id"])
    assignment = record(detail(headers, run_id))
    restarted_wait = step(assignment, "assignment.wait")
    state["restart"] = {
        "status": assignment.get("status"),
        "same_wait": (
            restarted_wait.get("waiting") or {}).get(
                "correlation_id") == correlation,
    }
    # Held-out event order: if the independent quote was not selected before
    # the restart, let the model choose it now, still while the wait is open.
    quote = step(assignment, "quote.calculate")
    if not quote:
        advanced = requests.post(
            API + f"/api/assignments/{run_id}/advance", headers=headers,
            json={"use_model": True, "max_adaptations": 2,
                  "deadline_seconds": 180}, timeout=600)
        state["post_restart_advance"] = {
            "status": advanced.status_code,
            "rounds": advanced.json().get("rounds")
            if advanced.status_code == 200 else None,
        }
        body = wait_for(headers, run_id, {"waiting", "blocked", "completed"})
        assignment = record(body)
        quote = step(assignment, "quote.calculate")
    quote_durable = next((
        item for item in (durable(args.db, run_id).get("steps") or [])
        if item.get("adapter") == "quote.calculate"), {})
    if (quote_durable.get("result") or {}).get("value"):
        state["quote_after_restart"] = True
    # Authorized receiving record and exact same-job reply.
    with (FIXTURES / "receiving-records-heldout.json").open("rb") as handle:
        uploaded = requests.post(
            API + "/api/documents/upload", headers=headers,
            files={"file": ("receiving-records-heldout.json", handle,
                            "application/octet-stream")}, timeout=120)
    uploaded.raise_for_status()
    added = requests.post(
        API + f"/api/assignments/{run_id}/sources", headers=headers,
        json={"source": {"kind": "document",
                         "document_id": uploaded.json()["id"]},
              "reason": "warehouse supplied the held-out receiving record"},
        timeout=300)
    added.raise_for_status()
    current = record(detail(headers, run_id))
    reply = None
    if str(step(current, "assignment.wait").get("status")) == "waiting":
        reply = requests.post(
            API + f"/api/assignments/{run_id}/responses/{correlation}",
            headers=headers,
            json={"response": "received 3 units",
                  "source": str(state["wait"].get("party") or ""),
                  "value": "3"}, timeout=600)
        reply.raise_for_status()
    body = wait_for(headers, run_id, {"completed", "failed", "blocked"})
    if str(record(body).get("status")) == "blocked":
        advanced = requests.post(
            API + f"/api/assignments/{run_id}/advance", headers=headers,
            json={"use_model": True, "max_adaptations": 2,
                  "deadline_seconds": 180}, timeout=600)
        if advanced.status_code == 200:
            body = wait_for(headers, run_id, {"completed", "failed", "blocked"})
    final = record(body)
    durable_assignment = durable(args.db, run_id)
    steps = {str(item.get("step_id")): item for item in durable_assignment.get("steps") or []}
    reconcile = next((
        item for item in steps.values()
        if item.get("adapter") == "invoice.reconcile"), {})
    quote_final = next((
        item for item in steps.values()
        if item.get("adapter") == "quote.calculate"), {})
    deliverable = next((
        item for item in durable_assignment.get("deliverables") or []
        if item.get("kind") == "document"), {})
    text = artifact_text(deliverable)
    employee_job = body.get("employee_job") or {}
    requirement_views = employee_job.get("business_requirements") or []
    criterion_declared = any(
        item.get("kind") == "business_result" and item.get("required")
        for item in durable_assignment.get("completion_criteria") or [])
    all_results_met = bool(requirement_views) and all(
        str(item.get("status") or "") == "satisfied"
        for item in requirement_views)
    outcome_satisfied = (
        (employee_job.get("business_outcome") or {}).get("state")
        == "satisfied")
    external_effects = [
        item for item in durable_assignment.get("steps") or []
        if str(item.get("effect") or "") == "external"
        and str(item.get("status") or "") == "applied"]
    served_providers = sorted(
        _served_providers(state) | _served_providers(body))
    local_only = all(
        provider == "ollama" or provider.startswith("local")
        for provider in served_providers)
    checks = {
        "wait_survived_restart": (
            state["restart"]["same_wait"] is True
            and state["restart"]["status"] == "waiting"),
        "quote_total_heldout": (
            str((quote_final.get("result") or {}).get("value"))
            == EXPECTED_QUOTE),
        "reconcile_total_heldout": (
            str((reconcile.get("result") or {}).get("value"))
            == EXPECTED_RECONCILE),
        "assignment_completed": final.get("status") == "completed",
        "criterion_declared": criterion_declared,
        "all_required_business_results_met": all_results_met,
        "overall_outcome_satisfied": outcome_satisfied,
        "artifact_applied": deliverable.get("status") == "applied",
        "artifact_has_quote": EXPECTED_QUOTE in text,
        "artifact_has_reconcile": EXPECTED_RECONCILE in text,
        "artifact_sha_matches": bool(deliverable.get("sha256"))
        and hashlib.sha256(
            Path(str(deliverable.get("artifact_path"))).read_bytes()
        ).hexdigest() == deliverable.get("sha256"),
        "no_external_effect": not external_effects,
        "served_routes_local_only": local_only,
    }
    state["served_providers"] = served_providers
    state["finish"] = {
        "status": final.get("status"),
        "steps": [{
            "step_id": item.get("step_id"),
            "adapter": item.get("adapter"),
            "status": item.get("status"),
            "operation_id": item.get("operation_id"),
            "result_value": (item.get("result") or {}).get("value"),
        } for item in durable_assignment.get("steps") or []],
        "deliverable": deliverable,
        "artifact_text": text,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    state_path.write_text(json.dumps(state, indent=1, default=str) + "\n")
    print(json.dumps(checks, indent=1))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
