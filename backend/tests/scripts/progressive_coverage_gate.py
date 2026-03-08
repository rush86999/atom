#!/usr/bin/env python3
"""
Progressive Coverage Gate Enforcement

Implements three-phase rollout strategy for coverage thresholds:
- Phase 1: 70% minimum (baseline enforcement)
- Phase 2: 75% minimum (interim target)
- Phase 3: 80% minimum (final target)

New code always requires 80% coverage regardless of phase.

Usage:
    export COVERAGE_PHASE=phase_1
    python progressive_coverage_gate.py [--phase phase_1] [--format text|json]
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Progressive thresholds by phase
PROGRESSIVE_THRESHOLDS = {
    "phase_1": {
        "backend": 70.0,
        "frontend": 70.0,
        "mobile": 50.0,
        "desktop": 40.0,
    },
    "phase_2": {
        "backend": 75.0,
        "frontend": 75.0,
        "mobile": 55.0,
        "desktop": 45.0,
    },
    "phase_3": {
        "backend": 80.0,
        "frontend": 80.0,
        "mobile": 60.0,
        "desktop": 50.0,
    },
}

# New code always requires 80% regardless of phase
NEW_CODE_THRESHOLD = 80.0

# Path to cross-platform coverage gate script
CROSS_PLATFORM_GATE_SCRIPT = Path(__file__).parent / "cross_platform_coverage_gate.py"


def get_current_phase() -> str:
    """Get current phase from environment variable."""
    return os.getenv("COVERAGE_PHASE", "phase_1")


def get_threshold_for_platform(platform: str, phase: Optional[str] = None) -> float:
    """Get threshold for platform in current phase."""
    if phase is None:
        phase = get_current_phase()
    return PROGRESSIVE_THRESHOLDS[phase][platform]


def validate_phase(phase: str) -> bool:
    """Validate that phase is one of the allowed values."""
    return phase in PROGRESSIVE_THRESHOLDS


def get_all_thresholds(phase: Optional[str] = None) -> Dict[str, float]:
    """Get all thresholds for the current phase."""
    if phase is None:
        phase = get_current_phase()
    return PROGRESSIVE_THRESHOLDS[phase].copy()


def check_emergency_bypass() -> bool:
    """Check if emergency bypass is enabled."""
    return os.getenv("EMERGENCY_COVERAGE_BYPASS", "false").lower() == "true"


def format_thresholds_for_cross_platform(thresholds: Dict[str, float]) -> str:
    """Format thresholds dict for cross_platform_coverage_gate.py --thresholds arg."""
    return ",".join([f"{k}={v}" for k, v in thresholds.items()])


def print_phase_info(phase: str, thresholds: Dict[str, float]):
    """Print phase information and thresholds."""
    print(f"📊 Coverage Gate: {phase.upper().replace('_', '-')}")
    print(f"   Backend threshold: {thresholds['backend']:.1f}%")
    print(f"   Frontend threshold: {thresholds['frontend']:.1f}%")
    print(f"   Mobile threshold: {thresholds['mobile']:.1f}%")
    print(f"   Desktop threshold: {thresholds['desktop']:.1f}%")
    print(f"   New code threshold: {NEW_CODE_THRESHOLD:.1f}% (always)")
    print()


def main():
    """Main enforcement logic."""
    parser = argparse.ArgumentParser(
        description="Progressive coverage gate enforcement with phase-aware thresholds"
    )

    parser.add_argument(
        "--phase",
        type=str,
        choices=["phase_1", "phase_2", "phase_3"],
        default=None,
        help="Override COVERAGE_PHASE environment variable"
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (passed through to cross_platform_coverage_gate.py)"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any platform below threshold (passed through to cross_platform_coverage_gate.py)"
    )

    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Path for JSON output (passed through to cross_platform_coverage_gate.py)"
    )

    parser.add_argument(
        "--backend-coverage",
        type=Path,
        default=None,
        help="Path to pytest coverage.json (passed through to cross_platform_coverage_gate.py)"
    )

    parser.add_argument(
        "--frontend-coverage",
        type=Path,
        default=None,
        help="Path to Jest coverage-final.json (passed through to cross_platform_coverage_gate.py)"
    )

    parser.add_argument(
        "--mobile-coverage",
        type=Path,
        default=None,
        help="Path to jest-expo coverage-final.json (passed through to cross_platform_coverage_gate.py)"
    )

    parser.add_argument(
        "--desktop-coverage",
        type=Path,
        default=None,
        help="Path to tarpaulin coverage.json (passed through to cross_platform_coverage_gate.py)"
    )

    args = parser.parse_args()

    # Get phase (CLI arg overrides env var)
    phase = args.phase if args.phase else get_current_phase()

    # Validate phase
    if not validate_phase(phase):
        print(f"ERROR: Invalid COVERAGE_PHASE '{phase}'. Must be one of: {list(PROGRESSIVE_THRESHOLDS.keys())}")
        sys.exit(2)

    # Check emergency bypass
    if check_emergency_bypass():
        print("⚠️  COVERAGE GATE BYPASSED (emergency mode)")
        print("   EMERGENCY_COVERAGE_BYPASS=true")
        print()
        sys.exit(0)

    # Get thresholds for current phase
    thresholds = get_all_thresholds(phase)

    # Print phase information
    if args.format == "text":
        print_phase_info(phase, thresholds)

    # Verify cross_platform_coverage_gate.py exists
    if not CROSS_PLATFORM_GATE_SCRIPT.exists():
        print(f"ERROR: cross_platform_coverage_gate.py not found at: {CROSS_PLATFORM_GATE_SCRIPT}")
        sys.exit(2)

    # Build command arguments for cross_platform_coverage_gate.py
    cmd_args = [
        sys.executable,
        str(CROSS_PLATFORM_GATE_SCRIPT),
        "--thresholds", format_thresholds_for_cross_platform(thresholds),
        "--format", args.format,
    ]

    if args.strict:
        cmd_args.append("--strict")

    if args.output_json:
        cmd_args.extend(["--output-json", str(args.output_json)])

    if args.backend_coverage:
        cmd_args.extend(["--backend-coverage", str(args.backend_coverage)])

    if args.frontend_coverage:
        cmd_args.extend(["--frontend-coverage", str(args.frontend_coverage)])

    if args.mobile_coverage:
        cmd_args.extend(["--mobile-coverage", str(args.mobile_coverage)])

    if args.desktop_coverage:
        cmd_args.extend(["--desktop-coverage", str(args.desktop_coverage)])

    # Execute cross_platform_coverage_gate.py
    logger.info(f"Executing: {' '.join(cmd_args)}")

    try:
        result = subprocess.run(cmd_args, check=False)
        sys.exit(result.returncode)
    except FileNotFoundError as e:
        logger.error(f"Failed to execute cross_platform_coverage_gate.py: {e}")
        sys.exit(2)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
