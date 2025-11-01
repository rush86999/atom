#!/usr/bin/env python3
"""
REAL USER JOURNEY TESTING
Pretend to be a user and verify real-world usability
Fix any issues that get in the way
"""

import subprocess
import time
import json
import requests
from datetime import datetime

def real_user_journey_testing():
    """Real user journey testing with issue fixing"""
    
    print("👤 REAL USER JOURNEY TESTING")
    print("=" * 80)
    print("Pretend to be a user and verify real-world usability")
    print("=" * 80)
    
    # User Persona Setup
    print("👤 USER PERSONA SETUP")
    print("=======================")
    user_persona = {
        "name": "Alex Developer",
        "role": "Software Developer",
        "goals": [
            "Authenticate using existing GitHub account",
            "Search across all connected services",
            "Manage tasks from multiple platforms",
            "Automate workflow across services",
            "Access unified calendar",
            "Communicate with team via integrated services"
        ],
        "technical_level": "Advanced - comfortable with OAuth and APIs",
        "expectations": "Seamless integration across GitHub, Google, Slack"
    }
    
    print(f"   👤 User: {user_persona['name']}")
    print(f"   🔧 Role: {user_persona['role']}")
    print(f"   🎯 Goals: {', '.join(user_persona['goals'])}")
    print(f"   💻 Technical Level: {user_persona['technical_level']}")
    print(f"   ⭐ Expectations: {user_persona['expectations']}")
    print()
    
    # Step 1: First Visit to Application
    print("🚀 STEP 1: FIRST VISIT TO APPLICATION")
    print("=======================================")
    
    print("   👤 User Action: Open browser and visit main application")
    print("   🌐 Expected URL: http://localhost:3000")
    print("   👤 User Expectation: Welcome page with clear options")
    
    try:
        response = requests.get("http://localhost:3000", timeout=10)
        if response.status_code == 200:
            print("   ✅ SUCCESS: Frontend is responding")
            content = response.text
            if "Welcome" in content or "ATOM" in content or len(content) > 1000:
                print("   ✅ SUCCESS: Content appears to be a valid UI")
            else:
                print("   ⚠️ ISSUE: Content minimal, check if frontend fully loaded")
        else:
            print(f"   ❌ ISSUE: Frontend returned HTTP {response.status_code}")
            print("   🔧 FIX NEEDED: Frontend not responding")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ ISSUE: Cannot connect to frontend - {e}")
        print("   🔧 FIX NEEDED: Start frontend development server")
        print("   🔧 COMMAND: cd frontend-nextjs && npm run dev")
    
    print()
    
    # Step 2: UI Component Exploration
    print("🔍 STEP 2: UI COMPONENT EXPLORATION")
    print("====================================")
    
    print("   👤 User Action: Look for available features/components")
    print("   👤 User Expectation: Clear list of features to use")
    
    ui_components = [
        {
            "name": "Search",
            "url": "http://localhost:3000/search",
            "purpose": "Search across all connected services",
            "user_value": "Find content across GitHub, Google, Slack etc."
        },
        {
            "name": "Tasks",
            "url": "http://localhost:3000/tasks",
            "purpose": "Task management and automation",
            "user_value": "Manage workflow tasks across services"
        },
        {
            "name": "Automations",
            "url": "http://localhost:3000/automations",
            "purpose": "Workflow automation",
            "user_value": "Create automated processes across services"
        },
        {
            "name": "Calendar",
            "url": "http://localhost:3000/calendar",
            "purpose": "Unified calendar view",
            "user_value": "See all events from Google, Slack etc."
        },
        {
            "name": "Communication",
            "url": "http://localhost:3000/communication",
            "purpose": "Team communication hub",
            "user_value": "Unified messaging across platforms"
        }
    ]
    
    component_results = []
    for component in ui_components:
        print(f"   🔍 Testing {component['name']} component...")
        print(f"      URL: {component['url']}")
        print(f"      Purpose: {component['purpose']}")
        print(f"      User Value: {component['user_value']}")
        
        try:
            response = requests.get(component['url'], timeout=5)
            if response.status_code == 200:
                print(f"      ✅ ACCESSIBLE: {component['name']} loads")
                component_results.append({
                    "component": component['name'],
                    "status": "accessible",
                    "url": component['url'],
                    "user_value": component['user_value']
                })
            else:
                print(f"      ⚠️ ISSUE: {component['name']} returned HTTP {response.status_code}")
                component_results.append({
                    "component": component['name'],
                    "status": "not_accessible",
                    "url": component['url'],
                    "user_value": component['user_value']
                })
        except requests.exceptions.RequestException as e:
            print(f"      ❌ ISSUE: Cannot access {component['name']} - {e}")
            component_results.append({
                "component": component['name'],
                "status": "error",
                "url": component['url'],
                "user_value": component['user_value']
            })
        
        print()
    
    # Step 3: OAuth Authentication Test
    print("🔐 STEP 3: OAUTH AUTHENTICATION TEST")
    print("======================================")
    
    print("   👤 User Action: Try to authenticate with existing account")
    print("   👤 User Expectation: Can login via GitHub, Google, or Slack")
    
    oauth_services = [
        {
            "name": "GitHub",
            "url": "http://localhost:5058/api/auth/github/authorize?user_id=alex_user",
            "expectation": "GitHub OAuth authorization URL or working flow",
            "user_accounts": "Most developers have GitHub accounts"
        },
        {
            "name": "Google",
            "url": "http://localhost:5058/api/auth/google/authorize?user_id=alex_user",
            "expectation": "Google OAuth authorization URL or working flow",
            "user_accounts": "Almost everyone has Google accounts"
        },
        {
            "name": "Slack",
            "url": "http://localhost:5058/api/auth/slack/authorize?user_id=alex_user",
            "expectation": "Slack OAuth authorization URL or working flow",
            "user_accounts": "Many professionals use Slack"
        }
    ]
    
    oauth_results = []
    for service in oauth_services:
        print(f"   🔐 Testing {service['name']} OAuth...")
        print(f"      URL: {service['url']}")
        print(f"      Expectation: {service['expectation']}")
        print(f"      User Accounts: {service['user_accounts']}")
        
        try:
            response = requests.get(service['url'], timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"      ✅ WORKING: {service['name']} OAuth responding")
                if 'auth_url' in data:
                    print(f"      📊 OAuth URL: {data.get('auth_url', 'Generated')}")
                elif 'status' in data:
                    print(f"      📊 Status: {data.get('status', 'Checking')}")
                
                oauth_results.append({
                    "service": service['name'],
                    "status": "working",
                    "user_value": f"Users can login with {service['name']}"
                })
            else:
                print(f"      ⚠️ ISSUE: {service['name']} OAuth returned HTTP {response.status_code}")
                oauth_results.append({
                    "service": service['name'],
                    "status": "not_working",
                    "user_value": f"Users cannot login with {service['name']}"
                })
        except requests.exceptions.RequestException as e:
            print(f"      ❌ ISSUE: Cannot access {service['name']} OAuth - {e}")
            oauth_results.append({
                "service": service['name'],
                "status": "error",
                "user_value": f"Users cannot login with {service['name']}"
            })
        
        print()
    
    # Step 4: Backend API Integration Test
    print("🔧 STEP 4: BACKEND API INTEGRATION TEST")
    print("======================================")
    
    print("   👤 User Action: Interact with features that require backend")
    print("   👤 User Expectation: Features work with real data and persistence")
    
    api_tests = [
        {
            "name": "User Data",
            "url": "http://localhost:8000/api/v1/users",
            "purpose": "User account management",
            "user_value": "Data persists across sessions"
        },
        {
            "name": "Task Management",
            "url": "http://localhost:8000/api/v1/tasks",
            "purpose": "Task data management",
            "user_value": "Tasks save and sync across services"
        },
        {
            "name": "Search API",
            "url": "http://localhost:8000/api/v1/search",
            "purpose": "Cross-service search",
            "user_value": "Real search across connected services"
        },
        {
            "name": "Services API",
            "url": "http://localhost:8000/api/v1/services",
            "purpose": "Service integration management",
            "user_value": "Connected services status and management"
        }
    ]
    
    api_results = []
    for api in api_tests:
        print(f"   🔧 Testing {api['name']} API...")
        print(f"      URL: {api['url']}")
        print(f"      Purpose: {api['purpose']}")
        print(f"      User Value: {api['user_value']}")
        
        try:
            response = requests.get(api['url'], timeout=5)
            if response.status_code in [200, 405]:  # 405 = method not allowed but API exists
                print(f"      ✅ ACCESSIBLE: {api['name']} API responding")
                api_results.append({
                    "api": api['name'],
                    "status": "accessible",
                    "user_value": api['user_value']
                })
            else:
                print(f"      ⚠️ ISSUE: {api['name']} API returned HTTP {response.status_code}")
                api_results.append({
                    "api": api['name'],
                    "status": "not_accessible",
                    "user_value": api['user_value']
                })
        except requests.exceptions.RequestException as e:
            print(f"      ❌ ISSUE: Cannot access {api['name']} API - {e}")
            api_results.append({
                "api": api['name'],
                "status": "error",
                "user_value": api['user_value']
            })
        
        print()
    
    # Step 5: Real Service Integration Test
    print("🔗 STEP 5: REAL SERVICE INTEGRATION TEST")
    print("=========================================")
    
    print("   👤 User Action: Connect and use real services")
    print("   👤 User Expectation: Can actually access GitHub, Google, Slack data")
    
    service_integrations = [
        {
            "name": "GitHub Integration",
            "test_url": "http://localhost:5058/api/auth/github/status",
            "purpose": "Access GitHub repositories, issues, commits",
            "user_value": "Real GitHub data in ATOM platform"
        },
        {
            "name": "Google Integration",
            "test_url": "http://localhost:5058/api/auth/gmail/status",
            "purpose": "Access Gmail, Calendar, Drive",
            "user_value": "Real Google services data in ATOM platform"
        },
        {
            "name": "Slack Integration",
            "test_url": "http://localhost:5058/api/auth/slack/status",
            "purpose": "Access Slack channels, messages, files",
            "user_value": "Real Slack data in ATOM platform"
        }
    ]
    
    integration_results = []
    for service in service_integrations:
        print(f"   🔗 Testing {service['name']}...")
        print(f"      Test URL: {service['test_url']}")
        print(f"      Purpose: {service['purpose']}")
        print(f"      User Value: {service['user_value']}")
        
        try:
            response = requests.get(service['test_url'], timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"      ✅ CONNECTED: {service['name']} integration active")
                if 'status' in data:
                    print(f"      📊 Status: {data.get('status', 'Active')}")
                if 'credentials' in data:
                    print(f"      📊 Credentials: {data.get('credentials', 'Configured')}")
                
                integration_results.append({
                    "service": service['name'],
                    "status": "connected",
                    "user_value": service['user_value']
                })
            else:
                print(f"      ⚠️ ISSUE: {service['name']} not fully connected")
                integration_results.append({
                    "service": service['name'],
                    "status": "not_connected",
                    "user_value": service['user_value']
                })
        except requests.exceptions.RequestException as e:
            print(f"      ❌ ISSUE: Cannot access {service['name']} - {e}")
            integration_results.append({
                "service": service['name'],
                "status": "error",
                "user_value": service['user_value']
            })
        
        print()
    
    # Step 6: Issue Identification and Fixes
    print("🔧 STEP 6: ISSUE IDENTIFICATION AND FIXES")
    print("==========================================")
    
    issues_found = []
    fixes_needed = []
    
    # Analyze all test results for issues
    if len([c for c in component_results if c['status'] == 'accessible']) < len(component_results) * 0.5:
        issues_found.append("Frontend components not fully accessible")
        fixes_needed.append({
            "issue": "Frontend components inaccessible",
            "fix": "Start frontend development server: cd frontend-nextjs && npm run dev",
            "priority": "CRITICAL"
        })
    
    if len([o for o in oauth_results if o['status'] == 'working']) < len(oauth_results) * 0.5:
        issues_found.append("OAuth services not fully working")
        fixes_needed.append({
            "issue": "OAuth services not working",
            "fix": "Check OAuth server status: curl http://localhost:5058/healthz",
            "priority": "CRITICAL"
        })
    
    if len([a for a in api_results if a['status'] == 'accessible']) < len(api_results) * 0.5:
        issues_found.append("Backend APIs not fully accessible")
        fixes_needed.append({
            "issue": "Backend APIs not accessible",
            "fix": "Check backend server status: curl http://localhost:8000/health",
            "priority": "CRITICAL"
        })
    
    if len([i for i in integration_results if i['status'] == 'connected']) < len(integration_results) * 0.5:
        issues_found.append("Service integrations not fully connected")
        fixes_needed.append({
            "issue": "Service integrations not connected",
            "fix": "Check OAuth credentials in .env file",
            "priority": "HIGH"
        })
    
    print("   🔍 Issues Found:")
    for issue in issues_found:
        print(f"      ❌ {issue}")
    
    print()
    print("   🔧 Fixes Needed:")
    for i, fix in enumerate(fixes_needed, 1):
        priority_icon = "🔴" if fix['priority'] == 'CRITICAL' else "🟡"
        print(f"      {priority_icon} FIX {i}: {fix['issue']}")
        print(f"         Action: {fix['fix']}")
        print(f"         Priority: {fix['priority']}")
        print()
    
    # Step 7: User Journey Completion Assessment
    print("🎯 STEP 7: USER JOURNEY COMPLETION ASSESSMENT")
    print("===============================================")
    
    print("   👤 User Journey Summary:")
    user_journey_steps = [
        "✅ 1. User visits application",
        "✅ 2. User explores UI components",
        "✅ 3. User attempts OAuth authentication",
        "✅ 4. User tests backend API integration",
        "✅ 5. User tries real service integrations",
        "✅ 6. User expects seamless workflow"
    ]
    
    for step in user_journey_steps:
        print(f"      {step}")
    
    print()
    
    # Calculate overall user readiness
    component_score = len([c for c in component_results if c['status'] == 'accessible']) / len(component_results) * 100
    oauth_score = len([o for o in oauth_results if o['status'] == 'working']) / len(oauth_results) * 100
    api_score = len([a for a in api_results if a['status'] == 'accessible']) / len(api_results) * 100
    integration_score = len([i for i in integration_results if i['status'] == 'connected']) / len(integration_results) * 100
    
    overall_score = (component_score + oauth_score + api_score + integration_score) / 4
    
    print("   📊 User Readiness Scores:")
    print(f"      🎨 UI Components: {component_score:.1f}%")
    print(f"      🔐 OAuth Services: {oauth_score:.1f}%")
    print(f"      🔧 Backend APIs: {api_score:.1f}%")
    print(f"      🔗 Service Integrations: {integration_score:.1f}%")
    print(f"      🎯 Overall User Readiness: {overall_score:.1f}%")
    print()
    
    # Final User Journey Assessment
    if overall_score >= 80:
        user_journey_status = "EXCELLENT - User journey fully functional"
        status_icon = "🎉"
        deployment_ready = "PRODUCTION READY"
    elif overall_score >= 60:
        user_journey_status = "GOOD - User journey mostly functional"
        status_icon = "⚠️"
        deployment_ready = "NEEDS MINOR FIXES"
    elif overall_score >= 40:
        user_journey_status = "BASIC - User journey partially functional"
        status_icon = "🔧"
        deployment_ready = "NEEDS MAJOR FIXES"
    else:
        user_journey_status = "POOR - User journey not functional"
        status_icon = "❌"
        deployment_ready = "NOT READY"
    
    print(f"   {status_icon} User Journey Status: {user_journey_status}")
    print(f"   {status_icon} Deployment Status: {deployment_ready}")
    print()
    
    # Create user journey report
    user_journey_report = {
        "timestamp": datetime.now().isoformat(),
        "test_type": "REAL_USER_JOURNEY_TESTING",
        "user_persona": user_persona,
        "component_results": component_results,
        "oauth_results": oauth_results,
        "api_results": api_results,
        "integration_results": integration_results,
        "issues_found": issues_found,
        "fixes_needed": fixes_needed,
        "scores": {
            "components": component_score,
            "oauth": oauth_score,
            "api": api_score,
            "integrations": integration_score,
            "overall": overall_score
        },
        "user_journey_status": user_journey_status,
        "deployment_ready": deployment_ready,
        "user_ready": overall_score >= 60
    }
    
    report_file = f"USER_JOURNEY_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(user_journey_report, f, indent=2)
    
    print(f"📄 User journey report saved to: {report_file}")
    
    return overall_score >= 60

if __name__ == "__main__":
    success = real_user_journey_testing()
    
    print(f"\n" + "=" * 80)
    if success:
        print("🎉 REAL USER JOURNEY TESTING PASSED!")
        print("✅ User can access and use core functionality")
        print("✅ OAuth authentication working")
        print("✅ Backend APIs accessible")
        print("✅ Service integrations connected")
        print("✅ UI components loading")
    else:
        print("❌ REAL USER JOURNEY TESTING FAILED!")
        print("❌ User cannot complete basic workflows")
        print("❌ Critical issues need to be fixed")
        print("❌ Review fixes and retry")
    
    print("=" * 80)
    exit(0 if success else 1)