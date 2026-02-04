#!/usr/bin/env python3
"""
Quick Integration Verification Script for Atom

This script provides a quick verification of third-party service integrations
with workflow automation and Atom agent chat interface.
"""

import json
import sys
from datetime import datetime
from typing import Any, Dict, List
import requests


class QuickIntegrationVerifier:
    """Quick verification of Atom integrations"""

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.results = {}

    def verify_service_registry(self) -> Dict[str, Any]:
        """Quick check of service registry"""
        try:
            response = requests.get(f"{self.base_url}/api/services", timeout=10)
            if response.status_code == 200:
                data = response.json()
                services = data.get("services", [])

                # Count services with workflow and chat capabilities
                workflow_enabled = len(
                    [
                        s
                        for s in services
                        if s.get("workflow_triggers") or s.get("workflow_actions")
                    ]
                )
                chat_enabled = len([s for s in services if s.get("chat_commands")])

                return {
                    "success": True,
                    "total_services": len(services),
                    "workflow_enabled": workflow_enabled,
                    "chat_enabled": chat_enabled,
                    "services": [s["id"] for s in services[:10]],  # First 10 services
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "total_services": 0,
                }
        except Exception as e:
            return {"success": False, "error": str(e), "total_services": 0}

    def verify_workflow_endpoints(self) -> Dict[str, Any]:
        """Quick check of workflow automation endpoints"""
        endpoints = [
            "/api/workflow-automation/analyze",
            "/api/workflow-automation/generate",
            "/api/workflow-automation/workflows",
        ]

        results = {}
        successful = 0

        for endpoint in endpoints:
            try:
                if endpoint.endswith("/workflows"):
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                else:
                    response = requests.post(
                        f"{self.base_url}{endpoint}",
                        json={"user_input": "test workflow", "user_id": "test"},
                        timeout=5,
                    )

                results[endpoint] = response.status_code in [200, 201]
                if results[endpoint]:
                    successful += 1
            except:
                results[endpoint] = False

        return {
            "success": successful == len(endpoints),
            "endpoints_tested": len(endpoints),
            "endpoints_successful": successful,
            "results": results,
        }

    def verify_chat_commands(self) -> Dict[str, Any]:
        """Quick check of chat command integration"""
        try:
            response = requests.get(
                f"{self.base_url}/api/services/chat-commands", timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                commands = data.get("chat_commands", [])

                return {
                    "success": True,
                    "commands_count": len(commands),
                    "sample_commands": [cmd["command"] for cmd in commands[:5]],
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "commands_count": 0,
                }
        except Exception as e:
            return {"success": False, "error": str(e), "commands_count": 0}

    def run_quick_verification(self) -> Dict[str, Any]:
        """Run all quick verification checks"""
        print("🚀 Quick Integration Verification")
        print("=" * 50)

        # Service Registry
        print("\n1. 📋 Service Registry...", end=" ")
        service_result = self.verify_service_registry()
        self.results["service_registry"] = service_result
        if service_result["success"]:
            print(f"✅ {service_result['total_services']} services")
        else:
            print("❌ Failed")

        # Workflow Endpoints
        print("2. ⚙️ Workflow Endpoints...", end=" ")
        workflow_result = self.verify_workflow_endpoints()
        self.results["workflow_endpoints"] = workflow_result
        if workflow_result["success"]:
            print(
                f"✅ {workflow_result['endpoints_successful']}/{workflow_result['endpoints_tested']}"
            )
        else:
            print("❌ Failed")

        # Chat Commands
        print("3. 💬 Chat Commands...", end=" ")
        chat_result = self.verify_chat_commands()
        self.results["chat_commands"] = chat_result
        if chat_result["success"]:
            print(f"✅ {chat_result['commands_count']} commands")
        else:
            print("❌ Failed")

        # Generate Summary
        summary = self._generate_summary()
        self._print_summary(summary)

        return {
            "timestamp": datetime.now().isoformat(),
            "results": self.results,
            "summary": summary,
        }

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate verification summary"""
        total_checks = len(self.results)
        successful_checks = sum(
            1 for result in self.results.values() if result["success"]
        )

        service_registry = self.results.get("service_registry", {})
        workflow_endpoints = self.results.get("workflow_endpoints", {})
        chat_commands = self.results.get("chat_commands", {})

        return {
            "total_checks": total_checks,
            "successful_checks": successful_checks,
            "success_rate": (successful_checks / total_checks * 100)
            if total_checks > 0
            else 0,
            "services_registered": service_registry.get("total_services", 0),
            "workflow_endpoints_working": workflow_endpoints.get(
                "endpoints_successful", 0
            ),
            "chat_commands_available": chat_commands.get("commands_count", 0),
            "status": "PASS"
            if successful_checks == total_checks
            else "PARTIAL"
            if successful_checks > 0
            else "FAIL",
        }

    def _print_summary(self, summary: Dict[str, Any]):
        """Print verification summary"""
        print("\n" + "=" * 50)
        print("📊 QUICK VERIFICATION SUMMARY")
        print("=" * 50)

        print(f"Overall Status: {summary['status']}")
        print(
            f"Checks Passed: {summary['successful_checks']}/{summary['total_checks']}"
        )
        print(f"Success Rate: {summary['success_rate']:.1f}%")

        print(f"\nIntegration Metrics:")
        print(f"  Services Registered: {summary['services_registered']}")
        print(f"  Workflow Endpoints: {summary['workflow_endpoints_working']}/3")
        print(f"  Chat Commands: {summary['chat_commands_available']}")

        if summary["status"] == "PASS":
            print(f"\n🎉 All integrations are working correctly!")
        elif summary["status"] == "PARTIAL":
            print(f"\n⚠️ Some integrations need attention")
        else:
            print(f"\n❌ Integration issues detected")

        print(f"\n⏰ Verified at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)


def main():
    """Main function"""
    verifier = QuickIntegrationVerifier()

    try:
        results = verifier.run_quick_verification()

        # Save results
        with open("/tmp/atom_quick_verification.json", "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n📄 Detailed results saved to: /tmp/atom_quick_verification.json")

        # Exit with appropriate code
        if results["summary"]["status"] == "PASS":
            sys.exit(0)
        elif results["summary"]["status"] == "PARTIAL":
            sys.exit(1)
        else:
            sys.exit(2)

    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        sys.exit(2)


if __name__ == "__main__":
    main()
