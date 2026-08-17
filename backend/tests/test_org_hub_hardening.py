"""Org Hub hardening (real-world prep): egress policy + key lifecycle + status.

A member request can never raise the hub's egress policy: the sensitivity
ceiling is clamped to ATOM_ORG_HUB_MAX_SENSITIVITY and sources are
intersected with ATOM_ORG_HUB_SOURCE_ALLOWLIST. The global delta cap spans
all sources (a per-source break no longer lets later sources exceed it).
Key lifecycle: peer keys revocable, own key protected. Status endpoint
reports cursor + recent imports.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import org_sharing_crypto
from core.models import (
    Base,
    BundleExport,
    BundleImport,
    IngestedDocument,
    IngestionSettings,
    OrgPublicKey,
)
from core.org_hub_service import (
    HubError,
    OrgHubService,
    apply_hub_source_policy,
    clamp_sensitivity_ceiling,
)

TABLES = [
    IngestedDocument.__table__,
    IngestionSettings.__table__,
    BundleExport.__table__,
    BundleImport.__table__,
    OrgPublicKey.__table__,
]


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(tmp_path / "org_sharing_key"))


@pytest.fixture()
def db():
    # TestClient serves requests from a different thread — StaticPool +
    # check_same_thread=False lets the in-memory DB cross threads.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def add_doc(db, external_id, integration_id="salesforce", sensitivity="internal",
            updated=None, removed=False):
    db.add(IngestedDocument(
        workspace_id="default", tenant_id="default", integration_id=integration_id,
        external_id=external_id, file_name=f"{external_id}", file_path="/x",
        file_type="json", content_preview=f"data {external_id}", sensitivity=sensitivity,
        external_modified_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        updated_at=updated or datetime(2026, 8, 10, tzinfo=timezone.utc),
        freshness_status="removed" if removed else "fresh",
    ))
    db.commit()


class TestEgressPolicy:
    def test_clamp_to_hub_max(self, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_HUB_MAX_SENSITIVITY", "internal")
        assert clamp_sensitivity_ceiling("restricted") == "internal"
        assert clamp_sensitivity_ceiling("confidential") == "internal"
        assert clamp_sensitivity_ceiling("internal") == "internal"
        assert clamp_sensitivity_ceiling("public") == "public"

    def test_clamp_allows_lower_than_max(self, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_HUB_MAX_SENSITIVITY", "confidential")
        assert clamp_sensitivity_ceiling("restricted") == "confidential"
        assert clamp_sensitivity_ceiling("confidential") == "confidential"

    def test_invalid_env_falls_back_internal(self, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_HUB_MAX_SENSITIVITY", "wild")
        assert clamp_sensitivity_ceiling("restricted") == "internal"

    def test_default_max_is_internal(self, monkeypatch):
        monkeypatch.delenv("ATOM_ORG_HUB_MAX_SENSITIVITY", raising=False)
        assert clamp_sensitivity_ceiling("confidential") == "internal"

    def test_allowlist_passthrough_when_unset(self, monkeypatch):
        monkeypatch.delenv("ATOM_ORG_HUB_SOURCE_ALLOWLIST", raising=False)
        assert apply_hub_source_policy(["slack", "gmail"]) == ["slack", "gmail"]

    def test_allowlist_defaults_when_nothing_requested(self, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_HUB_SOURCE_ALLOWLIST", "salesforce,slack")
        assert apply_hub_source_policy([]) == ["salesforce", "slack"]

    def test_allowlist_passes_allowed_and_denies_mixed(self, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_HUB_SOURCE_ALLOWLIST", "salesforce,slack")
        # A fully-allowlisted request passes untouched.
        assert apply_hub_source_policy(["slack"]) == ["slack"]
        # Mixed requests fail closed as a whole — no accidental partial sync.
        with pytest.raises(HubError, match="not on the hub allowlist"):
            apply_hub_source_policy(["slack", "gmail"])
        with pytest.raises(HubError, match="not on the hub allowlist"):
            apply_hub_source_policy(["personal_gmail"])


class TestDeltaBundlePolicy:
    async def test_requested_ceiling_clamped_in_payload(self, key_file, db, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_HUB_MAX_SENSITIVITY", "internal")
        monkeypatch.delenv("ATOM_ORG_HUB_SOURCE_ALLOWLIST", raising=False)
        add_doc(db, "int-1", sensitivity="internal")
        add_doc(db, "conf-1", sensitivity="confidential")
        env = OrgHubService().build_delta_bundle(
            db, "default", sources=["salesforce"], since_cursor={},
            sensitivity_ceiling="restricted",  # member asks for everything
        )
        payload = env["payload"]
        assert payload["ceiling_clamped_to"] == "internal"
        assert payload["sensitivity_ceiling"] == "internal"
        ids = {r["external_id"] for r in payload["records"]}
        assert "conf-1" not in ids  # hub policy won, not the request

    async def test_cap_spans_all_sources(self, key_file, db, monkeypatch):
        monkeypatch.delenv("ATOM_ORG_HUB_MAX_SENSITIVITY", raising=False)
        monkeypatch.delenv("ATOM_ORG_HUB_SOURCE_ALLOWLIST", raising=False)
        monkeypatch.setattr("core.org_hub_service.MAX_DELTA_RECORDS", 1)
        add_doc(db, "a-1", integration_id="salesforce")
        add_doc(db, "a-2", integration_id="salesforce")
        add_doc(db, "b-1", integration_id="slack")
        env = OrgHubService().build_delta_bundle(
            db, "default", sources=["salesforce", "slack"], since_cursor={},
        )
        payload = env["payload"]
        assert len(payload["records"]) == 1  # global cap, not per-source
        assert payload["truncated"] is True
        # Deferred source keeps no cursor → next pull resumes it from scratch.
        assert "slack" not in payload["cursor"]

    async def test_tombstones_travel_in_delta(self, key_file, db, monkeypatch):
        monkeypatch.delenv("ATOM_ORG_HUB_MAX_SENSITIVITY", raising=False)
        add_doc(db, "dead-1", removed=True)
        env = OrgHubService().build_delta_bundle(
            db, "default", sources=["salesforce"], since_cursor={},
        )
        assert env["payload"]["tombstones"] == ["dead-1"]
        assert env["payload"]["records"] == []


# ---------------------------------------------------------------------------
# Route-level: key lifecycle + hub status
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db, key_file, monkeypatch):
    from api.data_ingestion_routes import router
    from core.auth import get_current_user
    from core.database import get_db

    monkeypatch.setenv("ATOM_ORG_SHARING_ENABLED", "true")
    app = FastAPI()
    app.include_router(router)
    # workspace_id/tenant_id=None so resolve_*_id() falls back to "default"
    # (a bare MagicMock attribute would resolve to a truthy mock instead).
    app.dependency_overrides[get_current_user] = lambda: MagicMock(
        id="test-user", workspace_id=None, tenant_id=None)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


class TestKeyLifecycleRoutes:
    def test_list_and_revoke_peer_key(self, client, db):
        pub = org_sharing_crypto.public_key_b64(
            org_sharing_crypto.get_or_create_private_key())
        row = org_sharing_crypto.register_public_key(db, pub, label="peer-a", workspace_id="default")

        resp = client.get("/api/data-ingestion/org-key/list")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["count"] == 1 and body["keys"][0]["label"] == "peer-a"

        resp = client.delete(f"/api/data-ingestion/org-key/{row.id}")
        assert resp.status_code == 200
        assert db.query(OrgPublicKey).count() == 0

    def test_revoke_own_key_refused(self, client, db):
        pub = org_sharing_crypto.ensure_own_key_registered(db, "default", "default")
        row = db.query(OrgPublicKey).filter_by(public_key=pub).one()
        resp = client.delete(f"/api/data-ingestion/org-key/{row.id}")
        assert resp.status_code == 400
        assert "rotate" in resp.json()["detail"]
        assert db.query(OrgPublicKey).filter_by(is_own=True).count() == 1

    def test_revoke_unknown_key_404(self, client):
        resp = client.delete("/api/data-ingestion/org-key/nope")
        assert resp.status_code == 404

    def test_revoked_key_no_longer_verifies(self, client, db):
        import base64
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        # A genuinely foreign signer (not this instance's own key, which
        # verifies regardless of the registry).
        peer_key = Ed25519PrivateKey.generate()
        sig = base64.b64encode(peer_key.sign(b"proof")).decode()
        pub = base64.b64encode(peer_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()

        org_sharing_crypto.register_public_key(db, pub, label="peer", workspace_id="default")
        assert org_sharing_crypto.verify_payload(db, b"proof", sig, "default") is True

        row = db.query(OrgPublicKey).filter_by(label="peer").one()
        client.delete(f"/api/data-ingestion/org-key/{row.id}")
        assert org_sharing_crypto.verify_payload(db, b"proof", sig, "default") is False


class TestHubStatusRoute:
    def test_status_reports_cursor_and_imports(self, client, db):
        db.add(IngestionSettings(
            workspace_id="default", integration_id="org_hub", enabled=False,
            usage_stats_json={"org_hub_cursor": '{"salesforce": {"updated_at": "2026-08-10T00:00:00+00:00", "external_id": "a-1"}}'},
        ))
        db.add(BundleImport(workspace_id="default", payload_hash="h", records_total=3,
                            records_ingested=2, records_skipped=1))
        db.commit()

        resp = client.get("/api/data-ingestion/hub/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["cursor_sources"] == ["salesforce"]
        assert data["recent_imports"][0]["records_ingested"] == 2

    def test_status_empty_state(self, client):
        resp = client.get("/api/data-ingestion/hub/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["cursor"] == {} and data["recent_imports"] == []

    def test_flag_gates_routes(self, db, monkeypatch):
        from api.data_ingestion_routes import router
        from core.auth import get_current_user
        from core.database import get_db

        monkeypatch.setenv("ATOM_ORG_SHARING_ENABLED", "false")
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: MagicMock(id="u")
        app.dependency_overrides[get_db] = lambda: db
        c = TestClient(app)
        assert c.get("/api/data-ingestion/org-key/list").status_code == 403
        assert c.get("/api/data-ingestion/hub/status").status_code == 403
