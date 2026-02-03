#!/usr/bin/env python3
"""
Comprehensive Integration Test for Atom API

This script tests the complete integration between frontend and backend services
to ensure all components are working together properly.
"""

import json
import sys
import time
from typing import Any, Dict, List
import requests


class AtomIntegrationTest:
    """Comprehensive integration test suite for Atom API"""

    def __init__(self, base_url: str = "http://localhost:5058", frontend_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.frontend_url = frontend_url
        self.test_api_keys = {
            "X-OpenAI-API-Key": "sk-test-openai-key-12345678901234567890",
            "X-Google-Client-ID": "google-client-id-12345678901234567890",
            "X-Google-Client-Secret": "google-client-secret-12345678901234567890",
            "X-Notion-API-Token": "notion-token-12345678901234567890",
            "X-Dropbox-Access-Token": "dropbox-token-12345678901234567890"
        }

    def test_health_check(self) -> bool:
        """Test health check endpoint"""
        print("🧪 Testing health check...")
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check: {data['status']}")
                print(f"   Database: {data['database']}")
                print(f"   Real services: {data['real_services']}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

    def test_dashboard_endpoint(self) -> bool:
        """Test dashboard endpoint with API keys"""
        print("🧪 Testing dashboard endpoint...")
        try:
            headers = {**self.test_api_keys, "Content-Type": "application/json"}
            response = requests.get(
                f"{self.base_url}/api/dashboard?user_id=test_user",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Dashboard: {len(data['calendar'])} calendar events")
                print(f"   Tasks: {len(data['tasks'])}")
                print(f"   Messages: {len(data['messages'])}")
                print(f"   Stats: {data['stats']}")
                return True
            else:
                print(f"❌ Dashboard failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Dashboard error: {e}")
            return False

    def test_api_key_validation(self) -> bool:
        """Test API key validation endpoint"""
        print("🧪 Testing API key validation...")
        try:
            headers = {**self.test_api_keys, "Content-Type": "application/json"}
            response = requests.post(
                f"{self.base_url}/api/integrations/validate",
                headers=headers,
                json={},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data["success"]:
                    valid_keys = sum(1 for result in data["validation_results"].values() if result["valid"])
                    print(f"✅ API validation: {valid_keys} valid keys out of {len(data['validation_results'])}")
                    for key_name, result in data["validation_results"].items():
                        status = "✅" if result["valid"] else "❌"
                        print(f"   {status} {key_name}: {result['message']}")
                    return True
                else:
                    print("❌ API validation failed")
                    return False
            else:
                print(f"❌ API validation failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API validation error: {e}")
            return False

    def test_integration_status(self) -> bool:
        """Test integration status endpoint"""
        print("🧪 Testing integration status...")
        try:
            response = requests.get(f"{self.base_url}/api/integrations/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print("✅ Integration status:")
                for service, status in data.items():
                    print(f"   {service}: {status['status']}")
                return True
            else:
                print(f"❌ Integration status failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Integration status error: {e}")
            return False

    def test_frontend_connectivity(self) -> bool:
        """Test frontend connectivity"""
        print("🧪 Testing frontend connectivity...")
        try:
            # Test frontend health
            response = requests.get(f"{self.frontend_url}", timeout=10)
            if response.status_code == 200:
                print("✅ Frontend is accessible")

                # Test frontend API endpoint
                api_response = requests.get(f"{self.frontend_url}/api/dashboard-dev", timeout=10)
                if api_response.status_code == 200:
                    data = api_response.json()
                    print(f"✅ Frontend API: {len(data.get('calendar', []))} events, {len(data.get('tasks', []))} tasks")
                    return True
                else:
                    print(f"❌ Frontend API failed: {api_response.status_code}")
                    return False
            else:
                print(f"❌ Frontend not accessible: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Frontend connectivity error: {e}")
            return False

    def test_calendar_endpoints(self) -> bool:
        """Test calendar endpoints"""
        print("🧪 Testing calendar endpoints...")
        try:
            headers = {**self.test_api_keys, "Content-Type": "application/json"}

            # Test calendar events
            response = requests.get(
                f"{self.base_url}/api/calendar/events?user_id=test_user",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Calendar events: {len(data)} events retrieved")
                return True
            else:
                print(f"❌ Calendar events failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Calendar endpoints error: {e}")
            return False

    def test_task_endpoints(self) -> bool:
        """Test task endpoints"""
        print("🧪 Testing task endpoints...")
        try:
            headers = {**self.test_api_keys, "Content-Type": "application/json"}

            # Test task retrieval
            response = requests.get(
                f"{self.base_url}/api/tasks?user_id=test_user",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Tasks: {data.get('count', 0)} tasks retrieved")
                return True
            else:
                print(f"❌ Tasks failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Task endpoints error: {e}")
            return False

    def test_message_endpoints(self) -> bool:
        """Test message endpoints"""
        print("🧪 Testing message endpoints...")
        try:
            headers = {**self.test_api_keys, "Content-Type": "application/json"}

            # Test message retrieval
            response = requests.get(
                f"{self.base_url}/api/messages?user_id=test_user",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Messages: {data.get('count', 0)} messages retrieved")
                return True
            else:
                print(f"❌ Messages failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Message endpoints error: {e}")
            return False

    def run_comprehensive_test(self) -> bool:
        """Run all tests and return overall success"""
        print("🚀 Starting Comprehensive Atom Integration Test")
        print("=" * 60)

        tests = [
            self.test_health_check,
            self.test_frontend_connectivity,
            self.test_dashboard_endpoint,
            self.test_api_key_validation,
            self.test_integration_status,
            self.test_calendar_endpoints,
            self.test_task_endpoints,
            self.test_message_endpoints
        ]

        results = []
        for test in tests:
            try:
                success = test()
                results.append(success)
                print()
            except Exception as e:
                print(f"❌ Test crashed: {e}")
                results.append(False)
                print()

        # Summary
        print("=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)

        passed = sum(results)
        total = len(results)

        print(f"Tests passed: {passed}/{total}")
        print(f"Success rate: {(passed/total)*100:.1f}%")

        if passed == total:
            print("🎉 ALL TESTS PASSED! Atom integration is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the logs above for details.")
            return False

def main():
    """Main test runner"""
    # Check if servers are running
    try:
        # Test backend
        backend_response = requests.get("http://localhost:5058/healthz", timeout=2)
        if backend_response.status_code != 200:
            print("❌ Backend server is not running on port 5058")
            print("   Start it with: cd backend/python-api-service && python minimal_app.py")
            sys.exit(1)

        # Test frontend
        frontend_response = requests.get("http://localhost:3000", timeout=2)
        if frontend_response.status_code != 200:
            print("⚠️  Frontend server is not running on port 3000")
            print("   Start it with: cd frontend-nextjs && npm run dev")
            print("   Continuing with backend tests only...")

    except requests.exceptions.RequestException:
        print("❌ Servers are not running")
        print("   Start backend: cd backend/python-api-service && python minimal_app.py")
        print("   Start frontend: cd frontend-nextjs && npm run dev")
        sys.exit(1)

    # Run tests
    tester = AtomIntegrationTest()
    success = tester.run_comprehensive_test()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
