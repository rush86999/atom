#!/usr/bin/env python3
"""
Backend Server Diagnostic and Fix Script
Quickly analyzes and fixes common backend server startup issues
"""

import os
import sys
import subprocess
import time
import signal
import psutil
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return output"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def check_port_in_use(port):
    """Check if a port is in use and by what process"""
    try:
        # Using lsof to check port usage
        cmd = f"lsof -ti:{port}"
        returncode, stdout, stderr = run_command(cmd)
        if returncode == 0 and stdout.strip():
            pids = [int(pid) for pid in stdout.strip().split("\n") if pid]
            processes = []
            for pid in pids:
                try:
                    proc = psutil.Process(pid)
                    processes.append(
                        {
                            "pid": pid,
                            "name": proc.name(),
                            "cmdline": " ".join(proc.cmdline()),
                            "status": proc.status(),
                        }
                    )
                except psutil.NoSuchProcess:
                    processes.append(
                        {
                            "pid": pid,
                            "name": "Unknown",
                            "cmdline": "",
                            "status": "Terminated",
                        }
                    )
            return True, processes
        return False, []
    except Exception as e:
        return False, []


def kill_processes_on_port(port):
    """Kill processes using the specified port"""
    in_use, processes = check_port_in_use(port)
    if in_use:
        print(f"🔴 Port {port} is in use by {len(processes)} process(es):")
        for proc in processes:
            print(
                f"   - PID {proc['pid']}: {proc['name']} - {proc['cmdline'][:100]}..."
            )

        # Kill the processes
        cmd = f"lsof -ti:{port} | xargs kill -9"
        returncode, stdout, stderr = run_command(cmd)
        if returncode == 0:
            print(f"✅ Successfully killed processes on port {port}")
            time.sleep(1)  # Give time for processes to terminate
            # Verify they're gone
            in_use_after, _ = check_port_in_use(port)
            if not in_use_after:
                print(f"✅ Port {port} is now free")
                return True
            else:
                print(f"❌ Failed to free port {port}")
                return False
        else:
            print(f"❌ Failed to kill processes on port {port}: {stderr}")
            return False
    else:
        print(f"✅ Port {port} is free")
        return True


def check_environment_variables():
    """Check if required environment variables are set"""
    required_vars = ["DATABASE_URL", "FLASK_SECRET_KEY", "ATOM_OAUTH_ENCRYPTION_KEY"]
    optional_vars = ["PYTHON_API_PORT", "DEBUG", "FLASK_ENV"]

    print("\n🔍 Checking environment variables...")

    missing_required = []
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)
            print(f"   ❌ {var}: Not set")
        else:
            print(f"   ✅ {var}: Set")

    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"   ⚠️  {var}: {value}")
        else:
            print(f"   ℹ️  {var}: Not set (optional)")

    return missing_required


def check_python_dependencies():
    """Check if required Python packages are installed"""
    required_packages = [
        "flask",
        "psycopg2",
        "requests",
        "cryptography",
        "openai",
        "dropbox",
        "google-api-python-client",
    ]

    print("\n🔍 Checking Python dependencies...")

    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}: Installed")
        except ImportError:
            missing_packages.append(package)
            print(f"   ❌ {package}: Missing")

    return missing_packages


def check_database_connection():
    """Check if database connection is working"""
    print("\n🔍 Checking database connection...")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("   ❌ DATABASE_URL not set")
        return False

    try:
        import psycopg2

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        print(f"   ✅ Database connection successful: {version.split(',')[0]}")
        return True
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        return False


def create_minimal_env_file():
    """Create a minimal .env file if it doesn't exist"""
    env_file = Path("backend/python-api-service/.env")

    if env_file.exists():
        print(f"\n✅ Environment file exists: {env_file}")
        return True

    print(f"\n📝 Creating minimal environment file: {env_file}")

    env_content = """# Backend Environment Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
FLASK_SECRET_KEY=dev_secret_key_change_in_production_$(date +%s)
ATOM_OAUTH_ENCRYPTION_KEY=dev_encryption_key_change_in_production_$(date +%s)
PYTHON_API_PORT=5059

# External Service API Keys (Mock/Development)
DEEPGRAM_API_KEY=mock_deepgram_api_key
OPENAI_API_KEY=mock_openai_api_key

# OAuth Configuration (Mock/Development)
GOOGLE_CLIENT_ID=mock_google_client_id
GOOGLE_CLIENT_SECRET=mock_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback

MICROSOFT_CLIENT_ID=mock_microsoft_client_id
MICROSOFT_CLIENT_SECRET=mock_microsoft_client_secret
MICROSOFT_REDIRECT_URI=http://localhost:3000/auth/microsoft/callback

# Development Flags
DEBUG=true
FLASK_ENV=development
"""

    try:
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text(env_content)
        print(f"✅ Created environment file: {env_file}")
        return True
    except Exception as e:
        print(f"❌ Failed to create environment file: {e}")
        return False


def test_backend_startup():
    """Test if backend can start successfully"""
    print("\n🚀 Testing backend startup...")

    # First, free up the port
    port = int(os.getenv("PYTHON_API_PORT", "5059"))
    if not kill_processes_on_port(port):
        print("❌ Cannot proceed - port is still in use")
        return False

    # Try to start the backend with timeout
    backend_dir = Path("backend/python-api-service")
    cmd = f"timeout 15 python main_api_app.py"

    print(f"Starting backend server (timeout: 15 seconds)...")
    process = subprocess.Popen(
        cmd,
        shell=True,
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait for process with timeout
    try:
        stdout, stderr = process.communicate(timeout=20)
        returncode = process.returncode

        if returncode == 124:  # timeout exit code
            print("❌ Backend startup timed out (frozen)")
            print("STDOUT:", stdout[-500:] if stdout else "No output")
            print("STDERR:", stderr[-500:] if stderr else "No errors")
            return False
        elif returncode == 0:
            print("✅ Backend started successfully")
            print("STDOUT:", stdout[-200:] if stdout else "No output")
            return True
        else:
            print(f"❌ Backend failed with exit code {returncode}")
            print("STDOUT:", stdout[-500:] if stdout else "No output")
            print("STDERR:", stderr[-500:] if stderr else "No errors")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Backend startup timed out")
        process.kill()
        stdout, stderr = process.communicate()
        print("STDOUT:", stdout[-500:] if stdout else "No output")
        print("STDERR:", stderr[-500:] if stderr else "No errors")
        return False


def analyze_startup_issues():
    """Analyze common startup issues and suggest fixes"""
    print("\n🔧 Analyzing startup issues...")

    issues_found = []

    # Check for stuck database initialization
    print("1. Checking for database initialization issues...")
    if not os.getenv("DATABASE_URL"):
        issues_found.append("DATABASE_URL not set - database features will not work")
        print("   ⚠️  DATABASE_URL not set - using mock data")

    # Check for missing dependencies
    missing_deps = check_python_dependencies()
    if missing_deps:
        issues_found.append(f"Missing Python packages: {', '.join(missing_deps)}")

    # Check port availability
    port = int(os.getenv("PYTHON_API_PORT", "5059"))
    in_use, processes = check_port_in_use(port)
    if in_use:
        issues_found.append(f"Port {port} is in use by other processes")

    # Check environment file
    env_file = Path("backend/python-api-service/.env")
    if not env_file.exists():
        issues_found.append("Environment file missing")

    return issues_found


def apply_fixes():
    """Apply common fixes for backend startup issues"""
    print("\n🔧 Applying fixes...")

    fixes_applied = []

    # 1. Create environment file
    if create_minimal_env_file():
        fixes_applied.append("Created minimal environment file")

    # 2. Free up port
    port = int(os.getenv("PYTHON_API_PORT", "5059"))
    if kill_processes_on_port(port):
        fixes_applied.append(f"Freed up port {port}")

    # 3. Load environment variables
    env_file = Path("backend/python-api-service/.env")
    if env_file.exists():
        # Load environment variables from file
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key] = value
        fixes_applied.append("Loaded environment variables")

    return fixes_applied


def main():
    """Main diagnostic function"""
    print("🚀 ATOM Backend Server Diagnostic Tool")
    print("=" * 50)

    # Change to project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    print(f"Working directory: {project_root}")

    # Step 1: Analyze current state
    print("\n📊 STEP 1: System Analysis")
    print("-" * 30)

    issues = analyze_startup_issues()
    missing_env_vars = check_environment_variables()
    _ = check_python_dependencies()

    if issues:
        print(f"\n⚠️  Found {len(issues)} potential issue(s):")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("\n✅ No major issues detected in analysis")

    # Step 2: Apply fixes
    print("\n📊 STEP 2: Applying Fixes")
    print("-" * 30)

    fixes = apply_fixes()
    if fixes:
        print(f"✅ Applied {len(fixes)} fix(es):")
        for fix in fixes:
            print(f"   - {fix}")
    else:
        print("ℹ️  No fixes needed")

    # Step 3: Test startup
    print("\n📊 STEP 3: Testing Backend Startup")
    print("-" * 30)

    success = test_backend_startup()

    # Step 4: Summary and recommendations
    print("\n📊 STEP 4: Summary & Recommendations")
    print("-" * 30)

    if success:
        print("🎉 BACKEND SERVER IS WORKING!")
        print("\nNext steps:")
        print("1. Keep the backend server running in a separate terminal")
        print("2. Start the frontend: cd frontend-nextjs && npm run dev")
        print("3. Access the application at http://localhost:3000")
    else:
        print("❌ BACKEND SERVER STILL HAS ISSUES")
        print("\nRecommended actions:")
        print("1. Check database connection and credentials")
        print("2. Verify all required Python packages are installed")
        print("3. Check for port conflicts with other applications")
        print("4. Review backend logs for specific error messages")
        print("\nQuick manual test:")
        print("  cd backend/python-api-service")
        print(
            "  python -c \"from main_api_app import create_app; app = create_app(); print('✅ App created successfully')\""
        )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
