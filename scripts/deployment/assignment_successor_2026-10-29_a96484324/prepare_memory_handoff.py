#!/usr/bin/env python3
"""Export the required LanceDB memory into a prepared production root.

Chosen strategy: a read-only logical export of the tables required by the
declared admin workspace and the default document/agent retrieval paths. The
source may have active readers/writers; we read each table at its current
LanceDB version and write a fresh target table, so no second writer is attached
to the source and no mutable source file is copied.

Required workspace tables: documents, business_facts, agent_experience,
chat_messages, ingestion_metadata, integration_zoho, formula_cards.
Small root-level tables are exported too. The 7.2 GiB workspace
``atom_communications`` archive and the 30 GiB legacy ``default_shared``
workspace are intentionally omitted; they remain preserved at the source.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import lancedb

REQUIRED_TABLES = (
    "documents",
    "business_facts",
    "agent_experience",
    "chat_messages",
    "ingestion_metadata",
    "integration_zoho",
    "formula_cards",
)
ROOT_TABLES = (
    "documents",
    "chat_messages",
    "atom_communications",
    "ingestion_metadata",
    "turn_facts",
    "exchange_examples",
    "knowledge_graph",
)
OPTIONAL_WORKSPACE_TABLES = ("atom_communications",)


def dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def active_writers() -> list[str]:
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid=,command="], capture_output=True, text=True,
            timeout=20).stdout
    except Exception:
        return []
    return [
        line.strip()[:300] for line in out.splitlines()
        if any(n in line for n in ("uvicorn", "main_api_app", "gunicorn"))
    ]


def export_table(source_db, target_db, name: str) -> dict:
    table = source_db.open_table(name)
    version = getattr(table, "version", None)
    rows = table.count_rows()
    data = table.to_arrow()
    target_db.create_table(name, data, mode="create")
    target_rows = target_db.open_table(name).count_rows()
    if target_rows != rows:
        raise SystemExit(
            f"REFUSED: table {name} row count source={rows} target={target_rows}")
    return {"version": version, "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-memory-dir", required=True)
    ap.add_argument("--target-memory-dir", required=True)
    ap.add_argument("--workspace", default="default")
    ap.add_argument("--min-free-gib", type=float, default=20.0)
    ap.add_argument("--include-communications", action="store_true")
    args = ap.parse_args()
    source = Path(args.source_memory_dir).resolve()
    target = Path(args.target_memory_dir).resolve()
    workspace = str(args.workspace or "default")
    if source == target:
        raise SystemExit("REFUSED: source and target memory dirs are identical")
    source_ws = source / workspace
    if not source_ws.is_dir():
        raise SystemExit(f"REFUSED: source workspace store missing: {source_ws}")
    target_ws = target / workspace
    if target_ws.exists() and any(target_ws.iterdir()):
        raise SystemExit(f"REFUSED: target workspace already has data: {target_ws}")

    tables = list(REQUIRED_TABLES)
    if args.include_communications:
        tables.extend(OPTIONAL_WORKSPACE_TABLES)
    required = sum(
        dir_size(source_ws / f"{name}.lance") for name in tables
        if (source_ws / f"{name}.lance").is_dir()
    )
    required += sum(
        dir_size(source / f"{name}.lance") for name in ROOT_TABLES
        if (source / f"{name}.lance").is_dir()
    )
    probe = target
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free - required < int(args.min_free_gib * 1024**3):
        raise SystemExit(
            f"REFUSED: export needs {required/1024**3:.2f} GiB; free "
            f"{free/1024**3:.2f} GiB would leave less than "
            f"{args.min_free_gib:.1f} GiB headroom")

    writers = active_writers()
    target.mkdir(parents=True, exist_ok=True)
    target_ws.mkdir(parents=True, exist_ok=True)
    source_db = lancedb.connect(str(source_ws))
    target_db = lancedb.connect(str(target_ws))
    workspace_export = {}
    for name in tables:
        if name not in source_db.table_names():
            continue
        workspace_export[name] = export_table(source_db, target_db, name)

    root_export = {}
    source_root = lancedb.connect(str(source))
    target_root = lancedb.connect(str(target))
    for name in ROOT_TABLES:
        if name not in source_root.table_names():
            continue
        root_export[name] = export_table(source_root, target_root, name)

    omitted = {}
    for name in OPTIONAL_WORKSPACE_TABLES:
        if name in tables:
            continue
        path = source_ws / f"{name}.lance"
        if path.is_dir():
            omitted[f"workspace/{name}"] = {
                "bytes": dir_size(path),
                "reason": "large communication archive; not required for document/assignment retrieval",
            }
    shared = source / "default_shared"
    if shared.is_dir():
        omitted["workspace/default_shared"] = {
            "bytes": dir_size(shared),
            "reason": "legacy shared workspace not used by the declared admin workspace",
        }
    manifest = {
        "schema": "atom-memory-handoff-1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_memory_dir": str(source),
        "target_memory_dir": str(target),
        "workspace_migrated": workspace,
        "strategy": "read-only-logical-export-required-tables",
        "workspace_tables": workspace_export,
        "root_tables": root_export,
        "omitted": omitted,
        "required_bytes": required,
        "free_bytes_before": free,
        "free_bytes_after_estimate": free - required,
        "min_free_gib": args.min_free_gib,
        "active_writer_processes_seen": writers,
        "source_access": "read-only LanceDB table export at recorded versions",
        "source_mutated": False,
        "indexes": (
            "Data rows are preserved. LanceDB ANN/FTS indexes are rebuildable "
            "from the exported rows and are not copied as mutable index files."),
    }
    run = target.parent.parent / "run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "memory_handoff.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
