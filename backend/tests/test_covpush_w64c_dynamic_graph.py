"""Coverage push wave 64c — core/graphrag/dynamic_graph.py (TDD).

Target: >=95% statement coverage STANDALONE (this file alone).

Covers: UpdateType/GraphVersionStatus enums, IncrementalUpdateConfig,
GraphUpdate/GraphSnapshot dataclasses; GraphVersionManager (create_version
with/without session, version ids, graph hashes, rollback, diff);
IncrementalUpdateManager (add_update with batch-size/timeout flushes,
flush_updates empty/snapshot/context-session paths, _flush_impl happy +
failure + direct batch=None path, version creation thresholds, grouping,
node/edge apply for add/update/delete with all partial-update branches);
TemporalGraphTracker (metrics with data, empty workspace, no-session path);
DynamicGraphManager delegations (add_node with/without embedding, add_edge,
delete_node/delete_edge, flush, create_version, get_evolution_metrics); and
the three factory functions.

Uses a per-test temp-file SQLite engine (same pattern as the fleet
coordinator wave); zero LLM spend, no network.
"""
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.graphrag.dynamic_graph import (
    DynamicGraphManager,
    GraphSnapshot,
    GraphUpdate,
    GraphVersionManager,
    GraphVersionStatus,
    IncrementalUpdateConfig,
    IncrementalUpdateManager,
    TemporalGraphTracker,
    UpdateType,
    get_dynamic_graph_manager,
    get_incremental_updater,
    get_version_manager,
)
from core.models import GraphEdge, GraphNode
from core.models_registration import Base


@pytest.fixture()
def db_session():
    """Per-test isolated SQLite engine (temp file)."""
    _fd, _db_path = tempfile.mkstemp(suffix=".db")
    os.close(_fd)
    engine = create_engine(
        f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})
    _seen_idx = set()
    for _table in list(Base.metadata.tables.values()):
        for _idx in list(_table.indexes):
            if _idx.name in _seen_idx:
                _table.indexes.remove(_idx)
            else:
                _seen_idx.add(_idx.name)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.unlink(_db_path)
        except OSError:
            pass


class _Ctx:
    """Context-manager stand-in for get_db_session()."""

    def __init__(self, sess):
        self._sess = sess

    def __enter__(self):
        return self._sess

    def __exit__(self, *args):
        return False


def make_config(**overrides):
    base = dict(
        batch_size=100,
        batch_timeout_ms=5000,
        enable_versioning=True,
        max_versions=100,
        version_retention_days=30,
        auto_update_on_change=True,
        update_threshold=10,
        enable_indexing=True,
        enable_stats=True,
    )
    base.update(overrides)
    return IncrementalUpdateConfig(**base)


def make_update(update_type=UpdateType.NODE_ADD, entity_id="n1", data=None, **kw):
    return GraphUpdate(
        update_type=update_type,
        entity_id=entity_id,
        data=data or {},
        **kw,
    )


def insert_node(session, node_id, name="Node", node_type="person",
                description="desc", properties=None, embedding=None):
    session.add(GraphNode(
        id=node_id,
        workspace_id="ws1",
        name=name,
        type=node_type,
        description=description,
        properties=properties or {},
        embedding=embedding,
    ))
    session.commit()


def insert_edge(session, edge_id, source, target, rel="related_to", props=None):
    session.add(GraphEdge(
        id=edge_id,
        workspace_id="ws1",
        source_node_id=source,
        target_node_id=target,
        relationship_type=rel,
        properties=props or {},
    ))
    session.commit()


# ============================================================================
# Enums, Config and Dataclasses
# ============================================================================

class TestUpdateType:
    def test_values(self):
        assert UpdateType.NODE_ADD.value == "node_add"
        assert UpdateType.NODE_UPDATE.value == "node_update"
        assert UpdateType.NODE_DELETE.value == "node_delete"
        assert UpdateType.EDGE_ADD.value == "edge_add"
        assert UpdateType.EDGE_UPDATE.value == "edge_update"
        assert UpdateType.EDGE_DELETE.value == "edge_delete"
        assert UpdateType.BATCH_UPDATE.value == "batch_update"


class TestGraphVersionStatus:
    def test_values(self):
        assert GraphVersionStatus.DRAFT.value == "draft"
        assert GraphVersionStatus.COMMITTED.value == "committed"
        assert GraphVersionStatus.ROLLED_BACK.value == "rolled_back"
        assert GraphVersionStatus.ARCHIVED.value == "archived"


class TestIncrementalUpdateConfig:
    def test_defaults(self):
        config = IncrementalUpdateConfig()
        assert config.batch_size == 100
        assert config.batch_timeout_ms == 5000
        assert config.enable_versioning is True
        assert config.max_versions == 100
        assert config.version_retention_days == 30
        assert config.auto_update_on_change is True
        assert config.update_threshold == 10
        assert config.enable_indexing is True
        assert config.enable_stats is True

    def test_custom_values(self):
        config = make_config(batch_size=2, batch_timeout_ms=0,
                             enable_versioning=False, update_threshold=1)
        assert config.batch_size == 2
        assert config.batch_timeout_ms == 0
        assert config.enable_versioning is False
        assert config.update_threshold == 1


class TestGraphUpdateDataclass:
    def test_defaults(self):
        update = GraphUpdate(UpdateType.NODE_ADD, "n1")
        assert update.update_type == UpdateType.NODE_ADD
        assert update.entity_id == "n1"
        assert update.data == {}
        assert update.previous_state is None
        assert update.metadata == {}
        assert update.timestamp is not None

    def test_custom_values(self):
        ts = datetime(2026, 1, 1)
        update = GraphUpdate(
            UpdateType.EDGE_ADD,
            "e1",
            data={"a": 1},
            previous_state={"a": 0},
            timestamp=ts,
            metadata={"workspace_id": "ws1"},
        )
        assert update.data == {"a": 1}
        assert update.previous_state == {"a": 0}
        assert update.timestamp == ts
        assert update.metadata == {"workspace_id": "ws1"}


class TestGraphSnapshotDataclass:
    def test_fields_and_metadata_default(self):
        ts = datetime(2026, 1, 1)
        snapshot = GraphSnapshot(version_id="v_1", timestamp=ts,
                                 node_count=1, edge_count=2, hash="abc")
        assert snapshot.version_id == "v_1"
        assert snapshot.timestamp == ts
        assert snapshot.node_count == 1
        assert snapshot.edge_count == 2
        assert snapshot.hash == "abc"
        assert snapshot.metadata == {}


# ============================================================================
# GraphVersionManager
# ============================================================================

class TestGraphVersionManager:
    def test_init_default_config(self):
        manager = GraphVersionManager()
        assert manager.config == IncrementalUpdateConfig()

    def test_init_with_config(self):
        config = make_config(enable_versioning=False)
        manager = GraphVersionManager(config)
        assert manager.config is config

    def test_create_version_empty_workspace(self, db_session):
        manager = GraphVersionManager()
        snapshot = manager.create_version("ws1", db_session, {"reason": "test"})
        assert snapshot.node_count == 0
        assert snapshot.edge_count == 0
        assert snapshot.hash == hashlib_sha256("nodes:[]|edges:[]")
        assert snapshot.metadata == {"reason": "test"}
        assert snapshot.version_id.startswith("v_")
        assert snapshot.timestamp is not None

    def test_create_version_counts_and_hash(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2", node_type="task")
        insert_edge(db_session, "e1", "n1", "n2", "depends_on")
        manager = GraphVersionManager()
        snapshot = manager.create_version("ws1", db_session)
        assert snapshot.node_count == 2
        assert snapshot.edge_count == 1
        assert snapshot.hash == hashlib_sha256(
            "nodes:['n1', 'n2']|edges:[('n1', 'n2')]")

    def test_hash_changes_when_graph_changes(self, db_session):
        insert_node(db_session, "n1")
        manager = GraphVersionManager()
        first = manager.create_version("ws1", db_session).hash
        insert_node(db_session, "n3")
        second = manager.create_version("ws1", db_session).hash
        assert first != second

    def test_create_version_without_session(self, db_session):
        manager = GraphVersionManager()
        with patch("core.graphrag.dynamic_graph.get_db_session",
                   return_value=_Ctx(db_session)) as ctx:
            snapshot = manager.create_version("ws1", None)
        ctx.assert_called_once_with()
        assert snapshot.node_count == 0

    def test_generate_version_id_format(self):
        manager = GraphVersionManager()
        version_id = manager._generate_version_id()
        parts = version_id.split("_")
        assert parts[0] == "v"
        assert len(parts) == 4
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert len(parts[3]) == 8  # md5 prefix

    def test_generate_graph_hash_sorted(self, db_session):
        insert_node(db_session, "z_node")
        insert_node(db_session, "a_node")
        insert_edge(db_session, "e2", "z_node", "a_node")
        insert_edge(db_session, "e1", "a_node", "z_node")
        manager = GraphVersionManager()
        h1 = manager._generate_graph_hash("ws1", db_session)
        # Same state, another session → deterministic hash
        h2 = manager._generate_graph_hash("ws1", db_session)
        assert h1 == h2
        assert len(h1) == 16

    def test_rollback_with_session(self, db_session):
        manager = GraphVersionManager()
        assert manager.rollback_to_version("ws1", "v_x", db_session) is True

    def test_rollback_without_session(self, db_session):
        manager = GraphVersionManager()
        with patch("core.graphrag.dynamic_graph.get_db_session",
                   return_value=_Ctx(db_session)):
            assert manager.rollback_to_version("ws1", "v_x") is True

    def test_get_version_diff(self):
        manager = GraphVersionManager()
        assert manager.get_version_diff("ws1", "v1", "v2", MagicMock()) == []
        assert manager.get_version_diff("ws1", "v1", "v2") == []


# ============================================================================
# IncrementalUpdateManager — add_update / flush
# ============================================================================

class TestIncrementalUpdateManagerAdd:
    def test_init_defaults(self):
        manager = IncrementalUpdateManager()
        assert manager.config == IncrementalUpdateConfig()
        assert manager.pending_updates == []
        assert isinstance(manager.version_manager, GraphVersionManager)
        assert manager.last_flush is not None

    def test_init_with_config(self):
        config = make_config(batch_size=2)
        manager = IncrementalUpdateManager(config)
        assert manager.config is config
        assert manager.version_manager.config is config

    def test_add_update_buffers_without_flush(self, db_session):
        manager = IncrementalUpdateManager(make_config(batch_size=10))
        result = manager.add_update(UpdateType.NODE_ADD, "n1",
                                    {"id": "n1", "name": "N"},
                                    "ws1", db_session)
        assert result is True
        assert len(manager.pending_updates) == 1
        update = manager.pending_updates[0]
        assert update.update_type == UpdateType.NODE_ADD
        assert update.entity_id == "n1"
        assert update.metadata == {"workspace_id": "ws1"}

    def test_add_update_flushes_at_batch_size(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=2, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_ADD, "n1",
                           {"id": "n1", "name": "One"}, "ws1", db_session)
        result = manager.add_update(UpdateType.NODE_ADD, "n2",
                                    {"id": "n2", "name": "Two"}, "ws1", db_session)
        assert result is True
        assert manager.pending_updates == []
        assert db_session.query(GraphNode).filter(
            GraphNode.workspace_id == "ws1").count() == 2

    def test_add_update_flushes_on_timeout(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=10, batch_timeout_ms=5000, enable_versioning=False))
        manager.last_flush = datetime.now() - timedelta(seconds=10)
        result = manager.add_update(UpdateType.NODE_ADD, "n1",
                                    {"id": "n1", "name": "Late"}, "ws1",
                                    db_session)
        assert result is True
        assert manager.pending_updates == []
        assert db_session.query(GraphNode).filter(
            GraphNode.id == "n1").first() is not None

    def test_add_update_timeout_not_elapsed_no_flush(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=10, batch_timeout_ms=5000, enable_versioning=False))
        result = manager.add_update(UpdateType.NODE_ADD, "n1",
                                    {"id": "n1", "name": "Now"}, "ws1",
                                    db_session)
        assert result is True
        assert len(manager.pending_updates) == 1
        assert db_session.query(GraphNode).filter(
            GraphNode.id == "n1").first() is None

    def test_add_update_timeout_disabled_no_flush(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=10, batch_timeout_ms=0, enable_versioning=False))
        manager.last_flush = datetime.now() - timedelta(days=1)
        result = manager.add_update(UpdateType.NODE_ADD, "n1",
                                    {"id": "n1", "name": "Old"}, "ws1",
                                    db_session)
        assert result is True
        assert len(manager.pending_updates) == 1


class TestIncrementalUpdateManagerFlush:
    def test_flush_empty_pending_returns_true(self, db_session):
        manager = IncrementalUpdateManager()
        assert manager.flush_updates("ws1", db_session) is True

    def test_flush_with_session_clears_pending(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=10, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_ADD, "n1",
                           {"id": "n1", "name": "A"}, "ws1", db_session)
        manager.add_update(UpdateType.NODE_ADD, "n2",
                           {"id": "n2", "name": "B"}, "ws1", db_session)
        assert manager.flush_updates("ws1", db_session) is True
        assert manager.pending_updates == []
        assert db_session.query(GraphNode).count() == 2

    def test_flush_without_session_uses_context(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=10, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_ADD, "n1",
                           {"id": "n1", "name": "Ctx"}, "ws1", db_session)
        with patch("core.graphrag.dynamic_graph.get_db_session",
                   return_value=_Ctx(db_session)):
            assert manager.flush_updates("ws1") is True
        assert db_session.query(GraphNode).filter(
            GraphNode.id == "n1").first() is not None

    def test_flush_impl_direct_batch_none(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=10, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_ADD, "n1",
                           {"id": "n1", "name": "Direct"}, "ws1", db_session)
        assert manager._flush_impl("ws1", db_session) is True
        assert manager.pending_updates == []
        assert db_session.query(GraphNode).filter(
            GraphNode.id == "n1").first() is not None

    def test_flush_impl_exception_rolls_back(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=10, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_ADD, "n1",
                           {"id": "n1", "name": "Boom"}, "ws1", db_session)
        db_session.commit = Mock(side_effect=RuntimeError("db down"))
        with patch("core.graphrag.dynamic_graph.logger", MagicMock()) as log, \
             patch.object(db_session, "rollback", wraps=db_session.rollback) as rb:
            assert manager._flush_impl("ws1", db_session) is False
        rb.assert_called_once()
        log.error.assert_called_once()
        assert len(manager.pending_updates) == 1

    def test_flush_creates_version_when_threshold_met(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0,
            enable_versioning=True, update_threshold=1))
        snapshot = GraphSnapshot(version_id="v_new", timestamp=datetime.now(),
                                 node_count=1, edge_count=0, hash="h")
        manager.version_manager.create_version = Mock(return_value=snapshot)
        result = manager.add_update(UpdateType.NODE_ADD, "n1",
                                    {"id": "n1", "name": "V"}, "ws1",
                                    db_session)
        assert result is True
        manager.version_manager.create_version.assert_called_once_with(
            "ws1", db_session)

    def test_flush_skips_version_below_threshold(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=2, batch_timeout_ms=0,
            enable_versioning=True, update_threshold=10))
        manager.version_manager.create_version = Mock()
        manager.add_update(UpdateType.NODE_ADD, "n1",
                           {"id": "n1", "name": "V"}, "ws1", db_session)
        manager.add_update(UpdateType.NODE_ADD, "n2",
                           {"id": "n2", "name": "V"}, "ws1", db_session)
        manager.version_manager.create_version.assert_not_called()

    def test_flush_skips_version_when_versioning_disabled(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0,
            enable_versioning=False, update_threshold=1))
        manager.version_manager.create_version = Mock()
        manager.add_update(UpdateType.NODE_ADD, "n1",
                           {"id": "n1", "name": "V"}, "ws1", db_session)
        manager.version_manager.create_version.assert_not_called()

    def test_should_flush_all_conditions_false(self):
        manager = IncrementalUpdateManager(make_config(
            batch_size=10, batch_timeout_ms=5000))
        manager.pending_updates.append(make_update())
        assert manager._should_flush() is False

    def test_should_flush_batch_size_reached(self):
        manager = IncrementalUpdateManager(make_config(batch_size=2))
        manager.pending_updates = [make_update(), make_update()]
        assert manager._should_flush() is True

    def test_should_flush_timeout_reached(self):
        manager = IncrementalUpdateManager(make_config(batch_timeout_ms=100))
        manager.pending_updates = [make_update()]
        manager.last_flush = datetime.now() - timedelta(seconds=1)
        assert manager._should_flush() is True


# ============================================================================
# IncrementalUpdateManager — apply operations
# ============================================================================

class TestNodeApply:
    def test_create_new_node_full_data(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_ADD, "n1", {
            "id": "n1", "name": "Alice", "type": "person",
            "description": "founder", "properties": {"role": "ceo"},
            "embedding": [0.1, 0.2],
        }, "ws1", db_session)
        node = db_session.query(GraphNode).filter(GraphNode.id == "n1").first()
        assert node.name == "Alice"
        assert node.type == "person"
        assert node.description == "founder"
        assert node.properties == {"role": "ceo"}
        assert node.embedding == [0.1, 0.2]

    def test_create_new_node_uses_entity_id_and_name_fallback(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_ADD, "n1", {
            "type": "task",
        }, "ws1", db_session)
        node = db_session.query(GraphNode).filter(GraphNode.id == "n1").first()
        assert node.name == "node_n1"
        assert node.type == "task"
        assert node.description == ""
        assert node.properties == {}

    def test_update_existing_node_all_fields(self, db_session):
        insert_node(db_session, "n1", name="Old", node_type="person",
                    description="old", properties={"k": 1}, embedding=[0.0])
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_UPDATE, "n1", {
            "id": "n1", "name": "New", "type": "task",
            "description": "fresh", "properties": {"k": 2},
            "embedding": [0.9],
        }, "ws1", db_session)
        node = db_session.query(GraphNode).filter(GraphNode.id == "n1").first()
        assert node.name == "New"
        assert node.type == "task"
        assert node.description == "fresh"
        assert node.properties == {"k": 2}
        assert node.embedding == [0.9]

    def test_update_existing_node_partial_name_only(self, db_session):
        insert_node(db_session, "n1", name="Old", node_type="person",
                    description="keep", properties={"k": 1})
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_UPDATE, "n1", {
            "id": "n1", "name": "Renamed",
        }, "ws1", db_session)
        node = db_session.query(GraphNode).filter(GraphNode.id == "n1").first()
        assert node.name == "Renamed"
        assert node.type == "person"
        assert node.description == "keep"
        assert node.properties == {"k": 1}

    def test_update_existing_node_type_without_name(self, db_session):
        insert_node(db_session, "n1", name="Keep Name", node_type="person")
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_UPDATE, "n1", {
            "id": "n1", "type": "project",
        }, "ws1", db_session)
        node = db_session.query(GraphNode).filter(GraphNode.id == "n1").first()
        assert node.name == "Keep Name"
        assert node.type == "project"

    def test_delete_node_removes_connected_edges(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2")
        insert_node(db_session, "n3")
        insert_edge(db_session, "e1", "n1", "n2", "outgoing")
        insert_edge(db_session, "e2", "n3", "n1", "incoming")
        insert_edge(db_session, "e3", "n2", "n3", "unrelated")
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_DELETE, "n1", {}, "ws1", db_session)
        assert db_session.query(GraphNode).filter(
            GraphNode.id == "n1").first() is None
        assert db_session.query(GraphEdge).filter(
            GraphEdge.id == "e1").first() is None
        assert db_session.query(GraphEdge).filter(
            GraphEdge.id == "e2").first() is None
        assert db_session.query(GraphEdge).filter(
            GraphEdge.id == "e3").first() is not None


class TestEdgeApply:
    def test_create_new_edge_full_data(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2")
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.EDGE_ADD, "n1_n2", {
            "id": "e1", "source_node_id": "n1", "target_node_id": "n2",
            "relationship_type": "manages", "properties": {"weight": 2},
        }, "ws1", db_session)
        edge = db_session.query(GraphEdge).filter(GraphEdge.id == "e1").first()
        assert edge.source_node_id == "n1"
        assert edge.target_node_id == "n2"
        assert edge.relationship_type == "manages"
        assert edge.properties == {"weight": 2}

    def test_create_new_edge_without_id(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2")
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.EDGE_ADD, "n1_n2", {
            "source_node_id": "n1", "target_node_id": "n2",
        }, "ws1", db_session)
        edge = db_session.query(GraphEdge).filter(
            GraphEdge.source_node_id == "n1",
            GraphEdge.target_node_id == "n2").first()
        assert edge is not None
        assert edge.relationship_type == "related_to"
        assert edge.id is not None

    def test_create_edge_missing_endpoint_skipped(self, db_session):
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.EDGE_ADD, "n1_n2", {
            "id": "e1", "source_node_id": "n1",
        }, "ws1", db_session)
        assert db_session.query(GraphEdge).filter(
            GraphEdge.id == "e1").first() is None

    def test_update_existing_edge(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2")
        insert_edge(db_session, "e1", "n1", "n2", "related_to", {"a": 1})
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.EDGE_UPDATE, "n1_n2", {
            "source_node_id": "n1", "target_node_id": "n2",
            "relationship_type": "blocks", "properties": {"b": 2},
        }, "ws1", db_session)
        edge = db_session.query(GraphEdge).filter(GraphEdge.id == "e1").first()
        assert edge.relationship_type == "blocks"
        assert edge.properties == {"b": 2}

    def test_update_existing_edge_properties_only(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2")
        insert_edge(db_session, "e1", "n1", "n2", "related_to")
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.EDGE_UPDATE, "n1_n2", {
            "source_node_id": "n1", "target_node_id": "n2",
            "properties": {"strength": 5},
        }, "ws1", db_session)
        edge = db_session.query(GraphEdge).filter(GraphEdge.id == "e1").first()
        assert edge.relationship_type == "related_to"
        assert edge.properties == {"strength": 5}

    def test_update_edge_creates_when_absent(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2")
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.EDGE_UPDATE, "n1_n2", {
            "id": "e9", "source_node_id": "n1", "target_node_id": "n2",
            "relationship_type": "reports_to",
        }, "ws1", db_session)
        assert db_session.query(GraphEdge).filter(
            GraphEdge.id == "e9").first() is not None

    def test_delete_edge(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2")
        insert_edge(db_session, "e1", "n1", "n2")
        manager = IncrementalUpdateManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.EDGE_DELETE, "e1", {}, "ws1", db_session)
        assert db_session.query(GraphEdge).filter(
            GraphEdge.id == "e1").first() is None


class TestGroupAndDispatch:
    def test_group_updates_by_type(self):
        manager = IncrementalUpdateManager()
        updates = [
            make_update(UpdateType.NODE_ADD, "n1"),
            make_update(UpdateType.NODE_ADD, "n2"),
            make_update(UpdateType.EDGE_ADD, "e1"),
            make_update(UpdateType.NODE_DELETE, "n3"),
        ]
        grouped = manager._group_updates(updates)
        assert set(grouped.keys()) == {
            UpdateType.NODE_ADD, UpdateType.EDGE_ADD, UpdateType.NODE_DELETE}
        assert len(grouped[UpdateType.NODE_ADD]) == 2

    def test_flush_dispatches_mixed_types(self, db_session):
        insert_node(db_session, "n2")
        insert_node(db_session, "n3")
        insert_edge(db_session, "e1", "n2", "n3")
        manager = IncrementalUpdateManager(make_config(
            batch_size=4, batch_timeout_ms=0, enable_versioning=False))
        manager.add_update(UpdateType.NODE_ADD, "n1",
                           {"id": "n1", "name": "One"}, "ws1", db_session)
        manager.add_update(UpdateType.EDGE_ADD, "n1_n2", {
            "id": "e2", "source_node_id": "n1", "target_node_id": "n2",
        }, "ws1", db_session)
        manager.add_update(UpdateType.NODE_DELETE, "n3", {}, "ws1", db_session)
        manager.add_update(UpdateType.EDGE_DELETE, "e1", {}, "ws1", db_session)
        assert manager.flush_updates("ws1", db_session) is True
        assert db_session.query(GraphNode).filter(
            GraphNode.id == "n1").first() is not None
        assert db_session.query(GraphNode).filter(
            GraphNode.id == "n3").first() is None
        assert db_session.query(GraphEdge).filter(
            GraphEdge.id == "e2").first() is not None
        assert db_session.query(GraphEdge).filter(
            GraphEdge.id == "e1").first() is None


# ============================================================================
# TemporalGraphTracker
# ============================================================================

class TestTemporalGraphTracker:
    def test_init_defaults(self):
        tracker = TemporalGraphTracker()
        assert tracker.config == IncrementalUpdateConfig()

    def test_init_with_config(self):
        config = make_config(enable_stats=False)
        tracker = TemporalGraphTracker(config)
        assert tracker.config is config

    def test_metrics_with_growth(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2")
        insert_node(db_session, "n3")
        insert_edge(db_session, "e1", "n1", "n2")
        tracker = TemporalGraphTracker()
        metrics = tracker.get_evolution_metrics("ws1", 24, db_session)
        assert metrics["workspace_id"] == "ws1"
        assert metrics["period_hours"] == 24
        assert metrics["new_nodes"] == 3
        assert metrics["new_edges"] == 1
        assert metrics["total_nodes"] == 3
        assert metrics["total_edges"] == 1
        assert metrics["node_growth_rate_percent"] == 100.0
        assert metrics["edge_growth_rate_percent"] == 100.0
        assert metrics["query_time"]

    def test_metrics_empty_workspace_zero_growth(self, db_session):
        tracker = TemporalGraphTracker()
        metrics = tracker.get_evolution_metrics("other_ws", 1, db_session)
        assert metrics["total_nodes"] == 0
        assert metrics["total_edges"] == 0
        assert metrics["node_growth_rate_percent"] == 0
        assert metrics["edge_growth_rate_percent"] == 0

    def test_metrics_without_session(self, db_session):
        insert_node(db_session, "n1")
        tracker = TemporalGraphTracker()
        with patch("core.graphrag.dynamic_graph.get_db_session",
                   return_value=_Ctx(db_session)):
            metrics = tracker.get_evolution_metrics("ws1", 24)
        assert metrics["total_nodes"] == 1

    def test_metrics_rounded(self, db_session):
        insert_node(db_session, "n1")
        insert_node(db_session, "n2")
        insert_node(db_session, "n3")
        for node_id in ("n4", "n5", "n6", "n7"):
            insert_node(db_session, node_id)
        # Backdate 4 of the 7 nodes beyond the look-back window
        old = datetime.now() - timedelta(days=2)
        for node_id in ("n4", "n5", "n6", "n7"):
            node = db_session.query(GraphNode).filter(
                GraphNode.id == node_id).first()
            node.created_at = old
        db_session.commit()
        tracker = TemporalGraphTracker()
        metrics = tracker.get_evolution_metrics("ws1", 24, db_session)
        assert metrics["new_nodes"] == 3
        assert metrics["total_nodes"] == 7
        assert metrics["node_growth_rate_percent"] == 42.86


# ============================================================================
# DynamicGraphManager
# ============================================================================

class TestDynamicGraphManager:
    def test_init_default_and_with_config(self):
        manager = DynamicGraphManager()
        assert manager.config == IncrementalUpdateConfig()
        assert isinstance(manager.update_manager, IncrementalUpdateManager)
        assert isinstance(manager.version_manager, GraphVersionManager)
        assert isinstance(manager.temporal_tracker, TemporalGraphTracker)

        config = make_config(batch_size=5)
        manager2 = DynamicGraphManager(config)
        assert manager2.config is config
        assert manager2.update_manager.config is config

    def test_add_node_without_embedding(self, db_session):
        manager = DynamicGraphManager(make_config(batch_size=10))
        assert manager.add_node("ws1", "n1", "Node One", "person",
                                "desc", {"k": 1}, session=db_session) is True
        update = manager.update_manager.pending_updates[0]
        assert update.update_type == UpdateType.NODE_ADD
        assert update.data["id"] == "n1"
        assert update.data["name"] == "Node One"
        assert update.data["type"] == "person"
        assert update.data["description"] == "desc"
        assert update.data["properties"] == {"k": 1}
        assert "embedding" not in update.data

    def test_add_node_with_embedding(self, db_session):
        manager = DynamicGraphManager(make_config(batch_size=10))
        assert manager.add_node("ws1", "n1", "Node One", "person",
                                embedding=[0.5, 0.6], session=db_session) is True
        assert manager.update_manager.pending_updates[0].data["embedding"] == [0.5, 0.6]

    def test_add_node_none_properties_defaults_empty(self, db_session):
        manager = DynamicGraphManager(make_config(batch_size=10))
        manager.add_node("ws1", "n1", "Node One", "person", session=db_session)
        assert manager.update_manager.pending_updates[0].data["properties"] == {}

    def test_add_edge(self, db_session):
        manager = DynamicGraphManager(make_config(batch_size=10))
        assert manager.add_edge("ws1", "n1", "n2", "manages",
                                {"w": 1}, session=db_session) is True
        update = manager.update_manager.pending_updates[0]
        assert update.update_type == UpdateType.EDGE_ADD
        assert update.entity_id == "n1_n2"
        assert update.data["source_node_id"] == "n1"
        assert update.data["target_node_id"] == "n2"
        assert update.data["relationship_type"] == "manages"
        assert update.data["properties"] == {"w": 1}

    def test_add_edge_defaults(self, db_session):
        manager = DynamicGraphManager(make_config(batch_size=10))
        manager.add_edge("ws1", "n1", "n2", session=db_session)
        update = manager.update_manager.pending_updates[0]
        assert update.data["relationship_type"] == "related_to"
        assert update.data["properties"] == {}

    def test_delete_node(self, db_session):
        manager = DynamicGraphManager(make_config(batch_size=10))
        assert manager.delete_node("ws1", "n1", session=db_session) is True
        update = manager.update_manager.pending_updates[0]
        assert update.update_type == UpdateType.NODE_DELETE
        assert update.entity_id == "n1"
        assert update.data == {}

    def test_delete_edge(self, db_session):
        manager = DynamicGraphManager(make_config(batch_size=10))
        assert manager.delete_edge("ws1", "e1", session=db_session) is True
        update = manager.update_manager.pending_updates[0]
        assert update.update_type == UpdateType.EDGE_DELETE
        assert update.entity_id == "e1"

    def test_flush_delegates(self, db_session):
        manager = DynamicGraphManager()
        manager.update_manager.flush_updates = Mock(return_value=True)
        assert manager.flush("ws1", db_session) is True
        manager.update_manager.flush_updates.assert_called_once_with(
            "ws1", db_session)

    def test_create_version_delegates(self, db_session):
        manager = DynamicGraphManager()
        snapshot = GraphSnapshot(version_id="v_1", timestamp=datetime.now(),
                                 node_count=0, edge_count=0, hash="h")
        manager.version_manager.create_version = Mock(return_value=snapshot)
        result = manager.create_version("ws1", {"from": "test"}, db_session)
        assert result is snapshot
        manager.version_manager.create_version.assert_called_once_with(
            "ws1", db_session, {"from": "test"})

    def test_get_evolution_metrics_delegates(self, db_session):
        manager = DynamicGraphManager()
        manager.temporal_tracker.get_evolution_metrics = Mock(return_value={})
        assert manager.get_evolution_metrics("ws1", 12, db_session) == {}
        manager.temporal_tracker.get_evolution_metrics.assert_called_once_with(
            "ws1", 12, db_session)

    def test_end_to_end_node_lifecycle(self, db_session):
        manager = DynamicGraphManager(make_config(
            batch_size=1, batch_timeout_ms=0, enable_versioning=False))
        assert manager.add_node("ws1", "n1", "Alice", "person",
                                session=db_session) is True
        assert manager.add_node("ws1", "n2", "Bob", "person",
                                session=db_session) is True
        assert manager.add_edge("ws1", "n1", "n2", "colleague",
                                session=db_session) is True
        assert db_session.query(GraphNode).count() == 2
        assert db_session.query(GraphEdge).count() == 1
        assert manager.delete_node("ws1", "n1", session=db_session) is True
        assert db_session.query(GraphNode).count() == 1
        assert db_session.query(GraphEdge).count() == 0
        snapshot = manager.create_version("ws1", session=db_session)
        assert snapshot.node_count == 1


# ============================================================================
# Factory functions
# ============================================================================

class TestFactories:
    def test_get_dynamic_graph_manager(self):
        manager = get_dynamic_graph_manager()
        assert isinstance(manager, DynamicGraphManager)
        config = make_config(batch_size=3)
        assert get_dynamic_graph_manager(config).config is config

    def test_get_incremental_updater(self):
        updater = get_incremental_updater()
        assert isinstance(updater, IncrementalUpdateManager)
        config = make_config(batch_size=3)
        assert get_incremental_updater(config).config is config

    def test_get_version_manager(self):
        version_manager = get_version_manager()
        assert isinstance(version_manager, GraphVersionManager)
        config = make_config(batch_size=3)
        assert get_version_manager(config).config is config


def hashlib_sha256(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:16]
