"""
Auto Install Routes Test Coverage

Target: api/auto_install_routes.py (100 lines, 3 endpoints)
Coverage Goal: 75%+ line coverage

Tests cover:
- POST /auto-install/install - Single dependency installation
- POST /auto-install/batch - Batch installation for multiple skills
- GET /auto-install/status/{skill_id} - Installation status check

External dependencies mocked:
- AutoInstallerService (async install_dependencies, batch_install)
- Database (get_db dependency override)

Test pattern: Per-file FastAPI app with TestClient (Phase 177/178 pattern)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy.orm import Session


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_auto_installer():
    """
    Mock AutoInstallerService with async methods.

    Provides deterministic mock responses for install operations:
    - install_dependencies: AsyncMock returning success/failure results
    - batch_install: AsyncMock returning batch installation results
    - _get_image_tag: Mock returning Docker image tag
    - _image_exists: Mock returning image existence status

    Usage:
        def test_install_success(mock_auto_installer):
            mock_auto_installer.install_dependencies.return_value = {
                "success": True,
                "image_tag": "skill-123:python"
            }
    """
    mock = MagicMock()

    # Mock async install_dependencies method
    mock.install_dependencies = AsyncMock(return_value={
        "success": True,
        "image_tag": "atom-skill:skill-123-v1",
        "installed_packages": ["numpy", "pandas"],
        "total_count": 2
    })

    # Mock async batch_install method
    mock.batch_install = AsyncMock(return_value={
        "success": True,
        "total": 2,
        "successes": 2,
        "failures": 0,
        "results": [
            {
                "skill_id": "skill-1",
                "result": {"success": True, "image_tag": "atom-skill:skill-1-v1"}
            },
            {
                "skill_id": "skill-2",
                "result": {"success": True, "image_tag": "atom-skill:skill-2-v1"}
            }
        ]
    })

    # Mock _get_image_tag (private method)
    mock._get_image_tag = Mock(return_value="atom-skill:skill-123-v1")

    # Mock _image_exists (private method)
    mock._image_exists = Mock(return_value=False)

    return mock


@pytest.fixture(scope="function")
def mock_db_for_auto_install():
    """
    Mock Session for get_db dependency.

    Used to override database dependency in auto install routes.
    Returns mock database session for testing.

    Usage:
        def test_with_mock_db(mock_db_for_auto_install):
            # Route handler will use this mock session
            pass
    """
    mock = MagicMock(spec=Session)

    # Mock common session methods
    mock.add = MagicMock()
    mock.commit = MagicMock()
    mock.rollback = MagicMock()
    mock.refresh = MagicMock()
    mock.query = MagicMock()
    mock.flush = MagicMock()
    mock.close = MagicMock()

    return mock


@pytest.fixture(scope="function")
def auto_install_client(mock_auto_installer, mock_db_for_auto_install):
    """
    TestClient with auto install routes and mocked dependencies.

    Creates isolated FastAPI app with auto_install_routes router.
    Overrides get_db dependency to use mock database.
    Patches AutoInstallerService to use mock service.

    Usage:
        def test_install_endpoint(auto_install_client):
            response = auto_install_client.post("/auto-install/install", json={})
            assert response.status_code == 200
    """
    from api.auto_install_routes import router
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)

    # Override get_db dependency
    def override_get_db():
        yield mock_db_for_auto_install

    app.dependency_overrides[get_db] = override_get_db

    # Patch AutoInstallerService
    with patch('api.auto_install_routes.AutoInstallerService', return_value=mock_auto_installer):
        client = TestClient(app)
        yield client

    # Clean up dependency overrides
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sample_install_request():
    """
    Factory for valid InstallRequest with default values.

    Provides valid installation request data. All fields have
    sensible defaults that can be overridden.

    Usage:
        def test_install(sample_install_request):
            data = sample_install_request.copy()
            data["skill_id"] = "custom-skill"
            response = client.post("/auto-install/install", json=data)
    """
    return {
        "skill_id": "skill-123",
        "packages": ["numpy", "pandas"],
        "package_type": "python",
        "agent_id": "agent-001",
        "scan_for_vulnerabilities": True
    }


@pytest.fixture(scope="function")
def sample_batch_install_request():
    """
    Factory for valid BatchInstallRequest with multiple installations.

    Provides valid batch installation request data with default
    installations. Can be customized per test.

    Usage:
        def test_batch_install(sample_batch_install_request):
            data = sample_batch_install_request.copy()
            response = client.post("/auto-install/batch", json=data)
    """
    return {
        "installations": [
            {
                "skill_id": "skill-1",
                "packages": ["numpy"],
                "package_type": "python",
                "agent_id": "agent-001",
                "scan_for_vulnerabilities": True
            },
            {
                "skill_id": "skill-2",
                "packages": ["lodash"],
                "package_type": "npm",
                "agent_id": "agent-001",
                "scan_for_vulnerabilities": True
            }
        ],
        "agent_id": "agent-001"
    }


@pytest.fixture(scope="function")
def install_success_response():
    """
    Expected successful install response structure.

    Provides reference structure for successful installation responses.
    Used to verify API response format.

    Usage:
        def test_install_response_format(auto_install_client, install_success_response):
            response = auto_install_client.post("/auto-install/install", json={})
            assert response.json()["success"] == install_success_response["success"]
    """
    return {
        "success": True,
        "image_tag": "atom-skill:skill-123-v1",
        "installed_packages": ["numpy", "pandas"],
        "total_count": 2
    }


@pytest.fixture(scope="function")
def batch_install_response():
    """
    Expected batch install response structure.

    Provides reference structure for batch installation responses.
    Includes total count, successes, failures, and per-skill results.

    Usage:
        def test_batch_response_format(auto_install_client, batch_install_response):
            response = auto_install_client.post("/auto-install/batch", json={})
            assert response.json()["total"] == batch_install_response["total"]
    """
    return {
        "success": True,
        "total": 2,
        "successes": 2,
        "failures": 0,
        "results": [
            {
                "skill_id": "skill-1",
                "result": {"success": True, "image_tag": "atom-skill:skill-1-v1"}
            },
            {
                "skill_id": "skill-2",
                "result": {"success": True, "image_tag": "atom-npm-skill:skill-2-v1"}
            }
        ]
    }


# ============================================================================
# TestAutoInstallSuccess - Single Install Endpoint Tests
# ============================================================================

class TestAutoInstallSuccess:
    """
    Happy path tests for POST /auto-install/install endpoint.

    Tests successful installation scenarios:
    - Python package installation
    - NPM package installation
    - Vulnerability scanning
    - Multiple packages in single request
    """

    def test_install_dependencies_python(
        self,
        auto_install_client,
        sample_install_request,
        mock_auto_installer
    ):
        """Test POST /auto-install/install with python packages returns success with image_tag."""
        response = auto_install_client.post("/auto-install/install", json=sample_install_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "image_tag" in data
        assert "atom-skill:" in data["image_tag"]
        assert data["installed_packages"] == ["numpy", "pandas"]
        assert data["total_count"] == 2

        # Verify service was called
        mock_auto_installer.install_dependencies.assert_called_once()

    def test_install_dependencies_npm(
        self,
        auto_install_client,
        mock_auto_installer
    ):
        """Test install with npm package_type works correctly."""
        request_data = {
            "skill_id": "npm-skill-123",
            "packages": ["lodash", "axios"],
            "package_type": "npm",
            "agent_id": "agent-001",
            "scan_for_vulnerabilities": True
        }

        # Configure mock for npm packages
        mock_auto_installer.install_dependencies.return_value = {
            "success": True,
            "image_tag": "atom-npm-skill:npm-skill-123-v1",
            "installed_packages": ["lodash", "axios"],
            "total_count": 2
        }

        response = auto_install_client.post("/auto-install/install", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "atom-npm-skill:" in data["image_tag"]
        assert data["installed_packages"] == ["lodash", "axios"]

    def test_install_with_vulnerability_scan(
        self,
        auto_install_client,
        sample_install_request,
        mock_auto_installer
    ):
        """Test scan_for_vulnerabilities=True includes security scan in result."""
        sample_install_request["scan_for_vulnerabilities"] = True

        response = auto_install_client.post("/auto-install/install", json=sample_install_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify install_dependencies was called with scan_for_vulnerabilities=True
        call_args = mock_auto_installer.install_dependencies.call_args
        assert call_args.kwargs["scan_for_vulnerabilities"] is True

    def test_install_multiple_packages(
        self,
        auto_install_client,
        mock_auto_installer
    ):
        """Test installing multiple packages in single request succeeds."""
        request_data = {
            "skill_id": "data-skill-456",
            "packages": ["numpy", "pandas", "scikit-learn", "matplotlib"],
            "package_type": "python",
            "agent_id": "agent-002",
            "scan_for_vulnerabilities": False
        }

        # Configure mock for multiple packages
        mock_auto_installer.install_dependencies.return_value = {
            "success": True,
            "image_tag": "atom-skill:data-skill-456-v1",
            "installed_packages": ["numpy", "pandas", "scikit-learn", "matplotlib"],
            "total_count": 4
        }

        response = auto_install_client.post("/auto-install/install", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_count"] == 4
        assert len(data["installed_packages"]) == 4

    def test_install_missing_skill_id(
        self,
        auto_install_client
    ):
        """Test missing skill_id returns 422 validation error."""
        request_data = {
            "packages": ["numpy"],
            "package_type": "python",
            "agent_id": "agent-001",
            "scan_for_vulnerabilities": True
            # Missing skill_id
        }

        response = auto_install_client.post("/auto-install/install", json=request_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_install_empty_packages(
        self,
        auto_install_client
    ):
        """Test empty packages list returns 422 (min_items=1 constraint)."""
        request_data = {
            "skill_id": "skill-123",
            "packages": [],  # Empty list violates min_items=1
            "package_type": "python",
            "agent_id": "agent-001",
            "scan_for_vulnerabilities": True
        }

        response = auto_install_client.post("/auto-install/install", json=request_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


# ============================================================================
# TestAutoInstallBatch - Batch Install Endpoint Tests
# ============================================================================

class TestAutoInstallBatch:
    """
    Tests for POST /auto-install/batch endpoint.

    Tests batch installation scenarios:
    - Multiple skills installation
    - Two different skills
    - Mixed package types (python and npm)
    - Empty installations list validation
    - Partial failures
    """

    def test_batch_install_success(
        self,
        auto_install_client,
        sample_batch_install_request,
        mock_auto_installer
    ):
        """Test POST /auto-install/batch installs multiple skills successfully."""
        response = auto_install_client.post("/auto-install/batch", json=sample_batch_install_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert data["successes"] == 2
        assert data["failures"] == 0
        assert len(data["results"]) == 2

        # Verify batch_install was called
        mock_auto_installer.batch_install.assert_called_once()

    def test_batch_install_two_skills(
        self,
        auto_install_client,
        mock_auto_installer
    ):
        """Test batch install with 2 different skills."""
        request_data = {
            "installations": [
                {
                    "skill_id": "skill-analytics",
                    "packages": ["numpy", "pandas"],
                    "package_type": "python",
                    "agent_id": "agent-001",
                    "scan_for_vulnerabilities": True
                },
                {
                    "skill_id": "skill-frontend",
                    "packages": ["react", "axios"],
                    "package_type": "npm",
                    "agent_id": "agent-001",
                    "scan_for_vulnerabilities": False
                }
            ],
            "agent_id": "agent-001"
        }

        response = auto_install_client.post("/auto-install/batch", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successes"] == 2
        assert len(data["results"]) == 2

        # Verify both skills are in results
        skill_ids = [r["skill_id"] for r in data["results"]]
        assert "skill-analytics" in skill_ids
        assert "skill-frontend" in skill_ids

    def test_batch_install_mixed_package_types(
        self,
        auto_install_client,
        mock_auto_installer
    ):
        """Test batch with both python and npm packages."""
        request_data = {
            "installations": [
                {
                    "skill_id": "python-skill",
                    "packages": ["numpy"],
                    "package_type": "python",
                    "agent_id": "agent-001",
                    "scan_for_vulnerabilities": True
                },
                {
                    "skill_id": "npm-skill",
                    "packages": ["lodash"],
                    "package_type": "npm",
                    "agent_id": "agent-001",
                    "scan_for_vulnerabilities": True
                }
            ],
            "agent_id": "agent-001"
        }

        response = auto_install_client.post("/auto-install/batch", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 2

    def test_batch_install_empty(
        self,
        auto_install_client
    ):
        """Test empty installations list returns 422 (min_items=1 constraint)."""
        request_data = {
            "installations": [],  # Empty list violates min_items=1
            "agent_id": "agent-001"
        }

        response = auto_install_client.post("/auto-install/batch", json=request_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_batch_install_partial_failure(
        self,
        auto_install_client,
        mock_auto_installer
    ):
        """Test batch with some successes and some failures."""
        # Configure batch_install to return partial failure
        mock_auto_installer.batch_install.return_value = {
            "success": False,  # Overall success is False due to failures
            "total": 3,
            "successes": 2,
            "failures": 1,
            "results": [
                {
                    "skill_id": "skill-1",
                    "result": {"success": True, "image_tag": "atom-skill:skill-1-v1"}
                },
                {
                    "skill_id": "skill-2",
                    "result": {"success": True, "image_tag": "atom-skill:skill-2-v1"}
                },
                {
                    "skill_id": "skill-3",
                    "result": {"success": False, "error": "Package not found"}
                }
            ]
        }

        request_data = {
            "installations": [
                {
                    "skill_id": "skill-1",
                    "packages": ["numpy"],
                    "package_type": "python",
                    "agent_id": "agent-001",
                    "scan_for_vulnerabilities": True
                },
                {
                    "skill_id": "skill-2",
                    "packages": ["pandas"],
                    "package_type": "python",
                    "agent_id": "agent-001",
                    "scan_for_vulnerabilities": True
                },
                {
                    "skill_id": "skill-3",
                    "packages": ["nonexistent"],
                    "package_type": "python",
                    "agent_id": "agent-001",
                    "scan_for_vulnerabilities": True
                }
            ],
            "agent_id": "agent-001"
        }

        response = auto_install_client.post("/auto-install/batch", json=request_data)

        assert response.status_code == 200  # Batch endpoint returns 200 even with partial failures
        data = response.json()
        assert data["success"] is False  # Overall success is False
        assert data["total"] == 3
        assert data["successes"] == 2
        assert data["failures"] == 1


# ============================================================================
# TestAutoInstallStatus - Status Check Endpoint Tests
# ============================================================================

class TestAutoInstallStatus:
    """
    Tests for GET /auto-install/status/{skill_id} endpoint.

    Tests installation status check scenarios:
    - Installed status (image exists)
    - Not installed status (image doesn't exist)
    - NPM package type
    - Python package type (default)
    """

    def test_get_status_installed(
        self,
        auto_install_client,
        mock_auto_installer
    ):
        """Test GET /auto-install/status/{skill_id} returns installed=True when image exists."""
        # Configure mock to return image exists
        mock_auto_installer._image_exists.return_value = True
        mock_auto_installer._get_image_tag.return_value = "atom-skill:skill-123-v1"

        response = auto_install_client.get("/auto-install/status/skill-123?package_type=python")

        assert response.status_code == 200
        data = response.json()
        assert data["installed"] is True
        assert data["skill_id"] == "skill-123"
        assert data["package_type"] == "python"
        assert data["image_tag"] == "atom-skill:skill-123-v1"

    def test_get_status_not_installed(
        self,
        auto_install_client,
        mock_auto_installer
    ):
        """Test returns installed=False when image doesn't exist."""
        # Configure mock to return image doesn't exist
        mock_auto_installer._image_exists.return_value = False
        mock_auto_installer._get_image_tag.return_value = "atom-skill:skill-456-v1"

        response = auto_install_client.get("/auto-install/status/skill-456?package_type=python")

        assert response.status_code == 200
        data = response.json()
        assert data["installed"] is False
        assert data["skill_id"] == "skill-456"
        assert data["package_type"] == "python"
        assert data["image_tag"] is None  # No image_tag when not installed

    def test_get_status_npm_package(
        self,
        auto_install_client,
        mock_auto_installer
    ):
        """Test status check with npm package_type."""
        # Configure mock for npm package
        mock_auto_installer._image_exists.return_value = True
        mock_auto_installer._get_image_tag.return_value = "atom-npm-skill:npm-skill-789-v1"

        response = auto_install_client.get("/auto-install/status/npm-skill-789?package_type=npm")

        assert response.status_code == 200
        data = response.json()
        assert data["installed"] is True
        assert data["skill_id"] == "npm-skill-789"
        assert data["package_type"] == "npm"
        assert "atom-npm-skill:" in data["image_tag"]

    def test_get_status_python_default(
        self,
        auto_install_client,
        mock_auto_installer
    ):
        """Test status check defaults to python package_type when not specified."""
        mock_auto_installer._image_exists.return_value = True
        mock_auto_installer._get_image_tag.return_value = "atom-skill:skill-default-v1"

        # Request without package_type query parameter (defaults to python)
        response = auto_install_client.get("/auto-install/status/skill-default")

        assert response.status_code == 200
        data = response.json()
        assert data["installed"] is True
        assert data["package_type"] == "python"  # Default
        assert data["skill_id"] == "skill-default"
