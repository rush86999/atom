#!/usr/bin/env python3
"""
Crash Report Aggregation Script

This script aggregates crash reports from multiple fuzzing campaigns,
generates markdown and JSON reports with crash statistics and trends.

Usage:
    python aggregate_crash_reports.py --crash-dirs "backend/tests/fuzzing/campaigns/crashes/*"
    python aggregate_crash_reports.py --crash-dirs "crashes/*" --output report.md

Environment Variables:
    None
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tests.fuzzing.campaigns.crash_deduplicator import CrashDeduplicator


def aggregate_crashes(crash_dirs: List[Path]) -> Dict[str, List[Path]]:
    """
    Aggregate crashes from multiple campaign directories.

    Args:
        crash_dirs: List of crash directory paths

    Returns:
        Dict mapping signature_hash to list of crash files
    """
    deduplicator = CrashDeduplicator()
    crashes_by_signature = {}

    for crash_dir in crash_dirs:
        if not crash_dir.exists():
            print(f"Warning: Crash directory not found: {crash_dir}")
            continue

        print(f"Aggregating crashes from: {crash_dir}")

        # Deduplicate crashes in this directory
        dir_crashes = deduplicator.deduplicate_crashes(crash_dir)

        # Merge into overall crashes_by_signature
        for signature_hash, crash_files in dir_crashes.items():
            if signature_hash not in crashes_by_signature:
                crashes_by_signature[signature_hash] = []

            crashes_by_signature[signature_hash].extend(crash_files)

    return crashes_by_signature


def generate_report(crashes_by_signature: Dict[str, List[Path]], output_path: str, crash_dirs: List[Path] = None):
    """
    Generate markdown and JSON crash reports.

    Args:
        crashes_by_signature: Dict mapping signature_hash to list of crash files
        output_path: Path to output markdown report
        crash_dirs: List of crash directories (for context)
    """
    # Calculate statistics
    total_crashes = sum(len(files) for files in crashes_by_signature.values())
    unique_crashes = len(crashes_by_signature)

    # Group crashes by endpoint (extract from directory name)
    crashes_by_endpoint = {}
    for signature_hash, crash_files in crashes_by_signature.items():
        for crash_file in crash_files:
            # Extract endpoint from path: .../crashes/POST_api_auth_login_2026-03-24/*.input
            dir_name = crash_file.parent.name
            # Parse endpoint from directory name (remove timestamp)
            parts = dir_name.split("_")
            endpoint_parts = []
            for part in parts:
                if part.isdigit() or part.startswith("2026-"):
                    break
                endpoint_parts.append(part)

            endpoint = "_".join(endpoint_parts).replace("_", " ")

            if endpoint not in crashes_by_endpoint:
                crashes_by_endpoint[endpoint] = {"files": [], "unique_signatures": set()}

            crashes_by_endpoint[endpoint]["files"].extend(crash_files)
            crashes_by_endpoint[endpoint]["unique_signatures"].add(signature_hash)

    # Get top crash signatures by frequency
    signature_summary = []
    for signature_hash, crash_files in crashes_by_signature.items():
        signature_summary.append({
            "signature_hash": signature_hash,
            "count": len(crash_files),
            "example_crash": str(crash_files[0])
        })

    signature_summary.sort(key=lambda x: x["count"], reverse=True)

    # Generate markdown report
    markdown_lines = []
    markdown_lines.append("# Fuzzing Crash Report")
    markdown_lines.append("")
    markdown_lines.append(f"**Generated:** {datetime.utcnow().isoformat()}Z")
    markdown_lines.append("")

    # Summary section
    markdown_lines.append("## Summary")
    markdown_lines.append("")
    markdown_lines.append(f"- **Total crashes:** {total_crashes}")
    markdown_lines.append(f"- **Unique crashes:** {unique_crashes}")
    markdown_lines.append(f"- **Affected endpoints:** {len(crashes_by_endpoint)}")
    markdown_lines.append("")

    # Crashes by endpoint
    markdown_lines.append("## Crashes by Endpoint")
    markdown_lines.append("")
    for endpoint, data in sorted(crashes_by_endpoint.items()):
        total = len(data["files"])
        unique = len(data["unique_signatures"])
        markdown_lines.append(f"### {endpoint}")
        markdown_lines.append("")
        markdown_lines.append(f"- Total crashes: {total}")
        markdown_lines.append(f"- Unique crashes: {unique}")
        markdown_lines.append("")

    # Top crash signatures
    markdown_lines.append("## Top Crash Signatures")
    markdown_lines.append("")
    for i, sig in enumerate(signature_summary[:20], 1):
        markdown_lines.append(f"### {i}. Signature: `{sig['signature_hash'][:16]}...`")
        markdown_lines.append("")
        markdown_lines.append(f"- **Frequency:** {sig['count']} crashes")
        markdown_lines.append(f"- **Example:** `{sig['example_crash']}`")
        markdown_lines.append("")

    # Bug filing status
    markdown_lines.append("## Bug Filing Status")
    markdown_lines.append("")
    markdown_lines.append("Bug filing status is tracked by GitHub issues created via BugFilingService.")
    markdown_lines.append("Check GitHub repository for filed bugs with label `bug-discovery`.")
    markdown_lines.append("")

    # Trend analysis (if baseline exists)
    if crash_dirs:
        markdown_lines.append("## Trend Analysis")
        markdown_lines.append("")
        markdown_lines.append(f"Crash directories analyzed: {len(crash_dirs)}")
        markdown_lines.append("")
        for crash_dir in crash_dirs:
            markdown_lines.append(f"- `{crash_dir}`")
        markdown_lines.append("")
        markdown_lines.append("*Trend comparison with previous week requires baseline data.*")
        markdown_lines.append("")

    # Write markdown report
    with open(output_path, "w") as f:
        f.write("\n".join(markdown_lines))

    print(f"Markdown report generated: {output_path}")

    # Generate JSON summary
    json_output_path = output_path.replace(".md", ".json")
    json_data = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_crashes": total_crashes,
            "unique_crashes": unique_crashes,
            "affected_endpoints": len(crashes_by_endpoint)
        },
        "crashes_by_endpoint": {
            endpoint: {
                "total_crashes": len(data["files"]),
                "unique_crashes": len(data["unique_signatures"])
            }
            for endpoint, data in crashes_by_endpoint.items()
        },
        "top_signatures": signature_summary[:20]
    }

    with open(json_output_path, "w") as f:
        json.dump(json_data, f, indent=2)

    print(f"JSON summary generated: {json_output_path}")

    # Print summary to stdout
    print("\n" + "="*60)
    print("Crash Aggregation Summary")
    print("="*60)
    print(f"Total crashes: {total_crashes}")
    print(f"Unique crashes: {unique_crashes}")
    print(f"Affected endpoints: {len(crashes_by_endpoint)}")
    print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Aggregate crash reports from fuzzing campaigns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Aggregate crashes from all campaign directories
  python aggregate_crash_reports.py --crash-dirs "backend/tests/fuzzing/campaigns/crashes/*"

  # Specify output file
  python aggregate_crash_reports.py --crash-dirs "crashes/*" --output /tmp/report.md

  # Multiple directories
  python aggregate_crash_reports.py --crash-dirs "crashes/*" --crash-dirs "old/crashes/*"
        """
    )

    parser.add_argument(
        "--crash-dirs",
        action="append",
        required=True,
        help="Glob pattern for crash directories (can be specified multiple times)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="fuzzing-report.md",
        help="Output report path (default: fuzzing-report.md)"
    )

    args = parser.parse_args()

    # Expand glob patterns
    crash_dirs = []
    for pattern in args.crash_dirs:
        expanded = glob.glob(pattern)
        if not expanded:
            print(f"Warning: No directories found for pattern: {pattern}")
        crash_dirs.extend([Path(d) for d in expanded])

    if not crash_dirs:
        print("Error: No crash directories found")
        sys.exit(1)

    print(f"Found {len(crash_dirs)} crash directory(s)")

    # Aggregate crashes
    crashes_by_signature = aggregate_crashes(crash_dirs)

    if not crashes_by_signature:
        print("No crashes found in any directory")
        # Generate empty report
        generate_report({}, args.output, crash_dirs)
        sys.exit(0)

    # Generate report
    generate_report(crashes_by_signature, args.output, crash_dirs)

    # Exit code: 0 if success, 1 if no crashes
    total_crashes = sum(len(files) for files in crashes_by_signature.values())
    if total_crashes == 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
