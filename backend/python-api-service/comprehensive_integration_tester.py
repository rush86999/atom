#!/usr/bin/env python3
"""
Comprehensive Integration Test System
Tests all enhanced integrations across Flask and FastAPI frameworks
"""

import os
import json
import asyncio
import logging
import time
import httpx
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class IntegrationTestCase:
    """Single test case for integration testing"""
    name: str
    integration: str
    endpoint: str
    method: str
    headers: Dict[str, str] = None
    data: Dict[str, Any] = None
    expected_status: int = 200
    timeout: float = 10.0
    test_type: str = "health"  # health, functionality, performance, error

@dataclass
class TestResult:
    """Result of a single test case"""
    test_case: IntegrationTestCase
    status: 'passed' | 'failed' | 'error' | 'skipped'
    response_time: Optional[float] = None
    status_code: Optional[int] = None
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: str = None

@dataclass
class IntegrationTestReport:
    """Comprehensive test report for an integration"""
    integration_name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    skipped_tests: int
    test_results: List[TestResult]
    total_response_time: float
    average_response_time: float
    success_rate: float
    test_duration: float
    timestamp: str

@dataclass
class SystemTestReport:
    """System-wide test report"""
    total_integrations: int
    integration_reports: Dict[str, IntegrationTestReport]
    system_health_score: float
    overall_status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
    test_duration: float
    recommendations: List[str]
    timestamp: str

class ComprehensiveIntegrationTester:
    """Comprehensive integration testing system"""
    
    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.test_suites = self._generate_test_suites()
    
    def _generate_test_suites(self) -> Dict[str, List[IntegrationTestCase]]:
        """Generate comprehensive test suites for all integrations"""
        test_suites = {}
        
        # HubSpot Test Suite
        test_suites['hubspot'] = [
            IntegrationTestCase(
                name="HubSpot Health Check",
                integration="hubspot",
                endpoint="/api/integrations/hubspot/health",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="HubSpot Enhanced Health",
                integration="hubspot",
                endpoint="/api/v2/health/health/hubspot",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="HubSpot Bridge Status",
                integration="hubspot",
                endpoint="/api/bridge/status",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="HubSpot Enhanced Overview",
                integration="hubspot",
                endpoint="/api/enhanced/health/overview",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="HubSpot Contacts API",
                integration="hubspot",
                endpoint="/api/v2/hubspot/contacts",
                method="GET",
                headers={"user_id": "test_user"},
                test_type="functionality"
            ),
        ]
        
        # Slack Test Suite
        test_suites['slack'] = [
            IntegrationTestCase(
                name="Slack Health Check",
                integration="slack",
                endpoint="/api/integrations/slack/health",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Slack Enhanced Health",
                integration="slack",
                endpoint="/api/v2/health/health/slack",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Slack Bridge Status",
                integration="slack",
                endpoint="/api/bridge/status",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Slack Enhanced Overview",
                integration="slack",
                endpoint="/api/enhanced/health/overview",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Slack Channels API",
                integration="slack",
                endpoint="/api/v2/slack/channels",
                method="GET",
                headers={"user_id": "test_user"},
                test_type="functionality"
            ),
        ]
        
        # Jira Test Suite
        test_suites['jira'] = [
            IntegrationTestCase(
                name="Jira Health Check",
                integration="jira",
                endpoint="/api/integrations/jira/health",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Jira Enhanced Health",
                integration="jira",
                endpoint="/api/v2/health/health/jira",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Jira Bridge Status",
                integration="jira",
                endpoint="/api/bridge/status",
                method="GET",
                test_type="health"
            ),
        ]
        
        # Linear Test Suite
        test_suites['linear'] = [
            IntegrationTestCase(
                name="Linear Health Check",
                integration="linear",
                endpoint="/api/integrations/linear/health",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Linear Enhanced Health",
                integration="linear",
                endpoint="/api/v2/health/health/linear",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Linear Bridge Status",
                integration="linear",
                endpoint="/api/bridge/status",
                method="GET",
                test_type="health"
            ),
        ]
        
        # Salesforce Test Suite
        test_suites['salesforce'] = [
            IntegrationTestCase(
                name="Salesforce Health Check",
                integration="salesforce",
                endpoint="/api/integrations/salesforce/health",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Salesforce Enhanced Health",
                integration="salesforce",
                endpoint="/api/v2/health/health/salesforce",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Salesforce Bridge Status",
                integration="salesforce",
                endpoint="/api/bridge/status",
                method="GET",
                test_type="health"
            ),
        ]
        
        # Xero Test Suite
        test_suites['xero'] = [
            IntegrationTestCase(
                name="Xero Health Check",
                integration="xero",
                endpoint="/api/integrations/xero/health",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Xero Enhanced Health",
                integration="xero",
                endpoint="/api/v2/health/health/xero",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Xero Bridge Status",
                integration="xero",
                endpoint="/api/bridge/status",
                method="GET",
                test_type="health"
            ),
        ]
        
        # System-wide Test Suite
        test_suites['system'] = [
            IntegrationTestCase(
                name="Bridge Health",
                integration="system",
                endpoint="/api/bridge/health",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Enhanced Health Overview",
                integration="system",
                endpoint="/api/enhanced/health/overview",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Enhanced Detailed Health",
                integration="system",
                endpoint="/api/enhanced/health/detailed",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="All Integration Health",
                integration="system",
                endpoint="/api/v2/health/health/all",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="System Health Summary",
                integration="system",
                endpoint="/api/v2/health/health/summary",
                method="GET",
                test_type="health"
            ),
            IntegrationTestCase(
                name="Integration Discovery",
                integration="system",
                endpoint="/api/enhanced/management/discover",
                method="GET",
                test_type="functionality"
            ),
            IntegrationTestCase(
                name="Management Status",
                integration="system",
                endpoint="/api/enhanced/management/status",
                method="GET",
                test_type="functionality"
            ),
            IntegrationTestCase(
                name="Usage Analytics",
                integration="system",
                endpoint="/api/enhanced/analytics/usage",
                method="GET",
                test_type="functionality"
            ),
            IntegrationTestCase(
                name="Performance Analytics",
                integration="system",
                endpoint="/api/enhanced/analytics/performance",
                method="GET",
                test_type="functionality"
            ),
        ]
        
        return test_suites
    
    async def run_single_test(self, test_case: IntegrationTestCase) -> TestResult:
        """Run a single test case"""
        start_time = time.time()
        
        try:
            url = f"{self.base_url}{test_case.endpoint}"
            headers = test_case.headers or {}
            
            response = await self.http_client.request(
                method=test_case.method,
                url=url,
                headers=headers,
                json=test_case.data,
                timeout=test_case.timeout
            )
            
            response_time = (time.time() - start_time) * 1000  # milliseconds
            
            # Determine test status
            status = 'passed'
            error_message = None
            
            if response.status_code != test_case.expected_status:
                status = 'failed'
                error_message = f"Expected status {test_case.expected_status}, got {response.status_code}"
            
            # Try to parse response data
            try:
                response_data = response.json() if response.content else {}
            except:
                response_data = {"raw_response": response.text}
            
            return TestResult(
                test_case=test_case,
                status=status,
                response_time=response_time,
                status_code=response.status_code,
                response_data=response_data,
                error_message=error_message,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
        except httpx.TimeoutException as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                test_case=test_case,
                status='failed',
                response_time=response_time,
                error_message=f"Request timeout: {e}",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        except httpx.ConnectError as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                test_case=test_case,
                status='error',
                response_time=response_time,
                error_message=f"Connection error: {e}",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                test_case=test_case,
                status='error',
                response_time=response_time,
                error_message=f"Unexpected error: {e}",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
    
    async def run_integration_tests(self, integration_name: str) -> IntegrationTestReport:
        """Run all tests for a specific integration"""
        if integration_name not in self.test_suites:
            raise ValueError(f"No test suite found for integration: {integration_name}")
        
        test_cases = self.test_suites[integration_name]
        test_results = []
        start_time = time.time()
        
        logger.info(f"Running {len(test_cases)} tests for {integration_name} integration")
        
        # Run tests concurrently but with limits
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def run_with_semaphore(test_case):
            async with semaphore:
                return await self.run_single_test(test_case)
        
        test_results = await asyncio.gather(
            *[run_with_semaphore(test_case) for test_case in test_cases],
            return_exceptions=True
        )
        
        # Filter out exceptions and convert to test results
        filtered_results = []
        for result in test_results:
            if isinstance(result, Exception):
                logger.error(f"Test execution error: {result}")
                filtered_results.append(TestResult(
                    test_case=test_cases[0],  # Placeholder
                    status='error',
                    error_message=str(result),
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
            else:
                filtered_results.append(result)
        
        # Calculate metrics
        total_duration = time.time() - start_time
        passed_tests = sum(1 for r in filtered_results if r.status == 'passed')
        failed_tests = sum(1 for r in filtered_results if r.status == 'failed')
        error_tests = sum(1 for r in filtered_results if r.status == 'error')
        skipped_tests = sum(1 for r in filtered_results if r.status == 'skipped')
        total_tests = len(filtered_results)
        
        response_times = [r.response_time for r in filtered_results if r.response_time is not None]
        total_response_time = sum(response_times)
        average_response_time = total_response_time / len(response_times) if response_times else 0
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        return IntegrationTestReport(
            integration_name=integration_name,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            error_tests=error_tests,
            skipped_tests=skipped_tests,
            test_results=filtered_results,
            total_response_time=total_response_time,
            average_response_time=average_response_time,
            success_rate=success_rate,
            test_duration=total_duration,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    async def run_all_tests(self) -> SystemTestReport:
        """Run tests for all integrations and the system"""
        logger.info("Starting comprehensive integration testing")
        start_time = time.time()
        
        integration_reports = {}
        
        # Run tests for each integration
        for integration_name in self.test_suites.keys():
            try:
                logger.info(f"Testing {integration_name} integration...")
                report = await self.run_integration_tests(integration_name)
                integration_reports[integration_name] = report
                logger.info(f"{integration_name} tests completed: {report.success_rate:.1f}% success rate")
            except Exception as e:
                logger.error(f"Failed to run tests for {integration_name}: {e}")
                integration_reports[integration_name] = IntegrationTestReport(
                    integration_name=integration_name,
                    total_tests=0,
                    passed_tests=0,
                    failed_tests=0,
                    error_tests=1,
                    skipped_tests=0,
                    test_results=[],
                    total_response_time=0,
                    average_response_time=0,
                    success_rate=0,
                    test_duration=0,
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
        
        # Calculate system-wide metrics
        total_duration = time.time() - start_time
        total_tests = sum(r.total_tests for r in integration_reports.values())
        total_passed = sum(r.passed_tests for r in integration_reports.values())
        system_health_score = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # Determine overall status
        if system_health_score >= 95:
            overall_status = 'healthy'
        elif system_health_score >= 70:
            overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'
        
        # Generate recommendations
        recommendations = self._generate_recommendations(integration_reports)
        
        return SystemTestReport(
            total_integrations=len([k for k in self.test_suites.keys() if k != 'system']),
            integration_reports=integration_reports,
            system_health_score=system_health_score,
            overall_status=overall_status,
            test_duration=total_duration,
            recommendations=recommendations,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def _generate_recommendations(self, integration_reports: Dict[str, IntegrationTestReport]) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check for failed tests
        failed_integrations = [
            name for name, report in integration_reports.items()
            if report.success_rate < 100
        ]
        
        if failed_integrations:
            recommendations.append(f"Investigate failing tests for: {', '.join(failed_integrations)}")
        
        # Check for slow responses
        slow_integrations = [
            name for name, report in integration_reports.items()
            if report.average_response_time > 2000  # 2 seconds
        ]
        
        if slow_integrations:
            recommendations.append(f"Optimize performance for slow integrations: {', '.join(slow_integrations)}")
        
        # Check for system-wide issues
        system_report = integration_reports.get('system')
        if system_report:
            if system_report.success_rate < 100:
                recommendations.append("Address system-wide infrastructure issues")
        
        # Check for health endpoint consistency
        health_endpoint_issues = []
        for name, report in integration_reports.items():
            if name == 'system':
                continue
            
            health_tests = [r for r in report.test_results if 'health' in r.test_case.name.lower()]
            failed_health_tests = [r for r in health_tests if r.status != 'passed']
            
            if failed_health_tests:
                health_endpoint_issues.append(name)
        
        if health_endpoint_issues:
            recommendations.append(f"Fix health endpoint issues for: {', '.join(health_endpoint_issues)}")
        
        # General recommendations
        if len(recommendations) == 0:
            recommendations.append("All tests passed - system is performing well")
            recommendations.append("Consider adding more edge case tests for better coverage")
        
        return recommendations
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.http_client.aclose()
    
    def generate_report_json(self, report: SystemTestReport, file_path: str = None) -> str:
        """Generate JSON test report"""
        report_dict = asdict(report)
        json_report = json.dumps(report_dict, indent=2, default=str)
        
        if file_path:
            with open(file_path, 'w') as f:
                f.write(json_report)
            logger.info(f"Test report saved to {file_path}")
        
        return json_report
    
    def generate_report_html(self, report: SystemTestReport, file_path: str = None) -> str:
        """Generate HTML test report"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>ATOM Integration Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .summary { display: flex; gap: 20px; margin-bottom: 30px; }
        .metric { background: #e8f4fd; padding: 15px; border-radius: 5px; text-align: center; flex: 1; }
        .metric h3 { margin: 0 0 10px 0; color: #2c3e50; }
        .metric .value { font-size: 24px; font-weight: bold; color: #3498db; }
        .integration { margin-bottom: 30px; border: 1px solid #ddd; border-radius: 5px; overflow: hidden; }
        .integration-header { background: #34495e; color: white; padding: 15px; }
        .integration-body { padding: 20px; }
        .test-results { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }
        .test-case { border: 1px solid #eee; border-radius: 5px; padding: 15px; }
        .test-case.passed { border-left: 4px solid #27ae60; }
        .test-case.failed { border-left: 4px solid #e74c3c; }
        .test-case.error { border-left: 4px solid #f39c12; }
        .test-name { font-weight: bold; margin-bottom: 5px; }
        .test-status { color: #7f8c8d; font-size: 14px; }
        .test-response-time { color: #3498db; }
        .recommendations { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 20px; margin-top: 30px; }
        .recommendations h3 { margin-top: 0; color: #856404; }
        .recommendations ul { margin: 0; padding-left: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔬 ATOM Integration Test Report</h1>
        <p>Generated: {timestamp}</p>
        <p>Overall Status: <strong>{overall_status}</strong> (Health Score: {system_health_score:.1f}%)</p>
        <p>Test Duration: {test_duration:.2f} seconds</p>
    </div>

    <div class="summary">
        <div class="metric">
            <h3>Total Integrations</h3>
            <div class="value">{total_integrations}</div>
        </div>
        <div class="metric">
            <h3>System Health Score</h3>
            <div class="value">{system_health_score:.1f}%</div>
        </div>
        <div class="metric">
            <h3>Overall Status</h3>
            <div class="value">{overall_status}</div>
        </div>
        <div class="metric">
            <h3>Total Tests</h3>
            <div class="value">{total_tests}</div>
        </div>
    </div>

    <h2>📊 Integration Test Results</h2>
    {integration_sections}

    <div class="recommendations">
        <h3>💡 Recommendations</h3>
        <ul>{recommendations}</ul>
    </div>

    <div class="header" style="margin-top: 30px;">
        <p><em>Report generated by ATOM Enhanced Integration Testing System</em></p>
    </div>
</body>
</html>
        """
        
        # Generate integration sections
        integration_sections = ""
        for name, report in report.integration_reports.items():
            status_class = "passed" if report.success_rate >= 95 else "failed" if report.success_rate >= 70 else "error"
            
            integration_section = f"""
            <div class="integration">
                <div class="integration-header">
                    <h3>🔌 {name.title()} Integration</h3>
                    <p>Success Rate: {report.success_rate:.1f}% | {report.passed_tests}/{report.total_tests} passed</p>
                </div>
                <div class="integration-body">
                    <div class="test-results">
            """
            
            for test_result in report.test_results:
                test_status_class = test_result.status
                response_time_text = f"{test_result.response_time:.0f}ms" if test_result.response_time else "N/A"
                
                integration_section += f"""
                    <div class="test-case {test_status_class}">
                        <div class="test-name">{test_result.test_case.name}</div>
                        <div class="test-status">
                            Status: {test_result.status.upper()} | 
                            <span class="test-response-time">{response_time_text}</span>
                        </div>
                        {f'<div class="test-error">Error: {test_result.error_message}</div>' if test_result.error_message else ''}
                    </div>
                """
            
            integration_section += """
                    </div>
                </div>
            </div>
            """
            
            integration_sections += integration_section
        
        # Generate recommendations list
        recommendations_html = "".join([f"<li>{rec}</li>" for rec in report.recommendations])
        
        # Calculate total tests
        total_tests = sum(r.total_tests for r in report.integration_reports.values())
        
        return html_template.format(
            timestamp=report.timestamp,
            overall_status=report.overall_status.upper(),
            system_health_score=report.system_health_score,
            test_duration=report.test_duration,
            total_integrations=report.total_integrations,
            total_tests=total_tests,
            integration_sections=integration_sections,
            recommendations=recommendations_html
        )

# Main execution function
async def run_comprehensive_tests():
    """Run comprehensive integration tests"""
    tester = ComprehensiveIntegrationTester()
    
    try:
        # Run all tests
        report = await tester.run_all_tests()
        
        # Generate reports
        json_report = tester.generate_report_json(
            report, 
            "comprehensive_integration_test_report.json"
        )
        
        html_report = tester.generate_report_html(
            report,
            "comprehensive_integration_test_report.html"
        )
        
        # Save HTML report
        with open("comprehensive_integration_test_report.html", "w") as f:
            f.write(html_report)
        
        # Print summary
        print(f"\n{'='*60}")
        print("🔬 ATOM COMPREHENSIVE INTEGRATION TEST RESULTS")
        print(f"{'='*60}")
        print(f"Overall Status: {report.overall_status.upper()}")
        print(f"System Health Score: {report.system_health_score:.1f}%")
        print(f"Test Duration: {report.test_duration:.2f} seconds")
        print(f"Total Integrations: {report.total_integrations}")
        print(f"\nIntegration Results:")
        
        for name, integration_report in report.integration_reports.items():
            if name == 'system':
                continue
            print(f"  • {name.title()}: {integration_report.success_rate:.1f}% ({integration_report.passed_tests}/{integration_report.total_tests} passed)")
        
        if report.recommendations:
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"  {i}. {rec}")
        
        print(f"\n📄 Reports generated:")
        print(f"  • JSON: comprehensive_integration_test_report.json")
        print(f"  • HTML: comprehensive_integration_test_report.html")
        print(f"{'='*60}")
        
        return report
        
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(run_comprehensive_tests())