#!/usr/bin/env python3
"""Packaged smoke: reopen an existing taught assignment, then exercise mapping.

The same authenticated packaged API is used for both. The mapping flow creates
one new workbook-B assignment, confirms Amount through the mapping gap, and
checks 35.00 USD plus one accepted teaching update. No send is attempted except
the explicit server-side denial control, which must create no run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from docx import Document


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token = ""

    def call(self, method: str, path: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.status, json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode() or "{}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def docx_text(path: Path) -> str:
    document = Document(path)
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def assignment_detail(client: Client, run_id: str) -> dict:
    status, body = client.call("GET", f"/api/assignments/{run_id}")
    if status != 200:
        raise SystemExit(f"REFUSED: assignment read {run_id} -> {status}: {body}")
    return body.get("assignment") or {}


def find_assignment(client: Client, objective: str) -> tuple[dict, str]:
    status, rows = client.call("GET", "/api/assignments?include_terminal=true")
    if status != 200:
        raise SystemExit(f"REFUSED: assignment list -> {status}: {rows}")
    for row in rows:
        assignment = row.get("assignment") or row
        if assignment.get("objective") == objective:
            run_id = row.get("run_id") or assignment.get("run_id")
            return assignment_detail(client, run_id), run_id
    raise SystemExit(f"REFUSED: no existing assignment with objective {objective!r}")


def artifact_snapshot(assignment: dict, expected_sum: str) -> dict:
    documents = [d for d in assignment.get("deliverables") or []
                 if d.get("kind") == "document" and d.get("artifact_path")]
    if not documents:
        raise SystemExit("REFUSED: assignment has no document artifact")
    document = documents[0]
    path = Path(document["artifact_path"])
    if not path.is_file():
        raise SystemExit(f"REFUSED: artifact missing {path}")
    actual = sha256(path)
    recorded = str(document.get("sha256") or "")
    if not recorded or recorded != actual:
        raise SystemExit(
            f"REFUSED: artifact hash mismatch recorded={recorded!r} actual={actual!r}")
    text = docx_text(path)
    if expected_sum not in text:
        raise SystemExit(
            f"REFUSED: artifact does not contain {expected_sum!r}")
    return {
        "assignment_id": assignment.get("assignment_id"),
        "status": assignment.get("status"),
        "plan_revision": assignment.get("plan_revision"),
        "teaching_revision": assignment.get("teaching_revision"),
        "artifact_path": str(path),
        "artifact_sha256": actual,
        "artifact_contains_expected_sum": True,
        "deliverable_status": document.get("status"),
    }


def mapping_snapshot(assignment: dict, expected_sum: str,
                     expected_revision: int = 2) -> dict:
    if assignment.get("status") != "completed":
        raise SystemExit(
            f"REFUSED: mapping assignment status={assignment.get('status')!r}")
    mappings = [m for m in assignment.get("mappings") or []
                if str(m.get("concept") or "").lower() == "price"]
    if len(mappings) != 1:
        raise SystemExit(f"REFUSED: expected one Price mapping, got {mappings!r}")
    mapping = mappings[0]
    if mapping.get("column") != "Amount":
        raise SystemExit(f"REFUSED: mapping column={mapping.get('column')!r}")
    if int(mapping.get("revision") or 0) != expected_revision:
        raise SystemExit(
            f"REFUSED: mapping revision={mapping.get('revision')!r} "
            f"expected {expected_revision}")
    if mapping.get("unit_authority") != "source_evidence":
        raise SystemExit(
            f"REFUSED: unit authority={mapping.get('unit_authority')!r}")
    steps = assignment.get("steps") or []
    source_step = next((s for s in steps if s.get("step_id") == "source-1"), {})
    result_value = source_step.get("result_value")
    if result_value is None:
        result_value = (source_step.get("result") or {}).get("value")
    if result_value != expected_sum:
        raise SystemExit(
            f"REFUSED: mapping result={result_value!r}")
    artifact = artifact_snapshot(assignment, expected_sum)
    return {
        "run_id": assignment.get("run_id"),
        "assignment_id": assignment.get("assignment_id"),
        "objective": assignment.get("objective"),
        "status": assignment.get("status"),
        "mapping": mapping,
        "result": result_value,
        "unit": source_step.get("result_unit")
        or (source_step.get("result") or {}).get("unit"),
        "artifact": artifact,
    }


def provider_policy(client: Client) -> dict:
    status, body = client.call("GET", "/api/ai/provider-policy")
    if status != 200:
        raise SystemExit(f"REFUSED: provider policy -> {status}: {body}")
    policy = (body.get("data") or {}).get("policy") or body.get("policy") or {}
    allowed = [str(x) for x in policy.get("allowed_providers") or []]
    preferred = policy.get("preferred") or {}
    ok = (
        policy.get("mode") == "selected"
        and allowed == ["deepseek"]
        and preferred.get("provider") == "deepseek"
        and preferred.get("model") == "deepseek-flash"
    )
    if not ok:
        raise SystemExit(f"REFUSED: unexpected provider policy {policy!r}")
    return {"mode": policy.get("mode"), "allowed_providers": allowed,
            "preferred": preferred, "ok": True}


def send_denial(client: Client, source: dict) -> dict:
    _, before_rows = client.call(
        "GET", "/api/assignments?include_terminal=true")
    status, body = client.call("POST", "/api/assignments", {
        "objective": f"Release send denial {uuid.uuid4().hex[:8]}",
        "sources": [source],
        "deliverables": [],
        "outbound": {
            "to": ["release-smoke@example.invalid"],
            "subject": "Release send denial control",
            "body": "This request must be refused before transport.",
        },
    })
    _, after_rows = client.call(
        "GET", "/api/assignments?include_terminal=true")
    if status != 422:
        raise SystemExit(
            f"REFUSED: send denial expected 422, got {status}: {body}")
    if len(before_rows) != len(after_rows):
        raise SystemExit("REFUSED: denied send created a run")
    return {
        "http_status": status,
        "detail": body.get("detail"),
        "runs_before": len(before_rows),
        "runs_after": len(after_rows),
        "run_created": False,
        "send_allowed": False,
    }


def create_and_confirm_mapping(client: Client, args, source: dict) -> dict:
    objective = f"Release mapping smoke {uuid.uuid4().hex[:10]}: sum Price"
    status, created = client.call("POST", "/api/assignments", {
        "objective": objective,
        "agent_id": args.agent_id or None,
        "sources": [source],
        "calculation": {"aggregate": {
            "operation": "sum", "value_column": "Price"}},
        "deliverables": [{"kind": "document",
                          "description": "Release mapping smoke total"}],
    })
    if status != 200:
        raise SystemExit(f"REFUSED: mapping assignment -> {status}: {created}")
    run_id = created.get("run_id")
    if not run_id:
        raise SystemExit(f"REFUSED: mapping assignment has no run id: {created}")
    deadline = time.time() + 120
    detail = {}
    gaps = []
    while time.time() < deadline:
        status, body = client.call("GET", f"/api/assignments/{run_id}")
        if status != 200:
            raise SystemExit(
                f"REFUSED: mapping detail -> {status}: {body}")
        detail = body.get("assignment") or {}
        gaps = body.get("open_gaps") or []
        if any((g.get("inputs") or {}).get("mapping") for g in gaps):
            break
        if detail.get("status") in ("completed", "failed", "cancelled"):
            raise SystemExit(
                f"REFUSED: mapping assignment ended before a gap: {detail}")
        time.sleep(2)
    gap = next((g for g in gaps
                if (g.get("inputs") or {}).get("mapping")), None)
    if gap is None:
        raise SystemExit("REFUSED: mapping gap was not raised")
    mapping_gap = gap["inputs"]["mapping"]
    candidates = [c.get("column") for c in mapping_gap.get("candidates") or []]
    if "Amount" not in candidates or "Discount" not in candidates:
        raise SystemExit(f"REFUSED: unexpected candidates {candidates!r}")
    resolution = json.dumps({
        "request_id": gap["question_id"],
        "assignment_id": detail.get("assignment_id"),
        "column": "Amount",
        "unit": "USD",
        "source_version": mapping_gap.get("source_version"),
        "teaching_revision": mapping_gap.get("teaching_revision"),
    })
    status, resolved = client.call(
        "POST", f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        {"resolution": resolution})
    if status != 200:
        raise SystemExit(f"REFUSED: mapping confirmation -> {status}: {resolved}")
    deadline = time.time() + 180
    while time.time() < deadline:
        detail = assignment_detail(client, run_id)
        if detail.get("status") in ("completed", "failed", "cancelled"):
            break
        time.sleep(2)
    if detail.get("status") != "completed":
        raise SystemExit(
            f"REFUSED: mapping assignment ended {detail.get('status')!r}: "
            f"{json.dumps(detail.get('steps') or [])[:1200]}")
    snapshot = mapping_snapshot(
        detail, args.expected_mapping_sum, args.expected_mapping_revision)
    snapshot["run_id"] = run_id
    snapshot["gap"] = {
        "question_id": gap["question_id"],
        "source_version": mapping_gap.get("source_version"),
        "teaching_revision": mapping_gap.get("teaching_revision"),
        "candidates": candidates,
        "required_unit": mapping_gap.get("required_unit"),
        "source_unit": mapping_gap.get("source_unit"),
    }
    return snapshot


def collect(client: Client, args, source: dict) -> dict:
    existing, existing_run_id = find_assignment(
        client, args.existing_objective)
    existing_snapshot = artifact_snapshot(
        existing, args.expected_existing_sum)
    existing_snapshot["run_id"] = existing_run_id
    existing_snapshot["objective"] = existing.get("objective")
    policy = provider_policy(client)
    denial = send_denial(client, source)
    mapping = create_and_confirm_mapping(client, args, source)
    return {
        "schema": "atom-assignment-packaged-mapping-taught-smoke-1",
        "ok": True,
        "existing_taught_assignment": existing_snapshot,
        "mapping": mapping,
        "provider_policy": policy,
        "send_denial": denial,
        "source": {
            "dataset_name": args.dataset_name,
            "source": args.source,
            "external_id": args.external_id,
            "source_version": args.source_version,
            "sheet": args.sheet,
        },
    }


def verify(client: Client, args, before_doc: dict) -> dict:
    before = before_doc.get("smoke", before_doc)
    existing_before = before["existing_taught_assignment"]
    mapping_before = before["mapping"]
    existing, existing_run_id = find_assignment(
        client, args.existing_objective)
    existing_after = artifact_snapshot(existing, args.expected_existing_sum)
    existing_after["run_id"] = existing_run_id
    existing_after["objective"] = existing.get("objective")
    mapping_after = mapping_snapshot(
        assignment_detail(client, mapping_before["run_id"]),
        args.expected_mapping_sum, args.expected_mapping_revision)
    mapping_after["run_id"] = mapping_before["run_id"]
    mapping_after["gap"] = mapping_before.get("gap")
    fields = ("assignment_id", "status", "plan_revision", "teaching_revision",
              "artifact_path", "artifact_sha256")
    mismatches = {}
    for label, before_item, after_item in (
            ("existing", existing_before, existing_after),
            ("mapping", mapping_before, mapping_after)):
        for field in fields:
            if before_item.get(field) != after_item.get(field):
                mismatches[f"{label}.{field}"] = {
                    "before": before_item.get(field),
                    "after": after_item.get(field),
                }
    result = {
        "schema": "atom-assignment-packaged-mapping-taught-smoke-1",
        "ok": not mismatches,
        "existing_taught_assignment": existing_after,
        "mapping": mapping_after,
        "provider_policy": provider_policy(client),
        "restart_agreement": {"ok": not mismatches,
                              "mismatches": mismatches},
    }
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", required=True)
    ap.add_argument("--email", default="admin@example.com")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--agent-id", default="map-agent")
    ap.add_argument("--existing-objective", required=True)
    ap.add_argument("--expected-existing-sum", required=True)
    ap.add_argument("--dataset-name", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--external-id", required=True)
    ap.add_argument("--source-version", required=True)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--expected-mapping-sum", default="35.00")
    ap.add_argument("--expected-mapping-revision", type=int, default=2)
    ap.add_argument("--out", required=True)
    ap.add_argument("--verify-snapshot", default="")
    args = ap.parse_args()
    password = Path(args.password_file).read_text().strip()
    client = Client(args.api_base)
    status, body = client.call("POST", "/api/auth/login",
                               {"username": args.email, "password": password})
    if status != 200 or not body.get("access_token"):
        raise SystemExit("REFUSED: normal login failed")
    client.token = body["access_token"]
    source = {
        "kind": "workbook",
        "dataset_name": args.dataset_name,
        "source": args.source,
        "external_id": args.external_id,
        "source_version": args.source_version,
        "sheet": args.sheet,
    }
    if args.verify_snapshot:
        result = verify(client, args, json.loads(
            Path(args.verify_snapshot).read_text()))
    else:
        result = collect(client, args, source)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
