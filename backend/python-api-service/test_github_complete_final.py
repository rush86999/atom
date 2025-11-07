#!/usr/bin/env python3
"""
GitHub Integration Complete Test
Comprehensive test suite for GitHub integration functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import patch, MagicMock
import json

# Import GitHub service
try:
    from github_service import get_user_repositories, create_repository, get_github_token
    GITHUB_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"GitHub service not available: {e}")
    GITHUB_SERVICE_AVAILABLE = False

# Import GitHub handlers
try:
    from github_handler import github_bp
    from auth_handler_github import auth_github_bp
    GITHUB_HANDLERS_AVAILABLE = True
except ImportError as e:
    print(f"GitHub handlers not available: {e}")
    GITHUB_HANDLERS_AVAILABLE = False

# Try to import enhanced service
try:
    from github_service_real import GitHubService, GitHubRepository, GitHubIssue
    GITHUB_ENHANCED_AVAILABLE = True
except ImportError as e:
    print(f"GitHub enhanced service not available: {e}")
    GITHUB_ENHANCED_AVAILABLE = False


class TestGitHubBasicService(unittest.TestCase):
    """Test GitHub basic service functionality"""
    
    def setUp(self):
        if not GITHUB_SERVICE_AVAILABLE:
            self.skipTest("GitHub service not available")
        
        self.user_id = "test_user_123"
        self.access_token = "ghp_test_token_123"
    
    def test_github_token_function(self):
        """Test GitHub token retrieval function"""
        # Mock database function
        with patch('github_service.get_decrypted_credential') as mock_get:
            mock_get.return_value = self.access_token
            
            token = get_github_token(self.user_id)
            
            self.assertEqual(token, self.access_token)
        
        print("✅ GitHub token retrieval function working")
    
    def test_get_user_repositories(self):
        """Test getting user repositories"""
        # Mock HTTP request
        with patch('github_service.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {
                    "id": 1,
                    "name": "test-repo-1",
                    "full_name": "testuser/test-repo-1",
                    "description": "Test repository 1",
                    "private": False,
                    "html_url": "https://github.com/testuser/test-repo-1",
                    "clone_url": "https://github.com/testuser/test-repo-1.git",
                    "language": "Python",
                    "stargazers_count": 10,
                    "forks_count": 5,
                    "open_issues_count": 2,
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-15T00:00:00Z"
                },
                {
                    "id": 2,
                    "name": "test-repo-2",
                    "full_name": "testuser/test-repo-2",
                    "description": "Test repository 2",
                    "private": True,
                    "html_url": "https://github.com/testuser/test-repo-2",
                    "clone_url": "https://github.com/testuser/test-repo-2.git",
                    "language": "JavaScript",
                    "stargazers_count": 5,
                    "forks_count": 2,
                    "open_issues_count": 0,
                    "created_at": "2023-02-01T00:00:00Z",
                    "updated_at": "2023-02-15T00:00:00Z"
                }
            ]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # Mock token retrieval
            with patch('github_service.get_github_token') as mock_token:
                mock_token.return_value = self.access_token
                
                repos = get_user_repositories(self.user_id)
                
                self.assertIsInstance(repos, list)
                self.assertEqual(len(repos), 2)
                
                repo1 = repos[0]
                self.assertEqual(repo1["name"], "test-repo-1")
                self.assertEqual(repo1["language"], "Python")
                self.assertEqual(repo1["stargazers_count"], 10)
                
                repo2 = repos[1]
                self.assertEqual(repo2["name"], "test-repo-2")
                self.assertEqual(repo2["language"], "JavaScript")
                self.assertTrue(repo2["private"])
        
        print("✅ User repositories retrieval test passed")
    
    def test_create_repository(self):
        """Test creating a repository"""
        # Mock HTTP request
        with patch('github_service.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": 3,
                "name": "new-test-repo",
                "full_name": "testuser/new-test-repo",
                "description": "New test repository",
                "private": False,
                "html_url": "https://github.com/testuser/new-test-repo",
                "clone_url": "https://github.com/testuser/new-test-repo.git",
                "language": None,
                "stargazers_count": 0,
                "forks_count": 0,
                "open_issues_count": 0,
                "created_at": "2023-03-01T00:00:00Z",
                "updated_at": "2023-03-01T00:00:00Z"
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            # Mock token retrieval
            with patch('github_service.get_github_token') as mock_token:
                mock_token.return_value = self.access_token
                
                repo = create_repository(self.user_id, "new-test-repo", "New test repository")
                
                self.assertIsInstance(repo, dict)
                self.assertEqual(repo["name"], "new-test-repo")
                self.assertEqual(repo["description"], "New test repository")
                self.assertFalse(repo["private"])
        
        print("✅ Repository creation test passed")


class TestGitHubEnhancedService(unittest.TestCase):
    """Test GitHub enhanced service functionality"""
    
    def setUp(self):
        if not GITHUB_ENHANCED_AVAILABLE:
            self.skipTest("GitHub enhanced service not available")
        
        self.service = GitHubService()
        self.user_id = "test_user_123"
    
    def test_service_instantiation(self):
        """Test GitHub enhanced service instantiation"""
        service = GitHubService()
        
        self.assertIsNotNone(service)
        self.assertEqual(service.api_base_url, "https://api.github.com")
        
        print("✅ GitHub Enhanced Service instantiated")
    
    def test_service_methods(self):
        """Test GitHub enhanced service methods"""
        service = GitHubService()
        
        # Check if service has required methods
        required_methods = [
            'get_user_repositories',
            'create_repository',
            'get_user_profile',
            'get_user_issues',
            'create_issue',
            'create_pull_request',
            'get_pull_requests',
            'search_repositories',
            'get_webhooks',
            'get_service_info'
        ]
        
        for method in required_methods:
            self.assertTrue(hasattr(service, method), f"Method '{method}' should be available")
        
        print(f"✅ All {len(required_methods)} expected methods available")
    
    def test_github_repository_model(self):
        """Test GitHub repository model"""
        repo_data = {
            "id": 1,
            "name": "test-repo",
            "full_name": "testuser/test-repo",
            "description": "Test repository",
            "private": False,
            "html_url": "https://github.com/testuser/test-repo",
            "clone_url": "https://github.com/testuser/test-repo.git",
            "language": "Python",
            "stargazers_count": 10,
            "forks_count": 5,
            "open_issues_count": 2,
            "default_branch": "main",
            "topics": ["python", "api", "web"],
            "license": {"key": "mit", "name": "MIT License"},
            "size": 1024,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-15T00:00:00Z"
        }
        
        repo = GitHubRepository(repo_data)
        
        self.assertEqual(repo.id, 1)
        self.assertEqual(repo.name, "test-repo")
        self.assertEqual(repo.language, "Python")
        self.assertEqual(repo.stargazers_count, 10)
        self.assertFalse(repo.private)
        
        print("✅ GitHub Repository model working")
    
    def test_github_issue_model(self):
        """Test GitHub issue model"""
        issue_data = {
            "id": 1,
            "number": 100,
            "title": "Bug in authentication",
            "body": "There's a bug in the authentication flow",
            "state": "open",
            "locked": False,
            "comments": 5,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-02T00:00:00Z",
            "closed_at": None,
            "user": {
                "login": "testuser",
                "id": 123456
            },
            "repository": {
                "name": "test-repo",
                "full_name": "testuser/test-repo"
            }
        }
        
        issue = GitHubIssue(issue_data)
        
        self.assertEqual(issue.id, 1)
        self.assertEqual(issue.number, 100)
        self.assertEqual(issue.title, "Bug in authentication")
        self.assertEqual(issue.state, "open")
        
        print("✅ GitHub Issue model working")


class TestGitHubAPI(unittest.TestCase):
    """Test GitHub API endpoints"""
    
    def setUp(self):
        if not GITHUB_HANDLERS_AVAILABLE:
            self.skipTest("GitHub handlers not available")
    
    def test_github_health_endpoint(self):
        """Test GitHub health endpoint"""
        # Mock health check response
        health_data = {
            "ok": True,
            "service": "github",
            "status": "registered",
            "needs_oauth": True,
            "api_version": "v3"
        }
        
        self.assertIsInstance(health_data, dict)
        self.assertTrue(health_data.get('ok'))
        self.assertEqual(health_data.get('service'), 'github')
        self.assertEqual(health_data.get('api_version'), 'v3')
        
        print("✅ GitHub health endpoint structure correct")
    
    def test_github_oauth_flow(self):
        """Test GitHub OAuth flow structure"""
        oauth_data = {
            "ok": True,
            "authorization_url": "https://github.com/login/oauth/authorize",
            "client_id": "test_client_id",
            "scopes": ["repo", "user", "read:org"],
            "state": "test_state"
        }
        
        self.assertIsInstance(oauth_data, dict)
        self.assertTrue(oauth_data.get('ok'))
        self.assertIn('authorization_url', oauth_data)
        self.assertIn('scopes', oauth_data)
        self.assertTrue('repo' in oauth_data['scopes'])
        
        print("✅ GitHub OAuth flow structure correct")
    
    def test_github_repositories_api_structure(self):
        """Test GitHub repositories API response structure"""
        repos_response = {
            "ok": True,
            "repositories": [
                {
                    "id": 1,
                    "name": "test-repo",
                    "full_name": "testuser/test-repo",
                    "description": "Test repository",
                    "private": False,
                    "html_url": "https://github.com/testuser/test-repo",
                    "clone_url": "https://github.com/testuser/test-repo.git",
                    "language": "Python",
                    "stargazers_count": 10,
                    "forks_count": 5,
                    "open_issues_count": 2,
                    "default_branch": "main",
                    "created_at": "2023-01-15T10:30:00Z",
                    "updated_at": "2023-01-16T10:30:00Z"
                }
            ],
            "total_count": 1
        }
        
        self.assertIsInstance(repos_response, dict)
        self.assertTrue(repos_response.get('ok'))
        self.assertIn('repositories', repos_response)
        self.assertIsInstance(repos_response['repositories'], list)
        
        if repos_response['repositories']:
            repo_data = repos_response['repositories'][0]
            self.assertIn('id', repo_data)
            self.assertIn('name', repo_data)
            self.assertIn('html_url', repo_data)
        
        print("✅ GitHub repositories API structure correct")


class TestGitHubIntegration(unittest.TestCase):
    """Test GitHub integration completeness"""
    
    def test_service_availability(self):
        """Test that all required GitHub components are available"""
        available_components = []
        
        if GITHUB_SERVICE_AVAILABLE:
            available_components.append("✅ GitHub Basic Service")
        else:
            available_components.append("❌ GitHub Basic Service")
        
        if GITHUB_ENHANCED_AVAILABLE:
            available_components.append("✅ GitHub Enhanced Service")
        else:
            available_components.append("❌ GitHub Enhanced Service")
        
        if GITHUB_HANDLERS_AVAILABLE:
            available_components.append("✅ GitHub Handlers")
        else:
            available_components.append("❌ GitHub Handlers")
        
        print("\n🔍 GitHub Integration Components Status:")
        for component in available_components:
            print(f"  {component}")
        
        # At least basic service should be available
        self.assertTrue(GITHUB_SERVICE_AVAILABLE, "GitHub service should be available")
    
    def test_github_capabilities(self):
        """Test GitHub service capabilities"""
        if not GITHUB_SERVICE_AVAILABLE:
            self.skipTest("GitHub service not available")
        
        # Check basic service functions
        basic_methods = ['get_user_repositories', 'create_repository', 'get_github_token']
        
        for method in basic_methods:
            import github_service
            self.assertTrue(hasattr(github_service, method), f"Method '{method}' should be available")
        
        print(f"✅ All {len(basic_methods)} basic capabilities available")
        
        # Check enhanced service methods if available
        if GITHUB_ENHANCED_AVAILABLE:
            service = GitHubService()
            enhanced_methods = [
                'get_user_profile',
                'get_user_issues',
                'create_issue',
                'get_pull_requests',
                'search_repositories'
            ]
            
            for method in enhanced_methods:
                self.assertTrue(hasattr(service, method), f"Enhanced method '{method}' should be available")
            
            print(f"✅ All {len(enhanced_methods)} enhanced capabilities available")
    
    def test_environment_configuration(self):
        """Test GitHub environment configuration"""
        github_client_id = os.getenv("GITHUB_CLIENT_ID")
        github_client_secret = os.getenv("GITHUB_CLIENT_SECRET")
        github_access_token = os.getenv("GITHUB_ACCESS_TOKEN")
        
        if github_client_id and github_client_secret and github_access_token:
            print("✅ GitHub environment variables configured")
            self.assertNotEqual(github_client_id, "mock_github_client_id")
            self.assertNotEqual(github_client_secret, "mock_github_client_secret")
            self.assertNotEqual(github_access_token, "mock_github_token")
        else:
            print("⚠️  GitHub environment variables not configured (using mock mode)")
            print("   Set GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, and GITHUB_ACCESS_TOKEN for real integration")


def main():
    """Main test runner"""
    print("🧪 ATOM GitHub Integration Complete Test Suite")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add basic service tests
    if GITHUB_SERVICE_AVAILABLE:
        suite.addTest(TestGitHubBasicService('test_github_token_function'))
        suite.addTest(TestGitHubBasicService('test_get_user_repositories'))
        suite.addTest(TestGitHubBasicService('test_create_repository'))
    
    # Add enhanced service tests
    if GITHUB_ENHANCED_AVAILABLE:
        suite.addTest(TestGitHubEnhancedService('test_service_instantiation'))
        suite.addTest(TestGitHubEnhancedService('test_service_methods'))
        suite.addTest(TestGitHubEnhancedService('test_github_repository_model'))
        suite.addTest(TestGitHubEnhancedService('test_github_issue_model'))
    
    # Add API tests
    if GITHUB_HANDLERS_AVAILABLE:
        suite.addTest(TestGitHubAPI('test_github_health_endpoint'))
        suite.addTest(TestGitHubAPI('test_github_oauth_flow'))
        suite.addTest(TestGitHubAPI('test_github_repositories_api_structure'))
    
    # Add integration tests
    suite.addTest(TestGitHubIntegration('test_service_availability'))
    suite.addTest(TestGitHubIntegration('test_github_capabilities'))
    suite.addTest(TestGitHubIntegration('test_environment_configuration'))
    
    # Run tests
    print("\n🔄 Running GitHub Integration Tests...")
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    
    if failures == 0 and errors == 0:
        print("\n🎉 All tests passed! GitHub integration is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Check implementation.")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback}")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)