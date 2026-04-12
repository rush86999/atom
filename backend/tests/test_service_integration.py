"""
Service Integration Tests

Tests integration scenarios between multiple services.
Covers complex workflows where services interact to complete tasks.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache
from core.models import (
    AgentRegistry, AgentExecution, AgentOperationTracker,
    Episode, EpisodeSegment, CanvasAudit, BrowserSession
)
from core.llm.llm_service import LLMService
from core.workflow_engine import WorkflowEngine
from core.episode_segmentation_service import EpisodeSegmentationService
from tools.canvas_tool import CanvasTool
from tools.browser_tool import BrowserTool


class TestAgentLLMIntegration:
    """Test agent and LLM service integration."""

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

    def test_agent_using_llm_for_response_generation(self, mock_db):
        """Test agent using LLM service to generate responses."""
        agent = AgentRegistry(
            id="agent-llm-001",
            name="LLM Agent",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            config={"model": "gpt-4", "temperature": 0.7},
            is_active=True
        )

        execution = AgentExecution(
            id="exec-llm-001",
            agent_id=agent.id,
            status="running",
            input_data={"task": "Generate response"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Agent calls LLM service
        llm_response = {
            "content": "Here is the generated response based on your request.",
            "model": "gpt-4",
            "tokens_used": 150,
            "finish_reason": "stop"
        }

        execution.output_data = {
            "response": llm_response["content"],
            "metadata": {
                "model": llm_response["model"],
                "tokens": llm_response["tokens_used"]
            }
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.output_data["response"] is not None
        assert execution.output_data["metadata"]["tokens"] == 150

    def test_agent_streaming_llm_response(self, mock_db):
        """Test agent streaming LLM response in chunks."""
        agent = AgentRegistry(
            id="agent-stream-001",
            name="Streaming Agent",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        execution = AgentExecution(
            id="exec-stream-001",
            agent_id=agent.id,
            status="running",
            input_data={"task": "Stream response", "stream": True},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Stream chunks
        chunks = ["Hello", " there", "!", " How", " can", " I", " help?"]
        full_response = ""

        for i, chunk in enumerate(chunks):
            operation = AgentOperationTracker(
                execution_id=execution.id,
                operation_type="streaming",
                status="in_progress",
                progress=(i + 1) / len(chunks),
                metadata={"chunk": chunk, "chunk_index": i}
            )
            mock_db.add(operation)
            full_response += chunk

        # Complete streaming
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {"full_response": full_response, "chunks": len(chunks)}
        mock_db.commit()

        assert execution.output_data["full_response"] == "Hello there! How can I help?"
        assert execution.output_data["chunks"] == 7


class TestAgentWorkflowIntegration:
    """Test agent and workflow engine integration."""

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

    def test_agent_executing_workflow(self, mock_db):
        """Test agent executing a workflow blueprint."""
        agent = AgentRegistry(
            id="agent-wf-001",
            name="Workflow Agent",
            agent_type="workflow_agent",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        execution = AgentExecution(
            id="exec-wf-001",
            agent_id=agent.id,
            status="running",
            input_data={
                "task": "Execute workflow",
                "workflow_id": "daily_report",
                "parameters": {"date": "2026-04-12"}
            },
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Workflow steps
        steps = [
            {"name": "fetch_data", "status": "completed", "duration_ms": 500},
            {"name": "process_data", "status": "completed", "duration_ms": 1200},
            {"name": "generate_report", "status": "completed", "duration_ms": 800}
        ]

        for step in steps:
            operation = AgentOperationTracker(
                execution_id=execution.id,
                operation_type="workflow_step",
                status="completed",
                metadata=step
            )
            mock_db.add(operation)

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {
            "workflow_completed": True,
            "steps_executed": len(steps),
            "total_duration_ms": sum(s["duration_ms"] for s in steps)
        }
        mock_db.commit()

        assert execution.output_data["workflow_completed"] is True
        assert execution.output_data["steps_executed"] == 3

    def test_agent_handling_workflow_errors(self, mock_db):
        """Test agent handling workflow execution errors."""
        agent = AgentRegistry(
            id="agent-wf-error-001",
            name="Error Handling Agent",
            agent_type="workflow_agent",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        execution = AgentExecution(
            id="exec-wf-error-001",
            agent_id=agent.id,
            status="running",
            input_data={"task": "Execute workflow with error"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Workflow step fails
        failed_operation = AgentOperationTracker(
            execution_id=execution.id,
            operation_type="workflow_step",
            status="failed",
            metadata={
                "step_name": "validate_input",
                "error": "Invalid input format",
                "retryable": True
            }
        )
        mock_db.add(failed_operation)

        # Agent implements retry
        retry_operation = AgentOperationTracker(
            execution_id=execution.id,
            operation_type="workflow_step",
            status="completed",
            metadata={
                "step_name": "validate_input",
                "retry_attempt": 1,
                "success": True
            }
        )
        mock_db.add(retry_operation)

        # Continue workflow
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {"result": "Workflow completed after retry"}
        mock_db.commit()

        assert execution.status == "completed"


class TestAgentEpisodeIntegration:
    """Test agent and episode service integration."""

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

    def test_agent_creating_episode_during_execution(self, mock_db):
        """Test agent creating episode during execution."""
        agent = AgentRegistry(
            id="agent-ep-001",
            name="Episode Agent",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        execution = AgentExecution(
            id="exec-ep-001",
            agent_id=agent.id,
            status="running",
            input_data={"task": "Multi-step conversation"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Agent creates episode
        episode = Episode(
            id="episode-001",
            agent_id=agent.id,
            session_id=execution.id,
            title="Customer Support Conversation",
            summary="Agent helped user with account issue",
            status="active",
            started_at=datetime.utcnow(),
            metadata={"execution_id": execution.id}
        )
        mock_db.add(episode)

        # Add conversation segments
        for i in range(3):
            segment = EpisodeSegment(
                id=f"segment-{i:03d}",
                episode_id=episode.id,
                segment_type="conversation",
                content=f"Turn {i+1} conversation",
                timestamp=datetime.utcnow() - timedelta(minutes=5-i),
                metadata={"turn": i+1, "speaker": "user" if i % 2 == 0 else "agent"}
            )
            mock_db.add(segment)

        mock_db.commit()

        # Complete execution and episode
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {"episode_id": episode.id}
        episode.status = "completed"
        episode.ended_at = datetime.utcnow()
        mock_db.commit()

        assert episode.id is not None
        assert execution.output_data["episode_id"] == episode.id

    def test_agent_using_episode_context(self, mock_db):
        """Test agent using episode context for better responses."""
        agent = AgentRegistry(
            id="agent-ep-ctx-001",
            name="Context-Aware Agent",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        # Previous episode exists
        previous_episode = Episode(
            id="episode-002",
            agent_id=agent.id,
            session_id="session-002",
            title="Previous Conversation",
            summary="User asked about pricing",
            status="completed",
            started_at=datetime.utcnow() - timedelta(days=1),
            ended_at=datetime.utcnow() - timedelta(days=1),
            metadata={"user_preference": "prefers annual plans"}
        )
        mock_db.add(previous_episode)

        # New execution uses episode context
        execution = AgentExecution(
            id="exec-ep-ctx-001",
            agent_id=agent.id,
            status="running",
            input_data={
                "task": "Recommend plan",
                "context_episode_id": previous_episode.id
            },
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Agent uses context to provide personalized response
        execution.output_data = {
            "recommendation": "Annual plan (based on your preference)",
            "context_used": previous_episode.id
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert "Annual plan" in execution.output_data["recommendation"]


class TestAgentCanvasIntegration:
    """Test agent and canvas service integration."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = db.rollback = Mock()
        db.refresh = Mock()
        return db

    def test_agent_presenting_multiple_canvases(self, mock_db):
        """Test agent presenting multiple canvases in sequence."""
        agent = AgentRegistry(
            id="agent-canvas-001",
            name="Canvas Agent",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        execution = AgentExecution(
            id="exec-canvas-001",
            agent_id=agent.id,
            status="running",
            input_data={"task": "Present data visualization"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Present multiple canvases
        canvases = [
            {"type": "bar_chart", "title": "Q1 Sales"},
            {"type": "line_chart", "title": "Sales Trend"},
            {"type": "pie_chart", "title": "Market Share"}
        ]

        for i, canvas_config in enumerate(canvases):
            canvas = CanvasAudit(
                id=f"canvas-{i:03d}",
                canvas_id=f"canvas-{i}",
                canvas_type=canvas_config["type"],
                agent_id=agent.id,
                execution_id=execution.id,
                presented_at=datetime.utcnow() + timedelta(seconds=i*2),
                canvas_data=canvas_config,
                status="presented"
            )
            mock_db.add(canvas)

        mock_db.commit()

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {"canvases_presented": len(canvases)}
        mock_db.commit()

        assert execution.output_data["canvases_presented"] == 3

    def test_agent_collecting_canvas_input(self, mock_db):
        """Test agent collecting input through canvas form."""
        agent = AgentRegistry(
            id="agent-form-001",
            name="Form Agent",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        execution = AgentExecution(
            id="exec-form-001",
            agent_id=agent.id,
            status="running",
            input_data={"task": "Collect user information"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Present form
        form_canvas = CanvasAudit(
            id="form-001",
            canvas_id="user-form",
            canvas_type="interactive_form",
            agent_id=agent.id,
            execution_id=execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "fields": [
                    {"name": "name", "type": "text", "required": True},
                    {"name": "email", "type": "email", "required": True}
                ]
            },
            status="presented"
        )
        mock_db.add(form_canvas)

        # User submits form
        submission = CanvasAudit(
            id="form-submit-001",
            canvas_id="user-form",
            canvas_type="interactive_form",
            agent_id=agent.id,
            execution_id=execution.id,
            presented_at=datetime.utcnow() + timedelta(seconds=30),
            canvas_data={
                "values": {
                    "name": "John Doe",
                    "email": "john@example.com"
                },
                "submitted": True
            },
            status="submitted"
        )
        mock_db.add(submission)

        # Agent processes submission
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {
            "user_info": submission.canvas_data["values"],
            "confirmation": "Information collected successfully"
        }
        mock_db.commit()

        assert execution.output_data["user_info"]["name"] == "John Doe"


class TestAgentToolIntegration:
    """Test agent and tool service integration."""

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

    def test_agent_using_browser_tool(self, mock_db):
        """Test agent using browser tool for web automation."""
        agent = AgentRegistry(
            id="agent-browser-001",
            name="Browser Agent",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        execution = AgentExecution(
            id="exec-browser-001",
            agent_id=agent.id,
            status="running",
            input_data={"task": "Scrape website data"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Create browser session
        browser_session = BrowserSession(
            id="browser-001",
            execution_id=execution.id,
            url="https://example.com",
            status="active",
            started_at=datetime.utcnow()
        )
        mock_db.add(browser_session)

        # Browser operations
        operations = [
            {"action": "navigate", "url": "https://example.com"},
            {"action": "wait_for_selector", "selector": ".data"},
            {"action": "extract_text", "selector": ".data"}
        ]

        for op in operations:
            operation = AgentOperationTracker(
                execution_id=execution.id,
                operation_type="browser_operation",
                status="completed",
                metadata=op
            )
            mock_db.add(operation)

        # Complete browser session
        browser_session.status = "completed"
        browser_session.screenshot_data = "screenshot_base64"
        execution.output_data = {
            "scraped_data": "Extracted data from website",
            "screenshot": browser_session.screenshot_data
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.output_data["scraped_data"] is not None

    def test_agent_coordinating_multiple_tools(self, mock_db):
        """Test agent coordinating multiple tools in sequence."""
        agent = AgentRegistry(
            id="agent-multi-tool-001",
            name="Multi-Tool Agent",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        execution = AgentExecution(
            id="exec-multi-tool-001",
            agent_id=agent.id,
            status="running",
            input_data={"task": "Complex multi-tool workflow"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Tool 1: Browser
        browser_op = AgentOperationTracker(
            execution_id=execution.id,
            operation_type="browser_tool",
            status="completed",
            metadata={"action": "scrape", "url": "https://example.com"}
        )
        mock_db.add(browser_op)

        # Tool 2: Calendar
        calendar_op = AgentOperationTracker(
            execution_id=execution.id,
            operation_type="calendar_tool",
            status="completed",
            metadata={"action": "create_event", "title": "Meeting"}
        )
        mock_db.add(calendar_op)

        # Tool 3: Canvas
        canvas_op = AgentOperationTracker(
            execution_id=execution.id,
            operation_type="canvas_tool",
            status="completed",
            metadata={"action": "present_chart", "type": "bar_chart"}
        )
        mock_db.add(canvas_op)

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {
            "tools_used": ["browser", "calendar", "canvas"],
            "workflow_completed": True
        }
        mock_db.commit()

        assert len(execution.output_data["tools_used"]) == 3


class TestGovernanceWorkflowIntegration:
    """Test governance integrated with workflow execution."""

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

    def test_workflow_with_governance_checks_at_each_step(self, mock_db):
        """Test workflow with governance verification at each step."""
        from core.models import BlockedTriggerContext

        supervised_agent = AgentRegistry(
            id="agent-gov-wf-001",
            name="Supervised Workflow Agent",
            agent_type="workflow_agent",
            maturity_level="SUPERVISED",
            is_active=True
        )

        mock_db.query.return_value.filter.return_value.first.return_value = supervised_agent

        execution = AgentExecution(
            id="exec-gov-wf-001",
            agent_id=supervised_agent.id,
            status="running",
            input_data={"task": "Execute governed workflow"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Step 1: Low complexity (allowed)
        step1 = AgentOperationTracker(
            execution_id=execution.id,
            operation_type="workflow_step",
            status="completed",
            metadata={"step": "present_data", "complexity": 1, "governance": "passed"}
        )
        mock_db.add(step1)

        # Step 2: Medium complexity (allowed for SUPERVISED)
        step2 = AgentOperationTracker(
            execution_id=execution.id,
            operation_type="workflow_step",
            status="completed",
            metadata={"step": "update_state", "complexity": 3, "governance": "passed"}
        )
        mock_db.add(step2)

        # Step 3: High complexity (would require AUTONOMOUS)
        # Simulate governance check blocking this step
        blocked = BlockedTriggerContext(
            id="blocked-wf-001",
            agent_id=supervised_agent.id,
            trigger_type="workflow_step",
            trigger_source="workflow_engine",
            attempted_at=datetime.utcnow(),
            block_reason="Step complexity 4 requires AUTONOMOUS maturity",
            maturity_level=supervised_agent.maturity_level
        )
        mock_db.add(blocked)

        execution.status = "blocked"
        execution.error_message = "Workflow blocked: insufficient maturity for critical steps"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.status == "blocked"
        assert "insufficient maturity" in execution.error_message


class TestEpisodeCanvasIntegration:
    """Test episode and canvas integration for tracking."""

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

    def test_episode_tracking_canvas_presentations(self, mock_db):
        """Test episode tracking canvas presentations."""
        episode = Episode(
            id="episode-canvas-001",
            agent_id="agent-001",
            session_id="session-001",
            title="Canvas-Heavy Episode",
            summary="Episode with multiple canvas presentations",
            status="active",
            started_at=datetime.utcnow()
        )
        mock_db.add(episode)

        # Track canvas presentations in episode
        for i in range(3):
            canvas_segment = EpisodeSegment(
                id=f"seg-canvas-{i:03d}",
                episode_id=episode.id,
                segment_type="canvas_presentation",
                content=f"Presented {['bar_chart', 'line_chart', 'pie_chart'][i]}",
                timestamp=datetime.utcnow() + timedelta(seconds=i*10),
                metadata={
                    "canvas_type": ['bar_chart', 'line_chart', 'pie_chart'][i],
                    "canvas_id": f"canvas-{i}",
                    "user_interaction": "viewed"
                }
            )
            mock_db.add(canvas_segment)

        mock_db.commit()

        # Verify canvas tracking in episode
        mock_db.query.return_value.filter.return_value.all.return_value = [
            EpisodeSegment(segment_type="canvas_presentation"),
            EpisodeSegment(segment_type="canvas_presentation"),
            EpisodeSegment(segment_type="canvas_presentation")
        ]

        canvas_segments = mock_db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id,
            EpisodeSegment.segment_type == "canvas_presentation"
        ).all()

        assert len(canvas_segments) == 3
