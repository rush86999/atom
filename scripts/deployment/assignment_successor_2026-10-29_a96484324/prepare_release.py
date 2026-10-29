#!/usr/bin/env python3
"""Build one self-contained, reversible assignment-successor release.

The product app is a shallow git clone at the frozen release tag, so
``/api/health`` can report the exact source revision the process loaded.  The
deployment kit is copied beside it as an overlay and checksummed separately.

This script does not start services and does not copy production data unless
``--seed-data-from`` is explicitly supplied for an isolated rehearsal.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_identity import (  # noqa: E402
    EXPECTED_PRODUCT_TREE_SHA256,
    PRODUCT_PATHS,
    RELEASE_COMMIT,
    RELEASE_TAG,
    TESTED_RUNTIME_COMMIT,
    atomic_write_json,
    product_tree_sha256,
    sha256_file,
    sha256_tree,
)


def run(cmd: list[str], **kw) -> None:
    subprocess.run(cmd, check=True, **kw)


def copy_frontend_build(app: Path, release: Path, api_origin: str,
                        node_modules: Path | None) -> str:
    frontend_src = app / "frontend-nextjs"
    copied_node_modules = False
    existing = frontend_src / "node_modules"
    if existing.is_symlink():
        existing.unlink()
    if node_modules and not existing.exists():
        shutil.copytree(node_modules, existing, symlinks=True)
        copied_node_modules = True
    env = dict(os.environ)
    env["NEXT_PUBLIC_API_URL"] = api_origin
    env["NEXT_PUBLIC_ALLOW_LOOPBACK"] = "1"
    env["NODE_OPTIONS"] = "--max-old-space-size=4096"
    run(["npm", "run", "build"], cwd=frontend_src, env=env)

    standalone = frontend_src / ".next" / "standalone"
    if not standalone.is_dir():
        raise SystemExit("REFUSED: frontend build did not produce .next/standalone")
    dst = release / "frontend"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(standalone, dst, symlinks=False)
    static_dst = dst / ".next" / "static"
    static_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(frontend_src / ".next" / "static", static_dst, symlinks=False)
    public_src = frontend_src / "public"
    if public_src.is_dir():
        shutil.copytree(public_src, dst / "public", symlinks=False, dirs_exist_ok=True)
    build_id = (frontend_src / ".next" / "BUILD_ID").read_text().strip()
    if copied_node_modules:
        shutil.rmtree(frontend_src / "node_modules", ignore_errors=True)
    return build_id


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--tag", default=RELEASE_TAG)
    ap.add_argument("--expected-commit", default=RELEASE_COMMIT)
    ap.add_argument("--api-origin", default="http://127.0.0.1:8071")
    ap.add_argument("--api-port", type=int, default=8071)
    ap.add_argument("--frontend-port", type=int, default=3130)
    ap.add_argument("--python-bin", default=sys.executable)
    ap.add_argument("--node-modules", default="")
    ap.add_argument("--seed-data-from", default="")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    root = Path(args.root).resolve()
    commit = subprocess.check_output(
        ["git", "rev-parse", args.tag], cwd=repo, text=True).strip()
    if commit != args.expected_commit:
        raise SystemExit(
            f"REFUSED: tag {args.tag} is {commit}, expected {args.expected_commit}")

    release = root / "releases" / commit
    app = release / "app"
    release.mkdir(parents=True, exist_ok=True)
    for sub in ("config", "data", "backups", "logs", "run", "rehearsal"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    if not app.is_dir():
        run(["git", "clone", "--depth", "1", "--branch", args.tag,
             f"file://{repo}", str(app)])
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=app, text=True).strip()
    if head != commit:
        raise SystemExit(f"REFUSED: app HEAD {head} != {commit}")
    # The packaged app is disposable; remove build residue before checks.
    run(["git", "reset", "--hard", "HEAD"], cwd=app)
    run(["git", "clean", "-fd"], cwd=app)
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=app, text=True).strip()
    if dirty:
        raise SystemExit(f"REFUSED: packaged app is dirty:\n{dirty}")
    tree_hash = product_tree_sha256(app, "HEAD")
    if tree_hash != EXPECTED_PRODUCT_TREE_SHA256:
        raise SystemExit(
            f"REFUSED: product tree {tree_hash} != tested {EXPECTED_PRODUCT_TREE_SHA256}")

    node_modules = Path(args.node_modules).resolve() if args.node_modules else None
    build_id = copy_frontend_build(app, release, args.api_origin, node_modules)
    run(["git", "reset", "--hard", "HEAD"], cwd=app)
    run(["git", "clean", "-fd"], cwd=app)
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=app, text=True).strip()
    if dirty:
        raise SystemExit(f"REFUSED: build left tracked changes:\n{dirty}")

    kit_src = Path(__file__).resolve().parent
    kit_dst = release / "scripts"
    if kit_dst.exists():
        shutil.rmtree(kit_dst)
    shutil.copytree(kit_src, kit_dst, symlinks=False)
    docs_src = repo / "docs" / "deployment" / "assignment_successor_2026-10-29_a96484324"
    if docs_src.is_dir():
        shutil.copytree(docs_src, release / "docs", dirs_exist_ok=True)
    acceptance_docs_src = (
        repo / "docs" / "acceptance"
        / "assignment-successor-package-2026-10-29-a96484324")
    if acceptance_docs_src.is_dir():
        shutil.copytree(
            acceptance_docs_src,
            release / "docs" / "acceptance"
            / "assignment-successor-package-2026-10-29-a96484324",
            dirs_exist_ok=True)

    data = root / "data"
    env = {
        "ATOM_DEPLOYMENT_AUDIENCE": "single_user",
        "ATOM_PILOT_USER_EMAIL": "admin@example.com",
        "ATOM_OFFICE_FILE_AUTHZ": "single_user_shared_namespace",
        "ATOM_LOCAL_ONLY": "false",
        "ATOM_LLM_PROVIDER_POLICY": json.dumps({
            "mode": "selected",
            "allowed_providers": ["deepseek"],
            "preferred": {"provider": "deepseek", "model": "deepseek-flash"},
        }, separators=(",", ":")),
        "ATOM_PREFERRED_LLM_PROVIDER": "deepseek",
        "ATOM_PREFERRED_LLM_MODEL": "deepseek-flash",
        "ATOM_REVIEW_MODEL": "deepseek-flash",
        "ATOM_REVIEW_STRUCTURED": "1",
        "ATOM_CHAT_STREAMING": "false",
        "ATOM_CHAT_TURN_BUDGET_SECONDS": "180",
        "ATOM_CHAT_REQUEST_DEADLINE_SECONDS": "180",
        "ALLOWED_ORIGINS": "http://127.0.0.1:3130,http://localhost:3130",
        "ATOM_DATA_DIR": str(data),
        "DATABASE_URL": f"sqlite:///{data / 'atom.db'}",
        "LANCEDB_URI": str(data / "atom_memory"),
        "ATOM_OFFICE_DIR": str(data / "office"),
        "ATOM_ASSIGNMENT_OUTPUT_DIR": str(data / "office" / "assignments"),
        "ATOM_EMAIL_ATTACHMENT_DIR": str(data / "email_attachments"),
        "BYOK_CONFIG_FILE": str(data / "byok_config.json"),
        "BYOK_KEYS_FILE": str(data / "byok_keys.json"),
        "BYOK_ENC_KEY_FILE": str(data / "byok_encryption_key"),
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS": "0",
        "ATOM_ASSIGNMENT_ALLOW_LIVE_SEND": "0",
        "ATOM_EMAIL_SEND_DISABLED": "1",
        "ATOM_ASSIGNMENT_WORKER_TOPOLOGY": "one_worker_process_per_assignment",
        "API_PORT": str(args.api_port),
        "FE_PORT": str(args.frontend_port),
        "PYTHON_BIN": args.python_bin,
    }
    env_path = root / "config" / "env.release"
    lines = []
    for key, value in env.items():
        text = str(value)
        if key.endswith("_POLICY") or any(ch in text for ch in " {}\"'"):
            text = "'" + text.replace("'", "'\\''") + "'"
        lines.append(f"{key}={text}")
    env_path.write_text("\n".join(lines) + "\n")

    if args.seed_data_from:
        src = Path(args.seed_data_from).resolve()
        run([sys.executable, str(kit_src / "seed_rehearsal.py"),
             "--source", str(src), "--data-dir", str(data)])
        # The rehearsal copy must never retain live absolute paths. Enforce it
        # here as a package-build invariant, independent of the seed helper.
        import sqlite3
        con = sqlite3.connect(data / "atom.db")
        try:
            for table, column in (
                ("goal_runs", "parameters"),
                ("dataset_entries", "parquet_path"),
            ):
                try:
                    con.execute(
                        f"update {table} set {column}=replace({column}, ?, ?) "
                        f"where {column} like ?",
                        (str(src), str(data), f"%{src}%"))
                    con.commit()
                except sqlite3.Error:
                    con.rollback()
            remaining = con.execute(
                "select count(*) from goal_runs where parameters like ?",
                (f"%{src}%",)).fetchone()[0]
            if remaining:
                raise SystemExit(
                    f"REFUSED: rehearsal seed still references {remaining} live rows")
        finally:
            con.close()

    source_manifest = Path(__file__).resolve().parent / "source_manifest.json"
    identity = {
        "schema": "atom-assignment-successor-release-1",
        "release_tag": args.tag,
        "release_commit": commit,
        "tested_runtime_commit": TESTED_RUNTIME_COMMIT,
        "product_paths": list(PRODUCT_PATHS),
        "product_tree_sha256": tree_hash,
        "product_tree_matches_tested": tree_hash == EXPECTED_PRODUCT_TREE_SHA256,
        "source_manifest_sha256": sha256_file(source_manifest),
        "deployment_kit_tree_sha256": sha256_tree(kit_src),
        "frontend_build_id": build_id,
        "frontend_api_origin": args.api_origin,
        "api_port": args.api_port,
        "frontend_port": args.frontend_port,
        "audience": "single_user",
        "pilot_email": "admin@example.com",
        "outbound_scope": "draft_and_approval_only",
        "send_authorized": False,
        "topology": "one_worker_process_per_assignment",
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data),
        "seeded_rehearsal_data": bool(args.seed_data_from),
    }
    atomic_write_json(root / "RELEASE_IDENTITY.json", identity)
    atomic_write_json(release / "RELEASE_IDENTITY.json", identity)

    current = root / "current"
    if current.is_symlink() or current.exists():
        previous = root / "previous"
        if previous.is_symlink() or previous.exists():
            previous.unlink()
        previous.symlink_to(current.resolve())
        current.unlink()
    current.symlink_to(release)
    print(json.dumps(identity, indent=2))


if __name__ == "__main__":
    main()
