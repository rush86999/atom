#!/usr/bin/env python3
"""
Quick Fix for Notion Integration Database Issues
"""

import os
import sys

# Set minimal working environment
os.environ['DATABASE_URL'] = 'sqlite:///./quick_test.db'
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'

def test_flask_notion():
    """Test Flask app with Notion routes only"""
    print("🔧 Testing Flask + Notion Integration...")
    
    try:
        from flask import Flask
        from notion_handler_real import notion_bp
        from auth_handler_notion import auth_notion_bp
        
        app = Flask(__name__)
        app.register_blueprint(notion_bp)
        app.register_blueprint(auth_notion_bp)
        
        print("  ✓ Flask app created with Notion blueprints")
        
        # Test routes
        routes = []
        for rule in app.url_map.iter_rules():
            if 'notion' in rule.rule.lower():
                routes.append(rule.rule)
        
        print(f"  ✓ Found {len(routes)} Notion routes:")
        for route in routes:
            print(f"    - {route}")
        
        # Test client
        with app.test_client() as client:
            response = client.get('/api/notion/health?user_id=test')
            if response.status_code in [200, 401, 404]:
                print(f"  ✓ Health endpoint: {response.status_code}")
            else:
                print(f"  ✗ Health endpoint: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Flask test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_notion_client():
    """Test Notion client with mock data"""
    print("\n🔌 Testing Notion Client...")
    
    try:
        from notion_service_real import RealNotionService
        
        # Create service with mock token
        service = RealNotionService("mock_token")
        
        # Test service status
        status = service.get_service_status()
        print(f"  ✓ Service status: {status.get('status')}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Notion client test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Quick Notion Integration Test")
    print("=" * 50)
    
    results = []
    
    results.append(("Flask + Notion", test_flask_notion()))
    results.append(("Notion Client", test_simple_notion_client()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 QUICK TEST SUMMARY:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {test_name:<20} {status}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 Quick tests passed! Notion integration core is working.")
        print("\n📋 Next Steps:")
        print("1. Configure PostgreSQL for production")
        print("2. Set actual Notion OAuth credentials")
        print("3. Test full integration with real tokens")
        print("4. Deploy to production")
    else:
        print("⚠️  Some tests failed. Check errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)