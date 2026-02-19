"""
Tests for npm package REST API endpoints.

Tests cover:
- Governance endpoints (check, request, approve, ban)
- Installation endpoints (install with script analysis and vulnerability scanning)
- Execution endpoints (execute Node.js code)
- Utility endpoints (list, cleanup, status)
- Permission enforcement by agent maturity
- Malicious script blocking
- Vulnerability blocking
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from core.database import get_db
from core.models import AgentRegistry, PackageRegistry
from api.package_routes import router


# Create test app
app = FastAPI()
app.include_router(router, prefix="/api/packages")

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Test client for package routes."""
    app.include_router(router, prefix="/api/packages")
    return TestClient(app)


@pytest.fixture
def db_session():
    """Mock database session."""
    db = Mock()
    return db


@pytest.fixture
def student_agent(db_session):
    """Create STUDENT maturity agent."""
    agent = AgentRegistry(
        id="student-agent-001",
        name="Student Agent",
        status="student"
    )
    db_session.query.return_value.filter.return_value.first.return_value = agent
    return agent


@pytest.fixture
def intern_agent(db_session):
    """Create INTERN maturity agent."""
    agent = AgentRegistry(
        id="intern-agent-001",
        name="Intern Agent",
        status="intern"
    )
    db_session.query.return_value.filter.return_value.first.return_value = agent
    return agent


@pytest.fixture
def autonomous_agent(db_session):
    """Create AUTONOMOUS maturity agent."""
    agent = AgentRegistry(
        id="autonomous-agent-001",
        name="Autonomous Agent",
        status="autonomous"
    )
    db_session.query.return_value.filter.return_value.first.return_value = agent
    return agent


@pytest.fixture
def approved_npm_package(db_session):
    """Create approved npm package."""
    package = PackageRegistry(
        id="lodash:4.17.21",
        name="lodash",
        version="4.17.21",
        package_type="npm",
        status="active",
        min_maturity="intern"
    )
    return package


@pytest.fixture
def pending_npm_package(db_session):
    """Create pending npm package."""
    package = PackageRegistry(
        id="express:4.18.0",
        name="express",
        version="4.18.0",
        package_type="npm",
        status="pending",
        min_maturity="intern"
    )
    return package


@pytest.fixture
def banned_npm_package(db_session):
    """Create banned npm package."""
    package = PackageRegistry(
        id="malicious-pkg:1.0.0",
        name="malicious-pkg",
        version="1.0.0",
        package_type="npm",
        status="banned",
        ban_reason="Security vulnerability",
        min_maturity="autonomous"
    )
    return package


# ============================================================================
# npm Governance Endpoints Tests
# ============================================================================


class TestNpmGovernanceEndpoints:
    """Tests for npm governance endpoints."""

    def test_check_npm_package_permission_student_blocked(
        self, client, db_session, student_agent
    ):
        """Test that STUDENT agents are blocked from npm packages."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            response = client.get(
                "/api/packages/npm/check",
                params={
                    "agent_id": "student-agent-001",
                    "package_name": "lodash",
                    "version": "4.17.21"
                }
            )

            # STUDENT agents should be blocked
            assert response.status_code == 200
            data = response.json()
            assert data["allowed"] == False
            assert "STUDENT" in data["reason"]
            assert data["maturity_required"] == "intern"

    def test_check_npm_package_permission_intern_requires_approval(
        self, client, db_session, intern_agent
    ):
        """Test that INTERN agents require approval for npm packages."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock package query to return None (not in registry)
            db_session.query.return_value.filter.return_value.all.return_value = []

            response = client.get(
                "/api/packages/npm/check",
                params={
                    "agent_id": "intern-agent-001",
                    "package_name": "unknown-pkg",
                    "version": "1.0.0"
                }
            )

            # Unknown packages require approval
            assert response.status_code == 200
            data = response.json()
            assert data["allowed"] == False
            assert "not in registry" in data["reason"] or "requires approval" in data["reason"]

    def test_check_npm_package_permission_autonomous_allowed(
        self, client, db_session, autonomous_agent, approved_npm_package
    ):
        """Test that AUTONOMOUS agents allowed if package approved."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock package query to return approved package
            db_session.query.return_value.filter.return_value.first.return_value = approved_npm_package

            response = client.get(
                "/api/packages/npm/check",
                params={
                    "agent_id": "autonomous-agent-001",
                    "package_name": "lodash",
                    "version": "4.17.21"
                }
            )

            # AUTONOMOUS agent should be allowed for approved package
            assert response.status_code == 200
            data = response.json()
            assert data["allowed"] == True
            assert data["maturity_required"] == "intern"

    def test_request_npm_package_approval(self, client, db_session):
        """Test requesting npm package approval."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock governance service
            mock_package = Mock()
            mock_package.id = "express:4.18.0"
            mock_package.status = "pending"
            mock_package.package_type = "npm"

            with patch('api.package_routes.get_governance') as mock_gov:
                mock_gov.return_value.request_package_approval.return_value = mock_package

                response = client.post(
                    "/api/packages/npm/request",
                    json={
                        "package_name": "express",
                        "version": "4.18.0",
                        "requested_by": "user-001",
                        "reason": "Need for web server skill"
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert data["package_id"] == "express:4.18.0"
                assert data["status"] == "pending"
                assert data["package_type"] == "npm"

    def test_approve_npm_package(self, client, db_session):
        """Test approving npm package."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock governance service
            mock_package = Mock()
            mock_package.id = "express:4.18.0"
            mock_package.status = "active"
            mock_package.min_maturity = "intern"
            mock_package.approved_by = "admin-001"
            mock_package.approved_at = Mock()
            mock_package.approved_at.isoformat.return_value = "2026-02-19T00:00:00"

            with patch('api.package_routes.get_governance') as mock_gov:
                mock_gov.return_value.approve_package.return_value = mock_package

                response = client.post(
                    "/api/packages/npm/approve",
                    json={
                        "package_name": "express",
                        "version": "4.18.0",
                        "min_maturity": "intern",
                        "approved_by": "admin-001"
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert data["package_id"] == "express:4.18.0"
                assert data["status"] == "active"
                assert data["package_type"] == "npm"
                assert data["min_maturity"] == "intern"

    def test_ban_npm_package(self, client, db_session):
        """Test banning npm package."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock governance service
            mock_package = Mock()
            mock_package.id = "malicious-pkg:1.0.0"
            mock_package.status = "banned"
            mock_package.ban_reason = "Security vulnerability"

            with patch('api.package_routes.get_governance') as mock_gov:
                mock_gov.return_value.ban_package.return_value = mock_package

                response = client.post(
                    "/api/packages/npm/ban",
                    json={
                        "package_name": "malicious-pkg",
                        "version": "1.0.0",
                        "reason": "Security vulnerability"
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert data["package_id"] == "malicious-pkg:1.0.0"
                assert data["status"] == "banned"
                assert data["package_type"] == "npm"
                assert data["ban_reason"] == "Security vulnerability"


# ============================================================================
# npm Installation Endpoints Tests
# ============================================================================


class TestNpmInstallationEndpoints:
    """Tests for npm installation endpoints."""

    def test_install_npm_packages_success(self, client, db_session, autonomous_agent):
        """Test successful npm package installation."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock governance permission check
            with patch('api.package_routes.get_governance') as mock_gov:
                mock_gov.return_value.check_package_permission.return_value = {
                    "allowed": True,
                    "maturity_required": "intern",
                    "reason": None
                }

                # Mock npm installer
                mock_installer = Mock()
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-npm-skill:test-skill-v1",
                    "vulnerabilities": [],
                    "script_warnings": {"malicious": False, "warnings": []},
                    "build_logs": ["Step 1/5...", "Step 2/5..."]
                }

                with patch('api.package_routes.get_npm_installer') as mock_get_installer:
                    mock_get_installer.return_value = mock_installer

                    response = client.post(
                        "/api/packages/npm/install",
                        json={
                            "agent_id": "autonomous-agent-001",
                            "skill_id": "test-skill",
                            "packages": ["lodash@4.17.21"],
                            "package_manager": "npm",
                            "scan_for_vulnerabilities": True
                        }
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] == True
                    assert data["skill_id"] == "test-skill"
                    assert data["image_tag"] == "atom-npm-skill:test-skill-v1"

    def test_install_npm_packages_permission_denied(self, client, db_session, student_agent):
        """Test that STUDENT agents get 403 when installing npm packages."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock governance permission check (blocked)
            with patch('api.package_routes.get_governance') as mock_gov:
                mock_gov.return_value.check_package_permission.return_value = {
                    "allowed": False,
                    "maturity_required": "intern",
                    "reason": "STUDENT agents cannot execute npm packages"
                }

                response = client.post(
                    "/api/packages/npm/install",
                    json={
                        "agent_id": "student-agent-001",
                        "skill_id": "test-skill",
                        "packages": ["lodash@4.17.21"],
                        "package_manager": "npm"
                    }
                )

                assert response.status_code == 403
                data = response.json()
                assert "permission denied" in data["detail"]["error"]

    def test_install_npm_packages_malicious_scripts(self, client, db_session, autonomous_agent):
        """Test that malicious postinstall scripts are blocked."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock governance permission check
            with patch('api.package_routes.get_governance') as mock_gov:
                mock_gov.return_value.check_package_permission.return_value = {
                    "allowed": True,
                    "maturity_required": "intern",
                    "reason": None
                }

                # Mock npm installer with malicious scripts
                mock_installer = Mock()
                mock_installer.install_packages.return_value = {
                    "success": False,
                    "error": "Malicious postinstall/preinstall scripts detected",
                    "script_warnings": {
                        "malicious": True,
                        "warnings": ["Malicious pattern detected: process.env."],
                        "scripts_found": [{"package": "evil-pkg", "postinstall": True}]
                    },
                    "image_tag": None
                }

                with patch('api.package_routes.get_npm_installer') as mock_get_installer:
                    mock_get_installer.return_value = mock_installer

                    response = client.post(
                        "/api/packages/npm/install",
                        json={
                            "agent_id": "autonomous-agent-001",
                            "skill_id": "test-skill",
                            "packages": ["evil-pkg@1.0.0"],
                            "package_manager": "npm"
                        }
                    )

                    assert response.status_code == 403
                    data = response.json()
                    assert "Malicious postinstall" in data["detail"]["error"]

    def test_install_npm_packages_vulnerabilities(self, client, db_session, autonomous_agent):
        """Test that vulnerable packages are blocked."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock governance permission check
            with patch('api.package_routes.get_governance') as mock_gov:
                mock_gov.return_value.check_package_permission.return_value = {
                    "allowed": True,
                    "maturity_required": "intern",
                    "reason": None
                }

                # Mock npm installer with vulnerabilities
                mock_installer = Mock()
                mock_installer.install_packages.return_value = {
                    "success": False,
                    "error": "Vulnerabilities detected during scanning",
                    "vulnerabilities": [
                        {
                            "cve_id": "CVE-2021-23437",
                            "severity": "HIGH",
                            "package": "lodash",
                            "advisory": "Prototype Pollution"
                        }
                    ],
                    "image_tag": None
                }

                with patch('api.package_routes.get_npm_installer') as mock_get_installer:
                    mock_get_installer.return_value = mock_installer

                    response = client.post(
                        "/api/packages/npm/install",
                        json={
                            "agent_id": "autonomous-agent-001",
                            "skill_id": "test-skill",
                            "packages": ["lodash@4.17.20"],
                            "package_manager": "npm"
                        }
                    )

                    assert response.status_code == 400
                    data = response.json()
                    assert "Vulnerabilities detected" in data["detail"]["error"]

    def test_install_npm_yarn_manager(self, client, db_session, autonomous_agent):
        """Test that yarn package manager works."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock governance permission check
            with patch('api.package_routes.get_governance') as mock_gov:
                mock_gov.return_value.check_package_permission.return_value = {
                    "allowed": True,
                    "maturity_required": "intern",
                    "reason": None
                }

                # Mock npm installer
                mock_installer = Mock()
                mock_installer.install_packages.return_value = {
                    "success": True,
                    "image_tag": "atom-npm-skill:test-skill-v1",
                    "vulnerabilities": [],
                    "script_warnings": {"malicious": False, "warnings": []},
                    "build_logs": []
                }

                with patch('api.package_routes.get_npm_installer') as mock_get_installer:
                    mock_get_installer.return_value = mock_installer

                    response = client.post(
                        "/api/packages/npm/install",
                        json={
                            "agent_id": "autonomous-agent-001",
                            "skill_id": "test-skill",
                            "packages": ["lodash@4.17.21"],
                            "package_manager": "yarn"
                        }
                    )

                    assert response.status_code == 200
                    # Verify install_packages was called with yarn
                    mock_installer.install_packages.assert_called_once()
                    call_kwargs = mock_installer.install_packages.call_args[1]
                    assert call_kwargs["package_manager"] == "yarn"


# ============================================================================
# npm Execution Endpoints Tests
# ============================================================================


class TestNpmExecutionEndpoints:
    """Tests for npm execution endpoints."""

    def test_execute_npm_code_success(self, client, db_session):
        """Test successful Node.js code execution."""
        # Mock npm installer
        mock_installer = Mock()
        mock_installer.execute_with_packages.return_value = "Hello from Node.js!"

        with patch('api.package_routes.get_npm_installer') as mock_get_installer:
            mock_get_installer.return_value = mock_installer

            response = client.post(
                "/api/packages/npm/execute",
                json={
                    "agent_id": "autonomous-agent-001",
                    "skill_id": "test-skill",
                    "code": "console.log('Hello from Node.js!');",
                    "inputs": {},
                    "timeout_seconds": 30
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert data["output"] == "Hello from Node.js!"

    def test_execute_npm_code_image_not_found(self, client, db_session):
        """Test that 404 is returned when skill image not found."""
        # Mock npm installer to raise RuntimeError
        mock_installer = Mock()
        mock_installer.execute_with_packages.side_effect = RuntimeError(
            "Image atom-npm-skill:test-skill-v1 not found"
        )

        with patch('api.package_routes.get_npm_installer') as mock_get_installer:
            mock_get_installer.return_value = mock_installer

            response = client.post(
                "/api/packages/npm/execute",
                json={
                    "agent_id": "autonomous-agent-001",
                    "skill_id": "test-skill",
                    "code": "console.log('test');"
                }
            )

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]["error"]

    def test_execute_npm_code_with_inputs(self, client, db_session):
        """Test that inputs are passed correctly to execution."""
        # Mock npm installer
        mock_installer = Mock()
        mock_installer.execute_with_packages.return_value = "Result: 42"

        with patch('api.package_routes.get_npm_installer') as mock_get_installer:
            mock_get_installer.return_value = mock_installer

            response = client.post(
                "/api/packages/npm/execute",
                json={
                    "agent_id": "autonomous-agent-001",
                    "skill_id": "test-skill",
                    "code": "console.log(inputs.value);",
                    "inputs": {"value": 42},
                    "timeout_seconds": 30
                }
            )

            assert response.status_code == 200
            # Verify execute_with_packages was called with inputs
            mock_installer.execute_with_packages.assert_called_once()
            call_kwargs = mock_installer.execute_with_packages.call_args[1]
            assert call_kwargs["inputs"] == {"value": 42}


# ============================================================================
# npm Utility Endpoints Tests
# ============================================================================


class TestNpmUtilityEndpoints:
    """Tests for npm utility endpoints."""

    def test_list_npm_packages(self, client, db_session):
        """Test listing npm packages."""
        with patch('api.package_routes.get_db') as mock_get_db:
            mock_get_db.return_value = db_session

            # Mock governance service
            mock_package = Mock()
            mock_package.id = "lodash:4.17.21"
            mock_package.name = "lodash"
            mock_package.version = "4.17.21"
            mock_package.package_type = "npm"
            mock_package.min_maturity = "intern"
            mock_package.status = "active"
            mock_package.ban_reason = None
            mock_package.approved_by = "admin-001"
            mock_package.approved_at = Mock()
            mock_package.approved_at.isoformat.return_value = "2026-02-19T00:00:00"

            with patch('api.package_routes.get_governance') as mock_gov:
                mock_gov.return_value.list_packages.return_value = [mock_package]

                response = client.get("/api/packages/npm")

                assert response.status_code == 200
                data = response.json()
                assert data["count"] == 1
                assert len(data["packages"]) == 1
                assert data["packages"][0]["name"] == "lodash"

    def test_cleanup_npm_skill_image(self, client, db_session):
        """Test cleaning up npm skill image."""
        # Mock npm installer
        mock_installer = Mock()
        mock_installer.cleanup_skill_image.return_value = True

        with patch('api.package_routes.get_npm_installer') as mock_get_installer:
            mock_get_installer.return_value = mock_installer

            response = client.delete(
                "/api/packages/npm/test-skill",
                params={"agent_id": "autonomous-agent-001"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert data["skill_id"] == "test-skill"

    def test_get_npm_skill_image_status(self, client, db_session):
        """Test getting npm skill image status."""
        # Mock Docker client
        mock_image = Mock()
        mock_image.attrs = {
            "Size": 123456789,
            "Created": "2026-02-19T00:00:00",
            "RepoTags": ["atom-npm-skill:test-skill-v1"]
        }

        mock_docker = MagicMock()
        mock_docker.from_env.return_value.images.get.return_value = mock_image

        with patch('api.package_routes.docker', mock_docker):
            response = client.get("/api/packages/npm/test-skill/status")

            assert response.status_code == 200
            data = response.json()
            assert data["skill_id"] == "test-skill"
            assert data["image_exists"] == True
            assert data["size_bytes"] == 123456789

    def test_get_npm_skill_image_status_not_found(self, client, db_session):
        """Test getting status when image not found."""
        # Mock Docker client to raise ImageNotFound
        import docker
        mock_docker = MagicMock()
        mock_docker.from_env.return_value.images.get.side_effect = docker.errors.ImageNotFound("not found")

        with patch('api.package_routes.docker', mock_docker):
            response = client.get("/api/packages/npm/missing-skill/status")

            assert response.status_code == 200
            data = response.json()
            assert data["skill_id"] == "missing-skill"
            assert data["image_exists"] == False
