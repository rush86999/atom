"""
Comprehensive Test Suite for Enhanced Outlook Integration
Complete testing for Microsoft Graph API integration with the ATOM platform
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from outlook_routes_enhanced import router
from outlook_service_enhanced import (
    OutlookEnhancedService,
    OutlookEmail,
    OutlookCalendarEvent,
    OutlookContact,
    OutlookTask,
    OutlookFolder,
    EmailImportance,
    EventSensitivity,
    TaskStatus,
)


class TestOutlookIntegrationEnhanced:
    """Comprehensive test suite for enhanced Outlook integration"""

    @pytest.fixture
    def mock_outlook_service(self):
        """Mock Outlook service for testing"""
        with patch("outlook_routes_enhanced.outlook_service") as mock_service:
            # Mock service methods
            mock_service.get_user_emails_enhanced = AsyncMock(
                return_value=[
                    OutlookEmail(
                        id="email1",
                        conversation_id="conv1",
                        subject="Test Email",
                        body_preview="This is a test email",
                        body={"content": "Test content", "contentType": "HTML"},
                        importance="normal",
                        has_attachments=False,
                        is_read=True,
                        is_draft=False,
                        web_link="https://outlook.com/email1",
                        created_datetime="2024-01-10T10:00:00Z",
                        last_modified_datetime="2024-01-10T10:00:00Z",
                        received_datetime="2024-01-10T10:00:00Z",
                        sent_datetime="2024-01-10T09:55:00Z",
                        from_address={
                            "emailAddress": {"address": "sender@example.com"}
                        },
                        to_recipients=[
                            {"emailAddress": {"address": "recipient@example.com"}}
                        ],
                        cc_recipients=[],
                        bcc_recipients=[],
                        reply_to=[],
                        categories=[],
                        flag={},
                        internet_message_headers=[],
                        attachments=[],
                        metadata={
                            "accessed_at": "2024-01-10T10:00:00Z",
                            "source": "microsoft_graph",
                        },
                    )
                ]
            )

            mock_service.send_email_enhanced = AsyncMock(return_value=True)

            mock_service.create_calendar_event_enhanced = AsyncMock(
                return_value=OutlookCalendarEvent(
                    id="event1",
                    subject="Team Meeting",
                    body_preview="Weekly team sync",
                    body={"content": "Weekly team sync meeting", "contentType": "HTML"},
                    start={"dateTime": "2024-01-15T10:00:00Z", "timeZone": "UTC"},
                    end={"dateTime": "2024-01-15T11:00:00Z", "timeZone": "UTC"},
                    location={"displayName": "Conference Room A"},
                    locations=[{"displayName": "Conference Room A"}],
                    attendees=[{"emailAddress": {"address": "attendee@example.com"}}],
                    organizer={"emailAddress": {"address": "organizer@example.com"}},
                    is_all_day=False,
                    is_cancelled=False,
                    is_organizer=True,
                    response_requested=True,
                    response_status={
                        "response": "accepted",
                        "time": "2024-01-10T10:00:00Z",
                    },
                    sensitivity="normal",
                    show_as="busy",
                    type="singleInstance",
                    web_link="https://outlook.com/event1",
                    online_meeting={},
                    recurrence={},
                    reminder_minutes_before_start=15,
                    categories=[],
                    extensions=[],
                    metadata={
                        "created_at": "2024-01-10T10:00:00Z",
                        "source": "microsoft_graph",
                    },
                )
            )

            mock_service.create_contact_enhanced = AsyncMock(
                return_value=OutlookContact(
                    id="contact1",
                    display_name="John Doe",
                    given_name="John",
                    surname="Doe",
                    job_title="Software Engineer",
                    department="Engineering",
                    company_name="Tech Corp",
                    business_phones=["+1-555-0100"],
                    mobile_phone="+1-555-0101",
                    home_phones=[],
                    email_addresses=[
                        {"address": "john.doe@example.com", "name": "John Doe"}
                    ],
                    im_addresses=[],
                    home_address={},
                    business_address={},
                    other_address={},
                    personal_notes="Key contact for project",
                    birthday="1980-01-01",
                    anniversary="2010-06-15",
                    spouse_name="Jane Doe",
                    children=["Child1", "Child2"],
                    manager="Manager Name",
                    assistant_name="Assistant Name",
                    profession="Software Development",
                    categories=["Work"],
                    created_date_time="2024-01-10T10:00:00Z",
                    last_modified_date_time="2024-01-10T10:00:00Z",
                    metadata={
                        "created_at": "2024-01-10T10:00:00Z",
                        "source": "microsoft_graph",
                    },
                )
            )

            mock_service.create_task_enhanced = AsyncMock(
                return_value=OutlookTask(
                    id="task1",
                    subject="Complete project documentation",
                    body={"content": "Finish API documentation", "contentType": "HTML"},
                    importance="high",
                    status="notStarted",
                    completed_date_time={},
                    due_date_time={
                        "dateTime": "2024-01-20T17:00:00Z",
                        "timeZone": "UTC",
                    },
                    start_date_time={
                        "dateTime": "2024-01-15T09:00:00Z",
                        "timeZone": "UTC",
                    },
                    created_date_time="2024-01-10T10:00:00Z",
                    last_modified_date_time="2024-01-10T10:00:00Z",
                    is_reminder_on=True,
                    reminder_date_time={
                        "dateTime": "2024-01-20T16:00:00Z",
                        "timeZone": "UTC",
                    },
                    categories=["Work", "Documentation"],
                    assigned_to="john.doe@example.com",
                    parent_folder_id="folder1",
                    conversation_id="conv1",
                    conversation_index="index1",
                    flag={},
                    metadata={
                        "created_at": "2024-01-10T10:00:00Z",
                        "source": "microsoft_graph",
                    },
                )
            )

            mock_service.get_user_folders = AsyncMock(
                return_value=[
                    OutlookFolder(
                        id="folder1",
                        display_name="Inbox",
                        parent_folder_id="",
                        child_folder_count=3,
                        unread_item_count=5,
                        total_item_count=150,
                        folder_type="inbox",
                        is_hidden=False,
                        well_known_name="inbox",
                        metadata={
                            "accessed_at": "2024-01-10T10:00:00Z",
                            "source": "microsoft_graph",
                        },
                    ),
                    OutlookFolder(
                        id="folder2",
                        display_name="Sent Items",
                        parent_folder_id="",
                        child_folder_count=0,
                        unread_item_count=0,
                        total_item_count=89,
                        folder_type="sentitems",
                        is_hidden=False,
                        well_known_name="sentitems",
                        metadata={
                            "accessed_at": "2024-01-10T10:00:00Z",
                            "source": "microsoft_graph",
                        },
                    ),
                ]
            )

            mock_service.search_entities_enhanced = AsyncMock(
                return_value=[
                    {
                        "id": "result1",
                        "entityType": "message",
                        "subject": "Search Result Email",
                        "webLink": "https://outlook.com/result1",
                        "score": 0.85,
                    },
                    {
                        "id": "result2",
                        "entityType": "event",
                        "subject": "Search Result Event",
                        "webLink": "https://outlook.com/result2",
                        "score": 0.72,
                    },
                ]
            )

            mock_service.get_user_profile_enhanced = AsyncMock(
                return_value=OutlookUser(
                    id="user1",
                    display_name="Test User",
                    email="test.user@example.com",
                    job_title="Software Engineer",
                    department="Engineering",
                    office_location="Seattle",
                    mobile_phone="+1-555-0100",
                    business_phones=["+1-555-0101"],
                    user_principal_name="test.user@example.com",
                    mail="test.user@example.com",
                    account_enabled=True,
                    user_type="Member",
                    preferred_language="en-US",
                    timezone="Pacific Standard Time",
                    usage_location="US",
                    metadata={
                        "accessed_at": "2024-01-10T10:00:00Z",
                        "source": "microsoft_graph",
                    },
                )
            )

            mock_service.get_upcoming_events = AsyncMock(
                return_value=[
                    OutlookCalendarEvent(
                        id="upcoming1",
                        subject="Upcoming Meeting",
                        body_preview="Team sync",
                        body={
                            "content": "Upcoming team meeting",
                            "contentType": "HTML",
                        },
                        start={"dateTime": "2024-01-12T14:00:00Z", "timeZone": "UTC"},
                        end={"dateTime": "2024-01-12T15:00:00Z", "timeZone": "UTC"},
                        location={"displayName": "Virtual"},
                        locations=[{"displayName": "Virtual"}],
                        attendees=[],
                        organizer={
                            "emailAddress": {"address": "organizer@example.com"}
                        },
                        is_all_day=False,
                        is_cancelled=False,
                        is_organizer=True,
                        response_requested=False,
                        response_status={},
                        sensitivity="normal",
                        show_as="busy",
                        type="singleInstance",
                        web_link="https://outlook.com/upcoming1",
                        online_meeting={},
                        recurrence={},
                        reminder_minutes_before_start=15,
                        categories=[],
                        extensions=[],
                        metadata={
                            "created_at": "2024-01-10T10:00:00Z",
                            "source": "microsoft_graph",
                        },
                    )
                ]
            )

            mock_service.get_unread_email_count = AsyncMock(return_value=5)

            mock_service.mark_emails_read = AsyncMock(return_value=True)

            yield mock_service

    def test_health_endpoint_enhanced(self, mock_outlook_service):
        """Test enhanced health endpoint"""
        import asyncio

        async def test_health():
            from outlook_routes_enhanced import outlook_health_enhanced

            result = await outlook_health_enhanced()
            assert result["status"] == "healthy"
            assert result["service"] == "outlook"
            assert result["service_available"] == True
            assert result["database_available"] == True
            assert "timestamp" in result

        asyncio.run(test_health())

    def test_get_emails_enhanced_logic(self, mock_outlook_service):
        """Test enhanced get emails endpoint logic"""
        import asyncio

        async def test_emails():
            from outlook_routes_enhanced import get_emails_enhanced
            from outlook_routes_enhanced import EmailListEnhancedRequest

            request = EmailListEnhancedRequest(
                user_id="test-user-123",
                folder="inbox",
                query="subject:test",
                max_results=10,
                skip=0,
                include_attachments=True,
                order_by="receivedDateTime DESC",
            )

            result = await get_emails_enhanced(request)
            assert result["ok"] == True
            assert "emails" in result["data"]
            assert len(result["data"]["emails"]) == 1
            assert result["data"]["emails"][0]["subject"] == "Test Email"
            assert result["data"]["user_id"] == "test-user-123"

        asyncio.run(test_emails())

    def test_send_email_enhanced_logic(self, mock_outlook_service):
        """Test enhanced send email endpoint logic"""
        import asyncio

        async def test_send_email():
            from outlook_routes_enhanced import send_email_enhanced
            from outlook_routes_enhanced import EmailSendEnhancedRequest

            request = EmailSendEnhancedRequest(
                user_id="test-user-123",
                to_recipients=["recipient@example.com"],
                subject="Test Email",
                body="This is a test email",
                body_type="HTML",
                cc_recipients=["cc@example.com"],
                bcc_recipients=["bcc@example.com"],
                importance="high",
                attachments=[],
                save_to_sent_items=True,
            )

            result = await send_email_enhanced(request)
            assert result["ok"] == True
            assert result["data"]["message"] == "Email sent successfully"
            assert result["data"]["subject"] == "Test Email"

        asyncio.run(test_send_email())

    def test_create_calendar_event_enhanced_logic(self, mock_outlook_service):
        """Test enhanced create calendar event endpoint logic"""
        import asyncio

        async def test_create_event():
            from outlook_routes_enhanced import create_calendar_event_enhanced
            from outlook_routes_enhanced import CalendarEventEnhancedRequest

            request = CalendarEventEnhancedRequest(
                user_id="test-user-123",
                subject="Team Meeting",
                start_time="2024-01-15T10:00:00Z",
                end_time="2024-01-15T11:00:00Z",
                location="Conference Room A",
                body="Weekly team sync meeting",
                attendees=["attendee1@example.com", "attendee2@example.com"],
                is_all_day=False,
                sensitivity="normal",
                show_as="busy",
                reminder_minutes=15,
            )

            result = await create_calendar_event_enhanced(request)
            assert result["ok"] == True
            assert "event" in result["data"]
            assert result["data"]["event"]["subject"] == "Team Meeting"
            assert result["data"]["message"] == "Calendar event created successfully"

        asyncio.run(test_create_event())

    def test_create_contact_enhanced_logic(self, mock_outlook_service):
        """Test enhanced create contact endpoint logic"""
        import asyncio

        async def test_create_contact():
            from outlook_routes_enhanced import create_contact_enhanced
            from outlook_routes_enhanced import ContactEnhancedRequest

            request = ContactEnhancedRequest(
                user_id="test-user-123",
                display_name="John Doe",
                given_name="John",
                surname="Doe",
                email_addresses=["john.doe@example.com"],
                business_phones=["+1-555-0100"],
                mobile_phone="+1-555-0101",
                job_title="Software Engineer",
                company_name="Tech Corp",
            )

            result = await create_contact_enhanced(request)
            assert result["ok"] == True
            assert "contact" in result["data"]
            assert result["data"]["contact"]["display_name"] == "John Doe"
            assert result["data"]["message"] == "Contact created successfully"

        asyncio.run(test_create_contact())

    def test_create_task_enhanced_logic(self, mock_outlook_service):
        """Test enhanced create task endpoint logic"""
        import asyncio

        async def test_create_task():
            from outlook_routes_enhanced import create_task_enhanced
            from outlook_routes_enhanced import TaskEnhancedRequest

            request = TaskEnhancedRequest(
                user_id="test-user-123",
                subject="Complete project documentation",
                body="Finish API documentation for the project",
                importance="high",
                due_date="2024-01-20T17:00:00Z",
                start_date="2024-01-15T09:00:00Z",
                reminder_date="2024-01-20T16:00:00Z",
                categories=["Work", "Documentation"],
            )

            result = await create_task_enhanced(request)
            assert result["ok"] == True
            assert "task" in result["data"]
            assert result["data"]["task"]["subject"] == "Complete project documentation"
            assert result["data"]["message"] == "Task created successfully"

        asyncio.run(test_create_task())

    def test_get_folders_logic(self, mock_outlook_service):
        """Test get folders endpoint logic"""
        import asyncio

        async def test_folders():
            from outlook_routes_enhanced import get_folders
            from outlook_routes_enhanced import FolderListRequest

            request = FolderListRequest(user_id="test-user-123", folder_type="inbox")

            result = await get_folders(request)
            assert result["ok"] == True
            assert "folders" in result["data"]
            assert len(result["data"]["folders"]) == 2
            assert result["data"]["folders"][0]["display_name"] == "Inbox"

        asyncio.run(test_folders())

    def test_search_enhanced_logic(self, mock_outlook_service):
        """Test enhanced search endpoint logic"""
        import asyncio

        async def test_search():
            from outlook_routes_enhanced import search_enhanced
            from outlook_routes_enhanced import SearchEnhancedRequest

            request = SearchEnhancedRequest(
                user_id="test-user-123",
                query="project update",
                entity_types=["message", "event", "contact"],
                max_results=20,
            )

            result = await search_enhanced(request)
            assert result["ok"] == True
            assert "results" in result["data"]
            assert len(result["data"]["results"]) == 2
            assert result["data"]["query"] == "project update"

        asyncio.run(test_search())

    def test_get_user_profile_enhanced_logic(self, mock_outlook_service):
        """Test enhanced user profile endpoint logic"""
        import asyncio

        async def test_profile():
            from outlook_routes_enhanced import get_user_profile_enhanced

            result = await get_user_profile_enhanced(user_id="test-user-123")
            assert result["ok"] == True
            assert "profile" in result["data"]
            assert result["data"]["profile"]["display_name"] == "Test User"
            assert result["data"]["user_id"] == "test-user-123"

        asyncio.run(test_profile())

    def test_get_upcoming_events_logic(self, mock_outlook_service):
        """Test get upcoming events endpoint logic"""
        import asyncio

        async def test_upcoming_events():
            from outlook_routes_enhanced import get_upcoming_events

            result = await get_up
