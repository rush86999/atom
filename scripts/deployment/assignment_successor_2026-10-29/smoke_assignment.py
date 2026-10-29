#!/usr/bin/env python3
"""Open one existing completed assignment and its artifact through the API.

The same command writes a pre-restart snapshot and can compare a post-restart
snapshot. It never starts new durable work and never sends anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def docx_text(path: Path) -> str:
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def collect(client: Client, objective: str, expected_sum: str) -> dict:
    _, me = client.call("GET", "/api/auth/me")
    _, rows = client.call("GET", "/api/assignments?include_terminal=true")
    match = None
    for row in rows:
        assignment = row.get("assignment") or row
        if assignment.get("objective") == objective:
            match = row
            break
    if not match:
        raise SystemExit(f"REFUSED: no assignment with objective {objective!r}")
    run_id = match.get("run_id") or (match.get("assignment") or {}).get("run_id")
    _, detail = client.call("GET", f"/api/assignments/{run_id}")
    assignment = detail.get("assignment") or {}
    docs = [d for d in assignment.get("deliverables", [])
            if d.get("kind") == "document" and d.get("artifact_path")]
    if not docs:
        raise SystemExit("REFUSED: completed assignment has no document artifact")
    artifact = Path(docs[0]["artifact_path"])
    if not artifact.is_file():
        raise SystemExit(f"REFUSED: artifact missing {artifact}")
    text = docx_text(artifact)
    if expected_sum not in text:
        raise SystemExit(f"REFUSED: artifact does not contain {expected_sum}")
    steps = assignment.get("steps") or []
    snapshot = {
        "schema": "atom-assignment-release-representative-1",
        "run_id": run_id,
        "assignment_id": assignment.get("assignment_id"),
        "objective": objective,
        "status": assignment.get("status"),
        "plan_revision": assignment.get("plan_revision"),
        "teaching_revision": assignment.get("teaching_revision"),
        "deliverables": [
            {"kind": d.get("kind"), "status": d.get("status"),
             "artifact_path": d.get("artifact_path"), "sha256": d.get("sha256")}
            for d in assignment.get("deliverables", [])
        ],
        "artifact_path": str(artifact),
        "artifact_sha256": sha256(artifact),
        "artifact_contains_expected_sum": expected_sum in text,
        "step_summaries": [s.get("result_summary") for s in steps],
        "source_versions": [
            (s.get("binding") or {}).get("source_version")
            for s in assignment.get("sources", [])
        ],
        "user": {"id": me.get("id"), "email": me.get("email"),
                 "workspace_id": me.get("workspace_id"),
                 "tenant_id": me.get("tenant_id")},
    }
    return snapshot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", required=True)
    ap.add_argument("--email", default="admin@example.com")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--objective", required=True)
    ap.add_argument("--expected-sum", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare-to", default="")
    args = ap.parse_args()
    password = Path(args.password_file).read_text().strip()
    client = Client(args.api_base)
    status, body = client.call("POST", "/api/auth/login",
                               {"username": args.email, "password": password})
    if status != 200 or not body.get("access_token"):
        raise SystemExit("REFUSED: normal login failed")
    client.token = body["access_token"]
    snapshot = collect(client, args.objective, args.expected_sum)
    report = {"ok": True, "snapshot": snapshot}
    if args.compare_to:
        before = json.loads(Path(args.compare_to).read_text())
        fields = ("run_id", "assignment_id", "status", "plan_revision",
                  "teaching_revision", "artifact_path", "artifact_sha256",
                  "source_versions")
        mismatches = {
            field: {"before": before.get(field), "after": snapshot.get(field)}
            for field in fields if before.get(field) != snapshot.get(field)
        }
        report["restart_agreement"] = {
            "before": args.compare_to,
            "fields": list(fields),
            "mismatches": mismatches,
            "ok": not mismatches,
        }
        report["ok"] = not mismatches
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
