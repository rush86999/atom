"""Ontology-object journey gaps (continuation of the 2026-08-25 data-journey trace).

Traced journey: integration record → schema discovery
(``EntityTypeService.resolve_or_create_draft``) → ``EntityTypeDefinition``;
record → ``map_record_type`` → canonical GraphRAG node types; record →
``write_integration_fact`` → ``business_facts`` → agent recall. Deletion:
org-bundle tombstones retract facts (R84) — regular syncs did not.

Gaps fixed here:

O1. **Draft dead-end**: auto-discovered entity types are created
    ``is_active=False``, the API list defaults to active-only, and neither
    the service update path nor any route could ever flip them to active.
    Discovery output was unreachable forever — dead rows.
O2. **Sync-path staleness**: only org-bundle import retracted derived facts
    when records disappeared (tombstones). A regular FULL sync whose fetch
    no longer returns a record left its ``intfact:…`` fact citable forever —
    agents kept citing deleted data (the exact bug class R84 closed for
    bundles).
"""
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# O1. Discovered drafts must be visible + activatable
# ---------------------------------------------------------------------------
@pytest.fixture
def et_service():
    from core.database import Base
    from core.entity_type_service import EntityTypeService
    from core.models import EntityTypeDefinition

    import sqlalchemy

    engine = sqlalchemy.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    Base.metadata.create_all(engine, tables=[EntityTypeDefinition.__table__])
    db = sqlalchemy.orm.sessionmaker(bind=engine)()
    svc = EntityTypeService(db=db)
    yield svc, db
    db.close()


VALID_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"name": {"type": "string"}},
}


def test_discovered_draft_activatable_and_then_listed(et_service):
    """resolve_or_create_draft → invisible in default list → activate → listed."""
    svc, db = et_service

    draft = svc.resolve_or_create_draft(
        tenant_id="t1",
        slug="ws1_crm_crm_leads",
        display_name="Crm Leads",
        json_schema=VALID_SCHEMA,
        description="Automatically discovered from crm sync.",
    )
    assert draft.is_active is False

    # Default listing (active-only) must NOT contain the draft…
    assert draft.slug not in [t.slug for t in svc.list_entity_types(tenant_id="t1")]
    # …but an all-status listing must.
    assert draft.slug in [
        t.slug for t in svc.list_entity_types(tenant_id="t1", is_active=None)
    ]

    # Activation path: flip the flag through the service.
    updated = svc.update_entity_type(
        tenant_id="t1",
        entity_type_id=str(draft.id),
        is_active=True,
        changed_by="admin",
        change_summary="Approved auto-discovered type",
    )
    assert updated.is_active is True
    assert updated.version == 1, "activation is not a schema change — no version bump"
    assert draft.slug in [t.slug for t in svc.list_entity_types(tenant_id="t1")]


@pytest.mark.asyncio
async def test_routes_expose_is_active_end_to_end(et_service):
    """API surface: create/update accept is_active, list can include drafts,
    and every response carries the flag."""
    import backend.api.entity_type_routes as routes

    svc, _db = et_service
    created = svc.resolve_or_create_draft(
        tenant_id="ws1",
        slug="ws1_zoho_books_invoices",
        display_name="Books Invoices",
        json_schema=VALID_SCHEMA,
    )

    with patch.object(routes, "get_entity_type_service", return_value=svc):
        # Drafts hidden by default…
        resp_hidden = await routes.list_entity_types(workspace_id="ws1")
        slugs_hidden = {d["slug"] for d in resp_hidden["data"]}
        assert "ws1_zoho_books_invoices" not in slugs_hidden
        assert "is_active" in next(iter(resp_hidden["data"] or [{"is_active": 0}]))

        # …visible with include_drafts.
        resp_all = await routes.list_entity_types(
            workspace_id="ws1", include_drafts=True
        )
        slugs_all = {d["slug"] for d in resp_all["data"]}
        assert "ws1_zoho_books_invoices" in slugs_all
        row = next(d for d in resp_all["data"] if d["slug"] == "ws1_zoho_books_invoices")
        assert row["is_active"] is False

        # Activate via PATCH.
        upd = await routes.update_entity_type(
            workspace_id="ws1",
            entity_type_id=str(created.id),
            request=routes.EntityTypeUpdate(is_active=True),
        )
        assert upd["success"] is True

    refreshed = svc.get_entity_type(tenant_id="ws1", entity_type_id=str(created.id))
    assert refreshed.is_active is True


@pytest.mark.asyncio
async def test_get_entity_type_response_carries_is_active(et_service):
    svc, _db = et_service
    created = svc.resolve_or_create_draft(
        tenant_id="ws1", slug="ws1_x_y", display_name="Y",
        json_schema=VALID_SCHEMA,
    )
    import backend.api.entity_type_routes as routes

    with patch.object(routes, "get_entity_type_service", return_value=svc):
        resp = await routes.get_entity_type(
            workspace_id="ws1", entity_type_id=str(created.id)
        )
    assert resp["data"]["is_active"] is False


# ---------------------------------------------------------------------------
# O2. FULL syncs must retract facts for records that vanished upstream
# ---------------------------------------------------------------------------
class FakeFactHandler:
    """Handler double with real id semantics + a scannable facts table."""

    def __init__(self, fact_rows: Dict[str, Dict[str, Any]]):
        self.fact_rows = fact_rows  # doc_id -> metadata
        self.deleted: List[str] = []

    def get_document_by_id(self, table_name, doc_id):
        if table_name != "business_facts":
            return None
        if doc_id not in self.fact_rows:
            return None
        return {"id": doc_id, "metadata": self.fact_rows[doc_id]}

    def add_document(self, **kwargs):
        if kwargs.get("table_name") == "business_facts":
            self.fact_rows[kwargs["doc_id"]] = kwargs.get("metadata") or {}
        return True

    def delete_documents_by_id(self, table_name, doc_id):
        self.deleted.append(doc_id)
        existed = self.fact_rows.pop(doc_id, None) is not None or True
        return True

    def get_table(self, table_name):
        if table_name != "business_facts":
            return None
        return _FakeFactsTable(self.fact_rows)


class _FakeFactsTable:
    def __init__(self, rows):
        self._rows = rows
        self._where = None

    def search(self):
        return self

    def where(self, expr):
        self._where = expr
        return self

    def limit(self, n):
        return self

    def to_pandas(self):
        import pandas as pd

        prefix = ""
        if self._where and "LIKE" in self._where:
            prefix = self._where.split("LIKE '", 1)[1].split("%", 1)[0]
        recs = [
            {"id": rid, "metadata": meta}
            for rid, meta in self._rows.items()
            if rid.startswith(prefix)
        ]
        return pd.DataFrame(recs)


@pytest.mark.asyncio
async def test_retract_stale_integration_facts_deletes_only_missing():
    from core.integration_ontology_bridge import retract_stale_integration_facts

    handler = FakeFactHandler({
        "intfact:crm:L-1": {"id": "intfact:crm:L-1"},
        "intfact:crm:L-2": {"id": "intfact:crm:L-2"},
        "intfact:other:X-1": {"id": "intfact:other:X-1"},  # other integration
    })

    stats = await retract_stale_integration_facts(
        integration_id="crm",
        keep_record_ids=["L-1"],
        memory_handler=handler,
    )

    assert stats["retracted"] == 1
    assert "intfact:crm:L-2" in handler.deleted
    assert "intfact:crm:L-1" not in handler.deleted
    assert "intfact:other:X-1" not in handler.deleted


@pytest.mark.asyncio
async def test_retract_stale_noop_guards():
    from core.integration_ontology_bridge import retract_stale_integration_facts

    assert await retract_stale_integration_facts(
        integration_id="crm", keep_record_ids=["a"], memory_handler=None
    ) == {"retracted": 0}
    boom = MagicMock()
    boom.get_table.side_effect = RuntimeError("lance down")
    assert await retract_stale_integration_facts(
        integration_id="crm", keep_record_ids=["a"], memory_handler=boom
    ) == {"retracted": 0}


@pytest.mark.asyncio
async def test_full_sync_retracts_stale_facts(monkeypatch):
    """Clean FULL sync: record B gone from source → its fact retracted."""
    from core.hybrid_data_ingestion import (
        HybridDataIngestionService,
        SyncConfiguration,
    )

    service = HybridDataIngestionService(workspace_id="ws1")
    service.sync_configs["crm"] = SyncConfiguration(
        integration_id="crm", sync_mode="full"
    )
    handler = FakeFactHandler({
        "intfact:crm:A": {"id": "intfact:crm:A"},
        "intfact:crm:B": {"id": "intfact:crm:B"},
    })
    service.memory_handler = handler
    service.graphrag = None

    monkeypatch.setattr(
        service,
        "_fetch_integration_data",
        AsyncMock(return_value=[
            {"id": "A", "type": "unknown", "summary": "Account still exists at source"}
        ]),
    )

    results = await service.sync_integration_data("crm", force=True)

    assert results["success"] is True
    assert "intfact:crm:B" not in handler.fact_rows, (
        "FULL sync that no longer returns record B must retract its stale fact"
    )
    assert "intfact:crm:A" in handler.fact_rows, (
        "live record's fact must survive the GC"
    )
    assert results.get("facts_retracted") == 1


@pytest.mark.asyncio
async def test_incremental_sync_never_retracts(monkeypatch):
    """Incremental fetches only recent records — a small keep-set must NOT
    delete older facts."""
    from core.hybrid_data_ingestion import (
        HybridDataIngestionService,
        SyncConfiguration,
    )

    service = HybridDataIngestionService(workspace_id="ws1")
    service.sync_configs["crm"] = SyncConfiguration(
        integration_id="crm", sync_mode="incremental"
    )
    handler = FakeFactHandler({
        "intfact:crm:A": {"id": "intfact:crm:A"},
        "intfact:crm:B": {"id": "intfact:crm:B"},
    })
    service.memory_handler = handler
    service.graphrag = None

    monkeypatch.setattr(
        service,
        "_fetch_integration_data",
        AsyncMock(return_value=[
            {"id": "A", "type": "unknown", "summary": "Recent account record here"}
        ]),
    )

    results = await service.sync_integration_data("crm", force=True)

    assert results["success"] is True
    assert "intfact:crm:B" in handler.fact_rows, (
        "incremental syncs must never GC facts absent from a partial fetch"
    )


@pytest.mark.asyncio
async def test_partial_sync_never_retracts(monkeypatch):
    """A sync where some records errored may be missing ids for transient
    reasons — retraction would destroy live facts."""
    from core.hybrid_data_ingestion import (
        HybridDataIngestionService,
        SyncConfiguration,
    )

    service = HybridDataIngestionService(workspace_id="ws1")
    service.sync_configs["crm"] = SyncConfiguration(
        integration_id="crm", sync_mode="full"
    )
    handler = FakeFactHandler({"intfact:crm:A": {"id": "intfact:crm:A"}})
    service.memory_handler = handler
    service.graphrag = None

    async def boom(*a, **k):
        raise RuntimeError("fetch exploded mid-page")

    monkeypatch.setattr(service, "_fetch_integration_data", boom)

    results = await service.sync_integration_data("crm", force=True)

    assert results["success"] is False
    assert "intfact:crm:A" in handler.fact_rows, (
        "failed/partial syncs must never GC facts"
    )
