import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os

# Add the parent directory to the path to import the routes
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_routes import github_bp
from github_service import GitHubService


class TestGitHubRoutes:
    """Test suite for GitHub integration routes"""

    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.app = Mock()
        self.app.testing = True
        self.client = self.app.test_client()

        # Register the blueprint
        self.app.register_blueprint(github_bp)

        # Mock the GitHub service
        self.mock_service = Mock(spec=GitHubService)
        self.mock_service.access_token = "test_token"

        # Replace the global service instance
        import github_routes
        github_routes.github_service = self.mock_service

    def test_github_status_success(self):
        """Test GitHub status endpoint with successful authentication"""
        # Mock health check response
        self.mock_service.health_check.return_value = {
            "status": "healthy",
            "service": "github",
            "user": "testuser",
            "rate_limit_remaining": 4999,
            "rate_limit_reset": 1700000000,
            "timestamp": datetime.now().isoformat()
        }

        with self.app.test_client() as client:
            response = client.get('/api/github/status', headers={'X-User-ID': 'test_user'})

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['service'] == 'github'
            assert data['user_id'] == 'test_user'
            assert data['status'] == 'healthy'
            assert data['authenticated'] is True
            assert 'timestamp' in data

    def test_github_status_unauthorized(self):
        """Test GitHub status endpoint without authentication"""
        # Remove access token to simulate unauthorized state
        self.mock_service.access_token = None

        with self.app.test_client() as client:
            response = client.get('/api/github/status', headers={'X-User-ID': 'test_user'})

            assert response.status_code == 401
            data = json.loads(response.data)
            assert data['ok'] is False
            assert 'GitHub access token required' in data['error']

    def test_set_github_token_success(self):
        """Test setting GitHub access token successfully"""
        with self.app.test_client() as client:
            response = client.post('/api/github/auth/set-token',
                                 json={'access_token': 'new_test_token'})

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['message'] == 'GitHub access token set successfully'

            # Verify the service method was called
            self.mock_service.set_access_token.assert_called_once_with('new_test_token')

    def test_set_github_token_missing_token(self):
        """Test setting GitHub access token with missing token"""
        with self.app.test_client() as client:
            response = client.post('/api/github/auth/set-token', json={})

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['ok'] is False
            assert 'access_token is required' in data['error']

    def test_get_user_profile_success(self):
        """Test getting user profile successfully"""
        mock_profile = {
            "id": 1,
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "avatar_url": "https://example.com/avatar.jpg"
        }
        self.mock_service.get_user_profile.return_value = mock_profile

        with self.app.test_client() as client:
            response = client.get('/api/github/user/profile')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['profile'] == mock_profile
            self.mock_service.get_user_profile.assert_called_once()

    def test_get_user_profile_failure(self):
        """Test getting user profile when API fails"""
        self.mock_service.get_user_profile.return_value = None

        with self.app.test_client() as client:
            response = client.get('/api/github/user/profile')

            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['ok'] is False
            assert 'Failed to fetch user profile' in data['error']

    def test_get_organizations_success(self):
        """Test getting organizations successfully"""
        mock_orgs = [
            {"id": 1, "login": "org1", "name": "Organization 1"},
            {"id": 2, "login": "org2", "name": "Organization 2"}
        ]
        self.mock_service.get_organizations.return_value = mock_orgs

        with self.app.test_client() as client:
            response = client.get('/api/github/user/organizations')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['organizations'] == mock_orgs
            assert data['count'] == 2

    def test_get_repositories_user(self):
        """Test getting user repositories"""
        mock_repos = [
            {"id": 1, "name": "repo1", "private": False},
            {"id": 2, "name": "repo2", "private": True}
        ]
        self.mock_service.get_repositories.return_value = mock_repos

        with self.app.test_client() as client:
            response = client.get('/api/github/repositories')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['repositories'] == mock_repos
            assert data['count'] == 2
            self.mock_service.get_repositories.assert_called_once_with(org=None, visibility='all')

    def test_get_repositories_org(self):
        """Test getting organization repositories"""
        mock_repos = [{"id": 1, "name": "org-repo", "private": False}]
        self.mock_service.get_repositories.return_value = mock_repos

        with self.app.test_client() as client:
            response = client.get('/api/github/repositories?org=testorg&visibility=public')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['org'] == 'testorg'
            assert data['visibility'] == 'public'
            self.mock_service.get_repositories.assert_called_once_with(org='testorg', visibility='public')

    def test_get_repository_success(self):
        """Test getting specific repository successfully"""
        mock_repo = {
            "id": 1,
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "private": False
        }
        self.mock_service.get_repository.return_value = mock_repo

        with self.app.test_client() as client:
            response = client.get('/api/github/repositories/owner/test-repo')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['repository'] == mock_repo

    def test_get_repository_not_found(self):
        """Test getting non-existent repository"""
        self.mock_service.get_repository.return_value = None

        with self.app.test_client() as client:
            response = client.get('/api/github/repositories/owner/nonexistent')

            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['ok'] is False
            assert 'Repository owner/nonexistent not found' in data['error']

    def test_create_repository_success(self):
        """Test creating repository successfully"""
        mock_repo = {
            "id": 1,
            "name": "new-repo",
            "full_name": "user/new-repo",
            "private": True
        }
        self.mock_service.create_repository.return_value = mock_repo

        with self.app.test_client() as client:
            response = client.post('/api/github/repositories',
                                 json={
                                     'name': 'new-repo',
                                     'description': 'Test repository',
                                     'private': True,
                                     'auto_init': True
                                 })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['repository'] == mock_repo
            self.mock_service.create_repository.assert_called_once_with(
                name='new-repo',
                description='Test repository',
                private=True,
                auto_init=True
            )

    def test_create_repository_missing_name(self):
        """Test creating repository without required name"""
        with self.app.test_client() as client:
            response = client.post('/api/github/repositories',
                                 json={'description': 'Test repository'})

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['ok'] is False
            assert 'Repository name is required' in data['error']

    def test_get_issues_success(self):
        """Test getting issues successfully"""
        mock_issues = [
            {"id": 1, "title": "Issue 1", "state": "open"},
            {"id": 2, "title": "Issue 2", "state": "open"}
        ]
        self.mock_service.get_issues.return_value = mock_issues

        with self.app.test_client() as client:
            response = client.get('/api/github/repositories/owner/repo/issues?state=open&labels=bug,enhancement')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['issues'] == mock_issues
            assert data['state'] == 'open'
            self.mock_service.get_issues.assert_called_once_with(
                'owner', 'repo', state='open', labels=['bug', 'enhancement']
            )

    def test_create_issue_success(self):
        """Test creating issue successfully"""
        mock_issue = {
            "id": 1,
            "title": "New Issue",
            "body": "Issue description",
            "state": "open"
        }
        self.mock_service.create_issue.return_value = mock_issue

        with self.app.test_client() as client:
            response = client.post('/api/github/repositories/owner/repo/issues',
                                 json={
                                     'title': 'New Issue',
                                     'body': 'Issue description',
                                     'labels': ['bug', 'enhancement'],
                                     'assignees': ['user1']
                                 })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['issue'] == mock_issue
            self.mock_service.create_issue.assert_called_once_with(
                owner='owner',
                repo='repo',
                title='New Issue',
                body='Issue description',
                labels=['bug', 'enhancement'],
                assignees=['user1']
            )

    def test_create_issue_missing_title(self):
        """Test creating issue without required title"""
        with self.app.test_client() as client:
            response = client.post('/api/github/repositories/owner/repo/issues',
                                 json={'body': 'Issue description'})

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['ok'] is False
            assert 'Issue title is required' in data['error']

    def test_get_pull_requests_success(self):
        """Test getting pull requests successfully"""
        mock_prs = [
            {"id": 1, "title": "PR 1", "state": "open"},
            {"id": 2, "title": "PR 2", "state": "closed"}
        ]
        self.mock_service.get_pull_requests.return_value = mock_prs

        with self.app.test_client() as client:
            response = client.get('/api/github/repositories/owner/repo/pulls?state=open')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['pull_requests'] == mock_prs
            assert data['state'] == 'open'
            self.mock_service.get_pull_requests.assert_called_once_with(
                'owner', 'repo', state='open'
            )

    def test_create_pull_request_success(self):
        """Test creating pull request successfully"""
        mock_pr = {
            "id": 1,
            "title": "New PR",
            "head": "feature-branch",
            "base": "main",
            "state": "open"
        }
        self.mock_service.create_pull_request.return_value = mock_pr

        with self.app.test_client() as client:
            response = client.post('/api/github/repositories/owner/repo/pulls',
                                 json={
                                     'title': 'New PR',
                                     'head': 'feature-branch',
                                     'base': 'main',
                                     'body': 'PR description'
                                 })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['pull_request'] == mock_pr
            self.mock_service.create_pull_request.assert_called_once_with(
                owner='owner',
                repo='repo',
                title='New PR',
                head='feature-branch',
                base='main',
                body='PR description'
            )

    def test_create_pull_request_missing_fields(self):
        """Test creating pull request with missing required fields"""
        with self.app.test_client() as client:
            response = client.post('/api/github/repositories/owner/repo/pulls',
                                 json={'title': 'New PR'})

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['ok'] is False
            assert "Field 'head' is required" in data['error']

    def test_get_workflow_runs_success(self):
        """Test getting workflow runs successfully"""
        mock_workflows = [
            {"id": 1, "name": "CI", "status": "completed"},
            {"id": 2, "name": "Deploy", "status": "in_progress"}
        ]
        self.mock_service.get_workflow_runs.return_value = mock_workflows

        with self.app.test_client() as client:
            response = client.get('/api/github/repositories/owner/repo/workflows?branch=main')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['workflow_runs'] == mock_workflows
            assert data['branch'] == 'main'
            self.mock_service.get_workflow_runs.assert_called_once_with(
                'owner', 'repo', branch='main'
            )

    def test_search_code_success(self):
        """Test searching code successfully"""
        mock_results = [
            {"id": 1, "name": "file1.py", "path": "src/file1.py"},
            {"id": 2, "name": "file2.py", "path": "src/file2.py"}
        ]
        self.mock_service.search_code.return_value = mock_results

        with self.app.test_client() as client:
            response = client.get('/api/github/search/code?q=test+query&org=testorg')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['query'] == 'test query'
            assert data['org'] == 'testorg'
            assert data['results'] == mock_results
            self.mock_service.search_code.assert_called_once_with(
                query='test query', org='testorg'
            )

    def test_search_code_missing_query(self):
        """Test searching code without query"""
        with self.app.test_client() as client:
            response = client.get('/api/github/search/code')

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['ok'] is False
            assert "Search query parameter 'q' is required" in data['error']

    def test_search_issues_success(self):
        """Test searching issues successfully"""
        mock_results = [
            {"id": 1, "title": "Issue 1", "state": "open"},
            {"id": 2, "title": "Issue 2", "state": "closed"}
        ]
        self.mock_service.search_issues.return_value = mock_results

        with self.app.test_client() as client:
            response = client.get('/api/github/search/issues?q=bug&org=testorg')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['query'] == 'bug'
            assert data['org'] == 'testorg'
            assert data['results'] == mock_results
            self.mock_service.search_issues.assert_called_once_with(
                query='bug', org='testorg'
            )

    def test_get_rate_limit_success(self):
        """Test getting rate limit successfully"""
        mock_rate_limit = {
            "resources": {
                "core": {"limit": 5000, "remaining": 4999, "reset": 1700000000},
                "search": {"limit": 30, "remaining": 29, "reset": 1700000000}
            }
        }
        self.mock_service.get_rate_limit.return_value = mock_rate_limit

        with self.app.test_client() as client:
            response = client.get('/api/github/rate-limit')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok'] is True
            assert data['rate_limit'] == mock_rate_limit

    def test_get_rate_limit_failure(self):
        """Test getting rate limit when API fails"""
        self.mock_service.get_rate_limit.return_value = None

        with self.app.test_client() as client:
            response = client.get('/api/github/rate-limit')

            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['ok'] is False
            assert 'Failed to fetch rate limit' in data['error']

    def test_health_check_success(self):
        """Test health check endpoint"""
        mock_health = {
            "status": "healthy",
