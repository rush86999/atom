"""Derive packet metadata hashes without regenerating any test evidence."""
from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    return {
        "tests": int(suite.get("tests") or 0),
        "failures": int(suite.get("failures") or 0),
        "errors": int(suite.get("errors") or 0),
        "skipped": int(suite.get("skipped") or 0),
    }


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        check=False).stdout.strip()


failure_first_log = OUT / "failure-first.log"
failure_first_exit = {
    "command": [
        "python", "-m", "pytest",
        "tests/test_oracle_shopify_product_replay.py::"
        "test_known_success_replays_exact_resource_without_second_create",
        "-q", "--disable-warnings",
    ],
    "cwd": str(ROOT / "backend"),
    "code_source": "0b325c5f1e8de97a352f1d202cd1e8d13e21140b",
    "head_at_capture": "556bc4e40c6955a433d4b439957a8423d88fe0f1",
    "exit_code": 1,
    "captured_from_shell_exit_status": True,
    "log_sha256": _sha(failure_first_log),
    "log_bytes": failure_first_log.stat().st_size,
    "observed_status": "committed_unverified",
    "observed_action_result": "already_applied_unverified",
}
(OUT / "failure-first-exit.json").write_text(
    json.dumps(failure_first_exit, indent=2) + "\n", encoding="utf-8")

artifact_details = []
artifacts = {}
for path in sorted(OUT.iterdir()):
    if not path.is_file() or path.name == "MANIFEST.json":
        continue
    digest = _sha(path)
    artifacts[path.name] = digest
    artifact_details.append({
        "file": path.name,
        "sha256": digest,
        "bytes": path.stat().st_size,
    })

source_paths = [
    "backend/core/generic_agent.py",
    "backend/core/models.py",
    "backend/core/outbound_operation_claim.py",
    "backend/core/sqlite_schema_repair.py",
    "backend/tests/test_oracle_shopify_product_create.py",
    "backend/tests/test_oracle_shopify_product_replay.py",
]
source_commit = _git("rev-parse", "HEAD")
source_files = {}
for source_path in source_paths:
    blob = subprocess.run(
        ["git", "show", f"{source_commit}:{source_path}"],
        cwd=ROOT, capture_output=True, check=False).stdout
    source_files[source_path] = hashlib.sha256(blob).hexdigest()

manifest = {
    "executed_source": source_commit,
    "source_files": source_files,
    "journey": "Registered Shopify product-create durable exact replay",
    "date": "2026-11-07",
    "owner": (
        "Agent2 Shopify Oracle family; independent acceptance retained by root"),
    "source_identity": {
        "worktree": str(ROOT),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "base_commit": "556bc4e40c6955a433d4b439957a8423d88fe0f1",
        "product_code_predecessor": (
            "0b325c5f1e8de97a352f1d202cd1e8d13e21140b"),
        "source_commit": _git("rev-parse", "HEAD"),
        "source_commit_subject": _git("log", "-1", "--format=%s"),
        "run_tree": {
            "tracked_modified": _git(
                "status", "--porcelain", "--untracked-files=no"),
            "note": (
                "tracked tree clean at the implementation commit; the packet "
                "and retained scratch are untracked evidence"),
        },
    },
    "scope": {
        "implemented": "shopify_create_product durable exact replay",
        "mechanism": (
            "existing TaskOperationRecord claim + durable result/receipt, "
            "frozen request expectations, GenericAgent mutation consumer, "
            "existing ShopifyService transport and postcondition Oracle"),
        "not_implemented": [
            "shopify_create_blog",
            "shopify_create_article",
            "shopify_create_fulfillment",
        ],
        "no_new": [
            "operation engine",
            "provider router",
            "table/store",
            "approval lifecycle",
            "title-based resource lookup",
        ],
    },
    "environment": {
        "python": "3.14.7",
        "TESTING": "1",
        "SECRET_KEY": "explicit synthetic value; not recorded",
        "DATABASE_URL": "fresh scratch sqlite under this packet",
        "ATOM_DATA_DIR": "packet scratch/data",
        "LANCEDB_URI": "packet scratch/lancedb",
        "LANCEDB_URI_BASE": "packet scratch/lancedb",
        "ATOM_OUTPUT_DIR": "packet scratch/output",
        "provider_credentials": (
            "SHOPIFY_API_KEY, SHOPIFY_API_SECRET, SHOPIFY_SHOP_NAME and live "
            "model keys pinned to empty strings"),
        "live_effects": "none",
        "external_transport_double": "ShopifyService.http only",
    },
    "failure_first": failure_first_exit,
    "result": {
        **_counts(OUT / "focused.xml"),
        "exit_code": json.loads(
            (OUT / "focused-exit.json").read_text())["exit_code"],
    },
    "artifacts": artifacts,
    "artifact_details": artifact_details,
    "retained_scratch": "scratch (owned scratch; not part of the commit)",
}
(OUT / "MANIFEST.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "source_commit": manifest["source_identity"]["source_commit"],
    "result": manifest["result"],
    "artifacts": len(artifacts),
}, indent=2))
