"""Exact-source controlled evidence run for the Shopify product Oracle vertical.

No provider, account, credential or live dev DB is touched.  TESTING=1 plus
explicit scratch DATABASE_URL/data/Lance/output keep every import and test on
the scratch world.  The suite sums to an exact node list; only Shopify HTTP is
doubled inside the product controls.
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
SCRATCH.mkdir(parents=True, exist_ok=True)

NODES = [
    "tests/test_oracle_shopify_product_create.py",
    "tests/test_oracle_registry_verification_gap.py",
    "tests/test_oracle_connected_mutations.py",
    "tests/test_generic_oracle_mutation_contract.py",
    "tests/test_shopify_fulfillment_actions.py",
]

env = dict(os.environ)
env.update({
    "TESTING": "1",
    "ENVIRONMENT": "test",
    "SECRET_KEY": "synthetic-shopify-oracle-evidence-key-not-a-secret",
    "DATABASE_URL": f"sqlite:///{SCRATCH / 'atom.db'}",
    "ATOM_DATA_DIR": str(SCRATCH / "data"),
    "LANCEDB_URI": str(SCRATCH / "lancedb"),
    "LANCEDB_URI_BASE": str(SCRATCH / "lancedb"),
    "ATOM_OUTPUT_DIR": str(SCRATCH / "output"),
    "PYTHONDONTWRITEBYTECODE": "1",
})
for key in (
    "SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_SHOP_NAME",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
):
    env[key] = ""

xml_path = OUT / "focused.xml"
command = [
    sys.executable, "-m", "pytest", *NODES,
    "-q", "--disable-warnings",
    f"--junitxml={xml_path}",
]
completed = subprocess.run(
    command, cwd=BACKEND, env=env, capture_output=True, text=True)
log = (
    "$ "
    + " ".join(command)
    + "\n\nSTDOUT\n"
    + completed.stdout
    + "\nSTDERR\n"
    + completed.stderr
)
(OUT / "focused.log").write_text(log, encoding="utf-8")
(OUT / "focused-exit.json").write_text(
    json.dumps({
        "command": command,
        "cwd": str(BACKEND),
        "exit_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(
            completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(
            completed.stderr.encode()).hexdigest(),
    }, indent=2) + "\n",
    encoding="utf-8",
)
(OUT / "focused-spec.json").write_text(
    json.dumps({
        "nodes": NODES,
        "environment": {
            "TESTING": env["TESTING"],
            "DATABASE_URL": env["DATABASE_URL"],
            "ATOM_DATA_DIR": env["ATOM_DATA_DIR"],
            "LANCEDB_URI": env["LANCEDB_URI"],
            "LANCEDB_URI_BASE": env["LANCEDB_URI_BASE"],
            "ATOM_OUTPUT_DIR": env["ATOM_OUTPUT_DIR"],
            "SECRET_KEY": "<synthetic not recorded>",
            "provider_credentials": "pinned to empty strings",
        },
        "python": sys.version,
    }, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps({
    "exit_code": completed.returncode,
    "log": str(OUT / "focused.log"),
    "xml": str(xml_path),
}, indent=2))
sys.exit(completed.returncode)
