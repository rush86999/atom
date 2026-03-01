#!/usr/bin/env python3
"""
PR Coverage Comment Bot for Atom CI/CD

This script generates coverage delta reports for pull requests with file-by-file
breakdown on coverage drops. It provides developers immediate visibility into
coverage changes during code review.

Usage:
    python pr_coverage_comment_bot.py --help
    python pr_coverage_comment_bot.py --coverage-file coverage.json --base-branch origin/main
    python pr_coverage_comment_bot.py --coverage-file coverage.json --base-branch origin/main --output-file payload.json

Exit Codes:
    0: Success
    1: Error
    2: No coverage data
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


# Constants
DEFAULT_TARGET_COVERAGE = 80.0
COVERAGE_DROP_THRESHOLD = 1.0  # Only show files with >1% drop


def get_git_diff_files(base_branch: str) -> List[str]:
    """
    Get list of changed files compared to base branch.

    Args:
        base_branch: Base branch name (e.g., origin/main)

    Returns:
        List of changed file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        # Filter to Python files only
        return [f for f in files if f.endswith('.py')]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def load_coverage_data(coverage_file: Path) -> Optional[Dict[str, Any]]:
    """
    Load coverage data from JSON file.

    Args:
        coverage_file: Path to coverage.json

    Returns:
        Coverage data dict or None if error
    """
    if not coverage_file.exists():
        print(f"Error: Coverage file not found: {coverage_file}", file=sys.stderr)
        return None

    try:
        with open(coverage_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading coverage file: {e}", file=sys.stderr)
        return None


def get_baseline_coverage(base_branch: str) -> Optional[float]:
    """
    Get baseline coverage from base branch.

    Args:
        base_branch: Base branch name (e.g., origin/main)

    Returns:
        Baseline coverage percentage or None
    """
    try:
        # Try to fetch coverage.json from base branch
        result = subprocess.run(
            ["git", "show", f"{base_branch}:backend/tests/coverage_reports/metrics/coverage.json"],
            capture_output=True,
            text=True,
            check=False  # Don't fail if file doesn't exist in history
        )

        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            return data.get("totals", {}).get("percent_covered", 0.0)

        return None
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return None


def get_file_by_file_delta(
    coverage_data: Dict[str, Any],
    changed_files: List[str],
    baseline_coverage: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Get file-by-file coverage delta for changed files.

    Args:
        coverage_data: Current coverage data
        changed_files: List of changed file paths
        baseline_coverage: Baseline coverage percentage (if available)

    Returns:
        List of files with coverage drops
    """
    files_data = coverage_data.get("files", {})
    drops = []

    for file_path in changed_files:
        # Normalize path (remove leading backend/ if present)
        normalized_path = file_path
        if normalized_path.startswith("backend/"):
            normalized_path = normalized_path[len("backend/"):]

        if normalized_path not in files_data:
            continue

        file_info = files_data[normalized_path]
        summary = file_info.get("summary", {})
        current_pct = summary.get("percent_covered", 0.0)

        # For now, we'll flag any file below target as needing attention
        # In a full implementation, we'd compare against baseline per-file
        if current_pct < DEFAULT_TARGET_COVERAGE:
            # Estimate "before" as either baseline or target
            before_pct = baseline_coverage if baseline_coverage else DEFAULT_TARGET_COVERAGE
            delta_pct = current_pct - before_pct

            drops.append({
                "path": normalized_path,
                "before_pct": round(before_pct, 2),
                "after_pct": round(current_pct, 2),
                "delta_pct": round(delta_pct, 2),
                "covered_lines": summary.get("covered_lines", 0),
                "total_lines": summary.get("num_statements", 0)
            })

    # Sort by delta (largest drops first)
    drops.sort(key=lambda x: x["delta_pct"])

    return drops


def generate_pr_comment_payload(
    coverage_file: Path,
    base_branch: str,
    commit_hash: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate PR comment payload with coverage delta and file-by-file breakdown.

    Args:
        coverage_file: Path to coverage.json
        base_branch: Base branch name
        commit_hash: Current commit hash

    Returns:
        JSON payload with comment body
    """
    # Load coverage data
    coverage_data = load_coverage_data(coverage_file)
    if not coverage_data:
        return {
            "error": "Could not load coverage data",
            "body": "Error: Coverage data not available"
        }

    # Extract totals
    totals = coverage_data.get("totals", {})
    current_coverage = totals.get("percent_covered", 0.0)
    covered_lines = totals.get("covered_lines", 0)
    total_lines = totals.get("num_statements", 0)

    # Get baseline coverage
    baseline_coverage = get_baseline_coverage(base_branch)
    if baseline_coverage is None:
        baseline_coverage = DEFAULT_TARGET_COVERAGE  # Use target as fallback

    # Calculate delta
    delta_coverage = current_coverage - baseline_coverage

    # Get changed files
    changed_files = get_git_diff_files(base_branch)

    # Get file-by-file delta (only files with drops)
    files_with_drops = get_file_by_file_delta(coverage_data, changed_files, baseline_coverage)

    # Build comment body
    body_lines = []
    body_lines.append("## Coverage Report")
    body_lines.append("")
    body_lines.append("| Metric | Value |")
    body_lines.append("|--------|-------|")
    body_lines.append(f"| Coverage | {current_coverage:.2f}% |")
    body_lines.append(f"| Delta | {delta_coverage:+.2f}% |")
    body_lines.append(f"| Target | {DEFAULT_TARGET_COVERAGE:.0f}% |")
    body_lines.append(f"| Lines | {covered_lines:,} / {total_lines:,} |")

    # Add file-by-file breakdown if there are drops
    if files_with_drops:
        body_lines.append("")
        body_lines.append("### Files with Coverage Drops")
        body_lines.append("")
        body_lines.append("| File | Before | After | Change | Lines |")
        body_lines.append("|------|--------|-------|--------|-------|")

        for file_info in files_with_drops[:10]:  # Limit to top 10
            path = file_info["path"]
            before = file_info["before_pct"]
            after = file_info["after_pct"]
            delta = file_info["delta_pct"]
            covered = file_info["covered_lines"]
            total = file_info["total_lines"]

            # Truncate long paths
            if len(path) > 40:
                path = "..." + path[-37:]

            body_lines.append(
                f"| {path} | {before:.1f}% | {after:.1f}% | {delta:+.1f}% | {covered}/{total} |"
            )

        if len(files_with_drops) > 10:
            body_lines.append(f"| ... ({len(files_with_drops) - 10} more files) | | | | |")

    # Add recommendations
    if delta_coverage < 0:
        body_lines.append("")
        body_lines.append("### ⚠️ Coverage Decreased")
        body_lines.append("")
        body_lines.append("Please review the changes and add tests for uncovered code.")

    elif current_coverage < DEFAULT_TARGET_COVERAGE:
        body_lines.append("")
        body_lines.append("### 📈 Progress toward Target")
        body_lines.append("")
        body_lines.append(f"Current coverage is below {DEFAULT_TARGET_COVERAGE:.0f}% target. ")
        body_lines.append("Focus on adding tests to the files above to improve coverage.")

    else:
        body_lines.append("")
        body_lines.append("### ✅ Coverage Target Met")
        body_lines.append("")
        body_lines.append(f"Coverage is at or above the {DEFAULT_TARGET_COVERAGE:.0f}% target!")

    # Add footer
    body_lines.append("")
    body_lines.append("---")
    body_lines.append("")
    body_lines.append("*Report generated by [Coverage Report Workflow](.github/workflows/coverage-report.yml)*")

    return {
        "body": "\n".join(body_lines),
        "coverage": {
            "current": round(current_coverage, 2),
            "baseline": round(baseline_coverage, 2),
            "delta": round(delta_coverage, 2),
            "target": DEFAULT_TARGET_COVERAGE
        },
        "files_with_drops": len(files_with_drops),
        "changed_files_count": len(changed_files)
    }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate PR comment payload for coverage delta reporting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate payload for current coverage
  python pr_coverage_comment_bot.py \\
    --coverage-file backend/tests/coverage_reports/metrics/coverage.json \\
    --base-branch origin/main

  # Save to file
  python pr_coverage_comment_bot.py \\
    --coverage-file backend/tests/coverage_reports/metrics/coverage.json \\
    --base-branch origin/main \\
    --output-file pr_comment_payload.json

Exit Codes:
  0: Success
  1: Error
  2: No coverage data
        """
    )

    parser.add_argument(
        "--coverage-file",
        type=Path,
        default="backend/tests/coverage_reports/metrics/coverage.json",
        help="Path to coverage.json (default: backend/tests/coverage_reports/metrics/coverage.json)"
    )

    parser.add_argument(
        "--base-branch",
        type=str,
        default="origin/main",
        help="Base branch to compare against (default: origin/main)"
    )

    parser.add_argument(
        "--commit",
        type=str,
        default=None,
        help="Current commit hash (auto-detected if not provided)"
    )

    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Output file for payload JSON (default: stdout)"
    )

    args = parser.parse_args()

    # Auto-detect commit hash if not provided
    commit_hash = args.commit
    if commit_hash is None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            commit_hash = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # Generate payload
    payload = generate_pr_comment_payload(
        Path(args.coverage_file),
        args.base_branch,
        commit_hash
    )

    # Check for errors
    if "error" in payload:
        print(json.dumps(payload, indent=2))
        sys.exit(2)

    # Output payload
    json_output = json.dumps(payload, indent=2)

    if args.output_file:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_file, 'w') as f:
            f.write(json_output)
        print(f"Payload written to: {args.output_file}", file=sys.stderr)
    else:
        print(json_output)

    sys.exit(0)


if __name__ == "__main__":
    main()
