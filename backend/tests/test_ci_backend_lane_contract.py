"""Parallel CI must preserve coverage and never certify skipped/failed lanes."""
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
CORE_EXTRA = Path(__file__).parent / "fixtures/ci_backend_core_extra.json"

PRESERVATION_STEP = "Run backend lane preservation contract"
BACKEND_LANES = (
    "backend-core", "backend-core-extra", "backend-oracle", "backend-docker")
SHARED_DB = "sqlite:///test_ci.db"


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]


def canonical(item):
    return json.dumps(item, sort_keys=True)


def _shared_db_steps(steps):
    return [
        step for step in steps
        if (step.get("env") or {}).get("DATABASE_URL") in (None, SHARED_DB)
        or (step.get("env") or {}).get("DATABASE_URL") == SHARED_DB
    ]


def _partition_diff(core_steps, extra_steps, expected):
    actual = Counter(map(canonical, core_steps + extra_steps))
    wanted = Counter(map(canonical, expected))
    return actual - wanted, wanted - actual


def test_every_existing_backend_command_environment_and_setup_is_preserved():
    jobs = workflow()
    before = json.loads(BASELINE.read_text())
    additions = json.loads(ADDITIONS.read_text())
    docker_steps = json.loads(DOCKER_LANE.read_text())
    extra_names = json.loads(CORE_EXTRA.read_text())["step_names"]
    setup = before["setup_steps"]

    for name in BACKEND_LANES:
        lane = jobs[name]
        assert {k: v for k, v in lane.items() if k != "steps"} == before["job_properties"]
        assert lane["steps"][:len(setup)] == setup

    core_actual = [step for step in jobs["backend-core"]["steps"][len(setup):]
                   if step.get("name") != PRESERVATION_STEP]
    extra_actual = jobs["backend-core-extra"]["steps"][len(setup):]
    oracle_actual = jobs["backend-oracle"]["steps"][len(setup):]
    docker_actual = jobs["backend-docker"]["steps"][len(setup):]

    assert len(oracle_actual) == 1
    core_expected = list(before["test_steps"] + additions)
    assert oracle_actual[0] in core_expected
    core_expected.remove(oracle_actual[0])

    # Two explicit core lanes together preserve the exact pre-parallel +
    # additive ledger (order is per-lane; every command/env/duplicate once).
    assert _partition_diff(core_actual, extra_actual, core_expected) == (
        Counter(), Counter())
    assert Counter(map(canonical, extra_actual)) == Counter(
        map(canonical, [s for s in core_expected
                        if s.get("name") in set(extra_names)]))
    assert [s.get("name") for s in extra_actual] == extra_names
    assert Counter(map(canonical, docker_actual)) == Counter(
        map(canonical, docker_steps))
    assert Counter(map(
        canonical, core_actual + extra_actual + oracle_actual + docker_actual
    )) == Counter(map(
        canonical, before["test_steps"] + additions + docker_steps))

    assert any(step.get("name") == PRESERVATION_STEP
               for step in jobs["backend-core"]["steps"])

    # Shared-resource cohort: test_ci.db and no-explicit-DB steps stay in the
    # original backend-core; the extra lane may carry only isolated DB steps.
    assert _shared_db_steps(extra_actual) == []
    assert len(_shared_db_steps(core_actual)) >= 1
    names = [s.get("name") for s in core_actual]
    first_mini = "Run mini-app runtime-boundary journey (MINI-03 fail-closed joins)"
    second_mini = "Run real-process mini-app record restart control"
    if first_mini in names and second_mini in names:
        assert names.index(first_mini) + 1 == names.index(second_mini)


def test_partition_negative_controls():
    jobs = workflow()
    before = json.loads(BASELINE.read_text())
    additions = json.loads(ADDITIONS.read_text())
    setup = before["setup_steps"]
    core = [s for s in jobs["backend-core"]["steps"][len(setup):]
            if s.get("name") != PRESERVATION_STEP]
    extra = jobs["backend-core-extra"]["steps"][len(setup):]
    expected = list(before["test_steps"] + additions)
    expected.remove(jobs["backend-oracle"]["steps"][len(setup):][0])

    assert _partition_diff(core, extra, expected) == (Counter(), Counter())
    assert _partition_diff(core[1:], extra, expected) != (Counter(), Counter())
    assert _partition_diff(core, extra + [extra[0]], expected) != (
        Counter(), Counter())
    tampered = [dict(s) for s in extra]
    tampered[0] = {**tampered[0], "env": {**(tampered[0].get("env") or {}),
                                         "DATABASE_URL": "sqlite:///tampered.db"}}
    assert _partition_diff(core, tampered, expected) != (Counter(), Counter())
    shared = [{"name": "moved shared", "env": {"DATABASE_URL": SHARED_DB}}]
    assert _shared_db_steps(shared) != []


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
        "ATOM_CI_CORE_EXTRA_RESULT": "${{ needs.backend-core-extra.result }}",
        "ATOM_CI_ORACLE_RESULT": "${{ needs.backend-oracle.result }}",
        "ATOM_CI_DOCKER_RESULT": "${{ needs.backend-docker.result }}",
    }


@pytest.mark.parametrize("core,extra,oracle,docker", list(itertools.product(
    ["success", "failure", "cancelled", "skipped", ""], repeat=4)))
def test_real_gate_shell_requires_all_successes(core, extra, oracle, docker):
    command = workflow()["backend-tests"]["steps"][0]["run"]
    env = os.environ.copy()
    env.update(
        ATOM_CI_CORE_RESULT=core, ATOM_CI_CORE_EXTRA_RESULT=extra,
        ATOM_CI_ORACLE_RESULT=oracle, ATOM_CI_DOCKER_RESULT=docker)
    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", command],
                            env=env, capture_output=True, text=True)
    assert (result.returncode == 0) is (
        core == extra == oracle == docker == "success")
