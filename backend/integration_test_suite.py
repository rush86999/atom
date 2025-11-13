#!/usr/bin/env python3
"""
ATOM Integration Test Suite
Tests all frontend-backend connections
"""

import requests
import json
import time
import sys
from typing import Dict, List, Any

class AtomIntegrationTester:
    def __init__(self):
        self.backend_url = "http://localhost:5058"
        self.results = {}
        
    def test_backend_health(self) -> Dict[str, Any]:
        """Test backend health endpoint"""
        try:
            response = requests.get(f"{self.backend_url}/healthz", timeout=5)
            return {
                "ok": response.status_code == 200,
                "status_code": response.status_code,
                "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                "response_time": response.elapsed.total_seconds()
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "response_time": 5.0
            }
    
    def test_service_integrations(self) -> Dict[str, Dict[str, Any]]:
        """Test all service integrations"""
        services = ['gmail', 'slack', 'asana', 'github', 'notion', 'trello', 'outlook']
        results = {}
        
        for service in services:
            try:
                start_time = time.time()
                response = requests.get(f"{self.backend_url}/api/{service}/health", timeout=10)
                end_time = time.time()
                
                results[service] = {
                    "ok": response.status_code == 200,
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                }
            except Exception as e:
                results[service] = {
                    "ok": False,
                    "error": str(e),
                    "response_time": 10.0
                }
        
        return results
    
    def test_api_endpoints(self) -> Dict[str, Any]:
        """Test general API endpoints"""
        try:
            response = requests.get(f"{self.backend_url}/api/test", timeout=5)
            return {
                "ok": response.status_code == 200,
                "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                "status_code": response.status_code
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e)
            }
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all integration tests"""
        print("🚀 Starting ATOM Integration Tests...")
        print(f"📍 Testing backend at: {self.backend_url}")
        print("=" * 50)
        
        # Test backend health
        print("1. Testing backend health...")
        health_result = self.test_backend_health()
        self.results["health"] = health_result
        
        if health_result["ok"]:
            print(f"   ✅ Backend healthy (Response time: {health_result.get('response_time', 0):.2f}s)")
            print(f"   📊 Status: {health_result.get('data', {}).get('status', 'Unknown')}")
        else:
            print(f"   ❌ Backend unhealthy: {health_result.get('error', 'Unknown error')}")
            print("   ⚠️  Skipping other tests due to backend connection failure")
            return self.results
        
        # Test API endpoint
        print("\n2. Testing API endpoint...")
        api_result = self.test_api_endpoints()
        self.results["api"] = api_result
        
        if api_result["ok"]:
            print("   ✅ API endpoint working")
        else:
            print(f"   ❌ API endpoint failed: {api_result.get('error', 'Unknown error')}")
        
        # Test service integrations
        print("\n3. Testing service integrations...")
        service_results = self.test_service_integrations()
        self.results["services"] = service_results
        
        for service, result in service_results.items():
            if result["ok"]:
                print(f"   ✅ {service.capitalize()}: Connected ({result.get('response_time', 0):.2f}s)")
            else:
                print(f"   ❌ {service.capitalize()}: {result.get('error', 'Connection failed')}")
        
        return self.results
    
    def generate_report(self) -> str:
        """Generate integration test report"""
        if not self.results:
            return "No test results available. Run tests first."
        
        report = []
        report.append("ATOM INTEGRATION TEST REPORT")
        report.append("=" * 40)
        report.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Health status
        health = self.results.get("health", {})
        report.append("BACKEND HEALTH:")
        if health.get("ok"):
            report.append(f"  Status: ✅ HEALTHY")
            report.append(f"  Response Time: {health.get('response_time', 0):.2f}s")
        else:
            report.append(f"  Status: ❌ UNHEALTHY")
            report.append(f"  Error: {health.get('error', 'Unknown')}")
        report.append("")
        
        # Service integrations
        services = self.results.get("services", {})
        report.append("SERVICE INTEGRATIONS:")
        connected_count = sum(1 for s in services.values() if s.get("ok"))
        total_count = len(services)
        
        for service, result in services.items():
            status = "✅ CONNECTED" if result.get("ok") else "❌ FAILED"
            response_time = result.get("response_time", 0)
            report.append(f"  {service.capitalize()}: {status} ({response_time:.2f}s)")
        
        report.append(f"\nSummary: {connected_count}/{total_count} services connected")
        report.append("")
        
        # Overall status
        overall_healthy = health.get("ok") and connected_count > 0
        report.append(f"OVERALL STATUS: {'✅ HEALTHY' if overall_healthy else '❌ NEEDS ATTENTION'}")
        
        return "\n".join(report)

def main():
    """Main test execution"""
    tester = AtomIntegrationTester()
    
    try:
        results = tester.run_comprehensive_test()
        report = tester.generate_report()
        print("\n" + report)
        
        # Save report to file
        with open("integration_test_report.txt", "w") as f:
            f.write(report)
        
        print(f"\n📄 Report saved to: integration_test_report.txt")
        
        # Exit with appropriate code
        overall_healthy = results.get("health", {}).get("ok") and \
                         sum(1 for results in results.get("services", {}).values() if results.get("ok")) > 0
        
        sys.exit(0 if overall_healthy else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()