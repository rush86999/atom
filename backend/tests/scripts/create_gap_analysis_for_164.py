#!/usr/bin/env python3
"""
Create gap analysis JSON for Phase 164-02

Transforms existing gap analysis data into the format expected by
generate_test_stubs.py. This is a workaround for Phase 164-01 not
being executed yet.

Usage:
    python3 tests/scripts/create_gap_analysis_for_164.py
"""

import json
from pathlib import Path
from datetime import datetime


def load_data():
    """Load existing gap analysis and business impact data."""
    backend_dir = Path(__file__).parent.parent.parent

    # Load priority files (has coverage gap data)
    priority_path = backend_dir / "tests/coverage_reports/metrics/priority_files_for_phases_12_13.json"
    with open(priority_path) as f:
        priority_data = json.load(f)

    # Load business impact scores (has tier assignments)
    impact_path = backend_dir / "tests/coverage_reports/metrics/business_impact_scores.json"
    with open(impact_path) as f:
        impact_data = json.load(f)

    return priority_data, impact_data


def create_business_impact_lookup(impact_data):
    """Create a lookup dictionary for file -> business impact tier."""
    lookup = {}

    # Build lookup from files_by_tier
    files_by_tier = impact_data.get("files_by_tier", {})
    for tier, files in files_by_tier.items():
        for item in files:
            # Strip "backend/" prefix if present
            file_path = item.get("file", "")
            if file_path.startswith("backend/"):
                file_path = file_path[8:]
            lookup[file_path] = tier

    return lookup


def transform_to_164_format(priority_data, impact_lookup):
    """Transform data to Phase 164-02 expected format."""

    # Initialize tier breakdown
    tier_breakdown = {
        "Critical": {"files": [], "total_uncovered": 0, "file_count": 0},
        "High": {"files": [], "total_uncovered": 0, "file_count": 0},
        "Medium": {"files": [], "total_uncovered": 0, "file_count": 0},
        "Low": {"files": [], "total_uncovered": 0, "file_count": 0},
    }

    # Process priority files (from Phase 12 data)
    # Filter to only include files from phases "12" and "13"
    all_files = []
    for phase_id in ["12", "13"]:
        phase_data = priority_data.get("phases", {}).get(phase_id, {})
        phase_files = phase_data.get("files", [])
        all_files.extend(phase_files)

    # Process each file
    for file_item in all_files:
        file_path = file_item.get("file", "")

        # Look up business impact tier
        business_impact = impact_lookup.get(file_path, "Medium")  # Default to Medium

        # Calculate priority score (uncovered_lines * tier_score)
        tier_scores = {"Critical": 10, "High": 7, "Medium": 5, "Low": 3}
        tier_score = tier_scores.get(business_impact, 5)
        uncovered_lines = file_item.get("uncovered_lines", 0)
        priority_score = uncovered_lines * tier_score

        # Create gap entry
        gap_entry = {
            "file": file_path,
            "business_impact": business_impact,
            "uncovered_lines": uncovered_lines,
            "priority_score": priority_score,
            "current_percent": file_item.get("current_percent", 0.0),
            "total_lines": file_item.get("lines", 0),
            "missing_lines": [],  # Will be populated from coverage.json line analysis
            "recommended_test_type": file_item.get("recommended_test_type", "unit"),
            "tier": file_item.get("tier", "Unknown"),
        }

        # Add to appropriate tier
        if business_impact in tier_breakdown:
            tier_breakdown[business_impact]["files"].append(gap_entry)
            tier_breakdown[business_impact]["total_uncovered"] += uncovered_lines
            tier_breakdown[business_impact]["file_count"] += 1

    # Sort files within each tier by priority score
    for tier in tier_breakdown:
        tier_breakdown[tier]["files"].sort(
            key=lambda x: x.get("priority_score", 0), reverse=True
        )

    return tier_breakdown


def create_gap_analysis_json():
    """Create the gap analysis JSON for Phase 164-02."""

    print("Loading existing gap analysis data...")
    priority_data, impact_data = load_data()

    print("Creating business impact lookup...")
    impact_lookup = create_business_impact_lookup(impact_data)

    print("Transforming to Phase 164-02 format...")
    tier_breakdown = transform_to_164_format(priority_data, impact_lookup)

    # Calculate totals
    total_files = sum(tier["file_count"] for tier in tier_breakdown.values())
    total_uncovered = sum(tier["total_uncovered"] for tier in tier_breakdown.values())

    # Create final gap analysis structure
    gap_analysis = {
        "generated_at": datetime.now().isoformat() + "Z",
        "source": "Phase 164 gap analysis (transformed from existing data)",
        "summary": {
            "total_files": total_files,
            "total_uncovered_lines": total_uncovered,
            "tier_breakdown": {
                tier: tier_breakdown[tier]["file_count"]
                for tier in ["Critical", "High", "Medium", "Low"]
            },
        },
        "tier_breakdown": tier_breakdown,
    }

    # Write output
    backend_dir = Path(__file__).parent.parent.parent
    output_path = backend_dir / "tests/coverage_reports/metrics/backend_164_gap_analysis.json"

    with open(output_path, "w") as f:
        json.dump(gap_analysis, f, indent=2)

    print(f"\nCreated: {output_path}")
    print(f"Total files: {total_files}")
    print(f"Total uncovered lines: {total_uncovered}")
    for tier in ["Critical", "High", "Medium", "Low"]:
        count = tier_breakdown[tier]["file_count"]
        uncovered = tier_breakdown[tier]["total_uncovered"]
        print(f"  {tier}: {count} files, {uncovered} uncovered lines")


if __name__ == "__main__":
    create_gap_analysis_json()
