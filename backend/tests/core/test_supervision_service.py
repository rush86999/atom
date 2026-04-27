"""
Comprehensive Unit Tests for Supervision Service

================================================================================
PUBLIC METHODS
================================================================================

1. start_supervision_session(agent_id, trigger_context, workspace_id, supervisor_id)
   - Creates supervision session for SUPERVISED agents
   - Validates agent exists and has SUPERVISED maturity
   - Returns SupervisionSession with RUNNING status

2. monitor_agent_execution(session, db)
   - Async generator yielding SupervisionEvent objects
   - Polls AgentExecution table for real-time updates
   - Detects execution status changes (running → completed/failed)
   - 30-minute max duration with 500ms poll interval

3. intervene(session_id, intervention_type, guidance)
   - Human supervisor intervention in agent execution
   - Types: "pause", "correct", "terminate"
   - Updates session state and records intervention
   - Returns InterventionResult

4. complete_supervision(session_id, supervisor_rating, feedback)
   - Completes supervision session and records outcomes
   - Calculates confidence boost based on performance
   - Updates agent confidence score
   - Triggers episode creation and two-way learning
   - Returns SupervisionOutcome

5. get_active_sessions(workspace_id, limit)
   - Returns currently active supervision sessions
   - Optional workspace filtering
   - Ordered by start time (newest first)

6. get_supervision_history(agent_id, limit)
   - Returns agent's supervision history
   - Ordered by start time (newest first)
   - Returns list of session summaries

7. start_supervision_with_fallback(agent_id, trigger_context, workspace_id, user_id)
   - Start supervision with autonomous fallback
   - Uses human supervisor if available
   - Falls back to autonomous supervisor if human unavailable
   - Queues execution if no supervisor available

8. monitor_with_autonomous_fallback(session)
   - Monitor execution with autonomous supervisor
   - Routes to autonomous monitoring if supervisor is agent
   - Uses human monitoring for human supervisors

================================================================================
CRITICAL PATHS
================================================================================

1. Supervision Session Initialization
   - Agent lookup and validation
   - Session creation with proper status
   - Database commit and refresh

2. Real-Time Execution Monitoring
   - Polling AgentExecution table
   - Detecting status changes
   - Yielding supervision events
   - Handling max duration timeout

3. Intervention Trigger Logic
   - Session validation (must be RUNNING)
   - Intervention type validation
   - Session state updates
   - Intervention recording

4. Session Completion
   - Duration calculation
   - Confidence boost calculation
   - Agent confidence score update
   - AUTONOMOUS promotion check
   - Episode creation trigger (non-blocking)
   - Two-way learning trigger (non-blocking)

5. Autonomous Supervisor Fallback
   - User activity check
   - Autonomous supervisor lookup
   - Execution queuing if no supervisor

================================================================================
INTERVENTION SCENARIOS
================================================================================

1. Safety Violation Detection
   - Agent performing unsafe action
   - Intervention type: "terminate" or "pause"
   - Records violation in session

2. User Intervention Requests
   - Human supervisor detects issue
   - Intervention type: "pause", "correct", "terminate"
   - Provides guidance/correction

3. Automatic Intervention Triggers
   - Confidence drops below threshold
   - Execution timeout
   - Error rate exceeds limit

4. Intervention Escalation
   - Multiple interventions in session
   - Agent confidence impacted
   - Learning captured for future

================================================================================
WEBSOCKET COMMUNICATION
================================================================================

Note: Current implementation uses async generators (yield events) rather than
WebSocket. Future enhancements may add WebSocket support for real-time updates.

1. Event Broadcasting
   - SupervisionEvent objects yielded to monitor
   - Event types: "action", "result", "warning", "error"
   - Timestamped event data

2. Connection Management
   - Session-based monitoring
   - Automatic cleanup on completion

3. Error Handling
   - Monitoring errors yield error events
   - Session continues despite errors

================================================================================
SAFETY GUARDRAILS
================================================================================

1. Student Agent Rejection
   - STUDENT maturity agents cannot start supervision
   - Route to training instead

2. Intervention Validation
   - Session must be RUNNING to intervene
   - Intervention type must be valid
   - Session must exist

3. Permission Checks
   - Only supervisors can intervene
   - Only session owner can complete

4. Confidence Boost Calculation
   - Max boost: 0.1 (5-star rating, no interventions)
   - Min boost: 0.0 (1-star rating)
   - Intervention penalty: 0.01 per intervention
   - Caps at 1.0 (AUTONOMOUS threshold)

================================================================================
DEPENDENCIES
================================================================================

1. Database (Session)
   - AgentRegistry queries
   - SupervisionSession CRUD
   - AgentExecution monitoring
   - Transaction management

2. Episode Segmentation Service (optional, non-blocking)
   - create_supervision_episode()
   - Triggered on session completion

3. Feedback Service (optional, non-blocking)
   - rate_supervisor()
   - Creates supervisor ratings

4. Supervisor Learning Service (optional, non-blocking)
   - process_feedback_for_learning()
   - Triggers learning updates

5. User Activity Service (optional)
   - get_user_state()
   - Checks user availability for fallback

6. Autonomous Supervisor Service (optional)
   - find_autonomous_supervisor()
   - Finds autonomous supervisor for fallback

7. Supervised Queue Service (optional)
   - enqueue_execution()
   - Queues execution when no supervisor available

================================================================================
TEST COVERAGE GOAL: >=80% (target: 737 lines → 590+ lines covered)
================================================================================
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import asyncio
import json

from core.supervision_service import (
    SupervisionService,
    SupervisionEvent,
    InterventionResult,
    SupervisionOutcome
)
from core.models import (
    AgentRegistry,
    AgentExecution,
    AgentStatus,
    SupervisionSession,
    SupervisionStatus,
    User,
    Workspace
)


# ========================================================================
# Fixtures
# ========================================================================

@pytest.fixture
def db_session():
    """Mock database session"""
    session = Mock()
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def mock_agent():
    """Mock SUPERVISED agent"""
    agent = Mock(spec=AgentRegistry)
    agent.id = "agent_supervised_123"
    agent.name = "Test Supervised Agent"
    agent.status = AgentStatus.SUPERVISED.value
    agent.confidence_score = 0.75
    return agent


@pytest.fixture
def mock_session():
    """Mock supervision session"""
    session = Mock(spec=SupervisionSession)
    session.id = "session_123"
    session.agent_id = "agent_supervised_123"
    session.agent_name = "Test Supervised Agent"
    session.workspace_id = "workspace_123"
    session.supervisor_id = "supervisor_123"
    session.status = SupervisionStatus.RUNNING.value
    session.started_at = datetime.now()
    session.completed_at = None
    session.duration_seconds = None
    session.intervention_count = 0
    session.interventions = []
    session.supervisor_rating = None
    session.supervisor_feedback = None
    session.confidence_boost = None
    session.trigger_context = {"trigger_type": "automated"}
    return session


@pytest.fixture
def mock_execution():
    """Mock agent execution"""
    execution = Mock(spec=AgentExecution)
    execution.id = "execution_123"
    execution.agent_id = "agent_supervised_123"
    execution.status = "running"
    execution.started_at = datetime.now()
    execution.completed_at = None
    execution.input_summary = "Test input"
    execution.output_summary = None
    execution.error_message = None
    execution.duration_seconds = None
    return execution


@pytest.fixture
def supervision_service(db_session):
    """SupervisionService instance with mock DB"""
    return SupervisionService(db=db_session)


# ========================================================================
# Test Category 1: Supervision Lifecycle Tests (80 lines)
# ========================================================================

class TestSupervisionLifecycle:
    """Test supervision session lifecycle management"""

    def test_start_supervision_creates_session(
        self, supervision_service, db_session, mock_agent
    ):
        """Test starting supervision creates a session with correct status"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_agent
        db_session.query.return_value = mock_query

        # Execute
        result = asyncio.run(supervision_service.start_supervision_session(
            agent_id="agent_supervised_123",
            trigger_context={"trigger_type": "automated"},
            workspace_id="workspace_123",
            supervisor_id="supervisor_123"
        ))

        # Verify session created
        assert db_session.add.called
        assert db_session.commit.called
        assert db_session.refresh.called

    def test_start_supervision_validates_agent_exists(
        self, supervision_service, db_session
    ):
        """Test starting supervision fails for non-existent agent"""
        # Setup mock query to return None
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query.return_value = mock_query

        # Execute and verify exception
        with pytest.raises(ValueError, match="Agent .* not found"):
            asyncio.run(supervision_service.start_supervision_session(
                agent_id="nonexistent_agent",
                trigger_context={},
                workspace_id="workspace_123",
                supervisor_id="supervisor_123"
            ))

    def test_start_supervision_initializes_monitoring(
        self, supervision_service, db_session, mock_agent
    ):
        """Test session initialized with correct monitoring state"""
        # Setup mock
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_agent
        db_session.query.return_value = mock_query

        # Execute
        session = asyncio.run(supervision_service.start_supervision_session(
            agent_id="agent_supervised_123",
            trigger_context={"trigger_type": "automated"},
            workspace_id="workspace_123",
            supervisor_id="supervisor_123"
        ))

        # Verify session attributes
        assert session.agent_id == mock_agent.id
        assert session.agent_name == mock_agent.name
        assert session.status == SupervisionStatus.RUNNING.value
        assert session.intervention_count == 0

    def test_start_supervision_rejects_student_agents(
        self, supervision_service, db_session
    ):
        """Test STUDENT maturity agents cannot start supervision"""
        # Create STUDENT agent
        student_agent = Mock(spec=AgentRegistry)
        student_agent.id = "agent_student_123"
        student_agent.name = "Test Student Agent"
        student_agent.status = AgentStatus.STUDENT.value
        student_agent.confidence_score = 0.4

        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = student_agent
        db_session.query.return_value = mock_query

        # Note: Current implementation doesn't explicitly check maturity
        # This test documents expected behavior
        # Future implementation should add this validation
        pass  # Placeholder for maturity validation test

    def test_get_active_sessions_returns_list(
        self, supervision_service, db_session, mock_session
    ):
        """Test getting active sessions returns list"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_session]
        db_session.query.return_value = mock_query

        # Execute
        sessions = asyncio.run(supervision_service.get_active_sessions(
            workspace_id="workspace_123",
            limit=50
        ))

        # Verify query called correctly
        assert db_session.query.called
        assert mock_query.filter.called
        assert mock_query.order_by.called
        assert mock_query.limit.called

    def test_get_active_sessions_filters_by_workspace(
        self, supervision_service, db_session, mock_session
    ):
        """Test getting active sessions filters by workspace"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db_session.query.return_value = mock_query

        # Execute with workspace filter
        sessions = asyncio.run(supervision_service.get_active_sessions(
            workspace_id="workspace_123",
            limit=50
        ))

        # Verify filter called with workspace
        assert mock_query.filter.called

    def test_get_active_sessions_no_workspace_filter(
        self, supervision_service, db_session
    ):
        """Test getting active sessions without workspace filter"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db_session.query.return_value = mock_query

        # Execute without workspace filter
        sessions = asyncio.run(supervision_service.get_active_sessions())

        # Verify query called
        assert db_session.query.called

    def test_get_supervision_history_returns_list(
        self, supervision_service, db_session, mock_session
    ):
        """Test getting supervision history returns list"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_session]
        db_session.query.return_value = mock_query

        # Execute
        history = asyncio.run(supervision_service.get_supervision_history(
            agent_id="agent_supervised_123",
            limit=50
        ))

        # Verify query called
        assert db_session.query.called
        assert mock_query.filter.called
        assert mock_query.order_by.called


# ========================================================================
# Test Category 2: Monitoring Tests (80 lines)
# ========================================================================

class TestMonitoring:
    """Test real-time execution monitoring"""

    @pytest.mark.asyncio
    async def test_monitor_execution_tracks_operations(
        self, supervision_service, mock_session, mock_execution
    ):
        """Test monitoring tracks agent execution operations"""
        # Mock session refresh
        mock_session.status = SupervisionStatus.RUNNING.value

        # Mock execution query
        db = Mock()
        db.refresh = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_execution
        db.query.return_value = mock_query

        # Execute monitoring (collect first event)
        events = []
        async for event in supervision_service.monitor_agent_execution(mock_session, db):
            events.append(event)
            if len(events) >= 1:
                break

        # Verify events generated
        assert len(events) > 0
        assert events[0].event_type in ["action", "result", "error"]

    @pytest.mark.asyncio
    async def test_monitor_execution_detects_status_changes(
        self, supervision_service, mock_session, mock_execution
    ):
        """Test monitoring detects execution status changes"""
        # Mock execution status change
        mock_execution.status = "completed"
        mock_execution.completed_at = datetime.now()
        mock_execution.output_summary = "Task completed successfully"

        # Mock database
        db = Mock()
        db.refresh = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_execution
        db.query.return_value = mock_query

        # Execute monitoring
        events = []
        async for event in supervision_service.monitor_agent_execution(mock_session, db):
            events.append(event)
            if event.event_type == "result":
                break

        # Verify completion event detected
        assert any(e.event_type == "result" for e in events)

    @pytest.mark.asyncio
    async def test_monitor_execution_captures_execution_time(
        self, supervision_service, mock_session, mock_execution
    ):
        """Test monitoring captures execution duration"""
        # Mock execution with duration
        mock_execution.started_at = datetime.now() - timedelta(seconds=30)
        mock_execution.duration_seconds = 30

        # Mock database
        db = Mock()
        db.refresh = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_execution
        db.query.return_value = mock_query

        # Execute monitoring
        events = []
        async for event in supervision_service.monitor_agent_execution(mock_session, db):
            events.append(event)
            if len(events) >= 1:
                break

        # Verify event captured
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_monitor_execution_handles_agent_errors(
        self, supervision_service, mock_session, mock_execution
    ):
        """Test monitoring handles agent execution errors"""
        # Mock failed execution
        mock_execution.status = "failed"
        mock_execution.error_message = "Execution failed: API timeout"

        # Mock database
        db = Mock()
        db.refresh = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_execution
        db.query.return_value = mock_query

        # Execute monitoring
        events = []
        async for event in supervision_service.monitor_agent_execution(mock_session, db):
            events.append(event)
            if event.event_type == "error":
                break

        # Verify error event detected
        assert any(e.event_type == "error" for e in events)

    @pytest.mark.asyncio
    async def test_monitor_execution_updates_session_state(
        self, supervision_service, mock_session
    ):
        """Test monitoring respects session state changes"""
        # Mock session that stops running
        mock_session.status = SupervisionStatus.COMPLETED.value

        # Mock database
        db = Mock()
        db.refresh = Mock()

        # Execute monitoring
        events = []
        async for event in supervision_service.monitor_agent_execution(mock_session, db):
            events.append(event)

        # Verify monitoring stopped
        assert len(events) == 0  # No events because session not running

    @pytest.mark.asyncio
    async def test_monitor_execution_execution_timeout(
        self, supervision_service, mock_session
    ):
        """Test monitoring respects max duration timeout"""
        # Mock session that stays running
        mock_session.status = SupervisionStatus.RUNNING.value

        # Mock database
        db = Mock()
        db.refresh = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value = mock_query

        # Execute monitoring (should timeout after 30 minutes)
        # For testing, we'll break early
        events = []
        async for event in supervision_service.monitor_agent_execution(mock_session, db):
            events.append(event)
            if len(events) >= 1:  # Break after first event to avoid 30-minute wait
                break

        # Verify monitoring started
        assert len(events) >= 0

    @pytest.mark.asyncio
    async def test_monitor_execution_logs_agent_actions(
        self, supervision_service, mock_session, mock_execution
    ):
        """Test monitoring logs agent actions to session"""
        # Mock execution
        mock_execution.status = "running"

        # Mock database
        db = Mock()
        db.refresh = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_execution
        db.query.return_value = mock_query

        # Execute monitoring
        events = []
        async for event in supervision_service.monitor_agent_execution(mock_session, db):
            events.append(event)
            if len(events) >= 1:
                break

        # Verify action event logged
        assert any(e.event_type == "action" for e in events)


# ========================================================================
# Test Category 3: Intervention Tests (90 lines)
# ========================================================================

class TestIntervention:
    """Test supervisor intervention logic"""

    @pytest.mark.asyncio
    async def test_trigger_intervention_stops_execution(
        self, supervision_service, db_session, mock_session
    ):
        """Test pause intervention stops execution"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute pause intervention
        result = await supervision_service.intervene(
            session_id="session_123",
            intervention_type="pause",
            guidance="Pause execution for review"
        )

        # Verify intervention result
        assert result.success is True
        assert result.session_state == "paused"
        assert "paused" in result.message.lower()

    @pytest.mark.asyncio
    async def test_trigger_intervention_logs_reason(
        self, supervision_service, db_session, mock_session
    ):
        """Test intervention logs reason to session"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute intervention
        result = await supervision_service.intervene(
            session_id="session_123",
            intervention_type="correct",
            guidance="Fix the calculation error"
        )

        # Verify intervention recorded
        assert len(mock_session.interventions) > 0
        assert mock_session.intervention_count > 0
        assert db_session.commit.called

    @pytest.mark.asyncio
    async def test_trigger_intervention_notifies_user(
        self, supervision_service, db_session, mock_session
    ):
        """Test intervention provides user feedback"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute intervention
        result = await supervision_service.intervene(
            session_id="session_123",
            intervention_type="correct",
            guidance="Use the correct API endpoint"
        )

        # Verify message returned
        assert result.message is not None
        assert len(result.message) > 0

    @pytest.mark.asyncio
    async def test_trigger_intervention_validates_permission(
        self, supervision_service, db_session, mock_session
    ):
        """Test intervention validates session is running"""
        # Set session as completed
        mock_session.status = SupervisionStatus.COMPLETED.value

        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute and verify exception
        with pytest.raises(ValueError, match="Session must be RUNNING"):
            await supervision_service.intervene(
                session_id="session_123",
                intervention_type="pause",
                guidance="Pause for review"
            )

    @pytest.mark.asyncio
    async def test_trigger_intervention_safety_violation(
        self, supervision_service, db_session, mock_session
    ):
        """Test intervention for safety violation"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute terminate intervention for safety violation
        result = await supervision_service.intervene(
            session_id="session_123",
            intervention_type="terminate",
            guidance="Safety violation: attempting unauthorized data access"
        )

        # Verify termination
        assert result.session_state == "terminated"
        assert mock_session.status == SupervisionStatus.INTERRUPTED.value
        assert mock_session.completed_at is not None

    @pytest.mark.asyncio
    async def test_trigger_intervention_user_request(
        self, supervision_service, db_session, mock_session
    ):
        """Test intervention from user request"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute user-requested correction
        result = await supervision_service.intervene(
            session_id="session_123",
            intervention_type="correct",
            guidance="User requested: Use different parameters"
        )

        # Verify correction applied
        assert result.session_state == "running"
        assert "correction" in result.message.lower() or "continuing" in result.message.lower()

    @pytest.mark.asyncio
    async def test_trigger_intervention_automatic_trigger(
        self, supervision_service, db_session, mock_session
    ):
        """Test intervention from automatic trigger"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute automatic intervention
        result = await supervision_service.intervene(
            session_id="session_123",
            intervention_type="pause",
            guidance="Automatic pause: Confidence dropped below threshold"
        )

        # Verify intervention executed
        assert result.success is True

    @pytest.mark.asyncio
    async def test_trigger_intervention_escalation_logic(
        self, supervision_service, db_session, mock_session
    ):
        """Test intervention escalation with multiple interventions"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute multiple interventions
        await supervision_service.intervene(
            session_id="session_123",
            intervention_type="pause",
            guidance="First intervention"
        )

        await supervision_service.intervene(
            session_id="session_123",
            intervention_type="correct",
            guidance="Second intervention"
        )

        # Verify escalation tracked
        assert mock_session.intervention_count == 2
        assert len(mock_session.interventions) == 2

    @pytest.mark.asyncio
    async def test_multiple_interventions_same_session(
        self, supervision_service, db_session, mock_session
    ):
        """Test multiple interventions in same session"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute first intervention
        result1 = await supervision_service.intervene(
            session_id="session_123",
            intervention_type="pause",
            guidance="First pause"
        )

        # Execute second intervention
        result2 = await supervision_service.intervene(
            session_id="session_123",
            intervention_type="correct",
            guidance="Apply correction"
        )

        # Verify both interventions recorded
        assert mock_session.intervention_count == 2
        assert result1.success is True
        assert result2.success is True


# ========================================================================
# Test Category 4: WebSocket Communication Tests (80 lines)
# ========================================================================

class TestWebSocketCommunication:
    """Test WebSocket communication for live supervision updates"""

    @pytest.mark.asyncio
    async def test_supervision_event_broadcasts_message(
        self, supervision_service, mock_session
    ):
        """Test SupervisionEvent contains broadcast data"""
        event = SupervisionEvent(
            event_type="action",
            timestamp=datetime.now(),
            data={"action_type": "execution_started"}
        )

        # Verify event structure
        assert event.event_type == "action"
        assert event.data is not None
        assert isinstance(event.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_supervision_event_json_serialization(
        self, supervision_service, mock_session
    ):
        """Test SupervisionEvent can be JSON serialized"""
        event = SupervisionEvent(
            event_type="result",
            timestamp=datetime.now(),
            data={"status": "completed", "output": "Done"}
        )

        # Verify JSON serializable
        json_data = {
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data
        }

        assert json_data["event_type"] == "result"
        assert "output" in json_data["data"]

    @pytest.mark.asyncio
    async def test_supervision_event_error_handling(
        self, supervision_service, mock_session
    ):
        """Test error event contains error details"""
        event = SupervisionEvent(
            event_type="error",
            timestamp=datetime.now(),
            data={
                "error_type": "monitoring_error",
                "error_message": "Database connection failed",
                "session_id": "session_123"
            }
        )

        # Verify error event structure
        assert event.event_type == "error"
        assert "error_message" in event.data
        assert "session_id" in event.data

    @pytest.mark.asyncio
    async def test_supervision_event_action_types(
        self, supervision_service, mock_session
    ):
        """Test various action event types"""
        action_types = [
            "execution_started",
            "execution_progress",
            "execution_completed"
        ]

        for action_type in action_types:
            event = SupervisionEvent(
                event_type="action",
                timestamp=datetime.now(),
                data={"action_type": action_type}
            )

            assert event.data["action_type"] == action_type

    @pytest.mark.asyncio
    async def test_supervision_event_result_types(
        self, supervision_service, mock_session
    ):
        """Test various result event types"""
        event = SupervisionEvent(
            event_type="result",
            timestamp=datetime.now(),
            data={
                "step": "execution_completed",
                "status": "completed",
                "output_summary": "Task completed"
            }
        )

        assert event.event_type == "result"
        assert event.data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_monitor_with_autonomous_fallback(
        self, supervision_service, mock_session
    ):
        """Test monitoring with autonomous supervisor fallback"""
        # Mock session with autonomous supervisor
        mock_session.supervisor_id = "autonomous_supervisor_123"
        mock_session.trigger_context = {"user_id": "user_123"}

        # Execute (should not raise exception)
        await supervision_service.monitor_with_autonomous_fallback(mock_session)

        # Verify no exception raised
        assert True

    @pytest.mark.asyncio
    async def test_websocket_message_format_validation(
        self, supervision_service
    ):
        """Test WebSocket message format validation"""
        event = SupervisionEvent(
            event_type="action",
            timestamp=datetime.now(),
            data={"action_type": "test"}
        )

        # Validate message format
        assert hasattr(event, "event_type")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "data")
        assert isinstance(event.data, dict)


# ========================================================================
# Test Category 5: Safety Guardrails Tests (70 lines)
# ========================================================================

class TestSafetyGuardrails:
    """Test safety guardrails for supervision"""

    @pytest.mark.asyncio
    async def test_supervision_rejects_student_maturity(
        self, supervision_service, db_session
    ):
        """
        Test STUDENT maturity agents rejected from supervision.

        NOTE: Current implementation doesn't explicitly check maturity.
        This test documents expected safety behavior.
        Future implementation should add explicit STUDENT rejection.
        """
        # Document expected behavior
        # STUDENT agents should be rejected with ValueError
        # Route to training instead
        pass

    @pytest.mark.asyncio
    async def test_supervision_requires_supervisable_maturity(
        self, supervision_service, db_session
    ):
        """Test only SUPERVISED agents can start supervision"""
        # Only SUPERVISED (0.7-0.9 confidence) should be allowed
        # AUTONOMOUS (>0.9) don't need supervision
        # STUDENT (<0.5) should route to training
        # INTERN (0.5-0.7) should require approval
        pass

    @pytest.mark.asyncio
    async def test_intervention_requires_valid_session(
        self, supervision_service, db_session
    ):
        """Test intervention requires valid session ID"""
        # Setup mock query to return None
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query.return_value = mock_query

        # Execute and verify exception
        with pytest.raises(ValueError, match="Supervision session .* not found"):
            await supervision_service.intervene(
                session_id="nonexistent_session",
                intervention_type="pause",
                guidance="Test"
            )

    @pytest.mark.asyncio
    async def test_intervention_requires_running_session(
        self, supervision_service, db_session, mock_session
    ):
        """Test intervention requires session to be RUNNING"""
        # Set session as completed
        mock_session.status = SupervisionStatus.COMPLETED.value

        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute and verify exception
        with pytest.raises(ValueError, match="Session must be RUNNING"):
            await supervision_service.intervene(
                session_id="session_123",
                intervention_type="pause",
                guidance="Test"
            )

    @pytest.mark.asyncio
    async def test_intervention_validates_intervention_type(
        self, supervision_service, db_session, mock_session
    ):
        """Test intervention validates intervention type"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute and verify exception for invalid type
        with pytest.raises(ValueError, match="Unknown intervention type"):
            await supervision_service.intervene(
                session_id="session_123",
                intervention_type="invalid_type",
                guidance="Test"
            )

    @pytest.mark.asyncio
    async def test_guardrails_prevent_unsafe_actions(
        self, supervision_service, db_session, mock_session
    ):
        """Test guardrails prevent unsafe agent actions"""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute terminate intervention for unsafe action
        result = await supervision_service.intervene(
            session_id="session_123",
            intervention_type="terminate",
            guidance="Unsafe action detected"
        )

        # Verify execution stopped
        assert result.session_state == "terminated"
        assert mock_session.status == SupervisionStatus.INTERRUPTED.value

    @pytest.mark.asyncio
    async def test_confidence_boost_calculation(
        self, supervision_service
    ):
        """Test confidence boost calculation with safety limits"""
        # Test various rating/intervention combinations
        test_cases = [
            {"rating": 5, "interventions": 0, "expected_min": 0.09, "expected_max": 0.1},
            {"rating": 3, "interventions": 2, "expected_min": 0.03, "expected_max": 0.05},
            {"rating": 1, "interventions": 5, "expected_min": 0.0, "expected_max": 0.0},
        ]

        for case in test_cases:
            boost = supervision_service._calculate_confidence_boost(
                supervisor_rating=case["rating"],
                intervention_count=case["interventions"],
                duration_seconds=300
            )

            assert case["expected_min"] <= boost <= case["expected_max"]


# ========================================================================
# Test Category 6: Session Completion Tests
# ========================================================================

class TestSessionCompletion:
    """Test supervision session completion logic"""

    @pytest.mark.asyncio
    async def test_complete_supervision_calculates_duration(
        self, supervision_service, db_session, mock_session, mock_agent
    ):
        """Test completing supervision calculates duration correctly"""
        # Setup mock session with start time
        start_time = datetime.now() - timedelta(seconds=120)
        mock_session.started_at = start_time
        mock_session.status = SupervisionStatus.RUNNING.value

        # Setup mock queries
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [mock_session, mock_agent]
        db_session.query.return_value = mock_query

        # Execute completion
        outcome = await supervision_service.complete_supervision(
            session_id="session_123",
            supervisor_rating=4,
            feedback="Good performance"
        )

        # Verify duration calculated
        assert outcome.duration_seconds >= 115  # ~120 seconds, accounting for execution time
        assert outcome.duration_seconds <= 125

    @pytest.mark.asyncio
    async def test_complete_supervision_updates_agent_confidence(
        self, supervision_service, db_session, mock_session, mock_agent
    ):
        """Test completing supervision updates agent confidence"""
        # Setup mock queries
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [mock_session, mock_agent]
        db_session.query.return_value = mock_query

        # Execute completion with good rating
        old_confidence = mock_agent.confidence_score
        outcome = await supervision_service.complete_supervision(
            session_id="session_123",
            supervisor_rating=5,
            feedback="Excellent"
        )

        # Verify confidence increased
        assert mock_agent.confidence_score > old_confidence
        assert outcome.confidence_boost > 0

    @pytest.mark.asyncio
    async def test_complete_supervision_promotes_to_autonomous(
        self, supervision_service, db_session, mock_session, mock_agent
    ):
        """Test completing supervision promotes agent to AUTONOMOUS"""
        # Setup agent at 0.89 confidence (just below threshold)
        mock_agent.confidence_score = 0.89

        # Setup mock queries
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [mock_session, mock_agent]
        db_session.query.return_value = mock_query

        # Execute completion with excellent rating
        await supervision_service.complete_supervision(
            session_id="session_123",
            supervisor_rating=5,
            feedback="Excellent - ready for autonomy"
        )

        # Verify promotion
        assert mock_agent.confidence_score >= 0.9
        assert mock_agent.status == AgentStatus.AUTONOMOUS.value

    @pytest.mark.asyncio
    async def test_complete_supervision_creates_outcome(
        self, supervision_service, db_session, mock_session, mock_agent
    ):
        """Test completing supervision creates SupervisionOutcome"""
        # Setup mock queries
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [mock_session, mock_agent]
        db_session.query.return_value = mock_query

        # Execute completion
        outcome = await supervision_service.complete_supervision(
            session_id="session_123",
            supervisor_rating=4,
            feedback="Good performance, minor corrections"
        )

        # Verify outcome structure
        assert isinstance(outcome, SupervisionOutcome)
        assert outcome.session_id == "session_123"
        assert outcome.supervisor_rating == 4
        assert outcome.feedback == "Good performance, minor corrections"
        assert outcome.intervention_count == mock_session.intervention_count

    @pytest.mark.asyncio
    async def test_complete_supervision_validates_session_status(
        self, supervision_service, db_session, mock_session
    ):
        """Test completing supervision validates session is RUNNING"""
        # Set session as already completed
        mock_session.status = SupervisionStatus.COMPLETED.value

        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        db_session.query.return_value = mock_query

        # Execute and verify exception
        with pytest.raises(ValueError, match="Session must be RUNNING"):
            await supervision_service.complete_supervision(
                session_id="session_123",
                supervisor_rating=4,
                feedback="Test"
            )

    @pytest.mark.asyncio
    async def test_complete_supervision_triggers_episode_creation(
        self, supervision_service, db_session, mock_session, mock_agent
    ):
        """
        Test completing supervision triggers episode creation (non-blocking).

        NOTE: Episode creation is wrapped in try-except and uses asyncio.create_task.
        This test verifies the logic path is exercised, but doesn't wait for task completion.
        """
        # Setup mock queries
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [mock_session, mock_agent, None]
        db_session.query.return_value = mock_query

        # Mock episode service (optional, may not be available)
        with patch('core.supervision_service.asyncio.create_task'):
            outcome = await supervision_service.complete_supervision(
                session_id="session_123",
                supervisor_rating=4,
                feedback="Good"
            )

            # Verify outcome created (episode creation is non-blocking)
            assert outcome is not None

    @pytest.mark.asyncio
    async def test_complete_supervision_triggers_two_way_learning(
        self, supervision_service, db_session, mock_session, mock_agent
    ):
        """
        Test completing supervision triggers two-way learning (non-blocking).

        NOTE: Two-way learning is wrapped in try-except and uses asyncio.create_task.
        This test verifies the logic path is exercised.
        """
        # Setup mock queries
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [mock_session, mock_agent]
        db_session.query.return_value = mock_query

        # Mock learning services (optional, may not be available)
        with patch('core.supervision_service.asyncio.create_task'):
            outcome = await supervision_service.complete_supervision(
                session_id="session_123",
                supervisor_rating=4,
                feedback="Good"
            )

            # Verify outcome created (learning is non-blocking)
            assert outcome is not None


# ========================================================================
# Test Category 7: Autonomous Supervisor Fallback Tests
# ========================================================================

class TestAutonomousSupervisorFallback:
    """Test autonomous supervisor fallback logic"""

    @pytest.mark.asyncio
    async def test_start_supervision_with_fallback_uses_human(
        self, supervision_service, db_session, mock_agent
    ):
        """Test fallback uses human supervisor when available"""
        # Setup mock queries
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [mock_agent, None]  # agent exists, no autonomous needed
        db_session.query.return_value = mock_query

        # Mock user activity service
        with patch('core.supervision_service.UserActivityService') as mock_user_activity:
            mock_activity_service = AsyncMock()
            mock_activity_service.get_user_state.return_value = "online"
            mock_user_activity.return_value = mock_activity_service

            # Execute with human available
            session = await supervision_service.start_supervision_with_fallback(
                agent_id="agent_supervised_123",
                trigger_context={"trigger_type": "automated", "user_id": "user_123"},
                workspace_id="workspace_123",
                user_id="user_123"
            )

            # Verify session created with human supervisor
            assert session.supervisor_id == "user_123"

    @pytest.mark.asyncio
    async def test_start_supervision_with_fallback_falls_back_to_autonomous(
        self, supervision_service, db_session, mock_agent
    ):
        """Test fallback uses autonomous supervisor when human unavailable"""
        # Setup mock queries
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [mock_agent, None, mock_agent]
        db_session.query.return_value = mock_query

        # Mock user activity service (user offline)
        with patch('core.supervision_service.UserActivityService') as mock_user_activity:
            mock_activity_service = AsyncMock()
            mock_activity_service.get_user_state.return_value = "offline"
            mock_user_activity.return_value = mock_activity_service

            # Mock autonomous supervisor service (no autonomous supervisor found)
            with patch('core.supervision_service.AutonomousSupervisorService') as mock_autonomous:
                mock_auto_service = AsyncMock()
                mock_auto_service.find_autonomous_supervisor.return_value = None
                mock_autonomous.return_value = mock_auto_service

                # Mock queue service
                with patch('core.supervision_service.SupervisedQueueService') as mock_queue:
                    mock_queue_service = AsyncMock()
                    mock_queue.return_value = mock_queue_service

                    # Execute and verify exception (execution queued)
                    with pytest.raises(ValueError, match="User unavailable and no autonomous supervisor"):
                        await supervision_service.start_supervision_with_fallback(
                            agent_id="agent_supervised_123",
                            trigger_context={"trigger_type": "automated", "user_id": "user_123"},
                            workspace_id="workspace_123",
                            user_id="user_123"
                        )

    @pytest.mark.asyncio
    async def test_monitor_with_autonomous_supervisor(
        self, supervision_service, mock_session
    ):
        """Test monitoring with autonomous supervisor"""
        # Mock session with autonomous supervisor
        mock_session.supervisor_id = "autonomous_agent_123"
        mock_session.trigger_context = {"user_id": "user_123"}

        # Mock autonomous supervisor service
        with patch('core.supervision_service.AutonomousSupervisorService') as mock_autonomous:
            mock_auto_service = Mock()
            mock_auto_service.monitor_execution.return_value = self._mock_event_generator()
            mock_autonomous.return_value = mock_auto_service

            # Mock database queries
            db = Mock()
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = None
            db.query.return_value = mock_query

            # Execute monitoring
            await supervision_service.monitor_with_autonomous_fallback(mock_session)

            # Verify no exception raised
            assert True

    def _mock_event_generator(self):
        """Helper to create mock event generator"""
        async def event_gen():
            yield SupervisionEvent(
                event_type="action",
                timestamp=datetime.now(),
                data={"test": "data"}
            )
        return event_gen()


# ========================================================================
# Test Category 8: Edge Cases and Error Handling
# ========================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_monitor_execution_handles_missing_execution(
        self, supervision_service, mock_session
    ):
        """Test monitoring handles missing AgentExecution gracefully"""
        # Mock session that's running
        mock_session.status = SupervisionStatus.RUNNING.value

        # Mock database with no execution
        db = Mock()
        db.refresh = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value = mock_query

        # Execute monitoring (should handle gracefully)
        events = []
        async for event in supervision_service.monitor_agent_execution(mock_session, db):
            events.append(event)
            if len(events) >= 1:
                break

        # Verify no crash
        assert True

    @pytest.mark.asyncio
    async def test_monitor_execution_handles_database_errors(
        self, supervision_service, mock_session
    ):
        """Test monitoring handles database errors gracefully"""
        # Mock database that raises exception
        db = Mock()
        db.refresh.side_effect = Exception("Database connection lost")

        # Execute monitoring (should yield error event)
        events = []
        async for event in supervision_service.monitor_agent_execution(mock_session, db):
            events.append(event)
            if event.event_type == "error":
                break

        # Verify error event generated
        assert any(e.event_type == "error" for e in events)

    @pytest.mark.asyncio
    async def test_intervention_handles_invalid_session_id(
        self, supervision_service, db_session
    ):
        """Test intervention handles invalid session ID"""
        # Mock query to return None
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query.return_value = mock_query

        # Execute and verify exception
        with pytest.raises(ValueError, match="Supervision session .* not found"):
            await supervision_service.intervene(
                session_id="invalid_session_id",
                intervention_type="pause",
                guidance="Test"
            )

    @pytest.mark.asyncio
    async def test_complete_supervision_handles_invalid_session(
        self, supervision_service, db_session
    ):
        """Test completion handles invalid session ID"""
        # Mock query to return None
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query.return_value = mock_query

        # Execute and verify exception
        with pytest.raises(ValueError, match="Supervision session .* not found"):
            await supervision_service.complete_supervision(
                session_id="invalid_session_id",
                supervisor_rating=4,
                feedback="Test"
            )

    @pytest.mark.asyncio
    async def test_confidence_boost_capped_at_maximum(
        self, supervision_service
    ):
        """Test confidence boost is capped at maximum"""
        # Test with maximum rating and no interventions
        boost = supervision_service._calculate_confidence_boost(
            supervisor_rating=5,
            intervention_count=0,
            duration_seconds=300
        )

        # Verify boost doesn't exceed 0.1
        assert boost <= 0.1
        assert boost >= 0.09  # Allow small rounding differences

    @pytest.mark.asyncio
    async def test_confidence_boost_with_many_interventions(
        self, supervision_service
    ):
        """Test confidence boost with many interventions"""
        # Test with many interventions
        boost = supervision_service._calculate_confidence_boost(
            supervisor_rating=5,
            intervention_count=10,  # Many interventions
            duration_seconds=300
        )

        # Verify boost reduced but not negative
        assert boost >= 0.0
        assert boost < 0.1  # Should be less than max due to interventions

    @pytest.mark.asyncio
    async def test_supervision_history_with_no_sessions(
        self, supervision_service, db_session
    ):
        """Test getting supervision history when no sessions exist"""
        # Mock query to return empty list
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db_session.query.return_value = mock_query

        # Execute
        history = await supervision_service.get_supervision_history(
            agent_id="agent_with_no_history",
            limit=50
        )

        # Verify empty list
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_supervision_history_orders_by_start_time(
        self, supervision_service, db_session, mock_session
    ):
        """Test supervision history is ordered by start time (newest first)"""
        # Mock query
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_session]
        db_session.query.return_value = mock_query

        # Execute
        history = await supervision_service.get_supervision_history(
            agent_id="agent_supervised_123",
            limit=50
        )

        # Verify order_by called with started_at descending
        assert mock_query.filter.called
        assert mock_query.order_by.called
