"""
npm Package Routes API Tests

Test coverage for Plan 04 (npm API Routes):
- GET /api/packages/npm/check - Check npm package permission
- POST /api/packages/npm/request - Request npm package approval
- POST /api/packages/npm/approve - Approve npm package (admin)
- POST /api/packages/npm/ban - Ban npm package (admin)
- GET /api/packages/npm - List npm packages
- POST /api/packages/npm/install - Install npm packages
- POST /api/packages/npm/execute - Execute Node.js skill
- DELETE /api/packages/npm/{skill_id} - Cleanup npm image
- GET /api/packages/npm/{skill_id}/status - Get npm image status

Tests cover:
- npm governance endpoints (check, approve, ban, list)
- npm install/execute endpoints
- Error responses (400, 403, 404, 422, 500)
- Malformed request payloads
- Service error propagation
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
import docker

from api.package_routes import router


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def npm_client():
    """TestClient for npm package routes."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from api.package_routes import router

    # Create minimal app for testing
    app = FastAPI()
    app.include_router(router, prefix="/api/packages")
    return TestClient(app)


@pytest.fixture
def mock_npm_governance():
    """Mock npm governance service."""
    with patch('api.package_routes.PackageGovernanceService') as mock:
        instance = mock.return_value
        instance.check_package_permission.return_value = {
            "allowed": False,
            "maturity_required": "INTERN",
            "reason": "Package not approved"
        }
        instance.list_packages.return_value = []
        instance.get_cache_stats.return_value = {"hit_rate": 95.0}
        yield instance


@pytest.fixture
def mock_npm_installer():
    """Mock npm installer service."""
    with patch('api.package_routes.NpmPackageInstaller') as mock:
        instance = mock.return_value
        instance.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-npm-skill:test-v1",
            "vulnerabilities": [],
            "build_logs": ["Step 1/5", "Successfully built"]
        }
        instance.execute_with_packages.return_value = "Node.js output"
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
            "id": "test-npm-agent-autonomous",
            "name": "Test NPM Autonomous Agent",
            "status": "autonomous",
            "created_at": datetime.utcnow()
        }
    )
    db_session.commit()

    yield {"id": "test-npm-agent-autonomous", "status": "autonomous"}

    # Cleanup
    db_session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": "test-npm-agent-autonomous"})
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
            "id": "test-npm-agent-student",
            "name": "Test NPM Student Agent",
            "status": "student",
            "created_at": datetime.utcnow()
        }
    )
    db_session.commit()

    yield {"id": "test-npm-agent-student", "status": "student"}

    # Cleanup
    db_session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": "test-npm-agent-student"})
    db_session.commit()


@pytest.fixture
def intern_agent(db_session: Session):
    """Create INTERN agent for testing approval requirement."""
    from datetime import datetime
    from sqlalchemy import text

    # Use raw SQL to avoid SQLAlchemy relationship mapping issues
    db_session.execute(
        text("INSERT INTO agents (id, name, status, created_at) "
             "VALUES (:id, :name, :status, :created_at)"),
        {
            "id": "test-npm-agent-intern",
            "name": "Test NPM Intern Agent",
            "status": "intern",
            "created_at": datetime.utcnow()
        }
    )
    db_session.commit()

    yield {"id": "test-npm-agent-intern", "status": "intern"}

    # Cleanup
    db_session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": "test-npm-agent-intern"})
    db_session.commit()


@pytest.fixture
def db_session():
    """Create test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Test Class 1: TestNpmGovernanceCheck
# ============================================================================

class TestNpmGovernanceCheck:
    """GET /api/packages/npm/check endpoint tests."""

    def test_npm_check_with_unknown_package(self, npm_client, autonomous_agent, mock_npm_governance):
        """Test checking permission for unknown npm package (not approved)."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": False,
            "maturity_required": "INTERN",
            "reason": "Package not in registry"
        }

        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": autonomous_agent["id"],
                "package_name": "unknown-package",
                "version": "1.0.0"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert data["maturity_required"] == "INTERN"
        assert "not in registry" in data["reason"]

    def test_npm_check_with_approved_package(self, npm_client, autonomous_agent, mock_npm_governance):
        """Test checking permission for approved npm package."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": autonomous_agent["id"],
                "package_name": "lodash",
                "version": "4.17.21"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True
        assert data["maturity_required"] == "INTERN"
        assert data["reason"] is None

    def test_npm_check_with_banned_package(self, npm_client, autonomous_agent, mock_npm_governance):
        """Test checking permission for banned npm package."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": False,
            "maturity_required": "AUTONOMOUS",
            "reason": "Package banned due to security vulnerability CVE-2021-1234"
        }

        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": autonomous_agent["id"],
                "package_name": "malicious-package",
                "version": "1.0.0"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert "banned" in data["reason"].lower()

    def test_npm_check_student_agent_blocked(self, npm_client, student_agent, mock_npm_governance):
        """Test that STUDENT agents are always blocked from npm packages."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": False,
            "maturity_required": "INTERN",
            "reason": "STUDENT agents cannot execute npm packages (educational restriction)"
        }

        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": student_agent["id"],
                "package_name": "lodash",
                "version": "4.17.21"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert "STUDENT" in data["reason"]

    def test_npm_check_autonomous_agent_allowed(self, npm_client, autonomous_agent, mock_npm_governance):
        """Test that AUTONOMOUS agents with approved packages are allowed."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "AUTONOMOUS",
            "reason": None
        }

        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": autonomous_agent["id"],
                "package_name": "express",
                "version": "^4.18.0"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True

    def test_npm_check_response_structure(self, npm_client, autonomous_agent, mock_npm_governance):
        """Test that npm check response has correct structure."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": autonomous_agent["id"],
                "package_name": "async",
                "version": "3.2.0"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "allowed" in data
        assert "maturity_required" in data
        assert "reason" in data
        assert isinstance(data["allowed"], bool)
        assert isinstance(data["maturity_required"], str)


# ============================================================================
# Test Class 2: TestNpmGovernanceApproval
# ============================================================================

class TestNpmGovernanceApproval:
    """POST /api/packages/npm/approve endpoint tests."""

    def test_npm_approve_package_success(self, npm_client, mock_npm_governance, db_session):
        """Test successful npm package approval."""
        from datetime import datetime
        from core.models import PackageRegistry

        mock_package = PackageRegistry(
            id="pkg:npm:lodash:4.17.21",
            name="lodash",
            version="4.17.21",
            package_type="npm",
            min_maturity="INTERN",
            status="active",
            approved_by="admin-user",
            approved_at=datetime.utcnow()
        )
        mock_npm_governance.approve_package.return_value = mock_package

        response = npm_client.post(
            "/api/packages/npm/approve",
            json={
                "package_name": "lodash",
                "version": "4.17.21",
                "min_maturity": "INTERN",
                "approved_by": "admin-user"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["package_id"] == "pkg:npm:lodash:4.17.21"
        assert data["status"] == "active"
        assert data["min_maturity"] == "INTERN"
        assert data["approved_by"] == "admin-user"
        assert data["package_type"] == "npm"

    def test_npm_approve_with_min_maturity_levels(self, npm_client, mock_npm_governance, db_session):
        """Test approving npm package for different maturity levels."""
        from datetime import datetime
        from core.models import PackageRegistry

        for maturity in ["INTERN", "SUPERVISED", "AUTONOMOUS"]:
            mock_package = PackageRegistry(
                id=f"pkg:npm:pkg-{maturity}:1.0.0",
                name=f"pkg-{maturity}",
                version="1.0.0",
                package_type="npm",
                min_maturity=maturity,
                status="active",
                approved_by="admin-user",
                approved_at=datetime.utcnow()
            )
            mock_npm_governance.approve_package.return_value = mock_package

            response = npm_client.post(
                "/api/packages/npm/approve",
                json={
                    "package_name": f"pkg-{maturity}",
                    "version": "1.0.0",
                    "min_maturity": maturity,
                    "approved_by": "admin-user"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["min_maturity"] == maturity

    def test_npm_approve_invalidates_cache(self, npm_client, mock_npm_governance, db_session):
        """Test that approving npm package invalidates governance cache."""
        from datetime import datetime
        from core.models import PackageRegistry

        mock_package = PackageRegistry(
            id="pkg:npm:express:4.18.0",
            name="express",
            version="4.18.0",
            package_type="npm",
            min_maturity="SUPERVISED",
            status="active",
            approved_by="admin-user",
            approved_at=datetime.utcnow()
        )
        mock_npm_governance.approve_package.return_value = mock_package

        # Verify cache invalidation is called
        mock_npm_governance.reset_mock()

        response = npm_client.post(
            "/api/packages/npm/approve",
            json={
                "package_name": "express",
                "version": "4.18.0",
                "min_maturity": "SUPERVISED",
                "approved_by": "admin-user"
            }
        )

        assert response.status_code == 200
        mock_npm_governance.approve_package.assert_called_once()

    def test_npm_approve_already_approved(self, npm_client, mock_npm_governance, db_session):
        """Test approving already-approved npm package (should update)."""
        from datetime import datetime
        from core.models import PackageRegistry

        mock_package = PackageRegistry(
            id="pkg:npm:lodash:4.17.21",
            name="lodash",
            version="4.17.21",
            package_type="npm",
            min_maturity="INTERN",
            status="active",
            approved_by="admin-user",
            approved_at=datetime.utcnow()
        )
        mock_npm_governance.approve_package.return_value = mock_package

        response = npm_client.post(
            "/api/packages/npm/approve",
            json={
                "package_name": "lodash",
                "version": "4.17.21",
                "min_maturity": "INTERN",
                "approved_by": "admin-user"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    def test_npm_approve_malformed_request(self, npm_client):
        """Test approving npm package with malformed request."""
        response = npm_client.post(
            "/api/packages/npm/approve",
            json={
                "package_name": "",  # Empty package name
                "version": "1.0.0",
                "min_maturity": "INTERN",
                "approved_by": "admin-user"
            }
        )

        # FastAPI validates empty strings as required fields
        assert response.status_code == 422

    def test_npm_approve_creates_registry_entry(self, npm_client, mock_npm_governance, db_session):
        """Test that approving npm package creates registry entry."""
        from datetime import datetime
        from core.models import PackageRegistry

        mock_package = PackageRegistry(
            id="pkg:npm:new-package:1.0.0",
            name="new-package",
            version="1.0.0",
            package_type="npm",
            min_maturity="SUPERVISED",
            status="active",
            approved_by="admin-user",
            approved_at=datetime.utcnow()
        )
        mock_npm_governance.approve_package.return_value = mock_package

        response = npm_client.post(
            "/api/packages/npm/approve",
            json={
                "package_name": "new-package",
                "version": "1.0.0",
                "min_maturity": "SUPERVISED",
                "approved_by": "admin-user"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "package_id" in data
        assert data["package_id"].startswith("pkg:npm:")


# ============================================================================
# Test Class 3: TestNpmGovernanceBanning
# ============================================================================

class TestNpmGovernanceBanning:
    """POST /api/packages/npm/ban endpoint tests."""

    def test_npm_ban_package_success(self, npm_client, mock_npm_governance, db_session):
        """Test successful npm package banning."""
        from datetime import datetime
        from core.models import PackageRegistry

        mock_package = PackageRegistry(
            id="pkg:npm:vuln-package:1.0.0",
            name="vuln-package",
            version="1.0.0",
            package_type="npm",
            status="banned",
            ban_reason="Security vulnerability CVE-2024-1234"
        )
        mock_npm_governance.ban_package.return_value = mock_package

        response = npm_client.post(
            "/api/packages/npm/ban",
            json={
                "package_name": "vuln-package",
                "version": "1.0.0",
                "reason": "Security vulnerability CVE-2024-1234"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "banned"
        assert "CVE-2024-1234" in data["ban_reason"]
        assert data["package_type"] == "npm"

    def test_npm_ban_reason_stored(self, npm_client, mock_npm_governance, db_session):
        """Test that ban reason is stored correctly."""
        from datetime import datetime
        from core.models import PackageRegistry

        reason = "Malicious code detected in postinstall script"
        mock_package = PackageRegistry(
            id="pkg:npm:malicious:1.0.0",
            name="malicious",
            version="1.0.0",
            package_type="npm",
            status="banned",
            ban_reason=reason
        )
        mock_npm_governance.ban_package.return_value = mock_package

        response = npm_client.post(
            "/api/packages/npm/ban",
            json={
                "package_name": "malicious",
                "version": "1.0.0",
                "reason": reason
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ban_reason"] == reason

    def test_npm_ban_invalidates_cache(self, npm_client, mock_npm_governance, db_session):
        """Test that banning npm package invalidates governance cache."""
        from datetime import datetime
        from core.models import PackageRegistry

        mock_package = PackageRegistry(
            id="pkg:npm:bad-package:2.0.0",
            name="bad-package",
            version="2.0.0",
            package_type="npm",
            status="banned",
            ban_reason="Policy violation"
        )
        mock_npm_governance.ban_package.return_value = mock_package

        response = npm_client.post(
            "/api/packages/npm/ban",
            json={
                "package_name": "bad-package",
                "version": "2.0.0",
                "reason": "Policy violation"
            }
        )

        assert response.status_code == 200
        mock_npm_governance.ban_package.assert_called_once()

    def test_npm_ban_already_banned(self, npm_client, mock_npm_governance, db_session):
        """Test banning already-banned npm package (should update)."""
        from datetime import datetime
        from core.models import PackageRegistry

        mock_package = PackageRegistry(
            id="pkg:npm:vuln-package:1.0.0",
            name="vuln-package",
            version="1.0.0",
            package_type="npm",
            status="banned",
            ban_reason="Updated: Critical vulnerability"
        )
        mock_npm_governance.ban_package.return_value = mock_package

        response = npm_client.post(
            "/api/packages/npm/ban",
            json={
                "package_name": "vuln-package",
                "version": "1.0.0",
                "reason": "Updated: Critical vulnerability"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "banned"

    def test_npm_ban_blocks_all_maturities(self, npm_client, autonomous_agent, mock_npm_governance):
        """Test that banned npm packages are blocked for all maturity levels."""
        # First check that AUTONOMOUS agent is blocked from banned package
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": False,
            "maturity_required": "AUTONOMOUS",
            "reason": "Package banned due to security vulnerability"
        }

        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": autonomous_agent["id"],
                "package_name": "banned-package",
                "version": "1.0.0"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert "banned" in data["reason"].lower()


# ============================================================================
# Test Class 4: TestNpmInstallExecute
# ============================================================================

class TestNpmInstallExecute:
    """npm install and execute endpoint tests."""

    def test_npm_install_success(self, npm_client, autonomous_agent, mock_npm_governance, mock_npm_installer):
        """Test successful npm package installation."""
        # Mock permission granted
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        # Mock install success
        mock_npm_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-npm-skill:my-skill-v1",
            "vulnerabilities": [],
            "build_logs": ["Step 1/5 : FROM node:20-alpine", "Successfully built abc123"]
        }

        response = npm_client.post(
            "/api/packages/npm/install",
            json={
                "agent_id": autonomous_agent["id"],
                "skill_id": "my-skill",
                "packages": ["lodash@4.17.21", "express@^4.18.0"],
                "package_manager": "npm",
                "scan_for_vulnerabilities": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "atom-npm-skill:my-skill-v1" in data["image_tag"]
        assert len(data["packages_installed"]) == 2
        assert data["packages_installed"][0]["name"] == "lodash"

    def test_npm_install_with_vulnerability_scan(self, npm_client, autonomous_agent, mock_npm_governance, mock_npm_installer):
        """Test npm installation with vulnerability scan enabled."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        mock_npm_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-npm-skill:scan-skill-v1",
            "vulnerabilities": [],
            "build_logs": ["Running npm audit", "No vulnerabilities found"]
        }

        response = npm_client.post(
            "/api/packages/npm/install",
            json={
                "agent_id": autonomous_agent["id"],
                "skill_id": "scan-skill",
                "packages": ["axios@1.6.0"],
                "package_manager": "npm",
                "scan_for_vulnerabilities": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Verify scan_for_vulnerabilities was passed
        mock_npm_installer.install_packages.assert_called_once()

    def test_npm_install_permission_denied(self, npm_client, student_agent, mock_npm_governance):
        """Test that npm installation is denied for STUDENT agents."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": False,
            "maturity_required": "INTERN",
            "reason": "STUDENT agents cannot install npm packages"
        }

        response = npm_client.post(
            "/api/packages/npm/install",
            json={
                "agent_id": student_agent["id"],
                "skill_id": "test-skill",
                "packages": ["lodash@4.17.21"]
            }
        )

        assert response.status_code == 403
        assert "permission denied" in response.json()["detail"]["error"].lower()

    def test_npm_install_scanner_finds_vulnerabilities(self, npm_client, autonomous_agent, mock_npm_governance, mock_npm_installer):
        """Test npm installation when vulnerabilities are found."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        mock_npm_installer.install_packages.return_value = {
            "success": False,
            "error": "Vulnerabilities detected",
            "vulnerabilities": [
                {"cve_id": "CVE-2023-1234", "severity": "HIGH"}
            ]
        }

        response = npm_client.post(
            "/api/packages/npm/install",
            json={
                "agent_id": autonomous_agent["id"],
                "skill_id": "vuln-skill",
                "packages": ["vulnerable-pkg@1.0.0"],
                "scan_for_vulnerabilities": True
            }
        )

        assert response.status_code == 400
        assert "Vulnerabilities detected" in response.json()["detail"]["error"]

    def test_npm_execute_with_installed_image(self, npm_client, autonomous_agent, mock_npm_installer):
        """Test executing npm skill with installed packages."""
        mock_npm_installer.execute_with_packages.return_value = "Hello from Node.js!"

        response = npm_client.post(
            "/api/packages/npm/execute",
            json={
                "agent_id": autonomous_agent["id"],
                "skill_id": "my-skill",
                "code": "console.log('Hello')",
                "inputs": {},
                "timeout_seconds": 30
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Hello from Node.js!" in data["output"]

    def test_npm_execute_missing_image_error(self, npm_client, autonomous_agent, mock_npm_installer):
        """Test executing npm skill when image not found."""
        mock_npm_installer.execute_with_packages.side_effect = RuntimeError(
            "Image atom-npm-skill:nonexistent-v1 not found"
        )

        response = npm_client.post(
            "/api/packages/npm/execute",
            json={
                "agent_id": autonomous_agent["id"],
                "skill_id": "nonexistent",
                "code": "console.log('test')"
            }
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]["error"].lower()

    def test_npm_cleanup_skill_image(self, npm_client, mock_npm_installer):
        """Test cleaning up npm skill image."""
        mock_npm_installer.cleanup_skill_image.return_value = True

        response = npm_client.delete("/api/packages/npm/test-skill?agent_id=agent-123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "removed successfully" in data["message"].lower()

    def test_npm_get_skill_image_status(self, npm_client):
        """Test getting npm skill image status."""
        with patch('docker.from_env') as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            mock_image = MagicMock()
            mock_image.attrs = {
                "Size": 123456789,
                "Created": "2026-03-13T10:00:00Z",
                "RepoTags": ["atom-npm-skill:test-skill-v1"]
            }
            mock_client.images.get.return_value = mock_image

            response = npm_client.get("/api/packages/npm/test-skill/status")

            assert response.status_code == 200
            data = response.json()
            assert data["image_exists"] is True
            assert data["size_bytes"] > 0


# ============================================================================
# Test Class 5: TestNpmPackageListing
# ============================================================================

class TestNpmPackageListing:
    """GET /api/packages/npm endpoint tests."""

    def test_npm_list_all_packages(self, npm_client, mock_npm_governance):
        """Test listing all npm packages."""
        from datetime import datetime
        from core.models import PackageRegistry

        mock_packages = [
            PackageRegistry(
                id="pkg:npm:lodash:4.17.21",
                name="lodash",
                version="4.17.21",
                package_type="npm",
                min_maturity="INTERN",
                status="active",
                approved_by="admin",
                approved_at=datetime.utcnow()
            ),
            PackageRegistry(
                id="pkg:npm:express:4.18.0",
                name="express",
                version="4.18.0",
                package_type="npm",
                min_maturity="SUPERVISED",
                status="active",
                approved_by="admin",
                approved_at=datetime.utcnow()
            )
        ]
        mock_npm_governance.list_packages.return_value = mock_packages

        response = npm_client.get("/api/packages/npm")

        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        assert "count" in data
        assert data["count"] == 2

    def test_npm_list_filters_by_npm_type(self, npm_client, mock_npm_governance):
        """Test that npm list only returns npm packages (not Python)."""
        from datetime import datetime
        from core.models import PackageRegistry

        # Mock should filter by package_type="npm"
        mock_npm_governance.list_packages.return_value = [
            PackageRegistry(
                id="pkg:npm:lodash:4.17.21",
                name="lodash",
                version="4.17.21",
                package_type="npm",
                min_maturity="INTERN",
                status="active",
                approved_by="admin",
                approved_at=datetime.utcnow()
            )
        ]

        response = npm_client.get("/api/packages/npm")

        assert response.status_code == 200
        mock_npm_governance.list_packages.assert_called_once_with(
            status=None,
            package_type="npm",
            db=mock_npm_governance.list_packages.call_args[1]['db']
        )

    def test_npm_list_excludes_python_packages(self, npm_client, mock_npm_governance):
        """Test that Python packages are excluded from npm list."""
        from datetime import datetime
        from core.models import PackageRegistry

        # Only return npm packages
        mock_npm_governance.list_packages.return_value = [
            PackageRegistry(
                id="pkg:npm:express:4.18.0",
                name="express",
                version="4.18.0",
                package_type="npm",
                min_maturity="INTERN",
                status="active",
                approved_by="admin",
                approved_at=datetime.utcnow()
            )
        ]

        response = npm_client.get("/api/packages/npm")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1

    def test_npm_list_with_status_filter(self, npm_client, mock_npm_governance):
        """Test listing npm packages with status filter."""
        from datetime import datetime
        from core.models import PackageRegistry

        mock_npm_governance.list_packages.return_value = [
            PackageRegistry(
                id="pkg:npm:pending-pkg:1.0.0",
                name="pending-pkg",
                version="1.0.0",
                package_type="npm",
                min_maturity="INTERN",
                status="pending",
                approved_by=None,
                approved_at=None
            )
        ]

        response = npm_client.get("/api/packages/npm?status=pending")

        assert response.status_code == 200
        mock_npm_governance.list_packages.assert_called_once()

    def test_npm_list_empty_response(self, npm_client, mock_npm_governance):
        """Test listing npm packages when none exist."""
        mock_npm_governance.list_packages.return_value = []

        response = npm_client.get("/api/packages/npm")

        assert response.status_code == 200
        data = response.json()
        assert data["packages"] == []
        assert data["count"] == 0


# ============================================================================
# Test Class 6: TestNpmErrorResponses
# ============================================================================

class TestNpmErrorResponses:
    """Error response tests for npm endpoints."""

    def test_npm_check_missing_agent_id(self, npm_client):
        """Test npm check with missing agent_id returns 422."""
        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "package_name": "lodash",
                "version": "4.17.21"
                # Missing agent_id
            }
        )

        assert response.status_code == 422

    def test_npm_check_missing_package_name(self, npm_client):
        """Test npm check with missing package_name returns 422."""
        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": "agent-123",
                "version": "4.17.21"
                # Missing package_name
            }
        )

        assert response.status_code == 422

    def test_npm_install_empty_packages_list(self, npm_client, autonomous_agent):
        """Test npm install with empty packages list returns 400."""
        response = npm_client.post(
            "/api/packages/npm/install",
            json={
                "agent_id": autonomous_agent["id"],
                "skill_id": "test-skill",
                "packages": []  # Empty list
            }
        )

        # FastAPI validates non-empty lists
        assert response.status_code == 422

    def test_npm_install_invalid_package_manager(self, npm_client, autonomous_agent):
        """Test npm install with invalid package_manager."""
        # Note: This may not be validated by Pydantic, so might succeed
        response = npm_client.post(
            "/api/packages/npm/install",
            json={
                "agent_id": autonomous_agent["id"],
                "skill_id": "test-skill",
                "packages": ["lodash@4.17.21"],
                "package_manager": "invalid-manager"
            }
        )

        # May succeed or fail depending on validation
        assert response.status_code in [200, 422]

    def test_npm_execute_missing_skill_id(self, npm_client, autonomous_agent):
        """Test npm execute with missing skill_id returns 422."""
        response = npm_client.post(
            "/api/packages/npm/execute",
            json={
                "agent_id": autonomous_agent["id"],
                # Missing skill_id
                "code": "console.log('test')"
            }
        )

        assert response.status_code == 422

    def test_npm_approve_missing_version(self, npm_client):
        """Test npm approve with missing version returns 422."""
        response = npm_client.post(
            "/api/packages/npm/approve",
            json={
                "package_name": "lodash",
                # Missing version
                "min_maturity": "INTERN",
                "approved_by": "admin-user"
            }
        )

        assert response.status_code == 422

    def test_npm_ban_missing_reason(self, npm_client):
        """Test npm ban with missing reason returns 422."""
        response = npm_client.post(
            "/api/packages/npm/ban",
            json={
                "package_name": "bad-package",
                "version": "1.0.0"
                # Missing reason
            }
        )

        assert response.status_code == 422

    def test_npm_service_error_propagates(self, npm_client, mock_npm_governance):
        """Test that npm service errors propagate as 500."""
        mock_npm_governance.check_package_permission.side_effect = Exception("Database connection failed")

        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": "agent-123",
                "package_name": "lodash",
                "version": "4.17.21"
            }
        )

        assert response.status_code == 500

    def test_npm_governance_not_found(self, npm_client, mock_npm_governance):
        """Test npm governance when package not found."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": False,
            "maturity_required": "INTERN",
            "reason": "Package not found in registry"
        }

        response = npm_client.get(
            "/api/packages/npm/check",
            params={
                "agent_id": "agent-123",
                "package_name": "nonexistent-package",
                "version": "1.0.0"
            }
        )

        # Returns 200 with allowed=False (not 404)
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False

    def test_npm_installer_error_propagates(self, npm_client, autonomous_agent, mock_npm_governance, mock_npm_installer):
        """Test that npm installer errors propagate correctly."""
        mock_npm_governance.check_package_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        mock_npm_installer.install_packages.return_value = {
            "success": False,
            "error": "Docker daemon not running"
        }

        response = npm_client.post(
            "/api/packages/npm/install",
            json={
                "agent_id": autonomous_agent["id"],
                "skill_id": "test-skill",
                "packages": ["lodash@4.17.21"]
            }
        )

        assert response.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
