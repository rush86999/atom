#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced Service Detection for Workflow Automation
Improves service detection from natural language input
"""

import requests
import json
import time

BASE_URL = "http://localhost:5058"

# Service keyword mapping for enhanced detection
SERVICE_KEYWORDS = {
    "gmail": ["gmail", "email", "inbox", "message", "send email"],
    "asana": ["asana", "task", "todo", "project", "assign task"],
    "slack": ["slack", "notification", "message", "channel", "team"],
    "trello": ["trello", "board", "card", "list", "kanban"],
    "notion": ["notion", "note", "document", "page", "database"],
    "dropbox": ["dropbox", "file", "upload", "document", "storage"],
    "gdrive": ["google drive", "gdrive", "document", "file", "storage"],
    "github": ["github", "code", "repository", "issue", "pull request"],
    "calendar": ["calendar", "meeting", "schedule", "appointment", "event"],
    "outlook": ["outlook", "email", "calendar", "meeting"],
    "teams": ["teams", "meeting", "video", "call", "collaboration"],
    "jira": ["jira", "issue", "bug", "ticket", "project"],
    "box": ["box", "file", "storage", "document"],
    "tasks": ["task", "todo", "reminder", "deadline"]
}

def detect_services_from_text(user_input):
    """Enhanced service detection from natural language text"""
    detected_services = []
    user_input_lower = user_input.lower()
    
    for service, keywords in SERVICE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in user_input_lower:
                if service not in detected_services:
                    detected_services.append(service)
                break
    
    return detected_services

def test_enhanced_service_detection():
    """Test enhanced service detection with various inputs"""
    
    test_cases = [
        {
            "input": "When I receive an important email from gmail, create a task in asana and send a slack notification to my team",
            "expected": ["gmail", "asana", "slack"]
        },
        {
            "input": "After a calendar meeting in google calendar, create tasks in trello and send follow-up emails using gmail",
            "expected": ["calendar", "trello", "gmail"]
        },
        {
            "input": "When a document is uploaded to dropbox, process it and save to google drive for sharing",
            "expected": ["dropbox", "gdrive"]
        },
        {
            "input": "Create a github issue when a task is completed in asana and notify the team on slack",
            "expected": ["github", "asana", "slack"]
        },
        {
            "input": "Send an outlook email when a teams meeting is scheduled and create a follow-up task",
            "expected": ["outlook", "teams", "tasks"]
        },
        {
            "input": "First check my gmail for important emails, then create asana tasks for urgent items, finally send a slack summary",
            "expected": ["gmail", "asana", "slack"]
        },
        {
            "input": "Simultaneously check dropbox for new files and google drive for shared documents, then process both",
            "expected": ["dropbox", "gdrive"]
        },
        {
            "input": "If it's a work task, use asana, if it's a personal task, use trello, and always notify on slack",
            "expected": ["asana", "trello", "slack"]
        }
    ]
    
    print("🔍 Testing Enhanced Service Detection...")
    print("=" * 50)
    
    results = []
    
    for test in test_cases:
        detected = detect_services_from_text(test["input"])
        expected = test["expected"]
        
        # Calculate accuracy
        matched = [s for s in detected if s in expected]
        accuracy = len(matched) / len(expected) if expected else 0
        
        print("\n🧪 Input: {}".format(test["input"]))
        print("✅ Detected: {}".format(detected))
        print("🎯 Expected: {}".format(expected))
        print("📊 Accuracy: {:.1%}".format(accuracy))
        
        results.append({
            "input": test["input"],
            "detected_services": detected,
            "expected_services": expected,
            "matched_services": matched,
            "accuracy": accuracy
        })
    
    # Calculate overall statistics
    total_accuracy = sum(r["accuracy"] for r in results) / len(results)
    total_detected = sum(len(r["detected_services"]) for r in results)
    total_expected = sum(len(r["expected_services"]) for r in results)
    
    print("\n📊 Service Detection Summary:")
    print("=" * 50)
    print("🎯 Average Accuracy: {:.1%}".format(total_accuracy))
    print("📋 Total Detected Services: {}".format(total_detected))
    print("📋 Total Expected Services: {}".format(total_expected))
    
    # Save results
    with open('enhanced_service_detection_results.json', 'w') as f:
        json.dump({
            "timestamp": time.time(),
            "summary": {
                "average_accuracy": total_accuracy,
                "total_test_cases": len(test_cases),
                "total_detected_services": total_detected,
                "total_expected_services": total_expected
            },
            "detailed_results": results
        }, f, indent=2)
    
    print("\n💾 Results saved to enhanced_service_detection_results.json")
    
    return results

def create_enhanced_workflow_api():
    """Create enhanced workflow API that uses improved service detection"""
    
    print("\n🚀 Creating Enhanced Workflow API...")
    print("=" * 50)
    
    enhanced_workflows = [
        {
            "name": "Enhanced Email to Task Creation",
            "input": "When I receive an important email from gmail, create a task in asana and send a slack notification to my team",
            "expected_services": ["gmail", "asana", "slack"]
        },
        {
            "name": "Enhanced Meeting Follow-up",
            "input": "After a calendar meeting in google calendar, create tasks in trello and send follow-up emails using gmail",
            "expected_services": ["calendar", "trello", "gmail"]
        }
    ]
    
    enhanced_results = []
    
    for workflow in enhanced_workflows:
        print("\n🧪 Testing: {}".format(workflow['name']))
        print("Input: {}".format(workflow['input']))
        
        # First detect services
        detected_services = detect_services_from_text(workflow['input'])
        print("🔍 Detected Services: {}".format(detected_services))
        
        # Then generate workflow with detected services
        try:
            response = requests.post(
                "{}/api/workflow-automation/generate".format(BASE_URL),
                json={
                    "user_input": workflow["input"],
                    "user_id": "test_user",
                    "service_constraints": detected_services  # Pass detected services as constraints
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                workflow_services = result.get('workflow', {}).get('services', [])
                
                print("✅ Workflow generated successfully")
                print("📋 Workflow Services: {}".format(workflow_services))
                
                # Check if our detected services are in the workflow
                matched_services = [s for s in detected_services if s in workflow_services]
                accuracy = len(matched_services) / len(detected_services) if detected_services else 0
                
                enhanced_results.append({
                    "name": workflow["name"],
                    "success": True,
                    "detected_services": detected_services,
                    "workflow_services": workflow_services,
                    "matched_services": matched_services,
                    "accuracy": accuracy,
                    "expected_services": workflow["expected_services"]
                })
                
                print("🎯 Service Match Accuracy: {:.1%}".format(accuracy))
                
            else:
                print("❌ Failed to generate workflow: HTTP {}".format(response.status_code))
                enhanced_results.append({
                    "name": workflow["name"],
                    "success": False,
                    "error": "HTTP {}".format(response.status_code)
                })
                
        except Exception as e:
            print("❌ Error: {}".format(e))
            enhanced_results.append({
                "name": workflow["name"],
                "success": False,
                "error": str(e)
            })
    
    # Calculate overall statistics
    successful_workflows = [w for w in enhanced_results if w['success']]
    if successful_workflows:
        avg_accuracy = sum(w.get('accuracy', 0) for w in successful_workflows) / len(successful_workflows)
    else:
        avg_accuracy = 0
    
    print("\n📊 Enhanced Workflow API Summary:")
    print("=" * 50)
    print("✅ Successful Workflows: {}/{}".format(len(successful_workflows), len(enhanced_workflows)))
    print("🎯 Average Service Match Accuracy: {:.1%}".format(avg_accuracy))
    
    # Save enhanced results
    with open('enhanced_workflow_api_results.json', 'w') as f:
        json.dump({
            "timestamp": time.time(),
            "summary": {
                "successful_workflows": len(successful_workflows),
                "total_workflows": len(enhanced_workflows),
                "average_accuracy": avg_accuracy
            },
            "detailed_results": enhanced_results
        }, f, indent=2)
    
    print("\n💾 Enhanced API results saved to enhanced_workflow_api_results.json")
    
    return enhanced_results

def main():
    """Main execution function"""
    print("🚀 ATOM Enhanced Service Detection & Workflow Intelligence")
    print("=" * 50)
    
    # Phase 1: Enhanced Service Detection
    detection_results = test_enhanced_service_detection()
    
    # Phase 2: Enhanced Workflow API
    api_results = create_enhanced_workflow_api()
    
    # Summary
    print("\n🎉 ENHANCED SERVICE DETECTION COMPLETE")
    print("=" * 50)
    
    successful_detection = len([r for r in detection_results if r["accuracy"] > 0])
    successful_api = len([r for r in api_results if r["success"]])
    
    print("✅ Service Detection Tests: {}/{}".format(successful_detection, len(detection_results)))
    print("✅ Enhanced API Tests: {}/{}".format(successful_api, len(api_results)))
    
    if detection_results:
        avg_detection_accuracy = sum(r["accuracy"] for r in detection_results) / len(detection_results)
        print("🎯 Average Detection Accuracy: {:.1%}".format(avg_detection_accuracy))
    
    print("\n🚀 Next Steps:")
    print("   • Integrate enhanced service detection into workflow automation API")
    print("   • Update workflow agent integration service")
    print("   • Test with production workflows")

if __name__ == "__main__":
    main()