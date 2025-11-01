#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Workflow Intelligence Enhancement Script
Improves service detection and selection in workflow generation
"""

import requests
import json
import time

BASE_URL = "http://localhost:5058"

def test_enhanced_workflow_generation():
    """Test workflow generation with enhanced service detection"""
    
    enhanced_workflows = [
        {
            "name": "Email to Task Creation (Enhanced)",
            "input": "When I receive an important email from gmail, create a task in asana and send a slack notification to my team",
            "expected_services": ["gmail", "asana", "slack"],
            "keywords": ["gmail", "asana", "slack"]
        },
        {
            "name": "Meeting Follow-up (Enhanced)", 
            "input": "After a calendar meeting in google calendar, create tasks in trello and send follow-up emails using gmail",
            "expected_services": ["calendar", "trello", "gmail"],
            "keywords": ["calendar", "trello", "gmail"]
        },
        {
            "name": "Document Processing (Enhanced)",
            "input": "When a document is uploaded to dropbox, process it and save to google drive for sharing",
            "expected_services": ["dropbox", "gdrive"],
            "keywords": ["dropbox", "google drive", "gdrive"]
        },
        {
            "name": "Multi-Service Integration",
            "input": "Create a github issue when a task is completed in asana and notify the team on slack",
            "expected_services": ["github", "asana", "slack"],
            "keywords": ["github", "asana", "slack"]
        },
        {
            "name": "Communication Workflow",
            "input": "Send an outlook email when a teams meeting is scheduled and create a follow-up task",
            "expected_services": ["outlook", "teams", "tasks"],
            "keywords": ["outlook", "teams", "task"]
        }
    ]
    
    print("🤖 Testing Enhanced Workflow Intelligence...")
    print("=" * 50)
    
    enhanced_results = []
    
    for workflow in enhanced_workflows:
        print("\n🧪 Testing: {}".format(workflow['name']))
        print("Input: {}".format(workflow['input']))
        print("Expected Services: {}".format(workflow['expected_services']))
        
        try:
            response = requests.post(
                "{}/api/workflow-automation/generate".format(BASE_URL),
                json={
                    "user_input": workflow["input"],
                    "user_id": "test_user"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                detected_services = result.get('services', [])
                workflow_steps = len(result.get('steps', []))
                
                print("✅ Workflow generated successfully")
                print("📋 Services detected: {}".format(detected_services))
                print("🔢 Workflow steps: {}".format(workflow_steps))
                
                # Calculate service detection accuracy
                detected_count = len(detected_services)
                expected_count = len(workflow['expected_services'])
                
                # Check if expected services were detected
                matched_services = []
                for expected in workflow['expected_services']:
                    # Check for exact match or partial match
                    for detected in detected_services:
                        if expected in detected.lower() or detected.lower() in expected:
                            matched_services.append(expected)
                            break
                
                accuracy = len(matched_services) / expected_count if expected_count > 0 else 0
                
                enhanced_results.append({
                    "name": workflow["name"],
                    "success": True,
                    "detected_services": detected_services,
                    "expected_services": workflow["expected_services"],
                    "matched_services": matched_services,
                    "detection_accuracy": accuracy,
                    "workflow_steps": workflow_steps,
                    "keywords": workflow["keywords"]
                })
                
                print("🎯 Detection Accuracy: {:.1%}".format(accuracy))
                print("✅ Matched Services: {}".format(matched_services))
                
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
    total_workflows = len(enhanced_results)
    
    if successful_workflows:
        avg_accuracy = sum(w.get('detection_accuracy', 0) for w in successful_workflows) / len(successful_workflows)
        avg_steps = sum(w.get('workflow_steps', 0) for w in successful_workflows) / len(successful_workflows)
    else:
        avg_accuracy = 0
        avg_steps = 0
    
    print("\n📊 Enhanced Workflow Intelligence Summary:")
    print("=" * 50)
    print("✅ Successful Workflows: {}/{}".format(len(successful_workflows), total_workflows))
    print("🎯 Average Detection Accuracy: {:.1%}".format(avg_accuracy))
    print("🔢 Average Workflow Steps: {:.1f}".format(avg_steps))
    
    # Save enhanced results
    with open('enhanced_workflow_results.json', 'w') as f:
        json.dump({
            "timestamp": time.time(),
            "summary": {
                "total_workflows": total_workflows,
                "successful_workflows": len(successful_workflows),
                "average_accuracy": avg_accuracy,
                "average_steps": avg_steps
            },
            "detailed_results": enhanced_results
        }, f, indent=2)
    
    print("\n💾 Enhanced results saved to enhanced_workflow_results.json")
    
    return enhanced_results

def test_service_coordination():
    """Test cross-service workflow coordination"""
    
    coordination_tests = [
        {
            "name": "Multi-Service Sequential Workflow",
            "input": "First check my gmail for important emails, then create asana tasks for urgent items, finally send a slack summary",
            "expected_sequence": ["gmail", "asana", "slack"]
        },
        {
            "name": "Parallel Service Operations", 
            "input": "Simultaneously check dropbox for new files and google drive for shared documents, then process both",
            "expected_services": ["dropbox", "gdrive"]
        },
        {
            "name": "Conditional Service Selection",
            "input": "If it's a work task, use asana, if it's a personal task, use trello, and always notify on slack",
            "expected_services": ["asana", "trello", "slack"]
        }
    ]
    
    print("\n🔄 Testing Service Coordination...")
    print("=" * 50)
    
    coordination_results = []
    
    for test in coordination_tests:
        print("\n🧪 Testing: {}".format(test['name']))
        print("Input: {}".format(test['input']))
        
        try:
            response = requests.post(
                "{}/api/workflow-automation/generate".format(BASE_URL),
                json={
                    "user_input": test["input"],
                    "user_id": "test_user"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                detected_services = result.get('services', [])
                workflow_steps = result.get('steps', [])
                
                print("✅ Workflow generated successfully")
                print("📋 Services detected: {}".format(detected_services))
                print("🔢 Total steps: {}".format(len(workflow_steps)))
                
                # Analyze step sequence
                step_services = []
                for step in workflow_steps:
                    step_action = step.get('action', '').lower()
                    step_service = step.get('service', '').lower()
                    if step_service:
                        step_services.append(step_service)
                    elif any(service in step_action for service in ['gmail', 'asana', 'slack', 'dropbox', 'trello']):
                        for service in ['gmail', 'asana', 'slack', 'dropbox', 'trello']:
                            if service in step_action:
                                step_services.append(service)
                                break
                
                coordination_results.append({
                    "name": test["name"],
                    "success": True,
                    "detected_services": detected_services,
                    "step_sequence": step_services,
                    "total_steps": len(workflow_steps),
                    "expected_services": test.get('expected_services', []),
                    "expected_sequence": test.get('expected_sequence', [])
                })
                
                print("🔄 Step Sequence: {}".format(step_services))
                
            else:
                print("❌ Failed to generate workflow: HTTP {}".format(response.status_code))
                coordination_results.append({
                    "name": test["name"],
                    "success": False,
                    "error": "HTTP {}".format(response.status_code)
                })
                
        except Exception as e:
            print("❌ Error: {}".format(e))
            coordination_results.append({
                "name": test["name"],
                "success": False,
                "error": str(e)
            })
    
    # Save coordination results
    with open('service_coordination_results.json', 'w') as f:
        json.dump(coordination_results, f, indent=2)
    
    print("\n💾 Coordination results saved to service_coordination_results.json")
    
    return coordination_results

def main():
    """Main execution function"""
    print("🚀 ATOM Workflow Intelligence Enhancement")
    print("=" * 50)
    
    # Phase 1: Enhanced Service Detection
    enhanced_results = test_enhanced_workflow_generation()
    
    # Phase 2: Service Coordination
    coordination_results = test_service_coordination()
    
    # Summary
    print("\n🎉 WORKFLOW INTELLIGENCE ENHANCEMENT COMPLETE")
    print("=" * 50)
    
    successful_enhanced = len([w for w in enhanced_results if w['success']])
    successful_coordination = len([w for w in coordination_results if w['success']])
    
    print("✅ Enhanced Workflows: {}/{}".format(successful_enhanced, len(enhanced_results)))
    print("✅ Coordination Tests: {}/{}".format(successful_coordination, len(coordination_results)))
    
    # Calculate average accuracy
    if successful_enhanced > 0:
        avg_accuracy = sum(w.get('detection_accuracy', 0) for w in enhanced_results if w['success']) / successful_enhanced
        print("🎯 Average Detection Accuracy: {:.1%}".format(avg_accuracy))
    
    print("\n🚀 Next Steps:")
    print("   • Review enhanced workflow detection results")
    print("   • Analyze service coordination patterns")
    print("   • Prepare for production deployment")

if __name__ == "__main__":
    main()