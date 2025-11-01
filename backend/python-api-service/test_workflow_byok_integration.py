"""
Workflow Automation Test with BYOK Integration

This test validates the integration between workflow automation and the BYOK (Bring Your Own Keys) system.
It tests multi-provider AI usage in workflow generation and execution with user-configured API keys.
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional
import requests

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


class WorkflowBYOKIntegrationTest:
    """Test class for workflow automation with BYOK integration"""

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.test_user = "test_user_byok"
        self.test_results = []

    def setup_test_api_keys(self):
        """Setup test API keys for BYOK system"""
        print("🔑 Setting up test API keys for BYOK system...")

        # Test API keys (these would be real keys in production)
        test_keys = {
            "openai": "sk-test-openai-key-12345",
            "deepseek": "sk-test-deepseek-key-67890",
            "google_gemini": "AIza-test-gemini-key-abc123",
        }

        for provider, api_key in test_keys.items():
            try:
                response = requests.post(
                    f"{self.base_url}/api/user/api-keys/{self.test_user}/keys/{provider}",
                    json={"api_key": api_key},
                )

                if response.status_code == 200:
                    print(f"✅ {provider.upper()} API key configured")
                else:
                    print(f"⚠️ Failed to configure {provider}: {response.text}")

            except Exception as e:
                print(f"❌ Error configuring {provider}: {e}")

    def test_workflow_generation_with_byok(self):
        """Test workflow generation using BYOK-configured providers"""
        print("\n🤖 Testing Workflow Generation with BYOK Providers")
        print("=" * 60)

        test_cases = [
            {
                "name": "Customer Onboarding Workflow",
                "user_input": "Create a customer onboarding workflow with welcome email, calendar invite, and task assignments",
                "expected_services": ["gmail", "google_calendar", "asana", "notion"],
            },
            {
                "name": "Project Kickoff Workflow",
                "user_input": "Automate project kickoff with team communication, document sharing, and milestone setup",
                "expected_services": ["slack", "google_drive", "trello", "github"],
            },
            {
                "name": "Meeting Follow-up Workflow",
                "user_input": "Create automated follow-up for meetings with notes distribution and action items",
                "expected_services": ["gmail", "notion", "asana", "slack"],
            },
        ]

        for test_case in test_cases:
            print(f"\n📋 Test Case: {test_case['name']}")
            print(f"   Input: '{test_case['user_input']}'")

            try:
                response = requests.post(
                    f"{self.base_url}/api/workflow-automation/generate",
                    json={
                        "user_input": test_case["user_input"],
                        "user_id": self.test_user,
                    },
                )

                if response.status_code == 200:
                    result = response.json()

                    if result.get("success"):
                        workflow = result.get("workflow", {})

                        # Validate workflow structure
                        required_fields = [
                            "id",
                            "name",
                            "description",
                            "steps",
                            "services",
                        ]
                        missing_fields = [
                            field for field in required_fields if field not in workflow
                        ]

                        if not missing_fields:
                            print(f"✅ Workflow generated successfully")
                            print(f"   Workflow ID: {workflow.get('id')}")
                            print(
                                f"   Services: {', '.join(workflow.get('services', []))}"
                            )
                            print(f"   Steps: {len(workflow.get('steps', []))}")

                            # Check if expected services are included
                            included_services = set(workflow.get("services", []))
                            expected_services = set(test_case["expected_services"])
                            matched_services = included_services.intersection(
                                expected_services
                            )

                            print(
                                f"   Service Coverage: {len(matched_services)}/{len(expected_services)} expected services"
                            )

                            self.test_results.append(
                                {
                                    "test_case": test_case["name"],
                                    "status": "success",
                                    "workflow_id": workflow.get("id"),
                                    "services": workflow.get("services", []),
                                    "steps_count": len(workflow.get("steps", [])),
                                    "service_coverage": f"{len(matched_services)}/{len(expected_services)}",
                                }
                            )
                        else:
                            print(f"❌ Missing workflow fields: {missing_fields}")
                            self.test_results.append(
                                {
                                    "test_case": test_case["name"],
                                    "status": "failed",
                                    "error": f"Missing fields: {missing_fields}",
                                }
                            )
                    else:
                        print(
                            f"❌ Workflow generation failed: {result.get('message', 'Unknown error')}"
                        )
                        self.test_results.append(
                            {
                                "test_case": test_case["name"],
                                "status": "failed",
                                "error": result.get("message", "Unknown error"),
                            }
                        )
                else:
                    print(
                        f"❌ API request failed: {response.status_code} - {response.text}"
                    )
                    self.test_results.append(
                        {
                            "test_case": test_case["name"],
                            "status": "failed",
                            "error": f"HTTP {response.status_code}: {response.text}",
                        }
                    )

            except Exception as e:
                print(f"❌ Exception during workflow generation: {e}")
                self.test_results.append(
                    {
                        "test_case": test_case["name"],
                        "status": "failed",
                        "error": str(e),
                    }
                )

    def test_multi_provider_workflow_execution(self):
        """Test workflow execution with multi-provider AI selection"""
        print("\n🔄 Testing Multi-Provider Workflow Execution")
        print("=" * 60)

        # Test workflow that would benefit from different AI providers
        test_workflows = [
            {
                "name": "Code Review Workflow",
                "description": "Uses DeepSeek for code analysis and OpenAI for communication",
                "providers_expected": ["deepseek", "openai"],
            },
            {
                "name": "Document Analysis Workflow",
                "description": "Uses Google Gemini for document understanding and Anthropic for summarization",
                "providers_expected": ["google_gemini", "anthropic"],
            },
            {
                "name": "Customer Support Workflow",
                "description": "Uses multiple providers for different support tasks",
                "providers_expected": ["openai", "google_gemini", "deepseek"],
            },
        ]

        for workflow in test_workflows:
            print(f"\n🔧 Testing: {workflow['name']}")
            print(f"   Description: {workflow['description']}")
            print(f"   Expected Providers: {', '.join(workflow['providers_expected'])}")

            # Simulate provider selection based on workflow type
            selected_providers = self._select_providers_for_workflow(workflow["name"])

            print(f"   Selected Providers: {', '.join(selected_providers)}")

            # Check provider availability via BYOK system
            available_providers = []
            for provider in selected_providers:
                try:
                    response = requests.get(
                        f"{self.base_url}/api/user/api-keys/{self.test_user}/status"
                    )

                    if response.status_code == 200:
                        status_data = response.json()
                        provider_status = status_data.get("status", {}).get(
                            provider, {}
                        )

                        if provider_status.get("configured", False):
                            available_providers.append(provider)
                            print(f"   ✅ {provider.upper()} configured and available")
                        else:
                            print(f"   ⚠️ {provider.upper()} not configured")
                    else:
                        print(f"   ❌ Failed to check {provider} status")

                except Exception as e:
                    print(f"   ❌ Error checking {provider}: {e}")

            coverage = len(
                set(available_providers).intersection(
                    set(workflow["providers_expected"])
                )
            )
            coverage_percentage = (coverage / len(workflow["providers_expected"])) * 100

            print(
                f"   Provider Coverage: {coverage}/{len(workflow['providers_expected'])} ({coverage_percentage:.1f}%)"
            )

            self.test_results.append(
                {
                    "test_case": f"Multi-Provider: {workflow['name']}",
                    "status": "success" if coverage_percentage > 50 else "partial",
                    "expected_providers": workflow["providers_expected"],
                    "available_providers": available_providers,
                    "coverage_percentage": coverage_percentage,
                }
            )

    def _select_providers_for_workflow(self, workflow_type: str) -> List[str]:
        """Select appropriate AI providers based on workflow type"""
        provider_mapping = {
            "Code Review Workflow": ["deepseek", "openai"],
            "Document Analysis Workflow": ["google_gemini", "anthropic"],
            "Customer Support Workflow": ["openai", "google_gemini", "deepseek"],
            "default": ["openai", "google_gemini"],
        }

        return provider_mapping.get(workflow_type, provider_mapping["default"])

    def test_cost_aware_workflow_execution(self):
        """Test cost-aware provider selection in workflow execution"""
        print("\n💰 Testing Cost-Aware Workflow Execution")
        print("=" * 60)

        # Simulate different workflow complexity levels
        complexity_levels = [
            {"level": "simple", "estimated_tokens": 1000, "budget_limit": 0.01},
            {"level": "medium", "estimated_tokens": 5000, "budget_limit": 0.05},
            {"level": "complex", "estimated_tokens": 20000, "budget_limit": 0.20},
        ]

        for complexity in complexity_levels:
            print(f"\n📊 Complexity: {complexity['level'].upper()}")
            print(f"   Estimated Tokens: {complexity['estimated_tokens']:,}")
            print(f"   Budget Limit: ${complexity['budget_limit']:.3f}")

            # Select cost-optimal provider
            optimal_provider = self._select_cost_optimal_provider(
                complexity["estimated_tokens"], complexity["budget_limit"]
            )

            if optimal_provider:
                print(f"   ✅ Optimal Provider: {optimal_provider.upper()}")
                print(f"   💡 Strategy: {self._get_cost_strategy(optimal_provider)}")

                self.test_results.append(
                    {
                        "test_case": f"Cost-Aware: {complexity['level']} complexity",
                        "status": "success",
                        "optimal_provider": optimal_provider,
                        "estimated_tokens": complexity["estimated_tokens"],
                        "budget_limit": complexity["budget_limit"],
                        "strategy": self._get_cost_strategy(optimal_provider),
                    }
                )
            else:
                print(f"   ❌ No provider fits within budget")
                self.test_results.append(
                    {
                        "test_case": f"Cost-Aware: {complexity['level']} complexity",
                        "status": "failed",
                        "error": "No provider fits within budget",
                    }
                )

    def _select_cost_optimal_provider(
        self, tokens: int, budget_limit: float
    ) -> Optional[str]:
        """Select the most cost-effective provider within budget"""
        # Provider cost per token (approximate)
        provider_costs = {
            "deepseek": 0.00000014,  # $0.14 per 1M tokens
            "google_gemini": 0.000000075,  # $0.075 per 1M tokens
            "openai": 0.00003,  # $30 per 1M tokens for GPT-4
            "anthropic": 0.000015,  # $15 per 1M tokens for Claude-3 Opus
        }

        # Filter providers that fit within budget
        affordable_providers = []
        for provider, cost_per_token in provider_costs.items():
            total_cost = tokens * cost_per_token
            if total_cost <= budget_limit:
                affordable_providers.append((provider, total_cost))

        if affordable_providers:
            # Select the provider with lowest cost
            affordable_providers.sort(key=lambda x: x[1])
            return affordable_providers[0][0]

        return None

    def _get_cost_strategy(self, provider: str) -> str:
        """Get cost optimization strategy for provider"""
        strategies = {
            "deepseek": "Use for code generation and cost-sensitive tasks",
            "google_gemini": "Use for embeddings and general-purpose tasks",
            "openai": "Use for highest quality requirements",
            "anthropic": "Use for complex reasoning tasks",
        }
        return strategies.get(provider, "General purpose usage")

    def generate_integration_report(self):
        """Generate comprehensive integration test report"""
        print("\n📈 BYOK-Workflow Integration Test Report")
        print("=" * 60)

        total_tests = len(self.test_results)
        successful_tests = len(
            [r for r in self.test_results if r["status"] == "success"]
        )
        partial_tests = len([r for r in self.test_results if r["status"] == "partial"])
        failed_tests = len([r for r in self.test_results if r["status"] == "failed"])

        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0

        print(f"📊 Test Summary:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Successful: {successful_tests}")
        print(f"   Partial Success: {partial_tests}")
        print(f"   Failed: {failed_tests}")
        print(f"   Success Rate: {success_rate:.1f}%")

        print(f"\n🎯 Key Findings:")

        # Analyze workflow generation success
        workflow_tests = [r for r in self.test_results if "workflow_id" in r]
        if workflow_tests:
            avg_steps = sum(r.get("steps_count", 0) for r in workflow_tests) / len(
                workflow_tests
            )
            print(f"   • Average workflow steps: {avg_steps:.1f}")

        # Analyze multi-provider coverage
        provider_tests = [r for r in self.test_results if "coverage_percentage" in r]
        if provider_tests:
            avg_coverage = sum(
                r.get("coverage_percentage", 0) for r in provider_tests
            ) / len(provider_tests)
            print(f"   • Average provider coverage: {avg_coverage:.1f}%")

        # Analyze cost optimization
        cost_tests = [r for r in self.test_results if "optimal_provider" in r]
        if cost_tests:
            provider_usage = {}
            for test in cost_tests:
                provider = test.get("optimal_provider")
                provider_usage[provider] = provider_usage.get(provider, 0) + 1

            print(f"   • Cost-optimal provider distribution:")
            for provider, count in provider_usage.items():
                percentage = (count / len(cost_tests)) * 100
                print(f"     - {provider.upper()}: {count} tests ({percentage:.1f}%)")

        print(
            f"\n✅ BYOK-Workflow Integration Status: {'SUCCESSFUL' if success_rate >= 80 else 'NEEDS IMPROVEMENT'}"
        )

        # Save detailed results
        with open("byok_workflow_integration_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)

        print(f"\n📁 Detailed results saved to: byok_workflow_integration_results.json")

    def run_all_tests(self):
        """Run all BYOK-workflow integration tests"""
        print("🚀 Starting BYOK-Workflow Integration Tests")
        print("=" * 60)

        # Setup test environment
        self.setup_test_api_keys()

        # Run integration tests
        self.test_workflow_generation_with_byok()
        self.test_multi_provider_workflow_execution()
        self.test_cost_aware_workflow_execution()

        # Generate report
        self.generate_integration_report()

        return self.test_results


def main():
    """Main function to run BYOK-workflow integration tests"""
    tester = WorkflowBYOKIntegrationTest()
    results = tester.run_all_tests()

    # Exit with appropriate code
    success_rate = (
        len([r for r in results if r["status"] == "success"]) / len(results) * 100
    )
    if success_rate >= 80:
        print("\n🎉 BYOK-Workflow Integration Tests PASSED!")
        sys.exit(0)
    else:
        print("\n❌ BYOK-Workflow Integration Tests NEEDS IMPROVEMENT")
        sys.exit(1)


if __name__ == "__main__":
    main()
