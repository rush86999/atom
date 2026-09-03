"""Memory-store bootstrap tests — fresh installations and app restarts must
land on ONE store without hand migration.

Live incident (2026-09-02): old CWD-relative code accumulated the whole
memory (288 communications) under <repo>/data/atom_memory while the anchored
code read backend/data/atom_memory — after restart the agent went
memory-blind and could not find an email sitting in the store.
"""

from pathlib import Path

from core.memory_store_bootstrap import (
    memory_store_status,
    reconcile_memory_store,
)


def _mk_store(base: Path, workspace: str, tables: list, with_state=False):
    ws = base / workspace
    ws.mkdir(parents=True, exist_ok=True)
    for t in tables:
        (ws / f"{t}.lance").mkdir()
    if with_state:
        (ws / "poll_fetch_state.json").write_text('{"seen_message_ids": [1, 2]}')
    return ws


def test_migrates_legacy_store_when_anchored_is_empty(tmp_path):
    legacy = tmp_path / "repo" / "data" / "atom_memory"
    anchored = tmp_path / "repo" / "backend" / "data" / "atom_memory"
    _mk_store(legacy, "default", ["atom_communications", "documents"], with_state=True)

    summary = reconcile_memory_store(anchored_base=anchored, legacy_base=legacy)

    assert len(summary["migrated"]) == 1
    migrated_ws = anchored / "default"
    assert (migrated_ws / "atom_communications.lance").is_dir()
    assert (migrated_ws / "documents.lance").is_dir()
    assert (migrated_ws / "poll_fetch_state.json").exists()


def test_never_overwrites_anchored_store_that_has_tables(tmp_path):
    """Durable store is authoritative on conflict — adoption only fills an
    EMPTY anchored workspace."""
    legacy = tmp_path / "repo" / "data" / "atom_memory"
    anchored = tmp_path / "repo" / "backend" / "data" / "atom_memory"
    _mk_store(legacy, "default", ["atom_communications"])
    _mk_store(anchored, "default", ["chat_messages"])
    anchored_marker = anchored / "default" / "chat_messages.lance"

    summary = reconcile_memory_store(anchored_base=anchored, legacy_base=legacy)

    assert summary["migrated"] == []
    assert summary["skipped"], "conflicting workspace must be skipped"
    assert anchored_marker.is_dir(), "existing anchored table untouched"
    assert not (anchored / "default" / "atom_communications.lance").exists()


def test_fresh_install_without_legacy_store_is_a_noop(tmp_path):
    anchored = tmp_path / "repo" / "backend" / "data" / "atom_memory"

    summary = reconcile_memory_store(
        anchored_base=anchored,
        legacy_base=tmp_path / "repo" / "data" / "atom_memory",
    )

    assert summary["migrated"] == []
    assert anchored.exists() is False or list(anchored.iterdir()) == []


def test_idempotent_second_run_migrates_nothing(tmp_path):
    legacy = tmp_path / "repo" / "data" / "atom_memory"
    anchored = tmp_path / "repo" / "backend" / "data" / "atom_memory"
    _mk_store(legacy, "default", ["atom_communications"])

    first = reconcile_memory_store(anchored_base=anchored, legacy_base=legacy)
    assert len(first["migrated"]) == 1

    second = reconcile_memory_store(anchored_base=anchored, legacy_base=legacy)
    assert second["migrated"] == []


def test_lance_table_detection(tmp_path):
    from core import memory_store_bootstrap as msb

    ws = _mk_store(tmp_path, "default", ["atom_communications", "documents"])
    assert sorted(n[:-6] for n in msb._lance_tables(ws)) == [
        "atom_communications", "documents"
    ]
    assert msb._lance_tables(tmp_path / "empty") == []
