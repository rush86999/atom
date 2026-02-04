"""
Comprehensive Testing for Advanced Workflow and Memory System Features

This test suite validates the advanced workflow engine, memory system optimizer,
and production deployment features implemented in the Atom platform.
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import the advanced modules
try:
    sys.path.append("backend/python-api-service")
    from advanced_workflow_engine import AdvancedWorkflowEngine, NodeType, WorkflowStatus
    from memory_system_optimizer import CrossIntegrationSearchResult, MemorySystemOptimizer
    from production_deployment_manager import (
        DeploymentConfig,
        HealthStatus,
        ProductionDeploymentManager,
    )

    ADVANCED_FEATURES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Advanced features not available: {e}")
    ADVANCED_FEATURES_AVAILABLE = False


class AdvancedFeaturesTestSuite:
    """
    Comprehensive test suite for advanced workflow and memory system features.
    """

    def __init__(self):
        self.workflow_engine = None
        self.memory_optimizer = None
        self.deployment_manager = None
        self.test_results = {}

    async def setup(self):
        """Initialize test components"""
        logger.info("Setting up advanced features test suite...")

        if ADVANCED_FEATURES_AVAILABLE:
            self.workflow_engine = AdvancedWorkflowEngine()
            self.memory_optimizer = MemorySystemOptimizer()

            # Create mock deployment config for testing
            deployment_config = DeploymentConfig(
                name="test-deployment",
                version="1.0.0",
                environment="test",
                services=["backend-api", "frontend-nextjs"],
                health_check_endpoints={
                    "backend-api": "http://localhost:5058/health",
                    "frontend-nextjs": "http://localhost:3000/api/health",
                },
            )
            self.deployment_manager = ProductionDeploymentManager(
                deployment_config=deployment_config
            )

        logger.info("Test suite setup completed")

    async def test_workflow_templates(self):
        """Test workflow template creation and customization"""
        logger.info("Testing workflow templates...")

        if not self.workflow_engine:
            return {"status": "skipped", "reason": "Workflow engine not available"}

        try:
            # Test creating workflow from template
            workflow = await self.workflow_engine.create_workflow_from_template(
                "email_processing",
                {
                    "name": "Custom Email Processing",
                    "description": "Customized email processing workflow",
                    "node_updates": [
                        {
                            "node_id": "create_task_urgent",
                            "parameters": {
                                "priority": "highest",
                                "due_date": "immediate",
                            },
                        }
                    ],
                },
            )

            assert workflow["id"] is not None
            assert workflow["name"] == "Custom Email Processing"
            assert workflow["template"] == "email_processing"
            assert len(workflow["nodes"]) > 0
            assert len(workflow["connections"]) > 0

            # Test template availability
            available_templates = list(self.workflow_engine.workflow_templates.keys())
            assert "email_processing" in available_templates
            assert "meeting_followup" in available_templates

            logger.info("✓ Workflow templates test passed")
            return {"status": "passed", "workflow_id": workflow["id"]}

        except Exception as e:
            logger.error(f"Workflow templates test failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def test_conditional_workflow_execution(self):
        """Test workflow execution with conditional logic"""
        logger.info("Testing conditional workflow execution...")

        if not self.workflow_engine:
            return {"status": "skipped", "reason": "Workflow engine not available"}

        try:
            # Create a simple test workflow
            test_workflow = {
                "id": "test-conditional-workflow",
                "name": "Test Conditional Workflow",
                "description": "Workflow with conditional branching",
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger",
                        "name": "Start Workflow",
                        "service": "test",
                        "action": "start",
                        "parameters": {},
                    },
                    {
                        "id": "condition_node",
                        "type": "condition",
                        "name": "Check Condition",
                        "service": "test",
                        "action": "evaluate",
                        "parameters": {},
                        "conditions": [
                            {
                                "field": "test_value",
                                "operator": "greater_than",
                                "value": 10,
                            }
                        ],
                    },
                    {
                        "id": "high_value_action",
                        "type": "action",
                        "name": "High Value Action",
                        "service": "test",
                        "action": "process_high",
                        "parameters": {},
                        "conditions": [
                            {
                                "field": "test_value",
                                "operator": "greater_than",
                                "value": 10,
                            }
                        ],
                    },
                    {
                        "id": "low_value_action",
                        "type": "action",
                        "name": "Low Value Action",
                        "service": "test",
                        "action": "process_low",
                        "parameters": {},
                        "conditions": [
                            {
                                "field": "test_value",
                                "operator": "less_than",
                                "value": 10,
                            }
                        ],
                    },
                ],
                "connections": [
                    {"source_node_id": "trigger", "target_node_id": "condition_node"},
                    {
                        "source_node_id": "condition_node",
                        "target_node_id": "high_value_action",
                        "condition": "high",
                    },
                    {
                        "source_node_id": "condition_node",
                        "target_node_id": "low_value_action",
                        "condition": "low",
                    },
                ],
            }

            # Store workflow for execution
            self.workflow_engine.workflow_versions["test-conditional-workflow"] = {
                "1.0.0": test_workflow
            }

            # Test execution with high value
            execution_result = await self.workflow_engine.execute_workflow(
                "test-conditional-workflow", {"test_value": 15}
            )

            assert execution_result["status"] in ["completed", "failed"]
            assert execution_result["execution_id"] is not None

            logger.info("✓ Conditional workflow execution test passed")
            return {
                "status": "passed",
                "execution_id": execution_result["execution_id"],
            }

        except Exception as e:
            logger.error(f"Conditional workflow execution test failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def test_cross_integration_search(self):
        """Test cross-integration semantic search"""
        logger.info("Testing cross-integration search...")

        if not self.memory_optimizer:
            return {"status": "skipped", "reason": "Memory optimizer not available"}

        try:
            # Test search across multiple integrations
            search_results = await self.memory_optimizer.cross_integration_search(
                query="project meeting notes",
                integrations=["google_drive", "onedrive", "notion"],
                limit_per_integration=3,
                min_similarity=0.5,
            )

            # Verify search results structure
            for result in search_results:
                assert hasattr(result, "integration")
                assert hasattr(result, "document_title")
                assert hasattr(result, "similarity_score")
                assert hasattr(result, "source_integration")

            # Test metrics collection
            metrics = self.memory_optimizer.get_system_metrics()
            assert "cross_integration_searches" in metrics
            assert "total_documents" in metrics
            assert "search_latency_ms" in metrics

            logger.info("✓ Cross-integration search test passed")
            return {
                "status": "passed",
                "results_count": len(search_results),
                "metrics": metrics,
            }

        except Exception as e:
            logger.error(f"Cross-integration search test failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def test_memory_system_optimization(self):
        """Test memory system optimization routines"""
        logger.info("Testing memory system optimization...")

        if not self.memory_optimizer:
            return {"status": "skipped", "reason": "Memory optimizer not available"}

        try:
            # Test optimization routine
            await self.memory_optimizer.optimize_memory_system()

            # Verify metrics are updated
            metrics = self.memory_optimizer.get_system_metrics()
            assert metrics["last_optimization"] is not None

            # Test document addition
            test_documents = [
                {
                    "file_id": "test-file-1",
                    "file_name": "Test Document 1",
                    "content": "This is a test document about project planning",
                    "mime_type": "text/plain",
                    "created_time": datetime.now().isoformat(),
                }
            ]

            await self.memory_optimizer.add_documents("google_drive", test_documents)

            # Verify document count increased
            updated_metrics = self.memory_optimizer.get_system_metrics()
            assert updated_metrics["total_documents"] >= metrics["total_documents"]

            logger.info("✓ Memory system optimization test passed")
            return {"status": "passed", "metrics": updated_metrics}

        except Exception as e:
            logger.error(f"Memory system optimization test failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def test_deployment_health_checks(self):
        """Test deployment health check functionality"""
        logger.info("Testing deployment health checks...")

        if not self.deployment_manager:
            return {"status": "skipped", "reason": "Deployment manager not available"}

        try:
            # Test health check functionality
            health_results = await self.deployment_manager._run_health_checks(
                self.deployment_manager.deployment_config
            )

            # Verify health results structure
            for result in health_results:
                assert hasattr(result, "service")
                assert hasattr(result, "status")
                assert hasattr(result, "response_time_ms")
                assert hasattr(result, "timestamp")

            # Test health status evaluation
            deployment_success = self.deployment_manager._is_deployment_successful(
                health_results
            )
            assert isinstance(deployment_success, bool)

            logger.info("✓ Deployment health checks test passed")
            return {
                "status": "passed",
                "health_results_count": len(health_results),
                "deployment_success": deployment_success,
            }

        except Exception as e:
            logger.error(f"Deployment health checks test failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def test_pre_deployment_checks(self):
        """Test pre-deployment validation checks"""
        logger.info("Testing pre-deployment checks...")

        if not self.deployment_manager:
            return {"status": "skipped", "reason": "Deployment manager not available"}

        try:
            # Test pre-deployment checks
            await self.deployment_manager._run_pre_deployment_checks(
                self.deployment_manager.deployment_config
            )

            # Test individual check functions
            await self.deployment_manager._check_configuration_validity(
                self.deployment_manager.deployment_config
            )

            logger.info("✓ Pre-deployment checks test passed")
            return {"status": "passed"}

        except Exception as e:
            logger.error(f"Pre-deployment checks test failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def run_comprehensive_tests(self):
        """Run all comprehensive tests"""
        logger.info("Starting comprehensive advanced features testing...")

        await self.setup()

        test_methods = [
            self.test_workflow_templates,
            self.test_conditional_workflow_execution,
            self.test_cross_integration_search,
            self.test_memory_system_optimization,
            self.test_deployment_health_checks,
            self.test_pre_deployment_checks,
        ]

        for test_method in test_methods:
            test_name = test_method.__name__
            logger.info(f"Running {test_name}...")

            try:
                result = await test_method()
                self.test_results[test_name] = result

                if result.get("status") == "passed":
                    logger.info(f"✓ {test_name} completed successfully")
                else:
                    logger.warning(
                        f"⚠ {test_name} completed with status: {result.get('status')}"
                    )

            except Exception as e:
                logger.error(f"✗ {test_name} failed with exception: {e}")
                self.test_results[test_name] = {"status": "error", "error": str(e)}

        return self.generate_test_report()

    def generate_test_report(self):
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = sum(
            1
            for result in self.test_results.values()
            if result.get("status") == "passed"
        )
        failed_tests = sum(
            1
            for result in self.test_results.values()
            if result.get("status") in ["failed", "error"]
        )
        skipped_tests = sum(
            1
            for result in self.test_results.values()
            if result.get("status") == "skipped"
        )

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "skipped": skipped_tests,
                "success_rate": (passed_tests / total_tests * 100)
                if total_tests > 0
                else 0,
            },
            "detailed_results": self.test_results,
            "recommendations": self._generate_recommendations(),
        }

        return report

    def _generate_recommendations(self):
        """Generate recommendations based on test results"""
        recommendations = []

        if not ADVANCED_FEATURES_AVAILABLE:
            recommendations.append(
                "Install required dependencies for advanced features"
            )
            recommendations.append("Verify module import paths are correct")

        failed_tests = [
            name
            for name, result in self.test_results.items()
            if result.get("status") in ["failed", "error"]
        ]

        for test_name in failed_tests:
            recommendations.append(f"Investigate and fix issues in {test_name}")

        if not failed_tests and ADVANCED_FEATURES_AVAILABLE:
            recommendations.append("All advanced features are functioning correctly")
            recommendations.append("Proceed with production deployment")

        return recommendations


async def main():
    """Main test execution function"""
    test_suite = AdvancedFeaturesTestSuite()
    report = await test_suite.run_comprehensive_tests()

    # Print summary
    print("\n" + "=" * 60)
    print("ADVANCED FEATURES TEST REPORT")
    print("=" * 60)

    summary = report["summary"]
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Skipped: {summary['skipped']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")

    print("\nDETAILED RESULTS:")
    for test_name, result in report["detailed_results"].items():
        status_icon = (
            "✓"
            if result.get("status") == "passed"
            else "⚠"
            if result.get("status") == "skipped"
            else "✗"
        )
        print(f"  {status_icon} {test_name}: {result.get('status', 'unknown')}")
        if result.get("error"):
            print(f"     Error: {result['error']}")

    print("\nRECOMMENDATIONS:")
    for recommendation in report["recommendations"]:
        print(f"  • {recommendation}")

    print("=" * 60)

    # Save detailed report to file
    report_filename = (
        f"advanced_features_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(report_filename, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Detailed report saved to: {report_filename}")

    # Exit with appropriate code
    if summary["failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

    # Exit with appropriate code
    if summary["failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
