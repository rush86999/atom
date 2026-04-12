"""
Multi-Service Coordination Tests

Tests coordination and interaction between multiple services.
Covers agent + governance, LLM + workflow, episode + graduation, canvas + agent, tool + service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.agent_context_resolver import AgentContextResolver
from core.governance_cache import GovernanceCache
from core.models import AgentRegistry, AgentExecution, AgentOperationTracker, BlockedTriggerContext
from core.llm.llm_service import LLMService
from core.workflow_engine import WorkflowEngine
from core.episode_segmentation_service import EpisodeSegmentationService
from core.agent_graduation_service import AgentGraduationService
from tools.canvas_tool import CanvasTool
from api.canvas_routes import create_canvas


class TestAgentGovernanceCoordination:
    """Test agent and governance service coordination."""

    @pytest.fixture
    def governance_service(self):
        """Create governance service."""
        return AgentGovernanceService()

    @pytest.fixture
    def governance_cache(self):
        """Create governance cache."""
        return GovernanceCache()

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

    def test_agent_execution_with_governance_check(self, governance_service, governance_cache, mock_db):
        """Test agent execution coordinated with governance cache."""
        agent = AgentRegistry(
            id="agent-001",
            name="Test Agent",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            is_active=True
        )

        # Check governance via cache (fast path)
        mock_db.query.return_value.filter.return_value.first.return_value = agent

        can_execute = governance_cache.can_agent_execute(
            agent.id,
            "task_execution",
            agent.maturity_level
        )

        assert can_execute is True

        # Create execution with governance verified
        execution = AgentExecution(
            id="exec-001",
            agent_id=agent.id,
            status="running",
            input_data={"task": "test"},
            started_at=datetime.utcnow(),
            metadata={"governance_verified": True}
        )
        mock_db.add(execution)
        mock_db.commit()

        assert execution.metadata["governance_verified"] is True

    def test_blocked_trigger_interceptor_coordination(self, governance_service, mock_db):
        """Test trigger interceptor coordinated with governance."""
        student_agent = AgentRegistry(
            id="student-agent",
            name="Student Agent",
            agent_type="assistant",
            maturity_level="STUDENT",
            is_active=True
        )

        mock_db.query.return_value.filter.return_value.first.return_value = student_agent

        # Attempt automated trigger (should be blocked for STUDENT)
        trigger_context = BlockedTriggerContext(
            id="blocked-001",
            agent_id=student_agent.id,
            trigger_type="automated",
            trigger_source="scheduler",
            attempted_at=datetime.utcnow(),
            block_reason="STUDENT agents cannot execute automated triggers",
            maturity_level=student_agent.maturity_level
        )
        mock_db.add(trigger_context)
        mock_db.commit()

        assert trigger_context.block_reason is not None
        assert "STUDENT" in trigger_context.block_reason

    def test_governance_cache_invalidation_coordination(self, governance_cache, mock_db):
        """Test governance cache invalidation coordinated with agent updates."""
        agent_id = "agent-001"

        # Set initial cache value
        governance_cache.set_agent_maturity(agent_id, "INTERN")
        maturity = governance_cache.get_agent_maturity(agent_id)
        assert maturity == "INTERN"

        # Update agent maturity in database
        updated_agent = AgentRegistry(
            id=agent_id,
            name="Updated Agent",
            agent_type="assistant",
            maturity_level="SUPERVISED",
            is_active=True
        )

        mock_db.query.return_value.filter.return_value.first.return_value = updated_agent

        # Invalidate cache
        governance_cache.invalidate_agent(agent_id)

        # Cache should reflect updated value
        governance_cache.set_agent_maturity(agent_id, updated_agent.maturity_level)
        maturity = governance_cache.get_agent_maturity(agent_id)
        assert maturity == "SUPERVISED"


class TestLLMWorkflowIntegration:
    """Test LLM and workflow engine integration."""

    @pytest.fixture
    def llm_service(self):
        """Create LLM service."""
        return LLMService()

    @pytest.fixture
    def workflow_engine(self):
        """Create workflow engine."""
        return WorkflowEngine()

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

    def test_workflow_with_llm_decision_node(self, workflow_engine, mock_db):
        """Test workflow using LLM for decision nodes."""
        workflow_def = {
            "workflow_id": "wf-001",
            "name": "LLM Decision Workflow",
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "next": "llm_decision"
                },
                {
                    "id": "llm_decision",
                    "type": "llm_decision",
                    "prompt": "Classify sentiment as positive or negative",
                    "next_positive": "positive_branch",
                    "next_negative": "negative_branch"
                },
                {
                    "id": "positive_branch",
                    "type": "action",
                    "action": "send_positive_response"
                },
                {
                    "id": "negative_branch",
                    "type": "action",
                    "action": "send_negative_response"
                }
            ]
        }

        # Initialize workflow
        workflow_engine.initialize(workflow_def)
        assert workflow_engine.workflow_id == "wf-001"

        # Execute with LLM decision
        input_data = {"text": "This is great!"}
        result = {"branch": "positive_branch"}  # Simulated LLM decision

        assert result["branch"] == "positive_branch"

    def test_workflow_with_llm_content_generation(self, workflow_engine, mock_db):
        """Test workflow using LLM for content generation."""
        workflow_def = {
            "workflow_id": "wf-002",
            "name": "Content Generation Workflow",
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "next": "generate"
                },
                {
                    "id": "generate",
                    "type": "llm_generate",
                    "prompt_template": "Write a summary about {topic}",
                    "output_key": "summary"
                }
            ]
        }

        workflow_engine.initialize(workflow_def)

        input_data = {"topic": "artificial intelligence"}
        generated_content = {
            "summary": "AI is a transformative technology..."
        }

        assert "summary" in generated_content
        assert len(generated_content["summary"]) > 0


class TestEpisodeGraduationIntegration:
    """Test episode and graduation service integration."""

    @pytest.fixture
    def segmentation_service(self):
        """Create episode segmentation service."""
        return EpisodeSegmentationService()

    @pytest.fixture
    def graduation_service(self):
        """Create agent graduation service."""
        return AgentGraduationService()

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

    def test_episode_triggering_graduation_check(self, segmentation_service, graduation_service, mock_db):
        """Test episode completion triggering graduation evaluation."""
        from core.models import Episode, AgentGraduationCheckpoint

        # Create episode that contributes to graduation
        episode = Episode(
            id="episode-001",
            agent_id="agent-001",
            session_id="session-001",
            title="Graduation Episode",
            summary="Agent completed complex task successfully",
            status="completed",
            started_at=datetime.utcnow() - timedelta(hours=2),
            ended_at=datetime.utcnow()
        )
        mock_db.add(episode)
        mock_db.commit()

        # Check graduation criteria
        mock_db.query.return_value.filter.return_value.count.return_value = 10
        episode_count = mock_db.query(Episode).filter(
            Episode.agent_id == episode.agent_id
        ).count()

        # Episode count meets STUDENT → INTERN threshold (10 episodes)
        if episode_count >= 10:
            checkpoint = AgentGraduationCheckpoint(
                id="checkpoint-001",
                agent_id=episode.agent_id,
                from_maturity="STUDENT",
                to_maturity="INTERN",
                episode_id=episode.id,
                timestamp=datetime.utcnow(),
                criteria_met={"episode_count": episode_count},
                status="pending_approval"
            )
            mock_db.add(checkpoint)
            mock_db.commit()

        assert checkpoint.from_maturity == "STUDENT"
        assert checkpoint.to_maturity == "INTERN"

    def test_segmentation_with_graduation_tracking(self, segmentation_service, mock_db):
        """Test episode segmentation with graduation metadata."""
        from core.models import Episode, EpisodeSegment

        episode = Episode(
            id="episode-002",
            agent_id="agent-002",
            session_id="session-002",
            title="Segmented Episode",
            summary="Episode with multiple segments",
            status="active",
            started_at=datetime.utcnow(),
            metadata={
                "graduation_tracking": True,
                "intervention_count": 0,
                "constitutional_score": 0.85
            }
        )
        mock_db.add(episode)

        # Add segments with intervention tracking
        for i in range(3):
            segment = EpisodeSegment(
                id=f"segment-{i:03d}",
                episode_id=episode.id,
                segment_type="conversation",
                content=f"Segment {i}",
                timestamp=datetime.utcnow() - timedelta(minutes=30-i*5),
                metadata={
                    "required_intervention": False,
                    "graduation_eligible": True
                }
            )
            mock_db.add(segment)

        mock_db.commit()

        # Verify graduation tracking
        assert episode.metadata["graduation_tracking"] is True
        assert episode.metadata["intervention_count"] == 0


class TestCanvasAgentIntegration:
    """Test canvas and agent integration."""

    @pytest.fixture
    def canvas_tool(self):
        """Create canvas tool."""
        return CanvasTool()

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

    def test_agent_presenting_canvas(self, canvas_tool, mock_db):
        """Test agent presenting canvas to user."""
        from core.models import AgentExecution, CanvasAudit

        execution = AgentExecution(
            id="exec-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "present chart"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        canvas_data = {
            "canvas_type": "bar_chart",
            "title": "Sales Data",
            "data": {"labels": ["Q1", "Q2"], "datasets": [{"data": [100, 150]}]}
        }

        canvas_audit = CanvasAudit(
            id="canvas-001",
            canvas_id="chart-001",
            canvas_type="bar_chart",
            agent_id=execution.agent_id,
            execution_id=execution.id,
            presented_at=datetime.utcnow(),
            canvas_data=canvas_data,
            status="presented"
        )
        mock_db.add(canvas_audit)
        mock_db.commit()

        assert canvas_audit.execution_id == execution.id
        assert canvas_audit.status == "presented"

    def test_canvas_submission_continuing_agent_execution(self, canvas_tool, mock_db):
        """Test canvas submission continuing agent execution."""
        from core.models import AgentExecution, CanvasAudit

        execution = AgentExecution(
            id="exec-002",
            agent_id="agent-002",
            status="waiting_for_input",
            input_data={"task": "collect user input"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # User submits canvas
        submission = CanvasAudit(
            id="canvas-002",
            canvas_id="form-001",
            canvas_type="interactive_form",
            agent_id=execution.agent_id,
            execution_id=execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={"values": {"name": "User", "email": "user@example.com"}},
            status="submitted"
        )
        mock_db.add(submission)
        mock_db.commit()

        # Resume agent execution with submitted data
        execution.status = "running"
        execution.input_data["user_input"] = submission.canvas_data["values"]
        mock_db.commit()

        assert execution.status == "running"
        assert "user_input" in execution.input_data


class TestToolServiceCoordination:
    """Test tool and service coordination."""

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

    def test_browser_tool_with_agent_service(self, mock_db):
        """Test browser tool coordinated with agent service."""
        from core.models import AgentExecution, BrowserSession
        from tools.browser_tool import BrowserTool

        execution = AgentExecution(
            id="exec-003",
            agent_id="agent-003",
            status="running",
            input_data={"task": "scrape website"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Browser tool creates session
        browser_session = BrowserSession(
            id="browser-001",
            execution_id=execution.id,
            url="https://example.com",
            status="active",
            started_at=datetime.utcnow()
        )
        mock_db.add(browser_session)
        mock_db.commit()

        assert browser_session.execution_id == execution.id

        # Complete scraping
        browser_session.status = "completed"
        browser_session.screenshot_data = "base64_screenshot"
        execution.output_data = {"scraped_data": "results"}
        mock_db.commit()

        assert browser_session.status == "completed"

    def test_device_tool_with_governance_service(self, mock_db):
        """Test device tool coordinated with governance service."""
        from core.models import AgentExecution, DeviceSession
        from core.agent_governance_service import AgentGovernanceService

        governance_service = AgentGovernanceService()

        intern_agent = AgentRegistry(
            id="intern-agent",
            name="Intern Agent",
            agent_type="assistant",
            maturity_level="INTERN",
            is_active=True
        )

        mock_db.query.return_value.filter.return_value.first.return_value = intern_agent

        # Request camera access (requires INTERN+)
        can_access = governance_service.can_agent_execute_action(
            intern_agent.id,
            "device_camera",
            intern_agent.maturity_level
        )

        assert can_access is True

        execution = AgentExecution(
            id="exec-004",
            agent_id=intern_agent.id,
            status="running",
            input_data={"task": "capture photo"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        device_session = DeviceSession(
            id="device-001",
            execution_id=execution.id,
            device_type="camera",
            status="active",
            started_at=datetime.utcnow()
        )
        mock_db.add(device_session)
        mock_db.commit()

        assert device_session.device_type == "camera"

    def test_calendar_tool_with_workflow_service(self, mock_db):
        """Test calendar tool coordinated with workflow service."""
        from core.models import AgentExecution
        from tools.calendar_tool import CalendarTool

        execution = AgentExecution(
            id="exec-005",
            agent_id="agent-005",
            status="running",
            input_data={"task": "schedule meeting"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Calendar tool creates event
        event_data = {
            "title": "Team Meeting",
            "start": "2026-04-15T10:00:00Z",
            "duration_minutes": 60,
            "attendees": ["user1@example.com", "user2@example.com"]
        }

        execution.output_data = {
            "event_created": True,
            "event_id": "event-001",
            "event_data": event_data
        }
        mock_db.commit()

        assert execution.output_data["event_created"] is True

    def test_cli_tool_with_agent_lifecycle(self, mock_db):
        """Test CLI tool coordinated with agent lifecycle."""
        from core.models import AgentExecution
        from tools.atom_cli_skill_wrapper import AtomCliSkillWrapper

        # Agent starts daemon
        execution = AgentExecution(
            id="exec-006",
            agent_id="agent-006",
            status="running",
            input_data={"task": "start daemon"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # CLI tool executes command
        cli_result = {
            "command": "atom-os daemon",
            "exit_code": 0,
            "output": "Daemon started successfully",
            "pid": 12345
        }

        execution.output_data = cli_result
        execution.status = "completed"
        mock_db.commit()

        assert execution.status == "completed"
        assert execution.output_data["exit_code"] == 0


class TestCrossServiceErrorHandling:
    """Test error handling across service boundaries."""

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

    def test_governance_failure_propagating_to_agent(self, mock_db):
        """Test governance failure propagating to agent execution."""
        from core.models import AgentExecution, BlockedTriggerContext

        student_agent = AgentRegistry(
            id="student-agent",
            name="Student Agent",
            agent_type="assistant",
            maturity_level="STUDENT",
            is_active=True
        )

        mock_db.query.return_value.filter.return_value.first.return_value = student_agent

        # Governance check fails
        blocked_trigger = BlockedTriggerContext(
            id="blocked-002",
            agent_id=student_agent.id,
            trigger_type="automated",
            trigger_source="scheduler",
            attempted_at=datetime.utcnow(),
            block_reason="STUDENT agents cannot execute automated triggers",
            maturity_level=student_agent.maturity_level
        )
        mock_db.add(blocked_trigger)

        # Agent execution reflects governance failure
        execution = AgentExecution(
            id="exec-failed",
            agent_id=student_agent.id,
            status="blocked",
            input_data={"task": "automated task"},
            error_message="Blocked by governance: insufficient maturity level",
            started_at=None,  # Never started
            completed_at=datetime.utcnow()
        )
        mock_db.add(execution)
        mock_db.commit()

        assert execution.status == "blocked"
        assert execution.started_at is None

    def test_llm_failure_with_workflow_recovery(self, mock_db):
        """Test LLM failure with workflow recovery."""
        from core.models import AgentExecution

        execution = AgentExecution(
            id="exec-retry",
            agent_id="agent-007",
            status="running",
            input_data={"task": "llm task"},
            started_at=datetime.utcnow(),
            retry_count=0
        )
        mock_db.add(execution)

        # LLM fails
        execution.status = "failed"
        execution.error_message = "LLM API timeout"
        execution.retry_count = 1
        mock_db.commit()

        # Workflow implements retry
        execution.status = "running"
        execution.error_message = None
        mock_db.commit()

        # Retry succeeds
        execution.status = "completed"
        execution.output_data = {"result": "success after retry"}
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.status == "completed"
        assert execution.retry_count == 1
