#!/usr/bin/env python3
"""
ATOM Platform - Current Status Diagnostic Script

This script provides a quick diagnostic of the current ATOM platform status,
focusing on what's working and what needs immediate attention.
"""

import requests
import json
import sys
import time
from typing import Dict, Any, List


def check_backend_health() -> Dict[str, Any]:
    """Check backend server health"""
    try:
        response = requests.get("http://localhost:5058/healthz", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "✅ OPERATIONAL",
                "details": data,
                "message": f"Backend running on port 5058 - Status: {data.get('status', 'unknown')}",
            }
        else:
            return {
                "status": "❌ UNHEALTHY",
                "details": {"status_code": response.status_code},
                "message": f"Backend returned HTTP {response.status_code}",
            }
    except Exception as e:
        return {
            "status": "❌ OFFLINE",
            "details": {"error": str(e)},
            "message": "Backend server is not accessible",
        }


def check_workflow_generation() -> Dict[str, Any]:
    """Test workflow automation generation"""
    try:
        response = requests.post(
            "http://localhost:5058/api/workflow-automation/generate",
            json={
                "user_input": "Schedule a meeting for tomorrow",
                "user_id": "test_user",
            },
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "✅ OPERATIONAL",
                "details": data,
                "message": f"Workflow generation working - Generated workflow with {len(data.get('workflow', {}).get('steps', []))} steps",
            }
        else:
            return {
                "status": "❌ FAILING",
                "details": {"status_code": response.status_code},
                "message": f"Workflow generation returned HTTP {response.status_code}",
            }
    except Exception as e:
        return {
            "status": "❌ OFFLINE",
            "details": {"error": str(e)},
            "message": "Workflow generation endpoint not accessible",
        }


def check_service_registry() -> Dict[str, Any]:
    """Check service registry status"""
    try:
        response = requests.get("http://localhost:5058/api/services/status", timeout=10)

        if response.status_code == 200:
            data = response.json()
            total_services = data.get("total_services", 0)
            active_services = data.get("status_summary", {}).get("active", 0)

            return {
                "status": "✅ OPERATIONAL",
                "details": data,
                "message": f"Service registry: {active_services}/{total_services} services active ({active_services / total_services * 100:.1f}%)",
            }
        else:
            return {
                "status": "⚠️ PARTIAL",
                "details": {"status_code": response.status_code},
                "message": f"Service registry endpoint returned HTTP {response.status_code}",
            }
    except Exception as e:
        return {
            "status": "❌ OFFLINE",
            "details": {"error": str(e)},
            "message": "Service registry endpoint not accessible",
        }


def check_ui_endpoints() -> Dict[str, Any]:
    """Check frontend UI endpoints"""
    ui_endpoints = [
        ("Search UI", "/search"),
        ("Communication UI", "/communication"),
        ("Task UI", "/tasks"),
        ("Workflow Automation UI", "/automations"),
        ("Scheduling UI", "/calendar"),
    ]

    results = []
    accessible_count = 0

    for ui_name, endpoint in ui_endpoints:
        try:
            response = requests.get(f"http://localhost:3000{endpoint}", timeout=5)
            if response.status_code == 200:
                results.append(
                    {"ui": ui_name, "status": "✅ ACCESSIBLE", "endpoint": endpoint}
                )
                accessible_count += 1
            else:
                results.append(
                    {
                        "ui": ui_name,
                        "status": "❌ INACCESSIBLE",
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                    }
                )
        except Exception as e:
            results.append(
                {
                    "ui": ui_name,
                    "status": "❌ OFFLINE",
                    "endpoint": endpoint,
                    "error": str(e),
                }
            )

    return {
        "status": "✅ OPERATIONAL"
        if accessible_count == len(ui_endpoints)
        else "⚠️ PARTIAL",
        "details": {"ui_endpoints": results},
        "message": f"UI endpoints: {accessible_count}/{len(ui_endpoints)} accessible",
    }


def check_voice_integration() -> Dict[str, Any]:
    """Check voice integration endpoints"""
    try:
        response = requests.get(
            "http://localhost:5058/api/transcription/health", timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "✅ OPERATIONAL",
                "details": data,
                "message": "Voice integration endpoints are operational",
            }
        else:
            return {
                "status": "❌ FAILING",
                "details": {"status_code": response.status_code},
                "message": f"Voice integration returned HTTP {response.status_code}",
            }
    except Exception as e:
        return {
            "status": "❌ OFFLINE",
            "details": {"error": str(e)},
            "message": "Voice integration endpoints not accessible",
        }


def check_nlu_system() -> Dict[str, Any]:
    """Check NLU system status"""
    try:
        response = requests.post(
            "http://localhost:3000/api/agent/nlu",
            json={"message": "test workflow request", "userId": "test_user"},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "✅ OPERATIONAL",
                "details": data,
                "message": "TypeScript NLU system is operational",
            }
        else:
            return {
                "status": "❌ FAILING",
                "details": {"status_code": response.status_code},
                "message": f"NLU system returned HTTP {response.status_code}",
            }
    except Exception as e:
        return {
            "status": "❌ OFFLINE",
            "details": {"error": str(e)},
            "message": "NLU system endpoint not accessible",
        }


def generate_status_report() -> Dict[str, Any]:
    """Generate comprehensive status report"""
    print("🚀 ATOM Platform - Current Status Diagnostic")
    print("=" * 60)

    checks = [
        ("Backend Health", check_backend_health),
        ("Workflow Generation", check_workflow_generation),
        ("Service Registry", check_service_registry),
        ("UI Endpoints", check_ui_endpoints),
        ("Voice Integration", check_voice_integration),
        ("NLU System", check_nlu_system),
    ]

    results = {}
    operational_count = 0
    total_checks = len(checks)

    for check_name, check_func in checks:
        print(f"\n🔍 Checking: {check_name}")
        result = check_func()
        results[check_name] = result

        status_icon = (
            "✅"
            if "OPERATIONAL" in result["status"]
            else "⚠️"
            if "PARTIAL" in result["status"]
            else "❌"
        )
        print(f"   {status_icon} {result['status']}")
        print(f"   {result['message']}")

        if "OPERATIONAL" in result["status"]:
            operational_count += 1

    # Overall assessment
    success_rate = (operational_count / total_checks) * 100

    print(f"\n📊 OVERALL ASSESSMENT")
    print("=" * 60)
    print(f"   Operational Systems: {operational_count}/{total_checks}")
    print(f"   Success Rate: {success_rate:.1f}%")

    if success_rate >= 80:
        print("   🎉 EXCELLENT - Most systems are operational")
    elif success_rate >= 60:
        print("   ⚠️  GOOD - Core systems working, some need attention")
    else:
        print("   ❌ NEEDS WORK - Critical systems need attention")

    # Immediate priorities
    print(f"\n🎯 IMMEDIATE PRIORITIES")
    print("=" * 60)

    priorities = []
    for check_name, result in results.items():
        if "❌" in result["status"]:
            priorities.append(f"   • {check_name}: {result['message']}")

    if priorities:
        print("Critical fixes needed:")
        for priority in priorities:
            print(priority)
    else:
        print("   ✅ All critical systems are operational!")

    # Next steps
    print(f"\n🚀 RECOMMENDED NEXT STEPS")
    print("=" * 60)

    if "❌" in results["Backend Health"]["status"]:
        print("   1. Fix backend startup issues")
    if (
        "❌" in results["Service Registry"]["status"]
        or "⚠️" in results["Service Registry"]["status"]
    ):
        print("   2. Activate service integrations")
    if "❌" in results["NLU System"]["status"]:
        print("   3. Debug TypeScript NLU system")
    if "❌" in results["Voice Integration"]["status"]:
        print("   4. Fix voice integration endpoints")

    if not any("❌" in result["status"] for result in results.values()):
        print("   1. Run comprehensive validation tests")
        print("   2. Activate additional service integrations")
        print("   3. Enhance workflow intelligence")
        print("   4. Test cross-UI coordination")

    # Save detailed report
    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": {
            "operational_systems": operational_count,
            "total_systems": total_checks,
            "success_rate": success_rate,
        },
        "detailed_results": results,
        "recommendations": priorities,
    }

    with open("current_status_report.json", "w") as f:
        json.dump(report_data, f, indent=2)

    print(f"\n📄 Detailed report saved to: current_status_report.json")

    return report_data


def main():
    """Main diagnostic function"""
    try:
        report = generate_status_report()

        # Exit with appropriate code
        success_rate = report["overall_status"]["success_rate"]
        if success_rate >= 70:
            sys.exit(0)  # Success
        elif success_rate >= 50:
            sys.exit(1)  # Partial success
        else:
            sys.exit(2)  # Needs significant work

    except Exception as e:
        print(f"❌ Diagnostic failed: {str(e)}")
        sys.exit(3)


if __name__ == "__main__":
    main()
