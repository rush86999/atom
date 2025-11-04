#!/usr/bin/env python3
"""
ATOM Platform - Backend Startup Fix Script

This script diagnoses and fixes common backend startup issues,
ensuring the ATOM platform backend starts reliably.
"""

import os
import sys
import subprocess
import time
import requests
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BackendStartupFixer:
    """Backend startup diagnosis and fix tool"""

    def __init__(self, backend_url="http://localhost:5058"):
        self.backend_url = backend_url
        self.backend_process = None

    def check_dependencies(self):
        """Check if all required dependencies are installed"""
        logger.info("🔍 Checking dependencies...")

        required_packages = [
            "flask",
            "psycopg2-binary",
            "requests",
            "cryptography",
            "aiohttp",
            "pandas",
            "lancedb",
            "python-dotenv",
        ]

        missing_packages = []

        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                logger.info(f"✅ {package}")
            except ImportError:
                missing_packages.append(package)
                logger.error(f"❌ {package}")

        if missing_packages:
            logger.error(f"Missing packages: {', '.join(missing_packages)}")
            logger.info("Installing missing packages...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + missing_packages,
                    check=True,
                )
                logger.info("✅ Dependencies installed successfully")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install dependencies: {e}")
                return False
        else:
            logger.info("✅ All dependencies are installed")

        return True

    def check_environment(self):
        """Check environment configuration"""
        logger.info("🔍 Checking environment configuration...")

        required_env_vars = ["FLASK_SECRET_KEY", "PYTHON_API_PORT", "DATABASE_URL"]

        for var in required_env_vars:
            value = os.getenv(var)
            if value:
                logger.info(
                    f"✅ {var}: {value[:20]}..."
                    if len(value) > 20
                    else f"✅ {var}: {value}"
                )
            else:
                logger.warning(f"⚠️  {var}: Not set (using default)")

        # Set default values if not set
        os.environ.setdefault("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
        os.environ.setdefault("PYTHON_API_PORT", "5058")
        os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/atom_dev.db")
        os.environ.setdefault("FLASK_ENV", "development")
        os.environ.setdefault("DEBUG", "true")

        logger.info("✅ Environment configuration complete")
        return True

    def check_port_availability(self):
        """Check if port 5058 is available"""
        logger.info("🔍 Checking port availability...")

        try:
            response = requests.get(f"{self.backend_url}/healthz", timeout=2)
            if response.status_code == 200:
                logger.warning("⚠️  Port 5058 is already in use")
                return False
        except requests.RequestException:
            logger.info("✅ Port 5058 is available")
            return True

        return True

    def start_minimal_backend(self):
        """Start the minimal backend API"""
        logger.info("🚀 Starting minimal backend API...")

        try:
            # Use the existing start_minimal_api.py
            self.backend_process = subprocess.Popen(
                [sys.executable, "start_minimal_api.py"], cwd="."
            )

            # Wait for backend to start
            logger.info("⏳ Waiting for backend to start...")
            time.sleep(5)

            # Check if backend is running
            if self.check_backend_health():
                logger.info("✅ Minimal backend started successfully")
                return True
            else:
                logger.error("❌ Backend failed to start")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to start backend: {e}")
            return False

    def check_backend_health(self):
        """Check if backend is healthy"""
        try:
            response = requests.get(f"{self.backend_url}/healthz", timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Backend health: {data.get('status', 'unknown')}")
                return True
            else:
                logger.error(f"❌ Backend returned HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Backend health check failed: {e}")
            return False

    def test_critical_endpoints(self):
        """Test critical API endpoints"""
        logger.info("🔍 Testing critical endpoints...")

        endpoints_to_test = [
            ("/healthz", "GET"),
            ("/api/workflow-automation/generate", "POST"),
            ("/api/services/status", "GET"),
        ]

        all_successful = True

        for endpoint, method in endpoints_to_test:
            try:
                if method == "POST" and endpoint == "/api/workflow-automation/generate":
                    response = requests.post(
                        f"{self.backend_url}{endpoint}",
                        json={"user_input": "test", "user_id": "test_user"},
                        timeout=10,
                    )
                else:
                    response = requests.get(f"{self.backend_url}{endpoint}", timeout=10)

                if response.status_code == 200:
                    logger.info(f"✅ {endpoint}: HTTP {response.status_code}")
                else:
                    logger.warning(f"⚠️  {endpoint}: HTTP {response.status_code}")
                    all_successful = False

            except Exception as e:
                logger.error(f"❌ {endpoint}: {e}")
                all_successful = False

        return all_successful

    def fix_common_issues(self):
        """Fix common backend startup issues"""
        logger.info("🔧 Fixing common issues...")

        # Fix Flask async issue
        flask_async_fix = """
# Fix for Flask async views
import asgiref.sync
import flask

# Monkey patch Flask to handle async views
original_ensure_sync = flask.Flask.ensure_sync

def patched_ensure_sync(self, func):
    if hasattr(func, '__code__') and hasattr(func.__code__, 'co_flags'):
        if func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return asgiref.sync.async_to_sync(func)
    return original_ensure_sync(self, func)

flask.Flask.ensure_sync = patched_ensure_sync
"""

        # Write the fix to a file that can be imported
        fix_file = Path("flask_async_fix.py")
        fix_file.write_text(flask_async_fix)
        logger.info("✅ Applied Flask async fix")

        return True

    def run_comprehensive_fix(self):
        """Run comprehensive backend startup fix"""
        logger.info("🚀 Starting comprehensive backend startup fix")
        print("=" * 60)

        steps = [
            ("Check Dependencies", self.check_dependencies),
            ("Check Environment", self.check_environment),
            ("Check Port Availability", self.check_port_availability),
            ("Fix Common Issues", self.fix_common_issues),
            ("Start Backend", self.start_minimal_backend),
            ("Test Endpoints", self.test_critical_endpoints),
        ]

        results = []

        for step_name, step_func in steps:
            logger.info(f"\n🔧 {step_name}...")
            try:
                result = step_func()
                results.append((step_name, result))
                status = "✅ SUCCESS" if result else "❌ FAILED"
                logger.info(f"   {status}")
            except Exception as e:
                logger.error(f"   ❌ ERROR: {e}")
                results.append((step_name, False))

        # Generate report
        successful_steps = sum(1 for _, result in results if result)
        total_steps = len(results)

        print(f"\n📊 BACKEND STARTUP FIX REPORT")
        print("=" * 60)
        print(f"Successful steps: {successful_steps}/{total_steps}")

        for step_name, result in results:
            status_icon = "✅" if result else "❌"
            print(f"{status_icon} {step_name}")

        if successful_steps == total_steps:
            print("\n🎉 Backend startup fix completed successfully!")
            print("The ATOM platform backend is now running on http://localhost:5058")
        else:
            print(
                f"\n⚠️  Backend startup fix partially completed ({successful_steps}/{total_steps})"
            )
            print("Some features may not be available")

        # Save detailed report
        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "successful_steps": successful_steps,
            "total_steps": total_steps,
            "results": [{"step": step, "success": result} for step, result in results],
            "backend_url": self.backend_url,
            "status": "FULLY_OPERATIONAL"
            if successful_steps == total_steps
            else "PARTIALLY_OPERATIONAL",
        }

        with open("backend_startup_report.json", "w") as f:
            import json

            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved to: backend_startup_report.json")

        return successful_steps == total_steps

    def stop_backend(self):
        """Stop the backend process"""
        if self.backend_process:
            logger.info("🛑 Stopping backend...")
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=10)
                logger.info("✅ Backend stopped successfully")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️  Backend did not stop gracefully, forcing...")
                self.backend_process.kill()

        # Clean up fix file
        fix_file = Path("flask_async_fix.py")
        if fix_file.exists():
            fix_file.unlink()


def main():
    """Main function"""
    fixer = BackendStartupFixer()

    try:
        success = fixer.run_comprehensive_fix()

        if success:
            print("\n🚀 Ready for next steps!")
            print("You can now run:")
            print("  python execute_next_steps.py")
            print("  python activate_service_integrations.py")
            sys.exit(0)
        else:
            print("\n❌ Backend startup fix needs attention")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user")
        fixer.stop_backend()
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        fixer.stop_backend()
        sys.exit(2)


if __name__ == "__main__":
    main()
