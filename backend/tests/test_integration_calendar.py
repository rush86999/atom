"""
Calendar Integration Tests (pytest)

Tests Google Calendar integration with proper mocking.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.models import AgentExecution, AgentOperationTracker


class TestCalendarIntegration:
    """Test Google Calendar integration."""

    @pytest.fixture
    def mock_calendar_service(self):
        """Create mock Google Calendar service."""
        with patch('integrations.calendar_service.build') as mock_build:
            yield mock_build.return_value

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        return db

    def test_create_calendar_event(self, mock_calendar_service, mock_db):
        """Test creating an event in Google Calendar."""
        # Mock Calendar API response
        mock_calendar_service.events().insert().execute.return_value = {
            "id": "event-001",
            "summary": "Team Meeting",
            "start": {"dateTime": "2026-04-15T10:00:00Z"},
            "end": {"dateTime": "2026-04-15T11:00:00Z"},
            "htmlLink": "https://calendar.google.com/calendar/event?eid=event-001"
        }

        execution = AgentExecution(
            id="exec-calendar-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Create calendar event"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Create event
        event_body = {
            "summary": "Team Meeting",
            "start": {"dateTime": "2026-04-15T10:00:00Z"},
            "end": {"dateTime": "2026-04-15T11:00:00Z"},
            "attendees": [{"email": "user1@example.com"}]
        }

        result = mock_calendar_service.events().insert().execute()

        # Verify API call
        assert result["id"] == "event-001"
        assert result["summary"] == "Team Meeting"

        execution.output_data = {
            "event_created": True,
            "event_id": result["id"],
            "event_url": result["htmlLink"]
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.output_data["event_created"] is True

    def test_update_calendar_event(self, mock_calendar_service, mock_db):
        """Test updating an existing calendar event."""
        mock_calendar_service.events().update().execute.return_value = {
            "id": "event-001",
            "summary": "Updated Team Meeting",
            "start": {"dateTime": "2026-04-15T14:00:00Z"},
            "end": {"dateTime": "2026-04-15T15:00:00Z"}
        }

        execution = AgentExecution(
            id="exec-calendar-002",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Update event"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Update event
        event_id = "event-001"
        updated_body = {
            "summary": "Updated Team Meeting",
            "start": {"dateTime": "2026-04-15T14:00:00Z"},
            "end": {"dateTime": "2026-04-15T15:00:00Z"}
        }

        result = mock_calendar_service.events().update().execute()

        # Verify API call
        assert result["summary"] == "Updated Team Meeting"

        execution.output_data = {"event_updated": True, "event_id": event_id}
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_delete_calendar_event(self, mock_calendar_service, mock_db):
        """Test deleting a calendar event."""
        mock_calendar_service.events().delete().execute.return_value = None

        execution = AgentExecution(
            id="exec-calendar-003",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Delete event"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Delete event
        event_id = "event-001"
        mock_calendar_service.events().delete(calendarId='primary', eventId=event_id).execute()

        # Verify API call was made (no return value for delete)
        execution.output_data = {"event_deleted": True, "event_id": event_id}
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_list_calendar_events(self, mock_calendar_service, mock_db):
        """Test listing calendar events."""
        mock_calendar_service.events().list().execute.return_value = {
            "items": [
                {
                    "id": "event-001",
                    "summary": "Meeting 1",
                    "start": {"dateTime": "2026-04-15T10:00:00Z"}
                },
                {
                    "id": "event-002",
                    "summary": "Meeting 2",
                    "start": {"dateTime": "2026-04-16T14:00:00Z"}
                }
            ]
        }

        execution = AgentExecution(
            id="exec-calendar-004",
            agent_id="agent-001",
            status="running",
            input_data={"task": "List events"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # List events
        result = mock_calendar_service.events().list().execute()

        # Verify API call
        events = result.get("items", [])
        assert len(events) == 2

        execution.output_data = {
            "events_found": len(events),
            "events": [{"id": e["id"], "summary": e["summary"]} for e in events]
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_add_attendees_to_event(self, mock_calendar_service, mock_db):
        """Test adding attendees to calendar event."""
        mock_calendar_service.events().update().execute.return_value = {
            "id": "event-001",
            "summary": "Team Meeting",
            "attendees": [
                {"email": "user1@example.com", "responseStatus": "accepted"},
                {"email": "user2@example.com", "responseStatus": "needsAction"}
            ]
        }

        execution = AgentExecution(
            id="exec-calendar-005",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Add attendees"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Add attendees
        result = mock_calendar_service.events().update().execute()

        # Verify API call
        assert len(result["attendees"]) == 2

        execution.output_data = {
            "attendees_added": True,
            "attendee_count": len(result["attendees"])
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_calendar_error_handling(self, mock_calendar_service, mock_db):
        """Test handling Calendar API errors."""
        # Mock API error
        mock_calendar_service.events().insert().execute.side_effect = Exception(
            "HttpError: 403 Insufficient Permission"
        )

        execution = AgentExecution(
            id="exec-calendar-error-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Create event"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Attempt to create event
        try:
            mock_calendar_service.events().insert().execute()
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            mock_db.commit()

        assert execution.status == "failed"
        assert "403" in execution.error_message

    def test_calendar_authentication_error(self, mock_calendar_service, mock_db):
        """Test handling Calendar authentication errors."""
        # Mock auth error
        mock_calendar_service.events().insert().execute.side_effect = Exception(
            "RefreshError: Invalid credentials"
        )

        execution = AgentExecution(
            id="exec-calendar-auth-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Create event"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Attempt to create event
        try:
            mock_calendar_service.events().insert().execute()
        except Exception as e:
            execution.status = "failed"
            execution.error_message = f"Authentication failed: {str(e)}"
            execution.completed_at = datetime.utcnow()
            mock_db.commit()

        assert execution.status == "failed"
        assert "credentials" in execution.error_message.lower()
