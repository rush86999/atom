"""Exact-source evidence for the consolidated MEM-07 chain.

No live model/provider/network/sandbox/account/credential/spend/send/install.
Only the Memento model transport is doubled with controlled text inside the
test. Fresh scratch SQLite/data/LANCE/output/basetemp are explicit.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/private/tmp/atom-mem07-20261107")
BACKEND = ROOT / "backend"
OUT = Path(__file__).resolve().parent
SCRATCH = Path("/private/tmp/atom-mem07-evidence/run-final")
for child in ("", "data", "lancedb", "output", "basetemp", "skills"):
    (SCRATCH / child).mkdir(parents=True, exist_ok=True)

NODES = [
    "tests/test_mem07_consolidated_chain.py",
    "tests/test_tool_error_memento_lifecycle.py",
    "tests/test_memento_candidate_review.py",
    "tests/test_reviewed_improvement_apply.py",
    "tests/test_reviewed_improvement_boundaries.py",
    "tests/test_reviewed_skill_agent_consumption.py",
    "tests/test_tool_error_evolution.py",
    "tests/test_autodev_review_routes.py",
]

env = dict(os.environ)
env.update({
    "TESTING": "1",
    "ENVIRONMENT": "test",
    "SECRET_KEY": "synthetic-mem07-consolidated-evidence-key",
    "DATABASE_URL": f"sqlite:///{SCRATCH / 'atom.db'}",
    "ATOM_DATA_DIR": str(SCRATCH / "data"),
    "LANCEDB_URI": str(SCRATCH / "lancedb"),
    "LANCEDB_URI_BASE": str(SCRATCH / "lancedb"),
    "ATOM_OUTPUT_DIR": str(SCRATCH / "output"),
    "ATOM_WORKSPACE_SKILLS_ROOT": str(SCRATCH / "skills"),
    "TMPDIR": str(SCRATCH / "basetemp"),
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONPATH": str(BACKEND),
})
for key in (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_SHOP_NAME",
):
    env[key] = ""

xml_path = OUT / "focused.xml"
command = [
    sys.executable, "-m", "pytest", *NODES,
    "-q", "--disable-warnings", f"--junitxml={xml_path}",
]
completed = subprocess.run(
    command, cwd=str(BACKEND), env=env, capture_output=True, text=True)
log = (
    "$ " + " ".join(command)
    + f"\ncwd={BACKEND}\n\nSTDOUT\n"
    + completed.stdout + "\nSTDERR\n" + completed.stderr)
(OUT / "focused.log").write_text(log, encoding="utf-8")
result = {
    "command": command,
    "cwd": str(BACKEND),
    "exit_code": completed.returncode,
    "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
    "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
    "junitxml": str(xml_path.name) if xml_path.exists() else None,
    "process_spawned": True,
}
(OUT / "focused-exit.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
