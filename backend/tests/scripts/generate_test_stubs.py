#!/usr/bin/env python3
"""
Test Stub Generator for Phase 164

Generates scaffolded test files for uncovered code using gap-driven analysis.
Creates pytest-compatible test stubs with proper imports, fixtures, and
placeholder tests targeting specific missing lines.

Usage:
    cd backend
    python tests/scripts/generate_test_stubs.py \
        --gap-analysis tests/coverage_reports/metrics/backend_164_gap_analysis.json \
        --tier Critical \
        --limit 10 \
        --output-dir tests/unit

Output:
    - Scaffolded test files: tests/unit/test_<module>.py
    - Each stub includes: imports, fixtures, placeholder tests
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Testing patterns library - templates for different test types
TEST_PATTERNS = {
    "unit": {
        "description": "Unit tests for business logic with mocked dependencies",
        "imports": [
            "import pytest",
            "from unittest.mock import Mock, MagicMock, patch",
        ],
        "fixture_template": """
@pytest.fixture
def {module_name}_fixture():
    \"\"\"Fixture for {class_name} testing.\"\"\"
    # TODO: Initialize {class_name} instance
    pass
""",
        "test_template": """
def test_{function_name}_{scenario}({fixture_arg}):
    \"\"\"Test {function_name} - {scenario} scenario.

    TODO: Implement test for missing lines: {missing_lines}

    Context:
        File: {file_path}
        Module: {module_name}
        Coverage Gap: {gap_lines} lines
    \"\"\"
    # TODO: Arrange - Set up test data and mocks

    # TODO: Act - Call the function being tested

    # TODO: Assert - Verify expected behavior

    pytest.skip("Stub test - implementation needed")
""",
    },
    "integration": {
        "description": "Integration tests with TestClient for API routes",
        "imports": [
            "import pytest",
            "from fastapi.testclient import TestClient",
            "from main import app",  # Adjust based on actual app location
        ],
        "fixture_template": """
@pytest.fixture
def client():
    \"\"\"Fixture for FastAPI TestClient.\"\"\"
    return TestClient(app)
""",
        "test_template": """
def test_{endpoint}_{scenario}(client):
    \"\"\"Test {endpoint} endpoint - {scenario} scenario.

    TODO: Implement integration test for missing lines: {missing_lines}

    Context:
        File: {file_path}
        Endpoint: {endpoint}
        Coverage Gap: {gap_lines} lines
    \"\"\"
    # TODO: Arrange - Set up test data

    # TODO: Act - Make API request
    # response = client.{method}("/{endpoint}")

    # TODO: Assert - Verify response
    # assert response.status_code == 200

    pytest.skip("Stub test - implementation needed")
""",
    },
    "property": {
        "description": "Property-based tests with Hypothesis for invariants",
        "imports": [
            "import pytest",
            "from hypothesis import given, strategies as st",
        ],
        "fixture_template": "",
        "test_template": """
@given({strategy_args})
def test_{function_name}_property_{invariant}({input_args}):
    \"\"\"Property test for {function_name} - {invariant} invariant.

    TODO: Implement property test for missing lines: {missing_lines}

    Context:
        File: {file_path}
        Function: {function_name}
        Coverage Gap: {gap_lines} lines

    Invariant: {invariant_description}
    \"\"\"
    # TODO: Arrange - Set up test state

    # TODO: Act - Call function with generated inputs

    # TODO: Assert - Verify invariant holds

    pytest.skip("Stub test - implementation needed")
""",
    },
}


def determine_test_type(file_path: str, business_impact: str) -> str:
    """
    Determine appropriate test type based on file characteristics.

    Rules:
    - API routes (api/*, *_routes.py) -> integration
    - Services with complex logic (*_service.py) -> property + unit
    - Models (models.py) -> unit
    - Tools (tools/*) -> unit with mocking
    - Core business logic (core/*) -> property tests for invariants
    """
    if "routes.py" in file_path or "_routes.py" in file_path or file_path.startswith("api/"):
        return "integration"
    elif any(x in file_path for x in ["_service.py", "agent_governance", "episode_", "llm/"]):
        # Core services benefit from property tests
        return "property"
    else:
        return "unit"


def extract_module_info(file_path: str) -> Dict[str, str]:
    """
    Extract module information from file path for test generation.

    Examples:
        core/agent_governance_service.py -> module=agent_governance_service, class=AgentGovernanceService
        api/agent_routes.py -> module=agent_routes, class=AgentRoutes
    """
    # Remove .py extension
    module_name = file_path.replace(".py", "")

    # Extract just the filename (no directory)
    file_name = module_name.split("/")[-1]

    # Convert to class name (snake_case -> PascalCase)
    class_name = "".join(word.capitalize() for word in file_name.split("_"))

    return {
        "module_name": file_name,
        "class_name": class_name,
        "full_path": file_path,
        "import_path": module_name.replace("/", "."),
    }


def generate_strategy_for_type(param_type: str) -> str:
    """Generate Hypothesis strategy for a parameter type."""
    strategies = {
        "str": "st.text()",
        "int": "st.integers(min_value=0, max_value=1000)",
        "float": "st.floats(min_value=0.0, max_value=1000.0)",
        "bool": "st.booleans()",
        "dict": "st.dictionaries(st.text(), st.text())",
        "list": "st.lists(st.text())",
    }
    return strategies.get(param_type, "st.text()")


def generate_test_stub(
    gap_data: Dict[str, Any],
    test_type: str,
    output_dir: Path,
) -> Tuple[bool, str]:
    """
    Generate a test stub file for a coverage gap.

    Returns:
        Tuple of (success, message)
    """
    file_path = gap_data["file"]
    module_info = extract_module_info(file_path)

    # Determine test file path
    test_file_name = f"test_{module_info['module_name']}.py"
    test_file_path = output_dir / test_file_name

    # Check if already exists
    if test_file_path.exists():
        return False, f"Test file already exists: {test_file_path}"

    # Get test pattern
    pattern = TEST_PATTERNS.get(test_type, TEST_PATTERNS["unit"])

    # Generate file header
    lines = [
        f'"""\n',
        f'Test stub for {module_info["class_name"]}\n',
        f'\n',
        f'Generated: {datetime.now().isoformat()}\n',
        f'Source: {file_path}\n',
        f'Coverage Gap: {gap_data["uncovered_lines"]} missing lines\n',
        f'Target Coverage: 80%\n',
        f'Business Impact: {gap_data["business_impact"]}\n',
        f'Priority Score: {gap_data["priority_score"]}\n',
        f'"""\n',
        f'\n',
    ]

    # Add imports
    lines.extend([f"{imp}\n" for imp in pattern["imports"]])

    # Add module import
    if test_type == "unit":
        lines.append(f"from backend.{module_info['import_path']} import {module_info['class_name']}\n")
    elif test_type == "integration":
        lines.append(f"from backend.{module_info['import_path']} import router\n")

    lines.append("\n")

    # Add fixture if template has one
    if pattern["fixture_template"]:
        fixture = pattern["fixture_template"].format(
            module_name=module_info["module_name"],
            class_name=module_info["class_name"],
        )
        lines.append(fixture)

    # Generate test stubs based on missing lines
    missing_lines = gap_data.get("missing_lines", [])

    # Create placeholder tests for different scenarios
    scenarios = [
        ("happy_path", "normal successful execution"),
        ("error_handling", "error conditions and exceptions"),
        ("edge_cases", "boundary conditions and edge cases"),
    ]

    for i, (scenario, description) in enumerate(scenarios):
        # Determine function name from file path
        function_name = module_info["module_name"].replace("_", "")

        test_template_args = {
            "function_name": function_name,
            "scenario": scenario,
            "missing_lines": str(missing_lines[:10]) if missing_lines else "N/A",
            "gap_lines": gap_data["uncovered_lines"],
            "file_path": file_path,
            "module_name": module_info["module_name"],
            "class_name": module_info["class_name"],
            "fixture_arg": f"{module_info['module_name']}_fixture" if pattern["fixture_template"] else "",
            "endpoint": module_info["module_name"].replace("_", "/"),
            "method": "get",
            "strategy_args": "input=st.text()",
            "input_args": "input",
            "invariant": "idempotency",
            "invariant_description": "Function should produce same output for same input",
        }

        # Add strategy-specific args for property tests
        if test_type == "property":
            test_template_args["strategy_args"] = "value=st.text()"
            test_template_args["input_args"] = "value"

        lines.append(pattern["test_template"].format(**test_template_args))

    # Write test file
    test_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(test_file_path, "w") as f:
        f.writelines(lines)

    return True, f"Generated: {test_file_path}"


def load_gap_analysis(gap_analysis_path: Path) -> Dict[str, Any]:
    """Load gap analysis JSON."""
    with open(gap_analysis_path) as f:
        return json.load(f)


def generate_stubs(
    gap_analysis: Dict[str, Any],
    tier_filter: Optional[str] = None,
    limit: Optional[int] = None,
    output_dir: Path = Path("tests/unit"),
) -> List[Dict[str, Any]]:
    """
    Generate test stubs from gap analysis.

    Args:
        gap_analysis: Gap analysis data from Phase 164-01
        tier_filter: Only generate stubs for this tier (Critical/High/Medium/Low)
        limit: Maximum number of stubs to generate
        output_dir: Base directory for test files

    Returns:
        List of generation results
    """
    results = []
    generated_count = 0

    # Get all gaps from tier breakdown
    all_gaps = []
    for tier in ["Critical", "High", "Medium", "Low"]:
        if tier_filter and tier != tier_filter:
            continue
        tier_data = gap_analysis["tier_breakdown"].get(tier, {})
        tier_gaps = tier_data.get("files", [])
        all_gaps.extend(tier_gaps)

    # Sort by priority score (should already be sorted)
    all_gaps.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

    for gap in all_gaps:
        if limit and generated_count >= limit:
            break

        # Determine test type
        test_type = determine_test_type(gap["file"], gap["business_impact"])

        # Determine output directory based on test type
        if test_type == "integration":
            stub_output_dir = Path("tests/integration")
        elif test_type == "property":
            stub_output_dir = Path("tests/property")
        else:
            stub_output_dir = output_dir

        # Generate stub
        success, message = generate_test_stub(gap, test_type, stub_output_dir)

        results.append({
            "file": gap["file"],
            "test_type": test_type,
            "output_path": str(stub_output_dir),
            "success": success,
            "message": message,
        })

        if success:
            generated_count += 1

    return results


def generate_summary_report(
    results: List[Dict[str, Any]],
    output_path: Path,
) -> None:
    """Generate summary report of generated test stubs."""
    lines = [
        "# Gap-Driven Test Stubs - Phase 164\n",
        f"**Generated**: {datetime.now().isoformat()}\n",
        f"**Total Stubs Generated**: {sum(1 for r in results if r['success'])}\n",
        f"**Total Files Processed**: {len(results)}\n\n",
        "## Generated Test Stubs\n\n",
        "| Source File | Test Type | Output Path | Status |\n",
        "|-------------|-----------|-------------|--------|\n",
    ]

    for result in results:
        lines.append(
            f"| `{result['file']}` | {result['test_type']} | "
            f"{result['output_path']} | {'✅' if result['success'] else '⚠️'} |\n"
        )

    lines.append("\n## Next Steps\n")
    lines.append("1. Review generated test stubs in the output directories\n")
    lines.append("2. Implement placeholder tests with actual assertions\n")
    lines.append("3. Run pytest to verify new tests increase coverage\n")
    lines.append("4. Use coverage report to identify remaining gaps\n")

    with open(output_path, "w") as f:
        f.writelines(lines)

    print(f"Summary report: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate test stubs from coverage gap analysis"
    )
    parser.add_argument(
        "--gap-analysis",
        type=Path,
        default=Path("tests/coverage_reports/metrics/backend_164_gap_analysis.json"),
        help="Path to gap analysis JSON from Phase 164-01",
    )
    parser.add_argument(
        "--tier",
        type=str,
        choices=["Critical", "High", "Medium", "Low"],
        help="Only generate stubs for this business impact tier",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of stubs to generate (default: 10)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/unit"),
        help="Base output directory for test stubs",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("tests/coverage_reports/GAP_DRIVEN_TEST_STUBS.md"),
        help="Output path for summary report",
    )

    args = parser.parse_args()

    # Load gap analysis
    if not args.gap_analysis.exists():
        print(f"Error: Gap analysis not found: {args.gap_analysis}")
        print("Run Phase 164-01 first: python tests/scripts/coverage_gap_analysis.py")
        sys.exit(1)

    with open(args.gap_analysis) as f:
        gap_analysis = json.load(f)

    # Generate stubs
    print(f"Generating test stubs from gap analysis...")
    print(f"  Tier filter: {args.tier or 'All'}")
    print(f"  Limit: {args.limit}")
    print(f"  Output dir: {args.output_dir}")
    print()

    results = generate_stubs(
        gap_analysis,
        tier_filter=args.tier,
        limit=args.limit,
        output_dir=args.output_dir,
    )

    # Print results
    generated = sum(1 for r in results if r["success"])
    print(f"Generated {generated} test stubs")

    for result in results:
        if result["success"]:
            print(f"  ✓ {result['message']}")
        else:
            print(f"  ⚠️  {result['message']}")

    # Generate summary report
    generate_summary_report(results, args.report)


if __name__ == "__main__":
    main()
