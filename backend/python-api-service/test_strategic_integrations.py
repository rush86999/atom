#!/usr/bin/env python3
"""
🧪 STRATEGIC INTEGRATIONS TEST
Test suite for strategic new integrations framework and implementations
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


class StrategicIntegrationsTestSuite:
    """
    Comprehensive test suite for strategic new integrations
    """

    def __init__(self):
        self.test_results = []
        self.start_time = None
        self.end_time = None

    async def run_all_tests(self):
        """Run all strategic integrations tests"""
        self.start_time = datetime.now()
        logger.info("🚀 Starting Strategic Integrations Test Suite")
        logger.info("=" * 60)

        # Test Strategic Integrations Framework
        await self.test_strategic_framework()

        # Test GitLab CI/CD Integration
        await self.test_gitlab_ci_cd_integration()

        # Test Integration Prioritization
        await self.test_integration_prioritization()

        # Test ROI Analysis
        await self.test_roi_analysis()

        self.end_time = datetime.now()
        await self.generate_test_report()

    async def test_strategic_framework(self):
        """Test Strategic Integrations Framework"""
        logger.info("🎯 Testing Strategic Integrations Framework...")

        try:
            # Import strategic framework
            from strategic_integrations_framework import (
                IntegrationCategory,
                IntegrationPriority,
                StrategicIntegrationsFramework,
            )

            # Initialize framework
            framework = StrategicIntegrationsFramework()
            initialized = await framework.initialize()

            if not initialized:
                self.record_test_result(
                    "Strategic Framework Initialization",
                    False,
                    "Failed to initialize framework",
                )
                return

            self.record_test_result(
                "Strategic Framework Initialization",
                True,
                "Framework initialized successfully",
            )

            # Test integration catalog
            integration_count = len(framework.strategic_integrations)
            if integration_count > 0:
                self.record_test_result(
                    "Integration Catalog",
                    True,
                    f"Loaded {integration_count} strategic integrations",
                )
            else:
                self.record_test_result(
                    "Integration Catalog", False, "No integrations loaded"
                )

            # Test ROI analysis
            roi_count = len(framework.roi_analysis)
            if roi_count > 0:
                self.record_test_result(
                    "ROI Analysis",
                    True,
                    f"Generated ROI analysis for {roi_count} integrations",
                )
            else:
                self.record_test_result(
                    "ROI Analysis", False, "No ROI analysis generated"
                )

            # Test roadmap creation
            roadmap_count = len(framework.integration_roadmap)
            if roadmap_count > 0:
                self.record_test_result(
                    "Integration Roadmap",
                    True,
                    f"Created roadmap with {roadmap_count} items",
                )
            else:
                self.record_test_result(
                    "Integration Roadmap", False, "No roadmap created"
                )

            # Test category distribution
            categories = {}
            for integration in framework.strategic_integrations.values():
                category = integration.category.value
                if category not in categories:
                    categories[category] = 0
                categories[category] += 1

            if len(categories) >= 3:  # Should have multiple categories
                self.record_test_result(
                    "Category Distribution",
                    True,
                    f"Found integrations in {len(categories)} categories",
                )
            else:
                self.record_test_result(
                    "Category Distribution",
                    False,
                    f"Only {len(categories)} categories found",
                )

        except Exception as e:
            self.record_test_result(
                "Strategic Framework", False, f"Framework test failed: {str(e)}"
            )
            logger.error(f"Strategic framework test failed: {e}")

    async def test_gitlab_ci_cd_integration(self):
        """Test GitLab CI/CD Integration"""
        logger.info("🐙 Testing GitLab CI/CD Integration...")

        try:
            # Import GitLab integration
            from gitlab_ci_cd_integration import GitLabCICDIntegration

            # Initialize integration
            gitlab_integration = GitLabCICDIntegration()
            initialized = await gitlab_integration.initialize()

            if not initialized:
                self.record_test_result(
                    "GitLab Integration Initialization",
                    False,
                    "Failed to initialize GitLab integration",
                )
                return

            self.record_test_result(
                "GitLab Integration Initialization",
                True,
                "GitLab integration initialized successfully",
            )

            # Test project retrieval
            projects = await gitlab_integration.get_projects()
            if projects:
                self.record_test_result(
                    "Project Retrieval",
                    True,
                    f"Retrieved {len(projects)} GitLab projects",
                )
            else:
                self.record_test_result(
                    "Project Retrieval", False, "No projects retrieved"
                )

            # Test pipeline retrieval (if projects available)
            if projects:
                sample_project = projects[0]
                pipelines = await gitlab_integration.get_project_pipelines(
                    sample_project.project_id, limit=5
                )

                if pipelines is not None:  # Could be empty list
                    self.record_test_result(
                        "Pipeline Retrieval",
                        True,
                        f"Retrieved {len(pipelines)} pipelines for project {sample_project.project_id}",
                    )
                else:
                    self.record_test_result(
                        "Pipeline Retrieval", False, "Failed to retrieve pipelines"
                    )

                # Test job retrieval (if pipelines available)
                if pipelines:
                    sample_pipeline = pipelines[0]
                    jobs = await gitlab_integration.get_pipeline_jobs(
                        sample_project.project_id, sample_pipeline.pipeline_id
                    )

                    if jobs is not None:  # Could be empty list
                        self.record_test_result(
                            "Job Retrieval",
                            True,
                            f"Retrieved {len(jobs)} jobs for pipeline {sample_pipeline.pipeline_id}",
                        )
                    else:
                        self.record_test_result(
                            "Job Retrieval", False, "Failed to retrieve jobs"
                        )

            # Test pipeline triggering
            if projects:
                sample_project = projects[0]
                pipeline = await gitlab_integration.trigger_pipeline(
                    sample_project.project_id, ref="main"
                )

                if pipeline:
                    self.record_test_result(
                        "Pipeline Triggering",
                        True,
                        f"Successfully triggered pipeline {pipeline.pipeline_id}",
                    )
                else:
                    self.record_test_result(
                        "Pipeline Triggering", False, "Failed to trigger pipeline"
                    )

            # Test metrics calculation
            if gitlab_integration.pipelines:
                sample_pipeline_id = list(gitlab_integration.pipelines.keys())[0]
                metrics = await gitlab_integration.get_pipeline_metrics(
                    sample_pipeline_id
                )

                if metrics:
                    self.record_test_result(
                        "Metrics Calculation",
                        True,
                        f"Calculated metrics for pipeline {sample_pipeline_id}",
                    )
                else:
                    self.record_test_result(
                        "Metrics Calculation", False, "Failed to calculate metrics"
                    )

        except Exception as e:
            self.record_test_result(
                "GitLab CI/CD Integration", False, f"GitLab test failed: {str(e)}"
            )
            logger.error(f"GitLab integration test failed: {e}")

    async def test_integration_prioritization(self):
        """Test integration prioritization logic"""
        logger.info("📊 Testing Integration Prioritization...")

        try:
            from strategic_integrations_framework import StrategicIntegrationsFramework

            framework = StrategicIntegrationsFramework()
            await framework.initialize()

            # Test priority distribution
            priority_counts = {}
            for integration in framework.strategic_integrations.values():
                priority = integration.priority.value
                if priority not in priority_counts:
                    priority_counts[priority] = 0
                priority_counts[priority] += 1

            # Should have critical priority integrations
            if priority_counts.get("critical", 0) > 0:
                self.record_test_result(
                    "Priority Assignment",
                    True,
                    f"Found {priority_counts.get('critical', 0)} critical priority integrations",
                )
            else:
                self.record_test_result(
                    "Priority Assignment", False, "No critical priority integrations"
                )

            # Test roadmap prioritization
            if framework.integration_roadmap:
                # Check if roadmap is sorted by priority/business impact
                roadmap_priorities = [
                    integration.priority
                    for integration in framework.integration_roadmap
                ]

                # Should have high priority items first
                if any(p.value == "critical" for p in roadmap_priorities[:3]):
                    self.record_test_result(
                        "Roadmap Prioritization",
                        True,
                        "Roadmap properly prioritized with critical items first",
                    )
                else:
                    self.record_test_result(
                        "Roadmap Prioritization",
                        False,
                        "Roadmap not properly prioritized",
                    )

            else:
                self.record_test_result(
                    "Roadmap Prioritization", False, "No roadmap available"
                )

            # Test business impact scoring
            high_impact_integrations = [
                integration_id
                for integration_id, roi in framework.roi_analysis.items()
                if roi.business_impact_score >= 8.0
            ]

            if high_impact_integrations:
                self.record_test_result(
                    "Business Impact Scoring",
                    True,
                    f"Identified {len(high_impact_integrations)} high-impact integrations",
                )
            else:
                self.record_test_result(
                    "Business Impact Scoring",
                    False,
                    "No high-impact integrations identified",
                )

        except Exception as e:
            self.record_test_result(
                "Integration Prioritization",
                False,
                f"Prioritization test failed: {str(e)}",
            )
            logger.error(f"Integration prioritization test failed: {e}")

    async def test_roi_analysis(self):
        """Test ROI analysis calculations"""
        logger.info("💰 Testing ROI Analysis...")

        try:
            from strategic_integrations_framework import StrategicIntegrationsFramework

            framework = StrategicIntegrationsFramework()
            await framework.initialize()

            # Test ROI data completeness
            incomplete_roi = 0
            for integration_id, roi in framework.roi_analysis.items():
                if (
                    roi.development_cost <= 0
                    or roi.estimated_annual_value <= 0
                    or roi.payback_period_months <= 0
                ):
                    incomplete_roi += 1

            if incomplete_roi == 0:
                self.record_test_result(
                    "ROI Data Completeness",
                    True,
                    "All ROI analyses have complete data",
                )
            else:
                self.record_test_result(
                    "ROI Data Completeness",
                    False,
                    f"{incomplete_roi} integrations have incomplete ROI data",
                )

            # Test payback period calculation
            reasonable_payback = 0
            for roi in framework.roi_analysis.values():
                # Payback period should be reasonable (less than 12 months for high-value integrations)
                if (
                    roi.estimated_annual_value > 50000
                    and roi.payback_period_months <= 12
                ):
                    reasonable_payback += 1

            if reasonable_payback > 0:
                self.record_test_result(
                    "Payback Period Analysis",
                    True,
                    f"Found {reasonable_payback} integrations with reasonable payback periods",
                )
            else:
                self.record_test_result(
                    "Payback Period Analysis",
                    False,
                    "No integrations with reasonable payback periods",
                )

            # Test business impact distribution
            impact_scores = [
                roi.business_impact_score for roi in framework.roi_analysis.values()
            ]
            avg_impact = sum(impact_scores) / len(impact_scores) if impact_scores else 0

            if avg_impact >= 6.0:  # Should have decent average impact
                self.record_test_result(
                    "Business Impact Distribution",
                    True,
                    f"Average business impact score: {avg_impact:.1f}",
                )
            else:
                self.record_test_result(
                    "Business Impact Distribution",
                    False,
                    f"Low average business impact score: {avg_impact:.1f}",
                )

            # Test development cost estimation
            total_development_cost = sum(
                roi.development_cost for roi in framework.roi_analysis.values()
            )
            total_estimated_value = sum(
                roi.estimated_annual_value for roi in framework.roi_analysis.values()
            )

            if total_estimated_value > total_development_cost:
                self.record_test_result(
                    "Cost-Benefit Analysis",
                    True,
                    f"Total estimated value (${total_estimated_value:,.0f}) exceeds development cost (${total_development_cost:,.0f})",
                )
            else:
                self.record_test_result(
                    "Cost-Benefit Analysis",
                    False,
                    f"Development cost (${total_development_cost:,.0f}) exceeds estimated value (${total_estimated_value:,.0f})",
                )

        except Exception as e:
            self.record_test_result(
                "ROI Analysis", False, f"ROI analysis test failed: {str(e)}"
            )
            logger.error(f"ROI analysis test failed: {e}")

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
        logger.info("📋 STRATEGIC INTEGRATIONS TEST REPORT")
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
            "test_suite": "Strategic Integrations",
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

        report_filename = f"strategic_integrations_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, "w") as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"\n💾 Test report saved to: {report_filename}")

        # Final verdict
        if failed_tests == 0:
            logger.info(
                "\n🎉 ALL TESTS PASSED! Strategic integrations are working correctly."
            )
            return True
        elif success_rate >= 80:
            logger.info(
                f"\n⚠️  {failed_tests} test(s) failed but overall system is functional (success rate: {success_rate:.1f}%)."
            )
            return True
        else:
            logger.info(
                f"\n❌ {failed_tests} test(s) failed. System needs attention (success rate: {success_rate:.1f}%)."
            )
            return False


async def main():
    """Main test execution function"""
    test_suite = StrategicIntegrationsTestSuite()
    success = await test_suite.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # Run the test suite
    asyncio.run(main())
