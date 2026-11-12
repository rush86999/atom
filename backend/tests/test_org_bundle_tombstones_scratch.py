# -*- coding: utf-8 -*-
"""Scratch regression: removed documents never re-enter a snapshot bundle.

Synthetic in-memory data only (no live DB, no network). A document deleted at
its source keeps a durable ``freshness_status='removed'`` row by design; the
snapshot export must omit that row's body instead of treating it as content.

Snapshot tombstones are intentionally NOT asserted as propagated: the Phase-2
import contract keys tombstones by bare ``external_id`` with no source
identity/version, so a multi-source snapshot cannot safely erase by that key.
These tests pin the safe behavior (omission) until that contract changes.
"""
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, BundleExport, IngestedDocument
from core.org_data_bundle_service import OrgDataBundleService

TABLES = [IngestedDocument.__table__, BundleExport.__table__]


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(tmp_path / "org_sharing_key"))


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add_doc(
    db,
    external_id,
    *,
    workspace_id="default",
    integration_id="salesforce",
    sensitivity="internal",
    preview="contact data",
    file_name=None,
    freshness_status="fresh",
):
    db.add(IngestedDocument(
        workspace_id=workspace_id,
        tenant_id="default",
        integration_id=integration_id,
        external_id=external_id,
        file_name=file_name or f"{external_id}.json",
        file_path=f"/tmp/{external_id}",
        file_type="json",
        content_preview=preview,
        sensitivity=sensitivity,
        freshness_status=freshness_status,
        external_modified_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    ))
    db.commit()


class TestSnapshotExportOmitsRemovedDocuments:
    def test_removed_record_body_is_never_serialized(self, key_file, db):
        add_doc(db, "live-1", preview="ACTIVE CONTACT")
        add_doc(
            db,
            "dead-1",
            preview="TOMBSTONED SECRET BODY",
            file_name="dead-secret.json",
            freshness_status="removed",
        )

        envelope = OrgDataBundleService().build_bundle(
            db, "default", sources=["salesforce"], include=["records"]
        )
        payload = envelope["payload"]

        assert [r["external_id"] for r in payload["records"]] == ["live-1"]
        assert payload["sensitivity_breakdown"] == {"internal": 1}
        serialized = json.dumps(payload)
        assert "TOMBSTONED SECRET BODY" not in serialized
        assert "dead-secret.json" not in serialized

        # No bare-id snapshot tombstone: ambiguous across sources at import.
        assert payload["tombstones"] == []

    def test_removed_high_sensitivity_stays_behind_the_ceiling(self, key_file, db):
        add_doc(
            db,
            "dead-conf-1",
            sensitivity="confidential",
            preview="CONFIDENTIAL TOMBSTONED BODY",
            freshness_status="removed",
        )

        envelope = OrgDataBundleService().build_bundle(
            db, "default", sources=["salesforce"], include=["records"]
        )

        assert envelope["payload"]["records"] == []
        assert envelope["excluded_by_sensitivity"] == {"confidential": 1}
        assert envelope["payload"]["tombstones"] == []
        assert "CONFIDENTIAL TOMBSTONED BODY" not in json.dumps(envelope["payload"])

    def test_workspace_and_source_gating_still_apply(self, key_file, db):
        add_doc(db, "live-sf", integration_id="salesforce", preview="ACTIVE SF")
        add_doc(
            db,
            "dead-slack",
            integration_id="slack",
            preview="DEAD SLACK BODY",
            freshness_status="removed",
        )
        add_doc(
            db,
            "dead-other-ws",
            workspace_id="other-workspace",
            integration_id="salesforce",
            preview="DEAD FOREIGN WORKSPACE BODY",
            freshness_status="removed",
        )

        envelope = OrgDataBundleService().build_bundle(
            db, "default", sources=["salesforce"], include=["records"]
        )

        assert [r["external_id"] for r in envelope["payload"]["records"]] == ["live-sf"]
        serialized = json.dumps(envelope["payload"])
        assert "DEAD SLACK BODY" not in serialized
        assert "DEAD FOREIGN WORKSPACE BODY" not in serialized
        assert envelope["payload"]["sources"] == ["salesforce"]
