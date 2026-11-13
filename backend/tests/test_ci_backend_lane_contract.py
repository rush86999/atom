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
ADDITIONS = Path(__file__).parent / "fixtures/ci_backend_additions.json"
DOCKER_LANE = Path(__file__).parent / "fixtures/ci_backend_docker_lane.json"

PRESERVATION_STEP = "Run backend lane preservation contract"
BACKEND_LANES = ("backend-core", "backend-oracle", "backend-docker")


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]


def test_every_existing_backend_command_environment_and_setup_is_preserved():
    jobs = workflow()
    before = json.loads(BASELINE.read_text())
    additions = json.loads(ADDITIONS.read_text())
    docker_steps = json.loads(DOCKER_LANE.read_text())
    setup = before["setup_steps"]
    for name in BACKEND_LANES:
        lane = jobs[name]
        # Every backend lane must use the same job shape and setup as the
        # pre-parallel job; a lane that quietly diverges is a coverage risk.
        assert {k: v for k, v in lane.items() if k != "steps"} == before["job_properties"]
        assert lane["steps"][:len(setup)] == setup

    canonical = lambda item: json.dumps(item, sort_keys=True)
    core_actual = [step for step in jobs["backend-core"]["steps"][len(setup):]
                   if step.get("name") != PRESERVATION_STEP]
    oracle_actual = jobs["backend-oracle"]["steps"][len(setup):]
    docker_actual = jobs["backend-docker"]["steps"][len(setup):]

    # The ORACLE block moved intact to its own lane; everything else must
    # remain in backend-core.
    assert len(oracle_actual) == 1
    core_expected = list(before["test_steps"] + additions)
    assert oracle_actual[0] in core_expected
    core_expected.remove(oracle_actual[0])

    # The original pre-parallel ledger stays immutable. New core gates must be
    # declared exactly once in the additive ledger, preserving every original
    # command, environment and setup rather than relaxing to a subset check.
    assert Counter(map(canonical, core_actual)) == Counter(
        map(canonical, core_expected))
    # The full-service real-Docker receipt gate is relocated to its own hosted
    # lane, not dropped: that lane runs exactly those declared steps.
    assert Counter(map(canonical, docker_actual)) == Counter(
        map(canonical, docker_steps))
    # Nothing is duplicated, dropped, or moved into an undeclared lane.
    assert Counter(map(canonical,
                       core_actual + oracle_actual + docker_actual)) == Counter(
        map(canonical, before["test_steps"] + additions + docker_steps))

    assert any(step.get("name") == PRESERVATION_STEP
               for step in jobs["backend-core"]["steps"])


def test_required_backend_check_waits_for_all_lanes_even_on_failure():
    gate = workflow()["backend-tests"]
    assert gate.get("name", "backend-tests") == "backend-tests"
    assert gate["needs"] == list(BACKEND_LANES)
    assert gate["if"] == "${{ always() }}"
    assert not gate.get("continue-on-error", False)
    assert len(gate["steps"]) == 1
    assert not gate["steps"][0].get("continue-on-error", False)
    assert gate["steps"][0]["env"] == {
        "ATOM_CI_CORE_RESULT": "${{ needs.backend-core.result }}",
        "ATOM_CI_ORACLE_RESULT": "${{ needs.backend-oracle.result }}",
        "ATOM_CI_DOCKER_RESULT": "${{ needs.backend-docker.result }}"}


@pytest.mark.parametrize("core,oracle,docker", list(itertools.product(
    ["success", "failure", "cancelled", "skipped", ""], repeat=3)))
def test_real_gate_shell_requires_all_successes(core, oracle, docker):
    command = workflow()["backend-tests"]["steps"][0]["run"]
    env = os.environ.copy()
    env.update(ATOM_CI_CORE_RESULT=core, ATOM_CI_ORACLE_RESULT=oracle,
               ATOM_CI_DOCKER_RESULT=docker)
    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", command],
                            env=env, capture_output=True, text=True)
    assert (result.returncode == 0) is (core == oracle == docker == "success")
