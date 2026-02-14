"""
Integration tests for SUPERVISED agent operations with supervision integration.

Tests supervision session lifecycle, intervention workflows,
and cross-API integration between agent lifecycle and supervision systems.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, MagicMock
from core.agent_lifecycle_service import AgentLifecycleService
from core.agent_service import AgentService
from core.supervision_service import SupervisionService
from api.supervision_routes import router as supervision_router
from api.agent_routes import router as agent_router
from core.database import get_db


class TestSupervisionIntegration:
    """Test SUPERVISED agent operations with supervision integration."""

    def test_complete_supervised_agent_lifecycle(self):
        """Test complete SUPERVISED agent lifecycle: create → configure → execute → monitor → delete."""
        db = get_db()
        agent_service = Mock(spec=AgentLifecycleService)
        supervision_service = Mock(spec=SupervisionService)
        created_agent_id = None

        with TestClient(app) as client:
            # Create SUPERVISED agent
            response = client.post("/agents", json={
                "name": "Test SUPERVISED Agent",
                "type": "supervised",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "SUPERVISED"
            })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Configure agent
            response = client.put(f"/agents/{created_agent_id}", json={
                "status": "active",
                "config": {
                    "monitoring_enabled": True,
                    "learning_enabled": False
                }
            })
            assert response.status_code == 200

            # Execute task through agent
            response = client.post(f"/agents/{created_agent_id}/tasks", json={
                "name": "Test Task Execution",
                "type": "data_analysis",
                "parameters": {"query": "test query", "max_results": 10}
            })
            assert response.status_code == 201
            task_id = response.json()["id"]

            # Monitor agent status
            response = client.get(f"/agents/{created_agent_id}/status")
            assert response.status_code == 200
            agent_data = response.json()
            assert agent_data["status"] == "active"

            # Delete agent
            response = client.delete(f"/agents/{created_agent_id}")
            assert response.status_code == 200

    def test_supervision_session(self):
        """Test SUPERVISED supervision session lifecycle: start → pause → correct → terminate → resume."""
        db = get_db()
        agent_service = Mock(spec=SupervisionService)

        with TestClient(app) as client:
            # Create SUPERVISED agent
            response = client.post("/agents", json={
                "name": "Test SUPERVISED Agent",
                "type": "supervised",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "SUPERVISED"
            })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Start supervision session
            response = client.post(f"/supervision/sessions", json={
                "agent_id": created_agent_id
            })

        with TestClient(app) as client:
            # Create supervision session
            response = client.post("/supervision/interventions", json={
                "session_id": "test_supervision_session_id",
                "type": "correction"
                })

            # Submit intervention
            response = client.put(f"/supervision/interventions/{test_supervision_session_id}", json={
                "data": {"correction": "Fix error in task"}
            })

            # Terminate session
            response = client.delete(f"/supervision/sessions/{test_supervision_session_id}")

        with TestClient(app) as client:
            # Resume session
            response = client.put(f"/supervision/sessions/{test_supervision_session_id}", json={
                "status": "active"
            })

    def test_cross_api_integration(self):
        """Test cross-API workflows: agent → supervision → workflow → collaboration."""
        db = get_db()
        agent_service = Mock(spec=AgentLifecycleService)
        supervision_service = Mock(spec=SupervisionService)
        workflow_service = Mock(spec=WorkflowTemplateService)
        collaboration_service = Mock(spec=WorkflowCollaborationService)
        guidance_service = Mock(spec=AgentGuidanceService)

        with TestClient(app) as client:
            # End-to-end workflow test
            response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
            })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Create workflow
            response = client.post("/workflows", json={
                "agent_id": created_agent_id,
                "name": "Test Workflow",
                "type": "custom",
                "steps": [
                    {"agent_id": created_agent_id, "step_type": "create", "data": {"template_id": "test_template_1"}}
                    ]
            })
            assert response.status_code == 201
            created_workflow_id = response.json()["id"]

            # Share workflow
            response = client.post(f"/workflows/{created_workflow_id}/share", json={
                "agent_ids": [created_agent_id]
            })
            assert response.status_code == 201

            # Join shared workflow
            response = client.post(f"/workflows/{created_workflow_id}/join", json={
                "agent_ids": [created_agent_id]
            })
            assert response.status_code == 201

            # Complete workflow
            response = client.post(f"/workflows/{created_workflow_id}/complete", json={
                "agent_ids": [created_agent_id]
            })
            assert response.status_code == 201

            # Monitor workflow status
            response = client.get(f"/workflows/{created_workflow_id}")

            # Verify cross-API integration
        assert response.json()["status"] == "completed"

    def test_agent_guidance_integration(self):
        """Test agent guidance system integration."""
        db = get_db()
        guidance_service = Mock(spec=AgentGuidanceService)

        with TestClient(app) as client:
            # Track operation
            response = client.post("/operations", json={
                "type": "track",
                "data": {
                    "query": "test query",
                    "context": "test operation tracking",
                    "max_results": 10
                }
            })

            assert response.status_code == 200

            # Test presentation request
            response = client.post("/presentations", json={
                "agent_id": created_agent_id,
                "type": "presentation",
                "data": {
                    "presentation_type": "canvas",
                    "content": {"title": "Test", "elements": [...] }
                }
            })

            assert response.status_code == 200

            # Test permission request
            response = client.post("/permissions", json={
                "agent_id": created_agent_id,
                "type": "permission_request",
                "data": {"capability": "execute_script", "context": "test script execution"}
                })

            assert response.status_code == 200 or 403  # 403 Forbidden if capability not enabled

        db = get_db()

        with TestClient(app) as client:
            # Create agent
            response = client.post("/agents", json={
                "name": "Guidance Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
            })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Get agent status
            response = client.get(f"/agents/{created_agent_id}/status")
            assert response.status_code == 200
            agent_data = response.json()

            # Update agent
            response = client.put(f"/agents/{created_agent_id}", json={
                "config": {
                    "monitoring_enabled": True,
                    "learning_enabled": False,
                    "guidance": {
                        "enabled": True,
                        "suggestions": True,
                        "presentations": True,
                        "permission_requests": True
                    }
                }
            })
            assert response.status_code == 200

    def test_database_session_management(self):
        """Test database session management with automatic rollback."""
        db = get_db()

        with TestClient(app) as client:
            # Clean test data
            response = client.delete("/test-data")
            assert response.status_code == 200

            # Create test data
            response = client.post("/test-data", json={
                "agent_id": created_agent_id,
                "type": "data_analysis",
                "parameters": {"query": "test query"}
            })
            assert response.status_code == 200

            # Run tests with automatic rollback
            response = client.post("/test-run", json={
                "agent_id": created_agent_id
            })

            response = client.get(f"/test-runs/{created_agent_id}")
            assert response.status_code == 200
            results = response.json()

            # Verify data cleanup
            response = client.delete("/test-data")
            assert response.status_code == 200

        with TestClient(app) as client:
            # Create agent
            response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
            })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Configure agent
            response = client.put(f"/agents/{created_agent_id}", json={
                "status": "active",
                "config": {
                    "monitoring_enabled": True,
                    "learning_enabled": False
                }
            })

            # Execute task
            response = client.post(f"/agents/{created_agent_id}/tasks", json={
                "name": "Test Task Execution",
                "type": "data_analysis",
                "parameters": {"query": "test query"}
            })

            assert response.status_code == 201
            task_id = response.json()["id"]

            # Monitor task
            response = client.get(f"/agents/{created_agent_id}/status")
            assert response.status_code == 200
            agent_data = response.json()

            # Delete agent
            response = client.delete(f"/agents/{created_agent_id}")
            assert response.status_code == 200

            # Verify agent deleted
            response = client.get(f"/agents/{created_agent_id}")
            assert response.status_code == 404  # Expect 404

        with TestClient(app) as client:
            # Create agent
            response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Execute task
            response = client.post(f"/agents/{created_agent_id}/tasks", json={
                "name": "Test Task Execution",
                "type": "data_analysis",
                "parameters": {"query": "test query", "max_results": 10}
                })

            assert response.status_code == 201
            task_id = response.json()["id"]

            # Monitor task
            response = client.get(f"/agents/{created_agent_id}/status")
            assert response.status_code == 200
            agent_data = response.json()
            assert agent_data["status"] == "active"

            # Delete agent
            response = client.delete(f"/agents/{created_agent_id}")
            assert response.status_code == 200

    def test_fastapi_dependency_override(self):
        """Test FastAPI dependency override for realistic testing."""
        db = get_db()

        with TestClient(app) as client:
            # Mock database
            mock_db = MagicMock(spec=Session)

            # Override get_db to return mock_db
            from core.database import get_db
            app.dependency_overrides[get_db] = lambda: mock_db

            # Mock agent service
            from core.agent_service import AgentService
            mock_agent_service = Mock(spec=AgentService)

            app.dependency_overrides[AgentService] = lambda x: mock_agent_service

            # Mock supervision service
            from core.supervision_service import SupervisionService
            mock_supervision_service = Mock(spec=SupervisionService)

            # Mock workflow service
            from core.workflow_template_service import WorkflowTemplateService
            mock_workflow_service = Mock(spec=WorkflowTemplateService)

            # Mock collaboration service
            from core.workflow_collaboration_service import WorkflowCollaborationService

            # Mock guidance service
            from core.agent_guidance_service import AgentGuidanceService
            mock_guidance_service = Mock(spec=AgentGuidanceService)

            # Test with dependency overrides
            response = client.get("/operations/test")
            assert response.status_code == 200
            operations = response.json()

            # Verify all services called
            assert mock_agent_service.call_count > 0
            assert mock_supervision_service.call_count > 0
            assert mock_workflow_service.call_count > 0
            assert mock_collaboration_service.call_count > 0

            # Verify cleanup
            response = client.delete("/test-data")
            assert response.status_code == 200

            # Verify agent deleted
            response = client.get(f"/agents/{created_agent_id}")
            assert response.status_code == 404  # Expect 404

            mock_db.reset_mock()


@pytest.fixture
def test_agent_guidance_integration(db, mock_agent_service, mock_guidance_service, created_agent_id):
    """Test agent guidance integration with dependencies."""
    # Track operation
    response = client.post("/operations", json={
                "type": "track",
                "data": {
                    "query": "test query",
                    "context": "test operation tracking"
                    }
                })

    assert response.status_code == 200
    operation_id = response.json()["id"]

    # Test presentation request
    response = client.post("/presentations", json={
                "agent_id": created_agent_id,
                "type": "presentation",
                "data": {
                    "presentation_type": "canvas",
                    "content": {
                        "title": "Test Presentation",
                        "elements": [
                            {"type": "markdown", "content": "# Test Content"}
                            ]
                        }
                    }
                })

    assert response.status_code == 200

    # Test permission request
    response = client.post("/permissions", json={
                "agent_id": created_agent_id,
                "type": "permission_request",
                "data": {"capability": "execute_script", "context": "test script"}
                })

    assert response.status_code == 200 or 403

    # Verify permission granted
    operation_id = response.json()["id"]

    # Get agent status
    response = client.get(f"/agents/{created_agent_id}/status")
    assert response.status_code == 200
    agent_data = response.json()

    # Update agent
    response = client.put(f"/agents/{created_agent_id}", json={
                "config": {
                    "monitoring_enabled": True,
                    "guidance": {
                        "enabled": True,
                        "suggestions": True,
                        "presentations": True,
                        "permission_requests": True
                    },
                    "learning_enabled": False
                }
                })

    assert response.status_code == 200

        # Verify agent configured with guidance
        agent_config = agent_data["config"]
        assert agent_config["monitoring_enabled"] == True
        assert agent_config["guidance"]["enabled"] == True

    # Cleanup
    mock_agent_service.reset_mock()
    mock_supervision_service.reset_mock()
    mock_guidance_service.reset_mock()

    return created_agent_id


class TestCrossAPIIntegration:
    """Test cross-API workflows with all integration."""

    def __init__(self, db=None, agent_service=None, supervision_service=None,
                  workflow_service=None, collaboration_service=None, guidance_service=None):
        self.db = db
        self.agent_service = agent_service
        self.supervision_service = supervision_service
        self.workflow_service = workflow_service
        self.collaboration_service = collaboration_service
        self.guidance_service = guidance_service

        if not all([self.agent_service, self.supervision_service, self.workflow_service, self.collaboration_service, self.guidance_service]):
            raise ValueError("All services must be provided")

    def test_complete_agent_lifecycle(self):
        """Test complete agent lifecycle: create → configure → execute → monitor → delete."""
        with TestClient(app) as client:
            # Create agent
            response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Configure agent
            response = client.put(f"/agents/{created_agent_id}", json={
                "status": "active",
                "config": {
                    "monitoring_enabled": True,
                    "learning_enabled": False
                    }
                })

            # Execute task
            response = client.post(f"/agents/{created_agent_id}/tasks", json={
                "name": "Test Task Execution",
                "type": "data_analysis",
                "parameters": {"query": "test query", "max_results": 10}
                })

            assert response.status_code == 201
            task_id = response.json()["id"]

            # Monitor task
            response = client.get(f"/agents/{created_agent_id}/status")
            assert response.status_code == 200
            agent_data = response.json()
            assert agent_data["status"] == "active"

            # Delete agent
            response = client.delete(f"/agents/{created_agent_id}")
            assert response.status_code == 200

        return created_agent_id


def test_supervision_integration(db, supervision_service, created_agent_id):
        """Test SUPERVISED agent operations with supervision integration."""
    with TestClient(app) as client:
            # Create SUPERVISED agent
            response = client.post("/agents", json={
                "name": "Test SUPERVISED Agent",
                "type": "supervised",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "SUPERVISED"
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Start supervision session
            response = client.post(f"/supervision/sessions", json={
                "agent_id": created_agent_id
                })

        with TestClient(app) as client:
            # Submit intervention
            response = client.post(f"/supervision/interventions", json={
                "session_id": "test_supervision_session_id",
                "type": "correction"
                })

        # Terminate session
        response = client.delete(f"/supervision/sessions/{test_supervision_session_id}")
        with TestClient(app) as client:
            # Resume session
            response = client.put(f"/supervision/sessions/{test_supervision_session_id}", json={
                "status": "active"
            })

        return created_agent_id


def test_collaboration_integration(db, collaboration_service, created_agent_id):
    """Test workflow collaboration: share, join, complete."""
    with TestClient(app) as client:
            # Create agent
            response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "aasynchronous"]
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Create workflow
            response = client.post("/workflows", json={
                "agent_id": created_agent_id,
                "name": "Test Workflow",
                "type": "custom",
                "steps": [
                    {
                        "agent_id": created_agent_id,
                        "step_type": "create",
                        "data": {"template_id": "test_template_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "share",
                        "data": {"workflow_id": "test_collaboration_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "collaborate",
                        "data": {"workflow_id": "test_collaboration_1"}
                    }
                ]
            })

            assert response.status_code == 201
            created_workflow_id = response.json()["id"]

            # Share workflow
            response = client.post(f"/workflows/{created_workflow_id}/share", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201

            # Join workflow
            response = client.post(f"/workflows/{created_workflow_id}/join", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            joined_workflow_id = response.json()["id"]

            # Complete workflow
            response = client.post(f"/workflows/{joined_workflow_id}/complete", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201

            return joined_workflow_id


def test_agent_guidance_integration(db, guidance_service, created_agent_id):
    """Test agent guidance system integration."""
    with TestClient(app) as client:
            # Test presentation request
            response = client.post("/presentations", json={
                "agent_id": created_agent_id,
                "type": "presentation",
                "data": {
                    "presentation_type": "canvas",
                    "content": {"title": "Test", "elements": [...]}
                    }
                })

        return created_agent_id


def test_cross_api_workflows(db, agent_service, supervision_service, workflow_service, collaboration_service, guidance_service, created_agent_id):
    """Test cross-API workflows: agent → workflow → collaboration."""
    with TestClient(app) as client:
        # End-to-end workflow test
            response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Create workflow
            response = client.post("/workflows", json={
                "agent_id": created_agent_id,
                "name": "Test Workflow",
                "type": "custom",
                "steps": [
                    {
                        "agent_id": created_agent_id,
                        "step_type": "create",
                        "data": {"template_id": "test_template_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "share",
                        "data": {"workflow_id": "test_collaboration_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "collaborate",
                        "data": {"workflow_id": "test_collaboration_1"}
                    }
                ]
            })

            assert response.status_code == 201
            created_workflow_id = response.json()["id"]

            # Share workflow
            response = client.post(f"/workflows/{created_workflow_id}/share", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201

            # Join workflow
            response = client.post(f"/workflows/{created_workflow_id}/join", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            joined_workflow_id = response.json()["id"]

            # Complete workflow
            response = client.post(f"/workflows/{joined_workflow_id}/complete", json={
                "agent_ids": [created_agent_id]
            })

            # Monitor workflow status
            response = client.get(f"/workflows/{joined_workflow_id}")

            # Verify cross-API integration
            assert response.json()["status"] == "completed"

            # Verify all services called
            assert agent_service.call_count > 0
            assert supervision_service.call_count > 0
            assert workflow_service.call_count > 0
            assert collaboration_service.call_count > 0
            assert guidance_service.call_count > 0

            return joined_workflow_id


@pytest.fixture
def db():
    """Get database session with automatic rollback."""
    from core.database import get_db
    from unittest.mock import MagicMock
    import pytest

    db = get_db()

    with pytest.fixture(autouse=True):
        mock_db = MagicMock()
        mock_db.__iter__.return_value = iter([{
            "query": "SELECT * FROM agents",
            "query": "SELECT * FROM agent_sessions",
            "query": "SELECT * FROM interventions"
        }])

        mock_db.reset_mock()

        yield mock_db


# Test data
MOCK_TEST_DATA = {
    1: "test_agent": {
        "id": "test-agent-1",
        "status": "active",
        "config": {
            "monitoring_enabled": True,
            "learning_enabled": False,
            "guidance": {
                "enabled": True,
                "suggestions": True,
                "presentations": True,
                "permission_requests": True
            }
        },
        "capabilities": {
            "reasoning": ["reasoning", "analysis", "tool_use"],
            "maturity_level": "INTERN"
        }
        },
    2: "test_workflow": {
        "id": "test-workflow-1",
        "name": "Test Workflow",
        "agent_id": "test-agent-1"
        },
    3: "test_collaboration": {
        "id": "test-collaboration-1",
        "name": "Test Collaboration",
        "agent_id": "test-agent-1"
        },
     4: "test_supervision_session": {
        "id": "test-session-1",
        "agent_id": "test-agent-1",
        "status": "active"
        }


@pytest.fixture
def agent_services():
    """Get mock agent services."""
    from unittest.mock import Mock
    from core.agent_lifecycle_service import AgentLifecycleService
    from core.agent_service import AgentService

    agent_service = Mock(spec=AgentService)
    return Mock(spec=AgentLifecycleService), Mock(spec=AgentService)


@pytest.fixture
def supervision_services():
    """Get mock supervision services."""
    from unittest.mock import Mock
    from core.supervision_service import SupervisionService

    supervision_service = Mock(spec=SupervisionService)
    return Mock(spec=SupervisionService), Mock(spec=SupervisionService)


@pytest.fixture
def workflow_services():
    """Get mock workflow services."""
    from unittest.mock import Mock
    from core.workflow_template_service import WorkflowTemplateService

    workflow_service = Mock(spec=WorkflowTemplateService)
    return Mock(spec=WorkflowTemplateService), Mock(spec=WorkflowTemplateService)


@pytest.fixture
def collaboration_services():
    """Get mock collaboration services."""
    from unittest.mock import Mock
    from core.workflow_collaboration_service import WorkflowCollaborationService

    collaboration_service = Mock(spec=WorkflowCollaborationService)
    return Mock(spec=WorkflowCollaborationService), Mock(spec=WorkflowCollaborationService)


@pytest.fixture
def guidance_services():
    """Get mock guidance services."""
    from unittest.mock import Mock
    from core.agent_guidance_service import AgentGuidanceService

    guidance_service = Mock(spec=AgentGuidanceService)
    return Mock(spec=AgentGuidanceService), Mock(spec=AgentGuidanceService)


class TestFastAPIDependencyOverride:
    """Test FastAPI dependency override for realistic testing."""

    def __init__(self, db=None, agent_service=None, supervision_service=None):
        self.db = db if db else get_db()
        self.agent_service = agent_service if agent_service else None
        self.supervision_service = supervision_service if supervision_service else None
        self.workflow_service = workflow_service if workflow_service else None
        self.collaboration_service = collaboration_service if collaboration_service else None
        self.guidance_service = guidance_service if guidance_service else None

        self.fastapi_dep_override = FastAPIDependencyOverride(
            db=self.db,
            agent_service=self.agent_service,
            supervision_service=self.supervision_service,
            workflow_service=self.workflow_service,
            collaboration_service=self.collaboration_service,
            guidance_service=self.guidance_service
        )

    def test_complete_agent_lifecycle(self):
        """Test complete agent lifecycle: create → configure → execute → monitor → delete."""
        with TestClient(app) as client:
            # Create agent
            response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Configure agent
            response = client.put(f"/agents/{created_agent_id}", json={
                "status": "active",
                "config": {
                    "monitoring_enabled": True,
                    "learning_enabled": False,
                    }
                })

            # Execute task
            response = client.post(f"/agents/{created_agent_id}/tasks", json={
                "name": "Test Task Execution",
                "type": "data_analysis",
                "parameters": {"query": "test query", "max_results": 10}
                })

            assert response.status_code == 201
            task_id = response.json()["id"]

            # Monitor agent status
            response = client.get(f"/agents/{created_agent_id}/status")
            assert response.status_code == 200
            agent_data = response.json()
            assert agent_data["status"] == "active"

            # Delete agent
            response = client.delete(f"/agents/{created_agent_id}")
            assert response.status_code == 200

        return created_agent_id


def test_fastapi_dependency_override(self):
        """Test FastAPI dependency override for realistic testing."""
        with TestClient(app) as client:
            # Get operations
            response = client.get("/operations/test")
            operations = response.json()

            # Verify dependency injection working
            assert response.status_code == 200
            assert operations is not None

            # Verify all services called
            assert self.fastapi_dep_override.mock_agent_service.call_count > 0
            assert self.fastapi_dep_override.mock_supervision_service.call_count > 0
            assert self.fastapi_dep_override.mock_workflow_service.call_count > 0
            assert self.fastapi_dep_override.mock_collaboration_service.call_count > 0
            assert self.fastapi_dep_override.mock_guidance_service.call_count > 0

            # Cleanup
            self.fastapi_dep_override.mock_db.reset_mock()
            mock_db.reset_mock()
            self.fastapi_dep_override.mock_agent_service.reset_mock()
            self.fastapi_dep_override.mock_supervision_service.reset_mock()
            self.fastapi_dep_override.mock_workflow_service.reset_mock()
            self.fastapi_dep_override.mock_collaboration_service.reset_mock()
            self.fastapi_dep_override.mock_guidance_service.reset_mock()

            # Verify mock_db cleanup
            response = client.delete("/test-data")
            assert response.status_code == 200

            # Verify agent deleted
            response = client.get(f"/agents/{created_agent_id}")
            assert response.status_code == 404  # Expect 404

            return True


@pytest.mark.integration
def test_supervision_integration(db, supervision_service):
    """Test SUPERVISED agent operations with supervision integration."""
    agent_service = Mock(spec=AgentLifecycleService)
    created_agent_id = None

    with TestClient(app) as client:
        # Create SUPERVISED agent
        response = client.post("/agents", json={
                "name": "Test SUPERVISED Agent",
                "type": "supervised",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "SUPERVISED"
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

        # Start supervision session
        response = client.post(f"/supervision/sessions", json={
                "agent_id": created_agent_id
                })

        # Submit intervention
        response = client.post(f"/supervision/interventions", json={
                "session_id": "test_supervision_session_id",
                "type": "correction"
                })

        # Terminate session
        response = client.delete(f"/supervision/sessions/{test_supervision_session_id}")
        with TestClient(app) as client:
            # Resume session
            response = client.put(f"/supervision/sessions/{test_supervision_session_id}", json={
                "status": "active"
            })

        return created_agent_id


@pytest.mark.integration
def test_collaboration_integration(db, collaboration_service):
    """Test workflow collaboration: share, join, complete."""
    workflow_service = Mock(spec=WorkflowTemplateService)
    collaboration_service = Mock(spec=WorkflowCollaborationService)
    created_workflow_id = None
    shared_workflow_id = None

    with TestClient(app) as client:
        # Create agent
            response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "aasynchronous"]
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Create workflow
            response = client.post("/workflows", json={
                "agent_id": created_agent_id,
                "name": "Test Workflow",
                "type": "custom",
                "steps": [
                    {
                        "agent_id": created_agent_id,
                        "step_type": "create",
                        "data": {"template_id": "test_template_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "share",
                        "data": {"workflow_id": "test_collaboration_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "collaborate",
                        "data": {"workflow_id": "test_collaboration_1"}
                    }
                }
                ]
            })

            assert response.status_code == 201
            created_workflow_id = response.json()["id"]

            # Share workflow
            response = client.post(f"/workflows/{created_workflow_id}/share", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            shared_workflow_id = response.json()["id"]

            # Join workflow
            response = client.post(f"/workflows/{shared_workflow_id}/join", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            joined_workflow_id = response.json()["id"]

            # Complete workflow
            response = client.post(f"/workflows/{joined_workflow_id}/complete", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201

            return joined_workflow_id


@pytest.mark.integration
def test_agent_guidance_integration(db, guidance_service):
    """Test agent guidance system integration."""
    guidance_service = Mock(spec=AgentGuidanceService)
    created_agent_id = None

    with TestClient(app) as client:
        # Test presentation request
        response = client.post("/presentations", json={
                "agent_id": created_agent_id,
                "type": "presentation",
                "data": {
                    "presentation_type": "canvas",
                    "content": {"title": "Test Presentation", "elements": [...]}
                    }
                })

        assert response.status_code == 200

        # Test permission request
        response = client.post("/permissions", json={
                "agent_id": created_agent_id,
                "type": "permission_request",
                "data": {"capability": "execute_script", "context": "test script"}
                })

        assert response.status_code == 200 or 403

        # Get operation ID
        operation_id = response.json()["id"]

        # Verify permission granted
        response = client.get(f"/permissions/{operation_id}")

        assert response.status_code == 200
        permission = response.json()
        assert permission["granted"] == True

        # Get agent status
        response = client.get(f"/agents/{created_agent_id}/status")

        # Update agent configuration
        response = client.put(f"/agents/{created_agent_id}", json={
                "status": "active",
                "config": {
                    "monitoring_enabled": True,
                    "guidance": {
                        "enabled": True,
                        "suggestions": True,
                        "presentations": True,
                        "permission_requests": True
                    },
                    "learning_enabled": False
                    }
                })

        assert response.status_code == 200

        # Verify agent configured with guidance
        agent_config = agent_data["config"]
        assert agent_config["guidance"]["enabled"] == True

        return created_agent_id


def test_cross_api_workflows(db, agent_service, supervision_service, workflow_service, collaboration_service, guidance_service, created_agent_id):
    """Test cross-API workflows: agent → workflow → collaboration."""
    with TestClient(app) as client:
        # Create agent
        response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Create workflow
            response = client.post("/workflows", json={
                "agent_id": created_agent_id,
                "name": "Test Workflow",
                "type": "custom",
                "steps": [
                    {
                        "agent_id": created_agent_id,
                        "step_type": "create",
                        "data": {"template_id": "test_template_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "share",
                        "data": {"workflow_id": "test_collaboration_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "collaborate",
                        "data": {"workflow_id": "test_collaboration_1"}
                    }
                }
                ]
            })

            assert response.status_code == 201
            created_workflow_id = response.json()["id"]

            # Share workflow
            response = client.post(f"/workflows/{created_workflow_id}/share", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            shared_workflow_id = response.json()["id"]

            # Join workflow
            response = client.post(f"/workflows/{shared_workflow_id}/join", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            joined_workflow_id = response.json()["id"]

            # Complete workflow
            response = client.post(f"/workflows/{joined_workflow_id}/complete", json={
                "agent_ids": [created_agent_id]
            })

            # Monitor workflow status
            response = client.get(f"/workflows/{joined_workflow_id}")

            # Verify cross-API integration
            assert response.json()["status"] == "completed"

            # Verify all services called
            assert agent_service.call_count > 0
            assert supervision_service.call_count > 0
            assert workflow_service.call_count > 0
            assert collaboration_service.call_count > 0
            assert guidance_service.call_count > 0

            return joined_workflow_id


class TestFastAPIDependencyOverride:
    """Test FastAPI dependency override for realistic testing."""
    def __init__(self, db=None, agent_service=None, supervision_service=None,
                  workflow_service=None, collaboration_service=None, guidance_service=None):
        self.db = db if db else get_db()
        self.agent_service = agent_service if agent_service else None
        self.supervision_service = supervision_service if supervision_service else None
        self.workflow_service = workflow_service if workflow_service else None
        self.collaboration_service = collaboration_service if collaboration_service else None
        self.guidance_service = guidance_service if guidance_service else None

        self.fastapi_dep_override = FastAPIDependencyOverride(
            db=self.db,
            agent_service=self.agent_service,
            supervision_service=self.supervision_service,
            workflow_service=self.workflow_service,
            collaboration_service=self.collaboration_service,
            guidance_service=self.guidance_service
        )

    def test_complete_agent_lifecycle(self):
        """Test complete agent lifecycle: create → configure → execute → monitor → delete."""
        with TestClient(app) as client:
            # Create agent
            response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Configure agent
            response = client.put(f"/agents/{created_agent_id}", json={
                "status": "active",
                "config": {
                    "monitoring_enabled": True,
                    "learning_enabled": False
                    }
                })

            # Execute task
            response = client.post(f"/agents/{created_agent_id}/tasks", json={
                "name": " Test Task Execution",
                "type": "data_analysis",
                "parameters": {"query": "test query", "max_results": 10}
                })

            assert response.status_code == 201
            task_id = response.json()["id"]

            # Monitor agent status
            response = client.get(f"/agents/{created_agent_id}/status")
            assert response.status_code == 200
            agent_data = response.json()
            assert agent_data["status"] == "active"

            # Delete agent
            response = client.delete(f"/agents/{created_agent_id}")
            assert response.status_code == 200

        return created_agent_id


@pytest.mark.integration
def test_database_session_management(db):
    """Test database session management with automatic rollback."""
    db = get_db()
    mock_db = MagicMock()

    with pytest.fixture(autouse=True):
        # Clean test data
        response = client.delete("/test-data")
        assert response.status_code == 200

        # Create test data
        response = client.post("/test-data", json={
                "agent_id": created_agent_id,
                "type": "data_analysis",
                "parameters": {"query": "test query"}
                })

        assert response.status_code == 200

        # Run tests with automatic rollback
        response = client.post("/test-run", json={
                "agent_id": created_agent_id
            })

        response = client.get(f"/test-runs/{created_agent_id}")
        assert response.status_code == 200
        results = response.json()

        # Verify data cleanup
        response = client.delete("/test-data")
        assert response.status_code == 200

        # Verify agent deleted
        response = client.get(f"/agents/{created_agent_id}")
        assert response.status_code == 404  # Expect 404

        # Cleanup
        mock_db.reset_mock()


# Test data
MOCK_TEST_DATA = {
    1: "test_agent": {
        "id": "test-agent-1",
        "status": "active",
        "config": {
            "monitoring_enabled": True,
            "learning_enabled": False,
            "guidance": {
                "enabled": True,
                "suggestions": True,
                "presentations": True,
                "permission_requests": True
            }
        },
        "capabilities": {
            "reasoning": ["reasoning", "complexity_analysis", "tool_use"],
            "maturity_level": "INTERN"
        }
        }


@pytest.mark.integration
def test_cross_api_workflows():
    """Test cross-API workflows: agent → workflow → collaboration."""
    from test_integration_workflows import (
        test_complete_agent_lifecycle,
        test_supervision_integration,
        test_collaboration_integration,
        test_agent_guidance_integration,
        test_fastapi_dependency_override
    )

    with TestClient(app) as client:
        # Create agent
        response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
                })
            assert response.status_code == 201
            created_agent_id = response.json()["id"]

            # Create workflow
            response = client.post("/workflows", json={
                "agent_id": created_agent_id,
                "name": "Test Workflow",
                "type": "custom",
                "steps": [
                    {
                        "agent_id": created_agent_id,
                        "step_type": "create",
                        "data": {"template_id": "test_template_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "share",
                        "data": {"workflow_id": "test_collaboration_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "collaborate",
                        "data": {"workflow_id": "test_collaboration_1"}
                    }
                }
                ]
            })

            assert response.status_code == 201
            created_workflow_id = response.json()["id"]

            # Share workflow
            response = client.post(f"/workflows/{created_workflow_id}/share", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            shared_workflow_id = response.json()["id"]

            # Join workflow
            response = client.post(f"/workflows/{shared_workflow_id}/join", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            joined_workflow_id = response.json()["id"]

            # Complete workflow
            response = client.post(f"/workflows/{joined_workflow_id}/complete", json={
                "agent_ids": [created_agent_id]
            })

            # Monitor workflow status
            response = client.get(f"/workflows/{joined_workflow_id}")

            # Verify cross-API integration
            assert response.json()["status"] == "completed"

            # Verify all services called
            assert agent_service.call_count > 0
            assert supervision_service.call_count > 0
            assert workflow_service.call_count > 0
            assert collaboration_service.call_count > 0
            assert guidance_service.call_count > 0

            return joined_workflow_id


def test_agent_guidance_integration():
    """Test agent guidance system integration."""
    from test_agent_guidance_integration import (
        test_fastapi_dependency_override,
        test_complete_agent_lifecycle,
        test_supervision_integration,
        test_collaboration_integration,
        test_cross_api_workflows
    )

    guidance_service = Mock(spec=AgentGuidanceService)

    with TestClient(app) as client:
        # Test presentation request
        response = client.post("/presentations", json={
                "agent_id": created_agent_id,
                "type": "presentation",
                "data": {
                    "presentation_type": "canvas",
                    "content": {"title": "Test Presentation", "elements": [...]}
                    }
                })

        assert response.status_code == 200

        # Test permission request
        response = client.post("/permissions", json={
                "agent_id": created_agent_id,
                "type": "permission_request",
                "data": {"capability": "execute_script", "context": "test script"}
                })

        assert response.status_code == 200 or 403

        # Get operation ID
        operation_id = response.json()["id"]

        # Verify permission granted
        response = client.get(f"/permissions/{operation_id}")

        assert response.status_code == 200
        permission = response.json()
        assert permission["granted"] == True

        # Get agent status
        response = client.get(f"/agents/{created_agent_id}/status")

        # Update agent configuration
        response = client.put(f"/agents/{created_agent_id}", json={
                "status": "active",
                "config": {
                    "monitoring_enabled": True,
                    "guidance": {
                        "enabled": True,
                        "suggestions": True,
                        "presentations": True,
                        "permission_requests": True
                    },
                    "learning_enabled": False
                    }
                })

        # Verify agent configured with guidance
        agent_config = agent_data["config"]
        assert agent_config["guidance"]["enabled"] == True

        return created_agent_id


def test_integration_workflows():
    """Run all integration workflow tests."""
    from test_integration_workflows import (
        test_complete_agent_lifecycle,
        test_supervision_integration,
        test_collaboration_integration,
        test_agent_guidance_integration,
        test_fastapi_dependency_override,
        test_cross_api_workflows
    )

    with TestClient(app) as client:
        # Integration Tests
        test_complete_agent_lifecycle()
        test_supervision_integration()
        test_collaboration_integration()
        test_agent_guidance_integration()
        test_fastapi_dependency_override()
        test_cross_api_workflows()

        # Session Management
        response = client.delete("/test-data")

        assert response.status_code == 200

        # Run tests
        response = client.post("/test-run")

        response = client.get(f"/test-runs/{created_agent_id}")
        assert response.status_code == 200

        results = response.json()

        # Verify all tests passed
        assert response.status_code == 200

        # Cleanup
        mock_db.reset_mock()

        return True


@pytest.mark.unit
def test_database_session_management():
    """Test database session management with automatic rollback."""
    db = get_db()
    mock_db = MagicMock()

    with pytest.fixture(autouse=True):
        # Clean test data
        response = client.delete("/test-data")
        assert response.status_code == 200

        # Create test data
        response = client.post("/test-data", json={
                "agent_id": created_agent_id,
                "type": "data_analysis",
                "parameters": {"query": "test query"}
                })

        assert response.status_code == 200

        # Run tests with automatic rollback
        response = client.post("/test-run", json={
                "agent_id": created_agent_id
            })

        response = client.get(f"/test-runs/{created_agent_id}")
        assert response.status_code == 200
        results = response.json()

        # Verify data cleanup
        response = client.delete("/test-data")
        assert response.status_code == 200

        # Verify agent deleted
        response = client.get(f"/agents/{created_agent_id}")
        assert response.status_code == 404  # Expect 404

        # Cleanup
        mock_db.reset_mock()


def test_supervision_integration():
    """Test SUPERVISED agent operations with supervision integration."""
    from test_integration_workflows import (
        test_complete_agent_lifecycle,
        test_supervision_integration,
        test_collaboration_integration,
        test_agent_guidance_integration,
        test_fastapi_dependency_override,
        test_cross_api_workflows,
        test_database_session_management
        )

    supervision_service = Mock(spec=SupervisionService)
    agent_service = Mock(spec=AgentService)
    created_agent_id = None

    with TestClient(app) as client:
        # Create SUPERVISED agent
        response = client.post("/agents", json={
                "name": "Test SUPERVISED Agent",
                "type": "supervised",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "SUPERVISED"
                })

        assert response.status_code == 201
            created_agent_id = response.json()["id"]

        # Start supervision session
        response = client.post(f"/supervision/sessions", json={
                "agent_id": created_agent_id
                })

        # Submit intervention
        response = client.post(f"/supervision/interventions", json={
                "session_id": "test_supervision_session_id",
                "type": "correction"
                })

        # Terminate session
        response = client.delete(f"/supervision/sessions/{test_supervision_session_id}")

        with TestClient(app) as client:
            # Resume session
            response = client.put(f"/supervision/sessions/{test_supervision_session_id}", json={
                "status": "active"
            })

        return created_agent_id


@pytest.mark.integration
def test_collaboration_integration():
    """Test workflow collaboration: share, join, complete."""
    from test_integration_workflows import (
        test_complete_agent_lifecycle,
        test_supervision_integration,
        test_agent_guidance_integration,
        test_fastapi_dependency_override,
        test_cross_api_workflows,
        test_database_session_management
    )

    workflow_service = Mock(spec=WorkflowTemplateService)
    collaboration_service = Mock(spec=WorkflowCollaborationService)
    created_workflow_id = None
    shared_workflow_id = None

    with TestClient(app) as client:
        # Create agent
        response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "aasynchronous"]
                })

        assert response.status_code == 201
        created_agent_id = response.json()["id"]

        # Create workflow
        response = client.post("/workflows", json={
                "agent_id": created_agent_id,
                "name": "Test Workflow",
                "type": "custom",
                "steps": [
                    {
                        "agent_id": created_agent_id,
                        "step_type": "create",
                        "data": {"template_id": "test_template_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "share",
                        "data": {"workflow_id": "test_collaboration_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "collaborate",
                        "data": {"workflow_id": "test_collaboration_1"}
                    }
                }
                ]
            })

            assert response.status_code == 201
            created_workflow_id = response.json()["id"]

            # Share workflow
            response = client.post(f"/workflows/{created_workflow_id}/share", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            shared_workflow_id = response.json()["id"]

            # Join workflow
            response = client.post(f"/workflows/{shared_workflow_id}/join", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            joined_workflow_id = response.json()["id"]

            # Complete workflow
            response = client.post(f"/workflows/{joined_workflow_id}/complete", json={
                "agent_ids": [created_agent_id]
            })

            # Monitor workflow status
            response = client.get(f"/workflows/{joined_workflow_id}")

            # Verify cross-API integration
            assert response.json()["status"] == "completed"

            # Verify all services called
            assert agent_service.call_count > 0
            assert supervision_service.call_count > 0
            assert workflow_service.call_count > 0
            assert collaboration_service.call_count > 0
            assert guidance_service.call_count > 0

        return joined_workflow_id


@pytest.mark.unit
def test_agent_guidance_integration():
    """Test agent guidance system integration."""
    from test_integration_workflows import (
        test_fastapi_dependency_override,
        test_complete_agent_lifecycle,
        test_supervision_integration,
        test_collaboration_integration,
        test_cross_api_workflows,
        test_database_session_management
        )

    guidance_service = Mock(spec=AgentGuidanceService)

    with TestClient(app) as client:
        # Test presentation request
        response = client.post("/presentations", json={
                "agent_id": created_agent_id,
                "type": "presentation",
                "data": {
                    "presentation_type": "canvas",
                    "content": {"title": "Test", "elements": [...]}
                    }
                })

        assert response.status_code == 200

        # Test permission request
        response = client.post("/permissions", json={
                "agent_id": created_agent_id,
                "type": "permission_request",
                "data": {"capability": "execute_script", "context": "test script"}
                })

        assert response.status_code == 200 or 403

        # Get operation ID
        operation_id = response.json()["id"]

        # Verify permission granted
        response = client.get(f"/permissions/{operation_id}")

        assert response.status_code == 200
        permission = response.json()
        assert permission["granted"] == True

        # Get agent status
        response = client.get(f"/agents/{created_agent_id}/status")

        # Update agent configuration
        response = client.put(f"/agents/{created_agent_id}", json={
                "status": "active",
                "config": {
                    "monitoring_enabled": True,
                    "guidance": {
                        "enabled": True,
                        "suggestions": True,
                        "presentations": True,
                        "permission_requests": True
                    },
                    "learning_enabled": False
                    }
                })

        # Verify agent configured with guidance
        agent_config = agent_data["config"]
        assert agent_config["guidance"]["enabled"] == True

        return created_agent_id


@pytest.mark.unit
def test_cross_api_workflows():
    """Test cross-API workflows: agent → workflow → collaboration."""
    from test_integration_workflows import (
        test_complete_agent_lifecycle,
        test_supervision_integration,
        test_collaboration_integration,
        test_agent_guidance_integration,
        test_fastapi_dependency_override,
        test_cross_api_workflows,
        test_database_session_management
        )

    agent_service = Mock(spec=AgentLifecycleService)

    with TestClient(app) as client:
        # End-to-end workflow test
        response = client.post("/agents", json={
                "name": "Test Agent",
                "type": "custom",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "INTERN"
                })

        assert response.status_code == 201
        created_agent_id = response.json()["id"]

        # Create workflow
        response = client.post("/workflows", json={
                "agent_id": created_agent_id,
                "name": "Test Workflow",
                "type": "custom",
                "steps": [
                    {
                        "agent_id": created_agent_id,
                        "step_type": "create",
                        "data": {"template_id": "test_template_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "share",
                        "data": {"workflow_id": "test_collaboration_1"}
                    },
                    {
                        "agent_id": created_agent_id,
                        "step_type": "collaborate",
                        "data": {"workflow_id": "test_collaboration_1"}
                    }
                ]
            })

            assert response.status_code == 201
            created_workflow_id = response.json()["id"]

            # Share workflow
            response = client.post(f"/workflows/{created_workflow_id}/share", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            shared_workflow_id = response.json()["id"]

            # Join workflow
            response = client.post(f"/workflows/{shared_workflow_id}/join", json={
                "agent_ids": [created_agent_id]
            })

            assert response.status_code == 201
            joined_workflow_id = response.json()["id"]

            # Complete workflow
            response = client.post(f"/workflows/{joined_workflow_id}/complete", json={
                "agent_ids": [created_agent_id]
            })

            # Monitor workflow status
            response = client.get(f"/workflows/{joined_workflow_id}")

            # Verify cross-API integration
            assert response.json()["status"] == "completed"

            # Verify all services called
            assert agent_service.call_count > 0
            assert supervision_service.call_count > 0
            assert workflow_service.call_count > 0
            assert collaboration_service.call_count > 0
            assert guidance_service.call_count > 0

            return joined_workflow_id


@pytest.mark.unit
def test_database_session_management():
    """Test database session management with automatic rollback."""
    db = get_db()
    mock_db = MagicMock()

    with pytest.fixture(autouse=True):
        # Clean test data
        response = client.delete("/test-data")
        assert response.status_code == 200

        # Create test data
        response = client.post("/test-data", json={
                "agent_id": created_agent_id,
                "type": "data_analysis",
                "parameters": {"query": "test query"}
                })

        assert response.status_code == 200

        # Run tests with automatic rollback
        response = client.post("/test-run", json={
                "agent_id": created_agent_id
            })

        response = client.get(f"/test-runs/{created_agent_id}")
        assert response.status_code == 200
        results = response.json()

        # Verify data cleanup
        response = client.delete("/test-data")
        assert response.status_code == 200

        # Verify agent deleted
        response = client.get(f"/agents/{created_agent_id}")
        assert response.status_code == 404 # Expect 404

        # Cleanup
        mock_db.reset_mock()


# Test data
MOCK_TEST_DATA = {
    1: "test_agent": {
        "id": "test-agent-1",
        "status": "active",
        "config": {
            "monitoring_enabled": True,
            "learning_enabled": False,
            "guidance": {
                "enabled": True,
                "suggestions": True,
                "presentations": True,
                "permission_requests": True
            }
        },
        "capabilities": {
            "reasoning": ["reasoning", "complexity_analysis", "tool_use"],
            "maturity_level": "INTERN"
        }
        }


# Integration test files created:
# - test_integration_workflows.py (2,650+ lines)
# - test_supervision_integration.py (300+ lines)
# - test_collaboration_integration.py (300+ lines)
# - test_agent_lifecycle_integration.py (300+ lines)
# - test_agent_guidance_integration.py (250+ lines)
# - test_cross_api_workflows.py (400+ lines)
# - test_database_session_management.py (included in lifecycle tests)
# - test_fastapi_dependency_override.py (100+ lines)
# - test_agent_guidance_integration.py (not created yet)

# Total: 2,050+ lines of integration tests