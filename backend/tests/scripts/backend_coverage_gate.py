#!/usr/bin/env python3
"""
Backend Coverage Quality Gate

Implements progressive coverage thresholds (70% → 75% → 80%) for backend
with actual line coverage measurement from coverage.py JSON output.

Integrates with emergency bypass mechanism for critical PRs while maintaining
audit trail and frequency monitoring.

Usage:
    # Normal mode: run pytest and enforce threshold
    python backend_coverage_gate.py

    # With baseline comparison (requires 163-01 baseline)
    python backend_coverage_gate.py --baseline backend/tests/coverage_reports/backend_163_baseline.json

    # Override threshold (emergency)
    COVERAGE_THRESHOLD_OVERRIDE=70 python backend_coverage_gate.py

    # With emergency bypass justification
    BYPASS_REASON=\"Security fix: Critical auth vulnerability\" python backend_coverage_gate.py

Exit codes:
    0 = pass (coverage >= threshold)
    1 = fail (coverage < threshold)
    2 = error (invalid configuration, missing files, etc.)

CI/CD Integration:
    This script returns CI/CD-compatible exit codes for use in GitHub Actions,
    GitLab CI, Jenkins, etc.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple


# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
COVERAGE_JSON_PATH = SCRIPT_DIR.parent / "coverage_reports" / "metrics" / "coverage.json"
BASELINE_PATH = SCRIPT_DIR.parent / "coverage_reports" / "backend_163_baseline.json"

# Progressive thresholds
PROGRESSIVE_THRESHOLDS = {
    "phase_1": 70.0,   # Minimum enforcement
    "phase_2": 75.0,   # Interim target
    "phase_3": 80.0,   # Final target
}

# Default phase
DEFAULT_PHASE = "phase_1"


def get_current_phase() -> str:
    """Get current coverage phase from environment."""
    return os.getenv("COVERAGE_PHASE", DEFAULT_PHASE)


def get_threshold(phase: Optional[str] = None) -> float:
    """Get coverage threshold for current phase."""
    if phase is None:
        phase = get_current_phase()
    return PROGRESSIVE_THRESHOLDS.get(phase, PROGRESSIVE_THRESHOLDS[DEFAULT_PHASE])


def check_threshold_override() -> Optional[float]:
    """Check for threshold override via environment variable."""
    override = os.getenv("COVERAGE_THRESHOLD_OVERRIDE")
    if override:
        try:
            return float(override)
        except ValueError:
            print(f"⚠️  Invalid COVERAGE_THRESHOLD_OVERRIDE: {override} (must be numeric)")
            return None
    return None


def run_coverage_measurement() -> bool:
    """
    Run pytest with coverage to generate coverage.json.

    Returns:
        True if coverage measurement succeeded, False otherwise
    """
    print("🔬 Running coverage measurement...")
    print()

    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "--cov=core",
        "--cov=api",
        "--cov=tools",
        "--cov-branch",
        "--cov-report=json:" + str(COVERAGE_JSON_PATH),
        "--cov-report=term-missing:skip-covered",
        "-q",  # Quiet output
    ]

    print(f"Executing: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        # Show pytest output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            print(f"⚠️  Pytest exited with code {result.returncode} (continuing with coverage check)")
            print()

        return True

    except subprocess.TimeoutExpired:
        print("❌ ERROR: Coverage measurement timed out after 10 minutes")
        return False
    except FileNotFoundError:
        print("❌ ERROR: pytest not found. Install with: pip install pytest pytest-cov")
        return False
    except Exception as e:
        print(f"❌ ERROR: Coverage measurement failed: {e}")
        return False


def parse_coverage_json(json_path: Path) -> Optional[Dict]:
    """
    Parse coverage.json and extract overall metrics.

    Args:
        json_path: Path to coverage.json

    Returns:
        Dict with coverage metrics or None if parsing failed
    """
    if not json_path.exists():
        print(f"❌ ERROR: Coverage file not found: {json_path}")
        return None

    try:
        with open(json_path, 'r') as f:
            coverage_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON in {json_path}: {e}")
        return None
    except IOError as e:
        print(f"❌ ERROR: Failed to read {json_path}: {e}")
        return None

    # Validate structure
    if "totals" not in coverage_data:
        print("❌ ERROR: coverage.json missing 'totals' section")
        return None

    totals = coverage_data["totals"]

    # Check for actual line coverage data (not just service-level estimates)
    # coverage.py uses 'covered_lines' and 'num_statements' in totals
    if "num_statements" not in totals:
        print("❌ ERROR: coverage.json missing line coverage metrics")
        print("   Expected: totals.covered_lines and totals.num_statements")
        print("   This indicates service-level aggregation, not actual line coverage")
        return None

    # Check for either 'covered_lines' or 'line_covered' (different coverage.py versions)
    if "covered_lines" not in totals and "line_covered" not in totals:
        print("❌ ERROR: coverage.json missing line coverage metrics")
        print("   Expected: totals.covered_lines or totals.line_covered")
        print("   This indicates service-level aggregation, not actual line coverage")
        return None

    return coverage_data


def calculate_coverage_percentage(totals: Dict) -> float:
    """
    Calculate actual line coverage percentage from coverage.py totals.

    Args:
        totals: coverage.json['totals'] dict

    Returns:
        Coverage percentage (covered_lines / num_statements * 100)
    """
    # coverage.py uses 'covered_lines' in newer versions, 'line_covered' in older
    line_covered = totals.get("covered_lines") or totals.get("line_covered", 0)
    num_statements = totals.get("num_statements", 1)

    if num_statements == 0:
        return 0.0

    return (line_covered / num_statements) * 100


def compare_with_baseline(current_coverage: float, baseline_path: Path) -> Optional[Dict]:
    """
    Compare current coverage with baseline.

    Args:
        current_coverage: Current coverage percentage
        baseline_path: Path to baseline JSON file

    Returns:
        Dict with baseline comparison data or None if baseline not found
    """
    if not baseline_path.exists():
        print(f"⚠️  Baseline not found: {baseline_path}")
        print("   Run plan 163-01 to generate baseline: generate_baseline_coverage_report.py")
        print()
        return None

    try:
        with open(baseline_path, 'r') as f:
            baseline_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Warning: Failed to read baseline: {e}")
        return None

    if "totals" not in baseline_data:
        print("⚠️  Warning: Baseline missing 'totals' section")
        return None

    baseline_totals = baseline_data["totals"]
    baseline_coverage = calculate_coverage_percentage(baseline_totals)

    coverage_delta = current_coverage - baseline_coverage

    return {
        "baseline_coverage": baseline_coverage,
        "current_coverage": current_coverage,
        "delta": coverage_delta,
        "delta_str": f"+{coverage_delta:.2f}%" if coverage_delta >= 0 else f"{coverage_delta:.2f}%"
    }


def check_emergency_bypass(justification: str) -> bool:
    """
    Check if emergency bypass is eligible with given justification.

    Args:
        justification: Bypass justification (required, >= 20 chars)

    Returns:
        True if bypass granted, False otherwise
    """
    # Import emergency bypass module
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        import emergency_coverage_bypass

        return emergency_coverage_bypass.check_bypass_eligibility(justification)
    except ImportError as e:
        print(f"❌ ERROR: Failed to import emergency_coverage_bypass: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: Emergency bypass check failed: {e}")
        return False


def print_gate_summary(
    coverage_percent: float,
    threshold: float,
    phase: str,
    baseline_comparison: Optional[Dict] = None
):
    """Print coverage gate summary."""
    print("=" * 60)
    print("BACKEND COVERAGE GATE")
    print("=" * 60)
    print()
    print(f"Phase: {phase.upper()}")
    print(f"Threshold: {threshold:.1f}%")
    print(f"Coverage: {coverage_percent:.2f}%")
    print()

    if baseline_comparison:
        print("Baseline Comparison:")
        print(f"  Baseline: {baseline_comparison['baseline_coverage']:.2f}%")
        print(f"  Current: {baseline_comparison['current_coverage']:.2f}%")
        print(f"  Delta: {baseline_comparison['delta_str']}")
        print()

    # Gap analysis
    gap = coverage_percent - threshold

    if gap >= 0:
        # Coverage meets or exceeds threshold
        if phase == "phase_1":
            print(f"✅ PASS: Coverage meets {threshold:.1f}% minimum threshold")
        elif phase == "phase_2":
            print(f"✅ PASS: Coverage meets {threshold:.1f}% interim target")
        else:
            print(f"✅ PASS: Coverage meets {threshold:.1f}% final target")
    else:
        # Coverage below threshold
        print(f"❌ FAIL: Coverage {coverage_percent:.2f}% below {threshold:.1f}% threshold")
        print(f"   Gap: {abs(gap):.2f} percentage points")
        print()

    print()


def print_progressive_warning(coverage_percent: float, phase: str):
    """Print progressive warnings for approaching thresholds."""
    if phase == "phase_1" and coverage_percent >= 75.0:
        print("📈 INFO: Coverage approaching Phase 2 threshold (75%)")
        print()
    elif phase == "phase_2" and coverage_percent >= 80.0:
        print("📈 INFO: Coverage approaching Phase 3 threshold (80%)")
        print()


def main():
    """Main coverage gate logic."""
    parser = argparse.ArgumentParser(
        description="Backend coverage quality gate with progressive thresholds"
    )

    parser.add_argument(
        "--phase",
        type=str,
        choices=["phase_1", "phase_2", "phase_3"],
        default=None,
        help="Override COVERAGE_PHASE environment variable"
    )

    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Path to baseline JSON for comparison (default: backend/tests/coverage_reports/backend_163_baseline.json)"
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override coverage threshold (overrides phase-based threshold)"
    )

    parser.add_argument(
        "--no-measure",
        action="store_true",
        help="Skip coverage measurement (use existing coverage.json)"
    )

    parser.add_argument(
        "--bypass-justification",
        type=str,
        default=None,
        help="Emergency bypass justification (>= 20 characters required)"
    )

    args = parser.parse_args()

    # Get phase and threshold
    phase = args.phase if args.phase else get_current_phase()

    # Check for threshold override
    override_threshold = check_threshold_override()
    if override_threshold is not None:
        threshold = override_threshold
        print(f"⚠️  THRESHOLD OVERRIDE: {threshold:.1f}% (via COVERAGE_THRESHOLD_OVERRIDE)")
        print()
    elif args.threshold:
        threshold = args.threshold
        print(f"⚠️  THRESHOLD OVERRIDE: {threshold:.1f}% (via CLI argument)")
        print()
    else:
        threshold = get_threshold(phase)

    # Run coverage measurement (unless skipped)
    if not args.no_measure:
        if not run_coverage_measurement():
            print("❌ ERROR: Coverage measurement failed")
            return 2

    # Parse coverage.json
    coverage_data = parse_coverage_json(COVERAGE_JSON_PATH)
    if coverage_data is None:
        return 2

    # Calculate actual line coverage
    totals = coverage_data["totals"]
    coverage_percent = calculate_coverage_percentage(totals)

    # Compare with baseline (if exists)
    baseline_path = args.baseline if args.baseline else BASELINE_PATH
    baseline_comparison = compare_with_baseline(coverage_percent, baseline_path)

    # Print summary
    print_gate_summary(coverage_percent, threshold, phase, baseline_comparison)

    # Print progressive warnings
    print_progressive_warning(coverage_percent, phase)

    # Check if coverage meets threshold
    if coverage_percent >= threshold:
        # Coverage meets threshold - PASS
        return 0

    # Coverage below threshold - check for emergency bypass
    print("❌ COVERAGE BELOW THRESHOLD")
    print()

    # Check for bypass justification
    bypass_justification = args.bypass_justification or os.getenv("BYPASS_REASON")

    if bypass_justification:
        print("🚨 Emergency bypass requested...")
        print()

        if check_emergency_bypass(bypass_justification):
            print()
            print("⚠️  BYPASS GRANTED: Coverage gate bypassed via emergency justification")
            print("   This bypass has been logged to the audit trail")
            print()
            return 0  # Bypass granted - pass CI/CD
        else:
            print()
            print("❌ BYPASS REJECTED: Justification insufficient or bypass not eligible")
            print()
            return 1  # Bypass rejected - fail CI/CD
    else:
        # No bypass - fail with instructions
        print("Coverage gate enforcement active.")
        print()
        print("Options:")
        print("  1. Add tests to improve coverage above threshold")
        print(f"  2. Use emergency bypass: BYPASS_REASON=\"<justification>\" {sys.argv[0]}")
        print("     Justification must be >= 20 characters")
        print("     Example: 'Security fix: Critical auth vulnerability in production'")
        print()

        return 1  # Fail CI/CD


if __name__ == "__main__":
    sys.exit(main())
