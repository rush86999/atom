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
    if (not path.is_file() or path.name == "MANIFEST.json"
            or path.name == "scratch"):
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
    "journey": (
        "Shopify durable product-create replay: migration identity and "
        "existing-database upgrade"),
    "date": "2026-11-07",
    "owner": (
        "Agent2 Shopify Oracle family; independent acceptance retained by root"),
    "source_identity": {
        "worktree": str(ROOT),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "predecessor_source": (
            "6ed0fc82e8ec1846b84c11ef00c0f04a6550e168"),
        "predecessor_evidence": (
            "docs/acceptance/evidence/shopify_product_replay_6ed0fc82e "
            "(preserved unchanged)"),
        "source_commit": source_commit,
        "source_commit_subject": _git("log", "-1", "--format=%s"),
        "run_tree": {
            "tracked_modified": _git(
                "status", "--porcelain", "--untracked-files=no"),
            "note": (
                "tracked tree clean at the implementation commit; the packet "
                "and retained scratch are evidence"),
        },
    },
    "scope": {
        "implemented": (
            "revision identifier within Alembic's String(32) version column; "
            "real predecessor-database upgrade/restart control"),
        "mechanism": (
            "existing guarded alembic revision on the existing "
            "TaskOperationRecord table; no new table/engine/lifecycle"),
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
        "database_qualification": "SQLite executed only; no PostgreSQL runtime claim",
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
