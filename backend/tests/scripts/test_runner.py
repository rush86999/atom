#!/usr/bin/env python3
"""
Unified Test Runner for Atom Platform

Orchestrates test execution across all platforms:
- Backend pytest tests
- Web E2E tests (Playwright)
- Mobile API tests (pytest)
- Desktop tests (Tauri cargo)

Usage:
    python test_runner.py                    # Run all platforms
    python test_runner.py --platform backend # Run backend only
    python test_runner.py --workers 8        # Configure parallelism
    python test_runner.py --no-report        # Skip Allure report
"""
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


# Default configuration
DEFAULT_WORKERS = "auto"
ALLURE_RESULTS_DIR = "allure-results"
ALLURE_REPORT_DIR = "allure-report"


def run_command(cmd: List[str], cwd: str = None) -> int:
    """Run command and return exit code."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode


def run_backend_tests(workers: str, extra_args: List[str]) -> int:
    """Run backend pytest tests with Allure reporting."""
    print("\n" + "="*60)
    print("Running Backend Tests")
    print("="*60)

    cmd = [
        "pytest", "tests/",
        "-n", workers,
        "--alluredir", f"{ALLURE_RESULTS_DIR}/backend",
        "-v",
        *extra_args
    ]

    return run_command(cmd, cwd="backend")


def run_web_e2e_tests(workers: str, extra_args: List[str]) -> int:
    """Run web E2E tests with Playwright."""
    print("\n" + "="*60)
    print("Running Web E2E Tests")
    print("="*60)

    cmd = [
        "pytest", "tests/",
        "-n", workers,
        "--alluredir", f"../{ALLURE_RESULTS_DIR}/web",
        "-v",
        *extra_args
    ]

    return run_command(cmd, cwd="backend/tests/e2e_ui")


def run_mobile_api_tests(workers: str, extra_args: List[str]) -> int:
    """Run mobile API-level tests."""
    print("\n" + "="*60)
    print("Running Mobile API Tests")
    print("="*60)

    # Mobile API tests use pytest (same format as backend)
    cmd = [
        "pytest", "tests/",
        "-n", workers,
        "--alluredir", f"../../{ALLURE_RESULTS_DIR}/mobile",
        "-v",
        *extra_args
    ]

    # Check if mobile tests exist
    mobile_tests_path = Path("mobile/tests")
    if not mobile_tests_path.exists():
        print("Mobile API tests not found, skipping...")
        return 0

    return run_command(cmd, cwd="mobile")


def run_desktop_tests(extra_args: List[str]) -> int:
    """Run desktop Tauri tests."""
    print("\n" + "="*60)
    print("Running Desktop Tests")
    print("="*60)

    # Tauri cargo tests
    cmd = [
        "cargo", "test",
        "--manifest-path", "desktop/Cargo.toml",
        *extra_args
    ]

    desktop_path = Path("desktop")
    if not desktop_path.exists():
        print("Desktop tests not found, skipping...")
        return 0

    return run_command(cmd, cwd="desktop")


def clean_allure_results():
    """Clean Allure results directory before test run."""
    if os.path.exists(ALLURE_RESULTS_DIR):
        shutil.rmtree(ALLURE_RESULTS_DIR)
    os.makedirs(ALLURE_RESULTS_DIR, exist_ok=True)


def generate_allure_report():
    """Generate unified Allure report from all platforms."""
    print("\n" + "="*60)
    print("Generating Allure Report")
    print("="*60)

    # Merge Allure results from all platforms
    merged_dir = ALLURE_RESULTS_DIR
    for platform in ["backend", "web", "mobile"]:
        platform_dir = os.path.join(ALLURE_RESULTS_DIR, platform)
        if os.path.exists(platform_dir):
            # Copy to merged directory (Allure will aggregate)
            for file in os.listdir(platform_dir):
                src = os.path.join(platform_dir, file)
                dst = os.path.join(merged_dir, f"{platform}_{file}")
                shutil.copy2(src, dst)

    # Generate report
    cmd = [
        "allure", "generate",
        merged_dir,
        "--clean",
        "--o", ALLURE_REPORT_DIR
    ]

    exit_code = run_command(cmd)

    if exit_code == 0:
        print(f"\n✅ Allure report generated: {ALLURE_REPORT_DIR}/index.html")
        print("   View with: allure open allure-report")
    else:
        print(f"\n⚠️  Allure report generation failed (exit {exit_code})")
        print("   Install Allure: brew install allure  # macOS")

    return exit_code


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Unified test runner for Atom platform"
    )
    parser.add_argument(
        "--platform",
        choices=["all", "backend", "web", "mobile", "desktop"],
        default="all",
        help="Platform to test (default: all)"
    )
    parser.add_argument(
        "--workers",
        default=DEFAULT_WORKERS,
        help="Number of parallel workers (default: auto)"
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip Allure report generation"
    )
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        help="Extra arguments to pass to pytest"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Clean Allure results
    clean_allure_results()

    # Track overall exit code
    exit_code = 0

    # Run tests based on platform
    if args.platform in ["all", "backend"]:
        exit_code |= run_backend_tests(args.workers, args.extra)

    if args.platform in ["all", "web"]:
        exit_code |= run_web_e2e_tests(args.workers, args.extra)

    if args.platform in ["all", "mobile"]:
        exit_code |= run_mobile_api_tests(args.workers, args.extra)

    if args.platform in ["all", "desktop"]:
        exit_code |= run_desktop_tests(args.extra)

    # Generate report
    if not args.no_report:
        report_exit_code = generate_allure_report()
        exit_code |= report_exit_code

    # Print summary
    print("\n" + "="*60)
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ Tests failed with exit code {exit_code}")
    print("="*60)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
