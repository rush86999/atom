"""Failure-first controls for BPEWorkspaceStore write truthfulness.

These controls inject failures only at the storage seams exercised by the
real store (``os.replace`` / ``json.dump`` / ``tempfile.mkstemp`` /
``os.fdopen``) and assert the public ``save``/``load`` contract. Root owns
execution; nothing here is asserted as passing by the author.
"""
from __future__ import annotations

import os

import pytest

import core.bpe.persistence as persistence
from core.bpe.persistence import BPEWorkspaceStore
from core.bpe.workspace import BPEWorkspace, Subgoal


pytestmark = pytest.mark.unit


def _snapshot(title: str = "replacement") -> dict:
    workspace = BPEWorkspace("w", "a", "s")
    workspace.progress.append(Subgoal(title))
    workspace.experience.add("skills", f"{title} procedure")
    return workspace.to_dict()


def _seed(store: BPEWorkspaceStore) -> tuple:
    """Persist a known snapshot and return its path plus raw bytes."""
    assert store.save(_snapshot("original")) is True
    path = store._path_for("w")
    return path, path.read_bytes()


def _assert_no_temp_files(directory) -> None:
    assert list(directory.glob("*.tmp")) == []


class TestBPEPersistenceWriteTruth:
    def test_replace_failure_returns_false_and_preserves_previous_file(
        self, tmp_path, monkeypatch
    ):
        store = BPEWorkspaceStore(data_dir=tmp_path)
        path, original = _seed(store)

        def fail_replace(src, dst):
            raise OSError("replacement failed")

        monkeypatch.setattr(persistence.os, "replace", fail_replace)

        assert store.save(_snapshot("replacement")) is False
        assert path.read_bytes() == original
        assert store.load("w", "a", "s")["progress"][0]["title"] == "original"
        _assert_no_temp_files(tmp_path)

    def test_json_dump_failure_returns_false_and_preserves_previous_file(
        self, tmp_path, monkeypatch
    ):
        store = BPEWorkspaceStore(data_dir=tmp_path)
        path, original = _seed(store)

        def fail_dump(value, stream, *args, **kwargs):
            raise OSError("write failed")

        monkeypatch.setattr(persistence.json, "dump", fail_dump)

        assert store.save(_snapshot("replacement")) is False
        assert path.read_bytes() == original
        assert store.load("w", "a", "s")["progress"][0]["title"] == "original"
        _assert_no_temp_files(tmp_path)

    def test_mkstemp_failure_returns_false_and_preserves_previous_file(
        self, tmp_path, monkeypatch
    ):
        store = BPEWorkspaceStore(data_dir=tmp_path)
        path, original = _seed(store)

        def fail_mkstemp(*args, **kwargs):
            raise OSError("temp creation failed")

        monkeypatch.setattr(persistence.tempfile, "mkstemp", fail_mkstemp)

        assert store.save(_snapshot("replacement")) is False
        assert path.read_bytes() == original
        _assert_no_temp_files(tmp_path)

    def test_mkdir_failure_returns_false_without_creating_temp(self, tmp_path):
        blocker = tmp_path / "blocked"
        blocker.write_text("not a directory", encoding="utf-8")
        store = BPEWorkspaceStore(data_dir=blocker)

        assert store.save(_snapshot("replacement")) is False
        assert blocker.read_text(encoding="utf-8") == "not a directory"
        _assert_no_temp_files(tmp_path)

    def test_fdopen_failure_closes_fd_and_removes_temp_file(
        self, tmp_path, monkeypatch
    ):
        store = BPEWorkspaceStore(data_dir=tmp_path)
        path, original = _seed(store)
        captured = {}

        def fail_fdopen(fd, *args, **kwargs):
            captured["fd"] = fd
            raise OSError("fdopen failed")

        monkeypatch.setattr(persistence.os, "fdopen", fail_fdopen)

        assert store.save(_snapshot("replacement")) is False
        with pytest.raises(OSError):
            os.fstat(captured["fd"])
        assert path.read_bytes() == original
        _assert_no_temp_files(tmp_path)

    def test_valid_save_and_load_round_trip(self, tmp_path):
        store = BPEWorkspaceStore(data_dir=tmp_path)

        assert store.save(_snapshot("durable step")) is True
        loaded = store.load("w", "a", "s")

        assert loaded is not None
        restored = BPEWorkspace.from_dict(loaded)
        assert restored.progress[0].title == "durable step"
        assert restored.experience.recall("durable procedure")
        _assert_no_temp_files(tmp_path)

    def test_save_succeeds_after_failed_replacement(self, tmp_path, monkeypatch):
        store = BPEWorkspaceStore(data_dir=tmp_path)
        _seed(store)

        def fail_replace(src, dst):
            raise OSError("replacement failed")

        with monkeypatch.context() as patch:
            patch.setattr(persistence.os, "replace", fail_replace)
            assert store.save(_snapshot("failed replacement")) is False

        assert store.save(_snapshot("recovered")) is True
        loaded = store.load("w", "a", "s")
        assert loaded is not None
        assert loaded["progress"][0]["title"] == "recovered"
        _assert_no_temp_files(tmp_path)
