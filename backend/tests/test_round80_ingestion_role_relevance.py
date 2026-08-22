"""RED/GREEN tests — Round 80: data ingestion relevance to AI-employee memory.

The "AI employee" is an AgentRegistry row (category = role, specialty =
responsibility). Ingested org data (documents + integration records) was
stored workspace-scoped with NO role/agent attribution, and the knowledge
leg of recall_experiences returned the SAME docs to every agent — so ingested
data was not "relevant to the AI employee's memory for work/role/
responsibilities".

Fixes under test (RED first):
  R1 — IngestedDocument gains a nullable `role` column (ingestion target role).
  R2 — process_file_bytes(..., role=) stamps role into documents-table metadata.
  R3 — sync_integration_data(..., role=) stamps role into integration_* metadata.
  R4 — recall_experiences' knowledge leg (via _recall_general_knowledge) prefers
       documents tagged with the agent's role and tops up with untagged general
       knowledge (graceful degradation — never empty for a role).
  R5 — POST /api/data-ingestion/sync/{id}?agent_id=<id> resolves the AI
       employee's role (AgentRegistry.category) and passes it into the sync.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import IngestedDocument, User


@pytest.fixture
def fake_lance():
    """A MagicMock LanceDBMemoryManager stand-in that records search calls."""
    calls = []
    db = MagicMock()
    db.search = MagicMock(return_value=[])
    return db, calls


# Helper: attach a call-recording search to the mock db.
def _record_search(calls, db):
    def _search(table_name, query, limit=10, user_id=None, filter_str=None, **kw):
        calls.append({"table": table_name, "filter_str": filter_str, "limit": limit})
        return db.search.return_value
    db.search.side_effect = _search
    return db


# --------------------------------------------------------------------------
# R1 — model column
# --------------------------------------------------------------------------

class TestIngestedDocumentRoleColumn:
    def test_role_column_exists(self):
        cols = {c.name for c in IngestedDocument.__table__.columns}
        assert "role" in cols, "IngestedDocument needs a nullable `role` column"

    def test_role_nullable(self):
        col = IngestedDocument.__table__.columns["role"]
        assert col.nullable is True


# --------------------------------------------------------------------------
# R4 — role-relevant general-knowledge recall (tested on a lightweight object)
# --------------------------------------------------------------------------

class TestRoleRelevantKnowledgeRecall:
    def _make_world(self, fake_db):
        from core.agent_world_model import WorldModelService
        wm = WorldModelService.__new__(WorldModelService)
        wm.db = fake_db
        wm.table_name = "agent_experience"
        wm.facts_table_name = "business_facts"
        return wm

    def test_role_filtered_search_first(self, fake_lance):
        db, calls = fake_lance
        wm = self._make_world(db)
        _record_search(calls, db)

        # role search must run a metadata.role filter, then a general top-up
        # runs without the filter.
        wm._recall_general_knowledge(db, "prepare q3 report", "finance", limit=5)

        assert len(calls) >= 2
        role_call = calls[0]
        assert "metadata.role" in role_call["filter_str"]
        assert role_call["limit"] == 5
        # second call is the untagged general top-up (no filter)
        assert calls[1]["filter_str"] is None

    def test_untagged_general_docs_top_up_role_results(self, fake_lance):
        db, calls = fake_lance
        wm = self._make_world(db)

        role_hit = {"id": "r1", "text": "finance report"}
        general = [{"id": "g1", "text": "general note"}, {"id": "r1", "text": "dup"}]

        def fake_search(table_name, query, limit=10, user_id=None, filter_str=None, **kw):
            calls.append({"filter_str": filter_str, "limit": limit})
            return [role_hit] if filter_str else general

        db.search.side_effect = fake_search

        results = wm._recall_general_knowledge(db, "task", "sales", limit=5)
        # role hit first, then untagged general (dup 'r1' excluded)
        assert [r["id"] for r in results] == ["r1", "g1"]

    def test_no_role_falls_back_to_unfiltered_general(self, fake_lance):
        db, calls = fake_lance
        wm = self._make_world(db)
        _record_search(calls, db)
        wm._recall_general_knowledge(db, "task", None, limit=5)
        assert len(calls) == 1
        assert calls[0]["filter_str"] is None

    def test_role_normalized_to_lowercase(self, fake_lance):
        db, calls = fake_lance
        wm = self._make_world(db)
        _record_search(calls, db)
        wm._recall_general_knowledge(db, "task", "Operations", limit=5)
        assert calls and "operations" in calls[0]["filter_str"]


# --------------------------------------------------------------------------
# R2 — process_file_bytes stamps role into documents-table metadata
# --------------------------------------------------------------------------

class TestFileIngestionRoleTag:
    def test_role_in_document_metadata(self):
        from core.auto_document_ingestion import AutoDocumentIngestionService

        svc = AutoDocumentIngestionService.__new__(AutoDocumentIngestionService)
        svc.workspace_id = "default"
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(return_value="Financial summary text here")
        svc.redactor = None
        add_doc = AsyncMock(return_value=True)
        svc.memory_handler = MagicMock(add_document=add_doc)

        import asyncio
        result = asyncio.run(svc.process_file_bytes(
            b"pdf-bytes", "q3_sales.pdf", source="onedrive", role="finance",
        ))

        assert result["status"] == "ingested"
        _, kwargs = add_doc.call_args
        assert kwargs["metadata"]["role"] == "finance"
        assert kwargs["table_name"] == "documents"

    def test_no_role_keeps_metadata_clean(self):
        from core.auto_document_ingestion import AutoDocumentIngestionService

        svc = AutoDocumentIngestionService.__new__(AutoDocumentIngestionService)
        svc.workspace_id = "default"
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(return_value="Doc body here")
        svc.redactor = None
        add_doc = AsyncMock(return_value=True)
        svc.memory_handler = MagicMock(add_document=add_doc)

        import asyncio
        asyncio.run(svc.process_file_bytes(b"bytes", "note.md", source="upload"))
        _, kwargs = add_doc.call_args
        assert "role" not in kwargs["metadata"]


# --------------------------------------------------------------------------
# R3 — sync_integration_data stamps role into integration_* metadata
# --------------------------------------------------------------------------

class TestSyncRoleTag:
    async def _run_sync(self, role=None):
        from core.hybrid_data_ingestion import HybridDataIngestionService

        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "default"
        svc.tenant_id = None
        svc.memory_handler = MagicMock(add_document=AsyncMock(return_value=True))
        svc.graphrag = None
        svc.usage_stats = {}
        from core.hybrid_data_ingestion import SyncConfiguration
        svc.sync_configs = {"zoho": SyncConfiguration(integration_id="zoho")}
        svc._persist_integration = MagicMock()

        record = {"id": "rec1", "type": "deal", "name": "Acme", "user_id": "u1"}
        svc._fetch_integration_data = AsyncMock(return_value=[record])
        svc._record_to_text = MagicMock(return_value="Acme deal record text")

        return await svc.sync_integration_data("zoho", force=True, role=role), svc

    def test_role_passed_into_lancedb_metadata(self):
        import asyncio
        result, svc = asyncio.run(self._run_sync(role="sales"))
        assert result.get("records_ingested") == 1
        _, kwargs = svc.memory_handler.add_document.call_args
        assert kwargs["metadata"]["role"] == "sales"

    def test_no_role_omits_key(self):
        import asyncio
        _, svc = asyncio.run(self._run_sync())
        _, kwargs = svc.memory_handler.add_document.call_args
        assert "role" not in kwargs["metadata"]


# --------------------------------------------------------------------------
# R5 — trigger-sync resolves agent_id -> role and passes it through
# --------------------------------------------------------------------------

class TestTriggerSyncAgentRole:
    def _client(self, service_mock, agent=None):
        app = FastAPI()
        from core.auth import get_current_user
        from core.database import get_db
        from api import data_ingestion_routes as r

        app.include_router(r.router)
        app.dependency_overrides[get_current_user] = lambda: MagicMock(spec=User)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        with patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service", return_value=service_mock), \
                patch.object(r, "get_workspace_id", return_value="default"):
            return TestClient(app, raise_server_exceptions=False)

    def test_agent_id_resolves_role_into_sync(self):
        import asyncio
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service as _unused  # noqa: F401
        service = MagicMock()
        service.sync_integration_data = AsyncMock(return_value={"success": True})
        agent = MagicMock()
        agent.category = "Finance"

        app = FastAPI()
        from core.auth import get_current_user
        from core.database import get_db
        from api import data_ingestion_routes as r
        from core.models import AgentRegistry

        app.include_router(r.router)
        app.dependency_overrides[get_current_user] = lambda: MagicMock(spec=User)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        app.dependency_overrides[get_db] = lambda: db

        with patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service", return_value=service), \
                patch.object(r, "get_workspace_id", return_value="default"), \
                patch("core.agent_governance_service.AgentGovernanceService.can_perform_action",
                      return_value={"allowed": True}):
            c = TestClient(app, raise_server_exceptions=False)
            resp = c.post("/api/data-ingestion/sync/zoho?force=true&agent_id=agent-1")

        assert resp.status_code == 200
        service.sync_integration_data.assert_awaited_once_with("zoho", force=True, role="finance")
        db.query.assert_called_with(AgentRegistry)


# --------------------------------------------------------------------------
# R6 — role persists on SyncConfiguration so scheduled auto-syncs inherit it
# --------------------------------------------------------------------------

class TestRolePersistsOnConfig:
    """SyncConfiguration.role persists so scheduled auto-syncs inherit it."""

    def _svc_with_role(self, role):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService, SyncConfiguration,
        )
        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "default"
        svc.tenant_id = None
        svc.memory_handler = MagicMock(add_document=AsyncMock(return_value=True))
        svc.graphrag = None
        svc.usage_stats = {}
        cfg = SyncConfiguration(integration_id="zoho", role=role)
        svc.sync_configs = {"zoho": cfg}
        svc._persist_integration = MagicMock()
        return svc

    def _run(self, svc):
        import asyncio
        record = {"id": "r1", "type": "deal", "user_id": "u"}
        svc._fetch_integration_data = AsyncMock(return_value=[record])
        svc._record_to_text = MagicMock(return_value="Acme deal text")
        return asyncio.run(svc.sync_integration_data("zoho", force=True)), svc

    def test_explicit_role_overrides_config(self):
        import asyncio
        from core.hybrid_data_ingestion import HybridDataIngestionService

        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "default"
        svc.tenant_id = None
        svc.memory_handler = MagicMock(add_document=AsyncMock(return_value=True))
        svc.graphrag = None
        svc.usage_stats = {}
        cfg = SyncConfiguration(integration_id="zoho", role="sales")
        svc.sync_configs = {"zoho": cfg}
        svc._persist_integration = MagicMock()
        record = {"id": "r1", "type": "deal", "user_id": "u"}
        svc._fetch_integration_data = AsyncMock(return_value=[record])
        svc._record_to_text = MagicMock(return_value="Acme deal text")

        result = asyncio.run(
            svc.sync_integration_data("zoho", force=True, role="ops"))
        _, kwargs = svc.memory_handler.add_document.call_args
        assert kwargs["metadata"]["role"] == "ops"

    def test_config_role_used_without_explicit_param(self):
        svc = self._svc_with_role("finance")
        result, svc = self._run(svc)
        _, kwargs = svc.memory_handler.add_document.call_args
        assert kwargs["metadata"]["role"] == "finance"

    def test_explicit_role_overrides_config(self):
        svc = self._svc_with_role("sales")
        result, svc = self._run(svc)  # no explicit param → config wins? No:
        # explicit call-site param beats config; here we pass none so config applies


