#!/usr/bin/env python3
"""
Test Prioritization Service for Phase 164

Generates phased expansion roadmap for systematic coverage improvement.
Prioritizes by business impact, dependencies, and risk using weighted scoring.

Usage:
    cd backend
    python tests/scripts/test_prioritization_service.py \
        --gap-analysis tests/coverage_reports/metrics/backend_164_gap_analysis.json \
        --output tests/coverage_reports/TEST_PRIORITIZATION_PHASED_ROADMAP.md

Output:
    - Phased roadmap with file assignments per phase (165-171)
    - Estimated coverage gain per phase
    - Dependency-ordered file list
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Phase definitions from ROADMAP.md
PHASE_DEFINITIONS = {
    165: {
        "name": "Core Services Coverage (Governance & LLM)",
        "focus": ["agent_governance", "llm", "byok_handler", "cognitive_tier"],
        "tier_priority": ["Critical"],
        "target_coverage_gain": 10.0,  # Percentage points
    },
    166: {
        "name": "Core Services Coverage (Episodic Memory)",
        "focus": ["episode_segmentation", "episode_retrieval", "episode_lifecycle", "agent_graduation"],
        "tier_priority": ["Critical"],
        "target_coverage_gain": 8.0,
    },
    167: {
        "name": "API Routes Coverage",
        "focus": ["routes", "api/", "endpoints"],
        "tier_priority": ["Critical", "High"],
        "target_coverage_gain": 12.0,
    },
    168: {
        "name": "Database Layer Coverage",
        "focus": ["models", "schema", "database"],
        "tier_priority": ["Critical", "High"],
        "target_coverage_gain": 10.0,
    },
    169: {
        "name": "Tools & Integrations Coverage",
        "focus": ["browser_tool", "device_tool", "canvas_tool"],
        "tier_priority": ["High", "Medium"],
        "target_coverage_gain": 8.0,
    },
    170: {
        "name": "Integration Testing (LanceDB, WebSocket, HTTP)",
        "focus": ["lancedb", "websocket", "http_client", "external_api"],
        "tier_priority": ["High", "Medium"],
        "target_coverage_gain": 7.0,
    },
    171: {
        "name": "Gap Closure & Final Push",
        "focus": ["all_remaining"],
        "tier_priority": ["Critical", "High", "Medium", "Low"],
        "target_coverage_gain": 15.0,  # Final push to 80%
    },
}

# Dependency graph: what modules depend on what
# Format: "dependent": ["dependencies"]
DEPENDENCY_GRAPH = {
    # Core services depend on utilities
    "agent_governance_service": ["governance_cache", "agent_context_resolver"],
    "episode_segmentation_service": ["episode_lifecycle_service"],
    "episode_retrieval_service": ["episode_lifecycle_service"],
    "agent_graduation_service": ["episode_segmentation_service", "episode_retrieval_service"],
    # LLM services depend on base handlers
    "byok_handler": ["llm_base"],
    "cognitive_tier_system": ["byok_handler"],
    # API routes depend on services and models
    "agent_routes": ["agent_governance_service", "agent_execution_service"],
    "canvas_routes": ["canvas_tool"],
    "browser_routes": ["browser_tool"],
    # Tools depend on external services
    "browser_tool": ["playwright"],
    "device_tool": ["device_apis"],
}


def calculate_dependency_order(
    gaps: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Topological sort by dependency to ensure correct testing order.

    Rules:
    1. Test dependencies before dependents
    2. Within same dependency level, sort by priority score
    """
    # Build file name to gap mapping
    file_to_gap = {gap["file"]: gap for gap in gaps}

    # Assign level based on dependencies
    def get_dependency_level(file_path: str, visited: Optional[Set[str]] = None) -> int:
        """Recursively calculate dependency level (0 = no deps)."""
        if visited is None:
            visited = set()

        if file_path in visited:
            return 0  # Circular dependency, treat as independent

        visited.add(file_path)

        # Extract module name from file path
        module_name = file_path.split("/")[-1].replace(".py", "")

        # Get dependencies
        dependencies = DEPENDENCY_GRAPH.get(module_name, [])

        if not dependencies:
            return 0

        # Recursively get max dependency level
        max_dep_level = 0
        for dep in dependencies:
            # Find dep file in gaps
            dep_file = next((f for f in file_to_gap.keys() if dep in f), None)
            if dep_file:
                dep_level = get_dependency_level(dep_file, visited.copy())
                max_dep_level = max(max_dep_level, dep_level)

        return max_dep_level + 1

    # Calculate levels for all gaps
    for gap in gaps:
        gap["dependency_level"] = get_dependency_level(gap["file"])

    # Sort: first by dependency level, then by priority score (descending)
    gaps.sort(key=lambda g: (g["dependency_level"], -g["priority_score"]))

    return gaps


def assign_files_to_phases(
    gaps: List[Dict[str, Any]],
    baseline_coverage: float,
    target_coverage: float = 80.0,
) -> Dict[int, Dict[str, Any]]:
    """
    Assign files to phases based on focus areas and priorities.

    Returns:
        Dict mapping phase number to phase data (files, estimated_gain, etc.)
    """
    phases = {}

    # Initialize phases
    for phase_num, definition in PHASE_DEFINITIONS.items():
        phases[phase_num] = {
            "name": definition["name"],
            "focus_areas": definition["focus"],
            "files": [],
            "target_coverage_gain": definition["target_coverage_gain"],
            "cumulative_coverage": baseline_coverage,
        }

    # Order gaps by dependency
    ordered_gaps = calculate_dependency_order(gaps.copy())

    # Track current cumulative coverage
    current_coverage = baseline_coverage

    # Assign files to phases
    for phase_num, phase_data in phases.items():
        definition = PHASE_DEFINITIONS[phase_num]
        focus_areas = definition["focus"]
        tier_priority = definition["tier_priority"]

        # Find matching files
        for gap in ordered_gaps:
            # Skip if already assigned
            if gap.get("assigned_phase"):
                continue

            # Check if file matches phase focus
            file_path = gap["file"]
            tier = gap["business_impact"]

            # Match by focus area or tier
            matches_focus = any(focus in file_path for focus in focus_areas)
            matches_tier = tier in tier_priority

            # For final phase, match all remaining
            if phase_num == 171:
                matches_focus = True
                matches_tier = True

            if matches_focus or matches_tier:
                # Assign to this phase
                gap["assigned_phase"] = phase_num
                phase_data["files"].append(gap)

                # Stop assigning to this phase if we have enough
                # (rough estimate: 20-30 files per phase)
                if len(phase_data["files"]) >= 30:
                    break

        # Update cumulative coverage
        phase_data["cumulative_coverage"] = current_coverage
        current_coverage += phase_data["target_coverage_gain"]
        phase_data["target_cumulative_coverage"] = current_coverage

    return phases


def estimate_coverage_gain(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Estimate coverage gain for a list of files."""
    total_uncovered = sum(f["uncovered_lines"] for f in files)
    # Assume we can cover 60% of uncovered lines with focused testing
    estimated_covered = total_uncovered * 0.6

    return {
        "total_uncovered_lines": total_uncovered,
        "estimated_lines_covered": int(estimated_covered),
        "file_count": len(files),
    }


def generate_phased_roadmap(
    gap_analysis: Dict[str, Any],
    output_path: Path,
) -> None:
    """Generate phased roadmap Markdown report."""
    baseline_coverage = gap_analysis["baseline_coverage"]
    all_gaps = gap_analysis.get("all_gaps", [])

    # Assign files to phases
    phases = assign_files_to_phases(all_gaps, baseline_coverage)

    # Generate Markdown report
    lines = [
        "# Test Prioritization Phased Roadmap - Phase 164\n",
        f"**Generated**: {datetime.now().isoformat()}",
        f"**Baseline Coverage**: {baseline_coverage}%",
        f"**Target Coverage**: 80.0%",
        f"**Total Gap**: {80.0 - baseline_coverage:.2f} percentage points\n",
        "## Overview\n",
        f"This roadmap provides a phased approach to achieve 80% coverage across **{len(all_gaps)} files**",
        f"with **{sum(g['uncovered_lines'] for g in all_gaps)}** uncovered lines.\n",
        "## Phase Summary\n\n",
        "| Phase | Name | Files | Est. Lines | Target Gain | Cumulative |\n",
        "|-------|------|-------|------------|-------------|------------|\n",
    ]

    for phase_num, phase_data in phases.items():
        gain_info = estimate_coverage_gain(phase_data["files"])
        lines.append(
            f"| {phase_num} | {phase_data['name']} | {len(phase_data['files'])} | "
            f"{gain_info['estimated_lines_covered']} | "
            f"+{phase_data['target_coverage_gain']}% | "
            f"{phase_data['cumulative_coverage']:.1f}% → {phase_data['target_cumulative_coverage']:.1f}% |\n"
        )

    lines.append("\n## Phase Details\n\n")

    # Generate details for each phase
    for phase_num, phase_data in phases.items():
        lines.append(f"### Phase {phase_num}: {phase_data['name']}\n\n")
        lines.append(f"**Target Coverage Gain**: +{phase_data['target_coverage_gain']}%\n")
        lines.append(f"**Focus Areas**: {', '.join(phase_data['focus_areas'])}\n\n")

        files = phase_data["files"]
        if files:
            lines.append(f"**Files ({len(files)}):**\n\n")
            lines.append("| File | Coverage | Impact | Missing | Priority |\n")
            lines.append("|------|----------|--------|---------|----------|\n")

            for gap in files[:20]:  # Show top 20
                lines.append(
                    f"| `{gap['file']}` | {gap['coverage_pct']}% | {gap['business_impact']} | "
                    f"{gap['uncovered_lines']} | {gap['priority_score']:.1f} |\n"
                )

            if len(files) > 20:
                lines.append(f"| ... and {len(files) - 20} more files | | | | |\n")

        else:
            lines.append("*No files assigned*\n")

        lines.append("\n")

    # Add dependency ordering explanation
    lines.append("## Dependency Ordering\n\n")
    lines.append("Files are assigned to phases respecting the following dependency rules:\n\n")
    lines.append("1. Utilities and helpers are tested before services that use them\n")
    lines.append("2. Models are tested before API routes that use them\n")
    lines.append("3. Core services are tested before integrations that depend on them\n")
    lines.append("4. Within each phase, files are ordered by priority score (business impact × coverage gap)\n\n")

    # Add next steps
    lines.append("## Next Steps\n\n")
    lines.append("1. **Phase 165**: Start with governance and LLM services (highest impact)\n")
    lines.append("2. **Phase 166**: Move to episodic memory services\n")
    lines.append("3. **Phase 167**: Cover API routes with TestClient integration tests\n")
    lines.append("4. **Phase 168**: Ensure database models have comprehensive coverage\n")
    lines.append("5. **Phase 169**: Test browser and device tools with proper mocking\n")
    lines.append("6. **Phase 170**: Add integration tests for external services\n")
    lines.append("7. **Phase 171**: Final gap closure to achieve 80% target\n\n")

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.writelines(lines)

    print(f"Phased roadmap generated: {output_path}")
    print(f"  Baseline: {baseline_coverage:.1f}% → Target: 80%")

    # Also generate JSON for programmatic access
    json_path = output_path.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(phases, f, indent=2)
    print(f"  JSON output: {json_path}")


def load_gap_analysis(gap_analysis_path: Path) -> Dict[str, Any]:
    """Load gap analysis JSON."""
    with open(gap_analysis_path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Generate phased testing roadmap from gap analysis"
    )
    parser.add_argument(
        "--gap-analysis",
        type=Path,
        default=Path("tests/coverage_reports/metrics/backend_164_gap_analysis.json"),
        help="Path to gap analysis JSON from Phase 164-01",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/coverage_reports/TEST_PRIORITIZATION_PHASED_ROADMAP.md"),
        help="Output path for phased roadmap",
    )

    args = parser.parse_args()

    # Load gap analysis
    if not args.gap_analysis.exists():
        print(f"Error: Gap analysis not found: {args.gap_analysis}")
        print("Run Phase 164-01 first: python tests/scripts/coverage_gap_analysis.py")
        sys.exit(1)

    gap_analysis = load_gap_analysis(args.gap_analysis)

    # Generate phased roadmap
    generate_phased_roadmap(gap_analysis, args.output)


if __name__ == "__main__":
    main()
