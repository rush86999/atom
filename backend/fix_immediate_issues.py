#!/usr/bin/env python3
"""
Focused Fix Script for Immediate ATOM Issues

This script addresses the critical issues preventing Asana integration from working:
1. Backend accessibility issues
2. Missing environment variables
3. Service registration problems

Execution time: ~10 minutes
"""

import os
import sys
import subprocess
import time
import requests
from pathlib import Path


def print_step(message):
    """Print formatted step message"""
    print(f"\n🔧 {message}")
    print("-" * 50)


def print_success(message):
    """Print success message"""
    print(f"✅ {message}")


def print_error(message):
    """Print error message"""
    print(f"❌ {message}")


def print_info(message):
    """Print info message"""
    print(f"ℹ️  {message}")


def setup_environment():
    """Setup basic environment variables"""
    print_step("Setting up environment variables")

    # Create minimal .env file
    env_content = """# ATOM Development Environment
DATABASE_URL=sqlite:///./data/atom_development.db
FLASK_ENV=development
FLASK_SECRET_KEY=dev-secret-key-change-in-production
ATOM_OAUTH_ENCRYPTION_KEY=nCsfAph2Gln5Ag0uuEeqUVOvSEPtl7OLGT_jKsyzP84=
PYTHON_API_SERVICE_BASE_URL=http://localhost:8000

# Asana OAuth (configure these with actual values)
ASANA_CLIENT_ID=your_asana_client_id_here
ASANA_CLIENT_SECRET=your_asana_client_secret_here
ASANA_REDIRECT_URI=http://localhost:8000/api/auth/asana/callback

# Test configuration
TEST_USER_ID=test_user_asana
"""

    env_file = Path(".env")
    env_file.write_text(env_content)
    print_success("Created .env file with basic configuration")

    # Load environment variables
    for line in env_content.split("\n"):
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

    print_success("Environment variables loaded")


def stop_existing_backends():
    """Stop any existing backend processes"""
    print_step("Stopping existing backend processes")

    try:
        # Kill Python processes running backend
        subprocess.run(["pkill", "-f", "python.*backend"], capture_output=True)
        subprocess.run(["pkill", "-f", "python.*flask"], capture_output=True)
        subprocess.run(["pkill", "-f", "python.*main_api"], capture_output=True)
        time.sleep(2)
        print_success("Stopped existing backend processes")
    except Exception as e:
        print_error(f"Error stopping processes: {e}")


def start_proper_backend():
    """Start the backend with proper configuration"""
    print_step("Starting backend with Asana integration")

    # Add backend to Python path
    backend_path = Path("backend/python-api-service")
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    try:
        # Import and start the proper backend
        from backend.python_api_service.main_api_app import create_app

        app = create_app()

        # Start in background
        import threading

        def run_app():
            app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

        thread = threading.Thread(target=run_app, daemon=True)
        thread.start()

        print_success("Backend started on port 8000")
        return True

    except Exception as e:
        print_error(f"Failed to start proper backend: {e}")
        return False


def wait_for_backend(max_wait=30):
    """Wait for backend to become accessible"""
    print_step("Waiting for backend to become accessible")

    for i in range(max_wait):
        try:
            response = requests.get("http://localhost:8000/", timeout=5)
            if response.status_code == 200:
                print_success(f"Backend is accessible after {i + 1} seconds")
                return True
        except:
            pass

        time.sleep(1)
        if (i + 1) % 5 == 0:
            print_info(f"Still waiting... ({i + 1}/{max_wait} seconds)")

    print_error("Backend failed to become accessible")
    return False


def test_asana_endpoints():
    """Test Asana integration endpoints"""
    print_step("Testing Asana integration endpoints")

    endpoints_to_test = [
        "/api/asana/health",
        "/api/auth/asana/authorize?user_id=test_user",
        "/api/auth/asana/status?user_id=test_user",
    ]

    working_endpoints = 0

    for endpoint in endpoints_to_test:
        try:
            url = f"http://localhost:8000{endpoint}"
            if endpoint.startswith("/api/auth/asana/authorize"):
                response = requests.get(url, timeout=10)
            else:
                response = requests.get(url, timeout=5)

            if response.status_code == 200:
                print_success(f"{endpoint} - Working")
                working_endpoints += 1
            elif response.status_code == 404:
                print_error(f"{endpoint} - Not found (endpoint not registered)")
            else:
                print_info(f"{endpoint} - Status {response.status_code}")

        except Exception as e:
            print_error(f"{endpoint} - Failed: {e}")

    return working_endpoints


def check_service_imports():
    """Verify all Asana service modules can be imported"""
    print_step("Checking Asana service imports")

    modules = [
        "asana_service_real",
        "asana_handler",
        "auth_handler_asana",
        "db_oauth_asana",
    ]

    successful_imports = 0

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

            print_success(f"{module} - Imported successfully")
            successful_imports += 1

        except ImportError as e:
            print_error(f"{module} - Import failed: {e}")

    return successful_imports


def generate_next_steps_report(backend_ok, endpoints_working, imports_ok):
    """Generate next steps based on current status"""
    print_step("NEXT STEPS REPORT")

    if backend_ok and endpoints_working >= 2 and imports_ok == 4:
        print_success("🎉 Asana integration is READY!")
        print_info("Next steps:")
        print("1. Configure actual Asana OAuth credentials in .env file")
        print("2. Set up Asana developer app with redirect URI")
        print("3. Test OAuth flow with real Asana account")
        print("4. Verify task creation and project management")

    else:
        print_error("⚠️ Some issues need attention:")

        if not backend_ok:
            print("   - Backend not accessible on port 8000")
            print("   - Check if backend started properly")

        if endpoints_working < 2:
            print(f"   - Only {endpoints_working}/3 Asana endpoints working")
            print("   - Verify Asana blueprints are registered")

        if imports_ok < 4:
            print(f"   - Only {imports_ok}/4 Asana modules imported")
            print("   - Check Python path and module locations")

        print_info("Immediate fixes:")
        print("1. Run: python backend/python-api-service/main_api_app.py")
        print("2. Check backend logs for registration messages")
        print("3. Verify all Asana files are in backend/python-api-service/")


def main():
    """Main execution function"""
    print("🚀 ATOM IMMEDIATE ISSUES FIX SCRIPT")
    print("=" * 60)

    # Step 1: Setup environment
    setup_environment()

    # Step 2: Stop existing backends
    stop_existing_backends()

    # Step 3: Start proper backend
    backend_started = start_proper_backend()

    if not backend_started:
        print_error("Failed to start backend. Manual intervention required.")
        return

    # Step 4: Wait for backend
    backend_ok = wait_for_backend()

    if not backend_ok:
        print_error("Backend failed to start. Check logs and try manual startup.")
        return

    # Step 5: Test imports
    imports_ok = check_service_imports()

    # Step 6: Test endpoints
    endpoints_working = test_asana_endpoints()

    # Step 7: Generate report
    generate_next_steps_report(backend_ok, endpoints_working, imports_ok)

    print("\n" + "=" * 60)
    print("📊 EXECUTION SUMMARY:")
    print(f"   Backend: {'✅ OK' if backend_ok else '❌ FAILED'}")
    print(f"   Endpoints: {endpoints_working}/3 working")
    print(f"   Imports: {imports_ok}/4 successful")

    if backend_ok and endpoints_working >= 2 and imports_ok == 4:
        print("\n🎯 STATUS: READY FOR OAUTH CONFIGURATION")
    else:
        print("\n🎯 STATUS: NEEDS MANUAL INTERVENTION")


if __name__ == "__main__":
    main()
