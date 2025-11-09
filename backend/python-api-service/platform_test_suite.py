"""
ATOM Platform Test Suite
Comprehensive testing and optimization framework for all integrations
Following enterprise testing standards and best practices
"""

import asyncio
import json
import logging
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import httpx
from loguru import logger

@dataclass
class TestResult:
    """Test result data structure"""
    integration: str
    test_type: str
    status: str  # passed, failed, skipped
    duration: float
    details: Dict[str, Any]
    errors: List[str]
    timestamp: datetime

class PlatformTestSuite:
    """Comprehensive platform testing framework"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = datetime.now()
        
        # Integration endpoints for testing
        self.integration_endpoints = {
            'slack': {
                'health': '/api/slack/health',
                'auth': '/api/auth/slack/status'
            },
            'teams': {
                'health': '/api/teams/health',
                'auth': '/api/auth/teams/status'
            },
            'gmail': {
                'health': '/api/gmail/health',
                'auth': '/api/auth/gmail/status'
            },
            'bamboohr': {
                'health': '/api/bamboohr/health',
                'auth': '/api/auth/bamboohr/status'
            }
            # Add more integrations as needed
        }
        
        # Test configuration
        self.base_url = "http://localhost:8000"
        self.timeout = httpx.Timeout(30.0)
        self.max_concurrent = 5

    async def run_health_checks(self) -> List[TestResult]:
        """Run health checks for all integrations"""
        logger.info("🔍 Running health checks for all integrations...")
        results = []
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for integration, endpoints in self.integration_endpoints.items():
                result = await self._test_health_check(client, integration, endpoints['health'])
                results.append(result)
        
        return results

    async def _test_health_check(self, client: httpx.AsyncClient, integration: str, endpoint: str) -> TestResult:
        """Test health check endpoint for specific integration"""
        start_time = time.time()
        errors = []
        details = {}
        
        try:
            url = f"{self.base_url}{endpoint}"
            response = await client.get(url)
            
            duration = time.time() - start_time
            status = "passed" if response.status_code == 200 else "failed"
            
            details = {
                "status_code": response.status_code,
                "url": url
            }
            
            if response.status_code != 200:
                errors.append(f"Health check returned {response.status_code}")
            
        except Exception as e:
            duration = time.time() - start_time
            status = "failed"
            errors.append(f"Exception: {str(e)}")
        
        return TestResult(
            integration=integration,
            test_type="health_check",
            status=status,
            duration=duration,
            details=details,
            errors=errors,
            timestamp=datetime.utcnow()
        )

    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        passed_tests = len([r for r in self.results if r.status == "passed"])
        failed_tests = len([r for r in self.results if r.status == "failed"])
        total_tests = len(self.results)
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "test_start_time": self.start_time.isoformat(),
                "test_end_time": datetime.utcnow().isoformat()
            },
            "failed_tests": [r for r in self.results if r.status == "failed"],
            "integration_results": {}
        }

    async def run_quick_test(self) -> Dict[str, Any]:
        """Run quick test for key integrations"""
        logger.info("⚡ Running quick platform test...")
        
        self.results = await self.run_health_checks()
        report = self.generate_test_report()
        
        self._print_summary(report)
        return report

    def _print_summary(self, report: Dict[str, Any]):
        """Print test summary to console"""
        summary = report["summary"]
        
        print("\n" + "="*80)
        print("🎯 ATOM PLATFORM QUICK TEST RESULTS")
        print("="*80)
        
        print(f"📊 Overall Results:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   Passed: {summary['passed_tests']} ✅")
        print(f"   Failed: {summary['failed_tests']} ❌")
        print(f"   Success Rate: {summary['success_rate']:.1f}%")
        
        if report["failed_tests"]:
            print(f"\n❌ Failed Tests:")
            for test in report["failed_tests"][:5]:
                print(f"   {test.integration}.{test.test_type}: {test.errors[0] if test.errors else 'Unknown error'}")
        
        print("\n" + "="*80)

async def main():
    """Main execution function"""
    test_suite = PlatformTestSuite()
    
    try:
        await test_suite.run_quick_test()
    except KeyboardInterrupt:
        logger.info("Test suite interrupted by user")
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())