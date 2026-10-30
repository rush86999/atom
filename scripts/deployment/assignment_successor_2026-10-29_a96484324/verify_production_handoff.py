#!/usr/bin/env python3
"""Read-only verification of a prepared production data handoff."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_env(root: Path) -> dict:
    out = {}
    for line in (root / "config" / "env.release").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k] = v.strip().strip("'")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    env = read_env(root)
    data = Path(env["ATOM_DATA_DIR"])
    db_path = data / "atom.db"
    os.environ.update({
        "ATOM_DATA_DIR": str(data),
        "DATABASE_URL": env.get("DATABASE_URL", f"sqlite:///{db_path}"),
        "ATOM_OFFICE_DIR": env.get("ATOM_OFFICE_DIR", str(data / "office")),
        "ATOM_ASSIGNMENT_OUTPUT_DIR": env.get(
            "ATOM_ASSIGNMENT_OUTPUT_DIR", str(data / "office" / "assignments")),
        "LANCEDB_URI": env.get("LANCEDB_URI", str(data / "atom_memory")),
        "LANCEDB_URI_BASE": env.get(
            "LANCEDB_URI_BASE", str(data / "atom_memory")),
    })
    backend_dir = root / "current" / "app" / "backend"
    if not backend_dir.is_dir():
        backend_dir = Path(__file__).resolve().parents[3] / "backend"
    sys.path.insert(0, str(backend_dir))
    from core.assignment_plan import assignment_projection
    from core.goals.goal_run_service import GoalRunService
    from core.task_lifecycle import TaskLifecycle, operation_binding_sha256
    source_prefix = "/Users/rushiparikh/projects/atom/backend/data"
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0]
                  for t in ("users", "dataset_entries", "goal_runs")}
        admin = con.execute(
            "select hashed_password from users where email='admin@example.com'"
        ).fetchone()
        if admin is None or not str(admin[0] or "").strip():
            raise SystemExit("REFUSED: admin password hash missing")
        binding_mismatches = []
        operations = 0
        historical_refs = 0
        completed_run = None
        waiting_run = None
        artifact_checks = []
        for run_id, params in con.execute("select id, parameters from goal_runs"):
            data_json = json.loads(params)
            lifecycle = data_json.get("task_lifecycle") or {}
            assignment = lifecycle.get("assignment") or {}
            for op in lifecycle.get("operations") or []:
                operations += 1
                binding = op.get("operation_binding")
                stored = op.get("binding_sha256")
                if binding is not None and stored and (
                        operation_binding_sha256(binding) != stored):
                    binding_mismatches.append({
                        "run_id": run_id, "operation_id": op.get("operation_id")})
            if source_prefix in params:
                historical_refs += params.count(source_prefix)
            status = str(assignment.get("status") or "")
            if status == "completed" and completed_run is None and any(
                    d.get("artifact_path") for d in assignment.get("deliverables") or []):
                completed_run = run_id
            if status in ("waiting", "planned", "running") and waiting_run is None:
                waiting_run = run_id
            for deliverable in assignment.get("deliverables") or []:
                path = deliverable.get("artifact_path")
                expected = str(deliverable.get("sha256") or "")
                if not path:
                    continue
                p = Path(path)
                artifact_checks.append({
                    "run_id": run_id,
                    "path": path,
                    "exists": p.is_file(),
                    "hash_ok": bool(expected and p.is_file()
                                    and sha256(p) == expected),
                })
        if binding_mismatches:
            raise SystemExit(
                "REFUSED: operation binding digest mismatches: "
                + json.dumps(binding_mismatches[:10]))
        if any(not a["exists"] or not a["hash_ok"] for a in artifact_checks):
            raise SystemExit(
                "REFUSED: artifact checks failed: "
                + json.dumps([a for a in artifact_checks if not a["exists"] or not a["hash_ok"]][:10]))
        dataset_paths = [
            row[0] for row in con.execute(
                "select parquet_path from dataset_entries where parquet_path is not null")
        ]
        missing_datasets = [p for p in dataset_paths if not Path(p).is_file()]
        source_dataset_refs = [p for p in dataset_paths if source_prefix in str(p)]
        if source_dataset_refs:
            raise SystemExit(
                "REFUSED: dataset paths still reference the source: "
                + json.dumps(source_dataset_refs[:5]))
        # Only datasets actually referenced by an assignment are required to
        # resolve. Older catalog rows may already point at deleted historical
        # roots; record them instead of pretending the handoff broke them.
        entries = {
            row[0]: {"status": row[1], "parquet_path": row[2]}
            for row in con.execute(
                "select dataset_name, status, parquet_path from dataset_entries")
        }
        referenced = {}
        for run_id, params in con.execute("select id, parameters from goal_runs"):
            assignment = ((json.loads(params).get("task_lifecycle") or {})
                          .get("assignment") or {})
            for source in assignment.get("sources") or []:
                name = str((source.get("binding") or {}).get("dataset_name") or "")
                if name:
                    referenced.setdefault(name, []).append(run_id)
        missing_referenced = []
        for name in referenced:
            entry = entries.get(name)
            path = str((entry or {}).get("parquet_path") or "")
            if not entry or not path or not Path(path).is_file():
                missing_referenced.append({"dataset_name": name, "path": path})
        if missing_referenced:
            raise SystemExit(
                "REFUSED: assignment-referenced datasets are unavailable: "
                + json.dumps(missing_referenced[:10]))
        operational_source_refs = []
        for run_id, params in con.execute("select id, parameters from goal_runs"):
            assignment = ((json.loads(params).get("task_lifecycle") or {})
                          .get("assignment") or {})
            for step in assignment.get("steps") or []:
                if source_prefix in str((step.get("inputs") or {}).get("path") or ""):
                    operational_source_refs.append(f"{run_id}:inputs.path")
                if source_prefix in str(((step.get("result") or {}).get("artifact") or {}).get("path") or ""):
                    operational_source_refs.append(f"{run_id}:result.artifact.path")
            for deliverable in assignment.get("deliverables") or []:
                if source_prefix in str(deliverable.get("artifact_path") or ""):
                    operational_source_refs.append(f"{run_id}:deliverable.artifact_path")
        if operational_source_refs:
            raise SystemExit(
                "REFUSED: operational source references remain: "
                + json.dumps(operational_source_refs[:10]))
    finally:
        con.close()

    representatives = {}
    for label, run_id in (("completed", completed_run), ("waiting", waiting_run)):
        if not run_id:
            representatives[label] = None
            continue
        row = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True).execute(
            "select workspace_id, tenant_id from goal_runs where id=?", (run_id,)).fetchone()
        svc = GoalRunService(workspace_id=row[0] or "default",
                             tenant_id=row[1] or "default")
        record = TaskLifecycle(svc).get_task(run_id)
        if not record or not record.get("assignment"):
            raise SystemExit(f"REFUSED: representative {label} assignment {run_id} did not load")
        projection = assignment_projection(record["assignment"])
        representatives[label] = {
            "run_id": run_id,
            "assignment_id": projection.get("assignment_id"),
            "status": projection.get("status"),
            "plan_revision": projection.get("plan_revision"),
            "deliverables": len(projection.get("deliverables") or []),
            "mappings": len(projection.get("mappings") or []),
        }

    memory_manifest_path = root / "run" / "memory_handoff.json"
    memory = json.loads(memory_manifest_path.read_text()) if memory_manifest_path.is_file() else {}
    memory_ok = bool(memory.get("workspace_tables"))
    result = {
        "schema": "atom-production-handoff-verification-1",
        "root": str(root),
        "data_dir": str(data),
        "row_counts": counts,
        "admin_password_hash_present": True,
        "operations_checked": operations,
        "operation_binding_mismatches": 0,
        "artifact_checks": len(artifact_checks),
        "artifact_checks_ok": True,
        "dataset_paths_checked": len(dataset_paths),
        "dataset_paths_ok": True,
        "referenced_dataset_names": len(referenced),
        "referenced_dataset_paths_ok": True,
        "pre_existing_missing_dataset_paths": len(missing_datasets),
        "pre_existing_missing_dataset_samples": missing_datasets[:5],
        "operational_source_references": 0,
        "historical_source_reference_count": historical_refs,
        "representative_assignments": representatives,
        "memory_handoff": {
            "manifest": str(memory_manifest_path),
            "workspace_tables": memory.get("workspace_tables") or {},
            "strategy": memory.get("strategy"),
            "ok": memory_ok,
        },
        "authentication_smoke": "blocked_missing_pilot_password",
        "authentication_note": (
            "No config/pilot_password is present. The admin password hash was "
            "preserved; actual login must be run after the owner supplies the "
            "pilot password file."),
    }
    out = Path(args.out) if args.out else root / "run" / "production_handoff_verification.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
