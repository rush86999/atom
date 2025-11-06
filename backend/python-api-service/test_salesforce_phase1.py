#!/usr/bin/env python3
"""
🧪 Salesforce Phase 1 Enhanced Features Test Suite
Comprehensive tests for webhooks, bulk API, custom objects, and enhanced analytics
"""

import sys
import os
import asyncio
import requests
import json
import time
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import base64

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class SalesforcePhase1Tester:
    """Test suite for Salesforce Phase 1 enhanced features"""
    
    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.test_user_id = "test_salesforce_phase1_user"
        self.webhook_secret = "test_webhook_secret_for_phase1"
        
        # Test data
        self.test_bulk_data = [
            {"Name": f"Test Account {i}", "Type": "Prospect", "Industry": "Technology"}
            for i in range(1, 6)
        ]
        
        self.webhook_test_payload = {
            "event_type": "Account.created",
            "object": "Account",
            "ids": ["001test000000000001"],
            "changeType": "created",
            "changedFields": ["Name", "Type", "Industry"]
        }
    
    async def run_all_tests(self):
        """Run all Phase 1 feature tests"""
        print("🚀 Starting Salesforce Phase 1 Enhanced Features Test Suite")
        print("=" * 70)
        
        test_results = {}
        
        # Test 1: Webhooks
        test_results["webhooks"] = await self.test_webhook_features()
        
        # Test 2: Bulk API
        test_results["bulk_api"] = await self.test_bulk_api_features()
        
        # Test 3: Custom Objects
        test_results["custom_objects"] = await self.test_custom_object_features()
        
        # Test 4: Enhanced Analytics
        test_results["enhanced_analytics"] = await self.test_enhanced_analytics_features()
        
        # Test 5: Administration
        test_results["administration"] = await self.test_administration_features()
        
        # Generate summary report
        await self.generate_test_summary(test_results)
        
        return test_results
    
    async def test_webhook_features(self):
        """Test real-time webhook features"""
        print("\n📡 Testing Webhook Features...")
        print("-" * 40)
        
        results = {"passed": 0, "failed": 0, "tests": []}
        
        # Test 1.1: Create webhook subscription
        try:
            subscription_data = {
                "user_id": self.test_user_id,
                "object_type": "Account",
                "events": ["Account.created", "Account.updated"],
                "callback_url": "https://example.com/webhook/salesforce",
                "active": True
            }
            
            response = requests.post(
                f"{self.base_url}/api/salesforce/webhooks/subscribe",
                json=subscription_data,
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                if result.get("ok") and "subscription_id" in result:
                    print("✅ Webhook subscription created successfully")
                    print(f"   Subscription ID: {result['subscription_id']}")
                    results["passed"] += 1
                    results["tests"].append("Webhook subscription creation: PASSED")
                else:
                    print("❌ Webhook subscription creation failed")
                    results["failed"] += 1
                    results["tests"].append("Webhook subscription creation: FAILED")
            else:
                print(f"❌ Webhook subscription creation failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Webhook subscription creation: FAILED")
                
        except Exception as e:
            print(f"❌ Webhook subscription test error: {e}")
            results["failed"] += 1
            results["tests"].append("Webhook subscription creation: ERROR")
        
        # Test 1.2: List webhook subscriptions
        try:
            response = requests.get(
                f"{self.base_url}/api/salesforce/webhooks/subscriptions",
                params={"user_id": self.test_user_id},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok") and "subscriptions" in result:
                    print("✅ Webhook subscriptions listed successfully")
                    print(f"   Found {len(result['subscriptions'])} subscriptions")
                    results["passed"] += 1
                    results["tests"].append("Webhook subscription listing: PASSED")
                else:
                    print("❌ Webhook subscription listing failed")
                    results["failed"] += 1
                    results["tests"].append("Webhook subscription listing: FAILED")
            else:
                print(f"❌ Webhook subscription listing failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Webhook subscription listing: FAILED")
                
        except Exception as e:
            print(f"❌ Webhook listing test error: {e}")
            results["failed"] += 1
            results["tests"].append("Webhook subscription listing: ERROR")
        
        # Test 1.3: Process webhook payload
        try:
            # Generate signature
            timestamp = str(int(time.time()))
            message = f"{timestamp}.{json.dumps(self.webhook_test_payload, sort_keys=True)}"
            signature = hmac.new(
                self.webhook_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
            signature_b64 = base64.b64encode(signature).decode()
            
            headers = {
                "X-Salesforce-Signature": signature_b64,
                "X-Salesforce-Timestamp": timestamp,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{self.base_url}/webhooks/salesforce",
                json=self.webhook_test_payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print("✅ Webhook payload processed successfully")
                    results["passed"] += 1
                    results["tests"].append("Webhook payload processing: PASSED")
                else:
                    print("❌ Webhook payload processing failed")
                    results["failed"] += 1
                    results["tests"].append("Webhook payload processing: FAILED")
            else:
                print(f"❌ Webhook processing failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Webhook payload processing: FAILED")
                
        except Exception as e:
            print(f"❌ Webhook processing test error: {e}")
            results["failed"] += 1
            results["tests"].append("Webhook payload processing: ERROR")
        
        return results
    
    async def test_bulk_api_features(self):
        """Test bulk API features"""
        print("\n📦 Testing Bulk API Features...")
        print("-" * 40)
        
        results = {"passed": 0, "failed": 0, "tests": []}
        
        # Test 2.1: Create bulk job
        try:
            bulk_job_data = {
                "user_id": self.test_user_id,
                "operation": "insert",
                "object_type": "Account",
                "data": self.test_bulk_data
            }
            
            response = requests.post(
                f"{self.base_url}/api/salesforce/bulk/create-job",
                json=bulk_job_data,
                timeout=60  # Bulk operations can take longer
            )
            
            if response.status_code == 201:
                result = response.json()
                if result.get("ok") and "job_id" in result:
                    print("✅ Bulk job created successfully")
                    print(f"   Job ID: {result['job_id']}")
                    print(f"   Total records: {result['total_records']}")
                    job_id = result['job_id']
                    results["passed"] += 1
                    results["tests"].append("Bulk job creation: PASSED")
                    
                    # Test 2.2: Get bulk job status
                    await asyncio.sleep(2)  # Wait for job processing
                    
                    try:
                        status_response = requests.get(
                            f"{self.base_url}/api/salesforce/bulk/jobs/{job_id}",
                            timeout=30
                        )
                        
                        if status_response.status_code == 200:
                            status_result = status_response.json()
                            if status_result.get("ok"):
                                print("✅ Bulk job status retrieved successfully")
                                print(f"   Status: {status_result['job']['status']}")
                                results["passed"] += 1
                                results["tests"].append("Bulk job status retrieval: PASSED")
                            else:
                                print("❌ Bulk job status retrieval failed")
                                results["failed"] += 1
                                results["tests"].append("Bulk job status retrieval: FAILED")
                        else:
                            print(f"❌ Bulk job status retrieval failed: {status_response.status_code}")
                            results["failed"] += 1
                            results["tests"].append("Bulk job status retrieval: FAILED")
                            
                    except Exception as e:
                        print(f"❌ Bulk job status test error: {e}")
                        results["failed"] += 1
                        results["tests"].append("Bulk job status retrieval: ERROR")
                        
                else:
                    print("❌ Bulk job creation failed")
                    results["failed"] += 1
                    results["tests"].append("Bulk job creation: FAILED")
            else:
                print(f"❌ Bulk job creation failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Bulk job creation: FAILED")
                
        except Exception as e:
            print(f"❌ Bulk job creation test error: {e}")
            results["failed"] += 1
            results["tests"].append("Bulk job creation: ERROR")
        
        # Test 2.3: List bulk jobs
        try:
            response = requests.get(
                f"{self.base_url}/api/salesforce/bulk/jobs",
                params={"user_id": self.test_user_id},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok") and "jobs" in result:
                    print("✅ Bulk jobs listed successfully")
                    print(f"   Found {result['total_count']} jobs")
                    results["passed"] += 1
                    results["tests"].append("Bulk jobs listing: PASSED")
                else:
                    print("❌ Bulk jobs listing failed")
                    results["failed"] += 1
                    results["tests"].append("Bulk jobs listing: FAILED")
            else:
                print(f"❌ Bulk jobs listing failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Bulk jobs listing: FAILED")
                
        except Exception as e:
            print(f"❌ Bulk jobs listing test error: {e}")
            results["failed"] += 1
            results["tests"].append("Bulk jobs listing: ERROR")
        
        return results
    
    async def test_custom_object_features(self):
        """Test custom objects features"""
        print("\n🔧 Testing Custom Objects Features...")
        print("-" * 40)
        
        results = {"passed": 0, "failed": 0, "tests": []}
        
        # Test 3.1: List custom objects
        try:
            response = requests.get(
                f"{self.base_url}/api/salesforce/custom-objects",
                params={"user_id": self.test_user_id},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok") and "custom_objects" in result:
                    print("✅ Custom objects listed successfully")
                    print(f"   Found {result['total_count']} custom objects")
                    results["passed"] += 1
                    results["tests"].append("Custom objects listing: PASSED")
                    
                    # Test 3.2: Get custom object metadata
                    if result["custom_objects"]:
                        first_object = result["custom_objects"][0]
                        object_name = first_object["name"]
                        
                        try:
                            metadata_response = requests.get(
                                f"{self.base_url}/api/salesforce/custom-objects/{object_name}/metadata",
                                params={"user_id": self.test_user_id},
                                timeout=30
                            )
                            
                            if metadata_response.status_code == 200:
                                metadata_result = metadata_response.json()
                                if metadata_result.get("ok"):
                                    print("✅ Custom object metadata retrieved successfully")
                                    print(f"   Object: {metadata_result['custom_object']['name']}")
                                    results["passed"] += 1
                                    results["tests"].append("Custom object metadata: PASSED")
                                else:
                                    print("❌ Custom object metadata retrieval failed")
                                    results["failed"] += 1
                                    results["tests"].append("Custom object metadata: FAILED")
                            else:
                                print(f"❌ Custom object metadata retrieval failed: {metadata_response.status_code}")
                                results["failed"] += 1
                                results["tests"].append("Custom object metadata: FAILED")
                                
                        except Exception as e:
                            print(f"❌ Custom object metadata test error: {e}")
                            results["failed"] += 1
                            results["tests"].append("Custom object metadata: ERROR")
                    
                else:
                    print("❌ Custom objects listing failed")
                    results["failed"] += 1
                    results["tests"].append("Custom objects listing: FAILED")
            else:
                print(f"❌ Custom objects listing failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Custom objects listing: FAILED")
                
        except Exception as e:
            print(f"❌ Custom objects listing test error: {e}")
            results["failed"] += 1
            results["tests"].append("Custom objects listing: ERROR")
        
        # Test 3.3: Query custom object
        try:
            query_data = {
                "user_id": self.test_user_id,
                "fields": ["Id", "Name", "CreatedDate"],
                "where_clause": "Name != null",
                "limit": 10
            }
            
            response = requests.post(
                f"{self.base_url}/api/salesforce/custom-objects/Custom_Object__c/query",
                json=query_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print("✅ Custom object query executed successfully")
                    print(f"   Retrieved {len(result['records'])} records")
                    results["passed"] += 1
                    results["tests"].append("Custom object querying: PASSED")
                else:
                    print("❌ Custom object query failed")
                    results["failed"] += 1
                    results["tests"].append("Custom object querying: FAILED")
            else:
                print(f"❌ Custom object query failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Custom object querying: FAILED")
                
        except Exception as e:
            print(f"❌ Custom object query test error: {e}")
            results["failed"] += 1
            results["tests"].append("Custom object querying: ERROR")
        
        return results
    
    async def test_enhanced_analytics_features(self):
        """Test enhanced analytics features"""
        print("\n📊 Testing Enhanced Analytics Features...")
        print("-" * 40)
        
        results = {"passed": 0, "failed": 0, "tests": []}
        
        # Test 4.1: Get comprehensive analytics
        try:
            response = requests.get(
                f"{self.base_url}/api/salesforce/analytics/enhanced",
                params={
                    "user_id": self.test_user_id,
                    "type": "comprehensive",
                    "date_range": "30d",
                    "cache": "false"  # Force fresh computation
                },
                timeout=60  # Analytics can take longer
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print("✅ Enhanced analytics retrieved successfully")
                    analytics = result["analytics"]
                    
                    required_keys = [
                        "pipeline_analytics",
                        "lead_analytics", 
                        "account_analytics",
                        "real_time_metrics",
                        "trend_analysis",
                        "predictive_insights"
                    ]
                    
                    missing_keys = [key for key in required_keys if key not in analytics]
                    
                    if not missing_keys:
                        print("   All analytics components present")
                        results["passed"] += 1
                        results["tests"].append("Enhanced analytics retrieval: PASSED")
                    else:
                        print(f"   Missing analytics components: {missing_keys}")
                        results["failed"] += 1
                        results["tests"].append("Enhanced analytics retrieval: FAILED")
                else:
                    print("❌ Enhanced analytics retrieval failed")
                    results["failed"] += 1
                    results["tests"].append("Enhanced analytics retrieval: FAILED")
            else:
                print(f"❌ Enhanced analytics retrieval failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Enhanced analytics retrieval: FAILED")
                
        except Exception as e:
            print(f"❌ Enhanced analytics test error: {e}")
            results["failed"] += 1
            results["tests"].append("Enhanced analytics retrieval: ERROR")
        
        # Test 4.2: Get real-time metrics
        try:
            response = requests.get(
                f"{self.base_url}/api/salesforce/analytics/realtime",
                params={"user_id": self.test_user_id},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    realtime_metrics = result["realtime_metrics"]
                    
                    if "last_24_hours" in realtime_metrics and "webhook_events" in realtime_metrics:
                        print("✅ Real-time metrics retrieved successfully")
                        print(f"   Metrics categories: {list(realtime_metrics.keys())}")
                        results["passed"] += 1
                        results["tests"].append("Real-time metrics: PASSED")
                    else:
                        print("❌ Real-time metrics missing required components")
                        results["failed"] += 1
                        results["tests"].append("Real-time metrics: FAILED")
                else:
                    print("❌ Real-time metrics retrieval failed")
                    results["failed"] += 1
                    results["tests"].append("Real-time metrics: FAILED")
            else:
                print(f"❌ Real-time metrics retrieval failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Real-time metrics: FAILED")
                
        except Exception as e:
            print(f"❌ Real-time metrics test error: {e}")
            results["failed"] += 1
            results["tests"].append("Real-time metrics: ERROR")
        
        # Test 4.3: Test analytics caching
        try:
            # First request
            response1 = requests.get(
                f"{self.base_url}/api/salesforce/analytics/enhanced",
                params={
                    "user_id": self.test_user_id,
                    "type": "pipeline",
                    "date_range": "7d",
                    "cache": "true"
                },
                timeout=30
            )
            
            # Second request (should use cache)
            response2 = requests.get(
                f"{self.base_url}/api/salesforce/analytics/enhanced",
                params={
                    "user_id": self.test_user_id,
                    "type": "pipeline",
                    "date_range": "7d",
                    "cache": "true"
                },
                timeout=30
            )
            
            if response1.status_code == 200 and response2.status_code == 200:
                result1 = response1.json()
                result2 = response2.json()
                
                if result1.get("ok") and result2.get("ok"):
                    cache_used = result2.get("cached", False)
                    print("✅ Analytics caching test completed")
                    print(f"   Cache used: {cache_used}")
                    results["passed"] += 1
                    results["tests"].append("Analytics caching: PASSED")
                else:
                    print("❌ Analytics caching test failed")
                    results["failed"] += 1
                    results["tests"].append("Analytics caching: FAILED")
            else:
                print(f"❌ Analytics caching test failed: HTTP {response1.status_code}/{response2.status_code}")
                results["failed"] += 1
                results["tests"].append("Analytics caching: FAILED")
                
        except Exception as e:
            print(f"❌ Analytics caching test error: {e}")
            results["failed"] += 1
            results["tests"].append("Analytics caching: ERROR")
        
        return results
    
    async def test_administration_features(self):
        """Test administration features"""
        print("\n⚙️ Testing Administration Features...")
        print("-" * 40)
        
        results = {"passed": 0, "failed": 0, "tests": []}
        
        # Test 5.1: Health check
        try:
            response = requests.get(
                f"{self.base_url}/api/salesforce/admin/health",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print("✅ Health check passed")
                    health_info = {
                        "provider": result.get("provider"),
                        "version": result.get("version"),
                        "phase": result.get("phase"),
                        "features": list(result.get("features", {}).keys())
                    }
                    print(f"   {health_info}")
                    results["passed"] += 1
                    results["tests"].append("Health check: PASSED")
                else:
                    print("❌ Health check failed")
                    results["failed"] += 1
                    results["tests"].append("Health check: FAILED")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Health check: FAILED")
                
        except Exception as e:
            print(f"❌ Health check test error: {e}")
            results["failed"] += 1
            results["tests"].append("Health check: ERROR")
        
        # Test 5.2: Get integration metrics
        try:
            response = requests.get(
                f"{self.base_url}/api/salesforce/admin/metrics",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print("✅ Integration metrics retrieved successfully")
                    metrics_info = {
                        "period": result.get("period"),
                        "has_daily_metrics": "daily_metrics" in result,
                        "has_top_users": "top_users" in result,
                        "has_error_breakdown": "error_breakdown" in result
                    }
                    print(f"   {metrics_info}")
                    results["passed"] += 1
                    results["tests"].append("Integration metrics: PASSED")
                else:
                    print("❌ Integration metrics retrieval failed")
                    results["failed"] += 1
                    results["tests"].append("Integration metrics: FAILED")
            else:
                print(f"❌ Integration metrics retrieval failed: {response.status_code}")
                results["failed"] += 1
                results["tests"].append("Integration metrics: FAILED")
                
        except Exception as e:
            print(f"❌ Integration metrics test error: {e}")
            results["failed"] += 1
            results["tests"].append("Integration metrics: ERROR")
        
        return results
    
    async def generate_test_summary(self, test_results):
        """Generate comprehensive test summary report"""
        print("\n" + "=" * 70)
        print("📋 TEST SUMMARY REPORT")
        print("=" * 70)
        
        total_passed = 0
        total_failed = 0
        
        for feature, results in test_results.items():
            total_passed += results["passed"]
            total_failed += results["failed"]
            
            status = "✅ PASS" if results["failed"] == 0 else "❌ FAIL"
            feature_name = feature.replace("_", " ").title()
            
            print(f"\n{feature_name}: {status}")
            print(f"   Passed: {results['passed']}")
            print(f"   Failed: {results['failed']}")
            print(f"   Total:  {results['passed'] + results['failed']}")
            
            if results["failed"] > 0:
                print("   Failed tests:")
                for test in results["tests"]:
                    if "FAILED" in test or "ERROR" in test:
                        print(f"     - {test}")
        
        print("\n" + "=" * 70)
        print("📊 OVERALL RESULTS")
        print("=" * 70)
        print(f"Total Tests Passed:  {total_passed}")
        print(f"Total Tests Failed:  {total_failed}")
        print(f"Total Tests Run:     {total_passed + total_failed}")
        
        success_rate = (total_passed / (total_passed + total_failed)) * 100 if (total_passed + total_failed) > 0 else 0
        print(f"Success Rate:        {success_rate:.1f}%")
        
        if total_failed == 0:
            print("\n🎉 ALL TESTS PASSED! Salesforce Phase 1 integration is working correctly.")
        else:
            print(f"\n⚠️ {total_failed} test(s) failed. Please review the implementation.")
        
        print("\n🚀 Next Steps:")
        print("1. Review any failed tests and fix underlying issues")
        print("2. Run integration tests with actual Salesforce instance")
        print("3. Configure production webhook endpoints")
        print("4. Set up monitoring and alerting for production deployment")
        print("5. Document API endpoints for frontend integration")
        
        print("=" * 70)
        
        return {
            "total_passed": total_passed,
            "total_failed": total_failed,
            "success_rate": success_rate,
            "all_passed": total_failed == 0
        }

async def main():
    """Main test runner"""
    print("🧪 Salesforce Phase 1 Enhanced Features Test Suite")
    print("Testing Webhooks, Bulk API, Custom Objects, and Enhanced Analytics")
    print("Starting tests...\n")
    
    # Check if server is running
    tester = SalesforcePhase1Tester()
    
    try:
        response = requests.get(f"{tester.base_url}/healthz", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not responding correctly. Please ensure the API server is running on port 5058.")
            return False
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to server. Please ensure the API server is running on port 5058.")
        return False
    
    # Run tests
    test_results = await tester.run_all_tests()
    
    return test_results["all_passed"]

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Test suite failed with error: {e}")
        sys.exit(1)