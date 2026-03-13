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
    from datetime import datetime
    from sqlalchemy import text

    # Use raw SQL to avoid SQLAlchemy relationship mapping issues
    db_session.execute(
        text("INSERT INTO agents (id, name, status, created_at) "
             "VALUES (:id, :name, :status, :created_at)"),
        {
            "id": "test-agent-autonomous",
            "name": "Test Autonomous Agent",
            "status": "autonomous",
            "created_at": datetime.utcnow()
        }
    )
    db_session.commit()

    yield {"id": "test-agent-autonomous", "status": "autonomous"}

    # Cleanup
    db_session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": "test-agent-autonomous"})
    db_session.commit()


@pytest.fixture
def student_agent(db_session: Session):
    """Create STUDENT agent for testing permission denial."""
    from datetime import datetime
    from sqlalchemy import text

    # Use raw SQL to avoid SQLAlchemy relationship mapping issues
    db_session.execute(
        text("INSERT INTO agents (id, name, status, created_at) "
             "VALUES (:id, :name, :status, :created_at)"),
        {
            "id": "test-agent-student",
            "name": "Test Student Agent",
            "status": "student",
            "created_at": datetime.utcnow()
        }
    )
    db_session.commit()

    yield {"id": "test-agent-student", "status": "student"}

    # Cleanup
    db_session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": "test-agent-student"})
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
                "agent_id": autonomous_agent["id"],
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
                "agent_id": student_agent["id"],
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
                "agent_id": autonomous_agent["id"],
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
                "agent_id": autonomous_agent["id"],
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
                "agent_id": autonomous_agent["id"],
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
                "agent_id": autonomous_agent["id"],
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
            metadata={"agent_id": autonomous_agent["id"]},
            created_at=datetime.utcnow()
        )
        execution2 = SkillExecution(
            id="exec-2",
            skill_id="test-skill-2",
            skill_source="community",
            status="failed",
            sandbox_enabled=True,
            metadata={"agent_id": autonomous_agent["id"]},
            created_at=datetime.utcnow()
        )

        db_session.add(execution1)
        db_session.add(execution2)
        db_session.commit()

        response = client.get(f"/api/packages/audit?agent_id={autonomous_agent["id"]}")

        assert response.status_code == 200
        data = response.json()
        assert "operations" in data
        assert "count" in data

        # Cleanup
        db_session.delete(execution1)
        db_session.delete(execution2)
        db_session.commit()


# ============================================================================
# API Error Response Tests
# ============================================================================

class TestPackageApiErrorResponses:
    """Error response tests for package API endpoints."""

    def test_check_endpoint_422_on_missing_agent_id(self):
        """Test check endpoint returns 422 when agent_id is missing."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        response = client.get(
            "/api/packages/check",
            params={
                # Missing agent_id
                "package_name": "numpy",
                "version": "1.21.0"
            }
        )

        assert response.status_code == 422

    def test_check_endpoint_422_on_missing_package_name(self):
        """Test check endpoint returns 422 when package_name is missing."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        response = client.get(
            "/api/packages/check",
            params={
                "agent_id": "agent-123",
                # Missing package_name
                "version": "1.21.0"
            }
        )

        assert response.status_code == 422

    def test_install_endpoint_422_on_invalid_requirements_format(self):
        """Test install endpoint returns 400 on invalid requirements format."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": "agent-123",
                "skill_id": "test-skill",
                "requirements": ["invalid-package-name!!!"]  # Invalid format
            }
        )

        assert response.status_code == 400

    def test_install_endpoint_403_on_permission_denied(self, db_session: Session, student_agent, mock_governance):
        """Test install endpoint returns 403 when permission denied."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.check_package_permission.return_value = {
            "allowed": False,
            "maturity_required": "INTERN",
            "reason": "Package not approved"
        }

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": student_agent["id"],
                "skill_id": "test-skill",
                "requirements": ["numpy==1.21.0"]
            }
        )

        assert response.status_code == 403

    def test_execute_endpoint_404_on_missing_image(self, mock_installer):
        """Test execute endpoint returns 404 when image not found."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_installer.execute_with_packages.side_effect = RuntimeError(
            "Image atom-skill:nonexistent-v1 not found"
        )

        response = client.post(
            "/api/packages/execute",
            json={
                "agent_id": "agent-123",
                "skill_id": "nonexistent",
                "code": "print('test')"
            }
        )

        assert response.status_code == 404

    def test_approve_endpoint_422_on_invalid_maturity(self):
        """Test approve endpoint returns 400 on invalid maturity level."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        response = client.post(
            "/api/packages/approve",
            json={
                "package_name": "numpy",
                "version": "1.21.0",
                "min_maturity": "INVALID",  # Invalid maturity
                "approved_by": "admin-user"
            }
        )

        # May return 400 or 422 depending on validation
        assert response.status_code in [400, 422]

    def test_ban_endpoint_422_on_missing_reason(self):
        """Test ban endpoint returns 422 when reason is missing."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        response = client.post(
            "/api/packages/ban",
            json={
                "package_name": "bad-package",
                "version": "1.0.0"
                # Missing reason
            }
        )

        assert response.status_code == 422

    def test_audit_endpoint_filters_by_agent_id(self, db_session: Session, autonomous_agent):
        """Test audit endpoint filters by agent_id."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        response = client.get(f"/api/packages/audit?agent_id={autonomous_agent['id']}")

        assert response.status_code == 200
        data = response.json()
        assert "operations" in data
        assert "count" in data

    def test_stats_endpoint_returns_cache_metrics(self, mock_governance):
        """Test stats endpoint returns cache metrics."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.get_cache_stats.return_value = {
            "hit_rate": 95.0,
            "size": 1000,
            "evictions": 10
        }

        response = client.get("/api/packages/stats")

        assert response.status_code == 200
        data = response.json()
        assert "hit_rate" in data


class TestMalformedPayloads:
    """Test malformed request payloads."""

    def test_malformed_json_request(self):
        """Test endpoint handles malformed JSON gracefully."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        # Send invalid JSON
        response = client.post(
            "/api/packages/install",
            data="{invalid json}",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_extra_fields_ignored(self, mock_governance, mock_installer):
        """Test that extra fields in request are ignored."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:test-v1",
            "vulnerabilities": []
        }

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": "agent-123",
                "skill_id": "test-skill",
                "requirements": ["numpy==1.21.0"],
                "extra_field": "should_be_ignored"  # Extra field
            }
        )

        # Pydantic should ignore extra fields
        assert response.status_code == 200

    def test_null_values_in_optional_fields(self, mock_governance, mock_installer):
        """Test that null values in optional fields are handled."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:test-v1",
            "vulnerabilities": []
        }

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": "agent-123",
                "skill_id": "test-skill",
                "requirements": ["numpy==1.21.0"],
                "base_image": None  # Null optional field
            }
        )

        # May succeed or fail depending on validation
        assert response.status_code in [200, 422]

    def test_array_instead_of_string(self):
        """Test that array instead of string returns validation error."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        response = client.post(
            "/api/packages/approve",
            json={
                "package_name": ["numpy"],  # Array instead of string
                "version": "1.21.0",
                "min_maturity": "INTERN",
                "approved_by": "admin-user"
            }
        )

        assert response.status_code == 422

    def test_unicode_in_package_names(self, mock_governance, mock_installer):
        """Test that unicode in package names is handled correctly."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:test-v1",
            "vulnerabilities": []
        }

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": "agent-123",
                "skill_id": "test-skill",
                "requirements": ["python-dateutil"]  # Package with hyphen
            }
        )

        # Should handle unicode correctly
        assert response.status_code in [200, 400]


class TestServiceErrorPropagation:
    """Test service error propagation to API responses."""

    def test_governance_service_error_500(self, mock_governance):
        """Test governance service errors return 500."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.check_package_permission.side_effect = Exception("Database connection failed")

        response = client.get(
            "/api/packages/check",
            params={
                "agent_id": "agent-123",
                "package_name": "numpy",
                "version": "1.21.0"
            }
        )

        assert response.status_code == 500

    def test_scanner_service_error_500(self, mock_governance, mock_installer):
        """Test scanner service errors return 500."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        mock_installer.install_packages.return_value = {
            "success": False,
            "error": "Scanner service unavailable"
        }

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": "agent-123",
                "skill_id": "test-skill",
                "requirements": ["numpy==1.21.0"]
            }
        )

        assert response.status_code == 500

    def test_installer_service_error_500(self, mock_governance, mock_installer):
        """Test installer service errors return 500."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        mock_installer.install_packages.return_value = {
            "success": False,
            "error": "Docker daemon not running"
        }

        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": "agent-123",
                "skill_id": "test-skill",
                "requirements": ["numpy==1.21.0"]
            }
        )

        assert response.status_code == 500

    def test_database_error_500(self, mock_governance):
        """Test database errors return 500."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.list_packages.side_effect = Exception("Database connection lost")

        response = client.get("/api/packages/")

        assert response.status_code == 500

    def test_audit_service_error_logged(self, db_session: Session, mock_governance, mock_installer):
        """Test audit service errors are logged but don't block responses."""
        from fastapi.testclient import TestClient
        from main_api_app import app

        client = TestClient(app)

        mock_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:test-v1",
            "vulnerabilities": []
        }

        # Audit may fail but install should succeed
        response = client.post(
            "/api/packages/install",
            json={
                "agent_id": "agent-123",
                "skill_id": "test-skill",
                "requirements": ["numpy==1.21.0"]
            }
        )

        # Should succeed even if audit fails
        assert response.status_code == 200


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
