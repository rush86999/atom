#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CI Trending Integration Script

Purpose: Orchestrates all trending steps in CI environment, handles missing
coverage files gracefully, and provides structured output for job summaries.

Usage:
    python ci_trending_integration.py [options]

Options:
    --coverage-dir PATH       Path to coverage artifacts (default: ../coverage/)
    --output-dir PATH         Path for output files (default: tests/coverage_reports/)
    --commit-sha STR          Current commit SHA (from GITHUB_SHA)
    --branch STR              Branch name (from GITHUB_REF_NAME)
    --format FORMAT           Output format: json|markdown (default: json)

Example:
    python ci_trending_integration.py --coverage-dir ./coverage/ --output-dir ./output/
    python ci_trending_integration.py --commit-sha abc123 --branch main --format markdown
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
try:
    from typing import Dict
except ImportError:
    # Python 3.9+ supports built-in generic types
    Dict = dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Default paths
DEFAULT_COVERAGE_DIR = Path("../coverage/")
DEFAULT_OUTPUT_DIR = Path("tests/coverage_reports/")


def check_coverage_files_exist(coverage_dir: Path) -> Dict[str, bool]:
    """
    Check if coverage files exist for each platform.

    Args:
        coverage_dir: Path to coverage artifacts directory

    Returns:
        Dict mapping platform names to file existence status
    """
    platforms = {
        "backend": coverage_dir / "backend" / "coverage.json",
        "frontend": coverage_dir / "frontend" / "coverage-final.json",
        "mobile": coverage_dir / "mobile" / "coverage-final.json",
        "desktop": coverage_dir / "desktop" / "coverage.json"
    }

    existence = {}
    for platform, file_path in platforms.items():
        exists = file_path.exists()
        existence[platform] = exists

        if not exists:
            logger.warning(f"Coverage file not found: {file_path}")

    return existence


def orchestrate_trending(
    coverage_dir: Path,
    output_dir: Path,
    commit_sha: str = "",
    branch: str = ""
) -> Dict:
    """
    Orchestrate all trending steps in CI environment.

    Steps:
    1. Check coverage files exist
    2. Run cross_platform_coverage_gate.py
    3. Run update_cross_platform_trending.py with commit tracking
    4. Run coverage_trend_analyzer.py for regression detection
    5. Run generate_coverage_dashboard.py for visual trends

    Args:
        coverage_dir: Path to coverage artifacts
        output_dir: Path for output files
        commit_sha: Current commit SHA for tracking
        branch: Branch name for tracking

    Returns:
        Dict with:
            - success: bool
            - summary_path: Path or None
            - dashboard_path: Path or None
            - regression_count: int
            - critical_regressions: List[str]
            - errors: List[str]
    """
    result = {
        "success": True,
        "summary_path": None,
        "dashboard_path": None,
        "regression_count": 0,
        "critical_regressions": [],
        "errors": []
    }

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Check coverage files exist
    logger.info("Checking coverage files...")
    file_existence = check_coverage_files_exist(coverage_dir)

    available_platforms = [p for p, exists in file_existence.items() if exists]
    missing_platforms = [p for p, exists in file_existence.items() if not exists]

    if available_platforms:
        logger.info(f"Available platforms: {', '.join(available_platforms)}")
    else:
        error_msg = "No coverage files found for any platform"
        logger.error(error_msg)
        result["errors"].append(error_msg)
        result["success"] = False
        return result

    if missing_platforms:
        logger.warning(f"Missing platforms: {', '.join(missing_platforms)}")
        result["errors"].append(f"Missing coverage for: {', '.join(missing_platforms)}")

    # Step 2: Run cross-platform coverage gate
    logger.info("Running cross-platform coverage gate...")
    summary_path = output_dir / "metrics" / "cross_platform_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import subprocess

        cmd = [
            "python",
            "tests/scripts/cross_platform_coverage_gate.py",
            "--backend-coverage", str(coverage_dir / "backend" / "coverage.json"),
            "--frontend-coverage", str(coverage_dir / "frontend" / "coverage-final.json"),
            "--mobile-coverage", str(coverage_dir / "mobile" / "coverage-final.json"),
            "--desktop-coverage", str(coverage_dir / "desktop" / "coverage.json"),
            "--format", "json",
            "--output-json", str(summary_path)
        ]

        process_result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        if process_result.returncode != 0:
            logger.warning(f"Coverage gate failed: {process_result.stderr}")
            result["errors"].append(f"Coverage gate failed: {process_result.stderr}")

        if summary_path.exists():
            result["summary_path"] = str(summary_path)
            logger.info(f"Summary generated: {summary_path}")
        else:
            logger.warning("Summary file not created")

    except Exception as e:
        logger.error(f"Error running coverage gate: {e}")
        result["errors"].append(f"Coverage gate error: {str(e)}")

    # Step 3: Update trending data with commit tracking
    if result["summary_path"]:
        logger.info("Updating trending data...")

        try:
            trend_file = output_dir / "metrics" / "cross_platform_trend.json"

            cmd = [
                "python",
                "tests/scripts/update_cross_platform_trending.py",
                "--summary", str(summary_path),
                "--trending-file", str(trend_file),
                "--commit-sha", commit_sha,
                "--branch", branch,
                "--prune"
            ]

            process_result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            if process_result.returncode != 0:
                logger.warning(f"Trending update failed: {process_result.stderr}")
                result["errors"].append(f"Trending update failed: {process_result.stderr}")

            logger.info("Trending data updated")

        except Exception as e:
            logger.error(f"Error updating trending data: {e}")
            result["errors"].append(f"Trending update error: {str(e)}")

    # Step 4: Detect regressions
    if result["summary_path"]:
        logger.info("Detecting regressions...")

        try:
            regression_file = output_dir / "metrics" / "coverage_regressions.json"
            trend_file = output_dir / "metrics" / "cross_platform_trend.json"

            cmd = [
                "python",
                "tests/scripts/coverage_trend_analyzer.py",
                "--trending-file", str(trend_file),
                "--regression-threshold", "1.0",
                "--output", str(regression_file),
                "--format", "json"
            ]

            process_result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")

            if regression_file.exists():
                with open(regression_file, 'r') as f:
                    regression_data = json.load(f)

                regressions = regression_data.get("regressions", [])
                result["regression_count"] = len(regressions)

                # Extract critical regressions
                critical = [r["platform"] for r in regressions if r.get("severity") == "critical"]
                result["critical_regressions"] = critical

                logger.info(f"Detected {len(regressions)} regressions ({len(critical)} critical)")
            else:
                logger.info("No regressions detected")

        except Exception as e:
            logger.error(f"Error detecting regressions: {e}")
            result["errors"].append(f"Regression detection error: {str(e)}")

    # Step 5: Generate trend dashboard
    logger.info("Generating trend dashboard...")

    try:
        dashboard_dir = output_dir / "dashboards"
        dashboard_dir.mkdir(parents=True, exist_ok=True)

        dashboard_path = dashboard_dir / "coverage_trend_30d.html"
        trend_file = output_dir / "metrics" / "cross_platform_trend.json"

        cmd = [
            "python",
            "tests/scripts/generate_coverage_dashboard.py",
            "--trending-file", str(trend_file),
            "--output", str(dashboard_path),
            "--days", "30"
        ]

        process_result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")

        if dashboard_path.exists():
            result["dashboard_path"] = str(dashboard_path)
            logger.info(f"Dashboard generated: {dashboard_path}")
        else:
            logger.warning("Dashboard file not created")

    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        result["errors"].append(f"Dashboard generation error: {str(e)}")

    # Determine overall success
    if result["critical_regressions"]:
        result["success"] = False

    return result


def generate_ci_summary(results: Dict) -> str:
    """
    Create markdown summary for job posting.

    Args:
        results: Result dict from orchestrate_trending()

    Returns:
        Formatted markdown string
    """
    lines = []
    lines.append("## Coverage Trending Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.utcnow().isoformat() + 'Z'}")
    lines.append("")

    # Platform status
    lines.append("### Platform Status")
    lines.append("")

    if results.get("summary_path"):
        lines.append("✅ Coverage summary generated")
    else:
        lines.append("⚠️ Coverage summary not available")

    lines.append("")

    # Regression status
    lines.append("### Regression Status")
    lines.append("")

    regression_count = results.get("regression_count", 0)
    critical = results.get("critical_regressions", [])

    if regression_count > 0:
        lines.append(f"⚠️ **{regression_count} regression(s) detected**")
        lines.append("")

        if critical:
            lines.append(f"**Critical ({len(critical)}):** {', '.join(critical)}")
            lines.append("")

        lines.append("See detailed regression report in artifacts")
    else:
        lines.append("✅ **No regressions detected**")

    lines.append("")

    # Dashboard status
    lines.append("### Dashboard")
    lines.append("")

    if results.get("dashboard_path"):
        lines.append("✅ Trend dashboard generated")
        lines.append(f"Path: `{results['dashboard_path']}`")
    else:
        lines.append("⚠️ Dashboard not available")

    lines.append("")

    # Errors
    if results.get("errors"):
        lines.append("### Warnings/Errors")
        lines.append("")

        for error in results["errors"]:
            lines.append(f"- ⚠️ {error}")

        lines.append("")

    # Overall status
    lines.append("### Overall Status")
    lines.append("")

    if results.get("success"):
        lines.append("✅ **Trending analysis complete**")
    else:
        lines.append("❌ **Critical issues detected**")
        lines.append("")
        lines.append("Build may fail due to critical regressions")

    lines.append("")

    return "\n".join(lines)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="CI trending integration script"
    )

    parser.add_argument(
        "--coverage-dir",
        type=Path,
        default=DEFAULT_COVERAGE_DIR,
        help="Path to coverage artifacts"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Path for output files"
    )

    parser.add_argument(
        "--commit-sha",
        type=str,
        default="",
        help="Current commit SHA (from GITHUB_SHA)"
    )

    parser.add_argument(
        "--branch",
        type=str,
        default="",
        help="Branch name (from GITHUB_REF_NAME)"
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "markdown"],
        default="json",
        help="Output format"
    )

    args = parser.parse_args()

    # Run orchestration
    results = orchestrate_trending(
        args.coverage_dir,
        args.output_dir,
        args.commit_sha,
        args.branch
    )

    # Generate output
    if args.format == "json":
        # JSON output for machine parsing
        output = json.dumps(results, indent=2)
        print(output)

        # Exit with error code if critical regressions
        if not results["success"]:
            sys.exit(1)

    elif args.format == "markdown":
        # Markdown output for job summaries
        summary = generate_ci_summary(results)
        print(summary)

        # Exit with error code if critical regressions
        if not results["success"]:
            sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
