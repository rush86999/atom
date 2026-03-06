#!/usr/bin/env python3
"""
Cross-Platform Coverage Gate Enforcement Script

Purpose: Enforce platform-specific coverage minimums (backend >=70%, frontend >=80%,
mobile >=50%, desktop >=40%) while computing weighted overall score for CI/CD quality gates.

Usage:
    python cross_platform_coverage_gate.py [options]

Options:
    --backend-coverage PATH     Path to pytest coverage.json (default: relative path)
    --frontend-coverage PATH    Path to Jest coverage-final.json (default: relative path)
    --mobile-coverage PATH      Path to jest-expo coverage-final.json (default: relative path)
    --desktop-coverage PATH     Path to tarpaulin coverage.json (default: relative path)
    --weights CSV               Override default weights (comma-separated: backend=0.35,frontend=0.40,...)
    --thresholds CSV            Override default thresholds (comma-separated: backend=70,frontend=80,...)
    --output-json PATH          Path for JSON output (default: cross_platform_summary.json)
    --format FORMAT             Output format: text|json|markdown (default: text)
    --strict                    Exit 1 if any platform below threshold (default: warning only)

Example:
    python cross_platform_coverage_gate.py --format text
    python cross_platform_coverage_gate.py --strict --format json
    python cross_platform_coverage_gate.py --thresholds backend=75,frontend=85 --format markdown
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Platform-specific thresholds (from REQUIREMENTS.md)
PLATFORM_THRESHOLDS = {
    "backend": 70.0,
    "frontend": 80.0,
    "mobile": 50.0,
    "desktop": 40.0
}

# Platform weights (from RESEARCH.md recommendation)
# Total must sum to 1.0
PLATFORM_WEIGHTS = {
    "backend": 0.35,
    "frontend": 0.40,
    "mobile": 0.15,
    "desktop": 0.10
}

# Default file paths relative to script location
DEFAULT_BACKEND_COVERAGE = Path(__file__).parent.parent.parent / "tests/coverage_reports/metrics/coverage.json"
DEFAULT_FRONTEND_COVERAGE = Path(__file__).parent.parent.parent.parent / "frontend-nextjs/coverage/coverage-final.json"
DEFAULT_MOBILE_COVERAGE = Path(__file__).parent.parent.parent.parent / "mobile/coverage/coverage-final.json"
DEFAULT_DESKTOP_COVERAGE = Path(__file__).parent.parent.parent.parent / "frontend-nextjs/src-tauri/coverage/coverage.json"
DEFAULT_OUTPUT_JSON = Path(__file__).parent.parent / "coverage_reports/metrics/cross_platform_summary.json"


def load_backend_coverage(path):
    """
    Load backend coverage from pytest coverage.json format.

    Expected schema:
    {
        "totals": {
            "percent_covered": 75.0,
            "covered_lines": 1500,
            "num_statements": 2000
        }
    }

    Args:
        path: Path to pytest coverage.json

    Returns:
        Dict with coverage_pct, covered, total, file_path, error (if applicable)
    """
    result = {
        "coverage_pct": 0.0,
        "covered": 0,
        "total": 0,
        "file_path": str(path),
        "error": None
    }

    if not path.exists():
        logger.warning(f"Backend coverage file not found: {path}")
        result["error"] = "file not found"
        return result

    try:
        with open(path, 'r') as f:
            data = json.load(f)

        totals = data.get("totals", {})
        result["coverage_pct"] = totals.get("percent_covered", 0.0)
        result["covered"] = totals.get("covered_lines", 0)
        result["total"] = totals.get("num_statements", 0)

        logger.info(f"Backend coverage: {result['coverage_pct']:.2f}% ({result['covered']}/{result['total']} lines)")

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading backend coverage: {e}")
        result["error"] = str(e)

    return result


def load_frontend_coverage(path):
    """
    Load frontend coverage from Jest coverage-final.json format.

    Expected schema:
    {
        "/path/to/file.ts": {
            "s": { "1": 10, "2": 5 },  # statement counts
            "b": { "1": [10, 5] },     # branch counts [taken, not taken]
            "f": { "1": 10 },          # function counts
            "l": { "1": 10 }           # line counts
        }
    }

    Args:
        path: Path to Jest coverage-final.json

    Returns:
        Dict with coverage_pct, covered, total, file_path, error (if applicable)
    """
    result = {
        "coverage_pct": 0.0,
        "covered": 0,
        "total": 0,
        "file_path": str(path),
        "error": None
    }

    if not path.exists():
        logger.warning(f"Frontend coverage file not found: {path}")
        result["error"] = "file not found"
        return result

    try:
        with open(path, 'r') as f:
            data = json.load(f)

        total_statements = 0
        covered_statements = 0

        for file_path, file_data in data.items():
            # Skip node_modules and test files
            if "node_modules" in file_path or "__tests__" in file_path:
                continue

            statements = file_data.get("s", {})
            for stmt_id, count in statements.items():
                total_statements += 1
                if count > 0:
                    covered_statements += 1

        result["covered"] = covered_statements
        result["total"] = total_statements
        result["coverage_pct"] = (covered_statements / total_statements * 100) if total_statements > 0 else 0.0

        logger.info(f"Frontend coverage: {result['coverage_pct']:.2f}% ({result['covered']}/{result['total']} statements)")

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading frontend coverage: {e}")
        result["error"] = str(e)

    return result


def load_mobile_coverage(path):
    """
    Load mobile coverage from jest-expo coverage-final.json format.

    Note: jest-expo uses the same Jest coverage-final.json format as frontend.

    Args:
        path: Path to jest-expo coverage-final.json

    Returns:
        Dict with coverage_pct, covered, total, file_path, error (if applicable)
    """
    result = {
        "coverage_pct": 0.0,
        "covered": 0,
        "total": 0,
        "file_path": str(path),
        "error": None
    }

    if not path.exists():
        logger.warning(f"Mobile coverage file not found: {path}")
        result["error"] = "file not found"
        return result

    try:
        with open(path, 'r') as f:
            data = json.load(f)

        total_statements = 0
        covered_statements = 0

        for file_path, file_data in data.items():
            # Skip node_modules and test files
            if "node_modules" in file_path or "__tests__" in file_path:
                continue

            statements = file_data.get("s", {})
            for stmt_id, count in statements.items():
                total_statements += 1
                if count > 0:
                    covered_statements += 1

        result["covered"] = covered_statements
        result["total"] = total_statements
        result["coverage_pct"] = (covered_statements / total_statements * 100) if total_statements > 0 else 0.0

        logger.info(f"Mobile coverage: {result['coverage_pct']:.2f}% ({result['covered']}/{result['total']} statements)")

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading mobile coverage: {e}")
        result["error"] = str(e)

    return result


def load_desktop_coverage(path):
    """
    Load desktop coverage from tarpaulin coverage.json format.

    Expected schema:
    {
        "files": {
            "path/to/file.rs": {
                "stats": {
                    "covered": 50,
                    "coverable": 100,
                    "percent": 50.0
                }
            }
        }
    }

    Args:
        path: Path to tarpaulin coverage.json

    Returns:
        Dict with coverage_pct, covered, total, file_path, error (if applicable)
    """
    result = {
        "coverage_pct": 0.0,
        "covered": 0,
        "total": 0,
        "file_path": str(path),
        "error": None
    }

    if not path.exists():
        logger.warning(f"Desktop coverage file not found: {path}")
        result["error"] = "file not found"
        return result

    try:
        with open(path, 'r') as f:
            data = json.load(f)

        total_covered = 0
        total_lines = 0

        files = data.get("files", {})
        for file_path, file_data in files.items():
            stats = file_data.get("stats", {})
            total_covered += stats.get("covered", 0)
            total_lines += stats.get("coverable", 0)

        result["covered"] = total_covered
        result["total"] = total_lines
        result["coverage_pct"] = (total_covered / total_lines * 100) if total_lines > 0 else 0.0

        logger.info(f"Desktop coverage: {result['coverage_pct']:.2f}% ({result['covered']}/{result['total']} lines)")

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading desktop coverage: {e}")
        result["error"] = str(e)

    return result


def check_platform_thresholds(
    coverage_data,
    thresholds
):
    """
    Check each platform against its minimum threshold.

    Args:
        coverage_data: Dict mapping platform names to coverage dicts
                       {"backend": {"coverage_pct": 75.0, ...}, ...}
        thresholds: Dict mapping platform names to minimum thresholds
                    {"backend": 70.0, "frontend": 80.0, ...}

    Returns:
        (all_passed, list_of_failure_messages)
    """
    failures = []

    for platform, threshold in thresholds.items():
        if platform not in coverage_data:
            logger.warning(f"Platform '{platform}' not in coverage data, skipping threshold check")
            continue

        platform_data = coverage_data[platform]
        coverage = platform_data.get("coverage_pct", 0.0)

        if coverage < threshold:
            gap = threshold - coverage
            failure_msg = (
                f"{platform.capitalize()}: {coverage:.2f}% < {threshold:.2f}% "
                f"(gap: {gap:.2f}%)"
            )
            failures.append(failure_msg)
            logger.error(failure_msg)

    all_passed = len(failures) == 0
    return all_passed, failures


def compute_weighted_coverage(
    coverage_data,
    weights
):
    """
    Compute weighted overall coverage score.

    Args:
        coverage_data: Dict mapping platform names to coverage dicts
        weights: Dict mapping platform names to weight values

    Returns:
        Dict with overall_pct, platform_breakdown, validation_status
    """
    # Validate weights sum to 1.0 (with tolerance for floating point errors)
    total_weight = sum(weights.values())
    if not (0.99 <= total_weight <= 1.01):
        logger.warning(
            f"Weights sum to {total_weight:.2f}, expected 1.0. "
            f"Results may be inaccurate. Weights: {weights}"
        )

    weighted_sum = 0.0
    platform_breakdown = []

    for platform, weight in weights.items():
        if platform not in coverage_data:
            logger.warning(f"Platform '{platform}' not in coverage data, skipping")
            continue

        platform_data = coverage_data[platform]
        coverage = platform_data.get("coverage_pct", 0.0)
        contribution = coverage * weight
        weighted_sum += contribution

        platform_breakdown.append({
            "platform": platform,
            "coverage_pct": coverage,
            "weight": weight,
            "contribution": contribution
        })

    return {
        "overall_pct": weighted_sum,
        "platform_breakdown": platform_breakdown,
        "validation": {
            "total_weight": total_weight,
            "valid": 0.99 <= total_weight <= 1.01
        }
    }


def generate_text_report(data):
    """Generate human-readable text report."""
    lines = []
    lines.append("=" * 70)
    lines.append("Cross-Platform Coverage Report")
    lines.append("=" * 70)
    lines.append("")

    # Platform breakdown
    lines.append("Platform Coverage:")
    for platform_info in data["weighted"]["platform_breakdown"]:
        platform = platform_info["platform"].capitalize()
        coverage = platform_info["coverage_pct"]
        weight = platform_info["weight"]
        contribution = platform_info["contribution"]
        lines.append(f"  {platform}: {coverage:.2f}% (weight: {weight*100:.0f}%, contribution: {contribution:.2f}%)")

    lines.append("")

    # Overall weighted score
    overall = data["weighted"]["overall_pct"]
    lines.append(f"Overall Weighted Coverage: {overall:.2f}%")
    lines.append("")

    # Threshold checks
    lines.append("Platform Threshold Checks:")
    thresholds = data["thresholds"]
    for platform, threshold in thresholds.items():
        if platform in data["platforms"]:
            platform_data = data["platforms"][platform]
            coverage = platform_data["coverage_pct"]
            passed = coverage >= threshold
            status = "✓ PASS" if passed else "✗ FAIL"
            lines.append(f"  {platform.capitalize():10s}: {coverage:5.2f}% >= {threshold:5.2f}% ... {status}")

    lines.append("")

    # Failures
    if data["threshold_failures"]:
        lines.append("Failed Thresholds:")
        for failure in data["threshold_failures"]:
            lines.append(f"  - {failure}")
        lines.append("")
    else:
        lines.append("All platforms passed minimum thresholds! ✓")
        lines.append("")

    # Timestamp
    lines.append(f"Generated: {data['timestamp']}")
    lines.append("=" * 70)

    return "\n".join(lines)


def generate_json_report(data):
    """Generate machine-readable JSON report."""
    return json.dumps(data, indent=2)


def generate_markdown_report(data):
    """Generate markdown report (PR comment format)."""
    lines = []
    lines.append("## Cross-Platform Coverage Report")
    lines.append("")

    # Overall badge
    overall = data["weighted"]["overall_pct"]
    lines.append(f"### Overall: {overall:.2f}%")
    lines.append("")

    # Platform table
    lines.append("| Platform | Coverage | Weight | Threshold | Status |")
    lines.append("|----------|----------|--------|-----------|--------|")

    thresholds = data["thresholds"]
    for platform_info in data["weighted"]["platform_breakdown"]:
        platform = platform_info["platform"].capitalize()
        coverage = platform_info["coverage_pct"]
        weight = platform_info["weight"]
        threshold = thresholds.get(platform_info["platform"], 0.0)
        passed = coverage >= threshold
        status = "✓" if passed else "✗"

        lines.append(f"| {platform} | {coverage:.2f}% | {weight*100:.0f}% | ≥{threshold:.0f}% | {status} |")

    lines.append("")

    # Failures
    if data["threshold_failures"]:
        lines.append("### Failed Thresholds")
        for failure in data["threshold_failures"]:
            lines.append(f"- {failure}")
        lines.append("")

    lines.append(f"*Generated: {data['timestamp']}*")

    return "\n".join(lines)


def parse_weights_arg(weights_str):
    """Parse weights argument string (e.g., 'backend=0.35,frontend=0.40')."""
    weights = {}
    for pair in weights_str.split(','):
        key, value = pair.split('=')
        weights[key.strip()] = float(value.strip())
    return weights


def parse_thresholds_arg(thresholds_str):
    """Parse thresholds argument string (e.g., 'backend=70,frontend=80')."""
    thresholds = {}
    for pair in thresholds_str.split(','):
        key, value = pair.split('=')
        thresholds[key.strip()] = float(value.strip())
    return thresholds


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Cross-platform coverage enforcement with platform-specific thresholds"
    )

    parser.add_argument(
        "--backend-coverage",
        type=Path,
        default=DEFAULT_BACKEND_COVERAGE,
        help="Path to pytest coverage.json"
    )

    parser.add_argument(
        "--frontend-coverage",
        type=Path,
        default=DEFAULT_FRONTEND_COVERAGE,
        help="Path to Jest coverage-final.json"
    )

    parser.add_argument(
        "--mobile-coverage",
        type=Path,
        default=DEFAULT_MOBILE_COVERAGE,
        help="Path to jest-expo coverage-final.json"
    )

    parser.add_argument(
        "--desktop-coverage",
        type=Path,
        default=DEFAULT_DESKTOP_COVERAGE,
        help="Path to tarpaulin coverage.json"
    )

    parser.add_argument(
        "--weights",
        type=str,
        help="Override default weights (comma-separated: backend=0.35,frontend=0.40,...)"
    )

    parser.add_argument(
        "--thresholds",
        type=str,
        help="Override default thresholds (comma-separated: backend=70,frontend=80,...)"
    )

    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON,
        help="Path for JSON output"
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any platform below threshold"
    )

    args = parser.parse_args()

    # Use custom weights/thresholds if provided
    weights = parse_weights_arg(args.weights) if args.weights else PLATFORM_WEIGHTS.copy()
    thresholds = parse_thresholds_arg(args.thresholds) if args.thresholds else PLATFORM_THRESHOLDS.copy()

    logger.info(f"Using platform weights: {weights}")
    logger.info(f"Using platform thresholds: {thresholds}")

    # Load all platform coverages
    coverage_data = {
        "backend": load_backend_coverage(args.backend_coverage),
        "frontend": load_frontend_coverage(args.frontend_coverage),
        "mobile": load_mobile_coverage(args.mobile_coverage),
        "desktop": load_desktop_coverage(args.desktop_coverage)
    }

    # Check platform thresholds
    all_passed, failures = check_platform_thresholds(coverage_data, thresholds)

    # Compute weighted overall
    weighted_result = compute_weighted_coverage(coverage_data, weights)

    # Build result data
    result = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "platforms": coverage_data,
        "thresholds": thresholds,
        "threshold_failures": failures,
        "all_thresholds_passed": all_passed,
        "weighted": weighted_result
    }

    # Generate report
    if args.format == "text":
        report = generate_text_report(result)
        print(report)
    elif args.format == "json":
        report = generate_json_report(result)
        print(report)
    elif args.format == "markdown":
        report = generate_markdown_report(result)
        print(report)

    # Save JSON output
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, 'w') as f:
        json.dump(result, f, indent=2)
    logger.info(f"JSON report saved to: {args.output_json}")

    # Exit with error code if strict mode and any threshold failed
    if args.strict and not all_passed:
        logger.error("Strict mode: One or more platforms below threshold")
        sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
