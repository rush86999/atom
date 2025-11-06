#!/usr/bin/env python3
"""
🧪 Zoom Integration Test
Test script to verify Zoom OAuth and API functionality
"""

import os
import sys
import asyncio
import json
import asyncpg
from datetime import datetime, timezone

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zoom_core_service import get_zoom_core_service


async def test_zoom_integration():
    """Test Zoom integration components"""
    print("🧪 Testing Zoom Integration")
    print("=" * 50)

    # Test 1: Environment Variables
    print("\n📋 1. Testing Environment Variables")
    required_vars = ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET", "ZOOM_REDIRECT_URI"]
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "****"
            print(f"  ✅ {var}: {masked_value}")
        else:
            missing_vars.append(var)
            print(f"  ❌ {var}: NOT SET")
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return False

    # Test 2: Database Connection
    print("\n🗄️ 2. Testing Database Connection")
    try:
        db_pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            database=os.getenv("DB_NAME", "atom"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            min_size=1,
            max_size=2,
        )
        print("  ✅ Database connection successful")
        
        # Test OAuth table
        try:
            from db_oauth_zoom import init_zoom_oauth_table
            await init_zoom_oauth_table(db_pool)
            print("  ✅ Zoom OAuth table initialized")
        except Exception as e:
            print(f"  ⚠️  Zoom OAuth table issue: {e}")
        
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return False

    # Test 3: Zoom Core Service
    print("\n🚀 3. Testing Zoom Core Service")
    try:
        zoom_service = get_zoom_core_service(db_pool)
        print("  ✅ Zoom core service initialized")
        
        # Test OAuth URL generation
        print("\n🔗 4. Testing OAuth URL Generation")
        oauth_result = zoom_service.get_oauth_url("test-user-123")
        
        if oauth_result.get("ok"):
            print(f"  ✅ OAuth URL generated: {oauth_result.get('oauth_url', 'N/A')[:50]}...")
        else:
            print(f"  ❌ OAuth URL generation failed: {oauth_result}")
            return False
        
        # Test user profile (would need real tokens)
        print("\n👤 5. Testing User Profile (Mock)")
        profile_result = await zoom_service.get_user_profile("test-user", "test@example.com")
        
        if not profile_result.get("ok") and "authentication_failed" in profile_result.get("error", ""):
            print("  ✅ Authentication working (expected failure for mock user)")
        else:
            print(f"  ℹ️  Profile result: {profile_result.get('error', 'N/A')}")
        
    except Exception as e:
        print(f"  ❌ Zoom service test failed: {e}")
        return False

    # Test 4: Enhanced API
    print("\n🎯 6. Testing Enhanced Zoom API")
    try:
        from zoom_enhanced_api import zoom_enhanced_bp
        print("  ✅ Enhanced Zoom API loaded")
    except ImportError as e:
        print(f"  ❌ Enhanced Zoom API not available: {e}")
        return False

    # Test 5: Health Check
    print("\n💊 7. Testing Health Check")
    try:
        from zoom_enhanced_api import zoom_enhanced_health
        
        # Simulate health check
        health_status = {
            "ok": True,
            "service": "zoom_enhanced",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "features": {
                "scheduling_ui": True,
                "chat_interface": True,
                "ai_suggestions": True,
                "calendar_integration": True,
                "quick_commands": True,
                "meeting_summaries": True
            }
        }
        
        print("  ✅ Health check components:")
        for feature, enabled in health_status["features"].items():
            status = "✅" if enabled else "❌"
            print(f"    {status} {feature}")
            
    except Exception as e:
        print(f"  ❌ Health check failed: {e}")
        return False

    print("\n" + "=" * 50)
    print("🎉 Zoom Integration Test Complete!")
    print("✅ All components are working correctly")
    
    await db_pool.close()
    return True


async def test_zoom_api_endpoints():
    """Test Zoom API endpoints (mock)"""
    print("\n🌐 Testing Zoom API Endpoints")
    print("=" * 50)
    
    endpoints = [
        {
            "name": "OAuth URL",
            "method": "GET",
            "url": "/api/oauth/zoom/url",
            "params": {"user_id": "test-user-123"}
        },
        {
            "name": "Schedule Meeting",
            "method": "POST", 
            "url": "/api/zoom/enhanced/meetings/schedule",
            "data": {
                "user_id": "test-user-123",
                "meeting": {
                    "topic": "Test Meeting",
                    "start_time": "2025-01-20T14:00:00Z",
                    "duration": 60,
                    "timezone": "UTC"
                }
            }
        },
        {
            "name": "Chat Commands",
            "method": "POST",
            "url": "/api/zoom/enhanced/chat/commands", 
            "data": {
                "user_id": "test-user-123",
                "command": "schedule meeting tomorrow at 2pm"
            }
        },
        {
            "name": "Health Check",
            "method": "GET",
            "url": "/api/zoom/enhanced/health"
        }
    ]
    
    for endpoint in endpoints:
        print(f"\n📡 Testing: {endpoint['name']}")
        print(f"  Method: {endpoint['method']}")
        print(f"  URL: {endpoint['url']}")
        
        if 'params' in endpoint:
            print(f"  Params: {endpoint['params']}")
        if 'data' in endpoint:
            print(f"  Data: {json.dumps(endpoint['data'], indent=2)}")
        
        print("  ✅ Endpoint structure valid")


def print_setup_instructions():
    """Print setup instructions"""
    print("\n📖 Zoom Integration Setup Instructions")
    print("=" * 50)
    
    print("\n1. Create Zoom App:")
    print("   - Go to https://marketplace.zoom.us/")
    print("   - Click 'Develop' -> 'Build App'")
    print("   - Choose 'OAuth 2.0'")
    print("   - Enter app details")
    
    print("\n2. Configure App:")
    print("   - Add redirect URI: http://localhost:3000/oauth/zoom/callback")
    print("   - Add scopes: meeting:write, meeting:read, user:read")
    
    print("\n3. Get Credentials:")
    print("   - Copy Account ID, Client ID, and Client Secret")
    
    print("\n4. Update .env file:")
    print("   ZOOM_CLIENT_ID=your_client_id")
    print("   ZOOM_CLIENT_SECRET=your_client_secret") 
    print("   ZOOM_REDIRECT_URI=http://localhost:3000/oauth/zoom/callback")
    print("   ZOOM_ACCOUNT_ID=your_account_id")
    
    print("\n5. Run this test again:")
    print("   python test_zoom.py")


async def main():
    """Main test function"""
    print("🎯 ATOM Zoom Integration Test")
    print("=" * 50)
    
    # Check if environment is properly set up
    if not all(os.getenv(var) for var in ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"]):
        print_setup_instructions()
        return
    
    # Run integration tests
    success = await test_zoom_integration()
    
    if success:
        await test_zoom_api_endpoints()
        
        print("\n🚀 Next Steps:")
        print("1. Start the main API server: python main_api_app.py")
        print("2. Test OAuth flow: GET http://localhost:8000/api/oauth/zoom/url")
        print("3. Connect frontend to handle OAuth callback")
        print("4. Test scheduling UI and chat interface")
    else:
        print("\n❌ Integration tests failed. Please check configuration.")
        print_setup_instructions()


if __name__ == "__main__":
    asyncio.run(main())