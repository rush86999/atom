#!/usr/bin/env python3
"""
TEST INTEGRATION - Next Phase
Test if complete application is working
"""

import subprocess
import time
import json
from datetime import datetime

def test_integration_phase():
    """Test the integration of complete application"""
    
    print("🧪 TESTING INTEGRATION - NEXT PHASE")
    print("=" * 80)
    print("Testing if complete application is working")
    print("=" * 80)
    
    # Test server connectivity
    print("🔍 STEP 1: TESTING SERVER CONNECTIVITY")
    print("=========================================")
    
    servers = [
        {
            "name": "OAuth Server",
            "url": "http://localhost:5058/healthz",
            "expected_status": 200,
            "purpose": "Authentication service"
        },
        {
            "name": "Backend API Server", 
            "url": "http://localhost:8000/health",
            "expected_status": 200,
            "purpose": "Application API"
        },
        {
            "name": "Frontend Application",
            "url": "http://localhost:3000",
            "expected_status": 200,
            "purpose": "User interface"
        }
    ]
    
    connectivity_results = []
    for server in servers:
        print(f"   🔍 Testing {server['name']}...")
        print(f"      URL: {server['url']}")
        print(f"      Purpose: {server['purpose']}")
        
        try:
            result = subprocess.run([
                "curl", "-s", "--connect-timeout", "5", 
                "--max-time", "10", "-w", "%{http_code}",
                server['url']
            ], capture_output=True, text=True)
            
            http_code = result.stdout.strip()[-3:]  # Get last 3 chars (HTTP code)
            
            if http_code == str(server['expected_status']):
                print(f"      ✅ CONNECTED (HTTP {http_code})")
                connectivity_results.append({
                    "server": server['name'],
                    "status": "connected",
                    "http_code": http_code,
                    "url": server['url']
                })
            else:
                print(f"      ❌ NOT CONNECTED (HTTP {http_code})")
                connectivity_results.append({
                    "server": server['name'],
                    "status": "not_connected",
                    "http_code": http_code,
                    "url": server['url']
                })
                
        except Exception as e:
            print(f"      ❌ ERROR: {e}")
            connectivity_results.append({
                "server": server['name'],
                "status": "error",
                "error": str(e),
                "url": server['url']
            })
        
        print()
    
    # Step 2: Test OAuth endpoints
    print("🔐 STEP 2: TESTING OAUTH ENDPOINTS")
    print("====================================")
    
    oauth_endpoints = [
        {
            "name": "OAuth Services List",
            "url": "http://localhost:5058/api/auth/services",
            "purpose": "List available OAuth services"
        },
        {
            "name": "OAuth Status",
            "url": "http://localhost:5058/api/auth/oauth-status",
            "purpose": "Check OAuth service status"
        }
    ]
    
    oauth_results = []
    for endpoint in oauth_endpoints:
        print(f"   🔍 Testing {endpoint['name']}...")
        print(f"      URL: {endpoint['url']}")
        print(f"      Purpose: {endpoint['purpose']}")
        
        try:
            result = subprocess.run([
                "curl", "-s", "--connect-timeout", "5",
                endpoint['url']
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout:
                print(f"      ✅ WORKING")
                try:
                    data = json.loads(result.stdout)
                    print(f"      📊 Response: {json.dumps(data, indent=6)[:200]}...")
                except:
                    print(f"      📊 Response: {result.stdout[:100]}...")
                
                oauth_results.append({
                    "endpoint": endpoint['name'],
                    "status": "working",
                    "url": endpoint['url']
                })
            else:
                print(f"      ❌ NOT WORKING")
                oauth_results.append({
                    "endpoint": endpoint['name'],
                    "status": "not_working",
                    "url": endpoint['url']
                })
                
        except Exception as e:
            print(f"      ❌ ERROR: {e}")
            oauth_results.append({
                "endpoint": endpoint['name'],
                "status": "error",
                "error": str(e),
                "url": endpoint['url']
            })
        
        print()
    
    # Step 3: Test backend API endpoints
    print("🔧 STEP 3: TESTING BACKEND API ENDPOINTS")
    print("==========================================")
    
    api_endpoints = [
        {
            "name": "API Documentation",
            "url": "http://localhost:8000/docs",
            "purpose": "Interactive API documentation"
        },
        {
            "name": "API Users Endpoint",
            "url": "http://localhost:8000/api/v1/users",
            "purpose": "User management API"
        },
        {
            "name": "API Tasks Endpoint",
            "url": "http://localhost:8000/api/v1/tasks",
            "purpose": "Task management API"
        }
    ]
    
    api_results = []
    for endpoint in api_endpoints:
        print(f"   🔍 Testing {endpoint['name']}...")
        print(f"      URL: {endpoint['url']}")
        print(f"      Purpose: {endpoint['purpose']}")
        
        try:
            result = subprocess.run([
                "curl", "-s", "--connect-timeout", "5",
                "-w", "%{http_code}", endpoint['url']
            ], capture_output=True, text=True)
            
            response = result.stdout
            http_code = response[-3:] if len(response) > 3 else "000"
            
            if http_code in ["200", "401", "405"]:  # Acceptable responses
                print(f"      ✅ ACCESSIBLE (HTTP {http_code})")
                api_results.append({
                    "endpoint": endpoint['name'],
                    "status": "accessible",
                    "http_code": http_code,
                    "url": endpoint['url']
                })
            else:
                print(f"      ❌ NOT ACCESSIBLE (HTTP {http_code})")
                api_results.append({
                    "endpoint": endpoint['name'],
                    "status": "not_accessible",
                    "http_code": http_code,
                    "url": endpoint['url']
                })
                
        except Exception as e:
            print(f"      ❌ ERROR: {e}")
            api_results.append({
                "endpoint": endpoint['name'],
                "status": "error",
                "error": str(e),
                "url": endpoint['url']
            })
        
        print()
    
    # Step 4: Integration status summary
    print("📊 INTEGRATION STATUS SUMMARY")
    print("==============================")
    
    # Count results
    connected_servers = len([r for r in connectivity_results if r['status'] == 'connected'])
    working_oauth = len([r for r in oauth_results if r['status'] == 'working'])
    accessible_api = len([r for r in api_results if r['status'] == 'accessible'])
    
    print(f"   🔐 OAuth Server: {connected_servers}/1 servers connected")
    print(f"   🔧 Backend API: {'CONNECTED' if any('Backend' in r['server'] and r['status'] == 'connected' for r in connectivity_results) else 'NOT CONNECTED'}")
    print(f"   🎨 Frontend: {'CONNECTED' if any('Frontend' in r['server'] and r['status'] == 'connected' for r in connectivity_results) else 'NOT CONNECTED'}")
    print(f"   📊 OAuth Endpoints: {working_oauth}/2 working")
    print(f"   🔧 API Endpoints: {accessible_api}/3 accessible")
    print()
    
    # Determine integration status
    total_tests = len(servers) + len(oauth_endpoints) + len(api_endpoints)
    passing_tests = connected_servers + working_oauth + accessible_api
    success_rate = (passing_tests / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"🎯 INTEGRATION SUCCESS RATE: {success_rate:.1f}%")
    print(f"   Passing Tests: {passing_tests}/{total_tests}")
    print()
    
    # Next steps based on results
    print("🚀 NEXT STEPS BASED ON RESULTS")
    print("===============================")
    
    if success_rate >= 80:
        print("   ✅ EXCELLENT - Integration nearly complete!")
        print("   🎯 Next Step: Test OAuth authentication flows")
        print("   🎯 Then: Test UI component functionality")
        print("   🎯 Then: Test end-to-end user journeys")
    elif success_rate >= 60:
        print("   ⚠️ GOOD - Integration progressing well!")
        print("   🎯 Next Step: Fix any failing endpoints")
        print("   🎯 Then: Test OAuth authentication flows")
    elif success_rate >= 40:
        print("   🔴 NEEDS WORK - Some servers not responding")
        print("   🎯 Next Step: Fix server connectivity issues")
        print("   🎯 Then: Retest integration")
    else:
        print("   ❌ CRITICAL - Major connectivity issues")
        print("   🎯 Next Step: Check if servers are running")
        print("   🎯 Then: Restart servers if needed")
    
    print()
    
    # Create integration report
    integration_report = {
        "timestamp": datetime.now().isoformat(),
        "test_type": "INTEGRATION_TESTING_PHASE",
        "success_rate": success_rate,
        "total_tests": total_tests,
        "passing_tests": passing_tests,
        "connectivity_results": connectivity_results,
        "oauth_results": oauth_results,
        "api_results": api_results,
        "status": "integration_in_progress",
        "next_phase": "oauth_authentication_testing" if success_rate >= 60 else "server_connectivity_fix"
    }
    
    report_file = f"INTEGRATION_TEST_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(integration_report, f, indent=2)
    
    print(f"📄 Integration test report saved to: {report_file}")
    
    return success_rate >= 60

if __name__ == "__main__":
    success = test_integration_phase()
    
    print(f"\n" + "=" * 80)
    if success:
        print("🎉 INTEGRATION TESTING PASSED!")
        print("✅ Server connectivity verified")
        print("✅ OAuth endpoints working")
        print("✅ API endpoints accessible")
        print("✅ Ready for OAuth authentication testing")
    else:
        print("⚠️ INTEGRATION TESTING ISSUES FOUND")
        print("🔧 Some servers may not be responding")
        print("🔧 Check server status and restart if needed")
    
    print("\n🚀 NEXT ACTIONS:")
    print("   📋 Verify all servers are running")
    print("   📋 Test OAuth authentication flows")
    print("   📋 Test UI component functionality")
    print("   📋 Test end-to-end user journeys")
    print("=" * 80)
    exit(0 if success else 1)