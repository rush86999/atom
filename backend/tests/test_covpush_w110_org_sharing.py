# -*- coding: utf-8 -*-
"""Org Ingestion Sharing (docs/architecture/ORG_INGESTION_SHARING_PLAN.md) — w110.

Covers Phases 0-2:
- Phase 0: hybrid ingestion pipeline state persistence (ingestion_settings
  columns; sync_configs + usage_stats survive restart).
- Phase 1: Ed25519 org key registry (org_sharing_crypto) + signed ingestion
  profile export/import (ingestion_profile_service).
- Phase 2: signed org data bundle export/import with the P4 sensitivity gate,
  document_ingestions dedup idempotency, tombstones, and audit rows
  (org_data_bundle_service).

Security invariants pinned (plan §6): strip_credentials fail-closed on every
export; restricted/confidential excluded by default; signature verified BEFORE
parse; rejected imports are AUDITED; record caps; kill switch
ATOM_ORG_SHARING_ENABLED defaults off.

DB-backed tests use the worker_database fixture (SESSION-scoped in-memory
SQLite, full schema), so every test cleans its tables after itself. Phase 0
tests patch core.hybrid_data_ingestion.SessionLocal to that fixture's
sessionmaker and re-enable ATOM_INGESTION_PERSIST_STATE (the root conftest
disables persistence by default to keep pre-existing suites order-free).
"""
import asyncio
import base64
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.hybrid_data_ingestion import HybridDataIngestionService, SyncConfiguration

ORG_TABLES = (
    "IngestionSettings",
    "OrgPublicKey",
    "IngestionProfileImport",
    "BundleExport",
    "BundleImport",
    "IngestedDocument",
    "DocumentIngestion",
)


# =========================================================================== #
# Fixtures
# =========================================================================== #


@pytest.fixture
def key_file_env(tmp_path, monkeypatch):
    """Point the org-sharing key file at a tmp location for isolation."""
    key_file = tmp_path / "org_sharing_key"
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(key_file))
    return key_file


@pytest.fixture
def sharing_enabled(monkeypatch):
    monkeypatch.setenv("ATOM_ORG_SHARING_ENABLED", "true")


@pytest.fixture(autouse=True)
def clean_org_tables(worker_database):
    """The worker DB is session-scoped; wipe org-sharing rows after each test."""
    yield
    import core.models as m

    db = worker_database()
    try:
        for name in ORG_TABLES:
            model = getattr(m, name, None)
            if model is not None:
                db.query(model).delete()
        db.commit()
    finally:
        db.close()


def _make_user(user_id="w110-user", workspace_id=None, tenant_id=None):
    return SimpleNamespace(id=user_id, workspace_id=workspace_id, tenant_id=tenant_id)


def _foreign_keypair():
    """A keypair that is NOT the instance's own org-sharing key."""
    private = Ed25519PrivateKey.generate()
    public_b64 = base64.b64encode(
        private.public_key().public_bytes(
            encoding=__import__("cryptography").hazmat.primitives.serialization.Encoding.Raw,
            format=__import__("cryptography").hazmat.primitives.serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    return private, public_b64


# =========================================================================== #
# Phase 1 — org_sharing_crypto (Ed25519 key registry)
# =========================================================================== #


class TestOrgSharingCrypto:
    def test_keypair_generated_once_and_persisted_0600(self, key_file_env):
        from core import org_sharing_crypto as c

        k1 = c.get_or_create_private_key()
        k2 = c.get_or_create_private_key()
        assert k1.public_key() == k2.public_key()  # loaded, not regenerated
        assert key_file_env.exists()
        assert (key_file_env.stat().st_mode & 0o777) == 0o600

    def test_sign_verify_round_trip_own_key(self, key_file_env, worker_database):
        from core import org_sharing_crypto as c

        db = worker_database()
        payload = b"org ingestion profile payload"
        signature, _ = c.sign_payload(payload)
        assert c.verify_payload(db, payload, signature, workspace_id="default")

        # Tampered payload must fail
        assert not c.verify_payload(db, payload + b"x", signature, workspace_id="default")

    def test_foreign_signer_fails_until_registered(self, key_file_env, worker_database):
        """A signer whose key was never registered must not verify."""
        from core import org_sharing_crypto as c

        db = worker_database()
        private, pub_b64 = _foreign_keypair()
        payload = b"hello-bundle"
        signature = base64.b64encode(private.sign(payload)).decode("ascii")

        assert c.verify_payload(db, payload, signature, workspace_id="default") is False

        # …B registers A's public key…
        row = c.register_public_key(db, pub_b64, label="member-a", workspace_id="default")
        assert row.fingerprint == c.fingerprint(base64.b64decode(pub_b64))
        # …and now B can verify.
        assert c.verify_payload(db, payload, signature, workspace_id="default") is True

    def test_register_public_key_rejects_bad_length(self, key_file_env, worker_database):
        from core import org_sharing_crypto as c

        db = worker_database()
        with pytest.raises(ValueError):
            c.register_public_key(
                db, base64.b64encode(b"tooshort").decode(), label="x", workspace_id="default"
            )

    def test_register_public_key_idempotent(self, key_file_env, worker_database):
        from core import org_sharing_crypto as c
        from core.models import OrgPublicKey

        db = worker_database()
        pub = c.public_key_b64(c.get_or_create_private_key())
        c.register_public_key(db, pub, label="first", workspace_id="default")
        c.register_public_key(db, pub, label="second", workspace_id="default")
        rows = db.query(OrgPublicKey).filter(OrgPublicKey.public_key == pub).all()
        assert len(rows) == 1
        assert rows[0].label == "second"

    def test_bad_base64_signature_fails_closed(self, key_file_env, worker_database):
        from core import org_sharing_crypto as c

        db = worker_database()
        assert c.verify_payload(db, b"data", "!!!not-base64!!!", workspace_id="default") is False

    def test_empty_registry_own_key_still_verifies(self, key_file_env, worker_database):
        """The own key is an implicit candidate even with a fresh registry."""
        from core import org_sharing_crypto as c

        db = worker_database()
        sig, _ = c.sign_payload(b"x")
        assert c.verify_payload(db, b"x", sig, workspace_id="default")

    def test_fingerprint_is_sha256(self, key_file_env):
        from core import org_sharing_crypto as c

        raw = base64.b64decode(c.public_key_b64(c.get_or_create_private_key()))
        assert c.fingerprint(raw) == hashlib.sha256(raw).hexdigest()


# =========================================================================== #
# Phase 0 — hybrid ingestion state persistence
# =========================================================================== #


class TestPhase0Persistence:
    @contextmanager
    def _persisted(self, session_factory, workspace="w110-p0", persistence=True):
        """Construct the service with the worker DB as its persistence target.

        The patch stays open for the whole with-block so write-throughs during
        mutations hit the in-memory DB (SessionLocal is resolved at call time).
        """
        with patch("core.hybrid_data_ingestion.SessionLocal", session_factory), patch.dict(
            os.environ, {"ATOM_INGESTION_PERSIST_STATE": "true" if persistence else "false"}
        ):
            yield HybridDataIngestionService(workspace_id=workspace, tenant_id="default")

    def test_enable_sync_survives_restart(self, worker_database):
        sf = worker_database
        with self._persisted(sf) as s1:
            s1.enable_auto_sync(
                "salesforce",
                config=SyncConfiguration(
                    integration_id="salesforce",
                    entity_types=["contacts", "deals"],
                    sync_last_n_days=45,
                    max_records_per_sync=250,
                ),
            )
        with self._persisted(sf) as s2:  # "restart"
            assert s2.sync_configs["salesforce"].entity_types == ["contacts", "deals"]
            assert s2.sync_configs["salesforce"].sync_last_n_days == 45
            assert s2.sync_configs["salesforce"].max_records_per_sync == 250
            assert s2.usage_stats["salesforce"].auto_sync_enabled is True

    def test_usage_stats_survive_restart(self, worker_database):
        sf = worker_database
        with self._persisted(sf) as s1:
            s1.record_integration_usage("slack", "Slack", success=True)
            s1.record_integration_usage("slack", "Slack", success=False)
        with self._persisted(sf) as s2:
            stats = s2.usage_stats["slack"]
            assert stats.total_calls == 2
            assert stats.successful_calls == 1
            assert stats.last_used is not None
            assert stats.integration_name == "Slack"

    def test_disable_persists_disabled(self, worker_database):
        sf = worker_database
        with self._persisted(sf) as s1:
            s1.enable_auto_sync("jira")
            s1.disable_auto_sync("jira")
        with self._persisted(sf) as s2:
            assert s2.usage_stats["jira"].auto_sync_enabled is False

    def test_last_synced_persisted(self, worker_database):
        sf = worker_database
        synced_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        with self._persisted(sf) as s1:
            s1.enable_auto_sync("hubspot")
            s1.usage_stats["hubspot"].last_synced = synced_at
            s1._persist_integration("hubspot")
        with self._persisted(sf) as s2:
            assert s2.usage_stats["hubspot"].last_synced is not None
            assert abs((s2.usage_stats["hubspot"].last_synced - synced_at).total_seconds()) < 5

    def test_persistence_disabled_writes_nothing(self, worker_database):
        from core.models import IngestionSettings

        sf = worker_database
        with self._persisted(sf, persistence=False) as s:
            s.enable_auto_sync("salesforce")
        db = sf()
        try:
            rows = db.query(IngestionSettings).filter(
                IngestionSettings.workspace_id == "w110-p0"
            ).all()
            assert rows == []
        finally:
            db.close()

    def test_per_workspace_isolation(self, worker_database):
        sf = worker_database
        with self._persisted(sf, workspace="w110-p0-a") as s1:
            s1.enable_auto_sync("salesforce")
        with self._persisted(sf, workspace="w110-p0-b") as s2:
            assert "salesforce" not in s2.sync_configs


# =========================================================================== #
# Phase 1 — ingestion profile export/import
# =========================================================================== #


def _seed_settings(db, workspace, integration, **overrides):
    from core.models import IngestionSettings

    row = IngestionSettings(
        workspace_id=workspace,
        tenant_id="default",
        integration_id=integration,
        enabled=True,
        sync_frequency_minutes=30,
        auto_sync_new_files=True,
        file_types=["pdf", "docx"],
        sync_folders=["/org/drive/team"],
        exclude_folders=[],
        max_file_size_mb=25,
        entity_types=["contacts", "deals"],
        sync_last_n_days=45,
        max_records_per_sync=200,
        sync_mode="incremental",
    )
    for k, v in overrides.items():
        setattr(row, k, v)
    db.add(row)
    db.commit()
    return row


class TestIngestionProfileService:
    def test_build_profile_structure(self, worker_database):
        from core.ingestion_profile_service import PROFILE_KIND, PROFILE_VERSION, IngestionProfileService

        db = worker_database()
        _seed_settings(db, "w110-p1a", "salesforce")
        profile = IngestionProfileService().build_profile(db, "w110-p1a")
        assert profile["kind"] == PROFILE_KIND
        assert profile["profile_version"] == PROFILE_VERSION
        assert profile["workspace_id"] == "w110-p1a"
        assert len(profile["integrations"]) == 1
        entry = profile["integrations"][0]
        assert entry["integration_id"] == "salesforce"
        assert entry["entity_types"] == ["contacts", "deals"]
        assert entry["sync_last_n_days"] == 45
        assert entry["sync_folders"] == ["/org/drive/team"]
        assert entry["enabled"] is True

    def test_build_profile_strips_credentials_from_folders(self, worker_database):
        """Credential-shaped keys in settings are stripped out of the profile."""
        from core.ingestion_profile_service import IngestionProfileService

        db = worker_database()
        _seed_settings(
            db, "w110-p1a", "salesforce",
            sync_folders=[{"name": "team-drive", "access_token": "sekret-value"}],
        )
        profile = IngestionProfileService().build_profile(db, "w110-p1a")
        folders = profile["integrations"][0]["sync_folders"]
        assert folders == [{"name": "team-drive"}]

    def test_build_profile_fails_closed_when_credentials_survive(self, worker_database):
        """Even a credential key that survives strip_credentials must abort export."""
        from core.ingestion_profile_service import IngestionProfileError, IngestionProfileService

        db = worker_database()
        _seed_settings(
            db, "w110-p1a", "salesforce",
            sync_folders=[{"name": "team-drive", "access_token": "sekret-value"}],
        )
        svc = IngestionProfileService()
        with patch(
            "core.ingestion_profile_service.strip_credentials",
            side_effect=lambda obj: obj,  # simulate a sanitizer miss
        ):
            with pytest.raises(IngestionProfileError, match="credential"):
                svc.build_profile(db, "w110-p1a")

    def test_export_envelope_signed_and_hash_consistent(self, key_file_env, worker_database):
        from core import org_sharing_crypto
        from core.ingestion_profile_service import IngestionProfileService, canonical_payload, payload_hash

        db = worker_database()
        _seed_settings(db, "w110-p1a", "salesforce")
        envelope = IngestionProfileService().export_profile(db, "w110-p1a")
        assert envelope["kind"] == "atom_ingestion_profile"
        assert envelope["payload_hash"] == payload_hash(envelope["payload"])
        assert envelope["payload_hash"] == hashlib.sha256(
            canonical_payload(envelope["payload"])
        ).hexdigest()
        assert org_sharing_crypto.verify_payload(
            db, canonical_payload(envelope["payload"]), envelope["signature"], "w110-p1a"
        )

    def test_apply_profile_round_trip_a_to_b(self, key_file_env, worker_database):
        """Export on A, import on B → B schedules the same syncs with its own tenant."""
        from core.ingestion_profile_service import IngestionProfileService
        from core.models import IngestionSettings

        db = worker_database()
        _seed_settings(db, "w110-p1a", "salesforce")
        envelope = IngestionProfileService().export_profile(db, "w110-p1a")

        result = IngestionProfileService().apply_profile(
            db, envelope, workspace_id="w110-p1b", tenant_id="tenant-b",
            performed_by="alice",
        )
        assert result["applied_integrations"] == ["salesforce"]
        assert result["signature_valid"] is True

        row = db.query(IngestionSettings).filter(
            IngestionSettings.workspace_id == "w110-p1b",
            IngestionSettings.integration_id == "salesforce",
        ).first()
        assert row is not None
        assert row.tenant_id == "tenant-b"
        assert row.entity_types == ["contacts", "deals"]
        assert row.sync_last_n_days == 45
        assert row.sync_folders == ["/org/drive/team"]

    def test_apply_profile_only_touches_listed_integrations(self, key_file_env, worker_database):
        from core.ingestion_profile_service import IngestionProfileService
        from core.models import IngestionSettings

        db = worker_database()
        _seed_settings(db, "w110-p1a", "salesforce")
        # B has a personal notion config that must survive the import
        _seed_settings(db, "w110-p1b", "notion", sync_last_n_days=7, entity_types=["pages"])
        envelope = IngestionProfileService().export_profile(db, "w110-p1a")
        IngestionProfileService().apply_profile(db, envelope, workspace_id="w110-p1b")
        notion = db.query(IngestionSettings).filter(
            IngestionSettings.workspace_id == "w110-p1b",
            IngestionSettings.integration_id == "notion",
        ).first()
        assert notion.sync_last_n_days == 7  # untouched by the profile import

    def test_apply_profile_rejects_unsigned(self, key_file_env, worker_database):
        from core.ingestion_profile_service import IngestionProfileError, IngestionProfileService

        db = worker_database()
        _seed_settings(db, "w110-p1a", "salesforce")
        envelope = IngestionProfileService().export_profile(db, "w110-p1a")
        envelope.pop("signature")
        with pytest.raises(IngestionProfileError, match="not signed"):
            IngestionProfileService().apply_profile(db, envelope, workspace_id="w110-p1b")

    def test_apply_profile_rejects_tampered_payload(self, key_file_env, worker_database):
        from core.ingestion_profile_service import IngestionProfileError, IngestionProfileService

        db = worker_database()
        _seed_settings(db, "w110-p1a", "salesforce")
        envelope = IngestionProfileService().export_profile(db, "w110-p1a")
        envelope["payload"]["integrations"][0]["sync_last_n_days"] = 999  # tamper
        with pytest.raises(IngestionProfileError, match="tampered|hash"):
            IngestionProfileService().apply_profile(db, envelope, workspace_id="w110-p1b")

    def test_apply_profile_rejects_unregistered_signer(self, key_file_env, worker_database):
        """A signature from a member whose key is NOT in the registry is rejected."""
        from core.ingestion_profile_service import IngestionProfileError, IngestionProfileService, canonical_payload

        db = worker_database()
        _seed_settings(db, "w110-p1a", "salesforce")
        svc = IngestionProfileService()
        payload = svc.build_profile(db, "w110-p1a")
        private, _ = _foreign_keypair()  # NOT registered anywhere
        signature = base64.b64encode(private.sign(canonical_payload(payload))).decode("ascii")
        envelope = {
            "kind": "atom_ingestion_profile",
            "payload": payload,
            "payload_hash": hashlib.sha256(canonical_payload(payload)).hexdigest(),
            "signature": signature,
        }
        with pytest.raises(IngestionProfileError, match="signature"):
            svc.apply_profile(db, envelope, workspace_id="w110-p1b")

    def test_apply_profile_rejects_unsupported_version(self, key_file_env, worker_database):
        from core.ingestion_profile_service import IngestionProfileError, IngestionProfileService

        db = worker_database()
        _seed_settings(db, "w110-p1a", "salesforce")
        envelope = IngestionProfileService().export_profile(db, "w110-p1a")
        envelope["payload"]["profile_version"] = 999
        with pytest.raises(IngestionProfileError, match="profile_version"):
            IngestionProfileService().apply_profile(db, envelope, workspace_id="w110-p1b")

    def test_rejected_import_is_audited(self, key_file_env, worker_database):
        """Plan §6: unverified imports are rejected AND audited."""
        from core.ingestion_profile_service import IngestionProfileError, IngestionProfileService
        from core.models import IngestionProfileImport

        db = worker_database()
        _seed_settings(db, "w110-p1a", "salesforce")
        envelope = IngestionProfileService().export_profile(db, "w110-p1a")
        envelope.pop("signature")
        with pytest.raises(IngestionProfileError):
            IngestionProfileService().apply_profile(db, envelope, workspace_id="w110-p1b")
        audit = db.query(IngestionProfileImport).filter(
            IngestionProfileImport.workspace_id == "w110-p1b"
        ).all()
        assert len(audit) == 1
        assert audit[0].signature_valid is False


# =========================================================================== #
# Phase 2 — org data bundle export/import
# =========================================================================== #


def _seed_documents(db, workspace, integration="salesforce", count=3, sensitivity="internal"):
    from core.models import IngestedDocument

    docs = []
    for i in range(count):
        doc = IngestedDocument(
            workspace_id=workspace,
            tenant_id="default",
            integration_id=integration,
            external_id=f"sf-{workspace}-{i}",
            file_name=f"contact-{i}.txt",
            file_path=f"/org/{integration}/{i}",
            file_type="text",
            content_preview=f"Contact record {i}: Jane Doe, Acme Corp, VP Sales",
            sensitivity=sensitivity,
            external_modified_at=datetime.now(timezone.utc) - timedelta(days=i),
        )
        db.add(doc)
        docs.append(doc)
    db.commit()
    return docs


class TestOrgDataBundleService:
    def test_build_bundle_excludes_restricted_by_default(self, worker_database):
        from core.org_data_bundle_service import OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", sensitivity="internal", count=2)
        _seed_documents(db, "w110-p2a", integration="hr", sensitivity="restricted", count=1)
        envelope = OrgDataBundleService().build_bundle(
            db, "w110-p2a", sources=["salesforce", "hr"]
        )
        payload = envelope["payload"]
        assert len(payload["records"]) == 2
        assert all(r["sensitivity"] == "internal" for r in payload["records"])
        assert payload["sensitivity_breakdown"] == {"internal": 2}
        assert envelope["excluded_by_sensitivity"] == {"restricted": 1}

    def test_build_bundle_raised_ceiling_includes_confidential(self, worker_database):
        from core.org_data_bundle_service import OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", integration="finance", sensitivity="confidential", count=2)
        envelope = OrgDataBundleService().build_bundle(
            db, "w110-p2a", sources=["finance"], sensitivity_ceiling="confidential",
            destination="finance-team",
        )
        assert len(envelope["payload"]["records"]) == 2
        assert envelope["payload"]["sensitivity_ceiling"] == "confidential"

    def test_build_bundle_invalid_ceiling(self, worker_database):
        from core.org_data_bundle_service import BundleError, OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=1)
        with pytest.raises(BundleError, match="ceiling"):
            OrgDataBundleService().build_bundle(db, "w110-p2a", sources=[], sensitivity_ceiling="top-secret")

    def test_build_bundle_source_filter(self, worker_database):
        from core.org_data_bundle_service import OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", integration="salesforce", count=3)
        _seed_documents(db, "w110-p2a", integration="hubspot", count=2)
        envelope = OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["hubspot"])
        assert len(envelope["payload"]["records"]) == 2
        assert all(r["integration_id"] == "hubspot" for r in envelope["payload"]["records"])

    def test_build_bundle_record_cap(self, worker_database):
        from core.org_data_bundle_service import MAX_RECORDS_PER_BUNDLE, OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=MAX_RECORDS_PER_BUNDLE + 50)
        envelope = OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"])
        assert len(envelope["payload"]["records"]) <= MAX_RECORDS_PER_BUNDLE

    def test_build_bundle_fails_closed_when_credentials_survive(self, worker_database):
        """A credential-shaped key that survives sanitization must abort export."""
        from core.org_data_bundle_service import BundleError, OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=1)
        with patch(
            "core.org_data_bundle_service.has_credentials",
            return_value=True,  # simulate a sanitizer miss
        ):
            with pytest.raises(BundleError, match="credential"):
                OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"])

    def test_export_audit_row(self, worker_database):
        from core.models import BundleExport
        from core.org_data_bundle_service import OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=2)
        OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"], destination="sales-team")
        audit = db.query(BundleExport).filter(BundleExport.workspace_id == "w110-p2a").all()
        assert len(audit) == 1
        assert audit[0].record_count == 2
        assert audit[0].destination == "sales-team"
        assert len(audit[0].payload_hash) == 64

    def test_apply_bundle_round_trip_and_idempotency(self, key_file_env, worker_database):
        """A exports → B imports → re-import is a no-op (dedup)."""
        from core.models import DocumentIngestion, IngestedDocument
        from core.org_data_bundle_service import OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=3)
        envelope = OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"])

        with patch("core.lancedb_handler.get_lancedb_handler"):
            svc = OrgDataBundleService()
            result1 = asyncio.run(svc.apply_bundle(db, envelope, workspace_id="w110-p2b", tenant_id="tenant-b", performed_by="bob"))
            assert result1["records_total"] == 3
            assert result1["records_ingested"] == 3

            result2 = asyncio.run(svc.apply_bundle(db, envelope, workspace_id="w110-p2b"))
            assert result2["records_ingested"] == 0
            assert result2["records_skipped"] == 3

        docs = db.query(IngestedDocument).filter(IngestedDocument.workspace_id == "w110-p2b").all()
        assert len(docs) == 3
        dedup = db.query(DocumentIngestion).filter(DocumentIngestion.workspace_id == "w110-p2b").all()
        assert len(dedup) == 3
        assert all(d.source == "salesforce" for d in dedup)
        assert result1["errors"] == []

    def test_apply_bundle_reruns_embedding_for_changed_records(self, key_file_env, worker_database):
        from core.models import IngestedDocument
        from core.org_data_bundle_service import OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=1)
        envelope = OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"])
        with patch("core.lancedb_handler.get_lancedb_handler"):
            svc = OrgDataBundleService()
            asyncio.run(svc.apply_bundle(db, envelope, workspace_id="w110-p2b"))

        # exporter updates the record; re-export picks up the change
        src = db.query(IngestedDocument).filter(IngestedDocument.workspace_id == "w110-p2a").first()
        src.content_preview = "Contact record 0: Jane Doe, Acme Corp, CHIEF REVENUE OFFICER"
        db.commit()
        envelope2 = OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"])
        with patch("core.lancedb_handler.get_lancedb_handler"):
            result = asyncio.run(svc.apply_bundle(db, envelope2, workspace_id="w110-p2b"))
        assert result["records_ingested"] == 1
        assert result["records_skipped"] == 0

    def test_apply_bundle_tombstone_marks_removed(self, key_file_env, worker_database):
        from core import org_sharing_crypto
        from core.ingestion_profile_service import canonical_payload, payload_hash
        from core.models import IngestedDocument
        from core.org_data_bundle_service import OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=1)
        envelope = OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"])
        with patch("core.lancedb_handler.get_lancedb_handler"):
            asyncio.run(OrgDataBundleService().apply_bundle(db, envelope, workspace_id="w110-p2b"))

        # exporter deletes at origin and ships a tombstone
        db.query(IngestedDocument).filter(IngestedDocument.workspace_id == "w110-p2a").delete()
        db.commit()
        payload = envelope["payload"]
        payload["tombstones"] = [payload["records"][0]["external_id"]]
        signature, _ = org_sharing_crypto.sign_payload(canonical_payload(payload))
        tombstone_envelope = {
            "kind": "atom_org_data_bundle",
            "payload": payload,
            "payload_hash": payload_hash(payload),
            "signature": signature,
        }
        with patch("core.lancedb_handler.get_lancedb_handler"):
            result = asyncio.run(
                OrgDataBundleService().apply_bundle(db, tombstone_envelope, workspace_id="w110-p2b")
            )
        assert result["tombstones_applied"] == 1
        imported = db.query(IngestedDocument).filter(IngestedDocument.workspace_id == "w110-p2b").first()
        assert imported.freshness_status == "removed"

    def test_apply_bundle_rejects_bad_signature_and_audits(self, key_file_env, worker_database):
        """Plan §6: unverified bundles are rejected AND audited."""
        from core.models import BundleImport
        from core.org_data_bundle_service import BundleError, OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=1)
        envelope = OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"])
        envelope["signature"] = base64.b64encode(b"f" * 64).decode()
        with pytest.raises(BundleError, match="signature"):
            asyncio.run(
                OrgDataBundleService().apply_bundle(db, envelope, workspace_id="w110-p2b")
            )
        audit = db.query(BundleImport).filter(BundleImport.workspace_id == "w110-p2b").all()
        assert len(audit) == 1
        assert audit[0].records_total == 0

    def test_apply_bundle_rejects_tampered_payload(self, key_file_env, worker_database):
        from core.org_data_bundle_service import BundleError, OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=1)
        envelope = OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"])
        envelope["payload"]["records"][0]["content_preview"] = "tampered"
        with pytest.raises(BundleError, match="tampered|hash"):
            asyncio.run(
                OrgDataBundleService().apply_bundle(db, envelope, workspace_id="w110-p2b")
            )

    def test_apply_bundle_rejects_over_cap(self, key_file_env, worker_database):
        from core import org_sharing_crypto
        from core.ingestion_profile_service import canonical_payload, payload_hash
        from core.org_data_bundle_service import MAX_RECORDS_PER_BUNDLE, BundleError, OrgDataBundleService

        db = worker_database()
        payload = {
            "kind": "atom_org_data_bundle",
            "bundle_version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "workspace_id": "w110-p2a",
            "sources": ["salesforce"],
            "sensitivity_ceiling": "internal",
            "records": [
                {"integration_id": "salesforce", "external_id": f"x{i}", "content_preview": "c"}
                for i in range(MAX_RECORDS_PER_BUNDLE + 1)
            ],
            "tombstones": [],
            "sensitivity_breakdown": {},
        }
        signature, _ = org_sharing_crypto.sign_payload(canonical_payload(payload))
        envelope = {
            "kind": "atom_org_data_bundle",
            "payload": payload,
            "payload_hash": payload_hash(payload),
            "signature": signature,
        }
        with pytest.raises(BundleError, match="cap"):
            asyncio.run(OrgDataBundleService().apply_bundle(db, envelope, workspace_id="w110-p2b"))

    def test_apply_bundle_import_audit_row(self, key_file_env, worker_database):
        from core.models import BundleImport
        from core.org_data_bundle_service import OrgDataBundleService

        db = worker_database()
        _seed_documents(db, "w110-p2a", count=2)
        envelope = OrgDataBundleService().build_bundle(db, "w110-p2a", sources=["salesforce"])
        with patch("core.lancedb_handler.get_lancedb_handler"):
            asyncio.run(
                OrgDataBundleService().apply_bundle(db, envelope, workspace_id="w110-p2b", performed_by="bob")
            )
        audit = db.query(BundleImport).filter(BundleImport.workspace_id == "w110-p2b").all()
        assert len(audit) == 1
        assert audit[0].records_total == 2
        assert audit[0].records_ingested == 2
        assert audit[0].performed_by == "bob"


# =========================================================================== #
# Routes — kill switch + endpoints
# =========================================================================== #


class TestOrgSharingRoutes:
    @pytest.fixture
    def client(self, worker_database, key_file_env):
        from api.data_ingestion_routes import router
        from core.auth import get_current_user
        from core.database import get_db

        sf = worker_database

        def _override_user():
            return _make_user(user_id="w110-user")

        def _override_db():
            db = sf()
            try:
                yield db
            finally:
                db.close()

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_db] = _override_db
        return TestClient(app)

    def test_kill_switch_blocks_all_org_routes(self, client, key_file_env):
        # ATOM_ORG_SHARING_ENABLED defaults to false
        cases = [
            ("GET", "/api/data-ingestion/org-key", None),
            ("POST", "/api/data-ingestion/org-key/register", {"public_key": base64.b64encode(b"a" * 32).decode(), "label": "peer"}),
            ("GET", "/api/data-ingestion/profile/export", None),
            ("POST", "/api/data-ingestion/profile/import", {"profile": {}}),
            ("POST", "/api/data-ingestion/bundle/export", {"sources": [], "sensitivity_ceiling": "internal"}),
            ("POST", "/api/data-ingestion/bundle/import", {"bundle": {}}),
        ]
        for method, path, body in cases:
            resp = getattr(client, method.lower())(path, json=body) if body is not None else getattr(client, method.lower())(path)
            assert resp.status_code == 403, f"{method} {path} should be 403, got {resp.status_code}"
            assert "ATOM_ORG_SHARING_ENABLED" in str(resp.json())

    def test_org_key_endpoint_bootstraps_own_key(self, client, key_file_env, sharing_enabled):
        resp = client.get("/api/data-ingestion/org-key")
        assert resp.status_code == 200
        data = resp.json()["data"]
        raw = base64.b64decode(data["public_key"])
        assert len(raw) == 32
        assert data["fingerprint"] == hashlib.sha256(raw).hexdigest()

    def test_register_peer_key_endpoint(self, client, key_file_env, sharing_enabled):
        resp = client.post(
            "/api/data-ingestion/org-key/register",
            json={"public_key": base64.b64encode(b"b" * 32).decode(), "label": "alice-laptop"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["label"] == "alice-laptop"

    def test_register_peer_key_rejects_bad_length(self, client, key_file_env, sharing_enabled):
        resp = client.post(
            "/api/data-ingestion/org-key/register",
            json={"public_key": base64.b64encode(b"short").decode(), "label": "bad"},
        )
        assert resp.status_code == 400

    def test_profile_export_and_import_flow(self, client, worker_database, key_file_env, sharing_enabled):
        from core.models import IngestionSettings

        db = worker_database()
        db.add(IngestionSettings(
            workspace_id="default", tenant_id="default", integration_id="salesforce",
            enabled=True, sync_frequency_minutes=30, entity_types=["contacts"],
            sync_last_n_days=45, max_records_per_sync=150, sync_mode="incremental",
        ))
        db.commit()

        export = client.get("/api/data-ingestion/profile/export")
        assert export.status_code == 200
        envelope = export.json()["data"]
        assert envelope["kind"] == "atom_ingestion_profile"

        imported = client.post("/api/data-ingestion/profile/import", json={"profile": envelope})
        assert imported.status_code == 200
        assert imported.json()["data"]["count"] == 1

    def test_profile_import_rejects_unverified(self, client, key_file_env, sharing_enabled):
        resp = client.post(
            "/api/data-ingestion/profile/import",
            json={"profile": {"kind": "atom_ingestion_profile", "payload": {"profile_version": 1, "integrations": []}, "signature": base64.b64encode(b"z" * 64).decode()}},
        )
        assert resp.status_code == 400

    def test_bundle_export_and_import_flow(self, client, worker_database, key_file_env, sharing_enabled):
        from core.models import IngestedDocument

        db = worker_database()
        db.add(IngestedDocument(
            workspace_id="default", tenant_id="default", integration_id="salesforce",
            external_id="sf-1", file_name="c1.txt", file_path="/org/sf/1", file_type="text",
            content_preview="Contact: Jane Doe", sensitivity="internal",
        ))
        db.commit()

        exported = client.post(
            "/api/data-ingestion/bundle/export",
            json={"sources": ["salesforce"], "sensitivity_ceiling": "internal"},
        )
        assert exported.status_code == 200
        envelope = exported.json()["data"]
        assert envelope["kind"] == "atom_org_data_bundle"

        imported = client.post("/api/data-ingestion/bundle/import", json={"bundle": envelope})
        assert imported.status_code == 200
        assert imported.json()["data"]["records_ingested"] == 1
