#!/usr/bin/env python3
"""
Coverage-to-Prioritization Wrapper Script (Phase 292)

Purpose: Convert raw pytest coverage.json into the files_below_threshold format
expected by prioritize_high_impact_files.py, run prioritization, post-process into
3 tiers (Tier 1: <10%, Tier 2: 10-30%, Tier 3: 30-50%, all >200 lines), and
write both JSON and Markdown output.

Usage:
    python tests/scripts/coverage_to_prioritize.py \
        --coverage-file tests/coverage_reports/metrics/phase_292_backend_baseline.json \
        --output-dir tests/coverage_reports/metrics/ \
        --markdown-dir tests/coverage_reports/

Output:
    - {output_dir}/prioritized_files_v11.0.json: Machine-readable ranked files by tier
    - {markdown_dir}/HIGH_IMPACT_PRIORITIZATION_v11.0.md: Human-readable report

Dependencies:
    - prioritize_high_impact_files.py (existing prioritization engine)
    - business_impact_scores.json (authoritative impact tiers, D-06)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


# =============================================================================
# TIER DEFINITIONS (per D-04)
# =============================================================================

TIER_DEFINITIONS = {
    "Tier 1 (must-fix)": {
        "min_coverage": 0.0,
        "max_coverage": 10.0,
        "description": "< 10% coverage, > 200 lines (highest impact)",
    },
    "Tier 2 (should-fix)": {
        "min_coverage": 10.0,
        "max_coverage": 30.0,
        "description": "10-30% coverage, > 200 lines",
    },
    "Tier 3 (nice-to-fix)": {
        "min_coverage": 30.0,
        "max_coverage": 50.0,
        "description": "30-50% coverage, > 200 lines",
    },
}

TIER_THRESHOLDS = [
    ("Tier 1 (must-fix)", 0.0, 10.0),
    ("Tier 2 (should-fix)", 10.0, 30.0),
    ("Tier 3 (nice-to-fix)", 30.0, 50.0),
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert raw coverage.json to prioritized tiered file list"
    )
    parser.add_argument(
        "--coverage-file",
        type=Path,
        required=True,
        help="Path to raw coverage.json (e.g., phase_292_backend_baseline.json)",
    )
    parser.add_argument(
        "--impact-file",
        type=Path,
        default=Path("tests/coverage_reports/metrics/business_impact_scores.json"),
        help="Path to business_impact_scores.json (default: tests/coverage_reports/metrics/business_impact_scores.json)",
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=200,
        help="Minimum lines of code to include (default: 200, per D-06)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/coverage_reports/metrics/"),
        help="Output directory for JSON files (default: tests/coverage_reports/metrics/)",
    )
    parser.add_argument(
        "--markdown-dir",
        type=Path,
        default=Path("tests/coverage_reports/"),
        help="Output directory for Markdown reports (default: tests/coverage_reports/)",
    )
    return parser.parse_args()


def load_coverage_json(path: Path) -> Dict[str, Any]:
    """Load and validate coverage JSON file."""
    with open(path, "r") as f:
        data = json.load(f)

    # Validate structure
    assert "files" in data, "coverage.json missing 'files' key"
    assert "totals" in data, "coverage.json missing 'totals' key"

    return data


def convert_to_baseline_format(
    coverage_data: Dict[str, Any],
    min_lines: int = 200,
) -> List[Dict[str, Any]]:
    """
    Convert raw coverage.json files dict into files_below_threshold format.

    Each file entry:
        file, coverage_pct, total_lines, covered_lines, uncovered_lines

    Only includes files with total_lines >= min_lines.
    """
    files_below = []
    files = coverage_data.get("files", {})

    for filepath, file_info in files.items():
        summary = file_info.get("summary", {})
        num_statements = summary.get("num_statements", 0)

        # Filter by minimum lines (per D-06)
        if num_statements < min_lines:
            continue

        percent_covered = summary.get("percent_covered", 0.0)
        covered_lines = summary.get("covered_lines", 0)
        uncovered_lines = num_statements - covered_lines

        files_below.append({
            "file": filepath,
            "coverage_pct": round(percent_covered, 2),
            "total_lines": num_statements,
            "covered_lines": covered_lines,
            "uncovered_lines": uncovered_lines,
        })

    return files_below


def post_process_into_tiers(
    raw_ranked: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Post-process ranked files into 3 tiers by coverage threshold.

    Tier 1: coverage_pct < 10
    Tier 2: 10 <= coverage_pct < 30
    Tier 3: 30 <= coverage_pct < 50

    Within each tier, files retain their priority_score descending sort.
    """
    tiers: Dict[str, List[Dict[str, Any]]] = {
        "Tier 1 (must-fix)": [],
        "Tier 2 (should-fix)": [],
        "Tier 3 (nice-to-fix)": [],
    }

    for entry in raw_ranked:
        coverage_pct = entry.get("coverage_pct", 0.0)

        if coverage_pct < 10.0:
            tiers["Tier 1 (must-fix)"].append(entry)
        elif coverage_pct < 30.0:
            tiers["Tier 2 (should-fix)"].append(entry)
        elif coverage_pct < 50.0:
            tiers["Tier 3 (nice-to-fix)"].append(entry)
        # Files >= 50% are excluded from the output

    # Ensure each tier is sorted by priority_score descending
    for tier_key in tiers:
        tiers[tier_key].sort(key=lambda x: x.get("priority_score", 0), reverse=True)

    return tiers


def assign_tier_label(coverage_pct: float) -> str:
    """Assign a tier label based on coverage percentage."""
    if coverage_pct < 10.0:
        return "Tier 1 (must-fix)"
    elif coverage_pct < 30.0:
        return "Tier 2 (should-fix)"
    elif coverage_pct < 50.0:
        return "Tier 3 (nice-to-fix)"
    return "Tier 3 (nice-to-fix)"  # fallback


def write_json_output(
    tiered_files: Dict[str, List[Dict[str, Any]]],
    coverage_path: Path,
    output_path: Path,
) -> None:
    """Write the final tiered JSON output with summary."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Calculate summary
    total_files = sum(len(files) for files in tiered_files.values())
    total_uncovered = sum(
        entry.get("uncovered_lines", 0)
        for files in tiered_files.values()
        for entry in files
    )

    tier_counts = {}
    for tier_key, files in tiered_files.items():
        tier_counts[tier_key] = len(files)

    # Get top 3 files overall by priority_score
    all_files = []
    for files in tiered_files.values():
        all_files.extend(files)
    all_files.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    top_3 = [f.get("file", "") for f in all_files[:3]]

    output = {
        "generated_at": timestamp,
        "baseline_source": coverage_path.name,
        "formula": "priority_score = (uncovered_lines * impact_score) / (coverage_pct + 1)",
        "tier_definitions": {
            "Tier 1 (must-fix)": TIER_DEFINITIONS["Tier 1 (must-fix)"]["description"],
            "Tier 2 (should-fix)": TIER_DEFINITIONS["Tier 2 (should-fix)"]["description"],
            "Tier 3 (nice-to-fix)": TIER_DEFINITIONS["Tier 3 (nice-to-fix)"]["description"],
        },
        "summary": {
            "total_files_prioritized": total_files,
            "tier_1_count": tier_counts.get("Tier 1 (must-fix)", 0),
            "tier_2_count": tier_counts.get("Tier 2 (should-fix)", 0),
            "tier_3_count": tier_counts.get("Tier 3 (nice-to-fix)", 0),
            "total_uncovered_lines": total_uncovered,
            "top_3_files": top_3,
        },
        "tier_1": tiered_files.get("Tier 1 (must-fix)", []),
        "tier_2": tiered_files.get("Tier 2 (should-fix)", []),
        "tier_3": tiered_files.get("Tier 3 (nice-to-fix)", []),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  JSON report written to {output_path}")
    print(f"    T1={len(output['tier_1'])} T2={len(output['tier_2'])} T3={len(output['tier_3'])}")


def write_markdown_output(
    tiered_files: Dict[str, List[Dict[str, Any]]],
    coverage_path: Path,
    output_path: Path,
    all_quick_wins: List[Dict[str, Any]],
) -> None:
    """Write the human-readable Markdown prioritization report."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    total_files = sum(len(files) for files in tiered_files.values())
    total_uncovered = sum(
        entry.get("uncovered_lines", 0)
        for files in tiered_files.values()
        for entry in files
    )

    lines = []

    # Title and metadata
    lines.append("# High-Impact File Prioritization v11.0")
    lines.append("")
    lines.append(f"**Generated**: {timestamp}")
    lines.append("**Phase**: 292-02")
    lines.append("**Baseline**: {coverage_path.name}")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- **Total files prioritized (>200 lines, <50% coverage)**: {total_files}")
    lines.append(f"- **Total uncovered lines**: {total_uncovered:,}")
    lines.append("")
    lines.append("| Tier | Files | Definition |")
    lines.append("|------|-------|------------|")
    for tier_key, files in tiered_files.items():
        lines.append(f"| {tier_key} | {len(files)} | {TIER_DEFINITIONS[tier_key]['description']} |")
    lines.append("")

    # Tier Definitions
    lines.append("## Tier Definitions")
    lines.append("")
    lines.append("| Tier | Coverage Range | Min Lines | Priority |")
    lines.append("|------|---------------|-----------|----------|")
    lines.append("| Tier 1 (must-fix) | < 10% | > 200 | Highest - maximize coverage gain per test |")
    lines.append("| Tier 2 (should-fix) | 10-30% | > 200 | High - significant improvement possible |")
    lines.append("| Tier 3 (nice-to-fix) | 30-50% | > 200 | Moderate - incremental gains |")
    lines.append("")

    # Tier 1 Section
    lines.append("## Tier 1 (must-fix): < 10% Coverage, > 200 Lines")
    lines.append("")
    t1_files = tiered_files.get("Tier 1 (must-fix)", [])
    lines.append(f"**{len(t1_files)} files** — {sum(f.get('uncovered_lines', 0) for f in t1_files):,} uncovered lines")
    lines.append("")
    if t1_files:
        lines.append("| Rank | File | Coverage% | Uncovered | Impact | Priority Score | Business Tier |")
        lines.append("|------|------|-----------|-----------|--------|----------------|---------------|")
        for i, f in enumerate(t1_files, 1):
            lines.append(
                f"| {i} | {f['file']} | {f['coverage_pct']:.2f}% | {f['uncovered_lines']} | "
                f"{f['impact_score']} | {f['priority_score']:.2f} | {f['tier']} |"
            )
        lines.append("")

    # Tier 2 Section
    lines.append("## Tier 2 (should-fix): 10-30% Coverage, > 200 Lines")
    lines.append("")
    t2_files = tiered_files.get("Tier 2 (should-fix)", [])
    lines.append(f"**{len(t2_files)} files** — {sum(f.get('uncovered_lines', 0) for f in t2_files):,} uncovered lines")
    lines.append("")
    if t2_files:
        lines.append("| Rank | File | Coverage% | Uncovered | Impact | Priority Score | Business Tier |")
        lines.append("|------|------|-----------|-----------|--------|----------------|---------------|")
        for i, f in enumerate(t2_files, 1):
            lines.append(
                f"| {i} | {f['file']} | {f['coverage_pct']:.2f}% | {f['uncovered_lines']} | "
                f"{f['impact_score']} | {f['priority_score']:.2f} | {f['tier']} |"
            )
        lines.append("")

    # Tier 3 Section (top 20 only)
    lines.append("## Tier 3 (nice-to-fix): 30-50% Coverage, > 200 Lines")
    lines.append("")
    t3_files = tiered_files.get("Tier 3 (nice-to-fix)", [])
    lines.append(f"**{len(t3_files)} files** — {sum(f.get('uncovered_lines', 0) for f in t3_files):,} uncovered lines")
    lines.append("")
    display_t3 = t3_files[:20]
    if display_t3:
        lines.append("| Rank | File | Coverage% | Uncovered | Impact | Priority Score | Business Tier |")
        lines.append("|------|------|-----------|-----------|--------|----------------|---------------|")
        for i, f in enumerate(display_t3, 1):
            lines.append(
                f"| {i} | {f['file']} | {f['coverage_pct']:.2f}% | {f['uncovered_lines']} | "
                f"{f['impact_score']} | {f['priority_score']:.2f} | {f['tier']} |"
            )
        if len(t3_files) > 20:
            lines.append(f"")
            lines.append(f"*Showing top 20 of {len(t3_files)} files*")
        lines.append("")

    # Priority Score Formula
    lines.append("## Priority Score Formula")
    lines.append("")
    lines.append("```")
    lines.append("priority_score = (uncovered_lines * impact_score) / (coverage_pct + 1)")
    lines.append("```")
    lines.append("")
    lines.append("### Why This Formula?")
    lines.append("")
    lines.append("- **uncovered_lines**: More uncovered lines = more potential coverage gain")
    lines.append("- **impact_score**: Higher business impact = more value per test")
    lines.append(r"- **current_coverage_pct + 1**: Lower current coverage = higher priority")
    lines.append("  - Adding 1 prevents division by zero for 0% coverage files")
    lines.append("  - This creates a \"quick wins\" bias towards files with very low coverage")
    lines.append("")
    lines.append("### Impact Score Mapping")
    lines.append("")
    lines.append("| Business Tier | Score |")
    lines.append("|---------------|-------|")
    lines.append("| Critical | 10 |")
    lines.append("| High | 7 |")
    lines.append("| Medium | 5 |")
    lines.append("| Low | 3 |")
    lines.append("")

    # Quick Wins
    lines.append("## Quick Wins (0% Coverage AND Critical/High Business Impact)")
    lines.append("")
    if all_quick_wins:
        lines.append(f"These {len(all_quick_wins)} files have **zero coverage** but Critical or High business impact.")
        lines.append("")
        lines.append("| Rank | File | Uncovered Lines | Impact Score | Business Tier |")
        lines.append("|------|------|-----------------|--------------|---------------|")
        for i, f in enumerate(all_quick_wins, 1):
            lines.append(
                f"| {i} | {f['file']} | {f['uncovered_lines']} | "
                f"{f['impact_score']} | {f['tier']} |"
            )
    else:
        lines.append("No files with 0% coverage AND Critical/High business impact found.")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by coverage_to_prioritize.py*")
    lines.append("*Phase: 292-02*")
    lines.append(f"*Timestamp: {timestamp}*")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"  Markdown report written to {output_path}")


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Resolve paths relative to the script's expected working directory (backend/)
    script_dir = Path(__file__).resolve().parent.parent.parent  # backend/
    coverage_path = args.coverage_file
    if not coverage_path.is_absolute():
        coverage_path = script_dir / coverage_path

    impact_path = args.impact_file
    if not impact_path.is_absolute():
        impact_path = script_dir / impact_path

    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = script_dir / output_dir

    markdown_dir = args.markdown_dir
    if not markdown_dir.is_absolute():
        markdown_dir = script_dir / markdown_dir

    print("=" * 60)
    print("PHASE 292-02: BACKEND PRIORITIZATION WRAPPER")
    print("=" * 60)

    # Step 1: Load coverage.json
    print(f"\n[1/6] Loading coverage data from {coverage_path}...")
    coverage_data = load_coverage_json(coverage_path)
    print(f"  Found {len(coverage_data.get('files', {}))} files in coverage report")

    # Step 2: Convert to baseline format
    print(f"\n[2/6] Converting to baseline format (min_lines={args.min_lines})...")
    files_below = convert_to_baseline_format(coverage_data, args.min_lines)
    print(f"  {len(files_below)} files have >= {args.min_lines} lines")

    # Step 3: Write interim file
    print(f"\n[3/6] Writing interim baseline JSON...")
    interim = {
        "files_below_threshold": files_below,
    }
    interim_path = output_dir / "prioritize_input.json"
    interim_path.parent.mkdir(parents=True, exist_ok=True)
    with open(interim_path, "w") as f:
        json.dump(interim, f, indent=2)
    print(f"  Interim file written to {interim_path}")

    # Step 4: Invoke prioritize_high_impact_files.py
    print(f"\n[4/6] Invoking prioritize_high_impact_files.py...")
    prioritized_raw_json = output_dir / "prioritized_raw.json"
    temp_md = markdown_dir / "_temp_prioritization.md"

    prioritize_script = script_dir / "tests/scripts/prioritize_high_impact_files.py"
    if not prioritize_script.exists():
        print(f"ERROR: {prioritize_script} not found")
        return 1

    cmd = [
        sys.executable,
        str(prioritize_script),
        "--baseline", str(interim_path),
        "--impact", str(impact_path),
        "--output", str(prioritized_raw_json),
        "--report", str(temp_md),
        "--min-coverage", "50",
        "--quick-wins", "20",
    ]

    print(f"  Running: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(script_dir))

    if result.returncode != 0:
        print(f"ERROR: prioritize_high_impact_files.py failed with code {result.returncode}")
        print(f"STDERR: {result.stderr}")
        print(f"STDOUT: {result.stdout}")
        return 1

    print(f"  {result.stdout.strip()}")

    # Load raw prioritized output
    with open(prioritized_raw_json, "r") as f:
        raw_data = json.load(f)

    raw_ranked = raw_data.get("ranked_files", [])
    print(f"  Raw ranked files: {len(raw_ranked)}")

    # Step 5: Post-process into 3 tiers
    print(f"\n[5/6] Post-processing into 3 tiers (per D-04)...")
    tiered = post_process_into_tiers(raw_ranked)
    for tier_key, files in tiered.items():
        print(f"  {tier_key}: {len(files)} files")

    # Identify quick wins (0% coverage AND Critical/High tier)
    all_quick_wins = [
        f for f in raw_ranked
        if f.get("coverage_pct", 100) == 0.0
        and f.get("tier") in ["Critical", "High"]
    ]
    all_quick_wins.sort(key=lambda x: x.get("uncovered_lines", 0), reverse=True)
    print(f"  Quick wins (0% coverage, Critical/High): {len(all_quick_wins)}")

    # Step 6: Write output files
    print(f"\n[6/6] Writing output files...")
    json_output = output_dir / "prioritized_files_v11.0.json"
    write_json_output(tiered, coverage_path, json_output)

    md_output = markdown_dir / "HIGH_IMPACT_PRIORITIZATION_v11.0.md"
    write_markdown_output(tiered, coverage_path, md_output, all_quick_wins)

    # Cleanup temporary files
    interim_path.unlink(missing_ok=True)
    prioritized_raw_json.unlink(missing_ok=True)
    temp_md.unlink(missing_ok=True)

    print(f"\n{'=' * 60}")
    print("BACKEND PRIORITIZATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Output JSON:   {json_output}")
    print(f"  Output MD:     {md_output}")
    print(f"  Tier 1 count:  {len(tiered.get('Tier 1 (must-fix)', []))}")
    print(f"  Tier 2 count:  {len(tiered.get('Tier 2 (should-fix)', []))}")
    print(f"  Tier 3 count:  {len(tiered.get('Tier 3 (nice-to-fix)', []))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
