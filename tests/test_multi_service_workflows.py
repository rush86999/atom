#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Multi-Service Workflow Coordination
Tests complex workflows that span multiple services
"""

import requests
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Backend URL
BACKEND_URL = "http://localhost:5058"

def test_workflow_generation(user_input):
    """Test workflow generation with multi-service coordination"""
    try:
        url = BACKEND_URL + "/api/workflow-automation/generate"
        payload = {
            "user_input": user_input,
            "user_id": "test_user"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "workflow": data.get("workflow", {}),
                "services_used": data.get("workflow", {}).get("services", []),
                "steps_count": len(data.get("workflow", {}).get("steps", [])),
                "message": data.get("message", "Workflow generated successfully")
            }
        else:
            return {
                "success": False,
                "error": "HTTP {0}: {1}".format(response.status_code, response.text),
                "services_used": [],
                "steps_count": 0
            }
            
    except Exception as e:
        logger.error("Error testing workflow generation: {0}".format(str(e)))
        return {
            "success": False,
            "error": "Request failed: {0}".format(str(e)),
            "services_used": [],
            "steps_count": 0
        }

def test_complex_workflow_scenarios():
    """Test various complex workflow scenarios"""
    test_scenarios = [
        {
            "name": "Email to Task Workflow",
            "input": "When I receive an important email, create a task in Asana and send a Slack notification",
            "expected_services": ["gmail", "asana", "slack"]
        },
        {
            "name": "Meeting to Documentation",
            "input": "After a meeting, create notes in Notion and schedule follow-up tasks in Trello",
            "expected_services": ["notion", "trello"]
        },
        {
            "name": "File Processing Workflow", 
            "input": "When a file is uploaded to Dropbox, process it and save to Google Drive",
            "expected_services": ["dropbox", "google_drive"]
        },
        {
            "name": "Multi-Platform Communication",
            "input": "Send a message to both Slack and Microsoft Teams when a task is completed",
            "expected_services": ["slack", "microsoft_teams"]
        },
        {
            "name": "Development Workflow",
            "input": "When a GitHub issue is created, create a corresponding task in Jira",
            "expected_services": ["github", "jira"]
        }
    ]
    
    results = []
    successful_tests = 0
    
    for scenario in test_scenarios:
        logger.info("Testing scenario: {0}".format(scenario["name"]))
        
        result = test_workflow_generation(scenario["input"])
        scenario_result = {
            "scenario_name": scenario["name"],
            "user_input": scenario["input"],
            "expected_services": scenario["expected_services"],
            "actual_services": result.get("services_used", []),
            "steps_count": result.get("steps_count", 0),
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "error": result.get("error", "")
        }
        
        # Check if expected services were used
        if result["success"]:
            used_services = set(result.get("services_used", []))
            expected_services = set(scenario["expected_services"])
            
            # Check if at least some expected services were used
            service_match = len(used_services.intersection(expected_services)) > 0
            scenario_result["service_match"] = service_match
            
            if service_match and result["steps_count"] > 0:
                successful_tests += 1
                scenario_result["overall_success"] = True
            else:
                scenario_result["overall_success"] = False
        else:
            scenario_result["overall_success"] = False
            
        results.append(scenario_result)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(test_scenarios),
        "successful_scenarios": successful_tests,
        "success_rate": round((float(successful_tests) / len(test_scenarios)) * 100, 2),
        "results": results
    }

def test_workflow_intelligence():
    """Test workflow intelligence and service selection"""
    logger.info("Testing workflow intelligence...")
    
    # Test service selection accuracy
    test_cases = [
        ("Send an email", ["gmail"]),
        ("Create a task", ["asana", "trello"]),
        ("Upload a file", ["google_drive", "dropbox"]),
        ("Send a message", ["slack", "microsoft_teams"]),
        ("Create documentation", ["notion"]),
        ("Schedule a meeting", ["google_calendar", "outlook_calendar"])
    ]
    
    intelligence_results = []
    accurate_selections = 0
    
    for user_input, expected_services in test_cases:
        result = test_workflow_generation(user_input)
        
        if result["success"]:
            used_services = set(result.get("services_used", []))
            expected_set = set(expected_services)
            
            # Check if at least one expected service was selected
            service_accuracy = len(used_services.intersection(expected_set)) > 0
            
            if service_accuracy:
                accurate_selections += 1
            
            intelligence_results.append({
                "user_input": user_input,
                "expected_services": expected_services,
                "actual_services": list(used_services),
                "accurate": service_accuracy,
                "steps_count": result.get("steps_count", 0)
            })
        else:
            intelligence_results.append({
                "user_input": user_input,
                "expected_services": expected_services,
                "actual_services": [],
                "accurate": False,
                "steps_count": 0,
                "error": result.get("error", "")
            })
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(test_cases),
        "accurate_selections": accurate_selections,
        "accuracy_rate": round((float(accurate_selections) / len(test_cases)) * 100, 2),
        "results": intelligence_results
    }

def main():
    """Main execution function"""
    print("🚀 ATOM Multi-Service Workflow Testing")
    print("=" * 50)
    
    # Check backend health
    try:
        health_response = requests.get(BACKEND_URL + "/healthz", timeout=10)
        if health_response.status_code == 200:
            print("✅ Backend is running")
        else:
            print("❌ Backend is not responding")
            return
    except Exception as e:
        print("❌ Cannot connect to backend: {0}".format(str(e)))
        return
    
    # Test complex workflow scenarios
    print("\n📊 Testing Complex Workflow Scenarios...")
    workflow_results = test_complex_workflow_scenarios()
    
    print("\n🎯 Complex Workflow Results:")
    print("   Total Scenarios: {0}".format(workflow_results["total_scenarios"]))
    print("   Successful: {0}".format(workflow_results["successful_scenarios"]))
    print("   Success Rate: {0}%".format(workflow_results["success_rate"]))
    
    print("\n🔍 Scenario Details:")
    for result in workflow_results["results"]:
        status_icon = "✅" if result["overall_success"] else "❌"
        print("   {0} {1}".format(status_icon, result["scenario_name"]))
        print("     Input: {0}".format(result["user_input"]))
        print("     Services: {0}".format(result["actual_services"]))
        print("     Steps: {0}".format(result["steps_count"]))
        if not result["overall_success"] and result.get("error"):
            print("     Error: {0}".format(result["error"]))
    
    # Test workflow intelligence
    print("\n🧠 Testing Workflow Intelligence...")
    intelligence_results = test_workflow_intelligence()
    
    print("\n🎯 Workflow Intelligence Results:")
    print("   Total Cases: {0}".format(intelligence_results["total_cases"]))
    print("   Accurate Selections: {0}".format(intelligence_results["accurate_selections"]))
    print("   Accuracy Rate: {0}%".format(intelligence_results["accuracy_rate"]))
    
    print("\n🔍 Intelligence Details:")
    for result in intelligence_results["results"]:
        status_icon = "✅" if result["accurate"] else "❌"
        print("   {0} Input: {1}".format(status_icon, result["user_input"]))
        print("     Expected: {0}".format(result["expected_services"]))
        print("     Actual: {0}".format(result["actual_services"]))
    
    # Save results to file
    results_file = "workflow_coordination_results.json"
    combined_results = {
        "timestamp": datetime.now().isoformat(),
        "complex_workflows": workflow_results,
        "workflow_intelligence": intelligence_results
    }
    
    with open(results_file, 'w') as f:
        json.dump(combined_results, f, indent=2)
    
    print("\n📄 Results saved to: {0}".format(results_file))
    
    # Overall assessment
    print("\n📈 Overall Assessment:")
    if workflow_results["success_rate"] >= 80 and intelligence_results["accuracy_rate"] >= 80:
        print("   ✅ EXCELLENT: Workflow coordination is working effectively")
    elif workflow_results["success_rate"] >= 60 and intelligence_results["accuracy_rate"] >= 60:
        print("   ⚠️  GOOD: Workflow coordination needs minor improvements")
    else:
        print("   ❌ NEEDS WORK: Workflow coordination requires significant improvements")
    
    print("\n🚀 Next Steps:")
    print("   1. Review workflow generation accuracy")
    print("   2. Enhance service selection algorithms")
    print("   3. Test with real service integrations")
    print("   4. Prepare for production deployment")

if __name__ == "__main__":
    main()