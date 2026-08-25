"""Org Memory Bundle (Phase 2b) — GraphRAG + raw text sharing.

Graph export sensitivity filter + edge both-endpoint rule, node upsert/merge
policy (sensitivity never lowered), edge remap without stub nodes, knowledge
documents + business facts round-trip, v1 envelope backward compatibility,
section counts, community recompute trigger.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import org_sharing_crypto
from core.ingestion_profile_service import canonical_payload, payload_hash
from core.models import (
    Base,
    BundleExport,
    BundleImport,
    GraphEdge,
    GraphNode,
    KnowledgeDocument,
    OrgPublicKey,
)
from core.org_data_bundle_service import BundleError, OrgDataBundleService

TABLES = [
    GraphNode.__table__,
    GraphEdge.__table__,
    KnowledgeDocument.__table__,
    BundleExport.__table__,
    BundleImport.__table__,
    OrgPublicKey.__table__,
]


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(tmp_path / "org_sharing_key"))


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def add_node(db, name, type_, sensitivity="internal", description="", updated=None, workspace="default"):
    node = GraphNode(
        workspace_id=workspace, tenant_id="default", name=name, type=type_,
        description=description, properties={}, sensitivity=sensitivity,
        updated_at=updated,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def add_edge(db, src, tgt, rel="related_to", workspace="default"):
    db.add(GraphEdge(
        workspace_id=workspace, tenant_id="default",
        source_node_id=src.id, target_node_id=tgt.id, relationship_type=rel,
    ))
    db.commit()


def make_handler(facts=None):
    handler = MagicMock()
    handler.list_documents.return_value = facts or []
    return handler


class TestGraphExport:
    async def test_nodes_filtered_by_sensitivity(self, key_file, db):
        add_node(db, "Acme", "organization")
        add_node(db, "SecretPerson", "person", sensitivity="restricted")
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()):
            env = OrgDataBundleService().build_bundle(db, "default", sources=[], include=["graph"])
        nodes = env["payload"]["graph"]["nodes"]
        names = {n["name"] for n in nodes}
        assert names == {"Acme"}
        assert "embedding" not in nodes[0]  # derived vectors never exported

    async def test_edge_dropped_when_endpoint_filtered(self, key_file, db):
        acme = add_node(db, "Acme", "organization")
        hr = add_node(db, "HRFile", "document", sensitivity="restricted")
        add_edge(db, acme, hr, rel="mentions")
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()):
            env = OrgDataBundleService().build_bundle(db, "default", sources=[], include=["graph"])
        assert env["payload"]["graph"]["edges"] == []  # HRFile excluded → edge must not leak it

    async def test_raised_ceiling_includes_restricted_graph(self, key_file, db):
        add_node(db, "HRFile", "document", sensitivity="restricted")
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()):
            env = OrgDataBundleService().build_bundle(
                db, "default", sources=[], include=["graph"], sensitivity_ceiling="restricted")
        assert {n["name"] for n in env["payload"]["graph"]["nodes"]} == {"HRFile"}

    async def test_include_validation(self, key_file, db):
        with pytest.raises(BundleError, match="Unknown bundle sections"):
            OrgDataBundleService().build_bundle(db, "default", sources=[], include=["nonsense"])


class TestGraphImport:
    async def test_round_trip_nodes_and_edges(self, key_file, db):
        a = add_node(db, "Acme", "organization", description="CRM account")
        b = add_node(db, "Alice", "person", description="Contact")
        add_edge(db, b, a, rel="works_at")
        svc = OrgDataBundleService()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()):
            env = svc.build_bundle(db, "default", sources=[], include=["graph"])

        engine2 = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine2, tables=TABLES)
        db2 = sessionmaker(bind=engine2)()
        engine_mock = MagicMock()
        engine_mock.build_communities.return_value = {"success": True, "communities": 1}
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()), \
             patch("core.graphrag_engine.GraphRAGEngine", return_value=engine_mock):
            result = await svc.apply_bundle(db2, env, workspace_id="member-b", tenant_id="t")

        assert result["graph"]["nodes_ingested"] == 2
        assert result["graph"]["edges_ingested"] == 1
        node = db2.query(GraphNode).filter_by(name="Alice").one()
        assert node.description == "Contact"
        edge = db2.query(GraphEdge).one()
        assert edge.relationship_type == "works_at"
        # Community recompute was triggered for the merged graph.
        engine_mock.build_communities.assert_called_once_with("member-b")
        assert result["communities_rebuilt"] is True
        db2.close()

    async def test_unresolved_edge_skipped_no_stub_nodes(self, key_file, db):
        # Local graph has only Acme; the bundle references Alice→Acme.
        add_node(db, "Acme", "organization")
        payload_nodes = [
            {"key": ["Acme", "organization"], "name": "Acme", "type": "organization",
             "description": "", "properties": {}, "sensitivity": "internal",
             "source_updated_at": None, "content_hash": "x"},
        ]
        payload_edges = [
            {"source_key": ["Alice", "person"], "target_key": ["Acme", "organization"],
             "relationship_type": "works_at", "weight": 1.0, "properties": {}},
        ]
        svc = OrgDataBundleService()
        payload = {"kind": "atom_org_data_bundle", "bundle_version": 2,
                   "graph": {"nodes": payload_nodes, "edges": payload_edges}}
        envelope = {"kind": "atom_org_data_bundle", "payload": payload}
        envelope["payload_hash"] = payload_hash(payload)
        envelope["signature"], envelope["signed_by"] = org_sharing_crypto.sign_payload(canonical_payload(payload))

        result = svc._apply_graph_section(db, payload["graph"], "default", "default")
        assert result["edges_skipped_unresolved"] == 1
        assert result["edges_ingested"] == 0
        assert db.query(GraphNode).count() == 1  # no "Alice" stub was fabricated

    async def test_merge_policy_sensitivity_never_lowered(self, key_file, db):
        # Local node classified restricted, bundle claims internal.
        local = add_node(db, "Acme", "organization", sensitivity="restricted",
                         description="old", updated=datetime(2026, 1, 1, tzinfo=timezone.utc))
        svc = OrgDataBundleService()
        graph = {"nodes": [
            {"key": ["Acme", "organization"], "name": "Acme", "type": "organization",
             "description": "new from bundle", "properties": {}, "sensitivity": "internal",
             "source_updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
             "content_hash": "x"},
        ], "edges": []}
        svc._apply_graph_section(db, graph, "default", "default")
        db.refresh(local)
        assert local.sensitivity == "restricted"  # raised, never lowered
        assert local.description == "new from bundle"  # bundle is newer → wins

    async def test_merge_policy_local_newer_keeps_description(self, key_file, db):
        local = add_node(db, "Acme", "organization", description="local truth",
                         updated=datetime(2026, 8, 15, tzinfo=timezone.utc))
        svc = OrgDataBundleService()
        graph = {"nodes": [
            {"key": ["Acme", "organization"], "name": "Acme", "type": "organization",
             "description": "stale bundle", "properties": {}, "sensitivity": "internal",
             "source_updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
             "content_hash": "x"},
        ], "edges": []}
        svc._apply_graph_section(db, graph, "default", "default")
        db.refresh(local)
        assert local.description == "local truth"


class TestTextsSection:
    async def test_knowledge_documents_round_trip_and_dedup(self, key_file, db):
        db.add(KnowledgeDocument(tenant_id="default", workspace_id="default",
                                 title="Handbook", content="Be kind", sensitivity="internal"))
        db.add(KnowledgeDocument(tenant_id="default", workspace_id="default",
                                 title="Secret", content="payroll", sensitivity="restricted"))
        db.commit()
        svc = OrgDataBundleService()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()):
            env = svc.build_bundle(db, "default", sources=[], include=["texts"])
        docs = env["payload"]["texts"]["knowledge_documents"]
        assert [d["title"] for d in docs] == ["Handbook"]  # restricted excluded

        engine2 = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine2, tables=TABLES)
        db2 = sessionmaker(bind=engine2)()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()):
            r1 = await svc.apply_bundle(db2, env, workspace_id="member-b", tenant_id="default")
            r2 = await svc.apply_bundle(db2, env, workspace_id="member-b", tenant_id="default")
        assert r1["texts"]["knowledge_ingested"] == 1
        assert r2["texts"]["knowledge_skipped"] == 1  # dedup on identical content
        assert db2.query(KnowledgeDocument).count() == 1
        db2.close()

    async def test_business_facts_export_and_import(self, key_file, db):
        facts = [{"id": "fact-1", "text": "Acme renewed for 3 years",
                  "metadata": {"sensitivity": "internal", "type": "business_fact"}}]
        handler = make_handler(facts)
        svc = OrgDataBundleService()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            env = svc.build_bundle(db, "default", sources=[], include=["texts"])
        exported = env["payload"]["texts"]["business_facts"]
        assert len(exported) == 1 and exported[0]["fact_id"] == "fact-1"

        import_handler = MagicMock()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=import_handler):
            result = await svc.apply_bundle(db, env, workspace_id="member-b", tenant_id="default")
        assert result["texts"]["facts_ingested"] == 1
        import_handler.add_document.assert_called_once()
        kwargs = import_handler.add_document.call_args.kwargs
        assert kwargs["table_name"] == "business_facts"
        assert kwargs["doc_id"] == "orgbundle:fact-1"  # deterministic → idempotent
        assert "extract_knowledge" not in kwargs  # dead param removed (R84)

    async def test_restricted_fact_excluded(self, key_file, db):
        facts = [{"id": "f", "text": "salary data", "metadata": {"sensitivity": "restricted"}}]
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler(facts)):
            env = OrgDataBundleService().build_bundle(db, "default", sources=[], include=["texts"])
        assert env["payload"]["texts"]["business_facts"] == []


class TestVersionCompatAndAudit:
    async def test_v1_envelope_still_imports(self, key_file, db):
        svc = OrgDataBundleService()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()):
            env = svc.build_bundle(db, "default", sources=[], include=[])
        # Downgrade to a v1-shaped envelope (records only) and re-sign.
        payload = env["payload"]
        payload["bundle_version"] = 1
        payload.pop("graph", None)
        payload.pop("texts", None)
        envelope = {"kind": "atom_org_data_bundle", "payload": payload}
        envelope["payload_hash"] = payload_hash(payload)
        envelope["signature"], envelope["signed_by"] = org_sharing_crypto.sign_payload(canonical_payload(payload))
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()):
            result = await svc.apply_bundle(db, envelope, workspace_id="default")
        assert result["records_total"] == 0  # accepted, records-only semantics

    async def test_section_counts_audited(self, key_file, db):
        a = add_node(db, "Acme", "organization")
        b = add_node(db, "Alice", "person")
        add_edge(db, b, a, rel="works_at")
        svc = OrgDataBundleService()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()):
            env = svc.build_bundle(db, "default", sources=[], include=["graph"])
        export_row = db.query(BundleExport).one()
        assert export_row.section_counts["nodes"] == 2
        assert export_row.section_counts["edges"] == 1
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=make_handler()), \
             patch("core.graphrag_engine.GraphRAGEngine", return_value=MagicMock(
                 **{"build_communities.return_value": {"success": False}})):
            await svc.apply_bundle(db, env, workspace_id="member-b", tenant_id="default")
        import_row = db.query(BundleImport).one()
        assert import_row.section_counts["nodes_ingested"] == 2
