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

# Import colorama for colored output (if available)
try:
    from colorama import Fore, Style
    COLORAMA_AVAILABLE = True
except ImportError:
    # Define dummy colorama classes if not available
    class Fore:
        CYAN = ''
        RED = ''
        YELLOW = ''
    class Style:
        RESET_ALL = ''
    COLORAMA_AVAILABLE = False

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test_runner import E2ETestRunner

from config.test_config import TestConfig


def setup_environment():
    """Setup test environment and validate requirements"""
    print("[SETUP] Setting up E2E Test Environment...")

    # Check if we're in the right directory
    current_dir = Path(__file__).parent
    if (
        not (current_dir.parent / "backend").exists()
        and not (current_dir.parent / "frontend-nextjs").exists()
    ):
        print("[ERROR] Please run this script from the project root directory")
        sys.exit(1)

    # Load environment variables
    env_files = [".env", "config/.env", "backend/.env", "frontend-nextjs/.env"]

    for env_file in env_files:
        if Path(env_file).exists():
            print(f"[ENV] Loading environment from: {env_file}")
            break
    else:
        print("[WARN] No .env file found. Using environment variables only.")


def validate_credentials(test_category=None):
    """Validate required credentials for testing"""
    config = TestConfig()

    print("\n[CREDS] Validating Credentials...")

    if test_category:
        # Handle single or multiple categories
        if isinstance(test_category, list):
            # For multiple categories, check each individually
            available_categories = []
            all_missing_creds = []
            for category in test_category:
                missing_creds = config.get_missing_credentials(category)
                if not missing_creds:
                    available_categories.append(category)
                else:
                    all_missing_creds.extend(missing_creds)
            missing_creds = all_missing_creds
        else:
            # Single category
            missing_creds = config.get_missing_credentials(test_category)
            available_categories = [test_category] if not missing_creds else []
    else:
        missing_creds = config.get_missing_credentials("all")
        available_categories = config.get_test_categories_with_credentials()

    if missing_creds:
        print("[ERROR] Missing credentials:")
        for cred in missing_creds:
            print(f"   - {cred}")
    else:
        print("[OK] All required credentials are available")

    if available_categories:
        print(f"[OK] Available test categories: {', '.join(available_categories)}")
    else:
        print("[ERROR] No test categories have all required credentials")

    return available_categories


def check_service_connectivity():
    """Check connectivity to required services"""
    config = TestConfig()

    print("\n[NET] Checking Service Connectivity...")

    connectivity = config.check_service_connectivity()

    for service, status in connectivity.items():
        status_icon = "[OK]" if status else "[FAIL]"
        print(
            f"   {status_icon} {service.capitalize()}: {'Connected' if status else 'Not connected'}"
        )

    return connectivity


def generate_test_report(results, output_file=None):
    """Generate comprehensive test report"""
    print("\n[REPORT] Generating Test Report...")

    if output_file:
        report_path = Path(output_file)
    else:
        timestamp = results.get("end_time", "").replace(":", "").replace("-", "")
        report_path = Path("e2e_test_reports") / f"atom_e2e_report_{timestamp}.json"

    report_path.parent.mkdir(exist_ok=True)

    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"[FILE] Report saved to: {report_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("[SUMMARY] ATOM PLATFORM E2E TEST SUMMARY")
    print("=" * 80)

    overall_status = results.get("overall_status", "UNKNOWN")
    status_color = {"PASSED": "[PASS]", "FAILED": "[FAIL]", "NO_TESTS": "[SKIP]"}.get(
        overall_status, "[UNKNOWN]"
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
        "--skip-connectivity",
        action="store_true",
        help="Skip service connectivity check",
    )
    parser.add_argument(
        "--report-file", help="Output file for test report (default: auto-generated)"
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM-based marketing claim verification",
    )
    parser.add_argument(
        "--use-deepseek",
        action="store_true",
        help="Use DeepSeek for AI validation instead of OpenAI",
    )
    parser.add_argument(
        "--use-glm",
        action="store_true",
        help="Use GLM-4 for AI validation instead of OpenAI",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Setup environment
    setup_environment()

    # List categories if requested
    if args.list_categories:
        config = TestConfig()
        print("\n[CATEGORIES] Available Test Categories:")
        for category in config.REQUIRED_CREDENTIALS.keys():
            missing = config.get_missing_credentials(category)
            status = "[OK]" if not missing else "[FAIL]"
            print(
                f"   {status} {category}: {'Ready' if not missing else f'Missing {len(missing)} credentials'}"
            )
        return

    # Validate credentials
    test_categories = args.categories if args.categories else None
    available_categories = validate_credentials(test_categories[0] if test_categories and len(test_categories) == 1 else test_categories)

    # Check connectivity
    if not args.skip_connectivity:
        connectivity = check_service_connectivity()
    else:
        connectivity = {"frontend": True, "backend": True}  # Assume connected for testing

    # Stop here if validation only
    if args.validate_only:
        if available_categories and connectivity.get("backend", False):
            print("\n[OK] Environment is ready for testing!")
        else:
            print("\n[ERROR] Environment is not ready for testing")
            sys.exit(1)
        return

    # Check if we can proceed with testing
    if not available_categories:
        print(
            "\n[ERROR] Cannot proceed with testing - no categories have all required credentials"
        )
        sys.exit(1)

    if not connectivity.get("backend", False):
        print("\n[ERROR] Cannot proceed with testing - backend service is not accessible")
        sys.exit(1)

    # Run tests
    print("\n[START] Starting E2E Tests...")
    runner = E2ETestRunner()

    # Set environment variable to skip LLM if requested
    if args.skip_llm:
        os.environ["SKIP_LLM_VERIFICATION"] = "true"

    # Set environment variable to use GLM if requested
    if args.use_deepseek:
        os.environ["USE_DEEPSEEK_VALIDATOR"] = "true"
    
    if args.use_glm:
        os.environ["USE_GLM_VALIDATOR"] = "true"
        print(f"{Fore.CYAN}Using GLM 4.6 for AI validation{Style.RESET_ALL}")

    try:
        results = runner.run_all_tests(available_categories)

        # Generate report
        report_path = generate_test_report(results, args.report_file)

        # Exit with appropriate code
        if results.get("overall_status") == "PASSED":
            print("\n[SUCCESS] All tests passed!")
            sys.exit(0)
        else:
            print("\n[FAIL] Some tests failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n[STOP] Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] Test execution failed: {str(e)}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
