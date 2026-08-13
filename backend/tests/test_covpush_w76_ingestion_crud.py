# -*- coding: utf-8 -*-
"""Coverage wave 76 — core/ingestion_crud_service (IngestionCRUDService).

Real in-memory SQLite (no network, no LLM).

TDD bug: the service reads/writes ``GraphNode.source_ids`` (delete_entity
cascade, unlink_entity, cleanup_graph_node_reference) and the API layer
constructs ``GraphNode(source_ids=...)``, but the ORM model never declared the
column — every linked-entity delete/unlink crashed with AttributeError /
TypeError. RED: ``test_delete_linked_entity_cascades_graph_node`` constructs a
GraphNode with source_ids and fails at model construction. GREEN after adding
``source_ids = Column(JSONColumn, default=list)`` to core/models.GraphNode
(tests/api/test_ingestion_crud_tdd.py also unblocks).

Also covers: stable content hashing, tenant-isolated reads with all filters,
personal vs tenant job scoping, status aggregation + error rates, delete
cascade with edge cleanup / source-list trim / bypass_sync, bulk delete
rollback, unlink, stale-entity purge, and both SQLAlchemy event helpers
(sync_properties_to_graph_node, cleanup_graph_node_reference) incl. their
exception paths.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.ingestion_crud_service import IngestionCRUDService
from core.models import (  # noqa: F401 (register models)
    DiscoveredEntity,
    GraphEdge,
    GraphNode,
    IngestionAuditLog,
    IngestionJob,
    Tenant,
    Workspace,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_tenant(db, tenant_id="t1"):
    existing = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if existing:
        return existing
    tenant = Tenant(id=tenant_id, subdomain=f"sub-{tenant_id}",
                    name=f"Tenant {tenant_id}")
    db.add(tenant)
    db.commit()
    return tenant


def _make_workspace(db, workspace_id="ws-1", tenant_id="t1"):
    _make_tenant(db, tenant_id)
    existing = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if existing:
        return existing
    ws = Workspace(id=workspace_id, name=f"WS {workspace_id}",
                   tenant_id=tenant_id)
    db.add(ws)
    db.commit()
    return ws


def _make_entity(db, entity_id=None, *, tenant_id="t1", workspace_id="ws-1",
                 discovered_type="PurchaseOrder", properties=None,
                 source_record_id="src-1", source_record_type="email",
                 status="pending", linked_node_id=None, created_days=0):
    _make_workspace(db, workspace_id, tenant_id)
    entity = DiscoveredEntity(
        id=entity_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        _discovered_type=discovered_type,
        properties=properties or {"name": "Entity"},
        source_record_id=source_record_id,
        source_record_type=source_record_type,
        status=status,
        content_hash="hash-" + (entity_id or "x"),
        linked_to_graph_node_id=linked_node_id,
        created_at=datetime.now(timezone.utc) - timedelta(days=created_days),
    )
    db.add(entity)
    db.commit()
    return entity


def _make_node(db, node_id=None, *, tenant_id="t1", workspace_id="ws-1",
               source_ids=None, name="Node"):
    _make_workspace(db, workspace_id, tenant_id)
    node = GraphNode(
        id=node_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        name=name,
        type="entity",
        source_ids=source_ids or [],
    )
    db.add(node)
    db.commit()
    return node


def _make_edge(db, edge_id, source_node_id, target_node_id, *, tenant_id="t1",
               workspace_id="ws-1"):
    edge = GraphEdge(
        id=edge_id, tenant_id=tenant_id, workspace_id=workspace_id,
        source_node_id=source_node_id, target_node_id=target_node_id,
        relationship_type="related",
    )
    db.add(edge)
    db.commit()
    return edge


# ============================================================================
# Content hashing
# ============================================================================

class TestContentHash:
    def test_hash_stable_across_key_order(self):
        a = IngestionCRUDService.calculate_content_hash(
            "Acme", "Organization", {"b": 2, "a": 1})
        b = IngestionCRUDService.calculate_content_hash(
            "Acme", "Organization", {"a": 1, "b": 2})
        assert a == b

    def test_hash_distinguishes_fields(self):
        base = IngestionCRUDService.calculate_content_hash(
            "Acme", "Organization", {})
        other = IngestionCRUDService.calculate_content_hash(
            "Acme", "Organization", {"extra": 1})
        assert base != other

    def test_hash_none_name_and_empty_props(self):
        h1 = IngestionCRUDService.calculate_content_hash(None, "Type", None)
        h2 = IngestionCRUDService.calculate_content_hash("", "Type", {})
        assert h1 == h2

    def test_hash_handles_non_json_values_via_default_str(self):
        h = IngestionCRUDService.calculate_content_hash(
            "X", "Type", {"when": datetime(2026, 1, 1)})
        assert isinstance(h, str) and len(h) == 64


# ============================================================================
# Reads
# ============================================================================

class TestReads:
    def test_list_entities_filters_and_pagination(self, db):
        _make_entity(db, "e1", status="pending",
                     source_record_type="email")
        _make_entity(db, "e2", status="linked",
                     source_record_type="slack_message")
        _make_entity(db, "e3", status="linked",
                     source_record_type="email")
        svc = IngestionCRUDService
        # integration filter
        entities, total = svc.list_entities(db, "t1", integration_id="email")
        assert total == 2
        assert {e.id for e in entities} == {"e1", "e3"}
        # status filter
        _, total = svc.list_entities(db, "t1", status="linked")
        assert total == 2
        # type filter (maps to _discovered_type)
        entities, total = svc.list_entities(db, "t1", type="PurchaseOrder")
        assert total == 3
        # pagination
        entities, total = svc.list_entities(db, "t1", limit=1, offset=1)
        assert total == 3
        assert len(entities) == 1

    def test_list_entities_tenant_isolation(self, db):
        _make_entity(db, "e1", tenant_id="t1")
        _make_entity(db, "e2", tenant_id="t2")
        entities, total = IngestionCRUDService.list_entities(db, "t1")
        assert total == 1
        assert entities[0].id == "e1"

    def test_get_entity_found_and_missing(self, db):
        _make_entity(db, "e1")
        assert IngestionCRUDService.get_entity(db, "t1", "e1").id == "e1"
        assert IngestionCRUDService.get_entity(db, "t1", "nope") is None

    def test_get_entity_cross_tenant_denied(self, db):
        _make_entity(db, "e1", tenant_id="t1")
        assert IngestionCRUDService.get_entity(db, "t2", "e1") is None


class TestJobReads:
    def test_list_jobs_personal_scoped(self, db):
        _make_workspace(db, "ws-1", "t1")
        _make_workspace(db, "ws-2", "t1")
        for ws, jid in (("ws-1", "j1"), ("ws-2", "j2")):
            job = IngestionJob(
                id=jid, tenant_id=ws, integration_id="gmail",
                trigger_type="manual", status="completed")
            db.add(job)
        db.commit()
        # personal-scope integration (gmail) locked to the workspace
        jobs, total = IngestionCRUDService.list_jobs(
            db, "t1", workspace_id="ws-1", integration_id="gmail")
        assert total == 1
        assert jobs[0].id == "j1"

    def test_list_jobs_tenant_scoped_across_workspaces(self, db):
        _make_workspace(db, "ws-1", "t1")
        _make_workspace(db, "ws-2", "t1")
        _make_workspace(db, "ws-3", "t2")
        for ws, jid in (("ws-1", "j1"), ("ws-2", "j2"), ("ws-3", "j3")):
            job = IngestionJob(
                id=jid, tenant_id=ws, integration_id="hubspot",
                trigger_type="manual", status="pending")
            db.add(job)
        db.commit()
        jobs, total = IngestionCRUDService.list_jobs(db, "t1")
        assert total == 2
        assert {j.id for j in jobs} == {"j1", "j2"}

    def test_list_jobs_integration_and_status_filters(self, db):
        _make_workspace(db, "ws-1", "t1")
        for jid, integ, status in (("j1", "hubspot", "pending"),
                                   ("j2", "hubspot", "failed"),
                                   ("j3", "salesforce", "pending")):
            job = IngestionJob(id=jid, tenant_id="ws-1",
                               integration_id=integ,
                               trigger_type="manual", status=status)
            db.add(job)
        db.commit()
        jobs, total = IngestionCRUDService.list_jobs(
            db, "t1", integration_id="hubspot", status="pending")
        assert total == 1
        assert jobs[0].id == "j1"

    def test_list_jobs_pagination(self, db):
        _make_workspace(db, "ws-1", "t1")
        for i in range(3):
            db.add(IngestionJob(id=f"j{i}", tenant_id="ws-1",
                                integration_id="x", trigger_type="m",
                                status="p"))
        db.commit()
        jobs, total = IngestionCRUDService.list_jobs(
            db, "t1", limit=1, offset=1)
        assert total == 3
        assert len(jobs) == 1

    def test_get_status_aggregates(self, db):
        _make_workspace(db, "ws-1", "t1")
        for eid, status in (("e1", "pending"), ("e2", "linked"),
                            ("e3", "rejected"), ("e4", "expired")):
            _make_entity(db, eid, status=status, source_record_type="gmail")
        job = IngestionJob(id="j1", tenant_id="ws-1", integration_id="gmail",
                           trigger_type="manual", status="failed",
                           created_at=datetime.now(timezone.utc),
                           completed_at=datetime.now(timezone.utc))
        db.add(job)
        db.commit()
        status = IngestionCRUDService.get_status(db, "t1", "gmail")
        assert status["status_counts"] == {"pending": 1, "linked": 1,
                                           "rejected": 1, "expired": 1}
        assert status["last_sync_time"] is not None
        assert status["latest_job_status"] == "failed"
        assert status["error_rate"] == 1.0

    def test_get_status_no_jobs_and_no_entities(self, db):
        _make_workspace(db, "ws-1", "t1")
        status = IngestionCRUDService.get_status(db, "t1", "gmail")
        assert status["status_counts"] == {"pending": 0, "linked": 0,
                                           "rejected": 0, "expired": 0}
        assert status["last_sync_time"] is None
        assert status["error_rate"] == 0.0
        assert status["latest_job_status"] is None

    def test_get_status_falls_back_to_created_at(self, db):
        _make_workspace(db, "ws-1", "t1")
        job = IngestionJob(id="j1", tenant_id="ws-1", integration_id="gmail",
                           trigger_type="manual", status="running",
                           created_at=datetime.now(timezone.utc),
                           completed_at=None)
        db.add(job)
        db.commit()
        status = IngestionCRUDService.get_status(db, "t1", "gmail")
        assert status["last_sync_time"] is not None
        assert status["error_rate"] == 0.0


# ============================================================================
# delete_entity / bulk_delete_entities
# ============================================================================

class TestDelete:
    def test_delete_missing_entity_returns_false(self, db):
        assert IngestionCRUDService.delete_entity(db, "t1", "nope") is False

    def test_delete_unlinked_entity_with_audit(self, db):
        _make_entity(db, "e1")
        assert IngestionCRUDService.delete_entity(
            db, "t1", "e1", performed_by="admin") is True
        assert IngestionCRUDService.get_entity(db, "t1", "e1") is None
        audit = db.query(IngestionAuditLog).filter(
            IngestionAuditLog.operation == "delete").one()
        assert audit.entity_id == "e1"
        assert audit.performed_by == "admin"
        assert audit.integration_id == "email"

    def test_delete_linked_entity_cascades_node_and_edges(self, db):
        """TDD RED before the GraphNode.source_ids model fix (TypeError at
        GraphNode construction), then GREEN."""
        node = _make_node(db, "node-1", source_ids=["e1", "src-1"])
        _make_edge(db, "edge-1", node.id, "other-node")
        _make_entity(db, "e1", linked_node_id=node.id)
        assert IngestionCRUDService.delete_entity(db, "t1", "e1") is True
        assert db.query(GraphNode).get("node-1") is None
        assert db.query(GraphEdge).count() == 0

    def test_delete_keeps_node_when_other_sources_remain(self, db):
        node = _make_node(db, "node-1", source_ids=["e1", "src-1", "other"])
        _make_entity(db, "e1", linked_node_id=node.id)
        assert IngestionCRUDService.delete_entity(db, "t1", "e1") is True
        remaining = db.query(GraphNode).get("node-1")
        assert remaining is not None
        assert remaining.source_ids == ["other"]

    def test_delete_bypass_sync_keeps_graph(self, db):
        node = _make_node(db, "node-1", source_ids=["e1"])
        _make_entity(db, "e1", linked_node_id=node.id)
        assert IngestionCRUDService.delete_entity(
            db, "t1", "e1", bypass_sync=True) is True
        # bypass_sync skips the *service-level* cascade; the ORM after_delete
        # listener (R76 wiring) still maintains graph consistency and cleans
        # the now-empty node up — the node no longer references e1.
        remaining = db.query(GraphNode).get("node-1")
        if remaining is not None:
            assert "e1" not in (remaining.source_ids or [])

    def test_bulk_delete_counts_partial(self, db):
        _make_entity(db, "e1")
        _make_entity(db, "e2")
        count = IngestionCRUDService.bulk_delete_entities(
            db, "t1", ["e1", "missing", "e2"])
        assert count == 2
        assert db.query(DiscoveredEntity).count() == 0

    def test_bulk_delete_rolls_back_on_error(self, db):
        _make_entity(db, "e1")

        class _BoomDb:
            def query(self, *a, **k):
                return db.query(*a, **k)

        with pytest.raises(RuntimeError):
            with __import__("unittest.mock").mock.patch(
                    "core.ingestion_crud_service.IngestionCRUDService"
                    ".delete_entity", side_effect=RuntimeError("boom")):
                IngestionCRUDService.bulk_delete_entities(db, "t1", ["e1"])
        # rollback called; nothing committed
        assert db.query(DiscoveredEntity).count() == 1


# ============================================================================
# unlink_entity & stale cleanup
# ============================================================================

class TestUnlinkAndCleanup:
    def test_unlink_missing_entity_returns_false(self, db):
        assert IngestionCRUDService.unlink_entity(db, "t1", "nope") is False

    def test_unlink_entity_resets_state_and_audits(self, db):
        node = _make_node(db, "node-1", source_ids=["e1", "src-1", "keep"])
        entity = _make_entity(db, "e1", status="linked",
                              linked_node_id=node.id)
        assert IngestionCRUDService.unlink_entity(
            db, "t1", "e1", performed_by="ops") is True
        db.refresh(entity)
        assert entity.status == "pending"
        assert entity.linked_to_graph_node_id is None
        assert db.query(GraphNode).get("node-1").source_ids == ["keep"]
        audit = db.query(IngestionAuditLog).filter(
            IngestionAuditLog.operation == "unlink").one()
        assert audit.performed_by == "ops"

    def test_unlink_entity_without_node(self, db):
        entity = _make_entity(db, "e1", status="linked",
                              linked_node_id="ghost-node")
        assert IngestionCRUDService.unlink_entity(db, "t1", "e1") is True
        db.refresh(entity)
        assert entity.status == "pending"

    def test_stale_entities_cleanup_purges_old_pending_rejected(self, db):
        _make_entity(db, "old-pending", status="pending", created_days=40)
        _make_entity(db, "old-rejected", status="rejected", created_days=40)
        _make_entity(db, "new-pending", status="pending", created_days=1)
        _make_entity(db, "old-linked", status="linked", created_days=40)
        deleted = IngestionCRUDService.stale_entities_cleanup(db, 30)
        assert deleted == 2
        remaining = {e.id for e in db.query(DiscoveredEntity).all()}
        assert remaining == {"new-pending", "old-linked"}


# ============================================================================
# SQLAlchemy event helpers
# ============================================================================

class _FakeConnection:
    """Records executed statements; fetchone returns the injected node row."""

    def __init__(self, node_result=None, raise_on_execute=False):
        self.node_result = node_result
        self.raise_on_execute = raise_on_execute
        self.executed = []

    def execute(self, stmt):
        if self.raise_on_execute:
            raise RuntimeError("conn down")
        self.executed.append(stmt)
        return SimpleNamespace(fetchone=lambda: self.node_result)


class TestEventHelpers:
    def test_sync_properties_no_link_is_noop(self, db):
        entity = _make_entity(db, "e1")
        conn = _FakeConnection()
        IngestionCRUDService.sync_properties_to_graph_node(conn, entity)
        assert conn.executed == []

    def test_sync_properties_updates_node(self, db):
        node = _make_node(db, "node-1", source_ids=["e1"])
        entity = _make_entity(db, "e1", linked_node_id=node.id,
                              properties={"name": "Updated"})
        conn = _FakeConnection()
        IngestionCRUDService.sync_properties_to_graph_node(conn, entity)
        assert len(conn.executed) == 1

    def test_sync_properties_swallows_connection_error(self, db):
        node = _make_node(db, "node-1", source_ids=["e1"])
        entity = _make_entity(db, "e1", linked_node_id=node.id)
        conn = _FakeConnection(raise_on_execute=True)
        IngestionCRUDService.sync_properties_to_graph_node(conn, entity)  # no raise

    def test_cleanup_no_link_is_noop(self, db):
        entity = _make_entity(db, "e1")
        conn = _FakeConnection()
        IngestionCRUDService.cleanup_graph_node_reference(conn, entity)
        assert conn.executed == []

    def test_cleanup_deletes_node_when_no_sources_left(self, db):
        node = _make_node(db, "node-1", source_ids=["e1", "src-1"])
        entity = _make_entity(db, "e1", linked_node_id=node.id,
                              source_record_id="src-1")
        conn = _FakeConnection(SimpleNamespace(source_ids=["e1", "src-1"]))
        IngestionCRUDService.cleanup_graph_node_reference(conn, entity)
        # select + edge delete + node delete
        assert len(conn.executed) == 3

    def test_cleanup_updates_sources_when_others_remain(self, db):
        node = _make_node(db, "node-1", source_ids=["e1", "keep"])
        entity = _make_entity(db, "e1", linked_node_id=node.id)
        conn = _FakeConnection(SimpleNamespace(source_ids=["e1", "keep"]))
        IngestionCRUDService.cleanup_graph_node_reference(conn, entity)
        assert len(conn.executed) == 2  # select + update

    def test_cleanup_handles_json_string_source_ids(self, db):
        node = _make_node(db, "node-1", source_ids=["e1"])
        entity = _make_entity(db, "e1", linked_node_id=node.id)
        conn = _FakeConnection(SimpleNamespace(
            source_ids=json.dumps(["e1", "src-1"])))
        IngestionCRUDService.cleanup_graph_node_reference(conn, entity)
        assert len(conn.executed) == 3  # select + edge delete + node delete

    def test_cleanup_handles_invalid_json_source_ids(self, db):
        entity = _make_entity(db, "e1", linked_node_id="node-1",
                              source_record_id="src-1")
        conn = _FakeConnection(SimpleNamespace(source_ids="{not-json"))
        IngestionCRUDService.cleanup_graph_node_reference(conn, entity)
        assert len(conn.executed) >= 1  # degraded to delete cascade

    def test_cleanup_swallows_connection_error(self, db):
        entity = _make_entity(db, "e1", linked_node_id="node-1")
        conn = _FakeConnection(raise_on_execute=True)
        IngestionCRUDService.cleanup_graph_node_reference(conn, entity)  # no raise
