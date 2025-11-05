#!/usr/bin/env python3
"""
Google Integration Test Script
Comprehensive testing for Google Suite integration (Gmail, Calendar, Drive)
"""

import os
import sys
import json
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class GoogleIntegrationTester:
    """Comprehensive Google integration testing"""

    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.test_user_id = "test_user_google"
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

    async def test_health_endpoint(self):
        """Test Google integration health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/integrations/google/health")
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Health Check",
                    True,
                    {
                        "status": data.get("status"),
                        "service_available": data.get("service_available"),
                        "database_available": data.get("database_available"),
                    },
                )
            else:
                self.log_test(
                    "Health Check",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Health Check", False, {"error": str(e)})

    async def test_gmail_messages(self):
        """Test Gmail message listing"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "query": "test",
                "max_results": 5,
                "operation": "list",
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/google/gmail/messages", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                messages = data.get("data", {}).get("messages", [])
                self.log_test(
                    "Gmail Messages",
                    True,
                    {
                        "messages_count": len(messages),
                        "query": payload["query"],
                        "max_results": payload["max_results"],
                    },
                )
            else:
                self.log_test(
                    "Gmail Messages",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Gmail Messages", False, {"error": str(e)})

    async def test_calendar_events(self):
        """Test Calendar event listing"""
        try:
            time_min = datetime.utcnow().isoformat() + "Z"
            time_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

            payload = {
                "user_id": self.test_user_id,
                "time_min": time_min,
                "time_max": time_max,
                "max_results": 5,
                "operation": "list",
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/google/calendar/events", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                events = data.get("data", {}).get("events", [])
                self.log_test(
                    "Calendar Events",
                    True,
                    {
                        "events_count": len(events),
                        "time_range": f"{time_min} to {time_max}",
                    },
                )
            else:
                self.log_test(
                    "Calendar Events",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Calendar Events", False, {"error": str(e)})

    async def test_drive_files(self):
        """Test Drive file listing"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "q": "test",
                "page_size": 5,
                "operation": "list",
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/google/drive/files", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                files = data.get("data", {}).get("files", [])
                self.log_test(
                    "Drive Files",
                    True,
                    {
                        "files_count": len(files),
                        "query": payload["q"],
                        "page_size": payload["page_size"],
                    },
                )
            else:
                self.log_test(
                    "Drive Files",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Drive Files", False, {"error": str(e)})

    async def test_google_search(self):
        """Test cross-service Google search"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "query": "project",
                "services": ["gmail", "drive", "calendar"],
                "max_results": 10,
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/google/search", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("data", {}).get("results", [])
                self.log_test(
                    "Google Search",
                    True,
                    {
                        "results_count": len(results),
                        "query": payload["query"],
                        "services": payload["services"],
                    },
                )
            else:
                self.log_test(
                    "Google Search",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Google Search", False, {"error": str(e)})

    async def test_user_profile(self):
        """Test user profile retrieval"""
        try:
            payload = {"user_id": self.test_user_id}

            response = requests.post(
                f"{self.base_url}/api/integrations/google/user/profile", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                user_info = data.get("data", {}).get("user", {})
                services = data.get("data", {}).get("services", {})
                self.log_test(
                    "User Profile",
                    True,
                    {
                        "user_email": user_info.get("email"),
                        "services_connected": len(services),
                    },
                )
            else:
                self.log_test(
                    "User Profile",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("User Profile", False, {"error": str(e)})

    async def test_oauth_endpoints(self):
        """Test OAuth URL generation"""
        try:
            response = requests.get(f"{self.base_url}/api/oauth/google/url")
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "OAuth URL",
                    True,
                    {
                        "oauth_url": data.get("oauth_url"),
                        "service": data.get("service"),
                    },
                )
            else:
                self.log_test(
                    "OAuth URL",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("OAuth URL", False, {"error": str(e)})

    async def test_mock_operations(self):
        """Test mock operations (create, update, delete)"""
        try:
            # Test creating a mock calendar event
            event_payload = {
                "user_id": self.test_user_id,
                "operation": "create",
                "data": {
                    "summary": "Test Meeting",
                    "description": "This is a test event created by integration test",
                    "start": {
                        "dateTime": (datetime.utcnow() + timedelta(hours=1)).isoformat()
                        + "Z",
                        "timeZone": "UTC",
                    },
                    "end": {
                        "dateTime": (datetime.utcnow() + timedelta(hours=2)).isoformat()
                        + "Z",
                        "timeZone": "UTC",
                    },
                },
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/google/calendar/events",
                json=event_payload,
            )

            if response.status_code == 200:
                data = response.json()
                event = data.get("data", {}).get("event", {})
                self.log_test(
                    "Mock Event Creation",
                    True,
                    {"event_id": event.get("id"), "summary": event.get("summary")},
                )
            else:
                self.log_test(
                    "Mock Event Creation",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Mock Event Creation", False, {"error": str(e)})

    async def run_all_tests(self):
        """Run all Google integration tests"""
        print("🚀 Starting Google Integration Tests")
        print("=" * 50)

        # Check if backend is running
        try:
            health_response = requests.get(f"{self.base_url}/health", timeout=5)
            if health_response.status_code != 200:
                print("❌ Backend server is not running")
                print("Please start the backend server first:")
                print("  cd backend/python-api-service && python main_api_app.py")
                return self.results
        except:
            print("❌ Backend server is not accessible")
            print("Please start the backend server first:")
            print("  cd backend/python-api-service && python main_api_app.py")
            return self.results

        print("✅ Backend server is running")

        # Run tests
        await self.test_health_endpoint()
        await self.test_oauth_endpoints()
        await self.test_gmail_messages()
        await self.test_calendar_events()
        await self.test_drive_files()
        await self.test_google_search()
        await self.test_user_profile()
        await self.test_mock_operations()

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
            print("\n🎉 Google Integration: EXCELLENT")
        elif success_rate >= 60:
            print("\n✅ Google Integration: GOOD")
        elif success_rate >= 40:
            print("\n⚠️  Google Integration: NEEDS IMPROVEMENT")
        else:
            print("\n❌ Google Integration: POOR")

        return self.results

    def save_results(self, filename: str = "google_integration_test_results.json"):
        """Save test results to file"""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to: {filename}")


async def main():
    """Main execution function"""
    tester = GoogleIntegrationTester()
    results = await tester.run_all_tests()
    tester.save_results()


if __name__ == "__main__":
    asyncio.run(main())
