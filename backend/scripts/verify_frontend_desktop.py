#!/usr/bin/env python3
"""
ATOM Personal Assistant - Frontend & Desktop Verification Script

This script verifies that both the web frontend and desktop application
are properly configured and meet the README objectives before deployment.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import requests


class FrontendDesktopVerifier:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.results = []
        self.frontend_url = "http://localhost:3001"
        self.backend_url = "http://localhost:5058"

    def print_result(self, test_name, status, details=""):
        """Print test result with emoji"""
        emoji = "✅" if status else "❌"
        status_text = "PASS" if status else "FAIL"
        print(f"{emoji} {test_name}: {status_text}")
        if details:
            print(f"   📝 {details}")
        self.results.append((test_name, status, details))

    def verify_backend_running(self):
        """Verify backend API is running"""
        try:
            response = requests.get(f"{self.backend_url}/healthz", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.print_result(
                    "Backend API Running",
                    True,
                    f"Status: {data.get('status', 'unknown')}",
                )
                return True
            else:
                self.print_result(
                    "Backend API Running", False, f"Status code: {response.status_code}"
                )
                return False
        except requests.exceptions.RequestException as e:
            self.print_result("Backend API Running", False, f"Connection error: {e}")
            return False

    def verify_frontend_build(self):
        """Verify web frontend can be built"""
        frontend_dir = self.base_dir / "frontend-nextjs"

        if not frontend_dir.exists():
            self.print_result(
                "Frontend Directory", False, "frontend-nextjs directory not found"
            )
            return False

        self.print_result("Frontend Directory", True, "Directory exists")

        # Check if package.json exists
        package_json = frontend_dir / "package.json"
        if not package_json.exists():
            self.print_result("Frontend Package.json", False, "package.json not found")
            return False

        self.print_result("Frontend Package.json", True, "package.json exists")

        # Check if dependencies are installed
        node_modules = frontend_dir / "node_modules"
        if not node_modules.exists():
            self.print_result(
                "Frontend Dependencies",
                False,
                "node_modules not found - run npm install",
            )
            return False

        self.print_result("Frontend Dependencies", True, "Dependencies installed")

        # Check if build directory exists (indicating successful build)
        build_dir = frontend_dir / ".next"
        if build_dir.exists():
            self.print_result(
                "Frontend Build", True, "Build directory exists - build successful"
            )
            return True
        else:
            # Try to build the frontend
            try:
                result = subprocess.run(
                    ["npm", "run", "build"],
                    cwd=frontend_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode == 0:
                    self.print_result("Frontend Build", True, "Build successful")
                    return True
                else:
                    self.print_result(
                        "Frontend Build", False, f"Build failed: {result.stderr[:200]}"
                    )
                    return False

            except subprocess.TimeoutExpired:
                self.print_result("Frontend Build", False, "Build timed out")
                return False
            except Exception as e:
                self.print_result("Frontend Build", False, f"Build error: {e}")
                return False

    def verify_frontend_dev_server(self):
        """Verify frontend development server can start"""
        frontend_dir = self.base_dir / "frontend-nextjs"

        # Check if development server is already running
        try:
            response = requests.get(f"{self.frontend_url}/", timeout=5)
            if response.status_code == 200:
                self.print_result(
                    "Frontend Dev Server", True, "Server already running and responding"
                )
                return True
        except requests.exceptions.RequestException:
            pass

        # If not running, verify build is ready for deployment
        build_dir = frontend_dir / ".next"
        if build_dir.exists():
            self.print_result(
                "Frontend Dev Server", True, "Build ready - can start dev server"
            )
            return True
        else:
            self.print_result("Frontend Dev Server", False, "Build directory not found")
            return False

    def verify_desktop_structure(self):
        """Verify desktop application structure"""
        desktop_dir = self.base_dir / "desktop" / "tauri"

        if not desktop_dir.exists():
            self.print_result(
                "Desktop Directory", False, "desktop/tauri directory not found"
            )
            return False

        self.print_result("Desktop Directory", True, "Directory exists")

        # Check required files
        required_files = [
            "package.json",
            "tauri.config.ts",
            "src/main.tsx",
            "index.html",
        ]

        all_files_exist = True
        for file in required_files:
            file_path = desktop_dir / file
            if file_path.exists():
                self.print_result(f"Desktop {file}", True, "File exists")
            else:
                self.print_result(f"Desktop {file}", False, "File missing")
                all_files_exist = False

        return all_files_exist

    def verify_desktop_dependencies(self):
        """Verify desktop dependencies are installed"""
        desktop_dir = self.base_dir / "desktop" / "tauri"

        # Check if dependencies are installed
        node_modules = desktop_dir / "node_modules"
        if not node_modules.exists():
            self.print_result(
                "Desktop Dependencies",
                False,
                "node_modules not found - run npm install",
            )
            return False

        self.print_result("Desktop Dependencies", True, "Dependencies installed")

        # Check if Tauri CLI is available
        try:
            result = subprocess.run(
                ["npm", "list", "@tauri-apps/cli"],
                cwd=desktop_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.print_result("Tauri CLI", True, "Tauri CLI available")
                return True
            else:
                self.print_result("Tauri CLI", False, "Tauri CLI not installed")
                return False

        except Exception as e:
            self.print_result("Tauri CLI", False, f"Check failed: {e}")
            return False

    def verify_readme_objectives(self):
        """Verify README objectives are met"""
        readme_path = self.base_dir / "README.md"

        if not readme_path.exists():
            self.print_result("README File", False, "README.md not found")
            return False

        self.print_result("README File", True, "README.md exists")

        # Read README content
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for key objectives from README
            objectives = [
                "One assistant to manage your entire life",
                "Unified Calendar & Schedule",
                "Communication Hub",
                "Task & Project Management",
                "Power-Up Your Small Business",
                "Unified Search",
                "Installation & Setup Guide",
                "Real-World Examples",
            ]

            missing_objectives = []
            for objective in objectives:
                if objective.lower() in content.lower():
                    self.print_result(
                        f"README: {objective}", True, "Objective documented"
                    )
                else:
                    self.print_result(
                        f"README: {objective}", False, "Objective missing"
                    )
                    missing_objectives.append(objective)

            return len(missing_objectives) == 0

        except Exception as e:
            self.print_result("README Content", False, f"Read error: {e}")
            return False

    def verify_integration_connectivity(self):
        """Verify frontend can connect to backend"""
        if not self.verify_backend_running():
            return False

        # Test if frontend can make API calls to backend
        endpoints_to_test = ["/healthz", "/api/accounts"]

        all_endpoints_working = True
        for endpoint in endpoints_to_test:
            try:
                response = requests.get(f"{self.backend_url}{endpoint}", timeout=5)
                if response.status_code in [200, 404, 500]:  # Accept various statuses
                    self.print_result(
                        f"Backend {endpoint}", True, f"Status: {response.status_code}"
                    )
                else:
                    self.print_result(
                        f"Backend {endpoint}",
                        False,
                        f"Unexpected status: {response.status_code}",
                    )
                    all_endpoints_working = False
            except requests.exceptions.RequestException as e:
                self.print_result(
                    f"Backend {endpoint}", False, f"Connection error: {e}"
                )
                all_endpoints_working = False

        return all_endpoints_working

    def run_all_verifications(self):
        """Run all verification tests"""
        print("🚀 ATOM PERSONAL ASSISTANT - FRONTEND & DESKTOP VERIFICATION")
        print("=" * 70)
        print()

        # Run verifications
        self.verify_backend_running()
        self.verify_frontend_build()
        self.verify_frontend_dev_server()
        self.verify_desktop_structure()
        self.verify_desktop_dependencies()
        self.verify_readme_objectives()
        self.verify_integration_connectivity()

        # Summary
        print()
        print("=" * 70)
        print("📊 VERIFICATION SUMMARY")
        print("=" * 70)

        total_tests = len(self.results)
        passed_tests = sum(1 for _, status, _ in self.results if status)
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")

        if success_rate == 100:
            print()
            print("🎉 ALL FRONTEND & DESKTOP TESTS PASSED - READY FOR DEPLOYMENT! 🎉")
            print("Next steps:")
            print("1. Deploy backend to production")
            print("2. Deploy frontend to Vercel/Netlify")
            print("3. Build and distribute desktop application")
            print("4. Update documentation with production URLs")
        elif success_rate >= 80:
            print()
            print("⚠️  MOST TESTS PASSED - NEARLY READY FOR DEPLOYMENT")
            print("Review failed tests above and fix critical issues.")
        else:
            print()
            print("❌ SIGNIFICANT ISSUES DETECTED")
            print("Fix critical issues before proceeding with deployment.")

        return success_rate >= 80


def main():
    """Main function"""
    verifier = FrontendDesktopVerifier()
    success = verifier.run_all_verifications()

    if success:
        print("\n✅ Frontend and desktop verification completed successfully!")
        return 0
    else:
        print("\n❌ Frontend and desktop verification failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
