#!/usr/bin/env python3
"""
🚀 Enhanced Integration Test Suite
Tests integration routes after the registration fix
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, List, Any

class EnhancedIntegrationTester:
    """Enhanced integration tester for ATOM"""
    
    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.session = None
        self.results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_endpoint(self, method: str, url: str, integration: str, test_type: str) -> Dict[str, Any]:
        """Test a specific endpoint"""
        full_url = f"{self.base_url}{url}"
        start_time = time.time()
        
        try:
            async with self.session.request(method, full_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response_time = time.time() - start_time
                
                try:
                    data = await response.json()
                except:
                    data = await response.text()
                
                result = {
                    "test_name": f"{integration.upper()} {test_type.replace('_', ' ').title()}",
                    "integration": integration,
                    "test_type": test_type,
                    "passed": response.status == 200,
                    "duration": round(response_time, 3),
                    "status_code": response.status,
                    "details": {
                        "response_data": data,
                        "response_time": response_time,
                        "url": full_url
                    }
                }
                
        except Exception as e:
            response_time = time.time() - start_time
            result = {
                "test_name": f"{integration.upper()} {test_type.replace('_', ' ').title()}",
                "integration": integration,
                "test_type": test_type,
                "passed": False,
                "duration": round(response_time, 3),
                "details": {
                    "error": str(e),
                    "url": full_url,
                    "response_time": response_time
                }
            }
        
        self.results.append(result)
        return result
    
    async def test_integration(self, integration: str) -> List[Dict[str, Any]]:
        """Test all endpoints for an integration"""
        tests = []
        
        # Health check test
        tests.append(await self.test_endpoint("GET", f"/api/integrations/{integration}/health", integration, "health"))
        
        # Authentication test (if available)
        if integration in ['github', 'linear', 'jira', 'notion', 'slack', 'teams', 'figma']:
            tests.append(await self.test_endpoint("GET", f"/api/auth/{integration}/status", integration, "auth"))
        
        # Data retrieval tests
        if integration == 'github':
            tests.append(await self.test_endpoint("GET", "/api/integrations/github/repositories", integration, "data_retrieval"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/github/issues", integration, "data_retrieval"))
        elif integration == 'linear':
            tests.append(await self.test_endpoint("GET", "/api/integrations/linear/issues", integration, "data_retrieval"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/linear/teams", integration, "data_retrieval"))
        elif integration == 'jira':
            tests.append(await self.test_endpoint("GET", "/api/integrations/jira/projects", integration, "data_retrieval"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/jira/issues", integration, "data_retrieval"))
        elif integration == 'notion':
            tests.append(await self.test_endpoint("GET", "/api/integrations/notion/pages", integration, "data_retrieval"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/notion/databases", integration, "data_retrieval"))
        elif integration == 'slack':
            tests.append(await self.test_endpoint("GET", "/api/integrations/slack/channels", integration, "data_retrieval"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/slack/messages?channel=test", integration, "data_retrieval"))
        elif integration == 'teams':
            tests.append(await self.test_endpoint("GET", "/api/integrations/teams/teams", integration, "data_retrieval"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/teams/channels/team-1", integration, "data_retrieval"))
        elif integration == 'figma':
            tests.append(await self.test_endpoint("GET", "/api/integrations/figma/files", integration, "data_retrieval"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/figma/teams", integration, "data_retrieval"))
        
        # CRUD operations tests
        if integration == 'github':
            tests.append(await self.test_endpoint("POST", "/api/integrations/github/create", integration, "crud"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/github/repositories", integration, "crud"))
            tests.append(await self.test_endpoint("PUT", "/api/integrations/github/update/test-repo", integration, "crud"))
            tests.append(await self.test_endpoint("DELETE", "/api/integrations/github/delete/test-repo", integration, "crud"))
        elif integration == 'notion':
            tests.append(await self.test_endpoint("POST", "/api/integrations/notion/create", integration, "crud"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/notion/pages", integration, "crud"))
            tests.append(await self.test_endpoint("PUT", "/api/integrations/notion/update/test-page", integration, "crud"))
            tests.append(await self.test_endpoint("DELETE", "/api/integrations/notion/delete/test-page", integration, "crud"))
        elif integration == 'figma':
            tests.append(await self.test_endpoint("POST", "/api/integrations/figma/create", integration, "crud"))
            tests.append(await self.test_endpoint("GET", "/api/integrations/figma/files", integration, "crud"))
            tests.append(await self.test_endpoint("PUT", "/api/integrations/figma/update/test-file", integration, "crud"))
            tests.append(await self.test_endpoint("DELETE", "/api/integrations/figma/delete/test-file", integration, "crud"))
        
        return tests
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive integration tests"""
        print("🚀 Starting Enhanced Integration Testing...")
        
        integrations = ['github', 'linear', 'jira', 'notion', 'slack', 'teams', 'figma', 'asana']
        
        start_time = time.time()
        
        # Test all integrations
        for integration in integrations:
            print(f"📋 Testing {integration.upper()} integration...")
            await self.test_integration(integration)
        
        # Test comprehensive health endpoint
        print("🏥 Testing comprehensive health endpoint...")
        await self.test_endpoint("GET", "/api/integrations/comprehensive-health", "system", "health")
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        passed = len([r for r in self.results if r['passed']])
        failed = len([r for r in self.results if not r['passed']])
        total = len(self.results)
        success_rate = round((passed / total) * 100, 1) if total > 0 else 0
        
        # Group by test type
        test_type_stats = {}
        integration_stats = {}
        
        for result in self.results:
            test_type = result['test_type']
            integration = result['integration']
            
            if test_type not in test_type_stats:
                test_type_stats[test_type] = {'passed': 0, 'total': 0}
            if integration not in integration_stats:
                integration_stats[integration] = {'passed': 0, 'total': 0}
            
            test_type_stats[test_type]['total'] += 1
            integration_stats[integration]['total'] += 1
            
            if result['passed']:
                test_type_stats[test_type]['passed'] += 1
                integration_stats[integration]['passed'] += 1
        
        # Calculate success rates
        for test_type in test_type_stats:
            stats = test_type_stats[test_type]
            stats['success_rate'] = round((stats['passed'] / stats['total']) * 100, 1)
        
        for integration in integration_stats:
            stats = integration_stats[integration]
            stats['success_rate'] = round((stats['passed'] / stats['total']) * 100, 1)
        
        # Generate recommendations
        recommendations = []
        
        for integration, stats in integration_stats.items():
            if stats['success_rate'] < 50:
                recommendations.append(f"🚨 {integration.upper()}: Needs attention ({stats['success_rate']}% success rate)")
            elif stats['success_rate'] < 80:
                recommendations.append(f"⚠️  {integration.upper()}: Needs improvement ({stats['success_rate']}% success rate)")
            else:
                recommendations.append(f"✅ {integration.upper()}: Good performance ({stats['success_rate']}% success rate)")
        
        for test_type, stats in test_type_stats.items():
            if stats['success_rate'] < 50:
                recommendations.append(f"🚨 {test_type.replace('_', ' ').title()}: Critical improvements needed ({stats['success_rate']}% success rate)")
            elif stats['success_rate'] < 80:
                recommendations.append(f"⚠️  {test_type.replace('_', ' ').title()}: Improvements needed ({stats['success_rate']}% success rate)")
        
        summary = {
            "summary": {
                "passed": passed,
                "failed": failed,
                "total": total,
                "success_rate": success_rate,
                "duration": round(total_time, 2),
                "timestamp": datetime.utcnow().isoformat()
            },
            "test_type_stats": test_type_stats,
            "integration_stats": integration_stats,
            "results": self.results,
            "recommendations": recommendations
        }
        
        return summary

async def main():
    """Main test function"""
    async with EnhancedIntegrationTester() as tester:
        results = await tester.run_comprehensive_test()
        
        # Save results
        with open('enhanced_integration_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        # Print summary
        print(f"\n📊 Enhanced Integration Test Results:")
        print(f"   Passed: {results['summary']['passed']}")
        print(f"   Failed: {results['summary']['failed']}")
        print(f"   Total: {results['summary']['total']}")
        print(f"   Success Rate: {results['summary']['success_rate']}%")
        print(f"   Duration: {results['summary']['duration']}s")
        
        print(f"\n🎯 Integration Performance:")
        for integration, stats in results['integration_stats'].items():
            status = "✅" if stats['success_rate'] >= 80 else "⚠️" if stats['success_rate'] >= 50 else "🚨"
            print(f"   {status} {integration.upper()}: {stats['success_rate']}% ({stats['passed']}/{stats['total']})")
        
        print(f"\n📝 Recommendations:")
        for rec in results['recommendations']:
            print(f"   {rec}")
        
        print(f"\n💾 Results saved to: enhanced_integration_test_results.json")

if __name__ == "__main__":
    asyncio.run(main())