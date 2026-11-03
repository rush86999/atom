"""Campaign harness must never delete an arbitrary --world directory."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from core.assignment_launcher_guard import (
    MARKER_NAME, UnsafeScratchError,
)

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts/acceptance/employee_g5_normal_campaign.py"
)


def _module(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "employee_g5_campaign_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DEFAULT_WORLD_ROOT", tmp_path / "worlds")
    return module


def test_default_world_is_fresh_and_marked(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    first = module._prepare_world("", reset_world=False)
    second = module._prepare_world("", reset_world=False)
    assert first != second
    assert (first / MARKER_NAME).exists()
    assert (second / MARKER_NAME).exists()


def test_existing_unmarked_world_is_refused_and_preserved(
        tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    sentinel = tmp_path / "sentinel-world"
    sentinel.mkdir()
    keep = sentinel / "must-survive.txt"
    keep.write_text("do not delete")
    with pytest.raises(UnsafeScratchError, match="unmarked"):
        module._prepare_world(str(sentinel), reset_world=True)
    assert keep.read_text() == "do not delete"


def test_marked_world_requires_explicit_reset(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    sentinel = tmp_path / "marked-world"
    sentinel.mkdir()
    (sentinel / MARKER_NAME).write_text("owned")
    keep = sentinel / "must-survive.txt"
    keep.write_text("do not delete")
    with pytest.raises(UnsafeScratchError, match="reset-world"):
        module._prepare_world(str(sentinel), reset_world=False)
    assert keep.read_text() == "do not delete"


def test_marked_world_resets_only_with_explicit_flag(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    sentinel = tmp_path / "marked-reset-world"
    sentinel.mkdir()
    (sentinel / MARKER_NAME).write_text("owned")
    (sentinel / "old.txt").write_text("old")
    module._prepare_world(str(sentinel), reset_world=True)
    assert not (sentinel / "old.txt").exists()
    assert (sentinel / MARKER_NAME).exists()


def test_protected_source_path_is_refused(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    with pytest.raises(UnsafeScratchError):
        module._prepare_world(
            "/private/tmp/atom-full-app/docs/acceptance", reset_world=True)
