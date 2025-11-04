#!/usr/bin/env python3
"""
Jira Integration Startup Script
Starts the backend server with proper Jira OAuth configuration
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def load_env_variables():
    """Load environment variables from root .env file"""
    root_dir = Path(__file__).parent
    env_file = root_dir / ".env"

    if not env_file.exists():
        print("❌ .env file not found in root directory")
        return False

    print("📁 Loading environment variables from:", env_file)

    # Load environment variables
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()
                # Don't print sensitive values
                if "SECRET" in key or "KEY" in key or "PASSWORD" in key:
                    print(f"   ✅ {key} = [REDACTED]")
                else:
                    print(f"   ✅ {key} = {value}")

    return True


def check_jira_config():
    """Verify Jira OAuth configuration"""
    required_vars = ["JIRA_CLIENT_ID", "JIRA_CLIENT_SECRET"]
    missing_vars = []

    print("\n🔍 Checking Jira OAuth configuration...")
    for var in required_vars:
        if var in os.environ and os.environ[var]:
            print(f"   ✅ {var}: Configured")
        else:
            print(f"   ❌ {var}: Missing")
            missing_vars.append(var)

    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False

    # Set default redirect URI if not set
    if "JIRA_REDIRECT_URI" not in os.environ:
        os.environ["JIRA_REDIRECT_URI"] = "http://localhost:3000/oauth/jira/callback"
        print("   ⚡ JIRA_REDIRECT_URI: Set to default")

    print("✅ Jira OAuth configuration is complete!")
    return True


def start_backend_server():
    """Start the Flask backend server"""
    backend_dir = Path(__file__).parent / "backend" / "python-api-service"
    main_app = backend_dir / "main_api_with_integrations.py"

    if not main_app.exists():
        print(f"❌ Backend app not found: {main_app}")
        return False

    print(f"\n🚀 Starting backend server...")
    print(f"   📁 App: {main_app}")
    print(f"   🌐 Port: 8000")

    try:
        # Start the server in the background
        process = subprocess.Popen([sys.executable, str(main_app)], cwd=backend_dir)

        print(f"   🔧 Process ID: {process.pid}")

        # Wait for server to start
        print("   ⏳ Waiting for server to start...")
        time.sleep(5)

        # Test the server
        print("   🧪 Testing server connectivity...")
        import requests

        try:
            response = requests.get("http://localhost:8000/healthz", timeout=10)
            if response.status_code == 200:
                print("   ✅ Server is running and healthy!")
            else:
                print(f"   ⚠️  Server responded with status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Server not responding: {e}")
            return False

        return process

    except Exception as e:
        print(f"❌ Failed to start backend server: {e}")
        return False


def test_jira_oauth_endpoint():
    """Test the Jira OAuth endpoint"""
    print("\n🧪 Testing Jira OAuth endpoint...")

    try:
        import requests

        response = requests.get("http://localhost:8000/api/oauth/jira/url", timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("   ✅ Jira OAuth endpoint working!")
                print(f"   🔗 OAuth URL: {data.get('oauth_url', '')[:100]}...")
                print(f"   📋 Service: {data.get('service')}")
                print(f"   🎯 Scope: {data.get('scope')}")
                return True
            else:
                print(f"   ❌ OAuth endpoint error: {data.get('error')}")
                return False
        else:
            print(f"   ❌ HTTP {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"   ❌ Error testing OAuth endpoint: {e}")
        return False


def main():
    """Main startup function"""
    print("=" * 60)
    print("🚀 ATOM Jira Integration Startup")
    print("=" * 60)

    # Step 1: Load environment variables
    if not load_env_variables():
        return 1

    # Step 2: Check Jira configuration
    if not check_jira_config():
        return 1

    # Step 3: Start backend server
    process = start_backend_server()
    if not process:
        return 1

    # Step 4: Test Jira OAuth endpoint
    if not test_jira_oauth_endpoint():
        print("\n❌ Jira integration test failed")
        process.terminate()
        return 1

    # Success!
    print("\n" + "=" * 60)
    print("🎉 Jira Integration Started Successfully!")
    print("=" * 60)
    print("\n📋 Next Steps:")
    print("   1. 🖥️  Start the desktop app: cd desktop/tauri && npm run tauri dev")
    print("   2. ⚙️  Go to Settings → Integrations → Jira")
    print("   3. 🔗 Click 'Connect Jira' to start OAuth flow")
    print("   4. 🌐 Complete authentication in your browser")
    print("   5. ✅ Jira workspace will be connected to ATOM")
    print(f"\n🔧 Backend running on: http://localhost:8000")
    print(f"📝 Process ID: {process.pid}")
    print("\nTo stop the server: pkill -f 'main_api_with_integrations'")

    try:
        # Keep the script running
        process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down Jira integration...")
        process.terminate()

    return 0


if __name__ == "__main__":
    sys.exit(main())
