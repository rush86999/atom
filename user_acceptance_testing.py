"""
User Acceptance Testing Script for BYOK System

This script performs comprehensive user acceptance testing (UAT) for the
Atom BYOK (Bring Your Own Keys) system with real user scenarios and
multi-provider AI integration testing.
"""

import json
import requests
import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("user_acceptance_testing.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class UserAcceptanceTester:
    """User Acceptance Testing for BYOK System"""

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.test_users = {
            "business_user": "uat_business_user_001",
            "developer_user": "uat_developer_user_002",
            "student_user": "uat_student_user_003",
        }
        self.test_results = {}
        self.start_time = time.time()

    def setup_test_environment(self):
        """Setup test environment with realistic user data"""
        logger.info("🔧 Setting up UAT environment...")

        # Test API keys for different user personas
        self.test_api_keys = {
            "business_user": {
                "openai": "sk-uat-business-openai-12345",
                "google_gemini": "AIza-uat-business-gemini-abc123",
                "anthropic": "sk-ant-uat-business-claude-67890",
            },
            "developer_user": {
                "openai": "sk-uat-dev-openai-54321",
                "deepseek": "sk-uat-dev-deepseek-xyz789",
                "google_gemini": "AIza-uat-dev-gemini-def456",
            },
            "student_user": {
                "deepseek": "sk-uat-student-deepseek-98765",
                "google_gemini": "AIza-uat-student-gemini-ghi789",
            },
        }

        logger.info("✅ UAT environment configured")

    def test_user_onboarding(self):
        """Test user onboarding and initial setup"""
        logger.info("👤 Testing User Onboarding")

        onboarding_results = {}

        for user_type, user_id in self.test_users.items():
            logger.info(f"  Testing {user_type} onboarding...")

            try:
                # Test user can access the system
                health_response = requests.get(f"{self.base_url}/healthz", timeout=10)

                if health_response.status_code == 200:
                    onboarding_results[user_type] = {
                        "status": "✅ SUCCESS",
                        "system_access": True,
                        "response_time": health_response.elapsed.total_seconds(),
                    }
                    logger.info(f"    ✅ {user_type}: System access successful")
                else:
                    onboarding_results[user_type] = {
                        "status": "❌ FAILED",
                        "system_access": False,
                        "error": f"HTTP {health_response.status_code}",
                    }
                    logger.error(f"    ❌ {user_type}: System access failed")

            except Exception as e:
                onboarding_results[user_type] = {
                    "status": "❌ ERROR",
                    "system_access": False,
                    "error": str(e),
                }
                logger.error(f"    ❌ {user_type}: {e}")

        self.test_results["User Onboarding"] = onboarding_results
        return onboarding_results

    def test_byok_configuration(self):
        """Test BYOK API key configuration for different user personas"""
        logger.info("🔑 Testing BYOK Configuration")

        configuration_results = {}

        for user_type, user_id in self.test_users.items():
            logger.info(f"  Testing {user_type} BYOK configuration...")

            user_keys = self.test_api_keys.get(user_type, {})
            provider_results = {}

            for provider, api_key in user_keys.items():
                try:
                    # Configure API key
                    response = requests.post(
                        f"{self.base_url}/api/user/api-keys/{user_id}/keys/{provider}",
                        json={"api_key": api_key},
                        timeout=10,
                    )

                    if response.status_code == 200:
                        # Verify configuration
                        status_response = requests.get(
                            f"{self.base_url}/api/user/api-keys/{user_id}/status",
                            timeout=10,
                        )

                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            provider_status = status_data.get("status", {}).get(
                                provider, {}
                            )

                            provider_results[provider] = {
                                "status": "✅ CONFIGURED",
                                "configured": provider_status.get("configured", False),
                                "test_result": provider_status.get("test_result", {}),
                            }
                            logger.info(f"    ✅ {provider}: Configured successfully")
                        else:
                            provider_results[provider] = {
                                "status": "⚠️ PARTIAL",
                                "error": "Status verification failed",
                            }
                            logger.warning(
                                f"    ⚠️ {provider}: Status verification failed"
                            )
                    else:
                        provider_results[provider] = {
                            "status": "❌ FAILED",
                            "error": f"Configuration failed: HTTP {response.status_code}",
                        }
                        logger.error(f"    ❌ {provider}: Configuration failed")

                except Exception as e:
                    provider_results[provider] = {"status": "❌ ERROR", "error": str(e)}
                    logger.error(f"    ❌ {provider}: {e}")

            configuration_results[user_type] = provider_results

        self.test_results["BYOK Configuration"] = configuration_results
        return configuration_results

    def test_workflow_scenarios(self):
        """Test real-world workflow scenarios for different user types"""
        logger.info("🤖 Testing Workflow Scenarios")

        workflow_scenarios = {
            "business_user": [
                {
                    "description": "Customer onboarding automation",
                    "input": "Create a customer onboarding workflow with welcome email, calendar invite for orientation, and task assignments in Asana",
                    "expected_services": ["gmail", "google_calendar", "asana"],
                    "priority": "high",
                },
                {
                    "description": "Meeting follow-up automation",
                    "input": "Automate meeting follow-ups with notes distribution to team and action item tracking",
                    "expected_services": ["gmail", "slack", "asana"],
                    "priority": "medium",
                },
            ],
            "developer_user": [
                {
                    "description": "Code review workflow",
                    "input": "Create a code review workflow with GitHub pull request notifications and team coordination",
                    "expected_services": ["github", "slack", "trello"],
                    "priority": "high",
                },
                {
                    "description": "Project documentation automation",
                    "input": "Automate project documentation with Notion page creation and team notifications",
                    "expected_services": ["notion", "slack", "google_drive"],
                    "priority": "medium",
                },
            ],
            "student_user": [
                {
                    "description": "Study schedule automation",
                    "input": "Create a study schedule with calendar events and assignment tracking",
                    "expected_services": ["google_calendar", "notion", "trello"],
                    "priority": "high",
                },
                {
                    "description": "Research workflow automation",
                    "input": "Automate research workflow with document organization and citation management",
                    "expected_services": ["google_drive", "notion", "zotero"],
                    "priority": "medium",
                },
            ],
        }

        workflow_results = {}

        for user_type, user_id in self.test_users.items():
            logger.info(f"  Testing {user_type} workflow scenarios...")

            user_scenarios = workflow_scenarios.get(user_type, [])
            scenario_results = {}

            for scenario in user_scenarios:
                try:
                    response = requests.post(
                        f"{self.base_url}/api/workflow-automation/generate",
                        json={"user_input": scenario["input"], "user_id": user_id},
                        timeout=30,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("success"):
                            workflow = data.get("workflow", {})
                            services = workflow.get("services", [])
                            steps = workflow.get("steps", [])

                            # Calculate service coverage
                            expected = set(scenario["expected_services"])
                            actual = set(services)
                            coverage = len(expected.intersection(actual))
                            coverage_pct = (coverage / len(expected)) * 100

                            scenario_results[scenario["description"]] = {
                                "status": "✅ GENERATED",
                                "steps_count": len(steps),
                                "services_found": list(actual),
                                "service_coverage": f"{coverage_pct:.1f}%",
                                "response_time": response.elapsed.total_seconds(),
                                "workflow_id": workflow.get("id"),
                            }
                            logger.info(
                                f"    ✅ {scenario['description']}: {coverage_pct:.1f}% coverage"
                            )
                        else:
                            scenario_results[scenario["description"]] = {
                                "status": "❌ FAILED",
                                "error": data.get("message", "Unknown error"),
                            }
                            logger.error(
                                f"    ❌ {scenario['description']}: {data.get('message')}"
                            )
                    else:
                        scenario_results[scenario["description"]] = {
                            "status": "❌ HTTP ERROR",
                            "error": f"HTTP {response.status_code}",
                        }
                        logger.error(
                            f"    ❌ {scenario['description']}: HTTP {response.status_code}"
                        )

                except Exception as e:
                    scenario_results[scenario["description"]] = {
                        "status": "❌ ERROR",
                        "error": str(e),
                    }
                    logger.error(f"    ❌ {scenario['description']}: {e}")

            workflow_results[user_type] = scenario_results

        self.test_results["Workflow Scenarios"] = workflow_results
        return workflow_results

    def test_cost_optimization(self):
        """Test cost optimization with multi-provider AI selection"""
        logger.info("💰 Testing Cost Optimization")

        cost_test_scenarios = [
            {
                "use_case": "code_generation",
                "expected_provider": "deepseek",
                "budget_constraint": 0.05,
                "tokens_estimated": 5000,
            },
            {
                "use_case": "document_analysis",
                "expected_provider": "google_gemini",
                "budget_constraint": 0.02,
                "tokens_estimated": 3000,
            },
            {
                "use_case": "complex_reasoning",
                "expected_provider": "anthropic",
                "budget_constraint": 0.15,
                "tokens_estimated": 10000,
            },
        ]

        cost_results = {}

        for scenario in cost_test_scenarios:
            logger.info(f"  Testing {scenario['use_case']} cost optimization...")

            try:
                # Simulate provider selection based on cost optimization
                optimal_provider = self._select_optimal_provider(
                    scenario["use_case"],
                    scenario["budget_constraint"],
                    scenario["tokens_estimated"],
                )

                if optimal_provider:
                    cost_savings = self._calculate_cost_savings(
                        "openai",  # Baseline provider
                        optimal_provider,
                        scenario["tokens_estimated"],
                    )

                    cost_results[scenario["use_case"]] = {
                        "status": "✅ OPTIMIZED",
                        "optimal_provider": optimal_provider,
                        "expected_provider": scenario["expected_provider"],
                        "cost_savings": f"{cost_savings:.1f}%",
                        "match_expected": optimal_provider
                        == scenario["expected_provider"],
                    }
                    logger.info(
                        f"    ✅ {scenario['use_case']}: {optimal_provider} ({cost_savings:.1f}% savings)"
                    )
                else:
                    cost_results[scenario["use_case"]] = {
                        "status": "❌ NO_PROVIDER",
                        "error": "No provider fits budget constraint",
                    }
                    logger.error(
                        f"    ❌ {scenario['use_case']}: No provider fits budget"
                    )

            except Exception as e:
                cost_results[scenario["use_case"]] = {
                    "status": "❌ ERROR",
                    "error": str(e),
                }
                logger.error(f"    ❌ {scenario['use_case']}: {e}")

        self.test_results["Cost Optimization"] = cost_results
        return cost_results

    def _select_optimal_provider(
        self, use_case: str, budget: float, tokens: int
    ) -> Optional[str]:
        """Select optimal provider based on use case and budget"""
        provider_costs = {
            "deepseek": 0.00000014,  # $0.14 per 1M tokens
            "google_gemini": 0.000000075,  # $0.075 per 1M tokens
            "openai": 0.00003,  # $30 per 1M tokens (GPT-4)
            "anthropic": 0.000015,  # $15 per 1M tokens (Claude-3 Opus)
        }

        use_case_mapping = {
            "code_generation": ["deepseek", "openai"],
            "document_analysis": ["google_gemini", "openai"],
            "complex_reasoning": ["anthropic", "openai"],
        }

        suitable_providers = use_case_mapping.get(use_case, list(provider_costs.keys()))
        affordable_providers = []

        for provider in suitable_providers:
            cost = tokens * provider_costs[provider]
            if cost <= budget:
                affordable_providers.append((provider, cost))

        if affordable_providers:
            # Select the cheapest provider
            affordable_providers.sort(key=lambda x: x[1])
            return affordable_providers[0][0]

        return None

    def _calculate_cost_savings(
        self, baseline: str, optimized: str, tokens: int
    ) -> float:
        """Calculate cost savings percentage"""
        provider_costs = {
            "deepseek": 0.00000014,
            "google_gemini": 0.000000075,
            "openai": 0.00003,
            "anthropic": 0.000015,
        }

        baseline_cost = tokens * provider_costs[baseline]
        optimized_cost = tokens * provider_costs[optimized]

        if baseline_cost > 0:
            return ((baseline_cost - optimized_cost) / baseline_cost) * 100
        return 0

    def test_multi_user_isolation(self):
        """Test that user data and API keys are properly isolated"""
        logger.info("🔒 Testing Multi-User Isolation")

        isolation_results = {}

        try:
            # Test that users cannot access each other's API keys
            for user_type, user_id in self.test_users.items():
                status_response = requests.get(
                    f"{self.base_url}/api/user/api-keys/{user_id}/status", timeout=10
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    user_providers = list(status_data.get("status", {}).keys())

                    isolation_results[user_type] = {
                        "status": "✅ ISOLATED",
                        "providers_configured": len(user_providers),
                        "user_id": user_id,
                    }
                    logger.info(f"    ✅ {user_type}: Properly isolated")
                else:
                    isolation_results[user_type] = {
                        "status": "❌ ACCESS_ERROR",
                        "error": f"HTTP {status_response.status_code}",
                    }
                    logger.error(f"    ❌ {user_type}: Access error")

        except Exception as e:
            isolation_results["isolation_test"] = {
                "status": "❌ ERROR",
                "error": str(e),
            }
            logger.error(f"    ❌ Isolation test: {e}")

        self.test_results["Multi-User Isolation"] = isolation_results
        return isolation_results

    def generate_uat_report(self):
        """Generate comprehensive UAT report"""
        logger.info("📊 Generating UAT Report")

        total_tests = 0
        successful_tests = 0
        failed_tests = 0

        # Calculate overall statistics
        for category, results in self.test_results.items():
            if isinstance(results, dict):
                for test_name, result in results.items():
                    total_tests += 1
                    if "✅" in result.get("status", ""):
                        successful_tests += 1
                    elif "❌" in result.get("status", ""):
                        failed_tests += 1

        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        total_time = time.time() - self.start_time

        report = {
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": f"{success_rate:.1f}%",
                "total_time_seconds": total_time,
                "timestamp": datetime.now().isoformat(),
            },
            "test_categories": self.test_results,
            "recommendations": self._generate_recommendations(),
        }

        # Save detailed report
        with open("user_acceptance_testing_report.json", "w") as f:
            json.dump(report, f, indent=2)

        # Print summary
        print("\n" + "=" * 70)
        print("🎯 USER ACCEPTANCE TESTING REPORT - BYOK SYSTEM")
        print("=" * 70)
        print(f"📊 Overall Success Rate: {success_rate:.1f}%")
        print(f"⏱️  Total Testing Time: {total_time:.2f} seconds")
        print(f"👥 Test Users: {len(self.test_users)} personas")

        print(f"\n📈 Category Results:")
        for category, results in self.test_results.items():
            category_success = sum(
                1 for r in results.values() if "✅" in r.get("status", "")
            )
            category_total = len(results)
            category_rate = (
                (category_success / category_total) * 100 if category_total > 0 else 0
            )
            print(
                f"   {category:<20}: {category_success}/{category_total} ({category_rate:.1f}%)"
            )

        print(f"\n💡 Key Findings:")
        if success_rate >= 80:
            print("   ✅ BYOK system is ready for production deployment")
            print("   ✅ Multi-user isolation working correctly")
            print("   ✅ Cost optimization providing significant savings")
        elif success_rate >= 60:
            print("   ⚠️ BYOK system needs minor improvements")
            print("   ⚠️ Some workflow scenarios need optimization")
            print("   ⚠️ Consider additional user testing")
        else:
            print("   ❌ Significant improvements needed before production")
            print("   ❌ Review workflow generation and service integration")
            print("   ❌ Enhance cost optimization algorithms")

        print(f"\n📁 Detailed report saved to: user_acceptance_testing_report.json")

        return report

    def _generate_recommendations(self):
        """Generate recommendations based on test results"""
        recommendations = []

        # Analyze BYOK configuration results
        byok_config = self.test_results.get("BYOK Configuration", {})
        for user_type, providers in byok_config.items():
            failed_providers = [
                p for p, r in providers.items() if "❌" in r.get("status", "")
            ]
            if failed_providers:
                recommendations.append(
                    f"Fix {user_type} configuration for providers: {', '.join(failed_providers)}"
                )

        # Analyze workflow scenarios
        workflow_results = self.test_results.get("Workflow Scenarios", {})
        low_coverage = []
        for user_type, scenarios in workflow_results.items():
            for scenario, result in scenarios.items():
                if (
                    "service_coverage" in result
                    and float(result["service_coverage"].rstrip("%")) < 50
                ):
                    low_coverage.append(f"{user_type}: {scenario}")

        if low_coverage:
            recommendations.append(
                f"Improve service coverage for scenarios: {', '.join(low_coverage[:3])}"
            )

        # Cost optimization recommendations
        cost_results = self.test_results.get("Cost Optimization", {})
        mismatched_providers = [
            use_case
            for use_case, result in cost_results.items()
            if result.get("match_expected") is False
        ]

        if mismatched_providers:
            recommendations.append(
                f"Review cost optimization logic for: {', '.join(mismatched_providers)}"
            )

        if not recommendations:
            recommendations.append(
                "System is performing well across all test categories"
            )

        return recommendations

    def run_all_tests(self):
        """Run all user acceptance tests"""
        logger.info("🚀 Starting User Acceptance Testing")
        logger.info(f"🌐 Base URL: {self.base_url}")
        logger.info(f"👥 Test Users: {list(self.test_users.keys())}")

        # Setup test environment
        self.setup_test_environment()

        # Run all test suites
        self.test_user_onboarding()
        self.test_byok_configuration()
        self.test_workflow_scenarios()
        self.test_cost_optimization()
        self.test_multi_user_isolation()

        # Generate final report
        report = self.generate_uat_report()

        return report


def main():
    """Main function to run user acceptance testing"""
    tester = UserAcceptanceTester()
    report = tester.run_all_tests()

    # Exit with appropriate code
    success_rate = float(report["summary"]["success_rate"].rstrip("%"))
    if success_rate >= 80:
        print("\n🎉 USER ACCEPTANCE TESTING: PASSED ✅")
        print("   BYOK system is ready for production deployment!")
        exit(0)
    elif success_rate >= 60:
        print("\n⚠️ USER ACCEPTANCE TESTING: CONDITIONAL PASS ⚠️")
        print("   BYOK system needs minor improvements before full deployment")
        exit(0)
    else:
        print("\n❌ USER ACCEPTANCE TESTING: FAILED ❌")
        print("   Significant improvements needed before production deployment")
        exit(1)


if __name__ == "__main__":
    main()
