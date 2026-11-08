"""Parallel CI must preserve test coverage and never certify skipped/failed lanes."""
from collections import Counter
import itertools
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).parent / "fixtures/ci_backend_before_parallel.json"


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]


def test_every_existing_backend_command_environment_and_setup_is_preserved():
    jobs = workflow()
    before = json.loads(BASELINE.read_text())
    setup = before["setup_steps"]
    actual = []
    for name in ("backend-core", "backend-oracle"):
        lane = jobs[name]
        assert {k: v for k, v in lane.items() if k != "steps"} == before["job_properties"]
        assert lane["steps"][:len(setup)] == setup
        actual.extend(step for step in lane["steps"][len(setup):]
                      if step.get("name") != "Run backend lane preservation contract")
    canonical = lambda item: json.dumps(item, sort_keys=True)
    assert Counter(map(canonical, actual)) == Counter(map(canonical, before["test_steps"]))
    assert any(step.get("name") == "Run backend lane preservation contract"
               for step in jobs["backend-core"]["steps"])
    assert len(jobs["backend-oracle"]["steps"]) == len(setup) + 1


def test_required_backend_check_waits_for_both_lanes_even_on_failure():
    gate = workflow()["backend-tests"]
    assert gate.get("name", "backend-tests") == "backend-tests"
    assert gate["needs"] == ["backend-core", "backend-oracle"]
    assert gate["if"] == "${{ always() }}"
    assert not gate.get("continue-on-error", False)
    assert len(gate["steps"]) == 1
    assert not gate["steps"][0].get("continue-on-error", False)
    assert gate["steps"][0]["env"] == {
        "ATOM_CI_CORE_RESULT": "${{ needs.backend-core.result }}",
        "ATOM_CI_ORACLE_RESULT": "${{ needs.backend-oracle.result }}"}


@pytest.mark.parametrize("core,oracle", list(itertools.product(
    ["success", "failure", "cancelled", "skipped", ""], repeat=2)))
def test_real_gate_shell_requires_both_successes(core, oracle):
    command = workflow()["backend-tests"]["steps"][0]["run"]
    env = os.environ.copy()
    env.update(ATOM_CI_CORE_RESULT=core, ATOM_CI_ORACLE_RESULT=oracle)
    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", command],
                            env=env, capture_output=True, text=True)
    assert (result.returncode == 0) is (core == oracle == "success")
