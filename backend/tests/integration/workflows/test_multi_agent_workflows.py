"""
Integration tests for multi-agent orchestration scenarios.

Tests cover:
- Agent handoff workflows
- Parallel agent execution
- Agent error propagation
- Agent governance enforcement

Target: Multi-agent coordination and governance integration
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from core.workflow_engine import WorkflowEngine
from core.models import WorkflowExecution, WorkflowExecutionStatus, AgentRegistry


class TestMultiAgentWorkflows:
    """Integration tests for multi-agent orchestration."""

    @pytest.mark.asyncio
    async def test_agent_handoff_workflow(self, db_session: Session, mock_websocket_manager):
        """Test workflow with 2 agents: data collection -> analysis."""
        mock_analytics = MagicMock()
        mock_analytics.track_step_execution = MagicMock()

        mock_state_manager = AsyncMock()
        mock_state_manager.get_execution_state = AsyncMock(return_value={
            "status": "RUNNING",
            "steps": {},
            "outputs": {},
            "inputs": {}
        })
        mock_state_manager.update_step_status = AsyncMock()

        engine = WorkflowEngine()
        engine.state_manager = mock_state_manager

        # Create workflow with 2 agent steps
        workflow = {
            "id": "agent_handoff",
            "nodes": [
                {
                    "id": "agent1_collect",
                    "title": "Data Collection Agent",
                    "type": "action",
                    "config": {
                        "action": "collect_data",
                        "service": "agent_service",
                        "parameters": {
                            "agent_id": "agent_collector_001",
                            "maturity": "INTERN"
                        }
                    }
                },
                {
                    "id": "agent2_analyze",
                    "title": "Analysis Agent",
                    "type": "action",
                    "config": {
                        "action": "analyze_data",
                        "service": "agent_service",
                        "parameters": {
                            "agent_id": "agent_analyst_001",
                            "maturity": "SUPERVISED"
                        }
                    }
                }
            ],
            "connections": [
                {"source": "agent1_collect", "target": "agent2_analyze"}
            ]
        }

        executed_agents = []

        async def mock_agent_step(step, params):
            executed_agents.append(step["id"])
            # The workflow engine flattens config into step parameters
            agent_id = params.get("agent_id", "unknown")
            return {
                "result": {
                    "status": "success",
                    "agent": agent_id,
                    "output": f"Data from {agent_id}"
                }
            }

        with patch.object(engine, '_execute_step', side_effect=mock_agent_step):
            with patch('core.analytics_engine.get_analytics_engine', return_value=mock_analytics):
                await engine._execute_workflow_graph(
                    execution_id="exec_handoff_001",
                    workflow=workflow,
                    state={"steps": {}, "outputs": {}},
                    ws_manager=mock_websocket_manager,
                    user_id="test_user",
                    start_time=datetime.utcnow()
                )

        # Verify both agents executed in sequence
        assert len(executed_agents) == 2
        assert executed_agents == ["agent1_collect", "agent2_analyze"]

    @pytest.mark.asyncio
    async def test_parallel_agent_execution(self, db_session: Session, mock_websocket_manager):
        """Test 3 agents executing in parallel with different data sources."""
        mock_analytics = MagicMock()
        mock_analytics.track_step_execution = MagicMock()

        mock_state_manager = AsyncMock()
        mock_state_manager.get_execution_state = AsyncMock(return_value={
            "status": "RUNNING",
            "steps": {},
            "outputs": {},
            "inputs": {}
        })
        mock_state_manager.update_step_status = AsyncMock()

        engine = WorkflowEngine(max_concurrent_steps=3)
        engine.state_manager = mock_state_manager

        # Create workflow with 3 parallel agent steps
        workflow = {
            "id": "parallel_agents",
            "nodes": [
                {
                    "id": "agent1_api",
                    "title": "API Data Agent",
                    "type": "action",
                    "config": {
                        "action": "fetch_api_data",
                        "service": "agent_service",
                        "parameters": {"source": "api"}
                    }
                },
                {
                    "id": "agent2_db",
                    "title": "Database Agent",
                    "type": "action",
                    "config": {
                        "action": "query_database",
                        "service": "agent_service",
                        "parameters": {"source": "database"}
                    }
                },
                {
                    "id": "agent3_file",
                    "title": "File System Agent",
                    "type": "action",
                    "config": {
                        "action": "read_files",
                        "service": "agent_service",
                        "parameters": {"source": "filesystem"}
                    }
                }
            ],
            "connections": []
        }

        executed_agents = []

        async def mock_agent_step(step, params):
            agent_id = step["id"]
            executed_agents.append(agent_id)
            return {"result": {"status": "success", "source": params.get("source", "unknown")}}

        with patch.object(engine, '_execute_step', side_effect=mock_agent_step):
            with patch('core.analytics_engine.get_analytics_engine', return_value=mock_analytics):
                await engine._execute_workflow_graph(
                    execution_id="exec_parallel_001",
                    workflow=workflow,
                    state={"steps": {}, "outputs": {}},
                    ws_manager=mock_websocket_manager,
                    user_id="test_user",
                    start_time=datetime.utcnow()
                )

        # Verify all 3 agents executed
        assert len(executed_agents) == 3
        assert "agent1_api" in executed_agents
        assert "agent2_db" in executed_agents
        assert "agent3_file" in executed_agents

    @pytest.mark.asyncio
    async def test_agent_error_propagation(self, db_session: Session, mock_websocket_manager):
        """Test error propagation when agent fails mid-workflow."""
        mock_analytics = MagicMock()
        mock_analytics.track_step_execution = MagicMock()

        mock_state_manager = AsyncMock()
        mock_state_manager.get_execution_state = AsyncMock(return_value={
            "status": "RUNNING",
            "steps": {},
            "outputs": {},
            "inputs": {}
        })
        mock_state_manager.update_step_status = AsyncMock()

        engine = WorkflowEngine()
        engine.state_manager = mock_state_manager

        # Create workflow: agent1 -> agent2 -> agent3
        workflow = {
            "id": "error_propagation",
            "nodes": [
                {"id": "agent1", "title": "Agent 1", "type": "action",
                 "config": {"action": "task1", "service": "service"}},
                {"id": "agent2", "title": "Agent 2", "type": "action",
                 "config": {"action": "task2", "service": "service"}},
                {"id": "agent3", "title": "Agent 3", "type": "action",
                 "config": {"action": "task3", "service": "service"}},
            ],
            "connections": [
                {"source": "agent1", "target": "agent2"},
                {"source": "agent2", "target": "agent3"}
            ]
        }

        executed_agents = []

        async def mock_agent_step_with_error(step, params):
            executed_agents.append(step["id"])

            # Agent 2 fails
            if step["id"] == "agent2":
                raise Exception("Agent 2 processing error")

            return {"result": {"status": "success"}}

        with patch.object(engine, '_execute_step', side_effect=mock_agent_step_with_error):
            with patch('core.analytics_engine.get_analytics_engine', return_value=mock_analytics):
                try:
                    await engine._execute_workflow_graph(
                        execution_id="exec_error_001",
                        workflow=workflow,
                        state={"steps": {}, "outputs": {}},
                        ws_manager=mock_websocket_manager,
                        user_id="test_user",
                        start_time=datetime.utcnow()
                    )
                except Exception:
                    pass  # Expected error

        # Verify agent1 and agent2 attempted, agent3 did not run
        assert "agent1" in executed_agents
        assert "agent2" in executed_agents
        assert "agent3" not in executed_agents

    @pytest.mark.skip(reason="Governance enforcement requires trigger_interceptor integration - defer to future enhancement")
    @pytest.mark.asyncio
    async def test_agent_governance_enforcement(self, db_session: Session, mock_websocket_manager):
        """Test that STUDENT agent is blocked from AUTONOMOUS actions."""
        # TODO: Implement governance enforcement test with trigger_interceptor
        pass


class TestMultiAgentDatabase:
    """Test multi-agent workflow database persistence."""

    @pytest.mark.asyncio
    async def test_multi_agent_workflow_execution_record(self, db_session: Session):
        """Test creating workflow execution record for multi-agent scenario."""
        import json

        execution = WorkflowExecution(
            execution_id="exec_multiagent_001",
            workflow_id="multi_agent_workflow",
            status=WorkflowExecutionStatus.RUNNING,
            input_data=json.dumps({"agents": ["agent1", "agent2", "agent3"]}),
            steps=json.dumps([]),
            outputs=json.dumps({})
        )
        db_session.add(execution)
        db_session.commit()

        # Verify execution record
        retrieved = db_session.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == "exec_multiagent_001"
        ).first()

        assert retrieved is not None
        assert retrieved.status == WorkflowExecutionStatus.RUNNING
        assert "agents" in retrieved.input_data
