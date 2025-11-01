#!/usr/bin/env python3
"""
NLU System Diagnostic and Debugging Script

This script provides comprehensive diagnostics for the NLU bridge system
to identify and fix issues with the TypeScript NLU integration.
"""

import requests
import json
import logging
import sys
from typing import Dict, Any, Optional
from dataclasses import dataclass
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class NLUDiagnosticResult:
    """Results from NLU system diagnostics"""

    component: str
    status: str
    details: Dict[str, Any]
    error: Optional[str] = None


class NLUSystemDiagnostic:
    """Comprehensive diagnostic tool for NLU system"""

    def __init__(
        self, backend_url="http://localhost:5058", frontend_url="http://localhost:3000"
    ):
        self.backend_url = backend_url
        self.frontend_url = frontend_url
        self.results = []

    def run_comprehensive_diagnostics(self) -> bool:
        """Run all diagnostic tests"""
        print("🚀 Starting Comprehensive NLU System Diagnostics")
        print("=" * 60)

        tests = [
            ("Backend Health", self.test_backend_health),
            ("NLU Bridge Service", self.test_nlu_bridge_service),
            ("TypeScript NLU API", self.test_typescript_nlu_api),
            ("Workflow Agent Integration", self.test_workflow_agent_integration),
            ("NLU Analysis Endpoint", self.test_nlu_analysis_endpoint),
            ("Workflow Generation", self.test_workflow_generation),
            ("Service Registry", self.test_service_registry),
            ("Error Handling", self.test_error_handling),
        ]

        for test_name, test_func in tests:
            print(f"\n🔍 Testing: {test_name}")
            try:
                result = test_func()
                self.results.append(result)
                status_icon = "✅" if result.status == "PASS" else "❌"
                print(
                    f"   {status_icon} {result.status}: {result.details.get('message', '')}"
                )
                if result.error:
                    print(f"   Error: {result.error}")
            except Exception as e:
                error_result = NLUDiagnosticResult(
                    component=test_name,
                    status="ERROR",
                    details={"message": f"Test failed with exception: {str(e)}"},
                    error=str(e),
                )
                self.results.append(error_result)
                print(f"   ❌ ERROR: {str(e)}")

        return self.generate_diagnostic_report()

    def test_backend_health(self) -> NLUDiagnosticResult:
        """Test backend server health"""
        try:
            response = requests.get(f"{self.backend_url}/healthz", timeout=10)
            data = response.json()

            return NLUDiagnosticResult(
                component="Backend Health",
                status="PASS" if data.get("status") == "ok" else "FAIL",
                details={
                    "message": f"Backend status: {data.get('status')}",
                    "blueprints_loaded": data.get("total_blueprints", 0),
                    "database_status": data.get("database", {}),
                },
            )
        except Exception as e:
            return NLUDiagnosticResult(
                component="Backend Health",
                status="FAIL",
                details={"message": "Backend server unavailable"},
                error=str(e),
            )

    def test_nlu_bridge_service(self) -> NLUDiagnosticResult:
        """Test NLU bridge service import and initialization"""
        try:
            # Try to import the NLU bridge service
            sys.path.insert(0, "backend/python-api-service")
            from nlu_bridge_service import NLUBridgeService

            # Test service initialization
            service = NLUBridgeService(frontend_base_url=self.frontend_url)

            return NLUDiagnosticResult(
                component="NLU Bridge Service",
                status="PASS",
                details={
                    "message": "NLU bridge service imported successfully",
                    "frontend_url": service.frontend_base_url,
                },
            )
        except Exception as e:
            return NLUDiagnosticResult(
                component="NLU Bridge Service",
                status="FAIL",
                details={"message": "Failed to import NLU bridge service"},
                error=str(e),
            )

    def test_typescript_nlu_api(self) -> NLUDiagnosticResult:
        """Test TypeScript NLU API endpoint"""
        test_inputs = [
            "Schedule a meeting for tomorrow",
            "Send a message to Slack",
            "Create a task in Asana",
            "What's the weather like today?",
        ]

        results = []
        for user_input in test_inputs:
            try:
                response = requests.post(
                    f"{self.frontend_url}/api/agent/nlu",
                    json={"message": user_input, "userId": "diagnostic_user"},
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    results.append(
                        {
                            "input": user_input,
                            "success": data.get("success", False),
                            "response": data,
                        }
                    )
                else:
                    results.append(
                        {
                            "input": user_input,
                            "success": False,
                            "error": f"HTTP {response.status_code}",
                        }
                    )

            except Exception as e:
                results.append({"input": user_input, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r.get("success", False))

        return NLUDiagnosticResult(
            component="TypeScript NLU API",
            status="PASS" if success_count > 0 else "FAIL",
            details={
                "message": f"TypeScript NLU API responses: {success_count}/{len(test_inputs)} successful",
                "test_results": results,
            },
        )

    def test_workflow_agent_integration(self) -> NLUDiagnosticResult:
        """Test workflow agent integration service"""
        try:
            # Try to import workflow agent service
            sys.path.insert(0, "backend/python-api-service")
            from workflow_agent_integration import WorkflowAgentIntegrationService

            service = WorkflowAgentIntegrationService()

            return NLUDiagnosticResult(
                component="Workflow Agent Integration",
                status="PASS",
                details={
                    "message": "Workflow agent integration service imported successfully"
                },
            )
        except Exception as e:
            return NLUDiagnosticResult(
                component="Workflow Agent Integration",
                status="FAIL",
                details={
                    "message": "Failed to import workflow agent integration service"
                },
                error=str(e),
            )

    def test_nlu_analysis_endpoint(self) -> NLUDiagnosticResult:
        """Test the NLU analysis endpoint"""
        test_cases = [
            {
                "user_input": "When I receive an email from boss, create a task in Asana",
                "expected_workflow": True,
            },
            {"user_input": "What's the weather today?", "expected_workflow": False},
            {
                "user_input": "Schedule a meeting every Monday at 9 AM",
                "expected_workflow": True,
            },
        ]

        results = []
        for test_case in test_cases:
            try:
                response = requests.post(
                    f"{self.backend_url}/api/workflow-automation/analyze",
                    json={
                        "user_input": test_case["user_input"],
                        "user_id": "diagnostic_user",
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    results.append(
                        {
                            "input": test_case["user_input"],
                            "success": data.get("success", False),
                            "response": data,
                        }
                    )
                else:
                    results.append(
                        {
                            "input": test_case["user_input"],
                            "success": False,
                            "error": f"HTTP {response.status_code}",
                        }
                    )

            except Exception as e:
                results.append(
                    {
                        "input": test_case["user_input"],
                        "success": False,
                        "error": str(e),
                    }
                )

        success_count = sum(1 for r in results if r.get("success", False))

        return NLUDiagnosticResult(
            component="NLU Analysis Endpoint",
            status="PASS" if success_count > 0 else "FAIL",
            details={
                "message": f"NLU analysis endpoint: {success_count}/{len(test_cases)} successful",
                "test_results": results,
            },
        )

    def test_workflow_generation(self) -> NLUDiagnosticResult:
        """Test workflow generation endpoint"""
        test_inputs = [
            "Schedule a meeting for tomorrow",
            "Send a message to Slack",
            "Create a task in Asana",
        ]

        results = []
        for user_input in test_inputs:
            try:
                response = requests.post(
                    f"{self.backend_url}/api/workflow-automation/generate",
                    json={"user_input": user_input, "user_id": "diagnostic_user"},
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    results.append(
                        {
                            "input": user_input,
                            "success": data.get("success", False),
                            "workflow_actions": data.get("workflow", {}).get(
                                "actions", []
                            ),
                            "services_used": data.get("workflow", {}).get(
                                "services", []
                            ),
                        }
                    )
                else:
                    results.append(
                        {
                            "input": user_input,
                            "success": False,
                            "error": f"HTTP {response.status_code}",
                        }
                    )

            except Exception as e:
                results.append({"input": user_input, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r.get("success", False))

        return NLUDiagnosticResult(
            component="Workflow Generation",
            status="PASS" if success_count > 0 else "FAIL",
            details={
                "message": f"Workflow generation: {success_count}/{len(test_inputs)} successful",
                "test_results": results,
            },
        )

    def test_service_registry(self) -> NLUDiagnosticResult:
        """Test service registry for NLU-related services"""
        try:
            response = requests.get(
                f"{self.backend_url}/api/services/status", timeout=10
            )
            data = response.json()

            total_services = data.get("total_services", 0)
            active_services = data.get("status_summary", {}).get("active", 0)

            return NLUDiagnosticResult(
                component="Service Registry",
                status="PASS" if total_services > 0 else "FAIL",
                details={
                    "message": f"Service registry: {total_services} total, {active_services} active",
                    "total_services": total_services,
                    "active_services": active_services,
                },
            )
        except Exception as e:
            return NLUDiagnosticResult(
                component="Service Registry",
                status="FAIL",
                details={"message": "Failed to access service registry"},
                error=str(e),
            )

    def test_error_handling(self) -> NLUDiagnosticResult:
        """Test error handling in NLU system"""
        error_test_cases = [
            {"user_input": ""},  # Empty input
            {"user_input": "   "},  # Whitespace only
            {"invalid_field": "test"},  # Missing required field
        ]

        results = []
        for test_case in error_test_cases:
            try:
                response = requests.post(
                    f"{self.backend_url}/api/workflow-automation/generate",
                    json=test_case,
                    timeout=10,
                )

                # For error cases, we expect non-200 status
                if response.status_code >= 400:
                    results.append(
                        {
                            "test_case": test_case,
                            "success": True,  # Error handling worked
                            "status_code": response.status_code,
                        }
                    )
                else:
                    results.append(
                        {
                            "test_case": test_case,
                            "success": False,
                            "error": f"Expected error but got {response.status_code}",
                        }
                    )

            except Exception as e:
                results.append(
                    {"test_case": test_case, "success": False, "error": str(e)}
                )

        success_count = sum(1 for r in results if r.get("success", False))

        return NLUDiagnosticResult(
            component="Error Handling",
            status="PASS" if success_count > 0 else "FAIL",
            details={
                "message": f"Error handling: {success_count}/{len(error_test_cases)} tests passed",
                "test_results": results,
            },
        )

    def generate_diagnostic_report(self) -> bool:
        """Generate comprehensive diagnostic report"""
        print("\n" + "=" * 60)
        print("📊 NLU SYSTEM DIAGNOSTIC REPORT")
        print("=" * 60)

        passed_tests = sum(1 for r in self.results if r.status == "PASS")
        total_tests = len(self.results)

        print(f"\n📈 OVERALL STATUS: {passed_tests}/{total_tests} tests passed")

        # Detailed results
        for result in self.results:
            status_icon = "✅" if result.status == "PASS" else "❌"
            print(f"\n{status_icon} {result.component}")
            print(f"   Status: {result.status}")
            print(f"   Details: {result.details.get('message', 'N/A')}")
            if result.error:
                print(f"   Error: {result.error}")

        # Recommendations
        print("\n🎯 RECOMMENDATIONS:")

        failed_components = [r.component for r in self.results if r.status != "PASS"]
        if failed_components:
            print("❌ Issues detected in:")
            for component in failed_components:
                print(f"   - {component}")

            if "TypeScript NLU API" in failed_components:
                print("\n🔧 Fix TypeScript NLU API:")
                print("   1. Check if frontend server is running on port 3000")
                print("   2. Verify /api/agent/nlu endpoint exists")
                print("   3. Check frontend logs for NLU service errors")

            if "NLU Bridge Service" in failed_components:
                print("\n🔧 Fix NLU Bridge Service:")
                print("   1. Check nlu_bridge_service.py file exists")
                print("   2. Verify imports and dependencies")
                print("   3. Test service initialization")

            if "Workflow Generation" in failed_components:
                print("\n🔧 Fix Workflow Generation:")
                print("   1. Check workflow_automation_api.py endpoints")
                print("   2. Verify workflow_agent_integration service")
                print("   3. Test individual workflow generation steps")
        else:
            print("✅ All components are functioning correctly!")

        # Save detailed report
        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "overall_status": f"{passed_tests}/{total_tests} passed",
            "results": [
                {
                    "component": r.component,
                    "status": r.status,
                    "details": r.details,
                    "error": r.error,
                }
                for r in self.results
            ],
        }

        with open("nlu_diagnostic_report.json", "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved to: nlu_diagnostic_report.json")

        return passed_tests == total_tests


def main():
    """Main diagnostic function"""
    diagnostic = NLUSystemDiagnostic()
    success = diagnostic.run_comprehensive_diagnostics()

    if success:
        print("\n🎉 NLU System Diagnostics: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ NLU System Diagnostics: SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
