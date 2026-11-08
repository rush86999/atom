"""The published interpreter range must use real setup/boot, never guard doubles."""
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def jobs():
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]


def test_real_matrix_has_every_supported_version_and_no_optional_failure():
    job = jobs()["quickstart-install"]
    assert job["strategy"] == {
        "fail-fast": False, "matrix": {"python": ["3.11", "3.12", "3.13"]}}
    assert not job.get("continue-on-error", False)
    assert not job.get("if")
    assert job["timeout-minutes"] == 20
    assert job["name"] == "quickstart-install (${{ matrix.python }})"
    for step in job["steps"]:
        assert not step.get("continue-on-error", False)
        assert not step.get("if")


def test_original_real_install_artifact_and_boot_commands_are_preserved():
    before = json.loads((Path(__file__).parent / "fixtures/quickstart_before_supported_matrix.json").read_text())
    current = jobs()["quickstart-install"]
    assert current["runs-on"] == before["runs-on"]
    steps = []
    for step in current["steps"]:
        if step.get("name") in {"Verify fresh installation directories", "Verify storage binary compatibility"}:
            continue
        step = json.loads(json.dumps(step))
        if step.get("uses") == "actions/setup-python@v5":
            assert step["with"]["python-version"] == "${{ matrix.python }}"
            step["with"]["python-version"] = "3.11"
        steps.append(step)
    assert steps == before["steps"]
    assert any(step.get("run") == "make setup" for step in steps)
    assert not any("--check-python" in step.get("run", "") for step in steps)


def test_fresh_checkout_is_checked_before_dependency_installation():
    steps = jobs()["quickstart-install"]["steps"]
    fresh = next(i for i, step in enumerate(steps) if step.get("name") == "Verify fresh installation directories")
    install = next(i for i, step in enumerate(steps) if step.get("run") == "make setup")
    assert fresh < install
    assert steps[fresh]["run"] == "test ! -e backend/venv\ntest ! -e frontend-nextjs/node_modules\n"


def test_required_quickstart_waits_for_matrix_even_on_failure():
    gate = jobs()["quickstart"]
    assert gate["needs"] == ["quickstart-install"]
    assert gate["if"] == "${{ always() }}"
    assert not gate.get("continue-on-error", False)
    assert len(gate["steps"]) == 1
    assert gate["steps"][0]["env"] == {
        "ATOM_CI_QUICKSTART_RESULT": "${{ needs.quickstart-install.result }}"}


@pytest.mark.parametrize("result", ["success", "failure", "cancelled", "skipped", ""])
def test_actual_gate_shell_refuses_non_success_matrix(result):
    step = jobs()["quickstart"]["steps"][0]
    env = os.environ.copy()
    env["ATOM_CI_QUICKSTART_RESULT"] = result
    completed = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step["run"]],
                               env=env, capture_output=True, text=True, timeout=5)
    assert (completed.returncode == 0) is (result == "success")


def test_matrix_contract_is_part_of_required_backend_lane():
    steps = jobs()["backend-core"]["steps"]
    preservation = next(step for step in steps if step.get("name") == "Run backend lane preservation contract")
    assert "tests/test_ci_backend_lane_contract.py tests/test_quickstart_matrix_contract.py" in preservation["run"]


@pytest.mark.parametrize("python_version,accepted,rejected", [
    ("3.11", "1.26.4", "2.1.0"),
    ("3.12", "1.26.4", "2.1.0"),
    ("3.13", "2.1.0", "1.26.4"),
])
def test_numpy_abi_constraint_follows_supported_interpreter(python_version, accepted, rejected):
    from packaging.requirements import Requirement
    entries = [Requirement(line) for line in (ROOT / "backend/requirements.txt").read_text().splitlines()
               if line.startswith("numpy>=")]
    chosen = [entry for entry in entries
              if entry.marker is None or entry.marker.evaluate({"python_version": python_version})]
    assert len(chosen) == 1
    assert accepted in chosen[0].specifier
    assert rejected not in chosen[0].specifier
    assert "3.0.0" not in chosen[0].specifier


def test_actual_storage_smoke_runs_after_setup_and_before_boot():
    steps = jobs()["quickstart-install"]["steps"]
    names = [step.get("name") for step in steps]
    smoke = names.index("Verify storage binary compatibility")
    assert names.index("Run make setup (quickstart.sh)") < smoke
    assert smoke < names.index("Boot the full app from the generated env")
    assert steps[smoke]["run"] == "backend/venv/bin/python scripts/ci/verify_quickstart_storage.py"
    assert steps[smoke]["env"] == {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
