"""
Admin Skill Routes API Tests

Tests for admin skill routes (`api/admin/skill_routes.py`):
- POST /api/admin/skills - Create new standardized skill package
- Security scanning: Static analysis and optional LLM analysis
- Governance enforcement: AUTONOMOUS maturity, super_admin role required
- Error paths: 403 unauthorized, 409 policy violation, 422 validation error, 500 internal error

Coverage target: 75%+ line coverage on admin/skill_routes.py
"""

import pytest
import uuid
import os
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import admin skill routes router
from api.admin.skill_routes import router


# ============================================================================
# Test Database Setup
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing.

    Note: We use a mock session to avoid SQLAlchemy model relationship issues.
    The admin skill routes don't actually use the database for skill creation,
    they use the skill_builder_service which we mock.
    """
    from unittest.mock import MagicMock
    from sqlalchemy.orm import Session

    mock_db = MagicMock(spec=Session)

    yield mock_db


@pytest.fixture(scope="function")
def test_app(test_db: Session):
    """Create FastAPI app with admin skill routes for testing."""
    app = FastAPI()
    app.include_router(router)

    # Override get_db dependency
    from core.database import get_db

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield app

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(test_app: FastAPI):
    """Create TestClient for testing."""
    return TestClient(test_app)


@pytest.fixture(scope="function")
def super_admin_user():
    """Create mock super admin user for authorization tests."""
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = str(uuid.uuid4())
    user.email = "superadmin@test.com"
    user.first_name = "Super"
    user.last_name = "Admin"
    user.name = "Super Admin"
    user.role = "super_admin"
    user.status = "active"
    user.email_verified = True
    user.tenant_id = "test_tenant"

    return user


@pytest.fixture(scope="function")
def regular_user():
    """Create mock regular user for authentication testing."""
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = str(uuid.uuid4())
    user.email = "member@test.com"
    user.first_name = "Regular"
    user.last_name = "Member"
    user.name = "Regular Member"
    user.role = "member"
    user.status = "active"
    user.email_verified = True
    user.tenant_id = "test_tenant"

    return user


@pytest.fixture(scope="function")
def authenticated_admin_client(client: TestClient, super_admin_user: User):
    """Create authenticated TestClient with super admin user."""
    from core.auth import get_current_user

    def override_get_current_user():
        return super_admin_user

    client.app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    client.app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def unauthenticated_client(client: TestClient):
    """Create unauthenticated TestClient (no auth override)."""
    yield client


@pytest.fixture(scope="function")
def mock_static_analyzer():
    """Create MagicMock for StaticAnalyzer with configurable findings."""
    from atom_security.analyzers.static import StaticAnalyzer

    mock = MagicMock(spec=StaticAnalyzer)

    # Default: no findings (scan passes)
    mock.scan_content.return_value = []

    return mock


@pytest.fixture(scope="function")
def mock_skill_builder():
    """Create MagicMock for skill_builder_service with deterministic return values."""
    mock = MagicMock()

    # Default: successful skill creation
    mock.create_skill_package.return_value = {
        "success": True,
        "message": "Skill package created successfully",
        "skill_path": "/tmp/skills/test_skill",
        "metadata": {
            "name": "test_skill",
            "description": "Test skill",
            "version": "1.0.0"
        }
    }

    return mock


@pytest.fixture(scope="function")
def inactive_admin_user():
    """Create mock inactive super admin user for testing."""
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = str(uuid.uuid4())
    user.email = "inactive_admin@test.com"
    user.first_name = "Inactive"
    user.last_name = "Admin"
    user.name = "Inactive Admin"
    user.role = "super_admin"
    user.status = "inactive"
    user.email_verified = True
    user.tenant_id = "test_tenant"

    return user


# ============================================================================
# POST /api/admin/skills - Success Path Tests
# ============================================================================

class TestAdminSkillRoutesSuccess:
    """Tests for successful skill creation via admin skill routes."""

    def test_create_skill_success(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test successful skill creation with valid request."""
        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                    json={
                        "name": "test_skill",
                        "description": "A test skill for coverage",
                        "instructions": "You are a helpful assistant",
                        "capabilities": ["web_search", "data_analysis"],
                        "scripts": {
                            "main.py": "def main():\n    pass",
                            "utils.py": "def helper():\n    pass"
                        }
                    }
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["success"] is True
        assert "skill_path" in data["data"]
        assert "message" in data

    def test_create_skill_with_all_fields(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test skill creation with all optional fields populated."""
        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                    json={
                        "name": "advanced_skill",
                        "description": "An advanced skill with all fields",
                        "instructions": "You are an advanced assistant",
                        "capabilities": [
                            "web_search",
                            "data_analysis",
                            "file_operations",
                            "api_calls"
                        ],
                        "scripts": {
                            "main.py": "def main():\n    pass",
                            "utils.py": "def helper():\n    pass",
                            "config.py": "CONFIG = {}"
                        }
                    }
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify skill builder was called with correct parameters
        mock_skill_builder.create_skill_package.assert_called_once()
        call_args = mock_skill_builder.create_skill_package.call_args
        assert call_args[1]["metadata"].capabilities == [
            "web_search",
            "data_analysis",
            "file_operations",
            "api_calls"
        ]

    def test_create_skill_tenant_id_from_admin(
        self,
        authenticated_admin_client: TestClient,
        super_admin_user: User,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test that tenant_id is extracted from admin user."""
        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                    json={
                        "name": "tenant_skill",
                        "description": "Skill for specific tenant",
                        "instructions": "You are a tenant-specific assistant",
                        "scripts": {"main.py": "def main():\n    pass"}
                    }
                )

        assert response.status_code == 200

        # Verify tenant_id was passed to skill builder
        mock_skill_builder.create_skill_package.assert_called_once()
        call_args = mock_skill_builder.create_skill_package.call_args
        assert call_args[1]["tenant_id"] == super_admin_user.tenant_id

    def test_create_skill_default_author(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test that author defaults to admin email."""
        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                    json={
                        "name": "author_skill",
                        "description": "Skill to test author default",
                        "instructions": "You are an assistant",
                        "scripts": {"main.py": "def main():\n    pass"}
                    }
                )

        assert response.status_code == 200

        # Verify author was set from admin email
        mock_skill_builder.create_skill_package.assert_called_once()
        call_args = mock_skill_builder.create_skill_package.call_args
        assert call_args[1]["metadata"].author == "superadmin@test.com"

    def test_create_skill_without_llm_scan(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test skill creation when LLM scan is disabled."""
        # Ensure LLM scan is disabled
        original_env = os.environ.get("ATOM_SECURITY_ENABLE_LLM_SCAN")
        os.environ["ATOM_SECURITY_ENABLE_LLM_SCAN"] = "false"

        try:
            with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
                with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                    response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                        json={
                            "name": "no_llm_skill",
                            "description": "Skill without LLM scan",
                            "instructions": "You are an assistant",
                            "scripts": {"main.py": "def main():\n    pass"}
                        }
                    )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            # Restore original environment
            if original_env is not None:
                os.environ["ATOM_SECURITY_ENABLE_LLM_SCAN"] = original_env
            else:
                os.environ.pop("ATOM_SECURITY_ENABLE_LLM_SCAN", None)


# ============================================================================
# POST /api/admin/skills - Authentication & Authorization Tests
# ============================================================================

class TestAdminSkillRoutesAuth:
    """Tests for authentication and authorization on admin skill routes."""

    def test_create_skill_requires_super_admin(
        self,
        client: TestClient,
        regular_user: User,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test that non-super_admin cannot create skills."""
        from core.auth import get_current_user

        def override_get_current_user():
            return regular_user  # Regular user, not super_admin

        client.app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
                with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                    response = client.post(
                    "/api/admin/skills/api/admin/skills",
                        json={
                            "name": "unauthorized_skill",
                            "description": "Should fail",
                            "instructions": "You are an assistant",
                            "scripts": {"main.py": "def main():\n    pass"}
                        }
                    )

            # Should return 403 because regular_user is not super_admin
            assert response.status_code == 403
        finally:
            client.app.dependency_overrides.clear()

    def test_create_skill_unauthenticated(
        self,
        unauthenticated_client: TestClient
    ):
        """Test that unauthenticated request fails."""
        response = unauthenticated_client.post(
                    "/api/admin/skills/api/admin/skills",
            json={
                "name": "unauth_skill",
                "description": "Should fail",
                "instructions": "You are an assistant",
                "scripts": {"main.py": "def main():\n    pass"}
            }
        )

        # Should return 401 because no authentication provided
        assert response.status_code == 401

    def test_create_skill_inactive_admin(
        self,
        client: TestClient,
        inactive_admin_user: User,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test that inactive admin cannot create skills."""
        from core.auth import get_current_user

        def override_get_current_user():
            return inactive_admin_user  # Inactive super_admin

        client.app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
                with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                    response = client.post(
                    "/api/admin/skills/api/admin/skills",
                        json={
                            "name": "inactive_skill",
                            "description": "Should fail",
                            "instructions": "You are an assistant",
                            "scripts": {"main.py": "def main():\n    pass"}
                        }
                    )

            # Should return 401 or 403 because admin is inactive
            # The exact behavior depends on get_current_user implementation
            assert response.status_code in [401, 403]
        finally:
            client.app.dependency_overrides.clear()

    def test_get_super_admin_dependency(
        self,
        client: TestClient,
        super_admin_user: User,
        regular_user: User
    ):
        """Test get_super_admin dependency directly."""
        from core.admin_endpoints import get_super_admin

        # Test 1: super_admin role should pass
        result = get_super_admin(current_user=super_admin_user)
        assert result == super_admin_user

        # Test 2: non-super_admin role should raise HTTPException
        with pytest.raises(Exception) as exc_info:
            result = get_super_admin(current_user=regular_user)
        # Should raise HTTPException with 403 status
        assert exc_info.value.status_code == 403


# ============================================================================
# POST /api/admin/skills - Security Scanning Tests
# ============================================================================

class TestAdminSkillRoutesSecurity:
    """Tests for security scanning on admin skill routes."""

    def test_security_scan_static_pass(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test skill creation when static scan passes."""
        # Static scan returns no findings
        mock_static_analyzer.scan_content.return_value = []

        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                    json={
                        "name": "clean_skill",
                        "description": "Passes security scan",
                        "instructions": "You are an assistant",
                        "scripts": {"main.py": "def main():\n    pass"}
                    }
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_security_scan_critical_finding(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock
    ):
        """Test skill rejection for critical findings."""
        from atom_security.analyzers.static import StaticAnalyzer
        from atom_security.models import Severity

        # Create mock finding with HIGH severity
        mock_finding = MagicMock()
        mock_finding.severity = Severity.HIGH
        mock_finding.dict.return_value = {
            "severity": "HIGH",
            "category": "command_injection",
            "line": 1,
            "description": "Potential command injection detected"
        }

        mock_static_analyzer.scan_content.return_value = [mock_finding]

        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                json={
                    "name": "malicious_skill",
                    "description": "Contains critical findings",
                    "instructions": "You are an assistant",
                    "scripts": {"main.py": "import os; os.system('rm -rf /')"}
                }
            )

        assert response.status_code == 403
        data = response.json()
        assert "security policy violations" in data["detail"].lower()

    def test_security_scan_multiple_findings(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock
    ):
        """Test with multiple security findings of mixed severity."""
        from atom_security.models import Severity

        # Create multiple findings with different severities
        low_finding = MagicMock()
        low_finding.severity = Severity.LOW
        low_finding.dict.return_value = {
            "severity": "LOW",
            "category": "code_style",
            "line": 5,
            "description": "Line too long"
        }

        medium_finding = MagicMock()
        medium_finding.severity = Severity.MEDIUM
        medium_finding.dict.return_value = {
            "severity": "MEDIUM",
            "category": "error_handling",
            "line": 10,
            "description": "Missing error handling"
        }

        high_finding = MagicMock()
        high_finding.severity = Severity.HIGH
        high_finding.dict.return_value = {
            "severity": "HIGH",
            "category": "injection",
            "line": 15,
            "description": "SQL injection risk"
        }

        mock_static_analyzer.scan_content.return_value = [
            low_finding,
            medium_finding,
            high_finding
        ]

        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                json={
                    "name": "mixed_findings_skill",
                    "description": "Has multiple findings",
                    "instructions": "You are an assistant",
                    "scripts": {"main.py": "def main():\n    pass"}
                }
            )

        # Should fail due to HIGH severity finding
        assert response.status_code == 403

    def test_llm_scan_enabled(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test LLM scan when enabled."""
        # Enable LLM scan
        original_env = os.environ.get("ATOM_SECURITY_ENABLE_LLM_SCAN")
        os.environ["ATOM_SECURITY_ENABLE_LLM_SCAN"] = "true"

        # Mock LLM analyzer
        mock_llm_analyzer = AsyncMock()
        mock_llm_finding = MagicMock()
        mock_llm_finding.severity.value = "LOW"
        mock_llm_finding.dict.return_value = {
            "severity": "LOW",
            "category": "semantics",
            "description": "Potential ambiguity"
        }
        mock_llm_analyzer.analyze.return_value = [mock_llm_finding]

        # Static scan passes
        mock_static_analyzer.scan_content.return_value = []

        try:
            with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
                with patch('api.admin.skill_routes.LLMAnalyzer', return_value=mock_llm_analyzer):
                    with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                        response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                            json={
                                "name": "llm_scanned_skill",
                                "description": "Skill with LLM scan",
                                "instructions": "You are an assistant",
                                "scripts": {"main.py": "def main():\n    pass"}
                            }
                        )

            # Should succeed because only LOW findings from LLM
            assert response.status_code == 200
        finally:
            # Restore original environment
            if original_env is not None:
                os.environ["ATOM_SECURITY_ENABLE_LLM_SCAN"] = original_env
            else:
                os.environ.pop("ATOM_SECURITY_ENABLE_LLM_SCAN", None)

    def test_llm_scan_failure_blocks(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test that LLM scan failure doesn't block skill creation."""
        # Enable LLM scan
        original_env = os.environ.get("ATOM_SECURITY_ENABLE_LLM_SCAN")
        os.environ["ATOM_SECURITY_ENABLE_LLM_SCAN"] = "true"

        # Mock LLM analyzer that raises exception
        mock_llm_analyzer = AsyncMock()
        mock_llm_analyzer.analyze.side_effect = Exception("LLM service unavailable")

        # Static scan passes
        mock_static_analyzer.scan_content.return_value = []

        try:
            with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
                with patch('api.admin.skill_routes.LLMAnalyzer', return_value=mock_llm_analyzer):
                    with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                        response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                            json={
                                "name": "llm_fail_skill",
                                "description": "LLM scan fails but continues",
                                "instructions": "You are an assistant",
                                "scripts": {"main.py": "def main():\n    pass"}
                            }
                        )

            # Should succeed despite LLM scan failure (graceful degradation)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            # Restore original environment
            if original_env is not None:
                os.environ["ATOM_SECURITY_ENABLE_LLM_SCAN"] = original_env
            else:
                os.environ.pop("ATOM_SECURITY_ENABLE_LLM_SCAN", None)

    def test_security_scan_exception(
        self,
        authenticated_admin_client: TestClient,
        mock_skill_builder: MagicMock
    ):
        """Test handling of security module exceptions."""
        # Mock StaticAnalyzer that raises exception
        mock_analyzer = MagicMock()
        mock_analyzer.scan_content.side_effect = Exception("Security module crashed")

        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                    json={
                        "name": "scan_exception_skill",
                        "description": "Security scan fails",
                        "instructions": "You are an assistant",
                        "scripts": {"main.py": "def main():\n    pass"}
                    }
                )

        # Should succeed despite security scan exception (graceful degradation)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# POST /api/admin/skills - Error Path Tests
# ============================================================================

class TestAdminSkillRoutesError:
    """Tests for error handling on admin skill routes."""

    def test_create_skill_validation_error(
        self,
        authenticated_admin_client: TestClient
    ):
        """Test request validation failures."""
        response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
            json={
                # Missing required fields: name, description, instructions, scripts
                "capabilities": ["web_search"]
            }
        )

        assert response.status_code == 422

    def test_create_skill_invalid_scripts(
        self,
        authenticated_admin_client: TestClient
    ):
        """Test invalid scripts format."""
        response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
            json={
                "name": "invalid_scripts",
                "description": "Has invalid scripts",
                "instructions": "You are an assistant",
                "scripts": "not_a_dict"  # Should be dict
            }
        )

        assert response.status_code == 422

    def test_create_skill_builder_fails(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: MagicMock
    ):
        """Test skill builder service failure."""
        # Mock skill builder to return failure
        mock_skill_builder.create_skill_package.return_value = {
            "success": False,
            "message": "Failed to create skill package: Invalid skill structure"
        }

        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                    json={
                        "name": "builder_fail",
                        "description": "Builder fails",
                        "instructions": "You are an assistant",
                        "scripts": {"main.py": "def main():\n    pass"}
                    }
                )

        assert response.status_code == 422

    def test_create_skill_unhandled_exception(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock
    ):
        """Test unhandled exception path."""
        mock_skill_builder = MagicMock()
        mock_skill_builder.create_skill_package.side_effect = Exception("Unexpected error")

        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
                    json={
                        "name": "exception_skill",
                        "description": "Raises exception",
                        "instructions": "You are an assistant",
                        "scripts": {"main.py": "def main():\n    pass"}
                    }
                )

        assert response.status_code == 500

    def test_create_skill_empty_name(
        self,
        authenticated_admin_client: TestClient
    ):
        """Test empty name validation."""
        response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
            json={
                "name": "",  # Empty name
                "description": "Empty name",
                "instructions": "You are an assistant",
                "scripts": {"main.py": "def main():\n    pass"}
            }
        )

        assert response.status_code == 422

    def test_create_skill_invalid_capabilities(
        self,
        authenticated_admin_client: TestClient
    ):
        """Test invalid capabilities format."""
        response = authenticated_admin_client.post(
                    "/api/admin/skills/api/admin/skills",
            json={
                "name": "invalid_caps",
                "description": "Invalid capabilities",
                "instructions": "You are an assistant",
                "capabilities": "not_a_list",  # Should be list
                "scripts": {"main.py": "def main():\n    pass"}
            }
        )

        assert response.status_code == 422
