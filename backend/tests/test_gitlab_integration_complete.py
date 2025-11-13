#!/usr/bin/env python3
"""
Comprehensive GitLab Integration Test

This test file verifies the complete GitLab integration functionality
including OAuth, API endpoints, and service operations.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

# Add backend to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
)

import pytest
from flask import Flask

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestGitLabIntegration:
    """Comprehensive GitLab integration test suite"""

    def setup_method(self):
        """Setup test environment"""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

        # Mock environment variables
        os.environ["GITLAB_BASE_URL"] = "https://gitlab.com"
        os.environ["GITLAB_CLIENT_ID"] = "test-client-id"
        os.environ["GITLAB_CLIENT_SECRET"] = "test-client-secret"
        os.environ["GITLAB_REDIRECT_URI"] = (
            "http://localhost:3000/oauth/gitlab/callback"
        )
        os.environ["GITLAB_ACCESS_TOKEN"] = "test-access-token"

    def test_gitlab_enhanced_service_initialization(self):
        """Test GitLab enhanced service initialization"""
        from gitlab_enhanced_service import GitLabEnhancedService

        # Test initialization with access token
        service = GitLabEnhancedService("https://gitlab.com", "test-access-token")
        assert service.base_url == "https://gitlab.com"
        assert service.access_token == "test-access-token"
        assert service.cache is not None

        logger.info("✅ GitLab Enhanced Service initialization test passed")

    @patch("gitlab_enhanced_service.aiohttp.ClientSession")
    def test_gitlab_service_get_projects(self, mock_session):
        """Test GitLab service project retrieval"""
        from gitlab_enhanced_service import GitLabEnhancedService

        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": "test-project",
                "description": "Test project",
                "path_with_namespace": "user/test-project",
                "web_url": "https://gitlab.com/user/test-project",
                "visibility": "public",
                "last_activity_at": "2024-01-01T00:00:00Z",
                "default_branch": "main",
            }
        ]

        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

        service = GitLabEnhancedService("https://gitlab.com", "test-access-token")

        # Test async execution
        async def run_test():
            result = await service.get_projects("test-user")
            assert result["success"] is True
            assert len(result["data"]) == 1
            assert result["data"][0]["name"] == "test-project"

        asyncio.run(run_test())
        logger.info("✅ GitLab service get projects test passed")

    def test_gitlab_enhanced_api_blueprint(self):
        """Test GitLab enhanced API blueprint creation"""
        from gitlab_enhanced_api import gitlab_enhanced_bp

        assert gitlab_enhanced_bp.name == "gitlab_enhanced_bp"
        assert len(gitlab_enhanced_bp.deferred_functions) > 0

        # Check if routes are registered
        routes = [rule.rule for rule in gitlab_enhanced_bp.url_map.iter_rules()]
        expected_routes = [
            "/api/integrations/gitlab/health",
            "/api/integrations/gitlab/info",
            "/api/integrations/gitlab/projects/list",
            "/api/integrations/gitlab/issues/list",
            "/api/integrations/gitlab/merge-requests/list",
            "/api/integrations/gitlab/pipelines/list",
            "/api/integrations/gitlab/issues/create",
            "/api/integrations/gitlab/merge-requests/create",
            "/api/integrations/gitlab/pipelines/trigger",
            "/api/integrations/gitlab/branches/list",
        ]

        for route in expected_routes:
            assert any(route in r for r in routes), f"Route {route} not found"

        logger.info("✅ GitLab enhanced API blueprint test passed")

    @patch("gitlab_enhanced_api.get_gitlab_service")
    def test_gitlab_health_endpoint(self, mock_get_service):
        """Test GitLab health endpoint"""
        from gitlab_enhanced_api import gitlab_health

        # Mock service
        mock_service = Mock()
        mock_service.access_token = "test-token"
        mock_service.get_projects.return_value = {"success": True, "data": []}
        mock_get_service.return_value = mock_service

        # Test health endpoint
        with self.app.test_request_context():
            response = asyncio.run(gitlab_health())
            data = json.loads(response.get_data(as_text=True))

            assert response.status_code == 200
            assert data["success"] is True
            assert data["service"] == "gitlab"
            assert "components" in data["data"]

        logger.info("✅ GitLab health endpoint test passed")

    @patch("gitlab_enhanced_api.get_gitlab_service")
    def test_gitlab_projects_endpoint(self, mock_get_service):
        """Test GitLab projects endpoint"""
        from gitlab_enhanced_api import list_projects

        # Mock service
        mock_service = Mock()
        mock_service.get_projects.return_value = {
            "success": True,
            "data": [
                {
                    "id": 1,
                    "name": "test-project",
                    "description": "Test project",
                    "path_with_namespace": "user/test-project",
                    "web_url": "https://gitlab.com/user/test-project",
                }
            ],
        }
        mock_get_service.return_value = mock_service

        # Test projects endpoint
        with self.app.test_request_context(json={"user_id": "test-user"}):
            response = asyncio.run(list_projects())
            data = json.loads(response.get_data(as_text=True))

            assert response.status_code == 200
            assert data["success"] is True
            assert len(data["data"]) == 1
            assert data["data"][0]["name"] == "test-project"

        logger.info("✅ GitLab projects endpoint test passed")

    def test_gitlab_database_oauth_integration(self):
        """Test GitLab OAuth database integration"""
        from db_oauth_gitlab import (
            delete_gitlab_tokens,
            get_gitlab_tokens,
            init_gitlab_oauth_table,
            save_gitlab_tokens,
        )

        # Mock database pool
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Test table initialization
        mock_conn.fetchval.return_value = False  # Table doesn't exist
        mock_conn.execute.return_value = None

        async def test_init():
            result = await init_gitlab_oauth_table(mock_pool)
            assert result is True

        asyncio.run(test_init())

        # Test token operations
        test_tokens = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 7200,
            "scope": "read_user read_repository",
        }

        async def test_token_operations():
            # Test save tokens
            save_result = await save_gitlab_tokens(mock_pool, "test-user", test_tokens)
            assert save_result is True

            # Test get tokens
            mock_conn.fetchrow.return_value = {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "token_type": "Bearer",
                "expires_at": datetime(2024, 12, 31, 23, 59, 59),
                "scope": "read_user read_repository",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            tokens = await get_gitlab_tokens(mock_pool, "test-user")
            assert tokens is not None
            assert tokens["access_token"] == "test-access-token"

            # Test delete tokens
            mock_conn.execute.return_value = "DELETE 1"
            delete_result = await delete_gitlab_tokens(mock_pool, "test-user")
            assert delete_result is True

        asyncio.run(test_token_operations())
        logger.info("✅ GitLab database OAuth integration test passed")

    def test_gitlab_oauth_handler(self):
        """Test GitLab OAuth handler"""
        from auth_handler_gitlab import GitLabOAuthHandler

        handler = GitLabOAuthHandler()

        # Test OAuth URL generation
        result = handler.get_oauth_url("test-user", "test-state")
        assert result["success"] is True
        assert "oauth_url" in result
        assert "gitlab.com/oauth/authorize" in result["oauth_url"]
        assert "client_id=test-client-id" in result["oauth_url"]

        logger.info("✅ GitLab OAuth handler test passed")

    def test_gitlab_service_handler(self):
        """Test GitLab service handler"""
        from service_handlers.gitlab_handler import GitLabHandler

        handler = GitLabHandler()

        # Test handler initialization
        assert handler.client_id == "test-client-id"
        assert handler.client_secret == "test-client-secret"
        assert handler.api_base_url == "https://gitlab.com/api/v4"

        logger.info("✅ GitLab service handler test passed")

    def test_gitlab_api_response_formatting(self):
        """Test GitLab API response formatting"""
        from gitlab_enhanced_api import format_error_response, format_gitlab_response

        # Test success response
        test_data = {"projects": [{"id": 1, "name": "test"}]}
        success_response = format_gitlab_response(test_data, message="Success")

        assert success_response["success"] is True
        assert success_response["service"] == "gitlab"
        assert success_response["data"] == test_data
        assert success_response["message"] == "Success"
        assert "timestamp" in success_response

        # Test error response
        error_response = format_error_response("Test error", 400)

        assert error_response["success"] is False
        assert error_response["service"] == "gitlab"
        assert error_response["error"] == "Test error"
        assert error_response["status_code"] == 400
        assert "timestamp" in error_response

        logger.info("✅ GitLab API response formatting test passed")

    @patch("gitlab_enhanced_api.get_gitlab_service")
    def test_gitlab_issue_creation(self, mock_get_service):
        """Test GitLab issue creation endpoint"""
        from gitlab_enhanced_api import create_issue

        # Mock service
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # Test issue creation
        issue_data = {
            "project_id": 1,
            "title": "Test Issue",
            "description": "Test issue description",
            "labels": ["bug", "test"],
            "assignee_ids": [123],
        }

        with self.app.test_request_context(json=issue_data):
            response = asyncio.run(create_issue())
            data = json.loads(response.get_data(as_text=True))

            assert response.status_code == 200
            assert data["success"] is True
            assert data["message"] == "Issue created successfully"
            assert "data" in data

        logger.info("✅ GitLab issue creation endpoint test passed")

    @patch("gitlab_enhanced_api.get_gitlab_service")
    def test_gitlab_merge_request_creation(self, mock_get_service):
        """Test GitLab merge request creation endpoint"""
        from gitlab_enhanced_api import create_merge_request

        # Mock service
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # Test merge request creation
        mr_data = {
            "project_id": 1,
            "title": "Test MR",
            "description": "Test merge request description",
            "source_branch": "feature/test",
            "target_branch": "main",
            "assignee_ids": [123],
        }

        with self.app.test_request_context(json=mr_data):
            response = asyncio.run(create_merge_request())
            data = json.loads(response.get_data(as_text=True))

            assert response.status_code == 200
            assert data["success"] is True
            assert data["message"] == "Merge request created successfully"
            assert "data" in data

        logger.info("✅ GitLab merge request creation endpoint test passed")

    def test_gitlab_integration_completeness(self):
        """Test overall GitLab integration completeness"""

        # Check all required components exist
        required_files = [
            "backend/python-api-service/auth_handler_gitlab.py",
            "backend/python-api-service/service_handlers/gitlab_handler.py",
            "backend/python-api-service/gitlab_enhanced_service.py",
            "backend/python-api-service/gitlab_enhanced_api.py",
            "backend/python-api-service/db_oauth_gitlab.py",
            "frontend-nextjs/pages/integrations/gitlab.tsx",
            "src/ui-shared/integrations/gitlab/components/GitLabManager.tsx",
            "src/skills/gitlabSkills.ts",
        ]

        for file_path in required_files:
            full_path = os.path.join(os.path.dirname(__file__), file_path)
            assert os.path.exists(full_path), f"Required file missing: {file_path}"

        # Check API endpoints
        api_endpoints_dir = os.path.join(
            os.path.dirname(__file__), "frontend-nextjs/pages/api/integrations/gitlab"
        )
        assert os.path.exists(api_endpoints_dir), (
            "GitLab API endpoints directory missing"
        )

        api_files = os.listdir(api_endpoints_dir)
        expected_endpoints = [
            "authorize.ts",
            "callback.ts",
            "projects.ts",
            "issues.ts",
            "merge-requests.ts",
            "pipelines.ts",
            "create-issue.ts",
            "create-merge-request.ts",
            "trigger-pipeline.ts",
            "status.ts",
        ]

        for endpoint in expected_endpoints:
            assert endpoint in api_files, f"API endpoint missing: {endpoint}"

        logger.info("✅ GitLab integration completeness test passed")


def run_comprehensive_tests():
    """Run all GitLab integration tests"""
    print("🚀 Running Comprehensive GitLab Integration Tests")
    print("=" * 60)

    test_instance = TestGitLabIntegration()

    # Run all test methods
    test_methods = [
        method
        for method in dir(test_instance)
        if method.startswith("test_") and callable(getattr(test_instance, method))
    ]

    passed = 0
    failed = 0

    for method_name in test_methods:
        try:
            test_instance.setup_method()
            method = getattr(test_instance, method_name)
            method()
            print(f"✅ {method_name} - PASSED")
            passed += 1
        except Exception as e:
            print(f"❌ {method_name} - FAILED: {str(e)}")
            failed += 1

    print("=" * 60)
    print(
        f"📊 Test Results: {passed} passed, {failed} failed out of {len(test_methods)} tests"
    )

    if failed == 0:
        print(
            "🎉 All GitLab integration tests passed! The integration is ready for production."
        )
        return True
    else:
        print("⚠️  Some tests failed. Please review and fix the issues.")
        return False


if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)
