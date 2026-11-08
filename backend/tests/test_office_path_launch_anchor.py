"""Office storage and access must not fork when app launch CWD changes."""
from pathlib import Path

import pytest

from core.office_service import _validate_office_path


@pytest.mark.parametrize("configured", [False, True], ids=["default", "relative-config"])
def test_relative_office_path_is_stable_across_launch_directories(
        tmp_path, monkeypatch, configured):
    for name in ("ATOM_OFFICE_DIR", "ATOM_ASSIGNMENT_OUTPUT_DIR"):
        monkeypatch.delenv(name, raising=False)
    if configured:
        monkeypatch.setenv("ATOM_OFFICE_DIR", "data/office")
        monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", "data/office/assignments")
    paths = []
    for name in ("root-launch", "backend-launch"):
        launch = tmp_path / name
        launch.mkdir()
        monkeypatch.chdir(launch)
        paths.append(_validate_office_path("data/office/report.docx"))
    assert paths[0] == paths[1], "a launch-directory change forked the office namespace"
    assert Path(paths[0]).is_absolute()


def test_absolute_office_root_is_preserved_and_escape_refused(tmp_path, monkeypatch):
    owned = tmp_path / "owned-office"
    owned.mkdir()
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(owned))
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", str(owned / "assignments"))
    document = owned / "report.docx"
    assert _validate_office_path(str(document)) == str(document)
    with pytest.raises(ValueError, match="outside"):
        _validate_office_path(str(tmp_path / "foreign.docx"))
    outside = tmp_path / "outside"
    outside.mkdir()
    (owned / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="outside"):
        _validate_office_path(str(owned / "escape" / "report.docx"))


from tests.test_assignment_routes import route_env  # noqa: E402,F401


@pytest.mark.parametrize("target,expected", [("owned", 200), ("outside", 403), ("foreign", 404)])
def test_allocated_artifact_and_download_use_same_owned_root(
        route_env, tmp_path, monkeypatch, target, expected):
    from core.assignment_plan import new_assignment, new_step
    from core.assignment_resources import allocate_output_path

    office = tmp_path / "configured-office"
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(office))
    monkeypatch.delenv("ATOM_ASSIGNMENT_OUTPUT_DIR", raising=False)
    path = Path(allocate_output_path(
        route_env["current"]["user"], kind="document", title="Owned report",
        assignment_id="path-contract-assignment"))
    contents = b"owned artifact transport control"
    path.write_bytes(contents)
    if target == "outside":
        path = tmp_path / "foreign-artifact.docx"
        path.write_bytes(b"not authorized by the configured artifact root")
    plan = new_assignment(
        objective="Download an owned artifact", workspace_id="ws-1", tenant_id="tenant-1",
        steps=[new_step(step_id="calculate", title="Pending calculation",
                        operation_type="calculate", adapter="formula.calculate",
                        inputs={"expression": "1+1"})],
        deliverables=[{"deliverable_id": "result-1", "kind": "document", "artifact_path": str(path)}])
    record = route_env["executor"].create_assignment(
        "path-contract-conversation", "Download an owned artifact", assignment=plan)
    if target == "foreign":
        route_env["current"]["user"] = route_env["users"]["other"]
    response = route_env["client"].get(
        f"/api/assignments/{record['run_id']}/deliverables/result-1/download")
    assert response.status_code == expected, response.text
    if expected == 200:
        assert response.content == contents


def test_blank_storage_roots_do_not_authorize_the_launch_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_OFFICE_DIR", "")
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", "")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        _validate_office_path(str(tmp_path / "unowned.docx"))


def test_relative_artifact_allocation_keeps_one_owned_directory(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from core.assignment_resources import allocate_output_path
    import core.local_paths as paths

    backend = tmp_path / "backend-root"
    backend.mkdir()
    monkeypatch.setattr(paths, "_BACKEND_ROOT", backend)
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", "data/office/assignments")
    user = SimpleNamespace(id="owner-exact", workspace_id="workspace-exact")
    allocated = []
    for name in ("launch-one", "launch-two"):
        launch = tmp_path / name
        launch.mkdir()
        monkeypatch.chdir(launch)
        allocated.append(Path(allocate_output_path(
            user, kind="document", title="Report", assignment_id="assignment-exact")))
    expected = backend / "data/office/assignments/workspace-exact/owner-exact/assignment-exact"
    assert allocated[0].parent == allocated[1].parent == expected
    assert allocated[0] != allocated[1], "separate artifact requests retain distinct names"
