from __future__ import annotations

import pytest
import hmac
import hashlib
import json
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from core.database import get_db
from core.models import Tenant, TenantIntegration, UserConnection, DiscoveredEntity, WebhookTombstone
from core.tenant_discovery import TenantDiscoveryService

@pytest.fixture
def client(fastapi_app, db_session):
    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()

@pytest.fixture
def mock_db_setup(db_session):
    from core.models import UserConnection
    db_session.query(TenantIntegration).delete()
    db_session.query(UserConnection).delete()
    db_session.query(Tenant).delete()
    db_session.commit()

    # Setup test Tenant - use string ID to match model's default behavior
    tenant_id = "11234567-89ab-cdef-0123-456789abcdef"
    tenant = Tenant(
        id=tenant_id,
        subdomain="test-subdomain",
        name="Test Tenant"
    )
    db_session.add(tenant)
    db_session.flush()

    # Setup Slack integration config
    slack_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="slack",
        external_id="T_SLACK_123",
        is_active=True,
        config={"slack_signing_secret": "slack_secret_123"}
    )
    db_session.add(slack_integration)
    db_session.flush()

    # Setup HubSpot integration config
    hubspot_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="hubspot",
        external_id="PORTAL_123",
        is_active=True,
        config={"client_secret": "hubspot_secret_123"}
    )
    db_session.add(hubspot_integration)
    db_session.flush()

    # Setup Salesforce integration config
    salesforce_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="salesforce",
        external_id="ORG_123",
        is_active=True,
        config={"client_secret": "salesforce_secret_123"}
    )
    db_session.add(salesforce_integration)
    db_session.flush()

    # Setup Gmail integration config
    gmail_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="gmail",
        external_id="gmail_user@example.com",
        is_active=True,
        config={}
    )
    db_session.add(gmail_integration)
    db_session.flush()

    from core.models import UserConnection
    # Use string IDs to match model's default behavior
    gmail_conn = UserConnection(
        id="c1234567-89ab-cdef-0123-456789abcdef",
        user_id="a1234567-89ab-cdef-0123-456789abcdef",
        tenant_id=tenant_id,
        workspace_id=tenant_id,
        integration_id="gmail",
        connection_name="Gmail Connect",
        credentials={"access_token": "token_abc"},
        status="active"
    )
    db_session.add(gmail_conn)
    db_session.flush()

    # Setup Notion integration config
    notion_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="notion",
        external_id="WORKSPACE_123",
        is_active=True,
        config={"client_secret": "notion_secret_123"}
    )
    db_session.add(notion_integration)
    db_session.flush()

    # Setup Zoho CRM integration config for webhook TDD
    zoho_crm_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="zoho_crm",
        external_id="zoho_org_999",
        is_active=True,
        config={}
    )
    db_session.add(zoho_crm_integration)

    # Setup Zoho generic integration config for fallback tenant discovery
    zoho_generic_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="zoho",
        external_id="zoho_org_999",
        is_active=True,
        config={}
    )
    db_session.add(zoho_generic_integration)

    # Setup Jira integration config for webhook TDD
    jira_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="jira",
        external_id="jira_org_123",
        is_active=True,
        config={}
    )
    db_session.add(jira_integration)

    # Setup PM/CRM generic integration config for fallback tenant discovery
    pm_crm_generic_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="pm_crm",
        external_id="pm_crm_fallback_org",
        is_active=True,
        config={}
    )
    db_session.add(pm_crm_generic_integration)

    # Setup Twilio integration config for webhook TDD
    twilio_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="twilio",
        external_id="twilio_acme_sid",
        is_active=True,
        config={}
    )
    db_session.add(twilio_integration)

    # Setup Communication generic integration config for fallback tenant discovery
    communication_generic_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="communication",
        external_id="comm_fallback_workspace",
        is_active=True,
        config={}
    )
    db_session.add(communication_generic_integration)

    # Setup GitHub integration config for webhook TDD
    github_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="github",
        external_id="github_org_owner",
        is_active=True,
        config={}
    )
    db_session.add(github_integration)

    # Setup Dev/Prod generic integration config for fallback tenant discovery
    dev_prod_generic_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="dev_prod",
        external_id="dev_prod_fallback_workspace",
        is_active=True,
        config={}
    )
    db_session.add(dev_prod_generic_integration)

    # Setup Shopify integration config for webhook TDD
    shopify_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="shopify",
        external_id="shopify_store_id",
        is_active=True,
        config={}
    )
    db_session.add(shopify_integration)

    # Setup E-commerce/Marketing generic integration config for fallback tenant discovery
    ecommerce_marketing_generic_integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id="ecommerce_marketing",
        external_id="ecom_fallback_workspace",
        is_active=True,
        config={}
    )
    db_session.add(ecommerce_marketing_generic_integration)
    db_session.commit()

    return tenant

@pytest.mark.unit
class TestRealTimeWebhooksTDD:
    """TDD integration suite for unauthenticated real-time webhook routes & RLS bypass verification."""

    # =========================================================================
    # Slack Webhook Tests
    # =========================================================================

    def test_slack_url_verification_challenge(self, client):
        """Slack URL verification challenge should return challenge value directly."""
        challenge_payload = {
            "type": "url_verification",
            "challenge": "challenge_token_abc123"
        }
        response = client.post("/api/webhooks/slack/events", json=challenge_payload)
        assert response.status_code == 200
        assert response.json() == {"challenge": "challenge_token_abc123"}

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_slack_webhook_success(self, mock_enqueue, client, mock_db_setup):
        """Successful Slack webhook event processing with signature verification and queue enqueueing."""
        mock_enqueue.return_value = "job_slack_abc"
        
        payload_dict = {
            "type": "event_callback",
            "team_id": "T_SLACK_123",
            "event": {
                "type": "message",
                "text": "Hello Slack Ingestion!"
            }
        }
        body_bytes = json.dumps(payload_dict).encode("utf-8")
        
        # Calculate raw HMAC signature
        signature = hmac.new(b"slack_secret_123", body_bytes, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": "123456789",
            "X-Slack-Signature": signature
        }
        
        response = client.post("/api/webhooks/slack/events", content=body_bytes, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued", "job_id": "job_slack_abc"}
        mock_enqueue.assert_called_once()

    # =========================================================================
    # HubSpot Webhook Tests
    # =========================================================================

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_hubspot_webhook_success(self, mock_enqueue, client, mock_db_setup):
        """HubSpot webhook batch event processing with signature verification."""
        mock_enqueue.return_value = "job_hubspot_abc"
        
        payload_dict = [
            {
                "eventId": "1",
                "portalId": "PORTAL_123",
                "subscriptionType": "company.creation"
            }
        ]
        body_bytes = json.dumps(payload_dict).encode("utf-8")
        
        # Calculate raw HMAC signature
        signature = hmac.new(b"hubspot_secret_123", body_bytes, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-HubSpot-Signature": signature
        }
        
        response = client.post("/api/webhooks/hubspot/events", content=body_bytes, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued"}
        mock_enqueue.assert_called_once()

    # =========================================================================
    # Salesforce Webhook Tests
    # =========================================================================

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_salesforce_webhook_success(self, mock_enqueue, client, mock_db_setup):
        """Salesforce webhook event processing with signature verification."""
        mock_enqueue.return_value = "job_salesforce_abc"
        
        payload_dict = {
            "orgId": "ORG_123",
            "sobjectType": "Lead",
            "id": "lead_999"
        }
        body_bytes = json.dumps(payload_dict).encode("utf-8")
        
        # Salesforce signature uses HMAC SHA256
        signature = hmac.new(b"salesforce_secret_123", body_bytes, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Salesforce-Signature": signature
        }
        
        response = client.post("/api/webhooks/salesforce/events", content=body_bytes, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued", "job_id": "job_salesforce_abc"}
        mock_enqueue.assert_called_once()

    # =========================================================================
    # Gmail Webhook Tests
    # =========================================================================

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_gmail_webhook_success(self, mock_enqueue, client, mock_db_setup):
        """Gmail Pub/Sub notification processing and user connection mapping."""
        mock_enqueue.return_value = "job_gmail_abc"
        
        payload_dict = {
            "emailAddress": "gmail_user@example.com",
            "historyId": "999888"
        }
        body_bytes = json.dumps(payload_dict).encode("utf-8")
        
        headers = {
            "Content-Type": "application/json"
        }
        
        response = client.post("/api/webhooks/gmail/events", content=body_bytes, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued", "job_id": "job_gmail_abc"}
        mock_enqueue.assert_called_once()

    # =========================================================================
    # Notion Webhook Tests
    # =========================================================================

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_notion_webhook_success(self, mock_enqueue, client, mock_db_setup):
        """Notion webhook event processing with signature verification."""
        mock_enqueue.return_value = "job_notion_abc"
        
        payload_dict = {
            "workspace_id": "WORKSPACE_123",
            "event": "page.created"
        }
        body_bytes = json.dumps(payload_dict).encode("utf-8")
        
        # Notion signature uses HMAC SHA256
        signature = hmac.new(b"notion_secret_123", body_bytes, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Notion-Signature": signature
        }
        
        response = client.post("/api/webhooks/notion/events", content=body_bytes, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued", "job_id": "job_notion_abc"}
        mock_enqueue.assert_called_once()

    # =========================================================================
    # PostgreSQL Row-Level Security Dialect Simulation Tests
    # =========================================================================

    async def test_rls_bypass_postgres_dialect_execution(self, db_session, mock_db_setup):
        """Verify that when the database is PostgreSQL, RLS bypass and re-enable commands are executed."""
        # 1. Setup mock engine binding with Postgres dialect name
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        
        # 2. Mock db_session.execute to capture text commands
        mock_execute = MagicMock()
        
        with patch.object(db_session, "bind", mock_bind), \
             patch.object(db_session, "execute", mock_execute):
             
             discoverer = TenantDiscoveryService(db_session)
             
             # Force cache miss
             async def mock_get(*args, **kwargs):
                 return None
             discoverer.cache.get_async = mock_get
             
             # Call the target discovery service
             await discoverer.get_tenant_id_by_external_id("slack", "T_SLACK_123")
             
             # Assert that 'SET LOCAL row_security = off' and 'on' are executed
             executed_sqls = [str(call[0][0]) for call in mock_execute.call_args_list]
             assert any("SET LOCAL row_security = off" in sql for sql in executed_sqls)
             assert any("SET LOCAL row_security = on" in sql for sql in executed_sqls)

    # =========================================================================
    # New Gmail Pub/Sub Base64 & Zoho Webhook Tests
    # =========================================================================

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_gmail_pubsub_base64_webhook_success(self, mock_enqueue, client, mock_db_setup):
        """Gmail Pub/Sub base64 wrapped payload processing and connection mapping."""
        mock_enqueue.return_value = "job_gmail_pubsub_abc"

        # Construct inner JSON payload
        inner_payload = {
            "emailAddress": "gmail_user@example.com",
            "historyId": "999888"
        }
        
        # Base64 encode the inner payload
        import base64
        base64_str = base64.b64encode(json.dumps(inner_payload).encode("utf-8")).decode("utf-8")

        # Wrap in Pub/Sub message format
        pubsub_payload = {
            "message": {
                "data": base64_str,
                "messageId": "msg_12345"
            }
        }
        
        body_bytes = json.dumps(pubsub_payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json"
        }
        
        response = client.post("/api/webhooks/gmail/events", content=body_bytes, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued", "job_id": "job_gmail_pubsub_abc"}
        
        # Verify that source_connection_id was resolved and passed
        mock_enqueue.assert_called_once_with(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            integration_id="gmail",
            trigger_type="webhook",
            payload=inner_payload, # Should be the decoded inner payload
            source_connection_id="c1234567-89ab-cdef-0123-456789abcdef" # Resolved active connection
        )

    @pytest.mark.asyncio
    async def test_gmail_message_realtime_fetch(self):
        """Verify real-time history and message fetching in _transform_gmail_payload."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        # Initialize pipeline service
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        # Webhook data with source connection
        webhook_data = {
            "historyId": "999888",
            "_source_connection_id": "c1234567-89ab-cdef-0123-456789abcdef"
        }
        
        # Mock Google API responses
        mock_history = {
            "history": [
                {
                    "messagesAdded": [
                        {
                            "message": {
                                "id": "m999",
                                "threadId": "t999"
                            }
                        }
                    ]
                }
            ]
        }
        
        mock_message_detail = {
            "id": "m999",
            "threadId": "t999",
            "snippet": "Hello world from Gmail real-time webhook!",
            "internalDate": "1715875200000", # Milliseconds timestamp
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Real-time Testing"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "gmail_user@example.com"}
                ]
            }
        }
        
        # Mock direct fetch method
        async def mock_fetch(conn_id, path):
            if "history" in path:
                return mock_history
            elif "messages" in path:
                return mock_message_detail
            return None
            
        with patch.object(pipeline, "_fetch_gmail_resource_direct", side_effect=mock_fetch):
            records = await pipeline._transform_gmail_payload(webhook_data)
            
            assert len(records) == 1
            record = records[0]
            assert record["type"] == "gmail_message"
            assert record["id"] == "m999"
            assert record["subject"] == "Real-time Testing"
            assert record["content"] == "Hello world from Gmail real-time webhook!"
            assert record["from"] == "sender@example.com"
            assert record["to"] == "gmail_user@example.com"
            assert "2024-05-16" in record["timestamp"]

    @pytest.mark.asyncio
    async def test_zoho_crm_webhook_success(self):
        """Verify Zoho CRM webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "module": {"api_name": "Leads"},
            "key_id": "zoho_lead_123",
            "operation": "insert",
            "data": {"First_Name": "Rushi", "Last_Name": "Parikh", "Email": "rushi@example.com"}
        }
        
        records = await pipeline._transform_zoho_crm_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_crm_leads"
        assert record["id"] == "zoho_lead_123"
        assert record["object_type"] == "Leads"
        assert record["properties"]["First_Name"] == "Rushi"
        assert record["event_type"] == "insert"

    @pytest.mark.asyncio
    async def test_zoho_books_webhook_success(self):
        """Verify Zoho Books webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "module": "Invoices",
            "IDs": {"entity_id": "zoho_invoice_123"},
            "event_type": "invoice_created",
            "payload": {"invoice_number": "INV-001", "total": 100.0}
        }
        
        records = await pipeline._transform_zoho_books_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_books_invoices"
        assert record["id"] == "zoho_invoice_123"
        assert record["object_type"] == "Invoices"
        assert record["properties"]["invoice_number"] == "INV-001"
        assert record["event_type"] == "invoice_created"

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_zoho_suite_webhook_routing_success(self, mock_enqueue, client, mock_db_setup, db_session):
        """Verify Zoho webhook routing, reverse tenant discovery, job enqueueing, and source_connection_id resolution."""
        # Setup Zoho UserConnection for BYOK credential lookup
        from core.models import UserConnection
        tenant_id = "11234567-89ab-cdef-0123-456789abcdef"
        zoho_conn = UserConnection(
            id="c9999999-9999-9999-9999-999999999999",
            user_id="a1234567-89ab-cdef-0123-456789abcdef",
            tenant_id=tenant_id,
            integration_id="zoho_crm",
            connection_name="Zoho CRM Connection",
            status="active",
            credentials={"encrypted_token": "mock_zoho_token"}
        )
        db_session.add(zoho_conn)
        db_session.flush()

        mock_enqueue.return_value = "job_zoho_crm_abc"

        # Prepare test payload with orgId
        payload = {
            "orgId": "zoho_org_999",
            "module": {"api_name": "Leads"},
            "key_id": "zoho_lead_123",
            "data": {"First_Name": "Rushi"}
        }

        # Perform request to the unified Zoho CRM webhook endpoint
        response = client.post(
            "/api/webhooks/zoho/zoho-crm",
            json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "enqueued"

        # Verify that the background job was enqueued with the correct parameters including source_connection_id
        mock_enqueue.assert_called_once_with(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            integration_id="zoho_crm",
            trigger_type="webhook",
            payload=payload,
            source_connection_id="c9999999-9999-9999-9999-999999999999"
        )

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_zoho_suite_webhook_without_user_connection(self, mock_enqueue, client, mock_db_setup):
        """Verify Zoho webhook handles missing UserConnection gracefully (source_connection_id=None)."""
        mock_enqueue.return_value = "job_zoho_books_abc"

        # No UserConnection set up for zoho_books - should handle gracefully with source_connection_id=None
        payload = {
            "orgId": "zoho_org_999",
            "module": "Invoices",
            "key_id": "zoho_invoice_123",
            "data": {"invoice_number": "INV-001"}
        }

        response = client.post(
            "/api/webhooks/zoho/zoho-books",
            json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "enqueued"

        # Verify that the webhook still works with source_connection_id=None
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["tenant_id"] == "11234567-89ab-cdef-0123-456789abcdef"
        assert call_kwargs["integration_id"] == "zoho_books"
        assert call_kwargs["trigger_type"] == "webhook"
        assert call_kwargs["source_connection_id"] is None  # No connection exists

    @pytest.mark.asyncio
    async def test_zoho_projects_webhook_success(self):
        """Verify Zoho Projects webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "project_id": "9999",
            "module": "Tasks",
            "id": "zoho_task_123",
            "operation": "insert",
            "data": {"name": "Create rollout plan", "status": "In Progress"}
        }
        
        records = await pipeline._transform_zoho_projects_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_projects_tasks"
        assert record["id"] == "zoho_task_123"
        assert record["project_id"] == "9999"
        assert record["object_type"] == "Tasks"
        assert record["properties"]["name"] == "Create rollout plan"
        assert record["event_type"] == "insert"

    @pytest.mark.asyncio
    async def test_zoho_desk_webhook_success(self):
        """Verify Zoho Desk webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "ticketId": "zoho_ticket_123",
            "ticket": {"subject": "Need help with OAuth", "priority": "High"},
            "action": "create"
        }
        
        records = await pipeline._transform_zoho_desk_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_desk_ticket"
        assert record["id"] == "zoho_ticket_123"
        assert record["object_type"] == "ticket"
        assert record["properties"]["subject"] == "Need help with OAuth"
        assert record["event_type"] == "create"

    @pytest.mark.asyncio
    async def test_zoho_recruit_webhook_success(self):
        """Verify Zoho Recruit webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "module": "Candidates",
            "entityId": "zoho_candidate_123",
            "operation": "update",
            "data": {"First_Name": "Rushi", "Status": "Shortlisted"}
        }
        
        records = await pipeline._transform_zoho_recruit_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_recruit_candidates"
        assert record["id"] == "zoho_candidate_123"
        assert record["object_type"] == "Candidates"
        assert record["properties"]["First_Name"] == "Rushi"
        assert record["event_type"] == "update"

    @pytest.mark.asyncio
    async def test_zoho_campaigns_webhook_success(self):
        """Verify Zoho Campaigns webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "campaign_id": "zoho_camp_123",
            "event_type": "sent",
            "data": {"subject": "May Newsletter", "sent_count": 500}
        }
        
        records = await pipeline._transform_zoho_campaigns_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_campaigns_campaign"
        assert record["id"] == "zoho_camp_123"
        assert record["object_type"] == "campaign"
        assert record["properties"]["subject"] == "May Newsletter"
        assert record["event_type"] == "sent"

    @pytest.mark.asyncio
    async def test_zoho_forms_webhook_success(self):
        """Verify Zoho Forms webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "submission_id": "zoho_form_123",
            "event_type": "submitted",
            "data": {"Name": "Rushi", "Feedback": "Excellent app!"}
        }
        
        records = await pipeline._transform_zoho_forms_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_forms_submission"
        assert record["id"] == "zoho_form_123"
        assert record["object_type"] == "form_submission"
        assert record["properties"]["Name"] == "Rushi"
        assert record["event_type"] == "submitted"

    @pytest.mark.asyncio
    async def test_zoho_showtime_webhook_success(self):
        """Verify Zoho ShowTime webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "session_id": "zoho_session_123",
            "event_type": "session_ended",
            "data": {"title": "Sales Training", "duration_mins": 60}
        }
        
        records = await pipeline._transform_zoho_showtime_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_showtime_session"
        assert record["id"] == "zoho_session_123"
        assert record["object_type"] == "training_session"
        assert record["properties"]["title"] == "Sales Training"
        assert record["event_type"] == "session_ended"

    @pytest.mark.asyncio
    async def test_zoho_meeting_webhook_success(self):
        """Verify Zoho Meeting webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "meeting_id": "zoho_meet_123",
            "event_type": "meeting_started",
            "data": {"topic": "Sprint Planning", "participants_count": 8}
        }
        
        records = await pipeline._transform_zoho_meeting_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_meeting_session"
        assert record["id"] == "zoho_meet_123"
        assert record["object_type"] == "meeting"
        assert record["properties"]["topic"] == "Sprint Planning"
        assert record["event_type"] == "meeting_started"

    @pytest.mark.asyncio
    async def test_zoho_assist_webhook_success(self):
        """Verify Zoho Assist webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        webhook_data = {
            "session_id": "zoho_assist_123",
            "event_type": "session_completed",
            "data": {"technician": "support_agent_1", "customer_email": "cust@example.com"}
        }
        
        records = await pipeline._transform_zoho_assist_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoho_assist_session"
        assert record["id"] == "zoho_assist_123"
        assert record["object_type"] == "support_session"
        assert record["properties"]["technician"] == "support_agent_1"
        assert record["event_type"] == "session_completed"

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_zoho_suite_webhook_routing_all(self, mock_enqueue, client, mock_db_setup):
        """Verify routing and tenant discovery for all 10 Zoho suite integrations."""
        zoho_services = [
            "zoho-crm", "zoho-books", "zoho-projects", "zoho-desk", "zoho-recruit",
            "zoho-campaigns", "zoho-forms", "zoho-showtime", "zoho-meeting", "zoho-assist"
        ]
        
        for idx, service in enumerate(zoho_services):
            mock_enqueue.reset_mock()
            mock_enqueue.return_value = f"job_{service.replace('-', '_')}_abc"
            
            payload = {
                "orgId": "zoho_org_999",
                "key_id": f"{service}_id_{idx}",
                "data": {"test": "data"}
            }
            
            response = client.post(
                f"/api/webhooks/zoho/{service}",
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "enqueued"
            assert data["job_id"] == f"job_{service.replace('-', '_')}_abc"
            
            mock_enqueue.assert_called_once_with(
                tenant_id="11234567-89ab-cdef-0123-456789abcdef",
                integration_id=service.replace("-", "_"),
                trigger_type="webhook",
                payload=payload,
                source_connection_id=None
            )

    def test_pm_crm_webhook_handshakes(self, client):
        """Verify handshakes for Asana (X-Hook-Secret), Monday (challenge), and Trello (HEAD)."""
        # 1. Asana handshake
        response = client.post(
            "/api/webhooks/pm-crm/asana",
            headers={"X-Hook-Secret": "asana_secret_123"}
        )
        assert response.status_code == 200
        assert response.headers.get("X-Hook-Secret") == "asana_secret_123"

        # 2. Monday handshake
        response = client.post(
            "/api/webhooks/pm-crm/monday",
            json={"challenge": "monday_challenge_abc"}
        )
        assert response.status_code == 200
        assert response.json() == {"challenge": "monday_challenge_abc"}

        # 3. Trello HEAD request
        response = client.head("/api/webhooks/pm-crm/trello")
        assert response.status_code == 200

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_pm_crm_webhook_routing_all(self, mock_enqueue, client, mock_db_setup, db_session):
        """Verify routing and tenant discovery for all 10 PM and CRM integrations, including source_connection_id resolution."""
        from core.models import UserConnection

        # Setup Jira UserConnection for BYOK credential lookup
        tenant_id = "11234567-89ab-cdef-0123-456789abcdef"
        jira_conn = UserConnection(
            id="c8888888-8888-8888-8888-888888888888",
            user_id="a1234567-89ab-cdef-0123-456789abcdef",
            tenant_id=tenant_id,
            integration_id="jira",
            connection_name="Jira Test Connection",
            status="active",
            credentials={"encrypted_token": "mock_jira_token"}
        )
        db_session.add(jira_conn)
        db_session.flush()

        pm_crm_services = [
            "jira", "asana", "trello", "monday", "clickup", "linear",
            "pipedrive", "zendesk-sell", "insightly", "freshsales"
        ]

        # 1. Specific connector matching (e.g. Jira with jira_org_123) - WITH source_connection_id
        mock_enqueue.return_value = "job_jira_abc"
        payload_jira = {
            "clientKey": "jira_org_123",
            "issue": {"id": "1"}
        }
        response = client.post(
            "/api/webhooks/pm-crm/jira",
            json=payload_jira
        )
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued", "job_id": "job_jira_abc"}
        mock_enqueue.assert_called_once_with(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            integration_id="jira",
            trigger_type="webhook",
            payload=payload_jira,
            source_connection_id="c8888888-8888-8888-8888-888888888888"
        )

        # 2. Fallback matching (e.g. all other services using pm_crm fallback mapping)
        for idx, service in enumerate(pm_crm_services):
            if service == "jira":
                continue
            
            mock_enqueue.reset_mock()
            normalized_service = service.replace("-", "_")
            mock_enqueue.return_value = f"job_{normalized_service}_abc"

            # Create service-specific payload with the fallback org identifier
            if service == "monday":
                payload = {"accountId": "pm_crm_fallback_org", "event": {}}
            elif service == "linear":
                payload = {"organizationId": "pm_crm_fallback_org"}
            elif service == "pipedrive":
                payload = {"company_id": "pm_crm_fallback_org"}
            elif service == "clickup":
                payload = {"team_id": "pm_crm_fallback_org"}
            elif service == "zendesk-sell":
                payload = {"account_id": "pm_crm_fallback_org"}
            elif service == "insightly":
                payload = {"insightly_org_id": "pm_crm_fallback_org"}
            elif service == "freshsales":
                payload = {"account_id": "pm_crm_fallback_org"}
            elif service == "asana":
                payload = {"events": [{"workspace": "pm_crm_fallback_org"}]}
            else: # trello
                payload = {"model": {"idOrganization": "pm_crm_fallback_org"}}

            response = client.post(
                f"/api/webhooks/pm-crm/{service}",
                json=payload
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "enqueued"
            assert data["job_id"] == f"job_{normalized_service}_abc"

            mock_enqueue.assert_called_once_with(
                tenant_id="11234567-89ab-cdef-0123-456789abcdef",
                integration_id=normalized_service,
                trigger_type="webhook",
                payload=payload,
                source_connection_id=None  # No UserConnection for other services in this test
            )

    @pytest.mark.asyncio
    async def test_jira_payload_transformation(self):
        """Verify Jira webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "webhookEvent": "jira:issue_created",
            "issue": {
                "id": "jira_issue_123",
                "key": "PROJ-1",
                "fields": {
                    "summary": "Fix login crash",
                    "status": {"name": "In Progress"},
                    "assignee": {"displayName": "Rushi Parikh"}
                }
            }
        }
        records = await pipeline._transform_jira_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "jira_issue"
        assert record["id"] == "jira_issue_123"
        assert record["key"] == "PROJ-1"
        assert record["summary"] == "Fix login crash"
        assert record["status"] == "In Progress"
        assert record["assignee"] == "Rushi Parikh"
        assert record["event_type"] == "jira:issue_created"

    @pytest.mark.asyncio
    async def test_asana_payload_transformation(self):
        """Verify Asana webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "gid": "asana_task_123",
            "name": "Design UI dashboard",
            "completed": True,
            "action": "changed"
        }
        records = await pipeline._transform_asana_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "asana_task"
        assert record["id"] == "asana_task_123"
        assert record["name"] == "Design UI dashboard"
        assert record["completed"] is True
        assert record["event_type"] == "changed"

    @pytest.mark.asyncio
    async def test_trello_payload_transformation(self):
        """Verify Trello webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "action": {
                "type": "updateCard",
                "data": {
                    "card": {"id": "trello_card_123", "name": "Review PR"},
                    "listAfter": {"id": "list_done_999"}
                }
            }
        }
        records = await pipeline._transform_trello_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "trello_card"
        assert record["id"] == "trello_card_123"
        assert record["name"] == "Review PR"
        assert record["list_id"] == "list_done_999"
        assert record["event_type"] == "updateCard"

    @pytest.mark.asyncio
    async def test_monday_payload_transformation(self):
        """Verify Monday webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "event": {"type": "create_item"},
            "payload": {
                "item_id": "monday_item_123",
                "item_name": "Deploy production bundle",
                "board_id": "board_777",
                "column_values": {"status": "Done"}
            }
        }
        records = await pipeline._transform_monday_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "monday_item"
        assert record["id"] == "monday_item_123"
        assert record["name"] == "Deploy production bundle"
        assert record["board_id"] == "board_777"
        assert record["event_type"] == "create_item"

    @pytest.mark.asyncio
    async def test_clickup_payload_transformation(self):
        """Verify ClickUp webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "event": "taskCreated",
            "task": {
                "id": "clickup_task_123",
                "name": "Write TDD coverage",
                "status": "complete"
            }
        }
        records = await pipeline._transform_clickup_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "clickup_task"
        assert record["id"] == "clickup_task_123"
        assert record["name"] == "Write TDD coverage"
        assert record["status"] == "complete"
        assert record["event_type"] == "taskCreated"

    @pytest.mark.asyncio
    async def test_linear_payload_transformation(self):
        """Verify Linear webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "action": "create",
            "data": {
                "id": "linear_issue_123",
                "title": "Optimize cache latency",
                "state": {"name": "Backlog"}
            }
        }
        records = await pipeline._transform_linear_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "linear_issue"
        assert record["id"] == "linear_issue_123"
        assert record["title"] == "Optimize cache latency"
        assert record["state"] == "Backlog"
        assert record["event_type"] == "create"

    @pytest.mark.asyncio
    async def test_pipedrive_payload_transformation(self):
        """Verify Pipedrive webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "object": "deal",
            "event": "added",
            "current": {
                "id": "pipedrive_deal_123",
                "title": "Acme Corp Agreement",
                "value": 50000
            }
        }
        records = await pipeline._transform_pipedrive_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "pipedrive_deal"
        assert record["id"] == "pipedrive_deal_123"
        assert record["title"] == "Acme Corp Agreement"
        assert record["value"] == 50000
        assert record["object_type"] == "deal"
        assert record["event_type"] == "added"

    @pytest.mark.asyncio
    async def test_zendesk_sell_payload_transformation(self):
        """Verify Zendesk Sell webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "target_type": "lead",
            "target_id": "zendesk_lead_123",
            "trigger": "lead.created",
            "payload": {"name": "Rushi"}
        }
        records = await pipeline._transform_zendesk_sell_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zendesk_sell_lead"
        assert record["id"] == "zendesk_lead_123"
        assert record["object_type"] == "lead"
        assert record["properties"]["payload"]["name"] == "Rushi"
        assert record["event_type"] == "lead.created"

    @pytest.mark.asyncio
    async def test_insightly_payload_transformation(self):
        """Verify Insightly webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "object_name": "contact",
            "record_id": "insightly_contact_123",
            "event": "inserted",
            "data": {"first_name": "Rushi", "last_name": "Parikh"}
        }
        records = await pipeline._transform_insightly_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "insightly_contact"
        assert record["id"] == "insightly_contact_123"
        assert record["object_type"] == "contact"
        assert record["properties"]["first_name"] == "Rushi"
        assert record["event_type"] == "inserted"

    @pytest.mark.asyncio
    async def test_freshsales_payload_transformation(self):
        """Verify Freshsales webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "entity_type": "contact",
            "action": "create",
            "payload": {
                "id": "freshsales_contact_123",
                "emails": "rushi@example.com"
            }
        }
        records = await pipeline._transform_freshsales_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "freshsales_contact"
        assert record["id"] == "freshsales_contact_123"
        assert record["object_type"] == "contact"
        assert record["properties"]["emails"] == "rushi@example.com"
        assert record["event_type"] == "create"

    def test_communication_webhook_handshakes(self, client):
        """Verify handshakes and URL-encoded form parsing for Communication integrations."""
        # 1. HEAD request
        response = client.head("/api/webhooks/communication/discord")
        assert response.status_code == 200

        # 2. Twilio URL-encoded form parsing
        response = client.post(
            "/api/webhooks/communication/twilio",
            data={"AccountSid": "twilio_acme_sid", "Body": "Hello world"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 200

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_communication_webhook_routing_all(self, mock_enqueue, client, mock_db_setup):
        """Verify routing and tenant discovery for all 5 Communication integrations."""
        communication_services = [
            "discord", "teams", "telegram", "twilio", "intercom"
        ]

        # 1. Specific connector matching (e.g. Twilio with twilio_acme_sid)
        mock_enqueue.return_value = "job_twilio_abc"
        payload_twilio = {
            "AccountSid": "twilio_acme_sid",
            "Body": "Hello world"
        }
        response = client.post(
            "/api/webhooks/communication/twilio",
            json=payload_twilio
        )
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued", "job_id": "job_twilio_abc"}
        mock_enqueue.assert_called_once_with(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            integration_id="twilio",
            trigger_type="webhook",
            payload=payload_twilio,
            source_connection_id=None  # No UserConnection for this test
        )

        # 2. Fallback matching (e.g. all other services using communication base fallback mapping)
        for idx, service in enumerate(communication_services):
            if service == "twilio":
                continue
            
            mock_enqueue.reset_mock()
            normalized_service = service.replace("-", "_")
            mock_enqueue.return_value = f"job_{normalized_service}_abc"

            # Create service-specific payload with the fallback workspace identifier
            if service == "intercom":
                payload = {"app_id": "comm_fallback_workspace"}
            elif service == "teams":
                payload = {"tenantId": "comm_fallback_workspace"}
            elif service == "telegram":
                payload = {"message": {"chat": {"id": "comm_fallback_workspace"}}}
            else: # discord
                payload = {"guild_id": "comm_fallback_workspace"}

            response = client.post(
                f"/api/webhooks/communication/{service}",
                json=payload
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "enqueued"
            assert data["job_id"] == f"job_{normalized_service}_abc"

            mock_enqueue.assert_called_once_with(
                tenant_id="11234567-89ab-cdef-0123-456789abcdef",
                integration_id=normalized_service,
                trigger_type="webhook",
                payload=payload,
                source_connection_id=None  # No UserConnection for other services in this test
            )

    @pytest.mark.asyncio
    async def test_discord_payload_transformation(self):
        """Verify Discord webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "id": "discord_msg_123",
            "content": "Meeting started",
            "channel_id": "channel_555"
        }
        records = await pipeline._transform_discord_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "discord_message"
        assert record["id"] == "discord_msg_123"
        assert record["content"] == "Meeting started"
        assert record["channel_id"] == "channel_555"
        assert record["object_type"] == "message"

    @pytest.mark.asyncio
    async def test_teams_payload_transformation(self):
        """Verify Teams webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "id": "teams_msg_123",
            "text": "Task assigned to you",
            "from": {"name": "Rushi"}
        }
        records = await pipeline._transform_teams_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "teams_message"
        assert record["id"] == "teams_msg_123"
        assert record["text"] == "Task assigned to you"
        assert record["object_type"] == "message"

    @pytest.mark.asyncio
    async def test_telegram_payload_transformation(self):
        """Verify Telegram webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "update_id": 9999,
            "message": {
                "message_id": "tg_msg_123",
                "text": "Code review requested",
                "chat": {"id": "chat_888"}
            }
        }
        records = await pipeline._transform_telegram_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "telegram_message"
        assert record["id"] == "tg_msg_123"
        assert record["text"] == "Code review requested"
        assert record["chat_id"] == "chat_888"
        assert record["object_type"] == "message"

    @pytest.mark.asyncio
    async def test_twilio_payload_transformation(self):
        """Verify Twilio webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "MessageSid": "twilio_msg_123",
            "Body": "Production build ready!",
            "From": "+123456789",
            "To": "+987654321"
        }
        records = await pipeline._transform_twilio_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "twilio_sms"
        assert record["id"] == "twilio_msg_123"
        assert record["from"] == "+123456789"
        assert record["to"] == "+987654321"
        assert record["object_type"] == "message"
        assert record["properties"]["Body"] == "Production build ready!"

    @pytest.mark.asyncio
    async def test_intercom_payload_transformation(self):
        """Verify Intercom webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "topic": "conversation.user.created",
            "data": {
                "id": "intercom_conv_123",
                "conversation_message": {"subject": "Need help!"}
            }
        }
        records = await pipeline._transform_intercom_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "intercom_conversation"
        assert record["id"] == "intercom_conv_123"
        assert record["subject"] == "Need help!"
        assert record["object_type"] == "conversation"
        assert record["event_type"] == "conversation.user.created"

    def test_dev_prod_webhook_handshakes(self, client):
        """Verify handshake protocols for Dev & Productivity integrations."""
        # 1. Dropbox challenge handshake
        response = client.get("/api/webhooks/dev-prod/dropbox?challenge=drop_challenge_123")
        assert response.status_code == 200
        assert response.text == "drop_challenge_123"

        # 2. OneDrive validationToken challenge handshake
        response = client.get("/api/webhooks/dev-prod/onedrive?validationToken=onedrive_token_abc")
        assert response.status_code == 200
        assert response.text == "onedrive_token_abc"

        # 3. GitHub ping check event
        response = client.post(
            "/api/webhooks/dev-prod/github",
            json={"zen": "Practicality beats purity."},
            headers={"X-GitHub-Event": "ping"}
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "zen": "Practicality beats purity."}

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_dev_prod_webhook_routing_all(self, mock_enqueue, client, mock_db_setup):
        """Verify routing and tenant discovery for all 8 Dev & Productivity integrations."""
        dev_prod_services = [
            "github", "gitlab", "bitbucket", "google-drive", "dropbox", "box", "onedrive", "salesloft"
        ]

        # 1. Specific connector matching (e.g. GitHub with github_org_owner)
        mock_enqueue.return_value = "job_github_abc"
        payload_github = {
            "action": "opened",
            "organization": {"login": "github_org_owner"},
            "pull_request": {"number": 42, "title": "Add dev-prod webhooks", "state": "open"}
        }
        response = client.post(
            "/api/webhooks/dev-prod/github",
            json=payload_github
        )
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued", "job_id": "job_github_abc"}
        mock_enqueue.assert_called_once_with(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            integration_id="github",
            trigger_type="webhook",
            payload=payload_github,
            source_connection_id=None
        )

        # 2. Fallback matching (e.g. all other services using dev_prod base fallback mapping)
        for idx, service in enumerate(dev_prod_services):
            if service == "github":
                continue
            
            mock_enqueue.reset_mock()
            normalized_service = service.replace("-", "_")
            mock_enqueue.return_value = f"job_{normalized_service}_abc"

            # Create service-specific payload with the fallback workspace identifier
            if service == "gitlab":
                payload = {"project": {"path_with_namespace": "dev_prod_fallback_workspace"}}
            elif service == "bitbucket":
                payload = {"repository": {"workspace": {"uuid": "dev_prod_fallback_workspace"}}}
            elif service == "google-drive":
                payload = {"channelId": "dev_prod_fallback_workspace"}
            elif service == "dropbox":
                payload = {"accounts": ["dev_prod_fallback_workspace"]}
            elif service == "box":
                payload = {"enterprise": {"id": "dev_prod_fallback_workspace"}}
            elif service == "onedrive":
                payload = {"value": [{"clientState": "dev_prod_fallback_workspace"}]}
            else: # salesloft
                payload = {"tenant_id": "dev_prod_fallback_workspace"}

            response = client.post(
                f"/api/webhooks/dev-prod/{service}",
                json=payload
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "enqueued"
            assert data["job_id"] == f"job_{normalized_service}_abc"

            mock_enqueue.assert_called_once_with(
                tenant_id="11234567-89ab-cdef-0123-456789abcdef",
                integration_id=normalized_service,
                trigger_type="webhook",
                payload=payload,
                source_connection_id=None  # No UserConnection for other services in this test
            )

    @pytest.mark.asyncio
    async def test_github_payload_transformation(self):
        """Verify GitHub webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "action": "opened",
            "pull_request": {
                "number": 101,
                "title": "Clean codebase",
                "state": "open"
            }
        }
        records = await pipeline._transform_github_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "github_pull_request"
        assert record["id"] == "101"
        assert record["title"] == "Clean codebase"
        assert record["state"] == "open"
        assert record["object_type"] == "pull_request"

    @pytest.mark.asyncio
    async def test_gitlab_payload_transformation(self):
        """Verify GitLab webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "object_kind": "issue",
            "object_attributes": {
                "iid": 202,
                "title": "Database lag",
                "state": "opened",
                "action": "open"
            }
        }
        records = await pipeline._transform_gitlab_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "gitlab_issue"
        assert record["id"] == "202"
        assert record["title"] == "Database lag"
        assert record["state"] == "opened"
        assert record["object_type"] == "issue"

    @pytest.mark.asyncio
    async def test_bitbucket_payload_transformation(self):
        """Verify Bitbucket webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "pullrequest": {
                "id": 303,
                "title": "Fix OAuth validation",
                "state": "OPEN"
            },
            "action": "created"
        }
        records = await pipeline._transform_bitbucket_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "bitbucket_pull_request"
        assert record["id"] == "303"
        assert record["title"] == "Fix OAuth validation"
        assert record["state"] == "OPEN"
        assert record["object_type"] == "pull_request"

    @pytest.mark.asyncio
    async def test_google_drive_payload_transformation(self):
        """Verify Google Drive webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "file_id": "gd_file_123",
            "name": "Q2_Financials.xlsx",
            "action": "update"
        }
        records = await pipeline._transform_google_drive_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "google_drive_file"
        assert record["id"] == "gd_file_123"
        assert record["name"] == "Q2_Financials.xlsx"
        assert record["object_type"] == "file"
        assert record["event_type"] == "update"

    @pytest.mark.asyncio
    async def test_dropbox_payload_transformation(self):
        """Verify Dropbox webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "file_id": "drop_file_123",
            "name": "Design_Spec.pdf",
            "event_type": "file_added"
        }
        records = await pipeline._transform_dropbox_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "dropbox_file"
        assert record["id"] == "drop_file_123"
        assert record["name"] == "Design_Spec.pdf"
        assert record["object_type"] == "file"
        assert record["event_type"] == "file_added"

    @pytest.mark.asyncio
    async def test_box_payload_transformation(self):
        """Verify Box webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "file_id": "box_file_123",
            "file_name": "Logo_Final.png",
            "event_type": "FILE.UPLOADED"
        }
        records = await pipeline._transform_box_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "box_file"
        assert record["id"] == "box_file_123"
        assert record["name"] == "Logo_Final.png"
        assert record["object_type"] == "file"
        assert record["event_type"] == "FILE.UPLOADED"

    @pytest.mark.asyncio
    async def test_onedrive_payload_transformation(self):
        """Verify OneDrive webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "file_id": "one_file_123",
            "file_name": "Product_Backlog.xlsx",
            "action": "updated"
        }
        records = await pipeline._transform_onedrive_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "onedrive_file"
        assert record["id"] == "one_file_123"
        assert record["name"] == "Product_Backlog.xlsx"
        assert record["object_type"] == "file"
        assert record["event_type"] == "updated"

    @pytest.mark.asyncio
    async def test_salesloft_payload_transformation(self):
        """Verify Salesloft webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "event": {"action": "create"},
            "data": {
                "id": "salesloft_cadence_123",
                "name": "Outbound Prospecting"
            }
        }
        records = await pipeline._transform_salesloft_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "salesloft_cadence"
        assert record["id"] == "salesloft_cadence_123"
        assert record["name"] == "Outbound Prospecting"
        assert record["object_type"] == "cadence"
        assert record["event_type"] == "create"

    def test_ecommerce_marketing_webhook_handshakes(self, client):
        """Verify handshake protocols for E-commerce & Marketing integrations."""
        # 1. Mailchimp validation handshake (GET request)
        response = client.get("/api/webhooks/ecommerce-marketing/mailchimp")
        assert response.status_code == 200

        # 2. Zoom url_validation challenge handshake (POST request)
        response = client.post(
            "/api/webhooks/ecommerce-marketing/zoom",
            json={
                "event": "endpoint.url_validation",
                "payload": {"plainToken": "zoom_challenge_token_123"}
            }
        )
        assert response.status_code == 200
        assert response.json() == {
            "plainToken": "zoom_challenge_token_123",
            "encryptedToken": "zoom_challenge_token_123"
        }

        # 3. HEAD response check
        response = client.head("/api/webhooks/ecommerce-marketing/stripe")
        assert response.status_code == 200

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_ecommerce_marketing_webhook_routing_all(self, mock_enqueue, client, mock_db_setup):
        """Verify routing and tenant discovery for all 15 E-commerce & Marketing integrations."""
        ecom_marketing_services = [
            "shopify", "woocommerce", "bigcommerce", "magento", "stripe",
            "mailchimp", "activecampaign", "sendgrid", "convertkit", "getresponse",
            "airtable", "webex", "zoom", "freshdesk", "figma"
        ]

        # 1. Specific connector matching (e.g. Shopify with shopify_store_id)
        mock_enqueue.return_value = "job_shopify_abc"
        payload_shopify = {
            "id": 789,
            "domain": "shopify_store_id",
            "email": "customer@acme.com",
            "total_price": "299.99",
            "topic": "orders/create"
        }
        response = client.post(
            "/api/webhooks/ecommerce-marketing/shopify",
            json=payload_shopify
        )
        assert response.status_code == 200
        assert response.json() == {"status": "enqueued", "job_id": "job_shopify_abc"}
        mock_enqueue.assert_called_once_with(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            integration_id="shopify",
            trigger_type="webhook",
            payload=payload_shopify,
            source_connection_id=None
        )

        # 2. Fallback matching (e.g. all other services using ecommerce_marketing base fallback mapping)
        for idx, service in enumerate(ecom_marketing_services):
            if service == "shopify":
                continue
            
            mock_enqueue.reset_mock()
            normalized_service = service.replace("-", "_")
            mock_enqueue.return_value = f"job_{normalized_service}_abc"

            # Create service-specific payload with the fallback workspace identifier
            if service == "woocommerce":
                payload = {"store_url": "ecom_fallback_workspace"}
            elif service == "bigcommerce":
                payload = {"data": {"id": "123"}, "store_hash": "ecom_fallback_workspace"}
            elif service == "magento":
                payload = {"store_id": "ecom_fallback_workspace"}
            elif service == "stripe":
                payload = {"data": {"object": {"id": "ch_123"}}, "account": "ecom_fallback_workspace"}
            elif service == "mailchimp":
                payload = {"data": {"list_id": "ecom_fallback_workspace"}}
            elif service == "activecampaign":
                payload = {"account": "ecom_fallback_workspace"}
            elif service == "sendgrid":
                payload = [{"useragent": "ecom_fallback_workspace", "sg_message_id": "msg_123"}]
            elif service == "convertkit":
                payload = {"account_name": "ecom_fallback_workspace"}
            elif service == "getresponse":
                payload = {"contact": {"campaign_id": "ecom_fallback_workspace"}}
            elif service == "airtable":
                payload = {"base_id": "ecom_fallback_workspace"}
            elif service == "webex":
                payload = {"orgId": "ecom_fallback_workspace"}
            elif service == "zoom":
                payload = {"accountId": "ecom_fallback_workspace"}
            elif service == "freshdesk":
                payload = {"domain": "ecom_fallback_workspace"}
            else: # figma
                payload = {"team_id": "ecom_fallback_workspace"}

            response = client.post(
                f"/api/webhooks/ecommerce-marketing/{service}",
                json=payload
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "enqueued"
            assert data["job_id"] == f"job_{normalized_service}_abc"

            mock_enqueue.assert_called_once_with(
                tenant_id="11234567-89ab-cdef-0123-456789abcdef",
                integration_id=normalized_service,
                trigger_type="webhook",
                payload=payload,
                source_connection_id=None  # No UserConnection for other services in this test
            )

    @pytest.mark.asyncio
    async def test_shopify_payload_transformation(self):
        """Verify Shopify webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "id": "shop_order_123",
            "email": "buyer@example.com",
            "total_price": "150.00",
            "topic": "orders/create"
        }
        records = await pipeline._transform_shopify_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "shopify_orders_create"
        assert record["id"] == "shop_order_123"
        assert record["email"] == "buyer@example.com"
        assert record["total_price"] == "150.00"
        assert record["object_type"] == "order"

    @pytest.mark.asyncio
    async def test_woocommerce_payload_transformation(self):
        """Verify WooCommerce webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "id": "woo_order_123",
            "total": "99.50",
            "status": "processing",
            "action": "created"
        }
        records = await pipeline._transform_woocommerce_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "woocommerce_order"
        assert record["id"] == "woo_order_123"
        assert record["total"] == "99.50"
        assert record["status"] == "processing"
        assert record["object_type"] == "order"

    @pytest.mark.asyncio
    async def test_bigcommerce_payload_transformation(self):
        """Verify BigCommerce webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "scope": "store/order/created",
            "data": {
                "id": "bc_order_123",
                "total_tax_inc": "45.00"
            }
        }
        records = await pipeline._transform_bigcommerce_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "bigcommerce_order"
        assert record["id"] == "bc_order_123"
        assert record["total"] == "45.00"
        assert record["object_type"] == "order"

    @pytest.mark.asyncio
    async def test_magento_payload_transformation(self):
        """Verify Magento webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "entity_id": "mage_order_123",
            "grand_total": "125.00",
            "event_name": "sales_order_place_after"
        }
        records = await pipeline._transform_magento_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "magento_order"
        assert record["id"] == "mage_order_123"
        assert record["total"] == "125.00"
        assert record["object_type"] == "order"

    @pytest.mark.asyncio
    async def test_stripe_payload_transformation(self):
        """Verify Stripe webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "object": "charge",
                    "id": "ch_stripe_123",
                    "amount": 2500,
                    "currency": "usd"
                }
            }
        }
        records = await pipeline._transform_stripe_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "stripe_charge"
        assert record["id"] == "ch_stripe_123"
        assert record["amount"] == 2500
        assert record["currency"] == "usd"
        assert record["object_type"] == "charge"

    @pytest.mark.asyncio
    async def test_mailchimp_payload_transformation(self):
        """Verify Mailchimp webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "type": "subscribe",
            "data": {
                "id": "mc_sub_123",
                "email": "subscriber@domain.com"
            }
        }
        records = await pipeline._transform_mailchimp_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "mailchimp_subscribe"
        assert record["id"] == "mc_sub_123"
        assert record["email"] == "subscriber@domain.com"
        assert record["object_type"] == "subscribe"

    @pytest.mark.asyncio
    async def test_activecampaign_payload_transformation(self):
        """Verify ActiveCampaign webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "type": "subscribe",
            "contact": {
                "id": "ac_contact_123",
                "email": "contact@domain.com"
            }
        }
        records = await pipeline._transform_activecampaign_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "activecampaign_contact"
        assert record["id"] == "ac_contact_123"
        assert record["email"] == "contact@domain.com"
        assert record["object_type"] == "contact"

    @pytest.mark.asyncio
    async def test_sendgrid_payload_transformation(self):
        """Verify SendGrid webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = [{
            "sg_message_id": "sg_msg_123",
            "email": "recipient@domain.com",
            "event": "delivered"
        }]
        records = await pipeline._transform_sendgrid_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "sendgrid_email_event"
        assert record["id"] == "sg_msg_123"
        assert record["email"] == "recipient@domain.com"
        assert record["event_type"] == "delivered"
        assert record["object_type"] == "email_event"

    @pytest.mark.asyncio
    async def test_convertkit_payload_transformation(self):
        """Verify ConvertKit webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "event": {"name": "subscriber.activate"},
            "subscriber": {
                "id": "ck_sub_123",
                "email_address": "active@domain.com"
            }
        }
        records = await pipeline._transform_convertkit_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "convertkit_subscriber"
        assert record["id"] == "ck_sub_123"
        assert record["email"] == "active@domain.com"
        assert record["object_type"] == "subscriber"

    @pytest.mark.asyncio
    async def test_getresponse_payload_transformation(self):
        """Verify GetResponse webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "event": {"name": "subscribe"},
            "contact": {
                "contact_id": "gr_contact_123",
                "email": "gr@domain.com"
            }
        }
        records = await pipeline._transform_getresponse_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "getresponse_contact"
        assert record["id"] == "gr_contact_123"
        assert record["email"] == "gr@domain.com"
        assert record["object_type"] == "contact"
        assert record["event_type"] == "subscribe"

    @pytest.mark.asyncio
    async def test_airtable_payload_transformation(self):
        """Verify Airtable webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "record_id": "rec_airtable_123",
            "base_id": "base_abc",
            "table_id": "tbl_xyz",
            "action": "create"
        }
        records = await pipeline._transform_airtable_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "airtable_record"
        assert record["id"] == "rec_airtable_123"
        assert record["base_id"] == "base_abc"
        assert record["table_id"] == "tbl_xyz"
        assert record["object_type"] == "record"

    @pytest.mark.asyncio
    async def test_webex_payload_transformation(self):
        """Verify Webex webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "name": "messages.created",
            "data": {
                "id": "webex_msg_123",
                "text": "Hello Webex!",
                "personId": "user_webex_456"
            }
        }
        records = await pipeline._transform_webex_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "webex_message"
        assert record["id"] == "webex_msg_123"
        assert record["text"] == "Hello Webex!"
        assert record["person_id"] == "user_webex_456"
        assert record["object_type"] == "message"

    @pytest.mark.asyncio
    async def test_zoom_payload_transformation(self):
        """Verify Zoom webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "id": "zoom_meeting_123",
            "topic": "Strategy Alignment",
            "event": "meeting.created"
        }
        records = await pipeline._transform_zoom_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "zoom_meeting"
        assert record["id"] == "zoom_meeting_123"
        assert record["topic"] == "Strategy Alignment"
        assert record["object_type"] == "meeting"

    @pytest.mark.asyncio
    async def test_freshdesk_payload_transformation(self):
        """Verify Freshdesk webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "ticket_id": "fd_ticket_123",
            "subject": "Billing issue",
            "status": "Open",
            "trigger": "ticket_created"
        }
        records = await pipeline._transform_freshdesk_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "freshdesk_ticket"
        assert record["id"] == "fd_ticket_123"
        assert record["subject"] == "Billing issue"
        assert record["status"] == "Open"
        assert record["object_type"] == "ticket"

    @pytest.mark.asyncio
    async def test_figma_payload_transformation(self):
        """Verify Figma webhook payload transformation."""
        from core.ingestion_pipeline import IngestionPipelineService
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        webhook_data = {
            "file_key": "figma_key_123",
            "file_name": "Mobile Dashboard",
            "event_type": "FILE_COMMENT"
        }
        records = await pipeline._transform_figma_payload(webhook_data)
        assert len(records) == 1
        record = records[0]
        assert record["type"] == "figma_file"
        assert record["id"] == "figma_key_123"
        assert record["name"] == "Mobile Dashboard"
        assert record["object_type"] == "file"

    @pytest.mark.asyncio
    async def test_centralized_format_alignment_and_uuid_sanitization(self):
        """Verify centralized format alignment (Phase 3) and UUID serialization safety."""
        import uuid
        from core.ingestion_pipeline import IngestionPipelineService
        
        pipeline = IngestionPipelineService(
            tenant_id="11234567-89ab-cdef-0123-456789abcdef",
            workspace_id="w1234567-89ab-cdef-0123-456789abcdef"
        )
        
        # We will test using Shopify payload to confirm format alignment is applied
        webhook_data = {
            "id": 12345,  # Numeric ID should be converted to string
            "email": "buyer@example.com",
            "total_price": "150.00",
            "topic": "orders/create",
            "test_uuid": uuid.UUID("11234567-89ab-cdef-0123-456789abcdef")  # UUID should be stringified
        }
        
        records = await pipeline._transform_webhook_payload("shopify", webhook_data)
        assert len(records) == 1
        record = records[0]
        
        # Standardized fields must exist and match spec: {id, sender_id, subject, content, timestamp, metadata}
        assert record["id"] == "12345"  # Converted to string
        assert record["sender_id"] == "buyer@example.com"
        assert record["subject"] == "orders/create"
        assert record["content"] == ""
        assert isinstance(record["metadata"], dict)
        
        # Check UUID stringification / sanitization inside metadata to prevent JSON serialization errors
        metadata = record["metadata"]
        assert metadata["test_uuid"] == "11234567-89ab-cdef-0123-456789abcdef"
        assert isinstance(metadata["test_uuid"], str)


class TestScheduledWebhookRenewal:
    """TDD Verification Suite for Phase 4 subscription renewal at scale."""

    @pytest.mark.asyncio
    async def test_tier_categorization(self):
        """Verify that integrations are placed into the correct scheduling tier."""
        from core.webhook_renewal_service import ScheduledWebhookRenewalService
        from unittest.mock import MagicMock

        service = ScheduledWebhookRenewalService(db=MagicMock())

        # Tier 1 Critical: every 12h
        assert service.get_tier_for_integration("outlook") == "tier_1_critical"
        assert service.get_tier_for_integration("slack") == "tier_1_critical"

        # Tier 2 Business: every 24h
        assert service.get_tier_for_integration("github") == "tier_2_business"
        assert service.get_tier_for_integration("hubspot") == "tier_2_business"

        # Tier 3 Productivity: every 48h
        assert service.get_tier_for_integration("trello") == "tier_3_productivity"
        assert service.get_tier_for_integration("monday") == "tier_3_productivity"

        # Tier 4 Nice-to-have: every 7d
        assert service.get_tier_for_integration("shopify") == "tier_4_nice_to_have"
        assert service.get_tier_for_integration("freshdesk") == "tier_4_nice_to_have"

    @pytest.mark.asyncio
    async def test_renewal_boundary(self):
        """Verify is_renewal_due boundaries reflect proper staggered timing constraints."""
        from datetime import datetime, timezone, timedelta
        from core.webhook_renewal_service import ScheduledWebhookRenewalService
        from core.models import UserConnection
        from unittest.mock import MagicMock

        service = ScheduledWebhookRenewalService(db=MagicMock())
        now = datetime.now(timezone.utc)

        # Tier 1 Critical (12h limit)
        conn_t1 = UserConnection(
            integration_id="outlook", status="active", last_refresh_at=now - timedelta(hours=13)
        )
        assert service.is_renewal_due(conn_t1) is True

        conn_t1_recent = UserConnection(
            integration_id="outlook", status="active", last_refresh_at=now - timedelta(hours=10)
        )
        assert service.is_renewal_due(conn_t1_recent) is False

        # Tier 2 Business (24h limit)
        conn_t2 = UserConnection(
            integration_id="github", status="active", last_refresh_at=now - timedelta(hours=25)
        )
        assert service.is_renewal_due(conn_t2) is True

        conn_t2_recent = UserConnection(
            integration_id="github", status="active", last_refresh_at=now - timedelta(hours=20)
        )
        assert service.is_renewal_due(conn_t2_recent) is False

    @pytest.mark.asyncio
    async def test_consecutive_failures_alert(self):
        """Verify that 3 consecutive failures set the connection to error and emit a TrainingAlert."""
        from datetime import datetime, timezone
        from core.webhook_renewal_service import ScheduledWebhookRenewalService
        from core.models import UserConnection, TrainingAlert
        from unittest.mock import MagicMock

        db_mock = MagicMock()
        service = ScheduledWebhookRenewalService(db=db_mock)

        conn = UserConnection(
            id="c1234567-89ab-cdef-0123-456789abcdef",
            integration_id="outlook",
            status="active",
            tenant_id="t1234567-89ab-cdef-0123-456789abcdef",
            refresh_failure_count=0,
        )

        # Failure 1
        service._handle_failure(conn, "Timeout")
        assert conn.refresh_failure_count == 1
        assert conn.status == "active"

        # Failure 2
        service._handle_failure(conn, "Rate Limit")
        assert conn.refresh_failure_count == 2
        assert conn.status == "active"

        # Failure 3 -> should set to error and emit TrainingAlert
        service._handle_failure(conn, "Bad Gateway")
        assert conn.refresh_failure_count == 3
        assert conn.status == "error"

        # Verify db.add was called for TrainingAlert
        db_mock.add.assert_called_once()
        added_alert = db_mock.add.call_args[0][0]
        assert isinstance(added_alert, TrainingAlert)
        assert added_alert.alert_type == "WEBHOOK_RENEWAL_FAILURE"
        assert added_alert.severity == "critical"
        assert "Bad Gateway" in added_alert.description

    @pytest.mark.asyncio
    async def test_staggered_renewal_cycle(self):
        """Verify the full staggered renewal cycle behaves correctly on mixed due statuses."""
        from datetime import datetime, timezone, timedelta
        from core.webhook_renewal_service import ScheduledWebhookRenewalService
        from core.models import UserConnection
        from unittest.mock import AsyncMock, MagicMock

        db_mock = MagicMock()
        service = ScheduledWebhookRenewalService(db=db_mock)

        now = datetime.now(timezone.utc)

        # Connection 1: Due
        conn1 = UserConnection(
            integration_id="outlook", status="active", last_refresh_at=now - timedelta(hours=15)
        )
        # Connection 2: Not due
        conn2 = UserConnection(
            integration_id="github", status="active", last_refresh_at=now - timedelta(hours=5)
        )

        db_mock.query().filter().all.return_value = [conn1, conn2]

        # Mock actual renewal call
        service.renew_subscription_for_connection = AsyncMock(return_value={"status": "success"})

        results = await service.run_staggered_renewal_cycle()

        assert results["total_checked"] == 2
        assert results["skipped"] == 1
        assert results["renewed"] == 1
        service.renew_subscription_for_connection.assert_called_once_with(conn1)


class TestSelfServiceDashboard:
    """TDD Verification Suite for Phase 5 self-service webhook dashboard endpoints."""

    @pytest.mark.asyncio
    async def test_health_dashboard_endpoint(self):
        """Verify the health-dashboard endpoint returns correct connection statuses and aggregated summaries."""
        from api.routes.webhooks.monitoring import get_health_dashboard
        from core.models import UserConnection
        from unittest.mock import MagicMock
        from unittest import mock

        db_mock = MagicMock()

        # Seed two active connections
        conn1 = UserConnection(
            id="c1111111-2222-3333-4444-555555555555",
            user_id="raj-test-tenant-id",
            integration_id="outlook",
            connection_name="Outlook Primary",
            status="active",
            credentials="{}",
            last_refresh_error=None
        )
        conn2 = UserConnection(
            id="c2222222-3333-4444-5555-666666666666",
            user_id="raj-test-tenant-id",
            integration_id="slack",
            connection_name="Slack Main",
            status="error",
            credentials="{}",
            last_refresh_error="Rate Limit Exceeded"
        )

        db_mock.query().filter().all.return_value = [conn1, conn2]

        with mock.patch("core.connection_service.ConnectionService.get_connection_health_status") as mock_health:
            mock_health.side_effect = lambda cid, uid: {"health_status": "healthy" if cid == "c1111111-2222-3333-4444-555555555555" else "error"}

            response = await get_health_dashboard(tenant_id="raj-test-tenant-id", db=db_mock)

            assert response["tenant_id"] == "raj-test-tenant-id"
            summary = response["summary"]
            assert summary["total_connections"] == 2
            assert summary["healthy_connections"] == 1
            assert summary["error_connections"] == 1

            connections = response["connections"]
            assert len(connections) == 2
            assert connections[0]["connection_name"] == "Outlook Primary"
            assert connections[0]["health_status"] == "healthy"
            assert connections[1]["connection_name"] == "Slack Main"
            assert connections[1]["health_status"] == "error"

    @pytest.mark.asyncio
    async def test_manual_renewal_endpoint(self):
        """Verify that the manual renew endpoint correctly triggers connection subscription renewals."""
        from api.routes.webhooks.monitoring import manual_connection_renew
        from core.models import UserConnection
        from unittest.mock import AsyncMock, MagicMock
        from unittest import mock

        db_mock = MagicMock()
        conn = UserConnection(
            id="conn-renew-123",
            user_id="raj-test-tenant-id",
            integration_id="outlook",
            status="active",
            credentials="{}"
        )
        db_mock.query().filter().first.return_value = conn

        # Mock renewal service
        mock_outcome = {"status": "success"}
        with mock.patch("core.webhook_renewal_service.ScheduledWebhookRenewalService.renew_subscription_for_connection", new_callable=AsyncMock) as mock_renew:
            mock_renew.return_value = mock_outcome

            response = await manual_connection_renew(
                connection_id="conn-renew-123",
                tenant_id="raj-test-tenant-id",
                db=db_mock
            )

            assert response["status"] == "success"
            assert "Successfully renewed subscription" in response["message"]
            mock_renew.assert_called_once_with(conn)

    @pytest.mark.asyncio
    async def test_troubleshoot_diagnostics_endpoint(self):
        """Verify the troubleshoot endpoint performs diagnostics and returns copy-pasteable CLI commands."""
        from api.routes.webhooks.monitoring import troubleshoot_connection
        from core.models import UserConnection
        from unittest.mock import MagicMock

        db_mock = MagicMock()
        conn = UserConnection(
            id="conn-trouble-456",
            user_id="raj-test-tenant-id",
            integration_id="outlook",
            connection_name="Outlook Debug",
            status="active",
            credentials="{}"
        )
        db_mock.query().filter().first.return_value = conn

        response = await troubleshoot_connection(
            connection_id="conn-trouble-456",
            tenant_id="raj-test-tenant-id",
            db=db_mock
        )

        assert response["connection_id"] == "conn-trouble-456"
        assert response["integration_id"] == "outlook"

        diagnostics = response["diagnostics"]
        assert "overall_verdict" in diagnostics

        cli_tools = response["cli_troubleshooting_tools"]
        assert len(cli_tools) > 0
        assert cli_tools[0]["title"] == "Simulate Live Webhook Notification"
        assert "curl" in cli_tools[0]["command"]
        assert "conn-trouble-456" in cli_tools[0]["command"]


class TestRollbackAndResilience:
    """TDD Verification Suite for Phase 6 Webhook Rollback & Resilience."""

    @pytest.mark.asyncio
    async def test_webhook_feature_flag_disabled(self):
        """Verify that disabling a webhook via Feature Flag immediately ignores incoming events."""
        from api.routes.webhooks.webhook_bridge import webhook_bridge
        from unittest import mock

        db_mock = mock.MagicMock()
        registry_mock = mock.MagicMock()

        # Mock feature flag to return False
        with mock.patch("core.feature_flags.FeatureFlags.is_webhook_enabled", return_value=False) as mock_enabled:
            result = await webhook_bridge.process_event(
                platform="slack",
                tenant_id="test-tenant-123",
                data={"event": "test"},
                registry=registry_mock,
                db=db_mock
            )

            assert result["status"] == "ignored"
            assert result["reason"] == "webhook_feature_flag_disabled"
            mock_enabled.assert_called_once_with("slack")

    @pytest.mark.asyncio
    async def test_webhook_canary_rollout_cohorts(self):
        """Verify that fractional canary rollouts consistently include/exclude tenants."""
        from api.routes.webhooks.webhook_bridge import webhook_bridge
        from unittest import mock

        db_mock = mock.MagicMock()
        registry_mock = mock.MagicMock()

        # Mock FeatureFlags: enabled = True, canary = False for tenant A, True for tenant B
        with mock.patch("core.feature_flags.FeatureFlags.is_webhook_enabled", return_value=True), \
             mock.patch("core.feature_flags.FeatureFlags.is_webhook_canary_enabled") as mock_canary:
            
            # Scenario A: Tenant excluded from cohort
            mock_canary.return_value = False
            result_excluded = await webhook_bridge.process_event(
                platform="slack",
                tenant_id="tenant-excluded-456",
                data={"event": "test"},
                registry=registry_mock,
                db=db_mock
            )
            assert result_excluded["status"] == "ignored"
            assert result_excluded["reason"] == "webhook_canary_cohort_excluded"
            mock_canary.assert_called_with("slack", "tenant-excluded-456")

            # Scenario B: Tenant included (continues past canary check and fails on UCB/CB mock)
            mock_canary.return_value = True
            with mock.patch("core.circuit_breaker.circuit_breaker.is_enabled", return_value=False):
                result_included = await webhook_bridge.process_event(
                    platform="slack",
                    tenant_id="tenant-included-789",
                    data={"event": "test"},
                    registry=registry_mock,
                    db=db_mock
                )
                assert result_included["status"] == "ignored"
                assert result_included["reason"] == "circuit_breaker_open"

    @pytest.mark.asyncio
    async def test_webhook_ingestion_failure_records_circuit_breaker_error(self):
        """Verify that ingestion exceptions record failures on the circuit breaker."""
        from api.routes.webhooks.webhook_bridge import webhook_bridge
        from unittest import mock
        from unittest.mock import AsyncMock

        db_mock = mock.MagicMock()
        registry_mock = mock.MagicMock()
        
        # Mock active workspace lookup and message parsing
        mock_workspace = mock.MagicMock()
        mock_workspace.id = "ws-123"
        db_mock.query().filter().first.return_value = mock_workspace

        mock_msg = mock.MagicMock()
        mock_msg.content = "hello"
        mock_msg.sender_id = "user-123"
        mock_msg.metadata_json = {}

        ucb_mock_result = {"type": "message", "message": mock_msg}

        with mock.patch("core.feature_flags.FeatureFlags.is_webhook_enabled", return_value=True), \
             mock.patch("core.feature_flags.FeatureFlags.is_webhook_canary_enabled", return_value=True), \
             mock.patch("core.circuit_breaker.circuit_breaker.is_enabled", return_value=True), \
             mock.patch("core.universal_communication_bridge.UniversalCommunicationBridge.receive_message", new_callable=AsyncMock, return_value=ucb_mock_result), \
             mock.patch("core.ingestion_pipeline.IngestionPipelineService.process_webhook_payload_tiered", new_callable=AsyncMock, side_effect=ValueError("Ingestion crashed!")), \
             mock.patch("core.circuit_breaker.circuit_breaker.record_failure", new_callable=AsyncMock) as mock_record_failure:

            # Even if tiered ingestion fails, bridge absorbs it and continues command check / chat orchestrator
            # We mock orchestrator process_chat_message to return None so it doesn't fail
            mock_orch = mock.MagicMock()
            mock_orch.process_chat_message = AsyncMock(return_value=None)
            webhook_bridge._orchestrator = mock_orch

            result = await webhook_bridge.process_event(
                platform="slack",
                tenant_id="tenant-fail-999",
                data={"event": "crash"},
                registry=registry_mock,
                db=db_mock
            )

            # Assert failure recorded on circuit breaker
            mock_record_failure.assert_called_once()
            cb_key = mock_record_failure.call_args[0][0]
            assert cb_key == "slack:tenant-fail-999"
            assert "Ingestion crashed!" in str(mock_record_failure.call_args[1]["error"])

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_triggers_historical_sync_fallback(self):
        """Verify that when the circuit breaker trips open, it automatically triggers a fallback historical sync job."""
        from api.routes.webhooks.webhook_bridge import webhook_bridge
        from core.models import UserConnection
        from unittest import mock
        from unittest.mock import AsyncMock

        db_mock = mock.MagicMock()
        conn = UserConnection(
            id="conn-fallback-789",
            user_id="user-fallback-123",
            tenant_id="tenant-fallback-abc",
            integration_id="slack",
            status="active",
            credentials="{}"
        )
        db_mock.query().filter().first.return_value = conn

        # Mock SessionLocal and HistoricalSyncService
        mock_session_local = mock.MagicMock(return_value=db_mock)

        with mock.patch("core.database.SessionLocal", mock_session_local), \
             mock.patch("core.historical_sync_service.HistoricalSyncService.start_historical_sync", new_callable=AsyncMock) as mock_start_sync:

            mock_start_sync.return_value = "job-fallback-123"

            # Execute the callback directly on the bridge instance
            await webhook_bridge._on_circuit_open_fallback(
                service="slack:tenant-fallback-abc",
                stats={"last_error_message": "consecutive failures exceeded"}
            )

            # Verify historical sync service started with correct arguments
            mock_start_sync.assert_called_once()
            call_kwargs = mock_start_sync.call_args[1]
            assert call_kwargs["integration_id"] == "slack"
            assert call_kwargs["connection_id"] == "conn-fallback-789"
            assert call_kwargs["use_worker_queue"] is True
            assert "start_date" in call_kwargs
            assert "end_date" in call_kwargs

    @pytest.mark.asyncio
    async def test_webhook_ingestion_respects_connection_scope(self):
        """Verify webhook bridge partitions data based on connection scope (org vs personal)."""
        from unittest.mock import AsyncMock
        from unittest import mock
        from sqlalchemy.orm import Session
        # Create a mock DB session
        db_mock = mock.MagicMock(spec=Session)
        db_mock.bind = mock.MagicMock()
        db_mock.bind.dialect.name = "postgresql"

        # Mock Workspace query
        mock_workspace = mock.MagicMock()
        mock_workspace.id = "shared-workspace-uuid"

        # 1. Test ORG scoped connection
        mock_connection_org = mock.MagicMock()
        mock_connection_org.id = "conn-org-123"
        mock_connection_org.scope = "org"
        mock_connection_org.workspace_id = "some-other-workspace"

        # Set up DB query return values dynamically based on model parameter
        def mock_query_org(model):
            q = mock.MagicMock()
            if model.__name__ == "UserConnection":
                q.filter.return_value.order_by.return_value.first.return_value = mock_connection_org
            elif model.__name__ == "Workspace":
                q.filter.return_value.first.return_value = mock_workspace
            return q
        db_mock.query.side_effect = mock_query_org

        # Instantiate bridge and mock IngestionPipelineService
        from api.routes.webhooks.webhook_bridge import WebhookBridge
        webhook_bridge = WebhookBridge()
        
        with mock.patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService", autospec=True) as mock_ingestion_class, \
             mock.patch("api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge", autospec=True) as mock_ucb_class:
            
            mock_ingestion_instance = mock.MagicMock()
            mock_ingestion_instance.process_webhook_payload_tiered = AsyncMock(return_value={"success": True})
            mock_ingestion_class.return_value = mock_ingestion_instance

            mock_ucb_instance = mock.MagicMock()
            mock_ucb_instance.receive_message = AsyncMock(return_value={
                "type": "message", 
                "message": mock.MagicMock(content="hello", sender_id="user-123", metadata_json={})
            })
            mock_ucb_class.return_value = mock_ucb_instance

            await webhook_bridge.process_event(
                platform="slack",
                tenant_id="tenant-123",
                data={"event": "message"},
                registry=mock.MagicMock(),
                db=db_mock,
            )

            # Verify IngestionPipelineService was initialized with tenant's shared workspace ID
            mock_ingestion_class.assert_called_once()
            init_kwargs = mock_ingestion_class.call_args[1]
            assert init_kwargs["workspace_id"] == "shared-workspace-uuid"

        # 2. Test PERSONAL scoped connection
        mock_connection_personal = mock.MagicMock()
        mock_connection_personal.id = "conn-personal-456"
        mock_connection_personal.scope = "personal"
        mock_connection_personal.workspace_id = "personal-workspace-uuid"

        def mock_query_personal(model):
            q = mock.MagicMock()
            if model.__name__ == "UserConnection":
                q.filter.return_value.order_by.return_value.first.return_value = mock_connection_personal
            elif model.__name__ == "Workspace":
                q.filter.return_value.first.return_value = mock_workspace
            return q
        db_mock.query.side_effect = mock_query_personal

        with mock.patch("api.routes.webhooks.webhook_bridge.IngestionPipelineService", autospec=True) as mock_ingestion_class, \
             mock.patch("api.routes.webhooks.webhook_bridge.UniversalCommunicationBridge", autospec=True) as mock_ucb_class:
            
            mock_ingestion_instance = mock.MagicMock()
            mock_ingestion_instance.process_webhook_payload_tiered = AsyncMock(return_value={"success": True})
            mock_ingestion_class.return_value = mock_ingestion_instance

            mock_ucb_instance = mock.MagicMock()
            mock_ucb_instance.receive_message = AsyncMock(return_value={
                "type": "message", 
                "message": mock.MagicMock(content="hello", sender_id="user-123", metadata_json={})
            })
            mock_ucb_class.return_value = mock_ucb_instance

            await webhook_bridge.process_event(
                platform="slack",
                tenant_id="tenant-123",
                data={"event": "message"},
                registry=mock.MagicMock(),
                db=db_mock,
            )

            # Verify IngestionPipelineService was initialized with user's isolated personal workspace ID
            mock_ingestion_class.assert_called_once()
            init_kwargs = mock_ingestion_class.call_args[1]
            assert init_kwargs["workspace_id"] == "personal-workspace-uuid"

    @pytest.mark.asyncio
    async def test_microsoft365_create_subscription_change_type_expansion(self):
        """Verify that create_subscription automatically appends ',deleted' if 'created' is present and 'deleted' is not."""
        from integrations.microsoft365_service import Microsoft365Service
        from unittest import mock
        from unittest.mock import AsyncMock

        service_instance = Microsoft365Service(config={})
        with mock.patch.object(service_instance, "_make_graph_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"status": "success", "id": "sub_123"}
            
            # Scenario A: 'created' requested, 'deleted' not present -> should append ',deleted'
            await service_instance.create_subscription(
                token="token_123",
                resource="/me/mailFolders('Inbox')/messages",
                change_type="created",
                notification_url="https://example.com/webhook",
                expiration_datetime="2026-05-20T18:22:45Z"
            )
            mock_request.assert_called_once()
            payload = mock_request.call_args[0][3]
            assert payload["changeType"] == "created,deleted"
            
            # Scenario B: 'created,deleted' requested -> should not double-append
            mock_request.reset_mock()
            await service_instance.create_subscription(
                token="token_123",
                resource="/me/mailFolders('Inbox')/messages",
                change_type="created,deleted",
                notification_url="https://example.com/webhook",
                expiration_datetime="2026-05-20T18:22:45Z"
            )
            mock_request.assert_called_once()
            payload = mock_request.call_args[0][3]
            assert payload["changeType"] == "created,deleted"

            # Scenario C: 'updated' requested -> should remain 'updated'
            mock_request.reset_mock()
            await service_instance.create_subscription(
                token="token_123",
                resource="/me/events",
                change_type="updated",
                notification_url="https://example.com/webhook",
                expiration_datetime="2026-05-20T18:22:45Z"
            )
            mock_request.assert_called_once()
            payload = mock_request.call_args[0][3]
            assert payload["changeType"] == "updated"

    @pytest.mark.asyncio
    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    async def test_outlook_webhook_deletion_cascade(self, mock_enqueue, client, db_session):
        """Verify that an Outlook 'deleted' webhook event deletes the DiscoveredEntity records and skips queueing."""
        from core.models import Tenant, TenantIntegration, UserConnection, DiscoveredEntity
        from core.webhook_security import sign_client_state
        import json

        db_session.query(DiscoveredEntity).delete()
        db_session.query(TenantIntegration).delete()
        db_session.query(UserConnection).delete()
        db_session.query(Tenant).delete()
        db_session.commit()

        # Setup test Tenant
        tenant_id = "11234567-89ab-cdef-0123-456789abcdef"
        tenant = Tenant(id=tenant_id, subdomain="test-subdomain", name="Test Tenant")
        db_session.add(tenant)
        db_session.flush()

        # Setup Outlook integration config
        outlook_integration = TenantIntegration(
            tenant_id=tenant_id,
            connector_id="outlook",
            external_id="outlook_user_123",
            is_active=True,
            config={}
        )
        db_session.add(outlook_integration)

        # Setup Outlook UserConnection
        outlook_conn = UserConnection(
            id="c1234567-89ab-cdef-0123-456789abcdef",
            user_id="a1234567-89ab-cdef-0123-456789abcdef",
            tenant_id=tenant_id,
            workspace_id=tenant_id,
            integration_id="outlook",
            connection_name="Outlook Primary",
            credentials={"access_token": "token_abc"},
            status="active"
        )
        db_session.add(outlook_conn)
        db_session.flush()

        # Setup a DiscoveredEntity to be deleted
        target_message_id = "msg_abc123"
        entity = DiscoveredEntity(
            id="e1234567-89ab-cdef-0123-456789abcdef",
            tenant_id=tenant_id,
            workspace_id=tenant_id,
            source_record_id=target_message_id,
            source_record_type="outlook",
            _discovered_type="Email",
            properties={"subject": "Test Deletion"}
        )
        db_session.add(entity)
        db_session.commit()

        # Generate a valid signed clientState
        state_payload = {"c": str(outlook_conn.id)[:8]}
        signed_state = sign_client_state(json.dumps(state_payload))

        # Construct Outlook deleted event notification payload
        payload_dict = {
            "value": [
                {
                    "subscriptionId": "sub_123",
                    "clientState": signed_state,
                    "changeType": "deleted",
                    "resource": f"Users/outlook_user_123/Messages/{target_message_id}"
                }
            ]
        }
        body_bytes = json.dumps(payload_dict).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Host": "test-subdomain.localhost"
        }

        response = client.post("/api/webhooks/communication/outlook", content=body_bytes, headers=headers)
        assert response.status_code == 200
        
        # Verify DiscoveredEntity is deleted from database
        deleted_entity = db_session.query(DiscoveredEntity).filter(DiscoveredEntity.source_record_id == target_message_id).first()
        assert deleted_entity is None

        # Verify no ingestion job was enqueued
        mock_enqueue.assert_not_called()

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_tier2_discord_create_and_delete_cascade(self, mock_enqueue, client, db_session):
        tenant_id = "tenant_123"
        discord_conn = UserConnection(
            id="discord_conn_123",
            user_id="user_123",
            tenant_id=tenant_id,
            workspace_id=tenant_id,
            integration_id="discord",
            connection_name="Discord Connect",
            status="active"
        )
        db_session.add(discord_conn)
        
        from core.models import TenantIntegration
        integration = TenantIntegration(
            tenant_id=tenant_id,
            connector_id="discord",
            external_id="discord_server_123",
            is_active=True
        )
        db_session.add(integration)
        db_session.flush()

        target_msg_id = "discord_msg_456"
        entity = DiscoveredEntity(
            id="discord_entity_123",
            tenant_id=tenant_id,
            workspace_id=tenant_id,
            source_record_id=target_msg_id,
            source_record_type="discord",
            _discovered_type="Message",
            properties={"content": "Hello Discord!"}
        )
        db_session.add(entity)
        db_session.commit()

        # Send delete webhook
        payload_dict = {
            "event": "MESSAGE_DELETE",
            "id": target_msg_id
        }
        
        headers = {
            "Content-Type": "application/json",
            "Host": "test-subdomain.localhost"
        }
        
        response = client.post("/api/webhooks/communication/discord?tenant_id=tenant_123", json=payload_dict, headers=headers)
        assert response.status_code == 200
        
        # Verify DiscoveredEntity is deleted
        deleted_entity = db_session.query(DiscoveredEntity).filter(DiscoveredEntity.source_record_id == target_msg_id).first()
        assert deleted_entity is None
        mock_enqueue.assert_not_called()

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_tombstone_recording_on_delete(self, mock_enqueue, client, db_session):
        tenant_id = "tenant_123"
        from core.models import WebhookTombstone
        
        # Send delete webhook for non-existent resource
        payload_dict = {
            "event": "MESSAGE_DELETE",
            "id": "non_existent_msg"
        }
        
        headers = {
            "Content-Type": "application/json",
            "Host": "test-subdomain.localhost"
        }
        
        response = client.post("/api/webhooks/communication/discord?tenant_id=tenant_123", json=payload_dict, headers=headers)
        assert response.status_code == 200
        
        # Verify WebhookTombstone is recorded
        tombstone = db_session.query(WebhookTombstone).filter(
            WebhookTombstone.tenant_id == tenant_id,
            WebhookTombstone.integration_id == "discord",
            WebhookTombstone.source_record_id == "non_existent_msg"
        ).first()
        assert tombstone is not None
        mock_enqueue.assert_not_called()

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_tombstone_enforcement_on_create(self, mock_enqueue, client, db_session):
        tenant_id = "tenant_123"
        from core.models import WebhookTombstone
        
        # Write tombstone to DB
        tombstone = WebhookTombstone(
            tenant_id=tenant_id,
            integration_id="discord",
            source_record_id="tombstoned_msg"
        )
        db_session.add(tombstone)
        db_session.commit()

        # Send create webhook
        payload_dict = {
            "event": "MESSAGE_CREATE",
            "id": "tombstoned_msg",
            "content": "Should be ignored"
        }
        
        headers = {
            "Content-Type": "application/json",
            "Host": "test-subdomain.localhost"
        }
        
        response = client.post("/api/webhooks/communication/discord?tenant_id=tenant_123", json=payload_dict, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        assert response.json()["reason"] == "tombstoned"
        
        mock_enqueue.assert_not_called()

    @patch("api.routes.webhooks.ingestion_webhooks.webhook_queue.enqueue_ingestion_job")
    def test_tier1_slack_update_enqueuing(self, mock_enqueue, client, db_session):
        tenant_id = "tenant_123"
        slack_conn = UserConnection(
            id="slack_conn_123",
            user_id="user_123",
            tenant_id=tenant_id,
            workspace_id=tenant_id,
            integration_id="slack",
            connection_name="Slack Connect",
            status="active"
        )
        db_session.add(slack_conn)
        
        from core.models import TenantIntegration
        integration = TenantIntegration(
            tenant_id=tenant_id,
            connector_id="slack",
            external_id="team_123",
            is_active=True
        )
        db_session.add(integration)
        db_session.flush()
        db_session.commit()

        # Mock enqueue return value
        mock_enqueue.return_value = "job_999"

        # Send update webhook
        payload_dict = {
            "team_id": "team_123",
            "event": {
                "type": "message",
                "subtype": "message_changed",
                "message": {
                    "ts": "ts_123456",
                    "text": "Updated text"
                }
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Host": "test-subdomain.localhost"
        }
        
        response = client.post("/api/webhooks/slack/events", json=payload_dict, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "enqueued"
        assert response.json()["job_id"] == "job_999"
        
        mock_enqueue.assert_called_once()






