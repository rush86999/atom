"""Controlled evidence for the complete Shopify product material repair.

No live provider, model, account, credential or dev database is touched.
TESTING=1 plus explicit scratch DATABASE_URL/data/Lance/output keep every
import and test on a scratch world.  Only ``ShopifyService.http`` is doubled
inside the controls.

The failure-first capture temporarily puts the predecessor
``backend/core/shopify_mutations.py`` (HEAD^) back on disk and runs the new
controls against it, then restores the committed source in a finally block.
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
SOURCE = BACKEND / "core" / "shopify_mutations.py"
TEST = BACKEND / "tests" / "test_oracle_shopify_product_authorized_material.py"
PROBE = OUT / "root_probe" / "test_lead_shopify_authorized_material.py"

FOCUSED_NODES = [
    "tests/test_oracle_shopify_product_authorized_material.py",
    "tests/test_oracle_shopify_product_create.py",
    "tests/test_oracle_shopify_product_replay.py",
    "tests/test_oracle_registry_verification_gap.py",
    "tests/test_oracle_connected_mutations.py",
    "tests/test_generic_oracle_mutation_contract.py",
    "tests/test_shopify_fulfillment_actions.py",
]
# The real alembic upgrade node needs the project venv's passlib.  This
# machine's pytest interpreter has no passlib, so the unrelated environment
# gate is excluded and disclosed; the migration revision contract node still
# runs.
DESELECT = [
    "tests/test_oracle_shopify_product_replay.py::"
    "test_alembic_upgrade_records_revision_keeps_old_claim_and_restart_replays_once",
]

env = dict(os.environ)
env.update({
    "TESTING": "1",
    "ENVIRONMENT": "test",
    "SECRET_KEY": "synthetic-shopify-material-evidence-key-not-a-secret",
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


def _run(name, nodes, *, extra_args=(), cwd=BACKEND):
    xml_path = OUT / f"{name}.xml"
    command = [
        sys.executable, "-m", "pytest", *nodes,
        "-q", "--disable-warnings",
        f"--junitxml={xml_path}",
        *extra_args,
    ]
    completed = subprocess.run(
        command, cwd=str(cwd), env=env, capture_output=True, text=True)
    log = (
        "$ " + " ".join(command)
        + f"\ncwd={cwd}\n\nSTDOUT\n"
        + completed.stdout
        + "\nSTDERR\n"
        + completed.stderr
    )
    (OUT / f"{name}.log").write_text(log, encoding="utf-8")
    payload = {
        "command": command,
        "cwd": str(cwd),
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
    """Run the new controls against the predecessor material projection."""
    committed = SOURCE.read_bytes()
    predecessor = subprocess.check_output(
        ["git", "show", "HEAD^:backend/core/shopify_mutations.py"], cwd=ROOT)
    assert predecessor != committed
    try:
        SOURCE.write_bytes(predecessor)
        result = _run(
            "failure-first",
            ["tests/test_oracle_shopify_product_authorized_material.py"])
    finally:
        SOURCE.write_bytes(committed)
        assert _sha256(SOURCE) == hashlib.sha256(committed).hexdigest()
    return result


def main():
    failure_first = _failure_first()
    focused = _run(
        "focused", FOCUSED_NODES,
        extra_args=("--deselect", DESELECT[0]))
    probe = _run(
        "root-probe",
        ["../docs/acceptance/evidence/shopify_product_material_7cc5471f7/"
         "root_probe/test_lead_shopify_authorized_material.py"])
    verification = {
        "task": "registered Shopify product complete authorized material",
        "git_branch": subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT, text=True).strip(),
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source": {
            "path": str(SOURCE.relative_to(ROOT)),
            "sha256": _sha256(SOURCE),
        },
        "test": {
            "path": str(TEST.relative_to(ROOT)),
            "sha256": _sha256(TEST),
        },
        "root_probe_fixture": {
            "path": str(PROBE.relative_to(ROOT)),
            "sha256": _sha256(PROBE),
            "note": (
                "Exact content of root's supplied 3-negative/3-positive "
                "probe, copied into evidence so the fixture is reproducible "
                "against this source."),
        },
        "runs": {
            "failure_first": failure_first,
            "focused": focused,
            "root_probe": probe,
        },
        "deselected": DESELECT,
        "environment": {
            "TESTING": "1",
            "DATABASE_URL": env["DATABASE_URL"],
            "ATOM_DATA_DIR": env["ATOM_DATA_DIR"],
            "LANCEDB_URI": env["LANCEDB_URI"],
            "ATOM_OUTPUT_DIR": env["ATOM_OUTPUT_DIR"],
            "provider_credentials": "blank",
            "external_http": "ShopifyService.http doubled inside the tests only",
        },
        "expectation": {
            "failure_first_exit_code": 1,
            "focused_exit_code": 0,
            "root_probe_exit_code": 0,
        },
    }
    (OUT / "verification.json").write_text(
        json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "failure_first": failure_first["exit_code"],
        "focused": focused["exit_code"],
        "root_probe": probe["exit_code"],
    }, indent=2))


if __name__ == "__main__":
    main()
