"""Round 84 — close the four deferred R83b gaps (integration→ontology).

Gaps closed (docs/testing/TESTED_FILES_TRACKER.md R83b "Known remaining"):

A. Business-fact auto-extraction from integration records — deterministic,
   LLM-free fact writer (`core.integration_ontology_bridge`) wired into the
   hybrid sync loop, webhook basic tier, and org-bundle import. Facts are
   OBSERVATIONS: verification_status="unverified", sensitivity stamped into
   metadata, idempotent via DocumentIngestion markers keyed
   ``intfact:{integration_id}:{record_id}``.

B. Canonical entity-type mapping from integration record types —
   ``map_record_type`` coerces crm_leads→Lead, books_invoices→Invoice,
   contacts→Person … applied at the single GraphRAG funnel
   (ingest_structured_data) so every producer benefits. Kill switch
   ATOM_INTEGRATION_TYPE_MAP.

C. Org-bundle records section → ontology objects: apply_bundle now derives
   the same deterministic facts per newly-ingested record (no LLM — imports
   of 100k-record bundles must never bill).

D. Dead ``extract_knowledge`` param removed from LanceDBHandler.add_document
   (accepted-but-never-read since extraction moved to bytewax operators /
   GraphRAG paths); all callers co-updated.
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, DocumentIngestion


def _empty_graph_session():
    """Mock session where every node/edge lookup misses (insert path runs).

    _find_existing_node chains .filter_by(...)/.filter(...)[.limit(...)] —
    each must return None/[]."""
    session = MagicMock()
    q = session.query.return_value
    q.filter.return_value.first.return_value = None
    q.filter.return_value.all.return_value = []
    q.filter.return_value.limit.return_value.all.return_value = []
    q.filter_by.return_value.first.return_value = None
    q.filter_by.return_value.all.return_value = []
    return session


# ---------------------------------------------------------------------------
# GAP B: canonical entity-type mapping
# ---------------------------------------------------------------------------


class TestRecordTypeMapping:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            # direct alias hits
            ("contact", "Person"),
            ("user", "Person"),
            ("customer", "Person"),
            ("company", "Organization"),
            ("account", "Organization"),
            ("lead", "Lead"),
            ("deal", "Deal"),
            ("opportunity", "Deal"),
            ("invoice", "Invoice"),
            ("sales_order", "SalesOrder"),
            ("purchase_order", "PurchaseOrder"),
            ("quote", "Quote"),
            ("shipment", "Shipment"),
            ("message", "Message"),
            ("email", "Message"),
            ("file", "File"),
            ("task", "Task"),
            ("issue", "Task"),
            ("project", "Project"),
            # plurals of plain types
            ("contacts", "Person"),
            ("leads", "Lead"),
            ("deals", "Deal"),
            ("invoices", "Invoice"),
            ("orders", "SalesOrder"),
            ("emails", "Message"),
            ("issues", "Task"),
            ("tasks", "Task"),
            ("projects", "Project"),
            # irregular plurals
            ("companies", "Organization"),
            ("opportunities", "Deal"),
            # platform/module-prefixed compounds (real sync-config values)
            ("crm_leads", "Lead"),
            ("crm_deals", "Deal"),
            ("books_invoices", "Invoice"),
            ("inventory_sales_orders", "SalesOrder"),
            ("projects_tasks", "Task"),
            ("onedrive_file", "File"),
            ("google_drive_file", "File"),
            ("telegram_message", "Message"),
        ],
    )
    def test_maps_to_canonical_slugs(self, raw, expected):
        from core.integration_ontology_bridge import map_record_type

        assert map_record_type(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            # no ontology target yet → verbatim passthrough (None)
            "tickets",
            "ticket",
            "events",
            "attendees",
            "products",
            "campaigns",
            "channels",
            "databases",
            "comments",
            "inventory_items",
            "unknown",
            "",
            None,
        ],
    )
    def test_unmappable_types_pass_through(self, raw):
        from core.integration_ontology_bridge import map_record_type

        assert map_record_type(raw) is None

    def test_mapped_slug_resolves_through_seed_ontology(self):
        """Every mapping target must be a resolvable ontology slug."""
        from core.integration_ontology_bridge import RECORD_TYPE_TO_ONTOLOGY
        from core.ontology.ontology_service import OntologyService

        onto = OntologyService(tenant_id="default")
        for raw_type, slug in RECORD_TYPE_TO_ONTOLOGY.items():
            assert onto.resolve_entity_type(slug) == slug, (
                f"{raw_type!r} maps to non-resolvable slug {slug!r}"
            )

    def test_graphrag_funnel_coerces_record_types(self):
        """ingest_structured_data must store 'crm_leads' nodes as Lead."""
        from core.graphrag_engine import GraphRAGEngine

        engine = GraphRAGEngine.__new__(GraphRAGEngine)
        engine.workspace_id = "ws"
        engine.tenant_id = "t"

        session = _empty_graph_session()

        entity = {
            "name": "Bob",
            "type": "crm_leads",
            "description": "inbound lead",
            "properties": {},
        }
        with patch("core.graphrag_engine.get_db_session") as dbs:
            dbs.return_value.__enter__ = lambda s: session
            dbs.return_value.__exit__ = lambda s, *a: False
            engine.ingest_structured_data(
                workspace_id="ws", tenant_id="t",
                entities=[entity], relationships=[])

        added = [c.args[0] for c in session.add.call_args_list if c.args]
        nodes = [o for o in added if hasattr(o, "type") and hasattr(o, "name")]
        assert any(n.name == "Bob" and n.type == "Lead" for n in nodes), (
            f"expected coerced Lead node, got {[(n.name, n.type) for n in nodes]}"
        )

    def test_graphrag_funnel_kill_switch(self, monkeypatch):
        """ATOM_INTEGRATION_TYPE_MAP=false restores verbatim passthrough."""
        from core.graphrag_engine import GraphRAGEngine

        monkeypatch.setenv("ATOM_INTEGRATION_TYPE_MAP", "false")

        engine = GraphRAGEngine.__new__(GraphRAGEngine)
        engine.workspace_id = "ws"
        engine.tenant_id = "t"

        session = _empty_graph_session()

        entity = {"name": "Bob", "type": "crm_leads", "description": "", "properties": {}}
        with patch("core.graphrag_engine.get_db_session") as dbs:
            dbs.return_value.__enter__ = lambda s: session
            dbs.return_value.__exit__ = lambda s, *a: False
            engine.ingest_structured_data(
                workspace_id="ws", tenant_id="t",
                entities=[entity], relationships=[])

        added = [c.args[0] for c in session.add.call_args_list if c.args]
        nodes = [o for o in added if hasattr(o, "type") and hasattr(o, "name")]
        assert any(n.type == "crm_leads" for n in nodes)


# ---------------------------------------------------------------------------
# GAP A: deterministic business-fact writer
# ---------------------------------------------------------------------------


class FakeFactHandler:
    """Minimal LanceDB-handler double with real id-idempotency semantics."""

    def __init__(self):
        self.rows = {}
        self.calls = []

    def get_document_by_id(self, table_name, doc_id):
        return self.rows.get((table_name, doc_id))

    def add_document(self, **kwargs):
        self.calls.append(kwargs)
        self.rows[(kwargs["table_name"], kwargs["doc_id"])] = {
            "id": kwargs["doc_id"],
            "metadata": kwargs.get("metadata") or {},
        }
        return True

    def fact_calls(self):
        return [c for c in self.calls if c.get("table_name") == "business_facts"]


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    # Same contract as tests/test_org_memory_bundle.py — org signing key path.
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(tmp_path / "org_sharing_key"))


def _record_kwargs(**over):
    kw = dict(
        workspace_id="ws1",
        tenant_id="t1",
        integration_id="hubspot",
        record_type="contacts",
        record={"id": "ext-1", "name": "Bob", "email": "bob@acme.com"},
        text="contact Bob bob@acme.com lifecyclestage customer created 2026-08-01",
        sensitivity="internal",
    )
    kw.update(over)
    return kw


class TestFactWriter:
    async def test_writes_unverified_fact_with_metadata_contract(self):
        from core.integration_ontology_bridge import write_integration_fact

        handler = FakeFactHandler()

        stats = await write_integration_fact(**_record_kwargs(memory_handler=handler))

        assert stats == {"written": 1, "skipped": 0}
        assert len(handler.fact_calls()) == 1
        kw = handler.fact_calls()[0]
        expected_id = "intfact:hubspot:ext-1"
        assert kw["doc_id"] == expected_id
        meta = kw["metadata"]
        # Reader contract (agent_world_model.get_relevant_business_facts)
        assert meta["id"] == expected_id          # top-level id == metadata.id
        assert meta["fact"]
        assert isinstance(meta["citations"], list) and meta["citations"]
        assert meta["source_agent_id"] == "integration_bridge"
        assert meta["verification_status"] == "unverified"
        assert meta["type"] == "business_fact"
        # P4/export contract: sensitivity stamped so bundle export filters work
        assert meta["sensitivity"] == "internal"
        assert meta["domain"] == "Person"         # mapped from contacts
        assert meta["content_hash"]               # versioning stamp present
        # Text representation mirrors record_business_fact shape
        assert kw["text"].startswith("Fact: ")
        assert "Status: unverified" in kw["text"]

    async def test_idempotent_on_unchanged_content(self):
        from core.integration_ontology_bridge import write_integration_fact

        handler = FakeFactHandler()
        kw = _record_kwargs(memory_handler=handler)

        first = await write_integration_fact(**kw)
        second = await write_integration_fact(**kw)

        assert first["written"] == 1
        assert second == {"written": 0, "skipped": "unchanged"}
        assert len(handler.fact_calls()) == 1

    async def test_changed_content_appends_new_version(self):
        from core.integration_ontology_bridge import write_integration_fact

        handler = FakeFactHandler()
        base = _record_kwargs(memory_handler=handler)

        await write_integration_fact(**base)
        second = await write_integration_fact(
            **{**base, "text": base["text"] + " dealvalue 5000 stage proposal"})

        assert second["written"] == 1
        assert len(handler.fact_calls()) == 2

    async def test_flag_off_disables_writer(self, monkeypatch):
        from core.integration_ontology_bridge import write_integration_fact

        monkeypatch.setenv("ATOM_INTEGRATION_FACTS_ENABLED", "false")
        handler = MagicMock()

        stats = await write_integration_fact(**_record_kwargs(memory_handler=handler))

        assert stats == {"written": 0, "skipped": "disabled"}
        handler.add_document.assert_not_called()

    async def test_budget_cap_enforced(self):
        from core.integration_ontology_bridge import FactBudget, write_integration_fact

        handler = FakeFactHandler()
        budget = FactBudget(max_per_run=1)

        s1 = await write_integration_fact(
            **_record_kwargs(record={"id": "a"}, memory_handler=handler, budget=budget))
        s2 = await write_integration_fact(
            **_record_kwargs(record={"id": "b"}, memory_handler=handler, budget=budget))

        assert s1["written"] == 1
        assert s2 == {"written": 0, "skipped": "budget"}
        assert len(handler.fact_calls()) == 1

    async def test_no_handler_skips_gracefully(self):
        from core.integration_ontology_bridge import write_integration_fact

        stats = await write_integration_fact(**_record_kwargs(memory_handler=None))
        assert stats == {"written": 0, "skipped": "no_handler"}

    async def test_derive_fact_deterministic_and_salient(self):
        from core.integration_ontology_bridge import derive_fact

        record = {"id": "x1", "name": "Acme Renewal", "amount": 5000,
                  "stage": "proposal", "noise_internal_field": "zz"}
        f1 = derive_fact("salesforce", "opportunities", record,
                         "opportunity Acme Renewal amount 5000")
        f2 = derive_fact("salesforce", "opportunities", record,
                         "opportunity Acme Renewal amount 5000")
        assert f1 == f2                      # deterministic
        assert "Acme Renewal" in f1["fact"]  # subject picked up
        assert f1["domain"] == "Deal"
        assert "noise_internal_field" not in f1["fact"]

    async def test_replay_cannot_downgrade_sensitivity(self):
        """Unchanged content never rewrites — a replay claiming lower
        sensitivity cannot overwrite the stored row."""
        from core.integration_ontology_bridge import write_integration_fact

        handler = FakeFactHandler()
        base = _record_kwargs(sensitivity="confidential", memory_handler=handler)

        await write_integration_fact(**base)
        replay = await write_integration_fact(**{**base, "sensitivity": "internal"})

        assert replay == {"written": 0, "skipped": "unchanged"}
        stored = handler.fact_calls()[0]["metadata"]
        assert stored["sensitivity"] == "confidential"


# ---------------------------------------------------------------------------
# GAP A wiring: hybrid sync loop
# ---------------------------------------------------------------------------


class TestHybridSyncHook:
    async def test_sync_writes_facts_per_record(self, monkeypatch):
        import core.integration_ontology_bridge as bridge
        from core.hybrid_data_ingestion import HybridDataIngestionService

        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "ws1"
        svc.tenant_id = "t1"
        svc.memory_handler = MagicMock()
        svc.graphrag = None
        svc.usage_stats = {}
        svc.sync_configs = {}
        svc._sync_tasks = {}
        svc._persist_integration = MagicMock()

        async def fake_fetch(integration_id, config, discovery_mode=False, role=None):
            return [{"id": "r1", "type": "crm_leads",
                     "name": "Bob", "email": "bob@acme.com"}]

        svc._fetch_integration_data = fake_fetch

        # Schema-discovery touches SessionLocal — keep it off the real DB.
        import core.database as database
        monkeypatch.setattr(database, "SessionLocal", MagicMock())

        calls = []

        async def fake_write(**kwargs):
            calls.append(kwargs)
            return {"written": 1, "skipped": 0}

        monkeypatch.setattr(bridge, "write_integration_fact", fake_write)

        result = await svc.sync_integration_data("zoho", force=True)

        assert len(calls) == 1
        assert calls[0]["integration_id"] == "zoho"
        assert calls[0]["workspace_id"] == "ws1"
        assert calls[0]["sensitivity"] in ("internal", "confidential",
                                           "restricted", "public")
        assert result["facts_written"] == 1


# ---------------------------------------------------------------------------
# GAP A wiring: webhook basic tier
# ---------------------------------------------------------------------------


class TestWebhookTierHook:
    async def test_basic_tier_writes_facts_for_non_comm_records(self, monkeypatch):
        import core.integration_ontology_bridge as bridge
        from core.ingestion_pipeline import IngestionPipelineService

        svc = IngestionPipelineService.__new__(IngestionPipelineService)
        svc.tenant_id = "t1"
        svc.workspace_id = "ws1"
        svc.lancedb = MagicMock()
        svc.usage_tracker = MagicMock()
        svc.usage_tracker.check_quota_before_job = AsyncMock(
            return_value={"allowed": True})

        async def fake_transform(integration_id, webhook_data):
            return [{"id": "w1", "type": "contact", "name": "Zia",
                     "email": "zia@corp.com"}]

        svc._transform_webhook_payload = fake_transform
        svc._is_communication_record = MagicMock(return_value=False)
        svc._record_to_text = MagicMock(
            return_value="contact Zia zia@corp.com created 2026-08-01 long enough")
        svc._is_doc_already_ingested = MagicMock(return_value=False)
        svc._process_multi_entity_extraction = AsyncMock(return_value=None)
        svc._extract_structured_entities = MagicMock(
            return_value=(None, None, None))
        svc.graphrag = MagicMock()
        svc._record_doc_ingestion = MagicMock()

        calls = []

        async def fake_write(**kwargs):
            calls.append(kwargs)
            return {"written": 1, "skipped": 0}

        monkeypatch.setattr(bridge, "write_integration_fact", fake_write)

        result = await svc.process_webhook_payload_tiered(
            "hubspot", {"eventName": "contact.created"})

        assert len(calls) == 1
        assert calls[0]["integration_id"] == "hubspot"
        assert result["tier"] in ("basic", "deep")


# ---------------------------------------------------------------------------
# GAP C: org-bundle records section derives facts on import
# ---------------------------------------------------------------------------


def _signed_records_envelope(records):
    from core.ingestion_profile_service import canonical_payload, payload_hash
    from core import org_sharing_crypto

    payload = {
        "kind": "atom_org_data_bundle",
        "bundle_version": 2,
        "records": records,
        "tombstones": [],
    }
    envelope = {"kind": "atom_org_data_bundle", "payload": payload}
    envelope["payload_hash"] = payload_hash(payload)
    envelope["signature"], envelope["signed_by"] = org_sharing_crypto.sign_payload(
        canonical_payload(payload))
    return envelope


class TestBundleRecordsFacts:
    async def test_new_records_derive_facts_once(self, key_file):
        """Records section must now produce business-fact rows on import."""
        from core.models import BundleImport, IngestedDocument, OrgPublicKey
        from core.org_data_bundle_service import OrgDataBundleService

        tables = [
            IngestedDocument.__table__,
            DocumentIngestion.__table__,
            BundleImport.__table__,
            OrgPublicKey.__table__,
        ]
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=tables)
        db = sessionmaker(bind=engine)()

        records = [{
            "integration_id": "crm",
            "external_id": "L-1",
            "file_name": "lead.json",
            "file_type": "application/json",
            "content_preview": "Acme lead Bob bob@acme.com stage new source web",
            "external_modified_at": None,
            "sensitivity": "internal",
            "content_hash": "h1",
        }]
        envelope = _signed_records_envelope(records)

        handler = FakeFactHandler()
        svc = OrgDataBundleService()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            result = await svc.apply_bundle(db, envelope, workspace_id="member-b")

        fact_calls = handler.fact_calls()
        assert len(fact_calls) == 1, "bundle record must derive a business fact"
        kw = fact_calls[0]
        assert kw["metadata"]["verification_status"] == "unverified"
        assert kw["metadata"]["sensitivity"] == "internal"
        assert result.get("facts_written") == 1

        # Re-import unchanged → fact NOT rewritten (store-level idempotency)
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            result2 = await svc.apply_bundle(db, envelope, workspace_id="member-b")
        assert len(handler.fact_calls()) == 1
        assert result2.get("facts_written") == 0
        db.close()


# ---------------------------------------------------------------------------
# GAP D: dead extract_knowledge param removal
# ---------------------------------------------------------------------------


class TestDeadParamRemoved:
    def test_signature_has_no_extract_knowledge(self):
        from core.lancedb_handler import LanceDBHandler

        params = inspect.signature(LanceDBHandler.add_document).parameters
        assert "extract_knowledge" not in params

    def test_passing_extract_knowledge_raises(self):
        """Old callers must fail loudly (TypeError), not silently no-op."""
        from core.lancedb_handler import LanceDBHandler

        with pytest.raises(TypeError):
            LanceDBHandler.add_document(
                object(), table_name="t", text="x", extract_knowledge=True)

    def test_no_production_callers_remain(self):
        """Every add_document caller dropped the dead kwarg."""
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parents[1]
        self_name = pathlib.Path(__file__).name
        offenders = []
        pattern = re.compile(r"add_document\([^)]*extract_knowledge", re.DOTALL)
        for py in root.rglob("*.py"):
            sp = str(py)
            if "/venv/" in sp or "/node_modules/" in sp:
                continue
            if py.name == self_name:  # the TypeError probe below
                continue
            src = py.read_text(errors="ignore")
            if "extract_knowledge" not in src:
                continue
            for m in re.finditer(r"add_document\s*\(", src):
                # grab the balanced-ish call region
                region = src[m.start():m.start() + 600]
                region = region.split("\n\n")[0]
                if "extract_knowledge" in region:
                    offenders.append(f"{py.relative_to(root)}")
        assert offenders == [], f"stale extract_knowledge callers: {offenders}"
