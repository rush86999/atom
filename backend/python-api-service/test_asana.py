#!/usr/bin/env python3
"""
🧪 Asana Integration Test
Test script to verify Asana OAuth and API functionality
"""

import os
import sys
import asyncio
import json
import requests
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_asana_endpoints():
    """Test Asana API endpoints"""
    print("🧪 Testing Asana Integration")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    test_results = []
    
    # Test endpoints
    endpoints = [
        {
            "name": "Health Check",
            "method": "GET",
            "url": "/api/asana/health",
            "expected_status": 200
        },
        {
            "name": "List Projects (GET)",
            "method": "GET", 
            "url": "/projects?user_id=test-user-123",
            "expected_status": 200
        },
        {
            "name": "List Teams (GET)",
            "method": "GET",
            "url": "/teams?user_id=test-user-123&workspace_gid=workspace-123", 
            "expected_status": 200
        },
        {
            "name": "List Users (GET)",
            "method": "GET",
            "url": "/users?user_id=test-user-123&workspace_gid=workspace-123",
            "expected_status": 200
        },
        {
            "name": "List Projects (POST)",
            "method": "POST",
            "url": "/api/asana/projects",
            "data": {"user_id": "test-user-123", "workspace_id": "workspace-123"},
            "expected_status": 200
        },
        {
            "name": "List Teams (POST)",
            "method": "POST", 
            "url": "/api/asana/teams",
            "data": {"user_id": "test-user-123", "workspace_id": "workspace-123"},
            "expected_status": 200
        },
        {
            "name": "List Users (POST)",
            "method": "POST",
            "url": "/api/asana/users", 
            "data": {"user_id": "test-user-123", "workspace_id": "workspace-123"},
            "expected_status": 200
        },
        {
            "name": "Get Sections",
            "method": "POST",
            "url": "/api/asana/sections",
            "data": {"user_id": "test-user-123", "project_id": "project-123"},
            "expected_status": 200
        },
        {
            "name": "User Profile",
            "method": "POST",
            "url": "/api/asana/user-profile", 
            "data": {"user_id": "test-user-123"},
            "expected_status": 200
        },
        {
            "name": "Create Task",
            "method": "POST",
            "url": "/api/asana/create-task",
            "data": {
                "user_id": "test-user-123",
                "project_id": "project-123", 
                "name": "Test Task"
            },
            "expected_status": 200
        },
        {
            "name": "Enhanced Tasks",
            "method": "POST",
            "url": "/api/integrations/asana/tasks",
            "data": {
                "user_id": "test-user-123",
                "operation": "list"
            },
            "expected_status": 200
        },
        {
            "name": "Enhanced Projects", 
            "method": "POST",
            "url": "/api/integrations/asana/projects",
            "data": {
                "user_id": "test-user-123",
                "operation": "list"
            },
            "expected_status": 200
        },
        {
            "name": "Enhanced Teams",
            "method": "POST", 
            "url": "/api/integrations/asana/teams",
            "data": {
                "user_id": "test-user-123"
            },
            "expected_status": 200
        },
        {
            "name": "Enhanced Search",
            "method": "POST",
            "url": "/api/integrations/asana/search", 
            "data": {
                "user_id": "test-user-123",
                "query": "test"
            },
            "expected_status": 200
        },
        {
            "name": "Enhanced User Profile",
            "method": "POST",
            "url": "/api/integrations/asana/user/profile",
            "data": {"user_id": "test-user-123"},
            "expected_status": 200
        },
        {
            "name": "Enhanced Health",
            "method": "GET", 
            "url": "/api/integrations/asana/health",
            "expected_status": 200
        }
    ]
    
    print(f"\n📡 Testing {len(endpoints)} endpoints...")
    
    for i, endpoint in enumerate(endpoints, 1):
        print(f"\n{i:2d}. Testing: {endpoint['name']}")
        print(f"    Method: {endpoint['method']}")
        print(f"    URL: {endpoint['url']}")
        
        try:
            # Make request
            full_url = base_url + endpoint['url']
            
            if endpoint['method'] == 'GET':
                response = requests.get(full_url, timeout=10)
            else:
                data = endpoint.get('data', {})
                response = requests.post(full_url, json=data, timeout=10)
            
            status_ok = response.status_code == endpoint['expected_status']
            
            if status_ok:
                print(f"    ✅ Status: {response.status_code}")
                test_results.append({"endpoint": endpoint['name'], "status": "PASS"})
            else:
                print(f"    ❌ Status: {response.status_code} (expected {endpoint['expected_status']})")
                print(f"    Response: {response.text[:200]}...")
                test_results.append({"endpoint": endpoint['name'], "status": "FAIL"})
                
        except requests.exceptions.ConnectionError:
            print(f"    ❌ Connection failed - API server not running")
            test_results.append({"endpoint": endpoint['name'], "status": "FAIL"})
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
            test_results.append({"endpoint": endpoint['name'], "status": "FAIL"})
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = len([r for r in test_results if r['status'] == 'PASS'])
    failed = len([r for r in test_results if r['status'] == 'FAIL'])
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    print(f"\n📋 Detailed Results:")
    for result in test_results:
        status_icon = "✅" if result['status'] == 'PASS' else "❌"
        print(f"  {status_icon} {result['endpoint']}")
    
    if failed == 0:
        print(f"\n🎉 All tests passed! Asana integration is 100% ready!")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check the detailed results above.")
        return False


def test_environment_setup():
    """Test environment configuration"""
    print("\n🔧 Testing Environment Setup")
    print("=" * 30)
    
    required_vars = [
        "ASANA_CLIENT_ID", 
        "ASANA_CLIENT_SECRET",
        "ASANA_REDIRECT_URI"
    ]
    
    optional_vars = [
        "ASANA_ACCESS_TOKEN",
        "ASANA_WORKSPACE_ID"
    ]
    
    all_good = True
    
    print("\n📋 Required Environment Variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "****"
            print(f"  ✅ {var}: {masked}")
        else:
            print(f"  ❌ {var}: NOT SET")
            all_good = False
    
    print("\n📋 Optional Environment Variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            masked = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "****"
            print(f"  ✅ {var}: {masked}")
        else:
            print(f"  ⚠️  {var}: Not set (optional)")
    
    return all_good


def print_setup_instructions():
    """Print setup instructions"""
    print("\n📖 Asana Integration Setup Instructions")
    print("=" * 50)
    
    print("\n1. Create Asana App:")
    print("   - Go to https://app.asana.com/-/developer_console")
    print("   - Click 'Create New App'")
    print("   - Choose 'OAuth App'")
    print("   - Enter app details")
    
    print("\n2. Configure App:")
    print("   - Add redirect URI: http://localhost:3000/oauth/asana/callback")
    print("   - Add scopes: default, tasks:read, tasks:write, projects:read, projects:write")
    
    print("\n3. Get Credentials:")
    print("   - Copy Client ID and Client Secret")
    
    print("\n4. Update .env file:")
    print("   ASANA_CLIENT_ID=your_client_id")
    print("   ASANA_CLIENT_SECRET=your_client_secret")
    print("   ASANA_REDIRECT_URI=http://localhost:3000/oauth/asana/callback")
    
    print("\n5. Run this test again:")
    print("   python test_asana.py")


def main():
    """Main test function"""
    print("🎯 ATOM Asana Integration Test")
    print("=" * 50)
    
    # Test environment setup
    env_good = test_environment_setup()
    
    if not env_good:
        print("\n⚠️  Environment setup incomplete.")
        print_setup_instructions()
        return
    
    # Test API endpoints
    print(f"\n🚀 Starting API endpoint tests...")
    print("Note: Make sure the API server is running: python main_api_app.py")
    
    success = test_asana_endpoints()
    
    if success:
        print("\n🚀 Next Steps:")
        print("1. ✅ Asana integration is ready for production!")
        print("2. Test OAuth flow in your frontend application")
        print("3. Connect to real Asana workspace")
        print("4. Test with real user data")
    else:
        print("\n🔧 Troubleshooting:")
        print("1. Make sure API server is running: python main_api_app.py")
        print("2. Check environment variables")
        print("3. Verify blueprint registration in main_api_app.py")
        print("4. Check for import errors in logs")


if __name__ == "__main__":
    main()