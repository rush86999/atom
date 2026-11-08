"""Failure-first controls for persisted BPE namespace identity.

The store must preserve the exact ``(workspace_id, agent_id, scope_key)``
triple across a process restart. The pre-repair format was ambiguous in two
ways: the file name replaced every non-alphanumeric character with ``_`` and
the inner key joined ``agent_id`` and ``scope_key`` with ``|``. Different
namespaces could therefore share (and overwrite) one persisted slot. A stored
snapshot's embedded identity was also trusted even when it disagreed with the
requested namespace.

These controls use the real :class:`BPEWorkspaceStore` on ``tmp_path``. Root
owns execution; nothing here is asserted as passing by the author.
"""
from __future__ import annotations

import json

import pytest

import core.bpe.persistence as persistence
from core.bpe.persistence import BPEWorkspaceStore
from core.bpe.workspace import BPEWorkspace, Subgoal, get_workspace, reset_registry


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


def _snapshot(workspace_id="w", agent_id="a", scope_key="s",
              title="durable step") -> dict:
    workspace = BPEWorkspace(workspace_id, agent_id, scope_key)
    workspace.progress.append(Subgoal(title))
    workspace._pending_notes.append(f"note for {title}")
    return workspace.to_dict()


def _raw_scopes(store: BPEWorkspaceStore, workspace_id: str) -> dict:
    path = store._path_for(workspace_id)
    return json.loads(path.read_text(encoding="utf-8"))


def _title(store: BPEWorkspaceStore, workspace_id, agent_id, scope_key) -> str:
    snapshot = store.load(workspace_id, agent_id, scope_key)
    assert snapshot is not None
    return snapshot["progress"][0]["title"]


# ---------------------------------------------------------------------------
# Preserved foundation: normal ids keep their historic spelling
# ---------------------------------------------------------------------------


def test_safe_namespace_keeps_historic_filename_and_key(tmp_path):
    store = BPEWorkspaceStore(data_dir=tmp_path)

    assert store._path_for("w") == tmp_path / "w.json"
    assert store.save(_snapshot("w", "a", "s", "historic")) is True

    scopes = _raw_scopes(store, "w")
    assert "a|s" in scopes
    assert scopes["a|s"]["workspace_id"] == "w"
    assert scopes["a|s"]["agent_id"] == "a"
    assert scopes["a|s"]["scope_key"] == "s"
    assert _title(store, "w", "a", "s") == "historic"


# ---------------------------------------------------------------------------
# File-name collisions (old lossy sanitizer)
# ---------------------------------------------------------------------------


def test_lossy_workspace_filenames_cannot_collide(tmp_path):
    store = BPEWorkspaceStore(data_dir=tmp_path)
    # All three previously resolved to personal_user-1.json.
    workspace_ids = ("personal:user-1", "personal_user-1", "personal/user-1")

    paths = {store._path_for(value) for value in workspace_ids}
    assert len(paths) == len(workspace_ids)

    for workspace_id in workspace_ids:
        assert store.save(
            _snapshot(workspace_id, "a", "s", workspace_id)
        ) is True

    for workspace_id in workspace_ids:
        assert _title(store, workspace_id, "a", "s") == workspace_id


def test_mixed_case_workspace_names_cannot_share_a_file(tmp_path):
    store = BPEWorkspaceStore(data_dir=tmp_path)

    # Case-insensitive filesystems would otherwise alias Workspace.json and
    # workspace.json.
    assert store._path_for("workspace") != store._path_for("Workspace")
    assert store.save(_snapshot("workspace", "a", "s", "lower")) is True
    assert store.save(_snapshot("Workspace", "a", "s", "upper")) is True

    assert _title(store, "workspace", "a", "s") == "lower"
    assert _title(store, "Workspace", "a", "s") == "upper"


@pytest.mark.parametrize(
    "left,right",
    [
        (("agent|scope", ""), ("agent", "scope|")),
        (("a|b", "c"), ("a", "b|c")),
    ],
)
def test_scope_separator_collisions_are_distinct(tmp_path, left, right):
    store = BPEWorkspaceStore(data_dir=tmp_path)

    # Each pair produced the same legacy key: agent|scope|...
    store.save(_snapshot("w", left[0], left[1], "left"))
    store.save(_snapshot("w", right[0], right[1], "right"))

    scopes = _raw_scopes(store, "w")
    assert len(scopes) == 2

    assert _title(store, "w", left[0], left[1]) == "left"
    assert _title(store, "w", right[0], right[1]) == "right"


# ---------------------------------------------------------------------------
# Persisted snapshot identity must equal the requested namespace
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("workspace_id", "other-workspace"),
        ("agent_id", "other-agent"),
        ("scope_key", "other-scope"),
    ],
)
def test_embedded_identity_mismatch_is_refused(tmp_path, field, bad_value):
    store = BPEWorkspaceStore(data_dir=tmp_path)
    assert store.save(_snapshot("w", "a", "s", "owned")) is True

    path = store._path_for("w")
    scopes = json.loads(path.read_text(encoding="utf-8"))
    scopes["a|s"][field] = bad_value
    path.write_text(json.dumps(scopes), encoding="utf-8")

    assert store.load("w", "a", "s") is None


def test_tampered_snapshot_is_not_restored_under_requested_namespace(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    store = BPEWorkspaceStore(data_dir=tmp_path)
    assert store.save(_snapshot("w", "a", "s", "owned")) is True

    path = store._path_for("w")
    scopes = json.loads(path.read_text(encoding="utf-8"))
    scopes["a|s"]["agent_id"] = "other-agent"
    path.write_text(json.dumps(scopes), encoding="utf-8")

    reset_registry()  # simulate a fresh process
    restored = get_workspace("w", "a", "s")

    assert (
        restored.workspace_id, restored.agent_id, restored.scope_key
    ) == ("w", "a", "s")
    assert restored.progress == []
    assert restored._pending_notes == []


# ---------------------------------------------------------------------------
# Valid twins: encoded namespaces survive a real registry restore
# ---------------------------------------------------------------------------


def test_valid_awkward_namespace_survives_registry_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    store = BPEWorkspaceStore(data_dir=tmp_path)
    namespace = ("personal:user-7", "agent|one", "run|two")
    assert store.save(_snapshot(*namespace, title="restore me")) is True

    reset_registry()  # simulate a fresh process
    restored = get_workspace(*namespace)

    assert (
        restored.workspace_id, restored.agent_id, restored.scope_key
    ) == namespace
    assert restored.progress[0].title == "restore me"
    assert restored._pending_notes == ["note for restore me"]


# ---------------------------------------------------------------------------
# Read-through compatibility for pre-repair lossy files
# ---------------------------------------------------------------------------


def test_legacy_lossy_file_is_read_without_being_moved_or_deleted(tmp_path):
    store = BPEWorkspaceStore(data_dir=tmp_path)
    workspace_id = "personal:legacy"
    canonical = store._path_for(workspace_id)
    legacy = store._legacy_path_for(workspace_id)
    assert canonical != legacy

    legacy.write_text(
        json.dumps({
            "a|s": _snapshot(workspace_id, "a", "s", "legacy"),
            "b|t": _snapshot(workspace_id, "b", "t", "legacy sibling"),
        }),
        encoding="utf-8",
    )
    original_bytes = legacy.read_bytes()

    assert _title(store, workspace_id, "a", "s") == "legacy"
    assert store.save(
        _snapshot(workspace_id, "a", "s", "updated")
    ) is True

    assert canonical.exists()
    assert legacy.read_bytes() == original_bytes
    assert _title(store, workspace_id, "a", "s") == "updated"
    # Other scopes of the SAME workspace are carried into the canonical file;
    # only foreign workspace ids are excluded.
    assert _title(store, workspace_id, "b", "t") == "legacy sibling"


def test_legacy_colliding_file_cannot_lend_a_foreign_namespace(tmp_path):
    store = BPEWorkspaceStore(data_dir=tmp_path)
    target = "personal:collision"
    foreign = "personal_collision"  # same old lossy file name

    legacy = store._legacy_path_for(target)
    assert legacy == store._legacy_path_for(foreign)
    legacy.write_text(
        json.dumps({"a|s": _snapshot(foreign, "a", "s", "foreign")}),
        encoding="utf-8",
    )

    # The only entry in the shared legacy file belongs to another namespace.
    assert store.load(target, "a", "s") is None

    assert store.save(_snapshot(target, "a", "s", "target")) is True
    scopes = _raw_scopes(store, target)
    assert [entry["workspace_id"] for entry in scopes.values()] == [target]
    assert _title(store, target, "a", "s") == "target"

    # The old file is left untouched, including the foreign entry.
    legacy_scopes = json.loads(legacy.read_text(encoding="utf-8"))
    assert legacy_scopes["a|s"]["workspace_id"] == foreign


def test_traversal_shaped_workspace_ids_stay_inside_the_store(tmp_path):
    store = BPEWorkspaceStore(data_dir=tmp_path)

    for workspace_id in ("../escape", "..", "/absolute", "a/b", "a\\b"):
        assert store._path_for(workspace_id).parent == tmp_path
        assert store.save(
            _snapshot(workspace_id, "a", "s", workspace_id)
        ) is True
        assert _title(store, workspace_id, "a", "s") == workspace_id
