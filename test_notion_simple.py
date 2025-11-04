#!/usr/bin/env python3
"""
Simple Notion Integration Test
Tests basic module imports and app loading
"""

import os
import sys

# Set test environment
os.environ['DATABASE_URL'] = 'sqlite:///./test_atom.db'
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'

print("🚀 ATOM Notion Integration Simple Test")
print("=" * 50)

def test_basic_imports():
    """Test basic Notion imports"""
    print("\n📦 Testing Basic Imports...")
    
    try:
        from auth_handler_notion import auth_notion_bp
        print("  ✓ auth_handler_notion")
    except Exception as e:
        print(f"  ✗ auth_handler_notion: {e}")
        return False
    
    try:
        from notion_service_real import get_real_notion_client
        print("  ✓ notion_service_real")
    except Exception as e:
        print(f"  ✗ notion_service_real: {e}")
        return False
    
    try:
        from notion_handler_real import notion_bp
        print("  ✓ notion_handler_real")
    except Exception as e:
        print(f"  ✗ notion_handler_real: {e}")
        return False
    
    try:
        from db_oauth_notion import get_user_notion_tokens
        print("  ✓ db_oauth_notion")
    except Exception as e:
        print(f"  ✗ db_oauth_notion: {e}")
        return False
    
    return True

def test_app_import():
    """Test main app import"""
    print("\n🔧 Testing Main App Import...")
    
    try:
        # Import only what we need to avoid circular imports
        sys.path.insert(0, '.')
        
        # Test imports without loading full app
        import main_api_app
        print("  ✓ main_api_app module")
        
        # Check if blueprint variables exist
        notion_oauth_available = getattr(main_api_app, 'NOTION_OAUTH_AVAILABLE', False)
        notion_enhanced_available = getattr(main_api_app, 'NOTION_ENHANCED_AVAILABLE', False)
        
        print(f"  ✓ NOTION_OAUTH_AVAILABLE: {notion_oauth_available}")
        print(f"  ✓ NOTION_ENHANCED_AVAILABLE: {notion_enhanced_available}")
        
        return notion_oauth_available and notion_enhanced_available
        
    except Exception as e:
        print(f"  ✗ Main app import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_app():
    """Test creating a simple Flask app"""
    print("\n🌐 Testing Simple Flask App...")
    
    try:
        from flask import Flask
        from auth_handler_notion import auth_notion_bp
        from notion_handler_real import notion_bp
        
        app = Flask(__name__)
        app.register_blueprint(auth_notion_bp)
        app.register_blueprint(notion_bp)
        
        print("  ✓ Flask app created with Notion blueprints")
        
        # Test routes
        routes = []
        for rule in app.url_map.iter_rules():
            if 'notion' in rule.rule.lower():
                routes.append(rule.rule)
        
        print(f"  ✓ Found {len(routes)} Notion routes")
        return True
        
    except Exception as e:
        print(f"  ✗ Simple app failed: {e}")
        return False

def main():
    """Main test function"""
    results = []
    
    results.append(("Basic Imports", test_basic_imports()))
    results.append(("App Import", test_app_import()))
    results.append(("Simple App", test_simple_app()))
    
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
        print("🎉 Basic tests passed! Notion integration components are working.")
        print("\n📋 Next Steps:")
        print("1. Configure PostgreSQL database")
        print("2. Set NOTION_CLIENT_ID and NOTION_CLIENT_SECRET")
        print("3. Start the Flask app: python main_api_app.py")
        print("4. Test endpoints with curl or browser")
        return True
    else:
        print("⚠️  Some basic tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)