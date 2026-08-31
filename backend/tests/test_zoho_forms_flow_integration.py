# -*- coding: utf-8 -*-
"""Zoho Forms + Zoho Flow integration tests (webhook-push apps).

Zoho exposes no public read API for either product, so both ingest via
webhook push into per-integration LanceDB tables. These tests pin the
whole chain offline:

1. integrations/zoho_webhook_ingestion.py — payload normalization, upsert
   contract (table name, stable doc id, freshness/role stamps), trigger
   coordinator fan-out, fail-soft on write errors.
2. ZohoFormsService / ZohoFlowService — readback + search over the
   ingested table, execute_operation dispatch, health/capabilities.
3. Routers — /health, /capabilities, secret-protected Forms webhook
   (fail-closed without the secret), authed readback endpoints.
4. Registry wiring — service registry, NATIVE_INTEGRATIONS, status-route
   connection mappings.

Style: FastAPI TestClient + patches on real module paths; zero network,
zero LLM spend, no real DB.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations.zoho_webhook_ingestion import ingest_records, normalize_record


# ============================================================================
# Payload normalization
# ============================================================================


class TestNormalizeRecord:
    def test_forms_submission_flattens_arbitrary_fields(self):
        rec, text = normalize_record(
            {
                "EntryId": "E42",
                "Form": "Contact Us",
                "Name": "Jane Doe",
                "Email": "jane@wfs.example",
                "What can we help with": "pricing for the annual plan",
            },
            integration_id="zoho_forms",
            default_type="form_submission",
        )
        assert rec["id"] == "E42"
        assert rec["type"] == "form_submission"
        assert rec["form_name"] == "Contact Us"
        # arbitrary field labels must survive into the searchable text
        assert "What can we help with: pricing for the annual plan" in text
        assert "Jane Doe" in text

    def test_flow_event_uses_module_type_and_metadata_fields(self):
        rec, text = normalize_record(
            {
                "id": "F9",
                "module": "invoice_created",
                "flow_name": "Invoice sync",
                "company": "WFS Ltd",
                "amount": "1200",
                "modified_time": "2026-08-30T10:00:00Z",
            },
            integration_id="zoho_flow",
            default_type="event",
        )
        assert rec["id"] == "F9"
        assert rec["type"] == "invoice_created"
        assert rec["flow_name"] == "Invoice sync"
        assert rec["modified_at"] == "2026-08-30T10:00:00Z"
        assert "Invoice Created event from zoho_flow" in text
        assert "company: WFS Ltd" in text

    def test_missing_identity_gets_stable_uuid(self):
        rec, _ = normalize_record({"Name": "x"}, integration_id="zoho_forms", default_type="form_submission")
        assert rec["id"]

    def test_nested_values_rendered_not_dropped(self):
        _, text = normalize_record(
            {"items": [{"sku": "A1", "qty": 2}]},
            integration_id="zoho_forms",
            default_type="form_submission",
        )
        assert "items:" in text and "A1" in text


# ============================================================================
# Shared ingestion helper — upsert contract + trigger fan-out
# ============================================================================


def _fake_upsert(status="written"):
    upsert = AsyncMock(return_value=status)
    return upsert, patch("core.vector_upsert.upsert_document", new=upsert)


class TestIngestRecords:
    async def test_upserts_into_per_integration_table_with_stamps(self):
        upsert, p = _fake_upsert()
        trigger = AsyncMock()
        with p, patch("core.ai_trigger_coordinator.on_data_ingested", new=trigger):
            result = await ingest_records(
                MagicMock(),
                [{"id": "1", "Name": "Jane", "Email": "j@x.com"}],
                integration_id="zoho_forms",
                workspace_id="ws1",
                role="sales",
                default_type="form_submission",
            )
        assert result["received"] == 1 and result["ingested"] == 1
        assert upsert.await_count == 1
        kwargs = upsert.await_args.kwargs
        assert kwargs["table_name"] == "integration_zoho_forms"
        assert kwargs["doc_id"] == "rec_zoho_forms:1"
        assert kwargs["source"] == "zoho_forms"
        meta = kwargs["metadata"]
        assert meta["integration_id"] == "zoho_forms"
        assert meta["record_id"] == "1"
        assert meta["record_type"] == "form_submission"
        assert meta["freshness_status"] == "fresh"
        assert meta["role"] == "sales"
        assert meta["synced_at"] and meta["last_verified_at"]
        # written record fires the trigger coordinator
        assert trigger.await_count == 1
        assert trigger.await_args.kwargs["source"] == "zoho_forms"

    async def test_skipped_unchanged_does_not_fire_triggers(self):
        upsert, p = _fake_upsert(status="skipped_unchanged")
        trigger = AsyncMock()
        with p, patch("core.ai_trigger_coordinator.on_data_ingested", new=trigger):
            result = await ingest_records(
                MagicMock(), [{"id": "1"}], integration_id="zoho_flow"
            )
        assert result["ingested"] == 0
        assert result["skipped_unchanged"] == 1
        assert trigger.await_count == 0

    async def test_none_handler_reports_write_failed_without_raising(self):
        with patch("core.ai_trigger_coordinator.on_data_ingested", new=AsyncMock()):
            result = await ingest_records(
                None, [{"id": "1"}], integration_id="zoho_forms"
            )
        assert result["ingested"] == 0
        assert result["received"] == 1

    async def test_upsert_exception_is_contained(self):
        upsert = AsyncMock(side_effect=RuntimeError("lancedb down"))
        with patch("core.vector_upsert.upsert_document", new=upsert), patch(
            "core.ai_trigger_coordinator.on_data_ingested", new=AsyncMock()
        ):
            result = await ingest_records(
                MagicMock(), [{"id": "1"}], integration_id="zoho_forms"
            )
        assert result["ingested"] == 0

    async def test_sensitivity_classifier_failure_falls_back_to_internal(self):
        upsert, p = _fake_upsert()
        with patch(
            "core.data_taint_tracker.classify_sensitivity",
            side_effect=RuntimeError("nope"),
        ), p, patch("core.ai_trigger_coordinator.on_data_ingested", new=AsyncMock()):
            await ingest_records(
                MagicMock(), [{"id": "1"}], integration_id="zoho_forms"
            )
        meta = upsert.await_args.kwargs["metadata"]
        assert meta["sensitivity"] == "internal"


# ============================================================================
# Services
# ============================================================================


def _patch_handler(records=None, search_hits=None):
    handler = MagicMock()
    handler.list_documents = MagicMock(return_value=records or [])
    handler.search = MagicMock(return_value=search_hits or [])
    svc_factory = MagicMock(return_value=MagicMock(memory_handler=handler))
    return handler, patch(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service", new=svc_factory
    )


class TestZohoFormsService:
    def test_capabilities_document_webhook_push_mode(self):
        from integrations.zoho_forms_service import zoho_forms_service

        caps = zoho_forms_service.get_capabilities()
        assert caps["ingestion_mode"] == "webhook_push"
        assert caps["supports_pull_sync"] is False
        assert caps["webhook_secret_env"] == "ZOHOFORMS_WEBHOOK_SECRET"
        assert "ingest_records" in caps["operations"]

    def test_health_reports_webhook_configuration(self, monkeypatch):
        from integrations.zoho_forms_service import ZohoFormsService

        monkeypatch.delenv("ZOHOFORMS_WEBHOOK_SECRET", raising=False)
        assert ZohoFormsService().health_check()["webhook_configured"] is False
        monkeypatch.setenv("ZOHOFORMS_WEBHOOK_SECRET", "s3cret")
        assert ZohoFormsService().health_check()["webhook_configured"] is True

    async def test_list_and_search_submissions(self):
        from integrations.zoho_forms_service import ZohoFormsService

        handler, p = _patch_handler(
            records=[{"id": "r1"}], search_hits=[{"id": "r1", "text": "pricing"}]
        )
        with p:
            svc = ZohoFormsService(config={"workspace_id": "ws1"})
            recent = await svc.list_submissions()
            hits = await svc.search_submissions("pricing")
        handler.list_documents.assert_called_once_with("integration_zoho_forms", limit=20)
        handler.search.assert_called_once_with("integration_zoho_forms", "pricing", limit=10)
        assert recent == [{"id": "r1"}]
        assert hits[0]["text"] == "pricing"

    async def test_execute_operation_dispatch_and_unsupported(self):
        from integrations.zoho_forms_service import ZohoFormsService

        handler, p = _patch_handler()
        with p:
            svc = ZohoFormsService()
            ok = await svc.execute_operation("list_submissions", {})
            bad = await svc.execute_operation("delete_everything", {})
        assert ok["success"] is True
        assert bad["success"] is False and "Unsupported" in bad["error"]


class TestZohoFlowService:
    def test_capabilities_point_at_platform_webhook(self):
        from integrations.zoho_flow_service import zoho_flow_service

        caps = zoho_flow_service.get_capabilities()
        assert caps["webhook_path"] == "/webhooks/zoho-flow"
        assert caps["webhook_secret_env"] == "ZOHOFLOW_WEBHOOK_SECRET"
        assert caps["supports_pull_sync"] is False

    async def test_list_events_reads_integration_zoho_flow_table(self):
        from integrations.zoho_flow_service import ZohoFlowService

        handler, p = _patch_handler(records=[{"id": "e1"}])
        with p:
            events = await ZohoFlowService().list_events()
        handler.list_documents.assert_called_once_with("integration_zoho_flow", limit=20)
        assert events == [{"id": "e1"}]

    async def test_ingest_records_uses_shared_helper_contract(self):
        from integrations.zoho_flow_service import ZohoFlowService

        upsert = AsyncMock(return_value="written")
        handler, hp = _patch_handler()
        with hp, patch("core.vector_upsert.upsert_document", new=upsert), patch(
            "core.ai_trigger_coordinator.on_data_ingested", new=AsyncMock()
        ):
            result = await ZohoFlowService().ingest_records(
                [{"id": "e1", "module": "lead_created"}]
            )
        assert result["ingested"] == 1
        kwargs = upsert.await_args.kwargs
        assert kwargs["table_name"] == "integration_zoho_flow"
        assert kwargs["doc_id"] == "rec_zoho_flow:e1"


# ============================================================================
# Routers
# ============================================================================


def _forms_client():
    from integrations.zoho_forms_routes import router as forms_router

    app = FastAPI()
    app.include_router(forms_router, prefix="/api/v1/integrations/zoho-forms")
    return TestClient(app, raise_server_exceptions=False)


def _flow_client():
    from integrations.zoho_flow_routes import router as flow_router

    app = FastAPI()
    app.include_router(flow_router, prefix="/api/v1/integrations/zoho-flow")
    return TestClient(app, raise_server_exceptions=False)


class TestFormsRoutes:
    def test_health_and_capabilities_public(self):
        client = _forms_client()
        health = client.get("/api/v1/integrations/zoho-forms/health").json()
        assert health["healthy"] is True
        assert health["ingestion_mode"] == "webhook_push"
        caps = client.get("/api/v1/integrations/zoho-forms/capabilities").json()
        assert caps["webhook_path"] == "/api/v1/integrations/zoho-forms/webhook"

    def test_webhook_fails_closed_without_secret(self, monkeypatch):
        monkeypatch.delenv("ZOHOFORMS_WEBHOOK_SECRET", raising=False)
        client = _forms_client()
        res = client.post("/api/v1/integrations/zoho-forms/webhook", json={"a": 1})
        assert res.status_code == 401

    def test_webhook_rejects_wrong_secret(self, monkeypatch):
        monkeypatch.setenv("ZOHOFORMS_WEBHOOK_SECRET", "s3cret")
        client = _forms_client()
        res = client.post(
            "/api/v1/integrations/zoho-forms/webhook",
            json={"a": 1},
            headers={"Authorization": "Bearer wrong"},
        )
        assert res.status_code == 401

    def test_webhook_ingests_with_valid_secret(self, monkeypatch):
        monkeypatch.setenv("ZOHOFORMS_WEBHOOK_SECRET", "s3cret")
        upsert = AsyncMock(return_value="written")
        handler = MagicMock()
        svc_factory = MagicMock(return_value=MagicMock(memory_handler=handler))
        with patch("core.vector_upsert.upsert_document", new=upsert), patch(
            "core.ai_trigger_coordinator.on_data_ingested", new=AsyncMock()
        ), patch(
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service", new=svc_factory
        ):
            res = _forms_client().post(
                "/api/v1/integrations/zoho-forms/webhook",
                json={
                    "records": [
                        {"EntryId": "E1", "Form": "Contact", "Name": "Jane"},
                        {"EntryId": "E2", "Form": "Contact", "Name": "Bob"},
                    ]
                },
                headers={"Authorization": "Bearer s3cret"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True and body["ingested"] == 2
        assert upsert.await_count == 2
        assert upsert.await_args.kwargs["table_name"] == "integration_zoho_forms"

    def test_webhook_rejects_bad_json_and_empty_payload(self, monkeypatch):
        monkeypatch.setenv("ZOHOFORMS_WEBHOOK_SECRET", "s3cret")
        client = _forms_client()
        headers = {"Authorization": "Bearer s3cret"}
        assert client.post(
            "/api/v1/integrations/zoho-forms/webhook",
            data="not-json",
            headers=headers,
        ).status_code == 400
        assert client.post(
            "/api/v1/integrations/zoho-forms/webhook",
            json={"records": []},
            headers=headers,
        ).status_code == 400

    def test_submissions_requires_auth(self):
        client = _forms_client()
        assert (
            client.get("/api/v1/integrations/zoho-forms/submissions").status_code
            == 401
        )


class TestFlowRoutes:
    def test_health_and_capabilities_public(self):
        client = _flow_client()
        health = client.get("/api/v1/integrations/zoho-flow/health").json()
        assert health["healthy"] is True
        caps = client.get("/api/v1/integrations/zoho-flow/capabilities").json()
        assert caps["webhook_path"] == "/webhooks/zoho-flow"

    def test_events_requires_auth(self):
        client = _flow_client()
        assert client.get("/api/v1/integrations/zoho-flow/events").status_code == 401


# ============================================================================
# Registry / wiring
# ============================================================================


class TestRegistryWiring:
    def test_service_registry_entries_resolve(self):
        import importlib

        from core.integration_registry import DEFAULT_SERVICE_REGISTRY

        for key in ("zoho_forms", "zoho_flow"):
            assert key in DEFAULT_SERVICE_REGISTRY
            module_path, cls_name = DEFAULT_SERVICE_REGISTRY[key].split(":")
            module = importlib.import_module(module_path)
            assert hasattr(module, cls_name)

    async def test_native_integrations_and_dispatch(self):
        from integrations.universal_integration_service import (
            NATIVE_INTEGRATIONS,
            UniversalIntegrationService,
        )

        assert {"zoho_forms", "zoho_flow"} <= NATIVE_INTEGRATIONS

        handler, p = _patch_handler(records=[{"id": "r1"}])
        with p:
            svc = UniversalIntegrationService()
            result = await svc._execute_zoho(
                "zoho_forms", "list", {}, {"workspace_id": "ws1"}
            )
        assert result["status"] == "success"
        assert result["data"] == [{"id": "r1"}]
        handler.list_documents.assert_called_once_with("integration_zoho_forms", limit=20)

    def test_status_routes_map_suite_and_env_signals(self):
        from api.integration_status_routes import (
            _ENV_CREDENTIALS,
            _IT_PROVIDER_ALIASES,
            _PROVIDER_META,
        )

        assert _ENV_CREDENTIALS["zoho-forms"] == ["ZOHOFORMS_WEBHOOK_SECRET"]
        assert _ENV_CREDENTIALS["zoho-flow"] == ["ZOHOFLOW_WEBHOOK_SECRET"]
        assert {"zoho-forms", "zoho-flow"} <= set(_IT_PROVIDER_ALIASES["zoho"])
        assert _PROVIDER_META["zoho-forms"][0] == "Zoho Forms"
        assert _PROVIDER_META["zoho-flow"][0] == "Zoho Flow"

    def test_no_fake_oauth_scopes_added(self):
        """One unknown scope fails Zoho's whole consent URL — Forms/Flow must
        never appear in the suite scope list (no working scope exists)."""
        from core.oauth_handler import ZOHO_OAUTH_CONFIG

        joined = " ".join(ZOHO_OAUTH_CONFIG.scopes)
        assert "ZohoForms" not in joined
        assert "ZohoFlow" not in joined

    def test_not_registered_for_pull_sync(self):
        """Push-only apps must not appear as pull-sync integrations (a sync
        button that fetches nothing would be dishonest)."""
        from core.hybrid_data_ingestion import DEFAULT_SYNC_CONFIGS

        assert "zoho_forms" not in DEFAULT_SYNC_CONFIGS
        assert "zoho_flow" not in DEFAULT_SYNC_CONFIGS
