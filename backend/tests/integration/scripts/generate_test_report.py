#!/usr/bin/env python3
"""
Test Report Generator for Phase 208 Integration & Performance Testing

Generates comprehensive test reports combining integration, contract, performance,
and quality test results. Supports JSON, HTML, and Markdown output formats.

Usage:
    python generate_test_report.py --format markdown --output TEST_REPORT.md
    python generate_test_report.py --include integration,performance
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TestReportGenerator:
    """Generates comprehensive test reports from multiple test suites."""

    def __init__(self, output: str = "test-report.json", format_type: str = "json",
                 include: Optional[List[str]] = None):
        self.output = Path(output)
        self.format_type = format_type
        self.include = include or ["integration", "contract", "performance", "quality"]
        self.report_data = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "test_suites": {},
            "summary": {}
        }

    def run_test_suite(self, suite_name: str, test_path: str,
                       extra_args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run a test suite and capture results.

        Args:
            suite_name: Name of the test suite
            test_path: Path to tests
            extra_args: Additional pytest arguments

        Returns:
            Dictionary with test results
        """
        print(f"Running {suite_name} tests...")

        cmd = ["pytest", "-v", "--tb=short", test_path]
        if extra_args:
            cmd.extend(extra_args)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )

        # Parse output for test counts
        output = result.stdout + result.stderr
        lines = output.split('\n')

        passed = failed = skipped = 0
        duration = 0.0

        for line in lines:
            if " passed" in line:
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "passed":
                            passed = int(parts[i-1])
                        elif part == "failed":
                            failed = int(parts[i-1])
                        elif part == "skipped":
                            skipped = int(parts[i-1])
                except (ValueError, IndexError):
                    pass
            if "in" in line and "s" in line:
                try:
                    duration_str = line.split("in ")[1].split("s")[0].strip()
                    duration = float(duration_str)
                except (ValueError, IndexError):
                    pass

        return {
            "total": passed + failed + skipped,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration": duration,
            "exit_code": result.returncode,
            "output": output if result.returncode != 0 else ""
        }

    def generate_integration_report(self) -> Dict[str, Any]:
        """Generate integration test report."""
        if "integration" not in self.include:
            return {}

        result = self.run_test_suite(
            "Integration",
            "tests/integration/workflows/"
        )

        return {
            "type": "integration",
            "tests": result,
            "coverage": self._get_coverage_data()
        }

    def generate_contract_report(self) -> Dict[str, Any]:
        """Generate contract test report."""
        if "contract" not in self.include:
            return {}

        result = self.run_test_suite(
            "Contract",
            "tests/integration/contracts/",
            ["-m", "contract"]
        )

        return {
            "type": "contract",
            "tests": result,
            "schema_validations": result.get("passed", 0)
        }

    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate performance test report."""
        if "performance" not in self.include:
            return {}

        result = self.run_test_suite(
            "Performance",
            "tests/integration/performance/",
            ["--benchmark-only"]
        )

        return {
            "type": "performance",
            "tests": result,
            "benchmarks": self._parse_benchmark_data(result.get("output", ""))
        }

    def generate_quality_report(self) -> Dict[str, Any]:
        """Generate quality test report."""
        if "quality" not in self.include:
            return {}

        result = self.run_test_suite(
            "Quality",
            "tests/integration/quality/"
        )

        return {
            "type": "quality",
            "tests": result,
            "flakiness_rate": self._calculate_flakiness_rate(result)
        }

    def _get_coverage_data(self) -> Dict[str, float]:
        """Extract coverage data if available."""
        coverage_file = Path("tests/coverage_reports/metrics/coverage.json")
        if not coverage_file.exists():
            return {}

        try:
            with open(coverage_file) as f:
                data = json.load(f)
                return {
                    "line_coverage": data.get("totals", {}).get("percent_covered", 0),
                    "branch_coverage": data.get("totals", {}).get("percent_covered", 0)
                }
        except (json.JSONDecodeError, KeyError):
            return {}

    def _parse_benchmark_data(self, output: str) -> Dict[str, Any]:
        """Parse benchmark data from pytest-benchmark output."""
        benchmarks = {}
        lines = output.split('\n')

        for line in lines:
            if "P50" in line or "P95" in line or "P99" in line:
                parts = line.split()
                if len(parts) >= 4:
                    name = parts[0]
                    benchmarks[name] = {
                        "p50": float(parts[1]) if len(parts) > 1 else 0,
                        "p95": float(parts[2]) if len(parts) > 2 else 0,
                        "p99": float(parts[3]) if len(parts) > 3 else 0
                    }

        return benchmarks

    def _calculate_flakiness_rate(self, result: Dict[str, Any]) -> float:
        """Calculate flakiness rate from test results."""
        total = result.get("total", 0)
        failed = result.get("failed", 0)

        if total == 0:
            return 0.0

        return round((failed / total) * 100, 2)

    def generate_summary(self) -> Dict[str, Any]:
        """Generate overall summary from all test suites."""
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_duration = 0.0

        for suite_data in self.report_data["test_suites"].values():
            tests = suite_data.get("tests", {})
            total_tests += tests.get("total", 0)
            total_passed += tests.get("passed", 0)
            total_failed += tests.get("failed", 0)
            total_duration += tests.get("duration", 0)

        pass_rate = round((total_passed / total_tests * 100) if total_tests > 0 else 0, 2)

        return {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "pass_rate": pass_rate,
            "total_duration": round(total_duration, 2)
        }

    def generate(self) -> None:
        """Generate the complete test report."""
        # Generate individual suite reports
        integration = self.generate_integration_report()
        if integration:
            self.report_data["test_suites"]["integration"] = integration

        contract = self.generate_contract_report()
        if contract:
            self.report_data["test_suites"]["contract"] = contract

        performance = self.generate_performance_report()
        if performance:
            self.report_data["test_suites"]["performance"] = performance

        quality = self.generate_quality_report()
        if quality:
            self.report_data["test_suites"]["quality"] = quality

        # Generate summary
        self.report_data["summary"] = self.generate_summary()

        # Write output
        self._write_output()

    def _write_output(self) -> None:
        """Write report in specified format."""
        if self.format_type == "json":
            self._write_json()
        elif self.format_type == "html":
            self._write_html()
        elif self.format_type == "markdown":
            self._write_markdown()
        else:
            print(f"Unknown format: {self.format_type}")
            sys.exit(1)

    def _write_json(self) -> None:
        """Write JSON report."""
        with open(self.output, 'w') as f:
            json.dump(self.report_data, f, indent=2)
        print(f"✓ JSON report written to {self.output}")

    def _write_html(self) -> None:
        """Write HTML report."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .suite {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
    </style>
</head>
<body>
    <h1>Test Report</h1>
    <p><strong>Generated:</strong> {self.report_data['generated_at']}</p>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Tests:</strong> {self.report_data['summary']['total_tests']}</p>
        <p><strong>Passed:</strong> <span class="pass">{self.report_data['summary']['total_passed']}</span></p>
        <p><strong>Failed:</strong> <span class="fail">{self.report_data['summary']['total_failed']}</span></p>
        <p><strong>Pass Rate:</strong> {self.report_data['summary']['pass_rate']}%</p>
        <p><strong>Duration:</strong> {self.report_data['summary']['total_duration']}s</p>
    </div>

    <div class="suites">
"""

        for suite_name, suite_data in self.report_data['test_suites'].items():
            tests = suite_data.get('tests', {})
            html += f"""
        <div class="suite">
            <h2>{suite_name.title()} Tests</h2>
            <p><strong>Total:</strong> {tests.get('total', 0)}</p>
            <p><strong>Passed:</strong> <span class="pass">{tests.get('passed', 0)}</span></p>
            <p><strong>Failed:</strong> <span class="fail">{tests.get('failed', 0)}</span></p>
            <p><strong>Duration:</strong> {tests.get('duration', 0)}s</p>
        </div>
"""

        html += """
    </div>
</body>
</html>
"""

        with open(self.output, 'w') as f:
            f.write(html)
        print(f"✓ HTML report written to {self.output}")

    def _write_markdown(self) -> None:
        """Write Markdown report."""
        md = f"""# Test Report

**Generated:** {self.report_data['generated_at']}

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | {self.report_data['summary']['total_tests']} |
| Passed | {self.report_data['summary']['total_passed']} |
| Failed | {self.report_data['summary']['total_failed']} |
| Pass Rate | {self.report_data['summary']['pass_rate']}% |
| Duration | {self.report_data['summary']['total_duration']}s |

## Test Suites

"""

        for suite_name, suite_data in self.report_data['test_suites'].items():
            tests = suite_data.get('tests', {})
            md += f"""### {suite_name.title()} Tests

| Metric | Value |
|--------|-------|
| Total | {tests.get('total', 0)} |
| Passed | {tests.get('passed', 0)} |
| Failed | {tests.get('failed', 0)} |
| Skipped | {tests.get('skipped', 0)} |
| Duration | {tests.get('duration', 0)}s |

"""

            # Add suite-specific details
            if suite_name == "integration" and "coverage" in suite_data:
                coverage = suite_data["coverage"]
                md += f"""**Coverage:**
- Line Coverage: {coverage.get('line_coverage', 0)}%
- Branch Coverage: {coverage.get('branch_coverage', 0)}%

"""

            if suite_name == "performance" and "benchmarks" in suite_data:
                md += "**Benchmarks:**\n\n"
                for name, metrics in suite_data["benchmarks"].items():
                    md += f"- {name}: P50={metrics.get('p50', 0)}ms, P95={metrics.get('p95', 0)}ms, P99={metrics.get('p99', 0)}ms\n"
                md += "\n"

            if suite_name == "quality" and "flakiness_rate" in suite_data:
                md += f"**Flakiness Rate:** {suite_data['flakiness_rate']}%\n\n"

        md += """---

*Generated by Test Report Generator for Phase 208*
"""

        with open(self.output, 'w') as f:
            f.write(md)
        print(f"✓ Markdown report written to {self.output}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate comprehensive test reports for Phase 208"
    )
    parser.add_argument(
        "--output", "-o",
        default="test-report.json",
        help="Output file path (default: test-report.json)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "html", "markdown"],
        default="json",
        help="Output format (default: json)"
    )
    parser.add_argument(
        "--include", "-i",
        default="integration,contract,performance,quality",
        help="Comma-separated list of test types to include"
    )

    args = parser.parse_args()

    include = [s.strip() for s in args.include.split(',')]

    generator = TestReportGenerator(
        output=args.output,
        format_type=args.format,
        include=include
    )

    try:
        generator.generate()
        sys.exit(0)
    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
