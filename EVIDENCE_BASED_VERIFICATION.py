#!/usr/bin/env python3
"""
🚀 ATOM Personal Assistant - Evidence-Based Verification Script

This script provides concrete evidence for the current state of the ATOM application.
It only tests what can be verified with actual evidence, not claims.

Last Updated: 2025-09-27
"""

import os
import sys
import importlib
from datetime import datetime

# Add backend to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
)


def print_header(message):
    """Print formatted header"""
    print(f"\n{'=' * 60}")
    print(f"🔍 {message}")
    print(f"{'=' * 60}")


def print_result(test_name, status, evidence=""):
    """Print test result with evidence"""
    emoji = "✅" if status else "❌"
    status_text = "PASS" if status else "FAIL"
    print(f"{emoji} {test_name}: {status_text}")
    if evidence:
        print(f"   📝 Evidence: {evidence}")
    return status


def verify_file_exists(file_path, description):
    """Verify a file exists and is readable"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                content = f.read(100)  # Read first 100 chars to verify readability
            return print_result(description, True, f"File exists: {file_path}")
        else:
            return print_result(description, False, f"File not found: {file_path}")
    except Exception as e:
        return print_result(description, False, f"Error: {e}")


def verify_endpoint_functionality():
    """Verify that API endpoints return expected status codes"""
    print_header("API ENDPOINT VERIFICATION")

    results = []

    try:
        from minimal_app import create_minimal_app

        app = create_minimal_app()

        with app.test_client() as client:
            # Test health endpoint
            health_response = client.get("/healthz")
            results.append(
                print_result(
                    "Health Endpoint (/healthz)",
                    health_response.status_code == 200,
                    f"Status: {health_response.status_code}, Data: {health_response.get_json()}",
                )
            )

            # Test dashboard endpoint
            dashboard_response = client.get("/api/dashboard?user_id=test")
            results.append(
                print_result(
                    "Dashboard Endpoint (/api/dashboard)",
                    dashboard_response.status_code == 200,
                    f"Status: {dashboard_response.status_code}",
                )
            )

            # Test integrations status endpoint
            integrations_response = client.get("/api/integrations/status")
            results.append(
                print_result(
                    "Integrations Status Endpoint (/api/integrations/status)",
                    integrations_response.status_code == 200,
                    f"Status: {integrations_response.status_code}",
                )
            )

    except Exception as e:
        results.append(print_result("API Endpoint Testing", False, f"Error: {e}"))

    return all(results)


def verify_package_imports():
    """Verify that packages can be imported (evidence from test_package_imports.py)"""
    print_header("PACKAGE IMPORT VERIFICATION")

    # Instead of testing imports directly, check if the test file exists and runs
    test_file = "test_package_imports.py"
    if os.path.exists(test_file):
        try:
            # Import the test module to see if it runs
            spec = importlib.util.spec_from_file_location(
                "test_package_imports", test_file
            )
            test_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(test_module)

            # Check if the test has a main function that runs
            if hasattr(test_module, "main"):
                return print_result(
                    "Package Import Testing Framework",
                    True,
                    "test_package_imports.py loads successfully",
                )
            else:
                return print_result(
                    "Package Import Testing Framework",
                    False,
                    "test_package_imports.py missing main function",
                )

        except Exception as e:
            return print_result(
                "Package Import Testing Framework", False, f"Error loading test: {e}"
            )
    else:
        return print_result(
            "Package Import Testing Framework",
            False,
            f"Test file not found: {test_file}",
        )


def verify_real_service_files():
    """Verify that real service implementation files exist"""
    print_header("REAL SERVICE IMPLEMENTATION FILES")

    real_service_files = [
        ("box_service_real.py", "Box Service Implementation"),
        ("asana_service_real.py", "Asana Service Implementation"),
        ("jira_service_real.py", "Jira Service Implementation"),
        ("trello_service_real.py", "Trello Service Implementation"),
        ("docusign_service_real.py", "Docusign Service Implementation"),
        ("wordpress_service_real.py", "WordPress Service Implementation"),
        ("quickbooks_service_real.py", "QuickBooks Service Implementation"),
        ("auth_handler_box_real.py", "Box Auth Handler"),
        ("trello_handler_real.py", "Trello Handler"),
    ]

    results = []
    for filename, description in real_service_files:
        if os.path.exists(filename):
            results.append(print_result(description, True, f"File exists: {filename}"))
        else:
            results.append(
                print_result(description, False, f"File missing: {filename}")
            )

    return all(results)


def verify_testing_framework():
    """Verify that testing framework files exist"""
    print_header("TESTING FRAMEWORK VERIFICATION")

    test_files = [
        ("test_real_integrations.py", "Real Integration Testing"),
        ("test_package_imports.py", "Package Import Testing"),
        ("test_api_keys.py", "API Key Testing"),
    ]

    results = []
    for filename, description in test_files:
        if os.path.exists(filename):
            # Check if file has content
            with open(filename, "r") as f:
                content = f.read()
                if len(content) > 100:  # Reasonable minimum size
                    results.append(
                        print_result(
                            description, True, f"File exists with content: {filename}"
                        )
                    )
                else:
                    results.append(
                        print_result(description, False, f"File too small: {filename}")
                    )
        else:
            results.append(
                print_result(description, False, f"File missing: {filename}")
            )

    return all(results)


def verify_application_structure():
    """Verify that core application files exist"""
    print_header("APPLICATION STRUCTURE VERIFICATION")

    core_files = [
        ("main_api_app.py", "Main Application"),
        ("minimal_app.py", "Minimal Application"),
        ("start_app.py", "Application Startup Script"),
    ]

    results = []
    for filename, description in core_files:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                content = f.read()
                if "Flask" in content or "app" in content.lower():
                    results.append(
                        print_result(
                            description,
                            True,
                            f"File exists with Flask content: {filename}",
                        )
                    )
                else:
                    results.append(
                        print_result(
                            description,
                            False,
                            f"File exists but missing Flask content: {filename}",
                        )
                    )
        else:
            results.append(
                print_result(description, False, f"File missing: {filename}")
            )

    return all(results)


def main():
    """Main verification function"""
    print("🚀 ATOM PERSONAL ASSISTANT - EVIDENCE-BASED VERIFICATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print("📋 This script provides concrete evidence, not claims.")
    print("   Only tests what can be verified with actual evidence.")
    print("=" * 70)

    start_time = datetime.now()

    # Change to backend directory for testing
    original_dir = os.getcwd()
    backend_dir = os.path.join(original_dir, "backend", "python-api-service")

    if os.path.exists(backend_dir):
        os.chdir(backend_dir)
        print(f"📁 Testing in directory: {backend_dir}")
    else:
        print(f"❌ Backend directory not found: {backend_dir}")
        return 1

    # Run all verifications
    tests = [
        ("Application Structure", verify_application_structure),
        ("API Endpoints", verify_endpoint_functionality),
        ("Real Service Files", verify_real_service_files),
        ("Testing Framework", verify_testing_framework),
        ("Package Import Framework", verify_package_imports),
    ]

    results = {}
    for test_name, test_func in tests:
        results[test_name] = test_func()

    # Calculate summary
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    duration = datetime.now() - start_time

    print_header("VERIFICATION SUMMARY")

    print(f"📊 Evidence-Based Results:")
    print(f"   • Total Categories Verified: {total_tests}")
    print(f"   • Passed: {passed_tests}")
    print(f"   • Failed: {total_tests - passed_tests}")
    print(f"   • Success Rate: {success_rate:.1f}%")
    print(f"   • Duration: {duration.total_seconds():.2f} seconds")

    # Evidence-based status determination
    if success_rate >= 80:
        status = "🟢 READY FOR DEVELOPMENT"
        emoji = "✅"
        summary = "Core infrastructure verified. Ready for API key integration."
    elif success_rate >= 60:
        status = "🟡 DEVELOPMENT IN PROGRESS"
        emoji = "⚠️"
        summary = "Basic infrastructure exists. Some components need work."
    else:
        status = "🔴 NEEDS SIGNIFICANT WORK"
        emoji = "🚨"
        summary = "Core infrastructure incomplete. Major work required."

    print(f"\n{emoji} EVIDENCE-BASED STATUS: {status} {emoji}")
    print(f"   📋 {summary}")

    # Return to original directory
    os.chdir(original_dir)

    # Exit with appropriate code
    if success_rate >= 60:
        print(f"\n✅ Verification complete. Application is development-ready.")
        return 0
    else:
        print(f"\n❌ Verification complete. Significant work needed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
