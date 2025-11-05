import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from outlook_service import (
    OutlookService,
    OutlookEmail,
    OutlookCalendarEvent,
    OutlookContact,
    OutlookTask,
)


class TestOutlookIntegration:
    """Comprehensive test suite for Outlook integration"""

    def setup_method(self):
        """Setup test fixtures"""
        self.service = OutlookService()
        self.user_id = "test_user_123"
        self.mock_access_token = "mock_access_token_123"

    @pytest.fixture
    def mock_email_data(self):
        """Mock email data for testing"""
        return {
            "id": "email_123",
            "subject": "Test Email",
            "bodyPreview": "This is a test email preview",
            "body": {"contentType": "HTML", "content": "<p>Test email content</p>"},
            "sender": {
                "emailAddress": {"address": "sender@test.com", "name": "Test Sender"}
            },
            "from": {
                "emailAddress": {"address": "sender@test.com", "name": "Test Sender"}
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "recipient@test.com",
                        "name": "Test Recipient",
                    }
                }
            ],
            "receivedDateTime": "2024-01-15T10:00:00Z",
            "sentDateTime": "2024-01-15T09:55:00Z",
            "hasAttachments": False,
            "importance": "normal",
            "isRead": False,
            "webLink": "https://outlook.com/email/123",
            "conversationId": "conv_123",
            "parentFolderId": "folder_123",
        }

    @pytest.fixture
    def mock_calendar_event_data(self):
        """Mock calendar event data for testing"""
        return {
            "id": "event_123",
            "subject": "Team Meeting",
            "body": {"contentType": "HTML", "content": "<p>Weekly team sync</p>"},
            "start": {"dateTime": "2024-01-15T10:00:00Z", "timeZone": "UTC"},
            "end": {"dateTime": "2024-01-15T11:00:00Z", "timeZone": "UTC"},
            "location": {"displayName": "Conference Room A"},
            "attendees": [
                {
                    "emailAddress": {
                        "address": "attendee@test.com",
                        "name": "Test Attendee",
                    }
                }
            ],
            "organizer": {
                "emailAddress": {
                    "address": "organizer@test.com",
                    "name": "Test Organizer",
                }
            },
            "isAllDay": False,
            "showAs": "busy",
            "webLink": "https://outlook.com/event/123",
            "createdDateTime": "2024-01-14T09:00:00Z",
            "lastModifiedDateTime": "2024-01-14T09:30:00Z",
        }

    @pytest.fixture
    def mock_contact_data(self):
        """Mock contact data for testing"""
        return {
            "id": "contact_123",
            "displayName": "John Doe",
            "givenName": "John",
            "surname": "Doe",
            "emailAddresses": [{"address": "john.doe@test.com", "name": "John Doe"}],
            "businessPhones": ["+1-555-0100"],
            "mobilePhone": "+1-555-0101",
            "companyName": "Test Company",
            "jobTitle": "Software Engineer",
            "officeLocation": "Office 101",
            "createdDateTime": "2024-01-01T00:00:00Z",
            "lastModifiedDateTime": "2024-01-01T00:00:00Z",
        }

    @pytest.fixture
    def mock_task_data(self):
        """Mock task data for testing"""
        return {
            "id": "task_123",
            "subject": "Complete project documentation",
            "body": {
                "contentType": "text",
                "content": "Need to finish the project docs",
            },
            "importance": "high",
            "status": "notStarted",
            "createdDateTime": "2024-01-15T09:00:00Z",
            "lastModifiedDateTime": "2024-01-15T09:30:00Z",
            "dueDateTime": {"dateTime": "2024-01-20T17:00:00Z", "timeZone": "UTC"},
            "categories": ["Work", "Documentation"],
        }

    @pytest.mark.asyncio
    async def test_get_user_emails_success(self, mock_email_data):
        """Test successful email retrieval"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"value": [mock_email_data]}

            emails = await self.service.get_user_emails(self.user_id, "inbox")

            assert len(emails) == 1
            assert emails[0]["id"] == "email_123"
            assert emails[0]["subject"] == "Test Email"
            assert emails[0]["is_read"] is False
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_emails_with_query(self, mock_email_data):
        """Test email retrieval with search query"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"value": [mock_email_data]}

            emails = await self.service.get_user_emails(
                self.user_id, "inbox", query="test", max_results=25
            )

            assert len(emails) == 1
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_emails_empty(self):
        """Test email retrieval with no emails"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"value": []}

            emails = await self.service.get_user_emails(self.user_id, "inbox")

            assert len(emails) == 0
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """Test successful email sending"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"id": "sent_email_123", "status": "sent"}

            result = await self.service.send_email(
                self.user_id,
                to_recipients=["recipient@test.com"],
                subject="Test Subject",
                body="Test body content",
            )

            assert result is not None
            assert result["id"] == "sent_email_123"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_draft_email_success(self):
        """Test successful draft email creation"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"id": "draft_123", "subject": "Draft Email"}

            result = await self.service.create_draft_email(
                self.user_id,
                to_recipients=["recipient@test.com"],
                subject="Draft Subject",
                body="Draft body content",
            )

            assert result is not None
            assert result["id"] == "draft_123"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_email_by_id_success(self, mock_email_data):
        """Test successful email retrieval by ID"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = mock_email_data

            email = await self.service.get_email_by_id(self.user_id, "email_123")

            assert email is not None
            assert email["id"] == "email_123"
            assert email["subject"] == "Test Email"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_email_by_id_not_found(self):
        """Test email retrieval with non-existent ID"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = None

            email = await self.service.get_email_by_id(self.user_id, "nonexistent_id")

            assert email is None
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_email_success(self):
        """Test successful email deletion"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"success": True}

            result = await self.service.delete_email(self.user_id, "email_123")

            assert result is True
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_calendar_events_success(self, mock_calendar_event_data):
        """Test successful calendar events retrieval"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"value": [mock_calendar_event_data]}

            events = await self.service.get_calendar_events(
                self.user_id,
                time_min="2024-01-15T00:00:00Z",
                time_max="2024-01-15T23:59:59Z",
            )

            assert len(events) == 1
            assert events[0]["id"] == "event_123"
            assert events[0]["subject"] == "Team Meeting"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_calendar_event_success(self):
        """Test successful calendar event creation"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {
                "id": "new_event_123",
                "subject": "New Meeting",
            }

            result = await self.service.create_calendar_event(
                self.user_id,
                subject="New Meeting",
                body="Meeting description",
                start={"dateTime": "2024-01-16T10:00:00Z", "timeZone": "UTC"},
                end={"dateTime": "2024-01-16T11:00:00Z", "timeZone": "UTC"},
                attendees=["attendee@test.com"],
            )

            assert result is not None
            assert result["id"] == "new_event_123"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_contacts_success(self, mock_contact_data):
        """Test successful contacts retrieval"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"value": [mock_contact_data]}

            contacts = await self.service.get_user_contacts(self.user_id, query="John")

            assert len(contacts) == 1
            assert contacts[0]["id"] == "contact_123"
            assert contacts[0]["display_name"] == "John Doe"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_contact_success(self):
        """Test successful contact creation"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {
                "id": "new_contact_123",
                "displayName": "Jane Smith",
            }

            result = await self.service.create_contact(
                self.user_id,
                display_name="Jane Smith",
                given_name="Jane",
                surname="Smith",
                email_addresses=[
                    {"address": "jane.smith@test.com", "name": "Jane Smith"}
                ],
            )

            assert result is not None
            assert result["id"] == "new_contact_123"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_tasks_success(self, mock_task_data):
        """Test successful tasks retrieval"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"value": [mock_task_data]}

            tasks = await self.service.get_user_tasks(self.user_id, status="notStarted")

            assert len(tasks) == 1
            assert tasks[0]["id"] == "task_123"
            assert tasks[0]["subject"] == "Complete project documentation"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_task_success(self):
        """Test successful task creation"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"id": "new_task_123", "subject": "New Task"}

            result = await self.service.create_task(
                self.user_id,
                subject="New Task",
                body="Task description",
                importance="high",
                categories=["Work", "Urgent"],
            )

            assert result is not None
            assert result["id"] == "new_task_123"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_profile_success(self):
        """Test successful user profile retrieval"""
        mock_profile_data = {
            "id": "user_123",
            "displayName": "Test User",
            "mail": "test.user@test.com",
            "userPrincipalName": "test.user@test.com",
            "jobTitle": "Developer",
            "officeLocation": "Remote",
            "businessPhones": ["+1-555-0100"],
            "mobilePhone": "+1-555-0101",
        }

        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = mock_profile_data

            profile = await self.service.get_user_profile(self.user_id)

            assert profile is not None
            assert profile["id"] == "user_123"
            assert profile["display_name"] == "Test User"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_unread_emails_success(self, mock_email_data):
        """Test successful unread emails retrieval"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"value": [mock_email_data]}

            emails = await self.service.get_unread_emails(self.user_id)

            assert len(emails) == 1
            assert emails[0]["is_read"] is False
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_emails_success(self, mock_email_data):
        """Test successful email search"""
        with patch.object(self.service, "_make_graph_request") as mock_request:
            mock_request.return_value = {"value": [mock_email_data]}

            emails = await self.service.search_emails(self.user_id, query="test")

            assert len(emails) == 1
            assert emails[0]["subject"] == "Test Email"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_graph_request_no_token(self):
        """Test graph request with no access token"""
        with patch.object(self.service, "_get_access_token") as mock_token:
            mock_token.return_value = None

            result = await self.service._make_graph_request(self.user_id, "/me")

            assert result is None
            mock_token.assert_called_once_with(self.user_id)

    @pytest.mark.asyncio
    async def test_make_graph_request_api_error(self):
        """Test graph request with API error"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch("aiohttp.ClientSession") as mock_session,
        ):
            mock_token.return_value = self.mock_access_token
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text.return_value = "Internal Server Error"
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await self.service._make_graph_request(self.user_id, "/me")

            assert result is None

    def test_outlook_email_dataclass(self):
        """Test OutlookEmail dataclass functionality"""
        email = OutlookEmail(
            id="test_id",
            subject="Test Subject",
            body_preview="Test preview",
            sender={"name": "Test Sender"},
            is_read=False,
        )

        assert email.id == "test_id"
        assert email.subject == "Test Subject"
        assert email.body_preview == "Test preview"
        assert email.is_read is False

    def test_outlook_calendar_event_dataclass(self):
        """Test OutlookCalendarEvent dataclass functionality"""
        event = OutlookCalendarEvent(
            id="test_id",
            subject="Test Event",
            start={"dateTime": "2024-01-15T10:00:00Z"},
            end={"dateTime": "2024-01-15T11:00:00Z"},
            is_all_day=False,
        )

        assert event.id == "test_id"
        assert event.subject == "Test Event"
        assert event.is_all_day is False

    def test_outlook_contact_dataclass(self):
        """Test OutlookContact dataclass functionality"""
        contact = OutlookContact(
            id="test_id",
            display_name="Test Contact",
            email_addresses=[{"address": "test@test.com"}],
            company_name="Test Company",
        )

        assert contact.id == "test_id"
        assert contact.display_name == "Test Contact"
        assert contact.company_name == "Test Company"

    def test_outlook_task_dataclass(self):
        """Test OutlookTask dataclass functionality"""
        task = OutlookTask(
            id="test_id",
            subject="Test Task",
            importance="high",
            status="notStarted",
            categories=["Work"],
        )

        assert task.id == "test_id"
        assert task.subject == "Test Task"
        assert task.importance == "high"
        assert task.status == "notStarted"


# Note: FastAPI route tests would be implemented separately
# The service layer tests above provide comprehensive coverage
# of all Outlook integration functionality
