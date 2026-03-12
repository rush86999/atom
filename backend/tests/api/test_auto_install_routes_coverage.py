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
