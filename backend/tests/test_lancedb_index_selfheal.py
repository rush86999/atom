"""Regression tests for the self-healing, version-aware LanceDB FTS bootstrap.

Root cause being pinned: ``table.create_fts_index("content", replace=True)``
does NOT rewrite an index whose on-disk format version the installed reader
rejects. The reader logs
``[WARN lance::index] Index content_idx has version 2, which is not supported
(<=0), ignoring it`` and silently falls back to a full scan on EVERY boot, so
the "replace=True is idempotent" assumption lost the FTS performance
permanently. Only an explicit ``drop_index`` followed by a fresh
``create_fts_index`` clears it.

These tests use a real, embedded LanceDB under ``tmp_path`` (no server).
"""

import json

import lancedb
import pytest

from core import lancedb_index_selfheal as heal


def _make_table(tmp_path, name="atom_communications"):
    """Create a real LanceDB table with a searchable ``content`` column."""
    db = lancedb.connect(str(tmp_path / "db"))
    return db.create_table(
        name,
        data=[
            {"content": "hello world", "vector": [0.0] * 4},
            {"content": "goodbye moon", "vector": [0.0] * 4},
        ],
    )


def _index_names(table):
    """Names of the indices LanceDB currently reports for the table."""
    return {idx.name for idx in table.list_indices()}


def _spy_rebuild(monkeypatch, table):
    """Instrument create/drop on a real table without changing behaviour."""
    calls = {"create": 0, "drop": []}
    orig_create = table.create_fts_index
    orig_drop = table.drop_index

    def create(*args, **kwargs):
        calls["create"] += 1
        return orig_create(*args, **kwargs)

    def drop(name):
        calls["drop"].append(name)
        return orig_drop(name)

    monkeypatch.setattr(table, "create_fts_index", create)
    monkeypatch.setattr(table, "drop_index", drop)
    return calls


def test_fresh_table_builds_index_and_writes_marker(tmp_path, monkeypatch):
    """A fresh table (no index) gets one built and the marker persisted."""
    monkeypatch.setattr(heal, "_installed_lancedb_version", lambda: "1.2.3")
    table = _make_table(tmp_path)
    marker = tmp_path / "marker.json"

    assert heal.ensure_fts_index(table, marker_key=str(marker)) is True
    assert "content_idx" in _index_names(table)
    assert marker.exists()
    assert json.loads(marker.read_text())["version"] == "1.2.3"


def test_matching_marker_does_not_rebuild(tmp_path, monkeypatch):
    """Steady state: same version + index present -> no rebuild cost."""
    monkeypatch.setattr(heal, "_installed_lancedb_version", lambda: "1.2.3")
    table = _make_table(tmp_path)
    marker = tmp_path / "marker.json"

    assert heal.ensure_fts_index(table, marker_key=str(marker)) is True
    calls = _spy_rebuild(monkeypatch, table)

    assert heal.ensure_fts_index(table, marker_key=str(marker)) is True
    assert calls["create"] == 0
    assert calls["drop"] == []


def test_stale_marker_forces_rebuild_and_rewrites_marker(tmp_path, monkeypatch):
    """Upgrade path: marker version != installed version -> drop + recreate."""
    table = _make_table(tmp_path)
    table.create_fts_index("content", replace=True)
    marker = tmp_path / "marker.json"
    marker.write_text(json.dumps({"version": "0.0.1"}))

    monkeypatch.setattr(heal, "_installed_lancedb_version", lambda: "9.9.9")
    calls = _spy_rebuild(monkeypatch, table)

    assert heal.ensure_fts_index(table, marker_key=str(marker)) is True
    assert calls["create"] == 1
    assert calls["drop"] == ["content_idx"]
    assert json.loads(marker.read_text())["version"] == "9.9.9"


def test_index_without_marker_rebuilds_once_and_writes_marker(tmp_path, monkeypatch):
    """Upgrade from an install that predates the marker: rebuild once."""
    monkeypatch.setattr(heal, "_installed_lancedb_version", lambda: "1.2.3")
    table = _make_table(tmp_path)
    table.create_fts_index("content", replace=True)
    marker = tmp_path / "marker.json"
    calls = _spy_rebuild(monkeypatch, table)

    assert heal.ensure_fts_index(table, marker_key=str(marker)) is True
    assert calls["create"] == 1
    assert calls["drop"] == ["content_idx"]
    assert marker.exists()


def test_marker_present_but_index_missing_rebuilds(tmp_path, monkeypatch):
    """A marker alone is not proof of health: the index must also exist."""
    monkeypatch.setattr(heal, "_installed_lancedb_version", lambda: "1.2.3")
    table = _make_table(tmp_path)
    marker = tmp_path / "marker.json"
    marker.write_text(json.dumps({"version": "1.2.3"}))
    calls = _spy_rebuild(monkeypatch, table)

    assert heal.ensure_fts_index(table, marker_key=str(marker)) is True
    assert calls["create"] == 1
    assert "content_idx" in _index_names(table)


def test_drops_actual_listed_index_when_name_not_found(tmp_path, monkeypatch):
    """Defensive drop: resolve the real name from list_indices()."""
    monkeypatch.setattr(heal, "_installed_lancedb_version", lambda: "1.2.3")
    table = _make_table(tmp_path)
    table.create_fts_index("content", replace=True)
    marker = tmp_path / "marker.json"
    calls = _spy_rebuild(monkeypatch, table)

    assert (
        heal.ensure_fts_index(table, index_name="some_other_name", marker_key=str(marker))
        is True
    )
    # The requested name is dropped best-effort, and the real FTS index on the
    # column is dropped too, so a stale reader-rejected index cannot survive.
    assert "content_idx" in calls["drop"]


def test_drop_not_found_is_swallowed(tmp_path, monkeypatch):
    """A 'no such index' error from the drop must not abort the rebuild."""
    monkeypatch.setattr(heal, "_installed_lancedb_version", lambda: "1.2.3")
    table = _make_table(tmp_path)
    table.create_fts_index("content", replace=True)
    marker = tmp_path / "marker.json"

    def explode(name):
        raise ValueError(f"Index {name} not found")

    monkeypatch.setattr(table, "drop_index", explode)

    assert heal.ensure_fts_index(table, marker_key=str(marker)) is True
    assert "content_idx" in _index_names(table)


def test_failure_path_returns_false_and_never_raises(tmp_path):
    """A broken table object must degrade to False, never crash startup."""
    assert heal.ensure_fts_index(object()) is False

    class Broken:
        """Table-shaped object whose rebuild always fails."""

        name = "broken"
        _dataset_uri = str(tmp_path / "broken.lance")

        def list_indices(self):
            return []

        def create_fts_index(self, *args, **kwargs):
            raise RuntimeError("boom")

        def drop_index(self, name):
            raise RuntimeError("boom")

    assert heal.ensure_fts_index(Broken(), marker_key=str(tmp_path / "m.json")) is False


def test_marker_path_is_per_table(tmp_path):
    """Two tables in one database must not share a marker file."""
    first = _make_table(tmp_path, name="table_one")
    second = _make_table(tmp_path, name="table_two")

    first_marker = heal._resolve_marker_path(first, "content", None)
    second_marker = heal._resolve_marker_path(second, "content", None)

    assert first_marker != second_marker
    assert first_marker.name != second_marker.name
    assert first_marker.parent == second_marker.parent


def test_marker_parent_directories_are_created(tmp_path, monkeypatch):
    """The marker helper creates nested parent dirs as needed."""
    monkeypatch.setattr(heal, "_installed_lancedb_version", lambda: "1.2.3")
    table = _make_table(tmp_path)
    marker = tmp_path / "nested" / "deeper" / "marker.json"

    assert heal.ensure_fts_index(table, marker_key=str(marker)) is True
    assert marker.exists()


def test_returns_true_when_marker_write_fails(tmp_path, monkeypatch):
    """A read-only marker location must not report the (working) index as down."""
    monkeypatch.setattr(heal, "_installed_lancedb_version", lambda: "1.2.3")
    table = _make_table(tmp_path)

    def explode(*args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(heal, "_write_marker", explode)

    assert heal.ensure_fts_index(table, marker_key=str(tmp_path / "m.json")) is True
    assert "content_idx" in _index_names(table)
