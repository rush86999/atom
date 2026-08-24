"""Round 83 — integration → ontology path repair.

The path integration records → GraphRAGEngine.ingest_structured_data →
ontology was severed at every producer. These tests pin each fix:

1. arg-shift: knowledge_ingestion passed (ws, entities, relationships)
   positionally into (workspace_id, tenant_id, entities, relationships) —
   entities landed in tenant_id and every relationship was silently dropped.
2. _normalize_extractor_output was called but never defined → NameError on
   every process_document (the whole knowledge_ingestion path was dead).
3. historical_sync passed Entity/Relationship dataclasses where dicts were
   expected → AttributeError inside the engine catch-all → silent data loss.
4. microsoft365_learner relationships used "source"/"target" keys — every
   Outlook relationship was silently dropped (endpoints read from
   "from"/"to").
5. ingestion_pipeline synced_from edges pointed at an integration_id entity
   that was never created → every edge dangled.
6. ontology singleton ignored tenant_id after the first call.
7. ingest_document returned None → sync results always reported 0 extracted.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1 + 2: knowledge_ingestion
# ---------------------------------------------------------------------------

class TestKnowledgeIngestion:
    def test_normalize_extractor_output_promotes_nested_names(self):
        from core.knowledge_ingestion import _normalize_extractor_output

        entities = [
            {"id": "e1", "type": "Person", "properties": {"name": "Alice", "role": "CEO"}},
            {"id": "e2", "type": "Organization", "properties": {"name": "Acme"}},
        ]
        rels = [{"from": "e1", "to": "e2", "type": "WORKS_AT", "properties": {}}]

        ents, rels_out = _normalize_extractor_output(entities, rels)
        assert ents[0]["name"] == "Alice"
        assert ents[0]["type"] == "Person"
        assert ents[0]["properties"]["role"] == "CEO"
        # id-keyed endpoints remapped to names
        assert rels_out == [{"from": "Alice", "to": "Acme", "type": "WORKS_AT", "properties": {}}]

    def test_normalize_skips_unresolvable(self):
        from core.knowledge_ingestion import _normalize_extractor_output

        ents, rels = _normalize_extractor_output(
            [{"id": "x", "type": "Person", "properties": {}}],
            [{"from": None, "to": "x", "type": "KNOWS"}],
        )
        assert len(ents) == 1
        assert rels == []  # unresolvable/None endpoints dropped, not dangled

    @pytest.mark.asyncio
    async def test_process_document_keyword_args_no_arg_shift(self):
        """ingest_structured_data must receive entities/relationships by keyword."""
        from core import knowledge_ingestion as kng

        manager = kng.KnowledgeIngestionManager.__new__(kng.KnowledgeIngestionManager)
        manager.workspace_id = None
        manager.graphrag = MagicMock()
        manager.graphrag.ingest_structured_data = MagicMock(
            return_value={"entities": 2, "relationships": 1})
        manager.extractor = MagicMock()
        manager.extractor.extract_knowledge = AsyncMock(return_value={
            "entities": [
                {"id": "e1", "type": "Person", "properties": {"name": "Alice"}},
                {"id": "e2", "type": "Organization", "properties": {"name": "Acme"}},
            ],
            "relationships": [{"from": "e1", "to": "e2", "type": "WORKS_AT"}],
        })
        handler = MagicMock()
        handler.add_knowledge_edge.return_value = True
        with patch.object(kng, "get_lancedb_handler", return_value=handler), \
                patch.object(kng, "get_automation_settings") as settings_fn:
            settings_fn.return_value.get_settings.return_value = {}
            result = await manager.process_document(
                "text", "doc1", source="gmail", user_id="u1", workspace_id="ws1")

        kwargs = manager.graphrag.ingest_structured_data.call_args.kwargs
        assert kwargs["workspace_id"] == "ws1"
        assert kwargs["tenant_id"] == "ws1"
        # Entities normalized to named dicts, relationships survive intact.
        assert [e["name"] for e in kwargs["entities"]] == ["Alice", "Acme"]
        assert len(kwargs["relationships"]) == 1
        assert result["graphrag"] == {"entities": 2, "relationships": 1}


# ---------------------------------------------------------------------------
# 3: graphrag engine tolerates dataclass producers
# ---------------------------------------------------------------------------

class TestDataclassTolerance:
    def test_ingest_structured_data_accepts_dataclasses(self, tmp_path, monkeypatch):
        """Entity/Relationship-shaped objects must not crash the batch."""
        from core.graphrag_engine import GraphRAGEngine

        engine = GraphRAGEngine.__new__(GraphRAGEngine)
        engine.workspace_id = "ws"
        engine.tenant_id = "t"

        entity = SimpleNamespace(
            id="n1", name="Alice", entity_type="Person",
            description="desc", properties={"a": 1})
        rel = SimpleNamespace(
            id="r1", from_entity="Alice", to_entity="Acme",
            rel_type="WORKS_AT", description="", properties={})

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        # Both entities as dataclasses; rel endpoints by NAME.
        ent_acme = SimpleNamespace(
            id="n2", name="Acme", entity_type="Organization",
            description="", properties={})

        with patch("core.graphrag_engine.get_db_session") as dbs:
            dbs.return_value.__enter__ = lambda s: session
            dbs.return_value.__exit__ = lambda s, *a: False
            stats = engine.ingest_structured_data(
                workspace_id="ws", tenant_id="t",
                entities=[entity, ent_acme], relationships=[rel])

        assert stats.get("entities", 0) >= 2
        assert stats.get("relationships", 0) >= 1


# ---------------------------------------------------------------------------
# 4: microsoft365_learner relationship keys
# ---------------------------------------------------------------------------

class TestM365RelationshipKeys:
    def test_outlook_relationships_use_from_to(self):
        from core.microsoft365_learner import Microsoft365LifecycleLearner

        learner = Microsoft365LifecycleLearner.__new__(Microsoft365LifecycleLearner)
        entities, rels = learner._build_entities(
            subject="Invoice INV-123 attached",
            from_email="a@b.com",
            from_name="Alice",
            received="2026-01-01T00:00:00Z",
            matched_keywords=["invoice", "tracking"],
            order_ids=["INV-123"],
            tracking_ids=["1Z999AA1"],
            amounts=["$100"],
            body_preview="Invoice INV-123 attached. Tracking 1Z999AA1.",
            message_id="msg-1",
        )
        assert rels, "expected at least one relationship"
        for r in rels:
            assert "from" in r and "to" in r, f"legacy source/target keys leaked: {r}"
            assert "source" not in r and "target" not in r


# ---------------------------------------------------------------------------
# 5: ingestion_pipeline synced_from has a real target entity
# ---------------------------------------------------------------------------

class TestSyncedFromTarget:
    def test_extract_structured_entities_returns_integration_entity(self):
        from core.ingestion_pipeline import IngestionPipelineService

        svc = IngestionPipelineService.__new__(IngestionPipelineService)
        entity, rel, integ = svc._extract_structured_entities(
            {"id": "r1", "type": "contact", "name": "Bob", "email": "b@c.com"},
            "salesforce",
            "contact Bob b@c.com",
        )
        assert integ["name"] == "salesforce"
        assert rel["to"] == "salesforce" == integ["name"]


# ---------------------------------------------------------------------------
# 6: per-tenant ontology service
# ---------------------------------------------------------------------------

class TestOntologyPerTenant:
    def test_tenants_get_distinct_services(self):
        from core.ontology.ontology_service import _services_by_tenant, get_ontology_service

        a = get_ontology_service("tenant-a")
        b = get_ontology_service("tenant-b")
        assert a is not b
        assert _services_by_tenant["tenant-a"] is a
        assert _services_by_tenant["tenant-b"] is b
        # same tenant returns the cached instance
        assert get_ontology_service("tenant-a") is a


# ---------------------------------------------------------------------------
# 7: ingest_document returns stats
# ---------------------------------------------------------------------------

class TestIngestDocumentStats:
    @pytest.mark.asyncio
    async def test_empty_extraction_returns_zero_stats(self):
        from core.graphrag_engine import GraphRAGEngine

        engine = GraphRAGEngine.__new__(GraphRAGEngine)
        engine.workspace_id = "ws"
        engine.tenant_id = "t"
        with patch.object(engine, "_is_llm_available", return_value=False), \
                patch.object(engine, "_pattern_extract_entities_and_relationships",
                             return_value=([], [])):
            stats = await engine.ingest_document("ws", "t", doc_id="d", text="x")
        assert stats == {"entities": 0, "relationships": 0}

    @pytest.mark.asyncio
    async def test_success_returns_ingest_stats(self):
        from core.graphrag_engine import GraphRAGEngine

        engine = GraphRAGEngine.__new__(GraphRAGEngine)
        engine.workspace_id = "ws"
        engine.tenant_id = "t"
        e = SimpleNamespace(name="Alice", entity_type="Person", description="",
                            properties={}, sensitivity=None)
        with patch.object(engine, "_is_llm_available", return_value=False), \
                patch.object(engine, "_pattern_extract_entities_and_relationships",
                             return_value=([e], [])), \
                patch.object(engine, "ingest_structured_data",
                             return_value={"entities": 1, "relationships": 0}) as mock_isd:
            stats = await engine.ingest_document("ws", "t", doc_id="d", text="Alice")
        assert stats == {"entities": 1, "relationships": 0}
        assert mock_isd.call_args.args[0] == "ws"
