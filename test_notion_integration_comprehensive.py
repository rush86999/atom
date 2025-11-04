#!/usr/bin/env python3
"""
ATOM Notion Integration Test Script
Tests backend components, endpoints, and basic functionality
"""

import os
import sys
import json
import requests
from datetime import datetime

def test_environment():
    """Test environment configuration"""
    print("🔍 Testing Environment Configuration...")
    
    env_vars = [
        'DATABASE_URL',
        'NOTION_CLIENT_ID', 
        'NOTION_CLIENT_SECRET',
        'NOTION_REDIRECT_URI',
        'FLASK_SECRET_KEY'
    ]
    
    missing_vars = []
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✓ {var}: {'*' * min(len(value), 10)}")
        else:
            print(f"  ✗ {var}: Missing")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {missing_vars}")
        return False
    else:
        print("  ✓ All required environment variables set")
        return True

def test_database_connection():
    """Test database connection"""
    print("\n🗄️ Testing Database Connection...")
    
    try:
        # Import database utilities
        from db_utils import get_db_pool
        
        # Get connection pool
        db_pool = get_db_pool()
        if db_pool:
            print("  ✓ Database connection pool created")
            
            # Test connection
            with db_pool.getconn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                print("  ✓ Database connection test passed")
            return True
        else:
            print("  ✗ Database connection pool failed")
            return False
            
    except Exception as e:
        print(f"  ✗ Database connection failed: {e}")
        return False

def test_notion_modules():
    """Test Notion module imports"""
    print("\n📦 Testing Notion Module Imports...")
    
    modules = [
        ('auth_handler_notion', 'auth_notion_bp'),
        ('notion_service_real', 'get_real_notion_client'),
        ('notion_handler_real', 'notion_bp'),
        ('db_oauth_notion', 'get_user_notion_tokens'),
        ('notion_enhanced_api', 'notion_enhanced_bp')
    ]
    
    success = True
    for module_name, item in modules:
        try:
            module = __import__(module_name)
            if hasattr(module, item):
                print(f"  ✓ {module_name}.{item}")
            else:
                print(f"  ✗ {module_name}.{item} (missing)")
                success = False
        except ImportError as e:
            print(f"  ✗ {module_name}: {e}")
            success = False
        except Exception as e:
            print(f"  ✗ {module_name}: {e}")
            success = False
    
    return success

def test_blueprint_registration():
    """Test blueprint registration in main app"""
    print("\n🔧 Testing Blueprint Registration...")
    
    try:
        from main_api_app import app, ASANA_OAUTH_AVAILABLE, NOTION_OAUTH_AVAILABLE
        
        print(f"  ✓ Main app imported")
        print(f"  ✓ Asana OAuth available: {ASANA_OAUTH_AVAILABLE}")
        print(f"  ✓ Notion OAuth available: {NOTION_OAUTH_AVAILABLE}")
        
        # Check registered routes
        notion_routes = []
        for rule in app.url_map.iter_rules():
            if 'notion' in rule.rule.lower():
                notion_routes.append(rule.rule)
        
        print(f"  ✓ Found {len(notion_routes)} Notion routes:")
        for route in notion_routes:
            print(f"    - {route}")
        
        return len(notion_routes) > 0
        
    except Exception as e:
        print(f"  ✗ Blueprint registration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test API endpoints (if server is running)"""
    print("\n🌐 Testing API Endpoints...")
    
    base_url = "http://localhost:5058"
    test_endpoints = [
        ("/", "GET"),
        ("/api/real/notion/health", "GET"),
        ("/api/real/notion/search", "GET"),
        ("/api/real/notion/pages", "GET"),
        ("/api/real/notion/databases", "GET")
    ]
    
    for endpoint, method in test_endpoints:
        try:
            url = base_url + endpoint
            if method == "GET":
                response = requests.get(url, timeout=5)
            else:
                response = requests.post(url, timeout=5)
            
            if response.status_code == 200:
                print(f"  ✓ {method} {endpoint} - {response.status_code}")
            elif response.status_code == 401:
                print(f"  ⚠️  {method} {endpoint} - {response.status_code} (Auth required)")
            elif response.status_code == 404:
                print(f"  ✗ {method} {endpoint} - {response.status_code} (Not found)")
            else:
                print(f"  ⚠️  {method} {endpoint} - {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"  ⚠️  {method} {endpoint} - Connection refused (server not running)")
        except requests.exceptions.Timeout:
            print(f"  ⚠️  {method} {endpoint} - Timeout")
        except Exception as e:
            print(f"  ✗ {method} {endpoint} - {e}")

def test_frontend_components():
    """Test frontend component files exist"""
    print("\n🎨 Testing Frontend Components...")
    
    frontend_files = [
        'src/ui-shared/integrations/notion/index.ts',
        'src/ui-shared/integrations/notion/skills/notionSkills.ts',
        'src/ui-shared/integrations/notion/skills/notionSkillsEnhanced.ts',
        'src/ui-shared/integrations/notion/components/NotionSkills.tsx'
    ]
    
    success = True
    for file_path in frontend_files:
        if os.path.exists(file_path):
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path}")
            success = False
    
    return success

def test_notion_client():
    """Test Notion client (if credentials available)"""
    print("\n🔌 Testing Notion Client...")
    
    # Check if we have test credentials
    access_token = os.getenv('NOTION_ACCESS_TOKEN') or os.getenv('NOTION_API_TOKEN')
    
    if not access_token or access_token == 'your_notion_token_here':
        print("  ⚠️  No test credentials available")
        return True  # Not a failure, just no test
    
    try:
        from notion_client import Client
        notion = Client(auth=access_token)
        
        # Test search
        response = notion.search(query="test", page_size=1)
        print("  ✓ Notion client connected successfully")
        
        # Check workspace info
        if response.get("results"):
            print("  ✓ Notion search working")
        else:
            print("  ⚠️  Notion search returned no results")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Notion client failed: {e}")
        return False

def generate_setup_instructions():
    """Generate setup instructions"""
    print("\n📋 Setup Instructions:")
    
    print("""
1. Configure Environment:
   export DATABASE_URL="sqlite:///./atom_development.db"
   export FLASK_SECRET_KEY="your-secret-key"
   export NOTION_CLIENT_ID="your-client-id"
   export NOTION_CLIENT_SECRET="your-client-secret"
   export NOTION_REDIRECT_URI="http://localhost:5058/api/auth/notion/callback"

2. Start PostgreSQL (for production):
   brew services start postgresql
   createdb atom_development
   createuser atom_user

3. Run Database Migration:
   psql -d atom_development -f migrations/003_notion_oauth.sql

4. Configure Notion Integration:
   - Go to https://www.notion.so/my-integrations
   - Create new integration
   - Update NOTION_CLIENT_ID and NOTION_CLIENT_SECRET

5. Start Backend Server:
   python main_api_app.py
   or
   gunicorn --workers 4 --bind 0.0.0.0:5058 main_api_app:app

6. Test Integration:
   - Open http://localhost:5058/
   - Check Notion health: http://localhost:5058/api/real/notion/health?user_id=test_user
   - Connect Notion account: http://localhost:5058/api/auth/notion/authorize?user_id=test_user
""")

def main():
    """Main test function"""
    print("🚀 ATOM Notion Integration Test")
    print("=" * 50)
    
    # Test all components
    results = []
    
    results.append(("Environment", test_environment()))
    results.append(("Database", test_database_connection()))
    results.append(("Modules", test_notion_modules()))
    results.append(("Blueprints", test_blueprint_registration()))
    results.append(("API Endpoints", test_api_endpoints()))
    results.append(("Frontend", test_frontend_components()))
    results.append(("Notion Client", test_notion_client()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {test_name:<20} {status}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Notion integration is ready.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        generate_setup_instructions()
    
    return passed == total

if __name__ == "__main__":
    # Use local environment for testing
    os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_atom.db')
    os.environ.setdefault('FLASK_SECRET_KEY', 'test-secret-key')
    
    success = main()
    sys.exit(0 if success else 1)