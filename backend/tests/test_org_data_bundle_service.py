"""Org Data Bundle Service — Phase 2 opt-in data sharing.

Sensitivity gate, signature-before-parse, idempotent import (dedup),
tombstones, record cap, credential fail-closed.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import org_sharing_crypto
from core.models import (
    Base,
    BundleExport,
    BundleImport,
    DocumentIngestion,
    GraphEdge,
    GraphNode,
    IngestedDocument,
    KnowledgeDocument,
    OrgPublicKey,
)
from core.org_data_bundle_service import (
    MAX_RECORDS_PER_BUNDLE,
    BundleError,
    OrgDataBundleService,
)

TABLES = [
    IngestedDocument.__table__,
    DocumentIngestion.__table__,
    BundleExport.__table__,
    BundleImport.__table__,
    OrgPublicKey.__table__,
    # Phase 2b: default exports include graph + texts sections.
    GraphNode.__table__,
    GraphEdge.__table__,
    KnowledgeDocument.__table__,
]


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(tmp_path / "org_sharing_key"))


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def add_doc(db, external_id, sensitivity="internal", integration_id="salesforce", preview="Acme contact data"):
    db.add(IngestedDocument(
        workspace_id="default", tenant_id="default", integration_id=integration_id,
        external_id=external_id, file_name=f"{external_id}.json", file_path="/tmp/x",
        file_type="json", content_preview=preview, sensitivity=sensitivity,
        external_modified_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    ))
    db.commit()


class TestExport:
    async def test_sensitivity_gate_default_excludes_high(self, key_file, db):
        add_doc(db, "pub-1", "public")
        add_doc(db, "int-1", "internal")
        add_doc(db, "conf-1", "confidential")
        add_doc(db, "restr-1", "restricted")
        env = OrgDataBundleService().build_bundle(db, "default", sources=["salesforce"])
        ids = {r["external_id"] for r in env["payload"]["records"]}
        assert ids == {"pub-1", "int-1"}
        assert env["excluded_by_sensitivity"] == {"confidential": 1, "restricted": 1}

    async def test_raised_ceiling_scoped_subbundle(self, key_file, db):
        add_doc(db, "conf-1", "confidential")
        add_doc(db, "restr-1", "restricted")
        env = OrgDataBundleService().build_bundle(
            db, "default", sources=["salesforce"], sensitivity_ceiling="confidential",
            destination="finance-team",
        )
        ids = {r["external_id"] for r in env["payload"]["records"]}
        assert ids == {"conf-1"}
        assert env["excluded_by_sensitivity"] == {"restricted": 1}
        export = db.query(BundleExport).one()
        assert export.destination == "finance-team"
        assert export.record_count == 1

    async def test_invalid_ceiling_rejected(self, key_file, db):
        with pytest.raises(BundleError):
            OrgDataBundleService().build_bundle(db, "default", ["salesforce"], sensitivity_ceiling="wild")

    async def test_source_filter(self, key_file, db):
        add_doc(db, "sf-1", integration_id="salesforce")
        add_doc(db, "sl-1", integration_id="slack")
        env = OrgDataBundleService().build_bundle(db, "default", sources=["slack"])
        assert all(r["integration_id"] == "slack" for r in env["payload"]["records"])

    async def test_export_is_signed_and_audited(self, key_file, db):
        add_doc(db, "int-1")
        svc = OrgDataBundleService()
        env = svc.build_bundle(db, "default", sources=["salesforce"])
        assert db.query(BundleExport).count() == 1
        # Round-trip import on same instance verifies (own key).
        result = await svc.apply_bundle(db, env, workspace_id="default")
        assert result["records_ingested"] == 1

    async def test_record_cap(self, key_file, db, monkeypatch):
        monkeypatch.setattr("core.org_data_bundle_service.MAX_RECORDS_PER_BUNDLE", 2)
        for i in range(5):
            add_doc(db, f"doc-{i}")
        env = OrgDataBundleService().build_bundle(db, "default", sources=["salesforce"])
        assert len(env["payload"]["records"]) == 2


class TestImport:
    async def test_import_creates_rows_idempotently(self, key_file, db):
        add_doc(db, "int-1")
        svc = OrgDataBundleService()
        env = svc.build_bundle(db, "default", sources=["salesforce"])

        engine2 = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine2, tables=TABLES)
        db2 = sessionmaker(bind=engine2)()

        r1 = await svc.apply_bundle(db2, env, workspace_id="member-b", tenant_id="t")
        assert r1["records_ingested"] == 1
        assert r1["records_skipped"] == 0
        doc = db2.query(IngestedDocument).one()
        assert doc.external_id == "int-1"
        assert doc.sensitivity == "internal"

        # Re-import: unchanged hash → skipped, no duplicates.
        r2 = await svc.apply_bundle(db2, env, workspace_id="member-b")
        assert r2["records_ingested"] == 0
        assert r2["records_skipped"] == 1
        assert db2.query(IngestedDocument).count() == 1
        assert db2.query(DocumentIngestion).count() == 1
        assert db2.query(BundleImport).count() == 2
        db2.close()

    async def test_reimport_after_change_reingests(self, key_file, db):
        add_doc(db, "int-1")
        svc = OrgDataBundleService()
        env = svc.build_bundle(db, "default", sources=["salesforce"])
        await svc.apply_bundle(db, env, workspace_id="member-b")

        # Source changes → new hash → re-ingest (update, not duplicate).
        db.query(IngestedDocument).filter_by(external_id="int-1").update(
            {"content_preview": "updated", "external_modified_at": datetime(2026, 8, 15, tzinfo=timezone.utc)}
        )
        db.commit()
        env2 = svc.build_bundle(db, "default", sources=["salesforce"])
        r = await svc.apply_bundle(db, env2, workspace_id="member-b")
        assert r["records_ingested"] == 1
        assert db.query(IngestedDocument).filter_by(workspace_id="member-b").count() == 1

    async def test_tombstones_mark_removed(self, key_file, db):
        add_doc(db, "int-1")
        svc = OrgDataBundleService()
        env = svc.build_bundle(db, "default", sources=["salesforce"])
        env["payload"]["tombstones"] = ["int-1"]
        # Re-sign after mutation (simulating exporter deletion propagation).
        from core.ingestion_profile_service import canonical_payload, payload_hash
        env["payload_hash"] = payload_hash(env["payload"])
        env["signature"], env["signed_by"] = org_sharing_crypto.sign_payload(canonical_payload(env["payload"]))

        await svc.apply_bundle(db, env, workspace_id="member-b")
        imported = db.query(IngestedDocument).filter_by(workspace_id="member-b", external_id="int-1").one()
        assert imported.freshness_status == "removed"

    async def test_rejects_unsigned(self, key_file, db):
        add_doc(db, "int-1")
        env = OrgDataBundleService().build_bundle(db, "default", sources=["salesforce"])
        del env["signature"]
        with pytest.raises(BundleError, match="not signed"):
            await OrgDataBundleService().apply_bundle(db, env, workspace_id="default")

    async def test_rejects_tampered(self, key_file, db):
        add_doc(db, "int-1")
        env = OrgDataBundleService().build_bundle(db, "default", sources=["salesforce"])
        env["payload"]["records"][0]["content_preview"] = "injected"
        with pytest.raises(BundleError, match="tampered"):
            await OrgDataBundleService().apply_bundle(db, env, workspace_id="default")

    async def test_rejects_unknown_signer(self, key_file, db, tmp_path, monkeypatch):
        add_doc(db, "int-1")
        env = OrgDataBundleService().build_bundle(db, "default", sources=["salesforce"])
        monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(tmp_path / "other"))
        with pytest.raises(BundleError, match="signature"):
            await OrgDataBundleService().apply_bundle(db, env, workspace_id="default")

    async def test_rejects_wrong_kind_and_version(self, key_file, db):
        with pytest.raises(BundleError):
            await OrgDataBundleService().apply_bundle(db, {"kind": "nope"}, "default")
        bad = {"kind": "atom_org_data_bundle",
               "payload": {"bundle_version": 99}, "signature": "x", "payload_hash": "y"}
        with pytest.raises(BundleError, match="bundle_version"):
            await OrgDataBundleService().apply_bundle(db, bad, "default")

    async def test_rejects_oversize_bundle(self, key_file, db, monkeypatch):
        add_doc(db, "int-1")
        add_doc(db, "int-2")
        # Export under the real cap, then inflate + re-sign so the envelope
        # is structurally valid but exceeds the import-side cap.
        env = OrgDataBundleService().build_bundle(db, "default", sources=["salesforce"])
        env["payload"]["records"] = env["payload"]["records"] * (MAX_RECORDS_PER_BUNDLE + 1)
        from core.ingestion_profile_service import canonical_payload, payload_hash
        env["payload_hash"] = payload_hash(env["payload"])
        env["signature"], _ = org_sharing_crypto.sign_payload(canonical_payload(env["payload"]))
        with pytest.raises(BundleError, match="cap"):
            await OrgDataBundleService().apply_bundle(db, env, workspace_id="default")
