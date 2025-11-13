#!/usr/bin/env python3
"""
ATOM PLATFORM - DEVELOPMENT VERIFICATION SCRIPT
Basic testing for core functionality during development
Focus: Quick verification, not exhaustive testing
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


class DevVerification:
    """Basic verification for development work"""

    def __init__(self):
        self.base_urls = {
            "frontend": "http://localhost:3000",
            "backend": "http://localhost:8000",
            "oauth": "http://localhost:5058",
        }
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "environment": "development",
            "tests": {},
        }

    def log_test(self, test_name, status, details=None):
        """Log test result"""
        self.results["tests"][test_name] = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} {test_name}: {status}")
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")

    def verify_service_health(self):
        """Basic health check for all services"""
        print("🔍 VERIFYING SERVICE HEALTH")
        print("-" * 40)

        # Frontend health
        try:
            response = requests.get(
                f"{self.base_urls['frontend']}/api/health", timeout=10
            )
            if response.status_code == 200:
                self.log_test(
                    "Frontend Health",
                    "PASS",
                    {"response_time": response.elapsed.total_seconds()},
                )
            else:
                self.log_test(
                    "Frontend Health", "FAIL", {"status_code": response.status_code}
                )
        except Exception as e:
            self.log_test("Frontend Health", "FAIL", {"error": str(e)})

        # Backend health
        try:
            response = requests.get(f"{self.base_urls['backend']}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Backend Health",
                    "PASS",
                    {
                        "response_time": response.elapsed.total_seconds(),
                        "status": data.get("status", "unknown"),
                    },
                )
            else:
                self.log_test(
                    "Backend Health", "FAIL", {"status_code": response.status_code}
                )
        except Exception as e:
            self.log_test("Backend Health", "FAIL", {"error": str(e)})

        # OAuth health
        try:
            response = requests.get(f"{self.base_urls['oauth']}/healthz", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "OAuth Health",
                    "PASS",
                    {
                        "response_time": response.elapsed.total_seconds(),
                        "service": data.get("service", "unknown"),
                    },
                )
            else:
                self.log_test(
                    "OAuth Health", "FAIL", {"status_code": response.status_code}
                )
        except Exception as e:
            self.log_test("OAuth Health", "FAIL", {"error": str(e)})

    def verify_api_endpoints(self):
        """Basic verification of core API endpoints"""
        print("\n🔧 VERIFYING CORE API ENDPOINTS")
        print("-" * 40)

        endpoints = [
            ("System Status", "/api/system/status"),
            ("Service Registry", "/api/services/registry"),
            ("OAuth Status", "/api/auth/oauth-status"),
        ]

        for name, endpoint in endpoints:
            try:
                if "auth" in endpoint:
                    url = f"{self.base_urls['oauth']}{endpoint}"
                else:
                    url = f"{self.base_urls['backend']}{endpoint}"

                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    self.log_test(
                        f"API: {name}",
                        "PASS",
                        {
                            "response_time": response.elapsed.total_seconds(),
                            "endpoint": endpoint,
                        },
                    )
                else:
                    self.log_test(
                        f"API: {name}",
                        "FAIL",
                        {"status_code": response.status_code, "endpoint": endpoint},
                    )
            except Exception as e:
                self.log_test(
                    f"API: {name}", "FAIL", {"error": str(e), "endpoint": endpoint}
                )

    def verify_service_integrations(self):
        """Basic verification of service integration framework"""
        print("\n🔗 VERIFYING SERVICE INTEGRATIONS")
        print("-" * 40)

        # Test service registry
        try:
            response = requests.get(
                f"{self.base_urls['backend']}/api/services/registry", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                services = data.get("services", [])
                active_count = len([s for s in services if s.get("status") == "active"])

                self.log_test(
                    "Service Registry",
                    "PASS",
                    {"total_services": len(services), "active_services": active_count},
                )
            else:
                self.log_test(
                    "Service Registry", "FAIL", {"status_code": response.status_code}
                )
        except Exception as e:
            self.log_test("Service Registry", "FAIL", {"error": str(e)})

    def verify_workflow_system(self):
        """Basic verification of workflow system"""
        print("\n🔄 VERIFYING WORKFLOW SYSTEM")
        print("-" * 40)

        # Test workflow endpoints
        workflow_endpoints = [
            ("Workflow Templates", "/api/workflows/templates"),
            ("Workflow Execution", "/api/workflows/execute"),
        ]

        for name, endpoint in workflow_endpoints:
            try:
                response = requests.get(
                    f"{self.base_urls['backend']}{endpoint}", timeout=10
                )
                # For execute endpoint, we expect 405 (method not allowed for GET)
                if response.status_code in [200, 405]:
                    self.log_test(
                        f"Workflow: {name}",
                        "PASS",
                        {"status_code": response.status_code, "endpoint": endpoint},
                    )
                else:
                    self.log_test(
                        f"Workflow: {name}",
                        "FAIL",
                        {"status_code": response.status_code, "endpoint": endpoint},
                    )
            except Exception as e:
                self.log_test(
                    f"Workflow: {name}", "FAIL", {"error": str(e), "endpoint": endpoint}
                )

    def verify_byok_system(self):
        """Basic verification of BYOK system"""
        print("\n🤖 VERIFYING BYOK SYSTEM")
        print("-" * 40)

        # Test AI provider endpoints
        try:
            response = requests.get(
                f"{self.base_urls['backend']}/api/ai/providers", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                providers = data.get("providers", [])

                self.log_test(
                    "BYOK Providers",
                    "PASS",
                    {
                        "available_providers": len(providers),
                        "providers": [p.get("name") for p in providers],
                    },
                )
            else:
                self.log_test(
                    "BYOK Providers", "FAIL", {"status_code": response.status_code}
                )
        except Exception as e:
            self.log_test("BYOK Providers", "FAIL", {"error": str(e)})

    def verify_performance(self):
        """Basic performance verification"""
        print("\n⚡ VERIFYING PERFORMANCE")
        print("-" * 40)

        endpoints_to_test = [
            ("Backend Health", f"{self.base_urls['backend']}/health"),
            ("Service Registry", f"{self.base_urls['backend']}/api/services/registry"),
            ("OAuth Health", f"{self.base_urls['oauth']}/healthz"),
        ]

        for name, url in endpoints_to_test:
            try:
                start_time = time.time()
                response = requests.get(url, timeout=10)
                response_time = time.time() - start_time

                if response.status_code == 200 and response_time < 2.0:
                    self.log_test(
                        f"Performance: {name}",
                        "PASS",
                        {"response_time": f"{response_time:.3f}s"},
                    )
                elif response.status_code == 200:
                    self.log_test(
                        f"Performance: {name}",
                        "WARN",
                        {
                            "response_time": f"{response_time:.3f}s",
                            "note": "Response time > 2s",
                        },
                    )
                else:
                    self.log_test(
                        f"Performance: {name}",
                        "FAIL",
                        {
                            "status_code": response.status_code,
                            "response_time": f"{response_time:.3f}s",
                        },
                    )
            except Exception as e:
                self.log_test(f"Performance: {name}", "FAIL", {"error": str(e)})

    def generate_report(self):
        """Generate development verification report"""
        print("\n📊 GENERATING VERIFICATION REPORT")
        print("-" * 40)

        # Calculate summary
        total_tests = len(self.results["tests"])
        passed_tests = len(
            [t for t in self.results["tests"].values() if t["status"] == "PASS"]
        )
        failed_tests = len(
            [t for t in self.results["tests"].values() if t["status"] == "FAIL"]
        )
        warning_tests = len(
            [t for t in self.results["tests"].values() if t["status"] == "WARN"]
        )

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        summary = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "warnings": warning_tests,
            "success_rate": f"{success_rate:.1f}%",
        }

        self.results["summary"] = summary

        # Print summary
        print(f"📈 TEST SUMMARY:")
        print(f"   Total Tests: {total_tests}")
        print(f"   ✅ Passed: {passed_tests}")
        print(f"   ❌ Failed: {failed_tests}")
        print(f"   ⚠️  Warnings: {warning_tests}")
        print(f"   📊 Success Rate: {success_rate:.1f}%")

        # Save report
        report_file = (
            f"dev_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\n📄 Report saved: {report_file}")

        return summary

    def run_all_verifications(self):
        """Run all verification tests"""
        print("🚀 ATOM PLATFORM - DEVELOPMENT VERIFICATION")
        print("=" * 50)
        print("Running basic verification tests...")
        print("=" * 50)

        self.verify_service_health()
        self.verify_api_endpoints()
        self.verify_service_integrations()
        self.verify_workflow_system()
        self.verify_byok_system()
        self.verify_performance()

        summary = self.generate_report()

        print("\n" + "=" * 50)
        if summary["failed"] == 0 and summary["success_rate"] >= 80:
            print("🎉 DEVELOPMENT VERIFICATION: PASSED")
            print("✅ Platform is ready for development work")
        elif summary["failed"] <= 2 and summary["success_rate"] >= 70:
            print("⚠️ DEVELOPMENT VERIFICATION: ACCEPTABLE")
            print("🔄 Platform has minor issues but development can continue")
        else:
            print("❌ DEVELOPMENT VERIFICATION: NEEDS ATTENTION")
            print("🔧 Address critical issues before continuing development")

        print("=" * 50)

        return summary["success_rate"] >= 70


def main():
    """Main execution function"""
    verifier = DevVerification()
    success = verifier.run_all_verifications()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
