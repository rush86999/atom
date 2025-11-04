#!/usr/bin/env python3
"""
Focused Asana Integration Activation Test
Tests Asana integration endpoints and OAuth flow setup
"""

import os
import sys
import requests
import json
import logging
from typing import Dict, Any, Optional

# Add backend modules to Python path
backend_path = os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = os.getenv("PYTHON_API_SERVICE_BASE_URL", "http://localhost:8000")
TEST_USER_ID = os.getenv("TEST_USER_ID", "test_user_asana")


class AsanaActivationTest:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results = {}
        self.test_user_id = TEST_USER_ID

    def print_header(self, message: str):
        """Print formatted header"""
        print(f"\n{'=' * 60}")
        print(f"🧪 {message}")
        print(f"{'=' * 60}")

    def print_success(self, message: str):
        """Print success message"""
        print(f"✅ {message}")

    def print_error(self, message: str):
        """Print error message"""
        print(f"❌ {message}")

    def print_info(self, message: str):
        """Print info message"""
        print(f"ℹ️  {message}")

    def test_asana_health_endpoint(self) -> bool:
        """Test Asana health endpoint"""
        self.print_header("Testing Asana Health Endpoint")

        try:
            response = requests.get(f"{self.base_url}/api/asana/health", timeout=10)

            if response.status_code == 200:
                data = response.json()
                self.print_success("Asana health endpoint working!")
                print(f"   Service: {data.get('service', 'unknown')}")
                print(f"   Status: {data.get('status', 'unknown')}")
                print(f"   Message: {data.get('message', 'no message')}")
                print(f"   Needs OAuth: {data.get('needs_oauth', 'unknown')}")
                return True
            else:
                self.print_error(
                    f"Asana health endpoint failed: {response.status_code}"
                )
                print(f"   Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            self.print_error(f"Failed to connect to Asana health endpoint: {e}")
            return False

    def test_asana_oauth_authorization(self) -> bool:
        """Test Asana OAuth authorization endpoint"""
        self.print_header("Testing Asana OAuth Authorization")

        try:
            response = requests.get(
                f"{self.base_url}/api/auth/asana/authorize",
                params={"user_id": self.test_user_id},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                self.print_success("Asana OAuth authorization endpoint working!")
                print(f"   Auth URL: {data.get('auth_url', 'not provided')[:80]}...")
                print(f"   User ID: {data.get('user_id', 'not provided')}")
                print(
                    f"   CSRF Token: {data.get('csrf_token', 'not provided')[:20]}..."
                )
                return True
            else:
                self.print_error(f"OAuth authorization failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            self.print_error(f"Failed to connect to OAuth authorization: {e}")
            return False

    def test_asana_oauth_status(self) -> bool:
        """Test Asana OAuth status endpoint"""
        self.print_header("Testing Asana OAuth Status")

        try:
            response = requests.get(
                f"{self.base_url}/api/auth/asana/status",
                params={"user_id": self.test_user_id},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                self.print_success("Asana OAuth status endpoint working!")
                print(f"   Connected: {data.get('connected', 'unknown')}")
                print(f"   Expired: {data.get('expired', 'unknown')}")
                print(f"   Scopes: {data.get('scopes', [])}")
                print(f"   User ID: {data.get('user_id', 'unknown')}")
                return True
            else:
                self.print_error(f"OAuth status failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            self.print_error(f"Failed to connect to OAuth status: {e}")
            return False

    def test_asana_search_endpoint(self) -> bool:
        """Test Asana search endpoint (requires authentication)"""
        self.print_header("Testing Asana Search Endpoint")

        try:
            response = requests.post(
                f"{self.base_url}/api/asana/search",
                json={
                    "user_id": self.test_user_id,
                    "project_id": "test_project_id",
                    "query": "test query",
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    self.print_success("Asana search endpoint working!")
                    search_data = data.get("data", {})
                    print(f"   Status: {search_data.get('status', 'unknown')}")
                    return True
                else:
                    error_info = data.get("error", {})
                    if error_info.get("code") == "AUTH_ERROR":
                        self.print_info("Search requires authentication (expected)")
                        return True  # This is expected without OAuth setup
                    else:
                        self.print_error(
                            f"Search failed: {error_info.get('message', 'unknown error')}"
                        )
                        return False
            else:
                self.print_error(f"Search endpoint failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            self.print_error(f"Failed to connect to Asana search: {e}")
            return False

    def test_asana_list_tasks_endpoint(self) -> bool:
        """Test Asana list tasks endpoint (requires authentication)"""
        self.print_header("Testing Asana List Tasks Endpoint")

        try:
            response = requests.post(
                f"{self.base_url}/api/asana/list-tasks",
                json={"user_id": self.test_user_id, "project_id": "test_project_id"},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    self.print_success("Asana list tasks endpoint working!")
                    tasks_data = data.get("data", {})
                    print(f"   Status: {tasks_data.get('status', 'unknown')}")
                    return True
                else:
                    error_info = data.get("error", {})
                    if error_info.get("code") == "AUTH_ERROR":
                        self.print_info("List tasks requires authentication (expected)")
                        return True  # This is expected without OAuth setup
                    else:
                        self.print_error(
                            f"List tasks failed: {error_info.get('message', 'unknown error')}"
                        )
                        return False
            else:
                self.print_error(f"List tasks endpoint failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            self.print_error(f"Failed to connect to list tasks: {e}")
            return False

    def test_asana_projects_endpoint(self) -> bool:
        """Test Asana projects endpoint (requires authentication)"""
        self.print_header("Testing Asana Projects Endpoint")

        try:
            response = requests.post(
                f"{self.base_url}/api/asana/projects",
                json={
                    "user_id": self.test_user_id,
                    "workspace_id": "test_workspace_id",
                    "limit": 5,
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    self.print_success("Asana projects endpoint working!")
                    projects_data = data.get("data", {})
                    print(f"   Status: {projects_data.get('status', 'unknown')}")
                    return True
                else:
                    error_info = data.get("error", {})
                    if error_info.get("code") == "AUTH_ERROR":
                        self.print_info(
                            "Projects endpoint requires authentication (expected)"
                        )
                        return True  # This is expected without OAuth setup
                    else:
                        self.print_error(
                            f"Projects failed: {error_info.get('message', 'unknown error')}"
                        )
                        return False
            else:
                self.print_error(f"Projects endpoint failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            self.print_error(f"Failed to connect to Asana projects: {e}")
            return False

    def test_asana_create_task_endpoint(self) -> bool:
        """Test Asana create task endpoint (requires authentication)"""
        self.print_header("Testing Asana Create Task Endpoint")

        try:
            response = requests.post(
                f"{self.base_url}/api/asana/create-task",
                json={
                    "user_id": self.test_user_id,
                    "project_id": "test_project_id",
                    "name": "Test Task from ATOM Integration",
                    "notes": "This is a test task created by the ATOM Asana integration",
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    self.print_success("Asana create task endpoint working!")
                    task_data = data.get("data", {})
                    print(f"   Status: {task_data.get('status', 'unknown')}")
                    return True
                else:
                    error_info = data.get("error", {})
                    if error_info.get("code") == "AUTH_ERROR":
                        self.print_info(
                            "Create task requires authentication (expected)"
                        )
                        return True  # This is expected without OAuth setup
                    else:
                        self.print_error(
                            f"Create task failed: {error_info.get('message', 'unknown error')}"
                        )
                        return False
            else:
                self.print_error(f"Create task endpoint failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            self.print_error(f"Failed to connect to create task: {e}")
            return False

    def test_environment_configuration(self) -> bool:
        """Test environment variable configuration"""
        self.print_header("Testing Environment Configuration")

        required_vars = {
            "ASANA_CLIENT_ID": os.getenv("ASANA_CLIENT_ID"),
            "ASANA_CLIENT_SECRET": os.getenv("ASANA_CLIENT_SECRET"),
            "DATABASE_URL": os.getenv("DATABASE_URL"),
            "PYTHON_API_SERVICE_BASE_URL": os.getenv(
                "PYTHON_API_SERVICE_BASE_URL", BASE_URL
            ),
        }

        all_configured = True
        for var_name, var_value in required_vars.items():
            if var_value:
                self.print_success(f"{var_name}: Configured")
                if var_name in ["ASANA_CLIENT_ID", "ASANA_CLIENT_SECRET"]:
                    # Show partial values for security
                    masked_value = (
                        f"{var_value[:8]}...{var_value[-4:]}"
                        if len(var_value) > 12
                        else "***"
                    )
                    print(f"   Value: {masked_value}")
            else:
                self.print_error(f"{var_name}: Not configured")
                all_configured = False

        return all_configured

    def test_service_imports(self) -> bool:
        """Test that Asana service modules can be imported"""
        self.print_header("Testing Asana Service Imports")

        modules_to_test = [
            "asana_service_real",
            "asana_handler",
            "auth_handler_asana",
            "db_oauth_asana",
        ]

        all_imported = True
        for module_name in modules_to_test:
            try:
                if module_name == "asana_service_real":
                    from asana_service_real import (
                        AsanaServiceReal,
                        get_asana_service_real,
                    )
                elif module_name == "asana_handler":
                    from asana_handler import asana_bp, get_asana_client
                elif module_name == "auth_handler_asana":
                    from auth_handler_asana import auth_asana_bp
                elif module_name == "db_oauth_asana":
                    from db_oauth_asana import (
                        store_tokens,
                        get_tokens,
                        update_tokens,
                        delete_tokens,
                    )

                self.print_success(f"{module_name} imported successfully")
            except ImportError as e:
                self.print_error(f"Failed to import {module_name}: {e}")
                all_imported = False
            except Exception as e:
                self.print_error(f"Error importing {module_name}: {e}")
                all_imported = False

        return all_imported

    def run_all_tests(self) -> Dict[str, bool]:
        """Run all Asana integration tests"""
        self.print_header("🚀 Starting Asana Integration Activation Tests")
        print(f"Base URL: {self.base_url}")
        print(f"Test User ID: {self.test_user_id}")

        tests = [
            ("Environment Configuration", self.test_environment_configuration),
            ("Service Imports", self.test_service_imports),
            ("Health Endpoint", self.test_asana_health_endpoint),
            ("OAuth Authorization", self.test_asana_oauth_authorization),
            ("OAuth Status", self.test_asana_oauth_status),
            ("Search Endpoint", self.test_asana_search_endpoint),
            ("List Tasks Endpoint", self.test_asana_list_tasks_endpoint),
            ("Projects Endpoint", self.test_asana_projects_endpoint),
            ("Create Task Endpoint", self.test_asana_create_task_endpoint),
        ]

        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
            except Exception as e:
                self.print_error(f"Test {test_name} crashed: {e}")
                results[test_name] = False

        return results

    def generate_activation_guide(self, results: Dict[str, bool]):
        """Generate activation guide based on test results"""
        self.print_header("🎯 Asana Integration Activation Guide")

        passed = sum(results.values())
        total = len(results)

        print(f"\n📊 Test Results: {passed}/{total} tests passed")

        if passed == total:
            self.print_success(
                "🎉 All tests passed! Asana integration is ready for OAuth setup."
            )
        else:
            self.print_info("⚠️ Some tests require configuration to pass completely.")

        print(f"\n🔧 Next Steps for Asana Integration:")

        # Check environment configuration
        if not results.get("Environment Configuration", False):
            print("   1. 🔑 Configure environment variables:")
            print("      - Set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET")
            print("      - Configure DATABASE_URL for token storage")
            print("      - Copy from .env.integrations template")

        # Check service imports
        if not results.get("Service Imports", False):
            print("   2. 📦 Fix service import issues:")
            print("      - Check Python path configuration")
            print("      - Verify backend modules are accessible")

        # Check OAuth endpoints
        if not results.get("OAuth Authorization", False):
            print("   3. 🔐 Set up Asana OAuth app:")
            print("      - Create app in Asana Developer Console")
            print(
                "      - Configure redirect URI: http://localhost:8000/api/auth/asana/callback"
            )
            print(
                "      - Request scopes: default, tasks:read, tasks:write, projects:read"
            )

        # Check API endpoints
        if not any(
            [
                results.get("Search Endpoint", False),
                results.get("List Tasks Endpoint", False),
                results.get("Projects Endpoint", False),
                results.get("Create Task Endpoint", False),
            ]
        ):
            print("   4. 🚀 Complete OAuth flow:")
            print("      - User initiates OAuth from ATOM UI")
            print("      - Grant permissions in Asana")
            print("      - Handle callback and store tokens")
            print("      - Test authenticated API calls")

        if passed >= 5:  # Most basic tests passed
            print("   5. 🧪 Test with real Asana account:")
            print("      - Connect actual Asana workspace")
            print("      - Create test tasks and projects")
            print("      - Verify data synchronization")

        print(
            f"\n📋 Activation Status: {'READY' if passed >= 6 else 'CONFIGURATION NEEDED'}"
        )


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description="Test Asana integration activation")
    parser.add_argument("--url", default=BASE_URL, help="Base URL of ATOM backend")
    parser.add_argument("--user", default=TEST_USER_ID, help="Test user ID")

    args = parser.parse_args()

    tester = AsanaActivationTest(base_url=args.url)
    tester.test_user_id = args.user

    results = tester.run_all_tests()
    tester.generate_activation_guide(results)

    # Exit with appropriate code
    passed = sum(results.values())
    total = len(results)

    if passed == total:
        sys.exit(0)  # All tests passed
    elif passed >= 6:
        sys.exit(1)  # Most tests passed, needs configuration
    else:
        sys.exit(2)  # Significant issues


if __name__ == "__main__":
    main()
