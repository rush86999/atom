#!/usr/bin/env python3
"""
Notion Integration Test Script
Comprehensive testing for Notion database and document integration
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


class NotionIntegrationTester:
    """Comprehensive Notion integration testing"""

    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.test_user_id = "test_user_notion"
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
        """Test Notion integration health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/integrations/notion/health")
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
            response = requests.get(f"{self.base_url}/api/oauth/notion/url")
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

    async def test_pages_listing(self):
        """Test Notion pages listing"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "operation": "list",
                "max_results": 5,
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/notion/pages", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                pages = data.get("data", {}).get("pages", [])
                self.log_test(
                    "Pages Listing",
                    True,
                    {
                        "pages_count": len(pages),
                        "operation": payload["operation"],
                    },
                )
            else:
                self.log_test(
                    "Pages Listing",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Pages Listing", False, {"error": str(e)})

    async def test_databases_listing(self):
        """Test Notion databases listing"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "operation": "list",
                "max_results": 5,
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/notion/databases", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                databases = data.get("data", {}).get("databases", [])
                self.log_test(
                    "Databases Listing",
                    True,
                    {
                        "databases_count": len(databases),
                        "operation": payload["operation"],
                    },
                )
            else:
                self.log_test(
                    "Databases Listing",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Databases Listing", False, {"error": str(e)})

    async def test_page_creation(self):
        """Test Notion page creation"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "operation": "create",
                "data": {
                    "parent": {"database_id": "test_db_001"},
                    "properties": {
                        "title": {
                            "title": [
                                {"text": {"content": "Test Page from ATOM Integration"}}
                            ]
                        }
                    },
                    "children": [
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [
                                    {"type": "text", "text": {"content": "This is a test page created by ATOM integration testing."}}
                                ]
                            }
                        }
                    ]
                },
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/notion/pages", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                page = data.get("data", {}).get("page", {})
                self.log_test(
                    "Page Creation",
                    True,
                    {
                        "page_id": page.get("id"),
                        "page_title": "Test Page from ATOM Integration",
                    },
                )
            else:
                self.log_test(
                    "Page Creation",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Page Creation", False, {"error": str(e)})

    async def test_search_functionality(self):
        """Test Notion search functionality"""
        try:
            payload = {
                "user_id": self.test_user_id,
                "query": "test",
                "max_results": 5,
            }

            response = requests.post(
                f"{self.base_url}/api/integrations/notion/search", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("data", {}).get("results", [])
                self.log_test(
                    "Search Functionality",
                    True,
                    {
                        "results_count": len(results),
                        "query": payload["query"],
                    },
                )
            else:
                self.log_test(
                    "Search Functionality",
                    False,
                    {"status_code": response.status_code, "error": response.text},
                )
        except Exception as e:
            self.log_test("Search Functionality", False, {"error": str(e)})

    async def test_user_profile(self):
        """Test Notion user profile"""
        try:
            payload = {"user_id": self.test_user_id}

            response = requests.post(
                f"{self.base_url}/api/integrations/notion/user/profile", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                user_info = data.get("data", {}).get("user", {})
                workspaces = data.get("data", {}).get("workspaces", [])
                self.log_test(
                    "User Profile",
                    True,
                    {
                        "user_name": user_info.get("name"),
                        "user_email": user_info.get("email"),
                        "workspaces_count": len(workspaces),
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
        """Run all Notion integration tests"""
        print("🚀 Starting Notion Integration Tests")
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
        await self.test_pages_listing()
        await self.test_databases_listing()
        await self.test_page_creation()
        await self.test_search_functionality()
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
            print("\n🎉 Notion Integration: EXCELLENT")
        elif success_rate >= 60:
            print("\n✅ Notion Integration: GOOD")
        elif success_rate >= 40:
            print("\n⚠️  Notion Integration: NEEDS IMPROVEMENT")
        else:
            print("\n❌ Notion Integration: POOR")

        return self.results

    def save_results(self, filename: str = "notion_integration_test_results.json"):
        """Save test results to file"""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to: {filename}")


async def main():
    """Main execution function"""
    tester = NotionIntegrationTester()
    results = await tester.run_all_tests()
    tester.save_results()


if __name__ == "__main__":
    asyncio.run(main())