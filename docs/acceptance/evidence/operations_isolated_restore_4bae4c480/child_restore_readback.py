#!/usr/bin/env python3
"""Read-only child-backend readback across a stop/start boundary.

NOT EXECUTED by the 4bae4c480 candidate.  The workorder starts the backend; this
script never writes product data, never calls a provider and never sends.  It
fails if the original scratch source is still available or if any returned
managed path still points at the source root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path


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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--canvas-id", required=True)
    ap.add_argument("--goal-id", required=True)
    ap.add_argument("--document-id", required=True)
    ap.add_argument("--db-path", required=True)
    ap.add_argument("--artifact-path", required=True)
    ap.add_argument("--artifact-sha256", required=True)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare-to", default="")
    args = ap.parse_args()

    source_root = Path(args.source_root).expanduser().resolve()
    if source_root.exists():
        raise SystemExit(
            f"REFUSED: original source root is still available: {source_root}")
    password = Path(args.password_file).read_text().strip()
    target_root = Path(args.db_path).expanduser().resolve().parent
    client = Client(args.api_base)
    status, body = client.call("POST", "/api/auth/login", {
        "email": args.email, "username": args.email, "password": password,
    })
    if status != 200 or not body.get("access_token"):
        raise SystemExit(f"REFUSED: login failed: {status} {body}")
    client.token = body["access_token"]

    _, me = client.call("GET", "/api/auth/me")
    _, canvas = client.call("GET", f"/api/canvas/{args.canvas_id}")
    _, goal = client.call("GET", f"/api/goals/{args.goal_id}")

    content = canvas.get("content") or {}
    office_file = Path(str(content.get("office_file") or ""))
    if not office_file.is_file():
        raise SystemExit(f"REFUSED: canvas office artifact missing: {office_file}")
    if source_root == office_file or source_root in office_file.parents:
        raise SystemExit("REFUSED: canvas office binding still borrows the source")
    if target_root not in office_file.parents and office_file.parent != target_root:
        raise SystemExit("REFUSED: canvas office binding is outside the target")

    artifact = Path(args.artifact_path).expanduser().resolve()
    if not artifact.is_file():
        raise SystemExit(f"REFUSED: expected artifact missing: {artifact}")
    artifact_sha = sha256(artifact)
    if artifact_sha != args.artifact_sha256:
        raise SystemExit(
            f"REFUSED: artifact hash mismatch {artifact_sha} != {args.artifact_sha256}")

    db = sqlite3.connect(f"file:{Path(args.db_path).resolve()}?mode=ro", uri=True)
    try:
        row = db.execute(
            "SELECT id, file_path, file_name FROM ingested_documents WHERE id=?",
            (args.document_id,)).fetchone()
    finally:
        db.close()
    if not row:
        raise SystemExit(f"REFUSED: document row missing: {args.document_id}")
    document_path = Path(row[1])
    if not document_path.is_file():
        raise SystemExit(f"REFUSED: document file missing: {document_path}")
    if source_root == document_path or source_root in document_path.parents:
        raise SystemExit("REFUSED: document row still borrows the source")

    snapshot = {
        "schema": "atom-child-restore-readback-1",
        "user": {"id": me.get("id"), "email": me.get("email"),
                 "workspace_id": me.get("workspace_id"),
                 "tenant_id": me.get("tenant_id")},
        "canvas": {"id": args.canvas_id, "content": content,
                   "office_file": str(office_file)},
        "goal": goal,
        "document": {"id": row[0], "file_name": row[2],
                     "file_path": str(document_path)},
        "artifact": {"path": str(artifact), "sha256": artifact_sha},
        "source_root_unavailable": str(source_root),
        "target_root": str(target_root),
        "model_dispatched": False,
        "wrote_product_data": False,
    }
    report = {"ok": True, "snapshot": snapshot}
    if args.compare_to:
        before_doc = json.loads(Path(args.compare_to).read_text())
        before = before_doc.get("snapshot", before_doc)
        fields = ("user", "canvas", "goal", "document", "artifact")
        mismatches = {
            field: {"before": before.get(field), "after": snapshot.get(field)}
            for field in fields if before.get(field) != snapshot.get(field)
        }
        report["restart_agreement"] = {
            "before": args.compare_to, "fields": list(fields),
            "mismatches": mismatches, "ok": not mismatches,
        }
        report["ok"] = not mismatches
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
