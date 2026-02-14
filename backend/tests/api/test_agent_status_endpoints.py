"""
Tests for Agent Status API Endpoints

Coverage Targets:
- Status retrieval (GET /agent/status/{task_id})
- Status updates (PUT /agent/{agent_id}/status)
- Status filtering (GET /agents, /agent/status)
- Status metrics (GET /agent/metrics)
- Error handling (404, 400, 500)
"""

import pytest
import json
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from api.agent_status_endpoints import (
    router,
    load_agent_status,
    save_agent_status,
    AGENT_STATUS_FILE,
    AgentTask,
    AgentInfo
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create test client with router"""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

@pytest.fixture
def temp_status_file(tmp_path):
    """Create temporary status file"""
    status_file = tmp_path / "test_agent_status.json"
    with patch("api.agent_status_endpoints.AGENT_STATUS_FILE", status_file):
        yield status_file

@pytest.fixture
def sample_agent_data():
    """Sample agent data"""
    return {
        "agents": {
            "agent_001": {
                "agent_id": "agent_001",
                "name": "Test Agent 1",
                "type": "general",
                "status": "idle",
                "last_active": datetime.now().isoformat(),
                "current_task": None,
                "capabilities": ["text_processing", "analysis"],
                "health_score": 1.0
            },
            "agent_002": {
                "agent_id": "agent_002",
                "name": "Test Agent 2",
                "type": "specialized",
                "status": "busy",
                "last_active": datetime.now().isoformat(),
                "current_task": "task_001",
                "capabilities": ["data_processing"],
                "health_score": 0.9
            }
        },
        "tasks": {
            "task_001": {
                "task_id": "task_001",
                "agent_id": "agent_002",
                "status": "running",
                "progress": 0.5,
                "started_at": datetime.now().isoformat(),
                "completed_at": None,
                "error_message": None,
                "result": None,
                "metadata": {"test": "data"}
            },
            "task_002": {
                "task_id": "task_002",
                "agent_id": "agent_001",
                "status": "completed",
                "progress": 1.0,
                "started_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "error_message": None,
                "result": {"output": "success"},
                "metadata": {}
            }
        }
    }

@pytest.fixture
def sample_tasks(sample_agent_data):
    """Extract sample tasks from agent data"""
    return sample_agent_data["tasks"]

# ============================================================================
# GET /agent/status/{task_id} - Status Retrieval
# ============================================================================

def test_get_agent_status_success(client, temp_status_file, sample_agent_data):
    """Test successful status retrieval for existing task"""
    # Setup
    save_agent_status(sample_agent_data)

    # Test
    response = client.get("/api/agent-status/agent/status/task_001")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "task_001"
    assert data["agent_id"] == "agent_002"
    assert data["status"] == "running"
    assert data["progress"] == 0.5


def test_get_agent_status_not_found(client, temp_status_file):
    """Test status retrieval for non-existent task returns default"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    response = client.get("/api/agent-status/agent/status/nonexistent_task")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "nonexistent_task"
    assert data["agent_id"] == "unknown"
    assert data["status"] == "not_found"
    assert data["error_message"] == "Task not found"


def test_get_agent_status_empty_file(client, temp_status_file):
    """Test status retrieval with empty status file"""
    # Test
    response = client.get("/api/agent-status/agent/status/task_any")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "not_found"


# ============================================================================
# GET /agent/status - All Tasks
# ============================================================================

def test_get_all_agent_tasks(client, temp_status_file, sample_agent_data):
    """Test retrieving all agent tasks"""
    # Setup
    save_agent_status(sample_agent_data)

    # Test
    response = client.get("/api/agent-status/agent/status")

    # Verify
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    assert any(t["task_id"] == "task_001" for t in tasks)
    assert any(t["task_id"] == "task_002" for t in tasks)


def test_get_all_agent_tasks_empty(client, temp_status_file):
    """Test retrieving all tasks when no tasks exist"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    response = client.get("/api/agent-status/agent/status")

    # Verify
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 0


# ============================================================================
# GET /agents - All Agents
# ============================================================================

def test_get_all_agents(client, temp_status_file, sample_agent_data):
    """Test retrieving all agents"""
    # Setup
    save_agent_status(sample_agent_data)

    # Test
    response = client.get("/api/agent-status/agents")

    # Verify
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 2
    assert any(a["agent_id"] == "agent_001" for a in agents)
    assert any(a["agent_id"] == "agent_002" for a in agents)


def test_get_all_agents_empty(client, temp_status_file):
    """Test retrieving all agents when no agents exist"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    response = client.get("/api/agent-status/agents")

    # Verify
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 0


# ============================================================================
# GET /agents/{agent_id} - Specific Agent
# ============================================================================

def test_get_agent_info_success(client, temp_status_file, sample_agent_data):
    """Test successful retrieval of specific agent info"""
    # Setup
    save_agent_status(sample_agent_data)

    # Test
    response = client.get("/api/agent-status/agents/agent_001")

    # Verify
    assert response.status_code == 200
    agent = response.json()
    assert agent["agent_id"] == "agent_001"
    assert agent["name"] == "Test Agent 1"
    assert agent["type"] == "general"
    assert agent["status"] == "idle"


def test_get_agent_info_not_found_creates_default(client, temp_status_file):
    """Test agent info retrieval creates default agent if not found"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    response = client.get("/api/agent-status/agents/new_agent")

    # Verify
    assert response.status_code == 200
    agent = response.json()
    assert agent["agent_id"] == "new_agent"
    assert agent["name"] == "Agent new_agent"
    assert agent["type"] == "general"
    assert agent["status"] == "idle"
    assert "last_active" in agent

    # Verify default agent was saved
    data = load_agent_status()
    assert "new_agent" in data["agents"]


# ============================================================================
# POST /agent/{agent_id}/heartbeat - Heartbeat Update
# ============================================================================

def test_agent_heartbeat_success(client, temp_status_file):
    """Test successful agent heartbeat update"""
    # Setup
    status_data = {
        "agents": {
            "agent_001": {
                "agent_id": "agent_001",
                "name": "Test Agent",
                "type": "general",
                "status": "idle",
                "last_active": datetime.now().isoformat(),
                "current_task": None,
                "capabilities": [],
                "health_score": 1.0
            }
        },
        "tasks": {}
    }
    save_agent_status(status_data)

    # Test
    heartbeat_data = {
        "name": "Updated Agent",
        "status": "busy",
        "current_task": "task_123",
        "health_score": 0.95
    }
    response = client.post("/api/agent-status/agent/agent_001/heartbeat", json=heartbeat_data)

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "timestamp" in data["data"]

    # Verify agent was updated
    agent_status = load_agent_status()
    agent = agent_status["agents"]["agent_001"]
    assert agent["name"] == "Updated Agent"
    assert agent["status"] == "busy"
    assert agent["current_task"] == "task_123"
    assert agent["health_score"] == 0.95


def test_agent_heartbeat_new_agent(client, temp_status_file):
    """Test heartbeat creates new agent if not exists"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    heartbeat_data = {
        "name": "New Agent",
        "type": "specialized",
        "capabilities": ["analysis", "reporting"]
    }
    response = client.post("/api/agent-status/agent/agent_new/heartbeat", json=heartbeat_data)

    # Verify
    assert response.status_code == 200

    # Verify agent was created
    agent_status = load_agent_status()
    assert "agent_new" in agent_status["agents"]
    assert agent_status["agents"]["agent_new"]["name"] == "New Agent"


# ============================================================================
# POST /agent/task/{task_id}/update - Task Status Update
# ============================================================================

def test_update_task_status_success(client, temp_status_file, sample_agent_data):
    """Test successful task status update"""
    # Setup
    save_agent_status(sample_agent_data)

    # Test
    update_data = {
        "status": "completed",
        "progress": 1.0,
        "result": {"final_output": "done"}
    }
    response = client.post("/api/agent-status/agent/task/task_001/update", json=update_data)

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify task was updated
    agent_status = load_agent_status()
    task = agent_status["tasks"]["task_001"]
    assert task["status"] == "completed"
    assert task["progress"] == 1.0
    assert task["result"] == {"final_output": "done"}
    assert "completed_at" in task


def test_update_task_status_not_found(client, temp_status_file):
    """Test updating non-existent task returns 404"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    update_data = {"status": "running"}
    response = client.post("/api/agent-status/agent/task/nonexistent/update", json=update_data)

    # Verify
    assert response.status_code == 404


def test_update_task_status_running_sets_timestamp(client, temp_status_file, sample_agent_data):
    """Test updating to running status sets started_at timestamp"""
    # Setup
    task_data = sample_agent_data.copy()
    task_data["tasks"]["task_003"] = {
        "task_id": "task_003",
        "agent_id": "agent_001",
        "status": "pending",
        "progress": 0.0,
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "result": None,
        "metadata": {}
    }
    save_agent_status(task_data)

    # Test
    update_data = {"status": "running"}
    response = client.post("/api/agent-status/agent/task/task_003/update", json=update_data)

    # Verify
    assert response.status_code == 200
    agent_status = load_agent_status()
    task = agent_status["tasks"]["task_003"]
    assert task["started_at"] is not None


def test_update_task_status_with_error(client, temp_status_file, sample_agent_data):
    """Test updating task with error message"""
    # Setup
    save_agent_status(sample_agent_data)

    # Test
    update_data = {
        "status": "failed",
        "error_message": "Connection timeout",
        "progress": 0.3
    }
    response = client.post("/api/agent-status/agent/task/task_001/update", json=update_data)

    # Verify
    assert response.status_code == 200
    agent_status = load_agent_status()
    task = agent_status["tasks"]["task_001"]
    assert task["status"] == "failed"
    assert task["error_message"] == "Connection timeout"
    assert task["progress"] == 0.3


# ============================================================================
# POST /agent/task - Create Task
# ============================================================================

def test_create_task_success(client, temp_status_file):
    """Test successful task creation"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    task_data = {
        "task_id": "task_new",
        "agent_id": "agent_001",
        "status": "pending",
        "progress": 0.0,
        "metadata": {"source": "test"}
    }
    response = client.post("/api/agent-status/agent/task", json=task_data)

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["task_id"] == "task_new"

    # Verify task was created
    agent_status = load_agent_status()
    assert "task_new" in agent_status["tasks"]
    assert agent_status["tasks"]["task_new"]["agent_id"] == "agent_001"


def test_create_task_running_sets_timestamp(client, temp_status_file):
    """Test creating running task sets started_at"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    task_data = {
        "task_id": "task_running",
        "agent_id": "agent_001",
        "status": "running",
        "progress": 0.0
    }
    response = client.post("/api/agent-status/agent/task", json=task_data)

    # Verify
    assert response.status_code == 200
    agent_status = load_agent_status()
    task = agent_status["tasks"]["task_running"]
    assert task["started_at"] is not None


# ============================================================================
# DELETE /agent/task/{task_id} - Delete Task
# ============================================================================

def test_delete_task_success(client, temp_status_file, sample_agent_data):
    """Test successful task deletion"""
    # Setup
    save_agent_status(sample_agent_data)

    # Test
    response = client.delete("/api/agent-status/agent/task/task_001")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify task was deleted
    agent_status = load_agent_status()
    assert "task_001" not in agent_status["tasks"]
    assert "task_002" in agent_status["tasks"]  # Other task still exists


def test_delete_task_not_found(client, temp_status_file):
    """Test deleting non-existent task returns 404"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    response = client.delete("/api/agent-status/agent/task/nonexistent")

    # Verify
    assert response.status_code == 404


# ============================================================================
# GET /agent/metrics - Performance Metrics
# ============================================================================

def test_get_agent_metrics(client, temp_status_file, sample_agent_data):
    """Test retrieving agent metrics"""
    # Setup
    save_agent_status(sample_agent_data)

    # Test
    response = client.get("/api/agent-status/agent/metrics")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert "data" in data

    metrics = data["data"]
    assert "agents" in metrics
    assert "tasks" in metrics

    # Check agent metrics
    assert metrics["agents"]["total"] == 2
    assert metrics["agents"]["active"] == 1  # agent_002 is busy
    assert metrics["agents"]["idle"] == 1     # agent_001 is idle

    # Check task metrics
    assert metrics["tasks"]["total"] == 2
    assert metrics["tasks"]["completed"] == 1  # task_002
    assert metrics["tasks"]["failed"] == 0
    assert metrics["tasks"]["pending"] == 1   # task_001 is running

    # Check success rate
    assert "success_rate" in metrics
    assert metrics["success_rate"] == 0.5  # 1 completed out of 2


def test_get_agent_metrics_empty(client, temp_status_file):
    """Test metrics with no agents or tasks"""
    # Setup
    save_agent_status({"agents": {}, "tasks": {}})

    # Test
    response = client.get("/api/agent-status/agent/metrics")

    # Verify
    assert response.status_code == 200
    data = response.json()
    metrics = data["data"]

    assert metrics["agents"]["total"] == 0
    assert metrics["agents"]["active"] == 0
    assert metrics["tasks"]["total"] == 0
    assert metrics["tasks"]["completed"] == 0
    assert metrics["success_rate"] == 0.0  # Division by zero protection


# ============================================================================
# Error Handling
# ============================================================================

def test_load_agent_status_corrupted_file(temp_status_file):
    """Test loading from corrupted file returns empty dict"""
    # Setup
    temp_status_file.write_text("invalid json content")

    # Test
    data = load_agent_status()

    # Verify
    assert data == {"agents": {}, "tasks": {}}


def test_save_agent_status_error_handling(temp_status_file):
    """Test saving error is logged but doesn't crash"""
    # Setup - make file read-only
    temp_status_file.write_text("{}")
    temp_status_file.chmod(0o444)

    # Test - should not raise exception
    try:
        save_agent_status({"agents": {}, "tasks": {}})
    except Exception:
        pass  # Expected

    # Cleanup
    temp_status_file.chmod(0o644)


# ============================================================================
# Governance Integration
# ============================================================================

def test_active_agent_counting(client, temp_status_file):
    """Test active agent counting considers different states"""
    # Setup
    status_data = {
        "agents": {
            "agent_running": {"agent_id": "agent_running", "status": "running", "last_active": datetime.now().isoformat(), "name": "Running", "type": "general", "current_task": None, "capabilities": [], "health_score": 1.0},
            "agent_busy": {"agent_id": "agent_busy", "status": "busy", "last_active": datetime.now().isoformat(), "name": "Busy", "type": "general", "current_task": None, "capabilities": [], "health_score": 1.0},
            "agent_idle": {"agent_id": "agent_idle", "status": "idle", "last_active": datetime.now().isoformat(), "name": "Idle", "type": "general", "current_task": None, "capabilities": [], "health_score": 1.0}
        },
        "tasks": {}
    }
    save_agent_status(status_data)

    # Test
    response = client.get("/api/agent-status/agent/metrics")

    # Verify
    assert response.status_code == 200
    metrics = response.json()["data"]
    assert metrics["agents"]["active"] == 2  # running + busy
    assert metrics["agents"]["idle"] == 1    # idle agent


def test_task_status_filtering(client, temp_status_file):
    """Test task metrics correctly filter by status"""
    # Setup
    status_data = {
        "agents": {},
        "tasks": {
            "task_1": {"task_id": "task_1", "agent_id": "agent_1", "status": "completed", "progress": 1.0, "started_at": None, "completed_at": None, "error_message": None, "result": None, "metadata": {}},
            "task_2": {"task_id": "task_2", "agent_id": "agent_1", "status": "failed", "progress": 0.5, "started_at": None, "completed_at": None, "error_message": None, "result": None, "metadata": {}},
            "task_3": {"task_id": "task_3", "agent_id": "agent_1", "status": "running", "progress": 0.2, "started_at": None, "completed_at": None, "error_message": None, "result": None, "metadata": {}},
            "task_4": {"task_id": "task_4", "agent_id": "agent_1", "status": "pending", "progress": 0.0, "started_at": None, "completed_at": None, "error_message": None, "result": None, "metadata": {}}
        }
    }
    save_agent_status(status_data)

    # Test
    response = client.get("/api/agent-status/agent/metrics")

    # Verify
    assert response.status_code == 200
    metrics = response.json()["data"]
    assert metrics["tasks"]["total"] == 4
    assert metrics["tasks"]["completed"] == 1
    assert metrics["tasks"]["failed"] == 1
    assert metrics["tasks"]["pending"] == 2  # running + pending


# ============================================================================
# Pydantic Model Validation
# ============================================================================

def test_agent_task_model_validation():
    """Test AgentTask Pydantic model validation"""
    # Valid task
    task = AgentTask(
        task_id="task_001",
        agent_id="agent_001",
        status="running",
        progress=0.5,
        metadata={"key": "value"}
    )
    assert task.task_id == "task_001"
    assert task.status == "running"
    assert task.progress == 0.5

    # Task with all fields
    task_full = AgentTask(
        task_id="task_002",
        agent_id="agent_002",
        status="completed",
        progress=1.0,
        started_at=datetime.now(),
        completed_at=datetime.now(),
        error_message=None,
        result={"output": "success"},
        metadata={}
    )
    assert task_full.status == "completed"
    assert task_full.result == {"output": "success"}


def test_agent_info_model_validation():
    """Test AgentInfo Pydantic model validation"""
    # Valid agent
    agent = AgentInfo(
        agent_id="agent_001",
        name="Test Agent",
        type="general",
        status="idle",
        last_active=datetime.now(),
        current_task=None,
        capabilities=["text_processing"],
        health_score=0.95
    )
    assert agent.agent_id == "agent_001"
    assert agent.status == "idle"
    assert agent.health_score == 0.95

    # Agent with current task
    agent_busy = AgentInfo(
        agent_id="agent_002",
        name="Busy Agent",
        type="specialized",
        status="busy",
        last_active=datetime.now(),
        current_task="task_001",
        capabilities=["data_processing"],
        health_score=1.0
    )
    assert agent_busy.current_task == "task_001"
    assert agent_busy.status == "busy"
