#!/usr/bin/env python3
"""Load the documented sample workspace through the public product API.

Run this against a normally started local app:

    make sample

It creates one employee, uploads ``sample-workspace/sample_quote.csv``, records
two editable lessons, starts one grounded calculation/document job, resolves the
only compatible field mapping when the planner asks, and prints the assignment
URL. No cloud credential, live send or direct database write is used.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "sample-workspace" / "sample_quote.csv"


def _unwrap(body):
    if isinstance(body, dict) and "data" in body and isinstance(body["data"], dict):
        merged = dict(body)
        merged.update(body["data"])
        return merged
    return body


def request(session, method, url, **kwargs):
    response = session.request(method, url, timeout=120, **kwargs)
    try:
        body = response.json()
    except ValueError:
        body = {"text": response.text[:1000]}
    return response.status_code, _unwrap(body)


def password_from(args) -> str:
    if args.password:
        return args.password
    if os.getenv("ADMIN_PASSWORD"):
        return os.environ["ADMIN_PASSWORD"]
    path = Path(args.password_file)
    if path.is_file():
        return path.read_text().strip()
    raise SystemExit(
        f"REFUSED: no admin password. Pass --password or make sure {path} exists.")


def find_source(session, base, name: str) -> dict:
    deadline = time.time() + 60
    last = None
    while time.time() < deadline:
        status, rows = request(
            session, "GET", f"{base}/api/assignments/sources",
            params={"query": name, "limit": 20})
        last = rows
        if status == 200 and isinstance(rows, list):
            match = next((row for row in rows
                          if str(row.get("file_name") or "") == name), None)
            if match:
                return match
        time.sleep(1)
    raise SystemExit(f"REFUSED: uploaded source {name!r} did not appear: {last}")


def find_agent(session, base, name: str, workspace_id: str) -> str:
    status, rows = request(session, "GET", f"{base}/api/agents/")
    if status == 200:
        rows = rows if isinstance(rows, list) else rows.get("agents", [])
        match = next((row for row in rows
                      if str(row.get("name") or "") == name
                      and str(row.get("workspace_id") or "") == workspace_id),
                     None)
        if match:
            return str(match["id"])
    status, body = request(session, "POST", f"{base}/api/agents/custom", json={
        "name": name,
        "description": "Sample quote analyst — deterministic local example.",
        "category": "Sales",
    })
    if status not in (200, 201):
        raise SystemExit(f"REFUSED: agent creation returned {status}: {body}")
    agent_id = (body.get("agent_id") or (body.get("agent") or {}).get("id")
                or body.get("id"))
    if not agent_id:
        raise SystemExit(f"REFUSED: agent creation returned no id: {body}")
    return str(agent_id)


def teach(session, base, agent_id: str) -> None:
    lessons = [
        {
            "lesson": (
                "Method: for quote work, use the selected authorized sheet, "
                "sum the Price measure, cite the source sheet and row count, "
                "and ask for a missing fact instead of guessing. Context: sales."),
            "topic": "sample quote method",
            "context": {"business_category": "sales"},
        },
        {
            "lesson": (
                "Document format: use Arial 11 with Summary, Findings and "
                "Sources headings and an Item/Value table."),
            "topic": "sample document format",
            "applies_to": ["document"],
            "context": {"business_category": "sales", "qualification": "sample"},
            "conditions": {"qualification": "sample"},
            "format_spec": {
                "font_name": "Arial",
                "font_size": 11,
                "heading_order": ["Summary", "Findings", "Sources"],
                "table_columns": ["Item", "Value"],
            },
        },
    ]
    for lesson in lessons:
        status, body = request(
            session, "POST", f"{base}/api/agents/{agent_id}/teach", json=lesson)
        if status not in (200, 201):
            raise SystemExit(f"REFUSED: teaching returned {status}: {body}")


def resolve_mapping_gaps(session, base, run_id: str, detail: dict) -> dict:
    for _ in range(10):
        gaps = detail.get("open_gaps") or []
        if not gaps:
            return detail
        progressed = False
        for gap in gaps:
            mapping = (gap.get("inputs") or {}).get("mapping") or {}
            candidates = mapping.get("candidates") or []
            if not candidates:
                continue
            candidate = next(
                (item for item in candidates
                 if str(item.get("column")) == "Price"),
                candidates[0])
            resolution = {
                "request_id": gap.get("question_id"),
                "assignment_id": (detail.get("assignment") or {}).get(
                    "assignment_id"),
                "column": candidate.get("column"),
                "unit": mapping.get("source_unit") or "USD",
                "source_version": mapping.get("source_version"),
                "teaching_revision": mapping.get("teaching_revision"),
            }
            status, body = request(
                session, "POST",
                f"{base}/api/assignments/{run_id}/gaps/"
                f"{gap['question_id']}/resolve",
                json={"resolution": json.dumps(resolution),
                      "evidence": "sample workspace: the only numeric column"})
            if status not in (200, 201):
                raise SystemExit(
                    f"REFUSED: mapping resolution returned {status}: {body}")
            progressed = True
        if not progressed:
            return detail
        time.sleep(1)
        _, detail = request(
            session, "GET", f"{base}/api/assignments/{run_id}")
    return detail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=os.getenv(
        "ATOM_SAMPLE_BACKEND", "http://127.0.0.1:8001"))
    ap.add_argument("--frontend", default=os.getenv(
        "ATOM_SAMPLE_FRONTEND", "http://localhost:3001"))
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--password")
    ap.add_argument("--password-file", default=str(
        ROOT / "backend" / "logs" / "bootstrap_admin_password.txt"))
    args = ap.parse_args()

    base = args.backend.rstrip("/")
    password = password_from(args)
    session = requests.Session()
    status, login = request(session, "POST", f"{base}/api/auth/login", json={
        "username": "admin@example.com", "password": password})
    token = login.get("access_token")
    if status != 200 or not token:
        raise SystemExit(f"REFUSED: login returned {status}: {login}")
    session.headers.update({"Authorization": f"Bearer {token}"})

    _, me = request(session, "GET", f"{base}/api/auth/me")
    workspace_id = str(me.get("workspace_id") or "default")
    agent_id = find_agent(
        session, base, "Sample Quote Analyst", workspace_id)
    teach(session, base, agent_id)

    mime = mimetypes.guess_type(args.csv.name)[0] or "text/csv"
    with args.csv.open("rb") as handle:
        status, uploaded = request(
            session, "POST", f"{base}/api/documents/upload",
            files={"file": (args.csv.name, handle, mime)})
    if status not in (200, 201):
        raise SystemExit(f"REFUSED: upload returned {status}: {uploaded}")

    source = find_source(session, base, args.csv.name)
    objective = "Sum Price for the sample quote sheet"
    payload = {
        "objective": objective,
        "agent_id": agent_id,
        "sources": [{
            "kind": source.get("kind") or "workbook",
            "dataset_name": source.get("dataset_name"),
            "source": source.get("source"),
            "external_id": source.get("external_id"),
            "source_version": source.get("source_version"),
            "sheet": source.get("sheet"),
        }],
        "deliverables": [{"kind": "document", "description": objective}],
        "calculation": {"aggregate": {"operation": "sum",
                                      "value_column": "Price"}},
        "task_context": {"business_category": "sales",
                         "qualification": "sample"},
    }
    status, started = request(
        session, "POST", f"{base}/api/assignments", json=payload)
    if status not in (200, 201):
        raise SystemExit(
            f"REFUSED: assignment start returned {status}: {started}")
    run_id = started.get("run_id") or (started.get("run") or {}).get("id")
    if not run_id:
        raise SystemExit(f"REFUSED: assignment start returned no run id: {started}")

    detail = started
    deadline = time.time() + 180
    while time.time() < deadline:
        _, detail = request(session, "GET", f"{base}/api/assignments/{run_id}")
        detail = resolve_mapping_gaps(session, base, run_id, detail)
        assignment = detail.get("assignment") or {}
        if assignment.get("status") in ("completed", "failed", "cancelled"):
            break
        time.sleep(2)

    assignment = detail.get("assignment") or {}
    artifacts = [item for item in assignment.get("deliverables") or []
                 if item.get("artifact_path")]
    result = {
        "schema": "atom-sample-workspace-1",
        "status": "passed" if assignment.get("status") == "completed" else "failed",
        "backend": base,
        "frontend": args.frontend,
        "agent_id": agent_id,
        "run_id": run_id,
        "objective": objective,
        "assignment_status": assignment.get("status"),
        "source": {
            "dataset_name": source.get("dataset_name"),
            "sheet": source.get("sheet"),
            "rows": source.get("row_count"),
            "columns": source.get("columns"),
            "source_version": source.get("source_version"),
        },
        "result_value": next((step.get("result_value")
                              for step in assignment.get("steps") or []
                              if step.get("step_id") == "source-1"), None),
        "artifacts": [{
            "deliverable_id": item.get("deliverable_id"),
            "sha256": item.get("sha256"),
            "download_url": (
                f"{base}/api/assignments/{run_id}/deliverables/"
                f"{item.get('deliverable_id')}/download"),
        } for item in artifacts],
        "open_in_ui": f"{args.frontend}/assignments",
        "teaching": "editable in the employee's Training panel",
        "controlled_effects": "none (this sample is read + local document only)",
    }
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
