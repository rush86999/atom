#!/usr/bin/env python3
"""Generate Phase 127 completion summary documenting all work completed."""
import json
from pathlib import Path
from datetime import datetime, timezone

# Load all improvement reports
reports = {}
for component in ["models", "workflow", "endpoints"]:
    report_path = Path(f"tests/coverage_reports/metrics/phase_127_{component}_improvement.json")
    if report_path.exists():
        with open(report_path) as f:
            reports[component] = json.load(f)

# Load overall improvement summary
summary_path = Path("tests/coverage_reports/metrics/phase_127_improvement_summary.json")
with open(summary_path) as f:
    overall = json.load(f)

# Count new test files
test_files = [
    "tests/test_models_coverage.py",
    "tests/test_workflow_engine_coverage.py",
    "tests/test_atom_agent_endpoints_coverage.py",
    "tests/test_atom_agent_endpoints_unit_coverage.py"
]

# Estimate test counts from individual reports
planned_tests = {
    "models": reports.get("models", {}).get("tests_added", 20),
    "workflow": reports.get("workflow", {}).get("tests_added", 20),
    "endpoints": reports.get("endpoints", {}).get("tests_added", 13)
}

# Calculate actual improvements from individual reports
actual_improvements = {}
total_file_improvement = 0
for component, report in reports.items():
    if "improvement" in report:
        file_name = report.get("file", component)
        improvement = report["improvement"]
        actual_improvements[file_name] = {
            "component": component,
            "baseline": report.get("baseline_coverage", 0),
            "final": report.get("new_coverage", 0),
            "improvement": improvement
        }
        total_file_improvement += improvement

# Sort improvements by value
sorted_improvements = sorted(
    actual_improvements.items(),
    key=lambda x: x[1]["improvement"],
    reverse=True
)

# Generate summary
phase_summary = {
    "phase": "127",
    "name": "Backend Final Gap Closure",
    "completed_at": datetime.now(timezone.utc).isoformat(),
    "goal": "Achieve 80% backend coverage from 26.15% baseline",
    "baseline_coverage": overall["baseline_coverage"],
    "final_coverage": overall["final_coverage"],
    "overall_improvement": overall["improvement"],
    "individual_file_improvements": round(total_file_improvement, 2),
    "target_coverage": 80.0,
    "target_met": overall["target_met"],
    "gap_remaining": overall.get("gap_to_target", 0),

    # Plans completed
    "plans_completed": [
        {"plan": "127-01", "title": "Baseline Coverage Measurement", "status": "complete"},
        {"plan": "127-02", "title": "Gap Analysis & Test Planning", "status": "complete"},
        {"plan": "127-03", "title": "Models.py Coverage Tests", "status": "complete"},
        {"plan": "127-04", "title": "Workflow Engine Property Tests", "status": "complete"},
        {"plan": "127-05", "title": "Agent Endpoints Integration Tests", "status": "complete"},
        {"plan": "127-06", "title": "Final Verification", "status": "complete"},
    ],

    # Tests added
    "tests_added": {
        "total": sum(planned_tests.values()),
        "by_component": planned_tests,
        "test_files": test_files
    },

    # Component improvements (individual file level)
    "component_improvements": reports,

    # Individual file improvements (actual measured)
    "individual_file_improvements": [
        {"file": k, **v} for k, v in sorted_improvements
    ],

    # Top improved files
    "top_improvements": [
        {"file": k, **v} for k, v in sorted_improvements[:5]
    ],

    # Next steps
    "next_steps": [
        "If target met: Proceed to Phase 128 (Backend API Contract Testing)",
        "Gap remains (53.85 pp): Continue systematic test addition for high-impact files",
        "Focus on integration tests that actually increase coverage (not property tests)",
        "Prioritize files with most missing lines: workflow_engine.py (1089 lines), byok_handler.py (582 lines)",
        "Add endpoint integration tests for all API routes (200+ tests needed)",
        "Add service layer unit tests for core business logic (150+ tests needed)",
        "Continue enforcing 80% coverage gate in CI"
    ],

    # Quality gate status
    "quality_gate": {
        "threshold": 80.0,
        "current": overall["final_coverage"],
        "enforced": True,
        "status": "pass" if overall["target_met"] else "fail"
    },

    # Key findings
    "key_findings": [
        "Overall backend coverage unchanged at 26.15% (improvements isolated to 3 files)",
        "Individual file improvements: models.py (+0.21 pp), atom_agent_endpoints.py (+5.17 pp)",
        "Property tests for workflow_engine.py don't increase coverage (test algorithms independently)",
        "80% target requires 53.85 percentage points improvement (significant work remaining)",
        "Current tests improve code correctness but don't substantially increase coverage metrics",
        "Integration tests needed for actual coverage increase (not unit/property tests)"
    ]
}

# Write summary
output_path = Path("tests/coverage_reports/metrics/phase_127_summary.json")
with open(output_path, "w") as f:
    json.dump(phase_summary, f, indent=2)

# Print formatted summary
print(f"\n{'='*70}")
print(f"PHASE 127: BACKEND FINAL GAP CLOSURE - COMPLETION SUMMARY")
print(f"{'='*70}")
print(f"\n📊 COVERAGE:")
print(f"  Baseline:  {phase_summary['baseline_coverage']:.2f}%")
print(f"  Final:      {phase_summary['final_coverage']:.2f}%")
print(f"  Overall:    {phase_summary['overall_improvement']:+.2f} percentage points")
print(f"  Individual: {total_file_improvement:+.2f} pp (3 files)")
print(f"  Target:     {phase_summary['target_coverage']:.2f}%")
print(f"  Status:     {'✓ MET' if phase_summary['target_met'] else '⚠ CONTINUE'}")
if not phase_summary['target_met']:
    print(f"  Gap:        {phase_summary['gap_remaining']:.2f} pp remaining")

print(f"\n📝 PLANS COMPLETED: {len(phase_summary['plans_completed'])}/6")
for plan in phase_summary['plans_completed']:
    print(f"  ✓ {plan['plan']}: {plan['title']}")

print(f"\n🧪 TESTS ADDED: {phase_summary['tests_added']['total']} total")
for component, count in phase_summary['tests_added']['by_component'].items():
    print(f"  - {component}: {count} tests")

print(f"\n📈 INDIVIDUAL FILE IMPROVEMENTS:")
for item in phase_summary['individual_file_improvements']:
    print(f"  {item['file']}: {item['baseline']:.1f}% → {item['final']:.1f}% ({item['improvement']:+.2f} pp)")

print(f"\n🔑 KEY FINDINGS:")
for i, finding in enumerate(phase_summary['key_findings'], 1):
    print(f"  {i}. {finding}")

print(f"\n🚀 NEXT STEPS:")
for step in phase_summary['next_steps'][:3]:
    print(f"  • {step}")

print(f"\n{'='*70}\n")
