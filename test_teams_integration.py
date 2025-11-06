#!/usr/bin/env python3
"""
Microsoft Teams Integration Test Script
Comprehensive testing for Teams communication integration
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


class TeamsIntegrationTester:
    """Comprehensive Teams integration testing"""

    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.test_user_id = "test_user_teams"
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
        """Test Teams integration health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/integrations/teams/health")
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

    async def test_oauth_endpoints(self):
        """Test OAuth URL generation"""
        try:
            response = requests.get(f"{self.base_url}/api/oauth/teams/url")
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

    async def test_teams_listing(self):
        """Test Teams listing"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "operation": "list",
                "max_results": 5,
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/teams/teams", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                teams = data.get("data", {}).get("teams", [])
                self.log_test(
                    "Teams Listing",
                    True,
                    {
                        "teams_count": len(teams),
                        "operation": payload["operation"],
                    },
                )
            else:
                self.log_test(
                    "Teams Listing",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Teams Listing", False, {"error": str(e)})

    async def test_channels_listing(self):
        """Test Teams channels listing"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "operation": "list",
                "team_id": "team_001",
                "max_results": 5,
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/teams/channels", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                channels = data.get("data", {}).get("channels", [])
                self.log_test(
                    "Channels Listing",
                    True,
                    {
                        "channels_count": len(channels),
                        "team_id": payload["team_id"],
                    },
                )
            else:
                self.log_test(
                    "Channels Listing",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Channels Listing", False, {"error": str(e)})

    async def test_messages_listing(self):
        """Test Teams messages listing"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "operation": "list",
                "channel_id": "channel_001",
                "max_results": 5,
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/teams/messages", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                messages = data.get("data", {}).get("messages", [])
                self.log_test(
                    "Messages Listing",
                    True,
                    {
                        "messages_count": len(messages),
                        "channel_id": payload["channel_id"],
                    },
                )
            else:
                self.log_test(
                    "Messages Listing",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Messages Listing", False, {"error": str(e)})

    async def test_meetings_listing(self):
        """Test Teams meetings listing"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "operation": "list",
                "max_results": 5,
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/teams/meetings", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                meetings = data.get("data", {}).get("meetings", [])
                self.log_test(
                    "Meetings Listing",
                    True,
                    {
                        "meetings_count": len(meetings),
                        "operation": payload["operation"],
                    },
                )
            else:
                self.log_test(
                    "Meetings Listing",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Meetings Listing", False, {"error": str(e)})

    async def test_user_profile(self):
        """Test Teams user profile"""
        try:
            payload = {"user_id": self.test_user_id}

            response = requests.post(
                f"{self.base_url}/api/integrations/teams/user/profile", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                user_info = data.get("data", {}).get("user", {})
                teams = data.get("data", {}).get("teams", [])
                self.log_test(
                    "User Profile",
                    True,
                    {
                        "user_name": user_info.get("displayName"),
                        "user_email": user_info.get("mail"),
                        "teams_count": len(teams),
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

    async def run_all_tests(self):
        """Run all Teams integration tests"""
        print("🚀 Starting Microsoft Teams Integration Tests")
        print("=" * 50)

        # Check if backend is running
        try:
            health_response = requests.get(f"{self.base_url}/health", timeout=5)
            if health_response.status_code != 200:
                print("❌ Backend server is not running")
                print("Please start backend server first:")
                print("  cd backend/python-api-service && python minimal_api_app.py")
                return self.results
        except Exception as e:
            print(f"❌ Backend server is not accessible: {e}")
            print("Please start backend server first:")
            print("  cd backend/python-api-service && python minimal_api_app.py")
            return self.results

        print("✅ Backend server is running")

        # Run tests
        await self.test_health_endpoint()
        await self.test_oauth_endpoints()
        await self.test_teams_listing()
        await self.test_channels_listing()
        await self.test_messages_listing()
        await self.test_meetings_listing()
        await self.test_user_profile()

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
            print("\n🎉 Teams Integration: EXCELLENT")
        elif success_rate >= 60:
            print("\n✅ Teams Integration: GOOD")
        elif success_rate >= 40:
            print("\n⚠️  Teams Integration: NEEDS IMPROVEMENT")
        else:
            print("\n❌ Teams Integration: POOR")

        return self.results

    def save_results(self, filename: str = "teams_integration_test_results.json"):
        """Save test results to file"""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to: {filename}")


async def main():
    """Main execution function"""
    tester = TeamsIntegrationTester()
    results = await tester.run_all_tests()
    tester.save_results()


if __name__ == "__main__":
    asyncio.run(main())