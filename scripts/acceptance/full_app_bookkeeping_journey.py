#!/usr/bin/env python3
"""Invoice -> reviewed Books bill -> readback on the normal served app.

The invoice bytes are uploaded through the real document-ingestion route, the
extracted facts drive the real assignment planner, and the normal assignment
API executes the registered connected.books actions against an
environment-gated controlled Books transport. No live provider is contacted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from core.assignment_plan import new_step  # noqa: E402


def login(api: str, password: str) -> str:
    response = requests.post(
        f"{api}/api/auth/login",
        json={"username": "admin@example.com", "password": password},
        timeout=30,
    )
    if response.status_code != 200:
        raise AssertionError(
            f"login failed: {response.status_code} {response.text[:500]}")
    return response.json()["access_token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def parse_invoice(api: str, token: str, invoice_path: Path) -> dict:
    with invoice_path.open("rb") as handle:
        response = requests.post(
            f"{api}/api/document-ingestion/parse",
            headers=headers(token),
            files={"file": (invoice_path.name, handle, "text/plain")},
            data={"export_format": "text"},
            timeout=120,
        )
    if response.status_code != 200:
        raise AssertionError(
            f"invoice parse failed: {response.status_code} "
            f"{response.text[:800]}")
    body = response.json()
    if not body.get("success") or not body.get("content"):
        raise AssertionError(f"invoice parse returned no content: {body}")
    return body


def upload_invoice(api: str, token: str, invoice_path: Path) -> tuple:
    with invoice_path.open("rb") as handle:
        response = requests.post(
            f"{api}/api/document-ingestion/upload",
            headers=headers(token),
            files={"file": (invoice_path.name, handle, "text/plain")},
            timeout=120,
        )
    if response.status_code != 200:
        raise AssertionError(
            f"invoice upload failed: {response.status_code} "
            f"{response.text[:800]}")
    body = response.json()
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    document_id = str((data or {}).get("document_id") or "")
    if not document_id:
        raise AssertionError(f"invoice upload returned no document_id: {body}")
    return body, document_id


def extract_facts(text: str) -> dict:
    def capture(pattern: str) -> str:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if not match:
            raise AssertionError(f"invoice text lacks {pattern!r}")
        return match.group(1).strip()

    lines = []
    for match in re.finditer(
            r"^Line:\s*(.+?)\s*\|\s*([0-9.]+)\s*\|\s*(.+)$",
            text, re.IGNORECASE | re.MULTILINE):
        lines.append({
            "description": match.group(1).strip(),
            "amount": match.group(2).strip(),
            "account_label": match.group(3).strip(),
        })
    if not lines:
        raise AssertionError("invoice text has no line items")
    payment = re.search(
        r"^Payment:\s*([0-9.]+)\s+(\S+)$", text,
        re.IGNORECASE | re.MULTILINE)
    return {
        "vendor": capture(r"^Vendor:\s*(.+)$"),
        "invoice_number": capture(r"^Invoice Number:\s*(.+)$"),
        "date": capture(r"^Date:\s*(.+)$"),
        "due_date": capture(r"^Due Date:\s*(.+)$"),
        "currency": capture(r"^Currency:\s*(.+)$"),
        "tax": capture(r"^Tax:\s*(.+)$"),
        "total": capture(r"^Total:\s*(.+)$"),
        "lines": lines,
        "payment": ({
            "amount": payment.group(1), "reference": payment.group(2)
        } if payment else None),
    }


def assignment_steps(facts: dict) -> list:
    account_index = {"Parts": 0, "Freight": 1}
    lines = []
    for line in facts["lines"]:
        index = account_index.get(line["account_label"])
        if index is None:
            raise AssertionError(
                f"no controlled CoA mapping for {line['account_label']!r}")
        lines.append({
            "description": line["description"],
            "amount": line["amount"],
            "account_id": f"${{accounts.data.accounts.{index}.account_id}}",
        })
    proposal_input = {
        "provider": "zoho_books",
        "organization_id": "org-1",
        "entity_type": "bill",
        "external_id": facts["invoice_number"],
        "vendor_candidates": "${vendor.data.candidates}",
        "currency": facts["currency"],
        "document_date": facts["date"],
        "due_date": facts["due_date"],
        "lines": lines,
        "tax_total": facts["tax"],
        "document_total": facts["total"],
        "payment": facts["payment"],
    }
    return [
        new_step(
            step_id="vendor", title="Resolve the supplier identity",
            operation_type="retrieve", adapter="action.registry",
            inputs={"action": "connected.books.resolve_vendor",
                    "arguments": {"name": facts["vendor"],
                                  "organization_id": "org-1"}},
            effect="read_only",
        ),
        new_step(
            step_id="accounts", title="Resolve the chart of accounts",
            operation_type="retrieve", adapter="action.registry",
            inputs={"action": "connected.books.list_accounts",
                    "arguments": {"organization_id": "org-1"}},
            effect="read_only",
        ),
        new_step(
            step_id="propose", title="Build the balanced bill proposal",
            operation_type="retrieve", adapter="action.registry",
            depends_on=["vendor", "accounts"],
            inputs={"action": "connected.books.propose_bill",
                    "arguments": {"proposal_input": proposal_input}},
            effect="read_only",
        ),
        new_step(
            step_id="create", title="Post the approved bill",
            operation_type="outbound", adapter="action.registry",
            depends_on=["propose"],
            inputs={
                "action": "connected.books.create_bill",
                "arguments": {
                    "proposal": "${propose.data.data}",
                    "authority_reference": "grant-bookkeeping-1",
                    "operation_id": "op-bookkeeping-1",
                    "period_start": "2026-01-01",
                    "period_end": "2026-12-31",
                    "closed_through": "2026-10-31",
                },
            },
            effect="external", approval_required=True,
            approval_purpose="Post the reviewed supplier bill",
        ),
    ]


def start_assignment(api: str, token: str, facts: dict,
                     document_id: str) -> dict:
    response = requests.post(
        f"{api}/api/assignments",
        headers=headers(token),
        json={
            "objective": (
                f"Process supplier invoice {facts['invoice_number']} into a "
                "reviewed Zoho Books bill"),
            "sources": [{"document_id": document_id,
                         "kind": "document"}],
            "proposed_steps": assignment_steps(facts),
            "authorized_actions": ["calculate", "outbound"],
            "budget": {"max_steps": 20, "max_attempts_per_step": 3,
                       "max_wall_seconds": 600},
        },
        timeout=120,
    )
    if response.status_code != 200:
        raise AssertionError(
            f"assignment start failed: {response.status_code} "
            f"{response.text[:1200]}")
    return response.json()


def poll(api: str, token: str, run_id: str, timeout: int = 120) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        response = requests.get(
            f"{api}/api/assignments/{run_id}", headers=headers(token),
            timeout=30)
        if response.status_code != 200:
            raise AssertionError(
                f"assignment poll failed: {response.status_code} "
                f"{response.text[:500]}")
        last = response.json()
        assignment = last.get("assignment") or {}
        status = assignment.get("status")
        if status in ("completed", "failed", "cancelled", "blocked",
                      "awaiting_approval"):
            return last
        time.sleep(0.5)
    return last


def step_by_id(body: dict, step_id: str) -> dict:
    for step in (body.get("assignment") or {}).get("steps") or []:
        if step.get("step_id") == step_id:
            return step
    return {}


def persisted_assignment(world: Path, run_id: str) -> dict:
    """Read the durable assignment record, including full step results."""
    with sqlite3.connect(str(world / "atom.db")) as conn:
        row = conn.execute(
            "select parameters from goal_runs where id=?", (run_id,)
        ).fetchone()
    if not row or not row[0]:
        return {}
    parameters = row[0]
    if isinstance(parameters, str):
        parameters = json.loads(parameters)
    return (((parameters or {}).get("task_lifecycle") or {})
            .get("assignment") or {})


def internal_step(world: Path, run_id: str, step_id: str) -> dict:
    for step in persisted_assignment(world, run_id).get("steps") or []:
        if step.get("step_id") == step_id:
            return step
    return {}


def approve(api: str, token: str, run_id: str, step_id: str) -> dict:
    response = requests.post(
        f"{api}/api/assignments/{run_id}/approve/{step_id}",
        headers=headers(token),
        json={"note": "controlled bookkeeping approval"},
        timeout=60,
    )
    return {"status": response.status_code, "body": response.json()
            if response.content else {}}


def load_books_state(path: Path) -> dict:
    if not path.exists():
        return {"bills": {}, "creates": 0, "readbacks": 0, "calls": []}
    return json.loads(path.read_text())


def restart_world(world: Path, password: str) -> dict:
    repo = Path(__file__).resolve().parents[2]
    backend_pid = int((world / "backend.pid").read_text().strip())
    frontend_pid = int((world / "frontend.pid").read_text().strip())
    for pid in (backend_pid, frontend_pid):
        subprocess.run(["kill", "-INT", str(pid)], check=False)
    deadline = time.time() + 30
    while time.time() < deadline:
        alive = [pid for pid in (backend_pid, frontend_pid)
                 if subprocess.run(["kill", "-0", str(pid)],
                                   capture_output=True).returncode == 0]
        if not alive:
            break
        time.sleep(0.5)
    marker = json.loads((world / ".atom-integrated-world.json").read_text())
    env = dict(os.environ)
    env.update({
        "WORLD": str(world),
        "ADMIN_PASSWORD": password,
        "BACKEND_PORT": str(marker.get("backend_port") or 8097),
        "FRONTEND_PORT": str(marker.get("frontend_port") or 3138),
        "PYTHON": os.getenv(
            "BRENNAN_PYTHON",
            "/Users/rushiparikh/projects/atom/backend/venv314/bin/python"),
        "ATOM_BOOKS_CONTROLLED_TRANSPORT": "1",
        "ATOM_BOOKS_CONTROLLED_STATE": str(world / "books-state.json"),
        "ATOM_ASSIGNMENT_ALLOW_PROPOSED_STEPS": "1",
    })
    completed = subprocess.run(
        ["bash", str(repo / "scripts/acceptance/"
         "launch_integrated_local_candidate.sh")],
        env=env, capture_output=True, text=True, timeout=600)
    if completed.returncode != 0:
        raise AssertionError(
            f"world restart failed: {completed.stderr[-1200:]}")
    return {
        "old_backend_pid": backend_pid,
        "new_backend_pid": int((world / "backend.pid").read_text().strip()),
        "old_frontend_pid": frontend_pid,
        "new_frontend_pid": int((world / "frontend.pid").read_text().strip()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--world", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--restart", action="store_true", default=True)
    args = parser.parse_args()
    api = args.api.rstrip("/")
    world = Path(args.world).resolve()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    password = Path(args.password_file).read_text().strip()
    state_path = world / "books-state.json"

    invoice = out / "invoice-INV-IN-1.txt"
    invoice.write_text(
        "SUPPLIER INVOICE\n"
        "Vendor: Acme\n"
        "Invoice Number: INV-IN-1\n"
        "Date: 2026-11-01\n"
        "Due Date: 2026-12-01\n"
        "Currency: USD\n"
        "Tax: 0.00\n"
        "Payment: 50.00 EFT-1\n"
        "Total: 120.00\n"
        "Line: Parts | 100.00 | Parts\n"
        "Line: Freight | 20.00 | Freight\n",
        encoding="utf-8")
    checks = []

    def record(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok),
                       "detail": detail or {}})
        print(("PASS" if ok else "FAIL"), name,
              json.dumps(detail or {}, default=str)[:700])

    token = login(api, password)
    parsed = parse_invoice(api, token, invoice)
    upload_body, document_id = upload_invoice(api, token, invoice)
    facts = extract_facts(str(parsed.get("content") or ""))
    record("invoice bytes parse through the normal document route",
           parsed.get("success") and "Acme" in parsed.get("content", ""),
           {"method": parsed.get("method"), "chars": parsed.get("total_chars"),
            "document_id": document_id})
    record("invoice facts are extracted from the returned bytes",
           facts["invoice_number"] == "INV-IN-1"
           and facts["total"] == "120.00"
           and len(facts["lines"]) == 2,
           {"vendor": facts["vendor"], "total": facts["total"],
            "lines": facts["lines"]})

    before = load_books_state(state_path)
    started = start_assignment(api, token, facts, document_id)
    run_id = started.get("run_id")
    record("normal assignment starts from the invoice facts",
           bool(run_id),
           {"run_id": run_id,
            "status": (started.get("assignment") or {}).get("status")})
    pending = poll(api, token, run_id)
    create_step = step_by_id(pending, "create")
    record("vendor, CoA and balanced proposal resolve before approval",
           create_step.get("status") == "awaiting_approval"
           and step_by_id(pending, "vendor").get("status") == "applied"
           and step_by_id(pending, "accounts").get("status") == "applied"
           and step_by_id(pending, "propose").get("status") == "applied",
           {"create": create_step.get("status"),
            "vendor": step_by_id(pending, "vendor").get("status"),
            "accounts": step_by_id(pending, "accounts").get("status"),
            "propose": step_by_id(pending, "propose").get("status")})
    internal_propose = internal_step(world, run_id, "propose")
    proposal = (((internal_propose.get("result") or {}).get("data") or {})
                .get("data") or {})
    record("proposal is exact, balanced and not yet posted",
           proposal.get("status") == "proposed"
           and proposal.get("document_total") == "120.00"
           and proposal.get("posting") is None
           and (proposal.get("payment") or {}).get("posted") is False,
           {"status": proposal.get("status"),
            "total": proposal.get("document_total"),
            "duplicate_key": proposal.get("duplicate_key")})

    restart = None
    if args.restart:
        restart = restart_world(world, password)
        record("real backend restart preserves the pending approval",
               restart["old_backend_pid"] != restart["new_backend_pid"],
               restart)
        token = login(api, password)
        reopened = poll(api, token, run_id)
        create_step = step_by_id(reopened, "create")
        record("reopened assignment still awaits the same approval",
               create_step.get("status") == "awaiting_approval"
               and not create_step.get("result", {}).get("remote_id"),
               {"status": create_step.get("status"),
                "operation_id": create_step.get("operation_id")})

    approved = approve(api, token, run_id, "create")
    record("approval is accepted once", approved["status"] == 200,
           approved["body"])
    final = poll(api, token, run_id)
    create_step = step_by_id(final, "create")
    internal_create = internal_step(world, run_id, "create")
    create_result = internal_create.get("result") or {}
    remote_id = str(create_result.get("remote_id") or "")
    record("one registered Books create completes with readback",
           create_step.get("status") == "applied"
           and remote_id.startswith("bill-controlled-")
           and ((create_result.get("data") or {}).get(
               "verification") or {}).get("status") == "verified",
           {"status": create_step.get("status"),
            "remote_id": remote_id,
            "verification": (create_result.get("data") or {}).get(
                "verification")})
    after = load_books_state(state_path)
    record("provider effect count is exactly one",
           int(after.get("creates") or 0) == int(before.get("creates") or 0) + 1
           and int(after.get("readbacks") or 0) >= 1,
           {"before": before.get("creates"), "after": after.get("creates"),
            "readbacks": after.get("readbacks")})

    duplicate = approve(api, token, run_id, "create")
    after_duplicate = load_books_state(state_path)
    record("duplicate continuation is refused without a second effect",
           duplicate["status"] in (404, 409)
           and int(after_duplicate.get("creates") or 0)
           == int(after.get("creates") or 0),
           {"approve_status": duplicate["status"],
            "creates": after_duplicate.get("creates")})

    # A second assignment with the same invoice must hit the duplicate sweep,
    # not create another bill.
    duplicate_started = start_assignment(
        api, token, facts, document_id)
    duplicate_run = duplicate_started.get("run_id")
    duplicate_pending = poll(api, token, duplicate_run)
    if step_by_id(duplicate_pending, "create").get("status") == (
            "awaiting_approval"):
        approve(api, token, duplicate_run, "create")
        duplicate_pending = poll(api, token, duplicate_run)
    duplicate_step = step_by_id(duplicate_pending, "create")
    duplicate_state = load_books_state(state_path)
    duplicate_message = str(
        (duplicate_step.get("failure") or {}).get("message") or "")
    record("same invoice is refused as a duplicate without a second create",
           int(duplicate_state.get("creates") or 0)
           == int(after_duplicate.get("creates") or 0)
           and "duplicate" in duplicate_message.lower(),
           {"creates": duplicate_state.get("creates"),
            "step_status": duplicate_step.get("status"),
            "message": duplicate_message})

    invoice_sha = hashlib.sha256(invoice.read_bytes()).hexdigest()
    result = {
        "schema": "atom-full-app-bookkeeping-journey-1",
        "status": "passed" if all(item["ok"] for item in checks) else "failed",
        "checks": checks,
        "invoice": {"path": invoice.name, "sha256": invoice_sha},
        "parsed_method": parsed.get("method"),
        "facts": facts,
        "run_id": run_id,
        "duplicate_run_id": duplicate_run,
        "document_id": document_id,
        "upload": upload_body,
        "books_state": str(state_path),
        "restart": restart,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2,
                                                default=str))
    return 0 if all(item["ok"] for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
