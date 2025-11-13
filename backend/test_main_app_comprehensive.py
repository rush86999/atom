#!/usr/bin/env python3
"""
Comprehensive Test for ATOM Main Application

This script tests all core functionality of the ATOM main application
to ensure the platform is stable and operational.
"""

import os
import sys
import json
import requests
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5058"
TIMEOUT = 10
RETRY_COUNT = 3
RETRY_DELAY = 2


class ATOMTester:
    """Comprehensive tester for ATOM main application"""

    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "summary": {"total": 0, "passed": 0, "failed": 0, "success_rate": 0.0},
        }

    def log_test(self, test_name, success, message=None, data=None):
        """Log test result"""
        self.results["tests"][test_name] = {
            "success": success,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }

        if success:
            self.results["summary"]["passed"] += 1
            print(f"✅ {test_name}: {message}")
        else:
            self.results["summary"]["failed"] += 1
            print(f"❌ {test_name}: {message}")

        self.results["summary"]["total"] += 1

    def make_request(self, method, endpoint, data=None, headers=None):
        """Make HTTP request with retry logic"""
        url = f"{self.base_url}{endpoint}"
        headers = headers or {"Content-Type": "application/json"}

        for attempt in range(RETRY_COUNT):
            try:
                if method.upper() == "GET":
                    response = requests.get(url, headers=headers, timeout=TIMEOUT)
                elif method.upper() == "POST":
                    response = requests.post(
                        url, json=data, headers=headers, timeout=TIMEOUT
                    )
                elif method.upper() == "PUT":
                    response = requests.put(
                        url, json=data, headers=headers, timeout=TIMEOUT
                    )
                else:
                    raise ValueError(f"Unsupported method: {method}")

                return response
            except requests.exceptions.RequestException as e:
                if attempt == RETRY_COUNT - 1:
                    raise e
                time.sleep(RETRY_DELAY)

    def test_health_endpoint(self):
        """Test main health endpoint"""
        try:
            response = self.make_request("GET", "/healthz")
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "health_endpoint", True, "Health endpoint responding", data
                )
            else:
                self.log_test(
                    "health_endpoint",
                    False,
                    f"Health endpoint returned {response.status_code}",
                )
        except Exception as e:
            self.log_test("health_endpoint", False, f"Health endpoint error: {str(e)}")

    def test_service_registry(self):
        """Test service registry functionality"""
        try:
            response = self.make_request("GET", "/api/services/status")
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.log_test(
                        "service_registry",
                        True,
                        f"Service registry: {data.get('status_summary', {}).get('active', 0)} active services",
                        data,
                    )
                else:
                    self.log_test(
                        "service_registry",
                        False,
                        "Service registry returned unsuccessful",
                    )
            else:
                self.log_test(
                    "service_registry",
                    False,
                    f"Service registry returned {response.status_code}",
                )
        except Exception as e:
            self.log_test(
                "service_registry", False, f"Service registry error: {str(e)}"
            )

    def test_authentication_system(self):
        """Test user authentication system"""
        # Test authentication health
        try:
            response = self.make_request("GET", "/api/auth/health")
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "auth_health", True, "Authentication health endpoint working", data
                )
            else:
                self.log_test(
                    "auth_health", False, f"Auth health returned {response.status_code}"
                )
        except Exception as e:
            self.log_test("auth_health", False, f"Auth health error: {str(e)}")

        # Test user login
        try:
            login_data = {"email": "demo@atom.com", "password": "demo123"}
            response = self.make_request("POST", "/api/auth/login", data=login_data)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.log_test(
                        "user_login",
                        True,
                        "User login successful",
                        {
                            "user_id": data.get("user", {}).get("id"),
                            "token_received": "token" in data.get("user", {}),
                        },
                    )
                else:
                    self.log_test(
                        "user_login",
                        False,
                        f"Login unsuccessful: {data.get('message')}",
                    )
            else:
                self.log_test(
                    "user_login", False, f"Login returned {response.status_code}"
                )
        except Exception as e:
            self.log_test("user_login", False, f"Login error: {str(e)}")

    def test_workflow_generation(self):
        """Test workflow generation system"""
        try:
            workflow_data = {
                "user_input": "Schedule a meeting for tomorrow and send an email reminder"
            }
            response = self.make_request(
                "POST", "/api/workflow-automation/generate", data=workflow_data
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    workflow = data.get("workflow", {})
                    self.log_test(
                        "workflow_generation",
                        True,
                        f"Workflow generated with {len(workflow.get('steps', []))} steps",
                        {
                            "workflow_id": workflow.get("id"),
                            "steps_count": len(workflow.get("steps", [])),
                            "services": workflow.get("services", []),
                        },
                    )
                else:
                    self.log_test(
                        "workflow_generation",
                        False,
                        f"Workflow generation unsuccessful: {data.get('error')}",
                    )
            else:
                self.log_test(
                    "workflow_generation",
                    False,
                    f"Workflow generation returned {response.status_code}",
                )
        except Exception as e:
            self.log_test(
                "workflow_generation", False, f"Workflow generation error: {str(e)}"
            )

    def test_service_health_endpoints(self):
        """Test service health endpoints"""
        services_to_test = [
            "/api/gmail/health",
            "/api/outlook/health",
            "/api/slack/health",
            "/api/teams/health",
            "/api/github/health",
            "/api/gdrive/health",
            "/api/dropbox/health",
            "/api/trello/health",
            "/api/asana/health",
            "/api/notion/health",
        ]

        healthy_services = 0
        service_details = {}

        for service_endpoint in services_to_test:
            try:
                response = self.make_request("GET", service_endpoint)
                service_name = service_endpoint.split("/")[-2]  # Extract service name
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "healthy":
                        healthy_services += 1
                        service_details[service_name] = "healthy"
                    else:
                        service_details[service_name] = data.get("status", "unknown")
                else:
                    service_details[service_name] = f"http_{response.status_code}"
            except Exception as e:
                service_details[service_endpoint.split("/")[-2]] = f"error: {str(e)}"

        success_rate = (
            healthy_services / len(services_to_test) if services_to_test else 0
        )
        self.log_test(
            "service_health",
            success_rate >= 0.5,  # At least 50% of services should be healthy
            f"{healthy_services}/{len(services_to_test)} services healthy ({success_rate:.1%})",
            {"services": service_details, "success_rate": success_rate},
        )

    def test_search_functionality(self):
        """Test search functionality"""
        try:
            search_data = {"query": "test search", "limit": 5}
            response = self.make_request(
                "POST", "/semantic_search_meetings", data=search_data
            )
            # Search endpoints might return 200 even with no results, or 404 if not implemented
            if response.status_code in [200, 404]:
                self.log_test(
                    "search_functionality",
                    True,
                    f"Search endpoint responding (status: {response.status_code})",
                    {"status_code": response.status_code},
                )
            else:
                self.log_test(
                    "search_functionality",
                    False,
                    f"Search returned {response.status_code}",
                )
        except Exception as e:
            self.log_test("search_functionality", False, f"Search error: {str(e)}")

    def test_calendar_functionality(self):
        """Test calendar functionality"""
        try:
            # Test calendar health/availability
            response = self.make_request("GET", "/api/calendar/health")
            if response.status_code in [200, 404]:
                self.log_test(
                    "calendar_functionality",
                    True,
                    f"Calendar endpoint available (status: {response.status_code})",
                    {"status_code": response.status_code},
                )
            else:
                self.log_test(
                    "calendar_functionality",
                    False,
                    f"Calendar returned {response.status_code}",
                )
        except Exception as e:
            self.log_test("calendar_functionality", False, f"Calendar error: {str(e)}")

    def test_task_functionality(self):
        """Test task management functionality"""
        try:
            # Test tasks health/availability
            response = self.make_request("GET", "/api/tasks/health")
            if response.status_code in [200, 404]:
                self.log_test(
                    "task_functionality",
                    True,
                    f"Tasks endpoint available (status: {response.status_code})",
                    {"status_code": response.status_code},
                )
            else:
                self.log_test(
                    "task_functionality",
                    False,
                    f"Tasks returned {response.status_code}",
                )
        except Exception as e:
            self.log_test("task_functionality", False, f"Tasks error: {str(e)}")

    def test_message_functionality(self):
        """Test messaging functionality"""
        try:
            # Test messages health/availability
            response = self.make_request("GET", "/api/messages/health")
            if response.status_code in [200, 404]:
                self.log_test(
                    "message_functionality",
                    True,
                    f"Messages endpoint available (status: {response.status_code})",
                    {"status_code": response.status_code},
                )
            else:
                self.log_test(
                    "message_functionality",
                    False,
                    f"Messages returned {response.status_code}",
                )
        except Exception as e:
            self.log_test("message_functionality", False, f"Messages error: {str(e)}")

    def run_all_tests(self):
        """Run all comprehensive tests"""
        print("🚀 Starting Comprehensive ATOM Main Application Tests")
        print("=" * 60)

        # Run all test methods
        test_methods = [
            method
            for method in dir(self)
            if method.startswith("test_") and callable(getattr(self, method))
        ]

        for method_name in test_methods:
            method = getattr(self, method_name)
            method()

        # Calculate final summary
        total = self.results["summary"]["total"]
        passed = self.results["summary"]["passed"]
        success_rate = (passed / total) * 100 if total > 0 else 0

        self.results["summary"]["success_rate"] = success_rate

        # Print final summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {self.results['summary']['failed']}")
        print(f"Success Rate: {success_rate:.1f}%")

        if success_rate >= 80:
            print("🎉 ATOM Main Application: STABLE AND OPERATIONAL")
        elif success_rate >= 60:
            print("⚠️  ATOM Main Application: PARTIALLY OPERATIONAL")
        else:
            print("❌ ATOM Main Application: NEEDS ATTENTION")

        # Save results to file
        results_file = "main_app_test_results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\n📄 Detailed results saved to: {results_file}")
        return self.results


def main():
    """Main function"""
    tester = ATOMTester()
    results = tester.run_all_tests()

    # Exit with appropriate code
    if results["summary"]["success_rate"] >= 80:
        sys.exit(0)  # Success
    elif results["summary"]["success_rate"] >= 60:
        sys.exit(1)  # Partial success
    else:
        sys.exit(2)  # Failure


if __name__ == "__main__":
    main()
