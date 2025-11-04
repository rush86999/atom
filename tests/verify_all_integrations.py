#!/usr/bin/env python3
"""
Comprehensive Integration Verification Script for Atom Workflow Automation

This script verifies that:
1. All services are properly integrated with workflow automation
2. All services are connected to the NLU system
3. Workflow automation properly uses the NLU system
4. There are no gaps in the integration between services, workflow automation, and NLU
"""

import asyncio
import aiohttp
import json
import logging
import sys
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@dataclass
class ServiceInfo:
    """Information about a service"""

    id: str
    name: str
    capabilities: List[str]
    status: str
    health: str


@dataclass
class WorkflowStep:
    """Information about a workflow step"""

    service: str
    action: str
    name: str


@dataclass
class WorkflowTemplate:
    """Information about a workflow template"""

    id: str
    name: str
    steps: List[WorkflowStep]


@dataclass
class IntegrationStatus:
    """Status of integration verification"""

    service_id: str
    service_name: str
    has_workflow_integration: bool
    has_nlu_support: bool
    workflow_steps: List[str]
    nlu_capabilities: List[str]
    status: str


class IntegrationVerifier:
    """Main class for verifying all integrations"""

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.session = None
        self.services: Dict[str, ServiceInfo] = {}
        self.workflow_templates: List[WorkflowTemplate] = []
        self.nlu_capabilities: Dict[str, List[str]] = {}

    async def initialize(self):
        """Initialize HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch_services(self) -> Dict[str, ServiceInfo]:
        """Fetch all services from the service registry"""
        await self.initialize()

        try:
            async with self.session.get(f"{self.base_url}/api/services") as response:
                if response.status == 200:
                    data = await response.json()
                    services = {}

                    for service_data in data.get("services", []):
                        service = ServiceInfo(
                            id=service_data["id"],
                            name=service_data["name"],
                            capabilities=service_data.get("capabilities", []),
                            status=service_data.get("status", "unknown"),
                            health=service_data.get("health", "unknown"),
                        )
                        services[service.id] = service

                    logger.info(f"✅ Fetched {len(services)} services")
                    self.services = services
                    return services
                else:
                    logger.error(f"❌ Failed to fetch services: HTTP {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"❌ Error fetching services: {str(e)}")
            return {}

    async def fetch_workflow_templates(self) -> List[WorkflowTemplate]:
        """Fetch all workflow templates"""
        await self.initialize()

        try:
            async with self.session.get(
                f"{self.base_url}/api/workflows/templates"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    templates = []

                    for template_data in data.get("templates", []):
                        steps = []
                        for step_data in template_data.get("steps", []):
                            step = WorkflowStep(
                                service=step_data["service"],
                                action=step_data["action"],
                                name=step_data["name"],
                            )
                            steps.append(step)

                        template = WorkflowTemplate(
                            id=template_data["id"],
                            name=template_data["name"],
                            steps=steps,
                        )
                        templates.append(template)

                    logger.info(f"✅ Fetched {len(templates)} workflow templates")
                    self.workflow_templates = templates
                    return templates
                else:
                    logger.error(
                        f"❌ Failed to fetch workflow templates: HTTP {response.status}"
                    )
                    return []
        except Exception as e:
            logger.error(f"❌ Error fetching workflow templates: {str(e)}")
            return []

    async def test_nlu_workflow_analysis(
        self, test_queries: List[str]
    ) -> Dict[str, Any]:
        """Test NLU workflow analysis capabilities"""
        await self.initialize()

        results = {}

        for query in test_queries:
            try:
                async with self.session.post(
                    f"{self.base_url}/api/workflow-agent/analyze",
                    json={"user_input": query, "user_id": "test_user"},
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results[query] = {
                            "success": True,
                            "is_workflow_request": data.get(
                                "is_workflow_request", False
                            ),
                            "trigger": data.get("trigger"),
                            "actions": data.get("actions", []),
                            "workflow_id": data.get("workflow_id"),
                        }
                    else:
                        results[query] = {
                            "success": False,
                            "error": f"HTTP {response.status}",
                        }
            except Exception as e:
                results[query] = {"success": False, "error": str(e)}

        return results

    def analyze_service_workflow_integration(self) -> Dict[str, IntegrationStatus]:
        """Analyze which services are integrated with workflow automation"""
        integration_status = {}

        # Get all services used in workflow templates
        workflow_services = set()
        service_workflow_steps = {}

        for template in self.workflow_templates:
            for step in template.steps:
                workflow_services.add(step.service)
                if step.service not in service_workflow_steps:
                    service_workflow_steps[step.service] = []
                service_workflow_steps[step.service].append(
                    f"{template.name}: {step.name}"
                )

        # Check integration status for each service
        for service_id, service in self.services.items():
            has_workflow_integration = service_id in workflow_services
            workflow_steps = service_workflow_steps.get(service_id, [])

            # Determine NLU support based on service type and capabilities
            has_nlu_support = self._determine_nlu_support(service)
            nlu_capabilities = self._get_nlu_capabilities(service)

            # Determine overall status
            if has_workflow_integration and has_nlu_support:
                status = "✅ Fully Integrated"
            elif has_workflow_integration and not has_nlu_support:
                status = "⚠️ Partial Integration (Workflow Only)"
            elif not has_workflow_integration and has_nlu_support:
                status = "⚠️ Partial Integration (NLU Only)"
            else:
                status = "❌ Not Integrated"

            integration_status[service_id] = IntegrationStatus(
                service_id=service_id,
                service_name=service.name,
                has_workflow_integration=has_workflow_integration,
                has_nlu_support=has_nlu_support,
                workflow_steps=workflow_steps,
                nlu_capabilities=nlu_capabilities,
                status=status,
            )

        return integration_status

    def _determine_nlu_support(self, service: ServiceInfo) -> bool:
        """Determine if a service has NLU support"""
        # Core services that should have NLU support
        core_services = {
            "calendar",
            "tasks",
            "email",
            "slack",
            "teams",
            "discord",
            "notion",
            "dropbox",
            "gdrive",
            "github",
            "workflow",
            "notifications",
        }

        # Services with specific capabilities that indicate NLU support
        nlu_capable_services = {
            "calendar": ["create_event", "find_availability"],
            "tasks": ["create_task", "update_task"],
            "email": ["send_email", "search_emails"],
            "slack": ["send_message", "search_messages"],
            "teams": ["send_message"],
            "discord": ["send_message"],
            "notion": ["create_page", "search_pages"],
            "dropbox": ["upload_file", "share_file"],
            "gdrive": ["upload_file"],
            "github": ["create_issue", "search_code"],
            "workflow": ["create_workflow", "execute_workflow"],
            "notifications": ["send_notification"],
        }

        return (
            service.id in core_services
            and service.id in nlu_capable_services
            and any(
                cap in service.capabilities for cap in nlu_capable_services[service.id]
            )
        )

    def _get_nlu_capabilities(self, service: ServiceInfo) -> List[str]:
        """Get NLU capabilities for a service"""
        nlu_capability_map = {
            "calendar": ["schedule meetings", "find availability", "create events"],
            "tasks": ["create tasks", "update tasks", "list tasks"],
            "email": ["send emails", "search emails", "manage inbox"],
            "slack": ["send messages", "search messages", "manage channels"],
            "teams": ["send messages", "manage teams"],
            "discord": ["send messages", "manage channels"],
            "notion": ["create pages", "search pages", "update content"],
            "dropbox": ["upload files", "share files", "manage storage"],
            "gdrive": ["upload files", "manage documents", "share files"],
            "github": ["create issues", "search code", "manage repositories"],
            "workflow": [
                "create workflows",
                "execute workflows",
                "schedule automations",
            ],
            "notifications": ["send notifications", "manage preferences"],
        }

        return nlu_capability_map.get(service.id, [])

    def identify_integration_gaps(
        self, integration_status: Dict[str, IntegrationStatus]
    ) -> List[str]:
        """Identify gaps in integration"""
        gaps = []

        for service_id, status in integration_status.items():
            if not status.has_workflow_integration and not status.has_nlu_support:
                gaps.append(
                    f"Service '{status.service_name}' ({service_id}) has no integration"
                )
            elif not status.has_workflow_integration:
                gaps.append(
                    f"Service '{status.service_name}' ({service_id}) missing workflow integration"
                )
            elif not status.has_nlu_support:
                gaps.append(
                    f"Service '{status.service_name}' ({service_id}) missing NLU support"
                )

        return gaps

    def generate_integration_report(
        self,
        integration_status: Dict[str, IntegrationStatus],
        nlu_test_results: Dict[str, Any],
    ) -> str:
        """Generate a comprehensive integration report"""
        report = []
        report.append("=" * 80)
        report.append("🚀 ATOM WORKFLOW AUTOMATION INTEGRATION VERIFICATION REPORT")
        report.append("=" * 80)
        report.append("")

        # Summary section
        total_services = len(integration_status)
        fully_integrated = sum(
            1 for s in integration_status.values() if s.status == "✅ Fully Integrated"
        )
        partial_integrated = sum(
            1 for s in integration_status.values() if "⚠️" in s.status
        )
        not_integrated = sum(
            1 for s in integration_status.values() if s.status == "❌ Not Integrated"
        )

        report.append("📊 INTEGRATION SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Services: {total_services}")
        report.append(f"✅ Fully Integrated: {fully_integrated}")
        report.append(f"⚠️ Partial Integration: {partial_integrated}")
        report.append(f"❌ Not Integrated: {not_integrated}")
        report.append(
            f"Integration Coverage: {fully_integrated}/{total_services} ({fully_integrated / total_services * 100:.1f}%)"
        )
        report.append("")

        # Service details section
        report.append("🔧 SERVICE INTEGRATION DETAILS")
        report.append("-" * 40)

        for service_id, status in sorted(
            integration_status.items(), key=lambda x: x[1].status
        ):
            report.append(f"\n{status.status} - {status.service_name} ({service_id})")
            if status.has_workflow_integration:
                report.append(f"  📋 Workflow Steps: {len(status.workflow_steps)}")
                for step in status.workflow_steps[:3]:  # Show first 3 steps
                    report.append(f"    • {step}")
                if len(status.workflow_steps) > 3:
                    report.append(
                        f"    • ... and {len(status.workflow_steps) - 3} more"
                    )
            if status.has_nlu_support:
                report.append(
                    f"  🧠 NLU Capabilities: {', '.join(status.nlu_capabilities)}"
                )

        # NLU test results section
        report.append("\n🧠 NLU WORKFLOW ANALYSIS TEST RESULTS")
        report.append("-" * 40)

        successful_tests = sum(
            1 for result in nlu_test_results.values() if result.get("success", False)
        )
        total_tests = len(nlu_test_results)

        report.append(
            f"NLU Test Success Rate: {successful_tests}/{total_tests} ({successful_tests / total_tests * 100:.1f}%)"
        )
        report.append("")

        for query, result in nlu_test_results.items():
            if result.get("success", False):
                if result.get("is_workflow_request", False):
                    report.append(f"✅ '{query}' → Workflow detected")
                    if result.get("workflow_id"):
                        report.append(f"   Created workflow: {result['workflow_id']}")
                else:
                    report.append(f"ℹ️  '{query}' → Not a workflow request")
            else:
                report.append(
                    f"❌ '{query}' → Failed: {result.get('error', 'Unknown error')}"
                )

        # Integration gaps section
        gaps = self.identify_integration_gaps(integration_status)
        if gaps:
            report.append("\n⚠️ INTEGRATION GAPS IDENTIFIED")
            report.append("-" * 40)
            for gap in gaps:
                report.append(f"• {gap}")
        else:
            report.append("\n✅ NO INTEGRATION GAPS IDENTIFIED")
            report.append("-" * 40)
            report.append(
                "All services are properly integrated with workflow automation and NLU system!"
            )

        report.append("\n" + "=" * 80)
        report.append("🎯 RECOMMENDATIONS")
        report.append("-" * 40)

        if not_integrated > 0:
            report.append("1. Add workflow templates for non-integrated services")
            report.append(
                "2. Ensure NLU agents can recognize service-specific commands"
            )

        if partial_integrated > 0:
            report.append("3. Complete integration for partially integrated services")

        report.append("4. Test with real service credentials for end-to-end validation")
        report.append("5. Monitor workflow execution and NLU accuracy in production")

        report.append("\n" + "=" * 80)
        report.append("✅ VERIFICATION COMPLETE")
        report.append("=" * 80)

        return "\n".join(report)

    async def run_comprehensive_verification(self) -> bool:
        """Run comprehensive integration verification"""
        logger.info("🚀 Starting comprehensive integration verification...")

        try:
            # Step 1: Fetch services and workflow templates
            await self.fetch_services()
            await self.fetch_workflow_templates()

            if not self.services:
                logger.error("❌ No services found - cannot proceed with verification")
                return False

            # Step 2: Analyze integration status
            integration_status = self.analyze_service_workflow_integration()

            # Step 3: Test NLU workflow analysis
            test_queries = [
                "Schedule a meeting with the team next Monday at 2 PM",
                "Create a task to follow up with clients and notify me on Slack",
                "Upload the quarterly report to Dropbox and share it with the team",
                "What's the weather today?",  # This should NOT be a workflow request
                "When I receive an email from boss@company.com, create a task in Asana and notify me",
            ]

            nlu_test_results = await self.test_nlu_workflow_analysis(test_queries)

            # Step 4: Generate and print report
            report = self.generate_integration_report(
                integration_status, nlu_test_results
            )
            print(report)

            # Determine overall success
            total_services = len(integration_status)
            fully_integrated = sum(
                1
                for s in integration_status.values()
                if s.status == "✅ Fully Integrated"
            )

            success_threshold = 0.8  # 80% of services should be fully integrated
            success_rate = fully_integrated / total_services

            if success_rate >= success_threshold:
                logger.info(
                    f"✅ Integration verification PASSED ({success_rate:.1%} coverage)"
                )
                return True
            else:
                logger.warning(
                    f"⚠️ Integration verification PARTIAL ({success_rate:.1%} coverage)"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Integration verification FAILED: {str(e)}")
            return False
        finally:
            await self.close()


async def main():
    """Main function"""
    verifier = IntegrationVerifier()
    success = await verifier.run_comprehensive_verification()

    if success:
        print("\n🎉 ATOM workflow automation integration is READY for production!")
        sys.exit(0)
    else:
        print(
            "\n⚠️ Some integration issues need attention before production deployment."
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
