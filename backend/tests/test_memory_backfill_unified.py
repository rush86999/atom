"""
Outlook/email backfill → unified-memory bridge tests (P0.4 ingestion symmetry).

RED: `OutlookIntegration.backfill_to_memory` (via `_run_backfill`) wrote only
generic LanceDB entities — neither `atom_communications` (Pipeline A) nor graph
entities (Pipeline B). The plan contract requires backfill to reach both
pipelines, exactly like the webhook and poller live paths already do.

GREEN: `_bridge_records_to_unified_memory` routes email/communication backfill
records through `CommunicationIngestionPipeline.ingest_message` (Pipeline A +
Pipeline B via its `knowledge_manager.process_document` trigger) so backfilled
mail is readable at retrieval time.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.memory_integration_mixin import MemoryIntegrationMixin


class _EmailBackfill(MemoryIntegrationMixin):
    """Email-shaped integration under test (mirrors OutlookIntegration)."""

    def __init__(self):
        super().__init__(integration_id="outlook")

    async def fetch_records(self, start_date=None, end_date=None, limit=500):
        return [
            {
                "id": "email_001",
                "type": "email",
                "subject": "Q3 Quote",
                "from": "acme@example.com",
                "to": ["me@example.com"],
                "date": "2026-08-20T10:00:00Z",
                "body": "Per our call, the ACME Fab quote is $12,400 for 500 units.",
            }
        ]

    def get_integration_type(self):
        return "email"


@pytest.fixture
def email_backfill():
    return _EmailBackfill()


@pytest.mark.asyncio
async def test_email_backfill_routes_records_through_comm_pipeline(email_backfill):
    """Pipeline A bridge: every fetched record must reach ingest_message,
    so backfilled mail lands in the FTS+vector atom_communications store."""
    with patch(
        "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline",
    ) as mock_get:
        pipeline = MagicMock()
        pipeline.ingest_message = AsyncMock(return_value=True)
        mock_get.return_value = pipeline

        result = await email_backfill._bridge_records_to_unified_memory(
            await email_backfill.fetch_records()
        )

        assert result["comms"] == 1
        pipeline.ingest_message.assert_awaited_once()
        args = pipeline.ingest_message.await_args.args
        assert args[0] == "outlook"
        assert args[1]["id"] == "email_001"
        assert args[1]["subject"] == "Q3 Quote"


@pytest.mark.asyncio
async def test_non_communication_backfill_skips_bridge():
    """CRM/other integrations keep their existing generic-LanceDB behavior."""
    class _CrmBackfill(MemoryIntegrationMixin):
        def __init__(self):
            super().__init__(integration_id="salesforce")

        async def fetch_records(self, start_date=None, end_date=None, limit=500):
            return [{"id": "acc_1", "name": "ACME"}]

        def get_integration_type(self):
            return "crm"

    crm = _CrmBackfill()
    with patch(
        "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline",
    ) as mock_get:
        result = await crm._bridge_records_to_unified_memory(
            await crm.fetch_records()
        )
        mock_get.assert_not_called()
        assert result["comms"] == 0


@pytest.mark.asyncio
async def test_bridge_never_raises_on_pipeline_failure(email_backfill):
    """A broken comm pipeline must not fail the backfill job (log, allow)."""
    with patch(
        "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline",
    ) as mock_get:
        pipeline = MagicMock()
        pipeline.ingest_message = AsyncMock(side_effect=RuntimeError("redis down"))
        mock_get.return_value = pipeline

        result = await email_backfill._bridge_records_to_unified_memory(
            await email_backfill.fetch_records()
        )

        assert result["comms"] == 0
        assert result["graph"] == 0


@pytest.mark.asyncio
async def test_run_backfill_invokes_bridge(email_backfill):
    """_run_backfill must call the bridge so the whole backfill job is covered."""
    records = await email_backfill.fetch_records()
    email_backfill.lancedb = MagicMock()
    email_backfill.entity_extractor = MagicMock()
    email_backfill.entity_extractor.extract = AsyncMock(return_value=[
        {
            "id": "email_001",
            "type": "email",
            "text": "Q3 Quote per our call ACME Fab",
        }
    ])
    email_backfill.lancedb.add_documents = AsyncMock(return_value=None)

    job = MagicMock()
    job.status = "pending"
    job.total_records = 0
    job.processed_records = 0
    job.failed_records = 0

    with patch(
        "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline",
    ) as mock_get, patch.object(
        email_backfill, "fetch_records", AsyncMock(return_value=records)
    ):
        pipeline = MagicMock()
        pipeline.ingest_message = AsyncMock(return_value=True)
        mock_get.return_value = pipeline

        await email_backfill._run_backfill(
            job,
            start_date=None,
            end_date=None,
            limit=500,
            batch_size=50,
        )

        assert job.status == "completed"
        assert job.processed_records == 1
        pipeline.ingest_message.assert_awaited()
