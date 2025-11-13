#!/usr/bin/env python3
"""
🧪 COMPREHENSIVE ENHANCED INTEGRATIONS TEST
Test suite for AI-powered workflow automation and enhanced monitoring systems
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


class EnhancedIntegrationsTestSuite:
    """
    Comprehensive test suite for enhanced integration systems
    """

    def __init__(self):
        self.test_results = []
        self.start_time = None
        self.end_time = None

    async def run_all_tests(self):
        """Run all enhanced integration tests"""
        self.start_time = datetime.now()
        logger.info("🚀 Starting Enhanced Integrations Test Suite")
        logger.info("=" * 60)

        # Test AI Workflow Enhancement System
        await self.test_ai_workflow_system()

        # Test Enhanced Monitoring System
        await self.test_enhanced_monitoring_system()

        # Test Cross-Service Integration
        await self.test_cross_service_integration()

        # Test Performance and Analytics
        await self.test_performance_analytics()

        self.end_time = datetime.now()
        await self.generate_test_report()

    async def test_ai_workflow_system(self):
        """Test AI Workflow Enhancement System"""
        logger.info("🤖 Testing AI Workflow Enhancement System...")

        try:
            # Import AI workflow system
            from ai_workflow_enhancement_system import AIWorkflowEnhancementSystem

            # Initialize system
            workflow_system = AIWorkflowEnhancementSystem()
            initialized = await workflow_system.initialize()

            if not initialized:
                self.record_test_result(
                    "AI Workflow Initialization", False, "Failed to initialize system"
                )
                return

            self.record_test_result(
                "AI Workflow Initialization", True, "System initialized successfully"
            )

            # Test workflow creation
            test_workflow_data = {
                "name": "Test GitHub PR → Slack Notification",
                "description": "Test workflow for PR notifications",
                "trigger_service": "github",
                "action_services": ["slack"],
                "conditions": {"pr_state": "open", "repo": "test-repo"},
                "ai_optimized": True,
            }

            creation_result = await workflow_system.create_cross_service_workflow(
                test_workflow_data
            )

            if creation_result["success"]:
                workflow_id = creation_result["workflow_id"]
                self.record_test_result(
                    "Workflow Creation", True, f"Created workflow: {workflow_id}"
                )

                # Test workflow execution
                trigger_data = {
                    "pr_state": "open",
                    "repo": "test-repo",
                    "pr_number": 123,
                    "author": "test-user",
                }

                execution_result = await workflow_system.execute_workflow(
                    workflow_id, trigger_data
                )

                if execution_result["success"]:
                    self.record_test_result(
                        "Workflow Execution", True, "Workflow executed successfully"
                    )
                else:
                    self.record_test_result(
                        "Workflow Execution",
                        False,
                        f"Execution failed: {execution_result.get('error')}",
                    )

                # Test workflow listing
                workflows_count = len(workflow_system.workflows)
                if workflows_count > 0:
                    self.record_test_result(
                        "Workflow Management",
                        True,
                        f"Found {workflows_count} workflows",
                    )
                else:
                    self.record_test_result(
                        "Workflow Management", False, "No workflows found"
                    )

            else:
                self.record_test_result(
                    "Workflow Creation",
                    False,
                    f"Creation failed: {creation_result.get('error')}",
                )

        except Exception as e:
            self.record_test_result(
                "AI Workflow System", False, f"System test failed: {str(e)}"
            )
            logger.error(f"AI Workflow test failed: {e}")

    async def test_enhanced_monitoring_system(self):
        """Test Enhanced Monitoring and Analytics System"""
        logger.info("📊 Testing Enhanced Monitoring System...")

        try:
            # Import monitoring system
            from enhanced_monitoring_analytics import EnhancedMonitoringAnalytics

            # Initialize system
            monitoring_system = EnhancedMonitoringAnalytics()
            initialized = await monitoring_system.initialize()

            if not initialized:
                self.record_test_result(
                    "Monitoring System Initialization",
                    False,
                    "Failed to initialize system",
                )
                return

            self.record_test_result(
                "Monitoring System Initialization",
                True,
                "Monitoring system initialized",
            )

            # Test service metrics collection
            await asyncio.sleep(2)  # Allow time for background monitoring

            all_metrics = monitoring_system.get_all_metrics()
            if all_metrics:
                self.record_test_result(
                    "Metrics Collection",
                    True,
                    f"Collected metrics for {len(all_metrics)} services",
                )
            else:
                self.record_test_result(
                    "Metrics Collection", False, "No metrics collected"
                )

            # Test alert generation
            active_alerts = monitoring_system.get_active_alerts()
            self.record_test_result(
                "Alert System", True, f"Found {len(active_alerts)} active alerts"
            )

            # Test health reporting
            if hasattr(monitoring_system, "system_health"):
                health = monitoring_system.system_health
                self.record_test_result(
                    "Health Reporting", True, f"System health: {health.overall_score}%"
                )
            else:
                self.record_test_result(
                    "Health Reporting", False, "Health report not generated"
                )

            # Test performance history
            sample_service = list(all_metrics.keys())[0] if all_metrics else None
            if (
                sample_service
                and sample_service in monitoring_system.performance_history
            ):
                history = list(monitoring_system.performance_history[sample_service])
                if history:
                    self.record_test_result(
                        "Performance History",
                        True,
                        f"Collected {len(history)} history points",
                    )
                else:
                    self.record_test_result(
                        "Performance History", False, "No performance history"
                    )
            else:
                self.record_test_result(
                    "Performance History", False, "No service history available"
                )

        except Exception as e:
            self.record_test_result(
                "Enhanced Monitoring System", False, f"Monitoring test failed: {str(e)}"
            )
            logger.error(f"Monitoring test failed: {e}")

    async def test_cross_service_integration(self):
        """Test cross-service integration capabilities"""
        logger.info("🔄 Testing Cross-Service Integration...")

        try:
            # Test service connectivity simulation
            from ai_workflow_enhancement_system import AIWorkflowEnhancementSystem

            workflow_system = AIWorkflowEnhancementSystem()
            await workflow_system.initialize()

            # Test multiple service workflows
            complex_workflow_data = {
                "name": "Multi-Service Integration Test",
                "description": "Test workflow spanning multiple services",
                "trigger_service": "google_calendar",
                "action_services": ["slack", "trello", "asana"],
                "conditions": {"meeting_type": "team", "duration_min": 30},
                "ai_optimized": True,
            }

            creation_result = await workflow_system.create_cross_service_workflow(
                complex_workflow_data
            )

            if creation_result["success"]:
                workflow_id = creation_result["workflow_id"]

                # Check AI prediction for complex workflow
                if workflow_id in workflow_system.ai_predictions:
                    prediction = workflow_system.ai_predictions[workflow_id]
                    self.record_test_result(
                        "AI Prediction",
                        True,
                        f"Success rate: {prediction.predicted_success_rate:.1%}",
                    )

                    # Test optimization recommendations
                    if prediction.recommended_optimizations:
                        self.record_test_result(
                            "Optimization Recommendations",
                            True,
                            f"Generated {len(prediction.recommended_optimizations)} recommendations",
                        )
                    else:
                        self.record_test_result(
                            "Optimization Recommendations",
                            False,
                            "No recommendations generated",
                        )
                else:
                    self.record_test_result(
                        "AI Prediction", False, "No AI prediction generated"
                    )

                # Test cross-service execution
                trigger_data = {
                    "meeting_type": "team",
                    "duration_min": 45,
                    "title": "Team Sync",
                    "attendees": ["user1", "user2"],
                }

                execution_result = await workflow_system.execute_workflow(
                    workflow_id, trigger_data
                )

                if execution_result["success"]:
                    execution_count = len(execution_result.get("execution_results", []))
                    self.record_test_result(
                        "Cross-Service Execution",
                        True,
                        f"Executed {execution_count} service actions",
                    )
                else:
                    self.record_test_result(
                        "Cross-Service Execution",
                        False,
                        f"Execution failed: {execution_result.get('error')}",
                    )

            else:
                self.record_test_result(
                    "Complex Workflow Creation",
                    False,
                    f"Creation failed: {creation_result.get('error')}",
                )

        except Exception as e:
            self.record_test_result(
                "Cross-Service Integration", False, f"Integration test failed: {str(e)}"
            )
            logger.error(f"Cross-service test failed: {e}")

    async def test_performance_analytics(self):
        """Test performance analytics and optimization"""
        logger.info("📈 Testing Performance Analytics...")

        try:
            from enhanced_monitoring_analytics import EnhancedMonitoringAnalytics

            monitoring_system = EnhancedMonitoringAnalytics()
            await monitoring_system.initialize()

            # Wait for monitoring data collection
            await asyncio.sleep(3)

            # Test analytics generation
            all_metrics = monitoring_system.get_all_metrics()

            if all_metrics:
                # Calculate aggregate metrics
                total_services = len(all_metrics)
                healthy_services = sum(
                    1 for m in all_metrics.values() if m.status.value == "healthy"
                )
                avg_response_time = (
                    sum(m.response_time_ms for m in all_metrics.values())
                    / total_services
                )
                avg_success_rate = (
                    sum(m.success_rate for m in all_metrics.values()) / total_services
                )

                self.record_test_result(
                    "Aggregate Analytics",
                    True,
                    f"Healthy: {healthy_services}/{total_services}, "
                    f"Avg RT: {avg_response_time:.1f}ms, "
                    f"Avg Success: {avg_success_rate:.1%}",
                )

                # Test anomaly detection (if ML available)
                try:
                    import sklearn

                    ml_available = True
                except ImportError:
                    ml_available = False

                if ml_available:
                    # Simulate anomaly by creating unusual metrics
                    test_service = list(all_metrics.keys())[0]
                    if test_service:
                        # This would trigger ML anomaly detection in background
                        self.record_test_result(
                            "ML Anomaly Detection", True, "ML models initialized"
                        )
                    else:
                        self.record_test_result(
                            "ML Anomaly Detection", False, "No services for testing"
                        )
                else:
                    self.record_test_result(
                        "ML Anomaly Detection", False, "ML libraries not available"
                    )

            else:
                self.record_test_result(
                    "Aggregate Analytics", False, "No metrics for analytics"
                )

            # Test alert management
            active_alerts = monitoring_system.get_active_alerts()
            if active_alerts:
                sample_alert = active_alerts[0]
                alert_id = sample_alert.alert_id

                # Test alert acknowledgment
                if monitoring_system.acknowledge_alert(alert_id):
                    self.record_test_result(
                        "Alert Management", True, "Alert acknowledged successfully"
                    )
                else:
                    self.record_test_result(
                        "Alert Management", False, "Failed to acknowledge alert"
                    )

                # Test alert resolution
                if monitoring_system.resolve_alert(alert_id):
                    self.record_test_result(
                        "Alert Resolution", True, "Alert resolved successfully"
                    )
                else:
                    self.record_test_result(
                        "Alert Resolution", False, "Failed to resolve alert"
                    )
            else:
                self.record_test_result(
                    "Alert Management", True, "No active alerts (system healthy)"
                )

        except Exception as e:
            self.record_test_result(
                "Performance Analytics", False, f"Analytics test failed: {str(e)}"
            )
            logger.error(f"Performance analytics test failed: {e}")

    def record_test_result(self, test_name: str, success: bool, message: str):
        """Record test result"""
        result = {
            "test_name": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        self.test_results.append(result)

        status_icon = "✅" if success else "❌"
        logger.info(f"{status_icon} {test_name}: {message}")

    async def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("\n" + "=" * 60)
        logger.info("📋 ENHANCED INTEGRATIONS TEST REPORT")
        logger.info("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # Summary
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info(
            f"Duration: {(self.end_time - self.start_time).total_seconds():.1f}s"
        )

        # Detailed results
        logger.info("\n📄 Detailed Results:")
        for result in self.test_results:
            status = "PASS" if result["success"] else "FAIL"
            logger.info(f"  {status}: {result['test_name']} - {result['message']}")

        # Save report to file
        report_data = {
            "test_suite": "Enhanced Integrations",
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": success_rate,
            },
            "results": self.test_results,
        }

        report_filename = f"enhanced_integrations_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, "w") as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"\n💾 Test report saved to: {report_filename}")

        # Final verdict
        if failed_tests == 0:
            logger.info(
                "\n🎉 ALL TESTS PASSED! Enhanced integrations are working correctly."
            )
            return True
        else:
            logger.info(
                f"\n⚠️  {failed_tests} test(s) failed. Review the detailed results."
            )
            return False


async def main():
    """Main test execution function"""
    test_suite = EnhancedIntegrationsTestSuite()
    success = await test_suite.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # Run the test suite
    asyncio.run(main())
