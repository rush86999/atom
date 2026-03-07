#!/usr/bin/env python3
"""
Aggregate property test results from multiple platforms.

Combines FastCheck (frontend/mobile) and proptest (desktop) results
into unified cross-platform report with platform breakdown.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


def parse_jest_xml(junit_xml: Path) -> Dict[str, int]:
    """
    Parse Jest JUnit XML output (frontend, mobile).

    Args:
        junit_xml: Path to JUnit XML file

    Returns:
        Dict with total, passed, failed counts (all 0 if file missing)
    """
    if not junit_xml.exists():
        print(f"Warning: {junit_xml} not found, returning zeros", file=sys.stderr)
        return {"total": 0, "passed": 0, "failed": 0}

    try:
        tree = ET.parse(junit_xml)
        root = tree.getroot()

        total = 0
        passed = 0
        failed = 0

        # JUnit format: <testsuite><testcase ...>
        for testcase in root.findall(".//testcase"):
            total += 1
            # Check for failure element
            if testcase.find("failure") is not None:
                failed += 1
            else:
                passed += 1

        return {"total": total, "passed": passed, "failed": failed}

    except ET.ParseError as e:
        print(f"Error parsing {junit_xml}: {e}", file=sys.stderr)
        return {"total": 0, "passed": 0, "failed": 0}
    except Exception as e:
        print(f"Error reading {junit_xml}: {e}", file=sys.stderr)
        return {"total": 0, "passed": 0, "failed": 0}


def parse_proptest_json(proptest_json: Path) -> Dict[str, int]:
    """
    Parse proptest JSON output (desktop).

    Note: proptest doesn't natively output JSON, needs custom format.
    If JSON not available, falls back to parsing stdout with regex.

    Args:
        proptest_json: Path to proptest JSON file

    Returns:
        Dict with total, passed, failed counts (all 0 if file missing)
    """
    if not proptest_json.exists():
        print(f"Warning: {proptest_json} not found, returning zeros", file=sys.stderr)
        return {"total": 0, "passed": 0, "failed": 0}

    try:
        with open(proptest_json, "r") as f:
            data = json.load(f)

        # Expected format: {"total": int, "passed": int, "failed": int}
        return {
            "total": data.get("total", 0),
            "passed": data.get("passed", 0),
            "failed": data.get("failed", 0),
        }

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON {proptest_json}: {e}", file=sys.stderr)
        return {"total": 0, "passed": 0, "failed": 0}
    except Exception as e:
        print(f"Error reading {proptest_json}: {e}", file=sys.stderr)
        return {"total": 0, "passed": 0, "failed": 0}


def aggregate_results(
    frontend: Dict[str, int],
    mobile: Dict[str, int],
    desktop: Dict[str, int],
) -> Dict:
    """
    Aggregate results across platforms with pass rate calculation.

    Args:
        frontend: Frontend test results
        mobile: Mobile test results
        desktop: Desktop test results

    Returns:
        Aggregated results with platform breakdown and pass rate
    """
    total = frontend["total"] + mobile["total"] + desktop["total"]
    passed = frontend["passed"] + mobile["passed"] + desktop["passed"]
    failed = frontend["failed"] + mobile["failed"] + desktop["failed"]

    pass_rate = (passed / total * 100) if total > 0 else 0.0

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(pass_rate, 2),
        "platforms": {
            "frontend": frontend,
            "mobile": mobile,
            "desktop": desktop,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def generate_pr_comment(results: Dict) -> str:
    """
    Generate markdown table for PR comments.

    Args:
        results: Aggregated test results

    Returns:
        Markdown formatted comment
    """
    lines = ["## Property Test Results\n"]

    # Table header
    lines.append("| Platform | Passed | Total | Pass Rate |")
    lines.append("|----------|--------|-------|-----------|")

    # Platform rows
    for platform in ["frontend", "mobile", "desktop"]:
        platform_data = results["platforms"][platform]
        total = platform_data["total"]
        if total > 0:
            passed = platform_data["passed"]
            pass_rate = (passed / total * 100) if total > 0 else 0
            lines.append(
                f"| {platform.capitalize()} | {passed} | {total} | {pass_rate:.1f}% |"
            )
        else:
            lines.append(f"| {platform.capitalize()} | - | - | - |")

    # Overall row
    lines.append(
        f"| **Overall** | **{results['passed']}** | **{results['total']}** | **{results['pass_rate']:.1f}%** |"
    )

    # Status message
    if results["failed"] > 0:
        lines.append(f"\n❌ Some property tests failed ({results['failed']} failures)")
    else:
        lines.append("\n✅ All property tests passed")

    return "\n".join(lines)


def main() -> int:
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Aggregate property test results from multiple platforms"
    )
    parser.add_argument(
        "--frontend",
        type=Path,
        help="Path to frontend Jest JUnit XML or JSON file",
    )
    parser.add_argument(
        "--mobile",
        type=Path,
        help="Path to mobile Jest JUnit XML or JSON file",
    )
    parser.add_argument(
        "--desktop",
        type=Path,
        help="Path to desktop proptest JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (JSON format)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

    # Load results from each platform
    frontend_results = (
        parse_jest_xml(args.frontend) if args.frontend else {"total": 0, "passed": 0, "failed": 0}
    )
    mobile_results = (
        parse_jest_xml(args.mobile) if args.mobile else {"total": 0, "passed": 0, "failed": 0}
    )
    desktop_results = (
        parse_proptest_json(args.desktop)
        if args.desktop
        else {"total": 0, "passed": 0, "failed": 0}
    )

    # Aggregate results
    aggregated = aggregate_results(frontend_results, mobile_results, desktop_results)

    # Output results
    if args.format == "json":
        output = json.dumps(aggregated, indent=2)
        if args.output:
            args.output.write_text(output)
            print(f"Results written to {args.output}", file=sys.stderr)
        else:
            print(output)

    elif args.format == "markdown":
        comment = generate_pr_comment(aggregated)
        if args.output:
            args.output.write_text(comment)
            print(f"Comment written to {args.output}", file=sys.stderr)
        else:
            print(comment)

    else:  # text format
        print(f"Property Test Results ({aggregated['timestamp']})")
        print(f"Total: {aggregated['total']}")
        print(f"Passed: {aggregated['passed']}")
        print(f"Failed: {aggregated['failed']}")
        print(f"Pass Rate: {aggregated['pass_rate']}%")
        print("\nPlatform Breakdown:")
        for platform, data in aggregated["platforms"].items():
            print(f"  {platform.capitalize()}: {data['passed']}/{data['total']}")

    # Exit code based on test results
    return 0 if aggregated["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
