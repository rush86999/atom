"""
TDD bug-hunt tests for the data-ingestion/federation module set.

RED -> GREEN targets (bugs found while reading the sources):

A. graphrag_engine.canonical_search / _resolve_canonical_entity read the
   registry key "search_fields" (plural) and "display_field", but the real
   registry entries (_get_entity_registry) define "search_field" (singular)
   only. With the default ["name"] fallback the User model's `name` Python
   property is used in an .ilike() expression -> AttributeError
   ('property' object has no attribute 'ilike') -> canonical_search always
   returns [] and add_entity silently drops the canonical link.

B. historical_sync_service._extract_chunk_and_ingest calls
   GraphRAGEngine.ingestion_pipeline_batch(...) and GraphRAGEngine.close()
   which do not exist -> every historical sync chunk raises AttributeError
   at the ingest phase and the job is marked failed.

C. hybrid_data_ingestion.sync_integration_data calls
   self.graphrag.ingest_document(...) (an async coroutine) without awaiting
   it; the truthy coroutine then fails on .get("entities") -> one error per
   record, so every sync that has GraphRAG enabled is marked partial/failed.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.graphrag_engine import Entity, GraphRAGEngine, Relationship
from core.historical_sync_service import HistoricalSyncService


class _FakeSession:
    """Minimal stand-in for a SQLAlchemy session used by mocked services."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.closed = False

    def query(self, model):
        return _FakeQuery(self.rows, model)

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def add(self, obj):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


class _FakeQuery:
    def __init__(self, rows, model):
        self.rows = rows
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def limit(self, n):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


def _patch_db_session(rows=None):
    return patch("core.graphrag_engine.get_db_session", return_value=rows)


# ============================================================================
# A. canonical_search with the REAL entity registry
# ============================================================================

class TestCanonicalSearchRealRegistry:
    def test_user_search_uses_singular_search_field(self):
        """The real 'user' registry entry defines search_field='email'; the
        default ['name'] fallback hits the User.name Python property and
        crashes. Searching must return the matched record."""
        from core.models import User

        rec = MagicMock()
        rec.id = "user-1"
        rec.email = "alice@example.com"
        sess = _FakeSession([rec])

        engine = GraphRAGEngine(workspace_id="ws1", tenant_id="t1")
        with patch.object(
            engine, "_get_registry_entry", side_effect=engine._get_registry_entry
        ), patch("core.graphrag_engine.get_db_session", return_value=sess):
            # entity_type="user" resolves through the REAL registry
            result = engine.canonical_search(
                workspace_id="ws1", entity_type="user", query="alice"
            )
        assert result == [{"id": "user-1", "name": "alice@example.com"}]

    def test_resolve_canonical_entity_uses_singular_search_field(self):
        """_resolve_canonical_entity must look up 'search_field' (singular),
        not the missing 'display_field' key (default 'name' -> User.name
        property crash)."""
        from core.models import User

        rec = MagicMock()
        rec.id = "user-1"
        rec.email = "alice@example.com"
        sess = _FakeSession([rec])

        engine = GraphRAGEngine(workspace_id="ws1", tenant_id="t1")
        with patch.object(
            engine, "_get_registry_entry", side_effect=engine._get_registry_entry
        ):
            # matches via search_field="email"
            result = engine._resolve_canonical_entity(sess, "ws1", "alice@example.com", "user")
        assert result == "user-1"


# ============================================================================
# B. historical sync chunk ingestion uses existing GraphRAGEngine methods
# ============================================================================

class TestHistoricalSyncChunkIngestion:
    @pytest.mark.asyncio
    async def test_extract_chunk_and_ingest_uses_ingest_structured_data(self):
        """_extract_chunk_and_ingest must ingest through the methods that
        actually exist on GraphRAGEngine (ingest_structured_data) and must
        not call the phantom ingestion_pipeline_batch()/close()."""

        class FakeEngine:
            def __init__(self, *a, **kw):
                self.calls = []

            def ingest_structured_data(self, **kwargs):
                self.calls.append(("ingest_structured_data", kwargs))
                return {"entities": 1, "relationships": 1}

        fake_engine = FakeEngine()

        service = HistoricalSyncService(tenant_id="t1", db=_FakeSession())
        records = [
            ("doc-1", "Alice works at Acme Corp and leads the sales team.", "salesforce"),
            ("doc-2", "Bob handles support tickets at Acme Corp.", "salesforce"),
        ]
        fake_entities = [Entity(id=str(uuid.uuid4()), name="Alice", entity_type="person")]
        fake_rels = [Relationship(id=str(uuid.uuid4()), from_entity="x", to_entity="y", rel_type="works_at")]

        with patch("core.historical_sync_service.SessionLocal", return_value=_FakeSession()), \
             patch("core.graphrag_engine.GraphRAGEngine", return_value=fake_engine) as eng_cls, \
             patch(
                 "core.historical_sync_service._llm_extract_with_handler",
                 new=AsyncMock(return_value=(fake_entities, fake_rels)),
             ):
            entities, rels = await service._extract_chunk_and_ingest(
                job_id="job-1", chunk_count=0, llm_task_records=records,
                workspace_id="ws1", integration_id="salesforce",
            )

        assert entities == 2
        assert rels == 2
        assert len(fake_engine.calls) == 2, "ingest_structured_data must be called per extracted chunk"
        method, kwargs = fake_engine.calls[0]
        assert method == "ingest_structured_data"
        # R83: dataclass Entity/Relationship objects must be serialized to the
        # plain-dict shape — raw dataclasses raised AttributeError inside the
        # engine's catch-all and silently discarded the whole chunk.
        assert kwargs["entities"] == [
            {"name": "Alice", "type": "person", "description": "", "properties": {}}
        ]
        assert kwargs["relationships"] == [
            {"from": "x", "to": "y", "type": "works_at", "properties": {}}
        ]

    @pytest.mark.asyncio
    async def test_extract_chunk_failure_propagates(self):
        """If LLM extraction fails for every record, the chunk must return
        (0, 0) rather than crash on missing GraphRAGEngine methods."""

        class FakeEngine:
            def __init__(self, *a, **kw):
                pass

        service = HistoricalSyncService(tenant_id="t1", db=_FakeSession())
        with patch("core.historical_sync_service.SessionLocal", return_value=_FakeSession()), \
             patch("core.graphrag_engine.GraphRAGEngine", return_value=FakeEngine()), \
             patch(
                 "core.historical_sync_service._llm_extract_with_handler",
                 new=AsyncMock(return_value=([], [])),
             ):
            entities, rels = await service._extract_chunk_and_ingest(
                job_id="job-2", chunk_count=0,
                llm_task_records=[("doc-1", "some text here", "salesforce")],
                workspace_id="ws1",
            )
        assert entities == 0 and rels == 0


# ============================================================================
# C. hybrid sync must await graphrag.ingest_document
# ============================================================================

class TestHybridSyncAwaitsGraphrag:
    @pytest.mark.asyncio
    async def test_sync_integration_data_awaits_ingest_document(self):
        """graphrag.ingest_document is a coroutine; sync_integration_data must
        await it. Without the await, every record raises AttributeError
        ('coroutine' object has no attribute 'get') and the sync is marked
        partial/failed."""
        import core.hybrid_data_ingestion as hdi
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        class FakeGraphRAG:
            async def ingest_document(self, **kwargs):
                return {"entities": 3, "relationships": 2}

        service = HybridDataIngestionService(workspace_id="ws-h", tenant_id="t-h")
        service.graphrag = FakeGraphRAG()
        service.memory_handler = None
        service.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"],
        )

        fake_session = _FakeSession()
        fake_et = MagicMock()
        fake_et.resolve_or_create_draft = MagicMock()

        with patch("core.hybrid_data_ingestion.SessionLocal", return_value=fake_session), \
             patch("core.entity_type_service.EntityTypeService", return_value=fake_et), \
             patch.object(
                 service, "_fetch_integration_data",
                 new=AsyncMock(return_value=[
                     {"id": "c1", "type": "contact", "name": "Alice",
                      "email": "alice@example.com", "title": "CEO"},
                 ]),
             ):
            results = await service.sync_integration_data("salesforce")

        assert results["success"] is True, results
        assert results["errors"] == [], results
        assert results["entities_extracted"] == 3
        assert results["relationships_extracted"] == 2
