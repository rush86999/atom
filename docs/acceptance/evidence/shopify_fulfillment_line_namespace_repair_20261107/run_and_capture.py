#!/usr/bin/env python3
"""Capture the FO-line/order-line namespace repair with actual exits.

Phases
------
failure-first-line-namespace
    The new permanent probe against pre-repair source b813c2a1f, extracted
    from git into a disposable tree.  Expected red: one POST occurred.

exact6
    The full permanent independent control file on the clean committed repair
    source.  Six probes, including the new missing-order-line binding.

affected
    The integrated fulfillment contract/caller controls affected by the
    namespace split.

Only ``ShopifyService.http`` is doubled by the tests.  Every phase uses
``TESTING=1`` and a fresh scratch SQLite database.  No live provider, model,
browser, server, account or credential is contacted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

PACKET = Path(__file__).resolve().parent
REPO = PACKET.parents[3]
BACKEND = REPO / "backend"
FAILURE_SOURCE = "b813c2a1f"

PHASES = {
    "failure-first-line-namespace": [
        "tests/test_lead_shopify_fulfillment_rest_shape.py::"
        "test_missing_order_line_identity_cannot_borrow_fulfillment_order_line_id",
    ],
    "exact6": [
        "tests/test_lead_shopify_fulfillment_rest_shape.py",
    ],
    "affected": [
        "tests/test_oracle_shopify_fulfillment_create.py",
        "tests/test_shopify_fulfillment_actions.py",
        "tests/test_covpush_w95_shopify.py::TestFulfillments",
        "tests/test_covpush_saaspair.py::test_shopify_fulfillments",
        "tests/test_covpush_saaspair.py::test_shopify_create_fulfillment_minimal",
        "tests/test_covpush_intgr_b.py::TestShopifyService::test_write_operations",
        "tests/test_covpush_w87_freshdesk_trello_shopify.py::test_sh_write_endpoints",
    ],
}

SOURCE_FILES = [
    "backend/core/shopify_mutations.py",
    "backend/core/oracle/postcondition_verifiers.py",
    "backend/integrations/shopify_service.py",
    "backend/tests/test_lead_shopify_fulfillment_rest_shape.py",
    "backend/tests/test_oracle_shopify_fulfillment_create.py",
    "backend/tests/test_covpush_w95_shopify.py",
]


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO, text=True).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_source(revision: str, root: Path) -> Path:
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", revision, "backend"], cwd=REPO)
    target = root / "source"
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        tar.extractall(target)
    return target / "backend"


def _counts(output: str) -> dict:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary = lines[-1] if lines else ""
    counts = {}
    for value, label in re.findall(
            r"(\d+) (failed|passed|error|errors|skipped|deselected)", summary):
        counts["errors" if label == "error" else label] = int(value)
    return counts


def _run_phase(phase: str, source_rev: str | None = None) -> int:
    scratch = Path(tempfile.mkdtemp(
        prefix=f"fulfillment-line-{phase}-",
        dir=os.environ.get("ATOM_EVIDENCE_TMP") or None,
    ))
    backend = _extract_source(source_rev, scratch) if source_rev else BACKEND
    xml_path = PACKET / f"{phase}.xml"
    log_path = PACKET / f"{phase}.log"
    exit_path = PACKET / f"{phase}-exit.json"
    env = os.environ.copy()
    env.update({
        "TESTING": "1",
        "SECRET_KEY": "synthetic-not-a-secret",
        "DATABASE_URL": f"sqlite:///{scratch / 'scratch.db'}",
        "ENABLE_SCHEDULER": "false",
        "PYTHONPATH": str(backend),
    })
    command = [
        sys.executable, "-m", "pytest", *PHASES[phase], "-q",
        "--basetemp", str(scratch / "basetemp"),
        "-p", "no:cacheprovider",
        f"--junitxml={xml_path}",
    ]
    started = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(
        command, cwd=backend, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    finished = datetime.now(timezone.utc).isoformat()
    log_path.write_text(completed.stdout, encoding="utf-8")
    payload = {
        "phase": phase,
        "started_utc": started,
        "finished_utc": finished,
        "source_revision": source_rev or _git("rev-parse", "HEAD"),
        "source_revision_meaning": (
            "pre-repair source extracted from git" if source_rev
            else "clean committed repair source"),
        "command": command,
        "cwd": str(backend),
        "exit_code": completed.returncode,
        "counts": _counts(completed.stdout),
        "database_url": env["DATABASE_URL"],
        "testing": env["TESTING"],
    }
    exit_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.rmtree(scratch, ignore_errors=True)
    print(json.dumps({
        "phase": phase,
        "exit_code": completed.returncode,
        "counts": payload["counts"],
        "source_revision": payload["source_revision"],
    }, sort_keys=True))
    return completed.returncode


def _bind_source() -> None:
    binding = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "head": _git("rev-parse", "HEAD"),
        "head_subject": _git("log", "-1", "--format=%s"),
        "main_merged": _git("rev-parse", "origin/main"),
        "python": sys.version,
        "python_executable": sys.executable,
        "files": {
            name: _sha256(REPO / name)
            for name in SOURCE_FILES if (REPO / name).exists()
        },
        "status_porcelain": _git("status", "--porcelain").splitlines(),
        "live_calls": False,
        "credentials_used": False,
        "http_leaf_only_doubled": True,
        "testing": "1",
    }
    (PACKET / "source-binding.json").write_text(
        json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    statuses = {
        "failure-first-line-namespace": _run_phase(
            "failure-first-line-namespace", FAILURE_SOURCE),
        "exact6": _run_phase("exact6"),
        "affected": _run_phase("affected"),
    }
    _bind_source()
    overall = 0 if statuses["exact6"] == 0 and statuses["affected"] == 0 else 1
    (PACKET / "matrix-exit.json").write_text(
        json.dumps({
            "phases": statuses,
            "overall_exit": overall,
            "expected_failure_first_exit": 1,
            "exact6_and_affected_exit": 0,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
