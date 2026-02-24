#!/usr/bin/env python3
"""
Critical Path Coverage Mapper v3.2

Maps coverage gaps to critical business flows and identifies failure modes.

Generated: 2026-02-24
Phase: 81-03
Purpose: Understand which untested code paths pose the highest risk to core business operations
"""

import json
from typing import Dict, List, Any
from pathlib import Path


# Critical Business Paths
# These are the essential workflows that keep Atom running safely and effectively
CRITICAL_PATHS = {
    "agent_execution": {
        "name": "Agent Execution Flow",
        "description": "End-to-end agent request processing and execution",
        "steps": [
            {
                "file": "core/agent_governance_service.py",
                "function": "check_permissions",
                "description": "Governance check - validates agent can perform action"
            },
            {
                "file": "core/atom_agent_endpoints.py",
                "function": "stream_agent_response",
                "description": "Streaming response - token-by-token LLM output"
            },
            {
                "file": "core/llm/byok_handler.py",
                "function": "get_llm_response",
                "description": "LLM integration - multi-provider routing"
            },
            {
                "file": "core/agent_governance_service.py",
                "function": "log_execution",
                "description": "Execution logging - audit trail"
            },
        ],
        "failure_modes": [
            "Permission bypass allows unauthorized actions",
            "Streaming failure causes incomplete responses",
            "LLM provider failure causes request drop",
            "Logging failure loses audit trail",
        ],
    },

    "episode_creation": {
        "name": "Episode Creation Flow",
        "description": "Episodic memory segmentation and storage",
        "steps": [
            {
                "file": "core/episode_segmentation_service.py",
                "function": "detect_time_gap",
                "description": "Time gap detection - identifies conversation pauses"
            },
            {
                "file": "core/episode_segmentation_service.py",
                "function": "detect_topic_changes",
                "description": "Topic change detection - semantic context switches"
            },
            {
                "file": "core/episode_lifecycle_service.py",
                "function": "create_episode",
                "description": "Episode creation - new memory record"
            },
            {
                "file": "core/episode_retrieval_service.py",
                "function": "store_segment",
                "description": "Segment storage - persistence layer"
            },
        ],
        "failure_modes": [
            "Time gap mis-detection creates incorrect episodes",
            "Topic change failure misses context switches",
            "Episode creation corruption loses memory",
            "Storage failure causes data loss",
        ],
    },

    "canvas_presentation": {
        "name": "Canvas Presentation Flow",
        "description": "Canvas creation, rendering, and WebSocket updates",
        "steps": [
            {
                "file": "tools/canvas_tool.py",
                "function": "create_canvas",
                "description": "Canvas creation - initialize presentation"
            },
            {
                "file": "tools/canvas_tool.py",
                "function": "render_charts",
                "description": "Chart rendering - visualize data"
            },
            {
                "file": "api/canvas_routes.py",
                "function": "submit_canvas_data",
                "description": "Data submission - user input handling"
            },
            {
                "file": "core/agent_governance_service.py",
                "function": "check_governance",
                "description": "Governance enforcement - maturity-based access"
            },
        ],
        "failure_modes": [
            "Canvas creation fails silently",
            "Chart rendering displays incorrect data",
            "Submission bypass corrupts user data",
            "Governance bypass allows unauthorized canvas actions",
        ],
    },

    "graduation_promotion": {
        "name": "Agent Graduation Flow",
        "description": "Agent maturity assessment and promotion",
        "steps": [
            {
                "file": "core/agent_graduation_service.py",
                "function": "calculate_criteria",
                "description": "Graduation criteria - episode count, intervention rate"
            },
            {
                "file": "core/constitutional_validator.py",
                "function": "validate_compliance",
                "description": "Constitutional check - safety compliance"
            },
            {
                "file": "core/agent_governance_service.py",
                "function": "promote_agent",
                "description": "Promotion execution - maturity level change"
            },
            {
                "file": "core/episode_lifecycle_service.py",
                "function": "update_maturity",
                "description": "Maturity update - persistence"
            },
        ],
        "failure_modes": [
            "Criteria calculation error promotes unqualified agents",
            "Constitutional bypass allows non-compliant promotion",
            "Promotion corruption causes maturity mismatch",
            "Update failure creates stale maturity state",
        ],
    },
}


def get_file_coverage(coverage_json: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """
    Extract coverage data for a specific file.

    Args:
        coverage_json: Full coverage report JSON
        file_path: Path to file (e.g., "core/agent_governance_service.py")

    Returns:
        Coverage dictionary with coverage_pct, covered_lines, total_lines
        Returns 0% coverage if file not found
    """
    # Handle both "backend/" prefix and no prefix
    file_variants = [
        file_path,
        f"backend/{file_path}",
        f"backend/tests/{file_path}",
    ]

    for variant in file_variants:
        if "files" in coverage_json and variant in coverage_json["files"]:
            file_data = coverage_json["files"][variant]
            summary = file_data.get("summary", {})
            return {
                "coverage_pct": summary.get("percent_covered", 0.0),
                "covered_lines": summary.get("num_statements", 0) - summary.get("missing_lines", 0),
                "total_lines": summary.get("num_statements", 0),
                "missing_lines": summary.get("missing_lines", 0),
            }

    # File not found in coverage - treat as 0% coverage
    return {
        "coverage_pct": 0.0,
        "covered_lines": 0,
        "total_lines": 0,
        "missing_lines": 0,
    }


def calculate_risk(uncovered_steps: int, total_steps: int) -> str:
    """
    Calculate risk level based on uncovered critical steps.

    Risk Levels:
    - CRITICAL: 75%+ uncovered - Multiple untested steps, high failure probability
    - HIGH: 50-74% uncovered - Critical steps untested, significant risk
    - MEDIUM: 25-49% uncovered - Some coverage gaps, moderate risk
    - LOW: 0-24% uncovered - Mostly covered, minimal risk

    Args:
        uncovered_steps: Number of steps with insufficient coverage
        total_steps: Total number of steps in the path

    Returns:
        Risk level string: CRITICAL, HIGH, MEDIUM, LOW, or UNKNOWN
    """
    if total_steps == 0:
        return "UNKNOWN"

    uncovered_pct = uncovered_steps / total_steps

    if uncovered_pct >= 0.75:
        return "CRITICAL"
    elif uncovered_pct >= 0.5:
        return "HIGH"
    elif uncovered_pct >= 0.25:
        return "MEDIUM"
    else:
        return "LOW"


def analyze_path_coverage(path_name: str, path_data: Dict[str, Any], coverage_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze coverage for a critical business path.

    For each step in the path, check if the file/function has coverage.
    Calculate overall path coverage and risk level.

    Args:
        path_name: Name of the critical path (e.g., "agent_execution")
        path_data: Path configuration with steps and failure modes
        coverage_json: Full coverage report JSON

    Returns:
        Analysis results with:
        - covered_steps: Number of steps with >50% coverage
        - uncovered_steps: Number of steps with <=50% coverage
        - coverage_pct: Percentage of covered steps
        - risk_level: CRITICAL, HIGH, MEDIUM, or LOW
        - steps: Detailed breakdown of each step
        - failure_modes: List of potential failure modes
    """
    steps_analyzed = []
    covered_steps = 0
    uncovered_steps = 0

    for step in path_data["steps"]:
        file_path = step["file"]
        func_name = step["function"]

        # Get file-level coverage
        file_coverage = get_file_coverage(coverage_json, file_path)

        # Consider step covered if file has >50% coverage
        # Note: This is a simplified heuristic - function-level coverage would be more precise
        is_covered = file_coverage["coverage_pct"] > 50

        if is_covered:
            covered_steps += 1
        else:
            uncovered_steps += 1

        steps_analyzed.append({
            "step": step["description"],
            "file": file_path,
            "function": func_name,
            "is_covered": is_covered,
            "file_coverage_pct": file_coverage["coverage_pct"],
        })

    # Calculate risk level based on uncovered critical steps
    risk_level = calculate_risk(uncovered_steps, len(steps_analyzed))

    return {
        "path_name": path_name,
        "covered_steps": covered_steps,
        "uncovered_steps": uncovered_steps,
        "total_steps": len(steps_analyzed),
        "coverage_pct": round(covered_steps / len(steps_analyzed) * 100, 2) if steps_analyzed else 0,
        "risk_level": risk_level,
        "steps": steps_analyzed,
        "failure_modes": path_data["failure_modes"],
    }


def analyze_all_paths(coverage_json_path: str) -> Dict[str, Any]:
    """
    Analyze coverage for all critical business paths.

    Args:
        coverage_json_path: Path to coverage.json file

    Returns:
        Dictionary mapping path names to their analysis results
    """
    # Load coverage data
    with open(coverage_json_path, 'r') as f:
        coverage_json = json.load(f)

    # Analyze each critical path
    results = {}
    for path_name, path_data in CRITICAL_PATHS.items():
        results[path_name] = analyze_path_coverage(path_name, path_data, coverage_json)

    return results


def generate_summary_statistics(analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate summary statistics across all critical paths.

    Args:
        analysis_results: Results from analyze_all_paths()

    Returns:
        Summary statistics with overall coverage, risk distribution, etc.
    """
    total_paths = len(analysis_results)
    if total_paths == 0:
        return {
            "total_paths": 0,
            "avg_coverage_pct": 0,
            "high_risk_paths": [],
            "total_uncovered_steps": 0,
            "risk_distribution": {},
        }

    # Calculate average coverage
    avg_coverage = sum(r["coverage_pct"] for r in analysis_results.values()) / total_paths

    # Count paths by risk level
    risk_distribution = {}
    for result in analysis_results.values():
        risk = result["risk_level"]
        risk_distribution[risk] = risk_distribution.get(risk, 0) + 1

    # Identify high-risk paths (CRITICAL or HIGH)
    high_risk_paths = [
        name for name, result in analysis_results.items()
        if result["risk_level"] in ["CRITICAL", "HIGH"]
    ]

    # Total uncovered steps
    total_uncovered_steps = sum(r["uncovered_steps"] for r in analysis_results.values())

    return {
        "total_paths": total_paths,
        "avg_coverage_pct": round(avg_coverage, 2),
        "high_risk_paths": high_risk_paths,
        "total_uncovered_steps": total_uncovered_steps,
        "risk_distribution": risk_distribution,
    }


def main():
    """
    Main entry point for running critical path analysis.

    Usage:
        python critical_path_mapper.py

    Output:
        Generates critical_path_coverage.json in metrics directory
    """
    # Paths
    backend_dir = Path(__file__).parent.parent.parent
    coverage_json_path = backend_dir / "tests/coverage_reports/metrics/coverage.json"
    output_path = backend_dir / "tests/coverage_reports/metrics/critical_path_coverage.json"

    # Run analysis
    print(f"Loading coverage from: {coverage_json_path}")
    results = analyze_all_paths(str(coverage_json_path))

    # Generate summary statistics
    summary = generate_summary_statistics(results)

    # Combine results with summary
    output_data = {
        "summary": summary,
        "paths": results,
    }

    # Write output
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nCritical Path Coverage Analysis Complete")
    print(f"Output: {output_path}")
    print(f"\nSummary:")
    print(f"  Total Paths: {summary['total_paths']}")
    print(f"  Average Coverage: {summary['avg_coverage_pct']}%")
    print(f"  High-Risk Paths: {len(summary['high_risk_paths'])}")
    print(f"  Total Uncovered Steps: {summary['total_uncovered_steps']}")
    print(f"\nRisk Distribution:")
    for risk, count in summary['risk_distribution'].items():
        print(f"  {risk}: {count}")


if __name__ == "__main__":
    main()
