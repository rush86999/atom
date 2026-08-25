"""Round 84 — data-journey closure: tombstoned records must retract facts.

Gap: org-bundle import derives deterministic business facts per record
(``intfact:{integration_id}:{record_id}`` in business_facts). When the
source later sends a TOMBSTONE for that record, apply_bundle only set
``IngestedDocument.freshness_status='removed'`` — the derived fact stayed
live in business_facts forever, so agents kept citing deleted data.

Fix: bridge gains ``retract_integration_facts`` (delete every stored
version via delete_documents_by_id; never raises); apply_bundle's
tombstone loop retracts the fact for each removed doc it can trace back
to its integration.
"""

import json
from unittest.mock import MagicMock

import pytest


class FakeFactHandler:
    """Handler double with real id semantics (mirrors R84 ontology tests)."""

    def __init__(self):
        self.rows = {}
        self.deleted = []

    def get_document_by_id(self, table_name, doc_id):
        return self.rows.get((table_name, doc_id))

    def add_document(self, **kwargs):
        self.rows[(kwargs["table_name"], kwargs["doc_id"])] = {
            "id": kwargs["doc_id"],
            "metadata": kwargs.get("metadata") or {},
        }
        return True

    def delete_documents_by_id(self, table_name, doc_id):
        self.deleted.append((table_name, doc_id))
        existed = self.rows.pop((table_name, doc_id), None) is not None
        return True


# ---------------------------------------------------------------------------
# Bridge: retract_integration_facts
# ---------------------------------------------------------------------------


class TestRetractIntegrationFacts:
    async def test_deletes_every_version_of_the_fact(self):
        from core.integration_ontology_bridge import retract_integration_facts

        handler = FakeFactHandler()

        stats = await retract_integration_facts(
            workspace_id="ws1",
            integration_id="hubspot",
            record_ids=["ext-1", "ext-2"],
            memory_handler=handler,
        )

        assert stats == {"retracted": 2}
        assert ("business_facts", "intfact:hubspot:ext-1") in handler.deleted
        assert ("business_facts", "intfact:hubspot:ext-2") in handler.deleted

    async def test_no_handler_is_noop(self):
        from core.integration_ontology_bridge import retract_integration_facts

        stats = await retract_integration_facts(
            workspace_id="ws", integration_id="crm",
            record_ids=["x"], memory_handler=None,
        )
        assert stats == {"retracted": 0}

    async def test_empty_record_ids(self):
        from core.integration_ontology_bridge import retract_integration_facts

        stats = await retract_integration_facts(
            workspace_id="ws", integration_id="crm",
            record_ids=[], memory_handler=FakeFactHandler(),
        )
        assert stats == {"retracted": 0}

    async def test_handler_error_never_raises(self):
        from core.integration_ontology_bridge import retract_integration_facts

        handler = MagicMock()
        handler.delete_documents_by_id.side_effect = RuntimeError("lance down")

        stats = await retract_integration_facts(
            workspace_id="ws", integration_id="crm",
            record_ids=["a", "b"], memory_handler=handler,
        )
        assert stats == {"retracted": 0}

    async def test_flag_off_disables_retraction(self, monkeypatch):
        from core.integration_ontology_bridge import retract_integration_facts

        monkeypatch.setenv("ATOM_INTEGRATION_FACTS_ENABLED", "false")
        handler = MagicMock()
        stats = await retract_integration_facts(
            workspace_id="ws", integration_id="crm",
            record_ids=["a"], memory_handler=handler,
        )
        assert stats == {"retracted": 0}
        handler.delete_documents_by_id.assert_not_called()


# ---------------------------------------------------------------------------
# Wiring: apply_bundle tombstones retract derived facts
# ---------------------------------------------------------------------------


def _signed_envelope(payload):
    from core.ingestion_profile_service import canonical_payload, payload_hash
    from core import org_sharing_crypto

    envelope = {"kind": "atom_org_data_bundle", "payload": payload}
    envelope["payload_hash"] = payload_hash(payload)
    envelope["signature"], envelope["signed_by"] = org_sharing_crypto.sign_payload(
        canonical_payload(payload))
    return envelope


class TestBundleTombstoneRetraction:
    async def test_tombstone_retracts_derived_fact(self):
        from core.models import Base, DocumentIngestion
        from core.models import BundleImport, IngestedDocument, OrgPublicKey
        from core.org_data_bundle_service import OrgDataBundleService

        tables = [
            IngestedDocument.__table__,
            DocumentIngestion.__table__,
            BundleImport.__table__,
            OrgPublicKey.__table__,
        ]
        import sqlalchemy
        engine = sqlalchemy.create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=tables)
        db = sqlalchemy.orm.sessionmaker(bind=engine)()

        record = {
            "integration_id": "crm",
            "external_id": "L-9",
            "file_name": "lead.json",
            "file_type": "application/json",
            "content_preview": "Acme lead Bob bob@acme.com stage new source web",
            "external_modified_at": None,
            "sensitivity": "internal",
            "content_hash": "h9",
        }

        handler = FakeFactHandler()
        svc = OrgDataBundleService()

        # Import → derive fact.
        v1 = _signed_envelope({
            "kind": "atom_org_data_bundle", "bundle_version": 2,
            "records": [record], "tombstones": [],
        })
        with patch_target(handler):
            await svc.apply_bundle(db, v1, workspace_id="member-b")
        fact_id = "intfact:crm:L-9"
        assert ("business_facts", fact_id) not in [
            d for d in handler.deleted]

        # Tombstone the record → fact must be retracted.
        v2 = _signed_envelope({
            "kind": "atom_org_data_bundle", "bundle_version": 2,
            "records": [], "tombstones": ["L-9"],
        })
        with patch_target(handler):
            result = await svc.apply_bundle(db, v2, workspace_id="member-b")

        assert ("business_facts", fact_id) in handler.deleted, (
            "tombstoned record must retract its derived business fact"
        )
        assert result.get("facts_retracted") == 1
        db.close()


def patch_target(handler):
    from unittest.mock import patch
    return patch("core.lancedb_handler.get_lancedb_handler", return_value=handler)
