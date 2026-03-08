#!/usr/bin/env python3
"""
Merge Complexity and Coverage Metrics

Combines radon complexity data with pytest coverage data to identify
high-complexity, low-coverage functions (technical debt hotspots).

Usage:
    python merge_complexity_coverage.py --complexity complexity.json --coverage coverage.json
    python merge_complexity_coverage.py --complexity complexity.json --coverage coverage.json --min-complexity 15 --max-coverage 70
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


def load_radon_complexity(complexity_file: Path) -> Dict:
    """Load radon complexity JSON report.

    Args:
        complexity_file: Path to radon cc --json output file

    Returns:
        Nested dict structure: {module_path: {class_name: {method_name: complexity_score}}}
    """
    with open(complexity_file) as f:
        return json.load(f)


def load_coverage_data(coverage_file: Path) -> Dict:
    """Load pytest coverage.json report.

    Args:
        coverage_file: Path to pytest coverage.json file

    Returns:
        Dict mapping file paths to coverage data
    """
    with open(coverage_file) as f:
        coverage_data = json.load(f)

    # Extract files data for easier lookup
    return coverage_data.get("files", {})


def identify_hotspots(
    complexity_data: Dict,
    coverage_data: Dict,
    min_complexity: float = 10.0,
    max_coverage: float = 80.0
) -> List[Dict]:
    """Identify high-complexity, low-coverage functions.

    Args:
        complexity_data: Radon complexity data (nested dict)
        coverage_data: Coverage data (dict from coverage.json)
        min_complexity: Minimum complexity score to flag (default: 10)
        max_coverage: Maximum coverage percentage to flag (default: 80%)

    Returns:
        List of hotspot dicts sorted by complexity (descending)
    """
    hotspots = []

    # Radon format: {"module/path": {"class": {"method": complexity_score}}}
    for module_path, classes in complexity_data.items():
        for class_name, methods in classes.items():
            for method_name, complexity in methods.items():
                # Get coverage for this file
                file_coverage = coverage_data.get(module_path, {})
                file_pct = file_coverage.get("summary", {}).get("percent_covered", 0.0)

                # Flag if high complexity + low coverage
                if complexity > min_complexity and file_pct < max_coverage:
                    # Determine priority
                    priority = "high" if complexity > 20 else "medium"

                    hotspots.append({
                        "file": module_path,
                        "class": class_name,
                        "function": method_name,
                        "complexity": complexity,
                        "coverage": file_pct,
                        "priority": priority
                    })

    # Sort by complexity (descending)
    hotspots.sort(key=lambda x: x["complexity"], reverse=True)
    return hotspots


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Merge complexity and coverage data to identify technical debt hotspots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python merge_complexity_coverage.py --complexity complexity.json --coverage coverage.json

  # Custom thresholds
  python merge_complexity_coverage.py --complexity complexity.json --coverage coverage.json \\
    --min-complexity 15 --max-coverage 70

  # Specify output file
  python merge_complexity_coverage.py --complexity complexity.json --coverage coverage.json \\
    --output quality_metrics.json
        """
    )

    parser.add_argument(
        "--complexity",
        type=Path,
        required=True,
        help="Path to radon cc --json output file"
    )

    parser.add_argument(
        "--coverage",
        type=Path,
        required=True,
        help="Path to pytest coverage.json file"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default="quality_metrics.json",
        help="Output JSON file path (default: quality_metrics.json)"
    )

    parser.add_argument(
        "--min-complexity",
        type=float,
        default=10.0,
        help="Minimum complexity score to flag (default: 10.0)"
    )

    parser.add_argument(
        "--max-coverage",
        type=float,
        default=80.0,
        help="Maximum coverage percentage to flag (default: 80.0)"
    )

    args = parser.parse_args()

    # Validate input files exist
    if not args.complexity.exists():
        print(f"ERROR: Complexity file not found: {args.complexity}", file=sys.stderr)
        return 2

    if not args.coverage.exists():
        print(f"ERROR: Coverage file not found: {args.coverage}", file=sys.stderr)
        return 2

    # Load data
    try:
        complexity_data = load_radon_complexity(args.complexity)
        coverage_data = load_coverage_data(args.coverage)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in input file: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: Failed to load input files: {e}", file=sys.stderr)
        return 2

    # Identify hotspots
    hotspots = identify_hotspots(
        complexity_data,
        coverage_data,
        min_complexity=args.min_complexity,
        max_coverage=args.max_coverage
    )

    # Generate output
    high_priority_count = sum(1 for h in hotspots if h["priority"] == "high")
    medium_priority_count = sum(1 for h in hotspots if h["priority"] == "medium")

    output = {
        "hotspots": hotspots,
        "summary": {
            "total_hotspots": len(hotspots),
            "high_priority": high_priority_count,
            "medium_priority": medium_priority_count,
            "thresholds": {
                "min_complexity": args.min_complexity,
                "max_coverage": args.max_coverage
            }
        }
    }

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"\nComplexity/Coverage Hotspot Analysis")
    print(f"=" * 50)
    print(f"Total hotspots: {len(hotspots)}")
    print(f"High priority (complexity >20): {high_priority_count}")
    print(f"Medium priority (complexity 10-20): {medium_priority_count}")
    print(f"Output written to: {args.output}")

    if hotspots:
        print(f"\nTop 10 Hotspots:")
        for spot in hotspots[:10]:
            print(f"  - {spot['file']}::{spot['class']}.{spot['function']} "
                  f"(complexity={spot['complexity']}, coverage={spot['coverage']:.1f}%, "
                  f"priority={spot['priority']})")
        if len(hotspots) > 10:
            print(f"  ... and {len(hotspots) - 10} more")

    # Exit code: 0 if no hotspots, 1 if hotspots found
    return 0 if len(hotspots) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
