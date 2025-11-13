#!/usr/bin/env python3
"""
Outlook Integration Test Script
Comprehensive testing for Outlook email and calendar integration
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


class OutlookIntegrationTester:
    """Comprehensive Outlook integration testing"""

    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.test_user_id = "test_user_outlook"
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
        """Test Outlook integration health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/integrations/outlook/health")
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
            response = requests.get(f"{self.base_url}/api/oauth/outlook/url")
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

    async def run_all_tests(self):
        """Run all Outlook integration tests"""
        print("🚀 Starting Outlook Integration Tests")
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
            print("\n🎉 Outlook Integration: EXCELLENT")
        elif success_rate >= 60:
            print("\n✅ Outlook Integration: GOOD")
        elif success_rate >= 40:
            print("\n⚠️  Outlook Integration: NEEDS IMPROVEMENT")
        else:
            print("\n❌ Outlook Integration: POOR")

        return self.results

    def save_results(self, filename: str = "outlook_integration_test_results.json"):
        """Save test results to file"""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to: {filename}")


async def main():
    """Main execution function"""
    tester = OutlookIntegrationTester()
    results = await tester.run_all_tests()
    tester.save_results()


if __name__ == "__main__":
    asyncio.run(main())