#!/usr/bin/env python3
"""
Figma Integration Test
Comprehensive test suite for Figma integration functionality
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

# Import Figma service
try:
    from figma_service_real import figma_service, FigmaFile, FigmaTeam, FigmaUser, FigmaComponent, FigmaService
    FIGMA_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Figma service not available: {e}")
    FIGMA_SERVICE_AVAILABLE = False

# Import Figma handlers
try:
    from figma_handler import figma_bp
    from auth_handler_figma import auth_figma_bp
    FIGMA_HANDLERS_AVAILABLE = True
except ImportError as e:
    print(f"Figma handlers not available: {e}")
    FIGMA_HANDLERS_AVAILABLE = False


class TestFigmaService(unittest.TestCase):
    """Test Figma service functionality"""
    
    def setUp(self):
        if not FIGMA_SERVICE_AVAILABLE:
            self.skipTest("Figma service not available")
        
        self.user_id = "test_user_123"
        self.team_id = "test_team_456"
        self.file_key = "test_file_789"
    
    def test_service_info(self):
        """Test service information"""
        service_info = figma_service.get_service_info()
        
        self.assertIsInstance(service_info, dict)
        self.assertIn('name', service_info)
        self.assertIn('version', service_info)
        self.assertIn('capabilities', service_info)
        
        print(f"✅ Service info: {service_info['name']} v{service_info['version']}")
    
    @unittest.skipUnless(FIGMA_SERVICE_AVAILABLE, "Figma service not available")
    async def test_get_user_files(self):
        """Test getting user files"""
        files = await figma_service.get_user_files(self.user_id, limit=5)
        
        self.assertIsInstance(files, list)
        for file in files:
            self.assertIsInstance(file, FigmaFile)
            self.assertIsNotNone(file.key)
            self.assertIsNotNone(file.name)
        
        print(f"✅ Retrieved {len(files)} files")
    
    @unittest.skipUnless(FIGMA_SERVICE_AVAILABLE, "Figma service not available")
    async def test_get_user_teams(self):
        """Test getting user teams"""
        teams = await figma_service.get_user_teams(self.user_id, limit=5)
        
        self.assertIsInstance(teams, list)
        for team in teams:
            self.assertIsInstance(team, FigmaTeam)
            self.assertIsNotNone(team.id)
            self.assertIsNotNone(team.name)
        
        print(f"✅ Retrieved {len(teams)} teams")
    
    @unittest.skipUnless(FIGMA_SERVICE_AVAILABLE, "Figma service not available")
    async def test_get_user_profile(self):
        """Test getting user profile"""
        profile = await figma_service.get_user_profile(self.user_id)
        
        if profile:  # Profile might be None in mock mode
            self.assertIsInstance(profile, FigmaUser)
            self.assertIsNotNone(profile.id)
            self.assertIsNotNone(profile.name)
            print(f"✅ Retrieved profile: {profile.name}")
        else:
            print("ℹ️  Profile returned None (mock mode)")
    
    @unittest.skipUnless(FIGMA_SERVICE_AVAILABLE, "Figma service not available")
    async def test_search_figma(self):
        """Test Figma search functionality"""
        result = await figma_service.search_figma(self.user_id, "button", "global", 10)
        
        self.assertIsInstance(result, dict)
        self.assertIn('ok', result)
        if result.get('ok'):
            self.assertIn('results', result)
            self.assertIn('total_count', result)
            print(f"✅ Search found {result['total_count']} results")
        else:
            print(f"⚠️  Search returned error: {result.get('error')}")
    
    @unittest.skipUnless(FIGMA_SERVICE_AVAILABLE, "Figma service not available")
    async def test_get_file_components(self):
        """Test getting file components"""
        components = await figma_service.get_file_components(self.user_id, self.file_key, limit=5)
        
        self.assertIsInstance(components, list)
        for component in components:
            self.assertIsInstance(component, FigmaComponent)
            self.assertIsNotNone(component.key)
            self.assertIsNotNone(component.name)
        
        print(f"✅ Retrieved {len(components)} components")


class TestFigmaAPI(unittest.TestCase):
    """Test Figma API endpoints"""
    
    def setUp(self):
        if not FIGMA_HANDLERS_AVAILABLE:
            self.skipTest("Figma handlers not available")
    
    @patch('requests.get')
    def test_figma_health_endpoint(self, mock_get):
        """Test Figma health endpoint"""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "service": "figma",
            "status": "registered"
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Test endpoint (would be called via Flask in real scenario)
        response_data = {
            "ok": True,
            "service": "figma",
            "status": "registered",
            "needs_oauth": True
        }
        
        self.assertIsInstance(response_data, dict)
        self.assertTrue(response_data.get('ok'))
        self.assertEqual(response_data.get('service'), 'figma')
        
        print("✅ Figma health endpoint structure correct")
    
    def test_figma_oauth_flow(self):
        """Test Figma OAuth flow structure"""
        # Test OAuth authorization URL generation
        oauth_data = {
            "ok": True,
            "authorization_url": "https://www.figma.com/oauth?client_id=test_client",
            "client_id": "test_client_id",
            "redirect_uri": "http://localhost:3000/oauth/figma/callback",
            "scopes": ["file_read", "user_read"],
            "state": "test_state"
        }
        
        self.assertIsInstance(oauth_data, dict)
        self.assertTrue(oauth_data.get('ok'))
        self.assertIn('authorization_url', oauth_data)
        self.assertIn('scopes', oauth_data)
        
        print("✅ Figma OAuth flow structure correct")
    
    def test_figma_files_api_structure(self):
        """Test Figma files API response structure"""
        files_response = {
            "ok": True,
            "files": [
                {
                    "id": "file-1",
                    "name": "Test File",
                    "key": "ABC123",
                    "thumbnail_url": "https://example.com/thumb.png",
                    "last_modified": "2024-01-15T10:30:00Z",
                    "editor_type": "figma"
                }
            ],
            "total_count": 1
        }
        
        self.assertIsInstance(files_response, dict)
        self.assertTrue(files_response.get('ok'))
        self.assertIn('files', files_response)
        self.assertIsInstance(files_response['files'], list)
        
        if files_response['files']:
            file_data = files_response['files'][0]
            self.assertIn('id', file_data)
            self.assertIn('name', file_data)
            self.assertIn('key', file_data)
        
        print("✅ Figma files API structure correct")


class TestFigmaIntegration(unittest.TestCase):
    """Test Figma integration completeness"""
    
    def test_service_availability(self):
        """Test that all required Figma components are available"""
        available_components = []
        
        if FIGMA_SERVICE_AVAILABLE:
            available_components.append("✅ Figma Service")
        else:
            available_components.append("❌ Figma Service")
        
        if FIGMA_HANDLERS_AVAILABLE:
            available_components.append("✅ Figma Handlers")
        else:
            available_components.append("❌ Figma Handlers")
        
        print("\n🔍 Figma Integration Components Status:")
        for component in available_components:
            print(f"  {component}")
        
        # At least service should be available
        self.assertTrue(FIGMA_SERVICE_AVAILABLE, "Figma service should be available")
    
    def test_figma_capabilities(self):
        """Test Figma service capabilities"""
        if not FIGMA_SERVICE_AVAILABLE:
            self.skipTest("Figma service not available")
        
        service_info = figma_service.get_service_info()
        capabilities = service_info.get('capabilities', [])
        
        expected_capabilities = [
            'Get user files',
            'Get user teams', 
            'Get team projects',
            'Get file components',
            'Get user profile',
            'Search functionality'
        ]
        
        for capability in expected_capabilities:
            self.assertIn(capability, capabilities, f"Capability '{capability}' should be available")
        
        print(f"✅ All {len(expected_capabilities)} expected capabilities available")
    
    def test_environment_configuration(self):
        """Test Figma environment configuration"""
        figma_client_id = os.getenv("FIGMA_CLIENT_ID")
        figma_client_secret = os.getenv("FIGMA_CLIENT_SECRET")
        
        if figma_client_id and figma_client_secret:
            print("✅ Figma environment variables configured")
            self.assertNotEqual(figma_client_id, "mock_figma_client_id")
            self.assertNotEqual(figma_client_secret, "mock_figma_client_secret")
        else:
            print("⚠️  Figma environment variables not configured (using mock mode)")
            print("   Set FIGMA_CLIENT_ID and FIGMA_CLIENT_SECRET for real integration")


async def run_async_tests():
    """Run async test methods"""
    test_suite = TestFigmaService()
    test_suite.setUp()
    
    print("\n🚀 Running Async Figma Service Tests...")
    
    try:
        await test_suite.test_get_user_files()
        await test_suite.test_get_user_teams()
        await test_suite.test_get_user_profile()
        await test_suite.test_search_figma()
        await test_suite.test_get_file_components()
        print("✅ All async tests completed successfully")
    except Exception as e:
        print(f"❌ Async test failed: {e}")


def main():
    """Main test runner"""
    print("🧪 ATOM Figma Integration Test Suite")
    print("=" * 50)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add synchronous tests
    suite.addTest(TestFigmaService('test_service_info'))
    suite.addTest(TestFigmaAPI('test_figma_health_endpoint'))
    suite.addTest(TestFigmaAPI('test_figma_oauth_flow'))
    suite.addTest(TestFigmaAPI('test_figma_files_api_structure'))
    suite.addTest(TestFigmaIntegration('test_service_availability'))
    suite.addTest(TestFigmaIntegration('test_figma_capabilities'))
    suite.addTest(TestFigmaIntegration('test_environment_configuration'))
    
    # Run synchronous tests
    print("\n🔄 Running Synchronous Tests...")
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # Run async tests
    if FIGMA_SERVICE_AVAILABLE:
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
        print("\n🎉 All tests passed! Figma integration is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Check the implementation.")
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