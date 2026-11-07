#!/usr/bin/env python3
"""Run the fulfillment repair matrix and capture the ACTUAL process exits.

Phases
------
failure-first
    The permanent independent control file against the handed-off source
    revision, extracted from git into a disposable directory.  This is the
    expected red state (five confirmed contract failures).

valid
    The same permanent control file plus the integrated positive/negative
    contract suite and the affected agent-surface caller controls.

callers
    The service/caller controls whose fulfillment-order fixtures were updated
    to the declared parent/location/line material.

Only ``ShopifyService.http`` is doubled inside the tests.  No live provider,
model, browser, server, account or credential is contacted.  Every phase uses
``TESTING=1`` and a fresh scratch SQLite database under the evidence scratch
directory.
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

PHASES = {
    "failure-first": [
        "tests/test_lead_shopify_fulfillment_rest_shape.py",
    ],
    "valid": [
        "tests/test_lead_shopify_fulfillment_rest_shape.py",
        "tests/test_oracle_shopify_fulfillment_create.py",
        "tests/test_shopify_fulfillment_actions.py",
        "tests/test_covpush_w95_shopify.py::TestFulfillments",
    ],
    "callers": [
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
    "backend/tests/test_shopify_fulfillment_actions.py",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO, text=True).strip()


def _extract_source(revision: str, root: Path) -> Path:
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", revision, "backend"], cwd=REPO)
    target = root / "source"
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        tar.extractall(target)
    return target / "backend"


def _counts(output: str) -> dict:
    """Parse only pytest's final summary line, never log lines.

    Log messages such as ``order-500 failed`` must not be mistaken for test
    counts; the evidence has to state the real outcome.
    """
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary = lines[-1] if lines else ""
    counts = {}
    for value, label in re.findall(
            r"(\d+) (failed|passed|error|errors|skipped|deselected)", summary):
        label = "errors" if label == "error" else label
        counts[label] = int(value)
    return counts


def _run_phase(phase: str, source_rev: str | None = None) -> int:
    scratch = Path(tempfile.mkdtemp(
        prefix=f"fulfillment-{phase}-",
        dir=os.environ.get("ATOM_EVIDENCE_TMP") or None,
    ))
    backend = BACKEND
    if source_rev:
        backend = _extract_source(source_rev, scratch)
    basetemp = scratch / "basetemp"
    db_path = scratch / "scratch.db"
    xml_path = PACKET / f"{phase}.xml"
    log_path = PACKET / f"{phase}.log"
    exit_path = PACKET / f"{phase}-exit.json"
    env = os.environ.copy()
    env.update({
        "TESTING": "1",
        "SECRET_KEY": "synthetic-not-a-secret",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "ENABLE_SCHEDULER": "false",
        "PYTHONPATH": str(backend),
    })
    command = [
        sys.executable, "-m", "pytest",
        *PHASES[phase],
        "-q",
        "--basetemp", str(basetemp),
        "-p", "no:cacheprovider",
        f"--junitxml={xml_path}",
    ]
    started = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(
        command, cwd=backend, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    finished = datetime.now(timezone.utc).isoformat()
    output = completed.stdout
    log_path.write_text(output, encoding="utf-8")
    payload = {
        "phase": phase,
        "started_utc": started,
        "finished_utc": finished,
        "source_revision": source_rev or _git("rev-parse", "HEAD"),
        "source_revision_meaning": (
            "handed-off pre-repair source extracted from git"
            if source_rev else "current repair working tree"),
        "command": command,
        "cwd": str(backend),
        "exit_code": completed.returncode,
        "counts": _counts(output),
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


def _source_binding() -> None:
    binding = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "head": _git("rev-parse", "HEAD"),
        "head_subject": _git("log", "-1", "--format=%s"),
        "python": sys.version,
        "python_executable": sys.executable,
        "files": {
            name: _sha256(REPO / name)
            for name in SOURCE_FILES
            if (REPO / name).exists()
        },
        "status_porcelain": _git("status", "--porcelain").splitlines(),
        "live_calls": False,
        "credentials_used": False,
        "http_leaf_only_doubled": True,
        "testing": "1",
    }
    (PACKET / "source-binding.json").write_text(
        json.dumps(binding, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "all":
        failure_rev = None
        if len(argv) > 1:
            failure_rev = argv[1]
        statuses = {
            "failure-first": _run_phase("failure-first", failure_rev),
            "valid": _run_phase("valid"),
            "callers": _run_phase("callers"),
        }
        _source_binding()
        overall = 0 if statuses["valid"] == 0 and statuses["callers"] == 0 else 1
        (PACKET / "matrix-exit.json").write_text(
            json.dumps({
                "phases": statuses,
                "overall_exit": overall,
                "expected_failure_first_exit": 1,
                "valid_and_callers_exit": 0,
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        return overall
    phase = argv[0]
    if phase not in PHASES:
        raise SystemExit(f"unknown phase: {phase}")
    return _run_phase(phase, argv[1] if len(argv) > 1 else None)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
