#!/usr/bin/env python3
"""
Coverage JSON Parsing Utility

Extracts detailed metrics from coverage.json for CI integration and manual analysis.
Supports multiple output formats: JSON, text, CSV.

Usage:
    python backend/tests/scripts/parse_coverage_json.py [--coverage-file PATH] [--module NAME] [--format FORMAT]

Examples:
    python backend/tests/scripts/parse_coverage_json.py --format json
    python backend/tests/scripts/parse_coverage_json.py --module core.agent_governance_service
    python backend/tests/scripts/parse_coverage_json.py --format csv --output coverage.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List


def load_coverage_json(path: Path) -> Dict[str, Any]:
    """
    Load and parse coverage.json file.

    Args:
        path: Path to coverage.json

    Returns:
        Parsed coverage data dictionary
    """
    if not path.exists():
        raise FileNotFoundError(f"Coverage file not found: {path}")

    with open(path, 'r') as f:
        return json.load(f)


def get_module_coverage(coverage: Dict[str, Any], module_name: str) -> Optional[Dict[str, Any]]:
    """
    Get coverage data for a specific module.

    Args:
        coverage: Coverage data dictionary
        module_name: Module name (e.g., 'core.agent_governance_service' or 'core/agent_governance_service.py')

    Returns:
        Module coverage data or None if not found
    """
    files = coverage.get("files", {})

    # Try exact match first
    if module_name in files:
        return files[module_name]

    # Try with .py extension
    if not module_name.endswith('.py'):
        module_with_py = f"{module_name}.py"
        if module_with_py in files:
            return files[module_with_py]

    # Try converting dots to slashes
    normalized = module_name.replace('.', '/')
    if normalized in files:
        return files[normalized]

    if not normalized.endswith('.py'):
        normalized_with_py = f"{normalized}.py"
        if normalized_with_py in files:
            return files[normalized_with_py]

    # Try partial match
    for file_path, file_data in files.items():
        if module_name.replace('.', '/') in file_path:
            return file_data

    return None


def get_uncovered_lines(coverage: Dict[str, Any], module_name: str) -> List[int]:
    """
    Get uncovered line numbers for a module.

    Args:
        coverage: Coverage data dictionary
        module_name: Module name to query

    Returns:
        List of uncovered line numbers
    """
    module = get_module_coverage(coverage, module_name)

    if not module:
        return []

    return module.get("summary", {}).get("missing_lines", [])


def get_coverage_percentage(coverage: Dict[str, Any], module_name: str) -> float:
    """
    Get coverage percentage for a module.

    Args:
        coverage: Coverage data dictionary
        module_name: Module name to query

    Returns:
        Coverage percentage (0-100)
    """
    module = get_module_coverage(coverage, module_name)

    if not module:
        return 0.0

    return module.get("summary", {}).get("percent_covered", 0.0)


def get_modules_below_threshold(coverage: Dict[str, Any], threshold: float) -> List[tuple[str, float]]:
    """
    Get all modules below coverage threshold.

    Args:
        coverage: Coverage data dictionary
        threshold: Coverage threshold percentage

    Returns:
        List of (module_name, coverage) tuples sorted by coverage
    """
    below_threshold = []

    for file_path, file_data in coverage.get("files", {}).items():
        summary = file_data.get("summary", {})
        percent = summary.get("percent_covered", 0)

        if percent < threshold:
            below_threshold.append((file_path, percent))

    return sorted(below_threshold, key=lambda x: x[1])


def get_branch_coverage(coverage: Dict[str, Any], module_name: str) -> tuple[int, int]:
    """
    Get branch coverage for a module.

    Args:
        coverage: Coverage data dictionary
        module_name: Module name to query

    Returns:
        Tuple of (covered_branches, total_branches)
    """
    module = get_module_coverage(coverage, module_name)

    if not module:
        return (0, 0)

    summary = module.get("summary", {})
    covered = summary.get("covered_branches", 0)
    total = summary.get("num_branches", 0)

    return (covered, total)


def format_as_json(data: Dict[str, Any]) -> str:
    """
    Format coverage data as JSON string.

    Args:
        data: Coverage data to format

    Returns:
        JSON string with pretty printing
    """
    return json.dumps(data, indent=2)


def format_as_csv(coverage: Dict[str, Any]) -> str:
    """
    Format coverage data as CSV string.

    Args:
        coverage: Coverage data dictionary

    Returns:
        CSV formatted string
    """
    import io
    output = io.StringIO()

    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "file_path",
        "line_coverage",
        "covered_lines",
        "total_lines",
        "missing_lines",
        "branch_coverage",
        "covered_branches",
        "total_branches"
    ])

    # Write file data
    for file_path, file_data in coverage.get("files", {}).items():
        summary = file_data.get("summary", {})

        line_cov = summary.get("percent_covered", 0)
        covered = summary.get("covered_lines", 0)
        total = summary.get("num_statements", 0)
        missing = summary.get("missing_lines", 0)

        branch_cov = summary.get("percent_branches_covered", 0)
        branches_covered = summary.get("covered_branches", 0)
        total_branches = summary.get("num_branches", 0)

        writer.writerow([
            file_path,
            f"{line_cov:.2f}",
            covered,
            total,
            missing,
            f"{branch_cov:.2f}",
            branches_covered,
            total_branches
        ])

    return output.getvalue()


def format_as_text(coverage: Dict[str, Any], module_name: Optional[str] = None) -> str:
    """
    Format coverage data as human-readable text.

    Args:
        coverage: Coverage data dictionary
        module_name: Optional module name to filter

    Returns:
        Formatted text string
    """
    lines = []

    if module_name:
        # Single module output
        module = get_module_coverage(coverage, module_name)

        if not module:
            lines.append(f"Module not found: {module_name}")
        else:
            summary = module.get("summary", {})

            lines.append(f"Module: {module_name}")
            lines.append("-" * 60)
            lines.append(f"Line Coverage:   {summary.get('percent_covered', 0):.2f}%")
            lines.append(f"Covered Lines:   {summary.get('covered_lines', 0)} / {summary.get('num_statements', 0)}")
            lines.append(f"Missing Lines:   {len(summary.get('missing_lines', []))}")

            missing = summary.get("missing_branches", [])
            if missing:
                lines.append(f"Missing Branches: {len(missing)}")

            lines.append("")
            lines.append("Uncovered Lines:")
            for line in summary.get("missing_lines", [])[:20]:
                lines.append(f"  {line}")

            if len(summary.get("missing_lines", [])) > 20:
                lines.append(f"  ... and {len(summary.get('missing_lines', [])) - 20} more")
    else:
        # Overall metrics
        totals = coverage.get("totals", {})

        lines.append("=" * 80)
        lines.append("COVERAGE METRICS")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Overall Line Coverage:   {totals.get('percent_covered', 0):.2f}%")
        lines.append(f"Overall Branch Coverage: {totals.get('percent_branches_covered', 0):.2f}%")
        lines.append("")

        # Per-module breakdown
        lines.append("MODULE BREAKDOWN")
        lines.append("-" * 80)

        # Group by module
        by_module = {}
        for file_path, file_data in coverage.get("files", {}).items():
            parts = file_path.split("/")
            module = parts[1] if len(parts) > 1 else "root"

            if module not in by_module:
                by_module[module] = {"files": [], "covered": 0, "total": 0}

            summary = file_data.get("summary", {})
            by_module[module]["files"].append(file_path)
            by_module[module]["covered"] += summary.get("covered_lines", 0)
            by_module[module]["total"] += summary.get("num_statements", 0)

        for module in sorted(by_module.keys()):
            data = by_module[module]
            percent = (data["covered"] / data["total"] * 100) if data["total"] > 0 else 0
            lines.append(f"  {module:20s}  {percent:6.2f}%  ({data['covered']:5d} / {data['total']:5d} lines)")

    return "\n".join(lines)


def main():
    """Main execution entry point."""
    parser = argparse.ArgumentParser(
        description="Parse and query coverage.json for detailed metrics"
    )
    parser.add_argument(
        "--coverage-file",
        type=Path,
        default=Path(__file__).parent.parent / "coverage_reports" / "metrics" / "coverage.json",
        help="Path to coverage.json (default: backend/tests/coverage_reports/metrics/coverage.json)"
    )
    parser.add_argument(
        "--module",
        type=str,
        default=None,
        help="Query specific module (e.g., core.agent_governance_service)"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "text", "csv"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Filter modules below this threshold (only for --format json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file (default: stdout)"
    )

    args = parser.parse_args()

    # Load coverage data
    try:
        coverage = load_coverage_json(args.coverage_file)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return 1

    # Generate output
    if args.format == "json":
        if args.module:
            # Single module JSON output
            module = get_module_coverage(coverage, args.module)
            if module:
                output = format_as_json(module)
            else:
                print(f"Module not found: {args.module}", file=sys.stderr)
                return 1
        elif args.threshold:
            # Modules below threshold
            below = get_modules_below_threshold(coverage, args.threshold)
            output = format_as_json({"below_threshold": below})
        else:
            # Full coverage JSON
            output = format_as_json(coverage)

    elif args.format == "csv":
        output = format_as_csv(coverage)

    else:  # text
        output = format_as_text(coverage, args.module)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Output written to: {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
