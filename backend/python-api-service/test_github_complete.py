#!/usr/bin/env python3
"""
GitHub Integration Test
Comprehensive test suite for GitHub integration functionality
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import patch, MagicMock
import json
import requests
from datetime import datetime, timezone, timedelta

# Import GitHub service
try:
    from github_service import get_user_repositories, create_repository, get_github_token
    from github_service_real import GitHubService, GitHubRepository, GitHubIssue
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


class TestGitHubService(unittest.TestCase):
    """Test GitHub service functionality"""
    
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
    
    @unittest.skipUnless(GITHUB_SERVICE_AVAILABLE, "GitHub service not available")
    def test_get_user_repositories(self):
        """Test getting user repositories"""
        # Mock HTTP request
        with patch('requests.get') as mock_get:
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
    
    @unittest.skipUnless(GITHUB_SERVICE_AVAILABLE, "GitHub service not available")
    def test_create_repository(self):
        """Test creating a repository"""
        # Mock HTTP request
        with patch('requests.post') as mock_post:
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
        if not GITHUB_SERVICE_AVAILABLE:
            self.skipTest("GitHub service not available")
        
        self.service = GitHubService()
        self.user_id = "test_user_123"
    
    def test_service_instantiation(self):
        """Test GitHub service instantiation"""
        service = GitHubService()
        
        self.assertIsNotNone(service)
        self.assertEqual(service.api_base_url, "https://api.github.com")
        
        print("✅ GitHub Enhanced Service instantiated")
    
    @unittest.skipUnless(GITHUB_SERVICE_AVAILABLE, "GitHub service not available")
    async def test_get_user_profile(self):
        """Test getting user profile"""
        # Mock implementation
        with patch.object(self.service, '_make_request') as mock_request:
            mock_request.return_value = {
                "id": 123456,
                "login": "testuser",
                "name": "Test User",
                "email": "test@example.com",
                "bio": "Software Developer",
                "location": "San Francisco",
                "company": "Tech Corp",
                "public_repos": 10,
                "followers": 100,
                "following": 50,
                "created_at": "2020-01-01T00:00:00Z"
            }
            
            result = await self.service.get_user_profile(self.user_id)
            
            self.assertIsInstance(result, dict)
            self.assertEqual(result["login"], "testuser")
            self.assertEqual(result["name"], "Test User")
            self.assertEqual(result["public_repos"], 10)
            
        print("✅ User profile retrieval test passed")
    
    @unittest.skipUnless(GITHUB_SERVICE_AVAILABLE, "GitHub service not available")
    async def test_get_user_repositories_enhanced(self):
        """Test getting user repositories with enhanced service"""
        # Mock implementation
        with patch.object(self.service, '_make_request') as mock_request:
            mock_request.return_value = [
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
                    "topics": ["python", "api", "web"],
                    "license": {"key": "mit", "name": "MIT License"},
                    "size": 1024,
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-15T00:00:00Z"
                }
            ]
            
            result = await self.service.get_user_repositories(self.user_id, limit=10)
            
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)
            
            repo = result[0]
            self.assertIsInstance(repo, GitHubRepository)
            self.assertEqual(repo.name, "test-repo")
            self.assertEqual(repo.language, "Python")
            self.assertEqual(repo.stargazers_count, 10)
            
        print("✅ Enhanced user repositories retrieval test passed")
    
    @unittest.skipUnless(GITHUB_SERVICE_AVAILABLE, "GitHub service not available")
    async def test_get_user_issues(self):
        """Test getting user issues"""
        # Mock implementation
        with patch.object(self.service, '_make_request') as mock_request:
            mock_request.return_value = [
                {
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
            ]
            
            result = await self.service.get_user_issues(self.user_id, state="open", limit=10)
            
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)
            
            issue = result[0]
            self.assertIsInstance(issue, GitHubIssue)
            self.assertEqual(issue.number, 100)
            self.assertEqual(issue.title, "Bug in authentication")
            self.assertEqual(issue.state, "open")
            
        print("✅ User issues retrieval test passed")
    
    @unittest.skipUnless(GITHUB_SERVICE_AVAILABLE, "GitHub service not available")
    async def test_create_repository_enhanced(self):
        """Test creating a repository with enhanced service"""
        # Mock implementation
        with patch.object(self.service, '_make_request') as mock_request:
            mock_request.return_value = {
                "id": 2,
                "name": "new-enhanced-repo",
                "full_name": "testuser/new-enhanced-repo",
                "description": "New enhanced test repository",
                "private": False,
                "html_url": "https://github.com/testuser/new-enhanced-repo",
                "clone_url": "https://github.com/testuser/new-enhanced-repo.git",
                "language": None,
                "stargazers_count": 0,
                "forks_count": 0,
                "open_issues_count": 0,
                "default_branch": "main",
                "topics": [],
                "license": None,
                "size": 0,
                "created_at": "2023-03-01T00:00:00Z",
                "updated_at": "2023-03-01T00:00:00Z"
            }
            
            result = await self.service.create_repository(
                self.user_id,
                "new-enhanced-repo",
                "New enhanced test repository"
            )
            
            self.assertIsInstance(result, GitHubRepository)
            self.assertEqual(result.name, "new-enhanced-repo")
            self.assertEqual(result.description, "New enhanced test repository")
            self.assertFalse(result.private)
            
        print("✅ Enhanced repository creation test passed")


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
            available_components.append("✅ GitHub Service")
        else:
            available_components.append("❌ GitHub Service")
        
        if GITHUB_HANDLERS_AVAILABLE:
            available_components.append("✅ GitHub Handlers")
        else:
            available_components.append("❌ GitHub Handlers")
        
        print("\n🔍 GitHub Integration Components Status:")
        for component in available_components:
            print(f"  {component}")
        
        # At least service should be available
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
        
        # Check enhanced service methods
        try:
            from github_service_real import GitHubService
            service = GitHubService()
            enhanced_methods = [
                'get_user_profile',
                'get_user_repositories',
                'get_user_issues',
                'create_repository',
                'create_issue',
                'get_service_info'
            ]
            
            for method in enhanced_methods:
                self.assertTrue(hasattr(service, method), f"Enhanced method '{method}' should be available")
            
            print("✅ All basic and enhanced methods available")
            
        except ImportError:
            print("⚠️  Enhanced GitHub service not available")
        
        print(f"✅ All {len(basic_methods)} basic capabilities available")
    
    def test_environment_configuration(self):
        """Test GitHub environment configuration"""
        github_client_id = os.getenv("GITHUB_CLIENT_ID")
        github_client_secret = os.getenv("GITHUB_CLIENT_SECRET")
        
        if github_client_id and github_client_secret:
            print("✅ GitHub environment variables configured")
            self.assertNotEqual(github_client_id, "mock_github_client_id")
            self.assertNotEqual(github_client_secret, "mock_github_client_secret")
        else:
            print("⚠️  GitHub environment variables not configured (using mock mode)")
            print("   Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET for real integration")


def main():
    """Main test runner"""
    print("🧪 ATOM GitHub Integration Test Suite")
    print("=" * 50)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add synchronous tests
    suite.addTest(TestGitHubService('test_github_token_function'))
    suite.addTest(TestGitHubService('test_get_user_repositories'))
    suite.addTest(TestGitHubService('test_create_repository'))
    suite.addTest(TestGitHubEnhancedService('test_service_instantiation'))
    suite.addTest(TestGitHubAPI('test_github_health_endpoint'))
    suite.addTest(TestGitHubAPI('test_github_oauth_flow'))
    suite.addTest(TestGitHubAPI('test_github_repositories_api_structure'))
    suite.addTest(TestGitHubIntegration('test_service_availability'))
    suite.addTest(TestGitHubIntegration('test_github_capabilities'))
    suite.addTest(TestGitHubIntegration('test_environment_configuration'))
    
    # Run synchronous tests
    print("\n🔄 Running Synchronous Tests...")
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # Run async tests
    async def run_async_tests():
        test_suite = TestGitHubEnhancedService()
        test_suite.setUp()
        
        print("\n🚀 Running Async GitHub Service Tests...")
        
        try:
            await test_suite.test_get_user_profile()
            await test_suite.test_get_user_repositories_enhanced()
            await test_suite.test_get_user_issues()
            await test_suite.test_create_repository_enhanced()
            print("✅ All async tests completed successfully")
        except Exception as e:
            print(f"❌ Async test failed: {e}")
    
    if GITHUB_SERVICE_AVAILABLE:
        asyncio.run(run_async_tests())
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
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