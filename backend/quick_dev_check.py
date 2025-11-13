#!/usr/bin/env python3
"""
ATOM PLATFORM - QUICK DEVELOPMENT CHECK
Basic verification for core functionality during development
Focus: Essential services and basic API functionality
"""

import json
import time
from datetime import datetime

import requests


def log_test(name, status, details=None):
    """Quick test logging"""
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{icon} {name}: {status}")
    if details:
        for key, value in details.items():
            print(f"   {key}: {value}")


def check_service_health():
    """Check if essential services are running"""
    print("🔍 CHECKING SERVICE HEALTH")
    print("-" * 30)

    services = [
        ("Frontend", "http://localhost:3000"),
        ("Backend API", "http://localhost:8000"),
        ("OAuth Server", "http://localhost:5058"),
    ]

    results = {}
    for name, url in services:
        try:
            start_time = time.time()
            response = requests.get(
                f"{url}/health" if name != "OAuth Server" else f"{url}/healthz",
                timeout=5,
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                log_test(name, "PASS", {"response_time": f"{response_time:.3f}s"})
                results[name] = "PASS"
            else:
                log_test(name, "FAIL", {"status_code": response.status_code})
                results[name] = "FAIL"
        except Exception as e:
            log_test(name, "FAIL", {"error": str(e)})
            results[name] = "FAIL"

    return results


def check_core_endpoints():
    """Check essential API endpoints"""
    print("\n🔧 CHECKING CORE ENDPOINTS")
    print("-" * 30)

    endpoints = [
        ("Backend Health", "http://localhost:8000/health"),
        ("OAuth Status", "http://localhost:5058/api/auth/oauth-status"),
        ("API Docs", "http://localhost:8000/docs"),
    ]

    results = {}
    for name, url in endpoints:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code in [200, 405]:  # 405 is OK for some endpoints
                log_test(name, "PASS", {"status_code": response.status_code})
                results[name] = "PASS"
            else:
                log_test(name, "FAIL", {"status_code": response.status_code})
                results[name] = "FAIL"
        except Exception as e:
            log_test(name, "FAIL", {"error": str(e)})
            results[name] = "FAIL"

    return results


def check_service_registry():
    """Check if service registry is accessible"""
    print("\n🔗 CHECKING SERVICE REGISTRY")
    print("-" * 30)

    # Try multiple possible endpoints for service registry
    endpoints = [
        "http://localhost:8000/api/services",
        "http://localhost:8000/api/services/registry",
        "http://localhost:8000/services",
    ]

    for url in endpoints:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                service_count = (
                    len(data.get("services", []))
                    if isinstance(data, dict)
                    else len(data)
                )
                log_test(
                    "Service Registry",
                    "PASS",
                    {"endpoint": url, "services": service_count},
                )
                return "PASS"
        except:
            continue

    log_test("Service Registry", "FAIL", {"note": "No service registry endpoint found"})
    return "FAIL"


def check_workflow_system():
    """Check basic workflow functionality"""
    print("\n🔄 CHECKING WORKFLOW SYSTEM")
    print("-" * 30)

    # Check workflow endpoints
    workflow_endpoints = [
        "http://localhost:8000/api/workflows/templates",
    ]

    for url in workflow_endpoints:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                log_test("Workflow System", "PASS", {"endpoint": url})
                return "PASS"
        except:
            continue

    log_test("Workflow System", "WARN", {"note": "Workflow endpoints not accessible"})
    return "WARN"


def check_byok_system():
    """Check BYOK system basics"""
    print("\n🤖 CHECKING BYOK SYSTEM")
    print("-" * 30)

    endpoints = [
        "http://localhost:8000/api/ai/providers",
        "http://localhost:8000/ai/providers",
    ]

    for url in endpoints:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                providers = data.get("providers", [])
                log_test("BYOK Providers", "PASS", {"providers": len(providers)})
                return "PASS"
        except:
            continue

    log_test("BYOK Providers", "WARN", {"note": "BYOK endpoints not accessible"})
    return "WARN"


def generate_summary(all_results):
    """Generate development summary"""
    print("\n📊 DEVELOPMENT SUMMARY")
    print("-" * 30)

    total_tests = sum(len(results) for results in all_results.values())
    passed = sum(
        1
        for results in all_results.values()
        for status in results.values()
        if status == "PASS"
    )
    failed = sum(
        1
        for results in all_results.values()
        for status in results.values()
        if status == "FAIL"
    )
    warnings = sum(
        1
        for results in all_results.values()
        for status in results.values()
        if status == "WARN"
    )

    success_rate = (passed / total_tests * 100) if total_tests > 0 else 0

    print(f"Total Checks: {total_tests}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Warnings: {warnings}")
    print(f"📊 Success Rate: {success_rate:.1f}%")

    # Development readiness assessment
    if failed == 0 and success_rate >= 80:
        print("\n🎉 DEVELOPMENT READY: All systems go!")
        return True
    elif failed <= 2 and success_rate >= 60:
        print("\n⚠️  DEVELOPMENT ACCEPTABLE: Minor issues, development can continue")
        return True
    else:
        print("\n❌ DEVELOPMENT BLOCKED: Critical issues need attention")
        return False


def main():
    """Main execution function"""
    print("🚀 ATOM PLATFORM - QUICK DEV CHECK")
    print("=" * 40)
    print("Running essential development checks...")
    print("=" * 40)

    all_results = {}

    # Run all checks
    all_results["services"] = check_service_health()
    all_results["endpoints"] = check_core_endpoints()
    all_results["registry"] = {"Service Registry": check_service_registry()}
    all_results["workflows"] = {"Workflow System": check_workflow_system()}
    all_results["byok"] = {"BYOK System": check_byok_system()}

    # Generate summary
    dev_ready = generate_summary(all_results)

    print("\n" + "=" * 40)
    if dev_ready:
        print("✅ DEVELOPMENT CAN CONTINUE")
        print("Focus on feature development")
    else:
        print("❌ ADDRESS CRITICAL ISSUES FIRST")
        print("Fix failed checks before continuing development")
    print("=" * 40)

    # Save results for reference
    results_file = f"dev_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "results": all_results,
                "dev_ready": dev_ready,
            },
            f,
            indent=2,
        )

    print(f"\n📄 Results saved: {results_file}")


if __name__ == "__main__":
    main()
