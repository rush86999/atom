#!/usr/bin/env python3
"""
Per-Commit Coverage Report Generator for Atom v5.0

This script generates JSON coverage reports for each CI run, storing them in
coverage_reports/commits/ for historical analysis. Reports include coverage
metrics, module breakdown, and top uncovered files.

Usage:
    # Generate report for current coverage
    python per_commit_report_generator.py \
        --coverage-file backend/tests/coverage_reports/metrics/coverage.json \
        --commits-dir backend/tests/coverage_reports/commits

    # Specify commit hash (for CI)
    python per_commit_report_generator.py \
        --coverage-file backend/tests/coverage_reports/metrics/coverage.json \
        --commits-dir backend/tests/coverage_reports/commits \
        --commit abc123def456

    # List existing reports
    python per_commit_report_generator.py --list

    # Cleanup old reports (older than 90 days)
    python per_commit_report_generator.py \
        --commits-dir backend/tests/coverage_reports/commits \
        --cleanup \
        --retention-days 90

Features:
    - Per-commit coverage snapshots with commit hash and timestamp
    - Module breakdown (core, api, tools, skills)
    - Files below 80% threshold tracking
    - Top 10 uncovered files by missing lines
    - Automatic cleanup of old reports (configurable retention)
    - JSON format for machine readability (~1-2KB per report)
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


# Constants
DEFAULT_COVERAGE_FILE = Path("tests/coverage_reports/metrics/coverage.json")
DEFAULT_COMMITS_DIR = Path("tests/coverage_reports/commits")
DEFAULT_RETENTION_DAYS = 90
COVERAGE_THRESHOLD = 80.0


def get_git_commit_hash() -> Optional[str]:
    """
    Get current git commit hash.

    Returns:
        Commit hash as string, or None if not in git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def extract_module_breakdown(coverage_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Extract module-level coverage from coverage data.

    Args:
        coverage_data: Loaded coverage.json data

    Returns:
        Dict mapping module name to {covered, total, percent}
    """
    files = coverage_data.get("files", {})
    module_breakdown = {}

    for file_path, file_data in files.items():
        # Determine module from file path
        if file_path.startswith("core/"):
            module = "core"
        elif file_path.startswith("api/"):
            module = "api"
        elif file_path.startswith("tools/"):
            module = "tools"
        elif file_path.startswith("skills/"):
            module = "skills"
        else:
            module = "other"

        # Aggregate module coverage
        if module not in module_breakdown:
            module_breakdown[module] = {"covered": 0, "total": 0}

        summary = file_data.get("summary", {})
        module_breakdown[module]["covered"] += summary.get("covered_lines", 0)
        module_breakdown[module]["total"] += summary.get("num_statements", 0)

    # Calculate percentages
    result = {}
    for module, data in module_breakdown.items():
        covered = data["covered"]
        total = data["total"]
        percent = (covered / total * 100) if total > 0 else 0.0
        result[module] = {
            "covered": covered,
            "total": total,
            "percent": round(percent, 2)
        }

    return result


def get_files_below_threshold(
    coverage_data: Dict[str, Any],
    threshold: float = COVERAGE_THRESHOLD
) -> List[Dict[str, Any]]:
    """
    Find files with coverage below threshold.

    Args:
        coverage_data: Loaded coverage.json data
        threshold: Coverage threshold percentage

    Returns:
        List of dicts with path, percent_covered, uncovered_lines, total_lines
        Sorted by uncovered_lines descending
    """
    files = coverage_data.get("files", {})
    low_coverage_files = []

    for file_path, file_data in files.items():
        summary = file_data.get("summary", {})
        percent_covered = summary.get("percent_covered", 0.0)
        covered_lines = summary.get("covered_lines", 0)
        total_lines = summary.get("num_statements", 0)

        if percent_covered < threshold:
            uncovered_lines = total_lines - covered_lines
            low_coverage_files.append({
                "path": file_path,
                "percent_covered": round(percent_covered, 2),
                "uncovered_lines": uncovered_lines,
                "total_lines": total_lines
            })

    # Sort by uncovered_lines descending
    low_coverage_files.sort(key=lambda x: x["uncovered_lines"], reverse=True)

    return low_coverage_files


def generate_commit_report(
    coverage_file: Path,
    commit_hash: Optional[str] = None,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate per-commit coverage report.

    Args:
        coverage_file: Path to coverage.json
        commit_hash: Git commit hash (auto-detected if None)
        timestamp: ISO timestamp (auto-generated if None)

    Returns:
        Dict with commit, timestamp, overall_coverage, branch_coverage,
        module_breakdown, files_below_80, top_uncovered_files

    Raises:
        FileNotFoundError: If coverage_file doesn't exist
        ValueError: If coverage data is invalid
    """
    if not coverage_file.exists():
        raise FileNotFoundError(f"Coverage file not found: {coverage_file}")

    # Load coverage data
    with open(coverage_file) as f:
        coverage_data = json.load(f)

    # Extract totals
    totals = coverage_data.get("totals", {})
    overall_coverage = totals.get("percent_covered", 0.0)
    covered_lines = totals.get("covered_lines", 0)
    total_lines = totals.get("num_statements", 0)
    covered_branches = totals.get("covered_branches", 0)
    total_branches = totals.get("num_branches", 0)

    if total_lines == 0:
        raise ValueError("Invalid coverage data: total_lines is 0")

    # Calculate branch coverage
    branch_coverage = (covered_branches / total_branches * 100) if total_branches > 0 else 0.0

    # Extract module breakdown
    module_breakdown = extract_module_breakdown(coverage_data)

    # Get files below threshold
    low_coverage_files = get_files_below_threshold(coverage_data, COVERAGE_THRESHOLD)

    # Top 10 uncovered files
    top_uncovered_files = low_coverage_files[:10]

    # Get commit hash
    if commit_hash is None:
        commit_hash = get_git_commit_hash()

    if commit_hash is None:
        commit_hash = "unknown"

    # Generate timestamp
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Build report
    report = {
        "commit": commit_hash,
        "short_hash": commit_hash[:8] if commit_hash != "unknown" else "unknown",
        "timestamp": timestamp,
        "overall_coverage": round(overall_coverage, 2),
        "covered_lines": covered_lines,
        "total_lines": total_lines,
        "branch_coverage": round(branch_coverage, 2),
        "module_breakdown": module_breakdown,
        "files_below_80": len(low_coverage_files),
        "top_uncovered_files": top_uncovered_files
    }

    return report


def store_commit_report(report: Dict[str, Any], commits_dir: Path) -> Path:
    """
    Store commit report as JSON file.

    Args:
        report: Report dict from generate_commit_report
        commits_dir: Directory to store reports

    Returns:
        Path to stored report file

    Raises:
        IOError: If unable to write report
    """
    # Create directory if needed
    commits_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename from short hash
    short_hash = report["short_hash"]
    filename = f"{short_hash}_coverage.json"
    filepath = commits_dir / filename

    # Write report
    with open(filepath, 'w') as f:
        json.dump(report, f, indent=2)

    return filepath


def cleanup_old_reports(
    commits_dir: Path,
    days_to_keep: int = DEFAULT_RETENTION_DAYS
) -> int:
    """
    Remove old coverage reports.

    Args:
        commits_dir: Directory containing reports
        days_to_keep: Number of days to retain reports

    Returns:
        Number of deleted files
    """
    if not commits_dir.exists():
        return 0

    # Calculate cutoff time
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

    deleted_count = 0

    # Iterate through JSON files
    for filepath in commits_dir.glob("*.json"):
        try:
            # Load report to get timestamp
            with open(filepath) as f:
                report = json.load(f)

            timestamp_str = report.get("timestamp")
            if not timestamp_str:
                continue

            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # Delete if older than cutoff
            if timestamp < cutoff_time:
                filepath.unlink()
                deleted_count += 1
                print(f"Deleted old report: {filepath.name}")

        except (json.JSONDecodeError, IOError, ValueError) as e:
            print(f"Warning: Could not process {filepath.name}: {e}", file=sys.stderr)
            continue

    return deleted_count


def list_reports(commits_dir: Path) -> None:
    """
    List all stored coverage reports.

    Args:
        commits_dir: Directory containing reports
    """
    if not commits_dir.exists():
        print(f"No reports directory found: {commits_dir}")
        return

    # Find all JSON files
    reports = sorted(commits_dir.glob("*.json"))

    if not reports:
        print(f"No reports found in: {commits_dir}")
        return

    print(f"Found {len(reports)} coverage report(s):")
    print("")
    print(f"{'Filename':<30} {'Commit':<12} {'Coverage':>10} {'Date':<12}")
    print("-" * 70)

    for filepath in reports:
        try:
            with open(filepath) as f:
                report = json.load(f)

            filename = filepath.name
            commit = report.get("short_hash", "unknown")
            coverage = report.get("overall_coverage", 0.0)
            timestamp_str = report.get("timestamp", "")
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            date = timestamp.strftime("%Y-%m-%d")

            print(f"{filename:<30} {commit:<12} {coverage:>9.2f}% {date:<12}")

        except (json.JSONDecodeError, IOError, ValueError) as e:
            print(f"{filename:<30} {'ERROR':<12} {'N/A':>10} {'N/A':<12}")

    print("")


def main():
    """Main execution entry point."""
    parser = argparse.ArgumentParser(
        description="Generate per-commit coverage reports for Atom v5.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate report for current coverage
  python per_commit_report_generator.py \\
      --coverage-file backend/tests/coverage_reports/metrics/coverage.json \\
      --commits-dir backend/tests/coverage_reports/commits

  # Specify commit hash (for CI)
  python per_commit_report_generator.py \\
      --coverage-file backend/tests/coverage_reports/metrics/coverage.json \\
      --commits-dir backend/tests/coverage_reports/commits \\
      --commit abc123def456

  # List existing reports
  python per_commit_report_generator.py --list

  # Cleanup old reports (older than 90 days)
  python per_commit_report_generator.py \\
      --commits-dir backend/tests/coverage_reports/commits \\
      --cleanup \\
      --retention-days 90
        """
    )

    parser.add_argument(
        "--coverage-file",
        type=Path,
        default=DEFAULT_COVERAGE_FILE,
        help="Path to coverage.json (default: backend/tests/coverage_reports/metrics/coverage.json)"
    )
    parser.add_argument(
        "--commits-dir",
        type=Path,
        default=DEFAULT_COMMITS_DIR,
        help="Directory to store commit reports (default: backend/tests/coverage_reports/commits)"
    )
    parser.add_argument(
        "--commit",
        type=str,
        default=None,
        help="Git commit hash (auto-detected if not provided)"
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help="Number of days to retain reports (default: 90)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing reports"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Cleanup old reports (run in addition to generation)"
    )

    args = parser.parse_args()

    # List mode
    if args.list:
        list_reports(args.commits_dir)
        return 0

    # Generate report
    try:
        report = generate_commit_report(
            args.coverage_file,
            args.commit
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    # Store report
    try:
        filepath = store_commit_report(report, args.commits_dir)
        print(f"✅ Coverage report saved: {filepath}")
        print(f"   Commit: {report['commit']}")
        print(f"   Coverage: {report['overall_coverage']:.2f}%")
        print(f"   Files below 80%: {report['files_below_80']}")
    except IOError as e:
        print(f"Error: Failed to store report: {e}", file=sys.stderr)
        return 1

    # Cleanup old reports if requested
    if args.cleanup:
        deleted = cleanup_old_reports(args.commits_dir, args.retention_days)
        if deleted > 0:
            print(f"✅ Cleaned up {deleted} old report(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
