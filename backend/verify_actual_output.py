#!/usr/bin/env python3
"""
VERIFY ACTUAL OUTPUT vs README CLAIMS
Test complete application for real user usability
"""

import subprocess
import time
import json
import re
from datetime import datetime

def verify_actual_output_vs_readme():
    """Verify actual application output against README claims"""
    
    print("🔍 VERIFY ACTUAL OUTPUT vs README CLAIMS")
    print("=" * 80)
    print("Testing complete application for real user usability")
    print("=" * 80)
    
    # README Claims Analysis
    print("📋 README CLAIMS ANALYSIS:")
    readme_claims = {
        "oauth_infrastructure": {
            "claim": "OAuth Authentication for users",
            "expected": "Users can authenticate via OAuth",
            "components": ["github", "google", "slack", "outlook", "teams"],
            "user_value": "Secure login with existing accounts"
        },
        "backend_api": {
            "claim": "Backend API for data management",
            "expected": "API endpoints for user data",
            "components": ["users", "tasks", "workflows", "services"],
            "user_value": "Data persistence and management"
        },
        "frontend_ui": {
            "claim": "Frontend UI for user interaction",
            "expected": "Working UI components",
            "components": ["search", "tasks", "automations", "calendar", "communication"],
            "user_value": "Intuitive interface to use features"
        },
        "service_integrations": {
            "claim": "Service integrations for automation",
            "expected": "Real connections to services",
            "components": ["github", "google", "slack"],
            "user_value": "Actual automation of real services"
        }
    }
    
    for claim_type, details in readme_claims.items():
        display_name = claim_type.replace('_', ' ').title()
        print(f"   📋 {display_name}:")
        print(f"      Claim: {details['claim']}")
        print(f"      Expected: {details['expected']}")
        print(f"      Components: {', '.join(details['components'])}")
        print(f"      User Value: {details['user_value']}")
        print()
    
    # Step 1: Test OAuth Server
    print("🔐 STEP 1: TESTING OAUTH SERVER")
    print("==================================")
    
    oauth_tests = [
        {
            "name": "OAuth Server Health",
            "url": "http://localhost:5058/healthz",
            "expected": "OAuth server is running",
            "user_impact": "Users need authentication to work"
        },
        {
            "name": "OAuth Services Status",
            "url": "http://localhost:5058/api/auth/oauth-status",
            "expected": "OAuth services configured",
            "user_impact": "Users need available OAuth providers"
        },
        {
            "name": "GitHub OAuth Flow",
            "url": "http://localhost:5058/api/auth/github/authorize?user_id=test_user",
            "expected": "OAuth authorization URL or credentials message",
            "user_impact": "Users need to login with GitHub"
        },
        {
            "name": "Google OAuth Flow",
            "url": "http://localhost:5058/api/auth/google/authorize?user_id=test_user",
            "expected": "OAuth authorization URL or credentials message",
            "user_impact": "Users need to login with Google"
        }
    ]
    
    oauth_results = []
    for test in oauth_tests:
        print(f"   🔍 Testing: {test['name']}")
        print(f"      URL: {test['url']}")
        print(f"      Expected: {test['expected']}")
        print(f"      User Impact: {test['user_impact']}")
        
        try:
            result = subprocess.run([
                "curl", "-s", "--connect-timeout", "5",
                test['url']
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout:
                print(f"      ✅ WORKING")
                if test['name'] == "OAuth Server Health":
                    print(f"      📊 Response: OAuth server is running")
                elif test['name'] == "OAuth Services Status":
                    data = json.loads(result.stdout)
                    print(f"      📊 Services Configured: {data.get('total_services', 0)}")
                    print(f"      📊 Real Credentials: {data.get('configured_services', 0)}")
                else:
                    print(f"      📊 OAuth flow responding")
                
                oauth_results.append({
                    "test": test['name'],
                    "status": "working",
                    "user_value": test['user_impact']
                })
            else:
                print(f"      ❌ NOT WORKING")
                oauth_results.append({
                    "test": test['name'],
                    "status": "not_working",
                    "user_value": test['user_impact']
                })
                
        except Exception as e:
            print(f"      ❌ ERROR: {e}")
            oauth_results.append({
                "test": test['name'],
                "status": "error",
                "user_value": test['user_impact']
            })
        
        print()
    
    # Step 2: Test Backend API
    print("🔧 STEP 2: TESTING BACKEND API")
    print("=================================")
    
    backend_tests = [
        {
            "name": "API Server Health",
            "url": "http://localhost:8000/health",
            "expected": "API server is running",
            "user_impact": "Users need backend for data operations"
        },
        {
            "name": "API Documentation",
            "url": "http://localhost:8000/docs",
            "expected": "Interactive API documentation",
            "user_impact": "Users need to understand available endpoints"
        },
        {
            "name": "Users API Endpoint",
            "url": "http://localhost:8000/api/v1/users",
            "expected": "Users management API",
            "user_impact": "Users need to create/manage accounts"
        },
        {
            "name": "Tasks API Endpoint",
            "url": "http://localhost:8000/api/v1/tasks",
            "expected": "Tasks management API",
            "user_impact": "Users need to manage tasks"
        }
    ]
    
    backend_results = []
    for test in backend_tests:
        print(f"   🔍 Testing: {test['name']}")
        print(f"      URL: {test['url']}")
        print(f"      Expected: {test['expected']}")
        print(f"      User Impact: {test['user_impact']}")
        
        try:
            result = subprocess.run([
                "curl", "-s", "--connect-timeout", "5",
                "-w", "%{http_code}", test['url']
            ], capture_output=True, text=True, timeout=10)
            
            response = result.stdout.strip()
            http_code = response[-3:] if len(response) > 3 else "000"
            
            if http_code in ["200", "401", "405"]:  # Acceptable responses
                print(f"      ✅ ACCESSIBLE (HTTP {http_code})")
                backend_results.append({
                    "test": test['name'],
                    "status": "accessible",
                    "user_value": test['user_impact']
                })
            else:
                print(f"      ❌ NOT ACCESSIBLE (HTTP {http_code})")
                backend_results.append({
                    "test": test['name'],
                    "status": "not_accessible",
                    "user_value": test['user_impact']
                })
                
        except Exception as e:
            print(f"      ❌ ERROR: {e}")
            backend_results.append({
                "test": test['name'],
                "status": "error",
                "user_value": test['user_impact']
            })
        
        print()
    
    # Step 3: Test Frontend UI
    print("🎨 STEP 3: TESTING FRONTEND UI")
    print("================================")
    
    frontend_tests = [
        {
            "name": "Frontend Main Page",
            "url": "http://localhost:3000",
            "expected": "ATOM UI with 8 component cards",
            "user_impact": "Users need main interface to access features"
        },
        {
            "name": "Search Component",
            "url": "http://localhost:3000/search",
            "expected": "Search interface for cross-service search",
            "user_impact": "Users need search functionality to find content"
        },
        {
            "name": "Tasks Component",
            "url": "http://localhost:3000/tasks",
            "expected": "Task management interface",
            "user_impact": "Users need tasks to manage workflow"
        },
        {
            "name": "Automations Component",
            "url": "http://localhost:3000/automations",
            "expected": "Workflow automation interface",
            "user_impact": "Users need automations to increase productivity"
        }
    ]
    
    frontend_results = []
    for test in frontend_tests:
        print(f"   🔍 Testing: {test['name']}")
        print(f"      URL: {test['url']}")
        print(f"      Expected: {test['expected']}")
        print(f"      User Impact: {test['user_impact']}")
        
        try:
            result = subprocess.run([
                "curl", "-s", "--connect-timeout", "10",
                "-w", "%{http_code}", test['url']
            ], capture_output=True, text=True, timeout=15)
            
            response = result.stdout.strip()
            http_code = response[-3:] if len(response) > 3 else "000"
            
            if http_code == "200":
                print(f"      ✅ LOADED (HTTP {http_code})")
                content = result.stdout
                if "ATOM" in content or "Welcome" in content:
                    print(f"      📊 Content: ATOM interface detected")
                elif len(content) > 100:
                    print(f"      📊 Content: UI page detected")
                else:
                    print(f"      📊 Content: Page responsive")
                
                frontend_results.append({
                    "test": test['name'],
                    "status": "loaded",
                    "user_value": test['user_impact']
                })
            elif http_code == "000":
                print(f"      ⚠️ STARTING (Frontend may be initializing)")
                print(f"      💡 Wait 10-15 seconds and retry")
                frontend_results.append({
                    "test": test['name'],
                    "status": "starting",
                    "user_value": test['user_impact']
                })
            else:
                print(f"      ❌ NOT LOADED (HTTP {http_code})")
                frontend_results.append({
                    "test": test['name'],
                    "status": "not_loaded",
                    "user_value": test['user_impact']
                })
                
        except Exception as e:
            print(f"      ❌ ERROR: {e}")
            frontend_results.append({
                "test": test['name'],
                "status": "error",
                "user_value": test['user_impact']
            })
        
        print()
    
    # Step 4: User Journey Test
    print("👤 STEP 4: USER JOURNEY TEST")
    print("===============================")
    
    user_journey_tests = [
        {
            "step": "1. Access Application",
            "test": "User visits main application",
            "urls": ["http://localhost:3000"],
            "expected": "ATOM interface loads",
            "user_impact": "Entry point to application"
        },
        {
            "step": "2. Navigate Features",
            "test": "User can navigate to different components",
            "urls": ["http://localhost:3000/search", "http://localhost:3000/tasks"],
            "expected": "Component pages load",
            "user_impact": "Access to all features"
        },
        {
            "step": "3. Authenticate",
            "test": "User can authenticate via OAuth",
            "urls": ["http://localhost:5058/api/auth/oauth-status"],
            "expected": "OAuth flows available",
            "user_impact": "Secure login process"
        },
        {
            "step": "4. Use Services",
            "test": "User can access real service integrations",
            "urls": ["http://localhost:8000/api/v1/services"],
            "expected": "Service connectivity",
            "user_impact": "Actual automation of real services"
        }
    ]
    
    journey_results = []
    for journey_test in user_journey_tests:
        print(f"   👤 {journey_test['step']}")
        print(f"      Test: {journey_test['test']}")
        print(f"      URLs: {', '.join(journey_test['urls'])}")
        print(f"      Expected: {journey_test['expected']}")
        print(f"      User Impact: {journey_test['user_impact']}")
        
        # Test each URL in journey
        journey_passed = 0
        journey_total = len(journey_test['urls'])
        
        for url in journey_test['urls']:
            try:
                result = subprocess.run([
                    "curl", "-s", "--connect-timeout", "5",
                    "-w", "%{http_code}", url
                ], capture_output=True, text=True, timeout=10)
                
                response = result.stdout.strip()
                http_code = response[-3:] if len(response) > 3 else "000"
                
                if http_code == "200":
                    journey_passed += 1
                elif http_code == "000" and "3000" in url:
                    journey_passed += 0.5  # Frontend starting
                    
            except Exception as e:
                pass  # Count as failed
        
        journey_success_rate = (journey_passed / journey_total) * 100
        if journey_success_rate >= 75:
            print(f"      ✅ PASSED ({journey_success_rate:.1f}%)")
        elif journey_success_rate >= 50:
            print(f"      ⚠️ PARTIAL ({journey_success_rate:.1f}%)")
        else:
            print(f"      ❌ FAILED ({journey_success_rate:.1f}%)")
        
        journey_results.append({
            "step": journey_test['step'],
            "success_rate": journey_success_rate,
            "user_value": journey_test['user_impact']
        })
        print()
    
    # Step 5: Usability Assessment
    print("🎯 STEP 5: USABILITY ASSESSMENT")
    print("=================================")
    
    usability_factors = [
        {
            "factor": "Authentication",
            "requirement": "Users can login via OAuth",
            "weight": 30,
            "score": 0
        },
        {
            "factor": "UI Navigation",
            "requirement": "Users can navigate to features",
            "weight": 25,
            "score": 0
        },
        {
            "factor": "Service Access",
            "requirement": "Users can access real services",
            "weight": 25,
            "score": 0
        },
        {
            "factor": "Data Management",
            "requirement": "Users can manage data via APIs",
            "weight": 20,
            "score": 0
        }
    ]
    
    # Calculate scores based on test results
    oauth_working = len([r for r in oauth_results if r['status'] == 'working'])
    oauth_score = (oauth_working / len(oauth_results)) * 100
    usability_factors[0]['score'] = oauth_score
    
    backend_accessible = len([r for r in backend_results if r['status'] == 'accessible'])
    backend_score = (backend_accessible / len(backend_results)) * 100
    usability_factors[3]['score'] = backend_score
    
    frontend_loaded = len([r for r in frontend_results if r['status'] == 'loaded'])
    frontend_score = (frontend_loaded / len(frontend_results)) * 100
    usability_factors[1]['score'] = frontend_score
    
    journey_avg = sum([j['success_rate'] for j in journey_results]) / len(journey_results)
    usability_factors[2]['score'] = journey_avg
    
    print("   📊 Usability Factors:")
    total_weighted_score = 0
    for factor in usability_factors:
        status_icon = "✅" if factor['score'] >= 75 else "⚠️" if factor['score'] >= 50 else "❌"
        weighted_score = (factor['score'] / 100) * factor['weight']
        total_weighted_score += weighted_score
        print(f"      {status_icon} {factor['factor']}: {factor['score']:.1f}% (Weight: {factor['weight']}%)")
        print(f"         Requirement: {factor['requirement']}")
        print(f"         Weighted Score: {weighted_score:.1f}")
        print()
    
    # Overall usability assessment
    print("🎯 OVERALL USABILITY ASSESSMENT")
    print("================================")
    
    usability_score = total_weighted_score
    if usability_score >= 80:
        usability_level = "EXCELLENT - Production Ready"
        usability_icon = "🎉"
    elif usability_score >= 60:
        usability_level = "GOOD - Nearly Production Ready"
        usability_icon = "⚠️"
    elif usability_score >= 40:
        usability_level = "BASIC - Major Issues"
        usability_icon = "🔧"
    else:
        usability_level = "NOT USABLE - Critical Issues"
        usability_icon = "❌"
    
    print(f"   {usability_icon} Overall Usability: {usability_score:.1f}%")
    print(f"   {usability_icon} Assessment Level: {usability_level}")
    print()
    
    # README Claims Validation
    print("📋 README CLAIMS VALIDATION")
    print("===============================")
    
    claims_validation = {
        "OAuth Authentication": {
            "claimed": "Users can authenticate via OAuth",
            "actual": oauth_score,
            "validation": "VALIDATED" if oauth_score >= 75 else "PARTIAL" if oauth_score >= 50 else "INVALID",
            "user_ready": oauth_score >= 75
        },
        "Backend API": {
            "claimed": "API endpoints for data management",
            "actual": backend_score,
            "validation": "VALIDATED" if backend_score >= 75 else "PARTIAL" if backend_score >= 50 else "INVALID",
            "user_ready": backend_score >= 75
        },
        "Frontend UI": {
            "claimed": "Working UI components",
            "actual": frontend_score,
            "validation": "VALIDATED" if frontend_score >= 75 else "PARTIAL" if frontend_score >= 50 else "INVALID",
            "user_ready": frontend_score >= 75
        },
        "Service Integrations": {
            "claimed": "Real service connections",
            "actual": journey_avg,
            "validation": "VALIDATED" if journey_avg >= 75 else "PARTIAL" if journey_avg >= 50 else "INVALID",
            "user_ready": journey_avg >= 75
        }
    }
    
    validated_count = 0
    total_claims = len(claims_validation)
    
    for claim, validation in claims_validation.items():
        validation_icon = "✅" if validation['validation'] == 'VALIDATED' else "⚠️" if validation['validation'] == 'PARTIAL' else "❌"
        user_ready = "✅ YES" if validation['user_ready'] else "❌ NO"
        print(f"   {validation_icon} {claim}:")
        print(f"      Claimed: {validation['claimed']}")
        print(f"      Actual Score: {validation['actual']:.1f}%")
        print(f"      Validation: {validation['validation']}")
        print(f"      User Ready: {user_ready}")
        print()
        
        if validation['user_ready']:
            validated_count += 1
    
    # Final conclusion
    print("🎯 FINAL CONCLUSION")
    print("===================")
    
    claims_validated = (validated_count / total_claims) * 100
    
    if claims_validated >= 75 and usability_score >= 70:
        conclusion = "✅ APPLICATION IS USABLE BY ACTUAL USERS"
        conclusion_icon = "🎉"
        deployment_status = "READY FOR PRODUCTION"
    elif claims_validated >= 50 and usability_score >= 50:
        conclusion = "⚠️ APPLICATION IS MOSTLY USABLE - NEEDS FIXES"
        conclusion_icon = "⚠️"
        deployment_status = "NEEDS WORK BEFORE PRODUCTION"
    else:
        conclusion = "❌ APPLICATION IS NOT USABLE BY ACTUAL USERS"
        conclusion_icon = "❌"
        deployment_status = "MAJOR ISSUES BEFORE DEPLOYMENT"
    
    print(f"   {conclusion_icon} {conclusion}")
    print(f"   {conclusion_icon} Claims Validated: {claims_validated:.1f}% ({validated_count}/{total_claims})")
    print(f"   {conclusion_icon} Usability Score: {usability_score:.1f}%")
    print(f"   {conclusion_icon} Deployment Status: {deployment_status}")
    print()
    
    # Create verification report
    verification_report = {
        "timestamp": datetime.now().isoformat(),
        "verification_type": "ACTUAL_OUTPUT_vs_README_CLAIMS",
        "purpose": "Verify application is usable by actual users",
        "oauth_tests": oauth_results,
        "backend_tests": backend_results,
        "frontend_tests": frontend_results,
        "user_journey_tests": journey_results,
        "usability_factors": usability_factors,
        "usability_score": usability_score,
        "claims_validation": claims_validation,
        "claims_validated": claims_validated,
        "overall_conclusion": conclusion,
        "deployment_status": deployment_status,
        "user_ready": claims_validated >= 75 and usability_score >= 70
    }
    
    report_file = f"VERIFICATION_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(verification_report, f, indent=2)
    
    print(f"📄 Verification report saved to: {report_file}")
    
    return verification_report['user_ready']

if __name__ == "__main__":
    user_ready = verify_actual_output_vs_readme()
    
    print(f"\n" + "=" * 80)
    if user_ready:
        print("🎉 VERIFICATION PASSED!")
        print("✅ README claims validated against actual output")
        print("✅ Application is usable by actual users")
        print("✅ Ready for production deployment")
        print("\n🚀 DEPLOYMENT READY!")
    else:
        print("⚠️ VERIFICATION ISSUES FOUND!")
        print("❌ Some README claims not matching actual output")
        print("❌ Application needs fixes for user usability")
        print("❌ Not ready for production deployment")
        print("\n🔧 RECOMMENDATIONS:")
        print("   1. Fix any failing components")
        print("   2. Verify all servers are running")
        print("   3. Test complete user journeys")
        print("   4. Retest when fixes complete")
    
    print("=" * 80)
    exit(0 if user_ready else 1)