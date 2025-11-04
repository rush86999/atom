#!/usr/bin/env python3
"""
Quick Asana Integration Verification
Simple script to verify Asana integration is working
"""

import os
import sys
import requests
import json

# Add backend modules to Python path
backend_path = os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


def check_backend():
    """Check if backend is accessible"""
    print("🔍 Checking backend accessibility...")
    try:
        response = requests.get("http://localhost:5000/healthz", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is accessible on port 5000")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend not accessible: {e}")
        return False


def check_asana_imports():
    """Check if Asana modules can be imported"""
    print("\n📦 Checking Asana module imports...")
    modules = [
        "asana_service_real",
        "asana_handler",
        "auth_handler_asana",
        "db_oauth_asana",
    ]

    all_imported = True
    for module in modules:
        try:
            if module == "asana_service_real":
                from asana_service_real import AsanaServiceReal
            elif module == "asana_handler":
                from asana_handler import asana_bp
            elif module == "auth_handler_asana":
                from auth_handler_asana import auth_asana_bp
            elif module == "db_oauth_asana":
                from db_oauth_asana import store_tokens
            print(f"✅ {module} imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import {module}: {e}")
            all_imported = False

    return all_imported


def check_environment():
    """Check environment configuration"""
    print("\n🔑 Checking environment configuration...")
    required_vars = ["ASANA_CLIENT_ID", "ASANA_CLIENT_SECRET", "DATABASE_URL"]

    configured = 0
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: Configured")
            configured += 1
        else:
            print(f"❌ {var}: Not configured")

    return configured


def main():
    """Main verification function"""
    print("🚀 Quick Asana Integration Verification")
    print("=" * 50)

    # Check backend
    backend_ok = check_backend()

    # Check imports
    imports_ok = check_asana_imports()

    # Check environment
    env_configured = check_environment()

    # Summary
    print("\n" + "=" * 50)
    print("📊 VERIFICATION SUMMARY:")
    print(f"   Backend: {'✅ OK' if backend_ok else '❌ ISSUE'}")
    print(f"   Imports: {'✅ OK' if imports_ok else '❌ ISSUE'}")
    print(f"   Environment: {env_configured}/3 variables configured")

    if backend_ok and imports_ok and env_configured >= 2:
        print("\n🎉 Asana integration is READY for OAuth setup!")
        print("   Next steps:")
        print("   1. Set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET")
        print("   2. Configure Asana OAuth app")
        print("   3. Test OAuth flow")
    else:
        print("\n⚠️  Some issues detected:")
        if not backend_ok:
            print("   - Backend not accessible")
        if not imports_ok:
            print("   - Module import issues")
        if env_configured < 2:
            print("   - Environment variables not configured")


if __name__ == "__main__":
    main()
