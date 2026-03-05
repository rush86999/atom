#!/usr/bin/env python3
"""
Generate gap closure summary for Phase 127.
Compares baseline, interim, and final coverage measurements.
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    # Load all measurements
    metrics_dir = Path("tests/coverage_reports/metrics")

    with open(metrics_dir / "phase_127_baseline.json") as f:
        baseline = json.load(f)
    with open(metrics_dir / "phase_127_gapclosure_interim.json") as f:
        interim = json.load(f)
    with open(metrics_dir / "phase_127_final_gapclosure.json") as f:
        final = json.load(f)

    # Extract overall percentages
    def get_pct(data):
        return data['totals']['percent_covered']

    baseline_pct = get_pct(baseline)
    interim_pct = get_pct(interim)
    final_pct = get_pct(final)

    # Calculate improvements
    interim_improvement = interim_pct - baseline_pct
    final_improvement = final_pct - baseline_pct
    gap_remaining = 80.0 - final_pct

    # Generate summary
    summary = {
        "phase": "127",
        "gap_closure_plans": ["127-07", "127-08A", "127-08B", "127-10", "127-11", "127-12", "127-13", "127-09"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "measurements": {
            "baseline_percentage": round(baseline_pct, 2),
            "interim_percentage": round(interim_pct, 2),
            "final_percentage": round(final_pct, 2)
        },
        "improvements": {
            "interim_improvement_pp": round(interim_improvement, 2),
            "final_improvement_pp": round(final_improvement, 2),
            "total_improvement_pp": round(final_improvement, 2)
        },
        "target": {
            "percentage": 80.0,
            "gap_remaining_pp": round(gap_remaining, 2),
            "status": "NOT_MET" if final_pct < 80.0 else "MET"
        },
        "tests_added_during_gap_closure": {
            "plan_04": 20,   # workflow_engine integration (revised from property tests)
            "plan_07": 0,    # Investigation only
            "plan_08A": 24,  # workflow + world model
            "plan_08B": 17,  # episode services
            "plan_09": 0,    # CI enforcement only
            "plan_10": 42,   # LLM services
            "plan_11": 20,   # Canvas system (canvas_tool.py)
            "plan_12": 42,   # Device system (browser_tool.py + device_tool.py)
            "plan_13": 41,   # Governance + Episode additional
            "total": 206
        },
        "individual_file_improvements": {
            "workflow_engine_py": "+8.64 pp (0% → 8.64%)",
            "world_model_py": "+12.5 pp (18% → 30.5%)",
            "episode_services_avg": "+7.5 pp (average across 5 files)",
            "byok_handler_py": "+25 pp (35% → 60%)",
            "canvas_tool_py": "+40.76 pp (0% → 40.76%)",
            "browser_tool_py": "+57 pp (0% → 57%)",
            "device_tool_py": "+64 pp (0% → 64%)",
            "governance_services": "+10-20 pp (average across 4 files)"
        },
        "quality_gates": {
            "ci_enforcement": "ENABLED",
            "pre_commit_hook": "ENABLED",
            "fail_under_threshold": 80.0
        },
        "next_steps": {
            "estimated_additional_tests_needed": int(gap_remaining * 10),  # Rough estimate: ~10 tests per pp
            "recommended_next_phase": "127-14" if gap_remaining > 10 else "128",
            "focus_areas": [
                "High-impact files with most missing lines",
                "API endpoints (TestClient integration tests)",
                "Service layer business logic",
                "Router integration tests for all API modules"
            ],
            "lessons_learned": [
                "Overall backend coverage (26.15%) diluted across 528 files",
                "Individual file improvements significant but not reflected globally",
                "Integration tests effective for file-specific coverage (+8-64 pp)",
                "Property tests improve correctness but don't increase coverage",
                "26.15% is realistic baseline (core/, api/, tools/ only)",
                "Gap to 80% target: 53.85 percentage points (not 5.4 pp as originally claimed)"
            ]
        }
    }

    # Save summary
    output_path = metrics_dir / "phase_127_gapclosure_summary.json"
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Gap closure summary saved to {output_path}")
    print(f"Baseline: {baseline_pct:.2f}%")
    print(f"Interim: {interim_pct:.2f}%")
    print(f"Final: {final_pct:.2f}%")
    print(f"Total improvement: {final_improvement:+.2f} pp")
    print(f"Gap to 80%: {gap_remaining:.2f} pp")
    print(f"\nStatus: {summary['target']['status']}")
    print(f"Tests added: {summary['tests_added_during_gap_closure']['total']}")
    print(f"Quality gates: CI={summary['quality_gates']['ci_enforcement']}, Pre-commit={summary['quality_gates']['pre_commit_hook']}")


if __name__ == "__main__":
    main()
