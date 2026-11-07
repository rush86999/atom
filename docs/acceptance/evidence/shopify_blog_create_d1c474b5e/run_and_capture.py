"""Controlled evidence for the registered Shopify blog-create Oracle vertical.

No live provider, model, account, credential or dev database is touched.
TESTING=1 plus explicit scratch DATABASE_URL/data/Lance/output keep every
import and test on a scratch world.  Only ``ShopifyService.http`` is doubled
inside the controls.

The failure-first capture temporarily restores the predecessor versions of
the six implementation files (HEAD^), runs the new blog controls against
them, then restores the committed source in a finally block.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/private/tmp/atom-agent-job-baseline")
BACKEND = ROOT / "backend"
OUT = Path(__file__).resolve().parent
SCRATCH = OUT / "scratch"
for child in ("", "data", "lancedb", "output"):
    (SCRATCH / child).mkdir(parents=True, exist_ok=True)

IMPLEMENTATION_FILES = [
    "backend/core/action_registry.py",
    "backend/core/connected_actions.py",
    "backend/core/oracle/postcondition_verifiers.py",
    "backend/core/oracle/request_expectations.py",
    "backend/core/shopify_mutations.py",
    "backend/integrations/shopify_service.py",
]
TEST = BACKEND / "tests" / "test_oracle_shopify_blog_create.py"

FOCUSED_NODES = [
    "tests/test_oracle_shopify_blog_create.py",
    "tests/test_oracle_shopify_product_authorized_material.py",
    "tests/test_oracle_shopify_product_create.py",
    "tests/test_oracle_shopify_product_replay.py",
    "tests/test_oracle_registry_verification_gap.py",
    "tests/test_oracle_connected_mutations.py",
    "tests/test_generic_oracle_mutation_contract.py",
    "tests/test_shopify_fulfillment_actions.py",
    "tests/test_covpush_w95_shopify.py",
]
# The real alembic upgrade node needs the project venv's passlib.  This
# machine's pytest interpreter has no passlib, so the unrelated environment
# gate is excluded and disclosed; the migration revision contract node runs.
DESELECT = [
    "tests/test_oracle_shopify_product_replay.py::"
    "test_alembic_upgrade_records_revision_keeps_old_claim_and_restart_replays_once",
]

env = dict(os.environ)
env.update({
    "TESTING": "1",
    "ENVIRONMENT": "test",
    "SECRET_KEY": "synthetic-shopify-blog-evidence-key-not-a-secret",
    "DATABASE_URL": f"sqlite:///{SCRATCH / 'atom.db'}",
    "ATOM_DATA_DIR": str(SCRATCH / "data"),
    "LANCEDB_URI": str(SCRATCH / "lancedb"),
    "LANCEDB_URI_BASE": str(SCRATCH / "lancedb"),
    "ATOM_OUTPUT_DIR": str(SCRATCH / "output"),
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONPATH": str(BACKEND),
})
for key in (
    "SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_SHOP_NAME",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
):
    env[key] = ""


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _run(name, nodes, *, extra_args=()):
    xml_path = OUT / f"{name}.xml"
    command = [
        sys.executable, "-m", "pytest", *nodes,
        "-q", "--disable-warnings",
        f"--junitxml={xml_path}",
        *extra_args,
    ]
    completed = subprocess.run(
        command, cwd=str(BACKEND), env=env, capture_output=True, text=True)
    log = (
        "$ " + " ".join(command)
        + f"\ncwd={BACKEND}\n\nSTDOUT\n"
        + completed.stdout
        + "\nSTDERR\n"
        + completed.stderr
    )
    (OUT / f"{name}.log").write_text(log, encoding="utf-8")
    payload = {
        "command": command,
        "cwd": str(BACKEND),
        "exit_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(
            completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(
            completed.stderr.encode()).hexdigest(),
        "junitxml": str(xml_path.name) if xml_path.exists() else None,
    }
    (OUT / f"{name}-exit.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _failure_first():
    """Run the blog controls against the predecessor implementation."""
    committed = {
        relative: (ROOT / relative).read_bytes()
        for relative in IMPLEMENTATION_FILES
    }
    predecessor = {
        relative: subprocess.check_output(
            ["git", "show", f"HEAD^:{relative}"], cwd=ROOT)
        for relative in IMPLEMENTATION_FILES
    }
    assert any(predecessor[r] != committed[r] for r in IMPLEMENTATION_FILES)
    try:
        for relative, data in predecessor.items():
            (ROOT / relative).write_bytes(data)
        result = _run(
            "failure-first",
            ["tests/test_oracle_shopify_blog_create.py"])
    finally:
        for relative, data in committed.items():
            (ROOT / relative).write_bytes(data)
            assert _sha256(ROOT / relative) == hashlib.sha256(data).hexdigest()
    return result


def main():
    failure_first = _failure_first()
    focused = _run(
        "focused", FOCUSED_NODES,
        extra_args=("--deselect", DESELECT[0]))
    verification = {
        "task": "registered Shopify blog create exact-id/material Oracle",
        "git_branch": subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT, text=True).strip(),
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "implementation_files": {
            relative: _sha256(ROOT / relative)
            for relative in IMPLEMENTATION_FILES
        },
        "test": {
            "path": str(TEST.relative_to(ROOT)),
            "sha256": _sha256(TEST),
        },
        "runs": {
            "failure_first": failure_first,
            "focused": focused,
        },
        "deselected": DESELECT,
        "environment": {
            "TESTING": "1",
            "DATABASE_URL": env["DATABASE_URL"],
            "ATOM_DATA_DIR": env["ATOM_DATA_DIR"],
            "LANCEDB_URI": env["LANCEDB_URI"],
            "ATOM_OUTPUT_DIR": env["ATOM_OUTPUT_DIR"],
            "provider_credentials": "blank",
            "external_http": (
                "ShopifyService.http doubled inside the tests only"),
        },
        "expectation": {
            "failure_first_exit_code": 1,
            "focused_exit_code": 0,
        },
    }
    (OUT / "verification.json").write_text(
        json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "failure_first": failure_first["exit_code"],
        "focused": focused["exit_code"],
    }, indent=2))


if __name__ == "__main__":
    main()
