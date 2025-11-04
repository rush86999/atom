#!/usr/bin/env python3
"""
Simplified Verification Script for Atom Workflow Automation System
This script verifies the core workflow automation components without requiring the full backend server.
"""

import os
import sys
import logging
from typing import Dict, List, Any

# Add backend to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleWorkflowVerifier:
    """Simplified verification for workflow automation system"""

    def __init__(self):
        self.verification_results = {}

    def verify_workflow_execution_service(self) -> bool:
        """Verify workflow execution service components"""
        try:
            # Test import of workflow execution service
            from workflow_execution_service import workflow_execution_service

            # Check service registry
            if not hasattr(workflow_execution_service, "service_registry"):
                logger.error("Workflow execution service not properly initialized")
                return False

            # Check required services
            required_services = [
                "calendar",
                "tasks",
                "messages",
                "email",
                "documents",
                "asana",
                "trello",
                "notion",
                "dropbox",
            ]

            for service in required_services:
                if service not in workflow_execution_service.service_registry:
                    logger.error(f"Service {service} not found in registry")
                    return False

            logger.info("✅ Workflow execution service verified")
            return True

        except Exception as e:
            logger.error(f"Workflow execution service verification failed: {e}")
            return False

    def verify_workflow_api_module(self) -> bool:
        """Verify workflow API module is available"""
        try:
            from workflow_api import WORKFLOW_TEMPLATES, workflow_api_bp

            # Check workflow templates
            required_templates = [
                "meeting_scheduler",
                "task_automation",
                "document_workflow",
            ]
            for template_id in required_templates:
                if template_id not in WORKFLOW_TEMPLATES:
                    logger.error(f"Required template {template_id} not found")
                    return False

            # Check blueprint
            if not hasattr(workflow_api_bp, "name"):
                logger.error("Workflow API blueprint not properly initialized")
                return False

            logger.info("✅ Workflow API module verified")
            return True

        except Exception as e:
            logger.error(f"Workflow API module verification failed: {e}")
            return False

    def verify_frontend_components(self) -> bool:
        """Verify frontend workflow components exist"""
        try:
            frontend_components = [
                "frontend-nextjs/components/WorkflowAutomation.tsx",
                "frontend-nextjs/components/ServiceIntegrationDashboard.tsx",
                "frontend-nextjs/components/Dashboard.tsx",
            ]

            for component_path in frontend_components:
                if not os.path.exists(component_path):
                    logger.error(f"Frontend component {component_path} not found")
                    return False

            # Check Dashboard integration
            with open("frontend-nextjs/components/Dashboard.tsx", "r") as f:
                dashboard_content = f.read()

            required_imports = ["WorkflowAutomation", "ServiceIntegrationDashboard"]
            for import_name in required_imports:
                if import_name not in dashboard_content:
                    logger.error(f"Dashboard missing import: {import_name}")
                    return False

            required_tabs = ["Workflow Automation", "Service Integrations"]
            for tab_name in required_tabs:
                if tab_name not in dashboard_content:
                    logger.error(f"Dashboard missing tab: {tab_name}")
                    return False

            logger.info("✅ Frontend components verified")
            return True

        except Exception as e:
            logger.error(f"Frontend components verification failed: {e}")
            return False

    def verify_deployment_assets(self) -> bool:
        """Verify deployment assets exist"""
        try:
            deployment_assets = [
                "deploy_workflow_automation.sh",
                "backend/python-api/workflows/celery_app.py",
                "backend/python-api/workflows/workflows/tasks.py",
            ]

            for asset_path in deployment_assets:
                if not os.path.exists(asset_path):
                    logger.error(f"Deployment asset {asset_path} not found")
                    return False

            # Check deployment script content
            with open("deploy_workflow_automation.sh", "r") as f:
                script_content = f.read()

            required_components = [
                "workflow_execution_service",
                "WORKFLOW_TEMPLATES",
                "celery_app",
                "create_workflow_tables",
            ]

            for component in required_components:
                if component not in script_content:
                    logger.error(f"Deployment script missing component: {component}")
                    return False

            logger.info("✅ Deployment assets verified")
            return True

        except Exception as e:
            logger.error(f"Deployment assets verification failed: {e}")
            return False

    def verify_service_integration(self) -> bool:
        """Verify service integration components"""
        try:
            # Check real service implementations
            real_service_files = [
                "backend/python-api-service/asana_service_real.py",
                "backend/python-api-service/trello_service_real.py",
                "backend/python-api-service/notion_service_real.py",
                "backend/python-api-service/dropbox_service_real.py",
            ]

            for service_file in real_service_files:
                if not os.path.exists(service_file):
                    logger.error(
                        f"Real service implementation {service_file} not found"
                    )
                    return False

            logger.info("✅ Service integration verified")
            return True

        except Exception as e:
            logger.error(f"Service integration verification failed: {e}")
            return False

    def run_verification(self) -> Dict[str, bool]:
        """Run all verification tests"""
        print("🚀 Starting Simplified Workflow Automation Verification")
        print("=" * 60)

        verification_tests = [
            ("Workflow Execution Service", self.verify_workflow_execution_service),
            ("Workflow API Module", self.verify_workflow_api_module),
            ("Frontend Components", self.verify_frontend_components),
            ("Deployment Assets", self.verify_deployment_assets),
            ("Service Integration", self.verify_service_integration),
        ]

        results = {}

        for test_name, test_function in verification_tests:
            print(f"🔍 Testing: {test_name}...")
            try:
                result = test_function()
                results[test_name] = result
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"   {status}: {test_name}")
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                results[test_name] = False
                print(f"   ❌ FAIL: {test_name} (Exception)")

        return results

    def generate_report(self, results: Dict[str, bool]) -> str:
        """Generate a comprehensive verification report"""
        total_tests = len(results)
        passed_tests = sum(results.values())
        success_rate = (passed_tests / total_tests) * 100

        report = []
        report.append("📊 SIMPLIFIED WORKFLOW AUTOMATION VERIFICATION REPORT")
        report.append("=" * 60)
        report.append(f"Total Tests: {total_tests}")
        report.append(f"Passed: {passed_tests}")
        report.append(f"Failed: {total_tests - passed_tests}")
        report.append(f"Success Rate: {success_rate:.1f}%")
        report.append("")
        report.append("📋 Test Results:")
        report.append("-" * 30)

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            report.append(f"{status}: {test_name}")

        report.append("")
        report.append("🎯 System Status:")
        report.append("-" * 20)

        if success_rate >= 80:
            report.append("✅ Workflow automation system is READY FOR DEPLOYMENT!")
            report.append("")
            report.append("📝 Next Steps:")
            report.append("   1. Set up environment variables (.env file)")
            report.append(
                "   2. Start database: docker-compose -f docker-compose.postgres.yml up -d"
            )
            report.append("   3. Deploy: ./deploy_workflow_automation.sh")
            report.append("   4. Access UI: http://localhost:3000")
            report.append("   5. Navigate to Workflow Automation tab")
        else:
            failed_tests = [name for name, result in results.items() if not result]
            report.append("⚠️  System needs attention before deployment:")
            for failed_test in failed_tests:
                report.append(f"   - Fix: {failed_test}")

        return "\n".join(report)


def main():
    """Main verification function"""
    verifier = SimpleWorkflowVerifier()

    try:
        # Run verification
        results = verifier.run_verification()

        # Generate and print report
        report = verifier.generate_report(results)
        print("\n" + "=" * 60)
        print(report)
        print("=" * 60)

        # Exit with appropriate code
        success_rate = (sum(results.values()) / len(results)) * 100
        if success_rate >= 80:
            print(
                "\n🎉 Workflow automation system verification completed successfully!"
            )
            sys.exit(0)
        else:
            print("\n❌ Workflow automation system needs attention.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Verification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error during verification: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
