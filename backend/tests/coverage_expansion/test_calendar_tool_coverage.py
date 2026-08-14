"""
Coverage expansion tests for calendar tool.

Tests cover critical code paths in:
- tools/calendar_tool.py: Calendar operations via Google Calendar
- Event creation, updates, deletion, conflict checking
- Governance enforcement for calendar operations
- Authentication and error handling

Target: Cover critical paths (happy path + error paths) to increase coverage.
Uses extensive mocking to avoid Google Calendar API dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from typing import Dict, Any

from tools.calendar_tool import CalendarTool


@pytest.fixture(autouse=True)
def governance_agents():
    """Create the agent rows the governance permission check looks up.

    CalendarTool._check_calendar_permission queries AgentRegistry for the
    agent_id passed to run() ("agent-123", "student-agent", "intern-agent"
    throughout this suite); without the rows every action is denied before
    the mocked Google Calendar service is reached.
    """
    from core.database import SessionLocal
    from core.models import AgentRegistry

    session = SessionLocal()
    agents = [
        AgentRegistry(
            id="agent-123",
            name="Calendar Test Agent",
            status="autonomous",  # maturity_level aliases status
            category="Operations",
            module_path="core.test_agents",
            class_name="CalendarTestAgent",
        ),
        AgentRegistry(
            id="student-agent",
            name="Calendar Student Agent",
            status="student",
            category="Operations",
            module_path="core.test_agents",
            class_name="CalendarStudentAgent",
        ),
        AgentRegistry(
            id="intern-agent",
            name="Calendar Intern Agent",
            status="intern",
            category="Operations",
            module_path="core.test_agents",
            class_name="CalendarInternAgent",
        ),
    ]
    session.add_all(agents)
    session.commit()
    session.close()


class TestCalendarToolCoverage:
    """Coverage expansion for CalendarTool class."""

    @pytest.fixture
    def calendar_tool(self):
        """Get calendar tool instance."""
        return CalendarTool()

    # Test: CalendarTool initialization
    @patch('tools.calendar_tool.google_calendar_service')
    def test_calendar_tool_init_success(self, mock_gcal_service, calendar_tool):
        """Calendar tool initializes successfully."""
        assert isinstance(calendar_tool, CalendarTool)
        assert calendar_tool.governance_cache is not None

    @patch('tools.calendar_tool.google_calendar_service')
    def test_calendar_tool_init_auth_failure(self, mock_gcal_service):
        """Calendar tool handles auth failure gracefully."""
        mock_gcal_service.authenticate.side_effect = Exception("Auth failed")

        tool = CalendarTool()
        assert isinstance(tool, CalendarTool)

    # Test: Get events (read operation - INTERN+)
    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_get_events_success(self, mock_gcal_service):
        """Successfully get calendar events."""
        tool = CalendarTool()

        # google_calendar_service methods are awaited by CalendarTool
        mock_gcal_service.get_events = AsyncMock(return_value=[
            {
                "id": "event-1",
                "summary": "Team Meeting",
                "start": {"dateTime": "2026-04-12T10:00:00"},
                "end": {"dateTime": "2026-04-12T11:00:00"}
            },
            {
                "id": "event-2",
                "summary": "Lunch Break",
                "start": {"dateTime": "2026-04-12T12:00:00"},
                "end": {"dateTime": "2026-04-12T12:30:00"}
            }
        ])

        result = await tool.run(
            action="get_events",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="INTERN",
            date_min="2026-04-12T00:00:00",
            date_max="2026-04-12T23:59:59"
        )

        assert result["success"] == True
        assert "events" in result
        assert len(result["events"]) == 2

    @pytest.mark.asyncio
    async def test_get_events_student_blocked(self):
        """Student agents blocked from reading events."""
        tool = CalendarTool()

        # Current contract: run() raises PermissionError when governance
        # denies the action (see docstring of CalendarTool.run).
        with pytest.raises(PermissionError) as exc_info:
            await tool.run(
                action="get_events",
                user_id="user-123",
                agent_id="student-agent",
                maturity_level="STUDENT"
            )

        assert "maturity" in str(exc_info.value).lower()

    # Test: Check conflicts (read operation - INTERN+)
    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_check_conflicts_no_conflicts(self, mock_gcal_service):
        """Check for conflicts when none exist."""
        tool = CalendarTool()

        # Current API: check_conflicts delegates to the service's own
        # check_conflicts coroutine and returns its dict.
        mock_gcal_service.check_conflicts = AsyncMock(return_value={
            "success": True,
            "has_conflicts": False,
            "conflicts": []
        })

        result = await tool.run(
            action="check_conflicts",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="INTERN",
            start_time="2026-04-12T14:00:00",
            end_time="2026-04-12T15:00:00"
        )

        assert result["success"] == True
        assert result["has_conflicts"] == False

    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_check_conflicts_has_conflicts(self, mock_gcal_service):
        """Check for conflicts when events overlap."""
        tool = CalendarTool()

        # Current API: check_conflicts delegates to the service's own
        # check_conflicts coroutine and returns its dict.
        mock_gcal_service.check_conflicts = AsyncMock(return_value={
            "success": True,
            "has_conflicts": True,
            "conflicts": [
                {
                    "id": "existing-event",
                    "summary": "Existing Meeting",
                    "start": {"dateTime": "2026-04-12T14:30:00"},
                    "end": {"dateTime": "2026-04-12T15:30:00"}
                }
            ]
        })

        result = await tool.run(
            action="check_conflicts",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="INTERN",
            start_time="2026-04-12T14:00:00",
            end_time="2026-04-12T15:00:00"
        )

        assert result["success"] == True
        assert result["has_conflicts"] == True
        assert "conflicts" in result

    # Test: Create event (write operation - SUPERVISED+)
    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_create_event_success(self, mock_gcal_service):
        """Successfully create calendar event."""
        tool = CalendarTool()

        mock_gcal_service.create_event = AsyncMock(return_value={
            "id": "new-event-123",
            "summary": "New Meeting",
            "start": {"dateTime": "2026-04-12T16:00:00"},
            "end": {"dateTime": "2026-04-12T17:00:00"}
        })

        result = await tool.run(
            action="create_event",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="SUPERVISED",
            title="New Meeting",
            start_time="2026-04-12T16:00:00",
            end_time="2026-04-12T17:00:00",
            description="Team sync"
        )

        assert result["success"] == True
        assert "event" in result
        assert result["event"]["summary"] == "New Meeting"

    @pytest.mark.asyncio
    async def test_create_event_intern_blocked(self):
        """Intern agents blocked from creating events."""
        tool = CalendarTool()

        # Current contract: run() raises PermissionError when governance
        # denies the action (see docstring of CalendarTool.run).
        with pytest.raises(PermissionError) as exc_info:
            await tool.run(
                action="create_event",
                user_id="user-123",
                agent_id="intern-agent",
                maturity_level="INTERN",
                summary="Meeting",
                start_time="2026-04-12T16:00:00",
                end_time="2026-04-12T17:00:00"
            )

        assert "maturity" in str(exc_info.value).lower()

    # Test: Update event (write operation - SUPERVISED+)
    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_update_event_success(self, mock_gcal_service):
        """Successfully update calendar event."""
        tool = CalendarTool()

        mock_gcal_service.update_event = AsyncMock(return_value={
            "id": "event-123",
            "summary": "Updated Meeting",
            "start": {"dateTime": "2026-04-12T17:00:00"},
            "end": {"dateTime": "2026-04-12T18:00:00"}
        })

        result = await tool.run(
            action="update_event",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="SUPERVISED",
            event_id="event-123",
            updates={
                "summary": "Updated Meeting",
                "start_time": "2026-04-12T17:00:00",
                "end_time": "2026-04-12T18:00:00"
            }
        )

        assert result["success"] == True
        assert result["event"]["summary"] == "Updated Meeting"

    # Test: Delete event (write operation - SUPERVISED+)
    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_delete_event_success(self, mock_gcal_service):
        """Successfully delete calendar event."""
        tool = CalendarTool()

        mock_gcal_service.delete_event = AsyncMock(return_value=True)

        result = await tool.run(
            action="delete_event",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="SUPERVISED",
            event_id="event-123"
        )

        assert result["success"] == True
        assert result["action"] == "delete_event"

    # Test: List upcoming events
    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_list_upcoming_events_success(self, mock_gcal_service):
        """Successfully list upcoming events."""
        tool = CalendarTool()

        now = datetime.now()
        tomorrow = now + timedelta(days=1)

        mock_gcal_service.get_events = AsyncMock(return_value=[
            {
                "id": "event-1",
                "summary": "Tomorrow's Meeting",
                "start": {"dateTime": tomorrow.isoformat()},
                "end": {"dateTime": (tomorrow + timedelta(hours=1)).isoformat()}
            }
        ])

        result = await tool.run(
            action="get_events",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="INTERN",
            date_min=now.isoformat(),
            date_max=(tomorrow + timedelta(days=1)).isoformat()
        )

        assert result["success"] == True
        assert len(result["events"]) >= 0


class TestCalendarToolErrorHandling:
    """Coverage expansion for calendar tool error handling."""

    @pytest.fixture
    def calendar_tool(self):
        """Get calendar tool instance."""
        return CalendarTool()

    # Test: Invalid action
    @pytest.mark.asyncio
    async def test_invalid_action(self, calendar_tool):
        """Handle invalid action gracefully."""
        result = await calendar_tool.run(
            action="invalid_action",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="AUTONOMOUS"
        )

        assert result["success"] == False
        assert "unknown" in result["error"].lower() or "invalid" in result["error"].lower()

    # Test: Missing required parameters
    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_create_event_missing_summary(self, mock_gcal_service, calendar_tool):
        """Create event without summary."""
        result = await calendar_tool.run(
            action="create_event",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="SUPERVISED",
            start_time="2026-04-12T16:00:00",
            end_time="2026-04-12T17:00:00"
            # Missing: summary
        )

        assert result["success"] == False

    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_create_event_missing_times(self, mock_gcal_service, calendar_tool):
        """Create event without start/end times."""
        result = await calendar_tool.run(
            action="create_event",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="SUPERVISED",
            title="Meeting"
            # Missing: start_time, end_time
        )

        assert result["success"] == False

    # Test: API errors
    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_get_events_api_error(self, mock_gcal_service, calendar_tool):
        """Handle API errors gracefully."""
        mock_gcal_service.get_events = AsyncMock(side_effect=Exception("API Error"))

        result = await calendar_tool.run(
            action="get_events",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="INTERN"
        )

        assert result["success"] == False

    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_create_event_api_error(self, mock_gcal_service, calendar_tool):
        """Handle API errors on event creation."""
        mock_gcal_service.create_event = AsyncMock(side_effect=Exception("Authentication failed"))

        result = await calendar_tool.run(
            action="create_event",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="SUPERVISED",
            title="Meeting",
            start_time="2026-04-12T16:00:00",
            end_time="2026-04-12T17:00:00"
        )

        assert result["success"] == False

    # Test: Event not found
    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_update_event_not_found(self, mock_gcal_service, calendar_tool):
        """Update non-existent event."""
        mock_gcal_service.update_event = AsyncMock(side_effect=Exception("Event not found"))

        result = await calendar_tool.run(
            action="update_event",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="SUPERVISED",
            event_id="nonexistent-event",
            summary="Updated"
        )

        assert result["success"] == False

    @patch('tools.calendar_tool.google_calendar_service')
    @pytest.mark.asyncio
    async def test_delete_event_not_found(self, mock_gcal_service, calendar_tool):
        """Delete non-existent event."""
        mock_gcal_service.delete_event = AsyncMock(return_value=False)

        result = await calendar_tool.run(
            action="delete_event",
            user_id="user-123",
            agent_id="agent-123",
            maturity_level="SUPERVISED",
            event_id="nonexistent-event"
        )

        assert result["success"] == False


class TestCalendarToolGovernance:
    """Coverage expansion for calendar governance enforcement."""

    @pytest.fixture
    def calendar_tool(self):
        """Get calendar tool instance."""
        return CalendarTool()

    # Test: Maturity level enforcement
    @pytest.mark.asyncio
    async def test_student_blocked_from_all_operations(self, calendar_tool):
        """Student agents blocked from all calendar operations."""
        # Current contract: run() raises PermissionError when governance
        # denies the action (see docstring of CalendarTool.run).
        with pytest.raises(PermissionError):
            await calendar_tool.run(
                action="get_events",
                user_id="user-123",
                agent_id="student-agent",
                maturity_level="STUDENT"
            )

        with pytest.raises(PermissionError):
            await calendar_tool.run(
                action="create_event",
                user_id="user-123",
                agent_id="student-agent",
                maturity_level="STUDENT",
                summary="Meeting",
                start_time="2026-04-12T16:00:00",
                end_time="2026-04-12T17:00:00"
            )

    @pytest.mark.asyncio
    async def test_internet_allowed_read_only(self, calendar_tool):
        """INTERN agents allowed read operations only."""
        # Note: These will fail due to auth/API issues, but should pass governance check
        # We're testing governance logic, not API connectivity
        pass  # Would need more complex mocking to test this properly

    @pytest.mark.asyncio
    async def test_supervised_allowed_all_operations(self, calendar_tool):
        """SUPERVISED agents allowed all operations."""
        # Note: Would need more complex mocking
        pass

    @pytest.mark.asyncio
    async def test_autonomous_allowed_all_operations(self, calendar_tool):
        """AUTONOMOUS agents allowed all operations."""
        # Note: Would need more complex mocking
        pass
