"""Controlled evidence for the registered ``radio.send_message`` Oracle.

No live model, provider, server, browser, account, credential, install, spend,
send or deployment action is touched.  TESTING=1 plus explicit scratch
DATABASE_URL/data/Lance/output keep every import and test on a scratch world.
This candidate has no provider HTTP leaf; the real scratch SQLite store and
radio_service are used directly.

The failure-first capture temporarily restores the predecessor versions of the
three modified source files (HEAD^), removes the new producer module, runs the
new radio Oracle controls against them, then restores the committed source in
a finally block.
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

PREDECESSOR_FILES = [
    "backend/core/agent_radio/radio_actions.py",
    "backend/core/oracle/postcondition_verifiers.py",
    "backend/core/oracle/request_expectations.py",
]
NEW_FILES = [
    "backend/core/agent_radio/radio_mutations.py",
]
TEST = BACKEND / "tests" / "test_oracle_radio_send.py"

FOCUSED_NODES = [
    "tests/test_oracle_radio_send.py",
    "tests/unit/agents/test_radio_actions.py",
    "tests/test_covpush_w80a_radio.py",
    "tests/unit/agents/test_agent_radio_tool.py",
    "tests/test_oracle_registry_verification_gap.py",
    "tests/test_generic_oracle_mutation_contract.py",
    "tests/test_oracle_connected_mutations.py",
    "tests/test_oracle_effect_families.py",
]

ROOT_REFERENCE_COMMITS = {
    "decimal_context_fix": "e359b5ac7",
    "prerequisite_tests": ["4e0ead635", "00979657d"],
    "note": "not modified by this candidate; no Decimal/number helper changed",
}

env = dict(os.environ)
env.update({
    "TESTING": "1",
    "ENVIRONMENT": "test",
    "SECRET_KEY": "synthetic-radio-send-evidence-key-not-a-secret",
    "DATABASE_URL": f"sqlite:///{SCRATCH / 'atom.db'}",
    "ATOM_DATA_DIR": str(SCRATCH / "data"),
    "LANCEDB_URI": str(SCRATCH / "lancedb"),
    "LANCEDB_URI_BASE": str(SCRATCH / "lancedb"),
    "ATOM_OUTPUT_DIR": str(SCRATCH / "output"),
    "ATOM_RADIO_ENABLED": "true",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONPATH": str(BACKEND),
})
for key in (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_SHOP_NAME",
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
        "process_spawned": True,
    }
    (OUT / f"{name}-exit.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _failure_first():
    committed = {
        relative: (ROOT / relative).read_bytes()
        for relative in PREDECESSOR_FILES + NEW_FILES
    }
    predecessor = {
        relative: subprocess.check_output(
            ["git", "show", f"HEAD^:{relative}"], cwd=ROOT)
        for relative in PREDECESSOR_FILES
    }
    try:
        for relative, data in predecessor.items():
            (ROOT / relative).write_bytes(data)
        for relative in NEW_FILES:
            (ROOT / relative).unlink(missing_ok=True)
        result = _run(
            "failure-first", ["tests/test_oracle_radio_send.py"])
    finally:
        for relative, data in committed.items():
            (ROOT / relative).write_bytes(data)
            assert _sha256(ROOT / relative) == hashlib.sha256(data).hexdigest()
    return result


def main():
    failure_first = _failure_first()
    focused = _run("focused", FOCUSED_NODES)
    verification = {
        "task": "registered radio.send_message exact-row/material Oracle",
        "git_branch": subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT, text=True).strip(),
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "base": "origin/main e8187a0c2",
        "root_reference_commits": ROOT_REFERENCE_COMMITS,
        "contract": {
            "registry": (
                "core/agent_radio/radio_actions.py::radio_send_message"),
            "service": (
                "core/agent_radio/radio_service.py::send_message"),
            "read_primitive": (
                "radio.read_inbox / get_thread_snapshot; exact "
                "LateralMessage.id row + AgentThread scope"),
            "protocol": "docs/architecture/AGENT_RADIO.md section Protocol",
            "http_leaf": (
                "none; local durable DB candidate. No provider HTTP is "
                "claimed or doubled."),
        },
        "implementation_files": {
            relative: _sha256(ROOT / relative)
            for relative in PREDECESSOR_FILES + NEW_FILES
        },
        "test": {
            "path": str(TEST.relative_to(ROOT)),
            "sha256": _sha256(TEST),
        },
        "runs": {
            "failure_first": failure_first,
            "focused": focused,
        },
        "environment": {
            "TESTING": "1",
            "DATABASE_URL": env["DATABASE_URL"],
            "ATOM_DATA_DIR": env["ATOM_DATA_DIR"],
            "LANCEDB_URI": env["LANCEDB_URI"],
            "ATOM_OUTPUT_DIR": env["ATOM_OUTPUT_DIR"],
            "ATOM_RADIO_ENABLED": env["ATOM_RADIO_ENABLED"],
            "provider_credentials": "blank",
            "interpreter": sys.executable,
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
