"""
Package API Integration Tests

Test coverage for Plan 04 (REST API Integration):
- POST /install with permission checks
- POST /install with vulnerability scanning
- POST /execute with custom images
- DELETE /{skill_id} image cleanup
- GET /{skill_id}/status image status
- GET /audit audit trail
- Error handling (403, 404, 400)
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
import docker

from api.package_routes import router, get_governance, get_installer


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Create test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def mock_governance():
    """Mock package governance service."""
    with patch('api.package_routes.PackageGovernanceService') as mock:
        instance = mock.return_value
        instance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }
        instance.list_packages.return_value = []
        instance.get_cache_stats.return_value = {"hit_rate": 95.0}
        yield instance


@pytest.fixture
def mock_installer():
    """Mock package installer."""
    with patch('api.package_routes.PackageInstaller') as mock:
        instance = mock.return_value
        instance.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:test-skill-v1",
            "vulnerabilities": [],
            "build_logs": ["Step 1/5", "Successfully built"]
        }
        instance.execute_with_packages.return_value = "Output from skill"
        instance.cleanup_skill_image.return_value = True
        yield instance


@pytest.fixture
def autonomous_agent(db_session: Session):
    """Create AUTONOMOUS agent for testing."""
    from core.models import AgentRegistry
    from datetime import datetime

    agent = AgentRegistry(
        id="test-agent-autonomous",
        name="Test Autonomous Agent",
        status="autonomous",
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()

    yield agent

    # Cleanup
    db_session.delete(agent)
    db_session.commit()


@pytest.fixture
def student_agent(db_session: Session):
    """Create STUDENT agent for testing permission denial."""
    from core.models import AgentRegistry
    from datetime import datetime

    agent = AgentRegistry(
        id="test-agent-student",
        name="Test Student Agent",
        status="student",
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()

    yield agent

    # Cleanup
    db_session.delete(agent)
    db_session.commit()


# ============================================================================
# Install Endpoint Tests
# ============================================================================

class TestInstallEndpoint:
    """POST /api/packages/install endpoint."""

    def test_install_with_approved_packages(
        self,
        db_session: Session,
        autonomous_agent,
        mock_governance,
        mock_installer
    ):
        """Test successful package installation with approved packages."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        # Mock permission check for each package
        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": autonomous_agent.id,
                "skill_id": "test-skill",
                "requirements": ["numpy==1.21.0", "pandas>=1.3.0"],
                "scan_for_vulnerabilities": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "atom-skill:test-skill-v1" in data["image_tag"]
        assert len(data["packages_installed"]) == 2
        assert data["packages_installed"][0]["name"] == "numpy"

    def test_install_blocked_for_student_agent(
        self,
        db_session: Session,
        student_agent,
        mock_governance
    ):
        """Test that STUDENT agents are blocked from package installation."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        # Mock STUDENT blocking
        mock_governance.check_package_permission.return_value = {
            "allowed": False,
            "maturity_required": "INTERN",
            "reason": "STUDENT agents cannot execute Python packages (educational restriction)"
        }

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": student_agent.id,
                "skill_id": "test-skill",
                "requirements": ["numpy==1.21.0"]
            }
        )

        assert response.status_code == 403
        assert "Package permission denied" in response.json()["detail"]["error"]

    def test_install_fails_on_vulnerabilities(
        self,
        db_session: Session,
        autonomous_agent,
        mock_governance,
        mock_installer
    ):
        """Test that installation fails when vulnerabilities are detected."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        # Mock permission allowed
        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        # Mock vulnerability detection
        mock_installer.install_packages.return_value = {
            "success": False,
            "error": "Vulnerabilities detected",
            "vulnerabilities": [{"cve_id": "CVE-2021-1234"}]
        }

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": autonomous_agent.id,
                "skill_id": "test-skill",
                "requirements": ["vulnerable-pkg==1.0.0"]
            }
        )

        assert response.status_code == 400
        assert "Vulnerabilities detected" in response.json()["detail"]["error"]

    def test_install_with_invalid_requirement(
        self,
        db_session: Session,
        autonomous_agent
    ):
        """Test that invalid requirement strings return 400 error."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": autonomous_agent.id,
                "skill_id": "test-skill",
                "requirements": ["invalid-package-name!!!"]  # Invalid package name
            }
        )

        assert response.status_code == 400
        assert "Invalid requirement" in response.json()["detail"]["error"]


# ============================================================================
# Execute Endpoint Tests
# ============================================================================

class TestExecuteEndpoint:
    """POST /api/packages/execute endpoint."""

    def test_execute_with_installed_packages(
        self,
        db_session: Session,
        autonomous_agent,
        mock_installer
    ):
        """Test successful execution with installed packages."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        mock_installer.execute_with_packages.return_value = "Output from skill"

        response = client.post(
            "/api/packages/execute",
            json={
                "agent_id": autonomous_agent.id,
                "skill_id": "test-skill",
                "code": "print('hello')",
                "inputs": {},
                "timeout_seconds": 30
            }
        )

        assert response.status_code == 200
        assert response.json()["success"] == True

    def test_execute_fails_without_install(
        self,
        db_session: Session,
        autonomous_agent,
        mock_installer
    ):
        """Test that execution fails when image not found."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        # Mock image not found
        mock_installer.execute_with_packages.side_effect = RuntimeError(
            "Image atom-skill:nonexistent-skill-v1 not found"
        )

        response = client.post(
            "/api/packages/execute",
            json={
                "agent_id": autonomous_agent.id,
                "skill_id": "nonexistent-skill",
                "code": "print('hello')"
            }
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]["error"]


# ============================================================================
# Cleanup Endpoint Tests
# ============================================================================

class TestCleanupEndpoint:
    """DELETE /api/packages/{skill_id} endpoint."""

    def test_cleanup_removes_image(self, mock_installer):
        """Test successful image cleanup."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        mock_installer.cleanup_skill_image.return_value = True

        response = client.delete("/api/packages/test-skill?agent_id=agent-123")

        assert response.status_code == 200
        assert response.json()["success"] == True
        mock_installer.cleanup_skill_image.assert_called_once_with("test-skill")

    def test_cleanup_idempotent(self, mock_installer):
        """Test that cleanup is idempotent (returns success even if image not found)."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        mock_installer.cleanup_skill_image.return_value = False

        response = client.delete("/api/packages/test-skill?agent_id=agent-123")

        assert response.status_code == 200
        assert response.json()["success"] == False


# ============================================================================
# Status Endpoint Tests
# ============================================================================

class TestStatusEndpoint:
    """GET /api/packages/{skill_id}/status endpoint."""

    @patch('docker.from_env')
    def test_status_returns_image_details(self, mock_docker, mock_installer):
        """Test that status endpoint returns image details."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        # Mock Docker client and image
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = {
            "Size": 123456789,
            "Created": "2026-02-19T10:00:00Z",
            "RepoTags": ["atom-skill:test-skill-v1"]
        }
        mock_client.images.get.return_value = mock_image

        response = client.get("/api/packages/test-skill/status")

        assert response.status_code == 200
        data = response.json()
        assert data["image_exists"] == True
        assert data["size_bytes"] > 0

    @patch('docker.from_env')
    def test_status_when_image_not_found(self, mock_docker):
        """Test status endpoint when image does not exist."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        # Mock Docker client
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Mock image not found
        mock_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")

        response = client.get("/api/packages/nonexistent-skill/status")

        assert response.status_code == 200
        data = response.json()
        assert data["image_exists"] == False


# ============================================================================
# Audit Endpoint Tests
# ============================================================================

class TestAuditEndpoint:
    """GET /api/packages/audit endpoint."""

    def test_audit_lists_operations(
        self,
        db_session: Session,
        autonomous_agent
    ):
        """Test that audit endpoint lists package operations."""
        from fastapi.testclient import TestClient
        from main import app
        from core.models import SkillExecution
        from datetime import datetime

        client = TestClient(app)

        # Create test skill execution records
        execution1 = SkillExecution(
            id="exec-1",
            skill_id="test-skill-1",
            skill_source="community",
            status="completed",
            sandbox_enabled=True,
            metadata={"agent_id": autonomous_agent.id},
            created_at=datetime.utcnow()
        )
        execution2 = SkillExecution(
            id="exec-2",
            skill_id="test-skill-2",
            skill_source="community",
            status="failed",
            sandbox_enabled=True,
            metadata={"agent_id": autonomous_agent.id},
            created_at=datetime.utcnow()
        )

        db_session.add(execution1)
        db_session.add(execution2)
        db_session.commit()

        response = client.get(f"/api/packages/audit?agent_id={autonomous_agent.id}")

        assert response.status_code == 200
        data = response.json()
        assert "operations" in data
        assert "count" in data

        # Cleanup
        db_session.delete(execution1)
        db_session.delete(execution2)
        db_session.commit()


# ============================================================================
# Router Registration Tests
# ============================================================================

class TestRouterRegistration:
    """Test that all routes are properly registered."""

    def test_all_endpoints_registered(self):
        """Test that all 11 endpoints are registered."""
        routes = [r.path for r in router.routes]

        # Governance endpoints (Plan 01)
        assert "/check" in routes
        assert "/request" in routes
        assert "/approve" in routes
        assert "/ban" in routes
        assert "/" in routes
        assert "/stats" in routes

        # Package management endpoints (Plan 04)
        assert "/install" in routes
        assert "/execute" in routes
        assert "/{skill_id}" in routes
        assert "/{skill_id}/status" in routes
        assert "/audit" in routes

        # Total route count
        assert len(router.routes) == 11


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
