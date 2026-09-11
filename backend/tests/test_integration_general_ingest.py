"""General on-demand integration ingestion — ANY connected integration.

The mailbox attachment path is one strategy of a general mechanism. This suite
pins the family dispatch and the shared idempotency contract:

  - record apps (CRM/Books/Inventory/support/…) → live search, render the
    record to text, write it under ``ext_sha1(service:external_id)``;
  - storage (drives) → the shared find→open→read leg (which already ingests);
  - mailbox (outlook/gmail) → the pipeline's full-message ingest;
  - an item already in memory is reported ``already_ingested`` with no write;
  - the user's selective-ingestion setting gates every family;
  - the live-evidence planner routes a non-mailbox `ingest` plan here.
"""

import os

os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, patch

import pytest

import core.drive_tree_ingestion as dti


@pytest.fixture(autouse=True)
def no_settings_gate(monkeypatch):
    monkeypatch.setattr(dti, "_integration_settings", lambda iid, ws: None)


class _SyncHandler:
    """Mirrors LanceDBHandler: add_document is SYNC."""

    def __init__(self, sink):
        self._sink = sink

    def add_document(self, **kwargs):
        self._sink.append(kwargs)
        return True


@pytest.fixture
def ingest_env(monkeypatch):
    """Isolated memory write + no-op already-in-memory probe."""
    from core.auto_document_ingestion import AutoDocumentIngestionService

    written = []
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda workspace_id=None: _SyncHandler(written),
    )
    monkeypatch.setattr(
        AutoDocumentIngestionService,
        "ingested_external_ids",
        AsyncMock(return_value=[]),
    )
    return written


@pytest.mark.asyncio
async def test_record_service_renders_and_writes_to_memory(monkeypatch, ingest_env):
    monkeypatch.setattr(
        dti,
        "_live_search_records",
        AsyncMock(
            return_value=[
                {"id": "lead-1", "Full_Name": "Jane Doe", "company": "Acme",
                 "amount": 100, "nested": {"a": 1}},
            ]
        ),
    )

    out = await dti.ingest_integration_content("zoho_crm", "u-1", query="Acme")

    assert out["success"] is True
    assert out["strategy"] == "records"
    assert out["ingested"] == 1
    assert ingest_env, "record must be written to the documents store"
    row = ingest_env[0]
    assert row["doc_id"].startswith("ext_")
    assert "Jane Doe" in row["text"]
    assert "nested" in row["text"]  # containers are compacted, not dropped
    assert row["metadata"]["source_type"] == "integration_record"
    assert row["metadata"]["integration_id"] == "zoho_crm"
    assert row["extra_columns"]["freshness_status"] == "fresh"


@pytest.mark.asyncio
async def test_record_already_in_memory_is_a_noop(monkeypatch, ingest_env):
    from core.auto_document_ingestion import AutoDocumentIngestionService

    monkeypatch.setattr(
        dti, "_live_search_records",
        AsyncMock(return_value=[{"id": "lead-1", "Full_Name": "Jane Doe"}]),
    )
    monkeypatch.setattr(
        AutoDocumentIngestionService,
        "ingested_external_ids",
        AsyncMock(return_value=["lead-1"]),
    )

    out = await dti.ingest_integration_content("zoho_crm", "u-1", query="Jane")

    assert out["already_ingested"] == 1
    assert out["ingested"] == 0
    assert out["items"][0]["status"] == "already_ingested"
    assert ingest_env == []  # the whole point: no duplicate write


@pytest.mark.asyncio
async def test_any_record_service_works_without_a_per_service_adapter(monkeypatch, ingest_env):
    """The generalization: a service with no drive adapter and no bespoke
    branch — here a support desk — still ingests through live search."""
    monkeypatch.setattr(
        dti, "_live_search_records",
        AsyncMock(return_value=[{"id": "t-9", "subject": "Printer down",
                                 "status": "open"}]),
    )
    out = await dti.ingest_integration_content("zendesk", "u-1", query="printer")
    assert out["success"] is True
    assert out["ingested"] == 1
    assert "Printer down" in ingest_env[0]["text"]


@pytest.mark.asyncio
async def test_storage_uses_the_shared_read_leg(monkeypatch):
    calls = []

    class _UIS:
        async def execute(self, service, action, params, context=None):
            calls.append((service, action, params))
            return {
                "status": "success",
                "data": {
                    "found": True, "file_id": "f-1", "file_name": "quote.xlsx",
                    "chars_extracted": 120, "ingested_into_workspace": True,
                },
            }

    monkeypatch.setattr(
        "integrations.universal_integration_service.UniversalIntegrationService",
        lambda: _UIS(),
    )

    out = await dti.ingest_integration_content("google_drive", "u-1", external_id="f-1")

    assert out["strategy"] == "storage"
    assert out["ingested"] == 1
    assert calls == [("google_drive", "read", {"file_id": "f-1", "query": ""})]


@pytest.mark.asyncio
async def test_storage_open_without_index_write_is_not_reported_as_ingested(monkeypatch):
    class _UIS:
        async def execute(self, service, action, params, context=None):
            return {
                "status": "success",
                "data": {"found": True, "file_id": "f-1", "file_name": "x.png",
                         "ingested_into_workspace": False},
            }

    monkeypatch.setattr(
        "integrations.universal_integration_service.UniversalIntegrationService",
        lambda: _UIS(),
    )
    out = await dti.ingest_integration_content("onedrive", "u-1", external_id="f-1")
    assert out["items"][0]["status"] == "skipped"
    assert out["success"] is False


@pytest.mark.asyncio
async def test_mailbox_delegates_to_the_pipeline(monkeypatch):
    from integrations.atom_communication_ingestion_pipeline import ingestion_pipeline

    with patch.object(
        ingestion_pipeline,
        "ingest_email_on_demand",
        new=AsyncMock(
            return_value={"status": "ingested", "subject": "RFQ", "attachments": 2}
        ),
    ) as ingest:
        out = await dti.ingest_integration_content("outlook", "u-1", external_id="m-1")

    assert out["strategy"] == "mailbox"
    assert out["ingested"] == 1
    ingest.assert_awaited_once_with("outlook", "u-1", "m-1")


@pytest.mark.asyncio
async def test_selective_ingestion_setting_gates_every_family(monkeypatch):
    class _Disabled:
        enabled = False

    monkeypatch.setattr(dti, "_integration_settings", lambda iid, ws: _Disabled())
    out = await dti.ingest_integration_content("zoho_crm", "u-1", query="Acme")
    assert out["success"] is False
    assert "disabled" in out["error"]


@pytest.mark.asyncio
async def test_requires_an_id_or_query():
    out = await dti.ingest_integration_content("zoho_crm", "u-1")
    assert out["success"] is False
    assert "query or external_id" in out["error"]


@pytest.mark.asyncio
async def test_no_matching_content_is_honest(monkeypatch):
    monkeypatch.setattr(dti, "_live_search_records", AsyncMock(return_value=[]))
    out = await dti.ingest_integration_content("zoho_crm", "u-1", query="nothing")
    assert out["success"] is False
    assert "no matching" in out["error"]


# ─── planner wiring ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_planner_general_ingest_intent_returns_evidence(monkeypatch):
    import core.chat_tool_planner as ctp
    from core.chat_tool_planner import ToolPlan, execute_tool_plan

    with patch(
        "core.autonomy_policy.gate_for_topic",
        return_value={"outcome": "execute", "reason": "test"},
    ), patch.object(
        ctp, "_memory_search_block", new=AsyncMock(return_value="MEMORY: Jane Doe")
    ), patch(
        "core.drive_tree_ingestion.ingest_integration_content",
        new=AsyncMock(
            return_value={
                "success": True, "integration_id": "zoho_crm", "strategy": "records",
                "items": [{"external_id": "lead-1", "status": "ingested",
                           "name": "Jane Doe"}],
                "ingested": 1, "already_ingested": 0, "skipped": 0, "message": "ok",
            }
        ),
    ) as ingest:
        block = await execute_tool_plan(
            ToolPlan(use_tool=True, service="zoho_crm", intent="ingest",
                     query="Acme lead"),
            user_id="u-1",
            context={"agent_id": "a-1", "workspace_id": "default"},
        )

    assert block is not None
    assert "INGESTED" in block
    assert "Jane Doe" in block
    assert "MEMORY: Jane Doe" in block
    ingest.assert_awaited_once()
    assert ingest.await_args.args[0] == "zoho_crm"


@pytest.mark.asyncio
async def test_planner_general_ingest_respects_pinned_approval(monkeypatch):
    import core.chat_tool_planner as ctp
    from core.chat_tool_planner import ToolPlan, execute_tool_plan

    with patch(
        "core.autonomy_policy.gate_for_topic",
        return_value={"outcome": "propose", "reason": "owner pinned"},
    ), patch(
        "core.drive_tree_ingestion.ingest_integration_content", new=AsyncMock()
    ) as ingest:
        block = await execute_tool_plan(
            ToolPlan(use_tool=True, service="zoho_crm", intent="ingest", query="x"),
            user_id="u-1",
        )

    assert "needs owner approval" in block
    ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_planner_general_ingest_kill_switch(monkeypatch):
    import core.chat_tool_planner as ctp
    from core.chat_tool_planner import ToolPlan, execute_tool_plan

    monkeypatch.setattr(ctp, "_planner_ingest_enabled", lambda: False)
    with patch(
        "core.drive_tree_ingestion.ingest_integration_content", new=AsyncMock()
    ) as ingest:
        block = await execute_tool_plan(
            ToolPlan(use_tool=True, service="zoho_crm", intent="ingest", query="x"),
            user_id="u-1",
        )
    assert "disabled by configuration" in block
    ingest.assert_not_awaited()


# ─── resolving ONE record by id, with no query to guide search ──────────────


@pytest.mark.asyncio
async def test_record_by_external_id_resolves_from_structure_index(monkeypatch, ingest_env):
    """A named id must resolve even when the caller has no query: the mapped
    structure index row IS the record's summary for record apps, and its doc id
    is deterministic (one point lookup)."""
    index_row = {
        "id": "idx_zoho_crm_lead-1",
        "text": "Acme Corp, stage: Qualified",
        "source": "zoho_crm-index:zoho_crm/Jane Doe",
        "metadata": '{"file_name": "Jane Doe", "external_id": "lead-1"}',
    }

    class _Handler:
        def add_document(self, **kwargs):
            ingest_env.append(kwargs)
            return True

        def get_document_by_id(self, table_name, doc_id):
            return index_row if doc_id == "idx_zoho_crm_lead-1" else None

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda workspace_id=None: _Handler(),
    )
    monkeypatch.setattr(dti, "_live_search_records", AsyncMock(return_value=[]))

    out = await dti.ingest_integration_content("zoho_crm", "u-1", external_id="lead-1")

    assert out["success"] is True
    assert out["ingested"] == 1
    assert "Acme Corp" in ingest_env[0]["text"]


@pytest.mark.asyncio
async def test_record_by_external_id_matches_live_search_exactly(monkeypatch, ingest_env):
    """When the index has no row, a live search using the id as the query is
    matched EXACTLY — an incidental hit is never mistaken for the id."""
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda workspace_id=None: _SyncHandler(ingest_env),
    )
    monkeypatch.setattr(
        dti,
        "_live_search_records",
        AsyncMock(
            return_value=[
                {"id": "someone-else", "Full_Name": "Decoy"},
                {"id": "lead-1", "Full_Name": "Jane Doe", "company": "Acme"},
            ]
        ),
    )

    out = await dti.ingest_integration_content("zoho_crm", "u-1", external_id="lead-1")

    assert out["ingested"] == 1
    assert len(ingest_env) == 1  # the decoy hit is NOT ingested
    assert "Jane Doe" in ingest_env[0]["text"]


@pytest.mark.asyncio
async def test_record_external_id_unresolved_is_honest(monkeypatch, ingest_env):
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda workspace_id=None: _SyncHandler(ingest_env),
    )
    monkeypatch.setattr(dti, "_live_search_records", AsyncMock(return_value=[]))

    out = await dti.ingest_integration_content("zoho_crm", "u-1", external_id="ghost-9")

    assert out["success"] is False
    assert "ghost-9" in out["error"]
    assert ingest_env == []
