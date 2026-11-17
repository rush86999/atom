"""Parallel CI must preserve coverage and never certify skipped/failed lanes.

The immutable pre-parallel baseline and additive ledgers stay the source of
truth.  ``ci_backend_layout_v2.json`` only models where those same step
dictionaries live now: every step is registered exactly once, each lane keeps
the relative order of its cohort, shared-DB lineages (S1/S2) stay in one lane,
and the required aggregate waits for every lane with ``always()``.
"""
from collections import Counter
import copy
import itertools
import json
import os
from pathlib import Path
import re
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).parent / "fixtures/ci_backend_before_parallel.json"
ADDITIONS = Path(__file__).parent / "fixtures/ci_backend_additions.json"
DOCKER_LANE = Path(__file__).parent / "fixtures/ci_backend_docker_lane.json"
CORE_EXTRA = Path(__file__).parent / "fixtures/ci_backend_core_extra.json"
LAYOUT = Path(__file__).parent / "fixtures/ci_backend_layout_v2.json"

PRESERVATION_STEP = "Run backend lane preservation contract"

# The four lanes of the original, already-landed split keep their 5^4 status
# matrix as the baseline control set (see the parametrization below).
SHARED_DB = "sqlite:///test_ci.db"
STATUSES = ["success", "failure", "cancelled", "skipped", ""]


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]


def _load(path):
    return json.loads(path.read_text())


def layout():
    return _load(LAYOUT)


def canonical(item):
    return json.dumps(item, sort_keys=True)


def _names(steps):
    return [step.get("name") for step in steps]


def _test_steps(jobs, lane):
    """A lane's steps after the shared three-step setup prefix."""
    return jobs[lane]["steps"][len(_load(BASELINE)["setup_steps"]):]


def _shared_db_steps(steps):
    return [
        step for step in steps
        if (step.get("env") or {}).get("DATABASE_URL") == SHARED_DB
    ]


def _db_lineage(step):
    """Classify a step from its own env declaration, not from intent."""
    database_url = (step.get("env") or {}).get("DATABASE_URL")
    if database_url == SHARED_DB:
        return "S1"
    if database_url is None:
        return "S2"
    if database_url == "sqlite:///:memory:" or "${{ runner.temp }}" in database_url:
        return "T"
    return "U"


def _lineage_owners(jobs):
    """Owners of the S1/S2 cohorts among the core/extra test lanes.

    ``sqlite:///test_ci.db`` is relative, so each job workspace has its own
    file; oracle/docker are separate runners and are not part of this cohort.
    """
    owners = {}
    for lane in layout()["lanes"]:
        if not lane.startswith("backend-core") or lane not in jobs:
            continue
        for step in _test_steps(jobs, lane):
            if step.get("name") == PRESERVATION_STEP:
                continue
            owners.setdefault(_db_lineage(step), set()).add(lane)
    return {lineage: sorted(lanes) for lineage, lanes in owners.items()}


def _is_subsequence(names, reference):
    remaining = iter(reference)
    return all(any(candidate == name for candidate in remaining) for name in names)


def _layout_violations(jobs):
    """Every static preservation/placement invariant, as a list of failures."""
    violations = []
    spec = layout()
    before = _load(BASELINE)
    additions = _load(ADDITIONS)
    docker_steps = _load(DOCKER_LANE)
    setup = before["setup_steps"]
    lanes = spec["lanes"]

    if spec.get("schema") != "atom.ci.backend_layout.v2":
        violations.append("unexpected layout schema")

    for lane in lanes:
        if lane not in jobs:
            violations.append(f"missing lane job: {lane}")
            continue
        job = jobs[lane]
        if {key: value for key, value in job.items() if key != "steps"} != before[
                "job_properties"]:
            violations.append(f"{lane}: job properties changed")
        if job["steps"][:len(setup)] != setup:
            violations.append(f"{lane}: setup prefix changed")
        actual = _names(_test_steps(jobs, lane))
        if actual != lanes[lane]:
            violations.append(f"{lane}: steps do not match the declared layout")

    if "backend-tests" not in jobs:
        return violations + ["missing backend-tests aggregate"]

    # Exactly-once registration of every ledger step plus the preservation
    # contract.  A dropped, duplicated, renamed or extra step fails here.
    all_steps = []
    for lane in lanes:
        if lane in jobs:
            all_steps.extend(_test_steps(jobs, lane))
    preservation = [step for step in all_steps
                    if step.get("name") == PRESERVATION_STEP]
    if len(preservation) != 1:
        violations.append(
            f"preservation step registered {len(preservation)} times")
    elif preservation[0] not in _test_steps(jobs, "backend-core"):
        violations.append("preservation step moved out of backend-core")

    expected_names = Counter(
        _names(before["test_steps"] + additions + docker_steps)
        + [PRESERVATION_STEP])
    if Counter(_names(all_steps)) != expected_names:
        violations.append("lane step names are not registered exactly once")

    # No ledger step may also appear in an undeclared job.  Without this, a
    # future author could add a new lane outside the layout (and outside
    # needs) while every declared lane still looks correct.
    ledger_names = set(expected_names)
    for label, job in jobs.items():
        if label in lanes or label == "backend-tests":
            continue
        for step in job.get("steps", []):
            if step.get("name") in ledger_names:
                violations.append(
                    f"{label}: contains a ledger step outside the declared lanes")
                break

    expected_steps = Counter(map(
        canonical, before["test_steps"] + additions + docker_steps))
    expected_steps.update(map(canonical, preservation))
    actual_steps = Counter(map(canonical, all_steps))
    if actual_steps != expected_steps:
        violations.append(
            "lane step dictionaries differ from the immutable ledgers")

    # Byte-exact unchanged lanes.
    for lane, expected in (
            ("backend-oracle", [step for step in before["test_steps"]
                                if step.get("name")
                                == "Run shared ORACLE registry verification controls"]),
            ("backend-docker", docker_steps)):
        if lane in jobs and Counter(map(canonical, _test_steps(jobs, lane))) != Counter(
                map(canonical, expected)):
            violations.append(f"{lane}: fixed lane content changed")

    # Relative order: each lane is a subsequence of the original lane order,
    # the union is exactly that order's membership, and the extra shards join
    # back into the already-declared extra-lane order.
    order_reference = spec["order_reference"]
    for lane in ("backend-core", "backend-core-isolated"):
        reference = order_reference["backend-core"]
        if not _is_subsequence(lanes[lane], reference):
            violations.append(f"{lane}: original core relative order changed")
    core_members = Counter(
        lanes["backend-core"] + lanes["backend-core-isolated"])
    if core_members != Counter(order_reference["backend-core"]):
        violations.append("core shards do not partition the original core order")

    extra_joined = lanes["backend-core-extra"] + lanes["backend-core-extra-isolated"]
    if extra_joined != order_reference["backend-core-extra"]:
        violations.append("extra shards do not preserve the declared extra order")
    if extra_joined != _load(CORE_EXTRA)["step_names"]:
        violations.append("extra shard concatenation changed the extra ledger")

    # Shared lineages: S1 and S2 may each have exactly one owner unless a
    # written split justification exists.  This is what stops a future author
    # from scattering test_ci.db / test_integration.db residue and calling it
    # parallelism.
    owners = _lineage_owners(jobs)
    for lineage, declared in spec["lineage_owners"].items():
        if owners.get(lineage, []) != sorted(declared):
            if not spec.get("split_justification"):
                violations.append(
                    f"{lineage} lineages moved to {owners.get(lineage, [])}")
    if not owners.get("S1") or not owners.get("S2"):
        violations.append("shared lineage classification found no S1/S2 steps")

    # Mini-app runtime boundary and its real-process restart stay adjacent in
    # whichever lane carries them.
    first_mini = "Run mini-app runtime-boundary journey (MINI-03 fail-closed joins)"
    second_mini = "Run real-process mini-app record restart control"
    for lane in lanes:
        names = lanes[lane]
        if first_mini in names and second_mini in names:
            if names.index(first_mini) + 1 != names.index(second_mini):
                violations.append(f"{lane}: mini-app restart adjacency broken")
        elif (first_mini in names) != (second_mini in names):
            violations.append(f"{lane}: mini-app pair split across lanes")

    # Required aggregate: one always() step over exactly every backend lane,
    # with one status env per lane and no soft failure path.
    gate = jobs["backend-tests"]
    expected_needs = list(lanes)
    if gate.get("needs") != expected_needs:
        violations.append("backend-tests needs the wrong lane set")
    if gate.get("if") != "${{ always() }}":
        violations.append("backend-tests is not always()")
    if gate.get("continue-on-error", False):
        violations.append("backend-tests continue-on-error is set")
    if len(gate.get("steps", [])) != 1:
        violations.append("backend-tests is not a single step")
    else:
        step = gate["steps"][0]
        if step.get("continue-on-error", False):
            violations.append("backend-tests step continue-on-error is set")
        expected_env = {
            var: "${{ needs.%s.result }}" % lane
            for lane, var in spec["lane_result_env"].items()}
        if step.get("env") != expected_env:
            violations.append("backend-tests status env is incomplete")
        run = step.get("run") or ""
        for variable in expected_env:
            if f'"${variable}"' not in run:
                violations.append(
                    f"backend-tests shell does not check {variable}")

    # No-softening guard for command steps (the Docker upload artifact step
    # legitimately carries if: always() and has no run).
    for lane in lanes:
        if lane not in jobs:
            continue
        for step in _test_steps(jobs, lane):
            run = step.get("run")
            if run is None:
                continue
            if "if" in step or step.get("continue-on-error", False):
                violations.append(f"{lane}: test step gained a conditional")
            for token in ("|| true", "|| echo", "--ignore", "--deselect",
                          "--maxfail"):
                if token in run:
                    violations.append(
                        f"{lane}: test step contains {token!r}")
            if re.search(r"pytest\b[^\n]*\s-(?:k|m)\s", run):
                violations.append(f"{lane}: test step gained a selection flag")

    return violations


def _gate_results(overrides=None):
    env = os.environ.copy()
    for lane, variable in layout()["lane_result_env"].items():
        env[variable] = "success"
    for lane, result in (overrides or {}).items():
        env[layout()["lane_result_env"][lane]] = result
    return env


def _run_gate(overrides=None):
    command = workflow()["backend-tests"]["steps"][0]["run"]
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", command],
        env=_gate_results(overrides), capture_output=True, text=True)


def test_every_existing_backend_command_environment_and_setup_is_preserved():
    jobs = workflow()
    before = _load(BASELINE)
    additions = _load(ADDITIONS)
    docker_steps = _load(DOCKER_LANE)
    setup = before["setup_steps"]
    spec = layout()

    for lane in spec["lanes"]:
        lane_job = jobs[lane]
        assert {key: value for key, value in lane_job.items()
                if key != "steps"} == before["job_properties"]
        assert lane_job["steps"][:len(setup)] == setup

    core_actual = [step for step in _test_steps(jobs, "backend-core")
                   if step.get("name") != PRESERVATION_STEP]
    isolated_actual = _test_steps(jobs, "backend-core-isolated")
    extra_actual = (_test_steps(jobs, "backend-core-extra")
                    + _test_steps(jobs, "backend-core-extra-isolated"))
    oracle_actual = _test_steps(jobs, "backend-oracle")
    docker_actual = _test_steps(jobs, "backend-docker")

    assert len(oracle_actual) == 1
    core_expected = list(before["test_steps"] + additions)
    assert oracle_actual[0] in core_expected
    core_expected.remove(oracle_actual[0])

    # The two core lanes together, the two extra lanes together, and the
    # untouched Docker rows preserve the exact ledgers including duplicates.
    assert Counter(map(canonical, core_actual + isolated_actual + extra_actual)) == Counter(
        map(canonical, core_expected))
    assert Counter(map(canonical, extra_actual)) == Counter(
        map(canonical, [step for step in core_expected
                        if step.get("name") in set(_load(CORE_EXTRA)["step_names"])]))
    assert Counter(map(canonical, docker_actual)) == Counter(
        map(canonical, docker_steps))
    assert Counter(map(
        canonical, core_actual + isolated_actual + extra_actual
        + oracle_actual + docker_actual
    )) == Counter(map(
        canonical, before["test_steps"] + additions + docker_steps))

    assert any(step.get("name") == PRESERVATION_STEP
               for step in jobs["backend-core"]["steps"])

    # Shared-resource cohort: test_ci.db stays in original backend-core; both
    # extra lanes may carry only isolated DB steps.
    assert _shared_db_steps(extra_actual) == []
    assert len(_shared_db_steps(core_actual)) >= 1
    names = _names(core_actual + isolated_actual)
    first_mini = "Run mini-app runtime-boundary journey (MINI-03 fail-closed joins)"
    second_mini = "Run real-process mini-app record restart control"
    if first_mini in names and second_mini in names:
        assert names.index(first_mini) + 1 == names.index(second_mini)

    assert _layout_violations(jobs) == []


def test_lineage_ownership_is_single_lane():
    owners = _lineage_owners(workflow())
    assert owners["S1"] == ["backend-core"]
    assert owners["S2"] == ["backend-core"]
    assert owners["T"] and owners["U"]


def test_partition_negative_controls():
    jobs = workflow()
    before = _load(BASELINE)
    additions = _load(ADDITIONS)
    setup = before["setup_steps"]
    core = [step for step in jobs["backend-core"]["steps"][len(setup):]
            if step.get("name") != PRESERVATION_STEP]
    isolated = jobs["backend-core-isolated"]["steps"][len(setup):]
    extra = (jobs["backend-core-extra"]["steps"][len(setup):]
             + jobs["backend-core-extra-isolated"]["steps"][len(setup):])
    expected = list(before["test_steps"] + additions)
    expected.remove(jobs["backend-oracle"]["steps"][len(setup):][0])

    def diff(left, right):
        actual = Counter(map(canonical, left + right))
        wanted = Counter(map(canonical, expected))
        return actual - wanted, wanted - actual

    assert diff(core + isolated, extra) == (Counter(), Counter())
    assert diff((core + isolated)[1:], extra) != (Counter(), Counter())
    assert diff(core + isolated, extra + [extra[0]]) != (
        Counter(), Counter())
    tampered = [dict(step) for step in extra]
    tampered[0] = {**tampered[0], "env": {**(tampered[0].get("env") or {}),
                                         "DATABASE_URL": "sqlite:///tampered.db"}}
    assert diff(core + isolated, tampered) != (Counter(), Counter())
    shared = [{"name": "moved shared", "env": {"DATABASE_URL": SHARED_DB}}]
    assert _shared_db_steps(shared) != []


def test_layout_negative_controls_reject_coverage_or_ownership_changes():
    base = workflow()
    assert _layout_violations(base) == []

    dropped = copy.deepcopy(base)
    dropped["backend-core-isolated"]["steps"].pop()
    assert _layout_violations(dropped)

    duplicated = copy.deepcopy(base)
    duplicated["backend-core-isolated"]["steps"].append(
        copy.deepcopy(duplicated["backend-core-isolated"]["steps"][-1]))
    assert _layout_violations(duplicated)

    mutated = copy.deepcopy(base)
    moved = mutated["backend-core-isolated"]["steps"][3]
    moved["env"] = {**(moved.get("env") or {}),
                    "DATABASE_URL": "sqlite:///tampered.db"}
    assert _layout_violations(mutated)

    split = copy.deepcopy(base)
    shared_step = next(
        step for step in split["backend-core"]["steps"][3:]
        if _db_lineage(step) == "S1"
        and step.get("name") != PRESERVATION_STEP)
    split["backend-core"]["steps"].remove(shared_step)
    split["backend-core-isolated"]["steps"].append(shared_step)
    assert _lineage_owners(split)["S1"] == ["backend-core", "backend-core-isolated"]
    assert _layout_violations(split)

    reordered = copy.deepcopy(base)
    steps = reordered["backend-core-extra"]["steps"]
    steps[3], steps[4] = steps[4], steps[3]
    assert _layout_violations(reordered)

    rogue = copy.deepcopy(base)
    rogue["backend-core-rogue"] = {
        "runs-on": "ubuntu-latest",
        "steps": [copy.deepcopy(rogue["backend-core-isolated"]["steps"][3])],
    }
    assert _layout_violations(rogue)


@pytest.mark.parametrize("lane", tuple(layout()["lanes"]))
def test_removing_any_dependency_fails(lane):
    jobs = copy.deepcopy(workflow())
    jobs["backend-tests"]["needs"].remove(lane)
    assert _layout_violations(jobs)


@pytest.mark.parametrize("lane", tuple(layout()["lanes"]))
def test_removing_any_status_env_fails(lane):
    jobs = copy.deepcopy(workflow())
    jobs["backend-tests"]["steps"][0]["env"].pop(
        layout()["lane_result_env"][lane])
    assert _layout_violations(jobs)


def test_required_backend_check_waits_for_all_lanes_even_on_failure():
    spec = layout()
    gate = workflow()["backend-tests"]
    assert gate.get("name", "backend-tests") == "backend-tests"
    assert gate["needs"] == list(spec["lanes"])
    assert gate["if"] == "${{ always() }}"
    assert not gate.get("continue-on-error", False)
    assert len(gate["steps"]) == 1
    assert not gate["steps"][0].get("continue-on-error", False)
    assert gate["steps"][0]["env"] == {
        variable: "${{ needs.%s.result }}" % lane
        for lane, variable in spec["lane_result_env"].items()}
    assert _run_gate().returncode == 0


# Baseline control set: the original four-lane 5^4 matrix, with the two new
# lanes held at success so it measures exactly the properties it always did.
@pytest.mark.parametrize("core,extra,oracle,docker", list(itertools.product(
    STATUSES, repeat=4)))
def test_real_gate_shell_requires_all_successes(core, extra, oracle, docker):
    result = _run_gate({
        "backend-core": core,
        "backend-core-extra": extra,
        "backend-oracle": oracle,
        "backend-docker": docker,
    })
    assert (result.returncode == 0) is (
        core == extra == oracle == docker == "success")


# Linear expansion for the new lanes: every lane x every non-success status,
# plus the explicit all-success case.  The gate is a monotone conjunction of
# per-lane equality checks, so a single deviation is exhaustive for "any
# non-success fails" without a 5^6 product.
@pytest.mark.parametrize("lane", tuple(layout()["lanes"]))
@pytest.mark.parametrize("status", STATUSES[1:])
def test_each_lane_non_success_blocks_the_aggregate(lane, status):
    assert _run_gate({lane: status}).returncode != 0


def test_all_success_is_the_only_admitted_combination():
    assert _run_gate({lane: "success"
                      for lane in layout()["lanes"]}).returncode == 0


@pytest.mark.parametrize("first,second", list(itertools.product(
    STATUSES, repeat=2)))
def test_new_lane_pair_product_subset(first, second):
    result = _run_gate({
        "backend-core-isolated": first,
        "backend-core-extra-isolated": second,
    })
    assert (result.returncode == 0) is (
        first == second == "success")
