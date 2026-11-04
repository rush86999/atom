#!/usr/bin/env python3
"""Normal-app evidence for the remaining employee G5 behaviors.

One isolated real-application backend/world covers:
- a requested document artifact whose completion needs the rendered artifact,
- an independent branch that progresses while another branch waits,
- selective re-evaluation of only the changed branch with unrelated receipts
  retained, cancellation while waiting, and a refused late response,
- a controlled provider effect whose confirmation is lost, restart recovery,
  original-operation reconciliation and no resend.

Every effect is local/controlled. No live provider, credential, consent, send
or spend authority is used. The report keeps run/operation/receipt identities,
artifact bytes, source identity and the exact serving identity before/after
restart.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DEFAULT_WORLD_ROOT = Path(
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode")
PYTHON = sys.executable
sys.path.insert(0, str(BACKEND))
ADMIN_PASSWORD = "Scratch-Pass-123"


class Backend:
    def __init__(self, world: Path, out: Path, port: int) -> None:
        self.world = world
        self.out = out
        self.port = port
        self.proc: Optional[subprocess.Popen] = None
        self.log = None

    def start(self, reset: bool) -> None:
        try:
            probe = socket.create_connection(
                ("127.0.0.1", self.port), timeout=0.5)
        except OSError:
            probe = None
        if probe is not None:
            probe.close()
            raise RuntimeError(
                f"port {self.port} is already served by another process")
        env = dict(os.environ)
        env.update({
            "DATABASE_URL": f"sqlite:///{self.world}/atom.db",
            "ATOM_DATA_DIR": str(self.world / "data"),
            "LANCEDB_URI": str(self.world / "data" / "atom_memory"),
            "LANCEDB_URI_BASE": str(self.world / "data" / "atom_memory"),
            "ATOM_OFFICE_DIR": str(self.world / "data" / "office"),
            "ATOM_ASSIGNMENT_OUTPUT_DIR": str(
                self.world / "data" / "assignments"),
            "ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT": "1",
            "ATOM_ASSIGNMENT_OUTBOX": str(self.world / "outbox.jsonl"),
            "ATOM_ASSIGNMENT_CONTROLLED_OUTCOME": "uncertain",
            "ADMIN_PASSWORD": ADMIN_PASSWORD,
            "ATOM_LOCAL_ONLY": "true",
            "ENABLE_SCHEDULER": "false",
            "ENABLE_INGESTION_SYNC": "false",
            "PYTHONPATH": str(BACKEND),
        })
        self.log = open(self.out / "server.log", "a")
        self.proc = subprocess.Popen(
            [PYTHON, "-m", "uvicorn", "main_api_app:app",
             "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=str(BACKEND), env=env,
            stdout=self.log, stderr=subprocess.STDOUT)
        self.wait_ready()

    def wait_ready(self) -> None:
        deadline = time.time() + 240
        while time.time() < deadline:
            try:
                response = httpx.get(
                    f"http://127.0.0.1:{self.port}/api/health", timeout=2)
                if response.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("normal app backend did not become ready")

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


def _prepare_world(raw: str) -> Path:
    from core.assignment_launcher_guard import (
        MARKER_NAME, UnsafeScratchError, prepare_scratch_dir,
        validate_scratch_dir,
    )

    if not raw:
        candidate = DEFAULT_WORLD_ROOT / (
            f"atom-g5-remaining-{os.getpid()}-{uuid.uuid4().hex[:8]}")
        candidate.mkdir(parents=True)
        prepare_scratch_dir(candidate)
        return candidate
    candidate = validate_scratch_dir(raw)
    if candidate.exists() and any(candidate.iterdir()):
        if not (candidate / MARKER_NAME).exists():
            raise UnsafeScratchError(
                f"refusing an existing unmarked world: {candidate}")
        raise UnsafeScratchError(
            "this control owns a fresh scratch world; omit --world")
    prepare_scratch_dir(candidate)
    return candidate


def _check(checks: List[Dict[str, Any]], name: str, ok: bool, detail: Any):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL"), name,
          json.dumps(detail, default=str)[:700])


def _assignment(body: Dict[str, Any]) -> Dict[str, Any]:
    container = body.get("assignment")
    if not isinstance(container, dict):
        return {}
    nested = container.get("assignment")
    return nested if isinstance(nested, dict) else container


def _step(assignment: Dict[str, Any], step_id: str) -> Dict[str, Any]:
    return next(
        step for step in assignment.get("steps") or []
        if step.get("step_id") == step_id)


def _write_docx_text(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    return text


def _write_world_quote(path: Path) -> None:
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Prices"
    sheet.append(["Item", "Qty", "Price", "Currency"])
    sheet.append(["A", 2, 100, "USD"])
    sheet.append(["B", 3, 50, "USD"])
    workbook.save(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--world", default="")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    world = _prepare_world(args.world)
    report: Dict[str, Any] = {
        "schema": "atom-employee-g5-remaining-normal-app-1",
        "world": str(world),
        "checks": [],
        "event_order": [],
        "runs": {},
    }
    checks: List[Dict[str, Any]] = report["checks"]
    event_order: List[str] = report["event_order"]

    server = Backend(world, out, args.port)
    client = httpx.Client(timeout=180)

    def login() -> Dict[str, str]:
        response = client.post(
            server.base + "/api/auth/login",
            json={"username": "admin@example.com",
                  "password": ADMIN_PASSWORD})
        response.raise_for_status()
        return {"Authorization":
                f"Bearer {response.json()['access_token']}"}

    def get_assignment(run_id: str, headers: Dict[str, str]):
        response = client.get(
            server.base + f"/api/assignments/{run_id}", headers=headers)
        response.raise_for_status()
        return response.json()

    try:
        server.start(reset=True)
        headers = login()
        report["serving_identity_before"] = client.get(
            server.base + "/api/health").json()
        source_file = world / "price-book.xlsx"
        _write_world_quote(source_file)
        with source_file.open("rb") as handle:
            uploaded = client.post(
                server.base + "/api/document-ingestion/upload",
                headers=headers,
                files={"file": ("price-book.xlsx", handle,
                                "application/vnd.openxmlformats-officedocument"
                                ".spreadsheetml.sheet")})
        uploaded.raise_for_status()
        upload_body = uploaded.json()
        data = upload_body.get("data") if isinstance(
            upload_body.get("data"), dict) else upload_body
        document_id = str(data.get("document_id") or "")
        report["source"] = {
            "document_id": document_id,
            "file_name": data.get("file_name"),
            "sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
        }
        _check(checks, "normal upload creates the authorized source",
               bool(document_id), report["source"])
        event_order.append("source_uploaded")

        # 1. Requested document artifact. Completion must require the
        # rendered artifact, not only the intermediate calculation total.
        artifact_payload = {
            "objective": "Prepare the customer quote document",
            "sources": [{"document_id": document_id}],
            "calculation": {
                "line_items": [
                    {"item_id": "A", "category": "A", "quantity": "2",
                     "unit": "each", "pack_size": "1",
                     "unit_price": "100.00", "price_basis": "contract",
                     "currency": "USD"},
                    {"item_id": "B", "category": "B", "quantity": "3",
                     "unit": "each", "pack_size": "1",
                     "unit_price": "50.00", "price_basis": "contract",
                     "currency": "USD"},
                ],
                "currency": "USD", "freight": "20.00",
                "tax": {"basis": "none"}, "rounding": "half_up",
                "scale": 2, "rounding_authority": "customer agreement",
            },
            "deliverables": [{
                "kind": "document", "description": "Customer quote"}],
            "authorized_actions": ["retrieve", "calculate"],
        }
        artifact_start = client.post(
            server.base + "/api/assignments",
            headers=headers, json=artifact_payload)
        artifact_start.raise_for_status()
        artifact_body = artifact_start.json()
        artifact_run = artifact_body["run_id"]
        report["runs"]["artifact"] = artifact_run
        event_order.append("artifact_started")
        artifact_detail = get_assignment(artifact_run, headers)
        artifact_assignment = _assignment(artifact_detail)
        deliverable = (artifact_assignment.get("deliverables") or [{}])[0]
        artifact_path = Path(str(deliverable.get("artifact_path") or ""))
        artifact_sha = (
            hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            if artifact_path.is_file() else None)
        artifact_text = (
            _write_docx_text(artifact_path) if artifact_path.is_file() else "")
        criteria = (artifact_detail.get("employee_job") or {}).get(
            "criteria") or []
        outcome = (artifact_detail.get("employee_job") or {}).get(
            "business_outcome") or {}
        expected_total = 2 * 100 + 3 * 50 + 20
        _check(checks, "artifact objective completes only with applied artifact",
               artifact_assignment.get("status") == "completed"
               and deliverable.get("status") == "applied",
               {"status": artifact_assignment.get("status"),
                "deliverable_status": deliverable.get("status")})
        _check(checks, "artifact criterion is required and met",
               any(item.get("kind") == "artifact_verified"
                   and item.get("required") for item in criteria)
               and outcome.get("state") == "satisfied",
               {"criteria": criteria, "outcome": outcome.get("state")})
        _check(checks, "artifact bytes match the recorded sha256",
               bool(artifact_sha) and artifact_sha == deliverable.get("sha256"),
               {"sha256": artifact_sha,
                "recorded": deliverable.get("sha256")})
        _check(checks, "artifact content has the exact total, lines and source",
               f"{expected_total:.2f}" in artifact_text
               and "price-book.xlsx" in artifact_text
               and "A" in artifact_text and "B" in artifact_text,
               artifact_text[:1200])
        report["artifact"] = {
            "run_id": artifact_run,
            "deliverable": deliverable,
            "sha256": artifact_sha,
            "text": artifact_text,
            "expected_total": f"{expected_total:.2f}",
        }
        event_order.append("artifact_verified")

        # 2. Independent branch progress while another branch waits, then a
        # material change that reopens only the affected branch.
        wait_payload = {
            "objective": (
                "Wait for the carrier rate confirmation and prepare the "
                "review package"),
            "sources": [{"document_id": document_id}],
            "wait": {
                "correlation_id": "corr-g5-branch-remaining",
                "party": "carrier",
                "detail": "rate confirmation",
                "fact": "carrier_rate",
            },
            "deliverables": [{
                "kind": "document",
                "description": "Carrier review",
                "content": (
                    "Review prepared while waiting for the carrier "
                    "confirmation."),
            }],
            "authorized_actions": ["retrieve", "present", "calculate"],
        }
        wait_start = client.post(
            server.base + "/api/assignments",
            headers=headers, json=wait_payload)
        wait_start.raise_for_status()
        wait_run = wait_start.json()["run_id"]
        report["runs"]["branch"] = wait_run
        event_order.append("wait_assignment_started")
        wait_detail = get_assignment(wait_run, headers)
        wait_assignment = _assignment(wait_detail)
        task_version = int(
            (wait_detail.get("employee_job") or {}).get("task_version") or 0)
        patch_payload = {
            "patch_id": "g5-independent-branch-remaining-1",
            "base_task_version": task_version,
            "base_plan_revision": int(
                wait_assignment.get("plan_revision") or 1),
            "reason": (
                "prepare independent review calculations while the carrier "
                "reply is pending"),
            "observations": [{
                "kind": "business_decision",
                "detail": "independent branch work"}],
            "invalidate_steps": [], "remove_steps": [],
            "update_steps": [], "add_facts": [], "set_requires": {},
            "add_steps": [
                {"step_id": "branch-a", "title": "Calculate review subtotal",
                 "operation_type": "calculate", "adapter": "formula.calculate",
                 "depends_on": [],
                 "inputs": {"expression": "2 * 100 + 3 * 50",
                            "bindings": {}, "units": {},
                            "output_unit": "USD", "origin": {}},
                 "effect": "local", "requires": [],
                 "approval_required": False, "required": True},
                {"step_id": "branch-b", "title": "Calculate review reserve",
                 "operation_type": "calculate", "adapter": "formula.calculate",
                 "depends_on": [],
                 "inputs": {"expression": "1000 - 250",
                            "bindings": {}, "units": {},
                            "output_unit": "USD", "origin": {}},
                 "effect": "local", "requires": [],
                 "approval_required": False, "required": True},
            ],
        }
        patched = client.post(
            server.base + f"/api/assignments/{wait_run}/patch",
            headers=headers, json=patch_payload)
        patched.raise_for_status()
        event_order.append("independent_branches_adopted")
        wait_detail = get_assignment(wait_run, headers)
        wait_assignment = _assignment(wait_detail)
        branch_a = _step(wait_assignment, "branch-a")
        branch_b = _step(wait_assignment, "branch-b")
        wait_step = _step(wait_assignment, "wait")
        branch_b_before = {
            "operation_id": branch_b.get("operation_id"),
            "result_value": branch_b.get("result_value"),
            "result_summary": branch_b.get("result_summary"),
        }
        _check(checks, "independent branches complete while the wait stays open",
               wait_assignment.get("status") == "waiting"
               and branch_a.get("status") == "applied"
               and branch_b.get("status") == "applied"
               and wait_step.get("status") == "waiting",
               {"assignment": wait_assignment.get("status"),
                "branch_a": branch_a.get("status"),
                "branch_b": branch_b.get("status"),
                "wait": wait_step.get("status")})
        _check(checks, "independent branches have distinct operation receipts",
               branch_a.get("operation_id")
               and branch_b.get("operation_id")
               and branch_a["operation_id"] != branch_b["operation_id"],
               {"branch_a": branch_a.get("operation_id"),
                "branch_b": branch_b.get("operation_id")})

        invalidated = client.post(
            server.base + f"/api/assignments/{wait_run}/invalidate/branch-a",
            headers=headers,
            json={"reason": "branch A source revision changed"})
        invalidated.raise_for_status()
        event_order.append("affected_branch_invalidated")
        wait_detail = get_assignment(wait_run, headers)
        wait_assignment = _assignment(wait_detail)
        branch_a_after = _step(wait_assignment, "branch-a")
        branch_b_after = _step(wait_assignment, "branch-b")
        wait_after = _step(wait_assignment, "wait")
        _check(checks, "only the affected branch is re-evaluated",
               branch_a_after.get("status") == "applied"
               and branch_a_after.get("operation_id")
               and branch_a_after["operation_id"]
               != branch_a.get("operation_id")
               and branch_a_after.get("prior_result_count") == 1,
               {"before": branch_a.get("operation_id"),
                "after": branch_a_after.get("operation_id"),
                "prior_result_count": branch_a_after.get(
                    "prior_result_count")})
        _check(checks, "unrelated receipt and waiting operation are retained",
               branch_b_after.get("operation_id")
               == branch_b_before["operation_id"]
               and branch_b_after.get("result_value")
               == branch_b_before["result_value"]
               and branch_b_after.get("result_summary")
               == branch_b_before["result_summary"]
               and wait_after.get("operation_id")
               == wait_step.get("operation_id")
               and wait_after.get("status") == "waiting",
               {"branch_b": branch_b_before,
                "branch_b_after": {
                    "operation_id": branch_b_after.get("operation_id"),
                    "result_value": branch_b_after.get("result_value")},
                "wait": wait_after.get("operation_id")})
        report["branch"] = {
            "run_id": wait_run,
            "branch_a_before": branch_a.get("operation_id"),
            "branch_a_after": branch_a_after.get("operation_id"),
            "branch_b": branch_b_before,
            "wait_operation_id": wait_after.get("operation_id"),
        }
        event_order.append("selective_retention_verified")

        # 3. Cancellation while waiting and a late response refusal.
        cancelled = client.post(
            server.base + f"/api/assignments/{wait_run}/cancel",
            headers=headers,
            json={"reason": "owner cancelled while the carrier reply awaited"})
        cancelled.raise_for_status()
        event_order.append("waiting_assignment_cancelled")
        late = client.post(
            server.base + (
                f"/api/assignments/{wait_run}/responses/"
                "corr-g5-branch-remaining"),
            headers=headers,
            json={"response": "late carrier reply after cancellation",
                  "source": "carrier"})
        late_detail = late.json() if late.content else {}
        wait_detail = get_assignment(wait_run, headers)
        cancelled_assignment = _assignment(wait_detail)
        _check(checks, "late response after cancellation is refused",
               late.status_code == 409
               and "cancelled" in str(late_detail).lower()
               and cancelled_assignment.get("status") == "cancelled",
               {"status_code": late.status_code,
                "detail": late_detail,
                "assignment": cancelled_assignment.get("status")})
        _check(checks, "completed branch receipts survive cancellation",
               _step(cancelled_assignment, "branch-b").get("operation_id")
               == branch_b_before["operation_id"]
               and _step(cancelled_assignment, "branch-a").get(
                   "operation_id") == branch_a_after.get("operation_id"),
               [{"step": step.get("step_id"),
                 "status": step.get("status"),
                 "operation_id": step.get("operation_id")}
                for step in cancelled_assignment.get("steps") or []])
        event_order.append("late_response_refused")

        # 4. Controlled provider acceptance with lost confirmation, restart,
        # original-operation reconciliation and no resend.
        outbound_payload = {
            "objective": "Send one controlled delivery notice",
            "sources": [{"document_id": document_id}],
            "outbound": {
                "to": ["customer@example.invalid"],
                "subject": "Controlled notice",
                "body": "Controlled body",
            },
            "transport": "controlled",
            "authorized_actions": ["outbound"],
        }
        outbound_start = client.post(
            server.base + "/api/assignments",
            headers=headers, json=outbound_payload)
        outbound_start.raise_for_status()
        outbound_run = outbound_start.json()["run_id"]
        report["runs"]["uncertain"] = outbound_run
        event_order.append("controlled_outbound_started")
        outbound_detail = get_assignment(outbound_run, headers)
        outbound_assignment = _assignment(outbound_detail)
        send_step = next(
            step for step in outbound_assignment.get("steps") or []
            if step.get("operation_type") == "outbound")
        _check(checks, "controlled outbound awaits explicit approval",
               send_step.get("status") == "awaiting_approval",
               send_step.get("status"))
        approved = client.post(
            server.base + (
                f"/api/assignments/{outbound_run}/approve/"
                f"{send_step['step_id']}"),
            headers=headers, json={"note": "controlled approval"})
        approved.raise_for_status()
        client.post(
            server.base + f"/api/assignments/{outbound_run}/resume",
            headers=headers).raise_for_status()
        outbound_detail = get_assignment(outbound_run, headers)
        outbound_assignment = _assignment(outbound_detail)
        send_after = _step(outbound_assignment, send_step["step_id"])
        outbox = world / "outbox.jsonl"
        outbox_lines = [
            json.loads(line) for line in outbox.read_text().splitlines()
            if line.strip()
        ] if outbox.exists() else []
        outbox_sha = (
            hashlib.sha256(outbox.read_bytes()).hexdigest()
            if outbox.exists() else None)
        operation_id = send_after.get("operation_id")
        _check(checks, "provider accepted then lost confirmation",
               send_after.get("status") == "uncertain"
               and outbound_assignment.get("status") == "blocked",
               {"step": send_after.get("status"),
                "assignment": outbound_assignment.get("status")})
        _check(checks, "exactly one controlled effect exists",
               len(outbox_lines) == 1,
               {"count": len(outbox_lines), "sha256": outbox_sha})
        event_order.append("uncertain_effect_recorded")

        # Real process restart while the effect is uncertain.
        server.stop()
        server.start(reset=False)
        headers = login()
        report["serving_identity_after_restart"] = client.get(
            server.base + "/api/health").json()
        outbound_detail = get_assignment(outbound_run, headers)
        outbound_assignment = _assignment(outbound_detail)
        send_restart = _step(outbound_assignment, send_step["step_id"])
        outbox_lines_after = [
            json.loads(line) for line in outbox.read_text().splitlines()
            if line.strip()
        ] if outbox.exists() else []
        outbox_sha_after = (
            hashlib.sha256(outbox.read_bytes()).hexdigest()
            if outbox.exists() else None)
        _check(checks, "uncertain original operation survives restart",
               send_restart.get("status") == "uncertain"
               and send_restart.get("operation_id") == operation_id,
               {"status": send_restart.get("status"),
                "operation_id": send_restart.get("operation_id")})
        _check(checks, "restart creates no second effect",
               len(outbox_lines_after) == 1
               and outbox_sha_after == outbox_sha,
               {"count": len(outbox_lines_after),
                "sha256": outbox_sha_after})
        event_order.append("restart_verified")

        reconciled = client.post(
            server.base + (
                f"/api/assignments/{outbound_run}/reconcile/"
                f"{send_step['step_id']}"),
            headers=headers,
            json={"verdict": "applied",
                  "evidence": "the controlled outbox row matches the original "
                              "operation provider reference",
                  "evidence_ref": str(outbox),
                  "provider_ref": operation_id})
        reconciled.raise_for_status()
        resumed = client.post(
            server.base + f"/api/assignments/{outbound_run}/resume",
            headers=headers)
        resumed.raise_for_status()
        outbound_detail = get_assignment(outbound_run, headers)
        outbound_assignment = _assignment(outbound_detail)
        send_reconciled = _step(outbound_assignment, send_step["step_id"])
        outbox_lines_final = [
            json.loads(line) for line in outbox.read_text().splitlines()
            if line.strip()
        ] if outbox.exists() else []
        outbox_sha_final = (
            hashlib.sha256(outbox.read_bytes()).hexdigest()
            if outbox.exists() else None)
        _check(checks, "original operation reconciles to applied",
               send_reconciled.get("status") == "applied"
               and send_reconciled.get("operation_id") == operation_id,
               {"status": send_reconciled.get("status"),
                "operation_id": send_reconciled.get("operation_id")})
        _check(checks, "reconciled assignment completes without a resend",
               outbound_assignment.get("status") == "completed"
               and len(outbox_lines_final) == 1
               and outbox_sha_final == outbox_sha,
               {"assignment": outbound_assignment.get("status"),
                "count": len(outbox_lines_final),
                "sha256": outbox_sha_final})
        report["uncertain"] = {
            "run_id": outbound_run,
            "operation_id": operation_id,
            "outbox_sha256_before": outbox_sha,
            "outbox_sha256_after": outbox_sha_final,
            "outbox_count": len(outbox_lines_final),
            "step_id": send_step["step_id"],
        }
        event_order.append("uncertain_reconciled")

    finally:
        server.stop()
        client.close()

    report["all_checks_passed"] = all(item["ok"] for item in checks)
    (out / "report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n")
    (out / "REPORT.md").write_text(
        "# Employee G5 remaining normal-app campaign\n\n"
        + "\n".join(
            f"- {'PASS' if item['ok'] else 'FAIL'} {item['name']}"
            for item in checks)
        + "\n\nRun IDs:\n```\n"
        + json.dumps(report.get("runs"), indent=2)
        + "\n```\n")
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
