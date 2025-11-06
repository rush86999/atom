#!/usr/bin/env python3
"""
Test script for Enhanced Google Services
"""

import sys
import os
import asyncio
import requests
import json
from datetime import datetime, timezone, timedelta

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_gmail_enhanced_api():
    """Test Enhanced Gmail API endpoints"""
    print("🧪 Testing Enhanced Gmail API...")
    
    base_url = "http://localhost:8000"
    test_user_id = "test_user_123"
    
    try:
        # Test health endpoint
        print("\n📊 Testing Gmail health endpoint...")
        response = requests.post(
            f"{base_url}/api/gmail/enhanced/health",
            json={"user_id": test_user_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Gmail API health check: {result.get('ok', False)}")
        else:
            print(f"❌ Gmail health endpoint failed: {response.status_code}")
            
        # Test messages list endpoint
        print("\n📧 Testing Gmail messages list endpoint...")
        response = requests.post(
            f"{base_url}/api/gmail/enhanced/messages/list",
            json={
                "user_id": test_user_id,
                "max_results": 5,
                "query": "is:unread"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Gmail messages list response: {result.get('ok', False)}")
        else:
            print(f"⚠️ Gmail messages list: {response.status_code} (Expected if no OAuth token)")
            
    except Exception as e:
        print(f"❌ Gmail API test error: {e}")

async def test_calendar_enhanced_api():
    """Test Enhanced Calendar API endpoints"""
    print("\n🧪 Testing Enhanced Calendar API...")
    
    base_url = "http://localhost:8000"
    test_user_id = "test_user_123"
    
    try:
        # Test health endpoint
        print("\n📅 Testing Calendar health endpoint...")
        response = requests.post(
            f"{base_url}/api/calendar/enhanced/health",
            json={"user_id": test_user_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Calendar API health check: {result.get('ok', False)}")
        else:
            print(f"❌ Calendar health endpoint failed: {response.status_code}")
            
        # Test events list endpoint
        print("\n📆 Testing Calendar events list endpoint...")
        now = datetime.now(timezone.utc)
        time_min = (now - timedelta(days=7)).isoformat()
        time_max = (now + timedelta(days=7)).isoformat()
        
        response = requests.post(
            f"{base_url}/api/calendar/enhanced/events/list",
            json={
                "user_id": test_user_id,
                "calendar_id": "primary",
                "time_min": time_min,
                "time_max": time_max,
                "max_results": 10
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Calendar events list response: {result.get('ok', False)}")
        else:
            print(f"⚠️ Calendar events list: {response.status_code} (Expected if no OAuth token)")
            
    except Exception as e:
        print(f"❌ Calendar API test error: {e}")

async def test_database_imports():
    """Test database imports and table creation"""
    print("\n🧪 Testing Database Imports...")
    
    try:
        # Test Google OAuth database module
        print("\n🗃️ Testing Google OAuth database module...")
        from db_oauth_google import init_google_oauth_table, get_user_google_tokens
        
        print("✅ Google OAuth database module imported successfully")
        
        # Test other Google modules
        print("\n📦 Testing Gmail enhanced API module...")
        from gmail_enhanced_api import gmail_enhanced_bp
        
        print("✅ Gmail enhanced API module imported successfully")
        
        print("\n📦 Testing Calendar enhanced API module...")
        from calendar_enhanced_api import calendar_enhanced_bp
        
        print("✅ Calendar enhanced API module imported successfully")
        
    except ImportError as e:
        print(f"❌ Module import error: {e}")
    except Exception as e:
        print(f"❌ Database test error: {e}")

async def test_main_app_imports():
    """Test main app imports"""
    print("\n🧪 Testing Main App Imports...")
    
    try:
        # Test that main app can import all modules
        print("\n🚀 Testing main app Google imports...")
        
        # These should be importable by main_api_app.py
        from db_oauth_google import init_google_oauth_table
        from gmail_enhanced_api import gmail_enhanced_bp
        from calendar_enhanced_api import calendar_enhanced_bp
        
        print("✅ All Google service modules importable by main app")
        
    except ImportError as e:
        print(f"❌ Main app import error: {e}")
    except Exception as e:
        print(f"❌ Main app test error: {e}")

async def test_oauth_database():
    """Test OAuth database functionality (if database is available)"""
    print("\n🧪 Testing OAuth Database...")
    
    try:
        import asyncpg
        from db_oauth_google import init_google_oauth_table
        
        # Test database connection (if configured)
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = int(os.getenv('DB_PORT', 5432))
        db_name = os.getenv('DB_NAME', 'atom')
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', '')
        
        if db_password:
            print("\n🔗 Testing database connection...")
            conn = await asyncpg.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password
            )
            
            # Test table creation
            await init_google_oauth_table(conn)
            print("✅ Google OAuth table initialization successful")
            
            await conn.close()
        else:
            print("⚠️ Database password not configured, skipping database test")
            
    except Exception as e:
        print(f"⚠️ Database test failed (expected if database not running): {e}")

async def main():
    """Main test function"""
    print("=" * 60)
    print("🔬 ENHANCED GOOGLE SERVICES TEST SUITE")
    print("=" * 60)
    print(f"⏰ Test started at: {datetime.now().isoformat()}")
    
    # Run all tests
    await test_database_imports()
    await test_main_app_imports()
    await test_oauth_database()
    await test_gmail_enhanced_api()
    await test_calendar_enhanced_api()
    
    print("\n" + "=" * 60)
    print("✅ TEST SUITE COMPLETED")
    print("=" * 60)
    print("💡 Notes:")
    print("- OAuth token errors are expected if not authenticated")
    print("- Database errors are expected if database is not running")
    print("- Import errors should be investigated if they occur")
    print("- Health endpoints should return 200 if modules load correctly")

if __name__ == "__main__":
    asyncio.run(main())