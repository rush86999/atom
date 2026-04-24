#!/usr/bin/env python3
"""
Frontend Component Prioritization Script (Phase 292)

Purpose: Prioritize frontend components by BUSINESS CRITICALITY first (D-07),
with coverage percentage as a secondary factor. Uses the same priority_score
formula as the backend for consistency (D-05 spirit).

Criticality tiers per D-07:
    Critical (score=10): Canvas, Chat, Agent Dashboard
    High (score=7):      Integrations
    Medium (score=5):    UI components, pages, lib
    Low (score=3):       Hooks, shared

Usage:
    python tests/scripts/prioritize_frontend_components.py \
        --coverage-file /path/to/frontend-nextjs/coverage/coverage-final.json \
        --output-dir /path/to/frontend-nextjs/coverage/

Output:
    - {output_dir}/prioritized_frontend_components_v11.0.json
    - {output_dir}/HIGH_IMPACT_FRONTEND_COMPONENTS_v11.0.md
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# BUSINESS CRITICALITY TIERS (per D-07)
# =============================================================================

CRITICALITY_TIERS = {
    "Critical": {
        "patterns": ["components/canvas/", "components/chat/", "components/agent-dashboard/"],
        "description": "Core user-facing features (Canvas presentations, Chat interface, Agent Dashboard)",
        "score": 10,
    },
    "High": {
        "patterns": ["components/integrations/"],
        "description": "Integration components (WhatsApp, Slack, etc.)",
        "score": 7,
    },
    "Medium": {
        "patterns": ["components/ui/", "pages/", "lib/"],
        "description": "UI components, page layouts, utility libraries",
        "score": 5,
    },
    "Low": {
        "patterns": ["hooks/", "shared/"],
        "description": "Custom hooks, shared utilities",
        "score": 3,
    },
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Prioritize frontend components by business criticality"
    )
    parser.add_argument(
        "--coverage-file",
        type=Path,
        required=True,
        help="Path to frontend coverage-final.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for JSON and Markdown files (default: same dir as coverage-file)",
    )
    parser.add_argument(
        "--markdown-dir",
        type=Path,
        default=None,
        help="Output directory for Markdown report (default: same as output-dir)",
    )
    return parser.parse_args()


def load_coverage_json(path: Path) -> Dict[str, Any]:
    """Load and validate frontend coverage JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    assert "total" in data, "coverage-final.json missing 'total' key"
    return data


def determine_criticality(filepath: str) -> Tuple[str, int]:
    """
    Determine the business criticality tier for a filepath.

    Checks patterns in priority order: Critical -> High -> Medium -> Low.
    Returns (tier_name, score).
    """
    filepath_lower = filepath.lower()

    # Check Critical first (most specific patterns)
    for pattern in CRITICALITY_TIERS["Critical"]["patterns"]:
        if pattern in filepath_lower:
            return "Critical", CRITICALITY_TIERS["Critical"]["score"]

    # Check High
    for pattern in CRITICALITY_TIERS["High"]["patterns"]:
        if pattern in filepath_lower:
            return "High", CRITICALITY_TIERS["High"]["score"]

    # Check Medium
    for pattern in CRITICALITY_TIERS["Medium"]["patterns"]:
        if pattern in filepath_lower:
            return "Medium", CRITICALITY_TIERS["Medium"]["score"]

    # Check Low
    for pattern in CRITICALITY_TIERS["Low"]["patterns"]:
        if pattern in filepath_lower:
            return "Low", CRITICALITY_TIERS["Low"]["score"]

    # Default
    return "Medium", CRITICALITY_TIERS["Medium"]["score"]


def calculate_priority_score(uncovered_lines: float, impact_score: int, coverage_pct: float) -> float:
    """
    Calculate priority score using the same formula as backend (D-05 spirit).

    Formula: priority_score = (uncovered_lines * impact_score) / (coverage_pct + 1)
    The +1 prevents division by zero for 0% coverage files.
    """
    return round((uncovered_lines * impact_score) / (coverage_pct + 1), 2)


def process_coverage_data(
    coverage_data: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process frontend coverage data into by-criticality groups.

    Each file entry:
        file, coverage_pct, total_lines, covered_lines, uncovered_lines,
        criticality_tier, criticality_score, priority_score

    Sorting: primary=criticality_score desc, secondary=priority_score desc,
    tertiary=total_lines desc.
    """
    by_criticality: Dict[str, List[Dict[str, Any]]] = {
        "Critical": [],
        "High": [],
        "Medium": [],
        "Low": [],
    }

    # Determine root directory to strip from absolute paths
    # Coverage summary JSON uses absolute paths like /Users/.../frontend-nextjs/components/...
    root_markers = ["/frontend-nextjs/", "/atom/"]
    strip_prefix = ""
    for filepath in coverage_data:
        if filepath in ("total", "meta"):
            continue
        for marker in root_markers:
            idx = filepath.find(marker)
            if idx >= 0:
                strip_prefix = filepath[:idx] + "/"
                break
        break

    for filepath, file_info in coverage_data.items():
        if filepath in ("total", "meta"):
            continue

        # Parse file data
        lines_info = file_info.get("lines", {})
        total_lines = lines_info.get("total", 0)
        covered_lines = lines_info.get("covered", 0)
        coverage_pct = lines_info.get("pct", 0.0)
        uncovered_lines = total_lines - covered_lines

        # Strip absolute path prefix for pattern matching
        rel_path = filepath
        if strip_prefix and rel_path.startswith(strip_prefix):
            rel_path = rel_path[len(strip_prefix):]

        # Determine criticality
        criticality_tier, criticality_score = determine_criticality(rel_path)

        # Calculate priority score
        priority_score = calculate_priority_score(uncovered_lines, criticality_score, coverage_pct)

        entry = {
            "file": filepath,
            "coverage_pct": round(coverage_pct, 2),
            "total_lines": total_lines,
            "covered_lines": covered_lines,
            "uncovered_lines": uncovered_lines,
            "criticality_tier": criticality_tier,
            "criticality_score": criticality_score,
            "priority_score": priority_score,
        }

        by_criticality[criticality_tier].append(entry)

    # Sort within each tier: primary by priority_score desc, secondary by total_lines desc
    for tier in by_criticality:
        by_criticality[tier].sort(
            key=lambda x: (x["priority_score"], x["total_lines"]),
            reverse=True,
        )

    return by_criticality


def write_json_output(
    by_criticality: Dict[str, List[Dict[str, Any]]],
    output_path: Path,
    overall_coverage_pct: float,
) -> None:
    """Write the frontend prioritized JSON output."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    total_components = sum(len(files) for files in by_criticality.values())

    # Extract top 3 overall
    all_files = []
    for files in by_criticality.values():
        all_files.extend(files)
    all_files.sort(
        key=lambda x: (x["criticality_score"], x["priority_score"], x["total_lines"]),
        reverse=True,
    )
    top_3 = [f["file"] for f in all_files[:3]]

    output = {
        "generated_at": timestamp,
        "baseline_source": "coverage-final.json",
        "criticality_definitions": {
            "Critical": "Core features: Canvas, Chat, Agent Dashboard",
            "High": "Integration components",
            "Medium": "UI, pages, lib",
            "Low": "Hooks, shared",
        },
        "summary": {
            "total_components": total_components,
            "critical_count": len(by_criticality.get("Critical", [])),
            "high_count": len(by_criticality.get("High", [])),
            "medium_count": len(by_criticality.get("Medium", [])),
            "low_count": len(by_criticality.get("Low", [])),
            "overall_line_coverage": round(overall_coverage_pct, 2),
            "top_3_components": top_3,
        },
        "by_criticality": by_criticality,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  JSON report written to {output_path}")
    print(f"    Critical={len(by_criticality.get('Critical', []))} "
          f"High={len(by_criticality.get('High', []))} "
          f"Medium={len(by_criticality.get('Medium', []))} "
          f"Low={len(by_criticality.get('Low', []))}")


def write_markdown_output(
    by_criticality: Dict[str, List[Dict[str, Any]]],
    output_path: Path,
    overall_coverage_pct: float,
) -> None:
    """Write the frontend Markdown prioritization report."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    total_components = sum(len(files) for files in by_criticality.values())

    lines = []

    # Title
    lines.append("# Frontend High-Impact Component Prioritization v11.0")
    lines.append("")
    lines.append(f"**Generated**: {timestamp}")
    lines.append("**Phase**: 292-02")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- **Total components analyzed**: {total_components}")
    lines.append(f"- **Overall line coverage**: {overall_coverage_pct:.2f}%")
    lines.append("")
    lines.append("| Criticality | Components | Definition |")
    lines.append("|-------------|------------|------------|")
    for tier_key in ["Critical", "High", "Medium", "Low"]:
        files = by_criticality.get(tier_key, [])
        lines.append(f"| {tier_key} | {len(files)} | {CRITICALITY_TIERS[tier_key]['description']} |")
    lines.append("")

    # Criticality Definitions
    lines.append("## Criticality Definitions")
    lines.append("")
    lines.append("| Tier | Score | Patterns | Description |")
    lines.append("|------|-------|----------|-------------|")
    lines.append("| Critical | 10 | components/canvas/, components/chat/, components/agent-dashboard/ | Core user-facing features |")
    lines.append("| High | 7 | components/integrations/ | Integration components |")
    lines.append("| Medium | 5 | components/ui/, pages/, lib/ | UI, pages, lib |")
    lines.append("| Low | 3 | hooks/, shared/ | Hooks, shared utilities |")
    lines.append("")

    # Critical section
    lines.append("## Critical (Canvas, Chat, Agent Dashboard)")
    lines.append("")
    critical_files = by_criticality.get("Critical", [])
    lines.append(f"**{len(critical_files)} components** — Core user-facing features with highest business impact")
    lines.append("")
    if critical_files:
        lines.append("| Rank | Component | Coverage% | Lines | Uncovered | Priority Score |")
        lines.append("|------|-----------|-----------|-------|-----------|----------------|")
        for i, f in enumerate(critical_files, 1):
            lines.append(
                f"| {i} | {f['file']} | {f['coverage_pct']:.2f}% | {f['total_lines']} | "
                f"{f['uncovered_lines']} | {f['priority_score']:.2f} |"
            )
        lines.append("")

    # High section
    lines.append("## High (Integrations)")
    lines.append("")
    high_files = by_criticality.get("High", [])
    lines.append(f"**{len(high_files)} components** — Integration components with significant business impact")
    lines.append("")
    if high_files:
        lines.append("| Rank | Component | Coverage% | Lines | Uncovered | Priority Score |")
        lines.append("|------|-----------|-----------|-------|-----------|----------------|")
        for i, f in enumerate(high_files, 1):
            lines.append(
                f"| {i} | {f['file']} | {f['coverage_pct']:.2f}% | {f['total_lines']} | "
                f"{f['uncovered_lines']} | {f['priority_score']:.2f} |"
            )
        lines.append("")

    # Medium section (top 30 only)
    lines.append("## Medium (UI, Pages, Lib)")
    lines.append("")
    medium_files = by_criticality.get("Medium", [])
    lines.append(f"**{len(medium_files)} components** — Supporting UI, page layouts, and utility libraries")
    lines.append("")
    display_medium = medium_files[:30]
    if display_medium:
        lines.append("| Rank | Component | Coverage% | Lines | Uncovered | Priority Score |")
        lines.append("|------|-----------|-----------|-------|-----------|----------------|")
        for i, f in enumerate(display_medium, 1):
            lines.append(
                f"| {i} | {f['file']} | {f['coverage_pct']:.2f}% | {f['total_lines']} | "
                f"{f['uncovered_lines']} | {f['priority_score']:.2f} |"
            )
        if len(medium_files) > 30:
            lines.append("")
            lines.append(f"*Showing top 30 of {len(medium_files)} components*")
        lines.append("")

    # Low section (top 10 only)
    lines.append("## Low (Hooks, Shared)")
    lines.append("")
    low_files = by_criticality.get("Low", [])
    lines.append(f"**{len(low_files)} components** — Custom hooks and shared utilities")
    lines.append("")
    display_low = low_files[:10]
    if display_low:
        lines.append("| Rank | Component | Coverage% | Lines | Uncovered | Priority Score |")
        lines.append("|------|-----------|-----------|-------|-----------|----------------|")
        for i, f in enumerate(display_low, 1):
            lines.append(
                f"| {i} | {f['file']} | {f['coverage_pct']:.2f}% | {f['total_lines']} | "
                f"{f['uncovered_lines']} | {f['priority_score']:.2f} |"
            )
        if len(low_files) > 10:
            lines.append("")
            lines.append(f"*Showing top 10 of {len(low_files)} components*")
        lines.append("")

    # Priority Score Formula
    lines.append("## Priority Score Formula")
    lines.append("")
    lines.append("```")
    lines.append("priority_score = (uncovered_lines * criticality_score) / (coverage_pct + 1)")
    lines.append("```")
    lines.append("")
    lines.append("### Why This Formula?")
    lines.append("")
    lines.append("- **uncovered_lines**: More uncovered lines = more potential coverage gain")
    lines.append("- **criticality_score**: Higher business criticality = more value per test")
    lines.append(r"- **coverage_pct + 1**: Lower current coverage = higher priority")
    lines.append("  - Adding 1 prevents division by zero for 0% coverage components")
    lines.append("")

    # Quick wins
    lines.append("## Quick Wins (0% Coverage in Critical/High Tiers)")
    lines.append("")
    quick_wins = []
    for tier in ["Critical", "High"]:
        for f in by_criticality.get(tier, []):
            if f["coverage_pct"] == 0.0:
                quick_wins.append(f)
    quick_wins.sort(key=lambda x: x["uncovered_lines"], reverse=True)
    if quick_wins:
        lines.append(f"These {len(quick_wins)} components have **zero coverage** but Critical or High business impact.")
        lines.append("")
        lines.append("| Rank | Component | Uncovered Lines | Criticality | Priority Score |")
        lines.append("|------|-----------|-----------------|-------------|----------------|")
        for i, f in enumerate(quick_wins, 1):
            lines.append(
                f"| {i} | {f['file']} | {f['uncovered_lines']} | "
                f"{f['criticality_tier']} | {f['priority_score']:.2f} |"
            )
    else:
        lines.append("No components with 0% coverage in Critical or High tiers found.")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by prioritize_frontend_components.py*")
    lines.append("*Phase: 292-02*")
    lines.append(f"*Timestamp: {timestamp}*")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"  Markdown report written to {output_path}")


def main() -> int:
    """Main entry point."""
    args = parse_args()

    coverage_path = args.coverage_file
    if not coverage_path.is_absolute():
        coverage_path = coverage_path.resolve()

    # Determine output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = coverage_path.parent

    if not output_dir.is_absolute():
        output_dir = output_dir.resolve()

    if args.markdown_dir:
        markdown_dir = args.markdown_dir
    else:
        markdown_dir = output_dir

    if not markdown_dir.is_absolute():
        markdown_dir = markdown_dir.resolve()

    print("=" * 60)
    print("PHASE 292-02: FRONTEND COMPONENT PRIORITIZATION")
    print("=" * 60)

    # Step 1: Load coverage data
    print(f"\n[1/4] Loading coverage data from {coverage_path}...")
    coverage_data = load_coverage_json(coverage_path)

    total = coverage_data.get("total", {})
    overall_lines = total.get("lines", {})
    overall_coverage_pct = overall_lines.get("pct", 0.0)
    print(f"  Overall line coverage: {overall_coverage_pct:.2f}%")

    # Step 2: Process by criticality
    print(f"\n[2/4] Processing components by business criticality...")
    by_criticality = process_coverage_data(coverage_data)

    for tier in ["Critical", "High", "Medium", "Low"]:
        print(f"  {tier}: {len(by_criticality.get(tier, []))} components")

    # Step 3: Write JSON
    print(f"\n[3/4] Writing JSON output...")
    json_output = output_dir / "prioritized_frontend_components_v11.0.json"
    write_json_output(by_criticality, json_output, overall_coverage_pct)

    # Step 4: Write Markdown
    print(f"\n[4/4] Writing Markdown output...")
    md_output = markdown_dir / "HIGH_IMPACT_FRONTEND_COMPONENTS_v11.0.md"
    write_markdown_output(by_criticality, md_output, overall_coverage_pct)

    print(f"\n{'=' * 60}")
    print("FRONTEND PRIORITIZATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Output JSON: {json_output}")
    print(f"  Output MD:   {md_output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
