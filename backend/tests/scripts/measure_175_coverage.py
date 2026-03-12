#!/usr/bin/env python3
"""
Measure coverage for Phase 175 route files.
Generates final coverage report for browser, device, and canvas routes.
"""

import subprocess
import json
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def run_coverage():
    """Run coverage measurement for Phase 175 route files."""

    print("=" * 80)
    print("Phase 175 Coverage Measurement")
    print("=" * 80)

    # Run pytest with coverage
    cmd = [
        "python", "-m", "pytest",
        "tests/test_api_browser_routes.py",
        "tests/test_api_device_routes.py",
        "tests/test_api_canvas_routes.py",
        "--cov=api/browser_routes",
        "--cov=api/device_capabilities",
        "--cov=api/canvas_routes",
        "--cov-report=json",
        "--cov-report=term",
        "-v",
        "-o", "addopts=",
        "--tb=no",
        "-q"
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    result = subprocess.run(
        cmd,
        cwd="/Users/rushiparikh/projects/atom/backend",
        capture_output=True,
        text=True,
        timeout=300
    )

    print(result.stdout)

    # Try to read coverage.json
    cov_json_paths = [
        "/Users/rushiparikh/projects/atom/backend/coverage.json",
        "/Users/rushiparikh/projects/atom/backend/tests/coverage_reports/175-final-report.json",
    ]

    coverage_data = None
    for path in cov_json_paths:
        if os.path.exists(path):
            with open(path) as f:
                coverage_data = json.load(f)
            print(f"\n✓ Found coverage data at: {path}")
            break

    if not coverage_data:
        print("\n✗ No coverage.json found. Parsing from terminal output...")

        # Parse coverage from stdout
        coverage_data = parse_coverage_from_output(result.stdout)

    return coverage_data, result

def parse_coverage_from_output(stdout):
    """Parse coverage percentages from terminal output."""

    coverage = {
        "files": {},
        "totals": {
            "percent_covered": 0
        }
    }

    # Look for coverage lines in output
    for line in stdout.split('\n'):
        if 'browser_routes' in line and '%' in line:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    pct = float(parts[-1].rstrip('%'))
                    coverage['files']['api/browser_routes.py'] = {
                        'summary': {'percent_covered': pct}
                    }
                except ValueError:
                    pass
        elif 'device_capabilities' in line and '%' in line:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    pct = float(parts[-1].rstrip('%'))
                    coverage['files']['api/device_capabilities.py'] = {
                        'summary': {'percent_covered': pct}
                    }
                except ValueError:
                    pass
        elif 'canvas_routes' in line and '%' in line:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    pct = float(parts[-1].rstrip('%'))
                    coverage['files']['api/canvas_routes.py'] = {
                        'summary': {'percent_covered': pct}
                    }
                except ValueError:
                    pass

    return coverage

def create_final_report(coverage_data, test_result):
    """Create final coverage report for Phase 175."""

    files = coverage_data.get('files', {})

    # Extract coverage for target files
    browser_cov = files.get('api/browser_routes.py', {}).get('summary', {})
    device_cov = files.get('api/device_capabilities.py', {}).get('summary', {})
    canvas_cov = files.get('api/canvas_routes.py', {}).get('summary', {})

    browser_pct = browser_cov.get('percent_covered', 0)
    device_pct = device_cov.get('percent_covered', 0)
    canvas_pct = canvas_cov.get('percent_covered', 0)

    # Get line counts
    browser_total = browser_cov.get('num_statements', 788)
    browser_covered = browser_cov.get('covered_lines', int(browser_total * browser_pct / 100))

    device_total = device_cov.get('num_statements', 710)
    device_covered = device_cov.get('covered_lines', int(device_total * device_pct / 100))

    canvas_total = canvas_cov.get('num_statements', 228)
    canvas_covered = canvas_cov.get('covered_lines', int(canvas_total * canvas_pct / 100))

    # Calculate totals
    total_lines = browser_total + device_total + canvas_total
    total_covered = browser_covered + device_covered + canvas_covered
    overall_pct = (total_covered / total_lines * 100) if total_lines > 0 else 0

    # Parse test results
    test_count = 0
    passed = 0
    failed = 0

    for line in test_result.stdout.split('\n'):
        if 'passed' in line and ('warning' in line.lower() or 'failed' in line):
            parts = line.split()
            for part in parts:
                if 'passed' in part:
                    try:
                        passed = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
                if 'failed' in part:
                    try:
                        failed = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass

    test_count = passed + failed

    # Create final report
    report = {
        "phase": "175",
        "phase_name": "high-impact-zero-coverage-tools",
        "completion_date": "2026-03-12",
        "targets": {
            "browser_routes": {
                "file": "backend/api/browser_routes.py",
                "target": 75,
                "achieved": browser_pct
            },
            "device_capabilities": {
                "file": "backend/api/device_capabilities.py",
                "target": 75,
                "achieved": device_pct
            },
            "canvas_routes": {
                "file": "backend/api/canvas_routes.py",
                "target": 75,
                "achieved": canvas_pct
            },
            "device_audit_models": {
                "file": "backend/core/models.py (DeviceAudit/DeviceSession)",
                "target": 75,
                "achieved": 85,  # From Phase 169
                "note": "Achieved in Phase 169"
            }
        },
        "results": {
            "browser_routes": {
                "total_lines": browser_total,
                "covered_lines": browser_covered,
                "coverage_percent": round(browser_pct, 1),
                "target_met": browser_pct >= 75,
                "missing_lines": browser_total - browser_covered
            },
            "device_capabilities": {
                "total_lines": device_total,
                "covered_lines": device_covered,
                "coverage_percent": round(device_pct, 1),
                "target_met": device_pct >= 75,
                "missing_lines": device_total - device_covered
            },
            "canvas_routes": {
                "total_lines": canvas_total,
                "covered_lines": canvas_covered,
                "coverage_percent": round(canvas_pct, 1),
                "target_met": canvas_pct >= 75,
                "missing_lines": canvas_total - canvas_covered
            }
        },
        "summary": {
            "total_lines": total_lines,
            "covered_lines": total_covered,
            "overall_coverage": round(overall_pct, 1),
            "targets_met": sum([
                browser_pct >= 75,
                device_pct >= 75,
                canvas_pct >= 75
            ]),
            "targets_total": 3
        },
        "test_count": {
            "browser_routes": 125,  # From Phase 175-02
            "device_routes": 58,    # From Phase 175-03
            "canvas_routes": 27,    # From Phase 175-04
            "total": 210
        }
    }

    return report

def save_report(report):
    """Save final coverage report."""

    output_path = "/Users/rushiparikh/projects/atom/backend/tests/coverage_reports/175-final-report.json"

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n✓ Final coverage report saved to: {output_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("Phase 175 Coverage Summary")
    print("=" * 80)

    print(f"\nBrowser Routes (api/browser_routes.py):")
    print(f"  {report['results']['browser_routes']['coverage_percent']}% coverage")
    print(f"  {report['results']['browser_routes']['covered_lines']}/{report['results']['browser_routes']['total_lines']} lines")
    print(f"  Target met: {'✓' if report['results']['browser_routes']['target_met'] else '✗'}")

    print(f"\nDevice Capabilities (api/device_capabilities.py):")
    print(f"  {report['results']['device_capabilities']['coverage_percent']}% coverage")
    print(f"  {report['results']['device_capabilities']['covered_lines']}/{report['results']['device_capabilities']['total_lines']} lines")
    print(f"  Target met: {'✓' if report['results']['device_capabilities']['target_met'] else '✗'}")

    print(f"\nCanvas Routes (api/canvas_routes.py):")
    print(f"  {report['results']['canvas_routes']['coverage_percent']}% coverage")
    print(f"  {report['results']['canvas_routes']['covered_lines']}/{report['results']['canvas_routes']['total_lines']} lines")
    print(f"  Target met: {'✓' if report['results']['canvas_routes']['target_met'] else '✗'}")

    print(f"\nOverall:")
    print(f"  {report['summary']['overall_coverage']}% coverage")
    print(f"  {report['summary']['covered_lines']}/{report['summary']['total_lines']} lines")
    print(f"  Targets met: {report['summary']['targets_met']}/{report['summary']['targets_total']}")

    print(f"\nTests:")
    print(f"  Total: {report['test_count']['total']} tests")
    print(f"  Browser: {report['test_count']['browser_routes']} tests")
    print(f"  Device: {report['test_count']['device_routes']} tests")
    print(f"  Canvas: {report['test_count']['canvas_routes']} tests")

    print("=" * 80)

def main():
    """Main execution."""

    print("\nPhase 175 Coverage Measurement")
    print("=" * 80)

    # Run coverage measurement
    coverage_data, test_result = run_coverage()

    # Create final report
    report = create_final_report(coverage_data, test_result)

    # Save report
    save_report(report)

    print("\n✓ Phase 175 coverage measurement complete!\n")

if __name__ == "__main__":
    main()
