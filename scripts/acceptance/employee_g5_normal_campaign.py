#!/usr/bin/env python3
"""Held-out two-domain employee campaign through the normal product routes.

The script starts the controlled browser/API acceptance server (real
AssignmentExecutor and real assignment routes, scratch SQLite world), then
starts objective-only jobs through ``/api/assignments/from-objective``. The
initial proposal selects authorized evidence; the product's adaptive
follow-up proposes and compiles typed work.

No expected rows, step patches or final plans are supplied. Only source
references, objective, teaching terms and the user's answer to a missing
source are provided. Controlled effects stay local; no live provider is used.

Usage:
  python scripts/acceptance/employee_g5_normal_campaign.py \
    --ollama-url http://127.0.0.1:11436/v1 --model llama3.1:8b \
    --out /path/to/out --port 8094
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DEFAULT_WORLD_ROOT = Path(tempfile.gettempdir())
PYTHON = sys.executable


class Server:
    def __init__(
        self, world: Path, out: Path, port: int, model: str, url: str,
    ) -> None:
        self.world = world
        self.out = out
        self.port = port
        self.model = model
        self.url = url
        self.proc: Optional[subprocess.Popen] = None
        self.log = None

    def start(self, reset: bool) -> None:
        env = dict(os.environ)
        env.update({
            "ATOM_ASSIGNMENT_BROWSER_WORLD": str(self.world),
            "ATOM_ASSIGNMENT_BROWSER_WORLD_RESET": "1" if reset else "0",
            "ATOM_ASSIGNMENT_BROWSER_PORT": str(self.port),
            "ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS": "1",
            "ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT": str(self.world),
            "OLLAMA_BASE_URL": self.url,
            "OLLAMA_MODEL": self.model,
            "OLLAMA_CONTEXT_WINDOW": "16384",
            "ATOM_LOCAL_ONLY": "true",
            "ATOM_EMPLOYEE_PROVIDER_MODEL": f"ollama:{self.model}",
            "ATOM_EMPLOYEE_ATTEMPT_LOG": str(self.out / "attempts.jsonl"),
            "ATOM_EMPLOYEE_ADVANCE_DEADLINE_SECONDS": "300",
            "PYTHONPATH": str(BACKEND),
        })
        try:
            probe = socket.create_connection(
                ("127.0.0.1", self.port), timeout=0.5)
        except OSError:
            probe = None
        if probe is not None:
            probe.close()
            raise RuntimeError(
                f"port {self.port} is already served by another process")
        self.log = open(self.out / "server.log", "a")
        self.proc = subprocess.Popen(
            [PYTHON, str(BACKEND / "scripts" /
                        "assignment_browser_acceptance_server.py")],
            cwd=str(BACKEND), env=env,
            stdout=self.log, stderr=subprocess.STDOUT)
        self.wait_ready()

    def wait_ready(self) -> None:
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                response = httpx.get(
                    f"http://127.0.0.1:{self.port}/_acceptance/state",
                    timeout=2)
                if response.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("acceptance server did not become ready")

    def stop(self) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None
        if self.log is not None:
            self.log.close()
            self.log = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def _checks() -> List[Dict[str, Any]]:
    return []


def _check(checks: List[Dict[str, Any]], name: str, ok: bool, detail: Any):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL"), name,
          json.dumps(detail, default=str)[:700])


def _assignment(body: Dict[str, Any]) -> Dict[str, Any]:
    assignment = body.get("assignment") or {}
    nested = assignment.get("assignment") if isinstance(
        assignment, dict) else None
    return nested if isinstance(nested, dict) else assignment


def _steps(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _assignment(body).get("steps") or []


def _value(body: Dict[str, Any], adapter: str):
    for step in _steps(body):
        if step.get("adapter") == adapter:
            result = step.get("result")
            if isinstance(result, dict) and result.get("value") is not None:
                return result.get("value")
            return step.get("result_value")
    return None


def _round(body: Dict[str, Any], operation: str) -> Optional[Dict[str, Any]]:
    for item in (body.get("adaptive_rounds")
                 or body.get("rounds") or []):
        if item.get("work_request_operation") == operation:
            return item
    return None


def _write_quote(path: Path, b_price: float, a_qty: int) -> None:
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Prices"
    sheet.append(["Item", "Qty", "Price", "Currency"])
    sheet.append(["A", a_qty, 100, "USD"])
    sheet.append(["B", 3, b_price, "USD"])
    workbook.save(path)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2))


def _prepare_world(raw_world: str, *, reset_world: bool) -> Path:
    """Create a fresh harness-owned world or reuse a marked disposable one.

    Never deletes an arbitrary caller path. The existing launch guard validates
    the path root, requires its marker before reset, and is the only deletion
    path.
    """
    from core.assignment_launcher_guard import (
        MARKER_NAME, UnsafeScratchError, prepare_scratch_dir,
        validate_scratch_dir,
    )

    if not raw_world:
        candidate = DEFAULT_WORLD_ROOT / (
            f"atom-g5-normal-{os.getpid()}-{uuid.uuid4().hex[:8]}")
        if candidate.exists():
            raise UnsafeScratchError(
                f"fresh campaign world unexpectedly exists: {candidate}")
        candidate.mkdir(parents=True)
        prepare_scratch_dir(candidate)
        return candidate
    candidate = validate_scratch_dir(raw_world)
    if candidate.exists() and any(candidate.iterdir()):
        if not (candidate / MARKER_NAME).exists():
            raise UnsafeScratchError(
                "refusing an existing unmarked campaign world: "
                f"{candidate}")
        if not reset_world:
            raise UnsafeScratchError(
                "an existing campaign world requires explicit --reset-world: "
                f"{candidate}")
        prepare_scratch_dir(candidate, reset=True)
    else:
        prepare_scratch_dir(candidate)
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11436/v1")
    parser.add_argument("--model", default="llama3.1:8b")
    parser.add_argument("--out", required=True)
    parser.add_argument("--world", default="")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--port", type=int, default=8094)
    parser.add_argument(
        "--reset-world", action="store_true",
        help="explicitly reset an existing marked harness-owned world")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    world = _prepare_world(args.world, reset_world=args.reset_world)

    server = Server(world, out, args.port, args.model, args.ollama_url)
    checks: List[Dict[str, Any]] = []
    report: Dict[str, Any] = {
        "schema": "atom-employee-g5-normal-campaign-1",
        "model": args.model,
        "ollama_url": args.ollama_url,
        "world": str(world),
        "scenarios": {},
        "checks": checks,
    }
    client = httpx.Client(timeout=400)
    try:
        server.start(reset=True)
        report["serving_identity"] = client.get(
            server.base + "/_acceptance/state").json()

        # ---------------------------------------------------------- domain A
        prices = world / "price-book.xlsx"
        _write_quote(prices, 50, 2)
        quote_response = client.post(
            server.base + "/api/assignments/from-objective",
            json={
                "objective": (
                    "Prepare an exact customer quote from the approved "
                    "price book"),
                "sources": [{
                    "kind": "workbook", "path": str(prices),
                    "sheet": "Prices"}],
                "authorized_actions": ["retrieve", "calculate"],
                "teaching_terms": {
                    "currency": "USD", "freight": "20.00",
                    "tax_basis": "none"},
                "use_model": True,
                "task_context": {"business_category": "industrial_quote"},
            }).json()
        report["scenarios"]["quote_initial"] = quote_response
        _check(checks, "quote initial model proposal",
               quote_response.get("proposal_source") == "model",
               quote_response.get("proposal_source"))
        quote_round = _round(quote_response, "quote_calculation")
        _check(checks, "quote typed work adopted",
               bool(quote_round) and quote_round.get("adoption_status") == (
                   "applied"), quote_round)
        _check(checks, "quote initial total",
               str(_value(quote_response, "quote.calculate")) == "370.00",
               _value(quote_response, "quote.calculate"))
        _check(checks, "quote initial completed",
               _assignment(quote_response).get("status") == "completed",
               _assignment(quote_response).get("status"))
        quote_run = quote_response.get("run_id")

        # Changed price evidence: only the affected branch is reopened.
        _write_quote(prices, 55, 3)
        repriced = client.post(
            server.base + f"/api/assignments/{quote_run}/invalidate/source-1",
            json={"reason": "held-out price book changed: A quantity and B "
                            "price were revised"}).json()
        report["scenarios"]["quote_changed"] = repriced
        _check(checks, "quote changed total",
               str(_value(repriced, "quote.calculate")) == "485.00",
               _value(repriced, "quote.calculate"))
        _check(checks, "quote changed completed",
               _assignment(repriced).get("status") == "completed",
               _assignment(repriced).get("status"))

        # Real process restart against the same durable world.
        server.stop()
        server.start(reset=False)
        restarted = client.get(
            server.base + f"/api/assignments/{quote_run}").json()
        report["scenarios"]["quote_restart"] = restarted
        _check(checks, "quote survives restart",
               _assignment(restarted).get("status") == "completed",
               _assignment(restarted).get("status"))
        _check(checks, "quote value survives restart",
               str(_value(restarted, "quote.calculate")) == "485.00",
               _value(restarted, "quote.calculate"))

        # Cancellation on an independent objective-started job.
        note = world / "cancel-note.json"
        _write_json(note, {"note": "not needed"})
        cancelled_job = client.post(
            server.base + "/api/assignments/from-objective",
            json={
                "objective": "Cancel this independent evidence read",
                "sources": [{"kind": "document", "path": str(note)}],
                "authorized_actions": ["retrieve"],
                "use_model": False,
            }).json()
        cancel_run = cancelled_job.get("run_id")
        cancelled = client.post(
            server.base + f"/api/assignments/{cancel_run}/cancel",
            json={"reason": "held-out cancellation control"}).json()
        report["scenarios"]["cancel"] = cancelled
        _check(checks, "cancellation is terminal",
               (cancelled.get("assignment") or {}).get("status") == (
                   "cancelled"), cancelled.get("assignment", {}).get("status"))

        # ---------------------------------------------------------- domain B
        po = world / "purchase-order.json"
        invoice = world / "invoice.json"
        receiving = world / "receiving.json"
        _write_json(po, {
            "po_id": "PO-7", "vendor_id": "V-9", "quantity": "2",
            "unit_price": "120.00", "freight": "30.00", "currency": "USD"})
        _write_json(invoice, {
            "invoice_id": "INV-7", "po_id": "PO-7", "quantity": "2",
            "unit_price": "120.00", "freight": "30.00", "currency": "USD"})
        _write_json(receiving, {
            "po_id": "PO-7", "received_quantity": "2"})
        invoice_response = client.post(
            server.base + "/api/assignments/from-objective",
            json={
                "objective": (
                    "Reconcile the supplier invoice against the purchase "
                    "order and receiving record; prepare only supported "
                    "bookkeeping work"),
                "sources": [
                    {"kind": "document", "path": str(po)},
                    {"kind": "document", "path": str(invoice)},
                    {"kind": "document", "path": str(receiving)},
                ],
                "authorized_actions": ["retrieve", "calculate"],
                "use_model": True,
                "task_context": {
                    "business_category": "procurement_bookkeeping"},
            }).json()
        report["scenarios"]["invoice_initial"] = invoice_response
        invoice_round = _round(invoice_response, "invoice_reconciliation")
        _check(checks, "invoice typed work adopted",
               bool(invoice_round) and invoice_round.get("adoption_status") == (
                   "applied"), invoice_round)
        _check(checks, "invoice reconciled value",
               str(_value(invoice_response, "invoice.reconcile")) == "270.00",
               _value(invoice_response, "invoice.reconcile"))
        _check(checks, "invoice initial completed",
               _assignment(invoice_response).get("status") == "completed",
               _assignment(invoice_response).get("status"))

        # Missing invoice: the model sees PO + receiving only. Record the
        # actual proposal. The user may then supply the missing source; the
        # normal adapter reads it and the model decides the reconciliation.
        missing_po = world / "missing-po.json"
        missing_receiving = world / "missing-receiving.json"
        supplied_invoice = world / "supplied-invoice.json"
        _write_json(missing_po, {
            "po_id": "PO-8", "vendor_id": "V-9", "quantity": "2",
            "unit_price": "120.00", "freight": "30.00", "currency": "USD"})
        _write_json(missing_receiving, {
            "po_id": "PO-8", "received_quantity": "2"})
        _write_json(supplied_invoice, {
            "invoice_id": "INV-8", "po_id": "PO-8", "quantity": "2",
            "unit_price": "120.00", "freight": "30.00", "currency": "USD"})
        missing = client.post(
            server.base + "/api/assignments/from-objective",
            json={
                "objective": (
                    "Reconcile the supplier invoice for PO-8 and prepare "
                    "only supported bookkeeping work"),
                "sources": [
                    {"kind": "document", "path": str(missing_po)},
                    {"kind": "document", "path": str(missing_receiving)},
                ],
                "authorized_actions": ["retrieve", "calculate"],
                "use_model": True,
                "task_context": {
                    "business_category": "procurement_bookkeeping"},
            }).json()
        report["scenarios"]["missing_invoice"] = missing
        missing_run = missing.get("run_id")
        missing_rounds = missing.get("adaptive_rounds") or []
        _check(checks, "missing invoice not fabricated",
               not any(
                   item.get("work_request_operation") == (
                       "invoice_reconciliation")
                   for item in missing_rounds),
               [item.get("decision") for item in missing_rounds])
        obligations = (missing.get("employee_job") or {}).get(
            "open_obligations") or []
        _check(checks, "missing invoice produces actionable obligation",
               any(
                   str(item.get("kind") or "") == "missing_prerequisite"
                   and "invoice" in str(item.get("question") or "").lower()
                   for item in obligations if isinstance(item, dict)),
               obligations)

        supplied = client.post(
            server.base + f"/api/assignments/{missing_run}/sources",
            json={
                "source": {"kind": "document",
                           "path": str(supplied_invoice)},
                "reason": (
                    "the user supplied the supplier invoice source after "
                    "the evidence gap"),
            }).json()
        report["scenarios"]["missing_invoice_source"] = supplied
        _check(checks, "source answer resolves the obligation",
               bool(supplied.get("resolved_question_ids")), supplied)
        duplicate = client.post(
            server.base + f"/api/assignments/{missing_run}/sources",
            json={
                "source": {"kind": "document",
                           "path": str(supplied_invoice)},
                "reason": "duplicate source addition must not duplicate work",
            }).json()
        report["scenarios"]["missing_invoice_duplicate"] = duplicate
        _check(checks, "duplicate source is idempotent",
               duplicate.get("status") == "already_present", duplicate)
        recovered = client.post(
            server.base + f"/api/assignments/{missing_run}/advance",
            json={"use_model": True, "deadline_seconds": 300}).json()
        report["scenarios"]["missing_invoice_recovery"] = recovered
        recovered_round = _round(recovered, "invoice_reconciliation")
        _check(checks, "missing invoice recovery adopted",
               bool(recovered_round) and recovered_round.get(
                   "adoption_status") == "applied", recovered_round)
        _check(checks, "missing invoice recovered value",
               str(_value(recovered, "invoice.reconcile")) == "270.00",
               _value(recovered, "invoice.reconcile"))

        report["checks"] = checks
        report["ok"] = all(item["ok"] for item in checks)
        (out / "campaign.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n")
        print(json.dumps(
            {"ok": report["ok"], "checks": checks}, indent=2,
            default=str)[:12000])
        return 0 if report["ok"] else 1
    finally:
        server.stop()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
