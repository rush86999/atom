"""
Bug hunt: sync ``add_document`` called from async context (loop thread).

``LanceDBHandler.embed_text`` deliberately returns None when called from the
event-loop thread ("Please use async_embed_text") — the synchronous embedding
path cannot run there. Every service that called the SYNC ``add_document``
directly from an ``async def`` therefore failed to store anything: embed
returned None -> add_document returned False -> the write silently no-op'd
(or the route 500'd).

Each test below drives a REAL LanceDBHandler on a tmp dir (only the cloud
embed call is stubbed to a fixed 1536-dim vector) and asserts the row actually
lands. Before the fix every one of these was red: the embed same-thread guard
fires before any provider is consulted.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from core.lancedb_handler import LanceDBHandler


class _StubEmbed:
    """Replaces LLMService: deterministic offline embedding."""

    async def generate_embedding(self, text, **kw):
        return [0.01] * 1536


def make_real_handler(tmp_path, ws="bug_ws"):
    h = LanceDBHandler(db_path=str(tmp_path / f"ldb_{ws}"), workspace_id=ws)
    h.embedding_service = _StubEmbed()
    h._ensure_db()
    return h


def stored_rows(handler, table):
    t = handler.get_table(table)
    return t.count_rows() if t is not None else 0


# ============================================================================
# api/document_routes — POST /api/documents/ingest
# ============================================================================

async def test_api_ingest_stores_document(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from api.document_routes import router, get_current_user

    handler = make_real_handler(tmp_path)
    monkeypatch.setattr("api.document_routes.get_lancedb_handler", lambda ws=None: handler)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1", workspaces=[])

    from fastapi.testclient import TestClient
    resp = TestClient(app).post(
        "/api/documents/ingest",
        json={"content": "Quarterly compliance policy notes", "type": "txt"},
    )
    assert resp.status_code == 200, resp.text
    assert stored_rows(handler, "documents") == 1


# ============================================================================
# api/document_ingestion_routes — POST /api/document-ingestion/upload
# ============================================================================

async def test_upload_route_stores_document(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from api.document_ingestion_routes import router, get_current_user

    handler = make_real_handler(tmp_path)
    # upload_document does a local `from core.lancedb_handler import LanceDBHandler`
    monkeypatch.setattr("core.lancedb_handler.LanceDBHandler", lambda *a, **k: handler)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1", workspaces=[])

    from fastapi.testclient import TestClient
    resp = TestClient(app).post(
        "/api/document-ingestion/upload",
        files={"file": ("note.txt", b"hello world this is a text file", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    assert stored_rows(handler, "documents") == 1


# ============================================================================
# core/episode_segmentation_service — _archive_to_lancedb
# ============================================================================

async def test_episode_archive_stores_row(tmp_path):
    from core.episode_segmentation_service import EpisodeSegmentationService

    handler = make_real_handler(tmp_path)
    svc = EpisodeSegmentationService.__new__(EpisodeSegmentationService)
    svc.lancedb = handler

    episode = {
        "id": "ep1", "agent_id": "a1", "user_id": "u1", "workspace_id": "ws",
        "session_id": "s1", "status": "completed", "outcome": "success",
        "title": "Fix invoice", "description": "desc", "summary": "summ",
        "topics": ["billing"],
    }
    await svc._archive_to_lancedb(episode)
    assert stored_rows(handler, "episodes") == 1


# ============================================================================
# core/memory_consolidation — _archive_old_memories
# ============================================================================

async def test_memory_consolidation_archives_to_lancedb(tmp_path, monkeypatch):
    import core.memory_consolidation as mc

    handler = make_real_handler(tmp_path)

    old_memory = SimpleNamespace(
        id="m1", agent_id="a1", memory_type="episodic", importance_score=0.5,
        access_count=3, content="remember to file taxes", metadata_json=None,
        workspace_id="ws", created_at=None,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.all.return_value = [old_memory]
    monkeypatch.setattr(mc, "SessionLocal", MagicMock(return_value=db))
    monkeypatch.setattr(mc, "get_lancedb_handler", lambda tid=None: handler)

    svc = mc.MemoryConsolidationService(workspace_id="ws")
    count = await svc._archive_old_memories("t1")
    assert count == 1
    assert stored_rows(handler, "archived_memories") == 1


# ============================================================================
# core/auto_document_ingestion — process_file_bytes
# ============================================================================

async def test_auto_ingest_file_bytes_stores(tmp_path):
    from core.auto_document_ingestion import AutoDocumentIngestionService

    handler = make_real_handler(tmp_path)
    svc = AutoDocumentIngestionService()
    svc.memory_handler = handler

    result = await svc.process_file_bytes(
        b"important document body text", "report.txt", source="upload", user_id="u1"
    )
    assert result["status"] == "ingested", result
    assert stored_rows(handler, "documents") == 1


# ============================================================================
# core/hybrid_data_ingestion — sync_integration_data
# ============================================================================

async def test_hybrid_sync_stores_records(tmp_path, monkeypatch):
    import core.hybrid_data_ingestion as hybrid_mod
    from core.hybrid_data_ingestion import HybridDataIngestionService, SyncConfiguration

    handler = make_real_handler(tmp_path)
    with patch("core.lancedb_handler.get_lancedb_handler", return_value=None), \
         patch("core.graphrag_engine.GraphRAGEngine", side_effect=ImportError), \
         patch("core.llm_service.get_llm_service", side_effect=ImportError):
        svc = HybridDataIngestionService(workspace_id="ws", tenant_id="t1")
    svc.memory_handler = handler
    svc.graphrag = None
    svc.sync_configs = {
        "zoho": SyncConfiguration(integration_id="zoho", entity_types=["Leads"])
    }
    svc.usage_stats = {}
    monkeypatch.setattr(
        svc, "_fetch_integration_data",
        AsyncMock(return_value=[{"id": "r1", "name": "Acme Corp Lead", "amount": 500}]),
    )

    results = await svc.sync_integration_data("zoho", force=True)
    assert results.get("records_ingested") == 1, results
    assert stored_rows(handler, "integration_zoho") == 1


# ============================================================================
# core/ingestion_pipeline — process_webhook_payload_tiered
# ============================================================================

async def test_webhook_tiered_stores_message(tmp_path, monkeypatch):
    import core.ingestion_pipeline as ip

    handler = make_real_handler(tmp_path)
    svc = ip.IngestionPipelineService.__new__(ip.IngestionPipelineService)
    svc.tenant_id = "t1"
    svc.workspace_id = "ws"
    svc.lancedb = handler
    svc.usage_tracker = SimpleNamespace(
        check_quota_before_job=AsyncMock(return_value={"allowed": True}),
        calculate_acu_consumed=lambda **kw: 0.1,
    )
    svc._transform_webhook_payload = AsyncMock(
        return_value=[{"id": "w1", "type": "note"}]
    )
    svc._record_to_text = lambda record, iid: "a webhook body long enough to index"
    svc._is_doc_already_ingested = lambda ws, rid, text: False
    svc._extract_structured_entities = lambda record, iid, text: (None, None)
    svc._process_multi_entity_extraction = AsyncMock()
    svc.graphrag = MagicMock()
    monkeypatch.setattr(ip, "SessionLocal", MagicMock(
        return_value=MagicMock(query=MagicMock(return_value=MagicMock(
            filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None))))))))

    results = await svc.process_webhook_payload_tiered("zoho", {})
    assert results.get("records_processed") == 1, results
    assert stored_rows(handler, "tenant_t1_messages") == 1
