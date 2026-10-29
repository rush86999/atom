#!/usr/bin/env python3
"""Seed an isolated rehearsal data directory from an existing Atom data dir.

This is for rehearsal only. It never writes to the source data directory and
never copies production secrets into the package by default. Artifact and
dataset paths stored in the copied database are rewritten to the rehearsal
root so the copied assignment opens its copied artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import bcrypt


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
    finally:
        target.close()
        source.close()


def counts(path: Path) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        out = {}
        for table in ("users", "dataset_entries", "goal_runs", "hitl_interventions"):
            try:
                out[table] = con.execute(f"select count(*) from {table}").fetchone()[0]
            except sqlite3.Error:
                out[table] = None
        return out
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--password-file", default="")
    ap.add_argument("--include-memory", action="store_true",
                    help="copy the (large) LanceDB memory store too")
    args = ap.parse_args()
    source = Path(args.source).resolve()
    data = Path(args.data_dir).resolve()
    if source == data:
        raise SystemExit("REFUSED: source and destination data dirs are identical")
    data.mkdir(parents=True, exist_ok=True)

    src_db = source / "atom.db"
    if not src_db.is_file():
        raise SystemExit(f"REFUSED: missing {src_db}")
    backup_db(src_db, data / "atom.db")
    for name in ("office", "sheet_datasets", "email_attachments"):
        src = source / name
        if src.is_dir():
            dst = data / name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, symlinks=False)
    memory = data / "atom_memory"
    memory.mkdir(parents=True, exist_ok=True)
    if args.include_memory:
        src = source / "atom_memory"
        if src.is_dir():
            if memory.exists():
                shutil.rmtree(memory)
            shutil.copytree(src, memory, symlinks=False)
    for name in ("byok_config.json", "byok_keys.json", "byok_encryption_key"):
        src = source / name
        if src.is_file():
            shutil.copy2(src, data / name)
            os.chmod(data / name, 0o600)

    password = secrets.token_urlsafe(18)
    con = sqlite3.connect(data / "atom.db")
    try:
        row = con.execute(
            "select id,email from users where email='admin@example.com'").fetchone()
        if not row:
            raise SystemExit("REFUSED: admin@example.com not present in seed database")
        con.execute(
            "update users set hashed_password=?, two_factor_enabled=0, "
            "two_factor_secret=null, status='active' where id=?",
            (bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
             row[0]))
        # Rewrite absolute artifact/dataset paths into the rehearsal root.
        src_prefix = str(source)
        dst_prefix = str(data)
        for table, column in (
            ("goal_runs", "parameters"),
            ("dataset_entries", "parquet_path"),
            ("ingested_documents", "file_path"),
        ):
            try:
                con.execute(
                    f"update {table} set {column}=replace({column}, ?, ?) "
                    f"where {column} like ?",
                    (src_prefix, dst_prefix, f"%{src_prefix}%"))
                con.commit()
            except sqlite3.Error:
                con.rollback()
        con.commit()
    finally:
        con.close()

    password_file = Path(args.password_file).resolve() if args.password_file else (
        data.parent / "config" / "rehearsal_admin_password")
    password_file.parent.mkdir(parents=True, exist_ok=True)
    password_file.write_text(password + "\n")
    os.chmod(password_file, 0o600)

    before = counts(src_db)
    after = counts(data / "atom.db")
    manifest = {
        "schema": "atom-rehearsal-seed-1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_data_dir": str(source),
        "rehearsal_data_dir": str(data),
        "database_sha256": sha256(data / "atom.db"),
        "row_counts_source": before,
        "row_counts_rehearsal": after,
        "row_counts_preserved": before == after,
        "password_file": str(password_file),
        "password_file_mode": oct(password_file.stat().st_mode & 0o777),
        "secrets_copied": False,
    }
    (data.parent / "run").mkdir(parents=True, exist_ok=True)
    (data.parent / "run" / "rehearsal_seed.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if before != after:
        raise SystemExit("REFUSED: rehearsal row counts differ from source")


if __name__ == "__main__":
    main()
