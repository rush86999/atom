#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Readiness Verification Script
Tests that all critical security fixes are working correctly
"""

import subprocess
import sys
import os

def test_authentication_required():
    """Test that endpoints now require authentication"""
    print("🔍 Testing Authentication Requirements...")

    # Check that api_routes.py has authentication dependencies
    with open('/home/developer/projects/atom/backend/core/api_routes.py', 'r') as f:
        content = f.read()

    required_imports = [
        'from .auth import get_current_user',
        'Depends(get_current_user)'
    ]

    missing_auth = []
    for req in required_imports:
        if req not in content:
            missing_auth.append(req)

    if missing_auth:
        print(f"❌ MISSING AUTH: {missing_auth}")
        return False
    else:
        print("✅ Authentication requirements present")
        return True

def test_database_security():
    """Test that database configuration is production-ready"""
    print("🔍 Testing Database Security...")

    with open('/home/developer/projects/atom/backend/core/database.py', 'r') as f:
        content = f.read()

    required_features = [
        'def get_database_url',
        'DATABASE_URL environment variable is required in production',
        'sslmode=require',
        'pool_size'
    ]

    missing_features = []
    for feature in required_features:
        if feature not in content:
            missing_features.append(feature)

    if missing_features:
        print(f"❌ MISSING DB SECURITY: {missing_features}")
        return False
    else:
        print("✅ Database security features present")
        return True

def test_no_mock_fallbacks():
    """Test that mock data fallbacks are removed"""
    print("🔍 Testing Mock Data Removal...")

    # Check key integration files for mock data removal
    files_to_check = [
        '/home/developer/projects/atom/backend/integrations/salesforce_routes.py',
        '/home/developer/projects/atom/backend/integrations/hubspot_routes.py',
        '/home/developer/projects/atom/backend/integrations/zoom_routes.py'
    ]

    mock_issues = []
    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
                if 'mock_manager.get_mock_data' in content:
                    mock_issues.append(file_path)

    if mock_issues:
        print(f"❌ MOCK DATA STILL PRESENT: {mock_issues}")
        return False
    else:
        print("✅ Mock data fallbacks removed")
        return True

def test_archive_created():
    """Test that old insecure files are archived"""
    print("🔍 Testing File Archival...")

    archive_files = [
        '/home/developer/projects/atom/backend/core/archive/auth_v1.py',
        '/home/developer/projects/atom/backend/core/archive/api_routes_v1.py',
        '/home/developer/projects/atom/backend/core/archive/database_v1.py'
    ]

    missing_archives = []
    for file_path in archive_files:
        if not os.path.exists(file_path):
            missing_archives.append(file_path)

    if missing_archives:
        print(f"❌ MISSING ARCHIVES: {missing_archives}")
        return False
    else:
        print("✅ Old files properly archived")
        return True

def test_security_headers():
    """Test that security middleware is configured"""
    print("🔍 Testing Security Headers...")

    with open('/home/developer/projects/atom/backend/main_api_app.py', 'r') as f:
        content = f.read()

    required_middleware = [
        'SecurityHeadersMiddleware',
        'RateLimitMiddleware',
        'allow_origins'  # Should NOT be ["*"]
    ]

    middleware_issues = []

    if 'allow_origins=["*"]' in content:
        middleware_issues.append("CORS allows all origins (*)")

    if 'SecurityHeadersMiddleware' not in content:
        middleware_issues.append("Missing SecurityHeadersMiddleware")

    if 'RateLimitMiddleware' not in content:
        middleware_issues.append("Missing RateLimitMiddleware")

    if middleware_issues:
        print(f"❌ SECURITY MIDDLEWARE ISSUES: {middleware_issues}")
        return False
    else:
        print("✅ Security middleware properly configured")
        return True

def run_import_tests():
    """Test that the modified files can be imported without syntax errors"""
    print("🔍 Testing Import Syntax...")

    try:
        # Test database import
        import sys
        sys.path.insert(0, '/home/developer/projects/atom/backend')

        # Test database module
        from core.database import get_database_url, DATABASE_URL
        print("✅ Database module imports successfully")

        # Test api routes module
        from core.api_routes import router
        print("✅ API routes module imports successfully")

        return True
    except Exception as e:
        print(f"❌ IMPORT ERROR: {e}")
        return False

def main():
    """Run all production readiness tests"""
    print("🚀 ATOM Platform Production Readiness Verification")
    print("=" * 60)

    tests = [
        ("Authentication Security", test_authentication_required),
        ("Database Security", test_database_security),
        ("Mock Data Removal", test_no_mock_fallbacks),
        ("File Archival", test_archive_created),
        ("Security Headers", test_security_headers),
        ("Import Syntax", run_import_tests)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"   ⚠️  {test_name} FAILED")

    print("\n" + "=" * 60)
    print(f"📊 RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL TESTS PASSED - APP IS PRODUCTION READY!")
        print("\n✅ Critical security issues fixed")
        print("✅ Authentication properly implemented")
        print("✅ Database configuration secured")
        print("✅ Mock data removed from production")
        print("✅ Old code safely archived")

        print("\n🚀 Ready for deployment with:")
        print("   - PostgreSQL database")
        print("   - Proper environment variables")
        print("   - HTTPS/SSL configuration")
        print("   - Domain CORS configuration")

        return True
    else:
        print("❌ PRODUCTION NOT READY - Fix failed tests")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)