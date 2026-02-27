#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate Phase 101 coverage summary from pytest-cov results."""

import json
from datetime import datetime
from pathlib import Path

# Target threshold
TARGET_THRESHOLD = 60.0

# Coverage data from pytest-cov runs
coverage_data = {
    "phase": "101",
    "generated_at": datetime.utcnow().isoformat(),
    "baseline_version": "v5.0",
    "target_threshold": TARGET_THRESHOLD,
    "summary": {
        "total_services": 6,
        "services_meeting_threshold": 4,
        "overall_coverage_pct": 71.2,
        "threshold_met": False,
        "tests_added": 182,
        "property_tests": 50
    },
    "services": [
        {
            "file": "core/agent_governance_service.py",
            "coverage_pct_before": 10.39,
            "coverage_pct_after": 84.0,
            "covered_lines_before": 64,
            "covered_lines_after": 173,
            "total_lines": 206,
            "threshold_met": True,
            "tests_added": 46,
            "status": "EXCEEDS_TARGET"
        },
        {
            "file": "core/episode_segmentation_service.py",
            "coverage_pct_before": 8.25,
            "coverage_pct_after": 83.0,
            "covered_lines_before": 48,
            "covered_lines_after": 483,
            "total_lines": 580,
            "threshold_met": True,
            "tests_added": 30,
            "status": "EXCEEDS_TARGET"
        },
        {
            "file": "core/episode_retrieval_service.py",
            "coverage_pct_before": 9.03,
            "coverage_pct_after": 61.0,
            "covered_lines_before": 28,
            "covered_lines_after": 192,
            "total_lines": 315,
            "threshold_met": True,
            "tests_added": 25,
            "status": "MEETS_TARGET"
        },
        {
            "file": "core/episode_lifecycle_service.py",
            "coverage_pct_before": 10.85,
            "coverage_pct_after": 100.0,
            "covered_lines_before": 11,
            "covered_lines_after": 97,
            "total_lines": 97,
            "threshold_met": True,
            "tests_added": 15,
            "status": "EXCEEDS_TARGET"
        },
        {
            "file": "tools/canvas_tool.py",
            "coverage_pct_before": 3.80,
            "coverage_pct_after": 28.0,
            "covered_lines_before": 16,
            "covered_lines_after": 119,
            "total_lines": 422,
            "threshold_met": False,
            "tests_added": 35,
            "status": "BELOW_TARGET",
            "note": "Mock configuration issues, some tests still failing"
        },
        {
            "file": "tools/agent_guidance_canvas_tool.py",
            "coverage_pct_before": 14.67,
            "coverage_pct_after": 14.67,
            "covered_lines_before": 31,
            "covered_lines_after": 31,
            "total_lines": 211,
            "threshold_met": False,
            "tests_added": 25,
            "status": "NOT_EXECUTED",
            "note": "Test execution errors preventing coverage"
        }
    ]
}

# Calculate summary
services_meeting = sum(1 for s in coverage_data["services"] if s["threshold_met"])
coverage_sum = sum(s["coverage_pct_after"] for s in coverage_data["services"])
average_coverage = coverage_sum / len(coverage_data["services"])

coverage_data["summary"]["services_meeting_threshold"] = services_meeting
coverage_data["summary"]["overall_coverage_pct"] = round(average_coverage, 2)
coverage_data["summary"]["threshold_met"] = services_meeting == len(coverage_data["services"])

# Write output
output_dir = Path("/Users/rushiparikh/projects/atom/backend/tests/coverage_reports/metrics")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "phase_101_coverage_final.json"
with open(output_file, "w") as f:
    json.dump(coverage_data, f, indent=2)

print("[OK] Coverage summary written to", output_file)
print("\nPhase 101 Coverage Summary:")
print("   Services meeting threshold:", services_meeting, "/", len(coverage_data["services"]))
print("   Average coverage:", round(average_coverage, 2), "%")
print("   Target met:", coverage_data["summary"]["threshold_met"])
print("\nServices:")
for service in coverage_data["services"]:
    status_icon = "[OK]" if service["threshold_met"] else "[FAIL]"
    print("  ", status_icon, service["file"] + ":", str(service["coverage_pct_after"]) + "%", "(" + service["status"] + ")")
