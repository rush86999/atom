#!/usr/bin/env python3
"""Detect source changes since the production handoff snapshot.

Run immediately before cutover. Reads only; never writes the source or target
application data. A stale result must refresh the handoff from the current
source before activation.

The comparison is logical, not byte-level: SQLite WAL files churn on every
commit and even on checkpoints, so a raw WAL hash is not evidence that the
data changed. This check fingerprints committed table content (row counts and
row values), memory table versions/rows, and the referenced artifact/dataset
files that production retrieval depends on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import lancedb


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_writer_processes(source_root: Path) -> dict:
    """Processes holding the source SQLite files open.

    A fresh logical snapshot is not enough for cutover while a live writer can
    commit immediately after the check. Production cutover therefore requires
    an explicit quiescence boundary: no other process may hold the source
    database/WAL open. This is read-only (lsof), never a kill or lock.
    """
    lsof = shutil.which("lsof")
    if not lsof:
        return {"available": False, "error": "lsof not found", "processes": []}
    paths = [str(source_root / name) for name in (
        "atom.db", "atom.db-wal", "atom.db-shm")]
    paths = [path for path in paths if Path(path).exists()]
    if not paths:
        return {"available": True, "processes": []}
    try:
        out = subprocess.run(
            [lsof, "-nP", "-Fpc", "--", *paths],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception as exc:  # noqa: BLE001
        return {"available": False,
                "error": f"{type(exc).__name__}: {exc}",
                "processes": []}
    processes = []
    current = {}
    for line in out.splitlines():
        if line.startswith("p"):
            if current:
                processes.append(current)
            current = {"pid": int(line[1:])}
        elif line.startswith("c") and current:
            current["command"] = line[1:]
    if current:
        processes.append(current)
    own = os.getpid()
    processes = [p for p in processes if p.get("pid") != own]
    return {"available": True, "processes": processes}


def db_fingerprint(path: Path) -> dict:
    """Logical per-table fingerprint inside one read transaction."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.execute("pragma busy_timeout=30000")
    try:
        con.execute("begin")
        tables = [row[0] for row in con.execute(
            "select name from sqlite_master where type='table' "
            "and name not like 'sqlite_%' order by name")]
        out = {}
        for name in tables:
            try:
                con.execute(f'select rowid from "{name}" limit 1').fetchone()
                order = "rowid"
            except sqlite3.Error:
                info = list(con.execute(f'pragma table_info("{name}")'))
                pk = [row[1] for row in info if row[5]]
                order = ", ".join(
                    f'"{col}"' for col in (pk or [row[1] for row in info]))
            digest = hashlib.sha256()
            rows = 0
            for row in con.execute(f'select * from "{name}" order by {order}'):
                digest.update(repr(row).encode("utf-8", "surrogatepass"))
                digest.update(b"\x1e")
                rows += 1
            out[name] = {"rows": rows, "sha256": digest.hexdigest()}
        con.commit()
        return out
    finally:
        con.close()


def memory_state(manifest: dict) -> dict:
    source = Path(manifest["source_memory_dir"])
    workspace = manifest["workspace_migrated"]
    out = {"workspace": {}, "root": {}}
    for label, path, names in (
        ("workspace", source / workspace,
         (manifest.get("workspace_tables") or {})),
        ("root", source, (manifest.get("root_tables") or {})),
    ):
        db = lancedb.connect(str(path))
        for name in names:
            try:
                table = db.open_table(name)
                out[label][name] = {
                    "version": getattr(table, "version", None),
                    "rows": table.count_rows(),
                }
            except Exception as exc:  # noqa: BLE001
                out[label][name] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def target_checks(target_db: Path, target_root: Path, source_root: Path) -> dict:
    con = sqlite3.connect(f"file:{target_db}?mode=ro", uri=True)
    changed = []
    checked = 0
    try:
        for table, column in (("dataset_entries", "parquet_path"),):
            for path, in con.execute(
                    f'select "{column}" from "{table}" '
                    f'where "{column}" is not null'):
                p = Path(path)
                if not str(p).startswith(str(target_root)):
                    continue
                src = Path(str(p).replace(str(target_root), str(source_root), 1))
                if not p.is_file() or not src.is_file():
                    continue
                checked += 1
                if sha256(p) != sha256(src):
                    changed.append(
                        {"kind": table, "target": str(p), "source": str(src)})
        for params, in con.execute("select parameters from goal_runs"):
            assignment = ((json.loads(params).get("task_lifecycle") or {})
                          .get("assignment") or {})
            for deliverable in assignment.get("deliverables") or []:
                path = deliverable.get("artifact_path")
                if not path:
                    continue
                p = Path(path)
                if not str(p).startswith(str(target_root)):
                    continue
                src = Path(str(p).replace(str(target_root), str(source_root), 1))
                if not p.is_file() or not src.is_file():
                    continue
                checked += 1
                if sha256(p) != sha256(src):
                    changed.append(
                        {"kind": "artifact", "target": str(p),
                         "source": str(src)})
    finally:
        con.close()
    return {"checked": checked, "changed": changed}


def fingerprint_changes(baseline: dict, current: dict) -> list[dict]:
    changed = []
    for name in sorted(set(baseline) | set(current)):
        before = baseline.get(name)
        after = current.get(name)
        if before != after:
            changed.append({
                "table": name,
                "baseline": before,
                "current": after,
            })
    return changed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--phase", default="preflight")
    ap.add_argument("--require-quiescent-source", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    handoff = json.loads(
        (root / "run" / "production_data_handoff.json").read_text())
    memory = json.loads((root / "run" / "memory_handoff.json").read_text())
    baseline_path = root / "run" / "freshness_baseline.json"
    if not baseline_path.is_file():
        raise SystemExit(
            "REFUSED: freshness baseline missing; refresh the data handoff "
            "before cutover")
    baseline = json.loads(baseline_path.read_text())
    source_root = Path(handoff["source_data_dir"])
    target_root = Path(handoff["target_data_dir"])
    source_db = source_root / "atom.db"
    target_db = target_root / "atom.db"

    writer_check = source_writer_processes(source_root)
    current_fingerprint = db_fingerprint(source_db)
    table_changes = fingerprint_changes(
        baseline.get("source_db_fingerprint") or {}, current_fingerprint)
    current_memory = memory_state(memory)
    memory_changed = current_memory != (baseline.get("memory") or {})
    file_checks = target_checks(target_db, target_root, source_root)

    changes = []
    if args.require_quiescent_source:
        if not writer_check["available"]:
            changes.append({
                "item": "source_quiescence",
                "reason": "cannot verify source writers",
                "detail": writer_check.get("error"),
            })
        elif writer_check["processes"]:
            changes.append({
                "item": "source_quiescence",
                "reason": (
                    "source writers remain active; stop them with operational "
                    "authorization before cutover"),
                "processes": writer_check["processes"],
            })
    if table_changes:
        changes.append({
            "item": "source_db_fingerprint",
            "changed_tables": table_changes[:50],
            "changed_table_count": len(table_changes),
        })
    if memory_changed:
        changes.append({
            "item": "memory",
            "baseline": baseline.get("memory"),
            "current": current_memory,
        })
    if baseline.get("target_db_sha256"):
        actual_target = sha256(target_db)
        if actual_target != baseline["target_db_sha256"]:
            changes.append({
                "item": "target_db",
                "baseline_sha256": baseline["target_db_sha256"],
                "current_sha256": actual_target,
            })
    if file_checks["changed"]:
        changes.append({
            "item": "referenced_files",
            "changed": file_checks["changed"][:20],
            "changed_count": len(file_checks["changed"]),
        })

    report = {
        "schema": "atom-production-freshness-check-2",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "fresh": not changes,
        "changes": changes,
        "phase": args.phase,
        "require_quiescent_source": bool(args.require_quiescent_source),
        "source_writers": writer_check,
        "source_tables_fingerprinted": len(current_fingerprint),
        "source_table_changes": len(table_changes),
        "memory_unchanged": not memory_changed,
        "referenced_files_checked": file_checks["checked"],
        "baseline": str(baseline_path),
        "baseline_created_at": baseline.get("created_at"),
        "comparison": (
            "logical SQLite table content + LanceDB table versions/rows + "
            "referenced artifact/dataset hashes; WAL byte churn excluded"),
    }
    out = Path(args.out) if args.out else root / "run" / "freshness_check.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["fresh"] else 2)


if __name__ == "__main__":
    main()
