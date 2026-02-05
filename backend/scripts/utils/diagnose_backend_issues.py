#!/usr/bin/env python3
"""
🚀 ATOM Backend Diagnostic Script
Quickly diagnose and fix backend server issues
"""

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import requests


def check_port_availability(port=5058):
    """Check if port is available"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", port))
        sock.close()
        return result == 0
    except Exception as e:
        return False


def check_backend_process():
    """Check if backend process is running"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python.*main_api_app.py"], capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def check_health_endpoint():
    """Check if health endpoint responds"""
    try:
        response = requests.get("http://localhost:5058/healthz", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def check_python_dependencies():
    """Check if required Python dependencies are available"""
    required_modules = [
        "flask",
        "werkzeug",
        "requests",
        "sqlalchemy",
        "psycopg2",
        "celery",
    ]

    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)

    return missing_modules


def check_file_structure():
    """Check if required files exist"""
    required_files = [
        "backend/python-api-service/main_api_app.py",
        "backend/python-api-service/dashboard_routes.py",
        "backend/python-api-service/service_registry_routes.py",
        "backend/python-api-service/workflow_agent_integration.py",
        "backend/python-api-service/nlu_bridge_service.py",
    ]

    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)

    return missing_files


def start_backend_server():
    """Start the backend server"""
    print("🚀 Starting backend server...")
    try:
        # Kill any existing processes
        subprocess.run(["pkill", "-f", "python.*main_api_app.py"], capture_output=True)
        time.sleep(2)

        # Start the server in background
        process = subprocess.Popen(
            ["python3", "backend/python-api-service/main_api_app.py"],
            cwd=".",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for server to start
        print("⏳ Waiting for server to start...")
        for i in range(30):  # Wait up to 30 seconds
            if check_health_endpoint():
                print("✅ Backend server started successfully!")
                return True
            time.sleep(1)

        print("❌ Server failed to start within 30 seconds")
        return False

    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False


def run_comprehensive_diagnosis():
    """Run comprehensive diagnosis"""
    print("🔍 Running ATOM Backend Diagnosis...")
    print("=" * 50)

    # Check 1: Port availability
    print("1. Checking port 5058 availability...")
    port_available = check_port_availability()
    print(f"   {'✅ Port available' if port_available else '❌ Port in use'}")

    # Check 2: Backend process
    print("2. Checking backend process...")
    process_running = check_backend_process()
    print(f"   {'✅ Process running' if process_running else '❌ Process not running'}")

    # Check 3: Health endpoint
    print("3. Checking health endpoint...")
    health_ok = check_health_endpoint()
    print(
        f"   {'✅ Health endpoint responding' if health_ok else '❌ Health endpoint not responding'}"
    )

    # Check 4: Python dependencies
    print("4. Checking Python dependencies...")
    missing_deps = check_python_dependencies()
    if not missing_deps:
        print("   ✅ All dependencies available")
    else:
        print(f"   ❌ Missing dependencies: {', '.join(missing_deps)}")

    # Check 5: File structure
    print("5. Checking file structure...")
    missing_files = check_file_structure()
    if not missing_files:
        print("   ✅ All required files present")
    else:
        print(f"   ❌ Missing files: {', '.join(missing_files)}")

    print("=" * 50)

    # Summary and recommendations
    if health_ok:
        print("🎉 Backend is healthy and running!")
        return True
    else:
        print("⚠️  Backend issues detected:")

        if not process_running:
            print("   - Backend process is not running")
            print("   → Attempting to start server...")
            if start_backend_server():
                return True

        if port_available and not process_running:
            print("   - Port is available but no process")
            print("   → Try: cd backend/python-api-service && python main_api_app.py")

        if not port_available and not process_running:
            print("   - Port is in use by another process")
            print("   → Kill existing process: pkill -f 'python.*main_api_app.py'")

        if missing_deps:
            print(f"   - Missing Python dependencies: {', '.join(missing_deps)}")
            print("   → Install with: pip install " + " ".join(missing_deps))

        if missing_files:
            print(f"   - Missing required files: {', '.join(missing_files)}")
            print("   → Check file paths and restore missing files")

        return False


def quick_fix():
    """Attempt quick fixes for common issues"""
    print("🛠️  Attempting quick fixes...")

    # Kill any existing processes
    print("   - Killing existing processes...")
    subprocess.run(["pkill", "-f", "python.*main_api_app.py"], capture_output=True)
    time.sleep(2)

    # Start server directly
    print("   - Starting backend server...")
    try:
        os.chdir("backend/python-api-service")
        process = subprocess.Popen(
            ["python3", "main_api_app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait and check
        for i in range(20):
            if check_health_endpoint():
                print("   ✅ Server started successfully!")
                return True
            time.sleep(1)

        print("   ❌ Server failed to start")
        return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


if __name__ == "__main__":
    # Change to project root if needed
    if not Path("backend").exists():
        print("⚠️  Not in project root, attempting to find correct directory...")
        # Try to find the project root
        for parent in Path(".").absolute().parents:
            if (parent / "backend").exists():
                os.chdir(parent)
                print(f"✅ Changed to project root: {parent}")
                break

    if len(sys.argv) > 1 and sys.argv[1] == "--quick-fix":
        success = quick_fix()
    else:
        success = run_comprehensive_diagnosis()

    sys.exit(0 if success else 1)
