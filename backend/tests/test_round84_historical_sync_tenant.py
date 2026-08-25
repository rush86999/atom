"""Round 84 — data-journey bug: historical sync ingested under wrong tenant.

``HistoricalSyncService._extract_chunk_and_ingest`` constructs its
GraphRAGEngine with ``tenant_id=self.tenant_id`` but then calls
``ingest_structured_data(tenant_id=workspace_id)`` — overriding with the
WORKSPACE id. Every historical-backfill node was filed under a bogus
tenant, invisible to tenant-scoped graph reads (and to org-bundle /
hybrid-sync nodes ingested correctly).
"""

from unittest.mock import MagicMock, patch

import pytest

import core.historical_sync_service as hss


@pytest.mark.asyncio
async def test_historical_sync_ingests_under_service_tenant():
    svc = hss.HistoricalSyncService(
        tenant_id="tenant-1", db=MagicMock(), workspace_id="ws-1"
    )

    engine = MagicMock()
    engine.ingest_structured_data.return_value = {"inserted": 1}

    with patch.object(hss, "SessionLocal", return_value=MagicMock()), \
         patch("core.graphrag_engine.GraphRAGEngine", return_value=engine), \
         patch("core.llm_service.LLMService"):
        # One doc whose LLM extraction yields one entity.
        async def fake_extract(*a, **k):
            from types import SimpleNamespace

            ent = SimpleNamespace(
                name="Acme", entity_type="Organization",
                description="d", properties={},
            )
            rel = SimpleNamespace(
                from_entity="Acme", to_entity="Bob",
                rel_type="EMPLOYS", properties={},
            )
            return [ent], [rel]

        with patch.object(hss, "_llm_extract_with_handler") as mock_extract:
            mock_extract.side_effect = fake_extract
            total_e, total_r = await svc._extract_chunk_and_ingest(
                job_id="job-1",
                chunk_count=0,
                llm_task_records=[("doc-1", "some text", "src")],
                workspace_id="ws-1",
                integration_id="hubspot",
            )

    assert total_e == 1 and total_r == 1
    kwargs = engine.ingest_structured_data.call_args.kwargs
    assert kwargs["workspace_id"] == "ws-1"
    # THE FIX: tenant must be the service's tenant — not the workspace id.
    assert kwargs["tenant_id"] == "tenant-1"
