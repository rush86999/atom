"""
AI-Powered E2E Integration Test Suite
Tests all major ATOM integrations with AI validation for bugs and business value gaps
"""

import asyncio
import json
import logging
import aiohttp
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    service: str
    status: str  # passed, failed, warning
    response_time: float
    error_message: Optional[str] = None
    ai_validation: Optional[Dict[str, Any]] = None
    business_value_score: float = 0.0
    recommendations: List[str] = None

    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []

@dataclass
class BusinessValueMetrics:
    """Business value assessment metrics"""
    efficiency: float = 0.0  # Time/effort savings
    reliability: float = 0.0  # Uptime/consistency
    scalability: float = 0.0  # Growth capability
    integration_quality: float = 0.0  # How well it integrates
    user_experience: float = 0.0  # End-user satisfaction

class AIValidationEngine:
    """AI-powered validation engine for test results"""

    def __init__(self):
        self.ai_providers = ["openai", "claude", "gemini", "deepseek"]
        self.validation_rules = {
            "response_time": {"max": 5000, "warning": 2000, "critical": 10000},  # ms
            "error_rate": {"max": 0.05, "warning": 0.02, "critical": 0.1},  # percentage
            "data_completeness": {"min": 0.9, "warning": 0.8, "critical": 0.7},  # percentage
        }

    async def validate_with_ai(self, test_result: TestResult, response_data: Any) -> Dict[str, Any]:
        """Validate test results using AI analysis"""
        try:
            validation_result = {
                "ai_score": 0.0,
                "issues_detected": [],
                "strengths": [],
                "business_gaps": [],
                "technical_issues": [],
                "recommendations": []
            }

            # Simulate AI validation logic (in production, would call actual AI APIs)
            if test_result.status == "passed":
                if test_result.response_time < 1000:
                    validation_result["strengths"].append("Excellent response time")
                    validation_result["ai_score"] += 0.3
                elif test_result.response_time > 5000:
                    validation_result["technical_issues"].append("Slow response time")
                    validation_result["ai_score"] -= 0.2

                # Check response data quality
                if response_data and isinstance(response_data, dict):
                    if response_data.get("success"):
                        validation_result["strengths"].append("Successful response format")
                        validation_result["ai_score"] += 0.2
                    else:
                        validation_result["technical_issues"].append("Response indicates failure")
                        validation_result["ai_score"] -= 0.3

                    # Check for business value indicators
                    if "data" in response_data and response_data["data"]:
                        validation_result["strengths"].append("Contains meaningful data")
                        validation_result["ai_score"] += 0.2
                    else:
                        validation_result["business_gaps"].append("Missing or empty data")
                        validation_result["ai_score"] -= 0.1

            else:
                validation_result["ai_score"] = 0.0
                validation_result["technical_issues"].append(f"Test failed: {test_result.error_message}")

            # Business value analysis
            validation_result["business_value_score"] = min(max(validation_result["ai_score"], 0), 1.0)

            # Generate recommendations
            if validation_result["ai_score"] < 0.7:
                validation_result["recommendations"].append("Consider performance optimization")
            if validation_result["technical_issues"]:
                validation_result["recommendations"].append("Fix technical issues before production")
            if validation_result["business_gaps"]:
                validation_result["recommendations"].append("Address business value gaps")

            return validation_result

        except Exception as e:
            logger.error(f"AI validation failed: {e}")
            return {
                "ai_score": 0.0,
                "issues_detected": [f"AI validation error: {str(e)}"],
                "business_value_score": 0.0
            }

class ComprehensiveE2ETestRunner:
    """Comprehensive E2E test runner with AI validation"""

    def __init__(self):
        self.ai_validator = AIValidationEngine()
        self.backend_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        self.test_results: List[TestResult] = []
        self.session = None

    async def setup_session(self):
        """Setup HTTP session for testing"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"Content-Type": "application/json"}
        )

    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()

    async def test_health_endpoints(self):
        """Test health check endpoints"""
        health_tests = [
            {"name": "Backend Health", "url": f"{self.backend_url}/health"},
            {"name": "Frontend Health", "url": f"{self.frontend_url}/api/health"},
        ]

        for test in health_tests:
            result = await self.run_single_test(
                test_name=f"Health Check - {test['name']}",
                url=test["url"],
                service="health"
            )
            self.test_results.append(result)

    async def test_oauth_endpoints(self):
        """Test OAuth endpoints"""
        oauth_tests = [
            {"name": "Zoom OAuth Initiate", "url": f"{self.backend_url}/api/integrations/zoom/oauth/initiate"},
            {"name": "Social Store Health", "url": f"{self.backend_url}/api/integrations/social/health"},
            {"name": "Social Store Platforms", "url": f"{self.backend_url}/api/integrations/social/platforms"},
        ]

        for test in oauth_tests:
            result = await self.run_single_test(
                test_name=f"OAuth - {test['name']}",
                url=test["url"],
                service="oauth"
            )
            self.test_results.append(result)

    async def test_integration_services(self):
        """Test integration services"""
        integration_tests = [
            {"name": "AI Workflow", "url": f"{self.backend_url}/api/ai/workflow/status"},
            {"name": "Communication Memory", "url": f"{self.backend_url}/api/communication/memory/health"},
            {"name": "Memory Production", "url": f"{self.backend_url}/api/communication/memory/production/health"},
        ]

        for test in integration_tests:
            result = await self.run_single_test(
                test_name=f"Integration - {test['name']}",
                url=test["url"],
                service="integration"
            )
            self.test_results.append(result)

    async def test_api_functionality(self):
        """Test API functionality with data validation"""
        functionality_tests = [
            {
                "name": "Create Workflow",
                "url": f"{self.backend_url}/api/v1/workflows",
                "method": "POST",
                "data": {
                    "name": "Test Workflow",
                    "description": "Automated test workflow",
                    "steps": [
                        {"action": "process_data", "parameters": {"test": True}}
                    ]
                }
            },
            {
                "name": "Store Social Token",
                "url": f"{self.backend_url}/api/integrations/social/store",
                "method": "POST",
                "data": {
                    "platform": "test_platform",
                    "access_token": "test_token_123",
                    "user_info": {"email": "test@example.com"}
                }
            }
        ]

        for test in functionality_tests:
            result = await self.run_single_test(
                test_name=f"Functionality - {test['name']}",
                url=test["url"],
                service="functionality",
                method=test.get("method", "GET"),
                data=test.get("data")
            )
            self.test_results.append(result)

    async def test_business_value_scenarios(self):
        """Test scenarios that demonstrate business value"""
        business_tests = [
            {
                "name": "Data Analytics",
                "url": f"{self.backend_url}/api/v1/analytics/stats",
                "business_value": "efficiency",
                "expected_data_points": ["metrics", "insights", "trends"]
            },
            {
                "name": "Communication Search",
                "url": f"{self.backend_url}/api/atom/communication/memory/search",
                "method": "GET",
                "params": {"query": "test search", "limit": 10},
                "business_value": "productivity",
                "expected_data_points": ["results", "count", "relevance"]
            }
        ]

        for test in business_tests:
            result = await self.run_single_test(
                test_name=f"Business Value - {test['name']}",
                url=test["url"],
                service="business_value",
                method=test.get("method", "GET"),
                data=test.get("data"),
                business_value=test["business_value"]
            )
            self.test_results.append(result)

    async def run_single_test(self, test_name: str, url: str, service: str,
                             method: str = "GET", data: Optional[Dict] = None,
                             business_value: str = "general") -> TestResult:
        """Run a single test with AI validation"""
        start_time = time.time()

        try:
            # Make HTTP request
            if method == "GET":
                async with self.session.get(url) as response:
                    response_data = await response.json()
                    status = "passed" if response.status == 200 else "failed"
            elif method == "POST":
                async with self.session.post(url, json=data) as response:
                    response_data = await response.json()
                    status = "passed" if response.status in [200, 201] else "failed"
            else:
                raise ValueError(f"Unsupported method: {method}")

            response_time = (time.time() - start_time) * 1000  # Convert to ms

            # AI validation
            ai_validation = await self.ai_validator.validate_with_ai(
                TestResult(test_name=test_name, service=service, status=status,
                         response_time=response_time),
                response_data
            )

            # Calculate business value score
            business_metrics = BusinessValueMetrics()
            business_score = self._calculate_business_value(business_metrics, response_data, business_value)

            result = TestResult(
                test_name=test_name,
                service=service,
                status=status,
                response_time=response_time,
                ai_validation=ai_validation,
                business_value_score=business_score,
                recommendations=ai_validation.get("recommendations", [])
            )

            logger.info(f"✅ {test_name} - {status} ({response_time:.0f}ms)")
            return result

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            error_message = str(e)

            logger.error(f"❌ {test_name} - failed ({error_message})")

            return TestResult(
                test_name=test_name,
                service=service,
                status="failed",
                response_time=response_time,
                error_message=error_message,
                ai_validation={"ai_score": 0.0, "issues_detected": [error_message]},
                business_value_score=0.0,
                recommendations=[f"Fix error: {error_message}"]
            )

    def _calculate_business_value(self, metrics: BusinessValueMetrics, response_data: Any,
                                 value_type: str) -> float:
        """Calculate business value score based on response"""
        score = 0.0

        if response_data and isinstance(response_data, dict):
            # Check for success indicators
            if response_data.get("success"):
                score += 0.3

            # Check for data completeness
            if response_data.get("data"):
                score += 0.2

            # Check for meaningful content
            if len(str(response_data)) > 100:  # Substantial response
                score += 0.1

            # Value type specific scoring
            if value_type == "efficiency" and response_data.get("metrics"):
                score += 0.2
            elif value_type == "productivity" and response_data.get("results"):
                score += 0.2
            elif value_type == "reliability" and response_data.get("status"):
                score += 0.2

        return min(score, 1.0)

    async def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report with AI insights"""

        # Calculate overall statistics
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.status == "passed"])
        failed_tests = total_tests - passed_tests
        avg_response_time = sum(r.response_time for r in self.test_results) / total_tests if total_tests > 0 else 0
        avg_ai_score = sum(r.ai_validation.get("ai_score", 0) for r in self.test_results) / total_tests if total_tests > 0 else 0
        avg_business_value = sum(r.business_value_score for r in self.test_results) / total_tests if total_tests > 0 else 0

        # Group results by service
        results_by_service = {}
        for result in self.test_results:
            if result.service not in results_by_service:
                results_by_service[result.service] = []
            results_by_service[result.service].append(result)

        # Identify critical issues
        critical_issues = []
        for result in self.test_results:
            if result.status == "failed" or result.ai_validation.get("ai_score", 0) < 0.5:
                critical_issues.append({
                    "test": result.test_name,
                    "service": result.service,
                    "issue": result.error_message or "Low AI validation score",
                    "priority": "high" if result.status == "failed" else "medium"
                })

        # Generate business value recommendations
        business_recommendations = []
        low_value_services = [service for service, results in results_by_service.items()
                           if sum(r.business_value_score for r in results) / len(results) < 0.5]

        if low_value_services:
            business_recommendations.append(f"Improve business value in services: {', '.join(low_value_services)}")

        report = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "avg_response_time_ms": round(avg_response_time, 2),
                "avg_ai_score": round(avg_ai_score, 3),
                "avg_business_value": round(avg_business_value, 3)
            },
            "results_by_service": {},
            "critical_issues": critical_issues,
            "ai_insights": {
                "overall_health": "healthy" if avg_ai_score > 0.7 else "needs_attention",
                "performance_rating": "excellent" if avg_response_time < 1000 else "good" if avg_response_time < 3000 else "poor",
                "business_value_rating": "high" if avg_business_value > 0.7 else "medium" if avg_business_value > 0.4 else "low"
            },
            "business_value_assessment": {
                "overall_score": avg_business_value,
                "recommendations": business_recommendations,
                "improvement_areas": [result.service for result in self.test_results
                                    if result.business_value_score < 0.6]
            },
            "actionable_recommendations": []
        }

        # Compile service-specific insights
        for service, results in results_by_service.items():
            service_pass_rate = len([r for r in results if r.status == "passed"]) / len(results) * 100
            service_avg_ai = sum(r.ai_validation.get("ai_score", 0) for r in results) / len(results)
            service_business_value = sum(r.business_value_score for r in results) / len(results)

            report["results_by_service"][service] = {
                "total_tests": len(results),
                "pass_rate": round(service_pass_rate, 1),
                "avg_ai_score": round(service_avg_ai, 3),
                "business_value_score": round(service_business_value, 3),
                "issues": [r.error_message for r in results if r.status == "failed"],
                "recommendations": list(set([rec for r in results for rec in r.recommendations]))
            }

        # Generate actionable recommendations
        if report["test_metadata"]["success_rate"] < 90:
            report["actionable_recommendations"].append("Address test failures to improve overall system reliability")

        if report["test_metadata"]["avg_response_time_ms"] > 3000:
            report["actionable_recommendations"].append("Optimize slow endpoints for better performance")

        if report["ai_insights"]["business_value_rating"] == "low":
            report["actionable_recommendations"].append("Focus on enhancing business value in integrations")

        if len(critical_issues) > 0:
            report["actionable_recommendations"].append(f"Fix {len(critical_issues)} critical issues immediately")

        return report

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all E2E tests with AI validation"""
        logger.info("🚀 Starting AI-Powered E2E Integration Test Suite")
        logger.info("=" * 60)

        try:
            await self.setup_session()

            # Run test suites
            logger.info("🔍 Testing Health Endpoints...")
            await self.test_health_endpoints()

            logger.info("🔐 Testing OAuth Endpoints...")
            await self.test_oauth_endpoints()

            logger.info("🔗 Testing Integration Services...")
            await self.test_integration_services()

            logger.info("⚙️ Testing API Functionality...")
            await self.test_api_functionality()

            logger.info("💼 Testing Business Value Scenarios...")
            await self.test_business_value_scenarios()

            # Generate comprehensive report
            logger.info("📊 Generating AI-Powered Analysis Report...")
            report = await self.generate_comprehensive_report()

            # Print summary
            self._print_summary(report)

            # Save report
            report_file = f"ai_validation_e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)

            logger.info(f"📋 Detailed report saved to: {report_file}")

            return report

        finally:
            await self.cleanup_session()

    def _print_summary(self, report: Dict[str, Any]):
        """Print test summary to console"""
        metadata = report["test_metadata"]
        insights = report["ai_insights"]

        print("\n" + "=" * 80)
        print("🤖 AI-POWERED E2E INTEGRATION TEST RESULTS")
        print("=" * 80)

        print(f"📊 OVERALL METRICS:")
        print(f"   Total Tests: {metadata['total_tests']}")
        print(f"   Passed: {metadata['passed_tests']} ({metadata['success_rate']:.1f}%)")
        print(f"   Failed: {metadata['failed_tests']}")
        print(f"   Avg Response Time: {metadata['avg_response_time_ms']:.0f}ms")
        print(f"   AI Validation Score: {metadata['avg_ai_score']:.3f}")
        print(f"   Business Value Score: {metadata['avg_business_value']:.3f}")

        print(f"\n🧠 AI INSIGHTS:")
        print(f"   System Health: {insights['overall_health']}")
        print(f"   Performance Rating: {insights['performance_rating']}")
        print(f"   Business Value Rating: {insights['business_value_rating']}")

        print(f"\n🚨 CRITICAL ISSUES: {len(report['critical_issues'])}")
        for issue in report['critical_issues'][:5]:  # Show top 5
            print(f"   ❌ {issue['test']} ({issue['service']}) - {issue['priority']}")

        if len(report['critical_issues']) > 5:
            print(f"   ... and {len(report['critical_issues']) - 5} more issues")

        print(f"\n💡 ACTIONABLE RECOMMENDATIONS: {len(report['actionable_recommendations'])}")
        for i, rec in enumerate(report['actionable_recommendations'], 1):
            print(f"   {i}. {rec}")

        print("\n" + "=" * 80)

async def main():
    """Main function to run the AI-powered E2E test suite"""
    test_runner = ComprehensiveE2ETestRunner()
    await test_runner.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())