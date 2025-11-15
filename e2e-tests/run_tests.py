#!/usr/bin/env python3
"""
Main Entry Point for Atom Platform E2E Tests
Coordinates test execution with credential validation and LLM verification
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test_runner import E2ETestRunner

from config.test_config import TestConfig


def setup_environment():
    """Setup test environment and validate requirements"""
    print("🔧 Setting up E2E Test Environment...")

    # Check if we're in the right directory
    current_dir = Path(__file__).parent
    if (
        not (current_dir.parent / "backend").exists()
        and not (current_dir.parent / "frontend-nextjs").exists()
    ):
        print("❌ Error: Please run this script from the project root directory")
        sys.exit(1)

    # Load environment variables
    env_files = [".env", "config/.env", "backend/.env", "frontend-nextjs/.env"]

    for env_file in env_files:
        if Path(env_file).exists():
            print(f"📁 Loading environment from: {env_file}")
            break
    else:
        print("⚠️  No .env file found. Using environment variables only.")


def validate_credentials(test_category=None):
    """Validate required credentials for testing"""
    config = TestConfig()

    print("\n🔐 Validating Credentials...")

    if test_category:
        missing_creds = config.get_missing_credentials(test_category)
        available_categories = [test_category] if not missing_creds else []
    else:
        missing_creds = config.get_missing_credentials("all")
        available_categories = config.get_test_categories_with_credentials()

    if missing_creds:
        print("❌ Missing credentials:")
        for cred in missing_creds:
            print(f"   - {cred}")
    else:
        print("✅ All required credentials are available")

    if available_categories:
        print(f"✅ Available test categories: {', '.join(available_categories)}")
    else:
        print("❌ No test categories have all required credentials")

    return available_categories


def check_service_connectivity():
    """Check connectivity to required services"""
    config = TestConfig()

    print("\n🌐 Checking Service Connectivity...")

    connectivity = config.check_service_connectivity()

    for service, status in connectivity.items():
        status_icon = "✅" if status else "❌"
        print(
            f"   {status_icon} {service.capitalize()}: {'Connected' if status else 'Not connected'}"
        )

    return connectivity


def generate_test_report(results, output_file=None):
    """Generate comprehensive test report"""
    print("\n📊 Generating Test Report...")

    if output_file:
        report_path = Path(output_file)
    else:
        timestamp = results.get("end_time", "").replace(":", "").replace("-", "")
        report_path = Path("e2e_test_reports") / f"atom_e2e_report_{timestamp}.json"

    report_path.parent.mkdir(exist_ok=True)

    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"📄 Report saved to: {report_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("🎯 ATOM PLATFORM E2E TEST SUMMARY")
    print("=" * 80)

    overall_status = results.get("overall_status", "UNKNOWN")
    status_color = {"PASSED": "🟢", "FAILED": "🔴", "NO_TESTS": "🟡"}.get(
        overall_status, "⚪"
    )

    print(f"Overall Status: {status_color} {overall_status}")
    print(f"Duration: {results.get('duration_seconds', 0):.2f} seconds")
    print(f"Total Tests: {results.get('total_tests', 0)}")
    print(f"Tests Passed: {results.get('tests_passed', 0)}")
    print(f"Tests Failed: {results.get('tests_failed', 0)}")

    if results.get("llm_verification_available", False):
        claims_info = results.get("marketing_claims_verified", {})
        verified = claims_info.get("verified", 0)
        total = claims_info.get("total", 0)
        if total > 0:
            print(
                f"Marketing Claims Verified: {verified}/{total} ({verified / total * 100:.1f}%)"
            )

    return report_path


def main():
    """Main entry point for E2E tests"""
    parser = argparse.ArgumentParser(description="Atom Platform E2E Test Runner")
    parser.add_argument(
        "categories",
        nargs="*",
        help="Specific test categories to run (e.g., core communication productivity)",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List available test categories with credential status",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate credentials and connectivity without running tests",
    )
    parser.add_argument(
        "--report-file", help="Output file for test report (default: auto-generated)"
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM-based marketing claim verification",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Setup environment
    setup_environment()

    # List categories if requested
    if args.list_categories:
        config = TestConfig()
        print("\n📋 Available Test Categories:")
        for category in config.REQUIRED_CREDENTIALS.keys():
            missing = config.get_missing_credentials(category)
            status = "✅" if not missing else "❌"
            print(
                f"   {status} {category}: {'Ready' if not missing else f'Missing {len(missing)} credentials'}"
            )
        return

    # Validate credentials
    test_categories = args.categories if args.categories else None
    available_categories = validate_credentials(test_categories)

    # Check connectivity
    connectivity = check_service_connectivity()

    # Stop here if validation only
    if args.validate_only:
        if available_categories and connectivity.get("backend", False):
            print("\n✅ Environment is ready for testing!")
        else:
            print("\n❌ Environment is not ready for testing")
            sys.exit(1)
        return

    # Check if we can proceed with testing
    if not available_categories:
        print(
            "\n❌ Cannot proceed with testing - no categories have all required credentials"
        )
        sys.exit(1)

    if not connectivity.get("backend", False):
        print("\n❌ Cannot proceed with testing - backend service is not accessible")
        sys.exit(1)

    # Run tests
    print("\n🚀 Starting E2E Tests...")
    runner = E2ETestRunner()

    # Set environment variable to skip LLM if requested
    if args.skip_llm:
        os.environ["SKIP_LLM_VERIFICATION"] = "true"

    try:
        results = runner.run_all_tests(available_categories)

        # Generate report
        report_path = generate_test_report(results, args.report_file)

        # Exit with appropriate code
        if results.get("overall_status") == "PASSED":
            print("\n🎉 All tests passed!")
            sys.exit(0)
        else:
            print("\n💥 Some tests failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️  Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test execution failed: {str(e)}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
