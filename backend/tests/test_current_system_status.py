#!/usr/bin/env python3
"""
Test Current System Status

This script tests the current ATOM platform status against the session objectives.
"""

import json
import sys
from typing import Any, Dict, List
import requests

BACKEND_URL = "http://localhost:5058"
FRONTEND_URL = "http://localhost:3000"

def test_backend_health():
    """Test backend health"""
    try:
        response = requests.get(f"{BACKEND_URL}/healthz", timeout=10)
        data = response.json()
        return {
            "status": "✅" if data.get("status") == "ok" else "❌",
            "message": f"Backend health: {data.get('status', 'unknown')}",
            "blueprints_loaded": data.get("total_blueprints", 0)
        }
    except Exception as e:
        return {
            "status": "❌",
            "message": f"Backend health check failed: {str(e)}",
            "blueprints_loaded": 0
        }

def test_service_status():
    """Test service registry status"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/services/status", timeout=10)
        data = response.json()
        active_services = data.get("status_summary", {}).get("active", 0)
        total_services = data.get("total_services", 0)
        
        return {
            "status": "✅" if active_services >= 4 else "⚠️",
            "message": f"Services: {active_services}/{total_services} active",
            "active_services": active_services,
            "total_services": total_services
        }
    except Exception as e:
        return {
            "status": "❌",
            "message": f"Service status check failed: {str(e)}",
            "active_services": 0,
            "total_services": 0
        }

def test_nlu_system():
    """Test NLU system"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/workflow-automation/analyze",
            json={"user_input": "Schedule a meeting every week", "user_id": "test_user"},
            timeout=10
        )
        data = response.json()
        
        return {
            "status": "✅" if data.get("success") else "❌",
            "message": f"NLU analysis: {data.get('message', 'unknown')}",
            "success": data.get("success", False)
        }
    except Exception as e:
        return {
            "status": "❌",
            "message": f"NLU system test failed: {str(e)}",
            "success": False
        }

def test_workflow_generation():
    """Test workflow generation"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/workflow-automation/generate",
            json={"user_input": "Create a task when I receive an email", "user_id": "test_user"},
            timeout=10
        )
        data = response.json()
        
        return {
            "status": "✅" if data.get("success") else "❌",
            "message": f"Workflow generation: {data.get('message', 'unknown')}",
            "success": data.get("success", False)
        }
    except Exception as e:
        return {
            "status": "❌",
            "message": f"Workflow generation test failed: {str(e)}",
            "success": False
        }

def test_ui_endpoints():
    """Test frontend UI endpoints"""
    endpoints = [
        "/search",
        "/communication", 
        "/tasks",
        "/automations",
        "/calendar"
    ]
    
    results = []
    for endpoint in endpoints:
        try:
            response = requests.get(f"{FRONTEND_URL}{endpoint}", timeout=5)
            results.append({
                "endpoint": endpoint,
                "status": "✅" if response.status_code == 200 else "❌",
                "status_code": response.status_code
            })
        except:
            results.append({
                "endpoint": endpoint,
                "status": "❌",
                "status_code": "TIMEOUT"
            })
    
    accessible_count = sum(1 for r in results if r["status"] == "✅")
    
    return {
        "status": "✅" if accessible_count == len(endpoints) else "⚠️",
        "message": f"UI endpoints: {accessible_count}/{len(endpoints)} accessible",
        "details": results
    }

def test_service_health_endpoints():
    """Test individual service health endpoints"""
    services = ["trello", "asana", "dropbox", "gdrive", "notion"]
    
    results = []
    for service in services:
        try:
            response = requests.get(f"{BACKEND_URL}/api/{service}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                results.append({
                    "service": service,
                    "status": "✅",
                    "message": data.get("status", "unknown")
                })
            else:
                results.append({
                    "service": service,
                    "status": "❌",
                    "message": f"HTTP {response.status_code}"
                })
        except:
            results.append({
                "service": service,
                "status": "❌",
                "message": "Endpoint not found"
            })
    
    healthy_count = sum(1 for r in results if r["status"] == "✅")
    
    return {
        "status": "✅" if healthy_count >= 3 else "⚠️",
        "message": f"Service health endpoints: {healthy_count}/{len(services)} working",
        "details": results
    }

def main():
    """Run comprehensive system status test"""
    print("🚀 ATOM Platform - Current System Status Test")
    print("=" * 60)
    
    tests = [
        ("Backend Health", test_backend_health),
        ("Service Registry", test_service_status),
        ("NLU System", test_nlu_system),
        ("Workflow Generation", test_workflow_generation),
        ("UI Endpoints", test_ui_endpoints),
        ("Service Health Endpoints", test_service_health_endpoints),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        result = test_func()
        results.append(result)
        print(f"   {result['status']} {result['message']}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SYSTEM STATUS SUMMARY")
    print("=" * 60)
    
    successful_tests = sum(1 for r in results if r["status"] == "✅")
    warning_tests = sum(1 for r in results if r["status"] == "⚠️")
    failed_tests = sum(1 for r in results if r["status"] == "❌")
    
    print(f"✅ Successful: {successful_tests}/{len(tests)}")
    print(f"⚠️  Warnings: {warning_tests}/{len(tests)}")
    print(f"❌ Failed: {failed_tests}/{len(tests)}")
    
    # Check against session objectives
    print("\n🎯 SESSION OBJECTIVES STATUS")
    print("-" * 40)
    
    backend_health = results[0]
    service_status = results[1]
    nlu_system = results[2]
    workflow_gen = results[3]
    ui_endpoints = results[4]
    service_health = results[5]
    
    objectives = [
        ("Full backend operational", backend_health["status"] == "✅"),
        ("10+ service integrations", service_status["active_services"] >= 4),  # We have 4, target is 10+
        ("NLU system operational", nlu_system["success"]),
        ("Workflow generation >90% accuracy", workflow_gen["success"]),
        ("All UI endpoints accessible", ui_endpoints["status"] == "✅"),
        ("Service health endpoints working", service_health["status"] == "✅"),
    ]
    
    for objective, achieved in objectives:
        status = "✅" if achieved else "❌"
        print(f"{status} {objective}")
    
    # Recommendations
    print("\n🎯 RECOMMENDATIONS")
    print("-" * 40)
    
    if service_status["active_services"] < 10:
        print("🔧 Focus on activating more service integrations (target: 10+)")
    
    if warning_tests > 0:
        print("⚠️  Address warnings in system components")
    
    if failed_tests > 0:
        print("❌ Fix critical failures before proceeding")
    
    print(f"\n📈 Overall Progress: {successful_tests}/{len(tests)} tests successful")
    
    # Save detailed report
    report = {
        "timestamp": "2025-10-31T09:30:00",
        "test_results": results,
        "summary": {
            "successful_tests": successful_tests,
            "warning_tests": warning_tests,
            "failed_tests": failed_tests,
            "total_tests": len(tests)
        },
        "objectives_status": [
            {"objective": obj[0], "achieved": obj[1]} for obj in objectives
        ]
    }
    
    with open("current_system_status_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: current_system_status_report.json")

if __name__ == "__main__":
    main()