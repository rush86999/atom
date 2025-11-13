import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import sys
import os

# Add the parent directory to the path to import the service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_service import GitHubService, GitHubServiceType


class TestGitHubService:
    """Test suite for GitHubService"""

    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.service = GitHubService()
        self.service.set_access_token("test_access_token")

    def test_initialization(self):
        """Test GitHubService initialization"""
        service = GitHubService()
        assert service.api_base_url == "https://api.github.com"
        assert service.timeout == 30
        assert service.max_retries == 3
        assert service.client_id is None or isinstance(service.client_id, str)
        assert service.client_secret is None or isinstance(service.client_secret, str)

    def test_set_access_token(self):
        """Test setting access token"""
        service = GitHubService()
        service.set_access_token("test_token")
        assert service.access_token == "test_token"

    @patch('github_service.requests.request')
    def test_make_request_success(self, mock_request):
        """Test successful API request"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "name": "test"}
        mock_response.headers = {
            "X-RateLimit-Remaining": "4999",
            "X-RateLimit-Reset": "1700000000"
        }
        mock_request.return_value = mock_response

        result = self.service._make_request("GET", "/user")

        assert result == {"id": 1, "name": "test"}
        assert self.service.rate_limit_remaining == 4999
        assert self.service.rate_limit_reset == 1700000000
        mock_request.assert_called_once()

    @patch('github_service.requests.request')
    def test_make_request_unauthorized(self, mock_request):
        """Test API request with unauthorized error"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_request.return_value = mock_response

        result = self.service._make_request("GET", "/user")

        assert result is None

    @patch('github_service.requests.request')
    def test_make_request_rate_limit_retry(self, mock_request):
        """Test API request with rate limiting and retry"""
        # First call: rate limited
        mock_response1 = Mock()
        mock_response1.status_code = 429
        mock_response1.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(datetime.now().timestamp()) + 10)
        }

        # Second call: success
        mock_response2 = Mock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = {"id": 1, "name": "test"}
        mock_response2.headers = {
            "X-RateLimit-Remaining": "4999",
            "X-RateLimit-Reset": "1700000000"
        }

        mock_request.side_effect = [mock_response1, mock_response2]

        result = self.service._make_request("GET", "/user")

        assert result == {"id": 1, "name": "test"}
        assert mock_request.call_count == 2

    @patch('github_service.requests.request')
    def test_make_request_network_error_retry(self, mock_request):
        """Test API request with network error and retry"""
        # First call: network error
        mock_request.side_effect = [
            Exception("Network error"),
            Mock(status_code=200, json=lambda: {"id": 1}, headers={})
        ]

        result = self.service._make_request("GET", "/user")

        assert result == {"id": 1}
        assert mock_request.call_count == 2

    def test_get_headers_with_token(self):
        """Test headers generation with access token"""
        self.service.set_access_token("test_token")
        headers = self.service._get_headers()

        expected_headers = {
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "Authorization": "token test_token"
        }
        assert headers == expected_headers

    def test_get_headers_without_token(self):
        """Test headers generation without access token"""
        service = GitHubService()  # No token set
        headers = service._get_headers()

        expected_headers = {
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        assert headers == expected_headers

    @patch.object(GitHubService, '_make_request')
    def test_get_user_profile(self, mock_make_request):
        """Test getting user profile"""
        mock_make_request.return_value = {
            "id": 1,
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com"
        }

        result = self.service.get_user_profile()

        assert result == {
            "id": 1,
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com"
        }
        mock_make_request.assert_called_once_with("GET", "/user")

    @patch.object(GitHubService, '_make_request')
    def test_get_organizations(self, mock_make_request):
        """Test getting organizations"""
        mock_make_request.return_value = [
            {"id": 1, "login": "org1"},
            {"id": 2, "login": "org2"}
        ]

        result = self.service.get_organizations()

        assert result == [
            {"id": 1, "login": "org1"},
            {"id": 2, "login": "org2"}
        ]
        mock_make_request.assert_called_once_with("GET", "/user/orgs")

    @patch.object(GitHubService, '_make_request')
    def test_get_repositories_user(self, mock_make_request):
        """Test getting user repositories"""
        mock_make_request.return_value = [
            {"id": 1, "name": "repo1", "private": False},
            {"id": 2, "name": "repo2", "private": True}
        ]

        result = self.service.get_repositories()

        assert result == [
            {"id": 1, "name": "repo1", "private": False},
            {"id": 2, "name": "repo2", "private": True}
        ]
        mock_make_request.assert_called_once_with("GET", "/user/repos")

    @patch.object(GitHubService, '_make_request')
    def test_get_repositories_org(self, mock_make_request):
        """Test getting organization repositories"""
        mock_make_request.return_value = [
            {"id": 1, "name": "org-repo1", "private": False}
        ]

        result = self.service.get_repositories(org="testorg")

        assert result == [{"id": 1, "name": "org-repo1", "private": False}]
        mock_make_request.assert_called_once_with("GET", "/orgs/testorg/repos")

    @patch.object(GitHubService, '_make_request')
    def test_get_repository(self, mock_make_request):
        """Test getting specific repository"""
        mock_make_request.return_value = {
            "id": 1,
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "private": False,
            "html_url": "https://github.com/owner/test-repo"
        }

        result = self.service.get_repository("owner", "test-repo")

        assert result == {
            "id": 1,
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "private": False,
            "html_url": "https://github.com/owner/test-repo"
        }
        mock_make_request.assert_called_once_with("GET", "/repos/owner/test-repo")

    @patch.object(GitHubService, '_make_request')
    def test_create_repository(self, mock_make_request):
        """Test creating repository"""
        mock_make_request.return_value = {
            "id": 1,
            "name": "new-repo",
            "full_name": "user/new-repo",
            "private": True
        }

        result = self.service.create_repository(
            name="new-repo",
            description="Test repository",
            private=True,
            auto_init=True
        )

        expected_data = {
            "name": "new-repo",
            "description": "Test repository",
            "private": True,
            "auto_init": True
        }
        assert result == {
            "id": 1,
            "name": "new-repo",
            "full_name": "user/new-repo",
            "private": True
        }
        mock_make_request.assert_called_once_with("POST", "/user/repos", expected_data)

    @patch.object(GitHubService, '_make_request')
    def test_get_issues(self, mock_make_request):
        """Test getting issues"""
        mock_make_request.return_value = [
            {"id": 1, "title": "Issue 1", "state": "open"},
            {"id": 2, "title": "Issue 2", "state": "closed"}
        ]

        result = self.service.get_issues("owner", "repo", state="open")

        assert result == [
            {"id": 1, "title": "Issue 1", "state": "open"},
            {"id": 2, "title": "Issue 2", "state": "closed"}
        ]
        mock_make_request.assert_called_once_with("GET", "/repos/owner/repo/issues")

    @patch.object(GitHubService, '_make_request')
    def test_create_issue(self, mock_make_request):
        """Test creating issue"""
        mock_make_request.return_value = {
            "id": 1,
            "title": "New Issue",
            "body": "Issue description",
            "state": "open"
        }

        result = self.service.create_issue(
            owner="owner",
            repo="repo",
            title="New Issue",
            body="Issue description",
            labels=["bug", "enhancement"],
            assignees=["user1"]
        )

        expected_data = {
            "title": "New Issue",
            "body": "Issue description",
            "labels": ["bug", "enhancement"],
            "assignees": ["user1"]
        }
        assert result == {
            "id": 1,
            "title": "New Issue",
            "body": "Issue description",
            "state": "open"
        }
        mock_make_request.assert_called_once_with(
            "POST", "/repos/owner/repo/issues", expected_data
        )

    @patch.object(GitHubService, '_make_request')
    def test_get_pull_requests(self, mock_make_request):
        """Test getting pull requests"""
        mock_make_request.return_value = [
            {"id": 1, "title": "PR 1", "state": "open"},
            {"id": 2, "title": "PR 2", "state": "closed"}
        ]

        result = self.service.get_pull_requests("owner", "repo", state="open")

        assert result == [
            {"id": 1, "title": "PR 1", "state": "open"},
            {"id": 2, "title": "PR 2", "state": "closed"}
        ]
        mock_make_request.assert_called_once_with("GET", "/repos/owner/repo/pulls")

    @patch.object(GitHubService, '_make_request')
    def test_create_pull_request(self, mock_make_request):
        """Test creating pull request"""
        mock_make_request.return_value = {
            "id": 1,
            "title": "New PR",
            "head": "feature-branch",
            "base": "main",
            "state": "open"
        }

        result = self.service.create_pull_request(
            owner="owner",
            repo="repo",
            title="New PR",
            head="feature-branch",
            base="main",
            body="PR description"
        )

        expected_data = {
            "title": "New PR",
            "head": "feature-branch",
            "base": "main",
            "body": "PR description"
        }
        assert result == {
            "id": 1,
            "title": "New PR",
            "head": "feature-branch",
            "base": "main",
            "state": "open"
        }
        mock_make_request.assert_called_once_with(
            "POST", "/repos/owner/repo/pulls", expected_data
        )

    @patch.object(GitHubService, '_make_request')
    def test_get_workflow_runs(self, mock_make_request):
        """Test getting workflow runs"""
        mock_make_request.return_value = {
            "workflow_runs": [
                {"id": 1, "name": "CI", "status": "completed"},
                {"id": 2, "name": "Deploy", "status": "in_progress"}
            ]
        }

        result = self.service.get_workflow_runs("owner", "repo", branch="main")

        assert result == [
            {"id": 1, "name": "CI", "status": "completed"},
            {"id": 2, "name": "Deploy", "status": "in_progress"}
        ]
        mock_make_request.assert_called_once_with("GET", "/repos/owner/repo/actions/runs")

    @patch.object(GitHubService, '_make_request')
    def test_search_code(self, mock_make_request):
        """Test searching code"""
        mock_make_request.return_value = {
            "items": [
                {"id": 1, "name": "file1.py", "path": "src/file1.py"},
                {"id": 2, "name": "file2.py", "path": "src/file2.py"}
            ]
        }

        result = self.service.search_code("test query", org="testorg")

        assert result == [
            {"id": 1, "name": "file1.py", "path": "src/file1.py"},
            {"id": 2, "name": "file2.py", "path": "src/file2.py"}
        ]
        mock_make_request.assert_called_once_with("GET", "/search/code?q=org:testorg test query")

    @patch.object(GitHubService, '_make_request')
    def test_search_issues(self, mock_make_request):
        """Test searching issues"""
        mock_make_request.return_value = {
            "items": [
                {"id": 1, "title": "Issue 1", "state": "open"},
                {"id": 2, "title": "Issue 2", "state": "closed"}
            ]
        }

        result = self.service.search_issues("bug", org="testorg")

        assert result == [
            {"id": 1, "title": "Issue 1", "state": "open"},
            {"id": 2, "title": "Issue 2", "state": "closed"}
        ]
        mock_make_request.assert_called_once_with("GET", "/search/issues?q=org:testorg bug")

    @patch.object(GitHubService, '_make_request')
    def test_get_rate_limit(self, mock_make_request):
        """Test getting rate limit"""
        mock_make_request.return_value = {
            "resources": {
                "core": {"limit": 5000, "remaining": 4999, "reset": 1700000000},
                "search": {"limit": 30, "remaining": 29, "reset": 1700000000}
            }
        }

        result = self.service.get_rate_limit()

        assert result == {
            "resources": {
                "core": {"limit": 5000, "remaining": 4999, "reset": 1700000000},
                "search": {"limit": 30, "remaining": 29, "reset": 1700000000}
            }
        }
        mock_make_request.assert_called_once_with("GET", "/rate_limit")

    @patch.object(GitHubService, 'get_user_profile')
    @patch.object(GitHubService, 'get_rate_limit')
    def test_health_check_healthy(self, mock_get_rate_limit, mock_get_user_profile):
        """Test health check when service is healthy"""
        mock_get_user_profile.return_value = {"login": "testuser"}
        mock_get_rate_limit.return_value = {
            "resources": {"core": {"remaining": 4999, "reset": 1700000000}}
        }

        result = self.service.health_check()

        assert result["status"] == "healthy"
        assert result["service"] == "github"
        assert result["user"] == "testuser"
        assert "timestamp" in result

    @patch.object(GitHubService, 'get_user_profile')
    def test_health_check_unhealthy(self, mock_get_user_profile):
        """Test health check when service is unhealthy"""
        mock_get_user_profile.return_value = None

        result = self.service.health_check()

        assert result["status"] == "unhealthy"
        assert result["service"] == "github"
        assert "error" in result
        assert "timestamp" in result

    @patch.object(GitHubService, '_make_request')
    def test_create_webhook(self, mock_make_request):
        """Test creating webhook"""
        mock_make_request.return_value = {
            "id": 1,
            "name": "web",
            "active": True,
            "events": ["push", "pull_request"]
        }

        result = self.service.create_webhook(
            owner="owner",
            repo="repo",
            url="https://example.com/webhook",
            events=["push", "pull_request"]
        )

        expected_data = {
            "name": "web",
            "active": True,
            "events": ["push", "pull_request"],
            "config": {
                "url": "https://example.com/webhook",
                "content_type": "json"
            }
        }
        assert result == {
            "id": 1,
            "name": "web",
            "active": True,
            "events": ["push", "pull_request"]
        }
        mock_make_request.assert_called_once_with(
