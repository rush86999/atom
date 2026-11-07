"""Exact evidence for the radio readback-identity repair.

No live server/model/provider/account/credential/send/spend/install is touched.
TESTING=1 plus explicit scratch DATABASE_URL/data/Lance/output keep every import
and test on a scratch world.  This local candidate has no provider HTTP leaf.

Failure-first restores the pre-repair radio_mutations.py from root's permanent
test checkpoint 9aba74234 (before the narrow fix), runs root's supplied control
plus the new known-id/replay controls, then restores the committed source.
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

SOURCE = BACKEND / "core" / "agent_radio" / "radio_mutations.py"
PRE_FIX_REVISION = "9aba74234"

FAILURE_FIRST_NODES = [
    "tests/test_lead_radio_readback_identity.py",
    "tests/test_oracle_radio_send.py::"
    "test_known_committed_id_survives_readback_failure",
    "tests/test_oracle_radio_send.py::"
    "test_replay_after_readback_failure_does_not_resend",
]

FOCUSED_NODES = [
    "tests/test_lead_radio_readback_identity.py",
    "tests/test_oracle_radio_send.py",
    "tests/unit/agents/test_radio_actions.py",
    "tests/test_covpush_w80a_radio.py",
    "tests/unit/agents/test_agent_radio_tool.py",
    "tests/test_oracle_registry_verification_gap.py",
    "tests/test_generic_oracle_mutation_contract.py",
    "tests/test_oracle_connected_mutations.py",
    "tests/test_oracle_effect_families.py",
    "tests/test_information_wait_maturity_neutral.py",
]

env = dict(os.environ)
env.update({
    "TESTING": "1",
    "ENVIRONMENT": "test",
    "SECRET_KEY": "synthetic-radio-readback-repair-key-not-a-secret",
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
    committed = SOURCE.read_bytes()
    predecessor = subprocess.check_output(
        ["git", "show", f"{PRE_FIX_REVISION}:{SOURCE.relative_to(ROOT)}"],
        cwd=ROOT)
    assert predecessor != committed
    try:
        SOURCE.write_bytes(predecessor)
        result = _run("failure-first", FAILURE_FIRST_NODES)
    finally:
        SOURCE.write_bytes(committed)
        assert _sha256(SOURCE) == hashlib.sha256(committed).hexdigest()
    return result


def main():
    failure_first = _failure_first()
    focused = _run("focused", FOCUSED_NODES)
    verification = {
        "task": "radio.send_message known committed identity across readback failure",
        "git_branch": subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT, text=True).strip(),
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "parents": subprocess.check_output(
            ["git", "rev-list", "--parents", "-n", "1", "HEAD"],
            cwd=ROOT, text=True).strip().split()[1:],
        "base_origin_main": "e39e2af2f",
        "root_permanent_test_commit": PRE_FIX_REVISION,
        "root_negative_log": (
            "/private/tmp/root-radio-known-id-negative.log"),
        "root_negative_exit": (
            "/private/tmp/root-radio-known-id-negative-exit.json"),
        "contract": {
            "registry": (
                "core/agent_radio/radio_actions.py::radio_send_message"),
            "service": (
                "core/agent_radio/radio_service.py::send_message"),
            "read_primitive": (
                "radio.read_inbox / get_thread_snapshot; exact "
                "LateralMessage.id row + AgentThread membership"),
            "protocol": "docs/architecture/AGENT_RADIO.md section Protocol",
            "http_leaf": (
                "none; local durable DB candidate. No provider HTTP claimed."),
            "tenant_boundary": (
                "post-effect tenant mismatch only marks the receipt "
                "unverified; it is not a pre-effect tenant authorization "
                "gate. Current single-tenant contract is open-thread plus "
                "thread membership in radio_service.send_message."),
        },
        "implementation": {
            str(SOURCE.relative_to(ROOT)): _sha256(SOURCE),
        },
        "tests": {
            "root_supplied": (
                "backend/tests/test_lead_radio_readback_identity.py"),
            "oracle": "backend/tests/test_oracle_radio_send.py",
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
