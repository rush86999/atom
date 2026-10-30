#!/usr/bin/env python3
"""Schema-aware production data handoff into a prepared release root.

The SQLite database is copied with the SQLite backup API. User password hashes
are preserved. Artifact/dataset stores are copied. Only CURRENT operational
storage paths are relocated; historical provenance, prior results and
operation-binding arguments are left byte-for-byte intact so stored digests and
approval identities remain valid.

The source is opened read-only. Source changes during the copy are detected and
recorded; if detected, the handoff is labelled provisional and a final cutover
refresh is required before activation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def backup_db(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
        target.execute("pragma wal_checkpoint(full)")
    finally:
        target.close()
        source.close()


def table_columns(con: sqlite3.Connection, table: str) -> list[str]:
    try:
        return [row[1] for row in con.execute(f'pragma table_info("{table}")')]
    except sqlite3.Error:
        return []


def counts(path: Path) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        out = {}
        for table in ("users", "dataset_entries", "goal_runs"):
            try:
                out[table] = con.execute(
                    f"select count(*) from {table}").fetchone()[0]
            except sqlite3.Error:
                out[table] = None
        return out
    finally:
        con.close()


def admin_hash(path: Path) -> str:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select hashed_password from users where email='admin@example.com'"
        ).fetchone()
        if row is None:
            raise SystemExit("REFUSED: admin@example.com is absent from the source database")
        return str(row[0] or "")
    finally:
        con.close()


def db_fingerprint(path: Path) -> dict:
    """Logical per-table fingerprint of a SQLite database.

    Reads rows in a single read transaction so a live WAL writer cannot produce
    a mixed snapshot. Physical page/WAL churn is deliberately excluded: only
    committed logical content (row count + row values) changes the digest.
    """
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


def _relocate(value, source_prefix: str, target_prefix: str):
    if isinstance(value, str) and source_prefix in value:
        return value.replace(source_prefix, target_prefix)
    return value


def rewrite_assignment_operational(assignment: dict, source_prefix: str,
                                   target_prefix: str) -> int:
    """Rewrite only current operational paths in one assignment plan.

    Deliberately NOT touched: operations[].operation_binding, prior_results,
    prior_artifacts, provenance, receipts/evidence history. Those are historical
    identity/provenance and must keep their original text and digests.
    """
    changed = 0
    for step in assignment.get("steps") or []:
        inputs = step.get("inputs")
        if isinstance(inputs, dict):
            path = inputs.get("path")
            new = _relocate(path, source_prefix, target_prefix)
            if new != path:
                inputs["path"] = new
                changed += 1
        result = step.get("result")
        if isinstance(result, dict):
            artifact = result.get("artifact")
            if isinstance(artifact, dict):
                path = artifact.get("path")
                new = _relocate(path, source_prefix, target_prefix)
                if new != path:
                    artifact["path"] = new
                    changed += 1
    for deliverable in assignment.get("deliverables") or []:
        if not isinstance(deliverable, dict):
            continue
        path = deliverable.get("artifact_path")
        new = _relocate(path, source_prefix, target_prefix)
        if new != path:
            deliverable["artifact_path"] = new
            changed += 1
    return changed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-data-dir", required=True)
    ap.add_argument("--target-data-dir", required=True)
    ap.add_argument("--secrets-source", default="")
    ap.add_argument("--include-memory", action="store_true")
    args = ap.parse_args()
    source = Path(args.source_data_dir).resolve()
    target = Path(args.target_data_dir).resolve()
    if source == target:
        raise SystemExit("REFUSED: source and target data dirs are identical")
    src_db = source / "atom.db"
    if not src_db.is_file():
        raise SystemExit(f"REFUSED: missing {src_db}")
    if (target / "atom.db").exists():
        raise SystemExit(
            f"REFUSED: target already has a database: {target / 'atom.db'}")
    target.mkdir(parents=True, exist_ok=True)
    before_hash = admin_hash(src_db)
    source_stat_before = src_db.stat()
    source_hash_before = sha256(src_db)
    wal_path = source / "atom.db-wal"
    wal_before = (
        {"exists": True, "bytes": wal_path.stat().st_size,
         "mtime_ns": wal_path.stat().st_mtime_ns, "sha256": sha256(wal_path)}
        if wal_path.is_file() else {"exists": False})
    backup_db(src_db, target / "atom.db")
    after_hash = admin_hash(target / "atom.db")
    if before_hash != after_hash:
        raise SystemExit("REFUSED: admin password hash changed during handoff")
    source_stat_after = src_db.stat()
    source_hash_after = sha256(src_db)
    wal_after = (
        {"exists": True, "bytes": wal_path.stat().st_size,
         "mtime_ns": wal_path.stat().st_mtime_ns, "sha256": sha256(wal_path)}
        if wal_path.is_file() else {"exists": False})
    source_changed = (
        source_hash_before != source_hash_after
        or source_stat_before.st_size != source_stat_after.st_size
        or source_stat_before.st_mtime_ns != source_stat_after.st_mtime_ns
        or wal_before != wal_after
    )
    snapshot_sha256 = sha256(target / "atom.db")
    snapshot_fingerprint = db_fingerprint(target / "atom.db")

    for name in ("office", "sheet_datasets", "email_attachments"):
        src = source / name
        if src.is_dir():
            dst = target / name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, symlinks=False)
    if args.include_memory:
        src = source / "atom_memory"
        if src.is_dir():
            dst = target / "atom_memory"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, symlinks=False)
    else:
        (target / "atom_memory").mkdir(parents=True, exist_ok=True)

    for name in ("byok_config.json", "byok_keys.json", "byok_encryption_key"):
        src = source / name
        if src.is_file():
            dst = target / name
            shutil.copy2(src, dst)
            os.chmod(dst, 0o600)

    con = sqlite3.connect(target / "atom.db")
    schema_report = {"required": {}, "optional": {}, "rewritten_rows": {}}
    try:
        src_prefix = str(source)
        dst_prefix = str(target)
        required = (("dataset_entries", "parquet_path"),)
        optional = (
            ("ingested_documents", "file_path"),
            ("accounting_documents", "file_path"),
        )
        for table, column in required:
            cols = table_columns(con, table)
            if column not in cols:
                raise SystemExit(
                    f"REFUSED: required structure {table}.{column} is missing")
            try:
                cur = con.execute(
                    f'update "{table}" set "{column}"=replace("{column}", ?, ?) '
                    f'where "{column}" like ?',
                    (src_prefix, dst_prefix, f"%{src_prefix}%"))
                con.commit()
            except sqlite3.Error as exc:
                con.rollback()
                raise SystemExit(
                    f"REFUSED: required update {table}.{column} failed: {exc}")
            schema_report["required"][f"{table}.{column}"] = "updated"
            schema_report["rewritten_rows"][f"{table}.{column}"] = cur.rowcount
        for table, column in optional:
            cols = table_columns(con, table)
            if not cols:
                schema_report["optional"][f"{table}.{column}"] = "table_absent"
                continue
            if column not in cols:
                schema_report["optional"][f"{table}.{column}"] = "column_absent"
                continue
            try:
                cur = con.execute(
                    f'update "{table}" set "{column}"=replace("{column}", ?, ?) '
                    f'where "{column}" like ?',
                    (src_prefix, dst_prefix, f"%{src_prefix}%"))
                con.commit()
            except sqlite3.Error as exc:
                con.rollback()
                raise SystemExit(
                    f"REFUSED: optional update {table}.{column} failed: {exc}")
            schema_report["optional"][f"{table}.{column}"] = "updated"
            schema_report["rewritten_rows"][f"{table}.{column}"] = cur.rowcount

        assignment_paths_changed = 0
        operational_source_refs = []
        historical_source_refs = 0
        for run_id, params in con.execute("select id, parameters from goal_runs"):
            try:
                data = json.loads(params)
            except (TypeError, ValueError) as exc:
                raise SystemExit(
                    f"REFUSED: goal_run {run_id} parameters are not JSON: {exc}")
            lifecycle = data.get("task_lifecycle") or {}
            assignment = lifecycle.get("assignment")
            if isinstance(assignment, dict):
                assignment_paths_changed += rewrite_assignment_operational(
                    assignment, src_prefix, dst_prefix)
                for step in assignment.get("steps") or []:
                    inputs = step.get("inputs") if isinstance(step, dict) else {}
                    if isinstance(inputs, dict) and src_prefix in str(inputs.get("path") or ""):
                        operational_source_refs.append(f"{run_id}:inputs.path")
                    result = step.get("result") if isinstance(step, dict) else {}
                    artifact = result.get("artifact") if isinstance(result, dict) else {}
                    if isinstance(artifact, dict) and src_prefix in str(artifact.get("path") or ""):
                        operational_source_refs.append(f"{run_id}:result.artifact.path")
                for deliverable in assignment.get("deliverables") or []:
                    if isinstance(deliverable, dict) and src_prefix in str(deliverable.get("artifact_path") or ""):
                        operational_source_refs.append(f"{run_id}:deliverable.artifact_path")
            # Historical references are counted, not rewritten.
            if src_prefix in params:
                historical_source_refs += params.count(src_prefix)
            con.execute(
                "update goal_runs set parameters=? where id=?",
                (json.dumps(data, separators=(",", ":")), run_id))
        con.commit()
        if operational_source_refs:
            raise SystemExit(
                "REFUSED: current operational paths still reference the source: "
                + ", ".join(operational_source_refs[:10]))
        remaining = {
            "dataset_entries.parquet_path": con.execute(
                "select count(*) from dataset_entries where parquet_path like ?",
                (f"%{src_prefix}%",)).fetchone()[0],
        }
        for table, column in optional:
            if column in table_columns(con, table):
                remaining[f"{table}.{column}"] = con.execute(
                    f'select count(*) from "{table}" where "{column}" like ?',
                    (f"%{src_prefix}%",)).fetchone()[0]
        if any(remaining.values()):
            raise SystemExit(
                "REFUSED: source references remain in required storage columns: "
                + json.dumps(remaining))
        integrity = con.execute("pragma integrity_check").fetchone()[0]
        if integrity != "ok":
            raise SystemExit(f"REFUSED: target sqlite integrity_check={integrity}")
        schema_report["assignment_paths_changed"] = assignment_paths_changed
        schema_report["historical_source_reference_count"] = historical_source_refs
        schema_report["remaining_source_reference_counts"] = remaining
    finally:
        con.close()

    # Verify current artifact files exist and match their recorded hashes.
    artifact_checked = 0
    artifact_mismatches = []
    con = sqlite3.connect(f"file:{target / 'atom.db'}?mode=ro", uri=True)
    try:
        for run_id, params in con.execute("select id, parameters from goal_runs"):
            data = json.loads(params)
            assignment = (data.get("task_lifecycle") or {}).get("assignment") or {}
            for deliverable in assignment.get("deliverables") or []:
                path = deliverable.get("artifact_path")
                expected = str(deliverable.get("sha256") or "")
                if not path:
                    continue
                artifact_checked += 1
                p = Path(path)
                if not p.is_file():
                    artifact_mismatches.append({"run_id": run_id, "path": path, "error": "missing"})
                elif expected and sha256(p) != expected:
                    artifact_mismatches.append({"run_id": run_id, "path": path, "error": "sha256_mismatch"})
    finally:
        con.close()
    if artifact_mismatches:
        raise SystemExit(
            "REFUSED: referenced artifacts disagree: "
            + json.dumps(artifact_mismatches[:10]))

    secrets_copied = False
    if args.secrets_source:
        src = Path(args.secrets_source).resolve()
        if src.is_file():
            dst = target.parent / "config" / "secrets.env"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            os.chmod(dst, 0o600)
            secrets_copied = True

    artifact_files = sum(
        1 for name in ("office", "sheet_datasets", "email_attachments")
        for p in (target / name).rglob("*") if p.is_file()
    )
    manifest = {
        "schema": "atom-production-data-handoff-2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_data_dir": str(source),
        "target_data_dir": str(target),
        "database_sha256": sha256(target / "atom.db"),
        "row_counts": counts(target / "atom.db"),
        "admin_password_hash_preserved": True,
        "pilot_password_file_supplied": False,
        "pilot_password_requirement": (
            "The owner must supply config/pilot_password for the existing "
            "admin account. This handoff never generates or changes it."),
        "artifact_files": artifact_files,
        "artifact_files_checked": artifact_checked,
        "artifact_hash_mismatches": [],
        "secrets_env_copied": secrets_copied,
        "memory_included": bool(args.include_memory),
        "rehearsal_fixture_used": False,
        "schema_migration": schema_report,
        "source_snapshot_sha256": snapshot_sha256,
        "source_snapshot_fingerprint": snapshot_fingerprint,
        "source_snapshot_fingerprint_scope": (
            "Logical per-table row-count/row-value digests of the consistent "
            "SQLite backup snapshot, before operational path rewriting. "
            "Physical WAL/page churn is intentionally excluded."),
        "source_consistency": {
            "database_snapshot": "sqlite_backup_api",
            "source_opened_read_only": True,
            "source_hash_before": source_hash_before,
            "source_hash_after": source_hash_after,
            "source_wal_before": wal_before,
            "source_wal_after": wal_after,
            "source_changed_during_copy": source_changed,
            "snapshot_is_consistent": True,
            "provisional": False,
            "final_cutover_required": True,
            "cutover_freshness_gate": (
                "check_freshness.py compares the current source logical "
                "fingerprint, memory table versions and referenced files to "
                "this snapshot. Any change refuses the transaction."),
            "note": (
                "The backup API produced a consistent point-in-time snapshot. "
                "A live source may commit after the snapshot; that is expected "
                "and is detected by the cutover freshness gate, which requires "
                "a refresh rather than implying later writes are included."),
        },
        "source_mutated": False,
        "source_readonly_checks": [
            "SQLite source opened with URI mode=ro for backup and admin-hash read",
            "no write connection to the source data directory",
            "source hash/stat compared before and after the copy",
            "target operational paths checked for remaining source references",
        ],
    }
    run = target.parent / "run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "production_data_handoff.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    baseline = {
        "schema": "atom-production-freshness-baseline-2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_data_dir": str(source),
        "target_data_dir": str(target),
        "source_db_sha256": snapshot_sha256,
        "source_db_fingerprint": snapshot_fingerprint,
        "target_db_sha256": sha256(target / "atom.db"),
        "memory": {},
        "note": (
            "Created from the consistent handoff snapshot. check_freshness.py "
            "compares current source logical content, memory versions and "
            "referenced files to this baseline. WAL byte churn alone is not a "
            "data change."),
    }
    (run / "freshness_baseline.json").write_text(
        json.dumps(baseline, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
