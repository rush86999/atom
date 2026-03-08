#!/usr/bin/env python3
"""
New Code Coverage Enforcement

Enforces 80% coverage on all new files regardless of coverage phase.
Prevents accumulation of untested new code.

Usage:
    python new_code_coverage_gate.py --coverage-file coverage.json --base-branch origin/main
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# New code always requires 80% coverage regardless of phase
NEW_CODE_THRESHOLD = 80.0


def get_new_files(base_branch: str = "origin/main") -> List[str]:
    """
    Get list of new files added in current branch.

    Uses git diff --name-only --diff-filter=A to find added files.

    Args:
        base_branch: Base branch for comparison (default: origin/main)

    Returns:
        List of new file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=A", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        new_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        logger.info(f"Found {len(new_files)} new files in branch")
        return new_files
    except subprocess.CalledProcessError as e:
        logger.warning(f"git diff command failed: {e}")
        return []
    except FileNotFoundError:
        logger.warning("git command not found")
        return []


def load_coverage_data(coverage_file: Path) -> Dict:
    """
    Load coverage data from JSON file.

    Args:
        coverage_file: Path to coverage.json

    Returns:
        Coverage data dictionary
    """
    try:
        with open(coverage_file, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded coverage data from {coverage_file}")
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading coverage data from {coverage_file}: {e}")
        raise


def check_new_file_coverage(coverage_data: Dict, new_files: List[str]) -> bool:
    """
    Enforce 80% coverage on all new Python files.

    Args:
        coverage_data: Coverage data from coverage.json
        new_files: List of new file paths

    Returns:
        True if all files pass, False otherwise
    """
    all_passed = True
    checked_files = 0

    for file_path in new_files:
        # Only check Python files
        if not file_path.endswith('.py'):
            logger.debug(f"Skipping non-Python file: {file_path}")
            continue

        # Skip test files
        if 'test' in file_path or 'tests' in file_path:
            logger.debug(f"Skipping test file: {file_path}")
            continue

        # Get file coverage from coverage data
        files_data = coverage_data.get("files", {})
        file_coverage = files_data.get(file_path, {})

        if not file_coverage:
            print(f"⚠️  WARNING: New file {file_path} not found in coverage data (0% coverage)")
            all_passed = False
            checked_files += 1
            continue

        # Extract coverage percentage
        summary = file_coverage.get("summary", {})
        coverage_pct = summary.get("percent_covered", 0.0)

        if coverage_pct < NEW_CODE_THRESHOLD:
            print(f"❌ ERROR: New file {file_path} has {coverage_pct:.1f}% coverage (minimum: {NEW_CODE_THRESHOLD:.0f}%)")
            all_passed = False
        else:
            print(f"✅ PASS: New file {file_path} has {coverage_pct:.1f}% coverage")

        checked_files += 1

    if checked_files == 0:
        print("✅ No new Python files detected (excluding tests)")

    return all_passed


def main():
    """Main enforcement logic."""
    parser = argparse.ArgumentParser(
        description="Enforce 80% coverage on new files"
    )

    parser.add_argument(
        "--coverage-file",
        type=Path,
        required=True,
        help="Path to coverage.json"
    )

    parser.add_argument(
        "--base-branch",
        default="origin/main",
        help="Base branch for comparison (default: origin/main)"
    )

    args = parser.parse_args()

    # Check emergency bypass
    emergency_bypass = os.getenv("EMERGENCY_COVERAGE_BYPASS", "false").lower() == "true"
    if emergency_bypass:
        print("⚠️  COVERAGE GATE BYPASSED (emergency mode)")
        print("   EMERGENCY_COVERAGE_BYPASS=true")
        print()
        sys.exit(0)

    # Load coverage data
    if not args.coverage_file.exists():
        print(f"ERROR: Coverage file not found: {args.coverage_file}")
        sys.exit(2)

    try:
        coverage_data = load_coverage_data(args.coverage_file)
    except Exception as e:
        print(f"ERROR: Failed to load coverage data: {e}")
        sys.exit(2)

    # Get new files
    new_files = get_new_files(args.base_branch)

    if not new_files:
        print("✅ No new files detected")
        sys.exit(0)

    print(f"📊 Checking {len(new_files)} new files...")
    print()

    # Enforce 80% coverage
    if check_new_file_coverage(coverage_data, new_files):
        print()
        print("✅ All new files meet 80% coverage threshold")
        sys.exit(0)
    else:
        print()
        print("❌ Some new files do not meet 80% coverage threshold")
        print()
        print("Required actions:")
        print("  1. Add tests for new files to reach 80% coverage")
        print("  2. Use EMERGENCY_COVERAGE_BYPASS=true for critical PRs (requires approval)")
        sys.exit(1)


if __name__ == "__main__":
    main()
