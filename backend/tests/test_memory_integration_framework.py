"""
Test Memory Integration Framework

Tests the generic memory integration framework that wires integrations
to entity extraction, embedding generation, and LanceDB storage.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from core.memory_integration_mixin import (
    MemoryIntegrationMixin,
    BackfillJob,
    IntegrationBackfillManager
)
from core.integration_entity_extractor import IntegrationEntityExtractor


class TestMemoryIntegrationMixin:
    """Test the MemoryIntegrationMixin base class"""

    @pytest.fixture
    def mixin(self):
        """Create a test mixin instance"""
        class TestIntegration(MemoryIntegrationMixin):
            async def fetch_records(self, start_date=None, end_date=None, limit=500):
                # Mock email data
                return [
                    {
                        "id": "email_001",
                        "type": "email",
                        "subject": "Test Email",
                        "from": "sender@example.com",
                        "to": ["recipient@example.com"],
                        "date": "2026-04-26T10:00:00Z",
                        "body": "This is a test email body"
                    }
                ]

            def get_integration_type(self):
                return "email"

        return TestIntegration(integration_id="test")

    def test_init(self, mixin):
        """Test mixin initialization"""
        assert mixin.integration_id == "test"
        assert mixin.workspace_id == "default"
        assert mixin.embedding_service is not None
        assert mixin.entity_extractor is not None

    def test_get_integration_type_email(self, mixin):
        """Test integration type detection for email"""
        mixin.integration_id = "outlook"
        assert mixin.get_integration_type() == "email"

        mixin.integration_id = "gmail"
        assert mixin.get_integration_type() == "email"

    def test_get_integration_type_crm(self):
        """Test integration type detection for CRM"""
        # Create separate instances for each test
        class SalesforceIntegration(MemoryIntegrationMixin):
            async def fetch_records(self, start_date=None, end_date=None, limit=500):
                return []
        sf_integration = SalesforceIntegration(integration_id="salesforce")
        assert sf_integration.get_integration_type() == "crm"

        class HubSpotIntegration(MemoryIntegrationMixin):
            async def fetch_records(self, start_date=None, end_date=None, limit=500):
                return []
        hubspot_integration = HubSpotIntegration(integration_id="hubspot")
        assert hubspot_integration.get_integration_type() == "crm"

    def test_get_integration_type_communication(self):
        """Test integration type detection for communication"""
        # Create separate instances for each test
        class SlackIntegration(MemoryIntegrationMixin):
            async def fetch_records(self, start_date=None, end_date=None, limit=500):
                return []
        slack_integration = SlackIntegration(integration_id="slack")
        assert slack_integration.get_integration_type() == "communication"

        class TeamsIntegration(MemoryIntegrationMixin):
            async def fetch_records(self, start_date=None, end_date=None, limit=500):
                return []
        teams_integration = TeamsIntegration(integration_id="teams")
        assert teams_integration.get_integration_type() == "communication"

    def test_get_job_status(self):
        """Test job status tracking"""
        # Create a job
        job = BackfillJob("test_job", "outlook")
        job.status = "running"
        job.progress = 50

        # Mock the global job registry
        from core.memory_integration_mixin import _backfill_jobs
        _backfill_jobs["test_job"] = job

        # Get status
        status = MemoryIntegrationMixin.get_job_status("test_job")

        assert status is not None
        assert status["job_id"] == "test_job"
        assert status["status"] == "running"
        assert status["progress"] == 50

        # Clean up
        del _backfill_jobs["test_job"]


class TestIntegrationEntityExtractor:
    """Test the IntegrationEntityExtractor"""

    @pytest.fixture
    def extractor(self):
        return IntegrationEntityExtractor()

    def test_extract_email_entities(self, extractor):
        """Test email entity extraction"""
        record = {
            "id": "email_001",
            "subject": "Meeting Tomorrow",
            "from": "john@example.com",
            "to": ["jane@example.com", "bob@example.com"],
            "cc": ["cc@example.com"],
            "body": "Let's discuss the project tomorrow at 2pm.",
            "date": "2026-04-26T10:00:00Z"
        }

        entity = extractor._extract_email_entities(record)

        assert entity is not None
        assert entity["id"] == "email_email_001"
        assert "Meeting Tomorrow" in entity["text"]
        assert entity["metadata"]["subject"] == "Meeting Tomorrow"
        assert entity["metadata"]["from"] == "john@example.com"
        assert len(entity["metadata"]["to"]) == 2
        assert "person" in entity["metadata"]["entity_types"]
        assert "organization" in entity["metadata"]["entity_types"]

    def test_extract_crm_entities_lead(self, extractor):
        """Test CRM lead entity extraction"""
        record = {
            "id": "lead_001",
            "object": "lead",
            "name": "John Doe",
            "email": "john@example.com",
            "company": "Acme Corp",
            "title": "CEO"
        }

        entity = extractor._extract_crm_entities(record)

        assert entity is not None
        assert entity["id"] == "lead_lead_001"
        assert "John Doe" in entity["text"]
        assert entity["metadata"]["name"] == "John Doe"
        assert entity["metadata"]["company"] == "Acme Corp"

    def test_extract_communication_entities(self, extractor):
        """Test communication entity extraction"""
        record = {
            "id": "msg_001",
            "text": "@john Hey, can you review the PR? https://github.com/example/repo/pull/123",
            "channel": "general",
            "user": "alice",
            "ts": "1612345678.123456"
        }

        entity = extractor._extract_communication_entities(record)

        assert entity is not None
        assert entity["id"] == "message_msg_001"
        assert entity["metadata"]["channel"] == "general"
        assert entity["metadata"]["user"] == "alice"
        assert "john" in entity["metadata"]["mentions"]
        assert len(entity["metadata"]["urls"]) > 0

    def test_extract_project_entities_task(self, extractor):
        """Test project task entity extraction"""
        record = {
            "id": "TASK-001",
            "type": "issue",
            "summary": "Fix login bug",
            "description": "Users cannot login with SSO",
            "status": "Open",
            "assignee": "John Doe",
            "priority": "High",
            "project": "Authentication"
        }

        entity = extractor._extract_project_entities(record)

        assert entity is not None
        assert entity["id"] == "task_TASK-001"
        assert "Fix login bug" in entity["text"]
        assert entity["metadata"]["title"] == "Fix login bug"
        assert entity["metadata"]["status"] == "Open"
        assert entity["metadata"]["assignee"] == "John Doe"

    def test_extract_support_entities(self, extractor):
        """Test support ticket entity extraction"""
        record = {
            "id": "ticket_001",
            "subject": "Cannot access dashboard",
            "description": "Getting 403 error when accessing dashboard",
            "status": "Open",
            "priority": "Urgent",
            "requester": "jane@example.com",
            "assignee": "support@example.com"
        }

        entity = extractor._extract_support_entities(record)

        assert entity is not None
        assert entity["id"] == "ticket_ticket_001"
        assert "Cannot access dashboard" in entity["text"]
        assert entity["metadata"]["status"] == "Open"
        assert entity["metadata"]["priority"] == "Urgent"

    def test_extract_calendar_entities(self, extractor):
        """Test calendar event entity extraction"""
        record = {
            "id": "event_001",
            "summary": "Team Standup",
            "description": "Daily standup meeting",
            "start": {"dateTime": "2026-04-27T09:00:00Z"},
            "end": {"dateTime": "2026-04-27T09:30:00Z"},
            "attendees": [
                {"email": "john@example.com", "displayName": "John Doe"},
                {"email": "jane@example.com", "displayName": "Jane Doe"}
            ]
        }

        entity = extractor._extract_calendar_entities(record)

        assert entity is not None
        assert entity["id"] == "event_event_001"
        assert "Team Standup" in entity["text"]
        assert entity["metadata"]["title"] == "Team Standup"
        assert len(entity["metadata"]["attendees"]) == 2

    def test_extract_email_addresses(self, extractor):
        """Test email address extraction"""
        data = [
            "john@example.com",
            "Email: jane@example.com",
            "bob@test.com and alice@test.com"
        ]

        emails = extractor._extract_email_addresses(data)

        assert len(emails) == 4
        assert "john@example.com" in emails
        assert "jane@example.com" in emails

    def test_extract_domains(self, extractor):
        """Test domain extraction from emails"""
        emails = [
            "john@example.com",
            "jane@test.com",
            "bob@example.com"
        ]

        domains = extractor._extract_domains(emails)

        assert len(domains) == 2
        assert "example.com" in domains
        assert "test.com" in domains


class TestBackfillJob:
    """Test BackfillJob tracker"""

    def test_backfill_job_init(self):
        """Test job initialization"""
        job = BackfillJob("job_123", "outlook")

        assert job.job_id == "job_123"
        assert job.integration_id == "outlook"
        assert job.status == "pending"
        assert job.progress == 0
        assert job.total_records == 0
        assert job.processed_records == 0

    def test_backfill_job_to_dict(self):
        """Test job serialization"""
        job = BackfillJob("job_123", "outlook")
        job.status = "running"
        job.progress = 50
        job.total_records = 100
        job.processed_records = 45
        job.started_at = datetime(2026, 4, 26, 10, 0, 0)

        result = job.to_dict()

        assert result["job_id"] == "job_123"
        assert result["status"] == "running"
        assert result["progress"] == 50
        assert result["total_records"] == 100
        assert result["processed_records"] == 45
        assert "started_at" in result


class TestIntegrationBackfillManager:
    """Test IntegrationBackfillManager"""

    @pytest.mark.asyncio
    async def test_trigger_backfill_unsupported_integration(self):
        """Test triggering backfill for unsupported integration"""
        result = await IntegrationBackfillManager.trigger_backfill(
            integration_id="unsupported_integration"
        )

        assert result["success"] is False
        assert "not found or not supported" in result["error"]

    def test_get_job_status_nonexistent(self):
        """Test getting status of non-existent job"""
        status = MemoryIntegrationMixin.get_job_status("nonexistent_job")
        assert status is None
