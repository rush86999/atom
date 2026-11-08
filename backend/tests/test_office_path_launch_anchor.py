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
