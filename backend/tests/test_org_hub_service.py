# -*- coding: utf-8 -*-
"""Org Ingestion Hub (Phase 3) — docs/architecture/ORG_INGESTION_SHARING_PLAN.md.

Hub-side delta bundles + member-side pull/apply:
- ``core/org_hub_service.py``: ``build_delta_bundle`` (per-source monotonic
  cursor, tombstones, sensitivity gate, signed via the shared Phase 2
  sign_and_audit_bundle path) and ``pull_and_apply`` (HTTP pull + Phase 2
  import + cursor persistence in ingestion_settings.usage_stats_json).
- Routes: hub-side ``GET /api/data-ingestion/hub/bundles`` (auth via
  atom_sk_* GatewayApiKey; flag ATOM_ORG_HUB_ENABLED) and member-side
  ``POST /api/data-ingestion/hub/pull`` (flag ATOM_ORG_SHARING_ENABLED).

Session-scoped worker DB → autouse cleanup per test (same as w110).
"""
import asyncio
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ORG_TABLES = (
    "IngestionSettings",
    "OrgPublicKey",
    "IngestionProfileImport",
    "BundleExport",
    "BundleImport",
    "IngestedDocument",
    "DocumentIngestion",
)


@pytest.fixture
def key_file_env(tmp_path, monkeypatch):
    key_file = tmp_path / "org_sharing_key"
    monkeypatch.setenv("ATOM_ORG_SHARING_KEY_FILE", str(key_file))
    return key_file


@pytest.fixture
def sharing_enabled(monkeypatch):
    monkeypatch.setenv("ATOM_ORG_SHARING_ENABLED", "true")


@pytest.fixture
def hub_enabled(monkeypatch):
    monkeypatch.setenv("ATOM_ORG_HUB_ENABLED", "true")


@pytest.fixture(autouse=True)
def clean_org_tables(worker_database):
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


def _seed_documents(db, workspace, integration="salesforce", count=3, sensitivity="internal",
                    external_ids=None, stamps=None):
    """Seed IngestedDocument rows with increasing updated_at timestamps."""
    from core.models import IngestedDocument

    base = datetime.now(timezone.utc) - timedelta(hours=len(range(count)))
    stamps = stamps or [base + timedelta(hours=i) for i in range(count)]
    docs = []
    for i in range(count):
        doc = IngestedDocument(
            workspace_id=workspace,
            tenant_id="default",
            integration_id=integration,
            external_id=(external_ids or [f"sf-{i}" for i in range(count)])[i],
            file_name=f"contact-{i}.txt",
            file_path=f"/org/{integration}/{i}",
            file_type="text",
            content_preview=f"Contact record {i}: Jane Doe, Acme Corp",
            sensitivity=sensitivity,
            external_modified_at=base + timedelta(hours=i),
            updated_at=stamps[i],
        )
        db.add(doc)
        docs.append(doc)
    db.commit()
    return docs


def _hub_key(db, user_id="hub-user"):
    """Create a GatewayApiKey for hub auth and return its plaintext."""
    from core.models import GatewayApiKey, User
    from core.llm.gateway.auth import hash_api_key

    plaintext = "atom_sk_" + "a" * 32 + "hubtest"
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        user = User(id=user_id, email="hub@example.com", hashed_password="x",
                    first_name="Hub", last_name="User", role="admin", status="active")
        db.add(user)
        db.commit()
    db.add(GatewayApiKey(
        name="hub-test",
        key_hash=hash_api_key(plaintext),
        key_prefix=plaintext[:12],
        user_id=user_id,
        tenant_id="default",
        workspace_id="default",
        is_active=True,
    ))
    db.commit()
    return plaintext


class TestOrgHubService:
    def test_delta_first_pull_returns_all(self, key_file_env, worker_database):
        from core.org_hub_service import OrgHubService

        db = worker_database()
        _seed_documents(db, "w110-h1", count=3)
        envelope = OrgHubService().build_delta_bundle(
            db, "w110-h1", sources=["salesforce"], since_cursor=None,
        )
        payload = envelope["payload"]
        assert len(payload["records"]) == 3
        assert payload["hub_delta"] is True
        assert payload["cursor"]["salesforce"]["external_id"] == "sf-2"
        assert envelope["kind"] == "atom_org_data_bundle"
        assert envelope["payload_hash"] == hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def test_delta_incremental_second_pull(self, key_file_env, worker_database):
        from core.org_hub_service import OrgHubService
        from core.models import IngestedDocument

        db = worker_database()
        _seed_documents(db, "w110-h1", count=2)
        svc = OrgHubService()

        first = svc.build_delta_bundle(db, "w110-h1", sources=["salesforce"], since_cursor=None)
        cursor = first["payload"]["cursor"]

        # New document lands on the hub
        db.add(IngestedDocument(
            workspace_id="w110-h1", tenant_id="default", integration_id="salesforce",
            external_id="sf-2", file_name="c2.txt", file_path="/org/sf/2", file_type="text",
            content_preview="Contact record 2: Bob, Globex",
            sensitivity="internal",
            updated_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        ))
        db.commit()

        second = svc.build_delta_bundle(db, "w110-h1", sources=["salesforce"], since_cursor=cursor)
        records = second["payload"]["records"]
        assert len(records) == 1
        assert records[0]["external_id"] == "sf-2"
        assert second["payload"]["cursor"]["salesforce"]["external_id"] == "sf-2"

    def test_delta_changed_record_reappears(self, key_file_env, worker_database):
        from core.org_hub_service import OrgHubService
        from core.models import IngestedDocument

        db = worker_database()
        _seed_documents(db, "w110-h1", count=1)
        svc = OrgHubService()
        cursor = svc.build_delta_bundle(db, "w110-h1", sources=["salesforce"], since_cursor=None)["payload"]["cursor"]

        doc = db.query(IngestedDocument).filter(
            IngestedDocument.workspace_id == "w110-h1"
        ).first()
        doc.content_preview = "Contact record 0: Jane Doe, Acme Corp, CHIEF REVENUE OFFICER"
        doc.updated_at = datetime.now(timezone.utc) + timedelta(minutes=2)
        db.commit()

        delta = svc.build_delta_bundle(db, "w110-h1", sources=["salesforce"], since_cursor=cursor)
        assert len(delta["payload"]["records"]) == 1
        assert "CHIEF REVENUE OFFICER" in delta["payload"]["records"][0]["content_preview"]

    def test_delta_tombstones_removed_docs(self, key_file_env, worker_database):
        from core.org_hub_service import OrgHubService
        from core.models import IngestedDocument

        db = worker_database()
        _seed_documents(db, "w110-h1", count=2)
        svc = OrgHubService()
        cursor = svc.build_delta_bundle(db, "w110-h1", sources=["salesforce"], since_cursor=None)["payload"]["cursor"]

        doc = db.query(IngestedDocument).filter(
            IngestedDocument.workspace_id == "w110-h1",
            IngestedDocument.external_id == "sf-1",
        ).first()
        doc.freshness_status = "removed"
        doc.updated_at = datetime.now(timezone.utc) + timedelta(minutes=3)
        db.commit()

        delta = svc.build_delta_bundle(db, "w110-h1", sources=["salesforce"], since_cursor=cursor)
        assert delta["payload"]["tombstones"] == ["sf-1"]
        assert all(r["external_id"] != "sf-1" for r in delta["payload"]["records"])

    def test_delta_sensitivity_ceiling(self, key_file_env, worker_database):
        from core.org_hub_service import OrgHubService

        db = worker_database()
        _seed_documents(db, "w110-h1", integration="hr", sensitivity="restricted", count=1)
        _seed_documents(db, "w110-h1", integration="salesforce", sensitivity="internal", count=1)
        svc = OrgHubService()
        envelope = svc.build_delta_bundle(
            db, "w110-h1", sources=["hr", "salesforce"], since_cursor=None,
        )
        assert len(envelope["payload"]["records"]) == 1
        assert envelope["excluded_by_sensitivity"] == {"restricted": 1}

    def test_delta_signed_and_audited(self, key_file_env, worker_database):
        from core import org_sharing_crypto
        from core.ingestion_profile_service import canonical_payload
        from core.models import BundleExport
        from core.org_hub_service import OrgHubService

        db = worker_database()
        _seed_documents(db, "w110-h1", count=1)
        envelope = OrgHubService().build_delta_bundle(
            db, "w110-h1", sources=["salesforce"], since_cursor=None,
        )
        assert org_sharing_crypto.verify_payload(
            db, canonical_payload(envelope["payload"]), envelope["signature"], "w110-h1"
        )
        audit = db.query(BundleExport).filter(BundleExport.workspace_id == "w110-h1").all()
        assert len(audit) == 1
        assert audit[0].record_count == 1

    def test_cursor_round_trip(self):
        from core.org_hub_service import cursor_from_json, cursor_to_json

        cursor = {"salesforce": {"updated_at": "2026-08-16T10:00:00+00:00", "external_id": "sf-5"}}
        assert cursor_from_json(cursor_to_json(cursor)) == cursor
        assert cursor_from_json(None) == {}
        assert cursor_from_json("garbage{{{") == {}

    def test_pull_and_apply_incremental(self, key_file_env, worker_database):
        """Full member flow: pull → apply → cursor persisted → second pull skips."""
        from core.models import IngestedDocument
        from core.org_hub_service import OrgHubService

        db = worker_database()
        _seed_documents(db, "w110-h1", count=2)
        hub_svc = OrgHubService()
        first = hub_svc.build_delta_bundle(db, "w110-h1", sources=["salesforce"], since_cursor=None)
        second_delta = hub_svc.build_delta_bundle(
            db, "w110-h1", sources=["salesforce"], since_cursor=first["payload"]["cursor"]
        )

        class FakeResponse:
            def __init__(self, payload, status_code=200):
                self.payload = payload
                self.status_code = status_code

            def json(self):
                return self.payload

        responses = iter([
            FakeResponse(first),
            FakeResponse(second_delta),
        ])

        async def fake_get(url, params=None, headers=None):
            return next(responses)

        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = fake_get
            svc = OrgHubService()
            r1 = asyncio.run(svc.pull_and_apply(
                db, hub_url="http://hub:8000", api_key="atom_sk_test",
                sources=["salesforce"], workspace_id="w110-h2", tenant_id="t2",
            ))
            assert r1["records_ingested"] == 2
            assert r1["cursor"]["salesforce"]["external_id"] == "sf-1"

            # Second pull: cursor persisted → hub returns only the delta (empty
            # here since nothing changed on the hub) → 0 new records
            r2 = asyncio.run(svc.pull_and_apply(
                db, hub_url="http://hub:8000", api_key="atom_sk_test",
                sources=["salesforce"], workspace_id="w110-h2",
            ))
            assert r2["records_ingested"] == 0
            assert r2["records_skipped"] == 0

        docs = db.query(IngestedDocument).filter(IngestedDocument.workspace_id == "w110-h2").all()
        assert len(docs) == 2

    def test_pull_and_apply_401_raises(self, key_file_env, worker_database):
        from core.org_hub_service import HubError, OrgHubService

        db = worker_database()

        class Fake401:
            status_code = 401

            def json(self):
                return {}

        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = AsyncMock(return_value=Fake401())
            with pytest.raises(HubError, match="401"):
                asyncio.run(OrgHubService().pull_and_apply(
                    db, hub_url="http://hub", api_key="bad",
                    sources=["salesforce"], workspace_id="w110-h2",
                ))

    def test_pull_network_error_raises(self, key_file_env, worker_database):
        from core.org_hub_service import HubError, OrgHubService

        db = worker_database()
        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=RuntimeError("conn refused")
            )
            with pytest.raises(HubError, match="network"):
                asyncio.run(OrgHubService().pull_and_apply(
                    db, hub_url="http://hub", api_key="k",
                    sources=["salesforce"], workspace_id="w110-h2",
                ))


class TestOrgHubRoutes:
    @pytest.fixture
    def client(self, worker_database, key_file_env):
        from api.data_ingestion_routes import router
        from core.auth import get_current_user
        from core.database import get_db

        sf = worker_database

        def _override_user():
            return SimpleNamespace(id="w110-user")

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

    def test_hub_endpoint_gated_by_flag(self, client, key_file_env):
        # ATOM_ORG_HUB_ENABLED unset → 403
        resp = client.get("/api/data-ingestion/hub/bundles")
        assert resp.status_code == 403
        assert "ATOM_ORG_HUB_ENABLED" in str(resp.json())

    def test_hub_endpoint_requires_api_key(self, client, key_file_env, hub_enabled):
        resp = client.get("/api/data-ingestion/hub/bundles")
        assert resp.status_code == 401

    def test_hub_endpoint_rejects_bad_key(self, client, key_file_env, hub_enabled):
        resp = client.get(
            "/api/data-ingestion/hub/bundles",
            headers={"Authorization": "Bearer atom_sk_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"},
        )
        assert resp.status_code == 401

    def test_hub_endpoint_delta_flow(self, client, worker_database, key_file_env, hub_enabled):
        from core.models import IngestedDocument

        db = worker_database()
        _seed_documents(db, "default", count=2)
        key = _hub_key(db)

        resp = client.get(
            "/api/data-ingestion/hub/bundles?sources=salesforce",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 200
        envelope = resp.json()["data"]
        assert len(envelope["payload"]["records"]) == 2
        assert envelope["payload"]["hub_delta"] is True
        cursor = envelope["payload"]["cursor"]

        # incremental: new doc → only it comes back
        db.add(IngestedDocument(
            workspace_id="default", tenant_id="default", integration_id="salesforce",
            external_id="sf-new", file_name="n.txt", file_path="/org/sf/n", file_type="text",
            content_preview="New contact", sensitivity="internal",
            updated_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ))
        db.commit()
        resp2 = client.get(
            "/api/data-ingestion/hub/bundles?sources=salesforce&since=" + json.dumps(cursor),
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp2.status_code == 200
        records = resp2.json()["data"]["payload"]["records"]
        assert [r["external_id"] for r in records] == ["sf-new"]

    def test_member_pull_route(self, client, worker_database, key_file_env, sharing_enabled):
        """POST /hub/pull with a mocked hub returning a signed bundle."""
        from core.models import IngestedDocument
        from core.org_hub_service import OrgHubService

        db = worker_database()
        _seed_documents(db, "w110-hub", count=1)
        envelope = OrgHubService().build_delta_bundle(
            db, "w110-hub", sources=["salesforce"], since_cursor=None,
        )

        class FakeResponse:
            status_code = 200

            def json(self):
                return envelope

        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = AsyncMock(return_value=FakeResponse())
            resp = client.post(
                "/api/data-ingestion/hub/pull",
                json={"hub_url": "http://hub:8000", "api_key": "atom_sk_test",
                      "sources": ["salesforce"], "sensitivity_ceiling": "internal"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["records_ingested"] == 1

    def test_member_pull_route_gated(self, client, key_file_env):
        resp = client.post(
            "/api/data-ingestion/hub/pull",
            json={"hub_url": "http://hub", "api_key": "k", "sources": ["salesforce"]},
        )
        assert resp.status_code == 403
        assert "ATOM_ORG_SHARING_ENABLED" in str(resp.json())
