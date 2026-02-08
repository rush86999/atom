"""
Comprehensive Integration Verification Script for Atom

This script verifies that all third-party applications are properly integrated
with workflow automation and accessible via the Atom agent chat interface.
"""

import asyncio
from datetime import datetime
import json
import logging
import sys
from typing import Any, Dict, List, Optional
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/atom_complete_integration_verification.log"),
    ],
)
logger = logging.getLogger(__name__)


class CompleteIntegrationVerifier:
    """
    Comprehensive verification of workflow automation and chat integration
    for all third-party services in Atom.
    """

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.verification_results = {}
        self.service_registry = {}

    async def run_comprehensive_verification(self) -> Dict[str, Any]:
        """
        Run complete verification of all integrations
        """
        logger.info("🚀 Starting Complete Integration Verification")
        logger.info("=" * 80)

        results = {
            "timestamp": datetime.now().isoformat(),
            "verification_steps": {},
            "summary": {},
            "recommendations": [],
        }

        # Step 1: Verify Service Registry
        logger.info("\n1. 📋 Verifying Service Registry...")
        service_registry_result = await self.verify_service_registry()
        results["verification_steps"]["service_registry"] = service_registry_result

        # Step 2: Verify Workflow Automation Integration
        logger.info("\n2. ⚙️ Verifying Workflow Automation Integration...")
        workflow_integration_result = (
            await self.verify_workflow_automation_integration()
        )
        results["verification_steps"]["workflow_automation"] = (
            workflow_integration_result
        )

        # Step 3: Verify Chat Interface Integration
        logger.info("\n3. 💬 Verifying Chat Interface Integration...")
        chat_integration_result = await self.verify_chat_interface_integration()
        results["verification_steps"]["chat_interface"] = chat_integration_result

        # Step 4: Verify Individual Service Integrations
        logger.info("\n4. 🔗 Verifying Individual Service Integrations...")
        service_integration_result = await self.verify_individual_service_integrations()
        results["verification_steps"]["service_integrations"] = (
            service_integration_result
        )

        # Step 5: Verify Workflow Execution
        logger.info("\n5. 🚀 Verifying Workflow Execution...")
        workflow_execution_result = await self.verify_workflow_execution()
        results["verification_steps"]["workflow_execution"] = workflow_execution_result

        # Generate Summary
        results["summary"] = self._generate_summary(results["verification_steps"])
        results["recommendations"] = self._generate_recommendations(
            results["verification_steps"]
        )

        # Print Final Results
        self._print_verification_summary(results)

        return results

    async def verify_service_registry(self) -> Dict[str, Any]:
        """Verify service registry contains all third-party integrations"""
        try:
            response = requests.get(f"{self.base_url}/api/services", timeout=30)

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Service registry endpoint returned {response.status_code}",
                    "services_count": 0,
                    "workflow_enabled": 0,
                    "chat_enabled": 0,
                }

            data = response.json()
            services = data.get("services", [])

            # Store service registry for later use
            self.service_registry = {s["id"]: s for s in services}

            # Count services with workflow and chat capabilities
            workflow_enabled = len(
                [
                    s
                    for s in services
                    if s.get("workflow_triggers") or s.get("workflow_actions")
                ]
            )
            chat_enabled = len([s for s in services if s.get("chat_commands")])

            result = {
                "success": True,
                "total_services": len(services),
                "workflow_enabled": workflow_enabled,
                "chat_enabled": chat_enabled,
                "services": [s["id"] for s in services],
            }

            logger.info(f"   ✅ Service Registry: {len(services)} services registered")
            logger.info(f"   📊 Workflow Enabled: {workflow_enabled} services")
            logger.info(f"   💬 Chat Enabled: {chat_enabled} services")

            return result

        except Exception as e:
            logger.error(f"   ❌ Service Registry Verification Failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "total_services": 0,
                "workflow_enabled": 0,
                "chat_enabled": 0,
            }

    async def verify_workflow_automation_integration(self) -> Dict[str, Any]:
        """Verify workflow automation integration endpoints"""
        endpoints_to_test = [
            "/api/workflow-automation/analyze",
            "/api/workflow-automation/generate",
            "/api/workflow-automation/execute",
            "/api/workflow-automation/schedule",
            "/api/workflow-automation/workflows",
        ]

        results = {}
        successful_endpoints = 0

        for endpoint in endpoints_to_test:
            try:
                # Test GET endpoints
                if endpoint.endswith("/workflows"):
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                # Test POST endpoints with sample data
                else:
                    sample_data = {
                        "user_input": "schedule a meeting tomorrow at 2 PM",
                        "user_id": "test_user",
                    }
                    response = requests.post(
                        f"{self.base_url}{endpoint}", json=sample_data, timeout=10
                    )

                if response.status_code in [200, 201]:
                    results[endpoint] = {
                        "success": True,
                        "status_code": response.status_code,
                    }
                    successful_endpoints += 1
                    logger.info(f"   ✅ {endpoint}: {response.status_code}")
                else:
                    results[endpoint] = {
                        "success": False,
                        "status_code": response.status_code,
                    }
                    logger.info(f"   ❌ {endpoint}: {response.status_code}")

            except Exception as e:
                results[endpoint] = {"success": False, "error": str(e)}
                logger.info(f"   ❌ {endpoint}: {str(e)}")

        return {
            "success": successful_endpoints == len(endpoints_to_test),
            "endpoints_tested": len(endpoints_to_test),
            "endpoints_successful": successful_endpoints,
            "endpoint_results": results,
        }

    async def verify_chat_interface_integration(self) -> Dict[str, Any]:
        """Verify chat interface integration"""
        try:
            # Test chat commands endpoint
            response = requests.get(
                f"{self.base_url}/api/services/chat-commands", timeout=10
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Chat commands endpoint returned {response.status_code}",
                    "commands_count": 0,
                }

            data = response.json()
            commands = data.get("chat_commands", [])

            # Test a sample chat command
            test_command = {
                "service_id": "google_calendar",
                "command": "schedule meeting",
            }

            command_response = requests.post(
                f"{self.base_url}/api/services/test-chat-command",
                json=test_command,
                timeout=10,
            )

            command_test_success = command_response.status_code in [200, 201]

            result = {
                "success": True,
                "commands_count": len(commands),
                "command_test_success": command_test_success,
                "available_commands": [
                    cmd["command"] for cmd in commands[:10]
                ],  # First 10 commands
            }

            logger.info(f"   ✅ Chat Commands: {len(commands)} commands available")
            logger.info(
                f"   🧪 Command Test: {'✅ Success' if command_test_success else '❌ Failed'}"
            )

            return result

        except Exception as e:
            logger.error(f"   ❌ Chat Interface Verification Failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "commands_count": 0,
                "command_test_success": False,
            }

    async def verify_individual_service_integrations(self) -> Dict[str, Any]:
        """Verify integration status for individual services"""
        try:
            response = requests.get(
                f"{self.base_url}/api/services/integration-status", timeout=10
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Integration status endpoint returned {response.status_code}",
                    "services_tested": 0,
                }

            data = response.json()
            integration_status = data.get("integration_status", {})

            workflow_stats = integration_status.get("workflow_automation", {})
            chat_stats = integration_status.get("chat_interface", {})

            result = {
                "success": True,
                "workflow_automation": {
                    "total_services": workflow_stats.get("total_services", 0),
                    "workflow_enabled": workflow_stats.get("workflow_enabled", 0),
                    "triggers_available": workflow_stats.get("triggers_available", 0),
                    "actions_available": workflow_stats.get("actions_available", 0),
                },
                "chat_interface": {
                    "total_services": chat_stats.get("total_services", 0),
                    "chat_enabled": chat_stats.get("chat_enabled", 0),
                    "commands_available": chat_stats.get("commands_available", 0),
                },
            }

            logger.info(
                f"   📊 Workflow Integration: {workflow_stats.get('workflow_enabled', 0)}/{workflow_stats.get('total_services', 0)} services"
            )
            logger.info(
                f"   💬 Chat Integration: {chat_stats.get('chat_enabled', 0)}/{chat_stats.get('total_services', 0)} services"
            )
            logger.info(
                f"   ⚡ Triggers: {workflow_stats.get('triggers_available', 0)} available"
            )
            logger.info(
                f"   🎯 Actions: {workflow_stats.get('actions_available', 0)} available"
            )

            return result

        except Exception as e:
            logger.error(
                f"   ❌ Individual Service Integration Verification Failed: {str(e)}"
            )
            return {"success": False, "error": str(e), "services_tested": 0}

    async def verify_workflow_execution(self) -> Dict[str, Any]:
        """Verify workflow execution capabilities"""
        try:
            # Test workflow generation
            test_workflow_request = {
                "user_input": "create a workflow to schedule a meeting and send an email",
                "user_id": "test_user",
            }

            response = requests.post(
                f"{self.base_url}/api/workflow-automation/generate",
                json=test_workflow_request,
                timeout=15,
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Workflow generation returned {response.status_code}",
                    "workflow_generated": False,
                    "workflow_executed": False,
                }

            data = response.json()
            workflow_generated = data.get("success", False)
            workflow_id = data.get("workflow_id")

            # Test workflow execution if generation was successful
            workflow_executed = False
            if workflow_generated and workflow_id:
                execution_request = {"workflow_id": workflow_id, "user_id": "test_user"}

                execution_response = requests.post(
                    f"{self.base_url}/api/workflow-automation/execute",
                    json=execution_request,
                    timeout=15,
                )

                workflow_executed = execution_response.status_code == 200

            result = {
                "success": workflow_generated,
                "workflow_generated": workflow_generated,
                "workflow_executed": workflow_executed,
                "workflow_id": workflow_id,
            }

            logger.info(
                f"   🏗️ Workflow Generation: {'✅ Success' if workflow_generated else '❌ Failed'}"
            )
            logger.info(
                f"   🚀 Workflow Execution: {'✅ Success' if workflow_executed else '❌ Failed'}"
            )

            return result

        except Exception as e:
            logger.error(f"   ❌ Workflow Execution Verification Failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "workflow_generated": False,
                "workflow_executed": False,
            }

    def _generate_summary(self, verification_steps: Dict[str, Any]) -> Dict[str, Any]:
        """Generate verification summary"""
        total_steps = len(verification_steps)
        successful_steps = sum(
            1 for step in verification_steps.values() if step.get("success", False)
        )

        # Calculate integration coverage
        service_registry = verification_steps.get("service_registry", {})
        workflow_integration = verification_steps.get("workflow_automation", {})
        chat_integration = verification_steps.get("chat_interface", {})
        service_integration = verification_steps.get("service_integrations", {})

        total_services = service_registry.get("total_services", 0)
        workflow_enabled = service_registry.get("workflow_enabled", 0)
        chat_enabled = service_registry.get("chat_enabled", 0)

        workflow_coverage = (
            (workflow_enabled / total_services * 100) if total_services > 0 else 0
        )
        chat_coverage = (
            (chat_enabled / total_services * 100) if total_services > 0 else 0
        )

        return {
            "total_verification_steps": total_steps,
            "successful_steps": successful_steps,
            "success_rate": (successful_steps / total_steps * 100)
            if total_steps > 0
            else 0,
            "integration_coverage": {
                "total_services": total_services,
                "workflow_coverage": f"{workflow_coverage:.1f}%",
                "chat_coverage": f"{chat_coverage:.1f}%",
                "workflow_enabled_services": workflow_enabled,
                "chat_enabled_services": chat_enabled,
            },
            "overall_status": "PASS"
            if successful_steps == total_steps
            else "PARTIAL"
            if successful_steps > 0
            else "FAIL",
        }

    def _generate_recommendations(
        self, verification_steps: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on verification results"""
        recommendations = []

        service_registry = verification_steps.get("service_registry", {})
        workflow_integration = verification_steps.get("workflow_automation", {})
        chat_integration = verification_steps.get("chat_interface", {})

        total_services = service_registry.get("total_services", 0)
        workflow_enabled = service_registry.get("workflow_enabled", 0)
        chat_enabled = service_registry.get("chat_enabled", 0)

        # Check for missing workflow integration
        if workflow_enabled < total_services:
            missing_count = total_services - workflow_enabled
            recommendations.append(
                f"Add workflow automation to {missing_count} services without workflow integration"
            )

        # Check for missing chat integration
        if chat_enabled < total_services:
            missing_count = total_services - chat_enabled
            recommendations.append(
                f"Add chat commands to {missing_count} services without chat integration"
            )

        # Check workflow automation endpoints
        if not workflow_integration.get("success", False):
            successful_endpoints = workflow_integration.get("endpoints_successful", 0)
            total_endpoints = workflow_integration.get("endpoints_tested", 0)
            recommendations.append(
                f"Fix {total_endpoints - successful_endpoints} workflow automation endpoints"
            )

        # Check chat interface
        if not chat_integration.get("success", False):
            recommendations.append("Verify chat command handlers and endpoints")

        return recommendations

    def _print_verification_summary(self, results: Dict[str, Any]):
        """Print final verification summary"""
        summary = results["summary"]
        recommendations = results["recommendations"]

        logger.info("\n" + "=" * 80)
        logger.info("📊 COMPLETE INTEGRATION VERIFICATION SUMMARY")
        logger.info("=" * 80)

        logger.info(f"Overall Status: {summary['overall_status']}")
        logger.info(
            f"Verification Steps: {summary['successful_steps']}/{summary['total_verification_steps']} passed"
        )
        logger.info(f"Success Rate: {summary['success_rate']:.1f}%")

        logger.info(f"\nIntegration Coverage:")
        logger.info(
            f"  Total Services: {summary['integration_coverage']['total_services']}"
        )
        logger.info(
            f"  Workflow Automation: {summary['integration_coverage']['workflow_coverage']}"
        )
        logger.info(
            f"  Chat Interface: {summary['integration_coverage']['chat_coverage']}"
        )

        if recommendations:
            logger.info(f"\n📝 Recommendations:")
            for rec in recommendations:
                logger.info(f"  • {rec}")
        else:
            logger.info(f"\n🎉 All integrations are properly configured!")

        logger.info(f"\n⏰ Verification completed at: {results['timestamp']}")
        logger.info("=" * 80)


async def main():
    """Main function"""
    verifier = CompleteIntegrationVerifier()
    results = await verifier.run_comprehensive_verification()

    # Save results to file
    with open("/tmp/atom_integration_verification_report.json", "w") as f:
        json.dump(results, f, indent=2)

    print(
        f"\n📄 Detailed report saved to: /tmp/atom_integration_verification_report.json"
    )

    # Exit with appropriate code
    if results["summary"]["overall_status"] == "PASS":
        sys.exit(0)
    elif results["summary"]["overall_status"] == "PARTIAL":
        sys.exit(1)
    else:
        sys.exit(2)
