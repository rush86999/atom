"""The acceptance launcher must never delete an arbitrary env path."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.assignment_launcher_guard import (
    MARKER_NAME,
    UnsafeScratchError,
    prepare_scratch_dir,
    validate_scratch_dir,
)


def test_refuses_live_backend_data_path():
    with pytest.raises(UnsafeScratchError):
        validate_scratch_dir("/Users/example/projects/atom/backend/data")


def test_refuses_docs_and_frontend_paths():
    with pytest.raises(UnsafeScratchError):
        validate_scratch_dir("/tmp/project/docs/acceptance/world")
    with pytest.raises(UnsafeScratchError):
        validate_scratch_dir("/tmp/project/frontend-nextjs/world")


def test_refuses_paths_outside_approved_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_ASSIGNMENT_SCRATCH_ROOT", str(tmp_path))
    outside = Path("/Users/example/scratch/not-approved")
    with pytest.raises(UnsafeScratchError):
        validate_scratch_dir(outside)


def test_existing_non_empty_dir_requires_marker(tmp_path):
    world = tmp_path / "world"
    world.mkdir()
    (world / "keep.txt").write_text("do not delete")
    with pytest.raises(UnsafeScratchError):
        prepare_scratch_dir(world, reset=True)
    assert (world / "keep.txt").exists()


def test_reset_deletes_only_marked_world(tmp_path):
    world = prepare_scratch_dir(tmp_path / "world")
    (world / "old.txt").write_text("old")
    reset = prepare_scratch_dir(world, reset=True)
    assert reset == world
    assert (world / MARKER_NAME).exists()
    assert not (world / "old.txt").exists()


def test_launcher_has_no_unconditional_rmtree():
    source = (Path(__file__).resolve().parents[1] / "scripts" /
              "assignment_browser_acceptance_server.py").read_text()
    assert "rmtree(SCRATCH" not in source
    assert "prepare_scratch_dir" in source
