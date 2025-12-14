"""
Simple Test Runner to Identify Bugs and Issues
Uses basic HTTP requests to test the application
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import requests
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SimpleTestRunner:
    """Simple test runner to identify bugs without complex dependencies"""

    def __init__(self):
        self.backend_url = "http://localhost:5059"
        self.frontend_url = "http://localhost:3002"
        self.test_results = {
            "start_time": datetime.now().isoformat(),
            "backend_tests": [],
            "frontend_tests": [],
            "integration_tests": [],
            "bugs_found": [],
            "recommendations": []
        }

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all simple tests"""
        print("="*80)
        print("SIMPLE BUG IDENTIFICATION TESTS")
        print("="*80)

        # Test backend
        print("\n[BACKEND TESTS]")
        self.test_backend_health()
        self.test_backend_endpoints()

        # Test frontend
        print("\n[FRONTEND TESTS]")
        self.test_frontend_health()
        self.test_frontend_pages()

        # Test integrations
        print("\n[INTEGRATION TESTS]")
        self.test_api_connectivity()
        self.test_sample_workflows()

        # Generate report
        self.generate_report()

        return self.test_results

    def test_backend_health(self):
        """Test backend health endpoint"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                print("PASS Backend health check: PASSED")
                self.test_results["backend_tests"].append({
                    "test": "health_check",
                    "status": "passed",
                    "response_time": response.elapsed.total_seconds()
                })
            else:
                print(f"FAIL Backend health check: FAILED (Status: {response.status_code})")
                self.test_results["backend_tests"].append({
                    "test": "health_check",
                    "status": "failed",
                    "error": f"Status code: {response.status_code}"
                })
                self.test_results["bugs_found"].append({
                    "type": "backend",
                    "severity": "critical",
                    "description": f"Backend health endpoint returned {response.status_code}"
                })

        except Exception as e:
            print(f"FAIL Backend health check: ERROR ({str(e)})")
            self.test_results["backend_tests"].append({
                "test": "health_check",
                "status": "error",
                "error": str(e)
            })
            self.test_results["bugs_found"].append({
                "type": "backend",
                "severity": "critical",
                "description": f"Backend not accessible: {str(e)}"
            })

    def test_backend_endpoints(self):
        """Test key backend endpoints"""
        endpoints = [
            "/api/v1/services",
            "/api/v1/workflows",
            "/api/agent/status/test_task",
            "/api/system/status"
        ]

        for endpoint in endpoints:
            try:
                response = requests.get(f"{self.backend_url}{endpoint}", timeout=5)
                if response.status_code in [200, 401, 403]:  # 401/403 are OK (need auth)
                    print(f"PASS Backend endpoint {endpoint}: PASSED ({response.status_code})")
                    self.test_results["backend_tests"].append({
                        "test": f"endpoint_{endpoint}",
                        "status": "passed",
                        "status_code": response.status_code
                    })
                else:
                    print(f"FAIL Backend endpoint {endpoint}: FAILED ({response.status_code})")
                    self.test_results["backend_tests"].append({
                        "test": f"endpoint_{endpoint}",
                        "status": "failed",
                        "status_code": response.status_code
                    })
                    self.test_results["bugs_found"].append({
                        "type": "backend",
                        "severity": "high",
                        "description": f"Endpoint {endpoint} returned {response.status_code}"
                    })

            except Exception as e:
                print(f"FAIL Backend endpoint {endpoint}: ERROR ({str(e)})")
                self.test_results["backend_tests"].append({
                    "test": f"endpoint_{endpoint}",
                    "status": "error",
                    "error": str(e)
                })

    def test_frontend_health(self):
        """Test frontend accessibility"""
        try:
            response = requests.get(self.frontend_url, timeout=30)
            if response.status_code == 200:
                print("PASS Frontend accessible: PASSED")
                self.test_results["frontend_tests"].append({
                    "test": "frontend_accessible",
                    "status": "passed",
                    "response_time": response.elapsed.total_seconds()
                })
            else:
                print(f"FAIL Frontend accessible: FAILED ({response.status_code})")
                self.test_results["frontend_tests"].append({
                    "test": "frontend_accessible",
                    "status": "failed",
                    "error": f"Status code: {response.status_code}"
                })

        except Exception as e:
            print(f"FAIL Frontend accessible: ERROR ({str(e)})")
            self.test_results["frontend_tests"].append({
                "test": "frontend_accessible",
                "status": "error",
                "error": str(e)
            })
            self.test_results["bugs_found"].append({
                "type": "frontend",
                "severity": "critical",
                "description": f"Frontend not accessible: {str(e)}"
            })

    def test_frontend_pages(self):
        """Test key frontend pages"""
        pages = [
            "/",
            "/auth/login",
            "/dashboard",
            "/dev-studio",
            "/integrations",
            "/chat"
        ]

        for page in pages:
            try:
                response = requests.get(f"{self.frontend_url}{page}", timeout=5)
                if response.status_code == 200:
                    print(f"PASS Frontend page {page}: PASSED")
                    self.test_results["frontend_tests"].append({
                        "test": f"page_{page}",
                        "status": "passed",
                        "status_code": response.status_code
                    })
                else:
                    print(f"FAIL Frontend page {page}: FAILED ({response.status_code})")
                    self.test_results["frontend_tests"].append({
                        "test": f"page_{page}",
                        "status": "failed",
                        "status_code": response.status_code
                    })
                    self.test_results["bugs_found"].append({
                        "type": "frontend",
                        "severity": "medium",
                        "description": f"Page {page} returned {response.status_code}"
                    })

            except Exception as e:
                print(f"FAIL Frontend page {page}: ERROR ({str(e)})")
                self.test_results["frontend_tests"].append({
                    "test": f"page_{page}",
                    "status": "error",
                    "error": str(e)
                })

    def test_api_connectivity(self):
        """Test frontend-backend connectivity"""
        try:
            # Test if frontend can reach backend API
            response = requests.get(f"{self.frontend_url}/api/health", timeout=5)
            if response.status_code == 200:
                print("PASS Frontend-backend connectivity: PASSED")
                self.test_results["integration_tests"].append({
                    "test": "api_connectivity",
                    "status": "passed"
                })
            else:
                print(f"FAIL Frontend-backend connectivity: FAILED ({response.status_code})")
                self.test_results["integration_tests"].append({
                    "test": "api_connectivity",
                    "status": "failed",
                    "status_code": response.status_code
                })

        except Exception as e:
            print(f"FAIL Frontend-backend connectivity: ERROR ({str(e)})")
            self.test_results["integration_tests"].append({
                "test": "api_connectivity",
                "status": "error",
                "error": str(e)
            })

    def test_sample_workflows(self):
        """Test sample workflow functionality"""
        try:
            # Test atom-agent chat endpoint
            chat_data = {
                "message": "test message",
                "session_id": "test_session"
            }

            response = requests.post(
                f"{self.backend_url}/api/atom-agent/chat",
                json=chat_data,
                timeout=5
            )

            if response.status_code in [200, 201, 401]:  # 401 is OK (needs auth)
                print("PASS Agent API: PASSED")
                self.test_results["integration_tests"].append({
                    "test": "agent_api",
                    "status": "passed",
                    "status_code": response.status_code
                })
            else:
                print(f"FAIL Agent API: FAILED ({response.status_code})")
                self.test_results["integration_tests"].append({
                    "test": "agent_api",
                    "status": "failed",
                    "status_code": response.status_code
                })

        except Exception as e:
            print(f"FAIL Agent API: ERROR ({str(e)})")
            self.test_results["integration_tests"].append({
                "test": "agent_api",
                "status": "error",
                "error": str(e)
            })

    def generate_report(self):
        """Generate test report with recommendations"""
        print("\n" + "="*80)
        print("BUG IDENTIFICATION REPORT")
        print("="*80)

        # Count results
        backend_passed = len([t for t in self.test_results["backend_tests"] if t["status"] == "passed"])
        backend_total = len(self.test_results["backend_tests"])

        frontend_passed = len([t for t in self.test_results["frontend_tests"] if t["status"] == "passed"])
        frontend_total = len(self.test_results["frontend_tests"])

        integration_passed = len([t for t in self.test_results["integration_tests"] if t["status"] == "passed"])
        integration_total = len(self.test_results["integration_tests"])

        print(f"\nBackend Tests: {backend_passed}/{backend_total} passed")
        print(f"Frontend Tests: {frontend_passed}/{frontend_total} passed")
        print(f"Integration Tests: {integration_passed}/{integration_total} passed")
        print(f"\nTotal Bugs Found: {len(self.test_results['bugs_found'])}")

        # Categorize bugs
        critical_bugs = [b for b in self.test_results["bugs_found"] if b.get("severity") == "critical"]
        high_bugs = [b for b in self.test_results["bugs_found"] if b.get("severity") == "high"]
        medium_bugs = [b for b in self.test_results["bugs_found"] if b.get("severity") == "medium"]

        if critical_bugs:
            print(f"\nCRITICAL BUGS ({len(critical_bugs)}):")
            for bug in critical_bugs:
                print(f"  - {bug['description']}")

        if high_bugs:
            print(f"\nHIGH SEVERITY BUGS ({len(high_bugs)}):")
            for bug in high_bugs:
                print(f"  - {bug['description']}")

        if medium_bugs:
            print(f"\nMEDIUM SEVERITY BUGS ({len(medium_bugs)}):")
            for bug in medium_bugs:
                print(f"  - {bug['description']}")

        # Generate recommendations
        if critical_bugs:
            self.test_results["recommendations"].append("Fix critical connectivity issues first - server may not be running properly")

        if high_bugs:
            self.test_results["recommendations"].append("Review API endpoint configurations and implement proper error handling")

        if medium_bugs:
            self.test_results["recommendations"].append("Add proper routing and error pages for missing frontend routes")

        if not self.test_results["bugs_found"]:
            self.test_results["recommendations"].append("All tests passed! Consider adding more comprehensive tests")

        # Print recommendations
        if self.test_results["recommendations"]:
            print(f"\nRECOMMENDATIONS:")
            for i, rec in enumerate(self.test_results["recommendations"], 1):
                print(f"  {i}. {rec}")

        # Save report
        self.test_results["end_time"] = datetime.now().isoformat()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"test_results/simple_test_report_{timestamp}.json"

        os.makedirs("test_results", exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(self.test_results, f, indent=2, default=str)

        print(f"\nReport saved to: {report_path}")
        print("="*80)


def main():
    """Main entry point"""
    runner = SimpleTestRunner()
    results = runner.run_all_tests()

    # Exit with code based on results
    if len(results["bugs_found"]) > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()