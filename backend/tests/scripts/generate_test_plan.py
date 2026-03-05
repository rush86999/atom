#!/usr/bin/env python3
"""
Generate detailed test plan from gap analysis.

Creates file-to-test mapping with estimated coverage gain for efficient 80% target achievement.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

# Test type patterns based on file characteristics
TEST_PATTERNS = {
    # Models: unit tests for CRUD, relationships, validation
    "models.py": {
        "test_type": "unit",
        "test_class_prefix": "Test",
        "tests": [
            "test_create_{model}",
            "test_read_{model}",
            "test_update_{model}",
            "test_delete_{model}",
            "test_{model}_relationships",
            "test_{model}_validation",
            "test_{model}_edge_cases"
        ],
        "efficiency": 0.5  # 50% of lines covered per test pattern
    },
    # Workflow engines: property tests for DAG validation
    "workflow_engine.py": {
        "test_type": "property",
        "test_class_prefix": "TestProperty",
        "tests": [
            "test_dag_acyclic",
            "test_dag_topological_order",
            "test_workflow_execution_order",
            "test_parallel_steps_independent",
            "test_workflow_rollback_on_failure"
        ],
        "efficiency": 0.6,
    },
    # Endpoints: integration tests with TestClient
    "endpoints.py": {
        "test_type": "integration",
        "test_class_prefix": "TestAPI",
        "tests": [
            "test_get_{resource}",
            "test_post_{resource}",
            "test_put_{resource}",
            "test_delete_{resource}",
            "test_{resource}_not_found",
            "test_{resource}_validation_error"
        ],
        "efficiency": 0.4,  # API tests cover fewer lines per test
    },
    # Services: unit tests for business logic
    "service.py": {
        "test_type": "unit",
        "test_class_prefix": "Test",
        "tests": [
            "test_{service}_happy_path",
            "test_{service}_error_handling",
            "test_{service}_edge_cases",
            "test_{service}_validation"
        ],
        "efficiency": 0.55,
    }
}


def determine_test_pattern(file_path: str, lines_total: int, complexity: str) -> dict:
    """Determine test pattern based on file characteristics."""
    if "models.py" in file_path:
        return TEST_PATTERNS["models.py"]
    elif "workflow" in file_path and "engine" in file_path:
        return TEST_PATTERNS["workflow_engine.py"]
    elif "endpoint" in file_path or "routes.py" in file_path or "api/" in file_path:
        return TEST_PATTERNS["endpoints.py"]
    elif "service.py" in file_path or "_service.py" in file_path:
        return TEST_PATTERNS["service.py"]
    else:
        # Default to unit tests
        return {
            "test_type": "unit",
            "test_class_prefix": "Test",
            "tests": ["test_happy_path", "test_error_handling", "test_edge_cases"],
            "efficiency": 0.4,
        }


def main():
    """Generate test plan from gap analysis."""
    # Load gap analysis
    gap_analysis_path = Path("tests/coverage_reports/metrics/phase_127_gap_analysis.json")
    with open(gap_analysis_path) as f:
        gap_data = json.load(f)

    # Generate test plan
    test_plan = {
        "phase": "127",
        "plan": "02",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_coverage": gap_data["baseline_coverage"],
        "target_coverage": 80.0,
        "gap_to_close": gap_data["gap_to_target"],
        "strategy": "Focus on highest-impact files with maximum coverage gain per test",
        "plans": []
    }

    for priority_level in ["high_impact_files", "medium_impact_files", "low_impact_files"]:
        if priority_level not in gap_data:
            continue

        # Take ALL files from high/medium impact, top 15 from low
        # This ensures we have enough tests to reach 80%
        limit = None if priority_level != "low_impact_files" else 15

        for file_info in gap_data[priority_level][:limit]:
            file_path = file_info["file"]
            missing_lines = file_info["lines_missing"]
            complexity = file_info["complexity"]
            impact = file_info["business_impact"]

            pattern = determine_test_pattern(file_path, file_info["lines_total"], complexity)

            # Calculate number of tests needed - be more aggressive
            estimated_gain_per_test = missing_lines * pattern["efficiency"] / len(pattern["tests"])
            # More tests for larger files to maximize coverage
            tests_needed = min(len(pattern["tests"]) * 2, max(5, int(missing_lines / 50)))

            # Assign to implementation plan based on impact and priority
            if impact == "high" and priority_level == "high_impact_files":
                # Top high-impact files go to 127-03 or 127-04
                if "workflow_engine" in file_path or "atom_agent_endpoints" in file_path:
                    implementation_plan = "127-04"
                elif "models.py" in file_path:
                    implementation_plan = "127-03"
                else:
                    implementation_plan = "127-04"
            elif impact == "high" or priority_level == "high_impact_files":
                implementation_plan = "127-04"
            elif impact == "medium" or priority_level == "medium_impact_files":
                implementation_plan = "127-05"
            else:
                implementation_plan = "127-06"  # Final sweep

            # Extract model/service name from file path
            file_name = file_path.split("/")[-1].replace(".py", "")
            if "test_" in file_name:
                file_name = file_name.replace("test_", "")

            test_plan["plans"].append({
                "file": file_path,
                "current_coverage": file_info["coverage_percent"],
                "lines_missing": missing_lines,
                "estimated_gain_per_test": round(estimated_gain_per_test, 1),
                "tests_planned": tests_needed,
                "test_type": pattern["test_type"],
                "test_class_prefix": pattern["test_class_prefix"],
                "complexity": complexity,
                "business_impact": impact,
                "implementation_plan": implementation_plan,
                "test_names": [
                    t.format(model=file_name, service=file_name, resource=file_name, file=file_name)
                    for t in pattern["tests"][:tests_needed]
                ]
            })

    # Calculate projected coverage
    total_lines_missing = gap_data["total_missing_lines"]
    total_projected_gain = sum(
        p["tests_planned"] * p["estimated_gain_per_test"]
        for p in test_plan["plans"]
    )

    # More accurate projection: percentage of missing lines covered
    # Each test covers estimated_gain_per_test lines from the missing lines
    # Projected coverage = baseline + (total_gain / total_missing_lines * gap_to_target)
    coverage_gain_percentage = (total_projected_gain / total_lines_missing) * 100
    projected_coverage = gap_data["baseline_coverage"] + coverage_gain_percentage

    test_plan["projected_coverage"] = round(projected_coverage, 2)
    test_plan["total_tests_planned"] = sum(p["tests_planned"] for p in test_plan["plans"])
    test_plan["total_estimated_gain"] = round(total_projected_gain, 1)

    # Group by implementation plan
    test_plan["plans_by_implementation"] = {
        "127-03": [p for p in test_plan["plans"] if p["implementation_plan"] == "127-03"],
        "127-04": [p for p in test_plan["plans"] if p["implementation_plan"] == "127-04"],
        "127-05": [p for p in test_plan["plans"] if p["implementation_plan"] == "127-05"],
        "127-06": [p for p in test_plan["plans"] if p["implementation_plan"] == "127-06"],
    }

    # Write output
    output_path = Path("tests/coverage_reports/metrics/phase_127_test_plan.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(test_plan, f, indent=2)

    # Print summary
    print(f"Test Plan Generated:")
    print(f"  Total tests planned: {test_plan['total_tests_planned']}")
    print(f"  Projected coverage: {test_plan['projected_coverage']:.2f}%")
    print(f"  Plan 127-03: {len(test_plan['plans_by_implementation']['127-03'])} files")
    print(f"  Plan 127-04: {len(test_plan['plans_by_implementation']['127-04'])} files")
    print(f"  Plan 127-05: {len(test_plan['plans_by_implementation']['127-05'])} files")
    print(f"  Plan 127-06: {len(test_plan['plans_by_implementation']['127-06'])} files")
    print(f"\nTop 5 files with most tests:")
    for i, plan in enumerate(sorted(test_plan["plans"], key=lambda x: x["tests_planned"], reverse=True)[:5], 1):
        print(f"  {i}. {plan['file']}: {plan['tests_planned']} tests")


if __name__ == "__main__":
    main()
