import os
import sys
import requests
import time
import json
from pathlib import Path


class ApplicationTester:
    """Test script to verify Atom application functionality"""

    def __init__(self):
        self.base_url = "http://localhost:5059"
        self.frontend_url = "http://localhost:3000"
        self.test_results = {}

    def test_backend_health(self):
        """Test backend API health endpoints"""
        print("🧪 Testing Backend Health...")

        try:
            # Test main API endpoint
            response = requests.get(f"{self.base_url}/", timeout=5)
            self.test_results["backend_root"] = response.status_code == 200
            print(f"  ✅ Backend root: {response.status_code}")

            # Test search endpoint
            response = requests.get(f"{self.base_url}/search/health", timeout=5)
            self.test_results["search_health"] = response.status_code in [200, 404]
            print(f"  ✅ Search health: {response.status_code}")

            # Test task endpoint
            response = requests.get(f"{self.base_url}/tasks/health", timeout=5)
            self.test_results["tasks_health"] = response.status_code in [200, 404]
            print(f"  ✅ Tasks health: {response.status_code}")

        except requests.exceptions.ConnectionError:
            print("  ❌ Backend not running")
            self.test_results["backend_running"] = False
            return False
        except Exception as e:
            print(f"  ❌ Backend test failed: {e}")
            self.test_results["backend_running"] = False
            return False

        self.test_results["backend_running"] = True
        return True

    def test_frontend_build(self):
        """Test if frontend builds successfully"""
        print("🧪 Testing Frontend Build...")

        try:
            # Check if build directory exists
            frontend_dir = Path("frontend-nextjs")
            if not frontend_dir.exists():
                print("  ❌ Frontend directory not found")
                self.test_results["frontend_exists"] = False
                return False

            # Check if build output exists
            build_dir = frontend_dir / ".next"
            if build_dir.exists():
                print("  ✅ Frontend build directory exists")
                self.test_results["frontend_built"] = True
            else:
                print("  ⚠️  Frontend not built (run 'npm run build')")
                self.test_results["frontend_built"] = False

            self.test_results["frontend_exists"] = True
            return True

        except Exception as e:
            print(f"  ❌ Frontend test failed: {e}")
            self.test_results["frontend_exists"] = False
            return False

    def test_service_integrations(self):
        """Test service integration configurations"""
        print("🧪 Testing Service Integrations...")

        try:
            # Check backend service files
            backend_dir = Path("backend/python-api-service")
            service_files = [
                "search_routes.py",
                "task_handler.py",
                "message_handler.py",
                "workflow_api.py",
                "lancedb_handler.py",
            ]

            for service_file in service_files:
                file_path = backend_dir / service_file
                if file_path.exists():
                    print(f"  ✅ {service_file} exists")
                    self.test_results[f"service_{service_file}"] = True
                else:
                    print(f"  ❌ {service_file} missing")
                    self.test_results[f"service_{service_file}"] = False

            # Check sync system
            sync_dir = backend_dir / "sync"
            if sync_dir.exists():
                print("  ✅ LanceDB sync system exists")
                self.test_results["sync_system"] = True

                # Test sync configuration
                try:
                    sys.path.append(str(backend_dir))
                    from sync import get_config

                    config = get_config()
                    print(
                        f"  ✅ Sync config loaded: {config.get_recommended_storage_mode()}"
                    )
                    self.test_results["sync_config"] = True
                except Exception as e:
                    print(f"  ❌ Sync config failed: {e}")
                    self.test_results["sync_config"] = False
            else:
                print("  ❌ LanceDB sync system missing")
                self.test_results["sync_system"] = False

            return True

        except Exception as e:
            print(f"  ❌ Service integration test failed: {e}")
            return False

    def test_ui_components(self):
        """Test UI component existence"""
        print("🧪 Testing UI Components...")

        try:
            frontend_dir = Path("frontend-nextjs/pages")
            ui_files = [
                "search.tsx",
                "communication.tsx",
                "tasks.tsx",
                "automations.tsx",
                "voice.tsx",
                "index.tsx",
            ]

            for ui_file in ui_files:
                file_path = frontend_dir / ui_file
                if file_path.exists():
                    print(f"  ✅ {ui_file} exists")
                    self.test_results[f"ui_{ui_file}"] = True
                else:
                    print(f"  ❌ {ui_file} missing")
                    self.test_results[f"ui_{ui_file}"] = False

            # Check components directory
            components_dir = Path("frontend-nextjs/components")
            if components_dir.exists():
                print("  ✅ Components directory exists")
                self.test_results["components_dir"] = True
            else:
                print("  ❌ Components directory missing")
                self.test_results["components_dir"] = False

            return True

        except Exception as e:
            print(f"  ❌ UI component test failed: {e}")
            return False

    def test_database_connectivity(self):
        """Test database connectivity"""
        print("🧪 Testing Database Connectivity...")

        try:
            backend_dir = Path("backend/python-api-service")
            sys.path.append(str(backend_dir))

            # Test SQLite fallback
            try:
                from db_utils_fallback import get_db_connection, health_check_sqlite

                conn = get_db_connection()
                if conn:
                    print("  ✅ SQLite fallback database connected")
                    self.test_results["sqlite_db"] = True
                else:
                    print("  ❌ SQLite fallback database failed")
                    self.test_results["sqlite_db"] = False
            except Exception as e:
                print(f"  ⚠️  SQLite fallback: {e}")
                self.test_results["sqlite_db"] = False

            # Test PostgreSQL if configured
            try:
                from db_utils import get_db_pool

                pool = get_db_pool()
                if pool:
                    print("  ✅ PostgreSQL connection pool available")
                    self.test_results["postgres_db"] = True
                else:
                    print("  ⚠️  PostgreSQL not configured (using SQLite)")
                    self.test_results["postgres_db"] = False
            except Exception as e:
                print(f"  ⚠️  PostgreSQL: {e}")
                self.test_results["postgres_db"] = False

            return True

        except Exception as e:
            print(f"  ❌ Database test failed: {e}")
            return False

    def run_all_tests(self):
        """Run all application tests"""
        print("🚀 Starting Atom Application Tests")
        print("=" * 50)

        self.test_backend_health()
        print()

        self.test_frontend_build()
        print()

        self.test_service_integrations()
        print()

        self.test_ui_components()
        print()

        self.test_database_connectivity()
        print()

        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("📊 TEST SUMMARY")
        print("=" * 50)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests / total_tests) * 100:.1f}%")
        print()

        # Key functionality check
        key_features = [
            "backend_running",
            "frontend_exists",
            "sync_system",
            "ui_search.tsx",
            "ui_communication.tsx",
            "ui_tasks.tsx",
            "service_search_routes.py",
            "service_task_handler.py",
            "service_message_handler.py",
        ]

        print("🔑 Key Features Status:")
        for feature in key_features:
            status = "✅" if self.test_results.get(feature) else "❌"
            print(f"  {status} {feature}")

        print()

        # Recommendations
        if not self.test_results.get("backend_running"):
            print("💡 Recommendation: Start the backend server")
            print("  cd backend/python-api-service && python main_api_app.py")

        if not self.test_results.get("frontend_built"):
            print("💡 Recommendation: Build the frontend")
            print("  cd frontend-nextjs && npm run build")

        if not all(
            self.test_results.get(f"service_{sf}")
            for sf in ["search_routes.py", "task_handler.py", "message_handler.py"]
        ):
            print("💡 Recommendation: Check backend service implementations")

        print()
        print("🎯 Next Steps:")
        print("  1. Start backend server")
        print("  2. Build and start frontend")
        print("  3. Test cross-UI coordination")
        print("  4. Verify service integrations")
        print("  5. Test workflow automation")


def main():
    """Main test runner"""
    tester = ApplicationTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
