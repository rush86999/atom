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
    "backend/alembic/versions/20261107_task_operation_result_json.py",
    "backend/core/generic_agent.py",
    "backend/core/oracle/__init__.py",
    "backend/core/oracle/postcondition_verifiers.py",
    "backend/core/outbound_operation_claim.py",
    "backend/core/shopify_mutations.py",
    "backend/core/sqlite_schema_repair.py",
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
    "journey": "Shopify durable product-create replay: shared-core repair",
    "date": "2026-11-07",
    "owner": (
        "Agent2 Shopify Oracle family; independent acceptance retained by root"),
    "source_identity": {
        "worktree": str(ROOT),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "predecessor_replay_source": (
            "963a27781b58d606e0fe47e78f5ccf008cc597c2"),
        "predecessor_product_source": (
            "0b325c5f1e8de97a352f1d202cd1e8d13e21140b"),
        "source_commit": source_commit,
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
        "implemented": (
            "domain-neutral durable replay receipt, fail-closed proof JSON, "
            "existing-database result_json upgrade"),
        "mechanism": (
            "existing TaskOperationRecord claim + oracle-registered durable "
            "receipt projector/matcher, strict JSON persistence boundary, "
            "guarded SQLite repair + alembic revision"),
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
        "LANCEDB_PATH": "packet scratch/lancedb",
        "ATOM_OFFICE_DIR": "packet scratch/office",
        "ATOM_OUTPUT_DIR": "packet scratch/output",
        "provider_credentials": (
            "SHOPIFY_API_KEY, SHOPIFY_API_SECRET, SHOPIFY_SHOP_NAME and live "
            "model keys pinned to empty strings"),
        "live_effects": "none",
        "external_transport_double": "ShopifyService.http only",
    },
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
