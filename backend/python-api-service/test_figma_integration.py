#!/usr/bin/env python3
"""
Test Suite for Figma Integration
Comprehensive testing of all Figma components
"""

import asyncio
import json
import pytest
import aiohttp
from datetime import datetime
from typing import Dict, Any

# Test configuration
TEST_BASE_URL = "http://localhost:8000"
TEST_USER_ID = "test_user_123"
TEST_TEAM_ID = "test_team_123"
TEST_FILE_KEY = "test_file_123"

class TestFigmaIntegration:
    """Test class for Figma integration"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.base_url = TEST_BASE_URL
        self.user_id = TEST_USER_ID
        self.team_id = TEST_TEAM_ID
        self.file_key = TEST_FILE_KEY
    
    async def make_request(self, endpoint: str, method: str = "GET", data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to API endpoint"""
        url = f"{self.base_url}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url) as response:
                    return await response.json()
            elif method == "POST":
                async with session.post(url, json=data) as response:
                    return await response.json()
    
    # Health Tests
    @pytest.mark.asyncio
    async def test_figma_health_check(self):
        """Test Figma health check"""
        response = await self.make_request("/api/figma/health")
        
        assert response.get("ok") is True
        assert response.get("status") in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in response
        assert isinstance(response.get("service_available", False), bool)
        
        print(f"✅ Figma health check: {response.get('status')}")
    
    @pytest.mark.asyncio
    async def test_figma_detailed_health_check(self):
        """Test Figma detailed health check"""
        response = await self.make_request(f"/api/figma/health/detailed?user_id={self.user_id}")
        
        assert response.get("ok") is True
        assert "checks" in response
        checks = response["checks"]
        
        # Check for required components
        expected_checks = ["service", "database", "environment"]
        for check in expected_checks:
            assert check in checks
            assert "ok" in checks[check]
        
        print(f"✅ Figma detailed health check: {len(checks)} components checked")
    
    # File Management Tests
    @pytest.mark.asyncio
    async def test_list_figma_files(self):
        """Test listing Figma files"""
        response = await self.make_request("/api/figma/files", "GET", {
            "user_id": self.user_id,
            "team_id": self.team_id,
            "limit": 10
        })
        
        assert response.get("ok") is True
        assert "files" in response
        assert isinstance(response["files"], list)
        
        if response["files"]:
            file = response["files"][0]
            required_fields = ["id", "name", "key", "thumbnail_url", "last_modified"]
            for field in required_fields:
                assert field in file
        
        print(f"✅ Listed {len(response['files'])} Figma files")
    
    @pytest.mark.asyncio
    async def test_list_enhanced_figma_files(self):
        """Test enhanced Figma files listing"""
        response = await self.make_request("/api/integrations/figma/files", "POST", {
            "user_id": self.user_id,
            "team_id": self.team_id,
            "include_archived": False,
            "file_type": "all",
            "sort_by": "last_modified",
            "sort_order": "desc",
            "limit": 20
        })
        
        assert response.get("ok") is True
        assert "data" in response
        assert "files" in response["data"]
        assert "total_count" in response["data"]
        
        print(f"✅ Enhanced files listing: {response['data']['total_count']} total")
    
    # Team Management Tests
    @pytest.mark.asyncio
    async def test_list_figma_teams(self):
        """Test listing Figma teams"""
        response = await self.make_request("/api/figma/teams", "GET", {
            "user_id": self.user_id,
            "limit": 10
        })
        
        assert response.get("ok") is True
        assert "teams" in response
        assert isinstance(response["teams"], list)
        
        if response["teams"]:
            team = response["teams"][0]
            required_fields = ["id", "name", "members_count"]
            for field in required_fields:
                assert field in team
        
        print(f"✅ Listed {len(response['teams'])} Figma teams")
    
    @pytest.mark.asyncio
    async def test_list_enhanced_figma_teams(self):
        """Test enhanced Figma teams listing"""
        response = await self.make_request("/api/integrations/figma/teams", "POST", {
            "user_id": self.user_id,
            "include_members": True,
            "include_projects": True,
            "include_member_roles": True,
            "limit": 20
        })
        
        assert response.get("ok") is True
        assert "data" in response
        assert "teams" in response["data"]
        
        print(f"✅ Enhanced teams listing: {response['data']['total_count']} total")
    
    # Project Management Tests
    @pytest.mark.asyncio
    async def test_list_figma_projects(self):
        """Test listing Figma projects"""
        response = await self.make_request("/api/figma/projects", "GET", {
            "user_id": self.user_id,
            "team_id": self.team_id,
            "limit": 10
        })
        
        assert response.get("ok") is True
        assert "projects" in response
        assert isinstance(response["projects"], list)
        
        if response["projects"]:
            project = response["projects"][0]
            required_fields = ["id", "name", "team_id", "team_name"]
            for field in required_fields:
                assert field in project
        
        print(f"✅ Listed {len(response['projects'])} Figma projects")
    
    @pytest.mark.asyncio
    async def test_list_enhanced_figma_projects(self):
        """Test enhanced Figma projects listing"""
        response = await self.make_request("/api/integrations/figma/projects", "POST", {
            "user_id": self.user_id,
            "team_id": self.team_id,
            "include_file_counts": True,
            "include_thumbnails": True,
            "sort_by": "name",
            "sort_order": "asc",
            "limit": 20
        })
        
        assert response.get("ok") is True
        assert "data" in response
        assert "projects" in response["data"]
        
        print(f"✅ Enhanced projects listing: {response['data']['total_count']} total")
    
    # Component Management Tests
    @pytest.mark.asyncio
    async def test_list_figma_components(self):
        """Test listing Figma components"""
        response = await self.make_request("/api/figma/components", "GET", {
            "user_id": self.user_id,
            "file_key": self.file_key,
            "limit": 20
        })
        
        assert response.get("ok") is True
        assert "components" in response
        assert isinstance(response["components"], list)
        
        if response["components"]:
            component = response["components"][0]
            required_fields = ["id", "name", "component_key", "file_key", "node_id"]
            for field in required_fields:
                assert field in component
        
        print(f"✅ Listed {len(response['components'])} Figma components")
    
    @pytest.mark.asyncio
    async def test_list_enhanced_figma_components(self):
        """Test enhanced Figma components listing"""
        response = await self.make_request("/api/integrations/figma/components", "POST", {
            "user_id": self.user_id,
            "file_key": self.file_key,
            "include_variants": True,
            "include_metadata": True,
            "component_type": "all",
            "sort_by": "name",
            "sort_order": "asc",
            "limit": 50
        })
        
        assert response.get("ok") is True
        assert "data" in response
        assert "components" in response["data"]
        
        print(f"✅ Enhanced components listing: {response['data']['total_count']} total")
    
    # User Profile Tests
    @pytest.mark.asyncio
    async def test_get_figma_user_profile(self):
        """Test getting Figma user profile"""
        response = await self.make_request("/api/figma/users/profile", "GET", {
            "user_id": self.user_id
        })
        
        assert response.get("ok") is True
        assert "user" in response
        
        user = response["user"]
        required_fields = ["id", "name", "email", "role"]
        for field in required_fields:
            assert field in user
        
        print(f"✅ Retrieved user profile: {user['name']}")
    
    @pytest.mark.asyncio
    async def test_get_enhanced_figma_user_profile(self):
        """Test getting enhanced Figma user profile"""
        response = await self.make_request("/api/integrations/figma/user/profile", "POST", {
            "user_id": self.user_id,
            "include_team_details": True,
            "include_usage_stats": True,
            "include_permissions": True
        })
        
        assert response.get("ok") is True
        assert "data" in response
        assert "user" in response["data"]
        
        data = response["data"]
        if "services" in data:
            assert isinstance(data["services"], dict)
        
        print(f"✅ Enhanced user profile retrieved with services")
    
    # Search Tests
    @pytest.mark.asyncio
    async def test_search_figma(self):
        """Test Figma search functionality"""
        search_query = "design"
        response = await self.make_request("/api/figma/search", "POST", {
            "user_id": self.user_id,
            "query": search_query,
            "search_type": "global",
            "limit": 20
        })
        
        assert response.get("ok") is True
        assert "results" in response
        assert "query" in response
        assert response["query"] == search_query
        assert isinstance(response["results"], list)
        
        print(f"✅ Search results: {len(response['results'])} items for '{search_query}'")
    
    @pytest.mark.asyncio
    async def test_enhanced_search_figma(self):
        """Test enhanced Figma search functionality"""
        search_query = "button"
        response = await self.make_request("/api/integrations/figma/search", "POST", {
            "user_id": self.user_id,
            "query": search_query,
            "search_type": "all",
            "file_types": ["figma", "figjam"],
            "include_thumbnails": True,
            "limit": 30
        })
        
        assert response.get("ok") is True
        assert "data" in response
        assert "results" in response["data"]
        
        print(f"✅ Enhanced search: {response['data']['total_count']} items for '{search_query}'")
    
    # OAuth Tests
    @pytest.mark.asyncio
    async def test_figma_oauth_url(self):
        """Test Figma OAuth URL generation"""
        response = await self.make_request("/api/oauth/figma/url", "GET", {
            "user_id": self.user_id
        })
        
        assert response.get("success") is True
        assert "oauth_url" in response
        assert "state" in response
        assert "scopes" in response
        
        oauth_url = response["oauth_url"]
        assert "figma.com/oauth" in oauth_url
        
        print(f"✅ OAuth URL generated: {oauth_url[:50]}...")
    
    @pytest.mark.asyncio
    async def test_figma_oauth_callback(self):
        """Test Figma OAuth callback"""
        mock_code = "mock_authorization_code"
        mock_state = "mock_state_123"
        
        response = await self.make_request("/api/oauth/figma/callback", "POST", {
            "code": mock_code,
            "state": mock_state
        })
        
        assert response.get("success") is True
        assert "user_info" in response
        assert "tokens" in response
        assert "service" in response
        assert response["service"] == "figma"
        
        print(f"✅ OAuth callback processed successfully")
    
    # Comment Tests
    @pytest.mark.asyncio
    async def test_add_figma_comment(self):
        """Test adding comment to Figma file"""
        response = await self.make_request("/api/figma/comments", "POST", {
            "user_id": self.user_id,
            "file_key": self.file_key,
            "comment": "Test comment from integration",
            "position": {"x": 100, "y": 200}
        })
        
        assert response.get("ok") is True
        assert "comment" in response
        
        comment = response["comment"]
        assert "id" in comment
        assert "file_key" in comment
        assert "message" in comment
        assert comment["message"] == "Test comment from integration"
        
        print(f"✅ Comment added: {comment['id']}")
    
    # Version Tests
    @pytest.mark.asyncio
    async def test_get_figma_file_versions(self):
        """Test getting Figma file versions"""
        response = await self.make_request("/api/figma/versions", "GET", {
            "user_id": self.user_id,
            "file_key": self.file_key,
            "limit": 10
        })
        
        assert response.get("ok") is True
        assert "versions" in response
        assert isinstance(response["versions"], list)
        
        if response["versions"]:
            version = response["versions"][0]
            required_fields = ["id", "label", "created_at"]
            for field in required_fields:
                assert field in version
        
        print(f"✅ File versions: {len(response['versions'])} versions found")
    
    # Export Tests
    @pytest.mark.asyncio
    async def test_export_figma_file(self):
        """Test exporting Figma file"""
        response = await self.make_request("/api/figma/export", "POST", {
            "user_id": self.user_id,
            "file_key": self.file_key,
            "format": "png"
        })
        
        assert response.get("ok") is True
        assert "export_url" in response
        assert "format" in response
        assert response["format"] == "png"
        
        print(f"✅ File export URL: {response['export_url']}")
    
    # Styles Tests
    @pytest.mark.asyncio
    async def test_get_figma_styles(self):
        """Test getting Figma styles"""
        response = await self.make_request("/api/figma/styles", "GET", {
            "user_id": self.user_id,
            "file_key": self.file_key,
            "limit": 20
        })
        
        assert response.get("ok") is True
        assert "styles" in response
        assert isinstance(response["styles"], list)
        
        print(f"✅ Styles found: {len(response['styles'])} styles")
    
    # Integration Tests
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow"""
        print("🚀 Starting end-to-end Figma workflow test...")
        
        # 1. Check health
        health_response = await self.make_request("/api/figma/health")
        assert health_response.get("ok") is True
        print("✅ Health check passed")
        
        # 2. Get user profile
        profile_response = await self.make_request("/api/figma/users/profile", "GET", {
            "user_id": self.user_id
        })
        assert profile_response.get("ok") is True
        print(f"✅ User profile: {profile_response['user']['name']}")
        
        # 3. List teams
        teams_response = await self.make_request("/api/figma/teams", "GET", {
            "user_id": self.user_id,
            "limit": 5
        })
        assert teams_response.get("ok") is True
        print(f"✅ Teams listed: {len(teams_response['teams'])} teams")
        
        # 4. List files
        files_response = await self.make_request("/api/figma/files", "GET", {
            "user_id": self.user_id,
            "limit": 10
        })
        assert files_response.get("ok") is True
        print(f"✅ Files listed: {len(files_response['files'])} files")
        
        # 5. Search
        search_response = await self.make_request("/api/figma/search", "POST", {
            "user_id": self.user_id,
            "query": "test",
            "limit": 5
        })
        assert search_response.get("ok") is True
        print(f"✅ Search completed: {len(search_response['results'])} results")
        
        print("🎉 End-to-end workflow test completed successfully!")


# Test runner
async def run_tests():
    """Run all Figma integration tests"""
    test_instance = TestFigmaIntegration()
    
    tests = [
        test_instance.test_figma_health_check,
        test_instance.test_figma_detailed_health_check,
        test_instance.test_list_figma_files,
        test_instance.test_list_enhanced_figma_files,
        test_instance.test_list_figma_teams,
        test_instance.test_list_enhanced_figma_teams,
        test_instance.test_list_figma_projects,
        test_instance.test_list_enhanced_figma_projects,
        test_instance.test_list_figma_components,
        test_instance.test_list_enhanced_figma_components,
        test_instance.test_get_figma_user_profile,
        test_instance.test_get_enhanced_figma_user_profile,
        test_instance.test_search_figma,
        test_instance.test_enhanced_search_figma,
        test_instance.test_figma_oauth_url,
        test_instance.test_figma_oauth_callback,
        test_instance.test_add_figma_comment,
        test_instance.test_get_figma_file_versions,
        test_instance.test_export_figma_file,
        test_instance.test_get_figma_styles,
        test_instance.test_end_to_end_workflow,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"❌ Test failed: {test.__name__} - {str(e)}")
            failed += 1
    
    print(f"\n📊 Test Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")


if __name__ == "__main__":
    print("🧪 Running Figma Integration Test Suite...")
    print("=" * 60)
    asyncio.run(run_tests())