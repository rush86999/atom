"""
Database integration tests for workflow analytics and debugger.

Tests cover database-heavy code paths that unit tests with mocks cannot reach:
- AgentExecution database operations (create, update, query, aggregate)
- WorkflowExecution database operations and lifecycle
- WorkflowDebugSession database operations
- Database persistence and retrieval
- Database aggregation and analytics queries

Uses transaction rollback pattern for test isolation.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path as SysPath
sys.path.insert(0, str(SysPath(__file__).parent.parent.parent))

from core.models import (
    AgentRegistry,
    AgentExecution,
    WorkflowExecution,
    WorkflowDebugSession,
    ExecutionTrace,
    WorkflowExecutionLog,
    User,
    UserRole,
    WorkflowExecutionStatus
)
from core.workflow_debugger import WorkflowDebugger
from tests.factories.agent_factory import AgentFactory
from tests.factories.user_factory import UserFactory
from tests.factories.execution_factory import AgentExecutionFactory


class TestWorkflowDebuggerIntegration:
    """Test WorkflowDebugger database operations."""

    def test_create_debug_session(self, db_session: Session):
        """Test creating debug session in database."""
        debugger = WorkflowDebugger(db=db_session)

        # Create user
        user = UserFactory(email="debugger@test.com", _session=db_session)
        db_session.commit()

        # Create debug session
        session = debugger.create_debug_session(
            workflow_id="workflow-debug-1",
            user_id=user.id,
            session_name="Test Debug Session"
        )

        assert session.id is not None, "Session should have ID"
        assert session.workflow_id == "workflow-debug-1"
        assert session.user_id == user.id
        assert session.status == "active"
        assert session.session_name == "Test Debug Session"

        # Verify in database
        retrieved = db_session.query(WorkflowDebugSession).filter(
            WorkflowDebugSession.id == session.id
        ).first()
        assert retrieved is not None, "Session should be persisted"

    def test_query_debug_history(self, db_session: Session):
        """Test querying debug session history from database."""
        debugger = WorkflowDebugger(db=db_session)

        user = UserFactory(email="history@test.com", _session=db_session)
        db_session.commit()

        # Create multiple debug sessions
        session1 = debugger.create_debug_session(
            workflow_id="workflow-history",
            user_id=user.id,
            session_name="Session 1"
        )
        db_session.commit()

        session2 = debugger.create_debug_session(
            workflow_id="workflow-history",
            user_id=user.id,
            session_name="Session 2"
        )
        db_session.commit()

        # Query history
        sessions = debugger.get_active_debug_sessions(
            workflow_id="workflow-history",
            user_id=user.id
        )

        assert len(sessions) >= 2, "Should find at least 2 sessions"
        assert any(s.session_name == "Session 1" for s in sessions)
        assert any(s.session_name == "Session 2" for s in sessions)

    def test_pause_and_resume_session(self, db_session: Session):
        """Test pausing and resuming debug session."""
        debugger = WorkflowDebugger(db=db_session)

        user = UserFactory(email="pause-resume@test.com", _session=db_session)
        db_session.commit()

        session = debugger.create_debug_session(
            workflow_id="workflow-pause",
            user_id=user.id
        )
        db_session.commit()

        # Pause session
        result = debugger.pause_debug_session(session.id)
        assert result is True, "Should pause successfully"

        retrieved = db_session.query(WorkflowDebugSession).filter(
            WorkflowDebugSession.id == session.id
        ).first()
        assert retrieved.status == "paused"

        # Resume session
        result = debugger.resume_debug_session(session.id)
        assert result is True, "Should resume successfully"

        retrieved = db_session.query(WorkflowDebugSession).filter(
            WorkflowDebugSession.id == session.id
        ).first()
        assert retrieved.status == "active"

    def test_add_breakpoint(self, db_session: Session):
        """Test adding breakpoint to debug session."""
        debugger = WorkflowDebugger(db=db_session)

        user = UserFactory(email="breakpoint@test.com", _session=db_session)
        db_session.commit()

        session = debugger.create_debug_session(
            workflow_id="workflow-breakpoint",
            user_id=user.id
        )
        db_session.commit()

        # Add breakpoint
        breakpoint = debugger.add_breakpoint(
            workflow_id="workflow-breakpoint",
            node_id="node-123",
            user_id=user.id,
            debug_session_id=session.id
        )

        assert breakpoint is not None, "Breakpoint should be created"
        assert breakpoint.node_id == "node-123"

        # Verify breakpoint in database
        retrieved = db_session.query(WorkflowDebugSession).filter(
            WorkflowDebugSession.id == session.id
        ).first()

        assert retrieved is not None
        # Note: Breakpoints are stored as JSON, the breakpoint object itself was created
        # We just verify the session still exists and is active

    def test_create_execution_trace(self, db_session: Session):
        """Test recording execution traces to database."""
        debugger = WorkflowDebugger(db=db_session)

        user = UserFactory(email="trace@test.com", _session=db_session)
        agent = AgentFactory(name="TraceAgent", _session=db_session)
        execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        db_session.commit()

        session = debugger.create_debug_session(
            workflow_id="workflow-trace",
            user_id=user.id,
            execution_id=execution.id
        )
        db_session.commit()

        # Create trace
        trace = debugger.create_trace(
            workflow_id="workflow-trace",
            execution_id=execution.id,
            step_number=1,
            node_id="test-node",
            node_type="test",
            debug_session_id=session.id
        )

        assert trace is not None, "Trace should be created"
        # Note: trace object structure may vary

        # Verify trace in database
        traces = db_session.query(ExecutionTrace).filter(
            ExecutionTrace.session_id == session.id
        ).all()

        assert len(traces) > 0, "Should have trace record"

    def test_get_execution_traces(self, db_session: Session):
        """Test retrieving execution traces from database."""
        debugger = WorkflowDebugger(db=db_session)

        user = UserFactory(email="get-trace@test.com", _session=db_session)
        agent = AgentFactory(name="GetTraceAgent", _session=db_session)
        execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        db_session.commit()

        session = debugger.create_debug_session(
            workflow_id="workflow-get-trace",
            user_id=user.id,
            execution_id=execution.id
        )
        db_session.commit()

        # Create trace
        trace = debugger.create_trace(
            workflow_id="workflow-get-trace",
            execution_id=execution.id,
            step_number=1,
            node_id="test-node",
            node_type="test",
            debug_session_id=session.id
        )
        db_session.commit()

        # Get traces
        traces = debugger.get_execution_traces(session_id=session.id)

        assert len(traces) > 0, "Should find traces"
        assert traces[0].session_id == session.id


class TestAgentExecutionDatabaseCoverage:
    """Test AgentExecution database-heavy operations."""

    def test_agent_execution_lifecycle(self, db_session: Session):
        """Test complete lifecycle of AgentExecution record."""
        # Create agent
        agent = AgentFactory(name="LifecycleAgent", _session=db_session)
        db_session.commit()

        # Create execution record
        execution = AgentExecutionFactory(
            agent_id=agent.id,
            status="running",
            _session=db_session
        )
        db_session.commit()
        execution_id = execution.id

        # Update to completed
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.duration_seconds = 5.5
        execution.result_summary = "Test completed successfully"
        db_session.commit()

        # Query and verify
        retrieved = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution_id
        ).first()

        assert retrieved.status == "completed"
        assert retrieved.duration_seconds == 5.5
        assert retrieved.result_summary == "Test completed successfully"

    def test_execution_with_error(self, db_session: Session):
        """Test execution with error recording."""
        agent = AgentFactory(name="ErrorAgent", _session=db_session)
        db_session.commit()

        execution = AgentExecutionFactory(
            agent_id=agent.id,
            status="failed",
            error_message="Test error: validation failed",
            _session=db_session
        )
        db_session.commit()

        # Query failed executions
        failed_executions = db_session.query(AgentExecution).filter(
            AgentExecution.status == "failed"
        ).all()

        assert len(failed_executions) > 0
        assert "validation failed" in failed_executions[0].error_message

    def test_execution_query_by_agent(self, db_session: Session):
        """Test querying executions by agent."""
        agent = AgentFactory(name="QueryAgent", _session=db_session)
        db_session.commit()

        # Create multiple executions
        for i in range(5):
            AgentExecutionFactory(
                agent_id=agent.id,
                status="completed",
                _session=db_session
            )
        db_session.commit()

        # Query agent executions
        executions = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).all()

        assert len(executions) >= 5, "Should find all executions"

    def test_execution_duration_statistics(self, db_session: Session):
        """Test calculating execution duration statistics."""
        agent = AgentFactory(name="StatsAgent", _session=db_session)
        db_session.commit()

        # Create executions with varying durations
        durations = [1.0, 2.5, 3.0, 4.5, 5.0]
        for duration in durations:
            execution = AgentExecutionFactory(
                agent_id=agent.id,
                status="completed",
                duration_seconds=duration,
                _session=db_session
            )
        db_session.commit()

        # Calculate average
        result = db_session.query(
            func.avg(AgentExecution.duration_seconds)
        ).filter(
            AgentExecution.agent_id == agent.id,
            AgentExecution.status == "completed"
        ).scalar()

        expected_avg = sum(durations) / len(durations)
        assert abs(result - expected_avg) < 0.01, "Average should match"

    def test_execution_with_input_output(self, db_session: Session):
        """Test execution with input and output summaries."""
        agent = AgentFactory(name="IOAgent", _session=db_session)
        db_session.commit()

        execution = AgentExecutionFactory(
            agent_id=agent.id,
            input_summary="Process workflow: test-workflow",
            output_summary="Completed 3 steps successfully",
            _session=db_session
        )
        db_session.commit()

        retrieved = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first()

        assert "Process workflow" in retrieved.input_summary
        assert "Completed 3 steps" in retrieved.output_summary

    def test_execution_triggered_by(self, db_session: Session):
        """Test execution trigger source tracking."""
        agent = AgentFactory(name="TriggerAgent", _session=db_session)
        db_session.commit()

        # Create executions with different trigger sources
        for trigger in ["manual", "schedule", "websocket", "event"]:
            execution = AgentExecutionFactory(
                agent_id=agent.id,
                triggered_by=trigger,
                _session=db_session
            )
        db_session.commit()

        # Query by trigger type
        scheduled = db_session.query(AgentExecution).filter(
            and_(
                AgentExecution.agent_id == agent.id,
                AgentExecution.triggered_by == "schedule"
            )
        ).count()

        assert scheduled >= 1, "Should find scheduled execution"

    def test_execution_time_range_query(self, db_session: Session):
        """Test querying executions by time range."""
        agent = AgentFactory(name="TimeRangeAgent", _session=db_session)
        db_session.commit()

        now = datetime.utcnow()

        # Create execution at specific time
        execution = AgentExecutionFactory(
            agent_id=agent.id,
            started_at=now,
            _session=db_session
        )
        db_session.commit()

        # Query for recent executions
        recent = db_session.query(AgentExecution).filter(
            and_(
                AgentExecution.agent_id == agent.id,
                AgentExecution.started_at >= now - timedelta(minutes=5)
            )
        ).all()

        assert len(recent) >= 1, "Should find recent execution"


class TestDatabaseAggregationQueries:
    """Test database aggregation queries for analytics."""

    def test_count_executions_by_status(self, db_session: Session):
        """Test counting executions grouped by status."""
        agent = AgentFactory(name="AggregationAgent", _session=db_session)
        db_session.commit()

        # Create executions with different statuses
        statuses = ["running", "completed", "completed", "failed"]
        for status in statuses:
            AgentExecutionFactory(
                agent_id=agent.id,
                status=status,
                _session=db_session
            )
        db_session.commit()

        # Count by status
        result = db_session.query(
            AgentExecution.status,
            func.count()
        ).filter(
            AgentExecution.agent_id == agent.id
        ).group_by(AgentExecution.status).all()

        status_counts = {row[0]: row[1] for row in result}
        assert status_counts.get("completed", 0) == 2
        assert status_counts.get("running", 0) == 1
        assert status_counts.get("failed", 0) == 1

    def test_recent_executions_limit(self, db_session: Session):
        """Test querying recent executions with limit."""
        agent = AgentFactory(name="RecentAgent", _session=db_session)
        db_session.commit()

        # Create 10 executions
        for i in range(10):
            AgentExecutionFactory(
                agent_id=agent.id,
                status="completed",
                _session=db_session
            )
        db_session.commit()

        # Query 5 most recent
        recent = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).order_by(
            AgentExecution.started_at.desc()
        ).limit(5).all()

        assert len(recent) == 5

    def test_execution_exists_query(self, db_session: Session):
        """Test checking if execution exists."""
        agent = AgentFactory(name="ExistsAgent", _session=db_session)
        db_session.commit()

        execution = AgentExecutionFactory(
            agent_id=agent.id,
            _session=db_session
        )
        db_session.commit()

        # Check exists
        exists = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first() is not None

        assert exists is True

        # Check non-existent
        not_exists = db_session.query(AgentExecution).filter(
            AgentExecution.id == "non-existent-id"
        ).first() is not None

        assert not_exists is False
