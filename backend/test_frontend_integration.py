#!/usr/bin/env python3
"""
Frontend Integration Test Script
Test frontend accessibility and key UI endpoints
"""

import os
import sys
import requests
from datetime import datetime
from typing import Dict, Any

class FrontendIntegrationTester:
    """Frontend accessibility testing"""

    def __init__(self):
        self.base_url = "http://localhost:3000"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "summary": {"total": 0, "passed": 0, "failed": 0, "success_rate": 0.0},
        }

    def log_test(self, test_name: str, success: bool, details: Dict[str, Any] = None):
        """Log test result"""
        self.results["summary"]["total"] += 1
        if success:
            self.results["summary"]["passed"] += 1
            status = "✅ PASSED"
        else:
            self.results["summary"]["failed"] += 1
            status = "❌ FAILED"

        self.results["tests"][test_name] = {
            "status": "passed" if success else "failed",
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }

        print(f"{status} {test_name}")
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")

    def test_homepage(self):
        """Test main homepage accessibility"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200:
                content_length = len(response.content)
                self.log_test(
                    "Homepage Accessibility",
                    True,
                    {
                        "status_code": response.status_code,
                        "content_length": content_length,
                        "response_time": response.elapsed.total_seconds(),
                    },
                )
            else:
                self.log_test(
                    "Homepage Accessibility",
                    False,
                    {"status_code": response.status_code, "error": response.text[:100]},
                )
        except Exception as e:
            self.log_test("Homepage Accessibility", False, {"error": str(e)})

    def test_search_ui(self):
        """Test search UI endpoint"""
        try:
            response = requests.get(f"{self.base_url}/search", timeout=5)
            if response.status_code == 200:
                self.log_test(
                    "Search UI",
                    True,
                    {
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                    },
                )
            else:
                self.log_test(
                    "Search UI",
                    False,
                    {"status_code": response.status_code, "error": response.text[:100]},
                )
        except Exception as e:
            self.log_test("Search UI", False, {"error": str(e)})

    def test_communication_ui(self):
        """Test communication UI endpoint"""
        try:
            response = requests.get(f"{self.base_url}/communication", timeout=5)
            if response.status_code == 200:
                self.log_test(
                    "Communication UI",
                    True,
                    {
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                    },
                )
            else:
                self.log_test(
                    "Communication UI",
                    False,
                    {"status_code": response.status_code, "error": response.text[:100]},
                )
        except Exception as e:
            self.log_test("Communication UI", False, {"error": str(e)})

    def test_tasks_ui(self):
        """Test tasks UI endpoint"""
        try:
            response = requests.get(f"{self.base_url}/tasks", timeout=5)
            if response.status_code == 200:
                self.log_test(
                    "Tasks UI",
                    True,
                    {
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                    },
                )
            else:
                self.log_test(
                    "Tasks UI",
                    False,
                    {"status_code": response.status_code, "error": response.text[:100]},
                )
        except Exception as e:
            self.log_test("Tasks UI", False, {"error": str(e)})

    def test_automations_ui(self):
        """Test workflow automation UI endpoint"""
        try:
            response = requests.get(f"{self.base_url}/automations", timeout=5)
            if response.status_code == 200:
                self.log_test(
                    "Automations UI",
                    True,
                    {
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                    },
                )
            else:
                self.log_test(
                    "Automations UI",
                    False,
                    {"status_code": response.status_code, "error": response.text[:100]},
                )
        except Exception as e:
            self.log_test("Automations UI", False, {"error": str(e)})

    def test_calendar_ui(self):
        """Test calendar/scheduling UI endpoint"""
        try:
            response = requests.get(f"{self.base_url}/calendar", timeout=5)
            if response.status_code == 200:
                self.log_test(
                    "Calendar UI",
                    True,
                    {
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                    },
                )
            else:
                self.log_test(
                    "Calendar UI",
                    False,
                    {"status_code": response.status_code, "error": response.text[:100]},
                )
        except Exception as e:
            self.log_test("Calendar UI", False, {"error": str(e)})

    def test_integrations_ui(self):
        """Test integrations management UI endpoint"""
        try:
            response = requests.get(f"{self.base_url}/integrations", timeout=5)
            if response.status_code == 200:
                self.log_test(
                    "Integrations UI",
                    True,
                    {
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                    },
                )
            else:
                self.log_test(
                    "Integrations UI",
                    False,
                    {"status_code": response.status_code, "error": response.text[:100]},
                )
        except Exception as e:
            self.log_test("Integrations UI", False, {"error": str(e)})

    def run_all_tests(self):
        """Run all frontend accessibility tests"""
        print("🚀 Starting Frontend Integration Tests")
        print("=" * 50)

        # Quick connectivity test first
        print("🔍 Testing basic connectivity...")
        try:
            test_response = requests.get(f"{self.base_url}/", timeout=2)
            print(f"✅ Server responding (status: {test_response.status_code})")
        except Exception as e:
            print(f"❌ Frontend server not accessible: {e}")
            print("💡 Try starting frontend with: cd frontend-nextjs && npm run dev")
            return self.results

        # Run individual tests with reduced timeout
        self.test_homepage()
        self.test_search_ui()
        self.test_communication_ui()
        self.test_tasks_ui()
        self.test_automations_ui()
        self.test_calendar_ui()
        self.test_integrations_ui()

        # Calculate summary
        total = self.results["summary"]["total"]
        passed = self.results["summary"]["passed"]
        success_rate = (passed / total * 100) if total > 0 else 0

        self.results["summary"]["success_rate"] = success_rate

        # Print summary
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {self.results['summary']['failed']}")
        print(f"Success Rate: {success_rate:.1f}%")

        if success_rate >= 80:
            print("\n🎉 Frontend Integration: EXCELLENT")
        elif success_rate >= 60:
            print("\n✅ Frontend Integration: GOOD")
        elif success_rate >= 40:
            print("\n⚠️  Frontend Integration: NEEDS IMPROVEMENT")
        else:
            print("\n❌ Frontend Integration: POOR")

        return self.results

    def save_results(self, filename: str = "frontend_integration_test_results.json"):
        """Save test results to file"""
        import json
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to: {filename}")


def main():
    """Main execution function"""
    tester = FrontendIntegrationTester()
    results = tester.run_all_tests()
    tester.save_results()


if __name__ == "__main__":
    main()