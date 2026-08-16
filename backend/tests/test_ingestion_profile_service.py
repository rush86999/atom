"""Ingestion Profile Service — Phase 1 org config sharing.

Round-trip export/import on a temp SQLite DB, credential fail-closed,
signature verification, tamper detection, hot-reload into the live hybrid
service.
"""
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import org_sharing_crypto
from core.ingestion_profile_service import (
    IngestionProfileError,
    IngestionProfileService,
    canonical_payload,
    payload_hash,
)
from core.models import (
    Base,
    IngestionProfileImport,
    IngestionSettings,
    OrgPublicKey,
)

TABLES = [IngestionSettings.__table__, OrgPublicKey.__table__, IngestionProfileImport.__table__]


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    path = tmp_path / "org_sharing_key"
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(path))
    return path


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def seed_settings(db, workspace_id="default"):
    db.add(IngestionSettings(
        workspace_id=workspace_id, tenant_id="default", integration_id="salesforce",
        enabled=True, sync_frequency_minutes=30, file_types=["pdf"],
        entity_types=["contacts", "opportunities"], sync_last_n_days=14,
        max_records_per_sync=500, sync_mode="incremental",
        usage_stats_json={"total_calls": 12},
    ))
    db.add(IngestionSettings(
        workspace_id=workspace_id, tenant_id="default", integration_id="slack",
        enabled=False, sync_frequency_minutes=60,
    ))
    db.commit()


class TestBuild:
    def test_build_contains_integrations_sanitized(self, key_file, db):
        seed_settings(db)
        profile = IngestionProfileService().build_profile(db, "default")
        assert profile["kind"] == "atom_ingestion_profile"
        assert profile["profile_version"] == 1
        ids = {i["integration_id"] for i in profile["integrations"]}
        assert ids == {"salesforce", "slack"}
        sf = next(i for i in profile["integrations"] if i["integration_id"] == "salesforce")
        assert sf["entity_types"] == ["contacts", "opportunities"]
        assert sf["sync_last_n_days"] == 14

    def test_export_envelope_signed(self, key_file, db):
        seed_settings(db)
        env = IngestionProfileService().export_profile(db, "default")
        assert env["payload"]["kind"] == "atom_ingestion_profile"
        assert env["payload_hash"] == payload_hash(env["payload"])
        assert env["signature"]
        assert org_sharing_crypto.verify_payload(
            db, canonical_payload(env["payload"]), env["signature"], "default"
        )

    def test_credentials_stripped_from_export(self, key_file, db):
        seed_settings(db)
        db.query(IngestionSettings).filter_by(integration_id="slack").update(
            {"sync_folders": ["ok", {"api_key": "sk-secret"}]}
        )
        db.commit()
        profile = IngestionProfileService().build_profile(db, "default")
        slack = next(i for i in profile["integrations"] if i["integration_id"] == "slack")
        assert slack["sync_folders"] == ["ok", {}]

    def test_fail_closed_if_sanitizer_bypassed(self, key_file, db):
        seed_settings(db)
        db.query(IngestionSettings).filter_by(integration_id="slack").update(
            {"sync_folders": ["ok", {"api_key": "sk-secret"}]}
        )
        db.commit()
        # Defense-in-depth guard: if a credential-shaped key somehow survived
        # sanitization, export must refuse rather than share it.
        with patch("core.ingestion_profile_service.strip_credentials", side_effect=lambda o: o):
            with pytest.raises(IngestionProfileError, match="credential"):
                IngestionProfileService().build_profile(db, "default")


class TestApply:
    def test_round_trip_export_import(self, key_file, db):
        seed_settings(db)
        svc = IngestionProfileService()
        env = svc.export_profile(db, "default")

        # "Member B" workspace on a fresh DB.
        engine2 = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine2, tables=TABLES)
        db2 = sessionmaker(bind=engine2)()
        result = svc.apply_profile(db2, env, workspace_id="member-b", tenant_id="t",
                                   performed_by="user1")
        assert result["count"] == 2
        assert set(result["applied_integrations"]) == {"salesforce", "slack"}
        assert result["signature_valid"] is True

        sf = db2.query(IngestionSettings).filter_by(integration_id="salesforce").one()
        assert sf.enabled is True
        assert sf.entity_types == ["contacts", "opportunities"]
        assert sf.sync_last_n_days == 14
        audit = db2.query(IngestionProfileImport).one()
        assert audit.signature_valid is True
        assert audit.performed_by == "user1"
        db2.close()

    def test_reimport_is_idempotent_upsert(self, key_file, db):
        seed_settings(db)
        svc = IngestionProfileService()
        env = svc.export_profile(db, "default")
        svc.apply_profile(db, env, workspace_id="default")
        svc.apply_profile(db, env, workspace_id="default")
        assert db.query(IngestionSettings).count() == 2

    def test_import_does_not_touch_unlisted_integrations(self, key_file, db):
        db.add(IngestionSettings(workspace_id="default", integration_id="personal-gmail",
                                 enabled=False))
        db.commit()
        svc = IngestionProfileService()
        env = svc.export_profile(db, "default")  # empty profile
        svc.apply_profile(db, env, workspace_id="default")
        row = db.query(IngestionSettings).filter_by(integration_id="personal-gmail").one()
        assert row.enabled is False  # untouched

    def test_rejects_wrong_kind(self, key_file, db):
        with pytest.raises(IngestionProfileError):
            IngestionProfileService().apply_profile(db, {"kind": "nope"}, "default")

    def test_rejects_unsigned(self, key_file, db):
        seed_settings(db)
        env = IngestionProfileService().export_profile(db, "default")
        del env["signature"]
        with pytest.raises(IngestionProfileError, match="not signed"):
            IngestionProfileService().apply_profile(db, env, "default")

    def test_rejects_tampered_payload(self, key_file, db):
        seed_settings(db)
        env = IngestionProfileService().export_profile(db, "default")
        env["payload"]["integrations"][0]["entity_types"] = ["everything"]
        with pytest.raises(IngestionProfileError, match="tampered"):
            IngestionProfileService().apply_profile(db, env, "default")

    def test_rejects_unknown_signer(self, key_file, db, tmp_path, monkeypatch):
        seed_settings(db)
        env = IngestionProfileService().export_profile(db, "default")
        # Fresh instance key: signer no longer matches own key or registry.
        monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(tmp_path / "other"))
        with pytest.raises(IngestionProfileError, match="signature"):
            IngestionProfileService().apply_profile(db, env, "default")

    def test_rejects_future_version(self, key_file, db):
        env = {
            "kind": "atom_ingestion_profile",
            "payload": {"kind": "atom_ingestion_profile", "profile_version": 99, "integrations": []},
            "signature": "x",
            "payload_hash": "y",
        }
        with pytest.raises(IngestionProfileError, match="Unsupported"):
            IngestionProfileService().apply_profile(db, env, "default")

    def test_live_reload_into_hybrid_service(self, key_file, db):
        seed_settings(db)
        svc = IngestionProfileService()
        env = svc.export_profile(db, "default")
        fake = type("S", (), {})()
        fake.sync_configs = {}
        fake.usage_stats = {}
        fake.enable_auto_sync = lambda iid, config=None: fake.sync_configs.update({iid: config})
        with patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service", return_value=fake):
            result = svc.apply_profile(db, env, workspace_id="default")
        assert result["live_reload_count"] == 1  # only salesforce (enabled + hybrid cols)
        assert "salesforce" in fake.sync_configs
